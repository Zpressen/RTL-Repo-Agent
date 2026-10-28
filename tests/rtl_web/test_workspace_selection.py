import pytest
from zerorepo.rtl_web.schemas import Context, Selection
@pytest.mark.parametrize('panel',['spec','architecture','code','verify','repair'])
def test_five_panels(panel):
    assert Context(workspace_panel=panel).workspace_panel==panel
    assert Selection(workspace_panel=panel).workspace_panel==panel

def test_old_selection_and_context():
    assert Selection().workspace_panel=='architecture'
    assert Context(view='experience').view=='experience'
