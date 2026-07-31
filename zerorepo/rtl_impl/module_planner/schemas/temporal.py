from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field, model_validator

from .contracts import TextGrounding


TemporalPoint = Literal["PRE_EDGE", "POST_EDGE", "COMB"]
TemporalRelationKind = Literal["SAME_EDGE", "NEXT_EDGE", "EXACT_CYCLES", "BEFORE"]
TemporalSeverity = Literal["ERROR", "WARNING"]


class TemporalClock(BaseModel):
    name: str = Field(default="")
    edge: Literal["posedge", "negedge", "unspecified"] = Field(default="unspecified")


class TemporalReset(BaseModel):
    name: str = Field(default="")
    polarity: Literal["active_high", "active_low", "unspecified"] = Field(default="unspecified")
    kind: Literal["synchronous", "asynchronous", "unspecified"] = Field(default="unspecified")


class TemporalEvent(BaseModel):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    kind: Literal["start", "completion", "reset", "status", "other"] = Field(default="other")
    trigger: str = Field(..., min_length=1)
    guard: str = Field(default="")
    text_grounding: List[TextGrounding] = Field(default_factory=list)


class TemporalPhase(BaseModel):
    id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    order: int = Field(..., ge=0)
    trigger_event_id: str = Field(default="")
    cycles: int | None = Field(default=None, ge=0)
    guard: str = Field(default="")
    text_grounding: List[TextGrounding] = Field(default_factory=list)


class TemporalLatencyConstraint(BaseModel):
    id: str = Field(..., min_length=1)
    start_event_id: str = Field(..., min_length=1)
    end_event_id: str = Field(..., min_length=1)
    cycles: int | None = Field(default=None, ge=0)
    counting_basis: Literal["edge_distance", "inclusive_cycles", "unspecified"] = Field(default="unspecified")
    raw_statement: str = Field(default="")
    status: Literal["resolved", "ambiguous", "unsupported"] = Field(default="resolved")
    text_grounding: List[TextGrounding] = Field(default_factory=list)


class LogicalValueSequence(BaseModel):
    object: str = Field(..., min_length=1)
    tags: List[str] = Field(..., min_length=1)
    text_grounding: List[TextGrounding] = Field(default_factory=list)


class TemporalRelation(BaseModel):
    id: str = Field(..., min_length=1)
    source_id: str = Field(..., min_length=1)
    target_id: str = Field(..., min_length=1)
    relation: TemporalRelationKind
    delay_cycles: int | None = Field(default=None, ge=0)
    guard: str = Field(default="")
    text_grounding: List[TextGrounding] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_delay(self) -> "TemporalRelation":
        if self.relation == "EXACT_CYCLES" and self.delay_cycles is None:
            raise ValueError("EXACT_CYCLES relations require delay_cycles")
        return self


class TemporalInvariant(BaseModel):
    id: str = Field(..., min_length=1)
    statement: str = Field(..., min_length=1)
    event_id: str = Field(default="")
    phase_id: str = Field(default="")
    logical_object: str = Field(default="")
    required_value_tag: str = Field(default="")
    operation: str = Field(default="")
    bypass_operations: List[str] = Field(default_factory=list)
    guard: str = Field(default="")
    text_grounding: List[TextGrounding] = Field(default_factory=list)


class TemporalAmbiguity(BaseModel):
    id: str = Field(..., min_length=1)
    statement: str = Field(..., min_length=1)
    alternatives: List[str] = Field(default_factory=list)
    related_ids: List[str] = Field(default_factory=list)
    text_grounding: List[TextGrounding] = Field(default_factory=list)


class UnsupportedTemporalFeature(BaseModel):
    id: str = Field(..., min_length=1)
    feature: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)
    text_grounding: List[TextGrounding] = Field(default_factory=list)


