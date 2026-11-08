"""Traceability, mutation rejection and end-to-end fake-model acceptance."""
from __future__ import annotations

import json
from pathlib import Path
from rtl_artifact_test_utils import write_artifact_text
from zerorepo.rtl_impl.artifact_layout import artifact_path

import pytest

from test_rtl_module_planner import (
    QueueBackend, make_task_input, make_stage1_fact_payload,
    make_stage2_responsibility_payload, make_stage2_candidate_payload,
    make_stage3_module_skeleton_doc, make_module_spec_context_payload,
    make_block_spec_retrieval_payload, make_stage4_module_plan_payload,
    make_stage5_code_payload, make_stage6_module_code, make_merge_context_retrieval_payload,
)
from zerorepo.rtl_impl.module_planner import PlannerRunner
from zerorepo.rtl_impl.module_planner.schemas import (
    SourceEvidence, ResponsibilityLedgerOutput,
    ModuleSkeletonExport, ModulePlanArtifact, Stage1ContractsArtifact,
)
from zerorepo.rtl_impl.module_planner.module_organizer import (
    build_stage2_planning_input_from_task, build_module_organized_artifact_from_repo_skeleton,
)
from zerorepo.rtl_impl.module_planner.utils.responsibility_planning import (
    verify_source, ledger_errors, module_context,
    refinement_issues, task_metadata, task_errors, planning_report, artifact_content,
)
from zerorepo.rtl_impl.module_planner.utils.local_repair import fingerprint


def scenario(tmp_path, *, end_stage="stage4", before_run=None, artifacts=None):
    task, spec, _ = make_task_input(tmp_path, image_count=0)
    ledger = make_stage2_responsibility_payload(spec)
    for ru in ledger["responsibilities"]:
        state = ru["owned_state"][0]
        ru["state_accesses"] = [{"state_id": state, "role": role} for role in ("commit", "reset", "hold")]
    ledger["responsibilities"].append({
        "responsibility_id": "C_CLOCK", "description": "Use the specified shared clock and reset",
        "ownership_required": False, "evidence_sections": ["AES Demo Repository > Timing"],
        "source_refs": [{"source_file": str(spec), "quote": "Reset behavior: rst high returns the control to IDLE."}],
        "applies_to_responsibility_ids": ["RU_KEY_EXPANSION", "RU_TOP_CONTROL"],
    })
    normalized = ResponsibilityLedgerOutput.model_validate(ledger)
    assert not ledger_errors(normalized, build_stage2_planning_input_from_task(task_input=task))
    from zerorepo.rtl_impl.module_planner.utils.evidence import EvidenceRegistry
    registry = EvidenceRegistry(build_stage2_planning_input_from_task(task_input=task))
    # Models select indexed excerpts, not arbitrary quote bytes.
    for group in ("responsibilities", "state_objects"):
        for item in getattr(normalized, group):
            item.source_refs = list({identity: ref.model_copy(deep=True) for source in item.source_refs
                for identity, ref in registry.entries.items()
                if ref.start_line <= source.end_line and ref.end_line >= source.start_line}.values())
    draft_ledger = normalized.model_dump()
    for group in ("responsibilities", "state_objects"):
        for item in draft_ledger[group]:
            item["source_evidence_ids"] = [registry.register(ref) for ref in item.pop("source_refs")]
    responses = [make_stage1_fact_payload(spec), draft_ledger,
                 *[make_stage2_candidate_payload(style, complete=(style == "balanced"))
                   for style in ("conservative", "balanced", "modular")]]
    for name, ru in zip(("aes_key_expand_128", "aes_cipher_top"), normalized.responsibilities):
        doc = make_stage3_module_skeleton_doc(name, spec).replace("# MODULE_SKELETON_DOC v1", "# MODULE_SKELETON_DOC v2", 1)
        obligations = [{"obligation_id": "OB_" + a.role.upper(), "parent_responsibility_id": ru.responsibility_id,
            "behavior_kind": "state_update" if a.role == "commit" else a.role,
            "required_effect": f"{a.role} {a.state_id} as specified", "source_refs": [r.model_dump() for r in ru.source_refs],
            "state_accesses": [a.model_dump()], "constraint_refs": ["C_CLOCK"],
            "implementation_block_id": "B3", "supporting_block_ids": ["B1"]} for a in ru.state_accesses]
        doc = doc.replace("## 4. Decision Ledger", "### Behavioral Obligations\n```json\n" + json.dumps(obligations, indent=2) + "\n```\n\n## 4. Decision Ledger")
        from zerorepo.rtl_impl.module_planner.utils.skeleton_doc import parse_module_skeleton_doc
        from zerorepo.rtl_impl.module_planner.schemas.module_skeleton import SourceRefs
        from zerorepo.rtl_impl.module_planner.utils.evidence import evidence_id
        export = parse_module_skeleton_doc(doc, expected_module=name, expected_file_path=f"generate/rtl/{name}.v",
            source_refs=SourceRefs(module_contract_ref=f"module_contracts_v2::{name}", repo_skeleton_ref=f"repo_skeleton_v2::{name}", module_spec_file=str(spec)))
        draft_obligations = []
        for o in obligations:
            item = dict(o)
            item["source_evidence_ids"] = [evidence_id(ref) for ref in item.pop("source_refs")]
            draft_obligations.append(item)
        for block in export.structural_blocks:
            if block.block_kind not in {"decl", "meta"} and block.block_id != "B3":
                if block.block_kind == "inst":
                    draft_obligations.append({"obligation_id": "OB_INTEGRATE", "parent_responsibility_id": ru.responsibility_id,
                        "behavior_kind": "integration", "required_effect": "Integrate child interfaces for the assigned responsibility",
                        "source_evidence_ids": draft_obligations[0]["source_evidence_ids"], "implementation_block_id": block.block_id})
                else:
                    draft_obligations[0]["supporting_block_ids"].append(block.block_id)
        responses.append({"module_frame": export.module_frame,
            "structural_blocks": [b.model_dump(exclude={"placeholder"}) for b in export.structural_blocks],
            "module_behavior": export.module_behavior.model_dump(), "decision_ledger": export.decision_ledger.model_dump(),
            "behavioral_obligations": draft_obligations})
    plans = [make_stage4_module_plan_payload("aes_key_expand_128"), make_stage4_module_plan_payload("aes_cipher_top", top_module=True)]
    if end_stage in {"stage5", "stage6"}:
        for plan in plans:
            responses.extend(make_stage5_code_payload(task.task_id, plan["module"], t) for t in plan["subtasks"])
            if end_stage == "stage6":
                responses.extend([make_merge_context_retrieval_payload(plan["module"]), make_stage6_module_code(plan["module"])])
    backend = QueueBackend(responses)
    runner = PlannerRunner(output_root=tmp_path / "case", llm_backend=backend, artifacts=artifacts)
    if before_run:
        before_run(runner)
    result = runner.run(task, end_stage=end_stage)
    inputs = runner._current_planning_inputs
    root = runner.output_root
    stage3 = runner._read_module_skeletons_if_valid()
    stage4 = result if end_stage == "stage4" else runner.stage4_module_plans.output_model.model_validate_json((artifact_path(root, "module_plans.json")).read_text())
    return task, runner, backend, inputs, stage3, stage4


