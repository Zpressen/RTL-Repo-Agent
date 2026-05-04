from __future__ import annotations

from typing import Any, Dict, List

from ..schemas import (
    ModuleSpecBlocks,
    PlannerTaskInput,
    Stage2RepoSkeletonArtifact,
    Stage3ModuleSkeletonArtifact,
    Stage4SpecBlocksArtifact,
)
from ..utils import resolve_module_spec_text, split_spec_blocks
from .base import BaseStageAgent, validate_model


class Stage4SpecBlocksAgent(BaseStageAgent):
    stage_name = "stage4_spec_blocks"
    output_model = Stage4SpecBlocksArtifact

    def run(self, task_input: Any, partial_artifacts: Dict[str, Any]) -> Stage4SpecBlocksArtifact:
        task = task_input if isinstance(task_input, PlannerTaskInput) else validate_model(PlannerTaskInput, task_input)
        repo_skeleton = self._get_repo_skeleton_artifact(partial_artifacts)
        stage3 = self._get_stage3_artifact(partial_artifacts)
        module_order = self._generation_order(repo_skeleton)

        if stage3.module_order != module_order:
            raise ValueError(
                "Stage4 spec block splitting requires stage3.module_order to match "
                "repo_skeleton.planning_decisions.generation_order"
            )

        modules: List[ModuleSpecBlocks] = []
        for module_name in module_order:
            source_file, spec_text = resolve_module_spec_text(module_name, task.spec_md_files)
            blocks = split_spec_blocks(spec_text)
            modules.append(
                ModuleSpecBlocks(
                    module=module_name,
                    source_spec_file=source_file,
                    blocks=blocks,
                )
            )

        artifact = Stage4SpecBlocksArtifact(
            task_id=task.task_id,
            module_order=module_order,
            modules=modules,
        )
        quality_errors = self.validate_quality(artifact, task, partial_artifacts)
        if quality_errors:
            raise ValueError(f"{self.stage_name} output failed quality checks: {quality_errors}")
        self.logger.info(
            "[%s] Split %d module spec(s) into %d block(s)",
            self.stage_name,
            len(artifact.modules),
            sum(len(module.blocks) for module in artifact.modules),
        )
        self.artifact_sink.record_stage_output(self.stage_name, artifact, task)
        return artifact

    def build_prompt(self, task_input: Any, partial_artifacts: Dict[str, Any], stage_context: Dict[str, Any]):
        raise NotImplementedError("Stage4SpecBlocksAgent is deterministic and does not build prompts.")

    def validate_quality(
        self,
        artifact: Stage4SpecBlocksArtifact,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
    ) -> List[str]:
        repo_skeleton = self._get_repo_skeleton_artifact(partial_artifacts)
        expected_order = self._generation_order(repo_skeleton)
        errors: List[str] = []
        if artifact.schema_version != "spec_blocks_v1":
            errors.append("schema_version must remain spec_blocks_v1")
        if artifact.task_id != task_input.task_id:
            errors.append(f"task_id must remain {task_input.task_id}")
        if artifact.module_order != expected_order:
            errors.append("module_order must equal repo_skeleton.planning_decisions.generation_order")
        if [item.module for item in artifact.modules] != artifact.module_order:
            errors.append("modules[].module must exactly match module_order")
        for module in artifact.modules:
            if not module.blocks:
                errors.append(f"{module.module}: blocks must not be empty")
                continue
            for index, block in enumerate(module.blocks, start=1):
                expected_id = f"S{index:03d}"
                if block.block_id != expected_id:
                    errors.append(f"{module.module}: expected block_id {expected_id}, got {block.block_id}")
                if not block.text.strip():
                    errors.append(f"{module.module}: {block.block_id} text must not be empty")
        return errors

    def _generation_order(self, repo_skeleton: Stage2RepoSkeletonArtifact) -> List[str]:
        module_order = [str(item).strip() for item in repo_skeleton.planning_decisions.generation_order if str(item).strip()]
        if not module_order:
            raise ValueError("Stage4 spec block splitting requires repo_skeleton.planning_decisions.generation_order")
        return module_order

    def _get_repo_skeleton_artifact(self, partial_artifacts: Dict[str, Any]) -> Stage2RepoSkeletonArtifact:
        candidate = partial_artifacts.get("stage2")
        if candidate is None:
            raise ValueError("Stage4 spec block splitting requires partial_artifacts['stage2']")
        if isinstance(candidate, Stage2RepoSkeletonArtifact):
            return candidate
        return validate_model(Stage2RepoSkeletonArtifact, candidate)

    def _get_stage3_artifact(self, partial_artifacts: Dict[str, Any]) -> Stage3ModuleSkeletonArtifact:
        candidate = partial_artifacts.get("stage3")
        if candidate is None:
            raise ValueError("Stage4 spec block splitting requires partial_artifacts['stage3']")
        if isinstance(candidate, Stage3ModuleSkeletonArtifact):
            return candidate
        return validate_model(Stage3ModuleSkeletonArtifact, candidate)
