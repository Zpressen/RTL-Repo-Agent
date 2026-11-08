from __future__ import annotations

import json
import shutil
from pathlib import Path
from rtl_artifact_test_utils import write_artifact_text
from zerorepo.rtl_impl.artifact_layout import ArtifactLayout, artifact_path, artifact_dir

import pytest

import zerorepo.rtl_impl.module_planner.agents.global_defines as global_defines_mod
import zerorepo.rtl_impl.module_planner.agents.stage6_semantic_merge as semantic_mod
from zerorepo.rtl_impl.module_planner.agents.global_defines import (
    build_global_defines_context,
    build_stage5_global_defines_summary,
    copy_e203_canonical_define_files,
    copy_official_define_file,
)
from zerorepo.rtl_impl.module_planner.agents.stage5_agent import Stage5Agent
from zerorepo.rtl_impl.module_planner.agents.stage6_semantic_merge import (
    SemanticMergeState,
    Stage6MergeTools,
)
from zerorepo.rtl_impl.debug_agent.sim_reviewer import check_syntax
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
    write_artifact_text(official, "`define BIT_BLOCK 1044\n", encoding="utf-8")
    monkeypatch.setattr(global_defines_mod, "find_official_define_file", lambda _task, _module: official)

    task = PlannerTaskInput(task_id="sdc", spec_md_files=[str(tmp_path / "rtl_dataset" / "sdc" / "x.md")])
    entry = copy_official_define_file(
        task=task,
        module_name="sd_defines",
        workspace_root=tmp_path / "workspace",
        output_root=tmp_path / "outputs",
    )

    assert entry is not None
    merged = artifact_dir(tmp_path / "workspace", "merged") / "sd_defines.v"
    assert merged.read_text(encoding="utf-8") == official.read_text(encoding="utf-8")
    manifest = json.loads((artifact_path(tmp_path / "workspace", "global_defines_manifest.json")).read_text(encoding="utf-8"))
    assert manifest["global_define_files"][0]["mode"] == "official_copy"
    assert manifest["global_define_files"][0]["must_include"] is True


@pytest.mark.parametrize(
    ("top_module", "canonical_project"),
    [
        ("e203_ifu", "e203_ifu"),
        ("e203_exu_alu", "e203_exu_alu"),
        ("e203_exu_alu_system", "e203_exu_alu"),
    ],
)
def test_e203_canonical_headers_are_copied_from_matching_project(
    tmp_path: Path,
    top_module: str,
    canonical_project: str,
) -> None:
    oracle_root = tmp_path / "RealBench"
    verification_dir = oracle_root / "e203_hbirdv2" / canonical_project / "verification"
    verification_dir.mkdir(parents=True)
    write_artifact_text(verification_dir / "config.v", "`define E203_CFG_XLEN 32\n", encoding="utf-8")
    write_artifact_text(verification_dir / "e203_defines.v",
        '`include "config.v"\n`define E203_XLEN `E203_CFG_XLEN\n',
        encoding="utf-8",
    )

    workspace = tmp_path / "workspace"
    entries = copy_e203_canonical_define_files(
        top_module=top_module,
        oracle_root=oracle_root,
        workspace_root=workspace,
        output_root=tmp_path / "outputs",
    )

    assert [item["name"] for item in entries] == ["config.v", "e203_defines.v"]
    assert entries[0]["must_include"] is False
    assert entries[0]["included_by"] == ["e203_defines.v"]
    assert entries[1]["must_include"] is True
    assert Path(entries[0]["source"]).parent == verification_dir.resolve()
    assert (artifact_dir(workspace, "merged") / "config.v").read_text(encoding="utf-8") == "`define E203_CFG_XLEN 32\n"

    manifest = json.loads((artifact_path(workspace, "global_defines_manifest.json")).read_text(encoding="utf-8"))
    assert [item["name"] for item in manifest["global_define_files"]] == ["config.v", "e203_defines.v"]
    context = build_global_defines_context(workspace)
    assert "## config.v" in context
    assert "## e203_defines.v" in context


