from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import zerorepo.rtl_impl.debug_agent.debug_runner as debug_runner_module
import zerorepo.rtl_impl.debug_agent.trace_report as trace_report_module
from zerorepo.rtl_impl.debug_agent.bash_tools import CommandResult
from zerorepo.rtl_impl.debug_agent.debug_runner import ModuleDebugResult, ModuleDebugRunner, RtlDebugConfig
from zerorepo.rtl_impl.debug_agent.kg_debug_reads import DebugReadsMaterializer, kg_dynamic_slice
from zerorepo.rtl_impl.debug_agent.trace_report import (
    build_first_divergence_report,
    build_trace_report,
    build_value_backtrace,
)
from zerorepo.rtl_impl.debug_agent.trace_slicer import parse_rtl_assignments, parse_rtl_blocks
from zerorepo.rtl_impl.kg_agent.module_result_writer import ModuleResultWriter


class _FakeIngestor:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []

    def ingest(self, *, nodes: list[dict[str, Any]], edges: list[dict[str, Any]], mode: str, repo_uid: str) -> None:
        self.calls.append({"nodes": nodes, "edges": edges, "mode": mode, "repo_uid": repo_uid})
        self.edges.extend(edges)


class _FakeKgService:
    def __init__(self, *, repo_path: Path, blocks: list[Any] | None = None) -> None:
        self.repo_path = repo_path
        self.repo_uid = "repo1"
        self._ingestor = _FakeIngestor()
        self.blocks = blocks or []
        self.queries: list[tuple[str, dict[str, Any]]] = []

    def is_enabled(self) -> bool:
        return True

    def initialize(self) -> None:
        return None

    def query(self, cypher: str, params: dict[str, Any] | None = None, limit: int | None = None) -> dict[str, Any]:
        del limit
        params = params or {}
        self.queries.append((cypher, params))
        if "collect(DISTINCT child.name)" in cypher:
            return {"rows": [{"children": [], "parents": []}]}
        if "RETURN m.name AS module" in cypher:
            return {"rows": [{"module": "m", "uid": "mod:m", "path": "m.sv", "sl": 1, "el": 8}]}
        if "RETURN b.uid AS uid, b.kind AS kind, b.sl AS sl, b.el AS el" in cypher:
            rows = []
            for block in self.blocks:
                kind = "AlwaysBlock" if block.kind == "always" else "Assign"
                rows.append(
                    {
                        "uid": f"{kind}:{block.start_line}:{block.end_line}",
                        "kind": kind,
                        "sl": block.start_line,
                        "el": block.end_line,
                    }
                )
            return {"rows": rows}
        if "RETURN sym.name AS name" in cypher:
            names = params.get("names") or []
            return {"rows": [{"name": name, "uid": f"sym:{name}", "kind": "Signal"} for name in names]}
        return {"rows": []}


def test_debug_reads_materializer_writes_session_scoped_edges(tmp_path: Path) -> None:
    rtl = """module m(input clk, input a, output y);
  reg r;
  assign y = r;
  always @(posedge clk) begin
    r <= a;
  end
endmodule
"""
    rtl_path = tmp_path / "m.sv"
    rtl_path.write_text(rtl, encoding="utf-8")
    blocks = parse_rtl_blocks(rtl)
    kg = _FakeKgService(repo_path=tmp_path, blocks=blocks)

    result = DebugReadsMaterializer(kg).materialize(
        module_name="m",
        session_id="m:session:a",
        hop_depth=2,
        current_rtl_path=rtl_path,
        current_blocks=blocks,
    )

    assert result.session_id == "m:session:a"
    assert result.related_modules == ["m"]
    assert result.materialized_edges > 0
    assert result.current_uid_by_key
    assert kg._ingestor.calls[-1]["mode"] == "delta"
    assert {edge["type"] for edge in kg._ingestor.edges} == {"DEBUG_READS"}
    assert {edge["session_id"] for edge in kg._ingestor.edges} == {"m:session:a"}
    assert all(edge["role"] == "read" and edge["source_module"] == "m" for edge in kg._ingestor.edges)

    first_uids = {edge["uid"] for edge in kg._ingestor.edges}
    DebugReadsMaterializer(kg).materialize(
        module_name="m",
        session_id="m:session:a",
        hop_depth=2,
        current_rtl_path=rtl_path,
        current_blocks=blocks,
    )
    second_uids = {edge["uid"] for edge in kg._ingestor.edges}
    assert first_uids == second_uids


