from __future__ import annotations

import json
from pathlib import Path
from rtl_artifact_test_utils import write_artifact_text
from zerorepo.rtl_impl.artifact_layout import ArtifactLayout, artifact_path
from unittest.mock import Mock

import pytest

from zerorepo.rtl_impl.module_planner import PlannerRunner
from zerorepo.rtl_impl.module_planner.agents import (
    Stage1TemporalAgent,
    Stage2TemporalContractAgent,
    Stage4ModulePlanAgent,
    Stage5Agent,
)
from zerorepo.rtl_impl.module_planner.prompts import (
    stage1_temporal_extract,
    stage2_temporal_contract,
    stage3_timing_binding,
)
from zerorepo.rtl_impl.module_planner.schemas import (
    ArchitectureTimingContractArtifact,
    GlobalTemporalFactsArtifact,
    ModulePlanSubtask,
    ModuleSkeletonExport,
    ModuleTimingBindingArtifact,
    PlannerTaskInput,
    Stage2RepoSkeletonArtifact,
    Stage3ModuleSkeletonArtifact,
    SubtaskCodeArtifact,
    TimingBindingCheckArtifact,
)
from zerorepo.rtl_impl.module_planner.utils import PlannerLLMClient, check_temporal_bindings


class QueueBackend:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, *, system_prompt, user_prompt, images=None):
        self.calls.append({"system_prompt": system_prompt, "user_prompt": user_prompt, "images": list(images or [])})
        if not self.responses:
            raise AssertionError("No more queued responses.")
        return self.responses.pop(0)

    def complete_with_memory(self, *, memory, images=None):
        user_prompt = next((item.content for item in reversed(memory.history) if item.role == "user"), "")
        self.calls.append({"user_prompt": user_prompt, "images": list(images or [])})
        if not self.responses:
            raise AssertionError("No more queued responses.")
        return self.responses.pop(0)


def _task(tmp_path: Path) -> tuple[PlannerTaskInput, Path]:
    spec = tmp_path / "toy.md"
    write_artifact_text(spec,
        "\n".join(
            [
                "# Toy",
                "Top module: toy",
                "Ports:",
                "- clk: input, width 1",
                "- rst_n: input, width 1",
                "- ld: input, width 1",
                "- done: output, width 1",
                "On rise(ld), load State0.",
                "One cycle later, produce State1 and pulse done.",
            ]
        ),
        encoding="utf-8",
    )
    return PlannerTaskInput(task_id="toy", spec_md_files=[str(spec)]), spec.resolve()


def _stage1_facts_payload(spec_path: Path) -> dict:
    grounding = [
        {
            "source_md_file": str(spec_path),
            "section_path": "Toy",
            "start_line_anchor": "Top module: toy",
            "end_line_anchor": "- done: output, width 1",
        }
    ]
    return {
        "fact_ledger": {
            "source_files": [str(spec_path)],
            "facts": [
                {
                    "module": "toy",
                    "category": "module_identity",
                    "subject": "toy",
                    "predicate": "is_top_module",
                    "object": {"module": "toy", "modules": ["toy"]},
                    "source_kind": "explicit_text",
                    "text_grounding": grounding,
                },
                *[
                    {
                        "module": "toy",
                        "category": "interface",
                        "subject": name,
                        "predicate": "is_port",
                        "object": {"name": name, "direction": direction, "width": "1"},
                        "source_kind": "table_row",
                        "text_grounding": grounding,
                    }
                    for name, direction in [
                        ("clk", "input"),
                        ("rst_n", "input"),
                        ("ld", "input"),
                        ("done", "output"),
                    ]
                ],
            ],
            "ambiguous_items": [],
        }
    }


def _temporal_payload(spec_path: Path) -> dict:
    grounding = [{"source_md_file": str(spec_path), "section_path": "Toy"}]
    return {
        "schema_version": "global_temporal_facts_v1",
        "task_id": "toy",
        "clock": {"name": "clk", "edge": "posedge"},
        "reset": {"name": "rst_n", "polarity": "active_low", "kind": "asynchronous"},
        "events": [
            {
                "id": "EV_LD",
                "name": "load",
                "kind": "start",
                "trigger": "rise(ld)",
                "text_grounding": grounding,
            },
            {
                "id": "EV_DONE",
                "name": "done",
                "kind": "completion",
                "trigger": "done == 1",
                "text_grounding": grounding,
            },
        ],
        "phases": [
            {
                "id": "PH_UPDATE",
                "name": "UPDATE",
                "order": 0,
                "trigger_event_id": "EV_LD",
                "cycles": 1,
                "text_grounding": grounding,
            }
        ],
        "latency_constraints": [
            {
                "id": "LAT_LD_DONE",
                "start_event_id": "EV_LD",
                "end_event_id": "EV_DONE",
                "cycles": 1,
                "counting_basis": "edge_distance",
                "raw_statement": "One cycle later",
                "status": "resolved",
                "text_grounding": grounding,
            }
        ],
        "logical_value_sequences": [
            {"object": "state", "tags": ["State0", "State1"], "text_grounding": grounding}
        ],
        "relations": [
            {
                "id": "REL_UPDATE_DONE",
                "source_id": "PH_UPDATE",
                "target_id": "EV_DONE",
                "relation": "NEXT_EDGE",
                "text_grounding": grounding,
            }
        ],
        "invariants": [
            {
                "id": "INV_UPDATE",
                "statement": "Update produces State1.",
                "phase_id": "PH_UPDATE",
                "logical_object": "state",
                "required_value_tag": "State1",
                "text_grounding": grounding,
            }
        ],
        "ambiguities": [],
        "unsupported_features": [],
    }


