from __future__ import annotations

import json
from pathlib import Path
from rtl_artifact_test_utils import write_artifact_text

import pytest

from zerorepo.config.checkpoint_config import CheckpointManager
from zerorepo.rtl_impl.kg_agent.planning_graph import PlanningContextRetriever, PlanningGraphWriter
from zerorepo.rtl_impl.rtl_kg.graph_types_rtl import canonical_module_uid
from zerorepo.rtl_impl.rtl_kg import KnowledgeGraphRTL
from zerorepo.rtl_impl.rtl_kg_service import RTLKgService


class FakeKgService:
    enabled = True
    mode = "required"
    repo_uid = "demo@unit"

    def __init__(self, projection_path: Path):
        self.planning_projection_path = projection_path
        self.upserts = []
        self.query_rows = []

    def is_enabled(self):
        return True

    def upsert_planning_projection(self, nodes, edges):
        self.upserts.append((list(nodes), list(edges)))
        return {"nodes_input": len(nodes), "edges_input": len(edges)}

    def query(self, cypher, params=None, limit=None):
        if "RETURN p.name AS name" in cypher:
            return {"rows": []}
        return {"rows": list(self.query_rows)}


def _repo_skeleton():
    return {
        "task_id": "t1",
        "input_fingerprint": "stage2-fp",
        "top_module": "top",
        "module_order": ["leaf", "top"],
        "modules": [
            {
                "module": "leaf",
                "file_path": "generate/rtl/leaf.v",
                "role": "worker",
                "kind": "leaf_combinational",
                "parents": ["top"],
                "children": [],
            },
            {
                "module": "top",
                "file_path": "generate/rtl/top.v",
                "role": "controller",
                "kind": "top_controller",
                "parents": [],
                "children": ["leaf"],
            },
        ],
    }


def _skeleton(module="top"):
    return {
        "schema_version": "module_skeleton_export_v1",
        "module": module,
        "file_path": f"generate/rtl/{module}.v",
        "structural_blocks": [
            {"block_id": "B1", "block_kind": "decl"},
            {"block_id": "B2", "block_kind": "inst"},
        ],
        "module_behavior": {"control_style": "purely_combinational"},
    }


def _plan(module="top"):
    return {
        "schema_version": "module_plan_v1",
        "module": module,
        "subtasks": [
            {
                "id": "S1",
                "spec_refs": ["S001"],
                "timing_obligation_ids": ["T1"],
            }
        ],
    }


def _seven_module_sidecars(tmp_path):
    names = [f"m{index}" for index in range(7)]
    repo = {"input_fingerprint": "stage2-fp", "top_module": names[-1], "module_order": names,
            "modules": [{"module": name, "file_path": f"generate/rtl/{name}.v"} for name in names]}
    skeletons = {"input_fingerprint": "stage3-fp", "module_records": []}
    plans = {"input_fingerprint": "stage4-fp", "module_plan_files": []}
    for name in names:
        spec_file = f"plan/stage3/modules/{name}/spec_context.json"
        export_file = f"plan/stage3/modules/{name}/skeleton.json"
        plan_file = f"plan/stage4/modules/{name}/plan.json"
        write_artifact_text(tmp_path / spec_file, json.dumps({"blocks": [{"block_id": "S1",
            "text": f"Behavior for {name}", "source_file": "spec.md", "source_chunk_ids": [name]}]}))
        write_artifact_text(tmp_path / export_file, json.dumps(_skeleton(name)))
        write_artifact_text(tmp_path / plan_file, json.dumps(_plan(name)))
        skeletons["module_records"].append({"module": name, "spec_context_file": spec_file, "export_file": export_file})
        plans["module_plan_files"].append({"module": name, "plan_file": plan_file})
    return repo, skeletons, plans


