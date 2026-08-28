# Hand Occlusion Overnight Lab — State

LAST_UPDATE: 2026-08-28 05:35 CEST
STATUS: H1 v4 + H2 + v5 sens grid + H3 COMPLETE. v4d is the recommended hand-link extractor (10 identical + 1 youtube, ~1.000 visual precision). v5 sens grid confirms v4d's MIN_FROM_SLOPE=2.5 is in a flat region of the precision/recall curve. H2 combines v4d hand-links with E6c mid-air edges into 40 chains (identical) + 13 chains (youtube), with 1 conflict (tracklet 3) recorded for review. H3 stationary-cluster criterion correctly confirms 6/6 identical-video v4d hand-links as real held balls, with 1 false positive on the youtube video (stuck on face).

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
  See `h1_hand_pool/reports/h1_v1_report.md` for full analysis.

- **H1 v2** — Hand-pool with 5 physics-aware filters (committed, `a9a5464`).
  Adds: token TTL (60f), stale-token rejection (30f), throw leave-window
  (3f), wrist-velocity guard (30 px/frame), catch context (60f).
  See `h1_hand_pool/reports/h1_v2_report.md` for full analysis.
  20 v2 contact sheets at `contact_sheets_v2/`.

- **H1 v3** — Soft catch-context + sensitivity grid (committed, `0fd4bb0`).
  Replaces hard `UNCONTEXTED_ENTRY` with softer `POTENTIAL_ENTRY` flag.
  Sweeps `THROW_LEAVE_WINDOW_FRAMES` ∈ {3, 5, 7}.
  See `h1_hand_pool/reports/h1_v3_report.md` for full analysis.
  16 v3 contact sheets at `contact_sheets_v3/`.

- **H1 v4** — Multi-feature filter on v3c (committed, `05deab2`).
  Adds `MIN_FROM_SLOPE = 2.5` to v3c. Rejects 2 false positives
  (15→25, 35→40) and keeps all 8 other v3 links + 2 more from v2.
  See `h1_hand_pool/reports/h1_v4_report.md` for full analysis.
  11 v4 contact sheets at `contact_sheets_v4/`.

- **H2** — Combined AIR + HAND chain representation (committed).
  Union-finds v4d hand-links with E6c mid-air edges. Records
  conflicts (where hand and air logic disagree) rather than
  silently resolving. Identical: 76 tracklets → 40 chains
  (13 multi-tracklet, longest 8 tracklets). 1 conflict
  (tracklet 3 → {hand=9, air=8}). YouTube: 40 tracklets →
  13 chains. 0 conflicts.
  See `h1_hand_pool/reports/h2_report.md` for full analysis.

- **H1 v5** — Sensitivity grid on `MIN_FROM_SLOPE` ∈
  {1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0} (committed). Confirms
  v4d's `MIN_FROM_SLOPE = 2.5` is in a flat region
  (2.5-3.5 all give identical results). Threshold is
  well-justified and robust to small perturbations.
  See `h1_hand_pool/reports/h1_v5_sens_report.md`.

- **H3** — Low-confidence hand-region evidence (master §14).
  Three iterated designs (v1, v2, v3). The recommended v3
  "stationary cluster" criterion (≥3 low-conf dets in
  30px radius over ≥5 frames) correctly identifies
  6/6 identical-video v4d hand-link held phases as real
  held balls, with 1 false positive on the YouTube video
  (stuck on face). H3 is useful as a *downstream confidence
  signal* on v4d links, not as a general held-ball detector.
  See `h1_hand_pool/reports/h3_report.md`.

## Strongest findings so far

- v2 precision is **1.000 across every gap subset** of the reviewed
  labels. No wrong hand-links emitted.
- v3c (throw=7) emits 11 links on identical and 2 on youtube with
  precision 1.000 in CSV terms. Visual QA: 7/8 (87.5%) of inspected
  new v3 links are real catch-throws; the only false positive
  (15→25 youtube) is a mid-air pass-through admitted by the looser
  `THROW_LEAVE_WINDOW_FRAMES=7` test. v3 visual precision ≈ 0.875.
- **v4d is the new operating point**: 10 identical + 1 youtube
  links with visual precision ~1.000 (11/11 inspected confirmed
  real). 4x recall gain on identical vs v2.
- The `THROW_LEAVE_WINDOW_FRAMES=7` (v3c) combined with
  `MIN_FROM_SLOPE=2.5` (v4) is the right operating point: looser
  throw window admits more candidates, the slope filter rejects
  the pass-through false positives.
