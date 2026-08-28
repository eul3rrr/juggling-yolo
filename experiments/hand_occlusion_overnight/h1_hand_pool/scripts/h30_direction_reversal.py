#!/usr/bin/env python3
"""H30: direction-reversal check on H17 strict V-shape positives.

The H28 visual QA found that 6/12 H20-KEPT adjacent candidates had a real
'throw' visible but no real 'catch' visible. This is the H17 V-shape
criterion's throw-bias: it admits candidates where the target leaves the
hand, but does not require the source to actually descend into the hand.

H30 hypothesis: requiring the SOURCE's last frame to be physically ABOVE
the V-apex (in image coords, smaller y), with a velocity vector pointing
downward (y increasing) and TOWARD the V-apex hand, will reject the
'throw-only' false positives WITHOUT rejecting real catch+throws.

Specifically: the source's velocity vector dotted with (apex - source_end)
should be positive (moving toward the apex). The target's velocity vector
dotted with (target_start - apex) should be positive (moving away from the
apex). If either is negative (moving AWAY from the apex), the candidate
fails.

Implementation:
- For each H17 strict positive, compute:
  - source_tail_velocity: mean velocity of last N source frames
  - target_head_velocity: mean velocity of first N target frames
  - apex: V-apex (point on trajectory closest to the hand)
  - check source_velocity . (apex - source_end) > 0 (catch direction)
  - check target_velocity . (target_start - apex) > 0 (throw direction)
- Reject if NEITHER direction is correct (no real catch AND no real throw)
- The H17 V-shape already requires at least one endpoint to be at the
  hand, so requiring direction will be a STRICTER filter

Smallest experiment: apply H30 to the 151 H17 strict positives, see how
many pass. Then check precision on a sample.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from h17_v_shape_recovery import (
    load_per_det_tracklet, load_wrist_frames, find_closest_wrist,
    H17_THRESHOLDS, v_shape_check, strict_filter, load_tracklet_features,
)

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"


# H30 thresholds (declared from physical geometry):
# - DIR_TOL: minimum dot product magnitude to be considered a real
#   catch/throw direction. 0.5 corresponds to ~26 degrees off-axis.
#   Physical geometry: a real catch approaches the hand at >45 degrees
#   (steep descent), so a generous 60-degree tolerance is fine.
H30_THRESHOLDS = {
    "TAIL_FRAMES": 3,  # use last 3 source frames for velocity
    "HEAD_FRAMES": 3,  # use first 3 target frames for velocity
    "DIR_TOL": 0.0,  # dot product must be > 0 (any positive = moving toward)
    # The H17 strict filter already requires min slope magnitude.
}


def compute_direction_metrics(edge, wrist_frames):
    """For an H17 edge, compute positional V-shape indicators.

    V1 STRATEGY (velocity-based, REJECTED): use source-tail and target-head
    velocities, check dot product with apex direction. This was rejected
    because real catch+throws often have short source/target tracklets
    where the velocity is dominated by noise.

    V2 STRATEGY (positional): for a real catch+throw, the SOURCE's last
    position is ABOVE the V-apex (in image coords, smaller y) and the
    TARGET's first position is ABOVE the V-apex ALSO (the ball just left
    the hand). So a "V-shape through the hand" has BOTH endpoints above
    the apex. This is what the H17 V-shape actually measures.

    H30 v2 hypothesis: rejecting candidates where the source and target
    are on OPPOSITE sides of the V-apex (one above, one below) is too
    strict — it would reject the H28 REAL case 13→15 (apex in target,
    source above).

    The simpler check: the source's last y is LESS THAN the apex y
    (source is above apex, meaning source is at higher real-world
    position = approaching the hand from above). This is consistent
    with both real catch+throws AND some false positives.

    Returns dict with positional indicators.
    """
    src_dets = load_per_det_tracklet(edge["stem"], edge["from_tid"])
    tgt_dets = load_per_det_tracklet(edge["stem"], edge["to_tid"])
    if len(src_dets) < 3 or len(tgt_dets) < 3:
        return None

    src_end_x, src_end_y = src_dets[-1][1], src_dets[-1][2]
    tgt_start_x, tgt_start_y = tgt_dets[0][1], tgt_dets[0][2]

    # Compute V-shape to get apex
    edge2 = dict(edge)
    edge2["gap"] = int(edge.get("gap", 1))
    v = v_shape_check(edge2, wrist_frames)
    if v is None:
        return None
    if v["apex"] is None:
        return None
    apex_x, apex_y, apex_fr = v["apex"]

    # Positional checks (v2 strategy)
    src_to_apex_dy = src_end_y - apex_y  # positive = source is below apex
    tgt_to_apex_dy = tgt_start_y - apex_y  # positive = target is below apex

    src_to_apex_dist = ((src_end_x - apex_x) ** 2 + (src_end_y - apex_y) ** 2) ** 0.5
    tgt_to_apex_dist = ((tgt_start_x - apex_x) ** 2 + (tgt_start_y - apex_y) ** 2) ** 0.5

    # Source above apex: src_end_y < apex_y (source is higher in real world = approaching from above)
    src_above = src_to_apex_dy < -20.0
    # Target above apex: tgt_start_y < apex_y (target is also higher, just left hand going up)
    tgt_above = tgt_to_apex_dy < -20.0
    # Both above: real V-shape
    both_above = src_above and tgt_above

    # Try: a stricter "trajectory makes sense" check
    # For a real catch+throw, the source's last y should be GREATER than
    # the source's first y (source has been descending) — i.e., the
    # source is approaching from above and continuing to descend.
    src_first_y = src_dets[0][2]
    src_descending = src_end_y > src_first_y + 10  # source y increased by >10 (descending in image)
    # And the target's first y should be LESS than the target's last y
    # (target is ascending immediately after throw)
    tgt_last_y = tgt_dets[-1][2]
    tgt_ascending = tgt_start_y < tgt_last_y - 10  # target y decreased by >10 (ascending in image)

    return {
        "src_end": (src_end_x, src_end_y),
        "tgt_start": (tgt_start_x, tgt_start_y),
        "apex": (apex_x, apex_y),
        "src_to_apex_dy": src_to_apex_dy,
        "tgt_to_apex_dy": tgt_to_apex_dy,
        "src_to_apex_dist": src_to_apex_dist,
        "tgt_to_apex_dist": tgt_to_apex_dist,
        "src_above": src_above,
        "tgt_above": tgt_above,
        "both_above": both_above,
        "src_descending": src_descending,
        "tgt_ascending": tgt_ascending,
        "catch_ok": src_above,
        "throw_ok": tgt_above,
    }


def main():
    # Load H17 strict positives
    strict = list(csv.DictReader(open(H1_DATA / "h17_strict_v_shape_positives.csv")))
    print(f"H17 strict positives: {len(strict)}")

    # Compute direction metrics for all
    features = load_tracklet_features()
    results = []
    for r in strict:
        edge = {
            "stem": r["stem"],
            "from_tid": int(r["from_tid"]),
            "to_tid": int(r["to_tid"]),
            "gap": int(r["gap"]),
            "from_frame": int(r.get("from_frame", 0)) if r.get("from_frame") else 0,
            "to_frame": int(r.get("to_frame", 0)) if r.get("to_frame") else 0,
        }
        # Get from_frame and to_frame from tracklet features
        sk = (edge["stem"], edge["from_tid"])
        tk = (edge["stem"], edge["to_tid"])
        if sk in features:
            edge["from_frame"] = features[sk]["last_frame"]
        if tk in features:
            edge["to_frame"] = features[tk]["first_frame"]
            # Recompute gap
            edge["gap"] = edge["to_frame"] - edge["from_frame"]

        wrist_frames = load_wrist_frames(edge["stem"])
        m = compute_direction_metrics(edge, wrist_frames)
        if m is None:
            results.append({
                **r,
                "src_to_apex_dy": "",
                "tgt_to_apex_dy": "",
                "src_to_apex_dist": "",
                "tgt_to_apex_dist": "",
                "src_above": "",
                "tgt_above": "",
                "both_above": "",
                "src_descending": "",
                "tgt_ascending": "",
                "h30_pass": "NO_DATA",
                "h30_catch_ok": "",
                "h30_throw_ok": "",
            })
        else:
            catch_ok = m["src_above"]
            throw_ok = m["tgt_above"]
            h30_pass = (catch_ok or throw_ok)
            results.append({
                **r,
                "src_to_apex_dy": f"{m['src_to_apex_dy']:.1f}",
                "tgt_to_apex_dy": f"{m['tgt_to_apex_dy']:.1f}",
                "src_to_apex_dist": f"{m['src_to_apex_dist']:.1f}",
                "tgt_to_apex_dist": f"{m['tgt_to_apex_dist']:.1f}",
                "src_above": "True" if m["src_above"] else "False",
                "tgt_above": "True" if m["tgt_above"] else "False",
                "both_above": "True" if m["both_above"] else "False",
                "src_descending": "True" if m["src_descending"] else "False",
                "tgt_ascending": "True" if m["tgt_ascending"] else "False",
                "h30_pass": "True" if h30_pass else "False",
                "h30_catch_ok": "True" if catch_ok else "False",
                "h30_throw_ok": "True" if throw_ok else "False",
            })

    # Summary
    n = len(results)
    n_pass = sum(1 for r in results if r["h30_pass"] == "True")
    n_fail = sum(1 for r in results if r["h30_pass"] == "False")
    n_nodata = sum(1 for r in results if r["h30_pass"] == "NO_DATA")
    n_catch = sum(1 for r in results if r.get("h30_catch_ok") == "True")
    n_throw = sum(1 for r in results if r.get("h30_throw_ok") == "True")
    print(f"\nH30 direction-reversal results:")
    print(f"  pass: {n_pass}  fail: {n_fail}  no_data: {n_nodata}")
    print(f"  catch_ok: {n_catch}  throw_ok: {n_throw}")

    # Per-source
    for kind in ["v4d_rejected", "e6c_not_in_h7v2", "adjacent"]:
        sub = [r for r in results if r["kind"] == kind]
        if not sub:
            continue
        p = sum(1 for r in sub if r["h30_pass"] == "True")
        c = sum(1 for r in sub if r.get("h30_catch_ok") == "True")
        t = sum(1 for r in sub if r.get("h30_throw_ok") == "True")
        print(f"  {kind}: {len(sub)} total, {p} pass, {c} catch_ok, {t} throw_ok")

    # Save
    out_path = H1_DATA / "h30_direction_metrics.csv"
    fieldnames = list(results[0].keys())
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        for r in results:
            w.writerow(r)
    print(f"\nWrote {out_path}")

    # Save summary
    summary = {
        "experiment": "H30",
        "hypothesis": "Direction-reversal check on H17 strict V-shape positives",
        "n_strict": n,
        "n_pass": n_pass,
        "n_fail": n_fail,
        "n_nodata": n_nodata,
        "n_catch_ok": n_catch,
        "n_throw_ok": n_throw,
        "pass_rate": n_pass / max(1, n - n_nodata),
        "thresholds": H30_THRESHOLDS,
    }
    with (H1_DATA / "h30_summary.json").open("w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"Wrote {H1_DATA / 'h30_summary.json'}")


if __name__ == "__main__":
    main()
