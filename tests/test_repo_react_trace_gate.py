from __future__ import annotations

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from zerorepo.rtl_impl.debug_agent.bash_tools import CommandResult

from zerorepo.rtl_impl.repo_react.journal import RepoReActJournal
from zerorepo.rtl_impl.repo_react.compact import build_llm_compact_memory, parse_llm_compact_json
from zerorepo.rtl_impl.repo_react.context import DebugContextRouter
from zerorepo.rtl_impl.repo_react.prompt import _compact_long_term_memories, build_compact_prompt, build_continue_prompt, build_initial_prompt
from zerorepo.rtl_impl.repo_react.runner import RepoReActRunner
import zerorepo.rtl_impl.repo_react.runner as runner_module
from zerorepo.rtl_impl.repo_react.schemas import DebugContextPack, RepoReActInput, SimSnapshot, SystemTriage
import zerorepo.rtl_impl.repo_react.tools as tools_module
from zerorepo.rtl_impl.repo_react.tools import RepoReActTools, RepoReActToolState, _metric_delta, _parse_sim_metrics
from zerorepo.rtl_impl.rtl_memory.schemas import RTLMemoryHeader
from zerorepo.rtl_impl.rtl_memory.selector import build_selector_prompt
from zerorepo.rtl_impl.rtl_memory.store import RTLMemoryStore


class _CaptureAgent:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def __call__(self, msg: object) -> object:
        self.prompts.append(msg.get_text_content() or "")  # type: ignore[attr-defined]
        return SimpleNamespace(get_text_content=lambda: "")


class _FakeKG:
    def __init__(self, result: object) -> None:
        self.result = result
        self.calls: list[tuple[object, dict[str, object], int]] = []

    def is_enabled(self) -> bool:
        return True

    def query(self, template: object, params: dict[str, object], limit: int = 100) -> object:
        self.calls.append((template, params, limit))
        return self.result


def _make_tools(tmp_path: Path, *, repair_mode: str = "functional") -> RepoReActTools:
    workdir = tmp_path / "debug" / "m"
    workdir.mkdir(parents=True)
    rtl_path = workdir / "rtl.sv"
    rtl_path.write_text("module m(input clk, output y);\nassign y = clk;\nendmodule\n", encoding="utf-8")
    inp = RepoReActInput(
        module_name="m",
        repair_mode=repair_mode,  # type: ignore[arg-type]
        workspace_root=tmp_path,
        debug_workdir=workdir,
        rtl_path=rtl_path,
        merged_file=tmp_path / "merged" / "m.v",
        sim_failed_log="",
        initial_mismatch_count=1,
    )
    state = RepoReActToolState(
        input=inp,
        sim_reviewer=SimpleNamespace(),
        journal=RepoReActJournal(tmp_path / "repo_react" / "m"),
    )
    state.observed_rtl = True
    state.observed_trace_or_sim = True
    state.observed_tb_or_spec_or_kg = True
    state.observed_spec_or_stage = True
    return RepoReActTools(state)


def _make_repo_tools(tmp_path: Path) -> RepoReActTools:
    workdir = tmp_path / "debug_system" / "top"
    rtl_root = workdir / "generated"
    rtl_root.mkdir(parents=True)
    top_path = rtl_root / "top.v"
    child_path = rtl_root / "child.v"
    top_path.write_text("module top(output y);\nassign y = 1'b0;\nendmodule\n", encoding="utf-8")
    child_path.write_text("module child(output y);\nassign y = 1'b0;\nendmodule\n", encoding="utf-8")
    verify_dir = workdir / "verify_test"
    verify_dir.mkdir()
    verify_script = verify_dir / "top_verify.py"
    verify_script.write_text("print('hidden verifier')\n", encoding="utf-8")
    (workdir / "tb.sv").write_text("module tb; endmodule\n", encoding="utf-8")
    inp = RepoReActInput(
        module_name="top",
        top_module="top",
        repair_scope="repo",
        repair_mode="functional",
        workspace_root=tmp_path,
        debug_workdir=workdir,
        rtl_path=top_path,
        merged_file=tmp_path / "merged" / "top.v",
        rtl_root=rtl_root,
        verify_dir=verify_dir,
        verify_script=verify_script,
        sim_failed_log="",
        initial_mismatch_count=0,
    )
    sim_log = CommandResult(stdout="Summary:\n  top_system: PASS\n", stderr="").model_dump_json()
    state = RepoReActToolState(
        input=inp,
        sim_reviewer=SimpleNamespace(review=lambda: (True, 0, sim_log)),
        journal=RepoReActJournal(tmp_path / "repo_react" / "top"),
    )
    state.observed_rtl = True
    state.observed_trace_or_sim = True
    state.observed_tb_or_spec_or_kg = True
    state.observed_spec_or_stage = True
    return RepoReActTools(state)


def _make_runner(tmp_path: Path, *, repair_mode: str = "functional") -> tuple[RepoReActRunner, RepoReActTools]:
    tools = _make_tools(tmp_path, repair_mode=repair_mode)
    tools.state.observed_real_divergence = repair_mode == "functional"
    runner = RepoReActRunner.__new__(RepoReActRunner)
    runner.cfg = SimpleNamespace()
    runner.sim_reviewer = SimpleNamespace()
    runner.kg_service = None
    runner.max_steps = 30
    runner.logger = None
    runner._state = tools.state
    runner._tools = tools
    runner._context_router = DebugContextRouter(cfg=None, tools=tools)
    runner._agent = _CaptureAgent()
    runner._latest_context_pack = {}
    runner._last_compacted_action_calls = 0
    runner._last_checkpoint_action_calls = 0
    runner._tool_result_chars_since_compact = 0
    runner._tool_result_chars_since_light = 0
    runner._readonly_calls_since_action = 0
    runner._readonly_calls_since_light = 0
    runner._route_calls_since_action = 0
    runner._light_consolidations_since_checkpoint = 0
    runner._checkpoint_count = 0
    runner._max_readonly_calls_since_action = 16
    runner._router_first_enabled = True
    return runner, tools


def test_functional_apply_patch_requires_real_divergence(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")

    result = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ~clk;"}],
        reason="try change",
        expected_effect="change output",
        verify=False,
    )

    assert result["status"] == "kept_unverified"
    assert tools.state.action_calls == 1


def test_syntax_apply_patch_does_not_require_real_divergence(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="syntax")

    result = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = clk;"}],
        reason="syntax-only rewrite",
        expected_effect="lint remains clean",
        verify=False,
    )

    assert result["status"] == "kept_unverified"


def test_repo_scope_run_check_top_sim_uses_system_reviewer(tmp_path: Path) -> None:
    tools = _make_repo_tools(tmp_path)

    result = tools.run_check(mode="top_sim")

    assert result["status"] == "ok"
    assert result["mode"] == "top_sim"
    assert result["is_pass"] is True


