"""Contract repairs preserve code, identity, and all untargeted fields."""
from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from test_planner_local_repair import stage5_inputs
from test_rtl_module_planner import QueueBackend, make_stage5_code_payload
from zerorepo.rtl_impl.module_planner.agents import Stage5Agent, Stage6MergeAgent
from zerorepo.rtl_impl.module_planner.agents.base import StageGenerationError
from zerorepo.rtl_impl.module_planner.schemas import (
    ModuleMergeRecord, ModulePlanSubtask, Stage6MergeArtifact, SubtaskCodeArtifact,
)
from zerorepo.rtl_impl.module_planner.utils import PlannerLLMClient
from zerorepo.rtl_impl.module_planner.utils.codegen_repair import SubtaskCodeRepairAdapter


def adapter_and_payload():
    subtask = ModulePlanSubtask(id="B1", target="<block: outputs>", description="Drive outputs", spec_refs=["S001"], constraints=[])
    payload = make_stage5_code_payload("task", "toy", subtask.model_dump(), "assign helper = a;\nassign y = helper;")
    payload["contract"]["writes"] = ["y"]
    adapter = SubtaskCodeRepairAdapter(task_id="task", module="toy", subtask=subtask, context="Source constraints",
        validator=lambda artifact: ["Invalid code"] if "generate" in artifact.code else [],
        contract_validator=lambda artifact: Stage5Agent._contract_quality_issues(None, artifact))
    return adapter, payload


def test_complete_writes_diagnostic_and_leaf_repair_preserve_every_other_field():
    adapter, payload = adapter_and_payload()
    inspection = adapter.inspect(payload)
    issue, = inspection.issues
    assert issue.expected == ["helper", "y"] and issue.actual == ["y"]
    assert "['helper']" in issue.message
    targets = adapter.targets(inspection)
    assert set(targets) == {"contract.writes"}
    merged = adapter.merge(inspection, {"patches": [{"target": "contract.writes", "replacement": ["helper", "y"]}]}, targets)
    expected = copy.deepcopy(payload)
    expected["contract"]["writes"] = ["helper", "y"]
    assert merged == expected and not adapter.inspect(merged).issues
    assert inspection.candidate == payload
    assert "COMPLETE" in adapter.context_for(inspection, targets)


def test_replacing_writes_with_missing_signals_only_remains_a_hard_error():
    adapter, payload = adapter_and_payload()
    inspection = adapter.inspect(payload)
    merged = adapter.merge(inspection, {"patches": [{"target": "contract.writes", "replacement": ["helper"]}]}, adapter.targets(inspection))
    issue, = adapter.inspect(merged).issues
    assert issue.path == "contract.writes" and "['y']" in issue.message


@pytest.mark.parametrize("field", ["writes", "reads", "clocking", "reset_behavior", "hold_behavior", "latency", "assumptions"])
def test_each_missing_contract_field_is_a_leaf_target(field):
    adapter, payload = adapter_and_payload()
    payload["contract"]["writes"] = ["helper", "y"]
    replacement = payload["contract"].pop(field)
    inspection = adapter.inspect(payload)
    targets = adapter.targets(inspection)
    assert set(targets) == {f"contract.{field}"}
    merged = adapter.merge(inspection, {"patches": [{"target": f"contract.{field}", "replacement": replacement}]}, targets)
    assert not adapter.inspect(merged).issues


def test_multiple_fields_are_repaired_together():
    adapter, payload = adapter_and_payload()
    payload["contract"]["latency"] = ""
    inspection = adapter.inspect(payload)
    targets = adapter.targets(inspection)
    assert set(targets) == {"contract.writes", "contract.latency"}
    merged = adapter.merge(inspection, {"patches": [
        {"target": "contract.writes", "replacement": ["helper", "y"]},
        {"target": "contract.latency", "replacement": "combinational"},
    ]}, targets)
    assert not adapter.inspect(merged).issues


