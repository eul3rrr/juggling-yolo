from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import hand_boundaries as hb


def pts(frames, xs=None, ys=None):
    xs = xs or [0.0] * len(frames)
    ys = ys or [0.0] * len(frames)
    return [hb.BoundaryPoint(f, x, y) for f, x, y in zip(frames, xs, ys)]


def hands(frames, left=(0.0, 0.0), right=(1000.0, 1000.0), scale: float | None = 100.0):
    return {f: {"left": left, "right": right, "body_scale": scale,
                "left_confidence": 1.0, "right_confidence": 1.0}
            for f in frames}


def test_start_uses_first_observed_samples_only():
    b = hb.assess_boundary(1, "START", pts([2, 3, 4, 5, 6, 100], ys=[1, 2, 3, 4, 5, 999]), hands([2,3,4,5,6,100]))
    assert b.boundary_frame == 2
    assert b.hand_results["LEFT"].n_synchronized == 5


def test_end_uses_last_observed_samples_only():
    b = hb.assess_boundary(1, "END", pts([2, 3, 4, 5, 6, 100], ys=[1, 2, 3, 4, 5, 999]), hands([2,3,4,5,6,100]))
    assert b.boundary_frame == 100
    assert b.hand_results["LEFT"].endpoint_distance_px == 999
    assert b.hand_results["LEFT"].recent_min_distance_px == 2


def test_boundary_side_body_scale_does_not_leak_from_other_side():
    p = pts([1, 2, 3, 4, 5, 6], ys=[0, 0, 0, 0, 0, 0])
    h = hands(range(1, 7), left=(0, 0), right=None, scale=None)
    h[1]["body_scale"] = 100.0
    start = hb.assess_boundary(1, "START", p, h)
    end = hb.assess_boundary(1, "END", p, h)
    assert start.hand_results["LEFT"].endpoint_distance_normalized == 0.0
    assert end.hand_results["LEFT"].endpoint_distance_normalized is None


def test_start_body_scale_does_not_use_end_side():
    p = pts([1, 2, 3, 4, 5, 6], ys=[0, 0, 0, 0, 0, 0])
    h = hands(range(1, 7), left=(0, 0), right=None, scale=None)
    h[6]["body_scale"] = 100.0
    start = hb.assess_boundary(1, "START", p, h)
    assert start.hand_results["LEFT"].endpoint_distance_normalized is None


def test_fewer_than_three_synchronized_samples_means_insufficient():
    b = hb.assess_boundary(1, "END", pts([1, 2, 3]), hands([1, 3]))
    assert b.hand_results["LEFT"].motion == "INSUFFICIENT"


def test_very_near_can_be_evidence_without_trend():
    b = hb.assess_boundary(1, "END", pts([1, 2]), hands([1, 2], left=(0, 0)))
    assert b.hand_results["LEFT"].proximity == "VERY_NEAR"
    assert b.hand_results["LEFT"].hand_evidence is True


def test_far_cannot_be_rescued_by_approach():
    b = hb.assess_boundary(1, "END", pts([1,2,3,4], ys=[1000, 800, 600, 400]), hands([1,2,3,4], left=(0,0)))
    assert b.hand_results["LEFT"].proximity == "FAR"
    assert b.hand_results["LEFT"].hand_evidence is False


def test_recent_very_close_end_can_use_post_contact_case():
    p = pts([1,2,3,4,5], ys=[60, 50, 40, 20, 100])
    b = hb.assess_boundary(1, "END", p, hands([1,2,3,4,5], left=(0,0), scale=200.0))
    assert b.hand_results["LEFT"].post_contact is True
    assert b.hand_results["LEFT"].hand_evidence is True


def test_ambiguous_sides_are_not_forced():
    p = pts([1,2,3,4,5], xs=[10]*5, ys=[10]*5)
    b = hb.assess_boundary(1, "END", p, hands([1,2,3,4,5], left=(0,0), right=(20,20)))
    assert b.eligible_hands == ("LEFT", "RIGHT")
    assert b.preferred_hand is None
    assert b.ambiguous is True


def test_only_observed_rows_are_loaded(tmp_path):
    path = tmp_path / "tracks.csv"
    path.write_text("frame,time_seconds,track_id,confidence,center_x,center_y,observed\n1,0,1,1,0,0,1\n2,0,1,1,9,9,0\n3,0,1,1,1,1,1\n")
    loaded = hb.load_observed_tracklets(path)
    assert [p.frame for p in loaded[1]] == [1, 3]