@pytest.fixture
def case(tmp_path):
    return scenario(tmp_path)


def report(case):
    _, runner, _, inputs, stage3, stage4 = case
    return planning_report(runner.output_root, inputs["stage2_input"], inputs["stage2_decomposition"],
                           inputs["stage2"], inputs["modules"], stage3, stage4)


def test_exact_source_resolution_and_change_detection(tmp_path):
    path = tmp_path / "spec.md"
    write_artifact_text(path, "# Spec\n## A\nrepeat\n## B\nrepeat\n")
    docs = {str(path): path.read_text()}
    with pytest.raises(ValueError, match="exactly once"):
        verify_source(SourceEvidence(source_file=str(path), quote="repeat"), docs)
    ref = SourceEvidence(source_file=str(path), quote="repeat", section_path="Spec > B")
    verify_source(ref, docs)
    assert (ref.start_line, ref.end_line) == (5, 5)
    assert len(ref.content_hash) == 64
    with pytest.raises(ValueError, match="content_hash changed"):
        verify_source(ref, {str(path): path.read_text() + "changed"})
    with pytest.raises(ValueError, match="outside input"):
        verify_source(SourceEvidence(source_file=str(tmp_path / "other"), quote="repeat"), docs)
    with pytest.raises(ValueError, match="found 0"):
        verify_source(SourceEvidence(source_file=str(path), quote="Repeat"), docs)
    crlf = SourceEvidence(source_file=str(path), quote="# Spec\r\n## A")
    verify_source(crlf, docs)
    assert crlf.quote == "# Spec\n## A"


