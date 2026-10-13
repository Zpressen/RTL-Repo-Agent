"""Debug history survives process restarts, configuration errors and new RTL."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import tomllib

import pytest

from test_codex_debug_mcp import (
    FakeReviewer, INITIAL_RTL, EDITED_RTL, run_descriptor, isolated_codex_config_home,
    _write_parent_verifier,
)
from zerorepo.rtl_impl.codex_debug import session as session_module
from zerorepo.rtl_impl.codex_debug.history import DebugHistory, tree_manifest
from zerorepo.rtl_impl.codex_debug.runner import CodexDebugRunner
from zerorepo.rtl_impl.codex_debug.session import CodexDebugSession


def create_saved_history(descriptor):
    session = CodexDebugSession(descriptor, reviewer=FakeReviewer(descriptor.debug_workdir))
    session.close()
    (descriptor.private_root / "run_descriptor.json").write_text(descriptor.model_dump_json())
    status_path = descriptor.private_root / "debug_status.json"
    status = json.loads(status_path.read_text())
    status["codex_runtime"] = {"session_id": "same-session", "episode": 2}
    status_path.write_text(json.dumps(status))
    (descriptor.private_root / "run_record.json").write_text(json.dumps({"run_id": descriptor.run_id, "binding": {"source": "unchanged"}}))
    records = descriptor.private_root / "codex_home" / "sessions"
    records.mkdir(parents=True)
    (records / "rollout-same-session.jsonl").write_text("history\n")
    history = DebugHistory(descriptor.private_root.parent)
    history.private = descriptor.private_root
    history.task = descriptor.task_root
    return history


def test_same_sources_and_accepted_tree_resume_without_deleting_pending_history(run_descriptor, tmp_path):
    history = create_saved_history(run_descriptor)
    generated = tmp_path / "generated"
    shutil.copytree(run_descriptor.private_root / "accepted_baseline/merged", generated)
    run_descriptor.top_rtl.write_text(EDITED_RTL)
    result = history.select({"source": "unchanged"}, generated)
    assert result["runtime"]["session_id"] == "same-session"
    assert (run_descriptor.private_root / "codex_home/sessions/rollout-same-session.jsonl").read_text() == "history\n"
    assert not (history.workdir / "history").exists()


@pytest.mark.parametrize("change", ["rtl", "source", "accepted_corrupt", "missing_session", "state_corrupt", "counters", "spec"])
def test_incompatible_sessions_are_archived_with_reason_and_new_rtl_preserved(run_descriptor, tmp_path, change):
    history = create_saved_history(run_descriptor)
    generated = tmp_path / "generated"
    shutil.copytree(run_descriptor.private_root / "accepted_baseline/merged", generated)
    binding = {"source": "unchanged"}
    if change == "rtl":
        (generated / "top.v").write_text(EDITED_RTL)
    elif change == "source":
        binding["source"] = "changed"
    elif change == "accepted_corrupt":
        (run_descriptor.private_root / "accepted_baseline/merged/top.v").write_text("corrupt")
    elif change == "missing_session":
        (run_descriptor.private_root / "codex_home/sessions/rollout-same-session.jsonl").unlink()
    elif change == "state_corrupt":
        (run_descriptor.private_root / "session_state.json").write_text("{")
    elif change == "counters":
        path = run_descriptor.private_root / "session_state.json"
        state = json.loads(path.read_text()); state["counters"]["validation_trials"] = -1
        path.write_text(json.dumps(state))
    else:
        (run_descriptor.spec_root / "spec.md").write_text("Changed source")
    original = tree_manifest(generated)
    assert history.select(binding, generated) is None
    archive = next((history.workdir / "history").iterdir())
    assert (archive / "private/session_state.json").exists()
    assert json.loads((archive / "archive.json").read_text())["reason"]
    assert tree_manifest(generated) == original


def test_cross_launch_resume_inherits_validation_budget_and_appends_logs(run_descriptor, monkeypatch):
    verifier = run_descriptor.private_root.parent / "verify.py"
    _write_parent_verifier(verifier)
    descriptor = run_descriptor.model_copy(update={"verify_script": verifier})
    monkeypatch.setattr(session_module, "check_syntax", lambda *args, **kwargs: (True, "ok"))
    runner = CodexDebugRunner(timeout=10)
    commands = []
    def process(command, **kwargs):
        commands.append(command)
        current = CodexDebugSession.from_descriptor_path(descriptor.private_root / "run_descriptor.json",
            reviewer=FakeReviewer(descriptor.debug_workdir, results=[(len(commands) == 2, 0 if len(commands) == 2 else 1, "Summary:\n  system_verify: PASS\n" if len(commands) == 2 else "Summary:\n  system_verify: FAIL\n")]))
        try:
            descriptor.top_rtl.write_text(EDITED_RTL)
            result = current.validate_rtl_changes("evaluate")
            current.validate_rtl_changes("accept" if len(commands) == 2 else "rollback", candidate_id=result["candidate_id"])
        finally:
            current.close()
        return (1 if len(commands) == 1 else 0), False, '{"type":"thread.started","thread_id":"same-session"}\n', ""
    monkeypatch.setattr(runner, "_run_process", process)
    first = runner.run(descriptor)
    assert first.patch_attempts == 1
    marker = descriptor.private_root / "codex_home/sessions/keep-session.jsonl"
    marker.parent.mkdir(parents=True, exist_ok=True); marker.write_text("preserve")
    descriptor.top_rtl.write_text("unvalidated native edit")
    resumed = descriptor.model_copy(update={"codex_session_id": "same-session", "codex_episode": 2})
    second = runner.run(resumed)
    assert second.is_pass and second.patch_attempts == 2
    assert commands[1][:3] == ["codex", "exec", "resume"] and commands[1][-2] == "same-session"
    assert marker.read_text() == "preserve"
    assert (descriptor.private_root / "codex_trace_episode_001.jsonl").exists() is False  # mocked process owns per-episode output
    assert (descriptor.private_root / "codex_trace.jsonl").read_text().count('"thread.started"') == 2
    effective = tomllib.loads((descriptor.private_root / "codex_home/config.toml").read_text())
    assert effective["model_provider"] == "test_proxy" and effective["model"] == "profile-model"


def test_exhausted_validation_budget_does_not_start_another_process(run_descriptor, monkeypatch):
    verifier = run_descriptor.private_root.parent / "verify.py"
    _write_parent_verifier(verifier)
    descriptor = run_descriptor.model_copy(update={"verify_script": verifier, "max_validation_trials": 1})
    current = CodexDebugSession(descriptor, reviewer=FakeReviewer(descriptor.debug_workdir))
    monkeypatch.setattr(session_module, "check_syntax", lambda *args, **kwargs: (True, "ok"))
    descriptor.top_rtl.write_text(EDITED_RTL)
    result = current.validate_rtl_changes("evaluate")
    current.validate_rtl_changes("rollback", candidate_id=result["candidate_id"])
    current.close()
    runner = CodexDebugRunner(timeout=10)
    monkeypatch.setattr(runner, "_run_process", lambda *args, **kwargs: pytest.fail("Budget reset on resume"))
    result = runner.run(descriptor.model_copy(update={"codex_session_id": "same-session", "codex_episode": 2}))
    assert result.patch_attempts == 1 and not result.is_pass


def test_auth_preflight_preserves_session_storage_and_existing_log(run_descriptor, monkeypatch):
    runner = CodexDebugRunner(timeout=10)
    home = runner._prepare_private_codex_home(run_descriptor.private_root)
    marker = home / "sessions/keep.jsonl"
    marker.parent.mkdir(); marker.write_text("history")
    log = run_descriptor.private_root / "codex_stderr.log"
    log.write_text("previous failure\n")
    monkeypatch.delenv("ZEROREPO_TEST_CODEX_API_KEY")
    with pytest.raises(RuntimeError, match="ZEROREPO_TEST_CODEX_API_KEY"):
        runner.run(run_descriptor)
    assert marker.read_text() == "history"
    assert log.read_text().startswith("previous failure\n")


@pytest.mark.parametrize("legacy", [False, True])
def test_changed_provider_defaults_fail_without_overwriting_saved_session(run_descriptor, monkeypatch, legacy):
    import os
    runner = CodexDebugRunner(timeout=10)
    home = runner._prepare_private_codex_home(run_descriptor.private_root)
    marker = home / "sessions/keep.jsonl"
    marker.parent.mkdir(); marker.write_text("saved session")
    if legacy:
        (home / "provider_binding.json").unlink()
    saved_config = (home / "config.toml").read_bytes()
    profile = Path(os.environ["CODEX_HOME"]) / f"{runner.profile}.config.toml"
    profile.write_text(profile.read_text().replace("profile-model", "different-model"))
    with pytest.raises(RuntimeError, match="saved session|configuration changed"):
        runner.run(run_descriptor)
    assert (home / "config.toml").read_bytes() == saved_config
    assert marker.read_text() == "saved session"


def test_interrupted_parent_terminates_only_its_owned_codex_process(run_descriptor, monkeypatch):
    import io
    import signal
    calls = []
    class Process:
        pid = 123456
        stdout = io.StringIO("")
        stderr = io.StringIO("")
        returncode = None
        waits = 0
        def wait(self, **kwargs):
            self.waits += 1
            if self.waits == 1:
                raise KeyboardInterrupt()
            self.returncode = 0
            return 0
    monkeypatch.setattr("zerorepo.rtl_impl.codex_debug.runner.subprocess.Popen", lambda *args, **kwargs: Process())
    monkeypatch.setattr("zerorepo.rtl_impl.codex_debug.runner.os.killpg", lambda pid, sig: calls.append((pid, sig)))
    with pytest.raises(KeyboardInterrupt):
        CodexDebugRunner()._run_process(["mock-codex"], cwd=run_descriptor.task_root)
    assert calls == [(123456, signal.SIGTERM)]


def test_live_thread_id_is_durable_before_episode_finishes(run_descriptor, monkeypatch):
    import io
    descriptor_path = run_descriptor.private_root / "run_descriptor.json"
    descriptor_path.write_text(run_descriptor.model_dump_json())
    class Process:
        stdout = io.StringIO('{"type":"thread.started","thread_id":"live-session"}\n')
        stderr = io.StringIO("")
        returncode = 0
        def wait(self, **kwargs):
            return 0
    monkeypatch.setattr("zerorepo.rtl_impl.codex_debug.runner.subprocess.Popen", lambda *args, **kwargs: Process())
    CodexDebugRunner()._run_process(["mock-codex"], cwd=run_descriptor.task_root,
        tee_path=run_descriptor.private_root / "codex_trace_episode_001.jsonl")
    runtime = json.loads((run_descriptor.private_root / "active_runtime.json").read_text())
    assert runtime["session_id"] == "live-session" and runtime["episode"] == 1
    assert json.loads(descriptor_path.read_text())["codex_session_id"] == "live-session"


def test_each_system_invocation_grants_30_more_with_cumulative_history(tmp_path,monkeypatch):
    from types import SimpleNamespace
    from zerorepo.rtl_impl.debug_agent.system_debug_runner import SystemDebugRunner
    from zerorepo.rtl_impl.debug_agent.debug_runner import RtlDebugConfig
    from zerorepo.rtl_impl.repo_react.schemas import RepoReActResult
    workdir=tmp_path/'system';generated=workdir/'generated';generated.mkdir(parents=True)
    (generated/'top.v').write_text(INITIAL_RTL)
    spec=tmp_path/'source.md';spec.write_text('top specification\n')
    verifier=tmp_path/'oracle/verify.py';verifier.parent.mkdir()
    verifier.write_text('def verify_system(path): return False, "FAIL"\n')
    descriptors=[];totals=[30,44,74]
    def fake_run(self,descriptor,**kwargs):
        descriptors.append(descriptor)
        session=CodexDebugSession(descriptor,reviewer=FakeReviewer(descriptor.debug_workdir))
        session.validation_trials=totals[len(descriptors)-1]
        session._persist_session_state()
        status=session.get_debug_status(count_read=False)
        session.close()
        status['codex_runtime']={'session_id':'same-session','episode':descriptor.codex_episode}
        (descriptor.private_root/'debug_status.json').write_text(json.dumps(status))
        (descriptor.private_root/'run_descriptor.json').write_text(descriptor.model_dump_json())
        records=descriptor.private_root/'codex_home/sessions';records.mkdir(parents=True,exist_ok=True)
        with (records/'rollout-same-session.jsonl').open('a') as f:f.write(f'episode {descriptor.codex_episode}\n')
        return RepoReActResult(status='fail',is_pass=False,patch_attempts=session.validation_trials,mismatch_count=1)
    monkeypatch.setattr(CodexDebugRunner,'run',fake_run)
    runner=SystemDebugRunner(config=RtlDebugConfig(max_trials=30),workspace_root=tmp_path/'workspace',output_root=tmp_path/'outputs')
    used=[]
    for _ in range(3):
        _,trials=runner._run_codex_debug(planner_top_module='top',runtime_top_module='top',task=SimpleNamespace(spec_md_files=[str(spec)]),
            spec_text='top specification',contract_json='{}',workdir=workdir,generated_dir=generated,
            verify_script=verifier,sim_output='Summary:\n  system_verify: FAIL\n',mismatch_count=1)
        used.append(trials)
    assert used==[30,14,30]
    assert [(d.validation_trial_offset,d.max_validation_trials) for d in descriptors]==[(0,30),(30,60),(44,74)]
    assert len({d.run_id for d in descriptors})==1
    assert [d.codex_episode for d in descriptors]==[1,2,3]
    assert descriptors[-1].codex_session_id=='same-session'
    private=workdir/'codex_private'
    assert json.loads((private/'session_state.json').read_text())['counters']['validation_trials']==74
    status=json.loads((private/'debug_status.json').read_text())
    assert status['budgets']['validation_trials_this_launch']==30
    assert status['budgets']['remaining_validation_trials']==0
    assert len(list((private/'launches').glob('*.json')))==3
    assert (private/'codex_home/sessions/rollout-same-session.jsonl').read_text().count('episode')==3
