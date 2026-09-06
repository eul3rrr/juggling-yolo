from pathlib import Path
import importlib.util
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT_ROOT / "scripts" / "render_demo_videos.py"


def load_script():
    spec = importlib.util.spec_from_file_location("render_demo_videos", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_hid_union_is_transitive_and_deterministic():
    module = load_script()
    mapping = module.build_hid_mapping({1, 3, 4, 5, 6, 10, 13, 99}, [(3, 4), (4, 6), (6, 13), (1, 5), (5, 10)])
    assert mapping[3] == mapping[4] == mapping[6] == mapping[13]
    assert mapping[1] == mapping[5] == mapping[10]
    assert mapping[1] != mapping[3] != mapping[99]
    assert mapping == module.build_hid_mapping(list(reversed(sorted({1, 3, 4, 5, 6, 10, 13, 99}))), [(5, 10), (6, 13), (4, 6), (3, 4), (1, 5)])


def test_observed_filter_and_continuity_exclude_predictions():
    module = load_script()
    points = [module.TrackPoint(1, 1, 1, 0.9, True), module.TrackPoint(2, 2, 2, 0.0, False), module.TrackPoint(3, 3, 3, 0.8, True)]
    assert [point.frame for point in module.observed_points(points)] == [1, 3]
    history = module.track_continuity({7: points}, 3, trail_length=2)
    assert [point.frame for point in history[7]] == [1, 3]


def test_observed_trail_segments_never_cross_a_missing_frame():
    module = load_script()
    points = [
        module.TrackPoint(10, 1, 1, 0.9, True),
        module.TrackPoint(11, 2, 2, 0.8, True),
        module.TrackPoint(13, 4, 4, 0.7, True),
    ]
    segments = [(first.frame, second.frame) for first, second in zip(points, points[1:]) if second.frame == first.frame + 1]
    assert segments == [(10, 11)]


def test_bezier_and_dashes_have_endpoints_and_non_linear_geometry():
    module = load_script()
    points = module.cubic_bezier_points((0, 0), (100, 0), offset=20, samples=9)
    assert points[0] == (0, 0)
    assert points[-1] == (100, 0)
    assert max(abs(y) for _, y in points[1:-1]) > 0
    segments = module.dashed_polyline(points, dash=10, gap=5)
    assert segments
    assert segments[0][0] == (0, 0)


def test_event_windows_center_on_target_start():
    module = load_script()
    bridge = module.Bridge(3, 4, 149, 152, (1, 2), (3, 4), "RIGHT")
    indexed = module.event_windows([bridge], 200, window=2)
    assert sorted(indexed) == [150, 151, 152, 153, 154]


def test_canonical_hand_associations_match_selected_tracklet_endpoints():
    module = load_script()
    tracklets = module.load_tracklets(module.DEFAULT_TRACKLETS)
    associations = module.load_associations(module.DEFAULT_ASSOCIATIONS)
    events = module.load_events(module.DEFAULT_EVENTS)
    bridges = module.build_bridges(tracklets, associations, events)
    assert [(bridge.source_track, bridge.target_track) for bridge in bridges] == [
        (3, 4), (1, 5), (4, 6), (5, 10), (2, 11), (6, 13)
    ]
    mapping = module.build_hid_mapping(tracklets, [(bridge.source_track, bridge.target_track) for bridge in bridges])
    assert mapping[3] == mapping[4] == mapping[6] == mapping[13]
    assert mapping[1] == mapping[5] == mapping[10]
    assert mapping[2] == mapping[11]


def test_ffmpeg_command_has_required_site_video_flags(tmp_path: Path):
    module = load_script()
    command = module.ffmpeg_command(tmp_path / "demo.mp4", 1280, 720, 60000 / 1001)
    assert "libx264" in command
    assert "yuv420p" in command
    assert "+faststart" in command
    assert "-an" in command
    assert command[command.index("-f") + 1] == "rawvideo"
    assert command[command.index("-pix_fmt") + 1] == "bgr24"
    assert command[command.index("-crf") + 1] == "23"
    assert command[command.index("-bf") + 1] == "0"


def test_cli_rejects_invalid_crf():
    module = load_script()
    with pytest.raises(SystemExit):
        module.parse_args(["--crf", "52"])
