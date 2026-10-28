"""Portable private historical evidence. Never exports session or execution tables."""
from __future__ import annotations
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import sqlite3
import tempfile
from .artifacts import Artifacts, atomic_json, safe_path, sha, tree_manifest
from .store import Store, dump
from .cases import CASES
from .deployment_models import HistoricalSeed, RECORD_KINDS, relative_path

# SDC's seventeen recorded VCDs plus public indexes exceed the previous 512 MiB
# private archive allowance. This remains a bounded, administrator-only import;
# public ZIP and per-VCD parsing limits are independent and unchanged.
MAX_SEED_BYTES = 1024 * 1024**2


def _strings(value):
    if isinstance(value,str):
        yield value
    elif isinstance(value,dict):
        for key,child in value.items():
            if key=='source_run_id' and value.get('round_no') and value.get('origin')=='historical':continue
            yield from _strings(child)
    elif isinstance(value,list):
        for child in value: yield from _strings(child)


def _references(value):
    """Declared entity references must exist, including references in index JSON."""
    if isinstance(value,dict):
        if value.get('schema_version') == 'rtl-demo-story-v1':
            from .stories import story_references
            for kind, ident, expected in story_references(value): yield kind, ident
            return
        for key,child in value.items():
            # Archived import IDs differ from source provenance IDs. The latter
            # do not require importing another (possibly obsolete) run record.
            if key=='source_run_id' and value.get('round_no') and value.get('origin')=='historical':continue
            kind=None
            for candidate in ('artifact','validation','version','run'):
                if key==candidate+'_id' or key.endswith('_'+candidate+'_id'):
                    kind=candidate;break
            if kind and isinstance(child,str):yield kind,child
            if key in {'versions','validations','waveform_tile_artifact_ids'} and isinstance(child,list):
                kind={'versions':'version','validations':'validation','waveform_tile_artifact_ids':'artifact'}[key]
                for item in child:
                    if isinstance(item,str):yield kind,item
            yield from _references(child)
    elif isinstance(value,list):
        for child in value:yield from _references(child)


def _read_records(store):
    with store.connect() as c:
        return {(r['kind'],r['id']):{'kind':r['kind'],'id':r['id'],
                'owner':r['owner'],'payload':json.loads(r['payload'])}
                for r in c.execute('SELECT * FROM records')}


def _seed_id(data):
    value={k:v for k,v in data.items() if k!='seed_id'}
    return 'seed-'+hashlib.sha256(dump(value).encode()).hexdigest()


def _size(value):
    return value.stat().st_size if isinstance(value,Path) else len(value)


def _hash(value):
    return sha(value) if isinstance(value,Path) else hashlib.sha256(value).hexdigest()


def _audit_files(settings, expected):
    hashes=set()
    def visit(value):
        if isinstance(value,dict):
            for key,child in value.items():
                if key.endswith('sha256') and isinstance(child,str):hashes.add(child)
                visit(child)
        elif isinstance(value,list):
            for child in value:visit(child)
    visit(expected)
    if not settings.source.is_dir():return []
    result=[]
    names={'debug_sim_output.json','final_sim_output.json','debug_input_manifest.json'}
    for path in settings.source.rglob('*.json'):
        if path.name not in names or path.is_symlink() or sha(path) not in hashes:continue
        data=path.read_bytes()
        if re.search(rb'sk-[A-Za-z0-9_-]{16,}|-----BEGIN .*PRIVATE KEY-----',data):raise ValueError('Secret in historical audit')
        result.append((path.relative_to(settings.source).as_posix(),path))
    return sorted(result)


