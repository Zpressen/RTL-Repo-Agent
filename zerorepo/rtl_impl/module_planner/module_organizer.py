from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .agents.base import model_dump, validate_model
from .schemas import (
    ModuleContractsBundle,
    ModuleOrganizationArtifact,
    PlannerTaskInput,
    Stage1ContractsArtifact,
    Stage1FactLedger,
    Stage2PlanningInput,
    Stage2RepoSkeletonArtifact,
    Stage2SourceSpec,
    StructureContract,
)
from .utils import expand_markdown_inputs


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
    facts_by_module = {
        module_name: [fact for fact in stage1_artifact.fact_ledger.facts if fact.module == module_name]
        for module_name in module_order
    }
    repository_facts = [
        fact
        for fact in stage1_artifact.fact_ledger.facts
        if not fact.module or fact.module not in set(module_order)
    ]

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
                    "facts": [model_dump(item) for item in facts_by_module.get(module_name, [])],
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
            "fact_ledger": model_dump(stage1_artifact.fact_ledger),
            "repository_facts": [model_dump(item) for item in repository_facts],
            "modules": [model_dump(item) for item in bundles],
        },
    )


def build_stage2_planning_input(
    *,
    stage1_artifact: Stage1ContractsArtifact,
    task_input: PlannerTaskInput,
    compat_modules: ModuleOrganizationArtifact | None = None,
) -> Stage2PlanningInput:
    source_specs: list[Stage2SourceSpec] = []
    for path in expand_markdown_inputs(task_input.spec_md_files):
        spec_path = Path(path).resolve()
        try:
            markdown = spec_path.read_text(encoding="utf-8")
        except Exception:
            markdown = ""
        source_specs.append(
            Stage2SourceSpec(
                path=str(spec_path),
                stem=spec_path.stem,
                markdown=markdown,
            )
        )

    candidates = []
    if compat_modules is not None:
        candidates.extend(compat_modules.module_order)
    candidates.extend(stage1_artifact.structure_contract.modules)
    candidates.extend(fact.module for fact in stage1_artifact.fact_ledger.facts if fact.module)

    return Stage2PlanningInput(
        task_id=stage1_artifact.task_id,
        spec_index=dict(stage1_artifact.spec_index),
        source_specs=source_specs,
        fact_ledger=stage1_artifact.fact_ledger,
        legacy_contract_projection=stage1_artifact,
        compat_module_candidates=_ordered_unique(candidates),
    )


def build_stage2_planning_input_from_task(*, task_input: PlannerTaskInput) -> Stage2PlanningInput:
    source_specs = _read_stage2_source_specs(task_input)
    spec_index = {
        item.stem: item.path
        for item in source_specs
        if item.stem and item.path
    }
    return Stage2PlanningInput(
        task_id=task_input.task_id,
        spec_index=spec_index,
        source_specs=source_specs,
        fact_ledger=Stage1FactLedger(source_files=[item.path for item in source_specs if item.path]),
        legacy_contract_projection=None,
        compat_module_candidates=[],
    )


def build_module_organized_artifact_from_repo_skeleton(
    *,
    stage1_artifact: Stage1ContractsArtifact,
    repo_skeleton: Stage2RepoSkeletonArtifact,
) -> ModuleOrganizationArtifact:
    legacy = build_module_organized_artifact(stage1_artifact)
    legacy_by_module = {item.module: item for item in legacy.modules}
    repo_by_module = {item.module: item for item in repo_skeleton.modules}
    module_order = _ordered_unique(repo_skeleton.planning_decisions.generation_order)
    if set(module_order) != set(repo_by_module):
        module_order = _ordered_unique([*module_order, *(item.module for item in repo_skeleton.modules)])

    bundles = []
    for module_name in module_order:
        repo_module = repo_by_module.get(module_name)
        legacy_bundle = legacy_by_module.get(module_name)
        parents = list(repo_module.parents) if repo_module is not None else []
        children = list(repo_module.children) if repo_module is not None else []
        outgoing_relations = [
            {
                "parent": edge.parent,
                "child": edge.child,
                "text_grounding": [],
                "image_grounding": [],
            }
            for edge in repo_skeleton.global_invariants.hierarchy
            if edge.parent == module_name
        ]
        incoming_relations = [
            {
                "parent": edge.parent,
                "child": edge.child,
                "text_grounding": [],
                "image_grounding": [],
            }
            for edge in repo_skeleton.global_invariants.hierarchy
            if edge.child == module_name
        ]
        bundles.append(
            validate_model(
                ModuleContractsBundle,
                {
                    "module": module_name,
                    "is_top_module": bool(repo_skeleton.top_module and module_name == repo_skeleton.top_module),
                    "facts": [model_dump(item) for item in (legacy_bundle.facts if legacy_bundle is not None else [])],
                    "interface_contract": model_dump(legacy_bundle.interface_contract) if legacy_bundle and legacy_bundle.interface_contract else None,
                    "timing_contract": model_dump(legacy_bundle.timing_contract) if legacy_bundle and legacy_bundle.timing_contract else None,
                    "control_contract": model_dump(legacy_bundle.control_contract) if legacy_bundle and legacy_bundle.control_contract else None,
                    "datapath_contract": model_dump(legacy_bundle.datapath_contract) if legacy_bundle and legacy_bundle.datapath_contract else None,
                    "planning_facts": model_dump(legacy_bundle.planning_facts) if legacy_bundle and legacy_bundle.planning_facts else None,
                    "parent_modules": _ordered_unique(parents),
                    "child_modules": _ordered_unique(children),
                    "outgoing_hierarchy_relations": outgoing_relations,
                    "incoming_hierarchy_relations": incoming_relations,
                    "outgoing_instantiation_relations": [],
                    "incoming_instantiation_relations": [],
                },
            )
        )

    structure_payload = model_dump(stage1_artifact.structure_contract)
    structure_payload["top_module"] = repo_skeleton.top_module
    structure_payload["modules"] = module_order
    structure_payload["files"] = [repo_skeleton.global_invariants.file_map.get(module, f"rtl/{module}.v") for module in module_order]
    structure_payload["hierarchy"] = [
        {
            "parent": edge.parent,
            "child": edge.child,
            "text_grounding": [],
            "image_grounding": [],
        }
        for edge in repo_skeleton.global_invariants.hierarchy
    ]
    structure_payload["file_map"] = {f"{module}.v": [module] for module in module_order}
    structure_payload["generation_order_candidate"] = module_order

    return validate_model(
        ModuleOrganizationArtifact,
        {
            "task_id": stage1_artifact.task_id,
            "source_schema_version": repo_skeleton.schema_version,
            "top_module": repo_skeleton.top_module,
            "module_order": module_order,
            "repository_structure": structure_payload,
            "fact_ledger": model_dump(stage1_artifact.fact_ledger),
            "repository_facts": [model_dump(item) for item in legacy.repository_facts],
            "modules": [model_dump(item) for item in bundles],
        },
    )


