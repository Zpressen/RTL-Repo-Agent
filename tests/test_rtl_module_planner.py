from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest
from pydantic import BaseModel

from zerorepo.rtl_impl.retrieval_agent import BlockSpecRetriever, BlockSpecRetrievalResult
from zerorepo.rtl_impl.module_planner.agents import (
    Stage1Agent,
    Stage2Agent,
    Stage3Agent,
    Stage4ModulePlanAgent,
    Stage5Agent,
    Stage6MergeAgent,
)
import zerorepo.rtl_impl.module_planner.agents.global_defines as global_defines_mod
from zerorepo.rtl_impl.module_planner.agents.base import BaseStageAgent, validate_model
from zerorepo.rtl_impl.module_planner.module_organizer import build_module_organized_artifact
from zerorepo.rtl_impl.module_planner.planner_runner import PlannerRunner
from zerorepo.rtl_impl.module_planner.prompts import stage1_ingest_extract
from zerorepo.rtl_impl.module_planner.schemas import (
    ModuleOrganizationArtifact,
    PlannerTaskInput,
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
    return validate_model(
        Stage1ContractsArtifact,
        {
            "task_id": "aes_demo_001",
            "stage1_status": "contracts_completed",
            "completed_rounds": ["structure", "interface", "timing", "control", "datapath", "planning_facts"],
            **make_structure_payload(md_path),
            **make_interface_payload(md_path),
            **make_timing_payload(md_path, image_paths[0] if image_paths else None),
            **make_control_payload(md_path, image_paths[0] if image_paths else None),
            **make_datapath_payload(md_path),
            **make_planning_facts_payload(md_path),
        },
    )


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


def test_stage1_agent_runs_all_contract_rounds_without_alias_groups(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    backend = QueueBackend(
        [
            make_structure_payload(md_path),
            make_interface_payload(md_path),
            make_timing_payload(md_path, image_paths[0]),
            make_control_payload(md_path, image_paths[0]),
            make_datapath_payload(md_path),
            make_planning_facts_payload(md_path),
        ]
    )
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
    assert artifact.completed_rounds == ["structure", "interface", "timing", "control", "datapath", "planning_facts"]
    assert artifact.completed_batches == ["batch_0001"]
    assert artifact.structure_contract.top_module == "aes_cipher_top"
    assert artifact.interface_contracts[0].ports[0].name == "clk"
    assert artifact.timing_contracts[0].clocking["clock"] == "clk"
    assert artifact.control_contracts[0].abstract_states == ["IDLE", "LOAD", "ROUND_PROC", "DONE"]
    assert artifact.datapath_contracts[0].main_flow[0] == "initial_addroundkey"
    assert artifact.planning_facts[0].registers[0].name == "state_reg"
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

    responses = []
    for module_name, md_path, child in [
        ("mod_1", module_paths[0], "mod_6"),
        ("mod_6", module_paths[5], ""),
    ]:
        responses.extend(
            [
                make_module_structure_payload(module_name, md_path, child=child),
                make_minimal_interface_payload(module_name, md_path),
                {"timing_contracts": []},
                make_minimal_control_payload(module_name, md_path),
                make_minimal_datapath_payload(module_name, md_path),
                make_minimal_planning_facts_payload(module_name, md_path, child=child),
            ]
        )
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
    assert len(backend.calls) == 12
    assert backend.calls[0]["user_prompt"].count("[Document DOC_") == 5
    assert backend.calls[6]["user_prompt"].count("[Document DOC_") == 1
    organized = build_module_organized_artifact(artifact)
    assert organized.module_order[:6] == [f"mod_{index}" for index in range(1, 7)]


def test_stage1_agent_passes_existing_contracts_into_later_round_prompts(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    backend = QueueBackend(
        [
            make_structure_payload(md_path),
            make_interface_payload(md_path),
            make_timing_payload(md_path, image_paths[0]),
            make_control_payload(md_path, image_paths[0]),
            make_datapath_payload(md_path),
            make_planning_facts_payload(md_path),
        ]
    )
    agent = Stage1Agent(PlannerLLMClient(backend=backend))

    agent.run(task, {})

    assert '"top_module": "aes_cipher_top"' in backend.calls[1]["user_prompt"]
    assert '"interface_contracts"' in backend.calls[2]["user_prompt"]
    assert '"timing_contracts"' in backend.calls[3]["user_prompt"]
    assert '"control_contracts"' in backend.calls[4]["user_prompt"]
    assert '"datapath_contracts"' in backend.calls[5]["user_prompt"]


def test_stage1_agent_interface_contract_uses_module_level_grounding_only(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    backend = QueueBackend(
        [
            make_structure_payload(md_path),
            make_interface_payload(md_path),
            make_timing_payload(md_path, image_paths[0]),
            make_control_payload(md_path, image_paths[0]),
            make_datapath_payload(md_path),
            make_planning_facts_payload(md_path),
        ]
    )
    agent = Stage1Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run(task, {})
    dumped = artifact.model_dump()

    assert dumped["interface_contracts"][0]["text_grounding"]
    assert "text_grounding" not in dumped["interface_contracts"][0]["ports"][0]


def test_stage1_agent_accepts_structurally_valid_timing_without_keyword_gate(tmp_path):
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
            make_empty_structure_payload(),
            {"interface_contracts": []},
            {
                "timing_contracts": [
                    {
                        "module": "aes_cipher_top",
                        "clocking": {},
                        "reset_behavior": {},
                        "registered_objects": [],
                        "phase_timing": [
                            {
                                "phase": "completion",
                                "timing": "done is asserted when processing finishes",
                            }
                        ],
                        "timing_rules": [],
                        "underspecified": [],
                    }
                ]
            },
            {"control_contracts": []},
            {"datapath_contracts": []},
            {"planning_facts": []},
        ]
    )
    agent = Stage1Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run(task, {})

    assert len(artifact.timing_contracts) == 1
    assert artifact.timing_contracts[0].phase_timing[0]["phase"] == "completion"
    assert len(backend.calls) == 6
    assert "Do not treat the following as timing evidence by themselves" in backend.calls[2]["user_prompt"]


def test_stage1_agent_retries_when_timing_round_returns_empty_shell_contract(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    backend = QueueBackend(
        [
            make_structure_payload(md_path),
            make_interface_payload(md_path),
            {
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
                ]
            },
            make_timing_payload(md_path, image_paths[0]),
            make_control_payload(md_path, image_paths[0]),
            make_datapath_payload(md_path),
            make_planning_facts_payload(md_path),
        ]
    )
    agent = Stage1Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run(task, {})

    assert artifact.timing_contracts[0].clocking["update_edge"] == "rising clock edge"
    assert artifact.timing_contracts[0].timing_rules[0] == "ld is sampled on the rising clock edge"
    assert len(backend.calls) == 7
    assert "empty shell timing contract" in backend.calls[3]["user_prompt"]


def test_stage1_timing_prompt_uses_empty_list_negative_example_and_broader_explicit_wording():
    prompt = stage1_ingest_extract.build_timing_prompt(
        document_markdown="# Demo",
        current_contracts_json='{"timing_contracts": []}',
        stage_context="{}",
    )

    assert '"timing_contracts": []' in prompt
    assert "Do not emit placeholder or shell contracts" in prompt
    assert '"clocking": {}' in prompt
    assert '"registered_objects": []' in prompt
    assert "synchronous loading" in prompt
    assert "register updates on clock rising edge" in prompt
    assert "one round per clock cycle" in prompt


def test_stage1_agent_ignores_spec_images_and_runs_text_rounds_only(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=2)
    backend = QueueBackend(
        [
            make_structure_payload(md_path),
            make_interface_payload(md_path),
            make_timing_payload(md_path, image_paths[0]),
            make_control_payload(md_path, image_paths[0]),
            make_datapath_payload(md_path),
            make_planning_facts_payload(md_path),
        ]
    )
    agent = Stage1Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run(task, {})

    assert len(backend.calls) == 6
    assert all(call["images"] == [] for call in backend.calls)
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
            make_empty_structure_payload(),
            {"interface_contracts": []},
            {"timing_contracts": []},
            {"control_contracts": []},
            {"datapath_contracts": []},
            {"planning_facts": []},
        ]
    )
    agent = Stage1Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run(task, {})

    assert artifact.structure_contract.top_module == ""
    assert artifact.structure_contract.modules == ["empty"]
    assert artifact.interface_contracts == []
    assert artifact.planning_facts == []
    assert "image_contracts" not in artifact.model_dump()


