#!/usr/bin/env python3
"""H16 sensitivity grid — sweep H3 cluster thresholds on V-reclassified edges.

H16 v2 uses CLUSTER_MIN_FRAMES=5, CLUSTER_MIN_DETS=3, CLUSTER_RADIUS_PX=30,
GAP_PAD_FRAMES=5. These were inherited from H3 v3. Let me check if
the choice is robust for the V-reclassified case.

Visually confirmed verdicts on V-reclassified edges:
- identical 23->25: HAND-BORNE (NOT catch+throw)
- identical 30->33: REAL CATCH+THROW
- identical 39->47: HAND-BORNE (NOT catch+throw)
- identical 51->52: REAL CATCH+THROW
- youtube 27->28: FALSE POSITIVE (tracklet break)

Ideal H16: confirms BOTH REAL CATCH+THROWS, rejects ALL 3 others.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import h16_v_shape_h3_corroboration as h16  # type: ignore  # noqa: E402

# Visually-confirmed labels
LABELS = {
    "23->25": "HAND_BORNE",
    "30->33": "REAL",
    "39->47": "HAND_BORNE",
    "51->52": "REAL",
    "27->28": "FALSE_POS",
}

STEM_TO_VRECS = {
    "identical_balls_trick_000_018": ["23->25", "30->33", "39->47", "51->52"],
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": ["27->28"],
}


def main():
    # Pre-compute per-edge cluster stats for each (radius, min_frames, min_dets, pad) combo
    stems = list(STEM_TO_VRECS.keys())
    # Pre-load data once
    print("Loading data...")
    pre_data = {}
    for stem in stems:
        vrecs = h16.load_v_reclassified(stem)
        tracklets = h16.load_tracklet_features(stem)
        low_conf = h16.load_low_conf_dets(stem)
        wrists = h16.load_wrist_positions(stem)
        edge_data = []
        for vrec in vrecs:
            src, tgt = int(vrec["from_tid"]), int(vrec["to_tid"])
            hand = vrec["h14_hand"]
            t_src = tracklets.get(src, {})
            t_tgt = tracklets.get(tgt, {})
            gap_start = t_src.get("last_frame", 0)
            gap_end = t_tgt.get("first_frame", gap_start + 1)
            edge_low_conf = [d for d in low_conf if d["track_id"] not in {src, tgt}]
            # V-apex hand position
            wrist_xs, wrist_ys = [], []
            for fr in range(gap_start, gap_end + 1):
                if fr in wrists and hand in wrists[fr]:
                    wx, wy = wrists[fr][hand]
                    wrist_xs.append(wx)
                    wrist_ys.append(wy)
            if not wrist_xs:
                for fr in sorted(wrists.keys(), key=lambda f: abs(f - gap_start))[:5]:
                    if hand in wrists[fr]:
                        wrist_xs.append(wrists[fr][hand][0])
                        wrist_ys.append(wrists[fr][hand][1])
            target_xy = (sum(wrist_xs) / max(1, len(wrist_xs)),
                          sum(wrist_ys) / max(1, len(wrist_ys))) if wrist_xs else (0, 0)
            edge_data.append({
                "edge": f"{src}->{tgt}",
                "gap_start": gap_start,
                "gap_end": gap_end,
                "target_xy": target_xy,
                "edge_low_conf": edge_low_conf,
            })
        pre_data[stem] = edge_data

    # Sensitivity grid
    radii = [20, 30, 50, 75, 100]
    min_frames_vals = [3, 5, 7, 10]
    min_dets_vals = [2, 3, 5]
    pad_vals = [3, 5, 10]

    n_combos = len(radii) * len(min_frames_vals) * len(min_dets_vals) * len(pad_vals)
    print(f"Sweeping {n_combos} combinations...")

    grid = []
    for radius in radii:
        for min_frames in min_frames_vals:
            for min_dets in min_dets_vals:
                for pad in pad_vals:
                    n_confirmed = 0
                    n_correct = 0
                    n_real_caught = 0
                    n_real_total = 0
                    n_hand_borne_caught = 0
                    n_hand_borne_total = 0
                    n_fp_caught = 0
                    n_fp_total = 0
                    for stem, edge_data in pre_data.items():
                        for ed in edge_data:
                            cluster = h16.find_h3_cluster(
                                ed["edge_low_conf"], ed["target_xy"],
                                ed["gap_start"] - pad, ed["gap_end"] + pad)
                            # Override radius
                            # Recompute manually with the new radius
                            n_dets = 0
                            frames = set()
                            for d in ed["edge_low_conf"]:
                                if d["frame"] < ed["gap_start"] - pad:
                                    continue
                                if d["frame"] > ed["gap_end"] + pad:
                                    continue
                                dx = d["x"] - ed["target_xy"][0]
                                dy = d["y"] - ed["target_xy"][1]
                                if (dx * dx + dy * dy) ** 0.5 <= radius:
                                    n_dets += 1
                                    frames.add(d["frame"])
                            n_unique = len(frames)
                            is_confirmed = (n_unique >= min_frames
                                             and n_dets >= min_dets)
                            label = LABELS.get(ed["edge"], "?")
                            if is_confirmed:
                                n_confirmed += 1
                                if label == "REAL":
                                    n_real_caught += 1
                                elif label == "HAND_BORNE":
                                    n_hand_borne_caught += 1
                                elif label == "FALSE_POS":
                                    n_fp_caught += 1
                            if label == "REAL":
                                n_real_total += 1
                            elif label == "HAND_BORNE":
                                n_hand_borne_total += 1
                            elif label == "FALSE_POS":
                                n_fp_total += 1
                    # Compute precision/recall on the REAL class
                    if n_confirmed > 0:
                        precision = n_real_caught / n_confirmed
                    else:
                        precision = 0.0
                    if n_real_total > 0:
                        recall = n_real_caught / n_real_total
                    else:
                        recall = 0.0
                    f1 = (2 * precision * recall / (precision + recall)
                          if (precision + recall) > 0 else 0.0)
                    grid.append({
                        "radius": radius,
                        "min_frames": min_frames,
                        "min_dets": min_dets,
                        "pad": pad,
                        "n_confirmed": n_confirmed,
                        "n_real_caught": n_real_caught,
                        "n_hand_borne_caught": n_hand_borne_caught,
                        "n_fp_caught": n_fp_caught,
                        "n_real_total": n_real_total,
                        "n_hand_borne_total": n_hand_borne_total,
                        "n_fp_total": n_fp_total,
                        "precision": precision,
                        "recall": recall,
                        "f1": f1,
                    })

    # Sort by f1, then by recall
    grid.sort(key=lambda r: (-r["f1"], -r["recall"], r["n_confirmed"]))
    print(f"\nTop 10 settings by F1 (REAL = catch+throw, HAND_BORNE = not catch+throw, FALSE_POS = tracklet break):\n")
    print(f"{'rank':<5} {'r':<4} {'mf':<4} {'md':<4} {'pad':<4} {'conf':<5} {'real':<6} {'hb':<5} {'fp':<5} {'P':<6} {'R':<6} {'F1':<6}")
    for i, g in enumerate(grid[:10]):
        print(f"{i+1:<5} {g['radius']:<4} {g['min_frames']:<4} {g['min_dets']:<4} {g['pad']:<4} "
              f"{g['n_confirmed']:<5} {g['n_real_caught']}/{g['n_real_total']:<4} {g['n_hand_borne_caught']}/{g['n_hand_borne_total']:<4} "
              f"{g['n_fp_caught']}/{g['n_fp_total']:<4} {g['precision']:<6.2f} {g['recall']:<6.2f} {g['f1']:<6.2f}")

    out = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/data/h16_sensitivity.json")
    out.write_text(json.dumps(grid, indent=2))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
