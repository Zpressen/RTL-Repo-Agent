from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any

from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.tool import ToolResponse, Toolkit

from zerorepo.rtl_impl.debug_agent.agents import SafeReActAgent, clear_memory_safely, close_model_safely
from zerorepo.rtl_impl.debug_agent.config import OpenAIConfig
from zerorepo.rtl_impl.debug_agent.model import make_formatter, make_openai_model

from .schemas import (
    DebugContextGoal,
    DebugContextPack,
    DebugContextRouterInput,
    EvidenceItem,
    RawArtifactRef,
    SystemTriage,
    TimingEvidence,
)
from .tools import RepoReActTools, _clip, stage_artifact_help_text


ROUTER_SYSTEM_PROMPT = """
You are a read-only RTL debug investigator. You work for the main RepoReAct
debug agent, which needs concise, analyzed evidence before it can safely patch RTL.

Your process:
1. Read the investigation brief (goal, focus signals, suspect blocks, missing evidence)
2. Call 3-6 targeted readonly tools to gather the most relevant evidence
3. Synthesize a structured system triage plus a short analysis report

Available tools:
- read_context(kind="lines", path, start, end) — read specific RTL line ranges
- read_context(kind="file", path) — read a whole file (use sparingly)
- read_context(kind="testbench"|"trace_report"|"repair_journal"|"stage_artifact") — read artifacts
- search_context(pattern, scope) — regex search in rtl/tb/spec/all
- probe_vcd(signals, time_range, mode="changes") — sample VCD waveform values
- list_vcd_signals(pattern) — discover available VCD signal names
- trace_signal_cause(module_name, signal_name, time) — one-hop RTL/VCD/KG cause trace with Instance/Port boundaries
- read_module_semantics(module_name, focus_signals, focus_blocks) — Module-centred semantics with separate planning_block_id and rtl_block_id namespaces
- query_rtl_kg(query_type, module_name, signal_name) — query the RTL knowledge graph.
  Valid query_type values: module_interface, module_instances, instance_connections.
- run_check(mode="first_divergence") — get the first DUT/ref divergence report
- read_long_term_memory(path) — read selected RTL long-term memory markdown

Rules:
- Be selective: call only the tools that directly address the investigation brief
- Prefer read_context(kind="lines") with specific line ranges over whole files
- Tool responses include visible_payload; inspect it directly for RTL/spec/KG/VCD content.
- When probing VCD, target the divergence time window
- If run_check reports missing_vcd, stop using VCD tools and switch to static RTL/KG/spec triage.
- Do NOT propose patches or decide repair strategies — you are an analyst only
- Return JSON, not prose. The JSON must have keys system_triage and analysis_text.
- Keep analysis_text under 3000 characters

Your system_triage should include:
1. category: one of compile_or_elaboration, vcd_or_trace_unavailable, top_protocol_or_fsm,
   hierarchy_connection, interface_width_or_port_order, endian_or_byte_lane_mapping,
   key_schedule_logic, round_transform_logic, sbox_or_lookup_logic, latency_or_done_timing,
   spec_or_plan_mismatch, unknown
2. confidence: 0.0 to 1.0
3. symptom, root_signal, root_time
4. suspect_modules, suspect_files, signal_path, evidence, missing_evidence
5. recommended_tool_calls and patch_scope

analysis_text should concisely cover:
1. Key evidence found (with specific line numbers, signal values, time points)
2. Which RTL blocks/lines are most suspect and why
3. Any spec/contract vs RTL mismatches observed
4. One concrete suggestion for the main agent's next investigative step
""".strip()


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


def _slug(text: str) -> str:
    value = re.sub(r"[^A-Za-z0-9_.$-]+", "_", str(text).strip())
    value = re.sub(r"_+", "_", value).strip("_")
    return value[:80] or "evidence"


