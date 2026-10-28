"""Private loopback Neo4j supervisor for the ordinary-user demo environment.

JVM budgets and a host reserve check protect the existing preview. This
supervisor is not a replacement for the worker's required cgroup boundary.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import secrets
import shlex
import shutil
import signal
import subprocess
import time
import yaml
from neo4j import GraphDatabase


def process_tree_rss(root_pid):
    infos={}
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            if proc.stat().st_uid!=os.getuid():continue
            info={line.split(':',1)[0]:line.split(':',1)[1].strip() for line in (proc/'status').read_text().splitlines()}
            infos[int(proc.name)]=(int(info['PPid']),int(info.get('VmRSS','0 kB').split()[0])*1024)
        except (OSError,ValueError):pass
    children={root_pid}
    for _ in range(8):children.update(pid for pid,(parent,rss) in infos.items() if parent in children)
    return sum(infos[pid][1] for pid in children if pid in infos)


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True);args=p.parse_args()
    root=args.root.resolve();os.umask(0o077)
    control=root/'control';lock=(control/'kg.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:return
    agent=root/'private/agent.yaml';data=yaml.safe_load(agent.read_text())
    cfg=data.setdefault('rtl_kg',{});connection=cfg.setdefault('neo4j',{})
    password=connection.get('password','')
    if not password or password.startswith('REPLACE_'):password=secrets.token_urlsafe(32)
    cfg.update(enabled=True,mode='required')
    connection.update(uri='bolt://127.0.0.1:17687',user='neo4j',password=password)
    temporary=agent.with_suffix('.kg-new');temporary.write_text(yaml.safe_dump(data));temporary.chmod(0o600);os.replace(temporary,agent)
    home=root/'kg';conf=home/'conf';conf.mkdir(mode=0o700,parents=True,exist_ok=True)
    for directory in ['data','logs','run','transactions']:(home/directory).mkdir(mode=0o700,exist_ok=True)
    distribution=root/'toolchain/neo4j'
    for name in ['server-logs.xml','user-logs.xml']:
        source=distribution/'conf'/name
        if source.exists():shutil.copyfile(source,conf/name)
    lines=['server.default_listen_address=127.0.0.1','server.bolt.listen_address=127.0.0.1:17687',
        'server.http.enabled=false','server.https.enabled=false',
        'server.memory.heap.initial_size=128m','server.memory.heap.max_size=128m','server.memory.pagecache.size=32m',
        'server.bolt.thread_pool_min_size=1','server.bolt.thread_pool_max_size=8',
        'server.jvm.additional=-XX:ActiveProcessorCount=1',
        'server.jvm.additional=-XX:MaxMetaspaceSize=128m',
        'server.jvm.additional=-XX:ReservedCodeCacheSize=48m',
        'server.jvm.additional=-XX:MaxDirectMemorySize=64m',
        'server.jvm.additional=-Xss512k']
    for key,value in [('data','data'),('logs','logs'),('run','run'),('transaction.logs.root','transactions')]:
        lines.append('server.directories.'+key+'='+str(home/value))
    (conf/'neo4j.conf').write_text('\n'.join(lines)+'\n')
    env={k:v for k,v in os.environ.items() if k in {'PATH','HOME','LANG','LC_ALL'}}
    env.update(JAVA_HOME=str(root/'toolchain/jre'),NEO4J_HOME=str(distribution),NEO4J_CONF=str(conf))
    child=None;stopping=False
    def stop(signum,frame):
        nonlocal stopping
        stopping=True
        if child and child.poll() is None:
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    initialized=home/'credential-initialized';peak=0
    try:
        available=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
        if available<(448+256)*1024**2:raise RuntimeError('KG startup reserve unavailable')
        # Ask the distribution to assemble its own JVM arguments, then run
        # that JVM directly instead of retaining a second launcher JVM.
        prepared=subprocess.run([str(distribution/'bin/neo4j'),'console','--dry-run'],env=env,
            capture_output=True,text=True,check=True,timeout=30)
        command=shlex.split(prepared.stdout.strip().splitlines()[-1])
        if (not command or Path(command[0]).resolve()!=(root/'toolchain/jre/bin/java').resolve()
                or 'org.neo4j.server.CommunityEntryPoint' not in command):
            raise RuntimeError('Unexpected KG launch command')
        with (control/'kg-console.log').open('ab') as log:
            child=subprocess.Popen(command,env=env,cwd=distribution,stdin=subprocess.DEVNULL,
                stdout=log,stderr=log,start_new_session=True)
        start=time.monotonic();ready=False
        while child.poll() is None and not stopping:
            try:
                rss=process_tree_rss(child.pid);peak=max(peak,rss)
                available=next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
                if rss>448*1024**2 or available<256*1024**2:raise RuntimeError('KG memory reserve reached')
                if not ready:
                    try:
                        with GraphDatabase.driver(connection['uri'],auth=('neo4j',password),connection_timeout=2,max_connection_pool_size=2) as driver:
                            with driver.session(database='neo4j') as session:ready=session.run('RETURN 1 AS ok').single()['ok']==1
                    except Exception:
                        if not initialized.exists():
                            try:
                                with GraphDatabase.driver(connection['uri'],auth=('neo4j','neo4j'),connection_timeout=2,max_connection_pool_size=2) as driver:
                                    with driver.session(database='system') as session:session.run('ALTER CURRENT USER SET PASSWORD FROM $old TO $new',old='neo4j',new=password).consume()
                            except Exception as error:
                                print(json.dumps({'password_initialization_error':type(error).__name__,
                                    'code':getattr(error,'code',None)}),flush=True)
                    if ready:
                        initialized.write_text('initialized\n')
                        print(json.dumps({'kg_ready':True,'uri':connection['uri']}),flush=True)
                    elif time.monotonic()-start>90:raise RuntimeError('KG startup timed out')
                (control/'kg-state.json').write_text(json.dumps({'supervisor_pid':os.getpid(),'java_pid':child.pid,'ready':ready,
                    'uri':connection['uri'],'rss_bytes':rss,'peak_rss_bytes':peak,'checked_at':time.time()}))
                time.sleep(2)
            except FileNotFoundError:break
        if not stopping and child.poll() is not None:raise RuntimeError('KG process exited')
    finally:
        if child and child.poll() is None:
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:child.wait(timeout=15)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
        lock.close()


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'kg_ready':False,'error_type':type(error).__name__}),flush=True)
        raise SystemExit(1)
