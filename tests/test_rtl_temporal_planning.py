from __future__ import annotations

import json
from pathlib import Path
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

    def complete_with_memory(self, *, memory, images=None):
        user_prompt = next((item.content for item in reversed(memory.history) if item.role == "user"), "")
        self.calls.append({"user_prompt": user_prompt, "images": list(images or [])})
        if not self.responses:
            raise AssertionError("No more queued responses.")
        return self.responses.pop(0)


def _task(tmp_path: Path) -> tuple[PlannerTaskInput, Path]:
    spec = tmp_path / "toy.md"
    spec.write_text(
        "\n".join(
            [
                "# Toy",
                "On rise(ld), load State0.",
                "One cycle later, produce State1 and pulse done.",
            ]
        ),
        encoding="utf-8",
    )
    return PlannerTaskInput(task_id="toy", spec_md_files=[str(spec)]), spec.resolve()


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
            "file_map": {"toy": "rtl/toy.v"},
            "cross_module_alignment": [],
            "global_data_conventions": [],
        },
        "modules": [
            {
                "module": "toy",
                "file_path": "rtl/toy.v",
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


def test_planner_runner_temporal_planning_is_enabled_by_default(tmp_path):
    task, spec_path = _task(tmp_path)
    backend = QueueBackend([_temporal_payload(spec_path)])
    output_root = tmp_path / "outputs"
    runner = PlannerRunner(output_root=output_root, llm_backend=backend)

    artifact = runner.run(task, end_stage="stage1")

    assert runner.temporal_planning_enabled is True
    assert isinstance(artifact, GlobalTemporalFactsArtifact)
    assert artifact.events[0].id == "EV_LD"
    assert (output_root / "global_temporal_facts.json").exists()
    assert (output_root / "contracts.json").exists()
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
        "producer": "rtl/producer.v",
        "consumer": "rtl/consumer.v",
    }
    repo_payload["modules"] = [
        {
            **repo_payload["modules"][0],
            "module": "producer",
            "file_path": "rtl/producer.v",
            "kind": "leaf_stateful",
        },
        {**repo_payload["modules"][0], "module": "consumer", "file_path": "rtl/consumer.v"},
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


def test_stage1_temporal_failure_degrades_and_resume_reuses_artifact(tmp_path):
    task, _ = _task(tmp_path)
    output_root = tmp_path / "outputs"
    runner = PlannerRunner(
        output_root=output_root,
        llm_backend=QueueBackend(["not json", "still not json"]),
    )

    artifact = runner.run(task, end_stage="stage1")

    assert artifact.planning_status == "degraded"
    assert artifact.events == []
    assert artifact.degradation_reasons

    resume_backend = QueueBackend([])
    resumed = PlannerRunner(output_root=output_root, llm_backend=resume_backend).run(
        task,
        resume=True,
        end_stage="stage1",
    )
    assert resumed.planning_status == "degraded"
    assert resume_backend.calls == []


def test_stage1_temporal_failure_remains_fatal_in_strict_mode(tmp_path):
    task, _ = _task(tmp_path)
    runner = PlannerRunner(
        output_root=tmp_path / "outputs",
        llm_backend=QueueBackend(["not json", "still not json"]),
        temporal_failure_policy="strict",
    )

    with pytest.raises(ValueError, match="failed parse"):
        runner.run(task, end_stage="stage1")


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


def test_stage2_completion_writes_architecture_timing_sidecar(tmp_path):
    task, spec_path = _task(tmp_path)
    backend = QueueBackend([_temporal_payload(spec_path), _repo_payload(), _architecture_payload()])
    output_root = tmp_path / "outputs"
    runner = PlannerRunner(output_root=output_root, llm_backend=backend)

    artifact = runner.run(task, end_stage="stage2")

    assert isinstance(artifact, Stage2RepoSkeletonArtifact)
    assert (output_root / "architecture_timing_contract.json").exists()
    assert len(backend.calls) == 3
    assert "do not create one module per phase" in backend.calls[1]["user_prompt"].lower()

    resume_backend = QueueBackend([])
    resumed = PlannerRunner(output_root=output_root, llm_backend=resume_backend).run(
        task,
        resume=True,
        end_stage="stage2",
    )
    assert isinstance(resumed, Stage2RepoSkeletonArtifact)
    assert resume_backend.calls == []

    spec_path.write_text(spec_path.read_text(encoding="utf-8") + "\nAdditional timing clarification.", encoding="utf-8")
    changed_backend = QueueBackend(
        [_temporal_payload(spec_path), _repo_payload(), _architecture_payload()]
    )
    PlannerRunner(output_root=output_root, llm_backend=changed_backend).run(
        task,
        resume=True,
        end_stage="stage2",
    )
    assert len(changed_backend.calls) == 3


def test_stage2_temporal_quality_failure_writes_safe_degraded_contract(tmp_path):
    task, spec_path = _task(tmp_path)
    invalid_architecture = _architecture_payload()
    invalid_architecture["module_obligations"][0]["reads"] = [
        {"logical_object": "undeclared_payload", "logical_value_tag": "", "at": "PRE_EDGE"}
    ]
    backend = QueueBackend(
        [
            _temporal_payload(spec_path),
            _repo_payload(),
            json.loads(json.dumps(invalid_architecture)),
            json.loads(json.dumps(invalid_architecture)),
        ]
    )
    output_root = tmp_path / "outputs"
    runner = PlannerRunner(output_root=output_root, llm_backend=backend)

    runner.run(task, end_stage="stage2")

    saved = ArchitectureTimingContractArtifact.model_validate(
        json.loads((output_root / "architecture_timing_contract.json").read_text(encoding="utf-8"))
    )
    assert saved.planning_status == "degraded"
    assert saved.module_set == ["toy"]
    assert [item.module for item in saved.module_assignments] == ["toy"]
    assert saved.cross_module_transfers == []
    assert saved.module_obligations == []
    assert len(backend.calls) == 4


def test_degraded_architecture_skips_stage3_timing_llm(tmp_path):
    task, spec_path = _task(tmp_path)
    output_root = tmp_path / "outputs"
    export_path = output_root / "module_skeleton_json" / "toy.json"
    export_path.parent.mkdir(parents=True)
    export_path.write_text(json.dumps(_skeleton("toy").model_dump()), encoding="utf-8")
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
                    "doc_file": "module_skeleton_docs/toy.md",
                    "export_file": "module_skeleton_json/toy.json",
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
        llm_backend=QueueBackend([]),
        temporal_planning_enabled=False,
    )

    artifact = runner.run(task, end_stage="stage1")

    assert artifact.schema_version == "stage1_contracts_v1"
    assert not (tmp_path / "outputs" / "global_temporal_facts.json").exists()


def _skeleton(module: str, seq_block: str = "B2") -> ModuleSkeletonExport:
    return ModuleSkeletonExport.model_validate(
        {
            "module": module,
            "file_path": f"rtl/{module}.v",
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
        "producer": "rtl/producer.v",
        "consumer": "rtl/consumer.v",
    }
    repo_payload["modules"] = [
        {**repo_payload["modules"][0], "module": "producer", "file_path": "rtl/producer.v", "kind": "leaf_stateful"},
        {**repo_payload["modules"][0], "module": "consumer", "file_path": "rtl/consumer.v"},
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


def test_stage4_and_stage5_propagate_timing_obligation_ids(tmp_path):
    task, _ = _task(tmp_path)
    output_root = tmp_path / "outputs"
    (output_root / "module_skeleton_docs").mkdir(parents=True)
    (output_root / "module_skeleton_json").mkdir(parents=True)
    (output_root / "module_timing_binding_json").mkdir(parents=True)
    skeleton_doc = "\n".join(
        [
            "# MODULE_SKELETON_DOC v1",
            "## 1. Module Frame",
            "```verilog",
            "// <block: update>",
            "```",
            "## 2. Structural Skeleton",
            "### Block",
            "- block_id: B2",
            "- block_label: update",
            "- block_kind: seq",
        ]
    )
    (output_root / "module_skeleton_docs" / "toy.md").write_text(skeleton_doc, encoding="utf-8")
    (output_root / "module_skeleton_json" / "toy.json").write_text(
        json.dumps(_skeleton("toy").model_dump()),
        encoding="utf-8",
    )
    binding = {
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
    (output_root / "module_timing_binding_json" / "toy.json").write_text(
        json.dumps(binding),
        encoding="utf-8",
    )
    stage3 = {
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
                "doc_file": "module_skeleton_docs/toy.md",
                "export_file": "module_skeleton_json/toy.json",
                "source_refs": {
                    "module_contract_ref": "modules::toy",
                    "repo_skeleton_ref": "repo::toy",
                    "module_spec_file": "toy.md",
                },
                "block_ids": ["B2"],
            }
        ],
    }
    spec_blocks = {
        "task_id": "toy",
        "module_order": ["toy"],
        "modules": [
            {
                "module": "toy",
                "source_spec_file": "toy.md",
                "blocks": [
                    {"block_id": "S001", "text": "Interface: input clk and state update."}
                ],
            }
        ],
    }
    timing_manifest = {
        "task_id": "toy",
        "module_order": ["toy"],
        "status": "planned",
        "completed_modules": ["toy"],
        "resume_cursor": 1,
        "module_binding_files": [
            {"module": "toy", "binding_file": "module_timing_binding_json/toy.json"}
        ],
    }
    retrieval = {
        "schema_version": "block_spec_retrieval_v1",
        "module": "toy",
        "selections": [
            {
                "id": "B2_update",
                "target": "<block: update>",
                "spec_refs": ["S001"],
                "selection_reason": ["Update behavior."],
            }
        ],
        "fallback_used": False,
        "fallback_reason": "",
    }
    plan = {
        "module": "toy",
        "subtasks": [
            {
                "id": "B2_update",
                "target": "<block: update>",
                "description": "Implement the registered state update.",
                "spec_refs": ["S001"],
                "constraints": [],
                "timing_obligation_ids": ["OBL_UPDATE"],
                "logical_value_tags": ["State0", "State1"],
            }
        ],
    }
    stage4_backend = QueueBackend([retrieval, plan])
    stage4_agent = Stage4ModulePlanAgent(
        PlannerLLMClient(backend=stage4_backend),
        output_root=output_root,
    )
    stage4 = stage4_agent.run_incremental(
        task,
        {"stage3": stage3, "spec_blocks": spec_blocks, "timing_bindings": timing_manifest},
        persist_callback=lambda payload: (
            (output_root / payload["plan_file"]).parent.mkdir(parents=True, exist_ok=True),
            (output_root / payload["plan_file"]).write_text(json.dumps(payload["plan_payload"]), encoding="utf-8"),
        )
        if payload.get("module")
        else None,
    )
    assert '"timing_obligation_ids"' in stage4_backend.calls[1]["user_prompt"]

    stage5_response = {
        "task_id": "toy",
        "module": "toy",
        "subtask_id": "B2_update",
        "target": "<block: update>",
        "spec_refs": ["S001"],
        "timing_obligation_ids": ["OBL_UPDATE"],
        "code": "always @(posedge clk) begin\n  state_reg <= state_reg;\nend",
        "contract": {
            "writes": ["state_reg"],
            "reads": ["state_reg"],
            "clocking": "posedge clk",
            "reset_behavior": "none",
            "hold_behavior": "holds outside update",
            "latency": "one-cycle",
            "assumptions": [],
        },
    }
    stage5_backend = QueueBackend([stage5_response])
    stage5_agent = Stage5Agent(
        PlannerLLMClient(backend=stage5_backend),
        output_root=output_root,
        workspace_root=tmp_path / "workspace",
    )
    stage5_agent.run_incremental(
        task,
        {
            "stage4": stage4,
            "spec_blocks": spec_blocks,
            "timing_bindings": timing_manifest,
        },
    )

    assert "OBL_UPDATE" in stage5_backend.calls[0]["user_prompt"]
    contracts = json.loads(
        (tmp_path / "workspace" / "fragments" / "toy_contracts.json").read_text(encoding="utf-8")
    )
    assert contracts["contracts"][0]["timing_obligation_ids"] == ["OBL_UPDATE"]


def test_stage5_allows_actual_signal_names_and_mixed_comb_clocked_obligation(tmp_path):
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
        binding.block_obligations,
    )

    assert errors == []


def test_stage5_keeps_pure_comb_registered_clocking_as_nonfatal_diagnostic(tmp_path):
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
        binding.block_obligations,
    )

    assert errors == ["OB_COMB: pure combinational obligation uses registered clocking"]
    assert agent._is_nonfatal_timing_diagnostic(errors[0])
    assert not agent._is_nonfatal_timing_diagnostic(
        "timing_obligation_ids must equal ['OB_COMB']"
    )
