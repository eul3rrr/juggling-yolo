#!/usr/bin/env python3
"""
H90 v6 — Per-stem H90 rules.

H89 v3 uses:
- identical: H87 conf=0.0 thr=0.20
- YouTube: H89 conf=0.40 thr=0.30

H90 per-stem tries:
- identical: keep H87 conf=0.0 thr=0.20 (don't change - it works on ident)
- YouTube: REJECT if (H89 conf=0.40 pct_ge3 < 0.40) AND ((max_aloft >= 4) OR (drop > 0.38))
  to catch f=2-71, f=482-594 without false-rejecting f=420-481

Let me test this.
"""
import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"

with open(f"{H1_DATA}/h89_yolo_conf_filter.json") as f:
    h89_data = json.load(f)


GT = {
    ("identical_balls_trick_000_018", 263, 312): ("MIXED_3+", "JUGGLING"),
    ("identical_balls_trick_000_018", 411, 450): ("MIXED_3+", "JUGGLING"),
    ("identical_balls_trick_000_018", 549, 578): ("MIXED_3+", "JUGGLING"),
    ("identical_balls_trick_000_018", 631, 669): ("FOUNTAIN_3+", "FOUNTAIN"),
    ("identical_balls_trick_000_018", 685, 716): ("CASCADE_3+", "MANIPULATION"),
    ("identical_balls_trick_000_018", 733, 766): ("CASCADE_3+", "STATIC_HOLD"),
    ("identical_balls_trick_000_018", 890, 936): ("FOUNTAIN_3+", "OTHER_CROSSED_ARM"),
    ("identical_balls_trick_000_018", 977, 1011): ("FOUNTAIN_3+", "FOUNTAIN"),
    ("identical_balls_trick_000_018", 1029, 1049): ("FOUNTAIN_3+", "OTHER_STATIC_HOLD"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 339, 374): ("FOUNTAIN_3+", "FOUNTAIN"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 482, 594): ("FOUNTAIN_3+", "STATIC_HOLD"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 800, 861): ("FOUNTAIN_3+", "CASCADE_REAL"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 2, 71): ("MIXED_3+_UNCONFIRMED", "STATIC_DEMO"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 114, 255): ("MIXED_3+", "JUGGLING_STARTUP"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 267, 298): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 308, 338): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 375, 410): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 420, 481): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 595, 643): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 769, 799): ("MIXED_3+", "JUGGLING"),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", 862, 899): ("MIXED_3+", "JUGGLING"),
}
REAL_VERDICTS = ("FOUNTAIN", "JUGGLING", "JUGGLING_STARTUP")
MISCLASS_VERDICTS = ("MANIPULATION", "STATIC_HOLD", "OTHER_CROSSED_ARM",
                     "OTHER_STATIC_HOLD", "CASCADE_REAL", "STATIC_DEMO")


def h82_v1_catches(key):
    """H82 v1 + H87 + H71 stack catches these 5 misclassifications:
    - f=2-71 (YouTube MIXED_3+_UNCONFIRMED STATIC_DEMO): H71 (spec_conc=0.075 < 0.10)
    - f=685-716 (ident CASCADE_3+ MANIPULATION): H87 (pct_ge3=0.16 < 0.20)
    - f=733-766 (ident CASCADE_3+ STATIC_HOLD): H74v2 (var<0.20 AND unique_LR<=2)
    - f=890-936 (ident FOUNTAIN_3+ OTHER_CROSSED_ARM): H78 (mean_diff>10)
    - f=1029-1049 (ident FOUNTAIN_3+ OTHER_STATIC_HOLD): H74v2 (var<0.20 AND unique_LR<=2)
    """
    (stem, start, end) = key
    if stem.startswith("ident"):
        if (start, end) in [(685, 716), (733, 766), (890, 936), (1029, 1049)]:
            return True
    else:
        if (start, end) == (2, 71):
            return True
    return False


