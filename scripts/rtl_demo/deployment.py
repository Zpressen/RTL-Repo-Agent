"""Versioned deployment coordinator. Import/check use only the Python stdlib."""
from __future__ import annotations
import argparse
import ast
from datetime import datetime, timezone
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import sys
import tempfile

PACKAGES={'design','runtime','seed','verifier','ops'}
CASE_FILES={
'e203':('rtl_dataset/e203_exu_alu_hard/e203_exu_alu_system.md','system_task/e203_exu_alu_hard/verify_test/e203_exu_alu_system_verify.py'),
'aes_cipher_system_hard':('rtl_dataset/aes_cipher_hard/aes_cipher_system_hard.md','system_task/aes_cipher_hard/verify_test/aes_cipher_system_verify.py'),
'aes_inv_cipher_top_system':('rtl_dataset/aes_inv_cipher_system/aes_inv_cipher_top_system.md','system_task/aes_inv_cipher_top_hard/verify_test/aes_inv_cipher_system_verify.py'),
'sdc_controller_system':('rtl_dataset/sdc_controller_hard/sdc_controller_system.md','system_task/sdc_controller_hard/verify_test/sdc_controller_system_verify.py')}
CASE_IDS=set(CASE_FILES)
BLOCKED_PARTS={'.git','.agents','.specify','__pycache__','node_modules','codex_private','obj_dir','.rtl-demo','.venv','.venv-web','.venv-agent'}
TEXT_SUFFIXES={'.py','.yaml','.yml','.toml','.json','.txt','.md','.sh','.v','.sv','.vh','.svh','.js','.ts','.html','.css','.conf','.example','.service','.slice'}
SECRET=re.compile(rb'(?:sk-[A-Za-z0-9_-]{16,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
ASSIGNMENT=re.compile(rb'''(?im)^\s*["']?(?:api[_-]?key|password|access[_-]?token|gateway[_-]?key)["']?\s*[:=]\s*["']?([^\s,"'\n}]+)''')


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def relative_path(value):
    if (not isinstance(value,str) or not value or '\\' in value or '\x00' in value
        or any(ord(c)<32 for c in value) or PurePosixPath(value).is_absolute()
        or any(p in {'','.', '..'} for p in value.split('/'))): raise ValueError('Unsafe relative path')
    return value


def child(root,name):
    relative_path(name); root=Path(root).absolute(); path=root/name
    for part in [path,*path.parents]:
        if part==root.parent:break
        if part.is_symlink(): raise ValueError('Symlink deployment path')
    return path


def check_public_bytes(data, suffix=None):
    if SECRET.search(data): raise ValueError('Secret material in release')
    def literal_secret(key,value):
        if re.fullmatch(r'(?:api_key|password|access_token|gateway_key)',str(key),re.I) and isinstance(value,str) and value:
            if not value.startswith(('${','REPLACE_','<')) and value not in {'None','null','EMPTY'}:
                raise ValueError('Literal credential in release')
    if suffix=='.json':
        def visit(value):
            if isinstance(value,dict):
                for key,item in value.items():literal_secret(key,item);visit(item)
            elif isinstance(value,list):
                for item in value:visit(item)
        visit(json.loads(data))
    if suffix=='.py':
        tree=ast.parse(data)
        for node in ast.walk(tree):
            if isinstance(node,(ast.Assign,ast.AnnAssign)):
                value=node.value
                targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                if isinstance(value,ast.Constant):
                    for target in targets:
                        if isinstance(target,ast.Name):literal_secret(target.id,value.value)
            elif isinstance(node,ast.Dict):
                for key,value in zip(node.keys,node.values):
                    if isinstance(key,ast.Constant) and isinstance(value,ast.Constant):literal_secret(key.value,value.value)
        return
    if suffix in {'.sh','.js','.ts','.html','.css','.v','.sv','.vh','.svh'}:return
    for match in ASSIGNMENT.finditer(data):
        value=match.group(1)
        if value and not value.startswith((b'${',b'REPLACE_',b'<',b'None',b'null',b'os.',b'"',b"'")):
            raise ValueError('Literal secret assignment in release')


def inventory(root,package):
    root=Path(root).absolute()
    if package not in PACKAGES or root.is_symlink(): raise ValueError('Unknown package or unsafe root')
    result=[]; folded=set()
    for p in sorted(root.rglob('*')):
        rel=p.relative_to(root).as_posix();relative_path(rel)
        if p.is_symlink() or not (p.is_dir() or p.is_file()):raise ValueError('Unsafe release entry')
        if not p.is_file():continue
        if p.stat().st_nlink!=1:raise ValueError('Hardlink release entry')
        if rel.casefold() in folded:raise ValueError('Ambiguous release path')
        folded.add(rel.casefold())
        if any(x in BLOCKED_PARTS or x.startswith('.venv') for x in p.relative_to(root).parts): raise ValueError('Private/developer directory in release')
        if p.name in {'zerorepo_config.yaml','rtl_demo.local.yaml','rtl_demo.production.yaml','session.key','state.sqlite3'} or p.name.startswith('.env') or p.suffix=='.env' or (package=='ops' and p.name in {'agent.yaml','config.yaml','environment'}):raise ValueError('Private state in release')
        if package=='design':
            if p.suffix=='.zip':_static_module().validate_evidence_zip(p,root)
            elif p.suffix not in {'.html','.js','.css','.json','.svg','.png','.ico','.woff2','.txt'} or rel.startswith(('runtime/','seed/','verifier/','ops/')):raise ValueError('Private/nonstatic file in design')
        if p.suffix in TEXT_SUFFIXES or p.name=='LICENSE':
            try:check_public_bytes(p.read_bytes(),p.suffix)
            except (ValueError,SyntaxError):raise ValueError('Secret or invalid source in '+package+'/'+rel) from None
        result.append({'package':package,'source_relative_path':rel,'target_relative_path':rel,
                       'purpose':package+' deployment material','visibility':'design_protected' if package=='design' else ('ops_private' if package=='ops' else 'runtime_private'),
                       'size_bytes':p.stat().st_size,'sha256':digest(p),'mode':0o644 if package=='design' else 0o600})
    return result


def atomic_json(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd,tmp=tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd,'w') as out:json.dump(data,out,ensure_ascii=False,indent=2);out.write('\n')
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def checked(root):
    root=Path(root).absolute()
    if root.is_symlink():raise ValueError('Symlink release')
    m=json.loads((root/'deployment.json').read_text())
    if m.get('schema_version')!='rtl-demo-deploy-v1' or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',m.get('release_id','')):raise ValueError('Invalid release manifest')
    if m.get('target_origin','https://design.deepvalleychip.cn') not in {'https://agent.deepvalleychip.cn','https://design.deepvalleychip.cn'}:raise ValueError('Unknown target origin')
    if set(m.get('cases',{}))!=CASE_IDS:raise ValueError('Four cases required')
    if {p.name for p in root.iterdir()}!=PACKAGES|{'deployment.json'}:raise ValueError('Unknown release content')
    actual=[]
    for package in sorted(PACKAGES):
        if not (root/package).is_dir():raise ValueError('Missing release layer')
        actual+=inventory(root/package,package)
    # Source labels/purposes are metadata; file identity and visibility are recomputed.
    expected=m['files'];keys=set()
    for entry in expected:
        key=(entry['package'],relative_path(entry['target_relative_path']))
        relative_path(entry['source_relative_path'])
        if key in keys:raise ValueError('Duplicate manifest path')
        keys.add(key)
    actual_map={(x['package'],x['target_relative_path']):x for x in actual}
    if set(actual_map)!=keys:raise ValueError('Release file list mismatch')
    for e in expected:
        a=actual_map[(e['package'],e['target_relative_path'])]
        if any(a[k]!=e[k] for k in ('size_bytes','sha256','visibility','mode')):raise ValueError('Release file mismatch')
    seed=json.loads((root/'seed/seed.json').read_text())
    if set(seed.get('cases',{}))!=CASE_IDS:raise ValueError('Seed cases missing')
    if any(r.get('owner') is not None for r in seed.get('records',[])):raise ValueError('Private session records in seed')
    for cid,case in m['cases'].items():
        doc=json.loads((root/'design/cases'/cid/'manifest.json').read_text())
        spec,verifier=CASE_FILES[cid]
        if (doc['bundle_id']!=case['bundle_id'] or seed['cases'][cid]!=case['bundle_id']
            or case.get('seed_id')!=seed.get('seed_id')):raise ValueError('Static/backend/seed bundle mismatch')
        validate_story_binding(root, seed, cid)
        if not (root/'runtime'/spec).is_file() or digest(root/'runtime'/spec)!=case.get('spec_sha256'):
            raise ValueError('Task specification missing or inconsistent')
        if not (root/'verifier'/verifier).is_file():raise ValueError('Case verifier missing')
    for required in ['zerorepo/rtl_web/cli.py','zerorepo/rtl_web/runtime.py']:
        if not (root/'runtime'/required).is_file():raise ValueError('Runtime entry missing')
    if set(m.get('lock_hashes',{}))!={'requirements-web-prod.txt','requirements-agent-demo.txt','deploy/rtl_demo/toolchain.lock.json'}:
        raise ValueError('Production dependency/toolchain locks required')
    for name,h in m['lock_hashes'].items():
        if digest(child(root/'ops',name))!=h:raise ValueError('Lock mismatch')
    return m


def validate_story_binding(root, seed, case_id):
    path=Path(root)/'design/cases'/case_id/'stories/manifest.json'
    story_id=(seed.get('stories') or {}).get(case_id)
    if not path.exists():
        if story_id:raise ValueError('Public story manifest missing')
        return
    view=json.loads(path.read_text())
    if view.get('case_id')!=case_id or view.get('story_id')!=story_id:raise ValueError('Static/backend story mismatch')
    if story_id:
        record=next((r['payload'] for r in seed['records'] if r['kind']=='story' and r['id']==story_id),None)
        if not record:raise ValueError('Seed story missing')
        fingerprint=hashlib.sha256(json.dumps(record,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
        if view.get('fingerprint')!=fingerprint:raise ValueError('Story fingerprint mismatch')


def _copy_tree(src,dst,excluded,source_root=None):
    src=Path(src)
    if src.is_symlink():raise ValueError('Symlink source')
    root=source_root or src
    candidates=src.rglob('*') if src.is_dir() else [src]
    for p in sorted(candidates):
        rel=p.relative_to(root).as_posix() if p!=root else p.name
        parts=p.relative_to(src).parts if src.is_dir() else (p.name,)
        if any(x in excluded or x.startswith('.venv') for x in parts) or p.suffix in {'.pyc','.pyo','.so','.o','.a','.vcd','.fst'}:continue
        if p.is_symlink():raise ValueError('Symlink source')
        if not p.is_file():continue
        target=dst/(p.relative_to(src) if src.is_dir() else p.name)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(p,target)


def build(config,release_id,out):
    import yaml
    repo=Path(__file__).resolve().parents[2]
    sys.path.insert(0,str(repo))
    from zerorepo.rtl_web.settings import Settings
    from zerorepo.rtl_web.seed import export_seed
    from zerorepo.rtl_web.cases import CASES
    cfgpath=Path(config).resolve();cfg=yaml.safe_load(cfgpath.read_text())
    if cfg.get('schema_version')!='rtl-demo-package-input-v1':raise ValueError('Invalid build config')
    def source(value):return (cfgpath.parent/value).resolve()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',release_id):raise ValueError('Invalid release ID')
    target=Path(out).resolve()/release_id
    if target.exists() or target.is_relative_to(repo):raise ValueError('Output must be new and outside source repository')
    locks=cfg['production_locks'];tool=cfg['toolchain_lock']
    for name in [*locks,tool]:
        if not child(repo,name).is_file():raise ValueError('Production lock missing')
    excluded=set(cfg.get('exclude',[]))|BLOCKED_PARTS
    if any(x in {'**/*','*','.'} for group in cfg['include'].values() for x in group):raise ValueError('Broad source wildcard')
    target.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='.package-',dir=target.parent))
    try:
        settings=Settings(source(cfg['runtime_config']),create_data=False)
        shutil.copytree(source(cfg['dist']),stage/'design',symlinks=True)
        for package in ['runtime','ops']:
            (stage/package).mkdir()
            for name in cfg['include'][package]:
                src=child(repo,name);dst=stage/package/name
                if not src.exists():raise ValueError('Whitelisted source missing')
                if src.is_dir():_copy_tree(src,dst,excluded)
                else:_copy_tree(src,dst.parent,excluded)
        for cid,c in CASES.items():
            src=child(repo,c['spec']);dst=stage/'runtime'/c['spec'];dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,dst)
        summary=export_seed(settings,stage/'seed')
        oracle=source(cfg['oracle_root']);(stage/'verifier').mkdir()
        for c in CASES.values():
            for name in ['system_task/'+c['project_hint']+'/verify_test',*c['reference_roots']]:
                src=child(oracle,name)
                if not src.is_dir():raise ValueError('Verifier resources missing')
                _copy_tree(src,stage/'verifier'/name,excluded)
        hashes={}
        for name in [*locks,tool]:
            dst=stage/'ops'/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(child(repo,name),dst);hashes[name]=digest(dst)
        # Avoid release.py's build-only Git dependency on the target host.
        if not (stage/'design/release.json').exists():
            sys.path.insert(0,str(Path(__file__).parent))
            import release as static
            temp=stage/'static-stage'
            static.stage(stage/'design',temp,release_id)
            shutil.copyfile(temp/release_id/'design/release.json',stage/'design/release.json');shutil.rmtree(temp)
        revision=subprocess.run(['git','rev-parse','HEAD'],cwd=repo,capture_output=True,text=True,check=True).stdout.strip()
        dirty=bool(subprocess.run(['git','status','--porcelain'],cwd=repo,capture_output=True,text=True,check=True).stdout)
        files=[]
        for package in sorted(PACKAGES):files+=inventory(stage/package,package)
        cases={cid:{'bundle_id':settings.for_case(cid).bundle_id,'spec_sha256':digest(settings.for_case(cid).spec),'seed_id':summary['seed_id']} for cid in CASES}
        data={'schema_version':'rtl-demo-deploy-v1','target_origin':cfg.get('target_origin','https://design.deepvalleychip.cn'),'release_id':release_id,'created_at':datetime.now(timezone.utc).isoformat(),
              'source_revision':revision,'source_dirty':dirty,'platform':cfg['target_platform'],'cases':cases,'files':files,'lock_hashes':hashes,'state':'staged'}
        atomic_json(stage/'deployment.json',data);checked(stage);stage.rename(target)
    finally:
        if stage.exists():shutil.rmtree(stage)
    return {'release_id':release_id,'state':'staged','file_count':len(files),'target':str(target)}


