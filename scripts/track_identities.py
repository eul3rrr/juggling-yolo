#!/usr/bin/env python3
"""Ball identities from Norfair tracklets: N balls, each airborne, held or hidden.

Per LosslessCut segment the tracklets are linked by free-flight arcs, by a shared
hand, or (expensively) across a gap nothing explains, and at most N identities are
chosen globally. The detector, Norfair and the hand modules are not changed; the
chain mapping uses the existing ``track_id,chain_id`` schema.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import hand_association as ha  # noqa: E402
from src.annotation.segments import parse_losslesscut_csv, segment_frame_bounds  # noqa: E402
from src.tracking.pipeline import SegmentResult, track_video  # noqa: E402
from src.tracking.tracklets import SegmentSpan, load_observed_tracklets  # noqa: E402

STATE_FIELDS = ["frame", "segment_index", "ball_id", "chain_id", "state", "hand",
                "x", "y", "position_source", "track_id"]
LINK_FIELDS = ["segment_index", "ball_id", "chain_id", "source_track_id", "target_track_id",
               "kind", "hand", "cost", "gap_frames", "source_end_frame", "target_start_frame",
               "source_end_seconds", "fit_rmse_px"]
DROPPED_FIELDS = ["segment_index", "track_id", "reason", "first_frame", "last_frame", "n_observed"]


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _fmt(value: float | None) -> str:
    return "" if value is None else f"{value:.3f}"


def video_properties(video: Path) -> tuple[float, int]:
    import cv2
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise SystemExit(f"Could not open video: {video}")
    fps = capture.get(cv2.CAP_PROP_FPS)
    count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.release()
    return fps, count


def build_spans(tracklets: dict, fps: float, frame_count: int | None,
                segments_csv: Path | None, only: list[int] | None) -> list[SegmentSpan]:
    last = max(t.last_frame for t in tracklets.values()) + 1
    count = frame_count or last
    if segments_csv is None:
        return [SegmentSpan(0, 0, count)]
    spans = [SegmentSpan(s.index, *segment_frame_bounds(s, fps, count))
             for s in parse_losslesscut_csv(segments_csv)]
    return [s for s in spans if not only or s.index in only]


def parse_per_segment(values: list[str] | None) -> dict[int, int]:
    out: dict[int, int] = {}
    for value in values or []:
        index, _, count = value.partition("=")
        out[int(index)] = int(count)
    return out


def collect_rows(results: list[SegmentResult], fps: float):
    states, links, dropped, mapping = [], [], [], []
    chain_id = 0
    for result in results:
        index = result.span.index
        infos = result.infos
        chain_of_ball: dict[int, int] = {}
        if result.solution is None:
            continue
        for ball_id, (path, path_links) in enumerate(
                zip(result.solution.paths, result.solution.links), start=1):
            chain_id += 1
            chain_of_ball[ball_id] = chain_id
            mapping += [{"track_id": tid, "chain_id": chain_id} for tid in path]
            for link in path_links:
                end = infos[link.source].tracklet.last_frame
                links.append({
                    "segment_index": index, "ball_id": ball_id, "chain_id": chain_id,
                    "source_track_id": link.source, "target_track_id": link.target,
                    "kind": link.kind, "hand": link.hand, "cost": f"{link.cost:.2f}",
                    "gap_frames": link.gap_frames, "source_end_frame": end,
                    "target_start_frame": infos[link.target].tracklet.first_frame,
                    "source_end_seconds": f"{end / fps:.3f}",
                    "fit_rmse_px": _fmt(link.fit_rmse_px),
                })
        for row in result.timeline:
            states.append({
                "frame": row.frame, "segment_index": index, "ball_id": row.ball_id,
                "chain_id": chain_of_ball[row.ball_id], "state": row.state, "hand": row.hand,
                "x": _fmt(row.x), "y": _fmt(row.y), "position_source": row.position_source,
                "track_id": "" if row.track_id is None else row.track_id,
            })
        for tid in result.solution.unused:
            t = infos[tid].tracklet
            dropped.append({"segment_index": index, "track_id": tid, "reason": "unassigned",
                            "first_frame": t.first_frame, "last_frame": t.last_frame,
                            "n_observed": t.n_observed})
        dropped += [{"segment_index": index, "track_id": tid, "reason": "clutter",
                     "first_frame": "", "last_frame": "", "n_observed": ""}
                    for tid in result.clutter]
    states.sort(key=lambda r: (r["frame"], r["ball_id"]))
    mapping.sort(key=lambda r: r["track_id"])
    return states, links, dropped, mapping


def summarize(results: list[SegmentResult], fps: float) -> dict:
    segments = []
    for result in results:
        solution = result.solution
        kinds = Counter(link.kind for links in solution.links for link in links) if solution else {}
        unused_frames = sum(result.infos[tid].tracklet.n_observed for tid in solution.unused) if solution else 0
        segments.append({
            "segment_index": result.span.index,
            "start_frame": result.span.start, "end_frame": result.span.end,
            "start_seconds": round(result.span.start / fps, 3),
            "accel_y_px_per_frame2": result.accel_y, "accel_source": result.accel_source,
            "ball_count": result.n_balls, "ball_count_source": result.n_balls_source,
            "simultaneous_tracklet_histogram": result.count_histogram,
            "identities": len(solution.paths) if solution else 0,
            "tracklets": len(result.infos) + len(result.clutter),
            "links": dict(kinds),
            "unassigned_tracklets": len(solution.unused) if solution else 0,
            "unassigned_observed_frames": unused_frames,
            "clutter_tracklets": len(result.clutter),
        })
    return {"fps": fps, "segments": segments}


def look_here(links: list[dict], limit: int) -> list[dict]:
    """Hidden links first, then the costliest of the rest: the likeliest mistakes."""
    ranked = sorted(links, key=lambda r: (r["kind"] != "hidden", -float(r["cost"])))
    return ranked[:limit]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tracklets", type=Path, required=True)
    p.add_argument("--hands", type=Path, default=None, help="pose-hands CSV from extract_hands.py")
    p.add_argument("--video", type=Path, default=None, help="read fps and frame count from the video")
    p.add_argument("--fps", type=float, default=None, help="required when --video is not given")
    p.add_argument("--segments", type=Path, default=None, help="LosslessCut CSV")
    p.add_argument("--only-segment", type=int, action="append", default=None)
    p.add_argument("--balls", type=int, default=None, help="ball count for every segment (default: estimated)")
    p.add_argument("--balls-in-segment", action="append", default=None, metavar="INDEX=COUNT")
    p.add_argument("--look-here", type=int, default=15, help="how many suspicious links to print")
    p.add_argument("--output-dir", type=Path, required=True)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.video is not None:
        fps, frame_count = video_properties(args.video)
    elif args.fps is not None:
        fps, frame_count = args.fps, None
    else:
        raise SystemExit("Give --video or --fps")
    tracklets = load_observed_tracklets(args.tracklets)
    hands = ha._load_hands_by_frame(args.hands) if args.hands else {}
    spans = build_spans(tracklets, fps, frame_count, args.segments, args.only_segment)
    results = track_video(tracklets, spans, fps, hands, args.balls,
                          parse_per_segment(args.balls_in_segment))
    states, links, dropped, mapping = collect_rows(results, fps)
    summary = summarize(results, fps)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    _write(args.output_dir / "ball_states.csv", STATE_FIELDS, states)
    _write(args.output_dir / "links.csv", LINK_FIELDS, links)
    _write(args.output_dir / "dropped_tracklets.csv", DROPPED_FIELDS, dropped)
    _write(args.output_dir / "chain_mapping.csv", ["track_id", "chain_id"], mapping)
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    for seg in summary["segments"]:
        accel = seg["accel_y_px_per_frame2"]
        print(f"segment {seg['segment_index']} @{seg['start_seconds']:.1f}s: "
              f"balls={seg['ball_count']} ({seg['ball_count_source']}), "
              f"identities={seg['identities']}, tracklets={seg['tracklets']}, links={seg['links']}, "
              f"unassigned={seg['unassigned_tracklets']} ({seg['unassigned_observed_frames']} frames), "
              f"clutter={seg['clutter_tracklets']}, "
              f"gravity={'none' if accel is None else f'{accel:.2f}'} ({seg['accel_source']})")
    print("\nLook here first (hidden links, then the costliest):")
    for row in look_here(links, args.look_here):
        print(f"  {float(row['source_end_seconds']):8.2f}s  segment {row['segment_index']}  "
              f"ball {row['ball_id']}  {row['kind']:<6} {row['hand'] or '-':<5} "
              f"track {row['source_track_id']} -> {row['target_track_id']}  "
              f"gap {row['gap_frames']} frames  cost {row['cost']}")
    print(f"\nWrote {args.output_dir}")


if __name__ == "__main__":
    main()
