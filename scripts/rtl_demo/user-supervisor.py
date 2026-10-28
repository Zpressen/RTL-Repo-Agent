"""Owns only the selected loopback Demo component and restarts its child."""
from pathlib import Path
import argparse
import fcntl
import json
import os
import signal
import subprocess
import time


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,required=True)
    p.add_argument('--component',choices=['gateway','worker'],default='gateway');args=p.parse_args()
    component=args.component;prefix='' if component=='gateway' else 'worker-'
    root=args.root.resolve();control=root/'control';control.mkdir(mode=0o700,exist_ok=True)
    lock=(control/(prefix+'supervisor.lock')).open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:return
    environment=json.loads((root/'private/environment.json').read_text())
    env={'PATH':'/usr/bin:/bin','HOME':str(Path.home()),'LANG':'C.UTF-8',**environment}
    release=Path(json.loads((root/'private/launch.json').read_text())['release'])
    env['PYTHONPATH']=str(release)
    for key in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:env[key]='1'
    command=[str(release/'.venv-web/bin/python'),'-m','zerorepo.rtl_web.tunnel_gateway',
             '--config',str(root/'private/config.yaml'),'--design',str(release/'design'),
             '--auth',str(root/'private/auth.json'),'--port','18080']
    if component=='worker':
        command=[str(release/'.venv-web/bin/python'),'-m','zerorepo.rtl_web.worker','--config',str(root/'private/config.yaml')]
    stopping=False;child=None
    def stop(signum,frame):
        nonlocal stopping
        stopping=True
        if child and child.poll() is None:
            try:os.killpg(child.pid,signal.SIGTERM)
            except ProcessLookupError:pass
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    (control/(prefix+'supervisor.json')).write_text(json.dumps({'pid':os.getpid(),'started_at':time.time(),'release':str(release),'mode':'loopback_service_not_accepted','component':component}))
    try:
        while not stopping:
            with (control/(component+'.log')).open('ab') as out:
                child=subprocess.Popen(command,env=env,cwd=release,stdin=subprocess.DEVNULL,stdout=out,stderr=out,start_new_session=True)
                (control/(component+'.json')).write_text(json.dumps({'pid':child.pid,'started_at':time.time(),'release':str(release)}))
                while child.poll() is None:
                    if stopping:
                        try:child.wait(timeout=12)
                        except subprocess.TimeoutExpired:
                            try:os.killpg(child.pid,signal.SIGKILL)
                            except ProcessLookupError:pass
                        break
                    time.sleep(0.5)
                (control/(component+'-exit.json')).write_text(json.dumps({'pid':child.pid,'returncode':child.poll(),'stopping':stopping,'checked_at':time.time()}))
            if not stopping:time.sleep(3)
    finally:
        if child and child.poll() is None:
            try:os.killpg(child.pid,signal.SIGKILL)
            except ProcessLookupError:pass
        lock.close()


if __name__=='__main__':main()
