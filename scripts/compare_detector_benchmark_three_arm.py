#!/usr/bin/env python3
"""Build and serve a three-arm same-frame detector/tracking benchmark."""
from __future__ import annotations

import argparse
import json
import mimetypes
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.compare_detector_benchmark import digest, load_detection_rows
from scripts.review_track_events import load_tracklets, _video_meta
from src.annotation.benchmark import (
    build_hard_events,
    build_union_frames_multi,
    summarize_arm,
)
from src.annotation.preprocessing import selected_frame_ranges
from src.annotation.segments import parse_losslesscut_csv, segment_for_frame

WEB = ROOT / "web" / "detector_benchmark"
ARMS = ("baseline", "full", "freeze10")


def build(args: argparse.Namespace) -> None:
    video, segments_path = args.video.resolve(), args.segments.resolve()
    fps, frame_count, width, height = _video_meta(video)
    segments = parse_losslesscut_csv(segments_path, duration=frame_count / fps)
    paths = {
        "baseline": (args.baseline_detections, args.baseline_tracklets, args.baseline_model),
        "full": (args.full_detections, args.full_tracklets, args.full_model),
        "freeze10": (args.freeze10_detections, args.freeze10_tracklets, args.freeze10_model),
    }
    tracks = {arm: load_tracklets(tracklets.resolve()) for arm, (_, tracklets, _) in paths.items()}
    loaded = {arm: load_detection_rows(detections.resolve()) for arm, (detections, _, _) in paths.items()}
    detections = {arm: value[0] for arm, value in loaded.items()}
    by_frame = {arm: value[1] for arm, value in loaded.items()}
    selected_duration = sum(segment.end - segment.start for segment in segments)
    events = {arm: build_hard_events(arm, tracks[arm], fps, frame_count, segments) for arm in ARMS}
    frames = build_union_frames_multi(events, fps, frame_count)
    for row in frames:
        segment = segment_for_frame(row["frame"], fps, segments)
        if segment is None:
            raise ValueError(f"Hard frame {row['frame']} falls outside selected segments")
        row.update(
            timestamp=row["frame"] / fps,
            segment=segment.as_dict(),
            detections={arm: by_frame[arm].get(row["frame"], []) for arm in ARMS},
        )
    output = args.output.resolve()
    if output.exists():
        raise ValueError(f"Benchmark output already exists: {output}")
    output.mkdir(parents=True)
    (output / "viewer").mkdir()
    for arm in ARMS:
        (output / f"events_{arm}.json").write_text(json.dumps(events[arm], indent=2) + "\n")
    (output / "union_frames.json").write_text(json.dumps(frames, indent=2) + "\n")
    summaries = {
        arm: summarize_arm(
            [row for values in by_frame[arm].values() for row in values],
            tracks[arm], events[arm], selected_duration,
        )
        for arm in ARMS
    }
    selected_frame_count = sum(
        end - start for start, end in selected_frame_ranges(fps, frame_count, segments)
    )
    for summary in summaries.values():
        summary["detections_per_selected_frame"] = summary["total_detections"] / selected_frame_count
        summary["unresolved_events_per_1000_detections"] = (
            summary["total_unresolved_events"] / summary["total_detections"] * 1000
            if summary["total_detections"] else 0
        )
    counts = Counter(row["selection"] for row in frames)
    summary = {
        "arms": summaries,
        "hard_frame_selection_counts": dict(counts),
        "total_union_hard_frames": len(frames),
        "interpretation_note": "Operational comparison only; lemons has no manual ground truth.",
    }
    (output / "benchmark_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    arm_meta = {
        "baseline": {"label": "Baseline · YOLO26l", "model": str(args.baseline_model), "class_id": 32},
        "full": {"label": "Full fine-tune · HEPTAD", "model": str(args.full_model), "class_id": 0},
        "freeze10": {"label": "Freeze=10 · HEPTAD", "model": str(args.freeze10_model), "class_id": 0},
    }
    viewer_data = {"video": str(video), "fps": fps, "width": width, "height": height,
                   "arms": arm_meta, "frames": frames, "events": events}
    (output / "viewer" / "data.json").write_text(json.dumps(viewer_data, separators=(",", ":")))
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_video": str(video), "source_video_sha256": digest(video),
        "segments_path": str(segments_path), "segments_sha256": digest(segments_path),
        "segments": [segment.as_dict() for segment in segments],
        "selected_duration_seconds": selected_duration,
        "inference": {"imgsz": args.imgsz, "conf": args.conf, "batch_size": args.batch_size,
                      "device": args.device, "classes": {"baseline": [32], "full": [0], "freeze10": [0]}},
        "tracker": {"distance_threshold": args.distance_threshold, "hit_counter_max": args.hit_counter_max,
                    "segment_reset": True},
        "arms": {arm: {
            **arm_meta[arm],
            "detections": str(paths[arm][0].resolve()),
            "detections_sha256": digest(paths[arm][0].resolve()),
            "tracklets": str(paths[arm][1].resolve()),
            "tracklets_sha256": digest(paths[arm][1].resolve()),
        } for arm in ARMS},
        "event_counts": {arm: dict(Counter(row["event_kind"] for row in events[arm])) for arm in ARMS},
        "benchmark_frame_count": len(frames),
        "hard_frame_selection_counts": dict(counts),
        "union": {"deduplicate_key": "raw source frame", "arm_count": len(ARMS)},
        "development_set": "lemons",
    }
    for arm, model_id in (("full", args.full_model_id), ("freeze10", args.freeze10_model_id)):
        if model_id:
            manifest["arms"][arm]["platform_model_id"] = model_id
    (output / "benchmark_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


def serve(args: argparse.Namespace) -> None:
    import cv2
    benchmark = args.benchmark.resolve()
    data = (benchmark / "viewer" / "data.json").read_bytes()
    manifest = json.loads((benchmark / "benchmark_manifest.json").read_text())
    video = Path(manifest["source_video"])

    def jpeg(frame: int) -> bytes:
        cap = cv2.VideoCapture(str(video))
        try:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
            ok, image = cap.read()
            if not ok:
                raise ValueError(f"Cannot decode frame {frame}")
            ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 94])
            if not ok:
                raise ValueError("JPEG encoding failed")
            return encoded.tobytes()
        finally:
            cap.release()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def send_body(self, body, content_type, status=200):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            try:
                parsed = urlparse(self.path)
                if parsed.path == "/api/data":
                    return self.send_body(data, "application/json")
                if parsed.path == "/frame":
                    frame = int(parse_qs(parsed.query)["frame"][0])
                    return self.send_body(jpeg(frame), "image/jpeg")
                assets = {"/": "index.html", "/app.js": "app.js", "/styles.css": "styles.css"}
                if parsed.path in assets:
                    path = WEB / assets[parsed.path]
                    return self.send_body(path.read_bytes(), mimetypes.guess_type(path)[0] or "text/plain")
                return self.send_body(b'{"error":"not found"}', "application/json", 404)
            except (ValueError, KeyError, OSError) as error:
                return self.send_body(json.dumps({"error": str(error)}).encode(), "application/json", 400)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Benchmark viewer: http://{args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    make = sub.add_parser("build")
    for name in ("video", "segments", "baseline-detections", "baseline-tracklets", "baseline-model",
                 "full-detections", "full-tracklets", "full-model", "freeze10-detections",
                 "freeze10-tracklets", "freeze10-model", "output"):
        make.add_argument("--" + name, type=Path, required=True)
    make.add_argument("--full-model-id", default=None)
    make.add_argument("--freeze10-model-id", default=None)
    make.add_argument("--imgsz", type=int, default=960)
    make.add_argument("--conf", type=float, default=0.15)
    make.add_argument("--batch-size", type=int, default=4)
    make.add_argument("--device", default="0")
    make.add_argument("--distance-threshold", type=float, default=50)
    make.add_argument("--hit-counter-max", type=int, default=15)
    show = sub.add_parser("serve")
    show.add_argument("--benchmark", type=Path, required=True)
    show.add_argument("--host", default="127.0.0.1")
    show.add_argument("--port", type=int, default=43129)
    return root


if __name__ == "__main__":
    args = parser().parse_args()
    build(args) if args.command == "build" else serve(args)
