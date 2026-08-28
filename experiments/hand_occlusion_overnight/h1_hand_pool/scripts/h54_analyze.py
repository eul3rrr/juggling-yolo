#!/usr/bin/env python3
"""
H54b - H54 cross-reference analysis.

Hypothesis: the per-chain gravity CV (H54) is a single-ball signal
complementary to the H10 v10 quality score and the H11 v7 confidence
label. This script:
1. Loads H54 per-chain data.
2. Cross-references with H10 v10 quality + H11 v7 confidence.
3. Reports mean g_cv per (multi-tid, CONFIDENT/UNCERTAIN) stratum.
4. Visualizes the g_cv distribution.

Outputs:
- data/h54_with_h10_h11_<stem>.csv: per-chain H54 + H10 + H11 fields
- data/h54_analysis_summary.json: aggregate statistics
- reports/h54_report.md: full report (rendered externally)
"""

import csv
import json
import statistics
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

# H11 v7 confidence thresholds
QUALITY_CONFIDENT = 0.7
QUALITY_TRUSTABLE = 0.4

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]


def h11_label(q):
    """Replicate H11 v7's confidence labeling."""
    if q is None:
        return "UNKNOWN"
    if q >= QUALITY_CONFIDENT:
        return "CONFIDENT"
    if q >= QUALITY_TRUSTABLE:
        return "UNCERTAIN"
    return "LOW"


def load_h54_per_chain(stem):
    """Return list of dicts from H54 per-chain CSV."""
    path = H1_DATA / f"h54_per_chain_arc_gravity_{stem}.csv"
    out = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            out.append({
                "chain_id": r["chain_id"],
                "n_tracklets": int(r["n_tracklets"]),
                "n_arcs_total": int(r["n_arcs_total"]),
                "n_arcs_clean": int(r["n_arcs_clean"]),
                "g_mean_all": r["g_mean_all"] or None,
                "g_mean_clean": r["g_mean_clean"] or None,
                "g_std_clean": r["g_std_clean"] or None,
                "g_cv_clean": r["g_cv_clean"] or None,
                "h10_quality_v10": r["h10_quality_v10"] or None,
            })
    return out


