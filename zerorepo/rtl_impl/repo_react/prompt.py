from __future__ import annotations

import json
from typing import Any


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
9. Before patching, inspect read_memory failed_directions/promising_directions and avoid repeating failed ideas unless new evidence distinguishes the attempt.
10. If root cause is unclear, use list_vcd_signals/probe_vcd to inspect waveform evidence before patching.
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
) -> str:
    return (
        "Begin repository-level RTL repair.\n\n"
        f"<module_name>\n{module_name}\n</module_name>\n\n"
        f"<repair_mode>\n{repair_mode}\n</repair_mode>\n\n"
        f"<current_debug_rtl_path>\n{rtl_path}\n</current_debug_rtl_path>\n\n"
        f"<merged_rtl_path>\n{merged_file}\n</merged_rtl_path>\n\n"
        "<source_of_truth>\n"
        "The visible testbench and original module specification are authoritative for this repair session.\n"
        "</source_of_truth>\n\n"
        "<spec_excerpt>\n"
        f"{spec_text[:6000]}\n"
        "</spec_excerpt>\n\n"
        "<contract_json_diagnostic_only>\n"
        f"{contract_json[:6000]}\n"
        "</contract_json_diagnostic_only>\n\n"
        "<initial_sim_failure_excerpt>\n"
        f"{sim_failed_excerpt}\n"
        "</initial_sim_failure_excerpt>\n\n"
        "<initial_trace_summary_json>\n"
        f"{json.dumps(trace_summary, indent=2, ensure_ascii=False)}\n"
        "</initial_trace_summary_json>\n\n"
        "<known_planning_corrections_json>\n"
        f"{json.dumps(corrections, indent=2, ensure_ascii=False)}\n"
        "</known_planning_corrections_json>\n\n"
        "<repo_react_memory_brief_json>\n"
        f"{json.dumps(memory_snapshot, indent=2, ensure_ascii=False)}\n"
        "</repo_react_memory_brief_json>\n\n"
        "Start by observing with read_context, read_spec, retrieve_spec_block, search_context, "
        "query_rtl_kg, run_check, read_memory, list_vcd_signals, or probe_vcd. "
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
) -> str:
    pressure = (
        "ACTION PRESSURE: You have used many observation tools since the last write action. "
        "Your next step should be apply_patch, replace_block, record_correction, or generate_response unless one specific missing fact remains."
        if readonly_calls_since_action >= max(1, max_readonly_calls - 2)
        else "Observation is allowed, but keep it targeted."
    )
    return (
        "Continue repository-level RTL repair.\n\n"
        "<repo_react_memory_brief_json>\n"
        f"{json.dumps(memory_summary, indent=2, ensure_ascii=False)}\n"
        "</repo_react_memory_brief_json>\n\n"
        f"<observation_budget>{readonly_calls_since_action}/{max_readonly_calls}</observation_budget>\n"
        f"{pressure}\n\n"
        "Use read_context/read_spec/retrieve_spec_block/search_context/query_rtl_kg/run_check/read_memory/list_vcd_signals/probe_vcd only for missing evidence.\n"
        "If you only have waveform evidence, read spec or a relevant stage artifact before editing.\n"
        "If functional repair has not observed first_divergence yet, call run_check(mode=\"first_divergence\") before any apply_patch or replace_block.\n"
        "Check causal memory before patching; do not repeat unsafe_directions unless new evidence distinguishes the attempt.\n"
        "If an edit touches protected signals or high-coupling blocks, include protected_invariants_checked and preserve_plan in the write tool call.\n"
        "Edit-scope policy: after collecting enough evidence, decide the repair scope yourself from the root cause. Use apply_patch for line or region edits, including coordinated multi-range edits. Use replace_block when the complete always/assign block is the natural semantic unit. Do not distort patch size for its own sake; make it coherent, evidence-backed, and preserve already-improved behavior. Record_correction if upstream planning is wrong.\n"
        "If you cannot make a safe edit now, call generate_response(response=\"...brief summary...\")."
    )


def build_compact_prompt(snapshot: dict[str, Any]) -> str:
    return (
        "Compact checkpoint. Do not rely on prior chat history; the JSON below is a compact "
        "RepoReAct memory brief. Full journals and trace reports remain available through tools.\n\n"
        "<repo_react_memory_brief_json>\n"
        f"{json.dumps(snapshot, indent=2, ensure_ascii=False)}\n"
        "</repo_react_memory_brief_json>\n\n"
        "Next-step rules:\n"
        "1. Use next_local_target, repair_ledger, protected_invariants, and unsafe_directions as current progress memory.\n"
        "2. Read current RTL/spec/stage artifact/testbench/KG/VCD evidence as needed before patching.\n"
        "3. Do not retry unsafe_directions unless new evidence distinguishes the attempt.\n"
        "4. Choose edit scope from the evidence and diagnosis, not from a default preference for narrow or broad patches.\n"
        "5. Make one coherent evidence-backed apply_patch, replace_block, or record a planning correction.\n"
        "6. If root cause is unclear, inspect waveform signals with list_vcd_signals/probe_vcd, then connect it back to spec or planning intent."
    )
