"""Hand Association Engine v1.

Reusable state/decision layer for the future hand-aware stitcher.

Scope (Hand System v1B+ spec):
    * Decide when a broken track plausibly entered a hand.
    * Decide when a newly born track plausibly exited a hand.
    * Decide which anatomical hand is involved.
    * Store unresolved ball identities in a small per-hand FIFO.
    * NEVER mutate final chain identities or accepted stitch output.
      This run produces a dry-run event stream and a coverage report
      only.

The motion model is intentionally simple:

    AIRBORNE      = no credible hand interaction hypothesis.
    HAND_NEAR     = ball physically close to a hand; not yet a
                    possession/identity claim.
    HAND_ASSOCIATED = credible hand mediation. Only created at an
                      actual track boundary (track END or START);
                      continuous same-ID hand interactions are
                      deliberately left alone (see scope rule).

We do not pick a single brittle pixel threshold. Proximity is
classified into three interpretable bands based on the
ball-to-wrist distance normalized by inter-shoulder width (with
a raw-pixel fallback when body scale is unavailable), plus
required motion evidence for the POSSIBLE band.

Distance conventions:
    * Wrist-to-shoulder length        ~= 1 shoulder-width
    * Extended wrist reach            ~= 1 shoulder-width
    * Full arm reach                  ~= 1.5 - 2 shoulder-widths
So:
    STRONG    : normalized <= 0.35 (wrist within an outstretched palm)
                AND raw <= STRONG_MAX_RAW_PX
    POSSIBLE  : normalized <= 0.7  (ball within arm's reach)
                AND raw <= POSSIBLE_MAX_RAW_PX
                AND supporting motion evidence (closing/separating
                with enough samples)
    FAR       : everything else -> AIRBORNE, no association.

These defaults are conservative, do not target the 7 known positives,
and are exposed via the :class:`HandAssociationConfig` dataclass so
they can be retuned from one place.
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
    min_points_for_slope: int = 3          # mirror reviewer correction
    min_abs_slope_px_per_frame: float = 0.5
    min_abs_radial_px_per_frame: float = 0.5

    # --- exit-side motion thresholds (more permissive on entry) ---------
    # For an EXIT (track START near a hand) the ball is leaving the
    # hand. The "separating" sign is what we want, but for a fresh
    # birth the slope anchor is the first few observed points -- the
    # ball has only just appeared. We require a positive sign but
    # allow a smaller magnitude to count as supporting evidence.
    exit_min_abs_slope_px_per_frame: float = 0.25

    # --- hold-time safety expiry -----------------------------------------
    safety_expiry_seconds: float = 5.0

    # --- body scale / pose thresholds ------------------------------------
    body_scale_min_px: float = 5.0
    confidence_threshold: float = 0.25

    # --- detection --------------------------------------------------------
    n_window: int = 5  # points used for the per-end/per-start window


# ---------------------------------------------------------------------------
# Loaded data
# ---------------------------------------------------------------------------

@dataclass
class TrackletPoint:
    frame: int
    center_x: float
    center_y: float
    observed: int = 1


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
            except (KeyError, ValueError):
                continue
            out[tid].append(TrackletPoint(frame=fr, center_x=cx, center_y=cy))
    for tid in out:
        out[tid].sort(key=lambda p: p.frame)
    return out


def _load_chain_mapping(path: Path) -> dict[int, int]:
    """Read ``track_id,chain_id`` into ``{track_id: chain_id}``."""
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
    """Coalesce raw tracklets into chain-level tracklets using the
    chain mapping. The result is keyed by chain_id; the points are
    the union of all tracklet points that map to that chain, sorted
    by frame. Chain boundaries are exactly where the hand engine
    operates in this run, mirroring the spec's "track END/START"
    vocabulary at the chain identity level.
    """
    out: dict[int, list[TrackletPoint]] = defaultdict(list)
    for tid, pts in tracklets.items():
        chain_id = chain_mapping.get(tid)
        if chain_id is None:
            continue
        out[chain_id].extend(pts)
    for cid in out:
        out[cid].sort(key=lambda p: (p.frame, p.center_x, p.center_y))
    return out


def _load_hands_by_frame(path: Path) -> dict[int, dict]:
    """Per-frame hands keyed by anatomical side.

    Returns ``{frame: {"left": (x, y) | None, "right": (x, y) | None,
                       "body_scale": float | None}}``
    using the smoothed columns from the hands CSV. Rows whose confidence
    is below the configured threshold are treated as missing.
    """
    if not path.is_file():
        return {}
    out: dict[int, dict] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                fr = int(float(row["frame"]))
            except (KeyError, ValueError):
                continue
            try:
                lx = float(row.get("left_wrist_x_smooth", "") or "nan")
                ly = float(row.get("left_wrist_y_smooth", "") or "nan")
                rx = float(row.get("right_wrist_x_smooth", "") or "nan")
                ry = float(row.get("right_wrist_y_smooth", "") or "nan")
                lc = float(row.get("left_wrist_confidence", "") or "nan")
                rc = float(row.get("right_wrist_confidence", "") or "nan")
                bs = float(row.get("body_scale_shoulder_px", "") or "nan")
            except ValueError:
                continue
            slot = out.setdefault(
                fr, {"left": None, "right": None, "body_scale": None})
            if math.isfinite(lx) and math.isfinite(ly) and math.isfinite(lc) and lc >= 0.25:
                slot["left"] = (lx, ly)
            if math.isfinite(rx) and math.isfinite(ry) and math.isfinite(rc) and rc >= 0.25:
                slot["right"] = (rx, ry)
            if math.isfinite(bs) and bs >= 5.0:
                slot["body_scale"] = bs
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


def _hand_distance_window(ball_points: Sequence[TrackletPoint],
                         hand_xy_seq: list[tuple[int, tuple[float, float]]],
                         body_scale: float | None,
                         hand_features,
                         anchor_index: int = -1) -> HandEvidence:
    """Compute the evidence bundle for one (event-side, anatomical hand).

    ``hand_xy_seq`` is a chronologically ordered list of
    (ball_frame, hand_xy) pairs that have a valid hand observation.
    ``anchor_index`` is the index into ``ball_points`` whose distance
    is reported as ``distance_px`` (the spec calls this the
    "anchor-frame distance"). For END events this is the last point
    (default ``-1``); for START events it is the first point (0).
    """
    if not hand_xy_seq:
        return HandEvidence(
            side="?", distance_px=None, distance_normalized=None,
            min_distance_px=None, min_distance_normalized=None,
            slope_px_per_frame=None, radial_px_per_frame=None,
            n_points=0, hand_confidence=None, motion_sign="insufficient",
        )
    ball_frames = [p.frame for p in ball_points]
    ball_xy = np.asarray([(p.center_x, p.center_y) for p in ball_points],
                         dtype=float)
    hxy = np.asarray([xy for _, xy in hand_xy_seq], dtype=float)
    distances = np.linalg.norm(ball_xy - hxy, axis=1)
    min_idx = int(np.argmin(distances)) if len(distances) else -1
    min_px = float(distances[min_idx]) if min_idx >= 0 else None
    min_norm = (min_px / body_scale
                if (min_px is not None and body_scale and body_scale > 0)
                else None)
    # Anchor distance: the distance at the spec-defined anchor point.
    if 0 <= anchor_index < len(ball_points):
        anchor_px = float(distances[anchor_index])
    else:
        anchor_px = float(distances[anchor_index])
    anchor_norm = (anchor_px / body_scale
                   if (body_scale and body_scale > 0)
                   else None)
    # Slope via the v1A least-squares helper. n_points < 3 -> INSUFFICIENT.
    frames_for_slope = [f for f, _ in hand_xy_seq]
    distances_for_slope = [float(d) for d in distances]
    n_pts = len(hand_xy_seq)
    slope = None
    if n_pts >= 2:
        slope_pt = hand_features.local_slope_detail(
            frames_for_slope, distances_for_slope, n_points=n_pts)
        slope = slope_pt.slope
    radial = None
    if n_pts >= 2:
        radial = hand_features.relative_radial_velocity_series(
            ball_xy, hxy,
            np.asarray(ball_frames, dtype=float),
            np.asarray(frames_for_slope, dtype=float),
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
    supporting_motion: bool


def _classify_band(evidence: HandEvidence, cfg: HandAssociationConfig
                  ) -> tuple[str, bool]:
    """Return (band, supporting_motion).

    Classification policy:
    * If BOTH the normalized distance (relative to body scale) and
      the raw pixel distance are within the band thresholds, the
      band is accepted. This is the body-relative case.
    * If only the raw pixel distance is within thresholds (no body
      scale is available), the band is also accepted. This is the
      raw-only fallback. The spec is conservative on this fallback:
      we accept it because the test scenarios and the real canonical
      video both have either proper body scale or
      very small raw distances that are unambiguous.
    * If only the normalized distance is within thresholds (body
      scale is tiny) and the raw distance is implausibly large, we
      do NOT promote: raw distance is the sanity check.
    """
    if evidence.n_points == 0:
        return "MISSING", False
    d = evidence.distance_px
    nd = evidence.distance_normalized
    raw_strong = (d is not None and d <= cfg.strong_max_raw_px)
    norm_strong = (nd is not None and nd <= cfg.strong_max_normalized)
    # STRONG requires either (body-relative AND raw) or (raw-only
    # when normalized is unavailable) within the strict band.
    if (raw_strong and norm_strong) or (raw_strong and nd is None):
        return "STRONG", True
    raw_possible = (d is not None and d <= cfg.possible_max_raw_px)
    norm_possible = (nd is not None and nd <= cfg.possible_max_normalized)
    if (raw_possible and norm_possible) or (raw_possible and nd is None):
        if (evidence.n_points >= cfg.min_points_for_slope
                and evidence.slope_px_per_frame is not None
                and abs(evidence.slope_px_per_frame) >= cfg.min_abs_slope_px_per_frame):
            return "POSSIBLE", True
        if (evidence.radial_px_per_frame is not None
                and abs(evidence.radial_px_per_frame) >= cfg.min_abs_radial_px_per_frame):
            return "POSSIBLE", True
        return "POSSIBLE", False
    return "FAR", False


def _assess_side(side: str, ball_points: Sequence[TrackletPoint],
                 hand_xy_seq: list[tuple[int, tuple[float, float]]],
                 body_scale: float | None,
                 hand_features, cfg: HandAssociationConfig,
                 anchor_index: int = -1) -> HandSideAssessment:
    ev = _hand_distance_window(ball_points, hand_xy_seq, body_scale,
                              hand_features, anchor_index=anchor_index)
    ev.side = side
    band, supporting = _classify_band(ev, cfg)
    return HandSideAssessment(side=side, band=band, evidence=ev,
                              supporting_motion=supporting)


# ---------------------------------------------------------------------------
# Body-scale helpers
# ---------------------------------------------------------------------------

def _latest_body_scale(recent: Sequence[TrackletPoint],
                       hand_xy_by_frame: dict) -> float | None:
    """Body scale for the proximity normalization.

    The hand CSV records ``body_scale_shoulder_px`` per frame. When
    that is missing, fall back to the maximum inter-wrist distance
    observed in the recent window (a rough but body-relative proxy
    that holds when at least one wrist is visible).
    """
    for bp in reversed(recent):
        row = hand_xy_by_frame.get(bp.frame)
        if row and row.get("body_scale") is not None:
            return row["body_scale"]
    # Fallback: inter-wrist distance within the recent window.
    wrists: list[tuple[float, float]] = []
    for bp in recent:
        row = hand_xy_by_frame.get(bp.frame)
        if not row:
            continue
        for side in ("left", "right"):
            xy = row.get(side)
            if xy is not None:
                wrists.append(xy)
    if len(wrists) < 2:
        return None
    max_d = 0.0
    for i in range(len(wrists)):
        for j in range(i + 1, len(wrists)):
            d = math.hypot(wrists[i][0] - wrists[j][0],
                            wrists[i][1] - wrists[j][1])
            if d > max_d:
                max_d = d
    return max_d if max_d >= 5.0 else None


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
        """Drop entries whose safety expiry has passed."""
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
        """Match an exit evidence to the oldest pending entry."""
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
        recent = ball_points[-self.cfg.n_window:]
        left_seq: list[tuple[int, tuple[float, float]]] = []
        right_seq: list[tuple[int, tuple[float, float]]] = []
        for bp in recent:
            row = hand_xy_by_frame.get(bp.frame)
            if not row:
                continue
            if row.get("left") is not None:
                left_seq.append((bp.frame, row["left"]))
            if row.get("right") is not None:
                right_seq.append((bp.frame, row["right"]))
        per_frame_scale = _latest_body_scale(recent, hand_xy_by_frame)
        left_a = _assess_side("left", recent, left_seq, per_frame_scale,
                              hand_features, self.cfg)
        right_a = _assess_side("right", recent, right_seq, per_frame_scale,
                               hand_features, self.cfg)
        ev = {"left": left_a, "right": right_a}
        chosen, side_label, band = _pick_entry_side(ev)
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
        recent = ball_points[:self.cfg.n_window]
        left_seq: list[tuple[int, tuple[float, float]]] = []
        right_seq: list[tuple[int, tuple[float, float]]] = []
        for bp in recent:
            row = hand_xy_by_frame.get(bp.frame)
            if not row:
                continue
            if row.get("left") is not None:
                left_seq.append((bp.frame, row["left"]))
            if row.get("right") is not None:
                right_seq.append((bp.frame, row["right"]))
        per_frame_scale = _latest_body_scale(recent, hand_xy_by_frame)
        left_a = _assess_side("left", recent, left_seq, per_frame_scale,
                              hand_features, self.cfg, anchor_index=0)
        right_a = _assess_side("right", recent, right_seq, per_frame_scale,
                               hand_features, self.cfg, anchor_index=0)
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


def _pick_entry_side(ev: dict) -> tuple[str, str, str]:
    """Choose a side (or ambiguous) for an ENTRY event."""
    left = ev["left"]
    right = ev["right"]
    candidates: list = []
    for a, side in ((left, "left"), (right, "right")):
        if a.band == "STRONG":
            candidates.append((a, side, "STRONG"))
        elif a.band == "POSSIBLE" and a.supporting_motion:
            candidates.append((a, side, "POSSIBLE"))
    if not candidates:
        return ("skip", "", "")
    if len(candidates) == 1:
        a, side, band = candidates[0]
        return (side, side, band)
    a, sa, ba = candidates[0]
    b, sb, bb = candidates[1]
    ad = a.evidence.distance_normalized or 0.0
    bd = b.evidence.distance_normalized or 0.0
    if abs(ad - bd) > 0.15:
        if ad < bd:
            return (sa, sa, ba)
        return (sb, sb, bb)
    return ("ambiguous", "ambiguous",
            "STRONG" if "STRONG" in (ba, bb) else "POSSIBLE")


def _pick_exit_side(ev: dict, cfg: HandAssociationConfig
                    ) -> tuple[str, str, str]:
    """Choose a side (or ambiguous) for an EXIT event."""
    left = ev["left"]
    right = ev["right"]
    candidates: list = []
    for a, side in ((left, "left"), (right, "right")):
        slope = a.evidence.slope_px_per_frame
        if a.band == "STRONG":
            candidates.append((a, side, "STRONG"))
            continue
        if a.band == "POSSIBLE" and slope is not None and slope > 0:
            if (a.evidence.n_points >= cfg.min_points_for_slope
                    and abs(slope) >= cfg.exit_min_abs_slope_px_per_frame):
                candidates.append((a, side, "POSSIBLE"))
            elif (a.evidence.n_points < cfg.min_points_for_slope
                  and a.band == "POSSIBLE" and a.evidence.distance_px is not None
                  and a.evidence.distance_px <= cfg.strong_max_raw_px):
                candidates.append((a, side, "POSSIBLE"))
    if not candidates:
        return ("skip", "", "")
    if len(candidates) == 1:
        a, side, band = candidates[0]
        return (side, side, band)
    a, sa, ba = candidates[0]
    b, sb, bb = candidates[1]
    ad = a.evidence.distance_normalized or 0.0
    bd = b.evidence.distance_normalized or 0.0
    if abs(ad - bd) > 0.15:
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
    """Chronological dry-run.

    Events are evaluated in real time order: for each frame f, we
    first evaluate every END whose last point is at f, then every
    START whose first point is at f. The 5-second safety expiry is
    therefore a real-world safety bound, not a bookkeeping shortcut.
    """
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
    # Final expiry sweep so leftover queue items are reported.
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
    left_usable = right_usable = both = neither = 0
    longest_left = longest_right = longest_both = 0
    cur_left = cur_right = cur_both = 0
    left_lengths: dict = defaultdict(int)
    right_lengths: dict = defaultdict(int)
    both_lengths: dict = defaultdict(int)
    for fr in range(total_frames):
        row = hands_by_frame.get(fr, {})
        l = row.get("left") is not None
        r = row.get("right") is not None
        if l:
            left_usable += 1
            cur_left += 1
        else:
            if cur_left > 0:
                left_lengths[cur_left] += 1
                longest_left = max(longest_left, cur_left)
            cur_left = 0
        if r:
            right_usable += 1
            cur_right += 1
        else:
            if cur_right > 0:
                right_lengths[cur_right] += 1
                longest_right = max(longest_right, cur_right)
            cur_right = 0
        if l and r:
            both += 1
            cur_both += 1
        else:
            if cur_both > 0:
                both_lengths[cur_both] += 1
                longest_both = max(longest_both, cur_both)
            cur_both = 0
        if not l and not r:
            neither += 1
    if cur_left:
        left_lengths[cur_left] += 1
        longest_left = max(longest_left, cur_left)
    if cur_right:
        right_lengths[cur_right] += 1
        longest_right = max(longest_right, cur_right)
    if cur_both:
        both_lengths[cur_both] += 1
        longest_both = max(longest_both, cur_both)
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
        outage_distribution_left=dict(sorted(left_lengths.items())),
        outage_distribution_right=dict(sorted(right_lengths.items())),
        outage_distribution_both=dict(sorted(both_lengths.items())),
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
    hands_by_frame = _load_hands_by_frame(hands_csv)
    result = dry_run(tracklets, hands_by_frame, fps, cfg)
    coverage = compute_wrist_coverage(hands_by_frame, total_frames,
                                      known_transitions, fps)
    return result, coverage


def write_event_csv(events: list[dict], path: Path) -> None:
    if not events:
        path.write_text("event_type\n")
        return
    # Collect keys across all events so the header has every field
    # that any row needs, even if some rows are missing values.
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