# All host mutations below use fixed paths. Test layouts are explicit Python-only
# injections; the production CLI has no arbitrary destination/path option.
import contextlib
import fcntl
import socket
import sqlite3
import time


class DeploymentError(ValueError):
    def __init__(self,code,message):
        super().__init__(message); self.code=code


class Layout:
    root: Path=Path('/opt/rtl-agent')
    config: Path=Path('/etc/rtl-demo')
    data: Path=Path('/var/lib/rtl-demo')
    static: Path=Path('/srv/deepvalleychip')
    caddy: Path=Path('/etc/caddy')
    units: Path=Path('/etc/systemd/system')

    def __init__(self,root=Path('/opt/rtl-agent'),config=Path('/etc/rtl-demo'),data=Path('/var/lib/rtl-demo'),static=Path('/srv/deepvalleychip'),caddy=Path('/etc/caddy'),units=Path('/etc/systemd/system')):
        self.root=Path(root);self.config=Path(config);self.data=Path(data);self.static=Path(static);self.caddy=Path(caddy);self.units=Path(units)

    @property
    def records(self):return self.root/'deployment'


def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',value):
        raise ValueError('Invalid deployment identifier')
    return value


def no_links(path):
    path=Path(path).absolute()
    for p in [path,*path.parents]:
        if p.is_symlink():raise ValueError('Symlink host path')
    return path


