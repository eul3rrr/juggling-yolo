#!/usr/bin/env python3
"""H1 — Hand-pool baseline state machine.

A hand-occlusion-aware chronological pass over observed tracklets that maintains a
per-hand FIFO token stack and emits:
- hand_events.csv        per-frame hand-pool transitions
- hand_inventory.csv     per-hand snapshot of token stack depth + entries/exits
- hand_links.csv         proposed hand-transition links (with provenance)
- tracklet_features.csv  per-tracklet endpoint/start features used as evidence

First-stage thresholds are declared from PHYSICAL GEOMETRY (not from manual
labels). See THRESHOLDS below. E6c/E7/E11 artifacts are read-only evaluation
references.

Read but DO NOT modify:
- /home/it-admin/projects/juggling-yolo-hand-occlusion-night/detections/

Write only to:
- /home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/h1_hand_pool/

Conventions reused from existing experiments:
- track_id, frame, center_x, center_y, observed from norfair_dt50_hc5 CSV
- left/right wrist from yolo26s-pose CSV with conf >= 0.5
- reviewed contact pairs from detections/stitch_review_labels.csv
"""

from __future__ import annotations

import csv
import json
import math
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
# Detections live in this worktree; videos live in the parent juggling-yolo tree
SHIPPED = WORKTREE / "detections"
VIDEOS_DIR = Path("/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos")
H1_DIR = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool"
H1_DATA = H1_DIR / "data"
H1_REPORTS = H1_DIR / "reports"
H1_SCRIPTS = H1_DIR / "scripts"
H1_CS = H1_DIR / "contact_sheets"

# Image height used as physical reference; both clips are 720p (height=720).
# We'll read it dynamically from the first observed tracklet to be safe.
DEFAULT_IMAGE_HEIGHT = 720.0

# ---------------------------------------------------------------------------
# STEMS
# ---------------------------------------------------------------------------
STEMS = {
    "identical_balls_trick_000_018":
        "videos/identical_balls_trick_000_018.mp4",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090":
        "videos/youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090.mp4",
}

# ---------------------------------------------------------------------------
# THRESHOLDS — DECLARED FROM PHYSICAL GEOMETRY (not from manual labels).
#
# Rationale (geometric, not empirical):
# - Ball radius in image ~ 10-15 px for a juggling ball at this camera distance.
# - Hand-palm radius (from wrist) in image ~ 70-90 px for adult hands at 1-2 m.
#   We use a generous boundary of 0.15*image_height = 108 px to admit catches
#   where the ball center is on the back of the hand / fingers.
# - Catch approach: over a 5-frame window, ball is moving INTO a hand.
#   Concretely distance to wrist should DROP by at least 1 px/frame on average.
#   A 5-frame window at 30 fps is ~167 ms, a fast catch; this is a loose floor.
# - Throw divergence: ball is moving OUT of a hand, so distance to wrist should
#   INCREASE by at least 1 px/frame on average.
# - Pose confidence floor: 0.5 (existing convention from e7a/e7b).
# - Min-tracklet-length for endpoint slopes: 3 frames (we need a real window).
# - Minimum gap (tracklet-end to tracklet-start) for an AIR inference to coexist
#   with a HAND transition: 1 frame. Hand transitions can have gap=0.
# ---------------------------------------------------------------------------
THRESHOLDS = {
    "WRIST_CONF_MIN": 0.5,
    "HAND_REACH_PX_RATIO": 0.15,       # 0.15 * image_height = 108 px
    "CATCH_SLOPE_PX_PER_FRAME": -1.0,  # distance decreasing, end window
    "THROW_SLOPE_PX_PER_FRAME": 1.0,   # distance increasing, start window
    "SLOPE_WINDOW": 5,                 # frames for trend
    "MIN_SLOPE_SAMPLES": 3,            # need >=3 valid distance samples
    "MIN_TRACKLET_LEN": 3,             # need >=3 obs to fit a slope
    "MIN_HAND_DIST_SAMPLES": 3,        # per-tracklet distance observations needed
    # for event acceptance (not for slope)
}

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------
@dataclass
class Tracklet:
    tid: int
    pts: list[tuple[int, float, float]] = field(default_factory=list)
    confidences: list[tuple[int, float]] = field(default_factory=list)

    @property
    def first_frame(self) -> int | None:
        return self.pts[0][0] if self.pts else None

    @property
    def last_frame(self) -> int | None:
        return self.pts[-1][0] if self.pts else None

    @property
    def first_point(self) -> tuple[int, float, float] | None:
        return self.pts[0] if self.pts else None

    @property
    def last_point(self) -> tuple[int, float, float] | None:
        return self.pts[-1] if self.pts else None


