import pytest
from zerorepo.rtl_web.store import Store
from zerorepo.rtl_web.schemas import DemoError


def test_upstream_403_is_actionable_without_exposing_response_body(settings,monkeypatch):
    import asyncio
    from zerorepo.rtl_web.chat import model_decision

    class RejectedProcess:
        returncode=1
        async def communicate(self,payload):
            return b'',b'RTL_DEMO_CHAT_ERROR=LLMRequestError: OpenAI request failed: PermissionDeniedError, HTTP 403\n<html>private diagnostic</html>'

    async def spawn(*args,**kwargs):return RejectedProcess()
    monkeypatch.setattr(asyncio,'create_subprocess_exec',spawn)
    with pytest.raises(DemoError) as error:
        asyncio.run(model_decision(settings,{}))
    assert error.value.code=='model_access_denied'
    assert 'HTTP 403' in str(error.value)
    assert 'private diagnostic' not in str(error.value)


def test_atomic_idempotency_and_global_execution_slot(ledger):
    s = ledger.create_session("a", {})["session_id"]
    request = {"kind": "verify", "context_ref": {"case_id": "e203", "version_id": "v"}}
    op, new = ledger.accept_operation(s, "one", request)
    again, created = ledger.accept_operation(s, "one", request)
    assert new and not created and op["operation_id"] == again["operation_id"]
    with pytest.raises(DemoError) as e:
        ledger.accept_operation(s, "one", {**request, "kind": "fix"})
    assert e.value.code == "idempotency_conflict"
    other = ledger.create_session("b", {})["session_id"]
    with pytest.raises(DemoError) as e:
        ledger.accept_operation(other, "two", request)
    assert e.value.code == "busy"
    assert ledger.claim()["operation_id"] == op["operation_id"]
    assert ledger.claim() is None
    ledger.update_operation(op["operation_id"], state="completed", verdict="fail")
    assert ledger.accept_operation(other, "two", request)[1]


def test_context_and_messages_survive_reconnect(ledger):
    sid = ledger.create_session("a", {"version_id": "before"})["session_id"]
    msg, new = ledger.add_message(
        sid, "m", {"text": "解释架构", "context_ref": {"version_id": "before"}}
    )
    ledger.selection(sid, {"version_id": "after"})
    ledger.update_message(msg["message_id"], state="answered", answer="说明")
    restored = Store(ledger.root).session(sid)
    assert restored["messages"][0]["context_ref"]["version_id"] == "before"
    assert restored["selection"]["version_id"] == "after"
    events = ledger.events(sid)
    assert len(ledger.events(sid, events[-1]["event_id"])) == 0


def test_interruption_does_not_reexecute_running_operation(ledger):
    sid = ledger.create_session("a", {})["session_id"]
    op, _ = ledger.accept_operation(sid, "x", {"kind": "verify", "context_ref": {}})
    ledger.claim()
    ledger.interrupt(operations=True)
    assert ledger.operation(op["operation_id"])["state"] == "interrupted"
    assert ledger.claim() is None


def test_ten_round_api_context_evidence_and_idempotency(settings, bundle):
    from fastapi.testclient import TestClient
    from zerorepo.rtl_web.api import create_app
    from zerorepo.rtl_web.schemas import ChatDecision, EvidenceRef
    import time

    app = create_app(settings)
    seen = []

    async def provider(payload):
        seen.append(payload)
        return ChatDecision(
            kind="answer",
            text="测试替身，仅测试接口",
            evidence_refs=[
                EvidenceRef(artifact_id=bundle["spec_artifact_id"]),
                EvidenceRef(artifact_id="invented"),
            ],
        )

    app.state.decision_provider = provider
    headers = {"Origin": "http://localhost:5173", "X-Demo-Request": "1"}
    with TestClient(app, base_url="http://localhost") as c:
        session = c.post(
            "/api/sessions",
            json={"case_id": "e203"},
            headers={**headers, "Idempotency-Key": "chat-session"},
        ).json()
        sid = session["session_id"]
        ctx = {k: v for k, v in session["selection"].items() if k != "browsing_mode"}
        for i in range(10):
            body = {
                "text": f"question {i}",
                "context_ref": ctx,
                "client_message_id": str(i),
            }
            h = {**headers, "Idempotency-Key": str(i)}
            answer = c.post(f"/api/sessions/{sid}/messages", json=body, headers=h)
            assert answer.status_code == 202
            assert (
                c.post(f"/api/sessions/{sid}/messages", json=body, headers=h).json()[
                    "message_id"
                ]
                == answer.json()["message_id"]
            )
            for _ in range(100):
                current = c.get(f"/api/sessions/{sid}").json()
                if current["messages"][-1]["state"] != "replying":
                    break
                time.sleep(0.005)
            assert current["messages"][-1]["evidence_refs"] == [
                {"artifact_id": bundle["spec_artifact_id"]}
            ]
        assert len(current["messages"]) == 10 and len(seen) == 10
        assert len(seen[-1]["history"]) == 9
        events = app.state.store.events(sid, 0)
        cursor = events[4]["event_id"]
        assert all(e["event_id"] > cursor for e in app.state.store.events(sid, cursor))
        assert all(
            x["evidence"]["context_ref"]["version_id"] == ctx["version_id"]
            for x in seen
        )


def test_context_rejects_other_session_run_and_report(settings, ledger, bundle):
    from zerorepo.rtl_web.chat import validate_context, submit_operation
    from zerorepo.rtl_web.schemas import DemoError
    import pytest

    a = ledger.create_session("owner", {})["session_id"]
    b = ledger.create_session("outsider", {})["session_id"]
    ledger.put("run", "private", {"run_id": "private"}, a)
    with pytest.raises(DemoError, match="无权"):
        validate_context(ledger, b, {"case_id": "e203", "run_id": "private"})
    with pytest.raises(DemoError, match="不一致"):
        validate_context(
            ledger,
            a,
            {
                "version_id": bundle["versions"][0]["version_id"],
                "validation_id": bundle["validations"][-1]["validation_id"],
            },
        )
    with pytest.raises(DemoError, match="不支持"):
        submit_operation(settings, ledger, a, "bad", "shell", {})
