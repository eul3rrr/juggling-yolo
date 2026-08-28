#!/usr/bin/env python3
"""H45: siteswap-style per-event digit estimation from CATCH/THROW events.

HYPOTHESIS:
  H12 v8 infers CASCADE_3+ vs FOUNTAIN_3+ via a K=4 sliding window of
  hand events. The window is too short for late-phase patterns and
  introduces K=4 boundary effects. A siteswap-based approach
  computes the "throw digit" directly from the THROW-to-next-CATCH
  flight time and should produce a more uniform, less window-bound
  pattern inference.

  H45 v1 tests the smallest possible siteswap computation:
  per-chain flight-time statistics, cross-checked against H12 v8
  patterns. Three numbers per chain:
    - median flight time
    - flight-time CV (std/mean)
    - implied siteswap digit (flight_time / video_beat)

  Low CV in a chain means the chain is a uniform-pattern juggling
  cycle. High CV means the chain spans multiple patterns or has
  sparse/fragmented coverage.

ALGORITHM:
  1. Load chain_events_h35_<stem>.csv (CATCH and THROW events).
  2. For each chain, walk events in frame order. For each
     CATCH-THROW pair on the same tracklet, record the hold_time
     (throw_frame - catch_frame). For each THROW, find the next
     CATCH in the same chain and record the flight_time
     (next_catch_frame - throw_frame).
  3. Compute per-chain:
     - n_tracklets (with both CATCH and THROW observed)
     - median hold_time
     - median flight_time
     - flight_time CV (std/mean) (n_tracklets >= 3 only; CV = std/mean)
     - flight_time min/max
  4. Cross-check: do flight-time CVs correlate with H12 v8
     CASCADE_3+ vs FOUNTAIN_3+ phase membership of the chain's
     median frame?
  5. Sensitivity grid: classify chains as UNIFORM (CV < 0.5) or
     MIXED (CV >= 0.5). Report.

ADDITIONAL DIAGNOSTIC: event-log sparsity quantification.
  - Per video: total events, total CATCH->next-CATCH in same chain
    pairs (i.e. how many cross-tracklet catches did H7v3+ produce).
  - For a siteswap analysis to be useful, we need at least 3
    cross-tracklet catches per chain. Count chains with
    n_flights >= 3 vs n_flights < 3.

NOT parameter-tuned. Thresholds (CV < 0.5 = uniform) come from
the empirical observation that uniform juggling cycles have
flight-time std/mean around 0.2-0.4 across jugglers.
"""
from __future__ import annotations

import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# CV threshold for "uniform" siteswap pattern (declared from
# physics, not from labels: a 3-ball cascade with constant beats
# has CV=0 by construction; CV=0.5 admits ~30% noise in flight
# times before flagging as mixed)
UNIFORM_CV_THRESHOLD = 0.5


def load_events(stem: str) -> list[dict]:
    """Load chain events sorted by chain_id and event_frame."""
    with (H1_DATA / f"chain_events_h35_{stem}.csv").open() as f:
        events = list(csv.DictReader(f))
    return events


