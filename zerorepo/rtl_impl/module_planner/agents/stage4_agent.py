from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..prompts import stage4_checklist_eval, stage4_pairwise_tiebreak
from ..schemas import (
    CandidateChecklistResult,
    CandidateEvaluation,
    DeterministicMetrics,
    DeterministicPenalties,
    HardConstraintReport,
    ModuleCandidate,
    PairwisePassResult,
    PairwiseTieBreakResult,
    PairwiseWinner,
    PlannerTaskInput,
    Stage4ScoresArtifact,
    compute_dimension_scores,
    compute_macro_score,
    compute_selection_score,
    rank_candidate_key,
)
from ..utils import extract_explicit_submodule_names
from .base import BaseStageAgent


class _Stage4ChecklistLLMArtifact(BaseModel):
    candidate_id: str = Field(..., min_length=1)
    plan_style: str = Field(..., min_length=1)
    checklists: CandidateChecklistResult


class _Stage4PairwiseLLMArtifact(BaseModel):
    winner: PairwiseWinner
    rationale: List[str] = Field(..., min_length=1)


class Stage4Agent(BaseStageAgent):
    stage_name = "stage4_scores"
    output_model = Stage4ScoresArtifact
    system_role = stage4_checklist_eval.SYSTEM_ROLE
    pairwise_system_role = stage4_pairwise_tiebreak.SYSTEM_ROLE
    pairwise_threshold = 0.25

    def run(self, task_input: Any, partial_artifacts: Dict[str, Any]) -> Stage4ScoresArtifact:
        stage_context = self.context_provider.get_stage_context(
            self.stage_name,
            task_input,
            partial_artifacts,
        )
        candidates = partial_artifacts["stage3"].all_candidates()
        top_module_name = Path(task_input.spec_md_files[0]).stem
        explicit_submodules = sorted(
            extract_explicit_submodule_names(
                spec_md_files=task_input.spec_md_files,
                stage1_artifact=partial_artifacts.get("stage1"),
            )
        )

        evaluations: List[CandidateEvaluation] = []
        for candidate in candidates:
            local_context = {
                **stage_context,
                "candidate_id": candidate.candidate_id,
                "plan_style": candidate.plan_style,
                "top_module_name": top_module_name,
                "hard_preserve_explicit_submodules": explicit_submodules,
            }
            prompt = stage4_checklist_eval.build_prompt(
                candidate_json=self.to_pretty_json(candidate),
                ru_json=self.to_pretty_json(partial_artifacts["stage2"].responsibility_units),
                merge_hint_json=self.to_pretty_json(partial_artifacts["stage2"].merge_hints),
                split_hint_json=self.to_pretty_json(partial_artifacts["stage2"].split_hints),
                boundary_signal_json=self.to_pretty_json(partial_artifacts["stage2"].boundary_signals),
                granularity_profile_json=self.to_pretty_json(partial_artifacts["stage2"].granularity_profile),
                top_module_name=top_module_name,
                explicit_submodules_json=self.to_pretty_json(explicit_submodules),
                stage_context=self.to_pretty_json(local_context),
            )
            self.system_role = stage4_checklist_eval.SYSTEM_ROLE
            self._log_stage_input(prompt=prompt, images=[], stage_context=local_context)
            checklist_artifact = self._invoke_with_repair(
                prompt,
                [],
                task_input,
                partial_artifacts,
                output_model=_Stage4ChecklistLLMArtifact,
                quality_validator=lambda artifact, expected_id=candidate.candidate_id, expected_style=candidate.plan_style: (
                    self._validate_checklist_output(artifact, expected_id, expected_style)
                ),
            )
            self._log_stage_output(checklist_artifact)
            evaluations.append(
                self._build_candidate_evaluation(
                    candidate=candidate,
                    checklists=checklist_artifact.checklists,
                    partial_artifacts=partial_artifacts,
                    top_module_name=top_module_name,
                    explicit_submodules=explicit_submodules,
                )
            )

        ranked = sorted(evaluations, key=rank_candidate_key)
        shortlist = ranked[:3]
        shortlist_candidate_ids = [item.candidate_id for item in shortlist]
        selection_trace = [
            "Ranked candidates by hard_violation_count, deterministic_penalty_total, macro_score, then plan_style/id tie-break.",
            f"Shortlist: {shortlist_candidate_ids}",
        ]

        recommended_candidate_id = shortlist[0].candidate_id
        pairwise_tiebreak = None
        if len(shortlist) >= 2:
            score_delta = abs(shortlist[0].selection_score - shortlist[1].selection_score)
            selection_trace.append(
                f"Top-1 vs Top-2 selection_score delta: {round(score_delta, 3)}"
            )
            if score_delta <= self.pairwise_threshold:
                pairwise_tiebreak = self._run_pairwise_tiebreak(
                    task_input=task_input,
                    partial_artifacts=partial_artifacts,
                    stage_context=stage_context,
                    candidate_a=shortlist[0],
                    candidate_b=shortlist[1],
                    top_module_name=top_module_name,
                    explicit_submodules=explicit_submodules,
                    score_delta=score_delta,
                )
                selection_trace.append(
                    f"Pairwise tie-break triggered for {shortlist[0].candidate_id} vs {shortlist[1].candidate_id}."
                )
                if pairwise_tiebreak.applied and pairwise_tiebreak.final_winner:
                    recommended_candidate_id = pairwise_tiebreak.final_winner
                    selection_trace.append(
                        f"Stable pairwise winner selected: {recommended_candidate_id}"
                    )
                else:
                    selection_trace.append(
                        f"Pairwise result was tie or unstable; keeping shortlist winner {recommended_candidate_id}."
                    )

        artifact = Stage4ScoresArtifact(
            candidate_evaluations=ranked,
            shortlist_candidate_ids=shortlist_candidate_ids,
            recommended_candidate_id=recommended_candidate_id,
            pairwise_tiebreak=pairwise_tiebreak,
            selection_trace=selection_trace,
        )
        quality_errors = self.validate_quality(artifact, task_input, partial_artifacts)
        if quality_errors:
            raise ValueError(
                f"{self.stage_name} output failed quality checks after synthesis: {quality_errors}"
            )
        self.system_role = stage4_checklist_eval.SYSTEM_ROLE
        self._log_stage_output(artifact)
        self.artifact_sink.record_stage_output(self.stage_name, artifact, task_input)
        return artifact

    def build_prompt(
        self,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        stage_context: Dict[str, Any],
    ) -> tuple[str, List[str]]:
        raise NotImplementedError("Stage4Agent uses multi-pass checklist evaluation and pairwise tie-break.")

    def validate_quality(
        self,
        artifact: Stage4ScoresArtifact,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
    ) -> List[str]:
        candidate_map = {item.candidate_id: item for item in partial_artifacts["stage3"].all_candidates()}
        errors: List[str] = []
        evaluation_ids = [item.candidate_id for item in artifact.candidate_evaluations]
        if set(evaluation_ids) != set(candidate_map):
            errors.append(
                f"candidate_evaluations must cover exactly the synthesized candidates; got {sorted(set(evaluation_ids))}"
            )
        if len(evaluation_ids) != len(candidate_map):
            errors.append(f"expected {len(candidate_map)} candidate evaluations, got {len(evaluation_ids)}")
        if len(set(artifact.shortlist_candidate_ids)) != len(artifact.shortlist_candidate_ids):
            errors.append("shortlist_candidate_ids must be unique")

        ranked = sorted(artifact.candidate_evaluations, key=rank_candidate_key)
        expected_shortlist = [item.candidate_id for item in ranked[:3]]
        if artifact.shortlist_candidate_ids != expected_shortlist:
            errors.append(
                f"shortlist_candidate_ids must match the top 3 ranked candidates; expected {expected_shortlist}, got {artifact.shortlist_candidate_ids}"
            )
        if artifact.recommended_candidate_id not in candidate_map:
            errors.append(
                f"recommended_candidate_id {artifact.recommended_candidate_id} does not exist"
            )
            return errors

        expected_recommendation = expected_shortlist[0]
        if artifact.pairwise_tiebreak is not None:
            pairwise = artifact.pairwise_tiebreak
            if pairwise.candidate_a_id != expected_shortlist[0] or pairwise.candidate_b_id != expected_shortlist[1]:
                errors.append("pairwise_tiebreak must compare the first two shortlist candidates")
            if pairwise.score_delta > pairwise.trigger_threshold + 0.001:
                errors.append("pairwise_tiebreak was recorded even though the shortlist delta exceeded the threshold")
            if pairwise.applied:
                if pairwise.unstable_judgment:
                    errors.append("pairwise_tiebreak cannot be applied when unstable_judgment is true")
                if pairwise.final_winner is None:
                    errors.append("pairwise_tiebreak applied must include a final_winner")
                elif artifact.recommended_candidate_id != pairwise.final_winner:
                    errors.append(
                        "recommended_candidate_id must equal the pairwise final_winner when pairwise_tiebreak is applied"
                    )
            else:
                if artifact.recommended_candidate_id != expected_recommendation:
                    errors.append(
                        f"recommended_candidate_id must fall back to shortlist winner {expected_recommendation} when pairwise is not applied"
                    )
        elif artifact.recommended_candidate_id != expected_recommendation:
            errors.append(
                f"recommended_candidate_id must select the shortlist winner {expected_recommendation} when no pairwise tie-break is used"
            )
        if not artifact.selection_trace:
            errors.append("selection_trace must not be empty")
        return errors

    @staticmethod
    def _validate_checklist_output(
        artifact: _Stage4ChecklistLLMArtifact,
        expected_candidate_id: str,
        expected_plan_style: str,
    ) -> List[str]:
        errors: List[str] = []
        if artifact.candidate_id != expected_candidate_id:
            errors.append(
                f"expected candidate_id {expected_candidate_id}, got {artifact.candidate_id}"
            )
        if artifact.plan_style != expected_plan_style:
            errors.append(
                f"expected plan_style {expected_plan_style}, got {artifact.plan_style}"
            )
        return errors

    def _build_candidate_evaluation(
        self,
        *,
        candidate: ModuleCandidate,
        checklists: CandidateChecklistResult,
        partial_artifacts: Dict[str, Any],
        top_module_name: str,
        explicit_submodules: List[str],
    ) -> CandidateEvaluation:
        hard_constraint_report = self._compute_hard_constraint_report(
            candidate=candidate,
            partial_artifacts=partial_artifacts,
            top_module_name=top_module_name,
            explicit_submodules=explicit_submodules,
        )
        deterministic_metrics = self._compute_deterministic_metrics(
            candidate=candidate,
            partial_artifacts=partial_artifacts,
            hard_constraint_report=hard_constraint_report,
            top_module_name=top_module_name,
        )
        deterministic_penalties = self._compute_deterministic_penalties(deterministic_metrics)
        dimension_scores = compute_dimension_scores(checklists)
        macro_score = compute_macro_score(dimension_scores)
        selection_score = compute_selection_score(macro_score, deterministic_penalties.total_penalty)
        return CandidateEvaluation(
            candidate_id=candidate.candidate_id,
            plan_style=candidate.plan_style,
            checklists=checklists,
            dimension_scores=dimension_scores,
            hard_constraint_report=hard_constraint_report,
            deterministic_metrics=deterministic_metrics,
            deterministic_penalties=deterministic_penalties,
            macro_score=macro_score,
            selection_score=selection_score,
        )

    @staticmethod
    def _compute_hard_constraint_report(
        *,
        candidate: ModuleCandidate,
        partial_artifacts: Dict[str, Any],
        top_module_name: str,
        explicit_submodules: List[str],
    ) -> HardConstraintReport:
        module_map = {module.module_name: module for module in candidate.modules}
        ru_map = {
            ru.ru_id: ru for ru in partial_artifacts["stage2"].responsibility_units
        }
        violations: List[str] = []
        warnings: List[str] = []
        helper_tokens = {"helper", "wrapper"}

        top_module = module_map.get(top_module_name)
        if top_module is None:
            violations.append(f"Top module identity {top_module_name} is missing.")
        else:
            if top_module.boundary_authority != "explicit_from_spec":
                violations.append(f"Top module {top_module_name} must be explicit_from_spec.")
            if any(token in top_module.role.lower() for token in helper_tokens):
                violations.append(f"Top module {top_module_name} is downgraded to a helper/wrapper role.")

        for explicit_name in explicit_submodules:
            module = module_map.get(explicit_name)
            if module is None:
                violations.append(f"Explicit submodule {explicit_name} is missing.")
                continue
            if module.boundary_authority != "explicit_from_spec":
                violations.append(
                    f"Explicit submodule {explicit_name} must use boundary_authority explicit_from_spec."
                )
            if any(token in module.role.lower() for token in helper_tokens):
                violations.append(
                    f"Explicit submodule {explicit_name} is downgraded to a helper/wrapper role."
                )

        for module in candidate.modules:
            if (
                module.boundary_authority == "explicit_from_spec"
                and module.module_name not in explicit_submodules
                and module.module_name != top_module_name
            ):
                violations.append(
                    f"Module {module.module_name} claims explicit_from_spec without markdown-explicit evidence."
                )

        for merge_hint in partial_artifacts["stage2"].merge_hints:
            if merge_hint.recommendation != "preserve_explicit_boundary":
                continue
            for ru_id in merge_hint.ru_ids:
                ru = ru_map.get(ru_id)
                if ru is None:
                    continue
                explicit_related = sorted(set(ru.related_submodules) & set(explicit_submodules))
                for submodule_name in explicit_related:
                    module = module_map.get(submodule_name)
                    if module is None:
                        continue
                    if ru_id not in module.evidence_ru_ids:
                        violations.append(
                            f"Explicit boundary {submodule_name} does not carry required RU evidence {ru_id}."
                        )

        for merge_hint in partial_artifacts["stage2"].merge_hints:
            if merge_hint.recommendation not in {"merge_preferred", "high_overlap_keep_together"}:
                continue
            if Stage4Agent._is_merge_hint_split(candidate, merge_hint.ru_ids):
                warnings.append(
                    f"{merge_hint.recommendation} hint {merge_hint.hint_id} is split across multiple modules."
                )

        return HardConstraintReport(
            passed=len(violations) == 0,
            violations=violations,
            warnings=warnings,
        )

    @staticmethod
    def _compute_deterministic_metrics(
        *,
        candidate: ModuleCandidate,
        partial_artifacts: Dict[str, Any],
        hard_constraint_report: HardConstraintReport,
        top_module_name: str,
    ) -> DeterministicMetrics:
        module_count = len(candidate.modules)
        invented_module_count = sum(
            1 for module in candidate.modules if module.boundary_authority == "invented_for_convenience"
        )
        explicit_module_count = sum(
            1 for module in candidate.modules if module.boundary_authority == "explicit_from_spec"
        )
        cross_module_dependency_count = sum(len(module.depends_on) for module in candidate.modules)
        merge_hint_split_count = sum(
            1
            for merge_hint in partial_artifacts["stage2"].merge_hints
            if merge_hint.recommendation in {"merge_preferred", "high_overlap_keep_together"}
            and Stage4Agent._is_merge_hint_split(candidate, merge_hint.ru_ids)
        )
        return DeterministicMetrics(
            module_count=module_count,
            invented_module_count=invented_module_count,
            explicit_module_count=explicit_module_count,
            cross_module_dependency_count=cross_module_dependency_count,
            merge_hint_split_count=merge_hint_split_count,
            hard_violation_count=len(hard_constraint_report.violations),
            top_low_locality_ru_count=Stage4Agent._top_low_locality_ru_count(
                candidate,
                partial_artifacts,
                top_module_name,
            ),
            anti_merge_signal_conflict_count=Stage4Agent._anti_merge_signal_conflict_count(candidate, partial_artifacts),
            evidence_dispersion_count=Stage4Agent._evidence_dispersion_count(candidate, partial_artifacts),
        )

    @staticmethod
    def _compute_deterministic_penalties(
        metrics: DeterministicMetrics,
    ) -> DeterministicPenalties:
        hard_violation_penalty = round(float(metrics.hard_violation_count), 3)
        coupling_split_penalty = round(metrics.merge_hint_split_count * 0.25, 3)
        expected_linear_deps = max(metrics.module_count - 1, 0)
        extra_deps = max(0, metrics.cross_module_dependency_count - expected_linear_deps)
        interface_glue_penalty = round(extra_deps * 0.1, 3)
        locality_absorption_penalty = round(metrics.top_low_locality_ru_count * 0.08, 3)
        anti_merge_penalty = round(metrics.anti_merge_signal_conflict_count * 0.05, 3)
        evidence_dispersion_penalty = round(metrics.evidence_dispersion_count * 0.02, 3)
        total_penalty = round(
            hard_violation_penalty
            + coupling_split_penalty
            + interface_glue_penalty
            + locality_absorption_penalty
            + anti_merge_penalty
            + evidence_dispersion_penalty,
            3,
        )
        return DeterministicPenalties(
            hard_violation_penalty=hard_violation_penalty,
            coupling_split_penalty=coupling_split_penalty,
            interface_glue_penalty=interface_glue_penalty,
            locality_absorption_penalty=locality_absorption_penalty,
            anti_merge_penalty=anti_merge_penalty,
            evidence_dispersion_penalty=evidence_dispersion_penalty,
            total_penalty=total_penalty,
        )

    @staticmethod
    def _is_merge_hint_split(candidate: ModuleCandidate, ru_ids: List[str]) -> bool:
        owning_modules = {
            module.module_name
            for module in candidate.modules
            if any(ru_id in module.evidence_ru_ids for ru_id in ru_ids)
        }
        return len(owning_modules) > 1

    @staticmethod
    def _top_low_locality_ru_count(
        candidate: ModuleCandidate,
        partial_artifacts: Dict[str, Any],
        top_module_name: str,
    ) -> int:
        top_module = next((module for module in candidate.modules if module.module_name == top_module_name), None)
        if top_module is None:
            return 0
        ru_map = {ru.ru_id: ru for ru in partial_artifacts["stage2"].responsibility_units}
        return sum(
            1
            for ru_id in top_module.evidence_ru_ids
            if ru_id in ru_map
            and ru_map[ru_id].locality_score <= 0.65
            and (ru_map[ru_id].boundary_signals or ru_map[ru_id].anti_merge_signals)
        )

    @staticmethod
    def _anti_merge_signal_conflict_count(candidate: ModuleCandidate, partial_artifacts: Dict[str, Any]) -> int:
        ru_map = {ru.ru_id: ru for ru in partial_artifacts["stage2"].responsibility_units}
        split_hints = partial_artifacts["stage2"].split_hints
        count = 0
        for split_hint in split_hints:
            if not Stage4Agent._is_merge_hint_split(candidate, split_hint.ru_ids):
                count += 1
        for module in candidate.modules:
            module_rus = [ru_map[ru_id] for ru_id in module.evidence_ru_ids if ru_id in ru_map]
            if len(module_rus) < 2:
                continue
            if any(ru.anti_merge_signals for ru in module_rus):
                count += 1
        return count

    @staticmethod
    def _evidence_dispersion_count(candidate: ModuleCandidate, partial_artifacts: Dict[str, Any]) -> int:
        ru_map = {ru.ru_id: ru for ru in partial_artifacts["stage2"].responsibility_units}
        count = 0
        for module in candidate.modules:
            module_rus = [ru_map[ru_id] for ru_id in module.evidence_ru_ids if ru_id in ru_map]
            primary_span_ids = {span_id for ru in module_rus for span_id in ru.primary_span_ids}
            section_scopes = {
                Stage4Agent._section_scope_from_span_id(span_id, partial_artifacts)
                for span_id in primary_span_ids
            }
            section_scopes.discard("")
            if len(primary_span_ids) > 3 or len(section_scopes) > 2:
                count += 1
        return count

    @staticmethod
    def _section_scope_from_span_id(span_id: str, partial_artifacts: Dict[str, Any]) -> str:
        esu_map = {span.esu_id: span for span in partial_artifacts["stage1"].evidence_spans}
        span = esu_map.get(span_id)
        if span is None:
            return ""
        parts = [part.strip() for part in str(span.section_path).split(">") if part.strip()]
        return " > ".join(parts[:2]) if parts else "ROOT"

    def _run_pairwise_tiebreak(
        self,
        *,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        stage_context: Dict[str, Any],
        candidate_a: CandidateEvaluation,
        candidate_b: CandidateEvaluation,
        top_module_name: str,
        explicit_submodules: List[str],
        score_delta: float,
    ) -> PairwiseTieBreakResult:
        candidate_map = {
            item.candidate_id: item for item in partial_artifacts["stage3"].all_candidates()
        }
        first_pass = self._invoke_pairwise_pass(
            task_input=task_input,
            partial_artifacts=partial_artifacts,
            stage_context={
                **stage_context,
                "pairwise_order": "A_vs_B",
                "candidate_a_id": candidate_a.candidate_id,
                "candidate_b_id": candidate_b.candidate_id,
            },
            candidate_a=candidate_map[candidate_a.candidate_id],
            candidate_b=candidate_map[candidate_b.candidate_id],
            top_module_name=top_module_name,
            explicit_submodules=explicit_submodules,
        )
        second_pass = self._invoke_pairwise_pass(
            task_input=task_input,
            partial_artifacts=partial_artifacts,
            stage_context={
                **stage_context,
                "pairwise_order": "B_vs_A",
                "candidate_a_id": candidate_b.candidate_id,
                "candidate_b_id": candidate_a.candidate_id,
            },
            candidate_a=candidate_map[candidate_b.candidate_id],
            candidate_b=candidate_map[candidate_a.candidate_id],
            top_module_name=top_module_name,
            explicit_submodules=explicit_submodules,
        )
        mapped_first = self._map_pairwise_winner(
            winner=first_pass.winner,
            candidate_a_id=candidate_a.candidate_id,
            candidate_b_id=candidate_b.candidate_id,
        )
        mapped_second = self._map_pairwise_winner(
            winner=second_pass.winner,
            candidate_a_id=candidate_b.candidate_id,
            candidate_b_id=candidate_a.candidate_id,
        )

        final_winner: Optional[str] = None
        unstable_judgment = False
        applied = False
        if mapped_first == mapped_second and mapped_first not in {None, "tie"}:
            final_winner = mapped_first
            applied = True
        elif mapped_first == "tie" and mapped_second == "tie":
            final_winner = None
        else:
            unstable_judgment = True

        return PairwiseTieBreakResult(
            candidate_a_id=candidate_a.candidate_id,
            candidate_b_id=candidate_b.candidate_id,
            trigger_threshold=self.pairwise_threshold,
            score_delta=round(score_delta, 3),
            first_pass=first_pass,
            second_pass=second_pass,
            final_winner=final_winner,
            unstable_judgment=unstable_judgment,
            applied=applied,
        )

    def _invoke_pairwise_pass(
        self,
        *,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        stage_context: Dict[str, Any],
        candidate_a: ModuleCandidate,
        candidate_b: ModuleCandidate,
        top_module_name: str,
        explicit_submodules: List[str],
    ) -> PairwisePassResult:
        prompt = stage4_pairwise_tiebreak.build_prompt(
            candidate_a_json=self.to_pretty_json(candidate_a),
            candidate_b_json=self.to_pretty_json(candidate_b),
            ru_json=self.to_pretty_json(partial_artifacts["stage2"].responsibility_units),
            merge_hint_json=self.to_pretty_json(partial_artifacts["stage2"].merge_hints),
            top_module_name=top_module_name,
            explicit_submodules_json=self.to_pretty_json(explicit_submodules),
            stage_context=self.to_pretty_json(stage_context),
        )
        self.system_role = self.pairwise_system_role
        self._log_stage_input(prompt=prompt, images=[], stage_context=stage_context)
        llm_artifact = self._invoke_with_repair(
            prompt,
            [],
            task_input,
            partial_artifacts,
            output_model=_Stage4PairwiseLLMArtifact,
            quality_validator=lambda artifact: self._validate_pairwise_output(artifact),
        )
        self._log_stage_output(llm_artifact)
        return PairwisePassResult(
            presentation_order=[candidate_a.candidate_id, candidate_b.candidate_id],
            winner=llm_artifact.winner,
            rationale=llm_artifact.rationale,
        )

    @staticmethod
    def _validate_pairwise_output(artifact: _Stage4PairwiseLLMArtifact) -> List[str]:
        errors: List[str] = []
        if artifact.winner not in {"candidate_a", "candidate_b", "tie"}:
            errors.append(f"winner must be candidate_a, candidate_b, or tie; got {artifact.winner}")
        if not artifact.rationale:
            errors.append("rationale must be non-empty")
        return errors

    @staticmethod
    def _map_pairwise_winner(
        *,
        winner: str,
        candidate_a_id: str,
        candidate_b_id: str,
    ) -> Optional[str]:
        if winner == "candidate_a":
            return candidate_a_id
        if winner == "candidate_b":
            return candidate_b_id
        if winner == "tie":
            return "tie"
        return None