@dataclass
class Wrist:
    frame: int
    left: tuple[float, float] | None
    right: tuple[float, float] | None


@dataclass
class TrackletFeatures:
    """Per-tracklet summary: end-window + start-window hand-distance info."""
    tid: int
    first_frame: int
    last_frame: int
    n_pts: int
    first_x: float
    first_y: float
    last_x: float
    last_y: float
    # end window (catch signature)
    end_side: str | None
    end_dist: float | None
    end_slope: float | None
    end_samples: int
    end_pose_conf: float | None
    # start window (throw signature)
    start_side: str | None
    start_dist: float | None
    start_slope: float | None
    start_samples: int
    start_pose_conf: float | None


@dataclass
class HandEvent:
    """A single hand-pool event (entry / exit / unmatched / ambiguous)."""
    event_id: int
    video: str
    stem: str
    frame: int
    time_seconds: float
    hand: str                # "left" | "right"
    event_type: str          # ENTRY, EXIT, UNMATCHED_EXIT, UNRESOLVED_HELD_OR_LOST, AMBIGUOUS_POOL_EXIT
    tid: int | None          # tracklet involved
    point_x: float | None
    point_y: float | None
    wrist_x: float | None
    wrist_y: float | None
    dist: float | None
    slope: float | None
    pool_depth: int          # occupancy of this hand at this frame AFTER the event
    pre_depth: int           # occupancy BEFORE the event
    identity_ambiguous: bool
    notes: str = ""


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def load_tracklets(stem: str) -> dict[int, Tracklet]:
    """Load observed tracklets from norfair_dt50_hc5 CSV."""
    path = SHIPPED / f"{stem}_norfair_dt50_hc5.csv"
    out: dict[int, Tracklet] = {}
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("observed") != "1":
                continue
            tid = int(row["track_id"])
            tr = out.setdefault(tid, Tracklet(tid=tid))
            tr.pts.append(
                (int(row["frame"]),
                 float(row["center_x"]),
                 float(row["center_y"]))
            )
            tr.confidences.append((int(row["frame"]), float(row["confidence"])))
    # ensure pts sorted by frame
    for tr in out.values():
        tr.pts.sort(key=lambda p: p[0])
        tr.confidences.sort(key=lambda p: p[0])
    return out


def load_wrists(stem: str) -> dict[int, Wrist]:
    """Load per-frame left/right wrist from yolo26s-pose CSV.

    Returns frame -> Wrist. Only frames with at least one confident wrist
    (>=WRIST_CONF_MIN) appear in the dict.
    """
    path = SHIPPED / f"{stem}_yolo26s-pose.csv"
    out: dict[int, Wrist] = {}
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            f = int(row["frame"])
            entry = out.setdefault(f, Wrist(frame=f, left=None, right=None))
            for side in ("left", "right"):
                conf = row.get(f"{side}_wrist_confidence")
                x = row.get(f"{side}_wrist_x")
                y = row.get(f"{side}_wrist_y")
                if conf is None or x is None or y is None:
                    continue
                if float(conf) < THRESHOLDS["WRIST_CONF_MIN"]:
                    continue
                setattr(entry, side, (float(x), float(y)))
    return out


# ---------------------------------------------------------------------------
# Per-frame hand-distance
# ---------------------------------------------------------------------------
def nearest_hand(
    wrists: dict[int, Wrist],
    frame: int,
    x: float,
    y: float,
    tol: int = 2,
) -> tuple[float, str, tuple[float, float]] | None:
    """Return (distance, side, (wx, wy)) to nearest wrist within +/- tol frames.

    Returns None if no wrist is available in the window.
    """
    best: tuple[float, str, tuple[float, float]] | None = None
    for f in range(frame - tol, frame + tol + 1):
        wr = wrists.get(f)
        if wr is None:
            continue
        for side, xy in (("left", wr.left), ("right", wr.right)):
            if xy is None:
                continue
            d = math.hypot(xy[0] - x, xy[1] - y)
            if best is None or d < best[0]:
                best = (d, side, xy)
    return best


