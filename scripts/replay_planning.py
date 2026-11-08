#!/usr/bin/env python3
"""Explicit offline replay of captured exports; never a pipeline resume path."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from zerorepo.rtl_impl.module_planner.schemas import ModuleSkeletonExport
from zerorepo.rtl_impl.module_planner.utils.artifact_store import atomic_write_json, atomic_write_text
from zerorepo.rtl_impl.module_planner.utils.evidence import EvidenceRegistry
from zerorepo.rtl_impl.module_planner.utils.local_repair import fingerprint
from zerorepo.rtl_impl.module_planner.utils.responsibility_planning import module_context, refinement_issues
from zerorepo.rtl_impl.module_planner.utils.skeleton_json import compile_skeleton, render_skeleton
from zerorepo.rtl_impl.module_planner.utils.spec_mapping import module_spec_blocks
from zerorepo.rtl_impl.module_planner.utils.task_assembly import assemble_plan
from zerorepo.rtl_impl.module_planner.schemas import Stage2DecompositionArtifact, ModuleOrganizationArtifact
from zerorepo.rtl_impl.module_planner.module_organizer import build_stage2_planning_input_from_task
from zerorepo.rtl_impl.module_planner.schemas import PlannerTaskInput


def replay(source, output):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or source in output.parents or output in source.parents:
        raise ValueError('Use a separate replay directory; captured runs remain unchanged')
    decomposition = Stage2DecompositionArtifact.model_validate_json((source/'plan/stage2/stage2_decomposition.json').read_text())
    modules = ModuleOrganizationArtifact.model_validate_json((source/'plan/stage2/modules.json').read_text())
    sources = sorted({r.source_file for ru in decomposition.responsibilities for r in ru.source_refs})
    task = PlannerTaskInput(task_id=source.name, spec_md_files=sources)
    planning_input = build_stage2_planning_input_from_task(task_input=task)
    registry = EvidenceRegistry(planning_input)
    registry.register_tree(decomposition)
    records = []
    for path in sorted((source/'plan/stage3/modules').glob('*/skeleton.json')):
        name = path.parent.name
        record = {'module':name, 'captured_export_fingerprint':fingerprint(path.read_text())}
        try:
            export = ModuleSkeletonExport.model_validate_json(path.read_text())
            draft = {'module_frame':export.module_frame,
                'structural_blocks':[b.model_dump(exclude={'placeholder'}) for b in export.structural_blocks],
                'module_behavior':export.module_behavior.model_dump(), 'decision_ledger':export.decision_ledger.model_dump(),
                'behavioral_obligations':[]}
            for obligation in export.behavioral_obligations:
                item = obligation.model_dump(exclude={'clock_domain','reset_behavior','protocol'})
                item['source_evidence_ids'] = [registry.register(ref) for ref in item.pop('source_refs')]
                draft['behavioral_obligations'].append(item)
            context = module_context(decomposition, name)
            compiled = compile_skeleton(draft, module=name, source_refs=export.source_refs, context=context, registry=registry)
            issues = refinement_issues(compiled, context, planning_input)
            record.update(status='blocked' if issues else 'replayed', issues=[i.to_dict() for i in issues],
                          obligations=len(compiled.behavioral_obligations), blocks=len(compiled.structural_blocks))
            atomic_write_json(output/'modules'/name/'draft.json', draft)
            atomic_write_json(output/'modules'/name/'skeleton.json', compiled.model_dump())
            atomic_write_text(output/'modules'/name/'skeleton.md', render_skeleton(compiled))
            if not issues:
                bundle = next(m for m in modules.modules if m.module == name)
                spec = module_spec_blocks(compiled, context, bundle, EvidenceRegistry(planning_input))
                plan, refs = assemble_plan(compiled, spec)
                atomic_write_json(output/'modules'/name/'spec_blocks.json', spec.model_dump())
                atomic_write_json(output/'modules'/name/'plan.json', plan.model_dump())
                record['tasks'] = len(plan.subtasks)
        except (ValueError, OSError, KeyError, StopIteration) as exc:
            record.update(status='blocked', error=str(exc))
        records.append(record)
    selected = decomposition.selected_candidate()
    captured = {r['module'] for r in records}
    missing = [m.module for m in selected.modules if m.module not in captured]
    result = {'kind':'offline_captured_response_replay', 'real_model_acceptance':False,
        'source':str(source), 'status':'replayed' if records and not missing and all(r['status']=='replayed' for r in records) else 'blocked',
        'model_requests':0, 'missing_captured_modules':missing, 'modules':records}
    atomic_write_json(output/'replay_report.json', result)
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args=parser.parse_args()
    result=replay(args.source,args.output)
    print(json.dumps({'status':result['status'],'modules':len(result['modules']), 'report':str(args.output/'replay_report.json')}))
