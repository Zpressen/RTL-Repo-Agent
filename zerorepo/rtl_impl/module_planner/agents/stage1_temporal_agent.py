from __future__ import annotations

from typing import Any, Dict, List

from ..prompts import stage1_temporal_extract
from ..schemas import GlobalTemporalFactsArtifact, PlannerTaskInput, Stage2PlanningInput
from .base import BaseStageAgent, validate_model


class Stage1TemporalAgent(BaseStageAgent):
    stage_name = "stage1_temporal_facts"
    output_model = GlobalTemporalFactsArtifact
    system_role = stage1_temporal_extract.SYSTEM_ROLE
    max_parse_attempts = 2
    max_quality_attempts = 2
    allow_best_effort_quality_fallback = False

    def build_prompt(
        self,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        stage_context: Dict[str, Any],
    ) -> tuple[str, List[str]]:
        stage2_input = self._get_stage2_input(partial_artifacts)
        return (
            stage1_temporal_extract.build_prompt(
                task_id=task_input.task_id,
                source_specs_json=self.to_pretty_json(stage2_input.source_specs),
                stage_context=self.to_pretty_json(stage_context),
            ),
            [],
        )

    def validate_quality(
        self,
        artifact: GlobalTemporalFactsArtifact,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
    ) -> List[str]:
        errors: List[str] = []
        if artifact.schema_version != "global_temporal_facts_v1":
            errors.append("schema_version must remain global_temporal_facts_v1")
        if artifact.task_id != task_input.task_id:
            errors.append(f"task_id must remain {task_input.task_id}")
        return errors

    def _get_stage2_input(self, partial_artifacts: Dict[str, Any]) -> Stage2PlanningInput:
        candidate = partial_artifacts.get("stage2_input")
        if candidate is None:
            raise ValueError("Stage1T requires partial_artifacts['stage2_input']")
        if isinstance(candidate, Stage2PlanningInput):
            return candidate
        return validate_model(Stage2PlanningInput, candidate)
