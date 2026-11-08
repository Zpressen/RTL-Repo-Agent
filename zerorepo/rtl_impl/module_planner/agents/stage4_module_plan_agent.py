from __future__ import annotations

from zerorepo.rtl_impl.artifact_layout import ArtifactLayout

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


from ..schemas import (
    ModulePlanRecord,
    ModuleSkeletonExport,
    PlannerTaskInput,
    Stage3ModuleSkeletonArtifact,
    Stage4ModulePlansArtifact,
    Stage4SpecBlocksArtifact,
)
from .base import BaseStageAgent, model_dump, validate_model
from ..utils.responsibility_planning import module_context, refinement_issues


class Stage4ModulePlanAgent(BaseStageAgent):
    stage_name = "stage4_module_plans"
    output_model = Stage4ModulePlansArtifact
    system_role = "Deterministic Stage3 task assembly"
    allow_best_effort_quality_fallback = False
    plans_dirname = "module_plan_json"
    retrieval_dirname = "block_spec_retrieval_json"

    def __init__(
        self,
        llm_client,
        context_provider=None,
        artifact_sink=None,
        logger=None,
        output_root: str | Path | None = None,
        planning_context_retriever: Any | None = None,
    ):
        super().__init__(llm_client, context_provider, artifact_sink, logger)
        self.output_root = Path(output_root) if output_root is not None else None
        self.planning_context_retriever = planning_context_retriever
        self.cache_enabled = True

    def run(self, task_input: Any, partial_artifacts: Dict[str, Any]) -> Stage4ModulePlansArtifact:
        return self.run_incremental(task_input, partial_artifacts)

    def run_incremental(
        self,
        task_input: Any,
        partial_artifacts: Dict[str, Any],
        persist_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Stage4ModulePlansArtifact:
        task = task_input if isinstance(task_input, PlannerTaskInput) else validate_model(PlannerTaskInput, task_input)
        stage3 = self._get_stage3_artifact(partial_artifacts)
        spec_blocks = self._get_spec_blocks_artifact(partial_artifacts)
        module_spec_by_name = {item.module: item for item in spec_blocks.modules}
        record_by_module = {item.module: item for item in stage3.module_records}

        records: List[ModulePlanRecord] = []
        existing_artifact = self._get_existing_stage4_artifact(partial_artifacts)
        if existing_artifact is not None:
            if existing_artifact.task_id != task.task_id:
                raise ValueError(f"Stage4 resume artifact task_id must remain {task.task_id}")
            if existing_artifact.module_order != stage3.module_order:
                raise ValueError("Stage4 resume artifact module_order must match stage3.module_order")
            records.extend(existing_artifact.module_plan_files)
            self.logger.info(
                "[%s] Reusing %d completed module plan checkpoint(s)",
                self.stage_name,
                len(records),
            )
        for module_name in stage3.module_order[len(records) :]:
            if module_name not in module_spec_by_name:
                raise ValueError(f"Stage4 module planning requires spec blocks for `{module_name}`")
            if module_name not in record_by_module:
                raise ValueError(f"Stage4 module planning requires skeleton record for `{module_name}`")

            skeleton_context = self._read_skeleton_export_context(record_by_module[module_name])
            if skeleton_context is None or skeleton_context.schema_version != "module_skeleton_export_v3":
                raise ValueError(f"{module_name}: Stage4 requires authoritative v3 skeleton JSON")
            issues = refinement_issues(skeleton_context, module_context(partial_artifacts["stage2_decomposition"], module_name), partial_artifacts["stage2_input"])
            if issues:
                raise ValueError(f"{module_name}: invalid Stage3 refinement: {[i.message for i in issues]}")
            from ..utils.task_assembly import assemble_plan
            module_plan, retrieval_payload = assemble_plan(skeleton_context, module_spec_by_name[module_name])
            self.logger.info("[%s] Assembled %d tasks for %s without an LLM request", self.stage_name, len(module_plan.subtasks), module_name)
            plan_file = self._plan_relative_path(module_name)
            retrieval_file = self._retrieval_relative_path(module_name)
            records.append(ModulePlanRecord(module=module_name, plan_file=plan_file))
            if persist_callback is not None:
                persist_callback(
                    {
                        "module": module_name,
                        "task": task,
                        "input_fingerprint": str(partial_artifacts.get("stage4_input_fingerprint") or ""),
                        "plan_file": plan_file,
                        "plan_payload": model_dump(module_plan),
                        "retrieval_file": retrieval_file,
                        "retrieval_payload": retrieval_payload,
                        "manifest": {
                            "schema_version": "module_plans_v3",
                            "task_id": task.task_id,
                            "input_fingerprint": str(partial_artifacts.get("stage4_input_fingerprint") or ""),
                            "module_order": list(stage3.module_order),
                            "stage4_status": "module_plans_in_progress",
                            "completed_modules": [item.module for item in records],
                            "resume_cursor": len(records),
                            "module_plan_files": [model_dump(item) for item in records],
                        },
                    }
                )

        artifact = Stage4ModulePlansArtifact(
            schema_version="module_plans_v3",
            task_id=task.task_id,
            input_fingerprint=str(partial_artifacts.get("stage4_input_fingerprint") or ""),
            module_order=list(stage3.module_order),
            stage4_status="module_plans_planned",
            completed_modules=[item.module for item in records],
            resume_cursor=len(records),
            module_plan_files=records,
        )
        quality_errors = self.validate_quality(artifact, task, partial_artifacts)
        if quality_errors:
            raise ValueError(f"{self.stage_name} output failed quality checks: {quality_errors}")
        self.logger.info("[%s] Planned %d module(s)", self.stage_name, len(artifact.module_plan_files))
        if persist_callback is not None:
            persist_callback({"manifest": model_dump(artifact)})
        self.artifact_sink.record_stage_output(self.stage_name, artifact, task)
        return artifact

    def validate_quality(
        self,
        artifact: Stage4ModulePlansArtifact,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
    ) -> List[str]:
        stage3 = self._get_stage3_artifact(partial_artifacts)
        errors: List[str] = []
        if artifact.schema_version not in {"module_plans_v3"}:
            errors.append("schema_version must remain module_plans_v1")
        if artifact.task_id != task_input.task_id:
            errors.append(f"task_id must remain {task_input.task_id}")
        if artifact.module_order != stage3.module_order:
            errors.append("module_order must match stage3.module_order")
        modules = [item.module for item in artifact.module_plan_files]
        if artifact.completed_modules != modules:
            errors.append("completed_modules must exactly match module_plan_files[].module order")
        if modules != artifact.module_order[: len(modules)]:
            errors.append("module_plan_files[].module must be a prefix of module_order")
        if artifact.resume_cursor != len(modules):
            errors.append("resume_cursor must match completed module plan count")
        if artifact.stage4_status == "module_plans_planned" and modules != artifact.module_order:
            errors.append("final module_plan_files[].module must exactly match module_order")
        for record in artifact.module_plan_files:
            expected_file = self._plan_relative_path(record.module)
            if record.plan_file != expected_file:
                errors.append(f"{record.module}: plan_file must be {expected_file}")
        return errors

    def _get_stage3_artifact(self, partial_artifacts: Dict[str, Any]) -> Stage3ModuleSkeletonArtifact:
        candidate = partial_artifacts.get("stage3")
        if candidate is None:
            raise ValueError("Stage4 module planning requires partial_artifacts['stage3']")
        if isinstance(candidate, Stage3ModuleSkeletonArtifact):
            return candidate
        return validate_model(Stage3ModuleSkeletonArtifact, candidate)

    def _get_spec_blocks_artifact(self, partial_artifacts: Dict[str, Any]) -> Stage4SpecBlocksArtifact:
        candidate = partial_artifacts.get("spec_blocks")
        if candidate is None:
            raise ValueError("Stage4 module planning requires partial_artifacts['spec_blocks']")
        if isinstance(candidate, Stage4SpecBlocksArtifact):
            return candidate
        return validate_model(Stage4SpecBlocksArtifact, candidate)

    def _get_existing_stage4_artifact(self, partial_artifacts: Dict[str, Any]) -> Stage4ModulePlansArtifact | None:
        candidate = partial_artifacts.get("stage4_existing")
        if candidate is None:
            return None
        if isinstance(candidate, Stage4ModulePlansArtifact):
            return candidate
        return validate_model(Stage4ModulePlansArtifact, candidate)

    def _resolve_output_path(self, relative_or_absolute: str) -> Path:
        path = Path(relative_or_absolute)
        if path.is_absolute() or self.output_root is None:
            return path
        return (self.output_root / path).resolve()

    def _read_skeleton_export_context(self, record: Any) -> Any | None:
        export_file = getattr(record, "export_file", None)
        if not export_file:
            return None

        export_path = self._resolve_output_path(str(export_file))
        if not export_path.exists():
            self.logger.warning("[%s] Module skeleton export is missing: %s", self.stage_name, export_path)
            return None
        try:
            with open(export_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            return validate_model(ModuleSkeletonExport, payload)
        except Exception as exc:  # noqa: BLE001 - structured context is optional for retrieval.
            self.logger.warning(
                "[%s] Ignoring invalid module skeleton export at %s: %s",
                self.stage_name,
                export_path,
                exc,
            )
            return None

    def _plan_relative_path(self, module_name: str) -> str:
        return ArtifactLayout(self.output_root or Path(".")).module_relative(4, module_name, "plan.json")

    def _retrieval_relative_path(self, module_name: str) -> str:
        return ArtifactLayout(self.output_root or Path(".")).module_relative(4, module_name, "spec_refs.json")
