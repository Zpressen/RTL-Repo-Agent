from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from ..prompts import stage2_repo_skeleton
from ..schemas import ModuleOrganizationArtifact, PlannerTaskInput, Stage2PlanningInput, Stage2RepoSkeletonArtifact
from .base import BaseStageAgent, model_dump, validate_model


class Stage2Agent(BaseStageAgent):
    stage_name = "stage2_repo_skeleton"
    output_model = Stage2RepoSkeletonArtifact
    system_role = stage2_repo_skeleton.REPO_SKELETON_SYSTEM_ROLE

    def build_prompt(
        self,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
        stage_context: Dict[str, Any],
    ) -> tuple[str, List[str]]:
        stage2_input = self._get_stage2_input(partial_artifacts)
        prompt = stage2_repo_skeleton.build_repo_skeleton_prompt(
            stage2_planning_input_json=self.to_pretty_json(stage2_input),
            stage_context=self.to_pretty_json(stage_context),
        )
        return prompt, []

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
        if artifact.schema_version != "repo_skeleton_v1":
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
        elif self._has_partitioning_guidance(stage2_input) and len(planned_modules) < 2:
            errors.append(
                "source specs contain explicit functional decomposition or partitioning guidance; "
                "stage2 must plan more than one module or revise the decomposition rationale"
            )

        file_map = artifact.global_invariants.file_map
        missing_file_map = [module for module in planned_modules if module not in file_map]
        if missing_file_map:
            errors.append(f"global_invariants.file_map must cover all planned modules: missing {missing_file_map}")
        for module in planned_modules:
            expected_path = f"rtl/{module}.v"
            actual_path = file_map.get(module, "")
            if actual_path != expected_path:
                errors.append(f"global_invariants.file_map[{module}] must be `{expected_path}`")

        known_fact_ids = self._known_fact_ids(stage2_input)
        for edge in artifact.global_invariants.hierarchy:
            if edge.parent not in known_module_set or edge.child not in known_module_set:
                errors.append(f"global_invariants.hierarchy references unknown modules `{edge.parent}->{edge.child}`")
            if edge.source_kind == "inferred_from_fact_ledger" and (not edge.supporting_fact_ids or not edge.rationale.strip()):
                errors.append(
                    f"global_invariants.hierarchy inferred edge `{edge.parent}->{edge.child}` must cite supporting_fact_ids and rationale"
                )
            if edge.source_kind == "inferred_from_spec" and not edge.rationale.strip():
                errors.append(
                    f"global_invariants.hierarchy inferred-from-spec edge `{edge.parent}->{edge.child}` must include rationale"
                )
            unknown_fact_ids = [
                fact_id
                for fact_id in edge.supporting_fact_ids
                if edge.source_kind == "inferred_from_fact_ledger" and fact_id not in known_fact_ids
            ]
            if unknown_fact_ids:
                errors.append(
                    f"global_invariants.hierarchy `{edge.parent}->{edge.child}` cites unknown fact ids {unknown_fact_ids}"
                )

        explicit_edges = self._explicit_edges(stage2_input)
        actual_edges = {
            (edge.parent, edge.child)
            for edge in artifact.global_invariants.hierarchy
        }
        missing_explicit_edges = sorted(explicit_edges - actual_edges)
        if missing_explicit_edges:
            errors.append(f"global_invariants.hierarchy must preserve explicit stage1 edges: {missing_explicit_edges}")

        if self._has_dependency_facts(stage2_input) and not artifact.global_invariants.hierarchy:
            if not any("hierarchy" in item.lower() or "dependency" in item.lower() for item in artifact.open_issues):
                errors.append(
                    "fact_ledger contains dependency/resource facts but stage2 produced no hierarchy; "
                    "add inferred hierarchy or record an open issue"
                )

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
            expected_path = f"rtl/{module_entry.module}.v"
            if module_entry.file_path != expected_path:
                errors.append(f"modules[{module_entry.module}].file_path must be `{expected_path}`")
            if not module_entry.role.strip():
                errors.append(f"modules[{module_entry.module}].role must be non-empty")
            if module_entry.source_kind in {"inferred_from_fact_ledger", "inferred_from_spec"}:
                if not module_entry.supporting_fact_ids and not module_entry.rationale.strip():
                    errors.append(
                        f"modules[{module_entry.module}] inferred module decisions must cite supporting facts or rationale"
                    )
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
                if hint.source_kind == "inferred_from_fact_ledger" and (not hint.supporting_fact_ids or not hint.rationale.strip()):
                    errors.append(
                        f"modules[{module_entry.module}].instance_hints inferred hint for `{hint.module}` "
                        "must cite supporting_fact_ids and rationale"
                    )
                if hint.source_kind == "inferred_from_spec" and not hint.rationale.strip():
                    errors.append(
                        f"modules[{module_entry.module}].instance_hints inferred-from-spec hint for `{hint.module}` "
                        "must include rationale"
                    )
                unknown_fact_ids = [
                    fact_id
                    for fact_id in hint.supporting_fact_ids
                    if hint.source_kind == "inferred_from_fact_ledger" and fact_id not in known_fact_ids
                ]
                if unknown_fact_ids:
                    errors.append(
                        f"modules[{module_entry.module}].instance_hints for `{hint.module}` cites unknown fact ids {unknown_fact_ids}"
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
            "interface_contracts": [
                model_dump(item.interface_contract) for item in modules_artifact.modules if item.interface_contract
            ],
            "timing_contracts": [
                model_dump(item.timing_contract) for item in modules_artifact.modules if item.timing_contract
            ],
            "control_contracts": [
                model_dump(item.control_contract) for item in modules_artifact.modules if item.control_contract
            ],
            "datapath_contracts": [
                model_dump(item.datapath_contract) for item in modules_artifact.modules if item.datapath_contract
            ],
            "planning_facts": [
                model_dump(item.planning_facts) for item in modules_artifact.modules if item.planning_facts
            ],
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
