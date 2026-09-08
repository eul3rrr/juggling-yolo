import json
import pytest
from test_annotation_store import fixture_store


def test_export_full_frames(tmp_path):
    from src.annotation.export import export_yolo, normalize_box
    assert normalize_box(dict(x1=10,y1=20,x2=30,y2=40),100,100)==(.2,.3,.2,.2)
    s,_,_=fixture_store(tmp_path/'workspace')
    d=s.get(s.items()[0]['id'])
    assert export_yolo(s,tmp_path/'empty',frame_reader=lambda *args:None)==0
    b=d['boxes'][0];b.update(hand_overlap='heavy',visibility='partial',motion_blur='strong',annotation_confidence='uncertain')
    d.update(status='completed',focus_status='visible',focus_box_id=b['id'],all_visible_confirmed=True)
    s.save(d['id'],d)
    import numpy as np
    out=tmp_path/'export'
    assert export_yolo(s,out,frame_reader=lambda *args:np.zeros((240,320,3),dtype=np.uint8))==1
    line=next((out/'labels').rglob('*.txt')).read_text().strip().split()
    assert line[0]=='0' and len(line)==5
    meta=json.loads((out/'metadata.jsonl').read_text())
    assert meta['boxes'][0]['hand_overlap']=='heavy' and meta['provenance']
    assert meta['source']['source_group']=='session1' and meta['split']=='unassigned'
    assert meta['focus_box_id']==b['id'] and meta['predictions']
    assert 'train:' not in (out/'data.yaml').read_text()
    with pytest.raises(ValueError): export_yolo(s,out)
