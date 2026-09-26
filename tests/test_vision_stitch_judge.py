from pathlib import Path
import csv
import json
import sys

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.vision_stitch.judge import (JudgeClient, JudgeConfig, event_slug, extract_json,  # noqa: E402
                                     load_manifests, parse_verdict, resolve_api_key,
                                     result_is_current, run_judge, write_results_csv)

LETTERS = ["A", "B"]


def test_event_slug_is_filesystem_safe():
    assert event_slug("end:66:2279") == "end_66_2279"
    assert event_slug("a/b c") == "a_b_c"


def test_extract_json_handles_fences_and_prose():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure!\n{"a": 1}\nHope that helps.') == {"a": 1}
    assert extract_json("no json here") is None
    assert extract_json(None) is None


def test_parse_verdict_accepts_a_stitch_choice():
    verdict = parse_verdict('{"decision":"stitch","candidate":"b","confidence":1.4,"reason":" continuous"}', LETTERS)
    assert verdict["parse_ok"] is True
    assert verdict["decision"] == "stitch"
    assert verdict["candidate_letter"] == "B"
    assert verdict["confidence"] == 1.0            # clamped
    assert verdict["reason"] == "continuous"


def test_parse_verdict_requires_a_candidate_for_stitch():
    verdict = parse_verdict('{"decision":"stitch","confidence":0.5}', LETTERS)
    assert verdict["parse_ok"] is False
    assert "without a candidate" in verdict["error"]


def test_parse_verdict_rejects_unknown_candidate_and_decision():
    assert parse_verdict('{"decision":"stitch","candidate":"Z"}', LETTERS)["parse_ok"] is False
    assert parse_verdict('{"decision":"maybe"}', LETTERS)["parse_ok"] is False


def test_parse_verdict_drops_candidate_when_not_stitching():
    verdict = parse_verdict('{"decision":"none","candidate":"A","confidence":0.9}', LETTERS)
    assert verdict["parse_ok"] is True
    assert verdict["candidate_letter"] is None


def test_parse_verdict_reports_missing_json():
    empty = parse_verdict(None, LETTERS)
    assert empty["parse_ok"] is False
    assert "empty answer" in empty["error"]
    prose = parse_verdict("I cannot decide from these frames.", LETTERS)
    assert prose["parse_ok"] is False
    assert prose["error"] == "no JSON object in answer"


def test_resolve_api_key_prefers_an_explicit_value():
    assert resolve_api_key("explicit-key") == "explicit-key"


class LadderClient(JudgeClient):
    """Exercises the reasoning-effort ladder without touching the network."""

    def __init__(self, config, first_empty=True):
        super().__init__(config, "test-key")
        self.first_empty = first_empty
        self.efforts_used = []

    def _attempt(self, content, letters, effort):
        self.efforts_used.append(effort)
        if self.first_empty and effort == self.config.reasoning_effort:
            return dict(raw_text=None, reasoning_effort=effort, usage={}, latency_s=0.1, error=None,
                        verdict=parse_verdict(None, letters))
        text = '{"decision":"none","confidence":0.5}'
        return dict(raw_text=text, reasoning_effort=effort, usage={}, latency_s=0.1, error=None,
                    verdict=parse_verdict(text, letters))


def test_client_falls_back_to_a_cheaper_reasoning_level_on_an_empty_answer():
    config = JudgeConfig(model="test-model")
    assert config.efforts() == ["low", "minimal"]
    client = LadderClient(config)
    outcome = client.judge([{"type": "text", "text": "x"}], LETTERS)
    assert outcome["verdict"]["parse_ok"] is True
    assert outcome["reasoning_effort"] == "minimal"
    assert client.efforts_used == ["low", "minimal"]


def test_client_does_not_fall_back_when_the_first_attempt_succeeds_or_errors():
    config = JudgeConfig(model="test-model")
    ok_client = LadderClient(config, first_empty=False)
    assert ok_client.judge([], LETTERS)["reasoning_effort"] == "low"
    assert ok_client.efforts_used == ["low"]
    assert JudgeConfig(model="m", fallback_reasoning_effort="").efforts() == ["low"]
    assert JudgeConfig(model="m", reasoning_effort="minimal").efforts() == ["minimal"]


class FakeClient:
    """Deterministic stand-in for the OpenRouter client."""

    def __init__(self, answer=None, fail=False):
        self.answer = answer or '{"decision":"stitch","candidate":"A","confidence":0.8,"reason":"test"}'
        self.fail = fail
        self.calls = 0

    def judge(self, content, letters):
        self.calls += 1
        if self.fail:
            return dict(raw_text=None, verdict=parse_verdict(None, letters), usage={}, latency_s=0.1, error="boom")
        return dict(raw_text=self.answer, verdict=parse_verdict(self.answer, letters),
                    usage=dict(prompt_tokens=100, completion_tokens=10, reasoning_tokens=5, cost_usd=0.001),
                    latency_s=1.5, error=None)


