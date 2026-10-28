import pytest
from fastapi.testclient import TestClient
from zerorepo.rtl_web.api import create_app


def test_production_requires_gateway_and_origin(settings):
    settings.development = False
    settings.gateway_key = "test-gateway-only"
    with TestClient(
        create_app(settings), base_url="https://design.deepvalleychip.cn"
    ) as c:
        assert c.get("/api/health").status_code == 401
        assert (
            c.get(
                "/api/health", headers={"X-Demo-Gateway-Key": "test-gateway-only"}
            ).status_code
            == 200
        )
        headers = {
            "X-Demo-Gateway-Key": "test-gateway-only",
            "Idempotency-Key": "session",
            "X-Demo-Request": "1",
            "Origin": "https://evil.invalid",
        }
        assert (
            c.post(
                "/api/sessions", json={"case_id": "e203"}, headers=headers
            ).status_code
            == 403
        )


def test_cross_session_isolation(settings, ledger, bundle):
    with TestClient(
        create_app(settings), base_url="http://127.0.0.1", client=("127.0.0.1", 50000)
    ) as c:
        headers = {
            "Idempotency-Key": "s1",
            "X-Demo-Request": "1",
            "Origin": "http://127.0.0.1:5173",
        }
        one = c.post("/api/sessions", json={"case_id": "e203"}, headers=headers)
        assert one.status_code == 201
        headers["Idempotency-Key"] = "s2"
        two = c.post("/api/sessions", json={"case_id": "e203"}, headers=headers)
        assert two.status_code == 201
        assert c.get("/api/sessions/" + one.json()["session_id"]).status_code == 403


def test_chunked_body_over_budget_rejected_before_side_effect(settings,ledger):
    from fastapi.testclient import TestClient
    from zerorepo.rtl_web.api import create_app
    with TestClient(create_app(settings),base_url="http://127.0.0.1") as client:
        response=client.post('/api/sessions',content=iter([b' '*11000,b' '*11000]),
            headers={'content-type':'application/json','origin':'http://localhost:5173','X-Demo-Request':'1'})
        assert response.status_code==413
        with ledger.connect() as c:
            assert c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]==0


def test_generated_rtl_cannot_publish_selected_provider_credential(tmp_path,monkeypatch):
    from zerorepo.rtl_web.artifacts import Artifacts
    from zerorepo.rtl_web.store import Store
    from zerorepo.rtl_web.schemas import DemoError
    monkeypatch.setenv('CODEX_PROXY_A_API_KEY','synthetic-private-provider-key')
    source=tmp_path/'generated';source.mkdir();(source/'dut.v').write_text('module dut; // synthetic-private-provider-key\nendmodule\n')
    store=Store(tmp_path/'state');art=Artifacts(store.root,store)
    with pytest.raises(DemoError) as err:art.snapshot(source,'version-test','run-test')
    assert err.value.code=='private_output'
    assert not (store.root/'snapshots/version-test').exists()
    assert not store.list_records('version')


def test_private_literal_in_report_is_redacted_before_display(tmp_path):
    from zerorepo.rtl_web.artifacts import Artifacts
    from zerorepo.rtl_web.store import Store
    source=tmp_path/'report.json';source.write_text('{"stdout":"api failed synthetic-literal-credential"}')
    store=Store(tmp_path/'state');art=Artifacts(store.root,store);art.private_values.add('synthetic-literal-credential')
    record=art.add(source,'report',display=True)
    assert 'synthetic-literal-credential' not in art.file(record).read_text()
