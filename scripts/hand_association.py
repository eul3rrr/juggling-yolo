"""Hand Association Engine v1.

Reusable state/decision layer for the future hand-aware stitcher.

Scope (Hand System v1B+ spec):
    * Decide when a broken track plausibly entered a hand.
    * Decide when a newly born track plausibly exited a hand.
    * Decide which anatomical hand is involved.
    * Store unresolved ball identities in a small per-hand FIFO.
    * NEVER mutate final chain identities or accepted stitch output.

The motion model:

    AIRBORNE       = no credible hand interaction hypothesis.
    HAND_NEAR      = ball physically close to a hand; not yet a
                     possession/identity claim.
    HAND_ASSOCIATED = credible hand mediation. Created only at an
                      actual track boundary (track END or START);
                      continuous same-ID hand interactions are
                      deliberately left alone (see scope rule).

Proximity bands are derived from the ball-to-wrist distance
normalized by inter-shoulder width, with raw-pixel fallback when
no body scale is available.  The three bands are documented in
:data:`HandAssociationConfig`.  Motion evidence must be sign-correct:
an ENTRY requires the ball to be moving TOWARD the hand (negative
distance slope or negative radial relative velocity); an EXIT
requires it to be moving AWAY (positive slope or positive radial).

The 5-second safety expiry is a queue-cleanup safeguard, never a
scoring penalty.
"""
from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

# Reuse the v1A math. We do not re-implement any of it.
_HF_PATH = Path(__file__).resolve().parent / "hand_features.py"
_HO_PATH = Path(__file__).resolve().parent / "hand_overlay.py"


def _import_hf_ho():
    """Import hand_features and hand_overlay by file path so the
    engine can be loaded without `scripts/` on sys.path."""
    import importlib.util
    out = {}
    for name, path in (("hand_features", _HF_PATH), ("hand_overlay", _HO_PATH)):
        spec = importlib.util.spec_from_file_location(name, str(path))
        assert spec is not None and spec.loader is not None
        mod = importlib.util.module_from_spec(spec)
        sys.modules.setdefault(name, mod)
        spec.loader.exec_module(mod)
        out[name] = mod
    return out["hand_features"], out["hand_overlay"]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class HandAssociationConfig:
    """Centralised, conservative defaults for the hand-association engine."""

    # --- proximity bands (normalized + raw fallback) ---------------------
    strong_max_normalized: float = 0.35
    strong_max_raw_px: float = 60.0
    possible_max_normalized: float = 0.7
    possible_max_raw_px: float = 130.0

    # --- motion-evidence requirements (POSSIBLE band) --------------------
    # Sign convention: slope < 0 means CLOSING (toward the hand).
    # For ENTRY we need closing; for EXIT we need separating.
    # Mirrors the v1B reviewer correction: n_points < 3 -> INSUFFICIENT.
    min_points_for_slope: int = 3
    min_abs_slope_px_per_frame: float = 0.5
    min_abs_radial_px_per_frame: float = 0.5

    # --- exit-side motion threshold (slightly looser) --------------------
    # A freshly-born track has only a few points; we accept a smaller
    # magnitude as supporting evidence for an exit.
    exit_min_abs_slope_px_per_frame: float = 0.25

    # --- post-contact / hand-impulse END case -----------------------------
    # A track break is admissible as hand-mediated (case C) when the
    # recent observation window contains a STRONG-close minimum to
    # the same hand within ``post_contact_recent_frames`` FRAMES of
    # the endpoint AND the endpoint itself is still in a POSSIBLE
    # hand region AND the ball is not actively separating from the
    # hand at the endpoint.  The "not actively separating" check
    # rejects "ball was close 4 frames ago, now it's flying away"
    # cases that the endpoint-in-reach + min-in-window checks
    # alone would mis-classify.
    post_contact_min_normalized: float = 0.45
    post_contact_min_raw_px: float = 80.0
    post_contact_endpoint_max_normalized: float = 0.7
    post_contact_endpoint_max_raw_px: float = 130.0
    post_contact_recent_frames: int = 4
    # If the ball is moving AWAY from the hand faster than this
    # many shoulder-widths per second in the local endpoint window,
    # it is not credibly in contact.  The default is 0.2 sw/s
    # which is the boundary between "thrown" and "still in hand".
    post_contact_max_separating_sw_per_sec: float = 0.2

    # --- hold-time safety expiry -----------------------------------------
    # The 5-second expiry was a queue-cleanup safety for the original
    # dry-run pipeline.  For the integration (where bridges are
    # matched END->START in one pass), the gap between END and
    # START must be physically plausible: a hand-mediated identity
    # break is typically < 1 second.  A gap > 1.5 seconds is more
    # likely tracker fragmentation than a hand event.
    safety_expiry_seconds: float = 1.5

    # --- body scale / pose thresholds ------------------------------------
    body_scale_min_px: float = 5.0
    confidence_threshold: float = 0.25

    # --- detection --------------------------------------------------------
    n_window: int = 5  # points used for the per-end/per-start window

    # --- side-pick tie-breaker ------------------------------------------
    # When both LEFT and RIGHT qualify for an ENTRY or EXIT, the
    # smaller normalized distance wins; if the difference is below
    # this many shoulder-widths, the entry is recorded as ambiguous
    # (kept on a single FIFO queue, not duplicated per hand).
    side_tie_normalized: float = 0.15


# ---------------------------------------------------------------------------
# Loaded data
# ---------------------------------------------------------------------------

@dataclass
class TrackletPoint:
    frame: int
    center_x: float
    center_y: float
    observed: int = 1


@dataclass
class PersonHandRow:
    """A single pose row (per frame, per person) with smoothed
    keypoints and confidence values preserved."""
    frame: int
    person_index: int
    person_confidence: float | None
    left_wrist: tuple[float, float] | None
    left_wrist_conf: float | None
    right_wrist: tuple[float, float] | None
    right_wrist_conf: float | None
    body_scale: float | None


def _load_tracklets(path: Path) -> dict[int, list[TrackletPoint]]:
    out: dict[int, list[TrackletPoint]] = defaultdict(list)
    if not path.is_file():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("observed") or "1") != "1":
                continue
            try:
                tid = int(row["track_id"])
            except (KeyError, ValueError):
                continue
            try:
                fr = int(row["frame"])
                cx = float(row["center_x"])
                cy = float(row["center_y"])
            except (KeyError, ValueError, ValueError):
                continue
            out[tid].append(TrackletPoint(frame=fr, center_x=cx, center_y=cy))
    for tid in out:
        out[tid].sort(key=lambda p: p.frame)
    return out


def _load_chain_mapping(path: Path) -> dict[int, int]:
    if not path.is_file():
        return {}
    out: dict[int, int] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                out[int(row["track_id"])] = int(row["chain_id"])
            except (KeyError, ValueError):
                continue
    return out


