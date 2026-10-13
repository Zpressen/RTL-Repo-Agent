"""Source-only selection, cache recovery, and real SDK cancellation regressions."""
from __future__ import annotations

import asyncio
from dataclasses import replace
import json
from pathlib import Path
import time

import httpx
import openai
import pytest

from zerorepo.rpg_gen.base.llm_client.errors import LLMRequestError, LLMRequestTimeoutError
from zerorepo.rpg_gen.base.llm_client.providers.bounded_completion import create_bounded_chat_completion
from zerorepo.rpg_gen.base.llm_client.request_policy import LLMRequestOptions
from zerorepo.rtl_impl.module_planner.utils.llm_client import DefaultPlannerLLMBackend, PlannerLLMClient
from zerorepo.rtl_impl.retrieval_agent import ModuleSpecContextRetriever
from zerorepo.rtl_impl.retrieval_agent.source_context import source_ranges


class SelectBackend:
    def __init__(self, response=None):
        self.calls = []
        self.response = response

    def complete(self, *, system_prompt, user_prompt, images=None):
        self.calls.append(user_prompt)
        chunks = json.loads(user_prompt.split('[SOURCE_CHUNKS]\n')[1])
        if isinstance(self.response, BaseException):
            raise self.response
        return self.response if self.response is not None else {
            'module': 'toy', 'selections': [{'source_chunk_id': c['chunk_id']} for c in reversed(chunks)]}


def retrieval(tmp_path, response=None, limits=None):
    spec = tmp_path / 'toy.md'
    spec.write_text('# toy\nInterface and behavior.\n\n## Operation\ntoy updates output.\n')
    backend = SelectBackend(response)
    llm = PlannerLLMClient(backend=backend)
    retriever = ModuleSpecContextRetriever(llm, cache_root=tmp_path / 'outputs' / '.repair_cache' / 'module_spec', limits=limits)
    args = dict(module_name='toy', spec_md_files=[str(spec)], repo_module={'module': 'toy', 'role': 'toy operation'})
    return spec, backend, retriever, args


def test_selection_restores_exact_source_in_source_order_and_deduplicates(tmp_path):
    spec, backend, retriever, args = retrieval(tmp_path)
    backend.response = {'module': 'toy', 'selections': [
        {'source_chunk_id': 'C002'}, {'source_chunk_id': 'C001'}, {'source_chunk_id': 'C002'}]}
    result = retriever.select_module_spec_context(**args)
    assert not result.fallback_used
    assert ''.join(b.text for b in result.blocks) == spec.read_text()
    assert [b.source_chunk_ids for b in result.blocks] == [['C001'], ['C002']]
    assert [b.block_id for b in result.blocks] == ['S001', 'S002']
    assert 'DO NOT return source text' in backend.calls[0]


@pytest.mark.parametrize('raw', [
    {'module': 'other', 'selections': [{'source_chunk_id': 'C001'}]},
    {'module': 'toy', 'selections': [{'source_chunk_id': 'C999'}]},
    {'module': 'toy', 'selections': []},
    '{"module":"toy","selections":[{"source_chunk_id":"C001"}',
    '{"module":"toy","module":"other","selections":[]}',
    LLMRequestTimeoutError('total_timeout'),
])
def test_bad_or_timed_out_selection_degrades_and_is_cached(tmp_path, raw):
    spec, backend, retriever, args = retrieval(tmp_path, raw)
    first = retriever.select_module_spec_context(**args)
    assert first.fallback_used and first.fallback_reason
    assert ''.join(b.text for b in first.blocks) == spec.read_text()
    assert all(b.confidence == 'low' for b in first.blocks)
    second = retriever.select_module_spec_context(**args)
    assert first == second and len(backend.calls) == 1


def test_legacy_text_must_match_its_citation_not_another_source_chunk(tmp_path):
    spec, backend, retriever, args = retrieval(tmp_path)
    chunks = retriever._build_source_chunks(retriever._read_sources([str(spec)]))
    backend.response = {'module': 'toy', 'blocks': [{'block_id': 'S001', 'text': chunks[1]['text'],
        'source_file': str(spec), 'source_chunk_ids': ['C001']}]}
    assert retriever.select_module_spec_context(**args).fallback_used


