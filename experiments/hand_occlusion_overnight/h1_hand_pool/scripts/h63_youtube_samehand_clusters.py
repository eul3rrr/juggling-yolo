#!/usr/bin/env python3
"""H63 - characterize the YouTube 5-ball same-hand (SHOWER-like) sub-pattern.

H62 found that the YouTube 5-ball pattern is dominantly CASCADE
(70% alt-hand) but has 7 same-hand events (30%). H62 noted that
ALL 7 same-hand events are on the RIGHT hand. H63 asks: are these
7 same-hand events random, or do they form coherent sub-patterns?

Method:
- Cluster the 7 same-hand events by temporal proximity (intervals
  < 100 frames = "burst", >= 100 frames = "isolated").
- For each cluster, characterize: chains involved, time range,
  gap_frames distribution.
- Compare same-hand gap_frames vs alt-hand gap_frames.

Hypothesis: the same-hand events form "SHOWER-like bursts" within
the broader CASCADE pattern. A 5-ball CASCADE-SHOWER mix is a
common juggling pattern (called "Mills Mess" or "CASCADE-SHOWER
transition").

Outputs:
- data/h63_youtube_samehand_clusters.csv (per-pair + cluster ID)
- data/h63_samehand_summary.json (aggregate stats)
- reports/h63_report.md
"""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"

STEM = "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090"

CLUSTER_THRESHOLD_FRAMES = 100  # same-hand events within 100 frames = same cluster


