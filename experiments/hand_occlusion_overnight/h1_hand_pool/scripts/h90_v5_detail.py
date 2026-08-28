#!/usr/bin/env python3
"""
H90 v5 — Detail dump for the best rule.
"""
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


# Two rules to compare
def rule_A(feats):  # The H89 stack: conf=0.4 + thr=0.30
    c4 = feats.get('c40', {}) or {}
    return c4.get('pct_ge3', 1.0) < 0.30

def rule_B(feats):  # H90 best
    c4 = feats.get('c40', {}) or {}
    return c4.get('pct_ge3', 1.0) < 0.38 and (c4.get('max_aloft', 0) >= 4 or feats.get('drop_pct_ge3', 0) > 0.38)

def rule_C(feats):  # The "perfect-P" H90 alternative
    c4 = feats.get('c40', {}) or {}
    return c4.get('pct_ge3', 1.0) < 0.37 and (c4.get('max_aloft', 0) >= 4 or feats.get('drop_pct_ge3', 0) > 0.30)


def detail_for_rule(rule_fn, label):
    print(f"\n=== Per-phase outcome for: {label} ===")
    for k in sorted(h90.keys()):
        key = parse_key(k)
        v = h90[k]
        verdict = v['gt'][1]
        feats = v['feats']
        c4 = feats.get('c40', {}) or {}
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        if h82_v1_catches(key):
            outcome = "H82_TN" if is_misclass else "H82_TP"
            why = "H82+H87 baseline"
        else:
            rejected = rule_fn(feats)
            if is_real and not rejected:
                outcome = "TP"
            elif is_misclass and rejected:
                outcome = "TN"
            elif is_misclass and not rejected:
                outcome = "FP"
            elif is_real and rejected:
                outcome = "FN"
            why = f"c40p3={c4.get('pct_ge3', 0):.2f} max={c4.get('max_aloft', 0)} drop={feats.get('drop_pct_ge3', 0):.2f}"
        label_short = f"{key[0][:5]} f={key[1]}-{key[2]}"
        print(f"  {label_short:<25} {verdict:<22} {why:<50} -> {outcome}")


detail_for_rule(rule_A, "H89 (c40p3<0.30)")
detail_for_rule(rule_B, "H90 v4 best (c40p3<0.38 AND (max>=4 OR drop>0.38))")
detail_for_rule(rule_C, "H90 v5 perfect-P (c40p3<0.37 AND (max>=4 OR drop>0.30))")
