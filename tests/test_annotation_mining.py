import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_mine_and_crop():
    from scripts.review_track_events import Track, TrackObservation
    from src.annotation.mining import mine_candidates, crop_geometry, interpolate
    def track(tid, frames):
        return Track(tid, [TrackObservation(f, 30+f, 50, .8, o) for f,o in frames])
    tracks = {1:track(1, [(0,0)]+[(f,1) for f in range(2,61)]+[(65,0)]),
              2:track(2, [(63,0)]+[(f,1) for f in range(64,160)])}
    links = [{'source_track_id':1,'target_track_id':2,'association_type':'HAND'}]
    items = mine_candidates(tracks, links, 60, 180, 320, 240)
    assert items == mine_candidates(tracks, links, 60, 180, 320, 240)
    assert len({i['frame'] for i in items}) == len(items)
    assert items[0]['priority'] == 0
    transition = next(i for i in items if i['frame']==62)
    assert {'linked_gap','track_end'} <= set(transition['reasons'])
    assert any(p['inside_gap'] for p in transition['provenance'])
    assert transition['boxes'] == []
    ends = [p for i in items for p in i['provenance'] if p['kind']=='track_end']
    assert {p['end_frame'] for p in ends} == {60,159}
    starts = [p for i in items for p in i['provenance'] if p['kind']=='orphan_start']
    assert {p['start_frame'] for p in starts} == {2}
    ordinary = [i for i in items if i['priority']==2]
    assert ordinary
    assert all(min(abs(i['frame']-b) for b in [2,60,64,159]) > 15 for i in ordinary)
    assert all(0 <= i['frame'] < 180 for i in items)
    assert interpolate((0,0),(100,50),0,10,5) == (50,25)
    pose = {'left_wrist_x':20,'left_wrist_y':30,'left_elbow_x':40,'left_elbow_y':60,
            'left_shoulder_x':60,'left_shoulder_y':90,'body_scale_shoulder_px':40}
    x1,y1,x2,y2 = crop_geometry((10,20),320,240,pose)
    assert 0<=x1<=10 and 0<=y1<=20 and 60<=x2<=320 and 90<=y2<=240
    assert crop_geometry((-100,300),320,240) == [0,108,176,240]


def test_temporal_sampling():
    from src.annotation.mining import boundary_frames, gap_frames
    assert boundary_frames(20, 60, 100) == [5,11,14,16,18,19,20,21,22,24,26,29,35]
    assert boundary_frames(0, 30, 10) == [0,1,2,3,4,8]
    assert gap_frames(10, 15, 60) == [11,12,13,14]
    assert gap_frames(10, 50, 60) == [11,12,20,30,40,48,49]