def main() -> None:
    with (H1_DATA / "h62_youtube_pattern.csv").open() as fh:
        rows = list(csv.DictReader(fh))

    samehand = [r for r in rows if r["same_hand"] == "True"]
    althand = [r for r in rows if r["same_hand"] == "False"]

    print(f"YouTube 5-ball: {len(rows)} THROW->CATCH pairs")
    print(f"  Same-hand: {len(samehand)}")
    print(f"  Alt-hand:  {len(althand)}")
    print()

    # Sort same-hand by throw_frame
    samehand.sort(key=lambda r: int(r["throw_frame"]))
    print("Same-hand pairs (chronological):")
    for r in samehand:
        print(f"  f={r['throw_frame']:>3} {r['throw_hand']:>5} -> "
              f"f={r['next_catch_frame']:>3} {r['next_catch_hand']:>5}  "
              f"gap={r['gap_frames']:>3}  chain={r['chain_id']:>2}  q={r['q11_band']}")
    print()

    # Cluster same-hand events by temporal proximity
    clusters = []
    current_cluster = []
    for r in samehand:
        if not current_cluster:
            current_cluster.append(r)
        else:
            last_frame = int(current_cluster[-1]["throw_frame"])
            this_frame = int(r["throw_frame"])
            if this_frame - last_frame <= CLUSTER_THRESHOLD_FRAMES:
                current_cluster.append(r)
            else:
                clusters.append(current_cluster)
                current_cluster = [r]
    if current_cluster:
        clusters.append(current_cluster)

    print(f"Same-hand clusters (threshold={CLUSTER_THRESHOLD_FRAMES} frames):")
    for i, cluster in enumerate(clusters):
        first = int(cluster[0]["throw_frame"])
        last = int(cluster[-1]["throw_frame"])
        chains = set(int(r["chain_id"]) for r in cluster)
        gaps = [int(r["gap_frames"]) for r in cluster]
        print(f"  Cluster {i+1}: n={len(cluster)}, f={first}-{last} (span {last-first}), "
              f"chains={sorted(chains)}, gaps={gaps}")
    print()

    # Gap distribution comparison
    samehand_gaps = [int(r["gap_frames"]) for r in samehand]
    althand_gaps = [int(r["gap_frames"]) for r in althand]
    print("Gap distribution:")
    print(f"  Same-hand: n={len(samehand_gaps)}, "
          f"mean={statistics.mean(samehand_gaps):.1f}, "
          f"median={statistics.median(samehand_gaps):.1f}, "
          f"range={min(samehand_gaps)}-{max(samehand_gaps)}")
    print(f"  Alt-hand:  n={len(althand_gaps)}, "
          f"mean={statistics.mean(althand_gaps):.1f}, "
          f"median={statistics.median(althand_gaps):.1f}, "
          f"range={min(althand_gaps)}-{max(althand_gaps)}")
    print()

    # By q11
    print("By q11 band:")
    for r in rows:
        pass
    samehand_conf = sum(1 for r in samehand if r["q11_band"] == "CONF")
    samehand_unc = sum(1 for r in samehand if r["q11_band"] == "UNC")
    samehand_low = sum(1 for r in samehand if r["q11_band"] == "LOW")
    althand_conf = sum(1 for r in althand if r["q11_band"] == "CONF")
    althand_unc = sum(1 for r in althand if r["q11_band"] == "UNC")
    althand_low = sum(1 for r in althand if r["q11_band"] == "LOW")
    print(f"  Same-hand: CONF={samehand_conf}, UNC={samehand_unc}, LOW={samehand_low}")
    print(f"  Alt-hand:  CONF={althand_conf}, UNC={althand_unc}, LOW={althand_low}")
    print()

    # Hand symmetry check
    samehand_right = sum(1 for r in samehand if r["throw_hand"] == "right")
    samehand_left = sum(1 for r in samehand if r["throw_hand"] == "left")
    print(f"Same-hand by throw hand: right={samehand_right}, left={samehand_left}")
    print(f"  (If one hand dominates same-hand events, it's the 'lead' hand)")
    print()

    # Cluster summary
    summary = {
        "stem": STEM,
        "n_total_pairs": len(rows),
        "n_samehand": len(samehand),
        "n_althand": len(althand),
        "samehand_rate": round(len(samehand) / max(1, len(rows)), 3),
        "n_clusters": len(clusters),
        "clusters": [
            {
                "cluster_id": i + 1,
                "n_events": len(c),
                "first_frame": int(c[0]["throw_frame"]),
                "last_frame": int(c[-1]["throw_frame"]),
                "span": int(c[-1]["throw_frame"]) - int(c[0]["throw_frame"]),
                "chains": sorted(set(int(r["chain_id"]) for r in c)),
                "gaps": [int(r["gap_frames"]) for r in c],
            }
            for i, c in enumerate(clusters)
        ],
        "samehand_gaps": {
            "n": len(samehand_gaps),
            "mean": round(statistics.mean(samehand_gaps), 2),
            "median": round(statistics.median(samehand_gaps), 2),
            "min": min(samehand_gaps),
            "max": max(samehand_gaps),
        },
        "althand_gaps": {
            "n": len(althand_gaps),
            "mean": round(statistics.mean(althand_gaps), 2),
            "median": round(statistics.median(althand_gaps), 2),
            "min": min(althand_gaps),
            "max": max(althand_gaps),
        },
        "hand_asymmetry": {
            "samehand_right": samehand_right,
            "samehand_left": samehand_left,
            "althand_right": sum(1 for r in althand if r["throw_hand"] == "right"),
            "althand_left": sum(1 for r in althand if r["throw_hand"] == "left"),
        },
        "by_q11": {
            "samehand": {"CONF": samehand_conf, "UNC": samehand_unc, "LOW": samehand_low},
            "althand": {"CONF": althand_conf, "UNC": althand_unc, "LOW": althand_low},
        },
    }

    # Verdict
    print("=" * 60)
    print("VERDICT")
    print("=" * 60)
    multi_cluster_summaries = [c for c in summary["clusters"] if c["n_events"] > 1]
    all_bursts = all(c["span"] < 100 for c in multi_cluster_summaries)
    if len(multi_cluster_summaries) >= 2 and all_bursts:
        print(f"The same-hand events form {len(multi_cluster_summaries)} temporal CLUSTERS (SHOWER-like bursts).")
        print("This is a CASCADE-SHOWER mix, not a pure CASCADE.")
        summary["verdict"] = "CASCADE-SHOWER mix (SHOWER bursts within CASCADE)"
    elif len(samehand) >= 5 and all(r["throw_hand"] == "right" for r in samehand):
        print("The same-hand events are CONCENTRATED on the right hand.")
        print("This is a right-handed SHOWER tendency within CASCADE.")
        summary["verdict"] = "CASCADE with right-handed SHOWER tendency"
    else:
        print("The same-hand events are scattered, suggesting incidental same-hand")
        print("catch+throws in an otherwise CASCADE pattern.")
        summary["verdict"] = "CASCADE with incidental same-hand events"

    # Per-cluster CSV
    with (H1_DATA / "h63_youtube_samehand_clusters.csv").open("w") as fh:
        fh.write("cluster_id,throw_frame,throw_hand,next_catch_frame,next_catch_hand,"
                 "gap_frames,q11,q11_band,chain_id\n")
        for i, c in enumerate(clusters):
            for r in c:
                fh.write(f"{i+1},{r['throw_frame']},{r['throw_hand']},"
                         f"{r['next_catch_frame']},{r['next_catch_hand']},"
                         f"{r['gap_frames']},{r['q11']},{r['q11_band']},"
                         f"{r['chain_id']}\n")
    (H1_DATA / "h63_samehand_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {H1_DATA / 'h63_samehand_clusters.csv'}")
    print(f"Wrote {H1_DATA / 'h63_samehand_summary.json'}")


if __name__ == "__main__":
    main()
