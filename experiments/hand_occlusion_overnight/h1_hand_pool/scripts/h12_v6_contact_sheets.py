#!/usr/bin/env python3
"""H12 v6 visual QA contact sheet.

For the late phase (f=890-1050 on identical) which v2 misclassifies
as FOUNTAIN, show frames where v2 says FOUNTAIN but v5 says CASCADE
(so v6 reports MIXED_3+_ENSEMBLE).
"""
from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
CONTACT_DIR = H1_DIR / "contact_sheets_h12v6"
# Videos live in the juggling-tracker workspace, not the worktree
VIDEO_DIR = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos")

STEMS = {
    "identical_balls_trick_000_018": "identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}


def render_grid(stem: str, frames: list, out_path: Path,
                 v2_pat: dict, v5_pat: dict, v6_pat: dict,
                 title: str):
    """Render a 2x3 grid of frames with pattern labels."""
    CONTACT_DIR.mkdir(parents=True, exist_ok=True)
    # Use ffmpeg to extract frames
    tmpdir = out_path.parent / "_tmpframes"
    tmpdir.mkdir(parents=True, exist_ok=True)
    for f in frames:
        out_f = tmpdir / f"f_{f:05d}.png"
        if not out_f.exists():
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(VIDEO_DIR / STEMS[stem]),
                "-vf", f"select=eq(n\\,{f})",
                "-vframes", "1", str(out_f)
            ], check=True)
    # Build the contact sheet with PIL
    from PIL import Image, ImageDraw, ImageFont
    n_rows = 2
    n_cols = 3
    if len(frames) < n_rows * n_cols:
        n_rows = 1
        n_cols = min(len(frames), 3)
    sample = Image.open(tmpdir / f"f_{frames[0]:05d}.png")
    w, h = sample.size
    sw, sh = w // 4, h // 4
    margin = 8
    label_h = 30
    grid_w = n_cols * sw + (n_cols + 1) * margin
    grid_h = n_rows * (sh + label_h) + (n_rows + 1) * margin + 40
    grid = Image.new("RGB", (grid_w, grid_h), "white")
    draw = ImageDraw.Draw(grid)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
        title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
    except OSError:
        font = ImageFont.load_default()
        title_font = font
    draw.text((margin, 8), title, fill="black", font=title_font)
    for i, f in enumerate(frames[:n_rows * n_cols]):
        r = i // n_cols
        c = i % n_cols
        x = margin + c * (sw + margin)
        y = 40 + margin + r * (sh + label_h + margin)
        img = Image.open(tmpdir / f"f_{f:05d}.png").resize((sw, sh))
        grid.paste(img, (x, y))
        label = (f"f={f} v2={v2_pat.get(f, '?')} v5={v5_pat.get(f, '?')} "
                 f"v6={v6_pat.get(f, '?')}")
        draw.text((x, y + sh + 4), label, fill="black", font=font)
    grid.save(out_path)
    # Cleanup tmp
    for f in tmpdir.iterdir():
        f.unlink()
    tmpdir.rmdir()
    print(f"  wrote: {out_path.relative_to(WORKTREE)}")


def main():
    # Late phase on identical
    stem = "identical_balls_trick_000_018"
    # Load pattern data
    v2_pat = {}
    with (H1_DATA / f"pattern_inference_v2_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            v2_pat[int(r["frame"])] = r["pattern"]
    v5_pat = {}
    with (H1_DATA / f"pattern_inference_v5_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            v5_pat[int(r["frame"])] = r["pattern"]
    v6_pat = {}
    with (H1_DATA / f"pattern_inference_v6_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            v6_pat[int(r["frame"])] = r["pattern_v6"]

    # Sample late-phase frames where v2 says FOUNTAIN and v5 says CASCADE
    # (these become MIXED_3+_ENSEMBLE in v6)
    print(f"=== Late phase MIXED_3+_ENSEMBLE contact sheet (f=890-1050) ===")
    mixed_frames = [f for f in sorted(v6_pat)
                     if 890 <= f <= 1050
                     and v6_pat[f] == "MIXED_3+_ENSEMBLE"]
    print(f"  Found {len(mixed_frames)} MIXED_3+_ENSEMBLE frames in f=890-1050")
    # Sample 6 evenly spaced
    if len(mixed_frames) > 6:
        idxs = [int(i * (len(mixed_frames) - 1) / 5) for i in range(6)]
        sample_frames = [mixed_frames[i] for i in idxs]
    else:
        sample_frames = mixed_frames[:6]
    print(f"  Sample frames: {sample_frames}")
    render_grid(
        stem, sample_frames,
        CONTACT_DIR / "late_phase_ensemble_mixed.png",
        v2_pat, v5_pat, v6_pat,
        "H12 v6 late phase: v2=FOUNTAIN, v5=CASCADE, v6=MIXED_3+_ENSEMBLE"
    )

    # Also: f=890-936 frames (the v4v5 contact sheet frames)
    f890_936 = [890, 920, 950, 980, 1010, 1040]
    render_grid(
        stem, f890_936,
        CONTACT_DIR / "late_phase_890_1050.png",
        v2_pat, v5_pat, v6_pat,
        "H12 v6 late phase f=890-1050 (where v2 said FOUNTAIN wrong)"
    )

    # Early phase where v2 said CASCADE
    early_cascade = [f for f in sorted(v6_pat)
                      if 0 <= f <= 200
                      and v6_pat[f] == "CASCADE_3+"][:6]
    print(f"\n=== Early phase CASCADE_3+ contact sheet (f=0-200) ===")
    print(f"  Sample frames: {early_cascade}")
    if len(early_cascade) >= 6:
        render_grid(
            stem, early_cascade[:6],
            CONTACT_DIR / "early_phase_cascade.png",
            v2_pat, v5_pat, v6_pat,
            "H12 v6 early phase: CASCADE_3+ (v2 + v5 agree)"
        )

    # Sample frames where v2 was confident CASCADE and v5 was FOUNTAIN (or vice versa)
    # (genuine disagreement)
    print(f"\n=== Disagreement (v2 FOUNTAIN + v5 CASCADE) frames ===")
    disagree_frames = [f for f in sorted(v6_pat)
                        if v6_pat[f] == "MIXED_3+_ENSEMBLE"][:6]
    render_grid(
        stem, disagree_frames,
        CONTACT_DIR / "all_disagree_ensemble.png",
        v2_pat, v5_pat, v6_pat,
        "H12 v6: representative MIXED_3+_ENSEMBLE frames (v2/v5 disagree)"
    )


if __name__ == "__main__":
    main()
