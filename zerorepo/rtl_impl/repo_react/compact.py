from __future__ import annotations

import inspect
import json
import os
import re
from pathlib import Path
from typing import Any, Awaitable, Callable, Literal

from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.tool import Toolkit

from zerorepo.rtl_impl.debug_agent.agents import SafeReActAgent, clear_memory_safely, close_model_safely
from zerorepo.rtl_impl.debug_agent.config import OpenAIConfig
from zerorepo.rtl_impl.debug_agent.model import make_formatter, make_openai_model

CompactMode = Literal["checkpoint", "deep"]
CompactLLMGenerate = Callable[[str], str | Awaitable[str]]


COMPACT_SYSTEM_PROMPT = """
You compact repository-level RTL repair progress.

Return only strict JSON. Preserve evidence-backed decision state, not hidden chain-of-thought.
Every inference must be grounded in supplied trace, patch, memory, or context-pack facts.
The compact memory is advisory and must not override current RTL, trace, simulation, or specs.
""".strip()


def _clip(value: Any, max_chars: int = 900) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...<snip>..."


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    return obj if isinstance(obj, dict) else {}


def _read_jsonl_tail(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            obj = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows[-max(1, int(limit)) :]


def _slim_context_pack(pack: dict[str, Any], *, mode: CompactMode) -> dict[str, Any]:
    task = pack.get("task_frame") if isinstance(pack.get("task_frame"), dict) else {}
    triage = pack.get("system_triage") if isinstance(pack.get("system_triage"), dict) else {}
    timing = pack.get("timing_evidence") if isinstance(pack.get("timing_evidence"), dict) else {}
    working = pack.get("active_working_set") if isinstance(pack.get("active_working_set"), dict) else {}
    causal = pack.get("causal_memory") if isinstance(pack.get("causal_memory"), dict) else {}
    evidence = pack.get("evidence_pack") if isinstance(pack.get("evidence_pack"), list) else []
    evidence_limit = 0 if mode == "deep" else 3
    return {
        "pack_path": pack.get("pack_path") or "",
        "task_frame": {
            "current_target": task.get("current_target") or {},
            "top_diagnosis": _clip(task.get("top_diagnosis") or "", 900),
            "next_action_hint": task.get("next_action_hint") or "",
        },
        "system_triage": {
            "category": triage.get("category"),
            "root_signal": triage.get("root_signal"),
            "suspect_files": (triage.get("suspect_files") or [])[:5],
            "reason": _clip(triage.get("reason") or "", 900),
            "recommended_tool_calls": (triage.get("recommended_tool_calls") or [])[:5],
        },
        "timing_evidence": timing,
        "active_working_set": {
            "current_failure": working.get("current_failure") or {},
            "active_hypotheses": (working.get("active_hypotheses") or [])[:4],
            "rejected_hypotheses": (working.get("rejected_hypotheses") or [])[:4],
            "next_edit_candidates": (working.get("next_edit_candidates") or [])[:4],
            "missing_evidence": (working.get("missing_evidence") or [])[:5],
        },
        "causal_memory": {
            "repair_ledger_summary": (causal.get("repair_ledger_summary") or [])[:6],
            "promising_directions": (causal.get("promising_directions") or [])[:5],
            "protected_invariants": (causal.get("protected_invariants") or [])[:8],
            "unsafe_directions": (causal.get("unsafe_directions") or [])[:8],
        },
        "evidence_pack": evidence[:evidence_limit],
    }


def _slim_signal_trace(trace: dict[str, Any]) -> dict[str, Any]:
    candidates = trace.get("driver_candidates") if isinstance(trace.get("driver_candidates"), list) else []
    return {
        "status": trace.get("status"),
        "module": trace.get("module"),
        "signal": trace.get("signal"),
        "time": trace.get("time"),
        "observed_value": trace.get("observed_value"),
        "expected_value": trace.get("expected_value"),
        "focus_context": trace.get("focus_context") or {},
        "editable_rtl_blocks": (trace.get("editable_rtl_blocks") or [])[:8],
        "driver_candidates": [
            {
                "driver_block_id": item.get("driver_block_id"),
                "classification": item.get("classification"),
                "reason": _clip(item.get("reason") or "", 500),
                "assignment": {
                    key: (item.get("assignment") or {}).get(key)
                    for key in (
                        "id",
                        "block_id",
                        "lhs",
                        "rhs_signals",
                        "condition_signals",
                        "condition_expressions",
                        "start_line",
                        "end_line",
                    )
                },
            }
            for item in candidates[:8]
            if isinstance(item, dict)
        ],
        "next_frontier": (trace.get("next_frontier") or [])[:12],
        "boundary_mappings": (trace.get("boundary_mappings") or [])[:6],
        "recommended_next_calls": (trace.get("recommended_next_calls") or [])[:4],
        "recommended_next_call": trace.get("recommended_next_call") or {},
        "frontier_truncated": bool(trace.get("frontier_truncated")),
        "stop_reason": trace.get("stop_reason"),
    }


def _slim_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "module": snapshot.get("module"),
        "current_rtl_hash": snapshot.get("current_rtl_hash"),
        "last_sim": snapshot.get("last_sim"),
        "action_calls": snapshot.get("action_calls"),
        "patch_attempts": snapshot.get("patch_attempts"),
        "pending_syntax_candidates": snapshot.get("pending_syntax_candidates") or [],
        "max_steps": snapshot.get("max_steps"),
        "latest_trace_summary": {
            "fail_time": (snapshot.get("latest_trace_summary") or {}).get("fail_time"),
            "root_failure": (snapshot.get("latest_trace_summary") or {}).get("root_failure"),
            "top_diagnosis": (snapshot.get("latest_trace_summary") or {}).get("top_diagnosis"),
            "suspect_blocks": (snapshot.get("latest_trace_summary") or {}).get("suspect_blocks"),
        },
        "last_divergence_summary": snapshot.get("last_divergence_summary") or {},
        "last_signal_trace": _slim_signal_trace(snapshot.get("last_signal_trace") or {}),
        "pending_post_patch_trace": snapshot.get("pending_post_patch_trace") or {},
        "repair_ledger": snapshot.get("repair_ledger") or [],
        "protected_invariants": snapshot.get("protected_invariants") or [],
        "unsafe_directions": snapshot.get("unsafe_directions") or [],
        "next_local_target": snapshot.get("next_local_target") or {},
    }


