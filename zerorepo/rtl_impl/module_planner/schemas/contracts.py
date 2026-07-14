from __future__ import annotations

import json
from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field, model_validator

class TextGrounding(BaseModel):
    source_md_file: str = Field(default="")
    section_path: str = Field(default="")
    start_line_anchor: str = Field(default="")
    end_line_anchor: str = Field(default="")


class ImageGrounding(BaseModel):
    image_id: str = Field(default="")
    image_file: str = Field(default="")
    visible_text: List[str] = Field(default_factory=list)


FactSourceKind = Literal[
    "explicit_text",
    "table_row",
    "figure_text",
    "section_heading",
    "ambiguous_text",
]


class ExtractedFact(BaseModel):
    fact_id: str = Field(default="")
    module: str = Field(default="")
    category: str = Field(default="")
    subject: str = Field(default="")
    predicate: str = Field(default="")
    object: Dict[str, Any] = Field(default_factory=dict)
    source_kind: FactSourceKind = Field(default="explicit_text")
    text_grounding: List[TextGrounding] = Field(default_factory=list)
    image_grounding: List[ImageGrounding] = Field(default_factory=list)
    notes: str = Field(default="")

    @model_validator(mode="after")
    def validate_fact_shape(self) -> "ExtractedFact":
        if not self.category.strip():
            raise ValueError("category must be non-empty")
        return self

    def stable_key(self) -> str:
        return "|".join(
            [
                self.module.strip(),
                self.category.strip(),
                self.subject.strip(),
                self.predicate.strip(),
                json.dumps(self.object, sort_keys=True, ensure_ascii=True),
                self.source_kind,
                self.notes.strip(),
            ]
        )


class Stage1FactLedger(BaseModel):
    source_files: List[str] = Field(default_factory=list)
    facts: List[ExtractedFact] = Field(default_factory=list)
    ambiguous_items: List[ExtractedFact] = Field(default_factory=list)


class StructureRelation(BaseModel):
    parent: str = Field(default="")
    child: str = Field(default="")
    text_grounding: List[TextGrounding] = Field(default_factory=list)
    image_grounding: List[ImageGrounding] = Field(default_factory=list)


class StructureContract(BaseModel):
    system: str = Field(default="")
    top_module: str = Field(default="")
    files: List[str] = Field(default_factory=list)
    modules: List[str] = Field(default_factory=list)
    file_map: Dict[str, List[str]] = Field(default_factory=dict)
    hierarchy: List[StructureRelation] = Field(default_factory=list)
    instantiation_graph: List[StructureRelation] = Field(default_factory=list)
    generation_order_candidate: List[str] = Field(default_factory=list)
    text_grounding: List[TextGrounding] = Field(default_factory=list)
    image_grounding: List[ImageGrounding] = Field(default_factory=list)


class ParameterContract(BaseModel):
    name: str = Field(default="")
    value: str = Field(default="")
    meaning: str = Field(default="")


class PortContract(BaseModel):
    name: str = Field(default="")
    direction: str = Field(default="")
    width: str = Field(default="")
    role: str = Field(default="")
    active: str = Field(default="")
    meaning: str = Field(default="")


class InterfaceContract(BaseModel):
    module: str = Field(default="")
    ports: List[PortContract] = Field(default_factory=list)
    params: List[ParameterContract] = Field(default_factory=list)
    clock: str = Field(default="")
    reset: str = Field(default="")
    reset_polarity: str = Field(default="")
    handshakes: List[str] = Field(default_factory=list)
    parameter_constraints: List[str] = Field(default_factory=list)
    bus_roles: List[str] = Field(default_factory=list)
    text_grounding: List[TextGrounding] = Field(default_factory=list)
    image_grounding: List[ImageGrounding] = Field(default_factory=list)


class SignalRule(BaseModel):
    signal: str = Field(default="")
    signals: List[str] = Field(default_factory=list)
    rule: str = Field(default="")
    text_grounding: List[TextGrounding] = Field(default_factory=list)


class ResetBehavior(BaseModel):
    signal: str = Field(default="")
    active: str = Field(default="")
    effect: str = Field(default="")
    text_grounding: List[TextGrounding] = Field(default_factory=list)


class SignalSemantic(BaseModel):
    signal: str = Field(default="")
    semantic_type: str = Field(default="")
    text_grounding: List[TextGrounding] = Field(default_factory=list)


class TimingContract(BaseModel):
    module: str = Field(default="")
    clocking: Dict[str, Any] = Field(default_factory=dict)
    reset_behavior: Dict[str, Any] = Field(default_factory=dict)
    registered_objects: List[Dict[str, Any]] = Field(default_factory=list)
    phase_timing: List[Dict[str, Any]] = Field(default_factory=list)
    timing_rules: List[str] = Field(default_factory=list)
    underspecified: List[str] = Field(default_factory=list)


class StateTransition(BaseModel):
    from_state: str = Field(default="")
    to_state: str = Field(default="")
    condition: str = Field(default="")
    text_grounding: List[TextGrounding] = Field(default_factory=list)


class NamedMeaning(BaseModel):
    name: str = Field(default="")
    meaning: str = Field(default="")
    text_grounding: List[TextGrounding] = Field(default_factory=list)


class ControlCondition(BaseModel):
    condition: str = Field(default="")
    text_grounding: List[TextGrounding] = Field(default_factory=list)


