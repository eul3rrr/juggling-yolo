# Hand Occlusion Overnight Lab — State

LAST_UPDATE: 2026-08-28 02:55 CEST
STATUS: BOOTSTRAPPED. No hand experiments completed yet. Worker is launching.

## Isolation

- Branch: `experiments/hand-occlusion-overnight`
- Worktree: `/home/it-admin/projects/juggling-yolo-hand-occlusion-night`
- Base commit: `2ddf422` (main @ "experiment: E15 detector headroom — dropouts are threshold+association, not blindness")
- Upstream: pushed to `origin/experiments/hand-occlusion-overnight`
- Existing research recognized: E1, E2, E3, E3c, E4, E5, E6, E6c, E6d, E6e, E7, E8, E9, E10, E11, E15 — all on `main` and accessible read-only.
- Existing `experiments/overnight/` directory preserved untouched for reference.

## Hardware safety

- Physical RAM: ~14 GiB total.
- Pre-launch available: ~6.3 GiB MemAvailable, 1.8 GiB SwapFree.
- Watchdog preflight: require MemAvailable >= 3 GiB AND SwapFree >= 768 MiB before launching a worker.
- While worker runs: poll /proc/meminfo every 30s; if MemAvailable < 1.5 GiB or SwapFree < 256 MiB, terminate the worker gracefully and wait for recovery.
- Per-worker transient memory scope: MemoryHigh=4G MemoryMax=6G MemorySwapMax=2G (if available).

## Reasoning configuration

- Worker model: `minimax/minimax-m3:free`
- Reasoning requested: `ultra`
- Per-model override: `agent.reasoning_overrides["minimax/minimax-m3:free"] = "ultra"` set in `/home/it-admin/.hermes/profiles/juggling-tracker/config.yaml`.
- Watchdog also passes `--reasoning ultra` explicitly on the `hermes chat` invocation as belt-and-braces.

## Watchdog status

- Lock file: `experiments/hand_occlusion_overnight/watchdog.lock`
- PID file: `experiments/hand_occlusion_overnight/watchdog.pid`
- Log file: `experiments/hand_occlusion_overnight/watchdog.log`
- Stop sentinel: `experiments/hand_occlusion_overnight/STOP` (NOT yet created).

## Completed experiments

None yet.

## Strongest findings so far

None yet.

## Important negative findings

None yet.

## Current best experimental model

Not yet determined.

## Unresolved problems

- H1 hand-pool baseline not implemented.
- No hand-event CSV, no hand inventory CSV, no hand links CSV.

## Next action

1. Read the existing overnight scripts and reports to understand E6/E6c/E7/E9/E10/E11/E15 artifacts and the production tracklet format.
2. Inspect available pose/wrist extraction (the YOLO pose model is already vendored at the worktree root).
3. Implement H1 hand-pool state machine on one video:
   - emit `hand_events.csv`, `hand_inventory.csv`, `hand_links.csv`;
   - declare first-stage thresholds from physical geometry, NOT from manual labels;
   - evaluate against the existing reviewed contact cases.
4. Visual QA on selected contact transitions via compact contact sheets.
5. Compare with E6c and the E11 regime-split approach quantitatively.
6. Document everything in `RESULTS_LOG.md` and `RESEARCH_NOTES.md`, commit, push.

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

None. The worktree was just created from a clean committed base; no uncommitted experimental changes exist.
