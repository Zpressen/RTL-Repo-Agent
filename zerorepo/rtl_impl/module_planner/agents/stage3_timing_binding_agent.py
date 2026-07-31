from __future__ import annotations

from typing import Any, Dict, List

from ..prompts import stage3_timing_binding
from ..schemas import (
    ArchitectureTimingContractArtifact,
    GlobalTemporalFactsArtifact,
    ModuleSkeletonExport,
    ModuleTimingBindingArtifact,
    PlannerTaskInput,
)
from .base import BaseStageAgent, model_dump, validate_model


class Stage3TimingBindingAgent(BaseStageAgent):
    stage_name = "stage3_timing_binding"
    output_model = ModuleTimingBindingArtifact
    system_role = stage3_timing_binding.SYSTEM_ROLE
    max_parse_attempts = 2
    max_quality_attempts = 2
    allow_best_effort_quality_fallback = False

    def build_prompt(
        self,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        stage_context: Dict[str, Any],
    ) -> tuple[str, List[str]]:
        module_name = str(partial_artifacts.get("module_name") or "").strip()
        if not module_name:
            raise ValueError("Stage3 timing binding requires partial_artifacts['module_name']")
        temporal = self._get_temporal(partial_artifacts)
        architecture = self._get_architecture(partial_artifacts)
        skeleton = self._get_skeleton(partial_artifacts)
        spec_context = partial_artifacts.get("module_spec_context") or {}
        architecture_slice = {
            "module_assignment": next(
                (model_dump(item) for item in architecture.module_assignments if item.module == module_name),
                None,
            ),
            "cross_module_transfers": [
                model_dump(item)
                for item in architecture.cross_module_transfers
                if item.producer == module_name or item.consumer == module_name
            ],
            "module_obligations": [
                model_dump(item) for item in architecture.module_obligations if item.module == module_name
            ],
            "assumptions": list(architecture.assumptions),
        }
        return (
            stage3_timing_binding.build_prompt(
                task_id=task_input.task_id,
                module_name=module_name,
                temporal_facts_json=self.to_pretty_json(temporal),
                architecture_slice_json=self.to_pretty_json(architecture_slice),
                module_skeleton_json=self.to_pretty_json(skeleton),
                module_spec_context_json=self.to_pretty_json(spec_context),
                stage_context=self.to_pretty_json(stage_context),
            ),
            [],
        )

    def validate_quality(
        self,
        artifact: ModuleTimingBindingArtifact,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
    ) -> List[str]:
        module_name = str(partial_artifacts.get("module_name") or "").strip()
        architecture = self._get_architecture(partial_artifacts)
        skeleton = self._get_skeleton(partial_artifacts)
        errors: List[str] = []
        if artifact.schema_version != "module_timing_binding_v1":
            errors.append("schema_version must remain module_timing_binding_v1")
        if artifact.task_id != task_input.task_id:
            errors.append(f"task_id must remain {task_input.task_id}")
        if artifact.module != module_name:
            errors.append(f"module must remain {module_name}")

        block_ids = {item.block_id for item in skeleton.structural_blocks}
        expected_obligations = [
            item.id for item in architecture.module_obligations if item.module == module_name
        ]
        actual_obligations = [item.obligation_id for item in artifact.block_obligations]
        if actual_obligations != expected_obligations:
            errors.append(
                f"block_obligations must exactly follow architecture obligation order {expected_obligations}"
            )
        for binding in artifact.block_obligations:
            if binding.block_id not in block_ids:
                errors.append(f"{binding.obligation_id}: unknown block_id `{binding.block_id}`")
        for signal in artifact.signal_bindings:
            if signal.owner_block_id and signal.owner_block_id not in block_ids:
                errors.append(f"{signal.physical_signal}: unknown owner block `{signal.owner_block_id}`")

        expected_transfer_endpoints = []
        for transfer in architecture.cross_module_transfers:
            if transfer.producer == module_name:
                expected_transfer_endpoints.append((transfer.id, "producer"))
            if transfer.consumer == module_name:
                expected_transfer_endpoints.append((transfer.id, "consumer"))
        actual_transfer_endpoints = [
            (item.transfer_id, item.endpoint) for item in artifact.transfer_bindings
        ]
        if actual_transfer_endpoints != expected_transfer_endpoints:
            errors.append(
                f"transfer_bindings must exactly follow related transfer endpoints {expected_transfer_endpoints}"
            )
        for endpoint in artifact.transfer_bindings:
            if endpoint.block_id and endpoint.block_id not in block_ids:
                errors.append(f"{endpoint.transfer_id}: unknown endpoint block `{endpoint.block_id}`")
        return errors

    def _get_temporal(self, partial_artifacts: Dict[str, Any]) -> GlobalTemporalFactsArtifact:
        candidate = partial_artifacts.get("temporal_facts")
        if isinstance(candidate, GlobalTemporalFactsArtifact):
            return candidate
        return validate_model(GlobalTemporalFactsArtifact, candidate)

    def _get_architecture(self, partial_artifacts: Dict[str, Any]) -> ArchitectureTimingContractArtifact:
        candidate = partial_artifacts.get("architecture_timing")
        if isinstance(candidate, ArchitectureTimingContractArtifact):
            return candidate
        return validate_model(ArchitectureTimingContractArtifact, candidate)

    def _get_skeleton(self, partial_artifacts: Dict[str, Any]) -> ModuleSkeletonExport:
        candidate = partial_artifacts.get("module_skeleton_export")
        if isinstance(candidate, ModuleSkeletonExport):
            return candidate
        return validate_model(ModuleSkeletonExport, candidate)
