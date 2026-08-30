from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import render_hand_boundaries as rh


def test_nearest_available_hand_selection():
    assert rh.nearest_hand((10, 0), {"LEFT": (0, 0), "RIGHT": (100, 0)}) == ("LEFT", 10.0)
    assert rh.nearest_hand((10, 0), {"LEFT": None, "RIGHT": (100, 0)}) == ("RIGHT", 90.0)
    assert rh.nearest_hand((10, 0), {"LEFT": None, "RIGHT": None}) is None


def test_normalized_proximity_radii():
    assert rh.proximity_radii(200.0) == (70.0, 140.0, "normalized")


def test_raw_fallback_proximity_radii():
    assert rh.proximity_radii(None) == (60.0, 130.0, "raw")
    assert rh.proximity_radii(4.0) == (60.0, 130.0, "raw")


def test_normalized_distance_takes_priority_over_raw_fallback():
    assert rh.proximity_band(0.5, 50.0) == "POSSIBLE"
    assert rh.proximity_band(None, 50.0) == "VERY_NEAR"


def test_missing_wrist_is_safe():
    assert rh.wrist_xy(None) is None
    assert rh.wrist_xy((1.0, 2.0)) == (1.0, 2.0)


def test_assessment_grouping_has_one_logical_boundary_with_two_hands(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("track_id,boundary_type,boundary_frame,hand,hand_evidence,post_contact,preferred_hand,ambiguous,evidence_reason\n1,END,9,LEFT,1,0,LEFT,0,very_near\n1,END,9,RIGHT,0,0,LEFT,0,far\n")
    grouped = rh.load_assessments(p)
    assert list(grouped) == [("END", 1, 9)]
    assert set(grouped[("END", 1, 9)]) == {"LEFT", "RIGHT"}


def test_boundary_event_lookup_uses_plus_minus_15_frames():
    events = rh.index_boundary_events({("END", 3, 149): {"track_id": "3"}})
    assert events(134) == [("END", 3, 149)]
    assert events(164) == [("END", 3, 149)]
    assert events(165) == []


def test_verdict_display_comes_from_csv_row():
    row = {"hand_evidence": "0", "post_contact": "0", "preferred_hand": "", "ambiguous": "0", "evidence_reason": "possible"}
    assert rh.verdict_text(row) == "HAND: no (possible)"


def test_ffmpeg_command_is_browser_compatible():
    command = rh.ffmpeg_command(1280, 720, 60.0, Path("out.mp4"))
    assert "libx264" in command
    assert "yuv420p" in command
    assert "+faststart" in command
