import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from zerorepo.rpg_gen.base import Memory, RPG, RepoSkeleton
from zerorepo.rpg_gen.impl_level.func_design.designer import FuncDesigner
from zerorepo.rpg_gen.impl_level.func_design.agents.interface_agent import (
    DesignInterfacesTool,
    InterfaceAgent,
    InterfaceEnv,
    InterfaceReviewOutput,
    _get_top_module_facts,
)
from zerorepo.rpg_gen.impl_level.func_design.prompts.design import DESIGN_ITF
from zerorepo.rpg_gen.impl_level.rtl_trace import (
    build_rtl_trace_catalog,
    build_trace_context,
    build_implementation_node_catalog,
    build_code_anchor_catalog,
    build_implementation_hint_catalog,
    build_file_implementation_context_by_path,
)
from zerorepo.rpg_gen.impl_level.plan_tasks.task_batch import TaskBatch


FIXTURE_DIR = Path("rtl_outputs/rtl_spec_/.zerorepo")


def _load_rtl_context():
    repo_data = json.loads((FIXTURE_DIR / "repo_data.json").read_text(encoding="utf-8"))
    spec_facts = json.loads((FIXTURE_DIR / "spec_facts.json").read_text(encoding="utf-8"))
    rtl_metadata = repo_data["rtl_metadata"]
    file_specs = rtl_metadata.get("file_specs", []) or []
    trace_catalog = build_rtl_trace_catalog(spec_facts)
    implementation_node_catalog = build_implementation_node_catalog(spec_facts)
    code_anchor_catalog = build_code_anchor_catalog(spec_facts)
    implementation_hint_catalog = build_implementation_hint_catalog(spec_facts)
    file_trace_ids_by_path = {}
    for item in file_specs:
        file_path = item.get("file_path")
        if not file_path:
            continue
        file_trace_ids_by_path[file_path] = (
            list(item.get("related_req_ids", []) or [])
            + list(item.get("related_test_ids", []) or [])
            + list(item.get("related_prop_ids", []) or [])
        )
    return {
        "component_names": [item["file_path"] for item in file_specs if item.get("file_path")],
        "file_specs": file_specs,
        "file_specs_by_path": {
            item["file_path"]: item for item in file_specs if item.get("file_path")
        },
        "trace_catalog": trace_catalog,
        "file_trace_ids_by_path": file_trace_ids_by_path,
        "file_trace_context_by_path": {
            file_path: build_trace_context(trace_ids, trace_catalog)
            for file_path, trace_ids in file_trace_ids_by_path.items()
        },
        "file_secondary_context_by_path": {
            item["file_path"]: {
                "responsibility": item.get("responsibility", ""),
                "related_node_ids": list(item.get("related_node_ids", []) or []),
                "related_code_anchor_ids": list(item.get("related_code_anchor_ids", []) or []),
                "related_hint_ids": list(item.get("related_hint_ids", []) or []),
            }
            for item in file_specs
            if item.get("file_path")
        },
        "implementation_node_catalog": implementation_node_catalog,
        "code_anchor_catalog": code_anchor_catalog,
        "implementation_hint_catalog": implementation_hint_catalog,
        "file_implementation_context_by_path": build_file_implementation_context_by_path(
            file_specs,
            implementation_node_catalog,
            code_anchor_catalog,
            implementation_hint_catalog,
        ),
        "module_specs": rtl_metadata.get("module_specs", []),
        "top_module": spec_facts.get("top_module") or rtl_metadata.get("top_module", ""),
        "top_ports": spec_facts.get("top_ports", []),
        "top_params": spec_facts.get("params", []),
        "params": spec_facts.get("params", []),
        "clock_reset": spec_facts.get("clock_reset", {}),
        "default_params": spec_facts.get("default_params", []),
    }


