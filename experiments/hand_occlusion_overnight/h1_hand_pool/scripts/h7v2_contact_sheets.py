#!/usr/bin/env python3
"""H7v2 contact sheets — visually verify a small set of
reclassified BALLISTIC→HAND_TRANSITION edges.

Selects 6 reclassified edges across both videos: 3 from identical,
3 from YouTube. For each, render a 6-frame contact sheet showing
the source tracklet's last 3 frames + the target tracklet's first
3 frames, with hand-wrist overlay.

Output: h1_hand_pool/contact_sheets_h7v2/<edge_label>.png
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS = H1_DIR / "contact_sheets_h7v2"

# Insert local script directory for shared renderer
sys.path.insert(0, str(H1_DIR / "scripts"))
from h1_contact_sheets_v3 import (  # noqa: E402
    load_tracklets, load_wrist_frames, draw_link_sheet,
    VIDEOS_DIR,
)


def load_reclassified(stem: str) -> list[dict]:
    rows = []
    with (H1_DATA / f"h7v2_reclassified_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            r["gap"] = int(r["gap"])
            rows.append(r)
    return rows


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


def make_link_dict(reclass_row, tf, stem, video):
    """Convert a reclassified edge into a dict compatible with
    draw_link_sheet(). The hand-transitions need from_frame/to_frame
    of the actual tracklet endpoints."""
    from_t = tf[reclass_row["from_tid"]]
    to_t = tf[reclass_row["to_tid"]]
    return {
        "stem": stem,
        "video": video,
        "from_tid": reclass_row["from_tid"],
        "to_tid": reclass_row["to_tid"],
        "from_frame": from_t["last_frame"] - 2,  # mid-source
        "to_frame": to_t["first_frame"] + 2,      # mid-target
        "from_dist": from_t.get("end_dist") or 999.0,
        "to_dist": to_t.get("start_dist") or 999.0,
        "from_slope": from_t.get("end_slope") or 0.0,
        "to_slope": to_t.get("start_slope") or 0.0,
        "kind": "RECLASSIFIED",
        "tok_age_frames": 0,
        "identity_ambiguous": False,
        "hand": reclass_row["reason"].split("side=")[-1] if "side=" in reclass_row["reason"] else "unknown",
    }


def main():
    H1_CS.mkdir(parents=True, exist_ok=True)
    stems = {
        "identical_balls_trick_000_018": "videos/identical_balls_trick_000_018.mp4",
        "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
            "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
    }
    tracks_cache, wrists_cache = {}, {}
    rendered = 0
    target_count = {
        "identical_balls_trick_000_018": 4,
        "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": 4,
    }
    for stem, video in stems.items():
        if stem not in tracks_cache:
            tracks_cache[stem] = load_tracklets(stem)
            wrists_cache[stem] = load_wrist_frames(stem)
        tf = load_tracklet_features(stem)
        reclass = load_reclassified(stem)
        # Pick a small diverse subset
        # - First 2 (start of pattern)
        # - Then 2 from middle of pattern
        # - Then 1 long-gap edge
        # - Then 1 short-gap edge
        chosen = []
        seen_gaps = set()
        for r in reclass:
            gap_bucket = (r["gap"] // 5) * 5
            if gap_bucket not in seen_gaps and len(chosen) < target_count[stem]:
                chosen.append(r)
                seen_gaps.add(gap_bucket)
        # Pad with first remaining if still under target
        i = 0
        while len(chosen) < target_count[stem] and i < len(reclass):
            if reclass[i] not in chosen:
                chosen.append(reclass[i])
            i += 1

        for r in chosen:
            link_dict = make_link_dict(r, tf, stem, video)
            out_name = (f"{stem[:8]}_{r['from_tid']}_to_{r['to_tid']}_"
                        f"gap{r['gap']}.png")
            out_path = H1_CS / out_name
            ok = draw_link_sheet(
                stem, video, link_dict,
                tracks_cache[stem], wrists_cache[stem],
                out_path, f_focus=link_dict["to_frame"],
            )
            if ok:
                rendered += 1
                reason_short = r["reason"][:50]
                print(f"  rendered {out_name}  ({reason_short})")
    print(f"Rendered {rendered} H7v2 reclassified contact sheets to {H1_CS}")


if __name__ == "__main__":
    main()
