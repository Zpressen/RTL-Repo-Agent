from __future__ import annotations

from typing import Dict, List, Literal

from pydantic import BaseModel, Field


CouplingStrength = Literal["strong", "medium", "weak"]
Stage2PlanStyle = Literal["conservative", "balanced", "modular"]
BoundaryWidthStatus = Literal["explicit", "derived", "unresolved", "not_applicable"]
DecompositionStatus = Literal[
    "top_locked",
    "responsibilities_extracted",
    "candidates_generated",
    "selected",
    "selected_with_degradation",
    "failed",
]


class LockedTopModule(BaseModel):
    module: str = Field(..., min_length=1)
    resolution_mode: Literal["deterministic", "llm_resolved"]
    evidence_fact_ids: List[str] = Field(default_factory=list)
    evidence_sections: List[str] = Field(default_factory=list)
    rationale: str = Field(default="")


class TopResolutionOutput(BaseModel):
    module: str = Field(..., min_length=1)
    evidence_fact_ids: List[str] = Field(default_factory=list)
    evidence_sections: List[str] = Field(default_factory=list, min_length=1)
    rationale: str = Field(..., min_length=1)


class ResponsibilityDependency(BaseModel):
    target_responsibility_id: str = Field(..., min_length=1)
    coupling_strength: CouplingStrength = Field(default="medium")
    transferred_objects: List[str] = Field(default_factory=list)
    rationale: str = Field(default="")


class ResponsibilityUnit(BaseModel):
    responsibility_id: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    ownership_required: bool = Field(default=True)
    evidence_fact_ids: List[str] = Field(default_factory=list)
    evidence_sections: List[str] = Field(default_factory=list, min_length=1)
    inputs: List[str] = Field(default_factory=list)
    outputs: List[str] = Field(default_factory=list)
    owned_state: List[str] = Field(default_factory=list)
    clock_domain: str = Field(default="")
    reset_behavior: str = Field(default="")
    protocol: str = Field(default="")
    timing_class: str = Field(default="")
    dependencies: List[ResponsibilityDependency] = Field(default_factory=list)
    explicit_module_hint: str = Field(default="")
    reusable: bool = Field(default=False)
    iterative: bool = Field(default=False)


class ResponsibilityLedgerOutput(BaseModel):
    responsibilities: List[ResponsibilityUnit] = Field(..., min_length=1)
    global_clocking_notes: List[str] = Field(default_factory=list)
    global_data_conventions: List[str] = Field(default_factory=list)


class CandidateModule(BaseModel):
    module: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    responsibility_ids: List[str] = Field(..., min_length=1)
    source_kind: Literal[
        "explicit",
        "inferred_from_fact_ledger",
        "inferred_from_spec",
        "compatibility_hint",
    ] = Field(default="inferred_from_spec")
    supporting_fact_ids: List[str] = Field(default_factory=list)
    supporting_sections: List[str] = Field(default_factory=list)
    rationale: str = Field(default="")
    confidence: str = Field(default="")
    reused: bool = Field(default=False)


class CandidateHierarchyEdge(BaseModel):
    parent: str = Field(..., min_length=1)
    child: str = Field(..., min_length=1)
    source_kind: Literal[
        "explicit",
        "inferred_from_fact_ledger",
        "inferred_from_spec",
    ] = Field(default="inferred_from_spec")
    supporting_fact_ids: List[str] = Field(default_factory=list)
    rationale: str = Field(default="")
    confidence: str = Field(default="")


class LogicalBoundaryContract(BaseModel):
    boundary_id: str = Field(..., min_length=1)
    producer_module: str = Field(..., min_length=1)
    consumer_module: str = Field(..., min_length=1)
    producer_responsibility_ids: List[str] = Field(..., min_length=1)
    consumer_responsibility_ids: List[str] = Field(..., min_length=1)
    transferred_objects: List[str] = Field(..., min_length=1)
    direction: str = Field(..., min_length=1)
    protocol: str = Field(default="")
    timing_class: str = Field(default="")
    clock_domain: str = Field(default="")
    reset_behavior: str = Field(default="")
    width_status: BoundaryWidthStatus = Field(default="unresolved")
    width_evidence: List[str] = Field(default_factory=list)
    evidence_fact_ids: List[str] = Field(default_factory=list)
    evidence_sections: List[str] = Field(default_factory=list)
    rationale: str = Field(default="")


class Stage2DecompositionCandidate(BaseModel):
    candidate_id: str = Field(..., min_length=1)
    plan_style: Stage2PlanStyle
    top_module: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    modules: List[CandidateModule] = Field(..., min_length=1)
    hierarchy: List[CandidateHierarchyEdge] = Field(default_factory=list)
    boundary_contracts: List[LogicalBoundaryContract] = Field(default_factory=list)
    global_clocking_notes: List[str] = Field(default_factory=list)
    global_data_conventions: List[str] = Field(default_factory=list)
    open_issues: List[str] = Field(default_factory=list)


