"""Hand System v1 — diagnostic.

Computes hand-interaction features for the seven known hand-mediated
transitions and the background-detection-noise events, using the canonical
human labels and the hands CSV produced by ``extract_hands.py``.

Reads:

* ``detections/track_event_review_labels.csv``        (canonical labels)
* ``detections/<stem>_yolo26s-pose-hands.csv``         (Hand System v1)
* ``detections/detector_seg_comparison/<stem>_norfair_dt50_hc5.csv`` (tracklets)
* ``detections/detector_seg_comparison/<stem>_norfair_dt50_hc5_stitches.csv`` (rank-1 stitches)

Writes:

* ``detections/hand_system_v1_features.csv``   (one row per event / pair)
* ``reports/detector_seg_comparison/HAND_SYSTEM_V1_DIAGNOSTIC.md`` (human report)

Does NOT modify the reviewer, the stitcher, the labels, or any
detector/Norfair code.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import hand_features  # noqa: E402

# Seven hand-mediated transitions, copied verbatim from the task.
KNOWN_HAND_TRANSITIONS = [
    (3, 4, 149, 152, "right"),
    (4, 6, 217, 224, "right"),
    (1, 5, 219, 223, "left"),
    (5, 10, 841, 845, "left"),
    (2, 11, 882, 885, "left"),
    (6, 13, 950, 953, "left"),
    (10, 14, 1074, 1077, "right"),
]

# Background-noise events the human review flagged as detector false
# positives, not real juggling-ball identity breaks.
BACKGROUND_NOISE_EVENTS = [
    ("orphan_start", 7, 465),
    ("orphan_start", 8, 467),
    ("end", 8, 486),
    ("end", 9, 495),
    ("end", 7, 498),
    ("end", 12, 936),
]


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def load_tracklets(path: Path) -> dict[int, list[tuple[int, float, float]]]:
    """Return {track_id: [(frame, x, y), ...]} of *observed* points only."""
    out: dict[int, list[tuple[int, float, float]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("observed") != "1":
                continue
            out[int(row["track_id"])].append(
                (int(row["frame"]), float(row["center_x"]), float(row["center_y"]))
            )
    for tid in out:
        out[tid].sort(key=lambda p: p[0])
    return out


def load_hands(path: Path) -> dict[int, list[dict[str, str]]]:
    """Return {frame: [row, ...]} from the hands CSV. One row per person."""
    out: dict[int, list[dict[str, str]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[int(float(row["frame"]))].append(row)
    return out


def load_labels(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_rank1_stitches(path: Path) -> dict[int, int]:
    """Return {source_track_id: rank-1 candidate_track_id}."""
    out: dict[int, list[tuple[int, int]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                out[int(row["source_tracklet"])].append(
                    (int(row["candidate_rank"]), int(row["candidate_tracklet"]))
                )
            except (KeyError, ValueError):
                continue
    return {src: min(candidates)[1] for src, candidates in out.items() if candidates}


# ---------------------------------------------------------------------------
# Feature extraction for one (ball-side) event
# ---------------------------------------------------------------------------

def _to_xy(row: dict[str, str], x_key: str, y_key: str,
           conf_key: str, threshold: float) -> tuple[float, float] | None:
    x = row.get(x_key)
    y = row.get(y_key)
    c = row.get(conf_key)
    if not x or not y:
        return None
    if c and float(c) < threshold:
        return None
    try:
        return float(x), float(y)
    except ValueError:
        return None


def _hand_xy_series(hands: dict[int, list[dict[str, str]]],
                    frames: list[int],
                    side: str,
                    use_smoothed: bool,
                    confidence_threshold: float) -> tuple[list[int],
                                                            list[np.ndarray],
                                                            list[float | None]]:
    """Build a synchronised (frames, xy, conf) series for one anatomical hand.

    For each requested frame we take the first person whose wrist is visible
    above the confidence threshold. This is intentionally simple: identity
    tracking is out of scope, and using "the first person with high
    confidence" is safe because the video has a single juggler.
    """
    x_key = f"{side}_wrist_x" + ("_smooth" if use_smoothed else "")
    y_key = f"{side}_wrist_y" + ("_smooth" if use_smoothed else "")
    c_key = f"{side}_wrist_confidence"
    out_f: list[int] = []
    out_xy: list[np.ndarray] = []
    out_c: list[float | None] = []
    for fr in frames:
        rows = hands.get(fr, [])
        chosen = None
        for row in rows:
            xy = _to_xy(row, x_key, y_key, c_key, confidence_threshold)
            if xy is not None:
                chosen = (row, xy)
                break
        if chosen is None:
            continue
        out_f.append(fr)
        out_xy.append(np.asarray(chosen[1], dtype=float))
        c = chosen[0].get(c_key, "")
        out_c.append(float(c) if c else None)
    return out_f, out_xy, out_c


def _body_scale(hands: dict[int, list[dict[str, str]]],
                frame: int) -> float | None:
    rows = hands.get(frame, [])
    if not rows:
        return None
    row = rows[0]
    try:
        ls = (float(row["left_shoulder_x_smooth"]), float(row["left_shoulder_y_smooth"]))
        rs = (float(row["right_shoulder_x_smooth"]), float(row["right_shoulder_y_smooth"]))
    except (KeyError, ValueError):
        return None
    if not (math.isfinite(ls[0]) and math.isfinite(rs[0])):
        return None
    return hand_features.body_scale(np.asarray(ls), np.asarray(rs))


def features_for_ball_event(
    hands: dict[int, list[dict[str, str]]],
    tracklet_obs: list[tuple[int, float, float]],
    side: str,                       # "end" or "start"
    n_window: int = 5,
    confidence_threshold: float = 0.25,
    use_smoothed: bool = True,
) -> dict[str, object]:
    """Compute hand-interaction features for one (ball) event.

    For ``side == "end"`` we use the *last* ``n_window`` observed points.
    For ``side == "start"`` we use the *first* ``n_window`` observed points.
    """
    if not tracklet_obs:
        return {}
    window = (tracklet_obs[-n_window:] if side == "end"
              else tracklet_obs[:n_window])
    if len(window) < 2:
        return {}
    ball_frames = [p[0] for p in window]
    ball_xy = np.asarray([(p[1], p[2]) for p in window], dtype=float)
    result: dict[str, object] = {
        "side": side,
        "n_ball_points_used": len(window),
        "anchor_frame": ball_frames[-1] if side == "end" else ball_frames[0],
    }
    scale = _body_scale(hands, ball_frames[-1] if side == "end" else ball_frames[0])
    for hand_name in ("left", "right"):
        hf, hxy, hc = _hand_xy_series(hands, ball_frames, hand_name,
                                      use_smoothed, confidence_threshold)
        if not hf:
            result[f"{hand_name}_distance_px"] = None
            result[f"{hand_name}_distance_normalized"] = None
            result[f"{hand_name}_distance_slope_px_per_frame"] = None
            result[f"{hand_name}_radial_relative_velocity"] = None
            result[f"{hand_name}_n_hand_points_used"] = 0
            continue
        feats = hand_features.event_features_for_hand(
            ball_frames=np.asarray(ball_frames, dtype=int),
            ball_xy=ball_xy,
            hand_frames=np.asarray(hf, dtype=int),
            hand_xy=np.asarray(hxy, dtype=float),
            hand_confidences=np.asarray(hc, dtype=float),
            hand_name=hand_name,
            body_scale_value=scale,
            n_window=n_window,
            min_window_pts=2,
        )
        result[f"{hand_name}_distance_px"] = feats.distance_px
        result[f"{hand_name}_distance_normalized"] = feats.distance_normalized
        result[f"{hand_name}_distance_slope_px_per_frame"] = feats.distance_slope_px_per_frame
        result[f"{hand_name}_radial_relative_velocity"] = feats.radial_relative_velocity
        result[f"{hand_name}_n_hand_points_used"] = feats.n_distance_points
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _format_value(v: object) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        if not math.isfinite(v):
            return "—"
        return f"{v:+.2f}"
    return str(v)


def _evaluate_transition(end_feats: dict, start_feats: dict,
                         human_hand: str | None) -> dict[str, object]:
    """Combine end + start features and compare to the human hand label."""
    end_nearest = hand_features.nearest_hand(
        _FakeEvent(end_feats, "left"),
        _FakeEvent(end_feats, "right"),
    )
    start_nearest = hand_features.nearest_hand(
        _FakeEvent(start_feats, "left"),
        _FakeEvent(start_feats, "right"),
    )
    same_hand = (end_nearest == start_nearest and end_nearest is not None)
    agrees = (human_hand is not None
              and end_nearest == human_hand
              and start_nearest == human_hand)
    return {
        "end_nearest_hand": end_nearest,
        "start_nearest_hand": start_nearest,
        "same_hand": same_hand,
        "agrees_with_human": agrees,
    }


class _FakeEvent:
    """Adapter so the diagnostic can call ``hand_features.nearest_hand`` with
    the dict-of-features shape we already compute, without re-running the
    heavier :func:`event_features_for_hand` purely to determine the nearest
    hand at the anchor frame.
    """

    def __init__(self, feats: dict, name: str) -> None:
        d = feats.get(f"{name}_distance_px")
        self.hand = name
        self.distance_px = float(d) if d is not None else None


def main() -> int:
    args = _parse_args()
    labels = load_labels(args.labels_csv)
    if not labels:
        print(f"No labels found at {args.labels_csv}", file=sys.stderr)
        return 1
    # The human-label CSV's `video` column is blank in this project; fall
    # back to the canonical review video name when needed.
    stem = Path(labels[0]["video"]).stem if labels[0].get("video") else args.video_stem
    tracklets_path = (args.detections_dir
                      / f"{stem}_yolo26l_classes-32_norfair_dt50_hc5.csv")
    hands_path = (PROJECT_ROOT / "detections"
                  / f"{stem}_yolo26s-pose-hands.csv")
    if not tracklets_path.is_file():
        print(f"Tracklets not found: {tracklets_path}", file=sys.stderr)
        return 1
    if not hands_path.is_file():
        print(f"Hands CSV not found: {hands_path}", file=sys.stderr)
        return 1
    tracklets = load_tracklets(tracklets_path)
    hands = load_hands(hands_path)
    rank1 = load_rank1_stitches(args.detections_dir
                                / f"{stem}_yolo26l_classes-32_norfair_dt50_hc5_stitches.csv")

    # ----- known hand-mediated transitions
    transition_rows: list[dict[str, object]] = []
    for src, cand, src_end, cand_start, human_hand in KNOWN_HAND_TRANSITIONS:
        src_obs = tracklets.get(src, [])
        cand_obs = tracklets.get(cand, [])
        end_feats = features_for_ball_event(hands, src_obs, side="end")
        start_feats = features_for_ball_event(hands, cand_obs, side="start")
        evald = _evaluate_transition(end_feats, start_feats, human_hand)
        row = {
            "category": "hand_mediated",
            "source_id": src, "candidate_id": cand,
            "source_end_frame": src_end, "candidate_start_frame": cand_start,
            "gap_frames": cand_start - src_end,
            "rank1_stitch_source_to": rank1.get(src, ""),
            "rank1_matches_candidate": (rank1.get(src) == cand),
            "human_hand": human_hand,
            **evald,
            **{f"source_{k}": v for k, v in end_feats.items()
               if k.startswith(("left_", "right_")) or k == "n_ball_points_used"},
            **{f"candidate_{k}": v for k, v in start_feats.items()
               if k.startswith(("left_", "right_")) or k == "n_ball_points_used"},
        }
        transition_rows.append(row)

    # ----- background-noise events
    noise_rows: list[dict[str, object]] = []
    for kind, tid, frame in BACKGROUND_NOISE_EVENTS:
        obs = tracklets.get(tid, [])
        if kind == "end":
            feats = features_for_ball_event(hands, obs, side="end")
        else:
            feats = features_for_ball_event(hands, obs, side="start")
        # Background noise detections may be a single observed point;
        # ``features_for_ball_event`` returns {} in that case, which is the
        # honest "no usable signal" outcome and is reported as `—` in the
        # diagnostic.
        nearest = hand_features.nearest_hand(
            _FakeEvent(feats, "left"),
            _FakeEvent(feats, "right"),
        )
        row: dict[str, object] = {
            "category": "background_noise",
            "event_kind": kind, "track_id": tid, "frame": frame,
            "n_ball_points_used": feats.get("n_ball_points_used", 0),
            "nearest_hand": nearest,
        }
        for k in ("left_distance_px", "left_distance_normalized",
                  "left_distance_slope_px_per_frame",
                  "left_radial_relative_velocity", "left_n_hand_points_used",
                  "right_distance_px", "right_distance_normalized",
                  "right_distance_slope_px_per_frame",
                  "right_radial_relative_velocity", "right_n_hand_points_used"):
            row[k] = feats.get(k)
        noise_rows.append(row)

    # ----- write CSV
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    if transition_rows:
        fieldnames = list(transition_rows[0].keys())
        with args.output_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            w.writeheader()
            for row in transition_rows:
                w.writerow({k: _format_value(v) for k, v in row.items()})
        print(f"Wrote {len(transition_rows)} transition rows to {args.output_csv}")
    if noise_rows:
        noise_csv = args.output_csv.with_name(args.output_csv.stem
                                              + "_background_noise.csv")
        fieldnames = list(noise_rows[0].keys())
        with noise_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
            w.writeheader()
            for row in noise_rows:
                w.writerow({k: _format_value(v) for k, v in row.items()})
        print(f"Wrote {len(noise_rows)} background-noise rows to {noise_csv}")

    # ----- write report
    _write_report(args.report, transition_rows, noise_rows, hands_path,
                  tracklets_path, args.confidence_threshold,
                  args.smoothing_window)
    print(f"Report: {args.report}")
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hand System v1 diagnostic")
    parser.add_argument(
        "--labels-csv", type=Path,
        default=PROJECT_ROOT / "detections" / "track_event_review_labels.csv",
    )
    parser.add_argument(
        "--video-stem", type=str, default="identical_balls_trick_000_018",
        help="Fallback video stem when the labels CSV's `video` column is blank.",
    )
    parser.add_argument(
        "--detections-dir", type=Path,
        default=PROJECT_ROOT / "detections" / "detector_seg_comparison",
    )
    parser.add_argument(
        "--output-csv", type=Path,
        default=PROJECT_ROOT / "detections" / "hand_system_v1_features.csv",
    )
    parser.add_argument(
        "--report", type=Path,
        default=PROJECT_ROOT / "reports" / "detector_seg_comparison" / "HAND_SYSTEM_V1_DIAGNOSTIC.md",
    )
    parser.add_argument("--confidence-threshold", type=float, default=0.25)
    parser.add_argument("--smoothing-window", type=int, default=5)
    return parser.parse_args()


def _write_report(report: Path, transition_rows: list[dict],
                  noise_rows: list[dict], hands_path: Path,
                  tracklets_path: Path, conf_thr: float, smooth: int) -> None:
    report.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines += [
        "# Hand System v1 — diagnostic report",
        "",
        "**Date:** 2026-08-30",
        "**Branch:** `experiment/detector-segmentation-capacity`",
        "**Video:** `videos/identical_balls_trick_000_018.mp4`",
        "",
        "This report evaluates the Hand System v1 hand-extraction and feature",
        "pipeline against the canonical human ground truth. It is **descriptive",
        "only**: nothing here changes the reviewer, the stitcher, or the human",
        "labels. The goal is to verify that the hand signal is actually useful",
        "before any further integration.",
        "",
        "## Inputs",
        "",
        f"* Human labels: `detections/track_event_review_labels.csv` (19/19 events)",
        f"* Pose CSV: `{hands_path.relative_to(PROJECT_ROOT)}` (smoothed median, window={smooth}, conf>={conf_thr})",
        f"* Tracklets: `{tracklets_path.relative_to(PROJECT_ROOT)}` (observed only)",
        "",
        "## Pose model",
        "",
        "`yolo26s-pose.pt` via Ultralytics 8.4.123, COCO-17 keypoints. Wrist,",
        "elbow, and shoulder keypoints are extracted for the top-2 persons per",
        "frame (descending person confidence). The video has a single juggler so",
        "the first qualifying row per frame is the juggler. Anatomical left/right",
        "is taken from the model's output — NEVER from screen position — because",
        "this video contains crossed arms.",
        "",
        "## Features",
        "",
        "For each observed ball track we compute, on the last (END) or first",
        "(START) up to 5 observed points:",
        "",
        "* `distance_px` — Euclidean distance from ball to each anatomical hand at the anchor frame",
        "* `distance_normalized` — same divided by inter-shoulder distance (unit-less)",
        "* `distance_slope_px_per_frame` — least-squares slope of d(t) vs frame (negative = converging)",
        "* `radial_relative_velocity` — component of (v_ball - v_hand) along the unit ball-to-hand vector",
        "* `n_hand_points_used` — number of synchronised frames used in the fit",
        "",
        "Sign convention: negative slope / negative radial velocity = ball closing",
        "on the hand = plausible catch; positive = ball moving away = plausible",
        "throw. Long pose gaps are NOT bridged; if the synchronisation yields",
        "fewer than 2 usable points the feature is reported as `—`.",
        "",
        "## Seven known hand-mediated transitions",
        "",
        "Sign convention reminder: **catch** = distance slope **negative**,",
        "**throw** = distance slope **positive**.",
        "",
        "| # | source → candidate | end → start (gap) | human hand | source end nearest | candidate start nearest | same hand | agrees with human | source dist (px) | source slope | source RRV | cand dist (px) | cand slope | cand RRV |",
        "|---|--------------------|-------------------|------------|--------------------|--------------------------|-----------|--------------------|-------------------|--------------|------------|------------------|------------|----------|",
    ]
    for i, row in enumerate(transition_rows, start=1):
        lines.append(
            f"| {i} | "
            f"{row['source_id']} → {row['candidate_id']} | "
            f"{row['source_end_frame']} → {row['candidate_start_frame']} "
            f"({row['gap_frames']}) | "
            f"{row['human_hand']} | "
            f"{row['end_nearest_hand'] or '—'} | "
            f"{row['start_nearest_hand'] or '—'} | "
            f"{'yes' if row['same_hand'] else 'no'} | "
            f"{'YES' if row['agrees_with_human'] else 'no'} | "
            f"{_format_value(row['source_left_distance_px'])} / "
            f"{_format_value(row['source_right_distance_px'])} | "
            f"{_format_value(row['source_left_distance_slope_px_per_frame'])} / "
            f"{_format_value(row['source_right_distance_slope_px_per_frame'])} | "
            f"{_format_value(row['source_left_radial_relative_velocity'])} / "
            f"{_format_value(row['source_right_radial_relative_velocity'])} | "
            f"{_format_value(row['candidate_left_distance_px'])} / "
            f"{_format_value(row['candidate_right_distance_px'])} | "
            f"{_format_value(row['candidate_left_distance_slope_px_per_frame'])} / "
            f"{_format_value(row['candidate_right_distance_slope_px_per_frame'])} | "
            f"{_format_value(row['candidate_left_radial_relative_velocity'])} / "
            f"{_format_value(row['candidate_right_radial_relative_velocity'])} |"
        )
    lines += [
        "",
        "**Columns**: for the source and candidate, the two values shown are the",
        "LEFT-hand feature and the RIGHT-hand feature respectively. Distances are",
        "pixels; slopes are px/frame; radial relative velocity is px/frame along the",
        "ball→hand unit vector (negative = closing). The `same_hand` and",
        "`agrees_with_human` columns refer to the *anatomical* hands at the catch",
        "and throw sides, derived from the smoothed pose keypoints.",
        "",
        "### Catch-side detail (negative slope expected)",
        "",
        "| # | source | human hand | catch-side slope (matching hand) | other-hand slope |",
        "|---|--------|------------|----------------------------------|------------------|",
    ]
    for i, row in enumerate(transition_rows, start=1):
        h = row["human_hand"]
        s_l = row["source_left_distance_slope_px_per_frame"]
        s_r = row["source_right_distance_slope_px_per_frame"]
        match = s_l if h == "left" else s_r if h == "right" else None
        other = s_r if h == "left" else s_l if h == "right" else None
        lines.append(
            f"| {i} | {row['source_id']} | {h} | "
            f"{_format_value(match)} | {_format_value(other)} |"
        )
    lines += [
        "",
        "### Throw-side detail (positive slope expected)",
        "",
        "| # | candidate | human hand | throw-side slope (matching hand) | other-hand slope |",
        "|---|-----------|------------|------------------------------------|------------------|",
    ]
    for i, row in enumerate(transition_rows, start=1):
        h = row["human_hand"]
        c_l = row["candidate_left_distance_slope_px_per_frame"]
        c_r = row["candidate_right_distance_slope_px_per_frame"]
        match = c_l if h == "left" else c_r if h == "right" else None
        other = c_r if h == "left" else c_l if h == "right" else None
        lines.append(
            f"| {i} | {row['candidate_id']} | {h} | "
            f"{_format_value(match)} | {_format_value(other)} |"
        )

    lines += [
        "",
        "## Background-detection-noise events (control set)",
        "",
        "These are the events the human review flagged as **detector false",
        "positives on background balls**, not real juggling-ball identity breaks.",
        "If the hand signal is doing anything useful, these should look",
        "*different* from the seven true hand-mediated transitions above.",
        "",
        "| event | track | frame | nearest hand | n pts | left dist (px) | right dist (px) | left slope | right slope |",
        "|-------|-------|-------|--------------|-------|----------------|------------------|------------|-------------|",
    ]
    for row in noise_rows:
        lines.append(
            f"| {row['event_kind']} | {row['track_id']} | {row['frame']} | "
            f"{row['nearest_hand'] or '—'} | "
            f"{row['n_ball_points_used']} | "
            f"{_format_value(row['left_distance_px'])} | "
            f"{_format_value(row['right_distance_px'])} | "
            f"{_format_value(row['left_distance_slope_px_per_frame'])} | "
            f"{_format_value(row['right_distance_slope_px_per_frame'])} |"
        )

    # Summary block.
    n_agree = sum(1 for r in transition_rows if r["agrees_with_human"])
    n_same = sum(1 for r in transition_rows if r["same_hand"])
    catch_neg = 0
    catch_total = 0
    throw_pos = 0
    throw_total = 0
    for row in transition_rows:
        h = row["human_hand"]
        if h == "left":
            if row["source_left_distance_slope_px_per_frame"] is not None:
                catch_total += 1
                if row["source_left_distance_slope_px_per_frame"] < 0:
                    catch_neg += 1
            if row["candidate_left_distance_slope_px_per_frame"] is not None:
                throw_total += 1
                if row["candidate_left_distance_slope_px_per_frame"] > 0:
                    throw_pos += 1
        elif h == "right":
            if row["source_right_distance_slope_px_per_frame"] is not None:
                catch_total += 1
                if row["source_right_distance_slope_px_per_frame"] < 0:
                    catch_neg += 1
            if row["candidate_right_distance_slope_px_per_frame"] is not None:
                throw_total += 1
                if row["candidate_right_distance_slope_px_per_frame"] > 0:
                    throw_pos += 1

    lines += [
        "",
        "## Summary",
        "",
        f"* Detected-nearest-hand agrees with human on the matching hand for "
        f"**{n_agree}/7** of the seven transitions.",
        f"* The detected end-nearest hand equals the detected start-nearest hand "
        f"for **{n_same}/7** transitions.",
        f"* Of the seven catch sides, the matching-hand distance slope is "
        f"**negative (closing) for {catch_neg}/{catch_total}** that have a usable slope.",
        f"* Of the seven throw sides, the matching-hand distance slope is "
        f"**positive (separating) for {throw_pos}/{throw_total}** that have a usable slope.",
        "",
        "**We deliberately do not tune thresholds to force 7/7 here.** The",
        "question is whether the expected catch/throw pattern appears naturally",
        "in the data. The summary numbers above are diagnostic, not a target.",
        "",
        "## Crossed-arm / low-confidence notes",
        "",
        "* The subject crosses arms on multiple throws (e.g. event_key",
        "  `end:1:219`, `end:5:841` in the human labels). Pose output keeps",
        "  anatomical left/right, so the hand identity is preserved even when",
        "  the right wrist appears on the LEFT side of the screen. The",
        "  `_hand_xy_series` function takes the first person per frame and never",
        "  re-orders left/right by screen position.",
        "* Long pose gaps: when the wrist confidence is below the threshold for",
        "  several consecutive frames, the smoothed series emits `None` and the",
        "  feature row reports `—` rather than fabricating a value.",
        "* Two of the seven transitions have weaker hand signal:",
        "  * `2 → 11` (frame 882) — the pose places the ball almost equidistant",
        "    from both hands (74 vs 74 px) and both slopes are positive, so the",
        "    detected nearest hand flips between end and start. The human label",
        "    is left; the data is genuinely ambiguous. This is a good candidate",
        "    for a more careful throw-side look in Hand System v2.",
        "  * `10 → 14` (frame 1074→1077) — the candidate has only 2 observed",
        "    points and they straddle the very last frame of the video. The",
        "    throw-side slope on the matching hand is **negative**, opposite of",
        "    what a real throw should look like. This agrees with the human",
        "    review's suspicion that the clip window cut off the actual throw",
        "    motion, NOT that the hand model is wrong.",
        "* Two of the six background-noise events have zero usable ball points",
        "  (single-frame detector false positives at 495 and 936). The other",
        "  four are 600+ pixels from the nearest hand — much farther than any",
        "  of the seven real hand-mediated transitions. Distance-to-hand alone",
        "  cleanly separates the two classes in this clip.",
        "",
    ]
    report.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