def compute_per_chain_flight_stats(events: list[dict]) -> dict:
    """For each chain, walk events in time order, compute hold/flight
    times per tracklet, and aggregate per-chain statistics.
    """
    chains = defaultdict(list)
    for e in events:
        chains[e["chain_id"]].append((e["event"], e["tid"], int(e["event_frame"])))

    per_chain = {}
    for cid, evs in chains.items():
        evs = sorted(evs, key=lambda x: x[2])
        holds = []
        flights = []
        # Walk events; each tracklet has CATCH then THROW
        i = 0
        while i < len(evs) - 1:
            if (evs[i][0] == "CATCH"
                and evs[i+1][0] == "THROW"
                and evs[i][1] == evs[i+1][1]):
                catch_frame = evs[i][2]
                throw_frame = evs[i+1][2]
                hold_time = throw_frame - catch_frame
                if hold_time > 0:
                    holds.append(hold_time)
                # Find next CATCH in same chain (any tid)
                for j in range(i+2, len(evs)):
                    if evs[j][0] == "CATCH":
                        next_catch_frame = evs[j][2]
                        flight_time = next_catch_frame - throw_frame
                        if flight_time > 0:
                            flights.append(flight_time)
                        break
                i += 2
            else:
                i += 1

        # Per-chain stats
        chain_stats = {
            "n_tracklets": len(holds),
            "n_flights": len(flights),
            "hold_min": min(holds) if holds else None,
            "hold_median": statistics.median(holds) if holds else None,
            "hold_max": max(holds) if holds else None,
            "flight_min": min(flights) if flights else None,
            "flight_median": statistics.median(flights) if flights else None,
            "flight_max": max(flights) if flights else None,
            "flight_mean": (statistics.mean(flights) if flights else None),
            "flight_std": (statistics.stdev(flights) if len(flights) >= 2 else None),
        }
        if len(flights) >= 2:
            chain_stats["flight_cv"] = chain_stats["flight_std"] / chain_stats["flight_mean"]
            chain_stats["uniform"] = chain_stats["flight_cv"] < UNIFORM_CV_THRESHOLD
        else:
            chain_stats["flight_cv"] = None
            chain_stats["uniform"] = None
        per_chain[cid] = chain_stats
    return per_chain


def load_h12v8_frames(stem: str) -> dict:
    """Load H12 v8 pattern per frame."""
    with (H1_DATA / f"pattern_inference_h35_{stem}.csv").open() as f:
        out = {}
        for r in csv.DictReader(f):
            out[int(r["frame"])] = (r["pattern"], float(r["confidence"]))
    return out


def chain_dominant_pattern(per_chain: dict, events: list[dict],
                           h12_frames: dict) -> dict:
    """For each chain, find its frame range and report the H12 v8
    pattern that dominates within the chain's frame range.
    """
    chains = defaultdict(list)
    for e in events:
        chains[e["chain_id"]].append(int(e["event_frame"]))
    out = {}
    for cid, frames in chains.items():
        fmin, fmax = min(frames), max(frames)
        # Look at all H12 v8 frames in [fmin, fmax]
        pattern_counts = defaultdict(int)
        conf_sum = defaultdict(float)
        for f in range(fmin, fmax + 1):
            pat = h12_frames.get(f, (None, 0))
            if pat[0]:
                pattern_counts[pat[0]] += 1
                conf_sum[pat[0]] += pat[1]
        if pattern_counts:
            dom = max(pattern_counts.items(), key=lambda x: x[1])
            out[cid] = {
                "fmin": fmin,
                "fmax": fmax,
                "dominant_pattern": dom[0],
                "n_pattern_frames": dom[1],
                "all_patterns": dict(pattern_counts),
                "mean_conf": conf_sum[dom[0]] / dom[1],
            }
        else:
            out[cid] = {"fmin": fmin, "fmax": fmax,
                        "dominant_pattern": None, "n_pattern_frames": 0,
                        "all_patterns": {}, "mean_conf": 0.0}
    return out


