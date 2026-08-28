#!/usr/bin/env python3
"""H60 - per-frame hold-duration distribution across all h7v3plus3 chains.

H58 (and H58 v1) found that the 4 multi-tid CONFIDENT chains have
consistent held-phase durations:
- identical chains 7, 19, 20: gap=11 frames (3-ball cascade signature)
- YouTube chain 6: gap=17 frames (5-ball shower signature)

But the 4-chain sample is tiny. H60 measures the held-phase duration
distribution across ALL h7v3plus3 chains and looks for:
1. Multi-modal signatures (cascade, fountain, shower would have
   different modal held phases)
2. Hand-asymmetry (left vs right hand held-phase distributions)
3. Confidence-band interaction (does H10 v11 v3 quality correlate
   with held-phase duration?)
4. Per-stem comparison (identical 3-ball vs YouTube 5-ball)

Hypothesis: the held-phase distribution should be multi-modal with
distinct peaks for different juggling patterns. The H58 finding of
11-frame and 17-frame peaks should appear in the global distribution.

Output:
- data/h60_hold_duration_dist_<stem>.csv (per-event held phase + chain metadata)
- data/h60_hold_duration_summary.json (aggregate stats)
- reports/h60_report.md
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]


def load_catch_throw_v8(stem: str) -> list[dict]:
    path = H1_DATA / f"catch_throw_timeline_v8_{stem}.csv"
    with path.open() as fh:
        return list(csv.DictReader(fh))


def load_h10v11v3(stem: str) -> dict[int, tuple[float, str]]:
    path = H1_DATA / f"h10v11v3_nonlinear_w0.3_{stem}.csv"
    out = {}
    with path.open() as fh:
        for r in csv.DictReader(fh):
            out[int(r["chain_id"])] = (float(r["q11"]), r["label"])
    return out


def held_phase(event: dict) -> int:
    """gap_frames from the H12 v8 event log = (curr_first_frame - prev_last_frame)."""
    return int(event["gap_frames"])


def main() -> None:
    summary = {"videos": {}}
    for stem in STEMS:
        events = load_catch_throw_v8(stem)
        q11_map = load_h10v11v3(stem)

        # Per-event rows
        rows = []
        # Group by chain_id for per-chain stats
        per_chain = defaultdict(list)
        for ev in events:
            hp = held_phase(ev)
            cid = int(ev["chain_id"])
            q11_val, q11_label = q11_map.get(cid, (None, None))
            row = {
                "chain_id": cid,
                "event": ev["event"],
                "tid": int(ev["tid"]),
                "prev_tid": int(ev["prev_tid"]) if ev["prev_tid"] else None,
                "event_frame": int(ev["event_frame"]),
                "gap_frames": hp,
                "hand": ev["hand"],
                "edge_type": ev["edge_type"],
                "q11": q11_val,
                "q11_label": q11_label,
            }
            rows.append(row)
            per_chain[cid].append(row)

        # Global stats
        all_hp = [r["gap_frames"] for r in rows if r["event"] == "CATCH"]
        all_hp_throw = [r["gap_frames"] for r in rows if r["event"] == "THROW"]
        n_total = len(all_hp)
        n_low = sum(1 for h in all_hp if h < 10)
        n_mid = sum(1 for h in all_hp if 10 <= h < 25)
        n_high = sum(1 for h in all_hp if h >= 25)
        n_extreme = sum(1 for h in all_hp if h >= 50)

        # By hand
        by_hand = defaultdict(list)
        for r in rows:
            if r["event"] == "CATCH" and r["hand"] in ("left", "right"):
                by_hand[r["hand"]].append(r["gap_frames"])

        # By q11 label
        by_q = defaultdict(list)
        for r in rows:
            if r["event"] == "CATCH" and r["q11_label"]:
                by_q[r["q11_label"]].append(r["gap_frames"])

        # Multi-modal analysis: bucketize gap_frames and find peaks
        # Buckets: [0-2), [2-5), [5-10), [10-15), [15-20), [20-30), [30-50), [50+)
        bucket_edges = [0, 2, 5, 10, 15, 20, 30, 50, 200]
        bucket_labels = [f"[{a}-{b})" for a, b in zip(bucket_edges[:-1], bucket_edges[1:])]
        bucket_counts = [0] * len(bucket_labels)
        for h in all_hp:
            for i in range(len(bucket_edges) - 1):
                if bucket_edges[i] <= h < bucket_edges[i + 1]:
                    bucket_counts[i] += 1
                    break
            else:
                # h >= 200
                bucket_counts[-1] += 1
        # Find mode (most common bucket)
        max_bucket_idx = bucket_counts.index(max(bucket_counts))
        mode_bucket = bucket_labels[max_bucket_idx]
        mode_count = bucket_counts[max_bucket_idx]

        # Per-chain: median held phase per chain
        per_chain_stats = []
        for cid, evs in per_chain.items():
            catch_hp = [e["gap_frames"] for e in evs if e["event"] == "CATCH"]
            if not catch_hp:
                continue
            q11_val, q11_label = q11_map.get(cid, (None, None))
            per_chain_stats.append({
                "chain_id": cid,
                "n_events": len(catch_hp),
                "median_gap": statistics.median(catch_hp) if catch_hp else None,
                "min_gap": min(catch_hp) if catch_hp else None,
                "max_gap": max(catch_hp) if catch_hp else None,
                "q11": q11_val,
                "q11_label": q11_label,
            })

        # Stable events: held phase in [10, 20) — "looks like a real hold"
        # Filtered: drop short flights (<10) as identity switches (H45 finding)
        #           and long flights (>=50) as tracker fragmentation (H46)
        stable_hp = [h for h in all_hp if 10 <= h < 50]
        stable_count = len(stable_hp)
        stable_mean = statistics.mean(stable_hp) if stable_hp else 0
        stable_median = statistics.median(stable_hp) if stable_hp else 0

        summary["videos"][stem] = {
            "n_events_catch": n_total,
            "n_events_throw": len(all_hp_throw),
            "min": min(all_hp) if all_hp else 0,
            "max": max(all_hp) if all_hp else 0,
            "mean": round(statistics.mean(all_hp), 2) if all_hp else 0,
            "median": round(statistics.median(all_hp), 2) if all_hp else 0,
            "stdev": round(statistics.stdev(all_hp), 2) if len(all_hp) > 1 else 0,
            "buckets": dict(zip(bucket_labels, bucket_counts)),
            "mode_bucket": mode_bucket,
            "mode_count": mode_count,
            "n_short_lt10": n_low,
            "n_mid_10_25": n_mid,
            "n_high_25_50": n_high - n_extreme,
            "n_extreme_50plus": n_extreme,
            "stable_count": stable_count,
            "stable_mean": round(stable_mean, 2),
            "stable_median": round(stable_median, 2),
            "by_hand": {
                hand: {
                    "n": len(vals),
                    "mean": round(statistics.mean(vals), 2) if vals else 0,
                    "median": round(statistics.median(vals), 2) if vals else 0,
                }
                for hand, vals in by_hand.items()
            },
            "by_q11_label": {
                label: {
                    "n": len(vals),
                    "mean": round(statistics.mean(vals), 2) if vals else 0,
                    "median": round(statistics.median(vals), 2) if vals else 0,
                }
                for label, vals in by_q.items()
            },
            "per_chain_count": len(per_chain_stats),
            "n_chains_with_3plus_events": sum(1 for c in per_chain_stats if c["n_events"] >= 3),
        }

        # Per-event CSV
        (H1_DATA / f"h60_hold_duration_dist_{stem}.csv").write_text(
            "chain_id,event,tid,prev_tid,event_frame,gap_frames,hand,edge_type,q11,q11_label\n" +
            "\n".join(
                f"{r['chain_id']},{r['event']},{r['tid']},{r['prev_tid']},"
                f"{r['event_frame']},{r['gap_frames']},{r['hand']},"
                f"{r['edge_type']},{r['q11']},{r['q11_label']}"
                for r in rows
            ) + "\n"
        )

        print(f"\n=== {stem} ===")
        print(f"  N CATCH events: {n_total}")
        print(f"  mean gap: {summary['videos'][stem]['mean']}, "
              f"median: {summary['videos'][stem]['median']}, "
              f"range: {summary['videos'][stem]['min']}-{summary['videos'][stem]['max']}")
        print(f"  Buckets: {dict(zip(bucket_labels, bucket_counts))}")
        print(f"  Mode bucket: {mode_bucket} ({mode_count} events)")
        print(f"  n_short (gap<10): {n_low}, n_mid (10-25): {n_mid}, "
              f"n_high (25-50): {n_high - n_extreme}, n_extreme (50+): {n_extreme}")
        print(f"  Stable events [10, 50): {stable_count} "
              f"(mean {stable_mean:.2f}, median {stable_median:.2f})")
        print(f"  By hand: {dict(summary['videos'][stem]['by_hand'])}")
        print(f"  By q11 label: {dict(summary['videos'][stem]['by_q11_label'])}")
        print(f"  Per-chain: {len(per_chain_stats)} chains, "
              f"{summary['videos'][stem]['n_chains_with_3plus_events']} with 3+ events")

    # Cross-video comparison
    print("\n=== Cross-video comparison ===")
    for stem in STEMS:
        v = summary["videos"][stem]
        print(f"  {stem}:")
        print(f"    stable mean: {v['stable_mean']}, stable median: {v['stable_median']}")
        print(f"    mode bucket: {v['mode_bucket']} ({v['mode_count']} events)")

    (H1_DATA / "h60_hold_duration_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nWrote {H1_DATA / 'h60_hold_duration_summary.json'}")
    print(f"Wrote {H1_DATA / 'h60_hold_duration_dist_<stem>.csv'} (2 files)")


if __name__ == "__main__":
    main()
