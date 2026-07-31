from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Literal

from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.tool import ToolResponse, Toolkit

from zerorepo.rtl_impl.debug_agent.agents import (
    SafeReActAgent,
    clear_memory_safely,
    clear_memory_safely_async,
)
from zerorepo.rtl_impl.debug_agent.config import OpenAIConfig
from zerorepo.rtl_impl.debug_agent.model import make_formatter, make_openai_model
from zerorepo.rtl_impl.debug_agent.sim_reviewer import SimReviewer
from zerorepo.rtl_impl.debug_agent.trace_report import build_trace_report

from .compact import build_deterministic_compact_memory, build_llm_compact_memory
from .context import DebugContextRouter
from .journal import RepoReActJournal
from .prompt import (
    SYSTEM_PROMPT,
    build_compact_prompt,
    build_continue_prompt,
    build_initial_prompt,
    build_tool_call_recovery_prompt,
)
from .schemas import DebugContextGoal, Diagnosis, RepoReActInput, RepoReActResult, SimSnapshot
from .tools import RepoReActToolState, RepoReActTools, _extract_first_fail_time, _summarize_command_json
from .tools import stage_artifact_help_text

CompactDecision = Literal["none", "light", "checkpoint", "deep"]

LIGHT_READONLY_CALLS = 8
LIGHT_TOOL_CHARS = 24_000
CHECKPOINT_WRITES = 3
CHECKPOINT_TOOL_CHARS = 48_000
CHECKPOINT_LIGHTS = 1
CHECKPOINT_AFTER_LIGHT_CHARS = 32_000
DEEP_CHECKPOINTS = 2
DEEP_TOOL_CHARS = 160_000
DEEP_REMAINING_BUDGET_RATIO = 0.2

READONLY_TRACE_INTENT_FIELDS: dict[str, Any] = {
    "purpose": {"type": "string", "description": "Optional reason for this observation; used only for decision trace."},
    "question": {"type": "string", "description": "Optional question this observation should answer; used only for decision trace."},
    "expected_evidence": {"type": "string", "description": "Optional expected evidence; used only for decision trace."},
}


def _tool_schema(name: str, description: str, properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
            },
        },
    }


def _extract_diagnosis(text: str) -> Diagnosis | None:
    if not text:
        return None
    candidates: list[str] = []
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    candidates.extend(fenced)
    brace = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if brace:
        candidates.append(brace.group(0))
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
        except Exception:  # noqa: BLE001
            continue
        diag_obj = obj.get("diagnosis") if isinstance(obj, dict) and "diagnosis" in obj else obj
        if isinstance(diag_obj, dict):
            try:
                return Diagnosis.model_validate(diag_obj)
            except Exception:  # noqa: BLE001
                continue
    return None


