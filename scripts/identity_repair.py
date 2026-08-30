"""Hand Association Engine v1: identity_repair_v1.

Two-stage conservative identity repair pipeline:

  Stage 1: existing AIRBORNE / ballistic stitching
            (re-used exactly; never weakened)

  Stage 2: HAND recovery on remaining UNMATCHED boundaries
            (FIFO + per-hand queues; additive; precision-oriented)

The output is:

  * A final chain mapping CSV (track_id -> chain_id, where chain
    is the new "airborne + hand" persistent identity).
  * An accepted-edge CSV with one row per accepted AIRBORNE or
    HAND link, recording source, target, mode, hand side, frame
    range, evidence tier, and provenance.
  * A hand-recovery diagnostic CSV that records every hand
    proposal the engine considered and why it was admitted,
    rejected, or blocked by Stage 1.
  * A text / JSON report of summary statistics.

The final combined identity graph is validated for:

  * max one outgoing edge per source chain,
  * max one incoming edge per target chain,
  * strictly forward time (source.end < target.start),
  * acyclic.

Run on the full canonical video:
    videos/identical_balls_trick_000_018.mp4
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# Make the engine importable without altering sys.path globally.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import hand_association as ha  # noqa: E402


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Tracklet:
    track_id: int
    first_frame: int
    last_frame: int
    points: list[tuple[int, float, float]]  # (frame, x, y)


@dataclass
class AcceptedEdge:
    """One accepted identity edge.  source and target are chain
    IDs (post-stage-1 chains).  ``mode`` is "AIRBORNE" or "HAND"."""
    source: int
    target: int
    mode: str
    hand: str = ""            # "left" / "right" / "ambiguous" / "" (airborne)
    source_end_frame: int = 0
    target_start_frame: int = 0
    gap_frames: int = 0
    evidence_tier: str = ""
    features: dict = field(default_factory=dict)
    provenance: str = ""      # "baseline" or "hand_recovery"
    rejected_reason: str = ""  # populated for diagnostic records


@dataclass
class ChainAggregate:
    """A Stage-1 chain: a list of constituent raw tracklet IDs,
    plus its first and last frame in the chain."""
    chain_id: int
    tracklet_ids: list[int]
    first_frame: int
    last_frame: int


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_tracklets(path: Path) -> dict[int, Tracklet]:
    raw: dict[int, list[tuple[int, float, float]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("observed") or "1") != "1":
                continue
            try:
                tid = int(row["track_id"])
                fr = int(row["frame"])
                cx = float(row["center_x"])
                cy = float(row["center_y"])
            except (KeyError, ValueError):
                continue
            raw[tid].append((fr, cx, cy))
    out: dict[int, Tracklet] = {}
    for tid, pts in raw.items():
        pts.sort(key=lambda p: p[0])
        out[tid] = Tracklet(track_id=tid, first_frame=pts[0][0],
                            last_frame=pts[-1][0], points=pts)
    return out


def load_chain_mapping(path: Path) -> dict[int, int]:
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


def load_accepted_stitches(path: Path) -> list[tuple[int, int]]:
    """Return a list of (source_tracklet, target_tracklet) pairs."""
    if not path.is_file():
        return []
    out: list[tuple[int, int]] = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                if int(row.get("accepted") or "0") != 1:
                    continue
                src = int(row["source_tracklet"])
                tgt = int(row["candidate_tracklet"])
            except (KeyError, ValueError):
                continue
            out.append((src, tgt))
    return out


def build_stage1_chains(tracklets: dict[int, Tracklet],
                         chain_mapping: dict[int, int],
                         accepted: list[tuple[int, int]]
                         ) -> tuple[dict[int, int], dict[int, ChainAggregate]]:
    """Return (track_id -> chain_id, chain_id -> ChainAggregate)."""
    # The chain_mapping already groups tracklets into chains.  Use it
    # directly.  Accepted stitches that are NOT already reflected in
    # chain_mapping (i.e. the chain_mapping is the v0 baseline that
    # the v1 airborne pipeline produced) are folded in below.
    by_chain: dict[int, list[int]] = defaultdict(list)
    for tid, cid in chain_mapping.items():
        by_chain[cid].append(tid)

    # The "accepted" list is in the existing pipeline's accepted-
    # stitches CSV.  We need to translate these (tracklet-pair) into
    # chain-pair edges.  The chain_mapping is the authoritative
    # partition; if accepted includes pairs whose endpoints are
    # already in the same chain (post-stitch), we keep the chain.
    # Otherwise we fold them into Stage-1 chain edges.
    tracklet_to_chain = dict(chain_mapping)

    # Build intra-chain accepted edges (already merged):
    accepted_chain_edges: list[tuple[int, int]] = []
    seen_pairs: set[tuple[int, int]] = set()
    for src, tgt in accepted:
        s_chain = tracklet_to_chain.get(src)
        t_chain = tracklet_to_chain.get(tgt)
        if s_chain is None or t_chain is None:
            continue
        if s_chain == t_chain:
            continue  # already in same chain
        key = (s_chain, t_chain)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        accepted_chain_edges.append(key)

    # If a chain pair appears multiple times in accepted, the
    # chain_mapping may not yet reflect it.  In that case, fold
    # all the constituent tracklets into the source chain so the
    # chains remain a true partition.
    for src_chain, tgt_chain in accepted_chain_edges:
        if src_chain == tgt_chain:
            continue
        # Merge tgt into src.
        for tid, cid in list(tracklet_to_chain.items()):
            if cid == tgt_chain:
                tracklet_to_chain[tid] = src_chain

    # Re-derive by_chain from the updated mapping.
    by_chain = defaultdict(list)
    for tid, cid in tracklet_to_chain.items():
        by_chain[cid].append(tid)

    chain_aggregates: dict[int, ChainAggregate] = {}
    for cid, tids in by_chain.items():
        # Use the union of constituent tracklet ranges.
        first_frame = min(tracklets[t].first_frame for t in tids
                          if t in tracklets)
        last_frame = max(tracklets[t].last_frame for t in tids
                         if t in tracklets)
        chain_aggregates[cid] = ChainAggregate(
            chain_id=cid, tracklet_ids=sorted(tids),
            first_frame=first_frame, last_frame=last_frame)
    return tracklet_to_chain, chain_aggregates


# ---------------------------------------------------------------------------
# Stage 1 edges
# ---------------------------------------------------------------------------

def stage1_edges(accepted: list[tuple[int, int]],
                 tracklet_to_chain: dict[int, int],
                 tracklets: dict[int, Tracklet],
                 chain_aggregates: dict[int, ChainAggregate]
                 ) -> list[AcceptedEdge]:
    """Build a list of AcceptedEdge for every accepted airborne link
    that is NOT already an intra-chain collapse.  Each chain-level
    edge gets its own row with the union of constituent frames."""
    edges: list[AcceptedEdge] = []
    seen: set[tuple[int, int]] = set()
    for src, tgt in accepted:
        s_chain = tracklet_to_chain.get(src)
        t_chain = tracklet_to_chain.get(tgt)
        if s_chain is None or t_chain is None:
            continue
        if s_chain == t_chain:
            continue
        key = (s_chain, t_chain)
        if key in seen:
            continue
        seen.add(key)
        s_agg = chain_aggregates[s_chain]
        t_agg = chain_aggregates[t_chain]
        src_end = s_agg.last_frame
        tgt_start = t_agg.first_frame
        edges.append(AcceptedEdge(
            source=s_chain, target=t_chain, mode="AIRBORNE",
            source_end_frame=src_end, target_start_frame=tgt_start,
            gap_frames=max(0, tgt_start - src_end - 1),
            evidence_tier="baseline",
            features={},
            provenance="baseline",
        ))
    return edges


# ---------------------------------------------------------------------------
# Stage 2: hand recovery on remaining unmatched boundaries
# ---------------------------------------------------------------------------

@dataclass
class HandProposal:
    """A hand-engine proposal for one source -> target bridge."""
    source_chain: int
    target_chain: int
    hand: str                  # "left" / "right" / "ambiguous"
    source_end_frame: int
    target_start_frame: int
    gap_frames: int
    evidence_tier: str         # "STRONG" / "POSSIBLE" / "POSSIBLE_POST_CONTACT"
    source_min_distance_norm: float
    source_endpoint_norm: float
    target_min_distance_norm: float
    target_endpoint_norm: float
    n_points_source: int
    n_points_target: int
    post_contact: bool
    decision: str              # "admitted" / "blocked_by_stage1" /
                                # "rejected_hand_unambiguous" / etc.
    rejection_reason: str = ""


def _boundary_hand_features(chain: ChainAggregate,
                            tracklets: dict[int, Tracklet],
                            hand_xy_by_frame: dict,
                            cfg: ha.HandAssociationConfig,
                            hand_features,
                            fps: float,
                            window: int = 5) -> tuple[ha.HandSideAssessment,
                                                     ha.HandSideAssessment]:
    """Compute left/right HandSideAssessment for a chain END or START
    using the n_window of ball observations at the relevant end of
    the chain."""
    tids = [t for t in chain.tracklet_ids if t in tracklets]
    if not tids:
        return (ha.HandSideAssessment(side="?", band="MISSING",
                                     evidence=ha.HandEvidence(
                                         side="?", distance_px=None,
                                         distance_normalized=None,
                                         min_distance_px=None,
                                         min_distance_normalized=None,
                                         slope_px_per_frame=None,
                                         radial_px_per_frame=None,
                                         n_points=0, hand_confidence=None,
                                         motion_sign="insufficient"),
                                     entry_support=False,
                                     exit_support=False),
                ha.HandSideAssessment(side="?", band="MISSING",
                                     evidence=ha.HandEvidence(
                                         side="?", distance_px=None,
                                         distance_normalized=None,
                                         min_distance_px=None,
                                         min_distance_normalized=None,
                                         slope_px_per_frame=None,
                                         radial_px_per_frame=None,
                                         n_points=0, hand_confidence=None,
                                         motion_sign="insufficient"),
                                     entry_support=False,
                                     exit_support=False))
    # Build a unified sorted list of all observations across all
    # constituent tracklets of this chain.
    all_pts: list[ha.TrackletPoint] = []
    for tid in tids:
        for fr, cx, cy in tracklets[tid].points:
            all_pts.append(ha.TrackletPoint(frame=fr, center_x=cx,
                                            center_y=cy))
    all_pts.sort(key=lambda p: p.frame)
    # For an END evaluation, use the last ``window`` points.  For a
    # START, use the first ``window``.  We return END-style evidence
    # by default; the caller decides orientation.
    end_window = all_pts[-window:]
    per_frame_scale = ha._latest_body_scale(end_window, hand_xy_by_frame)
    synced_left_ball, synced_left = ha._synchronized_samples(
        end_window, hand_xy_by_frame, "left", cfg.n_window)
    synced_right_ball, synced_right = ha._synchronized_samples(
        end_window, hand_xy_by_frame, "right", cfg.n_window)
    anchor_idx_left = len(synced_left_ball) - 1
    anchor_idx_right = len(synced_right_ball) - 1
    last_frame = all_pts[-1].frame
    row = hand_xy_by_frame.get(last_frame, {})
    conf_left = row.get("left_confidence")
    conf_right = row.get("right_confidence")
    left_a = ha._assess_side("left", synced_left_ball, synced_left,
                             per_frame_scale, hand_features, cfg,
                             anchor_index=anchor_idx_left,
                             hand_confidence=conf_left, fps=fps)
    right_a = ha._assess_side("right", synced_right_ball, synced_right,
                              per_frame_scale, hand_features, cfg,
                              anchor_index=anchor_idx_right,
                              hand_confidence=conf_right, fps=fps)
    return left_a, right_a


def _start_features(chain: ChainAggregate,
                   tracklets: dict[int, Tracklet],
                   hand_xy_by_frame: dict,
                   cfg: ha.HandAssociationConfig,
                   hand_features,
                   fps: float,
                   window: int = 5) -> tuple[ha.HandSideAssessment,
                                            ha.HandSideAssessment]:
    """Like :func:`_boundary_hand_features` but for a chain START."""
    tids = [t for t in chain.tracklet_ids if t in tracklets]
    if not tids:
        return _boundary_hand_features(chain, tracklets, hand_xy_by_frame,
                                        cfg, hand_features, fps, window)
    all_pts: list[ha.TrackletPoint] = []
    for tid in tids:
        for fr, cx, cy in tracklets[tid].points:
            all_pts.append(ha.TrackletPoint(frame=fr, center_x=cx,
                                            center_y=cy))
    all_pts.sort(key=lambda p: p.frame)
    start_window = all_pts[:window]
    per_frame_scale = ha._latest_body_scale(start_window, hand_xy_by_frame)
    synced_left_ball, synced_left = ha._synchronized_samples(
        start_window, hand_xy_by_frame, "left", cfg.n_window)
    synced_right_ball, synced_right = ha._synchronized_samples(
        start_window, hand_xy_by_frame, "right", cfg.n_window)
    first_frame = all_pts[0].frame
    row = hand_xy_by_frame.get(first_frame, {})
    conf_left = row.get("left_confidence")
    conf_right = row.get("right_confidence")
    left_a = ha._assess_side("left", synced_left_ball, synced_left,
                             per_frame_scale, hand_features, cfg,
                             anchor_index=0,
                             hand_confidence=conf_left, fps=fps)
    right_a = ha._assess_side("right", synced_right_ball, synced_right,
                              per_frame_scale, hand_features, cfg,
                              anchor_index=0,
                              hand_confidence=conf_right, fps=fps)
    return left_a, right_a


def stage2_hand_recovery(chain_aggregates: dict[int, ChainAggregate],
                         tracklets: dict[int, Tracklet],
                         hand_xy_by_frame: dict,
                         stage1_used: set[tuple[int, int]],
                         cfg: ha.HandAssociationConfig,
                         fps: float,
                         ) -> tuple[list[HandProposal],
                                    list[AcceptedEdge]]:
    """Run the hand engine on unmatched chain boundaries.

    A boundary is "unmatched" if no Stage-1 edge touches it on the
    relevant side.  For each chain END with no outgoing stage-1
    edge, we look at hand evidence and, for each chain START with
    no incoming stage-1 edge, we look at hand evidence.  The
    engine proposes pairs; we admit only those that do not
    conflict with Stage 1 AND do not create sustained
    simultaneous overlap in the resulting merged chain.
    """
    hand_features, _ = ha._import_hf_ho()
    proposals: list[HandProposal] = []
    edges: list[AcceptedEdge] = []

    # Build boundary lookups from Stage 1.
    sources_with_outgoing: set[int] = {s for s, _ in stage1_used}
    targets_with_incoming: set[int] = {t for _, t in stage1_used}
    chains_with_no_outgoing = [c for c in chain_aggregates
                                 if c not in sources_with_outgoing]
    chains_with_no_incoming = [c for c in chain_aggregates
                                 if c not in targets_with_incoming]

    # Live chain partition.  Initially every chain is its own
    # root.  When we admit a hand bridge, the source and target
    # are unioned.  Sustained-overlap checks use this live
    # partition so that the engine is aware of which chains have
    # already been merged.
    parent: dict[int, int] = {c: c for c in chain_aggregates}
    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a: int, b: int) -> int:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
        return rb

    def _sustained_overlap_for_merge(src: int, tgt: int) -> bool:
        """Would unioning source and target create a sustained
        (>=6 frame) overlap among the constituent tracklets of
        the merged chain?"""
        merged = find(union(src, tgt))  # this mutates parent
        # Union back out so we can keep the partition unchanged
        # if the caller decides to reject.  But because we just
        # mutated, this is awkward.  Instead, simulate without
        # mutating: compute the merged set manually.
        # Undo: rebuild parent for the affected roots.
        # For our purposes, the partition mutation is fine if
        # the caller checks BEFORE committing the bridge; the
        # caller will rebuild the partition from the final edges
        # via coalesce_chains anyway.
        # Re-derive the set of constituent tracklets for the
        # merged root.
        involved = []
        for c in chain_aggregates:
            if find(c) == merged:
                involved.append(c)
        # Check pairwise overlap of time ranges among the
        # constituent chain aggregates.
        ranges = []
        for c in involved:
            agg = chain_aggregates[c]
            ranges.append((agg.first_frame, agg.last_frame, c))
        ranges.sort()
        for i in range(1, len(ranges)):
            prev_start, prev_end, _ = ranges[i - 1]
            cur_start, cur_end, _ = ranges[i]
            if cur_start <= prev_end:
                overlap = prev_end - cur_start + 1
                if overlap >= 6:
                    return True
        return False

    # Pre-compute END-side evidence per chain (the "incoming hand"
    # evidence: a track ending near a hand).
    end_evidence: dict[int, tuple[ha.HandSideAssessment,
                                    ha.HandSideAssessment]] = {}
    for cid in chains_with_no_outgoing:
        end_evidence[cid] = _boundary_hand_features(
            chain_aggregates[cid], tracklets, hand_xy_by_frame,
            cfg, hand_features, fps, cfg.n_window)
    # Pre-compute START-side evidence per chain (the "outgoing hand"
    # evidence: a track being born near a hand).
    start_evidence: dict[int, tuple[ha.HandSideAssessment,
                                      ha.HandSideAssessment]] = {}
    for cid in chains_with_no_incoming:
        start_evidence[cid] = _start_features(
            chain_aggregates[cid], tracklets, hand_xy_by_frame,
            cfg, hand_features, fps, cfg.n_window)

    # Sort by chronological order so the FIFO model picks the
    # oldest end before the newest.
    end_evidence_keys = sorted(chains_with_no_outgoing,
                                key=lambda c: chain_aggregates[c].last_frame)
    start_evidence_keys = sorted(chains_with_no_incoming,
                                  key=lambda c: chain_aggregates[c].first_frame)

    for src_cid in end_evidence_keys:
        src_agg = chain_aggregates[src_cid]
        left_a, right_a = end_evidence[src_cid]
        chosen, side_label, band = ha._pick_entry_side(
            {"left": left_a, "right": right_a}, cfg)
        if chosen == "skip":
            proposals.append(HandProposal(
                source_chain=src_cid, target_chain=-1,
                hand="", source_end_frame=src_agg.last_frame,
                target_start_frame=0, gap_frames=0,
                evidence_tier="NONE",
                source_min_distance_norm=min(
                    left_a.evidence.min_distance_normalized or 1.0,
                    right_a.evidence.min_distance_normalized or 1.0),
                source_endpoint_norm=min(
                    left_a.evidence.distance_normalized or 1.0,
                    right_a.evidence.distance_normalized or 1.0),
                target_min_distance_norm=0.0,
                target_endpoint_norm=0.0,
                n_points_source=max(left_a.evidence.n_points,
                                     right_a.evidence.n_points),
                n_points_target=0,
                post_contact=left_a.post_contact or right_a.post_contact,
                decision="no_evidence",
                rejection_reason="band not STRONG or POSSIBLE w/ motion",
            ))
            continue
        # Find the earliest eligible start after this end.
        bridge_proposed = False
        for tgt_cid in start_evidence_keys:
            if tgt_cid in {e.target for e in edges}:
                # Already used as a target by a previously admitted bridge.
                continue
            if tgt_cid == src_cid:
                continue
            if tgt_cid in sources_with_outgoing:
                # Already consumed by Stage 1 in the source role.
                continue
            tgt_agg = chain_aggregates[tgt_cid]
            if tgt_agg.first_frame <= src_agg.last_frame:
                # Not forward in time.
                continue
            gap = tgt_agg.first_frame - src_agg.last_frame
            # Bridge gap policy:
            #   * STRONG band: up to 0.5 seconds (30 frames at 60 fps).
            #   * POSSIBLE band: up to 0.2 seconds (12 frames at 60 fps).
            # Anything larger than these is almost certainly
            # tracker fragmentation, not a hand event.
            if band == "STRONG":
                max_gap = int(round(0.5 * fps))
            else:
                max_gap = int(round(0.2 * fps))
            if gap > max_gap:
                proposals.append(HandProposal(
                    source_chain=src_cid, target_chain=tgt_cid,
                    hand="",
                    source_end_frame=src_agg.last_frame,
                    target_start_frame=tgt_agg.first_frame,
                    gap_frames=gap,
                    evidence_tier="NONE",
                    source_min_distance_norm=min(
                        left_a.evidence.min_distance_normalized or 1.0,
                        right_a.evidence.min_distance_normalized or 1.0),
                    source_endpoint_norm=min(
                        left_a.evidence.distance_normalized or 1.0,
                        right_a.evidence.distance_normalized or 1.0),
                    target_min_distance_norm=0.0,
                    target_endpoint_norm=0.0,
                    n_points_source=max(left_a.evidence.n_points,
                                         right_a.evidence.n_points),
                    n_points_target=0,
                    post_contact=(left_a.post_contact or right_a.post_contact),
                    decision="gap_too_large",
                    rejection_reason=(f"gap {gap} > safety_expiry "
                                       f"{cfg.safety_expiry_seconds}s"),
                ))
                continue
            sl, sr = start_evidence[tgt_cid]
            chosen_e, side_label_e, band_e = ha._pick_exit_side(
                {"left": sl, "right": sr}, cfg)
            if chosen_e == "skip":
                proposals.append(HandProposal(
                    source_chain=src_cid, target_chain=tgt_cid,
                    hand="",
                    source_end_frame=src_agg.last_frame,
                    target_start_frame=tgt_agg.first_frame,
                    gap_frames=tgt_agg.first_frame - src_agg.last_frame,
                    evidence_tier="NONE",
                    source_min_distance_norm=min(
                        left_a.evidence.min_distance_normalized or 1.0,
                        right_a.evidence.min_distance_normalized or 1.0),
                    source_endpoint_norm=min(
                        left_a.evidence.distance_normalized or 1.0,
                        right_a.evidence.distance_normalized or 1.0),
                    target_min_distance_norm=min(
                        sl.evidence.min_distance_normalized or 1.0,
                        sr.evidence.min_distance_normalized or 1.0),
                    target_endpoint_norm=min(
                        sl.evidence.distance_normalized or 1.0,
                        sr.evidence.distance_normalized or 1.0),
                    n_points_source=max(left_a.evidence.n_points,
                                         right_a.evidence.n_points),
                    n_points_target=max(sl.evidence.n_points,
                                          sr.evidence.n_points),
                    post_contact=(left_a.post_contact or right_a.post_contact),
                    decision="no_evidence",
                    rejection_reason="start band not STRONG or POSSIBLE w/ motion",
                ))
                continue
            # Cross-side match: the END chose `side_label`, the
            # START must agree.
            if side_label_e != "ambiguous" and side_label != "ambiguous" \
                    and side_label != side_label_e:
                proposals.append(HandProposal(
                    source_chain=src_cid, target_chain=tgt_cid,
                    hand="",
                    source_end_frame=src_agg.last_frame,
                    target_start_frame=tgt_agg.first_frame,
                    gap_frames=tgt_agg.first_frame - src_agg.last_frame,
                    evidence_tier="NONE",
                    source_min_distance_norm=min(
                        left_a.evidence.min_distance_normalized or 1.0,
                        right_a.evidence.min_distance_normalized or 1.0),
                    source_endpoint_norm=min(
                        left_a.evidence.distance_normalized or 1.0,
                        right_a.evidence.distance_normalized or 1.0),
                    target_min_distance_norm=min(
                        sl.evidence.min_distance_normalized or 1.0,
                        sr.evidence.min_distance_normalized or 1.0),
                    target_endpoint_norm=min(
                        sl.evidence.distance_normalized or 1.0,
                        sr.evidence.distance_normalized or 1.0),
                    n_points_source=max(left_a.evidence.n_points,
                                         right_a.evidence.n_points),
                    n_points_target=max(sl.evidence.n_points,
                                          sr.evidence.n_points),
                    post_contact=(left_a.post_contact or right_a.post_contact),
                    decision="side_mismatch",
                    rejection_reason=(f"end side {side_label} != "
                                       f"start side {side_label_e}"),
                ))
                continue
            # Both sides agree.  Test the post-merge overlap
            # before committing.  We snapshot the partition so
            # we can roll back on rejection.
            parents_snapshot = dict(parent)
            merged_root = union(src_cid, tgt_cid)
            if _sustained_overlap_for_merge(src_cid, tgt_cid):
                # Roll back.  The bridge would create
                # physically impossible simultaneous
                # observations in the merged chain.
                parent.clear()
                parent.update(parents_snapshot)
                proposals.append(HandProposal(
                    source_chain=src_cid, target_chain=tgt_cid,
                    hand=side_label,
                    source_end_frame=src_agg.last_frame,
                    target_start_frame=tgt_agg.first_frame,
                    gap_frames=tgt_agg.first_frame - src_agg.last_frame,
                    evidence_tier=band,
                    source_min_distance_norm=min(
                        left_a.evidence.min_distance_normalized or 1.0,
                        right_a.evidence.min_distance_normalized or 1.0),
                    source_endpoint_norm=min(
                        left_a.evidence.distance_normalized or 1.0,
                        right_a.evidence.distance_normalized or 1.0),
                    target_min_distance_norm=min(
                        sl.evidence.min_distance_normalized or 1.0,
                        sr.evidence.min_distance_normalized or 1.0),
                    target_endpoint_norm=min(
                        sl.evidence.distance_normalized or 1.0,
                        sr.evidence.distance_normalized or 1.0),
                    n_points_source=max(left_a.evidence.n_points,
                                         right_a.evidence.n_points),
                    n_points_target=max(sl.evidence.n_points,
                                          sr.evidence.n_points),
                    post_contact=(left_a.post_contact or right_a.post_contact),
                    decision="rejected_overlap",
                    rejection_reason="merge creates sustained simultaneous overlap",
                ))
                continue
            # The merge is acceptable.  Commit the bridge.
            hand = side_label
            edge = AcceptedEdge(
                source=src_cid, target=tgt_cid, mode="HAND",
                hand=hand,
                source_end_frame=src_agg.last_frame,
                target_start_frame=tgt_agg.first_frame,
                gap_frames=tgt_agg.first_frame - src_agg.last_frame,
                evidence_tier=band,
                features={
                    "source_min_distance_norm":
                        left_a.evidence.min_distance_normalized
                        if side_label in ("left", "ambiguous")
                        else right_a.evidence.min_distance_normalized,
                    "source_endpoint_norm":
                        left_a.evidence.distance_normalized
                        if side_label in ("left", "ambiguous")
                        else right_a.evidence.distance_normalized,
                    "target_min_distance_norm":
                        sl.evidence.min_distance_normalized
                        if side_label in ("left", "ambiguous")
                        else sr.evidence.min_distance_normalized,
                    "target_endpoint_norm":
                        sl.evidence.distance_normalized
                        if side_label in ("left", "ambiguous")
                        else sr.evidence.distance_normalized,
                },
                provenance="hand_recovery",
            )
            edges.append(edge)
            proposals.append(HandProposal(
                source_chain=src_cid, target_chain=tgt_cid,
                hand=hand,
                source_end_frame=src_agg.last_frame,
                target_start_frame=tgt_agg.first_frame,
                gap_frames=tgt_agg.first_frame - src_agg.last_frame,
                evidence_tier=band,
                source_min_distance_norm=min(
                    left_a.evidence.min_distance_normalized or 1.0,
                    right_a.evidence.min_distance_normalized or 1.0),
                source_endpoint_norm=min(
                    left_a.evidence.distance_normalized or 1.0,
                    right_a.evidence.distance_normalized or 1.0),
                target_min_distance_norm=min(
                    sl.evidence.min_distance_normalized or 1.0,
                    sr.evidence.min_distance_normalized or 1.0),
                target_endpoint_norm=min(
                    sl.evidence.distance_normalized or 1.0,
                    sr.evidence.distance_normalized or 1.0),
                n_points_source=max(left_a.evidence.n_points,
                                     right_a.evidence.n_points),
                n_points_target=max(sl.evidence.n_points,
                                      sr.evidence.n_points),
                post_contact=(left_a.post_contact or right_a.post_contact),
                decision="admitted",
            ))
            bridge_proposed = True
            break  # one end -> one bridge
        if not bridge_proposed:
            proposals.append(HandProposal(
                source_chain=src_cid, target_chain=-1,
                hand="",
                source_end_frame=src_agg.last_frame,
                target_start_frame=0, gap_frames=0,
                evidence_tier=band,
                source_min_distance_norm=min(
                    left_a.evidence.min_distance_normalized or 1.0,
                    right_a.evidence.min_distance_normalized or 1.0),
                source_endpoint_norm=min(
                    left_a.evidence.distance_normalized or 1.0,
                    right_a.evidence.distance_normalized or 1.0),
                target_min_distance_norm=0.0,
                target_endpoint_norm=0.0,
                n_points_source=max(left_a.evidence.n_points,
                                     right_a.evidence.n_points),
                n_points_target=0,
                post_contact=(left_a.post_contact or right_a.post_contact),
                decision="admitted_no_match",
                rejection_reason="no eligible start found",
            ))

    return proposals, edges


# ---------------------------------------------------------------------------
# Graph validation and final chain coalescence
# ---------------------------------------------------------------------------

def validate_graph(edges: list[AcceptedEdge],
                   tracklets: dict[int, Tracklet],
                   tracklet_to_chain: dict[int, int],
                   ) -> tuple[list[str], list[str]]:
    """Validate the combined identity graph.  Return
    ``(errors, warnings)``; ``errors`` is a list of fatal
    problems, ``warnings`` is a list of non-fatal issues for
    inspection.  Empty ``errors`` means OK.

    Checks:
      * self-loops, multi-outgoing, multi-incoming
      * forward time
      * cycle detection
      * simultaneous-frame overlap within a chain (a persistent
        chain cannot have two clearly simultaneous physical balls).
    """
    errors: list[str] = []
    outgoing: dict[int, int] = defaultdict(int)
    incoming: dict[int, int] = defaultdict(int)
    for e in edges:
        if e.source == e.target:
            errors.append(f"self-loop on chain {e.source}")
        if outgoing[e.source] > 0:
            errors.append(
                f"chain {e.source} has multiple outgoing edges")
        outgoing[e.source] += 1
        if incoming[e.target] > 0:
            errors.append(
                f"chain {e.target} has multiple incoming edges")
        incoming[e.target] += 1
        if e.target_start_frame <= e.source_end_frame:
            errors.append(
                f"non-forward edge {e.source}->{e.target} "
                f"({e.source_end_frame}->{e.target_start_frame})")
    # Cycle detection
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[int, int] = {c: WHITE for c in outgoing}
    adj: dict[int, list[int]] = defaultdict(list)
    for e in edges:
        adj[e.source].append(e.target)
    def _dfs(node: int) -> bool:
        color[node] = GRAY
        for nxt in adj.get(node, []):
            if color.get(nxt, WHITE) == GRAY:
                return True
            if color.get(nxt, WHITE) == WHITE and _dfs(nxt):
                return True
        color[node] = BLACK
        return False
    for c in list(color.keys()):
        if color[c] == WHITE and _dfs(c):
            errors.append(f"cycle detected involving chain {c}")
    # Simultaneous-frame overlap check.  If two raw tracklets exist
    # at the same frame in different chains, the chains have
    # simultaneously visible balls and cannot be safely merged.
    # This is logged as a warning, not an error: the hand engine
    # may legitimately merge chains whose constituent tracklets
    # briefly co-existed (e.g. before/after a hand event), but
    # any sustained overlap is logged so the human can inspect.
    chain_to_tracklets: dict[int, list[int]] = defaultdict(list)
    for tid, cid in tracklet_to_chain.items():
        chain_to_tracklets[cid].append(tid)
    frame_to_chains: dict[int, set[int]] = defaultdict(set)
    for cid, tids in chain_to_tracklets.items():
        for tid in tids:
            tr = tracklets.get(tid)
            if tr is None:
                continue
            for fr, _, _ in tr.points:
                frame_to_chains[fr].add(cid)
    sustained = _sustained_overlaps(frame_to_chains)
    warnings: list[str] = []
    for f, cids in sustained:
        warnings.append(
            f"chains {sorted(cids)} have simultaneous observations at "
            f"frame {f}")
    return errors, warnings


def _sustained_overlaps(frame_to_chains: dict[int, set[int]],
                       max_consecutive: int = 3) -> list[tuple[int, set[int]]]:
    out: list[tuple[int, set[int]]] = []
    last_overlap_frame: int | None = None
    last_cids: set[int] | None = None
    for f in sorted(frame_to_chains.keys()):
        cids = frame_to_chains[f]
        if len(cids) > 1:
            if last_overlap_frame is not None \
                    and f - last_overlap_frame == 1 \
                    and cids == last_cids:
                out.append((f, cids))
            else:
                # First frame of a new overlap run; record it
                # tentatively.  We only report it if it sustains.
                if last_overlap_frame is not None \
                        and f - last_overlap_frame > max_consecutive:
                    pass
            last_overlap_frame = f
            last_cids = cids
        else:
            last_overlap_frame = None
            last_cids = None
    return out


def coalesce_chains(tracklet_to_chain: dict[int, int],
                     edges: list[AcceptedEdge]
                     ) -> dict[int, int]:
    """Union-find the chains along the accepted edges to produce the
    final chain mapping.  Chain IDs are renumbered 1..N for the
    output, preserving order."""
    parent: dict[int, int] = {c: c for c in tracklet_to_chain.values()}
    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    for e in edges:
        if e.source in parent and e.target in parent:
            union(e.source, e.target)
    # Renumber.
    root_to_id: dict[int, int] = {}
    next_id = 1
    out: dict[int, int] = {}
    for tid in sorted(tracklet_to_chain.keys()):
        root = find(tracklet_to_chain[tid])
        if root not in root_to_id:
            root_to_id[root] = next_id
            next_id += 1
        out[tid] = root_to_id[root]
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tracklets", required=True, type=Path)
    p.add_argument("--hands", required=True, type=Path)
    p.add_argument("--chain-mapping", required=True, type=Path)
    p.add_argument("--accepted-stitches", required=True, type=Path)
    p.add_argument("--fps", type=float, default=60.0)
    p.add_argument("--output-dir", required=True, type=Path)
    p.add_argument("--label-csv", type=Path, default=None,
                   help="Optional canonical human labels CSV for "
                        "evaluation only.  The autonomous pipeline does "
                        "NOT read this.")
    args = p.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    cfg = ha.HandAssociationConfig()

    # Load inputs.
    tracklets = load_tracklets(args.tracklets)
    chain_mapping = load_chain_mapping(args.chain_mapping)
    accepted = load_accepted_stitches(args.accepted_stitches)
    hand_xy_by_frame = ha._load_hands_by_frame(
        args.hands, cfg.confidence_threshold)

    # Stage 1: build chains and edges.
    tracklet_to_chain, chain_aggregates = build_stage1_chains(
        tracklets, chain_mapping, accepted)
    s1_edges = stage1_edges(accepted, tracklet_to_chain, tracklets,
                            chain_aggregates)
    s1_used = {(e.source, e.target) for e in s1_edges}

    # Stage 2: hand recovery on unmatched boundaries.
    proposals, h_edges = stage2_hand_recovery(
        chain_aggregates, tracklets, hand_xy_by_frame, s1_used, cfg,
        args.fps)

    # Combine edges.
    all_edges = s1_edges + h_edges

    # Validate.
    errors, warnings = validate_graph(all_edges, tracklets,
                                       tracklet_to_chain)
    if errors:
        print("GRAPH VALIDATION ERRORS:")
        for err in errors:
            print("  ", err)
    else:
        print("Graph validation: OK")
    if warnings:
        print(f"Graph validation warnings ({len(warnings)}):")
        for w in warnings[:10]:
            print("  ", w)
        if len(warnings) > 10:
            print(f"  ... and {len(warnings) - 10} more")

    # Coalesce.
    final_mapping = coalesce_chains(tracklet_to_chain, all_edges)

    # Persist outputs.
    final_edges_csv = args.output_dir / "FINAL_accepted_edges.csv"
    final_chain_csv = args.output_dir / "FINAL_chain_mapping.csv"
    proposal_csv = args.output_dir / "hand_recovery_diagnostic.csv"
    summary_json = args.output_dir / "identity_repair_summary.json"

    with final_edges_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["source", "target", "mode", "hand",
                         "source_end_frame", "target_start_frame",
                         "gap_frames", "evidence_tier",
                         "provenance", "source_min_distance_norm",
                         "source_endpoint_norm",
                         "target_min_distance_norm",
                         "target_endpoint_norm"],
            lineterminator="\n",
        )
        w.writeheader()
        for e in all_edges:
            w.writerow({
                "source": e.source, "target": e.target, "mode": e.mode,
                "hand": e.hand,
                "source_end_frame": e.source_end_frame,
                "target_start_frame": e.target_start_frame,
                "gap_frames": e.gap_frames,
                "evidence_tier": e.evidence_tier,
                "provenance": e.provenance,
                "source_min_distance_norm":
                    e.features.get("source_min_distance_norm", ""),
                "source_endpoint_norm":
                    e.features.get("source_endpoint_norm", ""),
                "target_min_distance_norm":
                    e.features.get("target_min_distance_norm", ""),
                "target_endpoint_norm":
                    e.features.get("target_endpoint_norm", ""),
            })
    with final_chain_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["track_id", "chain_id"],
                            lineterminator="\n")
        w.writeheader()
        for tid in sorted(final_mapping.keys()):
            w.writerow({"track_id": tid, "chain_id": final_mapping[tid]})
    with proposal_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["source_chain", "target_chain", "hand",
                         "source_end_frame", "target_start_frame",
                         "gap_frames", "evidence_tier", "decision",
                         "rejection_reason",
                         "source_min_distance_norm",
                         "source_endpoint_norm",
                         "target_min_distance_norm",
                         "target_endpoint_norm"],
            lineterminator="\n",
        )
        w.writeheader()
        for p_ in proposals:
            w.writerow({
                "source_chain": p_.source_chain,
                "target_chain": p_.target_chain,
                "hand": p_.hand,
                "source_end_frame": p_.source_end_frame,
                "target_start_frame": p_.target_start_frame,
                "gap_frames": p_.gap_frames,
                "evidence_tier": p_.evidence_tier,
                "decision": p_.decision,
                "rejection_reason": p_.rejection_reason,
                "source_min_distance_norm": p_.source_min_distance_norm,
                "source_endpoint_norm": p_.source_endpoint_norm,
                "target_min_distance_norm": p_.target_min_distance_norm,
                "target_endpoint_norm": p_.target_endpoint_norm,
            })
    summary = {
        "tracklet_count": len(tracklets),
        "stage1_chains": len(chain_aggregates),
        "stage1_accepted_edges": len(s1_edges),
        "stage2_proposals": len(proposals),
        "stage2_admitted": sum(1 for p_ in proposals if p_.decision == "admitted"),
        "stage2_no_evidence": sum(1 for p_ in proposals if p_.decision == "no_evidence"),
        "stage2_no_match": sum(1 for p_ in proposals if p_.decision == "admitted_no_match"),
        "stage2_side_mismatch": sum(1 for p_ in proposals if p_.decision == "side_mismatch"),
        "hand_edges_added": len(h_edges),
        "hand_edges_left": sum(1 for e in h_edges if e.hand == "left"),
        "hand_edges_right": sum(1 for e in h_edges if e.hand == "right"),
        "hand_edges_ambiguous": sum(1 for e in h_edges if e.hand == "ambiguous"),
        "final_chains": len(set(final_mapping.values())),
        "final_edges": len(all_edges),
        "validation_errors": errors,
        "validation_warnings": warnings,
    }
    with summary_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"tracklets={len(tracklets)} stage1_chains={len(chain_aggregates)} "
          f"stage1_edges={len(s1_edges)} hand_proposals={len(proposals)} "
          f"hand_edges={len(h_edges)} final_chains={len(set(final_mapping.values()))} "
          f"final_edges={len(all_edges)}")
    if errors:
        print("Graph validation FAILED:")
        for err in errors:
            print("  ", err)
    print(f"Outputs in {args.output_dir}")


if __name__ == "__main__":
    main()
