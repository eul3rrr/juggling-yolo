# Hand Occlusion Overnight Lab — State

LAST_UPDATE: 2026-08-28 04:25 CEST
STATUS: H1 v2 COMPLETE (5 physics-aware filters, all 3 v1 false-positive failure modes suppressed). v3 in next episode.

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

- **H1 v1** — Hand-pool baseline state machine (committed, `98c0375`).
  Per-tracklet end/start hand-distance features + per-hand FIFO token stack.
  Emits `hand_events.csv`, `hand_inventory.csv`, `hand_links.csv`,
  `tracklet_features.csv`, plus 21 contact sheets for visual QA.
  See `h1_hand_pool/reports/h1_v1_report.md` for full analysis.

- **H1 v2** — Hand-pool with 5 physics-aware filters (committed).
  Adds: token TTL (60f), stale-token rejection (30f), throw leave-window
  (3f), wrist-velocity guard (30 px/frame), catch context (60f).
  Emits same 4 CSVs (extended) + `hand_relevant_eval.json`.
  See `h1_hand_pool/reports/h1_v2_report.md` for full analysis.
  20 v2 contact sheets at `contact_sheets_v2/`.

## Strongest findings so far

- All 3 v1 false-positive failure modes (false catch from transient tracklet,
  false throw driven by hand motion, false catch from tracklet appearing
  near hand without approach) are **correctly suppressed by v2**.
- v2 emits only 3 surviving hand-links on identical, 0 on youtube.
  All 3 surviving links are visually plausible (1 matches a gap=0 reviewed
  "correct" pair, 2 are new plausible catch-throw sequences not surfaced
  by E6c).
- H1 v2 precision is **1.000 across every gap subset** of the reviewed
  labels. No wrong hand-links emitted.
- The `THROW_NO_LEAVE` filter (3-frame leave window) is the dominant
  improvement on the YouTube video: 19 of 25 youtube throws that v1
  classified as throws were reclassified as "ball not actually leaving
  the hand within 3 frames" — they were mid-air balls passing through
  the hand reach envelope.
- The `EXPIRED_HELD` filter bounds the pool: identical's pool depth at
  end of video goes from 11 (v1) to 3 (v2). 26 tokens aged out.

## Important negative findings

- H1 v2 recall is very low (1/8 = 12.5% on gap=0 reviewed) because most
  real catches in the juggled sequences are NOT in the gap=0 candidate
  set; the E6c candidate generator doesn't produce a candidate at the
  same frame as a catch. This is a **gap between E6c's stitching
  representation and H1's hand model** — a candidate pair implies a
  single ballistic edge, not necessarily a hand transition.
- v1 ev0001 (UNMATCHED_EXIT identical f=27) is **fundamentally
  unrecoverable** by any H1-style model: the catch that should have
  preceded this throw was never observed in the input data, and no
  downstream model can recover a "phantom" catch from mid-air.
- The YouTube video emits zero surviving hand-links in v2: every
  catch-like tracklet has no prior hand context (likely detector
  dropouts), and every throw-like tracklet fails the leave-window
  test. This is a genuine negative result for the YouTube video's
  H1 coverage.

## Current best experimental model

H1 v2 is the **current best**. v3 should explore:

1. Soft catch-context: emit a `POTENTIAL_ENTRY` flag instead of hard
   `UNCONTEXTED_ENTRY` filter; let downstream consumers apply confidence.
2. Sensitivity grid for `THROW_LEAVE_WINDOW_FRAMES` ∈ {3, 5, 7} to see
   if the leave-window is too strict.
3. Remove the `WRIST_MOTION_THROW` filter (it fires 0 times in current
   data; no measurable impact).
4. Eventually combine with E6c mid-air edges (master §11) to form
   AIR+HAND chains.

## Next action (v3)

1. Implement H1 v3 with the 3 routes in §10 of `h1_v2_report.md`.
2. Run sensitivity grid on `THROW_LEAVE_WINDOW_FRAMES` and report.
3. If time permits, start H2: combine E6c mid-air edges with H1 v2
   hand-links into a single chain representation (master §11).
   Preserve edge provenance.

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

None. Worktree clean after v2 commit.
