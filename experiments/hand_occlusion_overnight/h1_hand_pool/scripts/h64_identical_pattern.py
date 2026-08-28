#!/usr/bin/env python3
"""H64 - characterize the identical 3-ball pattern (cascade-to-fountain).

H62 found identical 3-ball is 63% same-hand (0.63 rate). H63
characterized YouTube's CASCADE-SHOWER mix. H64 asks: is the
identical 3-ball also a CASCADE-SHOWER mix, or is it a
CASCADE->FOUNTAIN transition?

If the same-hand events are CONCENTRATED in the late phase
(post some temporal boundary), the answer is FOUNTAIN
transition. If they're spread evenly throughout, the answer
is CASCADE-SHOWER mix (similar to YouTube).

Method: bin the same-hand and alt-hand events by frame range
and check for a temporal boundary.

Outputs:
- data/h64_identical_pattern.csv (per-pair + phase)
- data/h64_pattern_summary.json (aggregate stats)
- reports/h64_report.md
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import Counter
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"

STEM = "identical_balls_trick_000_018"


def main() -> None:
    events = list(csv.DictReader(open(
        H1_DATA / f"catch_throw_timeline_v8_{STEM}.csv"
    )))
    catches = sorted(
        [e for e in events if e["event"] == "CATCH" and e["hand"] in ("left", "right")],
        key=lambda e: int(e["event_frame"]),
    )
    throws = sorted(
        [e for e in events if e["event"] == "THROW" and e["hand"] in ("left", "right")],
        key=lambda e: int(e["event_frame"]),
    )

    pairs = []
    for t in throws:
        t_frame = int(t["event_frame"])
        t_hand = t["hand"]
        next_catches = [c for c in catches if int(c["event_frame"]) > t_frame]
        if not next_catches:
            continue
        next_c = min(next_catches, key=lambda c: int(c["event_frame"]))
        same = next_c["hand"] == t_hand
        try:
            q11 = float(t.get("chain_quality", 0))
        except (ValueError, TypeError):
            q11 = 0
        band = "CONF" if q11 >= 0.7 else ("UNC" if q11 >= 0.4 else "LOW")
        pairs.append({
            "throw_frame": t_frame,
            "throw_hand": t_hand,
            "next_catch_frame": int(next_c["event_frame"]),
            "next_catch_hand": next_c["hand"],
            "same_hand": same,
            "gap_frames": int(next_c["event_frame"]) - t_frame,
            "q11": q11,
            "q11_band": band,
            "chain_id": int(t["chain_id"]),
        })

    samehand = [p for p in pairs if p["same_hand"]]
    althand = [p for p in pairs if not p["same_hand"]]
    n_pairs = len(pairs)
    n_same = len(samehand)
    n_alt = len(althand)

    # Find temporal boundary: try every possible split point
    # and find the one that maximizes the same-hand rate difference
    # Require at least 3 events on each side to avoid trivial splits
    best_split = None
    best_diff = 0
    for split_frame in range(50, int(pairs[-1]["throw_frame"]) - 50, 10):
        pre = [p for p in pairs if p["throw_frame"] < split_frame]
        post = [p for p in pairs if p["throw_frame"] >= split_frame]
        if len(pre) < 3 or len(post) < 3:
            continue
        pre_same_rate = sum(1 for p in pre if p["same_hand"]) / len(pre)
        post_same_rate = sum(1 for p in post if p["same_hand"]) / len(post)
        diff = post_same_rate - pre_same_rate
        if diff > best_diff:
            best_diff = diff
            best_split = split_frame

    # Use the best split
    if best_split is None:
        best_split = 500  # fallback
    pre = [p for p in pairs if p["throw_frame"] < best_split]
    post = [p for p in pairs if p["throw_frame"] >= best_split]
    pre_same_rate = sum(1 for p in pre if p["same_hand"]) / max(1, len(pre))
    post_same_rate = sum(1 for p in post if p["same_hand"]) / max(1, len(post))
    pre_n_same = sum(1 for p in pre if p["same_hand"])
    pre_n_total = len(pre)
    post_n_same = sum(1 for p in post if p["same_hand"])
    post_n_total = len(post)

    # Bin by 100-frame windows
    windows = []
    window_size = 100
    last_frame = max(p["throw_frame"] for p in pairs)
    for w_start in range(0, last_frame + window_size, window_size):
        w_end = w_start + window_size
        in_win = [p for p in pairs if w_start <= p["throw_frame"] < w_end]
        if not in_win:
            continue
        n_same_in = sum(1 for p in in_win if p["same_hand"])
        windows.append({
            "window_start": w_start,
            "window_end": w_end,
            "n_pairs": len(in_win),
            "n_same": n_same_in,
            "same_rate": round(n_same_in / len(in_win), 3),
        })

    print(f"Identical 3-ball: {n_pairs} THROW->CATCH pairs")
    print(f"  Same-hand: {n_same} ({n_same/n_pairs:.2f})")
    print(f"  Alt-hand:  {n_alt} ({n_alt/n_pairs:.2f})")
    print()
    print(f"Temporal boundary analysis:")
    print(f"  Best split at f={best_split}")
    print(f"  Pre  (f<{best_split}): {pre_n_same}/{pre_n_total} same-hand ({pre_same_rate:.2f})")
    print(f"  Post (f>={best_split}): {post_n_same}/{post_n_total} same-hand ({post_same_rate:.2f})")
    print()
    print(f"Per 100-frame window:")
    for w in windows:
        print(f"  f={w['window_start']:>4}-{w['window_end']:>4}: "
              f"{w['n_same']:>2}/{w['n_pairs']:>2} same-hand ({w['same_rate']:.2f})")
    print()

    # Check if the post-same-rate is high enough to call FOUNTAIN
    if post_same_rate >= 0.7 and pre_same_rate < 0.6:
        verdict = f"CASCADE->FOUNTAIN transition at f={best_split}"
        print(f"VERDICT: {verdict}")
    elif post_same_rate > pre_same_rate + 0.2:
        verdict = f"CASCADE->MIXED transition at f={best_split}"
        print(f"VERDICT: {verdict}")
    else:
        verdict = "MIXED (no clear phase boundary)"
        print(f"VERDICT: {verdict}")

    # Hand-asymmetry in each phase
    pre_right = sum(1 for p in pre if p["throw_hand"] == "right")
    post_right = sum(1 for p in post if p["throw_hand"] == "right")
    print()
    print(f"Hand symmetry by phase:")
    print(f"  Pre:  right={pre_right}, left={pre_n_total - pre_right}")
    print(f"  Post: right={post_right}, left={post_n_total - post_right}")

    summary = {
        "stem": STEM,
        "n_pairs": n_pairs,
        "n_samehand": n_same,
        "n_althand": n_alt,
        "overall_same_rate": round(n_same / max(1, n_pairs), 3),
        "best_split_frame": best_split,
        "pre_split": {
            "n_pairs": pre_n_total,
            "n_same": pre_n_same,
            "same_rate": round(pre_same_rate, 3),
        },
        "post_split": {
            "n_pairs": post_n_total,
            "n_same": post_n_same,
            "same_rate": round(post_same_rate, 3),
        },
        "same_rate_delta": round(post_same_rate - pre_same_rate, 3),
        "windows": windows,
        "verdict": verdict,
    }
    (H1_DATA / "h64_pattern_summary.json").write_text(json.dumps(summary, indent=2))

    # Per-pair CSV
    (H1_DATA / "h64_identical_pattern.csv").write_text(
        "throw_frame,throw_hand,next_catch_frame,next_catch_hand,"
        "same_hand,gap_frames,q11,q11_band,chain_id,phase\n" +
        "\n".join(
            f"{p['throw_frame']},{p['throw_hand']},{p['next_catch_frame']},"
            f"{p['next_catch_hand']},{p['same_hand']},{p['gap_frames']},"
            f"{p['q11']},{p['q11_band']},{p['chain_id']},"
            f"{'pre' if p['throw_frame'] < best_split else 'post'}"
            for p in pairs
        ) + "\n"
    )
    print(f"\nWrote {H1_DATA / 'h64_identical_pattern.csv'}")
    print(f"Wrote {H1_DATA / 'h64_pattern_summary.json'}")


if __name__ == "__main__":
    main()
