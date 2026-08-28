#!/usr/bin/env python3
"""H37 contact sheets - cross-reference visualization.

Shows the (L, R, A) state vs H12 v8 pattern label per frame,
with hand-events highlighted. Two-panel:
- Top: stacked area chart of (L, R, A) with H12 v8 pattern
  background color.
- Bottom: catch/throw events.
"""
from __future__ import annotations

import csv
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
SHEETS_DIR = H1_DIR / "contact_sheets_h37"

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

STEMS = [
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
]

# Color map for H12 v8 patterns
PATTERN_COLORS = {
    "NO_BALL": "white",
    "SINGLE_BALL": "lightyellow",
    "TWO_BALL": "lightcyan",
    "TWO_BALL_HELD": "lightblue",
    "TWO_BALL_ONE_HAND": "lightsalmon",
    "CASCADE_3+": "lightgreen",
    "FOUNTAIN_3+": "lightcoral",
    "MIXED_3+": "plum",
    "MIXED_3+_UNCONFIRMED": "lightgray",
    "UNKNOWN": "gray",
}


def load_crossref(stem: str) -> list[dict]:
    rows = []
    with (H1_DATA / f"h37_crossref_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["frame"] = int(r["frame"])
            r["L"] = int(r["L"])
            r["R"] = int(r["R"])
            r["A"] = int(r["A"])
            r["h12_n_total"] = int(r["h12_n_total"])
            r["h12_confidence"] = float(r["h12_confidence"])
            rows.append(r)
    return rows


def render_crossref(stem: str, rows: list[dict]) -> Path:
    if not rows:
        return None
    frames = [r["frame"] for r in rows]
    Ls = [r["L"] for r in rows]
    Rs = [r["R"] for r in rows]
    As = [r["A"] for r in rows]
    patterns = [r["h12_pattern"] for r in rows]
    n_total = max(r["h12_n_total"] for r in rows)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    fig.suptitle(f"H37 cross-reference: {stem} (H36 L/R/A + H12 v8 pattern)",
                 fontsize=12)

    # Top panel: stacked area + pattern background
    # Pattern background
    prev_pat = None
    pat_start = frames[0]
    for i, (f, p) in enumerate(zip(frames, patterns)):
        if p != prev_pat:
            if prev_pat is not None and i > 0:
                ax1.axvspan(pat_start, f, alpha=0.3,
                            color=PATTERN_COLORS.get(prev_pat, "white"),
                            zorder=0)
            pat_start = f
            prev_pat = p
    if prev_pat is not None:
        ax1.axvspan(pat_start, frames[-1], alpha=0.3,
                    color=PATTERN_COLORS.get(prev_pat, "white"),
                    zorder=0)

    # Stacked area
    ax1.fill_between(frames, 0, Ls, alpha=0.7, label="L (left hand)",
                     color="orange")
    ax1.fill_between(frames, Ls,
                      [L + R for L, R in zip(Ls, Rs)],
                      alpha=0.7, label="R (right hand)", color="blue")
    ax1.fill_between(frames,
                      [L + R for L, R in zip(Ls, Rs)],
                      [L + R + A for L, R, A in zip(Ls, Rs, As)],
                      alpha=0.5, label="A (in air)", color="gray")
    ax1.set_ylabel("ball count")
    ax1.set_ylim(0, n_total + 1)
    ax1.set_title("State timeline (L/R/A) with H12 v8 pattern background")
    ax1.grid(True, alpha=0.3)

    # Bottom panel: confidence timeline
    confs = [r["h12_confidence"] for r in rows]
    ax2.fill_between(frames, 0, confs, alpha=0.5, color="green",
                     label="H12 v8 confidence")
    ax2.set_ylim(0, 1.1)
    ax2.set_ylabel("confidence")
    ax2.set_xlabel("frame")
    ax2.set_title("H12 v8 confidence over time")
    ax2.legend(loc="upper right")
    ax2.grid(True, alpha=0.3)

    # Add pattern legend
    handles = [plt.Rectangle((0, 0), 1, 1, fc=color, alpha=0.3, label=pat)
                for pat, color in PATTERN_COLORS.items()
                if any(p == pat for p in patterns)]
    ax1.legend(handles=handles, loc="upper right", fontsize=7, ncol=2)

    plt.tight_layout()
    out = SHEETS_DIR / f"{stem}_crossref.png"
    plt.savefig(out, dpi=80)
    plt.close()
    return out


def main() -> None:
    SHEETS_DIR.mkdir(parents=True, exist_ok=True)
    for stem in STEMS:
        rows = load_crossref(stem)
        if not rows:
            print(f"  {stem}: no data, skipping")
            continue
        out = render_crossref(stem, rows)
        print(f"  {stem}: wrote {out}")


if __name__ == "__main__":
    main()
