"""Compile model-owned design into the authoritative skeleton and its read view."""
from __future__ import annotations
import json
from ..schemas import ModuleSkeletonExport
from ..schemas.skeleton_draft import ModuleSkeletonDraft
from .responsibility_planning import derive_overlays


def contract_context(bundle):
    """Reference derived facts; full original evidence and RU contracts are inputs.

    In-memory bundles retain full fact anchors even when their persisted view
    is compact. Repeating those anchors can dwarf the actual module design.
    The digest binds all omitted fact bodies to checkpoint identity. This
    prompt-only projection never changes the authoritative bundle.
    """
    from .local_repair import fingerprint
    value = bundle.model_dump()
    digest = fingerprint(value)
    facts = value.pop("facts", [])
    value["fact_ids"] = [fact["fact_id"] for fact in facts if fact.get("fact_id")]
    value["canonical_contract_fingerprint"] = digest
    value["fact_context"] = (
        "Facts are provenance references here. Design from the complete EV source text, assigned RUs, "
        "state objects, interface contract and boundary contracts; do not duplicate child responsibilities.")
    return value


def repair_context(context, scope, issues=None):
    """Repair against full original evidence and RU contracts, not duplicate facts."""
    from copy import deepcopy
    value = deepcopy(context)
    contract = value.get("module_contract", {})
    if "facts" in contract:
        facts = contract.pop("facts")
        contract["fact_ids"] = [fact["fact_id"] for fact in facts if fact.get("fact_id")]
    contract["fact_context"] = (
        "Derived fact bodies are omitted for this entity repair. Use the complete EV evidence catalog "
        "and assigned responsibility contracts; all original source text remains available.")
    return value


def design_repair_context(context, scope, issues):
    """Broaden evidence for source errors; retain the module slice otherwise."""
    needs_sources = any(issue.category == "source" or issue.code in {
        "unknown_evidence", "source_not_inherited", "unbound_source", "invalid_source", "missing_source",
    } for issue in issues)
    return repair_context(context if needs_sources else design_context(context, scope), scope)


def design_context(context, scope):
    """Supply the module's sources, including adjacent text in their sections.

    Every referenced EV remains expanded in full. The complete context remains
    the checkpoint input; the full catalog is available again on repair, so a
    missing upstream source association can still be resolved exactly.
    """
    from copy import deepcopy
    value = deepcopy(context)
    catalog = value.get("evidence_catalog", {})
    entries = catalog.get("entries", [])
    required = set()

    def visit(item):
        if isinstance(item, dict):
            if isinstance(item.get("evidence_ref"), str):
                required.add(item["evidence_ref"])
            if isinstance(item.get("source_evidence_ids"), list):
                required.update(item["source_evidence_ids"])
            for key, child in item.items():
                if key != "evidence_catalog":
                    visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)

    visit(value)
    if not required:
        return value
    by_id = {entry["id"]: entry for entry in entries}
    unknown = required - by_id.keys()
    if unknown:
        raise ValueError(f"Module context cites evidence absent from catalog: {sorted(unknown)}")
    sections = {(by_id[key].get("file_id"), by_id[key].get("section_id")) for key in required}
    selected = [entry for entry in entries if entry["id"] in required
                or (entry.get("file_id"), entry.get("section_id")) in sections]
    catalog["entries"] = selected
    for dictionary, field in (("files", "file_id"), ("sections", "section_id")):
        used = {entry.get(field) for entry in selected}
        catalog[dictionary] = {key: item for key, item in catalog.get(dictionary, {}).items() if key in used}
    catalog["context_scope"] = (
        "Complete sources referenced by this module's RUs, states, constraints, interface and boundaries, "
        "plus text in those same source sections. Unrelated system sections are omitted from this design request. "
        "A repair request supplies the full catalog if further evidence associations are needed.")
    return value


def design_candidate_context(candidate, scope):
    """Expand editable obligations; retain cross-obligation ownership as an index.

    This is a reading view only. The session always persists, merges and checks
    the full candidate, including every unchanged effect and evidence binding.
    """
    from copy import deepcopy
    value = deepcopy(candidate)
    if scope.get("full") or "obligation_ids" not in scope:
        return value
    selected = set(scope["obligation_ids"])
    parents = set(scope.get("responsibility_ids", []))
    obligations = value.get("behavioral_obligations", [])
    value["behavioral_obligations"] = [o for o in obligations
        if o.get("obligation_id") in selected or o.get("parent_responsibility_id") in parents]
    value["preserved_obligation_index"] = [
        {key: o[key] for key in ("obligation_id", "parent_responsibility_id", "behavior_kind",
         "implementation_block_id", "supporting_block_ids", "state_accesses", "constraint_refs") if key in o}
        for o in obligations if o not in value["behavioral_obligations"]]
    value["reading_note"] = (
        "preserved_obligation_index is READ ONLY context, not a design field. Full unchanged obligations "
        "remain saved and are revalidated after merge. Return only repair_scope replacement entities; "
        "never emit this index or reading_note. Module frame and all blocks remain visible for integration.")
    if len(json.dumps(value, ensure_ascii=False, separators=(",", ":"))) >= len(json.dumps(candidate, ensure_ascii=False, separators=(",", ":"))):
        return deepcopy(candidate)
    return value


