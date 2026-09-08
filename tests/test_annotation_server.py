import json
import threading
from urllib.request import urlopen,Request
from urllib.error import HTTPError
import pytest
from test_annotation_store import fixture_store


def test_local_server_persistence_and_routes(tmp_path):
    from src.annotation.server import make_server
    s,_,_=fixture_store(tmp_path)
    server=make_server(s,'127.0.0.1',0)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        state=json.load(urlopen(base+'/api/items'))
        iid=state['items'][0]['id']
        d=json.load(urlopen(base+'/api/item?id='+iid))
        d.update(boxes=[],status='completed',focus_status='uncertain',all_visible_confirmed=True)
        req=Request(base+'/api/save',data=json.dumps(d).encode(),headers={'Content-Type':'application/json'})
        assert json.load(urlopen(req))['revision']==1
        assert json.load(urlopen(base+'/api/item?id='+iid))['status']=='completed'
        bad=Request(base+'/api/save',data=b'{}',headers={'Content-Type':'application/json','Origin':'https://evil.example'})
        with pytest.raises(HTTPError) as err: urlopen(bad)
        assert err.value.code==403
        with pytest.raises(HTTPError): urlopen(base+'/../../.git/config')
    finally:
        server.shutdown();server.server_close();thread.join()
