import logging

import pytest

from zerorepo.rtl_impl.module_planner.agents.stage1_agent import Stage1Agent
from zerorepo.rtl_impl.module_planner.schemas import PlannerTaskInput, Stage1ContractsArtifact
from zerorepo.rtl_impl.module_planner.utils import PlannerLLMClient
from zerorepo.rtl_impl.module_planner.utils.md_loader import extract_markdown_outline


def test_confirmed_target_and_bound_spec_finish_without_identity_retries(tmp_path, monkeypatch):
    spec = tmp_path / 'aes_cipher_system_hard.md'
    spec.write_text('**1.1 Top-Level Interface**\n\n| Signal | Direction | Width |\n| --- | --- | --- |\n| clk | input | 1 |\n| data | output | 128 |\n')
    introduction = tmp_path / 'spec.md'
    introduction.write_text('Generate aes_cipher_top using the attached specification.')
    task = PlannerTaskInput(task_id='unrelated-run-id', spec_md_files=[str(introduction), str(spec)],
                            required_top_module='aes_cipher_top', top_spec_file=str(spec))
    grounding = {'source_md_file': str(spec), 'start_line_anchor': '| clk | input | 1 |'}
    responses = [
        {'fact_ledger': {'facts': [{'module': 'aes_cipher_system_hard', 'category': 'interface', 'subject': 'clk',
          'predicate': 'is_port', 'object': {'name': 'clk', 'direction': 'input', 'width': '1'}, 'text_grounding': [grounding]}]}},
        {'interface_contract': {'module': 'aes_cipher_top', 'clock': 'clk', 'ports': [
            {'name': 'clk', 'direction': 'input', 'width': '1'},
            {'name': 'data', 'direction': 'output', 'width': '128'}], 'text_grounding': [grounding]}},
    ]
    calls = []

    def backend(**kwargs):
        calls.append(kwargs['user_prompt'])
        return responses.pop(0)

    agent = Stage1Agent(PlannerLLMClient(backend=backend), logger=logging.getLogger('confirmed-target-test'))
    monkeypatch.setattr(agent, '_repair_missing_top_identity', lambda **kwargs: pytest.fail('Confirmed top was needlessly re-extracted'))
    artifact = agent.run(task, {})
    assert artifact.stage1_status == 'contracts_completed'
    assert artifact.structure_contract.top_module == 'aes_cipher_top'
    assert artifact.spec_index['aes_cipher_top'] == str(spec.resolve())
    assert 'aes_cipher_top' in artifact.structure_contract.modules
    assert len(calls) == 2
    assert 'confirmed_task_constraints' in calls[0] and 'aes_cipher_top' in calls[0]
    assert '| data | output | 128 |' in calls[1]
    top = next(contract for contract in artifact.interface_contracts if contract.module == 'aes_cipher_top')
    assert [port.name for port in top.ports] == ['clk', 'data']


def test_explicit_generation_target_fact_is_a_top_identity():
    agent = Stage1Agent(PlannerLLMClient(backend=lambda **kwargs: None))
    artifact = Stage1ContractsArtifact(task_id='job', fact_ledger={'facts': [{
        'module': 'spec', 'category': 'module_identity', 'subject': 'aes_cipher_top',
        'predicate': 'is_explicit_generation_target', 'object': {'target_module': 'aes_cipher_top'},
    }]})
    artifact = agent._finalize_structure_contract(artifact, PlannerTaskInput(task_id='job', spec_md_files=['spec.md']))
    assert artifact.structure_contract.top_module == 'aes_cipher_top'


def test_unknown_identity_predicate_is_not_treated_as_explicit_top():
    agent = Stage1Agent(PlannerLLMClient(backend=lambda **kwargs: None))
    artifact = Stage1ContractsArtifact(task_id='job', fact_ledger={'facts': [{
        'module': 'document_name', 'category': 'module_identity', 'subject': 'maybe_top',
        'predicate': 'might_be_top', 'object': {},
    }]})
    artifact = agent._finalize_structure_contract(artifact, PlannerTaskInput(task_id='job', spec_md_files=['spec.md']))
    assert artifact.structure_contract.top_module == ''


def test_bound_top_spec_must_be_part_of_task_inputs(tmp_path):
    spec = tmp_path / 'spec.md'
    spec.write_text('A real input')
    task = PlannerTaskInput(task_id='job', spec_md_files=[str(spec)], top_spec_file=str(tmp_path / 'other.md'))
    agent = Stage1Agent(PlannerLLMClient(backend=lambda **kwargs: None))
    with pytest.raises(ValueError, match='must belong'):
        agent._resolve_top_spec_document(Stage1ContractsArtifact(task_id='job'), task)


def test_bold_numbered_repository_sections_are_visible_in_outline():
    outline = extract_markdown_outline('**1. Overview**\n\n**1.1 Top-Level Interface**\n\n**Bold prose**\n\n**2. Operation**')
    assert outline == ['1. Overview', '1. Overview > 1.1 Top-Level Interface', '2. Operation']
