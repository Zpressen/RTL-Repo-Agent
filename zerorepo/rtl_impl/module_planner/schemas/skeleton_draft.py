"""Model-owned design fields. Identity, provenance and overlays are compiled."""
from pydantic import BaseModel, ConfigDict, Field
from .module_skeleton import StructuralBlock, ModuleBehaviorSummary, DecisionLedger
from .planning import StateAccess
from typing import Literal


class DraftBlock(StructuralBlock):
    model_config = ConfigDict(extra="forbid")
    placeholder: str = ""


class DraftObligation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    obligation_id: str = Field(min_length=1)
    parent_responsibility_id: str = Field(min_length=1)
    behavior_kind: Literal["functional", "state_update", "reset", "hold", "protocol", "timing", "invariant", "integration"]
    trigger: str = "unspecified"
    guard: str = "unspecified"
    required_effect: str = Field(min_length=1)
    source_evidence_ids: list[str] = Field(min_length=1)
    constraint_refs: list[str] = Field(default_factory=list)
    state_accesses: list[StateAccess] = Field(default_factory=list)
    timing_relation: str = "unspecified"
    implementation_block_id: str = Field(min_length=1)
    supporting_block_ids: list[str] = Field(default_factory=list)


class EvidenceBindingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    responsibility_id: str
    source_evidence_ids: list[str] = Field(min_length=1)
    rationale: str = Field(min_length=1)


class ModuleSkeletonDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    module_frame: str = Field(min_length=1)
    structural_blocks: list[DraftBlock] = Field(min_length=1)
    behavioral_obligations: list[DraftObligation] = Field(min_length=1)
    module_behavior: ModuleBehaviorSummary = Field(default_factory=ModuleBehaviorSummary)
    decision_ledger: DecisionLedger = Field(default_factory=DecisionLedger)
    evidence_binding_requests: list[EvidenceBindingRequest] = Field(default_factory=list)