def build_deterministic_compact_memory(
    *,
    journal_root: str | Path,
    mode: CompactMode,
    memory_snapshot: dict[str, Any],
    context_pack: dict[str, Any],
) -> dict[str, Any]:
    """Build a non-empty recovery snapshot without relying on an LLM."""
    root = Path(journal_root)
    snapshot = _slim_snapshot(memory_snapshot)
    pack = _slim_context_pack(context_pack or {}, mode=mode)
    decisions = _read_jsonl_tail(root / "decision_trace.jsonl", 8)
    patches = _read_jsonl_tail(root / "patch_journal.jsonl", 5)
    pending = snapshot.get("pending_post_patch_trace") or {}
    last_trace = snapshot.get("last_signal_trace") or {}

    reasoning_trace = [
        {
            "tool": row.get("tool_name"),
            "observation": row.get("observation_summary") or {},
            "effect": row.get("effect"),
        }
        for row in decisions[-6:]
    ]
    patch_lessons = [
        {
            "action": row.get("action_type"),
            "target": row.get("target") or {},
            "reason": _clip(row.get("reason") or row.get("patch_summary") or "", 600),
            "effect": row.get("effect") or row.get("status"),
        }
        for row in patches[-4:]
    ]
    if pending:
        next_action = {
            "recommendation": "trace_signal_cause",
            "arguments": pending,
            "why": "The latest committed functional patch was neutral; a matching one-hop retrace is required.",
        }
    else:
        triage = pack.get("system_triage") or {}
        recommended = triage.get("recommended_tool_calls") or []
        next_action = {
            "recommendation": recommended[0] if recommended else "continue_local_causal_debug",
            "arguments": {},
            "why": (
                (pack.get("task_frame") or {}).get("next_action_hint")
                or "Continue from the latest persisted trace, simulation, and patch evidence."
            ),
        }

    last_patch = patches[-1] if patches else {}
    compact = {
        "schema": "repo_react_llm_compact.v1",
        "current_state": {
            "module": snapshot.get("module"),
            "current_rtl_hash": snapshot.get("current_rtl_hash"),
            "last_sim": snapshot.get("last_sim") or {},
            "first_divergence": snapshot.get("last_divergence_summary") or {},
            "last_signal_trace": last_trace,
            "pending_post_patch_trace": pending,
            "action_calls": snapshot.get("action_calls"),
            "patch_attempts": snapshot.get("patch_attempts"),
            "repair_ledger": snapshot.get("repair_ledger") or [],
            "protected_invariants": snapshot.get("protected_invariants") or [],
        },
        "reasoning_trace": reasoning_trace,
        "hypotheses": (pack.get("active_working_set") or {}).get("active_hypotheses") or [],
        "patch_lessons": patch_lessons,
        "open_questions": (
            [{"question": "Re-evaluate the root signal on the committed neutral baseline.", "required_call": pending}]
            if pending
            else (pack.get("active_working_set") or {}).get("missing_evidence") or []
        ),
        "next_action": next_action,
        "do_not_repeat": snapshot.get("unsafe_directions") or [],
        "metadata": {
            "mode": mode,
            "source": "deterministic_fallback",
            "last_patch_effect": last_patch.get("effect") or last_patch.get("status"),
            "source_decision_trace_count": len(decisions),
            "source_patch_journal_count": len(patches),
        },
    }
    return compact


