#!/usr/bin/env python3
"""H125 v1 — K-best successor analysis on the E6c candidate set.

Hypothesis: the 20 NOT_IN_CHAIN + correct review pairs are real catches
the H7 chain missed due to its one-successor-per-source capacity constraint.
For each source, list all candidate successors (not just the in-chain one)
and check: are the missing-correct edges systematically the 2nd-best
(closest trajectory_fit_error to the picked one)?

If true, a k-best successor augmentation is meaningful.
If not, the missing edges are not the "next-best alternative" — they're
geometrically distinguishable from the in-chain picks in a way that
suggests they're not really capacity-conflicts.

Method:
1. Load E6c accepted_stitches (113 review pairs for both videos)
2. Load h7v3plus3 admitted_edges (the chain picks)
3. For each source, list all successor candidates sorted by trajectory_fit_error
4. For each NOT_IN_CHAIN + correct edge, find its rank among the source's successors
5. Compute aggregate statistics: how often is rank=1 (best), rank=2, etc.?
6. Compare with the in-chain picks: what rank are the in-chain successors?
"""

from __future__ import annotations
import csv
import json
from collections import defaultdict
from pathlib import Path

WORKTREE = Path("/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
H1_DATA = WORKTREE / "experiments" / "hand_occlusion_overnight" / "h1_hand_pool" / "data"
DETECTIONS = WORKTREE / "detections"

VIDEO_STEMS = {
    "identical_balls_trick_000_018",
    "youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090",
}


def load_review_pairs():
    """Load the 113 review pairs from H59 per-pair eval."""
    path = H1_DATA / "h59_per_pair_eval.csv"
    with open(path) as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_e6c_candidates(stem):
    """Load all E6c candidate edges (accepted and rejected) for a video."""
    path = DETECTIONS / f"{stem}_norfair_dt50_hc5_accepted_stitches.csv"
    with open(path) as f:
        reader = csv.DictReader(f)
        return list(reader)


def load_in_chain_picks(stem):
    """Load h7v3plus3 admitted edges for a video."""
    path = H1_DATA / f"h7v3plus3_admitted_edges_{stem}.csv"
    with open(path) as f:
        reader = csv.DictReader(f)
        return {f'{r["from_tid"]}->{r["to_tid"]}': r for r in reader}


def main():
    # Load all review pairs and group by stem
    review_pairs = load_review_pairs()
    by_stem = defaultdict(list)
    for r in review_pairs:
        by_stem[r['stem']].append(r)

    summary = {
        "n_review_pairs": len(review_pairs),
        "stems": {},
    }

    # For each video, build source -> list of (target, err, accepted) sorted by err
    for stem, pairs in by_stem.items():
        e6c = load_e6c_candidates(stem)
        in_chain = load_in_chain_picks(stem)

        # Source -> sorted list of (target, err, accepted, in_chain_pick, label)
        src_succ = defaultdict(list)
        for r in e6c:
            src = int(r['source_tracklet'])
            tgt = int(r['candidate_tracklet'])
            err = float(r['trajectory_fit_error'])
            key = f"{src}->{tgt}"
            in_chain_pick = key in in_chain
            # Find review label
            rp = [p for p in pairs if int(p['source']) == src and int(p['candidate']) == tgt]
            label = rp[0]['label'] if rp else "NOT_IN_REVIEW"
            in_chain_review = rp[0]['in_h7v3plus3'] == 'True' if rp else None
            src_succ[src].append({
                'src': src, 'tgt': tgt, 'err': err,
                'e6c_accepted': r['accepted'] == '1',
                'in_chain_pick': in_chain_pick,
                'review_label': label,
                'in_chain_review': in_chain_review,
            })

        # Sort by err
        for src in src_succ:
            src_succ[src].sort(key=lambda x: x['err'])

        # Compute rank analysis
        # For each NOT_IN_CHAIN + correct edge, what is its rank among the source's successors?
        # For each IN_CHAIN + correct edge, what is its rank?
        nic_correct_ranks = []
        ic_correct_ranks = []
        nic_wrong_ranks = []
        ic_wrong_ranks = []
        for src, succs in src_succ.items():
            for rank, s in enumerate(succs, 1):
                if s['review_label'] == 'correct' and not s['in_chain_review']:
                    nic_correct_ranks.append({
                        'src': src, 'tgt': s['tgt'], 'rank': rank,
                        'err': s['err'], 'n_succ': len(succs),
                        'top1_err': succs[0]['err'],
                        'delta_to_top1': s['err'] - succs[0]['err'],
                    })
                elif s['review_label'] == 'correct' and s['in_chain_review']:
                    ic_correct_ranks.append({
                        'src': src, 'tgt': s['tgt'], 'rank': rank,
                        'err': s['err'], 'n_succ': len(succs),
                    })
                elif s['review_label'] == 'wrong' and not s['in_chain_review']:
                    nic_wrong_ranks.append({
                        'src': src, 'tgt': s['tgt'], 'rank': rank,
                        'err': s['err'], 'n_succ': len(succs),
                    })
                elif s['review_label'] == 'wrong' and s['in_chain_review']:
                    ic_wrong_ranks.append({
                        'src': src, 'tgt': s['tgt'], 'rank': rank,
                        'err': s['err'], 'n_succ': len(succs),
                    })

        # Aggregate stats
        stem_summary = {
            "n_sources": len(src_succ),
            "n_review_pairs": len(pairs),
            "rank_dist_nic_correct": dict(zip(*[
                ['1', '2', '3+'],
                [sum(1 for r in nic_correct_ranks if r['rank'] == 1),
                 sum(1 for r in nic_correct_ranks if r['rank'] == 2),
                 sum(1 for r in nic_correct_ranks if r['rank'] >= 3)]
            ])),
            "rank_dist_ic_correct": dict(zip(*[
                ['1', '2', '3+'],
                [sum(1 for r in ic_correct_ranks if r['rank'] == 1),
                 sum(1 for r in ic_correct_ranks if r['rank'] == 2),
                 sum(1 for r in ic_correct_ranks if r['rank'] >= 3)]
            ])),
            "n_nic_correct": len(nic_correct_ranks),
            "n_ic_correct": len(ic_correct_ranks),
            "n_nic_wrong": len(nic_wrong_ranks),
            "n_ic_wrong": len(ic_wrong_ranks),
        }

        # Delta to top1: how far are missing-correct edges from the source's best?
        if nic_correct_ranks:
            deltas = [r['delta_to_top1'] for r in nic_correct_ranks]
            stem_summary['delta_to_top1_stats'] = {
                'mean': sum(deltas) / len(deltas),
                'min': min(deltas),
                'max': max(deltas),
                'median': sorted(deltas)[len(deltas) // 2],
            }

        # Top-1 wrong rate
        top1_wrong = [r for sucs in src_succ.values() for r in sucs[:1] if r['review_label'] == 'wrong']
        top1_correct = [r for sucs in src_succ.values() for r in sucs[:1] if r['review_label'] == 'correct']
        top1_unreviewed = [r for sucs in src_succ.values() for r in sucs[:1] if r['review_label'] == 'NOT_IN_REVIEW']
        stem_summary['top1_review_label'] = {
            'wrong': len(top1_wrong),
            'correct': len(top1_correct),
            'unreviewed': len(top1_unreviewed),
        }

        summary['stems'][stem] = {
            'summary': stem_summary,
            'nic_correct': nic_correct_ranks,
            'ic_correct': ic_correct_ranks,
        }

    # Write outputs
    out_dir = H1_DATA

    # Per-edge CSV: detailed analysis
    with open(out_dir / 'h125_v1_kbest_per_edge.csv', 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            'stem', 'src', 'tgt', 'err', 'rank', 'n_succ',
            'top1_err', 'delta_to_top1', 'review_label',
            'in_chain_review', 'is_nic_correct', 'is_ic_correct'
        ])
        for stem, sd in summary['stems'].items():
            # Reconstruct: iterate all sources
            e6c = load_e6c_candidates(stem)
            pairs = by_stem[stem]
            src_succ = defaultdict(list)
            for r in e6c:
                src = int(r['source_tracklet'])
                tgt = int(r['candidate_tracklet'])
                err = float(r['trajectory_fit_error'])
                key = f"{src}->{tgt}"
                rp = [p for p in pairs if int(p['source']) == src and int(p['candidate']) == tgt]
                label = rp[0]['label'] if rp else "NOT_IN_REVIEW"
                in_chain_review = rp[0]['in_h7v3plus3'] == 'True' if rp else None
                src_succ[src].append({
                    'src': src, 'tgt': tgt, 'err': err,
                    'e6c_accepted': r['accepted'] == '1',
                    'review_label': label,
                    'in_chain_review': in_chain_review,
                })
            for src in src_succ:
                succs = sorted(src_succ[src], key=lambda x: x['err'])
                top1 = succs[0]['err'] if succs else 0
                for rank, s in enumerate(succs, 1):
                    is_nic = s['review_label'] == 'correct' and not s['in_chain_review']
                    is_ic = s['review_label'] == 'correct' and s['in_chain_review']
                    writer.writerow([
                        stem, s['src'], s['tgt'], f"{s['err']:.3f}", rank, len(succs),
                        f"{top1:.3f}", f"{s['err'] - top1:.3f}", s['review_label'],
                        s['in_chain_review'] or '', is_nic, is_ic
                    ])

    # Summary JSON
    out_summary = {
        'n_review_pairs': summary['n_review_pairs'],
        'stems': {stem: sd['summary'] for stem, sd in summary['stems'].items()},
    }
    with open(out_dir / 'h125_v1_summary.json', 'w') as f:
        json.dump(out_summary, f, indent=2)

    print('=== H125 v1 K-best successor analysis ===')
    print(f'Total review pairs: {summary["n_review_pairs"]}')
    print()
    for stem, sd in summary['stems'].items():
        s = sd['summary']
        print(f'--- {stem[:30]}... ---')
        print(f'  n_sources: {s["n_sources"]}, n_review_pairs: {s["n_review_pairs"]}')
        print(f'  NOT_IN_CHAIN + correct: {s["n_nic_correct"]}')
        print(f'    rank distribution: {s["rank_dist_nic_correct"]}')
        if 'delta_to_top1_stats' in s:
            d = s['delta_to_top1_stats']
            print(f'    delta_to_top1: mean={d["mean"]:.2f} min={d["min"]:.2f} max={d["max"]:.2f} median={d["median"]:.2f}')
        print(f'  IN_CHAIN + correct: {s["n_ic_correct"]}')
        print(f'    rank distribution: {s["rank_dist_ic_correct"]}')
        print(f'  Top-1 review label: {s["top1_review_label"]}')
        print(f'  NOT_IN_CHAIN + wrong: {s["n_nic_wrong"]}')
        print()


if __name__ == '__main__':
    main()
