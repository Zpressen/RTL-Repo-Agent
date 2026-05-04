from __future__ import annotations

from typing import Iterable

from .agents.base import model_dump, validate_model
from .schemas import ModuleContractsBundle, ModuleOrganizationArtifact, Stage1ContractsArtifact


def build_module_organized_artifact(stage1_artifact: Stage1ContractsArtifact) -> ModuleOrganizationArtifact:
    structure = stage1_artifact.structure_contract
    top_module = str(structure.top_module or "").strip()
    declared_modules = [str(item).strip() for item in structure.modules if str(item).strip()]

    contract_modules = _ordered_unique(
        [
            *(item.module for item in stage1_artifact.interface_contracts if item.module),
            *(item.module for item in stage1_artifact.timing_contracts if item.module),
            *(item.module for item in stage1_artifact.control_contracts if item.module),
            *(item.module for item in stage1_artifact.datapath_contracts if item.module),
            *(item.module for item in stage1_artifact.planning_facts if item.module),
        ]
    )
    module_order = _ordered_unique([top_module, *declared_modules, *contract_modules])

    interface_by_module = {item.module: item for item in stage1_artifact.interface_contracts if item.module}
    timing_by_module = {item.module: item for item in stage1_artifact.timing_contracts if item.module}
    control_by_module = {item.module: item for item in stage1_artifact.control_contracts if item.module}
    datapath_by_module = {item.module: item for item in stage1_artifact.datapath_contracts if item.module}
    planning_by_module = {item.module: item for item in stage1_artifact.planning_facts if item.module}

    bundles = []
    for module_name in module_order:
        outgoing_hierarchy = [item for item in structure.hierarchy if item.parent == module_name]
        incoming_hierarchy = [item for item in structure.hierarchy if item.child == module_name]
        outgoing_instantiation = [item for item in structure.instantiation_graph if item.parent == module_name]
        incoming_instantiation = [item for item in structure.instantiation_graph if item.child == module_name]

        bundles.append(
            validate_model(
                ModuleContractsBundle,
                {
                    "module": module_name,
                    "is_top_module": bool(top_module and module_name == top_module),
                    "interface_contract": model_dump(interface_by_module[module_name]) if module_name in interface_by_module else None,
                    "timing_contract": model_dump(timing_by_module[module_name]) if module_name in timing_by_module else None,
                    "control_contract": model_dump(control_by_module[module_name]) if module_name in control_by_module else None,
                    "datapath_contract": model_dump(datapath_by_module[module_name]) if module_name in datapath_by_module else None,
                    "planning_facts": model_dump(planning_by_module[module_name]) if module_name in planning_by_module else None,
                    "parent_modules": _ordered_unique(item.parent for item in incoming_hierarchy + incoming_instantiation if item.parent),
                    "child_modules": _ordered_unique(item.child for item in outgoing_hierarchy + outgoing_instantiation if item.child),
                    "outgoing_hierarchy_relations": [model_dump(item) for item in outgoing_hierarchy],
                    "incoming_hierarchy_relations": [model_dump(item) for item in incoming_hierarchy],
                    "outgoing_instantiation_relations": [model_dump(item) for item in outgoing_instantiation],
                    "incoming_instantiation_relations": [model_dump(item) for item in incoming_instantiation],
                },
            )
        )

    return validate_model(
        ModuleOrganizationArtifact,
        {
            "task_id": stage1_artifact.task_id,
            "source_schema_version": stage1_artifact.schema_version,
            "top_module": top_module,
            "module_order": module_order,
            "repository_structure": model_dump(structure),
            "modules": [model_dump(item) for item in bundles],
        },
    )


def _ordered_unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for raw in items:
        item = str(raw or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
