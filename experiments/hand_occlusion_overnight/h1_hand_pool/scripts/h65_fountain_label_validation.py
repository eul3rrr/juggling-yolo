#!/usr/bin/env python3
"""H65 - H12 v8 FOUNTAIN_3+ label validation at scale, post-H64 zone.

H39 (2026-08-28) found that H12 v8's FOUNTAIN_3+ classification was
only 30% accurate on 9 substantial identical phases + 2 YouTube
phases (visual QA verdicts: 3 FOUNTAIN, 4 MIXED, 1 CASCADE, 2 OTHER).

H64 (2026-08-28) found that the identical 3-ball video has a sharp
CASCADE->FOUNTAIN transition at f=240: pre-f=240 is CASCADE-like
(0.25 same-hand rate), post-f=240 is FOUNTAIN-like (0.73 same-hand
rate). This means the H39 visual-QA sample was dominated by the
post-f=240 phase, where FOUNTAIN_3+ is more expected.

H63 (2026-08-28) characterized the YouTube 5-ball video as a
CASCADE-SHOWER mix, with 2 SHOWER bursts (f=420-510, f=769-825).
The H12 v8 FOUNTAIN_3+ classification on YouTube may correspond
to the SHOWER bursts.

H65: a more rigorous visual QA on the H50-filtered pattern set,
restricted to substantial FOUNTAIN_3+ phases (>= 20 frames, the
H60 standard). The H50 filter is the latest validated event-log
filter, so this is the most current data.

Method:
  1. Load H50-filtered pattern phases.
  2. Extract substantial FOUNTAIN_3+ phases (>= 20 frames).
  3. For each phase, render a contact sheet with 4 evenly-spaced
     frames (fewer than H39's 6, more focused).
  4. Use vision_analyze (CLI) to label each phase as
     FOUNTAIN, CASCADE, MIXED, or OTHER.
  5. Compute H12 v8 FOUNTAIN_3+ accuracy on this sample.
  6. Compare to H39's 30% finding.

Output:
  - contact_sheets_h65/  -- 4-frame contact sheets
  - data/h65_summary.json
  - data/h65_visual_qa_verdicts.csv (recorded manually)
  - reports/h65_report.md
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import cv2
import numpy as np

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
PROJECT = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
CONTACT_DIR = H1_DIR / "contact_sheets_h65"
CONTACT_DIR.mkdir(parents=True, exist_ok=True)

# Source video paths (in the project workspace, not the worktree)
VIDEO_PATHS = {
    "identical_balls_trick_000_018": PROJECT
    / "videos" / "identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": PROJECT
    / "videos" / "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

# H64 finding: post-f=240 is the FOUNTAIN-rich phase on identical
POST_F_240_THRESHOLD = 240
# H63 finding: YouTube SHOWER bursts are at f=420-510 and f=769-825
YOUTUBE_SHOWER_BURSTS = [(420, 510), (769, 825)]


def load_fountain_phases(stem: str) -> list[tuple]:
    """Load substantial FOUNTAIN_3+ phases (>= 20 frames) from H50-filtered
    pattern_phases CSV.

    Returns list of (start, end, n, mean_conf, avg_quality) tuples.
    """
    path = H1_DATA / f"pattern_phases_h50_{stem}.csv"
    out = []
    for row in csv.DictReader(open(path)):
        if row["pattern"] == "FOUNTAIN_3+":
            n = int(row["n_frames"])
            if n >= 20:
                out.append((
                    int(row["start_frame"]),
                    int(row["end_frame"]),
                    n,
                    float(row["avg_confidence"]),
                ))
    return sorted(out, key=lambda x: x[0])


def render_phase_contact_sheet(stem: str, start: int, end: int,
                                n: int, conf: float) -> dict | None:
    """Render a 4-frame contact sheet for a FOUNTAIN_3+ phase."""
    video_path = VIDEO_PATHS.get(stem)
    if not video_path or not video_path.exists():
        print(f"  video not found: {video_path}")
        return None
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  cannot open: {video_path}")
        return None
    fps = cap.get(cv2.CAP_PROP_FPS)
    n_total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"  video: {video_path.name} {w}x{h} fps={fps} n={n_total}")

    # Pick 4 evenly-spaced frames in the phase (fewer than H39's 6
    # for more focused QA)
    n_pick = 4
    if n < n_pick:
        frames_to_pick = list(range(start, end + 1))
    else:
        step = n / n_pick
        frames_to_pick = [start + int(i * step) for i in range(n_pick)]
        if frames_to_pick[-1] != end:
            frames_to_pick[-1] = end

    panels = []
    for f_idx in frames_to_pick:
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
        ret, frame = cap.read()
        if not ret:
            continue
        # Annotate frame number
        cv2.putText(
            frame,
            f"f={f_idx}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 0),
            2,
        )
        panels.append(frame)
    if len(panels) < 2:
        cap.release()
        return None
    # Stitch panels vertically with separator lines
    sep_w = 4
    panel_h = panels[0].shape[0]
    panel_w = panels[0].shape[1]
    total_h = len(panels) * panel_h + (len(panels) - 1) * sep_w
    sheet = np.zeros((total_h, panel_w, 3), dtype=np.uint8)
    y = 0
    for p in panels:
        sheet[y:y + panel_h, :, :] = p
        y += panel_h + sep_w
    for i in range(1, len(panels)):
        y_sep = i * (panel_h + sep_w) - sep_w // 2
        sheet[y_sep:y_sep + sep_w, :, :] = (255, 255, 255)
    out_path = CONTACT_DIR / (
        f"fountain_phase_{stem}_f{start}-{end}_n{n}.png"
    )
    cv2.imwrite(str(out_path), sheet)
    print(f"  wrote: {out_path.name} (n={n}, mean_conf={conf:.3f})")
    cap.release()
    return {
        "phase_start": start,
        "phase_end": end,
        "n_frames": n,
        "mean_confidence": round(conf, 3),
        "contact_sheet": str(out_path.relative_to(WORKTREE)),
        "frames_picked": frames_to_pick,
    }


def classify_phase(stem: str, start: int, end: int) -> str:
    """Classify a phase by its position relative to known boundaries.

    This is a structural hint, not a ground-truth label. The vision
    QA verdict is the authoritative label.
    """
    if stem.startswith("identical"):
        if start >= POST_F_240_THRESHOLD:
            return "POST_F240_FOUNTAIN_ZONE"
        return "PRE_F240_CASCADE_ZONE"
    elif stem.startswith("youtube"):
        for s, e in YOUTUBE_SHOWER_BURSTS:
            # Allow 50-frame buffer
            if abs(start - s) < 50 or abs(end - e) < 50:
                return f"NEAR_SHOWER_BURST_{s}-{e}"
        return "OUTSIDE_KNOWN_SHOWER"
    return "UNKNOWN"


def main() -> None:
    summary = {"videos": {}}
    all_phases = []

    for stem in VIDEO_PATHS.keys():
        print(f"\n=== {stem} (H65 substantial FOUNTAIN_3+ phases) ===")
        phases = load_fountain_phases(stem)
        print(f"  found {len(phases)} substantial FOUNTAIN_3+ phases (>= 20 frames)")
        video_phases = []
        for start, end, n, conf in phases:
            zone = classify_phase(stem, start, end)
            print(f"  phase f={start}-{end}, n={n}, conf={conf:.3f}, zone={zone}")
            sheet = render_phase_contact_sheet(stem, start, end, n, conf)
            if sheet is None:
                continue
            sheet["zone"] = zone
            video_phases.append(sheet)
        summary["videos"][stem] = {
            "n_substantial_fountain_phases": len(phases),
            "sheets": video_phases,
        }
        all_phases.extend([
            {**s, "video": stem} for s in video_phases
        ])

    summary["methodology"] = {
        "filter": "H50 (10-frame flight-time filter on H12 v8 event log)",
        "min_phase_frames": 20,
        "n_frames_per_sheet": 4,
        "zone_classification": {
            "identical": "post-f=240 is FOUNTAIN-rich (H64)",
            "youtube": "SHOWER bursts at f=420-510, f=769-825 (H63)",
        },
        "comparison_to_h39": {
            "h39_n_phases_qa": 11,
            "h39_visual_precision": "30% (3/10 confirmed FOUNTAIN)",
            "h39_video": "H37 crossref, 6-frame contact sheets",
            "h65_differences": [
                "H50-filtered pattern data (latest validated)",
                "Min phase 20 frames (vs H39's 10 frames)",
                "4-frame sheets (vs H39's 6-frame)",
                "Explicit zone classification (POST_F240_FOUNTAIN_ZONE etc.)",
            ],
        },
    }
    summary["n_total_phases"] = len(all_phases)
    summary["phases_by_zone"] = {
        z: sum(1 for p in all_phases if p.get("zone") == z)
        for z in set(p.get("zone", "UNKNOWN") for p in all_phases)
    }

    out = H1_DATA / "h65_summary.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")
    print(f"\n=== Summary ===")
    print(f"Total substantial FOUNTAIN_3+ phases (H50-filtered): {len(all_phases)}")
    for z, n in summary["phases_by_zone"].items():
        print(f"  {z}: {n} phases")


if __name__ == "__main__":
    main()