def test_seven_module_rebuild_syncs_once_and_skips_unchanged_writes(tmp_path, monkeypatch):
    from zerorepo.rtl_impl.module_planner.utils import artifact_store
    repo, skeletons, plans = _seven_module_sidecars(tmp_path)
    service = FakeKgService(tmp_path / "projection.json")
    writer = PlanningGraphWriter(service, tmp_path)
    writes = []
    original_write = artifact_store.atomic_write_json
    def record_write(path, payload):
        writes.append(path)
        original_write(path, payload)
    monkeypatch.setattr(artifact_store, "atomic_write_json", record_write)
    writer.ensure_projection({}, repo, skeletons, plans)
    assert len(service.upserts) == 1
    nodes, edges = service.upserts[0]
    assert len(nodes) == 28 and len(edges) == 21
    assert len({node["uid"] for node in nodes}) == 28
    assert len([n for n in nodes if n["kind"] == "ModulePlan"]) == 7
    initial_writes = len(writes)
    assert initial_writes > 0
    writer.ensure_projection({}, repo, skeletons, plans)
    assert len(service.upserts) == 1
    assert len(writes) == initial_writes


@pytest.mark.parametrize("mode", ["required", "optional"])
def test_failed_batch_keeps_local_progress_and_retries_same_snapshot(tmp_path, mode):
    class FailOnce(FakeKgService):
        attempts = 0
        def upsert_planning_projection(self, nodes, edges):
            self.attempts += 1
            if self.attempts == 1:
                raise RuntimeError("Neo4j unavailable")
            return super().upsert_planning_projection(nodes, edges)
    repo, skeletons, plans = _seven_module_sidecars(tmp_path)
    service = FailOnce(tmp_path / "projection.json")
    service.mode = mode
    writer = PlanningGraphWriter(service, tmp_path)
    if mode == "required":
        with pytest.raises(RuntimeError, match="Neo4j unavailable"):
            writer.ensure_projection({}, repo, skeletons, plans)
    else:
        writer.ensure_projection({}, repo, skeletons, plans)
    local = json.loads(service.planning_projection_path.read_text())
    assert len([n for n in local["nodes"] if n["kind"] == "ModulePlan"]) == 7
    writer.ensure_projection({}, repo, skeletons, plans)
    assert service.attempts == 2 and len(service.upserts) == 1
    writer.ensure_projection({}, repo, skeletons, plans)
    assert service.attempts == 2


def test_partial_sync_failure_invalidates_old_acknowledgement(tmp_path):
    class PartialFailure(FakeKgService):
        attempts = 0
        def upsert_planning_projection(self, nodes, edges):
            self.attempts += 1
            # Treat the failed update as potentially applied before the error.
            result = super().upsert_planning_projection(nodes, edges)
            if self.attempts == 2:
                raise RuntimeError("connection lost after writing nodes")
            return result
    service = PartialFailure(tmp_path / "projection.json")
    writer = PlanningGraphWriter(service, tmp_path)
    original = _repo_skeleton()
    writer.upsert_module_anchors({}, original)
    changed = _repo_skeleton()
    changed["modules"][0]["role"] = "changed"
    with pytest.raises(RuntimeError, match="connection lost"):
        writer.upsert_module_anchors({}, changed)
    writer.upsert_module_anchors({}, original)
    assert service.attempts == 3
    assert next(n for n in service.upserts[-1][0] if n["name"] == "leaf")["role"] == "worker"


def test_new_writer_or_run_resynchronizes_even_when_local_snapshot_matches(tmp_path):
    repo, skeletons, plans = _seven_module_sidecars(tmp_path)
    service = FakeKgService(tmp_path / "projection.json")
    PlanningGraphWriter(service, tmp_path).ensure_projection({}, repo, skeletons, plans)
    restored = PlanningGraphWriter(service, tmp_path)
    restored.ensure_projection({}, repo, skeletons, plans)
    assert len(service.upserts) == 2
    restored.begin_run()
    restored.ensure_projection({}, repo, skeletons, plans)
    assert len(service.upserts) == 3