def sealed(path):
    path=no_links(path)
    for p in [path,*path.rglob('*')]:
        if p.is_symlink() or not (p.is_file() or p.is_dir()):raise ValueError('Unsafe sealed entry')
        info=p.stat()
        if info.st_uid!=0 or info.st_mode&0o022:raise ValueError('Candidate is writable outside root')
        if p.is_file() and info.st_nlink!=1:raise ValueError('Hardlink sealed entry')
    for p in path.parents:
        info=p.stat()
        if info.st_uid!=0 or info.st_mode&0o022:raise ValueError('Untrusted candidate ancestor')
    return path


def privileged():
    if os.geteuid()!=0:raise DeploymentError(5,'Root required; use the reviewed sealed candidate')


def backup_database(source,target):
    source=no_links(source);target=no_links(target)
    if target.exists():raise ValueError('Backup already exists')
    target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    if not source.is_file():return None
    try:
        with sqlite3.connect(source.as_uri()+'?mode=ro',uri=True) as src, sqlite3.connect(target) as dst:
            src.backup(dst)
            if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Invalid database backup')
        target.chmod(0o600)
    except Exception:
        target.unlink(missing_ok=True);raise
    return str(target)


def release_status(release_id,root=Path('/opt/rtl-agent/deployment')):
    release_id=identifier(release_id);path=child(root,release_id+'.json')
    if not path.is_file():return {'release_id':release_id,'state':'not_prepared','acceptance':'not_run'}
    record=json.loads(path.read_text())
    result={k:record[k] for k in ['release_id','state','prepared_at','activated_at','recovery_set','acceptance','blockers'] if k in record}
    current=Path(root).parent/'current'
    result['current']=current.is_symlink() and current.resolve()==Path(root).parent/'releases'/release_id
    # Do not create/open a Store or run paid dependency probes for status.
    if Path(root)==Path('/opt/rtl-agent/deployment'):
        result['services']={name:subprocess.run(['systemctl','is-active',name],capture_output=True,text=True).stdout.strip()
                            for name in ['rtl-demo-api','rtl-demo-worker','rtl-demo-kg']}
        state=Path('/var/lib/rtl-demo/worker-state.json')
        if state.is_file():
            try:
                worker=json.loads(state.read_text())
                result['worker']={k:worker.get(k) for k in ['release_id','code_root','pid','checked_at']}
            except (ValueError,OSError):result['worker']={'state':'unreadable'}
    return result


def validate_acceptance(evidence,release_id,evidence_root,*,host='39.107.243.176',origin='https://design.deepvalleychip.cn',host_id=None):
    if (evidence.get('release_id')!=identifier(release_id) or evidence.get('host')!=host
        or evidence.get('origin')!=origin):raise ValueError('Acceptance identity mismatch')
    if host_id is not None and evidence.get('host_id')!=host_id:raise ValueError('Acceptance machine mismatch')
    criteria=evidence.get('criteria',[])
    if len(criteria)!=12 or {x.get('criterion') for x in criteria}!={f'SC-{i:03}' for i in range(1,13)}:
        raise ValueError('All twelve acceptance criteria required')
    for criterion in criteria:
        if criterion.get('status')!='passed' or not criterion.get('evidence'):raise ValueError('Acceptance incomplete')
        for entry in criterion['evidence']:
            path=child(evidence_root,entry['path'])
            if (not path.is_file() or path.stat().st_nlink!=1 or path.stat().st_size!=entry['size_bytes']
                or digest(path)!=entry['sha256']):raise ValueError('Acceptance evidence mismatch')
            doc=json.loads(path.read_text())
            if any(doc.get(k)!=evidence[k] for k in ['release_id','host','origin']):raise ValueError('Unbound acceptance evidence')
            if host_id is not None and doc.get('host_id')!=host_id:raise ValueError('Evidence machine mismatch')
            if doc.get('status')!='passed' or doc.get('criterion')!=criterion['criterion']:
                raise ValueError('Evidence does not establish criterion')
    return True


