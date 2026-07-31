from __future__ import annotations

import json
from typing import Any

from .tools import stage_artifact_help, stage_artifact_help_text


def _take_list(value: Any, limit: int) -> list[Any]:
    if not isinstance(value, list):
        return []
    return value[: max(0, int(limit))]


def _clip_text(value: Any, max_chars: int) -> str:
    text = value if isinstance(value, str) else str(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...<snip>..."


def _compact_long_term_memories(value: Any, *, limit: int = 3, body_chars: int = 1000) -> list[dict[str, Any]]:
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
            limit=3,
            body_chars=1000,
        ),
        "negative_patterns": _compact_long_term_memories(
            causal.get("negative_patterns"),
            limit=2,
            body_chars=800,
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
            limit=3,
            body_chars=800 if deep else 1000,
        ),
    }


def _pack_summary_json(pack: dict[str, Any], *, mode: str = "checkpoint") -> str:
    task_frame = pack.get("task_frame") if isinstance(pack.get("task_frame"), dict) else {}
    timing = pack.get("timing_evidence") if isinstance(pack.get("timing_evidence"), dict) else {}
    system_triage = pack.get("system_triage") if isinstance(pack.get("system_triage"), dict) else {}
    evidence = pack.get("evidence_pack") if isinstance(pack.get("evidence_pack"), list) else []
    causal_memory = _compact_causal_memory(pack)
    working_set = _compact_active_working_set(pack, mode=mode)
    evidence_limit = 0 if mode == "deep" else 5
    return json.dumps(
        {
            "task_frame": task_frame,
            "system_triage": system_triage,
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

Your goal is to repair the generated RTL repository against the fixed system-level RealBench oracle.
This is a system-level debug task: the top testbench and top simulation are executable functional evidence,
but the visible testbench is not an exhaustive specification. Individual generated modules may differ from
an official module-level implementation only while remaining specification-equivalent for all legal inputs,
keys, states, and transaction sequences.
Work like a repair agent: inspect what you need, patch when you have a plausible localized causal repair, and use lint/simulation feedback to continue.

Rules:
1. You may only modify RTL through apply_patch or replace_block.
2. You may only record planning overlays through record_correction.
3. Never modify specifications, oracle files, testbenches, RealBench files, or original stage artifacts.
4. Stage artifacts are hypotheses. If they conflict with spec, testbench, trace, waveform, or RTL, record a correction.

5. For cross-module edits, use KG, source search, RTL reads, VCD probes, or spec reads as needed; you may also make one coherent multi-file patch when the diagnosis spans files.
6. Before every patch, write a concise plausible causal patch rationale. Do not wait for complete proof when evidence supports a small reversible repair; apply_patch/replace_block will verify and roll back regressions.
7. Choose the edit scope that matches your patch rationale. Do not prefer narrow or broad edits by default; use a line patch, multi-region patch, multi-file apply_patch, or replace_block according to the actual root cause.
8. Any injected DebugContextRouter context pack is advisory and must not override trace, simulation, spec, or RTL evidence.
9. Treat errors_*, errortime_*, stats*, and tb_match* as testbench metrics, not root-cause RTL signals.
10. If initial_trace_summary_json returns required_next_tool="trace_signal_cause", call it first with the exact supplied arguments. read_context and probe_vcd remain unavailable until that successful one-hop trace completes.
11. If first_divergence.status is stable_values_match_but_tb_edge_mismatch, prioritize active-region sampling, blocking/nonblocking assignment semantics, #1 delays, and output always block behavior.
12. Use replace_block whenever a complete always/assign block is the natural repair unit, including wrong default/hold behavior, decode structure, blocking/nonblocking timing, reset policy, or mutually-coupled register updates.
13. Causal memory is advisory. Use it to avoid repeating bad directions, but decide based on current evidence.
14. Do not repeat unsafe_directions unless new evidence clearly distinguishes the attempt.
15. You may call any read/debug tool when it helps your diagnosis; keep reads purposeful.
16. Stage artifact names are not module names. Valid read_context(kind="stage_artifact") artifact_name values are: {stage_artifacts}. Use read_module_semantics for module Spec/Skeleton/Plan; prefer stage6_merge, repo_skeleton, contracts, and modules for repository-level evidence.
17. In repo repair scope, suspect files may be child RTL files as well as the top RTL. Use the hierarchy only as evidence, not as a hard constraint.
18. After a patch, use the returned lint/simulation result to decide whether to continue, inspect more, or patch again.
19. If a patch returns syntax_retry_required, correct only that candidate's syntax and call the same action type and target again with syntax_retry_of set to its candidate_id. Syntax retries are not semantic repair failures and do not consume the functional repair budget until lint passes.
20. After the required initial one-hop trace, use read_module_semantics for consolidated Spec/Skeleton/Plan intent and use read_context or probe_vcd only for evidence the trace did not already provide. Follow Instance/Port boundary candidates one module at a time, and load parent/child semantics only after evidence implicates that module.
21. If a functional patch returns neutral with required_next_tool=trace_signal_cause, preserve the committed patch and complete that exact one-hop retrace before attempting another apply_patch or replace_block.
22. Tool calls must use the native function-call interface. Never print DSML, XML, <tool_call>, or <invoke> markup to simulate a tool call.
23. replace_block requires module_name plus an rtl_block_id returned by editable_rtl_blocks. ModuleSkeleton ids such as B1/B2/B5 are planning_block_id values and must never be passed as an edit target.
24. Expected/reference values from a testbench, mismatch report, trace, VCD, or repair memory are diagnostic evidence only. Never copy an observed value into RTL as a functional output or state constant, patch RHS, or special case for an observed input, time, FSM state, counter value, or failure location.
25. Functional outputs and state must remain derived from legal inputs, internal state, parameters, or specification-defined algorithmic constants. Passing the visible simulation is necessary but not sufficient; the repair must generalize to other legal vectors.
26. New functional constants are allowed only when required by the specification or algorithm, such as reset values, protocol encodings, AES S-box/Rcon entries, masks, or polynomials. The patch rationale must identify the source. A value seen only in the oracle is not specification evidence.
27. Never reuse concrete data literals from repair memory; reuse only structural or causal patterns. A lower mismatch count alone does not validate hardcoded or input-independent behavior.

Every reasoning step should include this JSON shape before taking an action:
{
  "failure_type": "timing_bug | local_logic_bug | interface_bug | plan_bug | unknown",
  "suspected_module": "...",
  "suspected_files": ["..."],
  "suspected_signals": ["..."],
  "data_path_verified": [
    {"signal": "...", "driver_module": "...", "verified": true, "how": "..."},
    {"signal": "...", "driver_module": "...", "verified": false, "reason": "not yet inspected"}
  ],
  "root_signal": "...",
  "first_divergence_time": 0,
  "ref_value": "...",
  "dut_value": "...",
  "divergence_class": "dut_late | dut_early | wrong_value | unknown",
  "evidence_summary": ["...", "..."],
  "generalization_check": {
    "new_functional_constants": [{"literal": "...", "spec_source": "..."}],
    "output_state_dependencies": ["legal input/state/parameter names"],
    "varies_with_legal_inputs": true,
    "uses_observed_expected_value": false
  },
  "next_action": "patch | replace_block | read_more | record_correction | stop"
}

When the design passes or you cannot make progress, finish by calling:
generate_response(response="...brief summary...")
	The response argument must be a plain string.
	""".replace("{stage_artifacts}", stage_artifact_help_text())


def build_initial_prompt(
    *,
    module_name: str,
    runtime_top_module: str = "",
    dut_instance: str = "",
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
    artifact_help = stage_artifact_help()
    raw_artifacts = pack.get("raw_artifacts") if isinstance(pack.get("raw_artifacts"), dict) else {}
    task_frame = pack.get("task_frame") if isinstance(pack.get("task_frame"), dict) else {}
    system_triage = pack.get("system_triage") if isinstance(pack.get("system_triage"), dict) else {}
    timing = pack.get("timing_evidence") if isinstance(pack.get("timing_evidence"), dict) else {}
    evidence = pack.get("evidence_pack") if isinstance(pack.get("evidence_pack"), list) else []
    causal_memory = _compact_causal_memory(pack)
    working_set = _compact_active_working_set(pack)
    return (
        "Begin repository-level RTL repair.\n\n"
        f"<planner_module_name>\n{module_name}\n</planner_module_name>\n\n"
        f"<runtime_top_module>\n{runtime_top_module or module_name}\n</runtime_top_module>\n\n"
        f"<dut_instance>\n{dut_instance}\n</dut_instance>\n\n"
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
        f"{json.dumps({'task_frame': task_frame, 'system_triage': system_triage, 'timing_evidence': timing, 'active_working_set': working_set, 'evidence_pack': evidence[:5], 'causal_memory_summary': causal_memory}, indent=2, ensure_ascii=False)}\n"
        "</debug_context_pack_summary_json>\n\n"
        "<raw_artifact_refs_json>\n"
        f"{json.dumps(raw_artifacts, indent=2, ensure_ascii=False)}\n"
        "</raw_artifact_refs_json>\n\n"
        "<stage_artifact_name_help_json>\n"
        f"{json.dumps(artifact_help, indent=2, ensure_ascii=False)}\n"
        "</stage_artifact_name_help_json>\n\n"
        "<initial_sim_failure_excerpt>\n"
        f"{sim_failed_excerpt}\n"
        "</initial_sim_failure_excerpt>\n\n"
        "<initial_trace_summary_json>\n"
        f"{json.dumps(trace_summary, indent=2, ensure_ascii=False)}\n"
        "</initial_trace_summary_json>\n\n"
        "This is a system-level RTL debug session. The top simulation/testbench is an executable functional oracle, "
        "not an exhaustive specification; generated submodules may be implemented differently from an official "
        "module-level implementation only while remaining specification-equivalent for all legal inputs and transaction sequences.\n\n"
        "Use the available RTL, module semantics, structural KG, trace, VCD, and simulation tools as needed. "
        "When initial_trace_summary_json supplies required_next_tool=trace_signal_cause, call it first with exactly the supplied arguments; read_context and probe_vcd are unlocked only after that one-hop trace succeeds. "
        "Then use read_module_semantics with signal/block focus for modules on the resulting suspect path. "
        "When the causal fix spans generated modules, make one coherent multi-file apply_patch rather than splitting dependent edits across turns. "
        "After each patch, follow the returned lint/simulation result and continue from the current baseline. "
        "For stage artifacts, use only artifact_name values from stage_artifact_name_help_json; do not pass module names like aes_cipher_top as artifact names. "
        "Recommended stage artifacts for system debug are stage6_merge, repo_skeleton, contracts, and modules; use read_module_semantics for module Spec/Skeleton/Plan. "
        "In functional repair, decide yourself whether semantic intent, trace/VCD, KG, or direct source inspection is needed before patching. "
        "When enough evidence supports a plausible localized repair, patch it and let apply_patch/replace_block verify and roll back regressions; do not keep observing just to prove the root cause completely. "
        "If it returns stable_values_match_but_tb_edge_mismatch, reason about active-region edge sampling and blocking/nonblocking behavior. "
        "If causal memory lists protected_invariants or unsafe_directions, treat them as advisory memory rather than hard requirements. "
        "Selected long-term memories include short excerpts in the context pack; call read_long_term_memory(path) only when the excerpt is insufficient. "
        "Expected/reference values are for localization and validation only and must never become a patch RHS or functional state/output constant. "
        "Reuse only structural or causal patterns from long-term memory, never its concrete data literals. "
        "A lower visible mismatch count alone does not prove that a patch generalizes. "
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
    remaining_reads = max(0, max_readonly_calls - readonly_calls_since_action)
    return (
        "Continue repository-level RTL repair.\n"
        "Use the existing conversation memory and latest persisted artifacts.\n"
        f"latest_context_pack_path: {pack.get('pack_path') or ''}\n"
        f"remaining_read_budget_since_action: {remaining_reads}\n"
        "Decide whether to patch, inspect narrowly, or finish. If enough evidence identifies a plausible localized repair, patch now rather than continuing broad observation. "
        "Expected/reference values are diagnostic only: never copy them into a patch RHS or functional state/output constant. "
        "Reuse only structural or causal patterns from repair memory, not concrete data literals, and do not treat a lower mismatch count alone as proof of generalization. "
        "When remaining_read_budget_since_action is 0, do not use record_correction or generate_response as a way to resume reading; only apply_patch/replace_block can reset the read budget."
    )


def build_compact_prompt(
    snapshot: dict[str, Any],
    mode: str = "checkpoint",
    llm_compact_memory: dict[str, Any] | None = None,
) -> str:
    compact_mode = "deep" if mode == "deep" else "checkpoint"
    title = "Deep compact checkpoint" if compact_mode == "deep" else "Compact checkpoint"
    recovery_section = ""
    if isinstance(llm_compact_memory, dict) and llm_compact_memory:
        recovery_section = (
            "<recovery_memory_json>\n"
            f"{json.dumps(llm_compact_memory, indent=2, ensure_ascii=False)}\n"
            "</recovery_memory_json>\n\n"
        )
    return (
        f"{title}. Do not rely on prior chat history; the JSON below is the latest "
        "debug recovery context. Full journals, trace reports, evidence files, and memory files remain available through tools.\n\n"
        "<context_pack_path>\n"
        f"{snapshot.get('pack_path') or ''}\n"
        "</context_pack_path>\n\n"
        f"{recovery_section}"
        "<debug_context_pack_summary_json>\n"
        f"{_pack_summary_json(snapshot, mode=compact_mode)}\n"
        "</debug_context_pack_summary_json>\n\n"
        "Next-step rules:\n"
        "1. recovery_memory_json is the non-empty compact decision trace and recovery memory; follow any exact required next call in it.\n"
        "2. Use task_frame, system_triage, timing_evidence, evidence_pack, and causal_memory_summary as deterministic anchors.\n"
        "3. selected_long_term_memories include short excerpts only; call read_long_term_memory(path) only when the excerpt is insufficient. Use any read/debug tool when it materially helps the next decision.\n"
        "4. Do not retry unsafe_directions unless new evidence distinguishes the attempt.\n"
        "5. Choose edit scope from the evidence and plausible causal patch rationale, not from a default preference for narrow or broad patches.\n"
        "6. Make one coherent evidence-backed apply_patch, including multiple files when the patch rationale spans generated modules, or use replace_block/record_correction when appropriate."
    )


def build_tool_call_recovery_prompt(tool_name: str | None) -> str:
    """Ask the model to retry a textual pseudo-call through native tool calling."""
    legal_arguments = {
        "replace_block": [
            "module_name",
            "rtl_block_id",
            "new_code",
            "reason",
            "expected_effect",
            "protected_invariants_checked",
            "preserve_plan",
            "syntax_retry_of",
            "verify",
            "rollback_on_fail",
        ],
        "apply_patch": [
            "patches",
            "reason",
            "expected_effect",
            "protected_invariants_checked",
            "preserve_plan",
            "syntax_retry_of",
            "verify",
            "rollback_on_fail",
        ],
    }
    target = tool_name if tool_name in legal_arguments else "the intended tool"
    args = legal_arguments.get(tool_name or "", [])
    fields = json.dumps(args, ensure_ascii=False) if args else "consult the native tool schema"
    extra = (
        " `replace_block` does not accept `path` or planning_block_id; use module_name and rtl_block_id."
        if tool_name == "replace_block"
        else ""
    )
    return (
        "Your previous response contained a textual DSML/XML-like tool call, so no action was executed. "
        f"Retry the same intent now using one native function call to {target}. "
        f"Legal argument names: {fields}.{extra} "
        "Do not repeat or quote the DSML/XML markup, and do not describe the call in prose."
    )
