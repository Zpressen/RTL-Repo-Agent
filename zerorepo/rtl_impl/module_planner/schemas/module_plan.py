from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

PlanStyle = Literal["conservative", "balanced", "aggressive"]
BoundaryAuthority = Literal["explicit_from_spec", "strong_implicit", "invented_for_convenience"]
ChecklistAnswer = Literal["yes", "uncertain", "no"]
PairwiseWinner = Literal["candidate_a", "candidate_b", "tie"]
PLAN_STYLE_ORDER = ("conservative", "balanced", "aggressive")
CHECKLIST_DIMENSIONS = (
    "spec_prior_fidelity",
    "coupling_preservation",
    "codegen_feasibility",
    "interface_naturalness",
    "granularity_economy",
)
CHECKLIST_RUBRIC: Dict[str, Dict[str, str]] = {
    "spec_prior_fidelity": {
        "SPF-1": "Preserve the explicit top-module identity from the spec.",
        "SPF-2": "Preserve explicit submodule names from the spec.",
        "SPF-3": "Cover explicit algorithm steps and core responsibilities.",
        "SPF-4": "Do not demote explicit modules into wrappers or helpers.",
        "SPF-5": "Do not add new main boundaries that conflict with the spec.",
        "SPF-6": "Module responsibilities can be traced back to concrete spec evidence.",
        "SPF-7": "Do not omit explicit I/O-facing responsibilities from the spec.",
        "SPF-8": "Preserve the original top/controller/integrator role described by the spec.",
    },
    "coupling_preservation": {
        "CP-1": "High-strength merge hints are mostly preserved.",
        "CP-2": "Shared-state responsibilities remain within the same or a natural boundary.",
        "CP-3": "Shared timing responsibilities are not split unnaturally.",
        "CP-4": "Same-FSM or same-stage update responsibilities remain tightly coupled.",
        "CP-5": "Special timing branches do not introduce unjustified new boundaries.",
        "CP-6": "Control logic and directly driven critical state updates are not hard-split.",
        "CP-7": "Strong datapath dependency chains are not broken into many tiny modules.",
        "CP-8": "The plan does not split coupling just to look more modular.",
    },
    "codegen_feasibility": {
        "CF-1": "Module count is in a reasonable range for the task.",
        "CF-2": "Each module has enough spec evidence to support standalone generation.",
        "CF-3": "The plan does not contain obviously over-fragmented modules.",
        "CF-4": "The plan does not contain obviously overloaded modules.",
        "CF-5": "Interface count does not imply excessive glue logic.",
        "CF-6": "Dependencies are clear and implementation order is natural.",
        "CF-7": "The plan avoids adjacent modules that must always be generated together.",
        "CF-8": "The split reduces downstream generation burden instead of increasing it.",
    },
    "interface_naturalness": {
        "IN-1": "Interfaces mostly come from spec entities, ports, or signal groups.",
        "IN-2": "The plan avoids overly abstract invented interface names.",
        "IN-3": "The plan avoids generic state_in/state_out/tmp_bus/ctrl_en style interfaces.",
        "IN-4": "Interface boundaries align with responsibility boundaries.",
        "IN-5": "The plan avoids extra intermediate interface layers added only for neatness.",
        "IN-6": "Interfaces map back to concrete protocol, state, or algorithm objects.",
        "IN-7": "Any new interface clearly lowers implementation complexity.",
        "IN-8": "Interface granularity is natural without being too black-box or too leaky.",
    },
    "granularity_economy": {
        "GE-1": "The plan avoids unnecessary convenience modules.",
        "GE-2": "Strongly coupled responsibilities are not hard-split into separate modules.",
        "GE-3": "Only clear structural boundaries are module-ized.",
        "GE-4": "Granularity stays in a balanced range: generatable, understandable, not too fine.",
        "GE-5": "Explicit primitives are not wrapped in needless intermediate layers.",
        "GE-6": "Module responsibilities are complete enough to avoid heavy cross-module stitching.",
        "GE-7": "Spec fidelity is not sacrificed for testability or reuse.",
        "GE-8": "The current granularity is steadier than finer plans and clearer than coarser plans.",
    },
}
CHECKLIST_ITEM_IDS: Dict[str, List[str]] = {
    dimension: list(items.keys()) for dimension, items in CHECKLIST_RUBRIC.items()
}
CHECKLIST_ANSWER_SCORES = {"yes": 1.0, "uncertain": 0.5, "no": 0.0}