def _load_chains(tracklets: dict[int, list[TrackletPoint]],
                 chain_mapping: dict[int, int]
                 ) -> dict[int, list[TrackletPoint]]:
    out: dict[int, list[TrackletPoint]] = defaultdict(list)
    for tid, pts in tracklets.items():
        chain_id = chain_mapping.get(tid)
        if chain_id is None:
            continue
        out[chain_id].extend(pts)
    for cid in out:
        out[cid].sort(key=lambda p: (p.frame, p.center_x, p.center_y))
    return out


def _parse_hand_csv(path: Path, confidence_threshold: float
                    ) -> tuple[dict[int, list[PersonHandRow]], int]:
    """Parse the hands CSV into ``{frame: [PersonHandRow, ...]}`` and
    return the number of frames that contain more than one pose row
    (so the caller can report the multi-pose rate)."""
    if not path.is_file():
        return {}, 0
    by_frame: dict[int, list[PersonHandRow]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                fr = int(float(row.get("frame", "nan")))
            except (KeyError, ValueError):
                continue
            try:
                person_index = int(float(row.get("person_index", "0")))
                person_conf = _safe_float(row.get("person_confidence"))
                body_scale = _safe_float(row.get("body_scale_shoulder_px"))
            except (KeyError, ValueError):
                continue
            def _kp(x: str, y: str, conf: str,
                    use_smooth: bool = False):
                xs = x + ("_smooth" if use_smooth else "")
                ys = y + ("_smooth" if use_smooth else "")
                cs = conf
                # Re-read the row, returning (xy, confidence) so we
                # preserve the actual confidence value rather than
                # just the binary presence.
                x_v = _safe_float(row.get(xs))
                y_v = _safe_float(row.get(ys))
                c_v = _safe_float(row.get(cs))
                if (x_v is None or y_v is None or c_v is None
                        or c_v < confidence_threshold):
                    return None, None
                return (x_v, y_v), c_v

            left_wrist, conf_left_wrist = _kp(
                "left_wrist_x", "left_wrist_y", "left_wrist_confidence", True)
            right_wrist, conf_right_wrist = _kp(
                "right_wrist_x", "right_wrist_y", "right_wrist_confidence", True)
            left_shoulder = _kp("left_shoulder_x", "left_shoulder_y",
                                "left_shoulder_confidence", True)[0]
            right_shoulder = _kp("right_shoulder_x", "right_shoulder_y",
                                 "right_shoulder_confidence", True)[0]
            # Per-frame inter-wrist distance: a robust body-scale
            # proxy when the shoulder width is not available.
            if left_wrist is not None and right_wrist is not None:
                inter_wrist = math.hypot(
                    left_wrist[0] - right_wrist[0],
                    left_wrist[1] - right_wrist[1],
                )
                if body_scale is None or body_scale < 5.0:
                    body_scale = inter_wrist if inter_wrist >= 5.0 else None
            elif body_scale is not None and body_scale < 5.0:
                body_scale = None
            # Last-resort fallback when shoulders are visible but
            # wrists are not: use shoulder width.
            if body_scale is None and left_shoulder and right_shoulder:
                sw = math.hypot(left_shoulder[0] - right_shoulder[0],
                                left_shoulder[1] - right_shoulder[1])
                if sw >= 5.0:
                    body_scale = sw
            by_frame[fr].append(PersonHandRow(
                frame=fr, person_index=person_index,
                person_confidence=person_conf,
                left_wrist=left_wrist,
                left_wrist_conf=conf_left_wrist,
                right_wrist=right_wrist,
                right_wrist_conf=conf_right_wrist,
                body_scale=body_scale,
            ))
    multi_pose_frames = sum(1 for rows in by_frame.values() if len(rows) > 1)
    return by_frame, multi_pose_frames


def _select_dominant_person(rows: list[PersonHandRow]) -> PersonHandRow | None:
    """Pick a single PersonHandRow for a frame using a stable,
    deterministic policy that does not assume screen-left/right.

    The chosen policy: prefer the row whose ``person_index`` is 0
    if it is the only one or if it has the highest person
    confidence; otherwise pick the row with the highest person
    confidence; if confidences are equal, take the lowest
    person_index.  This is continuity-friendly: a single juggler
    on screen who briefly spawns a low-confidence second detection
    does not have their wrist flipped to a phantom.
    """
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0]
    person_zero = next((r for r in rows if r.person_index == 0), None)
    if person_zero is not None:
        # The juggler is typically person_index 0.  Adopting the
        # later-arriving extra row would overwrite a valid juggler
        # with a low-confidence phantom.  Take person 0 unless it
        # is exceptionally weak and the alternative is much stronger.
        best = max(rows, key=lambda r: (
            (r.person_confidence or -1.0),
            -r.person_index,
        ))
        if person_zero.person_confidence is not None:
            if (best.person_confidence is not None
                    and best.person_confidence
                        > person_zero.person_confidence + 0.2):
                return best
            return person_zero
        return person_zero
    # No person_index=0; fall back to highest confidence.
    return max(rows, key=lambda r: (
        (r.person_confidence or -1.0),
        -r.person_index,
    ))


def _load_hands_by_frame(path: Path, confidence_threshold: float = 0.25
                         ) -> dict[int, dict]:
    """Per-frame hands keyed by anatomical side.

    Returns ``{frame: {"left": (x, y) | None, "right": (x, y) | None,
                       "body_scale": float | None,
                       "left_confidence": float | None,
                       "right_confidence": float | None}}``.

    Wrist confidence values are preserved (per-side) so consumers
    can inspect pose certainty.  When multiple pose rows exist for
    a single frame, the dominant-person selection policy (see
    :func:`_select_dominant_person`) is applied.
    """
    raw, _ = _parse_hand_csv(path, confidence_threshold)
    out: dict[int, dict] = {}
    for fr, rows in raw.items():
        chosen = _select_dominant_person(rows)
        if chosen is None:
            continue
        out[fr] = {
            "left": chosen.left_wrist,
            "right": chosen.right_wrist,
            "body_scale": chosen.body_scale,
            "left_confidence": chosen.left_wrist_conf,
            "right_confidence": chosen.right_wrist_conf,
            "person_index": chosen.person_index,
        }
    return out


# ---------------------------------------------------------------------------
# Per-event evidence
# ---------------------------------------------------------------------------

@dataclass
class HandEvidence:
    side: str
    distance_px: float | None
    distance_normalized: float | None
    min_distance_px: float | None
    min_distance_normalized: float | None
    slope_px_per_frame: float | None
    radial_px_per_frame: float | None
    n_points: int
    hand_confidence: float | None
    motion_sign: str


def _safe_float(v) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f):
        return None
    return f


