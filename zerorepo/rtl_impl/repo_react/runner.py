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

from .journal import RepoReActJournal
from .prompt import SYSTEM_PROMPT, build_compact_prompt, build_continue_prompt, build_initial_prompt
from .schemas import Diagnosis, RepoReActInput, RepoReActResult, SimSnapshot
from .tools import RepoReActToolState, RepoReActTools, _extract_first_fail_time, _summarize_command_json


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
        "list_vcd_signals",
        "probe_vcd",
        "run_check",
    }
    ACTION_TOOLS = {"apply_patch", "replace_block", "record_correction"}

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
        self._last_compacted_action_calls = 0
        self._tool_result_chars_since_compact = 0
        self._readonly_calls_since_action = 0
        self._max_readonly_calls_since_action = int(os.environ.get("ZEROREPO_REACT_READONLY_BUDGET", "16"))

        toolkit = Toolkit()
        toolkit.register_tool_function(
            self.read_context,
            json_schema=_tool_schema(
                "read_context",
                "Read repository tree, files, line ranges, specs, testbench, stage artifacts, trace reports, or journals.",
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
                    "artifact_name": {"type": ["string", "null"]},
                    "max_chars": {"type": "integer"},
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
                },
                ["module_name"],
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
                },
                ["mode"],
            ),
        )
        toolkit.register_tool_function(
            self.read_memory,
            json_schema=_tool_schema(
                "read_memory",
                "Read RepoReAct repair memory, failed directions, promising directions, or full snapshot.",
                {
                    "kind": {
                        "type": "string",
                        "enum": [
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
                        ],
                    },
                    "limit": {"type": "integer"},
                },
                [],
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
            max_iters=12,
        )

    def reset(self) -> None:
        clear_memory_safely(self._agent)
        self._state = None
        self._tools = None
        self._last_compacted_action_calls = 0
        self._tool_result_chars_since_compact = 0
        self._readonly_calls_since_action = 0

    def _tool_response(self, name: str, payload: dict[str, Any]) -> ToolResponse:
        if self._state is not None:
            self._state.journal.append_jsonl(
                "react_trace.jsonl",
                {"role": "tool", "tool_name": name, "tool_result": payload},
            )
        text = json.dumps(payload, indent=2, ensure_ascii=False)
        self._tool_result_chars_since_compact += len(text)
        if name in self.ACTION_TOOLS:
            self._readonly_calls_since_action = 0
        elif name in self.READONLY_TOOLS:
            self._readonly_calls_since_action += 1
        return ToolResponse(content=[{"type": "text", "text": text}])

    def _require_tools(self) -> RepoReActTools:
        if self._tools is None:
            raise RuntimeError("RepoReActRunner has no active tool state.")
        return self._tools

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

    def _needs_compact_checkpoint(self) -> bool:
        if self._state is None:
            return False
        edit_delta = int(self._state.action_calls) - int(self._last_compacted_action_calls)
        return edit_delta >= 2 or int(self._tool_result_chars_since_compact) >= 16000

    async def _compact_agent_memory(self) -> None:
        if self._tools is None or self._state is None:
            return
        snapshot = await asyncio.to_thread(self._tools.persist_memory_snapshot)
        prompt = build_compact_prompt(self._memory_summary(snapshot))
        clear_memory_safely(self._agent)
        self._last_compacted_action_calls = int(self._state.action_calls)
        self._tool_result_chars_since_compact = 0
        self._state.journal.append_jsonl("react_trace.jsonl", {"role": "user", "content": prompt, "compact": True})
        await self._agent(Msg("user", prompt, role="user"))

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
    ) -> ToolResponse:
        """Read repository tree, files, line ranges, specs, testbench, stage artifacts, trace reports, or journals."""
        blocked = self._readonly_budget_exceeded_response("read_context")
        if blocked is not None:
            return blocked
        result = await asyncio.to_thread(
            self._require_tools().read_context,
            kind,
            path,
            start,
            end,
            artifact_name,
            max_chars,
        )
        return self._tool_response("read_context", result)

    async def search_context(
        self,
        pattern: str,
        scope: Literal["rtl", "tb", "spec", "all"] = "all",
        file_glob: str = "**/*",
        max_results: int = 50,
        context_lines: int = 2,
    ) -> ToolResponse:
        """Search RTL, testbench, spec, or all context with a regex pattern."""
        blocked = self._readonly_budget_exceeded_response("search_context")
        if blocked is not None:
            return blocked
        result = await asyncio.to_thread(
            self._require_tools().search_context,
            pattern,
            scope,
            file_glob,
            max_results,
            context_lines,
        )
        return self._tool_response("search_context", result)

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
    ) -> ToolResponse:
        """Run a fixed-template RTL KG query for interface, instances, connections, or signal drivers."""
        blocked = self._readonly_budget_exceeded_response("query_rtl_kg")
        if blocked is not None:
            return blocked
        result = await asyncio.to_thread(
            self._require_tools().query_rtl_kg,
            query_type,
            module_name,
            signal_name,
            instance_name,
        )
        return self._tool_response("query_rtl_kg", result)

    async def read_spec(
        self,
        module_name: str | None = None,
        path: str | None = None,
        max_chars: int = 12000,
    ) -> ToolResponse:
        """Read the original spec document or current module spec excerpt."""
        blocked = self._readonly_budget_exceeded_response("read_spec")
        if blocked is not None:
            return blocked
        result = await asyncio.to_thread(self._require_tools().read_spec, module_name, path, max_chars)
        return self._tool_response("read_spec", result)

    async def retrieve_spec_block(
        self,
        module_name: str,
        query: str | None = None,
        block_id: str | None = None,
        max_results: int = 8,
    ) -> ToolResponse:
        """Retrieve relevant module spec blocks from spec_blocks.json by block id or query."""
        blocked = self._readonly_budget_exceeded_response("retrieve_spec_block")
        if blocked is not None:
            return blocked
        result = await asyncio.to_thread(
            self._require_tools().retrieve_spec_block,
            module_name,
            query,
            block_id,
            max_results,
        )
        return self._tool_response("retrieve_spec_block", result)

    async def list_vcd_signals(
        self,
        pattern: str = "",
        scope: str = "",
        limit: int = 100,
    ) -> ToolResponse:
        """List VCD signal names matching an optional pattern and scope."""
        blocked = self._readonly_budget_exceeded_response("list_vcd_signals")
        if blocked is not None:
            return blocked
        result = await asyncio.to_thread(self._require_tools().list_vcd_signals, pattern, scope, limit)
        return self._tool_response("list_vcd_signals", result)

    async def probe_vcd(
        self,
        signals: list[str],
        time: int | None = None,
        time_range: list[int] | None = None,
        edge: str | None = None,
        mode: str = "sample",
        max_rows: int = 80,
    ) -> ToolResponse:
        """Sample VCD signals at a time or over a time window with optional edge filtering."""
        blocked = self._readonly_budget_exceeded_response("probe_vcd")
        if blocked is not None:
            return blocked
        result = await asyncio.to_thread(
            self._require_tools().probe_vcd,
            signals,
            time,
            time_range,
            edge,
            mode,
            max_rows,
        )
        return self._tool_response("probe_vcd", result)

    async def run_check(
        self,
        mode: Literal["lint", "module_sim", "top_sim", "trace_summary", "first_divergence", "wave_window"],
        module_name: str | None = None,
        signals: list[str] | None = None,
        time_window: tuple[int, int] | None = None,
    ) -> ToolResponse:
        """Run lint, module simulation, trace summary, or v1 placeholder checks."""
        blocked = self._readonly_budget_exceeded_response("run_check")
        if blocked is not None:
            return blocked
        result = await asyncio.to_thread(
            self._require_tools().run_check,
            mode,
            module_name,
            signals,
            time_window,
        )
        return self._tool_response("run_check", result)

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
        result = await asyncio.to_thread(self._require_tools().read_memory, kind, limit)
        return self._tool_response("read_memory", result)

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
        return self._tool_response("apply_patch", result)

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
        return self._tool_response("replace_block", result)

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
        result = await asyncio.to_thread(
            self._require_tools().record_correction,
            correction_type,
            module_name,
            original_artifact,
            problem,
            evidence,
            override,
        )
        return self._tool_response("record_correction", result)

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
        inp.debug_workdir.mkdir(parents=True, exist_ok=True)
        journal = RepoReActJournal(inp.workspace_root / "repo_react" / inp.module_name)
        first_fail = _extract_first_fail_time(inp.sim_failed_log)
        state = RepoReActToolState(
            input=inp,
            sim_reviewer=self.sim_reviewer,
            journal=journal,
            kg_service=self.kg_service,
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
        max_steps = max(1, int(inp.max_steps or self.max_steps))
        initial_trace = self._build_initial_trace(inp)
        state.last_trace_summary = initial_trace
        corrections = self._tools.load_known_corrections()
        memory_snapshot = self._tools.persist_memory_snapshot()
        memory_brief = self._memory_summary(memory_snapshot)
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
        )
        journal.write_json("initial_context.json", {"prompt": first_prompt, "trace_summary": initial_trace})
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
                if self._needs_compact_checkpoint():
                    await self._compact_agent_memory()
                    if state.last_sim.is_pass and state.last_sim.mismatch_count == 0:
                        break
                    if int(state.action_calls) >= max_steps:
                        break
                snapshot = await asyncio.to_thread(self._tools.persist_memory_snapshot)
                prompt = build_continue_prompt(
                    memory_summary=self._memory_summary(snapshot),
                    readonly_calls_since_action=self._readonly_calls_since_action,
                    max_readonly_calls=self._max_readonly_calls_since_action,
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
