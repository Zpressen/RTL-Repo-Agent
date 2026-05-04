from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field

from .atoms import EvidenceSpanUnit, InteractionThread, SpecAtom, TypedResponsibilityAtom
from .contracts import Stage1ContractsArtifact
from .module_plan import CandidateBand, CandidateEvaluation, ModuleCandidate, PairwiseTieBreakResult


class Stage3CandidatesArtifact(BaseModel):
    bands: List[CandidateBand] = Field(..., min_length=3, max_length=3)

    def all_candidates(self) -> List[ModuleCandidate]:
        return [candidate for band in self.bands for candidate in band.candidates]


class Stage4ScoresArtifact(BaseModel):
    candidate_evaluations: List[CandidateEvaluation] = Field(..., min_length=1)
    shortlist_candidate_ids: List[str] = Field(..., min_length=3, max_length=3)
    recommended_candidate_id: str = Field(..., min_length=1)
    pairwise_tiebreak: PairwiseTieBreakResult | None = None
    selection_trace: List[str] = Field(..., min_length=1)
