from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from zerorepo.rtl_impl.debug_agent.adapters import build_debug_contract_json
from zerorepo.rtl_impl.retrieval_agent import (
    BlockSpecRetriever,
    BlockSpecRetrievalResult,
    ModuleSpecContextRetriever,
)
from zerorepo.rtl_impl.module_planner.agents import (
    Stage1Agent,
    Stage2Agent,
    Stage3Agent,
    Stage4SpecBlocksAgent,
    Stage4ModulePlanAgent,
    Stage5Agent,
    Stage6MergeAgent,
)
import zerorepo.rtl_impl.module_planner.agents.global_defines as global_defines_mod
from zerorepo.rtl_impl.module_planner.agents.base import BaseStageAgent, validate_model
from zerorepo.rtl_impl.module_planner.module_organizer import (
    build_module_organized_artifact,
    build_module_organized_artifact_from_repo_skeleton,
    build_module_organized_artifact_from_repo_skeleton_only,
    build_stage2_planning_input,
    build_stage2_planning_input_from_task,
)
from zerorepo.rtl_impl.module_planner.planner_runner import PlannerRunner
from zerorepo.rtl_impl.module_planner.prompts import stage1_ingest_extract
from zerorepo.rtl_impl.module_planner.schemas import (
    ExtractedFact,
    ModuleOrganizationArtifact,
    PlannerTaskInput,
    Stage1FactLedger,
    Stage2PlanningInput,
    Stage3ModuleSkeletonArtifact,
    Stage1ContractsArtifact,
    Stage2RepoSkeletonArtifact,
    Stage4ModulePlansArtifact,
    Stage4SpecBlocksArtifact,
    Stage5CodegenArtifact,
    Stage6MergeArtifact,
)
from zerorepo.rtl_impl.module_planner.utils import (
    PlannerLLMClient,
    expand_markdown_inputs,
    extract_module_section,
    parse_module_skeleton_doc,
    split_spec_blocks,
)
from zerorepo.rtl_impl.module_planner.utils.llm_client import DefaultPlannerLLMBackend


class QueueBackend:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, *, system_prompt, user_prompt, images=None):
        return self.complete(system_prompt=system_prompt, user_prompt=user_prompt, images=images)

    def complete(self, *, system_prompt, user_prompt, images=None):
        self.calls.append(
            {
                "mode": "complete",
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "images": list(images or []),
            }
        )
        if not self.responses:
            raise AssertionError("No more queued responses for planner backend.")
        return self.responses.pop(0)

    def complete_with_memory(self, *, memory, images=None):
        history = memory.history
        system_prompt = next((item.content for item in history if item.role == "system"), "")
        user_prompt = next((item.content for item in reversed(history) if item.role == "user"), "")
        self.calls.append(
            {
                "mode": "complete_with_memory",
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "images": list(images or []),
                "memory": memory.to_dict(),
            }
        )
        if not self.responses:
            raise AssertionError("No more queued responses for planner backend.")
        return self.responses.pop(0)


class RecordingContextProvider:
    def __init__(self):
        self.calls = []

    def get_stage_context(self, stage_name, task_input, partial_artifacts):
        self.calls.append(stage_name)
        return {"stage_name": stage_name, "artifact_keys": sorted(partial_artifacts.keys())}


class RecordingSink:
    def __init__(self):
        self.calls = []

    def record_stage_output(self, stage_name, artifact, task_input):
        self.calls.append((stage_name, task_input.task_id))


class SimpleStageArtifact(BaseModel):
    value: int


class QualityRetryAgent(BaseStageAgent):
    stage_name = "quality_retry_demo"
    output_model = SimpleStageArtifact
    system_role = "test"
    max_quality_attempts = 5

    def build_prompt(self, task_input, partial_artifacts, stage_context):
        return "return a value", []

    def validate_quality(self, artifact, task_input, partial_artifacts):
        if artifact.value == 0:
            return []
        return [f"quality_error_{idx}" for idx in range(artifact.value)]


def drop_text_grounding(value):
    if isinstance(value, dict):
        return {
            key: drop_text_grounding(item)
            for key, item in value.items()
            if key != "text_grounding"
        }
    if isinstance(value, list):
        return [drop_text_grounding(item) for item in value]
    return value


def make_task_input(tmp_path: Path, image_count: int = 1) -> tuple[PlannerTaskInput, Path, list[Path]]:
    md_path = tmp_path / "aes_cipher_top.md"
    image_refs = []
    image_paths: list[Path] = []
    for index in range(1, image_count + 1):
        image_name = f"aes_fsm_{index}.png"
        image_refs.append(f"![FSM {index}]({image_name})")
        image_path = tmp_path / image_name
        image_path.write_bytes(b"\x89PNG\r\n\x1a\n")
        image_paths.append(image_path)

    md_path.write_text(
        "\n".join(
            [
                "# AES Demo Repository",
                "System: AES Demo Repository",
                "Top module: aes_cipher_top",
                "Files: aes_cipher_top.v, aes_key_expand_128.v",
                "Modules: aes_cipher_top, aes_key_expand_128",
                "",
                "## Interface",
                "Module: aes_cipher_top",
                "Ports:",
                "- clk: input, width 1, role clock",
                "- rst: input, width 1, role reset, active high",
                "- ld: input, width 1, role load_start",
                "- done: output, width 1, role completion",
                "Reset polarity: high",
                "Handshake: ld/start to done",
                "",
                "## Timing",
                "Module: aes_cipher_top",
                "The design is stateful.",
                "Input sampling: ld is sampled on the rising clock edge.",
                "Output timing: done is asserted for one cycle after the final round.",
                "Reset behavior: rst high returns the control to IDLE.",
                "",
                "## Control",
                "Module: aes_cipher_top",
                "States: IDLE, LOAD, ROUND_PROC, DONE",
                "Transition: IDLE -> LOAD when ld is asserted.",
                "Transition: LOAD -> ROUND_PROC after input capture.",
                "Transition: ROUND_PROC -> DONE after the final round.",
                "Control signal: done means completion pulse.",
                "",
                "## Datapath",
                "Module: aes_cipher_top",
                "Main flow: initial_addroundkey, subbytes, shiftrows, mixcolumns, addroundkey",
                "Intermediate object: state_reg is the current AES state.",
                "Path: state_reg -> subbytes_out is combinational.",
                "Path: mixcolumns_out -> state_reg is registered_update.",
                "",
                *image_refs,
                "",
                "## Submodules",
                "aes_key_expand_128 is an explicit helper block used by aes_cipher_top.",
            ]
        ),
        encoding="utf-8",
    )

    task = PlannerTaskInput(
        task_id="aes_demo_001",
        spec_md_files=[str(md_path)],
        spec_images=[str(path) for path in image_paths],
        project_type="light_repo_spec2rtl",
        notes="planner test",
    )
    return task, md_path, image_paths


def make_structure_payload(md_path: Path) -> dict:
    return {
        "structure_contract": {
            "system": "AES Demo Repository",
            "top_module": "aes_cipher_top",
            "files": ["aes_cipher_top.v", "aes_key_expand_128.v"],
            "modules": ["aes_cipher_top", "aes_key_expand_128"],
            "file_map": {
                "aes_cipher_top.v": ["aes_cipher_top"],
                "aes_key_expand_128.v": ["aes_key_expand_128"],
            },
            "hierarchy": [
                {
                    "parent": "aes_cipher_top",
                    "child": "aes_key_expand_128",
                    "text_grounding": [
                        {
                            "source_md_file": str(md_path.resolve()),
                            "section_path": "AES Demo Repository > Submodules",
                            "start_line_anchor": "aes_key_expand_128 is an explicit helper block used by aes_cipher_top.",
                            "end_line_anchor": "aes_key_expand_128 is an explicit helper block used by aes_cipher_top.",
                        }
                    ],
                    "image_grounding": [],
                }
            ],
            "instantiation_graph": [],
            "generation_order_candidate": [],
            "text_grounding": [
                {
                    "source_md_file": str(md_path.resolve()),
                    "section_path": "AES Demo Repository",
                    "start_line_anchor": "System: AES Demo Repository",
                    "end_line_anchor": "Modules: aes_cipher_top, aes_key_expand_128",
                }
            ],
            "image_grounding": [],
        }
    }


def make_interface_payload(md_path: Path) -> dict:
    return {
        "interface_contracts": [
            {
                "module": "aes_cipher_top",
                "ports": [
                    {
                        "name": "clk",
                        "direction": "input",
                        "width": "1",
                        "role": "clock",
                        "active": "",
                        "meaning": "clock input",
                    },
                    {
                        "name": "rst",
                        "direction": "input",
                        "width": "1",
                        "role": "reset",
                        "active": "high",
                        "meaning": "reset input",
                    },
                    {
                        "name": "ld",
                        "direction": "input",
                        "width": "1",
                        "role": "load_start",
                        "active": "",
                        "meaning": "load request",
                    },
                    {
                        "name": "done",
                        "direction": "output",
                        "width": "1",
                        "role": "completion",
                        "active": "",
                        "meaning": "completion pulse",
                    },
                ],
                "params": [],
                "clock": "clk",
                "reset": "rst",
                "reset_polarity": "high",
                "handshakes": ["ld/start to done"],
                "parameter_constraints": [],
                "bus_roles": [],
                "text_grounding": [
                    {
                        "source_md_file": str(md_path.resolve()),
                        "section_path": "AES Demo Repository > Interface",
                        "start_line_anchor": "Module: aes_cipher_top",
                        "end_line_anchor": "Handshake: ld/start to done",
                    }
                ],
                "image_grounding": [],
            }
        ]
    }


def make_timing_payload(md_path: Path, image_path: Path | None = None) -> dict:
    return {
        "timing_contracts": [
            {
                "module": "aes_cipher_top",
                "clocking": {
                    "clock": "clk",
                    "update_edge": "rising clock edge",
                    "statement": "ld is sampled on the rising clock edge",
                },
                "reset_behavior": {
                    "signal": "rst",
                    "active": "high",
                    "effect": "returns the control to IDLE",
                },
                "registered_objects": [
                    {
                        "name": "state_reg",
                        "timing_role": "state register",
                        "timing": "updated synchronously once per active round",
                    }
                ],
                "phase_timing": [
                    {
                        "phase": "DONE",
                        "timing": "done is asserted for one cycle after the final round",
                    }
                ],
                "timing_rules": [
                    "ld is sampled on the rising clock edge",
                    "done is asserted for one cycle after the final round",
                    "one round per clock cycle",
                ],
                "underspecified": [
                    "reset release timing is not specified",
                    *([] if image_path is None else ["state diagram image shows phases but not exact cycle counts"]),
                ],
            }
        ]
    }


def make_control_payload(md_path: Path, image_path: Path | None = None) -> dict:
    image_grounding = []
    if image_path is not None:
        image_grounding = [
            {
                "image_id": "IMG_001",
                "image_file": str(image_path.resolve()),
                "visible_text": ["IDLE", "LOAD", "ROUND_PROC", "DONE"],
            }
        ]
    return {
        "control_contracts": [
            {
                "module": "aes_cipher_top",
                "abstract_states": ["IDLE", "LOAD", "ROUND_PROC", "DONE"],
                "transitions": [
                    {
                        "from_state": "IDLE",
                        "to_state": "LOAD",
                        "condition": "ld is asserted",
                        "text_grounding": [
                            {
                                "source_md_file": str(md_path.resolve()),
                                "section_path": "AES Demo Repository > Control",
                                "start_line_anchor": "Transition: IDLE -> LOAD when ld is asserted.",
                                "end_line_anchor": "Transition: IDLE -> LOAD when ld is asserted.",
                            }
                        ],
                    }
                ],
                "control_signals": [
                    {
                        "name": "done",
                        "meaning": "completion pulse",
                        "text_grounding": [
                            {
                                "source_md_file": str(md_path.resolve()),
                                "section_path": "AES Demo Repository > Control",
                                "start_line_anchor": "Control signal: done means completion pulse.",
                                "end_line_anchor": "Control signal: done means completion pulse.",
                            }
                        ],
                    }
                ],
                "bypass_conditions": [],
                "exception_conditions": [],
                "counter_rules": [],
                "text_grounding": [
                    {
                        "source_md_file": str(md_path.resolve()),
                        "section_path": "AES Demo Repository > Control",
                        "start_line_anchor": "Module: aes_cipher_top",
                        "end_line_anchor": "Control signal: done means completion pulse.",
                    }
                ],
                "image_grounding": image_grounding,
            }
        ]
    }


def make_datapath_payload(md_path: Path) -> dict:
    return {
        "datapath_contracts": [
            {
                "module": "aes_cipher_top",
                "input_data": ["text_in", "key"],
                "main_flow": [
                    "initial_addroundkey",
                    "subbytes",
                    "shiftrows",
                    "mixcolumns",
                    "addroundkey",
                ],
                "intermediate_objects": [
                    {
                        "name": "state_reg",
                        "role": "current AES state",
                        "text_grounding": [
                            {
                                "source_md_file": str(md_path.resolve()),
                                "section_path": "AES Demo Repository > Datapath",
                                "start_line_anchor": "Intermediate object: state_reg is the current AES state.",
                                "end_line_anchor": "Intermediate object: state_reg is the current AES state.",
                            }
                        ],
                    }
                ],
                "path_annotations": [
                    {
                        "path": "state_reg -> subbytes_out",
                        "kind": "combinational",
                        "text_grounding": [
                            {
                                "source_md_file": str(md_path.resolve()),
                                "section_path": "AES Demo Repository > Datapath",
                                "start_line_anchor": "Path: state_reg -> subbytes_out is combinational.",
                                "end_line_anchor": "Path: state_reg -> subbytes_out is combinational.",
                            }
                        ],
                    },
                    {
                        "path": "mixcolumns_out -> state_reg",
                        "kind": "registered_update",
                        "text_grounding": [
                            {
                                "source_md_file": str(md_path.resolve()),
                                "section_path": "AES Demo Repository > Datapath",
                                "start_line_anchor": "Path: mixcolumns_out -> state_reg is registered_update.",
                                "end_line_anchor": "Path: mixcolumns_out -> state_reg is registered_update.",
                            }
                        ],
                    },
                ],
                "registered_paths": ["mixcolumns_out -> state_reg"],
                "combinational_paths": ["state_reg -> subbytes_out"],
                "special_paths": [],
                "text_grounding": [
                    {
                        "source_md_file": str(md_path.resolve()),
                        "section_path": "AES Demo Repository > Datapath",
                        "start_line_anchor": "Module: aes_cipher_top",
                        "end_line_anchor": "Path: mixcolumns_out -> state_reg is registered_update.",
                    }
                ],
                "image_grounding": [],
            }
        ]
    }


def make_planning_facts_payload(md_path: Path) -> dict:
    return {
        "planning_facts": [
            {
                "module": "aes_cipher_top",
                "registers": [
                    {"name": "state_reg", "width": "128", "role": "current AES state"},
                    {"name": "dcnt", "width": "4", "role": "round counter"},
                ],
                "state_names": ["IDLE", "LOAD", "ROUND_PROC", "DONE"],
                "submodule_facts": [
                    {"module": "aes_key_expand_128", "count": 1, "usage": "round key provider"}
                ],
                "local_mappings": ["text_in maps into state matrix in column-major order"],
                "text_grounding": [
                    {
                        "source_md_file": str(md_path.resolve()),
                        "section_path": "AES Demo Repository > Datapath",
                        "start_line_anchor": "Main flow: initial_addroundkey, subbytes, shiftrows, mixcolumns, addroundkey",
                        "end_line_anchor": "aes_key_expand_128 is an explicit helper block used by aes_cipher_top.",
                    }
                ],
                "image_grounding": [],
            }
        ]
    }


def make_module_structure_payload(module_name: str, md_path: Path, *, child: str = "") -> dict:
    hierarchy = []
    if child:
        hierarchy.append(
            {
                "parent": module_name,
                "child": child,
                "text_grounding": [
                    {
                        "source_md_file": str(md_path.resolve()),
                        "section_path": f"{module_name} > Submodules",
                        "start_line_anchor": f"{module_name} instantiates {child}.",
                        "end_line_anchor": f"{module_name} instantiates {child}.",
                    }
                ],
                "image_grounding": [],
            }
        )
    return {
        "structure_contract": {
            "system": "Batch Demo",
            "top_module": module_name if child else "",
            "files": [],
            "modules": [module_name, *([child] if child else [])],
            "file_map": {},
            "hierarchy": hierarchy,
            "instantiation_graph": [],
            "generation_order_candidate": [],
            "text_grounding": [
                {
                    "source_md_file": str(md_path.resolve()),
                    "section_path": module_name,
                    "start_line_anchor": f"Module: {module_name}",
                    "end_line_anchor": f"Module: {module_name}",
                }
            ],
            "image_grounding": [],
        }
    }


def make_minimal_interface_payload(module_name: str, md_path: Path) -> dict:
    return {
        "interface_contracts": [
            {
                "module": module_name,
                "ports": [
                    {"name": "clk", "direction": "input", "width": "1", "role": "clock", "active": "", "meaning": "clock"}
                ],
                "params": [],
                "clock": "clk",
                "reset": "",
                "reset_polarity": "",
                "handshakes": [],
                "parameter_constraints": [],
                "bus_roles": [],
                "text_grounding": [
                    {
                        "source_md_file": str(md_path.resolve()),
                        "section_path": f"{module_name} > Interface",
                        "start_line_anchor": "Ports:",
                        "end_line_anchor": "Ports:",
                    }
                ],
                "image_grounding": [],
            }
        ]
    }


def make_minimal_control_payload(module_name: str, md_path: Path) -> dict:
    return {
        "control_contracts": [
            {
                "module": module_name,
                "abstract_states": ["IDLE"],
                "transitions": [],
                "control_signals": [],
                "bypass_conditions": [],
                "exception_conditions": [],
                "counter_rules": [],
                "text_grounding": [
                    {
                        "source_md_file": str(md_path.resolve()),
                        "section_path": f"{module_name} > Control",
                        "start_line_anchor": "States: IDLE",
                        "end_line_anchor": "States: IDLE",
                    }
                ],
                "image_grounding": [],
            }
        ]
    }


def make_minimal_datapath_payload(module_name: str, md_path: Path) -> dict:
    return {
        "datapath_contracts": [
            {
                "module": module_name,
                "input_data": [],
                "main_flow": ["pass_through"],
                "intermediate_objects": [],
                "path_annotations": [],
                "registered_paths": [],
                "combinational_paths": [],
                "special_paths": [],
                "text_grounding": [
                    {
                        "source_md_file": str(md_path.resolve()),
                        "section_path": f"{module_name} > Datapath",
                        "start_line_anchor": "Main flow: pass_through",
                        "end_line_anchor": "Main flow: pass_through",
                    }
                ],
                "image_grounding": [],
            }
        ]
    }


def make_minimal_planning_facts_payload(module_name: str, md_path: Path, *, child: str = "") -> dict:
    submodule_facts = []
    if child:
        submodule_facts.append({"module": child, "count": 1, "usage": "child block"})
    return {
        "planning_facts": [
            {
                "module": module_name,
                "registers": [{"name": f"{module_name}_r", "width": "1", "role": "state"}],
                "state_names": ["IDLE"],
                "submodule_facts": submodule_facts,
                "local_mappings": [],
                "text_grounding": [
                    {
                        "source_md_file": str(md_path.resolve()),
                        "section_path": f"{module_name} > Planning",
                        "start_line_anchor": f"Module: {module_name}",
                        "end_line_anchor": f"Module: {module_name}",
                    }
                ],
                "image_grounding": [],
            }
        ]
    }


def make_empty_structure_payload() -> dict:
    return {
        "structure_contract": {
            "system": "",
            "top_module": "",
            "files": [],
            "modules": [],
            "file_map": {},
            "hierarchy": [],
            "instantiation_graph": [],
            "generation_order_candidate": [],
            "text_grounding": [],
            "image_grounding": [],
        }
    }


def make_stage1_contract_artifact(md_path: Path, image_paths: list[Path]) -> Stage1ContractsArtifact:
    artifact = validate_model(
        Stage1ContractsArtifact,
        {
            "task_id": "aes_demo_001",
            "stage1_status": "contracts_completed",
            "completed_rounds": ["facts"],
            "spec_index": {"aes_cipher_top": str(md_path)},
            **make_stage1_fact_payload(md_path),
        },
    )
    task = PlannerTaskInput(
        task_id="aes_demo_001",
        spec_md_files=[str(md_path)],
        spec_images=[str(item) for item in image_paths],
        project_type="light_repo_spec2rtl",
        notes="fixture",
    )
    return Stage1Agent(PlannerLLMClient(backend=QueueBackend([])))._finalize_structure_contract(artifact, task)


