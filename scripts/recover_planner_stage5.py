"""Offline, evidence-checked recovery. No model client or network is used."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zerorepo.rtl_impl.module_planner.agents.stage5_agent import Stage5Agent
from zerorepo.rtl_impl.module_planner.schemas import (
    ModulePlanArtifact, PlannerTaskInput, Stage2RepoSkeletonArtifact,
    Stage3ModuleSkeletonArtifact, Stage4ModulePlansArtifact, Stage4SpecBlocksArtifact, SubtaskCodeArtifact,
)
from zerorepo.rtl_impl.module_planner.utils.artifact_store import atomic_write_json
from zerorepo.rtl_impl.module_planner.utils.local_repair import fingerprint, REPAIR_POLICY_VERSION
from zerorepo.rtl_impl.module_planner.utils.stage5_sources import SOURCE_VERSION, Stage5LogEvidence, source_snapshot
from zerorepo.rtl_impl.module_planner.utils.stage5_store import Stage5Store
from zerorepo.rtl_impl.port_contracts import ansi_module_ports


def load_inputs(output):
    def read(name):
        return json.loads((output / name).read_text())
    return {"stage2": Stage2RepoSkeletonArtifact.model_validate(read("repo_skeleton.json")),
            "stage3": Stage3ModuleSkeletonArtifact.model_validate(read("module_skeletons.json")),
            "stage4": Stage4ModulePlansArtifact.model_validate(read("module_plans.json")),
            "spec_blocks": Stage4SpecBlocksArtifact.model_validate(read("spec_blocks.json")),
            "stage5_input_fingerprint": read("stage5_codegen.json")["input_fingerprint"]}


def recover(output, module, *, apply=False):
    output = Path(output).resolve()
    workspace = output.parent.parent / "workspace"
    log_path = output.parent.parent / "zerorepo.log"
    inputs = load_inputs(output)
    agent = Stage5Agent(None, output_root=output, workspace_root=workspace)
    plan_record = next(r for r in inputs["stage4"].module_plan_files if r.module == module)
    plan = ModulePlanArtifact.model_validate_json((output / plan_record.plan_file).read_text())
    spec = next(r for r in inputs["spec_blocks"].modules if r.module == module)
    task = PlannerTaskInput(task_id=inputs["stage2"].task_id, spec_md_files=[spec.source_spec_file])
    skeleton_record = next(r for r in inputs["stage3"].module_records if r.module == module)
    skeleton, _ = agent._read_module_skeleton_context(skeleton_record)
    repo_module = next(r for r in inputs["stage2"].modules if r.module == module)
    info = repo_module.model_dump()
    responsibility = {k: info[k] for k in ("module", "role", "rationale", "module_kind", "parents", "children", "module_decision") if k in info}
    for key in ("parents", "children"):
        if key in responsibility:
            responsibility[key] = sorted(responsibility[key] or [])
    children = []
    for child in sorted(info.get("children") or []):
        ports = ansi_module_ports((workspace / "merged" / f"{child}.v").read_text())
        children.append({"module": child, "ports": sorted([{"name": p.name, "direction": p.direction, "width": p.width} for p in ports], key=lambda p: p["name"])})
    text = log_path.read_text()
    fragment_sets = []
    for match in re.finditer(r"========== stage6_merge INPUT ==========(.*?)========== END stage6_merge INPUT ==========", text, re.S):
        body = match.group(1)
        first = re.search(r"(?m)^// STAGE5_SUBTASK_BEGIN " + re.escape(plan.subtasks[0].id) + r":", body)
        last = re.search(r"(?m)^// STAGE5_SUBTASK_END " + re.escape(plan.subtasks[-1].id) + r"\s*$", body)
        if first and last:
            fragment_sets.append(body[first.start():last.end()].rstrip() + "\n")
    contract_sets = []
    for match in re.finditer(r'"text": "((?:\\.|[^"\\])*)"', text):
        try:
            content = json.loads('"' + match.group(1) + '"')
            record = json.loads(content)
        except ValueError:
            continue
        if isinstance(record, dict) and record.get("kind") == "fragment_contracts" and record.get("module") == module:
            contract_sets.append(record.get("contracts", {}))
    if not fragment_sets or not contract_sets:
        raise ValueError("No complete historical fragments/contracts evidence")
    fragments = fragment_sets[-1]
    old_contracts = contract_sets[-1]
    sections = agent._fragment_sections(fragments)
    if list(sections) != [s.id for s in plan.subtasks] or [c["subtask_id"] for c in old_contracts["contracts"]] != list(sections):
        raise ValueError("Historical fragment/contract identities are incomplete")
    # Bind all historical fragments to the original Stage6 inputs, not merely
    # to their presence in a log or to a compilable merged file.
    # Calculate with historical bytes without writing a temporary formal artifact.
    spec_record = next(m for m in inputs["spec_blocks"].modules if m.module == module)
    original_key = fingerprint({"policy": REPAIR_POLICY_VERSION, "module": module, "fragments": fragments,
        "skeleton": (output / skeleton_record.doc_file).read_text(), "spec": spec_record,
        "children": {child: (workspace / "merged" / f"{child}.v").read_text() for child in info.get("children") or []}})
    stamp = json.loads((workspace / "merged" / f"{module}.inputs.json").read_text())
    if original_key != stamp["input_fingerprint"] or fingerprint((workspace / "merged" / f"{module}.v").read_text()) != stamp["merged_fingerprint"]:
        raise ValueError("Historical Stage6 source/result binding does not match")
    evidence = Stage5LogEvidence(log_path)
    prefix = ""
    entries = []
    contracts = []
    interfaces = agent._select_interface_spec_blocks(spec)
    for subtask, historical_contract in zip(plan.subtasks, old_contracts["contracts"]):
        artifact = SubtaskCodeArtifact(task_id=task.task_id, module=module, subtask_id=subtask.id,
            target=subtask.target, spec_refs=subtask.spec_refs, code=sections[subtask.id][2], contract=historical_contract["contract"])
        errors = agent._validate_subtask_code(artifact, task, module, subtask)
        errors.extend(i.message for i in agent._contract_quality_issues(artifact))
        if errors:
            raise ValueError(f"{subtask.id}: {errors}")
        selected = agent._select_spec_blocks(spec, subtask.spec_refs)
        extra = [b for b in interfaces if b["block_id"] not in subtask.spec_refs]
        compact_subtask = subtask.model_dump()
        compact_subtask.pop("timing_obligation_ids", None)
        compact_subtask.pop("logical_value_tags", None)
        macros = agent._build_stage5_global_defines_summary(relevant_texts=[json.dumps(compact_subtask, ensure_ascii=False, indent=2),
            skeleton, json.dumps(selected, ensure_ascii=False, indent=2), json.dumps(extra, ensure_ascii=False, indent=2), prefix])
        matching = None
        for fields in evidence.records.get((module, subtask.id), []):
            try:
                checks = [(json.loads(fields["CURRENT_SUBTASK"]), compact_subtask),
                          (fields["MODULE_SKELETON"], skeleton.strip()),
                          (json.loads(fields["SELECTED_SPEC_BLOCKS"]), selected),
                          (json.loads(fields["MODULE_INTERFACE_SPEC_BLOCKS"]), extra),
                          (fields["PREVIOUS_MODULE_SNIPPETS"], prefix.strip() or "None"),
                          (fields["GLOBAL_DEFINES_CONTEXT"], macros.strip() or "None")]
            except (KeyError, ValueError):
                continue
            if all(a == b for a, b in checks):
                matching = fields
                break
        if matching is None:
            raise ValueError(f"{subtask.id}: Historical authoritative source evidence does not match")
        legacy = {"policy": REPAIR_POLICY_VERSION, "task_id": task.task_id, "module": module, "subtask": subtask,
                  "skeleton": skeleton, "spec_blocks": selected, "interface_blocks": extra,
                  "previous_snippets": prefix, "global_defines": macros, "planning_kg": ""}
        snapshot = source_snapshot(legacy=legacy, responsibility=responsibility, child_interfaces=children,
                                   skeleton_document=(output / skeleton_record.doc_file).read_text())
        source_hash = fingerprint(snapshot)
        entries.append({"subtask_id": subtask.id, "input_fingerprint": source_hash, "fingerprint_version": SOURCE_VERSION,
            "source_fingerprint": source_hash, "source_snapshot": snapshot, "artifact": artifact.model_dump(),
            "artifact_fingerprint": fingerprint(artifact.model_dump()), "migration_evidence": {
                "kind": "complete_stage6_log_bundle", "log": str(log_path), "stage6_input_fingerprint": original_key}})
        contracts.append(agent._contract_entry(artifact=artifact, subtask=subtask))
        prefix = agent._upsert_subtask_section(prefix, subtask, artifact.code)
    if prefix != fragments or contracts != old_contracts["contracts"]:
        raise ValueError("Reconstructed artifacts do not reproduce the historical bundle")
    if apply:
        saved = agent._read_checkpoint(module, task.task_id)
        if saved:
            preserved = Stage5Store(workspace).bundle(saved, agent._workspace_file(module).read_text(), json.loads(agent._contracts_file(module).read_text()))
            atomic_write_json(workspace / ".stage5_history" / module / f"{fingerprint(saved)}.json", preserved)
        agent._commit_subtasks(module_name=module, task_id=task.task_id, entries=entries, fragments=prefix,
            contracts=contracts, input_fingerprint=inputs["stage5_input_fingerprint"], complete=True)
    return {"module": module, "recovered_subtasks": len(entries), "applied": apply, "historical_stage6_binding_verified": True}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--module", required=True)
    parser.add_argument("--apply", action="store_true")
    arguments = parser.parse_args()
    print(json.dumps(recover(arguments.output_root, arguments.module, apply=arguments.apply), ensure_ascii=False))
