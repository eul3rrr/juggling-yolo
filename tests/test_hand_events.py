from pathlib import Path
import csv
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import hand_events as he


def rows(kind="END", evidence="1", eligible="{LEFT}", preferred="LEFT", ambiguous="0"):
    common = {"track_id":"2", "boundary_type":kind, "boundary_frame":"882",
              "boundary_x":"1", "boundary_y":"2", "eligible_hand_set":eligible,
              "preferred_hand":preferred, "ambiguous":ambiguous, "hand_evidence":evidence,
              "evidence_reason":"very_near"}
    return [dict(common, hand="LEFT", proximity_band="VERY_NEAR", motion="APPROACHING",
                 endpoint_distance_px="10", endpoint_distance_normalized="0.1",
                 recent_min_distance_px="10", recent_min_distance_normalized="0.1", post_contact="0"),
            dict(common, hand="RIGHT", proximity_band="FAR", motion="NEUTRAL",
                 endpoint_distance_px="100", endpoint_distance_normalized="1.0",
                 recent_min_distance_px="100", recent_min_distance_normalized="1.0", post_contact="0")]


def write_rows(path, data):
    fields=sorted({k for r in data for k in r})
    with path.open("w", newline="") as f:
        w=csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(data)


def test_end_with_hand_evidence_is_entry(tmp_path):
    p=tmp_path/"a.csv"; write_rows(p, rows("END"))
    e=he.load_logical_events(p, 2, 1078)[0]
    assert e.event_type == "HAND_ENTRY"


def test_start_with_hand_evidence_is_exit(tmp_path):
    p=tmp_path/"a.csv"; write_rows(p, rows("START"))
    assert he.load_logical_events(p, 2, 1078)[0].event_type == "HAND_EXIT"


def test_no_evidence_maps_to_non_hand_events(tmp_path):
    p=tmp_path/"a.csv"; write_rows(p, rows("END", "0", "{}", "", "0"))
    assert he.load_logical_events(p, 2, 1078)[0].event_type == "NON_HAND_END"
    write_rows(p, rows("START", "0", "{}", "", "0"))
    assert he.load_logical_events(p, 2, 1078)[0].event_type == "NON_HAND_START"


def test_ambiguous_is_one_event_and_preserves_set(tmp_path):
    p=tmp_path/"a.csv"; write_rows(p, rows(eligible="{LEFT,RIGHT}", preferred="", ambiguous="1"))
    e=he.load_logical_events(p, 2, 1078)[0]
    assert len(he.load_logical_events(p, 2, 1078)) == 1
    assert e.eligible_hand_set == "{LEFT,RIGHT}"
    assert e.preferred_hand is None
    assert e.ambiguous is True
    assert e.endpoint_distance_px == ""


def test_unambiguous_preferred_and_complete_set_are_retained(tmp_path):
    p=tmp_path/"a.csv"; write_rows(p, rows(eligible="{LEFT,RIGHT}", preferred="LEFT", ambiguous="0"))
    e=he.load_logical_events(p, 2, 1078)[0]
    assert e.preferred_hand == "LEFT"
    assert e.eligible_hand_set == "{LEFT,RIGHT}"


def test_video_boundary_flags_are_derived_from_frame_range(tmp_path):
    p=tmp_path/"a.csv"; d=rows("START")
    for row in d: row["boundary_frame"]="2"
    write_rows(p, d)
    e=he.load_logical_events(p, 2, 1078)[0]
    assert e.video_start_boundary is True and e.video_end_boundary is False
    d=rows("END"); d[0]["boundary_frame"]="1078"; d[1]["boundary_frame"]="1078"; write_rows(p,d)
    e=he.load_logical_events(p, 2, 1078)[0]
    assert e.video_end_boundary is True


def test_module_has_no_pairing_or_association_fields(tmp_path):
    p=tmp_path/"a.csv"; write_rows(p, rows("END"))
    e=he.load_logical_events(p, 2, 1078)[0]
    assert not hasattr(e, "source_track_id")
    assert not hasattr(e, "target_track_id")
    assert not hasattr(e, "paired_event")
