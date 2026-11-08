"""Deterministic block-to-task and evidence-to-spec mappings."""
from __future__ import annotations
from ..schemas import ModulePlanArtifact
from .evidence import evidence_id
from .responsibility_planning import ordered_blocks, task_metadata


def assemble_plan(export, module_spec):
    metadata = task_metadata(export)
    by_evidence = {}
    for spec in module_spec.blocks:
        for identity in spec.source_evidence_ids:
            by_evidence.setdefault(identity, []).append(spec.block_id)
    tasks, selections = [], []
    for block in ordered_blocks(export):
        key = f"{block.block_id}_{block.block_label}"
        data = metadata[key]
        evidence = {evidence_id(ref) for o in data['task_contract']['obligations'] for ref in o['source_refs']}
        # Declarations support module interface and storage. Their evidence is
        # structural context, never counted as behavioral implementation.
        if block.block_kind in {"decl", "meta"}:
            evidence.update(identity for spec in module_spec.blocks if spec.declaration_support for identity in spec.source_evidence_ids)
        if block.block_kind == "inst":
            evidence.update(identity for spec in module_spec.blocks if spec.integration_support for identity in spec.source_evidence_ids)
        refs = [spec.block_id for spec in module_spec.blocks if set(spec.source_evidence_ids) & evidence]
        missing = evidence - set(by_evidence)
        if missing or not refs:
            raise ValueError(f"{export.module}/{key}: no complete legal specification mapping; missing={sorted(missing)}")
        tasks.append({"id": key, "target": block.placeholder, "description": block.purpose,
                      "spec_refs": refs, "constraints": [], **data})
        selections.append({"id": key, "target": block.placeholder, "spec_refs": refs,
                           "selection_reason": ["Deterministic obligation and declaration evidence mapping"]})
    return ModulePlanArtifact.model_validate({"schema_version": "module_plan_v3", "module": export.module, "subtasks": tasks}), {
        "schema_version": "block_spec_retrieval_v1", "module": export.module, "selections": selections,
        "fallback_used": False, "fallback_reason": ""}
