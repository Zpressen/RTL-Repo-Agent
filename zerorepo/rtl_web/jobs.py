"""Trusted preparation for a runtime that never opens the web ledger."""
from __future__ import annotations
import json
import os
from pathlib import Path
import re
import shutil
import yaml
from .artifacts import Artifacts, atomic_json, safe_path, sha, tree_manifest
from .deployment_models import JobDescriptor
from .schemas import DemoError


def job_root(settings,run_id):
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,159}',run_id):
        raise DemoError('unsafe_job','运行标识无效。',422)
    return safe_path(settings.data/'jobs',run_id)


def contracts_for(settings,store,run_id,sid,seen=None):
    seen=set() if seen is None else seen
    if run_id in seen:raise DemoError('context_mismatch','接口契约引用形成循环。',409)
    seen.add(run_id)
    run=store.get('run',run_id,sid)
    if run['origin']=='historical':
        item=store.historical_input(settings.case['case_id'],run_id)
        if item:
            if item['status']!='present':raise DemoError('contracts_missing','该历史版本未保存接口契约，请从预置规格新建运行。',422)
            record=store.get('artifact',item['artifact_id'])
            path=Artifacts(settings.data,store).file(record)
            if sha(path)!=item['expected_sha256']:raise DemoError('contract_changed','接口契约摘要不一致。',409)
            return path
        if not settings.development:raise DemoError('contracts_missing','生产历史输入尚未登记。',422)
        # Legacy source access is restricted to the existing development workflow.
        path=settings.source/'.zerorepo/module_planner/outputs/contracts.json'
        evidence=settings.repo/'configs'/('rtl_demo_e203.evidence.json' if settings.case['case_id']=='e203' else 'rtl_demo_cases.evidence.json')
        data=json.loads(evidence.read_text());expected=(data if settings.case['case_id']=='e203' else data[settings.case['case_id']]).get('contracts_sha256')
        if not expected or not path.is_file():raise DemoError('contracts_missing','该历史版本未保存接口契约。',422)
        if sha(path)!=expected:raise DemoError('contract_changed','接口契约摘要不一致。',409)
        return path
    path=job_root(settings,run_id)/'.zerorepo/module_planner/outputs/contracts.json'
    if path.is_file():return path
    legacy=settings.data/'runs'/run_id/'.zerorepo/module_planner/outputs/contracts.json'
    if settings.development and legacy.is_file():return legacy
    if run.get('source_run_id'):return contracts_for(settings,store,run['source_run_id'],sid,seen)
    raise DemoError('contracts_missing','该运行没有可追溯接口契约。',422)


def prepare_job(settings,store,operation):
    from .chat import validate_context
    selected=settings.for_case(operation['context_ref'].get('case_id','e203'))
    context=validate_context(store,operation['session_id'],operation['context_ref'])
    root=job_root(selected,operation['run_id']);root.mkdir(parents=True,exist_ok=True,mode=0o700)
    descriptor=root/'job.json'
    if descriptor.exists():raise DemoError('job_exists','该运行输入已准备，不能重复执行。',409)
    inputs=root/'job_inputs';inputs.mkdir(mode=0o700)
    spec=inputs/'spec.md';shutil.copyfile(selected.spec,spec)
    records={};merged=root/'.zerorepo/workspace/merged';merged.mkdir(parents=True,exist_ok=True)
    from zerorepo.rtl_impl.rtl_memory.adapter import freeze_snapshot
    from zerorepo.rtl_impl.rtl_memory.ledger import MemoryLedger
    library = MemoryLedger(selected.memory_library) if selected.memory_library.exists() else None
    memory_path, memory_hash = freeze_snapshot(library, selected.case['case_id'], operation['session_id'], inputs/'memory', {'stage':'debug','module':selected.case.get('planner_top','')})
    records['memory'] = {'path':memory_path.relative_to(root).as_posix(), 'sha256':memory_hash}
    if operation['kind'] in {'verify','fix'}:
        version=store.get('version',context['version_id'],operation['session_id'])
        src=Artifacts(selected.data,store).version_path(version)
        for entry in version['file_manifest']:
            dst=safe_path(inputs/'rtl',entry['path']);dst.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(safe_path(src,entry['path']),dst)
            target=safe_path(merged,entry['path']);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(dst,target)
        records['rtl']={'tree_sha256':version['tree_sha256'],'file_manifest':version['file_manifest']}
    if operation['kind']=='fix':
        path=contracts_for(selected,store,context['run_id'],operation['session_id'])
        shutil.copyfile(path,inputs/'contracts.json');records['contracts_sha256']=sha(inputs/'contracts.json')
    # Only the Agent configuration is passed; no web/gateway/cookie secrets.
    agent=inputs/'agent.yaml';shutil.copyfile(selected.agent_config,agent)
    agent_data=yaml.safe_load(agent.read_text()) or {}
    debug=agent_data.get('rtl_debug',{}) or {}
    environment_names=[]
    if debug.get('backend')=='codex' and operation['kind']!='verify':
        binary=shutil.which(debug.get('codex_bin','codex'),path=selected.tool_env().get('PATH'))
        if not binary:raise DemoError('backend_cli','服务器的模型执行工具尚未配置。',503)
        records['backend_cli']=str(Path(binary).absolute())
        records['backend_cli_sha256']=sha(Path(binary).resolve())
        import tomllib
        profile=os.environ.get('ZEROREPO_CODEX_PROFILE',debug.get('codex_profile','proxy-a'))
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',profile):raise DemoError('backend_profile','后端profile不安全。',503)
        home=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))
        dst=inputs/'tool-profile';dst.mkdir(mode=0o700)
        for name in ['config.toml',profile+'.config.toml']:
            src=home/name
            if src.is_symlink():raise DemoError('backend_profile','后端profile不安全。',503)
            if src.is_file():
                shutil.copyfile(src,dst/name)
                def env_keys(value):
                    if isinstance(value,dict):
                        for k,v in value.items():
                            if k=='env_key' and isinstance(v,str):environment_names.append(v)
                            env_keys(v)
                env_keys(tomllib.loads(src.read_text()))
        if not (dst/(profile+'.config.toml')).is_file():raise DemoError('backend_profile','服务器的指定profile尚未配置。',503)
    raw=dict(selected.raw)
    raw.pop('memory_library', None)
    raw.update(repo_root=str(selected.repo),data_root=str(root/'runtime-state'),
               source_output=str(inputs),case={**selected.case,'spec':str(spec),'source_output':str(inputs)},cases={})
    raw['runtime']={**selected.runtime,'agent_config':str(agent)}
    config=inputs/'config.yaml';config.write_text(yaml.safe_dump(raw,allow_unicode=True))
    records.update(config='job_inputs/config.yaml',config_sha256=sha(config),
                   profile_manifest=[{'path':p.relative_to(inputs).as_posix(),'sha256':sha(p)} for p in sorted((inputs/'tool-profile').rglob('*')) if p.is_file()],
                   spec='job_inputs/spec.md',
                   spec_sha256=sha(spec),agent_config_sha256=sha(agent),context_ref=context,
                   environment_names=sorted(set(environment_names)))
    # Material identity is bound before starting any tool, not after its report.
    from .runtime import verifier_manifest
    records['oracle_manifest']=verifier_manifest(selected)
    payload=JobDescriptor(operation_id=operation['operation_id'],run_id=operation['run_id'],
                          case_id=selected.case['case_id'],kind=operation['kind'],
                          release_id=selected.release_id,inputs=records,
                          budgets={'timeout':selected.timeout,'verifier_timeout':selected.verifier_timeout,
                                   'compile_jobs':int(selected.runtime.get('compile_jobs',1))},
                          kg_partition='web-'+operation['run_id']).model_dump()
    atomic_json(descriptor,payload)
    for path in inputs.rglob('*'):
        if path.is_file():os.chmod(path,0o400)
    os.chmod(descriptor,0o400)
    return descriptor


