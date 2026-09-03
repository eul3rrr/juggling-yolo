from __future__ import annotations

import asyncio
import csv
import json
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import sys

import cv2
import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

try:
    from .engine import DisplayHIDMap, load_canonical_rows
    from .protocol import FrameState, serialize_frame_state
    from .sources import OpenCVSource, SourceOpenError
except ImportError:  # direct test/module loading
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from engine import DisplayHIDMap, load_canonical_rows
    from protocol import FrameState, serialize_frame_state
    from sources import OpenCVSource, SourceOpenError

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web" / "live"


def create_app() -> FastAPI:
    app = FastAPI(title="Juggling Tracker Live")
    app.state.source = None
    app.state.running = False
    app.state.paused = False
    app.state.config = {}
    app.state.replay = None
    app.state.recording = None
    app.state.detector = None
    app.state.tracker = None

    @app.get("/")
    async def index():
        return FileResponse(WEB / "index.html")

    @app.get("/app.js")
    async def javascript():
        return FileResponse(WEB / "app.js", media_type="text/javascript")

    @app.get("/styles.css")
    async def css():
        return FileResponse(WEB / "styles.css", media_type="text/css")

    @app.get("/api/health")
    async def health():
        return {"ok": True, "running": app.state.running, "config": app.state.config}

    @app.post("/api/start")
    async def start(config: dict):
        await _stop(app)
        app.state.config = config
        app.state.detector = None
        app.state.tracker = None
        app.state.replay = _load_replay(config.get("video_path")) if config.get("source", "video") == "video" else None
        if config.get("record"):
            session_dir = ROOT / "outputs" / "live_sessions" / datetime.now().strftime("%Y%m%d_%H%M%S")
            session_dir.mkdir(parents=True, exist_ok=True)
            app.state.recording = {"dir": session_dir, "writer": None, "state": (session_dir / "live_state.jsonl").open("w", encoding="utf-8")}
        app.state.running = True
        app.state.paused = False
        return {"ok": True, "config": config}

    @app.post("/api/control/{command}")
    async def control(command: str):
        if command == "pause": app.state.paused = True
        elif command == "play": app.state.paused = False
        elif command in {"stop", "restart"}:
            if app.state.source and command == "restart": app.state.source.restart()
            else: await _stop(app)
        return {"ok": True, "command": command}

    @app.websocket("/ws")
    async def websocket(ws: WebSocket):
        await ws.accept()
        try:
            while True:
                if not app.state.running:
                    await asyncio.sleep(.1); continue
                if app.state.paused:
                    await asyncio.sleep(.05); continue
                source = app.state.source
                if source is None:
                    cfg = app.state.config
                    source = OpenCVSource(cfg.get("source", "video"), cfg.get("video_path"), int(cfg.get("camera_index", 0)))
                    app.state.source = source
                    try: source.open()
                    except SourceOpenError as exc:
                        await ws.send_text(serialize_frame_state(FrameState(0, 0, 0, error=str(exc))))
                        app.state.running = False; continue
                started = time.perf_counter()
                ok, frame = source.read()
                if not ok:
                    app.state.paused = True
                    continue
                h, w = frame.shape[:2]
                state = _frame_state(app, source, frame, int(source._read_count - 1), started)
                if app.state.recording:
                    rec = app.state.recording
                    if rec["writer"] is None:
                        rec["writer"] = cv2.VideoWriter(str(rec["dir"] / "source.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), max(source.info.fps, 30), (w, h))
                    rec["writer"].write(frame)
                    rec["state"].write(serialize_frame_state(state) + "\n")
                await ws.send_text(serialize_frame_state(state))
                ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
                if ok: await ws.send_bytes(encoded.tobytes())
                await asyncio.sleep(0)
        except WebSocketDisconnect:
            return

    return app


def _frame_state(app, source, frame, frame_id, started):
    tracks = []
    cfg = app.state.config
    replay = app.state.replay
    if replay:
        tracks = replay["frames"].get(frame_id, [])
    else:
        rows = cfg.get("track_rows", {})
        tracks = list(rows.get(str(frame_id), rows.get(frame_id, [])))
        if not tracks and cfg.get("source") == "webcam":
            tracks = _infer_tracks(app, frame)
    recent_events = []
    recent_bridges = []
    if replay:
        recent_events = [e for e in replay["events"] if e["frame"] <= frame_id][-50:]
        recent_bridges = [b for b in replay["bridges"] if b["target_start_frame"] <= frame_id][-5:]
    hands = replay["hands"].get(frame_id, {}) if replay else {}
    pending = []
    if replay:
        for event in replay["events"]:
            if event["event_type"] != "HAND_ENTRY" or event["frame"] > frame_id:
                continue
            if not any(b["source_track_id"] == event["track_id"] and b["target_start_frame"] <= frame_id for b in replay["bridges"]):
                pending.append({"track_id": event["track_id"], "hid": replay["mapping"].get(event["track_id"]), "hand": event["hand"], "age_seconds": round((frame_id-event["frame"])/max(source.info.fps, 1), 2), "position": None})
    proximity = {}
    for side, wrist in hands.items():
        if not isinstance(wrist, dict) or wrist.get("x") is None: continue
        scale = wrist.get("body_scale")
        proximity[side] = {"x": wrist["x"], "y": wrist["y"], "very_near_radius": .35*scale if scale else 60, "possible_radius": .7*scale if scale else 130, "body_scale": scale}
    return FrameState(frame_id, frame.shape[1], frame.shape[0], source.info.fps,
                      1.0 / max(time.perf_counter() - started, 1e-6),
                      (time.perf_counter() - started) * 1000, tracks=tracks,
                      hands=hands, proximity=proximity, pending=pending,
                      events_recent=recent_events, bridges_recent=recent_bridges,
                      counts={"visible_tracks": len(tracks), "display_hids": len({t.get("hid", t.get("track_id")) for t in tracks}), "pending": len(pending)})


def _infer_tracks(app, frame):
    """Lazy webcam detector/tracker using the frozen live defaults."""
    if app.state.detector is None:
        try:
            from ultralytics import YOLO
            from norfair import Tracker
            app.state.detector = YOLO(str(ROOT / "yolo26l.pt"))
            app.state.tracker = Tracker(distance_function="euclidean", distance_threshold=50, hit_counter_max=5)
        except Exception:
            return []
    result = app.state.detector.predict(frame, classes=[32], conf=0.15, imgsz=960, verbose=False)[0]
    detections = []
    from norfair import Detection
    for xyxy, conf in zip(result.boxes.xyxy.cpu().numpy(), result.boxes.conf.cpu().numpy()):
        x1, y1, x2, y2 = xyxy
        detections.append(Detection(np.array([[(x1+x2)/2, (y1+y2)/2]], dtype=np.float32), scores=np.array([conf], dtype=np.float32)))
    tracks = []
    for track in app.state.tracker.update(detections):
        if track.id is None or track.last_detection is None:
            continue
        x, y = (float(v) for v in np.asarray(track.estimate)[0])
        tracks.append({"track_id": int(track.id), "x": x, "y": y, "confidence": float(np.asarray(track.last_detection.scores).reshape(-1)[0])})
    return tracks


async def _stop(app):
    if app.state.source: app.state.source.release()
    if app.state.recording:
        if app.state.recording["writer"]: app.state.recording["writer"].release()
        app.state.recording["state"].close()
        app.state.recording = None
    app.state.source = None
    app.state.running = False


def _load_replay(video_path):
    if not video_path:
        return None
    path = Path(video_path)
    track_path = ROOT / "detections" / "detector_seg_comparison" / f"{path.stem}_yolo26l_classes-32_norfair_dt50_hc5.csv"
    if not track_path.is_file():
        return None
    by_frame = defaultdict(list)
    with track_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("observed") != "1":
                continue
            by_frame[int(row["frame"])].append({"track_id": int(row["track_id"]), "x": float(row["center_x"]), "y": float(row["center_y"]), "confidence": float(row["confidence"])})
    assoc_path = ROOT / "detections" / "detector_seg_comparison" / f"{path.stem}_hand_associations.csv"
    mapping = DisplayHIDMap()
    if assoc_path.is_file():
        with assoc_path.open(newline="", encoding="utf-8") as f:
            pairs = [(int(r["source_track_id"]), int(r["target_track_id"])) for r in csv.DictReader(f)]
        mapping.apply_associations(pairs)
    for rows in by_frame.values():
        for row in rows: row["hid"] = mapping.hid_for(row["track_id"])
    events = []
    event_path = ROOT / "detections" / "detector_seg_comparison" / f"{path.stem}_hand_events.csv"
    if event_path.is_file():
        with event_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                events.append({"frame": int(row["boundary_frame"]), "track_id": int(row["track_id"]), "event_type": row["event_type"], "hand": row.get("preferred_hand") or row.get("eligible_hand_set", ""), "evidence": row.get("evidence_reason", ""), **{k: row[k] for k in ("endpoint_distance_px", "endpoint_distance_normalized", "recent_min_distance_px", "recent_min_distance_normalized", "motion", "proximity_band") if k in row}})
    bridges = []
    if assoc_path.is_file():
        with assoc_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                bridges.append({"source_track_id": int(row["source_track_id"]), "target_track_id": int(row["target_track_id"]), "source_end_frame": int(row["source_end_frame"]), "target_start_frame": int(row["target_start_frame"]), "hand": row.get("resolved_hand", "")})
    hands = defaultdict(dict)
    hands_path = ROOT / "detections" / f"{path.stem}_yolo26s-pose-hands.csv"
    if hands_path.is_file():
        with hands_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                fr = int(float(row["frame"]))
                for side in ("left", "right"):
                    x, y, c = row.get(f"{side}_wrist_x_smooth"), row.get(f"{side}_wrist_y_smooth"), row.get(f"{side}_wrist_confidence")
                    if x and y and c and float(c) >= .25:
                        hands[fr][side.upper()] = {"x": float(x), "y": float(y), "confidence": float(c), "body_scale": float(row["body_scale_shoulder_px"]) if row.get("body_scale_shoulder_px") else None}
    return {"frames": by_frame, "mapping": mapping.mapping, "events": events, "bridges": bridges, "hands": hands}
