#!/usr/bin/env python3
"""H1 v4 — contact sheets for surviving v4 links.

v4d (throw=7, soft catch-context, MIN_FROM_SLOPE=2.5, reach filter)
emits 10 identical + 1 youtube links. This script renders contact
sheets for all of them so the visual verifier can confirm.

Output: h1_hand_pool/contact_sheets_v4/
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

# Reuse the v3 contact sheet renderer
sys.path.insert(0, str(Path(__file__).resolve().parent))
from h1_contact_sheets_v3 import (  # noqa: E402
    load_tracklets, load_wrist_frames, draw_link_sheet,
    VIDEOS_DIR, H1_DATA,
)

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_CS_V4 = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "contact_sheets_v4"


def load_links(label: str) -> list[dict]:
    suf = label.replace(" ", "_").replace("(", "").replace(")", "").replace(",", "")
    suf = suf.replace("__", "_").strip("_")
    path = H1_DATA / f"hand_links_v4_{suf}.csv"
    rows = []
    with path.open() as fh:
        for r in csv.DictReader(fh):
            r["from_tid"] = int(r["from_tid"])
            r["to_tid"] = int(r["to_tid"])
            r["from_frame"] = int(r["from_frame"])
            r["to_frame"] = int(r["to_frame"])
            r["from_dist"] = float(r["from_dist"])
            r["to_dist"] = float(r["to_dist"])
            r["from_slope"] = float(r["from_slope"])
            r["to_slope"] = float(r["to_slope"])
            r["tok_age_frames"] = int(r["tok_age_frames"])
            r["identity_ambiguous"] = (r["identity_ambiguous"] == "True")
            rows.append(r)
    return rows


def main():
    H1_CS_V4.mkdir(parents=True, exist_ok=True)
    label = "v4d_throw7_full"
    links = load_links(label)
    tracks_cache, wrists_cache = {}, {}
    rendered = 0
    for i, l in enumerate(links, 1):
        stem = l["stem"]
        if stem not in tracks_cache:
            tracks_cache[stem] = load_tracklets(stem)
            wrists_cache[stem] = load_wrist_frames(stem)
        out_name = (f"{label}_link_{i}_{l['kind']}_"
                    f"{l['from_tid']}_to_{l['to_tid']}_f{l['to_frame']}.png")
        out_path = H1_CS_V4 / out_name
        ok = draw_link_sheet(
            stem, l["video"], l,
            tracks_cache[stem], wrists_cache[stem],
            out_path, f_focus=l["to_frame"],
        )
        if ok:
            rendered += 1
            print(f"  rendered {out_name}")
    print(f"Rendered {rendered} v4 surviving link contact sheets to {H1_CS_V4}")


if __name__ == "__main__":
    main()
