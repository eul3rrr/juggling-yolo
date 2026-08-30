"""Hand System v1B — reviewer-side helpers.

Reuses the v1A :mod:`hand_features` module for all numeric calculations
and adds:

* a tiny CSV loader for the per-frame hand rows,
* an :func:`event_hand_features` helper that produces the same
  distance / slope / radial-relative-velocity features the v1A
  diagnostic exposes, but keyed to a :class:`ReviewEvent`,
* a :func:`format_hand_metric` formatter that turns those numbers into
  reviewer-friendly strings (e.g. ``"-13.3  CLOSING"``) without losing
  the missing/underdetermined distinction,
* a :func:`annotate_features` helper that turns a primary event's
  features into a structured dict the browser can render.

This module deliberately does **not** re-implement any of the math in
:mod:`hand_features`. The reviewer and the v1A diagnostic must stay in
agreement on every number they show.
"""
from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Keep this in sync with scripts/hand_features.py / scripts/extract_hands.py
CONFIDENCE_THRESHOLD = 0.25
SMOOTHING_WINDOW = 5
N_POINTS = 5
BODY_SCALE_MIN_PX = 5.0


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

@dataclass
class PersonHandRow:
    """One person-row from the hand CSV, lazily converted to floats."""
    frame: int
    person_index: int
    left_wrist: tuple[float, float] | None
    left_wrist_conf: float | None
    right_wrist: tuple[float, float] | None
    right_wrist_conf: float | None
    left_elbow: tuple[float, float] | None
    left_elbow_conf: float | None
    right_elbow: tuple[float, float] | None
    right_elbow_conf: float | None
    left_shoulder: tuple[float, float] | None
    left_shoulder_conf: float | None
    right_shoulder: tuple[float, float] | None
    right_shoulder_conf: float | None
    body_scale: float | None

    @property
    def is_valid(self) -> bool:
        return (self.left_wrist is not None or self.right_wrist is not None
                or self.left_elbow is not None or self.right_elbow is not None
                or self.left_shoulder is not None or self.right_shoulder is not None)


def _safe_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        f = float(value)
    except ValueError:
        return None
    if not math.isfinite(f):
        return None
    return f


def _xy(row: dict, x_key: str, y_key: str, conf_key: str,
        threshold: float) -> tuple[tuple[float, float], float] | None:
    x = _safe_float(row.get(x_key))
    y = _safe_float(row.get(y_key))
    c = _safe_float(row.get(conf_key))
    if x is None or y is None or c is None:
        return None
    if c < threshold:
        return None
    return (x, y), c


