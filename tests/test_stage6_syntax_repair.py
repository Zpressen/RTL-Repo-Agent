from __future__ import annotations

import json
from pathlib import Path

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


def _diagnostic(root: Path, module: str) -> dict:
    return json.loads((root / "outputs" / "stage6_syntax_repair" / f"{module}.json").read_text(encoding="utf-8"))


def test_stage6_records_pass_without_retry(tmp_path: Path, monkeypatch) -> None:
    code = "module parent(input clk); endmodule"
    llm = FakeLLM([code])
    agent = Stage6MergeAgent(llm, output_root=tmp_path / "outputs", workspace_root=tmp_path / "workspace")
    rtl_path = tmp_path / "workspace" / "merged" / "parent.v"
    monkeypatch.setattr(stage6_merge_agent_mod, "check_syntax", lambda _path, top_module=None: (True, "lint ok"))

    result = agent._invoke_raw_with_repair(
        "ORIGINAL_PROMPT",
        task=None,
        partial_artifacts={},
        module_name="parent",
        rtl_path=rtl_path,
    )

    assert result == code
    assert len(llm.calls) == 1
    assert rtl_path.read_text(encoding="utf-8").strip() == code
    log = _diagnostic(tmp_path, "parent")
    assert log["status"] == "pass"
    assert log["syntax_passed"] is True


def test_stage6_delegates_syntax_failure_to_debug_without_retry(tmp_path: Path, monkeypatch) -> None:
    bad_code = "module parent(input clk); child u(.bad_port(clk)); endmodule"
    llm = FakeLLM([bad_code, "module parent(input clk); endmodule"])
    agent = Stage6MergeAgent(llm, output_root=tmp_path / "outputs", workspace_root=tmp_path / "workspace")
    rtl_path = tmp_path / "workspace" / "merged" / "parent.v"
    monkeypatch.setattr(
        stage6_merge_agent_mod,
        "check_syntax",
        lambda _path, top_module=None: (False, "%Error-PINNOTFOUND: rtl.sv:1: Pin not found: 'bad_port'"),
    )

    result = agent._invoke_raw_with_repair(
        "ORIGINAL_PROMPT",
        task=None,
        partial_artifacts={},
        module_name="parent",
        rtl_path=rtl_path,
    )

    assert result == bad_code
    assert len(llm.calls) == 1
    assert "bad_port" in rtl_path.read_text(encoding="utf-8")
    log = _diagnostic(tmp_path, "parent")
    assert log["status"] == "delegated_to_debug_syntax_repair"
    assert log["syntax_passed"] is False
    assert log["delegated_to"] == "ModuleDebugRunner.repo_react_syntax"
    assert "PINNOTFOUND" in log["syntax_summary"]


def test_stage6_delegates_empty_output_to_debug_without_retry(tmp_path: Path) -> None:
    llm = FakeLLM([""])
    agent = Stage6MergeAgent(llm, output_root=tmp_path / "outputs", workspace_root=tmp_path / "workspace")
    rtl_path = tmp_path / "workspace" / "merged" / "parent.v"

    result = agent._invoke_raw_with_repair(
        "ORIGINAL_PROMPT",
        task=None,
        partial_artifacts={},
        module_name="parent",
        rtl_path=rtl_path,
    )

    assert result == ""
    assert len(llm.calls) == 1
    assert rtl_path.read_text(encoding="utf-8") == "\n"
    log = _diagnostic(tmp_path, "parent")
    assert log["status"] == "empty_output_delegated_to_debug"
    assert log["syntax_passed"] is False