def test_e203_canonical_headers_fail_atomically_when_one_is_missing(tmp_path: Path) -> None:
    verification_dir = tmp_path / "RealBench" / "e203_hbirdv2" / "e203_ifu" / "verification"
    verification_dir.mkdir(parents=True)
    write_artifact_text(verification_dir / "config.v", "`define E203_CFG_XLEN 32\n", encoding="utf-8")
    workspace = tmp_path / "workspace"

    with pytest.raises(FileNotFoundError, match="e203_defines.v"):
        copy_e203_canonical_define_files(
            top_module="e203_ifu",
            oracle_root=tmp_path / "RealBench",
            workspace_root=workspace,
        )

    assert not (artifact_path(workspace, "global_defines_manifest.json")).exists()
    assert not (artifact_dir(workspace, "merged")).exists()


def test_stage5_macro_summary_resolves_conditions_dependencies_and_undefined_macros(
    tmp_path: Path,
) -> None:
    verification_dir = tmp_path / "RealBench" / "e203_hbirdv2" / "e203_ifu" / "verification"
    verification_dir.mkdir(parents=True)
    write_artifact_text(verification_dir / "config.v",
        "`define E203_CFG_MODE_2\n"
        "`define E203_CFG_ADDR_SIZE 32\n",
        encoding="utf-8",
    )
    write_artifact_text(verification_dir / "e203_defines.v",
        '`include "config.v"\n'
        "`ifdef E203_CFG_MODE_1\n"
        "  `define E203_DEPTH 1\n"
        "`elsif E203_CFG_MODE_2\n"
        "  `define E203_DEPTH 2\n"
        "`else\n"
        "  `define E203_DEPTH 4\n"
        "`endif\n"
        "`define E203_ADDR `E203_CFG_ADDR_SIZE'h8000_0000\n"
        "`ifdef E203_CFG_HAS_FPU\n"
        "  `define E203_HAS_FPU\n"
        "`endif\n"
        "`ifndef E203_CFG_HAS_FPU\n"
        "  `define E203_NO_FPU 1\n"
        "`endif\n"
        "`define E203_REMOVED 1\n"
        "`undef E203_REMOVED\n",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    copy_e203_canonical_define_files(
        top_module="e203_ifu",
        oracle_root=tmp_path / "RealBench",
        workspace_root=workspace,
    )

    summary = build_stage5_global_defines_summary(
        workspace,
        ["Use `E203_DEPTH, `E203_ADDR, `E203_HAS_FPU, `E203_NO_FPU, and `E203_REMOVED."],
        max_chars=6000,
    )

    assert "`define E203_DEPTH 2" in summary
    assert "`define E203_ADDR `E203_CFG_ADDR_SIZE'h8000_0000" in summary
    assert "`define E203_CFG_ADDR_SIZE 32" in summary
    assert "undefined `E203_HAS_FPU`" in summary
    assert "`define E203_NO_FPU 1" in summary
    assert "undefined `E203_REMOVED`" in summary
    assert "`define E203_DEPTH 1" not in summary
    assert "Stage 6 owns the canonical includes" in summary
    assert len(summary) <= 6000


def test_stage5_macro_summary_obeys_budget_without_partial_entries(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    merged = artifact_dir(workspace, "merged")
    merged.mkdir(parents=True)
    defines = merged / "defs.v"
    write_artifact_text(defines,
        "\n".join(f"`define FEATURE_{index:03d} {index}" for index in range(100)) + "\n",
        encoding="utf-8",
    )
    global_defines_mod.write_global_defines_manifest(
        workspace_root=workspace,
        output_root=None,
        entries=[
            {
                "name": "defs.v",
                "workspace_path": str(defines),
                "source": str(defines),
                "must_include": True,
            }
        ],
    )

    summary = build_stage5_global_defines_summary(
        workspace,
        ["Use `FEATURE_001 and `FEATURE_099."],
        max_chars=500,
    )

    assert len(summary) <= 500
    assert "`define FEATURE_001 1" in summary
    assert "`define FEATURE_099 99" in summary
    assert not summary.endswith("`define FEATURE_")


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


def _make_merge_tools(tmp_path: Path, monkeypatch) -> tuple[Stage6MergeTools, dict]:
    workspace = tmp_path / "workspace"
    merged_dir = artifact_dir(workspace, "merged")
    fragments_dir = artifact_dir(workspace, "fragments")
    merged_dir.mkdir(parents=True)
    fragments_dir.mkdir(parents=True)
    write_artifact_text(merged_dir / "config.v", "`define CFG_WIDTH 8\n", encoding="utf-8")
    write_artifact_text(merged_dir / "e203_defines.v",
        '`include "config.v"\n`define E203_WIDTH `CFG_WIDTH\n',
        encoding="utf-8",
    )
    fragment_file = fragments_dir / "m_fragments.v"
    write_artifact_text(fragment_file, "assign y = a;\n", encoding="utf-8")
    manifest = {
        "schema_version": "global_defines_manifest_v1",
        "global_define_files": [
            {
                "name": "config.v",
                "workspace_path": str(merged_dir / "config.v"),
                "must_include": False,
                "included_by": ["e203_defines.v"],
            },
            {
                "name": "e203_defines.v",
                "workspace_path": str(merged_dir / "e203_defines.v"),
                "must_include": True,
            },
        ],
    }
    lint_call: dict = {}

    def fake_check_syntax(path, top_module=None, include_dirs=None, support_files=None):
        lint_call.update(
            path=path,
            top_module=top_module,
            include_dirs=include_dirs,
            support_files=support_files,
        )
        return True, "lint ok"

    monkeypatch.setattr(semantic_mod, "check_syntax", fake_check_syntax)
    state = SemanticMergeState(
        artifact_layout=ArtifactLayout(workspace),
        module_name="m",
        merged_file=merged_dir / "m.v",
        draft_file=artifact_dir(workspace, "merge_drafts") / "m_draft.v",
        fragment_file=fragment_file,
        contracts_file=None,
        global_defines_manifest=manifest,
        required_includes=["e203_defines.v"],
        module_spec="spec",
        module_skeleton="module m(input a, output y); endmodule",
        global_defines_context=(
            "`define CFG_WIDTH 8\n"
            '`include "config.v"\n'
            "`define E203_WIDTH `CFG_WIDTH\n"
        ),
    )
    return Stage6MergeTools(state), lint_call


def test_stage6_requires_global_context_and_includes_only_root_header(tmp_path: Path, monkeypatch) -> None:
    tools, lint_call = _make_merge_tools(tmp_path, monkeypatch)
    tools.read_merge_context("fragments")
    tools.read_merge_context("spec")
    code = "module m(input a, output y);\nassign y = a;\nendmodule"

    rejected = tools.generate_merge_draft(code, "merge", "compile")
    assert rejected["status"] == "rejected"
    assert 'read_merge_context(kind="global_defines")' in rejected["reason"]

    context = tools.read_merge_context("global_defines", max_chars=60000)
    assert context["manifest"]["global_define_files"][0]["name"] == "config.v"
    kept = tools.generate_merge_draft(code, "merge", "compile")

    assert kept["status"] == "kept"
    draft = tools.state.draft_file.read_text(encoding="utf-8")
    assert draft.count('`include "e203_defines.v"') == 1
    assert '`include "config.v"' not in draft
    assert lint_call["top_module"] == "m"
    assert lint_call["include_dirs"] == [str(tools.state.merged_file.parent)]
    assert lint_call["support_files"] == []


def test_stage6_rejects_fallback_redefinition_of_authoritative_macro(tmp_path: Path, monkeypatch) -> None:
    tools, _ = _make_merge_tools(tmp_path, monkeypatch)
    tools.read_merge_context("fragments")
    tools.read_merge_context("spec")
    tools.read_merge_context("global_defines", max_chars=60000)

    rejected = tools.generate_merge_draft(
        "`ifndef E203_WIDTH\n"
        "`define E203_WIDTH 32\n"
        "`endif\n"
        "module m(input a, output y); assign y = a; endmodule",
        "fallback",
        "compile",
    )

    assert rejected["status"] == "rejected"
    assert "E203_WIDTH" in rejected["reason"]
    assert not tools.state.draft_file.exists()


def test_stage6_static_check_does_not_require_interface_contract(tmp_path: Path, monkeypatch) -> None:
    tools, _ = _make_merge_tools(tmp_path, monkeypatch)
    tools.state.draft_file.parent.mkdir(parents=True)
    write_artifact_text(tools.state.draft_file,
        '`include "e203_defines.v"\n'
        "module m(input a, output extra);\nassign extra = a;\nendmodule\n",
        encoding="utf-8",
    )

    result = tools.run_static_rtl_check("draft")

    assert result["status"] == "pass"
    assert result["structure"]["outputs"] == ["extra"]
    assert "extra" in result["structure"]["output_drivers"]

    write_artifact_text(tools.state.draft_file,
        '`include "e203_defines.v"\nmodule m(input a);\nendmodule\n',
        encoding="utf-8",
    )
    no_output = tools.run_static_rtl_check("draft")
    assert no_output["status"] == "pass"


def test_stage6_static_check_resolves_manifest_and_local_macros(tmp_path: Path, monkeypatch) -> None:
    tools, _ = _make_merge_tools(tmp_path, monkeypatch)
    tools.state.draft_file.parent.mkdir(parents=True)
    write_artifact_text(tools.state.draft_file,
        '`include "e203_defines.v"\n'
        "`define LOCAL_WIDTH 2\n"
        "module m(input a, output y);\n"
        "wire [`E203_WIDTH-1:0] official_bus;\n"
        "wire [`LOCAL_WIDTH-1:0] local_bus;\n"
        "assign y = a;\n"
        "endmodule\n",
        encoding="utf-8",
    )

    resolved = tools.run_static_rtl_check("draft")
    assert not any("unresolved macro" in error for error in resolved["errors"])

    write_artifact_text(tools.state.draft_file,
        "module m(input a, output y);\n"
        "wire [`MISSING_WIDTH-1:0] missing_bus;\n"
        "assign y = a;\n"
        "endmodule\n",
        encoding="utf-8",
    )
    unresolved = tools.run_static_rtl_check("draft")
    assert any("MISSING_WIDTH" in error for error in unresolved["errors"])


def test_stage6_structure_parse_failure_is_fatal(tmp_path: Path, monkeypatch) -> None:
    tools, _ = _make_merge_tools(tmp_path, monkeypatch)
    tools.state.draft_file.parent.mkdir(parents=True)
    write_artifact_text(tools.state.draft_file,
        "module m(input a, output y); assign y = a; endmodule\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        semantic_mod,
        "parse_rtl_blocks",
        lambda _text: (_ for _ in ()).throw(ValueError("bad parse")),
    )

    structure = tools.inspect_rtl_structure("draft")
    static = tools.run_static_rtl_check("draft")

    assert structure["status"] == "parse_error"
    assert tools.state.observed_structure is False
    assert static["status"] == "fail"
    assert any("bad parse" in error for error in static["errors"])


@pytest.mark.skipif(shutil.which("verilator") is None, reason="Verilator is not available")
def test_verilator_resolves_transitive_canonical_header_include(tmp_path: Path) -> None:
    merged_dir = artifact_dir(tmp_path, "merged")
    draft_dir = tmp_path / "draft"
    merged_dir.mkdir()
    draft_dir.mkdir()
    write_artifact_text(merged_dir / "config.v", "`define E203_CFG_WIDTH 8\n", encoding="utf-8")
    write_artifact_text(merged_dir / "e203_defines.v",
        '`include "config.v"\n`define E203_WIDTH `E203_CFG_WIDTH\n',
        encoding="utf-8",
    )
    rtl_path = draft_dir / "m.v"
    write_artifact_text(rtl_path,
        '`include "e203_defines.v"\n'
        "module m(input [`E203_WIDTH-1:0] a, output [`E203_WIDTH-1:0] y);\n"
        "assign y = a;\n"
        "endmodule\n",
        encoding="utf-8",
    )

    passed, output = check_syntax(
        str(rtl_path),
        top_module="m",
        include_dirs=[str(merged_dir)],
    )

    assert passed, output
