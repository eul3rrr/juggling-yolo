"""Hand System v1 — pose extraction.

Runs an Ultralytics pose model on a single juggling video, writes an
augmented per-frame CSV with raw and smoothed wrist / elbow / shoulder
coordinates plus a body-scale estimate.

The model is the same one the project already uses
(``yolo26s-pose.pt``) and keypoints follow the COCO-17 layout:
    5  left_shoulder
    6  right_shoulder
    7  left_elbow
    8  right_elbow
    9  left_wrist
   10  right_wrist

Anatomical left/right is taken from the pose output, NOT from screen
position. The video contains crossed arms and a screen-position heuristic
would be wrong.

The output CSV is named::

    detections/<stem>_yolo26s-pose-hands.csv

so it does not overwrite the existing
``detections/<stem>_yolo26s-pose.csv`` produced by the earlier
``analyze_stitch_features.py pose`` subcommand.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import hand_features  # noqa: E402

# COCO-17 keypoint indices
LEFT_SHOULDER, RIGHT_SHOULDER = 5, 6
LEFT_ELBOW, RIGHT_ELBOW = 7, 8
LEFT_WRIST, RIGHT_WRIST = 9, 10
KEYPOINT_NAMES = {
    LEFT_SHOULDER: "left_shoulder", RIGHT_SHOULDER: "right_shoulder",
    LEFT_ELBOW: "left_elbow", RIGHT_ELBOW: "right_elbow",
    LEFT_WRIST: "left_wrist", RIGHT_WRIST: "right_wrist",
}

# Confidence threshold below which a keypoint is treated as missing.
DEFAULT_CONFIDENCE_THRESHOLD = 0.25

# CSV schema. The first 8 columns are human-readable identifiers; the
# remaining columns are interleaved (raw, smoothed) for every tracked
# keypoint, so downstream code can choose the version that fits the use
# case.
_FIELDS_TOP = (
    "video", "frame", "time_seconds", "person_index", "person_confidence",
    "body_scale_shoulder_px",
)
_FIELDS_PER_KP = (
    "x", "y", "confidence", "x_smooth", "y_smooth",
)
_TRACKED_KEYPOINTS = (
    LEFT_SHOULDER, RIGHT_SHOULDER,
    LEFT_ELBOW, RIGHT_ELBOW,
    LEFT_WRIST, RIGHT_WRIST,
)
HANDS_FIELDS = _FIELDS_TOP + tuple(
    f"{KEYPOINT_NAMES[k]}_{field}" for k in _TRACKED_KEYPOINTS for field in _FIELDS_PER_KP
)


@dataclass
class PersonFrame:
    frame: int
    person_index: int
    person_confidence: float | None
    keypoints: dict[int, tuple[float, float, float | None]]


# ---------------------------------------------------------------------------
# Pose inference
# ---------------------------------------------------------------------------

def _resolve_device(value: str) -> str:
    if value and value != "auto":
        return value
    try:
        import torch
        return "0" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


def _parse_video(video: Path) -> tuple[float, int, int]:
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video}")
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    if fps <= 0 or width <= 0 or height <= 0:
        raise RuntimeError(f"Invalid video metadata: {fps=} {width=} {height=}")
    return fps, width, height


def _select_main_persons(frame_persons: list[PersonFrame],
                         max_persons: int) -> list[PersonFrame]:
    """Keep at most ``max_persons`` persons per frame by descending person
    confidence. Ties are broken by person_index to keep ordering stable.
    """
    return sorted(
        frame_persons,
        key=lambda p: (-(p.person_confidence or -1.0), p.person_index),
    )[:max_persons]


def _infer_pose(video: Path, model_path: str, device: str, imgsz: int,
                conf: float, max_persons: int) -> list[list[PersonFrame]]:
    """Run pose on the entire video, return per-frame person lists."""
    model = YOLO(model_path)
    if model.task != "pose":
        raise ValueError(f"Expected a pose checkpoint, but {model_path!r} has task {model.task!r}")
    print(f"Pose model: {model_path} (task={model.task})", flush=True)
    per_frame: list[list[PersonFrame]] = []
    for frame_index, result in enumerate(
        model.predict(source=str(video), stream=True, conf=conf,
                      imgsz=imgsz, device=device, vid_stride=1,
                      save=False, verbose=False)
    ):
        persons: list[PersonFrame] = []
        keypoints = result.keypoints
        if keypoints is not None and keypoints.data is not None:
            data = keypoints.data.detach().cpu().numpy()
            person_conf = (
                result.boxes.conf.detach().cpu().numpy()
                if result.boxes is not None and result.boxes.conf is not None
                else np.full(len(data), np.nan, dtype=float)
            )
            for person_index, person in enumerate(data):
                kps: dict[int, tuple[float, float, float | None]] = {}
                for kp_index in _TRACKED_KEYPOINTS:
                    if kp_index >= person.shape[0]:
                        continue
                    x, y, c = person[kp_index]
                    kps[kp_index] = (
                        float(x), float(y),
                        float(c) if math.isfinite(float(c)) else None,
                    )
                pc = float(person_conf[person_index]) if person_index < len(person_conf) and math.isfinite(float(person_conf[person_index])) else None
                persons.append(PersonFrame(
                    frame=frame_index, person_index=person_index,
                    person_confidence=pc, keypoints=kps,
                ))
        per_frame.append(_select_main_persons(persons, max_persons))
    return per_frame


# ---------------------------------------------------------------------------
# Smoothing + CSV write
# ---------------------------------------------------------------------------

def _smooth_per_keypoint(per_frame: list[list[PersonFrame]],
                         keypoint_index: int,
                         confidence_threshold: float,
                         window: int) -> list[list[tuple[float, float] | None]]:
    """Return per-frame per-person smoothed (x, y) tuples.

    The smoother is applied independently per (keypoint, person_index)
    trajectory. If person_index assignments are unstable across frames
    (e.g. the model reorders people), smoothing is intentionally degraded
    rather than re-identified: this script is a **hand-extraction
    primitive**, not a person tracker, and identity mistakes would silently
    swap anatomical labels.
    """
    # First, build per-person-series with the *raw* values.
    max_persons = max((len(p) for p in per_frame), default=0)
    series_x: list[list[float | None]] = [[] for _ in range(max_persons)]
    series_y: list[list[float | None]] = [[] for _ in range(max_persons)]
    series_c: list[list[float | None]] = [[] for _ in range(max_persons)]
    for frame_persons in per_frame:
        for slot in range(max_persons):
            if slot < len(frame_persons) and keypoint_index in frame_persons[slot].keypoints:
                x, y, c = frame_persons[slot].keypoints[keypoint_index]
                series_x[slot].append(x)
                series_y[slot].append(y)
                series_c[slot].append(c)
            else:
                series_x[slot].append(None)
                series_y[slot].append(None)
                series_c[slot].append(None)
    smoothed_x = [hand_features.smooth_series(
        sx, window=window, min_confidence=sc, confidence_threshold=confidence_threshold)
        for sx, sc in zip(series_x, series_c)]
    smoothed_y = [hand_features.smooth_series(
        sy, window=window, min_confidence=sc, confidence_threshold=confidence_threshold)
        for sy, sc in zip(series_y, series_c)]
    out: list[list[tuple[float, float] | None]] = []
    for sx, sy in zip(smoothed_x, smoothed_y):
        out.append([
            (float(x), float(y)) if x is not None and y is not None else None
            for x, y in zip(sx, sy)
        ])
    return out


def _body_scale_for_frame(left_shoulder_xy: tuple[float, float] | None,
                          right_shoulder_xy: tuple[float, float] | None) -> float | None:
    if left_shoulder_xy is None or right_shoulder_xy is None:
        return None
    return hand_features.body_scale(
        np.asarray(left_shoulder_xy, dtype=float),
        np.asarray(right_shoulder_xy, dtype=float),
    )


def _stored(video: Path) -> str:
    try:
        return str(video.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(video.resolve())


def write_csv(per_frame: list[list[PersonFrame]], video: Path, fps: float,
              output_csv: Path, confidence_threshold: float, window: int) -> int:
    smoothed_per_kp = {
        kp: _smooth_per_keypoint(per_frame, kp, confidence_threshold, window)
        for kp in _TRACKED_KEYPOINTS
    }
    rows_written = 0
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=HANDS_FIELDS, lineterminator="\n")
        writer.writeheader()
        for frame_index, persons in enumerate(per_frame):
            for slot, person in enumerate(persons):
                row: dict[str, str] = {
                    "video": _stored(video),
                    "frame": str(frame_index),
                    "time_seconds": f"{frame_index / fps:.6f}" if fps > 0 else "",
                    "person_index": str(person.person_index),
                    "person_confidence": (
                        f"{person.person_confidence:.6f}"
                        if person.person_confidence is not None else ""
                    ),
                }
                l_shoulder = person.keypoints.get(LEFT_SHOULDER)
                r_shoulder = person.keypoints.get(RIGHT_SHOULDER)
                scale = _body_scale_for_frame(
                    (l_shoulder[0], l_shoulder[1]) if l_shoulder else None,
                    (r_shoulder[0], r_shoulder[1]) if r_shoulder else None,
                )
                row["body_scale_shoulder_px"] = (
                    f"{scale:.3f}" if scale is not None else ""
                )
                for kp in _TRACKED_KEYPOINTS:
                    raw = person.keypoints.get(kp)
                    smooth = (
                        smoothed_per_kp[kp][slot][frame_index]
                        if slot < len(smoothed_per_kp[kp]) else None
                    )
                    base = KEYPOINT_NAMES[kp]
                    if raw is not None:
                        x, y, c = raw
                        row[f"{base}_x"] = f"{x:.3f}"
                        row[f"{base}_y"] = f"{y:.3f}"
                        row[f"{base}_confidence"] = (
                            f"{c:.6f}" if c is not None else ""
                        )
                    else:
                        row[f"{base}_x"] = ""
                        row[f"{base}_y"] = ""
                        row[f"{base}_confidence"] = ""
                    if smooth is not None:
                        row[f"{base}_x_smooth"] = f"{smooth[0]:.3f}"
                        row[f"{base}_y_smooth"] = f"{smooth[1]:.3f}"
                    else:
                        row[f"{base}_x_smooth"] = ""
                        row[f"{base}_y_smooth"] = ""
                writer.writerow(row)
                rows_written += 1
    return rows_written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hand System v1 pose extraction")
    parser.add_argument("video", type=Path)
    parser.add_argument(
        "--output-csv", type=Path, default=None,
        help="Override output path; default: detections/<stem>_yolo26s-pose-hands.csv",
    )
    parser.add_argument("--model", type=str, default="yolo26s-pose.pt")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--device", type=str, default="auto")
    parser.add_argument(
        "--confidence-threshold", type=float, default=DEFAULT_CONFIDENCE_THRESHOLD,
        help="Pose keypoints with confidence below this value are treated as missing.",
    )
    parser.add_argument(
        "--smoothing-window", type=int, default=5,
        help="Centered median window (frames). Long gaps are not bridged.",
    )
    parser.add_argument(
        "--max-persons-per-frame", type=int, default=2,
        help="Keep at most N persons per frame (by descending person confidence).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    video = args.video.resolve()
    if not video.is_file():
        print(f"Video not found: {video}", file=sys.stderr)
        return 1
    fps, width, height = _parse_video(video)
    device = _resolve_device(args.device)
    print(f"Input: {video}  {width}x{height} @ {fps:.3f} fps")
    print(f"Device: {device}  imgsz={args.imgsz}  conf={args.conf}")
    print(f"Smoothing: window={args.smoothing_window}  "
          f"confidence_threshold={args.confidence_threshold}")
    per_frame = _infer_pose(
        video, args.model, device, args.imgsz, args.conf, args.max_persons_per_frame,
    )
    output_csv = args.output_csv
    if output_csv is None:
        output_csv = PROJECT_ROOT / "detections" / f"{video.stem}_yolo26s-pose-hands.csv"
    rows = write_csv(
        per_frame, video, fps, output_csv,
        args.confidence_threshold, args.smoothing_window,
    )
    print(f"Pose frames: {len(per_frame)}")
    print(f"Pose rows:   {rows}")
    print(f"Output CSV:  {output_csv}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
