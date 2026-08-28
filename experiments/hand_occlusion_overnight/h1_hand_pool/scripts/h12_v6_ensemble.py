#!/usr/bin/env python3
"""H12 v6 - ensemble of v2 (event-log) and v5 (detector) signals.

H12 v2 uses catch/throw events to classify CASCADE vs FOUNTAIN. It's
correct in windows with >=3 events, but the event log is too sparse
on identical (8 events total) and YouTube (1 event). Late-phase
windows are right-hand-biased and v2 misclassifies cascade as
fountain.

H12 v5 uses per-frame horizontal-velocity directions of airborne
balls. It's a per-frame spatial signal but noisy: juggling
hands move during cascade, causing temporary vx=0 or single
direction. W=10 smoothing helps.

Hypothesis: combining the two signals with a confidence-weighted
ensemble should give the best of both:
  - When v2 has 3+ events in window AND v5 is clear (1 or 2 dirs):
    v2 wins (high confidence).
  - When v2 has 1-2 events (UNCONFIRMED) AND v5 is clear:
    v5 wins (per-frame signal is more reliable than sparse events).
  - When v2 has 0 events (NO_BALL/UNKNOWN) AND v5 is clear:
    v5 wins.
  - When v2 and v5 disagree: report MIXED_ENSEMBLE with conf = average.

This addresses the master §17 priority "ensemble v2 + v5 with v2's
high-confidence windows anchoring v5's per-frame signal".

Algorithm (per frame):
  1. Load v2 pattern + confidence + n_window_events.
  2. Load v5 pattern + confidence + smoothed_dirs.
  3. Decide winner:
     a. v2 CONFIDENT and v5 CONFIDENT and agree: v2 wins (high conf).
     b. v2 CONFIDENT and v5 CONFIDENT and disagree: MIXED_ENSEMBLE.
     c. v2 CONFIDENT, v5 unconfident: v2 wins.
     d. v2 UNCONFIRMED, v5 CONFIDENT: v5 wins.
     e. Both unconfident: UNKNOWN.
  4. Output: pattern_v6, confidence_v6, source (v2/v5/ensemble).
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

# v2 confidence thresholds
V2_CONFIDENT = 0.5  # at or above this, v2 is "confident"
V2_UNCONF_BELOW = 0.3  # below this, v2 is "unconfident" (mostly UNCONFIRMED)
# v5 confidence thresholds
V5_CONFIDENT = 0.6  # at or above this, v5 is "confident"
V5_UNCONF_BELOW = 0.4  # below this, v5 is "unconfident"


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


def v2_is_confident(v2: dict) -> bool:
    return v2["confidence"] >= V2_CONFIDENT and v2["pattern"] not in (
        "UNKNOWN", "MIXED_3+_UNCONFIRMED")


def v5_is_confident(v5: dict) -> bool:
    return v5["confidence"] >= V5_CONFIDENT and v5["pattern"] not in (
        "UNKNOWN", "MIXED_3+_UNCONFIRMED")


def patterns_agree(p1: str, p2: str) -> bool:
    """Two patterns agree if they're the same class (cascade, fountain, etc.)."""
    if p1 == p2:
        return True
    # Detector-suffix variants should match their non-suffix versions
    p1_base = p1.replace("_DETECTOR_SMOOTHED", "")
    p2_base = p2.replace("_DETECTOR_SMOOTHED", "")
    return p1_base == p2_base


def classify_3ball_relationship(v2_pattern: str, v5_pattern: str) -> str:
    """For 3+ ball patterns, what does v2 say vs v5 say?"""
    cascade_like = ("CASCADE" in v2_pattern or "CASCADE" in v5_pattern)
    fountain_like = ("FOUNTAIN" in v2_pattern or "FOUNTAIN" in v5_pattern)
    if cascade_like and fountain_like:
        return "DISAGREE"
    if cascade_like:
        return "CASCADE"
    if fountain_like:
        return "FOUNTAIN"
    return "MIXED"


def ensemble(f: int, v2: dict, v5: dict) -> dict:
    """Combine v2 and v5 into a single v6 classification."""
    n_total = max(v2.get("n_total", 0), v5.get("n_total", 0))
    p2 = v2["pattern"]
    p5 = v5["pattern"]
    c2 = v2["confidence"]
    c5 = v5["confidence"]
    v2_conf = v2_is_confident(v2)
    v5_conf = v5_is_confident(v5)

    # Decision tree
    if n_total == 0:
        return {"pattern_v6": "NO_BALL", "confidence_v6": 1.0,
                "source": "no_ball", "agree": True, "v2_confident": v2_conf,
                "v5_confident": v5_conf}

    if n_total < 3:
        # For 1-2 ball frames, both v2 and v5 should agree
        if patterns_agree(p2, p5):
            conf = (c2 + c5) / 2
            return {"pattern_v6": p2, "confidence_v6": round(conf, 3),
                    "source": "agree", "agree": True,
                    "v2_confident": v2_conf, "v5_confident": v5_conf}
        # Disagree on 1-2 ball: take the more confident
        if c2 >= c5:
            return {"pattern_v6": p2, "confidence_v6": round(c2 * 0.8, 3),
                    "source": "v2_wins_low_n", "agree": False,
                    "v2_confident": v2_conf, "v5_confident": v5_conf}
        return {"pattern_v6": p5, "confidence_v6": round(c5 * 0.8, 3),
                "source": "v5_wins_low_n", "agree": False,
                "v2_confident": v2_conf, "v5_confident": v5_conf}

    # 3+ balls
    rel = classify_3ball_relationship(p2, p5)
    if rel == "DISAGREE":
        # CASCADE vs FOUNTAIN: report MIXED_ENSEMBLE with conf = (c2 + c5) / 2
        return {"pattern_v6": "MIXED_3+_ENSEMBLE", "confidence_v6": round((c2 + c5) / 2, 3),
                "source": "ensemble_disagree", "agree": False,
                "v2_confident": v2_conf, "v5_confident": v5_conf}
    # rel is CASCADE, FOUNTAIN, or MIXED
    target_pattern = "CASCADE_3+" if rel == "CASCADE" else (
        "FOUNTAIN_3+" if rel == "FOUNTAIN" else "MIXED_3+")
    if v2_conf and v5_conf:
        # Both confident and agree: v2 wins (event-log is more
        # semantically meaningful)
        return {"pattern_v6": target_pattern, "confidence_v6": round(max(c2, c5), 3),
                "source": "v2+v5_agree", "agree": True,
                "v2_confident": v2_conf, "v5_confident": v5_conf}
    if v2_conf and not v5_conf:
        return {"pattern_v6": target_pattern, "confidence_v6": round(c2 * 0.9, 3),
                "source": "v2_confident", "agree": True,
                "v2_confident": v2_conf, "v5_confident": v5_conf}
    if v5_conf and not v2_conf:
        return {"pattern_v6": target_pattern, "confidence_v6": round(c5 * 0.9, 3),
                "source": "v5_confident", "agree": True,
                "v2_confident": v2_conf, "v5_confident": v5_conf}
    # Both unconfident
    return {"pattern_v6": "MIXED_3+_UNCONFIRMED",
            "confidence_v6": round((c2 + c5) / 2, 3),
            "source": "both_unconf", "agree": False,
            "v2_confident": v2_conf, "v5_confident": v5_conf}


