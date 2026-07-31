from __future__ import annotations

import json
from pathlib import Path

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
                "file_path": "rtl/leaf.v",
                "role": "worker",
                "kind": "leaf_combinational",
                "parents": ["top"],
                "children": [],
            },
            {
                "module": "top",
                "file_path": "rtl/top.v",
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
        "file_path": f"rtl/{module}.v",
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
        {"task_id": "t1"}, "top", context, artifact_path="module_spec_context_json/top.json"
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
                "expected_path": "rtl/top.v",
                "planned_children": ["leaf"],
                "implementation_status": "planned",
            }
        ],
        "edges": [],
    }
    service.planning_projection_path.write_text(json.dumps(projection), encoding="utf-8")
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
    assert module["expected_path"] == "rtl/top.v"
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
    rtl.write_text("module top(input a, output y); assign y = a; endmodule\n", encoding="utf-8")
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
    (tmp_path / "a.v").write_text("module same; endmodule\n", encoding="utf-8")
    (tmp_path / "b.v").write_text("module same; endmodule\n", encoding="utf-8")
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