class _SliceKgService:
    repo_uid = "repo1"

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def query(self, cypher: str, params: dict[str, Any] | None = None, limit: int | None = None) -> dict[str, Any]:
        del limit
        params = params or {}
        self.calls.append((cypher, params))
        if "sym.name IN $fail_signals" in cypher:
            return {"rows": [{"uid": "sym:out"}]}
        if "AND sym.uid IN $symbol_uids" in cypher:
            symbols = set(params.get("symbol_uids") or [])
            rows = []
            if "sym:out" in symbols:
                rows.append({"uid": "block:assign_out", "kind": "Assign", "path": "m.sv", "sl": 3, "el": 3})
            if "sym:a" in symbols:
                rows.append({"uid": "block:assign_a", "kind": "Assign", "path": "m.sv", "sl": 2, "el": 2})
            return {"rows": rows}
        if "RETURN DISTINCT sym.uid AS uid" in cypher:
            blocks = set(params.get("block_uids") or [])
            rows = []
            if "block:assign_out" in blocks:
                rows.append({"uid": "sym:a"})
            if "block:assign_a" in blocks:
                rows.append({"uid": "sym:b"})
            return {"rows": rows}
        if "b.uid IN $block_uids" in cypher:
            return {
                "rows": [
                    {"uid": "block:assign_a", "kind": "Assign", "path": "m.sv", "sl": 2, "el": 2, "writes": ["a"], "reads": ["b"]},
                    {"uid": "block:assign_out", "kind": "Assign", "path": "m.sv", "sl": 3, "el": 3, "writes": ["out"], "reads": ["a"]},
                ]
            }
        return {"rows": []}


def test_kg_dynamic_slice_walks_drives_and_debug_reads() -> None:
    result = kg_dynamic_slice(
        kg_service=_SliceKgService(),
        module_name="m",
        fail_signals=["out"],
        session_id="m:session:a",
        max_depth=3,
    )

    assert result.block_uids == ["block:assign_a", "block:assign_out"]
    assert {row["uid"] for row in result.rows} == {"block:assign_a", "block:assign_out"}


class _FailingKgService:
    repo_uid = "repo1"

    def is_enabled(self) -> bool:
        return True

    def initialize(self) -> None:
        raise RuntimeError("kg offline")


def test_trace_report_falls_back_to_local_slice_when_kg_fails(tmp_path: Path) -> None:
    rtl = """module m(input a, output y);
  assign y = a;
endmodule
"""
    rtl_path = tmp_path / "rtl.sv"
    rtl_path.write_text(rtl, encoding="utf-8")
    (tmp_path / "contract.json").write_text(json.dumps({"module_name": "m"}) + "\n", encoding="utf-8")
    sim_log = CommandResult(
        stdout="Hint: Output 'y' has 1 mismatches. First mismatch occurred at time 10.\nMismatches: 1 in 1 samples\n",
        stderr="",
    ).model_dump_json()

    report, suspect_blocks = build_trace_report(
        rtl_path=rtl_path,
        sim_log_json=sim_log,
        output_dir=tmp_path,
        kg_service=_FailingKgService(),
        kg_session_id="m:session:a",
    )

    assert suspect_blocks
    assert report["suspect_blocks"][0]["id"] == suspect_blocks[0].id


def test_trace_report_uses_planner_identity_for_kg_and_runtime_identity_for_rtl(tmp_path: Path) -> None:
    rtl = """module runtime_top(input a, output y);
  assign y = a;
endmodule
"""
    rtl_path = tmp_path / "runtime_top.sv"
    rtl_path.write_text(rtl, encoding="utf-8")
    blocks = parse_rtl_blocks(rtl)
    kg = _FakeKgService(repo_path=tmp_path, blocks=blocks)
    sim_log = CommandResult(
        stdout="Hint: Output 'y' has 1 mismatches. First mismatch occurred at time 10.\n",
        stderr="",
    ).model_dump_json()

    report, _ = build_trace_report(
        rtl_path=rtl_path,
        sim_log_json=sim_log,
        output_dir=tmp_path,
        planner_module_name="planner_top",
        runtime_top_module="runtime_top",
        kg_service=kg,
    )

    assert report["planner_module_name"] == "planner_top"
    assert report["runtime_top_module"] == "runtime_top"
    assert any("planner_top" in (params.get("modules") or []) for _query, params in kg.queries)


class _FakeSignal:
    def __init__(self, tv: list[tuple[int, str]]) -> None:
        self.tv = tv


class _BacktraceVcd:
    def __init__(self, _path: str, store_tvs: bool = True) -> None:
        del store_tvs
        self._signals = {
            "tb.clk": _FakeSignal([(0, "0"), (5, "1"), (10, "0")]),
            "tb.q_ref": _FakeSignal([(0, "01000100")]),
            "tb.q_dut": _FakeSignal([(0, "00000000")]),
            "tb.dut.q": _FakeSignal([(0, "00000000")]),
            "tb.dut.q_nxt": _FakeSignal([(0, "01000100")]),
            "tb.dut.rd": _FakeSignal([(0, "1")]),
            "tb.dut.empty": _FakeSignal([(0, "1")]),
        }


