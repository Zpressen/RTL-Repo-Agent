from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from types import SimpleNamespace
from zerorepo.rtl_impl.debug_agent.bash_tools import CommandResult
from zerorepo.rtl_impl.debug_agent.debug_runner import RtlDebugConfig

from zerorepo.rtl_impl.repo_react.journal import RepoReActJournal
from zerorepo.rtl_impl.repo_react.compact import (
    build_deterministic_compact_memory,
    build_llm_compact_memory,
    parse_llm_compact_json,
)
from zerorepo.rtl_impl.repo_react.context import DebugContextRouter
from zerorepo.rtl_impl.repo_react.prompt import (
    SYSTEM_PROMPT,
    _compact_long_term_memories,
    build_compact_prompt,
    build_continue_prompt,
    build_initial_prompt,
    build_tool_call_recovery_prompt,
)
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
    runner._pending_tool_call_recovery = {}
    runner._tool_call_recovery_signatures = set()
    runner._max_readonly_calls_since_action = 16
    runner._router_first_enabled = True
    runner._route_allowed_reads = []
    runner._route_read_count = 0
    runner._required_initial_trace_call = {}
    runner._initial_trace_completed = True
    return runner, tools


def test_debug_action_budget_defaults_to_thirty(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path)

    assert RtlDebugConfig(openai_config=None).max_trials == 30
    assert tools.state.input.max_steps == 30
    assert inspect.signature(RepoReActRunner).parameters["max_steps"].default == 30
    assert RepoReActRunner._resolve_max_agent_turns(
        tools.state.input,
        tools.state.input.max_steps,
    ) == 90


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

    assert result["status"] == "syntax_retry_required"
    assert result["rollback_reason"] == "lint_failed"
    assert result["candidate_id"] == "syntax_candidate_0001"
    assert result["patch_attempt_id"] == 1
    assert result["syntax_retries_used"] == 0
    assert result["syntax_retries_remaining"] == 2
    assert top_path.read_text(encoding="utf-8") == before_top
    assert child_path.read_text(encoding="utf-8") == before_child
    assert tools.state.action_calls == 0
    assert tools.state.patch_attempt_id == 1


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

    captured: dict[str, object] = {}

    def fake_judge(payload: dict[str, object]) -> dict[str, object]:
        captured.update(payload)
        return {"decision": "rollback"}

    monkeypatch.setattr(tools_module, "check_syntax", fake_check_syntax)
    monkeypatch.setattr(tools, "_llm_patch_acceptance_decision", fake_judge)

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
    assert len(captured["patch_diff"]) == 2  # type: ignore[arg-type]
    assert {item["path"] for item in captured["patch_diff"]} == {str(top_path), str(child_path)}  # type: ignore[union-attr]
    assert all("assign y = 1'b1;" in item["new_text"] for item in captured["patch_diff"])  # type: ignore[union-attr]
    assert len(captured["rtl_surrounding_context"]) == 2  # type: ignore[arg-type]
    assert top_path.read_text(encoding="utf-8") == before_top
    assert child_path.read_text(encoding="utf-8") == before_child


def test_repo_scope_defaults_to_light_readonly_budget(tmp_path: Path) -> None:
    tools = _make_repo_tools(tmp_path)
    runner = RepoReActRunner.__new__(RepoReActRunner)
    runner._readonly_budget_from_env = False
    runner._max_readonly_calls_since_action = 16

    runner._configure_scope_defaults(tools.state.input)

    assert runner._max_readonly_calls_since_action == 16


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


def test_apply_patch_syntax_retries_share_one_functional_action(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_tools(tmp_path, repair_mode="syntax")
    rtl_path = tools.state.input.rtl_path
    before = rtl_path.read_text(encoding="utf-8")
    lint_results = iter(
        [
            (False, CommandResult(stdout="", stderr=f"%Error: {rtl_path}:2:12: unexpected ';'").model_dump_json()),
            (False, CommandResult(stdout="", stderr=f"%Error: {rtl_path}:2:12: unexpected ';'").model_dump_json()),
            (True, CommandResult(stdout="lint ok", stderr="").model_dump_json()),
        ]
    )
    monkeypatch.setattr(tools_module, "check_syntax", lambda *_args, **_kwargs: next(lint_results))

    first = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ;"}],
        reason="repair assignment",
        expected_effect="lint passes",
    )
    assert first["status"] == "syntax_retry_required"
    assert first["syntax_errors"] == [
        {"path": str(rtl_path), "line": 2, "column": 12, "message": "unexpected ';'"}
    ]
    assert rtl_path.read_text(encoding="utf-8") == before
    assert tools.state.action_calls == 0

    second = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ;"}],
        reason="repair assignment syntax",
        expected_effect="lint passes",
        syntax_retry_of=first["candidate_id"],
    )
    assert second["status"] == "syntax_retry_required"
    assert second["candidate_id"] == first["candidate_id"]
    assert second["syntax_retries_used"] == 1
    assert second["syntax_retries_remaining"] == 1
    assert rtl_path.read_text(encoding="utf-8") == before
    assert tools.state.action_calls == 0

    third = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ~clk;"}],
        reason="finish assignment syntax repair",
        expected_effect="lint passes",
        syntax_retry_of=first["candidate_id"],
    )
    assert third["status"] == "pass"
    assert third["candidate_id"] == first["candidate_id"]
    assert third["patch_attempt_id"] == 3
    assert third["action_step"] == 1
    assert third["committed"] is True
    assert tools.state.patch_attempt_id == 3
    assert tools.state.action_calls == 1
    assert tools.state.syntax_candidates[first["candidate_id"]]["status"] == "resolved"


