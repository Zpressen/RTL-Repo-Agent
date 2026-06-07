from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from zerorepo.rtl_impl.debug_agent import rtl_editor
from zerorepo.rtl_impl.debug_agent.adapters import build_debug_contract_json
from zerorepo.rtl_impl.debug_agent.asserter import AsserterResult, _extract_ports as extract_assert_ports
from zerorepo.rtl_impl.debug_agent.boolean_proofer import BooleanProoferResult, _extract_ports as extract_proof_ports
from zerorepo.rtl_impl.debug_agent.rtl_editor import _EditSession
from zerorepo.rtl_impl.debug_agent.trace_report import (
    _build_window_times,
    _vcd_find_signal,
    _vcd_signal_names,
    _vcd_time_values,
    build_value_backtrace,
)
from zerorepo.rtl_impl.debug_agent.trace_slicer import parse_rtl_assignments, parse_rtl_blocks


def _build_contract(*, clock: str, registered_objects: list[dict[str, object]]) -> dict[str, object]:
    stage1 = {
        "interface_contracts": [
            {
                "module": "m",
                "ports": [
                    {"name": "clk", "direction": "input", "width": "1"},
                    {"name": "rst", "direction": "input", "width": "1"},
                    {"name": "out", "direction": "output", "width": "8"},
                ],
                "clock": "clk",
                "reset": "rst",
                "reset_polarity": "active-low",
            }
        ],
        "timing_contracts": [
            {
                "module": "m",
                "clocking": {"clock": clock, "update_edge": "rising clock edge"},
                "reset_behavior": {"signal": "rst", "active": "unspecified"},
                "registered_objects": registered_objects,
            }
        ],
    }
    return json.loads(build_debug_contract_json(module_name="m", stage1_contracts=stage1, spec_text=""))


def test_debug_contract_normalizes_sequential_timing_without_inventing_latency() -> None:
    contract = _build_contract(clock="clk", registered_objects=[{"name": "out"}])

    assert contract["io"][2]["dir"] == "output"
    assert contract["io"][2]["direction"] == "output"
    assert contract["clocking"] == {
        "is_sequential": True,
        "clock": {"name": "clk", "edge": "posedge"},
        "reset": {"name": "rst", "active": "low", "type": None},
        "timing_contract": contract["raw_timing_contract"],
    }
    assert contract["timing"] == {"out": {"latency_cycles": None}}


def test_debug_contract_marks_explicit_combinational_outputs_zero_latency() -> None:
    contract = _build_contract(clock="none", registered_objects=[])

    assert contract["clocking"]["is_sequential"] is False
    assert contract["timing"] == {"out": {"latency_cycles": 0}}


@pytest.mark.parametrize("direction_key", ["dir", "direction"])
def test_diagnostic_consumers_accept_both_direction_keys(direction_key: str) -> None:
    contract = {"io": [{"name": "out", direction_key: "output", "width": "8"}]}

    assert extract_assert_ports(contract)[0].direction == "output"
    assert extract_proof_ports(contract)[0].direction == "output"


class _FakeSignal:
    def __init__(self, tv: list[tuple[int, str]]) -> None:
        self.tv = tv


class _PrivateSignalsVcd:
    def __init__(self) -> None:
        self._signals = {
            "tb.clk": _FakeSignal([(0, "0"), (5, "1"), (10, "0"), (15, "1")]),
            "tb.out_dut": _FakeSignal([(0, "0"), (12, "1")]),
        }


def test_vcd_sampling_reads_private_signals() -> None:
    vcd = _PrivateSignalsVcd()

    assert _vcd_find_signal(vcd, "clk") == "tb.clk"
    assert _vcd_time_values(vcd, "tb.clk") == [(0, "0"), (5, "1"), (10, "0"), (15, "1")]
    assert _build_window_times(vcd, t_star=15) == [5, 10, 15]


