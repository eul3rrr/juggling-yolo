# Overnight Session State (updated continuously)

LAST_UPDATE: 2026-08-26 06:45 CEST
SESSION_ID: 20260826_061301_ccfd81
RESUME_CMD: cd /home/it-admin/projects/crl-analyzer/data/processed && /home/it-admin/.hermes/hermes-agent/venv/bin/python /home/it-admin/.hermes/hermes-agent/hermes -p juggling-tracker chat -q "<nudge>" --resume 20260826_061301_ccfd81 --yolo --no-restore-cwd

## Status: SETUP COMPLETE → starting E1 (ballistic stitcher re-scoring)

## Completed so far
- Loaded skills + all references; full project context recovered.
- Environment verified: venv has ultralytics/norfair/filterpy/lap/torch-cu130; RTX 3060.
- Watchdog deployed (tmux session `ox-keepalive`, script experiments/overnight/watchdog.sh,
  log experiments/overnight/watchdog.log). It resumes this session if the process dies.

## Current experiment: none yet (E1 next)

## Key facts to remember
- Labels: detections/stitch_review_labels.csv — 113 rows, key=(video,source_tracklet,candidate_tracklet), label ∈ correct/wrong.
- Norfair CSVs: detections/*_norfair_dt50_hc5.csv (frame,time_seconds,track_id,confidence,center_x,center_y,observed).
- Stitch candidates: detections/*_norfair_dt50_hc5_stitches.csv (has candidate_rank, prediction_error, end_velocity).
- Videos: identical_balls_trick_000_018.mp4 (1280x720@59.94, 1079f), weave_colored (1920x1080@23.976, 312f), youtube clip (1280x720@59.94, 900f).
- Feature summary: detections/stitch_review_feature_summary.json; enriched: stitch_review_features.csv.
- DO NOT touch anything outside experiments/overnight/. No changes to scripts/, detections/, outputs/.

## Next actions
1. E1: write experiments/overnight/scripts/e1_ballistic_rescore.py
2. Append results to RESULTS_LOG.md; commit+push.