def export_seed(settings, out: Path):
    out=out.absolute()
    if out.exists(): raise ValueError('Output already exists')
    store=Store(settings.data)
    records=_read_records(store)
    by_id={}
    for key in records: by_id.setdefault(key[1],[]).append(key)
    cases={cid:settings.for_case(cid).bundle_id for cid in CASES}
    pending=[('bundle',ident) for ident in cases.values()]
    from .recorded_history import SUFFIX
    pending.extend(('bundle', ident + SUFFIX) for ident in cases.values() if ('bundle', ident + SUFFIX) in records)
    stories={cid:store.control('story:'+cid) for cid in CASES if store.control('story:'+cid)}
    pending.extend(('story',ident) for ident in stories.values())
    selected={}; file_paths={}; inputs=[]; evidence_hashes={}
    art=Artifacts(settings.data,store)
    with store.connect() as c:
        archived_inputs=[json.loads(r[0]) for r in c.execute('SELECT payload FROM historical_inputs')]
    while pending:
        key=pending.pop()
        if key in selected: continue
        row=records.get(key)
        if not row or row['owner'] is not None or row['kind'] not in RECORD_KINDS:
            raise ValueError('Missing or private historical reference')
        payload=row['payload']
        if row['kind'] in {'run','bundle'} and (payload.get('origin')!='historical' or payload.get('case_id') not in CASES):
            raise ValueError('Seed contains non-historical input')
        selected[key]={'kind':row['kind'],'id':row['id'],'payload':payload}
        refs=list(_strings(payload))
        if row['kind']=='story':
            from .stories import load_story, story_references
            load_story(store,row['id'])
            pending.extend((k,i) for k,i,_ in story_references(payload));refs=[]
        if row['kind']=='artifact':
            path=art.file(payload); relative_path(payload['storage_key'])
            file_paths[payload['storage_key']]=path
            if payload.get('kind') in {'waveform','waveform_tile'}:
                refs+=list(_strings(json.loads(path.read_text())))
        elif row['kind']=='version':
            root=art.version_path(payload)
            for entry in payload['file_manifest']:
                key_name=relative_path(payload['storage_key']+'/'+entry['path'])
                file_paths[key_name]=safe_path(root,entry['path'])
        for ident in refs:
            pending.extend(by_id.get(ident,[]))
    # Contracts are explicit private inputs, not inferred from a public bundle.
    for cid,bid in cases.items():
        selected_settings=settings.for_case(cid)
        b=records[('bundle',bid)]['payload']
        rid=b['source_run_id']
        path=selected_settings.source/'.zerorepo/module_planner/outputs/contracts.json'
        evidence=settings.repo/'configs'/('rtl_demo_e203.evidence.json' if cid=='e203' else 'rtl_demo_cases.evidence.json')
        expected=None
        if evidence.is_file():
            evidence_hashes[evidence.name]=sha(evidence)
            e=json.loads(evidence.read_text()); e=e if cid=='e203' else e[cid]
            expected=e.get('contracts_sha256')
        item={'case_id':cid,'run_id':rid,'kind':'contracts','artifact_id':None,'expected_sha256':expected,'status':'missing'}
        archived=next((i for i in archived_inputs if i['case_id']==cid and i['run_id']==rid and i['kind']=='contracts' and i['status']=='present'),None)
        if archived:
            record=records.get(('artifact',archived['artifact_id']))
            if not record or record['owner'] is not None:raise ValueError('Invalid archived contract')
            path=art.file(record['payload'])
            if expected and sha(path)!=expected:raise ValueError('Archived contract source conflict')
            expected=archived['expected_sha256'];item['expected_sha256']=expected
        if expected:
            if not path.is_file() or path.is_symlink() or sha(path)!=expected:
                raise ValueError('Reviewed historical contracts missing or changed: '+cid)
            digest=sha(path); aid='artifact-contract-'+digest
            storage='artifacts/'+digest+'.contracts'
            item.update(artifact_id=aid,status='present')
            selected[('artifact',aid)]={'kind':'artifact','id':aid,'payload':{
                'artifact_id':aid,'kind':'contracts','sha256':digest,'source_sha256':digest,
                'size_bytes':path.stat().st_size,'storage_key':storage,'exposure':'private'}}
            file_paths[storage]=path
        inputs.append(item)
        audit=[]
        for name,src in _audit_files(selected_settings,e if evidence.is_file() else {}):
            h=sha(src);aid='artifact-audit-'+h;storage='artifacts/'+h+'.audit'
            selected[('artifact',aid)]={'kind':'artifact','id':aid,'payload':{
                'artifact_id':aid,'kind':'audit','sha256':h,'source_sha256':h,
                'size_bytes':src.stat().st_size,'storage_key':storage,'exposure':'private'}}
            file_paths[storage]=src;audit.append({'source_relative_path':name,'artifact_id':aid,'sha256':h})
        if audit:
            body=(dump({'files':audit})+'\n').encode();h=_hash(body);aid='artifact-audit-index-'+h;storage='artifacts/'+h+'.audit_index'
            selected[('artifact',aid)]={'kind':'artifact','id':aid,'payload':{
                'artifact_id':aid,'kind':'audit_index','sha256':h,'source_sha256':h,
                'size_bytes':len(body),'storage_key':storage,'exposure':'private'}}
            file_paths[storage]=body
            inputs.append({'case_id':cid,'run_id':rid,'kind':'audit','artifact_id':aid,'expected_sha256':h,'status':'present'})
        else:
            saved=next((i for i in archived_inputs if i['case_id']==cid and i['run_id']==rid and i['kind']=='audit'),None)
            if saved:
                pending=[saved['artifact_id']]
                while pending:
                    aid=pending.pop();r=records.get(('artifact',aid))
                    if not r or r['owner'] is not None:raise ValueError('Invalid audit reference')
                    selected[('artifact',aid)]={k:r[k] for k in ('kind','id','payload')}
                    p=art.file(r['payload']);file_paths[r['payload']['storage_key']]=p
                    if r['payload']['kind']=='audit_index':pending.extend(item['artifact_id'] for item in json.loads(p.read_text())['files'])
                inputs.append(saved)
    manifest={'schema_version':'rtl-demo-seed-v1','cases':cases,
              'records':[selected[k] for k in sorted(selected)],
              'files':[{'path':name,'size_bytes':_size(path),'sha256':_hash(path)} for name,path in sorted(file_paths.items())],
              'historical_inputs':inputs,'evidence_hashes':evidence_hashes,
              'total_bytes':sum(_size(p) for p in file_paths.values()),'export_tool_version':'1'}
    manifest['seed_id']=_seed_id(manifest)
    if stories:
        manifest.update(schema_version='rtl-demo-seed-v2', stories=stories)
        manifest['seed_id']=_seed_id(manifest)
    HistoricalSeed.model_validate(manifest)
    if manifest['total_bytes'] > MAX_SEED_BYTES:
        raise ValueError('Seed exceeds deployment budget')
    out.parent.mkdir(parents=True,exist_ok=True)
    tmp=Path(tempfile.mkdtemp(prefix='.seed-',dir=out.parent))
    try:
        os.chmod(tmp,0o700)
        for name,src in file_paths.items():
            dst=safe_path(tmp/'files',name);dst.parent.mkdir(parents=True,exist_ok=True)
            if isinstance(src,Path):shutil.copyfile(src,dst)
            else:dst.write_bytes(src)
            os.chmod(dst,0o600)
        atomic_json(tmp/'seed.json',manifest)
        validate_seed(tmp)
        tmp.rename(out)
    finally:
        if tmp.exists(): shutil.rmtree(tmp)
    return {'seed_id':manifest['seed_id'],'cases':cases,'record_count':len(selected),'file_count':len(file_paths),'total_bytes':manifest['total_bytes']}