def test_apply_patch_syntax_retry_exhaustion_does_not_consume_budget(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_tools(tmp_path, repair_mode="syntax")
    before = tools.state.input.rtl_path.read_text(encoding="utf-8")
    monkeypatch.setattr(tools_module, "check_syntax", lambda *_args, **_kwargs: (False, "lint failed"))
    patch = [{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ;"}]

    first = tools.apply_patch(patches=patch, reason="try", expected_effect="lint")
    second = tools.apply_patch(
        patches=patch,
        reason="retry one",
        expected_effect="lint",
        syntax_retry_of=first["candidate_id"],
    )
    third = tools.apply_patch(
        patches=patch,
        reason="retry two",
        expected_effect="lint",
        syntax_retry_of=first["candidate_id"],
    )

    assert first["status"] == "syntax_retry_required"
    assert second["status"] == "syntax_retry_required"
    assert third["status"] == "syntax_retry_exhausted"
    assert third["syntax_retries_used"] == 2
    assert third["syntax_retries_remaining"] == 0
    assert tools.state.patch_attempt_id == 3
    assert tools.state.action_calls == 0
    assert tools.state.input.rtl_path.read_text(encoding="utf-8") == before

    rejected = tools.apply_patch(
        patches=patch,
        reason="retry too late",
        expected_effect="lint",
        syntax_retry_of=first["candidate_id"],
    )
    assert rejected["status"] == "rejected"
    assert tools.state.patch_attempt_id == 3
    assert tools.state.action_calls == 0


def test_syntax_retry_rejects_unknown_or_changed_target_without_counting(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_tools(tmp_path, repair_mode="syntax")
    monkeypatch.setattr(tools_module, "check_syntax", lambda *_args, **_kwargs: (False, "lint failed"))
    first = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ;"}],
        reason="try",
        expected_effect="lint",
    )

    unknown = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = clk;"}],
        reason="unknown",
        expected_effect="lint",
        syntax_retry_of="syntax_candidate_9999",
    )
    changed_target = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 1, "end_line": 1, "new_text": "module m(input clk, output y);"}],
        reason="changed target",
        expected_effect="lint",
        syntax_retry_of=first["candidate_id"],
    )
    changed_action = tools.replace_block(
        block_id="C1",
        new_code="assign y = clk;",
        reason="changed action",
        expected_effect="lint",
        syntax_retry_of=first["candidate_id"],
    )

    assert unknown["status"] == "rejected"
    assert changed_target["status"] == "rejected"
    assert changed_action["status"] == "rejected"
    assert tools.state.patch_attempt_id == 1
    assert tools.state.action_calls == 0


def test_syntax_failure_is_journaled_but_not_an_unsafe_direction(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_tools(tmp_path, repair_mode="syntax")
    monkeypatch.setattr(tools_module, "check_syntax", lambda *_args, **_kwargs: (False, "lint failed"))

    result = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 2, "end_line": 2, "new_text": "assign y = ;"}],
        reason="syntax typo",
        expected_effect="lint",
    )
    snapshot = tools.memory_snapshot()

    assert result["status"] == "syntax_retry_required"
    assert tools._read_jsonl("patch_journal.jsonl")[-1]["effect"] == "syntax_failed"
    assert snapshot["unsafe_directions"] == []
    assert snapshot["failed_directions"] == []
    assert snapshot["repair_ledger"] == []
    assert snapshot["pending_syntax_candidates"][0]["candidate_id"] == result["candidate_id"]


