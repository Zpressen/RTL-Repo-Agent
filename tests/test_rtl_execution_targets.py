"""Cumulative CLI stop targets and continuation through module syntax repair."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from main import _run_rtl_planner_case, parse_args
from rtl_artifact_test_utils import write_artifact_text
from test_responsibility_refinement import scenario
from test_rtl_module_planner import (
    QueueBackend, make_stage4_module_plan_payload, make_stage5_code_payload,
    make_stage6_module_code, make_merge_context_retrieval_payload,
)
from zerorepo.rtl_impl.artifact_layout import ArtifactLayout
from zerorepo.rtl_impl.debug_agent.debug_runner import RtlDebugConfig
from zerorepo.rtl_impl.module_planner import PlannerRunner
from zerorepo.rtl_impl.module_planner.schemas import ModuleCodegenRecord, SystemDebugRecord
from zerorepo.rtl_impl.module_planner.utils.local_repair import fingerprint


def cli_args(monkeypatch, flags):
    monkeypatch.setattr(sys, "argv", ["main.py", "--config", "config.yaml", "--checkpoint", "state",
                                    "--repo", "case", *flags])
    return parse_args()


@pytest.mark.parametrize("flag,target", [(None, None), ("--plan", "plan"), ("--generate", "generate")])
def test_cli_stop_targets(monkeypatch, flag, target):
    args = cli_args(monkeypatch, ["--phase", "rtl_planner", *([flag] if flag else [])])
    assert args.rtl_stop_after == target


@pytest.mark.parametrize("flags", [
    ["--phase", "rtl_planner", "--plan", "--generate"],
    ["--plan"], ["--phase", "rtl", "--generate"],
    ["--phase", "design", "--plan"],
])
def test_cli_rejects_conflicting_or_nonplanner_targets(monkeypatch, flags):
    with pytest.raises(SystemExit) as exc:
        cli_args(monkeypatch, flags)
    assert exc.value.code == 2


@pytest.fixture
def script_dispatch(tmp_path):
    source = Path(__file__).resolve().parents[1] / "scripts/run_main.sh"
    script = tmp_path / "project/scripts/run_main.sh"
    script.parent.mkdir(parents=True)
    shutil.copyfile(source, script)
    binary = tmp_path / "bin/python"
    write_artifact_text(binary, '#!/bin/sh\nprintf "%s\\n" "$@" > "$RTL_DISPATCH_ARGS"\n')
    binary.chmod(0o755)
    captured = tmp_path / "args"

    def dispatch(arguments, mode="planner"):
        env = {**os.environ, "PATH": str(binary.parent) + os.pathsep + os.environ["PATH"],
               "RTL_DISPATCH_ARGS": str(captured), "RTL_PIPELINE_MODE": mode}
        result = subprocess.run(["bash", str(script), *arguments], env=env, capture_output=True, text=True)
        return result, captured.read_text().splitlines() if captured.exists() else []

    return dispatch


@pytest.mark.parametrize("flag", ["--plan", "--generate"])
@pytest.mark.parametrize("position", ["before", "after", "batch"])
def test_script_forwards_target_and_preserves_default_resume(script_dispatch, flag, position):
    arguments = {"before": [flag, "toy"], "after": ["toy", flag], "batch": [flag]}[position]
    result, args = script_dispatch(arguments)
    assert result.returncode == 0, result.stderr
    assert flag in args and "--resume" in args
    assert ("--rtl-spec" in args) == (position != "batch")
    if position != "batch":
        assert args[args.index("--rtl-spec") + 1] == "toy"


@pytest.mark.parametrize("arguments", [["--plan", "--generate"], ["a", "b"], ["--unknown"], ["--plan", "--plan"]])
def test_script_rejects_invalid_arguments(script_dispatch, arguments):
    result, args = script_dispatch(arguments)
    assert result.returncode == 2 and not args


def test_script_rejects_stop_target_in_legacy_mode(script_dispatch):
    result, args = script_dispatch(["--generate"], mode="legacy")
    assert result.returncode == 2 and not args


@pytest.mark.parametrize("target,end_stage,system_debug", [("plan", "stage4", True), ("generate", "stage6", False), (None, "stage6", True)])
def test_cli_dispatch_and_summary(tmp_path, caplog, target, end_stage, system_debug):
    # Stage4 deliberately has no status or module_files fields.
    result = SimpleNamespace() if target == "plan" else SimpleNamespace(
        status="completed", module_files=[], debug_files=[SimpleNamespace(module="toy", status="fail")])
    runner = SimpleNamespace(layout=ArtifactLayout(tmp_path), run=Mock(return_value=result))
    args = SimpleNamespace(rtl_stop_after=target, resume=True, force_rebuild=False)
    with caplog.at_level(logging.INFO):
        assert _run_rtl_planner_case(runner, "task", args, logging.getLogger("dispatch"), "toy") is result
    runner.run.assert_called_once_with("task", resume=True, end_stage=end_stage,
                                       force_rebuild=False, run_system_debug=system_debug)
    if target == "plan":
        assert "Stage4 planning gate passed" in caplog.text
        assert "final RTL" not in caplog.text
    else:
        assert "awaiting syntax repair: toy" in caplog.text
    if target == "generate":
        assert "system debug skipped by request" in caplog.text


def test_cli_does_not_tolerate_codegen_or_merge_failure(tmp_path):
    result = SimpleNamespace(status="failed", module_files=[SimpleNamespace(module="toy", status="failed", error="merge failed")])
    runner = SimpleNamespace(layout=ArtifactLayout(tmp_path), run=Mock(return_value=result))
    args = SimpleNamespace(rtl_stop_after="generate", resume=True, force_rebuild=False)
    with pytest.raises(RuntimeError, match="toy: merge failed"):
        _run_rtl_planner_case(runner, "task", args, logging.getLogger("dispatch"), "toy")


def test_plan_boundary_saves_gate_without_generation(tmp_path, monkeypatch):
    def configure(runner):
        for agent, method in ((runner.stage5, "run_module"), (runner.stage6, "run_module"),
                              (runner.system_debug_runner, "run_system")):
            monkeypatch.setattr(agent, method, lambda *a, **k: pytest.fail("executed past planning boundary"))

    _, runner, *_ = scenario(tmp_path, before_run=configure)
    assert json.loads(runner.layout.artifact("planning_gate_report.json").read_text())["status"] == "passed"
    assert not runner.layout.artifact("stage5_codegen.json").exists()
    assert not runner.layout.artifact("stage6_merge.json").exists()


def test_plan_generate_then_full_resume_retries_syntax_without_remerging(tmp_path, monkeypatch):
    task, planner, backend, *_ = scenario(tmp_path)
    # Append only the generation responses: planning must be reused.
    for name in ("aes_key_expand_128", "aes_cipher_top"):
        plan = make_stage4_module_plan_payload(name, top_module=name == "aes_cipher_top")
        backend.responses.extend(make_stage5_code_payload(task.task_id, name, subtask) for subtask in plan["subtasks"])
        backend.responses.extend([make_merge_context_retrieval_payload(name), make_stage6_module_code(name)])
    repairs = []
    checks = []
    system_calls = []
    monkeypatch.setattr("zerorepo.rtl_impl.module_planner.agents.stage6_merge_agent.check_syntax", lambda *a, **k: (True, "ok"))
    monkeypatch.setattr(planner.stage6, "_ensure_toolchain_path", lambda: None)
    monkeypatch.setattr(planner.debug_runner, "_ensure_toolchain_path", lambda: None)

    def syntax(_path, top_module=None):
        checks.append(top_module)
        return (top_module != "aes_key_expand_128", "syntax diagnosis")

    def repair(**kwargs):
        repairs.append((kwargs["module_name"], planner.debug_runner.pre_debug_syntax_max_attempts))
        # First invocation consumes its budget. The next run gets a new budget.
        return len(repairs) > 1, (kwargs["workdir"] / "rtl.sv").read_text(), repairs[-1][1]

    monkeypatch.setattr("zerorepo.rtl_impl.debug_agent.debug_runner.check_syntax", syntax)
    monkeypatch.setattr(planner.debug_runner, "_run_repo_react_syntax_repair", repair)
    monkeypatch.setattr(planner.system_debug_runner, "run_system", lambda **k: pytest.fail("system debug ran at generate boundary"))
    latest = planner.layout.artifact("system_debug_latest.json")
    write_artifact_text(latest, json.dumps({"top_module": "aes_cipher_top", "status": "fail", "debug_trials": 7}))
    old_latest = latest.read_bytes()
    result = planner.run(task, resume=True, end_stage="stage6", run_system_debug=False)
    assert result.status == "completed"
    assert [r.status for r in result.debug_files] == ["fail", "pass"]
    assert checks == ["aes_key_expand_128", "aes_cipher_top"]
    assert result.system_debug.status == "skipped" and "--generate" in result.system_debug.reason
    assert result.latest_system_debug is None and latest.read_bytes() == old_latest
    for name in ("stage5_codegen.json", "stage6_merge.json", "planning_code_consistency.json"):
        assert planner.layout.artifact(name).is_file()
    persisted = json.loads(planner.layout.artifact("stage6_merge.json").read_text())
    assert persisted["debug_files"][0]["status"] == "fail"
    assert persisted["latest_system_debug"] is None
    assert not planner.layout.cache("pending_debug_generation.json").exists()
    calls_after_generate = len(backend.calls)

    # Resume must feed the failed, source-bound merged RTL directly to repair.
    monkeypatch.setattr(planner.stage6, "run_module", lambda *a, **k: pytest.fail("unchanged module remerged"))
    monkeypatch.setattr("zerorepo.rtl_impl.module_planner.planner_runner._check_single_file_syntax",
                        lambda *a, **k: pytest.fail("pending syntax incorrectly used as cache rejection"))

    def system(**kwargs):
        system_calls.append(kwargs["top_module"])
        return SystemDebugRecord(top_module=kwargs["top_module"], status="pass")

    monkeypatch.setattr(planner.system_debug_runner, "run_system", system)
    result = planner.run(task, resume=True, end_stage="stage6")
    assert len(backend.calls) == calls_after_generate and not backend.responses
    assert [r.status for r in result.debug_files] == ["fixed", "pass"]
    assert repairs == [("aes_key_expand_128", 5), ("aes_key_expand_128", 5)]
    assert system_calls == ["aes_cipher_top"] and result.system_debug.status == "pass"


@pytest.mark.parametrize("change", [None, "fragment", "rtl", "skeleton", "dependency"])
def test_pending_syntax_reuse_requires_exact_source_and_content_binding(tmp_path, monkeypatch, change):
    runner = PlannerRunner(output_root=tmp_path / "case", llm_backend=QueueBackend([]))
    fragment = runner.stage5._workspace_file("toy")
    merged = runner.stage6._merged_file("toy")
    skeleton = runner.output_root / "skeleton.json"
    child = runner.stage6._merged_file("child")
    for path, text in ((fragment, "fragment"), (merged, "invalid syntax"), (skeleton, "behavior"), (child, "child code")):
        write_artifact_text(path, text)
    record = ModuleCodegenRecord(module="toy", workspace_file=str(fragment))
    inputs = {"stage2": SimpleNamespace(modules=[SimpleNamespace(module="toy", children=["child"])]),
              "stage3": SimpleNamespace(module_records=[SimpleNamespace(module="toy", export_file=str(skeleton))])}
    write_artifact_text(runner._stage6_cache_path("toy"), json.dumps({
        "input_fingerprint": runner._stage6_reuse_key("toy", record, inputs),
        "merged_fingerprint": fingerprint(merged.read_text()),
    }))
    monkeypatch.setattr(runner.stage6, "_ensure_toolchain_path", lambda: None)
    monkeypatch.setattr("zerorepo.rtl_impl.module_planner.planner_runner._check_single_file_syntax", lambda *a, **k: (False, "syntax"))
    assert runner._reuse_stage6_merge_if_valid("toy", record, inputs) is None  # strict default unchanged
    if change:
        path = {"fragment": fragment, "rtl": merged, "skeleton": skeleton, "dependency": child}[change]
        write_artifact_text(path, path.read_text() + " changed")
    result = runner._reuse_stage6_merge_if_valid("toy", record, inputs, allow_pending_syntax=True)
    assert (result is not None) == (change is None)


def test_generation_boundary_reports_disabled_syntax_as_disabled(tmp_path, monkeypatch):
    task, runner, *_ = scenario(tmp_path, end_stage="stage6", before_run=lambda r: (
        setattr(r.debug_runner, "config", RtlDebugConfig(enabled=False)),
        setattr(r.system_debug_runner, "config", RtlDebugConfig(enabled=False)),
    ))
    monkeypatch.setattr("zerorepo.rtl_impl.module_planner.planner_runner._check_single_file_syntax", lambda *a, **k: (True, "ok"))
    result = runner.run(task, resume=True, end_stage="stage6", run_system_debug=False)
    assert all(record.status == "disabled" for record in result.debug_files)
    assert result.system_debug.status == "skipped"
