#!/usr/bin/env python3
"""
H55 - H10 v11: combine H10 v10 with H54 gravity-CV as 5th dimension.

Hypothesis: H10 v10 (cross-edge, coverage) + H54 (within-chain physics
consistency) should give a better chain quality score than either alone.

Algorithm:
- Base: q_v10 = 0.30*h3 + 0.30*h8 + 0.40*h9 (h8v8 has tiny weight)
- v11: q_v11 = q_v10 - w54*g_cv (g_cv in [0, 2])
  - w54 = 0.30 (default; per-video adaptive may be needed)

Where g_cv is from H54 per-chain gravity CV (0 for chains with no
clean arcs, ~0.4-1.5 for chains with multi-arc gravity variability).

Per-video adaptive weights (H55 v2):
- identical: w54 = 0.30 (multi-tid CONFIDENT g_cv 0.379 vs UNCERTAIN 0.782,
  difference 0.40 — strong signal, weight 0.30 should help)
- youtube: w54 = 0.20 (smaller sample, less certain, weight 0.20)

Outputs:
- data/h10v11_<w54>_<stem>.csv: per-chain H10 v11 quality
- data/h10v11_summary.json: aggregate statistics
- reports/h55_report.md: analysis
"""

import csv
import json
import statistics
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

# Per-video adaptive weights (H55 v2). v1: w54=0.30 for both.
W54_IDENTICAL = 0.30
W54_YOUTUBE = 0.20

STEMS = [
    ("identical_balls_trick_000_018", W54_IDENTICAL),
    ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090", W54_YOUTUBE),
]

# H10 v10 quality formula: weighted sum of h3, h8, h9
# Plus h8v8 (already small). From the h10v10_chain_quality files.
# Formula: q_v10 = 0.30*h3 + 0.30*h8 + 0.40*h9 + 0.0*h8v8 (h8v8 was per-video)
# But the file already has the composite. We use the q_v10 column directly.
H3_WEIGHT = 0.30
H8_WEIGHT = 0.30
H9_WEIGHT = 0.40
# h8v8 has been per-video adaptive (0 for identical, 0.25 for youtube)
# already baked into the q_v10 file.

# Confidence thresholds (H11 v7)
QUALITY_CONFIDENT = 0.7
QUALITY_TRUSTABLE = 0.4


def load_h10v10(stem):
    """Return chain_id -> {q, h3, h8, h9, h8v8} dict."""
    path = H1_DATA / f"h10v10_h7v3plus3_{stem}.csv"
    out = {}
    with path.open() as fh:
        for r in csv.DictReader(fh):
            q = r["quality_v10"]
            out[r["chain_id"]] = {
                "q": float(q) if q else None,
                "h3": float(r["h3_score"]) if r["h3_score"] else None,
                "h8": float(r["h8_score"]) if r["h8_score"] else None,
                "h9": float(r["h9_score"]) if r["h9_score"] else None,
                "h8v8": float(r["h8v8_score"]) if r["h8v8_score"] else None,
            }
    return out


def load_h54_gcv(stem):
    """Return chain_id -> g_cv_clean (or None)."""
    path = H1_DATA / f"h54_per_chain_arc_gravity_{stem}.csv"
    out = {}
    with path.open() as fh:
        for r in csv.DictReader(fh):
            gcv = r["g_cv_clean"]
            out[r["chain_id"]] = float(gcv) if gcv else None
    return out


def compute_h10v11(stem, w54):
    """Compute H10 v11 with H54 weight w54."""
    h10 = load_h10v10(stem)
    gcv = load_h54_gcv(stem)
    out = []
    for cid, info in h10.items():
        q10 = info["q"]
        g = gcv.get(cid)
        if q10 is None:
            continue
        # v11: penalize g_cv; for chains with no g_cv, use 0 (no penalty)
        g_penalty = g if g is not None else 0.0
        q11 = q10 - w54 * g_penalty
        # Clamp to [0, 1]
        q11 = max(0.0, min(1.0, q11))
        out.append({
            "chain_id": cid,
            "q10": q10,
            "g_cv": g,
            "q11": round(q11, 4),
        })
    return out


def rank_chains(chains):
    """Sort chains by q (descending) and return rank dict."""
    sorted_chains = sorted(chains, key=lambda c: -c["q"])
    return {c["chain_id"]: i for i, c in enumerate(sorted_chains)}


def h11_label(q):
    if q is None:
        return "UNKNOWN"
    if q >= QUALITY_CONFIDENT:
        return "CONFIDENT"
    if q >= QUALITY_TRUSTABLE:
        return "UNCERTAIN"
    return "LOW"