def _xy(row: dict, x_key: str, y_key: str, conf_key: str,
        threshold: float) -> tuple[float, float] | None:
    x = _safe_float(row.get(x_key))
    y = _safe_float(row.get(y_key))
    c = _safe_float(row.get(conf_key))
    if x is None or y is None or c is None:
        return None
    if c < threshold:
        return None
    return (x, y)


def _hand_distance_window(ball_points: Sequence[TrackletPoint],
                         synced: list[tuple[int, tuple[float, float]]],
                         body_scale: float | None,
                         hand_features,
                         anchor_index: int = -1) -> HandEvidence:
    """Compute the evidence bundle for one (event-side, anatomical
    hand) using a SYNCHRONIZED list of ``(ball_frame, hand_xy)``
    pairs. The caller is responsible for producing ``synced`` from
    frames where both the observed ball and the requested wrist are
    usable. All distance, slope, and radial calculations use the
    same synchronized subset.
    """
    if not synced or not ball_points:
        return HandEvidence(
            side="?", distance_px=None, distance_normalized=None,
            min_distance_px=None, min_distance_normalized=None,
            slope_px_per_frame=None, radial_px_per_frame=None,
            n_points=0, hand_confidence=None, motion_sign="insufficient",
        )
    synced_frames = [s[0] for s in synced]
    synced_hand_xy = [s[1] for s in synced]
    # Pull ball points that match the synchronized frames, in order.
    ball_by_frame = {bp.frame: bp for bp in ball_points}
    synced_ball_pts = [ball_by_frame[f] for f in synced_frames
                       if f in ball_by_frame]
    n_pts = len(synced_ball_pts)
    if n_pts == 0:
        return HandEvidence(
            side="?", distance_px=None, distance_normalized=None,
            min_distance_px=None, min_distance_normalized=None,
            slope_px_per_frame=None, radial_px_per_frame=None,
            n_points=0, hand_confidence=None, motion_sign="insufficient",
        )
    ball_xy = np.asarray([(p.center_x, p.center_y) for p in synced_ball_pts],
                         dtype=float)
    hxy = np.asarray(synced_hand_xy, dtype=float)
    distances = np.linalg.norm(ball_xy - hxy, axis=1)
    min_idx = int(np.argmin(distances))
    min_px = float(distances[min_idx])
    min_norm = (min_px / body_scale
                if (body_scale and body_scale > 0) else None)
    if 0 <= anchor_index < n_pts:
        anchor_px = float(distances[anchor_index])
    else:
        anchor_px = float(distances[anchor_index])
    anchor_norm = (anchor_px / body_scale
                   if (body_scale and body_scale > 0) else None)
    slope = None
    if n_pts >= 2:
        slope_pt = hand_features.local_slope_detail(
            synced_frames, [float(d) for d in distances], n_points=n_pts)
        slope = slope_pt.slope
    radial = None
    if n_pts >= 2:
        radial = hand_features.relative_radial_velocity_series(
            ball_xy, hxy,
            np.asarray(synced_frames, dtype=float),
            np.asarray(synced_frames, dtype=float),
            min_window_pts=2,
        )
    if slope is None or not math.isfinite(slope) or n_pts < 3:
        motion_sign = "insufficient"
    elif slope < -0.5:
        motion_sign = "closing"
    elif slope > 0.5:
        motion_sign = "separating"
    else:
        motion_sign = "stable"
    return HandEvidence(
        side="?",
        distance_px=anchor_px,
        distance_normalized=anchor_norm,
        min_distance_px=min_px,
        min_distance_normalized=min_norm,
        slope_px_per_frame=slope,
        radial_px_per_frame=radial,
        n_points=n_pts,
        hand_confidence=None,
        motion_sign=motion_sign,
    )


# ---------------------------------------------------------------------------
# Per-side assessment
# ---------------------------------------------------------------------------

@dataclass
class HandSideAssessment:
    side: str
    band: str                 # "STRONG" | "POSSIBLE" | "FAR" | "MISSING"
    evidence: HandEvidence
    # Per-event-type motion-support signals.  These are kept
    # SEPARATE from the proximity band so "close to the hand" and
    # "moving in the right direction" are not conflated.  A band of
    # STRONG does not require any motion evidence; a band of
    # POSSIBLE does.
    entry_support: bool = False
    exit_support: bool = False
    # True when this side qualifies under the post-contact / hand-
    # impulse path (case C).  Set only on ENTRY evaluations.
    post_contact: bool = False


def _classify_band(evidence: HandEvidence, cfg: HandAssociationConfig
                  ) -> str:
    """Classify proximity into STRONG / POSSIBLE / FAR / MISSING.

    Pure geometry, no motion.  When a trustworthy body scale is
    available, the normalized distance is primary; raw-pixel is
    only a fallback when no body scale is recorded.
    """
    if evidence.n_points == 0:
        return "MISSING"
    d = evidence.distance_px
    nd = evidence.distance_normalized
    if nd is not None and math.isfinite(nd):
        if nd <= cfg.strong_max_normalized:
            return "STRONG"
        if nd <= cfg.possible_max_normalized:
            return "POSSIBLE"
        return "FAR"
    if d is not None and d <= cfg.strong_max_raw_px:
        return "STRONG"
    if d is not None and d <= cfg.possible_max_raw_px:
        return "POSSIBLE"
    return "FAR"


def _entry_motion_support(evidence: HandEvidence, cfg: HandAssociationConfig
                          ) -> bool:
    """Does the motion evidence support an ENTRY for this side?

    Sign convention: positive distance slope means the ball is
    moving AWAY (separating); negative means TOWARD (closing).  An
    ENTRY needs the ball to be moving TOWARD the hand.  The radial
    relative velocity has the same sign convention.  STRONG
    proximity does not require motion (set in the caller); this
    helper is consulted only when the band is POSSIBLE.
    """
    if (evidence.n_points >= cfg.min_points_for_slope
            and evidence.slope_px_per_frame is not None
            and evidence.slope_px_per_frame
                < -cfg.min_abs_slope_px_per_frame):
        return True
    if (evidence.radial_px_per_frame is not None
            and evidence.radial_px_per_frame
                < -cfg.min_abs_radial_px_per_frame):
        return True
    return False


def _exit_motion_support(evidence: HandEvidence, cfg: HandAssociationConfig
                         ) -> bool:
    """Does the motion evidence support an EXIT for this side?

    An EXIT needs the ball to be moving AWAY from the hand.  A
    freshly-born track with too few points for a slope is accepted
    only when the raw distance is small enough to imply the ball
    has just left the hand.
    """
    slope = evidence.slope_px_per_frame
    if (evidence.n_points >= cfg.min_points_for_slope
            and slope is not None
            and slope > cfg.exit_min_abs_slope_px_per_frame):
        return True
    # n<3 short-window case: accept when raw distance is within the
    # strong-band bound.  This covers the 10 -> 14 type cases where
    # the target track is born within an outstretched palm.
    if (evidence.n_points < cfg.min_points_for_slope
            and evidence.distance_px is not None
            and evidence.distance_px <= cfg.strong_max_raw_px):
        return True
    if (evidence.radial_px_per_frame is not None
            and evidence.radial_px_per_frame
                > cfg.min_abs_radial_px_per_frame):
        return True
    return False