# ---------------------------------------------------------------------------
# Per-tracklet features
# ---------------------------------------------------------------------------
def compute_tracklet_features(
    tracks: dict[int, Tracklet],
    wrists: dict[int, Wrist],
    image_height: float,
) -> dict[int, TrackletFeatures]:
    """For each tracklet, summarize end-window (catch) and start-window
    (throw) hand-distance evidence.

    Distance is the nearest-hand distance; slope is per-frame change in that
    distance over a window of THRESHOLDS['SLOPE_WINDOW'] points.
    """
    hand_reach_px = THRESHOLDS["HAND_REACH_PX_RATIO"] * image_height
    win = THRESHOLDS["SLOPE_WINDOW"]
    out: dict[int, TrackletFeatures] = {}
    for tid, tr in tracks.items():
        if not tr.pts:
            continue
        first_f, first_x, first_y = tr.pts[0]
        last_f, last_x, last_y = tr.pts[-1]

        # end window (catch signature)
        end_pts = tr.pts[-win:]
        end_dists = []
        end_sides = []
        end_wrist_xy: tuple[float, float] | None = None
        end_pose_conf = None
        for f, x, y in end_pts:
            nd = nearest_hand(wrists, f, x, y)
            if nd is None:
                continue
            end_dists.append((f, nd[0]))
            end_sides.append(nd[1])
            end_wrist_xy = nd[2]
        end_slope = None
        end_dist_at = None
        end_side = None
        if len(end_dists) >= THRESHOLDS["MIN_SLOPE_SAMPLES"]:
            fs = np.array([d[0] for d in end_dists], dtype=float)
            ds = np.array([d[1] for d in end_dists], dtype=float)
            if fs.max() != fs.min():
                end_slope = float(np.polyfit(fs, ds, 1)[0])
            end_dist_at = float(ds[-1])
            end_side = end_sides[-1]
            # pose conf at endpoint frame
            wr_at = wrists.get(last_f)
            if wr_at is not None:
                side_conf = None
                if end_side == "left" and wr_at.left is not None:
                    side_conf = next((c for fr, c in tr.confidences if fr == last_f), None)
                if end_side == "right" and wr_at.right is not None:
                    side_conf = next((c for fr, c in tr.confidences if fr == last_f), None)
                end_pose_conf = side_conf

        # start window (throw signature)
        start_pts = tr.pts[:win]
        start_dists = []
        start_sides = []
        start_wrist_xy: tuple[float, float] | None = None
        for f, x, y in start_pts:
            nd = nearest_hand(wrists, f, x, y)
            if nd is None:
                continue
            start_dists.append((f, nd[0]))
            start_sides.append(nd[1])
            start_wrist_xy = nd[2]
        start_slope = None
        start_dist_at = None
        start_side = None
        if len(start_dists) >= THRESHOLDS["MIN_SLOPE_SAMPLES"]:
            fs = np.array([d[0] for d in start_dists], dtype=float)
            ds = np.array([d[1] for d in start_dists], dtype=float)
            if fs.max() != fs.min():
                start_slope = float(np.polyfit(fs, ds, 1)[0])
            start_dist_at = float(ds[0])
            start_side = start_sides[0]

        out[tid] = TrackletFeatures(
            tid=tid,
            first_frame=first_f,
            last_frame=last_f,
            n_pts=len(tr.pts),
            first_x=first_x, first_y=first_y,
            last_x=last_x, last_y=last_y,
            end_side=end_side,
            end_dist=end_dist_at,
            end_slope=end_slope,
            end_samples=len(end_dists),
            end_pose_conf=end_pose_conf,
            start_side=start_side,
            start_dist=start_dist_at,
            start_slope=start_slope,
            start_samples=len(start_dists),
            start_pose_conf=end_pose_conf,
        )
    return out


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------
@dataclass
class HandState:
    """Per-hand FIFO token stack with arrival metadata.

    Each token: {'arrived_frame', 'arrived_tid', 'arrived_x', 'arrived_y',
                  'arrived_dist', 'arrived_slope', 'arrived_side',
                  'arrived_pose_conf', 'id'}
    """
    side: str
    tokens: deque = field(default_factory=deque)
    next_token_id: int = 0

    def depth(self) -> int:
        return len(self.tokens)


