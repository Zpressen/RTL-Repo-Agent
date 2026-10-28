"""Bounded, deterministic export of already-public historical engineering evidence."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import tempfile
import threading
import zipfile
from dataclasses import dataclass
from .artifacts import Artifacts, safe_path, sha, redact
from .schemas import DemoError

MAX_BYTES=64*1024*1024
MAX_ENTRIES=128
MAX_TEMP_BYTES=128*1024*1024
KINDS={'spec','planning','rtl','report','waveform','waveform_tile'}
IDENT=re.compile(r'[A-Za-z0-9_.-]{1,240}\Z')

def encoded(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode()

def relative(name):
    if not isinstance(name,str) or not name or '\\' in name or '\x00' in name or ':' in name or name.startswith('/') or any(x in {'','..','.'} for x in name.split('/')):
        raise DemoError('evidence_inconsistent','证据包文件名不安全。',409)
    return name

def public_bytes(data):
    try:text=data.decode('utf-8')
    except UnicodeError:raise DemoError('evidence_inconsistent','公开证据文本格式无效。',409) from None
    if redact(text)!=text or re.search(r'(?:/(?:srv|opt|var)/[^\s"<>]+|[A-Za-z]:\\\\|-----BEGIN .*PRIVATE KEY-----)',text):
        raise DemoError('evidence_inconsistent','材料含不应导出的内部信息。',409)
    return data

def wave_projection(w):
    keys={'validation_id','version_id','waveform_sha256','tiled','timescale','start_ticks','end_ticks','full_end_ticks','signals','sample_markers','missing_signals','marker_status','comparison_policy_id','truncated','tiles'}
    result={k:v for k,v in w.items() if k in keys}
    if 'timescale' in result:result['timescale']={k:v for k,v in w['timescale'].items() if k in {'value','unit'}}
    if 'signals' in result:result['signals']=[{k:v for k,v in x.items() if k in {'id','full_path','width','initial_value','changes'}} for x in w['signals']]
    if 'sample_markers' in result:result['sample_markers']=[{k:v for k,v in x.items() if k in {'time_ticks','sample_index','verdict','failed_signals','source','sampled_value_available'}} for x in w['sample_markers']]
    return result

@dataclass
class Entry:
    name:str
    value:Path|bytes
    role:str
    validations:list[str]
    version_id:str|None=None
    artifact:dict|None=None


def build_package(settings,store,case_id,validation_id,before_validation_id,out:Path,*,max_bytes=MAX_BYTES,max_entries=MAX_ENTRIES):
    """No record writes. Private owner access is intentionally never used here."""
    out=Path(out)
    if out.exists():raise DemoError('evidence_inconsistent','导出目标已存在。',409)
    ids=[before_validation_id,validation_id] if before_validation_id else [validation_id]
    if len(set(ids))!=len(ids) or any(not isinstance(i,str) or not IDENT.fullmatch(i) or i in {'.','..'} for i in ids):
        raise DemoError('invalid_selection','请选择不同且有效的验证记录。',422)
    selected=settings.for_case(case_id)
    b=store.get('bundle',selected.bundle_id)
    from .recorded_history import expanded_bundle
    b=expanded_bundle(store,b)
    if b.get('case_id')!=case_id or b.get('origin')!='historical':raise DemoError('evidence_not_public','当前案例没有公开历史包。',403)
    allowed={v['validation_id']:v for v in b['validations']}
    art=Artifacts(settings.data,store)
    entries=[]; versions=[]; validations=[];missing=[];seen_versions=set();input_sizes={}
    def get(kind,ident):
        try:return store.get(kind,ident)
        except DemoError as e:
            if e.status==403:raise DemoError('evidence_not_public','该记录不可公开导出。',403) from None
            raise
    def artifact(ident,kind):
        a=get('artifact',ident)
        if a.get('exposure')!='display' or a.get('kind')!=kind or kind not in KINDS:raise DemoError('evidence_not_public','该材料不在公开导出范围。',403)
        path=art.file(a)
        input_sizes[a['artifact_id']]=path.stat().st_size
        if path.stat().st_size!=a['size_bytes']:raise DemoError('evidence_inconsistent','证据文件大小与记录不一致。',409)
        if sum(input_sizes.values())>max_bytes:
            raise DemoError('evidence_too_large','证据输入超出预算。',413)
        return a,path
    def add(name,a,path,role,vs,version_id=None,data=None):
        relative(name)
        if data is not None:public_bytes(data)
        entries.append(Entry(name,data if data is not None else path,role,vs,version_id,a))
    for field,role,name in [('spec_artifact_id','spec','spec/specification.md'),('planner_artifact_id','planning','planning/repo_skeleton.json')]:
        a,p=artifact(b[field],role);add(name,a,p,role,ids)
    for ident in ids:
        v=get('validation',ident);run=get('run',v['run_id'])
        if run.get('case_id')!=case_id:raise DemoError('case_mismatch','不能跨案例打包。',422)
        if ident not in allowed or run.get('origin')!='historical':raise DemoError('evidence_not_public','记录不属于已公开历史包。',403)
        recorded=allowed[ident]
        for key in ['version_id','run_id','kind','verdict','waveform_sha256','report_artifact_id']:
            if v.get(key)!=recorded.get(key):raise DemoError('evidence_inconsistent','验证与公开记录不一致。',409)
        ver=get('version',v['version_id'])
        if ver['run_id']!=v['run_id']:raise DemoError('evidence_inconsistent','验证与受测版本不一致。',409)
        for k in [v['version_id'],v['run_id']]:
            if not IDENT.fullmatch(k) or k in {'.','..'}:raise DemoError('evidence_inconsistent','证据标识无效。',409)
        if ver['version_id'] not in seen_versions:
            art.version_path(ver)
            versions.append({**{k:ver[k] for k in ['version_id','run_id','tree_sha256']},'file_manifest':[{k:f[k] for k in ['path','sha256','size_bytes'] if k in f} for f in ver['file_manifest']]})
            for f in ver['file_manifest']:
                relative(f['path'])
                if Path(f['path']).suffix.lower() not in {'.v','.sv','.vh','.svh'}:raise DemoError('evidence_inconsistent','快照文件类型无效。',409)
                m=next((m for m in ver['modules'] if m['file']==f['path']),None)
                if not m:raise DemoError('evidence_inconsistent','完整RTL文件映射缺失。',409)
                a,p=artifact(m['artifact_id'],'rtl')
                if a['sha256']!=f['sha256']:raise DemoError('evidence_inconsistent','RTL文件与受测快照不一致。',409)
                vs=[x for x in ids if allowed.get(x,{}).get('version_id')==ver['version_id']]
                add('versions/'+ver['version_id']+'/rtl/'+f['path'],a,p,'rtl',vs,ver['version_id'])
            seen_versions.add(ver['version_id'])
        a,p=artifact(v['report_artifact_id'],'report');add('validations/'+ident+'/report.txt',a,p,'report',[ident],v['version_id'])
        record={k:v[k] for k in ['validation_id','run_id','version_id','kind','verdict','simulation_completed','total_samples','mismatched_samples','first_failure_ticks','waveform_sha256','comparison_policy_id','signal_names','signal_mismatches','probe_samples','probe_source_sha256','waveform_note','report_scope','verification_scope','signal_counter_status'] if k in v}
        record.update(report_artifact_id=a['artifact_id'],report_sha256=a['sha256'])
        validations.append(record)
        index_id=v.get('waveform_index_artifact_id')
        if not index_id:
            # Portable fixtures/legacy records can directly point to a public JSON waveform.
            candidate=get('artifact',v['waveform_artifact_id']) if v.get('waveform_artifact_id') else None
            if candidate and candidate.get('exposure')=='display' and candidate.get('kind')=='waveform':index_id=candidate['artifact_id']
        if not index_id:
            missing.append({'validation_id':ident,'role':'waveform','reason':'public_waveform_not_recorded'});continue
        a,p=artifact(index_id,'waveform');data=p.read_bytes()
        if hashlib.sha256(data).hexdigest()!=a['sha256']:raise DemoError('evidence_inconsistent','波形已变更。',409)
        wave=wave_projection(json.loads(data))
        def binding(w):
            if any(w.get(k)!=v.get(k) for k in ['validation_id','version_id','waveform_sha256']):raise DemoError('evidence_inconsistent','波形与所选验证不一致。',409)
        binding(wave)
        if wave.get('tiled'):
            tiles=[]
            for i,t in enumerate(wave['tiles']):
                ta,tp=artifact(t['artifact_id'],'waveform_tile');raw=tp.read_bytes()
                if hashlib.sha256(raw).hexdigest()!=ta['sha256']:raise DemoError('evidence_inconsistent','波形分片已变更。',409)
                tile=wave_projection(json.loads(raw));binding(tile)
                if tile['start_ticks']!=t['start_ticks'] or tile['end_ticks']!=t['end_ticks']:raise DemoError('evidence_inconsistent','波形分片窗口不一致。',409)
                tile_name=f'tiles/{i:04}.json'
                add('validations/'+ident+'/waveform/'+tile_name,ta,tp,'waveform_tile',[ident],v['version_id'],encoded(tile))
                tiles.append({'start_ticks':t['start_ticks'],'end_ticks':t['end_ticks'],'url':tile_name})
            if set(v.get('waveform_tile_artifact_ids',[]))!={t['artifact_id'] for t in wave['tiles']}:raise DemoError('evidence_inconsistent','波形分片引用不完整。',409)
            wave['tiles']=tiles
        add('validations/'+ident+'/waveform/index.json',a,p,'waveform',[ident],v['version_id'],encoded(wave))
    readme=('RTL Studio 公开历史证据包\n\n材料与所选RTL版本、验证记录绑定；结论仅适用于对应测试。\n'
            '查看 manifest.json 核对文件、SHA-256和验证身份。versions/ 为完整受测RTL，validations/ 为报告与公开波形。\n'
            'waveform/index.json 的 signals/changes 为真实 DUT 与 Reference 关键波形；分片路径相对 index。\n'
            '公开关键波形派生自真实VCD，不包含私有原始VCD、参考RTL、模型配置、会话或完整仿真环境。\n').encode()
    entries.append(Entry('README.txt',readme,'readme',ids))
    if len(entries)+1>max_entries:raise DemoError('evidence_too_large','证据包文件数超过上限。',413)
    total=sum(e.value.stat().st_size if isinstance(e.value,Path) else len(e.value) for e in entries)
    if total>max_bytes:raise DemoError('evidence_too_large','证据材料超过大小上限。',413)
    file_rows=[]
    for e in entries:
        size=e.value.stat().st_size if isinstance(e.value,Path) else len(e.value)
        h=sha(e.value) if isinstance(e.value,Path) else hashlib.sha256(e.value).hexdigest()
        if isinstance(e.value,Path):
            if e.artifact and h!=e.artifact['sha256']:raise DemoError('evidence_inconsistent','证据文件已变更。',409)
            public_bytes(e.value.read_bytes())
        row={'archive_path':e.name,'role':e.role,'validation_ids':e.validations,'archive_sha256':h,'size_bytes':size}
        if e.version_id:row['version_id']=e.version_id
        if e.artifact:
            row.update(artifact_id=e.artifact['artifact_id'],source_artifact_sha256=e.artifact['sha256'],source_sha256=e.artifact.get('source_sha256'))
        file_rows.append(row)
    manifest={'schema_version':'rtl-demo-evidence-v1','case_id':case_id,'bundle_id':b['bundle_id'],'source_fingerprint':b['source_fingerprint'],'selection':{'kind':'comparison' if before_validation_id else 'single','validation_id':validation_id,**({'before_validation_id':before_validation_id} if before_validation_id else {})},'validations':validations,'versions':versions,'files':sorted(file_rows,key=lambda f:f['archive_path']),'missing':missing,'exclusions':['raw_vcd_not_public','private_runtime_not_exported']}
    mb=public_bytes(encoded(manifest))
    if total+len(mb)>max_bytes:raise DemoError('evidence_too_large','证据包清单超过预算。',413)
    entries.append(Entry('manifest.json',mb,'manifest',ids))
    out.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix='evidence-',suffix='.zip',dir=out.parent);os.chmod(name,0o600);os.close(fd)
    try:
        with zipfile.ZipFile(name,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as archive:
            expected={f['archive_path']:f['archive_sha256'] for f in file_rows}
            for e in sorted(entries,key=lambda x:x.name):
                info=zipfile.ZipInfo(e.name,(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info._compresslevel=1;info.external_attr=0o100644<<16
                h=hashlib.sha256()
                with archive.open(info,'w') as target:
                    if isinstance(e.value,Path):
                        with e.value.open('rb') as source:
                            for chunk in iter(lambda:source.read(65536),b''):h.update(chunk);target.write(chunk)
                    else:h.update(e.value);target.write(e.value)
                if e.name in expected and h.hexdigest()!=expected[e.name]:raise DemoError('evidence_inconsistent','导出期间材料变更。',409)
                if Path(name).stat().st_size>max_bytes:raise DemoError('evidence_too_large','证据包超过输出上限。',413)
        if Path(name).stat().st_size>max_bytes:raise DemoError('evidence_too_large','证据包超过输出上限。',413)
        os.replace(name,out)
    finally:
        Path(name).unlink(missing_ok=True)
    return manifest


def export_packages(settings,store,bundle,out):
    out=Path(out);dest=out/'evidence';dest.mkdir(parents=True,exist_ok=True)
    index={'schema_version':'rtl-demo-evidence-index-v1','single':{},'comparisons':[]}
    selections=[(v['validation_id'],None) for v in bundle['validations']]
    pair=bundle['comparison_pair']
    if pair.get('before_validation_id'):selections.append((pair['after_validation_id'],pair['before_validation_id']))
    for run in bundle.get('debug_history',{}).get('runs',[]):
        selections += [(a['validation_id'],a['before_validation_id']) for a in run['attempts']]
    for ident,before in selections:
        fd,name=tempfile.mkstemp(dir=dest,suffix='.zip');os.close(fd);Path(name).unlink()
        temp=Path(name)
        try:
            build_package(settings,store,bundle['case_id'],ident,before,temp)
            digest=sha(temp);target=dest/(digest+'.zip');os.replace(temp,target);os.chmod(target,0o644)
            d={'kind':'comparison' if before else 'single','validation_id':ident,'url':f"/cases/{bundle['case_id']}/evidence/{digest}.zip",'sha256':digest,'size_bytes':target.stat().st_size}
            if before:d['before_validation_id']=before;index['comparisons'].append(d)
            else:index['single'][ident]=d
        finally:temp.unlink(missing_ok=True)
    keep={d['sha256']+'.zip' for d in list(index['single'].values())+index['comparisons']}
    for old in dest.glob('*.zip'):
        if re.fullmatch(r'[a-f0-9]{64}\.zip',old.name) and old.name not in keep:old.unlink()
    return index


class ExportManager:
    def __init__(self,settings,store):
        self.settings,self.store=settings,store
        self.lock=threading.Lock();self.active=set();self.guard=threading.Lock()
        self.root=safe_path(settings.data,'export-tmp')
    def startup(self):
        self.root.mkdir(mode=0o700,exist_ok=True);os.chmod(self.root,0o700)
        for p in self.root.glob('evidence-*.zip'):
            if p not in self.active:p.unlink(missing_ok=True)
    def create(self,cid,ident,before):
        if not self.lock.acquire(blocking=False):raise DemoError('export_busy','证据导出繁忙，请稍后重试。',429)
        path=None
        try:
            self.root.mkdir(mode=0o700,exist_ok=True)
            if sum(p.stat().st_size for p in self.root.glob('*.zip') if p.is_file())+MAX_BYTES>MAX_TEMP_BYTES:raise DemoError('evidence_too_large','临时下载空间已满。',413)
            fd,name=tempfile.mkstemp(prefix='evidence-',suffix='.zip',dir=self.root);os.close(fd);path=Path(name);path.unlink()
            build_package(self.settings,self.store,cid,ident,before,path)
            self.active.add(path);return path
        except BaseException:
            if path:path.unlink(missing_ok=True)
            raise
        finally:self.lock.release()
    def remove(self,path):
        path.unlink(missing_ok=True);self.active.discard(path)
