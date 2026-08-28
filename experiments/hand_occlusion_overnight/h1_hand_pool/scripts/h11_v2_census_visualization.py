#!/usr/bin/env python3
"""H11 v2 visual QA — render the per-frame census as a chart and
a few "identity merge" candidates as contact sheets.
"""
from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS = H1_DIR / "contact_sheets_h11"
H1_CS.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location(
    "h7cs", H1_DIR / "scripts" / "h7_contact_sheets.py")
assert spec is not None and spec.loader is not None
h7cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(h7cs)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def render_census_chart(stem: str, out_path: Path):
    """Plot the per-frame census (n_in_air, n_in_hand_left,
    n_in_hand_right) over time."""
    rows = list(csv.DictReader(
        (H1_DATA / f"per_frame_census_{stem}.csv").open()))
    if not rows:
        return
    frames = [int(r["frame"]) for r in rows]
    n_air = [int(r["n_in_air"]) for r in rows]
    n_h_l = [int(r["n_in_hand_left"]) for r in rows]
    n_h_r = [int(r["n_in_hand_right"]) for r in rows]
    n_total = [int(r["n_total_balls"]) for r in rows]
    q = [float(r["avg_chain_quality"]) for r in rows]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
    ax1.fill_between(frames, 0, n_air, label="in air", color="tab:blue", alpha=0.7)
    ax1.fill_between(frames, n_air, [a + h for a, h in zip(n_air, n_h_l)],
                     label="in hand (left)", color="tab:orange", alpha=0.7)
    ax1.fill_between(frames, [a + l for a, l in zip(n_air, n_h_l)],
                     [a + l + r for a, l, r in zip(n_air, n_h_l, n_h_r)],
                     label="in hand (right)", color="tab:green", alpha=0.7)
    ax1.plot(frames, n_total, color="black", lw=0.5, label="total")
    ax1.set_ylabel("ball count")
    ax1.set_title(f"H11 v2: per-frame juggling census — {stem}")
    ax1.legend(loc="upper right")
    ax1.set_ylim(bottom=0)
    ax1.grid(True, alpha=0.3)

    ax2.plot(frames, q, color="tab:red", lw=0.7)
    ax2.set_ylabel("avg chain quality")
    ax2.set_xlabel("frame")
    ax2.set_ylim(0, 1.05)
    ax2.axhline(0.7, color="gray", ls="--", alpha=0.5, label="CONFIDENT (0.7)")
    ax2.axhline(0.4, color="gray", ls=":", alpha=0.5, label="TRUSTABLE (0.4)")
    ax2.legend(loc="upper right")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path, dpi=80)
    plt.close()
    print(f"  rendered: {out_path.name}")


def main():
    print("=== Census charts ===")
    for stem, video in [
        ("identical_balls_trick_000_018", "videos/identical_balls_trick_000_018.mp4"),
        ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
         "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4"),
    ]:
        out = H1_CS / f"census_{stem}.png"
        try:
            render_census_chart(stem, out)
        except Exception as ex:
            print(f"  FAILED: {ex}")


if __name__ == "__main__":
    main()