def test_legacy_exact_block_remains_compatible(tmp_path):
    spec, backend, retriever, args = retrieval(tmp_path)
    chunks = retriever._build_source_chunks(retriever._read_sources([str(spec)]))
    backend.response = {'module': 'toy', 'blocks': [{'block_id': 'S001', 'text': chunks[0]['text'],
        'source_file': str(spec), 'source_chunk_ids': ['C001']}]}
    assert not retriever.select_module_spec_context(**args).fallback_used


@pytest.mark.parametrize('change', ['source', 'role', 'fact', 'corrupt', 'bypass', 'policy'])
def test_cache_invalidates_only_when_inputs_or_integrity_change(tmp_path, change):
    spec, backend, retriever, args = retrieval(tmp_path)
    args['fact_ledger'] = {'facts': [{'fact_id': 'F1', 'module': 'toy', 'subject': 'toy', 'object': 'original'}]}
    retriever.select_module_spec_context(**args)
    if change == 'source':
        spec.write_text(spec.read_text() + 'Extra toy constraint.\n')
    elif change == 'role':
        args['repo_module']['role'] = 'toy revised operation'
    elif change == 'fact':
        args['fact_ledger']['facts'][0]['object'] = 'revised'
    elif change == 'corrupt':
        (retriever.cache_root / 'toy.json').write_text('{}')
    elif change == 'policy':
        retriever.max_chunks = 1
    else:
        retriever.cache_enabled = False
    retriever.select_module_spec_context(**args)
    assert len(backend.calls) == 2


def test_unrelated_facts_do_not_invalidate_cached_module(tmp_path):
    _, backend, retriever, args = retrieval(tmp_path)
    args['fact_ledger'] = {'facts': [{'fact_id': 'Fother', 'module': 'unrelated', 'object': 'unrelated'}]}
    retriever.select_module_spec_context(**args)
    args['fact_ledger']['facts'][0]['object'] = 'unrelated revised'
    retriever.select_module_spec_context(**args)
    assert len(backend.calls) == 1


def test_cache_survives_new_retriever_without_completed_skeleton(tmp_path):
    _, backend, retriever, args = retrieval(tmp_path)
    first = retriever.select_module_spec_context(**args)
    fresh = ModuleSpecContextRetriever(PlannerLLMClient(backend=SelectBackend(AssertionError('no request'))),
                                      cache_root=retriever.cache_root)
    assert fresh.select_module_spec_context(**args) == first


def test_source_ranges_are_lossless_bounded_and_fence_aware():
    text = '# top\n\n##### fifth\n' + 'paragraph data\n' * 700 + '\n###### sixth\n~~~verilog\n## fake heading\n~~~\n'
    ranges = source_ranges(text)
    assert ''.join(text[s['start']:s['end']] for s in ranges) == text
    assert max(s['end']-s['start'] for s in ranges) <= 6000
    assert any('fifth' in s['heading_path'] for s in ranges)
    assert any('sixth' in s['heading_path'] for s in ranges)
    assert not any('fake heading' in s['heading_path'] for s in ranges)
    assert all(a['end'] == b['start'] for a, b in zip(ranges, ranges[1:]))


def test_budget_keeps_all_port_table_parts_even_when_not_sent_to_model(tmp_path):
    spec, backend, retriever, args = retrieval(tmp_path, limits={'chunk_chars': 500, 'max_chunks': 2, 'candidate_chars': 1000})
    text = '# toy\n## Ports\n| Name | Direction | Width |\n| --- | --- | --- |\n'
    text += ''.join(f'| port_{i} | input | 1 |\n' for i in range(120))
    spec.write_text(text)
    args.update(is_top_module=True, primary_spec_file=str(spec))
    result = retriever.select_module_spec_context(**args)
    assert 'port_119' in ''.join(b.text for b in result.blocks)
    assert retriever.last_input_summary['candidate_count'] <= 2
    assert retriever.last_input_summary['mandatory_local_ids']


