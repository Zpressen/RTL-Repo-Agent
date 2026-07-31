from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from zerorepo.rtl_impl.retrieval_agent import BlockSpecRetriever
from zerorepo.rtl_impl.retrieval_agent.utils import interface_block_refs

from ..prompts import stage4_module_plan
from ..schemas import (
    ModulePlanArtifact,
    ModulePlanRecord,
    ModuleSpecBlocks,
    ModuleSkeletonExport,
    ModuleTimingBindingArtifact,
    PlannerTaskInput,
    Stage3ModuleSkeletonArtifact,
    Stage3TimingBindingsArtifact,
    Stage4ModulePlansArtifact,
    Stage4SpecBlocksArtifact,
)
from .base import BaseStageAgent, model_dump, validate_model


class Stage4ModulePlanAgent(BaseStageAgent):
    stage_name = "stage4_module_plans"
    output_model = Stage4ModulePlansArtifact
    system_role = stage4_module_plan.SYSTEM_ROLE
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
        block_spec_retriever: BlockSpecRetriever | None = None,
        planning_context_retriever: Any | None = None,
    ):
        super().__init__(llm_client, context_provider, artifact_sink, logger)
        self.output_root = Path(output_root) if output_root is not None else None
        self.block_spec_retriever = block_spec_retriever or BlockSpecRetriever(
            llm_client=self.llm_client,
            logger=self.logger,
        )
        self.planning_context_retriever = planning_context_retriever

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

            skeleton_path = self._resolve_output_path(record_by_module[module_name].doc_file)
            skeleton_markdown = skeleton_path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
            skeleton_blocks = _extract_skeleton_blocks(skeleton_markdown)
            spec_block_ids = {item.block_id for item in module_spec_by_name[module_name].blocks}
            interface_spec_ids = _find_interface_spec_block_ids(module_spec_by_name[module_name])
            skeleton_context = self._read_skeleton_export_context(record_by_module[module_name])
            timing_binding = self._read_timing_binding_for_module(partial_artifacts, module_name)
            timing_by_block = self._timing_requirements_by_block(timing_binding)
            retrieval_result = self.block_spec_retriever.select_block_spec_refs(
                module_name=module_name,
                module_spec=module_spec_by_name[module_name],
                module_skeleton=skeleton_markdown,
                skeleton_blocks=skeleton_blocks,
                skeleton_context=skeleton_context,
            )
            expected_spec_refs_by_id = {
                selection.id: list(selection.spec_refs)
                for selection in retrieval_result.selections
            }
            planning_kg_context = ""
            if self.planning_context_retriever is not None:
                try:
                    context = self.planning_context_retriever.get_module_context(
                        module_name,
                        require_spec=True,
                        require_skeleton=True,
                        expected_fingerprints={
                            "spec_context": str(getattr(stage3, "input_fingerprint", "") or ""),
                            "skeleton": str(getattr(stage3, "input_fingerprint", "") or "")
                        },
                    )
                    planning_kg_context = self.planning_context_retriever.to_prompt_json(context)
                except Exception as exc:
                    mode = str(getattr(self.planning_context_retriever.kg_service, "mode", "required"))
                    if mode == "required":
                        raise
                    self.logger.warning(
                        "[%s] Planning KG context unavailable for %s; using sidecars: %s",
                        self.stage_name,
                        module_name,
                        exc,
                    )
            prompt = stage4_module_plan.build_prompt(
                module_name=module_name,
                module_skeleton=skeleton_markdown,
                module_spec_blocks=self.to_pretty_json(module_spec_by_name[module_name]),
                required_subtasks=self.to_pretty_json(
                    [
                        {
                            "id": block.subtask_id,
                            "target": block.target,
                            "spec_refs": expected_spec_refs_by_id[block.subtask_id],
                            "timing_obligation_ids": timing_by_block.get(block.block_id, {}).get(
                                "timing_obligation_ids", []
                            ),
                            "logical_value_tags": timing_by_block.get(block.block_id, {}).get(
                                "logical_value_tags", []
                            ),
                        }
                        for block in skeleton_blocks
                    ]
                ),
                planning_kg_context=planning_kg_context,
                stage_context=self.to_pretty_json(
                    {
                        "task_id": task.task_id,
                        "module": module_name,
                        "skeleton_doc_file": str(skeleton_path),
                        "module_interface_spec_refs": interface_spec_ids,
                        "block_spec_retrieval_file": self._retrieval_relative_path(module_name),
                        "block_spec_retrieval_fallback_used": retrieval_result.fallback_used,
                    }
                ),
            )
            self.logger.info(
                "[%s] Planning module %s from skeleton doc %s with %d spec block(s)",
                self.stage_name,
                module_name,
                skeleton_path,
                len(spec_block_ids),
            )
            module_plan = self._invoke_with_repair(
                prompt,
                [],
                task,
                partial_artifacts,
                output_model=ModulePlanArtifact,
                quality_validator=lambda artifact, expected_module=module_name, expected_blocks=skeleton_blocks, valid_spec_ids=spec_block_ids, expected_refs=expected_spec_refs_by_id, expected_timing=timing_by_block: (
                    self._validate_module_plan(
                        artifact,
                        expected_module=expected_module,
                        expected_blocks=expected_blocks,
                        valid_spec_ids=valid_spec_ids,
                        expected_spec_refs_by_id=expected_refs,
                        expected_timing_by_block=expected_timing,
                    )
                ),
            )
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
                        "retrieval_payload": model_dump(retrieval_result),
                        "manifest": {
                            "schema_version": "module_plans_v1",
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

    def build_prompt(self, task_input: PlannerTaskInput, partial_artifacts: Dict[str, Any], stage_context: Dict[str, Any]):
        raise NotImplementedError("Stage4ModulePlanAgent uses a custom per-module flow.")

    def validate_quality(
        self,
        artifact: Stage4ModulePlansArtifact,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
    ) -> List[str]:
        stage3 = self._get_stage3_artifact(partial_artifacts)
        errors: List[str] = []
        if artifact.schema_version != "module_plans_v1":
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

    def _validate_module_plan(
        self,
        artifact: ModulePlanArtifact,
        *,
        expected_module: str,
        expected_blocks: List["_SkeletonBlock"],
        valid_spec_ids: set[str],
        expected_spec_refs_by_id: Dict[str, List[str]] | None = None,
        expected_timing_by_block: Dict[str, Dict[str, List[str]]] | None = None,
    ) -> List[str]:
        errors: List[str] = []
        expected_refs = expected_spec_refs_by_id or {}
        expected_timing = expected_timing_by_block or {}
        if artifact.schema_version != "module_plan_v1":
            errors.append("schema_version must remain module_plan_v1")
        if artifact.module != expected_module:
            errors.append(f"module must be {expected_module}")
        if len(artifact.subtasks) != len(expected_blocks):
            errors.append(f"expected {len(expected_blocks)} subtasks, got {len(artifact.subtasks)}")
        for index, expected_block in enumerate(expected_blocks):
            if index >= len(artifact.subtasks):
                break
            subtask = artifact.subtasks[index]
            if subtask.id != expected_block.subtask_id:
                errors.append(f"subtask {index + 1}: id must be {expected_block.subtask_id}")
            if not _target_matches_block(subtask.target, expected_block):
                errors.append(f"{subtask.id}: target must reference skeleton placeholder {expected_block.target}")
            unknown_refs = [item for item in subtask.spec_refs if item not in valid_spec_ids]
            if unknown_refs:
                errors.append(f"{subtask.id}: unknown spec_refs {unknown_refs}")
            if not subtask.spec_refs:
                errors.append(f"{subtask.id}: spec_refs must not be empty")
            if subtask.id in expected_refs and subtask.spec_refs != expected_refs[subtask.id]:
                errors.append(
                    f"{subtask.id}: spec_refs must exactly match block retrieval output {expected_refs[subtask.id]}"
                )
            if len(subtask.constraints) > 3:
                errors.append(f"{subtask.id}: constraints must contain at most 3 items")
            timing_requirement = expected_timing.get(expected_block.block_id, {})
            expected_obligation_ids = timing_requirement.get("timing_obligation_ids", [])
            expected_tags = timing_requirement.get("logical_value_tags", [])
            if subtask.timing_obligation_ids != expected_obligation_ids:
                errors.append(
                    f"{subtask.id}: timing_obligation_ids must exactly match {expected_obligation_ids}"
                )
            if subtask.logical_value_tags != expected_tags:
                errors.append(f"{subtask.id}: logical_value_tags must exactly match {expected_tags}")
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

    def _read_timing_binding_for_module(
        self,
        partial_artifacts: Dict[str, Any],
        module_name: str,
    ) -> ModuleTimingBindingArtifact | None:
        candidate = partial_artifacts.get("timing_bindings")
        if candidate is None:
            return None
        manifest = (
            candidate
            if isinstance(candidate, Stage3TimingBindingsArtifact)
            else validate_model(Stage3TimingBindingsArtifact, candidate)
        )
        record = next((item for item in manifest.module_binding_files if item.module == module_name), None)
        if record is None:
            raise ValueError(f"Stage4 timing bindings missing module `{module_name}`")
        binding_path = self._resolve_output_path(record.binding_file)
        if not binding_path.exists():
            raise FileNotFoundError(f"missing module timing binding sidecar: {binding_path}")
        with open(binding_path, "r", encoding="utf-8") as f:
            return validate_model(ModuleTimingBindingArtifact, json.load(f))

    def _timing_requirements_by_block(
        self,
        binding: ModuleTimingBindingArtifact | None,
    ) -> Dict[str, Dict[str, List[str]]]:
        if binding is None:
            return {}
        result: Dict[str, Dict[str, List[str]]] = {}
        for obligation in binding.block_obligations:
            entry = result.setdefault(
                obligation.block_id,
                {"timing_obligation_ids": [], "logical_value_tags": []},
            )
            entry["timing_obligation_ids"].append(obligation.obligation_id)
            for access in [*obligation.reads, *obligation.writes, *obligation.combinational_outputs]:
                tag = access.logical_value_tag
                if tag and tag not in entry["logical_value_tags"]:
                    entry["logical_value_tags"].append(tag)
        return result

    def _plan_relative_path(self, module_name: str) -> str:
        return f"{self.plans_dirname}/{module_name}.json"

    def _retrieval_relative_path(self, module_name: str) -> str:
        return f"{self.retrieval_dirname}/{module_name}.json"


class _SkeletonBlock:
    def __init__(self, block_id: str, block_label: str, block_kind: str, target: str, raw_text: str):
        self.block_id = block_id
        self.block_label = block_label
        self.block_kind = block_kind
        self.target = target
        self.raw_text = raw_text

    @property
    def subtask_id(self) -> str:
        return f"{self.block_id}_{self.block_label}"


def _extract_skeleton_blocks(skeleton_markdown: str) -> List[_SkeletonBlock]:
    markers = re.findall(r"<block:\s*([^>]+?)\s*>", skeleton_markdown)
    marker_by_key: Dict[str, str] = {}
    for marker in markers:
        marker_text = marker.strip()
        target = f"<block: {marker_text}>"
        marker_by_key.setdefault(marker_text, target)
        marker_by_key.setdefault(_normalize_block_marker(marker_text), target)
    blocks: List[_SkeletonBlock] = []
    for subsection in re.split(r"^###\s+Block\s*$", skeleton_markdown, flags=re.MULTILINE)[1:]:
        block_id_match = re.search(r"^\s*[-*]\s+block_id:\s*(\S+)\s*$", subsection, flags=re.MULTILINE)
        label_match = re.search(r"^\s*[-*]\s+block_label:\s*(\S+)\s*$", subsection, flags=re.MULTILINE)
        kind_match = re.search(r"^\s*[-*]\s+block_kind:\s*(\S+)\s*$", subsection, flags=re.MULTILINE)
        if not block_id_match or not label_match:
            continue
        block_id = block_id_match.group(1).strip()
        block_label = label_match.group(1).strip()
        block_kind = kind_match.group(1).strip() if kind_match else ""
        subtask_id = f"{block_id}_{block_label}"
        target = (
            marker_by_key.get(subtask_id)
            or marker_by_key.get(block_label)
            or marker_by_key.get(_normalize_block_marker(subtask_id))
            or marker_by_key.get(_normalize_block_marker(block_label))
        )
        if target is None:
            target = f"<block: {block_label}>"
        blocks.append(
            _SkeletonBlock(
                block_id=block_id,
                block_label=block_label,
                block_kind=block_kind,
                target=target,
                raw_text=subsection,
            )
        )
    if not blocks:
        raise ValueError("Module skeleton markdown must contain at least one `### Block` subsection")
    return blocks


def _target_matches_block(target: str, expected_block: _SkeletonBlock) -> bool:
    normalized_target = _normalize_block_marker(target)
    candidates = {
        _normalize_block_marker(expected_block.target),
        _normalize_block_marker(expected_block.block_label),
        _normalize_block_marker(expected_block.subtask_id),
    }
    return normalized_target in candidates


def _normalize_block_marker(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")


def _find_interface_spec_block_ids(module_spec: ModuleSpecBlocks) -> List[str]:
    return interface_block_refs(module_spec)