def _compact_prompt(payload: dict[str, Any]) -> str:
    return (
        "Build a compact recovery memory for the next RepoReAct turn.\n"
        "Return JSON with exactly these top-level keys:\n"
        "schema, current_state, reasoning_trace, hypotheses, patch_lessons, "
        "open_questions, next_action, do_not_repeat.\n"
        "- schema must be repo_react_llm_compact.v1\n"
        "- reasoning_trace should be short evidence-backed observation/inference/decision entries\n"
        "- next_action must include recommendation and why\n\n"
        "<compact_input_json>\n"
        f"{json.dumps(payload, indent=2, ensure_ascii=False, default=str)}\n"
        "</compact_input_json>"
    )


def parse_llm_compact_json(text: str) -> dict[str, Any] | None:
    try:
        obj = json.loads(text)
    except Exception:  # noqa: BLE001
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            return None
        try:
            obj = json.loads(match.group(0))
        except Exception:  # noqa: BLE001
            return None
    if not isinstance(obj, dict):
        return None
    if obj.get("schema") != "repo_react_llm_compact.v1":
        return None
    required = {
        "current_state",
        "reasoning_trace",
        "hypotheses",
        "patch_lessons",
        "open_questions",
        "next_action",
        "do_not_repeat",
    }
    if any(key not in obj for key in required):
        return None
    return obj


async def _run_compact_agent(cfg: OpenAIConfig, prompt: str) -> str:
    agent = SafeReActAgent(
        name="RepoReActCompactor",
        sys_prompt=COMPACT_SYSTEM_PROMPT,
        model=make_openai_model(cfg),
        formatter=make_formatter(cfg.model, cfg.base_url),
        toolkit=Toolkit(),
        memory=InMemoryMemory(),
        max_iters=2,
    )
    try:
        msg = await agent(Msg("user", prompt, role="user"))
        return (msg.get_text_content() or "").strip()
    finally:
        clear_memory_safely(agent)
        await close_model_safely(agent)


async def build_llm_compact_memory(
    *,
    cfg: OpenAIConfig | None,
    journal_root: str | Path,
    mode: CompactMode,
    memory_snapshot: dict[str, Any],
    context_pack: dict[str, Any],
    logger: Any | None = None,
    llm_generate: CompactLLMGenerate | None = None,
) -> dict[str, Any] | None:
    """Return LLM compact memory, or None so the caller keeps deterministic compact."""
    if os.environ.get("ZEROREPO_REACT_LLM_COMPACT", "1").lower() in {"0", "false", "no", "off"}:
        return None
    if llm_generate is None and (cfg is None or not getattr(cfg, "api_key", "")):
        return None

    root = Path(journal_root)
    input_payload = {
        "mode": mode,
        "memory_snapshot": _slim_snapshot(memory_snapshot),
        "context_pack": _slim_context_pack(context_pack or {}, mode=mode),
        "decision_trace_tail": _read_jsonl_tail(root / "decision_trace.jsonl", 24 if mode == "checkpoint" else 16),
        "patch_journal_tail": _read_jsonl_tail(root / "patch_journal.jsonl", 8 if mode == "checkpoint" else 5),
        "previous_llm_compact": _read_json(root / "repo_react_llm_compact.json"),
    }
    prompt = _compact_prompt(input_payload)

    try:
        if llm_generate is not None:
            generated = llm_generate(prompt)
            if inspect.isawaitable(generated):
                text = await generated
            else:
                text = generated
        else:
            text = await _run_compact_agent(cfg, prompt)  # type: ignore[arg-type]
    except Exception as exc:  # noqa: BLE001
        if logger is not None:
            logger.debug("RepoReAct LLM compact failed: %s", exc)
        return None

    compact = parse_llm_compact_json(str(text))
    if compact is None:
        if logger is not None:
            logger.debug("RepoReAct LLM compact returned invalid JSON.")
        return None
    compact.setdefault("metadata", {})
    if isinstance(compact["metadata"], dict):
        compact["metadata"].update(
            {
                "mode": mode,
                "source_decision_trace_count": len(input_payload["decision_trace_tail"]),
                "source_patch_journal_count": len(input_payload["patch_journal_tail"]),
            }
        )
    return compact