def evidence_context(registry, context):
    result = {"module": context["module"]}
    for group in ("responsibilities", "constraints", "state_objects"):
        result[group] = []
        for original in context[group]:
            if group == "state_objects":
                referenced = {a["state_id"] for ru in context["responsibilities"] for a in ru["state_accesses"]}
                owners = {ru["responsibility_id"] for ru in context["responsibilities"]}
                if original["state_id"] not in referenced and original["owner_responsibility_id"] not in owners:
                    continue
            item = dict(original)
            item["source_evidence_ids"] = [registry.register(ref) for ref in item.pop("source_refs", [])]
            result[group].append(item)
    return result


def compile_skeleton(draft, *, module, source_refs, context, registry):
    value = ModuleSkeletonDraft.model_validate(draft)
    responsibilities = {r["responsibility_id"]: r for r in context["responsibilities"]}
    obligations = []
    for obligation in value.behavioral_obligations:
        ru = responsibilities.get(obligation.parent_responsibility_id, {})
        item = obligation.model_dump()
        identities = item.pop("source_evidence_ids")
        item["source_refs"] = registry.expand(identities)
        # Scope/ownership remains checked by refinement_issues, with precise
        # obligation diagnostics instead of reparsing a second document format.
        for key in ("clock_domain", "reset_behavior", "protocol"):
            item[key] = ru.get(key) or "unspecified"
        obligations.append(item)
    blocks = []
    for block in value.structural_blocks:
        item = block.model_dump()
        item["placeholder"] = f"<block: {block.block_label}>"
        blocks.append(item)
    decisions = value.decision_ledger.model_dump()
    if not decisions["chosen_decisions"]:
        decisions["chosen_decisions"] = [{"topic": "Responsibility refinement", "decision": "Use the listed structural blocks",
                                           "reason": "Implement the module's assigned responsibilities and obligations"}]
    export = ModuleSkeletonExport.model_validate({"schema_version": "module_skeleton_export_v3", "module": module,
        "file_path": f"generate/rtl/{module}.v", "source_refs": source_refs.model_dump(),
        "module_frame": value.module_frame, "structural_blocks": blocks,
        "module_behavior": value.module_behavior.model_dump(), "decision_ledger": decisions,
        "state_objects": [state for state in context["state_objects"] if state["owner_responsibility_id"] in responsibilities
                          or state["state_id"] in {a["state_id"] for r in context["responsibilities"] for a in r["state_accesses"]}],
        "behavioral_obligations": obligations})
    derive_overlays(export)
    return export


def render_skeleton(export):
    """Five-section human view; never parsed as planning authority."""
    def dump(value):
        return json.dumps(value, ensure_ascii=False, indent=2)
    return (f"# MODULE_SKELETON_DOC v3\n\n## 0. Module Identity\n"
            f"- module_name: {export.module}\n- file_path: {export.file_path}\n\n"
            f"## 1. Module Frame\n```verilog\n{export.module_frame}\n```\n\n"
            "## 2. Structural Skeleton\n" + "\n".join(
                f"### {b.block_id}: {b.block_label}\n- block_kind: {b.block_kind}\n- purpose: {b.purpose}\n"
                f"- code_shape: {b.code_shape}\n- depends_on: {dump(b.depends_on)}\n{b.placeholder}\n"
                for b in export.structural_blocks)
            + "\n## 3. Behavioral Overlay\n### Module Behavior Summary\n```json\n"
            + dump(export.module_behavior.model_dump()) + "\n```\n\n### Behavioral Obligations\n```json\n"
            + dump([o.model_dump() for o in export.behavioral_obligations])
            + "\n```\n\n### Block Behavioral Overlay\n```json\n"
            + dump([o.model_dump() for o in export.block_behavior_overlays])
            + "\n```\n\n## 4. Decision Ledger\n```json\n" + dump(export.decision_ledger.model_dump()) + "\n```\n")


def spec_context_view(registry, context, export):
    """Rebuild the source context from verified assignments and obligations."""
    from zerorepo.rtl_impl.retrieval_agent.schemas import ModuleSpecContextRetrievalResult, ModuleSpecContextBlock
    identities = {registry.register(ref) for group in ("responsibilities", "constraints")
                  for responsibility in context[group] for ref in responsibility["source_refs"]}
    identities.update(registry.register(ref) for obligation in export.behavioral_obligations for ref in obligation.source_refs)
    return ModuleSpecContextRetrievalResult(module=export.module,
        blocks=[ModuleSpecContextBlock(block_id=f"S{i:03d}", text=registry.entries[key].quote,
            source_file=registry.entries[key].source_file, source_chunk_ids=[key],
            source_ranges=[registry.entries[key].model_dump(exclude={"quote"})],
            relevance_reason=["Assigned responsibility or applicable constraint evidence"])
            for i, key in enumerate(sorted(identities), 1)])
