from __future__ import annotations

import json
from pathlib import Path
from rtl_artifact_test_utils import write_artifact_text
from zerorepo.rtl_impl.artifact_layout import artifact_dir
from types import SimpleNamespace

import pytest
import yaml

from zerorepo.rtl_impl.debug_agent.config import OpenAIConfig
from zerorepo.rtl_impl.debug_agent.debug_runner import RtlDebugConfig
from zerorepo.rtl_impl.debug_agent.system_debug_runner import SystemDebugRunner
from zerorepo.rtl_impl.repo_react.schemas import RepoReActResult


def _write_system_oracle(tmp_path: Path, top_module: str, body: str) -> Path:
    verify_dir = tmp_path / "oracle" / "system_task" / top_module / "verify_test"
    verify_dir.mkdir(parents=True)
    write_artifact_text(verify_dir / f"{top_module}_testbench.sv", "module tb; endmodule\n", encoding="utf-8")
    write_artifact_text(verify_dir / f"{top_module}_verify.py", body, encoding="utf-8")
    return verify_dir


def test_rtl_debug_config_loads_codex_settings_from_main_yaml(monkeypatch: object) -> None:
    for name in (
        "ZEROREPO_RTL_DEBUG_BACKEND",
        "ZEROREPO_RTL_DEBUG_MAX_TRIALS",
        "ZEROREPO_CODEX_PROFILE",
        "ZEROREPO_CODEX_TIMEOUT",
        "ZEROREPO_CODEX_MULTI_AGENT",
    ):
        monkeypatch.delenv(name, raising=False)
    root = Path(__file__).resolve().parents[1]
    config = yaml.safe_load((root / "configs" / "zerorepo_config.yaml").read_text(encoding="utf-8"))
    debug = RtlDebugConfig.from_mapping(config["rtl_debug"], openai_config=OpenAIConfig())
    assert debug.backend == "codex"
    assert debug.max_trials == 30
    assert debug.codex_profile == "proxy-a"
    assert debug.codex_model == ""
    assert debug.codex_timeout == 10800
    assert debug.codex_multi_agent is False


def test_rtl_debug_environment_can_override_yaml_for_one_run(monkeypatch: object) -> None:
    monkeypatch.setenv("ZEROREPO_RTL_DEBUG_BACKEND", "repo_react")
    monkeypatch.setenv("ZEROREPO_RTL_DEBUG_MAX_TRIALS", "7")
    monkeypatch.setenv("ZEROREPO_CODEX_PROFILE", "proxy-test")
    monkeypatch.setenv("ZEROREPO_CODEX_MULTI_AGENT", "true")
    debug = RtlDebugConfig.from_mapping(
        {"backend": "codex", "max_trials": 30},
        openai_config=OpenAIConfig(),
    )
    assert debug.backend == "repo_react"
    assert debug.max_trials == 7
    assert debug.codex_profile == "proxy-test"
    assert debug.codex_multi_agent is True


def _write_workspace(tmp_path: Path, top_module: str) -> tuple[Path, list[SimpleNamespace]]:
    workspace = tmp_path / "workspace"
    merged = artifact_dir(workspace, "merged")
    merged.mkdir(parents=True)
    top_file = merged / f"{top_module}.v"
    write_artifact_text(top_file, "module top(output y);\nassign y = 1'b0;\nendmodule\n", encoding="utf-8")
    return workspace, [SimpleNamespace(module=top_module, merged_file=str(top_file))]


def test_system_debug_runner_discovers_verifier_and_records_pass(tmp_path: Path) -> None:
    top_module = "top"
    _write_system_oracle(
        tmp_path,
        top_module,
        "def verify_system(generated_dir):\n    print('Verifying', generated_dir)\n    return True, 'Passed'\n",
    )
    workspace, records = _write_workspace(tmp_path, top_module)
    runner = SystemDebugRunner(
        config=RtlDebugConfig(oracle_root=str(tmp_path / "oracle"), openai_config=None),
        workspace_root=workspace,
        output_root=tmp_path / "outputs",
    )

    result = runner.run_system(
        top_module=top_module,
        task=SimpleNamespace(spec_md_files=[]),
        spec_text="spec",
        contract_json='{"module_name":"top"}',
        merged_records=records,
    )

    assert result.status == "pass"
    assert result.verify_dir.endswith("verify_test")
    assert result.verify_script.endswith("_verify.py")
    assert (Path(result.workdir) / "tb.sv").exists()
    assert Path(result.generated_dir, "top.v").exists()


