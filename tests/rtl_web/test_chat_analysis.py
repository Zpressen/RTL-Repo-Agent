"""Exercise real exported evidence, without models, toolchains, or RTL writes."""
import asyncio
import copy
import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from zerorepo.rtl_web.api import create_app
from zerorepo.rtl_web.chat import respond, evidence
from zerorepo.rtl_web.chat_analysis import unsupported_reply
from zerorepo.rtl_web.store import Store

PUBLIC = Path(__file__).resolve().parents[2] / 'web/rtl-demo/public'


def load_export(settings, case):
    store = Store(settings.data)
    b = json.loads((PUBLIC / 'cases' / case / 'manifest.json').read_text())
    store.put('bundle', b['bundle_id'], b)
    store.put('run', b['source_run_id'], {'run_id': b['source_run_id'], 'case_id': case, 'origin': 'historical'})
    for r in b['debug_history']['runs']:
        store.put('run', r['run_id'], r)
    for kind in ['version', 'validation']:
        for v in b[kind + 's']: store.put(kind, v[kind + '_id'], v)
    for a in b['artifacts']:
        url = b['content_urls'].get(a['artifact_id'])
        if not url: continue
        raw = json.loads((PUBLIC / url.lstrip('/')).read_text())['content'].encode()
        if a['kind'] == 'spec' and hashlib.sha256(raw).hexdigest() != a['sha256']:
            # Original spec uses CRLF; the static text wrapper normalizes reads.
            raw = settings.for_case(case).spec.read_bytes()
        assert hashlib.sha256(raw).hexdigest() == a['sha256']
        dest = settings.data / 'test-content' / a['artifact_id']; dest.parent.mkdir(exist_ok=True)
        dest.write_bytes(raw)
        store.put('artifact', a['artifact_id'], {**a, 'storage_key': dest.relative_to(settings.data).as_posix()})
    sid = store.create_session(case, {'case_id': case})['session_id']
    return store, b, sid


def context(b, value):
    return {'case_id': b['case_id'], 'run_id': value['run_id'], 'version_id': value['version_id'],
            'validation_id': value['validation_id'], 'view': 'workspace', 'workspace_panel': 'verify'}


@pytest.mark.parametrize('case,total', [('e203', 39), ('aes_cipher_system_hard', 8),
                                      ('aes_inv_cipher_top_system', 4), ('sdc_controller_system', 17)])
def test_all_analysis_buttons_invoke_model_with_bound_evidence(settings, case, total, monkeypatch):
    store, b, sid = load_export(settings, case)
    ctx = context(b, b['debug_history']['runs'][0]['validations'][0])
    seen = []
    async def provider(payload):
        seen.append(payload)
        return {'kind': 'answer', 'text': 'unique-model-response-' + str(len(seen)),
                'evidence_refs': [{'artifact_id': b['spec_artifact_id']}]}
    questions = ['这个设计如何拆分模块？', '解释当前验证结果', '分析失败原因与修复记录', '分析并修复失败版本', '再说明上面第二点']
    for i, question in enumerate(questions):
        msg, _ = store.add_message(sid, str(i), {'text': question, 'context_ref': ctx})
        asyncio.run(respond(settings, store, msg, provider))
        result = store.session(sid)['messages'][-1]
        assert result['state'] == 'answered' and result['answer'] == 'unique-model-response-' + str(i + 1)
        assert result['answer_source'] == 'model'
        assert seen[-1]['evidence']['validation']['validation_id'] == ctx['validation_id']
        assert seen[-1]['evidence']['historical_debug_context']['candidate_count'] == total
        assert len(seen[-1]['history']) == i
        assert result['evidence_refs'] == [{'artifact_id': b['spec_artifact_id']}]
    assert len(seen) == 5 and store.session(sid)['operations'] == []
    for i, text in enumerate(['重新验证当前设计', '按预置规格生成并验证']):
        msg, _ = store.add_message(sid, 'unsupported-' + str(i), {'text': text, 'context_ref': ctx})
        asyncio.run(respond(settings, store, msg, provider))
        result = store.session(sid)['messages'][-1]
        assert result['answer_source'] == 'unsupported_notice' and '暂不支持' in result['answer']
    assert len(seen) == 5


def test_model_receives_unverified_status_and_real_repair_baseline(settings):
    store, b, sid = load_export(settings, 'aes_inv_cipher_top_system')
    run = b['debug_history']['runs'][0]
    for attempt in run['attempts'][:2]:
        val = next(v for v in run['validations'] if v['validation_id'] == attempt['validation_id'])
        proof = evidence(settings, store, {'context_ref': context(b, val), 'session_id': sid})
        assert proof['validation']['verdict'] == 'unverified'
        assert not proof['validation']['simulation_completed']
        assert proof['recorded_repair']['baseline_version_id'] == attempt['baseline_version_id']
    attempt = run['attempts'][3]
    val = next(v for v in run['validations'] if v['validation_id'] == attempt['validation_id'])
    proof = evidence(settings, store, {'context_ref': context(b, val), 'session_id': sid})
    assert proof['recorded_repair']['baseline_version_id'] == attempt['baseline_version_id']
    assert proof['recorded_repair']['diagnosis']['summary'] == attempt['diagnosis']['summary']


