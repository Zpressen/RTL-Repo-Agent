from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from pydantic import BaseModel, Field

from ..prompts import stage1_ingest_extract
from ..schemas import (
    ControlContract,
    DatapathContract,
    ExtractedFact,
    InterfaceContract,
    IntermediateObject,
    PlanningFactsContract,
    PlanningRegister,
    PlannerTaskInput,
    PortContract,
    Stage1ContractsArtifact,
    Stage1FactLedger,
    StructureContract,
    StructureRelation,
    TimingContract,
)
from ..utils import (
    format_documents_for_prompt,
    load_markdown_files,
)
from .base import BaseStageAgent, model_dump, validate_model


class _FactRoundPayload(BaseModel):
    fact_ledger: Stage1FactLedger = Field(default_factory=Stage1FactLedger)


class Stage1Agent(BaseStageAgent):
    stage_name = "stage1_contracts"
    output_model = Stage1ContractsArtifact
    system_role = stage1_ingest_extract.SYSTEM_ROLE

    _MAX_FILES_PER_BATCH = 5

    _ROUND_SEQUENCE = ["facts"]

    _ROUND_OUTPUT_MODELS = {
        "facts": _FactRoundPayload,
    }

    _ROUND_SYSTEM_ROLES = {
        "facts": stage1_ingest_extract.FACTS_SYSTEM_ROLE,
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
        errors.extend(self._validate_fact_ledger(artifact.fact_ledger))
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
        if round_name == "facts":
            return (
                stage1_ingest_extract.build_facts_prompt(
                    document_markdown=batch_markdown,
                    current_contracts_json=current_contracts_json,
                    stage_context=self.to_pretty_json(stage_context),
                ),
                [],
            )
        raise ValueError(f"Unsupported stage1 round: {round_name}")

    def _validate_round_payload(self, round_name: str, payload: BaseModel) -> List[str]:
        if round_name == "facts":
            return self._validate_fact_ledger(payload.fact_ledger)
        raise ValueError(f"Unsupported stage1 round: {round_name}")

    def _merge_round_payload(
        self,
        artifact: Stage1ContractsArtifact,
        round_name: str,
        payload: BaseModel,
    ) -> Stage1ContractsArtifact:
        merged = model_dump(artifact)
        if round_name == "facts":
            merged["fact_ledger"] = model_dump(
                self._merge_fact_ledgers(artifact.fact_ledger, payload.fact_ledger)
            )
        else:
            raise ValueError(f"Unsupported stage1 round: {round_name}")
        merged["completed_modules"] = self._collect_completed_modules(validate_model(Stage1ContractsArtifact, merged))
        return validate_model(Stage1ContractsArtifact, merged)

    def _collect_completed_modules(self, artifact: Stage1ContractsArtifact) -> List[str]:
        return _ordered_unique(
            [
                *artifact.completed_modules,
                *(item.module for item in artifact.fact_ledger.facts if item.module),
                *(item.module for item in artifact.fact_ledger.ambiguous_items if item.module),
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
        artifact.fact_ledger = self._normalize_fact_ledger(artifact.fact_ledger, artifact.spec_index)
        if artifact.fact_ledger.facts:
            artifact = self._project_fact_ledger_to_legacy_contracts(artifact)

        structure = artifact.structure_contract
        module_order = _ordered_unique(
            [
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
            *structure.hierarchy,
            *artifact.structure_relation_candidates,
        ]
        hierarchy = _dedupe_relations(
            relation
            for relation in hierarchy_candidates
            if relation.parent in module_set and relation.child in module_set and relation.parent != relation.child
        )
        instantiation_graph = _dedupe_relations(
            relation
            for relation in [*structure.instantiation_graph, *artifact.instantiation_relation_candidates]
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

    @staticmethod
    def _filter_empty_facts(facts: Iterable[ExtractedFact]) -> List[ExtractedFact]:
        return [f for f in facts if str(f.category).strip()]

    def _merge_fact_ledgers(self, current: Stage1FactLedger, incoming: Stage1FactLedger) -> Stage1FactLedger:
        source_files = _ordered_unique([*current.source_files, *incoming.source_files])
        return Stage1FactLedger(
            source_files=source_files,
            facts=self._dedupe_facts(self._filter_empty_facts([*current.facts, *incoming.facts])),
            ambiguous_items=self._dedupe_facts(self._filter_empty_facts([*current.ambiguous_items, *incoming.ambiguous_items])),
        )

    def _normalize_fact_ledger(
        self,
        ledger: Stage1FactLedger,
        spec_index: Dict[str, str],
    ) -> Stage1FactLedger:
        source_files = _ordered_unique([*ledger.source_files, *spec_index.values()])
        facts = self._assign_fact_ids(self._dedupe_facts(ledger.facts), prefix="F")
        ambiguous_items = self._assign_fact_ids(self._dedupe_facts(ledger.ambiguous_items), prefix="A")
        return Stage1FactLedger(source_files=source_files, facts=facts, ambiguous_items=ambiguous_items)

    def _dedupe_facts(self, facts: Iterable[ExtractedFact]) -> List[ExtractedFact]:
        seen: set[str] = set()
        result: list[ExtractedFact] = []
        for fact in facts:
            key = fact.stable_key()
            if key in seen:
                continue
            seen.add(key)
            result.append(fact)
        return result

    def _assign_fact_ids(self, facts: List[ExtractedFact], *, prefix: str) -> List[ExtractedFact]:
        result: list[ExtractedFact] = []
        used: set[str] = set()
        next_index = 1
        for fact in facts:
            payload = model_dump(fact)
            fact_id = str(payload.get("fact_id") or "").strip()
            if not fact_id or fact_id in used:
                while f"{prefix}{next_index:04d}" in used:
                    next_index += 1
                fact_id = f"{prefix}{next_index:04d}"
                next_index += 1
            used.add(fact_id)
            payload["fact_id"] = fact_id
            result.append(validate_model(ExtractedFact, payload))
        return result

    def _project_fact_ledger_to_legacy_contracts(self, artifact: Stage1ContractsArtifact) -> Stage1ContractsArtifact:
        structure_payload = model_dump(artifact.structure_contract)
        interface_by_module = {item.module: model_dump(item) for item in artifact.interface_contracts if item.module}
        timing_by_module = {item.module: model_dump(item) for item in artifact.timing_contracts if item.module}
        control_by_module = {item.module: model_dump(item) for item in artifact.control_contracts if item.module}
        datapath_by_module = {item.module: model_dump(item) for item in artifact.datapath_contracts if item.module}
        planning_by_module = {item.module: model_dump(item) for item in artifact.planning_facts if item.module}

        explicit_relation_predicates = {
            "instantiates",
            "instantiate",
            "contains",
            "includes",
            "is_composed_of",
            "has_child_module",
            "uses_explicit_module",
            "is_explicit_helper_block_used_by",
        }

        for fact in artifact.fact_ledger.facts:
            category = fact.category.strip().lower()
            predicate = fact.predicate.strip().lower()
            obj = dict(fact.object or {})
            module_name = str(fact.module or obj.get("module") or "").strip()

            if category == "module_identity":
                if value := self._string_value(obj, "system"):
                    structure_payload["system"] = structure_payload.get("system") or value
                if predicate in {"is_top_module", "top_module"}:
                    top = self._string_value(obj, "module") or module_name or fact.subject
                    structure_payload["top_module"] = structure_payload.get("top_module") or top
                for module in self._list_or_single(obj.get("modules")):
                    structure_payload["modules"] = _ordered_unique([*structure_payload.get("modules", []), module])
                if module_name:
                    structure_payload["modules"] = _ordered_unique([*structure_payload.get("modules", []), module_name])
                if predicate in {"is_module", "defines_module"} and fact.subject:
                    structure_payload["modules"] = _ordered_unique([*structure_payload.get("modules", []), fact.subject])
                for file_name in self._list_or_single(obj.get("files")):
                    structure_payload["files"] = _ordered_unique([*structure_payload.get("files", []), file_name])
                file_map = dict(structure_payload.get("file_map", {}) or {})
                object_file_map = obj.get("file_map")
                if isinstance(object_file_map, dict):
                    for file_name, modules in object_file_map.items():
                        file_map[str(file_name)] = _ordered_unique(
                            [*file_map.get(str(file_name), []), *self._list_or_single(modules)]
                        )
                structure_payload["file_map"] = file_map
                structure_payload["text_grounding"] = [
                    *structure_payload.get("text_grounding", []),
                    *[model_dump(item) for item in fact.text_grounding],
                ]

            if predicate in explicit_relation_predicates or str(obj.get("relation_type", "")).lower() in explicit_relation_predicates:
                parent = self._string_value(obj, "parent") or module_name
                child = self._string_value(obj, "child") or self._string_value(obj, "module") or self._string_value(obj, "target")
                if parent and child and parent != child:
                    relation = {
                        "parent": parent,
                        "child": child,
                        "text_grounding": [model_dump(item) for item in fact.text_grounding],
                        "image_grounding": [model_dump(item) for item in fact.image_grounding],
                    }
                    target_field = "instantiation_graph" if "instantiat" in predicate else "hierarchy"
                    structure_payload[target_field] = [
                        *structure_payload.get(target_field, []),
                        relation,
                    ]

            if category == "interface":
                self._project_interface_fact(interface_by_module, fact, module_name, obj)

            if category == "register":
                self._project_register_fact(planning_by_module, fact, module_name, obj)

            if category == "state_machine":
                self._project_state_machine_fact(control_by_module, planning_by_module, fact, module_name, obj)

            if category == "timing":
                self._project_timing_fact(timing_by_module, fact, module_name, obj)

            if category in {"datapath", "mapping_rule", "algorithm_step"}:
                self._project_datapath_fact(datapath_by_module, planning_by_module, fact, module_name, obj)

        structure_payload["hierarchy"] = [
            model_dump(item) for item in _dedupe_relations(validate_model(StructureRelation, item) for item in structure_payload.get("hierarchy", []))
        ]
        structure_payload["instantiation_graph"] = [
            model_dump(item) for item in _dedupe_relations(validate_model(StructureRelation, item) for item in structure_payload.get("instantiation_graph", []))
        ]

        artifact.structure_contract = validate_model(StructureContract, structure_payload)
        artifact.interface_contracts = [
            validate_model(InterfaceContract, payload)
            for _, payload in sorted(interface_by_module.items())
        ]
        artifact.timing_contracts = [
            validate_model(TimingContract, payload)
            for _, payload in sorted(timing_by_module.items())
        ]
        artifact.control_contracts = [
            validate_model(ControlContract, payload)
            for _, payload in sorted(control_by_module.items())
        ]
        artifact.datapath_contracts = [
            validate_model(DatapathContract, payload)
            for _, payload in sorted(datapath_by_module.items())
        ]
        artifact.planning_facts = [
            validate_model(PlanningFactsContract, payload)
            for _, payload in sorted(planning_by_module.items())
        ]
        return artifact

    def _project_interface_fact(
        self,
        interface_by_module: Dict[str, Dict[str, Any]],
        fact: ExtractedFact,
        module_name: str,
        obj: Dict[str, Any],
    ) -> None:
        module = module_name
        if not module:
            return
        payload = interface_by_module.setdefault(
            module,
            {
                "module": module,
                "ports": [],
                "params": [],
                "clock": "",
                "reset": "",
                "reset_polarity": "",
                "handshakes": [],
                "parameter_constraints": [],
                "bus_roles": [],
                "text_grounding": [],
                "image_grounding": [],
            },
        )
        payload["text_grounding"] = [*payload.get("text_grounding", []), *[model_dump(item) for item in fact.text_grounding]]
        payload["image_grounding"] = [*payload.get("image_grounding", []), *[model_dump(item) for item in fact.image_grounding]]

        ports = obj.get("ports") if isinstance(obj.get("ports"), list) else [obj]
        existing_names = {str(port.get("name", "")) for port in payload.get("ports", []) if isinstance(port, dict)}
        for port_obj in ports:
            if not isinstance(port_obj, dict):
                continue
            port_name = str(port_obj.get("name") or fact.subject or "").strip()
            direction = str(port_obj.get("direction") or port_obj.get("dir") or "").strip()
            width = str(port_obj.get("width") or "").strip()
            if port_name and direction and width and port_name not in existing_names:
                payload["ports"].append(
                    model_dump(
                        PortContract(
                            name=port_name,
                            direction=direction,
                            width=width,
                            role=str(port_obj.get("role") or ""),
                            active=str(port_obj.get("active") or ""),
                            meaning=str(port_obj.get("meaning") or port_obj.get("description") or ""),
                        )
                    )
                )
                existing_names.add(port_name)
            role = str(port_obj.get("role") or "").lower()
            if role == "clock" and port_name and not payload.get("clock"):
                payload["clock"] = port_name
            if role == "reset" and port_name and not payload.get("reset"):
                payload["reset"] = port_name
        if value := self._string_value(obj, "reset_polarity"):
            payload["reset_polarity"] = payload.get("reset_polarity") or value
        for handshake in self._list_or_single(obj.get("handshakes") or obj.get("handshake")):
            payload["handshakes"] = _ordered_unique([*payload.get("handshakes", []), handshake])
        for role in self._list_or_single(obj.get("bus_roles") or obj.get("bus_role")):
            payload["bus_roles"] = _ordered_unique([*payload.get("bus_roles", []), role])

    def _project_register_fact(
        self,
        planning_by_module: Dict[str, Dict[str, Any]],
        fact: ExtractedFact,
        module_name: str,
        obj: Dict[str, Any],
    ) -> None:
        module = module_name
        if not module:
            return
        payload = self._planning_payload(planning_by_module, module, fact)
        reg_name = self._string_value(obj, "name") or fact.subject
        if not reg_name:
            return
        existing = {str(item.get("name", "")) for item in payload.get("registers", []) if isinstance(item, dict)}
        if reg_name not in existing:
            payload["registers"].append(
                model_dump(
                    PlanningRegister(
                        name=reg_name,
                        width=str(obj.get("width") or ""),
                        role=str(obj.get("role") or obj.get("description") or fact.predicate),
                    )
                )
            )

    def _project_state_machine_fact(
        self,
        control_by_module: Dict[str, Dict[str, Any]],
        planning_by_module: Dict[str, Dict[str, Any]],
        fact: ExtractedFact,
        module_name: str,
        obj: Dict[str, Any],
    ) -> None:
        module = module_name
        if not module:
            return
        control = control_by_module.setdefault(
            module,
            {
                "module": module,
                "abstract_states": [],
                "transitions": [],
                "control_signals": [],
                "bypass_conditions": [],
                "exception_conditions": [],
                "counter_rules": [],
                "text_grounding": [],
                "image_grounding": [],
            },
        )
        control["text_grounding"] = [*control.get("text_grounding", []), *[model_dump(item) for item in fact.text_grounding]]
        states = self._list_or_single(obj.get("states") or obj.get("state_names"))
        if not states and fact.predicate.lower() in {"has_state", "state"}:
            states = [fact.subject]
        control["abstract_states"] = _ordered_unique([*control.get("abstract_states", []), *states])
        planning = self._planning_payload(planning_by_module, module, fact)
        planning["state_names"] = _ordered_unique([*planning.get("state_names", []), *states])

    def _project_timing_fact(
        self,
        timing_by_module: Dict[str, Dict[str, Any]],
        fact: ExtractedFact,
        module_name: str,
        obj: Dict[str, Any],
    ) -> None:
        module = module_name
        if not module:
            return
        payload = timing_by_module.setdefault(
            module,
            {
                "module": module,
                "clocking": {},
                "reset_behavior": {},
                "registered_objects": [],
                "phase_timing": [],
                "timing_rules": [],
                "underspecified": [],
            },
        )
        if isinstance(obj.get("clocking"), dict):
            payload["clocking"] = {**payload.get("clocking", {}), **obj["clocking"]}
        if isinstance(obj.get("reset_behavior"), dict):
            payload["reset_behavior"] = {**payload.get("reset_behavior", {}), **obj["reset_behavior"]}
        for key in ("registered_objects", "phase_timing", "timing_rules", "underspecified"):
            if key in obj:
                payload[key] = [*payload.get(key, []), *self._list_or_single(obj.get(key))]
        if statement := self._string_value(obj, "statement"):
            payload["timing_rules"] = _ordered_unique([*payload.get("timing_rules", []), statement])
        elif fact.subject and fact.predicate:
            payload["timing_rules"] = _ordered_unique(
                [*payload.get("timing_rules", []), f"{fact.subject}: {fact.predicate}"]
            )

    def _project_datapath_fact(
        self,
        datapath_by_module: Dict[str, Dict[str, Any]],
        planning_by_module: Dict[str, Dict[str, Any]],
        fact: ExtractedFact,
        module_name: str,
        obj: Dict[str, Any],
    ) -> None:
        module = module_name
        if not module:
            return
        payload = datapath_by_module.setdefault(
            module,
            {
                "module": module,
                "input_data": [],
                "main_flow": [],
                "intermediate_objects": [],
                "path_annotations": [],
                "registered_paths": [],
                "combinational_paths": [],
                "special_paths": [],
                "text_grounding": [],
                "image_grounding": [],
            },
        )
        payload["text_grounding"] = [*payload.get("text_grounding", []), *[model_dump(item) for item in fact.text_grounding]]
        for key in ("input_data", "main_flow", "registered_paths", "combinational_paths", "special_paths"):
            values = self._list_or_single(obj.get(key))
            if values:
                payload[key] = _ordered_unique([*payload.get(key, []), *values])
        if fact.category.lower() == "algorithm_step" and fact.subject:
            payload["main_flow"] = _ordered_unique([*payload.get("main_flow", []), fact.subject])
        if name := self._string_value(obj, "intermediate_object"):
            payload["intermediate_objects"].append(
                model_dump(IntermediateObject(name=name, role=str(obj.get("role") or fact.predicate), text_grounding=list(fact.text_grounding)))
            )
        if mapping := self._string_value(obj, "mapping"):
            planning = self._planning_payload(planning_by_module, module, fact)
            planning["local_mappings"] = _ordered_unique([*planning.get("local_mappings", []), mapping])

    def _planning_payload(
        self,
        planning_by_module: Dict[str, Dict[str, Any]],
        module: str,
        fact: ExtractedFact,
    ) -> Dict[str, Any]:
        payload = planning_by_module.setdefault(
            module,
            {
                "module": module,
                "registers": [],
                "state_names": [],
                "submodule_facts": [],
                "local_mappings": [],
                "text_grounding": [],
                "image_grounding": [],
            },
        )
        payload["text_grounding"] = [*payload.get("text_grounding", []), *[model_dump(item) for item in fact.text_grounding]]
        payload["image_grounding"] = [*payload.get("image_grounding", []), *[model_dump(item) for item in fact.image_grounding]]
        return payload

    def _validate_fact_ledger(self, ledger: Stage1FactLedger) -> List[str]:
        errors: List[str] = []
        for field_name, facts in (("facts", ledger.facts), ("ambiguous_items", ledger.ambiguous_items)):
            seen_ids: set[str] = set()
            for index, fact in enumerate(facts):
                if fact.fact_id:
                    if fact.fact_id in seen_ids:
                        errors.append(f"fact_ledger.{field_name}[{index}].fact_id duplicates `{fact.fact_id}`")
                    seen_ids.add(fact.fact_id)
                if not fact.category.strip():
                    errors.append(f"fact_ledger.{field_name}[{index}].category must be non-empty")
        return errors

    def _string_value(self, obj: Dict[str, Any], key: str) -> str:
        value = obj.get(key)
        if value is None:
            return ""
        if isinstance(value, (list, dict)):
            return ""
        return str(value).strip()

    def _list_or_single(self, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return [item for item in value if item not in (None, "")]
        if isinstance(value, tuple):
            return [item for item in value if item not in (None, "")]
        if isinstance(value, dict):
            return [value]
        text = str(value).strip()
        return [text] if text else []

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