def test_prompt_and_facts_are_bounded_without_truncating_source(tmp_path):
    spec, _, retriever, args = retrieval(tmp_path)
    spec.write_text('# toy\n' + ('## toy operation\n' + 'data' * 2500 + '\n') * 30)
    args['fact_ledger'] = {'facts': [{'fact_id': str(i), 'module': 'toy', 'object': 'details' * 100,
        'text_grounding': 'repeated source' * 3000} for i in range(80)]}
    result = retriever.select_module_spec_context(**args)
    summary = retriever.last_input_summary
    assert summary['candidate_count'] <= 24 and summary['candidate_chars'] <= 48000
    assert summary['fact_chars'] <= 8000 and summary['prompt_chars'] <= 64000
    assert summary['omitted_fact_ids'] and summary['omitted_chunk_ids']
    for block in result.blocks:
        assert block.text in spec.read_text()


def wire(text='', finish=None):
    value = {'id': 'mock-request', 'object': 'chat.completion.chunk', 'created': 0, 'model': 'mock-model',
             'choices': [{'index': 0, 'delta': {'content': text}, 'finish_reason': finish}]}
    return ('data: ' + json.dumps(value) + '\n\n').encode()


class WaitingBody(httpx.AsyncByteStream):
    def __init__(self, text='partial', trickle=False):
        self.text = text
        self.trickle = trickle
        self.closed = False

    async def __aiter__(self):
        yield wire(self.text)
        while True:
            await asyncio.sleep(0.01 if self.trickle else 10)
            yield wire('.')

    async def aclose(self):
        self.closed = True


