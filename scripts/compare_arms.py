#!/usr/bin/env python3
"""Compute and report the comparison metrics for the three model arms.

This script consumes the minimal-detection CSVs, the Norfair tracklet CSVs, and
the stitch candidate CSVs produced by the existing pipeline for each arm, and
emits:

  * a per-arm summary JSON (detection counts, Norfair stats, stitch stats,
    distance-between-bbox-center-and-mask-centroid for the segmentation arm
    only)
  * a single combined CSV with one row per (model, video) for the parts of
    the summary that are flat enough to tabulate

The comparison is purely structural — it does not claim that any one arm is
"correct" relative to a ground truth.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

MINIMAL_FIELDS = (
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
)
NORFAIR_FIELDS = (
    "frame",
    "time_seconds",
    "track_id",
    "confidence",
    "center_x",
    "center_y",
    "observed",
)
STITCH_FIELDS = (
    "source_tracklet",
    "candidate_tracklet",
    "gap_frames",
    "predicted_x",
    "predicted_y",
    "candidate_start_x",
    "candidate_start_y",
    "prediction_error",
    "source_end_frame",
    "candidate_start_frame",
    "end_velocity_x",
    "end_velocity_y",
    "candidate_rank",
)


def _f(value: str) -> float:
    return float(value)


def _read_csv(path: Path, required: tuple[str, ...]) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"No header in {path}")
        for field in required:
            if field not in reader.fieldnames:
                raise ValueError(f"{path} missing column {field!r}")
        return list(reader)


def detection_summary(rows: list[dict[str, str]], video_frame_count: int | None) -> dict:
    """Aggregate per-frame counts, confidence distribution, etc."""
    per_frame = Counter()
    confidences = []
    for row in rows:
        per_frame[int(row["frame"])] += 1
        confidences.append(_f(row["confidence"]))
    total = sum(per_frame.values())
    counts = list(per_frame.values())
    frames_seen = set(per_frame)
    distribution = {
        "0": 0,
        "1": 0,
        "2": 0,
        "3": 0,
        "4+": 0,
    }
    if video_frame_count is not None:
        for frame in range(video_frame_count):
            n = per_frame.get(frame, 0)
            if n >= 4:
                distribution["4+"] += 1
            else:
                distribution[str(n)] += 1
    confidences_sorted = sorted(confidences)
    conf_summary = {
        "n": len(confidences_sorted),
        "min": min(confidences_sorted) if confidences_sorted else None,
        "max": max(confidences_sorted) if confidences_sorted else None,
        "mean": statistics.fmean(confidences_sorted) if confidences_sorted else None,
        "median": statistics.median(confidences_sorted) if confidences_sorted else None,
    }
    return {
        "total_detections": total,
        "frames_with_any_detection": len(frames_seen),
        "mean_per_frame": (
            statistics.fmean(counts) if counts else 0.0
        ),
        "median_per_frame": (
            statistics.median(counts) if counts else 0.0
        ),
        "frame_count_distribution": distribution,
        "confidence": conf_summary,
    }


def mask_diagnostics(
    instances_rows: list[dict[str, str]], video_frame_count: int | None
) -> dict:
    areas: list[int] = []
    centroid_distances: list[float] = []
    valid_centroid = 0
    invalid_centroid = 0
    for row in instances_rows:
        try:
            area = int(row["mask_area_px"])
        except (TypeError, ValueError):
            area = 0
        areas.append(area)
        if row.get("mask_centroid_valid") == "1":
            valid_centroid += 1
            cx_b = _f(row["center_x"])
            cy_b = _f(row["center_y"])
            cx_m = _f(row["mask_centroid_x"])
            cy_m = _f(row["mask_centroid_y"])
            centroid_distances.append(math.hypot(cx_m - cx_b, cy_m - cy_b))
        else:
            invalid_centroid += 1
    sorted_areas = sorted(areas)
    sorted_dists = sorted(centroid_distances)
    n = len(areas)
    if sorted_areas:
        area_summary = {
            "n": n,
            "min": min(sorted_areas),
            "max": max(sorted_areas),
            "mean": statistics.fmean(sorted_areas),
            "median": statistics.median(sorted_areas),
            "p25": _percentile(sorted_areas, 25),
            "p75": _percentile(sorted_areas, 75),
            "p90": _percentile(sorted_areas, 90),
        }
    else:
        area_summary = {"n": 0}
    if sorted_dists:
        dist_summary = {
            "n": len(sorted_dists),
            "median": statistics.median(sorted_dists),
            "p75": _percentile(sorted_dists, 75),
            "p90": _percentile(sorted_dists, 90),
            "max": max(sorted_dists),
        }
    else:
        dist_summary = {"n": 0}
    return {
        "mask_area": area_summary,
        "bbox_to_mask_centroid_distance_px": dist_summary,
        "valid_centroid_rows": valid_centroid,
        "invalid_centroid_rows": invalid_centroid,
    }


def _percentile(sorted_values: list, pct: float) -> float:
    if not sorted_values:
        return float("nan")
    k = (len(sorted_values) - 1) * (pct / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_values[int(k)]
    return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)


def norfair_summary(rows: list[dict[str, str]]) -> dict:
    if not rows:
        return {
            "n_track_rows": 0,
            "n_unique_track_ids": 0,
            "observed_rows": 0,
            "predicted_rows": 0,
            "observed_fraction": 0.0,
            "track_length_distribution": {},
            "lifespan_distribution": {},
            "short_tracks_le_5": 0,
            "short_tracks_le_10": 0,
        }
    # Group rows by track_id.
    per_track_frames: dict[int, set[int]] = defaultdict(set)
    per_track_lifespan: dict[int, tuple[int, int]] = {}
    observed = 0
    predicted = 0
    for row in rows:
        track_id = int(row["track_id"])
        frame = int(row["frame"])
        per_track_frames[track_id].add(frame)
        # Lifespan = first frame .. last frame inclusive.
        if track_id in per_track_lifespan:
            fmin, fmax = per_track_lifespan[track_id]
            per_track_lifespan[track_id] = (min(fmin, frame), max(fmax, frame))
        else:
            per_track_lifespan[track_id] = (frame, frame)
        if row.get("observed") == "1":
            observed += 1
        else:
            predicted += 1
    observed_counts = [len(frames) for frames in per_track_frames.values()]
    lifespans = [
        fmax - fmin + 1 for fmin, fmax in per_track_lifespan.values()
    ]
    sorted_counts = sorted(observed_counts)
    sorted_lifespans = sorted(lifespans)

    def _stats(values: list[int]) -> dict:
        if not values:
            return {"n": 0}
        return {
            "n": len(values),
            "min": min(values),
            "max": max(values),
            "mean": statistics.fmean(values),
            "median": statistics.median(values),
            "p25": _percentile(sorted(values), 25),
            "p75": _percentile(sorted(values), 75),
        }

    total = observed + predicted
    return {
        "n_track_rows": len(rows),
        "n_unique_track_ids": len(per_track_frames),
        "observed_rows": observed,
        "predicted_rows": predicted,
        "observed_fraction": (observed / total) if total else 0.0,
        "observed_per_track": _stats(observed_counts),
        "lifespan": _stats(sorted_lifespans),
        "short_tracks_le_5": sum(1 for c in observed_counts if c <= 5),
        "short_tracks_le_10": sum(1 for c in observed_counts if c <= 10),
    }


def stitch_summary(rows: list[dict[str, str]]) -> dict:
    if not rows:
        return {
            "n_candidates": 0,
            "n_source_tracklets_with_candidates": 0,
            "gap_distribution": {},
            "rank1_prediction_error": {},
        }
    gap_values: list[int] = []
    rank1_errors: list[float] = []
    sources_with_candidates: set[int] = set()
    for row in rows:
        gap = int(row["gap_frames"])
        gap_values.append(gap)
        if int(row["candidate_rank"]) == 1:
            rank1_errors.append(_f(row["prediction_error"]))
            sources_with_candidates.add(int(row["source_tracklet"]))
    gap_counter = Counter(gap_values)
    gap_dist = {
        "min": min(gap_values),
        "max": max(gap_values),
        "mean": statistics.fmean(gap_values),
        "median": statistics.median(gap_values),
        "by_value": dict(sorted(gap_counter.items())),
    }
    if rank1_errors:
        sorted_errors = sorted(rank1_errors)
        rank1_summary = {
            "n": len(sorted_errors),
            "min": sorted_errors[0],
            "max": sorted_errors[-1],
            "mean": statistics.fmean(sorted_errors),
            "median": statistics.median(sorted_errors),
            "p25": _percentile(sorted_errors, 25),
            "p75": _percentile(sorted_errors, 75),
        }
    else:
        rank1_summary = {"n": 0}
    return {
        "n_candidates": len(rows),
        "n_source_tracklets_with_candidates": len(sources_with_candidates),
        "gap_distribution": gap_dist,
        "rank1_prediction_error": rank1_summary,
    }


def framewise_diff(
    a_rows: list[dict[str, str]], b_rows: list[dict[str, str]]
) -> dict:
    """How many frames differ in (0, 1, 2, 3, 4+) sports-ball counts between A
    and B?  Reports only the magnitude of the per-frame-count difference.
    """
    a_per_frame = Counter(int(r["frame"]) for r in a_rows)
    b_per_frame = Counter(int(r["frame"]) for r in b_rows)
    all_frames = set(a_per_frame) | set(b_per_frame)
    differences = Counter()
    for frame in all_frames:
        diff = abs(a_per_frame.get(frame, 0) - b_per_frame.get(frame, 0))
        if diff == 0:
            differences[0] += 1
        elif diff == 1:
            differences[1] += 1
        elif diff == 2:
            differences[2] += 1
        else:
            differences["3+"] += 1
    return {
        "frames_compared": len(all_frames),
        "abs_frame_count_difference_distribution": dict(differences),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute per-arm comparison metrics and write summary JSON/CSV."
    )
    parser.add_argument(
        "--arms",
        nargs="+",
        required=True,
        help="One or more arm specs in the form model:detections_csv[:norfair_csv[:stitch_csv[:instances_csv]]].",
    )
    parser.add_argument(
        "--video-name",
        action="append",
        default=[],
        help="Optional display name (repeatable, same order as --arms).",
    )
    parser.add_argument(
        "--video-frame-count",
        type=int,
        action="append",
        default=[],
        help="Optional frame count of the source video (for 0/1/2/3/4+ distribution).",
    )
    parser.add_argument(
        "--compare",
        nargs=2,
        action="append",
        default=[],
        metavar=("ARM_A", "ARM_B"),
        help="Add a framewise-detection-count diff between two arm keys (must match a key in --arms).",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=PROJECT_ROOT / "detections" / "detector_seg_comparison_summary.json",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=PROJECT_ROOT / "detections" / "detector_seg_comparison_summary.csv",
    )
    args = parser.parse_args()

    arms: dict[str, dict] = {}
    csv_paths: dict[str, dict[str, Path]] = {}
    for arm_spec in args.arms:
        parts = arm_spec.split(":")
        if len(parts) < 2:
            raise ValueError(
                f"Arm spec must be key:detections_csv[:norfair_csv[:stitch_csv[:instances_csv]]]: got {arm_spec!r}"
            )
        key = parts[0]
        paths = {
            "detections": Path(parts[1]),
        }
        if len(parts) >= 3 and parts[2]:
            paths["norfair"] = Path(parts[2])
        if len(parts) >= 4 and parts[3]:
            paths["stitch"] = Path(parts[3])
        if len(parts) >= 5 and parts[4]:
            paths["instances"] = Path(parts[4])
        csv_paths[key] = paths
        arms[key] = {}

    video_names = args.video_name or list(arms.keys())
    if len(video_names) != len(arms):
        raise ValueError(
            f"--video-name count ({len(video_names)}) must match arm count ({len(arms)})"
        )
    video_frame_counts = args.video_frame_count or [None] * len(arms)
    if len(video_frame_counts) != len(arms):
        raise ValueError(
            f"--video-frame-count count ({len(video_frame_counts)}) must match arm count ({len(arms)})"
        )

    for (key, paths), video_name, frame_count in zip(
        csv_paths.items(), video_names, video_frame_counts
    ):
        det_rows = _read_csv(paths["detections"], MINIMAL_FIELDS)
        arms[key]["video_name"] = video_name
        arms[key]["detections_csv"] = str(paths["detections"])
        arms[key]["detection"] = detection_summary(det_rows, frame_count)
        if "norfair" in paths:
            n_rows = _read_csv(paths["norfair"], NORFAIR_FIELDS)
            arms[key]["norfair_csv"] = str(paths["norfair"])
            arms[key]["norfair"] = norfair_summary(n_rows)
        if "stitch" in paths:
            s_rows = _read_csv(paths["stitch"], STITCH_FIELDS)
            arms[key]["stitch_csv"] = str(paths["stitch"])
            arms[key]["stitch"] = stitch_summary(s_rows)
        if "instances" in paths:
            i_rows = _read_csv(paths["instances"], MINIMAL_FIELDS)
            arms[key]["instances_csv"] = str(paths["instances"])
            arms[key]["mask"] = mask_diagnostics(i_rows, frame_count)

    for compare_pair in args.compare:
        a, b = compare_pair
        if a not in csv_paths or b not in csv_paths:
            raise ValueError(
                f"Compare arm key missing in --arms: {a!r} or {b!r}"
            )
        a_rows = _read_csv(csv_paths[a]["detections"], MINIMAL_FIELDS)
        b_rows = _read_csv(csv_paths[b]["detections"], MINIMAL_FIELDS)
        arms.setdefault("comparisons", {})[f"{a}_vs_{b}"] = framewise_diff(
            a_rows, b_rows
        )

    # JSON does not allow mixed-type dict keys; stringify all keys in
    # counters and comparison distributions.
    def _stringify(obj):
        if isinstance(obj, dict):
            return {str(k): _stringify(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_stringify(v) for v in obj]
        return obj

    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(_stringify(arms), indent=2, sort_keys=True), encoding="utf-8"
    )
    print(f"Wrote summary JSON: {args.output_json}")

    # CSV: one row per arm with the most reportable scalars.
    flat_rows = []
    for key, payload in arms.items():
        if key == "comparisons":
            continue
        detection = payload.get("detection", {})
        norfair = payload.get("norfair", {})
        stitch = payload.get("stitch", {})
        mask = payload.get("mask", {})
        conf = detection.get("confidence", {})
        n_obs = norfair.get("observed_per_track", {})
        lifespan = norfair.get("lifespan", {})
        gap = stitch.get("gap_distribution", {})
        rank1 = stitch.get("rank1_prediction_error", {})
        area = mask.get("mask_area", {})
        dist = mask.get("bbox_to_mask_centroid_distance_px", {})
        flat_rows.append(
            {
                "arm": key,
                "video": payload.get("video_name", ""),
                "total_detections": detection.get("total_detections"),
                "mean_per_frame": detection.get("mean_per_frame"),
                "median_per_frame": detection.get("median_per_frame"),
                "frames_with_0": detection.get("frame_count_distribution", {}).get("0"),
                "frames_with_1": detection.get("frame_count_distribution", {}).get("1"),
                "frames_with_2": detection.get("frame_count_distribution", {}).get("2"),
                "frames_with_3": detection.get("frame_count_distribution", {}).get("3"),
                "frames_with_4+": detection.get("frame_count_distribution", {}).get("4+"),
                "conf_mean": conf.get("mean"),
                "conf_median": conf.get("median"),
                "n_unique_track_ids": norfair.get("n_unique_track_ids"),
                "n_track_rows": norfair.get("n_track_rows"),
                "observed_fraction": norfair.get("observed_fraction"),
                "track_observed_median": n_obs.get("median"),
                "track_observed_mean": n_obs.get("mean"),
                "lifespan_median": lifespan.get("median"),
                "lifespan_max": lifespan.get("max"),
                "short_tracks_le_5": norfair.get("short_tracks_le_5"),
                "short_tracks_le_10": norfair.get("short_tracks_le_10"),
                "n_stitch_candidates": stitch.get("n_candidates"),
                "n_stitch_sources": stitch.get("n_source_tracklets_with_candidates"),
                "stitch_gap_median": gap.get("median"),
                "stitch_gap_max": gap.get("max"),
                "rank1_error_median": rank1.get("median"),
                "rank1_error_p75": rank1.get("p75"),
                "mask_area_median": area.get("median"),
                "mask_area_p90": area.get("p90"),
                "bbox_to_centroid_dist_median": dist.get("median"),
                "bbox_to_centroid_dist_p90": dist.get("p90"),
            }
        )
    if flat_rows:
        fieldnames = list(flat_rows[0].keys())
        with args.output_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flat_rows)
        print(f"Wrote summary CSV: {args.output_csv}")


if __name__ == "__main__":
    main()
