"""Cancellable I/O with one deadline shared by connection, reads and retries."""
from __future__ import annotations

import asyncio
from concurrent.futures import Future
import random
import threading
import time

import httpx
import openai

from ..errors import IncompleteLLMResponseError, LLMRequestError, LLMRequestTimeoutError, LLMResponseTruncatedError
from ..request_policy import RequestProgress
from .completion_utils import _retryable_request_error, validate_completion


def error_details(exc, progress):
    details = {"error_type": type(exc).__name__,
               "http_status": getattr(exc, "status_code", None) or progress.diagnostics.get("http_status"),
               "server_request_id": getattr(exc, "request_id", None) or progress.diagnostics.get("server_request_id"),
               "waiting_phase": progress.phase}
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error", body)
        if isinstance(error, dict):
            # Do not log arbitrary messages, request bodies, headers or credentials.
            for key in ("type", "code"):
                value = error.get(key)
                if isinstance(value, (str, int)):
                    details["server_error_" + key] = str(value)[:100]
    return details


async def _consume(factory, kwargs, *, stream, include_usage, progress):
    kwargs = dict(kwargs)
    # The client default may still be 120 seconds. Per-call supervision owns
    # read/header deadlines; an SDK default must not preempt the larger budget.
    kwargs.setdefault("timeout", httpx.Timeout(progress.options.total_timeout_seconds,
                                              connect=min(15, progress.options.total_timeout_seconds)))
    async with factory() as client:
        if not stream:
            response = await client.chat.completions.create(**kwargs)
            progress.content(response.choices[0].message.content or "" if response.choices else "")
        else:
            stream_kwargs = dict(kwargs)
            if include_usage:
                stream_kwargs["stream_options"] = {"include_usage": True}
            async with client.chat.completions.stream(**stream_kwargs) as events:
                progress.phase = "first_content"
                http_response = getattr(events, "_response", None)
                if http_response is not None:
                    progress.diagnostics.update(http_status=http_response.status_code,
                        server_request_id=http_response.headers.get("x-request-id"))
                if progress.log:
                    print(f"[LLMClient] Stream connected in {time.monotonic() - progress.started:.2f}s", flush=True)
                async for event in events:
                    if event.type == "chunk":
                        progress.content("".join(c.delta.content or "" for c in event.chunk.choices))
                if not progress.chunks:
                    raise IncompleteLLMResponseError("The API stream ended without completion chunks")
                try:
                    response = await events.get_final_completion()
                except openai.LengthFinishReasonError as exc:
                    raise LLMResponseTruncatedError("Model output was truncated") from exc
        validate_completion(response)
        progress.diagnostics.update(finish_reason=response.choices[0].finish_reason,
                                    server_request_id=getattr(response, "_request_id", None) or progress.diagnostics.get("server_request_id"))
        return response


def _timeout_error(progress, reason):
    progress.diagnostics["timeout_reason"] = reason
    return LLMRequestTimeoutError(f"API request stopped: {reason}; phase={progress.phase}; "
        f"stage={progress.options.stage}; module={progress.options.module}",
        timeout_reason=reason, waiting_phase=progress.phase)


async def _supervise_io(coroutine, progress):
    task = asyncio.create_task(coroutine)
    try:
        while True:
            done, _ = await asyncio.wait({task}, timeout=progress.next_wakeup())
            if done:
                result = task.result()
                reason = progress.timeout()
                if reason:
                    raise _timeout_error(progress, reason)
                return result
            reason = progress.timeout()
            if reason:
                raise _timeout_error(progress, reason)
            if time.monotonic() >= progress.next_progress:
                progress.publish()
    finally:
        # Finish socket cancellation/connection closure before another attempt
        # starts. This also applies to caller interrupts and callback failures.
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def _attempts(factory, kwargs, *, stream, include_usage, progress):
    for attempt in range(progress.options.max_retries + 1):
        if time.monotonic() >= progress.deadline:
            raise _timeout_error(progress, "total_timeout")
        progress.begin_attempt()
        try:
            return await _supervise_io(_consume(factory, kwargs, stream=stream,
                include_usage=include_usage, progress=progress), progress)
        except openai.LengthFinishReasonError as exc:
            raise LLMResponseTruncatedError("Model output was truncated") from exc
        except (openai.OpenAIError, httpx.TransportError, LLMRequestError) as exc:
            progress.diagnostics.update(error_details(exc, progress))
            if isinstance(exc, LLMRequestTimeoutError):
                retryable = (progress.options.retry_first_content_timeout
                    and exc.diagnostics.get("timeout_reason") == "first_content_timeout"
                    and progress.first_content is None)
            else:
                retryable = _retryable_request_error(exc)
            if attempt >= progress.options.max_retries or not retryable:
                if isinstance(exc, LLMRequestError):
                    raise
                raise LLMRequestError("API request failed: " + str(progress.diagnostics), **progress.diagnostics) from exc
            progress.phase = "retry_delay"
            progress.publish("retrying")
            await _supervise_io(asyncio.sleep(random.uniform(3, 10)), progress)
    raise AssertionError("unreachable retry loop")


async def _supervised(factory, kwargs, *, stream, include_usage, options, log):
    progress = RequestProgress(options, log=log)
    try:
        result = await _attempts(factory, kwargs, stream=stream, include_usage=include_usage, progress=progress)
        progress.publish("completed")
        if log and stream:
            print(f"[LLMClient] Stream complete in {time.monotonic()-progress.started:.2f}s "
                  f"(finish_reason={result.choices[0].finish_reason})", flush=True)
        return result
    except BaseException as exc:
        if isinstance(exc, LLMRequestError):
            progress.diagnostics.update(exc.diagnostics)
        progress.publish("interrupted" if isinstance(exc, (asyncio.CancelledError, KeyboardInterrupt)) else "failed")
        raise


def create_bounded_chat_completion(factory, kwargs, *, stream, include_usage=False, options, log=True):
    """Keep the sync planner API while using cancellable asynchronous socket reads."""
    def coroutine():
        return _supervised(factory, kwargs, stream=stream, include_usage=include_usage, options=options, log=log)
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine())
    # A synchronous caller inside an existing event loop needs its own I/O loop.
    future = Future()
    state = {}
    def worker():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        task = loop.create_task(coroutine())
        state.update(loop=loop, task=task)
        try:
            future.set_result(loop.run_until_complete(task))
        except BaseException as exc:
            future.set_exception(exc)
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
    thread = threading.Thread(target=worker, daemon=True, name="bounded-llm-io")
    thread.start()
    try:
        return future.result()
    except BaseException:
        if "loop" in state and not state["loop"].is_closed():
            state["loop"].call_soon_threadsafe(state["task"].cancel)
        thread.join(timeout=2)
        raise