def test_repo_scope_apply_patch_can_edit_generated_rtl(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_repo_tools(tmp_path)

    def fake_check_syntax(_path: str, top_module: str | None = None) -> tuple[bool, str]:
        assert top_module == "top"
        return True, CommandResult(stdout="", stderr="").model_dump_json()

    monkeypatch.setattr(tools_module, "check_syntax", fake_check_syntax)
    child_path = tools.state.input.rtl_root / "child.v"  # type: ignore[operator]
    result = tools.apply_patch(
        patches=[{"path": str(child_path), "start_line": 2, "end_line": 2, "new_text": "assign y = 1'b1;"}],
        reason="fix child behavior seen from top sim",
        expected_effect="top sim passes",
    )

    assert result["status"] == "pass"
    assert "assign y = 1'b1;" in child_path.read_text(encoding="utf-8")


def test_repo_scope_apply_patch_rejects_verify_script(tmp_path: Path) -> None:
    tools = _make_repo_tools(tmp_path)
    verify_script = tools.state.input.verify_script

    result = tools.apply_patch(
        patches=[{"path": str(verify_script), "start_line": 1, "end_line": 1, "new_text": "print('bad')"}],
        reason="try to edit verifier",
        expected_effect="should be blocked",
        verify=False,
    )

    assert result["status"] == "rejected"
    assert "generated RTL" in result["reason"]


def test_repo_scope_apply_patch_rolls_back_failed_top_sim(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_repo_tools(tmp_path)
    fail_log = CommandResult(stdout="Summary:\n  top_system: FAIL\n", stderr="compile error").model_dump_json()
    tools.state.sim_reviewer = SimpleNamespace(review=lambda: (False, 0, fail_log))

    def fake_check_syntax(_path: str, top_module: str | None = None) -> tuple[bool, str]:
        return True, CommandResult(stdout="", stderr="").model_dump_json()

    monkeypatch.setattr(tools_module, "check_syntax", fake_check_syntax)
    child_path = tools.state.input.rtl_root / "child.v"  # type: ignore[operator]
    before = child_path.read_text(encoding="utf-8")

    result = tools.apply_patch(
        patches=[{"path": str(child_path), "start_line": 2, "end_line": 2, "new_text": "assign y = 1'b1;"}],
        reason="bad repo patch",
        expected_effect="top sim should fail",
    )

    assert result["status"] == "rollback"
    assert result["rollback_reason"] == "top_sim_failed_without_mismatch_count"
    assert child_path.read_text(encoding="utf-8") == before


def test_repo_scope_apply_patch_can_edit_multiple_rtl_files(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_repo_tools(tmp_path)
    top_path = tools.state.input.rtl_path
    child_path = tools.state.input.rtl_root / "child.v"  # type: ignore[operator]

    def fake_check_syntax(path: str, top_module: str | None = None) -> tuple[bool, str]:
        assert path == str(top_path)
        assert top_module == "top"
        return True, CommandResult(stdout="", stderr="").model_dump_json()

    monkeypatch.setattr(tools_module, "check_syntax", fake_check_syntax)

    result = tools.apply_patch(
        patches=[
            {"path": str(top_path), "start_line": 2, "end_line": 2, "new_text": "assign y = 1'b1;"},
            {"path": str(child_path), "start_line": 2, "end_line": 2, "new_text": "assign y = 1'b1;"},
        ],
        reason="coherent top and child repair",
        expected_effect="top sim passes",
    )

    assert result["status"] == "pass"
    assert tools.state.action_calls == 1
    assert "assign y = 1'b1;" in top_path.read_text(encoding="utf-8")
    assert "assign y = 1'b1;" in child_path.read_text(encoding="utf-8")
    rows = tools._read_jsonl("patch_journal.jsonl")
    assert len(rows[-1]["target"]["files"]) == 2


def test_multi_file_lint_fail_rolls_back_all_files(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_repo_tools(tmp_path)
    top_path = tools.state.input.rtl_path
    child_path = tools.state.input.rtl_root / "child.v"  # type: ignore[operator]
    before_top = top_path.read_text(encoding="utf-8")
    before_child = child_path.read_text(encoding="utf-8")

    def fake_check_syntax(_path: str, top_module: str | None = None) -> tuple[bool, str]:
        del top_module
        return False, "lint failed"

    monkeypatch.setattr(tools_module, "check_syntax", fake_check_syntax)

    result = tools.apply_patch(
        patches=[
            {"path": str(top_path), "start_line": 2, "end_line": 2, "new_text": "assign y = ;"},
            {"path": str(child_path), "start_line": 2, "end_line": 2, "new_text": "assign y = 1'b1;"},
        ],
        reason="broken multi-file patch",
        expected_effect="lint catches syntax",
    )

    assert result["status"] == "rollback"
    assert result["rollback_reason"] == "lint_failed"
    assert top_path.read_text(encoding="utf-8") == before_top
    assert child_path.read_text(encoding="utf-8") == before_child
    assert tools.state.action_calls == 1


def test_multi_file_sim_regression_rolls_back_all_files(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_repo_tools(tmp_path)
    top_path = tools.state.input.rtl_path
    child_path = tools.state.input.rtl_root / "child.v"  # type: ignore[operator]
    before_top = top_path.read_text(encoding="utf-8")
    before_child = child_path.read_text(encoding="utf-8")
    before_log = CommandResult(stdout="Mismatches: 1 in 4 samples\n", stderr="").model_dump_json()
    after_log = CommandResult(stdout="Mismatches: 2 in 4 samples\n", stderr="").model_dump_json()
    tools.state.last_sim = SimSnapshot(is_pass=False, mismatch_count=1, first_fail_time=10, sim_output_path="")
    tools.state.last_sim_output = before_log
    tools.state.sim_reviewer = SimpleNamespace(review=lambda: (False, 2, after_log))
    tools._refresh_trace = lambda _sim_output: {}  # type: ignore[method-assign]

    def fake_check_syntax(_path: str, top_module: str | None = None) -> tuple[bool, str]:
        del top_module
        return True, CommandResult(stdout="", stderr="").model_dump_json()

    monkeypatch.setattr(tools_module, "check_syntax", fake_check_syntax)
    monkeypatch.setattr(tools, "_llm_patch_acceptance_decision", lambda _payload: {"decision": "rollback"})

    result = tools.apply_patch(
        patches=[
            {"path": str(top_path), "start_line": 2, "end_line": 2, "new_text": "assign y = 1'b1;"},
            {"path": str(child_path), "start_line": 2, "end_line": 2, "new_text": "assign y = 1'b1;"},
        ],
        reason="multi-file regression",
        expected_effect="should rollback as a unit",
    )

    assert result["status"] == "rollback"
    assert result["rollback_reason"] == "mismatch_count_regressed"
    assert top_path.read_text(encoding="utf-8") == before_top
    assert child_path.read_text(encoding="utf-8") == before_child


def test_repo_scope_defaults_to_larger_readonly_budget(tmp_path: Path) -> None:
    tools = _make_repo_tools(tmp_path)
    runner = RepoReActRunner.__new__(RepoReActRunner)
    runner._readonly_budget_from_env = False
    runner._max_readonly_calls_since_action = 16

    runner._configure_scope_defaults(tools.state.input)

    assert runner._max_readonly_calls_since_action == 32


def test_env_readonly_budget_is_respected_for_repo_scope(tmp_path: Path) -> None:
    tools = _make_repo_tools(tmp_path)
    runner = RepoReActRunner.__new__(RepoReActRunner)
    runner._readonly_budget_from_env = True
    runner._max_readonly_calls_since_action = 20

    runner._configure_scope_defaults(tools.state.input)

    assert runner._max_readonly_calls_since_action == 20


def test_apply_patch_allows_more_than_two_ranges(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="syntax")

    result = tools.apply_patch(
        patches=[
            {"path": "rtl.sv", "start_line": 1, "end_line": 1, "new_text": "module m(input clk, output y);"},
            {"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ~clk;"},
            {"path": "rtl.sv", "start_line": 3, "end_line": 3, "new_text": "endmodule"},
        ],
        reason="multi-range syntax rewrite",
        expected_effect="all ranges apply",
        verify=False,
    )

    assert result["status"] == "kept_unverified"
    assert "assign y = ~clk;" in tools.state.input.rtl_path.read_text(encoding="utf-8")


def test_apply_patch_rejects_overlapping_ranges_without_consuming_budget(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="syntax")

    result = tools.apply_patch(
        patches=[
            {"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ~clk;"},
            {"path": "rtl.sv", "start_line": 2, "end_line": 3, "new_text": "assign y = clk;\nendmodule"},
        ],
        reason="overlap should be rejected",
        expected_effect="no write",
        verify=False,
    )

    assert result["status"] == "rejected"
    assert "Overlapping patch ranges" in result["reason"]
    assert tools.state.action_calls == 0


def test_invalid_patch_rejection_does_not_consume_action_budget(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="syntax")

    result = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 99, "end_line": 99, "new_text": "assign y = clk;"}],
        reason="bad range",
        expected_effect="no write",
        verify=False,
    )

    assert result["status"] == "rejected"
    assert tools.state.action_calls == 0


def test_functional_apply_patch_requires_spec_or_stage_context(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    tools.state.observed_real_divergence = True
    tools.state.observed_spec_or_stage = False

    result = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ~clk;"}],
        reason="try waveform-only change",
        expected_effect="change output",
        verify=False,
    )

    assert result["status"] == "kept_unverified"
    assert tools.state.action_calls == 1


def test_apply_patch_enforces_action_budget(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="syntax")
    tools.state.input.max_steps = 1
    tools.state.action_calls = 1

    result = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ~clk;"}],
        reason="over budget",
        expected_effect="should be blocked",
        verify=False,
    )

    assert result["status"] == "rejected"
    assert "max_steps=1" in result["reason"]


def test_parse_sim_metrics_extracts_total_and_per_signal() -> None:
    sim_log = CommandResult(
        cmd=["sim"],
        returncode=1,
        stdout=(
            "Hint: Output 'STATUS_REG' has 471 mismatches. First mismatch occurred at time 485.\n"
            "Hint: Output 'cmd_out' has 644 mismatches. First mismatch occurred at time 1155.\n"
            "Mismatches: 2473 in 5213 samples\n"
        ),
        stderr="",
    ).model_dump_json()

    metrics = _parse_sim_metrics(sim_log)

    assert metrics["total_samples_mismatch"] == 2473
    assert metrics["samples"] == 5213
    assert metrics["per_signal"]["STATUS_REG"] == {"count": 471, "first_time": 485}
    assert metrics["per_signal"]["cmd_out"] == {"count": 644, "first_time": 1155}


def test_metric_delta_treats_missing_hint_as_zero_mismatches() -> None:
    before = {
        "total_samples_mismatch": 2207,
        "samples": 5213,
        "per_signal": {
            "STATUS_REG": {"count": 471, "first_time": 485},
            "NORMAL_INT_REG": {"count": 1187, "first_time": 5},
        },
    }
    after = {
        "total_samples_mismatch": 4246,
        "samples": 5213,
        "per_signal": {
            "NORMAL_INT_REG": {"count": 4, "first_time": 10485},
        },
    }

    delta = _metric_delta(before, after)

    assert delta["per_signal"]["STATUS_REG"]["after"] == 0
    assert delta["per_signal"]["STATUS_REG"]["direction"] == "improved"
    assert delta["per_signal"]["NORMAL_INT_REG"]["direction"] == "improved"


def test_improved_patch_entry_is_distilled_to_long_term_memory(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    tools.state.last_trace_summary = {
        "top_diagnosis": "y is late",
        "first_failure": {"signal": "y", "time": 10},
    }
    tools.state.last_divergence_summary = {
        "status": "ok",
        "sampling_mode": "stable",
        "first_divergence": {"signal": "y", "time": 10, "classification": "late"},
    }

    tools._record_patch_entry(
        {
            "step": 1,
            "action_type": "apply_patch",
            "target": {"path": "rtl.sv", "start_line": 2, "end_line": 2},
            "changed_signals": ["y"],
            "effect": "improved",
            "hypothesis": "hold y for one cycle",
            "lesson": "Patch improved mismatch count or first fail time; continue from this direction.",
            "patch_summary": "assign y = delayed_clk;",
            "evidence": {
                "latest_trace_summary": tools.state.last_trace_summary,
                "last_divergence_summary": tools.state.last_divergence_summary,
            },
            "before": {"mismatch_count": 10, "first_fail_time": 10},
            "after": {"mismatch_count": 5, "first_fail_time": 20},
            "before_metrics": {
                "total_samples_mismatch": 10,
                "samples": 20,
                "per_signal": {"y": {"count": 10, "first_time": 10}},
            },
            "after_metrics": {
                "total_samples_mismatch": 5,
                "samples": 20,
                "per_signal": {"y": {"count": 5, "first_time": 20}},
            },
            "metric_delta": {"total_samples_mismatch": "10 -> 5", "per_signal": {}},
            "result": {"status": "improved"},
        }
    )

    memory_files = list((tmp_path / "rtl_memory" / "cases").glob("debug_m_y_improved_1.md"))
    assert len(memory_files) == 1
    assert "assign y = delayed_clk;" in memory_files[0].read_text(encoding="utf-8")
    assert "debug_m_y_improved_1" in (tmp_path / "rtl_memory" / "MEMORY.md").read_text(encoding="utf-8")


def test_promising_mixed_signal_delta_is_kept_despite_total_mismatch_regression(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    tools.state.observed_real_divergence = True

    before_log = CommandResult(
        cmd=["sim"],
        returncode=1,
        stdout=(
            "Hint: Output 'ERR_INT_REG' has 98 mismatches. First mismatch occurred at time 755.\n"
            "Hint: Output 'NORMAL_INT_REG' has 1187 mismatches. First mismatch occurred at time 5.\n"
            "Hint: Output 'RESP_1_REG' has 202 mismatches. First mismatch occurred at time 1165.\n"
            "Hint: Output 'STATUS_REG' has 471 mismatches. First mismatch occurred at time 485.\n"
            "Hint: Output 'ack_out' has 672 mismatches. First mismatch occurred at time 1105.\n"
            "Hint: Output 'errors_cmd_out' has 644 mismatches. First mismatch occurred at time 485.\n"
            "Hint: Output 'errors_settings' has 636 mismatches. First mismatch occurred at time 485.\n"
            "Mismatches: 2207 in 5213 samples\n"
        ),
        stderr="",
    ).model_dump_json()
    after_log = CommandResult(
        cmd=["sim"],
        returncode=1,
        stdout=(
            "Hint: Output 'ERR_INT_REG' has 6 mismatches. First mismatch occurred at time 10485.\n"
            "Hint: Output 'NORMAL_INT_REG' has 4 mismatches. First mismatch occurred at time 10485.\n"
            "Hint: Output 'RESP_1_REG' has 1087 mismatches. First mismatch occurred at time 1165.\n"
            "Hint: Output 'errors_cmd_out' has 4378 mismatches. First mismatch occurred at time 485.\n"
            "Hint: Output 'errors_settings' has 4275 mismatches. First mismatch occurred at time 485.\n"
            "Mismatches: 4378 in 5213 samples\n"
        ),
        stderr="",
    ).model_dump_json()
    tools.state.last_sim = SimSnapshot(is_pass=False, mismatch_count=2207, first_fail_time=5, sim_output_path="")
    tools.state.last_sim_output = before_log
    tools.state.sim_reviewer = SimpleNamespace(review=lambda: (False, 4378, after_log))
    tools._refresh_trace = lambda _sim_output: {}  # type: ignore[method-assign]

    def fake_check_syntax(_path: str, top_module: str | None = None) -> tuple[bool, str]:
        return True, CommandResult(cmd=["verilator"], returncode=0, stdout="", stderr="").model_dump_json()

    monkeypatch.setattr(tools_module, "check_syntax", fake_check_syntax)

    result = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ~clk;"}],
        reason="broad timing conversion improves control signals",
        expected_effect="NORMAL_INT_REG and ERR_INT_REG should improve before data path cleanup",
    )

    assert result["status"] == "improved"
    assert result["acceptance_reason"] == "promising_mixed_signal_delta"
    assert result["mismatch_count"] == 4378
    assert result["mixed_signal_delta"]["improvement_sum"] > result["mixed_signal_delta"]["regression_sum"]
    assert "assign y = ~clk;" in tools.state.input.rtl_path.read_text(encoding="utf-8")
    assert tools.state.last_sim.mismatch_count == 4378


def test_llm_acceptance_can_keep_functional_regression(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    tools.state.observed_real_divergence = True
    before_log = CommandResult(
        cmd=["sim"],
        returncode=1,
        stdout="Hint: Output 'int_busy' has 784 mismatches. First mismatch occurred at time 80.\nMismatches: 10042 in 10591\n",
        stderr="",
    ).model_dump_json()
    after_log = CommandResult(
        cmd=["sim"],
        returncode=1,
        stdout="Hint: Output 'int_busy' has 1846 mismatches. First mismatch occurred at time 1020.\nMismatches: 10040 in 10591\n",
        stderr="",
    ).model_dump_json()
    tools.state.last_sim = SimSnapshot(is_pass=False, mismatch_count=41298, first_fail_time=80, sim_output_path="")
    tools.state.last_sim_output = before_log
    tools.state.sim_reviewer = SimpleNamespace(review=lambda: (False, 42360, after_log))
    tools._refresh_trace = lambda _sim_output: {}  # type: ignore[method-assign]

    def fake_check_syntax(_path: str, top_module: str | None = None) -> tuple[bool, str]:
        return True, CommandResult(cmd=["verilator"], returncode=0, stdout="", stderr="").model_dump_json()

    def fake_judge(_payload: dict[str, object]) -> dict[str, object]:
        return {"decision": "keep", "confidence": 0.83, "reason": "first failure moved much later; fix clear next"}

    monkeypatch.setattr(tools_module, "check_syntax", fake_check_syntax)
    monkeypatch.setattr(tools, "_llm_patch_acceptance_decision", fake_judge)

    result = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ~clk;"}],
        reason="make int_busy sticky after new_cmd",
        expected_effect="moves int_busy failure later but needs clear condition",
    )

    assert result["status"] == "improved"
    assert result["script_rollback_recommendation"] == "mismatch_count_regressed"
    assert result["acceptance_decision"]["decision"] == "keep"
    assert "assign y = ~clk;" in tools.state.input.rtl_path.read_text(encoding="utf-8")
    assert tools.state.last_sim.mismatch_count == 42360


def test_llm_acceptance_can_confirm_functional_rollback(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    tools.state.observed_real_divergence = True
    before_log = CommandResult(
        cmd=["sim"],
        returncode=1,
        stdout="Hint: Output 'int_busy' has 784 mismatches. First mismatch occurred at time 80.\nMismatches: 10042 in 10591\n",
        stderr="",
    ).model_dump_json()
    after_log = CommandResult(
        cmd=["sim"],
        returncode=1,
        stdout="Hint: Output 'int_busy' has 1846 mismatches. First mismatch occurred at time 80.\nMismatches: 11000 in 10591\n",
        stderr="",
    ).model_dump_json()
    tools.state.last_sim = SimSnapshot(is_pass=False, mismatch_count=10042, first_fail_time=80, sim_output_path="")
    tools.state.last_sim_output = before_log
    tools.state.sim_reviewer = SimpleNamespace(review=lambda: (False, 11000, after_log))
    tools._refresh_trace = lambda _sim_output: {}  # type: ignore[method-assign]

    def fake_check_syntax(_path: str, top_module: str | None = None) -> tuple[bool, str]:
        return True, CommandResult(cmd=["verilator"], returncode=0, stdout="", stderr="").model_dump_json()

    def fake_judge(_payload: dict[str, object]) -> dict[str, object]:
        return {"decision": "rollback", "confidence": 0.9, "reason": "target signal worsened without timing progress"}

    monkeypatch.setattr(tools_module, "check_syntax", fake_check_syntax)
    monkeypatch.setattr(tools, "_llm_patch_acceptance_decision", fake_judge)

    result = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ~clk;"}],
        reason="bad int_busy patch",
        expected_effect="should be judged unsafe",
    )

    assert result["status"] == "rollback"
    assert result["rollback_reason"] == "mismatch_count_regressed"
    assert result["acceptance_decision"]["decision"] == "rollback"
    assert "assign y = clk;" in tools.state.input.rtl_path.read_text(encoding="utf-8")


def test_llm_acceptance_can_keep_first_fail_time_regression(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    before_log = CommandResult(
        stdout="Hint: Output 'y' has 10 mismatches. First mismatch occurred at time 80.\nMismatches: 10 in 20 samples\n",
        stderr="",
    ).model_dump_json()
    after_log = CommandResult(
        stdout="Hint: Output 'y' has 10 mismatches. First mismatch occurred at time 40.\nMismatches: 10 in 20 samples\n",
        stderr="",
    ).model_dump_json()
    tools.state.last_sim = SimSnapshot(is_pass=False, mismatch_count=10, first_fail_time=80, sim_output_path="")
    tools.state.last_sim_output = before_log
    tools.state.sim_reviewer = SimpleNamespace(review=lambda: (False, 10, after_log))
    tools._refresh_trace = lambda _sim_output: {}  # type: ignore[method-assign]

    def fake_check_syntax(_path: str, top_module: str | None = None) -> tuple[bool, str]:
        del top_module
        return True, CommandResult(stdout="", stderr="").model_dump_json()

    def fake_judge(payload: dict[str, object]) -> dict[str, object]:
        assert payload["script_rollback_recommendation"] == "first_fail_time_regressed"
        return {"decision": "keep", "confidence": 0.8, "reason": "earlier metric edge is acceptable; value path is fixed"}

    monkeypatch.setattr(tools_module, "check_syntax", fake_check_syntax)
    monkeypatch.setattr(tools, "_llm_patch_acceptance_decision", fake_judge)

    result = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ~clk;"}],
        reason="fix value path but expose earlier checker edge",
        expected_effect="keep if judge agrees",
    )

    assert result["status"] == "improved"
    assert result["script_rollback_recommendation"] == "first_fail_time_regressed"
    assert result["acceptance_decision"]["decision"] == "keep"
    assert "assign y = ~clk;" in tools.state.input.rtl_path.read_text(encoding="utf-8")


def test_consecutive_neutral_patches_are_judged_before_rollback(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    before_log = CommandResult(stdout="Mismatches: 1 in 4 samples\n", stderr="").model_dump_json()
    after_log = CommandResult(stdout="Mismatches: 1 in 4 samples\n", stderr="").model_dump_json()
    tools.state.last_sim = SimSnapshot(is_pass=False, mismatch_count=1, first_fail_time=10, sim_output_path="")
    tools.state.last_sim_output = before_log
    tools.state.sim_reviewer = SimpleNamespace(review=lambda: (False, 1, after_log))
    tools._refresh_trace = lambda _sim_output: {}  # type: ignore[method-assign]

    def fake_check_syntax(_path: str, top_module: str | None = None) -> tuple[bool, str]:
        del top_module
        return True, CommandResult(stdout="", stderr="").model_dump_json()

    monkeypatch.setattr(tools_module, "check_syntax", fake_check_syntax)
    monkeypatch.setattr(
        tools,
        "_llm_patch_acceptance_decision",
        lambda payload: {"decision": "keep", "confidence": 0.75, "reason": str(payload["script_rollback_recommendation"])},
    )

    results = []
    for expr in ["~clk", "clk", "~clk"]:
        results.append(
            tools.apply_patch(
                patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": f"assign y = {expr};"}],
                reason="neutral stepping stone",
                expected_effect="no aggregate metric change",
            )
        )

    assert [result["status"] for result in results] == ["neutral", "neutral", "improved"]
    assert all(result.get("rollback_reason") != "too_many_neutral_patches" for result in results)
    assert results[-1]["script_rollback_recommendation"] == "too_many_neutral_patches"
    assert results[-1]["acceptance_decision"]["decision"] == "keep"
    assert tools.state.neutral_kept == 0
    assert "assign y = ~clk;" in tools.state.input.rtl_path.read_text(encoding="utf-8")


def test_consecutive_neutral_patches_can_be_rolled_back_by_judge(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    before_log = CommandResult(stdout="Mismatches: 1 in 4 samples\n", stderr="").model_dump_json()
    after_log = CommandResult(stdout="Mismatches: 1 in 4 samples\n", stderr="").model_dump_json()
    tools.state.last_sim = SimSnapshot(is_pass=False, mismatch_count=1, first_fail_time=10, sim_output_path="")
    tools.state.last_sim_output = before_log
    tools.state.sim_reviewer = SimpleNamespace(review=lambda: (False, 1, after_log))
    tools.state.neutral_kept = 2
    tools._refresh_trace = lambda _sim_output: {}  # type: ignore[method-assign]

    def fake_check_syntax(_path: str, top_module: str | None = None) -> tuple[bool, str]:
        del top_module
        return True, CommandResult(stdout="", stderr="").model_dump_json()

    def fake_judge(payload: dict[str, object]) -> dict[str, object]:
        assert payload["script_rollback_recommendation"] == "too_many_neutral_patches"
        return {"decision": "rollback", "confidence": 0.9, "reason": "neutral streak has no causal progress"}

    monkeypatch.setattr(tools_module, "check_syntax", fake_check_syntax)
    monkeypatch.setattr(tools, "_llm_patch_acceptance_decision", fake_judge)

    result = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ~clk;"}],
        reason="third neutral attempt",
        expected_effect="judge may rollback",
    )

    assert result["status"] == "rollback"
    assert result["rollback_reason"] == "too_many_neutral_patches"
    assert result["acceptance_decision"]["decision"] == "rollback"
    assert "assign y = clk;" in tools.state.input.rtl_path.read_text(encoding="utf-8")


def test_light_consolidation_triggers_after_8_readonly_calls(tmp_path: Path) -> None:
    runner, _tools = _make_runner(tmp_path)
    runner._readonly_calls_since_light = 8

    assert runner._compact_decision() == "light"


def test_light_consolidation_triggers_after_route_debug_context(tmp_path: Path) -> None:
    runner, _tools = _make_runner(tmp_path)
    runner._route_calls_since_action = 1

    assert runner._compact_decision() == "light"


def test_light_consolidation_does_not_clear_agent_memory(tmp_path: Path) -> None:
    runner, _tools = _make_runner(tmp_path)
    runner._readonly_calls_since_light = 8

    assert runner._compact_decision() == "light"
    assert runner._checkpoint_count == 0
    assert runner._last_checkpoint_action_calls == 0


def test_checkpoint_requires_action_calls_positive(tmp_path: Path) -> None:
    runner, _tools = _make_runner(tmp_path)
    runner._tool_result_chars_since_compact = 96_000
    runner._tool_result_chars_since_light = 96_000

    assert runner._compact_decision() == "light"


def test_checkpoint_triggers_after_three_writes(tmp_path: Path) -> None:
    runner, tools = _make_runner(tmp_path)
    tools.state.action_calls = 3
    runner._last_checkpoint_action_calls = 0

    assert runner._compact_decision() == "checkpoint"


def test_checkpoint_triggers_after_96k_tool_chars(tmp_path: Path) -> None:
    runner, tools = _make_runner(tmp_path)
    tools.state.action_calls = 1
    runner._tool_result_chars_since_compact = 96_000

    assert runner._compact_decision() == "checkpoint"


def test_checkpoint_not_triggered_by_64k_before_first_patch(tmp_path: Path) -> None:
    runner, _tools = _make_runner(tmp_path)
    runner._tool_result_chars_since_compact = 64_000
    runner._tool_result_chars_since_light = 64_000

    assert runner._compact_decision() == "light"


def test_deep_compact_triggers_after_two_checkpoints(tmp_path: Path) -> None:
    runner, tools = _make_runner(tmp_path)
    tools.state.action_calls = 1
    runner._checkpoint_count = 2

    assert runner._compact_decision() == "deep"


def test_deep_compact_keeps_only_high_priority_working_set() -> None:
    context_pack = {
        "task_frame": {"current_target": {"signal": "out"}},
        "timing_evidence": {"signal": "out", "time": 7},
        "active_working_set": {
            "current_failure": {"signal": "out", "time": 7},
            "active_hypotheses": [
                {"id": f"hyp_{idx}", "text": f"h{idx}"}
                for idx in range(5)
            ],
            "pinned_evidence": [
                {"evidence_id": f"ev_{idx}", "summary": f"e{idx}"}
                for idx in range(5)
            ],
            "waveform_facts": [{"signal": "out", "time": idx} for idx in range(5)],
        },
        "evidence_pack": [{"evidence_id": "ev_full", "summary": "ordinary evidence"}],
        "causal_memory": {"repair_ledger_summary": [{"step": idx} for idx in range(6)]},
    }

    prompt = build_compact_prompt(context_pack, mode="deep")
    payload = prompt.split("<debug_context_pack_summary_json>\n", 1)[1].split("\n</debug_context_pack_summary_json>", 1)[0]
    obj = json.loads(payload)

    assert obj["evidence_pack"] == []
    assert len(obj["active_working_set"]["active_hypotheses"]) == 2
    assert len(obj["active_working_set"]["pinned_evidence"]) == 3
    assert obj["active_working_set"]["current_failure"]["signal"] == "out"


def test_compact_prompt_can_include_llm_compact_memory() -> None:
    context_pack = {
        "pack_path": "/tmp/pack.json",
        "task_frame": {"current_target": {"signal": "out"}},
    }
    llm_memory = {
        "schema": "repo_react_llm_compact.v1",
        "current_state": {"failure": "out mismatch"},
        "reasoning_trace": [{"observation": "read RTL", "inference": "bad hold", "decision": "patch"}],
        "hypotheses": [],
        "patch_lessons": [],
        "open_questions": [],
        "next_action": {"recommendation": "patch", "why": "evidence is sufficient"},
        "do_not_repeat": [],
    }

    prompt = build_compact_prompt(context_pack, mode="checkpoint", llm_compact_memory=llm_memory)

    assert "<llm_compact_memory_json>" in prompt
    assert "repo_react_llm_compact.v1" in prompt
    assert "debug_context_pack_summary_json" in prompt


def test_readonly_tool_writes_clipped_decision_trace(tmp_path: Path) -> None:
    runner, tools = _make_runner(tmp_path)
    long_text = "A" * 5000

    runner._tool_response(
        "read_context",
        {"status": "ok", "kind": "file", "path": str(tools.state.input.rtl_path), "content": long_text},
        trace_meta={
            "intent": {"purpose": "inspect current RTL", "question": "why is y wrong?"},
            "args": {"kind": "file", "path": str(tools.state.input.rtl_path)},
        },
    )

    rows = [
        json.loads(line)
        for line in (tools.state.journal.root / "decision_trace.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    row = rows[-1]
    assert row["tool_name"] == "read_context"
    assert row["tool_kind"] == "read"
    assert row["intent"]["purpose"] == "inspect current RTL"
    assert row["observation_summary"]["content_chars"] == 5000
    assert len(json.dumps(row, ensure_ascii=False)) < 2500
    assert long_text not in json.dumps(row, ensure_ascii=False)


def test_action_tool_decision_trace_records_reason_and_effect(tmp_path: Path) -> None:
    runner, tools = _make_runner(tmp_path, repair_mode="syntax")

    runner._tool_response(
        "apply_patch",
        {"status": "kept_unverified", "effect": "neutral", "target": {"path": str(tools.state.input.rtl_path)}},
        trace_meta={
            "intent": {"reason": "try simple assignment", "expected_effect": "lint remains clean"},
            "args": {"patches": [{"path": str(tools.state.input.rtl_path), "start_line": 2, "end_line": 2}]},
        },
    )

    row = json.loads((tools.state.journal.root / "decision_trace.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert row["tool_kind"] == "action"
    assert row["intent"]["reason"] == "try simple assignment"
    assert row["effect"] == "neutral"


def test_llm_compact_builder_accepts_mock_json(tmp_path: Path) -> None:
    journal = RepoReActJournal(tmp_path / "repo_react" / "m")
    journal.append_jsonl(
        "decision_trace.jsonl",
        {
            "tool_name": "probe_vcd",
            "tool_kind": "read",
            "intent": {"question": "is y delayed?"},
            "observation_summary": {"status": "ok", "row_count": 3},
        },
    )
    valid = {
        "schema": "repo_react_llm_compact.v1",
        "current_state": {"failure": "y mismatch"},
        "reasoning_trace": [{"observation": "VCD checked", "inference": "y is delayed", "decision": "inspect driver"}],
        "hypotheses": [{"claim": "driver hold bug", "status": "unresolved", "support": ["decision_trace"], "contradictions": []}],
        "patch_lessons": [],
        "open_questions": ["driver assignment kind"],
        "next_action": {"recommendation": "inspect", "why": "need source"},
        "do_not_repeat": [],
    }

    compact = asyncio.run(
        build_llm_compact_memory(
            cfg=None,
            journal_root=journal.root,
            mode="checkpoint",
            memory_snapshot={"module": "m", "last_sim": {"is_pass": False}},
            context_pack={"task_frame": {"current_target": {"signal": "y"}}},
            llm_generate=lambda _prompt: json.dumps(valid),
        )
    )

    assert compact is not None
    assert compact["schema"] == "repo_react_llm_compact.v1"
    assert compact["metadata"]["source_decision_trace_count"] == 1


def test_llm_compact_builder_returns_none_for_invalid_json(tmp_path: Path) -> None:
    journal = RepoReActJournal(tmp_path / "repo_react" / "m")

    compact = asyncio.run(
        build_llm_compact_memory(
            cfg=None,
            journal_root=journal.root,
            mode="deep",
            memory_snapshot={"module": "m"},
            context_pack={},
            llm_generate=lambda _prompt: "not json",
        )
    )

    assert compact is None
    assert parse_llm_compact_json("not json") is None


def test_llm_compact_builder_skips_without_api_key(tmp_path: Path) -> None:
    journal = RepoReActJournal(tmp_path / "repo_react" / "m")

    compact = asyncio.run(
        build_llm_compact_memory(
            cfg=None,
            journal_root=journal.root,
            mode="checkpoint",
            memory_snapshot={"module": "m"},
            context_pack={},
        )
    )

    assert compact is None


def test_compact_agent_memory_writes_llm_compact_and_prompt(tmp_path: Path, monkeypatch: object) -> None:
    runner, tools = _make_runner(tmp_path)
    runner._latest_context_pack = {"pack_path": "/tmp/pack.json", "task_frame": {"current_target": {"signal": "y"}}}
    llm_memory = {
        "schema": "repo_react_llm_compact.v1",
        "current_state": {"failure": "y mismatch"},
        "reasoning_trace": [],
        "hypotheses": [],
        "patch_lessons": [],
        "open_questions": [],
        "next_action": {"recommendation": "inspect", "why": "need source"},
        "do_not_repeat": [],
    }

    async def fake_compact(**_kwargs: object) -> dict[str, object]:
        return llm_memory

    monkeypatch.setattr(runner_module, "build_llm_compact_memory", fake_compact)

    asyncio.run(runner._compact_agent_memory(mode="checkpoint"))

    prompt = runner._agent.prompts[-1]
    assert "<llm_compact_memory_json>" in prompt
    assert "repo_react_llm_compact.v1" in prompt
    written = json.loads((tools.state.journal.root / "repo_react_llm_compact.json").read_text(encoding="utf-8"))
    assert written["current_state"]["failure"] == "y mismatch"


def test_debug_context_router_fallback_writes_pack_and_preserves_timing(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    tools.state.last_trace_summary = {
        "fail_time": 5,
        "total_mismatches": 7,
        "top_diagnosis": "NORMAL_INT_REG differs at the active edge.",
        "suspect_blocks": [{"id": "A6", "start_line": 20, "end_line": 40, "writes": ["NORMAL_INT_REG"]}],
    }
    tools.state.last_divergence_summary = {
        "status": "stable_values_match_but_tb_edge_mismatch",
        "sampling_mode": "edge_active",
        "edge": "posedge",
        "first_divergence": {
            "signal": "NORMAL_INT_REG",
            "time": 5,
            "ref": "0004",
            "dut": "0000",
            "edge": "posedge",
            "sampling_mode": "edge_active",
            "driver_assignment_kind": "nonblocking",
        },
        "suspect": {"driver_blocks": [{"id": "A6", "start_line": 20, "end_line": 40}]},
    }

    pack = DebugContextRouter(cfg=None, tools=tools).route(goal="initial_triage")

    assert pack["fallback_used"] is True
    assert pack["timing_evidence"]["signal"] == "NORMAL_INT_REG"
    assert pack["timing_evidence"]["time"] == 5
    assert pack["timing_evidence"]["edge"] == "posedge"
    assert pack["timing_evidence"]["driver_assignment_kind"] == "nonblocking"
    assert pack["timing_evidence"]["block_id"] == "A6"
    assert pack["timing_evidence"]["line_range"] == [20, 40]
    assert Path(pack["pack_path"]).is_file()
    assert (tools.state.input.debug_workdir / "debug_context_pack.json").is_file()
    evidence_index = tools.state.journal.root / "evidence" / "evidence_index.jsonl"
    assert evidence_index.is_file()
    assert all("module m(input clk" not in item["summary"] for item in pack["evidence_pack"])


def test_system_triage_schema_defaults() -> None:
    triage = SystemTriage()
    pack = DebugContextPack(module="m")

    assert triage.category == "unknown"
    assert triage.confidence == 0.0
    assert pack.system_triage.category == "unknown"


def test_repo_initial_route_builds_system_triage_without_explicit_focus(tmp_path: Path) -> None:
    tools = _make_repo_tools(tmp_path)
    tools.state.last_trace_summary = {
        "top_diagnosis": "text_out differs at first DUT/ref divergence.",
        "first_divergence": {
            "status": "ok",
            "sampling_mode": "stable",
            "first_divergence": {
                "signal": "text_out",
                "time": 16,
                "ref": "98",
                "dut": "63",
                "sampling_mode": "stable",
            },
            "suspect": {"driver_blocks": [{"id": "A1", "start_line": 10, "end_line": 20}]},
        },
    }

    pack = DebugContextRouter(cfg=None, tools=tools).route(goal="initial_triage")

    triage = pack["system_triage"]
    assert pack["fallback_used"] is True
    assert triage["root_signal"] == "text_out"
    assert triage["root_time"] == 16
    assert triage["suspect_files"]
    assert any(Path(path).name == "child.v" for path in triage["suspect_files"])
    assert triage["recommended_tool_calls"][0]["tool"] == "query_rtl_kg"
    assert "system_triage" in json.loads(Path(pack["pack_path"]).read_text(encoding="utf-8"))


def test_initial_context_pack_can_skip_debug_investigator(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_repo_tools(tmp_path)
    tools.state.last_trace_summary = {
        "first_divergence": {
            "status": "ok",
            "first_divergence": {"signal": "y", "time": 9, "ref": "1", "dut": "0"},
        }
    }
    calls = {"count": 0}

    def fake_investigator(self: object, request: object, timing: object, task_frame: object) -> dict[str, object]:
        calls["count"] += 1
        return {"analysis_text": "investigator ran"}

    monkeypatch.setattr(DebugContextRouter, "_run_investigator", fake_investigator)  # type: ignore[attr-defined]

    skipped = DebugContextRouter(cfg=SimpleNamespace(api_key="x"), tools=tools).route(
        goal="initial_triage",
        allow_investigator=False,
    )
    allowed = DebugContextRouter(cfg=SimpleNamespace(api_key="x"), tools=tools).route(
        goal="initial_triage",
        allow_investigator=True,
    )

    assert calls["count"] == 1
    assert skipped["fallback_used"] is True
    assert skipped["task_frame"].get("router_analysis") != "investigator ran"
    assert allowed["fallback_used"] is False
    assert allowed["task_frame"]["router_analysis"] == "investigator ran"


def test_repo_system_triage_uses_kg_child_module_candidates(tmp_path: Path) -> None:
    tools = _make_repo_tools(tmp_path)
    tools.state.kg_service = _FakeKG(
        [
            {"parent_module": "top", "instance_name": "u_child", "child_module": "child"},
        ]
    )
    tools.state.last_divergence_summary = {
        "status": "ok",
        "sampling_mode": "stable",
        "first_divergence": {"signal": "y", "time": 9, "ref": "1", "dut": "0"},
    }

    pack = DebugContextRouter(cfg=None, tools=tools).route(goal="initial_triage")
    triage = pack["system_triage"]

    assert "child" in triage["suspect_modules"]
    assert any(Path(path).name == "child.v" for path in triage["suspect_files"])
    assert any("KG module_instances returned candidates" in item for item in triage["evidence"])


def test_debug_investigator_tool_response_exposes_visible_content(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    router = DebugContextRouter(cfg=None, tools=tools)

    response = router.read_context(kind="lines", path=str(tools.state.input.rtl_path), start=1, end=2)
    payload = json.loads(response.content[0]["text"])

    assert payload["status"] == "ok"
    assert payload["tool_name"] == "read_context"
    assert "visible_payload" in payload
    assert "module m(input clk" in payload["visible_payload"]["content"]
    assert payload["evidence_ref"]["path"].endswith(".json")
    assert payload["evidence_ref"]["raw_chars"] > 0


def test_debug_investigator_read_spec_exposes_visible_content(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    tools.state.input.spec_text = "AES spec text should be visible to the investigator."
    router = DebugContextRouter(cfg=None, tools=tools)

    response = router.read_spec()
    payload = json.loads(response.content[0]["text"])

    assert payload["status"] == "ok"
    assert "AES spec text should be visible" in payload["visible_payload"]["content"]


def test_repo_debug_context_router_uses_larger_default_tool_budget(tmp_path: Path) -> None:
    tools = _make_repo_tools(tmp_path)

    router = DebugContextRouter(cfg=None, tools=tools)

    assert router.max_tool_calls >= 16


def test_debug_context_router_tool_budget_env_override(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("ZEROREPO_DEBUG_CONTEXT_ROUTER_MAX_TOOL_CALLS", "13")  # type: ignore[attr-defined]
    tools = _make_repo_tools(tmp_path)

    router = DebugContextRouter(cfg=None, tools=tools)

    assert router.max_tool_calls == 13


def test_debug_investigator_skips_vcd_tools_after_missing_vcd(tmp_path: Path) -> None:
    tools = _make_repo_tools(tmp_path)
    router = DebugContextRouter(cfg=None, tools=tools)

    first = json.loads(router.run_check("first_divergence").content[0]["text"])
    listed = json.loads(router.list_vcd_signals().content[0]["text"])
    probed = json.loads(router.probe_vcd(["y"], time=0).content[0]["text"])

    assert first["visible_payload"]["first_divergence"]["status"] == "missing_vcd"
    assert listed["status"] == "skipped_missing_vcd"
    assert probed["status"] == "skipped_missing_vcd"
    assert "static RTL/KG/spec triage" in listed["visible_payload"]["error"]


def test_investigator_triage_paths_are_normalized_to_generated_rtl(tmp_path: Path) -> None:
    tools = _make_repo_tools(tmp_path)
    router = DebugContextRouter(cfg=None, tools=tools)
    base = SystemTriage(root_signal="y")

    merged = router._merge_system_triage(
        base,
        {
            "suspect_files": ["child.v"],
            "recommended_tool_calls": [
                {"tool": "read_context", "args": {"kind": "file", "path": "child.v"}},
            ],
        },
    )

    assert Path(merged.suspect_files[0]).is_absolute()
    assert Path(merged.suspect_files[0]).name == "child.v"
    assert Path(merged.recommended_tool_calls[0]["args"]["path"]).is_absolute()


def test_debug_context_router_uses_initial_trace_divergence_for_task_frame(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    tools.state.last_trace_summary = {
        "top_diagnosis": "NORMAL_INT_REG differs at first DUT/ref divergence.",
        "first_divergence": {
            "status": "ok",
            "sampling_mode": "stable",
            "first_divergence": {
                "signal": "NORMAL_INT_REG",
                "time": 415,
                "ref": "0100",
                "dut": "0010",
                "edge": "posedge",
                "sampling_mode": "stable",
            },
            "suspect": {"driver_blocks": [{"id": "A7", "start_line": 176, "end_line": 287}]},
        },
    }

    pack = DebugContextRouter(cfg=None, tools=tools).route(goal="initial_triage")

    target = pack["task_frame"]["current_target"]
    assert target["signal"] == "NORMAL_INT_REG"
    assert target["time"] == 415
    assert target["ref"] == "0100"
    assert target["dut"] == "0010"
    assert "No current DUT/ref divergence target available" not in target["symptom"]
    assert pack["timing_evidence"]["block_id"] == "A7"


def test_debug_context_router_selects_long_term_memory_by_index(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    tools.state.last_divergence_summary = {
        "status": "ok",
        "sampling_mode": "stable",
        "first_divergence": {"signal": "cmd_out", "time": 9, "ref": "1", "dut": "0"},
    }
    store = RTLMemoryStore.from_workspace(tmp_path)
    store.upsert_memory(
        RTLMemoryHeader(
            memory_id="debug_m_cmd_out_improved",
            type="repair_outcome",
            stage="debug",
            module="m",
            module_family="m",
            signals=["cmd_out"],
            failure_type="local_logic_bug",
            outcome="improved",
            confidence=0.9,
            description="m: cmd_out improved when SETUP assignment was preserved.",
        ),
        "## Patch Summary\n\nVery long details should stay in the markdown file.\n",
    )

    pack = DebugContextRouter(cfg=None, tools=tools).route(goal="before_patch")
    memories = pack["causal_memory"]["selected_long_term_memories"]

    assert memories
    assert memories[0]["path"].endswith(".md")
    assert memories[0]["description"] == "m: cmd_out improved when SETUP assignment was preserved."
    assert "Very long details" in memories[0]["body_excerpt"]
    assert "content" not in memories[0]

    read_result = tools.read_long_term_memory(memories[0]["path"], max_chars=8000)
    outside_result = tools.read_long_term_memory(str(tmp_path / "not_memory.md"), max_chars=8000)

    assert read_result["status"] == "ok"
    assert "Very long details should stay in the markdown file." in read_result["content"]
    assert outside_result["status"] == "error"
    assert "outside rtl_memory root" in outside_result["error"]


def test_long_term_memory_compact_keeps_excerpt_only() -> None:
    compact = _compact_long_term_memories(
        [
            {
                "path": "cases/debug_m_out_improved.md",
                "memory_id": "debug_m_out_improved",
                "type": "repair_outcome",
                "stage": "debug",
                "module": "m",
                "signals": ["out"],
                "failure_type": "timing_bug",
                "outcome": "improved",
                "confidence": 0.9,
                "description": "m: out improved.",
                "patch_pattern": "keep the sampled value",
                "anti_trigger": "different first divergence",
                "content": "A" * 5000,
            }
        ],
        limit=3,
        body_chars=1000,
    )

    assert len(compact) == 1
    assert "content" not in compact[0]
    assert compact[0]["body_excerpt"].startswith("A" * 20)
    assert len(compact[0]["body_excerpt"]) < 1100


def test_memory_selector_prompt_uses_filename_and_description_only() -> None:
    header = RTLMemoryHeader(
        memory_id="debug_m_out_improved",
        type="repair_outcome",
        stage="debug",
        path="cases/debug_m_out_improved.md",
        module="m",
        signals=["out"],
        failure_type="timing_bug",
        description="m: out improved after preserving sampled value.",
        patch_pattern="large patch details should not enter selector prompt",
        anti_trigger="anti trigger details should not enter selector prompt",
    )

    prompt = build_selector_prompt({"module": "m", "signals": ["out"]}, [header], limit=5)

    assert "cases/debug_m_out_improved.md" in prompt
    assert "m: out improved after preserving sampled value." in prompt
    assert "large patch details should not enter selector prompt" not in prompt
    assert "anti trigger details should not enter selector prompt" not in prompt
    assert "memory_file_candidates_json" in prompt


def test_debug_context_router_scans_memory_files_without_index_and_injects_excerpt_only(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    tools.state.last_divergence_summary = {
        "status": "ok",
        "sampling_mode": "stable",
        "first_divergence": {"signal": "cmd_out", "time": 9, "ref": "1", "dut": "0"},
    }
    store = RTLMemoryStore.from_workspace(tmp_path)
    path = store.upsert_memory(
        RTLMemoryHeader(
            memory_id="debug_m_cmd_out_full",
            type="repair_outcome",
            stage="debug",
            module="m",
            module_family="m",
            signals=["cmd_out"],
            failure_type="local_logic_bug",
            outcome="improved",
            confidence=0.9,
            description="m: cmd_out full memory should be injected.",
        ),
        "## Full Memory\n\n" + ("full detail line\n" * 220),
    )
    store.index_path.unlink()

    pack = DebugContextRouter(cfg=None, tools=tools).route(goal="before_patch")
    memories = pack["causal_memory"]["selected_long_term_memories"]
    prompt = build_initial_prompt(
        module_name="m",
        repair_mode="functional",
        rtl_path=str(tools.state.input.rtl_path),
        merged_file=str(tools.state.input.merged_file),
        spec_text="",
        contract_json="",
        sim_failed_excerpt="",
        trace_summary={},
        corrections=[],
        memory_snapshot={},
        context_pack=pack,
    )

    assert path.is_file()
    assert memories
    assert "content" not in memories[0]
    assert "full detail line" in memories[0]["body_excerpt"]
    assert len(memories[0]["body_excerpt"]) < 1100
    assert "full detail line" in prompt
    assert "Selected long-term memories include short excerpts" in prompt


def test_repo_react_prompts_use_context_pack_not_full_static_payload() -> None:
    context_pack = {
        "pack_path": "/tmp/debug_context_pack.json",
        "task_frame": {"current_target": {"signal": "out"}, "top_diagnosis": "out stuck"},
        "system_triage": {
            "category": "hierarchy_connection",
            "confidence": 0.6,
            "root_signal": "out",
            "suspect_modules": ["m", "child"],
            "suspect_files": ["/tmp/rtl.sv", "/tmp/child.v"],
            "recommended_tool_calls": [{"tool": "query_rtl_kg", "args": {"query_type": "module_instances"}}],
            "patch_scope": "repo_child_or_top_after_triage",
        },
        "timing_evidence": {"signal": "out", "time": 7, "edge": "posedge", "ref": "1", "dut": "0"},
        "evidence_pack": [{"evidence_id": "ev_001", "summary": "short trace", "kind": "trace"}],
        "causal_memory": {
            "repair_ledger_summary": [
                {
                    "step": 3,
                    "action_type": "apply_patch",
                    "block_id": "A6",
                    "effect": "improved",
                    "metric_delta": {"total_mismatch": "4286 -> 3850"},
                    "hypothesis": "debounce threshold adds one cycle delay",
                    "lesson": "Patch improved mismatch count or first fail time; continue from this direction.",
                    "patch_summary": "threshold 14 -> 15",
                }
            ],
            "promising_directions": [
                {
                    "step": 3,
                    "effect": "improved",
                    "changed_signals": ["NORMAL_INT_REG"],
                    "lesson": "Keep the debounce threshold change.",
                }
            ],
            "protected_invariants": ["Do not revert debounce threshold change"],
            "unsafe_directions": ["replace_block of A7 regressed mismatch 4723 -> 9344"],
            "selected_long_term_memories": [
                {
                    "path": "cases/debug_m_out_improved.md",
                    "memory_id": "debug_m_out_improved",
                    "type": "repair_outcome",
                    "stage": "debug",
                    "module": "m",
                    "signals": ["out"],
                    "failure_type": "timing_bug",
                    "outcome": "improved",
                    "confidence": 0.9,
                    "description": "m: out improved after preserving sampled value.",
                    "patch_pattern": "hold sampled output through active edge",
                    "anti_trigger": "Do not reuse if first divergence signal differs.",
                    "body_excerpt": "## Patch Summary\nPreserve sampled output until the reference edge observes it.",
                }
            ],
        },
        "raw_artifacts": {"spec": {"kind": "spec", "path": "/tmp/spec.md"}},
    }
    prompt = build_initial_prompt(
        module_name="m",
        repair_mode="functional",
        rtl_path="/tmp/rtl.sv",
        merged_file="/tmp/m.v",
        spec_text="FULL_SPEC_SHOULD_NOT_APPEAR" * 100,
        contract_json="FULL_CONTRACT_SHOULD_NOT_APPEAR" * 100,
        sim_failed_excerpt="Hint: Output 'out' has 1 mismatches.",
        trace_summary={"fail_time": 7},
        corrections=[{"problem": "FULL_CORRECTION_SHOULD_NOT_APPEAR"}],
        memory_snapshot={"repair_ledger": ["FULL_MEMORY_SHOULD_NOT_APPEAR"]},
        context_pack=context_pack,
    )
    compact = build_compact_prompt(context_pack)
    continued = build_continue_prompt(
        memory_summary={},
        readonly_calls_since_action=1,
        max_readonly_calls=16,
        context_pack=context_pack,
    )

    assert "FULL_SPEC_SHOULD_NOT_APPEAR" not in prompt
    assert "FULL_CONTRACT_SHOULD_NOT_APPEAR" not in prompt
    assert "FULL_MEMORY_SHOULD_NOT_APPEAR" not in prompt
    assert "/tmp/debug_context_pack.json" in prompt
    assert "debug_context_pack_summary_json" in prompt
    assert "system_triage" in prompt
    assert "hierarchy_connection" in prompt
    assert "recommended_tool_calls" in prompt
    assert "FIRST ACTION REQUIREMENT" not in prompt
    assert "first visible tool call must be route_debug_context" not in prompt
    assert "route_debug_context with focused parameters" not in prompt
    assert "multi-file apply_patch" in prompt
    assert "stage_artifact_name_help_json" in prompt
    assert "spec_blocks" in prompt
    assert "do not pass module names like aes_cipher_top as artifact names" in prompt
    assert "system-level RTL debug session" in prompt
    assert "repo_react_memory_brief_json" not in compact
    assert "/tmp/debug_context_pack.json" in compact
    assert "causal_memory_summary" in compact
    assert "debounce threshold adds one cycle delay" in compact
    assert "Preserve sampled output until the reference edge observes it." in compact
    assert "Keep the debounce threshold change" in compact
    assert "replace_block of A7 regressed mismatch" in compact
    assert "Continue repository-level RTL repair." in continued
    assert "Use the existing conversation memory and latest persisted artifacts." in continued
    assert "latest_context_pack_path: /tmp/debug_context_pack.json" in continued
    assert "remaining_read_budget_since_action: 15" in continued
    assert "debug_context_pack_summary_json" not in continued
    assert "hierarchy_connection" not in continued
    assert "Keep the debounce threshold change" not in continued
    assert "replace_block of A7 regressed mismatch" not in continued


def test_stage_artifact_error_returns_valid_names(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")

    result = tools.read_context(kind="stage_artifact", artifact_name="aes_cipher_top")

    assert result["status"] == "error"
    assert "valid_artifact_names" in result
    assert "spec_blocks" in result["valid_artifact_names"]
    assert "stage6_merge" in result["valid_artifact_names"]
    assert "Do not" not in result["usage"]


def test_runner_requires_router_before_broad_raw_reads(tmp_path: Path) -> None:
    tools = _make_repo_tools(tmp_path)
    tools.state.last_trace_summary = {
        "first_divergence": {
            "status": "ok",
            "first_divergence": {"signal": "cmd_out", "time": 9, "ref": "1", "dut": "0"},
        }
    }
    runner = RepoReActRunner.__new__(RepoReActRunner)
    runner._state = tools.state
    runner._tools = tools
    runner._context_router = DebugContextRouter(cfg=None, tools=tools)
    runner._latest_context_pack = DebugContextRouter(cfg=None, tools=tools).route(goal="initial_triage")
    runner._last_compacted_action_calls = 0
    runner._last_checkpoint_action_calls = 0
    runner._tool_result_chars_since_compact = 0
    runner._tool_result_chars_since_light = 0
    runner._readonly_calls_since_action = 0
    runner._readonly_calls_since_light = 0
    runner._route_calls_since_action = 0
    runner._light_consolidations_since_checkpoint = 0
    runner._checkpoint_count = 0
    runner._max_readonly_calls_since_action = 16
    runner._router_first_enabled = True

    assert runner._router_first_required_response("probe_vcd") is None
    assert runner._router_first_required_response("query_rtl_kg") is None

    runner._route_calls_since_action = 1

    assert runner._router_first_required_response("probe_vcd") is None


def test_query_rtl_kg_tool_does_not_require_route_first_in_repo_scope(tmp_path: Path) -> None:
    tools = _make_repo_tools(tmp_path)
    runner = RepoReActRunner.__new__(RepoReActRunner)
    runner._state = tools.state
    runner._tools = tools
    runner._context_router = DebugContextRouter(cfg=None, tools=tools)
    runner._latest_context_pack = DebugContextRouter(cfg=None, tools=tools).route(goal="initial_triage")
    runner._last_compacted_action_calls = 0
    runner._last_checkpoint_action_calls = 0
    runner._tool_result_chars_since_compact = 0
    runner._tool_result_chars_since_light = 0
    runner._readonly_calls_since_action = 0
    runner._readonly_calls_since_light = 0
    runner._route_calls_since_action = 0
    runner._light_consolidations_since_checkpoint = 0
    runner._checkpoint_count = 0
    runner._max_readonly_calls_since_action = 32
    runner._router_first_enabled = True

    assert runner._router_first_required_response("query_rtl_kg") is None


def test_route_debug_context_returns_only_compact_evidence_index(tmp_path: Path) -> None:
    tools = _make_repo_tools(tmp_path)
    runner = RepoReActRunner.__new__(RepoReActRunner)
    runner._state = tools.state
    runner._tools = tools
    runner._context_router = DebugContextRouter(cfg=None, tools=tools)
    runner._latest_context_pack = {}
    runner._tool_result_chars_since_compact = 0
    runner._tool_result_chars_since_light = 0
    runner._readonly_calls_since_action = 0
    runner._readonly_calls_since_light = 0
    runner._route_calls_since_action = 0
    runner._route_allowed_reads = []
    runner._route_read_count = 0
    runner._max_readonly_calls_since_action = 32
    tools.state.last_trace_summary = {
        "first_divergence": {
            "status": "ok",
            "first_divergence": {"signal": "y", "time": 9, "ref": "1", "dut": "0"},
        }
    }

    full = runner._route_context_pack("initial_triage")
    payload = runner._compact_route_debug_context_result(full)

    assert payload["schema_version"] == "route_debug_context_summary_v1"
    assert payload["pack_path"]
    assert "system_triage" in payload
    assert "evidence_refs" in payload
    assert "evidence_pack" not in payload
    assert "raw_artifacts" not in payload
    assert "causal_memory" not in payload
    assert len(payload["recommended_tool_calls"]) <= 6
    full_pack = json.loads(Path(payload["pack_path"]).read_text(encoding="utf-8"))
    assert "evidence_pack" in full_pack


def test_route_debug_context_summary_clips_large_pack_payload() -> None:
    runner = RepoReActRunner.__new__(RepoReActRunner)
    long_text = "x" * 5000
    full = {
        "pack_path": "/tmp/pack.json",
        "task_frame": {"router_analysis": long_text},
        "timing_evidence": {"signal": "out", "time": 7},
        "system_triage": {
            "category": "top_protocol_or_fsm",
            "confidence": 0.9,
            "symptom": long_text,
            "root_signal": "out",
            "root_time": 7,
            "suspect_modules": ["m"],
            "signal_path": [{"evidence": long_text, "from": str(i), "to": str(i + 1)} for i in range(8)],
            "evidence": [long_text for _ in range(8)],
            "missing_evidence": [long_text for _ in range(8)],
            "recommended_tool_calls": [{"tool": "probe_vcd", "args": {"i": i}} for i in range(8)],
            "patch_scope": long_text,
            "reason": long_text,
        },
        "evidence_pack": [
            {
                "evidence_id": f"ev_{i:03d}",
                "kind": "trace",
                "summary": long_text,
                "artifact_ref": {"path": f"/tmp/evidence_{i}.json"},
                "salient": {"module": "m"},
            }
            for i in range(8)
        ],
        "raw_artifacts": {"spec": {"path": "/tmp/spec.md"}},
        "causal_memory": {"selected_long_term_memories": [{"content": long_text}]},
    }

    payload = runner._compact_route_debug_context_result(full)
    encoded = json.dumps(payload, ensure_ascii=False)

    assert len(encoded) < 8000
    assert len(payload["recommended_tool_calls"]) == 4
    assert len(payload["raw_read_policy"]["allowed_calls"]) == 4
    assert len(payload["system_triage"]["signal_path"]) == 3
    assert len(payload["system_triage"]["evidence"]) == 4
    assert len(payload["system_triage"]["missing_evidence"]) == 3
    assert len(payload["evidence_refs"]) == 4
    assert all(len(item["summary"]) <= 365 for item in payload["evidence_refs"])
    assert "raw_artifacts" not in payload
    assert "causal_memory" not in payload


def test_route_restricts_raw_reads_to_recommended_calls(tmp_path: Path) -> None:
    tools = _make_repo_tools(tmp_path)
    runner = RepoReActRunner.__new__(RepoReActRunner)
    runner._state = tools.state
    runner._tools = tools
    runner._latest_context_pack = {}
    runner._tool_result_chars_since_compact = 0
    runner._tool_result_chars_since_light = 0
    runner._readonly_calls_since_action = 0
    runner._readonly_calls_since_light = 0
    runner._route_calls_since_action = 1
    runner._route_allowed_reads = [
        {"tool": "query_rtl_kg", "args": {"query_type": "module_instances", "module_name": "top"}}
    ]
    runner._route_read_count = 0
    runner._max_readonly_calls_since_action = 32
    runner._router_first_enabled = True

    blocked_response = runner._route_read_restricted_response("search_context", {"pattern": "assign", "scope": "rtl"})
    allowed_response = runner._route_read_restricted_response(
        "query_rtl_kg",
        {"query_type": "module_instances", "module_name": "top"},
    )
    assert blocked_response is None
    assert allowed_response is None


def test_repo_top_patch_requires_child_exclusion_reason(tmp_path: Path) -> None:
    tools = _make_repo_tools(tmp_path)
    tools.state.observed_real_divergence = True
    top_path = str(tools.state.input.rtl_path)

    blocked = tools.apply_patch(
        patches=[{"path": top_path, "start_line": 2, "end_line": 2, "new_text": "assign y = 1'b1;"}],
        reason="Patch top output driver.",
        expected_effect="fix top output",
        verify=False,
    )
    allowed = tools.apply_patch(
        patches=[{"path": top_path, "start_line": 2, "end_line": 2, "new_text": "assign y = 1'b0;"}],
        reason="Patch top output driver after child modules were excluded by KG/spec evidence.",
        expected_effect="keep top output stable",
        verify=False,
    )

    assert blocked["status"] == "kept_unverified"
    assert allowed["status"] != "rejected"


def test_causal_memory_filters_budget_rejections_and_builds_invariants(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    tools.state.last_divergence_summary = {
        "status": "ok",
        "sampling_mode": "stable",
        "first_divergence": {"signal": "cmd_out", "time": 1155, "ref": "1", "dut": "0", "sampling_mode": "stable"},
        "suspect": {"driver_blocks": [{"id": "A7"}], "signals": ["cmd_out"]},
    }
    tools.state.journal.append_jsonl(
        "patch_journal.jsonl",
        {
            "step": 8,
            "action_type": "apply_patch",
            "target": {"path": "rtl.sv", "start_line": 223, "end_line": 223},
            "changed_signals": ["ack_out"],
            "effect": "improved",
            "hypothesis": "SETUP should not clear ack_out; hold ack_out through SETUP.",
            "lesson": "Patch improved mismatch count or first fail time; continue from this direction.",
            "patch_summary": "",
            "before": {"mismatch_count": 5393, "first_fail_time": 5},
            "after": {"mismatch_count": 5250, "first_fail_time": 5},
            "result": {"status": "improved"},
        },
    )
    tools.state.journal.append_jsonl(
        "patch_journal.jsonl",
        {
            "step": 10,
            "action_type": "replace_block",
            "block_id": "A7",
            "target": {"path": "rtl.sv", "start_line": 176, "end_line": 287, "block_id": "A7"},
            "changed_signals": ["STATUS_REG", "RESP_1_REG", "ERR_INT_REG", "NORMAL_INT_REG", "cmd_out", "settings", "req_out", "ack_out"],
            "effect": "regressed",
            "hypothesis": "broad blocking conversion",
            "lesson": "Patch worsened mismatch count or first fail time and was rolled back.",
            "patch_summary": "always @(posedge clk) begin ... end",
            "before": {"mismatch_count": 4723, "first_fail_time": 5},
            "after": {"mismatch_count": 9344, "first_fail_time": 1155},
            "result": {"status": "rollback", "rollback_reason": "mismatch_count_regressed"},
        },
    )
    tools.state.journal.append_jsonl(
        "patch_journal.jsonl",
        {
            "step": 11,
            "action_type": "apply_patch",
            "target": {},
            "changed_signals": [],
            "effect": "rejected",
            "hypothesis": "over budget",
            "lesson": "Repair action budget exhausted: max_steps=10.",
            "patch_summary": "Repair action budget exhausted: max_steps=10.",
            "result": {"status": "rejected", "reason": "Repair action budget exhausted: max_steps=10."},
        },
    )

    brief = tools.read_memory(kind="brief")["brief"]
    unsafe = tools.read_memory(kind="unsafe_directions")["unsafe_directions"]
    protected = tools.read_memory(kind="protected_invariants")["protected_invariants"]
    failed = tools.read_memory(kind="failed_directions")["directions"]
    pack = DebugContextRouter(cfg=None, tools=tools).route(goal="compact_resume")

    assert "nearby" not in str(brief)
    assert any("ack_out" in item and "SETUP" in item for item in protected)
    assert any("replace_block of A7" in item for item in unsafe)
    assert brief["next_local_target"]["signal"] == "cmd_out"
    assert all("budget exhausted" not in str(item).lower() for item in failed)
    assert pack["causal_memory"]["promising_directions"]
    assert pack["causal_memory"]["promising_directions"][0]["effect"] == "improved"


def test_protected_invariant_gate_requires_preserve_plan(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    tools.state.observed_real_divergence = True
    tools.state.journal.append_jsonl(
        "patch_journal.jsonl",
        {
            "step": 1,
            "action_type": "apply_patch",
            "target": {"path": "rtl.sv", "start_line": 2, "end_line": 2},
            "changed_signals": ["ack_out"],
            "effect": "improved",
            "hypothesis": "SETUP should hold ack_out; do not clear ack_out in SETUP.",
            "lesson": "Patch improved mismatch count or first fail time; continue from this direction.",
            "patch_summary": "ack_out hold through SETUP",
            "before": {"mismatch_count": 10, "first_fail_time": 5},
            "after": {"mismatch_count": 8, "first_fail_time": 5},
            "result": {"status": "improved"},
        },
    )

    blocked = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign ack_out = clk;"}],
        reason="touch protected ack_out",
        expected_effect="test gate",
        verify=False,
    )
    allowed = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign ack_out = clk;"}],
        reason="touch protected ack_out",
        expected_effect="test gate",
        protected_invariants_checked=["Do not clear ack_out in SETUP"],
        preserve_plan="This edit is outside SETUP and preserves ack_out hold-through behavior.",
        verify=False,
    )

    assert blocked["status"] == "kept_unverified"
    assert allowed["status"] == "kept_unverified"


def test_replace_block_requires_real_divergence_in_functional_mode(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")

    result = tools.replace_block(
        block_id="C1",
        new_code="assign y = ~clk;",
        reason="try full assign replacement",
        expected_effect="change output",
        verify=False,
    )

    assert result["status"] == "kept_unverified"
    assert tools.state.action_calls == 1


def test_replace_block_replaces_complete_assign_block_when_verified_false(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    tools.state.observed_real_divergence = True

    result = tools.replace_block(
        block_id="C1",
        new_code="assign y = ~clk;",
        reason="replace continuous assignment",
        expected_effect="invert output",
        verify=False,
    )

    rtl = tools.state.input.rtl_path.read_text(encoding="utf-8")
    assert result["status"] == "kept_unverified"
    assert "assign y = ~clk;" in rtl
    rows = tools._read_jsonl("patch_journal.jsonl")
    assert rows[-1]["action_type"] == "replace_block"
    assert rows[-1]["block_id"] == "C1"
    assert tools.memory_snapshot()["recent_replaced_blocks"][-1]["block_id"] == "C1"


def test_memory_snapshot_recent_repair_journal_is_slim(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    tools.state.journal.append_jsonl(
        "patch_journal.jsonl",
        {
            "step": 7,
            "action_type": "apply_patch",
            "block_id": "A3",
            "effect": "improved",
            "lesson": "Patch improved mismatch count or first fail time; continue from this direction.",
            "patch_summary": "assign y = fixed;",
            "before": {"mismatch_count": 12, "first_fail_time": 40},
            "after": {"mismatch_count": 6, "first_fail_time": 80},
            "metric_delta": {"total_mismatch": "12 -> 6"},
            "changed_signals": ["y"],
            "target": {"path": "rtl.sv", "start_line": 2, "end_line": 2},
            "result": {
                "trace_summary": {"huge": "T" * 5000},
                "sim_output_excerpt": "S" * 5000,
                "lint_output_excerpt": "L" * 5000,
            },
            "patches": [{"new_text": "P" * 5000}],
            "evidence": {"latest_trace_summary": {"huge": "E" * 5000}},
        },
    )

    snapshot = tools.memory_snapshot()
    recent = snapshot["recent_repair_journal"]

    assert len(recent) == 1
    assert set(recent[0]) == {
        "step",
        "action_type",
        "block_id",
        "effect",
        "lesson",
        "patch_summary",
        "before",
        "after",
        "metric_delta",
        "changed_signals",
        "target",
    }
    assert recent[0]["metric_delta"] == {"total_mismatch": "12 -> 6"}
    assert "result" not in recent[0]
    assert "patches" not in recent[0]
    assert "trace_summary" not in json.dumps(recent[0], ensure_ascii=False)
    assert len(json.dumps(recent, ensure_ascii=False)) < 2000


def test_replace_block_lint_fail_rolls_back(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_tools(tmp_path, repair_mode="syntax")
    before = tools.state.input.rtl_path.read_text(encoding="utf-8")

    def fake_check_syntax(_path: str, top_module: str | None = None) -> tuple[bool, str]:
        del top_module
        return False, "lint failed"

    monkeypatch.setattr(tools_module, "check_syntax", fake_check_syntax)
    result = tools.replace_block(
        block_id="C1",
        new_code="assign y = ;",
        reason="broken replace",
        expected_effect="lint should catch it",
    )

    assert result["status"] == "rollback"
    assert result["rollback_reason"] == "lint_failed"
    assert tools.state.input.rtl_path.read_text(encoding="utf-8") == before
