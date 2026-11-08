from __future__ import annotations

import importlib
import json
import re
from pathlib import Path
from rtl_artifact_test_utils import write_artifact_text
from zerorepo.rtl_impl.artifact_layout import ArtifactLayout, artifact_path, artifact_dir

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
from zerorepo.rtl_impl.module_planner.agents.base import BaseStageAgent, StageGenerationError, validate_model
from zerorepo.rtl_impl.module_planner.module_organizer import (
    build_module_organized_artifact,
    build_module_organized_artifact_from_repo_skeleton,
    build_module_organized_artifact_from_repo_skeleton_only,
    build_stage2_planning_input,
    build_stage2_planning_input_from_task,
)
from zerorepo.rtl_impl.module_planner.planner_runner import PlannerRunner
from zerorepo.rtl_impl.module_planner.prompts import stage1_ingest_extract, stage2_decomposition
from zerorepo.rtl_impl.module_planner.schemas import (
    CandidateDimensionScores,
    ExtractedFact,
    LockedTopModule,
    ModuleOrganizationArtifact,
    PlannerTaskInput,
    Stage1FactLedger,
    Stage2PlanningInput,
    Stage2DecompositionArtifact,
    Stage2CandidateEvaluation,
    Stage2DecompositionCandidate,
    ResponsibilityLedgerOutput,
    Stage2AdjudicationPass,
    Stage2SelectionPass,
    Stage2SelectionResult,
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
    ansi_module_ports,
    expand_markdown_inputs,
    extract_markdown_port_sections,
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

    write_artifact_text(md_path,
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
                "aes_cipher_top": "generate/rtl/aes_cipher_top.v",
                "aes_key_expand_128": "generate/rtl/aes_key_expand_128.v",
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
                "file_path": "generate/rtl/aes_key_expand_128.v",
                "role": "iterative round-key provider",
                "kind": "iterative_engine",
                "parents": ["aes_cipher_top"],
                "children": [],
                "instance_hints": [],
                "repo_notes": [],
            },
            {
                "module": "aes_cipher_top",
                "file_path": "generate/rtl/aes_cipher_top.v",
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


def make_stage2_responsibility_payload(spec_path=None) -> dict:
    payload = {
        "responsibilities": [
            {
                "responsibility_id": "RU_KEY_EXPANSION",
                "description": "Generate iterative AES round keys.",
                "ownership_required": True,
                "evidence_sections": ["AES Demo Repository > Key Expansion"],
                "inputs": ["cipher_key"],
                "outputs": ["round_key"],
                "owned_state": ["round_key_state"],
                "clock_domain": "clk",
                "reset_behavior": "rst active high",
                "protocol": "round_key_stream",
                "timing_class": "iterative_registered",
                "dependencies": [
                    {
                        "target_responsibility_id": "RU_TOP_CONTROL",
                        "coupling_strength": "medium",
                        "transferred_objects": ["round_key"],
                        "rationale": "Round control consumes generated keys.",
                    }
                ],
                "explicit_module_hint": "aes_key_expand_128",
                "iterative": True,
            },
            {
                "responsibility_id": "RU_TOP_CONTROL",
                "description": "Own top-level AES loading, round orchestration, and completion.",
                "ownership_required": True,
                "evidence_sections": ["AES Demo Repository > Timing"],
                "inputs": ["round_key", "ld"],
                "outputs": ["done"],
                "owned_state": ["round_counter"],
                "clock_domain": "clk",
                "reset_behavior": "rst active high",
                "protocol": "load_to_done",
                "timing_class": "registered_control",
                "dependencies": [],
                "explicit_module_hint": "aes_cipher_top",
            },
        ],
        "global_clocking_notes": ["All modules use clk and active-high rst."],
        "global_data_conventions": ["Round keys feed the top round datapath."],
    }

    if spec_path is not None:
        payload["state_objects"] = []
        for index, ru in enumerate(payload["responsibilities"]):
            ru["source_refs"] = [{"source_file": str(spec_path), "quote": spec_path.read_text()}]
            state = ru["owned_state"][0]
            ru["state_accesses"] = [{"state_id": state, "role": "commit"}]
            payload["state_objects"].append({"state_id": state, "name": state,
                "owner_responsibility_id": ru["responsibility_id"], "source_refs": ru["source_refs"]})
            for j, dependency in enumerate(ru["dependencies"]):
                dependency["dependency_id"] = f"DEP_{index}_{j}"
                dependency.update(dependency_kind="data", partition_constraint="interface_allowed", timing_relation="unspecified")
    return payload


def make_stage2_candidate_payload(style: str, *, complete: bool) -> dict:
    protocol = "round_key_stream" if complete else ""
    width_status = "derived" if complete else "unresolved"
    width_evidence = ["AES-128 round key is 128 bits"] if complete else []
    return {
        "candidate_id": f"stage2_{style}",
        "plan_style": style,
        "top_module": "aes_cipher_top",
        "summary": f"{style} AES decomposition with explicit key expansion.",
        "modules": [
            {
                "module": "aes_key_expand_128",
                "role": "iterative round-key provider",
                "responsibility_ids": ["RU_KEY_EXPANSION"],
                "source_kind": "explicit",
                "supporting_sections": ["AES Demo Repository > Key Expansion"],
                "rationale": "The source explicitly names the key expansion module.",
                "confidence": "high",
                "reused": False,
            },
            {
                "module": "aes_cipher_top",
                "role": "top-level AES encryption controller",
                "responsibility_ids": ["RU_TOP_CONTROL"],
                "source_kind": "explicit",
                "supporting_sections": ["AES Demo Repository > Interface"],
                "rationale": "The source explicitly identifies the top module.",
                "confidence": "high",
                "reused": False,
            },
        ],
        "hierarchy": [
            {
                "parent": "aes_cipher_top",
                "child": "aes_key_expand_128",
                "source_kind": "explicit",
                "rationale": "Explicit repository hierarchy.",
                "confidence": "high",
            }
        ],
        "boundary_contracts": [
            {
                "boundary_id": f"BC_KEY_TOP_{style.upper()}",
                "producer_module": "aes_key_expand_128",
                "consumer_module": "aes_cipher_top",
                "producer_responsibility_ids": ["RU_KEY_EXPANSION"],
                "consumer_responsibility_ids": ["RU_TOP_CONTROL"],
                "transferred_objects": ["round_key"],
                "direction": "producer_to_consumer",
                "protocol": protocol,
                "timing_class": "registered",
                "clock_domain": "clk",
                "reset_behavior": "rst active high",
                "width_status": width_status,
                "width_evidence": width_evidence,
                "evidence_sections": ["AES Demo Repository > Key Expansion"],
                "rationale": "Round key transfer from key expansion to top control.",
            }
        ],
        "global_clocking_notes": ["Shared clk and rst."],
        "global_data_conventions": ["Round keys are consumed by the top."],
        "open_issues": [],
    }


def make_stage2_decomposition_responses(spec_path) -> list[dict]:
    from zerorepo.rtl_impl.module_planner.utils.evidence import EvidenceRegistry
    inputs = build_stage2_planning_input_from_task(task_input=PlannerTaskInput(task_id="fixture", spec_md_files=[str(spec_path)]))
    registry = EvidenceRegistry(inputs)
    ledger = ResponsibilityLedgerOutput.model_validate(make_stage2_responsibility_payload(spec_path))
    from zerorepo.rtl_impl.module_planner.utils.responsibility_planning import ledger_errors
    assert not ledger_errors(ledger, inputs)
    draft = ledger.model_dump()
    for group in ("responsibilities", "state_objects"):
        for item in draft[group]:
            ids = {key for source in item["source_refs"] for key, ref in registry.entries.items()
                   if source["start_line"] <= ref.end_line and source["end_line"] >= ref.start_line}
            item["source_evidence_ids"] = sorted(ids)
            item["source_refs"] = registry.expand(sorted(ids))
    return [
        draft,
        make_stage2_candidate_payload("conservative", complete=False),
        make_stage2_candidate_payload("balanced", complete=True),
        make_stage2_candidate_payload("modular", complete=False),
    ]


def make_distinct_stage2_selection_candidates() -> list[Stage2DecompositionCandidate]:
    conservative_payload = make_stage2_candidate_payload("conservative", complete=True)
    conservative_payload["modules"] = [
        {
            "module": "aes_cipher_top",
            "role": "monolithic AES implementation",
            "responsibility_ids": ["RU_KEY_EXPANSION", "RU_TOP_CONTROL"],
            "source_kind": "explicit",
            "supporting_sections": ["AES Demo Repository"],
            "rationale": "Keep all responsibilities in the top.",
            "confidence": "medium",
            "reused": False,
        }
    ]
    conservative_payload["hierarchy"] = []
    conservative_payload["boundary_contracts"] = []

    balanced_payload = make_stage2_candidate_payload("balanced", complete=True)

    modular_payload = make_stage2_candidate_payload("modular", complete=True)
    modular_payload["modules"][0]["module"] = "aes_round_key_pipeline"
    modular_payload["hierarchy"][0]["child"] = "aes_round_key_pipeline"
    modular_payload["boundary_contracts"][0]["producer_module"] = "aes_round_key_pipeline"

    return [
        validate_model(Stage2DecompositionCandidate, payload)
        for payload in (conservative_payload, balanced_payload, modular_payload)
    ]


def make_stage2_selection_evaluations(
    candidates: list[Stage2DecompositionCandidate],
    *,
    fatal_by_id: dict[str, list[str]] | None = None,
    risks_by_id: dict[str, list[str]] | None = None,
) -> list[Stage2CandidateEvaluation]:
    fatal_by_id = fatal_by_id or {}
    risks_by_id = risks_by_id or {}
    return [
        Stage2CandidateEvaluation(
            candidate_id=item.candidate_id,
            plan_style=item.plan_style,
            fatal_violations=fatal_by_id.get(item.candidate_id, []),
            hard_violations=risks_by_id.get(item.candidate_id, []),
            metrics={
                "module_count": len(item.modules),
                "required_responsibility_count": 2,
                "stateful_responsibility_count": 2,
                "dependency_count": 1,
                "cross_module_dependency_count": len(item.boundary_contracts),
                "boundary_contract_count": len(item.boundary_contracts),
                "strong_coupling_cut_count": 0,
                "convenience_module_count": 0,
            },
        )
        for item in candidates
    ]


def make_stage2_ranking_response(
    ranked_candidate_ids: list[str],
) -> dict:
    return {
        "ranked_candidate_ids": ranked_candidate_ids,
        "winner_candidate_id": ranked_candidate_ids[0],
        "candidate_assessments": {
            candidate_id: [f"Assessment for {candidate_id}"]
            for candidate_id in ranked_candidate_ids
        },
        "rationale": ["Repository-level architecture judgment."],
    }


def make_module_spec_files(tmp_path: Path) -> tuple[Path, Path]:
    top_spec = tmp_path / "aes_cipher_top.md"
    key_spec = tmp_path / "aes_key_expand_128.md"
    write_artifact_text(top_spec,
        "\n".join(
            [
                "# aes_cipher_top",
                "TOP UNIQUE SPEC MARKER",
                "Controls AES round sequencing and completion behavior.",
                "",
                "## Interface",
                "Ports:",
                "- clk: input, width 1",
                "- rst: input, width 1",
                "- ld: input, width 1",
                "- done: output, width 1",
            ]
        ),
        encoding="utf-8",
    )
    write_artifact_text(key_spec,
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


def make_refined_skeleton_doc(module_name, spec_path, source_spec):
    text = make_stage3_module_skeleton_doc(module_name, spec_path).replace("# MODULE_SKELETON_DOC v1", "# MODULE_SKELETON_DOC v2", 1)
    ledger = make_stage2_responsibility_payload(source_spec)
    ru = ledger["responsibilities"][0 if module_name == "aes_key_expand_128" else 1]
    obligation = {"obligation_id": "OB_UPDATE", "parent_responsibility_id": ru["responsibility_id"],
        "behavior_kind": "state_update", "required_effect": ru["description"],
        "source_refs": ru["source_refs"], "state_accesses": ru["state_accesses"],
        "implementation_block_id": "B3", "supporting_block_ids": ["B1"]}
    return text.replace("## 4. Decision Ledger", "### Behavioral Obligations\n```json\n" + json.dumps([obligation]) + "\n```\n\n## 4. Decision Ledger")


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
    module_frame = (
        [f"module {module_name};"]
        if module_name == "sd_defines"
        else [
            f"module {module_name} (",
            "    input wire clk,",
            "    input wire rst,",
            "    input wire ld,",
            "    output wire done",
            ");",
        ]
    )
    return "\n".join(
        [
            "# MODULE_SKELETON_DOC v1",
            "",
            "## 0. Module Identity",
            f"- module_name: {module_name}",
            f"- file_path: generate/rtl/{module_name}.v",
            "- source_refs:",
            f"  - module_contract_ref: module_contracts_v1::{module_name}",
            f"  - repo_skeleton_ref: repo_skeleton_v1::{module_name}",
            f"  - spec_ref: {spec_path.name}",
            f"- planning_note: Build a pseudo-code-first skeleton for {module_name}.",
            "",
            "## 1. Module Frame",
            "```verilog",
            *module_frame,
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
    fragment = code or f"// generated fragment for {module_name} {subtask['id']}"
    return {
        "task_id": task_id,
        "module": module_name,
        "subtask_id": subtask["id"],
        "target": subtask["target"],
        "spec_refs": list(subtask["spec_refs"]),
        "code": fragment,
        "contract": {
            "writes": sorted(set(re.findall(r"\b([A-Za-z_]\w*)\s*(?:\[[^]]+\])?\s*(?:<=|(?<![=!<>])=(?![=]))", fragment))),
            "reads": [], "clocking": "unknown", "reset_behavior": "unknown",
            "hold_behavior": "unknown", "latency": "unknown", "assumptions": [],
        },
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
        *[
            _fact(
                md_path,
                module="aes_key_expand_128",
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

    assert artifact.completed_rounds == ["facts", "top_interface"]
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
    write_artifact_text(b_path, "# B\n", encoding="utf-8")
    write_artifact_text(a_path, "# A\n", encoding="utf-8")
    write_artifact_text(ignored, "ignore", encoding="utf-8")

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
    assert artifact.completed_rounds == ["facts", "top_interface"]
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
        write_artifact_text(md_path,
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
        {
            "interface_contract": {
                "module": "mod_1",
                "ports": [
                    {"name": "clk", "direction": "input", "width": "1", "role": "clock"}
                ],
                "text_grounding": [
                    {
                        "source_md_file": str(module_paths[0].resolve()),
                        "section_path": "mod_1",
                        "start_line_anchor": "Ports:",
                        "end_line_anchor": "- clk: input, width 1, role clock",
                    }
                ],
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
    assert len(backend.calls) == 3
    assert backend.calls[0]["user_prompt"].count("[Document DOC_") == 5
    assert backend.calls[1]["user_prompt"].count("[Document DOC_") == 1
    organized = build_module_organized_artifact(artifact)
    assert organized.module_order[:6] == [f"mod_{index}" for index in range(1, 7)]


def test_stage1_agent_facts_prompt_keeps_identity_without_full_derived_contracts(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    backend = QueueBackend([make_stage1_fact_payload(md_path)])
    agent = Stage1Agent(PlannerLLMClient(backend=backend))

    agent.run(task, {})

    assert len(backend.calls) == 1
    assert '"known_modules"' in backend.calls[0]["user_prompt"]
    assert '"spec_index"' in backend.calls[0]["user_prompt"]
    assert "Return JSON with exactly one key: `fact_ledger`" in backend.calls[0]["user_prompt"]
    assert '"interface_contracts":' not in backend.calls[0]["user_prompt"]


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
    write_artifact_text(md_path,
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
                            category="module_identity",
                            subject="aes_cipher_top",
                            predicate="is_top_module",
                            obj={"module": "aes_cipher_top"},
                        ),
                        _fact(
                            md_path,
                            module="aes_cipher_top",
                            category="interface",
                            subject="clk",
                            predicate="is_port",
                            obj={"name": "clk", "direction": "input", "width": "1"},
                        ),
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
                        _fact(
                            md_path,
                            module="aes_cipher_top",
                            category="module_identity",
                            subject="aes_cipher_top",
                            predicate="is_top_module",
                            obj={"module": "aes_cipher_top"},
                        ),
                        _fact(
                            md_path,
                            module="aes_cipher_top",
                            category="interface",
                            subject="clk",
                            predicate="is_port",
                            obj={"name": "clk", "direction": "input", "width": "1"},
                        ),
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
    assert artifact.completed_rounds == ["facts", "top_interface"]
    assert "image_contracts" not in artifact.model_dump()


def test_stage1_agent_rejects_missing_top_interface_after_retries(tmp_path):
    md_path = tmp_path / "empty.md"
    write_artifact_text(md_path, "# Blank Spec\n", encoding="utf-8")
    task = PlannerTaskInput(
        task_id="blank_demo",
        spec_md_files=[str(md_path)],
        spec_images=[],
        project_type="light_repo_spec2rtl",
        notes="blank test",
    )
    empty_facts = {
        "fact_ledger": {
            "source_files": [str(md_path.resolve())],
            "facts": [],
            "ambiguous_items": [],
        }
    }
    backend = QueueBackend([empty_facts, empty_facts, empty_facts])
    agent = Stage1Agent(PlannerLLMClient(backend=backend))
    agent.max_quality_attempts = 2

    with pytest.raises(StageGenerationError, match="top_module"):
        agent.run(task, {})

    assert len(backend.calls) == 3


def test_stage1_top_interface_retries_until_all_markdown_table_ports_are_exact(tmp_path):
    md_path = tmp_path / "table_top.md"
    write_artifact_text(md_path,
        "\n".join(
            [
                "# Table Top",
                "Top module: table_top",
                "",
                "## Clock Interface",
                "| Signal Name | Direction | Bit Width | Description |",
                "| --- | --- | --- | --- |",
                "| clk | Input | 1 | clock |",
                "| rst_n | Input | 1 | reset |",
                "",
                "## Data Interface",
                "| Port Name | Dir | Width | Description |",
                "| --- | --- | --- | --- |",
                "| data_i | Input | 8 | input data |",
                "| data_o | Output | [7:0] | output data |",
                "",
                "## Behavior",
                "BEHAVIOR TEXT MUST NOT ENTER THE TOP_INTERFACE PROMPT.",
            ]
        ),
        encoding="utf-8",
    )
    task = PlannerTaskInput(
        task_id="table_top_task",
        spec_md_files=[str(md_path)],
        spec_images=[],
        project_type="light_repo_spec2rtl",
    )
    facts = {
        "fact_ledger": {
            "source_files": [str(md_path.resolve())],
            "facts": [
                _fact(
                    md_path,
                    module="table_top",
                    category="module_identity",
                    subject="table_top",
                    predicate="is_top_module",
                    obj={"module": "table_top", "modules": ["table_top"]},
                ),
                _fact(
                    md_path,
                    module="table_top",
                    category="interface",
                    subject="clk",
                    predicate="is_port",
                    obj={"name": "clk", "direction": "input", "width": "1"},
                    source_kind="table_row",
                ),
            ],
            "ambiguous_items": [],
        }
    }

    def interface_payload(names):
        rows = {
            "clk": ("input", "1"),
            "rst_n": ("input", "1"),
            "data_i": ("input", "8"),
            "data_o": ("output", "8"),
        }
        return {
            "interface_contract": {
                "module": "table_top",
                "ports": [
                    {"name": name, "direction": rows[name][0], "width": rows[name][1]}
                    for name in names
                ],
                "text_grounding": [
                    {
                        "source_md_file": str(md_path.resolve()),
                        "section_path": "Table Top > Interfaces",
                        "start_line_anchor": "## Clock Interface",
                        "end_line_anchor": "| data_o | Output | [7:0] | output data |",
                    }
                ],
            }
        }

    backend = QueueBackend(
        [
            facts,
            interface_payload(["clk", "rst_n", "data_i"]),
            interface_payload(["clk", "rst_n", "data_i", "data_o"]),
        ]
    )
    agent = Stage1Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run(task, {})

    assert [port.name for port in artifact.interface_contracts[0].ports] == [
        "clk",
        "rst_n",
        "data_i",
        "data_o",
    ]
    assert len(backend.calls) == 3
    top_prompt = backend.calls[1]["user_prompt"]
    assert "## Clock Interface" in top_prompt
    assert "## Data Interface" in top_prompt
    assert "BEHAVIOR TEXT MUST NOT ENTER" not in top_prompt
    assert '"fact_ledger"' not in top_prompt
    assert "missing ports: ['data_o']" in backend.calls[2]["user_prompt"]


def test_markdown_port_table_parser_ignores_non_port_glossary():
    text = "\n".join(
        [
            "# Demo",
            "## Ports",
            "| Name | Direction | Width |",
            "| --- | --- | --- |",
            "| req_i | Input | 1 |",
            "",
            "## Configuration Glossary",
            "| Name | Meaning | Default |",
            "| --- | --- | --- |",
            "| Input | Direction selector | 0 |",
        ]
    )

    sections = extract_markdown_port_sections(text)

    assert len(sections) == 1
    assert [port.name for port in sections[0].ports] == ["req_i"]

def test_planner_runner_writes_contracts_json_and_resume_reuses_it(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    output_root = tmp_path / "outputs"
    backend = QueueBackend([make_stage1_fact_payload(md_path)])
    runner = PlannerRunner(output_root=output_root, llm_backend=backend, temporal_planning_enabled=False)

    first = runner.run(task, end_stage="stage1")
    second = runner.run(task, resume=True, end_stage="stage1")

    target = artifact_path(output_root, "contracts.json")
    modules_target = artifact_path(output_root, "modules.json")
    assert target.exists()
    assert not modules_target.exists()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["stage1_status"] == "contracts_completed"
    assert payload["completed_rounds"] == ["facts", "top_interface"]
    assert "image_contracts" not in payload
    assert "entity_alias_groups" not in payload
    assert payload["fact_ledger"]["source_files"] == [str(md_path.resolve())]
    assert payload["fact_ledger"]["facts"]
    assert payload["planning_facts"]
    assert first.completed_rounds == second.completed_rounds
    assert len(backend.calls) == 1


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
    write_artifact_text(artifact_path(output_root, "contracts.json"), json.dumps(partial_payload, indent=2), encoding="utf-8")

    backend = QueueBackend([make_stage1_fact_payload(md_path)])
    runner = PlannerRunner(output_root=output_root, llm_backend=backend, temporal_planning_enabled=False)

    artifact = runner.run(task, resume=True, end_stage="stage1")

    assert artifact.completed_rounds == ["facts", "top_interface"]
    assert artifact.fact_ledger.facts
    assert len(backend.calls) == 1


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
    write_artifact_text(artifact_path(output_root, "contracts.json"), json.dumps(legacy_payload, indent=2), encoding="utf-8")

    backend = QueueBackend([make_stage1_fact_payload(md_path)])
    runner = PlannerRunner(output_root=output_root, llm_backend=backend, temporal_planning_enabled=False)

    artifact = runner.run(task, resume=True, end_stage="stage1")

    assert artifact.timing_contracts
    assert artifact.completed_rounds == ["facts", "top_interface"]
    assert len(backend.calls) == 1


def test_planner_runner_writes_repo_skeleton_for_stage2(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    output_root = tmp_path / "outputs"
    backend = QueueBackend([make_stage1_fact_payload(md_path), *make_stage2_decomposition_responses(md_path)])
    runner = PlannerRunner(output_root=output_root, llm_backend=backend, temporal_planning_enabled=False)

    artifact = runner.run(task, end_stage="stage2")

    target = artifact_path(output_root, "repo_skeleton.json")
    assert isinstance(artifact, Stage2RepoSkeletonArtifact)
    assert target.exists()
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["stage2_status"] == "repo_skeleton_planned"
    assert payload["top_module"] == "aes_cipher_top"
    assert "module_order" not in payload
    assert payload["planning_decisions"]["generation_order"] == ["aes_key_expand_128", "aes_cipher_top"]
    assert len(backend.calls) == 5
    decomposition_path = artifact_path(output_root, "stage2_decomposition.json")
    assert decomposition_path.exists()
    decomposition = validate_model(
        Stage2DecompositionArtifact,
        json.loads(decomposition_path.read_text(encoding="utf-8")),
    )
    assert decomposition.selected_candidate_id == "stage2_balanced"
    assert (artifact_path(output_root, "contracts.json")).exists()


def test_planner_runner_resume_invalidates_repo_skeleton_without_interface_policy_fingerprint(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    output_root = tmp_path / "outputs"
    output_root.mkdir(parents=True, exist_ok=True)
    write_artifact_text(artifact_path(output_root, "repo_skeleton.json"),
        json.dumps(make_repo_skeleton_payload(), indent=2),
        encoding="utf-8",
    )
    backend = QueueBackend([make_stage1_fact_payload(md_path), *make_stage2_decomposition_responses(md_path)])
    runner = PlannerRunner(output_root=output_root, llm_backend=backend, temporal_planning_enabled=False)

    artifact = runner.run(task, resume=True, end_stage="stage2")

    assert isinstance(artifact, Stage2RepoSkeletonArtifact)
    assert artifact.stage2_status == "repo_skeleton_planned"
    assert artifact.input_fingerprint
    assert len(backend.calls) == 5


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
    write_artifact_text(artifact_path(output_root, "contracts.json"), json.dumps(partial_payload, indent=2), encoding="utf-8")

    backend = QueueBackend([make_stage1_fact_payload(md_path)])
    runner = PlannerRunner(output_root=output_root, llm_backend=backend, temporal_planning_enabled=False)

    artifact = runner.run(task, resume=True, end_stage="stage1")

    assert artifact.completed_rounds == ["facts", "top_interface"]
    assert artifact.planning_facts
    assert len(backend.calls) == 1


def test_planner_runner_writes_incremental_contract_statuses(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    output_root = tmp_path / "outputs"
    backend = QueueBackend([make_stage1_fact_payload(md_path)])
    runner = PlannerRunner(output_root=output_root, llm_backend=backend, temporal_planning_enabled=False)

    writes = []
    original_write_payload = runner._write_payload

    def recording_write(payload):
        writes.append(payload.get("stage1_status"))
        return original_write_payload(payload)

    runner._write_payload = recording_write
    runner.run(task, end_stage="stage1")

    assert writes == ["batch_0001_facts_completed", "batch_0001_completed", "contracts_completed"]


def test_planner_runner_supports_stage3_execution(tmp_path):
    from test_responsibility_refinement import scenario
    _, runner, backend, _, stage3, stage4 = scenario(tmp_path)
    assert stage3.schema_version == "stage3_skeleton_json_v3"
    assert stage4.schema_version == "module_plans_v3"
    for record in stage3.module_records:
        export = json.loads((runner.output_root / record.export_file).read_text())
        assert export["behavioral_obligations"] and export["structural_blocks"]
        assert (runner.output_root / record.doc_file).read_text().startswith("# MODULE_SKELETON_DOC v3")
    assert not backend.responses


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
    from test_responsibility_refinement import scenario
    _, runner, backend, _, stage3, stage4 = scenario(tmp_path)
    assert stage3.schema_version == "stage3_skeleton_json_v3"
    assert stage4.schema_version == "module_plans_v3"
    for record in stage3.module_records:
        export = json.loads((runner.output_root / record.export_file).read_text())
        assert export["behavioral_obligations"] and export["structural_blocks"]
        assert (runner.output_root / record.doc_file).read_text().startswith("# MODULE_SKELETON_DOC v3")
    assert not backend.responses


def test_stage4_spec_blocks_reuses_stage3_spec_context_sidecar(tmp_path):
    from test_responsibility_refinement import scenario
    _, runner, backend, _, _, _ = scenario(tmp_path)
    spec = json.loads(runner.layout.artifact("spec_blocks.json").read_text())
    assert spec["schema_version"] == "spec_blocks_v2"
    assert all(b["source_evidence_ids"] for m in spec["modules"] for b in m["blocks"])
    assert not any("[SOURCE_CHUNKS]" in call["user_prompt"] for call in backend.calls)
    for module in spec["modules"]:
        refs = json.loads(runner.layout.module(4, module["module"], "spec_refs.json").read_text())
        assert not refs["fallback_used"]


def test_stage4_spec_blocks_falls_back_for_legacy_stage3_without_sidecar(tmp_path):
    from test_responsibility_refinement import scenario
    _, runner, backend, _, _, _ = scenario(tmp_path)
    spec = json.loads(runner.layout.artifact("spec_blocks.json").read_text())
    assert spec["schema_version"] == "spec_blocks_v2"
    assert all(b["source_evidence_ids"] for m in spec["modules"] for b in m["blocks"])
    assert not any("[SOURCE_CHUNKS]" in call["user_prompt"] for call in backend.calls)
    for module in spec["modules"]:
        refs = json.loads(runner.layout.module(4, module["module"], "spec_refs.json").read_text())
        assert not refs["fallback_used"]


def test_stage4_module_plan_requires_interface_refs_for_first_decl_block(tmp_path):
    from test_responsibility_refinement import scenario
    _, runner, _, _, _, stage4 = scenario(tmp_path)
    specs = json.loads(runner.layout.artifact("spec_blocks.json").read_text())
    for record, spec in zip(stage4.module_plan_files, specs["modules"]):
        plan = json.loads((runner.output_root / record.plan_file).read_text())
        required = {b["block_id"] for b in spec["blocks"] if b["declaration_support"]}
        assert required <= set(plan["subtasks"][0]["spec_refs"])
        assert all(t["constraints"] == [] for t in plan["subtasks"])


def test_stage5_agent_uses_spec_blocks_module_order_and_selected_refs(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    output_root = tmp_path / "case"
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
    write_artifact_text(ArtifactLayout(output_root).module(4, Path("mod_a.json").stem, "plan.json"), json.dumps(mod_a_plan), encoding="utf-8")
    write_artifact_text(ArtifactLayout(output_root).module(4, Path("mod_b.json").stem, "plan.json"), json.dumps(mod_b_plan), encoding="utf-8")
    stage4 = {
        "schema_version": "module_plans_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a", "mod_b"],
        "module_plan_files": [
            {"module": "mod_a", "plan_file": "plan/stage4/modules/mod_a/plan.json"},
            {"module": "mod_b", "plan_file": "plan/stage4/modules/mod_b/plan.json"},
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
    workspace_root = tmp_path / "case"
    assert artifact.module_files[0].workspace_file.endswith("generate/fragments/mod_b_fragments.v")
    assert (artifact_dir(workspace_root, "fragments") / "mod_b_fragments.v").read_text(encoding="utf-8").find("assign b") >= 0
    assert (artifact_dir(workspace_root, "fragments") / "mod_a_fragments.v").read_text(encoding="utf-8").find("assign a") >= 0


def test_stage5_agent_repairs_markdown_fenced_code(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    output_root = tmp_path / "case"
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
    write_artifact_text(ArtifactLayout(output_root).module(4, Path("mod_a.json").stem, "plan.json"), json.dumps(plan), encoding="utf-8")
    stage4 = {
        "schema_version": "module_plans_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "module_plan_files": [{"module": "mod_a", "plan_file": "plan/stage4/modules/mod_a/plan.json"}],
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
    fragment_file = artifact_dir(tmp_path / "case", "fragments") / "mod_a_fragments.v"
    assert "assign a = 1'b1;" in fragment_file.read_text(encoding="utf-8")


def test_stage5_prompt_includes_module_interface_blocks_when_subtask_refs_omit_them(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    output_root = tmp_path / "case"
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
    write_artifact_text(ArtifactLayout(output_root).module(4, Path("mod_a.json").stem, "plan.json"), json.dumps(plan), encoding="utf-8")
    stage4 = {
        "schema_version": "module_plans_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "module_plan_files": [{"module": "mod_a", "plan_file": "plan/stage4/modules/mod_a/plan.json"}],
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
    output_root = tmp_path / "case"
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
    write_artifact_text(ArtifactLayout(output_root).module(4, Path("mod_a.json").stem, "plan.json"), json.dumps(plan), encoding="utf-8")
    stage4 = {
        "schema_version": "module_plans_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "module_plan_files": [{"module": "mod_a", "plan_file": "plan/stage4/modules/mod_a/plan.json"}],
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
    assert "[STAGE_CONTEXT]\nNone" in prompt
    assert "module_interface_spec_refs" not in prompt


def test_stage5_prompt_includes_global_defines_when_available(tmp_path, monkeypatch):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    official = tmp_path / "RealBench" / "sdc" / "sd_defines" / "sd_defines.v"
    official.parent.mkdir(parents=True)
    write_artifact_text(official, "`define BIT_BLOCK 1044\n`define SD_BUS_W 4\n", encoding="utf-8")
    monkeypatch.setattr(global_defines_mod, "find_official_define_file", lambda _task, _module: official)

    output_root = tmp_path / "case"
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
    write_artifact_text(ArtifactLayout(output_root).module(4, Path("mod_a.json").stem, "plan.json"), json.dumps(plan), encoding="utf-8")
    stage4 = {
        "schema_version": "module_plans_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "module_plan_files": [{"module": "mod_a", "plan_file": "plan/stage4/modules/mod_a/plan.json"}],
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

    class CompactPlanningRetriever:
        kg_service = type("KgService", (), {"mode": "required"})()

        def __init__(self):
            self.spec_refs = None

        def get_module_context(self, *_args, **_kwargs):
            return {"full_artifact": "FULL_KG_CONTEXT_MUST_NOT_BE_SERIALIZED"}

        def to_stage5_prompt_json(self, _context, spec_refs, max_chars=12000):
            self.spec_refs = list(spec_refs)
            assert max_chars == 12000
            return '{"marker":"COMPACT_STAGE5_KG"}'

    planning_retriever = CompactPlanningRetriever()
    agent = Stage5Agent(
        PlannerLLMClient(backend=backend),
        output_root=output_root,
        planning_context_retriever=planning_retriever,
    )

    agent.run_incremental(task, {"stage4": stage4, "spec_blocks": spec_blocks, "repo_skeleton": repo_skeleton})

    prompt = backend.calls[0]["user_prompt"]
    workspace_root = tmp_path / "case"
    assert "[GLOBAL_DEFINES_CONTEXT]" in prompt
    assert "`define BIT_BLOCK 1044" in prompt
    assert "`define SD_BUS_W 4" in prompt
    assert "COMPACT_STAGE5_KG" in prompt
    assert "FULL_KG_CONTEXT_MUST_NOT_BE_SERIALIZED" not in prompt
    assert planning_retriever.spec_refs == ["S001"]
    assert "planning_kg_context_chars" not in prompt
    assert "global_define_files" not in prompt
    assert (artifact_path(workspace_root, "global_defines_manifest.json")).exists()
    assert not (artifact_path(workspace_root / "merged", "global_defines_manifest.json")).exists()


def test_stage5_prompt_includes_current_module_skeleton_context(tmp_path):
    from test_responsibility_refinement import scenario
    _, runner, backend, _, stage3, _ = scenario(tmp_path, end_stage="stage5")
    prompts = [c["user_prompt"] for c in backend.calls if "[CURRENT_SUBTASK]" in c["user_prompt"]]
    assert prompts and any('"task_contract"' in p and '"OB_COMMIT"' in p for p in prompts)
    for record in stage3.module_records:
        frame, path = runner.stage5._read_module_skeleton_context(record)
        assert path.endswith("skeleton.json") and frame.startswith("module ")


def test_stage5_agent_run_module_writes_single_fragment_file(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    output_root = tmp_path / "case"
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
    write_artifact_text(ArtifactLayout(output_root).module(4, Path("mod_a.json").stem, "plan.json"), json.dumps(plan), encoding="utf-8")
    stage4 = {
        "schema_version": "module_plans_v1",
        "task_id": task.task_id,
        "module_order": ["mod_a"],
        "module_plan_files": [{"module": "mod_a", "plan_file": "plan/stage4/modules/mod_a/plan.json"}],
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
    assert record.workspace_file.endswith("generate/fragments/mod_a_fragments.v")
    fragment_text = Path(record.workspace_file).read_text(encoding="utf-8")
    assert "// STAGE5_SUBTASK_BEGIN B1_logic" in fragment_text
    assert "assign y = a;" in fragment_text


def test_stage6_merge_agent_writes_raw_merged_module_and_prompt_context(tmp_path):
    from test_responsibility_refinement import scenario
    _, runner, _, _, stage3, _ = scenario(tmp_path, end_stage="stage6")
    for record in stage3.module_records:
        assert (runner.layout.rtl / f"{record.module}.v").is_file()


def test_stage6_merge_agent_rejects_wrong_module_without_overwriting_merged(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    output_root = tmp_path / "case"
    fragment_dir = artifact_dir(tmp_path / "case", "fragments")
    fragment_dir.mkdir(parents=True)
    fragment_file = fragment_dir / "mod_a_fragments.v"
    write_artifact_text(fragment_file, "assign y = a;\n", encoding="utf-8")
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
    existing = artifact_dir(agent.workspace_root, "merged") / "mod_a.v"
    existing.parent.mkdir(parents=True, exist_ok=True)
    original = "module mod_a(input a, output y); assign y = a; endmodule\n"
    write_artifact_text(existing, original, encoding="utf-8")

    with pytest.raises(ValueError, match="must declare target module mod_a"):
        agent.run_module(
            task,
            {"spec_blocks": spec_blocks},
            "mod_a",
            {"module": "mod_a", "workspace_file": str(fragment_file), "completed_subtasks": ["B1_logic"]},
        )

    assert len(backend.calls) == 2
    assert existing.read_text(encoding="utf-8") == original
    assert not (output_root / "stage6_syntax_repair" / "mod_a.json").exists()


def test_planner_runner_supports_stage5_subtask_codegen_workspace(tmp_path):
    from test_responsibility_refinement import scenario
    _, runner, _, _, _, _ = scenario(tmp_path, end_stage="stage5")
    artifact = json.loads(runner.layout.artifact("stage5_codegen.json").read_text())
    assert artifact["status"] == "completed"
    assert all(runner.stage5._workspace_file(module).is_file() for module in artifact["module_order"])


def test_planner_runner_supports_stage6_per_module_merge(tmp_path):
    from test_responsibility_refinement import scenario
    _, runner, _, _, stage3, _ = scenario(tmp_path, end_stage="stage6")
    for record in stage3.module_records:
        assert (runner.layout.rtl / f"{record.module}.v").is_file()


def test_stage2_agent_builds_repo_skeleton_from_modules_artifact(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    stage1_artifact = make_stage1_contract_artifact(md_path, image_paths)
    modules_artifact = build_module_organized_artifact(stage1_artifact)
    stage2_input = build_stage2_planning_input(
        stage1_artifact=stage1_artifact,
        task_input=task,
        compat_modules=modules_artifact,
    )
    backend = QueueBackend(make_stage2_decomposition_responses(md_path))
    agent = Stage2Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run(task, {"modules": modules_artifact, "stage2_input": stage2_input})

    assert isinstance(artifact, Stage2RepoSkeletonArtifact)
    assert artifact.stage2_status == "repo_skeleton_planned"
    assert artifact.top_module == "aes_cipher_top"
    assert artifact.planning_decisions.generation_order == ["aes_key_expand_128", "aes_cipher_top"]
    responsibility_prompt = backend.calls[0]["user_prompt"]
    assert '"schema_version":"stage2_prompt_context_v1"' in responsibility_prompt
    assert len(backend.calls) == 4
    assert agent._last_decomposition.selected_candidate_id == "stage2_balanced"
    assert '"legacy_contract_projection"' not in responsibility_prompt
    assert '"interface_contracts"' not in responsibility_prompt
    assert '"timing_contracts"' not in responsibility_prompt
    assert '"control_contracts"' not in responsibility_prompt
    assert '"datapath_contracts"' not in responsibility_prompt
    assert '"fact_ledger"' not in responsibility_prompt

    source_markdown = md_path.read_text(encoding="utf-8")
    assert '"evidence_catalog":' in responsibility_prompt
    assert '"source_evidence_ids"' in responsibility_prompt
    assert "Input sampling: ld is sampled on the rising clock edge." in responsibility_prompt
    for candidate_call in backend.calls[1:4]:
        candidate_prompt = candidate_call["user_prompt"]
        assert source_markdown not in candidate_prompt
        assert '"markdown"' not in candidate_prompt
        assert '"path":' in candidate_prompt
        assert f'"stem":"{md_path.stem}"' in candidate_prompt
        assert '"architecture_facts":' in candidate_prompt
        assert '"explicit_hierarchy":' in candidate_prompt
        assert '"module":"aes_cipher_top"' in candidate_prompt
        for responsibility_id in ("RU_KEY_EXPANSION", "RU_TOP_CONTROL"):
            assert responsibility_id in candidate_prompt


def test_stage2_candidate_prompt_length_is_independent_of_source_markdown():
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([])))
    ledger = validate_model(ResponsibilityLedgerOutput, make_stage2_responsibility_payload())
    locked_top = LockedTopModule(
        module="aes_cipher_top",
        resolution_mode="deterministic",
        evidence_sections=["AES Demo Repository"],
    )
    base_context = {
        "schema_version": "stage2_prompt_context_v1",
        "task_id": "candidate-size-test",
        "primary_source_spec": {
            "path": "/specs/aes_cipher_top.md",
            "stem": "aes_cipher_top",
            "markdown": "SHORT_SOURCE_MARKER",
        },
        "supplemental_source_specs": [],
        "top_module_hint": "aes_cipher_top",
        "known_module_candidates": ["aes_cipher_top", "aes_key_expand_128"],
        "architecture_facts": [{"fact_id": "F_TOP", "predicate": "is_top_module"}],
        "architecture_facts_omitted_count": 0,
        "explicit_hierarchy": [{"parent": "aes_cipher_top", "child": "aes_key_expand_128"}],
    }

    def candidate_prompt(markdown: str) -> str:
        context = json.loads(json.dumps(base_context))
        context["primary_source_spec"]["markdown"] = markdown
        compact_context = agent._build_candidate_prompt_context(context)
        return stage2_decomposition.build_candidate_prompt(
            plan_style="balanced",
            prompt_context_json=agent._to_compact_json(compact_context),
            locked_top_json=agent._to_compact_json(locked_top),
            responsibility_ledger_json=agent._to_compact_json(ledger),
        )

    short_prompt = candidate_prompt("SHORT_SOURCE_MARKER")
    long_prompt = candidate_prompt("LONG_SOURCE_MARKER" * 10_000)

    assert len(short_prompt) == len(long_prompt)
    assert "SHORT_SOURCE_MARKER" not in short_prompt
    assert "LONG_SOURCE_MARKER" not in long_prompt
    assert '"path":"/specs/aes_cipher_top.md"' in short_prompt
    assert '"stem":"aes_cipher_top"' in short_prompt
    assert '"architecture_facts":' in short_prompt
    assert '"explicit_hierarchy":' in short_prompt


def test_stage2_llm_selection_policy_invalidates_v2_cache():
    assert "responsibility_refinement" in PlannerRunner.PIPELINE_POLICY_VERSION


def test_stage2_evaluator_marks_missing_cross_module_boundary_as_fatal(tmp_path):
    task, md_path, _ = make_task_input(tmp_path, image_count=0)
    stage1 = make_stage1_contract_artifact(md_path, [])
    stage2_input = build_stage2_planning_input(stage1_artifact=stage1, task_input=task)
    ledger = validate_model(ResponsibilityLedgerOutput, make_stage2_responsibility_payload())
    candidate_payload = make_stage2_candidate_payload("balanced", complete=True)
    candidate_payload["boundary_contracts"] = []
    candidate = validate_model(Stage2DecompositionCandidate, candidate_payload)
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([])))

    evaluation = agent._evaluate_candidate(
        candidate=candidate,
        locked_top=LockedTopModule(
            module="aes_cipher_top",
            resolution_mode="deterministic",
            evidence_sections=["AES Demo Repository"],
        ),
        responsibilities=ledger.responsibilities,
        stage2_input=stage2_input,
    )

    assert any("missing boundary contract" in item for item in evaluation.fatal_violations)


def test_stage2_single_module_skeleton_allows_internal_dependency_facts(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    ledger = validate_model(ResponsibilityLedgerOutput, make_stage2_responsibility_payload())
    candidate = make_distinct_stage2_selection_candidates()[0]
    stage2_input = Stage2PlanningInput.model_validate(
        {
            "task_id": task.task_id,
            "fact_ledger": {
                "facts": [
                    {
                        "fact_id": "F_TOP",
                        "module": "aes_cipher_top",
                        "category": "module_identity",
                        "subject": "aes_cipher_top",
                        "predicate": "is_top_module",
                        "object": {"module": "aes_cipher_top"},
                    },
                    {
                        "fact_id": "F_DEP",
                        "module": "aes_cipher_top",
                        "category": "data_dependency",
                        "subject": "round_key",
                        "predicate": "feeds",
                        "object": {"producer": "key expansion", "consumer": "top control"},
                    },
                ]
            },
        }
    )
    evaluation = make_stage2_selection_evaluations([candidate])[0]
    selection_result = Stage2SelectionResult(
        eligible_candidate_ids=[candidate.candidate_id],
        final_winner_candidate_id=candidate.candidate_id,
        final_reason="Only fatal-free architecture.",
    )
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([])))
    artifact = agent._candidate_to_repo_skeleton(
        task=task,
        stage2_input=stage2_input,
        locked_top=LockedTopModule(
            module="aes_cipher_top",
            resolution_mode="deterministic",
            evidence_fact_ids=["F_TOP"],
            evidence_sections=["AES Demo Repository"],
        ),
        responsibilities=ledger.responsibilities,
        candidate=candidate,
        evaluation=evaluation,
        selection_result=selection_result,
        degraded=False,
    )

    errors = agent.validate_quality(
        artifact,
        task,
        {"stage2_input": stage2_input},
    )

    assert artifact.global_invariants.hierarchy == []
    assert errors == []


def test_stage2_top_resolver_requires_grounded_unique_result(tmp_path):
    task, md_path, _ = make_task_input(tmp_path, image_count=0)
    stage2_input = build_stage2_planning_input_from_task(task_input=task)
    prompt_context = Stage2Agent(
        PlannerLLMClient(backend=QueueBackend([]))
    )._build_stage2_prompt_context(stage2_input)
    response = {
        "module": "aes_cipher_top",
        "evidence_fact_ids": [],
        "evidence_sections": ["AES Demo Repository > Interface"],
        "rationale": "The external port contract belongs to aes_cipher_top.",
    }
    backend = QueueBackend([response])
    agent = Stage2Agent(PlannerLLMClient(backend=backend))

    locked = agent._resolve_top_with_llm(
        task=task,
        partial_artifacts={"stage2_input": stage2_input},
        prompt_context=prompt_context,
        top_evidence={
            "aes_cipher_top": {"fact_ids": [], "sections": ["Interface"]},
            "aes_key_expand_128": {"fact_ids": [], "sections": ["Submodules"]},
        },
    )

    assert locked.module == "aes_cipher_top"
    assert locked.resolution_mode == "llm_resolved"
    assert len(backend.calls) == 1


def test_stage2_top_resolver_rejects_ungrounded_result(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    stage2_input = build_stage2_planning_input_from_task(task_input=task)
    prompt_context = Stage2Agent(
        PlannerLLMClient(backend=QueueBackend([]))
    )._build_stage2_prompt_context(stage2_input)
    invalid = {
        "module": "invented_top",
        "evidence_fact_ids": [],
        "evidence_sections": ["Invented Section"],
        "rationale": "Unsupported guess.",
    }
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([invalid] * 5)))

    with pytest.raises(StageGenerationError, match="quality checks"):
        agent._resolve_top_with_llm(
            task=task,
            partial_artifacts={"stage2_input": stage2_input},
            prompt_context=prompt_context,
            top_evidence={},
        )


def test_stage2_pairwise_requires_order_swapped_agreement(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    ledger = validate_model(ResponsibilityLedgerOutput, make_stage2_responsibility_payload())
    first = validate_model(
        Stage2DecompositionCandidate,
        make_stage2_candidate_payload("conservative", complete=True),
    )
    second_payload = make_stage2_candidate_payload("balanced", complete=True)
    second_payload["modules"][0]["module"] = "aes_round_key_engine"
    second_payload["hierarchy"][0]["child"] = "aes_round_key_engine"
    second_payload["boundary_contracts"][0]["producer_module"] = "aes_round_key_engine"
    second = validate_model(Stage2DecompositionCandidate, second_payload)
    dimensions = CandidateDimensionScores(
        responsibility_evidence_coverage=1.0,
        coupling_preservation=0.8,
        interface_completeness_naturalness=1.0,
        codegen_feasibility=1.0,
        granularity_economy=1.0,
    )
    evaluations = [
        Stage2CandidateEvaluation(
            candidate_id=item.candidate_id,
            plan_style=item.plan_style,
            dimension_scores=dimensions,
            total_score=0.96,
        )
        for item in (first, second)
    ]
    backend = QueueBackend(
        [
            {"winner_candidate_id": first.candidate_id, "rationale": ["first pass"]},
            {"winner_candidate_id": second.candidate_id, "rationale": ["second pass"]},
        ]
    )
    agent = Stage2Agent(PlannerLLMClient(backend=backend))

    result = agent._run_pairwise_tiebreak(
        task=task,
        partial_artifacts={},
        responsibilities=ledger.responsibilities,
        first=first,
        second=second,
        evaluations=evaluations,
        score_delta=0.0,
    )

    assert result.unstable_judgment is True
    assert result.applied is False
    assert [item.presentation_order for item in (result.first_pass, result.second_pass)] == [
        [first.candidate_id, second.candidate_id],
        [second.candidate_id, first.candidate_id],
    ]


def test_stage2_llm_selection_ranks_all_fatal_free_candidates_in_reverse_orders(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    ledger = validate_model(ResponsibilityLedgerOutput, make_stage2_responsibility_payload())
    candidates = make_distinct_stage2_selection_candidates()
    candidate_ids = [item.candidate_id for item in candidates]
    evaluations = make_stage2_selection_evaluations(
        candidates,
        risks_by_id={
            "stage2_balanced": ["risk"] * 5,
            "stage2_modular": ["risk"],
        },
    )
    ranked = ["stage2_balanced", "stage2_modular", "stage2_conservative"]
    backend = QueueBackend(
        [make_stage2_ranking_response(ranked), make_stage2_ranking_response(ranked)]
    )
    agent = Stage2Agent(PlannerLLMClient(backend=backend))

    selected, result, trace, degraded = agent._select_candidate(
        task=task,
        partial_artifacts={},
        responsibilities=ledger.responsibilities,
        candidates=candidates,
        evaluations=evaluations,
    )

    assert selected.candidate_id == "stage2_balanced"
    assert result.first_pass.presentation_order == candidate_ids
    assert result.second_pass.presentation_order == list(reversed(candidate_ids))
    assert result.fallback_used is False
    assert degraded is True
    assert len(backend.calls) == 2
    assert all("risk_findings" in call["user_prompt"] for call in backend.calls)
    assert all("total_score" not in call["user_prompt"] for call in backend.calls)
    assert all("total_score" not in item.model_dump() for item in evaluations)
    assert all("dimension_scores" not in item.model_dump() for item in evaluations)
    assert any("risk findings were retained as advisory" in item for item in trace)


def test_stage2_llm_selection_uses_third_adjudication_for_conflicting_winners(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    ledger = validate_model(ResponsibilityLedgerOutput, make_stage2_responsibility_payload())
    candidates = make_distinct_stage2_selection_candidates()
    evaluations = make_stage2_selection_evaluations(candidates)
    first_rank = ["stage2_balanced", "stage2_conservative", "stage2_modular"]
    second_rank = ["stage2_modular", "stage2_balanced", "stage2_conservative"]
    backend = QueueBackend(
        [
            make_stage2_ranking_response(first_rank),
            make_stage2_ranking_response(second_rank),
            {
                "winner_candidate_id": "stage2_modular",
                "rationale": ["The modular boundaries are better justified."],
            },
        ]
    )
    agent = Stage2Agent(PlannerLLMClient(backend=backend))

    selected, result, _, degraded = agent._select_candidate(
        task=task,
        partial_artifacts={},
        responsibilities=ledger.responsibilities,
        candidates=candidates,
        evaluations=evaluations,
    )

    assert selected.candidate_id == "stage2_modular"
    assert result.adjudication.winner_candidate_id == "stage2_modular"
    assert result.fallback_used is False
    assert degraded is False
    assert len(backend.calls) == 3


def test_stage2_llm_selection_uses_successful_pass_when_other_pass_fails(tmp_path, monkeypatch):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    ledger = validate_model(ResponsibilityLedgerOutput, make_stage2_responsibility_payload())
    candidates = make_distinct_stage2_selection_candidates()
    evaluations = make_stage2_selection_evaluations(candidates)
    passes = iter(
        [
            Stage2SelectionPass(
                presentation_order=[item.candidate_id for item in candidates],
                error="first ranking unavailable",
            ),
            Stage2SelectionPass(
                presentation_order=[item.candidate_id for item in reversed(candidates)],
                ranked_candidate_ids=[
                    "stage2_modular",
                    "stage2_balanced",
                    "stage2_conservative",
                ],
                winner_candidate_id="stage2_modular",
            ),
        ]
    )
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([])))
    monkeypatch.setattr(agent, "_run_selection_pass_safe", lambda **_: next(passes))

    selected, result, _, degraded = agent._select_candidate(
        task=task,
        partial_artifacts={},
        responsibilities=ledger.responsibilities,
        candidates=candidates,
        evaluations=evaluations,
    )

    assert selected.candidate_id == "stage2_modular"
    assert result.fallback_used is True
    assert "successful ranking" in result.fallback_reason
    assert degraded is True


def test_stage2_llm_selection_aggregates_ranks_when_adjudication_fails(tmp_path, monkeypatch):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    ledger = validate_model(ResponsibilityLedgerOutput, make_stage2_responsibility_payload())
    candidates = make_distinct_stage2_selection_candidates()
    evaluations = make_stage2_selection_evaluations(candidates)
    passes = iter(
        [
            Stage2SelectionPass(
                presentation_order=[item.candidate_id for item in candidates],
                ranked_candidate_ids=[
                    "stage2_balanced",
                    "stage2_conservative",
                    "stage2_modular",
                ],
                winner_candidate_id="stage2_balanced",
            ),
            Stage2SelectionPass(
                presentation_order=[item.candidate_id for item in reversed(candidates)],
                ranked_candidate_ids=[
                    "stage2_modular",
                    "stage2_balanced",
                    "stage2_conservative",
                ],
                winner_candidate_id="stage2_modular",
            ),
        ]
    )
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([])))
    monkeypatch.setattr(agent, "_run_selection_pass_safe", lambda **_: next(passes))
    monkeypatch.setattr(
        agent,
        "_run_adjudication_safe",
        lambda **_: Stage2AdjudicationPass(
            candidate_ids=["stage2_balanced", "stage2_modular"],
            error="adjudicator unavailable",
        ),
    )

    selected, result, _, degraded = agent._select_candidate(
        task=task,
        partial_artifacts={},
        responsibilities=ledger.responsibilities,
        candidates=candidates,
        evaluations=evaluations,
    )

    assert selected.candidate_id == "stage2_balanced"
    assert result.fallback_used is True
    assert "lower aggregate rank" in result.fallback_reason
    assert degraded is True


def test_stage2_llm_selection_style_fallback_when_both_rankings_fail(tmp_path, monkeypatch):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    ledger = validate_model(ResponsibilityLedgerOutput, make_stage2_responsibility_payload())
    candidates = make_distinct_stage2_selection_candidates()
    evaluations = make_stage2_selection_evaluations(candidates)
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([])))
    monkeypatch.setattr(
        agent,
        "_run_selection_pass_safe",
        lambda **kwargs: Stage2SelectionPass(
            presentation_order=kwargs["presentation_order"],
            error="ranking unavailable",
        ),
    )

    selected, result, _, degraded = agent._select_candidate(
        task=task,
        partial_artifacts={},
        responsibilities=ledger.responsibilities,
        candidates=candidates,
        evaluations=evaluations,
    )

    assert selected.candidate_id == "stage2_balanced"
    assert result.fallback_used is True
    assert "balanced, then modular, then conservative" in result.fallback_reason
    assert degraded is True


def test_stage2_selection_fallback_and_risks_are_audited_in_final_artifacts(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    ledger = validate_model(ResponsibilityLedgerOutput, make_stage2_responsibility_payload())
    candidate = make_distinct_stage2_selection_candidates()[1]
    evaluation = make_stage2_selection_evaluations(
        [candidate],
        risks_by_id={candidate.candidate_id: ["strong coupling risk"]},
    )[0]
    selection_result = Stage2SelectionResult(
        eligible_candidate_ids=[candidate.candidate_id],
        fallback_used=True,
        fallback_reason="Both architecture rankings were unavailable.",
        final_winner_candidate_id=candidate.candidate_id,
        final_reason="Operational fallback.",
    )
    stage2_input = Stage2PlanningInput.model_validate(
        {"task_id": task.task_id, "fact_ledger": {"facts": []}}
    )
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([])))
    artifact = agent._candidate_to_repo_skeleton(
        task=task,
        stage2_input=stage2_input,
        locked_top=LockedTopModule(
            module="aes_cipher_top",
            resolution_mode="deterministic",
            evidence_sections=["AES Demo Repository"],
        ),
        responsibilities=ledger.responsibilities,
        candidate=candidate,
        evaluation=evaluation,
        selection_result=selection_result,
        degraded=True,
    )
    decomposition = Stage2DecompositionArtifact(
        task_id=task.task_id,
        status="selected_with_degradation",
        locked_top=LockedTopModule(
            module="aes_cipher_top",
            resolution_mode="deterministic",
            evidence_sections=["AES Demo Repository"],
        ),
        candidates=[candidate],
        evaluations=[evaluation],
        selected_candidate_id=candidate.candidate_id,
        selection_result=selection_result,
    )

    assert any("strong coupling risk" in item for item in artifact.open_issues)
    assert any("architecture-judge fallback" in item for item in artifact.open_issues)
    assert decomposition.model_dump()["selection_result"]["fallback_used"] is True


def test_stage2_llm_selection_skips_judge_for_single_or_identical_architecture(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    ledger = validate_model(ResponsibilityLedgerOutput, make_stage2_responsibility_payload())
    candidates = [
        validate_model(
            Stage2DecompositionCandidate,
            make_stage2_candidate_payload(style, complete=True),
        )
        for style in ("conservative", "balanced", "modular")
    ]
    evaluations = make_stage2_selection_evaluations(candidates)
    backend = QueueBackend([])
    agent = Stage2Agent(PlannerLLMClient(backend=backend))

    identical_selected, identical_result, _, _ = agent._select_candidate(
        task=task,
        partial_artifacts={},
        responsibilities=ledger.responsibilities,
        candidates=candidates,
        evaluations=evaluations,
    )
    fatal_by_id = {
        "stage2_balanced": ["fatal"],
        "stage2_modular": ["fatal"],
    }
    single_selected, single_result, _, _ = agent._select_candidate(
        task=task,
        partial_artifacts={},
        responsibilities=ledger.responsibilities,
        candidates=candidates,
        evaluations=make_stage2_selection_evaluations(candidates, fatal_by_id=fatal_by_id),
    )

    assert identical_selected.candidate_id == "stage2_balanced"
    assert identical_result.eligible_candidate_ids == ["stage2_balanced"]
    assert single_selected.candidate_id == "stage2_conservative"
    assert single_result.eligible_candidate_ids == ["stage2_conservative"]
    assert backend.calls == []


def test_stage2_llm_selection_rejects_all_fatal_candidates(tmp_path):
    task, _, _ = make_task_input(tmp_path, image_count=0)
    ledger = validate_model(ResponsibilityLedgerOutput, make_stage2_responsibility_payload())
    candidates = make_distinct_stage2_selection_candidates()
    evaluations = make_stage2_selection_evaluations(
        candidates,
        fatal_by_id={item.candidate_id: ["fatal"] for item in candidates},
    )
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([])))

    with pytest.raises(ValueError, match="all Stage2 decomposition candidates have fatal violations"):
        agent._select_candidate(
            task=task,
            partial_artifacts={},
            responsibilities=ledger.responsibilities,
            candidates=candidates,
            evaluations=evaluations,
        )


def test_stage2_resumes_responsibilities_and_partial_candidate_set(tmp_path):
    task, md_path, image_paths = make_task_input(tmp_path, image_count=1)
    stage1 = make_stage1_contract_artifact(md_path, image_paths)
    modules = build_module_organized_artifact(stage1)
    ledger = validate_model(ResponsibilityLedgerOutput, make_stage2_responsibility_payload(md_path))
    partial = Stage2DecompositionArtifact(
        task_id=task.task_id,
        input_fingerprint="fp-stage2",
        status="responsibilities_extracted",
        locked_top=LockedTopModule(
            module="aes_cipher_top",
            resolution_mode="deterministic",
            evidence_sections=["AES Demo Repository"],
        ),
        responsibilities=ledger.responsibilities,
        state_objects=ledger.state_objects,
        global_clocking_notes=ledger.global_clocking_notes,
        global_data_conventions=ledger.global_data_conventions,
        candidates=[
            validate_model(
                Stage2DecompositionCandidate,
                make_stage2_candidate_payload("conservative", complete=False),
            )
        ],
    )
    backend = QueueBackend(
        [
            make_stage2_candidate_payload("balanced", complete=True),
            make_stage2_candidate_payload("modular", complete=False),
        ]
    )
    agent = Stage2Agent(PlannerLLMClient(backend=backend))

    artifact = agent.run(
        task,
        {
            "modules": modules,
            "stage2_input_fingerprint": "fp-stage2",
            "stage2_decomposition": partial,
        },
    )

    assert artifact.top_module == "aes_cipher_top"
    assert len(backend.calls) == 2
    assert agent._last_decomposition.selected_candidate_id == "stage2_balanced"
    assert any("Resumed Stage2" in item for item in agent._last_decomposition.selection_trace)


def test_stage3_receives_only_module_local_selected_boundaries():
    decomposition = {
        "selected_boundary_contracts": [
            make_stage2_candidate_payload("balanced", complete=True)["boundary_contracts"][0],
            {
                **make_stage2_candidate_payload("modular", complete=True)["boundary_contracts"][0],
                "producer_module": "unrelated_a",
                "consumer_module": "unrelated_b",
            },
        ]
    }
    agent = Stage3Agent(PlannerLLMClient(backend=QueueBackend([])))

    result = agent._boundary_contract_slice(decomposition, module_name="aes_cipher_top")

    assert len(result["incoming"]) == 1
    assert result["incoming"][0]["producer_module"] == "aes_key_expand_128"
    assert result["outgoing"] == []


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

    assert '"schema_version":"stage2_prompt_context_v1"' in prompt
    assert "Use modules.json as the primary source of truth" not in prompt
    assert "source spec markdown" in prompt
    assert '"known_module_candidates"' in prompt
    assert "aes_unified_functional_spec" in prompt
    assert "not treated as RTL modules" in prompt
    assert '"legacy_contract_projection"' not in prompt
    assert '"interface_contracts"' not in prompt
    assert '"text_grounding"' not in prompt


@pytest.mark.parametrize(
    "project,spec_name",
    [
        ("e203_ifu", "e203_ifu_system.md"),
        ("e203_exu_alu", "e203_exu_alu_system.md"),
    ],
)
def test_stage2_e203_prompt_is_compact_and_contains_primary_spec_once(project, spec_name):
    spec_path = (Path("rtl_dataset") / project / spec_name).resolve()
    task = PlannerTaskInput(task_id=project, spec_md_files=[str(spec_path)])
    stage2_input = build_stage2_planning_input_from_task(task_input=task)
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([])))

    prompt, _ = agent.build_prompt(task, {"stage2_input": stage2_input}, {})
    markdown = spec_path.read_text(encoding="utf-8")
    context = agent._build_stage2_prompt_context(stage2_input)

    assert len(prompt) < 90_000
    assert context["primary_source_spec"]["markdown"] == markdown
    assert prompt.count(markdown.splitlines()[0]) == 1
    for forbidden in (
        '"legacy_contract_projection"',
        '"interface_contracts"',
        '"timing_contracts"',
        '"control_contracts"',
        '"datapath_contracts"',
        '"text_grounding"',
    ):
        assert forbidden not in prompt


def test_stage2_retry_prompt_is_incremental():
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([])))
    original = "FULL SOURCE SPEC MARKER\n" + ("x" * 50_000)

    retry = agent._build_retry_prompt(original, ["top_module must not be empty"])

    assert "FULL SOURCE SPEC MARKER" not in retry
    assert len(retry) < 500
    assert "complete corrected JSON" in retry


def test_stage2_architecture_facts_are_filtered_and_bounded():
    facts = [
        {
            "fact_id": "F_TOP",
            "module": "top",
            "category": "module_identity",
            "subject": "top",
            "predicate": "is_top_module",
            "object": {"module": "top"},
            "text_grounding": [{"source_md_file": "top.md", "section_path": "Top"}],
        },
        {
            "fact_id": "F_PORT",
            "module": "top",
            "category": "interface",
            "subject": "wide_port_table",
            "predicate": "has_ports",
            "object": {"ports": ["p" + str(index) for index in range(100)]},
        },
    ]
    facts.extend(
        {
            "fact_id": f"F_RES_{index:03d}",
            "module": "top",
            "category": "resource_requirement",
            "subject": f"resource_{index}",
            "predicate": "requires",
            "object": {"resource": "x" * 300},
        }
        for index in range(100)
    )
    stage2_input = Stage2PlanningInput.model_validate(
        {"task_id": "bounded", "fact_ledger": {"facts": facts}}
    )
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([])))

    selected, omitted = agent._bounded_architecture_facts(stage2_input)
    encoded = json.dumps(selected, ensure_ascii=False, separators=(",", ":"))

    assert len(encoded) <= 20_000
    assert omitted > 0
    assert selected[0]["fact_id"] == "F_TOP"
    assert "F_PORT" not in {item["fact_id"] for item in selected}
    assert "text_grounding" not in encoded


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
                    "aes_sbox": "generate/rtl/aes_sbox.v",
                    "aes_key_expand_128": "generate/rtl/aes_key_expand_128.v",
                    "aes_cipher_top": "generate/rtl/aes_cipher_top.v",
                },
            },
            "modules": [
                {
                    "module": "aes_sbox",
                    "file_path": "generate/rtl/aes_sbox.v",
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
                    "file_path": "generate/rtl/aes_key_expand_128.v",
                    "role": "round key provider",
                    "kind": "iterative_engine",
                    "parents": ["aes_cipher_top"],
                    "children": [],
                    "instance_hints": [],
                },
                {
                    "module": "aes_cipher_top",
                    "file_path": "generate/rtl/aes_cipher_top.v",
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
                    "aes_sbox": "generate/rtl/aes_sbox.v",
                    "aes_cipher_top": "generate/rtl/aes_cipher_top.v",
                },
            },
            "modules": [
                {
                    "module": "aes_sbox",
                    "file_path": "generate/rtl/aes_sbox.v",
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
                    "file_path": "generate/rtl/aes_cipher_top.v",
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


def test_stage2_validation_allows_single_module_when_partitioning_guidance_is_not_explicit_structure(tmp_path):
    md_path = tmp_path / "hard_system.md"
    write_artifact_text(md_path,
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
                "file_map": {"hard_top": "generate/rtl/hard_top.v"},
            },
            "modules": [
                {
                    "module": "hard_top",
                    "file_path": "generate/rtl/hard_top.v",
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

    assert errors == []


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
                "file_map": {"aes_cipher_top": "generate/rtl/aes_cipher_top.v"},
            },
            "modules": [
                {
                    "module": "aes_cipher_top",
                    "file_path": "generate/rtl/aes_cipher_top.v",
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
                    "aes_sbox": "generate/rtl/aes_sbox.v",
                    "aes_cipher_top": "generate/rtl/aes_cipher_top.v",
                },
            },
            "modules": [
                {
                    "module": "aes_sbox",
                    "file_path": "generate/rtl/aes_sbox.v",
                    "role": "byte substitution helper",
                    "kind": "leaf_combinational",
                    "parents": ["aes_cipher_top"],
                    "children": [],
                    "instance_hints": [],
                },
                {
                    "module": "aes_cipher_top",
                    "file_path": "generate/rtl/aes_cipher_top.v",
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
                    "aes_sbox": "generate/rtl/aes_sbox.v",
                    "aes_cipher_top": "generate/rtl/aes_cipher_top.v",
                },
            },
            "modules": [
                {
                    "module": "aes_sbox",
                    "file_path": "generate/rtl/aes_sbox.v",
                    "role": "byte substitution helper",
                    "kind": "leaf_combinational",
                    "parents": ["aes_cipher_top"],
                    "children": [],
                    "instance_hints": [],
                },
                {
                    "module": "aes_cipher_top",
                    "file_path": "generate/rtl/aes_cipher_top.v",
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
            category="interface",
            subject="clk",
            predicate="is_port",
            obj={"name": "clk", "direction": "input", "width": "1"},
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
                "aes_cipher_top": "generate/rtl/aes_cipher_top.v",
                "aes_sbox": "generate/rtl/aes_sbox.v",
            },
            "cross_module_alignment": [],
            "global_data_conventions": [],
        },
        "modules": [
            {
                "module": "aes_sbox",
                "file_path": "generate/rtl/aes_sbox.v",
                "role": "S-box substitution unit",
                "kind": "leaf_combinational",
                "parents": ["aes_cipher_top"],
                "children": [],
                "instance_hints": [],
                "repo_notes": [],
            },
            {
                "module": "aes_cipher_top",
                "file_path": "generate/rtl/aes_cipher_top.v",
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
    agent = Stage2Agent(PlannerLLMClient(backend=QueueBackend([])))
    artifact = validate_model(Stage2RepoSkeletonArtifact, repo_payload)
    errors = agent.validate_quality(artifact, task, {"modules": modules_artifact})

    assert errors == []
    assert artifact.global_invariants.hierarchy[0].source_kind == "inferred_from_fact_ledger"
    assert artifact.modules[1].instance_hints[0].supporting_fact_ids == [support_id]


def test_stage2_allows_inferred_hierarchy_without_supporting_fact_ids(tmp_path):
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
            obj={"name": "clk", "direction": "input", "width": "1"},
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
                    "aes_cipher_top": "generate/rtl/aes_cipher_top.v",
                    "aes_sbox": "generate/rtl/aes_sbox.v",
                },
            },
            "modules": [
                {
                    "module": "aes_sbox",
                    "file_path": "generate/rtl/aes_sbox.v",
                    "role": "S-box substitution unit",
                    "kind": "leaf_combinational",
                    "parents": ["aes_cipher_top"],
                    "children": [],
                    "instance_hints": [],
                },
                {
                    "module": "aes_cipher_top",
                    "file_path": "generate/rtl/aes_cipher_top.v",
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

    assert errors == []


def test_stage2_normalizes_empty_fact_ledger_provenance_to_spec():
    assert (
        Stage2Agent._normalized_evidence_source_kind(
            "inferred_from_fact_ledger",
            [],
        )
        == "inferred_from_spec"
    )
    assert (
        Stage2Agent._normalized_evidence_source_kind(
            "inferred_from_fact_ledger",
            ["F0001"],
        )
        == "inferred_from_fact_ledger"
    )


def test_stage3_agent_builds_module_skeletons_incrementally(tmp_path):
    from test_responsibility_refinement import scenario
    _, runner, backend, _, stage3, stage4 = scenario(tmp_path)
    assert stage3.schema_version == "stage3_skeleton_json_v3"
    assert stage4.schema_version == "module_plans_v3"
    for record in stage3.module_records:
        export = json.loads((runner.output_root / record.export_file).read_text())
        assert export["behavioral_obligations"] and export["structural_blocks"]
        assert (runner.output_root / record.doc_file).read_text().startswith("# MODULE_SKELETON_DOC v3")
    assert not backend.responses


def test_stage3_agent_retries_portless_synthesizable_module_skeleton(tmp_path):
    from copy import deepcopy
    from test_responsibility_refinement import scenario
    saved = {}
    def inject(runner):
        responses = runner.llm_client.backend.responses
        index = next(i for i, value in enumerate(responses) if isinstance(value, dict) and "module_frame" in value)
        good = deepcopy(responses[index]); saved["frame"] = good["module_frame"]
        responses[index]["module_frame"] = "module aes_key_expand_128; endmodule"
        responses.insert(index+1, {"module_frame":good["module_frame"]})
    _, runner, backend, _, stage3, _ = scenario(tmp_path, before_run=inject)
    export = json.loads((runner.output_root/stage3.module_records[0].export_file).read_text())
    assert export["module_frame"] == saved["frame"]
    assert any('"sections":["module_frame"]' in c["user_prompt"] for c in backend.calls)


def test_stage3_agent_resolves_specs_from_directory_input(tmp_path):
    from test_responsibility_refinement import scenario
    _, runner, _, _, stage3, _ = scenario(tmp_path)
    record = stage3.module_records[0]
    source = Path(record.source_refs.module_spec_file)
    assert source.exists()
    assert runner.stage3._resolve_module_spec_file(PlannerTaskInput(task_id="directory", spec_md_files=expand_markdown_inputs([str(source.parent)])), record.module)


def test_stage3_agent_falls_back_to_unified_spec_when_module_spec_is_missing(tmp_path):
    from test_responsibility_refinement import scenario
    task, _, _, _, stage3, _ = scenario(tmp_path)
    assert all(r.source_refs.module_spec_file == task.spec_md_files[0] for r in stage3.module_records)


def test_stage3_agent_resume_regenerates_missing_sidecars(tmp_path):
    from test_responsibility_refinement import scenario
    task, runner, backend, _, stage3, _ = scenario(tmp_path)
    count = len(backend.calls)
    path = runner.output_root/stage3.module_records[0].doc_file
    path.unlink()
    runner.run(task, resume=True, end_stage="stage4")
    assert path.exists() and len(backend.calls) == count


def test_stage3_agent_resume_uses_cursor_and_skips_completed_sidecar(tmp_path):
    from test_responsibility_refinement import scenario
    task, runner, backend, _, stage3, _ = scenario(tmp_path)
    count = len(backend.calls)
    body = (runner.output_root/stage3.module_records[0].export_file).read_bytes()
    runner.run(task, resume=True, end_stage="stage4")
    assert len(backend.calls) == count
    assert (runner.output_root/stage3.module_records[0].export_file).read_bytes() == body


def test_stage3_agent_reuses_definition_only_undecided_export(tmp_path):
    spec_path = tmp_path / "sd_defines.md"
    write_artifact_text(spec_path, "# sd_defines\nDefinition constants only.\n", encoding="utf-8")
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
        expected_file_path="generate/rtl/sd_defines.v",
        source_refs={
            "module_contract_ref": "module_contracts_v1::sd_defines",
            "repo_skeleton_ref": "repo_skeleton_v1::sd_defines",
            "module_spec_file": str(spec_path.resolve()),
        },
    )
    write_artifact_text(ArtifactLayout(output_root).module(3, Path("sd_defines.md").stem, "skeleton.md"), doc, encoding="utf-8")
    write_artifact_text(ArtifactLayout(output_root).module(3, Path("sd_defines.json").stem, "skeleton.json"),
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
    write_artifact_text(spec_path, "# aes_cipher_top\n", encoding="utf-8")
    doc = make_stage3_module_skeleton_doc("aes_cipher_top", spec_path)

    export = parse_module_skeleton_doc(
        doc,
        expected_module="aes_cipher_top",
        expected_file_path="generate/rtl/aes_cipher_top.v",
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


def test_stage3_parser_rejects_missing_state_representation(tmp_path):
    spec_path = tmp_path / "sdc_controller.md"
    write_artifact_text(spec_path, "# sdc_controller\n", encoding="utf-8")
    doc = make_stage3_module_skeleton_doc("sdc_controller", spec_path).replace(
        "  - object: round_key_reg\n    storage_kind: registered\n    representation: packed vector\n    notes: primary stored representation for the module",
        "  - object: no top-level registered state objects; state held inside sub-modules",
    )

    with pytest.raises(ValueError) as error:
        parse_module_skeleton_doc(
            doc,
            expected_module="sdc_controller",
            expected_file_path="generate/rtl/sdc_controller.v",
            source_refs={
                "module_contract_ref": "module_contracts_v1::sdc_controller",
                "repo_skeleton_ref": "repo_skeleton_v1::sdc_controller",
                "module_spec_file": str(spec_path.resolve()),
            },
        )

    assert "state_model[0].storage_kind" in str(error.value)
    assert "state_model[0].representation" in str(error.value)

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
    write_artifact_text(spec_path,
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
    write_artifact_text(spec_path,
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


def test_top_module_spec_context_forces_all_primary_port_table_sections(tmp_path):
    spec_path = tmp_path / "table_top.md"
    write_artifact_text(spec_path,
        "\n".join(
            [
                "# Table Top",
                "Top module: table_top",
                "",
                "## Request Ports",
                "| Name | Direction | Width |",
                "| --- | --- | --- |",
                "| req_i | Input | 1 |",
                "",
                "## Configuration Glossary",
                "| Name | Meaning | Default |",
                "| --- | --- | --- |",
                "| Input | Direction selector | 0 |",
                "",
                "## Response Ports",
                "| Signal | Dir | Bit Width |",
                "| --- | --- | --- |",
                "| rsp_o | Output | 8 |",
            ]
        ),
        encoding="utf-8",
    )
    backend = QueueBackend(
        [
            {
                "schema_version": "module_spec_context_retrieval_v1",
                "module": "table_top",
                "blocks": [
                    {
                        "block_id": "S001",
                        "text": (
                            "## Configuration Glossary\n"
                            "| Name | Meaning | Default |\n"
                            "| --- | --- | --- |\n"
                            "| Input | Direction selector | 0 |"
                        ),
                        "source_file": str(spec_path.resolve()),
                        "source_chunk_ids": ["C003"],
                        "relevance_reason": ["LLM selected only a supplemental section."],
                        "confidence": "low",
                    }
                ],
                "fallback_used": False,
            }
        ]
    )
    retriever = ModuleSpecContextRetriever(PlannerLLMClient(backend=backend), max_chunks=4)

    result = retriever.select_module_spec_context(
        module_name="table_top",
        spec_md_files=[str(spec_path)],
        repo_module={"module": "table_top", "role": "top configuration glossary"},
        is_top_module=True,
        primary_spec_file=str(spec_path),
    )

    prompt = backend.calls[0]["user_prompt"]
    combined = "\n\n".join(block.text for block in result.blocks)
    assert "req_i" in prompt and "rsp_o" in prompt
    assert "req_i" in combined and "rsp_o" in combined
    assert [block.block_id for block in result.blocks] == ["S001", "S002", "S003"]
    assert result.blocks[0].source_chunk_ids == ["C002"]
    assert result.blocks[-1].source_chunk_ids == ["C004"]


def test_stage3_module_frame_validation_does_not_require_interface_contract():
    agent = Stage3Agent(PlannerLLMClient(backend=QueueBackend([])))
    valid_frame = "\n".join(
        [
            "module toy (",
            "  input wire clk,",
            "`ifdef FEATURE_DATA_O",
            "  output wire [7:0] data_o,",
            "`endif",
            "  input wire [`WIDTH-1:0] data_i",
            ");",
            "endmodule",
        ]
    )

    assert ansi_module_ports(valid_frame)[-1].width == "WIDTH"
    assert agent._validate_module_frame_interface(
        valid_frame,
        expected_module="toy",
    ) == []

    wrong_frame = "\n".join(
        [
            "module toy (",
            "  input wire clk,",
            "  input wire [7:0] data_o,",
            "  input wire [3:0] extra_i",
            ");",
            "endmodule",
        ]
    )
    assert agent._validate_module_frame_interface(
        wrong_frame,
        expected_module="toy",
    ) == []

    placeholder_errors = agent._validate_module_frame_interface(
        "module toy (/* port list placeholder */);\nendmodule",
        expected_module="toy",
    )
    assert any("port placeholder" in error for error in placeholder_errors)

    assert agent._validate_module_frame_interface(
        "module child;\nendmodule",
        expected_module="child",
    ) == []
    empty_port_errors = agent._validate_module_frame_interface(
        "module child;\nendmodule",
        expected_module="child",
        require_ports=True,
    )
    assert any("at least one concrete ANSI port" in error for error in empty_port_errors)


def test_stage4_spec_blocks_uses_module_context_retrieval_for_unified_spec_without_section(tmp_path):
    from test_responsibility_refinement import scenario
    _, runner, backend, _, _, _ = scenario(tmp_path)
    spec = json.loads(runner.layout.artifact("spec_blocks.json").read_text())
    assert spec["schema_version"] == "spec_blocks_v2"
    assert all(b["source_evidence_ids"] for m in spec["modules"] for b in m["blocks"])
    assert not any("[SOURCE_CHUNKS]" in call["user_prompt"] for call in backend.calls)
    for module in spec["modules"]:
        refs = json.loads(runner.layout.module(4, module["module"], "spec_refs.json").read_text())
        assert not refs["fallback_used"]


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
    write_artifact_text(spec_path, "# aes_sbox\n", encoding="utf-8")
    doc = "\n".join(
        [
            "# MODULE_SKELETON_DOC v1",
            "",
            "## 0. Module Identity",
            "- module_name: aes_sbox",
            "- file_path: generate/rtl/aes_sbox.v",
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
        expected_file_path="generate/rtl/aes_sbox.v",
        source_refs={
            "module_contract_ref": "module_contracts_v1::aes_sbox",
            "repo_skeleton_ref": "repo_skeleton_v1::aes_sbox",
            "module_spec_file": str(spec_path.resolve()),
        },
    )

    assert [item.block_id for item in export.structural_blocks] == ["B1", "B2", "B3"]
    assert [item.block_id for item in export.block_behavior_overlays] == ["B1", "B3"]


def test_stage3_parser_accepts_indented_decision_mapping_fields(tmp_path):
    spec_path = tmp_path / "aes_cipher_top.md"
    write_artifact_text(spec_path, "# aes_cipher_top\n", encoding="utf-8")
    doc = make_stage3_module_skeleton_doc("aes_cipher_top", spec_path).replace(
        "- topic: control style\n"
        "- decision: Keep semantic modes separate from the low-level code realization style.\n"
        "- reason: This avoids forcing an explicit FSM when counter- or flag-driven control is sufficient.",
        "- topic: control style\n"
        "  decision: Keep semantic modes separate from the low-level code realization style.\n"
        "  reason: This avoids forcing an explicit FSM when counter- or flag-driven control is sufficient.",
    )

    export = parse_module_skeleton_doc(
        doc,
        expected_module="aes_cipher_top",
        expected_file_path="generate/rtl/aes_cipher_top.v",
        source_refs={
            "module_contract_ref": "module_contracts_v1::aes_cipher_top",
            "repo_skeleton_ref": "repo_skeleton_v1::aes_cipher_top",
            "module_spec_file": str(spec_path.resolve()),
        },
    )

    assert export.decision_ledger.chosen_decisions[0].topic == "control style"
    assert export.decision_ledger.chosen_decisions[0].decision.startswith("Keep semantic modes")


def test_stage3_parser_rejects_unknown_overlay_block(tmp_path):
    spec_path = tmp_path / "aes_cipher_top.md"
    write_artifact_text(spec_path, "# aes_cipher_top\n", encoding="utf-8")
    doc = make_stage3_module_skeleton_doc("aes_cipher_top", spec_path).replace(
        "- block_id: B2\n- responsibilities:",
        "- block_id: B999\n- responsibilities:",
        1,
    )

    with pytest.raises(ValueError, match="unknown block_id"):
        parse_module_skeleton_doc(
            doc,
            expected_module="aes_cipher_top",
            expected_file_path="generate/rtl/aes_cipher_top.v",
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
                refusal = None
                tool_calls = None

            class Choice:
                message = Message()
                finish_reason = "stop"

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
