"""Render the autonomous AIRBORNE + HAND reconstruction.

Produces:
  * outputs/reconstruction/identical_balls_trick_000_018_AUTONOMOUS.mp4
  * outputs/reconstruction/identical_balls_trick_000_018_BASELINE_airborne.mp4
  * outputs/reconstruction/identical_balls_trick_000_018_HUMAN_REFERENCE.mp4

The autonomous path uses the identity-repair output:
    FINAL_chain_mapping.csv, FINAL_accepted_edges.csv
    (which may contain HAND edges in addition to AIRBORNE)

The baseline path uses the existing accepted-stitches CSV:
    *_accepted_stitches.csv
    (which contains only AIRBORNE edges)

The human-reference path uses the canonical human labels CSV
ONLY when --human-reference is passed.  It is NOT the autonomous
result and is intended for visual comparison only.
"""
from __future__ import annotations

import argparse
import colorsys
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAIL_LENGTH = 30
TRACKLET_EXPIRY_FRAMES = 15
TITLE_BAR_HEIGHT = 54


@dataclass(frozen=True)
class TrackPoint:
    frame: int
    center_x: float
    center_y: float
    observed: int


def _point(x: float, y: float) -> tuple[int, int]:
    return round(x), round(y)


def _text(frame, text, origin, color, scale: float = 0.52,
           thickness_black: int = 3, thickness_color: int = 1) -> None:
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale,
                 (0, 0, 0), thickness_black, cv2.LINE_AA)
    cv2.putText(frame, text, origin, cv2.FONT_HERSHEY_SIMPLEX, scale,
                 color, thickness_color, cv2.LINE_AA)


