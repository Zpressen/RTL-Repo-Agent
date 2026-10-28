"""Runs only after the locked Web/Agent environment has been built on target.

No secret values are returned. Configuration is always read from private files,
never accepted on the command line.
"""
from pathlib import Path
import argparse
import json
import os
import re
import shutil
import sys
import yaml


def derive(args):
    cfg=yaml.safe_load(Path(args.source).read_text()) or {}
    if cfg.get('development') or cfg.get('allowed_origins')!=['https://design.deepvalleychip.cn']:
        raise ValueError('Production origin/development mismatch')
    cfg.update(repo_root=str(args.release),data_root=str(args.data),release_id=args.release_id,development=False)
    cfg.pop('source_output',None)
    cfg.setdefault('runtime',{}).update(python=str(args.release/'.venv-agent/bin/python'),
        agent_config='/etc/rtl-demo/agent.yaml',oracle_root=str(args.oracle),
        toolchain_bin='/opt/rtl-agent/toolchain/bin',parser_library=str(args.parser),compile_jobs=1)
    from zerorepo.rtl_web.budgets import host_memory
    memory=host_memory()
    cfg.setdefault('budgets',{}).setdefault('existing_services_bytes',memory['total']-memory['available'])
    cfg['resource_boundary']='/etc/rtl-demo/resource-boundary.json'
    from zerorepo.rtl_web.cases import CASES
    if set(cfg.get('cases',{}))!=set(CASES):raise ValueError('Four case mappings required')
    for cid,binding in cfg['cases'].items():
        if binding.get('spec')!=CASES[cid]['spec']:raise ValueError('Unapproved case specification')
    # yaml expands no shell variables. LLMConfig performs its existing selected
    # provider substitution at use time; private KG credentials stay private.
    target=Path(args.target)
    if target.is_symlink():raise ValueError('Unsafe configuration destination')
    target.write_text(yaml.safe_dump(cfg,allow_unicode=True,sort_keys=False));target.chmod(0o600)


def offline_check(path):
    from zerorepo.rtl_web.settings import Settings
    from zerorepo.rtl_web.runtime import load_agent
    from zerorepo.rtl_impl.module_planner import PlannerRunner
    from zerorepo.rtl_impl.debug_agent.system_debug_runner import SystemSimReviewer
    from zerorepo.rtl_impl.codex_debug.runner import CodexDebugRunner
    from zerorepo.rtl_impl.rtl_kg.rtl_file_graph_builder import VerilogTreeSitter
    settings=Settings(path,create_data=False);data,llm=load_agent(settings)
    checks={'release_import':Path(__import__('zerorepo').__file__).resolve().is_relative_to(settings.repo),
            'planner_import':True,'reviewer_import':True,
            'parser':not VerilogTreeSitter.get_parser().parse(b'module probe; endmodule').root_node.has_error,
            'kg_required':bool(data.get('rtl_kg',{}).get('enabled'))}
    for cid in settings.raw['cases']:
        selected=settings.for_case(cid)
        checks[cid+'_materials']=bool(selected.spec.is_file() and selected.verify_script and selected.verify_script.is_file()
                                     and all(p.is_dir() for p in selected.reference_dirs))
    debug=data.get('rtl_debug',{})
    if debug.get('backend')=='codex':
        checks['backend_cli']=bool(shutil.which(debug.get('codex_bin','codex')))
        try:CodexDebugRunner(profile=debug.get('codex_profile','proxy-a')).profile_layers();checks['backend_profile']=True
        except (ValueError,OSError,RuntimeError):checks['backend_profile']=False
    checks['model_credentials']=bool(getattr(llm,'api_key',None))
    return {'ready':all(checks.values()),'checks':checks,'phase':'candidate_offline','worker_required':False}


def initialize_kg(path):
    """Change a fresh, loopback-only Neo4j default password using Bolt params.

    Neither the initial nor final password is ever placed in process argv.
    Existing production credentials are verified without resetting the graph.
    """
    from neo4j import GraphDatabase
    from neo4j.exceptions import AuthError
    from zerorepo.rtl_web.settings import Settings
    cfg=yaml.safe_load(Settings(path,create_data=False).agent_config.read_text())['rtl_kg']['neo4j']
    password=cfg.get('password','')
    if cfg.get('uri') not in {'bolt://127.0.0.1:7687','neo4j://127.0.0.1:7687'} or cfg.get('user')!='neo4j':raise ValueError('Unapproved KG target')
    if not isinstance(password,str) or len(password)<20 or password.startswith(('${','REPLACE_')):raise ValueError('Independent KG password required')
    try:
        with GraphDatabase.driver(cfg['uri'],auth=('neo4j',password),connection_timeout=3) as driver:
            driver.verify_connectivity()
            with driver.session() as session:session.run('RETURN 1').consume()
        return
    except AuthError:pass
    with GraphDatabase.driver(cfg['uri'],auth=('neo4j','neo4j'),connection_timeout=3) as driver:
        with driver.session(database='system') as session:
            session.run('ALTER CURRENT USER SET PASSWORD FROM $old TO $new',old='neo4j',new=password).consume()
    with GraphDatabase.driver(cfg['uri'],auth=('neo4j',password),connection_timeout=3) as driver:driver.verify_connectivity()


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('derive');a.add_argument('--source',type=Path,required=True);a.add_argument('--target',type=Path,required=True)
    for key in ['release','oracle','data','parser']:a.add_argument('--'+key,type=Path,required=True)
    a.add_argument('--release-id',required=True)
    for command in ['check','initialize-kg','capacity']:
        a=sub.add_parser(command);a.add_argument('--source',type=Path,required=True)
    args=p.parse_args()
    try:
        if args.command=='derive':derive(args)
        elif args.command=='check':print(json.dumps(offline_check(args.source)))
        elif args.command=='initialize-kg':initialize_kg(args.source)
        else:
            from zerorepo.rtl_web.settings import Settings
            from zerorepo.rtl_web.budgets import host_memory,disk_admission
            settings=Settings(args.source,create_data=False);b=settings.budgets;memory=host_memory()
            budget=sum(int(b.get(k,0)) for k in ['worker_memory_bytes','api_memory_bytes','kg_memory_bytes','host_reserve_bytes'])
            baseline=int(b.get('existing_services_bytes',memory['total']-memory['available']))
            disk_admission(settings.data,min_free_bytes=int(b.get('min_free_bytes',5*1024**3)))
            print(json.dumps({'ready':bool(budget and budget+baseline<=memory['total']),
                              'physical_bytes':memory['total'],'original_services_bytes':baseline,'reserved_budget_bytes':budget}))
    except Exception:
        print(json.dumps({'error':'private_configuration_or_dependency_unready'}),file=sys.stderr)
        raise SystemExit(4)


if __name__=='__main__':main()
