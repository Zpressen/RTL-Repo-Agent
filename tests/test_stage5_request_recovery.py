"""No-content retries share a deadline and preserve every attempt's evidence."""
import asyncio
import json

import httpx
import openai
import pytest

from test_retrieval_request_budget import bounded, wire
from zerorepo.rpg_gen.base.llm_client.errors import LLMRequestTimeoutError
from zerorepo.rpg_gen.base.llm_client.providers.bounded_completion import create_bounded_chat_completion
from zerorepo.rpg_gen.base.llm_client.request_policy import LLMRequestOptions, RequestProgress
from zerorepo.rtl_impl.module_planner.utils.llm_client import PlannerLLMClient


@pytest.fixture(autouse=True)
def warm_sdk_platform_metadata():
    # The SDK's first platform probe is synchronous and can take hundreds of
    # milliseconds. Exclude that one-off probe from subsecond transport tests.
    from openai._base_client import platform_headers
    platform_headers(openai.__version__, platform=None)


class WhitespaceBody(httpx.AsyncByteStream):
    def __init__(self, initial=" ", final=None):
        self.initial = initial
        self.final = final
        self.closed = False

    async def __aiter__(self):
        yield wire(self.initial)
        if self.final is not None:
            await asyncio.sleep(0.06)
            yield wire(self.final, "stop")
            yield b"data: [DONE]\n\n"
        else:
            while True:
                await asyncio.sleep(0.008)
                yield wire(" \n")

    async def aclose(self):
        self.closed = True


def test_whitespace_preserved_but_cannot_start_or_extend_progress(tmp_path, monkeypatch):
    now = [100.0]
    monkeypatch.setattr("zerorepo.rpg_gen.base.llm_client.request_policy.time.monotonic", lambda: now[0])
    progress = RequestProgress(LLMRequestOptions(first_content_timeout_seconds=10,
        idle_timeout_seconds=5, draft_root=tmp_path), log=False)
    progress.begin_attempt()
    now[0] = 104
    progress.content(" ")
    now[0] = 109
    progress.content("\n")
    assert progress.first_content is None and progress.effective_chars == 0
    now[0] = 110
    assert progress.timeout() == "first_content_timeout"
    progress.content('{"value":')
    now[0] = 114
    progress.content(" ")
    now[0] = 115
    assert progress.timeout() == "content_idle_timeout"
    progress.publish("failed")
    assert (progress.directory / "attempt_1.partial.txt").read_text() == ' \n{"value": '


def test_delayed_effective_body_uses_first_content_window_not_idle_window(tmp_path):
    body = WhitespaceBody(final='{"ok":true}')
    async def handler(request):
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=body)
    run, clients, snapshots = bounded(tmp_path, handler, total_timeout_seconds=3,
        first_content_timeout_seconds=2, idle_timeout_seconds=0.04)
    assert run().choices[0].message.content == ' {"ok":true}'
    assert body.closed and all(c.is_closed() for c in clients)
    assert any(s["content_chars"] and s["effective_content_chars"] == 0 for s in snapshots)


@pytest.mark.parametrize("initial,reason", [(" ", "first_content_timeout"), ("{", "content_idle_timeout")])
def test_whitespace_heartbeats_do_not_prevent_timeout(tmp_path, initial, reason):
    body = WhitespaceBody(initial=initial)
    async def handler(request):
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=body)
    run, clients, snapshots = bounded(tmp_path, handler, total_timeout_seconds=1,
        first_content_timeout_seconds=0.15, idle_timeout_seconds=0.08)
    with pytest.raises(LLMRequestTimeoutError) as caught:
        run()
    assert caught.value.diagnostics["timeout_reason"] == reason
    assert body.closed and len(clients) == 1 and clients[0].is_closed()
    assert snapshots[-1]["content_chars"] > len(initial)


