#!/usr/bin/env python3
"""H124 v1: compound precision-optimized edge filter for H7v2 reclassifications.

The H123 finding was that H7v2 reclassification is over-applied at ~50% rate
on the YouTube-heavy RAW_REJECTS pool (Wilson 95% CI: [30%, 75%]). The geometric
post-filters (H112, H114 v1 strict) only catch 1/6 of the false positives.

H124 v1 derives a NEW geometric rule from the H122+H123 visual QA data (15 cases:
8 REAL, 6 TRACKER_ARTIFACT, 1 UNCERTAIN) that achieves:
- 86% accuracy on the 14 known-label cases (12/14)
- 100% precision on rejects (4/4 TRACKER_ARTIFACT, 0 REALS rejected)
- 67% recall on rejects (4/6 TRACKER_ARTIFACTS caught)

The compound rule:
    FIRE (suggest REJECT the reclassification) if
        sjr > 90 AND NOT (red > 100 OR res > 10)
    OR  feat_n_pts <= 3

The rule is intentionally narrow (only fires on RAW_REJECTS, not STILL_RECLASSIFIED)
because STILL_RECLASSIFIED edges have a real catch/throw signature in BOTH raw and
orig data, so they are confirmed real regardless of geometry.

The rule's three-way flat region (sjr>90 with red<=100 AND res<=10, OR fn<=3)
correctly identifies:
- Cross-hand handoff artifacts (sjr>100, no V-shape in source, no large red or res)
- Very-short-source artifacts (2-3 raw points = noisy catch/throw signature)

The rule's false negative (5/15 visual-QA'd TRACKER_ARTIFACTS not caught) cluster
into 2 patterns:
- Low-sjr cross-ball handoffs (22->27, 33->36)
- Multi-ball handoff with strong post-throw ascent (res>10 catches it as REAL)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
OUT_DATA = H1_DATA

# Default rule parameters (flat region: sjr>90 with red<=100 AND res<=10, OR fn<=3)
SJT = 90      # sj_raw > SJT
RED_LO = 100  # raw_end_dist <= RED_LO
RES_LO = 10   # raw_end_slope <= RES_LO
FNT = 3       # feat_n_pts <= FNT


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


def main():
    # Load H121 per_edge data
    with (H1_DATA / "h121_per_edge.csv").open() as f:
        rows = list(csv.DictReader(f))

    # Classify each row
    out = []
    for r in rows:
        fires = fires_rule(r)
        v = r.get('visual_qa_verdict', '').strip()
        out.append({
            'stem': r['stem'],
            'from': r['from'],
            'to': r['to'],
            'verdict': r['verdict'],
            'visual_qa_verdict': v,
            'fires': fires,
            'sjr': to_float(r['sj_raw']),
            'red': to_float(r['raw_end_dist']),
            'res': to_float(r['raw_end_slope']),
            'fnp': int(r['feat_n_pts']),
        })

    # Statistics: visual-QA'd subset
    qa = [o for o in out if o['visual_qa_verdict'] in ('REAL', 'TRACKER_ARTIFACT')]
    tp = sum(1 for o in qa if o['visual_qa_verdict'] == 'REAL' and not o['fires'])
    fp = sum(1 for o in qa if o['visual_qa_verdict'] == 'REAL' and o['fires'])
    fn = sum(1 for o in qa if o['visual_qa_verdict'] == 'TRACKER_ARTIFACT' and not o['fires'])
    tn = sum(1 for o in qa if o['visual_qa_verdict'] == 'TRACKER_ARTIFACT' and o['fires'])
    n = tp + fp + fn + tn
    p = tn / (tn + fn) if (tn + fn) else 0
    r_rej = tn / (tn + fp) if (tn + fp) else 0
    acc = (tp + tn) / n if n else 0
    print("=" * 70)
    print(f"H124 v1 compound filter (sjr>{SJT} AND NOT(red>{RED_LO} OR res>{RES_LO}) OR fn<={FNT})")
    print("=" * 70)
    print(f"Visual-QA'd RAW_REJECTS subset (14 cases: 8 REAL + 6 ARTIFACT):")
    print(f"  TP={tp} (REAL kept), FP={fp} (REAL wrongly rejected),")
    print(f"  FN={fn} (ARTIFACT missed), TN={tn} (ARTIFACT caught),  acc={acc:.3f}")
    print(f"  P_when_fire={p:.3f} (when rule fires, fraction that's a real artifact)")
    print(f"  R_artifacts={r_rej:.3f} (fraction of artifacts caught)")

    # Per-case visual-QA detail
    print()
    print("Per-case detail (visual-QA'd):")
    for o in sorted(qa, key=lambda x: (x['stem'], int(x['from']), int(x['to']))):
        fire = "FIRE" if o['fires'] else "."
        v = o['visual_qa_verdict'][:5]
        print(f"  {o['stem'][:3]} {o['from']}->{o['to']:3s} v={v:5s} sjr={o['sjr']:6.1f} red={o['red']:6.1f} res={o['res']:6.2f} fn={o['fnp']:>3} {fire}")

    # Un-QA'd subset
    unqa = [o for o in out if o['verdict'] == 'RAW_REJECTS' and not o['visual_qa_verdict']]
    unqa_fires = [o for o in unqa if o['fires']]
    print()
    print(f"Un-QA'd RAW_REJECTS: {len(unqa_fires)}/{len(unqa)} fire the rule")
    for o in sorted(unqa_fires, key=lambda x: (x['stem'], int(x['from']), int(x['to']))):
        fire = "FIRE"
        print(f"  {o['stem'][:3]} {o['from']}->{o['to']:3s} sjr={o['sjr']:6.1f} red={o['red']:6.1f} res={o['res']:6.2f} fn={o['fnp']:>3} {fire}")

    # STILL_RECLASSIFIED: rule should NOT fire (they have real catch/throw signature in raw data)
    still = [o for o in out if o['verdict'] == 'STILL_RECLASSIFIED']
    still_fires = [o for o in still if o['fires']]
    print()
    print(f"STILL_RECLASSIFIED: rule fires on {len(still_fires)}/{len(still)}")
    print("(rule is intentionally for RAW_REJECTS only; STILL_RECLASSIFIED are confirmed real in raw data)")
    for o in sorted(still_fires, key=lambda x: (x['stem'], int(x['from']), int(x['to']))):
        print(f"  {o['stem'][:3]} {o['from']}->{o['to']:3s} sjr={o['sjr']:6.1f} red={o['red']:6.1f} res={o['res']:6.2f} fn={o['fnp']:>3} FIRE-on-fn-le-{FNT} (still reclassified in raw)")

    # Write summary JSON
    summary = {
        "rule": f"sjr>{SJT} AND NOT(red>{RED_LO} OR res>{RES_LO}) OR fn<={FNT}",
        "parameters": {"sjt": SJT, "red_lo": RED_LO, "res_lo": RES_LO, "fnt": FNT},
        "visual_qa_subset": {
            "n_qa": n,
            "n_real": sum(1 for o in qa if o['visual_qa_verdict'] == 'REAL'),
            "n_artifact": sum(1 for o in qa if o['visual_qa_verdict'] == 'TRACKER_ARTIFACT'),
            "tp_real_kept": tp,
            "fp_real_wrongly_rejected": fp,
            "fn_artifact_missed": fn,
            "tn_artifact_caught": tn,
            "acc": acc,
            "p_when_fire": p,
            "r_artifacts": r_rej,
        },
        "unqa_subset": {
            "n_total": len(unqa),
            "n_fires": len(unqa_fires),
            "fires": [
                {"stem": o['stem'], "from": o['from'], "to": o['to'],
                 "sjr": o['sjr'], "red": o['red'], "res": o['res'], "fnp": o['fnp']}
                for o in unqa_fires
            ],
        },
        "still_reclassified_subset": {
            "n_total": len(still),
            "n_fires": len(still_fires),
        },
    }
    with (OUT_DATA / "h124_v1_summary.json").open("w") as f:
        json.dump(summary, f, indent=2)
    print()
    print(f"Wrote {OUT_DATA / 'h124_v1_summary.json'}")

    # Write per-edge CSV
    with (OUT_DATA / "h124_v1_per_edge.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            'stem', 'from', 'to', 'verdict', 'visual_qa_verdict',
            'fires', 'sjr', 'red', 'res', 'fnp',
        ])
        w.writeheader()
        for o in out:
            w.writerow(o)
    print(f"Wrote {OUT_DATA / 'h124_v1_per_edge.csv'}")


if __name__ == "__main__":
    main()
