from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field

from ..prompts import stage1_ingest_extract
from ..schemas import (
    ControlContract,
    DatapathContract,
    InterfaceContract,
    PlanningFactsContract,
    PlannerTaskInput,
    Stage1ContractsArtifact,
    StructureContract,
    TimingContract,
)
from ..utils import (
    format_documents_for_prompt,
    load_markdown_files,
)
from .base import BaseStageAgent, model_dump, validate_model


class _StructureRoundPayload(BaseModel):
    structure_contract: StructureContract = Field(default_factory=StructureContract)


class _InterfaceRoundPayload(BaseModel):
    interface_contracts: List[InterfaceContract] = Field(default_factory=list)


class _TimingRoundPayload(BaseModel):
    timing_contracts: List[TimingContract] = Field(default_factory=list)


class _ControlRoundPayload(BaseModel):
    control_contracts: List[ControlContract] = Field(default_factory=list)


class _DatapathRoundPayload(BaseModel):
    datapath_contracts: List[DatapathContract] = Field(default_factory=list)


class _PlanningFactsRoundPayload(BaseModel):
    planning_facts: List[PlanningFactsContract] = Field(default_factory=list)


class Stage1Agent(BaseStageAgent):
    stage_name = "stage1_contracts"
    output_model = Stage1ContractsArtifact
    system_role = stage1_ingest_extract.SYSTEM_ROLE

    _ROUND_SEQUENCE = [
        "structure",
        "interface",
        "timing",
        "control",
        "datapath",
        "planning_facts",
    ]

    _ROUND_OUTPUT_MODELS = {
        "structure": _StructureRoundPayload,
        "interface": _InterfaceRoundPayload,
        "timing": _TimingRoundPayload,
        "control": _ControlRoundPayload,
        "datapath": _DatapathRoundPayload,
        "planning_facts": _PlanningFactsRoundPayload,
    }

    _ROUND_SYSTEM_ROLES = {
        "structure": stage1_ingest_extract.STRUCTURE_SYSTEM_ROLE,
        "interface": stage1_ingest_extract.INTERFACE_SYSTEM_ROLE,
        "timing": stage1_ingest_extract.TIMING_SYSTEM_ROLE,
        "control": stage1_ingest_extract.CONTROL_SYSTEM_ROLE,
        "datapath": stage1_ingest_extract.DATAPATH_SYSTEM_ROLE,
        "planning_facts": stage1_ingest_extract.PLANNING_FACTS_SYSTEM_ROLE,
    }

    def run(self, task_input: Any, partial_artifacts: Dict[str, Any]) -> Stage1ContractsArtifact:
        return self.run_incremental(task_input, partial_artifacts)

    def run_incremental(
        self,
        task_input: Any,
        partial_artifacts: Dict[str, Any],
        persist_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Stage1ContractsArtifact:
        self._last_quality_errors = []
        task = task_input if isinstance(task_input, PlannerTaskInput) else validate_model(PlannerTaskInput, task_input)
        stage_context = self.context_provider.get_stage_context(self.stage_name, task, partial_artifacts)
        self._prepare_inputs(task)

        artifact = self._bootstrap_artifact(task, partial_artifacts.get("stage1"))

        for round_name in self._ROUND_SEQUENCE:
            if round_name in artifact.completed_rounds:
                continue
            payload = self._run_round(
                round_name=round_name,
                task_input=task,
                partial_artifacts=partial_artifacts,
                stage_context=stage_context,
                artifact=artifact,
            )
            artifact = self._merge_round_payload(artifact, round_name, payload)
            artifact.completed_rounds = list(dict.fromkeys(list(artifact.completed_rounds) + [round_name]))
            artifact.stage1_status = f"{round_name}_completed"
            if persist_callback is not None:
                persist_callback(model_dump(artifact))

        artifact.stage1_status = "contracts_completed"
        errors = self.validate_quality(artifact, task, partial_artifacts)
        if errors:
            raise ValueError(f"{self.stage_name} output failed quality checks after synthesis: {errors}")
        if persist_callback is not None:
            persist_callback(model_dump(artifact))

        self._log_stage_output(artifact)
        self.artifact_sink.record_stage_output(self.stage_name, artifact, task)
        return artifact

    def build_prompt(
        self,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        stage_context: Dict[str, Any],
    ) -> tuple[str, List[str]]:
        raise NotImplementedError("Stage1Agent uses a custom multi-round contract extraction flow.")

    def validate_quality(
        self,
        artifact: Stage1ContractsArtifact,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
    ) -> List[str]:
        errors: List[str] = []
        if artifact.task_id != task_input.task_id:
            errors.append(f"task_id must remain {task_input.task_id}")
        if artifact.schema_version != "stage1_contracts_v1":
            errors.append("schema_version must remain stage1_contracts_v1")
        expected_prefix = self._ROUND_SEQUENCE[: len(artifact.completed_rounds)]
        if artifact.completed_rounds != expected_prefix:
            errors.append(f"completed_rounds must preserve round order: expected prefix {expected_prefix}, got {artifact.completed_rounds}")
        # Persisted contracts.json is compact and omits text_grounding. Keep the
        # final artifact validation compatible with that representation while
        # still enforcing grounding during each extraction round.
        errors.extend(self._validate_interface_contracts(artifact.interface_contracts, require_grounding=False))
        errors.extend(self._validate_timing_contracts(artifact.timing_contracts, require_grounding=False))
        errors.extend(self._validate_unique_modules(artifact.control_contracts, "control_contracts", require_grounding=False))
        errors.extend(self._validate_unique_modules(artifact.datapath_contracts, "datapath_contracts", require_grounding=False))
        errors.extend(self._validate_planning_facts(artifact.planning_facts, require_grounding=False))
        errors.extend(self._validate_structure_contract(artifact.structure_contract, require_grounding=False))
        return errors

    def _prepare_inputs(self, task_input: PlannerTaskInput) -> None:
        self._documents = load_markdown_files(task_input.spec_md_files)
        self._formatted_documents = format_documents_for_prompt(self._documents)

    def _bootstrap_artifact(self, task: PlannerTaskInput, existing: Any) -> Stage1ContractsArtifact:
        if existing is None:
            return validate_model(Stage1ContractsArtifact, {"task_id": task.task_id})
        if isinstance(existing, Stage1ContractsArtifact):
            artifact = existing
        else:
            artifact = validate_model(Stage1ContractsArtifact, existing)
        artifact.completed_rounds = [round_name for round_name in artifact.completed_rounds if round_name in self._ROUND_SEQUENCE]
        return artifact

    def _run_round(
        self,
        *,
        round_name: str,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        stage_context: Dict[str, Any],
        artifact: Stage1ContractsArtifact,
    ) -> BaseModel:
        prompt, images = self._build_round_prompt(round_name, artifact, stage_context)
        original_role = self.system_role
        self.system_role = self._ROUND_SYSTEM_ROLES[round_name]
        self._log_stage_input(prompt=prompt, images=images, stage_context={**stage_context, "round": round_name})
        payload = self._invoke_with_repair(
            prompt,
            images,
            task_input,
            partial_artifacts,
            output_model=self._ROUND_OUTPUT_MODELS[round_name],
            quality_validator=lambda candidate: self._validate_round_payload(round_name, candidate),
        )
        self._log_stage_output(payload)
        self.system_role = original_role
        return payload

    def _build_round_prompt(
        self,
        round_name: str,
        artifact: Stage1ContractsArtifact,
        stage_context: Dict[str, Any],
    ) -> tuple[str, List[str]]:
        current_contracts_json = self.to_pretty_json(model_dump(artifact))
        if round_name == "structure":
            return (
                stage1_ingest_extract.build_structure_prompt(
                    document_markdown=self._formatted_documents,
                    current_contracts_json=current_contracts_json,
                    stage_context=self.to_pretty_json(stage_context),
                ),
                [],
            )
        if round_name == "interface":
            return (
                stage1_ingest_extract.build_interface_prompt(
                    document_markdown=self._formatted_documents,
                    current_contracts_json=current_contracts_json,
                    stage_context=self.to_pretty_json(stage_context),
                ),
                [],
            )
        if round_name == "timing":
            return (
                stage1_ingest_extract.build_timing_prompt(
                    document_markdown=self._formatted_documents,
                    current_contracts_json=current_contracts_json,
                    stage_context=self.to_pretty_json(stage_context),
                ),
                [],
            )
        if round_name == "control":
            return (
                stage1_ingest_extract.build_control_prompt(
                    document_markdown=self._formatted_documents,
                    current_contracts_json=current_contracts_json,
                    stage_context=self.to_pretty_json(stage_context),
                ),
                [],
            )
        if round_name == "datapath":
            return (
                stage1_ingest_extract.build_datapath_prompt(
                    document_markdown=self._formatted_documents,
                    current_contracts_json=current_contracts_json,
                    stage_context=self.to_pretty_json(stage_context),
                ),
                [],
            )
        if round_name == "planning_facts":
            return (
                stage1_ingest_extract.build_planning_facts_prompt(
                    document_markdown=self._formatted_documents,
                    current_contracts_json=current_contracts_json,
                    stage_context=self.to_pretty_json(stage_context),
                ),
                [],
            )
        raise ValueError(f"Unsupported stage1 round: {round_name}")

    def _validate_round_payload(self, round_name: str, payload: BaseModel) -> List[str]:
        if round_name == "structure":
            return self._validate_structure_contract(payload.structure_contract)
        if round_name == "interface":
            return self._validate_interface_contracts(payload.interface_contracts)
        if round_name == "timing":
            return self._validate_timing_contracts(payload.timing_contracts)
        if round_name == "control":
            return self._validate_unique_modules(payload.control_contracts, "control_contracts")
        if round_name == "datapath":
            return self._validate_unique_modules(payload.datapath_contracts, "datapath_contracts")
        if round_name == "planning_facts":
            return self._validate_planning_facts(payload.planning_facts)
        raise ValueError(f"Unsupported stage1 round: {round_name}")

    def _merge_round_payload(
        self,
        artifact: Stage1ContractsArtifact,
        round_name: str,
        payload: BaseModel,
    ) -> Stage1ContractsArtifact:
        merged = model_dump(artifact)
        if round_name == "structure":
            merged["structure_contract"] = model_dump(payload.structure_contract)
        elif round_name == "interface":
            merged["interface_contracts"] = [model_dump(item) for item in payload.interface_contracts]
        elif round_name == "timing":
            merged["timing_contracts"] = [model_dump(item) for item in payload.timing_contracts]
        elif round_name == "control":
            merged["control_contracts"] = [model_dump(item) for item in payload.control_contracts]
        elif round_name == "datapath":
            merged["datapath_contracts"] = [model_dump(item) for item in payload.datapath_contracts]
        elif round_name == "planning_facts":
            merged["planning_facts"] = [model_dump(item) for item in payload.planning_facts]
        else:
            raise ValueError(f"Unsupported stage1 round: {round_name}")
        return validate_model(Stage1ContractsArtifact, merged)

    def _validate_unique_modules(
        self,
        contracts: List[BaseModel],
        field_name: str,
        require_grounding: bool = True,
    ) -> List[str]:
        errors: List[str] = []
        seen: set[str] = set()
        for index, contract in enumerate(contracts):
            module_name = str(getattr(contract, "module", "") or "").strip()
            if not module_name:
                errors.append(f"{field_name}[{index}].module must be non-empty")
                continue
            if module_name in seen:
                errors.append(f"{field_name} contains duplicate module `{module_name}`")
                continue
            seen.add(module_name)
            if require_grounding and not getattr(contract, "text_grounding", None) and not getattr(contract, "image_grounding", None):
                errors.append(f"{field_name}[{index}] must include at least one grounding object")
        return errors

    def _validate_interface_contracts(
        self,
        contracts: List[InterfaceContract],
        require_grounding: bool = True,
    ) -> List[str]:
        errors = self._validate_unique_modules(contracts, "interface_contracts", require_grounding=require_grounding)
        for index, contract in enumerate(contracts):
            for port_index, port in enumerate(contract.ports):
                if hasattr(port, "text_grounding"):
                    errors.append(
                        f"interface_contracts[{index}].ports[{port_index}] must not include per-port grounding; use module-level grounding"
                    )
            for param_index, param in enumerate(contract.params):
                if hasattr(param, "text_grounding"):
                    errors.append(
                        f"interface_contracts[{index}].params[{param_index}] must not include per-param grounding; use module-level grounding"
                    )
        return errors

    def _validate_timing_contracts(
        self,
        contracts: List[TimingContract],
        require_grounding: bool = True,
    ) -> List[str]:
        errors = self._validate_unique_modules(contracts, "timing_contracts", require_grounding=False)
        for index, contract in enumerate(contracts):
            if self._is_empty_timing_contract(contract):
                errors.append(
                    f"timing_contracts[{index}] must be omitted instead of emitting an empty shell timing contract"
                )
        return errors

    def _is_empty_timing_contract(self, contract: TimingContract) -> bool:
        return not any(
            (
                contract.clocking,
                contract.reset_behavior,
                contract.registered_objects,
                contract.phase_timing,
                contract.timing_rules,
                contract.underspecified,
            )
        )

    def _validate_planning_facts(
        self,
        facts: List[PlanningFactsContract],
        require_grounding: bool = True,
    ) -> List[str]:
        errors = self._validate_unique_modules(facts, "planning_facts", require_grounding=require_grounding)
        for index, item in enumerate(facts):
            for reg_index, reg in enumerate(item.registers):
                if not reg.name.strip():
                    errors.append(f"planning_facts[{index}].registers[{reg_index}].name must be non-empty")
            for sub_index, sub in enumerate(item.submodule_facts):
                if not sub.module.strip():
                    errors.append(f"planning_facts[{index}].submodule_facts[{sub_index}].module must be non-empty")
                if not isinstance(sub.count, (int, str)):
                    errors.append(
                        f"planning_facts[{index}].submodule_facts[{sub_index}].count must be int or string"
                    )
        return errors

    def _validate_structure_contract(self, contract: StructureContract, require_grounding: bool = True) -> List[str]:
        errors: List[str] = []
        module_set = set(contract.modules)
        if (
            contract.system
            or contract.top_module
            or contract.files
            or contract.modules
            or contract.file_map
            or contract.hierarchy
            or contract.instantiation_graph
            or contract.generation_order_candidate
        ) and require_grounding and not contract.text_grounding and not contract.image_grounding:
            errors.append("structure_contract must include at least one grounding object when non-empty")
        for file_name, modules in contract.file_map.items():
            if not file_name.strip():
                errors.append("structure_contract.file_map keys must be non-empty")
            unknown_modules = [item for item in modules if item not in module_set]
            if unknown_modules:
                errors.append(f"structure_contract.file_map references unknown modules {unknown_modules}")
        for relation_field in ("hierarchy", "instantiation_graph"):
            for relation in getattr(contract, relation_field):
                if relation.parent and module_set and relation.parent not in module_set:
                    errors.append(f"structure_contract.{relation_field} parent `{relation.parent}` is not listed in modules")
                if relation.child and module_set and relation.child not in module_set:
                    errors.append(f"structure_contract.{relation_field} child `{relation.child}` is not listed in modules")
                if relation.parent or relation.child:
                    if require_grounding and not relation.text_grounding and not relation.image_grounding:
                        errors.append(f"structure_contract.{relation_field} relation `{relation.parent}->{relation.child}` must include grounding")
        if contract.generation_order_candidate:
            unknown_modules = [item for item in contract.generation_order_candidate if item not in module_set]
            if unknown_modules:
                errors.append(f"structure_contract.generation_order_candidate references unknown modules {unknown_modules}")
        return errors
