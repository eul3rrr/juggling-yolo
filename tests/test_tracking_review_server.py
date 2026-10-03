import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.tracking.review_server import LabelStore, build_payload, link_key


def write_identity_dir(root: Path) -> Path:
    (root / "summary.json").write_text(json.dumps({"fps": 60.0, "segments": [
        {"segment_index": 0, "start_frame": 0, "end_frame": 4, "start_seconds": 0.0,
         "accel_y_px_per_frame2": 2.0, "accel_source": "segment", "ball_count": 1,
         "ball_count_source": "estimated", "identities": 1, "tracklets": 2, "links": {"hidden": 1},
         "unassigned_tracklets": 0, "unassigned_observed_frames": 0, "clutter_tracklets": 0},
        {"segment_index": 1, "start_frame": 100, "end_frame": 103, "start_seconds": 1.667,
         "accel_y_px_per_frame2": 2.0, "accel_source": "segment", "ball_count": 1,
         "ball_count_source": "estimated", "identities": 1, "tracklets": 1, "links": {},
         "unassigned_tracklets": 0, "unassigned_observed_frames": 0, "clutter_tracklets": 0},
    ]}))
    (root / "ball_states.csv").write_text(
        "frame,segment_index,ball_id,chain_id,state,hand,x,y,position_source,track_id\n"
        "0,0,1,1,AIRBORNE,,1,1,detection,1\n"
        "1,0,1,1,AIRBORNE,,2,2,detection,1\n"
        "2,0,1,1,HIDDEN,,,,,\n"
        "3,0,1,1,HELD,LEFT,3,3,detection,2\n"
        "4,0,1,1,HELD,LEFT,4,4,detection,2\n"
        "100,1,1,2,AIRBORNE,,1,1,detection,3\n"
        "101,1,1,2,AIRBORNE,,2,2,predicted,3\n"
        "102,1,1,2,AIRBORNE,,3,3,detection,3\n")
    (root / "links.csv").write_text(
        "segment_index,ball_id,chain_id,source_track_id,target_track_id,kind,hand,cost,gap_frames,"
        "source_end_frame,target_start_frame,source_end_seconds,fit_rmse_px\n"
        "0,1,1,1,2,hidden,LEFT,9.50,1,1,3,0.017,\n")
    return root


def test_payload_compresses_states_and_offsets_segments(tmp_path):
    root = write_identity_dir(tmp_path)
    payload = build_payload(root, LabelStore(root / "labels.csv"), "clip")
    first, second = payload["segments"]
    assert (first["video_offset"], first["first_frame"], first["last_frame"]) == (0, 0, 4)
    assert (second["video_offset"], second["first_frame"], second["last_frame"]) == (5, 100, 102)
    assert first["balls"][0]["runs"] == [[0, 1, "AIRBORNE", ""], [2, 2, "HIDDEN", ""], [3, 4, "HELD", "LEFT"]]
    assert second["balls"][0]["runs"] == [[100, 100, "AIRBORNE", ""], [101, 101, "PREDICTED", ""],
                                          [102, 102, "AIRBORNE", ""]]
    link = payload["links"][0]
    assert link["link_key"] == "0:1>2" and link["label"] == "" and link["cost"] == 9.5
    assert payload["link_counts"] == {"hidden": 1}


def test_labels_round_trip_and_show_up_in_the_payload(tmp_path):
    root = write_identity_dir(tmp_path)
    store = LabelStore(root / "labels.csv")
    row = {"segment_index": "0", "source_track_id": "1", "target_track_id": "2"}
    store.save(link_key(row), {"label": "wrong", "note": "it was the other ball", "video": "clip"})
    reloaded = LabelStore(root / "labels.csv")
    assert reloaded.rows["0:1>2"]["note"] == "it was the other ball"
    assert reloaded.counts() == {"correct": 0, "wrong": 1, "unclear": 0}
    payload = build_payload(root, reloaded, "clip")
    assert payload["links"][0]["label"] == "wrong"
    assert payload["label_counts"]["wrong"] == 1
