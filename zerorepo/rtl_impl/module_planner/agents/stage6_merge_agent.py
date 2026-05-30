from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from zerorepo.rtl_impl.debug_agent.sim_reviewer import check_syntax
from zerorepo.rtl_impl.debug_agent.utils import add_lineno
from zerorepo.rtl_impl.kg_agent import KGRetriever
from zerorepo.rtl_impl.retrieval_agent import MergeContextRetrievalResult, MergeContextRetriever
from zerorepo.rtl_impl.retrieval_agent.utils import interface_block_refs

from ..prompts import stage6_merge
from ..schemas import (
    ModuleCodegenRecord,
    ModuleMergeRecord,
    ModulePlanArtifact,
    ModuleSpecBlocks,
    PlannerTaskInput,
    Stage2RepoSkeletonArtifact,
    Stage3ModuleSkeletonArtifact,
    Stage4ModulePlansArtifact,
    Stage4SpecBlocksArtifact,
    Stage5CodegenArtifact,
    Stage6MergeArtifact,
)
from .base import BaseStageAgent, model_dump, validate_model
from .stage5_agent import _find_top_level_equals, _strip_rhs_of_assignments


class Stage6MergeAgent(BaseStageAgent):
    stage_name = "stage6_merge"
    output_model = Stage6MergeArtifact
    system_role = stage6_merge.SYSTEM_ROLE
    allow_best_effort_quality_fallback = True
    workspace_dirname = "workspace"
    merge_retrieval_dirname = "merge_retrieval_json"
    merge_child_context_dirname = "merge_child_context_json"
    max_quality_attempts = 3  # 1 initial + 2 retries
    child_full_code_max_lines = 200
    child_full_code_max_chars = 12000

    def __init__(
        self,
        llm_client,
        context_provider=None,
        artifact_sink=None,
        logger=None,
        output_root: str | Path | None = None,
        workspace_root: str | Path | None = None,
        kg_service: Any | None = None,
    ):
        super().__init__(llm_client, context_provider, artifact_sink, logger)
        self.output_root = Path(output_root) if output_root is not None else None
        self.workspace_root = Path(workspace_root) if workspace_root is not None else self._default_workspace_root()
        self.merge_context_retriever = MergeContextRetriever(llm_client=self.llm_client, logger=self.logger)
        self.kg_service = kg_service
        self.kg_retriever = (
            KGRetriever(kg_service)
            if kg_service is not None and getattr(kg_service, "is_enabled", lambda: False)()
            else None
        )

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
            self.logger.warning(
                "[%s] Final quality check has issues (non-fatal, continuing): %s",
                self.stage_name,
                quality_errors,
            )
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

        module_skeleton, module_skeleton_file = self._read_module_skeleton_context(skeleton_by_module.get(module_name))
        fragment_file = Path(record.workspace_file)
        if not fragment_file.exists():
            raise FileNotFoundError(f"Stage6 fragment file does not exist: {fragment_file}")
        generated_fragments = fragment_file.read_text(encoding="utf-8").replace("\r\n", "\n")
        dependency_context = self._build_dependency_context(module_name, partial_artifacts)
        retrieval_result = self._read_merge_retrieval_if_valid(
            module_name=module_name,
            module_spec=spec_by_module[module_name],
            fragment_file=fragment_file,
        )
        if retrieval_result is None:
            retrieval_result = self.merge_context_retriever.select_spec_refs(
                module_name=module_name,
                module_spec=spec_by_module[module_name],
                module_skeleton=module_skeleton,
                generated_fragments=generated_fragments,
                module_plan=self._read_module_plan_context(module_name, partial_artifacts),
                dependency_context=dependency_context,
            )
            self._write_json(self._merge_retrieval_file(module_name), model_dump(retrieval_result))
        else:
            self.logger.info(
                "[%s] Resume reused merge retrieval for %s from %s",
                self.stage_name,
                module_name,
                self._merge_retrieval_file(module_name),
            )

        kg_child_context = self._read_merge_child_context_if_valid(
            module_name=module_name,
            retrieval_file=self._merge_retrieval_file(module_name),
        )
        if kg_child_context is None:
            kg_child_context = self._build_kg_child_context_from_retrieval_decision(
                module_name,
                dependency_context,
                retrieval_result,
            )
            self._write_json(self._merge_child_context_file(module_name), kg_child_context)
        else:
            self.logger.info(
                "[%s] Resume reused merge child context for %s from %s",
                self.stage_name,
                module_name,
                self._merge_child_context_file(module_name),
            )
        module_spec = self._format_module_spec_by_refs(
            spec_by_module[module_name],
            retrieval_result.selected_spec_refs,
        )
        prompt = stage6_merge.build_prompt(
            module_spec=module_spec,
            module_skeleton=module_skeleton,
            kg_child_context=(
                self._format_kg_child_context_for_prompt(kg_child_context)
                if kg_child_context.get("retrieval_requested")
                else ""
            ),
            global_defines_context=dependency_context.get("global_defines_context", ""),
            generated_fragments=generated_fragments,
        )
        stage_context = {
            "task_id": task.task_id,
            "module": module_name,
            "fragment_file": str(fragment_file),
            "merged_file": str(self._merged_file(module_name)),
            "module_skeleton_file": module_skeleton_file,
            "module_spec_block_count": len(spec_by_module[module_name].blocks),
            "retrieval_selected_spec_refs": list(retrieval_result.selected_spec_refs),
            "retrieval_selected_spec_block_count": len(retrieval_result.selected_spec_refs),
            "retrieval_fallback_used": retrieval_result.fallback_used,
            "retrieval_use_kg_child_context": retrieval_result.use_kg_child_context,
            "retrieval_kg_child_modules": list(retrieval_result.kg_child_modules),
            "kg_child_context_child_count": len(kg_child_context.get("children", [])),
            "kg_child_context_enabled": bool(kg_child_context.get("kg_enabled")),
            "kg_child_context_requested": bool(kg_child_context.get("retrieval_requested")),
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
                syntax_correct, syntax_output = check_syntax(str(rtl_path), top_module=module_name)
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

        if self.allow_best_effort_quality_fallback and best_output.strip():
            self.logger.warning(
                "[%s] Quality checks still failed after %d attempts for %s; "
                "continuing with best-effort artifact: %s",
                self.stage_name,
                attempt_limit,
                module_name,
                best_errors,
            )
            self._write_text(rtl_path, best_output.rstrip() + "\n")
            return best_output.strip()

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
        code_for_array_check = _strip_rhs_of_assignments(code)
        if re.search(r"(?m)^\s*(?:wire|reg|integer)\b[^;]*\b[A-Za-z_][A-Za-z0-9_]*\s*(?:\[[^\]]+\]\s*)+[^;]*;", code_for_array_check):
            errors.append("merged module code must not use unpacked array declarations; flatten arrays into scalar signals")
        if re.search(r"\b(?:generate|endgenerate|genvar)\b", code):
            errors.append("merged module code must not use generate/genvar; explicitly unroll repeated logic and instances")
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

    def _format_module_spec_by_refs(self, module_spec: ModuleSpecBlocks, spec_refs: List[str]) -> str:
        block_by_id = {block.block_id: block for block in module_spec.blocks}
        selected_blocks = [block_by_id[block_id] for block_id in spec_refs if block_id in block_by_id]
        return "\n\n".join(f"[{block.block_id}]\n{block.text}" for block in selected_blocks)

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

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = path.with_name(f"{path.name}.tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
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

    def _merge_retrieval_file(self, module_name: str) -> Path:
        root = self.output_root if self.output_root is not None else Path(".")
        return (root / self.merge_retrieval_dirname / f"{module_name}.json").resolve()

    def _merge_child_context_file(self, module_name: str) -> Path:
        root = self.output_root if self.output_root is not None else Path(".")
        return (root / self.merge_child_context_dirname / f"{module_name}.json").resolve()

    def _read_merge_retrieval_if_valid(
        self,
        *,
        module_name: str,
        module_spec: ModuleSpecBlocks,
        fragment_file: Path,
    ) -> MergeContextRetrievalResult | None:
        path = self._merge_retrieval_file(module_name)
        if not path.exists():
            return None
        if fragment_file.exists() and path.stat().st_mtime < fragment_file.stat().st_mtime:
            self.logger.info(
                "[%s] Existing merge retrieval for %s is older than fragments; regenerating",
                self.stage_name,
                module_name,
            )
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            result = validate_model(MergeContextRetrievalResult, payload)
            self._validate_cached_merge_retrieval(result, module_name=module_name, module_spec=module_spec)
            return result
        except Exception as exc:  # noqa: BLE001 - invalid cache should not block regeneration.
            self.logger.info(
                "[%s] Existing merge retrieval for %s is invalid; regenerating: %s",
                self.stage_name,
                module_name,
                exc,
            )
            return None

    def _validate_cached_merge_retrieval(
        self,
        result: MergeContextRetrievalResult,
        *,
        module_name: str,
        module_spec: ModuleSpecBlocks,
    ) -> None:
        if result.schema_version != "merge_context_retrieval_v1":
            raise ValueError("schema_version must remain merge_context_retrieval_v1")
        if result.module != module_name:
            raise ValueError(f"module must equal {module_name}, got {result.module}")
        if not result.selected_spec_refs:
            raise ValueError("selected_spec_refs must not be empty")
        valid_refs = {block.block_id for block in module_spec.blocks}
        unknown = [ref for ref in result.selected_spec_refs if ref not in valid_refs]
        if unknown:
            raise ValueError(f"unknown selected_spec_refs: {unknown}")
        interface_refs = interface_block_refs(module_spec)
        if interface_refs and not any(ref in result.selected_spec_refs for ref in interface_refs):
            raise ValueError(f"selected_spec_refs must include an interface block: {interface_refs}")

    def _read_merge_child_context_if_valid(
        self,
        *,
        module_name: str,
        retrieval_file: Path,
    ) -> Dict[str, Any] | None:
        path = self._merge_child_context_file(module_name)
        if not path.exists():
            return None
        if retrieval_file.exists() and path.stat().st_mtime < retrieval_file.stat().st_mtime:
            self.logger.info(
                "[%s] Existing merge child context for %s is older than retrieval; regenerating",
                self.stage_name,
                module_name,
            )
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if payload.get("schema_version") != "merge_child_context_v1":
                raise ValueError("schema_version must remain merge_child_context_v1")
            if payload.get("module") != module_name:
                raise ValueError(f"module must equal {module_name}, got {payload.get('module')}")
            return payload
        except Exception as exc:  # noqa: BLE001 - invalid cache should not block regeneration.
            self.logger.info(
                "[%s] Existing merge child context for %s is invalid; regenerating: %s",
                self.stage_name,
                module_name,
                exc,
            )
            return None

    def _read_module_plan_context(
        self,
        module_name: str,
        partial_artifacts: Dict[str, Any],
    ) -> ModulePlanArtifact | None:
        stage4 = self._get_stage4_artifact(partial_artifacts)
        if stage4 is None:
            return None
        plan_records = {item.module: item for item in stage4.module_plan_files}
        record = plan_records.get(module_name)
        if record is None:
            return None
        path = self._resolve_output_path(record.plan_file)
        if not path.exists():
            self.logger.warning("[%s] Module plan sidecar is missing: %s", self.stage_name, path)
            return None
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        plan = validate_model(ModulePlanArtifact, payload)
        if plan.module != module_name:
            raise ValueError(f"Stage6 expected module plan for `{module_name}`, got `{plan.module}`")
        return plan

    def _build_dependency_context(self, module_name: str, partial_artifacts: Dict[str, Any]) -> Dict[str, Any]:
        repo_skeleton = self._get_repo_skeleton_artifact(partial_artifacts)
        if repo_skeleton is None:
            return {}
        module_by_name = {item.module: item for item in repo_skeleton.modules}
        module_record = module_by_name.get(module_name)
        if module_record is None:
            return {}
        child_modules = list(module_record.children)
        global_defines = self._detect_global_defines_modules(repo_skeleton, module_by_name)
        global_defines_context = self._build_global_defines_context(global_defines, module_name)
        return {
            "module": module_name,
            "children": child_modules,
            "instance_hints": [model_dump(item) for item in module_record.instance_hints],
            "global_hierarchy": [model_dump(edge) for edge in repo_skeleton.global_invariants.hierarchy],
            "cross_module_alignment": list(repo_skeleton.global_invariants.cross_module_alignment),
            "child_module_summaries": [
                {
                    "module": child,
                    "file_path": module_by_name[child].file_path,
                    "role": module_by_name[child].role,
                    "kind": module_by_name[child].kind,
                }
                for child in child_modules
                if child in module_by_name
            ],
            "global_defines_modules": list(global_defines),
            "global_defines_context": global_defines_context,
        }

    def _detect_global_defines_modules(
        self, repo_skeleton: Any, module_by_name: Dict[str, Any]
    ) -> List[str]:
        """Identify modules that provide global constants/defines used by other modules."""
        candidates: set[str] = set()

        # 1. Extract module names from global_data_conventions text
        conventions = getattr(repo_skeleton.global_invariants, "global_data_conventions", "") or ""
        for mod_name in module_by_name:
            if mod_name in conventions:
                candidates.add(mod_name)

        # 2. Check repo_notes for defines/constants keywords
        define_keywords = {"defines", "constants", "provides constants", "not a synthesizable module"}
        for mod_name, record in module_by_name.items():
            notes = " ".join(getattr(record, "repo_notes", []) or []).lower()
            if any(kw in notes for kw in define_keywords):
                candidates.add(mod_name)

        # 3. Exclude the current module itself (it doesn't depend on its own defines)
        # and modules that are already children (they get separate KG context)
        return sorted(candidates)

    def _build_global_defines_context(
        self, global_defines: List[str], current_module: str
    ) -> str:
        """Read the generated Verilog for global defines modules and return
        their content as prompt context.  Extracts numeric define values into
        an explicit table so the model cannot overlook them."""
        chunks: list[str] = []
        for mod_name in global_defines:
            if mod_name == current_module:
                continue
            merged_path = self._merged_file(mod_name)
            if not merged_path.exists():
                continue
            try:
                content = merged_path.read_text(encoding="utf-8")
            except OSError:
                continue

            # Extract active (non-commented) `define lines, parsed line-by-line
            active_defines: list[tuple[str, str]] = []
            define_re = re.compile(r"^\s*`define\s+(\w+)(?:\s+(.+?))?\s*$")
            for line in content.splitlines():
                line_stripped = line.strip()
                if line_stripped.startswith("//"):
                    continue
                m = define_re.match(line_stripped)
                if m:
                    value = (m.group(2) or "").strip()
                    if value and not value.startswith("//"):
                        active_defines.append((m.group(1), value))

            summary_lines = [f"  {n} = {v}" for n, v in active_defines]
            summary = (
                f"// --- Global defines from {mod_name}.v ---\n"
                f"// KEY VALUES (authoritative — override any conflicting\n"
                f"// parameter/localparam values in the generated fragments):\n"
                + ("\n".join(summary_lines) if summary_lines else "  (no active numeric defines)")
                + f"\n\n"
                f"// Full {mod_name}.v content for reference:\n"
                f"{content.strip()}\n"
                f"// --- End {mod_name}.v ---"
            )
            chunks.append(summary)
        return "\n\n".join(chunks)

    def _build_kg_child_context(self, module_name: str, dependency_context: Dict[str, Any]) -> Dict[str, Any]:
        child_modules = self._child_modules_from_dependency_context(module_name, dependency_context)
        return self._build_kg_child_context_for_modules(
            module_name=module_name,
            child_modules=child_modules,
            retrieval_requested=True,
            retrieval_reason="Direct KG child context build requested.",
        )

    def _build_kg_child_context_from_retrieval_decision(
        self,
        module_name: str,
        dependency_context: Dict[str, Any],
        retrieval_result: Any,
    ) -> Dict[str, Any]:
        all_child_modules = self._child_modules_from_dependency_context(module_name, dependency_context)
        selected_modules = [
            child
            for child in list(getattr(retrieval_result, "kg_child_modules", []) or [])
            if child in all_child_modules
        ]
        if getattr(retrieval_result, "use_kg_child_context", False) and not selected_modules:
            selected_modules = all_child_modules
        if not getattr(retrieval_result, "use_kg_child_context", False):
            return {
                "schema_version": "merge_child_context_v1",
                "module": module_name,
                "kg_enabled": self.kg_retriever is not None,
                "retrieval_requested": False,
                "retrieval_reason": str(getattr(retrieval_result, "kg_child_context_reason", "") or ""),
                "available_child_modules": all_child_modules,
                "requested_child_modules": [],
                "children": [],
            }
        return self._build_kg_child_context_for_modules(
            module_name=module_name,
            child_modules=selected_modules,
            retrieval_requested=True,
            retrieval_reason=str(getattr(retrieval_result, "kg_child_context_reason", "") or ""),
        )

    def _build_kg_child_context_for_modules(
        self,
        *,
        module_name: str,
        child_modules: List[str],
        retrieval_requested: bool,
        retrieval_reason: str,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "schema_version": "merge_child_context_v1",
            "module": module_name,
            "kg_enabled": self.kg_retriever is not None,
            "retrieval_requested": retrieval_requested,
            "retrieval_reason": retrieval_reason,
            "requested_child_modules": list(child_modules),
            "children": [],
        }
        if not child_modules:
            return payload
        if self.kg_retriever is None:
            payload["reason"] = "RTL KG is not enabled; child module context unavailable."
            return payload

        for child_module in child_modules:
            try:
                interface = self.kg_retriever.get_module_interface(child_module)
                child_context = self._child_context_from_interface(interface)
                self._attach_child_code_context(child_context)
                payload["children"].append(child_context)
            except Exception as exc:  # noqa: BLE001 - KG context should not block merge.
                if self.logger is not None:
                    self.logger.warning(
                        "[%s] KG child context lookup failed for %s -> %s: %s",
                        self.stage_name,
                        module_name,
                        child_module,
                        exc,
                    )
                payload["children"].append(
                    {
                        "module": child_module,
                        "child_status": "candidate",
                        "ports": [],
                        "parameters": [],
                        "file_path": "",
                        "final_rtl_path": "",
                        "simulation_status": "",
                        "simulation_passed": False,
                        "code_mode": "unavailable",
                        "full_code_included": False,
                        "lookup_error": str(exc),
                    }
                )
        return payload

    def _child_modules_from_dependency_context(
        self,
        module_name: str,
        dependency_context: Dict[str, Any],
    ) -> List[str]:
        child_modules: List[str] = []
        for child in dependency_context.get("children", []) or []:
            child_name = str(child).strip()
            if child_name and child_name != module_name and child_name not in child_modules:
                child_modules.append(child_name)
        for hint in dependency_context.get("instance_hints", []) or []:
            if not isinstance(hint, dict):
                continue
            child_name = str(hint.get("module") or "").strip()
            if child_name and child_name != module_name and child_name not in child_modules:
                child_modules.append(child_name)
        return child_modules

    def _child_context_from_interface(self, interface: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "module": str(interface.get("module") or ""),
            "child_status": str(interface.get("child_status") or "candidate"),
            "ports": list(interface.get("ports") or []),
            "parameters": list(interface.get("parameters") or []),
            "file_path": str(interface.get("file_path") or ""),
            "module_path": str(interface.get("module_path") or ""),
            "final_rtl_path": str(interface.get("final_rtl_path") or ""),
            "simulation_status": str(interface.get("simulation_status") or ""),
            "simulation_passed": bool(interface.get("simulation_passed")),
            "module_start_line": interface.get("module_start_line"),
            "module_end_line": interface.get("module_end_line"),
        }

    def _attach_child_code_context(self, child_context: Dict[str, Any]) -> None:
        child_context["code_mode"] = "interface_only"
        child_context["full_code_included"] = False
        child_context["source_file_read"] = ""
        child_context["functional_summary"] = (
            "Use this child module by instantiation. Do not duplicate verified child internals in the parent module."
        )
        source_path = self._resolve_child_rtl_path(child_context)
        if source_path is None or not source_path.exists() or not source_path.is_file():
            child_context["interface_code"] = self._synthesize_interface_code(child_context)
            return

        text = source_path.read_text(encoding="utf-8", errors="ignore").replace("\r\n", "\n")
        module_code = self._extract_module_code(text, str(child_context.get("module") or ""))
        child_context["source_file_read"] = str(source_path)
        child_context["interface_code"] = self._extract_interface_code(module_code, child_context)
        is_verified = child_context.get("child_status") == "verified"
        small_enough = (
            len(module_code.splitlines()) <= self.child_full_code_max_lines
            and len(module_code) <= self.child_full_code_max_chars
        )
        if is_verified and small_enough:
            child_context["code_mode"] = "full"
            child_context["full_code_included"] = True
            child_context["full_code"] = module_code.strip()

    def _resolve_child_rtl_path(self, child_context: Dict[str, Any]) -> Path | None:
        for key in ("final_rtl_path", "file_path", "module_path"):
            raw_path = str(child_context.get(key) or "").strip()
            if not raw_path:
                continue
            path = Path(raw_path)
            if path.is_absolute():
                return path
            repo_path_value = getattr(self.kg_service, "repo_path", "") if self.kg_service is not None else ""
            repo_path = Path(repo_path_value) if repo_path_value else None
            if repo_path is not None:
                return (repo_path / raw_path).resolve()
        return None

    def _extract_module_code(self, text: str, module_name: str) -> str:
        if not module_name:
            return text
        pattern = re.compile(
            rf"(?ms)^\s*module\s+{re.escape(module_name)}\b.*?^\s*endmodule\b"
        )
        match = pattern.search(text)
        return match.group(0) if match else text

    def _extract_interface_code(self, module_code: str, child_context: Dict[str, Any]) -> str:
        lines = module_code.splitlines()
        interface_lines: List[str] = []
        in_header = False
        for line in lines:
            stripped = line.strip()
            if not in_header and re.match(r"^module\b", stripped):
                in_header = True
            if in_header:
                interface_lines.append(line)
                if stripped.endswith(");") or (stripped.endswith(";") and "(" not in stripped):
                    in_header = False
                continue
            if re.match(r"^(input|output|inout|parameter|localparam)\b", stripped):
                interface_lines.append(line)
                continue
            if re.match(r"^(assign|always|initial|function|task|endmodule)\b", stripped):
                break
        text = "\n".join(interface_lines).strip()
        return text or self._synthesize_interface_code(child_context)

    def _synthesize_interface_code(self, child_context: Dict[str, Any]) -> str:
        module_name = str(child_context.get("module") or "")
        ports = child_context.get("ports", []) or []
        parameters = child_context.get("parameters", []) or []
        lines = [f"module {module_name}("]
        port_names = [str(port.get("name") or "") for port in ports if isinstance(port, dict) and port.get("name")]
        for index, port_name in enumerate(port_names):
            suffix = "," if index < len(port_names) - 1 else ""
            lines.append(f"    {port_name}{suffix}")
        lines.append(");")
        for param in parameters:
            if not isinstance(param, dict):
                continue
            name = str(param.get("name") or "")
            value = str(param.get("value") or "")
            if name:
                assignment = f" = {value}" if value else ""
                lines.append(f"parameter {name}{assignment};")
        for port in ports:
            if not isinstance(port, dict):
                continue
            name = str(port.get("name") or "")
            direction = str(port.get("direction") or "")
            width = str(port.get("width") or "")
            if name:
                width_text = f" {width}" if width else ""
                lines.append(f"{direction or 'wire'}{width_text} {name};")
        lines.append("endmodule")
        return "\n".join(lines)

    def _format_kg_child_context_for_prompt(self, kg_child_context: Dict[str, Any]) -> str:
        prompt_payload = json.loads(json.dumps(kg_child_context, ensure_ascii=False))
        for child in prompt_payload.get("children", []) or []:
            if isinstance(child, dict):
                child.pop("raw_query", None)
        return json.dumps(prompt_payload, indent=2, ensure_ascii=False)

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

    def _get_stage4_artifact(self, partial_artifacts: Dict[str, Any]) -> Stage4ModulePlansArtifact | None:
        candidate = partial_artifacts.get("stage4") or partial_artifacts.get("module_plans")
        if candidate is None:
            return None
        if isinstance(candidate, Stage4ModulePlansArtifact):
            return candidate
        return validate_model(Stage4ModulePlansArtifact, candidate)

    def _get_repo_skeleton_artifact(self, partial_artifacts: Dict[str, Any]) -> Stage2RepoSkeletonArtifact | None:
        candidate = partial_artifacts.get("stage2")
        if candidate is None:
            return None
        if isinstance(candidate, Stage2RepoSkeletonArtifact):
            return candidate
        return validate_model(Stage2RepoSkeletonArtifact, candidate)


def _extract_module_frame_section(text: str) -> str:
    match = re.search(
        r"(?ms)^##\s+1\.\s+Module Frame\b.*?(?=^##\s+\d+\.\s+|\Z)",
        text,
    )
    if match:
        return match.group(0).strip()
    return text.strip()
