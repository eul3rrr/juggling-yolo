"""Choose at most N ball identities as disjoint paths through the tracklets."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import networkx as nx

from src.tracking.links import Link, LinkCostConfig, SegmentContext, TrackletInfo

_SCALE = 100  # network simplex needs integer weights


@dataclass(frozen=True)
class Solution:
    paths: tuple[tuple[int, ...], ...]      # track ids in time order, one tuple per ball
    links: tuple[tuple[Link, ...], ...]     # chosen link between consecutive tracklets
    unused: tuple[int, ...]                 # tracklets no identity took
    cost: float


def _edge_cost(frames_from_edge: int, ctx: SegmentContext, in_hand: bool,
               hand_cost: float, base: float, cfg: LinkCostConfig) -> float:
    if frames_from_edge <= cfg.edge_margin_seconds * ctx.fps:
        return 0.0
    return hand_cost if in_hand else base


def solve_paths(infos: Sequence[TrackletInfo], links: Sequence[Link], n_balls: int,
                ctx: SegmentContext, cfg: LinkCostConfig = LinkCostConfig()) -> Solution:
    """Min-cost flow of ``n_balls`` units from segment start to segment end.

    Each tracklet carries at most one unit and pays out a reward for its
    observations. A unit may also skip every tracklet for free, so ``n_balls``
    is a ceiling: an identity is created only when its observations outweigh
    the links, birth and death it needs.
    """
    by_id = {info.tracklet.track_id: info.tracklet for info in infos}
    graph = nx.DiGraph()
    graph.add_node("S", demand=-n_balls)
    graph.add_node("T", demand=n_balls)
    graph.add_edge("S", "T", capacity=n_balls, weight=0)
    for info in infos:
        t = info.tracklet
        reward = cfg.reward_per_second * t.n_observed / ctx.fps
        graph.add_edge(("in", t.track_id), ("out", t.track_id), capacity=1,
                       weight=-round(reward * _SCALE))
        birth = _edge_cost(t.first_frame - ctx.span.start, ctx, info.start.hand_evidence,
                           cfg.birth_from_hand_cost, cfg.birth_cost, cfg)
        death = _edge_cost(ctx.span.end - 1 - t.last_frame, ctx, info.end.hand_evidence,
                           cfg.death_in_hand_cost, cfg.death_cost, cfg)
        graph.add_edge("S", ("in", t.track_id), capacity=1, weight=round(birth * _SCALE))
        graph.add_edge(("out", t.track_id), "T", capacity=1, weight=round(death * _SCALE))
    link_by_pair = {(link.source, link.target): link for link in links}
    for (source, target), link in link_by_pair.items():
        graph.add_edge(("out", source), ("in", target), capacity=1,
                       weight=round(link.cost * _SCALE))
    cost, flow = nx.network_simplex(graph)

    successor = {}
    for (source, target) in link_by_pair:
        if flow[("out", source)].get(("in", target), 0):
            successor[source] = target
    starts = sorted(
        (tid for tid in by_id if flow["S"].get(("in", tid), 0)),
        key=lambda tid: (by_id[tid].first_frame, by_id[tid].points[0][1], tid),
    )
    paths, chosen = [], []
    for tid in starts:
        path, path_links = [tid], []
        while path[-1] in successor:
            nxt = successor[path[-1]]
            path_links.append(link_by_pair[(path[-1], nxt)])
            path.append(nxt)
        paths.append(tuple(path))
        chosen.append(tuple(path_links))
    used = {tid for path in paths for tid in path}
    unused = tuple(sorted(tid for tid in by_id if tid not in used))
    return Solution(tuple(paths), tuple(chosen), unused, cost / _SCALE)
