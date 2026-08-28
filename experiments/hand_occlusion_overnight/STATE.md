# Hand Occlusion Overnight Lab — State

LAST_UPDATE: 2026-08-28 03:24 CEST
STATUS: BOOTSTRAPPED (v2 — direct GMI verified). Watchdog launching.

## Isolation

- Branch: `experiments/hand-occlusion-overnight`
- Worktree: `/home/it-admin/projects/juggling-yolo-hand-occlusion-night`
- Base commit: `2ddf422` (main @ "experiment: E15 detector headroom — dropouts are threshold+association, not blindness")
- Upstream: pushed to `origin/experiments/hand-occlusion-overnight`
- Existing research recognized: E1, E2, E3, E3c, E4, E5, E6, E6c, E6d, E6e, E7, E8, E9, E10, E11, E15 — all on `main` and accessible read-only.
- Existing `experiments/overnight/` directory preserved untouched for reference. (A legacy `STOP` file exists there from the previous run; it is NOT the lab stop sentinel and the watchdog does not read it.)

## Hardware safety

- Physical RAM: ~14 GiB total.
- Pre-launch available: ~5.9 GiB MemAvailable, ~2.2 GiB SwapFree at bootstrap.
- Watchdog preflight: require `MemAvailable >= 3 GiB` AND `SwapFree >= 768 MiB` before launching a worker.
- While worker runs: poll /proc/meminfo every 30s; if `MemAvailable < 1.5 GiB` or `SwapFree < 256 MiB`, terminate the worker gracefully and wait for recovery.
- Per-worker transient memory scope: `MemoryHigh=4G MemoryMax=6G MemorySwapMax=2G` (when systemd-run --user --scope is usable).

## Reasoning / model configuration

- Worker provider: `gmi` (explicit, never auto; never OpenRouter)
- Worker model: `MiniMaxAI/MiniMax-M3` (exact GMI model ID; verified by one-shot)
- Reasoning requested: `ultra`
- Per-model override in `/home/it-admin/.hermes/profiles/juggling-tracker/config.yaml`:
  `agent.reasoning_overrides["MiniMaxAI/MiniMax-M3"] = "ultra"`
- Watchdog also passes `--reasoning ultra` on every `hermes chat` invocation as belt-and-braces.
- One-shot verification reply: `GMI_OK`.

## Watchdog status

- Lock dir: `experiments/hand_occlusion_overnight/watchdog.lock`
- PID file: `experiments/hand_occlusion_overnight/watchdog.pid`
- Log file: `experiments/hand_occlusion_overnight/watchdog.log`
- Stop sentinel: `experiments/hand_occlusion_overnight/STOP` (NOT yet created).

## Completed experiments

- **H1 v1** — Hand-pool baseline state machine (committed).
  Per-tracklet end/start hand-distance features + per-hand FIFO token stack.
  Emits `hand_events.csv`, `hand_inventory.csv`, `hand_links.csv`,
  `tracklet_features.csv`, plus 21 contact sheets for visual QA.
  See `h1_hand_pool/reports/h1_v1_report.md` for full analysis.

## Strongest findings so far

- The H1 baseline **runs** and produces structured artifacts; visual QA
  reveals 4 distinct failure modes that the master instruction explicitly
  asks us to record (see `h1_v1_report.md` §5-6).
- **FIFO bookkeeping alone is insufficient**: when the pool depth exceeds 1,
  oldest-token consumption can pair a current throw with a catch from many
  seconds ago, producing implausible "links" that pass local evidence at
  each endpoint.
- The throw criteria is **dominated by hand motion, not ball motion**;
  a tracklet whose center moves away from the wrist because the **hand**
  is moving will fire a false-positive throw.
- The entry criteria can fire on **detection dropouts** as well as real
  catches — a ball disappearing near a hand is not evidence of a catch by
  itself.

## Important negative findings

- H1's recall against the full reviewed-label set is very low (<10%) but
  this is a **category error**: the reviewed labels are an E6c candidate
  set, mostly mid-air, NOT a hand-test set. H1 is intentionally a hand-only
  extractor and should be evaluated on a hand-relevant subset (e.g. gap=0
  pairs only).
- The pool grows without bound (depth 7 in identical video) for v1 because
  entries fire faster than exits.

## Current best experimental model

H1 v1 is the **baseline**; a v2 with TTL, stale-token rejection, throw
strictness, wrist-velocity guard, and catch-context check is the next step.

## Unresolved problems

- v1 visual QA showed false-positive throws driven by hand motion. A
  wrist-velocity check is needed to suppress these.
- v1 FIFO can pair very old catches with current throws. A TTL is needed
  to bound the pool.
- The youtube video's UNMATCHED_EXIT count (22) is suspiciously high and
  likely dominated by mid-air balls crossing the reach radius; the
  throw-strictness filter must require a fast initial divergence.

## Next action

1. Implement H1 v2 with the 5 filters listed in `h1_v1_report.md` §8.
2. Re-run on both videos; compare counter distributions before/after.
3. Re-render contact sheets for the SAME events (e.g. ev0002, ev0006,
   ev0001) and visually verify the failure modes are suppressed.
4. Re-evaluate against the gap=0 correct labels (the only hand-relevant
   subset of the reviewed set).
5. Document v2 in `h1_v1_report.md` continuation or new file.

## Important artifact paths

- `experiments/hand_occlusion_overnight/MASTER_INSTRUCTIONS.md`
- `experiments/hand_occlusion_overnight/STATE.md` (this file)
- `experiments/hand_occlusion_overnight/PLAN.md`
- `experiments/hand_occlusion_overnight/RESULTS_LOG.md`
- `experiments/hand_occlusion_overnight/RESEARCH_NOTES.md`
- `experiments/hand_occlusion_overnight/SETUP_NOTES.md`
- `experiments/hand_occlusion_overnight/watchdog.sh`
- `experiments/hand_occlusion_overnight/watchdog.log`
- `experiments/hand_occlusion_overnight/worker_prompt.txt`
- `experiments/hand_occlusion_overnight/h1_hand_pool/` (target for H1 artifacts)

Reference inputs (read-only):
- `experiments/overnight/scripts/`
- `experiments/overnight/reports/`
- `experiments/overnight/data/`
- `scripts/` (project root — production tracking)
- `videos/` (project root)

## Interrupted / dirty work

None. Worktree is clean except for the staged-but-not-yet-committed bootstrap fixup (corrected `watchdog.sh`, refreshed `SETUP_NOTES.md`, `STATE.md`, and `RESULTS_LOG.md`).
