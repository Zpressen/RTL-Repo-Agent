"""Shared, code-independent contracts for responsibility refinement."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field


class SourceEvidence(BaseModel):
    source_file: str = Field(min_length=1)
    quote: str = Field(min_length=1)
    section_path: str = ""
    start_line: int = Field(default=0, ge=0)
    end_line: int = Field(default=0, ge=0)
    content_hash: str = ""


class StateAccess(BaseModel):
    state_id: str = Field(min_length=1)
    role: Literal["read", "compute_next", "commit", "reset", "hold"]


class StateObject(BaseModel):
    state_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    owner_responsibility_id: str = Field(min_length=1)
    clock_domain: str = "unspecified"
    reset_behavior: str = "unspecified"
    source_refs: list[SourceEvidence] = Field(default_factory=list)


class BehaviorObligation(BaseModel):
    obligation_id: str = Field(min_length=1)
    parent_responsibility_id: str = Field(min_length=1)
    behavior_kind: Literal["functional", "state_update", "reset", "hold", "protocol", "timing", "invariant", "integration"]
    trigger: str = "unspecified"
    guard: str = "unspecified"
    required_effect: str = Field(min_length=1)
    source_refs: list[SourceEvidence] = Field(min_length=1)
    constraint_refs: list[str] = Field(default_factory=list)
    state_accesses: list[StateAccess] = Field(default_factory=list)
    clock_domain: str = "unspecified"
    reset_behavior: str = "unspecified"
    protocol: str = "unspecified"
    timing_relation: str = "unspecified"
    implementation_block_id: str = Field(min_length=1)
    supporting_block_ids: list[str] = Field(default_factory=list)


class TaskPlanningContract(BaseModel):
    state_objects: list[StateObject] = Field(default_factory=list)
    state_accesses: list[StateAccess] = Field(default_factory=list)
    # Full obligations remain structured and are not subject to the short
    # natural-language constraints limit on ModulePlanSubtask.
    obligations: list[BehaviorObligation] = Field(default_factory=list)
    support_only: bool = False