def validate_seed(source: Path):
    source=source.absolute()
    if source.is_symlink(): raise ValueError('Symlink seed')
    if {p.name for p in source.iterdir()}!={'seed.json','files'}:raise ValueError('Unknown seed input')
    for path in source.rglob('*'):
        if path.is_symlink() or not (path.is_dir() or path.is_file()): raise ValueError('Unsafe seed entry')
        if path.is_file() and path.stat().st_nlink!=1: raise ValueError('Hardlink seed')
    data=json.loads((source/'seed.json').read_text())
    HistoricalSeed.model_validate(data)
    if data['total_bytes'] > MAX_SEED_BYTES:raise ValueError('Seed exceeds deployment budget')
    if data['seed_id']!=_seed_id(data) or set(data['cases'])!=set(CASES): raise ValueError('Seed manifest mismatch')
    if data['schema_version']=='rtl-demo-seed-v1' and 'stories' in data:raise ValueError('v1 cannot contain story roots')
    if set(data.get('stories') or {})-set(CASES):raise ValueError('Unknown story case')
    files={}; casefold=set(); size=0
    for f in data['files']:
        name=relative_path(f['path'])
        if name in files or name.casefold() in casefold or not name.startswith(('artifacts/','snapshots/')):
            raise ValueError('Duplicate or unknown seed file')
        casefold.add(name.casefold());p=safe_path(source/'files',name)
        if not p.is_file() or p.stat().st_size!=f['size_bytes'] or sha(p)!=f['sha256']: raise ValueError('Seed file mismatch')
        files[name]=f;size+=f['size_bytes']
    if size!=data['total_bytes']: raise ValueError('Seed size mismatch')
    if size>MAX_SEED_BYTES:raise ValueError('Seed exceeds deployment budget')
    actual={p.relative_to(source/'files').as_posix() for p in (source/'files').rglob('*') if p.is_file()}
    if actual!=set(files): raise ValueError('Unexpected seed file')
    records={}
    for r in data['records']:
        if set(r)!={'kind','id','payload'} or r['kind'] not in RECORD_KINDS: raise ValueError('Unknown seed record')
        if r['kind']=='story' and data['schema_version']!='rtl-demo-seed-v2':raise ValueError('v1 cannot contain stories')
        key=(r['kind'],r['id']);p=r['payload']
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,239}',r['id']):raise ValueError('Unsafe record ID')
        if p.get('owner_session'):raise ValueError('Private record payload')
        if key in records: raise ValueError('Duplicate seed record')
        if p.get(r['kind']+'_id')!=r['id']: raise ValueError('Record ID mismatch')
        if r['kind'] in {'run','bundle'} and (p.get('origin')!='historical' or p.get('case_id') not in CASES): raise ValueError('Nonhistorical record')
        if r['kind']=='artifact':
            f=files.get(p['storage_key'])
            if not f or f['sha256']!=p['sha256'] or f['size_bytes']!=p['size_bytes']: raise ValueError('Artifact binding mismatch')
        if r['kind']=='version':
            directory=safe_path(source/'files',p['storage_key'])
            if tree_manifest(directory)!=(p['tree_sha256'],p['file_manifest']): raise ValueError('Snapshot mismatch')
        records[key]=r
    by_id={}
    for k in records: by_id.setdefault(k[1],[]).append(k)
    from .stories import validate_story
    for cid, ident in (data.get('stories') or {}).items():
        record=records.get(('story',ident))
        if not record or record['payload']['case_id']!=cid:raise ValueError('Story root mismatch')
        story=record['payload']
        if story['material_kind']!='real' or story['review']['status']!='approved':raise ValueError('Unreviewed story seed')
        validate_story(story,lambda k,i:records[(k,i)]['payload'],lambda a:safe_path(source/'files',a['storage_key']))
    pending=[('bundle',bid) for bid in data['cases'].values()]+[('story',i) for i in (data.get('stories') or {}).values()];seen=set()
    from .recorded_history import SUFFIX
    for bid in data['cases'].values():
        key=('bundle',bid+SUFFIX)
        if key in records:
            extra=records[key]['payload'];base=records[('bundle',bid)]['payload']
            if extra.get('base_bundle_id')!=bid or any(extra.get(k)!=base.get(k) for k in ('case_id','source_fingerprint')):
                raise ValueError('Historical supplement binding mismatch')
            pending.append(key)
    for item in data['historical_inputs']:
        if item['case_id'] not in CASES or ('run',item['run_id']) not in records: raise ValueError('Contract run missing')
        if item['status']=='present':
            r=records.get(('artifact',item['artifact_id']))
            if not r or r['payload']['sha256']!=item['expected_sha256']: raise ValueError('Contract binding mismatch')
            pending.append(('artifact',item['artifact_id']))
    while pending:
        key=pending.pop()
        if key in seen: continue
        if key not in records: raise ValueError('Seed reference missing')
        seen.add(key);p=records[key]['payload']; refs=list(_strings(p))
        if key[0]=='story':pending.extend(_references(p));refs=[]
        if key[0]=='artifact' and p['kind'] in {'waveform','waveform_tile','audit_index'}:
            index=json.loads(safe_path(source/'files',p['storage_key']).read_text())
            refs+=list(_strings(index))
            if any(ref not in records for ref in _references(index)):raise ValueError('Missing index reference')
        if any(ref not in records for ref in _references(p)):raise ValueError('Missing record reference')
        for ident in refs: pending.extend(by_id.get(ident,[]))
        for field,kind in [('run_id','run'),('source_run_id','run'),('version_id','version'),('parent_version_id','version'),('report_artifact_id','artifact'),('waveform_artifact_id','artifact'),('waveform_index_artifact_id','artifact')]:
            if field=='source_run_id' and p.get('round_no') and p.get('origin')=='historical':continue
            if key[0] in {'bundle','run','version','validation'} and p.get(field) and (kind,p[field]) not in records: raise ValueError('Seed reference missing')
    if seen!=set(records): raise ValueError('Unreachable seed record')
    return data


