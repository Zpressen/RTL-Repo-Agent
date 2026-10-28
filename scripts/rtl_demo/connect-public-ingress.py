"""Root-reviewed RTL Caddy ingress switch; compatible with Python 3.6.

Install a reviewed copy into a root-owned directory before executing it.
Does not change main/www, model credentials, worker policy or KG ports.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path('/home/dev/rtl-agent-demo')
RELEASE = ROOT / 'releases/ssh-demo-20261016-r1'
STATE = Path('/var/lib/rtl-demo-ingress')
CADDY = Path('/etc/caddy/Caddyfile')
UNIT = Path('/etc/systemd/system/rtl-demo-public.service')


def run(argv):
    subprocess.check_call(argv)


def replace_site(text, domain, block, allow_append=False):
    pattern = r'^' + re.escape(domain) + r'\s*\{'
    matches = list(re.finditer(pattern, text, re.M))
    if not matches and allow_append: return text.rstrip() + '\n\n' + block + '\n'
    if len(matches) != 1: raise ValueError('Exactly one ' + domain + ' site required')
    match = matches[0]
    depth = 1
    end = match.end()
    while depth and end < len(text):
        # Existing handoff site contains no quoted braces; skip comments.
        if text[end] == '#':
            end = text.find('\n', end)
            if end < 0: raise ValueError('Unclosed site')
            continue
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    if depth: raise ValueError('Unclosed site')
    return text[:match.start()] + block + text[end:]


def replace_design(text, domain='design.deepvalleychip.cn'):
    if domain not in {'design.deepvalleychip.cn', 'agent.deepvalleychip.cn'}:
        raise ValueError('Unapproved ingress domain')
    block = domain + ''' {
    request_body {
        max_size 20000
    }
    reverse_proxy 127.0.0.1:18080 {
        header_up -Authorization
        header_up -X-Demo-Gateway-Key
        flush_interval -1
    }
    handle_errors {
        @body_too_large expression `{http.error.message}.contains("HTTP 413: http: request body too large")`
        respond @body_too_large "Request body too large" 413
        respond "{http.error.status_text}" {http.error.status_code}
    }
    encode zstd gzip
    header {
        X-Content-Type-Options nosniff
        Referrer-Policy same-origin
    }
}'''
    if domain == 'design.deepvalleychip.cn':
        return replace_site(text, domain, block)
    # Keep the original design site independent of the Agent workbench.
    original_design = '''design.deepvalleychip.cn {
    root * /srv/deepvalleychip/design
    file_server
    encode zstd gzip
}'''
    updated = replace_site(text, 'design.deepvalleychip.cn', original_design)
    return replace_site(updated, domain, block, allow_append=True)


def install_bytes(path, data, mode=0o644):
    fd, name = tempfile.mkstemp(prefix='.rtl-ingress-', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.chmod(name, mode)
        os.replace(name, str(path))
    finally:
        if os.path.exists(name): os.unlink(name)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'activate', 'rollback'])
    parser.add_argument('--domain', choices=['design.deepvalleychip.cn','agent.deepvalleychip.cn'], default='agent.deepvalleychip.cn')
    args = parser.parse_args()
    if os.geteuid() != 0: raise ValueError('Maintainer root privileges required')
    if Path(__file__).stat().st_uid != 0: raise ValueError('Run a sealed root-owned copy')
    STATE.mkdir(mode=0o700, exist_ok=True)
    if STATE.is_symlink() or STATE.stat().st_uid != 0: raise ValueError('Unsafe state directory')
    if args.action == 'prepare':
        unit = '''[Unit]
Description=Deep Valley Chip public RTL gateway (loopback)
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=dev
Group=dev
WorkingDirectory={release}
Environment=HOME=/home/dev
ExecStart={root}/toolchain/python/bin/python3.13 {release}/scripts/rtl_demo/user-supervisor.py --root {root}
Restart=always
RestartSec=3
KillMode=control-group
TimeoutStopSec=20
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
MemoryAccounting=true
MemoryMax=256M
MemoryLimit=256M
CPUAccounting=true
CPUQuota=100%
TasksMax=128

[Install]
WantedBy=multi-user.target
'''.format(root=ROOT, release=RELEASE)
        if UNIT.exists() and UNIT.read_text() != unit:
            old = UNIT.read_text()
            expected = next(line for line in unit.splitlines() if line.startswith('ExecStart='))
            if not old.startswith('[Unit]\nDescription=Deep Valley Chip public RTL gateway (loopback)\n') or expected not in old.splitlines():
                raise ValueError('Existing unit differs; review first')
            (STATE / ('service.before-' + str(int(time.time())))).write_text(old)
        install_bytes(UNIT, unit.encode())
        run(['systemctl', 'daemon-reload'])
        print(json.dumps({'prepared': True, 'service': UNIT.name}))
        return
    state_file = STATE / 'state.json'
    if args.action == 'rollback':
        previous = json.loads(state_file.read_text())
        install_bytes(CADDY, Path(previous['backup']).read_bytes())
        run(['caddy', 'validate', '--config', str(CADDY), '--adapter', 'caddyfile'])
        run(['systemctl', 'reload', 'caddy'])
        print(json.dumps({'rolled_back': True}))
        return
    deadline = time.monotonic() + 20
    while True:
        try:
            with urllib.request.urlopen('http://127.0.0.1:18080/api/health', timeout=3) as response:
                health = json.load(response)
            break
        except OSError:
            if time.monotonic() >= deadline: raise
            time.sleep(0.5)
    if health.get('phase') != 'production' or not health['capabilities']['chat']['available']:
        raise ValueError('HTTPS-configured live backend with chat required')
    original = CADDY.read_bytes()
    candidate = replace_design(original.decode(), args.domain).encode()
    backup = STATE / ('Caddyfile.before-' + str(int(time.time())))
    backup.write_bytes(original)
    backup.chmod(0o600)
    staged = STATE / 'Caddyfile.candidate'
    staged.write_bytes(candidate)
    run(['caddy', 'validate', '--config', str(staged), '--adapter', 'caddyfile'])
    try:
        install_bytes(CADDY, candidate)
        run(['caddy', 'validate', '--config', str(CADDY), '--adapter', 'caddyfile'])
        run(['systemctl', 'reload', 'caddy'])
    except BaseException:
        install_bytes(CADDY, original)
        run(['systemctl', 'reload', 'caddy'])
        raise
    previous = json.loads(state_file.read_text()) if state_file.exists() else {}
    state = {'backup': previous.get('backup', str(backup)), 'activated_at': time.time(),
             'before_sha256': hashlib.sha256(original).hexdigest(),
             'after_sha256': hashlib.sha256(candidate).hexdigest(),
             'upstream': '127.0.0.1:18080', 'domain': args.domain}
    state_file.write_text(json.dumps(state, indent=2))
    state_file.chmod(0o600)
    print(json.dumps(state))


if __name__ == '__main__': main()