def _top_module_code_from_ports(rtl_context, omit_port=None):
    ports = []
    for port in rtl_context.get("top_ports", []):
        name = port.get("name")
        if not name or name == omit_port:
            continue
        direction = port.get("direction", "input")
        width_expr = str(port.get("width_expr", "1"))
        decl = f"  {direction} logic {name}"
        if width_expr and width_expr != "1":
            decl = f"  {direction} logic [{width_expr}-1:0] {name}"
        ports.append(decl)
    ports_block = ",\n".join(ports)
    return (
        "module axi_uart_top (\n"
        f"{ports_block}\n"
        ");\n"
        "  // TODO: instantiate submodules and wire top-level signals\n"
        "endmodule\n"
    )


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
            "target": "rtl/axi_uart_top.sv",
            "data_id": "shared_defs",
            "data_type": "RTLPackage",
            "transformation": "Package constants and typedefs feed top-level integration.",
        }
    ]
    rpg.base_classes = [
        {
            "file_path": "rtl/pkg/uart_pkg.sv",
            "code": "package uart_pkg;\n  typedef logic [7:0] uart_byte_t;\nendpackage\n",
        }
    ]
    return skeleton, rpg


def test_design_interfaces_tool_accepts_rtl_contracts():
    skeleton, rpg = _load_repo_objects()
    rtl_context = _load_rtl_context()
    env = SimpleNamespace(
        repo_rpg=rpg,
        repo_skeleton=skeleton,
        rtl_context=rtl_context,
        tgt_file_path="rtl/axi_uart_top.sv",
        tgt_units={
            "module:axi_uart_top": {
                "unit_kind": "rtl_module",
                "features": ["REQ-001", "PROP-001"],
            }
        },
        covered_units=set(),
        covered_features=set(),
    )

    result = asyncio.run(
        DesignInterfacesTool.execute(
            {
                "interfaces": [
                    {
                        "file_path": "rtl/axi_uart_top.sv",
                        "unit_name": "module:axi_uart_top",
                        "unit_kind": "rtl_module",
                        "features": ["REQ-001", "PROP-001"],
                        "spec": (
                            "module axi_uart_top contract: use clk and rst_n as the canonical top-level clock/reset, "
                            "expose the AXI-Lite external interface, route uart_rx/uart_tx pins, instantiate "
                            "axi_lite_regs/baud_gen/fifo_sync/uart_rx/uart_tx, and drive irq/status wiring."
                        ),
                        "code": _top_module_code_from_ports(rtl_context),
                    }
                ]
            },
            env=env,
        )
    )

    assert result.error is None
    assert result.state["covered_units"] == ["module:axi_uart_top"]


def test_design_interfaces_tool_rejects_top_module_missing_spec_ports():
    skeleton, rpg = _load_repo_objects()
    rtl_context = _load_rtl_context()
    missing_port = rtl_context["top_ports"][0]["name"]
    env = SimpleNamespace(
        repo_rpg=rpg,
        repo_skeleton=skeleton,
        rtl_context=rtl_context,
        tgt_file_path="rtl/axi_uart_top.sv",
        tgt_units={
            "module:axi_uart_top": {
                "unit_kind": "rtl_module",
                "features": ["REQ-001"],
            }
        },
        covered_units=set(),
        covered_features=set(),
    )

    result = asyncio.run(
        DesignInterfacesTool.execute(
            {
                "interfaces": [
                    {
                        "file_path": "rtl/axi_uart_top.sv",
                        "unit_name": "module:axi_uart_top",
                        "unit_kind": "rtl_module",
                        "features": ["REQ-001"],
                        "spec": (
                            "module axi_uart_top contract: use clk and rst_n as the canonical top-level clock/reset, "
                            "expose the AXI-Lite external interface, route uart_rx/uart_tx pins, and drive irq."
                        ),
                        "code": _top_module_code_from_ports(rtl_context, omit_port=missing_port),
                    }
                ]
            },
            env=env,
        )
    )

    assert result.error is not None
    assert "Missing ports" in result.error


