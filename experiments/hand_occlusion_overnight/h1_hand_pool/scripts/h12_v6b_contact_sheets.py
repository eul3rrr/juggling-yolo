#!/usr/bin/env python3
"""H12 v6b visual QA contact sheet for the late phase."""
from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
CONTACT_DIR = H1_DIR / "contact_sheets_h12v6b"
VIDEO_DIR = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos")

STEM = "identical_balls_trick_000_018"
VIDEO_NAME = "identical_balls_trick_000_018.mp4"


def render_grid(frames: list, out_path: Path,
                 v2_pat: dict, v5_pat: dict, v6b_pat: dict,
                 v2_conf: dict, v5_conf: dict,
                 title: str):
    CONTACT_DIR.mkdir(parents=True, exist_ok=True)
    tmpdir = out_path.parent / "_tmpframes"
    tmpdir.mkdir(parents=True, exist_ok=True)
    for f in frames:
        out_f = tmpdir / f"f_{f:05d}.png"
        if not out_f.exists():
            subprocess.run([
                "ffmpeg", "-y", "-loglevel", "error",
                "-i", str(VIDEO_DIR / VIDEO_NAME),
                "-vf", f"select=eq(n\\,{f})",
                "-vframes", "1", str(out_f)
            ], check=True)
    from PIL import Image, ImageDraw, ImageFont
    n_rows = 2
    n_cols = 3
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
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
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
        label = (f"f={f}\n"
                 f"v2={v2_pat.get(f, '?')} ({v2_conf.get(f, 0):.2f})\n"
                 f"v5={v5_pat.get(f, '?')} ({v5_conf.get(f, 0):.2f})\n"
                 f"v6b={v6b_pat.get(f, '?')}")
        draw.text((x, y + sh + 2), label, fill="black", font=font)
    grid.save(out_path)
    for f in tmpdir.iterdir():
        f.unlink()
    tmpdir.rmdir()
    print(f"  wrote: {out_path.relative_to(WORKTREE)}")


def main():
    v2_pat = {}
    v2_conf = {}
    with (H1_DATA / f"pattern_inference_v2_{STEM}.csv").open() as fh:
        for r in csv.DictReader(fh):
            v2_pat[int(r["frame"])] = r["pattern"]
            v2_conf[int(r["frame"])] = float(r["confidence"])
    v5_pat = {}
    v5_conf = {}
    with (H1_DATA / f"pattern_inference_v5_{STEM}.csv").open() as fh:
        for r in csv.DictReader(fh):
            v5_pat[int(r["frame"])] = r["pattern"]
            v5_conf[int(r["frame"])] = float(r["confidence"])
    v6b_pat = {}
    with (H1_DATA / f"pattern_inference_v6b_{STEM}.csv").open() as fh:
        for r in csv.DictReader(fh):
            v6b_pat[int(r["frame"])] = r["pattern_v6b"]

    # Sample late phase (f=890-1050) frames where v6b says CASCADE_3+
    # (v5 won, v2 was wrong)
    print(f"=== Late phase f=890-1050 v6b=CASCADE_3+ (v5 won) ===")
    v5_won_cascade = [f for f in sorted(v6b_pat)
                       if 890 <= f <= 1050
                       and v6b_pat[f] == "CASCADE_3+"]
    print(f"  Found {len(v5_won_cascade)} v6b=CASCADE_3+ frames in f=890-1050")
    if len(v5_won_cascade) >= 6:
        idxs = [int(i * (len(v5_won_cascade) - 1) / 5) for i in range(6)]
        sample = [v5_won_cascade[i] for i in idxs]
        render_grid(
            sample, CONTACT_DIR / "late_phase_v6b_cascade.png",
            v2_pat, v5_pat, v6b_pat, v2_conf, v5_conf,
            "H12 v6b late phase: v2=FOUNTAIN (low conf), v5=CASCADE (high conf), v6b=CASCADE"
        )

    # Compare v2, v6, v6b on f=890-1050
    print(f"\n=== Late phase f=890-1050 v6b=MIXED_3+_ENSEMBLE (genuine uncertainty) ===")
    mixed_ensemble = [f for f in sorted(v6b_pat)
                       if 890 <= f <= 1050
                       and v6b_pat[f] == "MIXED_3+_ENSEMBLE"]
    print(f"  Found {len(mixed_ensemble)} v6b=MIXED_3+_ENSEMBLE frames in f=890-1050")
    if len(mixed_ensemble) >= 6:
        idxs = [int(i * (len(mixed_ensemble) - 1) / 5) for i in range(6)]
        sample = [mixed_ensemble[i] for i in idxs]
        render_grid(
            sample, CONTACT_DIR / "late_phase_v6b_ensemble.png",
            v2_pat, v5_pat, v6b_pat, v2_conf, v5_conf,
            "H12 v6b late phase: genuine ensemble disagreement (close conf)"
        )

    # Standard 6-frame late phase comparison
    f890_1050 = [890, 920, 950, 980, 1010, 1040]
    render_grid(
        f890_1050, CONTACT_DIR / "late_phase_890_1050_v6b.png",
        v2_pat, v5_pat, v6b_pat, v2_conf, v5_conf,
        "H12 v6b late phase f=890-1050 (v2 wrong, v5 right, v6b takes v5)"
    )


if __name__ == "__main__":
    main()
