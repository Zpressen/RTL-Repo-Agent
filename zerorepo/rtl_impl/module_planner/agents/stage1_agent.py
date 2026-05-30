from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, TypeVar

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
    StructureRelation,
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


TContract = TypeVar("TContract", bound=BaseModel)


class Stage1Agent(BaseStageAgent):
    stage_name = "stage1_contracts"
    output_model = Stage1ContractsArtifact
    system_role = stage1_ingest_extract.SYSTEM_ROLE

    _MAX_FILES_PER_BATCH = 5

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
        artifact.spec_index = self._merge_spec_index(artifact.spec_index, self._documents)

        for batch_index, batch in enumerate(self._document_batches, start=1):
            batch_id = self._batch_id(batch_index, batch)
            if batch_id in artifact.completed_batches:
                continue
            formatted_batch = format_documents_for_prompt(batch)
            batch_context = {
                **stage_context,
                "batch_id": batch_id,
                "batch_index": batch_index,
                "batch_count": len(self._document_batches),
                "batch_spec_files": [document["path"] for document in batch],
                "batch_modules": [self._infer_module_name_from_document(document) for document in batch],
                "max_files_per_batch": self._MAX_FILES_PER_BATCH,
            }
            for round_name in self._ROUND_SEQUENCE:
                if self._should_skip_legacy_completed_round(artifact, batch_index, round_name):
                    continue
                payload = self._run_round(
                    round_name=round_name,
                    task_input=task,
                    partial_artifacts=partial_artifacts,
                    stage_context=batch_context,
                    artifact=artifact,
                    document_markdown=formatted_batch,
                )
                artifact = self._merge_round_payload(artifact, round_name, payload)
                artifact.stage1_status = f"{batch_id}_{round_name}_completed"
                if persist_callback is not None:
                    persist_callback(model_dump(artifact))
            artifact.completed_batches = _ordered_unique([*artifact.completed_batches, batch_id])
            artifact.completed_modules = self._collect_completed_modules(artifact)
            artifact.stage1_status = f"{batch_id}_completed"
            if persist_callback is not None:
                persist_callback(model_dump(artifact))

        artifact = self._finalize_structure_contract(artifact, task)
        artifact.completed_rounds = list(self._ROUND_SEQUENCE)
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
        errors.extend(self._validate_interface_contracts(artifact.interface_contracts, require_grounding=False))
        errors.extend(self._validate_timing_contracts(artifact.timing_contracts, require_grounding=False))
        errors.extend(self._validate_unique_modules(artifact.control_contracts, "control_contracts", require_grounding=False))
        errors.extend(self._validate_unique_modules(artifact.datapath_contracts, "datapath_contracts", require_grounding=False))
        errors.extend(self._validate_planning_facts(artifact.planning_facts, require_grounding=False))
        errors.extend(self._validate_structure_contract(artifact.structure_contract, require_grounding=False))
        return errors

    def _prepare_inputs(self, task_input: PlannerTaskInput) -> None:
        self._documents = load_markdown_files(task_input.spec_md_files)
        self._document_batches = self._make_document_batches(self._documents)
        self._formatted_documents = format_documents_for_prompt(self._documents)

    def _make_document_batches(self, documents: List[dict]) -> List[List[dict]]:
        return [documents[index : index + self._MAX_FILES_PER_BATCH] for index in range(0, len(documents), self._MAX_FILES_PER_BATCH)]

    def _batch_id(self, index: int, batch: List[dict]) -> str:
        return f"batch_{index:04d}"

    def _infer_module_name_from_document(self, document: dict) -> str:
        return Path(str(document.get("path", ""))).stem.strip()

    def _merge_spec_index(self, existing: Dict[str, str], documents: List[dict]) -> Dict[str, str]:
        merged = dict(existing or {})
        for document in documents:
            module_name = self._infer_module_name_from_document(document)
            if module_name and module_name not in merged:
                merged[module_name] = str(document.get("path", ""))
        return merged

    def _bootstrap_artifact(self, task: PlannerTaskInput, existing: Any) -> Stage1ContractsArtifact:
        if existing is None:
            return validate_model(Stage1ContractsArtifact, {"task_id": task.task_id})
        if isinstance(existing, Stage1ContractsArtifact):
            artifact = existing
        else:
            artifact = validate_model(Stage1ContractsArtifact, existing)
        artifact.completed_rounds = [round_name for round_name in artifact.completed_rounds if round_name in self._ROUND_SEQUENCE]
        artifact.completed_batches = _ordered_unique(artifact.completed_batches)
        artifact.completed_modules = _ordered_unique(artifact.completed_modules)
        artifact.top_module_candidates = _ordered_unique(artifact.top_module_candidates)
        return artifact

    def _should_skip_legacy_completed_round(
        self,
        artifact: Stage1ContractsArtifact,
        batch_index: int,
        round_name: str,
    ) -> bool:
        return batch_index == 1 and not artifact.completed_batches and round_name in artifact.completed_rounds

    def _run_round(
        self,
        *,
        round_name: str,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        stage_context: Dict[str, Any],
        artifact: Stage1ContractsArtifact,
        document_markdown: str,
    ) -> BaseModel:
        prompt, images = self._build_round_prompt(round_name, artifact, stage_context, document_markdown)
        original_role = self.system_role
        self.system_role = self._ROUND_SYSTEM_ROLES[round_name]
        self._log_stage_input(prompt=prompt, images=images, stage_context={**stage_context, "round": round_name})
        try:
            payload = self._invoke_with_repair(
                prompt,
                images,
                task_input,
                partial_artifacts,
                output_model=self._ROUND_OUTPUT_MODELS[round_name],
                quality_validator=lambda candidate: self._validate_round_payload(round_name, candidate),
            )
        finally:
            self.system_role = original_role
        self._log_stage_output(payload)
        return payload

    def _build_round_prompt(
        self,
        round_name: str,
        artifact: Stage1ContractsArtifact,
        stage_context: Dict[str, Any],
        document_markdown: str | None = None,
    ) -> tuple[str, List[str]]:
        current_contracts_json = self.to_pretty_json(model_dump(artifact))
        batch_markdown = document_markdown if document_markdown is not None else self._formatted_documents
        if round_name == "structure":
            return (
                stage1_ingest_extract.build_structure_prompt(
                    document_markdown=batch_markdown,
                    current_contracts_json=current_contracts_json,
                    stage_context=self.to_pretty_json(stage_context),
                ),
                [],
            )
        if round_name == "interface":
            return (
                stage1_ingest_extract.build_interface_prompt(
                    document_markdown=batch_markdown,
                    current_contracts_json=current_contracts_json,
                    stage_context=self.to_pretty_json(stage_context),
                ),
                [],
            )
        if round_name == "timing":
            return (
                stage1_ingest_extract.build_timing_prompt(
                    document_markdown=batch_markdown,
                    current_contracts_json=current_contracts_json,
                    stage_context=self.to_pretty_json(stage_context),
                ),
                [],
            )
        if round_name == "control":
            return (
                stage1_ingest_extract.build_control_prompt(
                    document_markdown=batch_markdown,
                    current_contracts_json=current_contracts_json,
                    stage_context=self.to_pretty_json(stage_context),
                ),
                [],
            )
        if round_name == "datapath":
            return (
                stage1_ingest_extract.build_datapath_prompt(
                    document_markdown=batch_markdown,
                    current_contracts_json=current_contracts_json,
                    stage_context=self.to_pretty_json(stage_context),
                ),
                [],
            )
        if round_name == "planning_facts":
            return (
                stage1_ingest_extract.build_planning_facts_prompt(
                    document_markdown=batch_markdown,
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
            structure = payload.structure_contract
            current_structure = artifact.structure_contract
            merged_structure = model_dump(current_structure)
            merged_structure["system"] = current_structure.system or structure.system
            merged_structure["top_module"] = current_structure.top_module or structure.top_module
            merged_structure["files"] = _ordered_unique([*current_structure.files, *structure.files])
            merged_structure["modules"] = _ordered_unique([*current_structure.modules, *structure.modules])
            file_map = {key: list(value) for key, value in current_structure.file_map.items()}
            for file_name, modules in structure.file_map.items():
                file_map[file_name] = _ordered_unique([*file_map.get(file_name, []), *modules])
            merged_structure["file_map"] = file_map
            merged_structure["text_grounding"] = [*model_dump(current_structure).get("text_grounding", []), *model_dump(structure).get("text_grounding", [])]
            merged_structure["image_grounding"] = [*model_dump(current_structure).get("image_grounding", []), *model_dump(structure).get("image_grounding", [])]
            merged["structure_contract"] = merged_structure
            merged["structure_relation_candidates"] = _dedupe_relations(
                [*artifact.structure_relation_candidates, *structure.hierarchy]
            )
            merged["instantiation_relation_candidates"] = _dedupe_relations(
                [*artifact.instantiation_relation_candidates, *structure.instantiation_graph]
            )
            merged["top_module_candidates"] = _ordered_unique([*artifact.top_module_candidates, structure.top_module])
        elif round_name == "interface":
            merged["interface_contracts"] = [model_dump(item) for item in self._upsert_contracts(artifact.interface_contracts, payload.interface_contracts)]
        elif round_name == "timing":
            merged["timing_contracts"] = [model_dump(item) for item in self._upsert_contracts(artifact.timing_contracts, payload.timing_contracts)]
        elif round_name == "control":
            merged["control_contracts"] = [model_dump(item) for item in self._upsert_contracts(artifact.control_contracts, payload.control_contracts)]
        elif round_name == "datapath":
            merged["datapath_contracts"] = [model_dump(item) for item in self._upsert_contracts(artifact.datapath_contracts, payload.datapath_contracts)]
        elif round_name == "planning_facts":
            merged["planning_facts"] = [model_dump(item) for item in self._upsert_contracts(artifact.planning_facts, payload.planning_facts)]
        else:
            raise ValueError(f"Unsupported stage1 round: {round_name}")
        merged["completed_modules"] = self._collect_completed_modules(validate_model(Stage1ContractsArtifact, merged))
        return validate_model(Stage1ContractsArtifact, merged)

    def _upsert_contracts(self, existing: List[TContract], incoming: List[TContract]) -> List[TContract]:
        ordered_modules = [str(getattr(item, "module", "") or "").strip() for item in existing]
        by_module = {
            str(getattr(item, "module", "") or "").strip(): item
            for item in existing
            if str(getattr(item, "module", "") or "").strip()
        }
        for item in incoming:
            module_name = str(getattr(item, "module", "") or "").strip()
            if not module_name:
                continue
            if module_name not in by_module:
                ordered_modules.append(module_name)
            by_module[module_name] = item
        return [by_module[module_name] for module_name in ordered_modules if module_name in by_module]

    def _collect_completed_modules(self, artifact: Stage1ContractsArtifact) -> List[str]:
        return _ordered_unique(
            [
                *artifact.completed_modules,
                *(item.module for item in artifact.interface_contracts),
                *(item.module for item in artifact.timing_contracts),
                *(item.module for item in artifact.control_contracts),
                *(item.module for item in artifact.datapath_contracts),
                *(item.module for item in artifact.planning_facts),
            ]
        )

    def _finalize_structure_contract(
        self,
        artifact: Stage1ContractsArtifact,
        task: PlannerTaskInput,
    ) -> Stage1ContractsArtifact:
        structure = artifact.structure_contract
        module_order = _ordered_unique(
            [
                *artifact.spec_index.keys(),
                *structure.modules,
                *(item.module for item in artifact.interface_contracts),
                *(item.module for item in artifact.timing_contracts),
                *(item.module for item in artifact.control_contracts),
                *(item.module for item in artifact.datapath_contracts),
                *(item.module for item in artifact.planning_facts),
                *(relation.parent for relation in artifact.structure_relation_candidates),
                *(relation.child for relation in artifact.structure_relation_candidates),
                *(relation.parent for relation in artifact.instantiation_relation_candidates),
                *(relation.child for relation in artifact.instantiation_relation_candidates),
                *(sub.module for facts in artifact.planning_facts for sub in facts.submodule_facts),
            ]
        )
        module_set = set(module_order)
        hierarchy_candidates = [
            *artifact.structure_relation_candidates,
            *self._planning_submodule_relations(artifact.planning_facts),
        ]
        hierarchy = _dedupe_relations(
            relation
            for relation in hierarchy_candidates
            if relation.parent in module_set and relation.child in module_set and relation.parent != relation.child
        )
        instantiation_graph = _dedupe_relations(
            relation
            for relation in artifact.instantiation_relation_candidates
            if relation.parent in module_set and relation.child in module_set and relation.parent != relation.child
        )
        top_module = self._select_top_module(artifact, task, module_order, [*hierarchy, *instantiation_graph])
        generation_order = self._child_before_parent_order(module_order, [*hierarchy, *instantiation_graph])

        structure_payload = model_dump(structure)
        structure_payload["top_module"] = top_module
        structure_payload["modules"] = module_order
        structure_payload["hierarchy"] = [model_dump(item) for item in hierarchy]
        structure_payload["instantiation_graph"] = [model_dump(item) for item in instantiation_graph]
        structure_payload["generation_order_candidate"] = generation_order
        artifact.structure_contract = validate_model(StructureContract, structure_payload)
        artifact.completed_modules = self._collect_completed_modules(artifact)
        return artifact

    def _planning_submodule_relations(self, facts: List[PlanningFactsContract]) -> List[StructureRelation]:
        relations: list[StructureRelation] = []
        for item in facts:
            parent = item.module.strip()
            if not parent:
                continue
            for submodule in item.submodule_facts:
                child = submodule.module.strip()
                if not child:
                    continue
                relations.append(StructureRelation(parent=parent, child=child, text_grounding=list(item.text_grounding), image_grounding=list(item.image_grounding)))
        return relations

    def _select_top_module(
        self,
        artifact: Stage1ContractsArtifact,
        task: PlannerTaskInput,
        module_order: List[str],
        relations: List[StructureRelation],
    ) -> str:
        module_set = set(module_order)
        candidates = [item for item in artifact.top_module_candidates if item in module_set]
        if len(set(candidates)) == 1:
            return candidates[0]
        if artifact.structure_contract.top_module in module_set:
            return artifact.structure_contract.top_module
        parents = {item.parent for item in relations if item.parent in module_set and item.child in module_set}
        children = {item.child for item in relations if item.parent in module_set and item.child in module_set}
        roots = [item for item in module_order if item in parents and item not in children]
        if len(roots) == 1:
            return roots[0]
        task_id = task.task_id.lower()
        for module_name in module_order:
            if module_name.lower() == task_id or module_name.lower() in task_id:
                return module_name
        return ""

    def _child_before_parent_order(self, module_order: List[str], relations: List[StructureRelation]) -> List[str]:
        module_set = set(module_order)
        children_by_parent: dict[str, set[str]] = {module: set() for module in module_order}
        for relation in relations:
            if relation.parent in module_set and relation.child in module_set and relation.parent != relation.child:
                children_by_parent[relation.parent].add(relation.child)
        visited: set[str] = set()
        visiting: set[str] = set()
        ordered: list[str] = []

        def visit(module_name: str) -> None:
            if module_name in visited:
                return
            if module_name in visiting:
                return
            visiting.add(module_name)
            for child in sorted(children_by_parent.get(module_name, set()), key=lambda item: module_order.index(item)):
                visit(child)
            visiting.remove(module_name)
            visited.add(module_name)
            ordered.append(module_name)

        for module_name in module_order:
            visit(module_name)
        return ordered

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


def _ordered_unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in items:
        item = str(raw or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _dedupe_relations(relations: Iterable[StructureRelation]) -> list[StructureRelation]:
    seen: set[tuple[str, str]] = set()
    ordered: list[StructureRelation] = []
    for relation in relations:
        parent = str(relation.parent or "").strip()
        child = str(relation.child or "").strip()
        if not parent or not child or (parent, child) in seen:
            continue
        seen.add((parent, child))
        ordered.append(relation)
    return ordered
