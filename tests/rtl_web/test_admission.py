from concurrent.futures import ThreadPoolExecutor
import pytest
from zerorepo.rtl_web.store import Store
from zerorepo.rtl_web.schemas import DemoError


def message(store,sid,key):
    return store.add_message(sid,key,{'text':'explain','context_ref':{},'client_message_id':key})


def test_global_chat_limit_and_idempotency(tmp_path):
    a=Store(tmp_path/'state');b=Store(tmp_path/'state')
    s1=a.create_session('first',{})['session_id'];s2=b.create_session('second',{})['session_id']
    msg,new=message(a,s1,'one');assert new
    same,new=message(a,s1,'one');assert not new and same['message_id']==msg['message_id']
    with pytest.raises(DemoError) as e:message(b,s2,'two')
    assert e.value.status==429
    assert b.session(s2)['messages']==[]
    with pytest.raises(DemoError) as e:message(a,s1,'three')
    assert e.value.status==409
    a.update_message(msg['message_id'],state='answered',answer='done')
    assert message(b,s2,'two')[1]


def test_two_connections_cannot_both_acquire_chat_slot(tmp_path):
    stores=[Store(tmp_path/'state') for _ in range(2)]
    sids=[s.create_session(str(i),{})['session_id'] for i,s in enumerate(stores)]
    def submit(i):
        try:message(stores[i],sids[i],str(i));return 202
        except DemoError as e:return e.status
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(submit,range(2)))==[202,429]
