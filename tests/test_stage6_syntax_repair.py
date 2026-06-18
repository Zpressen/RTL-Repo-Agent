from __future__ import annotations

import json

import zerorepo.rtl_impl.module_planner.agents.stage6_merge_agent as stage6_merge_agent_mod
from zerorepo.rtl_impl.module_planner.agents.stage6_merge_agent import Stage6MergeAgent


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, *, system_prompt, user_prompt, images=None):
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "images": list(images or []),
            }
        )
        if not self.responses:
            raise AssertionError("No more queued LLM responses.")
        return self.responses.pop(0)


def test_extract_verilator_errors_keeps_pin_and_parameter_errors(tmp_path):
    agent = Stage6MergeAgent(FakeLLM([]), output_root=tmp_path / "outputs", workspace_root=tmp_path / "workspace")
    syntax_output = """
%Warning-WIDTH: rtl.sv:1: signal width mismatch
%Error-PINNOTFOUND: rtl.sv:22:10: Pin not found: 'DAR_dat_i'
   22 |   .DAR_dat_i(sd_dat_dat_i)
      |    ^~~~~~~~~
%Error: rtl.sv:33:5: Parameter not found: 'SD_BUS_W'
%Error-PINMISSING: rtl.sv:44:1: Cell has missing pin: 'ack_o'
"""

    extracted = agent._extract_verilator_errors(syntax_output)

    assert "PINNOTFOUND" in extracted
    assert "DAR_dat_i" in extracted
    assert "Parameter not found" in extracted
    assert "PINMISSING" in extracted
    assert "Warning-WIDTH" not in extracted
    assert agent._is_interface_mismatch_error(syntax_output) is True


def test_build_post_merge_syntax_repair_prompt_contains_context(tmp_path):
    agent = Stage6MergeAgent(FakeLLM([]), output_root=tmp_path / "outputs", workspace_root=tmp_path / "workspace")
    prompt = agent._build_post_merge_syntax_repair_prompt(
        original_prompt="ORIGINAL_MERGE_PROMPT",
        module_name="parent",
        syntax_output="%Error-PINNOTFOUND: rtl.sv:3: Pin not found: 'bad_port'",
        code="module parent(input clk); child u(.bad_port(clk)); endmodule",
        module_spec="[S001]\nselected spec marker",
        module_skeleton="module skeleton marker",
        kg_child_context={
            "schema_version": "merge_child_context_v1",
            "children": [
                {
                    "module": "child",
                    "ports": [{"name": "clk", "direction": "input", "width": "1"}],
                    "parameters": [],
                    "interface_code": "module child(input clk); endmodule",
                }
            ],
        },
        previous_failures=[{"attempt": 1, "error_summary": "still bad"}],
    )

    assert "Interface mismatch repair" in prompt
    assert "bad_port" in prompt
    assert "module_with_lineno" in prompt
    assert "selected spec marker" in prompt
    assert "module skeleton marker" in prompt
    assert "module child(input clk)" in prompt
    assert "still bad" in prompt


def test_post_merge_syntax_repair_succeeds_after_second_repair(tmp_path, monkeypatch):
    bad_code = "module parent(input clk); child u(.bad_port(clk)); endmodule"
    still_bad = "module parent(input clk); child u(.still_bad(clk)); endmodule"
    good_code = "module parent(input clk); child u(.clk(clk)); endmodule"
    llm = FakeLLM([bad_code, still_bad, good_code])
    agent = Stage6MergeAgent(llm, output_root=tmp_path / "outputs", workspace_root=tmp_path / "workspace")
    rtl_path = tmp_path / "workspace" / "merged" / "parent.v"
    syntax_results = iter(
        [
            (False, "%Error-PINNOTFOUND: rtl.sv:1: Pin not found: 'bad_port'"),
            (False, "%Error-PINNOTFOUND: rtl.sv:1: Pin not found: 'still_bad'"),
            (True, ""),
        ]
    )
    monkeypatch.setattr(
        stage6_merge_agent_mod,
        "check_syntax",
        lambda _path, top_module=None: next(syntax_results),
    )

    result = agent._invoke_raw_with_repair(
        "ORIGINAL_PROMPT",
        task=None,
        partial_artifacts={},
        module_name="parent",
        rtl_path=rtl_path,
        module_spec="[S001]\nparent spec",
        module_skeleton="skeleton",
        kg_child_context={"children": [{"module": "child", "ports": [{"name": "clk"}]}]},
    )

    assert result == good_code
    assert rtl_path.read_text(encoding="utf-8").strip() == good_code
    assert len(llm.calls) == 3
    assert "failed Verilator after Stage6 merge" in llm.calls[1]["user_prompt"]
    assert "still_bad" in llm.calls[2]["user_prompt"]
    log = json.loads((tmp_path / "outputs" / "stage6_syntax_repair" / "parent.json").read_text(encoding="utf-8"))
    assert log["status"] == "pass_after_repair"
    assert len(log["attempts"]) == 2
    assert log["attempts"][0]["syntax_passed"] is False
    assert log["attempts"][1]["syntax_passed"] is True


def test_post_merge_syntax_repair_exhausts_after_five_failures(tmp_path, monkeypatch):
    initial_code = "module parent(input clk); child u(.bad_port(clk)); endmodule"
    repairs = [
        f"module parent(input clk); child u(.bad_port_{idx}(clk)); endmodule"
        for idx in range(5)
    ]
    llm = FakeLLM([initial_code] + repairs)
    agent = Stage6MergeAgent(llm, output_root=tmp_path / "outputs", workspace_root=tmp_path / "workspace")
    rtl_path = tmp_path / "workspace" / "merged" / "parent.v"
    monkeypatch.setattr(
        stage6_merge_agent_mod,
        "check_syntax",
        lambda _path, top_module=None: (False, "%Error-PINNOTFOUND: rtl.sv:1: Pin not found"),
    )

    result = agent._invoke_raw_with_repair(
        "ORIGINAL_PROMPT",
        task=None,
        partial_artifacts={},
        module_name="parent",
        rtl_path=rtl_path,
        module_spec="",
        module_skeleton="",
        kg_child_context={},
    )

    assert result == repairs[-1]
    assert len(llm.calls) == 6
    log = json.loads((tmp_path / "outputs" / "stage6_syntax_repair" / "parent.json").read_text(encoding="utf-8"))
    assert log["status"] == "fail"
    assert log["max_trials"] == 5
    assert len(log["attempts"]) == 5
