#!/usr/bin/env python3
"""H12 v6b - improved ensemble with confidence-weighted decision.

v6 reported MIXED_3+_ENSEMBLE for all frames where v2 and v5 disagreed.
But many of these disagreements are due to v2's late-phase FOUNTAIN
misclassification (low confidence 0.42-0.63) while v5's CASCADE
classification is uniformly confident (0.70).

v6b adds a confidence asymmetry rule:
  - If v2 conf > v5 conf + 0.1: v2 wins.
  - If v5 conf > v2 conf + 0.1: v5 wins.
  - If |v2 conf - v5 conf| <= 0.1: MIXED_3+_ENSEMBLE.

This way, when v5 is meaningfully more confident than v2, v6b
propagates v5's answer. When confidences are similar, v6b stays
honest with MIXED.

The asymmetry threshold (0.1) is small enough that genuinely
uncertain frames still report MIXED.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

# Confidence asymmetry threshold
CONF_ASYMMETRY = 0.10


def load_v2(stem: str) -> dict:
    out = {}
    with (H1_DATA / f"pattern_inference_v2_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            f = int(r["frame"])
            out[f] = {
                "pattern": r["pattern"],
                "confidence": float(r["confidence"]),
                "n_window_events": int(r["n_window_events"]),
                "n_total": int(r["n_total"]),
                "avg_quality": float(r["avg_quality"]),
            }
    return out


def load_v5(stem: str) -> dict:
    out = {}
    with (H1_DATA / f"pattern_inference_v5_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            f = int(r["frame"])
            out[f] = {
                "pattern": r["pattern"],
                "confidence": float(r["confidence"]),
                "smoothed_dirs": int(r["smoothed_dirs"]),
                "n_total": int(r["n_total"]),
            }
    return out


def classify_3ball_relationship(v2_pattern: str, v5_pattern: str) -> str:
    cascade_like = ("CASCADE" in v2_pattern or "CASCADE" in v5_pattern)
    fountain_like = ("FOUNTAIN" in v2_pattern or "FOUNTAIN" in v5_pattern)
    if cascade_like and fountain_like:
        return "DISAGREE"
    if cascade_like:
        return "CASCADE"
    if fountain_like:
        return "FOUNTAIN"
    return "MIXED"


def ensemble_v6b(f: int, v2: dict, v5: dict) -> dict:
    """v6b: confidence-weighted ensemble for 3+ ball frames."""
    n_total = max(v2.get("n_total", 0), v5.get("n_total", 0))
    p2 = v2["pattern"]
    p5 = v5["pattern"]
    c2 = v2["confidence"]
    c5 = v5["confidence"]

    if n_total == 0:
        return {"pattern_v6b": "NO_BALL", "confidence_v6b": 1.0,
                "source": "no_ball"}
    if n_total < 3:
        # 1-2 ball frames: agreement, no disagreement
        p2b = p2.replace("_DETECTOR_SMOOTHED", "").replace("_UNCONFIRMED", "")
        p5b = p5.replace("_DETECTOR_SMOOTHED", "").replace("_UNCONFIRMED", "")
        if p2b == p5b:
            return {"pattern_v6b": p2, "confidence_v6b": round((c2 + c5) / 2, 3),
                    "source": "agree"}
        # Disagree: take more confident
        if c2 > c5:
            return {"pattern_v6b": p2, "confidence_v6b": round(c2 * 0.8, 3),
                    "source": "v2_wins_low_n"}
        return {"pattern_v6b": p5, "confidence_v6b": round(c5 * 0.8, 3),
                "source": "v5_wins_low_n"}

    # 3+ balls
    rel = classify_3ball_relationship(p2, p5)
    if rel != "DISAGREE":
        # Agree (or one is MIXED)
        target = "CASCADE_3+" if rel == "CASCADE" else (
            "FOUNTAIN_3+" if rel == "FOUNTAIN" else "MIXED_3+")
        return {"pattern_v6b": target,
                "confidence_v6b": round(max(c2, c5), 3),
                "source": "agree"}
    # DISAGREE: CASCADE vs FOUNTAIN
    # Confidence asymmetry rule
    if c5 > c2 + CONF_ASYMMETRY:
        # v5 meaningfully more confident
        if "CASCADE" in p5:
            return {"pattern_v6b": "CASCADE_3+",
                    "confidence_v6b": round(c5, 3),
                    "source": "v5_conf_wins_cascade"}
        return {"pattern_v6b": "FOUNTAIN_3+",
                "confidence_v6b": round(c5, 3),
                "source": "v5_conf_wins_fountain"}
    if c2 > c5 + CONF_ASYMMETRY:
        if "CASCADE" in p2:
            return {"pattern_v6b": "CASCADE_3+",
                    "confidence_v6b": round(c2, 3),
                    "source": "v2_conf_wins_cascade"}
        return {"pattern_v6b": "FOUNTAIN_3+",
                "confidence_v6b": round(c2, 3),
                "source": "v2_conf_wins_fountain"}
    # Confidence similar
    return {"pattern_v6b": "MIXED_3+_ENSEMBLE",
            "confidence_v6b": round((c2 + c5) / 2, 3),
            "source": "ensemble_disagree_close_conf"}


def detect_phase_boundaries(results: list[dict]) -> list[dict]:
    if not results:
        return []
    phases = []
    current_pattern = None
    phase_start = None
    phase_confs = []
    for r in results:
        if r["pattern_v6b"] != current_pattern:
            if current_pattern is not None:
                phases.append({
                    "start_frame": phase_start,
                    "end_frame": r["frame"] - 1,
                    "pattern": current_pattern,
                    "n_frames": r["frame"] - phase_start,
                    "avg_confidence": round(sum(phase_confs) / len(phase_confs), 3)
                })
            current_pattern = r["pattern_v6b"]
            phase_start = r["frame"]
            phase_confs = [r["confidence_v6b"]]
        else:
            phase_confs.append(r["confidence_v6b"])
    if current_pattern is not None:
        phases.append({
            "start_frame": phase_start,
            "end_frame": results[-1]["frame"],
            "pattern": current_pattern,
            "n_frames": results[-1]["frame"] - phase_start + 1,
            "avg_confidence": round(sum(phase_confs) / len(phase_confs), 3)
        })
    return phases


def main():
    summary = {"videos": {}}
    for stem in STEMS:
        print(f"\n=== {stem} (H12 v6b confidence-weighted ensemble) ===")
        v2_data = load_v2(stem)
        v5_data = load_v5(stem)
        frames = sorted(set(v2_data.keys()) & set(v5_data.keys()))
        results = []
        pattern_counts = defaultdict(int)
        source_counts = defaultdict(int)
        for f in frames:
            v2 = v2_data[f]
            v5 = v5_data[f]
            res = ensemble_v6b(f, v2, v5)
            res["frame"] = f
            res["v2_pattern"] = v2["pattern"]
            res["v2_confidence"] = round(v2["confidence"], 3)
            res["v5_pattern"] = v5["pattern"]
            res["v5_confidence"] = round(v5["confidence"], 3)
            res["smoothed_dirs"] = v5["smoothed_dirs"]
            res["n_total"] = v2["n_total"]
            results.append(res)
            pattern_counts[res["pattern_v6b"]] += 1
            source_counts[res["source"]] += 1
        n_total_frames = len(results)
        print(f"  Total frames: {n_total_frames}")
        print(f"  Pattern distribution:")
        for p, n in sorted(pattern_counts.items(), key=lambda x: -x[1]):
            print(f"    {p}: {n}/{n_total_frames} = {100*n/n_total_frames:.1f}%")
        print(f"  Source distribution:")
        for s, n in sorted(source_counts.items(), key=lambda x: -x[1]):
            print(f"    {s}: {n}/{n_total_frames} = {100*n/n_total_frames:.1f}%")
        # Phases
        phases = detect_phase_boundaries(results)
        sub_phases = [p for p in phases if p["n_frames"] >= 20]
        print(f"  Substantial phases (n_frames >= 20): {len(sub_phases)}")
        for p in sub_phases:
            print(f"    f={p['start_frame']}-{p['end_frame']} {p['pattern']} "
                  f"n={p['n_frames']} conf={p['avg_confidence']}")
        out_csv = H1_DATA / f"pattern_inference_v6b_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            fieldnames = list(results[0].keys())
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(results)
        print(f"  wrote: {out_csv.name}")
        out_phases = H1_DATA / f"pattern_phases_v6b_{stem}.csv"
        with out_phases.open("w", newline="") as fh:
            fieldnames = ["start_frame", "end_frame", "pattern", "n_frames",
                          "avg_confidence"]
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(phases)
        print(f"  wrote: {out_phases.name}")
        summary["videos"][stem] = {
            "n_total_frames": n_total_frames,
            "v6b_pattern_counts": dict(pattern_counts),
            "v6b_pct_patterns": {p: round(100 * n / n_total_frames, 1)
                                  for p, n in pattern_counts.items()},
            "source_counts": dict(source_counts),
            "n_substantial_phases": len(sub_phases),
            "sub_phases": sub_phases,
        }
    out = H1_DATA / "h12_v6b_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