def _repo_payload() -> dict:
    return {
        "schema_version": "repo_skeleton_v1",
        "task_id": "toy",
        "source_schema_version": "stage2_planning_input_v1",
        "stage2_status": "repo_skeleton_planned",
        "top_module": "toy",
        "global_invariants": {
            "system_role": "single-cycle toy state update",
            "clocking_model": {
                "primary_clock": "clk",
                "reset_signal": "rst_n",
                "reset_style": "active-low asynchronous",
            },
            "hierarchy": [],
            "file_map": {"toy": "generate/rtl/toy.v"},
            "cross_module_alignment": [],
            "global_data_conventions": [],
        },
        "modules": [
            {
                "module": "toy",
                "file_path": "generate/rtl/toy.v",
                "role": "state update controller",
                "kind": "top_controller",
                "source_kind": "inferred_from_spec",
                "rationale": "The complete toy behavior is one module.",
                "confidence": "high",
                "module_decision": "required",
                "parents": [],
                "children": [],
                "instance_hints": [],
                "repo_notes": [],
            }
        ],
        "planning_decisions": {
            "generation_order": ["toy"],
            "leaf_first": True,
            "shared_modules": [],
            "top_level_integration_notes": [],
        },
        "open_issues": [],
    }


def _stage2_responsibilities() -> dict:
    return {
        "responsibilities": [
            {
                "responsibility_id": "RU_TOY_UPDATE",
                "description": "Own the toy state update and completion behavior.",
                "ownership_required": True,
                "evidence_sections": ["Toy Spec > Timing"],
                "inputs": ["ld", "state"],
                "outputs": ["done", "state"],
                "owned_state": ["state"],
                "clock_domain": "clk",
                "reset_behavior": "rst_n active low",
                "protocol": "load_to_done",
                "timing_class": "single_cycle_registered",
                "dependencies": [],
                "explicit_module_hint": "toy",
            }
        ],
        "global_clocking_notes": ["clk with active-low rst_n"],
        "global_data_conventions": [],
    }


def _stage2_candidate(style: str, *, grounded: bool) -> dict:
    return {
        "candidate_id": f"stage2_{style}",
        "plan_style": style,
        "top_module": "toy",
        "summary": "single-cycle toy state update",
        "modules": [
            {
                "module": "toy",
                "role": "state update controller",
                "responsibility_ids": ["RU_TOY_UPDATE"],
                "source_kind": "inferred_from_spec",
                "supporting_sections": ["Toy Spec > Timing"] if grounded else [],
                "rationale": "The complete toy behavior is one module.",
                "confidence": "high",
                "reused": False,
            }
        ],
        "hierarchy": [],
        "boundary_contracts": [],
        "global_clocking_notes": ["clk with active-low rst_n"],
        "global_data_conventions": [],
        "open_issues": [],
    }


def _stage2_decomposition_responses(spec_path) -> list[dict]:
    responses = [
        {**_stage2_responsibilities(), "responsibilities": [{**_stage2_responsibilities()["responsibilities"][0],
          "source_refs": [{"source_file": str(spec_path), "quote": spec_path.read_text()}],
          "state_accesses": [{"state_id": "state", "role": "commit"}]}],
          "state_objects": [{"state_id": "state", "name": "state", "owner_responsibility_id": "RU_TOY_UPDATE",
             "source_refs": [{"source_file": str(spec_path), "quote": spec_path.read_text()}]}]},
        _stage2_candidate("conservative", grounded=False),
        _stage2_candidate("balanced", grounded=True),
        _stage2_candidate("modular", grounded=False),
    ]

    from zerorepo.rtl_impl.module_planner.utils.evidence import EvidenceRegistry
    from zerorepo.rtl_impl.module_planner.module_organizer import build_stage2_planning_input_from_task
    registry = EvidenceRegistry(build_stage2_planning_input_from_task(task_input=PlannerTaskInput(task_id="toy", spec_md_files=[str(spec_path)])))
    for group in ("responsibilities", "state_objects"):
        for item in responses[0][group]: item["source_evidence_ids"] = list(registry.entries)
    return responses


def _architecture_payload() -> dict:
    return {
        "schema_version": "architecture_timing_contract_v1",
        "task_id": "toy",
        "module_set": ["toy"],
        "module_assignments": [
            {
                "module": "toy",
                "owns_logical_state": ["state"],
                "handles_event_ids": ["EV_LD", "EV_DONE"],
                "handles_phase_ids": ["PH_UPDATE"],
            }
        ],
        "cross_module_transfers": [],
        "module_obligations": [
            {
                "id": "OBL_UPDATE",
                "module": "toy",
                "phase_id": "PH_UPDATE",
                "reads": [
                    {"logical_object": "state", "logical_value_tag": "State0", "at": "PRE_EDGE"}
                ],
                "writes": [
                    {"logical_object": "state", "logical_value_tag": "State1", "at": "POST_EDGE"}
                ],
                "combinational_outputs": [],
                "latency_cycles": 1,
                "source_temporal_ids": ["PH_UPDATE", "INV_UPDATE"],
            }
        ],
        "assumptions": [],
    }