def test_changed_spec_syncs_full_snapshot_including_removal(tmp_path):
    repo, skeletons, plans = _seven_module_sidecars(tmp_path)
    service = FakeKgService(tmp_path / "projection.json")
    writer = PlanningGraphWriter(service, tmp_path)
    writer.ensure_projection({}, repo, skeletons, plans)
    old_ids = {n["uid"] for n in service.upserts[-1][0] if n["kind"] == "SpecFragment"}
    spec = tmp_path / skeletons["module_records"][0]["spec_context_file"]
    write_artifact_text(spec, json.dumps({"blocks": []}))
    writer.ensure_projection({}, repo, skeletons, plans)
    assert len(service.upserts) == 2
    nodes, edges = service.upserts[-1]
    assert len(old_ids - {n["uid"] for n in nodes}) == 1
    assert len([n for n in nodes if n["kind"] == "Module"]) == 7
    assert len([n for n in nodes if n["kind"] == "ModulePlan"]) == 7
    persisted = json.loads(service.planning_projection_path.read_text())
    assert nodes == persisted["nodes"] and edges == persisted["edges"]


def test_runner_defers_module_sync_and_reuses_completed_planning(tmp_path):
    from test_responsibility_refinement import scenario, report
    services = []
    def attach(runner):
        service = FakeKgService(runner.output_root / "plan/state/kg/planning_kg_projection.json")
        services.append(service)
        runner.planning_graph_writer = PlanningGraphWriter(service, runner.output_root)
    case = scenario(tmp_path, before_run=attach)
    task, runner, backend, *_ = case
    service = services[0]
    assert report(case)["status"] == "passed"
    assert len(service.upserts) == 3  # Once at each of Stage2, Stage3 and Stage4.
    kinds = [{node["kind"] for node in nodes} for nodes, _edges in service.upserts]
    assert kinds[0] == {"Module"}
    assert "ModuleSkeleton" in kinds[1] and "ModulePlan" not in kinds[1]
    assert "ModulePlan" in kinds[2]
    calls = len(backend.calls)
    runner.run(task, resume=True, end_stage="stage4")
    assert len(backend.calls) == calls
    assert len(service.upserts) == 4  # One fresh acknowledgement for the new run.


def test_planning_projection_is_module_centered_and_idempotent(tmp_path):
    service = FakeKgService(tmp_path / "planning_kg_projection.json")
    writer = PlanningGraphWriter(service, tmp_path)
    writer.upsert_module_anchors({"task_id": "t1"}, _repo_skeleton())
    context = {
        "module": "top",
        "blocks": [
            {
                "block_id": "S001",
                "text": "The top module instantiates leaf.",
                "source_file": "spec.md",
                "source_chunk_ids": ["C1"],
                "confidence": "high",
            }
        ],
    }
    writer.upsert_spec_fragments(
        {"task_id": "t1"}, "top", context, artifact_path="plan/stage3/modules/top/spec_context.json"
    )
    writer.upsert_module_skeleton({"task_id": "t1"}, "top", _skeleton(), input_fingerprint="s3")
    writer.upsert_module_plan({"task_id": "t1"}, "top", _plan(), input_fingerprint="s4")
    # A replay overwrites current nodes/edges instead of creating history nodes.
    writer.upsert_module_plan({"task_id": "t1"}, "top", _plan(), input_fingerprint="s4")

    projection = json.loads(service.planning_projection_path.read_text(encoding="utf-8"))
    modules = [item for item in projection["nodes"] if item["kind"] == "Module"]
    assert {item["uid"] for item in modules} == {
        "demo@unit:module:leaf",
        "demo@unit:module:top",
    }
    top = next(item for item in modules if item["name"] == "top")
    assert top["planned_children"] == ["leaf"]
    assert top["generation_rank"] == 1
    assert {item["type"] for item in projection["edges"]} == {
        "SPECIFIES",
        "HAS_SKELETON",
        "HAS_PLAN",
    }
    assert not {"DERIVED_FROM", "REFINES"} & {item["type"] for item in projection["edges"]}
    spec_edge = next(item for item in projection["edges"] if item["type"] == "SPECIFIES")
    assert spec_edge["local_ref"] == "S001"
    assert "S001" not in spec_edge["source"]
    assert len([item for item in projection["nodes"] if item["kind"] == "ModulePlan"]) == 1


