import base64
import hashlib
import json
from pathlib import Path
import pytest
import yaml
from fastapi.testclient import TestClient
from zerorepo.rtl_web.settings import Settings


def setup_gateway(tmp_path,settings,password_required=True,access_mode='ssh_tunnel',origin='https://design.deepvalleychip.cn'):
    from zerorepo.rtl_web.tunnel_gateway import create_gateway
    cfg=dict(settings.raw);cfg.update(development=False,access_mode='ssh_tunnel',allowed_origins=['http://127.0.0.1:18173'])
    if access_mode=='public':cfg.update(access_mode='public',allowed_origins=[origin])
    settings.config_path.write_text(yaml.safe_dump(cfg));selected=Settings(settings.config_path)
    selected.gateway_key='synthetic-internal-gateway-key'
    public=tmp_path/'design';public.mkdir();(public/'index.html').write_text('<html>RTL workspace</html>')
    auth=tmp_path/'auth.json';salt='synthetic-test-salt';password='synthetic-login-password'
    auth.write_text(json.dumps({'password_required':password_required,'username':'demo','salt':salt,'iterations':100000,
        'password_hash':hashlib.pbkdf2_hmac('sha256',password.encode(),salt.encode(),100000).hex()}));auth.chmod(0o600)
    from deployment_fixtures import historical_store
    historical_store(selected.data)
    app=create_gateway(selected,public,auth)
    headers={'Authorization':'Basic '+base64.b64encode(('demo:'+password).encode()).decode()}
    return app,headers


@pytest.mark.parametrize('origin',['https://design.deepvalleychip.cn','https://agent.deepvalleychip.cn'])
def test_public_gateway_requires_https_origin_and_sets_secure_cookie(tmp_path,settings,origin):
    app,_=setup_gateway(tmp_path,settings,password_required=False,access_mode='public',origin=origin)
    with TestClient(app,base_url=origin) as client:
        assert client.get('/').status_code==200
        assert client.get('/api/health').json()['phase']=='production'
        headers={'Origin':origin,'X-Demo-Request':'1','Idempotency-Key':'public-session'}
        response=client.post('/api/sessions',headers=headers,json={'case_id':'e203'})
        assert response.status_code==201
        assert 'Secure' in response.headers['set-cookie']
        assert client.get('/api/sessions/'+response.json()['session_id']).status_code==200
        headers.update(Origin='http://127.0.0.1:18173',**{'Idempotency-Key':'wrong-origin'})
        assert client.post('/api/sessions',headers=headers,json={'case_id':'e203'}).status_code==403
        other='https://agent.deepvalleychip.cn' if 'design.' in origin else 'https://design.deepvalleychip.cn'
        headers.update(Origin=other,**{'Idempotency-Key':'other-host'})
        assert client.post('/api/sessions',headers=headers,json={'case_id':'e203'}).status_code==403


def test_public_gateway_rejects_http_origin(tmp_path,settings):
    from zerorepo.rtl_web.tunnel_gateway import create_gateway
    setup_gateway(tmp_path,settings,password_required=False,access_mode='public')
    cfg=yaml.safe_load(settings.config_path.read_text());cfg['allowed_origins']=['http://design.deepvalleychip.cn']
    settings.config_path.write_text(yaml.safe_dump(cfg));selected=Settings(settings.config_path);selected.gateway_key='synthetic'
    with pytest.raises(ValueError,match='HTTPS origin'):create_gateway(selected,tmp_path/'design',tmp_path/'auth.json')


def test_passwordless_ssh_preview_keeps_session_and_origin_boundary(tmp_path,settings):
    app,_=setup_gateway(tmp_path,settings,password_required=False)
    with TestClient(app,base_url='http://127.0.0.1:18173') as client:
        response=client.get('/')
        assert response.status_code==200
        assert 'www-authenticate' not in response.headers
        assert client.get('/api/health').status_code==200
        headers={'Origin':'http://127.0.0.1:18173','X-Demo-Request':'1','Idempotency-Key':'without-password'}
        response=client.post('/api/sessions',headers=headers,json={'case_id':'e203'})
        assert response.status_code==201
        assert client.get('/api/sessions/'+response.json()['session_id']).status_code==200
        headers.update(Origin='https://untrusted.invalid',**{'Idempotency-Key':'untrusted'})
        assert client.post('/api/sessions',headers=headers,json={'case_id':'e203'}).status_code==403


