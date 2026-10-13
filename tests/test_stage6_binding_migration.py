"""Parent RTL reuse needs a bound historical dependency tree and equal ports."""
import hashlib
import json
import logging
from types import SimpleNamespace

import pytest

from zerorepo.rtl_impl.module_planner.planner_runner import PlannerRunner
from zerorepo.rtl_impl.module_planner.schemas import Stage4SpecBlocksArtifact
from zerorepo.rtl_impl.module_planner.utils.local_repair import fingerprint, REPAIR_POLICY_VERSION


@pytest.mark.parametrize("change", ["implementation_only", "interface", "skeleton", "corrupt_baseline"])
def test_stage6_migration_requires_all_historical_source_bindings(tmp_path, monkeypatch, change):
    root = tmp_path / ".zerorepo"
    output = root / "module_planner/outputs"
    merged = root / "workspace/merged"
    fragments = root / "workspace/fragments"
    output.mkdir(parents=True); merged.mkdir(parents=True); fragments.mkdir(parents=True)
    (root / "zerorepo.log").write_text("")
    skeleton = output / "skeleton.md"
    skeleton.write_text("module toy(input a, output y); child u(a,y); endmodule\n")
    top = merged / "toy.v"; top.write_text(skeleton.read_text())
    fragment = fragments / "toy_fragments.v"; fragment.write_text("child u(a,y);\n")
    old_child = "module child(input a, output y); assign y=a; endmodule\n"
    child = merged / "child.v"
    child.write_text("module child(input a, output y); assign y=~a; endmodule\n")
    specs = Stage4SpecBlocksArtifact.model_validate({"task_id": "task", "module_order": ["toy"],
        "modules": [{"module": "toy", "source_spec_file": "toy.md", "blocks": [{"block_id": "S001", "text": "Connect child"}]}]})
    (output / "spec_blocks.json").write_text(specs.model_dump_json())
    (output / "repo_skeleton.json").write_text(json.dumps({"modules": [{"module": "toy", "children": ["child"]}]}))
    (output / "module_skeletons.json").write_text(json.dumps({"module_records": [{"module": "toy", "doc_file": "skeleton.md"}]}))
    baseline = root / "workspace/debug_system/toy/codex_private/accepted_baseline/merged"
    baseline.mkdir(parents=True)
    (baseline / "child.v").write_text(old_child)
    (baseline.parent.parent / "session_state.json").write_text(json.dumps({"accepted_manifest": {"child.v": hashlib.sha256(old_child.encode()).hexdigest()}}))
    old_key = fingerprint({"policy": REPAIR_POLICY_VERSION, "module": "toy", "fragments": fragment.read_text(),
        "skeleton": skeleton.read_text(), "spec": specs.modules[0], "children": {"child": old_child}})
    stamp = merged / "toy.inputs.json"
    stamp.write_text(json.dumps({"input_fingerprint": old_key, "merged_fingerprint": fingerprint(top.read_text())}))
    if change == "interface":
        child.write_text("module child(input a, output [1:0] y); endmodule\n")
    elif change == "skeleton":
        skeleton.write_text(skeleton.read_text() + "Changed behavioral obligation\n")
    elif change == "corrupt_baseline":
        (baseline / "child.v").write_text("corrupt")
    before = top.read_bytes()
    runner = PlannerRunner.__new__(PlannerRunner)
    runner.output_root = output
    runner.stage6 = SimpleNamespace(_merged_file=lambda name: merged / f"{name}.v", _ensure_toolchain_path=lambda: None)
    runner.logger = logging.getLogger("binding-test")
    inputs = {"stage2": SimpleNamespace(modules=[SimpleNamespace(module="toy", children=["child"])]),
              "stage3": SimpleNamespace(module_records=[SimpleNamespace(module="toy", doc_file="skeleton.md")]), "spec_blocks": specs}
    monkeypatch.setattr("zerorepo.rtl_impl.module_planner.planner_runner._check_single_file_syntax", lambda *args, **kwargs: (True, "ok"))
    result = runner._reuse_stage6_merge_if_valid("toy", SimpleNamespace(workspace_file=str(fragment)), inputs)
    assert (result is not None) == (change == "implementation_only")
    assert top.read_bytes() == before
    if result:
        assert json.loads(stamp.read_text())["migration_evidence"]["old_input_fingerprint"] == old_key