def _min_was_recent(hand_xy_seq: list[tuple[int, tuple[float, float]]],
                    ball_points: Sequence[TrackletPoint],
                    evidence: HandEvidence,
                    cfg: HandAssociationConfig) -> bool:
    """Was the minimum-distance sample within
    ``cfg.post_contact_recent_frames`` FRAMES of the endpoint
    frame?  We use frame distance (not sample count) because the
    hand CSV may have missing hand observations, which would
    otherwise make the recency check spuriously fail.
    """
    if evidence.n_points < 2:
        return False
    if not hand_xy_seq:
        return False
    ball_by_frame = {bp.frame: bp for bp in ball_points}
    frames = [f for f, _ in hand_xy_seq]
    # Build a per-frame distance series using the same synchronized
    # subset.
    import numpy as _np
    ball_xy = _np.asarray([(ball_by_frame[f].center_x,
                            ball_by_frame[f].center_y)
                           for f in frames if f in ball_by_frame], dtype=float)
    hxy = _np.asarray([xy for _, xy in hand_xy_seq], dtype=float)
    if len(ball_xy) != len(hxy):
        return False
    dists = _np.linalg.norm(ball_xy - hxy, axis=1)
    if len(dists) == 0:
        return False
    min_idx = int(_np.argmin(dists))
    endpoint_frame = frames[-1]
    min_frame = frames[min_idx]
    return (endpoint_frame - min_frame) <= cfg.post_contact_recent_frames


def _recent_strong_minimum(evidence: HandEvidence, cfg: HandAssociationConfig
                            ) -> bool:
    """Did the synchronized window have a STRONG-close minimum to
    this hand?  Uses ``min_distance_normalized`` / ``min_distance_px``
    so the check reflects the *closest* observed proximity, not
    the anchor frame's current distance.
    """
    nd = evidence.min_distance_normalized
    d = evidence.min_distance_px
    if nd is not None and math.isfinite(nd):
        return nd <= cfg.post_contact_min_normalized
    return d is not None and d <= cfg.post_contact_min_raw_px


def _endpoint_still_in_reach(evidence: HandEvidence, cfg: HandAssociationConfig
                            ) -> bool:
    """Is the endpoint still inside a physically plausible
    hand-interaction region?  Used by case C to rule out
    "recently-touched-then-flew-far-away" continuations."""
    nd = evidence.distance_normalized
    d = evidence.distance_px
    if nd is not None and math.isfinite(nd):
        return nd <= cfg.post_contact_endpoint_max_normalized
    return d is not None and d <= cfg.post_contact_endpoint_max_raw_px


def _endpoint_not_separating(evidence: HandEvidence,
                             ball_points: Sequence[TrackletPoint],
                             cfg: HandAssociationConfig,
                             fps: float) -> bool:
    """Is the ball not actively separating from the hand at the
    endpoint?  Computed from the local endpoint slope scaled to
    shoulder-widths per second.  Used by case C to rule out
    "ball was close 4 frames ago, now it's flying away" cases.
    Returns True (admit) when the slope is below the configured
    per-shoulder-width per-second threshold OR when the slope
    cannot be computed (n<3).
    """
    if evidence.n_points < 3 or evidence.slope_px_per_frame is None:
        # No trustworthy slope -> don't reject on this basis.
        return True
    # Recover body_scale from evidence: distance_px / distance_normalized.
    body_scale = None
    if (evidence.distance_normalized is not None
            and evidence.distance_normalized > 0):
        body_scale = (evidence.distance_px or 0.0) / evidence.distance_normalized
    if body_scale is None or body_scale <= 0:
        # No body scale -> compare raw slope against the same
        # threshold scaled to per-second (60 fps assumption).
        return (evidence.slope_px_per_frame * fps
                <= cfg.post_contact_endpoint_max_raw_px)
    sw_per_sec = (evidence.slope_px_per_frame / body_scale) * fps
    return sw_per_sec <= cfg.post_contact_max_separating_sw_per_sec


def _assess_side(side: str, ball_points: Sequence[TrackletPoint],
                 hand_xy_seq: list[tuple[int, tuple[float, float]]],
                 body_scale: float | None,
                 hand_features, cfg: HandAssociationConfig,
                 anchor_index: int = -1,
                 hand_confidence: float | None = None,
                 fps: float = 60.0) -> HandSideAssessment:
    ev = _hand_distance_window(ball_points, hand_xy_seq, body_scale,
                              hand_features, anchor_index=anchor_index)
    ev.side = side
    ev.hand_confidence = hand_confidence
    band = _classify_band(ev, cfg)
    # STRONG always admits; POSSIBLE requires sign-correct motion.
    entry_support = (band == "STRONG") or (
        band == "POSSIBLE" and _entry_motion_support(ev, cfg))
    exit_support = (band == "STRONG") or (
        band == "POSSIBLE" and _exit_motion_support(ev, cfg))
    # Case C: post-contact / hand-impulse END path.  Admit a band
    # of POSSIBLE when the endpoint is still in reach AND the
    # synchronized window (the n_window of recent observations)
    # has a STRONG-close minimum.  The recent-window check is
    # implicitly satisfied by the n_window length: the min must
    # occur WITHIN the n_window, and the endpoint (also within
    # the n_window) is still in POSSIBLE.  Together those two
    # rules prevent the two failure modes called out in the spec:
    #   - a close fly-by followed by a distant END: the endpoint
    #     would be FAR, so endpoint_in_reach is False.
    #   - a generic close fly-by: the endpoint is FAR, same reason.
    # The n_window is the local endpoint window; recency within
    # that window is implied by both the min and the endpoint
    # being in the same window.
    post_contact = False
    if band == "POSSIBLE" and not entry_support:
        # Recency: the minimum must have occurred within
        # post_contact_recent_frames FRAMES of the endpoint.
        # The endpoint must still be in reach.  The not-separating
        # check was tried here but it was too strict: a successful
        # hand event is *exactly* when the ball is being thrown,
        # so the slope at the END is naturally large and positive.
        # The endpoint-in-reach bound is sufficient: if the ball
        # is genuinely flying away (200+ px), the endpoint is FAR
        # and the rule rejects.  If the endpoint is in POSSIBLE
        # (<= 130 px) and the recent min was STRONG, we admit.
        if (_endpoint_still_in_reach(ev, cfg)
                and _recent_strong_minimum(ev, cfg)
                and _min_was_recent(hand_xy_seq, ball_points, ev, cfg)):
            post_contact = True
            entry_support = True
    return HandSideAssessment(side=side, band=band, evidence=ev,
                              entry_support=entry_support,
                              exit_support=exit_support,
                              post_contact=post_contact)