def test_pipeline_to_stage5_has_complete_trace_and_consumes_contracts(tmp_path):
    case = scenario(tmp_path, end_stage="stage5")
    result = report(case)
    assert result["status"] == "passed"
    assert result["counts"]["required_responsibilities"] == result["counts"]["covered_responsibilities"] == 2
    assert result["counts"]["state_objects"] == 2
    assert result["counts"]["obligations"] == 8
    _, runner, backend, _, _, _ = case
    prompts = [c["user_prompt"] for c in backend.calls if "[CURRENT_SUBTASK]" in c["user_prompt"]]
    assert prompts and any('"OB_RESET"' in p and '"OB_HOLD"' in p and '"task_contract"' in p for p in prompts)
    assert (artifact_path(runner.output_root, "planning_gate_report.json")).is_file()
    assert json.loads((runner.output_root / "plan/stage4/modules/aes_cipher_top/plan.json").read_text())["subtasks"][0]["task_contract"]["support_only"]


def test_source_owned_module_evidence_and_soft_risks(case):
    _, _, _, inputs, _, _ = case
    assert inputs["modules"].schema_version == "module_contracts_v2"
    for bundle in inputs["modules"].modules:
        assert bundle.responsibility_ids
        assert bundle.responsibility_source_refs
        assert bundle.applicable_constraint_ids == ["C_CLOCK"]
    # Existing advisory architecture risks do not become gate errors.
    inputs["stage2"].open_issues.append("advisory architecture risk")
    result = report(case)
    assert result["status"] == "passed" and "advisory architecture risk" in result["risks"]


def test_inferred_module_gets_assigned_fact_evidence_without_matching_spec_name(case):
    _, runner, _, inputs, _, _ = case
    stage1 = Stage1ContractsArtifact.model_validate_json((artifact_path(runner.output_root, "contracts.json")).read_text())
    decomposition = inputs["stage2_decomposition"].model_copy(deep=True)
    repo = inputs["stage2"].model_copy(deep=True)
    evidence = next(f for f in stage1.fact_ledger.facts if f.module == "aes_cipher_top")
    decomposition.responsibilities[0].evidence_fact_ids = [evidence.fact_id]
    decomposition.selected_candidate().modules[0].module = "inferred_worker"
    repo.modules[0].module = "inferred_worker"
    repo.planning_decisions.generation_order[0] = "inferred_worker"
    artifact = build_module_organized_artifact_from_repo_skeleton(stage1_artifact=stage1,
        repo_skeleton=repo, decomposition=decomposition)
    worker = next(m for m in artifact.modules if m.module == "inferred_worker")
    assert worker.responsibility_ids == ["RU_KEY_EXPANSION"]
    assert evidence.fact_id in [f.fact_id for f in worker.facts]
    assert next(m for m in artifact.modules if m.module == "aes_cipher_top").interface_contract == next(i for i in stage1.interface_contracts if i.module == "aes_cipher_top")


@pytest.mark.parametrize("kind", ["state", "temporal"])
def test_typed_relationships_do_not_require_fake_data_contracts(case, kind):
    _, runner, _, inputs, _, _ = case
    decomposition = inputs["stage2_decomposition"].model_copy(deep=True)
    candidate = decomposition.selected_candidate()
    candidate.boundary_contracts = []
    dependency = decomposition.responsibilities[0].dependencies[0]
    dependency.dependency_kind = kind
    dependency.transferred_objects = ["round_key_state"] if kind == "state" else []
    dependency.timing_relation = "NEXT_EDGE"
    evaluation = runner.stage2._evaluate_candidate(candidate=candidate, locked_top=decomposition.locked_top,
        responsibilities=decomposition.responsibilities, stage2_input=inputs["stage2_input"])
    assert not evaluation.fatal_violations
    assert not ledger_errors(decomposition, inputs["stage2_input"])


@pytest.mark.parametrize("mutation", ["owner", "access", "constraint", "dependency", "fact", "missing_kind"])
def test_ledger_rejects_unknown_references(case, mutation):
    _, _, _, inputs, _, _ = case
    ledger = inputs["stage2_decomposition"].model_copy(deep=True)
    if mutation == "owner": ledger.state_objects[0].owner_responsibility_id = "BAD"
    elif mutation == "access": ledger.responsibilities[0].state_accesses[0].state_id = "BAD"
    elif mutation == "constraint": ledger.responsibilities[-1].applies_to_responsibility_ids = ["BAD"]
    elif mutation == "dependency": ledger.responsibilities[0].dependencies[0].target_responsibility_id = "BAD"
    elif mutation == "fact": ledger.responsibilities[0].evidence_fact_ids = ["BAD"]
    elif mutation == "missing_kind": ledger.responsibilities[0].dependencies[0].model_fields_set.remove("dependency_kind")
    assert ledger_errors(ledger, inputs["stage2_input"])