def test_planner_runner_temporal_planning_is_disabled_by_default(tmp_path):
    task, spec_path = _task(tmp_path)
    backend = QueueBackend([_stage1_facts_payload(spec_path)])
    output_root = tmp_path / "outputs"
    runner = PlannerRunner(output_root=output_root, llm_backend=backend)

    artifact = runner.run(task, end_stage="stage1")

    assert runner.temporal_planning_enabled is False
    assert artifact.schema_version == "stage1_contracts_v1"
    assert not (output_root / "global_temporal_facts.json").exists()
    assert (artifact_path(output_root, "contracts.json")).exists()
    assert len(backend.calls) == 1


def test_stage1_temporal_quality_does_not_validate_grounding_paths(tmp_path):
    task, spec_path = _task(tmp_path)
    payload = _temporal_payload(spec_path)
    for collection_name in (
        "events",
        "phases",
        "latency_constraints",
        "logical_value_sequences",
        "relations",
        "invariants",
    ):
        for item in payload[collection_name]:
            item["text_grounding"] = [
                {
                    "source_md_file": "aes_inv_cipher_system_hard.md",
                    "section_path": "an LLM-provided section label",
                }
            ]

    artifact = GlobalTemporalFactsArtifact.model_validate(payload)
    agent = Stage1TemporalAgent(PlannerLLMClient(backend=QueueBackend([])))

    assert agent.validate_quality(artifact, task, {}) == []


def test_stage1_temporal_prompt_lists_all_enums_and_complete_json_example():
    prompt = stage1_temporal_extract.build_prompt(
        task_id="toy",
        source_specs_json="[]",
    )

    assert 'clock.edge: "posedge" | "negedge" | "unspecified"' in prompt
    assert 'reset.polarity: "active_high" | "active_low" | "unspecified"' in prompt
    assert 'reset.kind: "synchronous" | "asynchronous" | "unspecified"' in prompt
    assert 'events[].kind: "start" | "completion" | "reset" | "status" | "other"' in prompt
    assert (
        'latency_constraints[].counting_basis: "edge_distance" | '
        '"inclusive_cycles" | "unspecified"'
    ) in prompt
    assert (
        'latency_constraints[].status: "resolved" | "ambiguous" | "unsupported"'
    ) in prompt
    assert (
        'relations[].relation: "SAME_EDGE" | "NEXT_EDGE" | '
        '"EXACT_CYCLES" | "BEFORE"'
    ) in prompt
    assert "Complete valid JSON example:" in prompt
    assert '"schema_version": "global_temporal_facts_v1"' in prompt
    assert '"text_grounding": [' in prompt
    assert 'Do not use "signal_edge", "signal_level", or "condition"' in prompt

    example = json.loads(stage1_temporal_extract.VALID_JSON_EXAMPLE)
    GlobalTemporalFactsArtifact.model_validate(example)


def test_stage2_temporal_prompt_lists_exact_fields_and_valid_example():
    prompt = stage2_temporal_contract.build_prompt(
        task_id="toy",
        temporal_facts_json="{}",
        repo_skeleton_json="{}",
        global_logical_objects_json='["state"]',
    )

    assert "architecture_logical_objects" in prompt
    assert "required_cycle_offset" in prompt
    assert "Do not use cycle_offset" in prompt
    assert '["state"]' in prompt
    assert "Complete valid JSON example:" in prompt

    example = json.loads(stage2_temporal_contract.VALID_JSON_EXAMPLE)
    ArchitectureTimingContractArtifact.model_validate(example)


def test_stage2_temporal_normalizes_legacy_fields_and_accepts_declared_objects(tmp_path):
    task, spec_path = _task(tmp_path)
    temporal = GlobalTemporalFactsArtifact.model_validate(_temporal_payload(spec_path))
    repo_payload = _repo_payload()
    repo_payload["top_module"] = "consumer"
    repo_payload["global_invariants"]["file_map"] = {
        "producer": "generate/rtl/producer.v",
        "consumer": "generate/rtl/consumer.v",
    }
    repo_payload["modules"] = [
        {
            **repo_payload["modules"][0],
            "module": "producer",
            "file_path": "generate/rtl/producer.v",
            "kind": "leaf_stateful",
        },
        {**repo_payload["modules"][0], "module": "consumer", "file_path": "generate/rtl/consumer.v"},
    ]
    repo_payload["planning_decisions"]["generation_order"] = ["producer", "consumer"]
    repo = Stage2RepoSkeletonArtifact.model_validate(repo_payload)
    agent = Stage2TemporalContractAgent(PlannerLLMClient(backend=QueueBackend([])))
    aes_architecture_objects = [
        "subword_input_byte",
        "subword_output_byte",
        "round_key_data",
        "write_enable",
        "key_load_info",
        "read_address",
        "round_key_data_out",
        "state_byte_in",
        "substituted_byte_out",
    ]
    payload = {
        "task_id": "toy",
        "module_set": ["producer", "consumer"],
        "architecture_logical_objects": aes_architecture_objects,
        "module_assignments": {
            "producer": {"owns_logical_objects": ["round_key_data"]},
            "consumer": {},
        },
        "cross_module_transfers": [
            {
                "id": f"XFER_AES_{index}",
                "source_module": "producer",
                "dest_module": "consumer",
                "logical_object": logical_object,
                "delivery": "REGISTERED",
                "visible_at": "POST_EDGE",
                "sampled_at": "PRE_EDGE",
                "cycle_offset": 1,
                "source_temporal_ids": ["PH_UPDATE"],
            }
            for index, logical_object in enumerate(aes_architecture_objects)
        ],
        "module_obligations": [],
    }

    artifact = agent._coerce_output(payload)

    assert all(item.required_cycle_offset == 1 for item in artifact.cross_module_transfers)
    assert artifact.module_assignments[0].owns_logical_state == ["round_key_data"]
    assert agent.validate_quality(artifact, task, {"temporal_facts": temporal, "stage2": repo}) == []


