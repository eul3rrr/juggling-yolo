#!/usr/bin/env python3
"""H45 contact sheets — visually verify chains with 3+ flight times.

Selects 3 chains (2 identical + 1 YouTube) with n_flights >= 3.
For each cross-tracklet flight, render a 6-frame contact sheet
focused on the THROW frame (start of the flight).

Output: h1_hand_pool/contact_sheets_h45/<stem>_chain<N>_<idx>.png
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS = H1_DIR / "contact_sheets_h45"
H1_CS.mkdir(exist_ok=True)

# Insert local script directory for shared renderer
sys.path.insert(0, str(H1_DIR / "scripts"))
from h1_contact_sheets_v3 import (  # noqa: E402
    load_tracklets, load_wrist_frames, draw_link_sheet,
    VIDEOS_DIR,
)


def load_flights(stem: str) -> list[dict]:
    flights = []
    with (H1_DATA / "h45_siteswap_flights.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            flights.append(r)
    return flights


def load_tracklet_features(stem: str) -> dict[int, dict]:
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            def _f(s):
                if not s:
                    return None
                try:
                    return float(s)
                except ValueError:
                    return None
            out[int(r["tid"])] = {
                "tid": int(r["tid"]),
                "first_frame": int(r["first_frame"]),
                "last_frame": int(r["last_frame"]),
                "n_pts": int(r["n_pts"]),
                "end_dist": _f(r["end_dist"]),
                "start_dist": _f(r["start_dist"]),
                "end_slope": _f(r["end_slope"]),
                "start_slope": _f(r["start_slope"]),
            }
    return out


def make_link_dict(flight, tf, stem):
    """Convert a flight row into a dict compatible with draw_link_sheet()."""
    from_tid = int(flight["throw_tid"])
    to_tid = int(flight["next_catch_tid"])
    if from_tid not in tf or to_tid not in tf:
        return None
    from_t = tf[from_tid]
    to_t = tf[to_tid]
    # Parse hand from reclassify_reason if present
    hand = "left" if from_tid % 2 == 0 else "right"
    return {
        "stem": stem,
        "from_tid": from_tid,
        "to_tid": to_tid,
        "from_frame": from_t["last_frame"] - 2,
        "to_frame": to_t["first_frame"] + 2,
        "from_dist": from_t.get("end_dist") or 999.0,
        "to_dist": to_t.get("start_dist") or 999.0,
        "from_slope": from_t.get("end_slope") or 0.0,
        "to_slope": to_t.get("start_slope") or 0.0,
        "hand": hand,
        "kind": "FLIGHT_TIME",
        "identity_ambiguous": False,
        "tok_age_frames": 0,
        "from_t": from_t,
        "to_t": to_t,
    }


def main() -> None:
    STEMS = [
        "identical_balls_trick_000_018",
        "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
    ]
    target_chains = {
        "identical_balls_trick_000_018": [22, 29],
        "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": [9],
    }

    tracks_cache = {}
    wrists_cache = {}
    rendered = 0
    for stem in STEMS:
        tracks_cache[stem] = load_tracklets(stem)
        wrists_cache[stem] = load_wrist_frames(stem)
        tf = load_tracklet_features(stem)
        flights = load_flights(stem)
        # Group flights by chain
        by_chain = defaultdict(list)
        for f in flights:
            by_chain[int(f["chain_id"])].append(f)
        video = VIDEOS_DIR / f"{stem}.mp4"
        for cid in target_chains.get(stem, []):
            chain_flights = sorted(by_chain.get(cid, []), key=lambda x: int(x["throw_frame"]))
            if not chain_flights:
                continue
            print(f"\n=== {stem} chain {cid} ({len(chain_flights)} flights) ===")
            for flight in chain_flights:
                print(f"  t{flight['throw_tid']}@{flight['throw_frame']} -> "
                      f"t{flight['next_catch_tid']}@{flight['next_catch_frame']} "
                      f"(flight={flight['flight_time']})")
            for idx, flight in enumerate(chain_flights):
                link = make_link_dict(flight, tf, stem)
                if link is None:
                    continue
                out_name = (f"{stem[:20]}_chain{cid}_{idx}_t{flight['throw_tid']}"
                            f"_to_t{flight['next_catch_tid']}_ft{flight['flight_time']}.png")
                out_path = H1_CS / out_name
                ok = draw_link_sheet(
                    stem, str(video), link,
                    tracks_cache[stem], wrists_cache[stem],
                    out_path, f_focus=int(flight["throw_frame"]),
                )
                if ok:
                    rendered += 1
                    print(f"  rendered: {out_name}")
                else:
                    print(f"  FAILED to render: {out_name}")
    print(f"\nRendered {rendered} H45 contact sheets to {H1_CS}")


if __name__ == "__main__":
    main()
