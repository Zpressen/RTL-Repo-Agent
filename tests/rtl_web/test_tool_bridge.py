import pytest


def test_scope_rejects_foreign_ids_and_arbitrary_queries():
    from zerorepo.rtl_web.tool_bridge import validate_call
    validate_call('run-one','get_debug_status',{})
    with pytest.raises(ValueError):validate_call('run-one','shell',{'command':'whoami'})
    with pytest.raises(ValueError):validate_call('run-one','query_rtl_kg',{'cypher':'MATCH (n) RETURN n'})
    with pytest.raises(ValueError):validate_call('run-one','get_debug_status',{'run_id':'run-two'})


def test_real_socket_authentication_and_fixed_dispatch(tmp_path,monkeypatch):
    import json,socket
    from zerorepo.rtl_web.tool_bridge import ToolBridge,bridge_call
    class Session:
        calls=0
        def get_debug_status(self):self.calls+=1;return {'scope':'run-one'}
        def close(self):pass
    session=Session()
    bridge=ToolBridge(tmp_path/'descriptor','run-one',session_factory=lambda p:session)
    try:
        for k,v in bridge.environment().items():monkeypatch.setenv(k,v)
        assert bridge_call('get_debug_status',[],{})=={'scope':'run-one'}
        assert session.calls==1
        assert bridge_call('query_rtl_kg',[],{'cypher':'MATCH(n) RETURN n'})['status']=='tool_error'
        monkeypatch.setenv('ZEROREPO_TOOL_BRIDGE_TOKEN','wrong-token')
        assert bridge_call('get_debug_status',[],{})['status']=='tool_error'
        assert session.calls==1
    finally:bridge.close()