def test_get_top_module_facts_prefers_explicit_top_ports_for_reset_name():
    rtl_context = {
        "top_module": "aes_cipher_top",
        "top_ports": [
            {"name": "clk", "direction": "input", "width_expr": 1, "domain": "clk", "desc": "Clock"},
            {"name": "rst", "direction": "input", "width_expr": 1, "domain": "clk", "desc": "Reset"},
            {"name": "done", "direction": "output", "width_expr": 1, "domain": "clk", "desc": "Done"},
        ],
        "top_params": [],
        "params": [],
        "default_params": [],
        "clock_reset": {
            "clock_port": "clk",
            "reset_port": "rst_n",
            "reset_polarity": "active-low",
            "reset_release": "sync",
        },
        "file_specs_by_path": {
            "aes_cipher_top.v": {
                "file_path": "aes_cipher_top.v",
                "file_kind": "rtl_top_module",
            }
        },
    }

    facts = _get_top_module_facts(rtl_context, "aes_cipher_top.v")

    assert facts["clock_port"] == "clk"
    assert facts["reset_port"] == "rst"
    assert facts["clock_reset"]["reset_port"] == "rst"


def test_design_interfaces_tool_custom_parse_repairs_double_brace_tool_call():
    raw = """
<tool_call>
{{
  "tool_name": "design_itfs_for_feature",
  "parameters": {
    "interfaces": [
      {
        "file_path": "rtl/axi_uart_top.sv",
        "unit_name": "module:axi_uart_top",
        "unit_kind": "rtl_module",
        "features": ["REQ-001"],
        "spec": "module axi_uart_top contract"
      }
    ]
  }
}}
</tool_call>
""".strip()

    parsed = DesignInterfacesTool.custom_parse(raw)

    assert len(parsed) == 1
    assert parsed[0]["interfaces"][0]["unit_name"] == "module:axi_uart_top"


def test_design_interfaces_tool_rejects_python_contracts_in_rtl_mode():
    skeleton, rpg = _load_repo_objects()
    rtl_context = _load_rtl_context()
    env = SimpleNamespace(
        repo_rpg=rpg,
        repo_skeleton=skeleton,
        rtl_context=rtl_context,
        tgt_file_path="scripts/run_sim.sh",
        tgt_units={
            "script:scripts/run_sim.sh": {
                "unit_kind": "script",
                "features": ["REQ-SIM-001"],
            }
        },
        covered_units=set(),
        covered_features=set(),
    )

    result = asyncio.run(
        DesignInterfacesTool.execute(
            {
                "interfaces": [
                    {
                        "file_path": "scripts/run_sim.sh",
                        "unit_name": "script:scripts/run_sim.sh",
                        "unit_kind": "script",
                        "spec": "def run_sim():\n    pass\n",
                        "code": "def run_sim():\n    pass\n",
                    }
                ]
            },
            env=env,
        )
    )

    assert result.error is not None
    assert "shell-script skeleton" in result.error or "Python-only constructs" in result.error


def test_design_interfaces_tool_requires_rtl_code_skeleton():
    skeleton, rpg = _load_repo_objects()
    rtl_context = _load_rtl_context()
    env = SimpleNamespace(
        repo_rpg=rpg,
        repo_skeleton=skeleton,
        rtl_context=rtl_context,
        tgt_file_path="rtl/pkg/uart_pkg.sv",
        tgt_units={
            "package:uart_pkg": {
                "unit_kind": "rtl_package",
                "features": [],
            }
        },
        covered_units=set(),
        covered_features=set(),
    )

    result = asyncio.run(
        DesignInterfacesTool.execute(
            {
                "interfaces": [
                    {
                        "file_path": "rtl/pkg/uart_pkg.sv",
                        "unit_name": "package:uart_pkg",
                        "unit_kind": "rtl_package",
                        "spec": "package uart_pkg contract: export UART constants and typedefs.",
                        "code": "",
                    }
                ]
            },
            env=env,
        )
    )

    assert result.error is not None
    assert "code skeleton" in result.error


