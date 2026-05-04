from __future__ import annotations

from typing import Any, Dict, List

from ..prompts import stage2_repo_skeleton
from ..schemas import ModuleOrganizationArtifact, PlannerTaskInput, Stage2RepoSkeletonArtifact
from .base import BaseStageAgent, validate_model


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
        modules_artifact = self._get_modules_artifact(partial_artifacts)
        prompt = stage2_repo_skeleton.build_repo_skeleton_prompt(
            modules_json=self.to_pretty_json(modules_artifact),
            stage_context=self.to_pretty_json(stage_context),
        )
        return prompt, []

    def validate_quality(
        self,
        artifact: Stage2RepoSkeletonArtifact,
        task_input: PlannerTaskInput,
        partial_artifacts: Dict[str, Any],
    ) -> List[str]:
        modules_artifact = self._get_modules_artifact(partial_artifacts)
        known_modules = list(modules_artifact.module_order)
        known_module_set = set(known_modules)
        errors: List[str] = []

        if artifact.task_id != task_input.task_id:
            errors.append(f"task_id must remain {task_input.task_id}")
        if artifact.schema_version != "repo_skeleton_v1":
            errors.append("schema_version must remain repo_skeleton_v1")
        if artifact.source_schema_version != modules_artifact.schema_version:
            errors.append(f"source_schema_version must remain {modules_artifact.schema_version}")
        if artifact.top_module != modules_artifact.top_module:
            errors.append(f"top_module must remain {modules_artifact.top_module}")
        if artifact.module_order:
            errors.append("module_order should be omitted or empty; use planning_decisions.generation_order instead")

        file_map = artifact.global_invariants.file_map
        missing_file_map = [module for module in known_modules if module not in file_map]
        if missing_file_map:
            errors.append(f"global_invariants.file_map must cover all modules: missing {missing_file_map}")
        for module in known_modules:
            expected_path = f"rtl/{module}.v"
            actual_path = file_map.get(module, "")
            if actual_path != expected_path:
                errors.append(f"global_invariants.file_map[{module}] must be `{expected_path}`")

        for edge in artifact.global_invariants.hierarchy:
            if edge.parent not in known_module_set or edge.child not in known_module_set:
                errors.append(f"global_invariants.hierarchy references unknown modules `{edge.parent}->{edge.child}`")

        generation_order = artifact.planning_decisions.generation_order
        if set(generation_order) != known_module_set or len(generation_order) != len(known_modules):
            errors.append("planning_decisions.generation_order must cover every module exactly once")
        else:
            module_names = [item.module for item in artifact.modules]
            if module_names != generation_order:
                errors.append(
                    "modules list must follow planning_decisions.generation_order to preserve generation sequencing"
                )
            order_index = {name: idx for idx, name in enumerate(generation_order)}
            for bundle in modules_artifact.modules:
                for child in bundle.child_modules:
                    if child in order_index and bundle.module in order_index:
                        if order_index[child] > order_index[bundle.module]:
                            errors.append(
                                f"planning_decisions.generation_order must be leaf-first; child `{child}` "
                                f"must appear before parent `{bundle.module}`"
                            )

        expected_shared = sorted(
            bundle.module
            for bundle in modules_artifact.modules
            if len(bundle.parent_modules) > 1
        )
        actual_shared = sorted(artifact.planning_decisions.shared_modules)
        if actual_shared != expected_shared:
            errors.append(f"planning_decisions.shared_modules must be {expected_shared}")

        for module_entry in artifact.modules:
            expected_path = f"rtl/{module_entry.module}.v"
            if module_entry.file_path != expected_path:
                errors.append(f"modules[{module_entry.module}].file_path must be `{expected_path}`")
            if not module_entry.role.strip():
                errors.append(f"modules[{module_entry.module}].role must be non-empty")
            source_bundle = next((item for item in modules_artifact.modules if item.module == module_entry.module), None)
            if source_bundle is None:
                errors.append(f"modules contains unknown module `{module_entry.module}`")
                continue
            if module_entry.parents != source_bundle.parent_modules:
                errors.append(f"modules[{module_entry.module}].parents must match modules.json")
            if module_entry.children != source_bundle.child_modules:
                errors.append(f"modules[{module_entry.module}].children must match modules.json")
            for hint in module_entry.instance_hints:
                if hint.module and hint.module not in known_module_set:
                    errors.append(
                        f"modules[{module_entry.module}].instance_hints references unknown module `{hint.module}`"
                    )

        return errors

    def _get_modules_artifact(self, partial_artifacts: Dict[str, Any]) -> ModuleOrganizationArtifact:
        candidate = partial_artifacts.get("modules")
        if candidate is None:
            raise ValueError("Stage2 repo skeleton planning requires partial_artifacts['modules']")
        if isinstance(candidate, ModuleOrganizationArtifact):
            return candidate
        return validate_model(ModuleOrganizationArtifact, candidate)
