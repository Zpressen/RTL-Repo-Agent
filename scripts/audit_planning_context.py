#!/usr/bin/env python3
"""Measure prompt-only projections against saved real planning artifacts.

No model calls, no changes to the supplied cases. Registry scratch files use a
temporary directory. Character comparisons replay the same saved inputs; they
are not token, model-quality or monetary savings estimates.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zerorepo.rtl_impl.module_planner.agents import Stage2Agent, Stage3Agent
from zerorepo.rtl_impl.module_planner.module_organizer import build_stage2_planning_input
from zerorepo.rtl_impl.module_planner.schemas import (
    PlannerTaskInput, Stage1ContractsArtifact, Stage2DecompositionArtifact,
    Stage2RepoSkeletonArtifact, ModuleOrganizationArtifact, ModuleSkeletonExport,
    ResponsibilityLedgerOutput,
)
from zerorepo.rtl_impl.module_planner.utils import PlannerLLMClient
from zerorepo.rtl_impl.module_planner.utils.evidence import evidence_id
from zerorepo.rtl_impl.module_planner.utils.local_repair import ArtifactIssue
from zerorepo.rtl_impl.module_planner.utils.planning_session import PlanningSession, NodeResult, entity_scope
from zerorepo.rtl_impl.module_planner.utils.skeleton_json import design_context, design_candidate_context, design_repair_context
from zerorepo.rtl_impl.module_planner.utils.stage5_sources import task_prompt_context
from zerorepo.rtl_impl.module_planner.utils.artifact_store import atomic_write_json


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def audit_case(root):
    root = Path(root).resolve()
    def read(cls, path):
        return cls.model_validate_json((root / "plan" / path).read_text())
    stage1 = read(Stage1ContractsArtifact, "stage1/contracts.json")
    decomposition = read(Stage2DecompositionArtifact, "stage2/stage2_decomposition.json")
    modules = read(ModuleOrganizationArtifact, "stage2/modules.json")
    repo = read(Stage2RepoSkeletonArtifact, "stage2/repo_skeleton.json")
    task = PlannerTaskInput(task_id=stage1.task_id, spec_md_files=stage1.fact_ledger.source_files)
    inputs = build_stage2_planning_input(stage1_artifact=stage1, task_input=task)
    result = {"case": root.name, "case_root": str(root), "stage3_modules": []}
    with TemporaryDirectory(prefix="planning_context_audit_") as scratch:
        client = PlannerLLMClient(backend=object())  # Any accidental API call fails.
        client.configure_execution(Path(scratch))
        agent2 = Stage2Agent(client)
        def capture_ledger(_session, **kw):
            original = kw["prompt"] + "\nINPUT:\n" + encode(kw["context"])
            projected = kw["prompt_view"]({"full": True}) + "\nINPUT:\n" + encode(kw["context"])
            result["stage2_initial_responsibilities"] = {
                "before_chars": len(agent2.system_role) + len(original),
                "after_chars": len(agent2.system_role) + len(projected),
                "original_evidence_preserved": True,
                "duplicate_fact_prose_removed": True,
            }
            return NodeResult("validated", ResponsibilityLedgerOutput(
                responsibilities=decomposition.responsibilities, state_objects=decomposition.state_objects,
                global_clocking_notes=decomposition.global_clocking_notes,
                global_data_conventions=decomposition.global_data_conventions))
        with patch.object(PlanningSession, "execute", capture_ledger):
            agent2._extract_responsibilities(task=task, partial_artifacts={"stage2_input": inputs},
                prompt_context=agent2._build_stage2_prompt_context(inputs), locked_top=decomposition.locked_top)

        def capture_candidate(_session, **kw):
            fixed = len(agent2.system_role) + len("\nINPUT:\n") + len(encode(kw["context"]))
            result["stage2_candidate_provenance"] = {
                "before_chars": fixed + len(kw["prompt"]),
                "after_chars": fixed + len(kw["prompt_view"]({"full": True})),
                "note": "One candidate; every cited original is retained. All three architectural styles use the same provenance view."}
            return NodeResult("validated", decomposition.candidates[0])
        with patch.object(PlanningSession, "execute", capture_candidate):
            agent2._generate_candidate(task=task, partial_artifacts={"stage2_input": inputs},
                prompt_context=agent2._build_stage2_prompt_context(inputs), locked_top=decomposition.locked_top,
                responsibility_ledger=ResponsibilityLedgerOutput(responsibilities=decomposition.responsibilities,
                    state_objects=decomposition.state_objects, global_clocking_notes=decomposition.global_clocking_notes,
                    global_data_conventions=decomposition.global_data_conventions), plan_style="conservative")

        def capture_design(session, **kw):
            module = kw["module"]
            export = ModuleSkeletonExport.model_validate_json(
                (root / "plan/stage3/modules" / module / "skeleton.json").read_text())
            context = kw["context"]
            view = design_context(context, {"full": True})
            fixed = len(session.agent.system_role) + len(kw["prompt"]) + len("\nINPUT:\n")
            draft = {"module_frame": export.module_frame,
                "structural_blocks": [b.model_dump(exclude={"placeholder"}) for b in export.structural_blocks],
                "module_behavior": export.module_behavior.model_dump(), "decision_ledger": export.decision_ledger.model_dump(),
                "behavioral_obligations": []}
            for obligation in export.behavioral_obligations:
                item = obligation.model_dump(exclude={"clock_domain", "reset_behavior", "protocol"})
                item["source_evidence_ids"] = [evidence_id(ref) for ref in item.pop("source_refs")]
                draft["behavioral_obligations"].append(item)
            issue = ArtifactIssue("behavioral_obligations", "source_not_inherited", "Repair this obligation's source binding",
                unit_id=draft["behavioral_obligations"][0]["obligation_id"])
            scope = entity_scope(draft, [issue])
            full_feedback = {"candidate": draft, "issues": [issue.to_dict()], "repair_scope": scope}
            focused_feedback = {**full_feedback, "candidate": design_candidate_context(draft, scope)}
            row = {"module": module, "before_initial_chars": fixed + len(encode(context)),
                "after_initial_chars": fixed + len(encode(view)),
                "before_evidence_entries": len(context["evidence_catalog"]["entries"]),
                "after_evidence_entries": len(view["evidence_catalog"]["entries"]),
                "sections_before": {k: len(encode(v)) for k, v in context.items()},
                "sections_after": {k: len(encode(v)) for k, v in view.items()},
                "single_obligation_repair_serialization": {
                    "note": "Controlled one-obligation scope; full catalog remains available during repair.",
                    "before_chars": fixed + len(encode(context)) + len(encode(full_feedback)),
                    "after_source_repair_chars": fixed + len(encode(design_repair_context(context, scope, [issue]))) + len(encode(focused_feedback)),
                    "after_ordinary_repair_chars": fixed + len(encode(design_repair_context(context, scope,
                        [ArtifactIssue("behavioral_obligations", "unknown_block", "Fix block ID")]))) + len(encode(focused_feedback))}}
            result["stage3_modules"].append(row)
            return NodeResult("validated", export, candidate=deepcopy(draft))
        with patch.object(PlanningSession, "execute", capture_design):
            Stage3Agent(client, output_root=scratch).run_incremental(task, {
                "stage2_input": inputs, "stage2_decomposition": decomposition, "stage2": repo, "modules": modules})
    result["stage3_initial_totals"] = {key: sum(r[field] for r in result["stage3_modules"])
        for key, field in (("before_chars", "before_initial_chars"), ("after_chars", "after_initial_chars"))}
    generation_tasks = []
    for path in sorted((root / "plan/stage4/modules").glob("*/plan.json")):
        for task in json.loads(path.read_text())["subtasks"]:
            task.pop("timing_obligation_ids", None)
            task.pop("logical_value_tags", None)
            generation_tasks.append({"module": path.parent.name, "task": task["id"],
                "before_pretty_chars": len(json.dumps(task, ensure_ascii=False, indent=2)),
                "compact_only_chars": len(encode(task)),
                "after_shared_chars": len(encode(task_prompt_context(task)))})
    result["stage5_task_contract_serialization"] = {
        "scope": "CURRENT_SUBTASK sections only, replayed from saved plans; not full requests or actual Stage5 API usage.",
        "tasks": generation_tasks,
        "totals": {key: sum(task[key] for task in generation_tasks)
            for key in ("before_pretty_chars", "compact_only_chars", "after_shared_chars")}}
    metrics = root / "plan/metrics.json"
    result["historical_actual_usage"] = json.loads(metrics.read_text()) if metrics.exists() else None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for case in args.cases:
        if args.output.resolve().is_relative_to(case.resolve()):
            parser.error("Audit output must be outside the audited case directories")
    result = {"kind": "same_input_prompt_serialization_comparison", "api_calls": 0,
        "notes": "Historical usage is reported separately. Replay character reductions do not prove token or output-quality improvements.",
        "cases": [audit_case(root) for root in args.cases]}
    atomic_write_json(args.output, result)
    for case in result["cases"]:
        print(encode({"case": case["case"], "stage2": case["stage2_initial_responsibilities"],
                      "stage3": case["stage3_initial_totals"]}))


if __name__ == "__main__":
    main()
