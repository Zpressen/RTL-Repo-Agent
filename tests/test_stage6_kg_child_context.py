from __future__ import annotations

import json
from pathlib import Path
from rtl_artifact_test_utils import write_artifact_text
from zerorepo.rtl_impl.artifact_layout import artifact_dir

from zerorepo.rtl_impl.retrieval_agent.schemas import MergeContextRetrievalResult
from zerorepo.rtl_impl.module_planner.agents.stage6_merge_agent import Stage6MergeAgent
from zerorepo.rtl_impl.module_planner.prompts import stage6_merge


class FakeLLM:
    def complete(self, *, system_prompt, user_prompt, images=None):
        return "module dummy; endmodule"


class FakeKgService:
    def __init__(self, repo_path: Path, *, passed: bool):
        self.repo_path = repo_path
        self.passed = passed
        self.query_calls = []

    def is_enabled(self):
        return True

    @property
    def repo_uid(self):
        return "repo@test"

    def query(self, cypher, params=None, limit=None):
        self.query_calls.append({"cypher": cypher, "params": params or {}, "limit": limit})
        module_name = (params or {}).get("module_name", "aes_sbox")
        return {
            "rows": [
                {
                    "module": module_name,
                    "module_path": f"{module_name}.v",
                    "module_start_line": 1,
                    "module_end_line": 20,
                    "simulation_status": "pass" if self.passed else "fail",
                    "simulation_passed": self.passed,
                    "final_rtl_path": str(self.repo_path / f"{module_name}.v"),
                    "ports": [
                        {
                            "name": "clk",
                            "attrs": json.dumps({"dir": "input", "width_expr": "1"}),
                            "path": f"{module_name}.v",
                            "sl": 2,
                            "el": 2,
                        },
                        {
                            "name": "dout",
                            "attrs": {"dir": "output", "width_expr": "[7:0]"},
                            "path": f"{module_name}.v",
                            "sl": 3,
                            "el": 3,
                        },
                    ],
                    "parameters": [
                        {
                            "name": "WIDTH",
                            "attrs": json.dumps({"value_short": "8", "width_expr": ""}),
                            "path": f"{module_name}.v",
                            "sl": 1,
                            "el": 1,
                        }
                    ],
                }
            ]
        }