def test_system_workdir_reset_preserves_codex_session_and_archived_runs(tmp_path: Path) -> None:
    _write_system_oracle(tmp_path, "top", "def verify_system(generated_dir):\n    return True, 'Passed'\n")
    workspace, records = _write_workspace(tmp_path, "top")
    runner = SystemDebugRunner(config=RtlDebugConfig(oracle_root=str(tmp_path / "oracle"), openai_config=None),
        workspace_root=workspace, output_root=tmp_path / "outputs")
    module_root = runner.debug_root / "top"
    workdir = module_root / "simulation"
    workdir.mkdir(parents=True)
    preserved = {}
    for relative in ["state/codex_private/session_state.json", "candidates/codex_task/merged/top.v",
                     "state/history/old-run/journal.jsonl", "reports/latest_debug_result.json"]:
        path = module_root / relative; path.parent.mkdir(parents=True, exist_ok=True)
        write_artifact_text(path, "preserved " + relative); preserved[path] = path.read_bytes()
    scratch = workdir / "scratch-old.txt"; write_artifact_text(scratch, "stale")
    generated = module_root / "candidates/generated"; generated.mkdir(parents=True, exist_ok=True); write_artifact_text(generated / "obsolete.v", "stale")
    result = runner.run_system(top_module="top", task=SimpleNamespace(spec_md_files=[]), spec_text="spec",
        contract_json='{"module_name":"top"}', merged_records=records)
    assert result.status == "pass"
    assert all(path.read_bytes() == value for path, value in preserved.items())
    assert not scratch.exists() and not (generated / "obsolete.v").exists()


@pytest.mark.parametrize(
    ("project", "top_module"),
    [
        ("e203_ifu_hard", "e203_ifu"),
        ("e203_exu_alu_hard", "e203_exu_alu"),
    ],
)
def test_system_debug_runner_uses_dataset_project_to_locate_verifier(
    tmp_path: Path,
    project: str,
    top_module: str,
) -> None:
    verify_dir = tmp_path / "oracle" / "system_task" / project / "verify_test"
    verify_dir.mkdir(parents=True)
    write_artifact_text(verify_dir / f"{project}_testbench.sv",
        f"module tb; {top_module} dut(); endmodule\n",
        encoding="utf-8",
    )
    write_artifact_text(verify_dir / f"{project}_verify.py",
        "def verify_system(generated_dir):\n    return True, 'Passed'\n",
        encoding="utf-8",
    )
    workspace, records = _write_workspace(tmp_path, top_module)
    write_artifact_text(artifact_dir(workspace, "merged") / f"{top_module}.v",
        f"module {top_module}; endmodule\n",
        encoding="utf-8",
    )
    spec_path = tmp_path / "rtl_dataset" / project / f"{top_module}_system.md"
    spec_path.parent.mkdir(parents=True)
    write_artifact_text(spec_path, "# spec\n", encoding="utf-8")
    runner = SystemDebugRunner(
        config=RtlDebugConfig(oracle_root=str(tmp_path / "oracle"), openai_config=None),
        workspace_root=workspace,
        output_root=tmp_path / "outputs",
    )

    result = runner.run_system(
        top_module=top_module,
        task=SimpleNamespace(spec_md_files=[spec_path]),
        spec_text="spec",
        contract_json=json.dumps({"module_name": top_module}),
        merged_records=records,
    )

    assert result.status == "pass"
    assert Path(result.verify_dir) == verify_dir
    assert result.top_module == top_module