def test_runner_agent_turn_budget_defaults_to_three_times_functional_budget(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    inp = tools.state.input
    inp.max_steps = 15
    assert RepoReActRunner._resolve_max_agent_turns(inp, inp.max_steps) == 45
    inp.max_agent_turns = 7
    assert RepoReActRunner._resolve_max_agent_turns(inp, inp.max_steps) == 7


def test_initial_trace_is_minimal_seed_with_required_one_hop_call(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    runner, tools = _make_runner(tmp_path, repair_mode="functional")
    report = {
        "runtime_top_module": "m",
        "dut_instance": "dut0",
        "first_failure": {"signal": "legacy_signal"},
        "suspect_blocks": [{"id": "A1", "start_line": 2, "end_line": 2}],
        "value_backtrace": {
            "chains": [
                {
                    "sig": "y",
                    "chain": [{"driver_block_id": "A1", "classification": "constant_assignment"}],
                }
            ]
        },
        "first_divergence": {
            "status": "ok",
            "sampling_event": {"edge": "posedge", "clock": "clk", "source": "tb_checker"},
            "nearby": {"rows": [{"t": 9, "y_dut": "0", "y_ref": "1"}]},
            "suspect": {"driver_blocks": [{"id": "A1"}]},
            "first_divergence": {
                "signal": "y",
                "time": 9,
                "ref": "1",
                "dut": "0",
                "classification": "wrong_value",
            },
        },
    }
    monkeypatch.setattr(runner_module, "build_trace_report", lambda **_kwargs: (report, []))

    seed = runner._build_initial_trace(tools.state.input)

    assert seed == {
        "root_module": "m",
        "root_signal": "y",
        "first_divergence_time": 9,
        "expected_value": "1",
        "actual_value": "0",
        "sampling_event": {"edge": "posedge", "clock": "clk", "source": "tb_checker"},
        "required_next_tool": "trace_signal_cause",
        "arguments": {
            "module_name": "m",
            "signal_name": "y",
            "time": 9,
            "expected_value": "1",
        },
    }
    assert runner._initial_dut_instance == "dut0"
    assert "nearby" not in seed
    assert "suspect_blocks" not in seed
    assert "value_backtrace_summary" not in seed
    persisted = json.loads((tools.state.input.debug_workdir / "trace_report.json").read_text(encoding="utf-8"))
    assert persisted["suspect_blocks"][0]["id"] == "A1"


def test_initial_trace_gate_unlocks_context_and_vcd_only_after_matching_successful_trace(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    runner, tools = _make_runner(tmp_path, repair_mode="functional")
    async def inline_to_thread(func: object, *args: object, **kwargs: object) -> object:
        return func(*args, **kwargs)  # type: ignore[operator]

    monkeypatch.setattr(runner_module.asyncio, "to_thread", inline_to_thread)
    required = {
        "module_name": "m",
        "signal_name": "y",
        "time": 9,
        "expected_value": "1",
    }
    runner._required_initial_trace_call = required
    runner._initial_trace_completed = False

    blocked_read = json.loads(
        asyncio.run(
            runner.read_context(
                kind="lines",
                path=str(tools.state.input.rtl_path),
                start=1,
                end=2,
            )
        ).content[0]["text"]
    )
    blocked_probe = json.loads(
        asyncio.run(runner.probe_vcd(signals=["y"], time=9)).content[0]["text"]
    )
    assert blocked_read["status"] == "initial_trace_required"
    assert blocked_probe["status"] == "initial_trace_required"
    assert blocked_read["arguments"] == required

    wrong = json.loads(
        asyncio.run(
            runner.trace_signal_cause(
                module_name="m",
                signal_name="y",
                time=10,
                expected_value="1",
            )
        ).content[0]["text"]
    )
    assert wrong["initial_trace_gate"]["status"] == "pending"
    assert runner._initial_trace_completed is False

    completed = json.loads(
        asyncio.run(
            runner.trace_signal_cause(
                module_name="m",
                signal_name="y",
                time=9,
                expected_value="1",
            )
        ).content[0]["text"]
    )
    assert completed["status"] == "static_only"
    assert completed["initial_trace_gate"] == {
        "status": "completed",
        "unlocked_tools": ["read_context", "probe_vcd"],
    }
    assert runner._initial_trace_completed is True

    unblocked_read = json.loads(
        asyncio.run(
            runner.read_context(
                kind="lines",
                path=str(tools.state.input.rtl_path),
                start=1,
                end=2,
            )
        ).content[0]["text"]
    )
    assert unblocked_read["status"] == "ok"


def test_runner_reports_independent_turn_action_and_patch_counts(tmp_path: Path, monkeypatch: object) -> None:
    runner, tools = _make_runner(tmp_path, repair_mode="functional")
    async def inline_to_thread(func: object, *args: object, **kwargs: object) -> object:
        return func(*args, **kwargs)  # type: ignore[operator]

    monkeypatch.setattr(runner_module.asyncio, "to_thread", inline_to_thread)
    runner._readonly_budget_from_env = False
    runner._route_allowed_reads = []
    runner._route_read_count = 0
    runner._build_initial_trace = lambda _inp: {}  # type: ignore[method-assign]
    monkeypatch.setattr(
        RepoReActTools,
        "persist_memory_snapshot",
        lambda self: {
            "module": self.state.input.module_name,
            "last_sim": self.state.last_sim.model_dump(),
            "action_calls": self.state.action_calls,
            "patch_attempts": self.state.patch_attempt_id,
            "max_steps": self.state.input.max_steps,
            "causal_memory_brief": {},
        },
    )
    inp = tools.state.input.model_copy(update={"max_steps": 15, "max_agent_turns": 3})

    result = asyncio.run(runner.chat(inp))

    assert result.status == "max_steps_exceeded"
    assert result.agent_turns == 3
    assert result.steps == 3
    assert result.action_calls == 0
    assert result.patch_attempts == 0
    assert "agent turn budget exhausted (3/3)" in result.reason


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


def test_acceptance_payload_includes_full_diff_context_authority_and_ledger(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")
    rtl_path = tools.state.input.rtl_path
    baseline_lines = ["module m(input clk, output y);"] + [f"// line {idx}" for idx in range(2, 65)] + ["endmodule"]
    rtl_path.write_text("\n".join(baseline_lines) + "\n", encoding="utf-8")
    tools.state.input.spec_text = "target_signal must change only at the sampled posedge."
    tb_text = "module tb;\nalways @(posedge clk) if (target_signal !== expected) errors = errors + 1;\nendmodule\n"
    (tools.state.input.debug_workdir / "tb.sv").write_text(tb_text, encoding="utf-8")

    for step in range(1, 8):
        tools.state.journal.append_jsonl(
            "patch_journal.jsonl",
            {
                "step": step,
                "effect": "neutral",
                "action_type": "apply_patch",
                "target": {"path": str(rtl_path), "start_line": step, "end_line": step},
                "changed_signals": [f"old_signal_{step}"],
                "hypothesis": f"prior repair {step}",
                "patch_summary": f"prior patch {step}",
                "result": {"status": "neutral"},
            },
        )
    tools.state.journal.append_jsonl(
        "patch_journal.jsonl",
        {"step": 8, "effect": "syntax_failed", "target": {"path": str(rtl_path)}, "result": {}},
    )

    before_log = CommandResult(
        stdout="Hint: Output 'target_signal' has 1 mismatches. First mismatch occurred at time 10.\nMismatches: 1 in 20 samples\n",
        stderr="",
    ).model_dump_json()
    after_log = CommandResult(
        stdout="Hint: Output 'target_signal' has 2 mismatches. First mismatch occurred at time 10.\nMismatches: 2 in 20 samples\n",
        stderr="",
    ).model_dump_json()
    tools.state.last_sim = SimSnapshot(is_pass=False, mismatch_count=1, first_fail_time=10, sim_output_path="")
    tools.state.last_sim_output = before_log
    tools.state.sim_reviewer = SimpleNamespace(review=lambda: (False, 2, after_log))
    tools._trace_payload_for_sim = lambda _sim_output: {  # type: ignore[method-assign]
        "trace_summary": None,
        "divergence_summary": None,
        "error": None,
    }
    captured: dict[str, object] = {}

    def fake_judge(payload: dict[str, object]) -> dict[str, object]:
        captured.update(payload)
        return {"decision": "rollback", "confidence": 0.9, "reason": "regressed"}

    monkeypatch.setattr(
        tools_module,
        "check_syntax",
        lambda *_args, **_kwargs: (True, CommandResult(stdout="", stderr="").model_dump_json()),
    )
    monkeypatch.setattr(tools, "_llm_patch_acceptance_decision", fake_judge)
    long_new_text = "wire target_signal;\n" + "// complete diff marker " + ("X" * 600)

    result = tools.apply_patch(
        patches=[{"path": "rtl.sv", "start_line": 31, "end_line": 31, "new_text": long_new_text}],
        reason="candidate hypothesis",
        expected_effect="change target signal",
    )

    assert result["status"] == "rollback"
    diff = captured["patch_diff"][0]  # type: ignore[index]
    assert diff["old_text"] == "// line 31"
    assert diff["new_text"] == long_new_text
    assert "X" * 600 in diff["unified_diff"]
    surrounding = captured["rtl_surrounding_context"][0]  # type: ignore[index]
    assert surrounding["above"].splitlines()[0] == "11: // line 11"
    assert surrounding["above"].splitlines()[-1] == "30: // line 30"
    assert surrounding["below"].splitlines()[0] == "32: // line 32"
    assert surrounding["below"].splitlines()[-1] == "51: // line 51"
    authority = captured["authoritative_context"]  # type: ignore[assignment]
    assert authority["spec"]["available"] is True  # type: ignore[index]
    assert authority["spec"]["content"] == tools.state.input.spec_text  # type: ignore[index]
    assert authority["testbench"]["content"] == tb_text  # type: ignore[index]
    assert [row["step"] for row in captured["recent_repair_ledger"]] == [3, 4, 5, 6, 7]  # type: ignore[union-attr]


def test_authoritative_context_uses_bounded_keyword_windows_and_reports_unavailable(tmp_path: Path) -> None:
    long_text = "\n".join(
        "magic_signal is sampled here" if idx == 500 else f"unrelated specification line {idx}"
        for idx in range(1, 1000)
    )
    excerpt = tools_module._bounded_authoritative_excerpt(
        long_text,
        keywords=["magic_signal"],
        max_chars=6000,
    )

    assert excerpt["truncated"] is True
    assert excerpt["selection"] == "keyword_windows"
    assert "magic_signal is sampled here" in excerpt["content"]
    assert len(excerpt["content"]) <= 6000

    tools = _make_tools(tmp_path / "missing", repair_mode="functional")
    context = tools._authoritative_context_for_acceptance(["y"])
    assert context["spec"]["available"] is False
    assert context["spec"]["source"] == "unavailable"
    assert context["testbench"]["available"] is False
    assert context["testbench"]["selection"] == "unavailable"

    spec_path = tools.state.input.workspace_root / "authoritative_spec.md"
    spec_path.write_text(long_text, encoding="utf-8")
    tools.state.input.spec_source_path = str(spec_path)
    tools.state.input.spec_text = "fallback text must not win"
    tb_path = tools.state.input.debug_workdir / "tb.sv"
    tb_path.write_text(long_text, encoding="utf-8")
    sourced = tools._authoritative_context_for_acceptance(["magic_signal"])

    assert sourced["spec"]["source"] == [str(spec_path)]
    assert "magic_signal is sampled here" in sourced["spec"]["content"]
    assert "fallback text must not win" not in sourced["spec"]["content"]
    assert sourced["spec"]["truncated"] is True
    assert sourced["testbench"]["available"] is True
    assert sourced["testbench"]["truncated"] is True
    assert "magic_signal is sampled here" in sourced["testbench"]["content"]
    assert len(sourced["spec"]["content"]) <= 6000
    assert len(sourced["testbench"]["content"]) <= 6000


def test_patch_surrounding_context_handles_file_boundaries() -> None:
    lines = [f"line {idx}" for idx in range(1, 31)]
    first = tools_module._patch_surrounding_context(
        Path("first.v"),
        tools_module.Patch(path="first.v", start_line=1, end_line=1, new_text="changed"),
        lines,
        context_lines=20,
    )
    last = tools_module._patch_surrounding_context(
        Path("last.v"),
        tools_module.Patch(path="last.v", start_line=30, end_line=30, new_text="changed"),
        lines,
        context_lines=20,
    )

    assert first["above"] == ""
    assert first["below"].splitlines()[0] == "2: line 2"
    assert first["below"].splitlines()[-1] == "21: line 21"
    assert last["above"].splitlines()[0] == "10: line 10"
    assert last["above"].splitlines()[-1] == "29: line 29"
    assert last["below"] == ""


def test_acceptance_decision_evidence_refs_are_optional_and_preserved(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path, repair_mode="functional")

    legacy = tools._parse_acceptance_decision('{"decision":"keep","confidence":0.7,"reason":"ok"}')
    enriched = tools._parse_acceptance_decision(
        '{"decision":"rollback","confidence":0.9,"reason":"bad",'
        '"evidence_refs":["patch_diff[0]","metric_delta.target_signal",3]}'
    )

    assert legacy is not None and "evidence_refs" not in legacy
    assert enriched is not None
    assert enriched["evidence_refs"] == ["patch_diff[0]", "metric_delta.target_signal", "3"]
    prompt = tools_module._build_patch_acceptance_prompt({"patch_diff": [], "authoritative_context": {}})
    assert "authoritative spec and testbench context outrank" in prompt
    assert "reason, expected_effect, and preserve_plan are hypotheses" in prompt
    assert '"evidence_refs"' in prompt


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

    assert "<recovery_memory_json>" in prompt
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


def test_failed_readonly_tool_does_not_consume_read_budget(tmp_path: Path) -> None:
    runner, _tools = _make_runner(tmp_path)
    runner._readonly_calls_since_action = 3
    runner._readonly_calls_since_light = 2

    runner._tool_response("read_context", {"status": "error", "error": "bad path"})

    assert runner._readonly_calls_since_action == 3
    assert runner._readonly_calls_since_light == 2

    runner._tool_response("read_context", {"status": "ok", "kind": "file", "content": "module m; endmodule"})

    assert runner._readonly_calls_since_action == 4
    assert runner._readonly_calls_since_light == 3


def test_failed_route_debug_context_does_not_consume_read_budget(tmp_path: Path) -> None:
    runner, _tools = _make_runner(tmp_path)

    runner._tool_response("route_debug_context", {"status": "error", "error": "router failed"})

    assert runner._route_calls_since_action == 0
    assert runner._readonly_calls_since_action == 0
    assert runner._readonly_calls_since_light == 0

    runner._tool_response("route_debug_context", {"status": "ok", "pack_path": "pack.json"})

    assert runner._route_calls_since_action == 1
    assert runner._readonly_calls_since_action == 1
    assert runner._readonly_calls_since_light == 1


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


def test_rejected_action_tool_does_not_reset_read_budget(tmp_path: Path) -> None:
    runner, _tools = _make_runner(tmp_path, repair_mode="syntax")
    runner._readonly_calls_since_action = 5
    runner._route_calls_since_action = 2
    runner._route_allowed_reads = [{"tool": "read_context", "args": {"kind": "lines"}}]
    runner._route_read_count = 1

    runner._tool_response("apply_patch", {"status": "rejected", "is_action_executed": False, "reason": "bad patch"})

    assert runner._readonly_calls_since_action == 5
    assert runner._route_calls_since_action == 2
    assert runner._route_allowed_reads
    assert runner._route_read_count == 1

    runner._tool_response("apply_patch", {"status": "rollback", "is_action_executed": True, "rollback_reason": "lint_failed"})

    assert runner._readonly_calls_since_action == 0
    assert runner._route_calls_since_action == 0
    assert runner._route_allowed_reads == []
    assert runner._route_read_count == 0


def test_record_correction_does_not_reset_read_budget(tmp_path: Path) -> None:
    runner, _tools = _make_runner(tmp_path, repair_mode="syntax")
    runner._readonly_calls_since_action = 16
    runner._route_calls_since_action = 2
    runner._route_allowed_reads = [{"tool": "read_context", "args": {"kind": "stage_artifact"}}]
    runner._route_read_count = 1

    runner._tool_response("record_correction", {"status": "ok", "path": "planning_corrections/plan_overrides.json"})

    assert runner._readonly_calls_since_action == 16
    assert runner._route_calls_since_action == 2
    assert runner._route_allowed_reads
    assert runner._route_read_count == 1


def test_observation_budget_exhausted_only_allows_rtl_edit_to_reset(tmp_path: Path) -> None:
    runner, _tools = _make_runner(tmp_path, repair_mode="syntax")
    runner._readonly_calls_since_action = 16
    runner._max_readonly_calls_since_action = 16

    response = runner._readonly_budget_exceeded_response("list_vcd_signals")
    assert response is not None
    payload = json.loads(response.content[0]["text"])

    assert payload["status"] == "observation_budget_exhausted"
    assert payload["required_next_action"] == ["apply_patch", "replace_block"]
    assert "record_correction and generate_response do not reset" in payload["message"]


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
    assert "<recovery_memory_json>" in prompt
    assert "repo_react_llm_compact.v1" in prompt
    written = json.loads((tools.state.journal.root / "repo_react_llm_compact.json").read_text(encoding="utf-8"))
    assert written["current_state"]["failure"] == "y mismatch"


def test_deterministic_compact_keeps_pending_neutral_retrace_without_context_pack(
    tmp_path: Path,
) -> None:
    journal = RepoReActJournal(tmp_path / "journal")
    journal.append_jsonl(
        "patch_journal.jsonl",
        {
            "action_type": "replace_block",
            "reason": "remove reset overwrite",
            "effect": "neutral",
            "target": {"block_id": "A2"},
        },
    )
    required = {
        "module_name": "m",
        "signal_name": "text_out",
        "time": 15,
        "expected_value": "aa",
    }

    compact = build_deterministic_compact_memory(
        journal_root=journal.root,
        mode="checkpoint",
        memory_snapshot={
            "module": "m",
            "current_rtl_hash": "rtl-hash",
            "last_sim": {"is_pass": False, "mismatch_count": 1},
            "last_divergence_summary": {
                "first_divergence": {
                    "signal": "text_out",
                    "time": 15,
                    "ref": "aa",
                    "dut": "00",
                }
            },
            "last_signal_trace": {"module": "m", "signal": "text_out", "time": 15},
            "pending_post_patch_trace": required,
            "repair_ledger": [{"effect": "neutral", "reason": "remove reset overwrite"}],
            "protected_invariants": ["keep output ordering"],
            "unsafe_directions": ["do not invert output bytes"],
        },
        context_pack={},
    )
    prompt = build_compact_prompt({}, llm_compact_memory=compact)

    assert compact["metadata"]["source"] == "deterministic_fallback"
    assert compact["next_action"]["recommendation"] == "trace_signal_cause"
    assert compact["next_action"]["arguments"] == required
    assert compact["patch_lessons"][0]["effect"] == "neutral"
    assert "<recovery_memory_json>" in prompt
    assert "text_out" in prompt


def test_compact_agent_memory_uses_deterministic_recovery_when_llm_compact_fails(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    runner, tools = _make_runner(tmp_path)
    required = {
        "module_name": "m",
        "signal_name": "y",
        "time": 9,
        "expected_value": "1",
    }
    tools.state.last_divergence_summary = {
        "first_divergence": {"signal": "y", "time": 9, "ref": "1", "dut": "0"}
    }
    tools.state.last_signal_trace = {
        "module": "m",
        "signal": "y",
        "time": 9,
        "focus_context": {"signals": ["y"], "rtl_blocks": ["A1"]},
    }
    tools.state.pending_post_patch_trace = required
    runner._latest_context_pack = {}

    async def failed_compact(**_kwargs: object) -> None:
        return None

    monkeypatch.setattr(runner_module, "build_llm_compact_memory", failed_compact)
    asyncio.run(runner._compact_agent_memory(mode="checkpoint"))

    prompt = runner._agent.prompts[-1]
    written = json.loads(
        (tools.state.journal.root / "repo_react_recovery_memory.json").read_text(
            encoding="utf-8"
        )
    )
    assert "<recovery_memory_json>" in prompt
    assert written["metadata"]["source"] == "deterministic_fallback"
    assert written["next_action"]["recommendation"] == "trace_signal_cause"
    assert written["next_action"]["arguments"] == required


def test_textual_dsml_tool_call_is_recorded_and_retried_once(tmp_path: Path) -> None:
    runner, tools = _make_runner(tmp_path)
    text = (
        '<｜｜DSML｜｜tool_calls>\n'
        '<｜｜DSML｜｜invoke name="replace_block">\n'
        '<｜｜DSML｜｜parameter name="path">rtl.sv</｜｜DSML｜｜parameter>\n'
        "</｜｜DSML｜｜invoke>\n"
        "</｜｜DSML｜｜tool_calls>"
    )

    runner._record_unexecuted_tool_call(text)

    assert tools.state.action_calls == 0
    assert runner._pending_tool_call_recovery["tool_name"] == "replace_block"
    recovery = build_tool_call_recovery_prompt("replace_block")
    assert "native function call" in recovery
    assert "does not accept `path`" in recovery
    rows = tools._read_jsonl("react_trace.jsonl")
    assert rows[-1]["event"] == "unexecuted_tool_call"
    assert rows[-1]["retry_eligible"] is True

    runner._pending_tool_call_recovery = {}
    runner._record_unexecuted_tool_call(text)
    assert runner._pending_tool_call_recovery == {}
    assert tools._read_jsonl("react_trace.jsonl")[-1]["retry_eligible"] is False


def test_neutral_patch_requires_matching_trace_before_next_rtl_action(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    runner, tools = _make_runner(tmp_path)

    async def inline_to_thread(func: object, *args: object, **kwargs: object) -> object:
        return func(*args, **kwargs)  # type: ignore[operator]

    monkeypatch.setattr(runner_module.asyncio, "to_thread", inline_to_thread)
    tools.state.last_divergence_summary = {
        "first_divergence": {"signal": "y", "time": 9, "ref": "1", "dut": "0"}
    }
    tools.state.last_trace_summary = {"runtime_top_module": "m"}
    neutral = runner._attach_post_patch_trace_requirement(
        {"status": "neutral", "committed": True, "effect": "neutral"}
    )
    required = neutral["arguments"]
    assert neutral["required_next_tool"] == "trace_signal_cause"

    blocked = json.loads(
        asyncio.run(
            runner.apply_patch(
                patches=[
                    {
                        "path": str(tools.state.input.rtl_path),
                        "start_line": 2,
                        "end_line": 2,
                        "new_text": "assign y = ~clk;",
                    }
                ],
                reason="second patch",
                expected_effect="change output",
                verify=False,
            )
        ).content[0]["text"]
    )
    assert blocked["status"] == "post_patch_trace_required"
    assert blocked["arguments"] == required

    wrong = json.loads(
        asyncio.run(
            runner.trace_signal_cause(
                module_name="m",
                signal_name="y",
                time=10,
                expected_value="1",
            )
        ).content[0]["text"]
    )
    assert wrong["post_patch_trace_gate"]["status"] == "pending"
    assert tools.state.pending_post_patch_trace == required

    matched = json.loads(
        asyncio.run(
            runner.trace_signal_cause(
                module_name="m",
                signal_name="y",
                time=9,
                expected_value="1",
            )
        ).content[0]["text"]
    )
    assert matched["post_patch_trace_gate"]["status"] == "completed"
    assert tools.state.pending_post_patch_trace == {}

    allowed = json.loads(
        asyncio.run(
            runner.apply_patch(
                patches=[
                    {
                        "path": str(tools.state.input.rtl_path),
                        "start_line": 2,
                        "end_line": 2,
                        "new_text": "assign y = ~clk;",
                    }
                ],
                reason="evidence refreshed",
                expected_effect="change output",
                verify=False,
            )
        ).content[0]["text"]
    )
    assert allowed["status"] == "kept_unverified"


def test_repeated_first_divergence_after_trace_returns_minimal_cache(tmp_path: Path) -> None:
    tools = _make_tools(tmp_path)
    tools.state.last_signal_trace = {
        "status": "static_only",
        "module": "m",
        "signal": "y",
        "time": 9,
    }
    tools.state.last_signal_trace_action_calls = tools.state.action_calls
    tools.state.last_divergence_summary = {
        "status": "ok",
        "sampling_event": {"edge": "posedge", "clock": "clk"},
        "first_divergence": {"signal": "y", "time": 9, "ref": "1", "dut": "0"},
    }

    result = tools.run_check("first_divergence")

    assert result["cached"] is True
    assert result["first_divergence"]["first_divergence"]["signal"] == "y"
    assert "nearby" not in result["first_divergence"]
    assert result["first_divergence"]["trace_report_path"].endswith("trace_report.json")


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
    assert triage["recommended_tool_calls"][0]["tool"] == "trace_signal_cause"
    assert triage["recommended_tool_calls"][1]["tool"] == "read_module_semantics"
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


def test_repo_debug_context_router_uses_light_default_tool_budget(tmp_path: Path) -> None:
    tools = _make_repo_tools(tmp_path)

    router = DebugContextRouter(cfg=None, tools=tools)

    assert router.max_tool_calls >= 8


def test_debug_context_router_errors_do_not_consume_tool_budget(tmp_path: Path) -> None:
    tools = _make_repo_tools(tmp_path)
    router = DebugContextRouter(cfg=None, tools=tools)
    router.max_tool_calls = 1

    failed = json.loads(router._readonly_tool_response("read_context", {"status": "error", "error": "bad path"}).content[0]["text"])

    assert failed["status"] == "error"
    assert router._tool_calls == 0

    first_ok = json.loads(router._readonly_tool_response("read_context", {"status": "ok", "content": "module top; endmodule"}).content[0]["text"])
    second_ok = json.loads(router._readonly_tool_response("read_context", {"status": "ok", "content": "module child; endmodule"}).content[0]["text"])

    assert first_ok["status"] == "ok"
    assert second_ok["status"] == "router_readonly_budget_exhausted"
    assert router._tool_calls == 1


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
        runtime_top_module="runtime_m",
        dut_instance="top_module1",
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
        runtime_top_module="runtime_m",
        dut_instance="top_module1",
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
    assert "<planner_module_name>\nm\n</planner_module_name>" in prompt
    assert "<runtime_top_module>\nruntime_m\n</runtime_top_module>" in prompt
    assert "<dut_instance>\ntop_module1\n</dut_instance>" in prompt
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


def test_repo_react_prompts_forbid_oracle_literal_hardcoding() -> None:
    oracle_value = "362f13449254d1bc0ede8c53b043ad5e"
    context_pack = {
        "pack_path": "/tmp/debug_context_pack.json",
        "causal_memory": {
            "selected_long_term_memories": [
                {
                    "path": "cases/debug_aes_improved.md",
                    "memory_id": "debug_aes_improved",
                    "type": "repair_outcome",
                    "stage": "debug",
                    "module": "aes_inv_cipher_top",
                    "signals": ["text_out"],
                    "failure_type": "timing_bug",
                    "outcome": "improved",
                    "confidence": 0.72,
                    "description": "A visible mismatch decreased.",
                    "patch_pattern": f"text_out <= 128'h{oracle_value};",
                    "body_excerpt": f"## Patch Summary\ntext_out <= 128'h{oracle_value};",
                }
            ]
        },
    }
    initial = build_initial_prompt(
        module_name="aes_inv_cipher_top",
        runtime_top_module="aes_inv_cipher_top",
        dut_instance="top_module1",
        repair_mode="functional",
        rtl_path="/tmp/aes_inv_cipher_top.v",
        merged_file="/tmp/merged_aes_inv_cipher_top.v",
        spec_text="",
        contract_json="",
        sim_failed_excerpt="Hint: Output text_out has 1 mismatch.",
        trace_summary={"expected_value": oracle_value},
        corrections=[],
        memory_snapshot={},
        context_pack=context_pack,
    )
    continued = build_continue_prompt(
        memory_summary={},
        readonly_calls_since_action=1,
        max_readonly_calls=16,
        context_pack=context_pack,
    )

    assert '"generalization_check"' in SYSTEM_PROMPT
    assert '"uses_observed_expected_value": false' in SYSTEM_PROMPT
    assert "visible testbench is not an exhaustive specification" in SYSTEM_PROMPT
    assert "Never copy an observed value into RTL" in SYSTEM_PROMPT
    assert "A lower mismatch count alone does not validate hardcoded" in SYSTEM_PROMPT
    assert oracle_value in initial
    assert "must never become a patch RHS" in initial
    assert "never its concrete data literals" in initial
    assert "does not prove that a patch generalizes" in initial
    assert "never copy them into a patch RHS" in continued
    assert "not concrete data literals" in continued
    assert "lower mismatch count alone as proof of generalization" in continued


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

    assert result["status"] == "syntax_retry_required"
    assert result["rollback_reason"] == "lint_failed"
    assert tools.state.input.rtl_path.read_text(encoding="utf-8") == before
    assert tools.state.action_calls == 0
    assert tools.state.patch_attempt_id == 1


def test_replace_block_syntax_retry_uses_same_candidate_chain(tmp_path: Path, monkeypatch: object) -> None:
    tools = _make_tools(tmp_path, repair_mode="syntax")
    lint_results = iter([(False, "lint failed"), (True, "lint ok")])
    monkeypatch.setattr(tools_module, "check_syntax", lambda *_args, **_kwargs: next(lint_results))

    first = tools.replace_block(
        block_id="C1",
        new_code="assign y = ;",
        reason="broken replace",
        expected_effect="lint passes",
    )
    retry = tools.replace_block(
        block_id="C1",
        new_code="assign y = ~clk;",
        reason="fix replace syntax",
        expected_effect="lint passes",
        syntax_retry_of=first["candidate_id"],
    )

    assert first["status"] == "syntax_retry_required"
    assert retry["status"] == "pass"
    assert retry["candidate_id"] == first["candidate_id"]
    assert tools.state.patch_attempt_id == 2
    assert tools.state.action_calls == 1
    assert "assign y = ~clk;" in tools.state.input.rtl_path.read_text(encoding="utf-8")
