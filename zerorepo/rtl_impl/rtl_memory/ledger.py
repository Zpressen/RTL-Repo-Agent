"""Small immutable causal-memory ledger. Only trusted maintainers approve it."""
from __future__ import annotations
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as f: f.write(canonical(data)+'\n')
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,239}', value) or '..' in value:
        raise ValueError('Invalid memory identifier')
    return value


def content_digest(memory):
    return digest({k: memory[k] for k in ('title', 'lesson', 'applicability', 'limitations')})


class MemoryLedger:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)

    @contextmanager
    def transaction(self):
        with (self.root/'ledger.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            path = self.root/'index.json'
            state = json.loads(path.read_text()) if path.exists() else {'revisions':[], 'events':[]}
            yield state
            atomic(path, state)

    def get(self, revision_id):
        path = self.root/'revisions'/(identifier(revision_id)+'.json')
        if path.is_symlink() or not path.is_file(): raise ValueError('Unknown revision')
        data = json.loads(path.read_text())
        expected = 'revision-' + digest({k:v for k,v in data.items() if k != 'revision_id'})
        if expected != revision_id or content_digest(data) != data['content_sha256']: raise ValueError('Memory revision changed')
        return data

    def add(self, value, dry_run=False):
        allowed = {'memory_id','case_id','scope','owner','project','title','lesson','applicability','limitations','source_run_id','source_version_id','backend','evidence_refs','parent_revision_id','validation_level','content_sha256','revision_id'}
        if set(value)-allowed: raise ValueError('Unknown memory field')
        data = dict(value)
        for key in ['memory_id','source_run_id']: identifier(data[key])
        if data.get('scope') not in {'private_session','project','public_reviewed'}: raise ValueError('Invalid scope')
        if data['scope'] == 'private_session' and not data.get('owner'): raise ValueError('Missing owner')
        if data['scope'] == 'project' and not data.get('project'): raise ValueError('Missing project')
        if data['scope'] == 'public_reviewed' and data.get('owner'): raise ValueError('Private owner cannot be published implicitly')
        for key, default in [('applicability',[]),('limitations',[]),('evidence_refs',[]),('parent_revision_id',None),('source_version_id',None),('validation_level','unverified')]: data.setdefault(key,default)
        if not isinstance(data.get('title'),str) or not isinstance(data.get('lesson'),str) or len(data['lesson']) > 8000: raise ValueError('Invalid memory content')
        if re.search(r'sk-[A-Za-z0-9_-]{16,}|-----BEGIN .*PRIVATE KEY-----|/home/|/etc/', canonical(data)):
            raise ValueError('Private content in memory')
        expected_content = content_digest(data)
        if data.get('content_sha256') and data['content_sha256'] != expected_content: raise ValueError('Content mismatch')
        data['content_sha256'] = expected_content
        supplied = data.pop('revision_id',None)
        data['revision_id'] = 'revision-' + digest(data)
        if supplied and supplied != data['revision_id']: raise ValueError('Revision mismatch')
        if dry_run:
            if data['parent_revision_id']:
                old=self.get(data['parent_revision_id'])
                if any(old.get(k)!=data.get(k) for k in ['memory_id','scope','owner','project','case_id']) or old['content_sha256']==expected_content:
                    raise ValueError('Invalid parent revision')
            return data
        with self.transaction() as index:
            parent = data['parent_revision_id']
            if parent:
                old = self.get(parent)
                if any(old.get(k)!=data.get(k) for k in ['memory_id','scope','owner','project','case_id']): raise ValueError('Foreign parent revision')
                if old['content_sha256'] == expected_content: raise ValueError('No substantive revision')
            path = self.root/'revisions'/(data['revision_id']+'.json')
            if path.exists():
                if self.get(data['revision_id']) != data: raise ValueError('Immutable memory conflict')
            else: atomic(path,data)
            if data['revision_id'] not in index['revisions']: index['revisions'].append(data['revision_id'])
        return data

    def review(self, revision_id, kind, reason, evidence_refs, replacement=None, dry_run=False):
        if kind not in {'approved','superseded','retired'} or not reason or not evidence_refs:
            raise ValueError('Review and evidence required')
        current = self.get(revision_id)
        if kind == 'superseded':
            child = self.get(replacement)
            if child.get('parent_revision_id') != revision_id: raise ValueError('Unrelated replacement')
        event = dict(revision_id=revision_id, kind=kind, reason=reason, evidence_refs=evidence_refs, replacement_revision_id=replacement)
        event['event_id']='lifecycle-'+digest(event)
        def validate(index):
            previous = [e for e in index['events'] if e['revision_id']==revision_id]
            if previous and previous[-1]['kind'] in {'superseded','retired'} and event not in previous:
                raise ValueError('Retired revision cannot become active')
        if dry_run:
            validate(self.state())
            return event
        with self.transaction() as index:
            validate(index)
            if event not in index['events']: index['events'].append(event)
        return event

    def state(self):
        path=self.root/'index.json'
        return json.loads(path.read_text()) if path.exists() else {'revisions':[], 'events':[]}

    def approved(self, case_id, owner, project=None):
        state = self.state(); latest = {e['revision_id']:e['kind'] for e in state['events']}
        result = []
        for rid in state['revisions']:
            memory = self.get(rid)
            authorized = memory['scope']=='public_reviewed' or (memory['scope']=='private_session' and owner and memory.get('owner')==owner) or (memory['scope']=='project' and project and memory.get('project')==project)
            if authorized and memory['case_id']==case_id and latest.get(rid)=='approved': result.append(memory)
        return result
