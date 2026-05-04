from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field, model_validator


PacketType = Literal["module_local", "bridge"]
RFURelationType = Literal["containment", "instantiates", "feeds", "reuse", "stage"]


class QualityReport(BaseModel):
    hard_fail_count: int = Field(default=0, ge=0)
    soft_warning_count: int = Field(default=0, ge=0)
    warnings: List[str] = Field(default_factory=list)
    auto_fixes: List[str] = Field(default_factory=list)


class RFUPacketSummary(BaseModel):
    packet_id: str = Field(..., min_length=1)
    packet_type: PacketType
    module_scope: List[str] = Field(..., min_length=1)
    seed_fragment_ids: List[str] = Field(..., min_length=1)
    context_fragment_ids: List[str] = Field(default_factory=list)
    focus_fragment_ids: List[str] = Field(..., min_length=1)
    focus_image_ids: List[str] = Field(default_factory=list)
    focus_image_region_ids: List[str] = Field(default_factory=list)
    canonical_entities: List[str] = Field(default_factory=list)
    packet_rationale: str = Field(..., min_length=1)


class RepositoryFunctionalUnit(BaseModel):
    rfu_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    implementation_role: str = Field(..., min_length=1)
    functional_boundary: str = Field(..., min_length=1)
    module_scope: List[str] = Field(..., min_length=1)
    supporting_fragment_ids: List[str] = Field(..., min_length=1)
    supporting_image_ids: List[str] = Field(default_factory=list)
    supporting_image_region_ids: List[str] = Field(default_factory=list)
    anchor_entities: List[str] = Field(default_factory=list)
    canonical_entities: List[str] = Field(default_factory=list)
    locality_rationale: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)


class RFURelation(BaseModel):
    relation_id: str = Field(..., min_length=1)
    relation_type: RFURelationType
    source_rfu_id: str = Field(..., min_length=1)
    target_rfu_id: str = Field(..., min_length=1)
    rationale: str = Field(..., min_length=1)
    supporting_fragment_ids: List[str] = Field(default_factory=list)
    supporting_image_region_ids: List[str] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_distinct_endpoints(self) -> "RFURelation":
        if self.source_rfu_id == self.target_rfu_id:
            raise ValueError("RFU relations must not be self-loops")
        return self
