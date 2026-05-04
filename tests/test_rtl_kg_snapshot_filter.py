from pathlib import Path

from zerorepo.config.checkpoint_config import CheckpointManager
from zerorepo.rtl_impl.rtl_kg import RTLKgService


def test_rtl_kg_snapshot_filter_keeps_only_planned_skeleton_paths(tmp_path):
    repo_path = tmp_path / "repo"
    repo_path.mkdir()
    ckpt_dir = tmp_path / ".zerorepo"
    manager = CheckpointManager(ckpt_dir)
    repo_data = {
        "rtl_metadata": {
            "files": {
                "top.v": "",
                "sub/leaf.v": "",
            },
            "file_specs": [
                {"file_path": "top.v"},
                {"file_path": "sub/leaf.v"},
            ],
        }
    }
    service = RTLKgService(
        repo_path=repo_path,
        checkpoint_manager=manager,
        repo_data=repo_data,
        config={},
    )

    nodes = [
        {"uid": "repo", "kind": "Repo", "name": "repo"},
        {"uid": "root", "kind": "File", "path": ".", "name": "repo", "attrs": {"is_dir": True}},
        {"uid": "top-file", "kind": "File", "path": "top.v", "name": "top.v"},
        {"uid": "sub-dir", "kind": "File", "path": "sub", "name": "sub", "attrs": {"is_dir": True}},
        {"uid": "leaf-file", "kind": "File", "path": "sub/leaf.v", "name": "leaf.v"},
        {"uid": "ckpt-dir", "kind": "File", "path": ".zerorepo", "name": ".zerorepo", "attrs": {"is_dir": True}},
        {"uid": "ckpt-file", "kind": "File", "path": ".zerorepo/spec_facts.json", "name": "spec_facts.json"},
        {"uid": "top-mod", "kind": "Module", "path": "top.v", "name": "top"},
        {"uid": "ckpt-mod", "kind": "Module", "path": ".zerorepo/spec_facts.json", "name": "bad"},
    ]
    edges = [
        {"source": {"uid": "repo"}, "target": {"uid": "root"}, "eid": "e1"},
        {"source": {"uid": "root"}, "target": {"uid": "top-file"}, "eid": "e2"},
        {"source": {"uid": "root"}, "target": {"uid": "sub-dir"}, "eid": "e3"},
        {"source": {"uid": "sub-dir"}, "target": {"uid": "leaf-file"}, "eid": "e4"},
        {"source": {"uid": "root"}, "target": {"uid": "ckpt-dir"}, "eid": "e5"},
        {"source": {"uid": "ckpt-dir"}, "target": {"uid": "ckpt-file"}, "eid": "e6"},
        {"source": {"uid": "top-file"}, "target": {"uid": "top-mod"}, "eid": "e7"},
        {"source": {"uid": "ckpt-file"}, "target": {"uid": "ckpt-mod"}, "eid": "e8"},
    ]

    filtered_nodes, filtered_edges = service._filter_snapshot_to_planned_skeleton(nodes, edges)
    kept_uids = {node["uid"] for node in filtered_nodes}

    assert "repo" in kept_uids
    assert "root" in kept_uids
    assert "top-file" in kept_uids
    assert "sub-dir" in kept_uids
    assert "leaf-file" in kept_uids
    assert "top-mod" in kept_uids

    assert "ckpt-dir" not in kept_uids
    assert "ckpt-file" not in kept_uids
    assert "ckpt-mod" not in kept_uids

    kept_edge_ids = {edge["eid"] for edge in filtered_edges}
    assert "e1" in kept_edge_ids
    assert "e2" in kept_edge_ids
    assert "e3" in kept_edge_ids
    assert "e4" in kept_edge_ids
    assert "e7" in kept_edge_ids
    assert "e5" not in kept_edge_ids
    assert "e6" not in kept_edge_ids
    assert "e8" not in kept_edge_ids