class RepoReActRunner:
    READONLY_TOOLS = {
        "read_context",
        "search_context",
        "query_rtl_kg",
        "read_module_semantics",
        "trace_signal_cause",
        "read_long_term_memory",
        "list_vcd_signals",
        "probe_vcd",
        "run_check",
    }
    ACTION_TOOLS = {"apply_patch", "replace_block", "record_correction"}
    READ_BUDGET_RESET_TOOLS = {"apply_patch", "replace_block"}
    ROUTER_FIRST_TOOLS: set[str] = set()

    def __init__(
        self,
        cfg: OpenAIConfig,
        *,
        sim_reviewer: SimReviewer,
        kg_service: Any | None = None,
        max_steps: int = 30,
        logger: Any | None = None,
    ) -> None:
        self.cfg = cfg
        self.sim_reviewer = sim_reviewer
        self.kg_service = kg_service
        self.max_steps = int(max_steps)
        self.logger = logger
        self._state: RepoReActToolState | None = None
        self._tools: RepoReActTools | None = None
        self._context_router: DebugContextRouter | None = None
        self._latest_context_pack: dict[str, Any] = {}
        self._last_compacted_action_calls = 0
        self._last_checkpoint_action_calls = 0
        self._tool_result_chars_since_compact = 0
        self._tool_result_chars_since_light = 0
        self._readonly_calls_since_action = 0
        self._readonly_calls_since_light = 0
        self._route_calls_since_action = 0
        self._route_allowed_reads: list[dict[str, Any]] = []
        self._route_read_count = 0
        self._required_initial_trace_call: dict[str, Any] = {}
        self._initial_trace_completed = False
        self._initial_dut_instance = ""
        self._light_consolidations_since_checkpoint = 0
        self._checkpoint_count = 0
        self._pending_tool_call_recovery: dict[str, Any] = {}
        self._tool_call_recovery_signatures: set[str] = set()
        self._readonly_budget_from_env = "ZEROREPO_REACT_READONLY_BUDGET" in os.environ
        self._max_readonly_calls_since_action = int(os.environ.get("ZEROREPO_REACT_READONLY_BUDGET", "16"))
        self._router_first_enabled = os.environ.get("ZEROREPO_REACT_ROUTER_FIRST", "0").lower() not in {"0", "false", "no"}

        toolkit = Toolkit()
        toolkit.register_tool_function(
            self.read_context,
            json_schema=_tool_schema(
                "read_context",
                "Read repository trees, files, line ranges, testbenches, stage artifacts, trace reports, or journals.",
                {
                    "kind": {
                        "type": "string",
                        "enum": [
                            "repo_tree",
                            "file",
                            "lines",
                            "testbench",
                            "stage_artifact",
                            "trace_report",
                            "repair_journal",
                        ],
                    },
                    "path": {"type": ["string", "null"]},
                    "start": {"type": ["integer", "null"]},
                    "end": {"type": ["integer", "null"]},
                    "artifact_name": {
                        "type": ["string", "null"],
                        "description": (
                            "Only used with kind='stage_artifact'. Valid names: "
                            f"{stage_artifact_help_text()}. Do not pass module names here."
                        ),
                    },
                    "max_chars": {"type": "integer"},
                    **READONLY_TRACE_INTENT_FIELDS,
                },
                ["kind"],
            ),
        )
        toolkit.register_tool_function(
            self.search_context,
            json_schema=_tool_schema(
                "search_context",
                "Search RTL, testbench, spec, or all context with a regex pattern.",
                {
                    "pattern": {"type": "string"},
                    "scope": {"type": "string", "enum": ["rtl", "tb", "spec", "all"]},
                    "file_glob": {"type": "string"},
                    "max_results": {"type": "integer"},
                    "context_lines": {"type": "integer"},
                    **READONLY_TRACE_INTENT_FIELDS,
                },
                ["pattern"],
            ),
        )
        toolkit.register_tool_function(
            self.query_rtl_kg,
            json_schema=_tool_schema(
                "query_rtl_kg",
                "Run a fixed-template structural RTL KG query for interfaces, instances, or connections.",
                {
                    "query_type": {
                        "type": "string",
                        "enum": [
                            "module_interface",
                            "module_instances",
                            "instance_connections",
                        ],
                    },
                    "module_name": {"type": "string"},
                    "signal_name": {"type": ["string", "null"]},
                    "instance_name": {"type": ["string", "null"]},
                    **READONLY_TRACE_INTENT_FIELDS,
                },
                ["query_type", "module_name"],
            ),
        )
        toolkit.register_tool_function(
            self.read_module_semantics,
            json_schema=_tool_schema(
                "read_module_semantics",
                "Read a Module-centred Spec/Skeleton/Plan view. Prefer this over separate planning-artifact reads; related module semantics are never loaded automatically.",
                {
                    "module_name": {"type": "string"},
                    "sections": {
                        "type": ["array", "null"],
                        "items": {"type": "string", "enum": ["spec", "skeleton", "plan"]},
                    },
                    "focus_signals": {"type": ["array", "null"], "items": {"type": "string"}},
                    "focus_blocks": {
                        "type": ["array", "null"],
                        "items": {"type": "string"},
                        "description": (
                            "Optional filter terms. Returned Skeleton ids are planning_block_id; "
                            "editable parser ids are rtl_block_id and the namespaces are never interchangeable."
                        ),
                    },
                    "max_chars": {"type": "integer"},
                    **READONLY_TRACE_INTENT_FIELDS,
                },
                ["module_name"],
            ),
        )
        toolkit.register_tool_function(
            self.trace_signal_cause,
            json_schema=_tool_schema(
                "trace_signal_cause",
                (
                    "Trace one signal through direct drivers in one module, sample its VCD evidence, "
                    "and expose Instance/Port boundary candidates without recursive traversal. "
                    "When a frontier is traceable, recommended_next_call is the preferred exact next one-hop trace."
                ),
                {
                    "module_name": {"type": "string"},
                    "signal_name": {"type": "string"},
                    "time": {"type": ["integer", "null"]},
                    "expected_value": {"type": ["string", "null"]},
                    "max_candidates": {"type": "integer"},
                    **READONLY_TRACE_INTENT_FIELDS,
                },
                ["module_name", "signal_name"],
            ),
        )
        # Legacy read_spec/retrieve_spec_block implementations remain available
        # internally, but are intentionally not exposed to the LLM. Module-centred
        # planning semantics must flow through read_module_semantics.
        toolkit.register_tool_function(
            self.read_long_term_memory,
            json_schema=_tool_schema(
                "read_long_term_memory",
                "Read a selected RTL long-term memory markdown file under workspace rtl_memory. Use this when selected_long_term_memories has a relevant path and the body excerpt is insufficient.",
                {
                    "path": {"type": "string"},
                    "max_chars": {"type": "integer"},
                    **READONLY_TRACE_INTENT_FIELDS,
                },
                ["path"],
            ),
        )
        toolkit.register_tool_function(
            self.list_vcd_signals,
            json_schema=_tool_schema(
                "list_vcd_signals",
                "List VCD signal names matching an optional pattern and scope.",
                {
                    "pattern": {"type": "string"},
                    "scope": {"type": "string"},
                    "limit": {"type": "integer"},
                    **READONLY_TRACE_INTENT_FIELDS,
                },
                [],
            ),
        )
        toolkit.register_tool_function(
            self.probe_vcd,
            json_schema=_tool_schema(
                "probe_vcd",
                "Sample VCD signals at a time or over a time window with optional edge filtering.",
                {
                    "signals": {"type": "array", "items": {"type": "string"}},
                    "time": {"type": ["integer", "null"]},
                    "time_range": {"type": ["array", "null"], "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                    "edge": {"type": ["string", "null"]},
                    "mode": {"type": "string", "enum": ["sample", "changes"]},
                    "max_rows": {"type": "integer"},
                    **READONLY_TRACE_INTENT_FIELDS,
                },
                ["signals"],
            ),
        )
        toolkit.register_tool_function(
            self.run_check,
            json_schema=_tool_schema(
                "run_check",
                "Run lint, module simulation, trace summary, or v1 placeholder checks.",
                {
                    "mode": {"type": "string", "enum": ["lint", "module_sim", "top_sim", "trace_summary", "first_divergence", "wave_window"]},
                    "module_name": {"type": ["string", "null"]},
                    "signals": {"type": ["array", "null"], "items": {"type": "string"}},
                    "time_window": {"type": ["array", "null"], "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                    **READONLY_TRACE_INTENT_FIELDS,
                },
                ["mode"],
            ),
        )
        # read_memory disabled: context_pack injected into every prompt already provides
        # the same session-state summary (task_frame, timing_evidence, causal_memory).
        # Raw read_memory calls returned ~45 KB of redundant JSON and accelerated the
        # compact checkpoint without adding decision-relevant information.
        # toolkit.register_tool_function(
        #     self.read_memory,
        #     json_schema=_tool_schema(
        #         "read_memory",
        #         "Read RepoReAct repair memory, failed directions, promising directions, or full snapshot. Use route_debug_context first for summarized memory selection.",
        #         {
        #             "kind": {
        #                 "type": "string",
        #                 "enum": [
        #                     "snapshot",
        #                     "brief",
        #                     "repair_journal",
        #                     "repair_ledger",
        #                     "protected_invariants",
        #                     "unsafe_directions",
        #                     "failed_directions",
        #                     "promising_directions",
        #                     "next_target",
        #                     "raw_snapshot",
        #                 ],
        #             },
        #             "limit": {"type": "integer"},
        #         },
        #         [],
        #     ),
        # )
        # DebugContextRouter remains an internal context service; exposing it as a
        # meta-tool would duplicate the direct read/debug tools above.
        toolkit.register_tool_function(
            self.apply_patch,
            json_schema={
                "type": "function",
                "function": {
                    "name": "apply_patch",
                    "description": "Apply one coherent RTL line-range patch whose scope matches the evidence and plausible causal patch rationale, then lint/sim/trace verify and rollback on regression.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "patches": {
                                "type": "array",
                                "minItems": 1,
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "path": {"type": "string"},
                                        "start_line": {"type": "integer"},
                                        "end_line": {"type": "integer"},
                                        "new_text": {"type": "string"},
                                    },
                                    "required": ["path", "start_line", "end_line", "new_text"],
                                },
                            },
                            "reason": {"type": "string"},
                            "expected_effect": {"type": "string"},
                            "protected_invariants_checked": {"type": ["array", "null"], "items": {"type": "string"}},
                            "preserve_plan": {"type": ["string", "null"]},
                            "syntax_retry_of": {
                                "type": ["string", "null"],
                                "description": "Candidate id returned by a prior syntax_retry_required result.",
                            },
                            "verify": {"type": "boolean"},
                            "rollback_on_fail": {"type": "boolean"},
                        },
                        "required": ["patches", "reason", "expected_effect"],
                    },
                },
            },
        )
        toolkit.register_tool_function(
            self.replace_block,
            json_schema={
                "type": "function",
                "function": {
                    "name": "replace_block",
                    "description": (
                        "Replace one complete RTL parser always/assign block in the specified module. "
                        "Use only module_name and rtl_block_id returned by "
                        "trace_signal_cause.editable_rtl_blocks or "
                        "read_module_semantics.editable_rtl_blocks. Never pass a B1/B2/B5 planning_block_id."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "module_name": {
                                "type": "string",
                                "description": "Logical module containing the current RTL parser block.",
                            },
                            "rtl_block_id": {
                                "type": "string",
                                "description": "Current RTL parser id such as A2, A3, or C101; never a planning block id.",
                            },
                            "new_code": {"type": "string"},
                            "reason": {"type": "string"},
                            "expected_effect": {"type": "string"},
                            "protected_invariants_checked": {"type": ["array", "null"], "items": {"type": "string"}},
                            "preserve_plan": {"type": ["string", "null"]},
                            "syntax_retry_of": {
                                "type": ["string", "null"],
                                "description": "Candidate id returned by a prior syntax_retry_required result.",
                            },
                            "verify": {"type": "boolean"},
                            "rollback_on_fail": {"type": "boolean"},
                        },
                        "required": [
                            "module_name",
                            "rtl_block_id",
                            "new_code",
                            "reason",
                            "expected_effect",
                        ],
                    },
                },
            },
        )
        toolkit.register_tool_function(
            self.record_correction,
            json_schema=_tool_schema(
                "record_correction",
                "Record a planning correction overlay without editing original stage artifacts.",
                {
                    "correction_type": {
                        "type": "string",
                        "enum": [
                            "wrong_contract",
                            "wrong_module_plan",
                            "wrong_interface",
                            "wrong_timing",
                            "wrong_dependency",
                            "wrong_retrieval",
                        ],
                    },
                    "module_name": {"type": "string"},
                    "original_artifact": {"type": "string"},
                    "problem": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "override": {"type": "object"},
                },
                ["correction_type", "module_name", "original_artifact", "problem", "evidence", "override"],
            ),
        )

        self._agent = SafeReActAgent(
            name="RepoReActDebugger",
            sys_prompt=SYSTEM_PROMPT,
            model=make_openai_model(cfg),
            formatter=make_formatter(cfg.model, cfg.base_url),
            toolkit=toolkit,
            memory=InMemoryMemory(),
            max_iters=20,
        )

    def reset(self) -> None:
        clear_memory_safely(self._agent)
        self._state = None
        self._tools = None
        self._context_router = None
        self._latest_context_pack = {}
        self._last_compacted_action_calls = 0
        self._last_checkpoint_action_calls = 0
        self._tool_result_chars_since_compact = 0
        self._tool_result_chars_since_light = 0
        self._readonly_calls_since_action = 0
        self._readonly_calls_since_light = 0
        self._route_calls_since_action = 0
        self._route_allowed_reads = []
        self._route_read_count = 0
        self._required_initial_trace_call = {}
        self._initial_trace_completed = False
        self._initial_dut_instance = ""
        self._light_consolidations_since_checkpoint = 0
        self._checkpoint_count = 0
        self._pending_tool_call_recovery = {}
        self._tool_call_recovery_signatures = set()

    def _configure_scope_defaults(self, inp: RepoReActInput) -> None:
        if inp.repair_scope == "repo" and not self._readonly_budget_from_env:
            self._max_readonly_calls_since_action = max(self._max_readonly_calls_since_action, 16)

    def _clip_trace_value(self, value: Any, max_chars: int = 900) -> Any:
        if isinstance(value, str):
            return value if len(value) <= max_chars else value[:max_chars] + "\n...<snip>..."
        if isinstance(value, list):
            return [self._clip_trace_value(item, max_chars=max_chars) for item in value[:8]]
        if isinstance(value, dict):
            return {
                str(key): self._clip_trace_value(item, max_chars=max_chars)
                for key, item in list(value.items())[:12]
                if key not in {"content", "new_text"}
            }
        return value

    @staticmethod
    def _detect_textual_tool_call(text: str) -> dict[str, str] | None:
        """Recognize DSML/XML pseudo-calls without parsing or executing arguments."""
        if not text:
            return None
        marker = re.search(
            r"(?is)(?:<\s*(?:tool_call|invoke|function_call)\b|"
            r"DSML.{0,32}?(?:tool[_\s-]*calls?|function[_\s-]*calls?|invoke)|"
            r"<\|(?:tool_call|function_call)\|>)",
            text,
        )
        if marker is None:
            return None
        tail = text[max(0, marker.start() - 80) : marker.start() + 800]
        name_match = re.search(
            r"""(?is)(?:name\s*=\s*["']|["']name["']\s*:\s*["']|"""
            r"""(?:tool|function)\s*[:=]\s*["']?)([A-Za-z_][A-Za-z0-9_]*)""",
            tail,
        )
        if name_match is None:
            known = re.search(r"\b(apply_patch|replace_block|trace_signal_cause|read_module_semantics)\b", tail)
            tool_name = known.group(1) if known else ""
        else:
            tool_name = name_match.group(1)
        normalized = re.sub(r"\s+", " ", tail).strip()[:500]
        return {
            "tool_name": tool_name,
            "signature": f"{tool_name}:{normalized}",
            "excerpt": tail[:800],
        }

    def _record_unexecuted_tool_call(self, text: str) -> None:
        detected = self._detect_textual_tool_call(text)
        if detected is None or self._state is None:
            return
        signature = detected["signature"]
        retry_eligible = signature not in self._tool_call_recovery_signatures
        self._state.journal.append_jsonl(
            "react_trace.jsonl",
            {
                "role": "system",
                "event": "unexecuted_tool_call",
                "tool_name": detected["tool_name"],
                "retry_eligible": retry_eligible,
                "content_excerpt": detected["excerpt"],
                "action_calls": int(self._state.action_calls),
            },
        )
        self._state.journal.append_jsonl(
            "decision_trace.jsonl",
            {
                "schema": "repo_react_decision_trace.v1",
                "step": int(self._state.action_calls),
                "action_calls": int(self._state.action_calls),
                "patch_attempts": int(self._state.patch_attempt_id),
                "tool_name": detected["tool_name"] or "unknown_textual_tool_call",
                "tool_kind": "unexecuted_tool_call",
                "observation_summary": {
                    "status": "unexecuted_tool_call",
                    "message": "Assistant emitted textual tool markup; no tool was executed.",
                },
                "effect": "not_executed",
                "evidence_refs": [{"kind": "journal", "path": "react_trace.jsonl"}],
            },
        )
        if retry_eligible:
            self._tool_call_recovery_signatures.add(signature)
            self._pending_tool_call_recovery = detected

    def _tool_kind(self, name: str) -> str:
        if name in self.ACTION_TOOLS:
            return "action"
        if name == "route_debug_context":
            return "route"
        return "read"

    def _counts_as_successful_tool_call(self, name: str, payload: dict[str, Any]) -> bool:
        status = str(payload.get("status", "ok") or "ok")
        if name in self.ACTION_TOOLS:
            if payload.get("is_action_executed") is False:
                return False
            return status not in {
                "error",
                "rejected",
                "observation_budget_exhausted",
                "router_first_required",
                "route_read_restricted",
                "post_patch_trace_required",
            }
        return status in {"ok", "static_only", "stable_values_match_but_tb_edge_mismatch", "no_divergence"}

    def _trace_intent(self, purpose: str = "", question: str = "", expected_evidence: str = "") -> dict[str, str]:
        return {
            key: value
            for key, value in {
                "purpose": purpose,
                "question": question,
                "expected_evidence": expected_evidence,
            }.items()
            if value
        }

    def _observation_summary(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "status": payload.get("status"),
        }
        for key in (
            "kind",
            "mode",
            "path",
            "module_name",
            "tool_name",
            "reason",
            "rollback_reason",
            "effect",
            "is_pass",
            "mismatch_count",
            "first_fail_time",
            "pack_path",
            "context_pack_path",
        ):
            if key in payload:
                summary[key] = self._clip_trace_value(payload.get(key), max_chars=500)
        if "content" in payload:
            text = str(payload.get("content") or "")
            summary["content_excerpt"] = self._clip_trace_value(text, max_chars=700)
            summary["content_chars"] = len(text)
        if "results" in payload and isinstance(payload.get("results"), list):
            summary["result_count"] = len(payload["results"])
            summary["results_excerpt"] = self._clip_trace_value(payload["results"][:3], max_chars=500)
        if "rows" in payload and isinstance(payload.get("rows"), list):
            summary["row_count"] = len(payload["rows"])
            summary["rows_excerpt"] = self._clip_trace_value(payload["rows"][:3], max_chars=500)
        if "lint_output_excerpt" in payload:
            summary["lint_output_excerpt"] = self._clip_trace_value(payload.get("lint_output_excerpt"), max_chars=700)
        if not any(value not in (None, "", [], {}) for value in summary.values()):
            summary["payload_excerpt"] = self._clip_trace_value(payload, max_chars=700)
        summary["tool"] = name
        return summary

    def _decision_evidence_refs(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = [{"kind": "journal", "path": "react_trace.jsonl"}]
        for key in ("path", "pack_path", "context_pack_path", "trace_report_path", "sim_output_path"):
            value = payload.get(key)
            if value:
                refs.append({"kind": key, "path": str(value)})
        target = payload.get("target") if isinstance(payload.get("target"), dict) else {}
        if target.get("path"):
            refs.append({"kind": "target", "path": str(target.get("path"))})
        if payload.get("step") is not None:
            refs.append({"kind": "patch_step", "step": payload.get("step")})
        if self._latest_context_pack and self._latest_context_pack.get("pack_path"):
            refs.append({"kind": "context_pack", "path": str(self._latest_context_pack.get("pack_path"))})
        return refs[:6]

    def _write_decision_trace(self, name: str, payload: dict[str, Any], trace_meta: dict[str, Any] | None = None) -> None:
        if self._state is None:
            return
        trace_meta = trace_meta or {}
        intent = trace_meta.get("intent") if isinstance(trace_meta.get("intent"), dict) else {}
        args = trace_meta.get("args") if isinstance(trace_meta.get("args"), dict) else {}
        row = {
            "schema": "repo_react_decision_trace.v1",
            "step": int(self._state.action_calls),
            "action_calls": int(self._state.action_calls),
            "patch_attempts": int(self._state.patch_attempt_id),
            "tool_name": name,
            "tool_kind": self._tool_kind(name),
            "intent": intent,
            "tool_args": self._clip_trace_value(args, max_chars=500),
            "observation_summary": self._observation_summary(name, payload),
            "effect": payload.get("effect") or payload.get("status"),
            "readonly_calls_since_action": int(self._readonly_calls_since_action),
            "evidence_refs": self._decision_evidence_refs(payload),
        }
        self._state.journal.append_jsonl("decision_trace.jsonl", row)

    def _tool_response(self, name: str, payload: dict[str, Any], trace_meta: dict[str, Any] | None = None) -> ToolResponse:
        if self._state is not None:
            self._state.journal.append_jsonl(
                "react_trace.jsonl",
                {"role": "tool", "tool_name": name, "tool_result": payload},
            )
            self._write_decision_trace(name, payload, trace_meta=trace_meta)
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        self._tool_result_chars_since_compact += len(text)
        self._tool_result_chars_since_light += len(text)
        counts_for_budget = self._counts_as_successful_tool_call(name, payload)
        if name in self.READ_BUDGET_RESET_TOOLS and counts_for_budget:
            self._readonly_calls_since_action = 0
            self._route_calls_since_action = 0
            self._route_allowed_reads = []
            self._route_read_count = 0
        elif name == "route_debug_context" and counts_for_budget:
            self._route_calls_since_action += 1
            self._readonly_calls_since_action += 1
            self._readonly_calls_since_light += 1
        elif name in self.READONLY_TOOLS and counts_for_budget:
            self._readonly_calls_since_action += 1
            self._readonly_calls_since_light += 1
        return ToolResponse(content=[{"type": "text", "text": text}])

    def _require_tools(self) -> RepoReActTools:
        if self._tools is None:
            raise RuntimeError("RepoReActRunner has no active tool state.")
        return self._tools

    def _require_context_router(self) -> DebugContextRouter:
        if self._context_router is None:
            raise RuntimeError("RepoReActRunner has no active context router.")
        return self._context_router

    def _readonly_budget_exceeded_response(self, tool_name: str) -> ToolResponse | None:
        if self._readonly_calls_since_action < self._max_readonly_calls_since_action:
            return None
        payload: dict[str, Any] = {
            "status": "observation_budget_exhausted",
            "tool_name": tool_name,
            "readonly_calls_since_action": self._readonly_calls_since_action,
            "max_readonly_calls_since_action": self._max_readonly_calls_since_action,
            "required_next_action": ["apply_patch", "replace_block"],
            "message": (
                "Observation budget exhausted. Stop reading more context unless you first take a verified RTL edit "
                "with apply_patch/replace_block. record_correction and generate_response do not reset the observation "
                "budget; generate_response should only be used to stop."
            ),
        }
        if self._tools is not None:
            try:
                snapshot = self._tools.memory_snapshot()
                payload["memory_summary"] = self._memory_summary(snapshot)
            except Exception:  # noqa: BLE001
                pass
        return self._tool_response(tool_name, payload)

    def _router_first_required_response(self, tool_name: str) -> ToolResponse | None:
        del tool_name
        return None

    def _initial_trace_gate_response(self, tool_name: str) -> ToolResponse | None:
        required = getattr(self, "_required_initial_trace_call", {})
        if (
            not isinstance(required, dict)
            or not required
            or bool(getattr(self, "_initial_trace_completed", False))
            or tool_name not in {"read_context", "probe_vcd"}
        ):
            return None
        payload = {
            "status": "initial_trace_required",
            "tool_name": tool_name,
            "required_next_tool": "trace_signal_cause",
            "arguments": required,
            "message": (
                "Complete the recommended one-hop trace_signal_cause call for the initial first-divergence "
                "signal before using read_context or probe_vcd. These detailed reads are unlocked after a "
                "successful matching trace."
            ),
        }
        return self._tool_response(tool_name, payload)

    def _matches_required_initial_trace(self, args: dict[str, Any]) -> bool:
        required = getattr(self, "_required_initial_trace_call", {})
        if not isinstance(required, dict) or not required:
            return False
        for key in ("module_name", "signal_name", "time", "expected_value"):
            expected = required.get(key)
            actual = args.get(key)
            if key == "time":
                try:
                    if int(actual) != int(expected):
                        return False
                except (TypeError, ValueError):
                    return False
            elif str(actual) != str(expected):
                return False
        return True

    def _post_patch_trace_required_response(self, tool_name: str) -> ToolResponse | None:
        if self._state is None or self._state.input.repair_mode != "functional":
            return None
        required = self._state.pending_post_patch_trace
        if not required:
            return None
        return self._tool_response(
            tool_name,
            {
                "status": "post_patch_trace_required",
                "tool_name": tool_name,
                "required_next_tool": "trace_signal_cause",
                "arguments": required,
                "message": (
                    "The previous functional patch was neutral. Re-run the matching one-hop signal trace "
                    "on the committed baseline before making another RTL modification."
                ),
            },
        )

    def _current_root_trace_requirement(self) -> dict[str, Any]:
        if self._state is None:
            return {}
        divergence = self._state.last_divergence_summary or {}
        first = divergence.get("first_divergence") if isinstance(divergence.get("first_divergence"), dict) else {}
        if isinstance(first.get("first_divergence"), dict):
            first = first["first_divergence"]
        signal = first.get("signal")
        time = first.get("time")
        expected = first.get("ref") if first.get("ref") is not None else first.get("expected")
        module_name = (
            (self._state.last_trace_summary or {}).get("runtime_top_module")
            or (self._state.last_signal_trace or {}).get("module")
            or self._state.input.top_module
            or self._state.input.module_name
        )
        if signal not in (None, "") and time is not None:
            return {
                "module_name": str(module_name),
                "signal_name": str(signal),
                "time": int(time),
                "expected_value": None if expected is None else str(expected),
            }
        last_signal = self._state.last_signal_trace or {}
        if last_signal.get("signal") and last_signal.get("time") is not None:
            return {
                "module_name": str(last_signal.get("module") or module_name),
                "signal_name": str(last_signal["signal"]),
                "time": int(last_signal["time"]),
                "expected_value": (
                    None
                    if last_signal.get("expected_value") is None
                    else str(last_signal.get("expected_value"))
                ),
            }
        return {}

    def _attach_post_patch_trace_requirement(self, result: dict[str, Any]) -> dict[str, Any]:
        if (
            self._state is None
            or self._state.input.repair_mode != "functional"
            or str(result.get("status") or "") != "neutral"
            or result.get("committed") is False
        ):
            return result
        required = self._current_root_trace_requirement()
        if not required:
            return result
        self._state.pending_post_patch_trace = required
        result = dict(result)
        result["required_next_tool"] = "trace_signal_cause"
        result["arguments"] = required
        return result

    def _matches_pending_post_patch_trace(self, args: dict[str, Any]) -> bool:
        if self._state is None or not self._state.pending_post_patch_trace:
            return False
        required = self._state.pending_post_patch_trace
        for key in ("module_name", "signal_name", "time", "expected_value"):
            expected = required.get(key)
            actual = args.get(key)
            if key == "time":
                try:
                    if int(actual) != int(expected):
                        return False
                except (TypeError, ValueError):
                    return False
            elif str(actual) != str(expected):
                return False
        return True

    def _compact_route_debug_context_result(self, pack: dict[str, Any]) -> dict[str, Any]:
        """Return only the conclusion and minimal evidence index for the main agent.

        The full DebugContextPack is still persisted to pack_path and kept in
        ``self._latest_context_pack``.  This tool-facing shape intentionally
        avoids returning full evidence bodies that the main agent will reread.
        """
        task_frame = pack.get("task_frame") if isinstance(pack.get("task_frame"), dict) else {}
        system_triage = pack.get("system_triage") if isinstance(pack.get("system_triage"), dict) else {}
        timing = pack.get("timing_evidence") if isinstance(pack.get("timing_evidence"), dict) else {}
        evidence = pack.get("evidence_pack") if isinstance(pack.get("evidence_pack"), list) else []
        recommended = system_triage.get("recommended_tool_calls") if isinstance(system_triage, dict) else []
        if not isinstance(recommended, list):
            recommended = []

        def clipped_list(value: Any, *, limit: int, max_chars: int) -> list[Any]:
            if not isinstance(value, list):
                return []
            return [self._clip_trace_value(item, max_chars=max_chars) for item in value[:limit]]

        slim_triage = {
            "category": system_triage.get("category"),
            "confidence": system_triage.get("confidence"),
            "symptom": self._clip_trace_value(system_triage.get("symptom"), max_chars=400),
            "root_signal": system_triage.get("root_signal"),
            "root_time": system_triage.get("root_time"),
            "suspect_modules": system_triage.get("suspect_modules") or [],
            "patch_scope": self._clip_trace_value(system_triage.get("patch_scope"), max_chars=400),
            "reason": self._clip_trace_value(system_triage.get("reason"), max_chars=400),
            "signal_path": clipped_list(system_triage.get("signal_path"), limit=3, max_chars=250),
            "evidence": clipped_list(system_triage.get("evidence"), limit=4, max_chars=250),
            "missing_evidence": clipped_list(system_triage.get("missing_evidence"), limit=3, max_chars=250),
            "recommended_tool_calls": recommended[:4],
        }

        refs: list[dict[str, Any]] = []
        for item in evidence[:6]:
            if not isinstance(item, dict):
                continue
            artifact = item.get("artifact_ref") if isinstance(item.get("artifact_ref"), dict) else {}
            refs.append(
                {
                    "id": item.get("evidence_id") or artifact.get("artifact_id") or "",
                    "kind": item.get("kind") or artifact.get("kind") or "",
                    "path": artifact.get("path") or "",
                    "summary": self._clip_trace_value(item.get("summary") or "", max_chars=250),
                    "salient": item.get("salient") if isinstance(item.get("salient"), dict) else {},
                }
            )

        analysis = str(task_frame.get("router_analysis") or "")
        return {
            "schema_version": "route_debug_context_summary_v1",
            "status": "ok",
            "pack_path": pack.get("pack_path") or "",
            "system_triage": slim_triage,
            "timing_evidence": timing,
            "router_analysis": analysis[:400],
            "evidence_refs": refs[:4],
            "recommended_tool_calls": recommended[:4],
            "raw_read_policy": {
                "max_followup_reads": 4,
                "allowed_calls": recommended[:4],
                "message": "Use only these recommended_tool_calls for raw follow-up evidence before patching.",
            },
        }

    def _set_route_allowed_reads(self, summary: dict[str, Any]) -> None:
        recommended = summary.get("recommended_tool_calls")
        self._route_allowed_reads = recommended[:6] if isinstance(recommended, list) else []
        self._route_read_count = 0

    def _route_read_restricted_response(self, tool_name: str, args: dict[str, Any]) -> ToolResponse | None:
        del tool_name, args
        return None

    def _matches_recommended_read(self, tool_name: str, args: dict[str, Any], item: dict[str, Any]) -> bool:
        if str(item.get("tool") or "") != tool_name:
            return False
        expected = item.get("args") if isinstance(item.get("args"), dict) else {}
        for key, value in expected.items():
            if value in (None, "", [], {}):
                continue
            if str(args.get(key)) != str(value):
                return False
        return True

    def _record_route_read_if_recommended(self, tool_name: str, args: dict[str, Any]) -> None:
        allowed = getattr(self, "_route_allowed_reads", [])
        if any(self._matches_recommended_read(tool_name, args, item) for item in allowed if isinstance(item, dict)):
            self._route_read_count = int(getattr(self, "_route_read_count", 0)) + 1

    def _memory_summary(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        if isinstance(snapshot.get("causal_memory_brief"), dict):
            return snapshot["causal_memory_brief"]
        if self._tools is not None:
            return self._tools._causal_memory_brief(snapshot)
        return {
            "schema": "repo_react_memory_brief.v1",
            "module": snapshot.get("module"),
            "current_rtl_hash": snapshot.get("current_rtl_hash"),
            "last_sim": snapshot.get("last_sim"),
            "repair_ledger": snapshot.get("repair_ledger") or [],
            "protected_invariants": snapshot.get("protected_invariants") or [],
            "unsafe_directions": snapshot.get("unsafe_directions") or [],
            "next_local_target": snapshot.get("next_local_target") or {},
            "high_coupling_blocks": snapshot.get("high_coupling_blocks") or [],
            "action_calls": snapshot.get("action_calls"),
            "patch_attempts": snapshot.get("patch_attempts"),
            "pending_syntax_candidates": snapshot.get("pending_syntax_candidates") or [],
            "max_steps": snapshot.get("max_steps"),
        }

    @staticmethod
    def _resolve_max_agent_turns(inp: RepoReActInput, max_steps: int) -> int:
        if inp.max_agent_turns is not None:
            return max(1, int(inp.max_agent_turns))
        return max(1, int(max_steps) * 3)

    def _has_real_divergence_for_checkpoint(self) -> bool:
        if self._state is None:
            return False
        if self._state.input.repair_mode != "functional":
            return True
        return bool(self._state.observed_real_divergence)

    def _remaining_budget_ratio(self) -> float:
        if self._state is None:
            return 1.0
        max_steps = max(1, int(self._state.input.max_steps or self.max_steps))
        remaining = max(0, max_steps - int(self._state.action_calls))
        return remaining / max_steps

    def _compact_decision(self) -> CompactDecision:
        if self._state is None:
            return "none"
        action_calls = int(self._state.action_calls)
        writes_since_checkpoint = action_calls - int(self._last_checkpoint_action_calls)
        if action_calls > 0:
            # ── Checkpoint first: preserve more evidence at moderate cost ──
            if self._has_real_divergence_for_checkpoint() and (
                writes_since_checkpoint >= CHECKPOINT_WRITES
                or int(self._tool_result_chars_since_compact) >= CHECKPOINT_TOOL_CHARS
                or (
                    int(self._light_consolidations_since_checkpoint) >= CHECKPOINT_LIGHTS
                    and int(self._tool_result_chars_since_compact) >= CHECKPOINT_AFTER_LIGHT_CHARS
                )
            ):
                return "checkpoint"
            # ── Deep: last-resort aggressive cut, only when truly desperate ──
            if (
                int(self._checkpoint_count) >= DEEP_CHECKPOINTS
                or self._remaining_budget_ratio() <= DEEP_REMAINING_BUDGET_RATIO
                or int(self._tool_result_chars_since_compact) >= DEEP_TOOL_CHARS
            ):
                return "deep"
        if (
            self._route_calls_since_action > 0
            or self._readonly_calls_since_light >= LIGHT_READONLY_CALLS
            or self._tool_result_chars_since_light >= LIGHT_TOOL_CHARS
            or (action_calls > 0 and action_calls > int(self._last_compacted_action_calls))
        ):
            return "light"
        return "none"

    def _needs_compact_checkpoint(self) -> bool:
        return self._compact_decision() in {"checkpoint", "deep"}

    async def _light_consolidate_context(self) -> dict[str, Any]:
        if self._tools is None or self._state is None:
            return {}
        self._tool_result_chars_since_light = 0
        self._readonly_calls_since_light = 0
        self._light_consolidations_since_checkpoint += 1
        self._last_compacted_action_calls = int(self._state.action_calls)
        self._route_calls_since_action = 0
        self._state.journal.append_jsonl(
                "react_trace.jsonl",
                {
                    "role": "system",
                    "compact": "light",
                    "context_pack_path": (self._latest_context_pack or {}).get("pack_path") or "",
                    "action_calls": int(self._state.action_calls),
                },
            )
        return self._latest_context_pack or {}

    async def _compact_agent_memory(self, mode: Literal["checkpoint", "deep"] = "checkpoint") -> bool:
        if self._tools is None or self._state is None:
            return False
        context_pack = self._latest_context_pack or {}
        snapshot = self._tools.persist_memory_snapshot()
        llm_compact = await build_llm_compact_memory(
            cfg=self.cfg,
            journal_root=self._state.journal.root,
            mode=mode,
            memory_snapshot=snapshot,
            context_pack=context_pack,
            logger=self.logger,
        )
        if not llm_compact:
            llm_compact = build_deterministic_compact_memory(
                journal_root=self._state.journal.root,
                mode=mode,
                memory_snapshot=snapshot,
                context_pack=context_pack,
            )
        self._state.journal.write_json("repo_react_llm_compact.json", llm_compact)
        self._state.journal.write_json("repo_react_recovery_memory.json", llm_compact)
        prompt = build_compact_prompt(context_pack, mode=mode, llm_compact_memory=llm_compact)
        await clear_memory_safely_async(self._agent)
        self._last_compacted_action_calls = int(self._state.action_calls)
        self._last_checkpoint_action_calls = int(self._state.action_calls)
        self._tool_result_chars_since_compact = 0
        self._tool_result_chars_since_light = 0
        self._readonly_calls_since_action = 0
        self._readonly_calls_since_light = 0
        self._route_calls_since_action = 0
        self._light_consolidations_since_checkpoint = 0
        self._checkpoint_count += 1
        self._state.journal.append_jsonl(
            "react_trace.jsonl",
            {"role": "user", "content": prompt, "compact": mode},
        )
        msg = await self._agent(Msg("user", prompt, role="user"))
        text = msg.get_text_content() or ""
        if text:
            self._state.journal.append_jsonl(
                "react_trace.jsonl",
                {"role": "assistant", "content": text, "compact": mode},
            )
            self._record_unexecuted_tool_call(text)
        return True

    def _route_context_pack(
        self,
        goal: DebugContextGoal,
        focus_signals: list[str] | None = None,
        focus_blocks: list[str] | None = None,
        missing_evidence: list[str] | None = None,
        max_items: int = 5,
        allow_investigator: bool = True,
    ) -> dict[str, Any]:
        pack = self._require_context_router().route(
            goal=goal,
            focus_signals=focus_signals,
            focus_blocks=focus_blocks,
            missing_evidence=missing_evidence,
            max_items=max_items,
            allow_investigator=allow_investigator,
        )
        self._latest_context_pack = pack
        if self._state is not None:
            try:
                self._state.input.context_pack_path = str(pack.get("pack_path") or "")
                self._state.input.context_pack_json = pack
            except Exception:  # noqa: BLE001
                pass
        return pack

    async def read_context(
        self,
        kind: Literal[
            "repo_tree",
            "file",
            "lines",
            "spec",
            "testbench",
            "stage_artifact",
            "trace_report",
            "repair_journal",
        ],
        path: str | None = None,
        start: int | None = None,
        end: int | None = None,
        artifact_name: str | None = None,
        max_chars: int = 12000,
        purpose: str = "",
        question: str = "",
        expected_evidence: str = "",
    ) -> ToolResponse:
        """Read repository tree, files, line ranges, specs, testbench, stage artifacts, trace reports, or journals."""
        blocked = self._readonly_budget_exceeded_response("read_context")
        if blocked is not None:
            return blocked
        initial_trace_required = self._initial_trace_gate_response("read_context")
        if initial_trace_required is not None:
            return initial_trace_required
        router_required = self._router_first_required_response("read_context")
        if router_required is not None:
            return router_required
        route_restricted = self._route_read_restricted_response(
            "read_context",
            {"kind": kind, "path": path, "start": start, "end": end, "artifact_name": artifact_name},
        )
        if route_restricted is not None:
            return route_restricted
        result = await asyncio.to_thread(
            self._require_tools().read_context,
            kind,
            path,
            start,
            end,
            artifact_name,
            max_chars,
        )
        self._record_route_read_if_recommended("read_context", {"kind": kind, "path": path, "start": start, "end": end, "artifact_name": artifact_name})
        return self._tool_response(
            "read_context",
            result,
            trace_meta={
                "intent": self._trace_intent(purpose, question, expected_evidence),
                "args": {"kind": kind, "path": path, "start": start, "end": end, "artifact_name": artifact_name},
            },
        )

    async def search_context(
        self,
        pattern: str,
        scope: Literal["rtl", "tb", "spec", "all"] = "all",
        file_glob: str = "**/*",
        max_results: int = 50,
        context_lines: int = 2,
        purpose: str = "",
        question: str = "",
        expected_evidence: str = "",
    ) -> ToolResponse:
        """Search RTL, testbench, spec, or all context with a regex pattern."""
        blocked = self._readonly_budget_exceeded_response("search_context")
        if blocked is not None:
            return blocked
        router_required = self._router_first_required_response("search_context")
        if router_required is not None:
            return router_required
        route_restricted = self._route_read_restricted_response("search_context", {"pattern": pattern, "scope": scope, "max_results": max_results})
        if route_restricted is not None:
            return route_restricted
        result = await asyncio.to_thread(
            self._require_tools().search_context,
            pattern,
            scope,
            file_glob,
            max_results,
            context_lines,
        )
        self._record_route_read_if_recommended("search_context", {"pattern": pattern, "scope": scope, "max_results": max_results})
        return self._tool_response(
            "search_context",
            result,
            trace_meta={
                "intent": self._trace_intent(purpose, question, expected_evidence),
                "args": {"pattern": pattern, "scope": scope, "file_glob": file_glob, "max_results": max_results},
            },
        )

    async def query_rtl_kg(
        self,
        query_type: Literal[
            "module_interface",
            "module_instances",
            "instance_connections",
            "signal_drivers",
        ],
        module_name: str,
        signal_name: str | None = None,
        instance_name: str | None = None,
        purpose: str = "",
        question: str = "",
        expected_evidence: str = "",
    ) -> ToolResponse:
        """Run a fixed-template RTL KG query for interface, instances, connections, or signal drivers."""
        blocked = self._readonly_budget_exceeded_response("query_rtl_kg")
        if blocked is not None:
            return blocked
        router_required = self._router_first_required_response("query_rtl_kg")
        if router_required is not None:
            return router_required
        route_restricted = self._route_read_restricted_response(
            "query_rtl_kg",
            {"query_type": query_type, "module_name": module_name, "signal_name": signal_name, "instance_name": instance_name},
        )
        if route_restricted is not None:
            return route_restricted
        result = await asyncio.to_thread(
            self._require_tools().query_rtl_kg,
            query_type,
            module_name,
            signal_name,
            instance_name,
        )
        self._record_route_read_if_recommended(
            "query_rtl_kg",
            {"query_type": query_type, "module_name": module_name, "signal_name": signal_name, "instance_name": instance_name},
        )
        return self._tool_response(
            "query_rtl_kg",
            result,
            trace_meta={
                "intent": self._trace_intent(purpose, question, expected_evidence),
                "args": {"query_type": query_type, "module_name": module_name, "signal_name": signal_name, "instance_name": instance_name},
            },
        )

    async def read_module_semantics(
        self,
        module_name: str,
        sections: list[str] | None = None,
        focus_signals: list[str] | None = None,
        focus_blocks: list[str] | None = None,
        max_chars: int = 12000,
        purpose: str = "",
        question: str = "",
        expected_evidence: str = "",
    ) -> ToolResponse:
        """Read the current Module-centred planning semantics."""
        blocked = self._readonly_budget_exceeded_response("read_module_semantics")
        if blocked is not None:
            return blocked
        router_required = self._router_first_required_response("read_module_semantics")
        if router_required is not None:
            return router_required
        last_trace = self._state.last_signal_trace if self._state is not None else {}
        trace_focus = last_trace.get("focus_context") if isinstance(last_trace.get("focus_context"), dict) else {}
        same_module = str(last_trace.get("module") or "") == str(module_name)
        focus_sources: dict[str, str] = {}
        if focus_signals is None and same_module:
            focus_signals = list(trace_focus.get("signals") or [])
            if focus_signals:
                focus_sources["signals"] = "last_signal_trace"
        elif focus_signals is not None:
            focus_sources["signals"] = "explicit"
        if focus_blocks is None and same_module:
            focus_blocks = list(
                trace_focus.get("rtl_block_ids")
                or trace_focus.get("rtl_blocks")
                or []
            )
            if focus_blocks:
                focus_sources["block_terms"] = "last_signal_trace"
        elif focus_blocks is not None:
            focus_sources["block_terms"] = "explicit"
        args = {
            "module_name": module_name,
            "sections": sections,
            "focus_signals": focus_signals,
            "focus_blocks": focus_blocks,
        }
        route_restricted = self._route_read_restricted_response("read_module_semantics", args)
        if route_restricted is not None:
            return route_restricted
        result = await asyncio.to_thread(
            self._require_tools().read_module_semantics,
            module_name,
            sections,
            focus_signals,
            focus_blocks,
            max_chars,
        )
        result = dict(result)
        core_focus = (
            result.get("focus_applied")
            if isinstance(result.get("focus_applied"), dict)
            else {}
        )
        rtl_block_ids = list(core_focus.get("rtl_block_ids") or [])
        planning_block_ids = list(core_focus.get("planning_block_ids") or [])
        block_source = focus_sources.pop("block_terms", None)
        if block_source and rtl_block_ids:
            focus_sources["rtl_block_ids"] = block_source
        if block_source and planning_block_ids:
            focus_sources["planning_block_ids"] = block_source
        result["focus_applied"] = {
            "signals": list(focus_signals or []),
            "rtl_block_ids": rtl_block_ids,
            "planning_block_ids": planning_block_ids,
            "sources": focus_sources,
        }
        self._record_route_read_if_recommended("read_module_semantics", args)
        return self._tool_response(
            "read_module_semantics",
            result,
            trace_meta={
                "intent": self._trace_intent(purpose, question, expected_evidence),
                "args": args,
            },
        )

    async def trace_signal_cause(
        self,
        module_name: str,
        signal_name: str,
        time: int | None = None,
        expected_value: str | None = None,
        max_candidates: int = 5,
        purpose: str = "",
        question: str = "",
        expected_evidence: str = "",
    ) -> ToolResponse:
        """Trace one module-local signal cause and its Instance/Port boundaries."""
        blocked = self._readonly_budget_exceeded_response("trace_signal_cause")
        if blocked is not None:
            return blocked
        router_required = self._router_first_required_response("trace_signal_cause")
        if router_required is not None:
            return router_required
        args = {
            "module_name": module_name,
            "signal_name": signal_name,
            "time": time,
            "expected_value": expected_value,
            "max_candidates": max_candidates,
        }
        route_restricted = self._route_read_restricted_response("trace_signal_cause", args)
        if route_restricted is not None:
            return route_restricted
        result = await asyncio.to_thread(
            self._require_tools().trace_signal_cause,
            module_name,
            signal_name,
            time,
            expected_value,
            max_candidates,
        )
        matched_initial_trace = self._matches_required_initial_trace(args)
        matched_post_patch_trace = self._matches_pending_post_patch_trace(args)
        if matched_initial_trace and str(result.get("status") or "") in {"ok", "static_only"}:
            self._initial_trace_completed = True
            result = dict(result)
            result["initial_trace_gate"] = {
                "status": "completed",
                "unlocked_tools": ["read_context", "probe_vcd"],
            }
        elif getattr(self, "_required_initial_trace_call", {}) and not getattr(self, "_initial_trace_completed", False):
            result = dict(result)
            result["initial_trace_gate"] = {
                "status": "pending",
                "required_next_tool": "trace_signal_cause",
                "arguments": self._required_initial_trace_call,
                "message": "This trace did not match and successfully complete the initial required trace.",
            }
        if matched_post_patch_trace and str(result.get("status") or "") in {"ok", "static_only"}:
            if self._state is not None:
                self._state.pending_post_patch_trace = {}
            result = dict(result)
            result["post_patch_trace_gate"] = {
                "status": "completed",
                "unlocked_tools": ["apply_patch", "replace_block"],
            }
        elif (
            self._state is not None
            and self._state.pending_post_patch_trace
        ):
            result = dict(result)
            result["post_patch_trace_gate"] = {
                "status": "pending",
                "required_next_tool": "trace_signal_cause",
                "arguments": self._state.pending_post_patch_trace,
            }
        self._record_route_read_if_recommended("trace_signal_cause", args)
        return self._tool_response(
            "trace_signal_cause",
            result,
            trace_meta={
                "intent": self._trace_intent(purpose, question, expected_evidence),
                "args": args,
            },
        )

    async def read_spec(
        self,
        module_name: str | None = None,
        path: str | None = None,
        max_chars: int = 12000,
        purpose: str = "",
        question: str = "",
        expected_evidence: str = "",
    ) -> ToolResponse:
        """Read the original spec document or current module spec excerpt."""
        blocked = self._readonly_budget_exceeded_response("read_spec")
        if blocked is not None:
            return blocked
        router_required = self._router_first_required_response("read_spec")
        if router_required is not None:
            return router_required
        route_restricted = self._route_read_restricted_response("read_spec", {"module_name": module_name, "path": path})
        if route_restricted is not None:
            return route_restricted
        result = await asyncio.to_thread(self._require_tools().read_spec, module_name, path, max_chars)
        self._record_route_read_if_recommended("read_spec", {"module_name": module_name, "path": path})
        return self._tool_response(
            "read_spec",
            result,
            trace_meta={
                "intent": self._trace_intent(purpose, question, expected_evidence),
                "args": {"module_name": module_name, "path": path},
            },
        )

    async def retrieve_spec_block(
        self,
        module_name: str,
        query: str | None = None,
        block_id: str | None = None,
        max_results: int = 8,
        purpose: str = "",
        question: str = "",
        expected_evidence: str = "",
    ) -> ToolResponse:
        """Retrieve relevant module spec blocks from spec_blocks.json by block id or query."""
        blocked = self._readonly_budget_exceeded_response("retrieve_spec_block")
        if blocked is not None:
            return blocked
        router_required = self._router_first_required_response("retrieve_spec_block")
        if router_required is not None:
            return router_required
        route_restricted = self._route_read_restricted_response(
            "retrieve_spec_block",
            {"module_name": module_name, "query": query, "block_id": block_id, "max_results": max_results},
        )
        if route_restricted is not None:
            return route_restricted
        result = await asyncio.to_thread(
            self._require_tools().retrieve_spec_block,
            module_name,
            query,
            block_id,
            max_results,
        )
        self._record_route_read_if_recommended(
            "retrieve_spec_block",
            {"module_name": module_name, "query": query, "block_id": block_id, "max_results": max_results},
        )
        return self._tool_response(
            "retrieve_spec_block",
            result,
            trace_meta={
                "intent": self._trace_intent(purpose, question, expected_evidence),
                "args": {"module_name": module_name, "query": query, "block_id": block_id, "max_results": max_results},
            },
        )

    async def read_long_term_memory(
        self,
        path: str,
        max_chars: int = 8000,
        purpose: str = "",
        question: str = "",
        expected_evidence: str = "",
    ) -> ToolResponse:
        """Read a selected RTL long-term memory markdown file."""
        blocked = self._readonly_budget_exceeded_response("read_long_term_memory")
        if blocked is not None:
            return blocked
        router_required = self._router_first_required_response("read_long_term_memory")
        if router_required is not None:
            return router_required
        route_restricted = self._route_read_restricted_response("read_long_term_memory", {"path": path})
        if route_restricted is not None:
            return route_restricted
        result = await asyncio.to_thread(self._require_tools().read_long_term_memory, path, max_chars)
        self._record_route_read_if_recommended("read_long_term_memory", {"path": path})
        return self._tool_response(
            "read_long_term_memory",
            result,
            trace_meta={
                "intent": self._trace_intent(purpose, question, expected_evidence),
                "args": {"path": path},
            },
        )

    async def list_vcd_signals(
        self,
        pattern: str = "",
        scope: str = "",
        limit: int = 100,
        purpose: str = "",
        question: str = "",
        expected_evidence: str = "",
    ) -> ToolResponse:
        """List VCD signal names matching an optional pattern and scope."""
        blocked = self._readonly_budget_exceeded_response("list_vcd_signals")
        if blocked is not None:
            return blocked
        router_required = self._router_first_required_response("list_vcd_signals")
        if router_required is not None:
            return router_required
        route_restricted = self._route_read_restricted_response("list_vcd_signals", {"pattern": pattern, "scope": scope, "limit": limit})
        if route_restricted is not None:
            return route_restricted
        result = await asyncio.to_thread(self._require_tools().list_vcd_signals, pattern, scope, limit)
        self._record_route_read_if_recommended("list_vcd_signals", {"pattern": pattern, "scope": scope, "limit": limit})
        return self._tool_response(
            "list_vcd_signals",
            result,
            trace_meta={
                "intent": self._trace_intent(purpose, question, expected_evidence),
                "args": {"pattern": pattern, "scope": scope, "limit": limit},
            },
        )

    async def probe_vcd(
        self,
        signals: list[str],
        time: int | None = None,
        time_range: list[int] | None = None,
        edge: str | None = None,
        mode: str = "sample",
        max_rows: int = 80,
        purpose: str = "",
        question: str = "",
        expected_evidence: str = "",
    ) -> ToolResponse:
        """Sample VCD signals at a time or over a time window with optional edge filtering."""
        blocked = self._readonly_budget_exceeded_response("probe_vcd")
        if blocked is not None:
            return blocked
        initial_trace_required = self._initial_trace_gate_response("probe_vcd")
        if initial_trace_required is not None:
            return initial_trace_required
        router_required = self._router_first_required_response("probe_vcd")
        if router_required is not None:
            return router_required
        route_restricted = self._route_read_restricted_response(
            "probe_vcd",
            {"signals": signals, "time": time, "time_range": time_range, "edge": edge, "mode": mode},
        )
        if route_restricted is not None:
            return route_restricted
        result = await asyncio.to_thread(
            self._require_tools().probe_vcd,
            signals,
            time,
            time_range,
            edge,
            mode,
            max_rows,
        )
        self._record_route_read_if_recommended("probe_vcd", {"signals": signals, "time": time, "time_range": time_range, "edge": edge, "mode": mode})
        return self._tool_response(
            "probe_vcd",
            result,
            trace_meta={
                "intent": self._trace_intent(purpose, question, expected_evidence),
                "args": {"signals": signals, "time": time, "time_range": time_range, "edge": edge, "mode": mode},
            },
        )

    async def run_check(
        self,
        mode: Literal["lint", "module_sim", "top_sim", "trace_summary", "first_divergence", "wave_window"],
        module_name: str | None = None,
        signals: list[str] | None = None,
        time_window: tuple[int, int] | None = None,
        purpose: str = "",
        question: str = "",
        expected_evidence: str = "",
    ) -> ToolResponse:
        """Run lint, module simulation, trace summary, or v1 placeholder checks."""
        blocked = self._readonly_budget_exceeded_response("run_check")
        if blocked is not None:
            return blocked
        router_required = self._router_first_required_response("run_check")
        if router_required is not None:
            return router_required
        route_restricted = self._route_read_restricted_response("run_check", {"mode": mode, "module_name": module_name, "signals": signals, "time_window": time_window})
        if route_restricted is not None:
            return route_restricted
        result = await asyncio.to_thread(
            self._require_tools().run_check,
            mode,
            module_name,
            signals,
            time_window,
        )
        self._record_route_read_if_recommended("run_check", {"mode": mode, "module_name": module_name, "signals": signals, "time_window": time_window})
        return self._tool_response(
            "run_check",
            result,
            trace_meta={
                "intent": self._trace_intent(purpose, question, expected_evidence),
                "args": {"mode": mode, "module_name": module_name, "signals": signals, "time_window": time_window},
            },
        )

    async def read_memory(
        self,
        kind: Literal[
            "snapshot",
            "brief",
            "repair_journal",
            "repair_ledger",
            "protected_invariants",
            "unsafe_directions",
            "failed_directions",
            "promising_directions",
            "next_target",
            "raw_snapshot",
        ] = "snapshot",
        limit: int = 5,
    ) -> ToolResponse:
        """Read RepoReAct repair memory."""
        blocked = self._readonly_budget_exceeded_response("read_memory")
        if blocked is not None:
            return blocked
        router_required = self._router_first_required_response("read_memory")
        if router_required is not None:
            return router_required
        result = await asyncio.to_thread(self._require_tools().read_memory, kind, limit)
        return self._tool_response("read_memory", result)

    async def route_debug_context(
        self,
        goal: DebugContextGoal = "specific_question",
        focus_signals: list[str] | None = None,
        focus_blocks: list[str] | None = None,
        missing_evidence: list[str] | None = None,
        max_items: int = 5,
        purpose: str = "",
        question: str = "",
        expected_evidence: str = "",
    ) -> ToolResponse:
        """Ask the read-only DebugContextRouter for a short context pack."""
        blocked = self._readonly_budget_exceeded_response("route_debug_context")
        if blocked is not None:
            return blocked
        result = await asyncio.to_thread(
            self._route_context_pack,
            goal,
            focus_signals,
            focus_blocks,
            missing_evidence,
            max_items,
        )
        summary = self._compact_route_debug_context_result(result)
        self._set_route_allowed_reads(summary)
        return self._tool_response(
            "route_debug_context",
            summary,
            trace_meta={
                "intent": self._trace_intent(purpose, question, expected_evidence),
                "args": {
                    "goal": goal,
                    "focus_signals": focus_signals,
                    "focus_blocks": focus_blocks,
                    "missing_evidence": missing_evidence,
                    "max_items": max_items,
                },
            },
        )

    async def apply_patch(
        self,
        patches: list[dict[str, Any]],
        reason: str,
        expected_effect: str,
        protected_invariants_checked: list[str] | None = None,
        preserve_plan: str | None = None,
        syntax_retry_of: str | None = None,
        verify: bool = True,
        rollback_on_fail: bool = True,
    ) -> ToolResponse:
        """Apply a controlled RTL patch with automatic lint/sim/trace verification and rollback."""
        post_patch_trace_required = self._post_patch_trace_required_response("apply_patch")
        if post_patch_trace_required is not None:
            return post_patch_trace_required
        router_required = self._router_first_required_response("apply_patch")
        if router_required is not None:
            return router_required
        result = await asyncio.to_thread(
            self._require_tools().apply_patch,
            patches,
            reason,
            expected_effect,
            protected_invariants_checked,
            preserve_plan,
            syntax_retry_of,
            verify,
            rollback_on_fail,
        )
        result = self._attach_post_patch_trace_requirement(dict(result))
        return self._tool_response(
            "apply_patch",
            result,
            trace_meta={
                "intent": {"reason": reason, "expected_effect": expected_effect},
                "args": {
                    "patches": [
                        {key: patch.get(key) for key in ("path", "start_line", "end_line")}
                        for patch in patches
                        if isinstance(patch, dict)
                    ],
                    "syntax_retry_of": syntax_retry_of,
                    "verify": verify,
                    "rollback_on_fail": rollback_on_fail,
                },
            },
        )

    async def replace_block(
        self,
        module_name: str,
        rtl_block_id: str,
        new_code: str,
        reason: str,
        expected_effect: str,
        protected_invariants_checked: list[str] | None = None,
        preserve_plan: str | None = None,
        syntax_retry_of: str | None = None,
        verify: bool = True,
        rollback_on_fail: bool = True,
    ) -> ToolResponse:
        """Replace one complete RTL block with automatic verification and rollback."""
        post_patch_trace_required = self._post_patch_trace_required_response("replace_block")
        if post_patch_trace_required is not None:
            return post_patch_trace_required
        router_required = self._router_first_required_response("replace_block")
        if router_required is not None:
            return router_required
        result = await asyncio.to_thread(
            self._require_tools().replace_block,
            rtl_block_id,
            new_code,
            reason,
            expected_effect,
            protected_invariants_checked,
            preserve_plan,
            syntax_retry_of,
            verify,
            rollback_on_fail,
            module_name,
            rtl_block_id,
        )
        result = self._attach_post_patch_trace_requirement(dict(result))
        return self._tool_response(
            "replace_block",
            result,
            trace_meta={
                "intent": {"reason": reason, "expected_effect": expected_effect},
                "args": {
                    "module_name": module_name,
                    "rtl_block_id": rtl_block_id,
                    "rtl_block_ref": f"{module_name}:{rtl_block_id}",
                    "syntax_retry_of": syntax_retry_of,
                    "verify": verify,
                    "rollback_on_fail": rollback_on_fail,
                },
            },
        )

    async def record_correction(
        self,
        correction_type: Literal[
            "wrong_contract",
            "wrong_module_plan",
            "wrong_interface",
            "wrong_timing",
            "wrong_dependency",
            "wrong_retrieval",
        ],
        module_name: str,
        original_artifact: str,
        problem: str,
        evidence: list[str],
        override: dict[str, Any],
    ) -> ToolResponse:
        """Record a planning correction overlay without editing original stage artifacts."""
        router_required = self._router_first_required_response("record_correction")
        if router_required is not None:
            return router_required
        result = await asyncio.to_thread(
            self._require_tools().record_correction,
            correction_type,
            module_name,
            original_artifact,
            problem,
            evidence,
            override,
        )
        return self._tool_response(
            "record_correction",
            result,
            trace_meta={
                "intent": {"reason": problem, "expected_effect": "record planning correction overlay"},
                "args": {"correction_type": correction_type, "module_name": module_name, "original_artifact": original_artifact},
            },
        )

    def _build_initial_trace(self, inp: RepoReActInput) -> dict[str, Any]:
        try:
            report, _blocks = build_trace_report(
                rtl_path=inp.rtl_path,
                sim_log_json=inp.sim_failed_log,
                output_dir=inp.debug_workdir,
                planner_module_name=inp.module_name,
                runtime_top_module=inp.top_module or inp.module_name,
                kg_service=self.kg_service,
                kg_hop_depth=inp.kg_hop_depth,
            )
            (inp.debug_workdir / "trace_report.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001
            report = {"trace_error": f"{type(exc).__name__}: {exc}"}
        report = report if isinstance(report, dict) else {}
        self._initial_dut_instance = str(report.get("dut_instance") or "")
        divergence_report = report.get("first_divergence")
        divergence_report = divergence_report if isinstance(divergence_report, dict) else {}
        first = (
            divergence_report.get("first_divergence")
            if divergence_report.get("status") in {"ok", "stable_values_match_but_tb_edge_mismatch"}
            else None
        )
        first = first if isinstance(first, dict) else {}
        root_module = str(report.get("runtime_top_module") or inp.top_module or inp.module_name)
        root_signal = first.get("signal")
        divergence_time = first.get("time")
        expected_value = first.get("ref")
        actual_value = first.get("dut")
        sampling_event = divergence_report.get("sampling_event") or report.get("sampling_event")

        arguments: dict[str, Any] = {}
        required_next_tool: str | None = None
        if root_signal not in (None, "") and divergence_time is not None:
            required_next_tool = "trace_signal_cause"
            arguments = {
                "module_name": root_module,
                "signal_name": str(root_signal),
                "time": int(divergence_time),
                "expected_value": None if expected_value is None else str(expected_value),
            }

        # The full trace remains available in trace_report.json. The initial
        # prompt intentionally receives only the first-divergence seed so that
        # trace_signal_cause owns driver, waveform, and one-hop localization.
        return {
            "root_module": root_module,
            "root_signal": root_signal,
            "first_divergence_time": divergence_time,
            "expected_value": expected_value,
            "actual_value": actual_value,
            "sampling_event": sampling_event,
            "required_next_tool": required_next_tool,
            "arguments": arguments,
        }

    async def chat(self, inp: RepoReActInput) -> RepoReActResult:
        self.reset()
        self._configure_scope_defaults(inp)
        inp.debug_workdir.mkdir(parents=True, exist_ok=True)
        journal = RepoReActJournal(inp.workspace_root / "repo_react" / inp.module_name)
        first_fail = _extract_first_fail_time(inp.sim_failed_log)
        state = RepoReActToolState(
            input=inp,
            sim_reviewer=self.sim_reviewer,
            journal=journal,
            kg_service=self.kg_service,
            model_cfg=self.cfg,
            logger=self.logger,
            last_sim=SimSnapshot(
                is_pass=False,
                mismatch_count=int(inp.initial_mismatch_count),
                first_fail_time=first_fail,
                sim_output_path=str(inp.debug_workdir / "initial_sim_output.json"),
            ),
            last_sim_output=inp.sim_failed_log,
        )
        self._state = state
        self._tools = RepoReActTools(state)
        self._context_router = DebugContextRouter(cfg=self.cfg, tools=self._tools, logger=self.logger)
        max_steps = max(1, int(inp.max_steps or self.max_steps))
        max_agent_turns = self._resolve_max_agent_turns(inp, max_steps)
        agent_turns = 0
        initial_trace = self._build_initial_trace(inp)
        state.last_trace_summary = initial_trace
        required_initial_trace = (
            initial_trace.get("arguments")
            if initial_trace.get("required_next_tool") == "trace_signal_cause"
            else {}
        )
        self._required_initial_trace_call = (
            dict(required_initial_trace) if isinstance(required_initial_trace, dict) else {}
        )
        self._initial_trace_completed = not bool(self._required_initial_trace_call)
        if self._required_initial_trace_call:
            state.last_divergence_summary = {
                "status": "ok",
                "sampling_event": initial_trace.get("sampling_event"),
                "first_divergence": {
                    "signal": initial_trace.get("root_signal"),
                    "time": initial_trace.get("first_divergence_time"),
                    "ref": initial_trace.get("expected_value"),
                    "dut": initial_trace.get("actual_value"),
                },
            }
            state.observed_real_divergence = True
        corrections = self._tools.load_known_corrections()
        memory_snapshot = self._tools.persist_memory_snapshot()
        memory_brief = self._memory_summary(memory_snapshot)
        context_pack = inp.context_pack_json if isinstance(inp.context_pack_json, dict) else {}
        self._latest_context_pack = context_pack
        first_prompt = build_initial_prompt(
            module_name=inp.module_name,
            runtime_top_module=inp.top_module or inp.module_name,
            dut_instance=str(getattr(self, "_initial_dut_instance", "") or ""),
            repair_mode=inp.repair_mode,
            rtl_path=str(inp.rtl_path),
            merged_file=str(inp.merged_file),
            spec_text=inp.spec_text,
            contract_json=inp.contract_json,
            sim_failed_excerpt=_summarize_command_json(inp.sim_failed_log),
            trace_summary=initial_trace,
            corrections=corrections,
            memory_snapshot=memory_brief,
            context_pack=context_pack,
        )
        journal.write_json(
            "initial_context.json",
            {"prompt": first_prompt, "trace_summary": initial_trace, "context_pack": context_pack},
        )
        journal.append_jsonl("react_trace.jsonl", {"role": "user", "content": first_prompt})

        try:
            agent_turns += 1
            msg = await self._agent(Msg("user", first_prompt, role="user"))
            text = msg.get_text_content() or ""
            diag = _extract_diagnosis(text)
            journal.append_jsonl(
                "react_trace.jsonl",
                {"role": "assistant", "content": text, "diagnosis": diag.model_dump() if diag else None},
            )
            self._record_unexecuted_tool_call(text)
            while agent_turns < max_agent_turns:
                if state.last_sim.is_pass and state.last_sim.mismatch_count == 0:
                    break
                if int(state.action_calls) >= max_steps:
                    break
                recovery = self._pending_tool_call_recovery
                if recovery:
                    self._pending_tool_call_recovery = {}
                    context_pack = {}
                    prompt = build_tool_call_recovery_prompt(recovery.get("tool_name"))
                else:
                    compact_decision = self._compact_decision()
                    if compact_decision == "light":
                        context_pack = await self._light_consolidate_context()
                    elif compact_decision in {"checkpoint", "deep"}:
                        compact_agent_turn = await self._compact_agent_memory(mode=compact_decision)
                        if compact_agent_turn:
                            agent_turns += 1
                        if state.last_sim.is_pass and state.last_sim.mismatch_count == 0:
                            break
                        if int(state.action_calls) >= max_steps:
                            break
                        if agent_turns >= max_agent_turns:
                            break
                        context_pack = self._latest_context_pack
                    else:
                        context_pack = {}
                    recovery = self._pending_tool_call_recovery
                    if recovery:
                        self._pending_tool_call_recovery = {}
                        context_pack = {}
                        prompt = build_tool_call_recovery_prompt(recovery.get("tool_name"))
                    else:
                        snapshot = await asyncio.to_thread(self._tools.persist_memory_snapshot)
                        if not context_pack:
                            context_pack = self._latest_context_pack or {}
                        prompt = build_continue_prompt(
                            memory_summary=self._memory_summary(snapshot),
                            readonly_calls_since_action=self._readonly_calls_since_action,
                            max_readonly_calls=self._max_readonly_calls_since_action,
                            context_pack=context_pack,
                        )
                next_turn = agent_turns + 1
                journal.append_jsonl("react_trace.jsonl", {"role": "user", "content": prompt, "step": next_turn})
                agent_turns += 1
                msg = await self._agent(Msg("user", prompt, role="user"))
                text = msg.get_text_content() or ""
                diag = _extract_diagnosis(text)
                journal.append_jsonl(
                    "react_trace.jsonl",
                    {
                        "role": "assistant",
                        "content": text,
                        "step": agent_turns,
                        "diagnosis": diag.model_dump() if diag else None,
                    },
                )
                self._record_unexecuted_tool_call(text)
                if state.last_sim.is_pass and state.last_sim.mismatch_count == 0:
                    break
                if int(state.action_calls) >= max_steps:
                    break

            rtl_code = inp.rtl_path.read_text(encoding="utf-8") if inp.rtl_path.exists() else ""
            if self._tools is not None:
                await asyncio.to_thread(self._tools.persist_memory_snapshot)
            status = "pass" if state.last_sim.is_pass and state.last_sim.mismatch_count == 0 else "max_steps_exceeded"
            if status == "pass":
                reason = ""
            elif int(state.action_calls) >= max_steps:
                reason = (
                    "RepoReActRunner ended without passing module simulation; "
                    f"repair action budget exhausted ({state.action_calls}/{max_steps})."
                )
            elif agent_turns >= max_agent_turns:
                reason = (
                    "RepoReActRunner ended without passing module simulation; "
                    f"agent turn budget exhausted ({agent_turns}/{max_agent_turns}) with "
                    f"{state.action_calls}/{max_steps} functional actions used."
                )
            else:
                reason = "RepoReActRunner ended without passing module simulation."
            return RepoReActResult(
                status=status,
                is_pass=status == "pass",
                rtl_code=rtl_code,
                steps=agent_turns,
                agent_turns=agent_turns,
                action_calls=state.action_calls,
                patch_attempts=state.patch_attempt_id,
                mismatch_count=int(state.last_sim.mismatch_count),
                trace_report_path=str(inp.debug_workdir / "trace_report.json"),
                sim_output_path=state.last_sim.sim_output_path,
                workdir=str(journal.root),
                reason=reason,
            )
        except Exception as exc:  # noqa: BLE001
            rtl_code = inp.rtl_path.read_text(encoding="utf-8") if inp.rtl_path.exists() else ""
            journal.append_jsonl(
                "react_trace.jsonl",
                {"role": "error", "content": f"{type(exc).__name__}: {exc}"},
            )
            return RepoReActResult(
                status="error",
                is_pass=False,
                rtl_code=rtl_code,
                steps=agent_turns,
                agent_turns=agent_turns,
                action_calls=state.action_calls,
                patch_attempts=state.patch_attempt_id,
                mismatch_count=int(state.last_sim.mismatch_count),
                trace_report_path=str(inp.debug_workdir / "trace_report.json"),
                sim_output_path=state.last_sim.sim_output_path,
                workdir=str(journal.root),
                reason=f"{type(exc).__name__}: {exc}",
            )
        finally:
            await clear_memory_safely_async(self._agent)
