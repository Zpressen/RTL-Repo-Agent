import hashlib,json,zipfile
import pytest
from evidence_fixtures import example_bundle
from zerorepo.rtl_web.schemas import DemoError
from zerorepo.rtl_web.evidence import build_package

def test_exact_complete_deterministic_public_package(settings,ledger,tmp_path):
    b=example_bundle(settings,ledger)
    a=tmp_path/'a.zip';z=tmp_path/'b.zip'
    build_package(settings,ledger,'e203','fixture-check2','fixture-check1',a)
    build_package(settings,ledger,'e203','fixture-check2','fixture-check1',z)
    assert a.read_bytes()==z.read_bytes()
    with zipfile.ZipFile(a) as arc:
        m=json.loads(arc.read('manifest.json'))
        assert len(m['versions'])==2
        assert sum(n.endswith('/defines.v') for n in arc.namelist())==2
        assert all(not n.endswith('.vcd') for n in arc.namelist())
        assert 'raw_vcd_not_public' in m['exclusions']
        for f in m['files']:
            data=arc.read(f['archive_path']);assert hashlib.sha256(data).hexdigest()==f['archive_sha256'];assert len(data)==f['size_bytes']

@pytest.mark.parametrize('before',['fixture-check2','absent'])
def test_bad_selection_fails(settings,ledger,tmp_path,before):
    example_bundle(settings,ledger)
    with pytest.raises(DemoError):build_package(settings,ledger,'e203','fixture-check2',before,tmp_path/'bad.zip')
    assert not (tmp_path/'bad.zip').exists()

def test_tampered_snapshot_fails_without_partial_output(settings,ledger,tmp_path):
    b=example_bundle(settings,ledger)
    (settings.data/b['versions'][0]['storage_key']/'dut.v').write_text('tampered')
    with pytest.raises(DemoError):build_package(settings,ledger,'e203','fixture-check1',None,tmp_path/'bad.zip')
    assert not (tmp_path/'bad.zip').exists()

def test_budget_and_incomplete_required_material(settings,ledger,tmp_path):
    example_bundle(settings,ledger)
    for options in [{'max_bytes':1},{'max_entries':2}]:
        with pytest.raises(DemoError) as e:build_package(settings,ledger,'e203','fixture-check2',None,tmp_path/'bad.zip',**options)
        assert e.value.status==413
    assert not (tmp_path/'bad.zip').exists()

def test_complete_tiled_wave_and_relative_paths(settings,ledger,tmp_path):
    from zerorepo.rtl_web.artifacts import Artifacts
    b=example_bundle(settings,ledger);art=Artifacts(settings.data,ledger);v=b['validations'][1]
    tiles=[]
    for i in range(2):
        wave={'validation_id':v['validation_id'],'version_id':v['version_id'],'waveform_sha256':v['waveform_sha256'],'start_ticks':str(i*10),'end_ticks':str((i+1)*10),'signals':[],'sample_markers':[],'timescale':{'value':1,'unit':'ps'}}
        p=tmp_path/f'tile{i}.json';p.write_text(json.dumps(wave));a=art.add(p,'waveform_tile',display=True);tiles.append({'artifact_id':a['artifact_id'],'start_ticks':wave['start_ticks'],'end_ticks':wave['end_ticks']})
    w={'tiled':True,'validation_id':v['validation_id'],'version_id':v['version_id'],'waveform_sha256':v['waveform_sha256'],'tiles':tiles}
    p=tmp_path/'index.json';p.write_text(json.dumps(w));a=art.add(p,'waveform',display=True)
    v.update(waveform_index_artifact_id=a['artifact_id'],waveform_tile_artifact_ids=[t['artifact_id'] for t in tiles]);ledger.put('validation',v['validation_id'],v);ledger.put('bundle',b['bundle_id'],b)
    out=tmp_path/'tiles.zip';build_package(settings,ledger,'e203',v['validation_id'],None,out)
    with zipfile.ZipFile(out) as z:
        index=json.loads(z.read('validations/fixture-check2/waveform/index.json'))
        assert len(index['tiles'])==2
        for t in index['tiles']:
            assert 'artifact_id' not in t and t['url'].startswith('tiles/')
            assert 'validations/fixture-check2/waveform/'+t['url'] in z.namelist()

def test_export_manager_busy_and_stale_cleanup(settings,ledger,tmp_path):
    from zerorepo.rtl_web.evidence import ExportManager
    example_bundle(settings,ledger);m=ExportManager(settings,ledger);m.startup()
    stale=m.root/'evidence-stale.zip';stale.write_bytes(b'old');m.startup();assert not stale.exists()
    m.lock.acquire()
    try:
        with pytest.raises(DemoError) as e:m.create('e203','fixture-check2',None)
        assert e.value.code=='export_busy'
    finally:m.lock.release()
    path=m.create('e203','fixture-check2',None);assert path.exists();m.remove(path);assert not path.exists()

def test_unexpected_write_failure_removes_temporary_archive(settings,ledger,tmp_path,monkeypatch):
    example_bundle(settings,ledger)
    def fail(*a,**k):raise OSError('test write failure')
    monkeypatch.setattr(zipfile.ZipFile,'open',fail)
    with pytest.raises(OSError):build_package(settings,ledger,'e203','fixture-check2',None,tmp_path/'bad.zip')
    assert not list(tmp_path.glob('*.zip'))
