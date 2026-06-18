from __future__ import annotations

import json

import zerorepo.rtl_impl.debug_agent.sim_reviewer as sim_reviewer_mod
from zerorepo.rtl_impl.debug_agent.bash_tools import CommandResult
from zerorepo.rtl_impl.debug_agent.sim_reviewer import sim_review, sim_review_mismatch_cnt


def test_output_mismatch_lines_override_zero_summary() -> None:
    stdout = "\n".join(
        [
            "Hint: Output 'wb_dat_o' has no mismatches.",
            "Hint: Output 'int_a' has 27 mismatches. First mismatch occurred at time 145.",
            "Hint: Output 'int_b' has no mismatches.",
            "Hint: Total mismatched samples is 0 out of 23932 samples",
            "Mismatches: 0 in 23932 samples",
        ]
    )

    assert sim_review_mismatch_cnt(stdout) == 27


def test_sim_review_fails_when_output_mismatch_conflicts_with_zero_summary(tmp_path, monkeypatch) -> None:
    (tmp_path / "rtl.sv").write_text("module dut; endmodule\n", encoding="utf-8")
    (tmp_path / "tb.sv").write_text("module tb; endmodule\n", encoding="utf-8")
    stdout = "\n".join(
        [
            "Hint: Output 'int_a' has 27 mismatches. First mismatch occurred at time 145.",
            "Hint: Total mismatched samples is 0 out of 23932 samples",
            "Mismatches: 0 in 23932 samples",
        ]
    )
    command_result = CommandResult(
        is_pass=True,
        stdout=stdout,
        stderr="",
    ).model_dump_json()
    monkeypatch.setattr(sim_reviewer_mod, "_require_executable", lambda _name: None)
    monkeypatch.setattr(sim_reviewer_mod, "run_bash_command", lambda *args, **kwargs: (True, command_result))

    is_pass, mismatch_cnt, sim_output = sim_review(str(tmp_path))

    assert is_pass is False
    assert mismatch_cnt == 27
    assert json.loads(sim_output)["stdout"] == stdout


def test_sim_review_puts_local_include_sources_before_testbench(tmp_path, monkeypatch) -> None:
    (tmp_path / "sd_defines.v").write_text("`define RAM_MEM_WIDTH 16\n", encoding="utf-8")
    (tmp_path / "support.sv").write_text('`include "sd_defines.v"\nmodule ref; endmodule\n', encoding="utf-8")
    (tmp_path / "rtl.sv").write_text("module dut; endmodule\n", encoding="utf-8")
    (tmp_path / "tb.sv").write_text("module tb; logic [`RAM_MEM_WIDTH-1:0] x; endmodule\n", encoding="utf-8")
    command_result = CommandResult(is_pass=True, stdout="Mismatches: 0 in 1 samples\n", stderr="").model_dump_json()
    captured: dict[str, str] = {}

    def fake_run_bash_command(cmd: str, *args, **kwargs):
        del args, kwargs
        captured["cmd"] = cmd
        return True, command_result

    monkeypatch.setattr(sim_reviewer_mod, "_require_executable", lambda _name: None)
    monkeypatch.setattr(sim_reviewer_mod, "run_bash_command", fake_run_bash_command)

    sim_review(str(tmp_path), str(tmp_path / "support.sv"))

    cmd = captured["cmd"]
    assert cmd.index(str(tmp_path / "sd_defines.v")) < cmd.index(str(tmp_path / "tb.sv"))