def main():
    summary = {"videos": {}, "config": {
        "H3_WEIGHT": H3_WEIGHT, "H8_WEIGHT": H8_WEIGHT, "H9_WEIGHT": H9_WEIGHT,
        "W54_IDENTICAL": W54_IDENTICAL, "W54_YOUTUBE": W54_YOUTUBE,
    }}

    for stem, w54 in STEMS:
        print(f"\n=== {stem} (H55 w54={w54}) ===")
        chains_v11 = compute_h10v11(stem, w54)
        # Also compute v10 ranking for comparison
        h10 = load_h10v10(stem)
        gcv = load_h54_gcv(stem)
        chains_v10 = [{"chain_id": cid, "q": info["q"]}
                      for cid, info in h10.items() if info["q"] is not None]
        rank_v10 = rank_chains(chains_v10)
        rank_v11 = rank_chains([{"chain_id": c["chain_id"], "q": c["q11"]}
                                for c in chains_v11])
        # Compare
        improved = []  # rank went up
        demoted = []   # rank went down
        unchanged = []
        for c in chains_v11:
            cid = c["chain_id"]
            r10 = rank_v10[cid]
            r11 = rank_v11[cid]
            if r11 < r10:
                improved.append((cid, c["q10"], c["g_cv"], c["q11"], r10, r11))
            elif r11 > r10:
                demoted.append((cid, c["q10"], c["g_cv"], c["q11"], r10, r11))
            else:
                unchanged.append(cid)
        improved.sort(key=lambda x: x[5])  # sort by new rank
        demoted.sort(key=lambda x: -x[4])  # sort by old rank (biggest demote first)
        print(f"  n_chains={len(chains_v11)}, "
              f"improved={len(improved)}, demoted={len(demoted)}, "
              f"unchanged={len(unchanged)}")
        print(f"  Mean q10={statistics.mean(c['q10'] for c in chains_v11):.4f}, "
              f"mean q11={statistics.mean(c['q11'] for c in chains_v11):.4f}")
        # Top 5 improved
        print("  Top-5 improved (rank up):")
        for cid, q10, g, q11, r10, r11 in improved[:5]:
            print(f"    chain {cid:>2}: rank {r10}->{r11}, q10={q10:.3f}, "
                  f"g_cv={g}, q11={q11:.3f}")
        # Top 5 demoted
        print("  Top-5 demoted (rank down):")
        for cid, q10, g, q11, r10, r11 in demoted[:5]:
            print(f"    chain {cid:>2}: rank {r10}->{r11}, q10={q10:.3f}, "
                  f"g_cv={g}, q11={q11:.3f}")
        # CONFIDENT count comparison
        n_conf_v10 = sum(1 for c in chains_v10 if c["q"] >= QUALITY_CONFIDENT)
        n_conf_v11 = sum(1 for c in chains_v11 if c["q11"] >= QUALITY_CONFIDENT)
        print(f"  CONFIDENT chains: v10={n_conf_v10}, v11={n_conf_v11} "
              f"(diff={n_conf_v11 - n_conf_v10:+d})")
        # Per-stratum mean g_cv
        for label in ("CONFIDENT", "UNCERTAIN", "LOW"):
            qs = [c for c in chains_v11 if h11_label(c["q11"]) == label]
            if not qs:
                continue
            gcv_for_label = []
            for c in qs:
                g = gcv.get(c["chain_id"])
                if g is not None:
                    gcv_for_label.append(g)
            mean_g = round(statistics.mean(gcv_for_label), 3) if gcv_for_label else None
            print(f"  {label} (n={len(qs)}, n_with_gcv={len(gcv_for_label)}, "
                  f"mean g_cv={mean_g})")

        # Write per-chain CSV
        out_csv = H1_DATA / f"h10v11_w{w54}_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["chain_id", "q10", "g_cv", "q11", "rank_v10", "rank_v11",
                        "h11_label_v11"])
            for c in chains_v11:
                cid = c["chain_id"]
                w.writerow([cid, c["q10"], c["g_cv"] if c["g_cv"] is not None else "",
                            c["q11"], rank_v10[cid], rank_v11[cid],
                            h11_label(c["q11"])])

        summary["videos"][stem] = {
            "w54": w54,
            "n_chains": len(chains_v11),
            "n_improved": len(improved),
            "n_demoted": len(demoted),
            "n_unchanged": len(unchanged),
            "mean_q10": round(statistics.mean(c["q10"] for c in chains_v11), 4),
            "mean_q11": round(statistics.mean(c["q11"] for c in chains_v11), 4),
            "n_confident_v10": n_conf_v10,
            "n_confident_v11": n_conf_v11,
            "top_5_improved": [
                {"chain_id": cid, "rank_v10": r10, "rank_v11": r11,
                 "q10": q10, "q11": q11, "g_cv": g}
                for cid, q10, g, q11, r10, r11 in improved[:5]
            ],
            "top_5_demoted": [
                {"chain_id": cid, "rank_v10": r10, "rank_v11": r11,
                 "q10": q10, "q11": q11, "g_cv": g}
                for cid, q10, g, q11, r10, r11 in demoted[:5]
            ],
        }

    out_path = H1_DATA / "h10v11_summary.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