@pytest.mark.parametrize("value", [None, "invalid", [], 7])
def test_missing_or_non_object_contract_uses_whole_target(value):
    adapter, payload = adapter_and_payload()
    payload["contract"] = value
    assert set(adapter.targets(adapter.inspect(payload))) == {"contract"}


def test_code_repair_always_requires_a_full_contract_even_when_missing():
    adapter, payload = adapter_and_payload()
    payload["code"] = "generate endgenerate"
    payload.pop("contract")
    assert set(adapter.targets(adapter.inspect(payload))) == {"code", "contract"}


def test_changed_code_contract_is_revalidated_before_acceptance():
    adapter, payload = adapter_and_payload()
    payload["code"] = "generate endgenerate"
    inspection = adapter.inspect(payload)
    targets = adapter.targets(inspection)
    assert set(targets) == {"code", "contract"}
    code = "assign helper = a;\nassign y = helper;"
    contract = copy.deepcopy(payload["contract"])
    patches = [{"target": "code", "replacement": code}, {"target": "contract", "replacement": contract}]
    merged = adapter.merge(inspection, {"patches": patches}, targets)
    assert any(issue.path == "contract.writes" for issue in adapter.inspect(merged).issues)
    contract["writes"] = ["helper", "y"]
    assert not adapter.inspect(adapter.merge(inspection, {"patches": patches}, targets)).issues


def test_invalid_list_item_selects_and_replaces_the_whole_field():
    adapter, payload = adapter_and_payload()
    payload["contract"]["writes"] = [None]
    inspection = adapter.inspect(payload)
    assert any(issue.path == "contract.writes[0]" for issue in inspection.issues)
    targets = adapter.targets(inspection)
    assert set(targets) == {"contract.writes"}
    merged = adapter.merge(inspection, {"patches": [{"target": "contract.writes", "replacement": ["helper", "y"]}]}, targets)
    assert not adapter.inspect(merged).issues


@pytest.mark.parametrize("patches", [
    [{"target": "contract.reads", "replacement": []}],
    [{"target": "contract.writes", "replacement": ["helper", "y"]}] * 2,
    [{"target": "contract", "replacement": {}}, {"target": "contract.writes", "replacement": []}],
])
def test_unknown_duplicate_and_overlapping_response_targets_are_rejected(patches):
    adapter, payload = adapter_and_payload()
    inspection = adapter.inspect(payload)
    with pytest.raises(ValueError, match="Unknown or duplicate"):
        adapter.merge(inspection, {"patches": patches}, adapter.targets(inspection))


def test_overlapping_authorized_targets_are_rejected():
    adapter, payload = adapter_and_payload()
    with pytest.raises(ValueError, match="Overlapping"):
        adapter.merge(adapter.inspect(payload), {"patches": []}, {"contract": {}, "contract.writes": {}})


def test_legacy_full_response_restores_only_absent_identity_fields():
    adapter, payload = adapter_and_payload()
    inspection = adapter.inspect(payload)
    response = copy.deepcopy(payload)
    response.pop("target")
    response["contract"]["writes"] = ["helper", "y"]
    merged = adapter.merge(inspection, response, adapter.targets(inspection))
    assert merged["target"] == payload["target"] and not adapter.inspect(merged).issues
    assert any("restored authoritative target" in change for change in adapter.merge_normalizations)
    assert "target" not in response  # never mutate the caller's response


@pytest.mark.parametrize("change", ["identity", "code", "reads"])
def test_legacy_full_response_rejects_wrong_identity_or_untargeted_content(change):
    adapter, payload = adapter_and_payload()
    inspection = adapter.inspect(payload)
    response = copy.deepcopy(payload)
    response["contract"]["writes"] = ["helper", "y"]
    if change == "identity":
        response["target"] = "wrong"
    elif change == "code":
        response["code"] += "\nassign other = a;"
    else:
        response["contract"]["reads"].append("other")
    with pytest.raises(ValueError, match="identity|untargeted"):
        adapter.merge(inspection, response, adapter.targets(inspection))
    assert adapter.merge_normalizations == []