def test_trace_report_includes_value_backtrace_and_ranked_suspects(tmp_path: Path, monkeypatch: Any) -> None:
    rtl = """module m(input clk, input rd, input empty, output logic [7:0] q);
  logic [7:0] q_nxt;
  always @(posedge clk) begin
    if (rd && !empty) q <= q_nxt;
  end
endmodule
"""
    rtl_path = tmp_path / "rtl.sv"
    rtl_path.write_text(rtl, encoding="utf-8")
    (tmp_path / "contract.json").write_text(json.dumps({"module_name": "m", "clocking": {"clock": {"name": "clk"}}}) + "\n", encoding="utf-8")
    (tmp_path / "tb.sv").write_text("module tb; m dut(); endmodule\n", encoding="utf-8")
    (tmp_path / "wave.vcd").write_text("$date\n$date\n", encoding="utf-8")
    monkeypatch.setattr(trace_report_module, "VCDVCD", _BacktraceVcd)
    sim_log = CommandResult(
        stdout="Hint: Output 'q' has 1 mismatches. First mismatch occurred at time 5.\nMismatches: 1 in 1 samples\n",
        stderr="",
    ).model_dump_json()

    report, suspect_blocks = build_trace_report(
        rtl_path=rtl_path,
        sim_log_json=sim_log,
        output_dir=tmp_path,
    )

    assert suspect_blocks
    assert report["value_backtrace"]["chains"][0]["chain"][0]["classification"] == "condition_blocks_update"
    assert "condition_blocks_update" in report["diagnostic_narrative"][0]


def test_trace_report_filters_tb_metric_first_failure(tmp_path: Path) -> None:
    rtl = """module m(clk, settings);
  input clk;
  output [1:0] settings;
  reg [1:0] settings;
  always @(posedge clk) settings <= 2'b01;
endmodule
"""
    rtl_path = tmp_path / "rtl.sv"
    rtl_path.write_text(rtl, encoding="utf-8")
    sim_log = CommandResult(
        stdout="Hint: Output 'errors_settings' has 1 mismatches. First mismatch occurred at time 5.\nMismatches: 1 in 1 samples\n",
        stderr="",
    ).model_dump_json()

    report, _blocks = build_trace_report(rtl_path=rtl_path, sim_log_json=sim_log, output_dir=tmp_path)

    assert report["first_failure"] is None
    assert report["fail_outputs"] == []
    assert report["ignored_tb_metrics"][0]["sig"] == "errors_settings"
    assert report["required_next_tool"] == "run_check(first_divergence)"


class _FirstDivergenceVcd:
    def __init__(self, _path: str, store_tvs: bool = True) -> None:
        del store_tvs
        self._signals = {
            "tb.clk": _FakeSignal([(0, "0"), (5, "1"), (10, "0")]),
            "tb.settings_ref": _FakeSignal([(0, "00"), (5, "01")]),
            "tb.settings_dut": _FakeSignal([(0, "00"), (10, "01")]),
            "tb.good1.state": _FakeSignal([(0, "001"), (5, "010")]),
            "tb.top_module1.state": _FakeSignal([(0, "001"), (10, "010")]),
        }


class _EdgeActiveDivergenceVcd:
    def __init__(self, _path: str, store_tvs: bool = True) -> None:
        del store_tvs
        self._signals = {
            "tb.clk": _FakeSignal([(0, "0"), (5, "1"), (10, "0")]),
            "tb.settings_ref": _FakeSignal([(0, "00"), (5, "01")]),
            "tb.settings_dut": _FakeSignal([(0, "00"), (5, "01")]),
        }


class _AuthoritativeSamplingVcd:
    def __init__(self, _path: str, store_tvs: bool = True) -> None:
        del store_tvs
        self._signals = {
            "tb.clk": _FakeSignal(
                [(0, "0"), (5, "1"), (10, "0"), (15, "1"), (20, "0"), (25, "1")]
            ),
            "tb.settings_ref": _FakeSignal([(0, "00"), (6, "01"), (16, "00"), (25, "01")]),
            "tb.settings_dut": _FakeSignal([(0, "00"), (5, "01"), (15, "00"), (25, "01")]),
        }