def bounded(tmp_path, handler, **overrides):
    clients = []
    snapshots = []
    options = LLMRequestOptions(total_timeout_seconds=0.12, first_content_timeout_seconds=1,
        idle_timeout_seconds=1, progress_interval_seconds=0.03, slow_window_seconds=0.04,
        stage='stage3_module_skeletons', module='toy', draft_root=tmp_path, progress_callback=snapshots.append)
    options = replace(options, **overrides)
    def factory():
        client = openai.AsyncOpenAI(api_key='test-secret', max_retries=0,
            http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        clients.append(client)
        return client
    def run():
        return create_bounded_chat_completion(factory, {'model': 'mock-model', 'messages': [{'role': 'user', 'content': 'test'}]},
            stream=True, options=options, log=False)
    return run, clients, snapshots


@pytest.mark.parametrize('condition', ['headers', 'empty_content', 'idle', 'trickle'])
def test_request_deadline_cancels_socket_wait_and_preserves_partial_draft(tmp_path, condition):
    body = WaitingBody(text='' if condition == 'empty_content' else 'partial', trickle=condition == 'trickle')
    calls = []
    async def handler(request):
        calls.append(request)
        if condition == 'headers':
            await asyncio.sleep(10)
        return httpx.Response(200, headers={'content-type': 'text/event-stream'}, stream=body)
    overrides = {}
    if condition in {'headers', 'empty_content'}:
        overrides['first_content_timeout_seconds'] = 0.07
    if condition == 'headers':
        # Include SDK's first-use platform-header initialization before reaching the transport.
        overrides.update(total_timeout_seconds=1, first_content_timeout_seconds=0.5)
    if condition == 'idle':
        overrides['idle_timeout_seconds'] = 0.07
    run, clients, snapshots = bounded(tmp_path, handler, **overrides)
    start = time.monotonic()
    with pytest.raises(LLMRequestTimeoutError):
        run()
    assert time.monotonic() - start < 2
    assert len(calls) == 1 and all(c.is_closed() for c in clients)
    assert snapshots[-1]['status'] == 'failed'
    assert snapshots[-1]['remaining_seconds'] >= 0
    assert 'completed' not in [s['status'] for s in snapshots]
    status_file = next(tmp_path.glob('stage3_module_skeletons/toy/*/status.json'))
    metadata = status_file.read_text()
    assert 'test-secret' not in metadata
    if condition in {'idle', 'trickle'}:
        assert 'partial' in status_file.with_name('attempt_1.partial.txt').read_text()
    if condition != 'headers':
        assert body.closed


def test_success_uses_actual_sdk_aggregation_and_closes_client(tmp_path):
    async def handler(request):
        return httpx.Response(200, headers={'content-type': 'text/event-stream', 'x-request-id': 'remote-id'},
            content=wire('{"value":') + wire('7}', 'stop') + b'data: [DONE]\n\n')
    run, clients, snapshots = bounded(tmp_path, handler, total_timeout_seconds=2)
    assert run().choices[0].message.content == '{"value":7}'
    assert snapshots[-1]['status'] == 'completed'
    assert snapshots[-1]['server_request_id'] == 'remote-id'
    assert all(c.is_closed() for c in clients)


def test_retry_backoff_counts_against_total_budget(tmp_path, monkeypatch):
    monkeypatch.setattr('zerorepo.rpg_gen.base.llm_client.providers.bounded_completion.random.uniform', lambda *_: 10)
    calls = []
    async def handler(request):
        calls.append(request)
        return httpx.Response(503, json={'error': {'code': 'busy', 'type': 'unavailable'}})
    run, clients, snapshots = bounded(tmp_path, handler)
    with pytest.raises(LLMRequestTimeoutError):
        run()
    assert len(calls) == 1 and all(c.is_closed() for c in clients)
    assert 'retrying' in [s['status'] for s in snapshots]


def test_one_retry_within_budget_then_success(tmp_path, monkeypatch):
    monkeypatch.setattr('zerorepo.rpg_gen.base.llm_client.providers.bounded_completion.random.uniform', lambda *_: 0.01)
    calls = []
    async def handler(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(503, headers={'x-request-id': 'failed-id'}, json={'error': {'code': 'busy'}})
        return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=wire('OK', 'stop') + b'data: [DONE]\n\n')
    run, clients, snapshots = bounded(tmp_path, handler, total_timeout_seconds=2)
    assert run().choices[0].message.content == 'OK'
    assert len(calls) == 2 and snapshots[-1]['attempt'] == 2
    assert 'error_type' not in snapshots[-1]
    assert all(c.is_closed() for c in clients)


def test_server_error_metadata_is_sanitized_and_not_retried(tmp_path):
    async def handler(request):
        return httpx.Response(400, headers={'x-request-id': 'failed-id'},
            json={'error': {'type': 'bad_input', 'code': 'invalid', 'message': 'test-secret'}})
    run, clients, snapshots = bounded(tmp_path, handler)
    with pytest.raises(LLMRequestError) as failure:
        run()
    assert len(clients) == 1
    assert snapshots[-1]['http_status'] == 400 and snapshots[-1]['server_error_code'] == 'invalid'
    assert snapshots[-1]['server_request_id'] == 'failed-id'
    assert 'test-secret' not in str(failure.value) and 'test-secret' not in json.dumps(snapshots)


def test_bounded_backend_sends_per_call_cap_without_mutating_config(tmp_path, monkeypatch):
    backend = DefaultPlannerLLMBackend({'provider': 'openai', 'model': 'test-model', 'api_key': 'test-secret',
        'max_tokens': 65536, 'stream': True, 'log': False})
    requests = []
    async def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=wire('OK', 'stop') + b'data: [DONE]\n\n')
    monkeypatch.setattr(backend, '_build_async_openai_client', lambda: openai.AsyncOpenAI(api_key='test-secret',
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)), max_retries=0))
    options = LLMRequestOptions(max_tokens=4096, draft_root=tmp_path)
    assert backend.complete(system_prompt='test', user_prompt='test', request_options=options) == 'OK'
    assert requests[0]['max_tokens'] == 4096 and backend.config.max_tokens == 65536


def test_sync_api_inside_existing_async_loop(tmp_path):
    async def handler(request):
        return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=wire('OK', 'stop') + b'data: [DONE]\n\n')
    run, clients, _ = bounded(tmp_path, handler, total_timeout_seconds=2)
    async def caller():
        return run().choices[0].message.content
    assert asyncio.run(caller()) == 'OK'
    assert all(c.is_closed() for c in clients)


