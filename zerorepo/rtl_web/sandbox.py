"""Fixed filesystem boundary for trusted runtime and narrower model processes."""
from __future__ import annotations
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from .schemas import DemoError

SAFE_ENV={'OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','PATH','LANG','LC_ALL','TZ','TMPDIR','PYTHONPATH','LD_LIBRARY_PATH','SSL_CERT_FILE','SSL_CERT_DIR',
          'CC','CXX','ZEROREPO_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY','AZURE_OPENAI_API_KEY','GOOGLE_API_KEY',
          'ZEROREPO_DEPLOY_ORACLE_ROOT','ZEROREPO_DEPLOY_TOOLCHAIN_BIN','ZEROREPO_DEPLOY_COMPILE_JOBS',
          'RTL_TS_LANG_SO','RTL_TS_GRAMMAR_DIR','RTL_TS_CACHE_DIR','ZEROREPO_RTL_KG_PARTITION'}


def minimal_environment(env,extra_names=()):
    blocked={'RTL_DEMO_GATEWAY_KEY','RTL_DEMO_PASSWORD_HASH','RTL_DEMO_DEVELOPMENT'}
    allowed=SAFE_ENV|set(extra_names)
    return {k:v for k,v in env.items() if k in allowed and k not in blocked}


def _mount(args,src,dst=None,writable=False):
    p=Path(src).absolute()
    if not p.exists():return
    if p==Path('/'):raise ValueError('Host root mount is forbidden')
    args.extend(['--bind' if writable else '--ro-bind',str(p),str(dst or p)])


def base_command():
    binary=shutil.which('bwrap')
    if not binary:raise DemoError('sandbox_unavailable','任务隔离工具尚未安装。',503)
    args=[binary,'--unshare-user','--unshare-pid','--die-with-parent','--new-session',
          '--proc','/proc','--dev','/dev','--tmpfs','/tmp']
    for root in ['/usr','/bin','/sbin','/lib','/lib64']:_mount(args,root)
    for name in ['/etc/resolv.conf','/etc/hosts','/etc/nsswitch.conf','/etc/ssl/certs','/etc/pki','/etc/passwd','/etc/group']:_mount(args,name)
    return args


def job_command(settings,job,command):
    job=Path(job).absolute();root=job.parent
    if root.parent!=settings.data/'jobs' or job.name!='job.json' or root.is_symlink():
        raise DemoError('unsafe_job','任务不在批准的执行目录。',422)
    args=base_command()
    _mount(args,settings.repo/'zerorepo')
    _mount(args,Path(settings.python).absolute().parents[1])
    for name in ['rtl_demo_e203.evidence.json','rtl_demo_cases.evidence.json']:
        _mount(args,settings.repo/'configs'/name)
    # Virtual environments reference a real interpreter outside their bin dir.
    _mount(args,Path(settings.python).resolve().parents[1])
    if settings.runtime.get('toolchain_bin'):_mount(args,settings.path(settings.runtime['toolchain_bin']).parent)
    if settings.runtime.get('parser_library'):_mount(args,settings.path(settings.runtime['parser_library']))
    if settings.oracle:_mount(args,settings.oracle)
    descriptor=json.loads(job.read_text())
    binary=descriptor.get('inputs',{}).get('backend_cli')
    if binary:
        if not Path(binary).is_absolute():raise DemoError('unsafe_job','模型工具路径不安全。',422)
        # Mount only the selected native executable, never its user's home or
        # credentials. The PATH alias remains usable inside the outer runtime.
        _mount(args,Path(binary).resolve(),Path(binary).absolute())
    _mount(args,root,writable=True)
    _mount(args,root/'job_inputs')
    _mount(args,job)
    args+=['--chdir',str(root),'--',*map(str,command)]
    return args


def native_probe():
    try:
        args=base_command()+['--','/usr/bin/true']
        r=subprocess.run(args,capture_output=True,timeout=5,env={'PATH':'/usr/bin:/bin'})
        return r.returncode==0
    except (OSError,subprocess.SubprocessError,DemoError):return False


def model_command(descriptor,command,process_env,bridge):
    """Model-side view excludes oracle, job_inputs and the trusted descriptor."""
    args=base_command()
    repo=Path(__file__).resolve().parents[2]
    _mount(args,repo/'zerorepo')
    _mount(args,Path(sys.executable).absolute().parents[1])
    _mount(args,Path(sys.executable).resolve().parents[1])
    codex=shutil.which(command[0],path=process_env.get('PATH'))
    if not codex:raise DemoError('backend_unavailable','模型工具尚未安装。',503)
    _mount(args,Path(codex).resolve())
    _mount(args,descriptor.spec_root)
    _mount(args,descriptor.merged_root,writable=True)
    home=Path(process_env['CODEX_HOME'])
    _mount(args,home,writable=True)
    output=descriptor.private_root/'model_output';output.mkdir(exist_ok=True)
    _mount(args,output,writable=True)
    _mount(args,bridge.directory)
    model_env={'PATH','LANG','LC_ALL','TZ','TMPDIR','PYTHONPATH','LD_LIBRARY_PATH','SSL_CERT_FILE','SSL_CERT_DIR','CODEX_HOME'}
    safe={k:v for k,v in process_env.items() if k in model_env}
    # Selected provider env keys are registered by the trusted profile parser.
    import tomllib
    base=tomllib.loads((home/'config.toml').read_text())
    base.setdefault('mcp_servers',{}).setdefault('zerorepo_rtl_debug',{}).setdefault('env',{}).update(bridge.environment())
    from zerorepo.rtl_impl.codex_debug.runner import CodexDebugRunner
    (home/'config.toml').write_text(CodexDebugRunner._serialize_toml(base))
    os.chmod(home/'config.toml',0o600)
    provider=base.get('model_provider','openai')
    env_key=base.get('model_providers',{}).get(provider,{}).get('env_key') or ('OPENAI_API_KEY' if provider=='openai' else None)
    if env_key in {'RTL_DEMO_GATEWAY_KEY','RTL_DEMO_PASSWORD_HASH','NEO4J_PASSWORD','KG_PASSWORD'}:
        raise ValueError('Provider cannot use a gateway or KG secret')
    if env_key and env_key in process_env:safe[env_key]=process_env[env_key]
    safe.update(bridge.environment())
    safe['TMPDIR']='/tmp'
    command=[str(Path(codex).resolve()),*command[1:]]
    args+=['--chdir',str(descriptor.task_root),'--',*command]
    return args,safe
