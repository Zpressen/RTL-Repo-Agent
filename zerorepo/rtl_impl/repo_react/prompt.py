from __future__ import annotations

import json
from typing import Any


def _take_list(value: Any, limit: int) -> list[Any]:
    if not isinstance(value, list):
        return []
    return value[: max(0, int(limit))]


def _clip_text(value: Any, max_chars: int) -> str:
    text = value if isinstance(value, str) else str(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...<snip>..."


def _compact_long_term_memories(value: Any, *, limit: int = 3, body_chars: int = 1800) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    compact: list[dict[str, Any]] = []
    for item in value[: max(0, int(limit))]:
        if not isinstance(item, dict):
            continue
        compact.append(
            {
                "path": item.get("path"),
                "memory_id": item.get("memory_id"),
                "type": item.get("type"),
                "stage": item.get("stage"),
                "module": item.get("module"),
                "signals": item.get("signals") or [],
                "failure_type": item.get("failure_type"),
                "outcome": item.get("outcome"),
                "confidence": item.get("confidence"),
                "description": item.get("description"),
                "patch_pattern": item.get("patch_pattern"),
                "anti_trigger": item.get("anti_trigger"),
                "content": item.get("content") or item.get("body_excerpt") or "",
                "body_excerpt": _clip_text(item.get("body_excerpt") or item.get("content") or "", body_chars),
            }
        )
    return compact


def _compact_causal_memory(pack: dict[str, Any]) -> dict[str, Any]:
    causal = pack.get("causal_memory") if isinstance(pack.get("causal_memory"), dict) else {}
    task_frame = pack.get("task_frame") if isinstance(pack.get("task_frame"), dict) else {}

    return {
        "repair_ledger_summary": _take_list(causal.get("repair_ledger_summary"), 5),
        "promising_directions": _take_list(causal.get("promising_directions"), 5),
        "protected_invariants": _take_list(
            causal.get("protected_invariants") or task_frame.get("protected_invariants"),
            8,
        ),
        "unsafe_directions": _take_list(
            causal.get("unsafe_directions") or task_frame.get("unsafe_directions"),
            8,
        ),
        "selected_long_term_memories": _compact_long_term_memories(
            causal.get("selected_long_term_memories"),
            limit=5,
            body_chars=1800,
        ),
        "negative_patterns": _compact_long_term_memories(
            causal.get("negative_patterns"),
            limit=3,
            body_chars=1200,
        ),
    }


def _compact_active_working_set(pack: dict[str, Any], *, mode: str = "checkpoint") -> dict[str, Any]:
    working = pack.get("active_working_set") if isinstance(pack.get("active_working_set"), dict) else {}
    if not working:
        return {}
    deep = mode == "deep"
    hyp_limit = 2 if deep else 5
    evidence_limit = 3 if deep else 5
    patch_limit = 5
    return {
        "current_failure": working.get("current_failure") or {},
        "active_hypotheses": _take_list(working.get("active_hypotheses"), hyp_limit),
        "pinned_evidence": _take_list(working.get("pinned_evidence"), evidence_limit),
        "pinned_code_slices": _take_list(working.get("pinned_code_slices"), 2 if deep else 3),
        "pinned_spec_clauses": _take_list(working.get("pinned_spec_clauses"), 2 if deep else 3),
        "waveform_facts": _take_list(working.get("waveform_facts"), 3 if deep else 5),
        "accepted_patch_summaries": _take_list(working.get("accepted_patch_summaries"), patch_limit),
        "rejected_hypotheses": _take_list(working.get("rejected_hypotheses"), 3 if deep else 5),
        "next_edit_candidates": _take_list(working.get("next_edit_candidates"), 2 if deep else 3),
        "missing_evidence": _take_list(working.get("missing_evidence"), 5),
        "protected_invariants": _take_list(working.get("protected_invariants"), 8),
        "unsafe_directions": _take_list(working.get("unsafe_directions"), 8),
        "selected_long_term_memories": _compact_long_term_memories(
            working.get("selected_long_term_memories"),
            limit=3 if deep else 5,
            body_chars=1200 if deep else 1800,
        ),
    }


def _pack_summary_json(pack: dict[str, Any], *, mode: str = "checkpoint") -> str:
    task_frame = pack.get("task_frame") if isinstance(pack.get("task_frame"), dict) else {}
    timing = pack.get("timing_evidence") if isinstance(pack.get("timing_evidence"), dict) else {}
    evidence = pack.get("evidence_pack") if isinstance(pack.get("evidence_pack"), list) else []
    causal_memory = _compact_causal_memory(pack)
    working_set = _compact_active_working_set(pack, mode=mode)
    evidence_limit = 0 if mode == "deep" else 5
    return json.dumps(
        {
            "task_frame": task_frame,
            "timing_evidence": timing,
            "active_working_set": working_set,
            "evidence_pack": evidence[:evidence_limit],
            "causal_memory_summary": causal_memory,
        },
        indent=2,
        ensure_ascii=False,
    )


SYSTEM_PROMPT = """
You are a repository-level RTL repair agent.

Your goal is to repair the generated RTL repository against the fixed RealBench oracle.
Work like a code agent: inspect repository files, stage artifacts, testbench behavior,
trace reports, simulation logs, VCD waveform data, memory, and RTL KG facts before changing code.

Rules:
1. You may only modify RTL through apply_patch or replace_block.
2. You may only record planning overlays through record_correction.
3. Never modify specifications, oracle files, testbenches, RealBench files, or original stage artifacts.
4. Stage artifacts are hypotheses. If they conflict with spec, testbench, trace, waveform, or RTL, record a correction.
5. Before apply_patch or replace_block, gather evidence from current RTL and simulation/trace, plus at least one of testbench, KG, or spec.
6. For cross-module edits, inspect parent/child interface using query_rtl_kg or search_context first.
7. Before every patch, write a concise causal diagnosis.
8. After gathering enough evidence, choose the edit scope that matches your diagnosis. Do not prefer narrow or broad edits by default; use a line patch, multi-region patch, or replace_block according to the actual root cause.
9. Before patching, inspect the task_frame and causal_memory in the latest context pack. Avoid unsafe_directions unless new evidence distinguishes the attempt, and build on promising directions.
10. Use route_debug_context as your primary observation tool. It launches an investigator subagent that calls 3-6 targeted tools and returns a concise analysis in router_analysis — read that field first. Call it with specific focus_signals, focus_blocks, and missing_evidence to get pre-analyzed evidence (RTL lines with line numbers, VCD signal values at the divergence time, matching spec blocks) in one compact response. Raw tools (read_context/search_context/probe_vcd) are only for following up on a specific artifact the investigator's analysis explicitly cites.
11. Treat errors_*, errortime_*, stats*, and tb_match* as testbench metrics, not root-cause RTL signals.
12. In functional repair mode, before apply_patch or replace_block you must call run_check(mode="first_divergence") and cite the real DUT/ref divergence.
13. If trace_summary returns required_next_tool, call that tool before patching.
14. If first_divergence.status is stable_values_match_but_tb_edge_mismatch, prioritize active-region sampling, blocking/nonblocking assignment semantics, #1 delays, and output always block behavior.
15. Use replace_block whenever a complete always/assign block is the natural repair unit, including wrong default/hold behavior, decode structure, blocking/nonblocking timing, reset policy, or mutually-coupled register updates. Cite the block_id, spec/stage intent, real divergence evidence, and preservation plan.
16. Functional patches must be grounded in requirements: read_spec, retrieve_spec_block, or read_context(stage_artifact) before editing.
17. Do not rely on waveform alone. Use waveform to localize, then use spec/stage artifacts/reference semantics to decide intent.
18. Before patching, inspect causal memory: protected_invariants, unsafe_directions, repair_ledger, and next_local_target.
19. If your edit may affect a protected signal or high-coupling block, pass protected_invariants_checked and preserve_plan to apply_patch/replace_block.
20. Do not repeat unsafe_directions unless new evidence clearly distinguishes the attempt.
21. route_debug_context returns pre-analyzed evidence (VCD around divergence time, suspect block RTL, matching spec blocks) in one compact response. Always call it first when you need new context. Never call multiple raw tools when one router call with the right focus parameters would return the same evidence.

Every reasoning step should include this JSON shape before taking an action:
{
  "failure_type": "timing_bug | local_logic_bug | interface_bug | plan_bug | unknown",
  "suspected_module": "...",
  "suspected_files": ["..."],
  "suspected_signals": ["..."],
  "root_signal": "...",
  "first_divergence_time": 0,
  "ref_value": "...",
  "dut_value": "...",
  "divergence_class": "dut_late | dut_early | wrong_value | unknown",
  "evidence_summary": ["...", "..."],
  "protected_invariants_checked": ["..."],
  "preserve_plan": "...",
  "next_action": "patch | replace_block | read_more | record_correction | stop"
}

When the design passes or you cannot make progress, finish by calling:
generate_response(response="...brief summary...")
The response argument must be a plain string.
"""


def build_initial_prompt(
    *,
    module_name: str,
    repair_mode: str,
    rtl_path: str,
    merged_file: str,
    spec_text: str,
    contract_json: str,
    sim_failed_excerpt: str,
    trace_summary: dict[str, Any],
    corrections: list[dict[str, Any]],
    memory_snapshot: dict[str, Any],
    context_pack: dict[str, Any] | None = None,
) -> str:
    del spec_text, contract_json, corrections, memory_snapshot
    pack = context_pack or {}
    raw_artifacts = pack.get("raw_artifacts") if isinstance(pack.get("raw_artifacts"), dict) else {}
    task_frame = pack.get("task_frame") if isinstance(pack.get("task_frame"), dict) else {}
    timing = pack.get("timing_evidence") if isinstance(pack.get("timing_evidence"), dict) else {}
    evidence = pack.get("evidence_pack") if isinstance(pack.get("evidence_pack"), list) else []
    causal_memory = _compact_causal_memory(pack)
    working_set = _compact_active_working_set(pack)
    return (
        "Begin repository-level RTL repair.\n\n"
        f"<module_name>\n{module_name}\n</module_name>\n\n"
        f"<repair_mode>\n{repair_mode}\n</repair_mode>\n\n"
        f"<current_debug_rtl_path>\n{rtl_path}\n</current_debug_rtl_path>\n\n"
        f"<merged_rtl_path>\n{merged_file}\n</merged_rtl_path>\n\n"
        "<source_of_truth>\n"
        "The visible testbench and original module specification are authoritative for this repair session.\n"
        "</source_of_truth>\n\n"
        "<context_pack_path>\n"
        f"{pack.get('pack_path') or ''}\n"
        "</context_pack_path>\n\n"
        "<debug_context_pack_summary_json>\n"
        f"{json.dumps({'task_frame': task_frame, 'timing_evidence': timing, 'active_working_set': working_set, 'evidence_pack': evidence[:5], 'causal_memory_summary': causal_memory}, indent=2, ensure_ascii=False)}\n"
        "</debug_context_pack_summary_json>\n\n"
        "<raw_artifact_refs_json>\n"
        f"{json.dumps(raw_artifacts, indent=2, ensure_ascii=False)}\n"
        "</raw_artifact_refs_json>\n\n"
        "<initial_sim_failure_excerpt>\n"
        f"{sim_failed_excerpt}\n"
        "</initial_sim_failure_excerpt>\n\n"
        "<initial_trace_summary_json>\n"
        f"{json.dumps(trace_summary, indent=2, ensure_ascii=False)}\n"
        "</initial_trace_summary_json>\n\n"
        "Start from the debug_context_pack_summary_json. If anything important is missing, call "
        "route_debug_context with focused parameters — it returns pre-analyzed evidence from "
        "multiple sources in one compact response.\n"
        "Example: route_debug_context(goal=\"before_patch\", focus_signals=[\"NORMAL_INT_REG\"], "
        "focus_blocks=[\"A6\"], missing_evidence=[\"spec requirement for card detect\"]) → returns "
        "analyzed VCD around the divergence time + suspect block RTL + relevant spec block — "
        "enough to form a causal diagnosis in one call.\n"
        "Selected long-term memories include the full selected markdown content in the context pack; call read_long_term_memory(path) only when you need to re-open a memory file from disk. "
        "Use read_context, search_context, list_vcd_signals, or probe_vcd only as precise follow-up "
        "after the router pack identifies a cited artifact or missing fact. "
        "read_spec, retrieve_spec_block, query_rtl_kg, and run_check remain available when the evidence gate specifically requires them. "
        "In functional repair, first establish semantic intent with read_spec/retrieve_spec_block or a relevant stage_artifact, "
        "then localize with trace/VCD. "
        "For functional repair, run run_check(mode=\"first_divergence\") before apply_patch/replace_block and use "
        "the returned real DUT/ref output mismatch as the root evidence. "
        "If it returns stable_values_match_but_tb_edge_mismatch, reason about active-region edge sampling and blocking/nonblocking behavior. "
        "Patch only after you have enough evidence. Choose the edit scope from the diagnosis: a single-line edit, several coordinated line ranges, "
        "or a complete always/assign replacement are all acceptable when they directly fit the root cause. Do not split a coherent semantic fix merely to reduce patch size. If causal memory lists protected_invariants or unsafe_directions, "
        "explicitly check them and include protected_invariants_checked/preserve_plan in write-tool arguments when relevant. "
        "In syntax repair mode, focus on lint errors, "
        "support.sv interfaces, missing macros, declarations, and Verilator diagnostics; lint pass is the success condition."
    )


def build_continue_prompt(
    *,
    memory_summary: dict[str, Any],
    readonly_calls_since_action: int,
    max_readonly_calls: int,
    context_pack: dict[str, Any] | None = None,
) -> str:
    del memory_summary
    pack = context_pack or {}
    task_frame = pack.get("task_frame") if isinstance(pack.get("task_frame"), dict) else {}
    timing = pack.get("timing_evidence") if isinstance(pack.get("timing_evidence"), dict) else {}
    evidence = pack.get("evidence_pack") if isinstance(pack.get("evidence_pack"), list) else []
    causal_memory = _compact_causal_memory(pack)
    working_set = _compact_active_working_set(pack)
    pressure = (
        "ACTION PRESSURE: You have used many observation tools since the last write action. "
        "Your next step should be apply_patch, replace_block, record_correction, or generate_response unless one specific missing fact remains."
        if readonly_calls_since_action >= max(1, max_readonly_calls - 2)
        else "Observation is allowed, but keep it targeted."
    )
    return (
        "Continue repository-level RTL repair.\n\n"
        "<context_pack_path>\n"
        f"{pack.get('pack_path') or ''}\n"
        "</context_pack_path>\n\n"
        "<debug_context_pack_summary_json>\n"
        f"{json.dumps({'task_frame': task_frame, 'timing_evidence': timing, 'active_working_set': working_set, 'evidence_pack': evidence[:5], 'causal_memory_summary': causal_memory}, indent=2, ensure_ascii=False)}\n"
        "</debug_context_pack_summary_json>\n\n"
        f"<observation_budget>{readonly_calls_since_action}/{max_readonly_calls}</observation_budget>\n"
        f"{pressure}\n\n"
        "Use route_debug_context first for missing broad context; selected_long_term_memories already include full selected memory content. Use read_long_term_memory only to re-open a memory file, or read_context/search_context/list_vcd_signals/probe_vcd as precise cited follow-up. Use read_spec/retrieve_spec_block/query_rtl_kg/run_check when the evidence gate specifically requires them.\n"
        "If you only have waveform evidence, read spec or a relevant stage artifact before editing.\n"
        "If functional repair has not observed first_divergence yet, call run_check(mode=\"first_divergence\") before any apply_patch or replace_block.\n"
        "Check causal memory before patching; do not repeat unsafe_directions unless new evidence distinguishes the attempt.\n"
        "If an edit touches protected signals or high-coupling blocks, include protected_invariants_checked and preserve_plan in the write tool call.\n"
        "Edit-scope policy: after collecting enough evidence, decide the repair scope yourself from the root cause. Use apply_patch for line or region edits, including coordinated multi-range edits. Use replace_block when the complete always/assign block is the natural semantic unit. Do not distort patch size for its own sake; make it coherent, evidence-backed, and preserve already-improved behavior. Record_correction if upstream planning is wrong.\n"
        "If you cannot make a safe edit now, call generate_response(response=\"...brief summary...\")."
    )


def build_compact_prompt(snapshot: dict[str, Any], mode: str = "checkpoint") -> str:
    compact_mode = "deep" if mode == "deep" else "checkpoint"
    title = "Deep compact checkpoint" if compact_mode == "deep" else "Compact checkpoint"
    return (
        f"{title}. Do not rely on prior chat history; the JSON below is the latest "
        "debug context pack summary. Full journals, trace reports, evidence files, and memory files remain available through tools.\n\n"
        "<context_pack_path>\n"
        f"{snapshot.get('pack_path') or ''}\n"
        "</context_pack_path>\n\n"
        "<debug_context_pack_summary_json>\n"
        f"{_pack_summary_json(snapshot, mode=compact_mode)}\n"
        "</debug_context_pack_summary_json>\n\n"
        "Next-step rules:\n"
        "1. Use task_frame, timing_evidence, evidence_pack, and causal_memory_summary as current progress memory.\n"
        "2. selected_long_term_memories already include full selected memory content; call read_long_term_memory(path) only to re-open a memory file. If other context is missing, call route_debug_context before broad direct reads; read current RTL/spec/stage artifact/testbench/KG/VCD evidence only as precise follow-up before patching.\n"
        "3. Do not retry unsafe_directions unless new evidence distinguishes the attempt.\n"
        "4. Choose edit scope from the evidence and diagnosis, not from a default preference for narrow or broad patches.\n"
        "5. Call route_debug_context when you need a short fresh pack before deciding what to read next.\n"
        "6. Make one coherent evidence-backed apply_patch, replace_block, or record a planning correction."
    )
