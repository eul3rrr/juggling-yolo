# Overnight Session State (updated continuously)

LAST_UPDATE: 2026-08-26 08:07 CEST
SESSION_ID: 20260826_061301_ccfd81

## Status: E1-E11 + E8 family COMPLETE -> E15 detector headroom probe, then
## E12 integration run + E13 siteswap validation, then final REPORT.md

## Key results so far (details in RESULTS_LOG.md)
- E1: ballistic scoring bal8 small real gain (top1 95.8->97.2%); Kalman filter no better.
- E2: global assignment kills greedy conflicts (1-11 -> 0), precision up.
- E3: shared-g scoring no effect; E3c: UNSUPERVISED playback-regime timeline from
  gravity modes (bimodal histogram; slow-mo segment [263,764] factor 4.13x).
- E4: KEY - synthetic occlusion benchmark (4180 cuts): bal8 keeps 85%+ top1 to gap 20
  (cv2 collapses to 53%); calibrated sigma(gap) curves extracted.
- E5: lit survey (reports/e5_papers_survey.md): TrackNet V4/V5 for detector upgrade;
  min-cost-flow chaining; microscopy intermittent-particles analogy.
- E6/E6b/E6c: chain-level global stitching; phantom-tracklet discovery (legacy CSVs
  contain Norfair estimates); observed-only join + per-video calibration + normalized
  costs => 31 links, 0 conflicts, 0 labeled-fp (ident-balls).
- E6d/E6e: visual QA (vision) found FP tracklets + detector dropouts (obs=0 frames);
  physical consistency check: 0 same-frame violations (structural guarantee).
- E7: wrong stitches concentrate at catches (slope -4.9 vs -0.2); naive hand-rescue
  HURTS (one catch matches many throws); needs hand inventories (future).
- E9: hand-aware tracklet states AIRBORNE/HELD/BACKGROUND/SWEEP; demote only
  BACKGROUND+SWEEP; metrics unchanged, interpretability up.
- E10: hand mutual exclusion with time-overlap-only dropping: removes 1 wrong, 0 correct.
- E11: regime-split acceptance MIXED (38 accepts 18 correct 1 wrong vs gate-only
  29/19/0) - keep gate-only primary; contact path needs full state machine.
- E8: constacc association cuts fragmentation 77->55 tracklets; RAW centers beat
  Kalman estimates as exported observations (+4-8pts recovery). ADOPT BOTH.

## Config to adopt (experiment-land consensus)
observed-only points + bal8 scoring + per-video q90(gap) calibration +
gap-normalized costs + successor assignment + CA Norfair motion model +
raw-center export. Precision-first: 0 wrong accepts on labeled videos.

## Remaining queue
- E15: detector headroom (low-conf/high-imgsz rerun on dropout frames).
- E12: integration run (full recommended config end-to-end, render chains).
- E13: siteswap validation (flight-time histogram should show period-3 cascade).
- REPORT.md: consolidated what-worked/what-didnt for the user.
