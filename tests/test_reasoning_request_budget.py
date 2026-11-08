"""Reasoning streams remain observable, private, cancellable and bounded."""
from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
import traceback

import httpx
import openai
import pytest

from test_retrieval_request_budget import bounded, wire
from test_rtl_module_planner import make_task_input
from zerorepo.rpg_gen.base.llm_client import Memory, SystemMessage, UserMessage
from zerorepo.rpg_gen.base.llm_client.errors import LLMRequestTimeoutError
from zerorepo.rpg_gen.base.llm_client.providers.bounded_completion import _reasoning_chars, create_bounded_chat_completion
from zerorepo.rpg_gen.base.llm_client.request_policy import LLMRequestOptions, RequestProgress
from zerorepo.rtl_impl.module_planner.agents import Stage3Agent
from zerorepo.rtl_impl.module_planner.utils import PlannerLLMClient
from zerorepo.rtl_impl.module_planner.utils.execution import RequestExecutor
from zerorepo.rtl_impl.public_progress import request_failure_summary, request_progress_callback


@pytest.fixture(scope="module", autouse=True)
def warm_sdk_platform_metadata():
    # SDK environment discovery and lazy model/parser setup are synchronous
    # first-use work. Warm the actual mock transport before short timing tests.
    from openai._base_client import platform_headers
    platform_headers(openai.__version__, platform=None)
    async def handler(request):
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
            content=reasoning_wire("warm") + wire("warm", "stop") + b"data: [DONE]\n\n")
    def factory():
        client = openai.AsyncOpenAI(api_key="local-test", max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        client._platform = "Linux"
        return client
    create_bounded_chat_completion(factory, {"model": "mock", "messages": []}, stream=True,
        options=LLMRequestOptions(total_timeout_seconds=30, first_content_timeout_seconds=30), log=False)


@pytest.fixture
def clock(monkeypatch):
    now = [0.0]
    monkeypatch.setattr("zerorepo.rpg_gen.base.llm_client.request_policy.time.monotonic", lambda: now[0])
    return now


def progress(**kwargs):
    options = dict(total_timeout_seconds=20, first_content_timeout_seconds=2,
                   reasoning_timeout_seconds=10, idle_timeout_seconds=3)
    options.update(kwargs)
    result = RequestProgress(LLMRequestOptions(**options), log=False)
    result.begin_attempt()
    return result


def test_real_reasoning_can_outlast_first_body_wait_but_not_body_idle(clock):
    p = progress()
    clock[0] = 1
    p.content("", reasoning_chars=8)
    clock[0] = 3
    assert p.timeout() is None and p.phase == "reasoning"
    assert p.first_content is None and p.text == "" and p.next_wakeup() == 1
    p.content("", reasoning_chars=7)
    clock[0] = 5
    p.content('{"ok": true}')
    assert p.phase == "streaming" and p.first_content == 5
    clock[0] = 8
    p.content("", reasoning_chars=3)
    assert p.timeout() == "content_idle_timeout"


@pytest.mark.parametrize("text", ["", " ", "\n"])
def test_empty_events_cannot_activate_reasoning_budget(clock, text):
    p = progress()
    for current in (0.5, 1, 1.5, 2):
        clock[0] = current
        p.content(text)
    assert p.timeout() == "first_content_timeout"
    assert p.reasoning_chars == 0 and p.empty_chunks == 4


@pytest.mark.parametrize("limit,elapsed,expected", [(20, 10, "reasoning_timeout"), (6, 6, "total_timeout")])
def test_active_reasoning_has_absolute_and_shared_total_deadlines(clock, limit, elapsed, expected):
    p = progress(total_timeout_seconds=limit)
    for current in range(1, elapsed + 1):
        clock[0] = current
        p.content("", reasoning_chars=4)
    assert p.timeout() == expected
    assert p.first_content is None


def test_reasoning_idle_and_disabled_allowance_and_retry_reset(clock):
    p = progress()
    clock[0] = 1
    p.content("", reasoning_chars=4)
    clock[0] = 4
    assert p.timeout() == "reasoning_idle_timeout"
    p.begin_attempt()
    assert p.first_reasoning is None and p.reasoning_chars == 0 and p.reasoning_chunks == 0
    assert p.deadline == 20  # A new transport attempt cannot restart the total budget.
    p = progress(reasoning_timeout_seconds=None)
    clock[0] = 5
    p.content("", reasoning_chars=9)
    clock[0] = 6
    assert p.timeout() == "first_content_timeout"


@pytest.mark.parametrize("bad", [0, -1])
def test_reasoning_budget_must_be_positive(bad):
    with pytest.raises(ValueError, match="reasoning_timeout_seconds"):
        LLMRequestOptions(reasoning_timeout_seconds=bad)


@pytest.mark.parametrize("value,count", [
    ({"reasoning_content": "private"}, 7),
    ({"reasoning": "private"}, 7),
    ({"reasoning": [{"type": "text", "text": "private"}]}, 7),
    ({"reasoning_content": "private", "reasoning": "private"}, 7),
    ({"reasoning_content": "  "}, 0),
    ({"reasoning": {"state": "thinking"}}, 0),
    ({"reasoning": 42}, 0),
])
def test_reasoning_aliases_count_only_actual_text(value, count):
    assert _reasoning_chars(SimpleNamespace(**value)) == count


def test_reasoning_text_never_enters_persisted_drafts_or_callbacks(clock, tmp_path):
    callbacks = []
    private = "PRIVATE_REASONING_DO_NOT_PERSIST"
    p = progress(draft_root=tmp_path, content_callback=callbacks.append)
    p.content("", reasoning_chars=_reasoning_chars(SimpleNamespace(reasoning_content=private)))
    p.publish()
    assert (p.directory / "attempt_1.partial.txt").read_text() == ""
    p.content("answer")
    p.publish("completed")
    assert callbacks == ["answer"]
    assert (p.directory / "attempt_1.partial.txt").read_text() == "answer"
    for path in tmp_path.rglob("*"):
        if path.is_file():
            assert private not in path.read_text()


def reasoning_wire(text, key="reasoning_content"):
    payload = {"id": "mock", "object": "chat.completion.chunk", "created": 0, "model": "mock",
               "choices": [{"index": 0, "delta": {key: text}, "finish_reason": None}]}
    return ("data: " + json.dumps(payload) + "\n\n").encode()


class ReasoningBody(httpx.AsyncByteStream):
    def __init__(self, mode="answer", key="reasoning_content"):
        self.mode, self.key, self.closed = mode, key, False

    async def __aiter__(self):
        for _ in range(8):
            yield reasoning_wire("PRIVATE_REASONING_DO_NOT_PERSIST", self.key)
            if self.mode == "idle":
                break
            await asyncio.sleep(0.05)
        if self.mode == "answer":
            yield wire('{"ok":true}', "stop")
            yield b"data: [DONE]\n\n"
        else:
            while True:
                yield reasoning_wire("PRIVATE_REASONING_DO_NOT_PERSIST", self.key) if self.mode == "active" else wire("")
                await asyncio.sleep(0.02)

    async def aclose(self):
        self.closed = True


@pytest.mark.parametrize("key", ["reasoning_content", "reasoning"])
def test_http_reasoning_before_answer_is_not_false_empty_timeout_and_not_persisted(tmp_path, key):
    body = ReasoningBody(key=key)
    async def handler(request):
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=body)
    callbacks = []
    run, clients, snapshots = bounded(tmp_path, handler, total_timeout_seconds=2,
        first_content_timeout_seconds=0.3, reasoning_timeout_seconds=1.4, idle_timeout_seconds=0.2,
        content_callback=callbacks.append, draft_root=None)
    result = run()
    assert result.choices[0].message.content == '{"ok":true}'
    assert any(s["waiting_phase"] == "reasoning" for s in snapshots)
    assert snapshots[-1]["reasoning_chunks"] == 8 and snapshots[-1]["content_chunks"] == 1
    assert snapshots[-1]["first_content_seconds"] > 0.3
    assert body.closed and all(c.is_closed() for c in clients)
    assert "PRIVATE_REASONING" not in json.dumps(snapshots) + json.dumps(callbacks)


