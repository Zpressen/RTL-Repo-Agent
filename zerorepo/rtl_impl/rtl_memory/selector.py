from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import replace
from typing import Any

from agentscope.memory import InMemoryMemory
from agentscope.message import Msg

from .schemas import RTLMemoryHeader, SelectedMemory
from .store import RTLMemoryStore


def build_selector_prompt(context: dict[str, Any], headers: list[RTLMemoryHeader], *, limit: int = 5) -> str:
    candidates = [
        {
            "path": header.path,
            "description": header.description or header.memory_id or header.path,
        }
        for header in headers
    ]
    return (
        "Select the most relevant RTL causal memory files for the current task.\n"
        "You are given only a filename/path plus a short description for each memory file.\n"
        "Choose memories whose descriptions are semantically useful for the current RTL repair context.\n"
        "Return only JSON with shape {\"selected\": [\"relative/path.md\"]}.\n"
        f"Select at most {max(1, int(limit))} files. Do not invent paths.\n\n"
        "<current_context_json>\n"
        f"{json.dumps(context, indent=2, ensure_ascii=False)}\n"
        "</current_context_json>\n\n"
        "<memory_file_candidates_json>\n"
        f"{json.dumps(candidates, indent=2, ensure_ascii=False)}\n"
        "</memory_file_candidates_json>\n"
    )


class RTLMemorySelector:
    def __init__(
        self,
        store: RTLMemoryStore,
        *,
        model_cfg: Any | None = None,
        logger: Any | None = None,
    ) -> None:
        self.store = store
        self.model_cfg = model_cfg
        self.logger = logger

    def select(
        self,
        context: dict[str, Any],
        *,
        memory_type: str | None = None,
        stage: str | None = None,
        limit: int = 5,
    ) -> list[SelectedMemory]:
        headers = self.store.scan_headers(memory_type=memory_type, stage=stage)
        if not headers:
            return []
        selected_paths = self._select_paths_with_llm(context, headers, limit=limit)
        if not selected_paths:
            selected_paths = [header.path for header in self._fallback_rank(context, headers, limit=limit)]
        selected: list[SelectedMemory] = []
        seen: set[str] = set()
        allowed = {header.path for header in headers}
        for path in selected_paths:
            if path in seen or path not in allowed:
                continue
            record = self.store.read_memory(path)
            if record is None:
                continue
            selected.append(SelectedMemory(path=path, header=record.header, content=record.body))
            seen.add(path)
            if len(selected) >= max(1, int(limit)):
                break
        return selected

    def _select_paths_with_llm(
        self,
        context: dict[str, Any],
        headers: list[RTLMemoryHeader],
        *,
        limit: int,
    ) -> list[str]:
        cfg = self.model_cfg
        if cfg is None or not getattr(cfg, "api_key", ""):
            return []
        try:
            from zerorepo.rtl_impl.debug_agent.agents import SafeReActAgent, clear_memory_safely, close_model_safely
            from zerorepo.rtl_impl.debug_agent.model import make_formatter, make_openai_model
        except Exception:  # noqa: BLE001
            return []

        model_name = os.environ.get("ZEROREPO_RTL_MEMORY_SELECTOR_MODEL", "").strip()
        if model_name:
            try:
                cfg = replace(cfg, model=model_name)
            except Exception:  # noqa: BLE001
                pass
        prompt = build_selector_prompt(context, headers, limit=limit)
        agent = SafeReActAgent(
            name="RTLMemorySelector",
            sys_prompt="You select relevant RTL causal memory files. Return JSON only.",
            model=make_openai_model(cfg),
            formatter=make_formatter(getattr(cfg, "model", None), getattr(cfg, "base_url", None)),
            memory=InMemoryMemory(),
            max_iters=2,
        )
        async def run_agent_once() -> Msg:
            try:
                return await agent(Msg("user", prompt, role="user"))
            finally:
                await close_model_safely(agent)

        try:
            text = self._run_async(run_agent_once()).get_text_content() or ""
        except Exception as exc:  # noqa: BLE001
            if self.logger is not None:
                self.logger.debug("RTL memory selector LLM failed, using fallback: %s", exc)
            return []
        finally:
            try:
                clear_memory_safely(agent)
            except Exception:  # noqa: BLE001
                pass
        return self._parse_selected_paths(text, allowed={header.path for header in headers}, limit=limit)

    def _run_async(self, coroutine: Any) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)
        import threading

        result: dict[str, Any] = {}

        def runner() -> None:
            try:
                result["value"] = asyncio.run(coroutine)
            except BaseException as exc:  # noqa: BLE001
                result["error"] = exc

        thread = threading.Thread(target=runner)
        thread.start()
        thread.join()
        if "error" in result:
            raise result["error"]
        return result["value"]

    def _parse_selected_paths(self, text: str, *, allowed: set[str], limit: int) -> list[str]:
        try:
            start = text.find("{")
            end = text.rfind("}")
            payload = json.loads(text[start : end + 1] if start >= 0 and end >= start else text)
        except Exception:  # noqa: BLE001
            return []
        selected = payload.get("selected") if isinstance(payload, dict) else None
        if not isinstance(selected, list):
            return []
        out: list[str] = []
        for item in selected:
            path = str(item)
            if path in allowed and path not in out:
                out.append(path)
            if len(out) >= max(1, int(limit)):
                break
        return out

    def _fallback_rank(
        self,
        context: dict[str, Any],
        headers: list[RTLMemoryHeader],
        *,
        limit: int,
    ) -> list[RTLMemoryHeader]:
        ctx_stage = str(context.get("stage") or "")
        ctx_module = str(context.get("module") or "")
        ctx_family = str(context.get("module_family") or "")
        ctx_failure = str(context.get("failure_type") or "")
        ctx_alignment = str(context.get("alignment") or "")
        ctx_signals = {str(s) for s in (context.get("signals") or context.get("related_signals") or []) if s}
        ctx_text = json.dumps(context, ensure_ascii=False).lower()
        first = context.get("first_fail_signal")
        if first:
            ctx_signals.add(str(first))

        def score(header: RTLMemoryHeader) -> tuple[float, float, str]:
            value = float(header.confidence or 0.0)
            if ctx_stage and header.stage == ctx_stage:
                value += 4
            if ctx_module and header.module == ctx_module:
                value += 5
            if ctx_family and header.module_family == ctx_family:
                value += 3
            if ctx_failure and header.failure_type == ctx_failure:
                value += 2
            if ctx_failure and header.trigger_failure_type == ctx_failure:
                value += 2
            if ctx_alignment and header.alignment == ctx_alignment:
                value += 2
            if ctx_alignment and header.trigger_alignment == ctx_alignment:
                value += 2
            overlap = ctx_signals & (set(header.signals) | set(header.trigger_signals))
            value += 2 * len(overlap)
            risk_overlap = ctx_signals & set(header.risk_signals)
            value += 0.5 * len(risk_overlap)
            anti = str(header.anti_trigger or "").lower()
            if anti and any(token and token in ctx_text for token in re.split(r"[^a-zA-Z0-9_.$-]+", anti)[:12]):
                value -= 1
            return (value, float(header.confidence or 0.0), header.path)

        ranked = sorted(headers, key=score, reverse=True)
        return ranked[: max(1, int(limit))]


__all__ = ["RTLMemorySelector", "build_selector_prompt"]