def test_planner_runner_writes_contracts_json_and_resume_reuses_it(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    output_root = tmp_path / "outputs"
    backend = QueueBackend(
        [
            make_structure_payload(md_path),
            make_interface_payload(md_path),
            make_timing_payload(md_path, image_paths[0]),
            make_control_payload(md_path, image_paths[0]),
            make_datapath_payload(md_path),
            make_planning_facts_payload(md_path),
        ]
    )
    runner = PlannerRunner(output_root=output_root, llm_backend=backend)

    first = runner.run(task, end_stage="stage1")
    second = runner.run(task, resume=True, end_stage="stage1")

    target = output_root / "contracts.json"
    modules_target = output_root / "modules.json"
    assert target.exists()
    assert modules_target.exists()
    payload = json.loads(target.read_text(encoding="utf-8"))
    modules_payload = json.loads(modules_target.read_text(encoding="utf-8"))
    assert payload["stage1_status"] == "contracts_completed"
    assert payload["completed_rounds"] == ["structure", "interface", "timing", "control", "datapath", "planning_facts"]
    assert "image_contracts" not in payload
    assert "entity_alias_groups" not in payload
    assert "text_grounding" not in json.dumps(payload, ensure_ascii=False)
    assert "text_grounding" not in json.dumps(modules_payload, ensure_ascii=False)
    assert payload["planning_facts"][0]["module"] == "aes_cipher_top"
    assert modules_payload["top_module"] == "aes_cipher_top"
    assert modules_payload["module_order"] == ["aes_cipher_top", "aes_key_expand_128"]
    assert modules_payload["modules"][0]["is_top_module"] is True
    assert modules_payload["modules"][0]["module"] == "aes_cipher_top"
    assert modules_payload["modules"][0]["planning_facts"]["module"] == "aes_cipher_top"
    assert first.completed_rounds == second.completed_rounds
    assert len(backend.calls) == 6


def test_planner_runner_resume_continues_from_partial_contracts_json(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    output_root = tmp_path / "outputs"
    output_root.mkdir(parents=True, exist_ok=True)
    partial_payload = {
        "task_id": task.task_id,
        "stage1_status": "interface_completed",
        "completed_rounds": ["structure", "interface"],
        **make_structure_payload(md_path),
        **make_interface_payload(md_path),
        "timing_contracts": [],
        "control_contracts": [],
        "datapath_contracts": [],
        "planning_facts": [],
    }
    partial_payload = drop_text_grounding(partial_payload)
    (output_root / "contracts.json").write_text(json.dumps(partial_payload, indent=2), encoding="utf-8")

    backend = QueueBackend(
        [
            make_timing_payload(md_path, image_paths[0]),
            make_control_payload(md_path, image_paths[0]),
            make_datapath_payload(md_path),
            make_planning_facts_payload(md_path),
        ]
    )
    runner = PlannerRunner(output_root=output_root, llm_backend=backend)

    artifact = runner.run(task, resume=True, end_stage="stage1")

    assert artifact.completed_rounds == ["structure", "interface", "timing", "control", "datapath", "planning_facts"]
    assert len(backend.calls) == 4


def test_planner_runner_resume_ignores_empty_shell_timing_artifact(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    output_root = tmp_path / "outputs"
    output_root.mkdir(parents=True, exist_ok=True)
    shell_payload = {
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
    shell_payload = drop_text_grounding(shell_payload)
    (output_root / "contracts.json").write_text(json.dumps(shell_payload, indent=2), encoding="utf-8")

    backend = QueueBackend(
        [
            make_structure_payload(md_path),
            make_interface_payload(md_path),
            make_timing_payload(md_path, image_paths[0]),
            make_control_payload(md_path, image_paths[0]),
            make_datapath_payload(md_path),
            make_planning_facts_payload(md_path),
        ]
    )
    runner = PlannerRunner(output_root=output_root, llm_backend=backend)

    artifact = runner.run(task, resume=True, end_stage="stage1")

    assert artifact.timing_contracts[0].clocking["clock"] == "clk"
    assert len(backend.calls) == 6


def test_planner_runner_writes_repo_skeleton_for_stage2(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    output_root = tmp_path / "outputs"
    backend = QueueBackend(
        [
            make_structure_payload(md_path),
            make_interface_payload(md_path),
            make_timing_payload(md_path, image_paths[0]),
            make_control_payload(md_path, image_paths[0]),
            make_datapath_payload(md_path),
            make_planning_facts_payload(md_path),
            make_repo_skeleton_payload(),
        ]
    )
    runner = PlannerRunner(output_root=output_root, llm_backend=backend)

    artifact = runner.run(task, end_stage="stage2")

    target = output_root / "repo_skeleton.json"
    assert isinstance(artifact, Stage2RepoSkeletonArtifact)
    assert target.exists()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["stage2_status"] == "repo_skeleton_planned"
    assert payload["top_module"] == "aes_cipher_top"
    assert "module_order" not in payload
    assert payload["planning_decisions"]["generation_order"] == ["aes_key_expand_128", "aes_cipher_top"]
    assert len(backend.calls) == 7


def test_planner_runner_resume_reuses_repo_skeleton_json(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    output_root = tmp_path / "outputs"
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "repo_skeleton.json").write_text(
        json.dumps(make_repo_skeleton_payload(), indent=2),
        encoding="utf-8",
    )
    backend = QueueBackend(
        [
            make_structure_payload(md_path),
            make_interface_payload(md_path),
            make_timing_payload(md_path, image_paths[0]),
            make_control_payload(md_path, image_paths[0]),
            make_datapath_payload(md_path),
            make_planning_facts_payload(md_path),
        ]
    )
    runner = PlannerRunner(output_root=output_root, llm_backend=backend)

    artifact = runner.run(task, resume=True, end_stage="stage2")

    assert isinstance(artifact, Stage2RepoSkeletonArtifact)
    assert artifact.stage2_status == "repo_skeleton_planned"
    assert len(backend.calls) == 6


def test_planner_runner_resume_runs_only_planning_facts_when_first_five_rounds_exist(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    output_root = tmp_path / "outputs"
    output_root.mkdir(parents=True, exist_ok=True)
    partial_payload = {
        "task_id": task.task_id,
        "stage1_status": "datapath_completed",
        "completed_rounds": ["structure", "interface", "timing", "control", "datapath"],
        **make_structure_payload(md_path),
        **make_interface_payload(md_path),
        **make_timing_payload(md_path, image_paths[0]),
        **make_control_payload(md_path, image_paths[0]),
        **make_datapath_payload(md_path),
        "planning_facts": [],
    }
    partial_payload = drop_text_grounding(partial_payload)
    (output_root / "contracts.json").write_text(json.dumps(partial_payload, indent=2), encoding="utf-8")

    backend = QueueBackend([make_planning_facts_payload(md_path)])
    runner = PlannerRunner(output_root=output_root, llm_backend=backend)

    artifact = runner.run(task, resume=True, end_stage="stage1")

    assert artifact.completed_rounds == ["structure", "interface", "timing", "control", "datapath", "planning_facts"]
    assert artifact.planning_facts[0].module == "aes_cipher_top"
    assert len(backend.calls) == 1


def test_planner_runner_writes_incremental_contract_statuses(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    output_root = tmp_path / "outputs"
    backend = QueueBackend(
        [
            make_structure_payload(md_path),
            make_interface_payload(md_path),
            make_timing_payload(md_path, image_paths[0]),
            make_control_payload(md_path, image_paths[0]),
            make_datapath_payload(md_path),
            make_planning_facts_payload(md_path),
        ]
    )
    runner = PlannerRunner(output_root=output_root, llm_backend=backend)

    writes = []
    original_write_payload = runner._write_payload

    def recording_write(payload):
        writes.append(payload.get("stage1_status"))
        return original_write_payload(payload)

    runner._write_payload = recording_write
    runner.run(task, end_stage="stage1")

    assert writes == [
        "batch_0001_structure_completed",
        "batch_0001_interface_completed",
        "batch_0001_timing_completed",
        "batch_0001_control_completed",
        "batch_0001_datapath_completed",
        "batch_0001_planning_facts_completed",
        "batch_0001_completed",
        "contracts_completed",
    ]


def test_planner_runner_supports_stage3_execution(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    top_spec, key_spec = make_module_spec_files(tmp_path)
    top_spec.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    backend = QueueBackend(
        [
            make_structure_payload(md_path),
            make_interface_payload(md_path),
            make_timing_payload(md_path, image_paths[0]),
            make_control_payload(md_path, image_paths[0]),
            make_datapath_payload(md_path),
            make_planning_facts_payload(md_path),
            make_repo_skeleton_payload(),
            make_stage3_module_skeleton_doc("aes_key_expand_128", key_spec),
            make_stage3_module_skeleton_doc("aes_cipher_top", top_spec),
        ]
    )
    runner = PlannerRunner(output_root=tmp_path / "outputs", llm_backend=backend)

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
            make_structure_payload(md_path),
            make_interface_payload(md_path),
            make_timing_payload(md_path, image_paths[0]),
            make_control_payload(md_path, image_paths[0]),
            make_datapath_payload(md_path),
            make_planning_facts_payload(md_path),
            make_repo_skeleton_payload(),
            make_stage3_module_skeleton_doc("aes_key_expand_128", key_spec),
            make_stage3_module_skeleton_doc("aes_cipher_top", top_spec),
            make_block_spec_retrieval_payload("aes_key_expand_128"),
            make_stage4_module_plan_payload("aes_key_expand_128"),
            make_block_spec_retrieval_payload("aes_cipher_top", top_module=True),
            make_stage4_module_plan_payload("aes_cipher_top", top_module=True),
        ]
    )
    output_root = tmp_path / "outputs"
    runner = PlannerRunner(output_root=output_root, llm_backend=backend)

    artifact = runner.run(task, end_stage="stage4")

    assert isinstance(artifact, Stage4ModulePlansArtifact)
    assert artifact.schema_version == "module_plans_v1"
    assert artifact.module_order == ["aes_key_expand_128", "aes_cipher_top"]
    assert [item.module for item in artifact.module_plan_files] == artifact.module_order
    spec_blocks_target = output_root / "spec_blocks.json"
    module_plans_target = output_root / "module_plans.json"
    key_plan_target = output_root / "module_plan_json" / "aes_key_expand_128.json"
    key_retrieval_target = output_root / "block_spec_retrieval_json" / "aes_key_expand_128.json"
    assert spec_blocks_target.exists()
    assert module_plans_target.exists()
    assert key_plan_target.exists()
    assert key_retrieval_target.exists()
    spec_payload = json.loads(spec_blocks_target.read_text(encoding="utf-8"))
    plan_payload = json.loads(key_plan_target.read_text(encoding="utf-8"))
    retrieval_payload = json.loads(key_retrieval_target.read_text(encoding="utf-8"))
    assert spec_payload["modules"][0]["blocks"][1]["block_id"] == "S002"
    assert plan_payload["subtasks"][0]["target"] == "<block: decl_state_and_keys>"
    assert retrieval_payload["schema_version"] == "block_spec_retrieval_v1"
    assert "MODULE_SKELETON_DOC v1" in backend.calls[9]["user_prompt"]
    assert "KEYEXP UNIQUE SPEC MARKER" in backend.calls[9]["user_prompt"]
    assert len(backend.calls) == 13


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
    assert '"spec_refs": [\n        "S001",\n        "S002"\n      ]' in backend.calls[1]["user_prompt"]
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
            make_structure_payload(md_path),
            make_interface_payload(md_path),
            make_timing_payload(md_path, image_paths[0]),
            make_control_payload(md_path, image_paths[0]),
            make_datapath_payload(md_path),
            make_planning_facts_payload(md_path),
            make_repo_skeleton_payload(),
            make_stage3_module_skeleton_doc("aes_key_expand_128", key_spec),
            make_stage3_module_skeleton_doc("aes_cipher_top", top_spec),
            make_block_spec_retrieval_payload("aes_key_expand_128"),
            key_plan,
            make_block_spec_retrieval_payload("aes_cipher_top", top_module=True),
            top_plan,
            *stage5_responses,
        ]
    )
    output_root = tmp_path / ".zerorepo" / "module_planner" / "outputs"
    runner = PlannerRunner(output_root=output_root, llm_backend=backend)

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
            make_structure_payload(md_path),
            make_interface_payload(md_path),
            make_timing_payload(md_path, image_paths[0]),
            make_control_payload(md_path, image_paths[0]),
            make_datapath_payload(md_path),
            make_planning_facts_payload(md_path),
            make_repo_skeleton_payload(),
            make_stage3_module_skeleton_doc("aes_key_expand_128", key_spec),
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
    runner = PlannerRunner(output_root=output_root, llm_backend=backend)

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
        index for index, call in enumerate(backend.calls) if call["system_prompt"] == "You are an RTL Merge Agent."
    ]
    assert len(stage6_call_indices) == 2
    first_merge_index = stage6_call_indices[0]
    assert "B5_comb_output_path" in backend.calls[first_merge_index - 1]["user_prompt"]
    assert "B1_decl_state_and_keys" in backend.calls[first_merge_index + 1]["user_prompt"]
    assert "STAGE5_SUBTASK_BEGIN B1_decl_state_and_keys" in backend.calls[first_merge_index]["user_prompt"]


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
    assert '"module_order": [' not in backend.calls[0]["user_prompt"]
    assert '"repository_structure"' in backend.calls[0]["user_prompt"]


def test_stage3_agent_builds_module_skeletons_incrementally(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    top_spec, key_spec = make_module_spec_files(tmp_path)
    top_spec.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    stage1_artifact = make_stage1_contract_artifact(md_path, image_paths)
    modules_artifact = build_module_organized_artifact(stage1_artifact)
    stage2_artifact = validate_model(Stage2RepoSkeletonArtifact, make_repo_skeleton_payload())
    backend = QueueBackend(
        [
            make_stage3_module_skeleton_doc("aes_cipher_top", top_spec),
            make_stage3_module_skeleton_doc("aes_key_expand_128", key_spec),
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
    assert len(persisted) == 3
    assert persisted[0]["manifest"]["completed_modules"] == ["aes_key_expand_128"]
    assert persisted[0]["doc_file"] == "module_skeleton_docs/aes_key_expand_128.md"
    assert persisted[0]["export_file"] == "module_skeleton_json/aes_key_expand_128.json"
    assert persisted[1]["manifest"]["completed_modules"] == ["aes_key_expand_128", "aes_cipher_top"]
    assert persisted[2]["manifest"]["stage3_status"] == "module_skeletons_planned"
    assert "KEYEXP UNIQUE SPEC MARKER" in backend.calls[0]["user_prompt"]
    assert "TOP UNIQUE SPEC MARKER" not in backend.calls[0]["user_prompt"]
    assert "TOP UNIQUE SPEC MARKER" in backend.calls[1]["user_prompt"]
    assert '"module": "aes_key_expand_128"' in backend.calls[0]["user_prompt"]
    assert '"module": "aes_cipher_top"' in backend.calls[1]["user_prompt"]
    assert "generation order:" in backend.calls[0]["user_prompt"]
    assert "MODULE_SKELETON_DOC v1" in backend.calls[0]["user_prompt"]
    assert "block_kind" in backend.calls[0]["user_prompt"]
    assert '"module_skeleton"' not in backend.calls[0]["user_prompt"]


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
            make_stage3_module_skeleton_doc("aes_key_expand_128", key_spec),
            make_stage3_module_skeleton_doc("aes_cipher_top", top_spec),
        ]
    )
    agent = Stage3Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run_incremental(task, {"modules": modules_artifact, "stage2": stage2_artifact})

    assert artifact.stage3_status == "module_skeletons_planned"
    assert [item.module for item in artifact.module_records] == ["aes_key_expand_128", "aes_cipher_top"]
    assert "KEYEXP UNIQUE SPEC MARKER" in backend.calls[0]["user_prompt"]
    assert "TOP UNIQUE SPEC MARKER" in backend.calls[1]["user_prompt"]


def test_stage3_agent_requires_standalone_module_spec_files(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    stage1_artifact = make_stage1_contract_artifact(md_path, image_paths)
    modules_artifact = build_module_organized_artifact(stage1_artifact)
    stage2_artifact = validate_model(Stage2RepoSkeletonArtifact, make_repo_skeleton_payload())
    backend = QueueBackend([make_stage3_module_skeleton_doc("aes_cipher_top", md_path)])
    agent = Stage3Agent(PlannerLLMClient(backend=backend))

    with pytest.raises(FileNotFoundError, match="aes_key_expand_128"):
        agent.run_incremental(
            task,
            {"modules": modules_artifact, "stage2": stage2_artifact},
        )


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
            make_stage3_module_skeleton_doc("aes_cipher_top", top_spec),
            make_stage3_module_skeleton_doc("aes_key_expand_128", key_spec),
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
    assert len(backend.calls) == 2


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
    backend = QueueBackend([make_stage3_module_skeleton_doc("aes_cipher_top", top_spec)])
    agent = Stage3Agent(PlannerLLMClient(backend=backend), output_root=output_root)

    artifact = agent.run_incremental(
        task,
        {"modules": modules_artifact, "stage2": stage2_artifact, "stage3": existing_manifest},
    )

    assert artifact.stage3_status == "module_skeletons_planned"
    assert artifact.completed_modules == ["aes_key_expand_128", "aes_cipher_top"]
    assert artifact.resume_cursor == 2
    assert len(backend.calls) == 1
    assert "TOP UNIQUE SPEC MARKER" in backend.calls[0]["user_prompt"]
    assert "KEYEXP UNIQUE SPEC MARKER" not in backend.calls[0]["user_prompt"]


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
