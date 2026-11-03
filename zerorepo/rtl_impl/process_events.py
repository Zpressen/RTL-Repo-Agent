"""Optional public process events; raw model reasoning never enters this schema."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import threading
import time
from uuid import uuid4
from datetime import datetime, timezone


def now():
    return datetime.now(timezone.utc).isoformat()

PUBLIC_TOOLS=frozenset({'read_context','search_context','read_spec','retrieve_spec_block','read_module_semantics','list_vcd_signals','probe_vcd','trace_signal_cause','query_rtl_kg','run_check','apply_patch','replace_block'})


def clock_epoch():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def source_clock():
    return {'clock_epoch':clock_epoch(),'source_monotonic_ns':str(time.monotonic_ns())}


class NullProcessEventSink:
    def emit(self, event_type, **fields):
        return None


def public_projection(row):
    allowed = {'event_type','action_id','parent_action_id','stage','status','source_stream_id',
               'producer_epoch','source_seq','clock_epoch','source_monotonic_ns','occurred_at',
               'source_kind','purpose_summary','result_summary','public_progress','context_refs','artifact_refs','substage','tool','elapsed_ms','plan_revision_id','plan_items','reason_code'}
    data = {key:value for key,value in row.items() if key in allowed}
    if not re.fullmatch(r'[a-z][a-z_]*\.[a-z][a-z_]*', str(data.get('event_type',''))):
        raise ValueError('Invalid process event type')
    if data.get('stage') not in {None,'spec','architecture','rtl','syntax','verify','diagnose','repair','complete'}:
        raise ValueError('Invalid stage')
    data['source_kind'] = data.get('source_kind','runtime_observation')
    if 'tool' in data and data['tool'] not in PUBLIC_TOOLS:raise ValueError('Invalid public tool label')
    if 'elapsed_ms' in data and (type(data['elapsed_ms']) is not int or data['elapsed_ms']<0):raise ValueError('Invalid elapsed time')
    if 'plan_items' in data:
        if not isinstance(data['plan_items'],list) or len(data['plan_items'])>40:raise ValueError('Invalid plan items')
        projected=[]
        for item in data['plan_items']:
            if not isinstance(item,dict) or item.get('stage') not in {'spec','architecture','rtl','syntax','verify','diagnose','repair','complete'} or item.get('status') not in {'planned','conditional','running','completed','failed','skipped'}:raise ValueError('Invalid plan item')
            if not re.fullmatch(r'[\w-]{1,160}',str(item.get('item_id',''))):raise ValueError('Invalid plan identity')
            projected.append({k:str(item[k])[:160] for k in ('item_id','stage','status','title') if k in item})
        data['plan_items']=projected
    if data['source_kind'] not in {'runtime_observation','agent_public_summary','posthoc_explanation','mechanism_illustration'}:
        raise ValueError('Invalid event source')
    secrets = [v for k,v in os.environ.items() if re.search('KEY|PASSWORD|TOKEN',k) and len(v)>=8]
    for key, limit in [('purpose_summary',600),('result_summary',1800)]:
        if key in data:
            text = str(data[key])[:limit]
            for secret in secrets:
                text = text.replace(secret,'[redacted]')
            text = re.sub(r'(?<![\w])/(?:home|tmp|opt|root|etc)/\S+', '[private path]', text)
            data[key] = text
    if 'public_progress' in data:
        if not isinstance(data['public_progress'],dict):raise ValueError('Invalid public progress')
        public={}
        for key in ('summary','plan','findings','decisions'):
            value=data['public_progress'].get(key)
            values=[value] if key=='summary' else value
            if not isinstance(values,list):continue
            cleaned=[]
            for item in values[:3]:
                if not isinstance(item,str):continue
                item=item[:600 if key=='summary' else 300]
                for secret in secrets:item=item.replace(secret,'[redacted]')
                item=re.sub(r'(?<![\w])/(?:home|tmp|opt|root|etc)/\S+','[private path]',item)
                if item.strip():cleaned.append(item)
            if cleaned:public[key]=cleaned[0] if key=='summary' else cleaned
        data['public_progress']=public
    refs = data.get('context_refs',{})
    data['context_refs'] = {k:v for k,v in refs.items() if k in {'version_id','check_id','candidate_id','projection_id','module_ref','block_ref','subtask_ref','kg_revision','evidence_revision'} and isinstance(v,str) and re.fullmatch(r'[\w.:-]{1,240}',v)}
    data['artifact_refs'] = [v for v in data.get('artifact_refs',[])[:16] if isinstance(v,str) and re.fullmatch(r'[\w.:-]{1,240}',v)]
    if len(json.dumps(data).encode()) > 16384:
        raise ValueError('Oversized process event')
    return data


class JsonlProcessEventSink:
    def __init__(self, path: Path, source_stream_id: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.stream = source_stream_id
        self.epoch = uuid4().hex
        self.sequence = 0
        self.lock = threading.Lock()

    def emit(self, event_type, **fields):
        # Capture before projection, lock contention and spool write.
        captured = source_clock()
        with self.lock:
            self.sequence += 1
            data = public_projection({**fields, **captured, 'event_type':event_type,
                                      'source_stream_id':self.stream,'producer_epoch':self.epoch,
                                      'source_seq':self.sequence,'occurred_at':now()})
            fd = os.open(self.path, os.O_WRONLY|os.O_APPEND|os.O_CREAT, 0o600)
            with os.fdopen(fd,'a') as stream:
                stream.write(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n')
                stream.flush()
                os.fsync(stream.fileno())
            return data