@pytest.mark.parametrize("end_stage", ["stage4", "stage5", "stage6"])
def test_runner_gate_blocks_generation_and_preserves_existing_rtl(tmp_path, monkeypatch, end_stage):
    captured = []
    def inject(runner):
        captured.append(runner)
        original = runner.stage4_module_plans.run_incremental
        sentinel = runner.stage5.workspace_root / "fragments/existing.v"
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        write_artifact_text(sentinel, "previous accepted RTL")
        def corrupt(*args, **kwargs):
            artifact = original(*args, **kwargs)
            path = runner.output_root / artifact.module_plan_files[0].plan_file
            plan = json.loads(path.read_text())
            plan["subtasks"][2]["obligation_ids"] = []
            write_artifact_text(path, json.dumps(plan))
            return artifact
        monkeypatch.setattr(runner.stage4_module_plans, "run_incremental", corrupt)
        monkeypatch.setattr(runner.stage5, "run_incremental", lambda *a, **k: pytest.fail("codegen must not be invoked"))
        monkeypatch.setattr(runner, "_run_stage6_per_module", lambda *a, **k: pytest.fail("merge/reuse must not be invoked"))
    with pytest.raises(ValueError, match="Planning gate failed"):
        scenario(tmp_path, end_stage=end_stage, before_run=inject)
    runner = captured[0]
    assert (runner.stage5.workspace_root / "fragments/existing.v").read_text() == "previous accepted RTL"
    assert json.loads((artifact_path(runner.output_root, "planning_gate_report.json")).read_text())["status"] == "failed"


@pytest.mark.parametrize("mutation,expected", [
    ("missing_obligations", "uncovered_responsibility"),
    ("declaration_owner", "invalid_implementation_block"),
    ("unknown_parent", "unknown_responsibility"),
    ("unknown_support", "unknown_block"),
    ("missing_constraint", "uncovered_constraint"),
    ("conflicting_commit", "state_commit_conflict"),
    ("missing_hold", "uncovered_state_access"),
    ("foreign_state", "state_owner_conflict"),
    ("source_drift", "invalid_source"),
    ("clock_drift", "contract_drift"),
])
def test_refinement_rejects_invalid_obligations(case, mutation, expected):
    _, runner, _, inputs, stage3, _ = case
    export = ModuleSkeletonExport.model_validate_json((runner.output_root / stage3.module_records[0].export_file).read_text())
    if mutation == "missing_obligations": export.behavioral_obligations = []
    elif mutation == "declaration_owner": export.behavioral_obligations[0].implementation_block_id = "B1"
    elif mutation == "unknown_parent": export.behavioral_obligations[0].parent_responsibility_id = "RU_UNKNOWN"
    elif mutation == "unknown_support": export.behavioral_obligations[0].supporting_block_ids = ["BAD"]
    elif mutation == "missing_constraint":
        for obligation in export.behavioral_obligations: obligation.constraint_refs = []
    elif mutation == "conflicting_commit":
        new = export.structural_blocks[2].model_copy(deep=True)
        new.block_id, new.block_label = "B_EXTRA", "extra"
        export.structural_blocks.append(new)
        export.behavioral_obligations[1].implementation_block_id = "B_EXTRA"
    elif mutation == "missing_hold": export.behavioral_obligations = [o for o in export.behavioral_obligations if o.behavior_kind != "hold"]
    elif mutation == "foreign_state": export.behavioral_obligations[0].state_accesses[0].state_id = "round_counter"
    elif mutation == "source_drift": export.behavioral_obligations[0].source_refs[0].quote = "invented evidence"
    elif mutation == "clock_drift": export.behavioral_obligations[0].clock_domain = "unrelated_clock"
    issues = refinement_issues(export, module_context(inputs["stage2_decomposition"], export.module), inputs["stage2_input"])
    assert expected in {i.code for i in issues}