def merge_design(caddyfile,design):
    """Replace exactly the design block while preserving other bytes and sites."""
    # Caddy placeholders contain braces; quoting/comments also must not affect
    # nesting. Refuse imports/multi-address design blocks that need manual review.
    start=None;depth=0;quote=None;comment=False;escape=False;placeholder=False
    blocks=[];line_start=0;block_start=None;header=''
    for i,c in enumerate(caddyfile):
        if comment:
            if c=='\n':comment=False;line_start=i+1
            continue
        if escape:escape=False;continue
        if c=='\\':escape=True;continue
        if quote:
            if c==quote:quote=None
            continue
        if c in {'"',"'",'`'}:quote=c;continue
        if c=='#':comment=True;continue
        if c=='{' and i+1<len(caddyfile) and caddyfile[i+1]=='$':placeholder=True;continue
        if placeholder:
            if c=='}':placeholder=False
            continue
        if c=='{':
            if depth==0:block_start=line_start;header=caddyfile[line_start:i].strip()
            depth+=1
        elif c=='}':
            depth-=1
            if depth<0:raise ValueError('Unbalanced Caddyfile')
            if depth==0:blocks.append((header,block_start,i+1))
        if c=='\n':line_start=i+1
    if depth or quote or placeholder:raise ValueError('Unsupported Caddyfile syntax')
    matches=[b for b in blocks if 'design.deepvalleychip.cn' in b[0]]
    if len(matches)!=1 or matches[0][0] not in {'design.deepvalleychip.cn','https://design.deepvalleychip.cn'}:
        raise ValueError('Exactly one standalone design site required')
    _,start,end=matches[0]
    return caddyfile[:start]+design.strip()+caddyfile[end:]


def environment_file(path):
    """Strict shared subset of systemd EnvironmentFile and shell-free parsing."""
    result={}
    for raw in Path(path).read_text().splitlines():
        line=raw.strip()
        if not line or line.startswith('#'):continue
        if '=' not in line:raise ValueError('Invalid service environment')
        key,value=line.split('=',1)
        if not re.fullmatch(r'[A-Z_][A-Z_0-9]*',key) or key in result:raise ValueError('Invalid environment key')
        # No expansion/evaluation; quoted scalar values are accepted verbatim.
        if len(value)>=2 and value[0]==value[-1] and value[0] in {'"',"'"}:value=value[1:-1]
        if any(c in value for c in ['\x00','\n','\r','\\','"',"'"]):raise ValueError('Unsupported environment encoding')
        result[key]=value
    return result


def private_file(path,group=None):
    path=no_links(path)
    info=path.stat()
    if info.st_uid!=0 or info.st_mode&0o037:raise ValueError('Private configuration permissions required')
    if not path.is_file():raise ValueError('Private configuration file required')
    if group is not None:
        import grp
        if info.st_gid!=grp.getgrnam(group).gr_gid:raise ValueError('Private configuration group mismatch')
    return path


def host_command(argv,*,env=None,cwd=None,timeout=600):
    # Never relay stderr/stdout from programs that can expand credentials.
    proc=subprocess.run([str(a) for a in argv],env=env,cwd=cwd,capture_output=True,text=True,timeout=timeout)
    if proc.returncode:raise DeploymentError(4,'Host command failed: '+Path(str(argv[0])).name)
    return proc.stdout


def as_service(argv,environment,*,user='rtl-demo',cwd=None,timeout=600):
    import pwd
    account=pwd.getpwnam(user)
    env={'PATH':'/opt/rtl-agent/toolchain/bin:/usr/sbin:/usr/bin:/bin','HOME':account.pw_dir,
         'LANG':'C.UTF-8',**environment}
    # Credentials remain in environment; no env KEY=VALUE command argv.
    proc=subprocess.run([str(x) for x in argv],env=env,cwd=cwd,user=account.pw_uid,group=account.pw_gid,
                        extra_groups=[],capture_output=True,text=True,timeout=timeout)
    if proc.returncode:raise DeploymentError(4,'Service check failed: '+Path(str(argv[0])).name)
    return proc.stdout


def write_private(path,data,*,group=None,mode=0o600):
    path=no_links(path);path.parent.mkdir(parents=True,exist_ok=True,mode=0o750)
    fd,tmp=tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as out:out.write(data if isinstance(data,bytes) else data.encode())
        os.chmod(tmp,mode)
        if group:
            import grp
            os.chown(tmp,0,grp.getgrnam(group).gr_gid)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


@contextlib.contextmanager
def deployment_lock(layout):
    layout.records.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (layout.records/'coordinator.lock').open('a') as stream:
        fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield


def _record(layout,release_id):
    path=child(layout.records,identifier(release_id)+'.json')
    if not path.is_file():raise DeploymentError(4,'Release not prepared')
    return json.loads(path.read_text())


def save_record(layout,record):atomic_json(child(layout.records,identifier(record['release_id'])+'.json'),record)


def _account(name,home):
    import pwd
    try:pwd.getpwnam(name)
    except KeyError:host_command(['useradd','--system','--user-group','--home-dir',home,'--shell','/sbin/nologin',name])