def test_design_interfaces_tool_rejects_non_canonical_rtl_features():
    skeleton, rpg = _load_repo_objects()
    rtl_context = _load_rtl_context()
    env = SimpleNamespace(
        repo_rpg=rpg,
        repo_skeleton=skeleton,
        rtl_context=rtl_context,
        tgt_file_path="rtl/modules/uart_rx.sv",
        tgt_units={
            "module:uart_rx": {
                "unit_kind": "rtl_module",
                "features": ["REQ-003", "TEST-020", "TEST-022"],
                "trace_context": rtl_context["file_trace_context_by_path"]["rtl/modules/uart_rx.sv"],
                "secondary_context": rtl_context["file_secondary_context_by_path"]["rtl/modules/uart_rx.sv"],
            }
        },
        covered_units=set(),
        covered_features=set(),
    )

    result = asyncio.run(
        DesignInterfacesTool.execute(
            {
                "interfaces": [
                    {
                        "file_path": "rtl/modules/uart_rx.sv",
                        "unit_name": "module:uart_rx",
                        "unit_kind": "rtl_module",
                        "features": ["uart_rx_internal_state"],
                        "spec": "module uart_rx contract: receive UART serial data and push bytes into RX FIFO.",
                        "code": "module uart_rx(input logic clk, input logic rst_n);\nendmodule\n",
                    }
                ]
            },
            env=env,
        )
    )

    assert result.error is not None
    assert "canonical trace IDs" in result.error


def test_rtl_interface_agent_uses_module_contract_prompt():
    skeleton, rpg = _load_repo_objects()
    rtl_context = _load_rtl_context()
    file_node = skeleton.find_file("rtl/axi_uart_top.sv")
    env = InterfaceEnv(
        review_llm=object(),
        review_format=InterfaceReviewOutput,
        review_memory=Memory(),
        register_tools=[],
        repo_skeleton=skeleton,
        repo_rpg=rpg,
        rtl_context=rtl_context,
        tgt_file_path=file_node.path,
        tgt_subgraph_name=file_node.path,
    )
    agent = object.__new__(InterfaceAgent)
    agent.repo_skeleton = skeleton
    agent.repo_rpg = rpg
    agent.rtl_context = rtl_context
    agent.tgt_file_node = file_node
    agent.tgt_file_path = file_node.path
    agent.tgt_subgraph_name = file_node.path
    agent.logger = SimpleNamespace(info=lambda *args, **kwargs: None)
    agent._env = env

    captured = {}

    def fake_run(task, max_error_times, max_steps):
        captured["task"] = task
        return {"final_results": [], "is_terminate": True, "is_suc": True}

    agent.run = fake_run
    result = agent.design_file_interface(
        tgt_subtree_implemented=[],
        all_implemented_subtrees={},
        max_steps=1,
        max_retries=1,
    )

    assert result["success"] is False
    assert "module:axi_uart_top" in captured["task"]
    assert "Do NOT emit Python syntax" in captured["task"]
    assert "return BOTH a minimal contract (`spec`) and a minimal code skeleton (`code`)" in captured["task"]
    assert "=== Top Module Ports From Spec Facts ===" in captured["task"]
    assert "s_axi_awvalid" in captured["task"]
    assert "rst_n" in captured["task"]
    assert "Define interfaces only (imports + signature + docstring + `pass`)." not in captured["task"]


def test_design_itf_prompt_is_rtl_only():
    assert "Python Mode" not in DESIGN_ITF
    assert "Operating Modes" not in DESIGN_ITF
    assert "top_module" in DESIGN_ITF
    assert "implementation_summary" in DESIGN_ITF


def test_rtl_interface_agent_renders_native_skeleton_file_code():
    agent = object.__new__(InterfaceAgent)
    rendered = agent._render_rtl_skeletons(
        {
            "module:axi_uart_top": {
                "unit": {
                    "file_path": "rtl/axi_uart_top.sv",
                    "unit_name": "module:axi_uart_top",
                    "unit_kind": "rtl_module",
                    "spec": "module axi_uart_top contract",
                    "code": (
                        "module axi_uart_top (\n"
                        "  input logic clk,\n"
                        "  input logic rst_n\n"
                        ");\n"
                        "  // TODO: top-level integration\n"
                        "endmodule\n"
                    ),
                }
            }
        }
    )

    assert rendered.startswith("module axi_uart_top")
    assert "```" not in rendered
    assert rendered.rstrip().endswith("endmodule")