class ModulePlan(BaseModel):
    module_name: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    boundary_authority: BoundaryAuthority
    responsibilities: List[str] = Field(..., min_length=1)
    interfaces: List[str] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)
    optional: bool = False
    evidence_ru_ids: List[str] = Field(..., min_length=1)


class ModuleCandidate(BaseModel):
    candidate_id: str = Field(..., min_length=1)
    plan_style: PlanStyle
    summary: str = Field(..., min_length=1)
    modules: List[ModulePlan] = Field(..., min_length=1)


class CandidateBand(BaseModel):
    plan_style: PlanStyle
    candidates: List[ModuleCandidate] = Field(..., min_length=3, max_length=3)


class ChecklistItemResult(BaseModel):
    check_id: str = Field(..., min_length=1)
    answer: ChecklistAnswer
    evidence: str = Field(..., min_length=1)


class CandidateChecklistResult(BaseModel):
    spec_prior_fidelity: List[ChecklistItemResult] = Field(..., min_length=8, max_length=8)
    coupling_preservation: List[ChecklistItemResult] = Field(..., min_length=8, max_length=8)
    codegen_feasibility: List[ChecklistItemResult] = Field(..., min_length=8, max_length=8)
    interface_naturalness: List[ChecklistItemResult] = Field(..., min_length=8, max_length=8)
    granularity_economy: List[ChecklistItemResult] = Field(..., min_length=8, max_length=8)

    @model_validator(mode="after")
    def validate_check_ids(self) -> "CandidateChecklistResult":
        for dimension in CHECKLIST_DIMENSIONS:
            expected = CHECKLIST_ITEM_IDS[dimension]
            actual = [item.check_id for item in getattr(self, dimension)]
            if actual != expected:
                raise ValueError(
                    f"{dimension} must contain checklist ids {expected}, got {actual}"
                )
        return self


class DimensionScores(BaseModel):
    spec_prior_fidelity: float = Field(..., ge=0.0, le=1.0)
    coupling_preservation: float = Field(..., ge=0.0, le=1.0)
    codegen_feasibility: float = Field(..., ge=0.0, le=1.0)
    interface_naturalness: float = Field(..., ge=0.0, le=1.0)
    granularity_economy: float = Field(..., ge=0.0, le=1.0)


class HardConstraintReport(BaseModel):
    passed: bool
    violations: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class DeterministicMetrics(BaseModel):
    module_count: int = Field(..., ge=0)
    invented_module_count: int = Field(..., ge=0)
    explicit_module_count: int = Field(..., ge=0)
    cross_module_dependency_count: int = Field(..., ge=0)
    merge_hint_split_count: int = Field(..., ge=0)
    hard_violation_count: int = Field(..., ge=0)
    top_low_locality_ru_count: int = Field(default=0, ge=0)
    anti_merge_signal_conflict_count: int = Field(default=0, ge=0)
    evidence_dispersion_count: int = Field(default=0, ge=0)


class DeterministicPenalties(BaseModel):
    hard_violation_penalty: float = Field(..., ge=0.0)
    coupling_split_penalty: float = Field(..., ge=0.0)
    interface_glue_penalty: float = Field(..., ge=0.0)
    locality_absorption_penalty: float = Field(default=0.0, ge=0.0)
    anti_merge_penalty: float = Field(default=0.0, ge=0.0)
    evidence_dispersion_penalty: float = Field(default=0.0, ge=0.0)
    total_penalty: float = Field(..., ge=0.0)

    @model_validator(mode="after")
    def validate_total_penalty(self) -> "DeterministicPenalties":
        expected = round(
            self.hard_violation_penalty
            + self.coupling_split_penalty
            + self.interface_glue_penalty,
            3,
        )
        expected = round(
            expected
            + self.locality_absorption_penalty
            + self.anti_merge_penalty
            + self.evidence_dispersion_penalty,
            3,
        )
        if abs(self.total_penalty - expected) > 0.001:
            raise ValueError(
                f"total_penalty must equal the sum of component penalties ({expected}), got {self.total_penalty}"
            )
        return self