def test_shared_fragment_uid_and_stale_edges_are_cleaned(tmp_path):
    service = FakeKgService(tmp_path / "planning_kg_projection.json")
    writer = PlanningGraphWriter(service, tmp_path)
    writer.upsert_module_anchors({"task_id": "t1"}, _repo_skeleton())
    shared = {
        "blocks": [
            {
                "block_id": "S001",
                "text": "Shared reset requirement.",
                "source_file": "spec.md",
                "source_chunk_ids": ["C7"],
            }
        ]
    }
    writer.upsert_spec_fragments({}, "leaf", shared)
    writer.upsert_spec_fragments({}, "top", shared)
    projection = json.loads(service.planning_projection_path.read_text(encoding="utf-8"))
    assert len([item for item in projection["nodes"] if item["kind"] == "SpecFragment"]) == 1
    assert len([item for item in projection["edges"] if item["type"] == "SPECIFIES"]) == 2

    writer.upsert_spec_fragments({}, "leaf", {"blocks": []})
    projection = json.loads(service.planning_projection_path.read_text(encoding="utf-8"))
    assert len([item for item in projection["nodes"] if item["kind"] == "SpecFragment"]) == 1
    assert len([item for item in projection["edges"] if item["type"] == "SPECIFIES"]) == 1


def test_new_stage2_fingerprint_invalidates_downstream_projection(tmp_path):
    service = FakeKgService(tmp_path / "planning_kg_projection.json")
    writer = PlanningGraphWriter(service, tmp_path)
    skeleton = _repo_skeleton()
    writer.upsert_module_anchors({}, skeleton)
    writer.upsert_module_skeleton({}, "top", _skeleton(), input_fingerprint="old-s3")
    writer.upsert_module_plan({}, "top", _plan(), input_fingerprint="old-s4")

    changed = _repo_skeleton()
    changed["input_fingerprint"] = "new-stage2-fp"
    writer.upsert_module_anchors({}, changed)
    projection = json.loads(service.planning_projection_path.read_text(encoding="utf-8"))
    assert {item["kind"] for item in projection["nodes"]} == {"Module"}
    assert projection["edges"] == []


def test_plan_bound_to_stale_skeleton_is_rejected(tmp_path):
    service = FakeKgService(tmp_path / "planning_kg_projection.json")
    service.query_rows = [
        {
            "module": {"name": "top", "stage2_fingerprint": "s2"},
            "specs": [{"fragment": {"content_hash": "h"}, "relation": {"local_ref": "S001"}}],
            "skeleton": {"content_hash": "new", "input_fingerprint": "s3"},
            "plan": {"skeleton_content_hash": "old", "input_fingerprint": "s4"},
        }
    ]
    retriever = PlanningContextRetriever(service, tmp_path)
    with pytest.raises(ValueError, match="stale ModuleSkeleton"):
        retriever.get_module_context("top", require_spec=True, require_skeleton=True, require_plan=True)


