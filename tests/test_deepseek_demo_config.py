import json
from types import SimpleNamespace

import httpx
import openai

from zerorepo.rpg_gen.base.llm_client import LLMClient, LLMConfig, Memory, UserMessage
from zerorepo.rpg_gen.base.llm_client.providers.openai_client import OpenAIProvider


def test_openai_compatible_deepseek_forwards_selected_parameters(monkeypatch):
    sent=[]
    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200,json={'id':'synthetic','object':'chat.completion','created':0,
            'model':'deepseek-v4-pro','choices':[{'index':0,'message':{'role':'assistant','content':'{"kind":"answer","text":"ok"}'},'finish_reason':'stop'}]})
    monkeypatch.setattr(OpenAIProvider,'create_client',lambda self,cfg:openai.OpenAI(
        api_key='synthetic-test-key',http_client=httpx.Client(transport=httpx.MockTransport(handler))))
    cfg=LLMConfig.from_dict({'provider':'openai','model':'deepseek-v4-pro','max_tokens':65536,
        'temperature':0.6,'reasoning_effort':'high','base_url':'https://api.deepseek.com','log':False})
    memory=Memory();memory.add_message(UserMessage(content='Return JSON.'))
    LLMClient(cfg).generate(memory)
    assert sent[0]['reasoning_effort']=='high'
    assert sent[0]['max_tokens']==65536
    assert sent[0]['temperature']==0.6


def test_demo_chat_respects_configured_token_budget(monkeypatch):
    from zerorepo.rtl_web import chat_runtime,runtime
    cfg=LLMConfig.from_dict({'model':'deepseek-v4-pro','max_tokens':65536})
    monkeypatch.setattr(runtime,'load_agent',lambda settings:({},cfg))
    def generate(self,*args,**kwargs):
        assert self.config.max_tokens==65536
        return '{"kind":"answer","text":"ok","evidence_refs":[]}'
    monkeypatch.setattr(LLMClient,'generate',generate)
    # No network client is needed to verify the request configuration.
    monkeypatch.setattr(LLMClient,'__init__',lambda self,config:setattr(self,'config',config))
    result=chat_runtime.answer(SimpleNamespace(runtime={'chat_max_tokens':65536}),{'text':'Explain','evidence':{}})
    assert result['text']=='ok'


def test_quick_chat_disables_thinking_without_changing_repair_settings(monkeypatch):
    from zerorepo.rtl_web import chat_runtime, runtime
    cfg = LLMConfig.from_dict({'model': 'deepseek-v4-pro', 'max_tokens': 65536,
                              'base_url': 'https://api.deepseek.com', 'reasoning_effort': 'high'})
    monkeypatch.setattr(runtime, 'load_agent', lambda settings: ({}, cfg))
    captured = []
    def generate(self, *args, **kwargs):
        captured.append(self.config)
        return '{"kind":"answer","text":"quick","evidence_refs":[]}'
    monkeypatch.setattr(LLMClient, 'generate', generate)
    monkeypatch.setattr(LLMClient, '__init__', lambda self, config: setattr(self, 'config', config))
    chat_runtime.answer(SimpleNamespace(runtime={'chat_max_tokens': 4096, 'chat_thinking': False}),
                        {'text': 'Explain', 'evidence': {}})
    assert captured[0].max_tokens == 4096
    assert captured[0].extra['extra_body']['thinking'] == {'type': 'disabled'}
    assert 'reasoning_effort' not in captured[0].extra


def test_deepseek_thinking_toggle_is_forwarded_in_request_body(monkeypatch):
    sent = []
    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={'id': 'synthetic', 'object': 'chat.completion', 'created': 0,
            'model': 'deepseek-v4-pro', 'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'ok'}, 'finish_reason': 'stop'}]})
    monkeypatch.setattr(OpenAIProvider, 'create_client', lambda self, cfg: openai.OpenAI(
        api_key='synthetic-test-key', http_client=httpx.Client(transport=httpx.MockTransport(handler))))
    cfg = LLMConfig.from_dict({'provider': 'openai', 'model': 'deepseek-v4-pro', 'max_tokens': 4096,
        'extra_body': {'thinking': {'type': 'disabled'}}, 'log': False})
    memory = Memory(); memory.add_message(UserMessage(content='Return JSON.'))
    LLMClient(cfg).generate(memory)
    assert sent[0]['thinking'] == {'type': 'disabled'}


def test_chat_receipt_uses_sdk_usage_not_model_authored_claims(monkeypatch):
    from zerorepo.rtl_web import chat_runtime, runtime
    cfg = LLMConfig.from_dict({'provider': 'openai', 'model': 'deepseek-v4-pro', 'max_tokens': 4096,
                              'base_url': 'https://api.deepseek.com', 'log': False})
    monkeypatch.setattr(runtime, 'load_agent', lambda settings: ({}, cfg))
    def handler(request):
        return httpx.Response(200, json={'id': 'synthetic-sdk-response', 'object': 'chat.completion', 'created': 0,
            'model': 'deepseek-v4-pro', 'usage': {'prompt_tokens': 123, 'completion_tokens': 45, 'total_tokens': 168},
            'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': '{"kind":"answer","text":"mock model content","evidence_refs":[]}'}, 'finish_reason': 'stop'}]})
    monkeypatch.setattr(OpenAIProvider, 'create_client', lambda self, cfg: openai.OpenAI(
        api_key='synthetic-test-key', http_client=httpx.Client(transport=httpx.MockTransport(handler))))
    result = chat_runtime.answer(SimpleNamespace(runtime={'chat_thinking': False, 'chat_max_tokens': 4096}),
                                 {'text': 'Explain', 'evidence': {}})
    assert result['text'] == 'mock model content'
    assert result['_model_receipt']['input_tokens'] == 123
    assert result['_model_receipt']['output_tokens'] == 45
    assert result['_model_receipt']['total_tokens'] == 168
    assert result['_model_receipt']['model'] == 'deepseek-v4-pro'
