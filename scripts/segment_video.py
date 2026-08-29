#!/usr/bin/env python3
"""Run frame-by-frame Ultralytics YOLO instance segmentation on one video.

For every sports-ball instance this writes:

  - a minimal per-frame detection CSV (frame,confidence,center_x,center_y,...)
    that matches the schema produced by ``scripts/detect_video.py`` so the
    downstream Norfair pipeline can consume it without modification.  The
    tracking point is the instance bounding-box center (NOT the mask centroid).

  - a richer per-instance CSV that additionally records mask area, mask
    centroid, and a compact polygon representation in the original video
    frame coordinates.

  - an annotated overlay MP4 showing the mask, the bbox, the bbox-center
    marker, the mask-centroid marker, the confidence, the frame number, and
    the number of sports-ball instances detected in the current frame.  Colors
    are assigned per frame-local instance and do NOT imply temporal identity.

This script is the perception-tier arm of the detector+segmentation capacity
comparison.  The downstream Norfair + stitch pipeline is run separately and
remains the same as for the pure-detection arms.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

# When invoked directly (./segment_video.py), the shebang initially selects
# the system Python.  Re-execute with this experiment's isolated environment
# before importing third-party dependencies.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
if sys.prefix == sys.base_prefix and VENV_PYTHON.is_file():
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])

import cv2
import numpy as np
import torch
from ultralytics import YOLO

# Minimal CSV — matches detect_video.py so track_norfair.py can consume it.
MINIMAL_CSV_FIELDS = [
    "video",
    "frame",
    "time_seconds",
    "class_id",
    "class_name",
    "confidence",
    "x1",
    "y1",
    "x2",
    "y2",
    "center_x",
    "center_y",
    "width",
    "height",
]

# Richer per-instance CSV with mask diagnostics.
INSTANCE_CSV_FIELDS = MINIMAL_CSV_FIELDS + [
    "frame_local_instance_index",
    "mask_area_px",
    "mask_centroid_x",
    "mask_centroid_y",
    "mask_centroid_valid",
    "polygon_points",
]

# Hard cap on polygon string length so CSV rows stay compact.
MAX_POLYGON_POINTS = 64


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run YOLO instance segmentation on every video frame and write "
            "detection + instance CSVs plus an overlay MP4."
        )
    )
    parser.add_argument("input_video", type=Path)
    parser.add_argument("--model", default="yolo26l-seg.pt")
    parser.add_argument("--conf", type=float, default=0.15)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument(
        "--classes",
        type=int,
        nargs="+",
        default=[32],
        help="COCO class IDs to keep (default: 32 sports ball).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs",
        help="Directory for the annotated overlay MP4.",
    )
    parser.add_argument(
        "--detections-dir",
        type=Path,
        default=PROJECT_ROOT / "detections",
        help="Directory for the minimal + instance CSVs.",
    )
    parser.add_argument(
        "--device",
        default="auto",
        help="Ultralytics device, e.g. auto, cpu, 0, or 0,1.",
    )
    parser.add_argument(
        "--mask-alpha",
        type=float,
        default=0.35,
        help="Overlay alpha for the mask fill (0..1).",
    )
    return parser.parse_args()


def resolve_device(requested: str) -> str:
    if requested != "auto":
        return requested
    return "0" if torch.cuda.is_available() else "cpu"


def safe_tag(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")


def video_metadata(path: Path) -> tuple[float, int, int, int]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"Could not open input video: {path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    capture.release()
    if fps <= 0 or width <= 0 or height <= 0 or frame_count <= 0:
        raise RuntimeError(
            f"Invalid video metadata: fps={fps}, w={width}, h={height}, frames={frame_count}"
        )
    return fps, width, height, frame_count


def _color_for_instance(index: int) -> tuple[int, int, int]:
    """Generate a distinguishable, pleasant BGR color from a frame-local index.

    This color is purely a visual aid for that frame.  It MUST NOT be
    interpreted as a temporal identifier.
    """
    # Use the golden-angle hue sequence for good separation.
    hue = (index * 0.61803398875) % 1.0
    saturation = 0.78
    value = 0.95
    import colorsys
    red, green, blue = colorsys.hsv_to_rgb(hue, saturation, value)
    return (round(blue * 255), round(green * 255), round(red * 255))


def _draw_legend(frame: np.ndarray) -> None:
    """Render a small legend so viewers do not mistake per-frame color for an ID."""
    height, width = frame.shape[:2]
    panel_height = 96
    panel_width = 320
    x0 = width - panel_width - 12
    y0 = height - panel_height - 12
    cv2.rectangle(frame, (x0, y0), (x0 + panel_width, y0 + panel_height), (20, 20, 20), -1)
    cv2.rectangle(frame, (x0, y0), (x0 + panel_width, y0 + panel_height), (220, 220, 220), 1)
    cv2.putText(frame, "frame-local only (NOT a track ID)", (x0 + 8, y0 + 18),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
    # Swatch: mask overlay color
    cv2.rectangle(frame, (x0 + 8, y0 + 28), (x0 + 28, y0 + 48), (140, 200, 255), -1)
    cv2.putText(frame, "MASK = frame-local segmented instance", (x0 + 34, y0 + 42),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
    # Plus marker
    cv2.drawMarker(frame, (x0 + 18, y0 + 64), (255, 255, 255),
                   cv2.MARKER_CROSS, 12, 2, cv2.LINE_AA)
    cv2.putText(frame, "+ = bbox center (tracking point)", (x0 + 34, y0 + 68),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
    # X marker
    cv2.drawMarker(frame, (x0 + 18, y0 + 84), (255, 255, 255),
                   cv2.MARKER_TILTED_CROSS, 12, 2, cv2.LINE_AA)
    cv2.putText(frame, "x = mask centroid (diagnostic only)", (x0 + 34, y0 + 88),
                cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)


def _draw_instance(
    frame: np.ndarray,
    mask: np.ndarray,
    bbox: tuple[float, float, float, float],
    confidence: float,
    instance_index: int,
    color: tuple[int, int, int],
    bbox_center: tuple[float, float],
    mask_centroid: tuple[float, float] | None,
    alpha: float,
) -> None:
    """Composite one instance: mask overlay, bbox, + center, x centroid, label."""
    # Mask overlay.  Mask is a (H, W) uint8/bool array aligned with the frame.
    mask_bool = mask.astype(bool)
    if mask_bool.any():
        overlay = frame.copy()
        overlay[mask_bool] = color
        cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0, frame)

    x1, y1, x2, y2 = bbox
    cv2.rectangle(
        frame,
        (round(x1), round(y1)),
        (round(x2), round(y2)),
        color,
        2,
        cv2.LINE_AA,
    )
    cv2.drawMarker(
        frame,
        (round(bbox_center[0]), round(bbox_center[1])),
        (255, 255, 255),
        cv2.MARKER_CROSS,
        14,
        2,
        cv2.LINE_AA,
    )
    if mask_centroid is not None:
        cv2.drawMarker(
            frame,
            (round(mask_centroid[0]), round(mask_centroid[1])),
            color,
            cv2.MARKER_TILTED_CROSS,
            12,
            2,
            cv2.LINE_AA,
        )
    label = f"#{instance_index} {confidence:.2f}"
    cv2.putText(
        frame,
        label,
        (round(x1) + 4, max(20, round(y1) - 6)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        color,
        2,
        cv2.LINE_AA,
    )


def _simplify_polygon(contour: np.ndarray, max_points: int) -> list[tuple[int, int]]:
    """Reduce a contour to at most ``max_points`` vertices using uniform stride."""
    n = len(contour)
    if n == 0:
        return []
    if n <= max_points:
        return [(int(p[0][0]), int(p[0][1])) for p in contour]
    stride = max(1, n // max_points)
    indices = list(range(0, n, stride))[:max_points]
    if indices[-1] != n - 1:
        indices[-1] = n - 1
    return [(int(contour[i][0][0]), int(contour[i][0][1])) for i in indices]


def _format_polygon(points: list[tuple[int, int]]) -> str:
    return ";".join(f"{x},{y}" for x, y in points)


def _mask_centroid(mask_bool: np.ndarray) -> tuple[float, float] | None:
    """Compute centroid as the mean of mask pixel coordinates.  Returns None
    if the mask is empty (defensive — should never happen in practice)."""
    ys, xs = np.where(mask_bool)
    if xs.size == 0:
        return None
    return (float(xs.mean()), float(ys.mean()))


def main() -> None:
    args = parse_args()
    input_video = args.input_video.resolve()
    if not input_video.is_file():
        raise FileNotFoundError(f"Input video does not exist: {input_video}")
    if not 0.0 <= args.conf <= 1.0:
        raise ValueError("--conf must be between 0 and 1")
    if args.imgsz <= 0:
        raise ValueError("--imgsz must be positive")
    if not 0.0 <= args.mask_alpha <= 1.0:
        raise ValueError("--mask-alpha must be between 0 and 1")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.detections_dir.mkdir(parents=True, exist_ok=True)

    device = resolve_device(args.device)
    model_reference = args.model
    project_model = PROJECT_ROOT / args.model
    if not Path(args.model).is_absolute() and project_model.is_file():
        model_reference = str(project_model)

    class_tag = "classes-" + "-".join(str(c) for c in args.classes)
    model_tag = safe_tag(Path(args.model).stem)
    run_tag = f"{input_video.stem}_{model_tag}_{class_tag}"

    annotated_path = args.output_dir / f"{run_tag}_overlay.mp4"
    minimal_csv_path = args.detections_dir / f"{run_tag}.csv"
    instance_csv_path = args.detections_dir / f"{run_tag}_instances.csv"

    fps, width, height, video_frame_count = video_metadata(input_video)

    print(f"Input: {input_video}")
    print(f"Model: {model_reference}")
    print(f"Device: {device}")
    if device != "cpu" and torch.cuda.is_available():
        print(f"CUDA device: {torch.cuda.get_device_name(0)}")
    print(
        f"Settings: conf={args.conf}, imgsz={args.imgsz}, "
        f"classes={args.classes}, vid_stride=1, mask_alpha={args.mask_alpha}"
    )
    print(f"Output MP4: {annotated_path}")
    print(f"Minimal CSV (downstream input): {minimal_csv_path}")
    print(f"Instance CSV (with masks): {instance_csv_path}")

    model = YOLO(model_reference)
    if model.task != "segment":
        raise ValueError(
            f"Expected a segmentation checkpoint, but {args.model!r} has task {model.task!r}"
        )

    writer = cv2.VideoWriter(
        str(annotated_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not create annotated video: {annotated_path}")

    frame_count = 0
    detection_count = 0
    instance_count = 0
    class_counts: Counter[str] = Counter()
    start_time = time.monotonic()
    inference_start: float | None = None
    inference_seconds_total = 0.0
    last_gpu_mem_mb: float | None = None

    try:
        with minimal_csv_path.open("w", newline="", encoding="utf-8") as minimal_file, \
             instance_csv_path.open("w", newline="", encoding="utf-8") as instance_file:
            minimal_writer = csv.DictWriter(minimal_file, fieldnames=MINIMAL_CSV_FIELDS)
            instance_writer = csv.DictWriter(instance_file, fieldnames=INSTANCE_CSV_FIELDS)
            minimal_writer.writeheader()
            instance_writer.writeheader()

            results = model.predict(
                source=str(input_video),
                stream=True,
                conf=args.conf,
                imgsz=args.imgsz,
                classes=args.classes,
                device=device,
                vid_stride=1,
                save=False,
                verbose=False,
            )
            for frame_index, result in enumerate(results):
                if frame_index == 0 and device != "cpu" and torch.cuda.is_available():
                    torch.cuda.synchronize()
                inference_start = time.monotonic()
                # Per-frame work begins here.
                frame = result.orig_img
                if frame is None:
                    # No original image available — read directly from the video.
                    cap = cv2.VideoCapture(str(input_video))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
                    ok, frame = cap.read()
                    cap.release()
                    if not ok:
                        raise RuntimeError(
                            f"Could not read frame {frame_index} from {input_video}"
                        )
                if frame.shape[0] != height or frame.shape[1] != width:
                    frame = cv2.resize(frame, (width, height))

                names = result.names
                boxes = result.boxes
                masks = result.masks
                per_frame_count = 0

                if boxes is not None and len(boxes) > 0:
                    xyxy = boxes.xyxy.detach().cpu().tolist()
                    confidences = boxes.conf.detach().cpu().tolist()
                    class_ids = boxes.cls.detach().cpu().to(torch.int64).tolist()

                    if masks is not None and len(masks) == len(boxes):
                        masks_data = masks.data.detach().cpu().numpy()
                    else:
                        masks_data = None

                    for instance_index, (coordinates, confidence, class_id) in enumerate(
                        zip(xyxy, confidences, class_ids, strict=True)
                    ):
                        x1, y1, x2, y2 = (float(v) for v in coordinates)
                        class_name = str(names[int(class_id)])
                        bbox_cx = (x1 + x2) / 2.0
                        bbox_cy = (y1 + y2) / 2.0
                        minimal_row = {
                            "video": input_video.name,
                            "frame": frame_index,
                            "time_seconds": f"{frame_index / fps:.6f}",
                            "class_id": int(class_id),
                            "class_name": class_name,
                            "confidence": f"{float(confidence):.6f}",
                            "x1": f"{x1:.3f}",
                            "y1": f"{y1:.3f}",
                            "x2": f"{x2:.3f}",
                            "y2": f"{y2:.3f}",
                            "center_x": f"{bbox_cx:.3f}",
                            "center_y": f"{bbox_cy:.3f}",
                            "width": f"{x2 - x1:.3f}",
                            "height": f"{y2 - y1:.3f}",
                        }
                        minimal_writer.writerow(minimal_row)
                        detection_count += 1
                        class_counts[class_name] += 1
                        per_frame_count += 1

                        # Mask diagnostics.
                        mask_area_px = 0
                        mask_centroid_x = ""
                        mask_centroid_y = ""
                        mask_centroid_valid = "0"
                        polygon_str = ""
                        if masks_data is not None:
                            raw_mask = masks_data[instance_index]
                            # Ultralytics returns masks at model input resolution
                            # by default.  Resize to the frame size so the
                            # reported area, centroid, and polygon are in
                            # ORIGINAL VIDEO pixel coordinates.
                            mask_frame = cv2.resize(
                                raw_mask.astype(np.float32),
                                (width, height),
                                interpolation=cv2.INTER_LINEAR,
                            )
                            mask_bool = mask_frame > 0.5
                            mask_area_px = int(mask_bool.sum())
                            centroid = _mask_centroid(mask_bool)
                            if centroid is not None and mask_area_px > 0:
                                mask_centroid_x = f"{centroid[0]:.3f}"
                                mask_centroid_y = f"{centroid[1]:.3f}"
                                mask_centroid_valid = "1"
                                contours, _ = cv2.findContours(
                                    mask_bool.astype(np.uint8),
                                    cv2.RETR_EXTERNAL,
                                    cv2.CHAIN_APPROX_NONE,
                                )
                                if contours:
                                    longest = max(contours, key=cv2.contourArea)
                                    simplified = _simplify_polygon(longest, MAX_POLYGON_POINTS)
                                    polygon_str = _format_polygon(simplified)

                        instance_row = dict(minimal_row)
                        instance_row.update(
                            {
                                "frame_local_instance_index": instance_index,
                                "mask_area_px": mask_area_px,
                                "mask_centroid_x": mask_centroid_x,
                                "mask_centroid_y": mask_centroid_y,
                                "mask_centroid_valid": mask_centroid_valid,
                                "polygon_points": polygon_str,
                            }
                        )
                        instance_writer.writerow(instance_row)
                        instance_count += 1

                        # Overlay drawing.
                        color = _color_for_instance(instance_index)
                        if masks_data is not None and mask_area_px > 0:
                            mask_to_draw = cv2.resize(
                                masks_data[instance_index].astype(np.float32),
                                (width, height),
                                interpolation=cv2.INTER_LINEAR,
                            ) > 0.5
                        else:
                            mask_to_draw = np.zeros((height, width), dtype=bool)
                        centroid_xy: tuple[float, float] | None = None
                        if mask_centroid_valid == "1":
                            centroid_xy = (float(mask_centroid_x), float(mask_centroid_y))
                        _draw_instance(
                            frame,
                            mask_to_draw,
                            (x1, y1, x2, y2),
                            float(confidence),
                            instance_index,
                            color,
                            (bbox_cx, bbox_cy),
                            centroid_xy,
                            args.mask_alpha,
                        )

                # Top-left HUD with frame + instance count.
                cv2.rectangle(frame, (0, 0), (max(280, width // 3), 30), (20, 20, 20), -1)
                cv2.putText(
                    frame,
                    f"frame {frame_index}  |  sports-ball instances: {per_frame_count}",
                    (8, 21),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.55,
                    (255, 255, 255),
                    1,
                    cv2.LINE_AA,
                )
                _draw_legend(frame)
                writer.write(frame)
                if device != "cpu" and torch.cuda.is_available() and frame_index % 50 == 0:
                    last_gpu_mem_mb = torch.cuda.max_memory_allocated() / (1024 ** 2)
                if frame_index == 0 and device != "cpu" and torch.cuda.is_available():
                    torch.cuda.reset_peak_memory_stats()
                frame_count += 1
                if device != "cpu" and torch.cuda.is_available():
                    torch.cuda.synchronize()
                inference_seconds_total += time.monotonic() - (inference_start or time.monotonic())
    finally:
        writer.release()

    total_seconds = time.monotonic() - start_time
    fps_eff = frame_count / total_seconds if total_seconds > 0 else 0.0
    inf_fps = frame_count / inference_seconds_total if inference_seconds_total > 0 else 0.0
    print(f"Frames processed: {frame_count}")
    print(f"Detection rows (minimal CSV): {detection_count}")
    print(f"Instance rows (mask CSV): {instance_count}")
    print(f"Class counts: {dict(class_counts.most_common())}")
    print(f"Wall time: {total_seconds:.2f}s  ({fps_eff:.2f} fps incl. I/O+overlay)")
    print(f"Inference time: {inference_seconds_total:.2f}s  ({inf_fps:.2f} fps pure model)")
    if device != "cpu" and torch.cuda.is_available():
        peak_mb = torch.cuda.max_memory_allocated() / (1024 ** 2)
        print(f"Peak GPU memory (YOLO): {peak_mb:.1f} MB")
    print(f"Overlay MP4: {annotated_path.resolve()}")
    print(f"Minimal CSV: {minimal_csv_path.resolve()}")
    print(f"Instance CSV: {instance_csv_path.resolve()}")


if __name__ == "__main__":
    main()
