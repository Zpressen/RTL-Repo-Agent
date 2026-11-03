"""Exercise actual SDK stream aggregation and the planner's error boundary."""

import json

import httpx
import openai
import pytest
from pydantic import BaseModel

from zerorepo.rpg_gen.base.llm_client import LLMClient, LLMConfig, Memory, UserMessage
from zerorepo.rpg_gen.base.llm_client.errors import (
    IncompleteLLMResponseError, LLMRequestError, LLMResponseTruncatedError,
)
from zerorepo.rpg_gen.base.llm_client.providers.openai_client import OpenAIProvider
from zerorepo.rtl_impl.module_planner.agents.base import BaseStageAgent
from zerorepo.rtl_impl.module_planner.utils.llm_client import DefaultPlannerLLMBackend, PlannerLLMClient


def chunk(delta, finish=None):
    return {
        "id": "test-stream", "object": "chat.completion.chunk", "created": 0, "model": "test-model",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish}],
    }


def sse(chunks):
    return "".join(f"data: {json.dumps(c)}\n\n" for c in chunks).encode() + b"data: [DONE]\n\n"


def streaming_response(chunks):
    return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=sse(chunks))


def config(**overrides):
    return LLMConfig.from_dict({
        "provider": "openai", "model": "test-model", "api_key": "local-test-key",
        "stream": True, "stream_include_usage": True, "max_retries": 1, "log": False,
        **overrides,
    })


@pytest.fixture
def sdk_factory(monkeypatch):
    monkeypatch.setattr("zerorepo.rpg_gen.base.llm_client.providers.retry_utils.time.sleep", lambda _: None)

    def install(handler):
        clients = []

        def create(cfg):
            client = openai.OpenAI(
                api_key=cfg.api_key,
                http_client=httpx.Client(transport=httpx.MockTransport(handler)),
            )
            clients.append(client)
            return client

        monkeypatch.setattr(OpenAIProvider, "create_client", lambda self, cfg: create(cfg))
        return create, clients

    return install


def test_stream_aggregates_text_usage_and_sends_configuration(sdk_factory):
    requests = []
    usage = {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18}

    def handler(request):
        requests.append(json.loads(request.content))
        return streaming_response([
            chunk({"role": "assistant", "content": '{"value":'}),
            chunk({"content": "7}"}, "stop"),
            {**chunk({}), "choices": [], "usage": usage},
        ])

    _, clients = sdk_factory(handler)
    llm = LLMClient(config())
    memory = Memory()
    memory.add_message(UserMessage(content="extract facts"))
    assert llm.generate(memory) == '{"value":7}'
    assert llm.last_usage["input_tokens"] == 11
    assert llm.last_usage["output_tokens"] == 7
    assert requests[0]["stream"] is True
    assert requests[0]["stream_options"] == {"include_usage": True}
    assert clients[-1].max_retries == 0
    assert clients[0].is_closed()


def test_stream_aggregates_fragmented_tool_arguments(sdk_factory):
    sdk_factory(lambda request: streaming_response([
        chunk({"role": "assistant", "tool_calls": [{"index": 0, "id": "call_1", "type": "function",
                                                      "function": {"name": "lookup", "arguments": '{"id":'}}]}),
        chunk({"tool_calls": [{"index": 0, "function": {"arguments": "7}"}}]}, "tool_calls"),
    ]))
    llm = LLMClient(config())
    response = llm.client.chat([UserMessage(content="lookup")], reuse_history=False)
    assert response.finish_reason == "tool_calls"
    assert response.tool_calls[0].name == "lookup"
    assert response.tool_calls[0].arguments == {"id": 7}
    assert response.tool_calls[0].call_id == "call_1"


@pytest.mark.parametrize("chunks", [[], [chunk({"role": "assistant", "content": '{"value":7}'})]])
def test_incomplete_stream_retries_without_committing_partial_content(sdk_factory, chunks):
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        return streaming_response(chunks)

    sdk_factory(handler)
    llm = LLMClient(config())
    memory = Memory()
    memory.add_message(UserMessage(content="extract facts"))
    with pytest.raises(IncompleteLLMResponseError):
        llm.generate(memory, max_retries=8)
    assert len(calls) == 2  # One provider retry; no outer generate retries.
    assert calls[0]["messages"] == calls[1]["messages"]
    assert all(message["role"] != "assistant" for message in llm.client.message_history)
    assert not hasattr(llm, "_last_response")


