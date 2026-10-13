"""Receive complete OpenAI-compatible responses with one transport retry loop."""

import time
from typing import Callable

import httpx
import openai
from openai.types.chat import ChatCompletion

from ..errors import IncompleteLLMResponseError, LLMRequestError, LLMResponseTruncatedError
from .retry_utils import retry_with


def _retryable_request_error(exc: Exception) -> bool:
    if isinstance(exc, (IncompleteLLMResponseError, openai.APIConnectionError, httpx.TransportError)):
        return True
    if isinstance(exc, openai.APIStatusError):
        return exc.status_code in {408, 409, 429} or exc.status_code >= 500
    if isinstance(exc, openai.APIError):
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            error = body.get("error", body)
            if isinstance(error, dict):
                return error.get("type") == "upstream_error" or error.get("code") == "upstream_error"
    return False


def request_with_retries(func: Callable, *, provider_name: str, max_retries: int):
    """Keep exhausted/fatal request failures out of higher-level repair loops."""
    try:
        return retry_with(func, provider_name, max_retries, retry_if=_retryable_request_error)()
    except LLMRequestError:
        raise
    except (openai.OpenAIError, httpx.TransportError) as exc:
        status = getattr(exc, "status_code", None)
        detail = f", HTTP {status}" if status is not None else ""
        raise LLMRequestError(f"{provider_name} request failed: {type(exc).__name__}{detail}") from exc


def create_chat_completion(
    client: openai.OpenAI,
    kwargs: dict,
    *,
    stream: bool,
    include_usage: bool = False,
    log: bool = True,
) -> ChatCompletion:
    """Consume and validate the whole response before returning any model output."""
    # The caller owns retries, including failures during stream consumption.
    client.max_retries = 0
    start = time.monotonic()
    if stream:
        stream_kwargs = dict(kwargs)
        if include_usage:
            stream_kwargs["stream_options"] = {"include_usage": True}
        chunks = 0
        content_chars = 0
        last_progress = start
        with client.chat.completions.stream(**stream_kwargs) as events:
            if log:
                print(f"[LLMClient] Stream connected in {time.monotonic() - start:.2f}s", flush=True)
            for event in events:
                if event.type != "chunk":
                    continue
                chunks += 1
                for choice in event.chunk.choices:
                    content_chars += len(choice.delta.content or "")
                now = time.monotonic()
                if log and (chunks == 1 or now - last_progress >= 30):
                    print(
                        f"[LLMClient] Stream progress: chunks={chunks}, "
                        f"content_chars={content_chars}, elapsed={now - start:.2f}s",
                        flush=True,
                    )
                    last_progress = now
            if not chunks:
                raise IncompleteLLMResponseError("The API stream ended without any completion chunks")
            try:
                response = events.get_final_completion()
            except openai.LengthFinishReasonError as exc:
                raise LLMResponseTruncatedError("Model output was truncated; increase max_tokens or reduce the task") from exc
    else:
        response = client.chat.completions.create(**kwargs)

    validate_completion(response)
    if log and stream:
        print(
            f"[LLMClient] Stream complete in {time.monotonic() - start:.2f}s "
            f"(finish_reason={response.choices[0].finish_reason})",
            flush=True,
        )
    return response


def validate_completion(response):
    if not response.choices or any(choice.finish_reason is None for choice in response.choices):
        raise IncompleteLLMResponseError("The API response ended without a finish_reason")
    for choice in response.choices:
        if choice.finish_reason == "length":
            raise LLMResponseTruncatedError("Model output was truncated; increase max_tokens or reduce the task")
        if choice.finish_reason == "content_filter" or choice.message.refusal:
            raise LLMRequestError("The model refused or filtered the request")
        if not choice.message.content and not choice.message.tool_calls:
            raise IncompleteLLMResponseError("The API returned neither content nor tool calls")
