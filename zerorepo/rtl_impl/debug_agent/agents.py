from __future__ import annotations

import json
import inspect
from typing import Any

from agentscope.agent import ReActAgent
from agentscope.tool import ToolResponse


class SafeReActAgent(ReActAgent):
    """ReActAgent with a more forgiving generate_response tool.

    Some models occasionally call `generate_response` with a non-string payload
    (e.g. a dict). The base implementation passes it through to `ToolResponse`,
    which then raises a validation error. This subclass coerces to a string so
    the agent can always terminate cleanly.
    """

    def generate_response(self, response: str, **kwargs: Any) -> ToolResponse:  # type: ignore[override]
        """Finish the conversation with a plain string response."""
        if not isinstance(response, str):
            try:
                response = json.dumps(response, ensure_ascii=False)
            except Exception:  # noqa: BLE001
                response = str(response)
        return super().generate_response(response=response, **kwargs)


def clear_memory_safely(agent: ReActAgent) -> None:
    """Clear AgentScope memory without 'coroutine was never awaited' warnings."""
    mem = getattr(agent, "memory", None)
    if mem is None:
        return
    clear = getattr(mem, "clear", None)
    if clear is None:
        return
    try:
        ret = clear()
    except TypeError:
        # Some memory implementations may require args; ignore.
        return

    # In AgentScope 1.0.7, InMemoryMemory.clear() is async; schedule it if needed.
    if hasattr(ret, "__await__"):
        try:
            loop = __import__("asyncio").get_running_loop()
            loop.create_task(ret)  # type: ignore[arg-type]
        except RuntimeError:
            # No running loop; run it to completion.
            __import__("asyncio").run(ret)  # type: ignore[arg-type]


async def close_model_safely(agent: ReActAgent) -> None:
    """Close short-lived AgentScope model clients before their event loop exits."""
    model = getattr(agent, "model", None)
    seen: set[int] = set()
    stack = [model]
    while stack:
        obj = stack.pop()
        if obj is None or id(obj) in seen:
            continue
        seen.add(id(obj))
        client = getattr(obj, "client", None)
        if client is not None:
            close = getattr(client, "close", None) or getattr(client, "aclose", None)
            if close is not None:
                try:
                    ret = close()
                    if inspect.isawaitable(ret):
                        await ret
                except Exception:  # noqa: BLE001
                    pass
        nested = getattr(obj, "_base_model", None)
        if nested is not None:
            stack.append(nested)
