from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import zerorepo.rtl_impl.codex_debug.session as session_module
import zerorepo.rtl_impl.codex_debug.runner as runner_module
from zerorepo.rtl_impl.codex_debug.mcp_server import mcp
from zerorepo.rtl_impl.codex_debug.runner import CodexDebugRunner
from zerorepo.rtl_impl.codex_debug.schemas import CodexDebugRunDescriptor
from zerorepo.rtl_impl.codex_debug.session import CodexDebugSession


INITIAL_RTL = "module top(input wire clk, output reg out); always @(posedge clk) out <= 1'b0; endmodule\n"
EDITED_RTL = "module top(input wire clk, output reg out); always @(posedge clk) out <= 1'b1; endmodule\n"
SECOND_EDIT = "module top(input wire clk, output reg out); always @(posedge clk) out <= ~out; endmodule\n"


class FakeReviewer:
    def __init__(self, output_dir: Path, results: list[tuple[bool, int, str]] | None = None) -> None:
        self.output_dir = output_dir
        self.results = list(
            results
            or [
                (
                    False,
                    1,
                    "Hint: Output out has 1 mismatches. First at time 20\nSummary:\n  system_verify: FAIL\n",
                )
            ]
        )
        self.calls = 0

    def review(self) -> tuple[bool, int, str]:
        index = min(self.calls, len(self.results) - 1)
        self.calls += 1
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "wave.vcd").write_text(
            "$timescale 1ns $end\n$scope module tb $end\n$var wire 1 ! clk $end\n$upscope $end\n$enddefinitions $end\n#0\n0!\n",
            encoding="utf-8",
        )
        return self.results[index]


@pytest.fixture
def run_descriptor(tmp_path: Path) -> CodexDebugRunDescriptor:
    task_root = tmp_path / "visible"
    spec_root = task_root / "spec"
    merged_root = task_root / "merged"
    private_root = tmp_path / "private"
    debug_workdir = private_root / "artifacts"
    spec_root.mkdir(parents=True)
    merged_root.mkdir(parents=True)
    debug_workdir.mkdir(parents=True)
    (spec_root / "spec.md").write_text("# top\nout follows the planned behavior.\n", encoding="utf-8")
    (merged_root / "top.v").write_text(INITIAL_RTL, encoding="utf-8")
    return CodexDebugRunDescriptor(
        run_id="test-run",
        task_root=task_root,
        spec_root=spec_root,
        merged_root=merged_root,
        private_root=private_root,
        debug_workdir=debug_workdir,
        planner_module_name="top",
        top_module="top",
        top_rtl=merged_root / "top.v",
        spec_paths=[spec_root / "spec.md"],
        initial_mismatch_count=2,
        initial_sim_output=(
            "Hint: Output out has 2 mismatches. First at time 10\n"
            "Summary:\n  system_verify: FAIL\n"
        ),
        max_validation_trials=3,
    )


@pytest.fixture(autouse=True)
def isolated_codex_config_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    codex_home = tmp_path / "source_codex_home"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text(
        'model = "base-model"\n', encoding="utf-8"
    )
    (codex_home / "proxy-a.config.toml").write_text(
        'model_provider = "test_proxy"\n'
        'model = "profile-model"\n'
        '[model_providers.test_proxy]\n'
        'name = "Test Proxy"\n'
        'base_url = "https://example.invalid/v1"\n'
        'env_key = "ZEROREPO_TEST_CODEX_API_KEY"\n'
        'requires_openai_auth = false\n'
        'wire_api = "responses"\n',
        encoding="utf-8",
    )
    # This is a test-only sentinel, not a credential.
    monkeypatch.setenv("ZEROREPO_TEST_CODEX_API_KEY", "test-key-present")
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    return codex_home


