# Overnight Session State (updated continuously)

LAST_UPDATE: 2026-08-26 07:40 CEST
SESSION_ID: 20260826_061301_ccfd81
RESUME_CMD: cd /home/it-admin/projects/crl-analyzer/data/processed && /home/it-admin/.hermes/hermes-agent/venv/bin/python /home/it-admin/.hermes/hermes-agent/hermes -p juggling-tracker chat --query-file /home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/experiments/overnight/nudge.txt --resume 20260826_061301_ccfd81 --yolo --no-restore-cwd

## Status: E1+E3(+b,c)+E2 COMPLETE -> starting E5 literature sweep, then E4 synthetic occlusion benchmark

## Completed so far
- Setup: PLAN.md queue, watchdog live (tmux ox-keepalive), resume mechanics validated.
- E1 ballistic rescoring: bal8 top1 97.2% H2H 23/24 (baseline 95.8%, 22/24); Kalman no
  better than LS; scoring model NOT the bottleneck. Harness reproduces all 113 shipped
  candidate rows exactly from legacy pre-a77cc5d CSVs (data/legacy_csv/).
- E3 shared-g scoring: NO effect (<1px at these horizons). Negative result.
- E3c gravity-mode timeline: UNSUPERVISED recovery of clip edit structure
  [0-263 normal][263-764 slow 4.13x][764-1079 normal] from per-window y-accel modes.
  Bimodal histogram = physics-only regime segmentation works. Tool for future gating.
- E2 global assignment: Hungarian beats greedy rank-1 (conflicts 1-11 -> 0; precision
  up at matched gates; F1 +0.01-0.03). Adopt global+ballistic when leaving experiment-land.

## Current: E5 arxiv/lit sweep (physics-informed MOT, ball tracking, min-cost-flow,
   PMBM filters, TrackNet). Then:
- E4 synthetic occlusion benchmark on clean tracklets (controlled curves).
- E6 implement best paper idea (likely min-cost-flow stitching w/ appearance-free costs).
- E7 hand-event layer using existing pose CSVs (catch/throw state transitions).
- E8 Norfair motion-model comparison (constant-position vs velocity vs accel) fragmentation.

## Key facts to remember
- Labels: detections/stitch_review_labels.csv (113 rows; 85 identical-balls + 28 youtube).
- Candidate universe gap<=10 caps max achievable correct accepts at ~71.
- Legacy CSVs (pre-a77cc5d semantics incl. Norfair estimates) in experiments/overnight/data/legacy_csv/.
- venv python path: workspace/juggling-yolo/.venv/bin/python; run scripts with cwd=repo root.
- e1_ballistic_rescore.evaluate(rows, models) reusable for any scorer table.
- DO NOT touch anything outside experiments/overnight/.
- Commits so far: b70f4c9 setup, e71f730 E1, eb732cd E3, dad693b E2 (all pushed).

## Next actions
1. E5: batched arxiv searches -> reports/e5_papers_survey.md
2. E4 synthetic occlusion benchmark -> scripts/e4_synthetic_occlusion.py
