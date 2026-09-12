#!/usr/bin/env python3
"""Build and serve an unbiased two-arm detector/tracker hard-event benchmark."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mimetypes
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.review_track_events import load_tracklets, _video_meta
from src.annotation.benchmark import build_benchmark
from src.annotation.segments import parse_losslesscut_csv, segment_for_frame

WEB = ROOT / "web" / "detector_benchmark"


def digest(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_detection_rows(path: Path):
    rows, by_frame = [], defaultdict(list)
    with path.open(newline="") as stream:
        for raw in csv.DictReader(stream):
            row = dict(raw)
            for key in ("frame", "class_id"):
                row[key] = int(row[key])
            for key in ("confidence", "x1", "y1", "x2", "y2", "center_x", "center_y"):
                row[key] = float(row[key])
            rows.append(row)
            by_frame[row["frame"]].append(row)
    return rows, dict(by_frame)


def build(args):
    video, segments_path = args.video.resolve(), args.segments.resolve()
    fps, frame_count, width, height = _video_meta(video)
    segments = parse_losslesscut_csv(segments_path, duration=frame_count / fps)
    tracks = {arm: load_tracklets(getattr(args, f"{arm}_tracklets").resolve()) for arm in ("baseline", "finetuned")}
    loaded = {arm: load_detection_rows(getattr(args, f"{arm}_detections").resolve()) for arm in ("baseline", "finetuned")}
    rows = {arm: loaded[arm][0] for arm in loaded}
    by_frame = {arm: loaded[arm][1] for arm in loaded}
    selected_duration = sum(segment.end - segment.start for segment in segments)
    benchmark = build_benchmark(
        tracks_by_arm=tracks, detections_by_arm=by_frame, fps=fps,
        frame_count=frame_count, segments=segments,
        selected_duration_seconds=selected_duration,
    )
    for frame in benchmark["frames"]:
        segment = segment_for_frame(frame["frame"], fps, segments)
        if segment is None:
            raise ValueError(f"Hard frame {frame['frame']} falls outside selected segments")
        frame.update(
            timestamp=frame["frame"] / fps,
            segment=segment.as_dict(),
            detections={arm: by_frame[arm].get(frame["frame"], []) for arm in by_frame},
        )
    output = args.output.resolve()
    viewer = output / "viewer"
    viewer.mkdir(parents=True, exist_ok=True)
    if (output / "benchmark_manifest.json").exists():
        raise ValueError(f"Benchmark already built: {output}")
    (output / "events_baseline.json").write_text(json.dumps(benchmark["events"]["baseline"], indent=2) + "\n")
    (output / "events_finetuned.json").write_text(json.dumps(benchmark["events"]["finetuned"], indent=2) + "\n")
    (output / "union_frames.json").write_text(json.dumps(benchmark["frames"], indent=2) + "\n")
    selection_counts = Counter(row["selection"] for row in benchmark["frames"])
    summary = {"arms": benchmark["summaries"], "hard_frame_selection_counts": dict(selection_counts),
               "total_union_hard_frames": len(benchmark["frames"])}
    (output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    (output / "benchmark_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    viewer_data = {"video": str(video), "fps": fps, "width": width, "height": height,
                   "frames": benchmark["frames"], "events": benchmark["events"]}
    (viewer / "data.json").write_text(json.dumps(viewer_data, separators=(",", ":")))
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_video": str(video), "source_video_sha256": digest(video),
        "segments_path": str(segments_path), "segments_sha256": digest(segments_path),
        "segments": [segment.as_dict() for segment in segments],
        "selected_duration_seconds": selected_duration,
        "baseline_model": args.baseline_model,
        "finetuned_model": str(args.finetuned_model.resolve()),
        "finetuned_model_sha256": digest(args.finetuned_model.resolve()),
        "training_dataset": str(args.training_dataset.resolve()),
        "training_image_count": sum(1 for _ in args.training_dataset.resolve().glob("images/*/*.jpg")),
        "inference": {"imgsz": args.imgsz, "conf": args.conf, "batch_size": args.batch_size,
                      "device": args.device, "baseline_classes": [32], "finetuned_classes": [0]},
        "tracker": {"distance_threshold": args.distance_threshold, "hit_counter_max": args.hit_counter_max},
        "inputs": {arm: {
            "detections": str(getattr(args, f"{arm}_detections").resolve()),
            "detections_sha256": digest(getattr(args, f"{arm}_detections").resolve()),
            "tracklets": str(getattr(args, f"{arm}_tracklets").resolve()),
            "tracklets_sha256": digest(getattr(args, f"{arm}_tracklets").resolve()),
        } for arm in ("baseline", "finetuned")},
        "event_counts": {arm: dict(Counter(row["event_kind"] for row in values))
                         for arm, values in benchmark["events"].items()},
        "benchmark_frame_count": len(benchmark["frames"]),
        "hard_frame_selection_counts": dict(selection_counts),
    }
    split_summary = args.training_dataset.resolve() / "split_summary.json"
    if split_summary.is_file():
        manifest["training_split"] = json.loads(split_summary.read_text())
    training_config = args.training_dataset.resolve().parent / "training_config.json"
    if training_config.is_file():
        manifest["training_config"] = json.loads(training_config.read_text())
    (output / "benchmark_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))


def serve(args):
    import cv2
    benchmark = args.benchmark.resolve()
    manifest = json.loads((benchmark / "benchmark_manifest.json").read_text())
    data = (benchmark / "viewer" / "data.json").read_bytes()
    video = Path(manifest["source_video"])

    @lru_cache(maxsize=64)
    def jpeg(frame):
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
            self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'")
            self.end_headers(); self.wfile.write(body)

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
                self.send_body(b'{"error":"not found"}', "application/json", 404)
            except (ValueError, KeyError, OSError) as error:
                self.send_body(json.dumps({"error": str(error)}).encode(), "application/json", 400)

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Benchmark viewer: http://{args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def parser():
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="command", required=True)
    make = sub.add_parser("build")
    for name in ("video", "segments", "baseline-detections", "baseline-tracklets",
                 "finetuned-detections", "finetuned-tracklets", "finetuned-model",
                 "training-dataset", "output"):
        make.add_argument("--" + name, type=Path, required=True)
    make.add_argument("--baseline-model", default="yolo26l.pt")
    make.add_argument("--imgsz", type=int, default=960); make.add_argument("--conf", type=float, default=0.15)
    make.add_argument("--batch-size", type=int, default=16); make.add_argument("--device", default="0")
    make.add_argument("--distance-threshold", type=float, default=50); make.add_argument("--hit-counter-max", type=int, default=15)
    show = sub.add_parser("serve"); show.add_argument("--benchmark", type=Path, required=True)
    show.add_argument("--host", default="127.0.0.1"); show.add_argument("--port", type=int, default=43129)
    return root


if __name__ == "__main__":
    args = parser().parse_args()
    build(args) if args.command == "build" else serve(args)