class CandidateEvaluation(BaseModel):
    candidate_id: str = Field(..., min_length=1)
    plan_style: PlanStyle
    checklists: CandidateChecklistResult
    dimension_scores: DimensionScores
    hard_constraint_report: HardConstraintReport
    deterministic_metrics: DeterministicMetrics
    deterministic_penalties: DeterministicPenalties
    macro_score: float
    selection_score: float

    @model_validator(mode="after")
    def validate_computed_scores(self) -> "CandidateEvaluation":
        expected_dimensions = compute_dimension_scores(self.checklists)
        for dimension in CHECKLIST_DIMENSIONS:
            actual = getattr(self.dimension_scores, dimension)
            expected = getattr(expected_dimensions, dimension)
            if abs(actual - expected) > 0.001:
                raise ValueError(
                    f"{self.candidate_id} dimension score mismatch for {dimension}: expected {expected}, got {actual}"
                )
        expected_macro = compute_macro_score(self.dimension_scores)
        if abs(self.macro_score - expected_macro) > 0.001:
            raise ValueError(
                f"{self.candidate_id} macro_score mismatch: expected {expected_macro}, got {self.macro_score}"
            )
        expected_selection = compute_selection_score(
            self.macro_score,
            self.deterministic_penalties.total_penalty,
        )
        if abs(self.selection_score - expected_selection) > 0.001:
            raise ValueError(
                f"{self.candidate_id} selection_score mismatch: expected {expected_selection}, got {self.selection_score}"
            )
        if self.hard_constraint_report.passed != (len(self.hard_constraint_report.violations) == 0):
            raise ValueError(
                f"{self.candidate_id} hard_constraint_report.passed must reflect whether violations is empty"
            )
        if self.deterministic_metrics.hard_violation_count != len(self.hard_constraint_report.violations):
            raise ValueError(
                f"{self.candidate_id} hard_violation_count must equal the number of hard violations"
            )
        return self


class PairwisePassResult(BaseModel):
    presentation_order: List[str] = Field(..., min_length=2, max_length=2)
    winner: PairwiseWinner
    rationale: List[str] = Field(..., min_length=1)


class PairwiseTieBreakResult(BaseModel):
    candidate_a_id: str = Field(..., min_length=1)
    candidate_b_id: str = Field(..., min_length=1)
    trigger_threshold: float = Field(..., ge=0.0)
    score_delta: float = Field(..., ge=0.0)
    first_pass: PairwisePassResult
    second_pass: PairwisePassResult
    final_winner: Optional[str] = None
    unstable_judgment: bool = False
    applied: bool = False


class FinalModulePlan(BaseModel):
    task_id: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    modules: List[ModulePlan] = Field(..., min_length=1)
    design_rationale: List[str] = Field(..., min_length=1)
    codegen_hints: List[str] = Field(..., min_length=3)


def answer_to_score(answer: ChecklistAnswer) -> float:
    return CHECKLIST_ANSWER_SCORES[answer]


def score_checklist_dimension(items: List[ChecklistItemResult]) -> float:
    if not items:
        return 0.0
    return round(sum(answer_to_score(item.answer) for item in items) / len(items), 3)


def compute_dimension_scores(checklists: CandidateChecklistResult | dict) -> DimensionScores:
    payload = checklists.model_dump() if isinstance(checklists, BaseModel) else checklists
    return DimensionScores(
        **{
            dimension: score_checklist_dimension(
                [ChecklistItemResult.model_validate(item) for item in payload[dimension]]
            )
            for dimension in CHECKLIST_DIMENSIONS
        }
    )


def compute_macro_score(score_source: DimensionScores | dict) -> float:
    payload = score_source.model_dump() if isinstance(score_source, BaseModel) else score_source
    return round(
        sum(float(payload[dimension]) for dimension in CHECKLIST_DIMENSIONS) / len(CHECKLIST_DIMENSIONS),
        3,
    )


def compute_selection_score(macro_score: float, total_penalty: float) -> float:
    return round(macro_score - total_penalty, 3)


def parse_candidate_index(candidate_id: str) -> int:
    try:
        return int(candidate_id.rsplit("_", 1)[1])
    except (IndexError, ValueError):
        return 9999


def sort_candidate_key(plan_style: str, candidate_id: str) -> tuple[int, int]:
    try:
        style_index = PLAN_STYLE_ORDER.index(plan_style)
    except ValueError:
        style_index = len(PLAN_STYLE_ORDER)
    return (style_index, parse_candidate_index(candidate_id))


def rank_candidate_key(evaluation: CandidateEvaluation) -> tuple[int, float, float, tuple[int, int]]:
    return (
        evaluation.deterministic_metrics.hard_violation_count,
        evaluation.deterministic_penalties.total_penalty,
        -evaluation.macro_score,
        sort_candidate_key(evaluation.plan_style, evaluation.candidate_id),
    )