def make_repo_skeleton_payload() -> dict:
    return {
        "task_id": "aes_demo_001",
        "stage2_status": "repo_skeleton_planned",
        "top_module": "aes_cipher_top",
        "global_invariants": {
            "system_role": "AES encryption system with top-level control and iterative key expansion",
            "clocking_model": {
                "primary_clock": "clk",
                "reset_signal": "rst",
                "reset_style": "top-level active-high reset with shared clock domain",
            },
            "hierarchy": [
                {"parent": "aes_cipher_top", "child": "aes_key_expand_128"},
            ],
            "file_map": {
                "aes_cipher_top": "rtl/aes_cipher_top.v",
                "aes_key_expand_128": "rtl/aes_key_expand_128.v",
            },
            "cross_module_alignment": [
                "aes_cipher_top and aes_key_expand_128 share clk for coordinated round processing",
            ],
            "global_data_conventions": [
                "text_in is processed through the AES round flow before done is asserted",
            ],
        },
        "modules": [
            {
                "module": "aes_key_expand_128",
                "file_path": "rtl/aes_key_expand_128.v",
                "role": "iterative round-key provider",
                "kind": "iterative_engine",
                "parents": ["aes_cipher_top"],
                "children": [],
                "instance_hints": [],
                "repo_notes": [],
            },
            {
                "module": "aes_cipher_top",
                "file_path": "rtl/aes_cipher_top.v",
                "role": "top-level AES encryption controller",
                "kind": "top_controller",
                "parents": [],
                "children": ["aes_key_expand_128"],
                "instance_hints": [
                    {
                        "module": "aes_key_expand_128",
                        "count": 1,
                        "usage": "round key provider",
                    }
                ],
                "repo_notes": ["Owns top-level orchestration and helper integration."],
            },
        ],
        "planning_decisions": {
            "generation_order": ["aes_key_expand_128", "aes_cipher_top"],
            "leaf_first": True,
            "shared_modules": [],
            "top_level_integration_notes": [
                "Integrate round-key generation before top-level completion signaling.",
            ],
        },
        "open_issues": [],
    }


def make_module_spec_files(tmp_path: Path) -> tuple[Path, Path]:
    top_spec = tmp_path / "aes_cipher_top.md"
    key_spec = tmp_path / "aes_key_expand_128.md"
    top_spec.write_text(
        "\n".join(
            [
                "# aes_cipher_top",
                "TOP UNIQUE SPEC MARKER",
                "Controls AES round sequencing and completion behavior.",
            ]
        ),
        encoding="utf-8",
    )
    key_spec.write_text(
        "\n".join(
            [
                "# aes_key_expand_128",
                "KEYEXP UNIQUE SPEC MARKER",
                "Generates round keys iteratively for the top module.",
            ]
        ),
        encoding="utf-8",
    )
    return top_spec, key_spec


def make_stage3_module_skeleton_doc(module_name: str, spec_path: Path) -> str:
    control_style = "counter_driven" if module_name == "aes_cipher_top" else "mixed"
    semantic_modes = (
        [
            "  - IDLE: waits for load",
            "  - INIT_ROUND: captures input and applies initial keying",
            "  - ROUND_OP: advances normal rounds",
            "  - FINAL_ROUND: finishes output preparation",
            "  - DONE: exposes completion",
        ]
        if module_name == "aes_cipher_top"
        else [
            "  - KEY_LOAD: captures key material",
            "  - KEY_ADVANCE: iterates round-key generation",
            "  - KEY_DONE: exposes key availability",
        ]
    )
    state_object = "state_matrix" if module_name == "aes_cipher_top" else "round_key_reg"
    frame_block_markers = (
        [
            "// <block: decl_state_and_keys>",
            "// <block: inst_child_blocks>",
            "// <block: seq_control_or_commit>",
            "// <block: helper_mixcolumns_gf>",
            "// <block: seq_final_output_and_done>",
        ]
        if module_name == "aes_cipher_top"
        else [
            "// <block: decl_state_and_keys>",
            "// <block: inst_child_blocks>",
            "// <block: seq_control_or_commit>",
            "// <block: comb_output_path>",
        ]
    )
    helper_block = (
        "\n### Block\n"
        "- block_id: B4\n"
        "- block_label: helper_mixcolumns_gf\n"
        "- block_kind: helper\n"
        "- required: false\n"
        "- purpose: Provide local helper logic for GF arithmetic or indexing.\n"
        "- code_shape: function defs\n"
        "- depends_on: []\n"
        "- placeholder:\n"
        "```verilog\n"
        "function automatic [7:0] gf_mul2;\n"
        "    // helper body\n"
        "endfunction\n"
        "```\n"
        "- must_appear:\n"
        "  - local helper function or equivalent helper region\n"
        "- may_appear:\n"
        "  - index helpers\n"
        "- retrieval_focus:\n"
        "  - helper arithmetic details\n"
        if module_name == "aes_cipher_top"
        else ""
    )
    return "\n".join(
        [
            "# MODULE_SKELETON_DOC v1",
            "",
            "## 0. Module Identity",
            f"- module_name: {module_name}",
            f"- file_path: rtl/{module_name}.v",
            "- source_refs:",
            f"  - module_contract_ref: module_contracts_v1::{module_name}",
            f"  - repo_skeleton_ref: repo_skeleton_v1::{module_name}",
            f"  - spec_ref: {spec_path.name}",
            f"- planning_note: Build a pseudo-code-first skeleton for {module_name}.",
            "",
            "## 1. Module Frame",
            "```verilog",
            f"module {module_name} (",
            "    // ports",
            ");",
            "",
            *frame_block_markers,
            "",
            "endmodule",
            "```",
            "",
            "## 2. Structural Skeleton",
            "### Block",
            "- block_id: B1",
            "- block_label: decl_state_and_keys",
            "- block_kind: decl",
            "- required: true",
            "- purpose: Declare ports, state storage, child wiring, and datapath intermediates.",
            "- code_shape: declaration group",
            "- depends_on: []",
            "- placeholder:",
            "```verilog",
            "reg [127:0] state_reg;",
            "wire [127:0] child_data;",
            "```",
            "- must_appear:",
            "  - ports",
            "  - registered state or output objects",
            "- may_appear:",
            "  - intermediate combinational nets",
            "- retrieval_focus:",
            "  - module interface",
            "  - state representation",
            "",
            "### Block",
            "- block_id: B2",
            "- block_label: inst_child_blocks",
            "- block_kind: inst",
            "- required: true",
            "- purpose: Instantiate spec-supported child modules and route their interfaces.",
            "- code_shape: instantiation cluster",
            "- depends_on: [B1]",
            "- placeholder:",
            "```verilog",
            "// child instances",
            "```",
            "- must_appear:",
            "  - spec-supported child module wiring",
            "- may_appear:",
            "  - generate patterns",
            "- retrieval_focus:",
            "  - child modules",
            "  - instance multiplicity",
            "",
            "### Block",
            "- block_id: B3",
            "- block_label: seq_control_or_commit",
            "- block_kind: seq",
            "- required: true",
            "- purpose: Hold round progression, load synchronization, and registered updates.",
            "- code_shape: always block",
            "- depends_on: [B1, B2]",
            "- placeholder:",
            "```verilog",
            "always @(posedge clk) begin",
            "    // sequential updates",
            "end",
            "```",
            "- must_appear:",
            "  - sequential control or state commit behavior",
            "- may_appear:",
            "  - final output capture",
            "- retrieval_focus:",
            "  - timing and control",
            "  - registered updates",
            "",
            "### Block",
            "- block_id: B5",
            f"- block_label: {'seq_final_output_and_done' if module_name == 'aes_cipher_top' else 'comb_output_path'}",
            f"- block_kind: {'seq' if module_name == 'aes_cipher_top' else 'comb'}",
            "- required: true",
            "- purpose: Realize final data/output exposure with module-specific completion behavior.",
            f"- code_shape: {'always block' if module_name == 'aes_cipher_top' else 'assign cluster'}",
            "- depends_on: [B1, B2, B3]",
            "- placeholder:",
            "```verilog",
            "// final output path",
            "```",
            "- must_appear:",
            "  - final output realization",
            "- may_appear:",
            "  - done or valid signaling",
            "- retrieval_focus:",
            "  - output timing",
            "  - final-round behavior",
            helper_block,
            "",
            "## 3. Behavioral Overlay",
            "### Module-Level Behavioral Summary",
            f"- control_style: {control_style}",
            "- semantic_modes:",
            *semantic_modes,
            "- state_model:",
            f"  - object: {state_object}",
            "    storage_kind: registered",
            "    representation: packed vector",
            "    notes: primary stored representation for the module",
            "- global_invariants:",
            "  - block ordering is logical rather than mandatory code order",
            "  - child outputs should feed the planned core path",
            "- open_semantic_questions:",
            "  - exact low-level helper implementation may vary",
            "",
            "### Block Behavioral Overlay",
            "- block_id: B2",
            "- responsibilities:",
            "  - instantiate and connect child logic",
            "- timing_semantics:",
            "  - child outputs are consumed by downstream planned blocks",
            "- touched_objects:",
            "  - child outputs",
            "- coupling_rules:",
            "  - downstream round or output path depends on child outputs",
            "- forbidden_drift:",
            "  - do not invent unsupported child modules",
            "",
            "### Block Behavioral Overlay",
            f"- block_id: {'B5' if module_name == 'aes_cipher_top' else 'B3'}",
            "- responsibilities:",
            "  - realize externally visible completion/output behavior",
            "- timing_semantics:",
            "  - final-only behavior is isolated from generic iteration",
            "- touched_objects:",
            "  - output registers or output wires",
            "- coupling_rules:",
            "  - completion behavior must align with final data availability",
            "- forbidden_drift:",
            "  - do not expose outputs before the final path stabilizes",
            "",
            "## 4. Decision Ledger",
            "### Chosen Decision",
            "- topic: control style",
            "- decision: Keep semantic modes separate from the low-level code realization style.",
            "- reason: This avoids forcing an explicit FSM when counter- or flag-driven control is sufficient.",
            "",
            "### Deferred Decision",
            "- items:",
            "  - whether helper logic is best kept inline or as local helper definitions",
            "",
            "### Structural Risk",
            "- items:",
            "  - large combinational round logic may create a long path if over-collapsed",
            "",
            "### Behavioral Risk",
            "- items:",
            "  - completion signaling may drift if final-output handling is not kept explicit",
        ]
    )


def make_module_spec_context_payload(module_name: str, spec_path: Path, text: str | None = None) -> dict:
    source_text = text if text is not None else spec_path.read_text(encoding="utf-8")
    return {
        "schema_version": "module_spec_context_retrieval_v1",
        "module": module_name,
        "blocks": [
            {
                "block_id": "S001",
                "text": source_text.strip(),
                "source_file": str(spec_path.resolve()),
                "source_chunk_ids": [],
                "relevance_reason": [f"Use source text for {module_name}."],
                "confidence": "high",
            }
        ],
        "open_issues": [],
        "fallback_used": False,
        "fallback_reason": "",
    }


def make_stage4_module_plan_payload(module_name: str, top_module: bool = False) -> dict:
    block_specs = (
        [
            ("B1_decl_state_and_keys", "<block: decl_state_and_keys>"),
            ("B2_inst_child_blocks", "<block: inst_child_blocks>"),
            ("B3_seq_control_or_commit", "<block: seq_control_or_commit>"),
            ("B5_seq_final_output_and_done", "<block: seq_final_output_and_done>"),
            ("B4_helper_mixcolumns_gf", "<block: helper_mixcolumns_gf>"),
        ]
        if top_module
        else [
            ("B1_decl_state_and_keys", "<block: decl_state_and_keys>"),
            ("B2_inst_child_blocks", "<block: inst_child_blocks>"),
            ("B3_seq_control_or_commit", "<block: seq_control_or_commit>"),
            ("B5_comb_output_path", "<block: comb_output_path>"),
        ]
    )
    return {
        "schema_version": "module_plan_v1",
        "module": module_name,
        "subtasks": [
            {
                "id": block_id,
                "target": target,
                "description": f"Generate the code region for {block_id}.",
                "spec_refs": ["S001"],
                "constraints": [],
            }
            for block_id, target in block_specs
        ],
    }


def make_block_spec_retrieval_payload(module_name: str, top_module: bool = False) -> dict:
    plan_payload = make_stage4_module_plan_payload(module_name, top_module=top_module)
    return {
        "schema_version": "block_spec_retrieval_v1",
        "module": module_name,
        "selections": [
            {
                "id": subtask["id"],
                "target": subtask["target"],
                "spec_refs": list(subtask["spec_refs"]),
                "selection_reason": [f"Use S001 for {subtask['id']}."],
            }
            for subtask in plan_payload["subtasks"]
        ],
        "fallback_used": False,
        "fallback_reason": "",
    }


def make_stage5_code_payload(task_id: str, module_name: str, subtask: dict, code: str | None = None) -> dict:
    return {
        "task_id": task_id,
        "module": module_name,
        "subtask_id": subtask["id"],
        "target": subtask["target"],
        "spec_refs": list(subtask["spec_refs"]),
        "code": code or f"// generated fragment for {module_name} {subtask['id']}",
    }


def make_stage6_module_code(module_name: str) -> str:
    return "\n".join(
        [
            f"module {module_name} (",
            "    input wire a,",
            "    output wire y",
            ");",
            "assign y = a;",
            "endmodule",
        ]
    )


def make_merge_context_retrieval_payload(module_name: str, spec_refs: list[str] | None = None) -> dict:
    return {
        "schema_version": "merge_context_retrieval_v1",
        "module": module_name,
        "selected_spec_refs": spec_refs or ["S001"],
        "use_kg_child_context": False,
        "kg_child_modules": [],
        "kg_child_context_reason": "No child context needed for this test.",
        "code_gap_notes": [],
        "selection_reason": ["Use selected spec blocks for merge."],
        "fallback_used": False,
    }


def test_build_module_organized_artifact_groups_contracts_by_module(tmp_path):
    _, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    stage1_artifact = make_stage1_contract_artifact(md_path, image_paths)

    organized = build_module_organized_artifact(stage1_artifact)

    assert isinstance(organized, ModuleOrganizationArtifact)
    assert organized.top_module == "aes_cipher_top"
    assert organized.module_order == ["aes_cipher_top", "aes_key_expand_128"]
    assert organized.modules[0].is_top_module is True
    assert organized.modules[0].interface_contract is not None
    assert organized.modules[0].timing_contract is not None
    assert organized.modules[0].control_contract is not None
    assert organized.modules[0].datapath_contract is not None
    assert organized.modules[0].planning_facts is not None
    assert organized.modules[0].planning_facts.registers[0].name == "state_reg"
    assert organized.modules[1].module == "aes_key_expand_128"
    assert organized.modules[1].control_contract is None
    assert organized.modules[1].planning_facts is None


def _fact_grounding(md_path: Path, anchor: str) -> list[dict]:
    return [
        {
            "source_md_file": str(md_path.resolve()),
            "section_path": "AES Demo Repository",
            "start_line_anchor": anchor,
            "end_line_anchor": anchor,
        }
    ]


def _fact(
    md_path: Path,
    *,
    module: str,
    category: str,
    subject: str,
    predicate: str,
    obj: dict,
    source_kind: str = "explicit_text",
    notes: str = "",
) -> dict:
    return {
        "fact_id": "",
        "module": module,
        "category": category,
        "subject": subject,
        "predicate": predicate,
        "object": obj,
        "source_kind": source_kind,
        "text_grounding": _fact_grounding(md_path, subject),
        "image_grounding": [],
        "notes": notes,
    }


def make_stage1_fact_payload(md_path: Path) -> dict:
    facts = [
        _fact(
            md_path,
            module="aes_cipher_top",
            category="module_identity",
            subject="aes_cipher_top",
            predicate="is_top_module",
            obj={
                "system": "AES Demo Repository",
                "module": "aes_cipher_top",
                "modules": ["aes_cipher_top", "aes_key_expand_128"],
                "files": ["aes_cipher_top.v", "aes_key_expand_128.v"],
                "file_map": {
                    "aes_cipher_top.v": ["aes_cipher_top"],
                    "aes_key_expand_128.v": ["aes_key_expand_128"],
                },
            },
        ),
        *[
            _fact(
                md_path,
                module="aes_cipher_top",
                category="interface",
                subject=name,
                predicate="is_port",
                obj={"name": name, "direction": direction, "width": "1", "role": role, **extra},
                source_kind="table_row",
            )
            for name, direction, role, extra in [
                ("clk", "input", "clock", {}),
                ("rst", "input", "reset", {"active": "high"}),
                ("ld", "input", "load_start", {}),
                ("done", "output", "completion", {}),
            ]
        ],
        _fact(
            md_path,
            module="aes_cipher_top",
            category="register",
            subject="state_reg",
            predicate="is_register",
            obj={"name": "state_reg", "width": "128", "role": "current AES state"},
        ),
        _fact(
            md_path,
            module="aes_cipher_top",
            category="register",
            subject="dcnt",
            predicate="is_register",
            obj={"name": "dcnt", "width": "4", "role": "round counter"},
        ),
        _fact(
            md_path,
            module="aes_cipher_top",
            category="state_machine",
            subject="control states",
            predicate="has_states",
            obj={"states": ["IDLE", "LOAD", "ROUND_PROC", "DONE"]},
        ),
        _fact(
            md_path,
            module="aes_cipher_top",
            category="timing",
            subject="input sampling",
            predicate="states_rule",
            obj={
                "clocking": {
                    "clock": "clk",
                    "update_edge": "rising clock edge",
                    "statement": "ld is sampled on the rising clock edge",
                },
                "reset_behavior": {
                    "signal": "rst",
                    "active": "high",
                    "effect": "returns the control to IDLE",
                },
                "timing_rules": [
                    "ld is sampled on the rising clock edge",
                    "done is asserted for one cycle after the final round",
                    "one round per clock cycle",
                ],
                "registered_objects": [
                    {
                        "name": "state_reg",
                        "timing_role": "state register",
                        "timing": "updated synchronously once per active round",
                    }
                ],
            },
        ),
        _fact(
            md_path,
            module="aes_cipher_top",
            category="datapath",
            subject="round flow",
            predicate="has_main_flow",
            obj={
                "input_data": ["text_in", "key"],
                "main_flow": ["initial_addroundkey", "subbytes", "shiftrows", "mixcolumns", "addroundkey"],
                "intermediate_object": "state_reg",
                "role": "current AES state",
                "registered_paths": ["mixcolumns_out -> state_reg"],
                "combinational_paths": ["state_reg -> subbytes_out"],
                "mapping": "text_in maps into state matrix in column-major order",
            },
        ),
        _fact(
            md_path,
            module="aes_cipher_top",
            category="module_identity",
            subject="aes_key_expand_128",
            predicate="contains",
            obj={"parent": "aes_cipher_top", "child": "aes_key_expand_128"},
        ),
        _fact(
            md_path,
            module="aes_cipher_top",
            category="data_dependency",
            subject="round key",
            predicate="uses_provider_output",
            obj={"data": "round key", "provider": "aes_key_expand_128"},
        ),
    ]
    return {"fact_ledger": {"source_files": [str(md_path.resolve())], "facts": facts, "ambiguous_items": []}}


def test_extracted_fact_requires_grounding_and_accepts_flexible_object(tmp_path):
    _, md_path, _ = make_task_input(tmp_path)

    fact = ExtractedFact.model_validate(
        _fact(
            md_path,
            module="aes_cipher_top",
            category="resource_requirement",
            subject="SubBytes",
            predicate="uses_parallel_units",
            obj={"unit": "S-box", "count": 16, "extra": {"shape": "parallel"}},
        )
    )

    assert fact.object["extra"]["shape"] == "parallel"
    # Grounding is no longer required; facts without grounding are accepted.
    fact_no_grounding = ExtractedFact.model_validate(
        {
            "module": "aes_cipher_top",
            "category": "interface",
            "subject": "clk",
            "predicate": "is_port",
            "object": {"name": "clk"},
            "source_kind": "explicit_text",
        }
    )
    assert fact_no_grounding.subject == "clk"