- v3a soft catch-context is a **safe no-op** for link counts; v2
  already created tokens on `UNCONTEXTED_ENTRY` and the
  `POTENTIAL_ENTRY` rename is purely a downstream-consumable
  signal.
- H3 stationary-cluster correctly identifies 6/6 identical-video
  v4d hand-link held phases as real held balls (visual
  precision 1.000 on identical). The 1 YouTube false positive
  is a detector limitation: YOLO confuses face/head features
  with sports balls when the hand is near the face. H3 does
  not recover any v4d-missed links — it is a *corroborating
  signal*, not a recovery mechanism.
- H3's baseline FPR (50-60% of random hand-region searches
  produce a stationary cluster) is HIGHER than its v4d-link
  rate (~11%). The "stationary cluster of low-conf dets"
  pattern is not specific to hand-events; it appears
  throughout the video. v3 is useful only because it's
  *restricted* to v4d-link time windows.
- The `THROW_NO_LEAVE` filter (3-frame leave window) is the dominant
  improvement on the YouTube video: 19 of 25 youtube throws that v1
  classified as throws were reclassified as "ball not actually leaving
  the hand within 3 frames" — they were mid-air balls passing through
  the hand reach envelope.
- The `EXPIRED_HELD` filter bounds the pool: identical's pool depth at
  end of video goes from 11 (v1) to 3 (v2). 26 tokens aged out.

## Important negative findings

- v1 ev0001 (UNMATCHED_EXIT identical f=27) is **fundamentally
  unrecoverable** by any H1-style model: the catch that should have
  preceded this throw was never observed in the input data, and no
  downstream model can recover a "phantom" catch from mid-air.
- Soft catch-context (v3a) is a no-op for link counts because v2
  already created tokens on `UNCONTEXTED_ENTRY`. A v5 that wants
  to *not* create tokens on uncontexted entries would need a
  separate hard/soft flag in the state machine, not just a
  rename.
- The "3→9 left/right swap" was a vision-analyze
  misinterpretation; the actual link is a real catch-throw on
  the image-left hand. v3's `AMBIGUOUS_POOL_EXIT` label
  correctly reflects identity ambiguity, not handedness.
- The vision verifier repeatedly confuses the contact sheet
  color mapping (ORANGE=LEFT, BLUE=RIGHT in image coordinates)
  with the juggler's left/right (which is mirrored in the
  camera image). v4 inherits the v2 model's consistent
  image-perspective hand attribution; the visual QA reports
  on the *image*-perspective hand.
- v4d's "handedness consistency" filter (reach check) is a
  no-op; v2's catch/throw classification already enforces that
  both endpoints are within the 108 px reach radius.

## Current best experimental model

H1 v4d is the **new recommended operating point** for hand-link
extraction: 10 identical + 1 youtube links with visual precision
~1.000. v2 remains valid as a strict-precision baseline.

| Setting | identical n_links | youtube n_links | Visual precision |
|---|---|---|---|
| v2 (throw=3)        |  3 | 0 | 1.000 (3/3 inspected) |
| v3c (throw=7)       | 11 | 2 | ~0.875 (7/8 inspected) |
| **v4d (throw=7+slope)** | **10** | **1** | **~1.000 (11/11 inspected)** |

## Next action

1. **Apply H3 as a downstream confidence signal on v4d
   links.** Add a `h3_confirmed: bool` field to v4d link
   records when a v3 stationary cluster is found in the
   held phase. This gives consumers a per-link
   corroboration flag.
2. **Test face-masked H3** to see if a face detector
   can mask out the YouTube false positive. The hypothesis
   is that the false positive is a face feature; masking
   face-region low-conf detections before clustering
   should eliminate it.
3. **H4: Literature-derived experiment.** Try a min-cost
   flow formulation of the AIR+HAND graph as an alternative
   to H2's union-find. Master §17 lists min-cost flow as
   a candidate approach; H2 is a simpler union-find that
   records conflicts; a min-cost flow could resolve the
   1 conflict optimally.
4. **H5: Object permanence explicit.** v4d is implicitly
   object-permanent (tokens persist 60 frames), but a v6
   could model this explicitly and use it to bridge
   detector dropouts in the H2 chains.

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
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h1_v3_report.md`
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h1_v4_report.md`

Reference inputs (read-only):
- `experiments/overnight/scripts/`
- `experiments/overnight/reports/`
- `experiments/overnight/data/`
- `scripts/` (project root — production tracking)
- `videos/` (project root)

## Interrupted / dirty work

None. v3 and v4 work committed in this episode.
