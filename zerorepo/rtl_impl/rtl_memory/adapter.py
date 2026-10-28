"""Frozen task-local memory access and objective use accounting."""
from __future__ import annotations
import json
from pathlib import Path, PurePosixPath
from .ledger import atomic, digest, identifier, content_digest


def freeze_snapshot(ledger, case_id, owner, out, context, limit=5):
    memories = ledger.approved(case_id,owner) if ledger else []
    # Reuse the existing selector's deterministic ranking without another model call.
    if memories:
        from .selector import RTLMemorySelector
        from .schemas import RTLMemoryHeader
        mapping = {m['revision_id']: m for m in memories}
        headers = [RTLMemoryHeader(memory_id=m['memory_id'],type='repair_outcome',stage='debug',module=str(context.get('module','')),description=m['title'],path=m['revision_id']) for m in memories]
        ranked = RTLMemorySelector._fallback_rank(None, context, headers, limit=limit)
        memories = [mapping[h.path] for h in ranked]
    # Ownership never crosses the trusted snapshot boundary into tool responses.
    snapshot = dict(schema_version='rtl-memory-snapshot-v1', case_id=case_id,
                    selector='rtl-memory-fallback-v1', memories=[{k:v for k,v in m.items() if k not in {'owner','project','scope'}} for m in memories[:limit]])
    path = Path(out)/'snapshot.json'; atomic(path, snapshot)
    return path, digest(snapshot)


class MemoryAdapter:
    def __init__(self, snapshot_path, expected_digest, root, outer_run_id, internal_run_id):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.outer_run_id=outer_run_id;self.internal_run_id=internal_run_id
        value=json.loads(Path(snapshot_path).read_text())
        if digest(value)!=expected_digest:raise ValueError('Memory snapshot changed')
        self.snapshot_sha256=expected_digest
        self.memories={m['revision_id']:m for m in value['memories']}
        for m in self.memories.values():
            if content_digest(m)!=m['content_sha256']:raise ValueError('Memory content changed')
        self.pending_path=self.root/'declarations.json'

    def events(self):
        events=[json.loads(p.read_text()) for p in (self.root/'events').glob('*.json')]
        return sorted(events,key=lambda e:e['sequence'])

    def emit(self, kind, revision_id, **proof):
        self.get(revision_id)
        body=dict(kind=kind,revision_id=revision_id,outer_run_id=self.outer_run_id,
                  internal_run_id=self.internal_run_id,snapshot_sha256=self.snapshot_sha256,**proof)
        event_id='memory-event-'+digest(body)
        path=self.root/'events'/(event_id+'.json')
        if path.exists():return json.loads(path.read_text())
        body.update(event_id=event_id,sequence=len(self.events())+1)
        atomic(path,body);return body

    def get(self, revision_id):
        identifier(revision_id)
        if revision_id not in self.memories:raise ValueError('Memory is outside this task snapshot')
        return self.memories[revision_id]

    def query(self, module_name=None, signals=None, failure_type=None, limit=5):
        if not isinstance(limit,int) or not 1<=limit<=5:raise ValueError('Memory query budget')
        if module_name is not None and (not isinstance(module_name,str) or len(module_name)>240):raise ValueError('Invalid module')
        if signals is not None and (not isinstance(signals,list) or len(signals)>100 or any(not isinstance(v,str) or len(v)>240 for v in signals)):raise ValueError('Invalid signals')
        if failure_type is not None and (not isinstance(failure_type,str) or len(failure_type)>240):raise ValueError('Invalid failure type')
        terms=[str(v).lower() for v in [module_name,failure_type,*(signals or [])] if v]
        ranked=sorted(self.memories.values(),key=lambda m:sum(t in json.dumps(m,ensure_ascii=False).lower() for t in terms),reverse=True)
        result=[]
        for m in ranked[:limit]:
            self.emit('retrieved',m['revision_id'])
            result.append({k:m[k] for k in ['revision_id','title','applicability','limitations','backend']})
        return dict(memories=result)

    def read(self, revision_id, max_chars=8000):
        if not isinstance(max_chars,int) or not 1<=max_chars<=8000:raise ValueError('Memory read budget')
        m=self.get(revision_id)
        result={k:m[k] for k in ['revision_id','title','lesson','applicability','limitations','backend','evidence_refs']}
        result['lesson']=result['lesson'][:max_chars]
        self.emit('provided',revision_id,response_sha256=digest(result))
        return result

    def declare(self, revision_id, decision, reason, target_files, target_signals):
        self.get(revision_id)
        if decision not in {'apply','reject','not_applicable'} or not isinstance(reason,str) or not 1<=len(reason)<=2000:raise ValueError('Invalid application declaration')
        if not isinstance(target_files,list) or not isinstance(target_signals,list) or len(target_files)>30 or len(target_signals)>100:raise ValueError('Application budget')
        if any(not isinstance(v,str) or len(v)>240 for v in target_files+target_signals):raise ValueError('Invalid application target')
        for value in target_files:
            p=PurePosixPath(value)
            if p.is_absolute() or '..' in p.parts or '\\' in value or not value or len(value)>240:raise ValueError('Unsafe application target')
        if decision=='apply' and not any(e['kind']=='provided' and e['revision_id']==revision_id for e in self.events()):raise ValueError('Memory not provided')
        pending=json.loads(self.pending_path.read_text()) if self.pending_path.exists() else {}
        pending[revision_id]=dict(decision=decision,reason=reason,target_files=target_files,target_signals=target_signals)
        atomic(self.pending_path,pending)
        return self.emit('application_declared',revision_id,**pending[revision_id])

    def observe(self, candidate_id, diff, tree_sha256, verdict, **binding):
        pending=json.loads(self.pending_path.read_text()) if self.pending_path.exists() else {}
        changed=set(diff.get('modified',[])+diff.get('added',[])+diff.get('removed',[]))
        for rid,declaration in pending.items():
            targets=changed & set(declaration['target_files'])
            if declaration['decision']!='apply' or not targets:continue
            self.emit('applied',rid,candidate_id=candidate_id,tree_sha256=tree_sha256,
                      diff_sha256=digest(diff),target_files=sorted(targets),reason=declaration['reason'])
            self.emit('validation_observed',rid,candidate_id=candidate_id,tree_sha256=tree_sha256,verdict=verdict,**binding)
        atomic(self.pending_path,{})

    def disposition(self,candidate_id,decision):
        for event in self.events():
            if event['kind']=='applied' and event.get('candidate_id')==candidate_id:
                observed = [e for e in self.events() if e['kind']=='validation_observed' and e.get('candidate_id')==candidate_id and e['revision_id']==event['revision_id']]
                last = observed[-1] if observed else {}
                self.emit('validation_observed',event['revision_id'],candidate_id=candidate_id,disposition=decision,verdict=last.get('verdict','unverified'),tree_sha256=event.get('tree_sha256'))

    def final_validation(self, tree_sha256, verdict, report_sha256, verifier_fingerprint):
        events=self.events()
        accepted={e.get('candidate_id') for e in events if e.get('disposition')=='accepted'}
        rolled_back={e.get('candidate_id') for e in events if e.get('disposition')=='rolled_back'}
        for e in events:
            if e['kind']=='applied' and e.get('tree_sha256')==tree_sha256 and e.get('candidate_id') in accepted-rolled_back:
                self.emit('validation_observed',e['revision_id'],candidate_id=e['candidate_id'],tree_sha256=tree_sha256,
                          verdict=verdict,report_sha256=report_sha256,verifier_fingerprint=verifier_fingerprint,validation_level='final_system')