def test_legacy_temporal_artifact_is_ignored_and_preserved_on_resume(tmp_path):
    task, _ = _task(tmp_path)
    output_root = tmp_path / "outputs"
    output_root.mkdir()
    legacy_path = output_root / "global_temporal_facts.json"
    legacy_text = '{"legacy":true}\n'
    write_artifact_text(legacy_path, legacy_text, encoding="utf-8")
    runner = PlannerRunner(
        output_root=output_root,
        llm_backend=QueueBackend([_stage1_facts_payload(task.spec_md_files[0])]),
    )

    artifact = runner.run(task, end_stage="stage1")

    assert artifact.schema_version == "stage1_contracts_v1"
    assert legacy_path.read_text(encoding="utf-8") == legacy_text

    resume_backend = QueueBackend([])
    resumed = PlannerRunner(output_root=output_root, llm_backend=resume_backend).run(
        task,
        resume=True,
        end_stage="stage1",
    )
    assert resumed.schema_version == "stage1_contracts_v1"
    assert resume_backend.calls == []
    assert legacy_path.read_text(encoding="utf-8") == legacy_text


def test_temporal_compatibility_options_are_ignored_even_in_strict_mode(tmp_path):
    task, _ = _task(tmp_path)
    backend = QueueBackend([_stage1_facts_payload(task.spec_md_files[0])])
    runner = PlannerRunner(
        output_root=tmp_path / "outputs",
        llm_backend=backend,
        temporal_planning_enabled=True,
        temporal_failure_policy="strict",
    )

    artifact = runner.run(task, end_stage="stage1")

    assert runner.temporal_planning_enabled is False
    assert artifact.schema_version == "stage1_contracts_v1"
    assert len(backend.calls) == 1


def test_stage3_timing_binding_prompt_lists_all_fields_enums_and_valid_example():
    prompt = stage3_timing_binding.build_prompt(
        task_id="toy",
        module_name="toy",
        temporal_facts_json="{}",
        architecture_slice_json="{}",
        module_skeleton_json="{}",
        module_spec_context_json="{}",
    )

    assert 'signal_bindings[].kind: "input" | "output" | "register" | "wire"' in prompt
    assert 'transfer_bindings[].endpoint: "producer" | "consumer"' in prompt
    assert 'reads[].at: "PRE_EDGE" | "POST_EDGE" | "COMB"' in prompt
    assert 'writes[].at: "PRE_EDGE" | "POST_EDGE" | "COMB"' in prompt
    assert 'combinational_outputs[].at: "PRE_EDGE" | "POST_EDGE" | "COMB"' in prompt
    assert 'Never use "internal" as kind.' in prompt
    assert "signal_name for physical_signal" in prompt
    assert "Each architecture obligation produces exactly one block_obligations entry" in prompt
    assert "Complete valid JSON example:" in prompt
    assert '"logical_value_tags": ["RK0", "RK1", "RK2"]' in prompt
    assert '"logical_value_tag": "RK1"' in prompt

    example = json.loads(stage3_timing_binding.VALID_JSON_EXAMPLE)
    ModuleTimingBindingArtifact.model_validate(example)


def test_stage2_completion_does_not_run_or_write_temporal_sidecars(tmp_path):
    task, spec_path = _task(tmp_path)
    backend = QueueBackend([_stage1_facts_payload(spec_path), *_stage2_decomposition_responses(spec_path)])
    output_root = tmp_path / "outputs"
    runner = PlannerRunner(output_root=output_root, llm_backend=backend)

    artifact = runner.run(task, end_stage="stage2")

    assert isinstance(artifact, Stage2RepoSkeletonArtifact)
    assert not (output_root / "global_temporal_facts.json").exists()
    assert not (output_root / "architecture_timing_contract.json").exists()
    assert not (output_root / "module_timing_bindings.json").exists()
    assert not (output_root / "timing_binding_check.json").exists()
    assert len(backend.calls) == 5
    assert "not modules" in backend.calls[1]["user_prompt"].lower()

    resume_backend = QueueBackend([])
    resumed = PlannerRunner(output_root=output_root, llm_backend=resume_backend).run(
        task,
        resume=True,
        end_stage="stage2",
    )
    assert isinstance(resumed, Stage2RepoSkeletonArtifact)
    assert resume_backend.calls == []

    write_artifact_text(spec_path, spec_path.read_text(encoding="utf-8") + "\nAdditional timing clarification.", encoding="utf-8")
    changed_backend = QueueBackend([_stage1_facts_payload(spec_path), *_stage2_decomposition_responses(spec_path)])
    PlannerRunner(output_root=output_root, llm_backend=changed_backend).run(
        task,
        resume=True,
        end_stage="stage2",
    )
    assert len(changed_backend.calls) == 5


