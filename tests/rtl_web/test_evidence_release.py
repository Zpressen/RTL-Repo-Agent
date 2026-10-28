import importlib.util,json,hashlib,zipfile
from pathlib import Path
import pytest
from evidence_fixtures import example_bundle
from zerorepo.rtl_web.evidence import export_packages

def module():
    p=Path(__file__).resolve().parents[2]/'scripts/rtl_demo/release.py'
    spec=importlib.util.spec_from_file_location('studio_release',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def test_zip_publish_allowlist_and_embedded_identity(settings,ledger,tmp_path):
    b=example_bundle(settings,ledger);root=tmp_path/'design';case=root/'cases/e203';case.mkdir(parents=True)
    index=export_packages(settings,ledger,b,case);doc={**b,'evidence_packages':index};(case/'manifest.json').write_text(json.dumps(doc))
    release=module();assert len(release.files(root))==4
    other=root/'arbitrary.zip';other.write_bytes(b'not allowed')
    with pytest.raises(ValueError):release.files(root)
    other.unlink()
    d=index['single']['fixture-check2'];p=root/d['url'].lstrip('/')
    p.write_bytes(p.read_bytes()+b'tampered')
    with pytest.raises(ValueError):release.files(root)

def test_rejects_unsafe_archive_even_with_correct_outer_hash(settings,ledger,tmp_path):
    b=example_bundle(settings,ledger);root=tmp_path/'design';case=root/'cases/e203';case.mkdir(parents=True)
    p=case/'bad.zip'
    with zipfile.ZipFile(p,'w') as z:z.writestr('../private.env','secret')
    h=hashlib.sha256(p.read_bytes()).hexdigest();target=case/'evidence'/(h+'.zip');target.parent.mkdir();p.rename(target)
    doc={**b,'evidence_packages':{'single':{'x':{'url':'/cases/e203/evidence/'+h+'.zip','sha256':h,'size_bytes':target.stat().st_size}},'comparisons':[]}}
    (case/'manifest.json').write_text(json.dumps(doc))
    with pytest.raises(ValueError):module().files(root)

@pytest.mark.parametrize('attack',['duplicate','symlink','traversal','absolute','extra','raw-vcd','wrong-entry-hash','inflate-budget'])
def test_rejects_internal_archive_attacks_with_valid_outer_index(settings,ledger,tmp_path,attack):
    import stat,warnings
    b=example_bundle(settings,ledger);root=tmp_path/'design';case=root/'cases/e203';case.mkdir(parents=True)
    index=export_packages(settings,ledger,b,case);doc={**b,'evidence_packages':index}
    d=index['single']['fixture-check2'];old=root/d['url'].lstrip('/')
    with zipfile.ZipFile(old) as z:members=[(i,z.read(i)) for i in z.infolist()]
    modified=case/'modified.zip'
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',UserWarning)
        with zipfile.ZipFile(modified,'w',compression=zipfile.ZIP_DEFLATED) as z:
            for info,data in members:
                if attack=='symlink' and info.filename=='README.txt':info.external_attr=(stat.S_IFLNK|0o777)<<16
                if attack=='wrong-entry-hash' and info.filename=='README.txt':data=b'changed public entry'
                z.writestr(info,data)
            if attack=='duplicate':z.writestr('README.txt','duplicate')
            if attack=='traversal':z.writestr('../outside.txt','outside')
            if attack=='absolute':z.writestr('/absolute.txt','outside')
            if attack=='extra':z.writestr('private/session.json','{}')
            if attack=='raw-vcd':z.writestr('private/wave.vcd','private')
            if attack=='inflate-budget':
                with z.open('large.txt','w') as stream:
                    for _ in range(1025):stream.write(b'x'*65536)
    digest=hashlib.sha256(modified.read_bytes()).hexdigest();target=case/'evidence'/(digest+'.zip');modified.rename(target)
    d.update(url='/cases/e203/evidence/'+target.name,sha256=digest,size_bytes=target.stat().st_size)
    (case/'manifest.json').write_text(json.dumps(doc))
    with pytest.raises(ValueError):module().validate_evidence_zip(target,root)
