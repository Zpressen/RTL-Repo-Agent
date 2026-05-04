import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from zerorepo.rpg_gen.base import Memory, RPG, RepoSkeleton
from zerorepo.rpg_gen.impl_level.func_design.agents.base_class_agent import (
    BaseClassAgent,
    BaseClassEnv,
    BaseClassReviewOutput,
    GenerateBaseClassesTool,
)


FIXTURE_DIR = Path("rtl_outputs/rtl_spec_/.zerorepo")


def _load_rtl_context():
    repo_data = json.loads((FIXTURE_DIR / "repo_data.json").read_text(encoding="utf-8"))
    rtl_metadata = repo_data["rtl_metadata"]
    file_specs = rtl_metadata.get("file_specs", []) or []
    return {
        "component_names": [item["file_path"] for item in file_specs if item.get("file_path")],
        "file_specs": file_specs,
        "module_specs": rtl_metadata.get("module_specs", []),
        "top_module": rtl_metadata.get("top_module", ""),
    }


def _load_repo_objects():
    repo_data = json.loads((FIXTURE_DIR / "repo_data.json").read_text(encoding="utf-8"))
    skeleton = RepoSkeleton.load_json(FIXTURE_DIR / "skeleton.json")
    rpg = RPG(
        repo_name=repo_data["repository_name"],
        repo_info=repo_data["repository_purpose"],
        excluded_files=[],
    )
    rpg.data_flow = [
        {
            "source": "rtl/pkg/uart_pkg.sv",
            "target": "rtl/modules/axi_lite_regs.sv",
            "data_id": "uart_pkg_defs",
            "data_type": "TypeAndConstantPackage",
            "transformation": "Package definitions are consumed by RTL modules.",
        }
    ]
    return skeleton, rpg


def test_generate_base_classes_tool_accepts_rtl_package_code():
    _, rpg = _load_repo_objects()
    rtl_context = _load_rtl_context()
    env = SimpleNamespace(repo_rpg=rpg, rtl_context=rtl_context)

    result = asyncio.run(
        GenerateBaseClassesTool.execute(
            {
                "base_classes": [
                    {
                        "file_path": "rtl/pkg/uart_pkg.sv",
                        "code": (
                            "package uart_pkg;\n"
                            "  // UART Protocol Constants used by Python ref model\n"
                            "  typedef enum logic [1:0] {UART_IDLE, UART_BUSY} uart_state_e;\n"
                            "endpackage\n"
                        ),
                    }
                ]
            },
            env=env,
        )
    )

    assert result.error is None
    assert result.state["base_classes"][0]["file_path"] == "rtl/pkg/uart_pkg.sv"


def test_generate_base_classes_tool_rejects_non_package_rtl_target():
    _, rpg = _load_repo_objects()
    rtl_context = _load_rtl_context()
    env = SimpleNamespace(repo_rpg=rpg, rtl_context=rtl_context)

    result = asyncio.run(
        GenerateBaseClassesTool.execute(
            {
                "base_classes": [
                    {
                        "file_path": "rtl/modules/uart_tx.sv",
                        "code": "package uart_pkg;\nendpackage\n",
                    }
                ]
            },
            env=env,
        )
    )

    assert result.error is not None
    assert "may only target these package files" in result.error


def test_rtl_base_class_agent_uses_package_context_in_task_and_review():
    skeleton, rpg = _load_repo_objects()
    rtl_context = _load_rtl_context()
    env = BaseClassEnv(
        review_llm=object(),
        review_format=BaseClassReviewOutput,
        review_memory=Memory(),
        register_tools=[],
        repo_skeleton=skeleton,
        repo_rpg=rpg,
        rtl_context=rtl_context,
    )
    agent = object.__new__(BaseClassAgent)
    agent.repo_skeleton = skeleton
    agent.repo_rpg = rpg
    agent.rtl_context = rtl_context
    agent._env = env

    captured = {}

    def fake_run(task, max_error_times, max_steps):
        captured["task"] = task
        return {"final_results": [], "is_terminate": True, "is_suc": True}

    agent.run = fake_run
    result = agent.generate_base_classes(max_retry=1, max_steps=1)

    assert result["success"] is False
    assert "rtl/pkg/uart_pkg.sv" in captured["task"]
    assert "shared RTL definitions" in captured["task"]
    assert "Python codebase" not in captured["task"]

    review_message = env.load_review_message([])
    assert "RTL Package Targets" in review_message
    assert "rtl/pkg/uart_pkg.sv" in review_message
    assert "Functional Graph Overview" not in review_message