def test_user_interrupt_retains_draft_and_closes_stream(tmp_path):
    body = WaitingBody()
    async def handler(request):
        return httpx.Response(200, headers={'content-type': 'text/event-stream'}, stream=body)
    def interrupt(snapshot):
        if snapshot['status'] == 'running' and snapshot['content']:
            raise KeyboardInterrupt()
    run, clients, _ = bounded(tmp_path, handler, progress_callback=interrupt, total_timeout_seconds=2)
    with pytest.raises(KeyboardInterrupt):
        run()
    status_file = next(tmp_path.glob('stage3_module_skeletons/toy/*/status.json'))
    assert json.loads(status_file.read_text())['status'] == 'interrupted'
    assert status_file.with_name('attempt_1.partial.txt').read_text() == 'partial'
    assert body.closed and all(c.is_closed() for c in clients)


def test_truncated_stream_is_not_retried(tmp_path):
    from zerorepo.rpg_gen.base.llm_client.errors import LLMResponseTruncatedError
    async def handler(request):
        return httpx.Response(200, headers={'content-type': 'text/event-stream'}, content=wire('partial', 'length'))
    run, clients, _ = bounded(tmp_path, handler)
    with pytest.raises(LLMResponseTruncatedError):
        run()
    assert len(clients) == 1 and clients[0].is_closed()


def test_retry_exhaustion_keeps_diagnostics(tmp_path, monkeypatch):
    monkeypatch.setattr('zerorepo.rpg_gen.base.llm_client.providers.bounded_completion.random.uniform', lambda *_: 0.001)
    async def handler(request):
        return httpx.Response(503, json={'error': {'type': 'unavailable', 'code': 'busy'}})
    run, clients, snapshots = bounded(tmp_path, handler, total_timeout_seconds=2)
    with pytest.raises(LLMRequestError):
        run()
    assert len(clients) == 2 and all(c.is_closed() for c in clients)
    assert snapshots[-1]['http_status'] == 503 and snapshots[-1]['attempt'] == 2


class FiniteTrackedBody(httpx.AsyncByteStream):
    def __init__(self, data):
        self.data = data
        self.closed = False

    async def __aiter__(self):
        yield self.data

    async def aclose(self):
        self.closed = True


def stream_error(**fields):
    return ('data: ' + json.dumps({'error': {'message': 'test-secret', **fields}}) + '\n\n').encode()


@pytest.mark.parametrize('field', ['type', 'code'])
def test_stream_upstream_error_retries_from_scratch_and_preserves_headers(tmp_path, monkeypatch, field):
    monkeypatch.setattr('zerorepo.rpg_gen.base.llm_client.providers.bounded_completion.random.uniform', lambda *_: 0.001)
    bodies = []
    async def handler(request):
        attempt = len(bodies) + 1
        data = wire('discarded-partial') + stream_error(**{field: 'upstream_error'}) if attempt == 1 else wire('OK', 'stop') + b'data: [DONE]\n\n'
        body = FiniteTrackedBody(data)
        bodies.append(body)
        return httpx.Response(200, headers={'content-type': 'text/event-stream', 'x-request-id': f'upstream-{attempt}'}, stream=body)
    run, clients, snapshots = bounded(tmp_path, handler, total_timeout_seconds=2)
    assert run().choices[0].message.content == 'OK'
    assert len(bodies) == 2 and all(b.closed for b in bodies) and all(c.is_closed() for c in clients)
    retry = next(s for s in snapshots if s['status'] == 'retrying')
    assert retry['http_status'] == 200 and retry['server_request_id'] == 'upstream-1'
    assert retry[f'server_error_{field}'] == 'upstream_error'
    assert snapshots[-1]['server_request_id'] == 'upstream-2' and 'server_error_type' not in snapshots[-1]
    status_file = next(tmp_path.glob('stage3_module_skeletons/toy/*/status.json'))
    assert status_file.with_name('attempt_1.partial.txt').read_text() == 'discarded-partial'
    assert status_file.with_name('attempt_2.partial.txt').read_text() == 'OK'
    assert 'test-secret' not in json.dumps(snapshots)