def load_tracklets(path: Path) -> dict[int, list[TrackPoint]]:
    grouped: dict[int, list[TrackPoint]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            grouped[int(row["track_id"])].append(
                TrackPoint(
                    int(row["frame"]),
                    float(row["center_x"]),
                    float(row["center_y"]),
                    int(row.get("observed", "1")),
                )
            )
    return {tid: sorted(pts, key=lambda p: p.frame)
            for tid, pts in grouped.items()}


def load_chain_mapping(path: Path) -> dict[int, int]:
    out: dict[int, int] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                out[int(row["track_id"])] = int(row["chain_id"])
            except (KeyError, ValueError):
                continue
    return out


def load_accepted_edges(path: Path) -> list[dict]:
    """Load FINAL_accepted_edges.csv.  Returns a list of dicts with
    keys: source, target, mode, hand, source_end_frame,
    target_start_frame, gap_frames, evidence_tier, provenance."""
    out: list[dict] = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                out.append({
                    "source": int(row["source"]),
                    "target": int(row["target"]),
                    "mode": row["mode"],
                    "hand": row.get("hand", ""),
                    "source_end_frame": int(row["source_end_frame"]),
                    "target_start_frame": int(row["target_start_frame"]),
                    "gap_frames": int(row["gap_frames"]),
                    "evidence_tier": row.get("evidence_tier", ""),
                    "provenance": row.get("provenance", ""),
                })
            except (KeyError, ValueError):
                continue
    return out


def load_human_labels(path: Path) -> list[dict]:
    """Load canonical human labels.  These are used ONLY for the
    human-reference path.  The autonomous path must NOT read them.
    Returns a list of dicts with keys: track_id (or similar), chain_id,
    and review status.
    """
    out: list[dict] = []
    if not path.is_file():
        return out
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(dict(row))
    return out


def _colors(chain_mapping: dict[int, int]) -> dict[int, tuple[int, int, int]]:
    chain_ids = sorted(set(chain_mapping.values()))
    out: dict[int, tuple[int, int, int]] = {}
    for index, cid in enumerate(chain_ids):
        r, g, b = colorsys.hsv_to_rgb(
            index / max(1, len(chain_ids)), 0.82, 0.95)
        out[cid] = (round(b * 255), round(g * 255), round(r * 255))
    return out


def render_reconstruction(
    *,
    video_path: Path,
    tracklets: dict[int, list[TrackPoint]],
    chain_mapping: dict[int, int],
    edges: list[dict],
    title: str,
    out_path: Path,
) -> None:
    """Render the reconstruction video.  Edges encode the mode
    (AIRBORNE or HAND); the renderer uses them to choose marker
    styles."""
    if not video_path.is_file():
        raise FileNotFoundError(f"Video not found: {video_path}")
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps,
                              (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open writer: {out_path}")

    colors = _colors(chain_mapping)
    # Group edges by source chain for quick lookup.
    edges_by_source: dict[int, list[dict]] = defaultdict(list)
    for e in edges:
        edges_by_source[e["source"]].append(e)

    # Build a frame -> (chain_id -> [points]) lookup for the trail.
    chain_trajectories: dict[int, dict[int, TrackPoint]] = {}
    for tid, points in tracklets.items():
        cid = chain_mapping.get(tid)
        if cid is None:
            continue
        chain_trajectories.setdefault(cid, {})
        for p in points:
            chain_trajectories[cid][p.frame] = p

    cap = cv2.VideoCapture(str(video_path))
    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        # Title bar.
        cv2.rectangle(frame, (0, 0), (width, TITLE_BAR_HEIGHT),
                       (0, 0, 0), -1)
        _text(frame, title, (10, 36), (255, 255, 255), 0.6)
        _text(frame, f"frame {frame_idx}/{n_frames}",
               (width - 220, 36), (200, 200, 200), 0.5)

        for cid, traj in chain_trajectories.items():
            color = colors[cid]
            # Past trail.
            trail = [(f, p) for f, p in traj.items()
                      if frame_idx - TRAIL_LENGTH <= f <= frame_idx]
            trail.sort(key=lambda x: x[0])
            for _, p in trail:
                if p.observed:
                    cv2.circle(frame, _point(p.center_x, p.center_y),
                                4, color, -1)
            # Current observation.
            current = traj.get(frame_idx)
            if current is not None:
                cv2.circle(frame, _point(current.center_x,
                                          current.center_y), 9, color, 2)
                _text(frame, f"C{cid}",
                       (round(current.center_x) + 12,
                         max(20, round(current.center_y) - 8)),
                       color, 0.5)
        # Inferred markers for HAND bridges.
        for e in edges:
            if e["mode"] != "HAND":
                continue
            src_end = e["source_end_frame"]
            tgt_start = e["target_start_frame"]
            if src_end < frame_idx <= tgt_start:
                # Show a "HAND L/R" label at the bridge midpoint.
                src_traj = chain_trajectories.get(e["source"], {})
                tgt_traj = chain_trajectories.get(e["target"], {})
                src_pt = src_traj.get(src_end)
                tgt_pt = tgt_traj.get(tgt_start)
                if src_pt and tgt_pt:
                    mid_x = (src_pt.center_x + tgt_pt.center_x) / 2
                    mid_y = (src_pt.center_y + tgt_pt.center_y) / 2
                    _text(frame, f"HAND {e['hand']}",
                           _point(mid_x, mid_y),
                           (255, 220, 0), 0.5)
        writer.write(frame)
        frame_idx += 1
    cap.release()
    writer.release()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True, type=Path)
    p.add_argument("--tracklets", required=True, type=Path)
    p.add_argument("--chain-mapping", required=True, type=Path)
    p.add_argument("--accepted-edges", type=Path, default=None,
                   help="FINAL_accepted_edges.csv (autonomous path)")
    p.add_argument("--baseline-stitches", type=Path, default=None,
                   help="Baseline airborne stitches CSV (for the "
                        "baseline renderer)")
    p.add_argument("--human-labels", type=Path, default=None,
                   help="Canonical human labels CSV.  Used ONLY for "
                        "the human-reference path.  The autonomous "
                        "path does not read this.")
    p.add_argument("--output-dir", required=True, type=Path)
    args = p.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    tracklets = load_tracklets(args.tracklets)

    # 1. Autonomous: use FINAL chain mapping + FINAL edges.
    auto_chain = load_chain_mapping(args.chain_mapping)
    auto_edges = load_accepted_edges(args.accepted_edges) if args.accepted_edges else []
    auto_out = args.output_dir / "identical_balls_trick_000_018_AUTONOMOUS.mp4"
    render_reconstruction(
        video_path=args.video, tracklets=tracklets,
        chain_mapping=auto_chain, edges=auto_edges,
        title="AUTONOMOUS airborne + hand (v1)",
        out_path=auto_out)
    print(f"Wrote {auto_out}")

    # 2. Baseline: re-derive chain mapping from the existing
    #    accepted-stitches CSV.
    if args.baseline_stitches:
        baseline_chain = _baseline_chain_mapping(args.baseline_stitches,
                                                   tracklets)
        baseline_edges = _baseline_edges(args.baseline_stitches,
                                           baseline_chain)
        baseline_out = args.output_dir / "identical_balls_trick_000_018_BASELINE_airborne.mp4"
        render_reconstruction(
            video_path=args.video, tracklets=tracklets,
            chain_mapping=baseline_chain, edges=baseline_edges,
            title="BASELINE airborne only",
            out_path=baseline_out)
        print(f"Wrote {baseline_out}")

    # 3. Human reference: re-derive chain mapping from canonical
    #    human labels.  Labeled HUMAN_REFERENCE.
    if args.human_labels and args.human_labels.is_file():
        human_chain = _human_chain_mapping(args.human_labels,
                                            tracklets)
        human_edges = _human_edges(args.human_labels, human_chain)
        human_out = args.output_dir / "identical_balls_trick_000_018_HUMAN_REFERENCE.mp4"
        render_reconstruction(
            video_path=args.video, tracklets=tracklets,
            chain_mapping=human_chain, edges=human_edges,
            title="HUMAN_REFERENCE (labels force-known links)",
            out_path=human_out)
        print(f"Wrote {human_out}")


def _baseline_chain_mapping(stitches_csv: Path,
                             tracklets: dict[int, list[TrackPoint]]
                             ) -> dict[int, int]:
    """Build a chain mapping from a baseline airborne stitches CSV.
    Only used for the BASELINE renderer, not for the autonomous
    path."""
    pairs: list[tuple[int, int]] = []
    with stitches_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                if int(row.get("accepted") or "0") != 1:
                    continue
                pairs.append((int(row["source_tracklet"]),
                               int(row["candidate_tracklet"])))
            except (KeyError, ValueError):
                continue
    parent: dict[int, int] = {}
    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    for s, t in pairs:
        if s in tracklets and t in tracklets:
            parent.setdefault(s, s)
            parent.setdefault(t, t)
            union(s, t)
    # All tracklets (even those not in any stitch) get a chain.
    for tid in tracklets:
        parent.setdefault(tid, tid)
    root_to_id: dict[int, int] = {}
    next_id = 1
    out: dict[int, int] = {}
    for tid in sorted(parent.keys()):
        root = find(parent[tid])
        if root not in root_to_id:
            root_to_id[root] = next_id
            next_id += 1
        out[tid] = root_to_id[root]
    return out


def _baseline_edges(stitches_csv: Path,
                   chain_mapping: dict[int, int]
                   ) -> list[dict]:
    out: list[dict] = []
    with stitches_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                if int(row.get("accepted") or "0") != 1:
                    continue
                s = int(row["source_tracklet"])
                t = int(row["candidate_tracklet"])
            except (KeyError, ValueError):
                continue
            sc = chain_mapping.get(s)
            tc = chain_mapping.get(t)
            if sc is None or tc is None or sc == tc:
                continue
            out.append({
                "source": sc, "target": tc, "mode": "AIRBORNE",
                "hand": "", "source_end_frame": 0,
                "target_start_frame": 0, "gap_frames": 0,
                "evidence_tier": "baseline", "provenance": "baseline",
            })
    return out


def _human_chain_mapping(labels_csv: Path,
                          tracklets: dict[int, list[TrackPoint]]
                          ) -> dict[int, int]:
    """Build a chain mapping from the canonical human labels.
    Used ONLY for the HUMAN_REFERENCE renderer."""
    out: dict[int, int] = {}
    if not labels_csv.is_file():
        return out
    with labels_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                tid = int(row.get("track_id")
                          or row.get("source_tracklet") or 0)
                cid = int(row.get("chain_id") or row.get("primary_chain_id") or 0)
                if tid and cid:
                    out[tid] = cid
            except (KeyError, ValueError):
                continue
    return out


def _human_edges(labels_csv: Path, chain_mapping: dict[int, int]
                 ) -> list[dict]:
    return []  # No explicit edges; the chain mapping is the human
               # reference structure.


if __name__ == "__main__":
    main()