def test_rtl_interface_env_uses_code_skeleton_in_summary():
    skeleton, rpg = _load_repo_objects()
    rtl_context = _load_rtl_context()
    file_node = skeleton.find_file("rtl/axi_uart_top.sv")
    env = InterfaceEnv(
        review_llm=object(),
        review_format=InterfaceReviewOutput,
        review_memory=Memory(),
        register_tools=[],
        repo_skeleton=skeleton,
        repo_rpg=rpg,
        rtl_context=rtl_context,
        tgt_file_path=file_node.path,
        tgt_subgraph_name=file_node.path,
    )
    upstream_file = SimpleNamespace(
        path="rtl/modules/uart_tx.sv",
        code="module uart_tx;\n  // transmitter skeleton\nendmodule\n",
        feature_paths=[],
    )

    summary = env._format_implemented_summary([upstream_file], current_file="rtl/axi_uart_top.sv")

    assert "Code Skeleton" in summary
    assert "Contract Summary" not in summary


def test_rtl_interface_agent_helpers_avoid_python_feature_summary():
    skeleton, rpg = _load_repo_objects()
    rtl_context = _load_rtl_context()
    file_node = skeleton.find_file("rtl/axi_uart_top.sv")
    agent = object.__new__(InterfaceAgent)
    agent.repo_skeleton = skeleton
    agent.repo_rpg = rpg
    agent.rtl_context = rtl_context
    agent.tgt_file_node = file_node
    agent.tgt_file_path = file_node.path
    agent.tgt_subgraph_name = file_node.path
    agent.logger = SimpleNamespace(info=lambda *args, **kwargs: None)

    upstream_file = SimpleNamespace(
        path="rtl/modules/uart_tx.sv",
        code="module uart_tx;\n  // transmitter skeleton\nendmodule\n",
        feature_paths=["rtl_modules/files/uart_tx.sv/requirements/REQ-002"],
    )
    all_implemented = {"rtl/modules/uart_tx.sv": [upstream_file]}
    rtl_data_flow = [
        {
            "source": "rtl/modules/uart_tx.sv",
            "target": "rtl/axi_uart_top.sv",
            "data_id": "tx_module_integration",
            "data_type": "ModuleInstance",
            "transformation": "UART TX module is instantiated in the top-level design.",
        }
    ]

    upstream = agent._extract_upstream_context(
        rtl_data_flow,
        file_node.path,
        all_implemented,
    )
    summary = agent._format_implemented_summary([upstream_file], current_file=file_node.path)

    assert "### From file: `rtl/modules/uart_tx.sv`" in upstream
    assert "```systemverilog" in upstream
    assert "Features:" not in upstream
    assert "Associated Features" not in summary
    assert "```systemverilog" in summary


def test_task_batch_accepts_unit_to_spec_without_unit_to_code():
    batch = TaskBatch(
        task="Implement module contract",
        file_path="rtl/axi_uart_top.sv",
        units_key=["module:axi_uart_top"],
        unit_to_code={},
        unit_to_features={"module:axi_uart_top": ["REQ-001"]},
        unit_to_spec={"module:axi_uart_top": "module axi_uart_top contract"},
        unit_to_kind={"module:axi_uart_top": "rtl_module"},
    )

    payload = batch.to_dict()
    assert payload["unit_to_spec"]["module:axi_uart_top"] == "module axi_uart_top contract"
    assert payload["unit_to_kind"]["module:axi_uart_top"] == "rtl_module"


def test_func_designer_rtl_context_includes_top_level_spec_facts():
    repo_data = json.loads((FIXTURE_DIR / "repo_data.json").read_text(encoding="utf-8"))
    repo_data["_repo_data_path"] = str(FIXTURE_DIR / "repo_data.json")
    repo_data["_repo_data_dir"] = str(FIXTURE_DIR)
    skeleton = RepoSkeleton.load_json(FIXTURE_DIR / "skeleton.json")
    designer = FuncDesigner(repo_skeleton=skeleton, repo_data=repo_data)

    rtl_context = designer._build_rtl_dataflow_context()

    assert rtl_context["top_module"] == "axi_uart_top"
    assert len(rtl_context["top_ports"]) > 0
    assert rtl_context["clock_reset"]["clock_port"] == "clk"
    assert "README.md" not in rtl_context["component_names"]


