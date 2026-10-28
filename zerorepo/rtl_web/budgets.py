"""Admission and measured resource checks; never mutate evidence to make room."""
from pathlib import Path
import os
import shutil
from .schemas import DemoError


def disk_admission(root: Path, *, min_free_bytes: int):
    root=Path(root)
    while not root.exists():root=root.parent
    free=shutil.disk_usage(root).free
    if free<min_free_bytes:raise DemoError('resource_unavailable','磁盘空间不足，暂不能启动任务。',503)
    return free


def job_usage(root: Path, max_bytes: int):
    size=0
    for p in Path(root).rglob('*'):
        if p.is_symlink():raise DemoError('unsafe_job','任务出现不安全链接。',409)
        if p.is_file():
            size+=p.stat().st_size
            if size>max_bytes:raise DemoError('resource_limit','任务达到存储预算，已中断并保留产物。',503)
    return size


def host_memory():
    values={line.split(':',1)[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()}
    return {'total':values['MemTotal'],'available':values['MemAvailable']}


def bounded_chat_memory_ready():
    # The API is already resident. Admit one SDK child plus the host reserve;
    # do not count the API and an unrelated native worker a second time.
    return host_memory()['available']>=(384+256)*1024**2


def production_checks(settings):
    b=settings.budgets
    memory=host_memory()
    baseline=int(b.get('existing_services_bytes',memory['total']-memory['available']))
    limits=sum(int(b.get(key,0)) for key in ['worker_memory_bytes','api_memory_bytes','kg_memory_bytes','host_reserve_bytes'])
    checks={'memory_budget':bool(limits and limits+baseline<=memory['total'])}
    try:disk_admission(settings.data,min_free_bytes=int(b.get('min_free_bytes',5*1024**3)));checks['disk_space']=True
    except (OSError,DemoError):checks['disk_space']=False
    # A root-generated descriptor names the actual cgroup files and job mount.
    # Read effective kernel values, never trust a boolean in YAML.
    resource=Path(settings.raw.get('resource_boundary','/etc/rtl-demo/resource-boundary.json'))
    try:
        import json
        d=json.loads(resource.read_text());job_root=settings.data/'jobs'
        checks['job_volume']=job_root.is_mount() and shutil.disk_usage(job_root).total<=int(b.get('jobs_max_bytes',8*1024**3))
        control=Path(d['memory_limit_file']).resolve()
        if not control.is_relative_to('/sys/fs/cgroup'):raise ValueError('Invalid controller path')
        limit=control.read_text().strip()
        checks['cgroup_memory']=limit.isdigit() and 0<int(limit)<=int(b['worker_memory_bytes'])
        cpu=Path(d['cpu_limit_file']).resolve()
        tasks=Path(d['tasks_limit_file']).resolve()
        if not all(p.is_relative_to('/sys/fs/cgroup') for p in [cpu,tasks]):raise ValueError('Invalid controller path')
        fields=cpu.read_text().strip().split()
        if cpu.name=='cpu.max':
            checks['cgroup_cpu']=(len(fields)==2 and all(x.isdigit() for x in fields) and 0<int(fields[0])<=int(fields[1]))
        else:
            period=int(cpu.with_name('cpu.cfs_period_us').read_text())
            checks['cgroup_cpu']=len(fields)==1 and fields[0].isdigit() and 0<int(fields[0])<=period
        checks['cgroup_tasks']=tasks.read_text().strip().isdigit() and int(tasks.read_text())<=128
        worker=json.loads((settings.data/'worker-state.json').read_text())
        from .worker import process_start
        if process_start(int(worker['pid']))!=worker.get('start'):raise ValueError('Worker PID changed')
        membership=Path(f"/proc/{int(worker['pid'])}/cgroup").read_text()
        if '/rtl-demo-worker.slice/' not in membership:raise ValueError('Worker is outside resource slice')
    except (OSError,ValueError,KeyError):
        for key in ['job_volume','cgroup_memory','cgroup_cpu','cgroup_tasks']:checks[key]=False
    return checks
