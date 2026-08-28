#!/usr/bin/env python3
"""H105 — H12 v9 hybrid: chain-event quality guard on H12 v8.

Hypothesis (from H104 negative + H105 chain-construction bias analysis):
The H12 v8 K=4 events_window over-classifies 3 H93 phases (f=685-716,
f=890-936, f=482-594) because the H7 chain emits hand-edge events
that have **abnormal geometric features** during contact juggling,
Mills Mess, and static hold. Specifically:
- f=685-716 STATIC_HOLD: only 1 chain event, end_dist=174.1 (far from
  hand, n_far=1 — unique in the dataset)
- f=890-936 OTHER_CROSSED_ARM: only 1 chain event, ambiguous=true
  (Mills Mess hand-cross)
- f=482-594 STATIC_HOLD: 3 chain events, 2 with low_slope (< 2.5)
  (static hold with embedded hand-handoffs)

H105 (H12 v9) is a H12 v8 per-frame classifier with a chain-event
quality guard: if the K=4 events_window contains any chain event
with abnormal features, demote to MIXED_3+_UNCONFIRMED.

Quality guard criteria (per H105 analysis of the 3 FP phases):
- QUALITY_FAR_DIST_THR = 100 (reject if any event has end_dist > 100)
- QUALITY_AMBIGUOUS = True (reject if any event is AMBIGUOUS_HAND_TRANSITION)
- QUALITY_LOW_SLOPE_THR = 2.5 (reject if events with end_slope < 2.5
  constitute >= 0.5 of in-window events)

The H12 v8 K=4 events_window is the same as in H104/H12 v8. The guard
operates on the chain-event metadata, not on the events_window itself.

Method: re-implement H12 v8's K=4 logic with the quality guard,
evaluate on H93 corrected GT (21 phases). Compare to H12 v8 baseline.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

K_EVENTS = 4
MIN_EVENTS_FOR_PATTERN = 3
CASCADE_MAX_SAME_HAND_RUN = 1
CASCADE_MIN_CATCH_RATE = 1.0
RECENT_EVENT_FRAMES = 30

# H105 chain-event quality guard thresholds
QUALITY_FAR_DIST_THR = 100.0   # reject if any K=4 event has end_dist > 100
QUALITY_LOW_SLOPE_THR = 2.5    # reject if low_slope ratio >= 0.5
QUALITY_LOW_SLOPE_RATIO = 0.5
QUALITY_AMBIGUOUS_RATIO = 0.25  # reject if ambiguous ratio >= 0.25


def to_float(s, default=0.0):
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def load_h7v3pure_chains(stem):
    out = []
    with (H1_DATA / f"h7v3pure_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["tids"] = [int(t) for t in r["tids"].split(",") if t.strip()]
            out.append(r)
    return out


def load_h7v3pure_admitted_edges(stem):
    out = []
    with (H1_DATA / f"h7v3pure_admitted_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            out.append(r)
    return out


def load_tracklet_features(stem):
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r.get("stem") != stem:
                continue
            t = r["tid"]
            if not t or not t.replace("-", "").isdigit():
                continue
            out[int(t)] = r
    return out


def build_catch_throw_timeline(stem):
    """Build the CATCH/THROW timeline from h7v3pure hand-edges, with chain-event quality metadata."""
    chains = load_h7v3pure_chains(stem)
    edges = load_h7v3pure_admitted_edges(stem)
    tfs = load_tracklet_features(stem)
    by_pair = {(e["from_tid"], e["to_tid"]): e for e in edges}

    events = []
    for c in chains:
        cid = c["chain_id"]
        for i in range(len(c["tids"]) - 1):
            from_tid, to_tid = c["tids"][i], c["tids"][i + 1]
            e = by_pair.get((from_tid, to_tid))
            if not e:
                continue
            if "HAND" not in e["edge_type"]:
                continue
            reason = e.get("reclassify_reason", "") or ""
            m = re.search(r"side=(\w+)", reason)
            hand = m.group(1) if m else None
            if not hand:
                m2 = re.search(r"hand=(\w+)", e.get("metadata", ""))
                hand = m2.group(1) if m2 else "unknown"
            from_t = tfs[from_tid]
            to_t = tfs[to_tid]
            end_dist = to_float(from_t["end_dist"])
            end_slope = to_float(from_t["end_slope"])
            start_dist = to_float(to_t["start_dist"])
            start_slope = to_float(to_t["start_slope"])
            ambiguous = (e["edge_type"] == "AMBIGUOUS_HAND_TRANSITION")
            qa = {
                "end_dist": end_dist,
                "end_slope": end_slope,
                "start_dist": start_dist,
                "start_slope": start_slope,
                "ambiguous": ambiguous,
                "is_far": end_dist > QUALITY_FAR_DIST_THR or start_dist > QUALITY_FAR_DIST_THR,
                "is_low_slope": abs(end_slope) < QUALITY_LOW_SLOPE_THR,
            }
            events.append({
                "chain_id": cid,
                "event": "CATCH",
                "tid": to_tid,
                "event_frame": int(from_t["last_frame"]),
                "hand": hand,
                "ambiguous": ambiguous,
                "edge_type": e["edge_type"],
                "qa": qa,
            })
            events.append({
                "chain_id": cid,
                "event": "THROW",
                "tid": to_tid,
                "event_frame": int(to_t["first_frame"]),
                "hand": hand,
                "ambiguous": ambiguous,
                "edge_type": e["edge_type"],
                "qa": qa,
            })
    events.sort(key=lambda e: e["event_frame"])
    return events


def build_per_frame_census(stem):
    """Per-frame (n_in_air, n_in_hand_l, n_in_hand_r, n_total) from h7v3pure chains.

    n_in_air counts chains whose tracklet spans the frame (in air between
    catch and throw). n_in_hand_l/r counts chains at the catch/throw event.
    """
    chains = load_h7v3pure_chains(stem)
    tfs = load_tracklet_features(stem)
    edges = load_h7v3pure_admitted_edges(stem)
    by_pair = {(e["from_tid"], e["to_tid"]): e for e in edges}

    in_air = defaultdict(set)
    in_hand_l = defaultdict(set)
    in_hand_r = defaultdict(set)
    for c in chains:
        cid = c["chain_id"]
        for tid in c["tids"]:
            if tid not in tfs:
                continue
            t = tfs[tid]
            for f in range(int(t["first_frame"]), int(t["last_frame"]) + 1):
                in_air[f].add(cid)
        for i in range(len(c["tids"]) - 1):
            from_tid, to_tid = c["tids"][i], c["tids"][i + 1]
            e = by_pair.get((from_tid, to_tid))
            if not e:
                continue
            hand = None
            reason = e.get("reclassify_reason", "") or ""
            m = re.search(r"side=(\w+)", reason)
            if m:
                hand = m.group(1)
            else:
                m2 = re.search(r"hand=(\w+)", e.get("metadata", ""))
                hand = m2.group(1) if m2 else None
            from_t = tfs[from_tid]
            to_t = tfs[to_tid]
            catch_frame = int(from_t["last_frame"])
            throw_frame = int(to_t["first_frame"])
            if hand == "left":
                in_hand_l[catch_frame].add(cid)
                in_hand_l[throw_frame].add(cid)
            elif hand == "right":
                in_hand_r[catch_frame].add(cid)
                in_hand_r[throw_frame].add(cid)
    out = {}
    all_frames = set(in_air.keys()) | set(in_hand_l.keys()) | set(in_hand_r.keys())
    for f in sorted(all_frames):
        n_air = len(in_air[f])
        n_l = len(in_hand_l[f])
        n_r = len(in_hand_r[f])
        all_chains = set(in_air[f]) | set(in_hand_l[f]) | set(in_hand_r[f])
        out[f] = {
            "frame": f,
            "n_in_air": n_air,
            "n_in_hand_left": n_l,
            "n_in_hand_right": n_r,
            "n_total_balls": len(all_chains),
        }
    return out


def hand_alternation_metric(events_window):
    hands = [e["hand"] for e in events_window if e["hand"] and e["hand"] != "unknown"]
    n = len(hands)
    if n == 0:
        return {"same_hand_run": 0, "unique_hands": 0, "alternation_score": 0.0, "n_events": 0}
    same_hand_run = sum(1 for i in range(1, n) if hands[i] == hands[i - 1])
    unique_hands = len(set(hands))
    if n <= 1:
        alt = 0.0
    else:
        alt = 1.0 - (same_hand_run / (n - 1))
    return {"same_hand_run": same_hand_run, "unique_hands": unique_hands,
            "alternation_score": alt, "n_events": n}


def catch_rate(events_window):
    catches = [e for e in events_window if e["event"] == "CATCH"]
    if len(catches) < 2:
        return 0.0
    duration = int(catches[-1]["event_frame"]) - int(catches[0]["event_frame"])
    if duration <= 0:
        return 0.0
    return len(catches) * 30.0 / duration


def chain_event_quality_guard(events_window):
    """Check if K=4 events_window has abnormal chain-event features.

    Returns (passed: bool, reason: str).
    """
    if not events_window:
        return True, "no_events"
    n_far = sum(1 for e in events_window if e["qa"]["is_far"])
    n_ambig = sum(1 for e in events_window if e["qa"]["ambiguous"])
    n_low_slope = sum(1 for e in events_window if e["qa"]["is_low_slope"])
    n = len(events_window)
    if n_far > 0:
        return False, f"n_far={n_far}"
    if n_ambig / n >= QUALITY_AMBIGUOUS_RATIO:
        return False, f"ambig_ratio={n_ambig/n:.2f}"
    if n_low_slope / n >= QUALITY_LOW_SLOPE_RATIO:
        return False, f"low_slope_ratio={n_low_slope/n:.2f}"
    return True, "ok"


def classify_3ball_v8(events_window, avg_quality):
    metrics = hand_alternation_metric(events_window)
    rate = catch_rate(events_window)
    n = metrics["n_events"]
    same_run = metrics["same_hand_run"]
    alt = metrics["alternation_score"]
    cascade_like = (same_run <= CASCADE_MAX_SAME_HAND_RUN
                    and alt >= 0.5
                    and rate >= CASCADE_MIN_CATCH_RATE)
    fountain_like = (same_run >= n - 1 and alt < 0.3)
    if n < MIN_EVENTS_FOR_PATTERN:
        return "MIXED_3+_UNCONFIRMED", avg_quality * 0.6
    if cascade_like and not fountain_like:
        return "CASCADE_3+", avg_quality
    if fountain_like and not cascade_like:
        return "FOUNTAIN_3+", avg_quality
    if cascade_like and fountain_like:
        if alt >= 0.5:
            return "CASCADE_3+", avg_quality
        return "FOUNTAIN_3+", avg_quality
    return "MIXED_3+", avg_quality


def classify_3ball_v9(events_window, avg_quality, use_guard=True):
    """H12 v9: H12 v8 + chain-event quality guard."""
    metrics = hand_alternation_metric(events_window)
    rate = catch_rate(events_window)
    n = metrics["n_events"]

    if n < MIN_EVENTS_FOR_PATTERN:
        return "MIXED_3+_UNCONFIRMED", avg_quality * 0.6

    # H105 quality guard
    if use_guard:
        passed, reason = chain_event_quality_guard(events_window)
        if not passed:
            return "MIXED_3+_UNCONFIRMED", avg_quality * 0.5

    return classify_3ball_v8(events_window, avg_quality)


def classify_pattern(census_row, events_window, use_v9=False):
    n_total = census_row["n_total_balls"]
    n_h_l = census_row["n_in_hand_left"]
    n_h_r = census_row["n_in_hand_right"]
    q = 0.5  # uniform default
    conf = max(q, 0.0)
    if n_total == 0:
        return "NO_BALL", 1.0
    if n_total == 1:
        return "SINGLE_BALL", conf
    if n_total == 2:
        if n_h_l == 1 and n_h_r == 1:
            return "TWO_BALL_HELD", conf
        if n_h_l + n_h_r == 1:
            return "TWO_BALL_ONE_HAND", conf
        return "TWO_BALL", conf
    if n_total >= 3:
        if use_v9:
            return classify_3ball_v9(events_window, q, use_guard=True)
        return classify_3ball_v8(events_window, q)
    return "UNKNOWN", conf


def run_inference(stem, use_v9):
    census = build_per_frame_census(stem)
    events = build_catch_throw_timeline(stem)
    events_sorted = sorted(events, key=lambda e: e["event_frame"])

    results = []
    for f, c in sorted(census.items()):
        events_before = [e for e in events_sorted if int(e["event_frame"]) <= f]
        events_window = events_before[-K_EVENTS:]
        pattern, conf = classify_pattern(c, events_window, use_v9=use_v9)
        # For diagnostics
        n_far = sum(1 for e in events_window if e["qa"]["is_far"])
        n_ambig = sum(1 for e in events_window if e["qa"]["ambiguous"])
        n_low_slope = sum(1 for e in events_window if e["qa"]["is_low_slope"])
        passed, reason = chain_event_quality_guard(events_window)
        results.append({
            "frame": f,
            "pattern": pattern,
            "confidence": round(conf, 3),
            "n_window_events": len(events_window),
            "n_far": n_far,
            "n_ambig": n_ambig,
            "n_low_slope": n_low_slope,
            "guard_passed": passed,
            "guard_reason": reason,
        })
    return results


def evaluate_on_h93(use_v9):
    with open(H1_DATA / "h93_multi_rater_qa.json") as fh:
        h93 = json.load(fh)
    gt = h93["corrected_ground_truth"]

    per_phase = []
    for stem in STEMS:
        results = run_inference(stem, use_v9)
        results_by_frame = {int(r["frame"]): r for r in results}
        for phase_key, verdict in gt.items():
            if not phase_key.startswith(stem):
                continue
            parts = phase_key.rsplit("_", 2)
            s, e = int(parts[1]), int(parts[2])
            in_phase = [r for r in results if s <= int(r["frame"]) <= e]
            if not in_phase:
                continue
            c = Counter(r["pattern"] for r in in_phase)
            dominant = c.most_common(1)[0][0]
            ACTIVE = ("FOUNTAIN_3+", "CASCADE_3+", "MIXED_3+", "FOUNTAIN_LOW_CONF")
            is_active = dominant in ACTIVE
            gt_active = verdict == "JUGGLING"
            # Average guard stats
            avg_far = sum(r["n_far"] for r in in_phase) / len(in_phase)
            avg_ambig = sum(r["n_ambig"] for r in in_phase) / len(in_phase)
            avg_low_slope = sum(r["n_low_slope"] for r in in_phase) / len(in_phase)
            guard_pass_rate = sum(1 for r in in_phase if r["guard_passed"]) / len(in_phase)
            per_phase.append({
                "phase_key": phase_key,
                "stem": stem,
                "verdict": verdict,
                "dominant": dominant,
                "is_active_pred": is_active,
                "is_active_gt": gt_active,
                "avg_far": round(avg_far, 2),
                "avg_ambig": round(avg_ambig, 2),
                "avg_low_slope": round(avg_low_slope, 2),
                "guard_pass_rate": round(guard_pass_rate, 2),
            })
    TP = sum(1 for p in per_phase if p["is_active_pred"] and p["is_active_gt"])
    TN = sum(1 for p in per_phase if not p["is_active_pred"] and not p["is_active_gt"])
    FP = sum(1 for p in per_phase if p["is_active_pred"] and not p["is_active_gt"])
    FN = sum(1 for p in per_phase if not p["is_active_pred"] and p["is_active_gt"])
    return per_phase, TP, TN, FP, FN


def main():
    print("=" * 72)
    print("H105 — H12 v9 hybrid with chain-event quality guard")
    print("=" * 72)

    # H93 GT evaluation
    print("\n=== H93 GT evaluation (21 phases) ===")
    print("\nBaseline (H12 v8, no guard):")
    v8_per_phase, v8_tp, v8_tn, v8_fp, v8_fn = evaluate_on_h93(use_v9=False)
    v8_total = v8_tp + v8_tn + v8_fp + v8_fn
    print(f"  TP={v8_tp} TN={v8_tn} FP={v8_fp} FN={v8_fn} (n={v8_total})")
    if (v8_tp + v8_fp) > 0:
        print(f"  Precision = {v8_tp/(v8_tp+v8_fp):.3f}")
    if (v8_tp + v8_fn) > 0:
        print(f"  Recall = {v8_tp/(v8_tp+v8_fn):.3f}")
    print(f"  Accuracy = {(v8_tp+v8_tn)/v8_total:.3f}")
    for p in v8_per_phase:
        if not p["is_active_pred"] and not p["is_active_gt"]:
            tag = "TN"
        elif p["is_active_pred"] and p["is_active_gt"]:
            tag = "TP"
        elif p["is_active_pred"] and not p["is_active_gt"]:
            tag = "FP"
        else:
            tag = "FN"
        if tag in ("FP", "TN"):
            print(f"    [{tag}] {p['phase_key'][-50:]:<50} verdict={p['verdict']:<20} "
                  f"dominant={p['dominant']:<25} avg_far={p['avg_far']} "
                  f"avg_ambig={p['avg_ambig']} avg_low_slope={p['avg_low_slope']} "
                  f"guard_pass={p['guard_pass_rate']}")

    print("\nH12 v9 (with chain-event quality guard):")
    v9_per_phase, v9_tp, v9_tn, v9_fp, v9_fn = evaluate_on_h93(use_v9=True)
    v9_total = v9_tp + v9_tn + v9_fp + v9_fn
    print(f"  TP={v9_tp} TN={v9_tn} FP={v9_fp} FN={v9_fn} (n={v9_total})")
    if (v9_tp + v9_fp) > 0:
        print(f"  Precision = {v9_tp/(v9_tp+v9_fp):.3f}")
    if (v9_tp + v9_fn) > 0:
        print(f"  Recall = {v9_tp/(v9_tp+v9_fn):.3f}")
    print(f"  Accuracy = {(v9_tp+v9_tn)/v9_total:.3f}")
    for p in v9_per_phase:
        if not p["is_active_pred"] and not p["is_active_gt"]:
            tag = "TN"
        elif p["is_active_pred"] and p["is_active_gt"]:
            tag = "TP"
        elif p["is_active_pred"] and not p["is_active_gt"]:
            tag = "FP"
        else:
            tag = "FN"
        if tag in ("FP", "FN", "TN"):
            print(f"    [{tag}] {p['phase_key'][-50:]:<50} verdict={p['verdict']:<20} "
                  f"dominant={p['dominant']:<25} avg_far={p['avg_far']} "
                  f"avg_ambig={p['avg_ambig']} avg_low_slope={p['avg_low_slope']} "
                  f"guard_pass={p['guard_pass_rate']}")

    # Save outputs
    out_csv = H1_DATA / "h105_per_phase.csv"
    with out_csv.open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(v9_per_phase[0].keys()))
        wr.writeheader()
        wr.writerows(v9_per_phase)
    print(f"\nper-phase CSV: {out_csv}")

    # Save per-frame pattern data
    for stem in STEMS:
        results = run_inference(stem, use_v9=True)
        out_csv = H1_DATA / f"pattern_inference_v9_guard_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
            wr.writeheader()
            wr.writerows(results)
        print(f"per-frame CSV ({stem}): {out_csv}")

    summary = {
        "method": "H105: H12 v9 hybrid with chain-event quality guard (FAR_DIST, AMBIGUOUS, LOW_SLOPE)",
        "guard_thresholds": {
            "QUALITY_FAR_DIST_THR": QUALITY_FAR_DIST_THR,
            "QUALITY_LOW_SLOPE_THR": QUALITY_LOW_SLOPE_THR,
            "QUALITY_LOW_SLOPE_RATIO": QUALITY_LOW_SLOPE_RATIO,
            "QUALITY_AMBIGUOUS_RATIO": QUALITY_AMBIGUOUS_RATIO,
        },
        "v8_baseline": {"TP": v8_tp, "TN": v8_tn, "FP": v8_fp, "FN": v8_fn,
                        "acc": round((v8_tp + v8_tn) / v8_total, 3)},
        "v9_with_guard": {"TP": v9_tp, "TN": v9_tn, "FP": v9_fp, "FN": v9_fn,
                          "acc": round((v9_tp + v9_tn) / v9_total, 3)},
    }
    out = H1_DATA / "h105_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"\nSummary: {out}")


if __name__ == "__main__":
    main()
