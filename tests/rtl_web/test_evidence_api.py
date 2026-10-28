import json,zipfile,io
from fastapi.testclient import TestClient
from evidence_fixtures import example_bundle
from zerorepo.rtl_web.api import create_app

def test_public_download_and_cleanup(settings,ledger):
    example_bundle(settings,ledger)
    with TestClient(create_app(settings),base_url='http://127.0.0.1') as c:
        r=c.get('/api/cases/e203/evidence.zip?validation_id=fixture-check2')
        assert r.status_code==200,r.text[:100] if r.status_code!=200 else ''
        assert r.headers['content-type']=='application/zip'
        assert not list((settings.data/'export-tmp').glob('*.zip'))
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:assert json.loads(z.read('manifest.json'))['selection']['validation_id']=='fixture-check2'
        assert c.get('/api/cases/e203/evidence.zip?validation_id=fixture-check2',headers={'X-Demo-Case':'sdc_controller_system'}).status_code==422
        assert c.get('/api/cases/e203/evidence.zip?validation_id=fixture-check2&before_validation_id=fixture-check2').status_code==422
        assert c.get('/api/cases/e203/evidence.zip?validation_id=absent').status_code==404

def test_private_record_is_not_exportable_even_with_owner(settings,ledger):
    example_bundle(settings,ledger)
    ledger.put('validation','private-check',{'validation_id':'private-check','run_id':'fixture-history','version_id':'fixture-v2'},'private-owner')
    with TestClient(create_app(settings),base_url='http://127.0.0.1') as c:
        assert c.get('/api/cases/e203/evidence.zip?validation_id=private-check').status_code==403
