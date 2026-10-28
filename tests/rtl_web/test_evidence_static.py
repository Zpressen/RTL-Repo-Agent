import hashlib,json,zipfile
from evidence_fixtures import example_bundle
from zerorepo.rtl_web.evidence import export_packages

def test_static_packages_match_selection_and_content(settings,ledger,tmp_path):
    b=example_bundle(settings,ledger);index=export_packages(settings,ledger,b,tmp_path)
    assert len(index['single'])==2 and len(index['comparisons'])==1
    for d in list(index['single'].values())+index['comparisons']:
        p=tmp_path/'evidence'/d['url'].rsplit('/',1)[-1]
        assert hashlib.sha256(p.read_bytes()).hexdigest()==d['sha256']
        assert p.stat().st_mode & 0o777 == 0o644
        with zipfile.ZipFile(p) as z:assert json.loads(z.read('manifest.json'))['selection']['validation_id']==d['validation_id']
    assert 'evidence_packages' not in ledger.get('bundle',b['bundle_id'])
