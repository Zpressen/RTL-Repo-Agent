import json
import logging
from pathlib import Path
from unittest.mock import patch

from zerorepo.rpg_gen.base import RPG
from zerorepo.rpg_gen.impl_level.plan_tasks.task_batch import TaskBatch
from zerorepo.rpg_gen.impl_level.plan_tasks.task_planner import (
    PlanTaskBatchesTool,
    TaskPlannerAgent,
    TaskPlanner,
    _build_rtl_unit_bundle,
    _build_rtl_unit_implementation_context,
    _build_rtl_unit_trace_context,
    _normalize_rtl_unit_features,
)


FIXTURE_DIR = Path("rtl_outputs/rtl_spec_/.zerorepo")


def _load_repo_data():
    repo_data = json.loads((FIXTURE_DIR / "repo_data.json").read_text(encoding="utf-8"))
    repo_data["_repo_data_path"] = str(FIXTURE_DIR / "repo_data.json")
    repo_data["_repo_data_dir"] = str(FIXTURE_DIR)
    return repo_data


def _load_rpg():
    repo_data = _load_repo_data()
    return RPG(
        repo_name=repo_data["repository_name"],
        repo_info=repo_data["repository_purpose"],
        excluded_files=[],
    )


def test_rtl_task_planner_agent_uses_rtl_prompt_context():
    repo_data = _load_repo_data()
    rpg = _load_rpg()
    file_spec = next(
        item
        for item in repo_data["rtl_metadata"]["file_specs"]
        if item.get("file_path") == "Makefile"
    )
    agent = object.__new__(TaskPlannerAgent)
    agent.repo_rpg = rpg
    agent.rtl_file_spec = file_spec
    planner = TaskPlanner(
        rpg=rpg,
        llm_cfg={},
        graph_data={},
        repo_data=repo_data,
        logger=logging.getLogger("test_rtl_task_planner"),
    )
    agent._env = type(
        "Env",
        (),
        {
            "file_path": "Makefile",
            "cur_subtree": "Makefile",
            "units_to_feature": {"build:Makefile": []},
            "units_to_trace_context": {"build:Makefile": []},
            "units_to_implementation_context": {},
            "unit_to_kind": {"build:Makefile": "build"},
            "secondary_context": {"responsibility": "build entry point"},
            "get_unit_catalog": lambda self: {
                "build:Makefile": (
                    "file_path=Makefile\n"
                    "unit_name=build:Makefile\n"
                    "unit_kind=build\n"
                    "responsibility=build entry point"
                )
            },
            "is_rtl_mode": lambda self: True,
        },
    )()
    agent.rtl_trace_catalog = planner.rtl_trace_catalog

    task = agent._build_rtl_task()

    assert "RTL/build file: Makefile" in task
    assert "Source code of the file" not in task
    assert "depends_on_files: []" in task
    assert "build:Makefile" in task
    assert "Supplementary file context" in task


def test_task_planner_builds_rtl_fallback_units_from_repo_data():
    repo_data = _load_repo_data()
    rpg = _load_rpg()
    graph_data = {
        "data_flow_phase": {"subtree_order": ["Makefile"]},
        "interfaces_phase": {
            "interfaces": {
                "subtrees": {
                    "Makefile": {
                        "files_order": ["Makefile"],
                        "interfaces": {
                            "Makefile": {
                                "file_code": "",
                                "units_to_code": {},
                                "units_to_features": {},
                            }
                        },
                    }
                }
            }
        },
    }
    planner = TaskPlanner(
        rpg=rpg,
        llm_cfg={},
        graph_data=graph_data,
        repo_data=repo_data,
        logger=logging.getLogger("test_rtl_task_planner"),
    )

    file_spec = planner.rtl_file_specs["Makefile"]
    fallback = _build_rtl_unit_bundle("Makefile", file_spec)

    assert "build:Makefile" in fallback["units_to_spec"]
    assert fallback["unit_to_kind"]["build:Makefile"] == "build"


def test_plan_task_batches_custom_parse_repairs_double_brace_tool_call():
    raw = """
<tool_call>
{{
  "tool_name": "plan_task_batches",
  "parameters": {
    "batches": [
      {
        "units": ["build:Makefile"],
        "task": "Implement the Makefile build entrypoint and lint/sim target wiring."
      }
    ]
  }
}}
</tool_call>
""".strip()

    parsed = PlanTaskBatchesTool.custom_parse(raw)

    assert len(parsed) == 1
    assert parsed[0]["batches"][0]["units"] == ["build:Makefile"]


