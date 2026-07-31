from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ..prompts import stage5_subtask_codegen
from ..schemas import (
    FragmentContract,
    ModuleCodegenRecord,
    ModulePlanArtifact,
    ModulePlanSubtask,
    ModuleSpecBlocks,
    ModuleTimingBindingArtifact,
    PlannerTaskInput,
    Stage3ModuleSkeletonArtifact,
    Stage3TimingBindingsArtifact,
    Stage4ModulePlansArtifact,
    Stage4SpecBlocksArtifact,
    Stage5CodegenArtifact,
    SubtaskCodeArtifact,
)
from .base import BaseStageAgent, model_dump, validate_model
from .global_defines import copy_official_define_file, is_define_only_module, read_global_defines_manifest


class Stage5Agent(BaseStageAgent):
    stage_name = "stage5_codegen"
    output_model = Stage5CodegenArtifact
    system_role = stage5_subtask_codegen.SYSTEM_ROLE
    allow_best_effort_quality_fallback = True
    max_quality_attempts = 3  # 1 initial + 2 retries
    workspace_dirname = "workspace"

    def __init__(
        self,
        llm_client,
        context_provider=None,
        artifact_sink=None,
        logger=None,
        output_root: str | Path | None = None,
        workspace_root: str | Path | None = None,
        planning_context_retriever: Any | None = None,
    ):
        super().__init__(llm_client, context_provider, artifact_sink, logger)
        self.output_root = Path(output_root) if output_root is not None else None
        self.workspace_root = Path(workspace_root) if workspace_root is not None else self._default_workspace_root()
        self.planning_context_retriever = planning_context_retriever

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
        self._ensure_global_defines_copied(task, partial_artifacts)

        records: List[ModuleCodegenRecord] = []
        for module_name in module_order:
            records.append(self.run_module(task, partial_artifacts, module_name))

        artifact = Stage5CodegenArtifact(
            task_id=task.task_id,
            input_fingerprint=str(partial_artifacts.get("stage5_input_fingerprint") or ""),
            module_order=module_order,
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
        timing_binding = self._read_timing_binding_for_module(partial_artifacts, module_name)
        timing_obligation_by_id = (
            {item.obligation_id: item for item in timing_binding.block_obligations}
            if timing_binding is not None
            else {}
        )
        planning_kg_context = ""
        if self.planning_context_retriever is not None:
            try:
                context = self.planning_context_retriever.get_module_context(
                    module_name,
                    require_spec=True,
                    require_skeleton=True,
                    require_plan=True,
                    include_code_interface=True,
                    expected_fingerprints={
                        "spec_context": str(getattr(stage3, "input_fingerprint", "") or ""),
                        "skeleton": str(getattr(stage3, "input_fingerprint", "") or ""),
                        "plan": str(getattr(stage4, "input_fingerprint", "") or ""),
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

        workspace_file = self._workspace_file(module_name)
        repo_skeleton = partial_artifacts.get("stage2") or partial_artifacts.get("repo_skeleton")
        if is_define_only_module(module_name, repo_skeleton):
            entry = copy_official_define_file(
                task=task,
                module_name=module_name,
                workspace_root=self.workspace_root,
                output_root=self.output_root,
            )
            if entry is not None:
                official_text = Path(entry["workspace_path"]).read_text(encoding="utf-8")
                self._write_text(workspace_file, official_text.rstrip() + "\n")
                self._write_contracts_file(
                    module_name,
                    [
                        {
                            "subtask_id": "official_copy",
                            "target": "<official define-only file>",
                            "spec_refs": [],
                            "contract": {
                                "writes": [],
                                "reads": [],
                                "clocking": "preprocessor_defines",
                                "reset_behavior": "none",
                                "hold_behavior": "none",
                                "latency": "compile_time",
                                "assumptions": ["Official define-only file copied verbatim; do not rewrite with LLM."],
                            },
                            "analysis": {"mode": "official_copy", "source": entry["source"]},
                        }
                    ],
                    input_fingerprint=str(partial_artifacts.get("stage5_input_fingerprint") or ""),
                )
                return ModuleCodegenRecord(
                    module=module_name,
                    workspace_file=str(workspace_file),
                    completed_subtasks=["official_copy"],
                )

        completed_subtasks: List[str] = []
        contract_entries: List[Dict[str, Any]] = []
        global_defines_context = self._build_global_defines_context()
        for subtask in module_plan.subtasks:
            timing_obligations = [
                timing_obligation_by_id[item]
                for item in subtask.timing_obligation_ids
                if item in timing_obligation_by_id
            ]
            missing_timing_ids = [
                item for item in subtask.timing_obligation_ids if item not in timing_obligation_by_id
            ]
            if missing_timing_ids:
                raise ValueError(
                    f"Stage5 missing timing obligations for {module_name}/{subtask.id}: {missing_timing_ids}"
                )
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
                "global_define_files": self._global_define_file_names(),
                "timing_obligation_ids": list(subtask.timing_obligation_ids),
            }
            prompt = stage5_subtask_codegen.build_prompt(
                task_id=task.task_id,
                module_name=module_name,
                current_subtask=self.to_pretty_json(model_dump(subtask)),
                module_skeleton=module_skeleton,
                selected_spec_blocks=self.to_pretty_json(selected_blocks),
                module_interface_spec_blocks=self.to_pretty_json(supplemental_interface_blocks),
                previous_module_snippets=previous_snippets,
                timing_obligations=self.to_pretty_json(timing_obligations),
                global_defines_context=global_defines_context,
                planning_kg_context=planning_kg_context,
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
                quality_validator=lambda candidate, expected_module=module_name, expected_subtask=subtask, expected_timing=timing_obligations: (
                    self._validate_subtask_code(
                        candidate,
                        task,
                        expected_module,
                        expected_subtask,
                        expected_timing,
                    )
                ),
            )
            if subtask.timing_obligation_ids and self._last_quality_errors:
                hard_errors = [
                    item
                    for item in self._last_quality_errors
                    if not self._is_nonfatal_timing_diagnostic(item)
                ]
                if hard_errors:
                    raise ValueError(
                        f"Stage5 timing-constrained subtask {module_name}/{subtask.id} "
                        f"failed validation: {hard_errors}"
                    )
                self.logger.warning(
                    "[%s] Timing diagnostics remain for %s/%s; continuing with the "
                    "best-effort local fragment: %s",
                    self.stage_name,
                    module_name,
                    subtask.id,
                    self._last_quality_errors,
                )
            updated_text = self._upsert_subtask_section(previous_snippets, subtask, artifact.code)
            self._write_text(workspace_file, updated_text)
            contract_entries.append(
                self._contract_entry(
                    artifact=artifact,
                    subtask=subtask,
                )
            )
            self._write_contracts_file(
                module_name,
                contract_entries,
                input_fingerprint=str(partial_artifacts.get("stage5_input_fingerprint") or ""),
            )
            completed_subtasks.append(subtask.id)

        return ModuleCodegenRecord(
            module=module_name,
            workspace_file=str(workspace_file),
            completed_subtasks=completed_subtasks,
        )

    def _contract_entry(self, *, artifact: SubtaskCodeArtifact, subtask: ModulePlanSubtask) -> Dict[str, Any]:
        extracted = self._extract_fragment_contract(artifact.code)
        if artifact.contract is not None:
            contract = model_dump(artifact.contract)
            writes = sorted(set(str(item) for item in contract.get("writes", []) if item) | set(extracted.writes))
            reads = sorted((set(str(item) for item in contract.get("reads", []) if item) | set(extracted.reads)) - set(writes))
            contract["writes"] = writes
            contract["reads"] = reads
            if not contract.get("clocking"):
                contract["clocking"] = extracted.clocking
        else:
            contract = model_dump(extracted)
        return {
            "subtask_id": subtask.id,
            "target": subtask.target,
            "spec_refs": list(subtask.spec_refs),
            "timing_obligation_ids": list(subtask.timing_obligation_ids),
            "contract": contract,
            "analysis": {
                "extracted_writes": extracted.writes,
                "extracted_reads": extracted.reads,
            },
        }

    def _write_contracts_file(
        self,
        module_name: str,
        entries: List[Dict[str, Any]],
        *,
        input_fingerprint: str = "",
    ) -> Path:
        path = self._contracts_file(module_name)
        payload = {
            "schema_version": "stage5_fragment_contracts_v1",
            "module": module_name,
            "input_fingerprint": input_fingerprint,
            "contracts": entries,
        }
        self._write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        return path

    def _contracts_file(self, module_name: str) -> Path:
        return (self.workspace_root / "fragments" / f"{module_name}_contracts.json").resolve()

    def _extract_fragment_contract(self, code: str) -> FragmentContract:
        text = _strip_verilog_comments(code)
        writes: set[str] = set()
        for match in re.finditer(r"\b([A-Za-z_][A-Za-z0-9_$]*)\b\s*(?:\[[^\]]+\])?\s*(?:<=|(?<![=!<>])=(?![=]))", text):
            lhs = match.group(1)
            if lhs not in {"if", "for", "while", "case", "assign"}:
                writes.add(lhs)
        identifiers = {
            item
            for item in re.findall(r"\b[A-Za-z_][A-Za-z0-9_$]*\b", text)
            if item
            and item not in {
                "always",
                "assign",
                "begin",
                "end",
                "if",
                "else",
                "case",
                "endcase",
                "posedge",
                "negedge",
                "wire",
                "reg",
                "input",
                "output",
                "localparam",
                "parameter",
            }
            and not item[0].isdigit()
        }
        reads = sorted(identifiers - writes)
        if "posedge" in text or "negedge" in text:
            edge = "posedge" if "posedge" in text else "negedge"
            clk_match = re.search(rf"{edge}\s+([A-Za-z_][A-Za-z0-9_$]*)", text)
            clocking = f"{edge} {clk_match.group(1)}" if clk_match else edge
        elif re.search(r"\balways\s*@", text):
            clocking = "combinational"
        elif writes:
            clocking = "continuous_or_declaration"
        else:
            clocking = "declarations"
        return FragmentContract(
            writes=sorted(writes),
            reads=reads,
            clocking=clocking,
            reset_behavior="unknown",
            hold_behavior="unknown",
            latency="unknown",
            assumptions=[],
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
        expected_timing_obligations: List[Any] | None = None,
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
        if artifact.timing_obligation_ids != expected_subtask.timing_obligation_ids:
            errors.append(
                f"timing_obligation_ids must equal {expected_subtask.timing_obligation_ids}"
            )
        if not artifact.code.strip():
            errors.append("code must not be empty")
        if "```" in artifact.code:
            errors.append("code must not contain Markdown fences")
        if "STAGE5_SUBTASK_BEGIN" in artifact.code or "STAGE5_SUBTASK_END" in artifact.code:
            errors.append("code must not include stage5 subtask marker comments")
        code_without_comments = _strip_rhs_of_assignments(_strip_verilog_comments(artifact.code))
        if re.search(
            r"(?m)^\s*(?:wire|reg|integer)\b[^;]*\b[A-Za-z_][A-Za-z0-9_]*\s*(?:\[[^\]]+\]\s*)+[^;]*;",
            code_without_comments,
        ):
            errors.append("code must not use unpacked array declarations; flatten arrays into scalar signals")
        if re.search(r"\b[A-Za-z_][A-Za-z0-9_]*\s*\[[^\]]+\]\s*\[[^\]]+\]", code_without_comments):
            errors.append("code must not use multidimensional signal references; flatten arrays into scalar signals")
        if re.search(r"\b(?:generate|endgenerate|genvar)\b", code_without_comments):
            errors.append("code must not use generate/genvar; explicitly unroll repeated logic and instances")
        obligations = expected_timing_obligations or []
        contract_clocking = str(artifact.contract.clocking if artifact.contract is not None else "")
        for obligation in obligations:
            has_post_edge_write = any(
                access.at == "POST_EDGE" for access in obligation.writes
            )
            has_edge_access = has_post_edge_write or any(
                access.at in {"PRE_EDGE", "POST_EDGE"}
                for access in [
                    *obligation.reads,
                    *obligation.combinational_outputs,
                ]
            )
            has_comb_output = any(
                access.at == "COMB" for access in obligation.combinational_outputs
            )
            if has_post_edge_write and (
                "posedge" not in contract_clocking and "negedge" not in contract_clocking
            ):
                errors.append(
                    f"{obligation.obligation_id}: POST_EDGE writes require a clocked fragment contract"
                )
            if has_comb_output and not has_edge_access and (
                "posedge" in contract_clocking or "negedge" in contract_clocking
            ):
                errors.append(
                    f"{obligation.obligation_id}: pure combinational obligation uses registered clocking"
                )
        return errors

    @staticmethod
    def _is_nonfatal_timing_diagnostic(message: str) -> bool:
        return (
            "POST_EDGE writes require a clocked fragment contract" in message
            or "pure combinational obligation uses registered clocking" in message
        )

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

    def _ensure_global_defines_copied(self, task: PlannerTaskInput, partial_artifacts: Dict[str, Any]) -> None:
        repo_skeleton = partial_artifacts.get("stage2") or partial_artifacts.get("repo_skeleton")
        if repo_skeleton is None:
            return
        for module_name in self._detect_global_defines_modules(repo_skeleton):
            copied = copy_official_define_file(
                task=task,
                module_name=module_name,
                workspace_root=self.workspace_root,
                output_root=self.output_root,
            )
            if copied is not None:
                self.logger.info(
                    "[%s] Copied official global defines %s -> %s",
                    self.stage_name,
                    copied.get("source"),
                    copied.get("workspace_path"),
                )

    def _detect_global_defines_modules(self, repo_skeleton: Any) -> List[str]:
        modules = list(_get(repo_skeleton, "modules", []) or [])
        by_name = {str(_get(item, "module", "") or ""): item for item in modules}
        candidates: set[str] = set()
        for module_name, record in by_name.items():
            notes = " ".join(_get(record, "repo_notes", []) or []).lower()
            role = str(_get(record, "role", "") or "").lower()
            local_define_hint = any(
                marker in notes or marker in role
                for marker in ("not a synthesizable module", "provides constants", "global parameter", "global defines", "preprocessor define")
            )
            if module_name and (is_define_only_module(module_name, repo_skeleton) or local_define_hint):
                candidates.add(module_name)

        invariants = _get(repo_skeleton, "global_invariants", None)
        conventions = str(_get(invariants, "global_data_conventions", "") or "")
        lowered_conventions = conventions.lower()
        for module_name in by_name:
            lowered = module_name.lower()
            if lowered and lowered in lowered_conventions and ("define" in lowered or "constant" in lowered_conventions):
                candidates.add(module_name)
        return sorted(candidates)

    def _global_define_file_names(self) -> List[str]:
        manifest = read_global_defines_manifest(self.workspace_root)
        names: List[str] = []
        for item in manifest.get("global_define_files", []) or []:
            if not isinstance(item, dict) or not item.get("must_include"):
                continue
            name = str(item.get("name") or item.get("module") or "")
            if name:
                names.append(name)
        return names

    def _build_global_defines_context(self, max_chars: int = 20000) -> str:
        manifest = read_global_defines_manifest(self.workspace_root)
        entries = [
            item
            for item in manifest.get("global_define_files", []) or []
            if isinstance(item, dict) and item.get("must_include")
        ]
        if not entries:
            return ""

        chunks: List[str] = [
            "Official global macro definitions are available for this task.",
            "Use these macro names and values as authoritative compile-time context.",
            "Do not redefine these macros in Stage5 fragments; the merge stage owns final include placement.",
            "",
        ]
        for entry in entries:
            name = str(entry.get("name") or entry.get("module") or "global_defines")
            path = Path(str(entry.get("workspace_path") or ""))
            if not path.is_file():
                continue
            content = path.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").strip()
            if not content:
                continue
            chunks.extend(
                [
                    f"## {name}",
                    f"- source: {entry.get('source', '')}",
                    f"- workspace_path: {path}",
                    "```verilog",
                    content,
                    "```",
                    "",
                ]
            )

        text = "\n".join(chunks).strip()
        if not text or text.count("```verilog") == 0:
            return ""
        if len(text) > max_chars:
            text = text[:max_chars].rstrip() + "\n...<global defines truncated>..."
        return text

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
            raise ValueError(f"Stage5 timing bindings missing module `{module_name}`")
        path = self._resolve_output_path(record.binding_file)
        if not path.exists():
            raise FileNotFoundError(f"missing module timing binding sidecar: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return validate_model(ModuleTimingBindingArtifact, json.load(f))

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


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


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


def _strip_verilog_comments(text: str) -> str:
    without_block = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"//.*", "", without_block)


def _find_top_level_equals(line: str) -> int:
    """Return position of first = that is not inside brackets/parens and not ==."""
    depth = 0
    for i, ch in enumerate(line):
        if ch in "[({":
            depth += 1
        elif ch in "])}":
            depth -= 1
        elif ch == "=":
            if depth == 0:
                if i + 1 < len(line) and line[i + 1] == "=":
                    continue
                return i
    return -1


def _strip_rhs_of_assignments(text: str) -> str:
    """Remove RHS of assignments so RHS array indexing like bar[INDEX]
    is not confused with unpacked array dimensions during quality validation."""
    result = []
    for line in text.splitlines():
        eq_pos = _find_top_level_equals(line)
        if eq_pos >= 0:
            result.append(line[:eq_pos] + ";")
        else:
            result.append(line)
    return "\n".join(result)


def _extract_module_frame_section(text: str) -> str:
    match = re.search(
        r"(?ms)^##\s+1\.\s+Module Frame\b.*?(?=^##\s+\d+\.\s+|\Z)",
        text,
    )
    if match:
        return match.group(0).strip()
    return text.strip()