def time_seconds(frame: int, fps: float = 30.0) -> float:
    return frame / fps


# ---------------------------------------------------------------------------
# Event classification
# ---------------------------------------------------------------------------
def classify_catch(features: TrackletFeatures, hand_reach_px: float) -> dict:
    """Return dict with keys {is_catch, side, dist, slope, conf} for the END of
    a tracklet (catch = ball entering a hand)."""
    if features.n_pts < THRESHOLDS["MIN_TRACKLET_LEN"]:
        return {"is_catch": False, "side": None, "dist": None, "slope": None}
    if features.end_dist is None or features.end_dist > hand_reach_px:
        return {"is_catch": False, "side": features.end_side,
                "dist": features.end_dist, "slope": features.end_slope}
    if (features.end_slope is None or
            features.end_slope > THRESHOLDS["CATCH_SLOPE_PX_PER_FRAME"]):
        return {"is_catch": False, "side": features.end_side,
                "dist": features.end_dist, "slope": features.end_slope}
    return {"is_catch": True, "side": features.end_side,
            "dist": features.end_dist, "slope": features.end_slope}


def classify_throw(features: TrackletFeatures, hand_reach_px: float) -> dict:
    """Return dict for the START of a tracklet (throw = ball leaving a hand)."""
    if features.n_pts < THRESHOLDS["MIN_TRACKLET_LEN"]:
        return {"is_throw": False, "side": None, "dist": None, "slope": None}
    if features.start_dist is None or features.start_dist > hand_reach_px:
        return {"is_throw": False, "side": features.start_side,
                "dist": features.start_dist, "slope": features.start_slope}
    if (features.start_slope is None or
            features.start_slope < THRESHOLDS["THROW_SLOPE_PX_PER_FRAME"]):
        return {"is_throw": False, "side": features.start_side,
                "dist": features.start_dist, "slope": features.start_slope}
    return {"is_throw": True, "side": features.start_side,
            "dist": features.start_dist, "slope": features.start_slope}


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run_for_stem(
    stem: str,
    video_key: str,
    image_height: float = DEFAULT_IMAGE_HEIGHT,
) -> dict:
    tracks = load_tracklets(stem)
    wrists = load_wrists(stem)
    feats = compute_tracklet_features(tracks, wrists, image_height)

    # Per-hand state
    state = {
        "left": HandState(side="left"),
        "right": HandState(side="right"),
    }

    # Build a per-frame timeline of tracklet events. Each tracklet contributes:
    #   - a CATCH candidate at last_frame
    #   - a THROW candidate at first_frame
    # We process frames in chronological order; for each frame, we apply all
    # THROW candidates at that frame (before CATCH candidates, so the
    # inventory is consumed then re-filled).
    catch_candidates: dict[int, list[tuple[int, dict]]] = defaultdict(list)  # frame -> [(tid, info)]
    throw_candidates: dict[int, list[tuple[int, dict]]] = defaultdict(list)
    hand_reach_px = THRESHOLDS["HAND_REACH_PX_RATIO"] * image_height

    for tid, f in feats.items():
        c = classify_catch(f, hand_reach_px)
        t = classify_throw(f, hand_reach_px)
        if c["is_catch"]:
            catch_candidates[f.last_frame].append((tid, c))
        if t["is_throw"]:
            throw_candidates[f.first_frame].append((tid, t))

    # Per-frame tracking
    all_events: list[HandEvent] = []
    inv_snapshots: list[dict] = []
    hand_links: list[dict] = []
    event_id = 0
    # Counters
    counters = {
        "ENTRY": 0, "EXIT": 0, "UNMATCHED_EXIT": 0,
        "UNRESOLVED_HELD_OR_LOST": 0, "AMBIGUOUS_POOL_EXIT": 0,
    }
    predecessor_conflict = 0  # multiple catch candidates for same hand+frame
    successor_conflict = 0    # multiple throw candidates for same hand+frame
    impossible_states = 0     # any pre_depth < 0 (shouldn't happen if invariants hold)
    multi_token_ambiguous = 0

    # Pre-compute frame range
    all_frames_throw = set(throw_candidates.keys())
    all_frames_catch = set(catch_candidates.keys())
    if all_frames_throw or all_frames_catch:
        fmin = min(all_frames_throw | all_frames_catch)
        fmax = max(all_frames_throw | all_frames_catch)
    else:
        fmin, fmax = 0, 0

    for frame in range(fmin, fmax + 1):
        # ---- process THROW candidates first (exit before entry) ----
        for tid, info in throw_candidates.get(frame, []):
            side = info["side"]
            if side not in state:
                continue
            st = state[side]
            pre_depth = st.depth()
            if pre_depth == 0:
                # UNMATCHED_EXIT
                event_id += 1
                ev = HandEvent(
                    event_id=event_id, video=video_key, stem=stem,
                    frame=frame, time_seconds=time_seconds(frame),
                    hand=side, event_type="UNMATCHED_EXIT",
                    tid=tid, point_x=feats[tid].first_x, point_y=feats[tid].first_y,
                    wrist_x=None, wrist_y=None,
                    dist=info["dist"], slope=info["slope"],
                    pool_depth=pre_depth, pre_depth=pre_depth,
                    identity_ambiguous=False,
                    notes="throw-side exit; hand was empty",
                )
                all_events.append(ev)
                counters["UNMATCHED_EXIT"] += 1
            else:
                # pop oldest token (FIFO bookkeeping only)
                tok = st.tokens.popleft()
                ambig = pre_depth > 1
                if ambig:
                    multi_token_ambiguous += 1
                et = "AMBIGUOUS_POOL_EXIT" if ambig else "EXIT"
                event_id += 1
                ev = HandEvent(
                    event_id=event_id, video=video_key, stem=stem,
                    frame=frame, time_seconds=time_seconds(frame),
                    hand=side, event_type=et,
                    tid=tid, point_x=feats[tid].first_x, point_y=feats[tid].first_y,
                    wrist_x=tok["arrived_wrist"][0], wrist_y=tok["arrived_wrist"][1],
                    dist=info["dist"], slope=info["slope"],
                    pool_depth=st.depth(), pre_depth=pre_depth,
                    identity_ambiguous=ambig,
                    notes=f"consumed token {tok['id']} from {tok['arrived_tid']}",
                )
                all_events.append(ev)
                counters[et] += 1
                # record link
                hand_links.append({
                    "video": video_key, "stem": stem,
                    "from_tid": tok["arrived_tid"],
                    "to_tid": tid,
                    "hand": side,
                    "from_frame": tok["arrived_frame"],
                    "to_frame": frame,
                    "from_dist": tok["arrived_dist"],
                    "to_dist": info["dist"],
                    "from_slope": tok["arrived_slope"],
                    "to_slope": info["slope"],
                    "identity_ambiguous": ambig,
                    "kind": et,
                })

        # ---- process CATCH candidates ----
        # group by side: if multiple catch candidates land on the same hand
        # at the same frame, that's a predecessor conflict.
        cands_by_side: dict[str, list[tuple[int, dict]]] = defaultdict(list)
        for tid, info in catch_candidates.get(frame, []):
            if info["side"] is None:
                continue
            cands_by_side[info["side"]].append((tid, info))
        for side, cands in cands_by_side.items():
            if len(cands) > 1:
                predecessor_conflict += 1
            st = state[side]
            for tid, info in cands:
                pre_depth = st.depth()
                # find the wrist at this frame
                wr = wrists.get(frame)
                wrist_xy = None
                if wr is not None and side == "left":
                    wrist_xy = wr.left
                elif wr is not None and side == "right":
                    wrist_xy = wr.right
                # create new token
                st.next_token_id += 1
                tok = {
                    "id": st.next_token_id,
                    "arrived_frame": frame,
                    "arrived_tid": tid,
                    "arrived_x": feats[tid].last_x,
                    "arrived_y": feats[tid].last_y,
                    "arrived_dist": info["dist"],
                    "arrived_slope": info["slope"],
                    "arrived_side": side,
                    "arrived_wrist": wrist_xy,
                }
                st.tokens.append(tok)
                event_id += 1
                ev = HandEvent(
                    event_id=event_id, video=video_key, stem=stem,
                    frame=frame, time_seconds=time_seconds(frame),
                    hand=side, event_type="ENTRY",
                    tid=tid, point_x=feats[tid].last_x, point_y=feats[tid].last_y,
                    wrist_x=(wrist_xy[0] if wrist_xy else None),
                    wrist_y=(wrist_xy[1] if wrist_xy else None),
                    dist=info["dist"], slope=info["slope"],
                    pool_depth=st.depth(), pre_depth=pre_depth,
                    identity_ambiguous=(st.depth() > 1),
                    notes=f"token {tok['id']} created",
                )
                all_events.append(ev)
                counters["ENTRY"] += 1

        # ---- record inventory snapshot at every frame (or only on change?) ----
        # To keep file small, snapshot only at frames where at least one event
        # occurred (or every 10 frames if no events).
        had_event = bool(throw_candidates.get(frame) or catch_candidates.get(frame))
        if had_event or (frame % 10 == 0):
            inv_snapshots.append({
                "video": video_key, "stem": stem, "frame": frame,
                "time_seconds": time_seconds(frame),
                "left_depth": state["left"].depth(),
                "right_depth": state["right"].depth(),
                "left_tokens": [t["id"] for t in state["left"].tokens],
                "right_tokens": [t["id"] for t in state["right"].tokens],
                "left_token_tids": [t["arrived_tid"] for t in state["left"].tokens],
                "right_token_tids": [t["arrived_tid"] for t in state["right"].tokens],
            })

    # At end of video: any tokens still in either hand are UNRESOLVED_HELD_OR_LOST
    for side in ("left", "right"):
        st = state[side]
        # pop remaining tokens, one UNRESOLVED event per remaining token
        for tok in list(st.tokens):
            event_id += 1
            ev = HandEvent(
                event_id=event_id, video=video_key, stem=stem,
                frame=fmax, time_seconds=time_seconds(fmax),
                hand=side, event_type="UNRESOLVED_HELD_OR_LOST",
                tid=tok["arrived_tid"],
                point_x=tok["arrived_x"], point_y=tok["arrived_y"],
                wrist_x=(tok["arrived_wrist"][0] if tok["arrived_wrist"] else None),
                wrist_y=(tok["arrived_wrist"][1] if tok["arrived_wrist"] else None),
                dist=tok["arrived_dist"], slope=tok["arrived_slope"],
                pool_depth=st.depth(), pre_depth=st.depth(),
                identity_ambiguous=True,
                notes=f"end-of-video: token {tok['id']} never consumed",
            )
            all_events.append(ev)
            counters["UNRESOLVED_HELD_OR_LOST"] += 1
            st.tokens.popleft()

    # impossible states check
    for ev in all_events:
        if ev.pre_depth < 0:
            impossible_states += 1

    return {
        "stem": stem,
        "video_key": video_key,
        "features": feats,
        "events": all_events,
        "inventory": inv_snapshots,
        "links": hand_links,
        "counters": counters,
        "predecessor_conflict": predecessor_conflict,
        "successor_conflict": successor_conflict,
        "impossible_states": impossible_states,
        "multi_token_ambiguous": multi_token_ambiguous,
        "image_height": image_height,
        "hand_reach_px": hand_reach_px,
    }