def test_one_obligation_entity_repair_preserves_unrelated_design(case):
    from copy import deepcopy
    from zerorepo.rtl_impl.module_planner.utils.planning_session import entity_scope, merge_entities
    from zerorepo.rtl_impl.module_planner.utils.local_repair import ArtifactIssue
    original = {"module_frame": "locked", "structural_blocks": [], "behavioral_obligations": [
        {"obligation_id": "A", "parent_responsibility_id": "R", "required_effect": "original"},
        {"obligation_id": "B", "parent_responsibility_id": "R", "required_effect": "keep"}]}
    scope = entity_scope(original, [ArtifactIssue("behavioral_obligations", "invalid_effect", "needs detail", unit_id="A", category="hardware")])
    replacement = deepcopy(original["behavioral_obligations"][0]); replacement["required_effect"] = "repaired"
    repaired = merge_entities(original, {"behavioral_obligations": [replacement]}, scope)
    assert repaired["behavioral_obligations"][1] == original["behavioral_obligations"][1]
    assert original["behavioral_obligations"][0]["required_effect"] == "original"
    with pytest.raises(ValueError, match="Untargeted"):
        merge_entities(original, {"module_frame": "changed"}, scope)


def test_authoritative_task_metadata_and_generation_topology(case):
    _, runner, _, _, stage3, stage4 = case
    export = ModuleSkeletonExport.model_validate_json((runner.output_root / stage3.module_records[0].export_file).read_text())
    plan = ModulePlanArtifact.model_validate_json((runner.output_root / stage4.module_plan_files[0].plan_file).read_text())
    assert not task_errors(plan, export)
    commit = next(t for t in plan.subtasks if "OB_COMMIT" in t.obligation_ids)
    assert len(commit.task_contract.obligations) == 3
    commit.obligation_ids = []
    assert any("obligation_ids" in e for e in task_errors(plan, export))
    export.structural_blocks[0].depends_on = [export.structural_blocks[-1].block_id]
    with pytest.raises(ValueError, match="cycle"):
        task_metadata(export)


@pytest.mark.parametrize("component", ["plan", "export", "source", "ownership", "must_colocate", "spec_refs", "target"])
def test_gate_rejects_drift_before_any_codegen(case, component):
    task, runner, backend, inputs, stage3, stage4 = case
    if component == "plan":
        path = runner.output_root / stage4.module_plan_files[0].plan_file
        value = json.loads(path.read_text()); value["subtasks"][2]["obligation_ids"] = []
        write_artifact_text(path, json.dumps(value))
    elif component == "export":
        path = runner.output_root / stage3.module_records[0].export_file
        value = json.loads(path.read_text()); value["behavioral_obligations"] = []
        write_artifact_text(path, json.dumps(value))
    elif component == "source": write_artifact_text(Path(task.spec_md_files[0]), "changed source")
    elif component == "ownership": inputs["stage2"].modules[0].responsibility_ids = []
    elif component == "must_colocate": inputs["stage2_decomposition"].responsibilities[0].dependencies[0].partition_constraint = "must_colocate"
    elif component in {"spec_refs", "target"}:
        path = runner.output_root / stage4.module_plan_files[0].plan_file
        value = json.loads(path.read_text())
        value["subtasks"][0][component] = ["BAD"] if component == "spec_refs" else "<block: unknown>"
        write_artifact_text(path, json.dumps(value))
    before = len(backend.calls)
    result = report(case)
    assert result["status"] == "failed" and result["errors"]
    assert len(backend.calls) == before


def test_resume_requires_current_bodies_and_reuses_new_checkpoints(case):
    task, runner, backend, inputs, stage3, stage4 = case
    count = len(backend.calls)
    runner.run(task, resume=True, end_stage="stage4")
    assert len(backend.calls) == count
    old = fingerprint(artifact_content(runner.output_root, stage3, stage4))
    path = runner.output_root / stage4.module_plan_files[-1].plan_file
    payload = json.loads(path.read_text()); payload["subtasks"][2]["task_contract"]["obligations"][0]["required_effect"] = "drift"
    write_artifact_text(path, json.dumps(payload))
    assert fingerprint(artifact_content(runner.output_root, stage3, stage4)) != old
    restored = runner._read_module_plans_if_valid(task, {**inputs, "stage3": stage3})
    assert restored.resume_cursor == 1
    assert restored.stage4_status == "module_plans_in_progress"


def test_legacy_artifacts_are_not_reused(case):
    _, runner, _, _, _, _ = case
    for filename, old, reader in [
        ("stage2_decomposition.json", "stage2_decomposition_v1", runner._read_stage2_decomposition_if_valid),
        ("repo_skeleton.json", "repo_skeleton_v1", runner._read_repo_skeleton_if_valid),
        ("module_skeletons.json", "stage3_skeleton_docs_v1", runner._read_module_skeletons_if_valid),
    ]:
        path = runner.layout.artifact(filename)
        value = json.loads(path.read_text()); value["schema_version"] = old
        write_artifact_text(path, json.dumps(value))
        assert reader() is None