# ---------------------------------------------------------------------------
# Body-scale helpers
# ---------------------------------------------------------------------------

def _latest_body_scale(recent: Sequence[TrackletPoint],
                       hand_xy_by_frame: dict) -> float | None:
    """Return the most recent trustworthy body scale recorded in
    ``hand_xy_by_frame`` for any frame in ``recent``.

    The hand CSV records ``body_scale_shoulder_px`` per frame. When
    that is missing, fall back to the per-frame inter-wrist
    distance of the most recent frame in the window.  We never
    cross frames (no cross-frame pairwise max of unrelated wrist
    positions) because that would mix frames and produce a junk
    scale when the juggler is moving.
    """
    for bp in reversed(recent):
        row = hand_xy_by_frame.get(bp.frame)
        if not row:
            continue
        bs = row.get("body_scale")
        if bs is not None and math.isfinite(bs) and bs >= 5.0:
            return bs
        l = row.get("left")
        r = row.get("right")
        if l is not None and r is not None:
            d = math.hypot(l[0] - r[0], l[1] - r[1])
            if d >= 5.0:
                return d
    return None


def _synchronized_samples(ball_points: Sequence[TrackletPoint],
                          hand_xy_by_frame: dict,
                          side: str,
                          window: int
                          ) -> tuple[list[TrackletPoint],
                                    list[tuple[int, tuple[float, float]]]]:
    """Build a synchronized (ball, hand) sample list by frame.

    Only frames where the ball is observed AND the requested wrist
    is usable are returned.  This guarantees that all downstream
    distance / slope / radial calculations operate on the same
    sample subset.

    The caller is responsible for selecting the appropriate window
    of ball points: ``pts[-window:]`` for END events, ``pts[:window]``
    for START events.  This function does NOT re-slice the points.
    """
    bp_by_frame = {bp.frame: bp for bp in ball_points}
    synced_ball: list[TrackletPoint] = []
    synced_hand: list[tuple[int, tuple[float, float]]] = []
    for bp in ball_points:
        row = hand_xy_by_frame.get(bp.frame)
        if not row:
            continue
        xy = row.get(side)
        if xy is None:
            continue
        synced_ball.append(bp_by_frame[bp.frame])
        synced_hand.append((bp.frame, xy))
    return synced_ball, synced_hand


# ---------------------------------------------------------------------------
# Pending hand entries, queues, and the engine
# ---------------------------------------------------------------------------

@dataclass
class PendingHandEntry:
    source_track_id: int
    side: str
    end_frame: int
    end_time: float
    expires_at_frame: int
    evidence_at_entry: dict
    band_at_entry: str
    queue_entered_frame: int
    n_points: int


@dataclass
class ProposedAssociation:
    source_track_id: int
    target_track_id: int
    hand: str
    exit_frame: int
    exit_time: float
    band: str
    evidence: dict
    queue_pop_side: str


@dataclass
class QueueExpiry:
    source_track_id: int
    side: str
    end_frame: int
    expires_at_frame: int
    reason: str = "safety_expiry"


