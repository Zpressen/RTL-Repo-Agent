from rtl_artifact_test_utils import write_artifact_text
import json
import os

from zerorepo.rtl_impl.module_planner.agents import Stage6MergeAgent
from zerorepo.rtl_impl.module_planner.schemas import ModuleSpecBlocks
from zerorepo.rtl_impl.retrieval_agent import MergeContextRetrievalResult
from zerorepo.rtl_impl.module_planner.utils.local_repair import fingerprint


def test_merge_retrieval_uses_content_binding_instead_of_mtime(tmp_path):
    agent=Stage6MergeAgent(None,output_root=tmp_path/'outputs')
    spec=ModuleSpecBlocks(module='toy',source_spec_file='toy.md',blocks=[{'block_id':'S001','text':'Drive y from a'}])
    fragment=tmp_path/'fragment.v';write_artifact_text(fragment, 'assign y=a;\n')
    payload=MergeContextRetrievalResult(module='toy',selected_spec_refs=['S001']).model_dump(mode='json')
    path=agent._merge_retrieval_file('toy');path.parent.mkdir(parents=True);write_artifact_text(path, json.dumps(payload))
    key=fingerprint({'spec':spec,'fragments':fragment.read_text()})
    agent._write_merge_cache_stamp('toy','spec',key,payload)
    os.utime(fragment,(2000000000,2000000000));os.utime(path,(1,1))
    assert agent._read_merge_retrieval_if_valid(module_name='toy',module_spec=spec,fragment_file=fragment,expected_key=key)
    write_artifact_text(fragment, 'assign y=~a;\n')
    changed=fingerprint({'spec':spec,'fragments':fragment.read_text()})
    assert agent._read_merge_retrieval_if_valid(module_name='toy',module_spec=spec,fragment_file=fragment,expected_key=changed) is None
    payload['selected_spec_refs']=['S999'];write_artifact_text(path, json.dumps(payload))
    assert agent._read_merge_retrieval_if_valid(module_name='toy',module_spec=spec,fragment_file=fragment,expected_key=key) is None


def test_child_context_uses_retrieval_and_dependency_content_binding(tmp_path):
    agent=Stage6MergeAgent(None,output_root=tmp_path/'outputs')
    retrieval=agent._merge_retrieval_file('toy');retrieval.parent.mkdir(parents=True);write_artifact_text(retrieval, '{}')
    path=agent._merge_child_context_file('toy');path.parent.mkdir(parents=True)
    payload={'schema_version':'merge_child_context_v1','module':'toy','retrieval_requested':False}
    write_artifact_text(path, json.dumps(payload));agent._write_merge_cache_stamp('toy','children','same',payload)
    os.utime(retrieval,(2000000000,2000000000));os.utime(path,(1,1))
    assert agent._read_merge_child_context_if_valid(module_name='toy',retrieval_file=retrieval,expected_key='same')==payload
    assert agent._read_merge_child_context_if_valid(module_name='toy',retrieval_file=retrieval,expected_key='changed') is None


def test_legacy_merge_retrieval_without_source_proof_is_not_trusted(tmp_path):
    agent=Stage6MergeAgent(None,output_root=tmp_path/'outputs')
    spec=ModuleSpecBlocks(module='toy',source_spec_file='toy.md',blocks=[{'block_id':'S001','text':'Drive y'}])
    path=agent._merge_retrieval_file('toy');path.parent.mkdir(parents=True)
    write_artifact_text(path, MergeContextRetrievalResult(module='toy',selected_spec_refs=['S001']).model_dump_json())
    assert agent._read_merge_retrieval_if_valid(module_name='toy',module_spec=spec,fragment_file=tmp_path/'missing.v',expected_key='same') is None
