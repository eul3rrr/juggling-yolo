#!/usr/bin/env python3
"""Independent observed-track boundary and ball-to-anatomical-hand assessment."""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hand_association as ha


@dataclass(frozen=True)
class BoundaryPoint:
    frame: int
    x: float
    y: float


@dataclass(frozen=True)
class HandBoundaryAssessment:
    proximity: str
    endpoint_distance_px: float | None
    recent_min_distance_px: float | None
    endpoint_distance_normalized: float | None
    recent_min_distance_normalized: float | None
    n_synchronized: int
    motion: str
    signed_trend: float | None
    hand_evidence: bool
    post_contact: bool
    reason: str


@dataclass(frozen=True)
class BoundaryAssessment:
    track_id: int
    boundary_type: str
    boundary_frame: int
    boundary_x: float
    boundary_y: float
    hand_results: dict[str, HandBoundaryAssessment]
    eligible_hands: tuple[str, ...]
    preferred_hand: str | None
    ambiguous: bool


CONFIG = ha.HandAssociationConfig()
HAND_FEATURES, _ = ha._import_hf_ho()


def load_observed_tracklets(path: Path) -> dict[int, list[BoundaryPoint]]:
    out: dict[int, list[BoundaryPoint]] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("observed") != "1":
                continue
            tid = int(row["track_id"])
            out.setdefault(tid, []).append(
                BoundaryPoint(int(row["frame"]), float(row["center_x"]), float(row["center_y"]))
            )
    for points in out.values():
        points.sort(key=lambda p: p.frame)
    return out


def _proximity(evidence: ha.HandEvidence) -> str:
    """Use normalized distance first; raw pixel distance is fallback only."""
    if evidence.distance_normalized is not None:
        if evidence.distance_normalized <= CONFIG.strong_max_normalized:
            return "VERY_NEAR"
        if evidence.distance_normalized <= CONFIG.possible_max_normalized:
            return "POSSIBLE"
        return "FAR"
    if evidence.distance_px is not None:
        if evidence.distance_px <= CONFIG.strong_max_raw_px:
            return "VERY_NEAR"
        if evidence.distance_px <= CONFIG.possible_max_raw_px:
            return "POSSIBLE"
    return "FAR"


def _motion_label(evidence: ha.HandEvidence) -> tuple[str, float | None]:
    signed = evidence.slope_px_per_frame
    if signed is None:
        signed = evidence.radial_px_per_frame
    if evidence.n_points < 3 or signed is None:
        return "INSUFFICIENT", signed
    if signed < -CONFIG.min_abs_slope_px_per_frame:
        return "APPROACHING", signed
    if signed > CONFIG.exit_min_abs_slope_px_per_frame:
        return "SEPARATING", signed
    return "NEUTRAL", signed


def _assess_side(boundary_type: str, ball_points: list[ha.TrackletPoint], hand_xy: dict,
                 scale: float | None, side: str) -> HandBoundaryAssessment:
    key = side.lower()
    synced_ball, synced_hand = ha._synchronized_samples(ball_points, hand_xy, key, 5)
    evidence = ha._hand_distance_window(
        synced_ball, synced_hand, scale, HAND_FEATURES,
        anchor_index=(0 if boundary_type == "START" else len(synced_ball) - 1),
    )
    proximity = _proximity(evidence)
    motion, signed = _motion_label(evidence)
    very_near_recent = (
        evidence.min_distance_normalized is not None
        and evidence.min_distance_normalized <= CONFIG.strong_max_normalized
    ) or (
        evidence.min_distance_normalized is None
        and evidence.min_distance_px is not None
        and evidence.min_distance_px <= CONFIG.strong_max_raw_px
    )
    recent_contact = (
        boundary_type == "END"
        and proximity == "POSSIBLE"
        and very_near_recent
        and evidence.n_points > 0
    )
    if boundary_type == "END":
        hand_evidence = proximity == "VERY_NEAR" or (
            proximity == "POSSIBLE" and (motion == "APPROACHING" or recent_contact)
        )
    else:
        hand_evidence = proximity == "VERY_NEAR" or (
            proximity == "POSSIBLE" and motion == "SEPARATING"
        )
    post_contact = recent_contact
    if proximity == "VERY_NEAR":
        reason = "very_near"
    elif boundary_type == "END" and recent_contact:
        reason = "possible + recent very_near (post_contact)"
    elif boundary_type == "END" and proximity == "POSSIBLE" and motion == "APPROACHING":
        reason = "possible + approaching"
    elif boundary_type == "START" and proximity == "POSSIBLE" and motion == "SEPARATING":
        reason = "possible + separating"
    elif proximity == "FAR":
        reason = "far"
    elif motion == "INSUFFICIENT":
        reason = "insufficient motion"
    else:
        reason = proximity.lower()
    return HandBoundaryAssessment(
        proximity, evidence.distance_px, evidence.min_distance_px,
        evidence.distance_normalized, evidence.min_distance_normalized,
        evidence.n_points, motion, signed, hand_evidence, post_contact, reason,
    )


