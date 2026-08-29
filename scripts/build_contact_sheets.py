#!/usr/bin/env python3
"""Build compact contact-sheet images for segmentation visual review.

For a given (video, segmentation-overlay-MP4) pair this script samples frames
at fixed intervals, then groups them into labelled contact sheets:

  * ``clean_airborne``  – frames where 1+ instance was detected and the
                          bbox center y is well above the lower third of the
                          frame (likely airborne, not at hand height).
  * ``blurred_or_large`` – frames where the bbox aspect ratio or area is
                          unusually large (motion-blurred or close-up).
  * ``near_hand_height`` – frames where at least one instance's bbox center
                          y is in the lower third of the frame (catch / throw
                          vicinity).
  * ``large_count`` – frames where the per-frame instance count is in the
                      upper tail of the distribution.
  * ``occlusion_like`` – frames where the bbox area is large relative to the
                         mask area (suggests partial occlusion), implemented
                         as a high (bbox_area / mask_area) ratio.
  * ``seg_vs_det_diff`` – frames where the segmentation-only overlay shows
                          clearly different mask behaviour than the
                          bbox-only detector overlay for the same source
                          frame.

The seg-vs-det-diff comparison reads the seg overlay MP4 and the det overlay
MP4 in lockstep and selects frames where they differ visually (a coarse but
informative heuristic: number of distinct colored bbox rectangles differs
materially).

Each contact sheet is written as a single PNG containing a grid of cropped
tiles.  Output directory: ``outputs/detector_seg_comparison/contact_sheets/``.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

import cv2
import numpy as np

TILE_SIZE = 256
COLS = 6
MAX_PER_CATEGORY = 18


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _frame_count(path: Path) -> int:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        return 0
    count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    return count


def _crop_tile(frame: np.ndarray, cx: float, cy: float, size: int = TILE_SIZE) -> np.ndarray:
    h, w = frame.shape[:2]
    half = size // 2
    x0 = int(round(cx)) - half
    y0 = int(round(cy)) - half
    x0 = max(0, min(w - size, x0))
    y0 = max(0, min(h - size, y0))
    if x0 < 0:
        x0 = 0
    if y0 < 0:
        y0 = 0
    if x0 + size > w:
        x0 = w - size
    if y0 + size > h:
        y0 = h - size
    return frame[y0 : y0 + size, x0 : x0 + size].copy()


def _save_sheet(tiles: list[tuple[str, np.ndarray]], output_path: Path, title: str) -> None:
    if not tiles:
        print(f"[skip] {title}: no tiles")
        return
    rows = (len(tiles) + COLS - 1) // COLS
    sheet = np.full((rows * TILE_SIZE, COLS * TILE_SIZE, 3), 30, dtype=np.uint8)
    for index, (label, tile) in enumerate(tiles):
        r, c = divmod(index, COLS)
        y = r * TILE_SIZE
        x = c * TILE_SIZE
        sheet[y : y + TILE_SIZE, x : x + TILE_SIZE] = tile
        cv2.rectangle(sheet, (x, y), (x + TILE_SIZE, y + TILE_SIZE), (220, 220, 220), 1)
        cv2.putText(
            sheet,
            label,
            (x + 6, y + 20),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    # Title bar
    bar = np.full((28, sheet.shape[1], 3), 20, dtype=np.uint8)
    cv2.putText(
        bar,
        title,
        (10, 20),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    sheet = np.vstack((bar, sheet))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), sheet)
    print(f"[ok]   {title}: {len(tiles)} tiles -> {output_path}")


def _sample_frame(
    video_path: Path,
    frame_index: int,
) -> np.ndarray | None:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        cap.release()
        return None
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None
    return frame


def _load_seg_frame(
    overlay_path: Path,
    frame_index: int,
) -> np.ndarray | None:
    cap = cv2.VideoCapture(str(overlay_path))
    if not cap.isOpened():
        cap.release()
        return None
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None
    return frame


def _bbox_area(row: dict[str, str]) -> float:
    return float(row["width"]) * float(row["height"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build segmentation contact sheets.")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--seg-overlay", type=Path, required=True)
    parser.add_argument(
        "--det-overlay",
        type=Path,
        required=False,
        help="Optional detector-only overlay (e.g. yolo26l) for the seg-vs-det comparison.",
    )
    parser.add_argument("--instances-csv", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "outputs" / "detector_seg_comparison" / "contact_sheets",
    )
    parser.add_argument("--stem", required=True, help="Filename prefix for the contact sheets.")
    parser.add_argument(
        "--sample-stride",
        type=int,
        default=15,
        help="Sample one frame every N frames of the source video.",
    )
    args = parser.parse_args()

    instances = _read_csv(args.instances_csv)
    if not instances:
        print(f"No instances found in {args.instances_csv}")
        return

    by_frame: dict[int, list[dict[str, str]]] = {}
    for row in instances:
        by_frame.setdefault(int(row["frame"]), []).append(row)

    frame_indices = sorted(by_frame)
    total_frames = _frame_count(args.video)
    sampled = [f for f in frame_indices if f % args.sample_stride == 0]

    # Categorize sampled frames.
    airborne: list[tuple[str, np.ndarray]] = []
    large_or_blurred: list[tuple[str, np.ndarray]] = []
    near_hand: list[tuple[str, np.ndarray]] = []
    catch_throw: list[tuple[str, np.ndarray]] = []
    high_count: list[tuple[str, np.ndarray]] = []
    low_mask_coverage: list[tuple[str, np.ndarray]] = []
    seg_vs_det_diff: list[tuple[str, np.ndarray]] = []

    counts = [len(by_frame[f]) for f in frame_indices]
    count_threshold_high = max(3, int(np.percentile(counts, 90))) if counts else 99
    # Top 10% of bbox areas (used to flag motion-blurred or close-up frames).
    all_bbox_areas = [
        float(r["width"]) * float(r["height"])
        for r in instances
    ]
    p90_bbox_area = (
        sorted(all_bbox_areas)[int(0.9 * len(all_bbox_areas))]
        if all_bbox_areas
        else float("inf")
    )

    for frame_index in sampled:
        rows = by_frame[frame_index]
        if not rows:
            continue
        source_frame = _sample_frame(args.video, frame_index)
        if source_frame is None:
            continue
        h, w = source_frame.shape[:2]
        seg_overlay = _load_seg_frame(args.seg_overlay, frame_index)
        if seg_overlay is None:
            continue
        # Build per-frame stats
        for row in rows:
            cx = (float(row["x1"]) + float(row["x2"])) / 2.0
            cy = (float(row["y1"]) + float(row["y2"])) / 2.0
            bbox_area = _bbox_area(row)
            mask_area = float(row.get("mask_area_px") or 0)
            ratio = (mask_area / bbox_area) if bbox_area > 0 else 0.0
            label = f"f{frame_index} conf{float(row['confidence']):.2f}"

            # Airborne: center y in upper half.
            if cy < h * 0.55:
                tile = _crop_tile(seg_overlay, cx, cy)
                airborne.append((label, tile))

            # Near hand: lower third.
            if cy > h * 0.66:
                tile = _crop_tile(seg_overlay, cx, cy)
                near_hand.append((label, tile))

            # Catch/throw band: middle-lower region (between airborne and
            # hand-occluded).  This is where the ball is being held, released,
            # or caught.
            if h * 0.5 <= cy <= h * 0.78:
                tile = _crop_tile(seg_overlay, cx, cy)
                catch_throw.append((label, tile))

            # Blurred or large bbox: top 10% of bbox areas.
            if bbox_area > p90_bbox_area:
                tile = _crop_tile(seg_overlay, cx, cy)
                large_or_blurred.append((label + " big", tile))

            # Mask coverage: ratio of mask area to bbox area.  Low ratio
            # suggests occlusion or mask loss.  We use a permissive threshold
            # so we actually collect these rare events.
            if 0 < ratio < 0.6:
                tile = _crop_tile(seg_overlay, cx, cy)
                low_mask_coverage.append((label + f" r{ratio:.2f}", tile))

        # High instance count.
        if len(rows) >= count_threshold_high:
            # Use the center of the cluster — average of instance centers.
            cxs = [(float(r["x1"]) + float(r["x2"])) / 2.0 for r in rows]
            cys = [(float(r["y1"]) + float(r["y2"])) / 2.0 for r in rows]
            avg_cx = float(np.mean(cxs))
            avg_cy = float(np.mean(cys))
            tile = _crop_tile(seg_overlay, avg_cx, avg_cy, size=TILE_SIZE)
            high_count.append((f"f{frame_index} n={len(rows)}", tile))

        # Seg vs det diff: if the bbox-only detector overlay has materially
        # fewer visible boxes than the seg overlay's instance count.
        if args.det_overlay is not None:
            det_overlay = _load_seg_frame(args.det_overlay, frame_index)
            if det_overlay is not None:
                # Heuristic: count distinct strongly-saturated pixels in each
                # overlay.  The seg overlay should be visibly more colorful.
                seg_colored = int((seg_overlay.max(axis=2) - seg_overlay.min(axis=2) > 40).sum())
                det_colored = int((det_overlay.max(axis=2) - det_overlay.min(axis=2) > 40).sum())
                if abs(seg_colored - det_colored) > 1500 and seg_colored > det_colored:
                    # Use the centroid of the strongest mask color cluster.
                    cxs = [(float(r["x1"]) + float(r["x2"])) / 2.0 for r in rows]
                    cys = [(float(r["y1"]) + float(r["y2"])) / 2.0 for r in rows]
                    if cxs:
                        avg_cx = float(np.mean(cxs))
                        avg_cy = float(np.mean(cys))
                        tile = _crop_tile(seg_overlay, avg_cx, avg_cy, size=TILE_SIZE)
                        seg_vs_det_diff.append((f"f{frame_index} seg-det+{seg_colored-det_colored}", tile))

    # Trim to MAX_PER_CATEGORY.
    airborne = airborne[:MAX_PER_CATEGORY]
    large_or_blurred = large_or_blurred[:MAX_PER_CATEGORY]
    near_hand = near_hand[:MAX_PER_CATEGORY]
    catch_throw = catch_throw[:MAX_PER_CATEGORY]
    high_count = high_count[:MAX_PER_CATEGORY]
    low_mask_coverage = low_mask_coverage[:MAX_PER_CATEGORY]
    seg_vs_det_diff = seg_vs_det_diff[:MAX_PER_CATEGORY]

    out = args.output_dir
    _save_sheet(airborne, out / f"{args.stem}_01_clean_airborne.png", "clean airborne balls (seg)")
    _save_sheet(large_or_blurred, out / f"{args.stem}_02_large_or_blurred.png", "large / motion-blurred instances")
    _save_sheet(near_hand, out / f"{args.stem}_03_near_hand_height.png", "near hand height (catches/throws)")
    _save_sheet(catch_throw, out / f"{args.stem}_04_catch_throw_band.png", "catch / throw band (center_y 0.5..0.78)")
    _save_sheet(high_count, out / f"{args.stem}_05_high_instance_count.png", "high instance count frames")
    _save_sheet(low_mask_coverage, out / f"{args.stem}_06_low_mask_coverage.png", "low mask coverage (possible occlusion)")
    if args.det_overlay is not None:
        _save_sheet(seg_vs_det_diff, out / f"{args.stem}_07_seg_vs_det_diff.png", "seg-vs-det visual difference")


if __name__ == "__main__":
    main()
