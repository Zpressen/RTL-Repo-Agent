import json

import pytest

from zerorepo.rtl_impl.module_planner.utils.json_repair import repair_json_payload
from zerorepo.rtl_impl.public_progress import split_public_result


@pytest.mark.parametrize('fenced', [False, True])
def test_latex_source_anchors_keep_literal_backslashes(fenced):
    anchor = r'The state is $sa_{ij}$ for $i,j \in \{0,1,2,3\}$.'
    raw = '{"fact_ledger":{"facts":[{"text_grounding":[{"start_line_anchor":"' + anchor + '"}]}]}}'
    if fenced:
        raw = '```json\n' + raw + '\n```'
    result = repair_json_payload(raw)
    assert result['fact_ledger']['facts'][0]['text_grounding'][0]['start_line_anchor'] == anchor


def test_valid_json_escapes_quotes_and_unicode_are_unchanged():
    data = {'text': 'line one\n"quote"\t中文', 'source': r'\in \{x\}', 'rtl': '\\escaped_identifier '}
    assert repair_json_payload(json.dumps(data)) == data
    assert repair_json_payload(r'{"text":"\u4e2d\u6587"}') == {'text': '中文'}


def test_invalid_unicode_escape_is_preserved_as_literal_source():
    assert repair_json_payload(r'{"source":"\unknown and \uZZZZ"}') == {'source': r'\unknown and \uZZZZ'}


def test_repair_does_not_accept_structurally_invalid_values():
    with pytest.raises(ValueError, match=r'line 1, column'):
        repair_json_payload('{"fact_ledger": ???}')


def test_public_report_is_separated_after_literal_escape_repair():
    raw = r'{"_public_start":{"summary":"提取 AES 规格"},"fact_ledger":{"anchor":"$i \in \{0,1\}$"},"_public_progress":{"summary":"保留原文公式"}}'
    cleaned, public, payload = split_public_result(raw)
    assert public == {'summary': '保留原文公式'}
    assert json.loads(cleaned) == payload == {'fact_ledger': {'anchor': r'$i \in \{0,1\}$'}}


def test_fact_round_accepts_formula_output_without_another_model_request():
    from zerorepo.rtl_impl.module_planner.agents.stage1_agent import Stage1Agent, _FactRoundPayload
    from zerorepo.rtl_impl.module_planner.utils.llm_client import PlannerLLMClient
    calls = []
    raw = r'{"fact_ledger":{"source_files":["aes.md"],"facts":[{"module":"aes_cipher_top","category":"datapath","text_grounding":[{"source_md_file":"aes.md","start_line_anchor":"$i \in \{0,1,2,3\}$"}]}]}}'

    def backend(**kwargs):
        calls.append(kwargs)
        return raw

    agent = Stage1Agent(PlannerLLMClient(backend=backend))
    payload = agent._invoke_with_repair('Extract AES facts', [], {}, {},
        output_model=_FactRoundPayload,
        quality_validator=lambda artifact: agent._validate_round_payload('facts', artifact))
    assert len(calls) == 1
    assert payload.fact_ledger.facts[0].text_grounding[0].start_line_anchor == r'$i \in \{0,1,2,3\}$'


def test_exhausted_parse_attempt_does_not_promise_another_retry(tmp_path):
    from pydantic import BaseModel
    from zerorepo.rtl_impl.module_planner.agents.base import BaseStageAgent, StageGenerationError
    from zerorepo.rtl_impl.module_planner.utils.llm_client import PlannerLLMClient
    from zerorepo.rtl_impl.process_observer import observe
    from zerorepo.rtl_impl.process_events import JsonlProcessEventSink

    class Output(BaseModel):
        module: str

    class Stage(BaseStageAgent):
        stage_name = 'stage1_contracts'
        output_model = Output
        max_parse_attempts = 2

    sink = JsonlProcessEventSink(tmp_path / 'events.jsonl', 'parse-failure')
    stage = Stage(PlannerLLMClient(backend=lambda **kwargs: '{"module": ???}'))
    with observe(sink, 'spec'), pytest.raises(StageGenerationError):
        stage._invoke_with_repair('Read module', [], {}, {})
    failures = [json.loads(line) for line in sink.path.read_text().splitlines() if json.loads(line)['event_type'] == 'finding.created']
    assert len(failures) == 2
    assert '请求修正' in failures[0]['result_summary']
    assert '本轮停止' in failures[-1]['result_summary']
    assert '请求修正' not in failures[-1]['result_summary']
