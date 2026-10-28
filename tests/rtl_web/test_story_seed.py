import json
from deployment_fixtures import historical_store
from test_seed import config
from test_story_evidence import archived
from zerorepo.rtl_web.settings import Settings
from zerorepo.rtl_web.seed import export_seed,import_seed,validate_seed
from zerorepo.rtl_web.stories import publish_story,story_view
from zerorepo.rtl_web.store import Store

def test_story_v2_roundtrip_and_original_v1(tmp_path):
    store,_=historical_store(tmp_path/'source')
    settings=Settings(config(tmp_path,store.root))
    export_seed(settings,tmp_path/'old')
    assert validate_seed(tmp_path/'old')['schema_version']=='rtl-demo-seed-v1'
    data=archived(store);publish_story(store,data,activate=True)
    export_seed(settings,tmp_path/'new')
    assert validate_seed(tmp_path/'new')['schema_version']=='rtl-demo-seed-v2'
    target=Settings(config(tmp_path,tmp_path/'target'))
    import_seed(target,tmp_path/'new')
    assert story_view(Store(target.data),'e203')['story_id']==data['story_id']
    import_seed(target,tmp_path/'old')
    assert story_view(Store(target.data),'e203')['story_id'] is None