# ---------------------------------------------------------------------------
# Evaluation against reviewed contact pairs
# ---------------------------------------------------------------------------
def load_reviewed_pairs(video_key: str) -> list[tuple[int, int, str]]:
    path = SHIPPED / "stitch_review_labels.csv"
    out: list[tuple[int, int, str]] = []
    with path.open(newline="") as fh:
        for r in csv.DictReader(fh):
            if r["video"] != video_key:
                continue
            try:
                out.append(
                    (int(r["source_tracklet"]),
                     int(r["candidate_tracklet"]),
                     r["label"])
                )
            except (KeyError, ValueError):
                continue
    return out


def evaluate_against_labels(
    summary: dict,
    video_key: str,
    reviewed: list[tuple[int, int, str]],
) -> dict:
    """For each reviewed (source, candidate, label) pair, classify H1's behavior:
    - HAND_LINK   if H1 produced a hand-link for this source->candidate
                  (any hand)
    - NO_LINK     if no hand-link produced
    - WRONG_HAND  if H1 produced a link to a different tracklet (rare)
    """
    by_src = defaultdict(list)
    for link in summary["links"]:
        by_src[link["from_tid"]].append(link)

    matched_correct = 0
    matched_wrong = 0
    missed_correct = 0
    missed_wrong = 0
    per_pair = []
    for src, cand, label in reviewed:
        links = by_src.get(src, [])
        match = [l for l in links if l["to_tid"] == cand]
        if match:
            if label == "correct":
                matched_correct += 1
            else:
                matched_wrong += 1
            per_pair.append({
                "src": src, "cand": cand, "label": label,
                "h1_decision": "HAND_LINK",
                "hand": match[0]["hand"],
                "ambiguous": match[0]["identity_ambiguous"],
            })
        else:
            if label == "correct":
                missed_correct += 1
            else:
                missed_wrong += 1
            per_pair.append({
                "src": src, "cand": cand, "label": label,
                "h1_decision": "NO_LINK",
                "hand": None, "ambiguous": None,
            })
    prec = matched_correct / max(1, matched_correct + matched_wrong)
    rec = matched_correct / max(1, matched_correct + missed_correct)
    return {
        "video": video_key,
        "reviewed_total": len(reviewed),
        "matched_correct": matched_correct,
        "matched_wrong": matched_wrong,
        "missed_correct": missed_correct,
        "missed_wrong": missed_wrong,
        "precision_hand_link": prec,
        "recall_hand_link": rec,
        "per_pair": per_pair,
    }


