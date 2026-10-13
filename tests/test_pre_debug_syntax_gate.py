from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import zerorepo.rtl_impl.debug_agent.debug_runner as debug_runner_module
from zerorepo.rtl_impl.debug_agent.debug_runner import ModuleDebugRunner, RtlDebugConfig
from zerorepo.rtl_impl.debug_agent.sim_reviewer import check_syntax


def _runner(tmp_path: Path) -> ModuleDebugRunner:
    return ModuleDebugRunner(
        config=RtlDebugConfig(openai_config=None),
        workspace_root=tmp_path / "workspace",
    )


def _write_debug_workdir(tmp_path: Path) -> Path:
    workdir = tmp_path / "workspace" / "debug" / "sdc_controller"
    workdir.mkdir(parents=True)
    (workdir / "rtl.sv").write_text(
        "\n".join(
            [
                "module sdc_controller(input clk, input [3:0] sd_dat_dat_i);",
                "sd_data_serial_host #(.SD_BUS_W(4)) u_data (",
                "    .clk(clk),",
                "    .DAT_dat_i(sd_dat_dat_i)",
                ");",
                "endmodule",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (workdir / "support.sv").write_text(
        "\n".join(
            [
                "module sd_data_serial_host(",
                "    input clk,",
                "    input [3:0] DAT_dat_i",
                ");",
                "endmodule",
                "",
                "module sd_fifo_rx_filler(",
                "    input clk,",
                "    output full",
                ");",
                "endmodule",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (workdir / "sd_defines.v").write_text("`define SD_BUS_W 4\n", encoding="utf-8")
    (workdir / "tb.sv").write_text("module tb; endmodule\n", encoding="utf-8")
    return workdir


def test_build_support_interface_index_and_macro_table(tmp_path: Path) -> None:
    workdir = _write_debug_workdir(tmp_path)
    runner = _runner(tmp_path)

    index = runner._build_support_interface_index(workdir)
    macros = runner._build_macro_table(workdir)

    data_host = index["modules"]["sd_data_serial_host"]
    assert {port["name"] for port in data_host["ports"]} == {"clk", "DAT_dat_i"}
    assert data_host["parameters"] == []
    assert "module sd_data_serial_host" in data_host["declaration"]
    assert {"name": "SD_BUS_W", "value": "4", "file": "sd_defines.v", "line": 1} in macros


def test_pre_debug_prompt_contains_support_index_macro_table_and_rules(tmp_path: Path) -> None:
    workdir = _write_debug_workdir(tmp_path)
    runner = _runner(tmp_path)
    rtl_code = (workdir / "rtl.sv").read_text(encoding="utf-8")
    support_text = (workdir / "support.sv").read_text(encoding="utf-8")

    prompt = runner._build_pre_debug_syntax_repair_prompt(
        module_name="sdc_controller",
        rtl_code=rtl_code,
        syntax_output="%Error: Parameter not found: 'SD_BUS_W'",
        support_index=runner._build_support_interface_index(workdir),
        support_text=support_text,
        macro_table=runner._build_macro_table(workdir),
        spec_text="spec text",
        contract_json='{"module_name": "sdc_controller"}',
    )

    assert "support.sv is the authoritative child module interface source" in prompt
    assert "Do not pass macros as parameter overrides" in prompt
    assert "Do not connect ports that are absent" in prompt
    assert "SD_BUS_W" in prompt
    assert "DAT_dat_i" in prompt
    assert "rtl_sv_with_lineno" in prompt


def test_repair_debug_workspace_syntax_updates_only_rtl_and_writes_log(tmp_path: Path, monkeypatch) -> None:
    workdir = _write_debug_workdir(tmp_path)
    runner = _runner(tmp_path)
    repaired = "\n".join(
        [
            "module sdc_controller(input clk, input [3:0] sd_dat_dat_i);",
            "sd_data_serial_host u_data (",
            "    .clk(clk),",
            "    .DAT_dat_i(sd_dat_dat_i)",
            ");",
            "endmodule",
        ]
    )
    syntax_results = iter(
        [
            (False, "%Error: Parameter not found: 'SD_BUS_W'"),
            (True, ""),
        ]
    )
    monkeypatch.setattr(
        debug_runner_module,
        "check_syntax",
        lambda _path, top_module=None: next(syntax_results),
    )
    monkeypatch.setattr(
        ModuleDebugRunner,
        "_call_pre_debug_syntax_repair_llm",
        lambda self, prompt: f"```systemverilog\n{repaired}\n```",
    )

    runner._repair_debug_workspace_syntax(
        module_name="sdc_controller",
        workdir=workdir,
        spec_text="spec text",
        contract_json="{}",
    )

    assert "#(.SD_BUS_W(4))" not in (workdir / "rtl.sv").read_text(encoding="utf-8")
    assert "module sd_data_serial_host" in (workdir / "support.sv").read_text(encoding="utf-8")
    log = json.loads((workdir / "pre_debug_syntax_repair.json").read_text(encoding="utf-8"))
    assert log["status"] == "pass_after_repair"
    assert log["attempts"][0]["syntax_passed"] is True
    assert (workdir / "support_interface_index.json").exists()


def test_repair_debug_workspace_syntax_failure_is_non_fatal(tmp_path: Path, monkeypatch) -> None:
    workdir = _write_debug_workdir(tmp_path)
    runner = _runner(tmp_path)
    monkeypatch.setattr(
        debug_runner_module,
        "check_syntax",
        lambda _path, top_module=None: (False, "%Error: still bad"),
    )
    monkeypatch.setattr(
        ModuleDebugRunner,
        "_call_pre_debug_syntax_repair_llm",
        lambda self, prompt: "module broken;",
    )

    runner._repair_debug_workspace_syntax(
        module_name="sdc_controller",
        workdir=workdir,
        spec_text="spec text",
        contract_json="{}",
    )

    log = json.loads((workdir / "pre_debug_syntax_repair.json").read_text(encoding="utf-8"))
    assert log["status"] == "fail"
    assert len(log["attempts"]) == 5


def test_run_module_runs_pre_debug_syntax_gate_before_sim_review(tmp_path: Path, monkeypatch) -> None:
    oracle_dir = tmp_path / "oracle" / "m" / "verification"
    oracle_dir.mkdir(parents=True)
    (oracle_dir / "m_testbench.sv").write_text("module tb; endmodule\n", encoding="utf-8")
    merged_file = tmp_path / "workspace" / "merged" / "m.v"
    merged_file.parent.mkdir(parents=True)
    merged_file.write_text("module m; endmodule\n", encoding="utf-8")
    events: list[str] = []

    class PassingReviewer:
        def __init__(self, workdir: str, support_path: str) -> None:
            self.workdir = workdir
            self.support_path = support_path

        def review(self) -> tuple[bool, int, str]:
            events.append("review")
            return True, 0, "{}"

    def fake_check_syntax(_path: str, top_module=None) -> tuple[bool, str]:
        events.append(f"syntax:{top_module}")
        return True, ""

    monkeypatch.setattr(debug_runner_module, "check_syntax", fake_check_syntax)
    monkeypatch.setattr(debug_runner_module, "SimReviewer", PassingReviewer)
    monkeypatch.setattr(ModuleDebugRunner, "_ensure_toolchain_path", lambda self: None)

    runner = ModuleDebugRunner(
        config=RtlDebugConfig(openai_config=None, oracle_root=str(tmp_path / "oracle")),
        workspace_root=tmp_path / "workspace",
    )
    result = runner.run_module(
        module_name="m",
        merged_file=merged_file,
        task=None,
        spec_text="spec",
        contract_json='{"module_name": "m"}',
    )

    assert result.status == "pass"
    assert events == ["syntax:m", "review"]
    assert (Path(result.workdir) / "pre_debug_syntax_repair.json").exists()


def test_run_module_syntax_gate_does_not_require_oracle_or_sim_review(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    merged_dir = workspace / "merged"
    merged_dir.mkdir(parents=True)
    merged_file = merged_dir / "m.v"
    merged_file.write_text("module m(output y);\nassign y = 1'b0;\nendmodule\n", encoding="utf-8")
    (merged_dir / "child.v").write_text("module child(output y);\nassign y = 1'b0;\nendmodule\n", encoding="utf-8")
    events: list[str] = []

    class FailingReviewer:
        def __init__(self, *_args, **_kwargs) -> None:
            events.append("reviewer_constructed")

        def review(self) -> tuple[bool, int, str]:
            events.append("review")
            return False, 1, "{}"

    def fake_check_syntax(_path: str, top_module=None) -> tuple[bool, str]:
        events.append(f"syntax:{top_module}")
        return True, "{}"

    monkeypatch.setattr(debug_runner_module, "check_syntax", fake_check_syntax)
    monkeypatch.setattr(debug_runner_module, "SimReviewer", FailingReviewer)
    monkeypatch.setattr(ModuleDebugRunner, "_ensure_toolchain_path", lambda self: None)
    runner = ModuleDebugRunner(
        config=RtlDebugConfig(openai_config=None, oracle_root=str(tmp_path / "missing_oracle")),
        workspace_root=workspace,
    )

    result = runner.run_module_syntax_gate(
        module_name="m",
        merged_file=merged_file,
        task=None,
        spec_text="spec",
        contract_json='{"module_name": "m"}',
    )

    assert result.status == "pass"
    assert events == ["syntax:m"]
    assert "module child" in (Path(result.workdir) / "support.sv").read_text(encoding="utf-8")


def test_syntax_gate_stages_manifest_headers_and_excludes_them_from_support(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    merged_dir = workspace / "merged"
    merged_dir.mkdir(parents=True)
    merged_file = merged_dir / "m.v"
    merged_file.write_text(
        '`include "e203_defines.v"\nmodule m(output [`E203_W-1:0] y); assign y = 0; endmodule\n',
        encoding="utf-8",
    )
    config_text = "`define E203_W 8\n"
    defines_text = '`include "config.v"\n'
    (merged_dir / "config.v").write_text(config_text, encoding="utf-8")
    (merged_dir / "e203_defines.v").write_text(defines_text, encoding="utf-8")
    (merged_dir / "child.v").write_text("module child; endmodule\n", encoding="utf-8")
    (workspace / "global_defines_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "global_defines_manifest_v1",
                "global_define_files": [
                    {
                        "name": "config.v",
                        "workspace_path": str(merged_dir / "config.v"),
                        "must_include": False,
                    },
                    {
                        "name": "e203_defines.v",
                        "workspace_path": str(merged_dir / "e203_defines.v"),
                        "must_include": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    runner = ModuleDebugRunner(config=RtlDebugConfig(openai_config=None), workspace_root=workspace)
    workdir = workspace / "debug" / "m"

    runner._prepare_syntax_gate_workdir(
        module_name="m",
        merged_file=merged_file,
        workdir=workdir,
        contract_json='{"module_name":"m"}',
        spec_source_path=None,
    )

    assert (workdir / "config.v").read_text(encoding="utf-8") == config_text
    assert (workdir / "e203_defines.v").read_text(encoding="utf-8") == defines_text
    support = (workdir / "support.sv").read_text(encoding="utf-8")
    assert "module child" in support
    assert "support source: config.v" not in support
    assert "support source: e203_defines.v" not in support
    manifest = json.loads((workdir / "debug_input_manifest.json").read_text(encoding="utf-8"))
    assert {Path(item).name for item in manifest["staged_global_define_files"]} == {
        "config.v",
        "e203_defines.v",
    }


def test_staged_nested_headers_lint_before_and_after_candidate_patch(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    merged_dir = workspace / "merged"
    merged_dir.mkdir(parents=True)
    merged_file = merged_dir / "m.v"
    merged_file.write_text(
        '`include "e203_defines.v"\n'
        "module m(output [`E203_W-1:0] y);\n"
        "child u_child(.y(y));\n"
        "endmodule\n",
        encoding="utf-8",
    )
    (merged_dir / "config.v").write_text("`define E203_W 8\n", encoding="utf-8")
    (merged_dir / "e203_defines.v").write_text('`include "config.v"\n', encoding="utf-8")
    (merged_dir / "child.v").write_text(
        '`include "e203_defines.v"\n'
        "module child(output [`E203_W-1:0] y); assign y = 0; endmodule\n",
        encoding="utf-8",
    )
    (workspace / "global_defines_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "global_defines_manifest_v1",
                "global_define_files": [
                    {"name": "config.v", "workspace_path": str(merged_dir / "config.v")},
                    {"name": "e203_defines.v", "workspace_path": str(merged_dir / "e203_defines.v")},
                ],
            }
        ),
        encoding="utf-8",
    )
    runner = ModuleDebugRunner(config=RtlDebugConfig(openai_config=None), workspace_root=workspace)
    runner._ensure_toolchain_path()
    if shutil.which("verilator") is None:
        pytest.skip("Verilator is not installed")
    workdir = workspace / "debug" / "m"
    runner._prepare_syntax_gate_workdir(
        module_name="m",
        merged_file=merged_file,
        workdir=workdir,
        contract_json='{"module_name":"m"}',
        spec_source_path=None,
    )

    initial_passed, initial_output = check_syntax(str(workdir / "rtl.sv"), top_module="m")
    assert initial_passed, initial_output

    (workdir / "rtl.sv").write_text(
        '`include "e203_defines.v"\n'
        "module m(output [`E203_W-1:0] y);\n"
        "wire [`E203_W-1:0] child_y;\n"
        "child u_child(.y(child_y));\n"
        "assign y = child_y;\n"
        "endmodule\n",
        encoding="utf-8",
    )
    patched_passed, patched_output = check_syntax(str(workdir / "rtl.sv"), top_module="m")
    assert patched_passed, patched_output


def test_run_module_syntax_gate_repairs_and_writes_back_to_merged(tmp_path: Path, monkeypatch) -> None:
    workspace = tmp_path / "workspace"
    merged_dir = workspace / "merged"
    merged_dir.mkdir(parents=True)
    merged_file = merged_dir / "m.v"
    merged_file.write_text("module m(output y)\nassign y = 1'b0;\nendmodule\n", encoding="utf-8")
    syntax_results = iter([(False, "%Error: syntax"), (True, "{}")])

    def fake_check_syntax(_path: str, top_module=None) -> tuple[bool, str]:
        return next(syntax_results)

    def fake_repair(self, *, workdir: Path, **_kwargs) -> tuple[bool, str, int]:
        repaired = "module m(output y);\nassign y = 1'b1;\nendmodule\n"
        (workdir / "rtl.sv").write_text(repaired, encoding="utf-8")
        return True, repaired, 1

    monkeypatch.setattr(debug_runner_module, "check_syntax", fake_check_syntax)
    monkeypatch.setattr(ModuleDebugRunner, "_ensure_toolchain_path", lambda self: None)
    monkeypatch.setattr(ModuleDebugRunner, "_run_repo_react_syntax_repair", fake_repair)
    runner = ModuleDebugRunner(config=RtlDebugConfig(openai_config=None), workspace_root=workspace)

    result = runner.run_module_syntax_gate(
        module_name="m",
        merged_file=merged_file,
        task=None,
        spec_text="spec",
        contract_json='{"module_name": "m"}',
    )

    assert result.status == "fixed"
    assert result.debug_trials == 1
    assert "assign y = 1'b1;" in merged_file.read_text(encoding="utf-8")
