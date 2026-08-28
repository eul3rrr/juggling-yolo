#!/usr/bin/env python3
"""H32 — render real-video-frame contact sheets for visual QA of
per-chain pattern verdicts.

For each selected h7v3plus2 chain, render a compact contact sheet:
- 6 representative video frames spanning the chain
- Ball positions overlaid
- Hand circles (L=orange, R=blue) at the wrist position
- Hand sequence and pattern verdict header

This uses cv2 to read actual video frames (NOT abstract ball positions)
so the visual QA is meaningful.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
JUGGLING_TRACKER_VIDEOS = Path(
    "/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos"
)
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_CS = H1_DIR / "contact_sheets_h32"
H1_CS.mkdir(exist_ok=True)

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


REACH_RADIUS = 108

# Hand colors (BGR for cv2): L=orange, R=blue
HAND_COLOR = {"left": (0, 165, 255), "right": (255, 100, 50)}


def load_metrics(stem: str) -> list[dict]:
    with (H1_DATA / f"h32_chain_metrics_{stem}.csv").open() as fh:
        return list(csv.DictReader(fh))


def load_tracklet_features(stem: str) -> dict[int, dict]:
    out = {}
    with (H1_DATA / "tracklet_features.csv").open() as fh:
        for r in csv.DictReader(fh):
            if r["stem"] != stem:
                continue
            r["tid"] = int(r["tid"])
            r["first_frame"] = int(r["first_frame"])
            r["last_frame"] = int(r["last_frame"])
            r["n_pts"] = int(r["n_pts"])
            r["first_x"] = float(r["first_x"])
            r["first_y"] = float(r["first_y"])
            r["last_x"] = float(r["last_x"])
            r["last_y"] = float(r["last_y"])
            r["end_dist"] = float(r["end_dist"]) if r["end_dist"] else None
            r["end_slope"] = float(r["end_slope"]) if r["end_slope"] else None
            r["start_dist"] = float(r["start_dist"]) if r["start_dist"] else None
            r["start_slope"] = float(r["start_slope"]) if r["start_slope"] else None
            out[r["tid"]] = r
    return out


def load_chain(stem: str, chain_id: int) -> dict | None:
    with (H1_DATA / f"h7v3plus2_chains_{stem}.csv").open() as fh:
        for r in csv.DictReader(fh):
            if int(r["chain_id"]) == chain_id:
                r["chain_id"] = int(r["chain_id"])
                r["n_tracklets"] = int(r["n_tracklets"])
                r["first_frame"] = int(r["first_frame"])
                r["last_frame"] = int(r["last_frame"])
                r["tids"] = [int(t) for t in r["tids"].split(",") if t]
                return r
    return None


def find_video(stem: str) -> Path | None:
    for p in [WORKTREE / "videos" / f"{stem}.mp4",
              JUGGLING_TRACKER_VIDEOS / f"{stem}.mp4"]:
        if p.exists():
            return p
    return None


def read_frame(video_path: Path, frame_idx: int) -> np.ndarray | None:
    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
    ok, frame = cap.read()
    cap.release()
    return frame if ok else None


def render_chain_sheet(metric: dict, chain: dict, tid_meta: dict,
                       video_path: Path, out_path: Path) -> None:
    """Render a 2x3 grid of video frames spanning the chain with ball
    position overlays."""
    f0 = chain["first_frame"]
    f1 = chain["last_frame"]
    frames = [f0,
              f0 + (f1 - f0) // 5,
              f0 + 2 * (f1 - f0) // 5,
              f0 + 3 * (f1 - f0) // 5,
              f0 + 4 * (f1 - f0) // 5,
              f1]

    # Read all frames first (cache so we don't open the video 6 times)
    frame_imgs = []
    for f in frames:
        img = read_frame(video_path, f)
        if img is None:
            # blank
            img = np.zeros((720, 1280, 3), dtype=np.uint8)
        frame_imgs.append(img)

    H, W = frame_imgs[0].shape[:2]
    panel_w, panel_h = W // 2, H // 3
    # 3 rows of 2 cols + 40px header
    sheet_h = 40 + 3 * panel_h
    sheet = np.zeros((sheet_h, W, 3), dtype=np.uint8)

    # Header background
    cv2.rectangle(sheet, (0, 0), (W, 40), (20, 20, 20), -1)
    header = (f"H32 chain {chain['chain_id']} | {metric['pattern_verdict']} | "
              f"hands={metric['hand_sequence']} | "
              f"n_tids={chain['n_tracklets']} | "
              f"f={f0}-{f1} | "
              f"h10q={metric['h10v10_quality']} | "
              f"alt_rate={metric['alternation_rate']}")
    cv2.putText(sheet, header, (10, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                (255, 255, 255), 1, cv2.LINE_AA)
    cv2.putText(sheet,
                f"catch_rate={metric['catch_rate_hz']}Hz "
                f"ball_est={metric['physical_ball_estimate']}",
                (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                (200, 200, 200), 1, cv2.LINE_AA)

    # Place frames in 3x2 grid
    for idx, (f, img) in enumerate(zip(frames, frame_imgs)):
        col = idx % 2
        row = idx // 2
        x0, y0 = col * panel_w, 40 + row * panel_h
        # Resize if necessary
        if img.shape[1] != panel_w or img.shape[0] != panel_h:
            img = cv2.resize(img, (panel_w, panel_h))
        sheet[y0:y0 + panel_h, x0:x0 + panel_w] = img
        # Frame label
        cv2.rectangle(sheet, (x0, y0), (x0 + 80, y0 + 22), (0, 0, 0), -1)
        cv2.putText(sheet, f"f={f}", (x0 + 4, y0 + 16),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
                    cv2.LINE_AA)

        # Overlay ball positions
        for tid in chain["tids"]:
            meta = tid_meta.get(tid)
            if not meta:
                continue
            t0, t1 = meta["first_frame"], meta["last_frame"]
            if not (t0 <= f <= t1):
                continue
            if t1 == t0:
                bx, by = meta["first_x"], meta["first_y"]
            else:
                r = (f - t0) / (t1 - t0)
                r = max(0.0, min(1.0, r))
                bx = meta["first_x"] + r * (meta["last_x"] - meta["first_x"])
                by = meta["first_y"] + r * (meta["last_y"] - meta["first_y"])
            # Color: orange for left-side tids (image), blue for right-side
            # Use end_side to determine color
            if meta.get("end_side") == "left":
                color = (0, 165, 255)  # BGR orange
            else:
                color = (255, 100, 50)  # BGR blue
            sx = int(x0 + bx / W * panel_w)
            sy = int(y0 + by / H * panel_h)
            cv2.circle(sheet, (sx, sy), 12, color, 2)
            cv2.putText(sheet, f"t{tid}", (sx + 14, sy + 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
                        cv2.LINE_AA)

    cv2.imwrite(str(out_path), sheet)


def main() -> None:
    stems = {
        "identical_balls_trick_000_018": "identical",
        "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090": "youtube",
    }
    summary = []
    for stem, label in stems.items():
        video = find_video(stem)
        if not video:
            print(f"[{stem}] no video found, skipping")
            continue
        metrics = load_metrics(stem)
        tid_meta = load_tracklet_features(stem)

        # Select chains: pick the largest CASCADE, the largest FOUNTAIN,
        # the largest MIXED/UNKNOWN, and a SINGLE_CATCH (if any)
        by_verdict = {}
        for m in metrics:
            if int(m["n_tracklets"]) < 2:
                continue
            v = m["pattern_verdict"]
            if v == "NO_CATCH":
                continue
            by_verdict.setdefault(v, []).append(m)

        for verdict in ("CASCADE_LIKE", "FOUNTAIN_LIKE", "MIXED", "UNKNOWN",
                        "SINGLE_CATCH"):
            if verdict not in by_verdict:
                continue
            # Pick the longest chain (most tids) for this verdict
            chosen = max(by_verdict[verdict], key=lambda m: int(m["n_tracklets"]))
            cid = int(chosen["chain_id"])
            chain = load_chain(stem, cid)
            if not chain:
                continue
            out_path = H1_CS / f"{label}_chain{cid}_{verdict}_H32.png"
            try:
                render_chain_sheet(chosen, chain, tid_meta, video, out_path)
                print(f"  rendered {out_path.name} "
                      f"(chain {cid}, {chosen['n_tracklets']} tids, "
                      f"hand_seq={chosen['hand_sequence']}, "
                      f"h10q={chosen['h10v10_quality']})")
                summary.append({
                    "stem": stem,
                    "label": label,
                    "chain_id": cid,
                    "verdict": verdict,
                    "n_tids": int(chosen["n_tracklets"]),
                    "hand_sequence": chosen["hand_sequence"],
                    "h10q": chosen["h10v10_quality"],
                    "png": out_path.name,
                })
            except Exception as ex:
                print(f"  ERROR {out_path.name}: {ex}")

    out_json = H1_DATA / "h32_contact_sheet_summary.json"
    with out_json.open("w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nwrote {out_json.name}: {len(summary)} sheets")


if __name__ == "__main__":
    main()