def test_stage2_ignores_existing_architecture_timing_sidecar(tmp_path):
    task, spec_path = _task(tmp_path)
    output_root = tmp_path / "outputs"
    output_root.mkdir()
    sidecar = output_root / "architecture_timing_contract.json"
    original = '{"legacy":"do-not-touch"}\n'
    write_artifact_text(sidecar, original, encoding="utf-8")
    backend = QueueBackend([_stage1_facts_payload(spec_path), *_stage2_decomposition_responses(spec_path)])
    runner = PlannerRunner(output_root=output_root, llm_backend=backend)

    runner.run(task, end_stage="stage2")

    assert sidecar.read_text(encoding="utf-8") == original
    assert len(backend.calls) == 5


def test_degraded_architecture_skips_stage3_timing_llm(tmp_path):
    task, spec_path = _task(tmp_path)
    output_root = tmp_path / "outputs"
    export_path = ArtifactLayout(output_root).module(3, Path("toy.json").stem, "skeleton.json")
    export_path.parent.mkdir(parents=True)
    write_artifact_text(export_path, json.dumps(_skeleton("toy").model_dump()), encoding="utf-8")
    stage3 = Stage3ModuleSkeletonArtifact.model_validate(
        {
            "task_id": "toy",
            "top_module": "toy",
            "module_order": ["toy"],
            "completed_modules": ["toy"],
            "resume_cursor": 1,
            "stage3_status": "module_skeletons_planned",
            "global_summary": ["toy"],
            "module_records": [
                {
                    "module": "toy",
                    "doc_file": "plan/stage3/modules/toy/skeleton.md",
                    "export_file": "plan/stage3/modules/toy/skeleton.json",
                    "source_refs": {
                        "module_contract_ref": "modules::toy",
                        "repo_skeleton_ref": "repo::toy",
                        "module_spec_file": "toy.md",
                    },
                    "block_ids": ["B1", "B2"],
                }
            ],
        }
    )
    temporal = GlobalTemporalFactsArtifact.model_validate(_temporal_payload(spec_path))
    repo = Stage2RepoSkeletonArtifact.model_validate(_repo_payload())
    architecture = ArchitectureTimingContractArtifact.model_validate(
        {
            "task_id": "toy",
            "planning_status": "degraded",
            "degradation_reasons": ["test fallback"],
            "module_set": ["toy"],
            "module_assignments": [{"module": "toy"}],
        }
    )
    backend = QueueBackend([])
    runner = PlannerRunner(output_root=output_root, llm_backend=backend)

    manifest, _ = runner._run_temporal_binding_stages(
        task=task,
        temporal_facts=temporal,
        repo_skeleton=repo,
        architecture_timing=architecture,
        module_skeletons=stage3,
        resume=False,
    )

    binding_path = output_root / manifest.module_binding_files[0].binding_file
    binding = ModuleTimingBindingArtifact.model_validate(
        json.loads(binding_path.read_text(encoding="utf-8"))
    )
    assert manifest.status == "planned"
    assert binding.signal_bindings == []
    assert binding.transfer_bindings == []
    assert binding.block_obligations == []
    assert backend.calls == []


def test_temporal_planning_can_be_explicitly_disabled_for_baseline(tmp_path):
    task, _ = _task(tmp_path)
    runner = PlannerRunner(
        output_root=tmp_path / "outputs",
        llm_backend=QueueBackend([_stage1_facts_payload(task.spec_md_files[0])]),
        temporal_planning_enabled=False,
    )

    artifact = runner.run(task, end_stage="stage1")

    assert artifact.schema_version == "stage1_contracts_v1"
    assert not (tmp_path / "outputs" / "global_temporal_facts.json").exists()


def _skeleton(module: str, seq_block: str = "B2") -> ModuleSkeletonExport:
    return ModuleSkeletonExport.model_validate(
        {
            "module": module,
            "file_path": f"generate/rtl/{module}.v",
            "source_refs": {
                "module_contract_ref": f"modules::{module}",
                "repo_skeleton_ref": f"repo::{module}",
                "module_spec_file": f"{module}.md",
            },
            "module_frame": "planning only",
            "structural_blocks": [
                {
                    "block_id": "B1",
                    "block_label": "decl",
                    "block_kind": "decl",
                    "purpose": "declare state",
                    "code_shape": "declarations",
                    "placeholder": "decl",
                },
                {
                    "block_id": seq_block,
                    "block_label": "update",
                    "block_kind": "seq",
                    "purpose": "update state",
                    "code_shape": "clocked update",
                    "placeholder": "update",
                },
            ],
            "module_behavior": {"control_style": "flag_driven"},
            "decision_ledger": {
                "chosen_decisions": [],
                "deferred_decisions": [],
                "structural_risks": [],
                "behavioral_risks": [],
            },
        }
    )