@pytest.mark.parametrize("mode,total,reasoning,idle,expected", [
    ("active", 2, 0.55, 0.2, "reasoning_timeout"),
    ("idle", 2, 1.4, 0.2, "reasoning_idle_timeout"),
    ("active", 0.55, 1.4, 0.2, "total_timeout"),
])
def test_http_reasoning_still_cancels_and_explains_timeout(tmp_path, mode, total, reasoning, idle, expected):
    body = ReasoningBody(mode)
    async def handler(request):
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=body)
    run, clients, snapshots = bounded(tmp_path, handler, total_timeout_seconds=total,
        first_content_timeout_seconds=0.3, reasoning_timeout_seconds=reasoning,
        idle_timeout_seconds=idle, max_retries=0, draft_root=None)
    with pytest.raises(LLMRequestTimeoutError) as caught:
        run()
    assert caught.value.diagnostics["timeout_reason"] == expected
    assert caught.value.diagnostics["reasoning_chars"] > 0
    assert snapshots[-1]["content_chars"] == 0 and body.closed and all(c.is_closed() for c in clients)
    assert "no running event loop" not in "".join(traceback.format_exception(caught.value))


def test_http_reasoning_timeout_retries_after_closing_old_stream(tmp_path, monkeypatch):
    monkeypatch.setattr("zerorepo.rpg_gen.base.llm_client.providers.bounded_completion.random.uniform", lambda *args: 0)
    body = ReasoningBody("active")
    calls = []
    async def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=body)
        assert body.closed and clients[0].is_closed()
        return httpx.Response(200, headers={"content-type": "text/event-stream"},
                              content=wire("OK", "stop") + b"data: [DONE]\n\n")
    run, clients, snapshots = bounded(tmp_path, handler, total_timeout_seconds=2,
        first_content_timeout_seconds=0.3, reasoning_timeout_seconds=0.55, idle_timeout_seconds=0.2,
        max_retries=1, retry_first_content_timeout=True, draft_root=None)
    assert run().choices[0].message.content == "OK" and len(calls) == 2
    retry = next(s for s in snapshots if s["status"] == "retrying")
    assert retry["timeout_reason"] == "reasoning_timeout" and retry["reasoning_chars"] > 0
    assert snapshots[-1]["attempt"] == 2 and snapshots[-1]["reasoning_chars"] == 0