def load_hands_by_frame(path: Path, threshold: float = CONFIDENCE_THRESHOLD
                        ) -> dict[int, list[PersonHandRow]]:
    """Load the hand CSV into a {frame: [PersonHandRow, ...]} structure.

    Per-keypoint raw values are preferred when their confidence passes the
    threshold; otherwise the smoothed value is consulted (it is itself
    already ``None`` when the centre was below threshold or missing). The
    smoothed coordinates are the "stay put when missing" version; using
    them here means the rendered skeleton does not jitter into plausible
    positions when the model briefly loses the wrist.
    """
    out: dict[int, list[PersonHandRow]] = defaultdict(list)
    if not path.is_file():
        return out
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                frame = int(float(row["frame"]))
            except (KeyError, ValueError):
                continue
            try:
                person_index = int(float(row.get("person_index", "0")))
            except ValueError:
                person_index = 0

            def _kp(x: str, y: str, conf: str,
                    use_smooth: bool = False) -> tuple[tuple[float, float], float] | None:
                x_key = x + ("_smooth" if use_smooth else "")
                y_key = y + ("_smooth" if use_smooth else "")
                return _xy(row, x_key, y_key, conf, threshold)

            # Use smoothed keypoints for the wrist+elbow+shoulder overlay
            # (already centred-median, already None when low-confidence).
            left_wrist = _kp("left_wrist_x", "left_wrist_y", "left_wrist_confidence", True)
            right_wrist = _kp("right_wrist_x", "right_wrist_y", "right_wrist_confidence", True)
            left_elbow = _kp("left_elbow_x", "left_elbow_y", "left_elbow_confidence", True)
            right_elbow = _kp("right_elbow_x", "right_elbow_y", "right_elbow_confidence", True)
            left_shoulder = _kp("left_shoulder_x", "left_shoulder_y", "left_shoulder_confidence", True)
            right_shoulder = _kp("right_shoulder_x", "right_shoulder_y", "right_shoulder_confidence", True)
            body_scale = _safe_float(row.get("body_scale_shoulder_px"))
            if body_scale is not None and body_scale < BODY_SCALE_MIN_PX:
                body_scale = None
            out[frame].append(PersonHandRow(
                frame=frame, person_index=person_index,
                left_wrist=left_wrist[0] if left_wrist else None,
                left_wrist_conf=left_wrist[1] if left_wrist else None,
                right_wrist=right_wrist[0] if right_wrist else None,
                right_wrist_conf=right_wrist[1] if right_wrist else None,
                left_elbow=left_elbow[0] if left_elbow else None,
                left_elbow_conf=left_elbow[1] if left_elbow else None,
                right_elbow=right_elbow[0] if right_elbow else None,
                right_elbow_conf=right_elbow[1] if right_elbow else None,
                left_shoulder=left_shoulder[0] if left_shoulder else None,
                left_shoulder_conf=left_shoulder[1] if left_shoulder else None,
                right_shoulder=right_shoulder[0] if right_shoulder else None,
                right_shoulder_conf=right_shoulder[1] if right_shoulder else None,
                body_scale=body_scale,
            ))
    return out


# ---------------------------------------------------------------------------
# Per-event feature computation
# ---------------------------------------------------------------------------

@dataclass
class _BallSample:
    frame: int
    xy: tuple[float, float]


def _track_observed_xy(track) -> list[_BallSample]:
    """Return observed-only (frame, x, y) samples for a track, in order.

    ``track`` is the reviewer's :class:`Track` (which has
    ``all_sorted`` of :class:`TrackObservation` with an ``observed``
    field).  We import the type lazily so this module stays decoupled.
    """
    out: list[_BallSample] = []
    for obs in track.all_sorted:
        if getattr(obs, "is_observed", True):
            out.append(_BallSample(frame=int(obs.frame),
                                   xy=(float(obs.center_x), float(obs.center_y))))
    out.sort(key=lambda s: s.frame)
    return out


def _hand_xy_series(hands: dict[int, list[PersonHandRow]],
                    frames: Iterable[int], side: str,
                    threshold: float = CONFIDENCE_THRESHOLD
                    ) -> tuple[list[int], list[tuple[float, float]], list[float | None]]:
    """Pick the first usable wrist for ``side`` at each requested frame.

    The video has a single juggler; the first qualifying row per frame is
    the juggler. Anatomical left/right is taken from the CSV columns, not
    from screen position.
    """
    out_f: list[int] = []
    out_xy: list[tuple[float, float]] = []
    out_c: list[float | None] = []
    for fr in frames:
        chosen = None
        for row in hands.get(fr, []):
            xy = (row.left_wrist if side == "left" else row.right_wrist)
            conf = (row.left_wrist_conf if side == "left" else row.right_wrist_conf)
            if xy is None or conf is None or conf < threshold:
                continue
            chosen = (xy, conf)
            break
        if chosen is None:
            continue
        out_f.append(fr)
        out_xy.append(chosen[0])
        out_c.append(float(chosen[1]))
    return out_f, out_xy, out_c


def _body_scale_at(hands: dict[int, list[PersonHandRow]],
                   frame: int) -> float | None:
    for row in hands.get(frame, []):
        if row.body_scale is not None:
            return row.body_scale
    return None