def test_func_designer_rtl_context_includes_trace_catalog():
    repo_data = json.loads((FIXTURE_DIR / "repo_data.json").read_text(encoding="utf-8"))
    repo_data["_repo_data_path"] = str(FIXTURE_DIR / "repo_data.json")
    repo_data["_repo_data_dir"] = str(FIXTURE_DIR)
    skeleton = RepoSkeleton.load_json(FIXTURE_DIR / "skeleton.json")
    designer = FuncDesigner(repo_skeleton=skeleton, repo_data=repo_data)

    rtl_context = designer._build_rtl_dataflow_context()

    assert rtl_context["trace_catalog"]["REQ-003"]["summary"]
    assert rtl_context["file_trace_context_by_path"]["rtl/modules/uart_rx.sv"][0]["id"] == "REQ-003"


def test_interface_agent_rtl_units_include_trace_context():
    skeleton, rpg = _load_repo_objects()
    rtl_context = _load_rtl_context()
    file_node = skeleton.find_file("rtl/modules/uart_rx.sv")
    agent = object.__new__(InterfaceAgent)
    agent.repo_skeleton = skeleton
    agent.repo_rpg = rpg
    agent.rtl_context = rtl_context
    agent.tgt_file_node = file_node
    agent.tgt_file_path = file_node.path
    agent.tgt_subgraph_name = file_node.path
    agent.logger = SimpleNamespace(info=lambda *args, **kwargs: None)

    units = agent._build_rtl_units_for_file(file_node.path)
    unit = units["module:uart_rx"]

    assert unit["features"] == ["REQ-003", "TEST-020", "TEST-022"]
    assert unit["trace_context"][0]["summary"]
    assert unit["secondary_context"]["responsibility"]


def test_func_designer_rtl_context_includes_implementation_catalogs():
    repo_data = json.loads((FIXTURE_DIR / "repo_data.json").read_text(encoding="utf-8"))
    repo_data["_repo_data_path"] = str(FIXTURE_DIR / "repo_data.json")
    repo_data["_repo_data_dir"] = str(FIXTURE_DIR)
    skeleton = RepoSkeleton.load_json(FIXTURE_DIR / "skeleton.json")
    designer = FuncDesigner(repo_skeleton=skeleton, repo_data=repo_data)

    rtl_context = designer._build_rtl_dataflow_context()

    assert rtl_context["implementation_node_catalog"]["NODE-06"]["goal"]
    assert rtl_context["code_anchor_catalog"]["ANCHOR-003"]["purpose"]
    assert rtl_context["implementation_hint_catalog"]["HINT-011"]["statement"]
    uart_rx_context = rtl_context["file_implementation_context_by_path"]["rtl/modules/uart_rx.sv"]
    assert uart_rx_context["nodes"][0]["node_id"] == "Node-06"
    assert any(item["anchor_id"] == "ANCHOR-003" for item in uart_rx_context["anchors"])
    assert any(item["hint_id"] == "HINT-011" for item in uart_rx_context["hints"])


def test_interface_agent_rtl_units_include_implementation_context():
    skeleton, rpg = _load_repo_objects()
    rtl_context = _load_rtl_context()
    file_node = skeleton.find_file("rtl/modules/uart_rx.sv")
    agent = object.__new__(InterfaceAgent)
    agent.repo_skeleton = skeleton
    agent.repo_rpg = rpg
    agent.rtl_context = rtl_context
    agent.tgt_file_node = file_node
    agent.tgt_file_path = file_node.path
    agent.tgt_subgraph_name = file_node.path
    agent.logger = SimpleNamespace(info=lambda *args, **kwargs: None)

    units = agent._build_rtl_units_for_file(file_node.path)
    implementation_context = units["module:uart_rx"]["implementation_context"]

    assert implementation_context["nodes"][0]["node_id"] == "Node-06"
    assert any(item["anchor_id"] == "ANCHOR-003" for item in implementation_context["anchors"])
    assert any(item["hint_id"] == "HINT-011" for item in implementation_context["hints"])
