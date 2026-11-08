"""Native JSON design, entity feedback, deterministic tasks and JSON recovery."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from test_responsibility_refinement import scenario, report
from test_planning_harness import RaisingBackend
from zerorepo.rpg_gen.base.llm_client.errors import LLMRequestTimeoutError
from zerorepo.rtl_impl.module_planner.agents import Stage3Agent
from zerorepo.rtl_impl.module_planner.schemas import ModuleSkeletonExport, SpecBlock, ModuleSpecBlocks
from zerorepo.rtl_impl.module_planner.schemas.skeleton_draft import ModuleSkeletonDraft
from zerorepo.rtl_impl.module_planner.utils import PlannerLLMClient
from zerorepo.rtl_impl.module_planner.utils.evidence import EvidenceRegistry, evidence_id
from zerorepo.rtl_impl.module_planner.utils.local_repair import ArtifactIssue
from zerorepo.rtl_impl.module_planner.utils.planning_session import PlanningSession, merge_entities, ledger_scope
from zerorepo.rtl_impl.module_planner.utils.responsibility_planning import module_context, refinement_issues, task_metadata
from zerorepo.rtl_impl.module_planner.utils.skeleton_json import compile_skeleton, render_skeleton, contract_context, repair_context
from zerorepo.rtl_impl.module_planner.utils.task_assembly import assemble_plan


@pytest.fixture(scope='module')
def planned(tmp_path_factory):
    return scenario(tmp_path_factory.mktemp('native_planning'))


def draft_from_export(export):
    obligations = []
    for obligation in export.behavioral_obligations:
        item = obligation.model_dump(exclude={'clock_domain', 'reset_behavior', 'protocol'})
        item['source_evidence_ids'] = [evidence_id(ref) for ref in item.pop('source_refs')]
        obligations.append(item)
    return {'module_frame': export.module_frame,
            'structural_blocks': [b.model_dump(exclude={'placeholder'}) for b in export.structural_blocks],
            'behavioral_obligations': obligations, 'module_behavior': export.module_behavior.model_dump(),
            'decision_ledger': export.decision_ledger.model_dump()}


def design_fixture(planned):
    task, runner, _, inputs, stage3, _ = planned
    record = stage3.module_records[0]
    export = ModuleSkeletonExport.model_validate_json((runner.output_root / record.export_file).read_text())
    registry = EvidenceRegistry(inputs['stage2_input'])
    registry.register_tree(inputs['stage2_decomposition'])
    context = module_context(inputs['stage2_decomposition'], export.module)
    def validate(payload):
        try:
            draft = ModuleSkeletonDraft.model_validate(payload)
            for obligation in draft.behavioral_obligations:
                registry.expand(obligation.source_evidence_ids)
            candidate = compile_skeleton(payload, module=export.module, source_refs=record.source_refs,
                                         context=context, registry=registry)
            return candidate, refinement_issues(candidate, context, inputs['stage2_input'])
        except ValueError as exc:
            return None, [ArtifactIssue('design', 'invalid_structure', str(exc), category='structure')]
    return task, draft_from_export(export), validate


def session(root, task, responses, resume=False, policy=None):
    backend = RaisingBackend(responses)
    client = PlannerLLMClient(backend=backend)
    client.configure_execution(root, policy)
    client.executor.begin_run(task, resume=resume)
    return backend, PlanningSession(Stage3Agent(client, output_root=root))


def test_stage4_uses_no_model_and_tasks_are_exact(planned):
    _, runner, backend, _, stage3, stage4 = planned
    stages = json.loads((runner.output_root / 'plan/metrics.json').read_text())['stages']
    assert not any(key.startswith('stage4') for key in stages)
    assert not backend.responses
    for record, plan_record in zip(stage3.module_records, stage4.module_plan_files):
        export = ModuleSkeletonExport.model_validate_json((runner.output_root / record.export_file).read_text())
        plan = json.loads((runner.output_root / plan_record.plan_file).read_text())
        metadata = task_metadata(export)
        for task, block in zip(plan['subtasks'], [next(b for b in export.structural_blocks if key == b.block_id+'_'+b.block_label) for key in metadata]):
            assert task['description'] == block.purpose and task['constraints'] == []
            assert all(task[key] == value for key, value in metadata[task['id']].items())


def test_stage3_contract_view_references_facts_and_binds_their_complete_contents(planned):
    bundle = planned[3]['modules'].modules[0]
    original = bundle.model_dump()
    projected = contract_context(bundle)
    assert bundle.model_dump() == original
    assert projected['fact_ids'] == [fact['fact_id'] for fact in original['facts'] if fact.get('fact_id')]
    assert 'facts' not in projected
    assert projected['responsibility_source_refs'] == original['responsibility_source_refs']
    assert projected['interface_contract'] == original['interface_contract']
    changed = bundle.model_copy(deep=True)
    changed.facts[0].notes += 'Changed fact body with the same ID'
    assert contract_context(changed)['canonical_contract_fingerprint'] != projected['canonical_contract_fingerprint']
    assert repair_context({'module_contract': projected}, {})['module_contract']['fact_ids'] == projected['fact_ids']


def test_repair_context_retains_all_evidence_and_contracts_without_duplicate_fact_bodies():
    context = {'evidence_catalog': {'entries': [{'id': 'EV_A', 'text': 'all original behavior'}]},
               'assigned': {'responsibilities': ['RU_A'], 'state_objects': ['ST_A']},
               'boundary_contracts': ['BC_A'], 'schema': {'type': 'object'},
               'module_contract': {'interface_contract': {'ports': ['clk']},
                                   'facts': [{'fact_id': 'F1', 'object': {'behavior': 'large derived detail'}}]}}
    original = deepcopy(context)
    view = repair_context(context, {})
    assert context == original
    for key in ['evidence_catalog', 'assigned', 'boundary_contracts', 'schema']:
        assert view[key] == context[key]
    assert view['module_contract']['interface_contract'] == context['module_contract']['interface_contract']
    assert view['module_contract']['fact_ids'] == ['F1'] and 'facts' not in view['module_contract']


def test_repair_can_resume_under_prompt_budget_without_regenerating_saved_candidate(planned, tmp_path):
    task, valid, validate = design_fixture(planned)
    bad = deepcopy(valid); bad['behavioral_obligations'][0]['implementation_block_id'] = 'UNKNOWN'
    context = {'module_contract': {'facts': [{'fact_id': 'F1', 'object': {'padding': 'x' * 12000}}]},
               'evidence_catalog': {'entries': []}, 'assigned': {}}
    from zerorepo.rtl_impl.module_planner.utils.execution import PlanningBudgetExceeded
    root = tmp_path / 'case'
    backend, run = session(root, task, [bad], policy={'max_prompt_chars': 14000})
    with pytest.raises(PlanningBudgetExceeded):
        run.execute(module='toy', prompt='design', context=context, validate=validate)
    assert len(backend.calls) == 1
    backend, resumed = session(root, task, [{'behavioral_obligations': [valid['behavioral_obligations'][0]]}],
                               resume=True, policy={'max_prompt_chars': 14000})
    result = resumed.execute(module='toy', prompt='design', context=context, validate=validate,
                             repair_context=repair_context)
    assert result.status == 'validated' and len(backend.calls) == 1
    assert 'VALIDATION RESULT' in backend.calls[0]['user_prompt']
    assert 'x' * 100 not in backend.calls[0]['user_prompt']


@pytest.mark.parametrize('mutate', ['unknown', 'duplicate', 'escaped_quote'])
def test_evidence_registry_is_one_exact_protocol(tmp_path, mutate):
    from zerorepo.rtl_impl.module_planner.module_organizer import build_stage2_planning_input_from_task
    from zerorepo.rtl_impl.module_planner.schemas import PlannerTaskInput, SourceEvidence
    path = tmp_path / 'spec.md'; path.write_text('# AMO\n| AMOOR | `original \\| i_rs2` |\n\n# B\nrepeat\n\n# C\nrepeat\n')
    task = PlannerTaskInput(task_id='amo', spec_md_files=[str(path)])
    registry = EvidenceRegistry(build_stage2_planning_input_from_task(task_input=task))
    identity = registry.register(SourceEvidence(source_file=str(path), quote='| AMOOR | `original \\| i_rs2` |'))
    assert identity.startswith('EV_')
    assert registry.expand([identity])[0]['quote'] == '| AMOOR | `original \\| i_rs2` |'
    with pytest.raises(ValueError):
        if mutate == 'unknown': registry.expand(['REF_unknown'])
        elif mutate == 'duplicate': registry.expand([identity, identity])
        else: registry.register(SourceEvidence(source_file=str(path), quote='| AMOOR | `original | i_rs2` |'))


def test_timeout_resumes_saved_json_entities_without_regeneration(planned, tmp_path):
    task, valid, validate = design_fixture(planned)
    bad = deepcopy(valid); bad['behavioral_obligations'][0]['source_evidence_ids'] = ['EV_unknown']
    # A semantic source error gives a targeted entity scope (not raw quote repair).
    def check(payload):
        if payload['behavioral_obligations'][0]['source_evidence_ids'] == ['EV_unknown']:
            return None, [ArtifactIssue('behavioral_obligations', 'invalid_evidence', 'Select allowed EV IDs', category='source', unit_id='OB_COMMIT')]
        return validate(payload)
    root = tmp_path / 'case'
    old, run = session(root, task, [bad, LLMRequestTimeoutError('repair timed out')])
    with pytest.raises(LLMRequestTimeoutError):
        run.execute(module='toy', prompt='design', context={}, validate=check)
    checkpoint = next((root/'plan/state/execution').glob('*.json'))
    saved = json.loads(checkpoint.read_text())
    assert saved['candidate'] == bad and saved['api_attempts'] == 2
    backend, resumed = session(root, task, [{'behavioral_obligations': [valid['behavioral_obligations'][0]]}], resume=True)
    result = resumed.execute(module='toy', prompt='design', context={}, validate=check)
    assert result.status == 'validated' and len(backend.calls) == 1
    assert 'repair_scope' in backend.calls[0]['user_prompt']
    assert result.candidate['structural_blocks'] == valid['structural_blocks']
    assert json.loads(checkpoint.read_text())['api_attempts'] == 3


def test_more_than_three_content_rounds_share_one_node_budget(planned, tmp_path):
    task, valid, validate = design_fixture(planned)
    bad = deepcopy(valid)
    for item in bad['behavioral_obligations']: item['parent_responsibility_id'] = 'RU_unknown'
    responses = [bad]
    for item in valid['behavioral_obligations']:
        responses.append({'behavioral_obligations': [item]})
    backend, run = session(tmp_path / 'case', task, responses)
    result = run.execute(module='toy', prompt='design', context={}, validate=validate)
    assert result.status == 'validated' and len(backend.calls) == 5


def test_illegal_repair_cannot_corrupt_candidate(planned, tmp_path):
    task, valid, validate = design_fixture(planned)
    bad = deepcopy(valid); bad['behavioral_obligations'][0]['implementation_block_id'] = 'UNKNOWN'
    backend, run = session(tmp_path/'case', task, [bad, {'module_frame': 'changed'}, {'behavioral_obligations': [valid['behavioral_obligations'][0]]}])
    result = run.execute(module='toy', prompt='design', context={}, validate=validate)
    assert result.status == 'validated'
    assert result.candidate['module_frame'] == valid['module_frame']
    assert len(backend.calls) == 3


def test_stalled_json_returns_needs_repair_and_persists(planned, tmp_path):
    task, valid, validate = design_fixture(planned)
    bad = deepcopy(valid); bad['behavioral_obligations'][0]['implementation_block_id'] = 'UNKNOWN'
    backend, run = session(tmp_path/'case', task, [bad, {}, {}])
    result = run.execute(module='toy', prompt='design', context={}, validate=validate)
    assert result.status == 'needs_repair' and len(backend.calls) == 3
    state = json.loads(next((tmp_path/'case/plan/state/execution').glob('*.json')).read_text())
    assert state['status'] == 'needs_repair' and state['candidate'] == bad


def test_stage2_repair_replaces_only_identified_entity():
    original = {'responsibilities': [{'responsibility_id':'R1','description':'keep'}, {'responsibility_id':'R2','description':'fix'}], 'state_objects':[]}
    issues = [ArtifactIssue('responsibilities[R2].source_evidence_ids','invalid_evidence','bad', category='source')]
    scope = ledger_scope(original, issues)
    repaired = merge_entities(original, {'responsibilities':[{'responsibility_id':'R2','description':'fixed'}]}, scope)
    assert repaired['responsibilities'][0] == original['responsibilities'][0]
    with pytest.raises(ValueError, match='Untargeted'):
        merge_entities(original, {'responsibilities':[{'responsibility_id':'R1','description':'wrong'}]}, scope)


def test_every_chunk_for_selected_evidence_is_kept_and_no_all_spec_fallback(planned):
    task, draft, validate = design_fixture(planned)
    export, issues = validate(draft); assert not issues
    sources = {evidence_id(ref.model_dump()) for o in export.behavioral_obligations for ref in o.source_refs}
    blocks = [SpecBlock(block_id=f'S{i+1:03d}', text='part', source_evidence_ids=[key]) for i,key in enumerate(sorted(sources))]
    first = blocks[0].source_evidence_ids
    blocks.append(SpecBlock(block_id=f'S{len(blocks)+1:03d}', text='another part', source_evidence_ids=first))
    blocks.append(SpecBlock(block_id=f'S{len(blocks)+1:03d}', text='irrelevant', source_evidence_ids=['EV_irrelevant']))
    spec = ModuleSpecBlocks(module=export.module, source_spec_file='spec.md', blocks=blocks)
    plan, refs = assemble_plan(export, spec)
    assert not refs['fallback_used']
    for task in plan.subtasks:
        assert blocks[-1].block_id not in task.spec_refs
        if blocks[0].block_id in task.spec_refs: assert blocks[-2].block_id in task.spec_refs
    for block in spec.blocks: block.source_evidence_ids = ['EV_foreign']
    with pytest.raises(ValueError, match='no complete legal'):
        assemble_plan(export, spec)


def test_markdown_view_drift_does_not_invalidate_json_or_gate(tmp_path):
    case = scenario(tmp_path)
    task, runner, backend, _, stage3, _ = case
    before = report(case)['input_fingerprint']
    record = stage3.module_records[0]
    path = runner.output_root / record.doc_file
    path.write_text('hand edited view')
    count = len(backend.calls)
    runner.run(task, resume=True, end_stage='stage4')
    assert len(backend.calls) == count and report(case)['input_fingerprint'] == before
    export = ModuleSkeletonExport.model_validate_json((runner.output_root/record.export_file).read_text())
    assert path.read_text() == render_skeleton(export)
    path.unlink()
    assert report(case)['status'] == 'passed' and path.exists()


@pytest.mark.parametrize('field', ['text','source_evidence_ids'])
def test_gate_rechecks_actual_spec_block_text_and_ids(tmp_path, field):
    case = scenario(tmp_path)
    runner = case[1]
    path = runner.layout.artifact('spec_blocks.json')
    value = json.loads(path.read_text()); value['modules'][0]['blocks'][0][field] = 'invented' if field == 'text' else ['EV_unknown']
    path.write_text(json.dumps(value))
    result = report(case)
    assert result['status'] == 'failed' and any(e['code'] == 'spec_evidence_drift' for e in result['errors'])


def test_scoped_obligation_repair_protects_other_obligations_of_same_ru():
    from zerorepo.rtl_impl.module_planner.utils.planning_session import entity_scope
    value = {'behavioral_obligations':[{'obligation_id':'A','parent_responsibility_id':'R'}, {'obligation_id':'B','parent_responsibility_id':'R'}], 'structural_blocks':[]}
    issue = ArtifactIssue('behavioral_obligations','unbound_source','A is invalid',unit_id='A',category='source',expected={'responsibility':'R'})
    scope = entity_scope(value,[issue])
    assert scope['obligation_ids'] == ['A']
    with pytest.raises(ValueError,match='Untargeted'):
        merge_entities(value, {'behavioral_obligations':[{'obligation_id':'B','parent_responsibility_id':'other'}]},scope)


def test_completed_response_journal_replays_after_validation_crash(planned, tmp_path):
    task, valid, validate = design_fixture(planned)
    def crash(payload):
        raise RuntimeError('process stopped after response fsync')
    root = tmp_path/'case'
    _, run = session(root,task,[valid])
    with pytest.raises(RuntimeError):
        run.execute(module='toy', prompt='design', context={}, validate=crash)
    backend, resumed = session(root,task,[],resume=True)
    result = resumed.execute(module='toy', prompt='design', context={}, validate=validate)
    assert result.status == 'validated' and backend.calls == []


def test_budget_exhaustion_retains_last_design(planned, tmp_path):
    from zerorepo.rtl_impl.module_planner.utils.execution import PlanningBudgetExceeded
    task, valid, validate = design_fixture(planned)
    bad = deepcopy(valid); bad['behavioral_obligations'][0]['parent_responsibility_id']='unknown'
    backend, run = session(tmp_path/'case',task,[bad],policy={'max_api_attempts':1})
    with pytest.raises(PlanningBudgetExceeded, match='candidate and'):
        run.execute(module='toy',prompt='design',context={},validate=validate)
    state=json.loads(next((tmp_path/'case/plan/state/execution').glob('*.json')).read_text())
    assert state['status']=='failed' and state['candidate']==bad and len(backend.calls)==1


def test_stage_template_fingerprint_is_scoped(monkeypatch):
    from zerorepo.rtl_impl.module_planner.utils.execution import template_fingerprint
    from pathlib import Path
    read = Path.read_text
    before = {s: template_fingerprint(s) for s in ('stage1','stage2','stage3','stage4')}
    def changed(path,*args,**kwargs):
        value=read(path,*args,**kwargs)
        return value+'\n# stage4 template changed' if path.name=='stage4_module_plan.py' else value
    monkeypatch.setattr(Path,'read_text',changed)
    after={s:template_fingerprint(s) for s in before}
    assert after['stage4']!=before['stage4']
    assert all(after[s]==before[s] for s in ('stage1','stage2','stage3'))


def test_source_only_upstream_addition_carries_candidate_across_restart(tmp_path):
    from zerorepo.rtl_impl.module_planner import PlannerRunner
    from zerorepo.rtl_impl.module_planner.schemas import PlannerTaskInput
    saved={}
    def inject(runner):
        responses=runner.llm_client.backend.responses
        ru=responses[1]['responsibilities'][0]
        ids=ru['source_evidence_ids']; assert len(ids)>1
        ru['source_evidence_ids']=ids[:1]
        index=next(i for i,value in enumerate(responses) if isinstance(value,dict) and 'module_frame' in value)
        draft=responses[index]
        for o in draft['behavioral_obligations']: o['source_evidence_ids']=ids[:1]
        draft['behavioral_obligations'][0]['source_evidence_ids']=ids[1:2]
        draft['evidence_binding_requests']=[{'responsibility_id':ru['responsibility_id'],'source_evidence_ids':ids[1:2], 'rationale':'Verified additional evidence for the unchanged reset/update responsibility'}]
        saved['repair']=deepcopy(draft['behavioral_obligations'][1])
        draft['behavioral_obligations'][1]['implementation_block_id']='UNKNOWN'
        responses.insert(index+1,LLMRequestTimeoutError('source updated; repair interrupted'))
        failing=RaisingBackend(responses)
        runner.llm_client.backend=failing
        saved.update(runner=runner,backend=failing,expected_ids=ids[:2])
    with pytest.raises(LLMRequestTimeoutError): scenario(tmp_path,before_run=inject,artifacts={'retention':'full'})
    runner=saved['runner']
    task=PlannerTaskInput.model_validate(runner.llm_client.executor.scope['task'])
    decomposition=json.loads(runner.layout.artifact('stage2_decomposition.json').read_text())
    from zerorepo.rtl_impl.module_planner.utils.evidence import evidence_id
    ru=decomposition['responsibilities'][0]
    assert {evidence_id(ref) for ref in ru['source_refs']} == set(saved['expected_ids'])
    backend=RaisingBackend([{'behavioral_obligations':[saved['repair']]},*saved['backend'].responses])
    resumed=PlannerRunner(output_root=runner.output_root,llm_backend=backend,artifacts={'retention':'full'})
    result=resumed.run(task,resume=True,end_stage='stage4')
    assert result.stage4_status=='module_plans_planned'
    assert 'VALIDATION RESULT' in backend.calls[0]['user_prompt']
    assert json.loads(resumed.layout.artifact('planning_gate_report.json').read_text())['status']=='passed'


def test_heading_only_and_code_fence_evidence_are_never_dropped():
    from zerorepo.rtl_impl.module_planner.utils import split_spec_blocks
    assert split_spec_blocks('**5.3 Initial Data Loading**')[0].text=='**5.3 Initial Data Loading**'
    text='## Behavior\nbody\n\n```text\n## literal inside code\n```\n## trailing heading'
    chunks=split_spec_blocks(text)
    assert len(chunks)==2 and '## literal inside code' in chunks[0].text
    assert chunks[-1].text=='## trailing heading'


@pytest.mark.parametrize('observer', ['normal', 'broken'])
def test_ui_observes_without_changing_prompt_result_or_budget(tmp_path, monkeypatch, observer):
    from zerorepo.rtl_impl.process_observer import observe
    from zerorepo.rpg_gen.base.llm_client import Memory, SystemMessage, UserMessage
    from test_planning_harness import ToyAgent
    class Backend:
        def complete_with_memory(self, *, memory, images=None, request_options=None):
            self.messages=[(message.role,message.content) for message in memory.history]
            self.options=request_options
            return '{"value":1}'
    class Sink:
        def emit(self,*args,**kwargs):
            if observer=='broken': raise RuntimeError('UI disconnected')
    backend=Backend()
    client=PlannerLLMClient(backend=backend); client.configure_execution(tmp_path)
    memory=Memory(); memory.add_message(SystemMessage(content='same system')); memory.add_message(UserMessage(content='same input'))
    with observe(Sink()):
        result=ToyAgent(client)._complete_public(memory=memory,module='toy')
    assert result=='{"value":1}'
    assert backend.messages==[('system','same system'),('user','same input')]
    assert backend.options.first_content_timeout_seconds==240


def test_state_contracts_are_program_inherited_and_support_roles_are_limited(planned):
    from zerorepo.rtl_impl.module_planner.schemas.planning import StateAccess
    task, draft, validate = design_fixture(planned)
    export, issues = validate(draft); assert not issues
    obligation=next(o for o in export.behavioral_obligations if o.obligation_id=='OB_COMMIT')
    obligation.state_accesses.append(StateAccess(state_id=export.state_objects[0].state_id,role='compute_next'))
    metadata=task_metadata(export)
    primary=next(t for t in metadata.values() if 'OB_COMMIT' in t['obligation_ids'])
    assert primary['task_contract']['state_objects'][0]['owner_responsibility_id']==obligation.parent_responsibility_id
    declaration=metadata['B1_decl_state_and_keys']['task_contract']
    assert declaration['support_only'] and declaration['state_accesses']==[] and declaration['state_objects']
    support=next(t for key,t in metadata.items() if key.startswith('B5_'))['task_contract']
    assert support['state_accesses']==[{'state_id':export.state_objects[0].state_id,'role':'compute_next'}]


def test_gate_rejects_changed_state_table_in_skeleton(tmp_path):
    case=scenario(tmp_path)
    runner,stage3=case[1],case[4]
    path=runner.output_root/stage3.module_records[0].export_file
    value=json.loads(path.read_text()); value['state_objects'][0]['owner_responsibility_id']='foreign'
    path.write_text(json.dumps(value))
    result=report(case)
    assert result['status']=='failed' and any(error['code']=='state_binding_drift' for error in result['errors'])


def test_module_primary_source_never_implicitly_imports_sibling_spec(tmp_path):
    from zerorepo.rtl_impl.module_planner.schemas import PlannerTaskInput
    from test_rtl_module_planner import QueueBackend
    supplied=tmp_path/'system.md'; supplied.write_text('Only the supplied system specification')
    (tmp_path/'toy.md').write_text('Unrequested sibling with conflicting interface')
    agent=Stage3Agent(PlannerLLMClient(backend=QueueBackend([])))
    task=PlannerTaskInput(task_id='source',spec_md_files=[str(supplied)])
    assert agent._resolve_module_spec_file(task,'toy')==str(supplied)


@pytest.mark.parametrize('mutation,code',[('placeholder','placeholder_drift'),('label','duplicate_block_label')])
def test_derived_block_identity_cannot_drift(planned,mutation,code):
    task,draft,validate=design_fixture(planned)
    export,issues=validate(draft); assert not issues
    if mutation=='placeholder': export.structural_blocks[0].placeholder='<block: foreign>'
    else: export.structural_blocks[1].block_label=export.structural_blocks[0].block_label
    inputs=planned[3]
    issues=refinement_issues(export,module_context(inputs['stage2_decomposition'],export.module),inputs['stage2_input'])
    assert code in {issue.code for issue in issues}


def test_unparseable_output_repair_and_full_regeneration_are_counted(planned,tmp_path):
    task,valid,validate=design_fixture(planned)
    backend,run=session(tmp_path/'case',task,['{"truncated":',valid])
    result=run.execute(module='toy',prompt='design',context={},validate=validate)
    assert result.status=='validated' and len(backend.calls)==2
    metrics=json.loads((tmp_path/'case/plan/metrics.json').read_text())['stages']['stage3_module_skeletons']
    assert metrics['content_repair_requests']==metrics['full_object_regeneration_requests']==1
    assert metrics['unknown_usage_attempts']==2


def test_partial_server_usage_remains_explicitly_unknown(tmp_path):
    from zerorepo.rtl_impl.module_planner.utils.execution import RequestExecutor
    executor=RequestExecutor(tmp_path)
    executor.record({'request_id':'partial','transport_attempt':1,'stage':'stage3','usage':{'input_tokens':None,'output_tokens':7},'status':'completed'})
    metrics=json.loads((tmp_path/'plan/metrics.json').read_text())['stages']['stage3']
    assert metrics['unknown_usage_attempts']==1 and metrics['known_output_tokens']==7


def test_deepseek_native_usage_fields_are_recorded_without_double_counting(monkeypatch):
    from types import SimpleNamespace
    from zerorepo.rpg_gen.base.llm_client import Memory, SystemMessage, UserMessage
    from zerorepo.rpg_gen.base.llm_client.request_policy import LLMRequestOptions
    from zerorepo.rtl_impl.module_planner.utils.llm_client import DefaultPlannerLLMBackend
    usage=SimpleNamespace(prompt_tokens=20,completion_tokens=8,prompt_cache_hit_tokens=9,reasoning_tokens=3)
    response=SimpleNamespace(usage=usage,model='test-model',choices=[SimpleNamespace(message=SimpleNamespace(content='ok'),finish_reason='stop')])
    monkeypatch.setattr('zerorepo.rtl_impl.module_planner.utils.llm_client.create_bounded_chat_completion',lambda *args,**kwargs:response)
    backend=DefaultPlannerLLMBackend({'provider':'openai','model':'test-model','api_key':'test-secret','log':False})
    memory=Memory(); memory.add_message(SystemMessage(content='system')); memory.add_message(UserMessage(content='input'))
    assert backend._complete_bounded(memory,None,LLMRequestOptions())=='ok'
    assert backend.last_request_usage=={'input_tokens':20,'output_tokens':8,'cache_read_input_tokens':9,'reasoning_tokens':3}