class _LegacyVcd:
    def __init__(self) -> None:
        self._signals = ["tb.clk", "tb.out_dut"]
        self._data = {
            "!": {"references": ["tb.clk"], "tv": [(0, "0"), (5, "1"), (10, "0"), (15, "1")]},
            '"': {"references": ["tb.out_dut"], "tv": [(0, "0"), (12, "1")]},
        }

    def get_data(self) -> dict[str, dict[str, object]]:
        return self._data

    def get_signals(self) -> list[str]:
        return self._signals


def test_vcd_sampling_reads_legacy_private_data() -> None:
    vcd = _LegacyVcd()

    assert _vcd_signal_names(vcd) == ["tb.clk", "tb.out_dut"]
    assert _vcd_time_values(vcd, "tb.clk") == [(0, "0"), (5, "1"), (10, "0"), (15, "1")]
    assert _build_window_times(vcd, t_star=15) == [5, 10, 15]


def test_vcd_signal_names_fall_back_to_reference_ids() -> None:
    vcd = SimpleNamespace(
        references_to_ids={"tb.clk": "!", "tb.data": '"'},
        data={"!": _FakeSignal([(0, "0"), (5, "1")])},
    )

    assert _vcd_signal_names(vcd) == ["tb.clk", "tb.data"]
    assert _vcd_find_signal(vcd, "clk") == "tb.clk"
    assert _vcd_time_values(vcd, "tb.clk") == [(0, "0"), (5, "1")]


def test_parse_rtl_assignments_extracts_common_driver_shapes() -> None:
    rtl = """module m(input clk, input rd, input empty, input [1:0] addr, input [7:0] a, b, output logic [7:0] y, q);
  logic [7:0] q_nxt, ram_0;
  assign y = a & b;
  always @(posedge clk) begin
    if (rd && !empty) q <= q_nxt;
  end
  always @(*) begin
    case (addr)
      2'd0: q_nxt = ram_0;
      default: q_nxt = 8'h00;
    endcase
  end
endmodule
"""

    assignments = parse_rtl_assignments(rtl)
    by_lhs = {assignment.lhs: assignment for assignment in assignments if assignment.lhs != "q_nxt"}
    q_nxt_assignments = [assignment for assignment in assignments if assignment.lhs == "q_nxt"]

    assert by_lhs["y"].kind == "continuous"
    assert set(by_lhs["y"].rhs_signals) == {"a", "b"}
    assert by_lhs["q"].kind == "nonblocking"
    assert set(by_lhs["q"].rhs_signals) == {"q_nxt"}
    assert set(by_lhs["q"].condition_signals) == {"empty", "rd"}
    assert any("addr" in assignment.condition_signals and "ram_0" in assignment.rhs_signals for assignment in q_nxt_assignments)


def test_value_backtrace_classifies_stale_lhs_and_blocking_condition() -> None:
    rtl = """module m(input clk, input rd, input empty, output logic [7:0] q);
  logic [7:0] q_nxt;
  always @(posedge clk) begin
    if (rd && !empty) q <= q_nxt;
  end
endmodule
"""
    assignments = parse_rtl_assignments(rtl)
    values = {"q": "00000000", "q_nxt": "01000100", "rd": "1", "empty": "1"}

    def sample_signal(*, leaf: str, t: int, prefer_dut: bool = False) -> str | None:
        del t, prefer_dut
        return values.get(leaf)

    result = build_value_backtrace(
        fail_outputs=[{"sig": "q", "expected": "01000100", "actual": "00000000"}],
        fail_time=216,
        assignments=assignments,
        sample_signal=sample_signal,
    )

    step = result["chains"][0]["chain"][0]
    assert step["classification"] == "condition_blocks_update"
    assert step["rhs_observed_values"] == {"q_nxt": "01000100"}
    assert step["condition_values"] == {"empty": "1", "rd": "1"}