def test_http_heartbeats_do_not_get_reasoning_allowance(tmp_path):
    body = ReasoningBody("idle", key="not_reasoning")
    async def handler(request):
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=body)
    run, clients, snapshots = bounded(tmp_path, handler, total_timeout_seconds=2,
        first_content_timeout_seconds=0.3, reasoning_timeout_seconds=1.4, max_retries=0, draft_root=None)
    with pytest.raises(LLMRequestTimeoutError) as caught:
        run()
    assert caught.value.diagnostics["timeout_reason"] == "first_content_timeout"
    assert snapshots[-1]["reasoning_chars"] == 0 and snapshots[-1]["empty_chunks"] > 0
    assert body.closed and all(c.is_closed() for c in clients)


def test_request_usage_keeps_reasoning_counters_without_guessing_tokens(tmp_path):
    task, *_ = make_task_input(tmp_path, image_count=0)
    executor = RequestExecutor(tmp_path / "case")
    executor.begin_run(task, resume=False)
    body = ReasoningBody()
    async def handler(request):
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=body)
    from openai import AsyncOpenAI
    def method(*, request_options):
        def factory():
            client = AsyncOpenAI(api_key="local-test", max_retries=0,
                http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
            client._platform = "Linux"
            return client
        result = create_bounded_chat_completion(factory, {"model": "mock", "messages": []},
            stream=True, options=request_options, log=False)
        return result.choices[0].message.content
    options = LLMRequestOptions(stage="stage3_module_skeletons", module="toy", total_timeout_seconds=2,
        first_content_timeout_seconds=0.3, reasoning_timeout_seconds=1.4, idle_timeout_seconds=0.2)
    assert executor.execute(method, {}, options, bounded=True) == '{"ok":true}'
    usage = json.loads((executor.root / "plan/state/request_usage.jsonl").read_text().splitlines()[-1])
    assert usage["reasoning_chars"] > 0 and usage["reasoning_chunks"] == 8
    assert usage["usage"] is None and usage["output_chars"] == len('{"ok":true}')
    assert "PRIVATE_REASONING" not in json.dumps(usage)


def test_stage3_defaults_and_explicit_overrides():
    client = PlannerLLMClient(backend=lambda **kwargs: None)
    options = client.request_options(stage="stage3_module_skeletons", module="toy")
    assert (options.total_timeout_seconds, options.first_content_timeout_seconds, options.reasoning_timeout_seconds) == (1200, 480, 900)
    client.request_policy = {"generation": {"total_timeout_seconds": 300, "first_content_timeout_seconds": 90},
                             "stages": {"stage3_module_skeletons": {"reasoning_timeout_seconds": 200}}}
    options = client.request_options(stage="stage3_module_skeletons", module="toy")
    assert (options.total_timeout_seconds, options.first_content_timeout_seconds, options.reasoning_timeout_seconds) == (300, 90, 200)
    assert client.request_options(stage="stage5_codegen", module="toy").reasoning_timeout_seconds is None
    assert client.request_options(stage="stage3_spec_retrieval", module="toy", retrieval=True).reasoning_timeout_seconds is None


def test_wait_policy_change_resumes_existing_stage3_candidate(tmp_path):
    from test_planning_harness import RaisingBackend, ToyAdapter
    from test_rtl_module_planner import QueueBackend
    task, *_ = make_task_input(tmp_path, image_count=0)
    root = tmp_path / "case"
    interrupted = RaisingBackend([{"value": 0}, LLMRequestTimeoutError("old wait limit")])
    client = PlannerLLMClient(backend=interrupted, request_policy={"stages": {
        "stage3_module_skeletons": {"first_content_timeout_seconds": 240, "total_timeout_seconds": 600,
                                    "reasoning_timeout_seconds": None}}})
    client.configure_execution(root)
    client.executor.begin_run(task, resume=False)
    with pytest.raises(LLMRequestTimeoutError):
        Stage3Agent(client)._invoke_local_repair(prompt="same specification", images=[], adapter=ToyAdapter())
    backend = QueueBackend([{"patches": [{"target": "value", "replacement": 1}]}])
    client = PlannerLLMClient(backend=backend)
    client.configure_execution(root)
    client.executor.begin_run(task, resume=True)
    result = Stage3Agent(client)._invoke_local_repair(prompt="same specification", images=[], adapter=ToyAdapter())
    assert result.artifact.value == 1 and len(backend.calls) == 1
    assert "Repair ONLY" in backend.calls[0]["user_prompt"]


@pytest.mark.parametrize("observing", [False, True])
def test_stage3_cli_workbench_share_reasoning_policy(tmp_path, monkeypatch, observing):
    class Backend:
        def complete_with_memory(self, *, memory, images=None, request_options=None):
            self.options = request_options
            return '{"ok":true}'
    backend = Backend()
    client = PlannerLLMClient(backend=backend)
    client.configure_execution(tmp_path)
    monkeypatch.setattr("zerorepo.rtl_impl.module_planner.agents.base.is_observing", lambda: observing)
    memory = Memory()
    memory.add_message(SystemMessage(content="system"))
    memory.add_message(UserMessage(content="generate"))
    Stage3Agent(client)._complete_public(memory=memory, module="toy")
    assert backend.options.first_content_timeout_seconds == 480 and backend.options.reasoning_timeout_seconds == 900
    assert backend.options.total_timeout_seconds <= 1200


def test_workbench_explains_reasoning_without_disclosing_text():
    events = []
    options = LLMRequestOptions(reasoning_timeout_seconds=900)
    callback = request_progress_callback(lambda *args, **kwargs: events.append(kwargs),
        {"stage": "plan", "action_id": "a", "substage": "stage3", "label": "规划"}, options)
    callback({"status": "running", "elapsed_seconds": 20, "waiting_phase": "reasoning", "reasoning_chars": 300,
              "effective_content_chars": 0, "remaining_seconds": 100})
    assert events[0]["reason_code"] == "request_reasoning" and "正在推理" in events[0]["result_summary"]
    for reason in ("reasoning_timeout", "reasoning_idle_timeout"):
        assert "推理" in request_failure_summary(LLMRequestTimeoutError("timeout", timeout_reason=reason))
