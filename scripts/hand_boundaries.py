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


def _motion_label(assessment: ha.HandSideAssessment) -> tuple[str, float | None]:
    evidence = assessment.evidence
    signed = evidence.slope_px_per_frame
    if signed is None:
        signed = evidence.radial_px_per_frame
    if evidence.n_points < 3 or signed is None:
        return "INSUFFICIENT", signed
    if signed < -0.5:
        return "APPROACHING", signed
    if signed > 0.5:
        return "SEPARATING", signed
    return "NEUTRAL", signed


def _reason(boundary_type: str, assessment: ha.HandSideAssessment, motion: str) -> str:
    if assessment.post_contact:
        return "possible + recent very_near (post_contact)"
    if assessment.band == "STRONG":
        return "very_near"
    if assessment.band == "POSSIBLE" and assessment.entry_support and boundary_type == "END":
        return "possible + approaching"
    if assessment.band == "POSSIBLE" and assessment.exit_support and boundary_type == "START":
        return "possible + separating"
    if assessment.band == "FAR":
        return "far"
    if motion == "INSUFFICIENT":
        return "insufficient motion"
    return assessment.band.lower()


def assess_boundary(track_id: int, boundary_type: str, points: list[BoundaryPoint], hands_by_frame: dict) -> BoundaryAssessment:
    if boundary_type not in {"START", "END"}:
        raise ValueError("boundary_type must be START or END")
    if not points:
        raise ValueError("boundary requires at least one observed point")
    window = points[:5] if boundary_type == "START" else points[-5:]
    ha_points = [ha.TrackletPoint(p.frame, p.x, p.y) for p in window]
    scale = ha._latest_body_scale(ha_points, hands_by_frame)
    results: dict[str, HandBoundaryAssessment] = {}
    for side in ("LEFT", "RIGHT"):
        key = side.lower()
        ball, wrist = ha._synchronized_samples(ha_points, hands_by_frame, key, 5)
        side_assessment = ha._assess_side(
            key, ball, wrist, scale, ha._import_hf_ho()[0], ha.HandAssociationConfig(),
            anchor_index=(0 if boundary_type == "START" else len(ball) - 1),
            hand_confidence=(hands_by_frame.get(window[0 if boundary_type == "START" else -1].frame, {})
                             .get(f"{key}_confidence")),
        )
        motion, signed = _motion_label(side_assessment)
        results[side] = HandBoundaryAssessment(
            proximity={"STRONG": "VERY_NEAR", "POSSIBLE": "POSSIBLE", "FAR": "FAR", "MISSING": "FAR"}[side_assessment.band],
            endpoint_distance_px=side_assessment.evidence.distance_px,
            recent_min_distance_px=side_assessment.evidence.min_distance_px,
            endpoint_distance_normalized=side_assessment.evidence.distance_normalized,
            recent_min_distance_normalized=side_assessment.evidence.min_distance_normalized,
            n_synchronized=side_assessment.evidence.n_points,
            motion=motion,
            signed_trend=signed,
            hand_evidence=(side_assessment.entry_support if boundary_type == "END" else side_assessment.exit_support),
            post_contact=side_assessment.post_contact,
            reason=_reason(boundary_type, side_assessment, motion),
        )
    eligible = tuple(side for side in ("LEFT", "RIGHT") if results[side].hand_evidence)
    preferred = None
    ambiguous = False
    if len(eligible) == 1:
        preferred = eligible[0]
    elif len(eligible) == 2:
        a, b = (results[s] for s in eligible)
        da = a.endpoint_distance_normalized if a.endpoint_distance_normalized is not None else a.endpoint_distance_px
        db = b.endpoint_distance_normalized if b.endpoint_distance_normalized is not None else b.endpoint_distance_px
        if da is None or db is None:
            ambiguous = True
        elif abs(da - db) <= (ha.HandAssociationConfig().side_tie_normalized if a.endpoint_distance_normalized is not None and b.endpoint_distance_normalized is not None else 15.0):
            ambiguous = True
        else:
            preferred = eligible[0] if da < db else eligible[1]
        if ambiguous:
            preferred = None
    return BoundaryAssessment(track_id, boundary_type, points[0 if boundary_type == "START" else -1].frame,
                              points[0 if boundary_type == "START" else -1].x,
                              points[0 if boundary_type == "START" else -1].y,
                              results, eligible, preferred, ambiguous)


def assess_all(tracklets: dict[int, list[BoundaryPoint]], hands_by_frame: dict) -> list[BoundaryAssessment]:
    out = []
    for tid in sorted(tracklets):
        for kind in ("START", "END"):
            out.append(assess_boundary(tid, kind, tracklets[tid], hands_by_frame))
    return out


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
    cfg = ha.HandAssociationConfig()
    hands_by_frame = ha._load_hands_by_frame(args.hands, cfg.confidence_threshold)
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