def test_stream_upstream_error_retry_exhaustion_retains_last_attempt_metadata(tmp_path, monkeypatch):
    monkeypatch.setattr('zerorepo.rpg_gen.base.llm_client.providers.bounded_completion.random.uniform', lambda *_: 0.001)
    bodies = []
    async def handler(request):
        attempt = len(bodies) + 1
        body = FiniteTrackedBody(wire(f'partial-{attempt}') + stream_error(type='upstream_error', code='temporary'))
        bodies.append(body)
        return httpx.Response(200, headers={'content-type': 'text/event-stream', 'x-request-id': f'upstream-{attempt}'}, stream=body)
    run, clients, snapshots = bounded(tmp_path, handler, total_timeout_seconds=2)
    with pytest.raises(LLMRequestError) as failure:
        run()
    assert len(bodies) == 2 and all(b.closed for b in bodies) and all(c.is_closed() for c in clients)
    assert snapshots[-1]['attempt'] == 2 and snapshots[-1]['status'] == 'failed'
    assert failure.value.diagnostics['http_status'] == 200
    assert failure.value.diagnostics['server_request_id'] == 'upstream-2'
    assert failure.value.diagnostics['server_error_type'] == 'upstream_error'
    assert failure.value.diagnostics['waiting_phase'] == 'streaming'
    status_file = next(tmp_path.glob('stage3_module_skeletons/toy/*/status.json'))
    assert status_file.with_name('attempt_1.partial.txt').read_text() == 'partial-1'
    assert status_file.with_name('attempt_2.partial.txt').read_text() == 'partial-2'
    assert 'test-secret' not in str(failure.value)


def test_stream_upstream_retry_backoff_cannot_exceed_total_budget(tmp_path, monkeypatch):
    monkeypatch.setattr('zerorepo.rpg_gen.base.llm_client.providers.bounded_completion.random.uniform', lambda *_: 10)
    body = FiniteTrackedBody(wire('partial') + stream_error(type='upstream_error'))
    async def handler(request):
        return httpx.Response(200, headers={'content-type': 'text/event-stream', 'x-request-id': 'initial'}, stream=body)
    run, clients, snapshots = bounded(tmp_path, handler, total_timeout_seconds=0.2)
    with pytest.raises(LLMRequestTimeoutError):
        run()
    assert len(clients) == 1 and clients[0].is_closed() and body.closed
    assert snapshots[-1]['waiting_phase'] == 'retry_delay' and snapshots[-1]['timeout_reason'] == 'total_timeout'
    assert snapshots[-1]['server_request_id'] == 'initial'


def test_unknown_stream_api_error_is_not_retried_and_keeps_headers(tmp_path):
    body = FiniteTrackedBody(wire('partial') + stream_error(type='unknown_error', code='unknown'))
    async def handler(request):
        return httpx.Response(200, headers={'content-type': 'text/event-stream', 'x-request-id': 'initial'}, stream=body)
    run, clients, snapshots = bounded(tmp_path, handler, total_timeout_seconds=2)
    with pytest.raises(LLMRequestError):
        run()
    assert len(clients) == 1 and clients[0].is_closed() and body.closed
    assert snapshots[-1]['http_status'] == 200 and snapshots[-1]['server_request_id'] == 'initial'


def test_authentication_error_is_not_retried_even_with_upstream_error_code(tmp_path):
    async def handler(request):
        return httpx.Response(401, json={'error': {'type': 'upstream_error'}})
    run, clients, snapshots = bounded(tmp_path, handler, total_timeout_seconds=2)
    with pytest.raises(LLMRequestError):
        run()
    assert len(clients) == 1 and clients[0].is_closed() and snapshots[-1]['http_status'] == 401


def test_low_throughput_is_visible_in_progress(tmp_path):
    body = WaitingBody(trickle=True)
    async def handler(request):
        return httpx.Response(200, headers={'content-type': 'text/event-stream'}, stream=body)
    run, _, snapshots = bounded(tmp_path, handler, slow_chars_per_second=10000)
    with pytest.raises(LLMRequestTimeoutError):
        run()
    assert any(s['slow'] for s in snapshots)


