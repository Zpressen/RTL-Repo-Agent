from fastapi.testclient import TestClient
from zerorepo.rtl_web.api import create_app

def test_waiting_api(settings):
    with TestClient(create_app(settings), base_url='http://127.0.0.1') as client:
        for case in ['e203','aes_cipher_system_hard','aes_inv_cipher_top_system','sdc_controller_system']:
            response = client.get('/api/cases/'+case+'/stories')
            assert response.status_code == 200
            assert response.json()['optimization']['state'] == 'awaiting_data'
            assert response.json()['experience']['memories'] == []
        assert client.get('/api/stories/story-absent').status_code == 404
