#!/usr/bin/env python3
"""H1 v2 — Hand-pool baseline state machine with physics-aware filters.

Adds the 5 filters identified from v1 visual QA (see h1_v1_report.md §8):

1. **Token TTL** (TOK_TTL_FRAMES) — tokens older than this expire as EXPIRED_HELD.
2. **Stale-token rejection** (STALE_TTL_FRAMES) — if a throw pops a token older
   than this, the throw is recorded as STALE_TOKEN_THROW, the link is dropped,
   and the throw is treated as UNMATCHED_EXIT for hand-link purposes.
3. **Throw strictness** (THROW_LEAVE_WINDOW_FRAMES) — require the ball to
   leave the reach radius within the first N observed frames of the
   tracklet (a real throw gains height fast).
4. **Wrist-movement guard** (WRIST_VEL_MAX) — compute per-frame wrist velocity
   in the throw window; if > V px/frame, the throw is recorded as
   WRIST_MOTION_THROW (not a hand-link).
5. **Catch strictness** (CATCH_CONTEXT_FRAMES) — require a recent hand event
   on the same hand in the last W frames; an entry with no prior hand
   activity is suspicious; it is recorded as UNCONTEXTED_ENTRY.

Outputs (parallel to v1):
- hand_events.csv
- hand_inventory.csv
- hand_links.csv (only true single-token and ambiguous hand-links survive)
- tracklet_features.csv (carries v2 diagnostics)
- summary.json

v2 vs v1:
- The 5 filters are DECLARED UP FRONT from physical geometry / observed v1
  failure modes, NOT from manual labels.
- Each filtered event still emits a row in hand_events.csv so we can count
  what was filtered and why.
- The state machine still enforces the FIFO token stack and the impossible-
  state / conflict checks.
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

# Reuse v1's data loaders, feature extraction, and Tracklet / Wrist / etc.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from h1_hand_pool import (  # noqa: E402
    DEFAULT_IMAGE_HEIGHT, STEMS, SHIPPED, H1_DIR, H1_DATA, H1_REPORTS,
    H1_CS, Tracklet, Wrist, TrackletFeatures, HandEvent,
    HandState, time_seconds,
    load_tracklets, load_wrists, nearest_hand, compute_tracklet_features,
    classify_catch, classify_throw,
    load_reviewed_pairs, evaluate_against_labels,
    write_outputs as v1_write_outputs,
    THRESHOLDS as V1_THRESHOLDS,
)

# -----------------------------------------------------------------------
# v2 thresholds — declared from physical geometry and v1 failure modes.
# -----------------------------------------------------------------------
# These are NOT tuned to manual labels.
# - TOK_TTL_FRAMES: 60 frames = 2.0 s at 30 fps. A real held ball rarely
#   stays continuously invisible for >2 s. v1 left tokens "live" until the
#   end of the video (10+ s), so a current throw could pop a token from
#   many seconds ago. 2 s is a generous ceiling.
# - STALE_TTL_FRAMES: 30 frames = 1.0 s. If a throw pops a token older than
#   1 s, the identity is too ambiguous for a hand-link.
# - THROW_LEAVE_WINDOW_FRAMES: 3 frames = 100 ms. A real throw at ~30 fps
#   moves the ball >1 ball-radius per frame; the ball leaves the hand
#   within ~100 ms.
# - WRIST_VEL_MAX: 30 px/frame. Hands can move at most ~30 px/frame at 30
#   fps without motion blur destroying the ball detection; a real throw
#   involves a slow hand (the ball leaves the hand before the hand moves
#   fast).
# - CATCH_CONTEXT_FRAMES: 60 frames = 2.0 s. A catch without a recent
#   hand event in the same window is suspicious (could be a dropout).
V2_THRESHOLDS = {
    "TOK_TTL_FRAMES": 60,
    "STALE_TTL_FRAMES": 30,
    "THROW_LEAVE_WINDOW_FRAMES": 3,
    "WRIST_VEL_MAX": 30.0,
    "CATCH_CONTEXT_FRAMES": 60,
}


# -----------------------------------------------------------------------
# v2 helpers
# -----------------------------------------------------------------------
def wrist_velocity(wrists: dict[int, Wrist], frame: int, side: str,
                   win: int = 3) -> float | None:
    """Mean per-frame wrist velocity (px/frame) over a small window around
    `frame`. Returns None if not enough data.

    We sample the wrist position on the 2*win+1 frames around `frame` and
    take the mean of the absolute frame-to-frame displacement, which is
    a robust measure of "how fast is the hand moving right now".
    """
    pts: list[tuple[int, float, float]] = []
    for f in range(frame - win, frame + win + 1):
        wr = wrists.get(f)
        if wr is None:
            continue
        xy = getattr(wr, side)
        if xy is None:
            continue
        pts.append((f, xy[0], xy[1]))
    if len(pts) < 2:
        return None
    pts.sort(key=lambda p: p[0])
    diffs = []
    for (f1, x1, y1), (f2, x2, y2) in zip(pts, pts[1:]):
        df = max(1, f2 - f1)
        diffs.append(math.hypot(x2 - x1, y2 - y1) / df)
    return float(np.mean(diffs)) if diffs else None


def throw_leaves_within(
    track: Tracklet,
    wrists: dict[int, Wrist],
    hand_reach_px: float,
    leave_window: int,
    side: str,
) -> bool:
    """True if the ball leaves the reach radius within the first
    `leave_window` observed frames of the tracklet, AS SEEN FROM THE NAMED
    HAND. We compute per-frame distance to the named hand's wrist, not the
    nearest hand, so we test whether this tracklet was actually born out
    of THIS hand.
    """
    if not track.pts or side not in ("left", "right"):
        return False
    for f, x, y in track.pts[:leave_window]:
        wr = wrists.get(f)
        if wr is None:
            continue
        xy = getattr(wr, side)
        if xy is None:
            continue
        if math.hypot(xy[0] - x, xy[1] - y) > hand_reach_px:
            return True
    return False


# -----------------------------------------------------------------------
# v2 state machine
# -----------------------------------------------------------------------
def run_for_stem_v2(
    stem: str,
    video_key: str,
    image_height: float = DEFAULT_IMAGE_HEIGHT,
) -> dict:
    tracks = load_tracklets(stem)
    wrists = load_wrists(stem)
    feats = compute_tracklet_features(tracks, wrists, image_height)

    state = {
        "left": HandState(side="left"),
        "right": HandState(side="right"),
    }

    # also track per-hand "last hand-event frame" for catch context
    last_hand_event_frame = {"left": -10_000, "right": -10_000}

    hand_reach_px = V1_THRESHOLDS["HAND_REACH_PX_RATIO"] * image_height

    # Reuse v1 candidate construction, but pin a side for throw-strictness.
    catch_candidates: dict[int, list[tuple[int, dict]]] = defaultdict(list)
    throw_candidates: dict[int, list[tuple[int, dict]]] = defaultdict(list)
    for tid, f in feats.items():
        c = classify_catch(f, hand_reach_px)
        t = classify_throw(f, hand_reach_px)
        if c["is_catch"]:
            catch_candidates[f.last_frame].append((tid, c))
        if t["is_throw"]:
            throw_candidates[f.first_frame].append((tid, t))

    all_events: list[HandEvent] = []
    inv_snapshots: list[dict] = []
    hand_links: list[dict] = []
    filtered_stats = {
        "EXPIRED_HELD": 0,
        "STALE_TOKEN_THROW": 0,
        "WRIST_MOTION_THROW": 0,
        "THROW_NO_LEAVE": 0,
        "UNCONTEXTED_ENTRY": 0,
    }
    counters = {
        "ENTRY": 0, "EXIT": 0, "UNMATCHED_EXIT": 0,
        "UNRESOLVED_HELD_OR_LOST": 0, "AMBIGUOUS_POOL_EXIT": 0,
    }
    predecessor_conflict = 0
    successor_conflict = 0
    impossible_states = 0
    multi_token_ambiguous = 0

    all_frames_throw = set(throw_candidates.keys())
    all_frames_catch = set(catch_candidates.keys())
    if all_frames_throw or all_frames_catch:
        fmin = min(all_frames_throw | all_frames_catch)
        fmax = max(all_frames_throw | all_frames_catch)
    else:
        fmin, fmax = 0, 0

    event_id = 0

    def emit(ev: HandEvent, ctr_key: str | None = None,
             ambiguous: bool = False) -> None:
        nonlocal multi_token_ambiguous
        all_events.append(ev)
        if ctr_key is not None and ctr_key in counters:
            counters[ctr_key] += 1
        if ambiguous:
            multi_token_ambiguous += 1

    for frame in range(fmin, fmax + 1):
        # ------- EXPIRE stale tokens (TTL filter) -------
        for side in ("left", "right"):
            st = state[side]
            while st.tokens and (frame - st.tokens[0]["arrived_frame"]
                                 > V2_THRESHOLDS["TOK_TTL_FRAMES"]):
                tok = st.tokens.popleft()
                event_id += 1
                ev = HandEvent(
                    event_id=event_id, video=video_key, stem=stem,
                    frame=frame, time_seconds=time_seconds(frame),
                    hand=side, event_type="EXPIRED_HELD",
                    tid=tok["arrived_tid"],
                    point_x=tok["arrived_x"], point_y=tok["arrived_y"],
                    wrist_x=(tok["arrived_wrist"][0] if tok["arrived_wrist"] else None),
                    wrist_y=(tok["arrived_wrist"][1] if tok["arrived_wrist"] else None),
                    dist=tok["arrived_dist"], slope=tok["arrived_slope"],
                    pool_depth=st.depth(), pre_depth=st.depth() + 1,
                    identity_ambiguous=True,
                    notes=(f"token {tok['id']} aged out (TTL="
                           f"{V2_THRESHOLDS['TOK_TTL_FRAMES']}f); "
                           f"from {tok['arrived_tid']}@f{tok['arrived_frame']}"),
                )
                emit(ev)
                filtered_stats["EXPIRED_HELD"] += 1

        # ------- THROW candidates -------
        # Group by side for successor_conflict counting.
        throw_by_side: dict[str, list[tuple[int, dict]]] = defaultdict(list)
        for tid, info in throw_candidates.get(frame, []):
            if info["side"] is None:
                continue
            throw_by_side[info["side"]].append((tid, info))
        for side, cands in throw_by_side.items():
            if len(cands) > 1:
                successor_conflict += 1
            st = state[side]
            for tid, info in cands:
                pre_depth = st.depth()

                # ---- THROW STRICTNESS: ball must leave reach within N frames
                if not throw_leaves_within(
                    tracks[tid], wrists, hand_reach_px,
                    V2_THRESHOLDS["THROW_LEAVE_WINDOW_FRAMES"], side,
                ):
                    event_id += 1
                    ev = HandEvent(
                        event_id=event_id, video=video_key, stem=stem,
                        frame=frame, time_seconds=time_seconds(frame),
                        hand=side, event_type="THROW_NO_LEAVE",
                        tid=tid, point_x=feats[tid].first_x,
                        point_y=feats[tid].first_y,
                        wrist_x=None, wrist_y=None,
                        dist=info["dist"], slope=info["slope"],
                        pool_depth=pre_depth, pre_depth=pre_depth,
                        identity_ambiguous=False,
                        notes=(f"ball did not leave {side} reach within "
                               f"{V2_THRESHOLDS['THROW_LEAVE_WINDOW_FRAMES']}f"),
                    )
                    emit(ev)
                    filtered_stats["THROW_NO_LEAVE"] += 1
                    # NOT consumed from pool; this is not a hand-link.
                    continue

                # ---- WRIST-MOTION GUARD
                wrist_v = wrist_velocity(wrists, frame, side)
                if wrist_v is not None and wrist_v > V2_THRESHOLDS["WRIST_VEL_MAX"]:
                    event_id += 1
                    ev = HandEvent(
                        event_id=event_id, video=video_key, stem=stem,
                        frame=frame, time_seconds=time_seconds(frame),
                        hand=side, event_type="WRIST_MOTION_THROW",
                        tid=tid, point_x=feats[tid].first_x,
                        point_y=feats[tid].first_y,
                        wrist_x=None, wrist_y=None,
                        dist=info["dist"], slope=info["slope"],
                        pool_depth=pre_depth, pre_depth=pre_depth,
                        identity_ambiguous=False,
                        notes=(f"wrist vel {wrist_v:.1f} > "
                               f"{V2_THRESHOLDS['WRIST_VEL_MAX']}"),
                    )
                    emit(ev)
                    filtered_stats["WRIST_MOTION_THROW"] += 1
                    # NOT consumed from pool; this is not a hand-link.
                    continue

                # Throw is a plausible hand-link. Decide what to do.
                if pre_depth == 0:
                    # UNMATCHED_EXIT (hand was empty)
                    event_id += 1
                    ev = HandEvent(
                        event_id=event_id, video=video_key, stem=stem,
                        frame=frame, time_seconds=time_seconds(frame),
                        hand=side, event_type="UNMATCHED_EXIT",
                        tid=tid, point_x=feats[tid].first_x,
                        point_y=feats[tid].first_y,
                        wrist_x=None, wrist_y=None,
                        dist=info["dist"], slope=info["slope"],
                        pool_depth=pre_depth, pre_depth=pre_depth,
                        identity_ambiguous=False,
                        notes="throw-side exit; hand was empty",
                    )
                    emit(ev, "UNMATCHED_EXIT")
                    last_hand_event_frame[side] = frame
                    continue

                # Pop oldest token.
                tok = st.tokens.popleft()
                tok_age = frame - tok["arrived_frame"]
                # ---- STALE-TOKEN check
                if tok_age > V2_THRESHOLDS["STALE_TTL_FRAMES"]:
                    # Re-insert the token (it WAS a real catch; we just
                    # don't trust this throw to match it). Actually we
                    # leave the token popped but mark this as STALE so
                    # the pool shrinks. Then count the throw as
                    # STALE_TOKEN_THROW.
                    event_id += 1
                    ev = HandEvent(
                        event_id=event_id, video=video_key, stem=stem,
                        frame=frame, time_seconds=time_seconds(frame),
                        hand=side, event_type="STALE_TOKEN_THROW",
                        tid=tid, point_x=feats[tid].first_x,
                        point_y=feats[tid].first_y,
                        wrist_x=(tok["arrived_wrist"][0] if tok["arrived_wrist"] else None),
                        wrist_y=(tok["arrived_wrist"][1] if tok["arrived_wrist"] else None),
                        dist=info["dist"], slope=info["slope"],
                        pool_depth=st.depth(), pre_depth=pre_depth,
                        identity_ambiguous=True,
                        notes=(f"token {tok['id']} age {tok_age}f > "
                               f"{V2_THRESHOLDS['STALE_TTL_FRAMES']}f; "
                               f"from {tok['arrived_tid']}@f{tok['arrived_frame']}"),
                    )
                    emit(ev)
                    filtered_stats["STALE_TOKEN_THROW"] += 1
                    last_hand_event_frame[side] = frame
                    continue

                ambig = pre_depth > 1
                et = "AMBIGUOUS_POOL_EXIT" if ambig else "EXIT"
                event_id += 1
                ev = HandEvent(
                    event_id=event_id, video=video_key, stem=stem,
                    frame=frame, time_seconds=time_seconds(frame),
                    hand=side, event_type=et,
                    tid=tid, point_x=feats[tid].first_x,
                    point_y=feats[tid].first_y,
                    wrist_x=(tok["arrived_wrist"][0] if tok["arrived_wrist"] else None),
                    wrist_y=(tok["arrived_wrist"][1] if tok["arrived_wrist"] else None),
                    dist=info["dist"], slope=info["slope"],
                    pool_depth=st.depth(), pre_depth=pre_depth,
                    identity_ambiguous=ambig,
                    notes=f"consumed token {tok['id']} from {tok['arrived_tid']}",
                )
                emit(ev, et, ambiguous=ambig)
                hand_links.append({
                    "video": video_key, "stem": stem,
                    "from_tid": tok["arrived_tid"],
                    "to_tid": tid, "hand": side,
                    "from_frame": tok["arrived_frame"],
                    "to_frame": frame,
                    "from_dist": tok["arrived_dist"],
                    "to_dist": info["dist"],
                    "from_slope": tok["arrived_slope"],
                    "to_slope": info["slope"],
                    "identity_ambiguous": ambig,
                    "kind": et,
                    "tok_age_frames": tok_age,
                })
                last_hand_event_frame[side] = frame

        # ------- CATCH candidates -------
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
                # ---- CATCH CONTEXT
                ctx_ok = (
                    frame - last_hand_event_frame[side]
                    <= V2_THRESHOLDS["CATCH_CONTEXT_FRAMES"]
                )
                # context is satisfied automatically for the FIRST event
                # in the video (last_hand_event_frame was initialized to
                # -10000) by simply emitting a normal ENTRY but flagging
                # the lack of context in notes. We use a separate
                # UNCONTEXTED_ENTRY event type so we can count and
                # filter.
                if not ctx_ok:
                    event_id += 1
                    wr = wrists.get(frame)
                    wrist_xy = (getattr(wr, side) if wr is not None else None)
                    ev = HandEvent(
                        event_id=event_id, video=video_key, stem=stem,
                        frame=frame, time_seconds=time_seconds(frame),
                        hand=side, event_type="UNCONTEXTED_ENTRY",
                        tid=tid, point_x=feats[tid].last_x,
                        point_y=feats[tid].last_y,
                        wrist_x=(wrist_xy[0] if wrist_xy else None),
                        wrist_y=(wrist_xy[1] if wrist_xy else None),
                        dist=info["dist"], slope=info["slope"],
                        pool_depth=st.depth(), pre_depth=pre_depth,
                        identity_ambiguous=False,
                        notes=(f"no hand event on {side} in last "
                               f"{V2_THRESHOLDS['CATCH_CONTEXT_FRAMES']}f; "
                               f"likely a detection dropout"),
                    )
                    emit(ev)
                    filtered_stats["UNCONTEXTED_ENTRY"] += 1
                    # We DO add a token so the algorithm still tracks
                    # the catch, but we mark the event as uncontexted
                    # so the visual inspector can verify.
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
                    last_hand_event_frame[side] = frame
                    continue

                wr = wrists.get(frame)
                wrist_xy = (getattr(wr, side) if wr is not None else None)
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
                    tid=tid, point_x=feats[tid].last_x,
                    point_y=feats[tid].last_y,
                    wrist_x=(wrist_xy[0] if wrist_xy else None),
                    wrist_y=(wrist_xy[1] if wrist_xy else None),
                    dist=info["dist"], slope=info["slope"],
                    pool_depth=st.depth(), pre_depth=pre_depth,
                    identity_ambiguous=(st.depth() > 1),
                    notes=f"token {tok['id']} created",
                )
                emit(ev, "ENTRY")
                last_hand_event_frame[side] = frame

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

    # End of video: any remaining tokens are UNRESOLVED_HELD_OR_LOST
    for side in ("left", "right"):
        st = state[side]
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
            emit(ev, "UNRESOLVED_HELD_OR_LOST")
            st.tokens.popleft()

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
        "filtered_stats": filtered_stats,
        "predecessor_conflict": predecessor_conflict,
        "successor_conflict": successor_conflict,
        "impossible_states": impossible_states,
        "multi_token_ambiguous": multi_token_ambiguous,
        "image_height": image_height,
        "hand_reach_px": hand_reach_px,
    }


# -----------------------------------------------------------------------
# v2 writer — extends v1's writer to add tok_age and filtered stats.
# -----------------------------------------------------------------------
def write_outputs_v2(all_runs: list[dict]) -> dict:
    H1_DATA.mkdir(parents=True, exist_ok=True)
    H1_REPORTS.mkdir(parents=True, exist_ok=True)

    # hand_events.csv (same fields as v1; v2 just adds more event types)
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

    # hand_links.csv (only v2 surviving hand-links; includes tok_age_frames)
    with (H1_DATA / "hand_links.csv").open("w", newline="") as fh:
        fields = [
            "video", "stem", "from_tid", "to_tid", "hand",
            "from_frame", "to_frame",
            "from_dist", "to_dist", "from_slope", "to_slope",
            "identity_ambiguous", "kind", "tok_age_frames",
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
                    "tok_age_frames": link.get("tok_age_frames", ""),
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

    summary = {
        "v2_thresholds": V2_THRESHOLDS,
        "v1_thresholds": V1_THRESHOLDS,
        "image_height": DEFAULT_IMAGE_HEIGHT,
        "hand_reach_px": DEFAULT_IMAGE_HEIGHT * V1_THRESHOLDS["HAND_REACH_PX_RATIO"],
        "videos": {},
    }
    for run in all_runs:
        reviewed = load_reviewed_pairs(run["video_key"])
        ev = evaluate_against_labels(run, run["video_key"], reviewed)
        summary["videos"][run["stem"]] = {
            "video_key": run["video_key"],
            "event_counts": run["counters"],
            "filtered_counts": run["filtered_stats"],
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


# -----------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------
def main() -> None:
    H1_DATA.mkdir(parents=True, exist_ok=True)
    H1_REPORTS.mkdir(parents=True, exist_ok=True)
    all_runs: list[dict] = []
    for stem, video_key in STEMS.items():
        print(f"[{stem}] running H1 v2 hand-pool state machine...")
        run = run_for_stem_v2(stem, video_key)
        print(f"  events:     {run['counters']}")
        print(f"  filtered:   {run['filtered_stats']}")
        print(f"  links:      {len(run['links'])}")
        print(f"  pred_conflicts: {run['predecessor_conflict']}")
        print(f"  succ_conflicts: {run['successor_conflict']}")
        print(f"  impossible states: {run['impossible_states']}")
        all_runs.append(run)

    summary = write_outputs_v2(all_runs)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
