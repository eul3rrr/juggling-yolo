#!/usr/bin/env python3
"""
H90 v2 — Refined per-phase decision rules.

Based on H90 v1 data:
- Rule A (c40_pct_ge3 < 0.30 AND drop > 0.25) catches f=2-71 and f=482-594
  (both FPs) but ALSO catches f=411-450 (JUGGLING) — false positive
- Rule B (c40_pct_ge3 < 0.30 AND c40_mean_aloft < 1.5) — over-rejects 3 phases
- Rule C (c40_max_aloft <= 2) — too strict (catches only f=549-578 FN on ident)

The KEY new signal from v1: c40_max_aloft discriminates YouTube FPs from real juggling!
- f=482-594 STATIC_HOLD: c40_max_aloft=4 (4 balls aloft even after conf filter)
- f=2-71 STATIC_DEMO: c40_max_aloft=3
- All YouTube real JUGGLING: c40_max_aloft=3 (with one exception at f=114-255 startup, max=3)
- The trick: f=482-594 has max=4 AND drop_pct_ge3 > 0.30 (drop=0.30)

Refined Rule E: REJECT if (c40_pct_ge3 < 0.40) AND ((c40_max_aloft >= 4) OR (drop > 0.35))
- Catches f=482-594 (max=4, drop=0.30) -- WRONG, drop=0.30 is NOT > 0.35
- Catches f=2-71 (max=3, drop=0.39)
- Misses f=800-861 (max=3, drop=0.34)

Let me explore more carefully.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"

# Load H90 v1 features
with open(f"{H1_DATA}/h90_per_phase_features.json") as f:
    h90 = json.load(f)

REAL_VERDICTS = ("FOUNTAIN", "JUGGLING", "JUGGLING_STARTUP")
MISCLASS_VERDICTS = ("MANIPULATION", "STATIC_HOLD", "OTHER_CROSSED_ARM",
                     "OTHER_STATIC_HOLD", "CASCADE_REAL", "STATIC_DEMO")


def h82_v1_catches(key):
    """H82 v1 + H87 catches these 4 identical misclassifications:
    - f=685-716: H87
    - f=733-766: H74v2
    - f=890-936: H78
    - f=1029-1049: H74v2
    """
    (stem, start, end) = key
    if stem.startswith("ident"):
        if (start, end) in [(685, 716), (733, 766), (890, 936), (1029, 1049)]:
            return True
    return False


# Print all features for the YouTube borderline phases
print("=" * 80)
print("H90 v2 — Refined per-phase rules")
print("=" * 80)

# Show full feature set for YouTube borderline phases
print("\nFull feature set for YouTube phases (focusing on c40 max/frac/std):")
for k, v in sorted(h90.items()):
    if "youtube" not in k:
        continue
    feats = v['feats']
    c4 = feats.get('c40', {}) or {}
    c0 = feats.get('c00', {}) or {}
    drop = feats.get('drop_pct_ge3', 0)
    print(f"  {k[-25:]:<25} {v['gt'][1]:<22} c40: maxA={c4.get('max_aloft'):>2} frac@max={c4.get('frac_at_max', 0):.2f} std={c4.get('std_aloft', 0):.2f} pct_ge3={c4.get('pct_ge3', 0):.2f} mA={c4.get('mean_aloft', 0):.2f} | drop={drop:.2f}")

# Now try a wider grid of rules
print("\n=== Sensitivity grid: REJECT if c40_pct_ge3 < thr AND <some_other_signal> ===")

# Print existing rule A performance in detail first
def evaluate_rule(rejected_fn, label):
    TP = TN = FP = FN = 0
    detail = []
    for k, v in h90.items():
        key = tuple(k.rsplit("_", 2)[0].rsplit("_", 1)[0].rsplit("_", 1)) if False else None
        # Just parse the key back
        parts = k.split("_")
        # The stem and frame range parts
        # Find the last two underscores
        # k format: identical_balls_trick_000_018_263_312
        if "identical" in k:
            stem = "identical_balls_trick_000_018"
            start = int(parts[-2])
            end = int(parts[-1])
        else:
            stem = "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090"
            start = int(parts[-2])
            end = int(parts[-1])
        key = (stem, start, end)
        feats = v['feats']
        verdict = v['gt'][1]
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS

        if h82_v1_catches(key):
            if is_misclass:
                TN += 1
            elif is_real:
                # H82 shouldn't FN real, but log it
                pass
            continue
        rejected = rejected_fn(feats)
        if is_real and not rejected:
            TP += 1
        elif is_misclass and rejected:
            TN += 1
        elif is_misclass and not rejected:
            FP += 1
        elif is_real and rejected:
            FN += 1
        detail.append((key, verdict, rejected, is_real, is_misclass))
    p = TP / max(1, TP+FP)
    r = TP / max(1, TP+FN)
    acc = (TP+TN) / max(1, TP+TN+FP+FN)
    print(f"\n  {label}: TP={TP} TN={TN} FP={FP} FN={FN} P={p:.3f} R={r:.3f} acc={acc:.3f}")
    return TP, TN, FP, FN, detail


# Test: REJECT if c40_pct_ge3 < 0.40 AND c40_max_aloft >= 4
def rule_e1(feats):
    c4 = feats.get('c40', {}) or {}
    return c4.get('pct_ge3', 1.0) < 0.40 and c4.get('max_aloft', 0) >= 4

evaluate_rule(rule_e1, "Rule E1: c40_pct_ge3 < 0.40 AND c40_max_aloft >= 4")

# Test: REJECT if c40_pct_ge3 < 0.40 AND drop_pct_ge3 > 0.35
def rule_e2(feats):
    c4 = feats.get('c40', {}) or {}
    return c4.get('pct_ge3', 1.0) < 0.40 and feats.get('drop_pct_ge3', 0) > 0.35

evaluate_rule(rule_e2, "Rule E2: c40_pct_ge3 < 0.40 AND drop > 0.35")

# Test: REJECT if c40_pct_ge3 < 0.40 AND (c40_max_aloft >= 4 OR drop > 0.35)
def rule_e3(feats):
    c4 = feats.get('c40', {}) or {}
    return c4.get('pct_ge3', 1.0) < 0.40 and (c4.get('max_aloft', 0) >= 4 or feats.get('drop_pct_ge3', 0) > 0.35)

evaluate_rule(rule_e3, "Rule E3: c40_pct_ge3 < 0.40 AND (max>=4 OR drop>0.35)")

# Test: REJECT if c40_pct_ge3 < 0.40 AND (c40_max_aloft >= 4 OR (drop > 0.30 AND c40_frac_at_max < 0.10))
def rule_e4(feats):
    c4 = feats.get('c40', {}) or {}
    drop = feats.get('drop_pct_ge3', 0)
    return c4.get('pct_ge3', 1.0) < 0.40 and (c4.get('max_aloft', 0) >= 4 or (drop > 0.30 and c4.get('frac_at_max', 1.0) < 0.10))

evaluate_rule(rule_e4, "Rule E4: c40_pct_ge3 < 0.40 AND (max>=4 OR (drop>0.30 AND frac@max<0.10))")

# Test: REJECT if c40_pct_ge3 < 0.36
def rule_e5(feats):
    c4 = feats.get('c40', {}) or {}
    return c4.get('pct_ge3', 1.0) < 0.36

evaluate_rule(rule_e5, "Rule E5: c40_pct_ge3 < 0.36")

# Test: REJECT if c40_max_aloft >= 4
def rule_e6(feats):
    c4 = feats.get('c40', {}) or {}
    return c4.get('max_aloft', 0) >= 4

evaluate_rule(rule_e6, "Rule E6: c40_max_aloft >= 4")

# Test: REJECT if c40_pct_ge3 < 0.40 AND c40_std_aloft < 0.50
def rule_e7(feats):
    c4 = feats.get('c40', {}) or {}
    return c4.get('pct_ge3', 1.0) < 0.40 and c4.get('std_aloft', 99) < 0.50

evaluate_rule(rule_e7, "Rule E7: c40_pct_ge3 < 0.40 AND c40_std_aloft < 0.50")

# Test: REJECT if c40_pct_ge3 < 0.40 AND c40_max_aloft >= 4 AND drop > 0.20
def rule_e8(feats):
    c4 = feats.get('c40', {}) or {}
    return c4.get('pct_ge3', 1.0) < 0.40 and c4.get('max_aloft', 0) >= 4 and feats.get('drop_pct_ge3', 0) > 0.20

evaluate_rule(rule_e8, "Rule E8: c40_pct_ge3 < 0.40 AND max>=4 AND drop>0.20")

# Comprehensive grid search
print("\n=== Comprehensive grid: REJECT if c40_pct_ge3 < t1 AND (c40_max >= t2 OR drop > t3) ===")
best = None
for t1 in [0.30, 0.35, 0.36, 0.37, 0.38, 0.39, 0.40, 0.42, 0.45]:
    for t2 in [3, 4]:
        for t3 in [0.20, 0.25, 0.30, 0.32, 0.35, 0.38, 0.40]:
            TP = TN = FP = FN = 0
            for k, v in h90.items():
                parts = k.split("_")
                if "identical" in k:
                    stem = "identical_balls_trick_000_018"
                else:
                    stem = "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090"
                start = int(parts[-2])
                end = int(parts[-1])
                key = (stem, start, end)
                feats = v['feats']
                verdict = v['gt'][1]
                is_real = verdict in REAL_VERDICTS
                is_misclass = verdict in MISCLASS_VERDICTS
                c4 = feats.get('c40', {}) or {}
                if h82_v1_catches(key):
                    if is_misclass:
                        TN += 1
                    continue
                rejected = c4.get('pct_ge3', 1.0) < t1 and (c4.get('max_aloft', 0) >= t2 or feats.get('drop_pct_ge3', 0) > t3)
                if is_real and not rejected: TP += 1
                elif is_misclass and rejected: TN += 1
                elif is_misclass and not rejected: FP += 1
                elif is_real and rejected: FN += 1
            p = TP / max(1, TP+FP); r = TP / max(1, TP+FN)
            acc = (TP+TN) / max(1, TP+TN+FP+FN)
            if best is None or (acc, p) > (best[6], best[7]):
                best = (t1, t2, t3, (TP, TN, FP, FN), r, acc, acc, p)
print(f"  Best: t1={best[0]} t2={best[1]} t3={best[2]} TPR={best[3]} R={best[4]:.3f} acc={best[5]:.3f} P={best[7]:.3f}")
