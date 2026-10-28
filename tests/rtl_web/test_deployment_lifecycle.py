import importlib.util
import json
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]


def module():
    spec=importlib.util.spec_from_file_location('deployment_lifecycle',ROOT/'scripts/rtl_demo/deployment.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    return m


def test_accept_requires_every_bound_criterion(tmp_path):
    m=module()
    evidence={'release_id':'r1','host':'39.107.243.176','origin':'https://design.deepvalleychip.cn','criteria':[]}
    with pytest.raises(ValueError):m.validate_acceptance(evidence,'r1',tmp_path)


def test_recovery_backup_captures_wal_consistently(tmp_path):
    from zerorepo.rtl_web.store import Store
    import sqlite3
    s=Store(tmp_path/'state');s.create_session('production',{})
    m=module();target=tmp_path/'backup.sqlite3'
    m.backup_database(s.db,target)
    with sqlite3.connect(target) as c:assert c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]==1
    assert s.key_path.read_bytes()==s.key


def test_status_is_read_only(tmp_path):
    m=module();missing=tmp_path/'not-created'
    result=m.release_status('r1',missing)
    assert result['state']=='not_prepared'
    assert not missing.exists()


def layout(m,tmp):
    return m.Layout(root=tmp/'opt',config=tmp/'etc-demo',data=tmp/'data',static=tmp/'srv',caddy=tmp/'caddy',units=tmp/'units')


def test_design_merge_preserves_unrelated_sites_and_environment_placeholders():
    m=module()
    old='(common) {\n header X-Test "literal { value }"\n}\nmain.example {\n import common\n}\ndesign.deepvalleychip.cn {\n root * /old\n # ignored }\n}\nother.example {\n reverse_proxy {$CAD_HOST}\n}\n'
    new='design.deepvalleychip.cn {\n reverse_proxy {$RTL_DEMO_UPSTREAM}\n}\n'
    actual=m.merge_design(old,new)
    assert actual.startswith(old[:old.index('design.deepvalleychip.cn')])
    assert actual.endswith(old[old.index('\nother.example'):])
    assert '/old' not in actual
    with pytest.raises(ValueError):m.merge_design('main.example { root * /x }',new)


def test_acceptance_binds_each_file_and_rejects_replacement(tmp_path):
    m=module();criteria=[]
    for i in range(1,13):
        name=f'SC-{i:03}';p=tmp_path/(name+'.json')
        p.write_text(json.dumps({'release_id':'r1','host':'39.107.243.176','origin':'https://design.deepvalleychip.cn','criterion':name,'status':'passed'}))
        criteria.append({'criterion':name,'status':'passed','evidence':[{'path':p.name,'size_bytes':p.stat().st_size,'sha256':m.digest(p)}]})
    index={'release_id':'r1','host':'39.107.243.176','origin':'https://design.deepvalleychip.cn','criteria':criteria}
    assert m.validate_acceptance(index,'r1',tmp_path)
    with pytest.raises(ValueError):m.validate_acceptance(index,'r2',tmp_path)
    (tmp_path/'SC-001.json').write_text('{}')
    with pytest.raises(ValueError):m.validate_acceptance(index,'r1',tmp_path)


def test_rollback_preserves_new_production_messages_and_key(tmp_path,monkeypatch):
    from zerorepo.rtl_web.store import Store
    m=module();paths=layout(m,tmp_path);paths.records.mkdir(parents=True)
    store=Store(paths.data);store.create_session('before',{})
    key=store.key_path.read_bytes()
    m.backup_database(store.db,paths.records/'snapshot.sqlite3')
    store.create_session('after-upgrade',{})
    recovery_root=paths.records/'recovery'/'recovery-test';recovery_root.mkdir(parents=True)
    design=recovery_root/'design';design.mkdir();(design/'index.html').write_text('old page')
    (paths.static/'design/assets').mkdir(parents=True)
    (paths.static/'design/assets/new-hash.js').write_text('new asset')
    data={'recovery_id':'recovery-test','previous_code':None,'files':[],'services':{}}
    m._restore(data,paths,commands=False)
    import sqlite3
    with sqlite3.connect(store.db) as c:assert c.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]==2
    assert store.key_path.read_bytes()==key
    assert (paths.static/'design/index.html').read_text()=='old page'
    assert (paths.static/'design/assets/new-hash.js').is_file()
    assert not store.control('maintenance')


