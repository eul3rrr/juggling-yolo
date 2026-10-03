"""Local review site for the identity stage: video, state timeline, link list, labels."""
from __future__ import annotations

import csv
import datetime
import json
import mimetypes
import os
import re
import tempfile
from collections import Counter, defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

WEB = Path(__file__).resolve().parents[2] / "web" / "identity_review"
LABEL_VALUES = ("correct", "wrong", "unclear")
LABEL_FIELDS = ["video", "link_key", "segment_index", "ball_id", "kind", "hand", "source_track_id",
                "target_track_id", "source_end_seconds", "label", "note", "labeled_at"]
RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")


class LabelStore:
    """CSV labels keyed by link; rows are rewritten atomically on every save."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.rows: dict[str, dict] = {}
        if self.path.is_file():
            with self.path.open(newline="", encoding="utf-8") as stream:
                for row in csv.DictReader(stream):
                    if row.get("link_key"):
                        self.rows[row["link_key"]] = dict(row)

    def save(self, link_key: str, record: dict) -> dict:
        if record.get("label") not in LABEL_VALUES:
            raise ValueError(f"label must be one of {LABEL_VALUES}")
        row = {field: "" for field in LABEL_FIELDS}
        row.update(self.rows.get(link_key, {}))
        row.update(record)
        row["link_key"] = link_key
        self.rows[link_key] = row
        self._flush()
        return row

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(prefix=".labels-", dir=self.path.parent)
        os.close(handle)
        temp = Path(temp_name)
        try:
            with temp.open("w", newline="", encoding="utf-8") as stream:
                writer = csv.DictWriter(stream, fieldnames=LABEL_FIELDS, lineterminator="\n")
                writer.writeheader()
                for key in sorted(self.rows):
                    writer.writerow({f: self.rows[key].get(f, "") for f in LABEL_FIELDS})
            os.replace(temp, self.path)
        finally:
            temp.unlink(missing_ok=True)

    def counts(self) -> dict:
        counter = Counter(row.get("label", "") for row in self.rows.values())
        return {value: counter.get(value, 0) for value in LABEL_VALUES}


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def link_key(row: dict) -> str:
    return f"{row['segment_index']}:{row['source_track_id']}>{row['target_track_id']}"


def build_payload(identity_dir: Path, labels: LabelStore, video_name: str) -> dict:
    """Everything the page needs, with per-ball states compressed into runs.

    The review video holds only frames inside the processed segments, so each
    segment also carries ``video_offset``: the review-video frame index of its
    first frame. The page converts between source frames and video time with it.
    """
    summary = json.loads((identity_dir / "summary.json").read_text(encoding="utf-8"))
    fps = summary["fps"]
    states = _read_csv(identity_dir / "ball_states.csv")
    frames_by_segment: dict[int, set[int]] = defaultdict(set)
    runs: dict[tuple[int, int], list[list]] = defaultdict(list)
    for row in states:
        seg, ball, frame = int(row["segment_index"]), int(row["ball_id"]), int(row["frame"])
        frames_by_segment[seg].add(frame)
        key, state, hand = (seg, ball), row["state"], row["hand"]
        source = row["position_source"]
        kind = state if state != "AIRBORNE" or source == "detection" else "PREDICTED"
        last = runs[key][-1] if runs[key] else None
        if last and last[1] == frame - 1 and last[2] == kind and last[3] == hand:
            last[1] = frame
        else:
            runs[key].append([frame, frame, kind, hand])

    offset = 0
    segments = []
    for seg in summary["segments"]:
        index = seg["segment_index"]
        frames = frames_by_segment.get(index)
        entry = dict(seg, video_offset=offset if frames else None,
                     first_frame=min(frames) if frames else None,
                     last_frame=max(frames) if frames else None,
                     balls=[{"ball_id": ball, "runs": runs[(index, ball)]}
                            for (s, ball) in sorted(runs) if s == index])
        segments.append(entry)
        offset += len(frames) if frames else 0

    links = []
    for row in _read_csv(identity_dir / "links.csv"):
        key = link_key(row)
        label = labels.rows.get(key, {})
        links.append({**row, "link_key": key, "cost": float(row["cost"]),
                      "gap_frames": int(row["gap_frames"]),
                      "segment_index": int(row["segment_index"]), "ball_id": int(row["ball_id"]),
                      "source_end_frame": int(row["source_end_frame"]),
                      "target_start_frame": int(row["target_start_frame"]),
                      "label": label.get("label", ""), "note": label.get("note", "")})
    links.sort(key=lambda r: (r["kind"] != "hidden", -r["cost"]))
    dropped_path = identity_dir / "dropped_tracklets.csv"
    dropped = _read_csv(dropped_path) if dropped_path.is_file() else []
    return {
        "video": video_name, "fps": fps, "segments": segments, "links": links,
        "dropped": dropped, "label_counts": labels.counts(), "labels_path": str(labels.path),
        "link_counts": dict(Counter(r["kind"] for r in links)),
    }


def make_server(identity_dir: Path, video: Path, labels: LabelStore, host: str, port: int,
                video_name: str) -> ThreadingHTTPServer:
    identity_dir = Path(identity_dir)
    video = Path(video)

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

        def send_video(self) -> None:
            """Serve the review video with byte ranges so the player can seek."""
            size = video.stat().st_size
            start, end = 0, size - 1
            match = RANGE.match(self.headers.get("Range", ""))
            if match:
                if match.group(1):
                    start = int(match.group(1))
                    if match.group(2):
                        end = min(int(match.group(2)), size - 1)
                elif match.group(2):
                    start = max(0, size - int(match.group(2)))
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.end_headers()
                    return
            self.send_response(206 if match else 200)
            self.send_header("Content-Type", "video/mp4")
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            if match:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            with video.open("rb") as stream:
                stream.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    chunk = stream.read(min(1 << 20, remaining))
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        return
                    remaining -= len(chunk)

        def do_GET(self):
            try:
                parsed = urlparse(self.path)
                if parsed.path == "/api/data":
                    return self.send_json(build_payload(identity_dir, labels, video_name))
                if parsed.path == "/video":
                    return self.send_video()
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
                rows = {link_key(r): r for r in _read_csv(identity_dir / "links.csv")}
                row = rows.get(str(payload.get("link_key")))
                if row is None:
                    raise ValueError("unknown link")
                saved = labels.save(link_key(row), dict(
                    video=video_name, segment_index=row["segment_index"], ball_id=row["ball_id"],
                    kind=row["kind"], hand=row["hand"], source_track_id=row["source_track_id"],
                    target_track_id=row["target_track_id"],
                    source_end_seconds=row["source_end_seconds"],
                    label=payload.get("label"), note=str(payload.get("note", ""))[:2000],
                    labeled_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                ))
                return self.send_json(dict(label=saved, label_counts=labels.counts()))
            except (ValueError, KeyError, TypeError) as error:
                return self.send_json({"error": str(error)}, status=400)

    return ThreadingHTTPServer((host, port), Handler)