def main():
    summary = {"videos": {}, "config": {
        "QUALITY_CONFIDENT": QUALITY_CONFIDENT,
        "QUALITY_TRUSTABLE": QUALITY_TRUSTABLE,
    }}
    for stem in STEMS:
        print(f"\n=== {stem} (H54 cross-reference) ===")
        rows = load_h54_per_chain(stem)
        # Parse numerics
        for r in rows:
            r["h10_q"] = float(r["h10_quality_v10"]) if r["h10_quality_v10"] else None
            r["h11_label"] = h11_label(r["h10_q"])
            r["g_cv"] = float(r["g_cv_clean"]) if r["g_cv_clean"] else None
            r["g_mean"] = float(r["g_mean_clean"]) if r["g_mean_clean"] else None
            r["g_std"] = float(r["g_std_clean"]) if r["g_std_clean"] else None
            r["is_multi"] = r["n_tracklets"] >= 2

        # Write enriched CSV
        out_csv = H1_DATA / f"h54_with_h10_h11_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["chain_id", "n_tracklets", "is_multi",
                        "n_arcs_total", "n_arcs_clean",
                        "g_mean_clean", "g_std_clean", "g_cv_clean",
                        "h10_quality_v10", "h11_label"])
            for r in rows:
                w.writerow([r["chain_id"], r["n_tracklets"], r["is_multi"],
                            r["n_arcs_total"], r["n_arcs_clean"],
                            r["g_mean"], r["g_std"], r["g_cv"],
                            r["h10_q"], r["h11_label"]])

        # Per-stratum statistics
        strata = {}
        for r in rows:
            if r["g_cv"] is None:
                continue
            key = (r["is_multi"], r["h11_label"])
            strata.setdefault(key, []).append(r["g_cv"])
        print("  Stratum (is_multi, h11_label): n, mean g_cv, median g_cv, min, max")
        for key in sorted(strata.keys()):
            cvs = strata[key]
            n = len(cvs)
            mean = statistics.mean(cvs)
            med = statistics.median(cvs)
            mn = min(cvs)
            mx = max(cvs)
            print(f"    {key}: n={n}, mean={mean:.3f}, med={med:.3f}, "
                  f"min={mn:.3f}, max={mx:.3f}")
        # H11 v7 question: do CONFIDENT chains have lower g_cv than
        # UNCERTAIN/LOW chains among multi-tracklet chains?
        # (single-ball chains should have consistent g across all arcs)
        # (multi-ball merges should have inconsistent g)
        multi_confident = [r["g_cv"] for r in rows
                           if r["is_multi"] and r["h11_label"] == "CONFIDENT"
                           and r["g_cv"] is not None]
        multi_uncert = [r["g_cv"] for r in rows
                        if r["is_multi"] and r["h11_label"] == "UNCERTAIN"
                        and r["g_cv"] is not None]
        multi_low = [r["g_cv"] for r in rows
                     if r["is_multi"] and r["h11_label"] == "LOW"
                     and r["g_cv"] is not None]
        # All multi (regardless of h11 label)
        all_multi = [r["g_cv"] for r in rows
                     if r["is_multi"] and r["g_cv"] is not None]
        # Per-chain g_cv ranking (highest CV = most inconsistent = likely
        # multi-ball merge)
        rows_with_cv = [r for r in rows if r["g_cv"] is not None]
        rows_with_cv.sort(key=lambda r: r["g_cv"], reverse=True)
        # Top-5 highest CV
        print("  Top-5 highest g_cv (most inconsistent):")
        for r in rows_with_cv[:5]:
            print(f"    chain {r['chain_id']:>2} (multi={r['is_multi']}, "
                  f"h11={r['h11_label']}, n_tids={r['n_tracklets']}, "
                  f"n_arcs={r['n_arcs_clean']}): g_cv={r['g_cv']:.3f}")
        # Top-5 lowest CV
        print("  Top-5 lowest g_cv (most consistent):")
        for r in rows_with_cv[-5:]:
            print(f"    chain {r['chain_id']:>2} (multi={r['is_multi']}, "
                  f"h11={r['h11_label']}, n_tids={r['n_tracklets']}, "
                  f"n_arcs={r['n_arcs_clean']}): g_cv={r['g_cv']:.3f}")

        # Bootstrap 90% CI for difference CONFIDENT vs UNCERTAIN
        # among multi-tracklet chains
        def bootstrap_diff(a, b, n_iter=1000):
            import random
            random.seed(42)
            obs = []
            for _ in range(n_iter):
                sa = [random.choice(a) for _ in range(len(a))]
                sb = [random.choice(b) for _ in range(len(b))]
                obs.append(statistics.mean(sb) - statistics.mean(sa))
            obs.sort()
            return obs[int(0.05 * n_iter)], obs[int(0.95 * n_iter)]

        ci_text = None
        if len(multi_confident) >= 2 and len(multi_uncert) >= 2:
            lo, hi = bootstrap_diff(multi_confident, multi_uncert)
            ci_text = (f"  Bootstrap 90% CI: "
                       f"mean(UNCERTAIN) - mean(CONFIDENT) = "
                       f"[{lo:+.3f}, {hi:+.3f}]")
            print(ci_text)
        elif len(multi_confident) >= 2 and len(multi_low) >= 2:
            lo, hi = bootstrap_diff(multi_confident, multi_low)
            ci_text = (f"  Bootstrap 90% CI: "
                       f"mean(LOW) - mean(CONFIDENT) = "
                       f"[{lo:+.3f}, {hi:+.3f}]")
            print(ci_text)
        elif len(multi_confident) >= 2:
            ci_text = f"  (no UNCERTAIN/LOW multi-tid chains to compare)"
            print(ci_text)

        # Pearson correlation of g_cv vs h10 quality
        pairs = [(r["g_cv"], r["h10_q"]) for r in rows
                 if r["g_cv"] is not None and r["h10_q"] is not None]
        pearson = None
        if len(pairs) >= 2:
            xs = [p[0] for p in pairs]
            ys = [p[1] for p in pairs]
            mx = statistics.mean(xs)
            my = statistics.mean(ys)
            num = sum((x - mx) * (y - my) for x, y in pairs)
            dx = (sum((x - mx) ** 2 for x in xs)) ** 0.5
            dy = (sum((y - my) ** 2 for y in ys)) ** 0.5
            if dx > 0 and dy > 0:
                pearson = num / (dx * dy)
            print(f"  Pearson(g_cv, h10_quality) = {pearson:.3f} (n={len(pairs)})")

        summary["videos"][stem] = {
            "n_chains": len(rows),
            "n_chains_with_g_cv": sum(1 for r in rows if r["g_cv"] is not None),
            "n_multi": sum(1 for r in rows if r["is_multi"]),
            "n_confident": sum(1 for r in rows if r["h11_label"] == "CONFIDENT"),
            "n_uncertain": sum(1 for r in rows if r["h11_label"] == "UNCERTAIN"),
            "n_low": sum(1 for r in rows if r["h11_label"] == "LOW"),
            "n_multi_confident": len(multi_confident),
            "n_multi_uncert": len(multi_uncert),
            "n_multi_low": len(multi_low),
            "g_cv_mean_multi_confident": round(statistics.mean(multi_confident), 3)
                if multi_confident else None,
            "g_cv_median_multi_confident": round(statistics.median(multi_confident), 3)
                if multi_confident else None,
            "g_cv_mean_multi_uncert": round(statistics.mean(multi_uncert), 3)
                if multi_uncert else None,
            "g_cv_median_multi_uncert": round(statistics.median(multi_uncert), 3)
                if multi_uncert else None,
            "g_cv_mean_all_multi": round(statistics.mean(all_multi), 3)
                if all_multi else None,
            "pearson_g_cv_h10": round(pearson, 3) if pearson is not None else None,
        }

    out_path = H1_DATA / "h54_analysis_summary.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