@pytest.mark.parametrize("condition", ["headers", "whitespace"])
def test_no_content_timeout_retries_once_from_scratch_then_succeeds(tmp_path, monkeypatch, condition):
    monkeypatch.setattr("zerorepo.rpg_gen.base.llm_client.providers.bounded_completion.random.uniform", lambda *_: 0.001)
    calls = []
    body = WhitespaceBody()
    async def handler(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            if condition == "headers":
                await asyncio.sleep(10)
            return httpx.Response(200, headers={"content-type": "text/event-stream", "x-request-id": "first"}, stream=body)
        assert clients[0].is_closed()
        if condition == "whitespace":
            assert body.closed
        return httpx.Response(200, headers={"content-type": "text/event-stream", "x-request-id": "second"},
            content=wire('{"ok":true}', "stop") + b"data: [DONE]\n\n")
    run, clients, snapshots = bounded(tmp_path, handler, total_timeout_seconds=1,
        first_content_timeout_seconds=0.15, retry_first_content_timeout=True)
    assert run().choices[0].message.content == '{"ok":true}'
    assert calls[0] == calls[1] and len(calls) == 2
    retry = next(s for s in snapshots if s["status"] == "retrying")
    assert retry["timeout_reason"] == "first_content_timeout"
    assert snapshots[-1]["attempt"] == 2 and "timeout_reason" not in snapshots[-1]
    assert snapshots[-1]["remaining_seconds"] < retry["remaining_seconds"]
    assert all(c.is_closed() for c in clients)
    directory = next(tmp_path.glob("stage3_module_skeletons/toy/*"))
    assert (directory / "attempt_2.partial.txt").read_text() == '{"ok":true}'
    first = json.loads((directory / "attempt_1.status.json").read_text())
    assert first["timeout_reason"] == "first_content_timeout" and first["status"] == "retrying"
    assert (directory / "attempt_1.partial.txt").read_text().strip() == ""


@pytest.mark.parametrize("retry_enabled,retries,expected_calls", [(False, 1, 1), (True, 0, 1), (True, 1, 2)])
def test_first_content_retry_exhaustion_and_opt_in(tmp_path, monkeypatch, retry_enabled, retries, expected_calls):
    monkeypatch.setattr("zerorepo.rpg_gen.base.llm_client.providers.bounded_completion.random.uniform", lambda *_: 0.001)
    async def handler(request):
        await asyncio.sleep(10)
    run, clients, snapshots = bounded(tmp_path, handler, total_timeout_seconds=1,
        first_content_timeout_seconds=0.15, retry_first_content_timeout=retry_enabled, max_retries=retries)
    with pytest.raises(LLMRequestTimeoutError) as caught:
        run()
    assert caught.value.diagnostics["timeout_reason"] == "first_content_timeout"
    assert len(clients) == expected_calls and all(c.is_closed() for c in clients)
    assert snapshots[-1]["status"] == "failed"


@pytest.mark.parametrize("backoff,attempts", [(0.001, 2), (10, 1)])
def test_no_content_retry_never_resets_total_deadline(tmp_path, monkeypatch, backoff, attempts):
    monkeypatch.setattr("zerorepo.rpg_gen.base.llm_client.providers.bounded_completion.random.uniform", lambda *_: backoff)
    async def handler(request):
        await asyncio.sleep(10)
    run, clients, snapshots = bounded(tmp_path, handler, total_timeout_seconds=0.3,
        first_content_timeout_seconds=0.2, retry_first_content_timeout=True)
    with pytest.raises(LLMRequestTimeoutError) as caught:
        run()
    assert caught.value.diagnostics["timeout_reason"] == "total_timeout"
    assert len(clients) == attempts and all(c.is_closed() for c in clients)
    assert snapshots[-1]["remaining_seconds"] == 0


def test_effective_body_idle_timeout_is_not_retried_even_with_opt_in(tmp_path):
    body = WhitespaceBody(initial="partial")
    async def handler(request):
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=body)
    run, clients, _ = bounded(tmp_path, handler, total_timeout_seconds=1,
        first_content_timeout_seconds=0.4, idle_timeout_seconds=0.08, retry_first_content_timeout=True)
    with pytest.raises(LLMRequestTimeoutError) as caught:
        run()
    assert caught.value.diagnostics["timeout_reason"] == "content_idle_timeout"
    assert len(clients) == 1 and clients[0].is_closed() and body.closed


def test_sdk_default_read_timeout_cannot_preempt_call_budget(tmp_path):
    clients = []
    async def handler(request):
        assert request.extensions["timeout"]["read"] == 1
        assert request.extensions["timeout"]["connect"] == 1
        await asyncio.sleep(0.04)
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
            content=wire("OK", "stop") + b"data: [DONE]\n\n")
    def factory():
        client = openai.AsyncOpenAI(api_key="local-test", max_retries=0, timeout=0.01,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        clients.append(client)
        return client
    result = create_bounded_chat_completion(factory, {"model": "mock", "messages": []}, stream=True,
        options=LLMRequestOptions(total_timeout_seconds=1, first_content_timeout_seconds=0.4), log=False)
    assert result.choices[0].message.content == "OK" and clients[0].is_closed()


def test_stage5_policy_is_separate_from_retrieval_and_other_generation():
    llm = PlannerLLMClient(backend=lambda **kwargs: None)
    stage5 = llm.request_options(stage="stage5_codegen", module="toy")
    assert (stage5.total_timeout_seconds, stage5.first_content_timeout_seconds, stage5.idle_timeout_seconds) == (600, 240, 120)
    assert stage5.retry_first_content_timeout and stage5.max_retries == 1
    for stage, retrieval in [("stage3_module_skeletons", False), ("stage4_spec_blocks", True)]:
        options = llm.request_options(stage=stage, module="toy", retrieval=retrieval)
        assert options.first_content_timeout_seconds == 120 and not options.retry_first_content_timeout
    llm.request_policy = {"stages": {"stage5_codegen": {"first_content_timeout_seconds": 180, "retry_first_content_timeout": False}}}
    override = llm.request_options(stage="stage5_codegen", module="toy")
    assert override.first_content_timeout_seconds == 180 and not override.retry_first_content_timeout
