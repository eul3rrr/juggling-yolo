import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def fixture_store(tmp_path):
    from src.annotation.store import Store
    s = Store(tmp_path)
    source = dict(source_key='video1', video_path='/tmp/source.mp4', fps=60, width=320, height=240, frame_count=100, source_group='session1')
    item = dict(frame=10, timestamp=10 / 60, priority=0, reasons=['linked_gap'], provenance=[{'event_key': 'link:1', 'kind': 'linked_gap'}], crop=[0, 0, 200, 200], focus_point=[30, 40], boxes=[])
    s.mine(source, [item], {10: [dict(x1=10, y1=20, x2=30, y2=40, confidence=0.8)]})
    return (s, source, item)

def test_annotation_roundtrip_and_resume(tmp_path):
    s, source, item = fixture_store(tmp_path)
    data = s.get(s.items()[0]['id'])
    box = data['boxes'][0]
    box.update(occluder='none', occlusion='none', visibility='clear', motion_blur='none', annotation_confidence='certain')
    manual = dict(box, id='manual1', annotation_source='manual', prediction_id=None, x1=50, x2=70)
    data.update(boxes=[box, manual], status='completed', focus_status='visible', focus_box_id=box['id'], all_visible_confirmed=True)
    s.save(data['id'], data)
    saved = s.get(data['id'])
    assert len(saved['boxes']) == 2 and saved['focus_box_id'] == box['id']
    s.mine(source, [item], {10: [dict(x1=10, y1=20, x2=30, y2=40, confidence=0.8)]})
    assert len(s.items()) == 1 and s.get(data['id']) == saved
    saved.update(boxes=[manual], focus_status='no_visible_evidence', focus_box_id=None)
    s.save(data['id'], saved)
    again = s.get(data['id'])
    assert again['predictions'][0]['deleted'] is True
    assert again['boxes'][0]['annotation_source'] == 'manual'
    assert again['boxes'][0]['source_detector_box'] is None
    with pytest.raises(ValueError):
        s.save(data['id'], saved)

def test_completed_visible_focus_metadata_is_optional_even_without_boxes(tmp_path):
    s, _, _ = fixture_store(tmp_path)
    d = s.get(s.items()[0]['id'])
    d.update(boxes=[], status='completed', focus_status='visible')
    saved = s.save(d['id'], d)
    assert saved['status'] == 'completed' and saved['boxes'] == []

def test_completion_validation(tmp_path):
    s, _, _ = fixture_store(tmp_path)
    d = s.get(s.items()[0]['id'])
    d.update(status='completed', focus_status='', all_visible_confirmed=False)
    saved = s.save(d['id'], d)
    assert saved['focus_status'] == ''
    assert saved['boxes'][0]['visibility'] == ''
    assert saved['all_visible_confirmed'] is False
    d = saved
    d['boxes'] = []
    d = s.save(d['id'], d)
    d = s.get(d['id'])
    d['focus_box_id'] = 'absent'
    d['focus_status'] = 'visible'
    with pytest.raises(ValueError):
        s.save(d['id'], d)


def test_completed_optional_metadata_still_rejects_invalid_values(tmp_path):
    s, _, _ = fixture_store(tmp_path)
    d = s.get(s.items()[0]['id'])
    d.update(status='completed', focus_status='invented')
    with pytest.raises(ValueError, match='focus status'):
        s.save(d['id'], d)
    d['focus_status'] = ''
    d['boxes'][0]['visibility'] = 'invented'
    with pytest.raises(ValueError, match='survey'):
        s.save(d['id'], d)


def test_multiple_sources_and_atomic_rejection(tmp_path):
    s, source, item = fixture_store(tmp_path)
    s.mine(dict(source, source_key='video2', video_path='/tmp/other.mp4'), [item], {})
    assert len(s.items()) == 2
    assert len({i['source_id'] for i in s.items()}) == 2
    first = s.get(s.items()[0]['id'])
    broken = dict(first, status='skipped', boxes=[dict(id='bad', x1=-1, y1=0, x2=10, y2=10)])
    with pytest.raises(ValueError):
        s.save(first['id'], broken)
    assert s.get(first['id']) == first
    with pytest.raises(ValueError):
        s.mine(dict(source, fps=30), [item], {})