def _write_child_module(repo_path: Path, module_name: str = "aes_sbox") -> Path:
    repo_path.mkdir(parents=True, exist_ok=True)
    path = repo_path / f"{module_name}.v"
    write_artifact_text(path,
        "\n".join(
            [
                f"module {module_name}(",
                "    input clk,",
                "    output [7:0] dout",
                ");",
                "parameter WIDTH = 8;",
                "assign dout = 8'h63;",
                "endmodule",
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_stage6_builds_full_code_context_for_small_verified_child(tmp_path):
    repo_path = artifact_dir(tmp_path, "merged")
    _write_child_module(repo_path)
    agent = Stage6MergeAgent(
        llm_client=FakeLLM(),
        output_root=tmp_path / "outputs",
        workspace_root=tmp_path / "workspace",
        kg_service=FakeKgService(repo_path, passed=True),
    )

    context = agent._build_kg_child_context(
        "aes_cipher_top",
        {"children": ["aes_sbox"], "instance_hints": []},
    )
    child = context["children"][0]

    assert child["module"] == "aes_sbox"
    assert child["child_status"] == "verified"
    assert child["ports"][1]["direction"] == "output"
    assert child["ports"][1]["width"] == "[7:0]"
    assert child["parameters"][0]["value"] == "8"
    assert child["code_mode"] == "full"
    assert child["full_code_included"] is True
    assert "assign dout" in child["full_code"]


def test_stage6_uses_interface_only_for_candidate_child(tmp_path):
    repo_path = artifact_dir(tmp_path, "merged")
    _write_child_module(repo_path)
    agent = Stage6MergeAgent(
        llm_client=FakeLLM(),
        output_root=tmp_path / "outputs",
        workspace_root=tmp_path / "workspace",
        kg_service=FakeKgService(repo_path, passed=False),
    )

    context = agent._build_kg_child_context(
        "aes_cipher_top",
        {"children": [], "instance_hints": [{"module": "aes_sbox"}]},
    )
    child = context["children"][0]

    assert child["child_status"] == "candidate"
    assert child["code_mode"] == "interface_only"
    assert child["full_code_included"] is False
    assert "full_code" not in child
    assert "module aes_sbox" in child["interface_code"]


def test_stage6_merge_prompt_includes_kg_child_context(tmp_path):
    repo_path = artifact_dir(tmp_path, "merged")
    _write_child_module(repo_path)
    agent = Stage6MergeAgent(
        llm_client=FakeLLM(),
        output_root=tmp_path / "outputs",
        workspace_root=tmp_path / "workspace",
        kg_service=FakeKgService(repo_path, passed=True),
    )
    context = agent._build_kg_child_context(
        "aes_cipher_top",
        {"children": ["aes_sbox"], "instance_hints": []},
    )

    prompt = stage6_merge.build_prompt(
        module_spec="[S001]\nparent spec",
        module_skeleton="module skeleton",
        kg_child_context=agent._format_kg_child_context_for_prompt(context),
        generated_fragments="fragment code",
    )

    assert "# KG CHILD MODULE CONTEXT" in prompt
    assert "aes_sbox" in prompt
    assert '"direction": "output"' in prompt
    assert '"width": "[7:0]"' in prompt


def test_stage6_child_context_is_non_blocking_without_kg(tmp_path):
    agent = Stage6MergeAgent(
        llm_client=FakeLLM(),
        output_root=tmp_path / "outputs",
        workspace_root=tmp_path / "workspace",
        kg_service=None,
    )

    context = agent._build_kg_child_context(
        "aes_cipher_top",
        {"children": ["aes_sbox"], "instance_hints": []},
    )

    assert context["kg_enabled"] is False
    assert context["children"] == []
    assert "unavailable" in context["reason"]


def test_stage6_skips_kg_lookup_when_retrieval_declines_child_context(tmp_path):
    repo_path = artifact_dir(tmp_path, "merged")
    _write_child_module(repo_path)
    kg_service = FakeKgService(repo_path, passed=True)
    agent = Stage6MergeAgent(
        llm_client=FakeLLM(),
        output_root=tmp_path / "outputs",
        workspace_root=tmp_path / "workspace",
        kg_service=kg_service,
    )

    context = agent._build_kg_child_context_from_retrieval_decision(
        "aes_cipher_top",
        {"children": ["aes_sbox"], "instance_hints": []},
        MergeContextRetrievalResult(
            module="aes_cipher_top",
            selected_spec_refs=["S001"],
            use_kg_child_context=False,
            kg_child_context_reason="Fragments do not instantiate child modules.",
        ),
    )

    assert context["retrieval_requested"] is False
    assert context["children"] == []
    assert context["available_child_modules"] == ["aes_sbox"]
    assert kg_service.query_calls == []


def test_stage6_uses_kg_lookup_when_retrieval_requests_child_context(tmp_path):
    repo_path = artifact_dir(tmp_path, "merged")
    _write_child_module(repo_path)
    kg_service = FakeKgService(repo_path, passed=True)
    agent = Stage6MergeAgent(
        llm_client=FakeLLM(),
        output_root=tmp_path / "outputs",
        workspace_root=tmp_path / "workspace",
        kg_service=kg_service,
    )

    context = agent._build_kg_child_context_from_retrieval_decision(
        "aes_cipher_top",
        {"children": ["aes_sbox", "aes_rcon"], "instance_hints": []},
        MergeContextRetrievalResult(
            module="aes_cipher_top",
            selected_spec_refs=["S001"],
            use_kg_child_context=True,
            kg_child_modules=["aes_sbox"],
            kg_child_context_reason="Fragments instantiate aes_sbox.",
        ),
    )

    assert context["retrieval_requested"] is True
    assert context["requested_child_modules"] == ["aes_sbox"]
    assert len(context["children"]) == 1
    assert context["children"][0]["module"] == "aes_sbox"
    assert len(kg_service.query_calls) == 1


def test_stage6_merge_prompt_omits_kg_section_without_retrieved_context():
    prompt = stage6_merge.build_prompt(
        module_spec="[S001]\nparent spec",
        module_skeleton="module skeleton",
        kg_child_context="",
        generated_fragments="fragment code",
    )

    assert "# KG CHILD MODULE CONTEXT" not in prompt
