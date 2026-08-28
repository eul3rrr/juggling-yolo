#!/usr/bin/env python3
"""H58 v1 — visual verification of the 4 multi-tid CONFIDENT chains.

H58 (h58_intersection_analysis.py) reported that the 3 identical +
1 YouTube multi-tid CONFIDENT chains (intersection of H11 v7 and
H10 v11 v3 CONFIDENT criteria) form a clean single-ball subset with
consistent held-phase durations:
- identical chains 7, 19, 20: gap=11 frames (3-ball cascade signature)
- YouTube chain 6: gap=17 frames (5-ball shower signature)

This script renders 4 contact sheets (one per chain) showing the
chain's tracklet trajectory, hand-edge, and the held phase.

The 4 chains:
  - identical chain 7:  tids (11, 14), f=87-160, q11=0.704, gap=11
  - identical chain 19: tids (30, 33), f=399-472, q11=0.867, gap=11
  - identical chain 20: tids (31, 36), f=411-578, q11=0.908, gap=11
  - YouTube chain 6:    tids (10, 12), f=117-309, q11=0.841, gap=17

Each contact sheet shows 8 frames: 3 from t_prev, 2 near the catch
gap, 3 from t_curr. This lets the eye verify the catch+throw cycle.

Outputs:
  - contact_sheets_h58/chain<id>_<stem>_h58v1.png  (4 files)
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_SCRIPTS = H1_DIR / "scripts"
H1_CS = H1_DIR / "contact_sheets_h58"
H1_CS.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(H1_SCRIPTS))
import h7_contact_sheets as h7cs  # type: ignore  # noqa: E402

# Per-tracklet colors keyed by hand (where known)
COLOR_LEFT = (0, 165, 255)     # orange (BGR)
COLOR_RIGHT = (255, 128, 0)    # blue
COLOR_DEFAULT = (200, 200, 200)

# 4 multi-tid CONFIDENT chains (from h58_summary.json + h58_intersection CSVs)
H58_CHAINS = {
    "identical_balls_trick_000_018": [
        (7, [11, 14], 0.7036, "gap=11 (3-ball cascade signature)"),
        (19, [30, 33], 0.8669, "gap=11"),
        (20, [31, 36], 0.9076, "gap=11"),
    ],
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": [
        (6, [10, 12], 0.8406, "gap=17 (5-ball shower signature)"),
    ],
}


def load_h7v3plus3(stem: str) -> dict:
    """Load chain topology from h7v3plus3_chains_<stem>.csv."""
    out = {}
    with (H1_DATA / f"h7v3plus3_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            out[r["chain_id"]] = {
                "n_tracklets": int(r["n_tracklets"]),
                "first_frame": int(r["first_frame"]),
                "last_frame": int(r["last_frame"]),
                "tids": [int(t) for t in r["tids"].split(",") if t.strip()],
            }
    return out


def load_catch_throw_v8(stem: str) -> list[dict]:
    """Load H12 v8 catch/throw events."""
    with (H1_DATA / f"catch_throw_timeline_v8_{stem}.csv").open() as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    for stem, chains in H58_CHAINS.items():
        print(f"\n=== {stem} (H58 v1 contact sheets) ===")
        h7v3plus3 = load_h7v3plus3(stem)
        v8_events = load_catch_throw_v8(stem)

        for chain_id, tids, q11, gap_note in chains:
            chain = h7v3plus3[str(chain_id)]
            assert chain["tids"] == tids, f"tid mismatch: {chain['tids']} vs {tids}"
            tid_a, tid_b = tids[0], tids[1]

            # Load tracklet points
            pts_a = h7cs.load_tracklet_points(stem, tid_a)
            pts_b = h7cs.load_tracklet_points(stem, tid_b)
            if not pts_a or not pts_b:
                print(f"  chain {chain_id}: missing tracklet data, skipping")
                continue

            # Find catch+throw events on this chain
            chain_events = [e for e in v8_events if int(e["chain_id"]) == chain_id]
            catch_event = next((e for e in chain_events if e["event"] == "CATCH"), None)
            throw_event = next((e for e in chain_events if e["event"] == "THROW"), None)

            # Build 8 frames: 3 from t_a (early, mid, end), 2 from held phase, 3 from t_b
            end_a = pts_a[-1][0]   # last frame of tid_a
            start_b = pts_b[0][0]  # first frame of tid_b
            n_a = len(pts_a)
            n_b = len(pts_b)
            a_mid = pts_a[n_a // 2][0]
            a_early = pts_a[max(0, n_a // 4)][0]
            b_mid = pts_b[n_b // 2][0]
            b_late = pts_b[min(n_b - 1, 3 * n_b // 4)][0]
            # 2 frames in the held phase: 1 before CATCH event, 1 after THROW event
            catch_f = int(catch_event["event_frame"]) if catch_event else (end_a + start_b) // 2
            throw_f = int(throw_event["event_frame"]) if throw_event else (end_a + start_b) // 2

            frames = [a_early, a_mid, end_a,
                      catch_f, throw_f,
                      start_b, b_mid, b_late]
            frames = sorted(set(frames))[:8]

            # Hand color from v8 event
            ev_hand = catch_event.get("hand", "unknown") if catch_event else "unknown"
            if ev_hand == "left":
                color_a, color_b = COLOR_LEFT, COLOR_LEFT
            elif ev_hand == "right":
                color_a, color_b = COLOR_RIGHT, COLOR_RIGHT
            else:
                color_a, color_b = COLOR_DEFAULT, COLOR_DEFAULT

            tracklets_to_show = [
                (tid_a, color_a, f"t{tid_a}"),
                (tid_b, color_b, f"t{tid_b}"),
            ]
            title = f"chain{chain_id} H58v1 q11={q11:.3f} tids={tids} ({gap_note})"
            subtitle_parts = [
                f"f_a: {a_early}..{end_a} ({n_a} pts)",
                f"CATCH@{catch_f}",
                f"THROW@{throw_f}",
                f"f_b: {start_b}..{b_late} ({n_b} pts)",
            ]
            if ev_hand in ("left", "right"):
                subtitle_parts.append(f"hand={ev_hand}")
            if catch_event:
                subtitle_parts.append(f"edge_type={catch_event.get('edge_type', '?')}")
            subtitle = " | ".join(subtitle_parts)

            out_path = H1_CS / f"chain{chain_id}_{stem}_h58v1.png"
            h7cs.render_contact_sheet(
                stem=stem, frames=frames, tracklets_to_show=tracklets_to_show,
                title=title, subtitle=subtitle, out_path=out_path,
                show_label_xy=True,
            )
            print(f"  rendered chain {chain_id}: {out_path.name}")


if __name__ == "__main__":
    main()
