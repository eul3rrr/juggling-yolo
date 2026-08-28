#!/usr/bin/env python3
"""H12 v2 vs v3 comparison contact sheet."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from h12_v2_comparison import render_v1_v2_comparison, STEMS

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS = H1_DIR / "contact_sheets_h12v3"
H1_CS.mkdir(parents=True, exist_ok=True)


def main():
    # Only identical has v3 output
    for stem in ["identical_balls_trick_000_018"]:
        v2 = []
        with (H1_DATA / f"pattern_inference_v2_{stem}.csv").open() as fh:
            for r in csv.DictReader(fh):
                v2.append({
                    "frame": int(r["frame"]),
                    "pattern": r["pattern"],
                    "confidence": float(r["confidence"]),
                })
        v3 = []
        with (H1_DATA / f"pattern_inference_v3_{stem}.csv").open() as fh:
            for r in csv.DictReader(fh):
                v3.append({
                    "frame": int(r["frame"]),
                    "pattern": r["pattern"],
                    "confidence": float(r["confidence"]),
                })
        out_path = H1_CS / f"v2_v3_comparison_{stem}.png"
        # Use the same comparison renderer
        render_v1_v2_comparison(stem, v2, v3, out_path)
        # Rename labels in the rendered image - actually, just print
        print(f"  wrote: {out_path.name}")


if __name__ == "__main__":
    main()