def detect_phase_boundaries(results: list[dict]) -> list[dict]:
    if not results:
        return []
    phases = []
    current_pattern = None
    phase_start = None
    phase_confs = []
    for r in results:
        if r["pattern_v6"] != current_pattern:
            if current_pattern is not None:
                phases.append({
                    "start_frame": phase_start,
                    "end_frame": r["frame"] - 1,
                    "pattern": current_pattern,
                    "n_frames": r["frame"] - phase_start,
                    "avg_confidence": round(sum(phase_confs) / len(phase_confs), 3)
                })
            current_pattern = r["pattern_v6"]
            phase_start = r["frame"]
            phase_confs = [r["confidence_v6"]]
        else:
            phase_confs.append(r["confidence_v6"])
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
        print(f"\n=== {stem} (H12 v6 ensemble of v2 + v5) ===")
        v2_data = load_v2(stem)
        v5_data = load_v5(stem)
        # Build frame set
        frames = sorted(set(v2_data.keys()) & set(v5_data.keys()))
        # Classify each frame
        results = []
        pattern_counts = defaultdict(int)
        source_counts = defaultdict(int)
        for f in frames:
            v2 = v2_data[f]
            v5 = v5_data[f]
            res = ensemble(f, v2, v5)
            res["frame"] = f
            res["v2_pattern"] = v2["pattern"]
            res["v2_confidence"] = round(v2["confidence"], 3)
            res["v5_pattern"] = v5["pattern"]
            res["v5_confidence"] = round(v5["confidence"], 3)
            res["smoothed_dirs"] = v5["smoothed_dirs"]
            res["n_total"] = v2["n_total"]
            results.append(res)
            pattern_counts[res["pattern_v6"]] += 1
            source_counts[res["source"]] += 1
        n_total_frames = len(results)
        print(f"  Total frames: {n_total_frames}")
        print(f"  Pattern distribution:")
        for p, n in sorted(pattern_counts.items(), key=lambda x: -x[1]):
            print(f"    {p}: {n}/{n_total_frames} = {100*n/n_total_frames:.1f}%")
        print(f"  Source distribution:")
        for s, n in sorted(source_counts.items(), key=lambda x: -x[1]):
            print(f"    {s}: {n}/{n_total_frames} = {100*n/n_total_frames:.1f}%")
        # Compare to v2 alone and v5 alone
        v2_pat = defaultdict(int)
        v5_pat = defaultdict(int)
        for r in results:
            v2_pat[r["v2_pattern"]] += 1
            v5_pat[r["v5_pattern"]] += 1
        # Phases
        phases = detect_phase_boundaries(results)
        # Substantial phases
        sub_phases = [p for p in phases if p["n_frames"] >= 20]
        print(f"  Substantial phases (n_frames >= 20): {len(sub_phases)}")
        for p in sub_phases:
            print(f"    f={p['start_frame']}-{p['end_frame']} {p['pattern']} "
                  f"n={p['n_frames']} conf={p['avg_confidence']}")
        # Persist
        out_csv = H1_DATA / f"pattern_inference_v6_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            fieldnames = list(results[0].keys())
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(results)
        print(f"  wrote: {out_csv.name}")
        out_phases = H1_DATA / f"pattern_phases_v6_{stem}.csv"
        with out_phases.open("w", newline="") as fh:
            fieldnames = ["start_frame", "end_frame", "pattern", "n_frames",
                          "avg_confidence"]
            w = csv.DictWriter(fh, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(phases)
        print(f"  wrote: {out_phases.name}")
        summary["videos"][stem] = {
            "n_total_frames": n_total_frames,
            "v6_pattern_counts": dict(pattern_counts),
            "v6_pct_patterns": {p: round(100 * n / n_total_frames, 1)
                                 for p, n in pattern_counts.items()},
            "source_counts": dict(source_counts),
            "n_substantial_phases": len(sub_phases),
            "sub_phases": sub_phases,
            "v2_pattern_counts": dict(v2_pat),
            "v5_pattern_counts": dict(v5_pat),
        }
    out = H1_DATA / "h12_v6_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
