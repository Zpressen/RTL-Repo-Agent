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

from zerorepo.rtl_impl.debug_agent.agents import SafeReActAgent, clear_memory_safely
from zerorepo.rtl_impl.debug_agent.config import OpenAIConfig
from zerorepo.rtl_impl.debug_agent.model import make_formatter, make_openai_model
from zerorepo.rtl_impl.debug_agent.sim_reviewer import SimReviewer
from zerorepo.rtl_impl.debug_agent.trace_report import build_trace_report

from .compact import build_llm_compact_memory
from .context import DebugContextRouter
from .journal import RepoReActJournal
from .prompt import SYSTEM_PROMPT, build_compact_prompt, build_continue_prompt, build_initial_prompt
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
        "read_spec",
        "retrieve_spec_block",
        "read_long_term_memory",
        "list_vcd_signals",
        "probe_vcd",
        "run_check",
        "route_debug_context",
    }
    ACTION_TOOLS = {"apply_patch", "replace_block", "record_correction"}
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
        self._light_consolidations_since_checkpoint = 0
        self._checkpoint_count = 0
        self._readonly_budget_from_env = "ZEROREPO_REACT_READONLY_BUDGET" in os.environ
        self._max_readonly_calls_since_action = int(os.environ.get("ZEROREPO_REACT_READONLY_BUDGET", "16"))
        self._router_first_enabled = os.environ.get("ZEROREPO_REACT_ROUTER_FIRST", "0").lower() not in {"0", "false", "no"}

        toolkit = Toolkit()
        toolkit.register_tool_function(
            self.read_context,
            json_schema=_tool_schema(
                "read_context",
                "Read repository tree, files, line ranges, specs, testbench, stage artifacts, trace reports, or journals. Use route_debug_context first in a new observation cycle unless you need one exact cited artifact.",
                {
                    "kind": {
                        "type": "string",
                        "enum": [
                            "repo_tree",
                            "file",
                            "lines",
                            "spec",
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
                "Search RTL, testbench, spec, or all context with a regex pattern. Use route_debug_context first in a new observation cycle.",
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
                "Run a fixed-template RTL KG query for interface, instances, connections, or signal drivers.",
                {
                    "query_type": {
                        "type": "string",
                        "enum": [
                            "module_interface",
                            "module_instances",
                            "instance_connections",
                            "signal_drivers",
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
            self.read_spec,
            json_schema=_tool_schema(
                "read_spec",
                "Read the original spec document or current module spec excerpt.",
                {
                    "module_name": {"type": ["string", "null"]},
                    "path": {"type": ["string", "null"]},
                    "max_chars": {"type": "integer"},
                    **READONLY_TRACE_INTENT_FIELDS,
                },
                [],
            ),
        )
        toolkit.register_tool_function(
            self.retrieve_spec_block,
            json_schema=_tool_schema(
                "retrieve_spec_block",
                "Retrieve relevant module spec blocks from spec_blocks.json by block id or query.",
                {
                    "module_name": {"type": "string"},
                    "query": {"type": ["string", "null"]},
                    "block_id": {"type": ["string", "null"]},
                    "max_results": {"type": "integer"},
                    **READONLY_TRACE_INTENT_FIELDS,
                },
                ["module_name"],
            ),
        )
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
                "List VCD signal names matching an optional pattern and scope. Use route_debug_context first in a new observation cycle.",
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
                "Sample VCD signals at a time or over a time window with optional edge filtering. Use route_debug_context first in a new observation cycle.",
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
        toolkit.register_tool_function(
            self.route_debug_context,
            json_schema=_tool_schema(
                "route_debug_context",
                "Ask the read-only DebugContextRouter subagent for a short context pack with evidence citations.",
                {
                    "goal": {
                        "type": "string",
                        "enum": [
                            "initial_triage",
                            "before_patch",
                            "after_patch",
                            "compact_resume",
                            "specific_question",
                        ],
                    },
                    "focus_signals": {"type": ["array", "null"], "items": {"type": "string"}},
                    "focus_blocks": {"type": ["array", "null"], "items": {"type": "string"}},
                    "missing_evidence": {"type": ["array", "null"], "items": {"type": "string"}},
                    "max_items": {"type": "integer"},
                    **READONLY_TRACE_INTENT_FIELDS,
                },
                ["goal"],
            ),
        )
        toolkit.register_tool_function(
            self.apply_patch,
            json_schema={
                "type": "function",
                "function": {
                    "name": "apply_patch",
                    "description": "Apply one coherent RTL line-range patch whose scope matches the evidence and diagnosis, then lint/sim/trace verify and rollback on regression.",
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
                    "description": "Replace one complete parsed always/assign block when that is the natural repair scope from the evidence and diagnosis, then lint/sim/trace verify and rollback on regression.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "block_id": {"type": "string"},
                            "new_code": {"type": "string"},
                            "reason": {"type": "string"},
                            "expected_effect": {"type": "string"},
                            "protected_invariants_checked": {"type": ["array", "null"], "items": {"type": "string"}},
                            "preserve_plan": {"type": ["string", "null"]},
                            "verify": {"type": "boolean"},
                            "rollback_on_fail": {"type": "boolean"},
                        },
                        "required": ["block_id", "new_code", "reason", "expected_effect"],
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
        self._light_consolidations_since_checkpoint = 0
        self._checkpoint_count = 0

    def _configure_scope_defaults(self, inp: RepoReActInput) -> None:
        if inp.repair_scope == "repo" and not self._readonly_budget_from_env:
            self._max_readonly_calls_since_action = max(self._max_readonly_calls_since_action, 32)

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

    def _tool_kind(self, name: str) -> str:
        if name in self.ACTION_TOOLS:
            return "action"
        if name == "route_debug_context":
            return "route"
        return "read"

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
        if name in self.ACTION_TOOLS:
            self._readonly_calls_since_action = 0
            self._route_calls_since_action = 0
            self._route_allowed_reads = []
            self._route_read_count = 0
        elif name == "route_debug_context":
            self._route_calls_since_action += 1
            self._readonly_calls_since_action += 1
            self._readonly_calls_since_light += 1
        elif name in self.READONLY_TOOLS:
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
            "required_next_action": ["apply_patch", "replace_block", "record_correction", "generate_response"],
            "message": (
                "Observation budget exhausted. Stop reading more context unless you first take a write action "
                "or finish with generate_response. Use the memory summary and evidence already gathered."
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
            "max_steps": snapshot.get("max_steps"),
        }

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

    async def _compact_agent_memory(self, mode: Literal["checkpoint", "deep"] = "checkpoint") -> None:
        if self._tools is None or self._state is None:
            return
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
        if llm_compact:
            self._state.journal.write_json("repo_react_llm_compact.json", llm_compact)
        prompt = build_compact_prompt(context_pack, mode=mode, llm_compact_memory=llm_compact)
        clear_memory_safely(self._agent)
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
        await self._agent(Msg("user", prompt, role="user"))

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
        verify: bool = True,
        rollback_on_fail: bool = True,
    ) -> ToolResponse:
        """Apply a controlled RTL patch with automatic lint/sim/trace verification and rollback."""
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
            verify,
            rollback_on_fail,
        )
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
                    "verify": verify,
                    "rollback_on_fail": rollback_on_fail,
                },
            },
        )

    async def replace_block(
        self,
        block_id: str,
        new_code: str,
        reason: str,
        expected_effect: str,
        protected_invariants_checked: list[str] | None = None,
        preserve_plan: str | None = None,
        verify: bool = True,
        rollback_on_fail: bool = True,
    ) -> ToolResponse:
        """Replace one complete RTL block with automatic verification and rollback."""
        router_required = self._router_first_required_response("replace_block")
        if router_required is not None:
            return router_required
        result = await asyncio.to_thread(
            self._require_tools().replace_block,
            block_id,
            new_code,
            reason,
            expected_effect,
            protected_invariants_checked,
            preserve_plan,
            verify,
            rollback_on_fail,
        )
        return self._tool_response(
            "replace_block",
            result,
            trace_meta={
                "intent": {"reason": reason, "expected_effect": expected_effect},
                "args": {"block_id": block_id, "verify": verify, "rollback_on_fail": rollback_on_fail},
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
                kg_service=self.kg_service,
                kg_hop_depth=inp.kg_hop_depth,
            )
            (inp.debug_workdir / "trace_report.json").write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:  # noqa: BLE001
            report = {"trace_error": f"{type(exc).__name__}: {exc}"}
        chains = ((report.get("value_backtrace") or {}).get("chains") or [])[:3] if isinstance(report, dict) else []
        return {
            "fail_time": report.get("fail_time") if isinstance(report, dict) else None,
            "total_mismatches": report.get("total_mismatches") if isinstance(report, dict) else None,
            "first_failure": report.get("first_failure") if isinstance(report, dict) else None,
            "root_failure": report.get("root_failure") if isinstance(report, dict) else None,
            "first_divergence": report.get("first_divergence") if isinstance(report, dict) else None,
            "required_next_tool": report.get("required_next_tool") if isinstance(report, dict) else None,
            "ignored_tb_metrics": report.get("ignored_tb_metrics") if isinstance(report, dict) else None,
            "raw_fail_outputs": report.get("raw_fail_outputs") if isinstance(report, dict) else None,
            "top_diagnosis": (report.get("diagnostic_narrative") or [None])[0] if isinstance(report, dict) else None,
            "suspect_blocks": (report.get("suspect_blocks") or [])[:8] if isinstance(report, dict) else [],
            "value_backtrace_summary": [
                {
                    "sig": chain.get("sig"),
                    "expected": chain.get("expected"),
                    "actual": chain.get("actual"),
                    "steps": [
                        {
                            "signal": step.get("signal"),
                            "driver_block_id": step.get("driver_block_id"),
                            "classification": step.get("classification"),
                            "reason": step.get("reason"),
                        }
                        for step in (chain.get("chain") or [])[:4]
                        if isinstance(step, dict)
                    ],
                }
                for chain in chains
                if isinstance(chain, dict)
            ],
            "vcd_available": report.get("vcd_available") if isinstance(report, dict) else None,
            "trace_error": report.get("trace_error") if isinstance(report, dict) else None,
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
        initial_trace = self._build_initial_trace(inp)
        state.last_trace_summary = initial_trace
        initial_divergence = initial_trace.get("first_divergence")
        if isinstance(initial_divergence, dict):
            state.last_divergence_summary = initial_divergence
            if initial_divergence.get("status") in {"ok", "stable_values_match_but_tb_edge_mismatch"} and initial_divergence.get("first_divergence"):
                state.observed_real_divergence = True
        corrections = self._tools.load_known_corrections()
        memory_snapshot = self._tools.persist_memory_snapshot()
        memory_brief = self._memory_summary(memory_snapshot)
        context_pack = inp.context_pack_json if isinstance(inp.context_pack_json, dict) else {}
        self._latest_context_pack = context_pack
        first_prompt = build_initial_prompt(
            module_name=inp.module_name,
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
            msg = await self._agent(Msg("user", first_prompt, role="user"))
            text = msg.get_text_content() or ""
            diag = _extract_diagnosis(text)
            journal.append_jsonl(
                "react_trace.jsonl",
                {"role": "assistant", "content": text, "diagnosis": diag.model_dump() if diag else None},
            )
            for step in range(1, max_steps + 1):
                if state.last_sim.is_pass and state.last_sim.mismatch_count == 0:
                    break
                if int(state.action_calls) >= max_steps:
                    break
                compact_decision = self._compact_decision()
                if compact_decision == "light":
                    context_pack = await self._light_consolidate_context()
                elif compact_decision in {"checkpoint", "deep"}:
                    await self._compact_agent_memory(mode=compact_decision)
                    if state.last_sim.is_pass and state.last_sim.mismatch_count == 0:
                        break
                    if int(state.action_calls) >= max_steps:
                        break
                    context_pack = self._latest_context_pack
                else:
                    context_pack = {}
                snapshot = await asyncio.to_thread(self._tools.persist_memory_snapshot)
                if not context_pack:
                    context_pack = self._latest_context_pack or {}
                prompt = build_continue_prompt(
                    memory_summary=self._memory_summary(snapshot),
                    readonly_calls_since_action=self._readonly_calls_since_action,
                    max_readonly_calls=self._max_readonly_calls_since_action,
                    context_pack=context_pack,
                )
                journal.append_jsonl("react_trace.jsonl", {"role": "user", "content": prompt, "step": step})
                msg = await self._agent(Msg("user", prompt, role="user"))
                text = msg.get_text_content() or ""
                diag = _extract_diagnosis(text)
                journal.append_jsonl(
                    "react_trace.jsonl",
                    {
                        "role": "assistant",
                        "content": text,
                        "step": step,
                        "diagnosis": diag.model_dump() if diag else None,
                    },
                )
                if state.last_sim.is_pass and state.last_sim.mismatch_count == 0:
                    break
                if int(state.action_calls) >= max_steps:
                    break

            rtl_code = inp.rtl_path.read_text(encoding="utf-8") if inp.rtl_path.exists() else ""
            if self._tools is not None:
                await asyncio.to_thread(self._tools.persist_memory_snapshot)
            status = "pass" if state.last_sim.is_pass and state.last_sim.mismatch_count == 0 else "max_steps_exceeded"
            reason = "" if status == "pass" else (
                f"RepoReActRunner ended without passing module simulation; "
                f"repair action budget exhausted ({state.action_calls}/{max_steps})."
                if int(state.action_calls) >= max_steps
                else "RepoReActRunner ended without passing module simulation."
            )
            return RepoReActResult(
                status=status,
                is_pass=status == "pass",
                rtl_code=rtl_code,
                steps=max_steps,
                action_calls=state.action_calls,
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
                steps=0,
                action_calls=state.action_calls,
                mismatch_count=int(state.last_sim.mismatch_count),
                trace_report_path=str(inp.debug_workdir / "trace_report.json"),
                sim_output_path=state.last_sim.sim_output_path,
                workdir=str(journal.root),
                reason=f"{type(exc).__name__}: {exc}",
            )
        finally:
            clear_memory_safely(self._agent)
