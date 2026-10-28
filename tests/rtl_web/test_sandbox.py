from pathlib import Path
import importlib.util
import pytest


def sandbox():
    import zerorepo.rtl_web.sandbox as m
    return m


def test_mount_plan_never_exposes_host_root_or_shared_state(tmp_path,settings):
    m=sandbox();root=settings.data/'jobs/run-test';root.mkdir(parents=True)
    (root/'job_inputs').mkdir();job=root/'job.json';job.write_text('{}')
    command=m.job_command(settings,job,['/usr/bin/true'])
    assert '--unshare-pid' in command and '--unshare-user' in command
    assert ['--ro-bind','/','/'] not in [command[i:i+3] for i in range(len(command)-2)]
    assert str(settings.data) not in command
    assert str(root) in command
    assert command.count(str(root/'job_inputs'))==2


def test_gateway_secrets_not_in_tool_environment(settings):
    m=sandbox()
    env=m.minimal_environment({'PATH':'/usr/bin','ZEROREPO_API_KEY':'fixture-model-key',
        'RTL_DEMO_GATEWAY_KEY':'fixture-gateway','UNRELATED_SECRET':'other'})
    assert env['ZEROREPO_API_KEY']=='fixture-model-key'
    assert 'RTL_DEMO_GATEWAY_KEY' not in env and 'UNRELATED_SECRET' not in env


def test_real_namespace_denies_other_state_and_input_writes(settings,tmp_path):
    import subprocess,sys
    from zerorepo.rtl_web.store import Store
    m=sandbox()
    if not m.native_probe():pytest.skip('Native namespace unavailable; deployment acceptance remains unpassed')
    Store(settings.data)
    other=settings.data/'runs/other';other.mkdir(parents=True);(other/'secret').write_text('other-session')
    root=settings.data/'jobs/run-native';inputs=root/'job_inputs';inputs.mkdir(parents=True)
    (inputs/'spec').write_text('immutable');job=root/'job.json';job.write_text('{}')
    script='''from pathlib import Path
assert not Path(SHARED).exists()
assert not Path(OTHER).exists()
try:
    Path(SPEC).write_text('changed')
except OSError:
    pass
else:
    raise AssertionError('Input was writable')
Path(OUTPUT).write_text('ok')
'''.replace('SHARED',repr(str(settings.data/'session.key'))).replace('OTHER',repr(str(other/'secret'))).replace('SPEC',repr(str(inputs/'spec'))).replace('OUTPUT',repr(str(root/'result')))
    command=m.job_command(settings,job,[settings.python,'-c',script])
    p=subprocess.run(command,capture_output=True,text=True,timeout=15,env=m.minimal_environment(settings.tool_env()))
    assert p.returncode==0,p.stderr
    assert (root/'result').read_text()=='ok'
    assert (inputs/'spec').read_text()=='immutable'


def test_selected_native_cli_is_mounted_without_personal_codex_state(settings,tmp_path):
    import json
    m=sandbox();root=settings.data/'jobs/run-native-cli';root.mkdir(parents=True)
    (root/'job_inputs').mkdir();binary=tmp_path/'personal-codex/tool/codex';binary.parent.mkdir(parents=True);binary.write_text('native-fixture')
    job=root/'job.json';job.write_text(json.dumps({'inputs':{'backend_cli':str(binary)}}))
    args=m.job_command(settings,job,['/usr/bin/true'])
    assert str(binary) in args
    assert str(binary.parent) not in args
    assert str(binary.parents[1]) not in args
