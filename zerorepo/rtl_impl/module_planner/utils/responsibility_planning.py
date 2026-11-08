"""Deterministic responsibility/refinement checks shared by all planning stages.

These checks establish traceability, not behavioral equivalence to the spec.
Legacy artifacts are readable by schemas, but only v2 artifacts pass the gate.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from zerorepo.rtl_impl.artifact_layout import ArtifactLayout, LAYOUT_VERSION

from ..schemas import BlockBehaviorOverlay
from .local_repair import ArtifactIssue, fingerprint


POLICY_VERSION = "responsibility_refinement_v2_harness"


def source_documents(planning_input):
    documents = {}
    for source in planning_input.source_specs:
        path = Path(source.path).resolve()
        try:
            documents[str(path)] = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        except OSError:
            documents[str(path)] = None
    return documents


def _sections(text):
    stack, paths, fenced = [], [], False
    for line in text.splitlines():
        if re.match(r"^\s*(```|~~~)", line):
            fenced = not fenced
        match = None if fenced else re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        bold = None if fenced else re.fullmatch(r"\*\*((\d+(?:\.\d+)*)\.?\s+[^*]+)\*\*", line.strip())
        if match or bold:
            level, title = (len(match[1]), match[2]) if match else (bold[2].count(".") + 1, bold[1])
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
        paths.append(" > ".join(title for _, title in stack))
    return paths


def verify_source(ref, documents):
    """Validate exact text and bind program-computed provenance in place."""
    path = str(Path(ref.source_file).resolve())
    if path not in documents:
        raise ValueError(f"source_file is outside input specifications: {ref.source_file}")
    text = documents[path]
    if text is None:
        raise ValueError(f"source_file cannot be read: {path}")
    quote = ref.quote.replace("\r\n", "\n")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if ref.content_hash and ref.content_hash != digest:
        raise ValueError(f"source content_hash changed: {path}")
    sections = _sections(text)
    occurrences, offset = [], 0
    while quote and (at := text.find(quote, offset)) >= 0:
        start = text.count("\n", 0, at) + 1
        end = start + quote.count("\n")
        section = sections[start - 1] if start <= len(sections) else ""
        if ((not ref.start_line or ref.start_line == start)
                and (not ref.end_line or ref.end_line == end)
                and (not ref.section_path or section == ref.section_path
                     or section.endswith(" > " + ref.section_path))):
            occurrences.append((start, end, section))
        offset = at + 1
    if len(occurrences) != 1:
        raise ValueError(f"quote must resolve exactly once using section/lines; found {len(occurrences)} in {path}")
    ref.source_file, ref.quote, ref.content_hash = path, quote, digest
    ref.start_line, ref.end_line, ref.section_path = occurrences[0]


def ledger_issues(ledger, planning_input):
    """Report the entity that must change, rather than every entity mentioned.

    In particular, a missing commit is an error in the owning RU's access
    list. The state table supplies context, but must not become a repair target
    merely because its ID appears in the diagnostic.
    """
    issues, documents = [], source_documents(planning_input)
    group, identity = "", ""

    def error(message, *, target=None, field="", code="invalid_ledger", **expected):
        target_group, target_id = target if target is not None else (group, identity)
        path = f"{target_group}[{target_id}]" if target_group else "ledger"
        if field:
            path += "." + field
        issues.append(ArtifactIssue(path, code, message, category="hardware",
                                   unit_id=target_id, expected=expected or None))

    for source in planning_input.source_specs:
        if documents.get(str(Path(source.path).resolve())) != source.markdown.replace("\r\n", "\n"):
            error(f"source {source.path}: changed since the planning input snapshot")
    rus = {r.responsibility_id: r for r in ledger.responsibilities}
    if len(rus) != len(ledger.responsibilities):
        error("responsibility IDs must be unique")
    states = {s.state_id: s for s in ledger.state_objects}
    if len(states) != len(ledger.state_objects):
        error("state_object IDs must be unique")
    if len({s.name for s in ledger.state_objects}) != len(ledger.state_objects):
        error("state_object names must be unambiguous; use qualified logical names")
    dependency_ids = set()
    fact_ids = {f.fact_id for f in planning_input.fact_ledger.facts}
    for ru in ledger.responsibilities:
        prefix = ru.responsibility_id
        group, identity = "responsibilities", prefix
        if not set(ru.evidence_fact_ids) <= fact_ids:
            error(f"{prefix}: unknown evidence_fact_ids")
        if not ru.source_refs:
            error(f"{prefix}: source_refs must contain verified original text")
        for ref in ru.source_refs:
            try:
                verify_source(ref, documents)
            except ValueError as exc:
                error(f"{prefix}: source_refs: {exc}")
        if not ru.ownership_required:
            if not ru.applies_to_responsibility_ids:
                error(f"{prefix}: non-owned constraint requires applies_to_responsibility_ids")
        for target in ru.applies_to_responsibility_ids:
            if target not in rus or not rus[target].ownership_required:
                error(f"{prefix}: invalid constraint target {target}")
        expected = sorted(s.name for s in states.values() if s.owner_responsibility_id == prefix)
        if sorted(ru.owned_state) != expected:
            error(f"{prefix}: owned_state must match state_objects ownership {expected}", field="owned_state")
        for access in ru.state_accesses:
            if access.state_id not in states:
                error(f"{prefix}: unknown state {access.state_id}", field="state_accesses")
            elif access.role in {"commit", "reset", "hold"} and states[access.state_id].owner_responsibility_id != prefix:
                error(f"{prefix}: cannot {access.role} another responsibility's state {access.state_id}", field="state_accesses")
        for dep in ru.dependencies:
            missing = {"dependency_kind", "partition_constraint"} - dep.model_fields_set
            if missing:
                error(f"{prefix}: dependency must explicitly declare {sorted(missing)}", field="dependencies")
            if not dep.dependency_id or dep.dependency_id in dependency_ids:
                error(f"{prefix}: dependency_id must be nonempty and globally unique", field="dependencies")
            dependency_ids.add(dep.dependency_id)
            if dep.target_responsibility_id not in rus or dep.target_responsibility_id == prefix:
                error(f"{prefix}: invalid dependency target {dep.target_responsibility_id}", field="dependencies")
            if dep.dependency_kind in {"data", "control"} and not dep.transferred_objects:
                error(f"{prefix}: {dep.dependency_id} requires transferred_objects", field="dependencies")
            if dep.dependency_kind == "state" and (not dep.transferred_objects or not set(dep.transferred_objects) <= set(states)):
                error(f"{prefix}: state dependency must reference known state IDs", field="dependencies")
            if dep.dependency_kind == "temporal" and dep.timing_relation in {"", "unspecified"}:
                error(f"{prefix}: temporal dependency requires timing_relation", field="dependencies")
    for state in states.values():
        group, identity = "state_objects", state.state_id
        owner = rus.get(state.owner_responsibility_id)
        if owner is None or not owner.ownership_required:
            error(f"state {state.state_id}: invalid owner {state.owner_responsibility_id}", field="owner_responsibility_id")
        if owner is not None and (state.state_id, "commit") not in {(a.state_id, a.role) for a in owner.state_accesses}:
            error(f"state {state.state_id}: owner {owner.responsibility_id} requires an explicit commit access in state_accesses",
                  target=("responsibilities", owner.responsibility_id), field="state_accesses", code="missing_state_commit",
                  state_id=state.state_id, owner_responsibility_id=owner.responsibility_id,
                  required_access={"state_id": state.state_id, "role": "commit"})
        if not state.source_refs:
            error(f"state {state.state_id}: source_refs must not be empty")
        for ref in state.source_refs:
            try:
                verify_source(ref, documents)
            except ValueError as exc:
                error(f"state {state.state_id}: {exc}")
    return issues


def ledger_errors(ledger, planning_input):
    """String diagnostics retained for the gate and existing public callers."""
    return [issue.message for issue in ledger_issues(ledger, planning_input)]


def module_context(decomposition, module):
    candidate = decomposition.selected_candidate()
    assigned = next((m.responsibility_ids for m in candidate.modules if m.module == module), []) if candidate else []
    owned = [r for r in decomposition.responsibilities if r.responsibility_id in assigned and r.ownership_required]
    ids = {r.responsibility_id for r in owned}
    constraints = [r for r in decomposition.responsibilities if not r.ownership_required
                   and ids.intersection(r.applies_to_responsibility_ids)]
    boundary_ids = {identity for contract in decomposition.selected_boundary_contracts
                    if module in {contract.producer_module, contract.consumer_module}
                    for identity in [*contract.producer_responsibility_ids, *contract.consumer_responsibility_ids]}
    return {
        "module": module,
        "boundary_source_refs": [ref.model_dump() for r in decomposition.responsibilities
                                 if r.responsibility_id in boundary_ids for ref in r.source_refs],
        "responsibilities": [r.model_dump() for r in owned],
        "constraints": [r.model_dump() for r in constraints],
        "state_objects": [s.model_dump() for s in decomposition.state_objects],
    }


def derive_overlays(export):
    """Obligation mappings are authoritative; textual overlays are commentary."""
    by_block = {o.block_id: o for o in export.block_behavior_overlays}
    for block in export.structural_blocks:
        overlay = by_block.get(block.block_id)
        if overlay is None:
            overlay = BlockBehaviorOverlay(block_id=block.block_id)
            export.block_behavior_overlays.append(overlay)
        primary = [o for o in export.behavioral_obligations if o.implementation_block_id == block.block_id]
        supporting = [o for o in export.behavioral_obligations if block.block_id in o.supporting_block_ids]
        overlay.obligation_ids = [o.obligation_id for o in primary]
        overlay.supporting_obligation_ids = [o.obligation_id for o in supporting]
        overlay.responsibility_ids = sorted({o.parent_responsibility_id for o in [*primary, *supporting]})


def refinement_issues(export, context, planning_input):
    issues = []
    def error(code, message, ru="", obligation="", block="", **details):
        issues.append(ArtifactIssue("behavioral_obligations", code, message, category="hardware",
                                   section="Behavioral Overlay", unit_id=obligation or block,
                                   module=export.module, stage="stage3", expected={"responsibility": ru, "block": block, **details}))
    rus = {r["responsibility_id"]: r for r in context["responsibilities"]}
    constraints = {r["responsibility_id"]: r for r in context["constraints"]}
    states = {s["state_id"]: s for s in context["state_objects"]}
    blocks = {b.block_id: b for b in export.structural_blocks}
    obligations = export.behavioral_obligations
    if len({o.obligation_id for o in obligations}) != len(obligations):
        error("duplicate_obligation", "obligation IDs must be unique within module")
    covered, constraint_coverage, commit_blocks = set(), set(), {}
    documents = source_documents(planning_input)
    for o in obligations:
        ru = rus.get(o.parent_responsibility_id)
        def fail(code, message, **details):
            error(code, message, o.parent_responsibility_id, o.obligation_id, o.implementation_block_id, **details)
        if ru is None:
            fail("unknown_responsibility", f"{o.obligation_id}: parent responsibility is not owned by module",
                 allowed_responsibility_ids=sorted(rus))
        # Block/delegation/support checks do not depend on a valid parent.
        # Report them now instead of hiding them behind unknown_responsibility.
        block = blocks.get(o.implementation_block_id)
        if block is None or block.block_kind in {"decl", "meta"}:
            fail("invalid_implementation_block", f"{o.obligation_id}: requires a behavioral implementation block")
        elif block.block_kind == "inst" and o.behavior_kind != "integration":
            fail("invalid_delegation", f"{o.obligation_id}: instance block can only implement local integration obligations",
                 implementation_block_kind="inst", required_behavior_kind="integration",
                 alternatives="Use integration for a local integration duty, or select an appropriate non-instance behavioral block")
        elif ru is not None:
            covered.add(o.parent_responsibility_id)
        if len(set(o.supporting_block_ids)) != len(o.supporting_block_ids) or o.implementation_block_id in o.supporting_block_ids:
            fail("invalid_support", f"{o.obligation_id}: support blocks must be distinct from primary block")
        for support in o.supporting_block_ids:
            if support not in blocks:
                fail("unknown_block", f"{o.obligation_id}: unknown supporting block {support}")
        for access in o.state_accesses:
            if access.state_id not in states:
                fail("unknown_state", f"{o.obligation_id}: unknown state {access.state_id}")
            if access.role in {"commit", "reset", "hold"} and (block is None or block.block_kind != "seq"):
                fail("state_commit_kind", f"{o.obligation_id}: persistent state mutation requires seq block")
        if ru is None:
            continue
        for field_name in ("clock_domain", "reset_behavior", "protocol"):
            inherited = ru.get(field_name) or "unspecified"
            actual = getattr(o, field_name)
            if actual in {"", "unspecified"}:
                setattr(o, field_name, inherited)
            elif actual != inherited:
                fail("contract_drift", f"{o.obligation_id}: {field_name} must preserve the parent RU contract",
                     field=field_name, required_value=inherited)
        if o.timing_relation in {"", "unspecified"}:
            o.timing_relation = ru.get("timing_class") or "unspecified"
        for constraint in o.constraint_refs:
            item = constraints.get(constraint)
            if item is None or o.parent_responsibility_id not in item["applies_to_responsibility_ids"]:
                fail("unknown_constraint", f"{o.obligation_id}: invalid constraint reference {constraint}", constraint=constraint)
            else:
                constraint_coverage.add((constraint, o.parent_responsibility_id))
        parent_refs = [*ru["source_refs"], *[ref for c in o.constraint_refs if c in constraints
                       and o.parent_responsibility_id in constraints[c]["applies_to_responsibility_ids"]
                       for ref in constraints[c]["source_refs"]]]
        for ref in o.source_refs:
            try:
                verify_source(ref, documents)
                if ref.model_dump() not in parent_refs:
                    fail("unbound_source", f"{o.obligation_id}: source must be inherited from parent RU or applicable constraint",
                         allowed_source_refs=parent_refs)
            except ValueError as exc:
                fail("invalid_source", f"{o.obligation_id}: {exc}", allowed_source_refs=parent_refs)
        for access in o.state_accesses:
            state = states.get(access.state_id)
            if state is None:
                continue
            allowed = {(a["state_id"], a["role"]) for a in ru["state_accesses"]}
            if (access.state_id, access.role) not in allowed:
                fail("unauthorized_state_access", f"{o.obligation_id}: state access {access.state_id}/{access.role} is absent from parent RU",
                     actual_access=access.model_dump(), allowed_state_accesses=ru["state_accesses"])
            if access.role in {"commit", "reset", "hold"}:
                if state["owner_responsibility_id"] != o.parent_responsibility_id:
                    fail("state_owner_conflict", f"{o.obligation_id}: foreign state mutation {access.state_id}", actual_access=access.model_dump())
                commit_blocks.setdefault(access.state_id, set()).add(o.implementation_block_id)
    for ru in sorted(set(rus) - covered):
        error("uncovered_responsibility", f"{ru}: no implementing behavioral obligation", ru=ru)
    for constraint, item in constraints.items():
        for ru in sorted(set(item["applies_to_responsibility_ids"]) & set(rus)):
            if (constraint, ru) not in constraint_coverage:
                error("uncovered_constraint", f"{constraint}: no obligation for applicable responsibility {ru}", ru=ru, constraint=constraint)
    for state in states.values():
        if state["owner_responsibility_id"] not in rus:
            continue
        writers = commit_blocks.get(state["state_id"], set())
        if len(writers) != 1:
            error("state_commit_conflict", f"state {state['state_id']}: requires exactly one submitting block; found {sorted(writers)}", ru=state["owner_responsibility_id"], state=state["state_id"])
        accesses = {(a.state_id, a.role) for o in obligations if o.parent_responsibility_id == state["owner_responsibility_id"] for a in o.state_accesses}
        expected = {(a["state_id"], a["role"]) for a in rus[state["owner_responsibility_id"]]["state_accesses"] if a["state_id"] == state["state_id"]}
        if not expected <= accesses or (state["state_id"], "commit") not in accesses:
            error("uncovered_state_access", f"state {state['state_id']}: declared state access/commit obligations are missing", ru=state["owner_responsibility_id"], state=state["state_id"])
    if export.schema_version == "module_skeleton_export_v3":
        labels = set()
        for block in export.structural_blocks:
            if block.block_label in labels:
                error("duplicate_block_label", f"{block.block_id}: duplicate block_label {block.block_label}", block=block.block_id)
            labels.add(block.block_label)
            if block.placeholder != f"<block: {block.block_label}>":
                error("placeholder_drift", f"{block.block_id}: placeholder differs from program-derived block label", block=block.block_id)
        accessed = {a["state_id"] for r in context["responsibilities"] for a in r["state_accesses"]}
        expected_states = [s for s in context["state_objects"] if s["owner_responsibility_id"] in rus or s["state_id"] in accessed]
        if [s.model_dump() for s in export.state_objects] != expected_states:
            error("state_binding_drift", "skeleton state objects differ from the authoritative state table")
        active = {o.implementation_block_id for o in obligations} | {key for o in obligations for key in o.supporting_block_ids}
        for block in export.structural_blocks:
            if block.block_id not in active:
                error("unmapped_block", f"{block.block_id}: block needs a primary or supporting obligation mapping", block=block.block_id,
                      ru=next(iter(rus), ""))
        expected_overlay = export.model_copy(deep=True)
        derive_overlays(expected_overlay)
        if [o.model_dump() for o in expected_overlay.block_behavior_overlays] != [o.model_dump() for o in export.block_behavior_overlays]:
            error("overlay_drift", "block overlays differ from the authoritative obligation mapping")
    return issues


def ordered_blocks(export):
    """Stable topological order for code-generation dependencies only."""
    pending, done, result = list(export.structural_blocks), set(), []
    ids = {b.block_id for b in pending}
    while pending:
        block = next((b for b in pending if set(b.depends_on) <= done), None)
        if block is None:
            raise ValueError("structural block generation dependencies contain a cycle or unknown reference")
        if not set(block.depends_on) <= ids:
            raise ValueError("unknown block dependency")
        pending.remove(block)
        done.add(block.block_id)
        result.append(block)
    return result


def task_metadata(export):
    result = {}
    for block in ordered_blocks(export):
        primary = [o for o in export.behavioral_obligations if o.implementation_block_id == block.block_id]
        support = [o for o in export.behavioral_obligations if block.block_id in o.supporting_block_ids]
        obligations = [*primary, *support]
        accesses = []
        for o in obligations if block.block_kind not in {"decl", "meta"} else []:
            for a in o.state_accesses:
                # Auxiliary logic can read or compute a next value; only the
                # primary implementing block inherits mutation obligations.
                if o not in primary and a.role not in {"read", "compute_next"}:
                    continue
                if a.model_dump() not in accesses:
                    accesses.append(a.model_dump())
        result[f"{block.block_id}_{block.block_label}"] = {
            "responsibility_ids": sorted({o.parent_responsibility_id for o in obligations}),
            "obligation_ids": [o.obligation_id for o in primary],
            "supporting_obligation_ids": [o.obligation_id for o in support],
            "depends_on_task_ids": [f"{d}_{next(b.block_label for b in export.structural_blocks if b.block_id == d)}" for d in block.depends_on],
            "constraint_refs": sorted({c for o in obligations for c in o.constraint_refs}),
            "task_contract": {"state_accesses": accesses,
                "state_objects": [s.model_dump() for s in export.state_objects
                                  if s.state_id in {a.state_id for o in obligations for a in o.state_accesses}],
                "obligations": [o.model_dump() for o in obligations], "support_only": not bool(primary)},
        }
    return result


def task_errors(plan, export):
    expected = task_metadata(export)
    errors = []
    if [t.id for t in plan.subtasks] != list(expected):
        errors.append("subtasks must exactly match stable topological block order")
    for task in plan.subtasks:
        if task.id not in expected:
            errors.append(f"{task.id}: unknown task")
            continue
        actual = task.model_dump()
        for key, value in expected[task.id].items():
            if actual[key] != value:
                errors.append(f"{task.id}: {key} differs from authoritative Stage3 mapping")
    return errors


def plan_sidecar_errors(root, plan, export, document, spec_blocks):
    """Use the same task/target/spec checks for generation, resume and gating."""
    import json
    from zerorepo.rtl_impl.retrieval_agent import BlockSpecRetrievalResult
    retrieval_path = ArtifactLayout(root).module(4, plan.module, "spec_refs.json")
    retrieval = BlockSpecRetrievalResult.model_validate(json.loads(retrieval_path.read_text()))
    from .task_assembly import assemble_plan
    module_spec = next(m for m in spec_blocks.modules if m.module == plan.module)
    expected_plan, expected_refs = assemble_plan(export, module_spec)
    errors = task_errors(plan, export)
    if plan.model_dump() != expected_plan.model_dump():
        errors.append("task body differs from deterministic Stage3 assembly")
    if retrieval.model_dump() != expected_refs:
        errors.append("spec reference evidence mapping differs from deterministic assembly")
    return errors


def artifact_content(root, stage3=None, stage4=None):
    """Hash bodies, not just manifest paths; missing bodies fail closed."""
    paths = []
    if stage3:
        paths.extend(path for r in stage3.module_records for path in (r.export_file, r.spec_context_file) if path)
    if stage4:
        paths.extend(r.plan_file for r in stage4.module_plan_files)
    return {name: Path(root, name).read_text(encoding="utf-8") for name in paths}


def planning_report(root, planning_input, decomposition, repo, modules, stage3, stage4):
    """Re-read every sidecar and verify the entire plan before any code reuse."""
    import json
    from ..schemas import ModuleSkeletonExport, ModulePlanArtifact, Stage4SpecBlocksArtifact
    from .skeleton_json import render_skeleton

    errors, risks, bodies = [], [], {}
    counts = {"required_responsibilities": sum(r.ownership_required for r in decomposition.responsibilities),
              "covered_responsibilities": 0, "state_objects": len(decomposition.state_objects),
              "modules": len(repo.modules), "obligations": 0, "blocks": 0, "tasks": 0}
    def add(code, message, stage="planning_gate", module="", **identity):
        errors.append({"code": code, "message": message, "stage": stage, "module": module, **identity})
    spec_blocks = None
    try:
        bodies["spec_blocks.json"] = ArtifactLayout(root).artifact("spec_blocks.json").read_text(encoding="utf-8")
        spec_blocks = Stage4SpecBlocksArtifact.model_validate_json(bodies["spec_blocks.json"])
    except (OSError, ValueError) as exc:
        add("invalid_spec_blocks", str(exc), "stage4")
    for message in ledger_errors(decomposition, planning_input):
        add("invalid_responsibility_ledger", message, "stage2", responsibility_id=message.split(":", 1)[0])
    versions = ((decomposition, "stage2_decomposition_v2"), (repo, "repo_skeleton_v2"),
                (modules, "module_contracts_v2"), (stage3, "stage3_skeleton_json_v3"), (stage4, "module_plans_v3"))
    for artifact, version in versions:
        if artifact.schema_version != version:
            add("legacy_artifact", f"requires {version}; found {artifact.schema_version}")
    candidate = decomposition.selected_candidate()
    if decomposition.status not in {"selected", "selected_with_degradation"}:
        add("incomplete_architecture", "Stage2 has not completed architecture selection", "stage2")
    if candidate is None:
        add("missing_selected_candidate", "Stage2 has no selected architecture", "stage2")
    else:
        from ..agents.stage2_agent import Stage2Agent
        # Pure evaluator: no model requests, persistence, or context providers.
        evaluation = Stage2Agent.__new__(Stage2Agent)._evaluate_candidate(
            candidate=candidate, locked_top=decomposition.locked_top,
            responsibilities=decomposition.responsibilities, stage2_input=planning_input)
        for message in evaluation.fatal_violations:
            add("invalid_architecture", message, "stage2")
        risks.extend(evaluation.hard_violations + evaluation.warnings)
        if [b.model_dump() for b in candidate.boundary_contracts] != [b.model_dump() for b in decomposition.selected_boundary_contracts]:
            add("boundary_drift", "selected_boundary_contracts differ from selected candidate", "stage2")
        if set(m.module for m in candidate.modules) != set(m.module for m in repo.modules):
            add("module_drift", "repository modules differ from selected candidate", "stage2")
        if repo.top_module != candidate.top_module or {(e.parent, e.child) for e in repo.global_invariants.hierarchy} != {(e.parent, e.child) for e in candidate.hierarchy}:
            add("hierarchy_drift", "repository hierarchy/top differ from selected candidate", "stage2")
    order = repo.planning_decisions.generation_order
    if (stage3.module_order != order or stage4.module_order != order
            or stage3.completed_modules != order or stage4.completed_modules != order):
        add("incomplete_modules", "Stage3/Stage4 must cover all selected modules in generation order")
    records = {r.module: r for r in stage3.module_records}
    plans = {r.module: r for r in stage4.module_plan_files}
    bundles = {m.module: m for m in modules.modules}
    covered = set()
    for module in repo.modules:
        name = module.module
        context = module_context(decomposition, name)
        expected_ru = [r["responsibility_id"] for r in context["responsibilities"]]
        expected_constraints = [r["responsibility_id"] for r in context["constraints"]]
        for item in (module, bundles.get(name)):
            if (item is None or sorted(item.responsibility_ids) != sorted(expected_ru)
                    or sorted(item.applicable_constraint_ids) != sorted(expected_constraints)):
                add("ownership_drift", "module RU/constraint assignments differ from selected architecture", "stage2", name)
        bundle = bundles.get(name)
        if bundle is not None:
            expected_sources = [ref for r in context["responsibilities"] + context["constraints"] for ref in r["source_refs"]]
            if [ref.model_dump() for ref in bundle.responsibility_source_refs] != expected_sources:
                add("module_evidence_drift", "module sources differ from assigned responsibility evidence", "stage2", name)
        try:
            record, plan_record = records[name], plans[name]
            if str(Path(record.source_refs.module_spec_file).resolve()) not in source_documents(planning_input):
                add("invalid_module_source", "module primary source is outside current input specifications", "stage3", name)
            for relative in (record.export_file, record.spec_context_file, plan_record.plan_file):
                if relative:
                    bodies[relative] = Path(root, relative).read_text(encoding="utf-8")
            export = ModuleSkeletonExport.model_validate(json.loads(bodies[record.export_file]))
            plan = ModulePlanArtifact.model_validate(json.loads(bodies[plan_record.plan_file]))
            from .skeleton_json import spec_context_view
            from .evidence import EvidenceRegistry
            expected_context = spec_context_view(EvidenceRegistry(planning_input), context, export).model_dump()
            if json.loads(bodies[record.spec_context_file]) != expected_context:
                add("source_context_drift", "module source context differs from verified assignments", "stage3", name)
            if spec_blocks is not None and bundle is not None:
                from .spec_mapping import module_spec_blocks
                from .evidence import EvidenceRegistry
                expected_spec = module_spec_blocks(export, context, bundle, EvidenceRegistry(planning_input))
                actual_spec = next((m for m in spec_blocks.modules if m.module == name), None)
                if actual_spec is None or expected_spec.model_dump() != actual_spec.model_dump():
                    add("spec_evidence_drift", "specification text or evidence mapping differs from verified sources", "stage4", name)
            if export.schema_version != "module_skeleton_export_v3" or plan.schema_version != "module_plan_v3":
                add("legacy_sidecar", "enhanced planning requires v3 skeleton and task sidecars", module=name)
            if export.module != name or plan.module != name:
                add("module_identity", "sidecar module identity differs from manifest", module=name)
            canonical = render_skeleton(export)
            doc_path = Path(root, record.doc_file)
            if not doc_path.exists() or doc_path.read_text(encoding="utf-8") != canonical:
                from .artifact_store import atomic_write_text
                atomic_write_text(Path(root, record.doc_file), canonical)
            bodies.pop(record.doc_file, None)
            from ..agents.stage3_agent import Stage3Agent
            checker = Stage3Agent.__new__(Stage3Agent)
            for message in checker._validate_export(export, expected_module=name,
                    expected_spec_path=record.source_refs.module_spec_file):
                add("invalid_skeleton", message, "stage3", name)
            from ..utils import ansi_module_ports, interface_contract_errors
            ports = checker._authoritative_ports(bundle, record.source_refs.module_spec_file) if bundle else []
            for message in interface_contract_errors(ansi_module_ports(export.module_frame), ports, label=name) if ports else []:
                add("interface_drift", message, "stage3", name)
            issues = refinement_issues(export, context, planning_input)
            for issue in issues:
                identity = issue.expected or {}
                add(issue.code, issue.message, "stage3", name, responsibility_id=identity.get("responsibility", ""),
                    obligation_id=issue.unit_id, block_id=identity.get("block", ""), path=issue.path)
            retrieval_file = ArtifactLayout(root).module_relative(4, name, "spec_refs.json")
            bodies[retrieval_file] = Path(root, retrieval_file).read_text(encoding="utf-8")
            messages = plan_sidecar_errors(root, plan, export, canonical, spec_blocks) if spec_blocks else task_errors(plan, export)
            for message in messages:
                add("task_metadata_drift", message, "stage4", name, task_id=message.split(":", 1)[0])
            for task in plan.subtasks:
                if task.timing_obligation_ids or task.logical_value_tags:
                    add("retired_timing_fields", "retired temporal fields must remain empty", "stage4", name, task_id=task.id)
            counts["obligations"] += len(export.behavioral_obligations)
            counts["blocks"] += len(export.structural_blocks)
            counts["tasks"] += len(plan.subtasks)
            covered.update(o.parent_responsibility_id for o in export.behavioral_obligations
                           if o.parent_responsibility_id in expected_ru and o.implementation_block_id in {b.block_id for b in export.structural_blocks if b.block_kind not in {"decl", "meta"}})
        except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
            add("invalid_sidecar", str(exc), module=name)
    counts["covered_responsibilities"] = len(covered)
    risks.extend(repo.open_issues)
    return {"schema_version": "planning_gate_v1", "status": "failed" if errors else "passed",
            "input_fingerprint": fingerprint({"layout_version": LAYOUT_VERSION, "policy": POLICY_VERSION, "decomposition": decomposition,
                "repo": repo, "modules": modules, "stage3": stage3, "stage4": stage4, "bodies": bodies, "sources": source_documents(planning_input)}),
            "counts": counts, "errors": errors, "risks": list(dict.fromkeys(risks))}