def test_patch_rejection_diagnostics_are_saved_and_used_in_next_request(tmp_path):
    task, output, inputs, subtasks = stage5_inputs(tmp_path, count=1)
    payload = make_stage5_code_payload(task.task_id, "toy", subtasks[0], "assign y = a;")
    payload["contract"]["writes"] = []
    wrong = {"patches": [{"target": "contract", "replacement": payload["contract"]}]}
    good = {"patches": [{"target": "contract.writes", "replacement": ["y"]}]}
    backend = QueueBackend([payload, wrong, good])
    agent = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output)
    agent.run_module(task, inputs, "toy")
    draft = json.loads(next((output / ".repair_drafts").rglob("attempt_2.json")).read_text())
    diagnostics = draft["patch_diagnostics"]
    assert diagnostics["allowed_targets"] == ["contract.writes"]
    assert diagnostics["received_targets"] == ["contract"]
    assert diagnostics["reason"] == draft["patch_error"]
    assert "allowed_targets" in backend.calls[2]["user_prompt"]
    assert "received_targets" in backend.calls[2]["user_prompt"]
    assert len(backend.calls) == 3


def test_three_invalid_repairs_keep_the_previous_checkpoint(tmp_path):
    task, output, inputs, subtasks = stage5_inputs(tmp_path, count=2)
    good = make_stage5_code_payload(task.task_id, "toy", subtasks[0], "assign y = a;")
    bad = make_stage5_code_payload(task.task_id, "toy", subtasks[1], "assign z = a;")
    bad["contract"]["writes"] = []
    missing_only = {"patches": [{"target": "contract.writes", "replacement": []}]}
    backend = QueueBackend([good, bad, missing_only, missing_only])
    agent = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output)
    with pytest.raises(StageGenerationError, match="after 3 attempts"):
        agent.run_module(task, inputs, "toy")
    checkpoint = agent._read_checkpoint("toy", task.task_id)
    assert len(checkpoint["subtasks"]) == 1
    assert checkpoint["subtasks"][0]["artifact"] == SubtaskCodeArtifact.model_validate(good).model_dump()
    assert "assign z" not in agent._workspace_file("toy").read_text()


def test_stage6_reports_failure_reasons_and_checks_paths_only_for_completed(tmp_path):
    records = [
        ModuleMergeRecord(module="failed", status="failed", error="Stage5 contract rejected"),
        ModuleMergeRecord(module="blocked", status="blocked", error="Dependency failed"),
        ModuleMergeRecord(module="unexplained", status="blocked"),
        ModuleMergeRecord(module="completed", fragment_file=str(tmp_path / "completed_fragments.v"),
            merged_file=str(tmp_path / "merged" / "completed.v")),
    ]
    artifact = Stage6MergeArtifact(task_id="task", module_order=[r.module for r in records], module_files=records)
    agent = Stage6MergeAgent(PlannerLLMClient(backend=QueueBackend([])), output_root=tmp_path)
    errors = agent.validate_quality(artifact, SimpleNamespace(task_id="task"), {
        "spec_blocks": {"task_id": "task", "module_order": artifact.module_order, "modules": [
            {"module": r.module, "source_spec_file": "spec.md", "blocks": [{"block_id": "S001", "text": "source"}]} for r in records]},
    })
    assert any("failed: Stage5 contract rejected" in error for error in errors)
    assert any("blocked: Dependency failed" in error for error in errors)
    assert any("Missing failure/blocking reason" in error for error in errors)
    assert not any("merged_file" in error or "fragment_file" in error for error in errors if not error.startswith("completed:"))
    assert sum("completed:" in error and "does not exist" in error for error in errors) == 2
