from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from zerorepo.rtl_impl.retrieval_agent import ModuleSpecContextRetrievalResult, ModuleSpecContextRetriever

from ..schemas import (
    ModuleSpecBlocks,
    PlannerTaskInput,
    SpecBlock,
    Stage2RepoSkeletonArtifact,
    Stage3ModuleSkeletonArtifact,
    Stage4SpecBlocksArtifact,
)
from ..utils import split_spec_blocks
from .base import BaseStageAgent, validate_model


class Stage4SpecBlocksAgent(BaseStageAgent):
    stage_name = "stage4_spec_blocks"
    output_model = Stage4SpecBlocksArtifact

    def __init__(
        self,
        llm_client,
        context_provider=None,
        artifact_sink=None,
        logger=None,
        output_root: str | Path | None = None,
        module_spec_context_retriever: ModuleSpecContextRetriever | None = None,
    ):
        super().__init__(llm_client, context_provider, artifact_sink, logger)
        self.output_root = Path(output_root) if output_root is not None else None
        self.module_spec_context_retriever = module_spec_context_retriever or ModuleSpecContextRetriever(
            llm_client,
            logger=self.logger,
        )

    def run(self, task_input: Any, partial_artifacts: Dict[str, Any]) -> Stage4SpecBlocksArtifact:
        task = task_input if isinstance(task_input, PlannerTaskInput) else validate_model(PlannerTaskInput, task_input)
        repo_skeleton = self._get_repo_skeleton_artifact(partial_artifacts)
        stage3 = self._get_stage3_artifact(partial_artifacts)
        module_order = self._generation_order(repo_skeleton)
        repo_module_by_name = {item.module: item for item in repo_skeleton.modules}

        if stage3.module_order != module_order:
            raise ValueError(
                "Stage4 spec block splitting requires stage3.module_order to match "
                "repo_skeleton.planning_decisions.generation_order"
            )

        modules: List[ModuleSpecBlocks] = []
        for module_name in module_order:
            retrieval_result = self._read_stage3_spec_context(stage3, module_name)
            if retrieval_result is None:
                retrieval_result = self.module_spec_context_retriever.select_module_spec_context(
                    module_name=module_name,
                    spec_md_files=task.spec_md_files,
                    repo_module=repo_module_by_name.get(module_name),
                    fact_ledger=self._fact_ledger(partial_artifacts),
                    skeleton_context=self._stage3_module_context(stage3, module_name),
                )
            source_file = next((block.source_file for block in retrieval_result.blocks if block.source_file), "")
            source_file = source_file or self._first_spec_file(task)
            blocks = self._split_retrieved_blocks(retrieval_result)
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

    def _first_spec_file(self, task: PlannerTaskInput) -> str:
        for item in task.spec_md_files:
            if str(item).strip():
                return str(item)
        return "unknown"

    def _stage3_module_context(self, stage3: Stage3ModuleSkeletonArtifact, module_name: str) -> str:
        record = next((item for item in stage3.module_records if item.module == module_name), None)
        if record is None:
            return ""
        return "\n".join(
            [
                f"module: {record.module}",
                f"planning_note: {record.planning_note}",
                f"block_ids: {', '.join(record.block_ids)}",
            ]
        )

    def _read_stage3_spec_context(
        self,
        stage3: Stage3ModuleSkeletonArtifact,
        module_name: str,
    ) -> ModuleSpecContextRetrievalResult | None:
        record = next((item for item in stage3.module_records if item.module == module_name), None)
        if record is None or not str(record.spec_context_file or "").strip():
            return None
        path = self._resolve_output_path(record.spec_context_file)
        if not path.exists() or not path.is_file():
            self.logger.warning(
                "[%s] Missing stage3 spec context sidecar for %s at %s; falling back to live retrieval",
                self.stage_name,
                module_name,
                path,
            )
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            result = validate_model(ModuleSpecContextRetrievalResult, payload)
            if result.module != module_name:
                raise ValueError(f"module must equal {module_name}, got {result.module}")
            return result
        except Exception as exc:
            self.logger.warning(
                "[%s] Invalid stage3 spec context sidecar for %s at %s: %s; falling back to live retrieval",
                self.stage_name,
                module_name,
                path,
                exc,
            )
            return None

    def _split_retrieved_blocks(self, retrieval_result: ModuleSpecContextRetrievalResult) -> List[SpecBlock]:
        split_blocks: List[SpecBlock] = []
        for retrieved in retrieval_result.blocks:
            split_blocks.extend(split_spec_blocks(retrieved.text))
        if not split_blocks:
            split_blocks = [
                SpecBlock(block_id="S001", text="\n\n".join(block.text for block in retrieval_result.blocks).strip())
            ]
        return [
            SpecBlock(block_id=f"S{index:03d}", text=block.text)
            for index, block in enumerate(split_blocks, start=1)
            if block.text.strip()
        ]

    def _resolve_output_path(self, relative_or_absolute: str) -> Path:
        path = Path(relative_or_absolute)
        if path.is_absolute() or self.output_root is None:
            return path
        return (self.output_root / path).resolve()

    def _fact_ledger(self, partial_artifacts: Dict[str, Any]) -> Any | None:
        stage2_input = partial_artifacts.get("stage2_input")
        if stage2_input is not None:
            return getattr(stage2_input, "fact_ledger", None) or (
                stage2_input.get("fact_ledger") if isinstance(stage2_input, dict) else None
            )
        stage1 = partial_artifacts.get("stage1")
        if stage1 is not None:
            return getattr(stage1, "fact_ledger", None) or (
                stage1.get("fact_ledger") if isinstance(stage1, dict) else None
            )
        return None

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