def test_stage3_5_detects_registered_same_edge_transfer():
    temporal = GlobalTemporalFactsArtifact.model_validate(
        {
            **_temporal_payload(Path("/tmp/toy.md")),
            "task_id": "toy",
        }
    )
    repo_payload = _repo_payload()
    repo_payload["top_module"] = "consumer"
    repo_payload["global_invariants"]["file_map"] = {
        "producer": "generate/rtl/producer.v",
        "consumer": "generate/rtl/consumer.v",
    }
    repo_payload["modules"] = [
        {**repo_payload["modules"][0], "module": "producer", "file_path": "generate/rtl/producer.v", "kind": "leaf_stateful"},
        {**repo_payload["modules"][0], "module": "consumer", "file_path": "generate/rtl/consumer.v"},
    ]
    repo_payload["planning_decisions"]["generation_order"] = ["producer", "consumer"]
    repo = Stage2RepoSkeletonArtifact.model_validate(repo_payload)
    architecture = ArchitectureTimingContractArtifact.model_validate(
        {
            "task_id": "toy",
            "module_set": ["producer", "consumer"],
            "module_assignments": [
                {"module": "producer", "owns_logical_state": ["state"]},
                {"module": "consumer"},
            ],
            "cross_module_transfers": [
                {
                    "id": "XFER_STATE",
                    "producer": "producer",
                    "consumer": "consumer",
                    "logical_object": "state",
                    "delivery": "REGISTERED",
                    "visible_at": "POST_EDGE",
                    "sampled_at": "PRE_EDGE",
                    "required_cycle_offset": 0,
                    "source_temporal_ids": ["PH_UPDATE"],
                }
            ],
            "module_obligations": [],
        }
    )
    bindings = {
        "producer": ModuleTimingBindingArtifact.model_validate(
            {
                "task_id": "toy",
                "module": "producer",
                "signal_bindings": [
                    {"logical_object": "state", "physical_signal": "state_out", "kind": "output"}
                ],
                "transfer_bindings": [
                    {
                        "transfer_id": "XFER_STATE",
                        "endpoint": "producer",
                        "physical_signal": "state_out",
                    }
                ],
            }
        ),
        "consumer": ModuleTimingBindingArtifact.model_validate(
            {
                "task_id": "toy",
                "module": "consumer",
                "signal_bindings": [
                    {"logical_object": "state", "physical_signal": "state_in", "kind": "input"}
                ],
                "transfer_bindings": [
                    {
                        "transfer_id": "XFER_STATE",
                        "endpoint": "consumer",
                        "physical_signal": "state_in",
                    }
                ],
            }
        ),
    }

    report = check_temporal_bindings(
        task_id="toy",
        temporal_facts=temporal,
        repo_skeleton=repo,
        architecture=architecture,
        skeletons={"producer": _skeleton("producer"), "consumer": _skeleton("consumer")},
        bindings=bindings,
    )

    assert report.status == "fail"
    assert any(item.code == "REGISTERED_VALUE_NOT_VISIBLE_AT_SAME_EDGE" for item in report.issues)


def test_stage3_5_warns_on_ambiguity_and_fails_on_missing_obligation():
    temporal_payload = _temporal_payload(Path("/tmp/toy.md"))
    temporal_payload["ambiguities"] = [
        {
            "id": "AMB_COUNT",
            "statement": "Cycle count uses two possible bases.",
            "alternatives": ["edge distance", "inclusive cycle count"],
        }
    ]
    temporal = GlobalTemporalFactsArtifact.model_validate(temporal_payload)
    repo = Stage2RepoSkeletonArtifact.model_validate(_repo_payload())
    architecture = ArchitectureTimingContractArtifact.model_validate(_architecture_payload())
    binding = ModuleTimingBindingArtifact.model_validate(
        {
            "task_id": "toy",
            "module": "toy",
            "signal_bindings": [
                {
                    "logical_object": "state",
                    "physical_signal": "state_reg",
                    "kind": "register",
                    "owner_block_id": "B1",
                    "logical_value_tags": ["State0", "State1"],
                }
            ],
            "block_obligations": [],
        }
    )

    report = check_temporal_bindings(
        task_id="toy",
        temporal_facts=temporal,
        repo_skeleton=repo,
        architecture=architecture,
        skeletons={"toy": _skeleton("toy")},
        bindings={"toy": binding},
    )

    assert report.status == "fail"
    assert any(item.code == "UNRESOLVED_TEMPORAL_AMBIGUITY" and item.severity == "WARNING" for item in report.issues)
    assert any(item.code == "MISSING_OBLIGATION_BINDING" and item.severity == "ERROR" for item in report.issues)


def test_stage3_5_allows_stage3_access_refinement_when_stage2_5_accesses_are_empty():
    temporal = GlobalTemporalFactsArtifact.model_validate(
        _temporal_payload(Path("/tmp/toy.md"))
    )
    repo = Stage2RepoSkeletonArtifact.model_validate(_repo_payload())
    architecture_payload = _architecture_payload()
    architecture_payload["module_obligations"][0]["reads"] = []
    architecture_payload["module_obligations"][0]["writes"] = []
    architecture_payload["module_obligations"][0]["combinational_outputs"] = []
    architecture = ArchitectureTimingContractArtifact.model_validate(architecture_payload)
    binding = ModuleTimingBindingArtifact.model_validate(
        {
            "task_id": "toy",
            "module": "toy",
            "signal_bindings": [
                {
                    "logical_object": "state",
                    "physical_signal": "state_reg",
                    "kind": "register",
                    "owner_block_id": "B1",
                    "logical_value_tags": ["State0", "State1"],
                }
            ],
            "block_obligations": [
                {
                    "obligation_id": "OBL_UPDATE",
                    "block_id": "B2",
                    "reads": [
                        {
                            "signal": "state_reg",
                            "at": "PRE_EDGE",
                            "logical_object": "state",
                            "logical_value_tag": "State0",
                        }
                    ],
                    "writes": [
                        {
                            "signal": "state_reg",
                            "at": "POST_EDGE",
                            "logical_object": "state",
                            "logical_value_tag": "State1",
                        }
                    ],
                }
            ],
        }
    )

    report = check_temporal_bindings(
        task_id="toy",
        temporal_facts=temporal,
        repo_skeleton=repo,
        architecture=architecture,
        skeletons={"toy": _skeleton("toy")},
        bindings={"toy": binding},
    )

    assert report.status == "warning"
    assert not any(
        item.code in {"OBLIGATION_ACCESS_MISMATCH", "MISSING_ARCHITECTURE_ACCESS"}
        for item in report.issues
    )


