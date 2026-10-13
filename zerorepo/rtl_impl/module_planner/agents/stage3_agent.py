from __future__ import annotations

import json
import re
import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from zerorepo.rtl_impl.retrieval_agent import ModuleSpecContextRetriever

from ..prompts import stage3_module_skeleton
from ..schemas import (
    ModuleOrganizationArtifact,
    ModuleRecord,
    ModuleSkeletonExport,
    PlannerTaskInput,
    QualityReport,
    SourceRefs,
    Stage2RepoSkeletonArtifact,
    Stage3ModuleSkeletonArtifact,
)
from ..utils import ansi_module_ports, parse_module_skeleton_doc, interface_contract_errors, markdown_ports
from ..utils.local_repair import ArtifactIssue
from ..utils.skeleton_repair import SkeletonRepairAdapter
from .base import BaseStageAgent, model_dump, validate_model
from .global_defines import is_define_only_module


class Stage3Agent(BaseStageAgent):
    stage_name = "stage3_module_skeletons"
    output_model = Stage3ModuleSkeletonArtifact
    system_role = stage3_module_skeleton.SYSTEM_ROLE
    allow_best_effort_quality_fallback = False
    enable_validation = True
    docs_dirname = "module_skeleton_docs"
    exports_dirname = "module_skeleton_json"
    spec_context_dirname = "module_spec_context_json"

    def __init__(
        self,
        llm_client,
        context_provider=None,
        artifact_sink=None,
        logger=None,
        output_root: str | Path | None = None,
        module_spec_context_retriever: ModuleSpecContextRetriever | None = None,
        planning_context_retriever: Any | None = None,
        retrieval_limits: dict | None = None,
    ):
        super().__init__(llm_client, context_provider, artifact_sink, logger)
        self.output_root = Path(output_root) if output_root is not None else None
        self.module_spec_context_retriever = module_spec_context_retriever or ModuleSpecContextRetriever(
            llm_client,
            logger=self.logger,
            cache_root=self.output_root / ".repair_cache" / "module_spec" if self.output_root else None,
            limits=retrieval_limits,
        )
        self.planning_context_retriever = planning_context_retriever

    def run(self, task_input: Any, partial_artifacts: Dict[str, Any]) -> Stage3ModuleSkeletonArtifact:
        return self.run_incremental(task_input, partial_artifacts)

    def run_incremental(
        self,
        task_input: Any,
        partial_artifacts: Dict[str, Any],
        persist_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        spec_context_persist_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Stage3ModuleSkeletonArtifact:
        self._last_quality_errors = []
        task = task_input if isinstance(task_input, PlannerTaskInput) else validate_model(PlannerTaskInput, task_input)
        modules_artifact = self._get_modules_artifact(partial_artifacts)
        repo_skeleton = self._get_repo_skeleton_artifact(partial_artifacts)
        stage_context = self.context_provider.get_stage_context(
            self.stage_name,
            task,
            {"modules": modules_artifact, "stage2": repo_skeleton},
        )
        planned_order = self._planned_module_order(modules_artifact, repo_skeleton)
        global_summary = self._build_global_summary(repo_skeleton)
        artifact = self._bootstrap_artifact(
            task,
            modules_artifact,
            repo_skeleton,
            planned_order,
            global_summary,
            partial_artifacts.get("stage3"),
        )
        requested_fingerprint = str(partial_artifacts.get("stage3_input_fingerprint") or "")
        if requested_fingerprint:
            artifact.input_fingerprint = requested_fingerprint

        bundle_by_module = {item.module: item for item in modules_artifact.modules}
        repo_module_by_name = {item.module: item for item in repo_skeleton.modules}

        for module_name in planned_order:
            if module_name in artifact.completed_modules:
                continue
            bundle = bundle_by_module.get(module_name)
            repo_module = repo_module_by_name.get(module_name)
            if bundle is None:
                raise ValueError(f"Stage3 requires modules.json slice for `{module_name}`")
            if repo_module is None:
                raise ValueError(f"Stage3 requires repo_skeleton.json slice for `{module_name}`")

            require_ports = not is_define_only_module(module_name, repo_skeleton)
            module_spec_markdown, module_spec_path, spec_context_result = self._module_spec_context(
                task,
                module_name=module_name,
                repo_module=repo_module,
                partial_artifacts=partial_artifacts,
            )
            if spec_context_result.fallback_used:
                warning = f"retrieval_degraded: {module_name}: {spec_context_result.fallback_reason}"
                if warning not in artifact.open_issues:
                    artifact.open_issues.append(warning)
            if spec_context_persist_callback is not None:
                spec_context_persist_callback(
                    {
                        "task": task,
                        "module": module_name,
                        "spec_context_file": self._spec_context_relative_path(module_name),
                        "spec_context_payload": model_dump(spec_context_result),
                        "input_fingerprint": requested_fingerprint,
                    }
                )
            if self.planning_context_retriever is not None:
                try:
                    kg_context = self.planning_context_retriever.get_module_context(
                        module_name,
                        require_spec=True,
                        expected_fingerprints={"spec_context": requested_fingerprint},
                    )
                    module_spec_markdown = self.planning_context_retriever.spec_markdown(kg_context)
                except Exception as exc:
                    mode = str(getattr(self.planning_context_retriever.kg_service, "mode", "required"))
                    if mode == "required":
                        raise
                    self.logger.warning(
                        "[%s] Planning KG spec context unavailable for %s; using sidecar: %s",
                        self.stage_name,
                        module_name,
                        exc,
                    )
            expected_file_path = f"rtl/{module_name}.v"
            source_refs = SourceRefs(
                module_contract_ref=f"{modules_artifact.schema_version}::{module_name}",
                repo_skeleton_ref=f"{repo_skeleton.schema_version}::{module_name}",
                module_spec_file=str(Path(module_spec_path).resolve()),
            )
            boundary_contract_slice = self._boundary_contract_slice(
                partial_artifacts.get("stage2_decomposition"),
                module_name=module_name,
            )
            prompt = stage3_module_skeleton.build_prompt(
                module_name=module_name,
                global_summary_json=self.to_pretty_json(global_summary),
                module_spec_markdown=module_spec_markdown,
                module_contract_json=self.to_pretty_json(bundle),
                repo_module_json=self.to_pretty_json(repo_module),
                boundary_contract_json=self.to_pretty_json(boundary_contract_slice),
                stage_context=self.to_pretty_json(
                    {
                        **stage_context,
                        "module": module_name,
                        "completed_modules": list(artifact.completed_modules),
                    }
                ),
            )
            self._log_stage_input(
                prompt=prompt,
                images=[],
                stage_context={
                    **stage_context,
                    "module": module_name,
                    "completed_modules": list(artifact.completed_modules),
                },
            )
            doc_text, export = self._invoke_skeleton_doc_with_repair(
                prompt=prompt,
                images=[],
                expected_module=module_name,
                expected_file_path=expected_file_path,
                source_refs=source_refs,
                require_ports=require_ports,
                expected_ports=self._authoritative_ports(bundle, module_spec_path),
            )

            record = self._build_module_record(export)
            record.spec_context_file = self._spec_context_relative_path(module_name)
            artifact.module_records.append(record)
            artifact.completed_modules.append(module_name)
            artifact.resume_cursor = len(artifact.completed_modules)
            artifact.stage3_status = "module_skeletons_in_progress"

            incremental_errors = self.validate_quality(
                artifact,
                task,
                {"modules": modules_artifact, "stage2": repo_skeleton},
            )
            if incremental_errors:
                raise ValueError(f"{self.stage_name} output failed quality checks during incremental write: {incremental_errors}")

            if persist_callback is not None:
                persist_callback(
                    {
                        "manifest": model_dump(artifact),
                        "task": task,
                        "input_fingerprint": requested_fingerprint,
                        "module": module_name,
                        "doc_file": record.doc_file,
                        "doc_text": doc_text,
                        "export_file": record.export_file,
                        "export_payload": model_dump(export),
                        "spec_context_file": record.spec_context_file,
                        "spec_context_payload": model_dump(spec_context_result),
                    }
                )

        artifact.stage3_status = "module_skeletons_planned"
        final_errors = self.validate_quality(
            artifact,
            task,
            {"modules": modules_artifact, "stage2": repo_skeleton},
        )
        if final_errors:
            raise ValueError(f"{self.stage_name} output failed quality checks after synthesis: {final_errors}")
        artifact.quality_report = self._build_quality_report(final_errors)
        for issue in artifact.open_issues:
            if issue.startswith("retrieval_degraded:"):
                artifact.quality_report.warnings.append(issue)
        artifact.quality_report.soft_warning_count = len(artifact.quality_report.warnings)
        if persist_callback is not None:
            persist_callback({"manifest": model_dump(artifact)})
        self._log_stage_output(artifact)
        self.artifact_sink.record_stage_output(self.stage_name, artifact, task)
        return artifact

    def _boundary_contract_slice(self, decomposition: Any, *, module_name: str) -> Dict[str, Any]:
        if decomposition is None:
            return {"module": module_name, "incoming": [], "outgoing": []}
        payload = model_dump(decomposition) if hasattr(decomposition, "model_dump") else dict(decomposition)
        contracts = payload.get("selected_boundary_contracts") or []
        return {
            "module": module_name,
            "incoming": [
                item for item in contracts if item.get("consumer_module") == module_name
            ],
            "outgoing": [
                item for item in contracts if item.get("producer_module") == module_name
            ],
        }

    def build_prompt(
        self,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        stage_context: Dict[str, Any],
    ) -> tuple[str, List[str]]:
        raise NotImplementedError("Stage3Agent uses a custom per-module incremental flow.")

    def validate_quality(
        self,
        artifact: Stage3ModuleSkeletonArtifact,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
    ) -> List[str]:
        if not self.enable_validation:
            return []
        modules_artifact = self._get_modules_artifact(partial_artifacts)
        repo_skeleton = self._get_repo_skeleton_artifact(partial_artifacts)
        planned_order = self._planned_module_order(modules_artifact, repo_skeleton)
        errors: List[str] = []

        if artifact.schema_version != "stage3_skeleton_docs_v1":
            errors.append("schema_version must remain stage3_skeleton_docs_v1")
        if artifact.task_id != task_input.task_id:
            errors.append(f"task_id must remain {task_input.task_id}")
        if artifact.top_module != repo_skeleton.top_module:
            errors.append(f"top_module must remain {repo_skeleton.top_module}")
        if artifact.module_order != planned_order:
            errors.append(f"module_order must remain {planned_order}")
        if artifact.source_schema_versions.get("modules") != modules_artifact.schema_version:
            errors.append(f"source_schema_versions.modules must remain {modules_artifact.schema_version}")
        if artifact.source_schema_versions.get("repo_skeleton") != repo_skeleton.schema_version:
            errors.append(f"source_schema_versions.repo_skeleton must remain {repo_skeleton.schema_version}")
        if not artifact.global_summary:
            errors.append("global_summary must not be empty")

        expected_completed = planned_order[: len(artifact.completed_modules)]
        if artifact.completed_modules != expected_completed:
            errors.append(
                f"completed_modules must be a prefix of module_order; expected {expected_completed}, got {artifact.completed_modules}"
            )

        if artifact.resume_cursor != len(artifact.completed_modules):
            errors.append("resume_cursor must match completed_modules length")
        if artifact.resume_cursor > len(planned_order):
            errors.append("resume_cursor must not exceed module_order length")

        actual_modules = [item.module for item in artifact.module_records]
        if actual_modules != artifact.completed_modules:
            errors.append("module_records[].module must exactly match completed_modules")

        if artifact.stage3_status == "module_skeletons_planned":
            if artifact.completed_modules != planned_order:
                errors.append("final stage3 artifact must mark every module as completed")
            if len(artifact.module_records) != len(planned_order):
                errors.append("final stage3 artifact must contain one record per module")
        elif artifact.stage3_status != "module_skeletons_in_progress":
            errors.append("stage3_status must be module_skeletons_in_progress or module_skeletons_planned")

        for record in artifact.module_records:
            expected_spec = self._resolve_module_spec_file(task_input, record.module)
            errors.extend(
                self._validate_module_record(
                    record,
                    expected_module=record.module,
                    expected_spec_path=expected_spec,
                )
            )
        return errors

    def _bootstrap_artifact(
        self,
        task: PlannerTaskInput,
        modules_artifact: ModuleOrganizationArtifact,
        repo_skeleton: Stage2RepoSkeletonArtifact,
        planned_order: List[str],
        global_summary: List[str],
        existing: Any,
    ) -> Stage3ModuleSkeletonArtifact:
        payload = {
            "task_id": task.task_id,
            "input_fingerprint": str(existing.input_fingerprint) if isinstance(existing, Stage3ModuleSkeletonArtifact) else "",
            "source_schema_versions": {
                "modules": modules_artifact.schema_version,
                "repo_skeleton": repo_skeleton.schema_version,
            },
            "stage3_status": "module_skeletons_in_progress",
            "top_module": repo_skeleton.top_module,
            "module_order": list(planned_order),
            "completed_modules": [],
            "resume_cursor": 0,
            "global_summary": list(global_summary),
            "module_records": [],
            "open_issues": list(repo_skeleton.open_issues),
            "quality_report": None,
        }
        if not payload["input_fingerprint"]:
            payload["input_fingerprint"] = ""
        artifact = validate_model(Stage3ModuleSkeletonArtifact, payload)
        if existing is None:
            return artifact

        existing_artifact = existing if isinstance(existing, Stage3ModuleSkeletonArtifact) else validate_model(Stage3ModuleSkeletonArtifact, existing)
        if not self._artifact_header_matches(
            existing_artifact,
            task=task,
            modules_artifact=modules_artifact,
            repo_skeleton=repo_skeleton,
            planned_order=planned_order,
        ):
            return artifact

        record_by_module = {item.module: item for item in existing_artifact.module_records}
        cursor = min(existing_artifact.resume_cursor, len(planned_order))
        if cursor == 0 and existing_artifact.completed_modules:
            cursor = min(len(existing_artifact.completed_modules), len(planned_order))

        for module_name in planned_order[:cursor]:
            next_record = record_by_module.get(module_name)
            if next_record is None:
                break
            expected_spec = self._resolve_module_spec_file(task, module_name)
            if not self._record_checkpoint_exists(next_record, expected_module=module_name, expected_spec_path=expected_spec):
                break
            artifact.module_records.append(next_record)
            artifact.completed_modules.append(module_name)
            artifact.resume_cursor = len(artifact.completed_modules)
            if next_record.spec_context_file:
                context_path = self._resolve_stage3_path(next_record.spec_context_file)
                if context_path.exists():
                    try:
                        context = json.loads(context_path.read_text(encoding="utf-8"))
                        if not isinstance(context, dict):
                            raise ValueError("Saved retrieval context must be an object")
                    except (OSError, ValueError) as exc:
                        self.logger.warning("[%s] Cannot restore retrieval warning for %s: %s", self.stage_name, module_name, exc)
                        context = {"fallback_used": True, "fallback_reason": "Saved retrieval context is unreadable; Stage4 must retrieve it again"}
                    if context.get("fallback_used"):
                        warning = f"retrieval_degraded: {module_name}: {context.get('fallback_reason', '')}"
                        if warning not in artifact.open_issues:
                            artifact.open_issues.append(warning)
        if artifact.completed_modules == planned_order and existing_artifact.stage3_status == "module_skeletons_planned":
            artifact.stage3_status = "module_skeletons_planned"
            artifact.quality_report = existing_artifact.quality_report
        return artifact

    def _artifact_header_matches(
        self,
        artifact: Stage3ModuleSkeletonArtifact,
        *,
        task: PlannerTaskInput,
        modules_artifact: ModuleOrganizationArtifact,
        repo_skeleton: Stage2RepoSkeletonArtifact,
        planned_order: List[str],
    ) -> bool:
        return (
            artifact.task_id == task.task_id
            and artifact.top_module == repo_skeleton.top_module
            and artifact.module_order == planned_order
            and artifact.source_schema_versions.get("modules") == modules_artifact.schema_version
            and artifact.source_schema_versions.get("repo_skeleton") == repo_skeleton.schema_version
        )

    def _record_checkpoint_exists(
        self,
        record: ModuleRecord,
        *,
        expected_module: str,
        expected_spec_path: str,
    ) -> bool:
        if self._validate_module_record(record, expected_module=expected_module, expected_spec_path=expected_spec_path):
            return False
        doc_path = self._resolve_stage3_path(record.doc_file)
        export_path = self._resolve_stage3_path(record.export_file)
        return doc_path.exists() and export_path.exists()

    def _planned_module_order(
        self,
        modules_artifact: ModuleOrganizationArtifact,
        repo_skeleton: Stage2RepoSkeletonArtifact,
    ) -> List[str]:
        generation_order = [str(item).strip() for item in repo_skeleton.planning_decisions.generation_order if str(item).strip()]
        module_set = {item.module for item in modules_artifact.modules}
        if generation_order and len(generation_order) == len(module_set) and set(generation_order) == module_set:
            return generation_order
        return list(modules_artifact.module_order)

    def _build_global_summary(self, repo_skeleton: Stage2RepoSkeletonArtifact) -> List[str]:
        summary: List[str] = []
        if repo_skeleton.global_invariants.system_role:
            summary.append(repo_skeleton.global_invariants.system_role)
        clock = repo_skeleton.global_invariants.clocking_model.primary_clock
        reset = repo_skeleton.global_invariants.clocking_model.reset_signal
        reset_style = repo_skeleton.global_invariants.clocking_model.reset_style
        if clock or reset or reset_style:
            summary.append(
                ", ".join(
                    item
                    for item in [
                        f"primary clock: {clock}" if clock else "",
                        f"reset: {reset}" if reset else "",
                        reset_style,
                    ]
                    if item
                )
            )
        summary.extend(item for item in repo_skeleton.global_invariants.cross_module_alignment if str(item).strip())
        summary.extend(item for item in repo_skeleton.global_invariants.global_data_conventions if str(item).strip())
        summary.extend(
            item for item in repo_skeleton.planning_decisions.top_level_integration_notes if str(item).strip()
        )
        if repo_skeleton.planning_decisions.generation_order:
            summary.append(
                f"generation order: {', '.join(repo_skeleton.planning_decisions.generation_order)}"
            )
        deduped: List[str] = []
        seen: set[str] = set()
        for item in summary:
            normalized = str(item or "").strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    def _authoritative_ports(self, bundle, spec_path):
        # A standalone module port table takes precedence over extracted facts.
        path = Path(spec_path)
        if path.stem == bundle.module and path.is_file():
            ports = markdown_ports(path.read_text(encoding="utf-8"))
            if ports:
                return ports
        contract = getattr(bundle, "interface_contract", None)
        return list(getattr(contract, "ports", []) or [])

    def _invoke_skeleton_doc_with_repair(
        self, *, prompt: str, images: List[str], expected_module: str,
        expected_file_path: str, source_refs: SourceRefs, require_ports: bool = False,
        expected_ports=None,
    ) -> tuple[str, ModuleSkeletonExport]:
        def quality(export):
            issues = []
            for error in self._validate_export(
                export, expected_module=expected_module,
                expected_spec_path=source_refs.module_spec_file, require_ports=require_ports,
            ):
                if "module_frame" in error or "Module Frame" in error:
                    continue  # independently checked on the candidate frame
                section = "Module Frame"
                path = "module_frame"
                if "chosen_decisions" in error:
                    section, path = "Decision Ledger", "decision_ledger.chosen_decisions"
                elif "control_style" in error:
                    section, path = "Behavioral Overlay", "module_behavior.control_style"
                issues.append(ArtifactIssue(path, "hardware_constraint", error, category="hardware", section=section))
            return issues

        def partial_quality(candidate):
            if "module_frame" not in candidate:
                return []
            errors = self._validate_module_frame_interface(
                candidate["module_frame"], expected_module=expected_module, require_ports=require_ports,
            )
            if expected_ports:
                errors.extend(interface_contract_errors(
                    ansi_module_ports(candidate["module_frame"]), expected_ports, label=f"{expected_module} Module Frame",
                ))
            return [ArtifactIssue("module_frame.ports", "interface_mismatch", error,
                                  category="hardware", section="Module Frame") for error in errors]

        # The example and general formatting rules are supplied per target; retain
        # the current module's authoritative source context for semantic repairs.
        context = prompt.split("Global summary:\n", 1)[-1]
        adapter = SkeletonRepairAdapter(
            expected_module=expected_module, expected_file_path=expected_file_path,
            source_refs=source_refs, context="Global summary:\n" + context,
            example=stage3_module_skeleton.EXAMPLE_OUTPUT, quality_validator=quality, partial_validator=partial_quality,
        )
        result = self._invoke_local_repair(
            prompt=prompt, images=images, adapter=adapter, max_attempts=self.max_parse_attempts,
        )
        self.logger.info(
            "[%s] Validation coverage for %s: format/structure checked; interface %s; "
            "natural-language timing/ownership/boundary completeness requires downstream behavioral validation",
            self.stage_name, expected_module, "checked" if expected_ports else "unverified (no authoritative port list)",
        )
        return result.candidate, result.artifact

    def _build_module_record(self, export: ModuleSkeletonExport) -> ModuleRecord:
        return ModuleRecord(
            module=export.module,
            doc_file=self._doc_relative_path(export.module),
            export_file=self._export_relative_path(export.module),
            export_schema_version=export.schema_version,
            source_refs=export.source_refs,
            planning_note=export.planning_note,
            block_ids=[item.block_id for item in export.structural_blocks],
        )

    def _record_is_reusable(self, record: ModuleRecord, *, expected_module: str, expected_spec_path: str) -> bool:
        if self._validate_module_record(record, expected_module=expected_module, expected_spec_path=expected_spec_path):
            return False
        doc_path = self._resolve_stage3_path(record.doc_file)
        export_path = self._resolve_stage3_path(record.export_file)
        if not doc_path.exists() or not export_path.exists():
            return False
        try:
            with open(export_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            export = validate_model(ModuleSkeletonExport, payload)
            parsed = parse_module_skeleton_doc(
                doc_path.read_text(encoding="utf-8"), expected_module=expected_module,
                expected_file_path=f"rtl/{expected_module}.v", source_refs=record.source_refs,
            )
            if model_dump(parsed) != model_dump(export):
                return False
        except Exception:
            return False
        return not self._validate_export(export, expected_module=expected_module, expected_spec_path=expected_spec_path)

    def _validate_module_record(
        self,
        record: ModuleRecord,
        *,
        expected_module: str,
        expected_spec_path: str,
    ) -> List[str]:
        errors: List[str] = []
        if record.module != expected_module:
            errors.append(f"{expected_module}: record.module must remain {expected_module}")
        if record.export_schema_version != "module_skeleton_export_v1":
            errors.append(f"{expected_module}: export_schema_version must remain module_skeleton_export_v1")
        expected_doc = self._doc_relative_path(expected_module)
        expected_export = self._export_relative_path(expected_module)
        if record.doc_file != expected_doc:
            errors.append(f"{expected_module}: doc_file must remain {expected_doc}")
        if record.export_file != expected_export:
            errors.append(f"{expected_module}: export_file must remain {expected_export}")
        if record.spec_context_file:
            expected_spec_context = self._spec_context_relative_path(expected_module)
            if record.spec_context_file != expected_spec_context:
                errors.append(f"{expected_module}: spec_context_file must remain {expected_spec_context}")
        if record.source_refs.module_contract_ref != f"module_contracts_v1::{expected_module}":
            errors.append(f"{expected_module}: source_refs.module_contract_ref must remain module_contracts_v1::{expected_module}")
        if record.source_refs.repo_skeleton_ref != f"repo_skeleton_v1::{expected_module}":
            errors.append(f"{expected_module}: source_refs.repo_skeleton_ref must remain repo_skeleton_v1::{expected_module}")
        if str(Path(record.source_refs.module_spec_file).resolve()) != str(Path(expected_spec_path).resolve()):
            errors.append(f"{expected_module}: source_refs.module_spec_file must match the resolved spec file path")
        if not record.block_ids:
            errors.append(f"{expected_module}: block_ids must not be empty")
        return errors

    def _validate_export(
        self,
        export: ModuleSkeletonExport,
        *,
        expected_module: str,
        expected_spec_path: str,
        require_ports: bool = False,
    ) -> List[str]:
        errors: List[str] = []
        if export.schema_version != "module_skeleton_export_v1":
            errors.append(f"{expected_module}: export schema_version must remain module_skeleton_export_v1")
        if export.module != expected_module:
            errors.append(f"{expected_module}: export module must remain {expected_module}")
        expected_file_path = f"rtl/{expected_module}.v"
        if export.file_path != expected_file_path:
            errors.append(f"{expected_module}: export file_path must remain {expected_file_path}")
        if str(Path(export.source_refs.module_spec_file).resolve()) != str(Path(expected_spec_path).resolve()):
            errors.append(f"{expected_module}: export source_refs.module_spec_file must match the resolved spec file path")
        if not export.module_frame.strip():
            errors.append(f"{expected_module}: module_frame must not be empty")
        errors.extend(
            self._validate_module_frame_interface(
                export.module_frame,
                expected_module=expected_module,
                require_ports=require_ports,
            )
        )
        if not export.structural_blocks:
            errors.append(f"{expected_module}: structural_blocks must not be empty")
        if not export.decision_ledger.chosen_decisions:
            errors.append(f"{expected_module}: decision_ledger.chosen_decisions must not be empty")
        if export.module_behavior.control_style == "undecided" and self._module_requires_strict_behavior(expected_module):
            errors.append(f"{expected_module}: module_behavior.control_style must not remain undecided")
        return errors

    def _validate_module_frame_interface(
        self,
        module_frame: str,
        *,
        expected_module: str,
        require_ports: bool = False,
    ) -> List[str]:
        errors: list[str] = []
        placeholder_patterns = [
            r"port\s+list\s+placeholder",
            r"//\s*ports?\b",
            r"\bTODO\b",
            r"<\s*ports?\s*>",
        ]
        for pattern in placeholder_patterns:
            if re.search(pattern, module_frame, flags=re.IGNORECASE):
                errors.append(f"{expected_module}: module_frame must not contain a port placeholder")
                break
        module_names = re.findall(r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)", module_frame)
        if module_names != [expected_module]:
            errors.append(
                f"{expected_module}: module_frame must declare exactly one module named {expected_module}"
            )
        if len(re.findall(r"\bendmodule\b", module_frame)) != 1:
            errors.append(f"{expected_module}: module_frame must contain exactly one endmodule")
        if require_ports and not ansi_module_ports(module_frame):
            errors.append(
                f"{expected_module}: Module Frame must declare at least one concrete ANSI port"
            )
        return errors

    def _module_requires_strict_behavior(self, module_name: str) -> bool:
        return module_name not in {"sd_defines"}

    def _resolve_module_spec_file(self, task_input: PlannerTaskInput, module_name: str) -> str:
        paths = [Path(item).resolve() for item in task_input.spec_md_files if str(item).strip()]

        for path in paths:
            if path.is_file() and path.stem == module_name:
                return str(path)
            if path.is_dir():
                candidate = path / f"{module_name}.md"
                if candidate.exists():
                    return str(candidate.resolve())

        checked_dirs: List[Path] = []
        for path in paths:
            parent = path if path.is_dir() else path.parent
            if parent in checked_dirs:
                continue
            checked_dirs.append(parent)
            candidate = parent / f"{module_name}.md"
            if candidate.exists():
                return str(candidate.resolve())

        for path in paths:
            if path.is_file():
                return str(path.resolve())

        raise FileNotFoundError(
            f"Stage3 could not find a standalone spec file for module `{module_name}`. "
            f"Expected one of the provided spec_md_files or a sibling file named `{module_name}.md`."
        )

    def _module_spec_context(
        self,
        task_input: PlannerTaskInput,
        *,
        module_name: str,
        repo_module: Any | None,
        partial_artifacts: Dict[str, Any],
    ) -> tuple[str, str, Any]:
        primary_spec_file = self._resolve_module_spec_file(task_input, module_name)
        repo_skeleton = self._get_repo_skeleton_artifact(partial_artifacts)
        result = self.module_spec_context_retriever.select_module_spec_context(
            module_name=module_name,
            spec_md_files=task_input.spec_md_files,
            repo_module=repo_module,
            fact_ledger=self._fact_ledger(partial_artifacts),
            is_top_module=module_name == repo_skeleton.top_module,
            primary_spec_file=primary_spec_file,
        )
        lines = [
            f"# Retrieved specification context for {module_name}",
            "",
        ]
        if result.fallback_used:
            lines.extend(
                [
                    f"Retrieval fallback: {result.fallback_reason}",
                    "",
                ]
            )
        for block in result.blocks:
            lines.extend(
                [
                    f"## {block.block_id}",
                    f"Source: {block.source_file or 'unknown'}",
                    "",
                    block.text,
                    "",
                ]
            )
        if result.open_issues:
            lines.extend(["## Retrieval Open Issues", *[f"- {item}" for item in result.open_issues]])
        # The source ref is the module's resolved primary spec, not whichever
        # supplemental retrieval block happened to appear first.
        return "\n".join(lines).strip(), primary_spec_file, result

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

    def _get_modules_artifact(self, partial_artifacts: Dict[str, Any]) -> ModuleOrganizationArtifact:
        candidate = partial_artifacts.get("modules")
        if candidate is None:
            raise ValueError("Stage3 module skeleton planning requires partial_artifacts['modules']")
        if isinstance(candidate, ModuleOrganizationArtifact):
            return candidate
        return validate_model(ModuleOrganizationArtifact, candidate)

    def _get_repo_skeleton_artifact(self, partial_artifacts: Dict[str, Any]) -> Stage2RepoSkeletonArtifact:
        candidate = partial_artifacts.get("stage2")
        if candidate is None:
            raise ValueError("Stage3 module skeleton planning requires partial_artifacts['stage2']")
        if isinstance(candidate, Stage2RepoSkeletonArtifact):
            return candidate
        return validate_model(Stage2RepoSkeletonArtifact, candidate)

    def _doc_relative_path(self, module_name: str) -> str:
        return f"{self.docs_dirname}/{module_name}.md"

    def _export_relative_path(self, module_name: str) -> str:
        return f"{self.exports_dirname}/{module_name}.json"

    def _spec_context_relative_path(self, module_name: str) -> str:
        return f"{self.spec_context_dirname}/{module_name}.json"

    def _resolve_stage3_path(self, relative_or_absolute: str) -> Path:
        path = Path(relative_or_absolute)
        if path.is_absolute() or self.output_root is None:
            return path
        return (self.output_root / path).resolve()

    @staticmethod
    def _build_quality_report(errors: List[str]) -> QualityReport:
        unchecked = [
            "unverified: prose timing/reset/latency obligations require downstream behavioral validation",
            "unverified: prose shared-object ownership has not been mechanically proven",
            "unverified: prose logical-boundary coverage has not been mechanically proven",
        ]
        return QualityReport(
            hard_fail_count=len(errors),
            soft_warning_count=len(unchecked),
            warnings=unchecked,
            auto_fixes=[],
        )