@dataclass
class HandStateMachine:
    """Per-hand FIFO of pending entries + chronological event log."""

    cfg: HandAssociationConfig
    fps: float
    left_queue: list[PendingHandEntry] = field(default_factory=list)
    right_queue: list[PendingHandEntry] = field(default_factory=list)
    ambiguous_queue: list[PendingHandEntry] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    counts: dict = field(default_factory=lambda: defaultdict(int))

    def _expiry_frame(self, frame: int) -> int:
        return int(round(frame + self.cfg.safety_expiry_seconds * self.fps))

    def _expiry_sweep(self, current_frame: int) -> list[QueueExpiry]:
        expired: list[QueueExpiry] = []
        keep_left: list[PendingHandEntry] = []
        for entry in self.left_queue:
            if current_frame >= entry.expires_at_frame:
                expired.append(QueueExpiry(
                    source_track_id=entry.source_track_id, side="left",
                    end_frame=entry.end_frame,
                    expires_at_frame=entry.expires_at_frame))
            else:
                keep_left.append(entry)
        self.left_queue = keep_left
        keep_right: list[PendingHandEntry] = []
        for entry in self.right_queue:
            if current_frame >= entry.expires_at_frame:
                expired.append(QueueExpiry(
                    source_track_id=entry.source_track_id, side="right",
                    end_frame=entry.end_frame,
                    expires_at_frame=entry.expires_at_frame))
            else:
                keep_right.append(entry)
        self.right_queue = keep_right
        keep_amb: list[PendingHandEntry] = []
        for entry in self.ambiguous_queue:
            if current_frame >= entry.expires_at_frame:
                expired.append(QueueExpiry(
                    source_track_id=entry.source_track_id, side="ambiguous",
                    end_frame=entry.end_frame,
                    expires_at_frame=entry.expires_at_frame))
            else:
                keep_amb.append(entry)
        self.ambiguous_queue = keep_amb
        for e in expired:
            self.counts["queue_expiry"] += 1
            self.events.append({
                "frame": current_frame,
                "time_seconds": current_frame / self.fps if self.fps else 0.0,
                "event_type": "queue_expiry",
                "track_id": e.source_track_id,
                "hand": e.side,
                "expires_at_frame": e.expires_at_frame,
                "reason": e.reason,
            })
        return expired

    def _queue_length(self) -> dict[str, int]:
        return {"left": len(self.left_queue),
                "right": len(self.right_queue),
                "ambiguous": len(self.ambiguous_queue)}

    def _push(self, entry: PendingHandEntry) -> None:
        if entry.side == "left":
            self.left_queue.append(entry)
        elif entry.side == "right":
            self.right_queue.append(entry)
        else:
            self.ambiguous_queue.append(entry)

    def _pop_for_exit(self, side: str) -> PendingHandEntry | None:
        if side == "left" and self.left_queue:
            return self.left_queue.pop(0)
        if side == "right" and self.right_queue:
            return self.right_queue.pop(0)
        if self.ambiguous_queue:
            return self.ambiguous_queue.pop(0)
        return None

    def evaluate_end(self, track_id: int, ball_points: list[TrackletPoint],
                     hand_xy_by_frame: dict,
                     frame_index: int,
                     hand_features) -> str:
        """Evaluate a track END. Returns chosen side or '' for AIRBORNE."""
        if not ball_points:
            return ""
        last_frame = ball_points[-1].frame
        end_time = last_frame / self.fps if self.fps else 0.0
        # END window: last N observed points. The body-scale lookup
        # and the synchronized helper both use ONLY this window so
        # no future-frames body scale can leak in.
        recent_end = ball_points[-self.cfg.n_window:]
        per_frame_scale = _latest_body_scale(recent_end, hand_xy_by_frame)
        synced_left_ball, synced_left = _synchronized_samples(
            recent_end, hand_xy_by_frame, "left", self.cfg.n_window)
        synced_right_ball, synced_right = _synchronized_samples(
            recent_end, hand_xy_by_frame, "right", self.cfg.n_window)
        # Use the right-hand row's confidence for diagnostics if
        # present; the load_hands_by_frame loader stores per-side
        # confidence.
        conf_left = None
        conf_right = None
        row = hand_xy_by_frame.get(last_frame)
        if row:
            conf_left = row.get("left_confidence")
            conf_right = row.get("right_confidence")
        # Anchor for END = last synchronized point.
        anchor_idx_left = len(synced_left_ball) - 1
        anchor_idx_right = len(synced_right_ball) - 1
        left_a = _assess_side("left", synced_left_ball, synced_left,
                              per_frame_scale, hand_features, self.cfg,
                              anchor_index=anchor_idx_left,
                              hand_confidence=conf_left,
                              fps=self.fps)
        right_a = _assess_side("right", synced_right_ball, synced_right,
                               per_frame_scale, hand_features, self.cfg,
                               anchor_index=anchor_idx_right,
                               hand_confidence=conf_right,
                               fps=self.fps)
        ev = {"left": left_a, "right": right_a}
        chosen, side_label, band = _pick_entry_side(ev, self.cfg)
        if chosen == "skip":
            self.counts["airborne_at_end"] += 1
            self.events.append({
                "frame": last_frame, "time_seconds": end_time,
                "event_type": "end_eval", "track_id": track_id,
                "hand": "", "band": _best_band(ev), "decision": "AIRBORNE",
                "left_band": left_a.band, "right_band": right_a.band,
                "left_motion": left_a.evidence.motion_sign,
                "right_motion": right_a.evidence.motion_sign,
                "left_dist_px": left_a.evidence.distance_px,
                "right_dist_px": right_a.evidence.distance_px,
                "left_min_dist_px": left_a.evidence.min_distance_px,
                "right_min_dist_px": right_a.evidence.min_distance_px,
                "left_slope_px_per_frame": left_a.evidence.slope_px_per_frame,
                "right_slope_px_per_frame": right_a.evidence.slope_px_per_frame,
                "left_radial_px_per_frame": left_a.evidence.radial_px_per_frame,
                "right_radial_px_per_frame": right_a.evidence.radial_px_per_frame,
                "queue_before": self._queue_length(),
                "queue_after": self._queue_length(),
            })
            return ""
        self._expiry_sweep(last_frame)
        queue_before = self._queue_length()
        entry = PendingHandEntry(
            source_track_id=track_id, side=side_label,
            end_frame=last_frame, end_time=end_time,
            expires_at_frame=self._expiry_frame(last_frame),
            evidence_at_entry=ev, band_at_entry=band,
            queue_entered_frame=last_frame,
            n_points=max(left_a.evidence.n_points, right_a.evidence.n_points),
        )
        self._push(entry)
        self.counts[f"{side_label}_entry" if side_label in ("left", "right")
                    else "ambiguous_entry"] += 1
        self.events.append({
            "frame": last_frame, "time_seconds": end_time,
            "event_type": "hand_entry", "track_id": track_id,
            "hand": side_label, "band": band,
            "left_band": left_a.band, "right_band": right_a.band,
            "left_motion": left_a.evidence.motion_sign,
            "right_motion": right_a.evidence.motion_sign,
            "left_dist_px": left_a.evidence.distance_px,
            "right_dist_px": right_a.evidence.distance_px,
            "left_min_dist_px": left_a.evidence.min_distance_px,
            "right_min_dist_px": right_a.evidence.min_distance_px,
            "left_slope_px_per_frame": left_a.evidence.slope_px_per_frame,
            "right_slope_px_per_frame": right_a.evidence.slope_px_per_frame,
            "left_radial_px_per_frame": left_a.evidence.radial_px_per_frame,
            "right_radial_px_per_frame": right_a.evidence.radial_px_per_frame,
            "n_points": entry.n_points,
            "queue_before": queue_before, "queue_after": self._queue_length(),
        })
        return side_label

    def evaluate_start(self, track_id: int,
                       ball_points: list[TrackletPoint],
                       hand_xy_by_frame: dict,
                       frame_index: int,
                       hand_features) -> ProposedAssociation | None:
        """Evaluate a track START. Returns the proposed association
        or None for AIRBORNE."""
        if not ball_points:
            return None
        first_frame = ball_points[0].frame
        exit_time = first_frame / self.fps if self.fps else 0.0
        # START window: first N observed points. The body-scale lookup
        # and the synchronized helper both use ONLY this window so
        # no future-frames body scale can leak in.
        recent_start = ball_points[:self.cfg.n_window]
        per_frame_scale = _latest_body_scale(recent_start, hand_xy_by_frame)
        synced_left_ball, synced_left = _synchronized_samples(
            recent_start, hand_xy_by_frame, "left", self.cfg.n_window)
        synced_right_ball, synced_right = _synchronized_samples(
            recent_start, hand_xy_by_frame, "right", self.cfg.n_window)
        conf_left = None
        conf_right = None
        row = hand_xy_by_frame.get(first_frame)
        if row:
            conf_left = row.get("left_confidence")
            conf_right = row.get("right_confidence")
        # Anchor for START = first synchronized point.
        left_a = _assess_side("left", synced_left_ball, synced_left,
                              per_frame_scale, hand_features, self.cfg,
                              anchor_index=0,
                              hand_confidence=conf_left)
        right_a = _assess_side("right", synced_right_ball, synced_right,
                               per_frame_scale, hand_features, self.cfg,
                               anchor_index=0,
                               hand_confidence=conf_right)
        ev = {"left": left_a, "right": right_a}
        self._expiry_sweep(first_frame)
        queue_before = self._queue_length()
        chosen, side_label, band = _pick_exit_side(ev, self.cfg)
        if chosen == "skip":
            self.counts["airborne_at_start"] += 1
            self.events.append({
                "frame": first_frame, "time_seconds": exit_time,
                "event_type": "start_eval", "track_id": track_id,
                "hand": "", "band": _best_band(ev), "decision": "AIRBORNE",
                "left_band": left_a.band, "right_band": right_a.band,
                "left_motion": left_a.evidence.motion_sign,
                "right_motion": right_a.evidence.motion_sign,
                "left_dist_px": left_a.evidence.distance_px,
                "right_dist_px": right_a.evidence.distance_px,
                "queue_before": queue_before, "queue_after": queue_before,
            })
            return None
        popped = self._pop_for_exit(side_label)
        if popped is None:
            self.counts["exit_with_no_entry"] += 1
            self.events.append({
                "frame": first_frame, "time_seconds": exit_time,
                "event_type": "start_eval", "track_id": track_id,
                "hand": side_label, "band": band,
                "left_band": left_a.band, "right_band": right_a.band,
                "left_motion": left_a.evidence.motion_sign,
                "right_motion": right_a.evidence.motion_sign,
                "left_dist_px": left_a.evidence.distance_px,
                "right_dist_px": right_a.evidence.distance_px,
                "queue_before": queue_before, "queue_after": queue_before,
                "note": "credible exit, no queued entry",
            })
            return ProposedAssociation(
                source_track_id=-1, target_track_id=track_id,
                hand=side_label, exit_frame=first_frame, exit_time=exit_time,
                band=band, evidence=ev, queue_pop_side="")
        assoc = ProposedAssociation(
            source_track_id=popped.source_track_id,
            target_track_id=track_id, hand=side_label,
            exit_frame=first_frame, exit_time=exit_time,
            band=band, evidence=ev, queue_pop_side=popped.side)
        self.counts[f"{side_label}_exit" if side_label in ("left", "right")
                    else "ambiguous_exit"] += 1
        if popped.side == side_label:
            self.counts["fifo_match"] += 1
        else:
            self.counts["fifo_cross_side"] += 1
        self.events.append({
            "frame": first_frame, "time_seconds": exit_time,
            "event_type": "hand_exit", "track_id": track_id,
            "source_track_id": popped.source_track_id,
            "hand": side_label, "queue_pop_side": popped.side,
            "band": band,
            "left_band": left_a.band, "right_band": right_a.band,
            "left_motion": left_a.evidence.motion_sign,
            "right_motion": right_a.evidence.motion_sign,
            "left_dist_px": left_a.evidence.distance_px,
            "right_dist_px": right_a.evidence.distance_px,
            "left_min_dist_px": left_a.evidence.min_distance_px,
            "right_min_dist_px": right_a.evidence.min_distance_px,
            "left_slope_px_per_frame": left_a.evidence.slope_px_per_frame,
            "right_slope_px_per_frame": right_a.evidence.slope_px_per_frame,
            "left_radial_px_per_frame": left_a.evidence.radial_px_per_frame,
            "right_radial_px_per_frame": right_a.evidence.radial_px_per_frame,
            "queue_before": queue_before, "queue_after": self._queue_length(),
        })
        return assoc