def build_module_organized_artifact_from_repo_skeleton_only(
    *,
    task_input: PlannerTaskInput,
    repo_skeleton: Stage2RepoSkeletonArtifact,
) -> ModuleOrganizationArtifact:
    repo_by_module = {item.module: item for item in repo_skeleton.modules}
    module_order = _ordered_unique(repo_skeleton.planning_decisions.generation_order)
    if set(module_order) != set(repo_by_module):
        module_order = _ordered_unique([*module_order, *(item.module for item in repo_skeleton.modules)])

    bundles = []
    for module_name in module_order:
        repo_module = repo_by_module.get(module_name)
        parents = list(repo_module.parents) if repo_module is not None else []
        children = list(repo_module.children) if repo_module is not None else []
        outgoing_relations = [
            {
                "parent": edge.parent,
                "child": edge.child,
                "text_grounding": [],
                "image_grounding": [],
            }
            for edge in repo_skeleton.global_invariants.hierarchy
            if edge.parent == module_name
        ]
        incoming_relations = [
            {
                "parent": edge.parent,
                "child": edge.child,
                "text_grounding": [],
                "image_grounding": [],
            }
            for edge in repo_skeleton.global_invariants.hierarchy
            if edge.child == module_name
        ]
        bundles.append(
            validate_model(
                ModuleContractsBundle,
                {
                    "module": module_name,
                    "is_top_module": bool(repo_skeleton.top_module and module_name == repo_skeleton.top_module),
                    "facts": [],
                    "interface_contract": None,
                    "timing_contract": None,
                    "control_contract": None,
                    "datapath_contract": None,
                    "planning_facts": None,
                    "parent_modules": _ordered_unique(parents),
                    "child_modules": _ordered_unique(children),
                    "outgoing_hierarchy_relations": outgoing_relations,
                    "incoming_hierarchy_relations": incoming_relations,
                    "outgoing_instantiation_relations": [],
                    "incoming_instantiation_relations": [],
                },
            )
        )

    structure_payload = {
        "top_module": repo_skeleton.top_module,
        "files": [repo_skeleton.global_invariants.file_map.get(module, f"rtl/{module}.v") for module in module_order],
        "modules": module_order,
        "file_map": {f"{module}.v": [module] for module in module_order},
        "hierarchy": [
            {
                "parent": edge.parent,
                "child": edge.child,
                "text_grounding": [],
                "image_grounding": [],
            }
            for edge in repo_skeleton.global_invariants.hierarchy
        ],
        "instantiation_graph": [],
        "generation_order_candidate": module_order,
    }
    fact_ledger = Stage1FactLedger(
        source_files=[
            item.path
            for item in _read_stage2_source_specs(task_input)
            if item.path
        ]
    )

    return validate_model(
        ModuleOrganizationArtifact,
        {
            "task_id": task_input.task_id,
            "source_schema_version": repo_skeleton.schema_version,
            "top_module": repo_skeleton.top_module,
            "module_order": module_order,
            "repository_structure": model_dump(validate_model(StructureContract, structure_payload)),
            "fact_ledger": model_dump(fact_ledger),
            "repository_facts": [],
            "modules": [model_dump(item) for item in bundles],
        },
    )


def _read_stage2_source_specs(task_input: PlannerTaskInput) -> list[Stage2SourceSpec]:
    source_specs: list[Stage2SourceSpec] = []
    for path in expand_markdown_inputs(task_input.spec_md_files):
        spec_path = Path(path).resolve()
        try:
            markdown = spec_path.read_text(encoding="utf-8")
        except Exception:
            markdown = ""
        source_specs.append(
            Stage2SourceSpec(
                path=str(spec_path),
                stem=spec_path.stem,
                markdown=markdown,
            )
        )
    return source_specs


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