def test_first_divergence_reports_real_dut_ref_output(tmp_path: Path, monkeypatch: Any) -> None:
    rtl = """module m(clk, settings);
  input clk;
  output [1:0] settings;
  reg [1:0] settings;
  always @(posedge clk) settings <= 2'b01;
endmodule
"""
    rtl_path = tmp_path / "rtl.sv"
    rtl_path.write_text(rtl, encoding="utf-8")
    (tmp_path / "contract.json").write_text(json.dumps({"module_name": "m", "clocking": {"clock": {"name": "clk"}}}) + "\n", encoding="utf-8")
    (tmp_path / "tb.sv").write_text(
        "module tb; m top_module1(); ref_m good1(); "
        "always @(posedge clk) begin if (!tb_match) errors = errors + 1; end endmodule\n",
        encoding="utf-8",
    )
    (tmp_path / "wave.vcd").write_text("$date\n$date\n", encoding="utf-8")
    monkeypatch.setattr(trace_report_module, "VCDVCD", _FirstDivergenceVcd)

    result = build_first_divergence_report(rtl_path=rtl_path, output_dir=tmp_path)

    assert result["status"] == "ok"
    assert result["first_divergence"]["signal"] == "settings"
    assert result["first_divergence"]["time"] == 5
    assert result["first_divergence"]["classification"] == "dut_late"


def test_first_divergence_reports_edge_active_mismatch_when_settled_values_match(tmp_path: Path, monkeypatch: Any) -> None:
    rtl = """module m(clk, settings);
  input clk;
  output [1:0] settings;
  reg [1:0] settings;
  always @(posedge clk) settings <= 2'b01;
endmodule
"""
    rtl_path = tmp_path / "rtl.sv"
    rtl_path.write_text(rtl, encoding="utf-8")
    (tmp_path / "contract.json").write_text(json.dumps({"module_name": "m", "clocking": {"clock": {"name": "clk"}}}) + "\n", encoding="utf-8")
    (tmp_path / "tb.sv").write_text(
        "module tb; m top_module1(); ref_m good1(); "
        "always @(posedge clk) begin if (!tb_match) errors = errors + 1; end endmodule\n",
        encoding="utf-8",
    )
    (tmp_path / "wave.vcd").write_text("$date\n$date\n", encoding="utf-8")
    sim_log = CommandResult(
        cmd=["sim"],
        returncode=1,
        stdout="Mismatches: 1 in 2 samples\nHint: Output 'settings' has 1 mismatches. First mismatch occurred at time 5.\n",
        stderr="",
    ).model_dump_json()
    monkeypatch.setattr(trace_report_module, "VCDVCD", _EdgeActiveDivergenceVcd)

    stable = build_first_divergence_report(rtl_path=rtl_path, output_dir=tmp_path, sim_log_json=sim_log, sampling_mode="stable")
    result = build_first_divergence_report(rtl_path=rtl_path, output_dir=tmp_path, sim_log_json=sim_log)

    assert stable["status"] == "no_divergence"
    assert result["status"] == "stable_values_match_but_tb_edge_mismatch"
    assert result["first_divergence"]["signal"] == "settings"
    assert result["first_divergence"]["time"] == 5
    assert result["first_divergence"]["sampling_mode"] == "edge_active"
    assert result["first_divergence"]["edge"] == "posedge"
    assert result["first_divergence"]["driver_assignment_kind"] == "nonblocking"
    assert result["first_divergence"]["dut"] == "00"
    assert result["first_divergence"]["ref"] == "01"