def test_stage1_fact_ledger_projects_legacy_contracts_without_inferred_hierarchy(tmp_path):
    task, md_path, _ = make_task_input(tmp_path)
    facts = [
        _fact(
            md_path,
            module="aes_cipher_top",
            category="module_identity",
            subject="aes_cipher_top",
            predicate="is_top_module",
            obj={"module": "aes_cipher_top", "modules": ["aes_cipher_top", "aes_sbox"]},
        ),
        _fact(
            md_path,
            module="aes_cipher_top",
            category="interface",
            subject="clk",
            predicate="is_port",
            obj={"name": "clk", "direction": "input", "width": "1", "role": "clock"},
            source_kind="table_row",
        ),
        _fact(
            md_path,
            module="aes_cipher_top",
            category="register",
            subject="dcnt",
            predicate="is_register",
            obj={"name": "dcnt", "width": "4", "role": "round counter"},
            source_kind="table_row",
        ),
        _fact(
            md_path,
            module="aes_cipher_top",
            category="state_machine",
            subject="control states",
            predicate="has_states",
            obj={"states": ["IDLE", "ROUND_OP", "DONE"]},
        ),
        _fact(
            md_path,
            module="aes_cipher_top",
            category="timing",
            subject="round timing",
            predicate="states_rule",
            obj={"statement": "one round per clock cycle"},
        ),
        _fact(
            md_path,
            module="aes_cipher_top",
            category="datapath",
            subject="round flow",
            predicate="has_main_flow",
            obj={"main_flow": ["SubBytes", "ShiftRows", "MixColumns", "AddRoundKey"]},
        ),
        _fact(
            md_path,
            module="aes_cipher_top",
            category="resource_requirement",
            subject="SubBytes",
            predicate="uses_parallel_units",
            obj={"unit": "S-box", "count": 16},
            notes="Do not infer hierarchy in stage1.",
        ),
        _fact(
            md_path,
            module="aes_cipher_top",
            category="data_dependency",
            subject="AddRoundKey",
            predicate="uses_provider_output",
            obj={"data": "round key", "provider": "key expansion module"},
            notes="Do not infer key expansion ports in stage1.",
        ),
    ]
    backend = QueueBackend([{"fact_ledger": {"source_files": [str(md_path.resolve())], "facts": facts, "ambiguous_items": []}}])
    agent = Stage1Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run_incremental(task, {})

    assert artifact.completed_rounds == ["facts"]
    assert artifact.fact_ledger.facts[0].fact_id == "F0001"
    assert artifact.structure_contract.top_module == "aes_cipher_top"
    assert "aes_sbox" in artifact.structure_contract.modules
    assert artifact.interface_contracts[0].ports[0].name == "clk"
    assert artifact.planning_facts[0].registers[0].name == "dcnt"
    assert artifact.control_contracts[0].abstract_states == ["IDLE", "ROUND_OP", "DONE"]
    assert artifact.timing_contracts[0].timing_rules == ["one round per clock cycle"]
    assert artifact.datapath_contracts[0].main_flow == ["SubBytes", "ShiftRows", "MixColumns", "AddRoundKey"]
    assert artifact.structure_contract.hierarchy == []
    assert artifact.structure_contract.instantiation_graph == []


def test_module_organizer_passes_fact_ledger_to_modules_json(tmp_path):
    task, md_path, _ = make_task_input(tmp_path)
    ledger = Stage1FactLedger.model_validate(
        {
            "source_files": [str(md_path.resolve())],
            "facts": [
                _fact(
                    md_path,
                    module="aes_cipher_top",
                    category="module_identity",
                    subject="aes_cipher_top",
                    predicate="is_top_module",
                    obj={"module": "aes_cipher_top"},
                )
            ],
            "ambiguous_items": [],
        }
    )
    artifact = Stage1ContractsArtifact(
        task_id=task.task_id,
        stage1_status="contracts_completed",
        completed_rounds=["facts"],
        spec_index={"aes_cipher_top": str(md_path)},
        fact_ledger=ledger,
    )
    agent = Stage1Agent(PlannerLLMClient(backend=QueueBackend([])))
    artifact = agent._finalize_structure_contract(artifact, task)

    organized = build_module_organized_artifact(artifact)

    assert organized.fact_ledger.facts[0].fact_id == "F0001"
    assert organized.modules[0].facts[0].category == "module_identity"


def test_base_stage_agent_uses_up_to_five_quality_attempts_and_returns_best_effort():
    backend = QueueBackend([{"value": 5}, {"value": 4}, {"value": 3}, {"value": 2}, {"value": 1}])
    agent = QualityRetryAgent(PlannerLLMClient(backend=backend))

    artifact = agent.run(task_input={"task_id": "demo"}, partial_artifacts={})

    assert artifact.value == 1
    assert len(backend.calls) == 5


def test_expand_markdown_inputs_recurses_directories_and_sorts(tmp_path):
    specs = tmp_path / "specs"
    nested = specs / "nested"
    nested.mkdir(parents=True)
    b_path = specs / "b.md"
    a_path = nested / "a.md"
    ignored = nested / "ignored.txt"
    b_path.write_text("# B\n", encoding="utf-8")
    a_path.write_text("# A\n", encoding="utf-8")
    ignored.write_text("ignore", encoding="utf-8")

    expanded = expand_markdown_inputs([str(specs), str(a_path)])

    assert expanded == sorted({str(a_path.resolve()), str(b_path.resolve())})