class CandidateDimensionScores(BaseModel):
    responsibility_evidence_coverage: float = Field(..., ge=0.0, le=1.0)
    coupling_preservation: float = Field(..., ge=0.0, le=1.0)
    interface_completeness_naturalness: float = Field(..., ge=0.0, le=1.0)
    codegen_feasibility: float = Field(..., ge=0.0, le=1.0)
    granularity_economy: float = Field(..., ge=0.0, le=1.0)


class Stage2CandidateEvaluation(BaseModel):
    candidate_id: str = Field(..., min_length=1)
    plan_style: Stage2PlanStyle
    fatal_violations: List[str] = Field(default_factory=list)
    hard_violations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    # Retained as optional compatibility fields for stage2_decomposition_v1 readers.
    # The v3 selection policy does not produce or consume scalar architecture scores.
    dimension_scores: CandidateDimensionScores | None = Field(default=None, exclude=True)
    total_score: float | None = Field(default=None, ge=0.0, le=1.0, exclude=True)
    metrics: dict = Field(default_factory=dict)


class Stage2RankingDecisionOutput(BaseModel):
    ranked_candidate_ids: List[str] = Field(..., min_length=1)
    winner_candidate_id: str = Field(..., min_length=1)
    candidate_assessments: Dict[str, List[str]] = Field(default_factory=dict)
    rationale: List[str] = Field(..., min_length=1)


class Stage2SelectionPass(BaseModel):
    presentation_order: List[str] = Field(default_factory=list)
    ranked_candidate_ids: List[str] = Field(default_factory=list)
    winner_candidate_id: str = Field(default="")
    candidate_assessments: Dict[str, List[str]] = Field(default_factory=dict)
    rationale: List[str] = Field(default_factory=list)
    error: str = Field(default="")


class Stage2AdjudicationDecisionOutput(BaseModel):
    winner_candidate_id: str = Field(..., min_length=1)
    rationale: List[str] = Field(..., min_length=1)


class Stage2AdjudicationPass(BaseModel):
    candidate_ids: List[str] = Field(default_factory=list)
    winner_candidate_id: str = Field(default="")
    rationale: List[str] = Field(default_factory=list)
    error: str = Field(default="")


class Stage2SelectionResult(BaseModel):
    eligible_candidate_ids: List[str] = Field(default_factory=list)
    first_pass: Stage2SelectionPass | None = None
    second_pass: Stage2SelectionPass | None = None
    adjudication: Stage2AdjudicationPass | None = None
    fallback_used: bool = Field(default=False)
    fallback_reason: str = Field(default="")
    final_winner_candidate_id: str = Field(default="")
    final_reason: str = Field(default="")


class Stage2PairwisePass(BaseModel):
    presentation_order: List[str] = Field(..., min_length=2, max_length=2)
    winner_candidate_id: str = Field(..., min_length=1)
    rationale: List[str] = Field(..., min_length=1)


class Stage2PairwiseDecisionOutput(BaseModel):
    winner_candidate_id: str = Field(..., min_length=1)
    rationale: List[str] = Field(..., min_length=1)


class Stage2PairwiseResult(BaseModel):
    candidate_a_id: str = Field(..., min_length=1)
    candidate_b_id: str = Field(..., min_length=1)
    trigger_threshold: float = Field(default=0.05, ge=0.0)
    score_delta: float = Field(..., ge=0.0)
    first_pass: Stage2PairwisePass
    second_pass: Stage2PairwisePass
    applied: bool = Field(default=False)
    final_winner_candidate_id: str = Field(default="")
    unstable_judgment: bool = Field(default=False)


class Stage2DecompositionArtifact(BaseModel):
    schema_version: str = Field(default="stage2_decomposition_v1")
    task_id: str = Field(..., min_length=1)
    input_fingerprint: str = Field(default="")
    status: DecompositionStatus = Field(default="top_locked")
    locked_top: LockedTopModule
    responsibilities: List[ResponsibilityUnit] = Field(default_factory=list)
    global_clocking_notes: List[str] = Field(default_factory=list)
    global_data_conventions: List[str] = Field(default_factory=list)
    candidates: List[Stage2DecompositionCandidate] = Field(default_factory=list)
    evaluations: List[Stage2CandidateEvaluation] = Field(default_factory=list)
    selected_candidate_id: str = Field(default="")
    selected_boundary_contracts: List[LogicalBoundaryContract] = Field(default_factory=list)
    selection_result: Stage2SelectionResult | None = None
    pairwise_result: Stage2PairwiseResult | None = None
    selection_trace: List[str] = Field(default_factory=list)
    failure_reasons: List[str] = Field(default_factory=list)

    def selected_candidate(self) -> Stage2DecompositionCandidate | None:
        return next(
            (item for item in self.candidates if item.candidate_id == self.selected_candidate_id),
            None,
        )
