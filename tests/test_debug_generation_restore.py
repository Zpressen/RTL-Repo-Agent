import json
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_planner_local_repair import stage5_inputs
from test_rtl_module_planner import QueueBackend, make_stage5_code_payload
from zerorepo.rtl_impl.codex_debug.history import debug_binding, tree_manifest
from zerorepo.rtl_impl.module_planner.agents import Stage5Agent
from zerorepo.rtl_impl.module_planner.planner_runner import PlannerRunner
from zerorepo.rtl_impl.module_planner.schemas import Stage2RepoSkeletonArtifact, Stage4ModulePlansArtifact, Stage4SpecBlocksArtifact
from zerorepo.rtl_impl.module_planner.utils import PlannerLLMClient
from zerorepo.rtl_impl.module_planner.utils.local_repair import fingerprint


@pytest.fixture
def saved_generation(tmp_path, monkeypatch):
    task, output, inputs, subtasks = stage5_inputs(tmp_path, count=1)
    Path(task.spec_md_files[0]).write_text('toy system specification\n')
    plan = json.loads((output/'module_plan_json/toy.json').read_text())
    leaf_plan = {**plan, 'module':'leaf'}
    (output/'module_plan_json/leaf.json').write_text(json.dumps(leaf_plan))
    stage4 = inputs['stage4']
    stage4['module_order']=['leaf','toy']
    stage4['module_plan_files'].insert(0, {'module':'leaf','plan_file':'module_plan_json/leaf.json'})
    inputs['stage4']=Stage4ModulePlansArtifact.model_validate(stage4)
    specs = inputs['spec_blocks']
    specs['module_order']=['leaf','toy']
    specs['modules'].insert(0, {**specs['modules'][0], 'module':'leaf'})
    inputs['spec_blocks']=Stage4SpecBlocksArtifact.model_validate(specs)
    inputs['stage2']=Stage2RepoSkeletonArtifact(task_id=task.task_id,top_module='toy',module_order=['leaf','toy'],
        modules=[{'module':'leaf','kind':'leaf_combinational','parents':['toy']},
                 {'module':'toy','kind':'top_controller','children':['leaf']}])
    backend=QueueBackend([make_stage5_code_payload(task.task_id,n,subtasks[0],'assign y0 = a;') for n in ['leaf','toy']])
    logger=logging.getLogger('generation-test');logger.setLevel(logging.CRITICAL)
    stage5=Stage5Agent(PlannerLLMClient(backend=backend),output_root=output,logger=logger)
    workspace=stage5.workspace_root
    merged=workspace/'merged';merged.mkdir(parents=True,exist_ok=True)
    original={'leaf.v':'module leaf(input a, output y); assign y=a; endmodule\n',
              'toy.v':'module toy(input a, output y); leaf u(a,y); endmodule\n'}
    for n,s in original.items():(merged/n).write_text(s)
    records={n:stage5.run_module(task,inputs,n) for n in ['leaf','toy']}
    runner=PlannerRunner.__new__(PlannerRunner)
    runner.output_root=output;runner.stage5=stage5;runner.logger=logging.getLogger('generation-test')
    runner.stage6=SimpleNamespace(_merged_file=lambda n:merged/f'{n}.v',_ensure_toolchain_path=lambda:None)
    for n,r in records.items():
        runner._stage6_cache_path(n).write_text(json.dumps({'input_fingerprint':runner._stage6_reuse_key(n,r,inputs),
            'merged_fingerprint':fingerprint((merged/f'{n}.v').read_text())}))
    private=workspace/'debug_system/toy/codex_private'
    origin=private/'launcher_baseline/merged';origin.mkdir(parents=True)
    for n,s in original.items():(origin/n).write_text(s)
    accepted=private/'accepted_baseline/merged';accepted.mkdir(parents=True)
    fixed={'leaf.v':'module leaf(input a, output [1:0] y); assign y={a,a}; endmodule\n',
           'toy.v':'module toy(input a, output y); wire [1:0] t; leaf u(a,t); assign y=t[0]; endmodule\n'}
    for n,s in fixed.items():
        (accepted/n).write_text(s);(merged/n).write_text(s)
    verifier=tmp_path/'oracle/verify.py';verifier.parent.mkdir()
    verifier.write_text('def verify_system(path): return False, "FAIL"\n')
    descriptor={'run_id':'same-run','top_module':'toy','spec_text':'spec','contract_json':'{}','verify_script':str(verifier)}
    (private/'run_descriptor.json').write_text(json.dumps(descriptor))
    (private/'session_state.json').write_text(json.dumps({'run_id':'same-run','accepted_manifest':tree_manifest(accepted)}))
    (private/'run_record.json').write_text(json.dumps({'run_id':'same-run','binding':debug_binding(top_module='toy',
        spec_text='spec',spec_paths=task.spec_md_files,contract_json='{}',verify_script=verifier)}))
    monkeypatch.setattr('zerorepo.rtl_impl.module_planner.planner_runner._check_single_file_syntax',lambda *a,**kw:(True,'ok'))
    return runner,task,inputs,private,merged,backend


