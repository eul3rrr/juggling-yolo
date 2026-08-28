#!/usr/bin/env python3
"""H39 - render contact sheets for the FOUNTAIN_3+ blocks rejected
by H39 post-filter. Visual QA: are these real FOUNTAIN or H12 v8
misclassifications?

Strategy:
  For each H39-rejected FOUNTAIN_3+ phase, render a contact sheet
  with 6 frames spanning the phase. Use vision_analyze to verify
  whether the phase is visually a FOUNTAIN (single-hand dominant)
  or something else (CASCADE / MIXED / no clear pattern).
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
CONTACT_DIR = H1_DIR / "contact_sheets_h39"
CONTACT_DIR.mkdir(parents=True, exist_ok=True)

# Source video paths (in the project workspace, not the worktree)
VIDEO_PATHS = {
    "identical_balls_trick_000_018": PROJECT
    / "videos" / "identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": PROJECT
    / "videos"
    / "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}


def load_crossref(stem: str) -> list[dict]:
    rows = []
    with (H1_DATA / f"h37_crossref_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            r["frame"] = int(r["frame"])
            r["L"] = int(r["L"])
            r["R"] = int(r["R"])
            r["A"] = int(r["A"])
            r["h12_confidence"] = float(r["h12_confidence"])
            rows.append(r)
    return rows


def find_fountain_phases(rows: list[dict], min_n: int = 5) -> list[tuple]:
    """Find FOUNTAIN_3+ phases (>= min_n frames) and return as
    (start_frame, end_frame, mean_conf, n_hand_occ_frames)."""
    phases = []
    cur_start = None
    cur_pattern = None
    for r in rows:
        p = r["h12_pattern"]
        if p == "FOUNTAIN_3+":
            if cur_start is None:
                cur_start = r["frame"]
                cur_pattern = p
        else:
            if cur_start is not None and cur_pattern == "FOUNTAIN_3+":
                n = r["frame"] - cur_start
                if n >= min_n:
                    confs = [
                        rr["h12_confidence"] for rr in rows
                        if cur_start <= rr["frame"] < r["frame"]
                        and rr["h12_pattern"] == "FOUNTAIN_3+"
                    ]
                    n_hand_occ = sum(
                        1 for rr in rows
                        if cur_start <= rr["frame"] < r["frame"]
                        and rr["h12_pattern"] == "FOUNTAIN_3+"
                        and (rr["L"] > 0 or rr["R"] > 0)
                    )
                    phases.append((
                        cur_start, r["frame"] - 1,
                        sum(confs) / len(confs),
                        n, n_hand_occ
                    ))
                cur_start = None
                cur_pattern = None
    if cur_start is not None and cur_pattern == "FOUNTAIN_3+":
        n = rows[-1]["frame"] - cur_start + 1
        if n >= min_n:
            confs = [
                rr["h12_confidence"] for rr in rows
                if cur_start <= rr["frame"] <= rows[-1]["frame"]
                and rr["h12_pattern"] == "FOUNTAIN_3+"
            ]
            n_hand_occ = sum(
                1 for rr in rows
                if cur_start <= rr["frame"] <= rows[-1]["frame"]
                and rr["h12_pattern"] == "FOUNTAIN_3+"
                and (rr["L"] > 0 or rr["R"] > 0)
            )
            phases.append((
                cur_start, rows[-1]["frame"],
                sum(confs) / len(confs),
                n, n_hand_occ
            ))
    return phases


def render_contact_sheet(stem: str, phases: list[tuple]) -> list[dict]:
    """Render a 6-frame contact sheet for each FOUNTAIN phase."""
    if not phases:
        return []
    video_path = VIDEO_PATHS.get(stem)
    if not video_path or not video_path.exists():
        print(f"  video not found: {video_path}")
        return []
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  cannot open: {video_path}")
        return []
    fps = cap.get(cv2.CAP_PROP_FPS)
    n_frames_video = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"  video: {video_path.name} {w}x{h} fps={fps} n={n_frames_video}")

    sheets = []
    for start, end, mean_conf, n, n_hand_occ in phases:
        # Pick 6 evenly-spaced frames in the phase
        n_pick = 6
        if n < n_pick:
            frames_to_pick = list(range(start, end + 1))
        else:
            step = n / n_pick
            frames_to_pick = [start + int(i * step) for i in range(n_pick)]
            if frames_to_pick[-1] != end:
                frames_to_pick[-1] = end

        # Read each frame
        panels = []
        for f_idx in frames_to_pick:
            cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
            ret, frame = cap.read()
            if not ret:
                continue
            # Add text annotation
            cv2.putText(
                frame,
                f"f={f_idx}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (255, 255, 0),
                2,
            )
            panels.append(frame)
        cap.release() if False else None  # Don't release mid-loop
        if len(panels) < 2:
            continue
        # Stitch panels vertically with separator lines
        sep_w = 4
        panel_h = panels[0].shape[0]
        panel_w = panels[0].shape[1]
        total_h = len(panels) * panel_h + (len(panels) - 1) * sep_w
        total_w = panel_w
        sheet = np.zeros((total_h, total_w, 3), dtype=np.uint8)
        y = 0
        for p in panels:
            sheet[y:y + panel_h, :, :] = p
            y += panel_h + sep_w
        # Draw separator lines
        for i in range(1, len(panels)):
            y_sep = i * (panel_h + sep_w) - sep_w // 2
            sheet[y_sep:y_sep + sep_w, :, :] = (255, 255, 255)

        out_path = CONTACT_DIR / (
            f"fountain_phase_{stem}_f{start}-{end}_n{n}_"
            f"handocc{n_hand_occ}.png"
        )
        cv2.imwrite(str(out_path), sheet)
        print(f"  wrote: {out_path.name} (n={n}, hand_occ={n_hand_occ}, "
              f"mean_conf={mean_conf:.3f})")
        sheets.append({
            "phase_start": start,
            "phase_end": end,
            "n_frames": n,
            "mean_conf": round(mean_conf, 3),
            "n_hand_occ_frames": n_hand_occ,
            "contact_sheet": str(out_path.relative_to(WORKTREE)),
            "frames_picked": frames_to_pick,
        })
    cap.release()
    return sheets


def main() -> None:
    summary = {"videos": {}}
    for stem in VIDEO_PATHS.keys():
        print(f"\n=== {stem} (H39 contact sheets) ===")
        rows = load_crossref(stem)
        if not rows:
            continue
        phases = find_fountain_phases(rows, min_n=10)  # Only >=10 frame phases
        print(f"  found {len(phases)} FOUNTAIN_3+ phases (>= 10 frames)")
        sheets = render_contact_sheet(stem, phases)
        summary["videos"][stem] = {
            "n_fountain_phases": len(phases),
            "sheets": sheets,
        }

    out = H1_DATA / "h39_contact_sheets.json"
    out.write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
