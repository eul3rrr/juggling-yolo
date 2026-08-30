"""Render the SHORT human-reference reconstruction.

The canonical human labels cover only the first ~3.7 seconds of
the canonical 18-second video, working on the 14-tracklet system.
This renderer produces a 3.7s human-reference clip using the
14-tracklet pipeline + the human labels.
"""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import cv2


def _load_tracklets(path: Path) -> dict[int, list[tuple[int, float, float]]]:
    out: dict[int, list[tuple[int, float, float]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                tid = int(row["track_id"])
                fr = int(row["frame"])
                cx = float(row["center_x"])
                cy = float(row["center_y"])
            except (KeyError, ValueError):
                continue
            out[tid].append((fr, cx, cy))
    return {tid: sorted(pts) for tid, pts in out.items()}


def _load_human_links(labels_csv: Path):
    """Return a list of (source_track_id, target_track_id) for
    human-confirmed selected links."""
    out = []
    with labels_csv.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("continuation_status") != "selected":
                continue
            try:
                t1 = int(row["primary_track_id"])
                t2 = (int(row.get("selected_related_track_id") or 0)
                      or int(row.get("selected_continuation_track_id") or 0))
            except (KeyError, ValueError):
                continue
            if t1 and t2:
                out.append((t1, t2))
    return out


def _human_chain_mapping(tracklets: dict, links: list[tuple[int, int]]):
    parent: dict[int, int] = {t: t for t in tracklets}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    for s, t in links:
        if s in tracklets and t in tracklets:
            parent.setdefault(s, s)
            parent.setdefault(t, t)
            union(s, t)
    root_to_id: dict[int, int] = {}
    next_id = 1
    out: dict[int, int] = {}
    for tid in sorted(tracklets.keys()):
        root = find(tid)
        if root not in root_to_id:
            root_to_id[root] = next_id
            next_id += 1
        out[tid] = root_to_id[root]
    return out


def _colors(chain_mapping):
    chain_ids = sorted(set(chain_mapping.values()))
    import colorsys
    out: dict[int, tuple[int, int, int]] = {}
    for i, cid in enumerate(chain_ids):
        r, g, b = colorsys.hsv_to_rgb(
            i / max(1, len(chain_ids)), 0.82, 0.95)
        out[cid] = (round(b * 255), round(g * 255), round(r * 255))
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--video", required=True, type=Path)
    p.add_argument("--tracklets", required=True, type=Path)
    p.add_argument("--labels", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--max-frame", type=int, default=230)
    args = p.parse_args()

    tracklets = _load_tracklets(args.tracklets)
    links = _load_human_links(args.labels)
    chain_mapping = _human_chain_mapping(tracklets, links)
    colors = _colors(chain_mapping)

    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        raise RuntimeError(f"Could not open video: {args.video}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 60.0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(args.output), fourcc, fps,
                              (width, height))

    cap = cv2.VideoCapture(str(args.video))
    frame_idx = 0
    title = "HUMAN_REFERENCE (labels force known links)"
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx > args.max_frame:
            break
        cv2.rectangle(frame, (0, 0), (width, 54), (0, 0, 0), -1)
        cv2.putText(frame, title, (10, 36),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                     (255, 255, 255), 1, cv2.LINE_AA)
        cv2.putText(frame, f"frame {frame_idx}",
                     (width - 120, 36),
                     cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                     (200, 200, 200), 1, cv2.LINE_AA)
        for tid, points in tracklets.items():
            cid = chain_mapping.get(tid)
            if cid is None:
                continue
            color = colors[cid]
            for f, cx, cy in points:
                if frame_idx - 30 <= f <= frame_idx:
                    cv2.circle(frame, (round(cx), round(cy)),
                                4, color, -1)
            current = [p for p in points if p[0] == frame_idx]
            if current:
                f, cx, cy = current[0]
                cv2.circle(frame, (round(cx), round(cy)),
                            9, color, 2)
                cv2.putText(frame, f"C{cid}",
                             (round(cx) + 12, max(20, round(cy) - 8)),
                             cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                             color, 1, cv2.LINE_AA)
        writer.write(frame)
        frame_idx += 1
    cap.release()
    writer.release()
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