def _best_band(ev: dict) -> str:
    order = {"STRONG": 0, "POSSIBLE": 1, "MISSING": 2, "FAR": 3}
    return min(((a.band, order.get(a.band, 9)) for a in ev.values()),
              key=lambda x: x[1])[0]


def _pick_entry_side(ev: dict, cfg: HandAssociationConfig
                    ) -> tuple[str, str, str]:
    """Choose a side (or ambiguous) for an ENTRY event.

    Sign-aware: when classifying POSSIBLE with supporting motion, the
    motion must be TOWARD the hand (closing).  Case C (post-contact
    / hand-impulse) is already folded into ``a.entry_support`` by
    :func:`_assess_side`.
    """
    left = ev["left"]
    right = ev["right"]
    candidates: list = []
    for a, side in ((left, "left"), (right, "right")):
        if not a.entry_support:
            continue
        band = a.band
        candidates.append((a, side, band if band in ("STRONG", "POSSIBLE") else "POSSIBLE"))
    if not candidates:
        return ("skip", "", "")
    if len(candidates) == 1:
        a, side, band = candidates[0]
        return (side, side, band)
    a, sa, ba = candidates[0]
    b, sb, bb = candidates[1]
    ad = a.evidence.distance_normalized
    bd = b.evidence.distance_normalized
    ad = ad if ad is not None and math.isfinite(ad) else (a.evidence.distance_px or 0.0)
    bd = bd if bd is not None and math.isfinite(bd) else (b.evidence.distance_px or 0.0)
    if abs(ad - bd) > cfg.side_tie_normalized:
        if ad < bd:
            return (sa, sa, ba)
        return (sb, sb, bb)
    return ("ambiguous", "ambiguous",
            "STRONG" if "STRONG" in (ba, bb) else "POSSIBLE")


def _pick_exit_side(ev: dict, cfg: HandAssociationConfig
                    ) -> tuple[str, str, str]:
    """Choose a side (or ambiguous) for an EXIT event.

    Sign-aware: POSSIBLE with supporting motion must be SEPARATING
    (positive slope) or fall under the n<3 raw-distance fallback.
    """
    left = ev["left"]
    right = ev["right"]
    candidates: list = []
    for a, side in ((left, "left"), (right, "right")):
        if not a.exit_support:
            continue
        band = a.band
        candidates.append((a, side, band if band in ("STRONG", "POSSIBLE") else "POSSIBLE"))
    if not candidates:
        return ("skip", "", "")
    if len(candidates) == 1:
        a, side, band = candidates[0]
        return (side, side, band)
    a, sa, ba = candidates[0]
    b, sb, bb = candidates[1]
    ad = a.evidence.distance_normalized
    bd = b.evidence.distance_normalized
    ad = ad if ad is not None and math.isfinite(ad) else (a.evidence.distance_px or 0.0)
    bd = bd if bd is not None and math.isfinite(bd) else (b.evidence.distance_px or 0.0)
    if abs(ad - bd) > cfg.side_tie_normalized:
        if ad < bd:
            return (sa, sa, ba)
        return (sb, sb, bb)
    return ("ambiguous", "ambiguous",
            "STRONG" if "STRONG" in (ba, bb) else "POSSIBLE")


# ---------------------------------------------------------------------------
# Dry-run driver
# ---------------------------------------------------------------------------

@dataclass
class DryRunResult:
    events: list[dict]
    counts: dict
    n_track_ends: int
    n_track_starts: int
    n_orphan_continuations: int
    queue_final: dict


def dry_run(tracklets: dict, hands_by_frame: dict, fps: float,
            cfg: HandAssociationConfig | None = None,
            ) -> DryRunResult:
    """Chronological dry-run over the whole video."""
    cfg = cfg or HandAssociationConfig()
    hand_features, _ = _import_hf_ho()
    sm = HandStateMachine(cfg=cfg, fps=fps)
    end_by_frame: dict = defaultdict(list)
    start_by_frame: dict = defaultdict(list)
    for tid, pts in tracklets.items():
        if not pts:
            continue
        start_by_frame[pts[0].frame].append(tid)
        if len(pts) > 1:
            end_by_frame[pts[-1].frame].append(tid)
    n_track_ends = n_track_starts = n_orphan_continuations = 0
    all_frames = set(end_by_frame.keys()) | set(start_by_frame.keys())
    last_frame = max(all_frames) if all_frames else 0
    for f in sorted(all_frames):
        for tid in end_by_frame.get(f, []):
            n_track_ends += 1
            sm.evaluate_end(tid, tracklets[tid], hands_by_frame, f,
                            hand_features)
        for tid in start_by_frame.get(f, []):
            n_track_starts += 1
            assoc = sm.evaluate_start(tid, tracklets[tid], hands_by_frame,
                                      f, hand_features)
            if assoc is not None and assoc.source_track_id == -1:
                n_orphan_continuations += 1
    sm._expiry_sweep(last_frame + int(round(cfg.safety_expiry_seconds * fps)) + 1)
    return DryRunResult(
        events=list(sm.events),
        counts=dict(sm.counts),
        n_track_ends=n_track_ends,
        n_track_starts=n_track_starts,
        n_orphan_continuations=n_orphan_continuations,
        queue_final={"left": [e.source_track_id for e in sm.left_queue],
                     "right": [e.source_track_id for e in sm.right_queue],
                     "ambiguous": [e.source_track_id for e in sm.ambiguous_queue]},
    )


