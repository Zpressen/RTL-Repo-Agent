from __future__ import annotations

from typing import Any, Dict, List, Optional, Type

from pydantic import BaseModel

from ..prompts import stage2_temporal_contract
from ..schemas import (
    ArchitectureTimingContractArtifact,
    GlobalTemporalFactsArtifact,
    PlannerTaskInput,
    Stage2RepoSkeletonArtifact,
)
from ..utils import repair_json_payload
from .base import BaseStageAgent, model_dump, validate_model


class Stage2TemporalContractAgent(BaseStageAgent):
    stage_name = "stage2_5_architecture_timing"
    output_model = ArchitectureTimingContractArtifact
    system_role = stage2_temporal_contract.SYSTEM_ROLE
    max_parse_attempts = 2
    max_quality_attempts = 2
    allow_best_effort_quality_fallback = False

    def build_prompt(
        self,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        stage_context: Dict[str, Any],
    ) -> tuple[str, List[str]]:
        temporal = self._get_temporal(partial_artifacts)
        repo = self._get_repo(partial_artifacts)
        global_logical_objects = sorted(
            {
                *(item.object for item in temporal.logical_value_sequences),
                *(item.logical_object for item in temporal.invariants if item.logical_object),
            }
        )
        return (
            stage2_temporal_contract.build_prompt(
                task_id=task_input.task_id,
                temporal_facts_json=self.to_pretty_json(temporal),
                repo_skeleton_json=self.to_pretty_json(repo),
                global_logical_objects_json=self.to_pretty_json(global_logical_objects),
                stage_context=self.to_pretty_json(stage_context),
            ),
            [],
        )

    def _coerce_output(
        self,
        raw: Any,
        output_model: Optional[Type[BaseModel]] = None,
    ) -> BaseModel:
        payload = model_dump(raw) if isinstance(raw, BaseModel) else repair_json_payload(raw)
        repairs: List[str] = []
        if isinstance(payload, dict):
            assignments = payload.get("module_assignments")
            if isinstance(assignments, dict):
                normalized_assignments = []
                for module, assignment in assignments.items():
                    if isinstance(assignment, dict):
                        assignment = dict(assignment)
                        assignment.setdefault("module", module)
                    normalized_assignments.append(assignment)
                payload["module_assignments"] = normalized_assignments
                repairs.append("module_assignments mapping -> list")

            for assignment in payload.get("module_assignments") or []:
                if not isinstance(assignment, dict):
                    continue
                if "owns_logical_objects" in assignment:
                    assignment.setdefault("owns_logical_state", assignment["owns_logical_objects"])
                    assignment.pop("owns_logical_objects", None)
                    repairs.append("owns_logical_objects -> owns_logical_state")

            for transfer in payload.get("cross_module_transfers") or []:
                if not isinstance(transfer, dict):
                    continue
                for legacy, canonical in (
                    ("source_module", "producer"),
                    ("dest_module", "consumer"),
                    ("cycle_offset", "required_cycle_offset"),
                ):
                    if legacy in transfer:
                        transfer.setdefault(canonical, transfer[legacy])
                        transfer.pop(legacy, None)
                        repairs.append(f"{legacy} -> {canonical}")

        if repairs:
            self.logger.warning(
                "[%s] Applied deterministic compatibility repairs: %s",
                self.stage_name,
                sorted(set(repairs)),
            )
        return validate_model(output_model or self.output_model, payload)

    def validate_quality(
        self,
        artifact: ArchitectureTimingContractArtifact,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
    ) -> List[str]:
        temporal = self._get_temporal(partial_artifacts)
        repo = self._get_repo(partial_artifacts)
        expected_modules = list(repo.planning_decisions.generation_order) or [item.module for item in repo.modules]
        errors: List[str] = []
        if artifact.schema_version != "architecture_timing_contract_v1":
            errors.append("schema_version must remain architecture_timing_contract_v1")
        if artifact.task_id != task_input.task_id:
            errors.append(f"task_id must remain {task_input.task_id}")
        if artifact.module_set != expected_modules:
            errors.append(f"module_set must exactly match repository generation order {expected_modules}")

        event_ids = {item.id for item in temporal.events}
        phase_ids = {item.id for item in temporal.phases}
        temporal_ids = {
            *(item.id for item in temporal.events),
            *(item.id for item in temporal.phases),
            *(item.id for item in temporal.latency_constraints),
            *(item.id for item in temporal.relations),
            *(item.id for item in temporal.invariants),
            *(item.id for item in temporal.ambiguities),
            *(item.id for item in temporal.unsupported_features),
        }
        global_logical_objects = {
            *(item.object for item in temporal.logical_value_sequences),
            *(item.logical_object for item in temporal.invariants if item.logical_object),
        }
        redundant_declarations = sorted(
            global_logical_objects.intersection(artifact.architecture_logical_objects)
        )
        if redundant_declarations:
            errors.append(
                "architecture_logical_objects repeats globally declared names "
                f"{redundant_declarations}; remove the duplicates"
            )
        logical_objects = global_logical_objects | set(artifact.architecture_logical_objects)
        logical_tags = {tag for item in temporal.logical_value_sequences for tag in item.tags}

        for assignment in artifact.module_assignments:
            unknown_state = [item for item in assignment.owns_logical_state if item not in logical_objects]
            unknown_events = [item for item in assignment.handles_event_ids if item not in event_ids]
            unknown_phases = [item for item in assignment.handles_phase_ids if item not in phase_ids]
            if unknown_state:
                errors.append(
                    f"{assignment.module}: unknown logical state {unknown_state}; declare justified "
                    "names in architecture_logical_objects or remove the references"
                )
            if unknown_events:
                errors.append(f"{assignment.module}: unknown event IDs {unknown_events}")
            if unknown_phases:
                errors.append(f"{assignment.module}: unknown phase IDs {unknown_phases}")
        for transfer in artifact.cross_module_transfers:
            if transfer.logical_object not in logical_objects:
                errors.append(
                    f"{transfer.id}: unknown logical object `{transfer.logical_object}`; declare it in "
                    "architecture_logical_objects when justified by the fixed repository, or remove the transfer"
                )
            unknown_sources = [item for item in transfer.source_temporal_ids if item not in temporal_ids]
            if unknown_sources:
                errors.append(f"{transfer.id}: unknown source temporal IDs {unknown_sources}")
        for obligation in artifact.module_obligations:
            if obligation.event_id and obligation.event_id not in event_ids:
                errors.append(f"{obligation.id}: unknown event ID `{obligation.event_id}`")
            if obligation.phase_id and obligation.phase_id not in phase_ids:
                errors.append(f"{obligation.id}: unknown phase ID `{obligation.phase_id}`")
            unknown_sources = [item for item in obligation.source_temporal_ids if item not in temporal_ids]
            if unknown_sources:
                errors.append(f"{obligation.id}: unknown source temporal IDs {unknown_sources}")
            for access in [*obligation.reads, *obligation.writes, *obligation.combinational_outputs]:
                if access.logical_object not in logical_objects:
                    errors.append(
                        f"{obligation.id}: unknown logical object `{access.logical_object}`; declare it in "
                        "architecture_logical_objects when justified, or remove the access"
                    )
                if access.logical_value_tag and access.logical_value_tag not in logical_tags:
                    errors.append(f"{obligation.id}: unknown logical value tag `{access.logical_value_tag}`")
        return errors

    def _get_temporal(self, partial_artifacts: Dict[str, Any]) -> GlobalTemporalFactsArtifact:
        candidate = partial_artifacts.get("temporal_facts")
        if candidate is None:
            raise ValueError("Stage2.5 requires partial_artifacts['temporal_facts']")
        if isinstance(candidate, GlobalTemporalFactsArtifact):
            return candidate
        return validate_model(GlobalTemporalFactsArtifact, candidate)

    def _get_repo(self, partial_artifacts: Dict[str, Any]) -> Stage2RepoSkeletonArtifact:
        candidate = partial_artifacts.get("stage2") or partial_artifacts.get("repo_skeleton")
        if candidate is None:
            raise ValueError("Stage2.5 requires partial_artifacts['stage2']")
        if isinstance(candidate, Stage2RepoSkeletonArtifact):
            return candidate
        return validate_model(Stage2RepoSkeletonArtifact, candidate)