class CounterRule(BaseModel):
    counter: str = Field(default="")
    rule: str = Field(default="")
    text_grounding: List[TextGrounding] = Field(default_factory=list)


class ControlContract(BaseModel):
    module: str = Field(default="")
    abstract_states: List[str] = Field(default_factory=list)
    transitions: List[StateTransition] = Field(default_factory=list)
    control_signals: List[NamedMeaning] = Field(default_factory=list)
    bypass_conditions: List[ControlCondition] = Field(default_factory=list)
    exception_conditions: List[ControlCondition] = Field(default_factory=list)
    counter_rules: List[CounterRule] = Field(default_factory=list)
    text_grounding: List[TextGrounding] = Field(default_factory=list)
    image_grounding: List[ImageGrounding] = Field(default_factory=list)


class IntermediateObject(BaseModel):
    name: str = Field(default="")
    role: str = Field(default="")
    text_grounding: List[TextGrounding] = Field(default_factory=list)


class PathAnnotation(BaseModel):
    path: str = Field(default="")
    kind: str = Field(default="")
    text_grounding: List[TextGrounding] = Field(default_factory=list)


class DatapathContract(BaseModel):
    module: str = Field(default="")
    input_data: List[str] = Field(default_factory=list)
    main_flow: List[str] = Field(default_factory=list)
    intermediate_objects: List[IntermediateObject] = Field(default_factory=list)
    path_annotations: List[PathAnnotation] = Field(default_factory=list)
    registered_paths: List[str] = Field(default_factory=list)
    combinational_paths: List[str] = Field(default_factory=list)
    special_paths: List[str] = Field(default_factory=list)
    text_grounding: List[TextGrounding] = Field(default_factory=list)
    image_grounding: List[ImageGrounding] = Field(default_factory=list)


class PlanningRegister(BaseModel):
    name: str = Field(default="")
    width: str = Field(default="")
    role: str = Field(default="")


class PlanningSubmoduleFact(BaseModel):
    module: str = Field(default="")
    count: int | str = Field(default="")
    usage: str = Field(default="")


class PlanningFactsContract(BaseModel):
    module: str = Field(default="")
    registers: List[PlanningRegister] = Field(default_factory=list)
    state_names: List[str] = Field(default_factory=list)
    submodule_facts: List[PlanningSubmoduleFact] = Field(default_factory=list)
    local_mappings: List[str] = Field(default_factory=list)
    text_grounding: List[TextGrounding] = Field(default_factory=list)
    image_grounding: List[ImageGrounding] = Field(default_factory=list)


class ModuleContractsBundle(BaseModel):
    module: str = Field(..., min_length=1)
    is_top_module: bool = Field(default=False)
    facts: List[ExtractedFact] = Field(default_factory=list)
    interface_contract: InterfaceContract | None = None
    timing_contract: TimingContract | None = None
    control_contract: ControlContract | None = None
    datapath_contract: DatapathContract | None = None
    planning_facts: PlanningFactsContract | None = None
    parent_modules: List[str] = Field(default_factory=list)
    child_modules: List[str] = Field(default_factory=list)
    outgoing_hierarchy_relations: List[StructureRelation] = Field(default_factory=list)
    incoming_hierarchy_relations: List[StructureRelation] = Field(default_factory=list)
    outgoing_instantiation_relations: List[StructureRelation] = Field(default_factory=list)
    incoming_instantiation_relations: List[StructureRelation] = Field(default_factory=list)


class ModuleOrganizationArtifact(BaseModel):
    schema_version: str = Field(default="module_contracts_v1")
    task_id: str = Field(..., min_length=1)
    source_schema_version: str = Field(default="stage1_contracts_v1")
    top_module: str = Field(default="")
    module_order: List[str] = Field(default_factory=list)
    repository_structure: StructureContract = Field(default_factory=StructureContract)
    fact_ledger: Stage1FactLedger = Field(default_factory=Stage1FactLedger)
    repository_facts: List[ExtractedFact] = Field(default_factory=list)
    modules: List[ModuleContractsBundle] = Field(default_factory=list)


class Stage1ContractsArtifact(BaseModel):
    schema_version: str = Field(default="stage1_contracts_v1")
    task_id: str = Field(..., min_length=1)
    stage1_status: str = Field(default="initialized")
    completed_rounds: List[str] = Field(default_factory=list)
    completed_batches: List[str] = Field(default_factory=list)
    completed_modules: List[str] = Field(default_factory=list)
    spec_index: Dict[str, str] = Field(default_factory=dict)
    structure_relation_candidates: List[StructureRelation] = Field(default_factory=list)
    instantiation_relation_candidates: List[StructureRelation] = Field(default_factory=list)
    top_module_candidates: List[str] = Field(default_factory=list)
    structure_contract: StructureContract = Field(default_factory=StructureContract)
    fact_ledger: Stage1FactLedger = Field(default_factory=Stage1FactLedger)
    interface_contracts: List[InterfaceContract] = Field(default_factory=list)
    timing_contracts: List[TimingContract] = Field(default_factory=list)
    control_contracts: List[ControlContract] = Field(default_factory=list)
    datapath_contracts: List[DatapathContract] = Field(default_factory=list)
    planning_facts: List[PlanningFactsContract] = Field(default_factory=list)