def test_general_model_cannot_accidentally_start_execution(settings):
    store, b, sid = load_export(settings, 'e203')
    val = b['debug_history']['runs'][0]['validations'][0]
    msg, _ = store.add_message(sid, 'free-form', {'text': '你能看看这个问题吗', 'context_ref': context(b, val)})
    async def provider(payload): return {'kind': 'fix', 'text': 'Executing'}
    asyncio.run(respond(settings, store, msg, provider))
    saved = store.session(sid)
    assert saved['messages'][-1]['state'] == 'answered'
    assert '不支持现场' in saved['messages'][-1]['answer']
    assert saved['operations'] == []


def test_live_run_does_not_borrow_historical_architecture(settings):
    store, b, sid = load_export(settings, 'e203')
    store.put('run', 'test-live', {'run_id': 'test-live', 'case_id': 'e203', 'origin': 'live', 'modules': []}, sid)
    msg = {'text': '这个设计如何拆分模块？', 'context_ref': {'case_id': 'e203', 'run_id': 'test-live'}, 'session_id': sid}
    proof = evidence(settings, store, msg)
    assert proof['case']['modules'] == []
    assert proof['record_origin'] == 'live'
    assert 'historical_debug_context' not in proof


def test_shortcuts_call_provider_through_real_session_api(settings):
    store, b, _ = load_export(settings, 'e203')
    app = create_app(settings)
    seen = []
    async def provider(payload):
        seen.append(payload)
        return {'kind': 'answer', 'text': 'real provider path in test'}
    app.state.decision_provider = provider
    headers = {'Origin': 'http://localhost:5173', 'X-Demo-Request': '1'}
    with TestClient(app, base_url='http://localhost') as c:
        session = c.post('/api/sessions', json={'case_id': 'e203'}, headers={**headers, 'Idempotency-Key': 'analysis-session'}).json()
        sid = session['session_id']; ctx = {k: v for k, v in session['selection'].items() if k != 'browsing_mode'}
        r = c.post('/api/sessions/' + sid + '/messages', json={'text': '解释当前验证结果', 'context_ref': ctx, 'client_message_id': 'analysis'}, headers={**headers, 'Idempotency-Key': 'analysis'})
        assert r.status_code == 202
        import time
        for _ in range(100):
            current = c.get('/api/sessions/' + sid).json()
            if current['messages'][-1]['state'] != 'replying': break
            time.sleep(.005)
        assert current['messages'][-1]['state'] == 'answered'
        assert current['messages'][-1]['answer_source'] == 'model'
        assert len(seen) == 1
        assert current['messages'][-1]['answer'] == 'real provider path in test'
        assert not current['operations']


def test_chat_sandbox_receives_only_reviewed_chat_options(settings, tmp_path):
    from zerorepo.rtl_web.jobs import prepare_chat_job
    import yaml
    settings.agent_config = tmp_path / 'agent.yaml'
    settings.agent_config.write_text('llm: {model: synthetic, api_key: fake-test-value}\nrtl_debug: {private: do-not-copy}\n')
    settings.runtime.update(chat_max_tokens=4096, chat_thinking=False, chat_execution_enabled=False, private_web_value='do-not-copy')
    task, path = prepare_chat_job(settings)
    cfg = yaml.safe_load(path.read_text())
    assert cfg['runtime']['chat_max_tokens'] == 4096
    assert cfg['runtime']['chat_thinking'] is False
    assert cfg['runtime']['chat_execution_enabled'] is False
    assert 'do-not-copy' not in path.read_text()
    agent = yaml.safe_load((task/'job_inputs/agent.yaml').read_text())
    assert set(agent) == {'llm'}


def test_model_failure_is_explicit_not_replaced_by_a_canned_analysis(settings, monkeypatch):
    from zerorepo.rtl_web.schemas import DemoError
    import zerorepo.rtl_web.chat as chat
    store, b, sid = load_export(settings, 'e203')
    async def unavailable(settings, payload): raise DemoError('model_unavailable', '模型当前不可用', 503)
    monkeypatch.setattr(chat, 'model_decision', unavailable)
    settings.require = lambda capability: None
    for i, text in enumerate(['这个设计如何拆分模块？', '解释当前验证结果', '分析失败原因与修复记录']):
        msg, _ = store.add_message(sid, str(i), {'text': text, 'context_ref': context(b, b['validations'][0])})
        asyncio.run(respond(settings, store, msg))
        saved = store.session(sid)['messages'][-1]
        assert saved['state'] == 'failed' and saved['error_code'] == 'model_unavailable'
        assert saved.get('answer_source') != 'recorded_evidence'
    assert store.session(sid)['operations'] == []
