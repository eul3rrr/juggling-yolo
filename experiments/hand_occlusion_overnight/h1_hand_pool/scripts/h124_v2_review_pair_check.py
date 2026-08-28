#!/usr/bin/env python3
"""H124 v2: cross-validate H124 v1 compound filter on the 113 review pair set.

The H124 v1 rule was derived from the 14 H122+H123 visual-QA'd RAW_REJECTS
cases and achieved 0% false-reject on REALS. But RAW_REJECTS are a
SPECIFIC subset of the chain's edges: cases where H7v2_orig reclassified
BALLISTIC -> HAND_TRANSITION but H7v2_raw (with raw data) wouldn't.

This script cross-validates the rule on the FULL 113 manual review set to
check for edge-level precision/recall impact.

Hypothesis:
- H124 v1 might fire on correct review pairs (the broader E6c set has
  similar geometry but is not all H7v2 reclassifications).
- If the rule is biased to H7v2 reclassifications only, it should not
  fire on non-reclassified edges.
"""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
DETECTIONS = WORKTREE / "detections"
OUT_DATA = H1_DATA

# H124 v1 rule parameters
SJT = 90
RED_LO = 100
RES_LO = 10
FNT = 3

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]


def to_float(s):
    if s is None or s == '':
        return None
    return float(s)


def fires_rule(r, sjt=SJT, red_lo=RED_LO, res_lo=RES_LO, fnt=FNT):
    sjr = to_float(r['sj_raw'])
    red = to_float(r['raw_end_dist'])
    res = to_float(r['raw_end_slope'])
    fnp = int(r['feat_n_pts'])
    rule1 = (sjr is not None and sjr > sjt) and not (
        (red is not None and red > red_lo) or (res is not None and res > res_lo)
    )
    rule2 = fnp <= fnt
    return rule1 or rule2


def dist(a, b):
    if not a or not b:
        return None
    return math.hypot(a[0] - b[0], a[1] - b[1])


def load_pose(stem):
    pose = {}
    pose_path = DETECTIONS / f"{stem}_yolo26s-pose.csv"
    if not pose_path.exists():
        return pose
    with pose_path.open() as fh:
        for r in csv.DictReader(fh):
            f = int(r["frame"])
            L = (float(r["left_wrist_x"]), float(r["left_wrist_y"])) if r["left_wrist_x"] else None
            R = (float(r["right_wrist_x"]), float(r["right_wrist_y"])) if r["right_wrist_x"] else None
            pose[f] = {"left": L, "right": R}
    return pose


def load_raw_tracklets(stem):
    raw = {}
    raw_path = DETECTIONS / f"{stem}_norfair_dt50_hc5.csv"
    if not raw_path.exists():
        return raw
    with raw_path.open() as fh:
        for r in csv.DictReader(fh):
            t = int(r['track_id'])
            raw.setdefault(t, []).append((
                int(r['frame']), float(r['center_x']), float(r['center_y']),
                float(r['confidence'])
            ))
    for t in raw:
        raw[t].sort()
    return raw


def load_features(stem):
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r['stem'] != stem:
                continue
            out[int(r['tid'])] = {
                'n_pts': int(r['n_pts']),
                'first_frame': int(r['first_frame']),
                'last_frame': int(r['last_frame']),
                'last_xy': (float(r['last_x']), float(r['last_y'])),
                'end_dist': to_float(r.get('end_dist')),
                'end_slope': to_float(r.get('end_slope')),
            }
    return out


def compute_end_slope(points, n=3):
    if len(points) < 2:
        return None
    last_n = points[-n:]
    slopes = []
    for i in range(1, len(last_n)):
        df = last_n[i][0] - last_n[i-1][0]
        dy = last_n[i][2] - last_n[i-1][2]
        if df > 0:
            slopes.append(dy / df)
    return sum(slopes) / len(slopes) if slopes else None