def test_stage3_5_only_requires_seq_block_for_post_edge_writes():
    temporal = GlobalTemporalFactsArtifact.model_validate(
        _temporal_payload(Path("/tmp/toy.md"))
    )
    repo = Stage2RepoSkeletonArtifact.model_validate(_repo_payload())
    architecture_payload = _architecture_payload()
    architecture_payload["module_obligations"][0]["reads"] = []
    architecture_payload["module_obligations"][0]["writes"] = []
    architecture_payload["module_obligations"][0]["combinational_outputs"] = []
    architecture = ArchitectureTimingContractArtifact.model_validate(architecture_payload)
    skeleton_payload = _skeleton("toy").model_dump()
    skeleton_payload["structural_blocks"][1]["block_kind"] = "comb"
    skeleton = ModuleSkeletonExport.model_validate(skeleton_payload)
    binding = ModuleTimingBindingArtifact.model_validate(
        {
            "task_id": "toy",
            "module": "toy",
            "signal_bindings": [
                {
                    "logical_object": "state",
                    "physical_signal": "state_next",
                    "kind": "wire",
                    "owner_block_id": "B2",
                    "logical_value_tags": ["State1"],
                }
            ],
            "block_obligations": [
                {
                    "obligation_id": "OBL_UPDATE",
                    "block_id": "B2",
                    "writes": [
                        {
                            "signal": "state_next",
                            "at": "COMB",
                            "logical_object": "state",
                            "logical_value_tag": "State1",
                        }
                    ],
                }
            ],
        }
    )

    report = check_temporal_bindings(
        task_id="toy",
        temporal_facts=temporal,
        repo_skeleton=repo,
        architecture=architecture,
        skeletons={"toy": skeleton},
        bindings={"toy": binding},
    )

    assert not any(
        item.code == "POST_EDGE_WRITE_REQUIRES_SEQ_BLOCK" for item in report.issues
    )


def test_stage3_5_reports_local_logical_object_refinement_as_warning():
    temporal = GlobalTemporalFactsArtifact.model_validate(
        _temporal_payload(Path("/tmp/toy.md"))
    )
    repo = Stage2RepoSkeletonArtifact.model_validate(_repo_payload())
    architecture_payload = _architecture_payload()
    architecture_payload["module_obligations"][0]["reads"] = []
    architecture_payload["module_obligations"][0]["writes"] = []
    architecture_payload["module_obligations"][0]["combinational_outputs"] = []
    architecture = ArchitectureTimingContractArtifact.model_validate(architecture_payload)
    binding = ModuleTimingBindingArtifact.model_validate(
        {
            "task_id": "toy",
            "module": "toy",
            "signal_bindings": [
                {
                    "logical_object": "local_counter",
                    "physical_signal": "counter_reg",
                    "kind": "register",
                    "owner_block_id": "B1",
                }
            ],
            "block_obligations": [
                {
                    "obligation_id": "OBL_UPDATE",
                    "block_id": "B2",
                    "reads": [
                        {
                            "signal": "counter_reg",
                            "at": "PRE_EDGE",
                            "logical_object": "local_counter",
                            "logical_value_tag": "",
                        }
                    ],
                }
            ],
        }
    )

    report = check_temporal_bindings(
        task_id="toy",
        temporal_facts=temporal,
        repo_skeleton=repo,
        architecture=architecture,
        skeletons={"toy": _skeleton("toy")},
        bindings={"toy": binding},
    )

    assert report.status == "warning"
    local_issues = [
        item for item in report.issues if item.code == "LOCAL_LOGICAL_OBJECT_REFINEMENT"
    ]
    assert len(local_issues) == 1
    assert local_issues[0].severity == "WARNING"


def test_runner_does_not_block_after_failed_timing_check(tmp_path):
    logger = Mock()
    runner = PlannerRunner(
        output_root=tmp_path / "outputs",
        llm_backend=QueueBackend([]),
        logger=logger,
    )
    report = TimingBindingCheckArtifact.model_validate(
        {
            "task_id": "toy",
            "status": "fail",
            "issues": [
                {
                    "code": "EXAMPLE_TIMING_CONFLICT",
                    "severity": "ERROR",
                    "message": "diagnostic only",
                }
            ],
        }
    )

    runner._report_timing_check(report)

    logger.warning.assert_called_once()
    assert "continuing to Stage4" in logger.warning.call_args.args[0]


def test_stage4_and_stage5_ignore_legacy_timing_bindings_and_emit_empty_compat_fields(tmp_path):
    from test_responsibility_refinement import scenario
    legacy={}
    def prepare(runner):
        for name in ("global_temporal_facts.json", "architecture_timing_contract.json", "module_timing_bindings.json"):
            path=runner.output_root/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text('{"legacy":"preserve"}')
            legacy[path]=path.read_bytes()
    _,runner,backend,_,_,stage4=scenario(tmp_path,end_stage="stage5",before_run=prepare)
    for record in stage4.module_plan_files:
        plan=json.loads((runner.output_root/record.plan_file).read_text())
        assert all(t["timing_obligation_ids"]==[] and t["logical_value_tags"]==[] for t in plan["subtasks"])
    for path,body in legacy.items(): assert path.read_bytes()==body
    assert not runner.temporal_planning_enabled
    prompts=[call["user_prompt"] for call in backend.calls if "[CURRENT_SUBTASK]" in call["user_prompt"]]
    assert prompts and all("[MODULE_TIMING_BINDING]" not in prompt for prompt in prompts)