def prepare(release,config,*,dry_run=False,layout=Layout()):
    source=Path(release).absolute();m=checked(source);rid=m['release_id']
    if source!=layout.root/'candidates'/rid:raise ValueError('Only sealed candidate path accepted')
    if Path(config).absolute()!=layout.config/'config.yaml':raise ValueError('Only fixed server configuration supported')
    actions={'release_id':rid,'state':'prepare_preview','dry_run':dry_run,
             'source':str(source),'release':str(layout.root/'releases'/rid),
             'accounts':['rtl-demo','rtl-demo-kg'],'oracle':'content-addressed four-case verifier',
             'environments':['.venv-web','.venv-agent'],'locks':m['lock_hashes'],
             'private_config':[str(layout.config/'config.yaml'),str(layout.config/'agent.yaml'),str(layout.config/'environment'),str(layout.caddy/'rtl-demo.env')],
             'job_volume':'8 GiB fixed loop volume; requires 5 GiB host reserve',
             'services':'stage only; activate installs/restarts RTL units',
             'unchanged':['main','www','CAD :28989','system Python','production DB/session.key','current symlink','Caddy active config']}
    if dry_run:return actions
    privileged();sealed(source)
    with deployment_lock(layout):
        destination=layout.root/'releases'/rid
        if destination.exists():
            record=_record(layout,rid)
            if record.get('manifest_sha256')!=digest(source/'deployment.json'):raise ValueError('Prepared identity conflict')
            if record['state'] not in {'prepared','active_unverified','accepted'}:raise DeploymentError(4,'Incomplete prepare requires review')
            return release_status(rid,layout.records)
        for path in [layout.root,layout.config,layout.records,layout.data,Path('/var/lib/rtl-demo-kg')]:no_links(path)
        _account('rtl-demo',str(layout.data));_account('rtl-demo-kg','/var/lib/rtl-demo-kg')
        import pwd,grp
        app=pwd.getpwnam('rtl-demo');kg=pwd.getpwnam('rtl-demo-kg')
        for path,uid,gid in [(layout.data,app.pw_uid,app.pw_gid),(Path('/var/lib/rtl-demo-kg'),kg.pw_uid,kg.pw_gid)]:
            path.mkdir(parents=True,exist_ok=True,mode=0o700);os.chown(path,uid,gid)
        layout.config.mkdir(parents=True,exist_ok=True,mode=0o750);os.chown(layout.config,0,app.pw_gid)
        for name in ['config.yaml','agent.yaml']:private_file(layout.config/name,'rtl-demo')
        private_file(layout.config/'environment');private_file(layout.caddy/'rtl-demo.env')
        service_env=environment_file(layout.config/'environment');caddy_env=environment_file(layout.caddy/'rtl-demo.env')
        if (len(service_env.get('RTL_DEMO_GATEWAY_KEY',''))<32 or service_env['RTL_DEMO_GATEWAY_KEY'].startswith('REPLACE_')
            or service_env.get('RTL_DEMO_DEVELOPMENT')=='1'
            or caddy_env.get('RTL_DEMO_GATEWAY_KEY')!=service_env['RTL_DEMO_GATEWAY_KEY']
            or caddy_env.get('RTL_DEMO_UPSTREAM')!='127.0.0.1:8000'
            or not caddy_env.get('RTL_DEMO_PASSWORD_HASH','').startswith('$2')):raise DeploymentError(4,'Private gateway/environment incomplete')
        tool=layout.root/'toolchain';python=tool/'bin/python3.13';uv=tool/'bin/uv'
        for binary in [python,uv,tool/'bin/verilator',tool/'bin/codex']:
            if not binary.is_file():raise DeploymentError(4,'Run reviewed bootstrap first')
        destination.parent.mkdir(parents=True,exist_ok=True,mode=0o755)
        record={'host_id':hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest(),'target_origin':m.get('target_origin','https://design.deepvalleychip.cn'),'release_id':rid,'state':'preparing','manifest_sha256':digest(source/'deployment.json'),'candidate':str(source),'acceptance':'not_run'}
        save_record(layout,record)
        try:
            shutil.copytree(source/'runtime',destination)
            metadata=destination/'.deployment';metadata.mkdir(mode=0o755)
            shutil.copytree(source/'seed',metadata/'seed')
            shutil.copyfile(source/'ops/scripts/rtl_demo/server_config.py',metadata/'server_config.py')
            for role in ['web','agent']:
                envpath=destination/('.venv-'+role)
                lock=source/'ops'/('requirements-web-prod.txt' if role=='web' else 'requirements-agent-demo.txt')
                host_command([uv,'venv','--python',python,envpath])
                host_command([uv,'pip','sync','--python',envpath/'bin/python','--require-hashes','--only-binary',':all:',lock],timeout=1800)
            verifier_hash=hashlib.sha256(json.dumps([(x['target_relative_path'],x['sha256']) for x in m['files'] if x['package']=='verifier'],sort_keys=True).encode()).hexdigest()
            oracle=layout.root/'oracle'/verifier_hash
            if not oracle.exists():shutil.copytree(source/'verifier',oracle)
            else:
                expected={x['target_relative_path']:x['sha256'] for x in m['files'] if x['package']=='verifier'}
                if {p.relative_to(oracle).as_posix():digest(p) for p in oracle.rglob('*') if p.is_file()}!=expected:raise ValueError('Existing oracle mismatch')
            parser=destination/'.native/rtl_langs.so';parser.parent.mkdir(mode=0o755)
            host_command(['bash',source/'ops/deploy/rtl_demo/build-parser.sh',destination/'.venv-agent/bin/python',destination,parser.parent],cwd=destination)
            # Materialize a candidate-specific config, without importing YAML in
            # this bootstrap coordinator. The Web environment now exists.
            prepared_config=layout.records/(rid+'.config.yaml')
            helper=metadata/'server_config.py'
            host_command([destination/'.venv-web/bin/python',helper,'derive','--source',config,'--target',prepared_config,
                          '--release',destination,'--release-id',rid,'--oracle',oracle,'--data',layout.data,'--parser',parser],cwd=destination,env={**os.environ,'PYTHONPATH':str(destination)})
            os.chown(prepared_config,0,app.pw_gid);prepared_config.chmod(0o640)
            # Root-owned files can be read but never changed by either service.
            for p in [destination,*destination.rglob('*'),oracle,*oracle.rglob('*')]:
                if not p.is_symlink():
                    executable=p.is_dir() or bool(p.stat().st_mode&0o111)
                    os.chown(p,0,app.pw_gid);p.chmod(0o750 if executable else 0o640)
            # Candidate seed validation uses an isolated disposable Store. It
            # never opens the production DB or launches a second worker.
            temporary=Path(tempfile.mkdtemp(prefix='candidate-',dir=layout.data))
            os.chown(temporary,app.pw_uid,app.pw_gid)
            try:
                candidate_cfg=temporary/'config.yaml'
                host_command([destination/'.venv-web/bin/python',helper,'derive','--source',prepared_config,'--target',candidate_cfg,
                              '--release',destination,'--release-id',rid,'--oracle',oracle,'--data',temporary/'state','--parser',parser],cwd=destination,env={**os.environ,'PYTHONPATH':str(destination)})
                os.chown(candidate_cfg,app.pw_uid,app.pw_gid);candidate_cfg.chmod(0o600)
                env={**service_env,'RTL_DEMO_CONFIG':str(candidate_cfg),'PYTHONPATH':str(destination)}
                as_service([destination/'.venv-web/bin/python','-m','zerorepo.rtl_web.cli','import-seed','--config',candidate_cfg,'--source',destination/'.deployment/seed'],env,cwd=destination)
                # Offline check imports actual Agent dependencies, parses AST,
                # validates materials/profile. Live KG/worker are activate gates.
                offline=json.loads(as_service([destination/'.venv-agent/bin/python',helper,'check','--source',candidate_cfg],env,cwd=destination))
                if not offline.get('ready'):raise DeploymentError(4,'Candidate offline dependencies incomplete')
                atomic_json(layout.records/(rid+'.candidate-check.json'),{'release_id':rid,**offline})
            finally:shutil.rmtree(temporary)
            record.update(state='prepared',prepared_at=datetime.now(timezone.utc).isoformat(),oracle=str(oracle),config=str(prepared_config))
            save_record(layout,record)
            return release_status(rid,layout.records)
        except Exception:
            record.update(state='failed',blockers=['prepare_incomplete']);save_record(layout,record)
            # Retain failed paths for diagnosis; do not silently reuse partial envs.
            raise


def _static_module():
    import importlib.util
    spec=importlib.util.spec_from_file_location('rtl_static_release',Path(__file__).with_name('release.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def story_roots(database):
    if not Path(database).is_file():return {}
    with sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True) as c:
        return {key:json.loads(value) for key,value in c.execute('SELECT key,value FROM controls') if key in {'story:'+cid for cid in CASE_IDS}}


def restore_story_roots(database,roots):
    allowed={'story:'+cid for cid in CASE_IDS}
    if set(roots)-allowed:raise ValueError('Unapproved recovery story root')
    if not Path(database).is_file():
        if roots:raise ValueError('Story recovery database missing')
        return
    with sqlite3.connect(database) as c:
        for key,ident in roots.items():
            row=c.execute("SELECT owner,payload FROM records WHERE kind='story' AND id=?",(ident,)).fetchone()
            if not row or row[0] is not None or json.loads(row[1]).get('case_id')!=key[6:]:raise ValueError('Story recovery evidence missing')
        for key in allowed:
            if key in roots:c.execute('INSERT INTO controls VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(roots[key])))
            else:c.execute('DELETE FROM controls WHERE key=?',(key,))


def capture_recovery(layout,rid):
    recovery_id='recovery-'+str(time.time_ns())
    root=layout.records/'recovery'/recovery_id;root.mkdir(parents=True,mode=0o700)
    current=layout.root/'current'
    previous=str(current.resolve()) if current.is_symlink() else None
    if current.exists() and not current.is_symlink():raise ValueError('Current must be a managed symlink')
    sources=[layout.config/'config.yaml',layout.config/'environment',layout.caddy/'Caddyfile',layout.caddy/'rtl-demo.env',
             layout.units/'caddy.service.d/rtl-demo.conf',layout.config/'resource-boundary.json',
             *[layout.units/n for n in ['rtl-demo-api.service','rtl-demo-worker.service','rtl-demo-worker.slice','rtl-demo-kg.service']]]
    entries=[]
    for i,source in enumerate(sources):
        no_links(source)
        entry={'target':str(source),'present':source.is_file()}
        if source.is_file():
            target=root/('file-'+str(i));shutil.copyfile(source,target);target.chmod(0o600)
            info=source.stat();entry.update(backup=target.name,mode=stat.S_IMODE(info.st_mode),uid=info.st_uid,gid=info.st_gid,sha256=digest(target))
        entries.append(entry)
    static=layout.static/'design'
    if static.exists():
        no_links(static)
        if any(p.is_symlink() for p in static.rglob('*')):raise ValueError('Symlink static state')
        shutil.copytree(static,root/'design')
    static_files=[{'path':p.relative_to(root/'design').as_posix(),'sha256':digest(p)} for p in (root/'design').rglob('*') if p.is_file()] if (root/'design').is_dir() else []
    database=backup_database(layout.data/'state.sqlite3',root/'state.sqlite3')
    key=layout.data/'session.key'
    if key.is_file():shutil.copyfile(key,root/'session.key');(root/'session.key').chmod(0o600)
    services={n:subprocess.run(['systemctl','is-active',n],capture_output=True,text=True).returncode==0 for n in ['rtl-demo-api','rtl-demo-worker','rtl-demo-kg']}
    data={'recovery_id':recovery_id,'release_id':rid,'target_origin':_record(layout,rid).get('target_origin','https://design.deepvalleychip.cn'),'story_roots':story_roots(root/'state.sqlite3'),'previous_code':previous,'files':entries,'static_files':static_files,'database_backup':bool(database),'services':services,
          'enabled':{name:subprocess.run(['systemctl','is-enabled','--quiet',name],capture_output=True).returncode==0 for name in services},'database_policy':'preserve current database; backup only for manual diagnosis','created_at':datetime.now(timezone.utc).isoformat()}
    atomic_json(root/'recovery.json',data)
    return data


def schema_compatible(database,previous_code):
    if not previous_code or not Path(database).is_file():return True
    # Existing tables/columns are additive in this release. Older code must
    # successfully read current schema before switching; never restore old DB.
    code='import sqlite3,sys; c=sqlite3.connect("file:"+sys.argv[1]+"?mode=ro",uri=True); from zerorepo.rtl_web.store import Store; assert c.execute("PRAGMA integrity_check").fetchone()[0]=="ok"; assert {"records","sessions","operations","messages"}<={x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type=\'table\'")}'
    host_command([Path(previous_code)/'.venv-web/bin/python','-c',code,database],cwd=previous_code)
    return True


def set_maintenance(layout,value):
    db=layout.data/'state.sqlite3'
    if not db.is_file():return
    with sqlite3.connect(db,timeout=15) as conn:
        tables={r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        # Additive migration works for the first upgrade from 001 too.
        conn.execute('CREATE TABLE IF NOT EXISTS controls (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        conn.execute('INSERT OR REPLACE INTO controls(key,value) VALUES(?,?)',('maintenance',json.dumps(bool(value))))


def _point_current(layout,target):
    current=layout.root/'current'
    if current.exists() and not current.is_symlink():raise ValueError('Unexpected current directory')
    temp=layout.root/('.current-'+str(time.time_ns()));temp.symlink_to(target);os.replace(temp,current)


def stop_backend():
    for name in ['rtl-demo-api','rtl-demo-worker']:
        if subprocess.run(['systemctl','is-active','--quiet',name],capture_output=True).returncode==0:
            host_command(['systemctl','stop',name])


def _install_units(layout,source):
    ops=source/'ops/deploy/rtl_demo'
    for name in ['rtl-demo-api.service','rtl-demo-worker.service','rtl-demo-worker.slice','rtl-demo-kg.service']:
        write_private(layout.units/name,(ops/name).read_bytes(),mode=0o644)
    write_private(layout.units/'caddy.service.d/rtl-demo.conf',(ops/'caddy-environment.conf.example').read_bytes(),mode=0o644)
    host_command(['systemctl','daemon-reload'])


def _resource_descriptor(layout):
    # Inspect the slice's effective kernel controls, not requested unit values.
    group=host_command(['systemctl','show','rtl-demo-worker.slice','--property=ControlGroup','--value']).strip()
    if group!='/rtl-demo-worker.slice':raise DeploymentError(4,'Worker slice not active')
    root=Path('/sys/fs/cgroup')
    if (root/'cgroup.controllers').is_file():
        entries={k:str(root/group.lstrip('/')/v) for k,v in [('memory_limit_file','memory.max'),('cpu_limit_file','cpu.max'),('tasks_limit_file','pids.max')]}
    else:
        entries={k:str(root/controller/group.lstrip('/')/v) for k,controller,v in [('memory_limit_file','memory','memory.limit_in_bytes'),('cpu_limit_file','cpu,cpuacct','cpu.cfs_quota_us'),('tasks_limit_file','pids','pids.max')]}
    if not all(Path(p).is_file() for p in entries.values()):raise DeploymentError(4,'Effective cgroup controls missing')
    write_private(layout.config/'resource-boundary.json',json.dumps(entries),group='rtl-demo',mode=0o640)


def _caddy_check_and_reload(layout,proposed,environment):
    path=layout.records/('Caddyfile-'+str(time.time_ns()))
    write_private(path,proposed,mode=0o600)
    env={**os.environ,**environment}
    # Both validate and systemctl reload use the exact EnvironmentFile values;
    # do not run `caddy adapt` (which would print expanded secrets).
    host_command(['caddy','validate','--config',path,'--adapter','caddyfile'],env=env)
    write_private(layout.caddy/'Caddyfile',proposed,mode=0o644)
    host_command(['systemctl','reload','caddy'])


def _production_preflight(layout,rid):
    release=layout.root/'releases'/rid
    env=environment_file(layout.config/'environment')
    env.update(RTL_DEMO_CONFIG=str(layout.config/'config.yaml'),PYTHONPATH=str(release))
    for cid in sorted(CASE_IDS):
        as_service([release/'.venv-web/bin/python','-m','zerorepo.rtl_web.cli','preflight','--config',layout.config/'config.yaml','--case',cid,'--json','--fail-if-unready'],env,cwd=release,timeout=180)
    import urllib.request
    request=urllib.request.Request('http://127.0.0.1:8000/api/health',headers={'X-Demo-Gateway-Key':env['RTL_DEMO_GATEWAY_KEY']})
    with urllib.request.urlopen(request,timeout=10) as stream:health=json.load(stream)
    if health.get('release_id')!=rid:raise DeploymentError(4,'API release mismatch')


def _restore(recovery,layout,*,commands=True):
    recovery_id=identifier(recovery['recovery_id']);root=layout.records/'recovery'/recovery_id
    allowed={str(layout.config/n) for n in ['config.yaml','environment','resource-boundary.json']}
    allowed|={str(layout.caddy/n) for n in ['Caddyfile','rtl-demo.env']}
    allowed|={str(layout.units/n) for n in ['rtl-demo-api.service','rtl-demo-worker.service','rtl-demo-worker.slice','rtl-demo-kg.service','caddy.service.d/rtl-demo.conf']}
    for entry in recovery.get('static_files',[]):
        if digest(child(root/'design',entry['path']))!=entry['sha256']:raise ValueError('Static recovery mismatch')
    if commands:stop_backend()
    for entry in recovery['files']:
        if entry['target'] not in allowed:raise ValueError('Unapproved recovery destination')
        target=no_links(entry['target'])
        if entry['present']:
            backup=child(root,entry['backup'])
            if digest(backup)!=entry['sha256']:raise ValueError('Recovery file mismatch')
            write_private(target,backup.read_bytes(),mode=entry['mode']);os.chown(target,entry['uid'],entry['gid'])
        else:target.unlink(missing_ok=True)
    previous=recovery['previous_code']
    if previous:
        if Path(previous).parent!=layout.root/'releases':raise ValueError('Unapproved recovery release')
        _point_current(layout,previous)
    else:
        current=layout.root/'current'
        if current.is_symlink():current.unlink()
    # Atomic replacements retain newly published hash assets for open browsers.
    design=root/'design'
    if design.exists():
        static=_static_module()
        for source in design.rglob('*'):
            if source.is_file():static.atomic_copy(source,layout.static/'design'/source.relative_to(design))
    # Deliberately never restore state.sqlite3 or session.key.
    if 'story_roots' in recovery:restore_story_roots(layout.data/'state.sqlite3',recovery['story_roots'])
    set_maintenance(layout,False)
    if commands:
        host_command(['systemctl','daemon-reload'])
        for service,was_active in recovery['services'].items():
            if service not in {'rtl-demo-api','rtl-demo-worker','rtl-demo-kg'}:raise ValueError('Unapproved recovery service')
            if recovery.get('enabled',{}).get(service):host_command(['systemctl','enable',service])
            else:subprocess.run(['systemctl','disable',service],capture_output=True)
            if was_active:host_command(['systemctl','restart',service])
            else:subprocess.run(['systemctl','stop',service],capture_output=True)
        host_command(['caddy','validate','--config',layout.caddy/'Caddyfile','--adapter','caddyfile'],env={**os.environ,**environment_file(layout.caddy/'rtl-demo.env')} if (layout.caddy/'rtl-demo.env').exists() else os.environ.copy())
        host_command(['systemctl','reload','caddy'])
    return recovery_id


def activate(release_id,*,dry_run=False,layout=Layout()):
    rid=identifier(release_id);record=_record(layout,rid)
    if record['state'] not in {'prepared','active_unverified','accepted','rolled_back'}:raise DeploymentError(4,'Release not prepared')
    source=Path(record['candidate']);m=checked(source)
    if m.get('target_origin')=='https://agent.deepvalleychip.cn':
        raise DeploymentError(4,'Agent-site package: legacy design activation is disabled. Use the existing rtl-demo-public.service update procedure; preserve the independent design site.')
    if digest(source/'deployment.json')!=record['manifest_sha256']:raise ValueError('Prepared manifest mismatch')
    preview={'release_id':rid,'state':'activate_preview','dry_run':dry_run,
             'steps':['maintenance','stop API/worker','consistent backup','schema gate','import approved seed','switch backend','start and probe four cases','design-only static install','validate complete Caddy config','reload Caddy'],
             'database_policy':'never roll back database or signing key','services':['rtl-demo-api','rtl-demo-worker','rtl-demo-kg']}
    if dry_run:return preview
    privileged();sealed(source)
    release=layout.root/'releases'/rid
    capacity=json.loads(host_command([release/'.venv-web/bin/python',release/'.deployment/server_config.py','capacity','--source',record['config']],
                                     cwd=release,env={**os.environ,'PYTHONPATH':str(release)}))
    if not capacity.get('ready'):raise DeploymentError(4,'Host capacity gate failed before stopping any service')
    with deployment_lock(layout):
        if (layout.root/'current').is_symlink() and (layout.root/'current').resolve()==layout.root/'releases'/rid:
            return release_status(rid,layout.records)
        recovery=None;set_maintenance(layout,True)
        try:
            recovery=capture_recovery(layout,rid)
            stop_backend()
            schema_compatible(layout.data/'state.sqlite3',recovery['previous_code'])
            release=layout.root/'releases'/rid
            write_private(layout.config/'config.yaml',Path(record['config']).read_bytes(),group='rtl-demo',mode=0o640)
            env=environment_file(layout.config/'environment');env.update(RTL_DEMO_CONFIG=str(layout.config/'config.yaml'),PYTHONPATH=str(release))
            as_service([release/'.venv-web/bin/python','-m','zerorepo.rtl_web.cli','import-seed','--config',layout.config/'config.yaml','--source',release/'.deployment/seed'],env,cwd=release)
            _install_units(layout,source)
            # Fixed-size storage is initialized only during the first stopped
            # deployment, never reformatted on upgrade or rollback.
            host_command(['bash',source/'ops/scripts/rtl_demo/prepare-job-storage.sh'])
            mount_name=host_command(['systemd-escape','--path','--suffix=mount',str(layout.data/'jobs')]).strip()
            if not re.fullmatch(r'[A-Za-z0-9\\_.-]+\.mount',mount_name):raise ValueError('Invalid mount unit name')
            write_private(layout.units/mount_name,(source/'ops/deploy/rtl_demo/job-storage.mount.example').read_bytes(),mode=0o644)
            host_command(['systemctl','daemon-reload']);host_command(['systemctl','enable',mount_name])
            neo=layout.config/'neo4j/neo4j.conf'
            for name in ['server-logs.xml','user-logs.xml']:
                logging_source=layout.root/'toolchain/neo4j/conf'/name
                if logging_source.is_file() and not (neo.parent/name).exists():
                    write_private(neo.parent/name,logging_source.read_bytes(),group='rtl-demo-kg',mode=0o640)
            if not neo.exists():write_private(neo,(source/'ops/deploy/rtl_demo/neo4j.conf.example').read_bytes(),group='rtl-demo-kg',mode=0o640)
            # Both service accounts need traversal of /etc/rtl-demo, but secret
            # files still grant reads only to their intended group.
            layout.config.chmod(0o751)
            os.chown(neo.parent,0,__import__('grp').getgrnam('rtl-demo-kg').gr_gid);neo.parent.chmod(0o750)
            _point_current(layout,release)
            host_command(['systemctl','enable','rtl-demo-kg','rtl-demo-api','rtl-demo-worker'])
            host_command(['systemctl','start','rtl-demo-kg'])
            # Fresh KG initialization and subsequent checks run with the private
            # service environment. Default credentials never leave loopback.
            deadline=time.monotonic()+45
            while True:
                try:
                    as_service([release/'.venv-agent/bin/python',release/'.deployment/server_config.py','initialize-kg','--source',layout.config/'config.yaml'],env,cwd=release,timeout=10)
                    break
                except DeploymentError:
                    if time.monotonic()>=deadline:raise
                    time.sleep(0.5)
            host_command(['systemctl','start','rtl-demo-api','rtl-demo-worker'])
            deadline=time.monotonic()+45
            while not (layout.data/'worker-state.json').is_file() and time.monotonic()<deadline:time.sleep(0.2)
            _resource_descriptor(layout)
            _production_preflight(layout,rid)
            static=_static_module();static.install(source/'design',base=layout.static)
            caddy_env=environment_file(layout.caddy/'rtl-demo.env')
            proposed=merge_design((layout.caddy/'Caddyfile').read_text(),(source/'ops/deploy/rtl_demo/Caddyfile.design.example').read_text())
            _caddy_check_and_reload(layout,proposed,caddy_env)
            set_maintenance(layout,False)
            record.update(state='active_unverified',activated_at=datetime.now(timezone.utc).isoformat(),recovery_set=recovery['recovery_id'],acceptance='not_run')
            save_record(layout,record)
            return release_status(rid,layout.records)
        except Exception as error:
            if recovery:
                try:_restore(recovery,layout)
                except Exception:
                    record.update(state='failed',blockers=['activation_failed','recovery_incomplete'],recovery_set=recovery['recovery_id']);save_record(layout,record)
                    raise DeploymentError(7,'Recovery incomplete; inspect recorded recovery set') from None
            else:
                set_maintenance(layout,False)
            record.update(state='failed',blockers=['activation_failed'],recovery_set=recovery['recovery_id'] if recovery else None);save_record(layout,record)
            raise DeploymentError(6,'Activation failed; previous entry restored') from None


def rollback(recovery_id,*,dry_run=False,layout=Layout()):
    recovery_id=identifier(recovery_id);path=layout.records/'recovery'/recovery_id/'recovery.json'
    data=json.loads(path.read_text())
    if data['recovery_id']!=recovery_id:raise ValueError('Recovery identity mismatch')
    result={'recovery_set':recovery_id,'release_id':data['release_id'],'state':'rollback_preview' if dry_run else 'rolled_back','dry_run':dry_run,'database_policy':'preserve current database and signing key'}
    if dry_run:return result
    privileged()
    with deployment_lock(layout):
        set_maintenance(layout,True)
        schema_compatible(layout.data/'state.sqlite3',data['previous_code'])
        try:_restore(data,layout)
        except Exception:raise DeploymentError(7,'Recovery incomplete; inspect recorded recovery set') from None
        record=_record(layout,data['release_id']);record.update(state='rolled_back');save_record(layout,record)
    return result


def accept(release_id,evidence_index,*,dry_run=False,layout=Layout()):
    rid=identifier(release_id);record=_record(layout,rid)
    if record['state'] not in {'active_unverified','accepted'}:raise DeploymentError(4,'Release is not active')
    current=layout.root/'current'
    if not current.is_symlink() or current.resolve()!=layout.root/'releases'/rid:raise DeploymentError(4,'Release is not current')
    path=no_links(evidence_index)
    try:
        machine=hashlib.sha256(Path('/etc/machine-id').read_bytes()).hexdigest()
        if record.get('host_id')!=machine:raise ValueError('Prepared host mismatch')
        manifest=checked(Path(record['candidate']))
        validate_acceptance(json.loads(path.read_text()),rid,path.parent,host_id=machine,
                            origin=manifest.get('target_origin','https://design.deepvalleychip.cn'))
    except (ValueError,OSError,KeyError):raise DeploymentError(4,'Bound acceptance evidence incomplete') from None
    if dry_run:return {'release_id':rid,'state':'accept_preview','dry_run':True}
    privileged();sealed(path.parent)
    with deployment_lock(layout):
        _production_preflight(layout,rid)
        record.update(state='accepted',acceptance='passed',evidence_index=str(path),evidence_index_sha256=digest(path))
        save_record(layout,record)
    return release_status(rid,layout.records)


def main():
    parser=argparse.ArgumentParser(description='Private RTL deployment coordinator')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('build');p.add_argument('--config',required=True);p.add_argument('--release-id',required=True);p.add_argument('--out',required=True)
    p=sub.add_parser('check');p.add_argument('--release',required=True)
    p=sub.add_parser('prepare');p.add_argument('--release',required=True);p.add_argument('--config',required=True);p.add_argument('--dry-run',action='store_true')
    for command in ['activate','status','accept']:
        p=sub.add_parser(command);p.add_argument('--release-id',required=True)
        if command!='status':p.add_argument('--dry-run',action='store_true')
        if command=='accept':p.add_argument('--evidence-index',required=True)
    p=sub.add_parser('rollback');p.add_argument('--recovery-set',required=True);p.add_argument('--dry-run',action='store_true')
    args=parser.parse_args()
    try:
        if args.command=='build':result=build(args.config,args.release_id,args.out)
        elif args.command=='check':
            m=checked(Path(args.release));result={'release_id':m['release_id'],'file_count':len(m['files']),'state':'staged'}
        elif args.command=='prepare':result=prepare(args.release,args.config,dry_run=args.dry_run)
        elif args.command=='activate':result=activate(args.release_id,dry_run=args.dry_run)
        elif args.command=='status':result=release_status(args.release_id)
        elif args.command=='rollback':result=rollback(args.recovery_set,dry_run=args.dry_run)
        else:result=accept(args.release_id,args.evidence_index,dry_run=args.dry_run)
        print(json.dumps(result,ensure_ascii=False))
    except (ValueError,OSError,KeyError,subprocess.SubprocessError) as error:
        print(json.dumps({'error':'deployment_not_ready' if isinstance(error,DeploymentError) else 'deployment_invalid','command':args.command}),file=sys.stderr)
        raise SystemExit(error.code if isinstance(error,DeploymentError) else 3)


if __name__=='__main__':main()