def import_seed(settings,source: Path,dry_run=False):
    data=validate_seed(source)
    if dry_run: return {'seed_id':data['seed_id'],'dry_run':True,'record_count':len(data['records'])}
    # Validate conflicts before writing any evidence; repeat inside transaction.
    if (settings.data/'state.sqlite3').is_file():
        conn=sqlite3.connect(f'file:{settings.data / "state.sqlite3"}?mode=ro',uri=True)
        try:
            for row in data['records']:
                old=conn.execute('SELECT owner,payload FROM records WHERE kind=? AND id=?',(row['kind'],row['id'])).fetchone()
                if old and (old[0] is not None or old[1]!=dump(row['payload'])): raise ValueError('Immutable seed conflict')
        finally:conn.close()
    store=Store(settings.data)
    created=[]
    try:
        with store.connect(True) as c:
            store.register_seed(c,data)
            for cid in CASES:
                ident=(data.get('stories') or {}).get(cid)
                if ident:c.execute('INSERT INTO controls VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('story:'+cid,dump(ident)))
                else:c.execute('DELETE FROM controls WHERE key=?',('story:'+cid,))
            for f in data['files']:
                dst=safe_path(settings.data,f['path'])
                if dst.exists():
                    if dst.is_symlink() or sha(dst)!=f['sha256']: raise ValueError('Immutable file conflict')
                else:
                    dst.parent.mkdir(parents=True,exist_ok=True)
                    fd,name=tempfile.mkstemp(dir=dst.parent)
                    try:
                        with os.fdopen(fd,'wb') as out: out.write(safe_path(source/'files',f['path']).read_bytes())
                        os.replace(name,dst);created.append(dst)
                    finally:
                        if os.path.exists(name):os.unlink(name)
            for cid,bid in data['cases'].items():
                b=next(r['payload'] for r in data['records'] if r['kind']=='bundle' and r['id']==bid)
                dst=settings.data/'bundles'/bid/'manifest.json'
                if dst.exists() and json.loads(dst.read_text())!=b: raise ValueError('Immutable bundle conflict')
                if not dst.exists():atomic_json(dst,b);created.append(dst)
    except BaseException:
        for p in reversed(created): p.unlink(missing_ok=True)
        raise
    return {'seed_id':data['seed_id'],'dry_run':False,'record_count':len(data['records']),'file_count':len(data['files'])}
