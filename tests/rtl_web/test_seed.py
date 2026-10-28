import json
import subprocess
import sys
from pathlib import Path
import pytest
from deployment_fixtures import historical_store


def cli(*args):
    return subprocess.run([sys.executable, '-m', 'zerorepo.rtl_web.cli', *map(str,args)], capture_output=True, text=True)


def config(tmp_path, root):
    import yaml
    path = tmp_path / (root.name + '.yaml')
    path.write_text(yaml.safe_dump({'repo_root': str(Path.cwd()), 'data_root': str(root), 'development': True}))
    return path


def export(tmp_path):
    store, bundles = historical_store(tmp_path / 'source')
    out = tmp_path / 'seed'
    p = cli('export-seed', '--config', config(tmp_path, store.root), '--out', out)
    assert p.returncode == 0, p.stderr
    return store, out


def test_export_reference_closure_and_private_exclusions(tmp_path):
    store, out = export(tmp_path)
    data = json.loads((out/'seed.json').read_text())
    ids = {r['id'] for r in data['records']}
    assert 'e203-v0' in ids
    assert 'private-fixture-run' not in ids
    assert any(r['payload'].get('kind')=='waveform_tile' for r in data['records'])
    assert {r['kind'] for r in data['records']} == {'bundle','run','version','validation','artifact'}
    assert not any(p.name in {'session.key','state.sqlite3'} for p in out.rglob('*'))
    assert len(data['cases']) == 4

def test_archived_supplement_preserves_source_identity_without_importing_a_second_run(tmp_path):
    from zerorepo.rtl_web.recorded_history import SUFFIX
    store,bundles=historical_store(tmp_path/'source')
    b=store.get('bundle',bundles['e203'])
    run={'run_id':'imported-history','source_run_id':'original-source-identity',
         'round_no':1,'origin':'historical','case_id':'e203','modules':[]}
    store.put('run',run['run_id'],run)
    extra={**b,'bundle_id':b['bundle_id']+SUFFIX,'base_bundle_id':b['bundle_id'],
           'debug_history':{'runs':[run]}}
    store.put('bundle',extra['bundle_id'],extra)
    out=tmp_path/'history-seed'
    exported=cli('export-seed','--config',config(tmp_path,store.root),'--out',out)
    assert exported.returncode==0,exported.stderr
    rows=json.loads((out/'seed.json').read_text())['records']
    assert any(r['id']==extra['bundle_id'] for r in rows)
    assert any(r['id']=='imported-history' for r in rows)
    assert not any(r['id']=='original-source-identity' for r in rows)
    assert cli('import-seed','--config',config(tmp_path,tmp_path/'target'),'--source',out,'--dry-run').returncode==0


def test_dry_run_and_import_idempotency_preserves_sessions(tmp_path):
    _, out = export(tmp_path)
    root = tmp_path/'target'
    cfg = config(tmp_path,root)
    p = cli('import-seed','--config',cfg,'--source',out,'--dry-run')
    assert p.returncode==0,p.stderr
    assert not root.exists()
    p = cli('import-seed','--config',cfg,'--source',out)
    assert p.returncode==0,p.stderr
    from zerorepo.rtl_web.store import Store
    s=Store(root); key=s.key; sess=s.create_session('production',{'case_id':'e203'})
    assert cli('import-seed','--config',cfg,'--source',out).returncode==0
    assert Store(root).key==key
    assert s.session(sess['session_id'])['session_id']==sess['session_id']


def test_tampered_file_rejected_without_partial_target(tmp_path):
    _,out=export(tmp_path)
    manifest=json.loads((out/'seed.json').read_text())
    (out/'files'/manifest['files'][0]['path']).write_text('tampered')
    root=tmp_path/'target'
    p=cli('import-seed','--config',config(tmp_path,root),'--source',out)
    assert p.returncode==3
    assert not root.exists()


def test_owner_reference_rejected(tmp_path):
    store,bundles=historical_store(tmp_path/'source')
    b=store.get('bundle',bundles['e203']);b['source_run_id']='private-fixture-run'
    store.put('bundle',b['bundle_id'],b)
    p=cli('export-seed','--config',config(tmp_path,store.root),'--out',tmp_path/'seed')
    assert p.returncode==3


def resign(data):
    import hashlib
    value={k:v for k,v in data.items() if k!='seed_id'}
    data['seed_id']='seed-'+hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


@pytest.mark.parametrize('mutation',['owner','traversal','missing_parent','unknown_record','unreachable'])
def test_forged_seed_rejected(tmp_path,mutation):
    _,out=export(tmp_path)
    data=json.loads((out/'seed.json').read_text())
    if mutation=='owner':data['records'][0]['owner']='private-session'
    if mutation=='traversal':data['files'][0]['path']='../secret'
    if mutation=='missing_parent':
        next(r['payload'] for r in data['records'] if r['kind']=='version')['parent_version_id']='absent-parent'
    if mutation=='unknown_record':data['records'].append({'kind':'message','id':'secret','payload':{}})
    if mutation=='unreachable':data['records'].append({'kind':'run','id':'unrelated','payload':{'run_id':'unrelated','case_id':'e203','origin':'historical'}})
    resign(data);(out/'seed.json').write_text(json.dumps(data))
    root=tmp_path/'target'
    p=cli('import-seed','--config',config(tmp_path,root),'--source',out)
    assert p.returncode==3
    assert not root.exists()


def test_symlink_and_extra_private_files_rejected(tmp_path):
    _,out=export(tmp_path)
    (out/'session.key').write_text('synthetic-private-key')
    assert cli('import-seed','--config',config(tmp_path,tmp_path/'target'),'--source',out).returncode==3
    (out/'session.key').unlink()
    (out/'files'/'link').symlink_to('/etc/passwd')
    assert cli('import-seed','--config',config(tmp_path,tmp_path/'target'),'--source',out).returncode==3


def test_conflict_does_not_overwrite_existing_state(tmp_path):
    _,out=export(tmp_path)
    from zerorepo.rtl_web.store import Store
    root=tmp_path/'target';s=Store(root)
    s.put('run','history-e203',{'run_id':'history-e203','origin':'live'},'production-owner')
    key=s.key;before=s.db.read_bytes()
    assert cli('import-seed','--config',config(tmp_path,root),'--source',out).returncode==3
    assert s.key==key
    with s.connect() as c:
        assert c.execute('SELECT COUNT(*) FROM records').fetchone()[0]==1


def test_private_seed_budget_still_rejects_oversize_before_writing(tmp_path, monkeypatch):
    import zerorepo.rtl_web.seed as seed
    from zerorepo.rtl_web.settings import Settings
    store, _ = historical_store(tmp_path/'source')
    monkeypatch.setattr(seed, 'MAX_SEED_BYTES', 1)
    out = tmp_path/'too-large'
    with pytest.raises(ValueError, match='deployment budget'):
        seed.export_seed(Settings(config(tmp_path, store.root)), out)
    assert not out.exists() and not list(tmp_path.glob('.seed-*'))
