#!/usr/bin/env python3
"""H36 contact sheets - render per-frame state evolution timeline.

H36 produces a per-frame (L, R, A) state timeline. We render
this as a contact sheet that shows the state for representative
time windows, along with the hand-events that caused state
transitions.

Output:
  contact_sheets_h36/{stem}_state_evolution.png  - per-video timeline
"""
from __future__ import annotations

import csv
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
SHEETS_DIR = H1_DIR / "contact_sheets_h36"

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]


def load_per_frame(stem: str) -> list[dict]:
    rows = []
    with (H1_DATA / f"h36_per_frame_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["frame"] = int(r["frame"])
            r["L"] = int(r["L"])
            r["R"] = int(r["R"])
            r["A"] = int(r["A"])
            rows.append(r)
    return rows


def load_timeline(stem: str) -> list[dict]:
    rows = []
    with (H1_DATA / f"h36_timeline_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["frame"] = int(r["frame"])
            r["L"] = int(r["L"])
            r["R"] = int(r["R"])
            r["A"] = int(r["A"])
            rows.append(r)
    return rows


def render_state_evolution(stem: str, per_frame: list[dict],
                            timeline: list[dict]) -> Path:
    """Render a 2-panel figure: state over time + hand-event markers."""
    if not per_frame:
        return None
    frames = [r["frame"] for r in per_frame]
    Ls = [r["L"] for r in per_frame]
    Rs = [r["R"] for r in per_frame]
    As = [r["A"] for r in per_frame]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    fig.suptitle(f"H36 state evolution: {stem}", fontsize=12)

    # Top panel: state over time as stacked area
    ax1.fill_between(frames, 0, Ls, alpha=0.5, label="L (left hand)",
                     color="orange")
    ax1.fill_between(frames, Ls,
                      [L + R for L, R in zip(Ls, Rs)],
                      alpha=0.5, label="R (right hand)", color="blue")
    ax1.fill_between(frames,
                      [L + R for L, R in zip(Ls, Rs)],
                      [L + R + A for L, R, A in zip(Ls, Rs, As)],
                      alpha=0.4, label="A (in air)", color="gray")
    ax1.set_ylabel("ball count")
    ax1.set_ylim(0, max(Ls) + max(Rs) + max(As) + 0.5)
    ax1.legend(loc="upper right")
    ax1.set_title("State timeline (L/R/A)")
    ax1.grid(True, alpha=0.3)

    # Bottom panel: hand-events as scatter (L/R for catch/throw)
    catches_L = [r["frame"] for r in timeline
                 if r["event_type"] == "CATCH" and r["hand"] == "left"]
    throws_L = [r["frame"] for r in timeline
                if r["event_type"] == "THROW" and r["hand"] == "left"]
    catches_R = [r["frame"] for r in timeline
                 if r["event_type"] == "CATCH" and r["hand"] == "right"]
    throws_R = [r["frame"] for r in timeline
                if r["event_type"] == "THROW" and r["hand"] == "right"]
    ambig = [r["frame"] for r in timeline
             if r["event_type"].startswith("AMBIG")]

    ax2.scatter(catches_L, [1] * len(catches_L), marker="^", s=80,
                color="orange", label="L catch", zorder=3)
    ax2.scatter(throws_L, [0] * len(throws_L), marker="v", s=80,
                color="orange", label="L throw", zorder=3)
    ax2.scatter(catches_R, [1] * len(catches_R), marker="^", s=80,
                color="blue", label="R catch", zorder=3)
    ax2.scatter(throws_R, [0] * len(throws_R), marker="v", s=80,
                color="blue", label="R throw", zorder=3)
    if ambig:
        ax2.scatter(ambig, [0.5] * len(ambig), marker="x", s=60,
                    color="red", label="ambiguous", zorder=3)

    ax2.set_yticks([0, 0.5, 1])
    ax2.set_yticklabels(["throw", "ambig", "catch"])
    ax2.set_ylim(-0.5, 1.5)
    ax2.set_xlabel("frame")
    ax2.set_title("Hand-events")
    ax2.legend(loc="upper right", fontsize=8, ncol=3)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    out = SHEETS_DIR / f"{stem}_state_evolution.png"
    plt.savefig(out, dpi=80)
    plt.close()
    return out


def main() -> None:
    SHEETS_DIR.mkdir(parents=True, exist_ok=True)
    for stem in STEMS:
        per_frame = load_per_frame(stem)
        timeline = load_timeline(stem)
        if not per_frame or not timeline:
            print(f"  {stem}: no data, skipping")
            continue
        out = render_state_evolution(stem, per_frame, timeline)
        print(f"  {stem}: wrote {out}")


if __name__ == "__main__":
    main()
