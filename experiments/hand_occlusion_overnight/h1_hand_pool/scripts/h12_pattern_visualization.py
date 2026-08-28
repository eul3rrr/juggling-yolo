#!/usr/bin/env python3
"""H12 visualization - per-frame pattern timeline chart."""
from __future__ import annotations

import csv
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS = H1_DIR / "contact_sheets_h11"
H1_CS.mkdir(parents=True, exist_ok=True)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PATTERN_COLORS = {
    "NO_BALL": "lightgray",
    "SINGLE_BALL": "lightblue",
    "TWO_BALL": "lightyellow",
    "TWO_BALL_HELD": "yellow",
    "TWO_BALL_ONE_HAND": "orange",
    "CASCADE_3+": "lightgreen",
    "FOUNTAIN_3+": "lightcoral",
    "UNKNOWN": "white",
}

PATTERN_ORDER = [
    "NO_BALL", "SINGLE_BALL", "TWO_BALL", "TWO_BALL_HELD",
    "TWO_BALL_ONE_HAND", "CASCADE_3+", "FOUNTAIN_3+", "UNKNOWN",
]
PATTERN_TO_Y = {p: i for i, p in enumerate(PATTERN_ORDER)}


def render_pattern_chart(stem: str, out_path: Path):
    rows = list(csv.DictReader(
        (H1_DATA / f"pattern_inference_{stem}.csv").open()))
    if not rows:
        return
    frames = [int(r["frame"]) for r in rows]
    ys = [PATTERN_TO_Y.get(r["pattern"], -1) for r in rows]
    colors = [PATTERN_COLORS.get(r["pattern"], "white") for r in rows]
    confidences = [float(r["confidence"]) for r in rows]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 6), sharex=True)
    # Top: pattern timeline as scatter
    for f, y, c in zip(frames, ys, colors):
        if y >= 0:
            ax1.scatter(f, y, c=c, s=4, alpha=0.7)
    ax1.set_yticks(range(len(PATTERN_ORDER)))
    ax1.set_yticklabels(PATTERN_ORDER, fontsize=8)
    ax1.set_ylabel("pattern")
    ax1.set_title(f"H12: per-frame juggling pattern inference — {stem}")
    ax1.set_ylim(-0.5, len(PATTERN_ORDER) - 0.5)
    ax1.grid(True, alpha=0.3)

    # Bottom: confidence
    ax2.plot(frames, confidences, color="tab:red", lw=0.5, alpha=0.7)
    ax2.set_ylabel("confidence")
    ax2.set_xlabel("frame")
    ax2.set_ylim(0, 1.05)
    ax2.axhline(0.5, color="gray", ls="--", alpha=0.5, label="min quality")
    ax2.legend(loc="upper right")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(out_path, dpi=80)
    plt.close()
    print(f"  rendered: {out_path.name}")


def main():
    print("=== Pattern charts ===")
    for stem, video in [
        ("identical_balls_trick_000_018", "videos/identical_balls_trick_000_018.mp4"),
        ("youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
         "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4"),
    ]:
        out = H1_CS / f"pattern_{stem}.png"
        try:
            render_pattern_chart(stem, out)
        except Exception as ex:
            print(f"  FAILED: {ex}")


if __name__ == "__main__":
    main()