def main():
    summary = {"videos": {}, "config": {
        "uniform_cv_threshold": UNIFORM_CV_THRESHOLD,
    }}
    overall_chains = []
    for stem in STEMS:
        print(f"\n=== {stem} ===")
        events = load_events(stem)
        per_chain = compute_per_chain_flight_stats(events)
        h12 = load_h12v8_frames(stem)
        dom = chain_dominant_pattern(per_chain, events, h12)
        # Combine
        video_summary = {
            "n_chains": len(per_chain),
            "chains": [],
        }
        for cid in sorted(per_chain, key=lambda c: int(c)):
            cs = per_chain[cid]
            ds = dom.get(cid, {})
            chain_record = {
                "chain_id": cid,
                **cs,
                "fmin": ds.get("fmin"),
                "fmax": ds.get("fmax"),
                "dominant_pattern": ds.get("dominant_pattern"),
                "mean_pattern_conf": round(ds.get("mean_conf", 0), 3),
                "all_patterns": ds.get("all_patterns", {}),
            }
            video_summary["chains"].append(chain_record)
            # Per-chain console
            flight_str = (f"flight med={cs['flight_median']:.0f}"
                          if cs['flight_median'] is not None else "flight=N/A")
            cv_str = (f"CV={cs['flight_cv']:.2f} ({'UNIFORM' if cs['uniform'] else 'MIXED'})"
                      if cs['flight_cv'] is not None else "CV=N/A")
            dom_str = ds.get('dominant_pattern', 'N/A')
            print(f"  chain {cid:>3}: f=[{ds.get('fmin','?'):>4},"
                  f"{ds.get('fmax','?'):>4}] n_tids={cs['n_tracklets']:>2}"
                  f" {flight_str:>16} {cv_str:>22}"
                  f"  dom={dom_str}")
            overall_chains.append({
                "stem": stem,
                "chain_id": cid,
                "n_tracklets": cs["n_tracklets"],
                "flight_median": cs["flight_median"],
                "flight_cv": cs["flight_cv"],
                "uniform": cs["uniform"],
                "dominant_pattern": dom_str,
                "fmin": ds.get("fmin"),
                "fmax": ds.get("fmax"),
            })
        # Aggregate per-pattern flight CV
        by_pattern = defaultdict(list)
        for ch in overall_chains:
            if ch["stem"] != stem:
                continue
            if ch["flight_cv"] is None:
                continue
            by_pattern[ch["dominant_pattern"]].append({
                "chain_id": ch["chain_id"],
                "flight_median": ch["flight_median"],
                "flight_cv": ch["flight_cv"],
                "uniform": ch["uniform"],
            })
        video_summary["per_pattern_summary"] = {
            p: {
                "n_chains": len(v),
                "n_uniform": sum(1 for x in v if x["uniform"]),
                "median_flight_cv": statistics.median([x["flight_cv"] for x in v]) if v else None,
                "median_flight_median": statistics.median([x["flight_median"] for x in v]) if v else None,
            }
            for p, v in by_pattern.items()
        }
        # Print aggregate
        print(f"\n  Per-pattern aggregate (n>=2 flights chains only):")
        for p, s in sorted(video_summary["per_pattern_summary"].items(),
                           key=lambda x: -x[1]["n_chains"]):
            print(f"    {p}: n={s['n_chains']}, uniform={s['n_uniform']},"
                  f" med_CV={s['median_flight_cv']:.2f},"
                  f" med_flight={s['median_flight_median']:.0f}")
        summary["videos"][stem] = video_summary

    # Cross-pattern comparison
    print(f"\n=== Cross-pattern flight-CV comparison ===")
    by_pattern_cv = defaultdict(list)
    for ch in overall_chains:
        if ch["flight_cv"] is not None:
            by_pattern_cv[ch["dominant_pattern"]].append(ch["flight_cv"])
    for p, cvs in sorted(by_pattern_cv.items(), key=lambda x: -len(x[1])):
        if len(cvs) >= 2:
            print(f"  {p}: n={len(cvs)}, mean CV={statistics.mean(cvs):.2f},"
                  f" median CV={statistics.median(cvs):.2f},"
                  f" stdev CV={statistics.stdev(cvs):.2f}")
    summary["cross_pattern_cv"] = {
        p: {
            "n": len(cvs),
            "mean": statistics.mean(cvs) if cvs else None,
            "median": statistics.median(cvs) if cvs else None,
            "stdev": statistics.stdev(cvs) if len(cvs) >= 2 else None,
        }
        for p, cvs in by_pattern_cv.items()
    }

    # Sparsity diagnostic
    print(f"\n=== Event-log sparsity diagnostic ===")
    for stem in STEMS:
        events = load_events(stem)
        chains = defaultdict(list)
        for e in events:
            chains[e["chain_id"]].append(e)
        n_chains = len(chains)
        n_events = len(events)
        n_catches = sum(1 for e in events if e["event"] == "CATCH")
        n_throws = sum(1 for e in events if e["event"] == "THROW")
        # Per-chain: count n_flights (cross-tracklet CATCH->next CATCH)
        per_chain_flights = {}
        for cid, evs in chains.items():
            evs = sorted(evs, key=lambda e: int(e["event_frame"]))
            flights = 0
            i = 0
            while i < len(evs) - 1:
                if (evs[i]["event"] == "CATCH"
                    and evs[i+1]["event"] == "THROW"
                    and evs[i]["tid"] == evs[i+1]["tid"]):
                    throw_frame = int(evs[i+1]["event_frame"])
                    for j in range(i+2, len(evs)):
                        if evs[j]["event"] == "CATCH":
                            flights += 1
                            break
                    i += 2
                else:
                    i += 1
            per_chain_flights[cid] = flights
        n_with_flights = sum(1 for f in per_chain_flights.values() if f > 0)
        n_with_3plus_flights = sum(1 for f in per_chain_flights.values() if f >= 3)
        # Event density: per-frame event rate
        if events:
            fmin = min(int(e["event_frame"]) for e in events)
            fmax = max(int(e["event_frame"]) for e in events)
            duration = max(1, fmax - fmin)
            event_rate = n_events / duration
        else:
            duration = 0
            event_rate = 0
        print(f"  {stem}:")
        print(f"    n_events = {n_events} ({n_catches} catches + {n_throws} throws)")
        print(f"    n_chains = {n_chains}, n_chains with flights = {n_with_flights}, n_chains with 3+ flights = {n_with_3plus_flights}")
        print(f"    event rate = {event_rate:.3f} events/frame (over {duration} frame range)")
        print(f"    For siteswap analysis (n_flights >= 3): only {n_with_3plus_flights}/{n_chains} chains qualify ({100*n_with_3plus_flights/max(1,n_chains):.0f}%)")
        summary["videos"][stem]["sparsity"] = {
            "n_events": n_events,
            "n_catches": n_catches,
            "n_throws": n_throws,
            "n_chains": n_chains,
            "n_chains_with_flights": n_with_flights,
            "n_chains_with_3plus_flights": n_with_3plus_flights,
            "event_rate": event_rate,
            "duration_frames": duration,
        }

    out = H1_DATA / "h45_siteswap_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")

    # Also write per-chain per-tracklet flight data for downstream use
    per_tracklet = []
    for ch in overall_chains:
        # Re-derive per-tracklet flights
        events = [e for e in load_events(ch["stem"])
                  if e["chain_id"] == ch["chain_id"]]
        events = sorted(events, key=lambda e: int(e["event_frame"]))
        i = 0
        while i < len(events) - 1:
            if (events[i]["event"] == "CATCH"
                and events[i+1]["event"] == "THROW"
                and events[i]["tid"] == events[i+1]["tid"]):
                throw_frame = int(events[i+1]["event_frame"])
                for j in range(i+2, len(events)):
                    if events[j]["event"] == "CATCH":
                        next_catch_frame = int(events[j]["event_frame"])
                        per_tracklet.append({
                            "stem": ch["stem"],
                            "chain_id": ch["chain_id"],
                            "throw_tid": events[i+1]["tid"],
                            "throw_frame": throw_frame,
                            "next_catch_tid": events[j]["tid"],
                            "next_catch_frame": next_catch_frame,
                            "flight_time": next_catch_frame - throw_frame,
                        })
                        break
                i += 2
            else:
                i += 1
    out2 = H1_DATA / "h45_siteswap_flights.csv"
    with out2.open("w", newline="") as f:
        if per_tracklet:
            w = csv.DictWriter(f, fieldnames=list(per_tracklet[0].keys()))
            w.writeheader()
            w.writerows(per_tracklet)
    print(f"Saved: {out2} ({len(per_tracklet)} rows)")


if __name__ == "__main__":
    main()