def get_features(stem, src, tgt, raw, feat, pose):
    src_pts = raw.get((stem, src), raw.get(src, []))
    tgt_pts = raw.get((stem, tgt), raw.get(tgt, []))
    sf = feat.get(src)
    tf = feat.get(tgt)
    if not src_pts or not tgt_pts or not sf or not tf:
        return None
    # raw spatial jump
    sj_raw = dist((src_pts[-1][1], src_pts[-1][2]), (tgt_pts[0][1], tgt_pts[0][2]))
    # raw end dist (from pose at last frame)
    src_last_frame = src_pts[-1][0]
    src_last_pos = (src_pts[-1][1], src_pts[-1][2])
    src_pose = pose.get(src_last_frame, {})
    dL = dist(src_last_pos, src_pose.get("left"))
    dR = dist(src_last_pos, src_pose.get("right"))
    raw_end_dist = min((d for d in [dL, dR] if d is not None), default=None)
    # raw end slope
    raw_end_slope = compute_end_slope(src_pts)
    # feat n_pts
    feat_n_pts = sf['n_pts']

    return {
        'sjr': sj_raw,
        'red': raw_end_dist,
        'res': raw_end_slope,
        'fnp': feat_n_pts,
    }


def main():
    # Load data per stem
    feat_by_stem = {}
    raw_by_stem = {}
    pose_by_stem = {}
    for stem in STEMS:
        feat_by_stem[stem] = load_features(stem)
        raw_by_stem[stem] = load_raw_tracklets(stem)
        pose_by_stem[stem] = load_pose(stem)

    # Load 113 review pairs
    with (DETECTIONS / "stitch_review_labels.csv").open() as f:
        review = list(csv.DictReader(f))

    out_rows = []
    for r in review:
        src = int(r['source_tracklet'])
        cand = int(r['candidate_tracklet'])
        stem = r['video'].replace('videos/', '').replace('.mp4', '')
        if stem not in STEMS:
            continue
        feats = get_features(stem, src, cand, raw_by_stem[stem], feat_by_stem[stem], pose_by_stem[stem])
        if feats is None:
            continue
        fires = fires_rule({
            'sj_raw': feats['sjr'],
            'raw_end_dist': feats['red'],
            'raw_end_slope': feats['res'],
            'feat_n_pts': feats['fnp'],
        })
        out_rows.append({
            'stem': stem,
            'src': src,
            'cand': cand,
            'label': r['label'],
            'gap': int(r['gap_frames']),
            'sjr': round(feats['sjr'], 1) if feats['sjr'] is not None else None,
            'red': round(feats['red'], 1) if feats['red'] is not None else None,
            'res': round(feats['res'], 2) if feats['res'] is not None else None,
            'fnp': feats['fnp'],
            'fires': fires,
        })

    # Stats
    fires_rows = [r for r in out_rows if r['fires']]
    print("=" * 70)
    print(f"H124 v2 cross-validation on 113 review pair set")
    print(f"  Rule: sjr>{SJT} AND NOT(red>{RED_LO} OR res>{RES_LO}) OR fn<={FNT}")
    print("=" * 70)
    print(f"\nRule fires on {len(fires_rows)}/{len(out_rows)} review pairs")
    if fires_rows:
        print("\nPer-fire detail:")
        for r in fires_rows:
            print(f"  {r['stem'][:3]} {r['src']}->{r['cand']} label={r['label']:6s} sjr={r['sjr']} red={r['red']} res={r['res']} fn={r['fnp']}")

    correct_fires = sum(1 for r in fires_rows if r['label'] == 'correct')
    wrong_fires = sum(1 for r in fires_rows if r['label'] == 'wrong')
    print()
    print(f"  Correct fires (rule wrongly rejects): {correct_fires}")
    print(f"  Wrong fires (rule correctly rejects): {wrong_fires}")
    if len(fires_rows) > 0:
        print(f"  P_when_fire = wrong_fires / fires = {wrong_fires / len(fires_rows):.3f}")
    else:
        print(f"  P_when_fire = N/A (no fires)")

    # Summary
    summary = {
        "n_review_pairs": len(out_rows),
        "n_fires": len(fires_rows),
        "n_correct_fires": correct_fires,
        "n_wrong_fires": wrong_fires,
        "p_when_fire_on_review": wrong_fires / len(fires_rows) if fires_rows else None,
    }
    with (OUT_DATA / "h124_v2_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {OUT_DATA / 'h124_v2_summary.json'}")

    with (OUT_DATA / "h124_v2_per_pair.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=['stem', 'src', 'cand', 'label', 'gap', 'sjr', 'red', 'res', 'fnp', 'fires'])
        w.writeheader()
        for r in out_rows:
            w.writerow(r)
    print(f"Wrote {OUT_DATA / 'h124_v2_per_pair.csv'}")


if __name__ == "__main__":
    main()
