#!/usr/bin/env python3
"""
H90 v4 — Exhaustive grid over per-phase rules.
"""
from __future__ import annotations
import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"

with open(f"{H1_DATA}/h90_per_phase_features.json") as f:
    h90 = json.load(f)

REAL_VERDICTS = ("FOUNTAIN", "JUGGLING", "JUGGLING_STARTUP")
MISCLASS_VERDICTS = ("MANIPULATION", "STATIC_HOLD", "OTHER_CROSSED_ARM",
                     "OTHER_STATIC_HOLD", "CASCADE_REAL", "STATIC_DEMO")


def h82_v1_catches(key):
    """H82 v1 + H87 stack catches these 4 identical misclassifications via:
    - f=685-716: H87 (pct_ge3=0.16 < 0.20)
    - f=733-766: H74v2 (var<0.20 AND unique_LR<=2)
    - f=890-936: H78 (mean_diff>10)
    - f=1029-1049: H74v2 (var<0.20 AND unique_LR<=2)
    """
    (stem, start, end) = key
    if stem.startswith("ident"):
        if (start, end) in [(685, 716), (733, 766), (890, 936), (1029, 1049)]:
            return True
    return False


def parse_key(k):
    parts = k.split("_")
    if "identical" in k:
        stem = "identical_balls_trick_000_018"
    else:
        stem = "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090"
    start = int(parts[-2])
    end = int(parts[-1])
    return (stem, start, end)


def evaluate(rule_fn):
    """Returns (TP, TN, FP, FN, per_phase_results)."""
    TP = TN = FP = FN = 0
    detail = []
    for k, v in h90.items():
        key = parse_key(k)
        verdict = v['gt'][1]
        feats = v['feats']
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS

        if h82_v1_catches(key):
            if is_misclass:
                TN += 1
            detail.append((key, verdict, "H82", is_real, is_misclass))
            continue
        rejected = rule_fn(feats)
        if is_real and not rejected:
            TP += 1
        elif is_misclass and rejected:
            TN += 1
        elif is_misclass and not rejected:
            FP += 1
        elif is_real and rejected:
            FN += 1
        detail.append((key, verdict, "REJ" if rejected else "KEEP", is_real, is_misclass))
    return TP, TN, FP, FN, detail


def per_stem(tpr):
    TP, TN, FP, FN, detail = tpr
    iTP = iTN = iFP = iFN = 0
    yTP = yTN = yFP = yFN = 0
    for key, verdict, action, is_real, is_misclass in detail:
        if action == "H82":
            continue
        is_ident = key[0].startswith("ident")
        if is_ident:
            if is_real and action == "KEEP": iTP += 1
            elif is_misclass and action == "REJ": iTN += 1
            elif is_misclass and action == "KEEP": iFP += 1
            elif is_real and action == "REJ": iFN += 1
        else:
            if is_real and action == "KEEP": yTP += 1
            elif is_misclass and action == "REJ": yTN += 1
            elif is_misclass and action == "KEEP": yFP += 1
            elif is_real and action == "REJ": yFN += 1
    return (iTP, iTN, iFP, iFN), (yTP, yTN, yFP, yFN)


def make_rule(thr_p3, max_thr, drop_thr):
    def rule(feats):
        c4 = feats.get('c40', {}) or {}
        if c4.get('pct_ge3', 1.0) >= thr_p3:
            return False  # NOT rejected (kept)
        if max_thr is not None and c4.get('max_aloft', 0) >= max_thr:
            return True
        if drop_thr is not None and feats.get('drop_pct_ge3', 0) > drop_thr:
            return True
        return False
    return rule


# Big grid
print("Grid: REJECT if (c40_pct_ge3 < t1) AND ((max_aloft >= t2) OR (drop > t3))")
print(f"{'t1':<5} {'t2':<4} {'t3':<5} {'TP':<3} {'TN':<3} {'FP':<3} {'FN':<3} {'P':<6} {'R':<6} {'acc':<6}  ident                            youtu")
best = None
for t1 in [0.30, 0.34, 0.35, 0.36, 0.37, 0.38, 0.39, 0.40, 0.42, 0.45]:
    for t2 in [3, 4, 5]:
        for t3 in [0.25, 0.30, 0.32, 0.35, 0.38, 0.40, None]:
            rule = make_rule(t1, t2, t3)
            TP, TN, FP, FN, detail = evaluate(rule)
            p = TP / max(1, TP+FP)
            r = TP / max(1, TP+FN)
            acc = (TP+TN) / max(1, TP+TN+FP+FN)
            if best is None or (acc > best[7] + 0.001) or (abs(acc - best[7]) < 0.001 and p > best[6]):
                i, y = per_stem((TP, TN, FP, FN, detail))
                best = (t1, t2, t3, TP, TN, FP, FN, acc, p, r, i, y)
            if acc > 0.80:
                i, y = per_stem((TP, TN, FP, FN, detail))
                line = f"{t1:<5} {t2:<4} {str(t3):<5} {TP:<3} {TN:<3} {FP:<3} {FN:<3} {p:<6.3f} {r:<6.3f} {acc:<6.3f}  i(TP={i[0]} TN={i[1]} FP={i[2]} FN={i[3]})  y(TP={y[0]} TN={y[1]} FP={y[2]} FN={y[3]})"
                if p == 1.0:
                    print(f"  PERFECT_P: {line}")
                elif acc >= 0.90 and p >= 0.85:
                    print(f"  HIGH_P_ACC: {line}")
                elif p >= 0.9:
                    print(f"  HIGH_P: {line}")
                elif acc >= 0.90:
                    print(f"  HIGH_ACC: {line}")

print(f"\nBest: t1={best[0]} t2={best[1]} t3={best[2]} TP={best[3]} TN={best[4]} FP={best[5]} FN={best[6]} P={best[8]:.3f} R={best[9]:.3f} acc={best[7]:.3f}")
print(f"  ident: TP={best[10][0]} TN={best[10][1]} FP={best[10][2]} FN={best[10][3]}")
print(f"  youtu: TP={best[11][0]} TN={best[11][1]} FP={best[11][2]} FN={best[11][3]}")
