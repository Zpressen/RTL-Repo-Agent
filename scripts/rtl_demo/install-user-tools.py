"""Install reviewed native tools into an ordinary user's private directory.

Archives must already match toolchain.lock.json; RPM payloads must be signed
by keys trusted by the target's RPM database. No RPM scripts are executed.
Run with the independently installed Python 3.13, never system Python 3.6.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import resource
import shlex
import shutil
import subprocess
import tarfile
import tempfile


def run(argv, **kwargs):
    return subprocess.run(list(map(str, argv)), check=True, **kwargs)


def wrapper(path, body):
    path.write_text('#!/bin/sh\nset -eu\n'+body+'\n')
    path.chmod(0o700)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--lock',type=Path,required=True)
    args=parser.parse_args()
    root=args.root.resolve();tools=root/'toolchain';downloads=root/'downloads'
    lock=json.loads(args.lock.read_text());tools.mkdir(mode=0o700,exist_ok=True)
    if root.stat().st_uid!=os.getuid():raise ValueError('User-owned root required')
    with tarfile.open(downloads/'rtl-demo-execution-tools.tar') as archive:
        archive.extractall(downloads,filter='data')
    artifacts=[]
    for item in lock['artifacts']:
        if item['name'] not in {'verilator','jre','neo4j','codex'}:continue
        source=downloads/(item['name']+'-'+item['version']+'.archive')
        if hashlib.sha256(source.read_bytes()).hexdigest()!=item['sha256']:
            raise ValueError('Archive digest mismatch')
        target=tools/(item['name']+'-source' if item['name']=='verilator' else item['name'])
        marker=target/'.artifact-sha256'
        if not target.exists():
            temporary=Path(tempfile.mkdtemp(prefix='.unpack-',dir=tools))
            with tarfile.open(source) as archive:archive.extractall(temporary,filter='data')
            children=list(temporary.iterdir())
            if len(children)==1 and children[0].is_dir():
                children[0].rename(target);temporary.rmdir()
            else:temporary.rename(target)
            marker.write_text(item['sha256'])
        if marker.read_text()!=item['sha256']:raise ValueError('Existing tool differs')
        artifacts.append({'name':item['name'],'sha256':item['sha256']})
    rpmroot=tools/'rpm-root';rpmroot.mkdir(mode=0o700,exist_ok=True)
    rpms=[]
    for rpm in sorted((downloads/'rpms').glob('*.rpm')):
        verified=run(['rpm','--checksig',rpm],capture_output=True,text=True)
        if 'NOKEY' in verified.stdout or 'NOT OK' in verified.stdout:raise ValueError('Untrusted RPM')
        package=run(['rpm','-qp','--qf','%{NAME} %{VERSION}-%{RELEASE}',rpm],capture_output=True,text=True).stdout.strip()
        name,version=package.split()
        pinned=lock['system_packages'].get(name)
        if name=='libstdc++-devel':pinned=lock['system_packages']['gcc-c++']
        if name=='cpp':pinned=lock['system_packages']['gcc']
        if name=='git-core':pinned=lock['system_packages']['git']
        if pinned!=version:raise ValueError('Unreviewed RPM version: '+name)
        # Do not run a package's installation scripts or update the RPM database.
        conversion=subprocess.Popen(['rpm2cpio',str(rpm)],stdout=subprocess.PIPE)
        try:run(['cpio','-idm','--quiet','--no-absolute-filenames'],cwd=rpmroot,stdin=conversion.stdout)
        finally:conversion.stdout.close()
        if conversion.wait():raise ValueError('RPM payload conversion failed')
        rpms.append({'package':package,'sha256':hashlib.sha256(rpm.read_bytes()).hexdigest()})
    bins=tools/'bin';bins.mkdir(mode=0o700,exist_ok=True)
    for name in ['ld','as','ar','ranlib']:
        binary=shutil.which(name,path='/usr/bin:/bin')
        if not binary:raise ValueError('System binutils missing: '+name)
        native=Path(binary).resolve(strict=True);link=bins/name
        if link.exists() or link.is_symlink():link.unlink()
        link.symlink_to(native)
    cpp=rpmroot/'usr/libexec/gcc/x86_64-redhat-linux/10'
    includes=rpmroot/'usr/include/c++/10'
    q=lambda p:shlex.quote(str(p))
    system_plugin=Path(run(['gcc','-print-file-name=liblto_plugin.so'],capture_output=True,text=True).stdout.strip())
    if (cpp/'liblto_plugin.so').is_file():system_plugin=cpp/'liblto_plugin.so'
    system_libgcc=Path(run(['gcc','-print-libgcc-file-name'],capture_output=True,text=True).stdout.strip())
    if not system_plugin.is_file() or not system_libgcc.is_file():raise ValueError('System GCC runtime missing')
    runtime=rpmroot/'usr/lib64/libstdc++.so.6'
    if not runtime.exists():runtime.symlink_to('/usr/lib64/libstdc++.so.6')
    cxx_link=rpmroot/'usr/lib/gcc/x86_64-redhat-linux/10/libstdc++.so'
    if cxx_link.is_symlink() and not cxx_link.exists():
        cxx_link.unlink();cxx_link.symlink_to('/usr/lib64/libstdc++.so.6')
    zlib=rpmroot/'usr/lib64/libz.so'
    if zlib.is_symlink() and not zlib.exists():zlib.unlink();zlib.symlink_to('/lib64/libz.so.1')
    wrapper(bins/'gcc','exec '+q(rpmroot/'usr/bin/gcc')+' -B'+q(bins)+' -B'+q(cpp)+' -B'+q(system_libgcc.parent)+' "$@"')
    wrapper(bins/'cc','exec '+q(bins/'gcc')+' "$@"')
    wrapper(bins/'g++','exec '+q(rpmroot/'usr/bin/g++')+' -B'+q(bins)+' -B'+q(cpp)+' -B'+q(rpmroot/'usr/lib/gcc/x86_64-redhat-linux/10')+
        ' -B'+q(system_plugin.parent)+' -B'+q(system_libgcc.parent)+
        ' -isystem '+q(includes)+' -isystem '+q(includes/'x86_64-redhat-linux')+' -isystem '+q(includes/'backward')+' "$@"')
    wrapper(bins/'bison','export BISON_PKGDATADIR='+q(rpmroot/'usr/share/bison')+'\nexec '+q(rpmroot/'usr/bin/bison')+' "$@"')
    wrapper(bins/'flex','exec '+q(rpmroot/'usr/bin/flex')+' "$@"')
    wrapper(bins/'git','export GIT_EXEC_PATH='+q(rpmroot/'usr/libexec/git-core')+'\nexec '+q(rpmroot/'usr/bin/git')+' "$@"')
    codex=bins/'codex'
    if codex.exists() or codex.is_symlink():codex.unlink()
    codex.symlink_to(tools/'codex/codex-x86_64-unknown-linux-musl')
    env={**os.environ,'PATH':str(bins)+':/usr/bin:/bin',
        'CPPFLAGS':'-I'+str(rpmroot/'usr/include'),'LDFLAGS':'-L'+str(rpmroot/'usr/lib64'),
        'CXXFLAGS':'-O0 -g0','CFLAGS':'-O1 -g0'}
    if not (bins/'verilator_bin').exists():
        source=tools/'verilator-source'
        run(['autoconf'],cwd=source,env=env)
        run(['./configure','--prefix='+str(tools),'--disable-partial-static'],cwd=source,env=env)
        # The default also builds a large developer/debug binary. Runtime
        # verification needs only the normal binary. Record this build choice.
        def build_limit():
            resource.setrlimit(resource.RLIMIT_AS,(768*1024**2,768*1024**2))
            resource.setrlimit(resource.RLIMIT_CORE,(0,0));os.nice(10)
        run(['make','-C','src','-j1','opt','VL_NOOPT=1'],cwd=source,env=env,preexec_fn=build_limit,timeout=1800)
    # Runtime deployment excludes generated manual pages and their extra
    # documentation-only build dependencies.
    run(['make','installbin','installredirect','installdata','VL_INST_PUBLIC_BIN_FILES=verilator_bin'],
        cwd=tools/'verilator-source',env=env,timeout=120)
    report={'artifacts':artifacts,'rpms':rpms,'system_package_install':False,
        'verilator_build':{'optimization':'-O0','variant':'normal binary only','parallel_jobs':1,'address_space_limit_bytes':768*1024**2},
        'versions':{name:run([bins/name,'--version'],capture_output=True,text=True,env=env).stdout.splitlines()[0]
                    for name in ['g++','verilator','codex','git']}}
    output=root/'control/native-tools-install.json';output.write_text(json.dumps(report,indent=2));output.chmod(0o600)
    print(json.dumps({'installed':True,'versions':report['versions']}),flush=True)


if __name__=='__main__':main()
