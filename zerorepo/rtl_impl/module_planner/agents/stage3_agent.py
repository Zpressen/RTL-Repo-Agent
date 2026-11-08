from __future__ import annotations

from zerorepo.rtl_impl.artifact_layout import ArtifactLayout

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

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
from ..utils import ansi_module_ports, interface_contract_errors, markdown_ports
from ..utils.local_repair import ArtifactIssue, model_issues
from ..utils.planning_session import PlanningSession
from ..utils.skeleton_json import compile_skeleton, render_skeleton, evidence_context, spec_context_view, contract_context, design_repair_context, design_context, design_candidate_context
from ..utils.evidence import EvidenceRegistry
from ..schemas.skeleton_draft import ModuleSkeletonDraft
from ..prompts import stage3_design
from pydantic import ValidationError
from .base import BaseStageAgent, model_dump, validate_model
from .global_defines import is_define_only_module
from ..utils.responsibility_planning import module_context, refinement_issues, ordered_blocks


class Stage3Agent(BaseStageAgent):
    stage_name = "stage3_module_skeletons"
    output_model = Stage3ModuleSkeletonArtifact
    system_role = stage3_design.SYSTEM_ROLE
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
        planning_context_retriever: Any | None = None,
        retrieval_limits: dict | None = None,
    ):
        super().__init__(llm_client, context_provider, artifact_sink, logger)
        self.output_root = Path(output_root) if output_root is not None else None
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
        self._refinement_decomposition = partial_artifacts.get("stage2_decomposition")
        self._refinement_input = partial_artifacts.get("stage2_input")
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

        self._active_manifest = artifact
        bundle_by_module = {item.module: item for item in modules_artifact.modules}
        repo_module_by_name = {item.module: item for item in repo_skeleton.modules}

        registry = EvidenceRegistry(self._refinement_input)
        registry.register_tree(self._refinement_decomposition)
        registry.save(self.output_root)
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
            module_spec_path = self._resolve_module_spec_file(task, module_name)
            responsibility_context = module_context(self._refinement_decomposition, module_name)
            context = evidence_context(registry, responsibility_context)
            source_refs = SourceRefs(
                module_contract_ref=f"{modules_artifact.schema_version}::{module_name}",
                repo_skeleton_ref=f"{repo_skeleton.schema_version}::{module_name}",
                module_spec_file=str(Path(module_spec_path).resolve()),
            )
            bound_once = set()
            def validate_design(candidate):
                try:
                    parsed, schema_issues = model_issues(ModuleSkeletonDraft, candidate)
                    if schema_issues:
                        return None, schema_issues
                    for request in parsed.evidence_binding_requests:
                        if request.responsibility_id in bound_once:
                            raise ValueError(f"Evidence binding already attempted for {request.responsibility_id}")
                        ru = next((r for r in self._refinement_decomposition.responsibilities
                                   if r.responsibility_id == request.responsibility_id
                                   and r.responsibility_id in [*bundle.responsibility_ids, *bundle.applicable_constraint_ids]), None)
                        if ru is None:
                            raise ValueError("Evidence binding request must name an owned responsibility")
                        refs = registry.expand(request.source_evidence_ids)
                        before = ru.source_refs[:]
                        from ..schemas import SourceEvidence
                        for ref in refs:
                            if ref not in [r.model_dump() for r in ru.source_refs]:
                                ru.source_refs.append(SourceEvidence.model_validate(ref))
                        from ..utils.responsibility_planning import ledger_errors
                        errors = ledger_errors(self._refinement_decomposition, self._refinement_input)
                        if errors:
                            ru.source_refs = before
                            raise ValueError(str(errors))
                        bound_once.add(ru.responsibility_id)
                        callback = getattr(self, "source_update_callback", None)
                        if callback:
                            callback(self._refinement_decomposition)
                        # The source-only update changes the trusted node input.
                        # Carry its current candidate to the new fingerprint so
                        # an interrupted next request resumes the same entities.
                        inputs["assigned"] = evidence_context(registry, module_context(self._refinement_decomposition, module_name))
                        inputs["module_contract"] = contract_context(next(m for m in modules_artifact.modules if m.module == module_name))
                        from ..utils.evidence import deduplicate_evidence
                        updated = deduplicate_evidence(inputs)
                        for ref in updated.pop("evidence", {}).values():
                            registry.register(ref)
                        updated["evidence_catalog"] = registry.prompt_catalog()
                        projected.clear()
                        projected.update(updated)
                        registry.save(self.output_root)
                    candidate["evidence_binding_requests"] = []
                    current = module_context(self._refinement_decomposition, module_name)
                    missing = [ArtifactIssue("behavioral_obligations", "unknown_evidence",
                        f"{o.obligation_id}: unknown EV IDs; select catalog IDs exactly", category="hardware",
                        unit_id=o.obligation_id, expected={"allowed_evidence_ids_from": "evidence_catalog.entries[].id"})
                        for o in parsed.behavioral_obligations if any(key not in registry.entries for key in o.source_evidence_ids)]
                    if missing:
                        return None, missing
                    export = compile_skeleton(candidate, module=module_name, source_refs=source_refs,
                                              context=current, registry=registry)
                    issues = refinement_issues(export, current, self._refinement_input)
                    for issue in issues:
                        if isinstance(issue.expected, dict) and "allowed_source_refs" in issue.expected:
                            issue.expected["allowed_source_evidence_ids"] = [registry.register(r)
                                for r in issue.expected.pop("allowed_source_refs")]
                    for error in self._validate_export(export, expected_module=module_name,
                            expected_spec_path=module_spec_path, require_ports=require_ports):
                        issues.append(ArtifactIssue("module_frame" if "module_frame" in error or "Module Frame" in error else "design",
                            "interface_or_design", error, category="hardware", module=module_name))
                    ports = self._authoritative_ports(bundle, module_spec_path)
                    for error in interface_contract_errors(ansi_module_ports(export.module_frame), ports,
                                                          label=module_name) if ports else []:
                        issues.append(ArtifactIssue("module_frame", "interface_mismatch", error, category="hardware", module=module_name))
                    try:
                        ordered_blocks(export)
                    except ValueError as exc:
                        issues.append(ArtifactIssue("structural_blocks", "generation_cycle", str(exc), category="hardware", module=module_name))
                    return export, issues
                except (ValueError, KeyError, TypeError, ValidationError) as exc:
                    return None, [ArtifactIssue("design", "invalid_design", str(exc), category="structure", module=module_name)]
            inputs = {"module": module_name, "global_summary": global_summary,
                "assigned": context, "module_contract": contract_context(bundle),
                "architecture": model_dump(repo_module),
                "boundary_contracts": self._boundary_contract_slice(self._refinement_decomposition, module_name=module_name),
                "evidence_catalog": registry.prompt_catalog(), "schema": ModuleSkeletonDraft.model_json_schema()}
            # Full sources occur only in the EV catalog; all other source objects
            # are projected to the same EV identifiers before reaching the model.
            from ..utils.evidence import deduplicate_evidence
            projected = deduplicate_evidence(inputs)
            for ref in projected.pop("evidence", {}).values():
                registry.register(ref)
            projected["evidence_catalog"] = registry.prompt_catalog()
            result = PlanningSession(self).execute(module=module_name, prompt=stage3_design.RULES,
                context=projected, validate=validate_design, context_view=design_context,
                # Restore the full source catalog on repair. Source-only
                # upstream supplements may need sections outside the initial
                # module slice; the strict binding validator is unchanged.
                repair_context=lambda _view, scope, issues: design_repair_context(projected, scope, issues),
                candidate_view=design_candidate_context)
            if result.status != "validated":
                from .base import StageGenerationError
                raise StageGenerationError(f"Stage3 {module_name} needs_repair: " + "; ".join(i.message for i in result.issues))
            export = result.artifact
            doc_text = render_skeleton(export)
            registry.save(self.output_root)
            spec_context_result = spec_context_view(registry, module_context(self._refinement_decomposition, module_name), export)

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
                        "input_fingerprint": artifact.input_fingerprint,
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

        if artifact.schema_version not in {"stage3_skeleton_docs_v1", "stage3_skeleton_json_v3"}:
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
            "schema_version": "stage3_skeleton_json_v3",
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
        export_path = self._resolve_stage3_path(record.export_file)
        return export_path.exists() and self._record_is_reusable(
            record, expected_module=expected_module, expected_spec_path=expected_spec_path)

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
        if not export_path.exists():
            return False
        try:
            with open(export_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            export = validate_model(ModuleSkeletonExport, payload)
            canonical = render_skeleton(export)
            if not doc_path.exists() or doc_path.read_text(encoding="utf-8") != canonical:
                from ..utils.artifact_store import atomic_write_text
                atomic_write_text(doc_path, canonical)
        except Exception:
            return False
        if getattr(self, "_refinement_decomposition", None) is not None:
            context = module_context(self._refinement_decomposition, expected_module)
            if export.schema_version != "module_skeleton_export_v3" or refinement_issues(export, context, self._refinement_input):
                return False
            try:
                registry = EvidenceRegistry(self._refinement_input)
                view = spec_context_view(registry, context, export)
                context_path = self._resolve_stage3_path(record.spec_context_file)
                if not context_path.is_file() or json.loads(context_path.read_text()) != view.model_dump():
                    from ..utils.artifact_store import atomic_write_json
                    atomic_write_json(context_path, view.model_dump())
            except (OSError, ValueError):
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
        if record.export_schema_version not in {"module_skeleton_export_v1", "module_skeleton_export_v3"}:
            errors.append(f"{expected_module}: export_schema_version must remain module_skeleton_export_v1")
        expected_doc = self._doc_relative_path(expected_module)
        expected_export = self._export_relative_path(expected_module)
        if record.doc_file != expected_doc:
            errors.append(f"{expected_module}: doc_file must remain {expected_doc}")
        if record.export_file != expected_export:
            errors.append(f"{expected_module}: export_file must remain {expected_export}")
        if record.export_schema_version == "module_skeleton_export_v3" and not record.spec_context_file:
            errors.append(f"{expected_module}: spec_context_file is required")
        if record.spec_context_file:
            expected_spec_context = self._spec_context_relative_path(expected_module)
            if record.spec_context_file != expected_spec_context:
                errors.append(f"{expected_module}: spec_context_file must remain {expected_spec_context}")
        if record.source_refs.module_contract_ref not in {f"module_contracts_v1::{expected_module}", f"module_contracts_v2::{expected_module}"}:
            errors.append(f"{expected_module}: source_refs.module_contract_ref must remain module_contracts_v1::{expected_module}")
        if record.source_refs.repo_skeleton_ref not in {f"repo_skeleton_v1::{expected_module}", f"repo_skeleton_v2::{expected_module}"}:
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
        if export.schema_version not in {"module_skeleton_export_v1", "module_skeleton_export_v3"}:
            errors.append(f"{expected_module}: export schema_version must remain module_skeleton_export_v1")
        if export.module != expected_module:
            errors.append(f"{expected_module}: export module must remain {expected_module}")
        expected_file_path = f"generate/rtl/{expected_module}.v"
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
        from ..utils import expand_markdown_inputs
        paths = [Path(item).resolve() for item in expand_markdown_inputs(task_input.spec_md_files)]
        matching = next((path for path in paths if path.stem == module_name), None)
        if matching is not None:
            return str(matching)
        if paths:
            return str(paths[0])
        raise FileNotFoundError(f"Stage3 has no input specification for {module_name}")

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
        return ArtifactLayout(self.output_root or Path(".")).module_relative(3, module_name, "skeleton.md")

    def _export_relative_path(self, module_name: str) -> str:
        return ArtifactLayout(self.output_root or Path(".")).module_relative(3, module_name, "skeleton.json")

    def _spec_context_relative_path(self, module_name: str) -> str:
        return ArtifactLayout(self.output_root or Path(".")).module_relative(3, module_name, "spec_context.json")

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