def test_first_divergence_uses_authoritative_tb_sample_and_keeps_early_transient_secondary(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    rtl = """module runtime_top(clk, settings);
  input clk;
  output [1:0] settings;
  reg [1:0] settings;
  always @(posedge clk) settings <= 2'b01;
endmodule
"""
    rtl_path = tmp_path / "runtime_top.v"
    rtl_path.write_text(rtl, encoding="utf-8")
    (tmp_path / "contract.json").write_text(
        json.dumps({"module_name": "planner_top", "clocking": {"clock": {"name": "clk"}}}) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "tb.sv").write_text(
        """module tb;
  runtime_top top_module1();
  ref_m good1();
  always @(posedge clk) begin
    if (!tb_match) errors = errors + 1;
  end
endmodule
""",
        encoding="utf-8",
    )
    (tmp_path / "wave.vcd").write_text("$date\n$date\n", encoding="utf-8")
    sim_log = CommandResult(
        cmd=["sim"],
        returncode=1,
        stdout=(
            "Hint: Output 'errors_settings' has 3 mismatches. First mismatch occurred at time 5.\n"
            "Hint: Output 'settings' has 1 mismatches. First mismatch occurred at time 25.\n"
        ),
        stderr="",
    ).model_dump_json()
    monkeypatch.setattr(trace_report_module, "VCDVCD", _AuthoritativeSamplingVcd)

    result = build_first_divergence_report(
        rtl_path=rtl_path,
        output_dir=tmp_path,
        sim_log_json=sim_log,
        runtime_top_module="runtime_top",
    )

    assert result["status"] == "ok"
    assert result["runtime_top_module"] == "runtime_top"
    assert result["dut_instance"] == "top_module1"
    assert result["authoritative_fail_time"] == 25
    assert result["ignored_tb_metrics"][0]["sig"] == "errors_settings"
    assert result["sampling_event"] == {"edge": "posedge", "clock": "clk", "source": "tb_checker"}
    assert result["first_divergence"]["time"] == 25
    assert result["first_divergence"]["sampling_mode"] == "edge_active"
    assert result["pre_sample_transients"][0]["time"] == 5
    assert result["pre_sample_transients"][0]["classification"] == "pre_sample_transient"

    report, _ = build_trace_report(
        rtl_path=rtl_path,
        sim_log_json=sim_log,
        output_dir=tmp_path,
        planner_module_name="planner_top",
        runtime_top_module="runtime_top",
    )
    assert report["fail_time"] == 25
    assert report["first_failure"]["time"] == 25
    assert report["root_failure"]["time"] == 25
    assert report["value_backtrace"]["sampling_mode"] == "edge_active"
    assert report["value_backtrace"]["chains"][0]["expected"] == "01"
    assert report["value_backtrace"]["chains"][0]["actual"] == "00"


def test_first_divergence_reports_unresolved_when_log_time_does_not_align_to_tb_sample(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    rtl_path = tmp_path / "runtime_top.v"
    rtl_path.write_text(
        "module runtime_top(input clk, output reg [1:0] settings);\n"
        "always @(posedge clk) settings <= 2'b01;\nendmodule\n",
        encoding="utf-8",
    )
    (tmp_path / "tb.sv").write_text(
        "module tb; runtime_top top_module1(); ref_m good1(); "
        "always @(posedge clk) begin if (!tb_match) errors = errors + 1; end endmodule\n",
        encoding="utf-8",
    )
    (tmp_path / "wave.vcd").write_text("$date\n$date\n", encoding="utf-8")
    sim_log = CommandResult(
        stdout="Hint: Output 'settings' has 1 mismatches. First mismatch occurred at time 20.\n",
        stderr="",
    ).model_dump_json()
    monkeypatch.setattr(trace_report_module, "VCDVCD", _AuthoritativeSamplingVcd)

    result = build_first_divergence_report(
        rtl_path=rtl_path,
        output_dir=tmp_path,
        sim_log_json=sim_log,
        runtime_top_module="runtime_top",
    )

    assert result["status"] == "sampling_alignment_unresolved"
    assert result["authoritative_fail_time"] == 20
    assert result["edge_active_candidate"]["time"] == 25

    report, _ = build_trace_report(
        rtl_path=rtl_path,
        sim_log_json=sim_log,
        output_dir=tmp_path,
        planner_module_name="planner_top",
        runtime_top_module="runtime_top",
    )
    assert report["fail_time"] == 20
    assert report["root_failure"] is None
    assert report["first_failure"] is None
    assert report["value_backtrace"]["fallback_reason"] == "sampling_alignment_unresolved"


def test_verilog_constants_are_not_extracted_as_vcd_signals() -> None:
    rtl = """module m(input clk, input [2:0] state, input [7:0] a, output reg [127:0] q);
  always @(posedge clk) begin
    if (state == 3'd0)
      q <= 128'h0000_0000_0000_0000_0000_0000_0000_0000;
    else
      q <= a ^ 8'hff;
  end
  always @(posedge clk) begin
    flag <= '0;
    nibble <= 4'sb10xz;
    mask <= 'hff;
  end
endmodule
"""

    assignments = parse_rtl_assignments(rtl)
    q_assignments = [item for item in assignments if item.lhs == "q"]
    constant_q = next(item for item in q_assignments if item.rhs_expression.startswith("128'h"))
    mixed_q = next(item for item in q_assignments if "a ^" in item.rhs_expression)

    assert constant_q.rhs_signals == ()
    assert constant_q.condition_signals == ("state",)
    assert mixed_q.rhs_signals == ("a",)
    assert next(item for item in assignments if item.lhs == "flag").rhs_signals == ()
    assert next(item for item in assignments if item.lhs == "nibble").rhs_signals == ()
    assert next(item for item in assignments if item.lhs == "mask").rhs_signals == ()
    assert not any(
        signal.startswith(("h", "b", "d"))
        for assignment in assignments
        for signal in (*assignment.rhs_signals, *assignment.condition_signals)
    )


def test_multiline_assignment_preserves_all_if_else_branches_and_conditions() -> None:
    rtl = """module top(
  input clk, input rst, input [1:0] fsm_state,
  input [7:0] state_a, state_b, output logic [15:0] text_out
);
  always @(posedge clk) begin
    if (rst) begin
      text_out <= '0;
    end else if (fsm_state == 2'd3) begin
      text_out <= {
        state_a,
        state_b
      };
    end else begin
      text_out <= text_out;
    end
  end
endmodule
"""

    assignments = [item for item in parse_rtl_assignments(rtl) if item.lhs == "text_out"]

    assert len(assignments) == 3
    reset, done, fallback = assignments
    assert reset.condition_exprs == ("rst",)
    assert done.condition_exprs == ("!rst", "fsm_state == 2'd3")
    assert fallback.condition_exprs == ("!rst", "!(fsm_state == 2'd3)")
    assert done.rhs_signals == ("state_a", "state_b")
    assert done.end_line > done.start_line
    assert "state_a,\n" in done.code_snippet


def test_value_backtrace_classifies_pure_constant_assignment_without_vcd_lookup() -> None:
    rtl = "module m(output q); assign q = 8'h00; endmodule\n"
    assignments = parse_rtl_assignments(rtl)
    sampled: list[str] = []

    def sample_signal(*, leaf: str, t: int, prefer_dut: bool) -> str | None:
        del t, prefer_dut
        sampled.append(leaf)
        return None

    result = build_value_backtrace(
        fail_outputs=[{"sig": "q", "expected": "1", "actual": "0"}],
        fail_time=25,
        assignments=assignments,
        sample_signal=sample_signal,
    )

    step = result["chains"][0]["chain"][0]
    assert step["classification"] == "constant_assignment"
    assert step["rhs_observed_values"] == {}
    assert sampled == []


def test_debug_reads_materializer_reports_missing_module_node(tmp_path: Path) -> None:
    rtl = """module m(input a, output y);
  assign y = a;
endmodule
"""
    rtl_path = tmp_path / "m.sv"
    rtl_path.write_text(rtl, encoding="utf-8")
    blocks = parse_rtl_blocks(rtl)

    class MissingModuleKg(_FakeKgService):
        def query(self, cypher: str, params: dict[str, Any] | None = None, limit: int | None = None) -> dict[str, Any]:
            if "RETURN m.name AS module" in cypher:
                return {"rows": []}
            return super().query(cypher, params, limit)

    result = DebugReadsMaterializer(MissingModuleKg(repo_path=tmp_path, blocks=blocks)).materialize(
        module_name="m",
        session_id="m:session:missing",
        current_rtl_path=rtl_path,
        current_blocks=blocks,
    )

    assert result.materialized_edges == 0
    assert result.module_rows_count == 0
    assert result.skipped_modules == [{"module": "m", "reason": "module_node_missing_or_parse_failed"}]
    assert "module_node_missing_or_parse_failed" in result.fallback_reason


def test_module_debug_runner_initial_result_callback() -> None:
    calls: list[tuple[str, str, ModuleDebugResult]] = []
    runner = ModuleDebugRunner(
        config=RtlDebugConfig(openai_config=None),
        workspace_root="/tmp/zerorepo-debug-test",
        initial_result_recorder=lambda module, merged, result: calls.append((module, str(merged), result)),
    )

    pass_result = runner._initial_debug_result(
        module_name="m",
        is_pass=True,
        mismatch_count=0,
        sim_output=CommandResult(stdout="ok", stderr="").model_dump_json(),
        workdir=Path("/tmp/zerorepo-debug-test/debug/m"),
    )
    fail_result = runner._initial_debug_result(
        module_name="m",
        is_pass=False,
        mismatch_count=7,
        sim_output=CommandResult(stdout="bad", stderr="").model_dump_json(),
        workdir=Path("/tmp/zerorepo-debug-test/debug/m"),
    )
    runner._record_initial_result(module_name="m", merged_file="m.v", result=fail_result)

    assert pass_result.status == "pass"
    assert fail_result.status == "fail"
    assert fail_result.mismatch_count == 7
    assert calls == [("m", "m.v", fail_result)]


def test_module_debug_runner_persists_last_failed_repair(tmp_path: Path, monkeypatch: Any) -> None:
    oracle_dir = tmp_path / "oracle" / "m" / "verification"
    oracle_dir.mkdir(parents=True)
    (oracle_dir / "m_testbench.sv").write_text("module tb; endmodule\n", encoding="utf-8")
    merged_file = tmp_path / "workspace" / "merged" / "m.v"
    merged_file.parent.mkdir(parents=True)
    merged_file.write_text("module m; assign y = 1'b0; endmodule\n", encoding="utf-8")

    class FailingReviewer:
        def __init__(self, workdir: str, support_path: str) -> None:
            self.workdir = workdir
            self.support_path = support_path

        def review(self) -> tuple[bool, int, str]:
            return False, 1, CommandResult(stdout="mismatch", stderr="").model_dump_json()

    def fake_editor(self: ModuleDebugRunner, **kwargs: Any) -> tuple[bool, str, int]:
        workdir = Path(kwargs["workdir"])
        repaired = "module m; assign y = 1'b1; endmodule\n"
        (workdir / "rtl.sv").write_text(repaired, encoding="utf-8")
        return False, repaired, 1

    monkeypatch.setattr(debug_runner_module, "SimReviewer", FailingReviewer)
    monkeypatch.setattr(debug_runner_module, "check_syntax", lambda *_args, **_kwargs: (True, CommandResult(stdout="", stderr="").model_dump_json()))
    monkeypatch.setattr(ModuleDebugRunner, "_ensure_toolchain_path", lambda self: None)
    monkeypatch.setattr(ModuleDebugRunner, "_run_repo_react", fake_editor)

    runner = ModuleDebugRunner(
        config=RtlDebugConfig(openai_config=None, oracle_root=str(tmp_path / "oracle"), max_trials=1),
        workspace_root=tmp_path / "workspace",
    )
    result = runner.run_module(
        module_name="m",
        merged_file=merged_file,
        task=None,
        spec_text="",
        contract_json=json.dumps({"module_name": "m"}),
    )

    assert result.status == "fail"
    assert "1'b1" in merged_file.read_text(encoding="utf-8")


class _FailingSimReviewer:
    def __init__(self, workdir: str, support_path: str) -> None:
        self.workdir = workdir
        self.support_path = support_path

    def review(self) -> tuple[bool, int, str]:
        return (
            False,
            3,
            CommandResult(
                stdout="Hint: Output 'out' has 3 mismatches. First mismatch occurred at time 10.\nMismatches: 3 in 3 samples\n",
                stderr="",
            ).model_dump_json(),
        )


def _write_debug_oracle(root: Path, module_name: str) -> None:
    verification_dir = root / module_name / "verification"
    verification_dir.mkdir(parents=True, exist_ok=True)
    (verification_dir / f"{module_name}_testbench.sv").write_text("module tb;\nendmodule\n", encoding="utf-8")


def test_module_debug_runner_uses_original_spec_and_stage1_metadata_for_editor(tmp_path: Path, monkeypatch: Any) -> None:
    workspace_root = tmp_path / "workspace"
    oracle_root = tmp_path / "oracle"
    merged_file = tmp_path / "m.v"
    merged_file.write_text("module m(input clk, input rst, output [7:0] out); endmodule\n", encoding="utf-8")
    _write_debug_oracle(oracle_root, "m")

    runner = ModuleDebugRunner(
        config=RtlDebugConfig(oracle_root=str(oracle_root), openai_config=None),
        workspace_root=workspace_root,
    )
    stage1_metadata = json.dumps({"module_name": "m", "io": [{"name": "out", "dir": "output", "width": 8}]}, indent=2)
    captured: dict[str, Any] = {}

    monkeypatch.setattr(debug_runner_module, "SimReviewer", _FailingSimReviewer)
    monkeypatch.setattr(debug_runner_module, "check_syntax", lambda *_args, **_kwargs: (True, CommandResult(stdout="", stderr="").model_dump_json()))

    def fake_run_editor(self: ModuleDebugRunner, **kwargs: Any) -> tuple[bool, str, int]:
        captured.update(kwargs)
        return True, kwargs["contract_json"], 1

    monkeypatch.setattr(ModuleDebugRunner, "_run_repo_react", fake_run_editor)

    result = runner.run_module(
        module_name="m",
        merged_file=merged_file,
        task=SimpleNamespace(),
        spec_text="module spec",
        contract_json=stage1_metadata,
        spec_source_path="/tmp/specs/m.md",
    )

    workdir = Path(result.workdir)
    manifest = json.loads((workdir / "debug_input_manifest.json").read_text(encoding="utf-8"))

    assert result.status == "fixed"
    assert json.loads((workdir / "contract.json").read_text(encoding="utf-8")) == json.loads(stage1_metadata)
    assert json.loads((workdir / "stage1_contract.json").read_text(encoding="utf-8")) == json.loads(stage1_metadata)
    assert json.loads(captured["contract_json"]) == json.loads(stage1_metadata)
    assert captured["spec_text"] == "module spec"
    assert captured["behavior_source"] == "spec_tb"
    assert not (workdir / "architect_prompt.txt").exists()
    assert not (workdir / "contract_lint.txt").exists()
    assert manifest["debug_behavior_source"] == "original_spec_and_visible_tb"
    assert manifest["diagnostic_metadata_source"] == "stage1"
    assert manifest["tb_visibility"] == "tb_only"
    assert manifest["spec_source_path"] == "/tmp/specs/m.md"


def test_module_debug_runner_keeps_stage1_metadata_when_debug_fails(tmp_path: Path, monkeypatch: Any) -> None:
    workspace_root = tmp_path / "workspace"
    oracle_root = tmp_path / "oracle"
    merged_file = tmp_path / "m.v"
    merged_file.write_text("module m(input clk, input rst, output [7:0] out); endmodule\n", encoding="utf-8")
    _write_debug_oracle(oracle_root, "m")

    runner = ModuleDebugRunner(
        config=RtlDebugConfig(oracle_root=str(oracle_root), openai_config=None),
        workspace_root=workspace_root,
    )
    stage1_metadata = json.dumps({"module_name": "m", "io": [{"name": "out", "dir": "output", "width": 8}]}, indent=2)
    captured: dict[str, Any] = {}

    monkeypatch.setattr(debug_runner_module, "SimReviewer", _FailingSimReviewer)
    monkeypatch.setattr(debug_runner_module, "check_syntax", lambda *_args, **_kwargs: (True, CommandResult(stdout="", stderr="").model_dump_json()))

    def fake_run_editor(self: ModuleDebugRunner, **kwargs: Any) -> tuple[bool, str, int]:
        captured["contract_json"] = kwargs["contract_json"]
        return False, "", 1

    monkeypatch.setattr(ModuleDebugRunner, "_run_repo_react", fake_run_editor)

    result = runner.run_module(
        module_name="m",
        merged_file=merged_file,
        task=SimpleNamespace(),
        spec_text="module spec",
        contract_json=stage1_metadata,
        spec_source_path="/tmp/specs/m.md",
    )

    workdir = Path(result.workdir)
    contract_text = (workdir / "contract.json").read_text(encoding="utf-8")
    manifest = json.loads((workdir / "debug_input_manifest.json").read_text(encoding="utf-8"))

    assert result.status == "fail"
    assert json.loads(contract_text) == json.loads(stage1_metadata)
    assert json.loads(captured["contract_json"]) == json.loads(stage1_metadata)
    assert manifest["debug_behavior_source"] == "original_spec_and_visible_tb"


class _WriterKgService:
    def __init__(self, root: Path) -> None:
        self.repo_uid = "repo1"
        self.repo_path = root
        self._ingestor = _FakeIngestor()
        self.refresh_calls: list[dict[str, Any]] = []

    def refresh_repo_files(self, *, changed_paths: list[str], stage: str, filter_to_planned_skeleton: bool) -> None:
        self.refresh_calls.append(
            {
                "changed_paths": changed_paths,
                "stage": stage,
                "filter_to_planned_skeleton": filter_to_planned_skeleton,
            }
        )

    def initialize(self) -> None:
        return None

    def query(self, cypher: str, params: dict[str, Any] | None = None, limit: int | None = None) -> dict[str, Any]:
        del cypher, params, limit
        return {"rows": [{"module_uid": "module:m"}]}


def test_module_result_writer_keeps_stage_specific_simulation_results(tmp_path: Path) -> None:
    kg = _WriterKgService(tmp_path)
    writer = ModuleResultWriter(
        kg_service=kg,
        workspace_root=tmp_path,
        checkpoint_dir=tmp_path,
    )
    merged_file = tmp_path / "m.v"
    merged_file.write_text("module m; endmodule\n", encoding="utf-8")

    writer.record_module_result(
        module_name="m",
        merged_file=merged_file,
        debug_result=SimpleNamespace(status="fail", mismatch_count=3),
        stage="post_initial_sim",
    )
    writer.record_module_result(
        module_name="m",
        merged_file=merged_file,
        debug_result=SimpleNamespace(status="fixed", mismatch_count=0, debug_trials=2),
        stage="post_module_debug",
    )

    payload = json.loads((tmp_path / "rtl_kg_module_statuses.json").read_text(encoding="utf-8"))
    assert payload["modules"]["m"]["stage"] == "post_module_debug"
    assert set(payload["records"]["m"]) == {"post_initial_sim", "post_module_debug"}

    node_uids = {node["uid"] for call in kg._ingestor.calls for node in call["nodes"]}
    edge_uids = {edge["uid"] for call in kg._ingestor.calls for edge in call["edges"]}
    assert "repo1:simulation_result:m:post_initial_sim" in node_uids
    assert "repo1:simulation_result:m:post_module_debug" in node_uids
    assert "repo1:has_sim_result:m:post_initial_sim" in edge_uids
    assert "repo1:has_sim_result:m:post_module_debug" in edge_uids
    assert kg.refresh_calls[-1]["stage"] == "post_module_debug"