def test_stage5_planning_context_keeps_only_selected_links_and_unique_metadata(tmp_path):
    context = {
        "module": {
            "name": "top",
            "role": "controller",
            "module_kind": "top_controller",
            "planned_children": ["leaf"],
            "stage2_fingerprint": "s2",
            "uid": "large-internal-uid",
            "attrs": "duplicated internal metadata",
        },
        "specs": [
            {
                "fragment": {
                    "content_hash": "h1",
                    "source_file": "spec.md",
                    "text": "SELECTED_SPEC_BODY_MUST_NOT_BE_DUPLICATED",
                },
                "relation": {
                    "local_ref": "S001",
                    "confidence": "high",
                    "relevance_reason": "current behavior",
                    "input_fingerprint": "spec-fp",
                },
            },
            {
                "fragment": {"content_hash": "h2", "text": "UNRELATED_SPEC_BODY"},
                "relation": {"local_ref": "S999"},
            },
        ],
        "skeleton": {
            "artifact_path": "plan/stage3/modules/top/skeleton.json",
            "content_hash": "sk-hash",
            "input_fingerprint": "s3",
        },
        "plan": {
            "artifact_path": "plan/stage4/modules/top/plan.json",
            "content_hash": "plan-hash",
            "input_fingerprint": "s4",
            "skeleton_content_hash": "sk-hash",
        },
        "skeleton_artifact": {"large": "x" * 20000},
        "plan_artifact": {"large": "y" * 20000},
        "code_interface": [
            {"name": "clk", "direction": "input", "width": "1", "path": "top.clk"}
        ],
        "child_code_interfaces": [
            {
                "module": "leaf",
                "actual_path": "generate/rtl/leaf.v",
                "implementation_status": "planned",
                "ports": [{"name": "a", "direction": "input", "width": "8"}],
            },
            {"module": "unplanned", "ports": [{"name": "ignored"}]},
        ],
    }

    text = PlanningContextRetriever.to_stage5_prompt_json(context, ["S001"], max_chars=12000)
    payload = json.loads(text)

    assert len(text) <= 12000
    assert [item["local_ref"] for item in payload["selected_spec_links"]] == ["S001"]
    assert payload["code_interface"][0]["name"] == "clk"
    assert [item["module"] for item in payload["child_code_interfaces"]] == ["leaf"]
    assert "SELECTED_SPEC_BODY_MUST_NOT_BE_DUPLICATED" not in text
    assert "UNRELATED_SPEC_BODY" not in text
    assert "skeleton_artifact" not in text
    assert "plan_artifact" not in text
    assert "large-internal-uid" not in text


def test_stage5_planning_context_budget_always_returns_valid_json():
    context = {
        "module": {"name": "wide", "planned_children": ["leaf"]},
        "specs": [],
        "skeleton": {"content_hash": "sk"},
        "plan": {"content_hash": "plan"},
        "code_interface": [
            {"name": f"port_{index:03d}", "direction": "input", "width": "32", "path": "p" * 80}
            for index in range(100)
        ],
        "child_code_interfaces": [
            {
                "module": "leaf",
                "ports": [
                    {"name": f"child_port_{index:03d}", "direction": "output", "width": "64"}
                    for index in range(100)
                ],
            }
        ],
    }

    text = PlanningContextRetriever.to_stage5_prompt_json(context, [], max_chars=600)
    payload = json.loads(text)

    assert len(text) <= 600
    assert payload["module"]["name"] == "wide"
    assert payload["truncated"] is True
    assert payload["omitted_count"]


def test_code_snapshot_merges_into_planned_module_uid(tmp_path):
    checkpoint = CheckpointManager(tmp_path)
    service = RTLKgService(
        repo_path=tmp_path / "rtl",
        checkpoint_manager=checkpoint,
        repo_data={},
        config={"enabled": False},
    )
    service._repo_uid = "demo@unit"
    projection = {
        "schema_version": "planning_kg_projection_v1",
        "repo_uid": "demo@unit",
        "nodes": [
            {
                "uid": "demo@unit:module:top",
                "repo_uid": "demo@unit",
                "kind": "Module",
                "name": "top",
                "expected_path": "generate/rtl/top.v",
                "planned_children": ["leaf"],
                "implementation_status": "planned",
            }
        ],
        "edges": [],
    }
    write_artifact_text(service.planning_projection_path, json.dumps(projection), encoding="utf-8")
    nodes, _ = service._merge_planning_projection(
        [
            {
                "uid": "demo@unit:module:top",
                "repo_uid": "demo@unit",
                "kind": "Module",
                "name": "top",
                "path": "top.v",
                "sl": 1,
                "el": 3,
                "h": "abc",
            }
        ],
        [],
    )
    module = next(item for item in nodes if item["kind"] == "Module")
    assert module["uid"] == canonical_module_uid("demo@unit", "top")
    assert module["expected_path"] == "generate/rtl/top.v"
    assert module["actual_path"] == "top.v"
    assert module["planned_children"] == ["leaf"]
    assert module["implementation_status"] == "materialized"