def test_stage5_rejects_nonempty_legacy_timing_ids(tmp_path):
    task, _ = _task(tmp_path)
    subtask = ModulePlanSubtask.model_validate(
        {
            "id": "B5_seq_state_update",
            "target": "<block: seq_state_update>",
            "description": "Load or advance the key words.",
            "spec_refs": ["S005"],
            "timing_obligation_ids": ["OB_KE_START", "OB_KE_RK_SEQ"],
            "logical_value_tags": ["RK0", "RK1"],
        }
    )
    binding = ModuleTimingBindingArtifact.model_validate(
        {
            "task_id": "toy",
            "module": "key_expansion",
            "block_obligations": [
                {
                    "obligation_id": "OB_KE_START",
                    "block_id": "B5",
                    "reads": [
                        {
                            "signal": "key_in",
                            "at": "PRE_EDGE",
                            "logical_object": "cipher_key",
                            "logical_value_tag": "RK0",
                        }
                    ],
                    "writes": [
                        {
                            "signal": "round_key_reg",
                            "at": "POST_EDGE",
                            "logical_object": "round_key",
                            "logical_value_tag": "RK0",
                        }
                    ],
                },
                {
                    "obligation_id": "OB_KE_RK_SEQ",
                    "block_id": "B5",
                    "reads": [
                        {
                            "signal": "round_key_reg",
                            "at": "PRE_EDGE",
                            "logical_object": "round_key",
                            "logical_value_tag": "RK0",
                        }
                    ],
                    "writes": [
                        {
                            "signal": "round_key_reg",
                            "at": "POST_EDGE",
                            "logical_object": "round_key",
                            "logical_value_tag": "RK1",
                        }
                    ],
                    "combinational_outputs": [
                        {
                            "signal": "next_round_key",
                            "at": "COMB",
                            "logical_object": "round_key",
                            "logical_value_tag": "RK1",
                        }
                    ],
                },
            ],
        }
    )
    artifact = SubtaskCodeArtifact.model_validate(
        {
            "task_id": "toy",
            "module": "key_expansion",
            "subtask_id": "B5_seq_state_update",
            "target": "<block: seq_state_update>",
            "spec_refs": ["S005"],
            "timing_obligation_ids": ["OB_KE_START", "OB_KE_RK_SEQ"],
            "code": (
                "always @(posedge clk) begin\n"
                "  if (kld) begin\n"
                "    W0 <= key[127:96];\n"
                "  end else begin\n"
                "    W0 <= W0_next;\n"
                "  end\n"
                "end"
            ),
            "contract": {
                "writes": ["W0"],
                "reads": ["clk", "kld", "key", "W0_next"],
                "clocking": "posedge clk",
                "reset_behavior": "none",
                "hold_behavior": "updated each active edge",
                "latency": "one-cycle",
                "assumptions": [],
            },
        }
    )
    agent = Stage5Agent(
        PlannerLLMClient(backend=QueueBackend([])),
        output_root=tmp_path / "outputs",
        workspace_root=tmp_path / "workspace",
    )

    errors = agent._validate_subtask_code(
        artifact,
        task,
        "key_expansion",
        subtask,
    )

    assert errors == ["timing_obligation_ids compatibility field must be empty"]


def test_stage5_no_longer_runs_temporal_clocking_diagnostics(tmp_path):
    task, _ = _task(tmp_path)
    subtask = ModulePlanSubtask.model_validate(
        {
            "id": "B2_comb",
            "target": "<block: comb>",
            "description": "Produce a combinational result.",
            "spec_refs": ["S001"],
            "timing_obligation_ids": ["OB_COMB"],
        }
    )
    binding = ModuleTimingBindingArtifact.model_validate(
        {
            "task_id": "toy",
            "module": "toy",
            "block_obligations": [
                {
                    "obligation_id": "OB_COMB",
                    "block_id": "B2",
                    "combinational_outputs": [
                        {
                            "signal": "result_next",
                            "at": "COMB",
                            "logical_object": "state",
                            "logical_value_tag": "State1",
                        }
                    ],
                }
            ],
        }
    )
    artifact = SubtaskCodeArtifact.model_validate(
        {
            "task_id": "toy",
            "module": "toy",
            "subtask_id": "B2_comb",
            "target": "<block: comb>",
            "spec_refs": ["S001"],
            "timing_obligation_ids": ["OB_COMB"],
            "code": "always @(posedge clk) result <= source;",
            "contract": {
                "writes": ["result"],
                "reads": ["source"],
                "clocking": "posedge clk",
                "reset_behavior": "none",
                "hold_behavior": "holds between edges",
                "latency": "one-cycle",
                "assumptions": [],
            },
        }
    )
    agent = Stage5Agent(
        PlannerLLMClient(backend=QueueBackend([])),
        output_root=tmp_path / "outputs",
        workspace_root=tmp_path / "workspace",
    )

    errors = agent._validate_subtask_code(
        artifact,
        task,
        "toy",
        subtask,
    )

    assert errors == ["timing_obligation_ids compatibility field must be empty"]
