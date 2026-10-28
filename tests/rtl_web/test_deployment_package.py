import importlib.util
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]


def module():
    path=ROOT/'scripts/rtl_demo/deployment.py'
    assert path.is_file(), 'The deployment command with a stdlib check is missing'
    spec=importlib.util.spec_from_file_location('deployment',path)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def test_unsafe_paths_and_secrets_are_rejected(tmp_path):
    m=module()
    for name in ['../secret','/etc/passwd','a/../b','a\\b']:
        with pytest.raises(ValueError): m.relative_path(name)
    with pytest.raises(ValueError): m.check_public_bytes(b'api_key: sk-THIS_IS_A_SYNTHETIC_SECRET_123456789')
    m.check_public_bytes(b'api_key: ${ZEROREPO_API_KEY}\n')


def test_links_rejected(tmp_path):
    m=module()
    (tmp_path/'link').symlink_to('/etc/passwd')
    with pytest.raises(ValueError): m.inventory(tmp_path,'runtime')


@pytest.fixture
def complete_package(tmp_path):
    import json
    m=module();root=tmp_path/'release';root.mkdir()
    for package in m.PACKAGES:(root/package).mkdir()
    for cid in m.CASE_IDS:
        public=root/'design/cases'/cid/'manifest.json';public.parent.mkdir(parents=True)
        public.write_text(json.dumps({'bundle_id':'bundle-'+cid}))
    specs={
        'e203':'rtl_dataset/e203_exu_alu_hard/e203_exu_alu_system.md',
        'aes_cipher_system_hard':'rtl_dataset/aes_cipher_hard/aes_cipher_system_hard.md',
        'aes_inv_cipher_top_system':'rtl_dataset/aes_inv_cipher_system/aes_inv_cipher_top_system.md',
        'sdc_controller_system':'rtl_dataset/sdc_controller_hard/sdc_controller_system.md'}
    for name in specs.values():
        p=root/'runtime'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('Task specification\n')
    for name in ['zerorepo/rtl_web/cli.py','zerorepo/rtl_web/runtime.py']:
        p=root/'runtime'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('# trusted runtime\n')
    for _,verifier in m.CASE_FILES.values():
        p=root/'verifier'/verifier;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('# trusted verifier\n')
    seed={'seed_id':'seed-fixture','cases':{cid:'bundle-'+cid for cid in m.CASE_IDS}}
    (root/'seed/seed.json').write_text(json.dumps(seed))
    (root/'ops/requirements-web-prod.txt').write_text('# fixture lock\n')
    (root/'ops/requirements-agent-demo.txt').write_text('# fixture lock\n')
    p=root/'ops/deploy/rtl_demo/toolchain.lock.json';p.parent.mkdir(parents=True);p.write_text('{}')
    manifest={'schema_version':'rtl-demo-deploy-v1','release_id':'r1','cases':{
        cid:{'bundle_id':'bundle-'+cid,'spec_sha256':m.digest(root/'runtime'/spec),'seed_id':'seed-fixture'} for cid,spec in specs.items()},
        'files':sum([m.inventory(root/package,package) for package in sorted(m.PACKAGES)],[]),
        'lock_hashes':{name:m.digest(root/'ops'/name) for name in ['requirements-web-prod.txt','requirements-agent-demo.txt','deploy/rtl_demo/toolchain.lock.json']}}
    (root/'deployment.json').write_text(json.dumps(manifest));return root


def test_check_is_stdlib_only_without_git_or_repository_imports(complete_package):
    import subprocess,sys
    r=subprocess.run([sys.executable,'-S',str(ROOT/'scripts/rtl_demo/deployment.py'),'check','--release',str(complete_package)],
                     cwd=complete_package,env={'PATH':'/no-tools','PYTHONPATH':''},capture_output=True,text=True)
    assert r.returncode==0,r.stderr


@pytest.mark.parametrize('mutation',['spec_missing','seed_bundle','file_hash','file_size','private_design','missing_case','missing_lock'])
def test_complete_package_rejects_corruption(complete_package,mutation):
    import json
    m=module();root=complete_package;manifest=json.loads((root/'deployment.json').read_text())
    if mutation=='spec_missing':
        p=root/'runtime/rtl_dataset/e203_exu_alu_hard/e203_exu_alu_system.md';p.unlink()
        manifest['files']=[e for e in manifest['files'] if e['target_relative_path']!=p.relative_to(root/'runtime').as_posix()]
    elif mutation=='seed_bundle':
        p=root/'seed/seed.json';seed=json.loads(p.read_text());seed['cases']['e203']='wrong';p.write_text(json.dumps(seed))
        manifest['files']=[e for e in manifest['files'] if e['package']!='seed']+m.inventory(root/'seed','seed')
    elif mutation in {'file_hash','file_size'}:
        manifest['files'][0]['sha256' if mutation=='file_hash' else 'size_bytes']='0'*64 if mutation=='file_hash' else 0
    elif mutation=='private_design':
        p=root/'design/reference.v';p.write_text('module reference; endmodule')
    elif mutation=='missing_case':del manifest['cases']['e203']
    else:manifest['lock_hashes'].pop('requirements-web-prod.txt')
    (root/'deployment.json').write_text(json.dumps(manifest))
    with pytest.raises(ValueError):m.checked(root)


def test_special_files_and_hardlinks_rejected(tmp_path):
    import os
    m=module();os.mkfifo(tmp_path/'pipe')
    with pytest.raises(ValueError):m.inventory(tmp_path,'runtime')
    (tmp_path/'pipe').unlink();(tmp_path/'one.py').write_text('x=1\n');os.link(tmp_path/'one.py',tmp_path/'two.py')
    with pytest.raises(ValueError):m.inventory(tmp_path,'runtime')


def test_secret_values_in_inline_structures_are_not_publishable():
    m=module()
    for suffix,body in [('.json',b'{"unrelated": 1, "password": "synthetic-secret-for-test"}'),
                        ('.py',b'config={"api_key": "synthetic-secret-for-test"}\n')]:
        with pytest.raises(ValueError):m.check_public_bytes(body,suffix)


def test_actual_environment_files_are_excluded_even_without_key_prefix(tmp_path):
    m=module();(tmp_path/'runtime.env').write_text('MODEL_KEY=synthetic-private-value')
    with pytest.raises(ValueError):m.inventory(tmp_path,'ops')
