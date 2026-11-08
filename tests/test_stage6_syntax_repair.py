from __future__ import annotations

import json
from pathlib import Path
from rtl_artifact_test_utils import write_artifact_text
from zerorepo.rtl_impl.artifact_layout import artifact_dir

import pytest

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
    return json.loads((artifact_dir(root / "outputs", "debug") / module / "reports" / "stage6_syntax_repair.json").read_text(encoding="utf-8"))


def test_stage6_records_pass_without_retry(tmp_path: Path, monkeypatch) -> None:
    code = "module parent(input clk); endmodule"
    llm = FakeLLM([code])
    agent = Stage6MergeAgent(llm, output_root=tmp_path / "outputs", workspace_root=tmp_path / "workspace")
    rtl_path = artifact_dir(tmp_path / "workspace", "merged") / "parent.v"
    monkeypatch.setattr(
        stage6_merge_agent_mod,
        "check_syntax",
        lambda _path, top_module=None, support_files=None: (True, "lint ok"),
    )

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
    rtl_path = artifact_dir(tmp_path / "workspace", "merged") / "parent.v"
    monkeypatch.setattr(
        stage6_merge_agent_mod,
        "check_syntax",
        lambda _path, top_module=None, support_files=None: (
            False,
            "%Error-PINNOTFOUND: rtl.sv:1: Pin not found: 'bad_port'",
        ),
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


@pytest.mark.parametrize(
    "raw_response",
    [None, "", "null", "None", "module other; endmodule", "module parent;"],
)
def test_stage6_rejects_invalid_raw_output_without_overwriting_merged(
    tmp_path: Path,
    raw_response: object,
) -> None:
    llm = FakeLLM([raw_response])
    agent = Stage6MergeAgent(llm, output_root=tmp_path / "outputs", workspace_root=tmp_path / "workspace")
    rtl_path = artifact_dir(tmp_path / "workspace", "merged") / "parent.v"
    rtl_path.parent.mkdir(parents=True)
    original = "module parent; wire preserved; endmodule\n"
    write_artifact_text(rtl_path, original, encoding="utf-8")

    with pytest.raises(ValueError, match="Existing merged RTL was preserved"):
        agent._invoke_raw_with_repair(
            "ORIGINAL_PROMPT",
            task=None,
            partial_artifacts={},
            module_name="parent",
            rtl_path=rtl_path,
        )

    assert len(llm.calls) == 1
    assert rtl_path.read_text(encoding="utf-8") == original
    assert not (tmp_path / "outputs" / "stage6_syntax_repair" / "parent.json").exists()