def write_manifest(events_root: Path, event_key: str, letters=("A", "B")) -> Path:
    slug = event_slug(event_key)
    directory = events_root / slug
    directory.mkdir(parents=True)
    (directory / "manifest.json").write_text(json.dumps({
        "event_key": event_key, "prompt_version": "v1", "segment_index": 0,
        "window_frames": 30, "top_k": len(letters),
        "video": {"path": "/tmp/none.mp4", "fps": 60.0, "frame_count": 1000, "width": 1920, "height": 1080},
        "source": {"track_id": 66, "last_frame": 100, "last_x": 1.0, "last_y": 2.0, "last_seconds": 1.667,
                   "last_confidence": 0.9, "observed_len": 20, "velocity_x": 1.0, "velocity_y": 0.0},
        "candidates": [{"letter": letter, "track_id": 70 + i, "first_frame": 110 + i, "first_x": 1.0,
                        "first_y": 1.0, "first_confidence": 0.8, "observed_len": 5, "gap_frames": 10 + i,
                        "gap_seconds": 0.17, "predicted_x": 1.0, "predicted_y": 1.0, "prediction_error": 3.0,
                        "rank": i + 1} for i, letter in enumerate(letters)],
        "cv_rank1": {"track_id": 70, "prediction_error": 3.0, "gap_frames": 10},
        "images": [],
    }) + "\n")
    return directory


def test_run_judge_writes_results_and_resumes(tmp_path):
    events_root, results_root = tmp_path / "events", tmp_path / "results"
    write_manifest(events_root, "end:66:100")
    write_manifest(events_root, "end:67:100")
    client = FakeClient()
    config = JudgeConfig(model="test-model")
    stats = run_judge(events_root, results_root, client, config, concurrency=2)
    assert stats["judged"] == 2 and stats["skipped_current"] == 0
    assert (results_root / "end_66_100.json").is_file()
    rows = list(csv.DictReader((results_root / "results.csv").open()))
    assert len(rows) == 2
    assert rows[0]["decision"] == "stitch" and rows[0]["candidate_letter"] == "A"
    assert rows[0]["candidate_track_id"] == "70"
    assert rows[0]["cost_usd"] == "0.001"
    # second run: everything already current
    stats2 = run_judge(events_root, results_root, client, config, concurrency=2)
    assert stats2["judged"] == 0 and stats2["skipped_current"] == 2
    assert client.calls == 2
    # forcing re-judges
    stats3 = run_judge(events_root, results_root, client, config, concurrency=2, force=True)
    assert stats3["judged"] == 2 and client.calls == 4


def test_run_judge_counts_parse_failures_and_errors(tmp_path):
    events_root, results_root = tmp_path / "events", tmp_path / "results"
    write_manifest(events_root, "end:66:100")
    stats = run_judge(events_root, results_root, FakeClient(fail=True), JudgeConfig(model="m"), concurrency=1)
    assert stats["judged"] == 1
    assert stats["parse_failures"] == 1
    assert stats["errors"] == 1
    rows = list(csv.DictReader((results_root / "results.csv").open()))
    assert rows[0]["parse_ok"] == "False"
    assert rows[0]["error"] == "boom"


def test_result_is_current_requires_matching_model_and_parse(tmp_path):
    manifest = {"prompt_version": "v1"}
    config = JudgeConfig(model="m")
    assert result_is_current({"model": "m", "prompt_version": "v1", "verdict": {"parse_ok": True}}, manifest, config)
    assert not result_is_current({"model": "other", "prompt_version": "v1", "verdict": {"parse_ok": True}}, manifest, config)
    assert not result_is_current({"model": "m", "prompt_version": "v2", "verdict": {"parse_ok": True}}, manifest, config)
    assert not result_is_current({"model": "m", "prompt_version": "v1", "verdict": {"parse_ok": False}}, manifest, config)


def test_load_manifests_and_results_csv_are_sorted(tmp_path):
    events_root, results_root = tmp_path / "events", tmp_path / "results"
    write_manifest(events_root, "end:68:100")
    write_manifest(events_root, "end:66:100")
    assert [m["event_key"] for m in load_manifests(events_root)] == ["end:66:100", "end:68:100"]
    run_judge(events_root, results_root, FakeClient(), JudgeConfig(model="m"), concurrency=1)
    path = write_results_csv(results_root, load_manifests(events_root))
    rows = list(csv.DictReader(path.open()))
    assert [r["event_key"] for r in rows] == ["end:66:100", "end:68:100"]