class BrokenStream(httpx.SyncByteStream):
    def __init__(self):
        self.closed = False

    def __iter__(self):
        yield sse([chunk({"role": "assistant", "content": "discard this partial response"})]).split(b"data: [DONE]")[0]
        raise httpx.RemoteProtocolError("Server disconnected")

    def close(self):
        self.closed = True


def test_disconnect_during_stream_retries_from_scratch_and_closes_response(sdk_factory):
    broken = BrokenStream()
    calls = []

    def handler(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=broken)
        return streaming_response([chunk({"role": "assistant", "content": '{"value":7}'}, "stop")])

    sdk_factory(handler)
    llm = LLMClient(config())
    memory = Memory()
    memory.add_message(UserMessage(content="extract facts"))
    assert llm.generate(memory) == '{"value":7}'
    assert len(calls) == 2
    assert broken.closed
    assert llm.client.message_history[-1]["content"] == '{"value":7}'


@pytest.mark.parametrize("status,expected_calls", [(400, 1), (401, 1), (403, 1), (408, 2), (409, 2), (429, 2), (500, 2)])
def test_status_retry_policy_and_structured_output_propagation(sdk_factory, status, expected_calls):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={"error": {"message": "test error"}})

    sdk_factory(handler)
    llm = LLMClient(config())
    memory = Memory()
    memory.add_message(UserMessage(content="extract facts"))

    class Artifact(BaseModel):
        value: int

    with pytest.raises(LLMRequestError) as caught:
        llm.call_with_structure_output(memory, Artifact, max_retries=3)
    assert len(calls) == expected_calls
    assert isinstance(caught.value.__cause__, openai.APIStatusError)
    assert caught.value.__cause__.status_code == status


@pytest.mark.parametrize("stream", [False, True])
def test_output_limit_is_fatal_for_both_transports(sdk_factory, stream):
    calls = []

    def handler(request):
        calls.append(request)
        if stream:
            return streaming_response([chunk({"role": "assistant", "content": '{"value":'}, "length")])
        return httpx.Response(200, json={
            "id": "test", "object": "chat.completion", "created": 0, "model": "test-model",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": '{"value":'}, "finish_reason": "length"}],
        })

    sdk_factory(handler)
    llm = LLMClient(config(stream=stream))
    memory = Memory()
    memory.add_message(UserMessage(content="extract facts"))
    with pytest.raises(LLMResponseTruncatedError):
        llm.generate(memory)
    assert len(calls) == 1


def test_non_streaming_behavior_is_preserved(sdk_factory):
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(200, json={
            "id": "test", "object": "chat.completion", "created": 0, "model": "test-model",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "OK"}, "finish_reason": "stop"}],
        })

    sdk_factory(handler)
    memory = Memory()
    memory.add_message(UserMessage(content="test"))
    assert LLMClient(config(stream=False)).generate(memory) == "OK"
    assert not captured[0].get("stream")
    assert "stream_options" not in captured[0]
    assert "response_format" not in captured[0]


def test_multimodal_uses_the_same_streaming_receiver(sdk_factory, monkeypatch, tmp_path):
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return streaming_response([chunk({"role": "assistant", "content": '{"value":7}'}, "stop")])

    create, _ = sdk_factory(handler)
    backend = DefaultPlannerLLMBackend(config())
    monkeypatch.setattr(backend, "_build_openai_client", lambda: create(backend.config))
    image = tmp_path / "diagram.png"
    image.write_bytes(b"image")
    assert backend.complete(system_prompt="sys", user_prompt="extract", images=[str(image)]) == '{"value":7}'
    assert captured[0]["stream"] is True
    assert captured[0]["messages"][-1]["content"][1]["image_url"]["url"].startswith("data:image/png;base64,")


@pytest.mark.parametrize("quality_retry", [False, True])
def test_planner_does_not_repair_request_errors(quality_retry):
    calls = []
    sink_calls = []

    class Artifact(BaseModel):
        value: int

    class Agent(BaseStageAgent):
        stage_name = "test"
        system_role = "test"
        output_model = Artifact

        def build_prompt(self, *args):
            return "extract facts", []

        def validate_quality(self, *args):
            return ["quality retry required"]

    class Backend:
        def complete_with_memory(self, **kwargs):
            calls.append(kwargs)
            if quality_retry and len(calls) == 1:
                return '{"value":7}'
            raise LLMRequestError("transport retries exhausted")

    class Sink:
        def record_stage_output(self, *args):
            sink_calls.append(args)

    agent = Agent(PlannerLLMClient(backend=Backend()), artifact_sink=Sink())
    with pytest.raises(LLMRequestError):
        agent.run(object(), {})
    assert len(calls) == (2 if quality_retry else 1)
    assert not sink_calls