# ---------------------------------------------------------------------------
# Outputs
# ---------------------------------------------------------------------------
def write_outputs(all_runs: list[dict]) -> None:
    H1_DATA.mkdir(parents=True, exist_ok=True)
    H1_REPORTS.mkdir(parents=True, exist_ok=True)

    # hand_events.csv
    with (H1_DATA / "hand_events.csv").open("w", newline="") as fh:
        fields = [
            "event_id", "video", "stem", "frame", "time_seconds",
            "hand", "event_type", "tid",
            "point_x", "point_y", "wrist_x", "wrist_y",
            "dist", "slope", "pre_depth", "pool_depth",
            "identity_ambiguous", "notes",
        ]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for run in all_runs:
            for ev in run["events"]:
                w.writerow({
                    "event_id": ev.event_id, "video": ev.video, "stem": ev.stem,
                    "frame": ev.frame, "time_seconds": round(ev.time_seconds, 4),
                    "hand": ev.hand, "event_type": ev.event_type,
                    "tid": ev.tid if ev.tid is not None else "",
                    "point_x": round(ev.point_x, 2) if ev.point_x is not None else "",
                    "point_y": round(ev.point_y, 2) if ev.point_y is not None else "",
                    "wrist_x": round(ev.wrist_x, 2) if ev.wrist_x is not None else "",
                    "wrist_y": round(ev.wrist_y, 2) if ev.wrist_y is not None else "",
                    "dist": round(ev.dist, 2) if ev.dist is not None else "",
                    "slope": round(ev.slope, 3) if ev.slope is not None else "",
                    "pre_depth": ev.pre_depth, "pool_depth": ev.pool_depth,
                    "identity_ambiguous": ev.identity_ambiguous,
                    "notes": ev.notes,
                })

    # hand_inventory.csv
    with (H1_DATA / "hand_inventory.csv").open("w", newline="") as fh:
        fields = [
            "video", "stem", "frame", "time_seconds",
            "left_depth", "right_depth",
            "left_tokens", "right_tokens",
            "left_token_tids", "right_token_tids",
        ]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for run in all_runs:
            for inv in run["inventory"]:
                w.writerow({
                    "video": inv["video"], "stem": inv["stem"],
                    "frame": inv["frame"],
                    "time_seconds": round(inv["time_seconds"], 4),
                    "left_depth": inv["left_depth"],
                    "right_depth": inv["right_depth"],
                    "left_tokens": ";".join(str(t) for t in inv["left_tokens"]),
                    "right_tokens": ";".join(str(t) for t in inv["right_tokens"]),
                    "left_token_tids": ";".join(str(t) for t in inv["left_token_tids"]),
                    "right_token_tids": ";".join(str(t) for t in inv["right_token_tids"]),
                })

    # hand_links.csv
    with (H1_DATA / "hand_links.csv").open("w", newline="") as fh:
        fields = [
            "video", "stem", "from_tid", "to_tid", "hand",
            "from_frame", "to_frame",
            "from_dist", "to_dist", "from_slope", "to_slope",
            "identity_ambiguous", "kind",
        ]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for run in all_runs:
            for link in run["links"]:
                w.writerow({
                    "video": link["video"], "stem": link["stem"],
                    "from_tid": link["from_tid"],
                    "to_tid": link["to_tid"],
                    "hand": link["hand"],
                    "from_frame": link["from_frame"],
                    "to_frame": link["to_frame"],
                    "from_dist": round(link["from_dist"], 2) if link["from_dist"] is not None else "",
                    "to_dist": round(link["to_dist"], 2) if link["to_dist"] is not None else "",
                    "from_slope": round(link["from_slope"], 3) if link["from_slope"] is not None else "",
                    "to_slope": round(link["to_slope"], 3) if link["to_slope"] is not None else "",
                    "identity_ambiguous": link["identity_ambiguous"],
                    "kind": link["kind"],
                })

    # tracklet_features.csv
    with (H1_DATA / "tracklet_features.csv").open("w", newline="") as fh:
        fields = [
            "video", "stem", "tid", "first_frame", "last_frame", "n_pts",
            "first_x", "first_y", "last_x", "last_y",
            "end_side", "end_dist", "end_slope", "end_samples", "end_pose_conf",
            "start_side", "start_dist", "start_slope", "start_samples",
            "start_pose_conf",
        ]
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for run in all_runs:
            for tid, f in run["features"].items():
                w.writerow({
                    "video": run["video_key"], "stem": run["stem"],
                    "tid": tid,
                    "first_frame": f.first_frame, "last_frame": f.last_frame,
                    "n_pts": f.n_pts,
                    "first_x": round(f.first_x, 2), "first_y": round(f.first_y, 2),
                    "last_x": round(f.last_x, 2), "last_y": round(f.last_y, 2),
                    "end_side": f.end_side if f.end_side is not None else "",
                    "end_dist": round(f.end_dist, 2) if f.end_dist is not None else "",
                    "end_slope": round(f.end_slope, 3) if f.end_slope is not None else "",
                    "end_samples": f.end_samples,
                    "end_pose_conf": round(f.end_pose_conf, 3) if f.end_pose_conf is not None else "",
                    "start_side": f.start_side if f.start_side is not None else "",
                    "start_dist": round(f.start_dist, 2) if f.start_dist is not None else "",
                    "start_slope": round(f.start_slope, 3) if f.start_slope is not None else "",
                    "start_samples": f.start_samples,
                    "start_pose_conf": round(f.start_pose_conf, 3) if f.start_pose_conf is not None else "",
                })

    # summary json
    summary = {
        "thresholds": THRESHOLDS,
        "image_height": DEFAULT_IMAGE_HEIGHT,
        "hand_reach_px": DEFAULT_IMAGE_HEIGHT * THRESHOLDS["HAND_REACH_PX_RATIO"],
        "videos": {},
    }
    for run in all_runs:
        reviewed = load_reviewed_pairs(run["video_key"])
        ev = evaluate_against_labels(run, run["video_key"], reviewed)
        summary["videos"][run["stem"]] = {
            "video_key": run["video_key"],
            "event_counts": run["counters"],
            "predecessor_conflicts": run["predecessor_conflict"],
            "successor_conflicts": run["successor_conflict"],
            "impossible_states": run["impossible_states"],
            "multi_token_ambiguous_events": run["multi_token_ambiguous"],
            "n_links": len(run["links"]),
            "n_tracklets": len(run["features"]),
            "evaluation_vs_reviewed": {
                "reviewed_total": ev["reviewed_total"],
                "matched_correct": ev["matched_correct"],
                "matched_wrong": ev["matched_wrong"],
                "missed_correct": ev["missed_correct"],
                "missed_wrong": ev["missed_wrong"],
                "precision_hand_link": ev["precision_hand_link"],
                "recall_hand_link": ev["recall_hand_link"],
            },
        }
    (H1_DATA / "summary.json").write_text(json.dumps(summary, indent=2))
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    H1_DATA.mkdir(parents=True, exist_ok=True)
    H1_REPORTS.mkdir(parents=True, exist_ok=True)
    all_runs: list[dict] = []
    for stem, video_key in STEMS.items():
        print(f"[{stem}] running H1 hand-pool state machine...")
        run = run_for_stem(stem, video_key)
        print(f"  events: {run['counters']}")
        print(f"  links:  {len(run['links'])}")
        print(f"  predecessor conflicts: {run['predecessor_conflict']}")
        print(f"  impossible states:     {run['impossible_states']}")
        all_runs.append(run)

    summary = write_outputs(all_runs)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
