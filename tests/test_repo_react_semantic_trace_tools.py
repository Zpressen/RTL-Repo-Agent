from __future__ import annotations

import asyncio
import ast
import hashlib
import json
from pathlib import Path
from rtl_artifact_test_utils import write_artifact_text
from zerorepo.rtl_impl.artifact_layout import ArtifactLayout, artifact_path
from types import SimpleNamespace
from typing import Any

import pytest

import zerorepo.rtl_impl.repo_react.context as context_module
import zerorepo.rtl_impl.repo_react.runner as runner_module
import zerorepo.rtl_impl.repo_react.tools as tools_module
from zerorepo.rtl_impl.repo_react.context import DebugContextRouter
from zerorepo.rtl_impl.repo_react.journal import RepoReActJournal
from zerorepo.rtl_impl.repo_react.schemas import RepoReActInput
from zerorepo.rtl_impl.repo_react.tools import RepoReActTools, RepoReActToolState


def _registered_tool_calls(module_path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(module_path).read_text(encoding="utf-8"))
    calls: dict[str, ast.Call] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Attribute) or node.func.attr != "register_tool_function":
            continue
        if not node.args or not isinstance(node.args[0], ast.Attribute):
            continue
        calls[node.args[0].attr] = node
    return calls


def test_public_tool_surfaces_exclude_legacy_overlaps() -> None:
    runner_calls = _registered_tool_calls(str(runner_module.__file__))
    router_calls = _registered_tool_calls(str(context_module.__file__))

    disabled = {"read_spec", "retrieve_spec_block", "route_debug_context", "read_memory"}
    assert not disabled & set(runner_calls)
    assert not disabled & set(router_calls)
    assert {"read_module_semantics", "trace_signal_cause"} <= set(runner_calls)
    assert {"read_module_semantics", "trace_signal_cause"} <= set(router_calls)

    for calls in (runner_calls, router_calls):
        read_context_literals = {
            item.value for item in ast.walk(calls["read_context"]) if isinstance(item, ast.Constant)
        }
        kg_literals = {
            item.value for item in ast.walk(calls["query_rtl_kg"]) if isinstance(item, ast.Constant)
        }
        assert "spec" not in read_context_literals
        assert "signal_drivers" not in kg_literals
    replace_literals = {
        item.value
        for item in ast.walk(runner_calls["replace_block"])
        if isinstance(item, ast.Constant)
    }
    assert {"module_name", "rtl_block_id"} <= replace_literals
    assert "block_id" not in replace_literals


def _make_tools(
    tmp_path: Path,
    *,
    rtl_text: str = "module top(input a, output y);\nassign y = a;\nendmodule\n",
    output_root: Path | None = None,
    kg_service: Any | None = None,
) -> RepoReActTools:
    rtl_root = tmp_path / "rtl"
    rtl_root.mkdir(exist_ok=True)
    rtl_path = rtl_root / "top.sv"
    write_artifact_text(rtl_path, rtl_text, encoding="utf-8")
    workdir = tmp_path / "debug"
    workdir.mkdir(exist_ok=True)
    inp = RepoReActInput(
        module_name="top",
        top_module="top",
        repair_scope="repo",
        workspace_root=tmp_path,
        debug_workdir=workdir,
        rtl_path=rtl_path,
        merged_file=rtl_path,
        rtl_root=rtl_root,
        output_root=output_root,
        initial_mismatch_count=1,
    )
    state = RepoReActToolState(
        input=inp,
        sim_reviewer=SimpleNamespace(),
        journal=RepoReActJournal(tmp_path / "journal"),
        kg_service=kg_service,
    )
    return RepoReActTools(state)


