from __future__ import annotations

import json
from pathlib import Path

import zerorepo.rtl_impl.debug_agent.debug_runner as debug_runner_module
from zerorepo.rtl_impl.debug_agent.debug_runner import ModuleDebugRunner, RtlDebugConfig


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