class DebugContextRouter:
    """Read-only context subagent for RepoReAct.

    The deterministic fallback is intentionally first-class: debug startup must not
    depend on a second model call. When enabled, the LLM router can add focused
    evidence, but the returned pack is always schema-validated and clipped.
    """

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

    def __init__(
        self,
        *,
        cfg: OpenAIConfig | None,
        tools: RepoReActTools,
        logger: Any | None = None,
        max_tool_calls: int = 6,
    ) -> None:
        self.cfg = cfg
        self.tools = tools
        self.state = tools.state
        self.logger = logger
        configured_budget = os.environ.get("ZEROREPO_DEBUG_CONTEXT_ROUTER_MAX_TOOL_CALLS")
        if configured_budget:
            try:
                max_tool_calls = int(configured_budget)
            except ValueError:
                pass
        elif tools.state.input.repair_scope == "repo" and tools.state.input.repair_mode == "functional":
            max_tool_calls = max(int(max_tool_calls), 8)
        self.max_tool_calls = max(1, int(max_tool_calls))
        self._tool_calls = 0
        self._evidence_counter = 0
        self._vcd_unavailable = False

    def route(
        self,
        *,
        goal: DebugContextGoal = "initial_triage",
        focus_signals: list[str] | None = None,
        focus_blocks: list[str] | None = None,
        missing_evidence: list[str] | None = None,
        max_items: int = 5,
        allow_investigator: bool = True,
    ) -> dict[str, Any]:
        request = DebugContextRouterInput(
            goal=goal,
            focus_signals=focus_signals or [],
            focus_blocks=focus_blocks or [],
            missing_evidence=missing_evidence or [],
            max_items=max(1, min(int(max_items), 10)),
        )
        request = self._default_repo_focus_request(request)
        pack = self._fallback_pack(request, reason="")

        # When the main agent supplies focus parameters, or repo scope auto-focuses
        # on the current divergence, launch the LLM
        # investigator subagent.  It calls 3-6 targeted readonly tools and
        # returns structured triage plus analysis that we inject into the pack.
        # Falls back to deterministic targeted evidence when the LLM is
        # unavailable (no API key, explicitly disabled, or call fails).
        if allow_investigator and (request.focus_signals or request.focus_blocks or request.missing_evidence):
            timing = pack.timing_evidence
            investigation = self._run_investigator(request, timing, pack.task_frame)
            if investigation:
                analysis_text = str(investigation.get("analysis_text") or investigation.get("router_analysis") or "").strip()
                if analysis_text:
                    pack.task_frame["router_analysis"] = analysis_text[:3000]
                triage_payload = investigation.get("system_triage")
                if isinstance(triage_payload, dict):
                    pack.system_triage = self._merge_system_triage(pack.system_triage, triage_payload)
                pack.fallback_used = False
                pack.fallback_reason = ""
            else:
                # LLM unavailable — use deterministic targeted evidence
                det = self._gather_targeted_evidence(request, timing)
                if det:
                    pack.task_frame["router_analysis"] = det

        return self._persist_pack(pack).model_dump()

    def _default_repo_focus_request(self, request: DebugContextRouterInput) -> DebugContextRouterInput:
        inp = self.state.input
        if inp.repair_scope != "repo" or inp.repair_mode != "functional":
            return request
        if request.focus_signals or request.focus_blocks or request.missing_evidence:
            return request
        trace = self.state.last_trace_summary or {}
        divergence = self.state.last_divergence_summary or {}
        timing = self._timing_evidence(trace, divergence)
        missing = [
            "System triage: inspect module hierarchy before patching.",
            "System triage: inspect parent/child instance connections for the failing output.",
            "System triage: inspect at least one candidate child RTL/spec before assuming top logic is the root cause.",
        ]
        return request.model_copy(
            update={
                "focus_signals": [timing.signal] if timing.signal else [],
                "focus_blocks": [timing.block_id] if timing.block_id else [],
                "missing_evidence": missing,
            }
        )

    # ------------------------------------------------------------------
    # Deterministic pack construction
    # ------------------------------------------------------------------

    def _gather_targeted_evidence(
        self,
        request: DebugContextRouterInput,
        timing: TimingEvidence,
    ) -> str:
        """Call targeted read tools based on focus signals/blocks/missing_evidence.

        Returns a concise analysis string (max ~3000 chars) suitable for
        injection into ``task_frame.router_analysis``.  When the main agent
        supplies focus parameters the router actually reads fresh RTL,
        probes VCD, or retrieves spec blocks — this makes the router
        genuinely useful rather than a data repackager.
        """
        parts: list[str] = []

        # 1. focus_blocks → read suspect RTL line ranges
        for block_id in (request.focus_blocks or [])[:2]:
            for block in (self.state.last_trace_summary.get("suspect_blocks") or []):
                if not isinstance(block, dict):
                    continue
                if block.get("id") != block_id:
                    continue
                start = block.get("start_line")
                end = block.get("end_line")
                if not isinstance(start, int) or not isinstance(end, int):
                    continue
                try:
                    result = self.tools.read_context(
                        kind="lines",
                        path=str(self.state.input.rtl_path),
                        start=start,
                        end=end,
                        max_chars=4000,
                    )
                    content = result.get("content") if isinstance(result, dict) else ""
                    parts.append(
                        f"[Block {block_id} RTL L{start}-L{end}]:\n{str(content)[:2000]}"
                    )
                except Exception:
                    pass
                break  # one block per id

        # 2. focus_signals → cross-module text search (repo scope)
        inp = self.state.input
        if inp.repair_scope == "repo" and inp.rtl_root and request.focus_signals:
            for sig in request.focus_signals[:2]:
                try:
                    result = self.tools.search_context(
                        pattern=sig, scope="rtl", max_results=10,
                    )
                    results = result.get("results") if isinstance(result, dict) else []
                    files_hit: set[str] = set()
                    for r in (results or [])[:5]:
                        fp = str(r.get("file") or "")
                        if fp:
                            files_hit.add(fp.split("/")[-1] if "/" in fp else fp)
                    if files_hit:
                        parts.append(
                            f"[Cross-module: '{sig}' found in {len(files_hit)} files: "
                            f"{', '.join(sorted(files_hit)[:6])}]"
                        )
                except Exception:
                    pass

        # 3. focus_signals → probe VCD around divergence time
        if request.focus_signals and timing.time is not None:
            try:
                t0 = max(0, int(timing.time) - 20)
                t1 = int(timing.time) + 20
                result = self.tools.probe_vcd(
                    signals=list(request.focus_signals)[:4],
                    time_range=[t0, t1],
                    mode="changes",
                    max_rows=20,
                )
                rows = result.get("rows") if isinstance(result, dict) else []
                if rows:
                    parts.append(
                        f"[VCD t={timing.time} ({t0}-{t1})]: "
                        f"{len(rows)} change events for {', '.join(request.focus_signals[:3])}"
                    )
            except Exception:
                pass

        # 4. missing_evidence mentions "spec" → read Module-centred semantics
        if request.missing_evidence and any(
            "spec" in m.lower() for m in request.missing_evidence
        ):
            try:
                query = timing.signal if timing.signal else ""
                result = self.tools.read_module_semantics(
                    module_name=self.state.input.module_name,
                    sections=["spec"],
                    focus_signals=[query] if query else [],
                    max_chars=6000,
                )
                matches = result.get("spec_fragments") if isinstance(result, dict) else []
                for m in (matches or [])[:2]:
                    if not isinstance(m, dict):
                        continue
                    parts.append(
                        f"[Spec {m.get('block_id', '?')}]: {str(m.get('text', ''))[:800]}"
                    )
            except Exception:
                pass

        return "\n".join(parts[:3]) if parts else ""

    def _fallback_pack(self, request: DebugContextRouterInput, *, reason: str) -> DebugContextPack:
        snapshot = self.tools.persist_memory_snapshot()
        brief = snapshot.get("causal_memory_brief") or self.tools._causal_memory_brief(snapshot)
        trace = snapshot.get("latest_trace_summary") or self.state.last_trace_summary or {}
        divergence = snapshot.get("last_divergence_summary") or self.state.last_divergence_summary or {}
        timing = self._timing_evidence(trace, divergence)
        task_frame = self._task_frame(brief, trace, timing)
        # When the main agent supplies focus parameters, gather fresh targeted
        # evidence (RTL lines, VCD probe, spec blocks) so the router returns
        # genuinely new information rather than repackaging prompt data.
        router_analysis = ""
        if request.focus_signals or request.focus_blocks or request.missing_evidence:
            router_analysis = self._gather_targeted_evidence(request, timing)
        if router_analysis:
            task_frame["router_analysis"] = router_analysis[:3000]
        raw_artifacts = self._raw_artifacts(snapshot)
        selected_memories = self._select_long_term_memories(
            task_frame=task_frame,
            timing=timing,
            limit=min(request.max_items, 3),
        )
        causal_memory = {
            "repair_ledger_summary": (brief.get("repair_ledger") or [])[:5],
            "promising_directions": (
                brief.get("promising_directions")
                or snapshot.get("promising_directions")
                or []
            )[:5],
            "protected_invariants": (brief.get("protected_invariants") or [])[:8],
            "unsafe_directions": (brief.get("unsafe_directions") or [])[:8],
            "selected_long_term_memories": selected_memories,
            "negative_patterns": [m for m in selected_memories if m.get("type") == "negative_direction"][:3],
        }
        evidence = self._fallback_evidence(
            trace=trace,
            divergence=divergence,
            brief=brief,
            raw_artifacts=raw_artifacts,
            selected_memories=selected_memories,
            max_items=request.max_items,
        )
        system_triage = self._system_triage(
            trace=trace,
            divergence=divergence,
            timing=timing,
            raw_artifacts=raw_artifacts,
        )
        active_working_set = self._active_working_set(
            trace=trace,
            divergence=divergence,
            brief=brief,
            timing=timing,
            evidence=evidence,
            causal_memory=causal_memory,
            system_triage=system_triage,
        )
        return DebugContextPack(
            goal=request.goal,
            module=self.state.input.module_name,
            repair_mode=self.state.input.repair_mode,
            task_frame=task_frame,
            evidence_pack=evidence,
            active_working_set=active_working_set,
            causal_memory=causal_memory,
            raw_artifacts=raw_artifacts,
            timing_evidence=timing,
            system_triage=system_triage,
            fallback_used=True,
            fallback_reason=reason or "deterministic_debug_context_router",
        )

    def _generated_rtl_files(self) -> list[Path]:
        inp = self.state.input
        root = inp.rtl_root if inp.rtl_root and inp.rtl_root.exists() else inp.rtl_path.parent
        try:
            return sorted(
                p for p in root.rglob("*")
                if p.is_file() and p.suffix.lower() in {".v", ".sv"}
            )
        except OSError:
            return [inp.rtl_path] if inp.rtl_path.exists() else []

    def _system_triage(
        self,
        *,
        trace: dict[str, Any],
        divergence: dict[str, Any],
        timing: TimingEvidence,
        raw_artifacts: dict[str, RawArtifactRef],
    ) -> SystemTriage:
        inp = self.state.input
        if inp.repair_scope != "repo":
            return SystemTriage(
                root_signal=timing.signal,
                root_time=timing.time,
                symptom=self._triage_symptom(trace, timing),
                suspect_modules=[inp.module_name] if inp.module_name else [],
                suspect_files=[str(inp.rtl_path)] if inp.rtl_path else [],
                evidence=["Module-scope repair: system triage is not required."],
                patch_scope="module",
                reason="Module repair scope uses existing local debug flow.",
            )

        files = self._generated_rtl_files()
        top_name = inp.top_module or inp.module_name
        modules_by_stem = {p.stem: p for p in files}
        child_modules = [name for name in modules_by_stem if name != Path(inp.rtl_path).stem]
        suspect_modules: list[str] = []
        if top_name:
            suspect_modules.append(top_name)
        category = self._classify_system_failure(timing, trace, child_modules)
        evidence: list[str] = []
        missing: list[str] = []
        signal_path: list[dict[str, Any]] = []
        recommended: list[dict[str, Any]] = []

        kg_modules: list[str] = []
        kg_status = ""
        if top_name:
            kg_result = self.tools.query_rtl_kg("module_instances", top_name)
            kg_status = str(kg_result.get("status") or "")
            if kg_status == "ok":
                kg_modules = self._known_modules_in_payload(kg_result.get("result"), modules_by_stem)
                evidence.append(f"KG module_instances returned candidates: {kg_modules or 'none found in generated files'}.")
            else:
                evidence.append(f"KG module_instances unavailable or incomplete: {kg_status}.")
        if timing.signal:
            recommended.append(
                {
                    "tool": "trace_signal_cause",
                    "args": {
                        "module_name": top_name,
                        "signal_name": timing.signal,
                        "time": timing.time,
                        "expected_value": timing.ref or None,
                    },
                }
            )
            recommended.append(
                {
                    "tool": "read_module_semantics",
                    "args": {
                        "module_name": top_name,
                        "focus_signals": [timing.signal],
                        "focus_blocks": [timing.block_id] if timing.block_id else [],
                    },
                }
            )
            recommended.append(
                {"tool": "search_context", "args": {"pattern": timing.signal, "scope": "rtl", "max_results": 20}}
            )
            try:
                search = self.tools.search_context(timing.signal, scope="rtl", max_results=20)
                hits = search.get("results") if isinstance(search, dict) else []
                hit_files = self._files_from_search_hits(hits)
                if hit_files:
                    evidence.append(f"RTL search for {timing.signal} found {len(hit_files)} file(s).")
                    signal_path.append({"signal": timing.signal, "files": hit_files[:8], "source": "search_context"})
            except Exception as exc:  # noqa: BLE001
                evidence.append(f"RTL search fallback failed: {type(exc).__name__}: {exc}")

        for name in kg_modules + child_modules:
            if name and name not in suspect_modules:
                suspect_modules.append(name)

        suspect_files = [str(modules_by_stem[name]) for name in suspect_modules if name in modules_by_stem]
        if str(inp.rtl_path) not in suspect_files:
            suspect_files.insert(0, str(inp.rtl_path))
        if len(suspect_modules) <= 1 and child_modules:
            missing.append("Inspect child modules before concluding the top output driver is the root cause.")
        missing.append("Confirm one spec/stage clause for the selected module before patching.")
        if kg_status and kg_status != "ok":
            missing.append("KG was unavailable; use search_context/read_context to reconstruct hierarchy.")

        confidence = 0.45 if timing.signal else 0.2
        if kg_modules:
            confidence = max(confidence, 0.6)
        if category != "unknown":
            confidence = max(confidence, 0.55)

        return SystemTriage(
            category=category,
            confidence=confidence,
            symptom=self._triage_symptom(trace, timing),
            root_signal=timing.signal,
            root_time=timing.time,
            suspect_modules=suspect_modules[:8],
            suspect_files=suspect_files[:8],
            signal_path=signal_path[:8],
            evidence=evidence[:8],
            missing_evidence=missing[:8],
            recommended_tool_calls=recommended[:8],
            patch_scope="repo_child_or_top_after_triage" if len(suspect_files) > 1 else "top_module_candidate",
            reason=(
                "System-level repo repair: first divergence is only a top-level symptom; "
                "inspect hierarchy and child RTL/spec before patching."
            ),
        )

    def _triage_symptom(self, trace: dict[str, Any], timing: TimingEvidence) -> str:
        diagnosis = trace.get("top_diagnosis") or trace.get("root_failure") or ""
        if timing.signal:
            return (
                f"DUT/ref divergence on {timing.signal} at {timing.time}: "
                f"ref={timing.ref}, dut={timing.dut}. {diagnosis}"
            ).strip()
        return str(diagnosis or "No real DUT/ref divergence available.")

    def _classify_system_failure(self, timing: TimingEvidence, trace: dict[str, Any], child_modules: list[str]) -> str:
        text = " ".join(
            [
                timing.signal,
                timing.sampling_mode,
                str(trace.get("top_diagnosis") or ""),
                str(trace.get("root_failure") or ""),
                " ".join(child_modules),
            ]
        ).lower()
        if not timing.signal and "vcd" in text:
            return "vcd_or_trace_unavailable"
        if "done" in timing.signal.lower() or "latency" in text:
            return "latency_or_done_timing"
        if "sbox" in text or "lookup" in text:
            return "sbox_or_lookup_logic"
        if "key" in text or "rcon" in text:
            return "key_schedule_logic"
        if "byte" in text or "endian" in text or "lane" in text:
            return "endian_or_byte_lane_mapping"
        if "instance" in text or "port" in text or "connection" in text:
            return "hierarchy_connection"
        if timing.signal and child_modules:
            return "round_transform_logic"
        if timing.signal:
            return "top_protocol_or_fsm"
        return "unknown"

    def _known_modules_in_payload(self, payload: Any, modules_by_stem: dict[str, Path]) -> list[str]:
        text = json.dumps(payload, ensure_ascii=False, default=str)
        found = [name for name in modules_by_stem if re.search(rf"(?<![A-Za-z0-9_$]){re.escape(name)}(?![A-Za-z0-9_$])", text)]
        return sorted(found)

    def _files_from_search_hits(self, hits: Any) -> list[str]:
        files: list[str] = []
        for item in hits or []:
            if not isinstance(item, dict):
                continue
            path = str(item.get("file") or item.get("path") or "")
            if path and path not in files:
                files.append(path)
        return files

    def _merge_system_triage(self, base: SystemTriage, payload: dict[str, Any]) -> SystemTriage:
        payload = self._normalize_triage_payload(payload)
        current = base.model_dump()
        for key, value in payload.items():
            if value in (None, "", [], {}):
                continue
            if key in current:
                current[key] = value
        try:
            return SystemTriage.model_validate(current)
        except Exception:
            return base

    def _normalize_triage_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(payload)
        files = normalized.get("suspect_files")
        if isinstance(files, list):
            normalized["suspect_files"] = [
                self._normalize_generated_rtl_path(str(path)) for path in files if str(path).strip()
            ]
        calls = normalized.get("recommended_tool_calls")
        if isinstance(calls, list):
            next_calls: list[dict[str, Any]] = []
            for call in calls:
                if not isinstance(call, dict):
                    continue
                item = dict(call)
                args = dict(item.get("args") or {}) if isinstance(item.get("args"), dict) else {}
                if isinstance(args.get("path"), str):
                    args["path"] = self._normalize_generated_rtl_path(args["path"])
                item["args"] = args
                next_calls.append(item)
            normalized["recommended_tool_calls"] = next_calls
        return normalized

    def _normalize_generated_rtl_path(self, path: str) -> str:
        value = path.strip()
        if not value:
            return value
        candidate = Path(value)
        if candidate.is_absolute():
            return str(candidate)
        inp = self.state.input
        roots = []
        if inp.rtl_root:
            roots.append(inp.rtl_root)
        roots.append(inp.rtl_path.parent)
        for root in roots:
            direct = root / value
            if direct.exists():
                return str(direct)
            by_name = root / Path(value).name
            if by_name.exists():
                return str(by_name)
        return value

    def _task_frame(self, brief: dict[str, Any], trace: dict[str, Any], timing: TimingEvidence) -> dict[str, Any]:
        current_target = brief.get("next_local_target") or {}
        symptom = str(current_target.get("symptom") or "")
        target_is_placeholder = "No current DUT/ref divergence target available" in symptom
        if timing.signal and (not current_target.get("signal") or target_is_placeholder):
            current_target = {
                **current_target,
                "signal": timing.signal,
                "time": timing.time,
                "suspect_blocks": [timing.block_id] if timing.block_id else [],
                "symptom": f"DUT/ref divergence on {timing.signal} at {timing.time}: ref={timing.ref}, dut={timing.dut}",
                "ref": timing.ref,
                "dut": timing.dut,
                "edge": timing.edge,
                "sampling_mode": timing.sampling_mode,
            }
        next_action = "read_more"
        if self.state.input.repair_mode == "syntax":
            next_action = "inspect_lint_and_patch"
        elif timing.signal and self.state.observed_spec_or_stage:
            next_action = "patch_when_causal_diagnosis_is_clear"
        elif timing.signal:
            next_action = "read_spec_or_stage_before_patch"
        return {
            "current_target": current_target,
            "top_diagnosis": trace.get("top_diagnosis") or trace.get("root_failure") or "",
            "protected_invariants": (brief.get("protected_invariants") or [])[:8],
            "unsafe_directions": (brief.get("unsafe_directions") or [])[:8],
            "next_action_hint": next_action,
            "required_next_tool": trace.get("required_next_tool"),
        }

    def _active_working_set(
        self,
        *,
        trace: dict[str, Any],
        divergence: dict[str, Any],
        brief: dict[str, Any],
        timing: TimingEvidence,
        evidence: list[EvidenceItem],
        causal_memory: dict[str, Any],
        system_triage: SystemTriage | None = None,
    ) -> dict[str, Any]:
        current_failure = {
            "signal": timing.signal,
            "time": timing.time,
            "edge": timing.edge,
            "sampling_mode": timing.sampling_mode,
            "ref": timing.ref,
            "dut": timing.dut,
            "driver_assignment_kind": timing.driver_assignment_kind,
            "block_id": timing.block_id,
            "line_range": timing.line_range,
            "top_diagnosis": trace.get("top_diagnosis") or trace.get("root_failure") or "",
        }
        pinned = [
            {
                "evidence_id": item.evidence_id,
                "kind": item.kind,
                "summary": item.summary,
                "artifact_ref": item.artifact_ref.model_dump(),
                "why_kept": item.why_selected or "Selected by context router.",
                "salient": item.salient,
            }
            for item in evidence[:5]
        ]
        repair_ledger = causal_memory.get("repair_ledger_summary") if isinstance(causal_memory.get("repair_ledger_summary"), list) else []
        accepted = [
            {
                "step": row.get("step"),
                "action_type": row.get("action_type"),
                "block_id": row.get("block_id"),
                "target": row.get("target"),
                "changed_signals": row.get("changed_signals") or row.get("affected_signals") or [],
                "effect": row.get("effect"),
                "metric_delta": row.get("metric_delta"),
                "hypothesis": row.get("hypothesis"),
                "lesson": row.get("lesson"),
                "patch_summary": row.get("patch_summary"),
            }
            for row in repair_ledger
            if isinstance(row, dict) and str(row.get("effect") or "") in {"passed", "improved"}
        ][:5]
        rejected = [
            {
                "step": row.get("step"),
                "block_id": row.get("block_id"),
                "effect": row.get("effect"),
                "hypothesis": row.get("hypothesis"),
                "lesson": row.get("lesson"),
                "metric_delta": row.get("metric_delta"),
            }
            for row in repair_ledger
            if isinstance(row, dict) and str(row.get("effect") or "") in {"rejected", "syntax_failed", "regressed"}
        ][:5]
        next_local_target = brief.get("next_local_target")
        if not isinstance(next_local_target, dict):
            next_local_target = {}
        active_hypotheses: list[dict[str, Any]] = []
        if timing.signal:
            active_hypotheses.append(
                {
                    "id": "hyp_current_failure",
                    "text": current_failure["top_diagnosis"]
                    or f"Investigate {timing.signal} divergence at {timing.time}.",
                    "status": "active",
                    "evidence_ids": [item.evidence_id for item in evidence[:3]],
                    "related_blocks": [timing.block_id] if timing.block_id else [],
                    "related_signals": [timing.signal],
                    "next_check": next_local_target.get("next_action") or "",
                    "rejected_reason": "",
                }
            )
        for row in accepted[:2]:
            if row.get("hypothesis"):
                active_hypotheses.append(
                    {
                        "id": f"hyp_improved_{row.get('step')}",
                        "text": row.get("hypothesis"),
                        "status": "supported",
                        "evidence_ids": [],
                        "related_blocks": [row.get("block_id")] if row.get("block_id") else [],
                        "related_signals": row.get("changed_signals") or [],
                        "next_check": "Preserve this improved behavior while continuing repair.",
                        "rejected_reason": "",
                    }
                )
        waveform_facts = []
        if timing.signal:
            waveform_facts.append(
                {
                    "signal": timing.signal,
                    "time": timing.time,
                    "edge": timing.edge,
                    "ref": timing.ref,
                    "dut": timing.dut,
                    "classification": timing.sampling_mode or timing.driver_assignment_kind or "",
                    "source": "timing_evidence",
                }
            )
        missing_evidence: list[str] = []
        inp = self.state.input
        if inp.repair_mode == "functional" and not self.state.observed_spec_or_stage:
            missing_evidence.append("Read original spec or relevant stage artifact before functional edit.")
        if inp.repair_mode == "functional" and not self.state.observed_real_divergence:
            missing_evidence.append('Call run_check(mode="first_divergence") before functional edit.')
        if inp.repair_scope == "repo" and inp.rtl_root and inp.rtl_root.exists():
            # Check if any sub-module files exist beyond the top RTL
            sub_files = [p for p in inp.rtl_root.rglob("*") if p.is_file() and p.suffix.lower() in {".v", ".sv"} and p.name != inp.rtl_path.name]
            if sub_files:
                missing_evidence.append(
                    f"Repo scope: {len(sub_files)} sub-module files exist under {inp.rtl_root}. "
                    "Use trace_signal_cause to expose Instance/Port boundaries, then trace and read semantics "
                    "only for sub-modules that enter the suspect path."
                )
        next_edit_candidates = []
        if timing.block_id:
            next_edit_candidates.append(
                {
                    "block_id": timing.block_id,
                    "rtl_block_id": timing.block_id,
                    "rtl_block_ref": (
                        f"{self.state.input.module_name}:{timing.block_id}"
                    ),
                    "line_range": timing.line_range,
                    "signals": [timing.signal] if timing.signal else [],
                    "file": str(self.state.input.rtl_path),
                    "reason": "Primary driver/suspect block for current failure.",
                }
            )
        if system_triage is not None:
            for path in system_triage.suspect_files[:4]:
                if not path:
                    continue
                if any(c.get("file") == path for c in next_edit_candidates):
                    continue
                next_edit_candidates.append(
                    {
                        "file": path,
                        "signals": [timing.signal] if timing.signal else [],
                        "reason": "Repo-level system triage candidate; inspect before choosing patch scope.",
                    }
                )
        return {
            "current_failure": current_failure,
            "active_hypotheses": active_hypotheses[:5],
            "pinned_evidence": pinned[:5],
            "pinned_code_slices": [],
            "pinned_spec_clauses": [],
            "waveform_facts": waveform_facts[:5],
            "accepted_patch_summaries": accepted[:5],
            "rejected_hypotheses": rejected[:5],
            "next_edit_candidates": next_edit_candidates[:5],
            "missing_evidence": missing_evidence,
            "protected_invariants": causal_memory.get("protected_invariants") or [],
            "unsafe_directions": causal_memory.get("unsafe_directions") or [],
            "selected_long_term_memories": causal_memory.get("selected_long_term_memories") or [],
        }

    def _raw_artifacts(self, snapshot: dict[str, Any]) -> dict[str, RawArtifactRef]:
        inp = self.state.input
        paths = snapshot.get("paths") if isinstance(snapshot.get("paths"), dict) else {}
        spec_path = inp.spec_source_path or (inp.spec_paths[0] if inp.spec_paths else "")
        patch_journal = self.state.journal.root / "patch_journal.jsonl"
        memory_index = inp.workspace_root / "rtl_memory" / "MEMORY.md"
        refs = {
            "rtl": RawArtifactRef(kind="rtl", path=str(inp.rtl_path), description="Current debug RTL."),
            "merged_file": RawArtifactRef(kind="rtl", path=str(inp.merged_file), description="Merged RTL source."),
            "rtl_root": RawArtifactRef(
                kind="rtl_root",
                path=str(inp.rtl_root) if inp.rtl_root else "",
                description="All generated module RTL files (repo repair scope).",
            ),
            "trace_report": RawArtifactRef(
                kind="trace",
                path=str(paths.get("trace_report") or inp.debug_workdir / "trace_report.json"),
                description="Full trace report.",
            ),
            "sim_output": RawArtifactRef(
                kind="sim",
                path=self.state.last_sim.sim_output_path or str(inp.debug_workdir / "initial_sim_output.json"),
                description="Latest simulation output JSON.",
            ),
            "spec": RawArtifactRef(kind="spec", path=str(spec_path), description="Original spec path or in-memory spec_text fallback."),
            "patch_journal": RawArtifactRef(kind="journal", path=str(patch_journal), description="Full patch attempt journal."),
            "memory_index": RawArtifactRef(kind="memory_index", path=str(memory_index), description="RTL long-term memory index."),
        }
        return refs

    def _timing_evidence(self, trace: dict[str, Any], divergence: dict[str, Any]) -> TimingEvidence:
        first = divergence.get("first_divergence") if isinstance(divergence.get("first_divergence"), dict) else {}
        if not first:
            trace_div = trace.get("first_divergence") if isinstance(trace.get("first_divergence"), dict) else {}
            first = trace_div.get("first_divergence") if isinstance(trace_div.get("first_divergence"), dict) else trace_div
            if not divergence and trace_div:
                divergence = trace_div
        suspect = divergence.get("suspect") if isinstance(divergence.get("suspect"), dict) else {}
        driver_blocks = suspect.get("driver_blocks") if isinstance(suspect.get("driver_blocks"), list) else []
        block_id = ""
        line_range: list[int] = []
        if driver_blocks:
            first_block = driver_blocks[0] if isinstance(driver_blocks[0], dict) else {}
            block_id = str(first_block.get("id") or first_block.get("block_id") or "")
            start = first_block.get("start_line")
            end = first_block.get("end_line")
            if isinstance(start, int) and isinstance(end, int):
                line_range = [start, end]
        if not block_id:
            for block in trace.get("suspect_blocks") or []:
                if not isinstance(block, dict):
                    continue
                if first.get("signal") and first.get("signal") not in (block.get("writes") or []):
                    continue
                block_id = str(block.get("id") or "")
                start = block.get("start_line")
                end = block.get("end_line")
                if isinstance(start, int) and isinstance(end, int):
                    line_range = [start, end]
                break
        return TimingEvidence(
            signal=str(first.get("signal") or ""),
            time=first.get("time") if isinstance(first.get("time"), int) else None,
            edge=str(first.get("edge") or divergence.get("edge") or ""),
            sampling_mode=str(first.get("sampling_mode") or divergence.get("sampling_mode") or ""),
            ref=str(first.get("ref") or ""),
            dut=str(first.get("dut") or ""),
            driver_assignment_kind=str(first.get("driver_assignment_kind") or divergence.get("driver_assignment_kind") or ""),
            block_id=block_id,
            line_range=line_range,
        )

    def _fallback_evidence(
        self,
        *,
        trace: dict[str, Any],
        divergence: dict[str, Any],
        brief: dict[str, Any],
        raw_artifacts: dict[str, RawArtifactRef],
        selected_memories: list[dict[str, Any]],
        max_items: int,
    ) -> list[EvidenceItem]:
        items: list[EvidenceItem] = []
        candidates: list[tuple[str, str, Any, RawArtifactRef, dict[str, Any], str]] = [
            (
                "initial_trace",
                "trace",
                trace,
                raw_artifacts["trace_report"],
                {"module": self.state.input.module_name, "path": raw_artifacts["trace_report"].path},
                "Trace summary anchors the current failure target.",
            ),
            (
                "first_divergence",
                "trace",
                divergence,
                raw_artifacts["trace_report"],
                {"module": self.state.input.module_name},
                "First divergence preserves timing-sensitive evidence.",
            ),
            (
                "causal_memory",
                "memory",
                {
                    "repair_ledger": brief.get("repair_ledger"),
                    "protected_invariants": brief.get("protected_invariants"),
                    "unsafe_directions": brief.get("unsafe_directions"),
                },
                raw_artifacts["patch_journal"],
                {"module": self.state.input.module_name},
                "Recent local repair memory helps avoid repeated failures.",
            ),
        ]
        if raw_artifacts["spec"].path:
            candidates.append(
                (
                    "spec_index",
                    "spec",
                    {"path": raw_artifacts["spec"].path},
                    raw_artifacts["spec"],
                    {"module": self.state.input.module_name, "path": raw_artifacts["spec"].path},
                    "Spec path is available for just-in-time requirement lookup.",
                )
            )
        if selected_memories:
            candidates.append(
                (
                    "long_term_memory",
                    "memory",
                    selected_memories,
                    raw_artifacts["memory_index"],
                    {"module": self.state.input.module_name, "count": len(selected_memories)},
                    "Selected long-term memory files match this module/failure context.",
                )
            )
        for name, kind, payload, ref, salient, why in candidates:
            if len(items) >= max(1, int(max_items)):
                break
            items.append(self._record_evidence(name, kind, payload, ref, salient=salient, why_selected=why))
        return items

    def _select_long_term_memories(
        self,
        *,
        task_frame: dict[str, Any],
        timing: TimingEvidence,
        limit: int,
    ) -> list[dict[str, Any]]:
        try:
            from zerorepo.rtl_impl.rtl_memory import RTLMemorySelector, RTLMemoryStore
        except Exception:  # noqa: BLE001
            return []
        store = RTLMemoryStore.from_workspace(self.state.input.workspace_root)
        if not store.root.exists():
            return []
        context = {
            "stage": "debug",
            "module": self.state.input.module_name,
            "signals": [timing.signal] if timing.signal else [],
            "first_fail_signal": timing.signal,
            "alignment": timing.sampling_mode,
            "task_frame": task_frame,
        }
        selector = RTLMemorySelector(store, model_cfg=self.cfg, logger=self.logger)
        selected = selector.select(context, limit=max(1, int(limit)))
        return [
            {
                "path": item.path,
                "memory_id": item.header.memory_id,
                "type": item.header.type,
                "stage": item.header.stage,
                "module": item.header.module,
                "signals": item.header.signals,
                "failure_type": item.header.failure_type,
                "outcome": item.header.outcome,
                "confidence": item.header.confidence,
                "description": item.header.description,
                "patch_pattern": item.header.patch_pattern,
                "anti_trigger": item.header.anti_trigger,
                "body_excerpt": _clip(item.content, max_chars=1000),
            }
            for item in selected
        ]

    # ------------------------------------------------------------------
    # Evidence logging and pack persistence
    # ------------------------------------------------------------------

    def _record_evidence(
        self,
        tool_name: str,
        kind: str,
        payload: Any,
        artifact_ref: RawArtifactRef,
        *,
        salient: dict[str, Any] | None = None,
        why_selected: str = "",
    ) -> EvidenceItem:
        self._evidence_counter += 1
        evidence_id = f"ev_{self._evidence_counter:03d}_{_slug(tool_name)}"
        evidence_dir = self.state.journal.root / "evidence"
        evidence_dir.mkdir(parents=True, exist_ok=True)
        path = evidence_dir / f"{evidence_id}.json"
        raw_text = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
        path.write_text(raw_text + "\n", encoding="utf-8")
        summary = self._summarize_payload(tool_name, payload)
        index_row = {
            "evidence_id": evidence_id,
            "tool_name": tool_name,
            "kind": kind,
            "summary": summary,
            "path": str(path),
            "salient": salient or {},
            "raw_chars": len(raw_text),
            "visible_chars": len(summary),
        }
        self.state.journal.append_jsonl("evidence/evidence_index.jsonl", index_row)
        return EvidenceItem(
            evidence_id=evidence_id,
            kind=kind,
            summary=summary,
            artifact_ref=RawArtifactRef(
                kind=artifact_ref.kind,
                path=str(path),
                artifact_id=evidence_id,
                description=artifact_ref.description,
            ),
            why_selected=why_selected,
            salient=salient or {},
        )

    def _summarize_payload(self, tool_name: str, payload: Any) -> str:
        if isinstance(payload, dict):
            parts: list[str] = []
            for key in (
                "status",
                "mode",
                "fail_time",
                "total_mismatches",
                "top_diagnosis",
                "required_next_tool",
                "first_failure",
                "root_failure",
                "first_divergence",
                "next_local_target",
            ):
                if key in payload and payload.get(key) not in (None, "", [], {}):
                    parts.append(f"{key}={payload.get(key)}")
            if parts:
                return _clip(f"{tool_name}: " + "; ".join(parts), max_chars=900)
        text = json.dumps(payload, ensure_ascii=False, default=str)
        return _clip(f"{tool_name}: {text}", max_chars=900)

    def _persist_pack(self, pack: DebugContextPack) -> DebugContextPack:
        root = self.state.journal.root / "context_packs"
        root.mkdir(parents=True, exist_ok=True)
        idx = len(list(root.glob("pack_*.json"))) + 1
        path = root / f"pack_{idx:03d}.json"
        pack = pack.model_copy(update={"pack_path": str(path)})
        text = pack.model_dump_json(indent=2)
        path.write_text(text + "\n", encoding="utf-8")
        debug_pack_path = self.state.input.debug_workdir / "debug_context_pack.json"
        debug_pack_path.write_text(text + "\n", encoding="utf-8")
        self.state.journal.write_json("debug_context_pack.json", pack.model_dump())
        return pack

    # ------------------------------------------------------------------
    # LLM investigator subagent
    # ------------------------------------------------------------------

    def _run_investigator(
        self,
        request: DebugContextRouterInput,
        timing: TimingEvidence,
        task_frame: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Launch an LLM subagent to independently investigate and return analysis.

        The subagent receives a concise brief (goal + focus signals/blocks) and
        may call up to ``max_tool_calls`` readonly tools.  Its final response is
        treated as a plain-text analysis report and injected into the context
        pack as ``system_triage`` and ``task_frame.router_analysis``.

        Returns ``None`` when the LLM is unavailable, disabled, or fails.
        """
        cfg = self.cfg
        if cfg is None or not getattr(cfg, "api_key", ""):
            return None
        if os.environ.get("ZEROREPO_DEBUG_CONTEXT_ROUTER_LLM", "1").lower() in {"0", "false", "no", "off"}:
            return None

        self._tool_calls = 0
        toolkit = Toolkit()
        self._register_readonly_tools(toolkit)
        agent = SafeReActAgent(
            name="DebugInvestigator",
            sys_prompt=ROUTER_SYSTEM_PROMPT,
            model=make_openai_model(cfg),
            formatter=make_formatter(cfg.model, cfg.base_url),
            toolkit=toolkit,
            memory=InMemoryMemory(),
            max_iters=self.max_tool_calls,
        )
        prompt = self._investigation_prompt(request, timing, task_frame)

        async def run_agent_once() -> Msg:
            try:
                return await agent(Msg("user", prompt, role="user"))
            finally:
                await close_model_safely(agent)

        try:
            msg = self._run_async(run_agent_once())
            text = (msg.get_text_content() or "").strip()
            if not text or len(text) < 50:
                return None
            parsed = self._parse_investigator_output(text)
            if parsed is None:
                return {"analysis_text": text[:3000]}
            return parsed
        except Exception as exc:
            if self.logger is not None:
                self.logger.debug(
                    "DebugInvestigator failed for %s: %s",
                    self.state.input.module_name,
                    exc,
                )
            return None
        finally:
            clear_memory_safely(agent)

    def _parse_investigator_output(self, text: str) -> dict[str, Any] | None:
        try:
            obj = self._parse_json(text)
        except Exception:
            return None
        if not isinstance(obj, dict):
            return None
        if "system_triage" not in obj and "analysis_text" not in obj:
            return {"analysis_text": text[:3000]}
        return obj

    def _investigation_prompt(
        self,
        request: DebugContextRouterInput,
        timing: TimingEvidence,
        task_frame: dict[str, Any],
    ) -> str:
        suspect_info = ""
        if timing.block_id and timing.line_range:
            suspect_info = (
                f"Primary suspect: block {timing.block_id} "
                f"(lines {timing.line_range[0]}-{timing.line_range[1]})\n"
            )
        inp = self.state.input
        module_file_list = ""
        if inp.repair_scope == "repo" and inp.rtl_root and inp.rtl_root.exists():
            files = sorted(
                p for p in inp.rtl_root.rglob("*")
                if p.is_file() and p.suffix.lower() in {".v", ".sv"}
            )
            if files:
                lines = ["Generated module files (all are editable — investigate sub-modules before assuming they are correct):"]
                for f in files:
                    try:
                        size = f.stat().st_size
                        lines.append(f"  {f.relative_to(inp.rtl_root)}  ({size} bytes)")
                    except OSError:
                        lines.append(f"  {f.relative_to(inp.rtl_root)}")
                module_file_list = "\n".join(lines) + "\n\n"

        return (
            "Investigate this system-level RTL debug failure and return JSON.\n"
            "The top simulation/testbench is the functional oracle; localize symptoms across ALL generated modules.\n\n"
            f"{module_file_list}"
            f"Module: {inp.module_name}\n"
            f"Repair scope: {inp.repair_scope}\n"
            f"Repair mode: {inp.repair_mode}\n"
            f"First divergence: signal={timing.signal}, time={timing.time}, "
            f"ref={timing.ref}, dut={timing.dut}\n"
            f"Sampling mode: {timing.sampling_mode}, "
            f"driver: {timing.driver_assignment_kind}\n"
            f"{suspect_info}"
            f"Top trace diagnosis: {task_frame.get('top_diagnosis', '')}\n\n"
            f"Goal: {request.goal}\n"
            f"Focus signals: {request.focus_signals or 'investigate the first-divergence signal'}\n"
            f"Focus blocks: {request.focus_blocks or 'investigate the primary suspect block'}\n"
            f"Missing evidence: {request.missing_evidence or 'general investigation'}\n\n"
            "Signal cause tracing is deliberately one module and one hop at a time. Do NOT assume sub-modules are correct.\n"
            "Tool results include visible_payload with clipped RTL/spec/KG/VCD content; use that content as evidence.\n"
            "If run_check(mode=\"first_divergence\") reports missing_vcd, stop calling list_vcd_signals/probe_vcd and continue with static RTL/KG/spec triage.\n"
            f"Valid stage_artifact artifact_name values: {stage_artifact_help_text()}. Do not pass module names as artifact names.\n"
            "When an output diverges, prefer this evidence flow:\n"
            "  1. trace_signal_cause(module_name, signal_name, time) for its direct driver and boundary candidates\n"
            "  2. if a boundary candidate is causal, trace the mapped parent/child module signal in a new call\n"
            "  3. read_module_semantics only for a module that entered the suspect path\n"
            "  4. use low-level KG, VCD, source, or legacy spec tools only when the consolidated result is insufficient\n\n"
            "Call the most relevant readonly tools to gather evidence, then return exactly this JSON shape:\n"
            "{\n"
            "  \"system_triage\": {\n"
            "    \"category\": \"unknown\",\n"
            "    \"confidence\": 0.0,\n"
            "    \"symptom\": \"...\",\n"
            "    \"root_signal\": \"...\",\n"
            "    \"root_time\": 0,\n"
            "    \"suspect_modules\": [\"...\"],\n"
            "    \"suspect_files\": [\"...\"],\n"
            "    \"signal_path\": [{\"from\": \"...\", \"to\": \"...\", \"evidence\": \"...\"}],\n"
            "    \"evidence\": [\"...\"],\n"
            "    \"missing_evidence\": [\"...\"],\n"
            "    \"recommended_tool_calls\": [{\"tool\": \"query_rtl_kg\", \"args\": {}}],\n"
            "    \"patch_scope\": \"...\",\n"
            "    \"reason\": \"...\"\n"
            "  },\n"
            "  \"analysis_text\": \"concise evidence summary and next investigative step\"\n"
            "}"
        )

    def _register_readonly_tools(self, toolkit: Toolkit) -> None:
        toolkit.register_tool_function(
            self.read_context,
            json_schema=_tool_schema(
                "read_context",
                "Read repository context. Read-only.",
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
                            "Only for kind=stage_artifact. Valid values: "
                            f"{stage_artifact_help_text()}. Do not use module names."
                        ),
                    },
                    "max_chars": {"type": "integer"},
                },
                ["kind"],
            ),
        )
        toolkit.register_tool_function(
            self.search_context,
            json_schema=_tool_schema(
                "search_context",
                "Search RTL/TB/spec context. Read-only.",
                {"pattern": {"type": "string"}, "scope": {"type": "string"}, "max_results": {"type": "integer"}},
                ["pattern"],
            ),
        )
        # Legacy memory/spec readers remain callable internally for compatibility,
        # but are not part of the Router LLM tool surface.
        toolkit.register_tool_function(
            self.read_long_term_memory,
            json_schema=_tool_schema(
                "read_long_term_memory",
                "Read a selected RTL long-term memory markdown file under workspace rtl_memory. Read-only.",
                {"path": {"type": "string"}, "max_chars": {"type": "integer"}},
                ["path"],
            ),
        )
        toolkit.register_tool_function(
            self.query_rtl_kg,
            json_schema=_tool_schema(
                "query_rtl_kg",
                "Query RTL KG. Read-only.",
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
                },
                ["query_type", "module_name"],
            ),
        )
        toolkit.register_tool_function(
            self.read_module_semantics,
            json_schema=_tool_schema(
                "read_module_semantics",
                "Read consolidated Module-centred Spec/Skeleton/Plan semantics. Read-only.",
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
                            "Optional filter terms. Skeleton results use planning_block_id; "
                            "editable RTL results use rtl_block_id."
                        ),
                    },
                    "max_chars": {"type": "integer"},
                },
                ["module_name"],
            ),
        )
        toolkit.register_tool_function(
            self.trace_signal_cause,
            json_schema=_tool_schema(
                "trace_signal_cause",
                (
                    "Trace one module-local signal hop with RTL, VCD, KG drivers, and Instance/Port boundaries. "
                    "Use recommended_next_call for the preferred exact next one-hop trace. Read-only."
                ),
                {
                    "module_name": {"type": "string"},
                    "signal_name": {"type": "string"},
                    "time": {"type": ["integer", "null"]},
                    "expected_value": {"type": ["string", "null"]},
                    "max_candidates": {"type": "integer"},
                },
                ["module_name", "signal_name"],
            ),
        )
        toolkit.register_tool_function(
            self.list_vcd_signals,
            json_schema=_tool_schema(
                "list_vcd_signals",
                "List VCD signals. Read-only.",
                {"pattern": {"type": "string"}, "scope": {"type": "string"}, "limit": {"type": "integer"}},
                [],
            ),
        )
        toolkit.register_tool_function(
            self.probe_vcd,
            json_schema=_tool_schema(
                "probe_vcd",
                "Probe VCD signal values. Read-only.",
                {
                    "signals": {"type": "array", "items": {"type": "string"}},
                    "time": {"type": ["integer", "null"]},
                    "time_range": {"type": ["array", "null"], "items": {"type": "integer"}},
                    "edge": {"type": ["string", "null"]},
                    "mode": {"type": "string"},
                    "max_rows": {"type": "integer"},
                },
                ["signals"],
            ),
        )
        toolkit.register_tool_function(
            self.run_check,
            json_schema=_tool_schema(
                "run_check",
                "Run lint/sim/trace/first-divergence checks. Read-only from router perspective.",
                {
                    "mode": {"type": "string"},
                    "module_name": {"type": ["string", "null"]},
                    "signals": {"type": ["array", "null"], "items": {"type": "string"}},
                    "time_window": {"type": ["array", "null"], "items": {"type": "integer"}},
                },
                ["mode"],
            ),
        )

    def _readonly_tool_response(self, name: str, payload: dict[str, Any]) -> ToolResponse:
        status = str(payload.get("status", "ok") or "ok")
        counts_for_budget = status in {"ok", "static_only", "stable_values_match_but_tb_edge_mismatch", "no_divergence"}
        if counts_for_budget and self._tool_calls >= self.max_tool_calls:
            payload = {
                "status": "router_readonly_budget_exhausted",
                "tool_name": name,
                "tool_budget_used": self._tool_calls,
                "tool_budget_limit": self.max_tool_calls,
                "evidence_index_path": str(self.state.journal.root / "evidence" / "evidence_index.jsonl"),
            }
            counts_for_budget = False
        if counts_for_budget:
            self._tool_calls += 1
        if name == "run_check":
            first = payload.get("first_divergence") if isinstance(payload.get("first_divergence"), dict) else payload
            if isinstance(first, dict) and first.get("status") == "missing_vcd":
                self._vcd_unavailable = True
        ref = RawArtifactRef(kind="router_tool", description=f"Raw {name} result.")
        item = self._record_evidence(name, self._kind_for_tool(name, payload), payload, ref, salient={"module": self.state.input.module_name})
        raw_chars = len(json.dumps(payload, ensure_ascii=False, default=str))
        response = {
            "status": payload.get("status", "ok"),
            "tool_name": name,
            "summary": item.summary,
            "visible_payload": self._visible_payload_for_investigator(name, payload),
            "evidence_ref": {
                "path": item.artifact_ref.path,
                "artifact_id": item.artifact_ref.artifact_id,
                "kind": item.kind,
                "raw_chars": raw_chars,
            },
            "tool_budget": {
                "used": self._tool_calls,
                "limit": self.max_tool_calls,
                "exhausted": self._tool_calls >= self.max_tool_calls,
            },
        }
        text = json.dumps(response, indent=2, ensure_ascii=False)
        return ToolResponse(content=[{"type": "text", "text": text}])

    def _visible_payload_for_investigator(self, name: str, payload: dict[str, Any], max_chars: int = 7000) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {"value": _clip(str(payload), max_chars=max_chars)}
        status = payload.get("status", "ok")
        visible: dict[str, Any] = {"status": status}
        for key in ("kind", "mode", "path", "artifact_name", "start", "end", "pattern", "scope", "query_type", "source", "error"):
            if key in payload and payload.get(key) not in (None, "", [], {}):
                visible[key] = payload.get(key)

        if name in {"read_context", "read_spec", "read_long_term_memory"}:
            content = payload.get("content")
            if isinstance(content, str):
                visible["content"] = _clip(content, max_chars=max_chars)
        elif name == "read_module_semantics":
            for key in (
                "module",
                "spec_fragments",
                "skeleton_blocks",
                "plan_subtasks",
                "interface",
                "semantic_invariants",
                "editable_rtl_blocks",
                "block_alignment",
                "neighbors",
                "provenance",
                "focus_applied",
                "warnings",
                "truncated",
            ):
                if key in payload and payload.get(key) not in (None, "", [], {}):
                    visible[key] = self._clip_json(payload.get(key), max_chars=max_chars)
        elif name == "trace_signal_cause":
            for key in (
                "module",
                "signal",
                "resolved_vcd_path",
                "time",
                "observed_value",
                "expected_value",
                "rtl_path",
                "driver_candidates",
                "next_frontier",
                "frontier_candidates",
                "frontier_truncated",
                "boundary_mappings",
                "context_escalation_candidates",
                "editable_rtl_blocks",
                "focus_context",
                "recommended_next_call",
                "recommended_next_calls",
                "stop_reason",
                "warnings",
                "provenance",
            ):
                if key in payload and payload.get(key) not in (None, "", [], {}):
                    visible[key] = self._clip_json(payload.get(key), max_chars=max_chars)
        elif name == "retrieve_spec_block":
            matches = payload.get("matches")
            if isinstance(matches, list):
                visible["matches"] = self._clip_json(matches, max_chars=max_chars)
        elif name == "search_context":
            results = payload.get("results")
            if isinstance(results, list):
                visible["results"] = self._clip_json(results, max_chars=max_chars)
                visible["truncated"] = payload.get("truncated")
        elif name == "query_rtl_kg":
            visible["result"] = self._clip_json(payload.get("result"), max_chars=max_chars)
        elif name == "list_vcd_signals":
            signals = payload.get("signals")
            if isinstance(signals, list):
                visible["signals"] = signals[:100]
                visible["count"] = payload.get("count", len(signals))
                visible["truncated"] = payload.get("truncated")
        elif name == "probe_vcd":
            rows = payload.get("rows")
            if isinstance(rows, list):
                visible["rows"] = self._clip_json(rows, max_chars=max_chars)
            for key in ("signals", "time", "time_range", "mode"):
                if key in payload:
                    visible[key] = payload.get(key)
        elif name == "run_check":
            for key in (
                "mode",
                "is_pass",
                "mismatch_count",
                "first_fail_time",
                "first_divergence",
                "trace_summary",
                "sim_output_excerpt",
                "output_excerpt",
            ):
                if key in payload and payload.get(key) not in (None, "", [], {}):
                    visible[key] = self._clip_json(payload.get(key), max_chars=max_chars)
        elif name == "read_memory":
            for key in ("memory", "snapshot", "brief", "repair_ledger", "protected_invariants", "unsafe_directions"):
                if key in payload and payload.get(key) not in (None, "", [], {}):
                    visible[key] = self._clip_json(payload.get(key), max_chars=max_chars)

        if len(visible) <= 1:
            visible["payload"] = self._clip_json(payload, max_chars=max_chars)
        return visible

    def _clip_json(self, value: Any, *, max_chars: int) -> Any:
        text = json.dumps(value, ensure_ascii=False, default=str)
        clipped = _clip(text, max_chars=max_chars)
        try:
            return json.loads(clipped)
        except Exception:
            return clipped

    def _kind_for_tool(self, name: str, payload: dict[str, Any]) -> str:
        if name in {"read_spec", "retrieve_spec_block", "read_module_semantics"}:
            return "spec"
        if name in {"list_vcd_signals", "probe_vcd", "run_check", "trace_signal_cause"}:
            return "trace"
        if name == "read_memory":
            return "memory"
        return str(payload.get("kind") or "context")

    def read_context(
        self,
        kind: str,
        path: str | None = None,
        start: int | None = None,
        end: int | None = None,
        artifact_name: str | None = None,
        max_chars: int = 12000,
    ) -> ToolResponse:
        result = self.tools.read_context(kind, path, start, end, artifact_name, max_chars)  # type: ignore[arg-type]
        return self._readonly_tool_response("read_context", result)

    def search_context(self, pattern: str, scope: str = "all", max_results: int = 50) -> ToolResponse:
        result = self.tools.search_context(pattern, scope, max_results=max_results)  # type: ignore[arg-type]
        return self._readonly_tool_response("search_context", result)

    def read_memory(self, kind: str = "brief", limit: int = 5) -> ToolResponse:
        result = self.tools.read_memory(kind, limit)  # type: ignore[arg-type]
        return self._readonly_tool_response("read_memory", result)

    def read_spec(self, module_name: str | None = None, path: str | None = None, max_chars: int = 12000) -> ToolResponse:
        result = self.tools.read_spec(module_name, path, max_chars)
        return self._readonly_tool_response("read_spec", result)

    def retrieve_spec_block(
        self,
        module_name: str,
        query: str | None = None,
        block_id: str | None = None,
        max_results: int = 8,
    ) -> ToolResponse:
        result = self.tools.retrieve_spec_block(module_name, query, block_id, max_results)
        return self._readonly_tool_response("retrieve_spec_block", result)

    def read_long_term_memory(self, path: str, max_chars: int = 8000) -> ToolResponse:
        result = self.tools.read_long_term_memory(path, max_chars)
        return self._readonly_tool_response("read_long_term_memory", result)

    def query_rtl_kg(
        self,
        query_type: str,
        module_name: str,
        signal_name: str | None = None,
        instance_name: str | None = None,
    ) -> ToolResponse:
        result = self.tools.query_rtl_kg(query_type, module_name, signal_name, instance_name)  # type: ignore[arg-type]
        return self._readonly_tool_response("query_rtl_kg", result)

    def read_module_semantics(
        self,
        module_name: str,
        sections: list[str] | None = None,
        focus_signals: list[str] | None = None,
        focus_blocks: list[str] | None = None,
        max_chars: int = 12000,
    ) -> ToolResponse:
        result = self.tools.read_module_semantics(
            module_name,
            sections,
            focus_signals,
            focus_blocks,
            max_chars,
        )
        return self._readonly_tool_response("read_module_semantics", result)

    def trace_signal_cause(
        self,
        module_name: str,
        signal_name: str,
        time: int | None = None,
        expected_value: str | None = None,
        max_candidates: int = 5,
    ) -> ToolResponse:
        result = self.tools.trace_signal_cause(
            module_name,
            signal_name,
            time,
            expected_value,
            max_candidates,
        )
        return self._readonly_tool_response("trace_signal_cause", result)

    def list_vcd_signals(self, pattern: str = "", scope: str = "", limit: int = 100) -> ToolResponse:
        if self._vcd_unavailable:
            return self._readonly_tool_response(
                "list_vcd_signals",
                {
                    "status": "skipped_missing_vcd",
                    "error": "VCD was already reported missing; switch to static RTL/KG/spec triage.",
                    "suggested_tools": ["trace_signal_cause", "read_module_semantics", "read_context", "query_rtl_kg", "run_check"],
                },
            )
        result = self.tools.list_vcd_signals(pattern, scope, limit)
        return self._readonly_tool_response("list_vcd_signals", result)

    def probe_vcd(
        self,
        signals: list[str],
        time: int | None = None,
        time_range: list[int] | None = None,
        edge: str | None = None,
        mode: str = "sample",
        max_rows: int = 80,
    ) -> ToolResponse:
        if self._vcd_unavailable:
            return self._readonly_tool_response(
                "probe_vcd",
                {
                    "status": "skipped_missing_vcd",
                    "signals": signals,
                    "time": time,
                    "time_range": time_range,
                    "mode": mode,
                    "error": "VCD was already reported missing; inspect generated RTL, KG hierarchy, spec blocks, and simulator output instead.",
                    "suggested_tools": ["trace_signal_cause", "read_module_semantics", "read_context", "query_rtl_kg", "run_check"],
                },
            )
        result = self.tools.probe_vcd(signals, time, time_range, edge, mode, max_rows)
        return self._readonly_tool_response("probe_vcd", result)

    def run_check(
        self,
        mode: str,
        module_name: str | None = None,
        signals: list[str] | None = None,
        time_window: list[int] | None = None,
    ) -> ToolResponse:
        result = self.tools.run_check(mode, module_name, signals, tuple(time_window) if time_window is not None else None)  # type: ignore[arg-type]
        return self._readonly_tool_response("run_check", result)

    def _parse_json(self, text: str) -> Any:
        try:
            return json.loads(text)
        except Exception:  # noqa: BLE001
            match = re.search(r"\{.*\}", text, flags=re.DOTALL)
            if not match:
                raise
            return json.loads(match.group(0))

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


__all__ = ["DebugContextRouter"]