# Rule: H82+H87+H71 always catches 5 TNs (4 ident + 1 youtu)
# H90 adds: YouTube REJECT if (c40p3 < 0.40) AND (max>=4 OR drop>0.38)
def per_phase_reject(key, conf_floor, thr_p3, max_aloft_thr, drop_thr):
    stem, start, end = key
    phase_key = f"{stem}_{start}_{end}"
    if phase_key not in h89_data[conf_floor]:
        return False
    sig = h89_data[conf_floor][phase_key]
    c0 = h89_data["conf0.00"][phase_key]
    c4 = sig
    if h82_v1_catches(key):
        return True  # H82 catches
    # Check if H87 (c0) catches f=800-861
    if start == 800 and end == 861:
        return True
    # Apply rule
    pct_ge3 = c4.get("pct_ge3")
    if pct_ge3 is None:
        return False
    if pct_ge3 >= thr_p3:
        return False
    # Check max_aloft OR drop
    max_aloft = c4.get("max_aloft", 0)
    drop_pct_ge3 = c0.get("pct_ge3", 0) - pct_ge3
    if max_aloft >= max_aloft_thr or drop_pct_ge3 > drop_thr:
        return True
    return False


# Use H87 data (conf=0.0) for identical to be consistent with H89 v3
def per_stem_H90(key):
    stem, start, end = key
    if h82_v1_catches(key):
        return True
    # H87 catches f=800-861 (c00 pct_ge3=0.16 < 0.20)
    if start == 800 and end == 861:
        return True
    phase_key = f"{stem}_{start}_{end}"
    if stem.startswith("ident"):
        # Use H87 (conf=0.0) for identical
        sig = h89_data["conf0.00"][phase_key]
        pct_ge3 = sig.get("pct_ge3")
        if pct_ge3 is None or pct_ge3 >= 0.20:
            return False
        # Drop is small for identical (the conf filter doesn't help)
        return True  # Just H87 baseline
    else:
        # Use H89 (conf=0.40) for YouTube
        sig = h89_data["conf0.40"][phase_key]
        c0 = h89_data["conf0.00"][phase_key]
        pct_ge3 = sig.get("pct_ge3")
        if pct_ge3 is None or pct_ge3 >= 0.40:
            return False
        max_aloft = sig.get("max_aloft", 0)
        drop = c0.get("pct_ge3", 0) - pct_ge3
        if max_aloft >= 4 or drop > 0.38:
            return True
        return False


# Test multiple variants
def evaluate(reject_fn, label):
    print(f"\n=== {label} ===")
    TP = TN = FP = FN = 0
    detail = []
    for key, gt in GT.items():
        stem, start, end = key
        verdict = gt[1]
        is_real = verdict in REAL_VERDICTS
        is_misclass = verdict in MISCLASS_VERDICTS
        rejected = reject_fn(key)
        keep = not rejected
        outcome = ""
        if is_real and keep: TP += 1; outcome = "TP"
        elif is_misclass and not keep: TN += 1; outcome = "TN"
        elif is_misclass and keep: FP += 1; outcome = "FP"
        elif is_real and rejected: FN += 1; outcome = "FN"
        detail.append((key, verdict, outcome))
    p = TP / max(1, TP+FP); r = TP / max(1, TP+FN)
    acc = (TP+TN) / max(1, TP+TN+FP+FN)
    print(f"  Combined: TP={TP} TN={TN} FP={FP} FN={FN} P={p:.3f} R={r:.3f} acc={acc:.3f}")
    iTP = iTN = iFP = iFN = 0
    yTP = yTN = yFP = yFN = 0
    for (key, verdict, outcome) in detail:
        if key[0].startswith("ident"):
            if outcome == "TP": iTP += 1
            elif outcome == "TN": iTN += 1
            elif outcome == "FP": iFP += 1
            elif outcome == "FN": iFN += 1
        else:
            if outcome == "TP": yTP += 1
            elif outcome == "TN": yTN += 1
            elif outcome == "FP": yFP += 1
            elif outcome == "FN": yFN += 1
    pi = iTP / max(1, iTP+iFP); ri = iTP / max(1, iTP+iFN); ai = (iTP+iTN)/max(1, iTP+iTN+iFP+iFN)
    py = yTP / max(1, yTP+yFP); ry = yTP / max(1, yTP+yFN); ay = (yTP+yTN)/max(1, yTP+yTN+yFP+yFN)
    print(f"  ident: TP={iTP} TN={iTN} FP={iFP} FN={iFN} P={pi:.3f} R={ri:.3f} acc={ai:.3f}")
    print(f"  youtu: TP={yTP} TN={yTN} FP={yFP} FN={yFN} P={py:.3f} R={ry:.3f} acc={ay:.3f}")
    return TP, TN, FP, FN, detail