def test_private_ssh_gateway_authenticates_static_and_api(tmp_path,settings):
    app,headers=setup_gateway(tmp_path,settings)
    with TestClient(app,base_url='http://127.0.0.1:18173') as client:
        assert client.get('/').status_code==401
        assert client.get('/api/health').status_code==401
        assert client.get('/',headers=headers).text=='<html>RTL workspace</html>'
        health=client.get('/api/health',headers=headers).json()
        assert health['status']=='ok'
        assert health['phase']=='ssh_preview'
        assert client.get('/api/not-an-api',headers=headers).status_code==404
        assert client.get('/.env',headers=headers).status_code==404


def test_ssh_preview_cookie_and_origin_remain_separate_from_production(tmp_path,settings):
    app,headers=setup_gateway(tmp_path,settings)
    with TestClient(app,base_url='http://127.0.0.1:18173') as client:
        send={**headers,'Origin':'http://127.0.0.1:18173','X-Demo-Request':'1','Idempotency-Key':'tunnel-session'}
        response=client.post('/api/sessions',headers=send,json={'case_id':'e203'})
        assert response.status_code==201
        assert 'Secure' not in response.headers['set-cookie']
        sid=response.json()['session_id']
        assert client.get('/api/sessions/'+sid,headers=headers).status_code==200
        send.update(Origin='https://untrusted.invalid',**{'Idempotency-Key':'another-session'})
        assert client.post('/api/sessions',headers=send,json={'case_id':'e203'}).status_code==403


def test_ssh_preview_configuration_rejects_public_origin(settings):
    cfg=dict(settings.raw);cfg.update(access_mode='ssh_tunnel',development=False,allowed_origins=['https://design.deepvalleychip.cn'])
    settings.config_path.write_text(yaml.safe_dump(cfg))
    with pytest.raises(ValueError):Settings(settings.config_path)


def test_static_entry_and_manifest_revalidate_after_release_update(tmp_path,settings):
    app,_=setup_gateway(tmp_path,settings,password_required=False)
    public=tmp_path/'design'
    (public/'release.json').write_text('{"release_id":"old"}')
    with TestClient(app,base_url='http://127.0.0.1:18173') as client:
        for path,updated in [('/', '<html>Updated RTL Studio workspace</html>'),
                             ('/release.json', '{"release_id":"new-studio"}')]:
            initial=client.get(path)
            assert 'no-cache' in initial.headers['cache-control']
            cached=client.get(path,headers={'If-None-Match':initial.headers['etag']})
            assert cached.status_code==304
            assert 'must-revalidate' in cached.headers['cache-control']
            (public/('index.html' if path=='/' else 'release.json')).write_text(updated)
            fresh=client.get(path,headers={'If-None-Match':initial.headers['etag']})
            assert fresh.status_code==200
            assert fresh.text==updated
            assert fresh.headers['etag']!=initial.headers['etag']


def test_event_stream_rotates_and_resumes_without_losing_events(tmp_path, settings, monkeypatch):
    import zerorepo.rtl_web.api as api
    from zerorepo.rtl_web.store import Store
    monkeypatch.setattr(api, 'EVENT_STREAM_SECONDS', 0.05)
    app,_=setup_gateway(tmp_path,settings,password_required=False)
    with TestClient(app,base_url='http://127.0.0.1:18173') as client:
        headers={'Origin':'http://127.0.0.1:18173','X-Demo-Request':'1','Idempotency-Key':'rotate-events'}
        session=client.post('/api/sessions',headers=headers,json={'case_id':'e203'}).json()
        ident=session['session_id']
        url='/api/sessions/'+ident+'/events'
        first=client.get(url)
        assert first.status_code==200
        assert first.text.startswith('retry: 3000\n\n')
        assert 'event: session.created' in first.text
        cursor=int(next(line[4:] for line in first.text.splitlines() if line.startswith('id: ')))
        store=Store(settings.data)
        store.selection(ident,{'case_id':'e203','panel':'verify'})
        resumed=client.get(url,headers={'Last-Event-ID':str(cursor)})
        assert 'event: selection.updated' in resumed.text
        assert 'event: session.created' not in resumed.text
        assert resumed.headers['x-accel-buffering']=='no'
        assert app.active == {'request':0,'stream':0}
