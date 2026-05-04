from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from zerorepo.rtl_impl.debug_agent.sim_reviewer import check_syntax
from zerorepo.rtl_impl.debug_agent.utils import add_lineno

from ..prompts import stage6_merge
from ..schemas import (
    ModuleCodegenRecord,
    ModuleMergeRecord,
    ModuleSpecBlocks,
    PlannerTaskInput,
    Stage3ModuleSkeletonArtifact,
    Stage4SpecBlocksArtifact,
    Stage5CodegenArtifact,
    Stage6MergeArtifact,
)
from .base import BaseStageAgent, model_dump, validate_model


class Stage6MergeAgent(BaseStageAgent):
    stage_name = "stage6_merge"
    output_model = Stage6MergeArtifact
    system_role = stage6_merge.SYSTEM_ROLE
    allow_best_effort_quality_fallback = False
    workspace_dirname = "workspace"
    max_quality_attempts = 5

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

    def run(
        self,
        task_input: Any,
        partial_artifacts: Dict[str, Any],
    ) -> Stage6MergeArtifact:
        return self.run_incremental(task_input, partial_artifacts)

    def run_incremental(
        self,
        task_input: Any,
        partial_artifacts: Dict[str, Any],
        persist_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Stage6MergeArtifact:
        task = task_input if isinstance(task_input, PlannerTaskInput) else validate_model(PlannerTaskInput, task_input)
        spec_blocks = self._get_spec_blocks_artifact(partial_artifacts)
        stage5 = self._get_stage5_artifact(partial_artifacts)
        stage5_by_module = {item.module: item for item in stage5.module_files}

        records: List[ModuleMergeRecord] = []
        for module_name in spec_blocks.module_order:
            if module_name not in stage5_by_module:
                raise ValueError(f"Stage6 missing stage5 fragments for `{module_name}`")
            records.append(self.run_module(task, partial_artifacts, module_name, stage5_by_module[module_name]))

        artifact = Stage6MergeArtifact(
            task_id=task.task_id,
            module_order=list(spec_blocks.module_order),
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
        stage5_record: ModuleCodegenRecord | Dict[str, Any],
    ) -> ModuleMergeRecord:
        task = task_input if isinstance(task_input, PlannerTaskInput) else validate_model(PlannerTaskInput, task_input)
        record = (
            stage5_record
            if isinstance(stage5_record, ModuleCodegenRecord)
            else validate_model(ModuleCodegenRecord, stage5_record)
        )
        if record.module != module_name:
            raise ValueError(f"Stage6 expected fragments for `{module_name}`, got `{record.module}`")

        spec_blocks = self._get_spec_blocks_artifact(partial_artifacts)
        stage3 = self._get_stage3_artifact(partial_artifacts)
        spec_by_module = {item.module: item for item in spec_blocks.modules}
        skeleton_by_module = {item.module: item for item in stage3.module_records} if stage3 is not None else {}
        if module_name not in spec_by_module:
            raise ValueError(f"Stage6 missing spec blocks for `{module_name}`")

        module_spec = self._format_module_spec(spec_by_module[module_name])
        module_skeleton, module_skeleton_file = self._read_module_skeleton_context(skeleton_by_module.get(module_name))
        fragment_file = Path(record.workspace_file)
        if not fragment_file.exists():
            raise FileNotFoundError(f"Stage6 fragment file does not exist: {fragment_file}")
        generated_fragments = fragment_file.read_text(encoding="utf-8").replace("\r\n", "\n")
        prompt = stage6_merge.build_prompt(
            module_spec=module_spec,
            module_skeleton=module_skeleton,
            generated_fragments=generated_fragments,
        )
        stage_context = {
            "task_id": task.task_id,
            "module": module_name,
            "fragment_file": str(fragment_file),
            "merged_file": str(self._merged_file(module_name)),
            "module_skeleton_file": module_skeleton_file,
            "module_spec_block_count": len(spec_by_module[module_name].blocks),
            "generated_fragments_chars": len(generated_fragments),
        }

        merged_file = self._merged_file(module_name)
        self.logger.info("[%s] Merging %s into %s", self.stage_name, module_name, merged_file)
        self._log_stage_input(prompt=prompt, images=[], stage_context=stage_context)
        merged_code = self._invoke_raw_with_repair(prompt, task, partial_artifacts, module_name, merged_file)
        self._write_text(merged_file, merged_code.rstrip() + "\n")
        return ModuleMergeRecord(
            module=module_name,
            fragment_file=str(fragment_file),
            merged_file=str(merged_file),
        )

    def build_prompt(self, task_input: PlannerTaskInput, partial_artifacts: Dict[str, Any], stage_context: Dict[str, Any]):
        raise NotImplementedError("Stage6MergeAgent uses a custom raw-Verilog flow.")

    def validate_quality(
        self,
        artifact: Stage6MergeArtifact,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
    ) -> List[str]:
        spec_blocks = self._get_spec_blocks_artifact(partial_artifacts)
        errors: List[str] = []
        if artifact.schema_version != "stage6_merge_v1":
            errors.append("schema_version must remain stage6_merge_v1")
        if artifact.task_id != task_input.task_id:
            errors.append(f"task_id must remain {task_input.task_id}")
        if artifact.module_order != spec_blocks.module_order:
            errors.append("module_order must exactly match spec_blocks.module_order")
        if [item.module for item in artifact.module_files] != artifact.module_order:
            errors.append("module_files[].module must exactly match module_order")
        for record in artifact.module_files:
            fragment_path = Path(record.fragment_file)
            merged_path = Path(record.merged_file)
            if fragment_path.name != f"{record.module}_fragments.v":
                errors.append(f"{record.module}: fragment_file must end with {record.module}_fragments.v")
            if merged_path.name != f"{record.module}.v":
                errors.append(f"{record.module}: merged_file must end with {record.module}.v")
            if merged_path.parent.name != "merged":
                errors.append(f"{record.module}: merged_file must be under a merged directory")
            if not fragment_path.exists():
                errors.append(f"{record.module}: fragment_file does not exist at {fragment_path}")
            if not merged_path.exists():
                errors.append(f"{record.module}: merged_file does not exist at {merged_path}")
        return errors

    def _invoke_raw_with_repair(
        self,
        prompt: str,
        task: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        module_name: str,
        rtl_path: Path,
    ) -> str:
        del task, partial_artifacts
        self._ensure_toolchain_path()
        attempt_limit = max(1, int(getattr(self, "max_quality_attempts", 5)))
        current_prompt = prompt
        best_output = ""
        best_errors: List[str] = []
        for attempt in range(1, attempt_limit + 1):
            if attempt > 1:
                self._log_retry_prompt(current_prompt, reason=f"quality_failure_attempt_{attempt - 1}")
            raw = self.llm_client.complete(system_prompt=self.system_role, user_prompt=current_prompt, images=None)
            self._log_llm_raw_output(raw, attempt_label="initial" if attempt == 1 else f"retry_{attempt}")
            code = self._extract_verilog_code(raw if isinstance(raw, str) else str(raw))
            errors = self._validate_raw_module(code, module_name)
            if not errors:
                self._write_text(rtl_path, code.rstrip() + "\n")
                syntax_correct, syntax_output = check_syntax(str(rtl_path))
                if syntax_correct:
                    return code.strip()
                errors = ["Verilator syntax/lint check failed", self._summarize_syntax_output(syntax_output)]
            if not errors:
                return code.strip()
            if not best_errors or len(errors) < len(best_errors):
                best_output = code
                best_errors = list(errors)
            self.logger.warning(
                "[%s] Quality check failed on attempt %d/%d for %s: %s",
                self.stage_name,
                attempt,
                attempt_limit,
                module_name,
                errors,
            )
            if errors and errors[0] == "Verilator syntax/lint check failed":
                current_prompt = self._build_syntax_retry_prompt(prompt, syntax_output, code)
            else:
                current_prompt = self._build_raw_retry_prompt(prompt, errors)
        raise ValueError(
            f"{self.stage_name} output failed quality checks after {attempt_limit} attempts: "
            f"{best_errors}; best output prefix: {best_output[:200]!r}"
        )

    def _validate_raw_module(self, code: str, module_name: str) -> List[str]:
        errors: List[str] = []
        stripped = code.strip()
        if not stripped:
            errors.append("merged module code must not be empty")
        all_module_decls = re.findall(r"(?m)^\s*module\s+([A-Za-z_][A-Za-z0-9_$]*)\b", code)
        expected_module_decls = [item for item in all_module_decls if item == module_name]
        if len(expected_module_decls) != 1:
            errors.append(f"merged module code must contain exactly one `module {module_name}` declaration")
        if len(all_module_decls) != 1:
            errors.append("merged module code must contain exactly one module declaration")
        endmodule_count = len(re.findall(r"(?m)^\s*endmodule\b", code))
        if endmodule_count != 1:
            errors.append("merged module code must contain exactly one endmodule")
        if "STAGE5_SUBTASK_BEGIN" in code or "STAGE5_SUBTASK_END" in code:
            errors.append("merged module code must not contain stage5 fragment markers")
        placeholder_pattern = re.compile(r"\b(TODO|FIXME|TBD|PLACEHOLDER)\b|<block:", flags=re.IGNORECASE)
        if placeholder_pattern.search(code):
            errors.append("merged module code must not contain obvious placeholders")
        return errors

    def _build_raw_retry_prompt(self, original_prompt: str, errors: List[str]) -> str:
        return (
            f"{original_prompt}\n\n"
            "The previous output was invalid. Return only the corrected complete Verilog module code.\n"
            "Return either raw Verilog or one fenced Verilog code block. Do not return JSON or explanations.\n"
            f"Issues:\n- " + "\n- ".join(errors)
        )

    def _build_syntax_retry_prompt(self, original_prompt: str, syntax_output: str, code: str) -> str:
        return (
            f"{original_prompt}\n\n"
            "The previous output was rejected by Verilator after it was written to the merged RTL file.\n"
            "Fix only the RTL syntax/lint/compile issues reported below while preserving the module "
            "interface and intended behavior.\n\n"
            "<verilator_lint_log>\n"
            f"{self._summarize_syntax_output(syntax_output)}\n"
            "</verilator_lint_log>\n\n"
            "<module_with_lineno>\n"
            f"{add_lineno(code)}\n"
            "</module_with_lineno>\n\n"
            "Return only the corrected complete Verilog module code. Do not return JSON or explanations."
        )

    def _summarize_syntax_output(self, syntax_output: str) -> str:
        text = syntax_output
        try:
            from zerorepo.rtl_impl.debug_agent.bash_tools import CommandResult

            obj = CommandResult.model_validate_json(syntax_output)
            text = "\n".join(part for part in [obj.stdout, obj.stderr] if part)
        except Exception:  # noqa: BLE001
            text = syntax_output
        text = text.strip()
        if len(text) > 6000:
            text = text[:6000] + "\n...<snip>..."
        return text

    def _ensure_toolchain_path(self) -> None:
        if shutil.which("verilator"):
            return
        candidates = [
            Path(os.environ["ZEROREPO_RTL_DEBUG_TOOLCHAIN_BIN"]).expanduser()
            if os.environ.get("ZEROREPO_RTL_DEBUG_TOOLCHAIN_BIN")
            else None,
            Path("/home/mokita/miniconda3/envs/realbench/bin"),
            Path("/home/mokita/miniconda3/bin"),
        ]
        for candidate in candidates:
            if candidate is None:
                continue
            verilator = candidate / "verilator"
            if verilator.is_file():
                os.environ["PATH"] = f"{candidate}{os.pathsep}{os.environ.get('PATH', '')}"
                return

    def _extract_verilog_code(self, raw: str) -> str:
        fenced_blocks = re.findall(
            r"```(?:verilog|systemverilog|sv)?\s*\n(.*?)```",
            raw,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if fenced_blocks:
            return fenced_blocks[0].strip()
        generic_blocks = re.findall(r"```\s*\n(.*?)```", raw, flags=re.DOTALL)
        if generic_blocks:
            return generic_blocks[0].strip()
        return raw.strip()

    def _format_module_spec(self, module_spec: ModuleSpecBlocks) -> str:
        return "\n\n".join(f"[{block.block_id}]\n{block.text}" for block in module_spec.blocks)

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

    def _merged_file(self, module_name: str) -> Path:
        return (self.workspace_root / "merged" / f"{module_name}.v").resolve()

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
            raise ValueError("Stage6 merge requires partial_artifacts['spec_blocks']")
        if isinstance(candidate, Stage4SpecBlocksArtifact):
            return candidate
        return validate_model(Stage4SpecBlocksArtifact, candidate)

    def _get_stage5_artifact(self, partial_artifacts: Dict[str, Any]) -> Stage5CodegenArtifact:
        candidate = partial_artifacts.get("stage5")
        if candidate is None:
            raise ValueError("Stage6 merge requires partial_artifacts['stage5']")
        if isinstance(candidate, Stage5CodegenArtifact):
            return candidate
        return validate_model(Stage5CodegenArtifact, candidate)


def _extract_module_frame_section(text: str) -> str:
    match = re.search(
        r"(?ms)^##\s+1\.\s+Module Frame\b.*?(?=^##\s+\d+\.\s+|\Z)",
        text,
    )
    if match:
        return match.group(0).strip()
    return text.strip()
