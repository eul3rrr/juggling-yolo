#!/usr/bin/env python3
"""H104 — H12 v9 continuous-density pattern classifier.

Hypothesis (from H103): H12 v8 over-classifies H93 STATIC_HOLD /
OTHER_CROSSED_ARM phases as active patterns (FOUNTAIN_3+ / CASCADE_3+)
because its K=4 sliding window (last 4 events, regardless of time)
treats sparse hand-handoff events the same as dense active juggling.

A real cascade has 4+ events in 30-60 frames. A static hold with
hand-handoffs has 4 events spread over 100+ frames. The K=4 window
sees both as "n=4 events" but the time density is very different.

H104 (H12 v9) adds a TIME-DENSITY check:
- For each frame, compute time_span = event_frame[-1] - event_frame[0]
  in the K=4 events_window.
- If time_span > TIME_SPAN_MAX, the events are too sparse for a
  non-UNCONFIRMED classification.
- Default operating point: TIME_SPAN_MAX=80 frames (~2.7s at 30fps).

This should preserve FOUNTAIN_3+ on real juggling phases (where
4 events in 30-60 frames) but demote FOUNTAIN_3+ on static hold
phases (where 4 events in 100+ frames).

Method: re-implement H12 v8's K=4 logic with the time-density
guard, evaluate on H93 corrected GT (21 phases).
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


def load_h7v3pure_chains(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h7v3pure_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["chain_id"] = int(r["chain_id"])
            r["n_tracklets"] = int(r["n_tracklets"])
            r["first_frame"] = int(r["first_frame"])
            r["last_frame"] = int(r["last_frame"])
            r["tids"] = [int(t) for t in r["tids"].split(",") if t.strip()]
            out.append(r)
    return out


def load_h7v3pure_admitted_edges(stem: str) -> list[dict]:
    out = []
    with (H1_DATA / f"h7v3pure_admitted_edges_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            out.append(r)
    return out


def load_tracklet_features(stem: str) -> dict[int, dict]:
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
        for r in csv.DictReader(fh):
            t = r["tid"]
            if not t or not t.replace("-", "").isdigit():
                continue
            tid = int(t)
            # match by stem column (the bare name) since `video`
            # column includes the videos/ path prefix
            row_stem = r.get("stem", "") or r.get("video", "")
            if row_stem != stem:
                continue
            out[tid] = {
                "first_frame": int(r["first_frame"]),
                "last_frame": int(r["last_frame"]),
            }
    return out


def load_h10v9_quality(stem: str) -> dict[int, float]:
    out = {}
    with (H1_DATA / f"h10v9_chain_quality_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            out[int(r["chain_id"])] = float(r["quality_v9"])
    return out


def parse_hand_from_metadata(metadata: str) -> str | None:
    m = re.search(r"hand=(\w+)", metadata)
    if m:
        return m.group(1)
    m = re.search(r"side=(\w+)", metadata)
    if m:
        return m.group(1)
    return None


def build_catch_throw_timeline(stem: str) -> list[dict]:
    """Build the CATCH/THROW timeline from h7v3pure hand-edges only."""
    chains = load_h7v3pure_chains(stem)
    edges = load_h7v3pure_admitted_edges(stem)
    tfs = load_tracklet_features(stem)
    h10v9_q = load_h10v9_quality(stem)
    by_pair = {(e["from_tid"], e["to_tid"]): e for e in edges}

    events = []
    for c in chains:
        cid = c["chain_id"]
        quality = h10v9_q.get(cid, 0.0)
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
                hand = parse_hand_from_metadata(e["metadata"]) or "unknown"
            from_t = tfs[from_tid]
            to_t = tfs[to_tid]
            events.append({
                "chain_id": cid,
                "event": "CATCH",
                "tid": to_tid,
                "prev_tid": from_tid,
                "event_frame": from_t["last_frame"],
                "prev_last_frame": from_t["last_frame"],
                "curr_first_frame": to_t["first_frame"],
                "gap_frames": to_t["first_frame"] - from_t["last_frame"],
                "hand": hand,
                "ambiguous": (e["edge_type"] == "AMBIGUOUS_HAND_TRANSITION"),
                "chain_quality": quality,
                "edge_type": e["edge_type"],
            })
            events.append({
                "chain_id": cid,
                "event": "THROW",
                "tid": to_tid,
                "prev_tid": from_tid,
                "event_frame": to_t["first_frame"],
                "prev_last_frame": from_t["last_frame"],
                "curr_first_frame": to_t["first_frame"],
                "gap_frames": to_t["first_frame"] - from_t["last_frame"],
                "hand": hand,
                "ambiguous": (e["edge_type"] == "AMBIGUOUS_HAND_TRANSITION"),
                "chain_quality": quality,
                "edge_type": e["edge_type"],
            })
    events.sort(key=lambda e: e["event_frame"])
    return events


def build_per_frame_census(stem: str) -> dict[int, dict]:
    """Per-frame (n_in_air, n_in_hand_l, n_in_hand_r, n_total) from h7v3pure chains."""
    chains = load_h7v3pure_chains(stem)
    tfs = load_tracklet_features(stem)
    edges = load_h7v3pure_admitted_edges(stem)
    h10v9_q = load_h10v9_quality(stem)
    by_pair = {(e["from_tid"], e["to_tid"]): e for e in edges}

    in_air: dict[int, set[int]] = defaultdict(set)
    in_hand_l: dict[int, set[int]] = defaultdict(set)
    in_hand_r: dict[int, set[int]] = defaultdict(set)
    chain_qualities = h10v9_q

    for c in chains:
        cid = c["chain_id"]
        for tid in c["tids"]:
            if tid not in tfs:
                continue
            t = tfs[tid]
            for f in range(t["first_frame"], t["last_frame"] + 1):
                in_air[f].add(cid)
        for i in range(len(c["tids"]) - 1):
            from_tid, to_tid = c["tids"][i], c["tids"][i + 1]
            e = by_pair.get((from_tid, to_tid))
            if not e:
                continue
            hand = parse_hand_from_metadata(e["metadata"])
            from_t = tfs[from_tid]
            to_t = tfs[to_tid]
            catch_frame = from_t["last_frame"]
            throw_frame = to_t["first_frame"]
            if hand == "left":
                for f in [catch_frame, throw_frame]:
                    in_hand_l[f].add(cid)
            elif hand == "right":
                for f in [catch_frame, throw_frame]:
                    in_hand_r[f].add(cid)
            gap = to_t["first_frame"] - from_t["last_frame"]
            if 0 < gap <= 5 and hand in ("left", "right"):
                for f in range(catch_frame, throw_frame + 1):
                    if hand == "left":
                        in_hand_l[f].add(cid)
                    else:
                        in_hand_r[f].add(cid)

    out = {}
    all_frames = set(in_air.keys()) | set(in_hand_l.keys()) | set(in_hand_r.keys())
    for f in sorted(all_frames):
        n_air = len(in_air[f])
        n_l = len(in_hand_l[f])
        n_r = len(in_hand_r[f])
        all_chains = set()
        all_chains |= in_air[f]
        all_chains |= in_hand_l[f]
        all_chains |= in_hand_r[f]
        n_total = len(all_chains)
        if all_chains:
            avg_q = sum(chain_qualities.get(c, 0.0) for c in all_chains) / n_total
        else:
            avg_q = 0.0
        out[f] = {
            "frame": f,
            "n_in_air": n_air,
            "n_in_hand_left": n_l,
            "n_in_hand_right": n_r,
            "n_total_balls": n_total,
            "avg_chain_quality": round(avg_q, 3),
        }
    return out


def hand_alternation_metric(events_window):
    if not events_window:
        return {"same_hand_run": 0, "unique_hands": 0,
                "alternation_score": 0.0, "n_events": 0}
    hands = [e["hand"] for e in events_window]
    n = len(hands)
    same_hand_run = sum(1 for i in range(1, n) if hands[i] == hands[i - 1])
    unique_hands = len(set(h for h in hands if h and h != "unknown"))
    if n <= 1:
        alternation_score = 0.0
    else:
        alternation_score = 1.0 - (same_hand_run / (n - 1))
    return {
        "same_hand_run": same_hand_run,
        "unique_hands": unique_hands,
        "alternation_score": alternation_score,
        "n_events": n,
    }


def catch_rate(events_window):
    catches = [e for e in events_window if e["event"] == "CATCH"]
    if len(catches) < 2:
        return 0.0
    duration = float(int(catches[-1]["event_frame"]) -
                      int(catches[0]["event_frame"]))
    if duration <= 0:
        return 0.0
    return len(catches) * 30.0 / duration


def classify_3ball_v8(events_window, avg_quality,
                      n_in_hand_left, n_in_hand_right):
    """Original H12 v8 classifier (no time-density guard)."""
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
        return "MIXED_3+_UNCONFIRMED", avg_quality * 0.6, same_run, alt, rate
    if cascade_like and not fountain_like:
        return "CASCADE_3+", avg_quality, same_run, alt, rate
    if fountain_like and not cascade_like:
        return "FOUNTAIN_3+", avg_quality, same_run, alt, rate
    if cascade_like and fountain_like:
        if alt >= 0.5:
            return "CASCADE_3+", avg_quality, same_run, alt, rate
        return "FOUNTAIN_3+", avg_quality, same_run, alt, rate
    return "MIXED_3+", avg_quality, same_run, alt, rate


def classify_3ball_v9(events_window, avg_quality,
                      n_in_hand_left, n_in_hand_right,
                      time_span_thr=80):
    """H12 v9: time-density guard on top of H12 v8.

    If the K=4 events span > time_span_thr frames, demote to
    MIXED_3+_UNCONFIRMED with low confidence. This catches
    static-hold phases with sparse hand-handoffs.
    """
    metrics = hand_alternation_metric(events_window)
    rate = catch_rate(events_window)
    n = metrics["n_events"]
    same_run = metrics["same_hand_run"]
    alt = metrics["alternation_score"]

    # Time-density check
    if n >= 2:
        frames = [int(e["event_frame"]) for e in events_window]
        time_span = max(frames) - min(frames)
    else:
        time_span = 0

    if n < MIN_EVENTS_FOR_PATTERN:
        return "MIXED_3+_UNCONFIRMED", avg_quality * 0.6, same_run, alt, rate

    # v9 guard: if events are too sparse, demote to UNCONFIRMED
    if time_span > time_span_thr:
        return "MIXED_3+_UNCONFIRMED", avg_quality * 0.5, same_run, alt, rate

    cascade_like = (same_run <= CASCADE_MAX_SAME_HAND_RUN
                    and alt >= 0.5
                    and rate >= CASCADE_MIN_CATCH_RATE)
    fountain_like = (same_run >= n - 1 and alt < 0.3)
    if cascade_like and not fountain_like:
        return "CASCADE_3+", avg_quality, same_run, alt, rate
    if fountain_like and not cascade_like:
        return "FOUNTAIN_3+", avg_quality, same_run, alt, rate
    if cascade_like and fountain_like:
        if alt >= 0.5:
            return "CASCADE_3+", avg_quality, same_run, alt, rate
        return "FOUNTAIN_3+", avg_quality, same_run, alt, rate
    return "MIXED_3+", avg_quality, same_run, alt, rate


def classify_pattern(census_row, events_window, recent_events, use_v9=False, time_span_thr=80):
    n_total = census_row["n_total_balls"]
    n_air = census_row["n_in_air"]
    n_h_l = census_row["n_in_hand_left"]
    n_h_r = census_row["n_in_hand_right"]
    q = census_row["avg_chain_quality"]
    conf = max(q, 0.0)
    if n_total == 0:
        return "NO_BALL", 1.0, 0, 0.0, 0.0
    if n_total == 1:
        return "SINGLE_BALL", conf, 0, 0.0, 0.0
    if n_total == 2:
        if n_h_l == 1 and n_h_r == 1:
            return "TWO_BALL_HELD", conf, 0, 0.0, 0.0
        if n_h_l + n_h_r == 1:
            return "TWO_BALL_ONE_HAND", conf, 0, 0.0, 0.0
        return "TWO_BALL", conf, 0, 0.0, 0.0
    if n_total >= 3:
        if use_v9:
            return classify_3ball_v9(events_window, q, n_h_l, n_h_r, time_span_thr)
        return classify_3ball_v8(events_window, q, n_h_l, n_h_r)
    return "UNKNOWN", conf, 0, 0.0, 0.0


def detect_phase_boundaries(results):
    if not results:
        return []
    phases = []
    current = None
    start = None
    confs = []
    for r in results:
        if r["pattern"] != current:
            if current is not None:
                phases.append({
                    "start_frame": start,
                    "end_frame": r["frame"] - 1,
                    "pattern": current,
                    "n_frames": r["frame"] - start,
                    "avg_confidence": round(sum(confs) / len(confs), 3),
                })
            current = r["pattern"]
            start = r["frame"]
            confs = [r["confidence"]]
        else:
            confs.append(r["confidence"])
    if current is not None:
        phases.append({
            "start_frame": start,
            "end_frame": results[-1]["frame"],
            "pattern": current,
            "n_frames": results[-1]["frame"] - start + 1,
            "avg_confidence": round(sum(confs) / len(confs), 3),
        })
    return phases


def run_inference(stem, use_v9, time_span_thr):
    census = build_per_frame_census(stem)
    events = build_catch_throw_timeline(stem)
    events_sorted = sorted(events, key=lambda e: e["event_frame"])
    events_by_frame = defaultdict(list)
    for e in events:
        events_by_frame[int(e["event_frame"])].append(e)

    results = []
    pattern_counts = Counter()
    for f, c in sorted(census.items()):
        events_before = [e for e in events_sorted
                          if int(e["event_frame"]) <= f]
        events_window = events_before[-K_EVENTS:]
        recent = []
        for df in range(-RECENT_EVENT_FRAMES, RECENT_EVENT_FRAMES + 1):
            recent.extend(events_by_frame.get(f + df, []))
        pattern, conf, same_run, alt, rate = classify_pattern(
            c, events_window, recent, use_v9, time_span_thr)
        # Time-span for diagnostics
        if events_window:
            ws_frames = [int(e["event_frame"]) for e in events_window]
            time_span = max(ws_frames) - min(ws_frames) if len(ws_frames) >= 2 else 0
        else:
            time_span = 0
        results.append({
            "frame": f,
            "n_in_air": c["n_in_air"],
            "n_in_hand_left": c["n_in_hand_left"],
            "n_in_hand_right": c["n_in_hand_right"],
            "n_total": c["n_total_balls"],
            "avg_quality": c["avg_chain_quality"],
            "pattern": pattern,
            "confidence": round(conf, 3),
            "n_window_events": len(events_window),
            "n_recent_events": len(recent),
            "same_hand_run": same_run,
            "alternation_score": round(alt, 3),
            "catch_rate_hz": round(rate, 2),
            "time_span_K": time_span,
        })
        pattern_counts[pattern] += 1
    return results, pattern_counts, len(results)


def evaluate_on_h93(use_v9, time_span_thr):
    """Apply the H93 corrected GT and count TP/TN/FP/FN.

    H93 verdict: JUGGLING, STATIC_HOLD, OTHER_CROSSED_ARM
    H12 prediction classes (for phase-level accuracy):
      - ACTIVE = FOUNTAIN_3+, CASCADE_3+, MIXED_3+ (with high conf)
      - STATIC = MIXED_3+_UNCONFIRMED, TWO_BALL, SINGLE_BALL, NO_BALL, UNKNOWN
    We use a simple rule: JUGGLING = ACTIVE (FOUNTAIN_3+, CASCADE_3+, MIXED_3+)
    and STATIC_HOLD/OTHER = STATIC.
    """
    with open(H1_DATA / "h93_multi_rater_qa.json") as fh:
        h93 = json.load(fh)
    gt = h93["corrected_ground_truth"]

    # Run on both stems
    per_phase = []
    for stem in STEMS:
        results, pattern_counts, n_total_frames = run_inference(
            stem, use_v9, time_span_thr)
        results_by_frame = {int(r["frame"]): r for r in results}
        for phase_key, verdict in gt.items():
            if not phase_key.startswith(stem):
                continue
            parts = phase_key.rsplit("_", 2)
            s, e = int(parts[1]), int(parts[2])
            in_phase = [r for r in results
                        if s <= int(r["frame"]) <= e]
            if not in_phase:
                continue
            # Dominant pattern
            c = Counter(r["pattern"] for r in in_phase)
            dominant = c.most_common(1)[0][0]
            # Active vs static
            ACTIVE = ("FOUNTAIN_3+", "CASCADE_3+", "MIXED_3+", "FOUNTAIN_LOW_CONF")
            is_active = dominant in ACTIVE
            gt_active = verdict == "JUGGLING"
            per_phase.append({
                "phase_key": phase_key,
                "stem": stem,
                "verdict": verdict,
                "dominant": dominant,
                "is_active_pred": is_active,
                "is_active_gt": gt_active,
                "n_frames": len(in_phase),
            })
    # Compute TP/TN/FP/FN
    TP = sum(1 for p in per_phase if p["is_active_pred"] and p["is_active_gt"])
    TN = sum(1 for p in per_phase if not p["is_active_pred"] and not p["is_active_gt"])
    FP = sum(1 for p in per_phase if p["is_active_pred"] and not p["is_active_gt"])
    FN = sum(1 for p in per_phase if not p["is_active_pred"] and p["is_active_gt"])
    return per_phase, TP, TN, FP, FN


def main():
    print("=" * 72)
    print("H104 — H12 v9 continuous-density pattern classifier")
    print("=" * 72)

    # H93 GT evaluation
    print("\n=== H93 GT evaluation (21 phases) ===")
    print("\nBaseline (H12 v8, no time-span guard):")
    v8_per_phase, v8_tp, v8_tn, v8_fp, v8_fn = evaluate_on_h93(
        use_v9=False, time_span_thr=80)
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
        if tag in ("FP", "FN", "TN"):
            print(f"    [{tag}] {p['phase_key'][-50:]:<50} verdict={p['verdict']:<20} "
                  f"dominant={p['dominant']}")

    # Sensitivity grid for TIME_SPAN_THR
    print("\n=== Sensitivity grid: TIME_SPAN_THR ===")
    print(f"{'thr':>5}  {'TP':>3}  {'TN':>3}  {'FP':>3}  {'FN':>3}  "
          f"{'P':>6}  {'R':>6}  {'acc':>6}")
    grid = []
    for thr in [40, 50, 60, 70, 80, 90, 100, 120, 150, 200, 300, 500]:
        per_phase, tp, tn, fp, fn = evaluate_on_h93(use_v9=True, time_span_thr=thr)
        p = tp / max(1, tp + fp)
        r = tp / max(1, tp + fn)
        acc = (tp + tn) / max(1, tp + tn + fp + fn)
        grid.append({"thr": thr, "TP": tp, "TN": tn, "FP": fp, "FN": fn,
                     "P": round(p, 3), "R": round(r, 3), "acc": round(acc, 3)})
        print(f"{thr:>5}  {tp:>3}  {tn:>3}  {fp:>3}  {fn:>3}  "
              f"{p:>6.3f}  {r:>6.3f}  {acc:>6.3f}")

    # Save the per-phase data for the chosen operating point
    chosen_thr = 80
    chosen_per_phase, c_tp, c_tn, c_fp, c_fn = evaluate_on_h93(
        use_v9=True, time_span_thr=chosen_thr)
    out_csv = H1_DATA / "h104_per_phase.csv"
    with out_csv.open("w", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(chosen_per_phase[0].keys()))
        wr.writeheader()
        wr.writerows(chosen_per_phase)
    print(f"\nper-phase CSV (thr={chosen_thr}): {out_csv}")

    # Also save the per-frame pattern data
    for stem in STEMS:
        results, pattern_counts, n_total_frames = run_inference(
            stem, use_v9=True, time_span_thr=chosen_thr)
        out_csv = H1_DATA / f"pattern_inference_v9_{stem}.csv"
        with out_csv.open("w", newline="") as fh:
            wr = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
            wr.writeheader()
            wr.writerows(results)
        print(f"per-frame CSV ({stem}): {out_csv}")

    # Save summary
    summary = {
        "method": "H104: H12 v9 continuous-density pattern classifier with TIME_SPAN guard",
        "v8_baseline": {"TP": v8_tp, "TN": v8_tn, "FP": v8_fp, "FN": v8_fn,
                        "acc": round((v8_tp + v8_tn) / v8_total, 3)},
        "sens_grid": grid,
        "chosen_thr": chosen_thr,
        "v9_at_chosen_thr": {"TP": c_tp, "TN": c_tn, "FP": c_fp, "FN": c_fn,
                              "acc": round((c_tp + c_tn) / 21, 3)},
    }
    out = H1_DATA / "h104_summary.json"
    out.write_text(json.dumps(summary, indent=2))
    print(f"\nSummary: {out}")


if __name__ == "__main__":
    main()
