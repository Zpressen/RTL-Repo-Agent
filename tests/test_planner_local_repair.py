"""Regressions for repair locality, trustworthy completion, and crash recovery."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from rtl_artifact_test_utils import write_artifact_text
from zerorepo.rtl_impl.artifact_layout import ArtifactLayout, artifact_path, artifact_dir
from types import SimpleNamespace

import pytest

from test_rtl_module_planner import (
    QueueBackend, make_stage3_module_skeleton_doc, make_stage4_module_plan_payload,
    make_block_spec_retrieval_payload, make_stage5_code_payload,
)
from zerorepo.rpg_gen.base.llm_client.errors import LLMRequestError
from zerorepo.rtl_impl.debug_agent import ModuleDebugResult
from zerorepo.rtl_impl.module_planner.agents import Stage3Agent, Stage4ModulePlanAgent, Stage5Agent
from zerorepo.rtl_impl.module_planner.agents.base import StageGenerationError
from zerorepo.rtl_impl.module_planner.planner_runner import PlannerRunner
from zerorepo.rtl_impl.module_planner.schemas import (
    ModuleCodegenRecord, ModuleMergeRecord, ModulePlanSubtask, PlannerTaskInput,
    SourceRefs, Stage4SpecBlocksArtifact, Stage5CodegenArtifact,
)
from zerorepo.rtl_impl.module_planner.utils import PlannerLLMClient, inspect_module_skeleton_doc
from zerorepo.rtl_impl.module_planner.utils.codegen_repair import ModulePlanRepairAdapter
from zerorepo.rtl_impl.module_planner.utils.local_repair import fingerprint, strict_json
from zerorepo.rtl_impl.module_planner.utils.skeleton_doc import scan_doc_regions
from zerorepo.rtl_impl.retrieval_agent import BlockSpecRetrievalResult


@pytest.fixture
def skeleton(tmp_path):
    spec = tmp_path / "toy.md"
    write_artifact_text(spec, "# toy\n", encoding="utf-8")
    refs = SourceRefs(module_contract_ref="module_contracts_v1::toy", repo_skeleton_ref="repo_skeleton_v1::toy", module_spec_file=str(spec))
    text = make_stage3_module_skeleton_doc("toy", spec)
    args = dict(expected_module="toy", expected_file_path="generate/rtl/toy.v", source_refs=refs)
    return text, args


def section_body(text, name):
    region = next(item for item in scan_doc_regions(text)[0] if item.name == name)
    return text[region.body_start:region.end]


def test_skeleton_reports_all_fields_and_independent_reference_errors(skeleton):
    text, args = skeleton
    for mode in inspect_module_skeleton_doc(text, **args).artifact.module_behavior.semantic_modes[:2]:
        text = text.replace(f"{mode.mode}: {mode.meaning}", mode.mode)
    text = text.replace("- timing_semantics:\n  - child outputs are consumed by downstream planned blocks\n", "")
    text = text.replace("- topic: control style\n", "").replace("- reason: This avoids forcing an explicit FSM when counter- or flag-driven control is sufficient.\n", "")
    text = text.replace("- depends_on: [B1]", "- depends_on: [BAD]")
    result = inspect_module_skeleton_doc(text, **args)
    paths = {item.path for item in result.issues}
    assert {"module_behavior.semantic_modes[0]", "module_behavior.semantic_modes[1]",
            "block_behavior_overlays[0].timing_semantics", "decision_ledger.chosen_decisions[0].topic",
            "decision_ledger.chosen_decisions[0].reason"} <= paths
    assert any(item.code == "unknown_reference" for item in result.issues)
    assert all(item.line is not None for item in result.issues if item.code != "unknown_reference")
    assert result.artifact is None
    assert "reason" not in result.candidate["decision_ledger"]["chosen_decisions"][0]


def test_missing_list_differs_from_explicit_empty(skeleton):
    text, args = skeleton
    original = "- timing_semantics:\n  - child outputs are consumed by downstream planned blocks"
    empty = inspect_module_skeleton_doc(text.replace(original, "- timing_semantics: []"), **args)
    absent = inspect_module_skeleton_doc(text.replace(original, ""), **args)
    assert empty.artifact.block_behavior_overlays[0].timing_semantics == []
    assert any(item.path == "block_behavior_overlays[0].timing_semantics" for item in absent.issues)


def test_scanner_ignores_fenced_headings_and_reports_duplicates(skeleton):
    text, args = skeleton
    fenced = text.replace("module toy (", "## Decision Ledger\n### Chosen Decision\nmodule toy (", 1)
    result = inspect_module_skeleton_doc(fenced, **args)
    assert len(result.regions) == 5
    assert not result.issues
    duplicate = inspect_module_skeleton_doc(text + "\n## Module Frame\n```verilog\nmodule wrong; endmodule\n```\n", **args)
    assert any(item.code == "duplicate_section" for item in duplicate.issues)
    assert "module_frame" not in duplicate.candidate  # ambiguous content is never silently selected


def test_plain_risk_lists_normalize_without_changing_rtl(skeleton):
    text, args = skeleton
    bare = text.replace("- items:\n  -", "*", 3)
    result = inspect_module_skeleton_doc(bare, **args)
    assert not result.issues
    assert len(result.normalizations) == 3
    assert section_body(result.normalized_doc, "Module Frame") == section_body(text, "Module Frame")
    assert result.artifact.decision_ledger == inspect_module_skeleton_doc(text, **args).artifact.decision_ledger


def test_stage3_repairs_only_decision_ledger(skeleton, tmp_path):
    from copy import deepcopy
    from test_responsibility_refinement import scenario
    saved={}
    def inject(runner):
        responses=runner.llm_client.backend.responses
        index=next(i for i,value in enumerate(responses) if isinstance(value,dict) and "module_frame" in value)
        saved["design"]=deepcopy(responses[index])
        del responses[index]["decision_ledger"]["chosen_decisions"][0]["reason"]
        responses.insert(index+1,{"decision_ledger":saved["design"]["decision_ledger"]})
    _, runner, backend, _, stage3, _=scenario(tmp_path,before_run=inject)
    value=json.loads((runner.output_root/stage3.module_records[0].export_file).read_text())
    assert value["decision_ledger"]==saved["design"]["decision_ledger"]
    assert value["module_frame"]==saved["design"]["module_frame"]
    assert any('"sections":["decision_ledger"]' in c["user_prompt"] for c in backend.calls)


def test_stage3_repairs_one_overlay_entry(skeleton, tmp_path):
    from test_responsibility_refinement import scenario
    _, runner, _, _, stage3, _=scenario(tmp_path)
    value=json.loads((runner.output_root/stage3.module_records[0].export_file).read_text())
    for overlay in value["block_behavior_overlays"]:
        expected=[o["obligation_id"] for o in value["behavioral_obligations"] if o["implementation_block_id"]==overlay["block_id"]]
        assert overlay["obligation_ids"]==expected


@pytest.mark.parametrize("patches", [
    [{"target": "Module Frame", "replacement": "bad"}],
    [{"target": "Decision Ledger", "replacement": "bad"}] * 2,
    [{"target": "Decision Ledger", "replacement": "## Module Frame\nbad"}],
])
def test_stage3_rejects_invalid_patches_without_losing_candidate(skeleton, patches, tmp_path):
    from copy import deepcopy
    from test_responsibility_refinement import scenario
    saved={}
    def inject(runner):
        responses=runner.llm_client.backend.responses
        index=next(i for i,value in enumerate(responses) if isinstance(value,dict) and "module_frame" in value)
        saved["design"]=deepcopy(responses[index])
        responses[index]["behavioral_obligations"][0]["source_evidence_ids"]=["EV_unknown"]
        responses[index+1:index+1]=[{"patches":patches},{"behavioral_obligations":[saved["design"]["behavioral_obligations"][0]]}]
    _, runner, backend, _, stage3, _=scenario(tmp_path,before_run=inject)
    value=json.loads((runner.output_root/stage3.module_records[0].export_file).read_text())
    assert value["module_frame"]==saved["design"]["module_frame"]
    assert any("Untargeted design section: patches" in c["user_prompt"] for c in backend.calls)


def test_stage4_patches_one_description_and_preserves_other_tasks():
    plan = make_stage4_module_plan_payload("toy")
    required = [{key: item[key] for key in ("id", "target", "spec_refs")} for item in plan["subtasks"]]
    broken = copy.deepcopy(plan)
    del broken["subtasks"][1]["description"]
    adapter = ModulePlanRepairAdapter(module="toy", required=required, context="skeleton", source_blocks=[], validator=lambda _: [])
    inspection = adapter.inspect(broken)
    target = f"subtasks/{plan['subtasks'][1]['id']}/description"
    assert set(adapter.targets(inspection)) == {target}
    merged = adapter.merge(inspection, {"patches": [{"target": target, "replacement": "Recovered source-grounded description"}]}, adapter.targets(inspection))
    assert merged["subtasks"][0] == plan["subtasks"][0]
    assert merged["subtasks"][2:] == plan["subtasks"][2:]
    assert not adapter.inspect(merged).issues
    whole = copy.deepcopy(plan)
    whole["subtasks"][0]["description"] = "Unrequested rewrite"
    with pytest.raises(ValueError, match="untargeted"):
        adapter.merge(inspection, whole, adapter.targets(inspection))


def test_stage4_does_not_guess_ambiguous_identities():
    plan = make_stage4_module_plan_payload("toy")
    required = [{key: item[key] for key in ("id", "target", "spec_refs")} for item in plan["subtasks"]]
    original = copy.deepcopy(plan)
    plan["subtasks"][1]["id"] = plan["subtasks"][0]["id"]
    adapter = ModulePlanRepairAdapter(module="toy", required=required, context="", source_blocks=[], validator=lambda _: [])
    result = adapter.inspect(plan)
    assert any(item.code == "ambiguous_identity" for item in result.issues)
    assert set(adapter.targets(result)) == {"subtasks:unresolved"}
    patched = adapter.merge(result, {"patches": [{"target": "subtasks:unresolved", "replacement": original["subtasks"][:2]}]}, adapter.targets(result))
    assert patched["subtasks"][2:] == original["subtasks"][2:]
    assert not adapter.inspect(patched).issues


@pytest.mark.parametrize("invalid", [None, [], "not an object"])
def test_stage4_malformed_identity_preserves_identifiable_tasks(invalid):
    original = make_stage4_module_plan_payload("toy")
    required = [{key: item[key] for key in ("id", "target", "spec_refs")} for item in original["subtasks"]]
    broken = copy.deepcopy(original)
    if invalid == "not an object":
        broken["subtasks"][0] = invalid
    else:
        broken["subtasks"][0]["id"] = invalid
    adapter = ModulePlanRepairAdapter(module="toy", required=required, context="", source_blocks=[], validator=lambda _: [])
    inspected = adapter.inspect(broken)
    targets = adapter.targets(inspected)
    assert set(targets) == {"subtasks:unresolved"}
    repaired = adapter.merge(inspected, {"patches": [{"target": "subtasks:unresolved", "replacement": original["subtasks"][:1]}]}, targets)
    assert repaired["subtasks"][1:] == original["subtasks"][1:]
    assert not adapter.inspect(repaired).issues


def test_stage4_failed_plan_reuses_retrieval_on_restart(tmp_path, skeleton):
    from test_responsibility_refinement import scenario
    task, runner, backend, _, _, stage4=scenario(tmp_path)
    path=runner.output_root/stage4.module_plan_files[0].plan_file
    original=path.read_text()
    bad=json.loads(original); del bad["subtasks"][0]["description"]
    path.write_text(json.dumps(bad))
    count=len(backend.calls)
    runner.run(task,resume=True,end_stage="stage4")
    assert len(backend.calls)==count
    assert json.loads(path.read_text())==json.loads(original)


def stage5_inputs(tmp_path, *, count=3):
    task = PlannerTaskInput(task_id="toy_task", spec_md_files=[str(tmp_path / "toy.md")])
    output = tmp_path / "outputs"
    (output / "module_plan_json").mkdir(parents=True)
    subtasks = [{"id": f"B{i}", "target": f"<block: B{i}>", "description": f"Implement source obligation {i}", "spec_refs": ["S001"], "constraints": []} for i in range(1, count + 1)]
    plan = {"module": "toy", "subtasks": subtasks}
    write_artifact_text(ArtifactLayout(output).module(4, Path("toy.json").stem, "plan.json"), json.dumps(plan), encoding="utf-8")
    inputs = {
        "stage4": {"task_id": task.task_id, "module_order": ["toy"], "module_plan_files": [{"module": "toy", "plan_file": "plan/stage4/modules/toy/plan.json"}]},
        "spec_blocks": {"task_id": task.task_id, "module_order": ["toy"], "modules": [{"module": "toy", "source_spec_file": "toy.md", "blocks": [{"block_id": "S001", "text": "Read a and drive y."}]}]},
        "stage5_input_fingerprint": "initial",
    }
    return task, output, inputs, subtasks


def test_stage5_resumes_valid_prefix_after_third_subtask_fails(tmp_path):
    task, output, inputs, subtasks = stage5_inputs(tmp_path)
    good = [make_stage5_code_payload(task.task_id, "toy", subtask, f"assign y{i} = a;") for i, subtask in enumerate(subtasks)]
    bad = make_stage5_code_payload(task.task_id, "toy", subtasks[2], "generate endgenerate")
    agent = Stage5Agent(PlannerLLMClient(backend=QueueBackend(good[:2] + [bad] * 3)), output_root=output)
    with pytest.raises(StageGenerationError):
        agent.run_module(task, inputs, "toy")
    before = agent._workspace_file("toy").read_text(encoding="utf-8")
    checkpoint = agent._read_checkpoint("toy", task.task_id)
    assert checkpoint["status"] == "in_progress"
    assert [item["subtask_id"] for item in checkpoint["subtasks"]] == ["B1", "B2"]
    backend = QueueBackend([good[2]])
    resumed = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output)
    inputs["stage5_input_fingerprint"] = "new-manifest-fingerprint"
    record = resumed.run_module(task, inputs, "toy")
    assert len(backend.calls) == 1
    assert record.completed_subtasks == ["B1", "B2", "B3"]
    assert resumed._workspace_file("toy").read_text(encoding="utf-8").startswith(before)
    assert resumed._read_checkpoint("toy", task.task_id)["status"] == "completed"
    assert "generate endgenerate" not in backend.calls[0]["user_prompt"]


def test_stage5_repairs_contract_without_regenerating_code(tmp_path):
    task, output, inputs, subtasks = stage5_inputs(tmp_path, count=1)
    payload = make_stage5_code_payload(task.task_id, "toy", subtasks[0], "assign y = a;")
    contract = copy.deepcopy(payload["contract"])
    payload["contract"]["writes"] = []
    backend = QueueBackend([payload, {"patches": [{"target": "contract.writes", "replacement": contract["writes"]}]}])
    agent = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output)
    agent.run_module(task, inputs, "toy")
    assert agent._fragment_sections(agent._workspace_file("toy").read_text())["B1"][2] == "assign y = a;"
    assert "The code is fixed" in backend.calls[1]["user_prompt"]
    assert agent._read_checkpoint("toy")["subtasks"][0]["artifact"]["code"] == payload["code"]


def test_stage5_missing_contract_is_repaired_explicitly(tmp_path):
    task, output, inputs, subtasks = stage5_inputs(tmp_path, count=1)
    payload = make_stage5_code_payload(task.task_id, "toy", subtasks[0], "assign y = a;")
    contract = payload.pop("contract")
    backend = QueueBackend([payload, {"patches": [{"target": "contract", "replacement": contract}]}])
    Stage5Agent(PlannerLLMClient(backend=backend), output_root=output).run_module(task, inputs, "toy")
    assert len(backend.calls) == 2
    assert "Generated fragments require an explicit contract" in backend.calls[1]["user_prompt"]


def test_stage5_reassembles_metadata_without_a_model_retry(tmp_path):
    task, output, inputs, subtasks = stage5_inputs(tmp_path, count=1)
    payload = make_stage5_code_payload("wrong", "wrong", subtasks[0], "assign y = a;")
    payload["spec_refs"] = ["WRONG"]
    backend = QueueBackend([payload])
    agent = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output)
    agent.run_module(task, inputs, "toy")
    assert len(backend.calls) == 1
    saved = agent._read_checkpoint("toy")["subtasks"][0]["artifact"]
    assert saved["module"] == "toy" and saved["task_id"] == task.task_id and saved["spec_refs"] == ["S001"]


def test_stage5_plan_change_invalidates_only_affected_suffix(tmp_path):
    task, output, inputs, subtasks = stage5_inputs(tmp_path)
    good = [make_stage5_code_payload(task.task_id, "toy", item, f"assign y{i} = a;") for i, item in enumerate(subtasks)]
    agent = Stage5Agent(PlannerLLMClient(backend=QueueBackend(good)), output_root=output)
    agent.run_module(task, inputs, "toy")
    plan_path = ArtifactLayout(output).module(4, Path("toy.json").stem, "plan.json")
    plan = json.loads(plan_path.read_text())
    plan["subtasks"][1]["constraints"] = ["A new source obligation"]
    write_artifact_text(plan_path, json.dumps(plan), encoding="utf-8")
    backend = QueueBackend(good[1:])
    resumed = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output)
    resumed.run_module(task, inputs, "toy")
    assert len(backend.calls) == 2
    assert '"id": "B2"' in backend.calls[0]["user_prompt"]


def test_resume_interruption_does_not_discard_valid_cached_tail(tmp_path, monkeypatch):
    task, output, inputs, subtasks = stage5_inputs(tmp_path)
    good = [make_stage5_code_payload(task.task_id, "toy", item, f"assign y{i} = a;") for i, item in enumerate(subtasks)]
    agent = Stage5Agent(PlannerLLMClient(backend=QueueBackend(good)), output_root=output)
    agent.run_module(task, inputs, "toy")
    backend = QueueBackend([])
    interrupted = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output)
    commit = interrupted._commit_subtasks
    def interrupt(**kwargs):
        commit(**kwargs)
        raise RuntimeError("process interrupted after first prefix commit")
    monkeypatch.setattr(interrupted, "_commit_subtasks", interrupt)
    with pytest.raises(RuntimeError, match="interrupted"):
        interrupted.run_module(task, inputs, "toy")
    checkpoint = interrupted._read_checkpoint("toy")
    assert checkpoint["status"] == "completed"
    assert [item["subtask_id"] for item in checkpoint["subtasks"]] == ["B1", "B2", "B3"]
    candidate = json.loads(next((artifact_dir(agent.workspace_root, ".stage5_candidates")).glob("toy/*/checkpoint.json")).read_text())
    assert [item["subtask_id"] for item in candidate["subtasks"]] == ["B1"]
    assert [item["subtask_id"] for item in candidate["pending_subtasks"]] == ["B2", "B3"]
    resumed = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output)
    assert resumed.run_module(task, inputs, "toy").completed_subtasks == ["B1", "B2", "B3"]
    assert backend.calls == []


def test_runner_stage5_cache_checks_current_inputs_and_content(tmp_path):
    task, output, inputs, subtasks = stage5_inputs(tmp_path, count=1)
    backend = QueueBackend([make_stage5_code_payload(task.task_id, "toy", subtasks[0], "assign y = a;")])
    runner = PlannerRunner(output_root=output, llm_backend=backend)
    runner.stage5.run_module(task, inputs, "toy")
    assert runner._reuse_stage5_fragment_if_valid("toy", inputs, task) is not None
    assert len(backend.calls) == 1
    source = copy.deepcopy(inputs)
    source["spec_blocks"]["modules"][0]["blocks"][0]["text"] = "Different binding source"
    assert runner._reuse_stage5_fragment_if_valid("toy", source, task) is None
    path = runner.stage5._workspace_file("toy")
    write_artifact_text(path, path.read_text().replace("assign y = a;", "assign y = b;"))
    assert runner._reuse_stage5_fragment_if_valid("toy", inputs, task) is None
    assert len(backend.calls) == 1


def test_checkpoint_restores_last_committed_prefix_after_sidecar_write_failure(tmp_path, monkeypatch):
    task, output, inputs, subtasks = stage5_inputs(tmp_path, count=2)
    good = [make_stage5_code_payload(task.task_id, "toy", item, f"assign y{i} = a;") for i, item in enumerate(subtasks)]
    agent = Stage5Agent(PlannerLLMClient(backend=QueueBackend(good)), output_root=output)
    write = agent._write_contracts_file
    def fail(module, entries, **kwargs):
        if len(entries) == 2:
            raise OSError("simulated contract write failure")
        return write(module, entries, **kwargs)
    monkeypatch.setattr(agent, "_write_contracts_file", fail)
    with pytest.raises(OSError):
        agent.run_module(task, inputs, "toy")
    assert len(agent._read_checkpoint("toy")["subtasks"]) == 1
    backend = QueueBackend([good[1]])
    resumed = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output)
    resumed.run_module(task, inputs, "toy")
    assert len(backend.calls) == 0  # verified candidate survives failed alias publication
    assert list(resumed._fragment_sections(resumed._workspace_file("toy").read_text())) == ["B1", "B2"]


def test_contract_comparison_is_not_mistaken_for_an_assignment(tmp_path):
    task, output, inputs, subtasks = stage5_inputs(tmp_path, count=1)
    payload = make_stage5_code_payload(task.task_id, "toy", subtasks[0], "always @(a or b) begin\n  if (a <= b) y = a;\nend")
    payload["contract"]["writes"] = ["y"]
    backend = QueueBackend([payload])
    agent = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output)
    agent.run_module(task, inputs, "toy")
    contract = json.loads(agent._contracts_file("toy").read_text())["contracts"][0]
    assert contract["contract"]["writes"] == ["y"]
    assert contract["analysis"]["mode"] == "heuristic_hints_only"
    assert len(backend.calls) == 1


@pytest.mark.parametrize("text", [
    "// STAGE5_SUBTASK_BEGIN B1\nx\n// STAGE5_SUBTASK_END B2\n",
    "// STAGE5_SUBTASK_BEGIN B1\nx\n",
    "// STAGE5_SUBTASK_BEGIN B1\nx\n// STAGE5_SUBTASK_END B1\n" * 2,
])
def test_stage5_rejects_ambiguous_fragment_markers(tmp_path, text):
    task, output, _, subtasks = stage5_inputs(tmp_path, count=1)
    agent = Stage5Agent(PlannerLLMClient(backend=QueueBackend([])), output_root=output)
    with pytest.raises(ValueError):
        agent._upsert_subtask_section(text, ModulePlanSubtask.model_validate(subtasks[0]), "assign y = a;")


def test_fragment_replacement_preserves_literal_backslashes(tmp_path):
    _, output, _, subtasks = stage5_inputs(tmp_path, count=1)
    agent = Stage5Agent(PlannerLLMClient(backend=QueueBackend([])), output_root=output)
    subtask = ModulePlanSubtask.model_validate(subtasks[0])
    existing = agent._upsert_subtask_section("", subtask, "assign y = a;")
    replacement = r'initial $display("\1");'
    updated = agent._upsert_subtask_section(existing, subtask, replacement)
    assert agent._fragment_sections(updated)["B1"][2] == replacement


def test_stage5_request_failure_is_not_a_content_retry(tmp_path):
    task, output, inputs, _ = stage5_inputs(tmp_path, count=1)
    class FailedBackend(QueueBackend):
        def complete_with_memory(self, **kwargs):
            self.calls.append(kwargs)
            raise LLMRequestError("transport failed")
    backend = FailedBackend([])
    with pytest.raises(LLMRequestError):
        Stage5Agent(PlannerLLMClient(backend=backend), output_root=output).run_module(task, inputs, "toy")
    assert len(backend.calls) == 1


def test_runner_records_failure_blocks_parent_and_continues_independent_module(tmp_path, monkeypatch):
    task = PlannerTaskInput(task_id="failure", spec_md_files=[str(tmp_path / "spec.md")])
    runner = PlannerRunner(output_root=tmp_path / "outputs", llm_backend=QueueBackend([]))
    runner.output_root.mkdir(parents=True, exist_ok=True)
    latest_path = artifact_path(runner.output_root, "system_debug_latest.json")
    latest = {"top_module": "parent", "status": "fail", "debug_trials": 15, "mismatch_count": 99}
    write_artifact_text(latest_path, json.dumps(latest))
    modules = ["bad", "parent", "independent"]
    specs = Stage4SpecBlocksArtifact.model_validate({"task_id": task.task_id, "module_order": modules, "modules": [{"module": name, "source_spec_file": f"{name}.md", "blocks": [{"block_id": "S001", "text": "obligation"}]} for name in modules]})
    inputs = {"spec_blocks": specs, "stage5_input_fingerprint": "test", "stage2": SimpleNamespace(top_module="parent", modules=[SimpleNamespace(module=name, children=["bad"] if name == "parent" else []) for name in modules])}
    generated = []
    merged = []
    def stage5(task, inputs, module):
        generated.append(module)
        if module == "bad":
            raise StageGenerationError("original fragment failure")
        path = runner.stage5._workspace_file(module)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_artifact_text(path, "// accepted fragment\n")
        return ModuleCodegenRecord(module=module, workspace_file=str(path), completed_subtasks=["B1"])
    def stage6(task, inputs, module, record):
        merged.append(module)
        path = runner.stage6._merged_file(module)
        path.parent.mkdir(parents=True, exist_ok=True)
        write_artifact_text(path, f"module {module}; endmodule\n")
        return ModuleMergeRecord(module=module, fragment_file=record.workspace_file, merged_file=str(path))
    monkeypatch.setattr(runner, "_reuse_stage5_fragment_if_valid", lambda *args: None)
    monkeypatch.setattr(runner.stage5, "run_module", stage5)
    monkeypatch.setattr(runner.stage6, "run_module", stage6)
    monkeypatch.setattr(runner.stage6, "validate_quality", lambda *args: [])
    monkeypatch.setattr(runner, "_write_planning_kg_consistency_report", lambda **kwargs: None)
    monkeypatch.setattr(runner.debug_runner, "run_module_syntax_gate", lambda **kwargs: ModuleDebugResult(module=kwargs["module_name"], status="pass"))
    monkeypatch.setattr(runner.system_debug_runner, "run_system", lambda **kwargs: pytest.fail("Incomplete generation must not run system debug"))
    result = runner._run_stage6_per_module(task, inputs, specs)
    assert generated == ["bad", "independent"]
    assert merged == ["independent"]
    assert result.status == "failed" and result.system_debug.status == "skipped"
    assert result.latest_system_debug.debug_trials == 15
    assert json.loads(latest_path.read_text()) == latest
    manifest = json.loads((artifact_path(runner.output_root, "stage5_codegen.json")).read_text())
    assert manifest["status"] == "failed"
    assert "original fragment failure" in manifest["module_files"][0]["error"]
    assert manifest["module_files"][1]["status"] == "blocked"


def test_stage6_cache_requires_unchanged_fragment_content(tmp_path, monkeypatch):
    runner = PlannerRunner(output_root=tmp_path / "outputs", llm_backend=QueueBackend([]))
    fragment = runner.stage5._workspace_file("toy")
    merged = runner.stage6._merged_file("toy")
    fragment.parent.mkdir(parents=True, exist_ok=True)
    merged.parent.mkdir(parents=True, exist_ok=True)
    write_artifact_text(fragment, "assign y = a;\n")
    write_artifact_text(merged, "module toy; endmodule\n")
    record = ModuleCodegenRecord(module="toy", workspace_file=str(fragment))
    inputs = {"stage5_input_fingerprint": "present"}
    write_artifact_text(runner._stage6_cache_path("toy"), json.dumps({"input_fingerprint": runner._stage6_reuse_key("toy", record, inputs), "merged_fingerprint": fingerprint(merged.read_text())}))
    monkeypatch.setattr(runner.stage6, "_ensure_toolchain_path", lambda: None)
    monkeypatch.setattr("zerorepo.rtl_impl.module_planner.planner_runner._check_single_file_syntax", lambda *args, **kwargs: (True, ""))
    assert runner._reuse_stage6_merge_if_valid("toy", record, inputs) is not None
    write_artifact_text(fragment, "assign y = b;\n")
    assert runner._reuse_stage6_merge_if_valid("toy", record, inputs) is None


@pytest.mark.parametrize("raw", ['{"code":"unfinished', '{"code":"a", "code":"b"}', '{"code":"valid"} trailing'])
def test_strict_json_rejects_truncation_duplicate_fields_and_trailing_content(raw):
    with pytest.raises(ValueError):
        strict_json(raw)
