from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, List, Set, Tuple

from ..prompts import stage2_decomposition, stage2_repo_skeleton
from ..schemas import (
    LockedTopModule,
    ModuleOrganizationArtifact,
    PlannerTaskInput,
    ResponsibilityLedgerOutput,
    ResponsibilityUnit,
    Stage2AdjudicationDecisionOutput,
    Stage2AdjudicationPass,
    Stage2CandidateEvaluation,
    Stage2DecompositionArtifact,
    Stage2DecompositionCandidate,
    Stage2PairwiseDecisionOutput,
    Stage2PairwisePass,
    Stage2PairwiseResult,
    Stage2PlanningInput,
    Stage2RankingDecisionOutput,
    Stage2RepoSkeletonArtifact,
    Stage2SelectionPass,
    Stage2SelectionResult,
    TopResolutionOutput,
)
from .base import BaseStageAgent, model_dump, validate_model
from ..utils.responsibility_planning import ledger_errors, ledger_issues, module_context


class Stage2Agent(BaseStageAgent):
    stage_name = "stage2_repo_skeleton"
    output_model = Stage2RepoSkeletonArtifact
    system_role = stage2_repo_skeleton.REPO_SKELETON_SYSTEM_ROLE
    memory_context_window = 16
    architecture_facts_max_chars = 20_000
    pairwise_threshold = 0.05
    plan_styles = ("conservative", "balanced", "modular")

    _ARCHITECTURE_FACT_CATEGORIES = {
        "module_identity",
        "resource_requirement",
        "data_dependency",
    }
    _EXPLICIT_RELATION_PREDICATES = {
        "instantiates",
        "instantiate",
        "contains",
        "includes",
        "is_composed_of",
        "has_child_module",
    }

    def run(
        self,
        task_input: Any,
        partial_artifacts: Dict[str, Any],
        decomposition_persist_callback: Callable[[Dict[str, Any]], None] | None = None,
    ) -> Stage2RepoSkeletonArtifact:
        self._last_quality_errors = []
        task = task_input if isinstance(task_input, PlannerTaskInput) else validate_model(PlannerTaskInput, task_input)
        stage2_input = self._get_stage2_input(partial_artifacts)
        if not stage2_input.source_specs:
            from ..module_organizer import build_stage2_planning_input_from_task
            stage2_input.source_specs = build_stage2_planning_input_from_task(task_input=task).source_specs
            partial_artifacts = {**partial_artifacts, "stage2_input": stage2_input}
        stage_context = self.context_provider.get_stage_context(self.stage_name, task, partial_artifacts)
        prompt_context = self._build_stage2_prompt_context(stage2_input)
        if stage_context:
            prompt_context["additional_stage_context"] = stage_context
        input_fingerprint = str(partial_artifacts.get("stage2_input_fingerprint") or "")
        existing = partial_artifacts.get("stage2_decomposition")
        decomposition = (
            existing
            if isinstance(existing, Stage2DecompositionArtifact)
            else validate_model(Stage2DecompositionArtifact, existing)
            if existing is not None
            else None
        )
        if decomposition is not None and (
            decomposition.task_id != task.task_id
            or decomposition.input_fingerprint != input_fingerprint
        ):
            decomposition = None

        if decomposition is None:
            top_evidence = self._collect_top_evidence(stage2_input)
            if len(top_evidence) == 1:
                top_module = next(iter(top_evidence))
                top_record = top_evidence[top_module]
                locked_top = LockedTopModule(
                    module=top_module,
                    resolution_mode="deterministic",
                    evidence_fact_ids=top_record["fact_ids"],
                    evidence_sections=top_record["sections"],
                    rationale="Unique grounded top-module identity collected from Stage1 evidence.",
                )
            else:
                prompt_context["top_module_hint"] = ""
                locked_top = self._resolve_top_with_llm(
                    task=task,
                    partial_artifacts=partial_artifacts,
                    prompt_context=prompt_context,
                    top_evidence=top_evidence,
                )
            decomposition = Stage2DecompositionArtifact(
                schema_version="stage2_decomposition_v2",
                task_id=task.task_id,
                input_fingerprint=input_fingerprint,
                status="top_locked",
                locked_top=locked_top,
                selection_trace=[
                    f"Locked top `{locked_top.module}` using {locked_top.resolution_mode}."
                ],
            )
            self._persist_decomposition(decomposition, decomposition_persist_callback)
        else:
            locked_top = decomposition.locked_top
            decomposition.selection_trace.append(f"Resumed Stage2 from `{decomposition.status}`.")

        if decomposition.responsibilities:
            responsibility_ledger = ResponsibilityLedgerOutput(
                responsibilities=list(decomposition.responsibilities),
                state_objects=list(decomposition.state_objects),
                global_clocking_notes=list(decomposition.global_clocking_notes),
                global_data_conventions=list(decomposition.global_data_conventions),
            )
        else:
            try:
                responsibility_ledger = self._extract_responsibilities(
                    task=task, partial_artifacts=partial_artifacts,
                    prompt_context=prompt_context, locked_top=locked_top,
                )
            except Exception as exc:
                decomposition.status = "failed"
                decomposition.failure_reasons = [str(exc)]
                self._persist_decomposition(decomposition, decomposition_persist_callback)
                raise
            decomposition.responsibilities = list(responsibility_ledger.responsibilities)
            decomposition.state_objects = list(responsibility_ledger.state_objects)
            decomposition.global_clocking_notes = list(responsibility_ledger.global_clocking_notes)
            decomposition.global_data_conventions = list(responsibility_ledger.global_data_conventions)
            decomposition.status = "responsibilities_extracted"
            decomposition.selection_trace.append(
                f"Extracted {len(decomposition.responsibilities)} shared responsibility units."
            )
            self._persist_decomposition(decomposition, decomposition_persist_callback)

        resumed_errors = ledger_errors(responsibility_ledger, stage2_input)
        if resumed_errors:
            decomposition.status = "failed"
            decomposition.failure_reasons = resumed_errors
            self._persist_decomposition(decomposition, decomposition_persist_callback)
            raise ValueError(f"Invalid responsibility ledger: {resumed_errors}")
        existing_candidates = {item.plan_style: item for item in decomposition.candidates}
        candidates: list[Stage2DecompositionCandidate] = []
        for plan_style in self.plan_styles:
            candidate = existing_candidates.get(plan_style)
            if candidate is not None:
                evaluation = self._evaluate_candidate(candidate=candidate, locked_top=locked_top,
                    responsibilities=list(responsibility_ledger.responsibilities), stage2_input=stage2_input)
                if evaluation.fatal_violations:
                    candidate = None  # Resume its repair node; keep other verified candidates.
            if candidate is None:
                candidate = self._generate_candidate(
                    task=task,
                    partial_artifacts=partial_artifacts,
                    prompt_context=prompt_context,
                    locked_top=locked_top,
                    responsibility_ledger=responsibility_ledger,
                    plan_style=plan_style,
                )
            candidates.append(candidate)
            decomposition.candidates = list(candidates)
            self._persist_decomposition(decomposition, decomposition_persist_callback)

        decomposition.status = "candidates_generated"
        decomposition.evaluations = [
            self._evaluate_candidate(
                candidate=candidate,
                locked_top=locked_top,
                responsibilities=decomposition.responsibilities,
                stage2_input=stage2_input,
            )
            for candidate in candidates
        ]
        try:
            selected, selection_result, trace, degraded = self._select_candidate(
                task=task,
                partial_artifacts=partial_artifacts,
                responsibilities=decomposition.responsibilities,
                candidates=candidates,
                evaluations=decomposition.evaluations,
            )
        except Exception as exc:
            decomposition.status = "failed"
            decomposition.failure_reasons = [str(exc)]
            self._persist_decomposition(decomposition, decomposition_persist_callback)
            raise
        decomposition.selected_candidate_id = selected.candidate_id
        decomposition.selected_boundary_contracts = list(selected.boundary_contracts)
        decomposition.selection_result = selection_result
        decomposition.pairwise_result = None
        decomposition.selection_trace.extend(trace)
        decomposition.status = "selected_with_degradation" if degraded else "selected"
        self._persist_decomposition(decomposition, decomposition_persist_callback)

        selected_evaluation = next(
            item for item in decomposition.evaluations if item.candidate_id == selected.candidate_id
        )
        repo_skeleton = self._candidate_to_repo_skeleton(
            task=task,
            stage2_input=stage2_input,
            locked_top=locked_top,
            responsibilities=decomposition.responsibilities,
            candidate=selected,
            evaluation=selected_evaluation,
            selection_result=selection_result,
            degraded=degraded,
        )
        repo_skeleton.input_fingerprint = input_fingerprint
        quality_errors = self.validate_quality(
            repo_skeleton,
            task,
            {**partial_artifacts, "stage2_input": stage2_input},
        )
        if quality_errors:
            decomposition.status = "failed"
            decomposition.failure_reasons = quality_errors
            self._persist_decomposition(decomposition, decomposition_persist_callback)
            raise ValueError(f"{self.stage_name} deterministic conversion failed quality checks: {quality_errors}")

        self._last_decomposition = decomposition
        self._log_stage_output(repo_skeleton)
        self.artifact_sink.record_stage_output(self.stage_name, repo_skeleton, task)
        return repo_skeleton

    @staticmethod
    def _persist_decomposition(
        artifact: Stage2DecompositionArtifact,
        callback: Callable[[Dict[str, Any]], None] | None,
    ) -> None:
        if callback is not None:
            callback(model_dump(artifact))

    @staticmethod
    def _to_compact_json(payload: Any) -> str:
        return json.dumps(
            BaseStageAgent._json_ready(payload),
            ensure_ascii=False,
            separators=(",", ":"),
        )

    def _invoke_stage_model(
        self,
        *,
        system_role: str,
        prompt: str,
        output_model: Any,
        task: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        quality_validator: Callable[[Any], List[str]],
        output_name: str,
        allow_best_effort: bool = False,
        prompt_view=None,
    ) -> Any:
        original_role = self.system_role
        original_output_name = getattr(self, "_retry_output_name", "JSON object")
        original_best_effort = self.allow_best_effort_quality_fallback
        self.system_role = system_role
        self._retry_output_name = output_name
        self.allow_best_effort_quality_fallback = allow_best_effort
        if prompt_view:
            self.logger.info("[%s] Prepared canonical input for %s (%d chars); API request uses projected context",
                             self.stage_name, output_name, len(prompt))
        else:
            self._log_stage_input(prompt=prompt, images=[], stage_context={"substage": output_name})
        try:
            artifact = self._invoke_with_repair(
                prompt,
                [],
                task,
                partial_artifacts,
                output_model=output_model,
                quality_validator=quality_validator,
                prompt_view=prompt_view,
            )
        finally:
            self.system_role = original_role
            self._retry_output_name = original_output_name
            self.allow_best_effort_quality_fallback = original_best_effort
        self._log_stage_output(artifact)
        return artifact

    def _collect_top_evidence(self, stage2_input: Stage2PlanningInput) -> Dict[str, Dict[str, List[str]]]:
        collected: dict[str, dict[str, list[str]]] = {}

        def add(module: str, *, fact_id: str = "", section: str = "") -> None:
            name = str(module or "").strip()
            if not name:
                return
            record = collected.setdefault(name, {"fact_ids": [], "sections": []})
            if fact_id and fact_id not in record["fact_ids"]:
                record["fact_ids"].append(fact_id)
            if section and section not in record["sections"]:
                record["sections"].append(section)

        for fact in stage2_input.fact_ledger.facts:
            if fact.category.strip().lower() != "module_identity":
                continue
            if fact.predicate.strip().lower() not in {"is_top_module", "top_module"}:
                continue
            module = str(fact.object.get("module") or fact.module or fact.subject or "").strip()
            sections = [item.section_path for item in fact.text_grounding if item.section_path]
            if sections:
                for section in sections:
                    add(module, fact_id=fact.fact_id, section=section)
            else:
                add(module, fact_id=fact.fact_id)

        legacy = stage2_input.legacy_contract_projection
        if legacy is not None:
            legacy_top = str(legacy.structure_contract.top_module or "").strip()
            structure_sections = [
                item.section_path
                for item in legacy.structure_contract.text_grounding
                if item.section_path
            ]
            if structure_sections:
                for section in structure_sections:
                    add(legacy_top, section=section)
            else:
                add(legacy_top)
            interface_candidates = [
                interface
                for interface in legacy.interface_contracts
                if interface.module and interface.ports
            ]
            if legacy_top:
                interface_candidates = [
                    interface for interface in interface_candidates if interface.module == legacy_top
                ]
            elif len(interface_candidates) != 1:
                interface_candidates = []
            for interface in interface_candidates:
                sections = [item.section_path for item in interface.text_grounding if item.section_path]
                if sections:
                    for section in sections:
                        add(interface.module, section=section)
                else:
                    add(interface.module)
        return collected

    def _resolve_top_with_llm(
        self,
        *,
        task: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        prompt_context: Dict[str, Any],
        top_evidence: Dict[str, Dict[str, List[str]]],
    ) -> LockedTopModule:
        prompt = stage2_decomposition.build_top_resolver_prompt(
            prompt_context_json=self.to_pretty_json(prompt_context),
            candidate_names_json=self.to_pretty_json(sorted(top_evidence)),
        )
        known_fact_ids = {
            str(item.get("fact_id") or "")
            for item in prompt_context.get("architecture_facts") or []
            if str(item.get("fact_id") or "")
        }
        source_markdown = str(
            (prompt_context.get("primary_source_spec") or {}).get("markdown") or ""
        )

        def validate(output: TopResolutionOutput) -> List[str]:
            errors: list[str] = []
            if output.module not in top_evidence and output.module not in source_markdown:
                errors.append("resolved module must appear in grounded candidate evidence or source markdown")
            unknown_ids = [item for item in output.evidence_fact_ids if item not in known_fact_ids]
            if unknown_ids:
                errors.append(f"top resolution cites unknown fact IDs: {unknown_ids}")
            if not output.evidence_sections:
                errors.append("top resolution must cite at least one source section")
            return errors

        output = self._invoke_stage_model(
            system_role=stage2_decomposition.TOP_RESOLVER_SYSTEM_ROLE,
            prompt=prompt,
            output_model=TopResolutionOutput,
            task=task,
            partial_artifacts=partial_artifacts,
            quality_validator=validate,
            output_name="top_resolution",
        )
        return LockedTopModule(
            module=output.module,
            resolution_mode="llm_resolved",
            evidence_fact_ids=list(output.evidence_fact_ids),
            evidence_sections=list(output.evidence_sections),
            rationale=output.rationale,
        )

    def _extract_responsibilities(
        self,
        *,
        task: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        prompt_context: Dict[str, Any],
        locked_top: LockedTopModule,
    ) -> ResponsibilityLedgerOutput:
        from ..utils.evidence import EvidenceRegistry, ResponsibilityLedgerDraft, draft_schema
        planning_input = self._get_stage2_input(partial_artifacts)
        registry = EvidenceRegistry(planning_input)
        registry.planning_input = planning_input
        root = getattr(self.llm_client, "output_root", None)
        if root is not None:
            registry.save(root)
        compact_context = {k: v for k, v in prompt_context.items() if k not in {
            "primary_source_spec", "responsibility_source_specs", "responsibility_facts", "architecture_facts"}}
        compact_context["facts"] = prompt_context.get("responsibility_facts", [])
        compact_context["architecture_fact_ids"] = [item["fact_id"] for item in prompt_context.get("architecture_facts", [])]
        compact_context["evidence_catalog"] = registry.prompt_catalog()
        prompt = stage2_decomposition.build_responsibility_prompt(
            prompt_context_json=self._to_compact_json(compact_context),
            locked_top_json=self.to_pretty_json(locked_top),
            evidence_ids=True,
        )
        output_rules = ("\nOUTPUT OVERRIDE: Return ResponsibilityLedgerDraft using source_evidence_ids for every RU and state. "
                   "Do not emit quotes, line numbers, hashes or source_refs; the program resolves IDs to exact original evidence.\n"
                   + json.dumps(draft_schema(), ensure_ascii=False, separators=(",", ":")))
        prompt += output_rules

        def responsibility_prompt_view(scope):
            from ..utils.local_repair import fingerprint
            # The complete initial input remains the checkpoint identity. A
            # request needs the complete original sources and current ledger,
            # not a second copy of Stage1's derived prose about those sources.
            repair_view = {k: v for k, v in compact_context.items() if k != "facts"}
            facts = compact_context["facts"]
            repair_view["fact_ids"] = [f["fact_id"] for f in facts if f.get("fact_id")]
            repair_view["canonical_fact_fingerprint"] = fingerprint(facts)
            repair_view["fact_context_note"] = (
                "Stage1 fact prose is derived from the complete evidence_catalog below. "
                "Preserve valid fact references; use the original evidence to repair only the requested entities. "
                "Select exact EV IDs from evidence_catalog.entries[].id; do not invent IDs. "
                "Remove repeated IDs within each source_evidence_ids list.")
            wire_prompt = stage2_decomposition.build_responsibility_prompt(
                prompt_context_json=self._to_compact_json(repair_view),
                locked_top_json=self.to_pretty_json(locked_top), evidence_ids=True)
            # The historical illustrative object omits mandatory state/access
            # and EV fields. The real JSON schema below is the sole output
            # shape; avoid both the duplicate example and its conflicting cues.
            rules, marker, example = wire_prompt.partition("Return exactly one JSON object with:")
            _, context_marker, source_context = example.partition("Stage2 prompt context:")
            if marker and context_marker:
                wire_prompt = (rules + "Return exactly one ResponsibilityLedgerDraft object matching the JSON schema below.\n\n"
                               + context_marker + source_context)
            return wire_prompt + output_rules
        self.logger.info("[%s] Prepared canonical responsibility input (%d chars); API request uses projected context",
                         self.stage_name, len(prompt))
        known_fact_ids = self._known_fact_ids(self._get_stage2_input(partial_artifacts))

        def additional_errors(output: ResponsibilityLedgerOutput) -> List[str]:
            errors: list[str] = []
            ids = [item.responsibility_id for item in output.responsibilities]
            duplicates = sorted({item for item in ids if ids.count(item) > 1})
            if duplicates:
                errors.append(f"responsibility IDs must be unique: {duplicates}")
            if not any(item.ownership_required for item in output.responsibilities):
                errors.append("at least one responsibility must require module ownership")
            id_set = set(ids)
            for responsibility in output.responsibilities:
                unknown_targets = [
                    item.target_responsibility_id
                    for item in responsibility.dependencies
                    if item.target_responsibility_id not in id_set
                    or item.target_responsibility_id == responsibility.responsibility_id
                ]
                if unknown_targets:
                    errors.append(
                        f"{responsibility.responsibility_id} has invalid dependency targets {unknown_targets}"
                    )
                unknown_facts = [
                    fact_id
                    for fact_id in responsibility.evidence_fact_ids
                    if fact_id not in known_fact_ids
                ]
                if unknown_facts:
                    errors.append(
                        f"{responsibility.responsibility_id} cites unknown fact IDs {unknown_facts}"
                    )
            return errors

        def validate(output: ResponsibilityLedgerOutput) -> List[str]:
            return ledger_errors(output, planning_input) + additional_errors(output)

        old_role, old_name = self.system_role, getattr(self, "_retry_output_name", "")
        self.system_role = stage2_decomposition.RESPONSIBILITY_SYSTEM_ROLE
        self._retry_output_name = "responsibility_ledger"
        try:
            from ..utils.planning_session import PlanningSession, ledger_scope
            from ..utils.local_repair import ArtifactIssue, model_issues
            def inspect(payload):
                draft, issues = model_issues(ResponsibilityLedgerDraft, payload)
                if issues:
                    return None, issues
                for group, key in (("responsibilities", "responsibility_id"), ("state_objects", "state_id")):
                    for item in getattr(draft, group):
                        try:
                            registry.expand(item.source_evidence_ids)
                        except ValueError as exc:
                            issues.append(ArtifactIssue(f"{group}[{getattr(item, key)}]", "invalid_evidence", str(exc),
                                category="source", unit_id=getattr(item, key),
                                expected={"allowed_evidence_ids_from": "evidence_catalog.entries[].id"}))
                if issues:
                    return None, issues
                resolved = registry.resolve(draft)
                issues = ledger_issues(resolved, planning_input)
                issues.extend(ArtifactIssue("ledger", "invalid_ledger", message, category="hardware")
                              for message in additional_errors(resolved))
                for issue in issues:
                    issue.stage, issue.module = self.stage_name, task.task_id
                return resolved, issues
            if getattr(self.llm_client, "executor", None) is None:
                # An injected stand-alone model double has no durable case root.
                # Runner production always installs the bounded executor.
                return self._invoke_stage_model(system_role=self.system_role, prompt=prompt,
                    output_model=ResponsibilityLedgerOutput, task=task, partial_artifacts=partial_artifacts,
                    quality_validator=validate, output_name="responsibility_ledger")
            result = PlanningSession(self).execute(module=task.task_id, prompt=prompt, context={},
                validate=inspect, operation="responsibility_ledger", scope_builder=ledger_scope,
                prompt_view=responsibility_prompt_view)
            if result.status != "validated":
                from .base import StageGenerationError
                raise StageGenerationError("Stage2 responsibility ledger needs_repair: " + "; ".join(i.message for i in result.issues or []))
            registry.save(root)
            return result.artifact
        finally:
            self.system_role, self._retry_output_name = old_role, old_name

    def _generate_candidate(
        self,
        *,
        task: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        prompt_context: Dict[str, Any],
        locked_top: LockedTopModule,
        responsibility_ledger: ResponsibilityLedgerOutput,
        plan_style: str,
    ) -> Stage2DecompositionCandidate:
        candidate_prompt_context = self._build_candidate_prompt_context(prompt_context)
        prompt_context_json = self._to_compact_json(candidate_prompt_context)
        locked_top_json = self._to_compact_json(locked_top)
        from ..utils.evidence import deduplicate_evidence, EvidenceRegistry
        ledger_view = deduplicate_evidence(model_dump(responsibility_ledger))
        responsibility_ledger_json = self._to_compact_json(ledger_view)
        prompt = stage2_decomposition.build_candidate_prompt(
            plan_style=plan_style,
            prompt_context_json=prompt_context_json,
            locked_top_json=locked_top_json,
            responsibility_ledger_json=responsibility_ledger_json,
        )
        # Provenance hashes and repeated absolute paths are checked locally.
        # Architecture reasoning keeps every cited original quote, line range
        # and EV identity through the indexed catalog instead of full sidecars.
        registry = EvidenceRegistry(self._get_stage2_input(partial_artifacts))
        registry.register_tree(responsibility_ledger)
        compact_ledger = {key: value for key, value in ledger_view.items() if key != "evidence"}
        compact_ledger["evidence_catalog"] = registry.prompt_catalog(ledger_view.get("evidence", {}).keys())
        wire_prompt = stage2_decomposition.build_candidate_prompt(
            plan_style=plan_style, prompt_context_json=prompt_context_json,
            locked_top_json=locked_top_json, responsibility_ledger_json=self._to_compact_json(compact_ledger))
        fixed_chars = max(
            0,
            len(prompt)
            - len(prompt_context_json)
            - len(locked_top_json)
            - len(responsibility_ledger_json),
        )
        self.logger.info(
            "[%s] Candidate prompt chars (%s): responsibilities=%d grounding=%d "
            "locked_top=%d fixed=%d total=%d",
            self.stage_name,
            plan_style,
            len(responsibility_ledger_json),
            len(prompt_context_json),
            len(locked_top_json),
            fixed_chars,
            len(prompt),
        )

        def validate(output: Stage2DecompositionCandidate) -> List[str]:
            errors: list[str] = []
            expected_id = f"stage2_{plan_style}"
            if output.candidate_id != expected_id:
                errors.append(f"candidate_id must be {expected_id}")
            if output.plan_style != plan_style:
                errors.append(f"plan_style must be {plan_style}")
            if not errors:
                evaluation = self._evaluate_candidate(
                    candidate=output,
                    locked_top=locked_top,
                    responsibilities=list(responsibility_ledger.responsibilities),
                    stage2_input=self._get_stage2_input(partial_artifacts),
                )
                errors.extend(evaluation.fatal_violations)
            return errors

        return self._invoke_stage_model(
            system_role=stage2_decomposition.CANDIDATE_SYSTEM_ROLE,
            prompt=prompt,
            output_model=Stage2DecompositionCandidate,
            task=task,
            partial_artifacts=partial_artifacts,
            quality_validator=validate,
            output_name=f"{plan_style}_candidate",
            allow_best_effort=True,
            prompt_view=lambda _scope: wire_prompt,
        )

    def _evaluate_candidate(
        self,
        *,
        candidate: Stage2DecompositionCandidate,
        locked_top: LockedTopModule,
        responsibilities: List[ResponsibilityUnit],
        stage2_input: Stage2PlanningInput,
    ) -> Stage2CandidateEvaluation:
        fatal: list[str] = []
        hard: list[str] = []
        warnings: list[str] = []
        module_names = [item.module for item in candidate.modules]
        module_set = set(module_names)
        ru_by_id = {item.responsibility_id: item for item in responsibilities}
        owners: dict[str, list[str]] = {item: [] for item in ru_by_id}
        for module in candidate.modules:
            for responsibility_id in module.responsibility_ids:
                if responsibility_id not in ru_by_id:
                    fatal.append(
                        f"module `{module.module}` references unknown responsibility `{responsibility_id}`"
                    )
                    continue
                if not ru_by_id[responsibility_id].ownership_required:
                    fatal.append(f"module `{module.module}` must not own constraint-only responsibility `{responsibility_id}`")
                owners[responsibility_id].append(module.module)

        if candidate.top_module != locked_top.module:
            fatal.append(
                f"candidate top `{candidate.top_module}` differs from locked top `{locked_top.module}`"
            )
        if locked_top.module not in module_set:
            fatal.append(f"locked top `{locked_top.module}` is missing from candidate modules")
        duplicates = sorted({name for name in module_names if module_names.count(name) > 1})
        if duplicates:
            fatal.append(f"duplicate module names: {duplicates}")

        for responsibility in responsibilities:
            owner_count = len(owners.get(responsibility.responsibility_id, []))
            if responsibility.ownership_required and owner_count != 1:
                fatal.append(
                    f"required responsibility `{responsibility.responsibility_id}` must have exactly one owner; "
                    f"found {owner_count}"
                )
            elif owner_count > 1:
                fatal.append(
                    f"responsibility `{responsibility.responsibility_id}` has multiple owners "
                    f"{owners[responsibility.responsibility_id]}"
                )

        explicit_modules = self._explicit_module_names(stage2_input, locked_top.module)
        explicit_modules.update(
            item.explicit_module_hint
            for item in responsibilities
            if item.explicit_module_hint
        )
        missing_explicit_modules = sorted(explicit_modules - module_set)
        if missing_explicit_modules:
            fatal.append(f"missing explicit modules: {missing_explicit_modules}")

        edge_pairs: list[tuple[str, str]] = []
        for edge in candidate.hierarchy:
            if edge.parent not in module_set or edge.child not in module_set or edge.parent == edge.child:
                fatal.append(f"invalid hierarchy edge `{edge.parent}->{edge.child}`")
            edge_pairs.append((edge.parent, edge.child))
        if self._has_cycle(module_set, edge_pairs):
            fatal.append("candidate hierarchy contains a cycle")
        missing_explicit_edges = sorted(self._explicit_edges(stage2_input) - set(edge_pairs))
        if missing_explicit_edges:
            fatal.append(f"missing explicit hierarchy edges: {missing_explicit_edges}")

        boundary_by_ru_pair: dict[tuple[str, str], list[Any]] = {}
        for boundary in candidate.boundary_contracts:
            if (
                boundary.producer_module not in module_set
                or boundary.consumer_module not in module_set
                or boundary.producer_module == boundary.consumer_module
            ):
                fatal.append(f"boundary `{boundary.boundary_id}` has invalid module endpoints")
            for producer_id in boundary.producer_responsibility_ids:
                for consumer_id in boundary.consumer_responsibility_ids:
                    boundary_by_ru_pair.setdefault((producer_id, consumer_id), []).append(boundary)
            unknown_boundary_rus = [
                item
                for item in [
                    *boundary.producer_responsibility_ids,
                    *boundary.consumer_responsibility_ids,
                ]
                if item not in ru_by_id
            ]
            if unknown_boundary_rus:
                fatal.append(
                    f"boundary `{boundary.boundary_id}` references unknown responsibilities "
                    f"{sorted(set(unknown_boundary_rus))}"
                )

        for boundary in candidate.boundary_contracts:
            for ru_id in boundary.producer_responsibility_ids:
                if owners.get(ru_id) != [boundary.producer_module]:
                    fatal.append(f"boundary `{boundary.boundary_id}` producer responsibility `{ru_id}` has inconsistent ownership")
            for ru_id in boundary.consumer_responsibility_ids:
                if owners.get(ru_id) != [boundary.consumer_module]:
                    fatal.append(f"boundary `{boundary.boundary_id}` consumer responsibility `{ru_id}` has inconsistent ownership")
        boundary_ids = [b.boundary_id for b in candidate.boundary_contracts]
        if len(boundary_ids) != len(set(boundary_ids)):
            fatal.append("duplicate boundary IDs")

        cross_dependencies: list[tuple[ResponsibilityUnit, Any, str, str]] = []
        cut_weight = 0
        total_coupling_weight = 0
        strong_coupling_cut_count = 0
        strength_weights = {"strong": 3, "medium": 2, "weak": 1}
        for responsibility in responsibilities:
            source_owners = owners.get(responsibility.responsibility_id, [])
            for dependency in responsibility.dependencies:
                weight = strength_weights[dependency.coupling_strength]
                total_coupling_weight += weight
                target_owners = owners.get(dependency.target_responsibility_id, [])
                if len(source_owners) != 1 or len(target_owners) != 1:
                    continue
                source_module, target_module = source_owners[0], target_owners[0]
                if source_module == target_module:
                    continue
                cut_weight += weight
                cross_dependencies.append(
                    (responsibility, dependency, source_module, target_module)
                )
                matches = boundary_by_ru_pair.get(
                    (responsibility.responsibility_id, dependency.target_responsibility_id),
                    [],
                )
                matches = [
                    item
                    for item in matches
                    if item.producer_module == source_module and item.consumer_module == target_module
                ]
                if not matches and dependency.dependency_kind in {"data", "control"}:
                    fatal.append(
                        "missing boundary contract for cross-module dependency "
                        f"`{responsibility.responsibility_id}->{dependency.target_responsibility_id}` "
                        f"({source_module}->{target_module})"
                    )
                if dependency.dependency_kind in {"data", "control"} and matches:
                    transferred = {obj for item in matches for obj in item.transferred_objects}
                    if not set(dependency.transferred_objects) <= transferred:
                        fatal.append(f"boundary contract omits transferred objects for `{responsibility.responsibility_id}->{dependency.target_responsibility_id}`")
                if dependency.partition_constraint == "must_colocate":
                    fatal.append(f"must_colocate dependency `{dependency.dependency_id}` is split across modules")
                if dependency.coupling_strength == "strong":
                    strong_coupling_cut_count += 1
                    hard.append(
                        "strongly coupled responsibilities are split across modules: "
                        f"`{responsibility.responsibility_id}->{dependency.target_responsibility_id}`"
                    )

        for boundary in candidate.boundary_contracts:
            incomplete = []
            for field_name in ("protocol", "timing_class", "clock_domain", "reset_behavior"):
                value = str(getattr(boundary, field_name) or "").strip().lower()
                if not value:
                    incomplete.append(field_name)
            if boundary.width_status == "unresolved":
                incomplete.append("width_status")
            if boundary.width_status in {"explicit", "derived"} and not boundary.width_evidence:
                incomplete.append("width_evidence")
            if incomplete:
                hard.append(
                    f"boundary `{boundary.boundary_id}` has incomplete logical contract fields: {incomplete}"
                )
            grounded_objects = self._boundary_objects_are_grounded(boundary, ru_by_id)
            if not grounded_objects:
                hard.append(
                    f"boundary `{boundary.boundary_id}` transferred objects lack responsibility/spec grounding"
                )

        explicit_hint_by_ru = {
            item.responsibility_id: item.explicit_module_hint
            for item in responsibilities
            if item.explicit_module_hint
        }
        convenience_modules = 0
        for module in candidate.modules:
            module_rus = [ru_by_id[item] for item in module.responsibility_ids if item in ru_by_id]
            has_support = bool(module.supporting_fact_ids or module.supporting_sections)
            if module.module != locked_top.module and module.source_kind != "explicit" and not has_support:
                hard.append(f"inferred module `{module.module}` lacks fact or spec-section evidence")
            hinted = any(
                explicit_hint_by_ru.get(item.responsibility_id) == module.module
                for item in module_rus
            )
            convenience = (
                module.module != locked_top.module
                and len(module_rus) == 1
                and not module_rus[0].owned_state
                and not module_rus[0].reusable
                and not hinted
            )
            if convenience:
                convenience_modules += 1
                hard.append(
                    f"module `{module.module}` is a single-responsibility convenience boundary"
                )

        high_glue_limit = max(2, 2 * max(1, len(module_set) - 1))
        if len(candidate.boundary_contracts) > high_glue_limit:
            hard.append(
                f"candidate has high glue cost: {len(candidate.boundary_contracts)} boundaries "
                f"for {len(module_set)} modules"
            )

        required = [item for item in responsibilities if item.ownership_required]
        dependency_count = sum(len(item.dependencies) for item in responsibilities)
        stateful_responsibility_count = sum(bool(item.owned_state) for item in responsibilities)
        return Stage2CandidateEvaluation(
            candidate_id=candidate.candidate_id,
            plan_style=candidate.plan_style,
            fatal_violations=self._ordered_nonempty(fatal),
            hard_violations=self._ordered_nonempty(hard),
            warnings=self._ordered_nonempty(warnings),
            metrics={
                "module_count": len(candidate.modules),
                "required_responsibility_count": len(required),
                "stateful_responsibility_count": stateful_responsibility_count,
                "dependency_count": dependency_count,
                "cross_module_dependency_count": len(cross_dependencies),
                "boundary_contract_count": len(candidate.boundary_contracts),
                "strong_coupling_cut_count": strong_coupling_cut_count,
                "coupling_cut_weight": cut_weight,
                "total_coupling_weight": total_coupling_weight,
                "convenience_module_count": convenience_modules,
            },
        )

    def _explicit_module_names(self, stage2_input: Stage2PlanningInput, top_module: str) -> Set[str]:
        modules = {top_module}
        for parent, child in self._explicit_edges(stage2_input):
            modules.update({parent, child})
        for fact in stage2_input.fact_ledger.facts:
            if fact.category.strip().lower() != "module_identity":
                continue
            values = fact.object.get("modules") or []
            if isinstance(values, str):
                values = [values]
            values = [fact.object.get("module"), *values]
            if fact.predicate.strip().lower() in {
                "is_module", "defines_module", "is_top_module", "top_module", "is_explicit_generation_target",
            }:
                values.append(fact.object.get("target_module") or fact.object.get("name") or fact.subject or fact.module)
            modules.update(str(item).strip() for item in values if str(item or "").strip())
        legacy = stage2_input.legacy_contract_projection
        # Native Stage1 projections include module-valued *scopes* of facts.
        # A filename fallback attached to a definition of a concept is not an
        # explicit RTL module declaration. Use actual identity/relation facts
        # above; only genuine legacy inputs need the projected module list.
        if legacy is not None and not stage2_input.fact_ledger.facts:
            modules.update(str(item).strip() for item in legacy.structure_contract.modules if str(item).strip())
        return {item for item in modules if item}

    @staticmethod
    def _boundary_objects_are_grounded(boundary: Any, ru_by_id: Dict[str, ResponsibilityUnit]) -> bool:
        grounded: set[str] = set()
        ru_ids = [*boundary.producer_responsibility_ids, *boundary.consumer_responsibility_ids]
        for ru_id in ru_ids:
            responsibility = ru_by_id.get(ru_id)
            if responsibility is None:
                continue
            grounded.update(responsibility.inputs)
            grounded.update(responsibility.outputs)
            grounded.update(responsibility.owned_state)
            for dependency in responsibility.dependencies:
                grounded.update(dependency.transferred_objects)
        return bool(boundary.transferred_objects) and all(
            item in grounded for item in boundary.transferred_objects
        )

    def _select_candidate(
        self,
        *,
        task: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        responsibilities: List[ResponsibilityUnit],
        candidates: List[Stage2DecompositionCandidate],
        evaluations: List[Stage2CandidateEvaluation],
    ) -> tuple[
        Stage2DecompositionCandidate,
        Stage2SelectionResult,
        List[str],
        bool,
    ]:
        candidate_by_id = {item.candidate_id: item for item in candidates}
        evaluation_by_id = {item.candidate_id: item for item in evaluations}
        fatal_free = [item for item in candidates if not evaluation_by_id[item.candidate_id].fatal_violations]
        if not fatal_free:
            reasons = {
                item.candidate_id: item.fatal_violations
                for item in evaluations
            }
            raise ValueError(f"all Stage2 decomposition candidates have fatal violations: {reasons}")

        trace = [
            f"{len(fatal_free)} candidate(s) passed deterministic fatal validation; "
            "risk findings were retained as advisory LLM evidence."
        ]
        judge_candidates, duplicate_notes = self._distinct_selection_candidates(fatal_free)
        trace.extend(duplicate_notes)
        eligible_ids = [item.candidate_id for item in judge_candidates]
        selection_result = Stage2SelectionResult(eligible_candidate_ids=eligible_ids)

        if len(judge_candidates) == 1:
            selected_id = judge_candidates[0].candidate_id
            reason = (
                "Only one distinct fatal-free architecture remained; selected without LLM ranking."
            )
            selection_result.final_winner_candidate_id = selected_id
            selection_result.final_reason = reason
            trace.append(f"{reason} Winner `{selected_id}`.")
        else:
            first_order = list(eligible_ids)
            second_order = list(reversed(first_order))
            first_pass = self._run_selection_pass_safe(
                task=task,
                partial_artifacts=partial_artifacts,
                responsibilities=responsibilities,
                candidates=judge_candidates,
                evaluations=evaluations,
                presentation_order=first_order,
                output_name="architecture_ranking_first_pass",
            )
            second_pass = self._run_selection_pass_safe(
                task=task,
                partial_artifacts=partial_artifacts,
                responsibilities=responsibilities,
                candidates=judge_candidates,
                evaluations=evaluations,
                presentation_order=second_order,
                output_name="architecture_ranking_second_pass",
            )
            selection_result.first_pass = first_pass
            selection_result.second_pass = second_pass
            successful = [item for item in (first_pass, second_pass) if not item.error]

            if len(successful) == 2 and first_pass.winner_candidate_id == second_pass.winner_candidate_id:
                selected_id = first_pass.winner_candidate_id
                reason = "Independent order-reversed LLM rankings agreed on the winner."
            elif len(successful) == 2:
                disputed_ids = [first_pass.winner_candidate_id, second_pass.winner_candidate_id]
                adjudication = self._run_adjudication_safe(
                    task=task,
                    partial_artifacts=partial_artifacts,
                    responsibilities=responsibilities,
                    candidates=[candidate_by_id[item] for item in disputed_ids],
                    evaluations=evaluations,
                    first_pass=first_pass,
                    second_pass=second_pass,
                )
                selection_result.adjudication = adjudication
                if not adjudication.error:
                    selected_id = adjudication.winner_candidate_id
                    reason = "Third LLM adjudication resolved conflicting independent rankings."
                else:
                    selected_id = self._aggregate_disputed_rankings(
                        disputed_ids,
                        first_pass,
                        second_pass,
                        candidate_by_id,
                    )
                    selection_result.fallback_used = True
                    selection_result.fallback_reason = (
                        "Adjudication failed after retries; selected the disputed candidate with "
                        "the lower aggregate rank, using balanced/modular/conservative only for an exact tie. "
                        f"Error: {adjudication.error}"
                    )
                    reason = selection_result.fallback_reason
            elif len(successful) == 1:
                selected_id = successful[0].winner_candidate_id
                selection_result.fallback_used = True
                failed_pass = first_pass if first_pass.error else second_pass
                selection_result.fallback_reason = (
                    "One independent ranking failed after retries; used the successful ranking. "
                    f"Error: {failed_pass.error}"
                )
                reason = selection_result.fallback_reason
            else:
                selected_id = self._style_fallback_candidate_id(judge_candidates)
                selection_result.fallback_used = True
                selection_result.fallback_reason = (
                    "Both independent rankings failed after retries; selected by operational "
                    "fallback preference balanced, then modular, then conservative. "
                    f"Errors: first={first_pass.error}; second={second_pass.error}"
                )
                reason = selection_result.fallback_reason

            selection_result.final_winner_candidate_id = selected_id
            selection_result.final_reason = reason
            trace.append(f"{reason} Winner `{selected_id}`.")

        selected_evaluation = evaluation_by_id[selection_result.final_winner_candidate_id]
        degraded = bool(selected_evaluation.hard_violations or selection_result.fallback_used)
        return (
            candidate_by_id[selection_result.final_winner_candidate_id],
            selection_result,
            trace,
            degraded,
        )

    def _distinct_selection_candidates(
        self,
        candidates: List[Stage2DecompositionCandidate],
    ) -> tuple[List[Stage2DecompositionCandidate], List[str]]:
        preference = {"balanced": 0, "modular": 1, "conservative": 2}
        grouped: dict[tuple[Any, ...], list[Stage2DecompositionCandidate]] = {}
        for candidate in candidates:
            grouped.setdefault(self._candidate_signature(candidate), []).append(candidate)
        representatives: list[Stage2DecompositionCandidate] = []
        notes: list[str] = []
        for group in grouped.values():
            representative = min(
                group,
                key=lambda item: (preference.get(item.plan_style, 99), item.candidate_id),
            )
            representatives.append(representative)
            if len(group) > 1:
                notes.append(
                    "Structurally identical candidates "
                    f"{[item.candidate_id for item in group]} were represented by "
                    f"`{representative.candidate_id}`."
                )
        display_order = {style: index for index, style in enumerate(self.plan_styles)}
        representatives.sort(
            key=lambda item: (display_order.get(item.plan_style, 99), item.candidate_id)
        )
        return representatives, notes

    def _run_selection_pass_safe(
        self,
        *,
        task: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        responsibilities: List[ResponsibilityUnit],
        candidates: List[Stage2DecompositionCandidate],
        evaluations: List[Stage2CandidateEvaluation],
        presentation_order: List[str],
        output_name: str,
    ) -> Stage2SelectionPass:
        candidate_by_id = {item.candidate_id: item for item in candidates}
        evaluation_by_id = {item.candidate_id: item for item in evaluations}
        ordered_candidates = [candidate_by_id[item] for item in presentation_order]
        prompt = stage2_decomposition.build_selection_prompt(
            responsibility_summary_json=self._to_compact_json(
                self._selection_responsibility_view(responsibilities)
            ),
            candidate_views_json=self._to_compact_json(
                [
                    self._selection_candidate_view(item, evaluation_by_id[item.candidate_id])
                    for item in ordered_candidates
                ]
            ),
            presentation_order_json=self._to_compact_json(presentation_order),
        )
        allowed = set(presentation_order)

        def validate(output: Stage2RankingDecisionOutput) -> List[str]:
            errors: list[str] = []
            if len(output.ranked_candidate_ids) != len(presentation_order) or set(
                output.ranked_candidate_ids
            ) != allowed:
                errors.append("ranking must contain every eligible candidate ID exactly once")
            if output.ranked_candidate_ids and output.winner_candidate_id != output.ranked_candidate_ids[0]:
                errors.append("winner_candidate_id must equal the first ranked candidate")
            if set(output.candidate_assessments) != allowed:
                errors.append("candidate_assessments must cover every eligible candidate ID exactly once")
            return errors

        try:
            output = self._invoke_stage_model(
                system_role=stage2_decomposition.SELECTION_SYSTEM_ROLE,
                prompt=prompt,
                output_model=Stage2RankingDecisionOutput,
                task=task,
                partial_artifacts=partial_artifacts,
                quality_validator=validate,
                output_name=output_name,
            )
            return Stage2SelectionPass(
                presentation_order=presentation_order,
                ranked_candidate_ids=list(output.ranked_candidate_ids),
                winner_candidate_id=output.winner_candidate_id,
                candidate_assessments=dict(output.candidate_assessments),
                rationale=list(output.rationale),
            )
        except Exception as exc:
            from ..utils.execution import fatal_request_error
            if fatal_request_error(exc):
                raise
            self.logger.warning("[%s] %s failed: %s", self.stage_name, output_name, exc)
            return Stage2SelectionPass(
                presentation_order=presentation_order,
                error=str(exc),
            )

    def _run_adjudication_safe(
        self,
        *,
        task: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        responsibilities: List[ResponsibilityUnit],
        candidates: List[Stage2DecompositionCandidate],
        evaluations: List[Stage2CandidateEvaluation],
        first_pass: Stage2SelectionPass,
        second_pass: Stage2SelectionPass,
    ) -> Stage2AdjudicationPass:
        candidate_ids = [item.candidate_id for item in candidates]
        evaluation_by_id = {item.candidate_id: item for item in evaluations}
        prompt = stage2_decomposition.build_adjudication_prompt(
            responsibility_summary_json=self._to_compact_json(
                self._selection_responsibility_view(responsibilities)
            ),
            candidate_views_json=self._to_compact_json(
                [
                    self._selection_candidate_view(item, evaluation_by_id[item.candidate_id])
                    for item in candidates
                ]
            ),
            prior_passes_json=self._to_compact_json([first_pass, second_pass]),
            candidate_ids_json=self._to_compact_json(candidate_ids),
        )
        allowed = set(candidate_ids)

        def validate(output: Stage2AdjudicationDecisionOutput) -> List[str]:
            if output.winner_candidate_id not in allowed:
                return [f"adjudication winner must be one of {sorted(allowed)}"]
            return []

        try:
            output = self._invoke_stage_model(
                system_role=stage2_decomposition.ADJUDICATION_SYSTEM_ROLE,
                prompt=prompt,
                output_model=Stage2AdjudicationDecisionOutput,
                task=task,
                partial_artifacts=partial_artifacts,
                quality_validator=validate,
                output_name="architecture_ranking_adjudication",
            )
            return Stage2AdjudicationPass(
                candidate_ids=candidate_ids,
                winner_candidate_id=output.winner_candidate_id,
                rationale=list(output.rationale),
            )
        except Exception as exc:
            from ..utils.execution import fatal_request_error
            if fatal_request_error(exc):
                raise
            self.logger.warning("[%s] architecture adjudication failed: %s", self.stage_name, exc)
            return Stage2AdjudicationPass(candidate_ids=candidate_ids, error=str(exc))

    @staticmethod
    def _selection_responsibility_view(
        responsibilities: List[ResponsibilityUnit],
    ) -> List[Dict[str, Any]]:
        return [
            {
                "responsibility_id": item.responsibility_id,
                "description": item.description,
                "ownership_required": item.ownership_required,
                "applies_to_responsibility_ids": list(item.applies_to_responsibility_ids),
                "owned_state": list(item.owned_state),
                "state_accesses": [access.model_dump() for access in item.state_accesses],
                "clock_domain": item.clock_domain,
                "reset_behavior": item.reset_behavior,
                "protocol": item.protocol,
                "timing_class": item.timing_class,
                "dependencies": [
                    {
                        "target_responsibility_id": dependency.target_responsibility_id,
                        "dependency_id": dependency.dependency_id,
                        "dependency_kind": dependency.dependency_kind,
                        "partition_constraint": dependency.partition_constraint,
                        "timing_relation": dependency.timing_relation,
                        "coupling_strength": dependency.coupling_strength,
                        "transferred_objects": list(dependency.transferred_objects),
                    }
                    for dependency in item.dependencies
                ],
                "explicit_module_hint": item.explicit_module_hint,
                "reusable": item.reusable,
                "iterative": item.iterative,
            }
            for item in responsibilities
        ]

    @staticmethod
    def _selection_candidate_view(
        candidate: Stage2DecompositionCandidate,
        evaluation: Stage2CandidateEvaluation,
    ) -> Dict[str, Any]:
        return {
            "candidate_id": candidate.candidate_id,
            "plan_style": candidate.plan_style,
            "summary": candidate.summary,
            "modules": [
                {
                    "module": item.module,
                    "role": item.role,
                    "responsibility_ids": list(item.responsibility_ids),
                    "source_kind": item.source_kind,
                    "rationale": item.rationale,
                }
                for item in candidate.modules
            ],
            "hierarchy": [
                {
                    "parent": item.parent,
                    "child": item.child,
                    "source_kind": item.source_kind,
                    "rationale": item.rationale,
                }
                for item in candidate.hierarchy
            ],
            "boundary_contracts": [
                {
                    "producer_module": item.producer_module,
                    "consumer_module": item.consumer_module,
                    "producer_responsibility_ids": list(item.producer_responsibility_ids),
                    "consumer_responsibility_ids": list(item.consumer_responsibility_ids),
                    "transferred_objects": list(item.transferred_objects),
                    "protocol": item.protocol,
                    "timing_class": item.timing_class,
                    "width_status": item.width_status,
                }
                for item in candidate.boundary_contracts
            ],
            "open_issues": list(candidate.open_issues),
            "risk_findings": list(evaluation.hard_violations),
            "warnings": list(evaluation.warnings),
            "descriptive_metrics": dict(evaluation.metrics),
        }

    def _aggregate_disputed_rankings(
        self,
        disputed_ids: List[str],
        first_pass: Stage2SelectionPass,
        second_pass: Stage2SelectionPass,
        candidate_by_id: Dict[str, Stage2DecompositionCandidate],
    ) -> str:
        rank_sums = {
            candidate_id: first_pass.ranked_candidate_ids.index(candidate_id)
            + second_pass.ranked_candidate_ids.index(candidate_id)
            for candidate_id in disputed_ids
        }
        minimum = min(rank_sums.values())
        tied = [candidate_by_id[item] for item, score in rank_sums.items() if score == minimum]
        return self._style_fallback_candidate_id(tied)

    @staticmethod
    def _style_fallback_candidate_id(
        candidates: List[Stage2DecompositionCandidate],
    ) -> str:
        preference = {"balanced": 0, "modular": 1, "conservative": 2}
        return min(
            candidates,
            key=lambda item: (preference.get(item.plan_style, 99), item.candidate_id),
        ).candidate_id

    @staticmethod
    def _candidate_signature(candidate: Stage2DecompositionCandidate) -> tuple[Any, ...]:
        assignments = tuple(
            sorted(
                (module.module, tuple(sorted(module.responsibility_ids)))
                for module in candidate.modules
            )
        )
        hierarchy = tuple(sorted((edge.parent, edge.child) for edge in candidate.hierarchy))
        boundaries = tuple(
            sorted(
                (
                    item.producer_module,
                    item.consumer_module,
                    tuple(sorted(item.producer_responsibility_ids)),
                    tuple(sorted(item.consumer_responsibility_ids)),
                    tuple(sorted(item.transferred_objects)),
                )
                for item in candidate.boundary_contracts
            )
        )
        return assignments, hierarchy, boundaries

    def _run_pairwise_tiebreak(
        self,
        *,
        task: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        responsibilities: List[ResponsibilityUnit],
        first: Stage2DecompositionCandidate,
        second: Stage2DecompositionCandidate,
        evaluations: List[Stage2CandidateEvaluation],
        score_delta: float,
    ) -> Stage2PairwiseResult:
        allowed_ids = {first.candidate_id, second.candidate_id}

        def run_pass(
            candidate_a: Stage2DecompositionCandidate,
            candidate_b: Stage2DecompositionCandidate,
            label: str,
        ) -> Stage2PairwisePass:
            prompt = stage2_decomposition.build_pairwise_prompt(
                responsibility_ledger_json=self.to_pretty_json(responsibilities),
                candidate_a_json=self.to_pretty_json(candidate_a),
                candidate_b_json=self.to_pretty_json(candidate_b),
                evaluations_json=self.to_pretty_json(evaluations),
            )

            def validate(output: Stage2PairwiseDecisionOutput) -> List[str]:
                if output.winner_candidate_id not in allowed_ids:
                    return [f"winner must be one of {sorted(allowed_ids)}"]
                return []

            output = self._invoke_stage_model(
                system_role=stage2_decomposition.PAIRWISE_SYSTEM_ROLE,
                prompt=prompt,
                output_model=Stage2PairwiseDecisionOutput,
                task=task,
                partial_artifacts=partial_artifacts,
                quality_validator=validate,
                output_name=label,
            )
            return Stage2PairwisePass(
                presentation_order=[candidate_a.candidate_id, candidate_b.candidate_id],
                winner_candidate_id=output.winner_candidate_id,
                rationale=list(output.rationale),
            )

        first_pass = run_pass(first, second, "pairwise_first_pass")
        second_pass = run_pass(second, first, "pairwise_second_pass")
        stable = first_pass.winner_candidate_id == second_pass.winner_candidate_id
        return Stage2PairwiseResult(
            candidate_a_id=first.candidate_id,
            candidate_b_id=second.candidate_id,
            trigger_threshold=self.pairwise_threshold,
            score_delta=score_delta,
            first_pass=first_pass,
            second_pass=second_pass,
            applied=stable,
            final_winner_candidate_id=first_pass.winner_candidate_id if stable else "",
            unstable_judgment=not stable,
        )

    def _candidate_to_repo_skeleton(
        self,
        *,
        task: PlannerTaskInput,
        stage2_input: Stage2PlanningInput,
        locked_top: LockedTopModule,
        responsibilities: List[ResponsibilityUnit],
        candidate: Stage2DecompositionCandidate,
        evaluation: Stage2CandidateEvaluation,
        selection_result: Stage2SelectionResult,
        degraded: bool,
    ) -> Stage2RepoSkeletonArtifact:
        ru_by_id = {item.responsibility_id: item for item in responsibilities}
        module_by_name = {item.module: item for item in candidate.modules}
        module_names = set(module_by_name)
        hierarchy = list(candidate.hierarchy)
        generation_order = self._leaf_first_order(
            module_names,
            [(item.parent, item.child) for item in hierarchy],
        )
        parents_by_module = {
            module: sorted({item.parent for item in hierarchy if item.child == module})
            for module in module_names
        }
        children_by_module = {
            module: sorted({item.child for item in hierarchy if item.parent == module})
            for module in module_names
        }
        hierarchy_payload = []
        for edge in hierarchy:
            payload = model_dump(edge)
            payload["source_kind"] = self._normalized_evidence_source_kind(
                edge.source_kind,
                edge.supporting_fact_ids,
            )
            hierarchy_payload.append(payload)
        modules_payload: list[dict[str, Any]] = []
        for module_name in generation_order:
            candidate_module = module_by_name[module_name]
            module_rus = [
                ru_by_id[item]
                for item in candidate_module.responsibility_ids
                if item in ru_by_id
            ]
            kind = self._derive_module_kind(
                module_name=module_name,
                top_module=locked_top.module,
                responsibilities=module_rus,
            )
            instance_hints = []
            for edge in hierarchy:
                if edge.parent != module_name:
                    continue
                child = module_by_name[edge.child]
                instance_hints.append(
                    {
                        "module": edge.child,
                        "count": self._instance_count_hint(
                            stage2_input,
                            child_module=edge.child,
                            supporting_fact_ids=edge.supporting_fact_ids,
                        ),
                        "usage": child.role,
                        "source_kind": self._normalized_evidence_source_kind(
                            edge.source_kind,
                            edge.supporting_fact_ids,
                        ),
                        "supporting_fact_ids": list(edge.supporting_fact_ids),
                        "rationale": edge.rationale or f"Selected {candidate.plan_style} hierarchy boundary.",
                        "confidence": edge.confidence,
                    }
                )
            modules_payload.append(
                {
                    "module": module_name,
                    "responsibility_ids": [r.responsibility_id for r in module_rus if r.ownership_required],
                    "applicable_constraint_ids": [r.responsibility_id for r in responsibilities if not r.ownership_required and set(r.applies_to_responsibility_ids).intersection(candidate_module.responsibility_ids)],
                    "file_path": f"generate/rtl/{module_name}.v",
                    "role": candidate_module.role,
                    "kind": kind,
                    "source_kind": self._normalized_evidence_source_kind(
                        candidate_module.source_kind,
                        candidate_module.supporting_fact_ids,
                    ),
                    "supporting_fact_ids": list(candidate_module.supporting_fact_ids),
                    "rationale": candidate_module.rationale or candidate.summary,
                    "confidence": candidate_module.confidence,
                    "module_decision": "required",
                    "parents": parents_by_module[module_name],
                    "children": children_by_module[module_name],
                    "instance_hints": instance_hints,
                    "repo_notes": [
                        f"Owns responsibilities: {', '.join(candidate_module.responsibility_ids)}"
                    ],
                }
            )

        primary_clock, reset_signal, reset_style = self._clocking_model(
            stage2_input,
            responsibilities,
        )
        boundary_alignment = [
            f"{item.producer_module}->{item.consumer_module}: "
            f"{', '.join(item.transferred_objects)}; protocol={item.protocol or 'unresolved'}; "
            f"timing={item.timing_class or 'unresolved'}"
            for item in candidate.boundary_contracts
        ]
        open_issues = list(candidate.open_issues)
        if degraded:
            open_issues.extend(
                f"Stage2 degraded selection: {item}" for item in evaluation.hard_violations
            )
        if selection_result.fallback_used:
            open_issues.append(
                f"Stage2 architecture-judge fallback: {selection_result.fallback_reason}"
            )
        shared_modules = sorted(
            module for module, parents in parents_by_module.items() if len(parents) > 1
        )
        return validate_model(
            Stage2RepoSkeletonArtifact,
            {
                "schema_version": "repo_skeleton_v2",
                "task_id": task.task_id,
                "source_schema_version": stage2_input.schema_version,
                "stage2_status": "repo_skeleton_planned",
                "top_module": locked_top.module,
                "global_invariants": {
                    "system_role": candidate.summary,
                    "clocking_model": {
                        "primary_clock": primary_clock,
                        "reset_signal": reset_signal,
                        "reset_style": reset_style,
                    },
                    "hierarchy": hierarchy_payload,
                    "file_map": {
                        module_name: f"generate/rtl/{module_name}.v"
                        for module_name in generation_order
                    },
                    "cross_module_alignment": boundary_alignment,
                    "global_data_conventions": self._ordered_nonempty(
                        [
                            *candidate.global_data_conventions,
                            *[
                                item
                                for responsibility in responsibilities
                                for item in (
                                    [responsibility.protocol] if responsibility.protocol else []
                                )
                            ],
                        ]
                    ),
                },
                "modules": modules_payload,
                "planning_decisions": {
                    "generation_order": generation_order,
                    "leaf_first": True,
                    "shared_modules": shared_modules,
                    "top_level_integration_notes": boundary_alignment,
                },
                "open_issues": self._ordered_nonempty(open_issues),
            },
        )

    @staticmethod
    def _normalized_evidence_source_kind(
        source_kind: str,
        supporting_fact_ids: List[str],
    ) -> str:
        """Keep optional evidence metadata from becoming a conversion blocker.

        Candidate generation can ground an inferred boundary in specification
        sections without selecting a Stage1 fact id.  Treat that provenance as
        spec-derived instead of emitting the contradictory combination
        ``inferred_from_fact_ledger`` plus an empty fact-id list.
        """
        if source_kind == "inferred_from_fact_ledger" and not supporting_fact_ids:
            return "inferred_from_spec"
        return source_kind

    @staticmethod
    def _instance_count_hint(
        stage2_input: Stage2PlanningInput,
        *,
        child_module: str,
        supporting_fact_ids: List[str],
    ) -> int | str:
        supporting_ids = set(supporting_fact_ids)
        for fact in stage2_input.fact_ledger.facts:
            obj = fact.object or {}
            referenced_names = {
                str(obj.get("module") or "").strip(),
                str(obj.get("child") or "").strip(),
                str(obj.get("unit") or "").strip(),
                str(obj.get("resource") or "").strip(),
                str(fact.subject or "").strip(),
            }
            if child_module not in referenced_names and fact.fact_id not in supporting_ids:
                continue
            count = obj.get("count") or obj.get("instance_count") or obj.get("instances")
            if count not in (None, "", 0):
                return count
        return 1

    @staticmethod
    def _derive_module_kind(
        *,
        module_name: str,
        top_module: str,
        responsibilities: List[ResponsibilityUnit],
    ) -> str:
        if module_name == top_module:
            return "top_controller"
        if any(item.iterative for item in responsibilities):
            return "iterative_engine"
        stateful = any(
            item.owned_state
            or item.clock_domain
            or item.reset_behavior
            or "registered" in item.timing_class.lower()
            or "multi" in item.timing_class.lower()
            for item in responsibilities
        )
        return "leaf_stateful" if stateful else "leaf_combinational"

    @staticmethod
    def _leaf_first_order(modules: Set[str], hierarchy: List[Tuple[str, str]]) -> List[str]:
        parents_by_child: dict[str, set[str]] = {module: set() for module in modules}
        child_count: dict[str, int] = {module: 0 for module in modules}
        for parent, child in hierarchy:
            parents_by_child.setdefault(child, set()).add(parent)
            child_count[parent] = child_count.get(parent, 0) + 1
        ready = sorted(module for module in modules if child_count.get(module, 0) == 0)
        order: list[str] = []
        while ready:
            module = ready.pop(0)
            order.append(module)
            for parent in sorted(parents_by_child.get(module, set())):
                child_count[parent] -= 1
                if child_count[parent] == 0:
                    ready.append(parent)
                    ready.sort()
        if len(order) != len(modules):
            raise ValueError("candidate hierarchy cannot produce a leaf-first generation order")
        return order

    @staticmethod
    def _clocking_model(
        stage2_input: Stage2PlanningInput,
        responsibilities: List[ResponsibilityUnit],
    ) -> tuple[str, str, str]:
        primary_clock = next((item.clock_domain for item in responsibilities if item.clock_domain), "")
        reset_style = next((item.reset_behavior for item in responsibilities if item.reset_behavior), "")
        reset_signal = ""
        legacy = stage2_input.legacy_contract_projection
        if legacy is not None:
            top = legacy.structure_contract.top_module
            interface = next(
                (item for item in legacy.interface_contracts if item.module == top),
                None,
            )
            if interface is not None:
                primary_clock = primary_clock or interface.clock
                reset_signal = interface.reset
                reset_style = reset_style or interface.reset_polarity
        return primary_clock, reset_signal, reset_style

    def build_prompt(
        self,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        stage_context: Dict[str, Any],
    ) -> tuple[str, List[str]]:
        stage2_input = self._get_stage2_input(partial_artifacts)
        prompt_context = self._build_stage2_prompt_context(stage2_input)
        prompt_context_json = json.dumps(
            prompt_context,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        stage_context_json = json.dumps(
            stage_context or {},
            ensure_ascii=False,
            separators=(",", ":"),
        )
        prompt = stage2_repo_skeleton.build_repo_skeleton_prompt(
            stage2_prompt_context_json=prompt_context_json,
            stage_context=stage_context_json,
        )
        primary_markdown = str(
            (prompt_context.get("primary_source_spec") or {}).get("markdown") or ""
        )
        facts_json = json.dumps(
            prompt_context.get("architecture_facts") or [],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        fixed_chars = max(0, len(prompt) - len(prompt_context_json) - len(stage_context_json))
        self.logger.info(
            "[%s] Prompt context chars: source=%d facts=%d context=%d fixed=%d total=%d",
            self.stage_name,
            len(primary_markdown),
            len(facts_json),
            len(prompt_context_json),
            fixed_chars,
            len(prompt),
        )
        return prompt, []

    def _build_retry_prompt(self, original_prompt: str, errors: List[str]) -> str:
        del original_prompt
        output_name = str(getattr(self, "_retry_output_name", "repo_skeleton_v1 JSON") or "JSON")
        return (
            f"Revise the complete {output_name} JSON from the previous response.\n"
            "Return the complete corrected JSON object only. Do not repeat or summarize the input spec.\n"
            "Issues:\n- " + "\n- ".join(errors)
        )

    def _build_stage2_prompt_context(self, stage2_input: Stage2PlanningInput) -> Dict[str, Any]:
        top_module = self._top_module_hint(stage2_input)
        primary = self._primary_source_spec(stage2_input, top_module)
        supplemental = [
            {"path": item.path, "stem": item.stem}
            for item in stage2_input.source_specs
            if primary is None or item.path != primary.path
        ]
        architecture_facts, omitted_count = self._bounded_architecture_facts(stage2_input)
        known_modules = self._known_module_candidates(stage2_input, top_module)
        explicit_hierarchy = self._explicit_hierarchy_context(stage2_input)
        return {
            "schema_version": "stage2_prompt_context_v1",
            "task_id": stage2_input.task_id,
            "primary_source_spec": (
                {"path": primary.path, "stem": primary.stem, "markdown": primary.markdown}
                if primary is not None
                else None
            ),
            "supplemental_source_specs": supplemental,
            "responsibility_source_specs": [{"path": item.path, "markdown": item.markdown} for item in stage2_input.source_specs if primary is None or item.path != primary.path],
            "responsibility_facts": [f.model_dump(exclude={"text_grounding", "image_grounding"}) for f in stage2_input.fact_ledger.facts],
            "top_module_hint": top_module,
            "known_module_candidates": known_modules,
            "architecture_facts": architecture_facts,
            "architecture_facts_omitted_count": omitted_count,
            "explicit_hierarchy": explicit_hierarchy,
        }

    @staticmethod
    def _build_candidate_prompt_context(prompt_context: Dict[str, Any]) -> Dict[str, Any]:
        """Remove source markdown after Stage2A has established the shared behavior baseline."""
        candidate_context = {k: v for k, v in prompt_context.items() if k not in {"responsibility_source_specs", "responsibility_facts"}}
        primary = prompt_context.get("primary_source_spec")
        if isinstance(primary, dict):
            candidate_context["primary_source_spec"] = {
                key: primary[key]
                for key in ("path", "stem")
                if key in primary
            }
        return candidate_context

    def _top_module_hint(self, stage2_input: Stage2PlanningInput) -> str:
        explicit = sorted(self._explicit_top_modules(stage2_input))
        if explicit:
            return explicit[0]
        legacy = stage2_input.legacy_contract_projection
        if legacy is not None:
            return str(legacy.structure_contract.top_module or "").strip()
        return ""

    def _primary_source_spec(self, stage2_input: Stage2PlanningInput, top_module: str):
        sources = list(stage2_input.source_specs)
        if not sources:
            return None
        grounded_paths: list[str] = []
        for fact in stage2_input.fact_ledger.facts:
            if fact.module != top_module:
                continue
            grounded_paths.extend(
                grounding.source_md_file
                for grounding in fact.text_grounding
                if grounding.source_md_file
            )
        for grounded_path in grounded_paths:
            resolved = str(Path(grounded_path).resolve())
            match = next(
                (item for item in sources if str(Path(item.path).resolve()) == resolved),
                None,
            )
            if match is not None:
                return match
        indexed_path = str(stage2_input.spec_index.get(top_module) or "")
        if indexed_path:
            resolved = str(Path(indexed_path).resolve())
            match = next(
                (item for item in sources if str(Path(item.path).resolve()) == resolved),
                None,
            )
            if match is not None:
                return match
        preferred_stems = {top_module, f"{top_module}_system"}
        match = next((item for item in sources if item.stem in preferred_stems), None)
        return match or sources[0]

    def _bounded_architecture_facts(
        self,
        stage2_input: Stage2PlanningInput,
    ) -> tuple[List[Dict[str, Any]], int]:
        ranked: list[tuple[int, int, Any]] = []
        for index, fact in enumerate(stage2_input.fact_ledger.facts):
            category = fact.category.strip().lower()
            predicate = fact.predicate.strip().lower()
            relation_type = str(fact.object.get("relation_type") or "").strip().lower()
            explicit_relation = (
                predicate in self._EXPLICIT_RELATION_PREDICATES
                or relation_type in self._EXPLICIT_RELATION_PREDICATES
            )
            if category not in self._ARCHITECTURE_FACT_CATEGORIES and not explicit_relation:
                continue
            if explicit_relation or (
                category == "module_identity"
                and predicate in {"is_top_module", "top_module"}
            ):
                priority = 0
            elif category == "module_identity":
                priority = 1
            elif category == "resource_requirement":
                priority = 2
            else:
                priority = 3
            ranked.append((priority, index, fact))
        ranked.sort(key=lambda item: (item[0], item[1]))

        selected: list[Dict[str, Any]] = []
        omitted = 0
        for _, _, fact in ranked:
            entry = self._compact_architecture_fact(fact)
            candidate = [*selected, entry]
            encoded = json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))
            if len(encoded) <= self.architecture_facts_max_chars:
                selected.append(entry)
            else:
                omitted += 1
        return selected, omitted

    def _compact_architecture_fact(self, fact: Any) -> Dict[str, Any]:
        payload = {
            "fact_id": fact.fact_id,
            "module": fact.module,
            "category": fact.category,
            "subject": fact.subject,
            "predicate": fact.predicate,
            "object": fact.object,
            "notes": fact.notes,
        }
        return self._drop_empty_values(payload)

    def _known_module_candidates(
        self,
        stage2_input: Stage2PlanningInput,
        top_module: str,
    ) -> List[str]:
        values = [top_module, *stage2_input.compat_module_candidates]
        for fact in stage2_input.fact_ledger.facts:
            if fact.category.strip().lower() != "module_identity":
                continue
            module_values = fact.object.get("modules") or []
            if isinstance(module_values, str):
                module_values = [module_values]
            values.extend(
                [
                    fact.module,
                    str(fact.object.get("module") or ""),
                    *[str(item) for item in module_values],
                    str(fact.object.get("parent") or ""),
                    str(fact.object.get("child") or ""),
                ]
            )
        return self._ordered_nonempty(values)

    def _explicit_hierarchy_context(self, stage2_input: Stage2PlanningInput) -> List[Dict[str, str]]:
        entries: list[Dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for fact in stage2_input.fact_ledger.facts:
            predicate = fact.predicate.strip().lower()
            relation_type = str(fact.object.get("relation_type") or "").strip().lower()
            if (
                predicate not in self._EXPLICIT_RELATION_PREDICATES
                and relation_type not in self._EXPLICIT_RELATION_PREDICATES
            ):
                continue
            parent = str(fact.object.get("parent") or fact.module or "").strip()
            child = str(fact.object.get("child") or fact.object.get("target") or "").strip()
            if not parent or not child or parent == child or (parent, child) in seen:
                continue
            seen.add((parent, child))
            entries.append(
                {
                    "parent": parent,
                    "child": child,
                    "fact_id": fact.fact_id,
                    "predicate": predicate or relation_type,
                }
            )
        return entries

    @classmethod
    def _drop_empty_values(cls, value: Any) -> Any:
        if isinstance(value, dict):
            return {
                key: cls._drop_empty_values(item)
                for key, item in value.items()
                if item not in (None, "", [], {})
            }
        if isinstance(value, list):
            return [cls._drop_empty_values(item) for item in value]
        return value

    @staticmethod
    def _ordered_nonempty(values: List[str]) -> List[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            item = str(value or "").strip()
            if not item or item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result

    def validate_quality(
        self,
        artifact: Stage2RepoSkeletonArtifact,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
    ) -> List[str]:
        stage2_input = self._get_stage2_input(partial_artifacts)
        planned_modules = [item.module for item in artifact.modules]
        known_module_set = set(planned_modules)
        errors: List[str] = []

        if artifact.task_id != task_input.task_id:
            errors.append(f"task_id must remain {task_input.task_id}")
        if artifact.schema_version not in {"repo_skeleton_v1", "repo_skeleton_v2"}:
            errors.append("schema_version must remain repo_skeleton_v1")
        if artifact.source_schema_version != stage2_input.schema_version:
            errors.append(f"source_schema_version must remain {stage2_input.schema_version}")
        if artifact.module_order:
            errors.append("module_order should be omitted or empty; use planning_decisions.generation_order instead")
        if not artifact.top_module:
            errors.append("top_module must be non-empty")
        elif artifact.top_module not in known_module_set:
            errors.append(f"top_module `{artifact.top_module}` must appear in planned modules")
        explicit_tops = self._explicit_top_modules(stage2_input)
        if explicit_tops and artifact.top_module not in explicit_tops:
            errors.append(f"top_module must preserve explicit Stage1 top candidates {sorted(explicit_tops)}")
        duplicate_modules = sorted({module for module in planned_modules if planned_modules.count(module) > 1})
        if duplicate_modules:
            errors.append(f"modules must not contain duplicates: {duplicate_modules}")
        if not planned_modules:
            errors.append("modules must not be empty")

        file_map = artifact.global_invariants.file_map
        missing_file_map = [module for module in planned_modules if module not in file_map]
        if missing_file_map:
            errors.append(f"global_invariants.file_map must cover all planned modules: missing {missing_file_map}")
        for module in planned_modules:
            expected_path = f"generate/rtl/{module}.v"
            actual_path = file_map.get(module, "")
            if actual_path != expected_path:
                errors.append(f"global_invariants.file_map[{module}] must be `{expected_path}`")

        for edge in artifact.global_invariants.hierarchy:
            if edge.parent not in known_module_set or edge.child not in known_module_set:
                errors.append(f"global_invariants.hierarchy references unknown modules `{edge.parent}->{edge.child}`")

        explicit_edges = self._explicit_edges(stage2_input)
        actual_edges = {
            (edge.parent, edge.child)
            for edge in artifact.global_invariants.hierarchy
        }
        missing_explicit_edges = sorted(explicit_edges - actual_edges)
        if missing_explicit_edges:
            errors.append(f"global_invariants.hierarchy must preserve explicit stage1 edges: {missing_explicit_edges}")

        generation_order = artifact.planning_decisions.generation_order
        if set(generation_order) != known_module_set or len(generation_order) != len(planned_modules):
            errors.append("planning_decisions.generation_order must cover every planned module exactly once")
        else:
            module_names = [item.module for item in artifact.modules]
            if module_names != generation_order:
                errors.append(
                    "modules list must follow planning_decisions.generation_order to preserve generation sequencing"
                )
            order_index = {name: idx for idx, name in enumerate(generation_order)}
            dependency_edges = [(edge.parent, edge.child) for edge in artifact.global_invariants.hierarchy]
            for parent, child in dependency_edges:
                if child in order_index and parent in order_index and order_index[child] > order_index[parent]:
                    errors.append(
                        f"planning_decisions.generation_order must be leaf-first; child `{child}` "
                        f"must appear before parent `{parent}`"
                    )

            if self._has_cycle(known_module_set, dependency_edges):
                errors.append("global_invariants.hierarchy must not contain dependency cycles")

        expected_shared = sorted(self._shared_modules_from_hierarchy(artifact))
        actual_shared = sorted(artifact.planning_decisions.shared_modules)
        missing_shared = [module for module in expected_shared if module not in actual_shared]
        if missing_shared:
            errors.append(f"planning_decisions.shared_modules must include explicit shared modules {missing_shared}")

        for module_entry in artifact.modules:
            expected_path = f"generate/rtl/{module_entry.module}.v"
            if module_entry.file_path != expected_path:
                errors.append(f"modules[{module_entry.module}].file_path must be `{expected_path}`")
            if not module_entry.role.strip():
                errors.append(f"modules[{module_entry.module}].role must be non-empty")
            unknown_module_refs = [
                item
                for item in [*module_entry.parents, *module_entry.children]
                if item not in known_module_set
            ]
            if unknown_module_refs:
                errors.append(f"modules[{module_entry.module}] references unknown parent/child modules {unknown_module_refs}")
            expected_parents = sorted(edge.parent for edge in artifact.global_invariants.hierarchy if edge.child == module_entry.module)
            expected_children = sorted(edge.child for edge in artifact.global_invariants.hierarchy if edge.parent == module_entry.module)
            if sorted(module_entry.parents) != expected_parents:
                errors.append(f"modules[{module_entry.module}].parents must match global hierarchy parents {expected_parents}")
            if sorted(module_entry.children) != expected_children:
                errors.append(f"modules[{module_entry.module}].children must match global hierarchy children {expected_children}")
            for hint in module_entry.instance_hints:
                if hint.module and hint.module not in known_module_set:
                    errors.append(
                        f"modules[{module_entry.module}].instance_hints references unknown module `{hint.module}`"
                    )

        return errors

    def _known_fact_ids(self, stage2_input: Stage2PlanningInput) -> set[str]:
        fact_ids: set[str] = set()
        for fact in stage2_input.fact_ledger.facts:
            if fact.fact_id:
                fact_ids.add(fact.fact_id)
        return fact_ids

    def _has_dependency_facts(self, stage2_input: Stage2PlanningInput) -> bool:
        categories = {"resource_requirement", "data_dependency"}
        return any(str(fact.category).strip().lower() in categories for fact in stage2_input.fact_ledger.facts)

    def _has_partitioning_guidance(self, stage2_input: Stage2PlanningInput) -> bool:
        markers = {
            "functional decomposition",
            "design partitioning guidance",
            "natural boundaries",
            "reusable implementation units",
            "separate sequential blocks",
            "separate reusable implementation",
        }
        for source_spec in stage2_input.source_specs:
            text = str(source_spec.markdown or "").lower()
            if any(marker in text for marker in markers):
                return True
        return False

    def _explicit_top_modules(self, stage2_input: Stage2PlanningInput) -> Set[str]:
        tops: set[str] = set()
        for fact in stage2_input.fact_ledger.facts:
            if fact.category.strip().lower() == "module_identity" and fact.predicate.strip().lower() in {"is_top_module", "top_module"}:
                value = str(fact.object.get("module") or fact.module or fact.subject or "").strip()
                if value:
                    tops.add(value)
        legacy_projection = stage2_input.legacy_contract_projection
        legacy_top = legacy_projection.structure_contract.top_module if legacy_projection is not None else ""
        if legacy_top and not tops:
            tops.add(legacy_top)
        return tops

    def _explicit_edges(self, stage2_input: Stage2PlanningInput) -> Set[Tuple[str, str]]:
        predicates = {
            "instantiates",
            "instantiate",
            "contains",
            "includes",
            "is_composed_of",
            "has_child_module",
        }
        edges: set[tuple[str, str]] = set()
        for fact in stage2_input.fact_ledger.facts:
            predicate = fact.predicate.strip().lower()
            relation_type = str(fact.object.get("relation_type") or "").strip().lower()
            if predicate not in predicates and relation_type not in predicates:
                continue
            parent = str(fact.object.get("parent") or fact.module or "").strip()
            child = str(fact.object.get("child") or fact.object.get("target") or "").strip()
            if parent and child and parent != child:
                edges.add((parent, child))
        legacy = stage2_input.legacy_contract_projection
        if legacy is not None:
            for relation in [
                *legacy.structure_contract.hierarchy,
                *legacy.structure_contract.instantiation_graph,
            ]:
                parent = str(relation.parent or "").strip()
                child = str(relation.child or "").strip()
                if parent and child and parent != child:
                    edges.add((parent, child))
        return edges

    def _shared_modules_from_hierarchy(self, artifact: Stage2RepoSkeletonArtifact) -> Set[str]:
        parent_count: dict[str, int] = {}
        for edge in artifact.global_invariants.hierarchy:
            parent_count[edge.child] = parent_count.get(edge.child, 0) + 1
        return {module for module, count in parent_count.items() if count > 1}

    def _has_cycle(self, modules: Set[str], edges: List[Tuple[str, str]]) -> bool:
        children_by_parent: dict[str, set[str]] = {module: set() for module in modules}
        for parent, child in edges:
            if parent in modules and child in modules:
                children_by_parent[parent].add(child)
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(module: str) -> bool:
            if module in visiting:
                return True
            if module in visited:
                return False
            visiting.add(module)
            for child in children_by_parent.get(module, set()):
                if visit(child):
                    return True
            visiting.remove(module)
            visited.add(module)
            return False

        return any(visit(module) for module in modules)

    def _get_stage2_input(self, partial_artifacts: Dict[str, Any]) -> Stage2PlanningInput:
        candidate = partial_artifacts.get("stage2_input")
        if candidate is not None:
            if isinstance(candidate, Stage2PlanningInput):
                return candidate
            return validate_model(Stage2PlanningInput, candidate)
        modules_artifact = self._get_modules_artifact(partial_artifacts)
        legacy_payload = {
            "task_id": modules_artifact.task_id,
            "stage1_status": "contracts_completed",
            "completed_rounds": ["facts"],
            "spec_index": {},
            "structure_contract": model_dump(modules_artifact.repository_structure),
            "fact_ledger": model_dump(modules_artifact.fact_ledger),
        }
        return Stage2PlanningInput(
            task_id=modules_artifact.task_id,
            spec_index={},
            source_specs=[],
            fact_ledger=modules_artifact.fact_ledger,
            legacy_contract_projection=legacy_payload,
            compat_module_candidates=list(modules_artifact.module_order),
        )

    def _get_modules_artifact(self, partial_artifacts: Dict[str, Any]) -> ModuleOrganizationArtifact:
        candidate = partial_artifacts.get("modules")
        if candidate is None:
            raise ValueError("Stage2 repo skeleton planning requires partial_artifacts['modules']")
        if isinstance(candidate, ModuleOrganizationArtifact):
            return candidate
        return validate_model(ModuleOrganizationArtifact, candidate)
