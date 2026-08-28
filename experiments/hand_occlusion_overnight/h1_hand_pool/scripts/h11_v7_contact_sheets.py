#!/usr/bin/env python3
"""H11 v7 contact sheets — render V-reclassified edges in their chain context.

For each V-reclassified edge, show the full chain with the
V-reclassified hand-edge highlighted. This lets us visually
verify that the 4 identical V-reclassified chains (23->25,
30->33, 39->47, 51->52) are real single-ball catch-throws, and
that the 1 YouTube V-reclassified (27->28) is a tracklet break
(false positive).

Also renders the chain 30 quality-jump case (q8=0.427 ->
q9=0.727 from V-reclassifying 51->52) and chain 13 (q8=0.204
-> q9=0.504).
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_SCRIPTS = H1_DIR / "scripts"
H1_CS = H1_DIR / "contact_sheets_h11v7"
H1_CS.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(H1_SCRIPTS))
import h7_contact_sheets as h7cs  # type: ignore  # noqa: E402

# Per-tracklet colors keyed by tid
COLOR_LEFT = (0, 165, 255)    # orange (BGR)
COLOR_RIGHT = (255, 128, 0)   # blue
COLOR_DEFAULT = (200, 200, 200)


def load_h7v3pure_chains(stem: str) -> list[dict]:
    with (H1_DATA / f"h7v3pure_chains_{stem}.csv").open() as fh:
        out = []
        for r in csv.DictReader(fh):
            r["chain_id"] = int(r["chain_id"])
            r["n_tracklets"] = int(r["n_tracklets"])
            r["first_frame"] = int(r["first_frame"])
            r["last_frame"] = int(r["last_frame"])
            r["tids"] = [int(t) for t in r["tids"].split(",") if t]
            out.append(r)
    return out


def load_h7v3pure_edges(stem: str) -> list[dict]:
    with (H1_DATA / f"h7v3pure_admitted_edges_{stem}.csv").open() as fh:
        return list(csv.DictReader(fh))


def load_v7_events(stem: str) -> list[dict]:
    with (H1_DATA / f"chain_events_v7_{stem}.csv").open() as fh:
        return list(csv.DictReader(fh))


def load_h10_quality(stem: str, version: str = "v9") -> dict[int, float]:
    field = f"quality_{version}"
    with (H1_DATA / f"h10{version}_chain_quality_{stem}.csv").open() as fh:
        return {int(r["chain_id"]): float(r[field]) for r in csv.DictReader(fh)}


def main():
    stems = [
        "identical_balls_trick_000_018",
        "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
    ]
    for stem in stems:
        print(f"\n=== {stem} ===")
        chains = load_h7v3pure_chains(stem)
        edges = load_h7v3pure_edges(stem)
        v7_events = load_v7_events(stem)
        qv8 = load_h10_quality(stem, "v8")
        qv9 = load_h10_quality(stem, "v9")

        vrec_edges = [e for e in edges if e["edge_type"] == "V_RECLASSIFIED_HAND_TRANSITION"]
        print(f"V-reclassified edges: {len(vrec_edges)}")

        # Group V-reclassified edges by chain
        cid_to_vrec = {}
        for c in chains:
            for i in range(len(c["tids"]) - 1):
                a, b = c["tids"][i], c["tids"][i + 1]
                if any(e["from_tid"] == str(a) and e["to_tid"] == str(b) for e in vrec_edges):
                    cid_to_vrec.setdefault(c["chain_id"], set()).add((a, b))

        for cid, vrec_pairs in cid_to_vrec.items():
            chain = next(c for c in chains if c["chain_id"] == cid)
            tids = chain["tids"]
            q8 = qv8.get(cid, 0.0)
            q9 = qv9.get(cid, 0.0)

            # Frame selection: cover the chain's full span with
            # 6 frames evenly spaced, plus the 2 frames at the
            # V-reclassified edge boundary.
            first_f = chain["first_frame"]
            last_f = chain["last_frame"]
            frames = [first_f + i * (last_f - first_f) // 5 for i in range(6)]
            for a, b in vrec_pairs:
                # Find frames near a's end and b's start
                for r in csv.DictReader((H1_DATA / "tracklet_features.csv").open()):
                    if r["stem"] != stem:
                        continue
                    tid = int(r["tid"])
                    if tid == a:
                        frames.append(int(r["last_frame"]))
                    if tid == b:
                        frames.append(int(r["first_frame"]))
            frames = sorted(set(frames))[:8]

            # Color: orange for left-hand tids, blue for right-hand
            # (parsed from v7 events on this chain)
            tids_color = {tid: COLOR_DEFAULT for tid in tids}
            for ev in v7_events:
                if int(ev["chain_id"]) != cid:
                    continue
                if ev["hand"] in ("left", "right"):
                    c = COLOR_LEFT if ev["hand"] == "left" else COLOR_RIGHT
                    tids_color[int(ev["prev_tid"])] = c
                    tids_color[int(ev["tid"])] = c

            tracklets_to_show = [(tid, tids_color[tid], f"t{tid}") for tid in tids]
            label = f"chain{cid} v8={q8:.3f}->v9={q9:.3f}"
            subtitle = "V_RECLASSIFIED: " + ",".join(f"{a}->{b}" for a, b in vrec_pairs)
            out_path = H1_CS / f"chain{cid}_{stem}_h11v7.png"
            h7cs.render_contact_sheet(
                stem=stem, frames=frames, tracklets_to_show=tracklets_to_show,
                title=label, subtitle=subtitle, out_path=out_path,
                show_label_xy=True)
            print(f"  rendered chain {cid}: {out_path.name}")


if __name__ == "__main__":
    main()