def test_value_backtrace_continues_upstream_to_mux_like_source() -> None:
    rtl = """module m(input clk, input [1:0] addr, output logic [7:0] q);
  logic [7:0] q_nxt, ram_0;
  always @(posedge clk) q <= q_nxt;
  always @(*) begin
    case (addr)
      2'd0: q_nxt = ram_0;
      default: q_nxt = 8'h00;
    endcase
  end
endmodule
"""
    assignments = parse_rtl_assignments(rtl)
    values = {"q": "00000000", "q_nxt": "00000000", "ram_0": "01000100", "addr": "00"}

    def sample_signal(*, leaf: str, t: int, prefer_dut: bool = False) -> str | None:
        del t, prefer_dut
        return values.get(leaf)

    result = build_value_backtrace(
        fail_outputs=[{"sig": "q", "expected": "01000100", "actual": "00000000"}],
        fail_time=216,
        assignments=assignments,
        sample_signal=sample_signal,
    )

    chain = result["chains"][0]["chain"]
    assert chain[0]["classification"] == "lhs_matches_rhs_continue_upstream"
    assert chain[1]["signal"] == "q_nxt"
    assert chain[1]["classification"] == "source_matches_expected_mux_wrong"


def test_value_backtrace_marks_missing_rhs_vcd_signal() -> None:
    assignments = parse_rtl_assignments(
        """module m(input clk, output logic [7:0] q);
  logic [7:0] q_nxt;
  always @(posedge clk) q <= q_nxt;
endmodule
"""
    )

    def sample_signal(*, leaf: str, t: int, prefer_dut: bool = False) -> str | None:
        del leaf, t, prefer_dut
        return None

    result = build_value_backtrace(
        fail_outputs=[{"sig": "q", "expected": "1", "actual": "0"}],
        fail_time=10,
        assignments=assignments,
        sample_signal=sample_signal,
    )

    assert result["chains"][0]["chain"][0]["classification"] == "missing_vcd_signal"


class _FakeReviewer:
    def __init__(self, outcome: tuple[bool, int, str]) -> None:
        self.outcome = outcome
        self.calls = 0

    def review(self) -> tuple[bool, int, str]:
        self.calls += 1
        return self.outcome


def _edit_session(tmp_path: Path, reviewer: _FakeReviewer) -> tuple[_EditSession, Path]:
    rtl_path = tmp_path / "rtl.sv"
    rtl_path.write_text("module m;\n  wire a;\n  child u(.a(a));\nendmodule\n", encoding="utf-8")
    return (
        _EditSession(
            tb_path=str(tmp_path / "tb.sv"),
            rtl_path=str(rtl_path),
            output_dir=str(tmp_path),
            last_mismatch_cnt=1,
            sim_reviewer=reviewer,  # type: ignore[arg-type]
            max_trials=2,
        ),
        rtl_path,
    )


def test_apply_patch_set_rejects_multiple_ranges_in_one_trial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reviewer = _FakeReviewer((True, 0, json.dumps({"stdout": "passed", "stderr": ""})))
    session, rtl_path = _edit_session(tmp_path, reviewer)
    original = rtl_path.read_text(encoding="utf-8")
    monkeypatch.setattr(rtl_editor, "check_syntax", lambda _path: (True, ""))

    result = session.apply_patch_set(
        [
            {"start_line": 2, "end_line": 2, "new_code": "  logic [7:0] a;"},
            {"start_line": 3, "end_line": 3, "new_code": "  child u(.a(a[0]));"},
        ]
    )

    assert result["is_action_executed"] is False
    assert "exactly one semantic line-range patch" in result["error_msg"]
    assert session.action_calls == 0
    assert reviewer.calls == 0
    assert rtl_path.read_text(encoding="utf-8") == original
    assert session.repair_journal[-1]["effect"] == "rejected"
    assert "Batch patch was rejected" in session.repair_journal[-1]["lesson"]


