from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..prompts import stage5_subtask_codegen
from ..schemas import (
    ModuleCodegenRecord,
    ModulePlanArtifact,
    ModulePlanSubtask,
    ModuleSpecBlocks,
    PlannerTaskInput,
    Stage3ModuleSkeletonArtifact,
    Stage4ModulePlansArtifact,
    Stage4SpecBlocksArtifact,
    Stage5CodegenArtifact,
    SubtaskCodeArtifact,
)
from .base import BaseStageAgent, model_dump, validate_model


class Stage5Agent(BaseStageAgent):
    stage_name = "stage5_codegen"
    output_model = Stage5CodegenArtifact
    system_role = stage5_subtask_codegen.SYSTEM_ROLE
    allow_best_effort_quality_fallback = False
    workspace_dirname = "workspace"

    def __init__(
        self,
        llm_client,
        context_provider=None,
        artifact_sink=None,
        logger=None,
        output_root: str | Path | None = None,
        workspace_root: str | Path | None = None,
    ):
        super().__init__(llm_client, context_provider, artifact_sink, logger)
        self.output_root = Path(output_root) if output_root is not None else None
        self.workspace_root = Path(workspace_root) if workspace_root is not None else self._default_workspace_root()

    def run(self, task_input: Any, partial_artifacts: Dict[str, Any]) -> Stage5CodegenArtifact:
        return self.run_incremental(task_input, partial_artifacts)

    def run_incremental(
        self,
        task_input: Any,
        partial_artifacts: Dict[str, Any],
        persist_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Stage5CodegenArtifact:
        task = task_input if isinstance(task_input, PlannerTaskInput) else validate_model(PlannerTaskInput, task_input)
        stage4 = self._get_stage4_artifact(partial_artifacts)
        spec_blocks = self._get_spec_blocks_artifact(partial_artifacts)
        module_order = list(spec_blocks.module_order)
        spec_by_module = {item.module: item for item in spec_blocks.modules}
        plan_record_by_module = {item.module: item for item in stage4.module_plan_files}

        self._validate_inputs(module_order, spec_by_module, plan_record_by_module)

        records: List[ModuleCodegenRecord] = []
        for module_name in module_order:
            records.append(self.run_module(task, partial_artifacts, module_name))

        artifact = Stage5CodegenArtifact(
            task_id=task.task_id,
            module_order=module_order,
            module_files=records,
        )
        quality_errors = self.validate_quality(artifact, task, partial_artifacts)
        if quality_errors:
            raise ValueError(f"{self.stage_name} output failed quality checks: {quality_errors}")
        if persist_callback is not None:
            persist_callback({"manifest": model_dump(artifact)})
        self.artifact_sink.record_stage_output(self.stage_name, artifact, task)
        return artifact

    def run_module(
        self,
        task_input: Any,
        partial_artifacts: Dict[str, Any],
        module_name: str,
    ) -> ModuleCodegenRecord:
        task = task_input if isinstance(task_input, PlannerTaskInput) else validate_model(PlannerTaskInput, task_input)
        stage4 = self._get_stage4_artifact(partial_artifacts)
        spec_blocks = self._get_spec_blocks_artifact(partial_artifacts)
        stage3 = self._get_stage3_artifact(partial_artifacts)
        spec_by_module = {item.module: item for item in spec_blocks.modules}
        plan_record_by_module = {item.module: item for item in stage4.module_plan_files}
        skeleton_record_by_module = {item.module: item for item in stage3.module_records} if stage3 is not None else {}

        if module_name not in spec_by_module:
            raise ValueError(f"Stage5 missing spec blocks for module `{module_name}`")
        if module_name not in plan_record_by_module:
            raise ValueError(f"Stage5 missing module plan for `{module_name}`")

        module_spec = spec_by_module[module_name]
        module_interface_blocks = self._select_interface_spec_blocks(module_spec)
        module_plan = self._read_module_plan(plan_record_by_module[module_name].plan_file)
        if module_plan.module != module_name:
            raise ValueError(f"Stage5 expected module plan for `{module_name}`, got `{module_plan.module}`")
        module_skeleton, module_skeleton_file = self._read_module_skeleton_context(
            skeleton_record_by_module.get(module_name)
        )

        workspace_file = self._workspace_file(module_name)
        completed_subtasks: List[str] = []
        for subtask in module_plan.subtasks:
            previous_snippets = self._read_text_if_exists(workspace_file)
            selected_blocks = self._select_spec_blocks(module_spec, subtask.spec_refs)
            selected_block_ids = {item["block_id"] for item in selected_blocks}
            supplemental_interface_blocks = [
                item for item in module_interface_blocks if item["block_id"] not in selected_block_ids
            ]
            stage_context = {
                "task_id": task.task_id,
                "module": module_name,
                "subtask_id": subtask.id,
                "workspace_file": str(workspace_file),
                "module_order_source": "spec_blocks.module_order",
                "spec_refs": list(subtask.spec_refs),
                "selected_spec_block_count": len(selected_blocks),
                "module_interface_spec_refs": [item["block_id"] for item in supplemental_interface_blocks],
                "module_skeleton_file": module_skeleton_file,
                "module_skeleton_chars": len(module_skeleton),
                "previous_module_snippets_chars": len(previous_snippets),
            }
            prompt = stage5_subtask_codegen.build_prompt(
                task_id=task.task_id,
                module_name=module_name,
                current_subtask=self.to_pretty_json(model_dump(subtask)),
                module_skeleton=module_skeleton,
                selected_spec_blocks=self.to_pretty_json(selected_blocks),
                module_interface_spec_blocks=self.to_pretty_json(supplemental_interface_blocks),
                previous_module_snippets=previous_snippets,
                stage_context=self.to_pretty_json(stage_context),
            )
            self.logger.info(
                "[%s] Generating %s/%s into %s",
                self.stage_name,
                module_name,
                subtask.id,
                workspace_file,
            )
            self._log_stage_input(prompt=prompt, images=[], stage_context=stage_context)
            artifact = self._invoke_with_repair(
                prompt,
                [],
                task,
                partial_artifacts,
                output_model=SubtaskCodeArtifact,
                quality_validator=lambda candidate, expected_module=module_name, expected_subtask=subtask: (
                    self._validate_subtask_code(candidate, task, expected_module, expected_subtask)
                ),
            )
            updated_text = self._upsert_subtask_section(previous_snippets, subtask, artifact.code)
            self._write_text(workspace_file, updated_text)
            completed_subtasks.append(subtask.id)

        return ModuleCodegenRecord(
            module=module_name,
            workspace_file=str(workspace_file),
            completed_subtasks=completed_subtasks,
        )

    def build_prompt(self, task_input: PlannerTaskInput, partial_artifacts: Dict[str, Any], stage_context: Dict[str, Any]):
        raise NotImplementedError("Stage5Agent uses a custom per-subtask flow.")

    def validate_quality(
        self,
        artifact: Stage5CodegenArtifact,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
    ) -> List[str]:
        spec_blocks = self._get_spec_blocks_artifact(partial_artifacts)
        errors: List[str] = []
        if artifact.schema_version != "stage5_codegen_v1":
            errors.append("schema_version must remain stage5_codegen_v1")
        if artifact.task_id != task_input.task_id:
            errors.append(f"task_id must remain {task_input.task_id}")
        if artifact.module_order != spec_blocks.module_order:
            errors.append("module_order must exactly match spec_blocks.module_order")
        if [item.module for item in artifact.module_files] != artifact.module_order:
            errors.append("module_files[].module must exactly match module_order")
        for record in artifact.module_files:
            path = Path(record.workspace_file)
            if path.name != f"{record.module}_fragments.v":
                errors.append(f"{record.module}: workspace_file must end with {record.module}_fragments.v")
            if path.parent.name != "fragments":
                errors.append(f"{record.module}: workspace_file must be under a fragments directory")
            if not path.exists():
                errors.append(f"{record.module}: workspace_file does not exist at {path}")
        return errors

    def _validate_subtask_code(
        self,
        artifact: SubtaskCodeArtifact,
        task: PlannerTaskInput,
        expected_module: str,
        expected_subtask: ModulePlanSubtask,
    ) -> List[str]:
        errors: List[str] = []
        if artifact.task_id != task.task_id:
            errors.append(f"task_id must equal {task.task_id}")
        if artifact.module != expected_module:
            errors.append(f"module must equal {expected_module}")
        if artifact.subtask_id != expected_subtask.id:
            errors.append(f"subtask_id must equal {expected_subtask.id}")
        if artifact.target != expected_subtask.target:
            errors.append(f"target must equal {expected_subtask.target}")
        if artifact.spec_refs != expected_subtask.spec_refs:
            errors.append(f"spec_refs must equal {expected_subtask.spec_refs}")
        if not artifact.code.strip():
            errors.append("code must not be empty")
        if "```" in artifact.code:
            errors.append("code must not contain Markdown fences")
        if "STAGE5_SUBTASK_BEGIN" in artifact.code or "STAGE5_SUBTASK_END" in artifact.code:
            errors.append("code must not include stage5 subtask marker comments")
        return errors

    def _validate_inputs(
        self,
        module_order: List[str],
        spec_by_module: Dict[str, ModuleSpecBlocks],
        plan_record_by_module: Dict[str, Any],
    ) -> None:
        missing_specs = [module for module in module_order if module not in spec_by_module]
        if missing_specs:
            raise ValueError(f"Stage5 missing spec blocks for modules: {missing_specs}")
        missing_plans = [module for module in module_order if module not in plan_record_by_module]
        if missing_plans:
            raise ValueError(f"Stage5 missing module plans for modules: {missing_plans}")

    def _read_module_plan(self, relative_or_absolute: str) -> ModulePlanArtifact:
        path = self._resolve_output_path(relative_or_absolute)
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return validate_model(ModulePlanArtifact, payload)

    def _read_module_skeleton_context(self, record: Any | None) -> tuple[str, str | None]:
        if record is None:
            return "", None
        doc_file = getattr(record, "doc_file", None)
        if not doc_file:
            return "", None
        path = self._resolve_output_path(str(doc_file))
        if not path.exists():
            self.logger.warning("[%s] Module skeleton doc is missing: %s", self.stage_name, path)
            return "", str(path)
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
        return _extract_module_frame_section(text), str(path)

    def _select_spec_blocks(self, module_spec: ModuleSpecBlocks, spec_refs: List[str]) -> List[Dict[str, str]]:
        block_by_id = {block.block_id: block for block in module_spec.blocks}
        missing = [block_id for block_id in spec_refs if block_id not in block_by_id]
        if missing:
            raise ValueError(f"{module_spec.module}: unknown spec_refs {missing}")
        return [
            {
                "block_id": block_id,
                "text": block_by_id[block_id].text,
            }
            for block_id in spec_refs
        ]

    def _select_interface_spec_blocks(self, module_spec: ModuleSpecBlocks) -> List[Dict[str, str]]:
        primary_matches = [block for block in module_spec.blocks if _is_primary_interface_spec_block(block.text)]
        selected = primary_matches or [block for block in module_spec.blocks if _is_interface_like_spec_block(block.text)][:1]
        return [
            {
                "block_id": block.block_id,
                "text": block.text,
            }
            for block in selected
        ]

    def _upsert_subtask_section(self, existing_text: str, subtask: ModulePlanSubtask, code: str) -> str:
        description = self._sanitize_marker_description(subtask.description)
        section = (
            f"// STAGE5_SUBTASK_BEGIN {subtask.id}: {description}\n"
            f"{code.strip()}\n"
            f"// STAGE5_SUBTASK_END {subtask.id}\n"
        )
        pattern = re.compile(
            rf"// STAGE5_SUBTASK_BEGIN {re.escape(subtask.id)}(?::[^\n]*)?\n"
            rf".*?"
            rf"// STAGE5_SUBTASK_END {re.escape(subtask.id)}\n?",
            flags=re.DOTALL,
        )
        if pattern.search(existing_text):
            updated = pattern.sub(section, existing_text)
        else:
            prefix = existing_text.rstrip()
            updated = f"{prefix}\n\n{section}" if prefix else section
        return updated.rstrip() + "\n"

    def _sanitize_marker_description(self, description: str) -> str:
        collapsed = " ".join(description.replace("\r\n", "\n").split())
        return collapsed[:120]

    def _workspace_file(self, module_name: str) -> Path:
        return (self.workspace_root / "fragments" / f"{module_name}_fragments.v").resolve()

    def _read_text_if_exists(self, path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8").replace("\r\n", "\n")

    def _write_text(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.name}.tmp")
        tmp_path.write_text(text, encoding="utf-8")
        tmp_path.replace(path)

    def _resolve_output_path(self, relative_or_absolute: str) -> Path:
        path = Path(relative_or_absolute)
        if path.is_absolute() or self.output_root is None:
            return path
        return (self.output_root / path).resolve()

    def _default_workspace_root(self) -> Path:
        if self.output_root is None:
            return Path(self.workspace_dirname)
        if self.output_root.name == "outputs" and self.output_root.parent.name == "module_planner":
            return (self.output_root.parent.parent / self.workspace_dirname).resolve()
        return (self.output_root.parent / self.workspace_dirname).resolve()

    def _get_stage4_artifact(self, partial_artifacts: Dict[str, Any]) -> Stage4ModulePlansArtifact:
        candidate = partial_artifacts.get("stage4") or partial_artifacts.get("module_plans")
        if candidate is None:
            raise ValueError("Stage5 code generation requires partial_artifacts['stage4']")
        if isinstance(candidate, Stage4ModulePlansArtifact):
            return candidate
        return validate_model(Stage4ModulePlansArtifact, candidate)

    def _get_stage3_artifact(self, partial_artifacts: Dict[str, Any]) -> Stage3ModuleSkeletonArtifact | None:
        candidate = partial_artifacts.get("stage3")
        if candidate is None:
            return None
        if isinstance(candidate, Stage3ModuleSkeletonArtifact):
            return candidate
        return validate_model(Stage3ModuleSkeletonArtifact, candidate)

    def _get_spec_blocks_artifact(self, partial_artifacts: Dict[str, Any]) -> Stage4SpecBlocksArtifact:
        candidate = partial_artifacts.get("spec_blocks")
        if candidate is None:
            raise ValueError("Stage5 code generation requires partial_artifacts['spec_blocks']")
        if isinstance(candidate, Stage4SpecBlocksArtifact):
            return candidate
        return validate_model(Stage4SpecBlocksArtifact, candidate)


def _is_primary_interface_spec_block(text: str) -> bool:
    if not _is_interface_like_spec_block(text):
        return False
    heading = _first_nonempty_line(text).lower()
    if "interface" not in heading:
        return False
    prefix = heading.split("interface", 1)[0]
    return not re.search(r"\d+\.\d+", prefix)


def _is_interface_like_spec_block(text: str) -> bool:
    normalized = text.lower()
    if "interface" not in normalized:
        return False
    has_table_headers = "direction" in normalized and "width" in normalized and (
        "signal" in normalized or "port" in normalized
    )
    has_port_rows = bool(re.search(r"\|\s*[a-zA-Z_][\w]*\s*\|\s*(?:input|output|inout)\b", normalized))
    return has_table_headers or has_port_rows


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().strip("*").strip()
        if stripped:
            return stripped
    return ""


def _extract_module_frame_section(text: str) -> str:
    match = re.search(
        r"(?ms)^##\s+1\.\s+Module Frame\b.*?(?=^##\s+\d+\.\s+|\Z)",
        text,
    )
    if match:
        return match.group(0).strip()
    return text.strip()