def test_activate_validation_failure_restores_previous_entry(tmp_path,monkeypatch):
    m=module();paths=layout(m,tmp_path);paths.records.mkdir(parents=True)
    source=paths.root/'candidates/r2';source.mkdir(parents=True);(source/'deployment.json').write_text('{}')
    old=paths.root/'releases/r1';old.mkdir(parents=True);(paths.root/'current').symlink_to(old)
    m.save_record(paths,{'release_id':'r2','state':'prepared','candidate':str(source),'manifest_sha256':m.digest(source/'deployment.json'),'config':'unused'})
    monkeypatch.setattr(m,'checked',lambda p:{'release_id':'r2'})
    monkeypatch.setattr(m,'privileged',lambda:None);monkeypatch.setattr(m,'sealed',lambda p:p)
    recovery={'recovery_id':'recovery-test','previous_code':str(old),'services':{},'files':[]}
    monkeypatch.setattr(m,'capture_recovery',lambda *a:recovery)
    monkeypatch.setattr(m,'host_command',lambda *a,**k:json.dumps({'ready':True}))
    monkeypatch.setattr(m,'stop_backend',lambda:None)
    restored=[]
    monkeypatch.setattr(m,'_restore',lambda r,p:restored.append(r))
    # A missing prepared config fails before any public static/Caddy mutation.
    with pytest.raises(m.DeploymentError) as err:m.activate('r2',layout=paths)
    assert err.value.code==6 and restored==[recovery]
    assert m.release_status('r2',paths.records)['state']=='failed'
    assert (paths.root/'current').resolve()==old


def test_dry_run_activation_does_not_create_or_write_state(tmp_path,monkeypatch):
    m=module();paths=layout(m,tmp_path);paths.records.mkdir(parents=True)
    source=tmp_path/'source';source.mkdir();(source/'deployment.json').write_text('{}')
    m.save_record(paths,{'release_id':'r2','state':'prepared','candidate':str(source),'manifest_sha256':m.digest(source/'deployment.json')})
    monkeypatch.setattr(m,'checked',lambda p:{'release_id':'r2'})
    before={p.relative_to(tmp_path).as_posix():p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert m.activate('r2',dry_run=True,layout=paths)['dry_run']
    after={p.relative_to(tmp_path).as_posix():p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert before==after and not paths.data.exists()


def test_capacity_failure_never_stops_running_business(tmp_path,monkeypatch):
    m=module();paths=layout(m,tmp_path);paths.records.mkdir(parents=True)
    source=paths.root/'candidates/r2';source.mkdir(parents=True);(source/'deployment.json').write_text('{}')
    m.save_record(paths,{'release_id':'r2','state':'prepared','candidate':str(source),'manifest_sha256':m.digest(source/'deployment.json'),'config':'unused'})
    monkeypatch.setattr(m,'checked',lambda p:{'release_id':'r2'})
    monkeypatch.setattr(m,'privileged',lambda:None);monkeypatch.setattr(m,'sealed',lambda p:p)
    monkeypatch.setattr(m,'host_command',lambda *a,**k:json.dumps({'ready':False}))
    stopped=[];monkeypatch.setattr(m,'stop_backend',lambda:stopped.append(True))
    with pytest.raises(m.DeploymentError) as err:m.activate('r2',layout=paths)
    assert err.value.code==4 and not stopped
    assert not paths.data.exists()
    assert m.release_status('r2',paths.records)['state']=='prepared'
