from __future__ import annotations

from pathlib import Path

from zerorepo.rtl_impl.module_planner.agents.stage6_merge_agent import Stage6MergeAgent
from zerorepo.rtl_impl.rtl_kg import RTLKgService


class _CheckpointManager:
    def get_path(self, name: str) -> Path:
        return Path("/tmp") / f"{name}.json"


def _service(repo_path: Path) -> RTLKgService:
    svc = RTLKgService(
        repo_path=repo_path,
        checkpoint_manager=_CheckpointManager(),
        repo_data={},
        config={"enabled": False},
    )
    svc._repo_uid = "repo1"
    return svc


def test_text_fallback_adds_module_blocks_and_drives_for_parser_hostile_rtl(tmp_path: Path) -> None:
    rtl = """module top(input clk, input rst, output reg y);
  reg [7:0] state [0:3][0:3];
  wire [7:0] next_state [0:3][0:3];
  function [7:0] f;
    input [7:0] x;
    f = (x[7]) ? {x[6:0], 1'b0} ^ 8'h1b : {x[6:0], 1'b0};
  endfunction
  assign next_state[0][0] = f(state[0][0]);
  always @(posedge clk or posedge rst) begin
    if (rst) y <= 1'b0;
    else y <= next_state[0][0][0];
  end
endmodule
"""
    rtl_path = tmp_path / "top.v"
    rtl_path.write_text(rtl, encoding="utf-8")
    svc = _service(tmp_path)
    file_node = {
        "uid": "repo1:file:top.v",
        "repo_uid": "repo1",
        "kind": "File",
        "name": "top.v",
        "path": "top.v",
    }

    nodes, edges = svc._augment_snapshot_with_text_fallback([file_node], [])

    assert any(node.get("kind") == "Module" and node.get("name") == "top" for node in nodes)
    assert any(node.get("kind") == "Port" and node.get("name") == "y" for node in nodes)
    assert any(node.get("kind") == "AlwaysBlock" for node in nodes)
    assert any(node.get("kind") == "Assign" for node in nodes)
    assert any(edge.get("type") == "DRIVES" and str(edge.get("target_uid")).endswith(":y:top.v") for edge in edges)


def test_stage6_rejects_unpacked_arrays_and_generate() -> None:
    code = """module top(input clk, output y);
  wire [7:0] a [0:3][0:3];
  genvar i;
  generate for (i = 0; i < 4; i = i + 1) begin : g
    assign a[i][0] = 8'h00;
  end endgenerate
  assign y = a[0][0][0];
endmodule
"""
    agent = object.__new__(Stage6MergeAgent)
    errors = agent._validate_raw_module(code, "top")

    assert any("unpacked array" in error for error in errors)
    assert any("generate/genvar" in error for error in errors)