def test_system_debug_runner_accepts_system_suffixed_planner_top(tmp_path: Path) -> None:
    planner_top = "e203_exu_alu_system"
    runtime_top = "e203_exu_alu"
    project = "e203_exu_alu_hard"
    verify_dir = tmp_path / "oracle" / "system_task" / project / "verify_test"
    verify_dir.mkdir(parents=True)
    write_artifact_text(verify_dir / "e203_exu_alu_testbench.sv",
        f"module tb; {runtime_top} top_module1(); endmodule\n",
        encoding="utf-8",
    )
    write_artifact_text(verify_dir / "e203_exu_alu_system_verify.py",
        "from pathlib import Path\n"
        "SCRIPT_DIR = str(Path(__file__).parent)\n"
        "TESTBENCH_FILE = 'e203_exu_alu_testbench.sv'\n"
        "def verify_system(generated_dir):\n"
        "    generated = Path(generated_dir)\n"
        "    system_rtl = generated / 'e203_exu_alu_system.v'\n"
        "    forbidden_alias = generated / 'e203_exu_alu.v'\n"
        "    tb = Path(SCRIPT_DIR, TESTBENCH_FILE).read_text()\n"
        "    passed = (system_rtl.is_file() and not forbidden_alias.exists()\n"
        "              and 'module e203_exu_alu_system(' in system_rtl.read_text()\n"
        "              and 'e203_exu_alu_system top_module1(' in tb)\n"
        "    return passed, 'Passed' if passed else 'Missing simulation-only TB alias'\n",
        encoding="utf-8",
    )
    workspace, records = _write_workspace(tmp_path, planner_top)
    write_artifact_text(artifact_dir(workspace, "merged") / f"{planner_top}.v",
        f"module {planner_top}(output y); assign y = 1'b0; endmodule\n",
        encoding="utf-8",
    )
    spec_path = tmp_path / "rtl_dataset" / project / f"{planner_top}.md"
    spec_path.parent.mkdir(parents=True)
    write_artifact_text(spec_path, "# spec\n", encoding="utf-8")
    runner = SystemDebugRunner(
        config=RtlDebugConfig(oracle_root=str(tmp_path / "oracle"), openai_config=None),
        workspace_root=workspace,
        output_root=tmp_path / "outputs",
    )

    result = runner.run_system(
        top_module=planner_top,
        task=SimpleNamespace(spec_md_files=[spec_path]),
        spec_text="spec",
        contract_json=json.dumps({"module_name": planner_top}),
        merged_records=records,
    )

    assert result.status == "pass"
    assert result.planner_top_module == planner_top
    assert result.top_module == planner_top
    assert result.dut_instance == "top_module1"
    assert Path(result.runtime_rtl_path).name == f"{planner_top}.v"
    assert not (Path(result.generated_dir) / f"{runtime_top}.v").exists()
    manifest = json.loads(
        (Path(result.workdir) / "debug_input_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["runtime_top_alias_of"] == ""
    assert manifest["testbench_dut_module"] == runtime_top
    assert manifest["simulation_module_aliases"] == {runtime_top: planner_top}
    patched_tb = (
        Path(result.workdir)
        / "simulation_compat"
        / "verify_files"
        / "e203_exu_alu_testbench.sv"
    )
    assert f"{planner_top} top_module1(" in patched_tb.read_text(encoding="utf-8")
    assert f"{runtime_top} top_module1(" in (
        verify_dir / "e203_exu_alu_testbench.sv"
    ).read_text(encoding="utf-8")


def test_system_debug_runner_missing_verifier_is_error_not_module_fallback(tmp_path: Path) -> None:
    top_module = "top"
    workspace, records = _write_workspace(tmp_path, top_module)
    runner = SystemDebugRunner(
        config=RtlDebugConfig(oracle_root=str(tmp_path / "oracle"), openai_config=None),
        workspace_root=workspace,
        output_root=tmp_path / "outputs",
    )

    result = runner.run_system(
        top_module=top_module,
        task=SimpleNamespace(spec_md_files=[]),
        spec_text="spec",
        contract_json='{"module_name":"top"}',
        merged_records=records,
    )

    assert result.status == "error"
    assert "system_task/top/verify_test" in result.reason


def test_system_debug_runner_uses_merged_simulation_top_alias(tmp_path: Path) -> None:
    planner_top = "planned_system"
    simulation_top = "actual_top"
    verify_dir = _write_system_oracle(
        tmp_path,
        simulation_top,
        "def verify_system(generated_dir):\n    return True, 'Passed'\n",
    )
    write_artifact_text(verify_dir / f"{simulation_top}_testbench.sv",
        f"module tb; {simulation_top} top_module1(); endmodule\n",
        encoding="utf-8",
    )
    workspace, records = _write_workspace(tmp_path, planner_top)
    alias_file = artifact_dir(workspace, "merged") / f"{simulation_top}.v"
    write_artifact_text(alias_file,
        f"module {simulation_top}(output y);\nassign y = 1'b0;\nendmodule\n",
        encoding="utf-8",
    )
    runner = SystemDebugRunner(
        config=RtlDebugConfig(oracle_root=str(tmp_path / "oracle"), openai_config=None),
        workspace_root=workspace,
        output_root=tmp_path / "outputs",
    )

    result = runner.run_system(
        top_module=planner_top,
        task=SimpleNamespace(spec_md_files=[]),
        spec_text="spec",
        contract_json='{"module_name":"planned_system"}',
        merged_records=records,
    )

    assert result.status == "pass"
    assert result.top_module == simulation_top
    assert result.planner_top_module == planner_top
    assert result.dut_instance == "top_module1"
    assert Path(result.runtime_rtl_path).name == f"{simulation_top}.v"
    assert Path(result.generated_dir, f"{simulation_top}.v").exists()
    manifest = json.loads((Path(result.workdir) / "debug_input_manifest.json").read_text(encoding="utf-8"))
    assert manifest["planner_module_name"] == planner_top
    assert manifest["runtime_top_module"] == simulation_top
    assert manifest["dut_instance"] == "top_module1"
    assert Path(manifest["runtime_rtl_path"]).name == f"{simulation_top}.v"


def test_system_debug_runner_passes_logical_and_runtime_identity_to_repo_react(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    planner_top = "planned_system"
    simulation_top = "actual_top"
    verify_dir = _write_system_oracle(
        tmp_path,
        simulation_top,
        "def verify_system(generated_dir):\n    return False, 'Mismatches: 1 in 1 samples'\n",
    )
    write_artifact_text(verify_dir / f"{simulation_top}_testbench.sv",
        f"module tb; {simulation_top} top_module1(); endmodule\n",
        encoding="utf-8",
    )
    workspace, records = _write_workspace(tmp_path, planner_top)
    write_artifact_text(artifact_dir(workspace, "merged") / f"{simulation_top}.v",
        f"module {simulation_top}(output y); assign y = 1'b0; endmodule\n",
        encoding="utf-8",
    )
    runner = SystemDebugRunner(
        config=RtlDebugConfig(oracle_root=str(tmp_path / "oracle"), openai_config=None),
        workspace_root=workspace,
        output_root=tmp_path / "outputs",
    )
    captured: dict[str, object] = {}

    def fake_react(**kwargs: object) -> tuple[bool, int]:
        captured.update(kwargs)
        return False, 1

    monkeypatch.setattr(runner, "_run_repo_react", fake_react)

    result = runner.run_system(
        top_module=planner_top,
        task=SimpleNamespace(spec_md_files=[]),
        spec_text="spec",
        contract_json='{"module_name":"planned_system"}',
        merged_records=records,
    )

    assert result.status == "fail"
    assert captured["planner_top_module"] == planner_top
    assert captured["runtime_top_module"] == simulation_top
    assert result.planner_top_module == planner_top
    assert result.top_module == simulation_top


def test_system_debug_runner_rejects_ambiguous_runtime_aliases(tmp_path: Path) -> None:
    planner_top = "planned_system"
    workspace, records = _write_workspace(tmp_path, planner_top)
    for simulation_top in ("actual_top_a", "actual_top_b"):
        _write_system_oracle(
            tmp_path,
            simulation_top,
            "def verify_system(generated_dir):\n    return True, 'Passed'\n",
        )
        write_artifact_text(artifact_dir(workspace, "merged") / f"{simulation_top}.v",
            f"module {simulation_top}(output y); assign y = 1'b0; endmodule\n",
            encoding="utf-8",
        )
    runner = SystemDebugRunner(
        config=RtlDebugConfig(oracle_root=str(tmp_path / "oracle"), openai_config=None),
        workspace_root=workspace,
        output_root=tmp_path / "outputs",
    )

    result = runner.run_system(
        top_module=planner_top,
        task=SimpleNamespace(spec_md_files=[]),
        spec_text="spec",
        contract_json='{"module_name":"planned_system"}',
        merged_records=records,
    )

    assert result.status == "error"
    assert "Multiple simulation top aliases" in result.reason


def test_system_debug_runner_preserves_wave_vcd_from_verifier_tempdir(tmp_path: Path) -> None:
    top_module = "top"
    _write_system_oracle(
        tmp_path,
        top_module,
        "\n".join(
            [
                "import pathlib",
                "import tempfile",
                "",
                "def verify_system(generated_dir):",
                "    with tempfile.TemporaryDirectory() as temp_dir:",
                "        pathlib.Path(temp_dir, 'wave.vcd').write_text('$date\\n$date\\n', encoding='utf-8')",
                "    return True, 'Passed with wave'",
                "",
            ]
        ),
    )
    workspace, records = _write_workspace(tmp_path, top_module)
    runner = SystemDebugRunner(
        config=RtlDebugConfig(oracle_root=str(tmp_path / "oracle"), openai_config=None),
        workspace_root=workspace,
        output_root=tmp_path / "outputs",
    )

    result = runner.run_system(
        top_module=top_module,
        task=SimpleNamespace(spec_md_files=[]),
        spec_text="spec",
        contract_json='{"module_name":"top"}',
        merged_records=records,
    )

    assert result.status == "pass"
    assert (Path(result.workdir) / "wave.vcd").read_text(encoding="utf-8") == "$date\n$date\n"
    assert "ZEROREPO_VCD_COPIED" in Path(result.sim_output_path).read_text(encoding="utf-8")


def test_system_debug_runner_invokes_repo_react_on_failure_and_syncs_generated(tmp_path: Path, monkeypatch: object) -> None:
    top_module = "top"
    _write_system_oracle(
        tmp_path,
        top_module,
        "def verify_system(generated_dir):\n    return False, 'FAIL: Functional mismatches\\nHint: Total mismatched samples is 3 out of 10 samples'\n",
    )
    workspace, records = _write_workspace(tmp_path, top_module)
    runner = SystemDebugRunner(
        config=RtlDebugConfig(oracle_root=str(tmp_path / "oracle"), openai_config=None),
        workspace_root=workspace,
        output_root=tmp_path / "outputs",
    )
    calls: list[Path] = []

    def fake_react(**kwargs: object) -> tuple[bool, int]:
        generated_dir = kwargs["generated_dir"]
        assert isinstance(generated_dir, Path)
        calls.append(generated_dir)
        write_artifact_text(generated_dir / "top.v",
            "module top(output y);\nassign y = 1'b1;\nendmodule\n",
            encoding="utf-8",
        )
        return True, 1

    monkeypatch.setattr(runner, "_run_repo_react", fake_react)

    result = runner.run_system(
        top_module=top_module,
        task=SimpleNamespace(spec_md_files=[]),
        spec_text="spec",
        contract_json='{"module_name":"top"}',
        merged_records=records,
    )

    assert result.status == "fixed"
    assert result.debug_trials == 1
    assert calls
    assert "assign y = 1'b1;" in (artifact_dir(workspace, "merged") / "top.v").read_text(encoding="utf-8")


def test_system_debug_runner_dispatches_to_task_scoped_codex_backend(tmp_path: Path, monkeypatch: object) -> None:
    top_module = "top"
    _write_system_oracle(
        tmp_path,
        top_module,
        "def verify_system(generated_dir):\n"
        "    return False, 'FAIL: Functional mismatches\\nHint: Total mismatched samples is 3 out of 10 samples'\n",
    )
    source_spec = tmp_path / "source_spec.md"
    write_artifact_text(source_spec, "# Original top spec\n", encoding="utf-8")
    workspace, records = _write_workspace(tmp_path, top_module)
    runner = SystemDebugRunner(
        config=RtlDebugConfig(
            backend="codex",
            oracle_root=str(tmp_path / "oracle"),
            openai_config=None,
        ),
        workspace_root=workspace,
        output_root=tmp_path / "outputs",
    )

    def fake_codex_run(self: object, descriptor: object, **_kwargs: object) -> RepoReActResult:
        task_root = getattr(descriptor, "task_root")
        spec_root = getattr(descriptor, "spec_root")
        merged_root = getattr(descriptor, "merged_root")
        private_root = getattr(descriptor, "private_root")
        assert Path(spec_root).is_relative_to(Path(task_root))
        assert Path(merged_root).is_relative_to(Path(task_root))
        assert not Path(private_root).is_relative_to(Path(task_root))
        assert (Path(spec_root) / "source_spec.md").is_file()
        write_artifact_text(Path(merged_root) / "top.v",
            "module top(output y);\nassign y = 1'b1;\nendmodule\n",
            encoding="utf-8",
        )
        final_output = Path(private_root) / "final_sim_output.json"
        write_artifact_text(final_output, "PASS", encoding="utf-8")
        return RepoReActResult(
            status="pass",
            is_pass=True,
            action_calls=2,
            patch_attempts=2,
            sim_output_path=str(final_output),
        )

    monkeypatch.setattr(
        "zerorepo.rtl_impl.codex_debug.runner.CodexDebugRunner.run",
        fake_codex_run,
    )
    result = runner.run_system(
        top_module=top_module,
        task=SimpleNamespace(spec_md_files=[source_spec]),
        spec_text="inline spec",
        contract_json='{"module_name":"top"}',
        merged_records=records,
    )

    assert result.status == "fixed"
    assert result.debug_trials == 2
    assert "assign y = 1'b1;" in (artifact_dir(workspace, "merged") / "top.v").read_text(encoding="utf-8")
