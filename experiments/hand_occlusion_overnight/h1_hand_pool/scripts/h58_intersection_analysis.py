#!/usr/bin/env python3
"""
H58 - H11 v7 + H10 v11 + H12 v8 triple intersection.

Hypothesis: the 3+1 multi-tid CONFIDENT chains (intersection of
H11 v7 and H10 v11 v3 CONFIDENT criteria) should be the
"purest" single-ball trajectories in the dataset. The H12 v8
catch/throw events on these chains should be a clean
single-ball juggling cycle (e.g., consistent hand alternation,
consistent flight times).

Outputs:
- data/h58_intersection_<stem>.csv: H11 v7 + H10 v11 v3 CONFIDENT chains
- data/h58_event_summary_<stem>.csv: catch/throw events for these chains
- data/h58_summary.json: aggregate
"""

import csv
import json
import statistics
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]
QUALITY_CONFIDENT = 0.7


def load_h10v11v3(stem):
    """Load H56 v1 (H10 v11 v3) labels."""
    path = H1_DATA / f"h10v11v3_nonlinear_w0.3_{stem}.csv"
    out = {}
    with path.open() as fh:
        for r in csv.DictReader(fh):
            out[r["chain_id"]] = (float(r["q11"]), r["label"])
    return out


def load_h7v3plus3(stem):
    """Load chain topology."""
    path = H1_DATA / f"h7v3plus3_chains_{stem}.csv"
    out = {}
    with path.open() as fh:
        for r in csv.DictReader(fh):
            tids = [int(t) for t in r["tids"].split(",") if t.strip()]
            out[r["chain_id"]] = {"n_tracklets": int(r["n_tracklets"]),
                                  "tids": tids,
                                  "first_frame": int(r["first_frame"]),
                                  "last_frame": int(r["last_frame"])}
    return out


def load_catch_throw_v8(stem):
    """Load H12 v8 catch/throw events."""
    path = H1_DATA / f"catch_throw_timeline_v8_{stem}.csv"
    events = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            events.append({
                "chain_id": r["chain_id"],
                "event": r["event"],
                "tid": int(r["tid"]),
                "prev_tid": int(r["prev_tid"]) if r["prev_tid"] else None,
                "event_frame": int(r["event_frame"]),
                "gap_frames": int(r["gap_frames"]) if r["gap_frames"] else None,
                "hand": r["hand"],
                "chain_quality": float(r["chain_quality"]),
                "edge_type": r["edge_type"],
            })
    return events


def main():
    summary = {"videos": {}, "config": {"QUALITY_CONFIDENT": QUALITY_CONFIDENT}}
    for stem in STEMS:
        print(f"\n=== {stem} (H58 H11 v7 + H10 v11 v3 intersection) ===")
        h56 = load_h10v11v3(stem)
        chains = load_h7v3plus3(stem)
        events = load_catch_throw_v8(stem)

        # H10 v11 v3 multi-tid CONFIDENT chains
        confident = []
        for cid, info in chains.items():
            q11, label = h56.get(cid, (None, None))
            if label == "CONFIDENT" and info["n_tracklets"] >= 2:
                confident.append({
                    "chain_id": cid,
                    "n_tracklets": info["n_tracklets"],
                    "tids": info["tids"],
                    "first_frame": info["first_frame"],
                    "last_frame": info["last_frame"],
                    "q11": q11,
                })
        confident.sort(key=lambda c: int(c["chain_id"]))
        print(f"  Multi-tid CONFIDENT chains (H56 v1): {len(confident)}")
        for c in confident:
            print(f"    chain {c['chain_id']:>2}: n_tids={c['n_tracklets']}, "
                  f"q11={c['q11']:.3f}, tids={c['tids']}, "
                  f"f={c['first_frame']}-{c['last_frame']}")
        # Catch/throw events on these chains
        confident_ids = set(c["chain_id"] for c in confident)
        events_for_conf = [e for e in events if e["chain_id"] in confident_ids]
        catches = [e for e in events_for_conf if e["event"] == "CATCH"]
        throws = [e for e in events_for_conf if e["event"] == "THROW"]
        print(f"  Catch/throw events on these chains: "
              f"{len(catches)} catches, {len(throws)} throws")
        # Hand alternation
        hands_seq = [e["hand"] for e in events_for_conf if e["hand"]]
        if hands_seq:
            n_alt = sum(1 for i in range(1, len(hands_seq))
                        if hands_seq[i] != hands_seq[i-1])
            alt_rate = n_alt / (len(hands_seq) - 1) if len(hands_seq) > 1 else 0
            print(f"  Hand sequence: {hands_seq}")
            print(f"  Hand alternation rate: {alt_rate:.2f}")
        # Gap distribution
        gaps = [e["gap_frames"] for e in events_for_conf
                if e["gap_frames"] is not None]
        if gaps:
            print(f"  Gap frames: min={min(gaps)}, max={max(gaps)}, "
                  f"mean={statistics.mean(gaps):.1f}, "
                  f"median={statistics.median(gaps):.1f}")

        # Save intersection CSV
        out_csv = H1_DATA / f"h58_intersection_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["chain_id", "n_tracklets", "tids", "first_frame",
                        "last_frame", "q11"])
            for c in confident:
                w.writerow([c["chain_id"], c["n_tracklets"],
                            ",".join(str(t) for t in c["tids"]),
                            c["first_frame"], c["last_frame"], c["q11"]])

        # Save event summary
        out_events = H1_DATA / f"h58_event_summary_{stem}.csv"
        with out_events.open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["chain_id", "event", "tid", "prev_tid", "event_frame",
                        "gap_frames", "hand", "edge_type"])
            for e in events_for_conf:
                w.writerow([e["chain_id"], e["event"], e["tid"],
                            e["prev_tid"] if e["prev_tid"] is not None else "",
                            e["event_frame"], e["gap_frames"] if e["gap_frames"] is not None else "",
                            e["hand"], e["edge_type"]])

        summary["videos"][stem] = {
            "n_confident_chains": len(confident),
            "n_catches": len(catches),
            "n_throws": len(throws),
            "n_alt_hands": n_alt if hands_seq else 0,
            "n_hand_seq": len(hands_seq),
            "alt_rate": round(alt_rate, 3) if hands_seq else None,
            "gap_min": min(gaps) if gaps else None,
            "gap_max": max(gaps) if gaps else None,
            "gap_mean": round(statistics.mean(gaps), 1) if gaps else None,
            "gap_median": round(statistics.median(gaps), 1) if gaps else None,
        }

    out_path = H1_DATA / "h58_summary.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