def test_apply_patch_set_accepts_decimal_string_ranges(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reviewer = _FakeReviewer((True, 0, json.dumps({"stdout": "passed", "stderr": ""})))
    session, rtl_path = _edit_session(tmp_path, reviewer)
    monkeypatch.setattr(rtl_editor, "check_syntax", lambda _path: (True, ""))

    result = session.apply_patch_set(
        [
            {"start_line": "2", "end_line": "2", "new_code": "  logic [7:0] a;"},
        ]
    )

    assert result["is_action_executed"] is True
    assert session.action_calls == 1
    assert reviewer.calls == 1
    assert "logic [7:0] a" in rtl_path.read_text(encoding="utf-8")
    assert session.repair_journal[-1]["action_type"] == "apply_patch_set"
    assert session.repair_journal[-1]["effect"] == "passed"
    assert (tmp_path / "repair_journal.json").exists()


def test_apply_patch_set_accepts_line_start_aliases(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reviewer = _FakeReviewer((True, 0, json.dumps({"stdout": "passed", "stderr": ""})))
    session, rtl_path = _edit_session(tmp_path, reviewer)
    monkeypatch.setattr(rtl_editor, "check_syntax", lambda _path: (True, ""))

    result = session.apply_patch_set(
        [
            {"line_start": "2", "line_end": "2", "new_code": "  logic [7:0] a;"},
        ]
    )

    assert result["is_action_executed"] is True
    assert session.action_calls == 1
    assert reviewer.calls == 1
    assert "logic [7:0] a" in rtl_path.read_text(encoding="utf-8")


def test_apply_patch_set_accepts_new_line_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reviewer = _FakeReviewer((True, 0, json.dumps({"stdout": "passed", "stderr": ""})))
    session, rtl_path = _edit_session(tmp_path, reviewer)
    monkeypatch.setattr(rtl_editor, "check_syntax", lambda _path: (True, ""))

    result = session.apply_patch_set(
        [
            {"start_line": 2, "end_line": 2, "new_line": "  logic [7:0] a;"},
        ]
    )

    assert result["is_action_executed"] is True
    assert session.action_calls == 1
    assert reviewer.calls == 1
    assert "logic [7:0] a" in rtl_path.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "patches",
    [
        [
            {"start_line": 2, "end_line": 3, "new_code": "  logic a;"},
            {"start_line": 3, "end_line": 3, "new_code": "  child u(.a(a));"},
        ],
        [{"start_line": 5, "end_line": 5, "new_code": "  logic a;"}],
        [{"start_line": "2.0", "end_line": "2", "new_code": "  logic a;"}],
        [{"start_line": "-1", "end_line": "2", "new_code": "  logic a;"}],
        [{"start_line": "line2", "end_line": "2", "new_code": "  logic a;"}],
    ],
)
def test_apply_patch_set_rejects_invalid_ranges_without_writing(tmp_path: Path, patches: list[dict[str, object]]) -> None:
    reviewer = _FakeReviewer((True, 0, "{}"))
    session, rtl_path = _edit_session(tmp_path, reviewer)
    original = rtl_path.read_text(encoding="utf-8")

    result = session.apply_patch_set(patches)  # type: ignore[arg-type]

    assert result["is_action_executed"] is False
    assert rtl_path.read_text(encoding="utf-8") == original
    assert session.action_calls == 0
    assert reviewer.calls == 0


def test_apply_patch_set_rolls_back_failed_simulation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reviewer = _FakeReviewer((False, 2, json.dumps({"stdout": "mismatch", "stderr": ""})))
    session, rtl_path = _edit_session(tmp_path, reviewer)
    original = rtl_path.read_text(encoding="utf-8")
    monkeypatch.setattr(rtl_editor, "check_syntax", lambda _path: (True, ""))

    result = session.apply_patch_set([{"start_line": 2, "end_line": 2, "new_code": "  logic a;"}])

    assert result["is_action_executed"] is False
    assert "rolled back" in result["error_msg"]
    assert rtl_path.read_text(encoding="utf-8") == original
    assert session.repair_journal[-1]["effect"] == "rejected"
    assert "rolled back" in session.repair_journal[-1]["after"]["error_msg"]


def test_apply_patch_set_rolls_back_failed_syntax(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reviewer = _FakeReviewer((True, 0, "{}"))
    session, rtl_path = _edit_session(tmp_path, reviewer)
    original = rtl_path.read_text(encoding="utf-8")
    monkeypatch.setattr(rtl_editor, "check_syntax", lambda _path: (False, "syntax error"))

    result = session.apply_patch_set([{"start_line": 2, "end_line": 2, "new_code": "  logic a"}])

    assert result["is_action_executed"] is False
    assert result["error_msg"] == "Syntax error. Action rolled back."
    assert rtl_path.read_text(encoding="utf-8") == original
    assert reviewer.calls == 0
    assert session.repair_journal[-1]["effect"] == "syntax_failed"
    assert "syntax" in session.repair_journal[-1]["lesson"].lower()


def test_replace_block_records_repair_journal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reviewer = _FakeReviewer((True, 0, json.dumps({"stdout": "passed", "stderr": ""})))
    session, rtl_path = _edit_session(tmp_path, reviewer)
    blocks = parse_rtl_blocks(rtl_path.read_text(encoding="utf-8"))
    session.blocks_by_id = {block.id: block for block in blocks}
    monkeypatch.setattr(rtl_editor, "check_syntax", lambda _path: (True, ""))

    result = session.replace_block("A1", "  wire b;")

    assert result["is_action_executed"] is True
    assert session.repair_journal[-1]["action_type"] == "replace_block"
    assert session.repair_journal[-1]["target"]["block_id"] == "A1"
    assert session.repair_journal[-1]["effect"] == "passed"
    assert result["repair_journal_summary"][-1]["action_type"] == "replace_block"


def test_trace_summary_includes_recent_repair_journal_entries(tmp_path: Path) -> None:
    session, _rtl_path = _edit_session(tmp_path, _FakeReviewer((False, 1, "{}")))
    session.trace_report = {"diagnostic_narrative": ["top"], "fail_outputs": []}
    session.repair_journal = [
        {
            "trial": i,
            "action_type": "apply_patch_set",
            "target": {"start_line": i, "end_line": i},
            "patch_count": 1,
            "patch_summary": f"patch {i}",
            "before": {"mismatch_cnt": 10, "fail_time": 1, "top_diagnosis": "top"},
            "after": {"accepted": True, "is_sim_pass": False, "mismatch_cnt": 9, "fail_time": 2, "error_msg": ""},
            "effect": "improved",
            "lesson": f"lesson {i}",
        }
        for i in range(1, 7)
    ]

    summary = session.trace_summary()

    assert [entry["trial"] for entry in summary["repair_journal_summary"]] == [2, 3, 4, 5, 6]
    assert summary["repair_journal_summary"][-1]["lesson"] == "lesson 6"


def test_tool_apply_patch_set_returns_repair_journal_summary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reviewer = _FakeReviewer((True, 0, json.dumps({"stdout": "passed", "stderr": ""})))
    session, _rtl_path = _edit_session(tmp_path, reviewer)
    monkeypatch.setattr(rtl_editor, "check_syntax", lambda _path: (True, ""))
    editor = object.__new__(rtl_editor.RTLEditor)
    editor._session = session

    response = asyncio.run(
        editor._tool_apply_patch_set([{"start_line": 2, "end_line": 2, "new_code": "  logic a;"}])
    )
    result = json.loads(response.content[0]["text"])

    assert result["is_action_executed"] is True
    assert result["repair_journal_summary"][-1]["action_type"] == "apply_patch_set"


def test_tool_run_simulation_refreshes_trace_from_saved_log(tmp_path: Path) -> None:
    sim_output = json.dumps({"stdout": "Hint: Output 'out' has 1 mismatches. First mismatch occurred at time 5.", "stderr": ""})
    reviewer = _FakeReviewer((False, 1, sim_output))
    session, _rtl_path = _edit_session(tmp_path, reviewer)
    refreshed: list[str] = []

    def refresh_trace(*, sim_log_json: str) -> None:
        refreshed.append(sim_log_json)
        session.trace_report = {"fail_time": 5, "fail_outputs": []}

    session._refresh_trace = refresh_trace  # type: ignore[method-assign]
    editor = object.__new__(rtl_editor.RTLEditor)
    editor._session = session

    response = asyncio.run(editor._tool_run_simulation())
    result = json.loads(response.content[0]["text"])

    assert refreshed == [sim_output]
    assert "sim_output" not in result
    assert result["trace_summary"]["fail_time"] == 5


def test_tool_run_simulation_tolerates_missing_saved_log(tmp_path: Path) -> None:
    session, _rtl_path = _edit_session(tmp_path, _FakeReviewer((False, 1, "{}")))

    def run_simulation() -> dict[str, object]:
        return {
            "is_sim_pass": False,
            "sim_mismatch_cnt": 1,
            "sim_output_excerpt": "mismatch",
            "sim_output_path": str(tmp_path / "missing.json"),
        }

    session.run_simulation = run_simulation  # type: ignore[method-assign]
    editor = object.__new__(rtl_editor.RTLEditor)
    editor._session = session

    response = asyncio.run(editor._tool_run_simulation())
    result = json.loads(response.content[0]["text"])

    assert result["sim_mismatch_cnt"] == 1
    assert result["sim_output_excerpt"] == "mismatch"


class _CaptureDebuggerAgent:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def __call__(self, msg: object) -> None:
        text = msg.get_text_content()  # type: ignore[attr-defined]
        self.prompts.append(text or "")


def _prompt_editor(
    tmp_path: Path,
    *,
    enable_asserter: bool = False,
    enable_boolean_proofer: bool = False,
) -> tuple[rtl_editor.RTLEditor, _CaptureDebuggerAgent]:
    (tmp_path / "rtl.sv").write_text("module m(input clk, output out); assign out = clk; endmodule\n", encoding="utf-8")
    capture = _CaptureDebuggerAgent()
    editor = object.__new__(rtl_editor.RTLEditor)
    editor._cfg = SimpleNamespace()
    editor.sim_reviewer = _FakeReviewer((False, 1, "{}"))
    editor.max_trials = 0
    editor.enable_asserter = enable_asserter
    editor.enable_boolean_proofer = enable_boolean_proofer
    editor.kg_service = None
    editor.kg_hop_depth = 2
    editor._agent = capture
    editor._session = None
    editor.reset = lambda: setattr(editor, "_session", None)  # type: ignore[method-assign]
    return editor, capture


def test_spec_tb_prompt_contains_full_tb_without_stage1_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tb_text = "module tb;\n" + ("// visible input sequence\n" * 500) + "// TB_TAIL_SENTINEL\nendmodule\n"
    (tmp_path / "tb.sv").write_text(tb_text, encoding="utf-8")
    editor, capture = _prompt_editor(tmp_path)
    monkeypatch.setattr(rtl_editor, "build_trace_report", lambda **_kwargs: ({"fail_outputs": []}, []))

    asyncio.run(
        editor.chat(
            spec="ORIGINAL_SPEC_SENTINEL",
            output_dir_per_run=str(tmp_path),
            sim_failed_log="{}",
            sim_mismatch_cnt=1,
            contract_json='{"module_name": "m", "private": "STAGE1_METADATA_SENTINEL"}',
            behavior_source="spec_tb",
            max_trials=0,
        )
    )

    prompt = capture.prompts[0]
    assert "<original_module_spec>" in prompt
    assert "ORIGINAL_SPEC_SENTINEL" in prompt
    assert "TB_TAIL_SENTINEL" in prompt
    assert "<contract_json>" not in prompt
    assert "STAGE1_METADATA_SENTINEL" not in prompt
    assert "Architect contract" not in prompt


def test_contract_prompt_mode_remains_compatible(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "tb.sv").write_text("module tb;\nendmodule\n", encoding="utf-8")
    editor, capture = _prompt_editor(tmp_path)
    monkeypatch.setattr(rtl_editor, "build_trace_report", lambda **_kwargs: ({"fail_outputs": []}, []))

    asyncio.run(
        editor.chat(
            spec="background only",
            output_dir_per_run=str(tmp_path),
            sim_failed_log="{}",
            sim_mismatch_cnt=1,
            contract_json='{"module_name": "m", "marker": "CONTRACT_SENTINEL"}',
            max_trials=0,
        )
    )

    prompt = capture.prompts[0]
    assert "<contract_json>" in prompt
    assert "CONTRACT_SENTINEL" in prompt
    assert "SOURCE OF TRUTH" in prompt


def test_continue_prompt_repeats_original_spec_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "tb.sv").write_text("module tb;\nendmodule\n", encoding="utf-8")
    editor, capture = _prompt_editor(tmp_path)
    monkeypatch.setattr(rtl_editor, "build_trace_report", lambda **_kwargs: ({"fail_outputs": []}, []))

    asyncio.run(
        editor.chat(
            spec="ORIGINAL_SPEC_CONTINUE_SENTINEL",
            output_dir_per_run=str(tmp_path),
            sim_failed_log="{}",
            sim_mismatch_cnt=1,
            contract_json='{"module_name": "m"}',
            behavior_source="spec_tb",
            max_trials=1,
        )
    )

    assert len(capture.prompts) == 2
    assert "<original_module_spec>" in capture.prompts[1]
    assert "ORIGINAL_SPEC_CONTINUE_SENTINEL" in capture.prompts[1]


def test_spec_tb_helpers_receive_metadata_without_exposing_it_in_prompt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "tb.sv").write_text("module tb;\nendmodule\n", encoding="utf-8")
    editor, capture = _prompt_editor(tmp_path, enable_asserter=True, enable_boolean_proofer=True)
    received: dict[str, str] = {}
    metadata_json = '{"module_name": "m", "private": "STAGE1_METADATA_SENTINEL"}'
    monkeypatch.setattr(rtl_editor, "build_trace_report", lambda **_kwargs: ({"fail_outputs": []}, []))

    class _FakeProofer:
        def __init__(self, _cfg: object) -> None:
            pass

        async def prove(self, **kwargs: object) -> BooleanProoferResult:
            received["proofer"] = str(kwargs["contract_json"])
            return BooleanProoferResult(status="skip", summary="diagnostic proof skipped")

    class _FakeAsserter:
        def __init__(self, _cfg: object) -> None:
            pass

        async def analyze(self, **kwargs: object) -> AsserterResult:
            received["asserter"] = str(kwargs["contract_json"])
            return AsserterResult(status="skip", summary="diagnostic assertion skipped")

    monkeypatch.setattr(rtl_editor, "BooleanProofer", _FakeProofer)
    monkeypatch.setattr(rtl_editor, "Asserter", _FakeAsserter)

    asyncio.run(
        editor.chat(
            spec="original specification",
            output_dir_per_run=str(tmp_path),
            sim_failed_log="{}",
            sim_mismatch_cnt=1,
            contract_json=metadata_json,
            behavior_source="spec_tb",
            max_trials=0,
        )
    )

    assert received == {"proofer": metadata_json, "asserter": metadata_json}
    assert "STAGE1_METADATA_SENTINEL" not in capture.prompts[0]
    assert "non-authoritative diagnostic hint" in capture.prompts[0]
