"""Optional public action observer shared by planner and debug tools.

Only controlled labels and scalar outcomes are emitted. Prompts, arguments,
model responses and raw tool payloads remain with the existing private journal.
"""
from __future__ import annotations
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import inspect
import re
import time
from uuid import uuid4

_sink=ContextVar('rtl_public_process_sink',default=None)
_stage=ContextVar('rtl_public_process_stage',default='spec')
_parent=ContextVar('rtl_public_process_parent',default=None)


@contextmanager
def observe(sink,stage='spec'):
    token=_sink.set(sink);stage_token=_stage.set(stage)
    try:yield
    finally:_stage.reset(stage_token);_sink.reset(token)


def set_stage(stage):
    _stage.set(stage)


def is_observing():
    return _sink.get() is not None


def emit_public(event_type, **fields):
    sink = _sink.get()
    if sink is not None:
        sink.emit(event_type, stage=_stage.get(), **fields)


def public_emitter():
    """Capture the sink for a content callback running on a separate I/O thread."""
    sink, stage = _sink.get(), _stage.get()
    def emit(event_type, **fields):
        if sink is not None:sink.emit(event_type, **({'stage':stage} | fields))
    return emit


def observed(kind,label,*,stage=None,tool=None,summarize=None,registered_tool=True):
    """One source boundary; wrappers/bridges must not add duplicate observers."""
    def decorate(fn):
        def start(args,kwargs):
            sink=_sink.get()
            if sink is None:return None
            action='action-'+uuid4().hex;started=time.monotonic_ns()
            fields=dict(action_id=action,parent_action_id=_parent.get(),stage=stage or _stage.get(),purpose_summary=label)
            if kind == 'model':
                from .public_progress import current_step
                step = current_step()
                if step:
                    fields['action_id']=step['action_id']
                    fields.update(stage=step['stage'], purpose_summary=step['label'], substage=step['substage'])
                    if step['module']:fields['context_refs']={'module_ref':step['module']}
            if kind=='tool':
                if registered_tool:
                    fields['tool']=tool or fn.__name__
                else:
                    # Operations without an identifier in the public v1 tool
                    # catalog use substage. Its optional tool field stays
                    # absent, so an already-running worker can ingest these
                    # source events without a schema upgrade or restart.
                    fields['substage']=tool or fn.__name__
                bound=inspect.signature(fn).bind_partial(*args,**kwargs).arguments
                parts=[]
                for key in ('query_type','module_name','signal_name','mode','kind','target','top_module'):
                    value=bound.get(key)
                    if isinstance(value,str) and re.fullmatch(r'[A-Za-z_][\w.$:-]{0,100}',value):parts.append(value)
                if parts:fields['purpose_summary']=label+' · '+' / '.join(parts)
                module=bound.get('module_name') or bound.get('top_module') or getattr(getattr(bound.get('self'),'state',None),'module_name',None)
                if isinstance(module,str) and re.fullmatch(r'[A-Za-z_][\w.$:-]{0,100}',module):
                    fields['context_refs']={'module_ref':module}
                if isinstance(bound.get('time'),int):fields['purpose_summary']+=f' · t={bound["time"]}'
            sink.emit(kind+'.started',**fields)
            token=_parent.set(action)
            return sink,fields,started,token
        def finish(record,result=None,error=False,exception=None):
            if record is None:return result
            sink,fields,started,token=record
            try:
                failed=error or isinstance(result,dict) and (result.get('status') in {'error','failed','rejected','kg_unavailable','unavailable','unsupported','missing_vcd'} or result.get('success') is False)
                if kind=='tool' and isinstance(result,dict):
                    failed=failed or result.get('status') in {'fail','missing_target','tool_unavailable'} or result.get('is_pass') is False or result.get('verdict') in {'fail','unverified'} or result.get('execution_status') in {'error','timed_out','cancelled'}
                if kind=='tool' and isinstance(result,tuple) and result and type(result[0]) is bool:
                    failed=failed or not result[0]
                extra = {}
                summary = '动作未完成，请核对本轮报告。' if failed else label+'：已返回结果。'
                if failed and exception is not None:
                    from .public_progress import request_failure_summary
                    summary=request_failure_summary(exception) or summary
                if kind=='tool' and isinstance(result,dict) and not failed:
                    counts=[]
                    for key,name in [('rows','图谱记录'),('signals','信号'),('results','结果'),('candidates','候选原因')]:
                        if isinstance(result.get(key),list):counts.append(f'{len(result[key])}项{name}')
                    if counts:summary='实际返回'+'、'.join(counts)+'。'
                if kind=='tool' and not error and summarize is not None:
                    # A trusted projector returns counts/fixed labels only. It
                    # never serializes tool arguments, source code or responses.
                    summary=summarize(result)
                if kind == 'model' and not failed:
                    from .public_progress import split_public_result, artifact_result
                    result, progress, payload = split_public_result(result)
                    summary = artifact_result(payload)
                    if isinstance(payload,dict) and payload.get('plan_style') in {'conservative','balanced','modular'}:
                        style={'conservative':'保守方案','balanced':'均衡方案','modular':'模块化方案'}[payload['plan_style']]
                        fields['purpose_summary']+=' · '+style
                    if progress:
                        extra.update(public_progress=progress, source_kind='agent_public_summary')
                        summary = progress.get('summary') or summary
                sink.emit(kind+('.failed' if failed else '.completed'),**fields,status='failed' if failed else 'completed',
                    elapsed_ms=round((time.monotonic_ns()-started)/1000000),result_summary=summary,**extra)
                return result
            finally:_parent.reset(token)
        if inspect.iscoroutinefunction(fn):
            @wraps(fn)
            async def asynchronous(*args,**kwargs):
                record=start(args,kwargs)
                try:result=await fn(*args,**kwargs)
                except BaseException as exc:finish(record,error=True,exception=exc);raise
                return finish(record,result)
            return asynchronous
        @wraps(fn)
        def synchronous(*args,**kwargs):
            record=start(args,kwargs)
            try:result=fn(*args,**kwargs)
            except BaseException as exc:finish(record,error=True,exception=exc);raise
            return finish(record,result)
        return synchronous
    return decorate
