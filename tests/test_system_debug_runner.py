from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from zerorepo.rtl_impl.debug_agent.debug_runner import RtlDebugConfig
from zerorepo.rtl_impl.debug_agent.system_debug_runner import SystemDebugRunner


def _write_system_oracle(tmp_path: Path, top_module: str, body: str) -> Path:
    verify_dir = tmp_path / "oracle" / "system_task" / top_module / "verify_test"
    verify_dir.mkdir(parents=True)
    (verify_dir / f"{top_module}_testbench.sv").write_text("module tb; endmodule\n", encoding="utf-8")
    (verify_dir / f"{top_module}_verify.py").write_text(body, encoding="utf-8")
    return verify_dir


def _write_workspace(tmp_path: Path, top_module: str) -> tuple[Path, list[SimpleNamespace]]:
    workspace = tmp_path / "workspace"
    merged = workspace / "merged"
    merged.mkdir(parents=True)
    top_file = merged / f"{top_module}.v"
    top_file.write_text("module top(output y);\nassign y = 1'b0;\nendmodule\n", encoding="utf-8")
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
    (verify_dir / f"{simulation_top}_testbench.sv").write_text(
        f"module tb; {simulation_top} top_module1(); endmodule\n",
        encoding="utf-8",
    )
    workspace, records = _write_workspace(tmp_path, planner_top)
    alias_file = workspace / "merged" / f"{simulation_top}.v"
    alias_file.write_text(
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
    (verify_dir / f"{simulation_top}_testbench.sv").write_text(
        f"module tb; {simulation_top} top_module1(); endmodule\n",
        encoding="utf-8",
    )
    workspace, records = _write_workspace(tmp_path, planner_top)
    (workspace / "merged" / f"{simulation_top}.v").write_text(
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
        (workspace / "merged" / f"{simulation_top}.v").write_text(
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
        (generated_dir / "top.v").write_text(
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
    assert "assign y = 1'b1;" in (workspace / "merged" / "top.v").read_text(encoding="utf-8")
