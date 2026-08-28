# Results Log — Hand Occlusion Overnight Lab

This file records the experimental findings produced by the overnight workers.
Each entry should include: hypothesis, dataset/video, smallest reproduction,
quantitative result, visual QA result, verdict, and links to artifacts.

## Conventions

- One H-section per hypothesis. Sub-entries per experiment within a hypothesis.
- Quote counts directly from the CSV outputs; do not pool across videos without
  saying so.
- Tag label-informed experiments explicitly as `LABEL_INFORMED_EXPLORATORY`.
- Always include: video, video frame range, denominator, precision, recall,
  ambiguous-pool count, impossible-state count, predecessor/successor conflict
  count, chain-fragmentation count.

---

## H0 — Bootstrap

- Date: 2026-08-28 03:24 CEST
- Hypothesis: N/A (bootstrap)
- Result: Worktree created, branch `experiments/hand-occlusion-overnight` based
  on `2ddf422`, all lab files committed at `5f69f25`, watchdog and per-model
  reasoning override corrected for direct GMI use, one-shot GMI verification
  `GMI_OK` returned by `MiniMaxAI/MiniMax-M3` via provider `gmi`.
- Verdict: PASS — setup ready, watchdog launching.

---

## H1 — Hand-pool baseline

Status: **v1 COMPLETE & COMMITTED**, v2 in next episode.

### v1 (2026-08-28 ~03:40 CEST)

- Hypothesis: per-hand FIFO token stack + end/start hand-distance slopes
  identifies plausible catch/throw transitions.
- First-stage thresholds from physical geometry (declared in script header,
  NOT tuned to labels).
- Quantitative result:

| Video | ENTRY | EXIT | UNMATCHED_EXIT | AMBIG_POOL_EXIT | UNRESOLVED | n_links |
|---|---|---|---|---|---|---|
| identical_balls_trick_000_018 | 33 | 1 | 2 | 22 | 10 | 23 |
| youtube_juggling_for_data_analysis_eh1I3SlZn48_075_090 | 5 | 5 | 22 | 0 | 0 | 5 |

- Visual QA: 4 events inspected via vision; **all 4 had real failure modes**:
  (a) entry with overly steep slope from a transient tracklet,
  (b) throw driven by hand motion, not ball motion,
  (c) unmatched throw from a mid-air ball passing the hand,
  (d) entry where no ball is actually approaching.
- Negative findings:
  - FIFO alone can pair a current throw with a catch from many seconds ago.
  - Throw criteria is hand-motion dominated; needs wrist-velocity guard.
  - Entry criteria fires on detection dropouts.
  - Pool grows unbounded (depth 7 in identical video); TTL needed.
- H1 recall on full reviewed set is very low (~5%) but the reviewed set
  is an E6c candidate set, mostly mid-air, NOT a hand-test set. Future
  evaluation must use a hand-relevant subset (gap=0, both endpoints in
  hand reach).
- Verdict: **PARTIAL PASS** — baseline works, failure modes well-documented.
  See `h1_hand_pool/reports/h1_v1_report.md`.
- Artifacts:
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_hand_pool.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h1_contact_sheets.py`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/*.csv`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/data/summary.json`
  - `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets/*.png` (21 files)

---