class GlobalTemporalFactsArtifact(BaseModel):
    schema_version: str = Field(default="global_temporal_facts_v1")
    task_id: str = Field(..., min_length=1)
    input_fingerprint: str = Field(default="")
    planning_status: Literal["complete", "degraded"] = Field(default="complete")
    degradation_reasons: List[str] = Field(default_factory=list)
    clock: TemporalClock = Field(default_factory=TemporalClock)
    reset: TemporalReset = Field(default_factory=TemporalReset)
    events: List[TemporalEvent] = Field(default_factory=list)
    phases: List[TemporalPhase] = Field(default_factory=list)
    latency_constraints: List[TemporalLatencyConstraint] = Field(default_factory=list)
    logical_value_sequences: List[LogicalValueSequence] = Field(default_factory=list)
    relations: List[TemporalRelation] = Field(default_factory=list)
    invariants: List[TemporalInvariant] = Field(default_factory=list)
    ambiguities: List[TemporalAmbiguity] = Field(default_factory=list)
    unsupported_features: List[UnsupportedTemporalFeature] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_references(self) -> "GlobalTemporalFactsArtifact":
        if self.planning_status == "degraded" and not self.degradation_reasons:
            raise ValueError("degraded temporal facts require at least one degradation reason")
        if self.planning_status == "complete" and self.degradation_reasons:
            raise ValueError("complete temporal facts must not contain degradation reasons")
        event_ids = {item.id for item in self.events}
        phase_ids = {item.id for item in self.phases}
        all_ids = [
            *(item.id for item in self.events),
            *(item.id for item in self.phases),
            *(item.id for item in self.latency_constraints),
            *(item.id for item in self.relations),
            *(item.id for item in self.invariants),
            *(item.id for item in self.ambiguities),
            *(item.id for item in self.unsupported_features),
        ]
        if len(all_ids) != len(set(all_ids)):
            raise ValueError("temporal fact IDs must be globally unique")
        for phase in self.phases:
            if phase.trigger_event_id and phase.trigger_event_id not in event_ids:
                raise ValueError(f"phase `{phase.id}` references unknown trigger event `{phase.trigger_event_id}`")
        for latency in self.latency_constraints:
            if latency.start_event_id not in event_ids or latency.end_event_id not in event_ids:
                raise ValueError(f"latency `{latency.id}` references unknown event")
        known_relation_endpoints = event_ids | phase_ids | {item.id for item in self.invariants}
        for relation in self.relations:
            if relation.source_id not in known_relation_endpoints or relation.target_id not in known_relation_endpoints:
                raise ValueError(f"relation `{relation.id}` references unknown endpoint")
        known_tags = {tag for item in self.logical_value_sequences for tag in item.tags}
        for invariant in self.invariants:
            if invariant.event_id and invariant.event_id not in event_ids:
                raise ValueError(f"invariant `{invariant.id}` references unknown event `{invariant.event_id}`")
            if invariant.phase_id and invariant.phase_id not in phase_ids:
                raise ValueError(f"invariant `{invariant.id}` references unknown phase `{invariant.phase_id}`")
            if invariant.required_value_tag and invariant.required_value_tag not in known_tags:
                raise ValueError(
                    f"invariant `{invariant.id}` references unknown logical value tag `{invariant.required_value_tag}`"
                )
        return self


class ModuleTemporalAssignment(BaseModel):
    module: str = Field(..., min_length=1)
    owns_logical_state: List[str] = Field(default_factory=list)
    handles_event_ids: List[str] = Field(default_factory=list)
    handles_phase_ids: List[str] = Field(default_factory=list)


class CrossModuleTimingTransfer(BaseModel):
    id: str = Field(..., min_length=1)
    producer: str = Field(..., min_length=1)
    consumer: str = Field(..., min_length=1)
    logical_object: str = Field(..., min_length=1)
    delivery: Literal["REGISTERED", "COMBINATIONAL"]
    visible_at: TemporalPoint
    sampled_at: TemporalPoint
    required_cycle_offset: int = Field(default=0, ge=0)
    source_temporal_ids: List[str] = Field(..., min_length=1)


class LogicalTimingAccess(BaseModel):
    logical_object: str = Field(..., min_length=1)
    logical_value_tag: str = Field(default="")
    at: TemporalPoint


class ModuleTimingObligation(BaseModel):
    id: str = Field(..., min_length=1)
    module: str = Field(..., min_length=1)
    event_id: str = Field(default="")
    phase_id: str = Field(default="")
    reads: List[LogicalTimingAccess] = Field(default_factory=list)
    writes: List[LogicalTimingAccess] = Field(default_factory=list)
    combinational_outputs: List[LogicalTimingAccess] = Field(default_factory=list)
    latency_cycles: int | None = Field(default=None, ge=0)
    guard: str = Field(default="")
    source_temporal_ids: List[str] = Field(..., min_length=1)


class ArchitectureTimingContractArtifact(BaseModel):
    schema_version: str = Field(default="architecture_timing_contract_v1")
    task_id: str = Field(..., min_length=1)
    input_fingerprint: str = Field(default="")
    planning_status: Literal["complete", "degraded"] = Field(default="complete")
    degradation_reasons: List[str] = Field(default_factory=list)
    module_set: List[str] = Field(..., min_length=1)
    architecture_logical_objects: List[str] = Field(default_factory=list)
    module_assignments: List[ModuleTemporalAssignment] = Field(default_factory=list)
    cross_module_transfers: List[CrossModuleTimingTransfer] = Field(default_factory=list)
    module_obligations: List[ModuleTimingObligation] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_structure(self) -> "ArchitectureTimingContractArtifact":
        if self.planning_status == "degraded" and not self.degradation_reasons:
            raise ValueError("degraded architecture timing requires at least one degradation reason")
        if self.planning_status == "complete" and self.degradation_reasons:
            raise ValueError("complete architecture timing must not contain degradation reasons")
        if len(self.module_set) != len(set(self.module_set)):
            raise ValueError("module_set must not contain duplicates")
        if any(not item.strip() for item in self.architecture_logical_objects):
            raise ValueError("architecture_logical_objects must not contain blank names")
        if len(self.architecture_logical_objects) != len(set(self.architecture_logical_objects)):
            raise ValueError("architecture_logical_objects must not contain duplicates")
        module_set = set(self.module_set)
        assignment_modules = [item.module for item in self.module_assignments]
        if len(assignment_modules) != len(set(assignment_modules)):
            raise ValueError("module_assignments must not contain duplicate modules")
        if set(assignment_modules) != module_set:
            raise ValueError("module_assignments must cover module_set exactly")
        transfer_ids = [item.id for item in self.cross_module_transfers]
        obligation_ids = [item.id for item in self.module_obligations]
        if len(transfer_ids) != len(set(transfer_ids)):
            raise ValueError("cross_module_transfers must not contain duplicate IDs")
        if len(obligation_ids) != len(set(obligation_ids)):
            raise ValueError("module_obligations must not contain duplicate IDs")
        for transfer in self.cross_module_transfers:
            if transfer.producer not in module_set or transfer.consumer not in module_set:
                raise ValueError(f"transfer `{transfer.id}` references a module outside module_set")
            if transfer.producer == transfer.consumer:
                raise ValueError(f"transfer `{transfer.id}` must cross module boundaries")
        for obligation in self.module_obligations:
            if obligation.module not in module_set:
                raise ValueError(f"obligation `{obligation.id}` references a module outside module_set")
        return self


