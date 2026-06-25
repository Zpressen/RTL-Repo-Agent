from __future__ import annotations

import json
from pathlib import Path

import zerorepo.rtl_impl.module_planner.agents.global_defines as global_defines_mod
import zerorepo.rtl_impl.module_planner.agents.stage6_semantic_merge as semantic_mod
from zerorepo.rtl_impl.module_planner.agents.global_defines import copy_official_define_file
from zerorepo.rtl_impl.module_planner.agents.stage5_agent import Stage5Agent
from zerorepo.rtl_impl.module_planner.agents.stage6_semantic_merge import (
    SemanticMergeContext,
    Stage6SemanticMergeRunner,
    Stage6SemanticMergeTools,
)
from zerorepo.rtl_impl.module_planner.schemas import PlannerTaskInput


class FakeLLM:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, *, system_prompt, user_prompt, images=None):
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt, "images": images})
        if not self.responses:
            raise AssertionError("No queued response")
        return self.responses.pop(0)


def test_official_define_file_is_copied_and_manifested(tmp_path: Path, monkeypatch) -> None:
    official = tmp_path / "RealBench" / "sdc" / "sd_defines" / "sd_defines.v"
    official.parent.mkdir(parents=True)
    official.write_text("`define BIT_BLOCK 1044\n", encoding="utf-8")
    monkeypatch.setattr(global_defines_mod, "find_official_define_file", lambda _task, _module: official)

    task = PlannerTaskInput(task_id="sdc", spec_md_files=[str(tmp_path / "rtl_dataset" / "sdc" / "x.md")])
    entry = copy_official_define_file(
        task=task,
        module_name="sd_defines",
        workspace_root=tmp_path / "workspace",
        output_root=tmp_path / "outputs",
    )

    assert entry is not None
    merged = tmp_path / "workspace" / "merged" / "sd_defines.v"
    assert merged.read_text(encoding="utf-8") == official.read_text(encoding="utf-8")
    manifest = json.loads((tmp_path / "workspace" / "merged" / "global_defines_manifest.json").read_text(encoding="utf-8"))
    assert manifest["global_define_files"][0]["mode"] == "official_copy"
    assert manifest["global_define_files"][0]["must_include"] is True


def test_stage5_contract_fallback_extracts_writes_and_reads(tmp_path: Path) -> None:
    agent = Stage5Agent(llm_client=FakeLLM([]), workspace_root=tmp_path / "workspace")

    contract = agent._extract_fragment_contract(
        "always @(posedge clk) begin\n"
        "  if (rst) y <= 1'b0;\n"
        "  else y <= a & b;\n"
        "end\n"
    )

    assert contract.writes == ["y"]
    assert "a" in contract.reads
    assert "b" in contract.reads
    assert contract.clocking == "posedge clk"


def test_stage6_semantic_react_applies_patch_with_required_include_and_report(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(semantic_mod, "check_syntax", lambda _path, top_module=None: (True, "lint ok"))
    merged_file = tmp_path / "workspace" / "merged" / "m.v"
    manifest = {
        "schema_version": "global_defines_manifest_v1",
        "global_define_files": [
            {
                "name": "sd_defines.v",
                "module": "sd_defines",
                "source": "/official/sd_defines.v",
                "workspace_path": str(tmp_path / "workspace" / "merged" / "sd_defines.v"),
                "mode": "official_copy",
                "must_include": True,
            }
        ],
    }
    ctx = SemanticMergeContext(
        module_name="m",
        merged_file=merged_file,
        module_spec="spec",
        module_skeleton="module m(input a, output y); endmodule",
        kg_child_context="",
        global_defines_context="`define BIT_BLOCK 1044",
        generated_fragments="assign y = a;",
        fragment_file=tmp_path / "workspace" / "fragments" / "m_fragments.v",
        contracts_file=None,
        global_defines_manifest=manifest,
        required_includes=["sd_defines.v"],
    )
    tools = Stage6SemanticMergeTools(ctx)
    llm = FakeLLM(
        [
            json.dumps({"action": {"tool": "read_merge_context", "args": {}}}),
            json.dumps(
                {
                    "action": {
                        "tool": "apply_merge_patch",
                        "args": {
                            "new_code": "module m(input a, output y);\nassign y = a;\nendmodule",
                            "reason": "merge complete",
                        },
                    }
                }
            ),
        ]
    )

    runner = Stage6SemanticMergeRunner(llm, tools, max_steps=3)
    code = runner.run("initial prompt", fallback_raw_merge=lambda _raw=None: "")
    report = tools.write_merge_report(tmp_path / "workspace" / "merge_reports" / "m_merge_report.json")

    assert '`include "sd_defines.v"' in code
    assert merged_file.read_text(encoding="utf-8").startswith('`include "sd_defines.v"')
    assert report["required_includes"] == ["sd_defines.v"]
    assert report["static_check_summary"]["status"] == "pass"


def test_stage6_raw_verilog_is_routed_through_semantic_patch(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(semantic_mod, "check_syntax", lambda _path, top_module=None: (True, "lint ok"))
    merged_file = tmp_path / "workspace" / "merged" / "m.v"
    ctx = SemanticMergeContext(
        module_name="m",
        merged_file=merged_file,
        module_spec="spec",
        module_skeleton="module m(input a, output y); endmodule",
        kg_child_context="",
        global_defines_context="`define BIT_BLOCK 1044",
        generated_fragments="assign y = a;",
        fragment_file=tmp_path / "workspace" / "fragments" / "m_fragments.v",
        contracts_file=None,
        global_defines_manifest={
            "schema_version": "global_defines_manifest_v1",
            "global_define_files": [{"name": "sd_defines.v", "must_include": True}],
        },
        required_includes=["sd_defines.v"],
    )
    tools = Stage6SemanticMergeTools(ctx)
    llm = FakeLLM(["module m(input a, output y);\nassign y = a;\nendmodule"])
    fallback_calls = []

    runner = Stage6SemanticMergeRunner(llm, tools, max_steps=2)
    code = runner.run("initial prompt", fallback_raw_merge=lambda raw=None: fallback_calls.append(raw) or "")
    report = tools.write_merge_report(tmp_path / "workspace" / "merge_reports" / "m_merge_report.json")

    assert not fallback_calls
    assert '`include "sd_defines.v"' in code
    assert (tmp_path / "workspace" / "merge_snapshots" / "m" / "step_001" / "after.v").exists()
    assert report["merge_iterations"][0]["status"] == "kept"
    assert any(item["tool"] == "read_merge_context" for item in runner.history if item["role"] == "tool")