def test_text_fallback_uses_same_canonical_module_uid(tmp_path):
    service = RTLKgService(
        repo_path=tmp_path,
        checkpoint_manager=CheckpointManager(tmp_path / ".checkpoint"),
        repo_data={},
        config={"enabled": False},
    )
    service._repo_uid = "demo@unit"
    module = {
        "name": "top",
        "path": "generated/top.v",
        "text": "module top(input a, output y); assign y = a; endmodule",
        "sl": 1,
        "el": 1,
        "h": "abc",
    }
    file_node = {"uid": "demo@unit:file:generated/top.v"}
    nodes, _ = service._fallback_module_graph(module=module, file_node=file_node)
    assert nodes[0]["uid"] == canonical_module_uid("demo@unit", "top")


def test_tree_sitter_and_text_fallback_module_uids_match(tmp_path):
    rtl = tmp_path / "nested" / "top.v"
    rtl.parent.mkdir()
    write_artifact_text(rtl, "module top(input a, output y); assign y = a; endmodule\n", encoding="utf-8")
    graph = KnowledgeGraphRTL.build(tmp_path)
    parsed = next(item for item in graph.neo4j_nodes() if item.get("kind") == "Module")

    service = RTLKgService(
        repo_path=tmp_path,
        checkpoint_manager=CheckpointManager(tmp_path / ".checkpoint"),
        repo_data={},
        config={"enabled": False},
    )
    service._repo_uid = graph.repo_uid
    fallback, _ = service._fallback_module_graph(
        module={
            "name": "top",
            "path": "a/different/path.v",
            "text": rtl.read_text(encoding="utf-8"),
            "sl": 1,
            "el": 1,
            "h": "abc",
        },
        file_node={"uid": f"{graph.repo_uid}:file:a/different/path.v"},
    )
    assert parsed["uid"] == fallback[0]["uid"] == canonical_module_uid(graph.repo_uid, "top")


def test_duplicate_rtl_module_definitions_are_rejected(tmp_path):
    write_artifact_text(tmp_path / "a.v", "module same; endmodule\n", encoding="utf-8")
    write_artifact_text(tmp_path / "b.v", "module same; endmodule\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate RTL Module definition"):
        KnowledgeGraphRTL.build(tmp_path)


def test_stage6_code_filter_excludes_syntax_failed_files(tmp_path):
    service = RTLKgService(
        repo_path=tmp_path,
        checkpoint_manager=CheckpointManager(tmp_path / ".checkpoint"),
        repo_data={},
        config={"enabled": False},
    )
    nodes = [
        {"uid": "repo", "kind": "Repo"},
        {"uid": "good-file", "kind": "File", "path": "good.v"},
        {"uid": "bad-file", "kind": "File", "path": "bad.v"},
        {"uid": "good-module", "kind": "Module", "name": "good"},
        {"uid": "bad-module", "kind": "Module", "name": "bad"},
    ]
    edges = [
        {"source_uid": "good-file", "target_uid": "good-module", "type": "DEFINES"},
        {"source_uid": "bad-file", "target_uid": "bad-module", "type": "DEFINES"},
    ]
    filtered_nodes, filtered_edges = service._filter_snapshot_to_file_paths(nodes, edges, {"good.v"})
    assert {item["uid"] for item in filtered_nodes} == {"repo", "good-file", "good-module"}
    assert len(filtered_edges) == 1