class PhysicalSignalBinding(BaseModel):
    logical_object: str = Field(..., min_length=1)
    physical_signal: str = Field(..., min_length=1)
    kind: Literal["input", "output", "register", "wire"]
    owner_block_id: str = Field(default="")
    logical_value_tags: List[str] = Field(default_factory=list)


class TransferEndpointBinding(BaseModel):
    transfer_id: str = Field(..., min_length=1)
    endpoint: Literal["producer", "consumer"]
    physical_signal: str = Field(..., min_length=1)
    block_id: str = Field(default="")


class BoundTimingAccess(BaseModel):
    signal: str = Field(..., min_length=1)
    at: TemporalPoint
    logical_object: str = Field(..., min_length=1)
    logical_value_tag: str = Field(default="")


class BlockTimingObligationBinding(BaseModel):
    obligation_id: str = Field(..., min_length=1)
    block_id: str = Field(..., min_length=1)
    reads: List[BoundTimingAccess] = Field(default_factory=list)
    writes: List[BoundTimingAccess] = Field(default_factory=list)
    combinational_outputs: List[BoundTimingAccess] = Field(default_factory=list)
    guard: str = Field(default="")


class ModuleTimingBindingArtifact(BaseModel):
    schema_version: str = Field(default="module_timing_binding_v1")
    task_id: str = Field(..., min_length=1)
    module: str = Field(..., min_length=1)
    input_fingerprint: str = Field(default="")
    signal_bindings: List[PhysicalSignalBinding] = Field(default_factory=list)
    transfer_bindings: List[TransferEndpointBinding] = Field(default_factory=list)
    block_obligations: List[BlockTimingObligationBinding] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)


class ModuleTimingBindingRecord(BaseModel):
    module: str = Field(..., min_length=1)
    binding_file: str = Field(..., min_length=1)


class Stage3TimingBindingsArtifact(BaseModel):
    schema_version: str = Field(default="module_timing_bindings_v1")
    task_id: str = Field(..., min_length=1)
    input_fingerprint: str = Field(default="")
    module_order: List[str] = Field(..., min_length=1)
    status: Literal["in_progress", "planned"] = Field(default="planned")
    completed_modules: List[str] = Field(default_factory=list)
    resume_cursor: int = Field(default=0, ge=0)
    module_binding_files: List[ModuleTimingBindingRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_records(self) -> "Stage3TimingBindingsArtifact":
        modules = [item.module for item in self.module_binding_files]
        if not self.completed_modules:
            self.completed_modules = list(modules)
        if not self.resume_cursor:
            self.resume_cursor = len(modules)
        if modules != self.completed_modules:
            raise ValueError("module_binding_files must exactly match completed_modules")
        if modules != self.module_order[: len(modules)]:
            raise ValueError("module_binding_files must be a prefix of module_order")
        if self.resume_cursor != len(modules):
            raise ValueError("resume_cursor must match completed module count")
        if self.status == "planned" and modules != self.module_order:
            raise ValueError("planned timing bindings must cover every module")
        return self


class TimingBindingIssue(BaseModel):
    code: str = Field(..., min_length=1)
    severity: TemporalSeverity
    module: str = Field(default="")
    block_id: str = Field(default="")
    obligation_id: str = Field(default="")
    message: str = Field(..., min_length=1)


class TimingBindingCheckArtifact(BaseModel):
    schema_version: str = Field(default="timing_binding_check_v1")
    task_id: str = Field(..., min_length=1)
    input_fingerprint: str = Field(default="")
    status: Literal["pass", "warning", "fail"] = Field(default="pass")
    issues: List[TimingBindingIssue] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status(self) -> "TimingBindingCheckArtifact":
        expected = (
            "fail"
            if any(item.severity == "ERROR" for item in self.issues)
            else "warning"
            if self.issues
            else "pass"
        )
        if self.status != expected:
            raise ValueError(f"status must be `{expected}` for the supplied issues")
        return self