def _write_sidecars(root: Path) -> None:
    (root / "module_spec_context_json").mkdir(parents=True)
    (root / "module_skeleton_json").mkdir()
    (root / "module_plan_json").mkdir()
    write_artifact_text(ArtifactLayout(root).module(3, Path("top.json").stem, "spec_context.json"),
        json.dumps(
            {
                "module": "top",
                "blocks": [
                    {"block_id": "S001", "text": "Output y follows data signal a.", "source_file": "spec.md"},
                    {"block_id": "S002", "text": "Reset clears internal state.", "source_file": "spec.md"},
                ],
            }
        ),
        encoding="utf-8",
    )
    write_artifact_text(ArtifactLayout(root).module(3, Path("top.json").stem, "skeleton.json"),
        json.dumps(
            {
                "module": "top",
                "planning_note": "Small combinational wrapper.",
                "structural_blocks": [
                    {"block_id": "B1", "block_kind": "comb", "purpose": "Drive y from a."},
                    {"block_id": "B2", "block_kind": "decl", "purpose": "Unrelated status declaration."},
                ],
                "module_behavior": {"control_style": "purely_combinational"},
            }
        ),
        encoding="utf-8",
    )
    write_artifact_text(ArtifactLayout(root).module(4, Path("top.json").stem, "plan.json"),
        json.dumps(
            {
                "module": "top",
                "subtasks": [
                    {
                        "id": "B1_drive_y",
                        "target": "<block: B1>",
                        "description": "Drive y from signal a.",
                        "spec_refs": ["S001"],
                    },
                    {
                        "id": "B2_decl",
                        "target": "<block: B2>",
                        "description": "Declare status.",
                        "spec_refs": ["S002"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    write_artifact_text(artifact_path(root, "repo_skeleton.json"),
        json.dumps(
            {
                "top_module": "top",
                "modules": [
                    {
                        "module": "top",
                        "role": "wrapper",
                        "parents": [],
                        "children": ["child"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def test_read_module_semantics_sidecar_fallback_is_focused_and_neighbor_light(tmp_path: Path) -> None:
    output_root = tmp_path / "outputs"
    _write_sidecars(output_root)
    tools = _make_tools(
        tmp_path,
        output_root=output_root,
        rtl_text=(
            "module top(input clk, input [7:0] state_matrix, output logic [7:0] text_out);\n"
            "always @(posedge clk) text_out <= state_matrix;\n"
            "endmodule\n"
        ),
    )

    result = tools.read_module_semantics(
        "top",
        focus_signals=["y"],
        focus_blocks=["B1"],
    )

    assert result["status"] == "ok"
    assert result["source"] == "sidecar_fallback"
    assert [item["block_id"] for item in result["spec_fragments"]] == ["S001"]
    assert [item["block_id"] for item in result["skeleton_blocks"]] == ["B1"]
    assert [item["id"] for item in result["plan_subtasks"]] == ["B1_drive_y"]
    assert result["neighbors"] == [
        {
            "relation": "child",
            "module": "child",
            "instance_name": "",
            "instance_path": "",
            "semantics_included": False,
            "source": "planned_hierarchy",
        }
    ]
    assert all("spec_fragments" not in item for item in result["neighbors"])


class _PlanningKg:
    repo_uid = "demo@unit"

    def __init__(self, spec_hash: str):
        self.spec_hash = spec_hash

    def is_enabled(self) -> bool:
        return True

    def query(self, cypher: str, params: dict[str, Any] | None = None, limit: int = 100) -> dict[str, Any]:
        del limit
        params = params or {}
        if "collect(DISTINCT {fragment:" in cypher:
            return {
                "rows": [
                    {
                        "module": {"name": "top", "role": "wrapper", "stage2_fingerprint": "s2"},
                        "specs": [
                            {
                                "fragment": {
                                    "content_hash": self.spec_hash,
                                    "source_file": "spec.md",
                                },
                                "relation": {
                                    "local_ref": "S001",
                                    "artifact_path": "plan/stage3/modules/top/spec_context.json",
                                },
                            }
                        ],
                        "skeleton": {
                            "artifact_path": "plan/stage3/modules/top/skeleton.json",
                            "content_hash": "sk-hash",
                            "input_fingerprint": "s3",
                        },
                        "plan": {
                            "artifact_path": "plan/stage4/modules/top/plan.json",
                            "skeleton_content_hash": "sk-hash",
                            "input_fingerprint": "s4",
                        },
                    }
                ]
            }
        if "RETURN p.name AS name" in cypher:
            return {"rows": [{"name": "y", "attrs": {"dir": "output", "width_expr": "[0:0]"}, "path": "top.sv"}]}
        if "UNWIND coalesce" in cypher:
            return {"rows": []}
        if '"child" AS relation' in cypher:
            return {
                "rows": [
                    {
                        "relation": "child",
                        "related_module": "child",
                        "instance_name": "u_child",
                        "instance_path": "top.sv",
                    }
                ]
            }
        raise AssertionError(f"Unexpected KG query for {params}: {cypher[:80]}")


def test_read_module_semantics_hydrates_current_planning_kg_artifacts(tmp_path: Path) -> None:
    output_root = tmp_path / "outputs"
    _write_sidecars(output_root)
    spec_text = "Output y follows data signal a."
    tools = _make_tools(
        tmp_path,
        output_root=output_root,
        kg_service=_PlanningKg(hashlib.sha256(spec_text.encode()).hexdigest()),
    )

    result = tools.read_module_semantics("top")

    assert result["source"] == "planning_kg"
    assert result["spec_fragments"][0]["text"] == spec_text
    assert result["interface"][0]["name"] == "y"
    assert result["provenance"]["fingerprints"]["plan_skeleton_content"] == "sk-hash"
    assert result["neighbors"][0]["instance_name"] == "u_child"


class _TraceKg:
    repo_uid = "demo@unit"

    def is_enabled(self) -> bool:
        return True

    def query(self, cypher: str, params: dict[str, Any] | None = None, limit: int = 100) -> dict[str, Any]:
        del limit
        module = str((params or {}).get("module_name") or "")
        if "m.actual_path AS actual_path" in cypher:
            return {"rows": [{"module": module, "actual_path": f"{module}.sv", "module_uid": f"demo@unit:module:{module}"}]}
        if "collect(DISTINCT {" in cypher and "drivers" in cypher:
            return {"rows": [{"drivers": [{"kind": "Assign", "name": "C1", "sl": 2, "el": 2}]}]}
        if '"parent_to_child" AS mapping_direction' in cypher:
            if module == "top":
                return {
                    "rows": [
                        {
                            "mapping_direction": "parent_to_child",
                            "parent_module": "top",
                            "instance_name": "u_child",
                            "instance_path": "top.sv",
                            "child_module": "child",
                            "child_port": "out",
                            "child_port_attrs": json.dumps({"dir": "output", "width_expr": "[7:0]"}),
                            "target_kind": "Signal",
                            "target_name": "y",
                            "connection_expression": "y[7:0]",
                            "connection": {"p": "out", "x": "y[7:0]"},
                        }
                    ]
                }
            return {
                "rows": [
                    {
                        "mapping_direction": "child_to_parent",
                        "parent_module": "top",
                        "instance_name": "u_child",
                        "instance_path": "top.sv",
                        "child_module": "child",
                        "child_port": "in",
                        "child_port_attrs": {"dir": "input", "width_expr": "[7:0]"},
                        "target_kind": "Signal",
                        "target_name": "a",
                        "connection_expression": "a[7:0]",
                        "connection": {"p": "in", "x": "a[7:0]"},
                    }
                ]
            }
        raise AssertionError(f"Unexpected KG query: {cypher[:100]}")


class _RoundKeyTraceKg(_TraceKg):
    def query(self, cypher: str, params: dict[str, Any] | None = None, limit: int = 100) -> dict[str, Any]:
        if '"parent_to_child" AS mapping_direction' in cypher:
            return {
                "rows": [
                    {
                        "mapping_direction": "parent_to_child",
                        "parent_module": "aes_inv_cipher_top",
                        "instance_name": "u_key_expand",
                        "instance_path": "aes_inv_cipher_top.sv",
                        "child_module": "aes_key_expand",
                        "child_port": "round_key",
                        "child_port_attrs": {"dir": "output", "width_expr": "[127:0]"},
                        "target_kind": "Signal",
                        "target_name": "round_key_wire",
                        "connection_expression": "round_key_wire",
                        "connection": {"p": "round_key", "x": "round_key_wire"},
                    }
                ]
            }
        return super().query(cypher, params, limit)


def test_trace_signal_cause_returns_static_one_hop_and_child_output_boundary(tmp_path: Path) -> None:
    tools = _make_tools(
        tmp_path,
        rtl_text=(
            "module top(input [7:0] a, output [7:0] y);\n"
            "assign y = a;\n"
            "endmodule\n"
        ),
        kg_service=_TraceKg(),
    )

    result = tools.trace_signal_cause("top", "y", time=10, expected_value="00000001")

    assert result["status"] == "static_only"
    assert result["driver_candidates"][0]["classification"] == "static_dependency"
    assert result["driver_candidates"][0]["assignment"]["rhs_signals"] == ["a"]
    assert result["driver_candidates"][0]["kg_drivers"][0]["kind"] == "Assign"
    mapping = result["boundary_mappings"][0]
    assert mapping["connection_expression"] == "y[7:0]"
    assert mapping["direction"] == "output"
    assert mapping["width"] == "[7:0]"
    assert {
        "module": "child",
        "signal": "out",
        "relation": "child_output_boundary",
    }.items() <= result["next_frontier"][0].items()
    assert result["recommended_next_call"] == {
        "tool": "trace_signal_cause",
        "args": {
            "module_name": "child",
            "signal_name": "out",
            "time": 10,
        },
        "candidate_id": "F1",
        "reason": "y is driven through instance u_child.out.",
    }
    assert result["recommended_next_calls"][0] == result["recommended_next_call"]
    assert result["editable_rtl_blocks"][0]["rtl_block_id"] == "C1"
    assert result["editable_rtl_blocks"][0]["rtl_block_ref"] == "top:C1"
    assert result["provenance"]["one_hop_only"] is True


def test_trace_signal_cause_recommends_exact_round_key_child_port_next_hop(
    tmp_path: Path,
) -> None:
    rtl_root = tmp_path / "rtl"
    rtl_root.mkdir()
    rtl_path = rtl_root / "aes_inv_cipher_top.sv"
    write_artifact_text(rtl_path,
        (
            "module aes_inv_cipher_top(output [127:0] round_key_wire);\n"
            "aes_key_expand u_key_expand(.round_key(round_key_wire));\n"
            "endmodule\n"
        ),
        encoding="utf-8",
    )
    workdir = tmp_path / "debug"
    workdir.mkdir()
    tools = RepoReActTools(
        RepoReActToolState(
            input=RepoReActInput(
                module_name="aes_inv_cipher_top",
                top_module="aes_inv_cipher_top",
                repair_scope="repo",
                workspace_root=tmp_path,
                debug_workdir=workdir,
                rtl_path=rtl_path,
                merged_file=rtl_path,
                rtl_root=rtl_root,
                initial_mismatch_count=1,
            ),
            sim_reviewer=SimpleNamespace(),
            journal=RepoReActJournal(tmp_path / "journal"),
            kg_service=_RoundKeyTraceKg(),
        )
    )

    result = tools.trace_signal_cause(
        "aes_inv_cipher_top",
        "round_key_wire",
        time=245,
    )

    assert result["recommended_next_call"] == {
        "tool": "trace_signal_cause",
        "args": {
            "module_name": "aes_key_expand",
            "signal_name": "round_key",
            "time": 245,
        },
        "candidate_id": "F1",
        "reason": (
            "round_key_wire is driven through instance "
            "u_key_expand.round_key."
        ),
    }


def test_trace_signal_cause_samples_one_hop_vcd_values(tmp_path: Path) -> None:
    if tools_module.VCDVCD is None:
        pytest.skip("vcdvcd is not installed")
    tools = _make_tools(tmp_path)
    write_artifact_text(tools.state.input.debug_workdir / "wave.vcd",
        """$date today $end
$version unit $end
$timescale 1ns $end
$scope module tb $end
$scope module dut $end
$var wire 1 ! a $end
$var wire 1 " y $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
0!
0"
#10
1!
0"
""",
        encoding="utf-8",
    )

    result = tools.trace_signal_cause("top", "y", time=10, expected_value="1")

    assert result["status"] == "ok"
    assert result["observed_value"] == "0"
    assert result["driver_candidates"][0]["rhs_observed_values"] == {"a": "1"}
    assert result["driver_candidates"][0]["classification"] == "source_matches_expected_mux_wrong"
    assert result["resolved_vcd_path"].endswith(".dut.y")


def test_trace_signal_cause_preserves_multiple_driver_candidates(tmp_path: Path) -> None:
    tools = _make_tools(
        tmp_path,
        rtl_text=(
            "module top(input clk, input a, input b, output logic y);\n"
            "always @(posedge clk) y <= a;\n"
            "always @(*) y = b;\n"
            "endmodule\n"
        ),
    )

    result = tools.trace_signal_cause("top", "y", time=10)

    assert len(result["driver_candidates"]) == 2
    assert {item["assignment"]["kind"] for item in result["driver_candidates"]} == {
        "nonblocking",
        "blocking",
    }
    sequential = next(item for item in result["driver_candidates"] if item["assignment"]["kind"] == "nonblocking")
    assert sequential["needs_edge_probe"] is True


def test_trace_signal_cause_returns_all_multiline_branches_and_condition_first_frontier(
    tmp_path: Path,
) -> None:
    tools = _make_tools(
        tmp_path,
        rtl_text=(
            "module top(input clk, input rst, input [1:0] fsm_state,\n"
            "input [7:0] state_a, state_b, output logic [15:0] text_out);\n"
            "always @(posedge clk) begin\n"
            "  if (rst) text_out <= '0;\n"
            "  else if (fsm_state == 2'd3) text_out <= {\n"
            "    state_a,\n"
            "    state_b\n"
            "  };\n"
            "  else text_out <= text_out;\n"
            "end\n"
            "endmodule\n"
        ),
    )

    result = tools.trace_signal_cause("top", "text_out", time=15, expected_value="ffff")

    assert len(result["driver_candidates"]) == 3
    conditions = [
        item["assignment"]["condition_expressions"]
        for item in result["driver_candidates"]
    ]
    assert conditions == [
        ["rst"],
        ["!rst", "fsm_state == 2'd3"],
        ["!rst", "!(fsm_state == 2'd3)"],
    ]
    done = result["driver_candidates"][1]["assignment"]
    assert done["rhs_signals"] == ["state_a", "state_b"]
    assert done["end_line"] > done["start_line"]
    assert result["next_frontier"][0]["relation"] == "local_rhs"
    assert result["focus_context"]["rtl_block_ids"] == ["A1"]
    assert result["focus_context"]["rtl_block_refs"] == ["top:A1"]
    assert result["recommended_next_calls"][0]["tool"] == "trace_signal_cause"
    assert result["recommended_next_calls"][-1]["tool"] == "read_module_semantics"


def test_trace_signal_frontier_is_condition_first_and_capped_at_twelve(tmp_path: Path) -> None:
    condition = " && ".join(f"c{i}" for i in range(8))
    rhs = " ^ ".join(f"a{i}" for i in range(8))
    ports = ", ".join([*(f"input c{i}" for i in range(8)), *(f"input a{i}" for i in range(8))])
    tools = _make_tools(
        tmp_path,
        rtl_text=f"module top({ports}, output logic y);\\nalways @(*) if ({condition}) y = {rhs};\\nendmodule\\n",
    )

    result = tools.trace_signal_cause("top", "y", time=3)

    assert result["frontier_truncated"] is True
    assert len(result["next_frontier"]) == 12
    assert all(item["relation"] == "local_rhs" for item in result["next_frontier"][:8])
    assert sum(item["relation"] == "local_condition" for item in result["next_frontier"]) == 4


def test_trace_signal_condition_blocking_prioritizes_condition_but_keeps_rhs(
    tmp_path: Path,
) -> None:
    if tools_module.VCDVCD is None:
        pytest.skip("vcdvcd is not installed")
    tools = _make_tools(
        tmp_path,
        rtl_text=(
            "module top(input c, input a, output logic y);\n"
            "always @(*) if (c) y = a;\n"
            "endmodule\n"
        ),
    )
    write_artifact_text(tools.state.input.debug_workdir / "wave.vcd",
        """$date today $end
$version unit $end
$timescale 1ns $end
$scope module tb $end
$scope module dut $end
$var wire 1 ! c $end
$var wire 1 " a $end
$var wire 1 # y $end
$upscope $end
$upscope $end
$enddefinitions $end
#0
0!
1"
0#
#10
0!
1"
0#
""",
        encoding="utf-8",
    )

    result = tools.trace_signal_cause("top", "y", time=10, expected_value="1")

    assert result["driver_candidates"][0]["classification"] == "condition_blocks_update"
    assert result["next_frontier"][0]["relation"] == "local_condition"
    assert result["next_frontier"][0]["signal"] == "c"
    assert any(
        item["relation"] == "local_rhs" and item["signal"] == "a"
        for item in result["next_frontier"]
    )


def test_trace_signal_cause_reverse_maps_child_input_to_parent_actual(tmp_path: Path) -> None:
    rtl_root = tmp_path / "rtl"
    rtl_root.mkdir()
    write_artifact_text(rtl_root / "top.sv", "module top; endmodule\n", encoding="utf-8")
    write_artifact_text(rtl_root / "child.sv",
        "module child(input [7:0] in, output [7:0] out);\nassign out = in;\nendmodule\n",
        encoding="utf-8",
    )
    workdir = tmp_path / "debug"
    workdir.mkdir()
    inp = RepoReActInput(
        module_name="top",
        top_module="top",
        repair_scope="repo",
        workspace_root=tmp_path,
        debug_workdir=workdir,
        rtl_path=rtl_root / "top.sv",
        merged_file=rtl_root / "top.sv",
        rtl_root=rtl_root,
        initial_mismatch_count=1,
    )
    tools = RepoReActTools(
        RepoReActToolState(
            input=inp,
            sim_reviewer=SimpleNamespace(),
            journal=RepoReActJournal(tmp_path / "journal"),
            kg_service=_TraceKg(),
        )
    )

    result = tools.trace_signal_cause("child", "in", time=10)

    assert result["boundary_mappings"][0]["mapping_direction"] == "child_to_parent"
    assert any(
        item["module"] == "top"
        and item["signal"] == "a"
        and item["relation"] == "parent_input_boundary"
        for item in result["next_frontier"]
    )


def test_debug_context_router_exposes_new_tool_payloads(tmp_path: Path) -> None:
    output_root = tmp_path / "outputs"
    _write_sidecars(output_root)
    tools = _make_tools(tmp_path, output_root=output_root)
    router = DebugContextRouter(cfg=None, tools=tools)

    semantics = json.loads(router.read_module_semantics("top", focus_signals=["y"]).content[0]["text"])
    trace = json.loads(router.trace_signal_cause("top", "y", time=10).content[0]["text"])

    assert semantics["visible_payload"]["spec_fragments"][0]["block_id"] == "S001"
    assert semantics["visible_payload"]["skeleton_blocks"][0]["planning_block_id"] == "B1"
    assert semantics["visible_payload"]["editable_rtl_blocks"][0]["rtl_block_ref"] == "top:C1"
    assert trace["visible_payload"]["driver_candidates"][0]["classification"] == "static_dependency"
    assert trace["visible_payload"]["editable_rtl_blocks"][0]["rtl_block_ref"] == "top:C1"
    assert trace["visible_payload"]["recommended_next_call"]["tool"] == "trace_signal_cause"
    assert trace["tool_budget"]["used"] == 2


def test_replace_block_targets_child_module_with_module_scoped_rtl_id(
    tmp_path: Path,
) -> None:
    rtl_root = tmp_path / "rtl"
    rtl_root.mkdir()
    top_path = rtl_root / "top.sv"
    child_path = rtl_root / "child.sv"
    write_artifact_text(top_path,
        (
            "module top(input a, output logic z, output logic y);\n"
            "always @(*) z = a;\n"
            "always @(*) y = a;\n"
            "endmodule\n"
        ),
        encoding="utf-8",
    )
    write_artifact_text(child_path,
        (
            "module child(input a, output logic z, output logic y);\n"
            "always @(*) z = a;\n"
            "always @(*) y = a;\n"
            "endmodule\n"
        ),
        encoding="utf-8",
    )
    workdir = tmp_path / "debug"
    workdir.mkdir()
    inp = RepoReActInput(
        module_name="top",
        top_module="top",
        repair_scope="repo",
        workspace_root=tmp_path,
        debug_workdir=workdir,
        rtl_path=top_path,
        merged_file=top_path,
        rtl_root=rtl_root,
        initial_mismatch_count=1,
    )
    tools = RepoReActTools(
        RepoReActToolState(
            input=inp,
            sim_reviewer=SimpleNamespace(),
            journal=RepoReActJournal(tmp_path / "journal"),
        )
    )
    tools.state.observed_real_divergence = True

    result = tools.replace_block(
        block_id=None,
        module_name="child",
        rtl_block_id="A2",
        new_code="always @(*) y = ~a;",
        reason="edit traced child driver",
        expected_effect="invert child output",
        verify=False,
    )

    assert result["status"] == "kept_unverified"
    assert result["module_name"] == "child"
    assert result["rtl_block_id"] == "A2"
    assert result["rtl_block_ref"] == "child:A2"
    assert "y = ~a" in child_path.read_text(encoding="utf-8")
    assert "y = ~a" not in top_path.read_text(encoding="utf-8")
    assert not any("Deprecated" in warning for warning in result["warnings"])


def test_replace_block_rejects_planning_id_with_editable_rtl_candidates(
    tmp_path: Path,
) -> None:
    output_root = tmp_path / "outputs"
    _write_sidecars(output_root)
    skeleton_path = ArtifactLayout(output_root).module(3, Path("top.json").stem, "skeleton.json")
    skeleton = json.loads(skeleton_path.read_text(encoding="utf-8"))
    skeleton["structural_blocks"].append(
        {
            "block_id": "B5",
            "block_kind": "comb",
            "purpose": "Drive output y.",
        }
    )
    write_artifact_text(skeleton_path, json.dumps(skeleton), encoding="utf-8")
    tools = _make_tools(tmp_path, output_root=output_root)
    tools.state.last_signal_trace = {
        "module": "top",
        "focus_context": {"signals": ["y"], "rtl_block_ids": ["C1"]},
        "editable_rtl_blocks": [{"rtl_block_id": "C1", "rtl_block_ref": "top:C1"}],
    }

    result = tools.replace_block(
        block_id=None,
        module_name="top",
        rtl_block_id="B5",
        new_code="assign y = ~a;",
        reason="mistaken planning id",
        expected_effect="should be rejected",
        verify=False,
    )

    assert result["status"] == "invalid_rtl_block_id"
    assert result["detected_namespace"] == "planning_block_id"
    assert result["provided"] == "B5"
    assert result["valid_editable_blocks"][0]["rtl_block_id"] == "C1"
    assert result["valid_editable_blocks"][0]["rtl_block_ref"] == "top:C1"
    assert "planning block" in result["message"]


def test_replace_block_rejects_unknown_rtl_id_with_current_candidates(
    tmp_path: Path,
) -> None:
    tools = _make_tools(tmp_path)

    result = tools.replace_block(
        block_id=None,
        module_name="top",
        rtl_block_id="A999",
        new_code="assign y = ~a;",
        reason="stale parser id",
        expected_effect="should be rejected",
        verify=False,
    )

    assert result["status"] == "invalid_rtl_block_id"
    assert result["detected_namespace"] == "unknown_rtl_block_id"
    assert result["valid_editable_blocks"][0]["rtl_block_ref"] == "top:C1"


def test_replace_block_rejects_conflicting_old_and_new_block_ids(
    tmp_path: Path,
) -> None:
    tools = _make_tools(tmp_path)

    result = tools.replace_block(
        block_id="C1",
        module_name="top",
        rtl_block_id="A1",
        new_code="assign y = ~a;",
        reason="conflicting identifiers",
        expected_effect="should be rejected",
        verify=False,
    )

    assert result["status"] == "conflicting_block_ids"
    assert result["is_action_executed"] is False
    assert tools.state.action_calls == 0


def test_replace_block_legacy_block_id_keeps_compatibility_warning(
    tmp_path: Path,
) -> None:
    tools = _make_tools(tmp_path)
    tools.state.observed_real_divergence = True

    result = tools.replace_block(
        block_id="C1",
        new_code="assign y = ~a;",
        reason="legacy compatibility",
        expected_effect="invert output",
        verify=False,
    )

    assert result["status"] == "kept_unverified"
    assert result["rtl_block_ref"] == "top:C1"
    assert any("Deprecated" in warning for warning in result["warnings"])


def test_runner_auto_focuses_module_semantics_from_latest_signal_trace(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    output_root = tmp_path / "outputs"
    _write_sidecars(output_root)
    spec_path = ArtifactLayout(output_root).module(3, Path("top.json").stem, "spec_context.json")
    skeleton_path = ArtifactLayout(output_root).module(3, Path("top.json").stem, "skeleton.json")
    plan_path = ArtifactLayout(output_root).module(4, Path("top.json").stem, "plan.json")
    write_artifact_text(spec_path,
        json.dumps(
            {
                "module": "top",
                "blocks": [
                    {"block_id": "S005", "text": "text_out is emitted from the final state matrix."}
                ],
            }
        ),
        encoding="utf-8",
    )
    write_artifact_text(skeleton_path,
        json.dumps(
            {
                "module": "top",
                "structural_blocks": [
                    {
                        "block_id": "B5_final_output",
                        "block_kind": "seq",
                        "purpose": "Drive text_out from the final state matrix.",
                    },
                    {"block_id": "B2_other", "block_kind": "comb", "purpose": "Unrelated decode."},
                ],
            }
        ),
        encoding="utf-8",
    )
    write_artifact_text(plan_path,
        json.dumps(
            {
                "module": "top",
                "subtasks": [
                    {
                        "id": "B5_emit",
                        "target": "<block: B5_final_output>",
                        "description": "Emit text_out.",
                        "spec_refs": ["S005"],
                    },
                    {
                        "id": "B2_decode",
                        "target": "<block: B2_other>",
                        "description": "Unrelated decode.",
                        "spec_refs": [],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    tools = _make_tools(
        tmp_path,
        output_root=output_root,
        rtl_text=(
            "module top(input logic [7:0] state_matrix, output logic [7:0] text_out);\n"
            "always @(*) text_out = state_matrix;\n"
            "endmodule\n"
        ),
    )
    tools.state.last_signal_trace = {
        "module": "top",
        "signal": "text_out",
        "focus_context": {
            "signals": ["text_out"],
            "rtl_block_ids": ["A1"],
        },
    }
    runner = runner_module.RepoReActRunner.__new__(runner_module.RepoReActRunner)
    runner._state = tools.state
    runner._tools = tools
    runner._context_router = DebugContextRouter(cfg=None, tools=tools)
    runner._readonly_calls_since_action = 0
    runner._readonly_calls_since_light = 0
    runner._max_readonly_calls_since_action = 16
    runner._route_allowed_reads = []
    runner._route_read_count = 0
    runner._tool_result_chars_since_compact = 0
    runner._tool_result_chars_since_light = 0
    runner._route_calls_since_action = 0
    runner._latest_context_pack = {}

    async def inline_to_thread(func: Any, *args: Any, **kwargs: Any) -> Any:
        return func(*args, **kwargs)

    monkeypatch.setattr(runner_module.asyncio, "to_thread", inline_to_thread)
    auto = json.loads(
        asyncio.run(runner.read_module_semantics(module_name="top")).content[0]["text"]
    )
    explicit = json.loads(
        asyncio.run(
            runner.read_module_semantics(
                module_name="top",
                focus_signals=[],
                focus_blocks=["B2_other"],
            )
        ).content[0]["text"]
    )

    assert auto["focus_applied"] == {
        "signals": ["text_out"],
        "rtl_block_ids": ["A1"],
        "planning_block_ids": ["B5_final_output"],
        "sources": {
            "signals": "last_signal_trace",
            "rtl_block_ids": "last_signal_trace",
            "planning_block_ids": "last_signal_trace",
        },
    }
    assert [item["block_id"] for item in auto["skeleton_blocks"]] == ["B5_final_output"]
    assert auto["skeleton_blocks"][0]["planning_block_id"] == "B5_final_output"
    assert [item["id"] for item in auto["plan_subtasks"]] == ["B5_emit"]
    assert auto["editable_rtl_blocks"][0]["rtl_block_ref"] == "top:A1"
    assert auto["block_alignment"][0]["planning_block_id"] == "B5_final_output"
    assert auto["block_alignment"][0]["rtl_block_refs"] == ["top:A1"]
    assert auto["block_alignment"][0]["authoritative_for_editing"] is False
    assert explicit["focus_applied"]["rtl_block_ids"] == []
    assert explicit["focus_applied"]["planning_block_ids"] == ["B2_other"]
    assert explicit["focus_applied"]["sources"]["planning_block_ids"] == "explicit"