def test_rtl_task_planner_normalizes_features_to_canonical_trace_ids():
    repo_data = _load_repo_data()
    file_specs = {
        item["file_path"]: item
        for item in repo_data["rtl_metadata"]["file_specs"]
    }

    axi_lite_regs_features = _normalize_rtl_unit_features(
        file_specs["rtl/modules/axi_lite_regs.sv"],
        ["module:axi_lite_regs"],
        {"module:axi_lite_regs": ["axi_register_map"]},
    )
    fifo_features = _normalize_rtl_unit_features(
        file_specs["rtl/modules/fifo_sync.sv"],
        ["module:fifo_sync"],
        {"module:fifo_sync": ["rx_fifo_interface", "tx_fifo_interface"]},
    )
    makefile_features = _normalize_rtl_unit_features(
        file_specs["Makefile"],
        ["build:Makefile"],
        {"build:Makefile": ["build:Makefile"]},
    )

    assert axi_lite_regs_features["module:axi_lite_regs"] == [
        "REQ-001",
        "REQ-002",
        "REQ-004",
        "REQ-005",
        "TEST-001",
        "TEST-011",
        "TEST-020",
        "TEST-030",
        "TEST-040",
        "PROP-001",
        "PROP-010",
    ]
    assert fifo_features["module:fifo_sync"] == []
    assert makefile_features["build:Makefile"] == []


def test_rtl_task_planner_builds_trace_context_from_catalog():
    repo_data = _load_repo_data()
    rpg = _load_rpg()
    planner = TaskPlanner(
        rpg=rpg,
        llm_cfg={},
        graph_data={},
        repo_data=repo_data,
        logger=logging.getLogger("test_rtl_task_planner_trace_context"),
    )
    file_spec = next(
        item
        for item in repo_data["rtl_metadata"]["file_specs"]
        if item.get("file_path") == "rtl/modules/uart_rx.sv"
    )
    features = _normalize_rtl_unit_features(
        file_spec,
        ["module:uart_rx"],
        {"module:uart_rx": []},
    )
    trace_context = _build_rtl_unit_trace_context(
        ["module:uart_rx"],
        features,
        planner.rtl_trace_catalog,
    )

    assert trace_context["module:uart_rx"][0]["id"] == "REQ-003"
    assert "UART frame" in trace_context["module:uart_rx"][0]["summary"]


def test_rtl_task_planner_builds_implementation_context_for_uart_rx():
    repo_data = _load_repo_data()
    rpg = _load_rpg()
    planner = TaskPlanner(
        rpg=rpg,
        llm_cfg={},
        graph_data={},
        repo_data=repo_data,
        logger=logging.getLogger("test_rtl_task_planner_impl_context"),
    )
    file_spec = next(
        item
        for item in repo_data["rtl_metadata"]["file_specs"]
        if item.get("file_path") == "rtl/modules/uart_rx.sv"
    )
    context = _build_rtl_unit_implementation_context(
        file_path="rtl/modules/uart_rx.sv",
        file_spec=file_spec,
        unit_to_kind={"module:uart_rx": "rtl_module"},
        file_implementation_context_by_path=planner.file_implementation_context_by_path,
    )

    assert context["module:uart_rx"]["nodes"][0]["node_id"] == "Node-06"
    assert any(item["anchor_id"] == "ANCHOR-003" for item in context["module:uart_rx"]["anchors"])
    assert any(item["hint_id"] == "HINT-011" for item in context["module:uart_rx"]["hints"])


