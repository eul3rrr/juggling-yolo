#!/usr/bin/env python3
"""Build a contact sheet of detections that only appear in a lower threshold arm.

For each pair (lower_csv, higher_csv), identify detections in the lower
CSV that are not present in the higher CSV (matched by frame +
rounded center) and crop a small image around each one from the source
video. Lay the crops out into a PNG montage for visual QA.

The categorization (TP / FP / hand-occlusion / motion-blur / etc.) is
left to the human reviewer. This script only produces the visual
evidence.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import sys
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _f(value: str) -> float:
    return float(value)


def _montage(images: list[np.ndarray], cols: int, pad: int = 4,
             bg: tuple[int, int, int] = (32, 32, 32)) -> np.ndarray:
    if not images:
        raise ValueError("No images to montage")
    h = max(img.shape[0] for img in images)
    w = max(img.shape[1] for img in images)
    rows = math.ceil(len(images) / cols)
    sheet_h = rows * (h + pad) + pad
    sheet_w = cols * (w + pad) + pad
    sheet = np.full((sheet_h, sheet_w, 3), bg, dtype=np.uint8)
    for i, img in enumerate(images):
        r, c = divmod(i, cols)
        y = pad + r * (h + pad)
        x = pad + c * (w + pad)
        sheet[y:y + img.shape[0], x:x + img.shape[1]] = img
    return sheet


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input_video", type=Path)
    parser.add_argument("lower_csv", type=Path)
    parser.add_argument("higher_csv", type=Path)
    parser.add_argument("output_png", type=Path)
    parser.add_argument("--max-crops", type=int, default=24,
                        help="Maximum number of crops to include.")
    parser.add_argument("--crop-half-size", type=int, default=64,
                        help="Half-size of the square crop window in pixels.")
    parser.add_argument("--cols", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--min-conf", type=float, default=0.0)
    parser.add_argument("--max-conf", type=float, default=1.0)
    args = parser.parse_args()

    rng = random.Random(args.seed)

    # Read higher-CSV keys so we can detect "new" detections.
    higher_keys: set[tuple[int, float, float]] = set()
    with args.higher_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            higher_keys.add((
                int(row["frame"]),
                round(_f(row["center_x"]), 1),
                round(_f(row["center_y"]), 1),
            ))

    new_rows: list[dict[str, str]] = []
    with args.lower_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            c = _f(row["confidence"])
            if c < args.min_conf or c > args.max_conf:
                continue
            key = (int(row["frame"]),
                   round(_f(row["center_x"]), 1),
                   round(_f(row["center_y"]), 1))
            if key not in higher_keys:
                new_rows.append(row)
    new_rows.sort(key=lambda r: _f(r["confidence"]), reverse=True)
    if len(new_rows) > args.max_crops:
        # Stratified sample across the confidence range so the montage is
        # representative: keep the highest-conf new detections plus a
        # random sample of the rest.
        keep_top = max(1, args.max_crops // 4)
        top = new_rows[:keep_top]
        rest = new_rows[keep_top:]
        rng.shuffle(rest)
        chosen = top + rest[: args.max_crops - keep_top]
        chosen.sort(key=lambda r: int(r["frame"]))
        new_rows = chosen

    if not new_rows:
        print(f"No new detections between {args.higher_csv.name} and "
              f"{args.lower_csv.name} in conf [{args.min_conf}, {args.max_conf}]")
        return

    cap = cv2.VideoCapture(str(args.input_video))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open {args.input_video}")

    crops: list[np.ndarray] = []
    for row in new_rows:
        frame_idx = int(row["frame"])
        cx = int(_f(row["center_x"]))
        cy = int(_f(row["center_y"]))
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ok, frame = cap.read()
        if not ok:
            continue
        h, w = frame.shape[:2]
        half = args.crop_half_size
        x0 = max(0, cx - half)
        y0 = max(0, cy - half)
        x1 = min(w, cx + half)
        y1 = min(h, cy + half)
        crop = frame[y0:y1, x0:x1].copy()
        cv2.rectangle(crop, (max(0, cx - half - x0), max(0, cy - half - y0)),
                      (min(crop.shape[1], cx + half - x0),
                       min(crop.shape[0], cy + half - y0)),
                      (0, 255, 0), 2)
        cv2.putText(crop, f"f{frame_idx} c{_f(row['confidence']):.2f}",
                    (4, crop.shape[0] - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
                    cv2.LINE_AA)
        # Resize so all crops are the same size in the montage.
        target = (2 * args.crop_half_size, 2 * args.crop_half_size)
        crop = cv2.resize(crop, target, interpolation=cv2.INTER_AREA)
        crops.append(crop)

    cap.release()

    sheet = _montage(crops, cols=args.cols)
    args.output_png.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.output_png), sheet)
    print(f"Wrote {args.output_png} with {len(crops)} crops")
    print(f"  new detections: {len(new_rows)} between "
          f"{args.higher_csv.name} (excluded) and {args.lower_csv.name} (included)")
    print(f"  conf range: {min(_f(r['confidence']) for r in new_rows):.3f} - "
          f"{max(_f(r['confidence']) for r in new_rows):.3f}")


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover