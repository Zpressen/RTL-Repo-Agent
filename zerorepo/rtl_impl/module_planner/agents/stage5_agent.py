from __future__ import annotations

import copy
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
    PlannerTaskInput,
    Stage3ModuleSkeletonArtifact,
    Stage4ModulePlansArtifact,
    Stage4SpecBlocksArtifact,
    Stage5CodegenArtifact,
    SubtaskCodeArtifact,
)
from .base import BaseStageAgent, StageGenerationError, model_dump, validate_model
from ..utils.artifact_store import atomic_write_json, atomic_write_text
from ..utils.local_repair import ArtifactIssue, REPAIR_POLICY_VERSION, fingerprint
from ..utils.codegen_repair import SubtaskCodeRepairAdapter
from ..utils.stage5_sources import SOURCE_VERSION, Stage5LogEvidence, changed_components, compact_stage5_interfaces, source_snapshot, stable_planning_context, stage5_prompt_context
from ..utils.stage5_store import Stage5Store
from zerorepo.rtl_impl.port_contracts import ansi_module_ports
from .global_defines import (
    build_stage5_global_defines_summary,
    copy_e203_canonical_define_files,
    copy_official_define_file,
    is_define_only_module,
    read_global_defines_manifest,
)


class Stage5Agent(BaseStageAgent):
    stage_name = "stage5_codegen"
    output_model = Stage5CodegenArtifact
    system_role = stage5_subtask_codegen.SYSTEM_ROLE
    allow_best_effort_quality_fallback = False
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
        oracle_root: str | Path = "/home/mokita/RealBench",
    ):
        super().__init__(llm_client, context_provider, artifact_sink, logger)
        self.output_root = Path(output_root) if output_root is not None else None
        self.workspace_root = Path(workspace_root) if workspace_root is not None else self._default_workspace_root()
        self.planning_context_retriever = planning_context_retriever
        self.oracle_root = Path(oracle_root).expanduser()
        self._validated_subtasks_by_module: dict[str, list[str]] = {}
        self._candidate_keys = {}
        self._source_evidence = None

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
            raise ValueError(f"{self.stage_name} final validation failed: {quality_errors}")
        if persist_callback is not None:
            persist_callback({"manifest": model_dump(artifact)})
        self.artifact_sink.record_stage_output(self.stage_name, artifact, task)
        return artifact

    def run_module(
        self,
        task_input: Any,
        partial_artifacts: Dict[str, Any],
        module_name: str,
        *,
        reuse_only: bool = False,
    ) -> ModuleCodegenRecord:
        task = task_input if isinstance(task_input, PlannerTaskInput) else validate_model(PlannerTaskInput, task_input)
        self._validated_subtasks_by_module[module_name] = []
        self._ensure_global_defines_copied(task, partial_artifacts)
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
        skeleton_document = Path(module_skeleton_file).read_text() if module_skeleton_file and Path(module_skeleton_file).is_file() else None
        planning_kg_source: Dict[str, Any] | None = None
        if self.planning_context_retriever is not None:
            try:
                planning_kg_source = self.planning_context_retriever.get_module_context(
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
        repo_modules = repo_skeleton.get("modules", []) if isinstance(repo_skeleton, dict) else getattr(repo_skeleton, "modules", [])
        repo_module = next((item for item in repo_modules if (item.get("module") if isinstance(item, dict) else item.module) == module_name), None)
        module_info = repo_module if isinstance(repo_module, dict) else model_dump(repo_module) if repo_module is not None else {}
        responsibility = {key: module_info[key] for key in ("module", "role", "rationale", "module_kind", "parents", "children", "module_decision") if key in module_info}
        for key in ("parents", "children"):
            if key in responsibility:
                responsibility[key] = sorted(responsibility[key] or [])
        child_interfaces = []
        for child in sorted(module_info.get("children") or []):
            # Only the runner supplies this map after verifying a whole accepted
            # debug generation and its immutable original dependency contracts.
            child_path = Path(partial_artifacts.get("_stage5_dependency_files", {}).get(
                child, self.workspace_root / "merged" / f"{child}.v"))
            if child_path.is_file():
                ports = [{"name": p.name, "direction": p.direction, "width": p.width} for p in ansi_module_ports(child_path.read_text())]
            else:
                interface = next((c for c in (planning_kg_source or {}).get("child_code_interfaces", []) if c.get("module") == child), {})
                ports = stable_planning_context({"child_code_interfaces": [interface]}).get("child_code_interfaces", [{}])[0].get("ports", [])
            child_interfaces.append({"module": child, "ports": sorted(ports, key=lambda p: p["name"])})
        candidate_key = fingerprint({"task": task.task_id, "module": module_name, "plan": module_plan,
            "spec": module_spec, "skeleton": module_skeleton, "skeleton_document": skeleton_document, "responsibility": responsibility,
            "child_interfaces": child_interfaces, "defines": read_global_defines_manifest(self.workspace_root)})
        self._candidate_keys[module_name] = candidate_key
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
        saved = self._read_checkpoint(module_name, task.task_id)
        store = Stage5Store(self.workspace_root)
        if not reuse_only:
            candidate_path = store.candidate_file(module_name, candidate_key)
            if candidate_path.exists():
                try:
                    candidate = json.loads(candidate_path.read_text())
                    store.validate(candidate)
                    saved = candidate
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    self.logger.info("[%s] Ignoring invalid candidate for %s: %s", self.stage_name, module_name, exc)
        if saved and not saved.get("bundle_path"):
            # Preserve legacy state before any replacement, including failed imports.
            try:
                text = workspace_file.read_text()
                contract_payload = json.loads(self._contracts_file(module_name).read_text())
                if fingerprint(text) == saved["fragment_fingerprint"] and fingerprint(contract_payload) == saved["contracts_fingerprint"]:
                    preserved = store.bundle(saved, text, contract_payload)
                    atomic_write_json(self.workspace_root / ".stage5_history" / module_name / f"{fingerprint(saved)}.json", preserved)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                self.logger.info("[%s] Legacy checkpoint preservation unavailable: %s", self.stage_name, exc)
        if reuse_only:
            if saved.get("status") != "completed":
                raise StageGenerationError("No completed Stage5 checkpoint")
            try:
                if saved["fragment_fingerprint"] != fingerprint(workspace_file.read_text(encoding="utf-8")):
                    raise ValueError("Fragment content changed since validation")
                contracts_payload = json.loads(self._contracts_file(module_name).read_text(encoding="utf-8"))
                if saved["contracts_fingerprint"] != fingerprint(contracts_payload):
                    raise ValueError("Contract content changed since validation")
                sections = self._fragment_sections(workspace_file.read_text(encoding="utf-8"))
                if list(sections) != [item.id for item in module_plan.subtasks]:
                    raise ValueError("Fragment identities/order mismatch")
            except (OSError, ValueError, KeyError) as exc:
                raise StageGenerationError(str(exc)) from exc
        saved_entries = saved.get("subtasks", []) + saved.get("pending_subtasks", [])
        if reuse_only and len(saved_entries) != len(module_plan.subtasks):
            raise StageGenerationError("Checkpoint does not cover the complete module plan")
        accepted_entries = []
        migrated_sources = False
        reusable_prefix = True
        previous_snippets = ""
        for subtask_index, subtask in enumerate(module_plan.subtasks):
            if subtask.timing_obligation_ids or subtask.logical_value_tags:
                raise ValueError(
                    f"Stage5 requires empty compatibility timing fields for {module_name}/{subtask.id}"
                )
            selected_blocks = self._select_spec_blocks(module_spec, subtask.spec_refs)
            selected_block_ids = {item["block_id"] for item in selected_blocks}
            supplemental_interface_blocks = [
                item for item in module_interface_blocks if item["block_id"] not in selected_block_ids
            ]
            current_subtask_payload = model_dump(subtask)
            current_subtask_payload.pop("timing_obligation_ids", None)
            current_subtask_payload.pop("logical_value_tags", None)
            current_subtask_json = self.to_pretty_json(current_subtask_payload)
            selected_spec_blocks_json = self.to_pretty_json(selected_blocks)
            module_interface_spec_blocks_json = self.to_pretty_json(supplemental_interface_blocks)
            global_defines_context = self._build_stage5_global_defines_summary(
                relevant_texts=[
                    current_subtask_json,
                    module_skeleton,
                    selected_spec_blocks_json,
                    module_interface_spec_blocks_json,
                    previous_snippets,
                ],
            )
            planning_kg_context = ""
            if planning_kg_source is not None:
                try:
                    planning_kg_context = self.planning_context_retriever.to_stage5_prompt_json(
                        stage5_prompt_context(planning_kg_source),
                        subtask.spec_refs,
                        max_chars=12000,
                    )
                    planning_kg_context = compact_stage5_interfaces(planning_kg_context, child_interfaces)
                except Exception as exc:
                    mode = str(getattr(self.planning_context_retriever.kg_service, "mode", "required"))
                    if mode == "required":
                        raise
                    self.logger.warning(
                        "[%s] Compact planning KG context unavailable for %s/%s; "
                        "using sidecars: %s",
                        self.stage_name,
                        module_name,
                        subtask.id,
                        exc,
                    )
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
                "global_defines_summary_chars": len(global_defines_context),
                "planning_kg_context_chars": len(planning_kg_context),
            }
            prompt = stage5_subtask_codegen.build_prompt(
                task_id=task.task_id,
                module_name=module_name,
                current_subtask=current_subtask_json,
                module_skeleton=module_skeleton,
                selected_spec_blocks=selected_spec_blocks_json,
                module_interface_spec_blocks=module_interface_spec_blocks_json,
                previous_module_snippets=previous_snippets,
                global_defines_context=global_defines_context,
                planning_kg_context=planning_kg_context,
                stage_context=self.to_pretty_json(stage_context),
            )
            adapter = SubtaskCodeRepairAdapter(
                task_id=task.task_id, module=module_name, subtask=subtask, context=prompt,
                validator=lambda candidate, expected_module=module_name, expected_subtask=subtask: (
                    self._validate_subtask_code(
                        candidate,
                        task,
                        expected_module,
                        expected_subtask,
                    )
                ), contract_validator=self._contract_quality_issues,
            )
            legacy = {
                "policy": REPAIR_POLICY_VERSION, "task_id": task.task_id, "module": module_name,
                "subtask": subtask, "skeleton": module_skeleton,
                "spec_blocks": selected_blocks, "interface_blocks": supplemental_interface_blocks,
                "previous_snippets": previous_snippets, "global_defines": global_defines_context,
                "planning_kg": planning_kg_context,
            }
            legacy["planning_kg"] = self.planning_context_retriever.to_stage5_prompt_json(
                planning_kg_source, subtask.spec_refs, max_chars=12000) if planning_kg_source is not None else ""
            snapshot = source_snapshot(legacy=legacy, responsibility=responsibility, child_interfaces=child_interfaces,
                                       skeleton_document=skeleton_document)
            unit_fingerprint = fingerprint(snapshot)
            provenance = None
            artifact = None
            if reusable_prefix and subtask_index < len(saved_entries):
                entry = saved_entries[subtask_index]
                try:
                    if entry["subtask_id"] != subtask.id:
                        raise ValueError("Subtask identity changed")
                    if entry.get("fingerprint_version") == SOURCE_VERSION:
                        if fingerprint(entry.get("source_snapshot")) != entry.get("source_fingerprint"):
                            raise ValueError("Source snapshot checksum mismatch")
                        if entry.get("source_fingerprint") != unit_fingerprint:
                            canonical = copy.deepcopy(entry["source_snapshot"])
                            for key in ("parents", "children"):
                                if key in canonical.get("responsibility", {}):
                                    canonical["responsibility"][key] = sorted(canonical["responsibility"][key] or [])
                            if fingerprint(canonical) != unit_fingerprint:
                                raise ValueError("Source components changed: " + ", ".join(changed_components(entry.get("source_snapshot"), snapshot)))
                            provenance = {"kind": "canonical_dependency_order", "previous_source_fingerprint": entry["source_fingerprint"]}
                    else:
                        if self._source_evidence is None:
                            self._source_evidence = Stage5LogEvidence(self.workspace_root.parent / "zerorepo.log")
                        provenance = self._source_evidence.proves_legacy(entry, legacy, responsibility, child_interfaces)
                        if provenance and skeleton_document is not None and not self._source_evidence.proves_full_skeleton(module_name):
                            provenance = None
                        if not provenance:
                            raise ValueError("Legacy checkpoint lacks matching source evidence; regeneration required")
                    if entry["artifact_fingerprint"] != fingerprint(entry["artifact"]):
                        raise ValueError("Checkpoint artifact checksum mismatch")
                    cached = validate_model(SubtaskCodeArtifact, entry["artifact"])
                    errors = self._validate_subtask_code(cached, task, module_name, subtask)
                    errors.extend(issue.message for issue in adapter.inspect(entry["artifact"]).issues)
                    if errors:
                        raise ValueError("; ".join(errors))
                    artifact = cached
                    migrated_sources = migrated_sources or provenance is not None
                    self.logger.info("[%s] Reusing validated subtask %s/%s", self.stage_name, module_name, subtask.id)
                except (ValueError, KeyError, TypeError) as exc:
                    self.logger.info("[%s] Subtask %s invalidated: %s", self.stage_name, subtask.id, exc)
            if artifact is None:
                if reuse_only:
                    raise StageGenerationError(f"Subtask checkpoint is stale: {subtask.id}")
                self.logger.info("[%s] Generating %s/%s into %s", self.stage_name, module_name, subtask.id, workspace_file)
                self._log_stage_input(prompt=prompt, images=[], stage_context=stage_context)
                reusable_prefix = False
                artifact = self._invoke_local_repair(
                    prompt=prompt, images=[], adapter=adapter,
                    max_attempts=max(self.max_parse_attempts, self.max_quality_attempts),
                ).artifact
            if artifact.timing_obligation_ids:
                raise ValueError(
                    f"Stage5 generated non-empty retired timing fields for {module_name}/{subtask.id}"
                )
            updated_text = self._upsert_subtask_section(previous_snippets, subtask, artifact.code)
            contract_entries.append(
                self._contract_entry(
                    artifact=artifact,
                    subtask=subtask,
                )
            )
            accepted_entries.append({
                "subtask_id": subtask.id, "input_fingerprint": unit_fingerprint,
                "fingerprint_version": SOURCE_VERSION, "source_fingerprint": unit_fingerprint,
                "source_snapshot": snapshot, **({"migration_evidence": provenance} if provenance else {}),
                "artifact": model_dump(artifact), "artifact_fingerprint": fingerprint(model_dump(artifact)),
            })
            if not reuse_only:
                self._commit_subtasks(
                    module_name=module_name, task_id=task.task_id, entries=accepted_entries,
                    fragments=updated_text, contracts=contract_entries,
                    input_fingerprint=str(partial_artifacts.get("stage5_input_fingerprint") or ""),
                    complete=subtask_index == len(module_plan.subtasks) - 1,
                    pending=saved_entries[len(accepted_entries):] if reusable_prefix else [],
                )
            previous_snippets = updated_text
            completed_subtasks.append(subtask.id)
            self._validated_subtasks_by_module[module_name] = list(completed_subtasks)

        if reuse_only:
            if previous_snippets != workspace_file.read_text(encoding="utf-8"):
                raise StageGenerationError("Checkpoint artifacts do not reproduce the fragment file")
            if contract_entries != contracts_payload.get("contracts"):
                raise StageGenerationError("Checkpoint artifacts do not reproduce the contract sidecar")
            if migrated_sources:
                self._commit_subtasks(module_name=module_name, task_id=task.task_id, entries=accepted_entries,
                    fragments=previous_snippets, contracts=contract_entries,
                    input_fingerprint=str(partial_artifacts.get("stage5_input_fingerprint") or ""), complete=True)

        return ModuleCodegenRecord(
            module=module_name,
            workspace_file=str(workspace_file),
            completed_subtasks=completed_subtasks,
        )

    def _checkpoint_file(self, module_name):
        return (self.workspace_root / "fragments" / f"{module_name}_checkpoint.json").resolve()

    def _read_checkpoint(self, module_name, task_id=None):
        path = self._checkpoint_file(module_name)
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != "stage5_subtasks_v1" or payload.get("policy") != REPAIR_POLICY_VERSION:
                return {}
            if payload.get("module") != module_name or (task_id is not None and payload.get("task_id") != task_id):
                return {}
            if not isinstance(payload.get("subtasks"), list) or not all(isinstance(item, dict) for item in payload["subtasks"]):
                return {}
            if not isinstance(payload.get("pending_subtasks", []), list) or not all(isinstance(item, dict) for item in payload.get("pending_subtasks", [])):
                return {}
            if payload.get("bundle_path"):
                Stage5Store(self.workspace_root).validate(payload)
                publishing = self.workspace_root / ".stage5_publish" / f"{module_name}.json"
                if publishing.exists():
                    Stage5Store(self.workspace_root).restore_aliases(payload)
                    publishing.unlink()
            return payload
        except (ValueError, TypeError, OSError) as exc:
            self.logger.info("[%s] Ignoring invalid checkpoint %s: %s", self.stage_name, path, exc)
            return {}

    def _commit_subtasks(self, *, module_name, task_id, entries, fragments, contracts, input_fingerprint, complete, pending=None):
        contract_payload = {"schema_version": "stage5_fragment_contracts_v1", "module": module_name,
                            "input_fingerprint": input_fingerprint, "contracts": contracts}
        checkpoint = {
            "schema_version": "stage5_subtasks_v1", "policy": REPAIR_POLICY_VERSION,
            "module": module_name, "task_id": task_id,
            "status": "completed" if complete else "in_progress",
            "input_fingerprint": input_fingerprint, "subtasks": entries,
            "pending_subtasks": [] if complete else (pending or []),
            "fragment_fingerprint": fingerprint(fragments),
            "contracts_fingerprint": fingerprint(contract_payload),
        }
        store = Stage5Store(self.workspace_root)
        marker = store.bundle(checkpoint, fragments, contract_payload)
        candidate_path = store.candidate_file(module_name, self._candidate_keys.get(module_name, "import"))
        atomic_write_json(candidate_path, marker)
        current = self._read_checkpoint(module_name, task_id)
        if current.get("status") == "completed" and not complete:
            return
        # Immutable bundles make a crash between alias writes recoverable from
        # the previous active marker. The marker changes only after all writes.
        publishing = self.workspace_root / ".stage5_publish" / f"{module_name}.json"
        atomic_write_json(publishing, {"candidate": marker.get("bundle_path")})
        atomic_write_text(self._workspace_file(module_name), fragments)
        self._write_contracts_file(module_name, contracts, input_fingerprint=input_fingerprint)
        atomic_write_json(self._checkpoint_file(module_name), marker)
        publishing.unlink()

    def _contract_quality_issues(self, artifact):
        if artifact.contract is None:
            return []
        # Limit hard mismatches to simple assignment statements. The broad
        # extraction below is a diagnostic hint (e.g. <= in an if can be a
        # comparison), and must not manufacture contract obligations.
        obvious = set(re.findall(
            r"(?m)^\s*(?:assign\s+)?([A-Za-z_][A-Za-z0-9_$]*)\s*(?:\[[^\]]+\])?\s*(?:<=|(?<![=!<>])=(?![=]))",
            _strip_verilog_comments(artifact.code),
        ))
        missing = sorted(obvious - set(artifact.contract.writes))
        if missing:
            return [ArtifactIssue(
                "contract.writes", "contract_code_mismatch",
                f"Contract omits apparent assignment targets {missing}; review against code and source",
                expected=sorted(obvious), actual=list(artifact.contract.writes),
                category="hardware", unit_id=artifact.subtask_id,
            )]
        return []

    def _contract_entry(self, *, artifact: SubtaskCodeArtifact, subtask: ModulePlanSubtask) -> Dict[str, Any]:
        extracted = self._extract_fragment_contract(artifact.code)
        if artifact.contract is None:
            raise ValueError("Cannot commit a generated fragment without its explicit contract")
        contract = model_dump(artifact.contract)
        return {
            "subtask_id": subtask.id,
            "target": subtask.target,
            "spec_refs": list(subtask.spec_refs),
            "timing_obligation_ids": [],
            "contract": contract,
            "analysis": {
                "extracted_writes": extracted.writes,
                "extracted_reads": extracted.reads,
                "mode": "heuristic_hints_only",
                "timing_validation": "unverified",
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
        atomic_write_json(path, payload)
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
        if artifact.status != "completed":
            errors.append(f"stage5 is {artifact.status}, not completed")
        if artifact.module_order != spec_blocks.module_order:
            errors.append("module_order must exactly match spec_blocks.module_order")
        if [item.module for item in artifact.module_files] != artifact.module_order:
            errors.append("module_files[].module must exactly match module_order")
        for record in artifact.module_files:
            if record.status != "completed":
                errors.append(f"{record.module}: {record.status}: {record.error}")
                continue
            if "stage4" in partial_artifacts:
                stage4 = self._get_stage4_artifact(partial_artifacts)
                plan_record = next((item for item in stage4.module_plan_files if item.module == record.module), None)
                if plan_record:
                    expected = [item.id for item in self._read_module_plan(plan_record.plan_file).subtasks]
                    official = record.completed_subtasks == ["official_copy"] and is_define_only_module(record.module, partial_artifacts.get("stage2"))
                    if record.completed_subtasks != expected and not official:
                        errors.append(f"{record.module}: completed_subtasks must cover the complete plan in order")
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
        if artifact.timing_obligation_ids:
            errors.append("timing_obligation_ids compatibility field must be empty")
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
        if re.search(r"[\s:]", subtask.id):
            raise ValueError("Subtask marker identity must not contain whitespace or colon")
        sections = self._fragment_sections(existing_text)
        if subtask.id in sections:
            start, end, _ = sections[subtask.id]
            updated = existing_text[:start] + section + existing_text[end:]
        else:
            prefix = existing_text.rstrip()
            updated = f"{prefix}\n\n{section}" if prefix else section
        return updated.rstrip() + "\n"

    def _fragment_sections(self, text):
        sections = {}
        opened = None
        offset = 0
        outside = []
        for line in text.splitlines(keepends=True):
            begin = re.fullmatch(r"\s*// STAGE5_SUBTASK_BEGIN ([^\s:]+)(?::[^\n]*)?\s*", line)
            end = re.fullmatch(r"\s*// STAGE5_SUBTASK_END ([^\s:]+)\s*", line)
            if begin:
                unit = begin.group(1)
                if opened or unit in sections:
                    raise ValueError(f"Duplicate or nested Stage5 marker: {unit}")
                opened = (unit, offset, offset + len(line))
            elif end:
                if opened is None or opened[0] != end.group(1):
                    raise ValueError("Mismatched Stage5 marker")
                sections[opened[0]] = (opened[1], offset + len(line), text[opened[2]:offset].strip())
                opened = None
            elif opened is None:
                outside.append(line)
            offset += len(line)
        if opened:
            raise ValueError(f"Unclosed Stage5 marker: {opened[0]}")
        if "".join(outside).strip():
            raise ValueError("Unexpected code outside Stage5 subtask markers")
        return sections

    def _sanitize_marker_description(self, description: str) -> str:
        collapsed = " ".join(description.replace("\r\n", "\n").split())
        return collapsed[:120]

    def _ensure_global_defines_copied(self, task: PlannerTaskInput, partial_artifacts: Dict[str, Any]) -> None:
        repo_skeleton = partial_artifacts.get("stage2") or partial_artifacts.get("repo_skeleton")
        if repo_skeleton is None:
            return
        canonical_entries = copy_e203_canonical_define_files(
            top_module=str(_get(repo_skeleton, "top_module", "") or ""),
            oracle_root=self.oracle_root,
            workspace_root=self.workspace_root,
            output_root=self.output_root,
        )
        for entry in canonical_entries:
            self.logger.info(
                "[%s] Copied canonical E203 defines %s -> %s",
                self.stage_name,
                entry.get("source"),
                entry.get("workspace_path"),
            )
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

    def _build_stage5_global_defines_summary(
        self,
        relevant_texts: List[str],
        max_chars: int = 6000,
    ) -> str:
        return build_stage5_global_defines_summary(
            self.workspace_root,
            relevant_texts=relevant_texts,
            max_chars=max_chars,
        )

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