def test_debug_modified_interfaces_reuse_original_stage5_sources_and_fixed_rtl(saved_generation):
    runner,task,inputs,private,merged,backend=saved_generation
    with pytest.raises(ValueError,match='stale'):
        runner.stage5.run_module(task,inputs,'toy',reuse_only=True)
    before={n:h for n,h in tree_manifest(merged).items() if n.endswith('.v')}
    result=runner._restore_debug_generation(task,inputs)
    assert set(result)=={'leaf','toy'} and len(backend.calls)==2
    assert {n:h for n,h in tree_manifest(merged).items() if n.endswith('.v')}==before
    for n,r in result.items():
        assert runner._reuse_stage6_merge_if_valid(n,r,inputs) is not None
    # A later native invocation overwrites launcher_baseline; the immutable
    # original generation still supplies the old dependency contract.
    for p in (private/'accepted_baseline/merged').iterdir():
        (private/'launcher_baseline/merged'/p.name).write_bytes(p.read_bytes())
    assert runner._restore_debug_generation(task,inputs)
    assert {n:h for n,h in tree_manifest(merged).items() if n.endswith('.v')}==before


@pytest.mark.parametrize('change',['spec','plan','source','accepted_corrupt','manual_rtl','origin_corrupt','binding_corrupt','force_rebuild'])
def test_debug_restore_rejects_source_changes_and_corruption_without_overwriting_rtl(saved_generation,change):
    runner,task,inputs,private,merged,backend=saved_generation
    if change in ['origin_corrupt','binding_corrupt']:
        assert runner._restore_debug_generation(task,inputs)
    if change=='spec':inputs['spec_blocks'].modules[0].blocks[0].text+='Changed requirement'
    elif change=='plan':
        p=runner.output_root/'module_plan_json/leaf.json';v=json.loads(p.read_text())
        v['subtasks'][0]['constraints']=['changed'];p.write_text(json.dumps(v))
    elif change=='source':Path(task.spec_md_files[0]).write_text('changed source')
    elif change=='accepted_corrupt':(private/'accepted_baseline/merged/leaf.v').write_text('corrupt')
    elif change=='manual_rtl':(merged/'leaf.v').write_text('manual edit outside lineage')
    elif change=='origin_corrupt':(runner._debug_generation_origin/'leaf.v').write_text('corrupt')
    elif change=='binding_corrupt':
        p=runner._debug_generation_binding_path();v=json.loads(p.read_text());v['source_fingerprint']='wrong';p.write_text(json.dumps(v))
    else:runner._allow_debug_generation_reuse=False
    before=tree_manifest(merged)
    assert runner._restore_debug_generation(task,inputs) is None
    assert tree_manifest(merged)==before and len(backend.calls)==2


def test_accepted_change_after_interrupt_restores_only_verified_lineage(saved_generation):
    runner,task,inputs,private,merged,_=saved_generation
    assert runner._restore_debug_generation(task,inputs)
    accepted=private/'accepted_baseline/merged'
    (accepted/'leaf.v').write_text((accepted/'leaf.v').read_text().replace('{a,a}','{~a,~a}'))
    p=private/'session_state.json';v=json.loads(p.read_text());v['accepted_manifest']=tree_manifest(accepted);p.write_text(json.dumps(v))
    assert runner._restore_debug_generation(task,inputs)
    assert (merged/'leaf.v').read_bytes()==(accepted/'leaf.v').read_bytes()


def test_publish_failure_stops_before_remerge_and_can_resume(saved_generation,monkeypatch):
    runner,task,inputs,private,merged,_=saved_generation
    from zerorepo.rtl_impl.module_planner import planner_runner as module
    write=module.atomic_write_json
    def interrupted(path,value):
        if str(path).endswith('.inputs.json'):raise OSError('interrupted publish')
        write(path,value)
    with monkeypatch.context() as patch:
        patch.setattr(module,'atomic_write_json',interrupted)
        with pytest.raises(RuntimeError,match='retained for retry'):
            runner._restore_debug_generation(task,inputs)
    assert runner._restore_debug_generation(task,inputs)
