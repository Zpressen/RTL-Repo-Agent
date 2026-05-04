from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from .common import (
    AtomScope,
    AtomType,
    EvidenceRole,
    EvidenceSpanKind,
    LocalDomainTag,
    ResponsibilityAtomType,
    SourceModality,
)


class EvidenceSpanUnit(BaseModel):
    esu_id: str = Field(..., min_length=1)
    section_path: str = Field(..., min_length=1)
    source_file: str = Field(..., min_length=1)
    source_modality: SourceModality
    span_kind: EvidenceSpanKind
    evidence_role: EvidenceRole = EvidenceRole.CONTENT
    raw_span: str = Field(..., min_length=1)
    entities: List[str] = Field(default_factory=list)
    neighbor_esu_ids: List[str] = Field(default_factory=list)
    local_domain_tags: List[LocalDomainTag] = Field(default_factory=list)
    region_label: Optional[str] = None
    table_context: Optional[str] = None


class TypedResponsibilityAtom(BaseModel):
    atom_id: str = Field(..., min_length=1)
    atom_type: ResponsibilityAtomType
    atom_scope: AtomScope = AtomScope.STEP
    text: str = Field(..., min_length=1)
    source_esu_id: str = Field(..., min_length=1)
    source_file: str = Field(..., min_length=1)
    source_section: str = Field(..., min_length=1)
    related_entities: List[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def infer_atom_scope(self) -> "TypedResponsibilityAtom":
        if self.atom_scope != AtomScope.STEP:
            return self
        inferred = {
            ResponsibilityAtomType.INTERFACE_BUNDLE: AtomScope.BUNDLE,
            ResponsibilityAtomType.STATE_CLUSTER: AtomScope.CLUSTER,
            ResponsibilityAtomType.CONTROL_MODE: AtomScope.MODE,
            ResponsibilityAtomType.PROTOCOL_EXCHANGE: AtomScope.BUNDLE,
            ResponsibilityAtomType.BEHAVIOR_STEP: AtomScope.STEP,
            ResponsibilityAtomType.CONFIG_GATE: AtomScope.CONSTRAINT,
            ResponsibilityAtomType.SUBMODULE_HINT: AtomScope.HINT,
            ResponsibilityAtomType.CONSTRAINT_OR_TEMPORAL: AtomScope.CONSTRAINT,
        }.get(self.atom_type, AtomScope.STEP)
        self.atom_scope = inferred
        return self


class InteractionThread(BaseModel):
    thread_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    supporting_esu_ids: List[str] = Field(..., min_length=1)
    supporting_atom_ids: List[str] = Field(default_factory=list)
    domain_tags: List[LocalDomainTag] = Field(default_factory=list)
    ordered_steps: List[str] = Field(..., min_length=1)
    entry_conditions: List[str] = Field(default_factory=list)
    terminal_conditions: List[str] = Field(default_factory=list)


class SpecAtom(BaseModel):
    atom_id: str = Field(..., min_length=1)
    atom_type: AtomType
    text: str = Field(..., min_length=1)
    source_file: str = Field(..., min_length=1)
    source_section: str = Field(..., min_length=1)
    related_entities: List[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
