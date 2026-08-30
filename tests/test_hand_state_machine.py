from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from hand_events import HandEvent
import hand_state_machine as sm


def ev(tid, kind, frame, hands, preferred=None, ambiguous=False, start=False, end=False):
    return HandEvent(tid, "END" if kind == "HAND_ENTRY" else "START", frame, kind, "0", "0", hands, preferred, ambiguous, True, "test", start, end, "VERY_NEAR", "", "1", "", "1", "", False)


def run(events, fps: float = 10, expiry=5):
    return sm.match_hand_events(events, fps, expiry)


def test_simple_left_entry_exit():
    r=run([ev(1,"HAND_ENTRY",10,"{LEFT}"),ev(2,"HAND_EXIT",20,"{LEFT}","LEFT")])
    assert [(x.source_track_id,x.target_track_id,x.resolved_hand) for x in r.associations] == [(1,2,"LEFT")]


def test_simple_right_entry_exit():
    r=run([ev(1,"HAND_ENTRY",10,"{RIGHT}"),ev(2,"HAND_EXIT",20,"{RIGHT}","RIGHT")])
    assert len(r.associations)==1 and r.associations[0].resolved_hand=="RIGHT"


def test_fifo_two_left_sources():
    r=run([ev(20,"HAND_ENTRY",10,"{LEFT}"),ev(21,"HAND_ENTRY",11,"{LEFT}"),ev(30,"HAND_EXIT",20,"{LEFT}","LEFT"),ev(31,"HAND_EXIT",21,"{LEFT}","LEFT")])
    assert [(a.source_track_id,a.target_track_id) for a in r.associations] == [(20,30),(21,31)]


def test_left_right_pending_are_independent():
    r=run([ev(1,"HAND_ENTRY",10,"{LEFT}"),ev(2,"HAND_ENTRY",11,"{RIGHT}"),ev(3,"HAND_EXIT",20,"{RIGHT}","RIGHT")])
    assert [(a.source_track_id,a.target_track_id) for a in r.associations] == [(2,3)]


def test_ambiguous_source_is_stored_once_and_consumed_once():
    r=run([ev(2,"HAND_ENTRY",10,"{LEFT,RIGHT}",ambiguous=True),ev(3,"HAND_EXIT",20,"{LEFT}","LEFT"),ev(4,"HAND_EXIT",21,"{RIGHT}","RIGHT")])
    assert len(r.associations)==1 and r.associations[0].source_track_id==2
    assert r.associations[0].match_rule == "FIFO_AMBIGUOUS_SOURCE_RESOLVED"


def test_preferred_exit_does_not_fallback():
    r=run([ev(1,"HAND_ENTRY",10,"{RIGHT}"),ev(2,"HAND_EXIT",20,"{LEFT,RIGHT}","LEFT")])
    assert not r.associations and any(x.reason=="NO_COMPATIBLE_PENDING_SOURCE" for x in r.unmatched)


def test_ambiguous_exit_chooses_oldest_compatible():
    r=run([ev(1,"HAND_ENTRY",10,"{RIGHT}"),ev(2,"HAND_ENTRY",11,"{LEFT}"),ev(3,"HAND_EXIT",20,"{LEFT,RIGHT}",ambiguous=True)])
    assert r.associations[0].source_track_id==1
    assert r.associations[0].resolved_hand=="RIGHT"


def test_age_does_not_change_fifo_order():
    r=run([ev(1,"HAND_ENTRY",10,"{LEFT}"),ev(2,"HAND_ENTRY",40,"{LEFT}"),ev(3,"HAND_EXIT",50,"{LEFT}","LEFT")], fps=10, expiry=10)
    assert r.associations[0].source_track_id==1


def test_stale_source_expires():
    r=run([ev(1,"HAND_ENTRY",0,"{LEFT}"),ev(2,"HAND_EXIT",51,"{LEFT}","LEFT")], fps=10, expiry=5)
    assert not r.associations
    assert any(x.event.track_id==1 and x.reason=="EXPIRED_PENDING_SOURCE" for x in r.unmatched)


def test_video_start_exit_unmatched():
    r=run([ev(2,"HAND_EXIT",2,"{LEFT}","LEFT",start=True)])
    assert not r.associations and r.unmatched[0].reason=="VIDEO_START_EXIT"


def test_video_end_entry_unresolved():
    r=run([ev(2,"HAND_ENTRY",1078,"{LEFT}",end=True)])
    assert not r.associations and r.unmatched[0].reason=="VIDEO_END_PENDING_ENTRY"


def test_same_frame_is_not_match():
    r=run([ev(1,"HAND_ENTRY",10,"{LEFT}"),ev(2,"HAND_EXIT",10,"{LEFT}","LEFT")])
    assert not r.associations


def test_non_hand_events_are_ignored():
    non=HandEvent(1,"END",10,"NON_HAND_END","0","0","{}",None,False,False,"far",False,False,"","","","","","",False)
    r=run([non,ev(2,"HAND_EXIT",20,"{LEFT}","LEFT")])
    assert not r.associations
    assert all(x.event.event_type != "NON_HAND_END" for x in r.unmatched)


def test_source_and_target_uniqueness():
    r=run([ev(1,"HAND_ENTRY",1,"{LEFT}"),ev(2,"HAND_EXIT",2,"{LEFT}","LEFT"),ev(3,"HAND_EXIT",3,"{LEFT}","LEFT")])
    assert len(r.associations)==1
    assert len({a.source_track_id for a in r.associations})==len(r.associations)
    assert len({a.target_track_id for a in r.associations})==len(r.associations)


def test_no_pairing_fields_or_distance_selection():
    r=run([ev(1,"HAND_ENTRY",1,"{LEFT}"),ev(2,"HAND_EXIT",2,"{LEFT}","LEFT")])
    assert not hasattr(r.associations[0], "score")
    assert not hasattr(r.associations[0], "successor_event")


def test_canonical_data_obeys_hand_association_invariants():
    root = Path(__file__).resolve().parents[1]
    events = sm.load_hand_events(
        root / "detections/detector_seg_comparison/identical_balls_trick_000_018_hand_events.csv"
    )
    result = run(events, fps=59.94)
    assert len({a.source_track_id for a in result.associations}) == len(result.associations)
    assert len({a.target_track_id for a in result.associations}) == len(result.associations)
    assert all(a.source_end_frame < a.target_start_frame for a in result.associations)
    assert all(x.event.event_type in {"HAND_ENTRY", "HAND_EXIT"} for x in result.unmatched)
