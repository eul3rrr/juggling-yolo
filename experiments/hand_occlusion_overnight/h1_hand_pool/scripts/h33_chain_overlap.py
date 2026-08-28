#!/usr/bin/env python3
"""H33 — tracklet-overlap multi-ball detector on h7v3plus2 chains.

HYPOTHESIS:
  A single physical ball cannot be at two different positions at
  the same time. If two tracklets in the same chain overlap
  temporally (frame i is in both tracklets' time range), they MUST
  be from different physical balls (or a single ball was detected
  twice during occlusion).

  H32 visual QA on 7 chains found 5/7 are MULTI_BALL_MERGE. The
  overlap-based check should be a simple, deterministic signal
  for this.

  H33 hypothesis: chains with tracklet-time overlap are likely
  multi-ball merges. The signal should be strongest on identical
  (where detector has more mid-air detections) and weakest on
  YouTube (where long tracklets span multi-ball phases without
  overlap).

APPROACH (declared from physical geometry, not tuned to labels):
  - For each h7v3plus2 chain, sort its tracklets by first_frame
  - For each consecutive pair (sorted by first_frame), compute
    overlap = max(0, prev_last - curr_first + 1)
  - max_overlap = max overlap across all consecutive pairs
  - total_overlap = sum of overlaps
  - Verdict:
    - MULTI_BALL_HIGH if max_overlap >= 5
    - MULTI_BALL_LOW if 0 < max_overlap < 5
    - SINGLE_BALL_CANDIDATE if max_overlap == 0 AND n_tids >= 2
    - SINGLE_BALL if n_tids == 1

  H32 visual QA: chains 22, 0, 30, 3, 1 were MULTI_BALL_MERGE.
  Chains 29 was UNKNOWN_OK (real 2-ball pattern), 15 was
  SINGLE_CATCH_WRONG.

  Expectation: chains 22, 0, 30, 15, 1 should be MULTI_BALL_HIGH.
  Chain 29 and 3 may or may not be flagged depending on overlap.

OUTPUTS:
  - data/h33_chain_overlap_identical_balls_trick_000_018.csv
  - data/h33_chain_overlap_youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.csv
  - data/h33_summary.json
  - data/h33_visual_qa_check.json (cross-check with H32 verdicts)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = {
    "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

OVERLAP_THRESHOLD_HIGH = 5  # >= 5 frames is strong multi-ball evidence


def load_tracklet_features(stem: str) -> dict[int, dict]:
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            r["tid"] = int(r["tid"])
            r["first_frame"] = int(r["first_frame"])
            r["last_frame"] = int(r["last_frame"])
            r["n_pts"] = int(r["n_pts"])
            out[r["tid"]] = r
    return out


def load_h7v3plus2_chains(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h7v3plus2_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["chain_id"] = int(r["chain_id"])
            r["n_tracklets"] = int(r["n_tracklets"])
            r["first_frame"] = int(r["first_frame"])
            r["last_frame"] = int(r["last_frame"])
            r["tids"] = [int(t) for t in r["tids"].split(",") if t]
            out.append(r)
    return out


def load_h32_metrics(stem: str) -> dict[int, dict]:
    out = {}
    with (H1_DATA / f"h32_chain_metrics_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            out[int(r["chain_id"])] = r
    return out


def per_chain_overlap(chain: dict, tid_meta: dict) -> dict:
    """Compute tracklet overlap for a single chain."""
    ranges = []
    for t in chain["tids"]:
        m = tid_meta.get(t)
        if m:
            ranges.append((t, m["first_frame"], m["last_frame"]))
    ranges.sort(key=lambda x: x[1])

    overlaps = []  # list of (tid_a, tid_b, overlap_frames)
    max_overlap = 0
    max_overlap_pair = None
    total_overlap = 0
    n_overlap_pairs = 0
    for i in range(len(ranges) - 1):
        t_a, f0_a, f1_a = ranges[i]
        t_b, f0_b, f1_b = ranges[i + 1]
        if f1_a >= f0_b:
            ov = f1_a - f0_b + 1
            overlaps.append((t_a, t_b, ov))
            total_overlap += ov
            n_overlap_pairs += 1
            if ov > max_overlap:
                max_overlap = ov
                max_overlap_pair = (t_a, t_b)

    # Verdict
    if chain["n_tracklets"] == 1:
        verdict = "SINGLE_BALL"
    elif max_overlap >= OVERLAP_THRESHOLD_HIGH:
        verdict = "MULTI_BALL_HIGH"
    elif max_overlap > 0:
        verdict = "MULTI_BALL_LOW"
    else:
        verdict = "SINGLE_BALL_CANDIDATE"

    return {
        "chain_id": chain["chain_id"],
        "n_tids": chain["n_tracklets"],
        "n_overlap_pairs": n_overlap_pairs,
        "max_overlap": max_overlap,
        "max_overlap_pair": f"{max_overlap_pair[0]}->{max_overlap_pair[1]}" if max_overlap_pair else "",
        "total_overlap": total_overlap,
        "verdict": verdict,
        "tids": ",".join(str(t) for t in chain["tids"]),
    }


def main() -> None:
    summary = {"videos": {}}
    visual_qa_check = {"videos": {}}

    for stem in STEMS:
        chains = load_h7v3plus2_chains(stem)
        tid_meta = load_tracklet_features(stem)
        h32 = load_h32_metrics(stem)

        per_chain = []
        for c in chains:
            m = per_chain_overlap(c, tid_meta)
            # Add h10v10 quality from h32
            m["h32_pattern"] = h32.get(c["chain_id"], {}).get("pattern_verdict", "")
            m["h10v10_quality"] = h32.get(c["chain_id"], {}).get("h10v10_quality", "")
            m["h32_ball_estimate"] = h32.get(c["chain_id"], {}).get("physical_ball_estimate", "")
            per_chain.append(m)

        # Aggregate stats
        n_multi_tracklet = sum(1 for m in per_chain if m["n_tids"] > 1)
        n_high = sum(1 for m in per_chain if m["verdict"] == "MULTI_BALL_HIGH")
        n_low = sum(1 for m in per_chain if m["verdict"] == "MULTI_BALL_LOW")
        n_single = sum(1 for m in per_chain if m["verdict"] == "SINGLE_BALL_CANDIDATE")
        n_singleton = sum(1 for m in per_chain if m["verdict"] == "SINGLE_BALL")

        # Save per-chain CSV
        out_csv = H1_DATA / f"h33_chain_overlap_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            cols = list(per_chain[0].keys())
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(per_chain)
        print(f"  wrote {out_csv.name}")

        summary["videos"][stem] = {
            "n_chains": len(per_chain),
            "n_multi_tracklet": n_multi_tracklet,
            "n_multi_ball_high": n_high,
            "n_multi_ball_low": n_low,
            "n_single_ball_candidate": n_single,
            "n_singleton": n_singleton,
        }

        # Visual QA cross-check (H32 verdicts)
        visual_qa = {
            22: ("identical", "CASCADE_LIKE", "MULTI_BALL_MERGE"),
            0: ("youtube", "CASCADE_LIKE", "MULTI_BALL_MERGE"),
            30: ("identical", "FOUNTAIN_LIKE", "MULTI_BALL_MERGE"),
            3: ("youtube", "FOUNTAIN_LIKE", "MULTI_BALL_MERGE"),
            29: ("identical", "UNKNOWN", "UNKNOWN_OK"),
            15: ("identical", "SINGLE_CATCH", "SINGLE_CATCH_WRONG"),
            1: ("youtube", "SINGLE_CATCH", "MULTI_BALL_MERGE"),
        }
        qa_check = []
        for cid, (qa_stem, h32_v, vision_v) in visual_qa.items():
            if qa_stem != ("identical" if "identical" in stem else "youtube"):
                continue
            m = next((x for x in per_chain if x["chain_id"] == cid), None)
            if m is None:
                continue
            h33_says_multi = m["verdict"] in ("MULTI_BALL_HIGH", "MULTI_BALL_LOW")
            vision_says_multi = vision_v == "MULTI_BALL_MERGE"
            qa_check.append({
                "chain_id": cid,
                "h32_verdict": h32_v,
                "vision_verdict": vision_v,
                "h33_verdict": m["verdict"],
                "h33_max_overlap": m["max_overlap"],
                "h33_says_multi": h33_says_multi,
                "vision_says_multi": vision_says_multi,
                "agree": h33_says_multi == vision_says_multi,
            })
        visual_qa_check["videos"][stem] = qa_check

    out_json = H1_DATA / "h33_summary.json"
    with out_json.open("w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nwrote {out_json.name}")

    qa_json = H1_DATA / "h33_visual_qa_check.json"
    with qa_json.open("w") as fh:
        json.dump(visual_qa_check, fh, indent=2)
    print(f"wrote {qa_json.name}")

    print("\n=== SUMMARY ===")
    print(json.dumps(summary, indent=2))
    print("\n=== H32/H33 CROSS-CHECK ===")
    for stem, checks in visual_qa_check["videos"].items():
        n_agree = sum(1 for c in checks if c["agree"])
        n_total = len(checks)
        print(f"\n{stem}: {n_agree}/{n_total} agreement")
        for c in checks:
            mark = "OK" if c["agree"] else "X"
            print(f"  [{mark}] chain {c['chain_id']}: h32={c['h32_verdict']} "
                  f"vision={c['vision_verdict']} h33={c['h33_verdict']} "
                  f"max_overlap={c['h33_max_overlap']}")


if __name__ == "__main__":
    main()