@dataclass
class HandMetrics:
    """Features for a track END or START against a single anatomical hand."""
    hand: str                   # "left" or "right"
    distance_px: float | None
    distance_normalized: float | None
    distance_slope_px_per_frame: float | None
    radial_relative_velocity: float | None
    n_points: int
    hand_confidence: float | None
    trend_label: str  # "INSUFFICIENT (n=N)" | "CLOSING" | "SEPARATING" | "STABLE" | "—"

    def as_dict(self) -> dict:
        return asdict(self)


def _import_hand_features():
    """Load :mod:`hand_features` by file path so we do not require the
    ``scripts`` directory to be on ``sys.path`` (it isn't, in the test
    runner and in the reviewer's own process)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "hand_features", PROJECT_ROOT / "scripts" / "hand_features.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("hand_features", module)
    spec.loader.exec_module(module)
    return module


def compute_hand_metrics(ball_samples: list[_BallSample],
                         hands: dict[int, list[PersonHandRow]],
                         side: str,
                         n_window: int = N_POINTS) -> dict[str, HandMetrics]:
    """Compute v1A-equivalent hand features for an event.

    For ``side == "end"`` we use the last ``n_window`` observed ball
    points; for ``side == "start"`` we use the first ``n_window``. The
    window is reversed on the START side so the same
    :func:`hand_features.local_slope_detail` and
    :func:`hand_features.relative_radial_velocity_series` produce a
    slope that is anchored to the most recent (for END) or earliest
    (for START) usable ball point.
    """
    hand_features = _import_hand_features()

    if len(ball_samples) < 2:
        empty = lambda name: HandMetrics(
            hand=name, distance_px=None, distance_normalized=None,
            distance_slope_px_per_frame=None,
            radial_relative_velocity=None,
            n_points=0, hand_confidence=None, trend_label="—",
        )
        return {"left": empty("left"), "right": empty("right")}

    window = (ball_samples[-n_window:] if side == "end"
              else ball_samples[:n_window])
    if side == "start":
        window = list(reversed(window))
    ball_frames = [s.frame for s in window]
    ball_xy = np.asarray([s.xy for s in window], dtype=float)
    body_scale_value = _body_scale_at(hands, ball_frames[-1])

    out: dict[str, HandMetrics] = {}
    for hand_name in ("left", "right"):
        hf, hxy, hc = _hand_xy_series(hands, ball_frames, hand_name)
        if len(hf) < 2:
            out[hand_name] = HandMetrics(
                hand=hand_name, distance_px=None, distance_normalized=None,
                distance_slope_px_per_frame=None, radial_relative_velocity=None,
                n_points=len(hf),
                hand_confidence=hc[-1] if hc else None, trend_label="—",
            )
            continue
        feats = hand_features.event_features_for_hand(
            ball_frames=np.asarray(ball_frames, dtype=int),
            ball_xy=ball_xy,
            hand_frames=np.asarray(hf, dtype=int),
            hand_xy=np.asarray(hxy, dtype=float),
            hand_confidences=np.asarray(hc, dtype=float),
            hand_name=hand_name,
            body_scale_value=body_scale_value,
            n_window=len(hf),
            min_window_pts=2,
        )
        out[hand_name] = HandMetrics(
            hand=hand_name,
            distance_px=feats.distance_px,
            distance_normalized=feats.distance_normalized,
            distance_slope_px_per_frame=feats.distance_slope_px_per_frame,
            radial_relative_velocity=feats.radial_relative_velocity,
            n_points=feats.n_distance_points,
            hand_confidence=feats.hand_confidence,
            trend_label=_trend_label(feats.distance_slope_px_per_frame,
                                      feats.n_distance_points),
        )
    return out


def _trend_label(slope: float | None, n_points: int = 0) -> str:
    """Decide the human-readable trend class for a slope.

    Sample-count policy: a two-point least-squares slope is
    mathematically a two-frame difference, which we explicitly do
    not want to treat as reliable trend evidence. The threshold is
    therefore ``n_points < 3`` => ``"INSUFFICIENT (n=N)"``,
    regardless of the numeric slope. The raw slope is still
    available to the caller via ``distance_slope_px_per_frame`` and
    is rendered numerically; only the *categorical trend evidence*
    is suppressed.
    """
    if slope is None or not math.isfinite(float(slope)):
        return "—"
    if n_points < 3:
        return f"INSUFFICIENT (n={int(n_points)})"
    s = float(slope)
    if s < -0.5:
        return "CLOSING"
    if s > 0.5:
        return "SEPARATING"
    return "STABLE"


def nearest_hand(metrics: dict[str, HandMetrics]) -> str | None:
    """Which hand is closer to the ball at the anchor frame.

    Mirrors :func:`hand_features.nearest_hand` so the reviewer agrees
    with the v1A diagnostic.
    """
    candidates = [(m.distance_px, m.hand) for m in metrics.values()
                  if m.distance_px is not None]
    if not candidates:
        return None
    return min(candidates, key=lambda c: c[0])[1]


def event_hand_features(event, hands: dict[int, list[PersonHandRow]]
                        ) -> dict:
    """Build a JSON-serialisable hand-features dict for one event.

    Returned keys:
        ``source``     : ``HandMetrics`` for the primary track's last N points
                        (END side) — meaningful for END and ORPHAN_START
                        (where the primary is the new track).
        ``candidates`` : list of per-candidate metric dicts, in the
                        reviewer's numbering order.
    """
    primary_samples = _track_observed_xy(event.primary)
    # For ORPHAN events the primary is a brand-new track; use its first
    # N observed points. For END events the primary is the track that
    # just ended; use its last N observed points.
    primary_side = "start" if event.kind == "orphan_start" else "end"
    source_metrics = compute_hand_metrics(primary_samples, hands, side=primary_side)
    source: dict[str, object] = {name: m.as_dict() for name, m in source_metrics.items()}
    source["nearest"] = nearest_hand(source_metrics)
    candidates: list[dict] = []
    for idx, cand in enumerate(event.nearby_starts, start=1):
        cand_samples = _track_observed_xy(cand)
        # For END events the candidate trajectory "starts" at the new
        # track; for ORPHAN events the candidate is an *earlier* ending,
        # so we use the END side of that predecessor trajectory.
        side = "end" if event.kind == "orphan_start" else "start"
        m = compute_hand_metrics(cand_samples, hands, side=side)
        candidates.append({
            "index": idx,
            "track_id": int(cand.track_id),
            "nearest": nearest_hand(m),
            "left": m["left"].as_dict(),
            "right": m["right"].as_dict(),
        })
    return {"source": source, "candidates": candidates}


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def format_hand_metric(value: float | None, *, decimals: int = 1,
                       signed: bool = True) -> str:
    """Format a numeric metric for display.

    * ``None`` and non-finite values render as ``—`` (U+2014 em-dash).
    * Signed values are rendered with a leading ``+`` or ``-`` so the
      human can scan a column of slopes and spot CLOSING/SEPARATING
      at a glance.
    """
    if value is None or not math.isfinite(float(value)):
        return "—"
    if signed:
        return f"{value:+.{decimals}f}"
    return f"{value:.{decimals}f}"


def format_distance(m: HandMetrics) -> str:
    return format_hand_metric(m.distance_px, decimals=1, signed=False) + " px"


def format_slope(m: HandMetrics) -> str:
    return f"d' {format_hand_metric(m.distance_slope_px_per_frame, decimals=1)}"


def format_rrv(m: HandMetrics) -> str:
    return f"radial {format_hand_metric(m.radial_relative_velocity, decimals=1)}"


def format_trend(m: HandMetrics) -> str:
    return m.trend_label
