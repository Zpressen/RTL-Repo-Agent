"""Generation output cannot invalidate its inputs or erase an accepted bundle."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_planner_local_repair import stage5_inputs
from test_rtl_module_planner import QueueBackend, make_stage5_code_payload
from zerorepo.rpg_gen.base.llm_client.errors import LLMRequestTimeoutError
from zerorepo.rtl_impl.module_planner.agents import Stage5Agent
from zerorepo.rtl_impl.module_planner.utils import PlannerLLMClient
from zerorepo.rtl_impl.module_planner.utils.local_repair import fingerprint
from zerorepo.rtl_impl.module_planner.utils.stage5_sources import SOURCE_VERSION, compact_stage5_interfaces, stage5_prompt_context
from zerorepo.rtl_impl.module_planner.utils.stage5_store import Stage5Store


class MutablePlanningKG:
    def __init__(self):
        self.context = {"module": {"name": "toy", "role": "Drive y", "implementation_status": "planned"}, "code_interface": []}
        self.kg_service = SimpleNamespace(mode="required")
        self.prompts = []

    def get_module_context(self, *args, **kwargs):
        return copy.deepcopy(self.context)

    def to_stage5_prompt_json(self, context, refs, max_chars=12000):
        self.prompts.append(copy.deepcopy(context))
        return json.dumps(context, sort_keys=True, separators=(",", ":"))


def test_prompt_dedup_preserves_source_identity_and_original_kg(tmp_path, monkeypatch):
    from zerorepo.rtl_impl.module_planner.agents import stage5_agent
    from zerorepo.rtl_impl.module_planner.utils.stage5_sources import stable_planning_context
    kg = MutablePlanningKG()
    kg.context["specs"] = [{"relation": {"local_ref": "S001", "relevance_reason": "duplicated prose",
        "input_fingerprint": "old-binding"}, "fragment": {"text": "original specification", "source_file": "spec.md"}}]
    original = copy.deepcopy(kg.context)
    task, output, inputs, _, _, backend, agent = setup_agent(tmp_path, kg=kg)
    with monkeypatch.context() as patch:
        patch.setattr(stage5_agent, "stage5_prompt_context", stable_planning_context)
        agent.run_module(task, inputs, "toy")
    marker = agent._read_checkpoint("toy")
    resumed = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output, planning_context_retriever=kg)
    assert resumed.run_module(task, inputs, "toy", reuse_only=True).status == "completed"
    assert resumed._read_checkpoint("toy") == marker and len(backend.calls) == 1
    assert kg.context == original
    compact = stage5_prompt_context(original)
    assert compact["specs"][0] == {"relation": {"local_ref": "S001"}, "fragment": {}}
    assert compact["module"]["role"] == original["module"]["role"]


def test_kg_dedup_leaves_budget_for_complete_child_interface():
    from zerorepo.rtl_impl.kg_agent.planning_graph import PlanningContextRetriever
    original = {"module": {"name": "toy", "planned_children": ["leaf"]},
        "specs": [{"relation": {"local_ref": f"S{i:03d}", "input_fingerprint": "f"*400},
                   "fragment": {"content_hash": "h"*64, "source_file": "p"*150}} for i in range(23)],
        "child_code_interfaces": [{"module": "leaf", "ports": [
            {"name": f"port_{i:03d}", "direction": "input", "width": "32"} for i in range(100)]}]}
    refs = [f"S{i:03d}" for i in range(23)]
    old = json.loads(PlanningContextRetriever.to_stage5_prompt_json(original, refs))
    new = json.loads(compact_stage5_interfaces(PlanningContextRetriever.to_stage5_prompt_json(
        stage5_prompt_context(original), refs), original["child_code_interfaces"]))
    assert not old["child_code_interfaces"] or len(old["child_code_interfaces"][0]["ports"]) < 100
    assert len(new["child_code_interfaces"][0]["ports"]) == 100
    assert new["child_code_interfaces"][0]["ports"][-1] == ["port_099", "input", "32"]
    assert [s["local_ref"] for s in new["selected_spec_links"]] == refs
    assert not new.get("truncated")


def setup_agent(tmp_path, count=1, kg=None):
    task, output, inputs, tasks = stage5_inputs(tmp_path, count=count)
    payloads = [make_stage5_code_payload(task.task_id, "toy", s, f"assign y{i} = a;") for i, s in enumerate(tasks)]
    backend = QueueBackend(payloads)
    agent = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output, planning_context_retriever=kg)
    return task, output, inputs, tasks, payloads, backend, agent


def test_kg_materialization_and_removal_survive_restarts_without_requests(tmp_path):
    kg = MutablePlanningKG()
    task, output, inputs, _, _, backend, agent = setup_agent(tmp_path, kg=kg)
    agent.run_module(task, inputs, "toy")
    kg.context["module"].update(implementation_status="materialized", actual_path="toy.v")
    kg.context["code_interface"] = [{"name": "unexpected_old_output", "direction": "output"}]
    for _ in range(2):
        resumed = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output, planning_context_retriever=kg)
        assert resumed.run_module(task, inputs, "toy", reuse_only=True).status == "completed"
        kg.context["module"].pop("actual_path", None)
        kg.context["module"]["implementation_status"] = "planned"
        kg.context["code_interface"] = []
    assert len(backend.calls) == 1
    prompt = backend.calls[0]["user_prompt"]
    assert '"implementation_status"' not in prompt and '"actual_path"' not in prompt
    checkpoint = agent._read_checkpoint("toy")
    assert checkpoint["subtasks"][0]["fingerprint_version"] == SOURCE_VERSION


def test_child_ports_are_untruncated_sorted_authoritative_inputs(tmp_path):
    kg = MutablePlanningKG()
    task, output, inputs, _, _, backend, agent = setup_agent(tmp_path, kg=kg)
    inputs["stage2"] = {"modules": [{"module": "toy", "role": "Drive y", "children": ["child"]}]}
    child = agent.workspace_root / "merged" / "child.v"
    child.parent.mkdir(parents=True)
    child.write_text("module child(input a, output [3:0] y); endmodule\n")
    agent.run_module(task, inputs, "toy")
    child.write_text("module child(output [3:0] y, input a); endmodule\n")
    assert agent.run_module(task, inputs, "toy", reuse_only=True).status == "completed"
    child.write_text("module child(output [7:0] y, input a); endmodule\n")
    with pytest.raises(ValueError, match="stale"):
        agent.run_module(task, inputs, "toy", reuse_only=True)
    assert len(backend.calls) == 1


def test_full_skeleton_behavior_changes_invalidate_even_with_same_frame(tmp_path, monkeypatch):
    task, _, inputs, _, _, backend, agent = setup_agent(tmp_path)
    doc = tmp_path / "skeleton.md"
    doc.write_text("module toy; endmodule\nBehavior: synchronous reset\n")
    monkeypatch.setattr(agent, "_read_module_skeleton_context", lambda record: ("module toy; endmodule", str(doc)))
    agent.run_module(task, inputs, "toy")
    doc.write_text("module toy; endmodule\nBehavior: asynchronous reset\n")
    with pytest.raises(ValueError, match="stale"):
        agent.run_module(task, inputs, "toy", reuse_only=True)
    assert len(backend.calls) == 1


@pytest.mark.parametrize("component", ["spec", "role", "plan", "snapshot_corrupt"])
def test_true_source_changes_and_source_checksum_fail_closed(tmp_path, component):
    task, output, inputs, _, _, backend, agent = setup_agent(tmp_path)
    inputs["stage2"] = {"modules": [{"module": "toy", "role": "Original", "children": []}]}
    agent.run_module(task, inputs, "toy")
    if component == "spec":
        inputs["spec_blocks"]["modules"][0]["blocks"][0]["text"] = "Changed requirement"
    elif component == "role":
        inputs["stage2"]["modules"][0]["role"] = "Changed responsibility"
    elif component == "plan":
        path = output / "module_plan_json" / "toy.json"
        data = json.loads(path.read_text()); data["subtasks"][0]["constraints"] = ["Changed"]
        path.write_text(json.dumps(data))
    else:
        marker = agent._checkpoint_file("toy")
        data = json.loads(marker.read_text()); data["subtasks"][0]["source_snapshot"]["skeleton"] = "tampered"
        marker.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        agent.run_module(task, inputs, "toy", reuse_only=True)
    assert len(backend.calls) == 1


def test_failed_new_generation_preserves_complete_files_and_resumes_candidate(tmp_path):
    task, output, inputs, tasks, payloads, _, agent = setup_agent(tmp_path, count=3)
    agent.run_module(task, inputs, "toy")
    paths = [agent._checkpoint_file("toy"), agent._workspace_file("toy"), agent._contracts_file("toy")]
    before = [p.read_bytes() for p in paths]
    plan_path = output / "module_plan_json" / "toy.json"
    plan = json.loads(plan_path.read_text()); plan["subtasks"][1]["constraints"] = ["New source"]
    plan_path.write_text(json.dumps(plan))
    backend = QueueBackend([payloads[1]])
    original = backend.complete_with_memory
    calls = 0
    def complete(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise LLMRequestTimeoutError("simulated timeout")
        return original(**kwargs)
    backend.complete_with_memory = complete
    failed = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output)
    with pytest.raises(LLMRequestTimeoutError):
        failed.run_module(task, inputs, "toy")
    assert [p.read_bytes() for p in paths] == before
    assert agent._read_checkpoint("toy")["status"] == "completed"
    resumed_backend = QueueBackend([payloads[2]])
    resumed = Stage5Agent(PlannerLLMClient(backend=resumed_backend), output_root=output)
    assert resumed.run_module(task, inputs, "toy").completed_subtasks == ["B1", "B2", "B3"]
    assert len(resumed_backend.calls) == 1


@pytest.mark.parametrize("failure_point", ["contracts", "marker"])
def test_crash_during_publication_restores_previous_complete_bundle(tmp_path, monkeypatch, failure_point):
    task, output, inputs, _, _, _, agent = setup_agent(tmp_path)
    agent.run_module(task, inputs, "toy")
    before = agent._workspace_file("toy").read_text()
    current = agent._read_checkpoint("toy")
    if failure_point == "contracts":
        monkeypatch.setattr(agent, "_write_contracts_file", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("interrupted")))
    else:
        from zerorepo.rtl_impl.module_planner.agents import stage5_agent
        original = stage5_agent.atomic_write_json
        def write(path, value):
            if path == agent._checkpoint_file("toy"):
                raise OSError("interrupted")
            original(path, value)
        monkeypatch.setattr(stage5_agent, "atomic_write_json", write)
    with pytest.raises(OSError):
        agent._commit_subtasks(module_name="toy", task_id=task.task_id, entries=current["subtasks"],
            fragments="different incomplete aliases\n", contracts=[], input_fingerprint="different", complete=True)
    assert agent._read_checkpoint("toy") == current
    assert agent._workspace_file("toy").read_text() == before


def test_bundle_corruption_is_not_accepted(tmp_path):
    task, _, inputs, _, _, _, agent = setup_agent(tmp_path)
    agent.run_module(task, inputs, "toy")
    marker = agent._read_checkpoint("toy")
    bundle = agent.workspace_root / marker["bundle_path"] / "toy_fragments.v"
    bundle.write_text("tampered")
    assert agent._read_checkpoint("toy") == {}


@pytest.mark.parametrize("valid", [True, False])
def test_legacy_migration_requires_reproducible_old_source_hash(tmp_path, valid):
    task, _, inputs, _, _, backend, agent = setup_agent(tmp_path)
    agent.run_module(task, inputs, "toy")
    marker = agent._read_checkpoint("toy")
    entry = marker["subtasks"][0]
    source = entry["source_snapshot"]
    old = {k: v for k, v in source.items() if k not in {"fingerprint_version", "responsibility", "child_interfaces"}}
    old["planning_kg"] = ""
    entry["input_fingerprint"] = fingerprint(old) if valid else "unknown"
    for key in ["fingerprint_version", "source_fingerprint", "source_snapshot"]:
        entry.pop(key)
    marker.pop("bundle_path")
    agent._checkpoint_file("toy").write_text(json.dumps(marker))
    if valid:
        assert agent.run_module(task, inputs, "toy", reuse_only=True).status == "completed"
        assert agent._read_checkpoint("toy")["subtasks"][0]["migration_evidence"]["kind"] == "legacy_hash_verified"
    else:
        with pytest.raises(ValueError, match="stale"):
            agent.run_module(task, inputs, "toy", reuse_only=True)
    assert len(backend.calls) == 1