def test_stage3_skeleton_timeout_reuses_independent_retrieval_after_restart(tmp_path):
    from test_rtl_module_planner import (make_task_input, make_module_spec_files, make_stage1_contract_artifact,
        build_module_organized_artifact, make_repo_skeleton_payload)
    from zerorepo.rtl_impl.module_planner.agents import Stage3Agent
    from zerorepo.rtl_impl.module_planner.schemas import Stage2RepoSkeletonArtifact
    task, md, images = make_task_input(tmp_path)
    make_module_spec_files(tmp_path)
    modules = build_module_organized_artifact(make_stage1_contract_artifact(md, images))
    stage2 = Stage2RepoSkeletonArtifact.model_validate(make_repo_skeleton_payload())
    class Backend:
        def __init__(self):
            self.retrieval_calls = 0
            self.generation_calls = 0
        def complete(self, *, system_prompt, user_prompt, images=None):
            self.retrieval_calls += 1
            candidates = json.loads(user_prompt.split('[SOURCE_CHUNKS]\n')[1])
            module = user_prompt.split('[MODULE_NAME]\n')[1].splitlines()[0]
            return {'module': module, 'selections': [{'source_chunk_id': candidates[0]['chunk_id']}]}
        def complete_with_memory(self, *, memory, images=None):
            self.generation_calls += 1
            raise LLMRequestTimeoutError('generation deadline')
    first = Backend()
    root = tmp_path / 'outputs'
    with pytest.raises(LLMRequestTimeoutError):
        Stage3Agent(PlannerLLMClient(backend=first), output_root=root).run_incremental(task,
            {'modules': modules, 'stage2': stage2})
    assert first.retrieval_calls == first.generation_calls == 1
    second = Backend()
    with pytest.raises(LLMRequestTimeoutError):
        Stage3Agent(PlannerLLMClient(backend=second), output_root=root).run_incremental(task,
            {'modules': modules, 'stage2': stage2})
    assert second.retrieval_calls == 0 and second.generation_calls == 1
    assert not (root / 'module_skeleton_docs').exists()


@pytest.mark.parametrize('hard_error', [False, True])
def test_degraded_retrieval_preserves_quality_warning_and_hard_skeleton_checks(tmp_path, hard_error):
    from test_rtl_module_planner import (make_task_input, make_module_spec_files, make_stage1_contract_artifact,
        build_module_organized_artifact, make_repo_skeleton_payload, make_stage3_module_skeleton_doc)
    from zerorepo.rtl_impl.module_planner.agents import Stage3Agent
    from zerorepo.rtl_impl.module_planner.agents.base import StageGenerationError
    from zerorepo.rtl_impl.module_planner.schemas import Stage2RepoSkeletonArtifact
    task, md, images = make_task_input(tmp_path)
    top, key = make_module_spec_files(tmp_path)
    modules = build_module_organized_artifact(make_stage1_contract_artifact(md, images))
    stage2 = Stage2RepoSkeletonArtifact.model_validate(make_repo_skeleton_payload())
    class Backend:
        count = 0
        def complete(self, *, system_prompt, user_prompt, images=None):
            raise LLMRequestTimeoutError('retrieval deadline')
        def complete_with_memory(self, *, memory, images=None):
            self.count += 1
            if hard_error:
                return 'invalid skeleton'
            module, spec = ('aes_key_expand_128', key) if self.count == 1 else ('aes_cipher_top', top)
            return make_stage3_module_skeleton_doc(module, spec)
    agent = Stage3Agent(PlannerLLMClient(backend=Backend()), output_root=tmp_path/'outputs')
    arguments = (task, {'modules': modules, 'stage2': stage2})
    if hard_error:
        with pytest.raises(StageGenerationError):
            agent.run_incremental(*arguments)
    else:
        artifact = agent.run_incremental(*arguments)
        assert artifact.stage3_status == 'module_skeletons_planned'
        assert len([w for w in artifact.quality_report.warnings if w.startswith('retrieval_degraded:')]) == 2
        assert artifact.quality_report.soft_warning_count == len(artifact.quality_report.warnings)


def test_optional_request_policy_reaches_callable_custom_backend():
    seen = []
    def custom(*, system_prompt, user_prompt, images=None, request_options=None):
        seen.append(request_options)
        return 'OK'
    llm = PlannerLLMClient(backend=custom)
    options = llm.request_options(stage='stage3_test', module='toy', retrieval=True)
    assert llm.complete(system_prompt='test', user_prompt='test', request_options=options) == 'OK'
    assert seen == [options] and options.total_timeout_seconds == 180
