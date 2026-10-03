# Overnight Research Plan — Multi-Object Tracking of Juggling Balls

Session: 20260826_061301_ccfd81 · Started: 2026-08-26 ~06:40 CEST
Rule: EXPERIMENTS ONLY. Nothing outside `experiments/overnight/` in the juggling-yolo
repo may change. Existing scripts/CSVs/videos are read-only inputs. Commit+push only
new experiment code/results under experiments/overnight/.

## Problem inventory (from project history)

P1. Tracklet fragmentation: Norfair local tracklets break at every occlusion/hand pass.
    Current stitcher = constant-velocity extrapolation from last 2 points only.
P2. Identity ambiguity near hands/crossings: rank-1 candidate often wrong with tiny margin.
P3. No physics model: gravity is known and shared by ALL balls but unused.
P4. Greedy per-source ranking: no global 1-to-1 consistency (two sources can claim one candidate).
P5. No hand/event model: catches/throws are where identities legitimately permute.
P6. Detector gaps during overlap: no appearance/shape evidence beyond center points.
P7. Offline information unused: future frames could disambiguate past associations (viterbi-style).

## Prior evidence

- 113 labeled stitch candidates (71 correct / 42 wrong) on 2 clips.
- trajectory_fit_error (quadratic fit over 10+10 pts): correct median ~11px, wrong median ~47px — informative but overlapping (correct max 65, wrong min 12.6).
- Wrong rows have near-zero trajectory_fit_margin vs alternatives (median ratio 0.95).
- nearest_hand_distance is NOT discriminative by itself.
- prediction_margin/ratio (vs best alternative) are decent signals.

## Experiment queue (work top-down; log EVERYTHING in RESULTS_LOG.md; update STATE.md)

E1. Ballistic stitcher: replace last-2-point velocity with robust quadratic fit per axis
    (x linear, y quadratic) on last N points, predict at candidate_start. Re-score the SAME
    113 labeled pairs offline (no re-running review): compare ranking metrics (rank-of-true,
    correct@1, error separation) CV-vs-ballistic. Mathematically grounded, zero risk.

E2. Global assignment: Hungarian/lap on the full cost matrix (all source×candidate pairs)
    with ballistic costs + gate. Compare greedy-rank1 vs global 1-to-1 on labeled data.

E3. Physics-consistent gap interpolation: fit shared image-space gravity g from clean
    flights across each video; constrain y-quadratic acceleration == g for all stitches;
    measure whether the shared-g constraint improves discrimination on the 113 labels.

E4. Synthetic occlusion benchmark: take confident long tracks, artificially delete k-frame
    windows, measure stitch recovery rate for CV vs ballistic vs ballistic+global vs
    Kalman variants. Gives controlled curves without needing new labels.

E5. Literature sweep (arxiv skill): MOT with physics priors; ball trajectory tracking;
    sports ball tracking (TrackNet etc.); multi-target tracking global optimization
    (min-cost-flow, graph cuts); PMBM/GGIW filters; occlusion-aware MOT. Collect a
    curated annotated list w/ applicability verdicts. Write papers_survey.md.

E6. Reproduce/adapt the most promising small idea from E5 (candidates: min-cost-flow
    stitcher; TrackNet-style detector for occlusion recovery if GPU allows; constant-accel
    Kalman with learned-ish gating).

E7. Hand-event layer prototype: use existing pose CSV wrists; detect catch/throw moments
    on labeled stitches; test "identity resets at hands" hypothesis quantitatively.

E8. If time: Norfair Kalman motion-model comparison (constant-position/velocity/
    acceleration) on raw detections — measures fragmentation source difference.

## Rules

- Use venv python: /home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/.venv/bin/python
- All outputs → experiments/overnight/{data,reports}/ ; videos only if needed for judgment.
- Vision checks allowed on generated frames (vision_analyze).
- After EACH experiment: append RESULTS_LOG.md, update STATE.md, commit+push.
- If stuck/no strong candidate: go back to data (CSV forensics) or literature (arxiv),
  find next problem, add to queue.
