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
    TimingEvidence,
)
from .tools import RepoReActTools, _clip


ROUTER_SYSTEM_PROMPT = """
You are a read-only RTL debug investigator. You work for the main RepoReAct
debug agent, which needs concise, analyzed evidence before it can safely patch RTL.

Your process:
1. Read the investigation brief (goal, focus signals, suspect blocks, missing evidence)
2. Call 3-6 targeted readonly tools to gather the most relevant evidence
3. Synthesize a short analysis report

Available tools:
- read_context(kind="lines", path, start, end) — read specific RTL line ranges
- read_context(kind="file", path) — read a whole file (use sparingly)
- read_context(kind="spec"|"testbench"|"trace_report"|"repair_journal") — read artifacts
- search_context(pattern, scope) — regex search in rtl/tb/spec/all
- probe_vcd(signals, time_range, mode="changes") — sample VCD waveform values
- list_vcd_signals(pattern) — discover available VCD signal names
- read_spec(module_name) — read the original design specification
- retrieve_spec_block(module_name, query) — find spec blocks by keyword or block_id
- query_rtl_kg(query_type, module_name, signal_name) — query the RTL knowledge graph
- run_check(mode="first_divergence") — get the first DUT/ref divergence report
- read_memory(kind="brief") — read the current session's repair memory summary
- read_long_term_memory(path) — read selected RTL long-term memory markdown

Rules:
- Be selective: call only the tools that directly address the investigation brief
- Prefer read_context(kind="lines") with specific line ranges over whole files
- When probing VCD, target the divergence time window
- Do NOT propose patches or decide repair strategies — you are an analyst only
- Return a plain-text analysis report, not JSON
- Keep the report under 3000 characters

Your report should concisely cover:
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
        "read_spec",
        "retrieve_spec_block",
        "read_long_term_memory",
        "list_vcd_signals",
        "probe_vcd",
        "run_check",
        "read_memory",
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
        self.max_tool_calls = max(1, int(max_tool_calls))
        self._tool_calls = 0
        self._evidence_counter = 0

    def route(
        self,
        *,
        goal: DebugContextGoal = "initial_triage",
        focus_signals: list[str] | None = None,
        focus_blocks: list[str] | None = None,
        missing_evidence: list[str] | None = None,
        max_items: int = 5,
    ) -> dict[str, Any]:
        request = DebugContextRouterInput(
            goal=goal,
            focus_signals=focus_signals or [],
            focus_blocks=focus_blocks or [],
            missing_evidence=missing_evidence or [],
            max_items=max(1, min(int(max_items), 10)),
        )
        pack = self._fallback_pack(request, reason="")

        # When the main agent supplies focus parameters, launch the LLM
        # investigator subagent.  It calls 3-6 targeted readonly tools and
        # returns a plain-text analysis that we inject into the pack.
        # Falls back to deterministic targeted evidence when the LLM is
        # unavailable (no API key, explicitly disabled, or call fails).
        if request.focus_signals or request.focus_blocks or request.missing_evidence:
            timing = pack.timing_evidence
            analysis = self._run_investigator(request, timing, pack.task_frame)
            if analysis:
                pack.task_frame["router_analysis"] = analysis
                pack.fallback_used = False
                pack.fallback_reason = ""
            else:
                # LLM unavailable — use deterministic targeted evidence
                det = self._gather_targeted_evidence(request, timing)
                if det:
                    pack.task_frame["router_analysis"] = det

        return self._persist_pack(pack).model_dump()

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

        # 2. focus_signals → probe VCD around divergence time
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

        # 3. missing_evidence mentions "spec" → retrieve matching spec blocks
        if request.missing_evidence and any(
            "spec" in m.lower() for m in request.missing_evidence
        ):
            try:
                query = timing.signal if timing.signal else ""
                result = self.tools.retrieve_spec_block(
                    module_name=self.state.input.module_name,
                    query=query,
                    max_results=3,
                )
                matches = result.get("matches") if isinstance(result, dict) else []
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
        active_working_set = self._active_working_set(
            trace=trace,
            divergence=divergence,
            brief=brief,
            timing=timing,
            evidence=evidence,
            causal_memory=causal_memory,
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
            fallback_used=True,
            fallback_reason=reason or "deterministic_debug_context_router",
        )

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
        if self.state.input.repair_mode == "functional" and not self.state.observed_spec_or_stage:
            missing_evidence.append("Read original spec or relevant stage artifact before functional edit.")
        if self.state.input.repair_mode == "functional" and not self.state.observed_real_divergence:
            missing_evidence.append('Call run_check(mode="first_divergence") before functional edit.')
        next_edit_candidates = []
        if timing.block_id:
            next_edit_candidates.append(
                {
                    "block_id": timing.block_id,
                    "line_range": timing.line_range,
                    "signals": [timing.signal] if timing.signal else [],
                    "reason": "Primary driver/suspect block for current failure.",
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
            "next_edit_candidates": next_edit_candidates[:3],
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
                "content": item.content,
                "body_excerpt": _clip(item.content, max_chars=2400),
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
    ) -> str | None:
        """Launch an LLM subagent to independently investigate and return analysis.

        The subagent receives a concise brief (goal + focus signals/blocks) and
        may call up to ``max_tool_calls`` readonly tools.  Its final response is
        treated as a plain-text analysis report and injected into the context
        pack as ``task_frame.router_analysis``.

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
            return text[:3000]
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
        return (
            "Investigate this RTL debug failure and return a concise analysis.\n\n"
            f"Module: {self.state.input.module_name}\n"
            f"Repair mode: {self.state.input.repair_mode}\n"
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
            "Call the most relevant readonly tools to gather evidence, "
            "then return your analysis as plain text."
        )

    def _register_readonly_tools(self, toolkit: Toolkit) -> None:
        toolkit.register_tool_function(
            self.read_context,
            json_schema=_tool_schema(
                "read_context",
                "Read repository context. Read-only.",
                {
                    "kind": {"type": "string"},
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
                "Search RTL/TB/spec context. Read-only.",
                {"pattern": {"type": "string"}, "scope": {"type": "string"}, "max_results": {"type": "integer"}},
                ["pattern"],
            ),
        )
        toolkit.register_tool_function(
            self.read_memory,
            json_schema=_tool_schema("read_memory", "Read repair memory. Read-only.", {"kind": {"type": "string"}, "limit": {"type": "integer"}}, []),
        )
        toolkit.register_tool_function(
            self.read_spec,
            json_schema=_tool_schema(
                "read_spec",
                "Read original spec or module spec excerpt. Read-only.",
                {"module_name": {"type": ["string", "null"]}, "path": {"type": ["string", "null"]}, "max_chars": {"type": "integer"}},
                [],
            ),
        )
        toolkit.register_tool_function(
            self.retrieve_spec_block,
            json_schema=_tool_schema(
                "retrieve_spec_block",
                "Retrieve spec blocks by module/query/id. Read-only.",
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
                    "query_type": {"type": "string"},
                    "module_name": {"type": "string"},
                    "signal_name": {"type": ["string", "null"]},
                    "instance_name": {"type": ["string", "null"]},
                },
                ["query_type", "module_name"],
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
        self._tool_calls += 1
        if self._tool_calls > self.max_tool_calls:
            payload = {"status": "router_readonly_budget_exhausted", "tool_name": name}
        ref = RawArtifactRef(kind="router_tool", description=f"Raw {name} result.")
        item = self._record_evidence(name, self._kind_for_tool(name, payload), payload, ref, salient={"module": self.state.input.module_name})
        text = json.dumps({"status": payload.get("status", "ok"), "evidence": item.model_dump()}, indent=2, ensure_ascii=False)
        return ToolResponse(content=[{"type": "text", "text": text}])

    def _kind_for_tool(self, name: str, payload: dict[str, Any]) -> str:
        if name in {"read_spec", "retrieve_spec_block"}:
            return "spec"
        if name in {"list_vcd_signals", "probe_vcd", "run_check"}:
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

    def list_vcd_signals(self, pattern: str = "", scope: str = "", limit: int = 100) -> ToolResponse:
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
