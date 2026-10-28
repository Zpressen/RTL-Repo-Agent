import pytest
from pydantic import ValidationError
from zerorepo.rtl_web.schemas import Context, Selection, DemoError
from zerorepo.rtl_web.story_schemas import StoryBundle
from zerorepo.rtl_web.stories import prepare_story, publish_story, story_view
from story_fixtures import story_fixture

def test_context_backwards_compatible():
    assert Context().view == 'workspace'
    assert Selection().workspace_panel == 'architecture'
    with pytest.raises(ValidationError): Context(view='foreign')
    with pytest.raises(ValidationError): StoryBundle(**{**story_fixture(), 'campaigns': []})

def test_synthetic_not_publishable(ledger):
    story = prepare_story(story_fixture())
    with pytest.raises((ValueError, DemoError)):
        publish_story(ledger, story, activate=True)

def test_empty_has_no_metrics(ledger):
    view = story_view(ledger, 'e203')
    assert view['optimization']['state'] == 'awaiting_data'
    assert view['experience']['state'] == 'empty'
    assert 'storage_key' not in str(view)


@pytest.mark.parametrize('kind',['archived','pass','fail','revision','missing_reference','cross_case'])
def test_scenarios_remain_synthetic(ledger,kind):
    from story_fixtures import story_scenario
    value=prepare_story(story_scenario(kind))
    with pytest.raises(ValueError,match='Synthetic'):
        publish_story(ledger,value,activate=True)

def test_cyclic_revisions_rejected():
    from story_fixtures import story_scenario
    value=story_scenario('revision');value['memories'][0]['parent_revision_id']='synthetic-v2'
    with pytest.raises(ValidationError,match='Cyclic'):
        StoryBundle.model_validate(value)