def assess_boundary(track_id: int, boundary_type: str, points: list[BoundaryPoint], hands_by_frame: dict) -> BoundaryAssessment:
    if boundary_type not in {"START", "END"}:
        raise ValueError("boundary_type must be START or END")
    if not points:
        raise ValueError("boundary requires at least one observed point")
    window = points[:5] if boundary_type == "START" else points[-5:]
    ha_points = [ha.TrackletPoint(p.frame, p.x, p.y) for p in window]
    scale = ha._latest_body_scale(ha_points, hands_by_frame)
    results = {side: _assess_side(boundary_type, ha_points, hands_by_frame, scale, side)
               for side in ("LEFT", "RIGHT")}
    eligible = tuple(side for side in ("LEFT", "RIGHT") if results[side].hand_evidence)
    preferred = None
    ambiguous = False
    if len(eligible) == 1:
        preferred = eligible[0]
    elif len(eligible) == 2:
        a, b = (results[s] for s in eligible)
        da = a.endpoint_distance_normalized if a.endpoint_distance_normalized is not None else a.endpoint_distance_px
        db = b.endpoint_distance_normalized if b.endpoint_distance_normalized is not None else b.endpoint_distance_px
        tie = CONFIG.side_tie_normalized if a.endpoint_distance_normalized is not None and b.endpoint_distance_normalized is not None else 15.0
        if da is None or db is None or abs(da - db) <= tie:
            ambiguous = True
        else:
            preferred = eligible[0] if da < db else eligible[1]
    point = points[0 if boundary_type == "START" else -1]
    return BoundaryAssessment(track_id, boundary_type, point.frame, point.x, point.y,
                              results, eligible, preferred, ambiguous)


def assess_all(tracklets: dict[int, list[BoundaryPoint]], hands_by_frame: dict) -> list[BoundaryAssessment]:
    return [assess_boundary(tid, kind, tracklets[tid], hands_by_frame)
            for tid in sorted(tracklets) for kind in ("START", "END")]


def write_csv(assessments: list[BoundaryAssessment], path: Path) -> None:
    fields = ["track_id", "boundary_type", "boundary_frame", "boundary_x", "boundary_y", "hand",
              "endpoint_distance_px", "recent_min_distance_px", "endpoint_distance_normalized",
              "recent_min_distance_normalized", "n_synchronized_samples", "motion", "signed_trend",
              "proximity_band", "hand_evidence", "post_contact", "eligible_hand_set", "preferred_hand",
              "ambiguous", "evidence_reason"]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for a in assessments:
            for side, r in a.hand_results.items():
                w.writerow({"track_id": a.track_id, "boundary_type": a.boundary_type,
                            "boundary_frame": a.boundary_frame, "boundary_x": f"{a.boundary_x:.6f}",
                            "boundary_y": f"{a.boundary_y:.6f}", "hand": side,
                            "endpoint_distance_px": _fmt(r.endpoint_distance_px),
                            "recent_min_distance_px": _fmt(r.recent_min_distance_px),
                            "endpoint_distance_normalized": _fmt(r.endpoint_distance_normalized),
                            "recent_min_distance_normalized": _fmt(r.recent_min_distance_normalized),
                            "n_synchronized_samples": r.n_synchronized, "motion": r.motion,
                            "signed_trend": _fmt(r.signed_trend), "proximity_band": r.proximity,
                            "hand_evidence": int(r.hand_evidence), "post_contact": int(r.post_contact),
                            "eligible_hand_set": "{" + ",".join(a.eligible_hands) + "}",
                            "preferred_hand": a.preferred_hand or "", "ambiguous": int(a.ambiguous),
                            "evidence_reason": r.reason})


def _fmt(v):
    return "" if v is None else f"{v:.6f}"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tracklets", type=Path, required=True)
    p.add_argument("--hands", type=Path, required=True)
    p.add_argument("--output-csv", type=Path, required=True)
    args = p.parse_args()
    tracklets = load_observed_tracklets(args.tracklets)
    hands_by_frame = ha._load_hands_by_frame(args.hands, CONFIG.confidence_threshold)
    assessments = assess_all(tracklets, hands_by_frame)
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    write_csv(assessments, args.output_csv)
    for a in assessments:
        parts = [f"{s}={'HAND_EVIDENCE' if r.hand_evidence else r.proximity.lower()} ({r.reason})" for s, r in a.hand_results.items()]
        print(f"{a.boundary_type} track {a.track_id} @{a.boundary_frame}: " + ", ".join(parts))
    print(f"boundaries: START={sum(a.boundary_type == 'START' for a in assessments)} END={sum(a.boundary_type == 'END' for a in assessments)}")
    print(f"with_hand_evidence: START={sum(a.boundary_type == 'START' and bool(a.eligible_hands) for a in assessments)} END={sum(a.boundary_type == 'END' and bool(a.eligible_hands) for a in assessments)}")
    print(f"ambiguous_boundaries: {sum(a.ambiguous for a in assessments)}")


if __name__ == "__main__":
    main()