@pytest.fixture
def debug_session(
    run_descriptor: CodexDebugRunDescriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> CodexDebugSession:
    monkeypatch.setattr(session_module, "check_syntax", lambda *_args, **_kwargs: (True, "lint ok"))
    reviewer = FakeReviewer(run_descriptor.debug_workdir)
    session = CodexDebugSession(run_descriptor, reviewer=reviewer)
    yield session
    session.close()


def test_mcp_exposes_only_the_eight_codex_debug_tools() -> None:
    async def collect() -> list[Any]:
        return await mcp.list_tools()

    tools = asyncio.run(collect())
    assert [tool.name for tool in tools] == [
        "read_module_semantics",
        "query_rtl_kg",
        "trace_signal_cause",
        "list_vcd_signals",
        "probe_vcd",
        "run_check",
        "validate_rtl_changes",
        "get_debug_status",
    ]
    query = next(tool for tool in tools if tool.name == "query_rtl_kg")
    enum_values = query.inputSchema["properties"]["query_type"]["enum"]
    assert enum_values == [
        "module_interface",
        "module_instances",
        "instance_connections",
        "signal_drivers",
    ]


def test_native_edit_evaluate_and_accept_advances_baseline(debug_session: CodexDebugSession) -> None:
    rtl_path = debug_session.merged_root / "top.v"
    rtl_path.write_text(EDITED_RTL, encoding="utf-8")

    blocked = debug_session.run_check("top_sim")
    assert blocked["status"] == "dirty_workspace_requires_validation"

    evaluated = debug_session.validate_rtl_changes(
        "evaluate",
        reason="Drive the expected value.",
        expected_effect="Reduce out mismatches.",
    )
    assert evaluated["status"] == "evaluated"
    assert evaluated["lint_pass"] is True
    assert evaluated["sim_completed"] is True
    assert evaluated["diff"]["modified"] == ["top.v"]
    candidate_id = evaluated["candidate_id"]
    assert debug_session.get_debug_status()["phase"] == "pending_validated"

    accepted = debug_session.validate_rtl_changes("accept", candidate_id=candidate_id)
    assert accepted["status"] == "accepted"
    assert accepted["baseline_revision"] == 1
    assert debug_session.get_debug_status()["phase"] == "clean_accepted"
    assert rtl_path.read_text(encoding="utf-8") == EDITED_RTL


def test_codex_can_rollback_a_validated_candidate(debug_session: CodexDebugSession) -> None:
    rtl_path = debug_session.merged_root / "top.v"
    rtl_path.write_text(EDITED_RTL, encoding="utf-8")
    first = debug_session.validate_rtl_changes("evaluate")
    debug_session.validate_rtl_changes("accept", candidate_id=first["candidate_id"])

    rtl_path.write_text(SECOND_EDIT, encoding="utf-8")
    second = debug_session.validate_rtl_changes("evaluate")
    rolled_back = debug_session.validate_rtl_changes("rollback", candidate_id=second["candidate_id"])

    assert rolled_back["status"] == "rolled_back"
    assert rtl_path.read_text(encoding="utf-8") == EDITED_RTL
    assert debug_session.get_debug_status()["phase"] == "clean_accepted"


def test_accept_rejects_candidate_changed_after_evaluation(debug_session: CodexDebugSession) -> None:
    rtl_path = debug_session.merged_root / "top.v"
    rtl_path.write_text(EDITED_RTL, encoding="utf-8")
    result = debug_session.validate_rtl_changes("evaluate")
    rtl_path.write_text(SECOND_EDIT, encoding="utf-8")

    stale = debug_session.validate_rtl_changes("accept", candidate_id=result["candidate_id"])
    assert stale["status"] == "stale_candidate"
    assert debug_session.get_debug_status()["phase"] == "dirty_unvalidated"


def test_lint_failure_keeps_candidate_for_codex_retry(
    run_descriptor: CodexDebugRunDescriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lint_results = iter([(False, "syntax error"), (True, "lint ok")])
    monkeypatch.setattr(session_module, "check_syntax", lambda *_args, **_kwargs: next(lint_results))
    session = CodexDebugSession(run_descriptor, reviewer=FakeReviewer(run_descriptor.debug_workdir))
    try:
        rtl_path = session.merged_root / "top.v"
        rtl_path.write_text(EDITED_RTL, encoding="utf-8")
        first = session.validate_rtl_changes("evaluate")
        assert first["status"] == "lint_failed"
        assert session.list_vcd_signals()["status"] == "candidate_dynamic_evidence_unavailable"

        rtl_path.write_text(SECOND_EDIT, encoding="utf-8")
        second = session.validate_rtl_changes("evaluate")
        assert second["candidate_id"] == first["candidate_id"]
        assert second["candidate_revision"] == 2
        assert second["lint_pass"] is True
    finally:
        session.close()


def test_empty_diff_does_not_consume_validation_budget(debug_session: CodexDebugSession) -> None:
    result = debug_session.validate_rtl_changes("evaluate")
    assert result["status"] == "no_changes"
    assert debug_session.validation_trials == 0


def test_non_rtl_file_or_symlink_is_rejected_and_baseline_restored(debug_session: CodexDebugSession) -> None:
    bad_file = debug_session.merged_root / "notes.txt"
    bad_file.write_text("not rtl", encoding="utf-8")
    rejected = debug_session.validate_rtl_changes("evaluate")
    assert rejected["status"] == "security_violation"
    assert rejected["restored"] is True
    assert not bad_file.exists()
    assert (debug_session.merged_root / "top.v").read_text(encoding="utf-8") == INITIAL_RTL

    outside = debug_session.private_root / "outside.v"
    outside.write_text(EDITED_RTL, encoding="utf-8")
    (debug_session.merged_root / "escape.v").symlink_to(outside)
    symlink_rejected = debug_session.validate_rtl_changes("evaluate")
    assert symlink_rejected["status"] == "security_violation"
    assert not (debug_session.merged_root / "escape.v").exists()


def test_changed_spec_aborts_validation(debug_session: CodexDebugSession) -> None:
    (debug_session.spec_root / "spec.md").write_text("tampered", encoding="utf-8")
    (debug_session.merged_root / "top.v").write_text(EDITED_RTL, encoding="utf-8")
    result = debug_session.validate_rtl_changes("evaluate")
    assert result["status"] == "security_violation"
    assert "spec" in result["reason"]


def test_semantics_response_hides_server_side_artifact_paths(debug_session: CodexDebugSession) -> None:
    hidden = debug_session.private_root / "planning" / "module_plan.json"
    debug_session.tools.read_module_semantics = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
        "status": "ok",
        "source": "planning_kg",
        "provenance": {"output_root": str(hidden.parent), "artifact_paths": {"plan": str(hidden)}},
        "plan_subtasks": [{"id": "T1", "text": "repair output timing"}],
    }
    result = debug_session.read_module_semantics("top")
    serialized = json.dumps(result)
    assert "output_root" not in serialized
    assert "artifact_paths" not in serialized
    assert str(debug_session.private_root) not in serialized
    assert result["plan_subtasks"][0]["id"] == "T1"


def test_close_fails_closed_and_restores_unresolved_edit(debug_session: CodexDebugSession) -> None:
    rtl_path = debug_session.merged_root / "top.v"
    rtl_path.write_text(EDITED_RTL, encoding="utf-8")
    debug_session.close()
    assert rtl_path.read_text(encoding="utf-8") == INITIAL_RTL


def test_dirty_workspace_can_rollback_without_an_evaluated_candidate(debug_session: CodexDebugSession) -> None:
    rtl_path = debug_session.merged_root / "top.v"
    rtl_path.write_text(EDITED_RTL, encoding="utf-8")
    result = debug_session.validate_rtl_changes("rollback")
    assert result["status"] == "rolled_back"
    assert rtl_path.read_text(encoding="utf-8") == INITIAL_RTL


def test_initial_trace_is_advisory_and_does_not_block_validation(debug_session: CodexDebugSession) -> None:
    trace_report_path = debug_session.debug_workdir / "trace_report.json"
    assert trace_report_path.is_file()
    trace_report = json.loads(trace_report_path.read_text(encoding="utf-8"))
    assert trace_report.get("runtime_top_module") == "top" or "trace_error" in trace_report

    debug_session.required_initial_trace = {
        "module_name": "top",
        "signal_name": "out",
        "time": 10,
        "expected_value": "1",
    }
    debug_session.initial_trace_completed = False
    rtl_path = debug_session.merged_root / "top.v"
    rtl_path.write_text(EDITED_RTL, encoding="utf-8")
    evaluated = debug_session.validate_rtl_changes("evaluate")
    assert evaluated["status"] == "evaluated"
    assert debug_session.validation_trials == 1
    debug_session.validate_rtl_changes("rollback", candidate_id=evaluated["candidate_id"])

    debug_session.tools.trace_signal_cause = lambda *_args, **_kwargs: {"status": "static_only"}  # type: ignore[method-assign]
    traced = debug_session.trace_signal_cause("top", "out", 10, "1")
    assert traced["initial_trace_hint"]["status"] == "observed"


def test_readonly_calls_are_statistics_without_a_hard_limit(debug_session: CodexDebugSession) -> None:
    for _ in range(40):
        result = debug_session.get_debug_status()
        assert result["status"] == "ok"
    status = debug_session.get_debug_status()
    assert status["budgets"]["readonly_calls"] == 41
    assert "max_readonly_calls" not in status["budgets"]


def test_session_restores_counters_and_accepted_evidence_across_mcp_restarts(
    run_descriptor: CodexDebugRunDescriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(session_module, "check_syntax", lambda *_args, **_kwargs: (True, "lint ok"))
    first = CodexDebugSession(run_descriptor, reviewer=FakeReviewer(run_descriptor.debug_workdir))
    rtl_path = first.merged_root / "top.v"
    rtl_path.write_text(EDITED_RTL, encoding="utf-8")
    evaluated = first.validate_rtl_changes("evaluate")
    first.validate_rtl_changes("accept", candidate_id=evaluated["candidate_id"])
    first.get_debug_status()
    first.close()

    second = CodexDebugSession(run_descriptor, reviewer=FakeReviewer(run_descriptor.debug_workdir))
    try:
        status = second.get_debug_status()
        assert status["baseline_revision"] == 1
        assert status["budgets"]["validation_trials"] == 1
        assert status["budgets"]["accepted_actions"] == 1
        assert status["budgets"]["readonly_calls"] == 2
        assert rtl_path.read_text(encoding="utf-8") == EDITED_RTL
    finally:
        second.close()


def test_session_rejects_corrupt_or_mismatched_persistent_state(
    run_descriptor: CodexDebugRunDescriptor,
) -> None:
    first = CodexDebugSession(run_descriptor, reviewer=FakeReviewer(run_descriptor.debug_workdir))
    first.close()
    state_path = run_descriptor.private_root / "session_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["run_id"] = "different-run"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(ValueError, match="another run"):
        CodexDebugSession(run_descriptor, reviewer=FakeReviewer(run_descriptor.debug_workdir))


def test_validation_budget_exhaustion_requires_rollback(
    run_descriptor: CodexDebugRunDescriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    descriptor = run_descriptor.model_copy(update={"max_validation_trials": 1})
    monkeypatch.setattr(session_module, "check_syntax", lambda *_args, **_kwargs: (True, "lint ok"))
    session = CodexDebugSession(descriptor, reviewer=FakeReviewer(descriptor.debug_workdir))
    try:
        rtl_path = session.merged_root / "top.v"
        rtl_path.write_text(EDITED_RTL, encoding="utf-8")
        first = session.validate_rtl_changes("evaluate")
        assert first["status"] == "evaluated"
        rtl_path.write_text(SECOND_EDIT, encoding="utf-8")
        exhausted = session.validate_rtl_changes("evaluate")
        assert exhausted["status"] == "validation_budget_exhausted"
        assert session.validate_rtl_changes("rollback")["status"] == "rolled_back"
    finally:
        session.close()


def _write_parent_verifier(path: Path) -> None:
    path.write_text(
        "from pathlib import Path\n"
        "def verify_system(generated_dir):\n"
        "    text = Path(generated_dir, 'top.v').read_text()\n"
        "    ok = \"1'b1\" in text\n"
        "    return ok, ('PASS' if ok else 'FAIL')\n",
        encoding="utf-8",
    )


def test_codex_runner_accepts_only_mcp_committed_baseline(
    run_descriptor: CodexDebugRunDescriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = run_descriptor.private_root.parent / "verify.py"
    _write_parent_verifier(verifier)
    descriptor = run_descriptor.model_copy(update={"verify_script": verifier})
    monkeypatch.setattr(session_module, "check_syntax", lambda *_args, **_kwargs: (True, "lint ok"))
    runner = CodexDebugRunner(timeout=10)

    def fake_process(
        _command: list[str],
        *,
        cwd: Path,
        tee_path: Path | None = None,
        process_env: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> tuple[int, bool, str, str]:
        assert cwd == descriptor.task_root
        assert tee_path == descriptor.private_root / "codex_trace_episode_001.jsonl"
        assert timeout is not None and timeout > 0
        assert process_env is not None
        private_codex_home = Path(process_env["CODEX_HOME"])
        assert private_codex_home == descriptor.private_root / "codex_home"
        assert (private_codex_home / "config.toml").is_file()
        assert (private_codex_home / "proxy-a.config.toml").is_file()
        assert not (private_codex_home / "auth.json").exists()
        session = CodexDebugSession(
            descriptor,
            reviewer=FakeReviewer(
                descriptor.debug_workdir,
                results=[(True, 0, "Summary:\n  system_verify: PASS\n")],
            ),
        )
        descriptor.top_rtl.write_text(EDITED_RTL, encoding="utf-8")
        evaluated = session.validate_rtl_changes("evaluate")
        session.validate_rtl_changes("accept", candidate_id=evaluated["candidate_id"])
        session.close()
        return 0, False, '{"type":"agent_message"}\n', ""

    monkeypatch.setattr(runner, "_run_process", fake_process)
    result = runner.run(descriptor)
    assert result.is_pass is True
    assert result.action_calls == 1
    assert result.patch_attempts == 1
    assert descriptor.top_rtl.read_text(encoding="utf-8") == EDITED_RTL


def test_codex_command_uses_only_run_scoped_mcp_and_workspace(
    run_descriptor: CodexDebugRunDescriptor,
) -> None:
    runner = CodexDebugRunner(codex_bin="codex-test", profile="proxy-a", model="debug-model")
    descriptor_path = run_descriptor.private_root / "descriptor.json"
    last_message = run_descriptor.private_root / "last.txt"
    command = runner.build_command(run_descriptor, descriptor_path, last_message, "debug")
    rendered = "\n".join(command)
    assert command[:2] == ["codex-test", "exec"]
    assert "--ephemeral" not in command
    assert "--profile" in command and "proxy-a" in command
    assert "--ignore-user-config" not in command
    assert 'forced_login_method="api"' in command
    assert "workspace-write" in command
    assert str(run_descriptor.task_root) in command
    assert "mcp_servers.zerorepo_rtl_debug.command" in rendered
    assert "mcp_servers.zerorepo_rtl_debug.enabled_tools" in rendered
    assert "mcp_servers.zerorepo_rtl_debug.env.PYTHONPATH" in rendered
    assert (
        f"mcp_servers.zerorepo_rtl_debug.startup_timeout_sec="
        f"{run_descriptor.verifier_timeout + 60}"
    ) in rendered
    multi_index = command.index("multi_agent")
    assert command[multi_index - 1] == "--disable"
    assert "--model" not in command


def test_codex_multi_agent_and_resume_command_are_explicitly_configured(
    run_descriptor: CodexDebugRunDescriptor,
) -> None:
    runner = CodexDebugRunner(codex_bin="codex-test", multi_agent=True)
    descriptor_path = run_descriptor.private_root / "descriptor.json"
    last_message = run_descriptor.private_root / "last.txt"
    initial = runner.build_command(run_descriptor, descriptor_path, last_message, "debug")
    resume = runner.build_resume_command(
        run_descriptor,
        descriptor_path,
        last_message,
        "session-123",
        "continue",
    )
    initial_index = initial.index("multi_agent")
    resume_index = resume.index("multi_agent")
    assert initial[initial_index - 1] == "--enable"
    assert resume[resume_index - 1] == "--enable"
    assert resume[:3] == ["codex-test", "exec", "resume"]
    expected_startup_timeout = (
        f"mcp_servers.zerorepo_rtl_debug.startup_timeout_sec="
        f"{run_descriptor.verifier_timeout + 60}"
    )
    assert expected_startup_timeout in initial
    assert expected_startup_timeout in resume
    assert "--profile" not in resume
    assert "--ephemeral" not in resume
    assert resume[-2:] == ["session-123", "continue"]


def test_codex_runner_resumes_same_session_until_accepted_baseline_passes(
    run_descriptor: CodexDebugRunDescriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = run_descriptor.private_root.parent / "verify.py"
    _write_parent_verifier(verifier)
    descriptor = run_descriptor.model_copy(update={"verify_script": verifier})
    monkeypatch.setattr(session_module, "check_syntax", lambda *_args, **_kwargs: (True, "lint ok"))
    runner = CodexDebugRunner(timeout=10)
    commands: list[list[str]] = []

    def fake_process(
        command: list[str],
        *,
        cwd: Path,
        timeout: float | None = None,
        **_kwargs: object,
    ) -> tuple[int, bool, str, str]:
        del cwd, timeout
        commands.append(command)
        current = CodexDebugSession.from_descriptor_path(
            descriptor.private_root / "run_descriptor.json",
            reviewer=FakeReviewer(
                descriptor.debug_workdir,
                results=[(True, 0, "Summary:\n  system_verify: PASS\n")],
            ),
        )
        try:
            if len(commands) == 2:
                descriptor.top_rtl.write_text(EDITED_RTL, encoding="utf-8")
                evaluated = current.validate_rtl_changes("evaluate")
                current.validate_rtl_changes("accept", candidate_id=evaluated["candidate_id"])
        finally:
            current.close()
        return 0, False, '{"type":"thread.started","thread_id":"session-123"}\n', ""

    monkeypatch.setattr(runner, "_run_process", fake_process)
    result = runner.run(descriptor)
    assert result.is_pass is True
    assert len(commands) == 2
    assert commands[1][:3] == ["codex", "exec", "resume"]
    assert commands[1][-2] == "session-123"
    status = json.loads((descriptor.private_root / "debug_status.json").read_text(encoding="utf-8"))
    assert status["codex_runtime"] == {
        "session_id": "session-123",
        "episode": 2,
        "resumed": True,
    }


def test_codex_runner_shares_one_wall_clock_deadline_across_resumes(
    run_descriptor: CodexDebugRunDescriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = run_descriptor.private_root.parent / "verify.py"
    verifier.write_text("def verify_system(_generated_dir):\n    return False, 'FAIL'\n", encoding="utf-8")
    descriptor = run_descriptor.model_copy(update={"verify_script": verifier})
    ticks = iter([100.0, 102.0, 106.0])
    monkeypatch.setattr(runner_module.time, "monotonic", lambda: next(ticks))
    runner = CodexDebugRunner(timeout=10)
    episode_timeouts: list[float] = []

    def fake_process(
        _command: list[str],
        *,
        timeout: float | None = None,
        **_kwargs: object,
    ) -> tuple[int, bool, str, str]:
        assert timeout is not None
        episode_timeouts.append(timeout)
        if len(episode_timeouts) == 1:
            session = CodexDebugSession.from_descriptor_path(
                descriptor.private_root / "run_descriptor.json",
                reviewer=FakeReviewer(descriptor.debug_workdir),
            )
            session.close()
            return 0, False, '{"type":"thread.started","thread_id":"session-123"}\n', ""
        return 0, True, '{"type":"thread.started","thread_id":"session-123"}\n', ""

    monkeypatch.setattr(runner, "_run_process", fake_process)
    result = runner.run(descriptor)
    assert result.is_pass is False
    assert episode_timeouts == [8.0, 4.0]
    assert "timed out after 10s" in result.reason


def test_codex_command_uses_model_only_without_profile(
    run_descriptor: CodexDebugRunDescriptor,
) -> None:
    runner = CodexDebugRunner(codex_bin="codex-test", profile="", model="debug-model")
    descriptor_path = run_descriptor.private_root / "descriptor.json"
    last_message = run_descriptor.private_root / "last.txt"
    command = runner.build_command(run_descriptor, descriptor_path, last_message, "debug")
    assert "--profile" not in command
    assert "--model" in command and "debug-model" in command


def test_run_process_captures_each_jsonl_and_stderr_line_once(tmp_path: Path) -> None:
    runner = CodexDebugRunner(profile="", timeout=5)
    tee = tmp_path / "trace.jsonl"
    command = [
        sys.executable,
        "-c",
        "import sys; print('{\"type\":\"thread.started\",\"thread_id\":\"s1\"}'); "
        "print('{\"type\":\"turn.completed\"}'); print('warning', file=sys.stderr)",
    ]
    exit_code, timed_out, stdout, stderr = runner._run_process(  # noqa: SLF001
        command,
        cwd=tmp_path,
        tee_path=tee,
        timeout=5,
    )
    assert exit_code == 0
    assert timed_out is False
    assert stdout.count("thread.started") == 1
    assert stdout.count("turn.completed") == 1
    assert stderr == "warning\n"
    assert tee.read_text(encoding="utf-8") == stdout
    assert runner._extract_session_id(stdout) == "s1"  # noqa: SLF001


def test_codex_profile_preflight_rejects_missing_provider_key(
    run_descriptor: CodexDebugRunDescriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ZEROREPO_TEST_CODEX_API_KEY")
    runner = CodexDebugRunner(timeout=10)
    with pytest.raises(RuntimeError, match="ZEROREPO_TEST_CODEX_API_KEY"):
        runner.run(run_descriptor)
    stderr = (run_descriptor.private_root / "codex_stderr.log").read_text(encoding="utf-8")
    assert "profile preflight failed" in stderr
    assert "test-key-present" not in stderr


def test_codex_runner_discards_unvalidated_native_edit(
    run_descriptor: CodexDebugRunDescriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = run_descriptor.private_root.parent / "verify.py"
    _write_parent_verifier(verifier)
    descriptor = run_descriptor.model_copy(update={"verify_script": verifier})
    runner = CodexDebugRunner(timeout=10)

    def fake_process(
        _command: list[str],
        *,
        cwd: Path,
        **_kwargs: object,
    ) -> tuple[int, bool, str, str]:
        descriptor.top_rtl.write_text(EDITED_RTL, encoding="utf-8")
        return 0, False, "", ""

    monkeypatch.setattr(runner, "_run_process", fake_process)
    result = runner.run(descriptor)
    assert result.is_pass is False
    assert descriptor.top_rtl.read_text(encoding="utf-8") == INITIAL_RTL


def test_codex_runner_rejects_spec_or_out_of_scope_modification(
    run_descriptor: CodexDebugRunDescriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = run_descriptor.private_root.parent / "verify.py"
    _write_parent_verifier(verifier)
    descriptor = run_descriptor.model_copy(update={"verify_script": verifier})
    runner = CodexDebugRunner(timeout=10)

    def fake_process(
        _command: list[str],
        *,
        cwd: Path,
        **_kwargs: object,
    ) -> tuple[int, bool, str, str]:
        (descriptor.spec_root / "spec.md").write_text("changed", encoding="utf-8")
        (descriptor.task_root / "outside.txt").write_text("outside", encoding="utf-8")
        descriptor.top_rtl.write_text(EDITED_RTL, encoding="utf-8")
        return 0, False, "", ""

    monkeypatch.setattr(runner, "_run_process", fake_process)
    result = runner.run(descriptor)
    assert result.is_pass is False
    assert "outside merged RTL" in result.reason
    assert not (descriptor.task_root / "outside.txt").exists()
    assert descriptor.top_rtl.read_text(encoding="utf-8") == INITIAL_RTL


def test_codex_runner_preserves_accepted_rtl_on_scope_violation(
    run_descriptor: CodexDebugRunDescriptor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    verifier = run_descriptor.private_root.parent / "verify.py"
    _write_parent_verifier(verifier)
    descriptor = run_descriptor.model_copy(update={"verify_script": verifier})
    monkeypatch.setattr(
        session_module,
        "check_syntax",
        lambda *_args, **_kwargs: (True, "lint ok"),
    )
    runner = CodexDebugRunner(timeout=10)

    def fake_process(
        _command: list[str],
        *,
        cwd: Path,
        **_kwargs: object,
    ) -> tuple[int, bool, str, str]:
        del cwd
        session = CodexDebugSession.from_descriptor_path(
            descriptor.private_root / "run_descriptor.json",
            reviewer=FakeReviewer(
                descriptor.debug_workdir,
                results=[(True, 0, "Summary:\n  system_verify: PASS\n")],
            ),
        )
        try:
            descriptor.top_rtl.write_text(EDITED_RTL, encoding="utf-8")
            evaluated = session.validate_rtl_changes("evaluate")
            accepted = session.validate_rtl_changes(
                "accept",
                candidate_id=evaluated["candidate_id"],
            )
            assert accepted["status"] == "accepted"
        finally:
            session.close()

        # These changes are outside the accepted RTL transaction. They must
        # still fail the scope policy, but must not erase the accepted RTL.
        descriptor.top_rtl.write_text(SECOND_EDIT, encoding="utf-8")
        (descriptor.spec_root / "spec.md").write_text("changed", encoding="utf-8")
        (descriptor.task_root / "outside.txt").write_text("outside", encoding="utf-8")
        return 0, False, "", ""

    monkeypatch.setattr(runner, "_run_process", fake_process)
    result = runner.run(descriptor)

    assert result.is_pass is False
    assert "read-only spec tree changed" in result.reason
    assert "out-of-scope task path: outside.txt" in result.reason
    assert "parent verifier rejected" not in result.reason
    assert descriptor.top_rtl.read_text(encoding="utf-8") == EDITED_RTL
    assert not (descriptor.task_root / "outside.txt").exists()
    assert (descriptor.spec_root / "spec.md").read_text(encoding="utf-8").startswith("# top")
    report = json.loads(
        (descriptor.private_root / "scope_violation.json").read_text(encoding="utf-8")
    )
    assert report["violations"] == [
        "read-only spec tree changed",
        "out-of-scope task path: outside.txt",
    ]


def test_stdio_server_lists_tools(run_descriptor: CodexDebugRunDescriptor, tmp_path: Path) -> None:
    descriptor_path = tmp_path / "run_descriptor.json"
    descriptor_path.write_text(run_descriptor.model_dump_json(indent=2), encoding="utf-8")

    async def exercise() -> list[str]:
        params = StdioServerParameters(
            command=sys.executable,
            args=[
                "-m",
                "zerorepo.rtl_impl.codex_debug.mcp_server",
                "--run-descriptor",
                str(descriptor_path),
            ],
            cwd=str(Path(__file__).resolve().parents[1]),
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                response = await client.list_tools()
                return [tool.name for tool in response.tools]

    names = asyncio.run(exercise())
    assert names == [
        "read_module_semantics",
        "query_rtl_kg",
        "trace_signal_cause",
        "list_vcd_signals",
        "probe_vcd",
        "run_check",
        "validate_rtl_changes",
        "get_debug_status",
    ]
