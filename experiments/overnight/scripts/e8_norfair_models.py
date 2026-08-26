#!/usr/bin/env python3
"""E8: Norfair motion-model comparison for fragmentation.

Models:
- nofilter      : NoFilterFactory (pure nearest-center persistence).
- optvel        : OptimizedKalmanFilterFactory (constant velocity, norfair's
                  optimized default).
- optvel_looseQ : OptimizedKalmanFilterFactory with larger process noise Q.
- constacc      : custom constant-acceleration filter implementing the
                  minimal predict/update/x interface.

All runs use distance_threshold=50, hit_counter_max=5 on the existing YOLO
detection CSVs. Outputs fragmentation stats + CSVs under data/e8/.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

BASE = Path(__file__).resolve().parents[1]
PROJECT = BASE.parents[1]
OUT_DIR = BASE / "data" / "e8"
SHIPPED = PROJECT / "detections"

sys.path.insert(0, str(PROJECT / "scripts"))

from norfair import Detection, Tracker  # noqa: E402
from norfair.filter import (  # noqa: E402
    FilterFactory,
    NoFilterFactory,
    OptimizedKalmanFilterFactory,
)

STEMS = {
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
}
DISTANCE_THRESHOLD = 50
HIT_COUNTER_MAX = 5


class ConstantAccelerationFilter:
    """Constant-acceleration Kalman filter compatible with Norfair's
    [pos, vel] state-layout assumptions (acceleration kept internal)."""

    def __init__(self, initial_detection: np.ndarray):
        flat = np.asarray(initial_detection, dtype=float).flatten()
        self.dim_z = flat.size
        self._n = 3 * self.dim_z
        self._x = np.zeros((self._n, 1))
        self._x[: self.dim_z, 0] = flat
        self._P = np.eye(self._n) * 100.0
        self._P[self.dim_z : 2 * self.dim_z, self.dim_z : 2 * self.dim_z] *= 0.1
        self._q = np.eye(self._n) * 0.1
        self._r = np.eye(self.dim_z) * 4.0
        self._H = np.zeros((self.dim_z, self._n))
        self._H[: self.dim_z, : self.dim_z] = np.eye(self.dim_z)
        self.dt = 1.0

    @property
    def x(self) -> np.ndarray:
        return self._x[: 2 * self.dim_z].copy()

    @x.setter
    def x(self, value: np.ndarray) -> None:
        self._x[: 2 * self.dim_z] = value

    def _F(self, dt: float) -> np.ndarray:
        F = np.eye(self._n)
        for i in range(self.dim_z):
            F[i, self.dim_z + i] = dt
            F[i, 2 * self.dim_z + i] = 0.5 * dt * dt
            F[self.dim_z + i, 2 * self.dim_z + i] = dt
        return F

    def predict(self):
        F = self._F(self.dt)
        self._x = F @ self._x
        self._P = F @ self._P @ F.T + self._q

    def update(self, detection_points_flatten, R=None, H=None):
        z = np.asarray(detection_points_flatten, dtype=float).reshape((self.dim_z, 1))
        y = z - self._H @ self._x
        S = self._H @ self._P @ self._H.T + self._r
        K = self._P @ self._H.T @ np.linalg.inv(S)
        self._x = self._x + K @ y
        self._P = (np.eye(self._n) - K @ self._H) @ self._P


class ConstantAccelerationFactory(FilterFactory):
    def create_filter(self, initial_detection):
        return ConstantAccelerationFilter(initial_detection)


def load_detections(stem: str) -> dict[int, list[tuple[float, float, float]]]:
    path = SHIPPED / f"{stem}_yolo26s_classes-32.csv"
    by_frame: dict[int, list[tuple[float, float, float]]] = defaultdict(list)
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            by_frame[int(row["frame"])].append(
                (float(row["center_x"]), float(row["center_y"]), float(row["confidence"]))
            )
    return dict(by_frame)


def run_tracker(by_frame, factory) -> list[dict]:
    tracker = Tracker(
        distance_function="euclidean",
        distance_threshold=DISTANCE_THRESHOLD,
        hit_counter_max=HIT_COUNTER_MAX,
        filter_factory=factory,
    )
    rows = []
    for frame in sorted(by_frame):
        detections = [
            Detection(points=np.array([[x, y]]), scores=np.array([c]))
            for x, y, c in by_frame[frame]
        ]
        active = tracker.update(detections=detections)
        det_ids = {id(d) for d in detections}
        for obj in active:
            x, y = obj.estimate[0]
            observed = int(
                obj.last_detection is not None
                and id(obj.last_detection) in det_ids
            )
            rows.append({
                "frame": frame,
                "track_id": obj.id,
                "center_x": float(x),
                "center_y": float(y),
                "observed": observed,
            })
    return rows


def fragmentation_stats(rows: list[dict]) -> dict:
    by_track = defaultdict(list)
    for r in rows:
        by_track[r["track_id"]].append(r["frame"])
    lengths = sorted(len(v) for v in by_track.values())
    return {
        "n_tracklets": len(by_track),
        "median_points": float(np.median(lengths)) if lengths else 0.0,
        "max_points": lengths[-1] if lengths else 0,
        "total_rows": len(rows),
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results = {}
    for stem in sorted(STEMS):
        by_frame = load_detections(stem)
        configs = {
            "nofilter": NoFilterFactory(),
            "optvel": OptimizedKalmanFilterFactory(),
            "optvel_looseQ": OptimizedKalmanFilterFactory(Q=1.0),
            "constacc": ConstantAccelerationFactory(),
        }
        for name, factory in configs.items():
            rows = run_tracker(by_frame, factory)
            stats = fragmentation_stats(rows)
            out_csv = OUT_DIR / f"{stem}_norfair_{name}.csv"
            with out_csv.open("w", newline="") as fh:
                writer = csv.DictWriter(
                    fh, fieldnames=["frame", "track_id", "center_x", "center_y", "observed"]
                )
                writer.writeheader()
                writer.writerows(rows)
            results[f"{stem}|{name}"] = stats
            print(f"[{stem}] {name}: {stats}")
    (OUT_DIR / "e8_summary.json").write_text(json.dumps(results, indent=2))
    print("wrote data/e8/e8_summary.json")


if __name__ == "__main__":
    main()