def test_stage1_agent_runs_facts_round_without_alias_groups(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    backend = QueueBackend([make_stage1_fact_payload(md_path)])
    context_provider = RecordingContextProvider()
    sink = RecordingSink()
    agent = Stage1Agent(
        PlannerLLMClient(backend=backend),
        context_provider=context_provider,
        artifact_sink=sink,
    )

    artifact = agent.run(task, {})

    assert isinstance(artifact, Stage1ContractsArtifact)
    assert artifact.stage1_status == "contracts_completed"
    assert artifact.completed_rounds == ["facts"]
    assert artifact.completed_batches == ["batch_0001"]
    assert artifact.structure_contract.top_module == "aes_cipher_top"
    assert artifact.interface_contracts[0].ports[0].name == "clk"
    assert artifact.timing_contracts[0].clocking["clock"] == "clk"
    assert artifact.control_contracts[0].abstract_states == ["IDLE", "LOAD", "ROUND_PROC", "DONE"]
    assert artifact.datapath_contracts[0].main_flow[0] == "initial_addroundkey"
    assert artifact.planning_facts[0].registers[0].name == "state_reg"
    assert len(backend.calls) == 1
    assert "Stage1 round: facts" in backend.calls[0]["user_prompt"]
    assert "image_contracts" not in artifact.model_dump()
    assert "entity_alias_groups" not in artifact.model_dump()
    assert context_provider.calls == ["stage1_contracts"]
    assert sink.calls == [("stage1_contracts", "aes_demo_001")]


def test_stage1_agent_batches_directory_specs_and_reduces_hierarchy(tmp_path):
    specs_dir = tmp_path / "batch_specs"
    specs_dir.mkdir()
    module_paths = []
    for index in range(1, 7):
        module_name = f"mod_{index}"
        md_path = specs_dir / f"{module_name}.md"
        md_path.write_text(
            "\n".join(
                [
                    f"# {module_name}",
                    f"Module: {module_name}",
                    "Ports:",
                    "- clk: input, width 1, role clock",
                    "States: IDLE",
                    "Main flow: pass_through",
                    *(["mod_1 instantiates mod_6."] if module_name == "mod_1" else []),
                ]
            ),
            encoding="utf-8",
        )
        module_paths.append(md_path)

    # Build module_identity facts for every module so they appear in
    # structure_contract.modules even after spec_index.keys() is no longer
    # treated as a module-name source.
    def _batch_facts(batch_paths, extra_facts=()):
        return [
            *[
                _fact(
                    p,
                    module=p.stem,
                    category="module_identity",
                    subject=p.stem,
                    predicate="is_module",
                    obj={"name": p.stem},
                )
                for p in batch_paths
            ],
            *extra_facts,
        ]

    responses = [
        {
            "fact_ledger": {
                "source_files": [str(p.resolve()) for p in module_paths[:5]],
                "facts": _batch_facts(
                    module_paths[:5],
                    extra_facts=[
                        _fact(
                            module_paths[0],
                            module="mod_1",
                            category="module_identity",
                            subject="mod_1",
                            predicate="contains",
                            obj={"parent": "mod_1", "child": "mod_6"},
                        )
                    ],
                ),
                "ambiguous_items": [],
            }
        },
        {
            "fact_ledger": {
                "source_files": [str(module_paths[5].resolve())],
                "facts": _batch_facts([module_paths[5]]),
                "ambiguous_items": [],
            }
        },
    ]
    task = PlannerTaskInput(
        task_id="mod_1_demo",
        spec_md_files=[str(specs_dir)],
        spec_images=[],
        project_type="light_repo_spec2rtl",
        notes="batch test",
    )
    backend = QueueBackend(responses)
    agent = Stage1Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run(task, {})

    assert artifact.completed_batches == ["batch_0001", "batch_0002"]
    assert list(artifact.spec_index) == [f"mod_{index}" for index in range(1, 7)]
    assert set(artifact.structure_contract.modules) == {f"mod_{index}" for index in range(1, 7)}
    assert [(item.parent, item.child) for item in artifact.structure_contract.hierarchy] == [("mod_1", "mod_6")]
    assert artifact.structure_contract.generation_order_candidate.index("mod_6") < artifact.structure_contract.generation_order_candidate.index("mod_1")
    assert len(backend.calls) == 2
    assert backend.calls[0]["user_prompt"].count("[Document DOC_") == 5
    assert backend.calls[1]["user_prompt"].count("[Document DOC_") == 1
    organized = build_module_organized_artifact(artifact)
    assert organized.module_order[:6] == [f"mod_{index}" for index in range(1, 7)]


def test_stage1_agent_facts_prompt_includes_current_contracts_context(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    backend = QueueBackend([make_stage1_fact_payload(md_path)])
    agent = Stage1Agent(PlannerLLMClient(backend=backend))

    agent.run(task, {})

    assert len(backend.calls) == 1
    assert '"schema_version": "stage1_contracts_v1"' in backend.calls[0]["user_prompt"]
    assert "Return JSON with exactly one key: `fact_ledger`" in backend.calls[0]["user_prompt"]
    assert "interface_contracts" in backend.calls[0]["user_prompt"]


def test_stage1_agent_projected_interface_contract_uses_module_level_grounding_only(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    backend = QueueBackend([make_stage1_fact_payload(md_path)])
    agent = Stage1Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run(task, {})
    dumped = artifact.model_dump()

    assert dumped["interface_contracts"][0]["text_grounding"]
    assert "text_grounding" not in dumped["interface_contracts"][0]["ports"][0]


def test_stage1_agent_projects_timing_facts_from_fact_ledger(tmp_path):
    md_path = tmp_path / "control_only.md"
    md_path.write_text(
        "\n".join(
            [
                "# Control Only Demo",
                "## Timing",
                "Module: aes_cipher_top",
                "done is asserted when processing finishes.",
                "The controller returns to IDLE after completion.",
            ]
        ),
        encoding="utf-8",
    )
    task = PlannerTaskInput(
        task_id="control_only_demo",
        spec_md_files=[str(md_path)],
        spec_images=[],
        project_type="light_repo_spec2rtl",
        notes="timing validator test",
    )
    backend = QueueBackend(
        [
            {
                "fact_ledger": {
                    "source_files": [str(md_path.resolve())],
                    "facts": [
                        _fact(
                            md_path,
                            module="aes_cipher_top",
                            category="timing",
                            subject="completion",
                            predicate="states_rule",
                            obj={"phase_timing": [{"phase": "completion", "timing": "done is asserted when processing finishes"}]},
                        )
                    ],
                    "ambiguous_items": [],
                }
            }
        ]
    )
    agent = Stage1Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run(task, {})

    assert len(artifact.timing_contracts) == 1
    assert artifact.timing_contracts[0].phase_timing[0]["phase"] == "completion"
    assert len(backend.calls) == 1
    assert "Stage 1 now produces a flexible evidence-backed fact ledger" in backend.calls[0]["user_prompt"]


def test_stage1_agent_accepts_ungrounded_fact_without_retry(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    backend = QueueBackend(
        [
            {
                "fact_ledger": {
                    "source_files": [str(md_path.resolve())],
                    "facts": [
                        {
                            "module": "aes_cipher_top",
                            "category": "timing",
                            "subject": "clocking",
                            "predicate": "states_rule",
                            "object": {"statement": "register updates on rising edge"},
                            "source_kind": "explicit_text",
                            "text_grounding": [],
                            "image_grounding": [],
                        }
                    ],
                    "ambiguous_items": [],
                }
            },
        ]
    )
    agent = Stage1Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run(task, {})

    # Ungrounded facts are now accepted without retry — only 1 LLM call.
    assert len(backend.calls) == 1


def test_stage1_facts_prompt_replaces_old_timing_prompt():
    prompt = stage1_ingest_extract.build_facts_prompt(
        document_markdown="# Demo",
        current_contracts_json='{"fact_ledger": {"facts": []}}',
        stage_context="{}",
    )

    assert "Return JSON with exactly one key: `fact_ledger`" in prompt
    assert "resource_requirement" in prompt
    assert "data_dependency" in prompt
    assert not hasattr(stage1_ingest_extract, "build_timing_prompt")


def test_stage1_agent_ignores_spec_images_and_runs_text_facts_round_only(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=2)
    backend = QueueBackend([make_stage1_fact_payload(md_path)])
    agent = Stage1Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run(task, {})

    assert len(backend.calls) == 1
    assert all(call["images"] == [] for call in backend.calls)
    assert artifact.completed_rounds == ["facts"]
    assert "image_contracts" not in artifact.model_dump()


def test_stage1_agent_leaves_missing_information_blank(tmp_path):
    md_path = tmp_path / "empty.md"
    md_path.write_text("# Blank Spec\n", encoding="utf-8")
    task = PlannerTaskInput(
        task_id="blank_demo",
        spec_md_files=[str(md_path)],
        spec_images=[],
        project_type="light_repo_spec2rtl",
        notes="blank test",
    )
    backend = QueueBackend(
        [
            {
                "fact_ledger": {
                    "source_files": [str(md_path.resolve())],
                    "facts": [],
                    "ambiguous_items": [],
                }
            }
        ]
    )
    agent = Stage1Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run(task, {})

    assert artifact.structure_contract.top_module == ""
    assert artifact.structure_contract.modules == []
    assert artifact.interface_contracts == []
    assert artifact.planning_facts == []
    assert artifact.completed_rounds == ["facts"]
    assert "image_contracts" not in artifact.model_dump()

def test_planner_runner_writes_contracts_json_and_resume_reuses_it(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    output_root = tmp_path / "outputs"
    backend = QueueBackend([])
    runner = PlannerRunner(output_root=output_root, llm_backend=backend, temporal_planning_enabled=False)

    first = runner.run(task, end_stage="stage1")
    second = runner.run(task, resume=True, end_stage="stage1")

    target = output_root / "contracts.json"
    modules_target = output_root / "modules.json"
    assert target.exists()
    assert not modules_target.exists()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["stage1_status"] == "contracts_completed"
    assert payload["completed_rounds"] == ["facts"]
    assert "image_contracts" not in payload
    assert "entity_alias_groups" not in payload
    assert payload["fact_ledger"]["source_files"] == [str(md_path.resolve())]
    assert payload["fact_ledger"]["facts"] == []
    assert payload["planning_facts"] == []
    assert first.completed_rounds == second.completed_rounds
    assert len(backend.calls) == 0


def test_planner_runner_resume_continues_from_partial_contracts_json(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    output_root = tmp_path / "outputs"
    output_root.mkdir(parents=True, exist_ok=True)
    partial_payload = {
        "task_id": task.task_id,
        "stage1_status": "interface_completed",
        "completed_rounds": ["structure", "interface"],
        "fact_ledger": {"source_files": [], "facts": [], "ambiguous_items": []},
    }
    partial_payload = drop_text_grounding(partial_payload)
    (output_root / "contracts.json").write_text(json.dumps(partial_payload, indent=2), encoding="utf-8")

    backend = QueueBackend([])
    runner = PlannerRunner(output_root=output_root, llm_backend=backend, temporal_planning_enabled=False)

    artifact = runner.run(task, resume=True, end_stage="stage1")

    assert artifact.completed_rounds == ["facts"]
    assert artifact.fact_ledger.facts == []
    assert len(backend.calls) == 0


def test_planner_runner_resume_ignores_legacy_six_round_contracts_json(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    output_root = tmp_path / "outputs"
    output_root.mkdir(parents=True, exist_ok=True)
    legacy_payload = {
        "task_id": task.task_id,
        "stage1_status": "contracts_completed",
        "completed_rounds": ["structure", "interface", "timing", "control", "datapath", "planning_facts"],
        **make_structure_payload(md_path),
        **make_interface_payload(md_path),
        "timing_contracts": [
            {
                "module": "aes_cipher_top",
                "clocking": {},
                "reset_behavior": {},
                "registered_objects": [],
                "phase_timing": [],
                "timing_rules": [],
                "underspecified": [],
            }
        ],
        **make_control_payload(md_path, image_paths[0]),
        **make_datapath_payload(md_path),
        **make_planning_facts_payload(md_path),
    }
    legacy_payload = drop_text_grounding(legacy_payload)
    (output_root / "contracts.json").write_text(json.dumps(legacy_payload, indent=2), encoding="utf-8")

    backend = QueueBackend([])
    runner = PlannerRunner(output_root=output_root, llm_backend=backend, temporal_planning_enabled=False)

    artifact = runner.run(task, resume=True, end_stage="stage1")

    assert artifact.timing_contracts == []
    assert artifact.completed_rounds == ["facts"]
    assert len(backend.calls) == 0


def test_planner_runner_writes_repo_skeleton_for_stage2(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    output_root = tmp_path / "outputs"
    backend = QueueBackend([make_repo_skeleton_payload()])
    runner = PlannerRunner(output_root=output_root, llm_backend=backend, temporal_planning_enabled=False)

    artifact = runner.run(task, end_stage="stage2")

    target = output_root / "repo_skeleton.json"
    assert isinstance(artifact, Stage2RepoSkeletonArtifact)
    assert target.exists()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["stage2_status"] == "repo_skeleton_planned"
    assert payload["top_module"] == "aes_cipher_top"
    assert "module_order" not in payload
    assert payload["planning_decisions"]["generation_order"] == ["aes_key_expand_128", "aes_cipher_top"]
    assert len(backend.calls) == 1
    assert not (output_root / "contracts.json").exists()


def test_planner_runner_resume_reuses_repo_skeleton_json(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    output_root = tmp_path / "outputs"
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "repo_skeleton.json").write_text(
        json.dumps(make_repo_skeleton_payload(), indent=2),
        encoding="utf-8",
    )
    backend = QueueBackend([])
    runner = PlannerRunner(output_root=output_root, llm_backend=backend, temporal_planning_enabled=False)

    artifact = runner.run(task, resume=True, end_stage="stage2")

    assert isinstance(artifact, Stage2RepoSkeletonArtifact)
    assert artifact.stage2_status == "repo_skeleton_planned"
    assert len(backend.calls) == 0


def test_planner_runner_resume_reruns_facts_when_legacy_partial_rounds_exist(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    output_root = tmp_path / "outputs"
    output_root.mkdir(parents=True, exist_ok=True)
    partial_payload = {
        "task_id": task.task_id,
        "stage1_status": "datapath_completed",
        "completed_rounds": ["structure", "interface", "timing", "control", "datapath"],
        "fact_ledger": {"source_files": [], "facts": [], "ambiguous_items": []},
    }
    partial_payload = drop_text_grounding(partial_payload)
    (output_root / "contracts.json").write_text(json.dumps(partial_payload, indent=2), encoding="utf-8")

    backend = QueueBackend([])
    runner = PlannerRunner(output_root=output_root, llm_backend=backend, temporal_planning_enabled=False)

    artifact = runner.run(task, resume=True, end_stage="stage1")

    assert artifact.completed_rounds == ["facts"]
    assert artifact.planning_facts == []
    assert len(backend.calls) == 0


def test_planner_runner_writes_incremental_contract_statuses(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    output_root = tmp_path / "outputs"
    backend = QueueBackend([])
    runner = PlannerRunner(output_root=output_root, llm_backend=backend, temporal_planning_enabled=False)

    writes = []
    original_write_payload = runner._write_payload

    def recording_write(payload):
        writes.append(payload.get("stage1_status"))
        return original_write_payload(payload)

    runner._write_payload = recording_write
    runner.run(task, end_stage="stage1")

    assert writes == ["contracts_completed"]


def test_planner_runner_supports_stage3_execution(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    top_spec, key_spec = make_module_spec_files(tmp_path)
    top_spec.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    backend = QueueBackend(
        [
            make_repo_skeleton_payload(),
            make_module_spec_context_payload("aes_key_expand_128", key_spec),
            make_stage3_module_skeleton_doc("aes_key_expand_128", key_spec),
            make_module_spec_context_payload("aes_cipher_top", top_spec),
            make_stage3_module_skeleton_doc("aes_cipher_top", top_spec),
        ]
    )
    runner = PlannerRunner(
        output_root=tmp_path / "outputs",
        llm_backend=backend,
        temporal_planning_enabled=False,
    )

    artifact = runner.run(task, end_stage="stage3")

    assert isinstance(artifact, Stage3ModuleSkeletonArtifact)
    assert artifact.stage3_status == "module_skeletons_planned"
    assert (tmp_path / "outputs" / "module_skeletons.json").exists()
    assert (tmp_path / "outputs" / "module_skeleton_docs" / "aes_cipher_top.md").exists()
    assert (tmp_path / "outputs" / "module_skeleton_json" / "aes_cipher_top.json").exists()


def make_toy_block_spec_inputs():
    module_spec = {
        "module": "toy",
        "source_spec_file": "toy.md",
        "blocks": [
            {
                "block_id": "S001",
                "text": "**Interface**\n\n| Signal Name | Direction | Width |\n| --- | --- | --- |\n| a | input | 8 |\n| y | output | 8 |",
            },
            {"block_id": "S002", "text": "**Operation**\n\nOutput y is computed from input a."},
        ],
    }
    skeleton_blocks = [
        {
            "block_id": "B1",
            "block_label": "decl_ports",
            "block_kind": "decl",
            "target": "<block: decl_ports>",
            "raw_text": "Declare module ports.",
        },
        {
            "block_id": "B2",
            "block_label": "comb_output",
            "block_kind": "comb",
            "target": "<block: comb_output>",
            "raw_text": "Drive y from a.",
        },
    ]
    return module_spec, skeleton_blocks


def test_block_spec_retriever_returns_valid_selection():
    module_spec, skeleton_blocks = make_toy_block_spec_inputs()
    payload = {
        "schema_version": "block_spec_retrieval_v1",
        "module": "toy",
        "selections": [
            {
                "id": "B1_decl_ports",
                "target": "<block: decl_ports>",
                "spec_refs": ["S001"],
                "selection_reason": ["Interface block is needed for declarations."],
            },
            {
                "id": "B2_comb_output",
                "target": "<block: comb_output>",
                "spec_refs": ["S002"],
                "selection_reason": ["Operation block defines output behavior."],
            },
        ],
        "fallback_used": False,
        "fallback_reason": "",
    }
    backend = QueueBackend([payload])
    retriever = BlockSpecRetriever(PlannerLLMClient(backend=backend))

    result = retriever.select_block_spec_refs(
        module_name="toy",
        module_spec=module_spec,
        module_skeleton="module toy; // <block: decl_ports> // <block: comb_output>",
        skeleton_blocks=skeleton_blocks,
    )

    assert isinstance(result, BlockSpecRetrievalResult)
    assert result.fallback_used is False
    assert result.selections[0].spec_refs == ["S001"]
    assert result.selections[1].spec_refs == ["S002"]


def test_block_spec_retriever_falls_back_on_unknown_ref():
    module_spec, skeleton_blocks = make_toy_block_spec_inputs()
    payload = {
        "schema_version": "block_spec_retrieval_v1",
        "module": "toy",
        "selections": [
            {"id": "B1_decl_ports", "target": "<block: decl_ports>", "spec_refs": ["S999"]},
            {"id": "B2_comb_output", "target": "<block: comb_output>", "spec_refs": ["S002"]},
        ],
        "fallback_used": False,
        "fallback_reason": "",
    }
    retriever = BlockSpecRetriever(PlannerLLMClient(backend=QueueBackend([payload])))

    result = retriever.select_block_spec_refs(
        module_name="toy",
        module_spec=module_spec,
        module_skeleton="module toy;",
        skeleton_blocks=skeleton_blocks,
    )

    assert result.fallback_used is True
    assert [selection.spec_refs for selection in result.selections] == [["S001", "S002"], ["S001", "S002"]]


def test_block_spec_retriever_falls_back_when_interface_missing():
    module_spec, skeleton_blocks = make_toy_block_spec_inputs()
    payload = {
        "schema_version": "block_spec_retrieval_v1",
        "module": "toy",
        "selections": [
            {"id": "B1_decl_ports", "target": "<block: decl_ports>", "spec_refs": ["S002"]},
            {"id": "B2_comb_output", "target": "<block: comb_output>", "spec_refs": ["S002"]},
        ],
        "fallback_used": False,
        "fallback_reason": "",
    }
    retriever = BlockSpecRetriever(PlannerLLMClient(backend=QueueBackend([payload])))

    result = retriever.select_block_spec_refs(
        module_name="toy",
        module_spec=module_spec,
        module_skeleton="module toy;",
        skeleton_blocks=skeleton_blocks,
    )

    assert result.fallback_used is True
    assert result.selections[0].spec_refs == ["S001", "S002"]


def test_block_spec_retriever_falls_back_on_selection_order_mismatch():
    module_spec, skeleton_blocks = make_toy_block_spec_inputs()
    payload = {
        "schema_version": "block_spec_retrieval_v1",
        "module": "toy",
        "selections": [
            {"id": "B2_comb_output", "target": "<block: comb_output>", "spec_refs": ["S002"]},
            {"id": "B1_decl_ports", "target": "<block: decl_ports>", "spec_refs": ["S001"]},
        ],
        "fallback_used": False,
        "fallback_reason": "",
    }
    retriever = BlockSpecRetriever(PlannerLLMClient(backend=QueueBackend([payload])))

    result = retriever.select_block_spec_refs(
        module_name="toy",
        module_spec=module_spec,
        module_skeleton="module toy;",
        skeleton_blocks=skeleton_blocks,
    )

    assert result.fallback_used is True
    assert [selection.id for selection in result.selections] == ["B1_decl_ports", "B2_comb_output"]


def test_planner_runner_supports_stage4_spec_block_splitting(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    top_spec, key_spec = make_module_spec_files(tmp_path)
    top_spec.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    key_spec.write_text(
        "\n".join(
            [
                "**aes_key_expand_128 Design Specification**",
                "",
                "**1. Introduction**",
                "KEYEXP UNIQUE SPEC MARKER",
                "",
                "**4.1 Basic Principle**",
                "Generates round keys iteratively for the top module.",
            ]
        ),
        encoding="utf-8",
    )
    backend = QueueBackend(
        [
            make_repo_skeleton_payload(),
            make_module_spec_context_payload("aes_key_expand_128", key_spec),
            make_stage3_module_skeleton_doc("aes_key_expand_128", key_spec),
            make_module_spec_context_payload("aes_cipher_top", top_spec),
            make_stage3_module_skeleton_doc("aes_cipher_top", top_spec),
            make_block_spec_retrieval_payload("aes_key_expand_128"),
            make_stage4_module_plan_payload("aes_key_expand_128"),
            make_block_spec_retrieval_payload("aes_cipher_top", top_module=True),
            make_stage4_module_plan_payload("aes_cipher_top", top_module=True),
        ]
    )
    output_root = tmp_path / "outputs"
    runner = PlannerRunner(output_root=output_root, llm_backend=backend, temporal_planning_enabled=False)

    artifact = runner.run(task, end_stage="stage4")

    assert isinstance(artifact, Stage4ModulePlansArtifact)
    assert artifact.schema_version == "module_plans_v1"
    assert artifact.module_order == ["aes_key_expand_128", "aes_cipher_top"]
    assert [item.module for item in artifact.module_plan_files] == artifact.module_order
    spec_blocks_target = output_root / "spec_blocks.json"
    module_plans_target = output_root / "module_plans.json"
    key_plan_target = output_root / "module_plan_json" / "aes_key_expand_128.json"
    key_retrieval_target = output_root / "block_spec_retrieval_json" / "aes_key_expand_128.json"
    key_spec_context_target = output_root / "module_spec_context_json" / "aes_key_expand_128.json"
    assert spec_blocks_target.exists()
    assert module_plans_target.exists()
    assert key_plan_target.exists()
    assert key_retrieval_target.exists()
    assert key_spec_context_target.exists()
    spec_payload = json.loads(spec_blocks_target.read_text(encoding="utf-8"))
    plan_payload = json.loads(key_plan_target.read_text(encoding="utf-8"))
    retrieval_payload = json.loads(key_retrieval_target.read_text(encoding="utf-8"))
    assert spec_payload["modules"][0]["blocks"][0]["block_id"] == "S001"
    assert "KEYEXP UNIQUE SPEC MARKER" in spec_payload["modules"][0]["blocks"][0]["text"]
    assert plan_payload["subtasks"][0]["target"] == "<block: decl_state_and_keys>"
    assert retrieval_payload["schema_version"] == "block_spec_retrieval_v1"
    assert "MODULE_SKELETON_DOC v1" in backend.calls[5]["user_prompt"]
    assert "KEYEXP UNIQUE SPEC MARKER" in backend.calls[5]["user_prompt"]
    assert len(backend.calls) == 9


def test_stage4_spec_blocks_reuses_stage3_spec_context_sidecar(tmp_path):
    spec_path = tmp_path / "toy.md"
    spec_path.write_text("# Toy Spec\n", encoding="utf-8")
    output_root = tmp_path / "outputs"
    spec_context_dir = output_root / "module_spec_context_json"
    spec_context_dir.mkdir(parents=True)
    spec_context_file = spec_context_dir / "toy.json"
    spec_context_file.write_text(
        json.dumps(
            {
                "schema_version": "module_spec_context_retrieval_v1",
                "module": "toy",
                "blocks": [
                    {
                        "block_id": "S001",
                        "text": "## Interface\nToy has input a and output y.\n\n## Operation\nOutput y follows input a.",
                        "source_file": str(spec_path.resolve()),
                        "source_chunk_ids": ["C001"],
                        "relevance_reason": ["Cached broad retrieval."],
                        "confidence": "high",
                    }
                ],
                "open_issues": [],
                "fallback_used": False,
                "fallback_reason": "",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    task = PlannerTaskInput(
        task_id="toy_task",
        spec_md_files=[str(spec_path)],
        spec_images=[],
        project_type="light_repo_spec2rtl",
    )
    stage2_artifact = validate_model(
        Stage2RepoSkeletonArtifact,
        {
            "task_id": task.task_id,
            "stage2_status": "repo_skeleton_planned",
            "top_module": "toy",
            "global_invariants": {"hierarchy": [], "file_map": {"toy": "rtl/toy.v"}},
            "modules": [
                {
                    "module": "toy",
                    "file_path": "rtl/toy.v",
                    "role": "toy passthrough",
                    "kind": "leaf_combinational",
                    "parents": [],
                    "children": [],
                    "instance_hints": [],
                }
            ],
            "planning_decisions": {
                "generation_order": ["toy"],
                "leaf_first": True,
                "shared_modules": [],
            },
            "open_issues": [],
        },
    )
    stage3_artifact = validate_model(
        Stage3ModuleSkeletonArtifact,
        {
            "task_id": task.task_id,
            "stage3_status": "module_skeletons_planned",
            "top_module": "toy",
            "module_order": ["toy"],
            "completed_modules": ["toy"],
            "resume_cursor": 1,
            "global_summary": [],
            "module_records": [
                {
                    "module": "toy",
                    "doc_file": "module_skeleton_docs/toy.md",
                    "export_file": "module_skeleton_json/toy.json",
                    "spec_context_file": "module_spec_context_json/toy.json",
                    "export_schema_version": "module_skeleton_export_v1",
                    "source_refs": {
                        "module_contract_ref": "module_contracts_v1::toy",
                        "repo_skeleton_ref": "repo_skeleton_v1::toy",
                        "module_spec_file": str(spec_path.resolve()),
                    },
                    "planning_note": "Toy skeleton.",
                    "block_ids": ["B1"],
                }
            ],
            "open_issues": [],
        },
    )

    class ExplodingRetriever:
        def select_module_spec_context(self, **kwargs):
            raise AssertionError("Stage4 should reuse the Stage3 spec context sidecar")

    backend = QueueBackend([])
    agent = Stage4SpecBlocksAgent(
        PlannerLLMClient(backend=backend),
        output_root=output_root,
        module_spec_context_retriever=ExplodingRetriever(),
    )

    artifact = agent.run(task, {"stage2": stage2_artifact, "stage3": stage3_artifact})

    assert backend.calls == []
    assert artifact.modules[0].source_spec_file == str(spec_path.resolve())
    assert [block.block_id for block in artifact.modules[0].blocks] == ["S001", "S002"]
    assert "Toy has input a" in artifact.modules[0].blocks[0].text
    assert "Output y follows input a" in artifact.modules[0].blocks[1].text


def test_stage4_spec_blocks_falls_back_for_legacy_stage3_without_sidecar(tmp_path):
    spec_path = tmp_path / "toy.md"
    spec_path.write_text("## Operation\nLegacy fallback source text.", encoding="utf-8")
    task = PlannerTaskInput(
        task_id="toy_task",
        spec_md_files=[str(spec_path)],
        spec_images=[],
        project_type="light_repo_spec2rtl",
    )
    stage2_artifact = validate_model(
        Stage2RepoSkeletonArtifact,
        {
            "task_id": task.task_id,
            "stage2_status": "repo_skeleton_planned",
            "top_module": "toy",
            "global_invariants": {"hierarchy": [], "file_map": {"toy": "rtl/toy.v"}},
            "modules": [
                {
                    "module": "toy",
                    "file_path": "rtl/toy.v",
                    "role": "toy passthrough",
                    "kind": "leaf_combinational",
                    "parents": [],
                    "children": [],
                    "instance_hints": [],
                }
            ],
            "planning_decisions": {
                "generation_order": ["toy"],
                "leaf_first": True,
                "shared_modules": [],
            },
            "open_issues": [],
        },
    )
    stage3_artifact = validate_model(
        Stage3ModuleSkeletonArtifact,
        {
            "task_id": task.task_id,
            "stage3_status": "module_skeletons_planned",
            "top_module": "toy",
            "module_order": ["toy"],
            "completed_modules": ["toy"],
            "resume_cursor": 1,
            "global_summary": [],
            "module_records": [
                {
                    "module": "toy",
                    "doc_file": "module_skeleton_docs/toy.md",
                    "export_file": "module_skeleton_json/toy.json",
                    "export_schema_version": "module_skeleton_export_v1",
                    "source_refs": {
                        "module_contract_ref": "module_contracts_v1::toy",
                        "repo_skeleton_ref": "repo_skeleton_v1::toy",
                        "module_spec_file": str(spec_path.resolve()),
                    },
                    "planning_note": "Legacy skeleton record.",
                    "block_ids": ["B1"],
                }
            ],
            "open_issues": [],
        },
    )
    backend = QueueBackend([make_module_spec_context_payload("toy", spec_path)])
    agent = Stage4SpecBlocksAgent(PlannerLLMClient(backend=backend))

    artifact = agent.run(task, {"stage2": stage2_artifact, "stage3": stage3_artifact})

    assert len(backend.calls) == 1
    assert "Legacy fallback source text" in artifact.modules[0].blocks[0].text


def test_stage4_module_plan_requires_interface_refs_for_first_decl_block(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    output_root = tmp_path / "outputs"
    skeleton_dir = output_root / "module_skeleton_docs"
    skeleton_dir.mkdir(parents=True)
    skeleton_doc = "\n".join(
        [
            "# MODULE_SKELETON_DOC v1",
            "",
            "## 1. Module Frame",
            "```verilog",
            "module toy (",
            "    // port list placeholder: input [7:0] a, output [7:0] y",
            ");",
            "// <block: decl_table>",
            "// <block: comb_output>",
            "endmodule",
            "```",
            "",
            "## 2. Structural Skeleton",
            "### Block",
            "- block_id: B1",
            "- block_label: decl_table",
            "- block_kind: decl",
            "- required: true",
            "- purpose: Declare table and module ports.",
            "- code_shape: declaration group",
            "- depends_on: []",
            "- placeholder:",
            "```verilog",
            "// declarations",
            "```",
            "- must_appear:",
            "  - input a",
            "  - output y",
            "- may_appear: []",
            "- retrieval_focus:",
            "  - interface",
            "",
            "### Block",
            "- block_id: B2",
            "- block_label: comb_output",
            "- block_kind: comb",
            "- required: true",
            "- purpose: Drive output y from input a.",
            "- code_shape: assign",
            "- depends_on: [B1]",
            "- placeholder:",
            "```verilog",
            "// output assignment",
            "```",
            "- must_appear:",
            "  - output y",
            "- may_appear: []",
            "- retrieval_focus:",
            "  - output port",
        ]
    )
    (skeleton_dir / "toy.md").write_text(skeleton_doc, encoding="utf-8")
    stage3 = {
        "schema_version": "stage3_skeleton_docs_v1",
        "task_id": task.task_id,
        "stage3_status": "module_skeletons_planned",
        "top_module": "toy",
        "module_order": ["toy"],
        "completed_modules": ["toy"],
        "global_summary": [],
        "module_records": [
            {
                "module": "toy",
                "doc_file": "module_skeleton_docs/toy.md",
                "export_file": "module_skeleton_json/toy.json",
                "source_refs": {
                    "module_contract_ref": "module_contracts_v1::toy",
                    "repo_skeleton_ref": "repo_skeleton_v1::toy",
                    "module_spec_file": "toy.md",
                },
                "block_ids": ["B1", "B2"],
            }
        ],
        "open_issues": [],
    }
    spec_blocks = {
        "schema_version": "spec_blocks_v1",
        "task_id": task.task_id,
        "module_order": ["toy"],
        "modules": [
            {
                "module": "toy",
                "source_spec_file": "toy.md",
                "blocks": [
                    {
                        "block_id": "S001",
                        "text": "**3. Interface**\n\n| Signal Name | Direction | Width | Description |\n| --- | --- | --- | --- |\n| a | input | 8 | Input byte |\n| y | output | 8 | Output byte |",
                    },
                    {
                        "block_id": "S002",
                        "text": "**4. Operation**\n\nOutput y is computed from input a.",
                    },
                ],
            }
        ],
    }
    bad_plan = {
        "schema_version": "module_plan_v1",
        "module": "toy",
        "subtasks": [
            {
                "id": "B1_decl_table",
                "target": "<block: decl_table>",
                "description": "Declare the lookup table.",
                "spec_refs": ["S002"],
                "constraints": [],
            },
            {
                "id": "B2_comb_output",
                "target": "<block: comb_output>",
                "description": "Drive output y from input a.",
                "spec_refs": ["S002"],
                "constraints": [],
            },
        ],
    }
    retrieval_payload = {
        "schema_version": "block_spec_retrieval_v1",
        "module": "toy",
        "selections": [
            {
                "id": "B1_decl_table",
                "target": "<block: decl_table>",
                "spec_refs": ["S001", "S002"],
                "selection_reason": ["Declaration needs interface and table behavior."],
            },
            {
                "id": "B2_comb_output",
                "target": "<block: comb_output>",
                "spec_refs": ["S002"],
                "selection_reason": ["Operation block defines output behavior."],
            },
        ],
        "fallback_used": False,
        "fallback_reason": "",
    }
    fixed_plan = {
        "schema_version": "module_plan_v1",
        "module": "toy",
        "subtasks": [
            {
                "id": "B1_decl_table",
                "target": "<block: decl_table>",
                "description": "Declare ports using the interface spec and declare the lookup table.",
                "spec_refs": ["S001", "S002"],
                "constraints": ["Port directions and widths must match the interface table."],
            },
            {
                "id": "B2_comb_output",
                "target": "<block: comb_output>",
                "description": "Drive output y from input a using the declared interface ports.",
                "spec_refs": ["S002"],
                "constraints": [],
            },
        ],
    }
    backend = QueueBackend([retrieval_payload, bad_plan, fixed_plan])
    agent = Stage4ModulePlanAgent(PlannerLLMClient(backend=backend), output_root=output_root)

    artifact = agent.run_incremental(task, {"stage3": stage3, "spec_blocks": spec_blocks})

    assert isinstance(artifact, Stage4ModulePlansArtifact)
    assert len(backend.calls) == 3
    assert '"id": "B1_decl_table"' in backend.calls[1]["user_prompt"]
    assert '"S001"' in backend.calls[1]["user_prompt"]
    assert '"S002"' in backend.calls[1]["user_prompt"]
    assert "spec_refs must exactly match block retrieval output ['S001', 'S002']" in backend.calls[2]["user_prompt"]


def test_stage5_agent_uses_spec_blocks_module_order_and_selected_refs(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    output_root = tmp_path / ".zerorepo" / "module_planner" / "outputs"
    plan_dir = output_root / "module_plan_json"
    plan_dir.mkdir(parents=True)
    mod_a_plan = {
        "schema_version": "module_plan_v1",
        "module": "mod_a",
        "subtasks": [
            {
                "id": "B1_a",
                "target": "<block: B1_a>",
                "description": "Generate mod_a fragment.",
                "spec_refs": ["S001"],
                "constraints": [],
            }
        ],
    }
    mod_b_plan = {
        "schema_version": "module_plan_v1",
        "module": "mod_b",
        "subtasks": [
            {
                "id": "B1_b",
                "target": "<block: B1_b>",
                "description": "Generate mod_b fragment.",
                "spec_refs": ["S002"],
                "constraints": [],
            }
        ],
    }
    (plan_dir / "mod_a.json").write_text(json.dumps(mod_a_plan), encoding="utf-8")
    (plan_dir / "mod_b.json").write_text(json.dumps(mod_b_plan), encoding="utf-8")
    stage4 = {
        "schema_version": "module_plans_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a", "mod_b"],
        "module_plan_files": [
            {"module": "mod_a", "plan_file": "module_plan_json/mod_a.json"},
            {"module": "mod_b", "plan_file": "module_plan_json/mod_b.json"},
        ],
    }
    spec_blocks = {
        "schema_version": "spec_blocks_v1",
        "task_id": task.task_id,
        "module_order": ["mod_b", "mod_a"],
        "modules": [
            {
                "module": "mod_b",
                "source_spec_file": "mod_b.md",
                "blocks": [
                    {"block_id": "S001", "text": "B_UNUSED_SPEC"},
                    {"block_id": "S002", "text": "B_SELECTED_SPEC"},
                ],
            },
            {
                "module": "mod_a",
                "source_spec_file": "mod_a.md",
                "blocks": [
                    {"block_id": "S001", "text": "A_SELECTED_SPEC"},
                ],
            },
        ],
    }
    backend = QueueBackend(
        [
            make_stage5_code_payload(task.task_id, "mod_b", mod_b_plan["subtasks"][0], "assign b = 1'b1;"),
            make_stage5_code_payload(task.task_id, "mod_a", mod_a_plan["subtasks"][0], "assign a = 1'b1;"),
        ]
    )
    agent = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output_root)

    artifact = agent.run_incremental(task, {"stage4": stage4, "spec_blocks": spec_blocks})

    assert isinstance(artifact, Stage5CodegenArtifact)
    assert artifact.module_order == ["mod_b", "mod_a"]
    assert [record.module for record in artifact.module_files] == ["mod_b", "mod_a"]
    assert "B_SELECTED_SPEC" in backend.calls[0]["user_prompt"]
    assert "B_UNUSED_SPEC" not in backend.calls[0]["user_prompt"]
    workspace_root = tmp_path / ".zerorepo" / "workspace"
    assert artifact.module_files[0].workspace_file.endswith("workspace/fragments/mod_b_fragments.v")
    assert (workspace_root / "fragments" / "mod_b_fragments.v").read_text(encoding="utf-8").find("assign b") >= 0
    assert (workspace_root / "fragments" / "mod_a_fragments.v").read_text(encoding="utf-8").find("assign a") >= 0


def test_stage5_agent_repairs_markdown_fenced_code(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    output_root = tmp_path / ".zerorepo" / "module_planner" / "outputs"
    plan_dir = output_root / "module_plan_json"
    plan_dir.mkdir(parents=True)
    plan = {
        "schema_version": "module_plan_v1",
        "module": "mod_a",
        "subtasks": [
            {
                "id": "B1_a",
                "target": "<block: B1_a>",
                "description": "Generate mod_a fragment.",
                "spec_refs": ["S001"],
                "constraints": [],
            }
        ],
    }
    (plan_dir / "mod_a.json").write_text(json.dumps(plan), encoding="utf-8")
    stage4 = {
        "schema_version": "module_plans_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "module_plan_files": [{"module": "mod_a", "plan_file": "module_plan_json/mod_a.json"}],
    }
    spec_blocks = {
        "schema_version": "spec_blocks_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "modules": [
            {
                "module": "mod_a",
                "source_spec_file": "mod_a.md",
                "blocks": [{"block_id": "S001", "text": "A_SELECTED_SPEC"}],
            }
        ],
    }
    backend = QueueBackend(
        [
            make_stage5_code_payload(task.task_id, "mod_a", plan["subtasks"][0], "```verilog\nassign a = 1'b0;\n```"),
            make_stage5_code_payload(task.task_id, "mod_a", plan["subtasks"][0], "assign a = 1'b1;"),
        ]
    )
    agent = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output_root)

    agent.run_incremental(task, {"stage4": stage4, "spec_blocks": spec_blocks})

    assert len(backend.calls) == 2
    fragment_file = tmp_path / ".zerorepo" / "workspace" / "fragments" / "mod_a_fragments.v"
    assert "assign a = 1'b1;" in fragment_file.read_text(encoding="utf-8")


def test_stage5_prompt_includes_module_interface_blocks_when_subtask_refs_omit_them(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    output_root = tmp_path / ".zerorepo" / "module_planner" / "outputs"
    plan_dir = output_root / "module_plan_json"
    plan_dir.mkdir(parents=True)
    plan = {
        "schema_version": "module_plan_v1",
        "module": "mod_a",
        "subtasks": [
            {
                "id": "B1_logic",
                "target": "<block: B1_logic>",
                "description": "Generate logic that relies on existing port declarations.",
                "spec_refs": ["S002"],
                "constraints": [],
            }
        ],
    }
    (plan_dir / "mod_a.json").write_text(json.dumps(plan), encoding="utf-8")
    stage4 = {
        "schema_version": "module_plans_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "module_plan_files": [{"module": "mod_a", "plan_file": "module_plan_json/mod_a.json"}],
    }
    spec_blocks = {
        "schema_version": "spec_blocks_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "modules": [
            {
                "module": "mod_a",
                "source_spec_file": "mod_a.md",
                "blocks": [
                    {
                        "block_id": "S001",
                        "text": "**3. Interface**\n\nPORT_INTERFACE_TEXT\n\n| Signal Name | Direction | Width | Description |\n| --- | --- | --- | --- |\n| a | input | 8 | Input byte |\n| y | output | 8 | Output byte |",
                    },
                    {"block_id": "S002", "text": "**4. Operation**\n\nLOGIC_TEXT"},
                ],
            }
        ],
    }
    backend = QueueBackend(
        [make_stage5_code_payload(task.task_id, "mod_a", plan["subtasks"][0], "assign y = a;")]
    )
    agent = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output_root)

    agent.run_incremental(task, {"stage4": stage4, "spec_blocks": spec_blocks})

    prompt = backend.calls[0]["user_prompt"]
    assert "[MODULE_INTERFACE_SPEC_BLOCKS]" in prompt
    assert "PORT_INTERFACE_TEXT" in prompt
    assert "LOGIC_TEXT" in prompt
    assert "may be used only for module boundary facts" in prompt


def test_stage5_prompt_deduplicates_interface_blocks_already_selected(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    output_root = tmp_path / ".zerorepo" / "module_planner" / "outputs"
    plan_dir = output_root / "module_plan_json"
    plan_dir.mkdir(parents=True)
    plan = {
        "schema_version": "module_plan_v1",
        "module": "mod_a",
        "subtasks": [
            {
                "id": "B1_decl",
                "target": "<block: B1_decl>",
                "description": "Declare ports and local objects.",
                "spec_refs": ["S001", "S002"],
                "constraints": [],
            }
        ],
    }
    (plan_dir / "mod_a.json").write_text(json.dumps(plan), encoding="utf-8")
    stage4 = {
        "schema_version": "module_plans_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "module_plan_files": [{"module": "mod_a", "plan_file": "module_plan_json/mod_a.json"}],
    }
    spec_blocks = {
        "schema_version": "spec_blocks_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "modules": [
            {
                "module": "mod_a",
                "source_spec_file": "mod_a.md",
                "blocks": [
                    {
                        "block_id": "S001",
                        "text": "**3. Interface**\n\nDEDUP_INTERFACE_TEXT\n\n| Signal Name | Direction | Width | Description |\n| --- | --- | --- | --- |\n| a | input | 8 | Input byte |\n| y | output | 8 | Output byte |",
                    },
                    {"block_id": "S002", "text": "**4. Operation**\n\nLOGIC_TEXT"},
                ],
            }
        ],
    }
    backend = QueueBackend(
        [make_stage5_code_payload(task.task_id, "mod_a", plan["subtasks"][0], "wire [7:0] local_y;")]
    )
    agent = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output_root)

    agent.run_incremental(task, {"stage4": stage4, "spec_blocks": spec_blocks})

    prompt = backend.calls[0]["user_prompt"]
    assert prompt.count("DEDUP_INTERFACE_TEXT") == 1
    assert '"module_interface_spec_refs": []' in prompt


def test_stage5_prompt_includes_global_defines_when_available(tmp_path, monkeypatch):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    official = tmp_path / "RealBench" / "sdc" / "sd_defines" / "sd_defines.v"
    official.parent.mkdir(parents=True)
    official.write_text("`define BIT_BLOCK 1044\n`define SD_BUS_W 4\n", encoding="utf-8")
    monkeypatch.setattr(global_defines_mod, "find_official_define_file", lambda _task, _module: official)

    output_root = tmp_path / ".zerorepo" / "module_planner" / "outputs"
    plan_dir = output_root / "module_plan_json"
    plan_dir.mkdir(parents=True)
    plan = {
        "schema_version": "module_plan_v1",
        "module": "mod_a",
        "subtasks": [
            {
                "id": "B1_logic",
                "target": "<block: B1_logic>",
                "description": "Generate logic using global constants.",
                "spec_refs": ["S001"],
                "constraints": [],
            }
        ],
    }
    (plan_dir / "mod_a.json").write_text(json.dumps(plan), encoding="utf-8")
    stage4 = {
        "schema_version": "module_plans_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "module_plan_files": [{"module": "mod_a", "plan_file": "module_plan_json/mod_a.json"}],
    }
    spec_blocks = {
        "schema_version": "spec_blocks_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "modules": [
            {
                "module": "mod_a",
                "source_spec_file": "mod_a.md",
                "blocks": [{"block_id": "S001", "text": "**Operation**\nUse global SD constants."}],
            }
        ],
    }
    repo_skeleton = {
        "modules": [
            {"module": "sd_defines", "role": "global defines", "repo_notes": ["provides constants"]},
            {"module": "mod_a", "role": "logic", "repo_notes": []},
        ],
        "global_invariants": {"global_data_conventions": "sd_defines provides global constants"},
    }
    backend = QueueBackend(
        [make_stage5_code_payload(task.task_id, "mod_a", plan["subtasks"][0], "wire [`SD_BUS_W-1:0] bus;")]
    )
    agent = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output_root)

    agent.run_incremental(task, {"stage4": stage4, "spec_blocks": spec_blocks, "repo_skeleton": repo_skeleton})

    prompt = backend.calls[0]["user_prompt"]
    workspace_root = tmp_path / ".zerorepo" / "workspace"
    assert "[GLOBAL_DEFINES_CONTEXT]" in prompt
    assert "`define BIT_BLOCK 1044" in prompt
    assert "`define SD_BUS_W 4" in prompt
    assert '"global_define_files": [\n    "sd_defines.v"\n  ]' in prompt
    assert (workspace_root / "global_defines_manifest.json").exists()
    assert not (workspace_root / "merged" / "global_defines_manifest.json").exists()


def test_stage5_prompt_includes_current_module_skeleton_context(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    output_root = tmp_path / ".zerorepo" / "module_planner" / "outputs"
    plan_dir = output_root / "module_plan_json"
    skeleton_dir = output_root / "module_skeleton_docs"
    plan_dir.mkdir(parents=True)
    skeleton_dir.mkdir(parents=True)
    skeleton_doc = "\n".join(
        [
            "# MODULE_SKELETON_DOC v1",
            "## 1. Module Frame",
            "module mod_a (",
            "    // port placeholder",
            ");",
            "// <block: B1_logic>",
            "endmodule",
            "SKELETON_POSITION_MARKER",
        ]
    )
    (skeleton_dir / "mod_a.md").write_text(skeleton_doc, encoding="utf-8")
    plan = {
        "schema_version": "module_plan_v1",
        "module": "mod_a",
        "subtasks": [
            {
                "id": "B1_logic",
                "target": "<block: B1_logic>",
                "description": "Generate local logic.",
                "spec_refs": ["S001"],
                "constraints": [],
            }
        ],
    }
    (plan_dir / "mod_a.json").write_text(json.dumps(plan), encoding="utf-8")
    stage3 = {
        "schema_version": "stage3_skeleton_docs_v1",
        "task_id": task.task_id,
        "stage3_status": "module_skeletons_planned",
        "top_module": "mod_a",
        "module_order": ["mod_a"],
        "completed_modules": ["mod_a"],
        "global_summary": [],
        "module_records": [
            {
                "module": "mod_a",
                "doc_file": "module_skeleton_docs/mod_a.md",
                "export_file": "module_skeleton_json/mod_a.json",
                "source_refs": {
                    "module_contract_ref": "module_contracts_v1::mod_a",
                    "repo_skeleton_ref": "repo_skeleton_v1::mod_a",
                    "module_spec_file": "mod_a.md",
                },
                "block_ids": ["B1"],
            }
        ],
        "open_issues": [],
    }
    stage4 = {
        "schema_version": "module_plans_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "module_plan_files": [{"module": "mod_a", "plan_file": "module_plan_json/mod_a.json"}],
    }
    spec_blocks = {
        "schema_version": "spec_blocks_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "modules": [
            {
                "module": "mod_a",
                "source_spec_file": "mod_a.md",
                "blocks": [{"block_id": "S001", "text": "**4. Operation**\n\nGenerate local logic."}],
            }
        ],
    }
    backend = QueueBackend(
        [make_stage5_code_payload(task.task_id, "mod_a", plan["subtasks"][0], "assign y = a;")]
    )
    agent = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output_root)

    agent.run_incremental(task, {"stage3": stage3, "stage4": stage4, "spec_blocks": spec_blocks})

    prompt = backend.calls[0]["user_prompt"]
    assert "[MODULE_SKELETON]" in prompt
    assert "SKELETON_POSITION_MARKER" in prompt
    assert "module_skeleton_docs/mod_a.md" in backend.calls[0]["user_prompt"]


def test_stage5_agent_run_module_writes_single_fragment_file(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    output_root = tmp_path / ".zerorepo" / "module_planner" / "outputs"
    plan_dir = output_root / "module_plan_json"
    plan_dir.mkdir(parents=True)
    plan = {
        "schema_version": "module_plan_v1",
        "module": "mod_a",
        "subtasks": [
            {
                "id": "B1_logic",
                "target": "<block: B1_logic>",
                "description": "Generate logic.",
                "spec_refs": ["S001"],
                "constraints": [],
            }
        ],
    }
    (plan_dir / "mod_a.json").write_text(json.dumps(plan), encoding="utf-8")
    stage4 = {
        "schema_version": "module_plans_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "module_plan_files": [{"module": "mod_a", "plan_file": "module_plan_json/mod_a.json"}],
    }
    spec_blocks = {
        "schema_version": "spec_blocks_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "modules": [
            {
                "module": "mod_a",
                "source_spec_file": "mod_a.md",
                "blocks": [{"block_id": "S001", "text": "A_SELECTED_SPEC"}],
            }
        ],
    }
    backend = QueueBackend(
        [make_stage5_code_payload(task.task_id, "mod_a", plan["subtasks"][0], "assign y = a;")]
    )
    agent = Stage5Agent(PlannerLLMClient(backend=backend), output_root=output_root)

    record = agent.run_module(task, {"stage4": stage4, "spec_blocks": spec_blocks}, "mod_a")

    assert record.module == "mod_a"
    assert record.workspace_file.endswith("workspace/fragments/mod_a_fragments.v")
    fragment_text = Path(record.workspace_file).read_text(encoding="utf-8")
    assert "// STAGE5_SUBTASK_BEGIN B1_logic" in fragment_text
    assert "assign y = a;" in fragment_text


def test_stage6_merge_agent_writes_raw_merged_module_and_prompt_context(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    output_root = tmp_path / ".zerorepo" / "module_planner" / "outputs"
    skeleton_dir = output_root / "module_skeleton_docs"
    fragment_dir = tmp_path / ".zerorepo" / "workspace" / "fragments"
    skeleton_dir.mkdir(parents=True)
    fragment_dir.mkdir(parents=True)
    (skeleton_dir / "mod_a.md").write_text("SKELETON_POSITION_MARKER", encoding="utf-8")
    fragment_file = fragment_dir / "mod_a_fragments.v"
    fragment_file.write_text(
        "// STAGE5_SUBTASK_BEGIN B1_logic: Generate logic.\nassign y = a;\n// STAGE5_SUBTASK_END B1_logic\n",
        encoding="utf-8",
    )
    stage3 = {
        "schema_version": "stage3_skeleton_docs_v1",
        "task_id": task.task_id,
        "stage3_status": "module_skeletons_planned",
        "top_module": "mod_a",
        "module_order": ["mod_a"],
        "completed_modules": ["mod_a"],
        "global_summary": [],
        "module_records": [
            {
                "module": "mod_a",
                "doc_file": "module_skeleton_docs/mod_a.md",
                "export_file": "module_skeleton_json/mod_a.json",
                "source_refs": {
                    "module_contract_ref": "module_contracts_v1::mod_a",
                    "repo_skeleton_ref": "repo_skeleton_v1::mod_a",
                    "module_spec_file": "mod_a.md",
                },
                "block_ids": ["B1"],
            }
        ],
        "open_issues": [],
    }
    spec_blocks = {
        "schema_version": "spec_blocks_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "modules": [
            {
                "module": "mod_a",
                "source_spec_file": "mod_a.md",
                "blocks": [
                    {"block_id": "S001", "text": "MODULE_SPEC_MARKER"},
                    {"block_id": "S002", "text": "MORE_SPEC_MARKER"},
                ],
            }
        ],
    }
    backend = QueueBackend(
        [
            make_merge_context_retrieval_payload("mod_a", ["S001", "S002"]),
            f"```verilog\n{make_stage6_module_code('mod_a')}\n```",
        ]
    )
    agent = Stage6MergeAgent(PlannerLLMClient(backend=backend), output_root=output_root)

    record = agent.run_module(
        task,
        {"stage3": stage3, "spec_blocks": spec_blocks},
        "mod_a",
        {"module": "mod_a", "workspace_file": str(fragment_file), "completed_subtasks": ["B1_logic"]},
    )

    assert record.merged_file.endswith("workspace/merged/mod_a.v")
    assert Path(record.merged_file).read_text(encoding="utf-8") == make_stage6_module_code("mod_a") + "\n"
    assert "```" not in Path(record.merged_file).read_text(encoding="utf-8")
    prompt = backend.calls[1]["user_prompt"]
    assert "MODULE_SPEC_MARKER" in prompt
    assert "MORE_SPEC_MARKER" in prompt
    assert "SKELETON_POSITION_MARKER" in prompt
    assert "STAGE5_SUBTASK_BEGIN B1_logic" in prompt


def test_stage6_merge_agent_delegates_invalid_raw_verilog_to_debug(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    output_root = tmp_path / ".zerorepo" / "module_planner" / "outputs"
    fragment_dir = tmp_path / ".zerorepo" / "workspace" / "fragments"
    fragment_dir.mkdir(parents=True)
    fragment_file = fragment_dir / "mod_a_fragments.v"
    fragment_file.write_text("assign y = a;\n", encoding="utf-8")
    spec_blocks = {
        "schema_version": "spec_blocks_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "modules": [
            {
                "module": "mod_a",
                "source_spec_file": "mod_a.md",
                "blocks": [{"block_id": "S001", "text": "MODULE_SPEC_MARKER"}],
            }
        ],
    }
    backend = QueueBackend(
        [
            make_merge_context_retrieval_payload("mod_a"),
            "```verilog\nmodule wrong_name(input a, output y);\n// TODO\n// STAGE5_SUBTASK_BEGIN B1\n",
        ]
    )
    agent = Stage6MergeAgent(PlannerLLMClient(backend=backend), output_root=output_root)

    record = agent.run_module(
        task,
        {"spec_blocks": spec_blocks},
        "mod_a",
        {"module": "mod_a", "workspace_file": str(fragment_file), "completed_subtasks": ["B1_logic"]},
    )

    assert len(backend.calls) == 2
    assert "module wrong_name" in Path(record.merged_file).read_text(encoding="utf-8")
    syntax_log = json.loads((output_root / "stage6_syntax_repair" / "mod_a.json").read_text(encoding="utf-8"))
    assert syntax_log["status"] == "delegated_to_debug_syntax_repair"
    assert syntax_log["syntax_passed"] is False
    assert syntax_log["delegated_to"] == "ModuleDebugRunner.repo_react_syntax"


def test_planner_runner_supports_stage5_subtask_codegen_workspace(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    top_spec, key_spec = make_module_spec_files(tmp_path)
    top_spec.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    key_spec.write_text(
        "\n".join(
            [
                "**aes_key_expand_128 Design Specification**",
                "",
                "**1. Introduction**",
                "KEYEXP UNIQUE SPEC MARKER",
                "",
                "**4.1 Basic Principle**",
                "Generates round keys iteratively for the top module.",
            ]
        ),
        encoding="utf-8",
    )
    key_plan = make_stage4_module_plan_payload("aes_key_expand_128")
    top_plan = make_stage4_module_plan_payload("aes_cipher_top", top_module=True)
    stage5_responses = [
        make_stage5_code_payload(task.task_id, "aes_key_expand_128", subtask)
        for subtask in key_plan["subtasks"]
    ] + [
        make_stage5_code_payload(task.task_id, "aes_cipher_top", subtask)
        for subtask in top_plan["subtasks"]
    ]
    backend = QueueBackend(
        [
            make_repo_skeleton_payload(),
            make_module_spec_context_payload("aes_key_expand_128", key_spec),
            make_stage3_module_skeleton_doc("aes_key_expand_128", key_spec),
            make_module_spec_context_payload("aes_cipher_top", top_spec),
            make_stage3_module_skeleton_doc("aes_cipher_top", top_spec),
            make_block_spec_retrieval_payload("aes_key_expand_128"),
            key_plan,
            make_block_spec_retrieval_payload("aes_cipher_top", top_module=True),
            top_plan,
            *stage5_responses,
        ]
    )
    output_root = tmp_path / ".zerorepo" / "module_planner" / "outputs"
    runner = PlannerRunner(output_root=output_root, llm_backend=backend, temporal_planning_enabled=False)

    artifact = runner.run(task, end_stage="stage5")

    assert isinstance(artifact, Stage5CodegenArtifact)
    assert artifact.module_order == ["aes_key_expand_128", "aes_cipher_top"]
    workspace_root = tmp_path / ".zerorepo" / "workspace"
    key_workspace = workspace_root / "fragments" / "aes_key_expand_128_fragments.v"
    top_workspace = workspace_root / "fragments" / "aes_cipher_top_fragments.v"
    assert key_workspace.exists()
    assert top_workspace.exists()
    assert "// STAGE5_SUBTASK_BEGIN B1_decl_state_and_keys" in key_workspace.read_text(encoding="utf-8")
    manifest = json.loads((output_root / "stage5_codegen.json").read_text(encoding="utf-8"))
    assert manifest["module_order"] == ["aes_key_expand_128", "aes_cipher_top"]
    assert manifest["module_files"][0]["completed_subtasks"] == [
        subtask["id"] for subtask in key_plan["subtasks"]
    ]


def test_planner_runner_supports_stage6_per_module_merge(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    top_spec, key_spec = make_module_spec_files(tmp_path)
    top_spec.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    key_spec.write_text(
        "\n".join(
            [
                "**aes_key_expand_128 Design Specification**",
                "",
                "**1. Introduction**",
                "KEYEXP UNIQUE SPEC MARKER",
            ]
        ),
        encoding="utf-8",
    )
    key_plan = make_stage4_module_plan_payload("aes_key_expand_128")
    top_plan = make_stage4_module_plan_payload("aes_cipher_top", top_module=True)
    key_stage5_responses = [
        make_stage5_code_payload(task.task_id, "aes_key_expand_128", subtask)
        for subtask in key_plan["subtasks"]
    ]
    top_stage5_responses = [
        make_stage5_code_payload(task.task_id, "aes_cipher_top", subtask)
        for subtask in top_plan["subtasks"]
    ]
    backend = QueueBackend(
        [
            make_repo_skeleton_payload(),
            make_module_spec_context_payload("aes_key_expand_128", key_spec),
            make_stage3_module_skeleton_doc("aes_key_expand_128", key_spec),
            make_module_spec_context_payload("aes_cipher_top", top_spec),
            make_stage3_module_skeleton_doc("aes_cipher_top", top_spec),
            make_block_spec_retrieval_payload("aes_key_expand_128"),
            key_plan,
            make_block_spec_retrieval_payload("aes_cipher_top", top_module=True),
            top_plan,
            *key_stage5_responses,
            make_merge_context_retrieval_payload("aes_key_expand_128"),
            make_stage6_module_code("aes_key_expand_128"),
            *top_stage5_responses,
            make_merge_context_retrieval_payload("aes_cipher_top"),
            make_stage6_module_code("aes_cipher_top"),
        ]
    )
    output_root = tmp_path / ".zerorepo" / "module_planner" / "outputs"
    runner = PlannerRunner(output_root=output_root, llm_backend=backend, temporal_planning_enabled=False)

    artifact = runner.run(task, end_stage="stage6")

    assert isinstance(artifact, Stage6MergeArtifact)
    assert artifact.module_order == ["aes_key_expand_128", "aes_cipher_top"]
    workspace_root = tmp_path / ".zerorepo" / "workspace"
    assert (workspace_root / "fragments" / "aes_key_expand_128_fragments.v").exists()
    assert (workspace_root / "merged" / "aes_key_expand_128.v").exists()
    assert (workspace_root / "fragments" / "aes_cipher_top_fragments.v").exists()
    assert (workspace_root / "merged" / "aes_cipher_top.v").exists()
    stage6_manifest = json.loads((output_root / "stage6_merge.json").read_text(encoding="utf-8"))
    assert stage6_manifest["module_order"] == ["aes_key_expand_128", "aes_cipher_top"]
    assert stage6_manifest["module_files"][0]["fragment_file"].endswith(
        "workspace/fragments/aes_key_expand_128_fragments.v"
    )
    assert stage6_manifest["module_files"][0]["merged_file"].endswith("workspace/merged/aes_key_expand_128.v")
    stage6_call_indices = [
        index for index, call in enumerate(backend.calls) if "RTL Merge Agent" in call["system_prompt"]
    ]
    key_merge_indices = [
        index
        for index in stage6_call_indices
        if '"module": "aes_key_expand_128"' in backend.calls[index]["user_prompt"]
    ]
    top_merge_indices = [
        index for index in stage6_call_indices if '"module": "aes_cipher_top"' in backend.calls[index]["user_prompt"]
    ]
    assert key_merge_indices
    assert top_merge_indices
    assert min(key_merge_indices) < min(top_merge_indices)
    first_key_merge_index = min(key_merge_indices)
    assert "B5_comb_output_path" in backend.calls[first_key_merge_index - 1]["user_prompt"]
    assert "STAGE5_SUBTASK_BEGIN B1_decl_state_and_keys" in backend.calls[first_key_merge_index]["user_prompt"]


def test_stage2_agent_builds_repo_skeleton_from_modules_artifact(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    stage1_artifact = make_stage1_contract_artifact(md_path, image_paths)
    modules_artifact = build_module_organized_artifact(stage1_artifact)
    backend = QueueBackend([make_repo_skeleton_payload()])
    agent = Stage2Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run(task, {"modules": modules_artifact})

    assert isinstance(artifact, Stage2RepoSkeletonArtifact)
    assert artifact.stage2_status == "repo_skeleton_planned"
    assert artifact.top_module == "aes_cipher_top"
    assert artifact.planning_decisions.generation_order == ["aes_key_expand_128", "aes_cipher_top"]
    assert '"schema_version": "stage2_planning_input_v1"' in backend.calls[0]["user_prompt"]
    assert '"legacy_contract_projection"' in backend.calls[0]["user_prompt"]
    assert '"compat_module_candidates"' in backend.calls[0]["user_prompt"]
    assert '"fact_ledger"' in backend.calls[0]["user_prompt"]


def test_build_stage2_planning_input_from_task_includes_specs_without_legacy_stage1(tmp_path):
    task, md_path, _ = make_task_input(tmp_path, image_count=1)

    stage2_input = build_stage2_planning_input_from_task(task_input=task)

    assert isinstance(stage2_input, Stage2PlanningInput)
    assert stage2_input.schema_version == "stage2_planning_input_v1"
    assert stage2_input.source_specs[0].path == str(md_path.resolve())
    assert "Top module: aes_cipher_top" in stage2_input.source_specs[0].markdown
    assert stage2_input.spec_index == {"aes_cipher_top": str(md_path.resolve())}
    assert stage2_input.fact_ledger.source_files == [str(md_path.resolve())]
    assert stage2_input.fact_ledger.facts == []
    assert stage2_input.legacy_contract_projection is None
    assert stage2_input.compat_module_candidates == []


def test_build_stage2_planning_input_includes_specs_and_compat_candidates(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    stage1_artifact = make_stage1_contract_artifact(md_path, image_paths)
    compat_modules = build_module_organized_artifact(stage1_artifact)

    stage2_input = build_stage2_planning_input(
        stage1_artifact=stage1_artifact,
        task_input=task,
        compat_modules=compat_modules,
    )

    assert isinstance(stage2_input, Stage2PlanningInput)
    assert stage2_input.schema_version == "stage2_planning_input_v1"
    assert stage2_input.source_specs[0].stem == "aes_cipher_top"
    assert "Top module: aes_cipher_top" in stage2_input.source_specs[0].markdown
    assert "aes_cipher_top" in stage2_input.compat_module_candidates
    assert stage2_input.legacy_contract_projection.task_id == task.task_id


def test_stage2_prompt_uses_planning_input_not_modules_primary_source(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    stage1_artifact = make_stage1_contract_artifact(md_path, image_paths)
    stage2_input = build_stage2_planning_input(
        stage1_artifact=stage1_artifact,
        task_input=task,
        compat_modules=build_module_organized_artifact(stage1_artifact),
    )
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([])))

    prompt, _ = agent.build_prompt(task, {"stage2_input": stage2_input}, {})

    assert "stage2_planning_input_v1" in prompt
    assert "Use modules.json as the primary source of truth" not in prompt
    assert "source spec markdown" in prompt
    assert "compatibility module candidates" in prompt
    assert "aes_unified_functional_spec" in prompt
    assert "not treated as RTL modules" in prompt


def test_stage2_validation_allows_planned_modules_not_in_compat_candidates(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    stage1_artifact = make_stage1_contract_artifact(md_path, image_paths)
    stage2_input = build_stage2_planning_input(
        stage1_artifact=stage1_artifact,
        task_input=task,
        compat_modules=build_module_organized_artifact(stage1_artifact),
    )
    stage2_input.compat_module_candidates = ["aes_cipher_top"]
    artifact = validate_model(
        Stage2RepoSkeletonArtifact,
        {
            "task_id": task.task_id,
            "source_schema_version": "stage2_planning_input_v1",
            "stage2_status": "repo_skeleton_planned",
            "top_module": "aes_cipher_top",
            "global_invariants": {
                "hierarchy": [
                    {
                        "parent": "aes_cipher_top",
                        "child": "aes_sbox",
                        "source_kind": "inferred_from_spec",
                        "rationale": "SubBytes behavior is isolated enough to plan as a reusable S-box module.",
                    },
                    {
                        "parent": "aes_cipher_top",
                        "child": "aes_key_expand_128",
                        "source_kind": "explicit",
                        "rationale": "Preserved from explicit Stage1 fact.",
                    },
                ],
                "file_map": {
                    "aes_sbox": "rtl/aes_sbox.v",
                    "aes_key_expand_128": "rtl/aes_key_expand_128.v",
                    "aes_cipher_top": "rtl/aes_cipher_top.v",
                },
            },
            "modules": [
                {
                    "module": "aes_sbox",
                    "file_path": "rtl/aes_sbox.v",
                    "role": "byte substitution helper",
                    "kind": "leaf_combinational",
                    "source_kind": "inferred_from_spec",
                    "rationale": "SubBytes uses byte substitution.",
                    "parents": ["aes_cipher_top"],
                    "children": [],
                    "instance_hints": [],
                },
                {
                    "module": "aes_key_expand_128",
                    "file_path": "rtl/aes_key_expand_128.v",
                    "role": "round key provider",
                    "kind": "iterative_engine",
                    "parents": ["aes_cipher_top"],
                    "children": [],
                    "instance_hints": [],
                },
                {
                    "module": "aes_cipher_top",
                    "file_path": "rtl/aes_cipher_top.v",
                    "role": "top controller",
                    "kind": "top_controller",
                    "parents": [],
                    "children": ["aes_sbox", "aes_key_expand_128"],
                    "instance_hints": [],
                },
            ],
            "planning_decisions": {
                "generation_order": ["aes_sbox", "aes_key_expand_128", "aes_cipher_top"],
                "leaf_first": True,
                "shared_modules": [],
            },
            "open_issues": [],
        },
    )
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([])))

    errors = agent.validate_quality(artifact, task, {"stage2_input": stage2_input})

    assert errors == []


def test_stage2_validation_accepts_inferred_from_spec_with_empty_fact_ledger(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=1)
    stage2_input = build_stage2_planning_input_from_task(task_input=task)
    artifact = validate_model(
        Stage2RepoSkeletonArtifact,
        {
            "task_id": task.task_id,
            "source_schema_version": "stage2_planning_input_v1",
            "stage2_status": "repo_skeleton_planned",
            "top_module": "aes_cipher_top",
            "global_invariants": {
                "hierarchy": [
                    {
                        "parent": "aes_cipher_top",
                        "child": "aes_sbox",
                        "source_kind": "inferred_from_spec",
                        "rationale": "The source spec describes a reusable S-box function used by the cipher datapath.",
                    }
                ],
                "file_map": {
                    "aes_sbox": "rtl/aes_sbox.v",
                    "aes_cipher_top": "rtl/aes_cipher_top.v",
                },
            },
            "modules": [
                {
                    "module": "aes_sbox",
                    "file_path": "rtl/aes_sbox.v",
                    "role": "byte substitution helper",
                    "kind": "leaf_combinational",
                    "source_kind": "inferred_from_spec",
                    "rationale": "Reusable byte substitution from the spec.",
                    "parents": ["aes_cipher_top"],
                    "children": [],
                    "instance_hints": [],
                },
                {
                    "module": "aes_cipher_top",
                    "file_path": "rtl/aes_cipher_top.v",
                    "role": "top controller",
                    "kind": "top_controller",
                    "source_kind": "inferred_from_spec",
                    "rationale": "Top-level module named by the source spec.",
                    "parents": [],
                    "children": ["aes_sbox"],
                    "instance_hints": [
                        {
                            "module": "aes_sbox",
                            "count": 16,
                            "usage": "SubBytes byte substitution",
                            "source_kind": "inferred_from_spec",
                            "rationale": "The spec calls for parallel byte substitutions.",
                        }
                    ],
                },
            ],
            "planning_decisions": {
                "generation_order": ["aes_sbox", "aes_cipher_top"],
                "leaf_first": True,
                "shared_modules": [],
            },
            "open_issues": [],
        },
    )
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([])))

    errors = agent.validate_quality(artifact, task, {"stage2_input": stage2_input})

    assert errors == []


def test_stage2_validation_rejects_single_module_when_partitioning_guidance_exists(tmp_path):
    md_path = tmp_path / "hard_system.md"
    md_path.write_text(
        "\n".join(
            [
                "# Hard System",
                "Top module: hard_top",
                "## Functional Decomposition",
                "The design has natural boundaries and reusable implementation units.",
            ]
        ),
        encoding="utf-8",
    )
    task = PlannerTaskInput(
        task_id="hard_demo",
        spec_md_files=[str(md_path)],
        spec_images=[],
        project_type="light_repo_spec2rtl",
        notes="hard partitioning test",
    )
    stage2_input = build_stage2_planning_input_from_task(task_input=task)
    artifact = validate_model(
        Stage2RepoSkeletonArtifact,
        {
            "task_id": task.task_id,
            "source_schema_version": "stage2_planning_input_v1",
            "stage2_status": "repo_skeleton_planned",
            "top_module": "hard_top",
            "global_invariants": {
                "hierarchy": [],
                "file_map": {"hard_top": "rtl/hard_top.v"},
            },
            "modules": [
                {
                    "module": "hard_top",
                    "file_path": "rtl/hard_top.v",
                    "role": "top controller",
                    "kind": "top_controller",
                    "source_kind": "inferred_from_spec",
                    "rationale": "Only top module planned.",
                    "parents": [],
                    "children": [],
                    "instance_hints": [],
                }
            ],
            "planning_decisions": {
                "generation_order": ["hard_top"],
                "leaf_first": True,
                "shared_modules": [],
            },
            "open_issues": [],
        },
    )
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([])))

    errors = agent.validate_quality(artifact, task, {"stage2_input": stage2_input})

    assert any("partitioning guidance" in error for error in errors)


def test_stage2_repo_skeleton_normalizes_object_open_issues():
    artifact = validate_model(
        Stage2RepoSkeletonArtifact,
        {
            "task_id": "open_issue_demo",
            "source_schema_version": "stage2_planning_input_v1",
            "stage2_status": "repo_skeleton_planned",
            "top_module": "aes_cipher_top",
            "global_invariants": {
                "hierarchy": [],
                "file_map": {"aes_cipher_top": "rtl/aes_cipher_top.v"},
            },
            "modules": [
                {
                    "module": "aes_cipher_top",
                    "file_path": "rtl/aes_cipher_top.v",
                    "role": "top controller",
                    "kind": "top_controller",
                    "parents": [],
                    "children": [],
                    "instance_hints": [],
                }
            ],
            "planning_decisions": {
                "generation_order": ["aes_cipher_top"],
                "leaf_first": True,
                "shared_modules": [],
            },
            "open_issues": [
                {
                    "issue": "Round constant generation boundary is uncertain",
                    "options": ["local helper", "separate round_const_gen"],
                },
                {
                    "issue": "MixColumns/xtime boundary is uncertain",
                    "decision": "prefer local helper unless timing requires module split",
                },
            ],
        },
    )

    assert artifact.open_issues == [
        "Round constant generation boundary is uncertain. options: local helper; separate round_const_gen",
        "MixColumns/xtime boundary is uncertain. decision: prefer local helper unless timing requires module split",
    ]


def test_build_modules_artifact_from_repo_skeleton_filters_spec_filename_module(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    stage1_artifact = make_stage1_contract_artifact(md_path, image_paths)
    repo_skeleton = validate_model(
        Stage2RepoSkeletonArtifact,
        {
            "task_id": task.task_id,
            "source_schema_version": "stage2_planning_input_v1",
            "stage2_status": "repo_skeleton_planned",
            "top_module": "aes_cipher_top",
            "global_invariants": {
                "hierarchy": [
                    {"parent": "aes_cipher_top", "child": "aes_sbox", "source_kind": "inferred_from_spec"}
                ],
                "file_map": {
                    "aes_sbox": "rtl/aes_sbox.v",
                    "aes_cipher_top": "rtl/aes_cipher_top.v",
                },
            },
            "modules": [
                {
                    "module": "aes_sbox",
                    "file_path": "rtl/aes_sbox.v",
                    "role": "byte substitution helper",
                    "kind": "leaf_combinational",
                    "parents": ["aes_cipher_top"],
                    "children": [],
                    "instance_hints": [],
                },
                {
                    "module": "aes_cipher_top",
                    "file_path": "rtl/aes_cipher_top.v",
                    "role": "top controller",
                    "kind": "top_controller",
                    "parents": [],
                    "children": ["aes_sbox"],
                    "instance_hints": [],
                },
            ],
            "planning_decisions": {
                "generation_order": ["aes_sbox", "aes_cipher_top"],
                "leaf_first": True,
                "shared_modules": [],
            },
            "open_issues": [],
        },
    )

    modules_artifact = build_module_organized_artifact_from_repo_skeleton(
        stage1_artifact=stage1_artifact,
        repo_skeleton=repo_skeleton,
    )

    assert modules_artifact.module_order == ["aes_sbox", "aes_cipher_top"]
    assert "aes_unified_functional_spec" not in modules_artifact.module_order
    assert modules_artifact.modules[0].parent_modules == ["aes_cipher_top"]
    assert modules_artifact.modules[1].child_modules == ["aes_sbox"]


def test_build_modules_artifact_from_repo_skeleton_only_uses_repo_skeleton_order(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=1)
    repo_skeleton = validate_model(
        Stage2RepoSkeletonArtifact,
        {
            "task_id": task.task_id,
            "source_schema_version": "stage2_planning_input_v1",
            "stage2_status": "repo_skeleton_planned",
            "top_module": "aes_cipher_top",
            "global_invariants": {
                "hierarchy": [
                    {
                        "parent": "aes_cipher_top",
                        "child": "aes_sbox",
                        "source_kind": "inferred_from_spec",
                        "rationale": "S-box is a reusable helper.",
                    }
                ],
                "file_map": {
                    "aes_sbox": "rtl/aes_sbox.v",
                    "aes_cipher_top": "rtl/aes_cipher_top.v",
                },
            },
            "modules": [
                {
                    "module": "aes_sbox",
                    "file_path": "rtl/aes_sbox.v",
                    "role": "byte substitution helper",
                    "kind": "leaf_combinational",
                    "parents": ["aes_cipher_top"],
                    "children": [],
                    "instance_hints": [],
                },
                {
                    "module": "aes_cipher_top",
                    "file_path": "rtl/aes_cipher_top.v",
                    "role": "top controller",
                    "kind": "top_controller",
                    "parents": [],
                    "children": ["aes_sbox"],
                    "instance_hints": [],
                },
            ],
            "planning_decisions": {
                "generation_order": ["aes_sbox", "aes_cipher_top"],
                "leaf_first": True,
                "shared_modules": [],
            },
            "open_issues": [],
        },
    )

    modules_artifact = build_module_organized_artifact_from_repo_skeleton_only(
        task_input=task,
        repo_skeleton=repo_skeleton,
    )

    assert modules_artifact.source_schema_version == "repo_skeleton_v1"
    assert modules_artifact.module_order == ["aes_sbox", "aes_cipher_top"]
    assert modules_artifact.fact_ledger.facts == []
    assert modules_artifact.modules[0].parent_modules == ["aes_cipher_top"]
    assert modules_artifact.modules[1].child_modules == ["aes_sbox"]


def test_debug_contract_builder_accepts_missing_stage1_contracts():
    payload = json.loads(
        build_debug_contract_json(
            module_name="aes_cipher_top",
            stage1_contracts=None,
            spec_text="The aes_cipher_top module asserts done after encryption completes.",
        )
    )

    assert payload["module_name"] == "aes_cipher_top"
    assert payload["io"] == []
    assert any("encryption" in item for item in payload["functional_summary"])


def test_stage2_accepts_fact_ledger_inferred_hierarchy_with_supporting_facts(tmp_path):
    task, md_path, _ = make_task_input(tmp_path)
    facts = [
        _fact(
            md_path,
            module="aes_cipher_top",
            category="module_identity",
            subject="aes_cipher_top",
            predicate="is_top_module",
            obj={"module": "aes_cipher_top", "modules": ["aes_cipher_top", "aes_sbox"]},
        ),
        _fact(
            md_path,
            module="aes_cipher_top",
            category="resource_requirement",
            subject="SubBytes",
            predicate="uses_parallel_units",
            obj={"unit": "aes_sbox", "count": 16},
        ),
    ]
    stage1_artifact = Stage1Agent(
        PlannerLLMClient(
            backend=QueueBackend([{"fact_ledger": {"source_files": [str(md_path.resolve())], "facts": facts, "ambiguous_items": []}}])
        )
    ).run_incremental(task, {})
    modules_artifact = build_module_organized_artifact(stage1_artifact)
    support_id = next(fact.fact_id for fact in stage1_artifact.fact_ledger.facts if fact.category == "resource_requirement")
    repo_payload = {
        "task_id": task.task_id,
        "stage2_status": "repo_skeleton_planned",
        "top_module": "aes_cipher_top",
        "global_invariants": {
            "system_role": "AES system",
            "clocking_model": {},
            "hierarchy": [
                {
                    "parent": "aes_cipher_top",
                    "child": "aes_sbox",
                    "source_kind": "inferred_from_fact_ledger",
                    "supporting_fact_ids": [support_id],
                    "rationale": "SubBytes requires S-box units.",
                }
            ],
            "file_map": {
                "aes_cipher_top": "rtl/aes_cipher_top.v",
                "aes_sbox": "rtl/aes_sbox.v",
            },
            "cross_module_alignment": [],
            "global_data_conventions": [],
        },
        "modules": [
            {
                "module": "aes_sbox",
                "file_path": "rtl/aes_sbox.v",
                "role": "S-box substitution unit",
                "kind": "leaf_combinational",
                "parents": ["aes_cipher_top"],
                "children": [],
                "instance_hints": [],
                "repo_notes": [],
            },
            {
                "module": "aes_cipher_top",
                "file_path": "rtl/aes_cipher_top.v",
                "role": "top controller",
                "kind": "top_controller",
                "parents": [],
                "children": ["aes_sbox"],
                "instance_hints": [
                    {
                        "module": "aes_sbox",
                        "count": 16,
                        "usage": "SubBytes parallel substitution",
                        "source_kind": "inferred_from_fact_ledger",
                        "supporting_fact_ids": [support_id],
                        "rationale": "Resource fact states 16 S-box units.",
                    }
                ],
                "repo_notes": [],
            },
        ],
        "planning_decisions": {
            "generation_order": ["aes_sbox", "aes_cipher_top"],
            "leaf_first": True,
            "shared_modules": [],
            "top_level_integration_notes": [],
        },
        "open_issues": [],
    }
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([repo_payload])))

    artifact = agent.run(task, {"modules": modules_artifact})

    assert artifact.global_invariants.hierarchy[0].source_kind == "inferred_from_fact_ledger"
    assert artifact.modules[1].instance_hints[0].supporting_fact_ids == [support_id]


def test_stage2_rejects_fact_ledger_inferred_hierarchy_without_supporting_facts(tmp_path):
    task, md_path, _ = make_task_input(tmp_path)
    facts = [
        _fact(
            md_path,
            module="aes_cipher_top",
            category="module_identity",
            subject="aes_cipher_top",
            predicate="is_top_module",
            obj={"module": "aes_cipher_top", "modules": ["aes_cipher_top", "aes_sbox"]},
        ),
        _fact(
            md_path,
            module="aes_cipher_top",
            category="resource_requirement",
            subject="SubBytes",
            predicate="uses_parallel_units",
            obj={"unit": "aes_sbox", "count": 16},
        ),
    ]
    stage1_artifact = Stage1Agent(
        PlannerLLMClient(
            backend=QueueBackend([{"fact_ledger": {"source_files": [str(md_path.resolve())], "facts": facts, "ambiguous_items": []}}])
        )
    ).run_incremental(task, {})
    modules_artifact = build_module_organized_artifact(stage1_artifact)
    artifact = validate_model(
        Stage2RepoSkeletonArtifact,
        {
            "task_id": task.task_id,
            "stage2_status": "repo_skeleton_planned",
            "top_module": "aes_cipher_top",
            "global_invariants": {
                "hierarchy": [
                    {
                        "parent": "aes_cipher_top",
                        "child": "aes_sbox",
                        "source_kind": "inferred_from_fact_ledger",
                    }
                ],
                "file_map": {
                    "aes_cipher_top": "rtl/aes_cipher_top.v",
                    "aes_sbox": "rtl/aes_sbox.v",
                },
            },
            "modules": [
                {
                    "module": "aes_sbox",
                    "file_path": "rtl/aes_sbox.v",
                    "role": "S-box substitution unit",
                    "kind": "leaf_combinational",
                    "parents": ["aes_cipher_top"],
                    "children": [],
                    "instance_hints": [],
                },
                {
                    "module": "aes_cipher_top",
                    "file_path": "rtl/aes_cipher_top.v",
                    "role": "top controller",
                    "kind": "top_controller",
                    "parents": [],
                    "children": ["aes_sbox"],
                    "instance_hints": [],
                },
            ],
            "planning_decisions": {
                "generation_order": ["aes_sbox", "aes_cipher_top"],
                "leaf_first": True,
                "shared_modules": [],
            },
            "open_issues": [],
        },
    )
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([])))

    errors = agent.validate_quality(artifact, task, {"modules": modules_artifact})

    assert any("supporting_fact_ids" in error for error in errors)


def test_stage3_agent_builds_module_skeletons_incrementally(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    top_spec, key_spec = make_module_spec_files(tmp_path)
    top_spec.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    stage1_artifact = make_stage1_contract_artifact(md_path, image_paths)
    modules_artifact = build_module_organized_artifact(stage1_artifact)
    stage2_artifact = validate_model(Stage2RepoSkeletonArtifact, make_repo_skeleton_payload())
    backend = QueueBackend(
        [
            make_module_spec_context_payload("aes_key_expand_128", key_spec),
            make_stage3_module_skeleton_doc("aes_key_expand_128", key_spec),
            make_module_spec_context_payload("aes_cipher_top", top_spec),
            make_stage3_module_skeleton_doc("aes_cipher_top", top_spec),
        ]
    )
    agent = Stage3Agent(PlannerLLMClient(backend=backend))
    persisted = []

    artifact = agent.run_incremental(
        task,
        {"modules": modules_artifact, "stage2": stage2_artifact},
        persist_callback=lambda payload: persisted.append(payload),
    )

    assert isinstance(artifact, Stage3ModuleSkeletonArtifact)
    assert artifact.stage3_status == "module_skeletons_planned"
    assert artifact.module_order == ["aes_key_expand_128", "aes_cipher_top"]
    assert [item.module for item in artifact.module_records] == ["aes_key_expand_128", "aes_cipher_top"]
    assert artifact.module_records[0].export_schema_version == "module_skeleton_export_v1"
    assert artifact.module_records[0].doc_file == "module_skeleton_docs/aes_key_expand_128.md"
    assert artifact.module_records[0].export_file == "module_skeleton_json/aes_key_expand_128.json"
    assert artifact.module_records[0].spec_context_file == "module_spec_context_json/aes_key_expand_128.json"
    assert len(persisted) == 3
    assert persisted[0]["manifest"]["completed_modules"] == ["aes_key_expand_128"]
    assert persisted[0]["doc_file"] == "module_skeleton_docs/aes_key_expand_128.md"
    assert persisted[0]["export_file"] == "module_skeleton_json/aes_key_expand_128.json"
    assert persisted[0]["spec_context_file"] == "module_spec_context_json/aes_key_expand_128.json"
    assert persisted[0]["spec_context_payload"]["schema_version"] == "module_spec_context_retrieval_v1"
    assert persisted[1]["manifest"]["completed_modules"] == ["aes_key_expand_128", "aes_cipher_top"]
    assert persisted[1]["spec_context_file"] == "module_spec_context_json/aes_cipher_top.json"
    assert persisted[2]["manifest"]["stage3_status"] == "module_skeletons_planned"
    assert "KEYEXP UNIQUE SPEC MARKER" in backend.calls[1]["user_prompt"]
    assert "TOP UNIQUE SPEC MARKER" not in backend.calls[1]["user_prompt"]
    assert "TOP UNIQUE SPEC MARKER" in backend.calls[3]["user_prompt"]
    assert '"module": "aes_key_expand_128"' in backend.calls[1]["user_prompt"]
    assert '"module": "aes_cipher_top"' in backend.calls[3]["user_prompt"]
    assert "generation order:" in backend.calls[1]["user_prompt"]
    assert "MODULE_SKELETON_DOC v1" in backend.calls[1]["user_prompt"]
    assert "block_kind" in backend.calls[1]["user_prompt"]
    assert '"module_skeleton"' not in backend.calls[1]["user_prompt"]


def test_stage3_agent_resolves_specs_from_directory_input(tmp_path):
    specs_dir = tmp_path / "specs"
    specs_dir.mkdir()
    top_spec, key_spec = make_module_spec_files(specs_dir)
    task, _, _ = make_task_input(tmp_path, image_count=1)
    task = PlannerTaskInput(
        task_id=task.task_id,
        spec_md_files=[str(specs_dir)],
        spec_images=[],
        project_type=task.project_type,
        notes=task.notes,
    )
    stage1_artifact = make_stage1_contract_artifact(top_spec, [])
    modules_artifact = build_module_organized_artifact(stage1_artifact)
    stage2_artifact = validate_model(Stage2RepoSkeletonArtifact, make_repo_skeleton_payload())
    backend = QueueBackend(
        [
            make_module_spec_context_payload("aes_key_expand_128", key_spec),
            make_stage3_module_skeleton_doc("aes_key_expand_128", key_spec),
            make_module_spec_context_payload("aes_cipher_top", top_spec),
            make_stage3_module_skeleton_doc("aes_cipher_top", top_spec),
        ]
    )
    agent = Stage3Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run_incremental(task, {"modules": modules_artifact, "stage2": stage2_artifact})

    assert artifact.stage3_status == "module_skeletons_planned"
    assert [item.module for item in artifact.module_records] == ["aes_key_expand_128", "aes_cipher_top"]
    assert "KEYEXP UNIQUE SPEC MARKER" in backend.calls[1]["user_prompt"]
    assert "TOP UNIQUE SPEC MARKER" in backend.calls[3]["user_prompt"]


def test_stage3_agent_falls_back_to_unified_spec_when_module_spec_is_missing(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    stage1_artifact = make_stage1_contract_artifact(md_path, image_paths)
    modules_artifact = build_module_organized_artifact(stage1_artifact)
    stage2_artifact = validate_model(Stage2RepoSkeletonArtifact, make_repo_skeleton_payload())
    backend = QueueBackend(
        [
            {
                "schema_version": "module_spec_context_retrieval_v1",
                "module": "aes_key_expand_128",
                "blocks": [
                    {
                        "block_id": "S001",
                        "text": "## Submodules\naes_key_expand_128 is an explicit helper block used by aes_cipher_top.",
                        "source_file": str(md_path.resolve()),
                        "source_chunk_ids": ["C006"],
                        "relevance_reason": ["Submodule section names aes_key_expand_128."],
                        "confidence": "medium",
                    }
                ],
                "fallback_used": False,
            },
            make_stage3_module_skeleton_doc("aes_key_expand_128", md_path),
            make_module_spec_context_payload("aes_cipher_top", md_path),
            make_stage3_module_skeleton_doc("aes_cipher_top", md_path),
        ]
    )
    agent = Stage3Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run_incremental(
        task,
        {"modules": modules_artifact, "stage2": stage2_artifact},
    )

    assert artifact.stage3_status == "module_skeletons_planned"
    assert backend.calls[0]["mode"] == "complete"
    assert "MODULE SPEC CONTEXT RETRIEVAL" not in backend.calls[1]["user_prompt"]
    assert "Top module: aes_cipher_top" in backend.calls[3]["user_prompt"]


def test_stage3_agent_resume_regenerates_missing_sidecars(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    top_spec, key_spec = make_module_spec_files(tmp_path)
    top_spec.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    stage1_artifact = make_stage1_contract_artifact(md_path, image_paths)
    modules_artifact = build_module_organized_artifact(stage1_artifact)
    stage2_artifact = validate_model(Stage2RepoSkeletonArtifact, make_repo_skeleton_payload())
    existing_manifest = {
        "schema_version": "stage3_skeleton_docs_v1",
        "task_id": task.task_id,
        "source_schema_versions": {
            "modules": modules_artifact.schema_version,
            "repo_skeleton": stage2_artifact.schema_version,
        },
        "stage3_status": "module_skeletons_in_progress",
        "top_module": stage2_artifact.top_module,
        "module_order": modules_artifact.module_order,
        "completed_modules": ["aes_cipher_top"],
        "global_summary": ["resume test"],
        "module_records": [
            {
                "module": "aes_cipher_top",
                "doc_file": "module_skeleton_docs/aes_cipher_top.md",
                "export_file": "module_skeleton_json/aes_cipher_top.json",
                "export_schema_version": "module_skeleton_export_v1",
                "source_refs": {
                    "module_contract_ref": "module_contracts_v1::aes_cipher_top",
                    "repo_skeleton_ref": "repo_skeleton_v1::aes_cipher_top",
                    "module_spec_file": str(top_spec.resolve()),
                },
                "planning_note": "stale manifest entry",
                "block_ids": ["B1"],
            }
        ],
        "open_issues": [],
        "quality_report": None,
    }
    backend = QueueBackend(
        [
            make_module_spec_context_payload("aes_key_expand_128", key_spec),
            make_stage3_module_skeleton_doc("aes_key_expand_128", key_spec),
            make_module_spec_context_payload("aes_cipher_top", top_spec),
            make_stage3_module_skeleton_doc("aes_cipher_top", top_spec),
        ]
    )
    agent = Stage3Agent(PlannerLLMClient(backend=backend), output_root=tmp_path / "outputs")

    artifact = agent.run_incremental(
        task,
        {"modules": modules_artifact, "stage2": stage2_artifact, "stage3": existing_manifest},
    )

    assert artifact.stage3_status == "module_skeletons_planned"
    assert artifact.module_order == ["aes_key_expand_128", "aes_cipher_top"]
    assert [item.module for item in artifact.module_records] == ["aes_key_expand_128", "aes_cipher_top"]
    assert len(backend.calls) == 4


def test_stage3_agent_resume_uses_cursor_and_skips_completed_sidecar(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    top_spec, key_spec = make_module_spec_files(tmp_path)
    top_spec.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    stage1_artifact = make_stage1_contract_artifact(md_path, image_paths)
    modules_artifact = build_module_organized_artifact(stage1_artifact)
    stage2_artifact = validate_model(Stage2RepoSkeletonArtifact, make_repo_skeleton_payload())
    output_root = tmp_path / "outputs"
    (output_root / "module_skeleton_docs").mkdir(parents=True)
    (output_root / "module_skeleton_json").mkdir(parents=True)

    completed_doc = make_stage3_module_skeleton_doc("aes_key_expand_128", key_spec)
    completed_export = parse_module_skeleton_doc(
        completed_doc,
        expected_module="aes_key_expand_128",
        expected_file_path="rtl/aes_key_expand_128.v",
        source_refs={
            "module_contract_ref": "module_contracts_v1::aes_key_expand_128",
            "repo_skeleton_ref": "repo_skeleton_v1::aes_key_expand_128",
            "module_spec_file": str(key_spec.resolve()),
        },
    )
    (output_root / "module_skeleton_docs" / "aes_key_expand_128.md").write_text(completed_doc, encoding="utf-8")
    (output_root / "module_skeleton_json" / "aes_key_expand_128.json").write_text(
        json.dumps(completed_export.model_dump(), indent=2),
        encoding="utf-8",
    )
    existing_manifest = {
        "schema_version": "stage3_skeleton_docs_v1",
        "task_id": task.task_id,
        "source_schema_versions": {
            "modules": modules_artifact.schema_version,
            "repo_skeleton": stage2_artifact.schema_version,
        },
        "stage3_status": "module_skeletons_in_progress",
        "top_module": stage2_artifact.top_module,
        "module_order": ["aes_key_expand_128", "aes_cipher_top"],
        "completed_modules": ["aes_key_expand_128"],
        "resume_cursor": 1,
        "global_summary": ["resume test"],
        "module_records": [
            {
                "module": "aes_key_expand_128",
                "doc_file": "module_skeleton_docs/aes_key_expand_128.md",
                "export_file": "module_skeleton_json/aes_key_expand_128.json",
                "export_schema_version": "module_skeleton_export_v1",
                "source_refs": {
                    "module_contract_ref": "module_contracts_v1::aes_key_expand_128",
                    "repo_skeleton_ref": "repo_skeleton_v1::aes_key_expand_128",
                    "module_spec_file": str(key_spec.resolve()),
                },
                "planning_note": "completed checkpoint",
                "block_ids": [item.block_id for item in completed_export.structural_blocks],
            }
        ],
        "open_issues": [],
        "quality_report": None,
    }
    backend = QueueBackend(
        [
            make_module_spec_context_payload("aes_cipher_top", top_spec),
            make_stage3_module_skeleton_doc("aes_cipher_top", top_spec),
        ]
    )
    agent = Stage3Agent(PlannerLLMClient(backend=backend), output_root=output_root)

    artifact = agent.run_incremental(
        task,
        {"modules": modules_artifact, "stage2": stage2_artifact, "stage3": existing_manifest},
    )

    assert artifact.stage3_status == "module_skeletons_planned"
    assert artifact.completed_modules == ["aes_key_expand_128", "aes_cipher_top"]
    assert artifact.resume_cursor == 2
    assert len(backend.calls) == 2
    assert "TOP UNIQUE SPEC MARKER" in backend.calls[1]["user_prompt"]
    assert "KEYEXP UNIQUE SPEC MARKER" not in backend.calls[1]["user_prompt"]


def test_stage3_agent_reuses_definition_only_undecided_export(tmp_path):
    spec_path = tmp_path / "sd_defines.md"
    spec_path.write_text("# sd_defines\nDefinition constants only.\n", encoding="utf-8")
    output_root = tmp_path / "outputs"
    (output_root / "module_skeleton_docs").mkdir(parents=True)
    (output_root / "module_skeleton_json").mkdir(parents=True)
    doc = make_stage3_module_skeleton_doc("sd_defines", spec_path).replace(
        "- control_style: mixed",
        "- control_style: undecided",
    )
    export = parse_module_skeleton_doc(
        doc,
        expected_module="sd_defines",
        expected_file_path="rtl/sd_defines.v",
        source_refs={
            "module_contract_ref": "module_contracts_v1::sd_defines",
            "repo_skeleton_ref": "repo_skeleton_v1::sd_defines",
            "module_spec_file": str(spec_path.resolve()),
        },
    )
    (output_root / "module_skeleton_docs" / "sd_defines.md").write_text(doc, encoding="utf-8")
    (output_root / "module_skeleton_json" / "sd_defines.json").write_text(
        json.dumps(export.model_dump(), indent=2),
        encoding="utf-8",
    )
    agent = Stage3Agent(PlannerLLMClient(backend=QueueBackend([])), output_root=output_root)
    record = agent._build_module_record(export)

    assert agent._record_is_reusable(
        record,
        expected_module="sd_defines",
        expected_spec_path=str(spec_path),
    )


def test_stage3_parser_builds_export_from_doc(tmp_path):
    spec_path = tmp_path / "aes_cipher_top.md"
    spec_path.write_text("# aes_cipher_top\n", encoding="utf-8")
    doc = make_stage3_module_skeleton_doc("aes_cipher_top", spec_path)

    export = parse_module_skeleton_doc(
        doc,
        expected_module="aes_cipher_top",
        expected_file_path="rtl/aes_cipher_top.v",
        source_refs={
            "module_contract_ref": "module_contracts_v1::aes_cipher_top",
            "repo_skeleton_ref": "repo_skeleton_v1::aes_cipher_top",
            "module_spec_file": str(spec_path.resolve()),
        },
    )

    assert export.schema_version == "module_skeleton_export_v1"
    assert export.module == "aes_cipher_top"
    assert export.module_behavior.control_style == "counter_driven"
    assert any(item.block_kind == "helper" for item in export.structural_blocks)


def test_stage3_parser_defaults_partial_state_model_entries(tmp_path):
    spec_path = tmp_path / "sdc_controller.md"
    spec_path.write_text("# sdc_controller\n", encoding="utf-8")
    doc = make_stage3_module_skeleton_doc("sdc_controller", spec_path).replace(
        "  - object: round_key_reg\n    storage_kind: registered\n    representation: packed vector\n    notes: primary stored representation for the module",
        "  - object: no top-level registered state objects; state held inside sub-modules",
    )

    export = parse_module_skeleton_doc(
        doc,
        expected_module="sdc_controller",
        expected_file_path="rtl/sdc_controller.v",
        source_refs={
            "module_contract_ref": "module_contracts_v1::sdc_controller",
            "repo_skeleton_ref": "repo_skeleton_v1::sdc_controller",
            "module_spec_file": str(spec_path.resolve()),
        },
    )

    state_entry = export.module_behavior.state_model[0]
    assert state_entry.object == "no top-level registered state objects; state held inside sub-modules"
    assert state_entry.storage_kind == "unspecified"
    assert state_entry.representation == "implementation-open"


def test_spec_block_splitter_handles_bold_numbered_headings():
    blocks = split_spec_blocks(
        "\n".join(
            [
                "**aes_sbox Design Specification**",
                "",
                "**1. Introduction**",
                "Intro text.",
                "",
                "**2. Block Diagram**",
                "Diagram text.",
                "",
                "**4.1 Basic Principle**",
                "Lookup table details.",
            ]
        )
    )

    assert [item.block_id for item in blocks] == ["S001", "S002", "S003"]
    assert blocks[0].text.startswith("**aes_sbox Design Specification**")
    assert "**1. Introduction**" in blocks[0].text
    assert blocks[1].text.startswith("**2. Block Diagram**")
    assert blocks[2].text.startswith("**4.1 Basic Principle**")


def test_spec_block_splitter_extracts_module_from_unified_spec():
    unified = "\n".join(
        [
            "# aes_inv_cipher_top Design Specification**",
            "",
            "## 1. Introduction**",
            "Top text.",
            "",
            "# aes_inv_sbox Design Specification**",
            "",
            "## 1. Introduction**",
            "Inverse sbox intro.",
            "",
            "**4.1 Basic Principle**",
            "Inverse lookup table.",
            "",
            "# aes_rcon Design Specification",
            "",
            "## 1. Introduction",
            "Rcon text.",
        ]
    )

    module_text = extract_module_section(unified, "aes_inv_sbox")
    blocks = split_spec_blocks(module_text)

    assert module_text.startswith("# aes_inv_sbox Design Specification**")
    assert "Top text." not in module_text
    assert "Rcon text." not in module_text
    assert [item.block_id for item in blocks] == ["S001", "S002"]
    assert "Inverse sbox intro." in blocks[0].text
    assert "Inverse lookup table." in blocks[1].text


def test_module_spec_context_retriever_falls_back_when_llm_returns_non_source_text(tmp_path):
    spec_path = tmp_path / "aes_cipher_system.md"
    spec_path.write_text(
        "\n".join(
            [
                "# AES Unified Spec",
                "",
                "## SubBytes",
                "The SubBytes step uses S-box substitution for each state byte.",
                "",
                "## RCON",
                "The round constant output changes only in the MSB.",
            ]
        ),
        encoding="utf-8",
    )
    backend = QueueBackend(
        [
            {
                "schema_version": "module_spec_context_retrieval_v1",
                "module": "aes_sbox",
                "blocks": [
                    {
                        "block_id": "S001",
                        "text": "This hallucinated text is not copied from the source.",
                        "source_file": str(spec_path),
                        "source_chunk_ids": ["C001"],
                        "relevance_reason": ["bad output"],
                        "confidence": "high",
                    }
                ],
                "fallback_used": False,
            }
        ]
    )
    retriever = ModuleSpecContextRetriever(PlannerLLMClient(backend=backend))

    result = retriever.select_module_spec_context(
        module_name="aes_sbox",
        spec_md_files=[str(spec_path)],
        repo_module={"role": "S-box substitution unit", "parents": ["aes_cipher_top"], "children": []},
    )

    assert result.fallback_used is True
    assert result.blocks
    assert "SubBytes" in result.blocks[0].text
    assert result.open_issues


def test_module_spec_context_prompt_preserves_source_chunk_order_after_ranking(tmp_path):
    spec_path = tmp_path / "aes_spec.md"
    spec_path.write_text(
        "\n".join(
            [
                "# AES Spec",
                "",
                "## Interface",
                "The S-box substitution unit has input byte_in and output byte_out.",
                "",
                "## Background",
                "This project overview mentions AES rounds.",
                "",
                "## Validation",
                "aes_sbox sbox S-box SubBytes substitution combinational lookup validates the output byte.",
            ]
        ),
        encoding="utf-8",
    )
    interface_text = "## Interface\nThe S-box substitution unit has input byte_in and output byte_out."
    backend = QueueBackend(
        [
            {
                "schema_version": "module_spec_context_retrieval_v1",
                "module": "aes_sbox",
                "blocks": [
                    {
                        "block_id": "S001",
                        "text": interface_text,
                        "source_file": str(spec_path.resolve()),
                        "source_chunk_ids": ["C002"],
                        "relevance_reason": ["Interface section constrains aes_sbox ports."],
                        "confidence": "high",
                    }
                ],
                "fallback_used": False,
            }
        ]
    )
    retriever = ModuleSpecContextRetriever(PlannerLLMClient(backend=backend), max_chunks=3)

    result = retriever.select_module_spec_context(
        module_name="aes_sbox",
        spec_md_files=[str(spec_path)],
        repo_module={"role": "S-box substitution unit", "parents": ["aes_cipher_top"], "children": []},
    )

    prompt = backend.calls[0]["user_prompt"]
    assert result.fallback_used is False
    assert prompt.index('"chunk_id": "C002"') < prompt.index('"chunk_id": "C004"')


def test_stage4_spec_blocks_uses_module_context_retrieval_for_unified_spec_without_section(tmp_path):
    spec_path = tmp_path / "aes_cipher_system.md"
    spec_path.write_text(
        "\n".join(
            [
                "# AES Unified Spec",
                "",
                "## Top",
                "Top module: aes_cipher_top",
                "The top controller sequences AES rounds.",
                "",
                "## SubBytes",
                "SubBytes requires S-box substitution for every state byte.",
                "The S-box maps an input byte to an output byte through combinational lookup.",
            ]
        ),
        encoding="utf-8",
    )
    task = PlannerTaskInput(
        task_id="aes_demo_001",
        spec_md_files=[str(spec_path)],
        spec_images=[],
        project_type="light_repo_spec2rtl",
        notes="unified spec retrieval test",
    )
    stage2_artifact = validate_model(
        Stage2RepoSkeletonArtifact,
        {
            "task_id": task.task_id,
            "stage2_status": "repo_skeleton_planned",
            "top_module": "aes_cipher_top",
            "global_invariants": {
                "hierarchy": [{"parent": "aes_cipher_top", "child": "aes_sbox"}],
                "file_map": {
                    "aes_sbox": "rtl/aes_sbox.v",
                    "aes_cipher_top": "rtl/aes_cipher_top.v",
                },
            },
            "modules": [
                {
                    "module": "aes_sbox",
                    "file_path": "rtl/aes_sbox.v",
                    "role": "S-box byte substitution lookup",
                    "kind": "leaf_combinational",
                    "parents": ["aes_cipher_top"],
                    "children": [],
                    "instance_hints": [],
                },
                {
                    "module": "aes_cipher_top",
                    "file_path": "rtl/aes_cipher_top.v",
                    "role": "top controller",
                    "kind": "top_controller",
                    "parents": [],
                    "children": ["aes_sbox"],
                    "instance_hints": [],
                },
            ],
            "planning_decisions": {
                "generation_order": ["aes_sbox", "aes_cipher_top"],
                "leaf_first": True,
                "shared_modules": [],
            },
            "open_issues": [],
        },
    )
    stage3_artifact = validate_model(
        Stage3ModuleSkeletonArtifact,
        {
            "task_id": task.task_id,
            "source_schema_versions": {
                "modules": "module_contracts_v1",
                "repo_skeleton": stage2_artifact.schema_version,
            },
            "stage3_status": "module_skeletons_planned",
            "top_module": "aes_cipher_top",
            "module_order": ["aes_sbox", "aes_cipher_top"],
            "completed_modules": ["aes_sbox", "aes_cipher_top"],
            "resume_cursor": 2,
            "global_summary": ["unified spec"],
            "module_records": [
                {
                    "module": "aes_sbox",
                    "doc_file": "module_skeleton_docs/aes_sbox.md",
                    "export_file": "module_skeleton_json/aes_sbox.json",
                    "export_schema_version": "module_skeleton_export_v1",
                    "source_refs": {
                        "module_contract_ref": "module_contracts_v1::aes_sbox",
                        "repo_skeleton_ref": "repo_skeleton_v1::aes_sbox",
                        "module_spec_file": str(spec_path.resolve()),
                    },
                    "planning_note": "S-box lookup skeleton.",
                    "block_ids": ["B1"],
                },
                {
                    "module": "aes_cipher_top",
                    "doc_file": "module_skeleton_docs/aes_cipher_top.md",
                    "export_file": "module_skeleton_json/aes_cipher_top.json",
                    "export_schema_version": "module_skeleton_export_v1",
                    "source_refs": {
                        "module_contract_ref": "module_contracts_v1::aes_cipher_top",
                        "repo_skeleton_ref": "repo_skeleton_v1::aes_cipher_top",
                        "module_spec_file": str(spec_path.resolve()),
                    },
                    "planning_note": "Top controller skeleton.",
                    "block_ids": ["B1"],
                },
            ],
            "open_issues": [],
        },
    )
    backend = QueueBackend(
        [
            {
                "schema_version": "module_spec_context_retrieval_v1",
                "module": "aes_sbox",
                "blocks": [
                    {
                        "block_id": "S001",
                        "text": "## SubBytes\nSubBytes requires S-box substitution for every state byte.\nThe S-box maps an input byte to an output byte through combinational lookup.",
                        "source_file": str(spec_path.resolve()),
                        "source_chunk_ids": ["C003"],
                        "relevance_reason": ["SubBytes text describes the S-box module role."],
                        "confidence": "high",
                    }
                ],
                "fallback_used": False,
            },
            {
                "schema_version": "module_spec_context_retrieval_v1",
                "module": "aes_cipher_top",
                "blocks": [
                    {
                        "block_id": "S001",
                        "text": "## Top\nTop module: aes_cipher_top\nThe top controller sequences AES rounds.",
                        "source_file": str(spec_path.resolve()),
                        "source_chunk_ids": ["C002"],
                        "relevance_reason": ["Top section describes the controller."],
                        "confidence": "high",
                    }
                ],
                "fallback_used": False,
            },
        ]
    )
    agent = Stage4SpecBlocksAgent(PlannerLLMClient(backend=backend))

    artifact = agent.run(task, {"stage2": stage2_artifact, "stage3": stage3_artifact})

    assert artifact.module_order == ["aes_sbox", "aes_cipher_top"]
    assert "S-box maps an input byte" in artifact.modules[0].blocks[0].text
    assert "top controller sequences" in artifact.modules[1].blocks[0].text


def test_spec_block_splitter_merges_heading_only_parent_blocks():
    blocks = split_spec_blocks(
        "\n".join(
            [
                "**aes_key_expand_128 Design Specification**",
                "",
                "**1. Introduction**",
                "Intro text.",
                "",
                "**4. Operation Principle**",
                "",
                "**4.1 Basic Principle**",
                "Basic text.",
                "",
                "**4.2 Mathematical Derivation**",
                "Math text.",
            ]
        )
    )

    assert [item.block_id for item in blocks] == ["S001", "S002", "S003"]
    assert blocks[1].text.startswith("**4. Operation Principle**")
    assert "**4.1 Basic Principle**" in blocks[1].text
    assert "Basic text." in blocks[1].text
    assert blocks[2].text.startswith("**4.2 Mathematical Derivation**")


def test_stage3_parser_accepts_asterisk_field_bullets_and_combined_overlay_section(tmp_path):
    spec_path = tmp_path / "aes_sbox.md"
    spec_path.write_text("# aes_sbox\n", encoding="utf-8")
    doc = "\n".join(
        [
            "# MODULE_SKELETON_DOC v1",
            "",
            "## 0. Module Identity",
            "- module_name: aes_sbox",
            "- file_path: rtl/aes_sbox.v",
            "- source_refs:",
            "  - module_contract_ref: module_contracts_v1::aes_sbox",
            "  - repo_skeleton_ref: repo_skeleton_v1::aes_sbox",
            f"  - module_spec_file: {spec_path.resolve()}",
            "- planning_note: Compact combinational lookup planning.",
            "",
            "## 1. Module Frame",
            "```verilog",
            "module aes_sbox (",
            "    // ports",
            ");",
            "// <block: decl_ports>",
            "// <block: decl_rom>",
            "// <block: comb_lookup>",
            "endmodule",
            "```",
            "",
            "## 2. Structural Skeleton",
            "### Block",
            "* block_id: B1",
            "* block_label: decl_ports",
            "* block_kind: decl",
            "* required: true",
            "* purpose: Declare ports.",
            "* code_shape: declaration group",
            "* depends_on: []",
            "* placeholder:",
            "```verilog",
            "// skeleton only: ports",
            "```",
            "* must_appear:",
            "  * input a",
            "  * output b",
            "* may_appear:",
            "  * width comments",
            "* retrieval_focus:",
            "  * interface",
            "",
            "### Block",
            "* block_id: B2",
            "* block_label: decl_rom",
            "* block_kind: decl",
            "* required: true",
            "* purpose: Declare the lookup table.",
            "* code_shape: constant declaration group",
            "* depends_on: []",
            "* placeholder:",
            "```verilog",
            "// skeleton only: rom declaration",
            "```",
            "* must_appear:",
            "  * table object",
            "* may_appear:",
            "  * init comments",
            "* retrieval_focus:",
            "  * lookup values",
            "",
            "### Block",
            "* block_id: B3",
            "* block_label: comb_lookup",
            "* block_kind: comb",
            "* required: true",
            "* purpose: Map a to b with the table.",
            "* code_shape: combinational path",
            "* depends_on: [B1, B2]",
            "* placeholder:",
            "```verilog",
            "// skeleton only: lookup mapping",
            "```",
            "* must_appear:",
            "  * output path",
            "* may_appear:",
            "  * cast comments",
            "* retrieval_focus:",
            "  * output timing",
            "",
            "## 3. Behavioral Overlay",
            "### Module-Level Behavioral Summary",
            "* control_style: mixed",
            "* semantic_modes:",
            "  * LUT: direct substitution",
            "* state_model:",
            "  * object: lookup_path",
            "    storage_kind: stateless",
            "    representation: combinational",
            "    notes: no sequential storage",
            "* global_invariants:",
            "  * output depends only on input a",
            "* open_semantic_questions:",
            "  * exact constant declaration form",
            "",
            "### Block Behavioral Overlay",
            "* block_id: B1",
            "* responsibilities:",
            "  * expose ports",
            "* timing_semantics:",
            "  * combinational interface only",
            "* touched_objects:",
            "  * a",
            "  * b",
            "* coupling_rules:",
            "  * widths align with parent modules",
            "* forbidden_drift:",
            "  * no extra handshake ports",
            "",
            "* block_id: B3",
            "* responsibilities:",
            "  * drive output through lookup",
            "* timing_semantics:",
            "  * immediate combinational evaluation",
            "* touched_objects:",
            "  * a",
            "  * b",
            "* coupling_rules:",
            "  * depends on B2 table dimensions",
            "* forbidden_drift:",
            "  * no sequential latency",
            "",
            "## 4. Decision Ledger",
            "### Chosen Decision",
            "* topic: lookup strategy",
            "* decision: Keep the design lookup-based.",
            "* reason: The spec describes a table-based implementation.",
            "",
            "### Deferred Decision",
            "* items:",
            "  * exact declaration syntax",
            "",
            "### Structural Risk",
            "* items:",
            "  * table declaration may become verbose",
            "",
            "### Behavioral Risk",
            "* items:",
            "  * parent timing closure remains external",
        ]
    )

    export = parse_module_skeleton_doc(
        doc,
        expected_module="aes_sbox",
        expected_file_path="rtl/aes_sbox.v",
        source_refs={
            "module_contract_ref": "module_contracts_v1::aes_sbox",
            "repo_skeleton_ref": "repo_skeleton_v1::aes_sbox",
            "module_spec_file": str(spec_path.resolve()),
        },
    )

    assert [item.block_id for item in export.structural_blocks] == ["B1", "B2", "B3"]
    assert [item.block_id for item in export.block_behavior_overlays] == ["B1", "B3"]


def test_stage3_parser_rejects_unknown_overlay_block(tmp_path):
    spec_path = tmp_path / "aes_cipher_top.md"
    spec_path.write_text("# aes_cipher_top\n", encoding="utf-8")
    doc = make_stage3_module_skeleton_doc("aes_cipher_top", spec_path).replace(
        "- block_id: B2\n- responsibilities:",
        "- block_id: B999\n- responsibilities:",
        1,
    )

    with pytest.raises(ValueError, match="unknown block_id"):
        parse_module_skeleton_doc(
            doc,
            expected_module="aes_cipher_top",
            expected_file_path="rtl/aes_cipher_top.v",
            source_refs={
                "module_contract_ref": "module_contracts_v1::aes_cipher_top",
                "repo_skeleton_ref": "repo_skeleton_v1::aes_cipher_top",
                "module_spec_file": str(spec_path.resolve()),
            },
        )


def test_default_planner_backend_sends_images_as_multimodal_content(tmp_path, monkeypatch):
    image_path = tmp_path / "fsm.png"
    image_path.write_bytes(b"\x89PNG\r\n\x1a\n")

    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured["kwargs"] = kwargs

            class Message:
                content = '{"ok": true}'

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAIClient:
        chat = FakeChat()

    class FakeOpenAI:
        NOT_GIVEN = object()

        def OpenAI(self, **kwargs):
            captured["client_kwargs"] = kwargs
            return FakeOpenAIClient()

    class FakeLLMClient:
        def __init__(self, config):
            self.config = config

        def generate(self, memory, max_retries=1, retry_delay=0.0):
            raise AssertionError("text-only path should not be used in this test")

    real_import_module = importlib.import_module

    monkeypatch.setattr("zerorepo.rtl_impl.module_planner.utils.llm_client.LLMClient", FakeLLMClient)
    monkeypatch.setattr("importlib.import_module", lambda name: FakeOpenAI() if name == "openai" else real_import_module(name))

    backend = DefaultPlannerLLMBackend(
        {
            "provider": "openai",
            "model": "gpt-5-mini",
            "api_key": "test-key",
            "max_tokens": 256,
        }
    )
    backend.complete(system_prompt="sys", user_prompt="user", images=[str(image_path)])

    messages = captured["kwargs"]["messages"]
    assert messages[1]["content"][0] == {"type": "text", "text": "user"}
    assert messages[1]["content"][1]["type"] == "image_url"