def test_rtl_task_planner_task_includes_trace_descriptions():
    repo_data = _load_repo_data()
    rpg = _load_rpg()
    planner = TaskPlanner(
        rpg=rpg,
        llm_cfg={},
        graph_data={},
        repo_data=repo_data,
        logger=logging.getLogger("test_rtl_task_planner_task_trace"),
    )
    file_spec = next(
        item
        for item in repo_data["rtl_metadata"]["file_specs"]
        if item.get("file_path") == "rtl/modules/uart_rx.sv"
    )
    features = {"module:uart_rx": ["REQ-003", "TEST-020", "TEST-022"]}
    trace_context = _build_rtl_unit_trace_context(
        ["module:uart_rx"],
        features,
        planner.rtl_trace_catalog,
    )

    agent = object.__new__(TaskPlannerAgent)
    agent.repo_rpg = rpg
    agent.rtl_file_spec = file_spec
    agent._env = type(
        "Env",
        (),
        {
            "file_path": "rtl/modules/uart_rx.sv",
            "cur_subtree": "rtl/modules/uart_rx.sv",
            "units_to_feature": features,
            "units_to_trace_context": trace_context,
            "units_to_implementation_context": {
                "module:uart_rx": planner.file_implementation_context_by_path["rtl/modules/uart_rx.sv"]
            },
            "unit_to_kind": {"module:uart_rx": "rtl_module"},
            "secondary_context": {"responsibility": file_spec.get("responsibility", "")},
            "get_unit_catalog": lambda self: {
                "module:uart_rx": "module uart_rx contract"
            },
            "is_rtl_mode": lambda self: True,
        },
    )()

    task = agent._build_rtl_task()

    assert "REQ-003 (requirement)" in task
    assert "When a valid UART frame is received" in task
    assert "TEST-020 (test)" in task
    assert "ANCHOR-003" in task
    assert "RX state machine definition" in task


def test_task_planner_skips_rtl_documentation_files(tmp_path):
    repo_data = _load_repo_data()
    rpg = _load_rpg()
    graph_data = {
        "data_flow_phase": {"subtree_order": ["README.md"]},
        "interfaces_phase": {
            "interfaces": {
                "subtrees": {
                    "README.md": {
                        "files_order": ["README.md"],
                        "interfaces": {
                            "README.md": {
                                "file_code": "documentation placeholder",
                                "units_to_code": {},
                                "units_to_spec": {"doc:README.md": "readme contract"},
                                "unit_to_kind": {"doc:README.md": "documentation"},
                                "units_to_features": {"doc:README.md": ["README.md"]},
                            }
                        },
                    }
                }
            }
        },
    }
    planner = TaskPlanner(
        rpg=rpg,
        llm_cfg={},
        graph_data=graph_data,
        repo_data=repo_data,
        logger=logging.getLogger("test_rtl_task_planner_docs"),
    )

    with patch.object(TaskPlannerAgent, "plan_all_tasks", side_effect=AssertionError("README.md should be skipped")):
        planner.plan_all_batches(tmp_path / "tasks.json")

    assert "README.md" not in planner.planned_batches_dict
    assert "FINAL_TASKS" in planner.planned_batches_dict


def test_task_planner_adds_rtl_special_batches():
    repo_data = _load_repo_data()
    rpg = _load_rpg()
    planner = TaskPlanner(
        rpg=rpg,
        llm_cfg={},
        graph_data={"data_flow_phase": {"subtree_order": ["rtl/axi_uart_top.sv"]}},
        repo_data=repo_data,
        logger=logging.getLogger("test_rtl_task_planner_special"),
    )

    planned_batches = {
        "rtl/axi_uart_top.sv": {
            "rtl/axi_uart_top.sv": []
        }
    }
    planned_batches["rtl/axi_uart_top.sv"]["rtl/axi_uart_top.sv"] = [
        TaskBatch(
            task="Implement top integration wiring.",
            file_path="rtl/axi_uart_top.sv",
            units_key=["module:axi_uart_top"],
            unit_to_code={},
            unit_to_spec={"module:axi_uart_top": "module axi_uart_top contract"},
            unit_to_kind={"module:axi_uart_top": "rtl_module"},
            unit_to_features={"module:axi_uart_top": ["REQ-001", "PROP-001"]},
            subtree="rtl/axi_uart_top.sv",
        )
    ]
    agent_results = {"rtl/axi_uart_top.sv": {"rtl/axi_uart_top.sv": {"success": True}}}

    planner._add_special_batches(planned_batches, agent_results)

    subtree_special = planned_batches["rtl/axi_uart_top.sv"]["<SUBTREE_VERIFICATION>_rtl/axi_uart_top.sv"][0]
    final_special = planned_batches["FINAL_TASKS"]["<FINAL_REPO_VALIDATION>"][0]

    assert subtree_special.task_type == "subtree_verification"
    assert "compile, lint, or simulate" in subtree_special.task
    assert subtree_special.unit_to_spec
    assert final_special.task_type == "final_repo_validation"
    assert "full lint and simulation" in final_special.task
    assert final_special.unit_to_spec