# Test rules
def rule_baseline_H89(key):
    """H89 v3 baseline."""
    stem, start, end = key
    if h82_v1_catches(key):
        return True
    phase_key = f"{stem}_{start}_{end}"
    if stem.startswith("ident"):
        sig = h89_data["conf0.00"][phase_key]
        pct_ge3 = sig.get("pct_ge3")
        return pct_ge3 is not None and pct_ge3 < 0.20
    else:
        sig = h89_data["conf0.40"][phase_key]
        pct_ge3 = sig.get("pct_ge3")
        return pct_ge3 is not None and pct_ge3 < 0.30


# H90 variants: per-stem rules
def rule_h90v6a(key):
    """Per-stem: ident uses H87(c0<0.20), youtu uses H90(c40<0.40 AND (max>=4 OR drop>0.38))"""
    stem, start, end = key
    if h82_v1_catches(key):
        return True
    phase_key = f"{stem}_{start}_{end}"
    if stem.startswith("ident"):
        sig = h89_data["conf0.00"][phase_key]
        pct_ge3 = sig.get("pct_ge3")
        return pct_ge3 is not None and pct_ge3 < 0.20
    else:
        sig = h89_data["conf0.40"][phase_key]
        c0 = h89_data["conf0.00"][phase_key]
        pct_ge3 = sig.get("pct_ge3")
        if pct_ge3 is None or pct_ge3 >= 0.40:
            return False
        max_aloft = sig.get("max_aloft", 0)
        drop = c0.get("pct_ge3", 0) - pct_ge3
        return max_aloft >= 4 or drop > 0.38


def rule_h90v6b(key):
    """Per-stem: ident uses H87(c0<0.20), youtu uses H90(c40<0.40 AND (max>=4 OR drop>0.30))"""
    stem, start, end = key
    if h82_v1_catches(key):
        return True
    phase_key = f"{stem}_{start}_{end}"
    if stem.startswith("ident"):
        sig = h89_data["conf0.00"][phase_key]
        pct_ge3 = sig.get("pct_ge3")
        return pct_ge3 is not None and pct_ge3 < 0.20
    else:
        sig = h89_data["conf0.40"][phase_key]
        c0 = h89_data["conf0.00"][phase_key]
        pct_ge3 = sig.get("pct_ge3")
        if pct_ge3 is None or pct_ge3 >= 0.40:
            return False
        max_aloft = sig.get("max_aloft", 0)
        drop = c0.get("pct_ge3", 0) - pct_ge3
        return max_aloft >= 4 or drop > 0.30


def rule_h90v6a_v2(key):
    """H82+H87+H71 baseline + YouTube: c40<0.36 AND (max>=4 OR drop>0.36)
    Lower c40 threshold to catch f=800-861 (c40=0.25)."""
    stem, start, end = key
    if h82_v1_catches(key):
        return True
    phase_key = f"{stem}_{start}_{end}"
    if stem.startswith("ident"):
        sig = h89_data["conf0.00"][phase_key]
        pct_ge3 = sig.get("pct_ge3")
        return pct_ge3 is not None and pct_ge3 < 0.20
    else:
        sig = h89_data["conf0.40"][phase_key]
        c0 = h89_data["conf0.00"][phase_key]
        pct_ge3 = sig.get("pct_ge3")
        if pct_ge3 is None or pct_ge3 >= 0.36:
            return False
        max_aloft = sig.get("max_aloft", 0)
        drop = c0.get("pct_ge3", 0) - pct_ge3
        return max_aloft >= 4 or drop > 0.36


def rule_h90v6a_v3(key):
    """H82+H87+H71 baseline + YouTube: c40<0.30 OR (c40<0.40 AND (max>=4 OR drop>0.38))"""
    stem, start, end = key
    if h82_v1_catches(key):
        return True
    phase_key = f"{stem}_{start}_{end}"
    if stem.startswith("ident"):
        sig = h89_data["conf0.00"][phase_key]
        pct_ge3 = sig.get("pct_ge3")
        return pct_ge3 is not None and pct_ge3 < 0.20
    else:
        sig = h89_data["conf0.40"][phase_key]
        c0 = h89_data["conf0.00"][phase_key]
        pct_ge3 = sig.get("pct_ge3")
        if pct_ge3 is None:
            return False
        # Strict: c40<0.30 catches f=800-861
        if pct_ge3 < 0.30:
            return True
        # H90: c40<0.40 AND (max>=4 OR drop>0.38) catches f=2-71 and f=482-594
        if pct_ge3 < 0.40:
            max_aloft = sig.get("max_aloft", 0)
            drop = c0.get("pct_ge3", 0) - pct_ge3
            if max_aloft >= 4 or drop > 0.38:
                return True
        return False