# ---------------------------------------------------------------------------
# Wrist coverage statistics
# ---------------------------------------------------------------------------

@dataclass
class WristCoverageStats:
    total_frames: int
    fps: float
    left_usable: int
    right_usable: int
    both_usable: int
    neither_usable: int
    left_pct: float
    right_pct: float
    both_pct: float
    neither_pct: float
    longest_left_outage: int
    longest_right_outage: int
    longest_both_outage: int
    outage_distribution_left: dict
    outage_distribution_right: dict
    outage_distribution_both: dict
    coverage_around_transitions: list


def compute_wrist_coverage(hands_by_frame: dict, total_frames: int,
                           known_transitions: list | None = None,
                           fps: float = 60.0,
                           window: int = 30) -> WristCoverageStats:
    """Per-frame wrist availability + outage-run statistics.

    An OUTAGE is a contiguous run of frames during which the wrist
    is unavailable.  With 100% availability, every outage length
    is zero, and the distributions are empty.
    """
    left_usable = right_usable = both = neither = 0
    longest_left = longest_right = longest_both = 0
    cur_left = cur_right = cur_both = 0
    for fr in range(total_frames):
        row = hands_by_frame.get(fr, {})
        l = row.get("left") is not None
        r = row.get("right") is not None
        if l:
            left_usable += 1
            cur_left = 0
        else:
            cur_left += 1
            longest_left = max(longest_left, cur_left)
        if r:
            right_usable += 1
            cur_right = 0
        else:
            cur_right += 1
            longest_right = max(longest_right, cur_right)
        if l and r:
            both += 1
            cur_both = 0
        elif not l and not r:
            cur_both += 1
            longest_both = max(longest_both, cur_both)
        # When exactly one wrist is missing, the "both" outage run
        # is broken: a partial outage is not a both-wrist outage.
        if not l or not r:
            if not (not l and not r):
                cur_both = 0
        if not l and not r:
            neither += 1
    # Flush trailing runs.
    if cur_left:
        longest_left = max(longest_left, cur_left)
    if cur_right:
        longest_right = max(longest_right, cur_right)
    if cur_both:
        longest_both = max(longest_both, cur_both)
    # Build the run-length distributions by re-scanning with a
    # second pass that closes each run when the wrist re-appears.
    def _distrib(side_key: str) -> dict:
        runs: dict = defaultdict(int)
        cur = 0
        for fr in range(total_frames):
            row = hands_by_frame.get(fr, {})
            present = row.get(side_key) is not None
            if not present:
                cur += 1
            else:
                if cur > 0:
                    runs[cur] += 1
                cur = 0
        if cur > 0:
            runs[cur] += 1
        return dict(sorted(runs.items()))
    left_lengths = _distrib("left")
    right_lengths = _distrib("right")
    # both = 1 only when both are unavailable.
    both_runs: dict = defaultdict(int)
    cur = 0
    for fr in range(total_frames):
        row = hands_by_frame.get(fr, {})
        both_missing = (row.get("left") is None
                        and row.get("right") is None)
        if both_missing:
            cur += 1
        else:
            if cur > 0:
                both_runs[cur] += 1
            cur = 0
    if cur > 0:
        both_runs[cur] += 1
    both_lengths = dict(sorted(both_runs.items()))
    per_frame = total_frames or 1
    around: list = []
    if known_transitions:
        for tr in known_transitions:
            t = tr["frame"]
            lo = max(0, t - window)
            hi = min(total_frames - 1, t + window)
            l_usable = r_usable = 0
            for fr in range(lo, hi + 1):
                row = hands_by_frame.get(fr, {})
                if row.get("left") is not None:
                    l_usable += 1
                if row.get("right") is not None:
                    r_usable += 1
            span = max(1, hi - lo + 1)
            around.append({
                "transition": f"{tr['source_id']}->{tr['target_id']} @ {t}",
                "hand_label": tr.get("hand", ""),
                "window": window,
                "left_pct": l_usable / span,
                "right_pct": r_usable / span,
            })
    return WristCoverageStats(
        total_frames=total_frames, fps=fps,
        left_usable=left_usable, right_usable=right_usable,
        both_usable=both, neither_usable=neither,
        left_pct=left_usable / per_frame,
        right_pct=right_usable / per_frame,
        both_pct=both / per_frame,
        neither_pct=neither / per_frame,
        longest_left_outage=longest_left,
        longest_right_outage=longest_right,
        longest_both_outage=longest_both,
        outage_distribution_left=left_lengths,
        outage_distribution_right=right_lengths,
        outage_distribution_both=both_lengths,
        coverage_around_transitions=around,
    )


# ---------------------------------------------------------------------------
# Convenience: load + run from paths
# ---------------------------------------------------------------------------

def run_dry_run(tracklets_csv: Path, hands_csv: Path, fps: float,
                total_frames: int,
                cfg: HandAssociationConfig | None = None,
                known_transitions: list | None = None,
                ) -> tuple:
    cfg = cfg or HandAssociationConfig()
    tracklets = _load_tracklets(tracklets_csv)
    hands_by_frame = _load_hands_by_frame(hands_csv, cfg.confidence_threshold)
    result = dry_run(tracklets, hands_by_frame, fps, cfg)
    coverage = compute_wrist_coverage(hands_by_frame, total_frames,
                                      known_transitions, fps)
    return result, coverage


def write_event_csv(events: list[dict], path: Path) -> None:
    if not events:
        path.write_text("event_type\n")
        return
    keys: list = []
    seen = set()
    for e in events:
        for k in e.keys():
            if k not in seen:
                seen.add(k)
                keys.append(k)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys, lineterminator="\n",
                                extrasaction="ignore")
        writer.writeheader()
        for e in events:
            row = {}
            for k in keys:
                v = e.get(k, "")
                if isinstance(v, dict):
                    parts = ",".join(f"{s}={n}" for s, n in v.items())
                    v = parts
                row[k] = v
            writer.writerow(row)
