from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import render_hand_stitches as rs


def test_accepted_association_chains_are_transitive():
    links = [(3, 4), (4, 6), (6, 13), (1, 5), (5, 10)]
    chains = rs.derive_display_chains(links, range(1, 15))
    assert chains[3] == chains[4] == chains[6] == chains[13]
    assert chains[1] == chains[5] == chains[10]


def test_same_hand_chain_tracks_share_display_identity():
    mapping = rs.assign_display_ids([(3, 4), (4, 6)], range(1, 7))
    assert mapping[3] == mapping[4] == mapping[6]


def test_unrelated_tracklets_do_not_share_display_identity():
    mapping = rs.assign_display_ids([(3, 4)], range(1, 7))
    assert len({mapping[1], mapping[2], mapping[3], mapping[4], mapping[5], mapping[6]}) == 5
    assert mapping[1] != mapping[3]


def test_ambiguous_pending_identity_is_represented_once():
    parsed = rs.parse_pending("T2:{LEFT,RIGHT};T5:{LEFT}")
    assert parsed == [(2, "{LEFT,RIGHT}"), (5, "{LEFT}")]
    assert [x[0] for x in parsed].count(2) == 1


def test_state_trace_pending_parsing():
    assert rs.parse_trace_pending("T2:{LEFT,RIGHT};T5:{LEFT}") == [(2, "{LEFT,RIGHT}"), (5, "{LEFT}")]
    assert rs.parse_trace_pending("") == []


def test_accepted_stitch_lookup_by_target_frame_and_track():
    rows = [{"target_track_id":"10", "target_start_frame":"845", "source_track_id":"5", "resolved_hand":"LEFT", "match_rule":"FIFO"}]
    lookup = rs.index_associations(rows)
    assert lookup[(10, 845)]["source_track_id"] == "5"


def test_unmatched_exit_lookup():
    rows = [{"track_id":"14", "boundary_frame":"1077", "event_type":"HAND_EXIT", "reason":"NO_COMPATIBLE_PENDING_SOURCE"}]
    lookup = rs.index_unmatched(rows)
    assert lookup[(14, 1077)]["reason"] == "NO_COMPATIBLE_PENDING_SOURCE"


def test_video_start_exit_reason_rendering():
    assert "video start" in rs.status_for_unmatched("VIDEO_START_EXIT").lower()


def test_video_end_pending_reason_rendering():
    assert "video end" in rs.status_for_unmatched("VIDEO_END_PENDING_ENTRY").lower()


def test_ffmpeg_command_uses_browser_encoding():
    cmd = rs.ffmpeg_command(1280, 720, 59.94, Path("out.mp4"))
    assert "libx264" in cmd and "yuv420p" in cmd and "+faststart" in cmd
