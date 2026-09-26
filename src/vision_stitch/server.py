"""Local review UI for vision-stitch verdicts: evidence, verdict, human label."""
from __future__ import annotations

import csv
import datetime
import json
import mimetypes
import os
import re
import tempfile
from collections import Counter
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import cv2

from src.vision_stitch.evidence import FrameReader
from src.vision_stitch.judge import event_slug

WEB = Path(__file__).resolve().parents[2] / "web" / "vision_stitch"
LABEL_VALUES = ("correct", "wrong", "unclear")
LABEL_FIELDS = ["video", "event_key", "source_track_id", "source_end_frame", "model_decision",
                "model_candidate_letter", "model_candidate_track_id", "model_confidence",
                "cv_rank1_track_id", "cv_prediction_error", "label", "note", "labeled_at"]
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")


class LabelStore:
    """CSV labels keyed by event_key; existing rows are preserved and updated in place."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.rows: dict[str, dict] = {}
        if self.path.is_file():
            with self.path.open(newline="", encoding="utf-8") as stream:
                for row in csv.DictReader(stream):
                    if row.get("event_key"):
                        self.rows[row["event_key"]] = dict(row)

    def get(self, event_key: str) -> dict | None:
        return self.rows.get(event_key)

    def save(self, event_key: str, record: dict) -> dict:
        label = record.get("label")
        if label not in LABEL_VALUES:
            raise ValueError(f"label must be one of {LABEL_VALUES}")
        row = {field: "" for field in LABEL_FIELDS}
        row.update(self.rows.get(event_key, {}))
        row.update(record)
        row["event_key"] = event_key
        self.rows[event_key] = row
        self._flush()
        return row

    def _flush(self) -> None:
        directory = self.path.parent
        handle, temp_name = tempfile.mkstemp(prefix=".labels-", dir=directory)
        os.close(handle)
        temp = Path(temp_name)
        try:
            with temp.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=LABEL_FIELDS)
                writer.writeheader()
                for key in sorted(self.rows):
                    writer.writerow({field: self.rows[key].get(field, "") for field in LABEL_FIELDS})
            os.replace(temp, self.path)
        finally:
            temp.unlink(missing_ok=True)

    def counts(self) -> dict:
        counter = Counter(row.get("label", "") for row in self.rows.values())
        return {value: counter.get(value, 0) for value in LABEL_VALUES}


@lru_cache(maxsize=4)
def _reader_for(video_path: str) -> FrameReader:
    return FrameReader(Path(video_path))


def build_items(events_root: Path, results_root: Path, labels: LabelStore, video_label: str) -> list[dict]:
    items = []
    for manifest_path in sorted(Path(events_root).glob("*/manifest.json")):
        manifest = json.loads(manifest_path.read_text())
        slug = event_slug(manifest["event_key"])
        result_path = Path(results_root) / f"{slug}.json"
        result = json.loads(result_path.read_text()) if result_path.is_file() else {}
        verdict = result.get("verdict", {}) or {}
        usage = result.get("usage", {}) or {}
        source, candidates = manifest["source"], manifest["candidates"]
        frames = [source["last_frame"]] + [c["first_frame"] for c in candidates]
        items.append(dict(
            event_key=manifest["event_key"],
            slug=slug,
            video=video_label,
            segment_index=manifest["segment_index"],
            window=dict(first_frame=max(0, min(frames) - 45), last_frame=max(frames) + 45,
                        reference_frame=source["last_frame"], fps=manifest["video"]["fps"]),
            source=source,
            candidates=candidates,
            cv_rank1=manifest["cv_rank1"],
            model=dict(
                model=result.get("model"), prompt_version=result.get("prompt_version"),
                decision=verdict.get("decision"), candidate_letter=verdict.get("candidate_letter"),
                candidate_track_id=result.get("candidate_track_id"),
                confidence=verdict.get("confidence"), reason=verdict.get("reason"),
                parse_ok=verdict.get("parse_ok"), raw_text=result.get("raw_text"),
                latency_s=result.get("latency_s"), cost_usd=usage.get("cost_usd"),
                error=result.get("error") or verdict.get("error"),
                judged=bool(result),
            ),
            images=[dict(url=f"/evidence/{slug}/{image['file']}", role=image["role"], letter=image.get("letter"),
                         label=image["label"], seconds=image["seconds"], frame=image["frame"])
                    for image in manifest["images"]],
            label=labels.get(manifest["event_key"]),
        ))
    return items


def make_server(events_root: Path, results_root: Path, labels: LabelStore, video: Path,
                host: str = "127.0.0.1", port: int = 43130) -> ThreadingHTTPServer:
    events_root, results_root = Path(events_root), Path(results_root)
    video_label = Path(video).name

    def jpeg(slug: str, frame: int) -> bytes:
        manifest_path = events_root / slug / "manifest.json"
        if not manifest_path.is_file():
            raise ValueError("unknown event")
        manifest = json.loads(manifest_path.read_text())
        reader = _reader_for(manifest["video"]["path"])
        image = reader(frame)
        ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 88])
        if not ok:
            raise ValueError("JPEG encoding failed")
        return buffer.tobytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def send_body(self, body: bytes, content_type: str, status: int = 200) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, payload, status: int = 200) -> None:
            self.send_body(json.dumps(payload, allow_nan=False).encode(), "application/json", status)

        def do_GET(self):
            try:
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                if parsed.path == "/api/items":
                    items = build_items(events_root, results_root, labels, video_label)
                    return self.send_json(dict(items=items, label_counts=labels.counts(),
                                               video=video_label, labels_path=str(labels.path)))
                if parsed.path == "/evidence":
                    slug = query.get("event", [""])[0]
                    name = query.get("file", [""])[0]
                    if not SAFE_NAME.match(slug) or not SAFE_NAME.match(name):
                        raise ValueError("invalid evidence path")
                    path = events_root / slug / name
                    if not path.is_file():
                        raise ValueError("evidence not found")
                    return self.send_body(path.read_bytes(), "image/jpeg")
                if parsed.path == "/frame":
                    slug = query.get("event", [""])[0]
                    if not SAFE_NAME.match(slug):
                        raise ValueError("invalid event")
                    return self.send_body(jpeg(slug, int(query["frame"][0])), "image/jpeg")
                assets = {"/": "index.html", "/app.js": "app.js", "/styles.css": "styles.css"}
                if parsed.path in assets:
                    path = WEB / assets[parsed.path]
                    return self.send_body(path.read_bytes(), mimetypes.guess_type(path)[0] or "text/plain")
                return self.send_json({"error": "not found"}, status=404)
            except (ValueError, KeyError, OSError) as error:
                return self.send_json({"error": str(error)}, status=400)

        def do_POST(self):
            origin = self.headers.get("Origin")
            if origin and origin != "http://" + self.headers.get("Host", ""):
                return self.send_json({"error": "Cross-origin write refused"}, status=403)
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.send_json({"error": "JSON required"}, status=415)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 200000:
                    raise ValueError("Invalid request size")
                payload = json.loads(self.rfile.read(length))
                if self.path != "/api/label" or not isinstance(payload, dict):
                    return self.send_json({"error": "not found"}, status=404)
                item = next((i for i in build_items(events_root, results_root, labels, video_label)
                             if i["event_key"] == payload.get("event_key")), None)
                if item is None:
                    raise ValueError("unknown event")
                row = dict(
                    video=item["video"], source_track_id=item["source"]["track_id"],
                    source_end_frame=item["source"]["last_frame"],
                    model_decision=item["model"]["decision"] or "",
                    model_candidate_letter=item["model"]["candidate_letter"] or "",
                    model_candidate_track_id=item["model"]["candidate_track_id"] or "",
                    model_confidence=item["model"]["confidence"] if item["model"]["confidence"] is not None else "",
                    cv_rank1_track_id=item["cv_rank1"]["track_id"],
                    cv_prediction_error=round(item["cv_rank1"]["prediction_error"], 3),
                    label=payload.get("label"), note=str(payload.get("note", ""))[:2000],
                    labeled_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                )
                saved = labels.save(item["event_key"], row)
                return self.send_json(dict(label=saved, label_counts=labels.counts()))
            except (ValueError, KeyError, TypeError) as error:
                return self.send_json({"error": str(error)}, status=400)

    return ThreadingHTTPServer((host, port), Handler)
