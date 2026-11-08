"""Offline restoration of a committed Stage5 bundle in the current case layout.

Never reconstruct planning or generation evidence from logs. Normal --resume
still verifies current per-task sources before reusing these restored aliases.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from zerorepo.rtl_impl.artifact_layout import ArtifactLayout, LAYOUT_VERSION
from zerorepo.rtl_impl.module_planner import PlannerRunner
from zerorepo.rtl_impl.module_planner.module_organizer import build_stage2_planning_input
from zerorepo.rtl_impl.module_planner.schemas import (
    ModuleOrganizationArtifact, ModulePlanArtifact, PlannerTaskInput, Stage1ContractsArtifact,
    Stage2DecompositionArtifact, Stage2RepoSkeletonArtifact,
    Stage3ModuleSkeletonArtifact, Stage4ModulePlansArtifact,
)
from zerorepo.rtl_impl.module_planner.utils import canonical_fingerprint
from zerorepo.rtl_impl.module_planner.utils.local_repair import fingerprint, REPAIR_POLICY_VERSION
from zerorepo.rtl_impl.module_planner.utils.responsibility_planning import artifact_content, module_context, planning_report
from zerorepo.rtl_impl.module_planner.utils.stage5_sources import SOURCE_VERSION
from zerorepo.rtl_impl.module_planner.utils.stage5_store import Stage5Store


def recover(output, module, *, apply=False):
    """Verify the active immutable bundle and optionally restore public aliases."""
    layout = ArtifactLayout(Path(output).resolve())
    run = json.loads((layout.case_root / 'run.json').read_text())
    if run.get('layout_version') != LAYOUT_VERSION:
        raise ValueError('Recovery requires the current RTL case layout')

    def read(model, name):
        return model.model_validate_json(layout.artifact(name).read_text())

    stage1 = read(Stage1ContractsArtifact, 'contracts.json')
    task = PlannerTaskInput(task_id=stage1.task_id, spec_md_files=stage1.fact_ledger.source_files)
    stage2_input = build_stage2_planning_input(stage1_artifact=stage1, task_input=task)
    decomposition = read(Stage2DecompositionArtifact, 'stage2_decomposition.json')
    repo = read(Stage2RepoSkeletonArtifact, 'repo_skeleton.json')
    modules = read(ModuleOrganizationArtifact, 'modules.json')
    stage3 = read(Stage3ModuleSkeletonArtifact, 'module_skeletons.json')
    stage4 = read(Stage4ModulePlansArtifact, 'module_plans.json')
    report = planning_report(layout.case_root, stage2_input, decomposition, repo, modules, stage3, stage4)
    if report['status'] != 'passed':
        raise ValueError(f"Planning gate failed before restoring Stage5: {report['errors']}")
    # Legacy derived text_grounding is compacted on disk. The original gate
    # fingerprint binds that projection; its authoritative RU/state contents
    # are rechecked above and against every source snapshot below.
    committed_gate = json.loads(layout.artifact('planning_gate_report.json').read_text())
    if committed_gate.get('status') != 'passed':
        raise ValueError('No committed successful planning gate')
    expected = canonical_fingerprint({
        'stage4': stage4, 'planning_gate_fingerprint': committed_gate['input_fingerprint'],
        'planning_bodies': artifact_content(layout.case_root, stage3, stage4),
        'repair_policy': REPAIR_POLICY_VERSION, 'pipeline_policy': PlannerRunner.PIPELINE_POLICY_VERSION,
    })
    marker = json.loads(layout.stage5_checkpoint(module).read_text())
    if marker.get('module') != module or marker.get('status') != 'completed':
        raise ValueError('Recovery requires a completed checkpoint for the requested module')
    if marker.get('task_id') != task.task_id or marker.get('input_fingerprint') != expected:
        raise ValueError('Stage5 bundle is not bound to the current planning inputs')
    store = Stage5Store(layout.case_root)
    store.validate(marker)
    plan_ref = next(r for r in stage4.module_plan_files if r.module == module)
    plan = ModulePlanArtifact.model_validate_json(layout.resolve(plan_ref.plan_file).read_text())
    skeleton_ref = next(r for r in stage3.module_records if r.module == module)
    document_hash = fingerprint(layout.resolve(skeleton_ref.export_file).read_text())
    refinement = module_context(decomposition, module)
    if [e['subtask_id'] for e in marker['subtasks']] != [t.id for t in plan.subtasks]:
        raise ValueError('Stage5 bundle does not cover the current module plan')
    for entry, subtask in zip(marker['subtasks'], plan.subtasks):
        if (entry.get('fingerprint_version') != SOURCE_VERSION
                or fingerprint(entry.get('source_snapshot')) != entry.get('source_fingerprint')
                or fingerprint(entry.get('artifact')) != entry.get('artifact_fingerprint')):
            raise ValueError('Stage5 source/artifact checksum mismatch')
        source = entry['source_snapshot']
        if (source.get('subtask') != subtask.model_dump()
                or source.get('skeleton_document') != document_hash
                or source.get('responsibility', {}).get('refinement') != refinement):
            raise ValueError('Stage5 responsibilities, obligations or tasks changed')
    if apply:
        store.restore_aliases(marker)
    return {'module': module, 'recovered_subtasks': len(marker['subtasks']), 'applied': apply,
            'planning_gate_verified': True, 'bundle_verified': True,
            'requires_resume_source_validation': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-root', type=Path, required=True, help='Case root containing run.json and plan/')
    parser.add_argument('--module', required=True)
    parser.add_argument('--apply', action='store_true', help='Restore fragment/contract aliases after verification')
    arguments = parser.parse_args()
    print(json.dumps(recover(arguments.output_root, arguments.module, apply=arguments.apply), ensure_ascii=False))