def load_job(path):
    path=Path(path).absolute()
    if path.is_symlink():raise DemoError('unsafe_job','任务描述符不安全。',422)
    job=JobDescriptor.model_validate_json(path.read_text()).model_dump()
    root=path.parent
    if job['inputs'].get('memory'):
        from zerorepo.rtl_impl.rtl_memory.ledger import digest
        item = job['inputs']['memory']
        if digest(json.loads(safe_path(root,item['path']).read_text())) != item['sha256']:
            raise DemoError('input_changed','任务经验快照发生变化。',409)
    for file,expected in [('spec.md',job['inputs']['spec_sha256']),('agent.yaml',job['inputs']['agent_config_sha256'])]:
        if sha(safe_path(root,'job_inputs/'+file))!=expected:raise DemoError('input_changed','任务输入发生变化。',409)
    if job['inputs'].get('config_sha256') and sha(root/job['inputs']['config'])!=job['inputs']['config_sha256']:
        raise DemoError('input_changed','任务配置发生变化。',409)
    for entry in job['inputs'].get('profile_manifest',[]):
        if sha(safe_path(root/'job_inputs',entry['path']))!=entry['sha256']:
            raise DemoError('input_changed','选定后端配置发生变化。',409)
    if job['inputs'].get('backend_cli_sha256'):
        if sha(Path(job['inputs']['backend_cli']).resolve())!=job['inputs']['backend_cli_sha256']:
            raise DemoError('input_changed','模型执行工具发生变化。',409)
    if 'rtl' in job['inputs']:
        if tree_manifest(root/'job_inputs/rtl')!=(job['inputs']['rtl']['tree_sha256'],job['inputs']['rtl']['file_manifest']):
            raise DemoError('input_changed','RTL输入发生变化。',409)
    if job['kind']=='fix' and sha(root/'job_inputs/contracts.json')!=job['inputs']['contracts_sha256']:
        raise DemoError('input_changed','接口契约发生变化。',409)
    return job


def prepare_chat_job(settings):
    """A transient provider-only view; no KG, debug, ledger or history on disk."""
    import tempfile
    root=settings.data/'jobs';root.mkdir(parents=True,exist_ok=True)
    task=Path(tempfile.mkdtemp(prefix='chat-',dir=root));inputs=task/'job_inputs';inputs.mkdir(mode=0o700)
    data=yaml.safe_load(settings.agent_config.read_text()) or {}
    agent=inputs/'agent.yaml';agent.write_text(yaml.safe_dump({'llm':data.get('llm',{})}))
    cfg={'repo_root':str(settings.repo),'data_root':str(task/'runtime-state'),'development':False,
         'release_id':settings.release_id,'case':{'case_id':settings.case['case_id']},
         'runtime':{'agent_config':str(agent),'python':settings.python,
                    **{key:settings.runtime[key] for key in ['chat_max_tokens','chat_thinking','chat_execution_enabled'] if key in settings.runtime}}}
    config=inputs/'config.yaml';config.write_text(yaml.safe_dump(cfg))
    atomic_json(task/'job.json',{'kind':'chat','release_id':settings.release_id})
    for path in inputs.iterdir():path.chmod(0o400)
    return task,config