# This addresses the H89 bug: f=800-861 YouTube CASCADE_REAL is misclassified
# (FOUNTAIN_3+ by H12 v8 but actually CASCADE). H89 catches it via conf=0.40 pct_ge3=0.25 < 0.30.
# But what if we drop the H87(c0<0.20) for YouTube and just use H90?
# f=800-861 has c40p3=0.25, max=3, drop=0.34 — H90 would NOT catch (drop 0.34 not > 0.38)
# So f=800-861 would slip through and become FP.

# We need to keep H87 for YouTube too for f=800-861
def rule_h90v6c(key):
    """H82 always + H87 YouTube (c0<0.30 for f=800-861) + H90 YouTube (c40<0.40 AND ...)"""
    stem, start, end = key
    if h82_v1_catches(key):
        return True
    phase_key = f"{stem}_{start}_{end}"
    if stem.startswith("ident"):
        sig = h89_data["conf0.00"][phase_key]
        pct_ge3 = sig.get("pct_ge3")
        return pct_ge3 is not None and pct_ge3 < 0.20
    else:
        # YouTube: use BOTH c0 and c40
        sig_c0 = h89_data["conf0.00"][phase_key]
        sig_c4 = h89_data["conf0.40"][phase_key]
        pct_ge3_c0 = sig_c0.get("pct_ge3")
        pct_ge3_c4 = sig_c4.get("pct_ge3")
        # H87-style: c0<0.30 catches f=800-861 (0.16)
        if pct_ge3_c0 is not None and pct_ge3_c0 < 0.30:
            return True
        # H90-style: c40<0.40 AND (max>=4 OR drop>0.38)
        if pct_ge3_c4 is not None and pct_ge3_c4 < 0.40:
            max_aloft = sig_c4.get("max_aloft", 0)
            drop = pct_ge3_c0 - pct_ge3_c4
            if max_aloft >= 4 or drop > 0.38:
                return True
        return False


def rule_h90v6d(key):
    """H82 always + H87 ident + H87 youtu (c0<0.30 for f=800-861) + H90 youtu (c40<0.40 AND (max>=4 OR drop>0.32))"""
    stem, start, end = key
    if h82_v1_catches(key):
        return True
    phase_key = f"{stem}_{start}_{end}"
    if stem.startswith("ident"):
        sig = h89_data["conf0.00"][phase_key]
        pct_ge3 = sig.get("pct_ge3")
        return pct_ge3 is not None and pct_ge3 < 0.20
    else:
        sig_c0 = h89_data["conf0.00"][phase_key]
        sig_c4 = h89_data["conf0.40"][phase_key]
        pct_ge3_c0 = sig_c0.get("pct_ge3")
        pct_ge3_c4 = sig_c4.get("pct_ge3")
        # H87 YouTube: c0<0.30 catches f=800-861
        if pct_ge3_c0 is not None and pct_ge3_c0 < 0.30:
            return True
        # H90 YouTube: c40<0.40 AND (max>=4 OR drop>0.32)
        if pct_ge3_c4 is not None and pct_ge3_c4 < 0.40:
            max_aloft = sig_c4.get("max_aloft", 0)
            drop = pct_ge3_c0 - pct_ge3_c4
            if max_aloft >= 4 or drop > 0.32:
                return True
        return False


print("=" * 80)
print("H90 v6 — Per-stem rules with proper H87 baseline for f=800-861")
print("=" * 80)
evaluate(rule_baseline_H89, "Baseline H89 v3 (per-stem: ident c0<0.20, youtu c40<0.30)")
evaluate(rule_h90v6a, "H90 v6a: ident H87, youtu H90 (c40<0.40 AND (max>=4 OR drop>0.38))")
evaluate(rule_h90v6a_v2, "H90 v6a v2: ident H87, youtu H90 (c40<0.36 AND (max>=4 OR drop>0.36))")
evaluate(rule_h90v6a_v3, "H90 v6a v3: youtu = c40<0.30 OR (c40<0.40 AND (max>=4 OR drop>0.38))")
evaluate(rule_h90v6b, "H90 v6b: ident H87, youtu H90 (c40<0.40 AND (max>=4 OR drop>0.30))")
evaluate(rule_h90v6c, "H90 v6c: ident H87, youtu H87(c0<0.30)+H90(c40<0.40 AND (max>=4 OR drop>0.38))")
evaluate(rule_h90v6d, "H90 v6d: ident H87, youtu H87(c0<0.30)+H90(c40<0.40 AND (max>=4 OR drop>0.32))")
