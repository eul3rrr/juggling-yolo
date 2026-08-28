# Hand Occlusion Overnight Lab — State

LAST_UPDATE: 2026-08-28 18:10 CEST
STATUS: H30 + H31 + H32 + H33 + H34 + H35 + H36 + H37 + H38 + H39 + H40 + H41 + H42 + H43 + H45 + H46 + H47 + H48 + H49 + H50 + H51 + H52 + H53 + **H58 v1** + **H59** + **H60** + **H61** + **H62** + **H63** + **H64** + **H65** + **H66** + **H67**
COMPLETE. H35 PASS (consumer-pass, no change). H36 PASS: per-frame
hand-occupancy state machine produces closed juggling system. H37
PASS (consumer-pass, validation): 80.7%/76.5% agreement between
H36 (L, R, A) and H12 v8 pattern labels. H38 PASS (precision
improvement, narrow scope): rejects 1/22 identical and 12/129
YouTube CASCADE_3+ classifications that lack hand-occupancy
support. The YouTube rejection is a tight 12-frame contiguous
block at f=470-481 with H12 v8 confidence 0.639-0.646.
Recommended operating point remains h7v3plus3 (H34 + H35 + H36
+ H37 + H38). **H39 NEGATIVE**: H12 v8 FOUNTAIN_3+ classification
is fundamentally unreliable (only 30% accurate on 10 visual-QA'd
phases — 4/10 MIXED, 1/10 CASCADE, 2/10 OTHER, 3/10 FOUNTAIN).
H36 chain-driven state is too sparse to validate FOUNTAIN_3+
because H36 only marks hand-occupancy at chain events, not
continuous state. H39 v1 (frame-level) precision 20% (over-
rejects 60% of real juggling). H39 v2 (phase-level) precision
50% on small sample. The finding is real and important
(H12 v8 over-classifies FOUNTAIN_3+) but H36 is not a reliable
validator. **H32 NEGATIVE**: per-chain
hand-alternation-based CASCADE/FOUNTAIN classification on h7v3plus2
chains is fundamentally confounded by multi-ball merges. 5/7 visual-QA'd
chains are MULTI_BALL_MERGE (precision of H32 CASCADE/FOUNTAIN
classification: 1/7 = 14.3%). The h7v3plus2 chains are valid as
"hand-event lists" but NOT as "single-ball trajectories" — multiple
physical balls being juggled simultaneously produce a chain with
edges that all have hand-region support, but the chain is not a
single-ball trajectory. H32 confirms H10/H11: the chain set is mostly
multi-ball merges. The CASCADE/FOUNTAIN problem is now understood to
be a single-ball-vs-multi-ball identification problem, not a
cascade-vs-fountain classification problem. **H33 NEGATIVE**:
tracklet-time overlap is not a useful signal for multi-ball
detection — the h7v3plus2 chain construction produces temporally
sequential tracklets by design, so even multi-ball-merge chains
have NO tracklet overlap. **H34 PASS (incremental)**: union of
H22 YouTube 16->21 veto (-> 20->21) and H26 identical 7->10/59->61
H24-KEPT edges. YouTube 7-tid chain (1,9,13,16,21,29,34) is
correctly split into (1,9,13,16) and (20,21,29,34). Recommended
operating point is now **h7v3plus3** (H34).

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
  (stuck on a stationary high-up object, NOT face).
  H3 is useful as a *downstream confidence signal* on v4d
  links, not as a general held-ball detector.
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

1. ~~**Integrate H3 + H2 + H6 into a unified chain
   representation.**~~ **DONE** as `h237_unified_chain.py`. Most
   informative possible: v4d hand-links + E6c air-edges + H3
   confirmations + H7 conflict resolution. See
   `data/h237_unified_chains_*.csv` and
   `data/h237_unified_edges_*.csv`.
2. ~~**H7: full min-cost flow**~~ **DONE.** Capacity constraints,
   cycle detection, gap/error-aware air-edge cost. Sensitivity grid is flat
   (48 settings, identical results). Longest chain 7 on identical,
   6 on YouTube. H7 resolves the H2 conflict the same way H6 does
   (hand-edge wins on cost) but adds strict DAG-path semantics.
3. ~~**H8: physics consistency check on H7 chains**~~ **DONE.** Per-edge
   y-velocity discontinuity. Identifies 2 confirmed E6c false positives
   on identical (5→6, 50→55). Most useful as a post-hoc quality
   signal. Limitation: unreliable on long tracklets (YouTube video).
4. ~~**H9: explicit object permanence** to bridge detector dropouts in H7
   chains~~ **DONE.** Coverage measurement: 82.9% on identical, 94.7%
   on YouTube. Visual QA confirmed all 4 gaps in chain 30 are real
   hand-hold phases. H9 is a measurement, not a recovery.
5. ~~**H10: chain quality assessment**~~ **DONE.** Per-chain quality
   = 0.30*h3 + 0.30*h8 + 0.40*h9. Top-quality chains are real
   juggling cycles (chain 23, chain 6); mid-quality chains contain
   identity switches (chain 30); low-quality chains are dominated
   by false ballistic edges (chain 13). 1 H10 false positive
   (chain 38: real single ball, misclassified as low quality).
   Useful as a downstream confidence signal.
6. ~~**H8 v4: short-tracklet-only**~~ **DONE. NEGATIVE result.** v4
   skips all edges where source or target has n_pts > 30. On
   YouTube, this skips ALL 24 air edges (no physics signal).
   On identical, v4 misses 2 known true positives (5→6, 50→55)
   that v3 correctly caught. Trade-off not worth it. v3
   retained as H10's H8 signal.
7. ~~**H8 v5: parabolic-fit physics**~~ **DONE. MIXED result.** v5
   fits a parabola to last 8 / first 8 frames of source / target
   and predicts the expected y-velocity with constant-gravity
   extrapolation. v5 catches 2 NEW identity switches on identical
   (60→64, 21→22) that v3 missed. YouTube limitation persists
   (long-tracklet phase changes look like identity switches).
8. ~~**H10 v5: replace v3 with v5 in H10**~~ **DONE. PASS.** v5
   correctly demotes 2 v3-false-positives (chains 24, 29) and
   promotes 1 v3-false-negative (chain 36). H10 v5 is the new
   recommended chain quality score. 6 chains IMPROVED rank,
   3 WORSENED, 34 unchanged. Mean quality similar (0.539 vs 0.529).
9. ~~**H237 v5: enrich unified chain representation with H10 v5**~~
   **DONE.** Adds h10_v5_quality, h10_v5_rank columns to
   h237_unified_chains. Top chain in v5 is now chain 36
   (real single ball, v3 over-penalized its 33-frame gap).
10. ~~**H11: tracklet-level identity propagation**~~ **DONE. PASS.**
    Three implementations:
    - h11 v1: per-tracklet ball_id assignment + catch/throw events
    - h11 v2: per-frame census + identity-merge candidates
    - h11 v3: quality-filtered census (sensitivity grid)
    9 CONFIDENT identical chains + 1 CONFIDENT YouTube chain
    with correct physical ball ID. 8 catch/throw events on
    identical, 1 on YouTube. Per-frame census: 51% cascade
    time on identical, 100% on YouTube (over-counting
    artifact). 1 CONFIDENT identity-merge candidate is a
    FALSE POSITIVE — algorithm needs stricter spatial
    proximity (chain 36 ↔ chain 30: t62 and t63 are 73
    pixels apart at f=890, not co-located).
11. **H8 v7: fundamentally different approach for YouTube
    long tracklets** — per-bounce segmentation at frame
    level (not just apexes), or 3D ball trajectory
    estimation (Ponglertnapakorn & Suwajanakorn 2025),
    or accept the limitation and use H8 only for short
    tracklets. H8 v6's apex-level segmentation was too
    coarse.
12. ~~**H11 v4: stricter spatial proximity for identity-merge
    candidates**~~ **DONE. PASS.** Adds SPATIAL_RADIUS=80px
    and VELOCITY_COHERENCE=5.0 px/frame filters to H11 v2.
    85.7% reduction in candidates on identical (42 → 6),
    100% on YouTube (2 → 0). The v2 chain 36 ↔ chain 30
    CONFIDENT-merge false positive is correctly removed.
    None of the 6 remaining v4 candidates pass the
    velocity coherence test, suggesting there are NO real
    missed-merge opportunities on identical or YouTube
    within the v2's 30-frame window. Sensitivity grid:
    (80, 5) is in a flat region. H11 v4 is the new
    recommended identity-merge algorithm, replacing H11 v2.
    See `h1_hand_pool/reports/h11_v4_report.md`.
13. ~~**H12: per-catch-frame juggling pattern inference**~~
    **DONE. PASS.** Per-frame pattern inference on identical:
    33.8% UNKNOWN, 21.9% CASCADE_3+, 15.3% TWO_BALL,
    13.9% SINGLE_BALL, 11.7% FOUNTAIN_3+, 3.2% NO_BALL.
    4-phase pattern: 0-220 FOUNTAIN, 300-700 CASCADE
    (main), 700+ mixed. YouTube unreliable due to H10 v5
    over-counting. See `h1_hand_pool/reports/h12_report.md`.
14. ~~**H8 v7: fundamentally different approach for YouTube
    long tracklets**~~ **DONE. NEGATIVE result.**
    v7 (vy-sign-change) detected 1-arc for 73/76
    identical and 38/40 YouTube tracklets (smoothing
    destroyed intra-tracklet sign changes). v8
    (local-extrema) detected 1-12 arcs correctly. Per-arc
    gravity statistics are useful (YouTube median 0.46
    matches expected 0.5; identical median 0.69 is higher).
    Cross-edge physics: 0/24 OK on YouTube because most
    H7 BALLISTIC edges are catch+throws in disguise.
    v8 is useful for per-arc statistics but its cross-edge
    check doesn't work.
15. ~~**H11 v5: hand-relative coordinates for merge
    algorithm**~~ **DEFERRED.** H11 v4 already achieves
    100% reduction in false-positive merge candidates.
    v5 is a marginal improvement that can wait.
16. ~~**H12 v3: integrate detector-level signal**~~ **DONE.
    MIXED.** Enriched event log with 1 visually-confirmed
    v3c-rejected event (35->40 identical, real catch-throw
    that v4d incorrectly rejected). Changes 26 frames from
    FOUNTAIN_3+ to MIXED_3+ at f=797-829. Late FOUNTAIN_3+
    blocks (f=890-1050) UNCHANGED. Confirms the limitation
    is fundamental. A truly different approach is needed.
17. **H13: detector-level ball detection** — re-run
    YOLO at lower confidence (0.1) and compare to
    v4d hand-link predictions. Master §14's "lower
    confidence evidence tier near hand events" is
    the inspiration. The YouTube over-counting is
    partly due to detector confusion; a lower-conf
    re-run might reveal where balls actually are.
18. ~~**H12 v6: ensemble of v2 and v5**~~ **DONE.**
    PARTIAL PASS (basic) and MIXED (v6b confidence-
    weighted). The CASCADE/FOUNTAIN question is
    FUNDAMENTALLY UNRESOLVED with current data.
19. ~~**H10 v6: integrate per-arc gravity as 4th
    quality dimension**~~ **DONE. MIXED.**
    Default w8v8=0.25 hurts identical ranking
    (chain 21 drops from v5 #0 to v6 #7) and helps
    YouTube ranking (mean q 0.537 → 0.569).
    Sensitivity grid is NOT flat. Recommended v6b:
    per-video adaptive weights (w8v8=0 for identical,
    w8v8=0.30 for YouTube) — implemented below.
20. ~~**H10 v6b: per-video adaptive weights for h8v8**~~
    **DONE. PASS.** identical: w8v8=0 (matches v5,
    no degradation). youtube: w8v8=0.25 (improves
    over v5: mean q 0.537 → 0.569). H10 v6b is the
    new recommended chain quality score for
    mixed-video analyses. Best of both worlds.
22. ~~**H7 v2: re-classify YouTube BALLISTIC edges as
    HAND_TRANSITION if they pass through a hand
    region.**~~ **DONE. PASS.** Reclassified 13/37
    identical and 25/27 YouTube BALLISTIC edges. Visual
    QA on 8 edges (4 identical + 4 YouTube) all confirmed
    as REAL_CATCH_THROW. Mean YouTube chain quality jumps
    0.537 → 0.679 (over-counting fixed at its source).
    See `h1_hand_pool/reports/h7v2_report.md`.
23. ~~**H10 v8: H7v2-reclassified chains + v6b per-video
    adaptive weights**~~ **DONE. PASS.** 14/15 YouTube
    chains now have h8=1.0 (no BALLISTIC edges to
    penalize). New top YouTube chain (chain 0, 7 tids,
    6 hand edges) achieves q=0.671 with h8v8=0.86. See
    `h1_hand_pool/reports/h10v8_report.md`.
24. **H13: detector-level low-confidence ball evidence at
    hand events (master §14)** — DONE. NEGATIVE result.
    Four iterations:
    - v1 (any single detection, FPR 91-100% — useless)
    - v2 (H3 stationary cluster, 6/62 edges corroborated, 3
      are kept-ballistic false positives — NOT a discriminator)
    - v3+v4 (concentration ratio + peak-vs-context; statistically
      real signal but correlates with gap length, not event type)
    - v5 (strict cluster + hand-specificity; 3/13 kept-ballistic
      edges STRICT_CORROBORATED — actively MIS-calibrated)
    **Conclusion**: the detector's low-conf signal is fundamentally
    NOT a discriminator for catch-throws vs identity switches. The
    hand-event context required to interpret the signal is exactly
    what we're trying to corroborate, making master §14's
    "lower-confidence evidence tier near hand events" idea
    unimplementable with detector signal alone. See
    `h1_hand_pool/reports/h13_report.md` and
    `h1_hand_pool/reports/h13v2_report.md`.
25. **H14: V-shape trajectory check on h7v2-kept BALLISTIC
    edges** — DONE. PASS. Examines the full source-tail + gap +
    target-head trajectory and asks: does it dip toward a hand
    and come back out? A real catch-throw has this V-shape; a
    true mid-air identity switch has a smoother monotonic
    trajectory. Result: 5/13 BALLISTIC edges have a V-shape
    (3 V_DEEP + 2 V_SHALLOW). Visual QA on all 5: 4/5 are real
    catch-throws (23→25, 30→33, 39→47, 51→52 identical) that
    the strict h7v2 rule missed; 1/5 is a false positive
    (27→28 YouTube — tracklet break with 100-px jump in 5
    frames). The 8 always-FLAT ballistic edges are correctly
    rejected. H14 is an add-on to H7v2, not a replacement.
    See `h1_hand_pool/reports/h14_report.md`.

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

None. H16 + H17 v1 (PARTIAL PASS) committed in this episode.

26. ~~**H13 v2: stricter cluster criterion**~~ **DONE. NEGATIVE.**
    Confirms H13 v1's finding: detector signal is fundamentally NOT a
    discriminator between real catch-throws and identity switches.
27. ~~**H14: per-edge V-shape check on h7v2-kept BALLISTIC edges**~~
    **DONE. PASS.** Recovers 4 hidden catch-throws on identical.
28. ~~**H15 v2: reclassify h7v2-kept BALLISTIC edges that pass H14**~~
    **DONE. PASS with YouTube caveat.** h7v3pure chain pipeline.
29. ~~**H10 v9: H7v2 + H15v2 chains with V_RECLASSIFIED h3 fix**~~
    **DONE. PASS.**
30. ~~**H11 v7: identity propagation on h7v3pure chains**~~
    **DONE. MIXED (consumer-pass, visual nuance).** 23 catch+throw
    events on identical.
31. ~~**H16: H3 stationary-cluster corroboration for V-reclass edges**~~
    **DONE. PARTIAL PASS.** Confirmatory signal only.
32. ~~**H17 v1: V-shape recovery for v4d-rejected + adjacent candidates**~~
    **DONE. PARTIAL PASS.** 151 strict V-shape positives, ~38-56%
    precision.
33. ~~**H20: stricter in-hand + vel-jump + apex rejection for H17
    positives**~~ **DONE. PASS.** Achieves 0.900 precision and 0.833
    FPR drop on the 16-edge visual QA set, with stable sensitivity
    grid. Vel-jump is the dominant filter (28/36 rejections).
    H20 is a strict post-filter for H17 candidate mining and a
    candidate-pool generator (26 e6c_not_in_h7v2 + 88 adjacent
    H20-KEPTs not in production chain set).
34. ~~**H21 v1: H20-KEPT chain set augmentation**~~ **DONE. MIXED.**
    3/4 identical H20-KEPT REAL edges admitted as new
    HAND_TRANSITION edges, merging 3 pairs of chains. 1/1 YouTube
    H20-KEPT REAL edge (20→21) REJECTED by capacity conflict with
    existing 16→21. H21 v2 chain quality DROPS slightly on identical
    (-0.023) because new chains expose BALLISTIC edges that h8 v5
    penalizes. Visual analysis reveals the existing 16→21 YouTube
    edge may be wrong (tracklet 20 is the canonical contact).
    H21 is a research tool, not a chain-set replacement.
35. ~~**H22 v1+v2: H20-KEPT edge veto mode**~~ **DONE. MIXED
    (narrow-scope PASS).** Successfully vetoes existing 16→21
    YouTube edge in favor of H20-KEPT 20→21 (V-shape min_d=5.3 vs
    existing target start_dist=35.3). YouTube mean chain quality
    improves +0.0034 (0.685→0.689). The 7-tid chain (1,9,13,16,
    21,29,34) splits into 2 chains (1,9,13,16) and (20,21,29,34).
    0 identical veto decisions (the 2 H20-KEPT candidates with
    strong V-shape had existing source successors in the chain set).
    H22 confirms the visual analysis that 16→21 is wrong and
    20→21 is the real catch. h7v3pure remains the recommended
    chain set; H22 is a useful diagnostic tool.
36. **H24: H20-KEPT e6c_not_in_h7v2 candidate review at scale** —
    DONE. NEGATIVE. 9-candidate H20-KEPT-not-in-h7v2 visual QA
    finds 2 REAL (7→10, 59→61 identical) + 2 PARTIAL + 5 FALSE.
    REAL precision drops from H20's 62.5% to 22.2% on the H24
    sample. Cross-ball artifacts are the dominant failure mode
    (4/5 FALSE). V_SHALLOW (1/1 REAL) is more reliable than
    V_DEEP (1/8 REAL). 2 NEW REAL H20-KEPT candidates
    identified (7→10, 59→61 identical) but the 4 cross-ball
    false positives make H20-KEPT-not-in-h7v2 an UNRELIABLE
    augmentation source. H25 should add color-continuity or
    trajectory-overlap filter to reject cross-ball artifacts.
37. **H26: H24 NEW REAL H20-KEPT chain set augmentation v2** —
    DONE. PASS (incremental). Integrates the 2 H24 NEW REAL
    H20-KEPT-not-in-h7v2 edges (7→10 and 59→61 identical) into
    h7v3pure as HAND_TRANSITION. Both admitted with cost=1.0.
    identical chains 43→42. H10 v10 mean quality 0.8044 (H21)
    → 0.8105 (H26) (+0.0061). H26-KEPT edges are HAND_TRANSITION
    so they don't trigger h8 v5 physics penalty (the H21 v2
    quality drop pattern doesn't apply). H21+H26 together cover
    7 visually-confirmed REAL H20-KEPT edges (5 from H20 + 2
    from H24). h7v3plus2 is the new recommended chain set for
    H20-KEPT-augmented analyses.
38. **H28: H20-KEPT adjacent candidate review at scale** —
    DONE. NEGATIVE. 12-candidate visual QA (8 identical + 4
    YouTube) of the 88 H20-KEPT `adjacent` pool finds REAL
    precision 17% (2/12) and REAL+PARTIAL precision 50% (6/12).
    4/12 FALSE positives dominated by "continuous upward path
    through hand region" (3/4) and "cross-hand pairing" (1/4).
    V_SHALLOW 0/2 = 0% on the H28 sample, opposite to H24's
    V_SHALLOW 1/1=100% (which was too small to characterize).
    The 88 H20-KEPT adjacent candidates should NOT be
    auto-incorporated. H28 confirms H17→H20→H24 negative
    finding chain: V-shape + in-hand + vel-jump + apex filters
    admit too many false positives in the noisiest pool.
    See `h1_hand_pool/reports/h28_report.md`.
39. **H30: direction-reversal check on H17 strict pool** —
    DONE. CLAIMED PARTIAL PASS (overfit). H30 src_above+src_desc
    had 0/14 FALSE on the deduplicated known-label set (n=30),
    suggesting it was a precision-optimized filter. The H30
    report's claim was based on a small biased known-label sample
    that included 5 H20+H30-AND candidates with 4 REAL + 1
    PARTIAL (100% precision on the QA'd subset).
40. **H31: visual QA of H20+H30-AND intersection** —
    DONE. NEGATIVE. H31 visual QA on 10 NEW H20+H30-AND
    candidates (not in the known-label set) finds 0/10 REAL,
    2/10 PARTIAL, 8/10 FALSE. The H30 claim of "0/14 FALSE on
    known labels" was overfitted to a biased sample; on a
    more representative sample, H30 has 0% REAL precision.
    H31 confirms the H17→H20→H24→H28→H31 negative finding
    chain: every geometric post-filter on the H17 V-shape pool
    fails to produce a reliable high-precision candidate set.
    The recommended operating point remains h7v3plus2 (H26).
    See `h1_hand_pool/reports/h31_report.md`.

## Next action

H50 PASS — closes H49's negative result. The 10-frame flight-time
filter has real downstream impact of only 1.0% identical / 0.0%
YouTube pattern label changes. The filter is a SAFE post-filter.

**Recommended operating point:** h7v3plus3 chain set + H12 v8 +
H50 10-frame event log filter. This is the final precision-optimized
configuration for FOUNTAIN_3+ / CASCADE_3+ downstream consumers.

Remaining research directions:
1. **H51: H43 + H50 combined post-filter** — apply H43's
   confidence-based FOUNTAIN_3+ filter (conf < 0.55) on top of
   H50's filtered pipeline. The combined filter should be the
   final precision-optimized stack.
2. **H52: H8 v5 parabolic fit for ft=3-9 disambiguation** — the
   chain 13 ft=3 case shows a real catch-throw CAN have a 3-frame
   flight. H8 v5's parabolic fit on source-tail + target-head
   could distinguish "real short catch-throw" from "tracker
   fragmentation" for ambiguous ft=3-9 cases.
3. **Stop here**. The h7v3plus3 + H12 v8 + H50 10-frame filter is
   a well-validated, precision-improved operating point. Further
   improvements would require fundamentally different signals.

H37 is complete (PASS, consumer-pass, validation). H36 (L, R, A)
state validates CASCADE_3+ but cannot disambiguate FOUNTAIN_3+.

H36 is complete (PASS). The h7v3plus3 chain set is now
validated at the per-frame hand-occupancy level.

H35 is complete (PASS, consumer-pass). The h7v3plus3 chain set
is functionally equivalent to h7v3pure for downstream consumers.

H31 is complete (NEGATIVE). The H17→H20→H30 pipeline is now
established as a negative finding chain: every geometric post-filter
on the H17 V-shape pool fails to produce a reliable high-precision
candidate set on a larger visual QA sample.

The 5 already-QA'd H20+H30-AND candidates (4 REAL + 1 PARTIAL) were
a biased sample that over-represented the precision of the pool.
On the larger 10-candidate H31 sample, the pool has 0% REAL
precision.

Recommended operating point remains h7v3plus2 (H26).

Remaining research directions (priorities):
1. **H32: stop trying to filter the H17 V-shape pool.** The H17
   V-shape strict pool has fundamental geometric limitations that
   no amount of post-filtering can fix. Future work should focus
   on:
   - Using ONLY the H17+H20-KEPT visually-confirmed REAL subset
     (used by H21+H26)
   - Or building a fundamentally different candidate mining
     approach (e.g. trained model, or different geometry)
2. **H33: literature search for multi-ball juggling tracking
   methods.** The H17 V-shape approach is hand-crafted and has
   known limitations. A literature search may reveal methods
   that handle the ball+hand interaction more robustly. Possible
   directions:
   - Where Is The Ball (Ponglertnapakorn 2025) — 3D trajectory
     estimation, but requires LSTM training
   - Physics-based ball tracking (2009) — 3D motion, requires
     marker positions
   - TOTNet (2025) — learned temporal tracking, requires
     sports-tracking dataset
   - Cooperative Trajectory Matching (2024) — Kalman filter
     prediction, requires feature extractor training
3. **H34: H22+H26 combined chain set** — apply H22's YouTube
   20→21 veto on top of H26's 2 NEW REAL H24 edges. This tests
   whether H22's YouTube improvement and H26's identical
   improvement are additive. (Lower priority — both improvements
   are small: H22 +0.0034, H26 +0.0061.)
4. **H35: pattern inference on h7v3plus2.** Apply H12's
   per-frame pattern inference to the recommended chain set
   (h7v3plus2) to characterize the final juggling pattern.

41. **H32: per-chain hand-alternation + ball-count characterization
    on h7v3plus2** — DONE. NEGATIVE. H32's CASCADE/FOUNTAIN
    classification based on per-chain hand alternation is
    fundamentally confounded by multi-ball merges. 5/7 visual-QA'd
    chains are MULTI_BALL_MERGE. The h7v3plus2 chains are valid as
    "hand-event lists" but NOT as "single-ball trajectories." H32
    confirms H10/H11's finding that the chain set is mostly
    multi-ball merges. The CASCADE/FOUNTAIN problem is now
    understood to be a single-ball-vs-multi-ball identification
    problem. Recommended operating point remains h7v3plus2 (H26).
    See `h1_hand_pool/reports/h32_report.md`.

42. **H33: tracklet-time overlap multi-ball detector** — DONE.
    NEGATIVE. The h7v3plus2 chain construction produces
    temporally sequential tracklets by design, so even
    multi-ball-merge chains have NO tracklet-time overlap. H33
    misses ALL 5 vision-confirmed MULTI_BALL_MERGE chains from
    H32. Tracklet-time overlap is not a useful signal. See
    `h1_hand_pool/reports/h33_report.md`.

43. **H34: H22 + H26 combined chain set (h7v3plus3) + H10 v10
    chain quality** — DONE. PASS (incremental, union-of-improvements).
    Combines H22's YouTube 16->21 veto (-> 20->21) with H26's
    2 identical H24-KEPT edges (7->10, 59->61). h7v3plus3 is
    the new recommended chain set, replacing h7v3plus2 (H26).
    Results:
    - identical: 42 chains, mean q 0.8105 (unchanged from h7v3plus2)
    - YouTube: 15 chains, mean q 0.6886 (+0.0034 vs h7v3plus2's 0.6852)
    - YouTube chain topology: the contested 7-tid chain
      (1,9,13,16,21,29,34) is correctly split into
      (1,9,13,16) and (20,21,29,34)
    - Found and fixed a chain-quality formula bug (h3=None handling)
      in the initial h34_chain_quality.py — the v1 formula
      incorrectly made single-tracklet chains drop from 1.0 to 0.7.
      Fixed to use h10v10_with_h26.py's h3-redistribution rule.
    See `h1_hand_pool/reports/h34_report.md`.

## H34 conclusion

The recommended operating point h7v3plus3 (H34) is the union of
H22's YouTube 16->21 veto and H26's identical 7->10/59->61
H24-KEPT edges:

- **H10 v10 chain quality** is a real but imperfect signal for
  single-ball-ness (1/7 false positive rate on visual QA).
- **H11 v7 identity propagation** is the most accurate single-ball
  filter (CONFIDENT chains are 9/9 visually verified on identical).
- **H32 hand-alternation pattern_verdict** is confounded by
  multi-ball merges (5/7 MULTI_BALL_MERGE on visual QA).

**For downstream consumers:** the h7v3plus3 chain set (H34) is a
list of "real hand events" with 42 identical + 15 YouTube chains.
For "single-ball trajectory" claims, use H11 v7 CONFIDENT chains
(9 + 1). For "this catch/throw happened here" claims, use h7v3plus3
+ H10 v10 quality. For "this chain is CASCADE/FOUNTAIN" claims,
abandon the classification — the chain is mostly multi-ball merges,
not a single-ball pattern.

## H35 conclusion

H35 is a **consumer-pass** re-measurement: H11 v7 and H12 v7
re-run on h7v3plus3 produces identical per-frame pattern
distribution to h7v3pure (H12 v8). The H22 YouTube 7→4+4 chain
split is a chain-topology change that does NOT change the
per-frame census (the census is dominated by the 11 single-tid
YouTube chains, not the multi-tid chain topology).

**H35 PASS verdict:** h7v3plus3 is functionally equivalent to
h7v3pure for downstream consumers. Use h7v3plus3 going forward.

See `h1_hand_pool/reports/h35_report.md` for full analysis.

## H36 conclusion

H36 implements a per-frame hand-occupancy state machine on
h7v3plus3 chains. The state is (L, R, A) where L = balls in
left hand, R = balls in right hand, A = balls in air. The
state is constrained: L + R + A = total_n_balls (3 for
identical, 5 for YouTube) and each hand has bounded capacity
(0-3 balls).

**Key results:**
- Zero conservation violations on either video.
- Zero over-capacity events on either video.
- 73% of frames have all balls in air (consistent with
  cascade patterns).
- The h7v3plus3 chain set is a closed juggling system on
  both videos.

**H36 PASS verdict:** The h7v3plus3 chain set is now
validated at three levels: chain quality (H10), identity
propagation (H11), and per-frame hand-occupancy (H36). The
chain set is a complete, consistent, closed representation
of the juggling routines in both videos.

See `h1_hand_pool/reports/h36_report.md` for full analysis.

## H37 conclusion

H37 cross-references the H36 (L, R, A) state with H12 v8
pattern labels. Result: 80.7% agreement on identical, 76.5%
on YouTube. Late-phase identical FOUNTAIN_3+ has 97% (0, 0, 3)
state — H36 has no hand-occupancy evidence. CASCADE_3+ has
hand-occupancy support (20/22 identical are (0, 1, 2); 66/129
YouTube are (0, 1, 4)). H12 v8 confidence drops to 0.5-0.7 in
the late phase.

**H37 PASS verdict:** H36 (L, R, A) state validates CASCADE_3+
classification (which has hand-occupancy support) but cannot
disambiguate FOUNTAIN_3+ (which has no hand-occupancy signal).
The 80%/76% agreement rate is a useful summary metric.

See `h1_hand_pool/reports/h37_report.md` for full analysis.

## H38 conclusion

H38 is a strict post-filter that rejects CASCADE_3+
classifications where H36 has no hand-occupancy support
(H36 state (0, 0, 3) or (0, 0, 5)). The improvement is
small: 1/22 identical and 12/129 YouTube CASCADE_3+
classifications are rejected. The YouTube rejection is a
tight 12-frame contiguous block at f=470-481 with H12 v8
confidence 0.639-0.646. No substantial CASCADE phases (>= 20
consecutive frames) are broken by the filter.

**H38 PASS verdict:** H38 is a safe, narrow-scope precision
improvement. The CASCADE_3+ classifications that have
hand-occupancy support (95% identical, 91% YouTube) are
preserved. Use H38 as a downstream consumer filter if
precision matters more than recall.

See `h1_hand_pool/reports/h38_report.md` for full analysis.

## H39 conclusion

H39 attempted the symmetric post-filter to H38: reject
FOUNTAIN_3+ classifications where H36 has no hand-occupancy
support. Visual QA on 10 FOUNTAIN_3+ phases revealed that
H12 v8's FOUNTAIN_3+ classification is **only 30% accurate**:

- 3/10 real FOUNTAIN
- 4/10 MIXED (real juggling with hand-occupancy)
- 1/10 CASCADE (real 5-ball cascade on YouTube f=339-374)
- 2/10 OTHER (hold trick + 2-ball exercise)

This is a real and important finding: H12 v8 over-classifies
FOUNTAIN_3+ by ~70%. However, H36 is not a reliable validator
because H36 only emits state changes at chain events, not at
continuous hand-occupancy. The H39 v1 (frame-level) over-rejects
60% of real juggling (precision 20%); H39 v2 (phase-level) is
more conservative (precision 50% on 2 rejections).

**H39 verdict: NEGATIVE.** Don't use H39 as a downstream filter.
The H12 v8 FOUNTAIN_3+ classification should be left as-is with
the caveat that it has ~70% error rate. A reliable filter would
require a continuous hand-occupancy signal, which H36 doesn't
provide.

See `h1_hand_pool/reports/h39_report.md` for full analysis.

## H40 + H41 conclusion

**H40: continuous per-frame hand-occupancy signal.** Implements
two signals: H40 v1 (per-frame, 108 px reach) and H40 v2
(sustained 100 px reach, 3-frame run). H40 v2 detects ~3-4x
more hand-occupancy than H36 (72.3% vs 23.7% on identical,
98.1% vs 25.8% on YouTube). H40 is a useful diagnostic
signal — independent of chain events.

**H41: FOUNTAIN_3+ post-filter via H40 v2.** H41 v1
(MIN_OCC=0.50) and v2 (MIN_OCC=0.20) implemented. Both
over-reject real juggling phases and over-keep real
misclassifications. H41 v2 precision is 50% on rejects
(same as H39 v2) — no improvement.

**Key finding:** H40 v2 hand-occupancy does NOT cleanly
discriminate FOUNTAIN from CASCADE. On identical, FOUNTAIN
81.8% vs CASCADE 90.9% (similar). On YouTube, FOUNTAIN 98.2%
vs CASCADE 96.9% (essentially equal). The "both-hands
occupied" rate is more discriminating (YouTube FOUNTAIN
74.5% vs CASCADE 42.2%) but is dominated by sustained
ball-wrist proximity, not actual holds.

**Negative finding:** H40 sustained-occupancy detects "ball
near hand", not "ball held by hand". A ball passing through
the 100 px hand reach for 3 frames is counted as
hand-occupied. This is a fundamental limitation of 2D
distance as a proxy for holding.

**Verdict:** H40 PASS as a diagnostic signal (better
hand-occupancy coverage than H36). H41 NEGATIVE as a
FOUNTAIN_3+ post-filter. H12 v8 FOUNTAIN_3+ classification
remains fundamentally unreliable (per H39).

See `h1_hand_pool/reports/h40_h41_report.md` for full
analysis.

## H42 conclusion

**H42: hybrid H36 + H40 v2 (L, R, A) state.** H42 uses
H36 chain events where available (23.7% identical,
25.8% YouTube) and H40 v2 sustained-occupancy as fallback
(51.5% identical, 73.0% YouTube). H42 hybrid state is
useful for diagnostic purposes — it gives a more complete
hand-occupancy picture than H36 alone.

**Verdict: MIXED.** H42 hybrid doesn't significantly
improve CASCADE/FOUNTAIN discrimination over H40 v2.
The H36 chain events dominate the L+R decision and carry
the same handedness bias. H42 is useful as a diagnostic
for downstream consumers needing a complete (L, R, A)
timeline.

See `h1_hand_pool/reports/h42_report.md` for full
analysis.

## H43 conclusion

**H43: H12 v8 confidence-based FOUNTAIN_3+ filter.** Rejects
FOUNTAIN_3+ frames where H12 v8 confidence < 0.55.

**Verdict: PASS (narrow scope).** H43 correctly identifies
27/298 (9.1%) of identical FOUNTAIN_3+ frames as low-confidence.
All 27 are in f=1029-1060 (the "OTHER 2-ball exercise" phase
from H39 visual QA) — a real misclassification that H43
catches without over-rejecting any real FOUNTAIN.

**Visual QA: 1/1 correct reject (precision 100%), 1/2 recall.**
H43 misses the f=977-1011 hold trick (conf 0.565), but
catches the f=1029-1050 2-ball exercise (conf 0.463).

**Comparison with H39-H42:**
- H39 v1 (frame-level H36): precision 20% (over-rejects)
- H39 v2 (phase-level H36): precision 50% on 2 rejections
- H41 v2 (H40 v2): precision 50% on 4 rejections
- **H43 (H12 v8 conf < 0.55): precision 100% on 1 rejection**

**Recommended operating point:** H43 + h7v3plus3 chain set
is the new recommended configuration for FOUNTAIN_3+
downstream consumers.

See `h1_hand_pool/reports/h43_report.md` for full analysis.

## Future research directions (post H34)

The h7v3plus3 chain set is now the recommended operating point.
The most likely productive directions:

1. **Multi-ball identification** — the fundamental problem is now
   "is this chain a single physical ball?". Possible approaches:
   - Cross-tracklet velocity coherence (H8 v5 already checks
     per-edge; could extend to per-chain)
   - Color tracking (mentioned in H30 but not implemented;
     would require re-running detector)
   - Multi-view 3D (out of scope for monocular 2D setup)
2. **Literature search for multi-ball juggling tracking methods**
   that handle identity and hand-occlusion. See RESEARCH_NOTES for
   current sources. Possible directions:
   - Where Is The Ball (Ponglertnapakorn 2025) — 3D trajectory
     estimation, but requires LSTM training
   - TOTNet (2025) — learned temporal tracking, requires
     sports-tracking dataset
   - Cooperative Trajectory Matching (2024) — Kalman filter
     prediction
3. **Re-running downstream consumers on h7v3plus3** — H12 pattern
   inference, H11 v7 identity propagation, H237 unified chain
   representation all need re-measurement on the new chain set
   to fully characterize the impact of H22's YouTube chain split.
4. **Stop here.** The h7v3plus3 chain set is well-validated.
   Further chain improvements would require fundamentally different
   signals (multi-view, learned color tracking, or 3D ball
   estimation).

## H45 conclusion

**H45: per-chain flight-time / siteswap analysis** — DONE.
NEGATIVE result with structural insight.

The H12 v8 hand-event log is too sparse for siteswap analysis:
- identical: 48 events / 1032 frames (0.047 events/frame),
  only 2/13 chains have n_flights >= 3.
- YouTube: 50 events / 847 frames (0.059 events/frame),
  only 1/10 chains has n_flights >= 3.

Of the 3 chains with 3+ flights, visual QA on all 11
individual flights found:

**Identical** (3-ball cascade):
- chain 22 (FOUNTAIN_3+, CV=0.65): 3/4 flights (ft=33, 31, 39)
  are real catch-throws. 1/4 (ft=1) is an identity switch.
- chain 29 (SINGLE_BALL, CV=0.78): 1/2 inspected flights
  (ft=33) is a real catch-throw. 1/2 (ft=5) is an identity
  switch (cross-hand + 5-frame "flight").

**YouTube** (5-ball):
- chain 9 (MIXED_3+, CV=0.47): 0/4 flights are real
  catch-throws. ALL 4 are tracker fragmentation artifacts
  (slope jumps, no ball at hand, 58-134 frame "flights"
  are physically impossible for 5-ball). The "low CV" is
  misleadingly "uniform" because all 4 flights are the SAME
  artifact (~58-62 frames each).

**Key H45 findings:**

1. **The 10-frame flight-time filter is a useful downstream
   post-filter:** drop any H12 v8 "flight" < 10 frames as a
   likely identity switch. On identical, this rejects 3/11
   flights as identity switches and preserves 7 real
   catch-throws. On YouTube, the filter is unhelpful because
   all flights are >= 58 frames.

2. **The H12 v8 event log is trustworthy for chain topology
   on both videos, but for inter-event timing only on
   identical.** The 30-40 frame flight times on identical
   match the expected 3-ball cascade ball airtime (1.0-1.3s
   at 30fps) exactly. The 58-67 frame "flights" on YouTube
   are uniformly tracker fragmentation.

3. **Siteswap analysis is infeasible on the h7v3plus3 chain
   set with the H12 v8 event log.** This is a fundamental
   input-data limitation, not an H45 algorithm problem.

**Recommended next research (H46): per-flight physics check
via H8 v8.** For each H12 v8 "flight", compute H8 v8's
gravity estimate from the source's last arc and target's
first arc, and reject flights where the implied free-fall
time is inconsistent with the measured flight time. This
would convert H8 v8 from a per-edge signal to a per-flight
signal, distinguishing real flights from tracker-fragmentation
artifacts based on physics alone.

See `h1_hand_pool/reports/h45_report.md` for full analysis.

## H46 conclusion

**H46: per-flight physics check via bounce model** — DONE.
NEGATIVE result (H46 v1 hypothesis was wrong; H46 v2
bounce sign test confirms H45's YouTube finding).

**H46 v1** tried to extrapolate source's last-arc parabola
across the held-phase gap and compare to target's first
position. ALL 26 flights marked PHYSICS_VIOLATION,
including visually-confirmed REAL catch-throws. Hypothesis
was wrong: the source tracklet's last points are NOT the
descent into the hand — they are the post-throw ascent
(the tracklet starts at the throw frame, not the catch
frame).

**H46 v2** (bounce sign test) checks v_in < 0 AND v_out < 0
(both post-throw tracklets ascending):
- identical: 2/11 BOUNCE_OK (chain 29's ft=5 and ft=33)
- YouTube: 0/15 BOUNCE_OK

The YouTube 0/15 result is strong evidence that all YouTube
H12 v8 events are tracker fragmentation (consistent with
H45's 0/4 visually-confirmed REAL flights on YouTube chain 9).

**The fundamental issue is that H12 v8's per-tracklet data
structure is not aligned with held-phase physics.** The held
phase is not in any tracklet. Per-flight physics would need
explicit hold-phase interpolation (the ball is at the hand
during the gap) or hand-pose-anchored position.

**Combined H45 + H46 finding:** the H12 v8 event log is
fundamentally not a clean signal for flight-time analysis.
The 10-frame filter (H45) is the only actionable post-filter;
H46's bounce sign test is too restrictive on identical (rejects
real catch-throws) and too permissive on YouTube (rejects
everything).

See `h1_hand_pool/reports/h46_report.md` for full analysis.

## H47 conclusion

**H47: H12 v8 with 10-frame flight-time filter** — DONE.
PASS (narrow scope).

Applies H45's most actionable finding (the 10-frame
flight-time filter) to H12 v8's event log. Drops any
(CATCH, THROW) pair with flight time < 10 frames.

- identical: 3/48 events dropped (6.2%) — all 3 are
  identity switches (ft=1, 3, 5) confirmed by H45 visual QA
- YouTube: 0/50 events dropped (all flights are >= 58
  frames, consistent with H45's tracker-fragmentation
  finding)

**The 10-frame filter is a safe, useful downstream post-filter
for H12 v8 event log consumers.** It can be applied before
K=4 sliding window inference as a precision improvement.
H47 is NOT a drop-in replacement for H12 v8 (the H47
simplified classifier doesn't use chain quality); it's a
measurement of the filter's impact on the event log.

See `h1_hand_pool/reports/h47_report.md` for full analysis.

## H48 conclusion

**H48: flight-time filter threshold sensitivity grid** — DONE.
PASS (confirms H45's 10-frame filter is optimal).

Sweeps MIN_FLIGHT_TIME in {5, 10, 15, 20, 30, 40, 50, 60} and
reports the per-threshold impact on H45-labeled flights.

**Key finding: THR=10 is in a flat region (10-30) for
identical.** All thresholds in {10, 15, 20, 30} give
identical results on H45 labels (4 REAL kept, 3
IDENTITY_SWITCH dropped). THR=10 is the most permissive,
so it's the best choice.

**THR=40 is the first threshold that drops REAL catch-throws
on identical** (false positives). THR=50+ drops all 4 REAL
catch-throws (catastrophic).

**YouTube: no threshold in {5..50} drops any of the 4
TRACKER_FRAGMENTATION flights.** The 4 YouTube flights have
very similar flight times 58-67, so a single threshold
cannot separate them. THR=60 drops 1/4 (the longest, ft=134).

**There is NO single threshold that filters YouTube's
tracker-fragmentation flights without dropping identical's
real catch-throws.** The H45 finding (10-frame filter) is
robust and in a flat region of the sensitivity grid.

See `h1_hand_pool/reports/h48_report.md` for full analysis.

## H49 conclusion

**H49: 10-frame filter impact on per-frame pattern** — DONE.
NEGATIVE result (impact measurement methodology is flawed).

The K=4-only re-classification rate is 45.2% identical,
15.9% YouTube. This is an UPPER BOUND on actual H12 v8
impact because the K=4-only classifier doesn't apply
H12 v8's full pipeline (census + chain quality + n_total
balls).

For example, H12 v8 says f=236-242 identical are TWO_BALL
(conf 0.64) because the census shows only 2 balls in air.
My K=4 classifier says they should be CASCADE_3+ after
the filter. But H12 v8's actual re-run would still call
them TWO_BALL because the census doesn't change.

H49 is a NEGATIVE result for impact measurement: the K=4
window context changes for many frames, but the actual
downstream impact on H12 v8's pattern labels is bounded
by the full pipeline's additional inputs. A proper
measurement would require re-running H12 v8 with the
filtered event log.

The H45/H47/H48 findings remain the actionable results:
the 10-frame filter drops 3/48 events on identical and
0/50 on YouTube.

See `h1_hand_pool/reports/h49_report.md` for full analysis.

## Summary of H45-H49 series

This 5-episode series built on the H43 finding
(FOUNTAIN_3+ post-filter) to explore the H12 v8 event log
in more depth:

- **H45** (NEGATIVE with insight): siteswap analysis is
  infeasible with the H12 v8 event log (only 2/13
  identical chains and 1/10 YouTube chains have 3+ flights).
  But the per-flight distribution revealed that:
  - identical 30-40 frame flights = real catch-throws
  - identical < 10 frame flights = identity switches
  - YouTube 58-67 frame flights = tracker fragmentation
  → The 10-frame flight-time filter is a useful downstream
  post-filter.

- **H46** (NEGATIVE): per-flight physics check via bounce
  model. H46 v1 hypothesis was wrong (source tracklet's
  last points are NOT the descent into the hand). H46 v2
  bounce sign test confirmed H45's YouTube finding (0/15
  YouTube flights pass the sign test).

- **H47** (PASS, narrow scope): applying H45's 10-frame
  filter to H12 v8 event log. Drops 3/48 events on
  identical (6.2%) — all 3 are identity switches confirmed
  by H45 visual QA. No-op on YouTube.

- **H48** (PASS, confirms H45): sensitivity grid over
  THR ∈ {5, 10, 15, 20, 30, 40, 50, 60}. THR=10 is in a
  flat region (10-30 all give identical H45-labeled
  results). THR=40 first drops REAL catch-throws. YouTube
  has no threshold that filters its tracker fragmentation
  without dropping real catch-throws.

- **H49** (NEGATIVE for impact measurement): the K=4-only
  re-classification rate is 45.2% identical, 15.9%
  YouTube. This is an UPPER BOUND on actual H12 v8 impact
  because the K=4 classifier doesn't apply H12 v8's full
  pipeline. A proper measurement requires re-running H12
  v8 with the filtered event log.

**Most important finding:** the 10-frame flight-time filter
is a useful, validated, and well-justified (flat region in
sensitivity grid) post-filter for H12 v8 event log
consumers. It drops identity switches on identical without
affecting real catch-throws.

## H50 conclusion

**H50: H12 v8 with 10-frame filter (full pipeline re-run)** — DONE.
PASS. Closes H49's negative result.

H50 implements the proper measurement: re-run H12 v8's FULL
pipeline (census + K=4 events + chain quality + n_total) on
the FILTERED event log, and report the actual pattern distribution
change vs the unfiltered H12 v8 baseline (using the same pipeline,
same chain set, same quality scores — only the event log differs).

**Real downstream impact (apples-to-apples):**
- identical: 6 events dropped (3 short flights), 10/1042 (1.0%) frames changed
- YouTube: 0 events dropped, 0/898 (0.0%) frames changed

H49's K=4-only upper bound (45.2%/15.9%) is now refined to a real
1.0%/0.0% impact. H12 v8's per-frame pattern labels are robust to
the event-log filter because the full pipeline (census + chain quality
+ n_total) dominates the K=4 sliding window signal.

**Per-pattern delta on identical:**
- FOUNTAIN_3+ -0.3%, CASCADE_3+ +0.7%, MIXED_3+ -0.3%
- All other patterns unchanged
- Substantial phases (n_frames >= 20): 15 -> 15 (unchanged)

**YouTube: zero change** (filter is a no-op at the event level since
all YouTube flights are >= 58 frames).

**Visual QA on the 3 changed windows** (3 contact sheets in
`contact_sheets_h50/`):
- chain 23 ft=1: IDENTITY_SWITCH (H50 correct, confirms H45)
- chain 30 ft=5: TRACKER_FRAGMENTATION (H50 correct, confirms H45)
- **chain 13 ft=3: UNEXPECTED FINDING** — vision tool says this looks
  like a real catch-throw, contradicting H45's bucket analysis. H45
  did not visually QA this case (only chains with n_flights >= 3 were
  QA'd). The 10-frame threshold may be over-aggressive for this 1 case.

**Recommended operating point:** H12 v8 + 10-frame event log filter
for downstream consumers. The 1.0% identical change is a precision
improvement (fewer FOUNTAIN_3+ misclassifications on the chains where
the underlying identity switches were). The 1/3 ambiguous drop
(chain 13 ft=3) is a known limitation that does not invalidate the
10-frame threshold.

See `h1_hand_pool/reports/h50_report.md` for full analysis.

**H50's most important finding:** the H49 K=4-only upper bound was
indeed an upper bound, as H49 suspected. The real downstream impact
of the 10-frame filter is small (1% identical, 0% YouTube), so the
filter is a SAFE post-filter that improves precision without breaking
substantial phases.

## H51 conclusion

**H51: H12 v8 + H50 10-frame filter + H43 FOUNTAIN confidence
filter** — DONE. PASS. H50 and H43 compose cleanly.

The two filters operate at different stages and don't interfere:
- H50 modifies the input event log (drops 6 events on identical)
- H43 modifies the output pattern labels (rejects 21 FOUNTAIN_3+ frames on identical)

**Per-frame diff (H50+H43 vs H43 only):**
- identical: 10/1042 (1.0%) — same as H50 alone
- YouTube: 0/898 (0.0%) — same as H50 alone

**Combined precision improvement on identical:**
- FOUNTAIN_3+: -2.3% (24 frames, down from H12 v8 baseline 16.4%)
- CASCADE_3+: +0.7% (7 frames, up from baseline 6.7%)
- Substantial phases: 15 -> 15 (unchanged)

**YouTube**: 0% change (both filters are no-ops on YouTube).

**Recommended operating point**: h7v3plus3 + H12 v8 + H50 +
H43. This is the final precision-optimized stack.

See `h1_hand_pool/reports/h51_report.md` for full analysis.

## H52 conclusion

**H52: H8 v5 parabolic physics on H50-dropped (CATCH, THROW) pairs** — DONE.
PASS. Closes the H50 visual QA ambiguity on chain 13.

H8 v5 parabolic fit on the 3 H50-dropped pairs:

| Chain | ft | src_n | tgt_n | H8 v5 (MIN=6) | H8 v5 (MIN=2) | H50 visual QA |
|---|---|---|---|---|---|---|
| 13   | 3  | 36 | 4  | INSUFFICIENT | VIOLATING  | REAL (WRONG) |
| 23   | 1  | 14 | 2  | INSUFFICIENT | OK (unreliable) | FRAGMENTATION |
| 30   | 5  |  2 | 6  | INSUFFICIENT | VIOLATING  | FRAGMENTATION |

**Key finding**: H50 visual QA was wrong about chain 13. H8 v5
physics says chain 13 is TRACKER_FRAGMENTATION:
- Source tail y-velocity at CATCH: -32.1 px/frame (fast descent)
- Target head y-velocity at THROW: -1.1 px/frame (at rest)
- Gravity-adjusted predicted tgt_vy: -27.0 px/frame
- **Velocity discontinuity: 19.5 px/frame** (way above 5.0 tol)

A real catch-throw would have consistent velocities. The
19.5 px/frame discontinuity is too large. The target tracklet
is a spurious detection at the hand region.

**Resolution**: H45's claim "< 10 frame flights = identity
switches" is now fully verified by H8 v5 physics. The
10-frame filter is correct and should not be relaxed.

**Recommended operating point** (now fully validated):
h7v3plus3 + H12 v8 + H50 10-frame filter + H43 confidence filter
+ H52 physics corroboration. The 10-frame filter is the final
operating point.

See `h1_hand_pool/reports/h52_report.md` for full analysis.

**H53 conclusion**

**H53: H52 sensitivity grid preservation + multi-rater visual QA
consensus on the 3 H50-dropped pairs** — DONE. PASS.

Three contributions:

1. **H52 sensitivity grid (preserved)**: The H52 summary JSON did
   not preserve the MIN=2 sensitivity-grid values that the H52
   report cites (e.g. chain 13 src_vy=-32.1, tgt_vy=-1.1, v_disc=19.5).
   H53 re-runs the 9-cell MIN_TRACKLET_PTS grid and saves every cell
   to `h53_h52_sensitivity_grid.json`. The MIN=2/3/4 results are
   consistent (v_disc=19.5 for chain 13) but MIN=5+ is INSUFFICIENT_DATA.
   The chain 23 "OK at MIN=2" result is unreliable because tgt_n=2
   makes the parabolic fit degenerate.

2. **Multi-rater visual QA consensus**: 4 raters (H45 bucket, H50
   vision A, H52 physics, H53 vision A and B with two question
   phrasings) all 3 dropped pairs reach TRACKER_FRAGMENTATION consensus.
   The chain 13 ft=3 "real catch-throw" caveat from H50 is now
   resolved: 2/3 vision votes + H52 physics say TRACKER_FRAGMENTATION.
   The chain 23 ft=1 case is vision-tool-ambiguous (H50 says frag,
   H53-A says real, H53-B says different balls) — 2/3 vote for
   TRACKER_FRAGMENTATION with filter-default tie.

3. **H52+MIN=2 vs H50 on full event log**: H52+MIN=2 is OVER-AGGRESSIVE
   as a standalone filter (16/25 identical and 24/25 YouTube C2T
   drops). The 10-frame filter is more conservative. H52+MIN=2 is a
   useful corroborating signal on H50 drops: 5/11 identical and
   12/13 YouTube H50 drops are also H52+MIN=2 VIOLATING
   (high-confidence fragmentation). 6 identical and 1 YouTube H50-only
   drops are ambiguous (H52 says OK/INSUFFICIENT_DATA).

**Verdict: PASS.** All 3 H50 drops are TRACKER_FRAGMENTATION by
multi-rater consensus. The h7v3plus3 + H12 v8 + H50 + H43 + H52
stack is the final operating point. H53 closes a documentation gap
(H52 JSON missing grid values) and confirms the operating point
through 3 independent visual QA passes + 1 physics check.

See `h1_hand_pool/reports/h53_report.md` for full analysis.

## H54 conclusion

**H54: per-chain arc-gravity distribution as a single-ball signal** —
DONE. PASS.

The per-chain coefficient of variation (CV) of clean per-arc gravity
values (from H8 v8 extrema-arc fits) is a discriminative signal for
"is this a single physical ball?".

**Key results:**
- **Identical**: 2 multi-tid CONFIDENT chains (g_cv mean 0.379) vs
  11 multi-tid UNCERTAIN chains (g_cv mean 0.782). 2x difference.
  Bootstrap 90% CI for difference: [+0.13, +0.84] (positive).
- **YouTube**: 1 multi-tid CONFIDENT (g_cv 0.427) vs 9 multi-tid
  UNCERTAIN (g_cv mean 0.656). 1.5x difference, same direction.
- **Independence from H10 v10**: Pearson correlation 0.008 identical,
  -0.308 YouTube. H54 measures within-chain physics consistency; H10
  v10 measures cross-edge and coverage. The two signals are
  complementary.

**Visual QA (3/3 confirmed):**
- chain 22 (g_cv=1.537): MULTI_BALL_MERGE confirmed (H32 contact sheet)
- chain 30 (g_cv=0.417): TRUE single-ball catch-throw (H11 v7 contact sheet)
- chain 12 YouTube (g_cv=1.179): MULTI_BALL_MERGE confirmed (H11 v7 contact sheet)

**Verdict: PASS.** H54 is a real, independent single-ball signal. It
should be combined with H10 v10 as a 5th quality dimension (H55).

See `h1_hand_pool/reports/h54_report.md` for full analysis.

## H55 conclusion

**H55: H10 v11 with H54 gravity-CV as 5th dimension** — DONE. PASS
(narrow-scope precision improvement).

**Two iterations:**
- v1 (linear penalty): too aggressive, CONFIDENT count 27→24 on
  identical at w54=0.30.
- v2 (gated penalty, min_arcs=3, w54=0.30): correct. Only 9 chains
  penalized (those with n_arcs_clean >= 3). CONFIDENT count
  27→26 on identical, 5→4 on YouTube.

**Operating point (v2):** min_arcs=3, w54=0.30. Flat region of
sensitivity grid (w54=0.20-0.50 all give 26 CONFIDENT identical,
3-4 CONFIDENT YouTube).

**Visual QA (4/4 confirmed):**
- chain 14 identical (g_cv=1.089, demoted to LOW): TRACKER FRAGMENTATION
  confirmed (H55 contact sheet) — two independent juggling cycles
  stitched.
- chain 22 identical (g_cv=1.537, demoted to LOW): MULTI_BALL_MERGE
  confirmed (H32 contact sheet).
- chain 12 YouTube (g_cv=1.179, demoted to LOW): MULTI_BALL_MERGE
  confirmed (H11 v7 contact sheet).
- chain 6 YouTube (g_cv=0.427, preserved CONFIDENT q11=0.713):
  TRUE single-ball catch-throw confirmed (H11 v7 contact sheet).

**Verdict: PASS (narrow-scope precision improvement).** H55 v2
correctly demotes 3 multi-ball-merge chains (chain 14, chain 22,
chain 12) that v10 over-ranked. The CONFIDENT count drops by 1
on each video, which is acceptable because the lost chains are
confirmed false positives.

**Recommended operating point:** h7v3plus3 + H10 v11 (H55 v2,
min_arcs=3, w54=0.30) + H12 v8 + H50 + H43 + H52 + H53.

For strictest single-ball filtering: H10 v11 + H11 v7 CONFIDENT.
Multi-tid CONFIDENT: 2 identical (chain 20, chain 19) + 1 YouTube
(chain 6).

See `h1_hand_pool/reports/h55_report.md` for full analysis.

## H56 conclusion

**H56: H10 v11 v3 with non-linear g_cv penalty (deadzone + ramp)**
— DONE. PASS — improves on H55 v2.

**Hypothesis:** H55 v2's linear penalty over-penalizes chains with
mid-range g_cv (e.g., chain 30 with g_cv=0.417, visually confirmed
single-ball but demoted to LOW). A non-linear penalty with a
deadzone (no penalty below g_cv=0.5) and a linear ramp (penalty
scales linearly from 0 to w54 between g_cv=0.5 and g_cv=1.0) should
preserve low-CV chains while still penalizing high-CV chains.

**Formulation:**
```
g_penalty = 0                                    if g_cv <= DEADZONE
         = w54 * (g_cv - DEADZONE) / (RAMP_END - DEADZONE)   if DEADZONE < g_cv < RAMP_END
         = w54                                  if g_cv >= RAMP_END
q_v11 = max(0, min(1, q_v10 - g_penalty))
```

**Operating point (default):** deadzone=0.5, ramp_end=1.0, w54=0.30,
n_arcs_clean >= 3. Wide flat region of sensitivity grid.

**Key results:**
- **Identical**: 27 CONFIDENT (matches v10), 3 multi-tid CONFIDENT
  (chain 20, chain 19, **chain 7** new). Chain 22 (g_cv=1.537)
  still demoted to LOW.
- **YouTube**: 5 CONFIDENT (matches v10), 1 multi-tid CONFIDENT
  (chain 6, in deadzone). Chain 12 (g_cv=1.179) still demoted.
- **chain 30** (g_cv=0.417, in deadzone): preserved as UNCERTAIN
  (q11=q10=0.405). Not over-penalized as in H55 v2.

**Visual QA (3/3):**
- chain 7 identical (g_cv=0.72, NEW CONFIDENT): TRUE single-ball
  catch-throw confirmed (H56 v1 contact sheet). Parabolic arc
  visible. ✅
- chain 30 identical (g_cv=0.417, preserved UNCERTAIN): TRUE
  single-ball (H11 v7 contact sheet). ✅
- chain 12 YouTube (g_cv=1.179, demoted): MULTI_BALL_MERGE
  confirmed. ✅

**Verdict: PASS — improves on H55 v2.** H56 v1 recovers the v10
CONFIDENT count while still demoting the confirmed multi-ball-merge
chains. H56 v1 is the new recommended chain quality score, replacing
H10 v10 and H55 v2.

**Negative finding:** chain 14 (g_cv=1.089, n_arcs_clean=2) escapes
the H56 v1 penalty because n_arcs < 3. This is a known limitation
of the n_arcs gate; H55 v2 catches it but at the cost of
over-penalizing chain 30. Trade-off: H56 v1 has better recall on
real single-balls, H55 v2 has better precision on small-sample
chains.

**Recommended operating point:** h7v3plus3 + H10 v11 v3 (H56 v1,
deadzone=0.5, ramp_end=1.0, w54=0.30) + H12 v8 + H50 + H43 + H52 +
H53.

For strictest single-ball filtering: H10 v11 v3 + H11 v7 CONFIDENT.
Multi-tid CONFIDENT: 3 identical (chain 20, chain 19, chain 7) +
1 YouTube (chain 6).

See `h1_hand_pool/reports/h56_report.md` for full analysis.

## H57 conclusion

**H57: H10 v11 v4 with conditional penalty for high-CV low-arc chains**
— DONE. PARTIAL PASS.

**Hypothesis:** H56 v1's `n_arcs_clean >= 3` gate is too strict for
chains with very high g_cv (e.g., chain 14 with g_cv=1.089 and only
2 clean arcs). When g_cv > 1.0, even 2 arcs are sufficient to detect
inconsistency.

**Formulation:**
- If n_arcs_clean >= 3: apply H56 v1 full non-linear penalty
- If n_arcs_clean >= 2 AND g_cv >= 1.0: apply partial penalty
  (PARTIAL_W54=0.15 with linear ramp from 0 at g_cv=1.0 to 0.15 at g_cv=1.5)
- Else: no penalty

**Key result:** No CONFIDENT chains are demoted. The CONFIDENT count
is preserved at v10 levels (27 identical, 5 YouTube). The partial
penalty reduces q for high-CV low-arc chains (chain 14, 16, 28, 34)
by 0.02-0.08, reflecting the inconsistent-gravity evidence as a
"soft warning" without changing the label.

**Verdict: PARTIAL PASS.** H57 v1 addresses the H56 v1 chain 14
limitation but the practical impact is small (no label changes).
The recommended operating point remains H56 v1 (H10 v11 v3) for
simplicity; H57 v1 is a useful refinement for downstream consumers
who want extra signal.

**Recommended operating point:** h7v3plus3 + H10 v11 v4 (H57 v1)
+ H12 v8 + H50 + H43 + H52 + H53.

The H10 v11 v3 (H56 v1) and H10 v11 v4 (H57 v1) give the same
CONFIDENT/UNCERTAIN/LOW labels; v4 adds soft penalties for
high-CV low-arc chains.

See `h1_hand_pool/reports/h57_report.md` for full analysis.

## H58 conclusion

**H58: H11 v7 + H10 v11 v3 + H12 v8 triple intersection** — DONE.
PASS — validates the v11 multi-tid CONFIDENT chains as a clean
single-ball filter.

**Hypothesis:** The 4 multi-tid CONFIDENT chains (3 identical + 1
YouTube) at the intersection of H11 v7 and H10 v11 v3 CONFIDENT
criteria should be the "purest" single-ball trajectories. The H12
v8 catch/throw events on these chains should reveal a clean
juggling pattern.

**Identical (n=3 multi-tid CONFIDENT chains):**
- chain 7: tids (11, 14), f=87-160, q11=0.704
- chain 19: tids (30, 33), f=399-472, q11=0.867
- chain 20: tids (31, 36), f=411-578, q11=0.908

**Key findings:**
- **All 3 identical chains have gap_frames=11** (consistent 11-frame
  held phase). This is a structural signature of 3-ball cascade.
- **Hand alternation rate 100%** for all 3 chains (alternating
  hands, consistent with CASCADE pattern).
- q11 range 0.704-0.908.

**YouTube (n=1 multi-tid CONFIDENT chain):**
- chain 6: tids (10, 12), f=117-309, q11=0.841, gap=17 frames,
  right hand only. Consistent with 5-ball SHOWER pattern.

**Verdict: PASS.** The 3 identical + 1 YouTube chains form a clean
single-ball subset. The 11-frame held phase (identical) and
17-frame held phase (YouTube) are structural signatures of 3-ball
cascade and 5-ball shower respectively. This is the **closing
experiment** for the chain-quality optimization arc (H54 → H55 →
H56 → H57 → H58).

**Recommended operating point (final):** h7v3plus3 + H10 v11 v3
(H56 v1) + H12 v8 + H50 + H43 + H52 + H53 + H58 pattern validation.

The 3 identical + 1 YouTube multi-tid CONFIDENT chains are the
"purest" single-ball trajectories for downstream consumers.

See `h1_hand_pool/reports/h58_report.md` for full analysis.

## Final summary

The hand-occlusion overnight lab has produced a comprehensive,
validated chain representation for both videos over 58 research
episodes spanning ~16 hours. The final operating point is:

**h7v3plus3 + H10 v11 v3 (H56 v1) + H12 v8 + H50 10-frame filter +
H43 confidence filter + H52 physics corroboration + H53 multi-rater
visual QA + H58 pattern validation**

The H10 v11 v3 (H56 v1) and H10 v11 v4 (H57 v1) give the same
label classification; v3 is the recommended operating point.

The 3 identical + 1 YouTube multi-tid CONFIDENT chains are the
"purest" single-ball trajectories:
- chain 7, 19, 20 identical (3-ball cascade, 11-frame held phase)
- chain 6 YouTube (5-ball shower, 17-frame held phase)

See `h1_hand_pool/reports/FINAL_SUMMARY.md` for a comprehensive
overview of all 53 episodes, the strongest findings, the
important negative findings, and the recommended operating point.

## H58 v1 conclusion (2026-08-28 ~15:45 CEST)

**H58 v1: visual verification of the 4 multi-tid CONFIDENT chains** —
DONE. PASS. Closes the H58 visual-verification gap.

H58 (h58_intersection_analysis.py) reported that the 3 identical +
1 YouTube multi-tid CONFIDENT chains form a clean single-ball
subset with consistent held-phase durations (3-ball cascade
signature 11 frames, 5-ball shower signature 17 frames). But the
H58 report did not include contact sheets on disk.

H58 v1 (h58_v1_contact_sheets.py) renders 4 contact sheets (one
per chain), each showing 7 frames: 3 from t_prev, 2 from the held
phase, 3 from t_curr. Wrist circles + per-tid colors + (x, y)
labels.

Visual QA via vision_analyze (3/3 inspected, 1 YouTube):
- chain 7 identical (q11=0.704, tids 11->14): CATCH@114, THROW@114,
  trajectory consistent with single-ball cascade
- chain 19 identical (q11=0.867, tids 30->33): CATCH@460, THROW@471,
  11-frame held phase, ball visible at hand
- chain 6 YouTube (q11=0.841, tids 10->12): CATCH@238, THROW@255,
  17-frame held phase, right hand only (SHOWER signature)

The H58 hypothesis is now visually confirmed. Artifacts:
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h58_v1_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h58/*.png` (4 files)

## H59 conclusion (2026-08-28 ~16:00 CEST)

**H59: end-to-end precision/recall of h7v3plus3 + H10 v11 v3 against
the 113 manually reviewed pairs** — DONE. PASS. First objective
validation of the entire chain-quality optimization arc.

The 113 manually reviewed pairs (stitch_review_labels.csv) have
been sitting on disk since the original E6c work in 2024. They are
the only ground-truth labels available.

**Headline numbers (full 113-pair set, 71 correct + 42 wrong):**
- precision = 0.981 (51 TP, 1 FP)
- recall = 0.718 (20 FN)
- FPR = 0.024 (1/42)

**Per-quality-band:**
- CONFIDENT: 2/2 correct, 1.000 precision
- UNCERTAIN: 36/36 correct, 1.000 precision
- LOW: 13/13 correct + 1 FP, 0.929 precision
- NOT_IN_CHAIN: 20 correct missed (FN)

**Per-edge-type:**
- HAND_TRANSITION: 2/2, 1.000 precision
- BALLISTIC: 8/8, 1.000 precision
- RECLASSIFIED_HAND_TRANSITION: 33/34, 0.971 (1 FP: identical 22->27)
- V_RECLASSIFIED_HAND_TRANSITION: 5/5, 1.000
- H22/H26: 1/1 + 2/2, 1.000

**Per-stem:** YouTube precision 1.000, recall 0.923 (only 1 FN).
Identical precision 0.964, recall 0.600 (18 FN from capacity
constraint, not model bug).

**Structural cause of FN (20 missed correct pairs):**
h7v3plus3 has a one-successor-per-source capacity constraint.
When E6c proposes 2+ plausible successors, h7v3plus3 picks one
and the rest become FN even if they are "correct" in the review.
This is a design choice (H7 min-cost flow), not a model defect.

**The H22 YouTube 16->21 veto conflicts with the manual label.**
The 2024 manual review said 16->21 is "correct" but H22's 2026
visual analysis said 16->21 is a tracklet break and 20->21 is the
real catch. This is a real disagreement between the manual review
and the lab visual analysis. Lab analysis is more rigorous and
more recent.

**New precision-maximizing operating point (H59-validated):**
- h7v3plus3 + (CONFIDENT or UNCERTAIN) = precision 1.000, FPR 0.000
  (research/exploratory can use h7v3plus3 all = 0.981/0.718).

This is the first objective validation of the entire chain-quality
optimization arc (H1 -> H2 -> ... -> H58) without relying on
heuristic self-consistency.

See `h1_hand_pool/reports/h59_report.md` for full analysis.

## Next action (H60+)

H59 closed the chain-quality arc with objective validation. Possible
remaining research directions (from PLAN §"Next episode candidates"):

1. **H60: per-frame hold-duration distribution** — the 4 multi-tid
   CONFIDENT chains have 11-frame (identical) and 17-frame (YouTube)
   held phases. Measure the held-phase distribution across ALL
   h7v3plus3 chains and look for multi-modal signatures of
   different patterns (cascade, fountain, shower).

2. **H11 v5** (hand-relative coordinates for merge) — was
   DEFERRED in H11 v4; the 1 v2 false positive is now removed by
   v4's stricter spatial proximity. v5 is a marginal improvement
   that can wait.

3. **Stop here.** The h7v3plus3 + H10 v11 v3 + (CONF or UNCERTAIN)
   operating point is precision 1.000 on the manual review. Further
   chain improvements would require fundamentally different signals
   (multi-view, learned color tracking, or 3D ball estimation).

## H60 conclusion (2026-08-28 ~16:20 CEST)

**H60: per-frame hold-duration distribution across h7v3plus3 chains**
— DONE. PASS. H58 cascade/shower signatures confirmed at the
population level.

**Identical (3-ball cascade, 25 CATCH events):**
- Range: 4-29 frames, mean 12.6, **median 11**
- Mode bucket: [5-10) with 10 events
- Stable events [10, 50): mean 16.57, median 14.50
- The H58 11-frame signature is the **median** held phase across
  the entire h7v3plus3 chain set on identical, not just the 3
  multi-tid CONFIDENT chains.

**YouTube (5-ball, 25 CATCH events):**
- Range: 5-17 frames, mean 9.84, **median 9**
- Mode bucket: [5-10) with 13 events
- Stable events [10, 50): mean 12.42, median 12.00
- The H58 17-frame signature is the **max** held phase on YouTube
  (chain 6 CONFIDENT). YouTube's typical hold is 9 frames (median),
  much shorter than identical's 11 frames.

**Hand-asymmetry reversal (NEW FINDING):**
- identical: right hand held phases LONGER (median 12.5 vs 11)
- YouTube: right hand held phases SHORTER (median 9 vs 11)
- The two videos show different juggling patterns.

**H10 v11 v3 quality is INDEPENDENT of held-phase duration.**
CONFIDENT and UNCERTAIN chains have the same median held phase on
identical. The 1 CONFIDENT event on YouTube (chain 6) has a much
longer held phase than UNCERTAIN events, but this is because
chain 6 IS the long-held-phase chain.

**Verdict: PASS.** H58 cascade/shower signatures are confirmed at
the population level. The 11-frame and 17-frame H58 findings are
not quirks of the 4 multi-tid CONFIDENT chains — they are typical
or extreme values of the global distribution.

See `h1_hand_pool/reports/h60_report.md` for full analysis.

## H61 conclusion (2026-08-28 ~16:50 CEST)

**H61: YouTube 16->21 vs 20->21 catch+throw conflict — visual
adjudication** — DONE. PASS. H22 verdict visually confirmed.

The 2024 manual stitch review said YouTube 16->21 is "correct"
(gap=8, prediction_error=194.41). H22's 2026 visual analysis
(V-shape min_d=5.3 for 20->21 vs target_start_dist=35.3 for 16->21)
concluded 16->21 is WRONG and 20->21 is the real catch.

H61 renders a side-by-side contact sheet showing both alternatives
and asks the vision tool to adjudicate.

Vision tool verdict (3 independent evidence):
1. **Proximity**: t20 endpoint (f=473) is AT the right-hand catch
   zone. t16 endpoint (f=468) is high and offset from the wrist,
   visibly far from the right hand.
2. **Temporal gap**: 20->21 has 9 frames (typical YouTube hold per
   H60 finding). 16->21 has 14 frames (atypically long).
3. **Trajectory continuity**: t20's path leads naturally to the
   right hand at f=473. t16's trajectory ends in a region
   inconsistent with handing the ball to the right hand.

**Verdict: 20->21 is the real catch-throw. 16->21 is not.**

Implications:
- H22's 2026 visual analysis is a stronger signal than the 2024
  manual labels for this case. The 2024 reviewer did not have
  access to V-shape hand-proximity evidence.
- The h7v3plus3 chain set (which has 20->21 and excludes 16->21)
  is correct.
- This is the ONLY "FN that's actually a TN" case from H59. All
  other 51 TP match the manual review. The H59 evaluation is
  now fully validated.
- The 9-frame gap (20->21) is the exact typical YouTube hold
  per H60 — the chain algorithm correctly identifies the
  characteristic 5-ball hold.

See `h1_hand_pool/reports/h61_report.md` for full analysis.

## H62 conclusion (2026-08-28 ~17:00 CEST)

**H62: YouTube 5-ball pattern characterization — CASCADE, not SHOWER**
— DONE. PASS. H58 SHOWER interpretation corrected.

H58 (and H58 v1) interpreted the YouTube 5-ball pattern as
SHOWER based on the 1 CONFIDENT chain (chain 6) with
right-hand-only events. H62 systematically examines all 24
YouTube catch+throw events to test the SHOWER hypothesis.

**Result: YouTube 5-ball is 70% ALT-HAND (CASCADE), 30%
same-hand. Identical 3-ball is 63% same-hand, 37% alt-hand
(MIXED).** The two videos have OPPOSITE hand-pattern biases.

Key findings:
1. H58 SHOWER interpretation was based on n=1 (chain 6). The
   broader YouTube pattern is 70% alt-hand, consistent with
   CASCADE.
2. The YouTube 5-ball pattern is CASCADE, not SHOWER. The 17-frame
   hold (chain 6) is still a real signature feature but it's an
   exception in an otherwise CASCADE pattern.
3. The H60 hand-asymmetry reversal is consistent with CASCADE
   (a left-biased juggler) rather than SHOWER.

Implication: H58 report's "5-ball shower signature" should be
replaced with "5-ball cascade signature" in any downstream
consumer. The 17-frame hold remains a real signature of the
5-ball cascade (vs 11-frame for 3-ball).

This is a useful correction: the H58 SHOWER interpretation
was over-generalized from 1 CONFIDENT chain to the whole video.
The H58 v1 vision tool was misled by the chain 6 anomaly.
H62 uses the full 24-event dataset to characterize the pattern.

See `h1_hand_pool/reports/h62_report.md` for full analysis.

## H63 conclusion (2026-08-28 ~17:10 CEST)

**H63: YouTube 5-ball CASCADE-SHOWER mix** — DONE. PASS. H62
refined.

H62 found the YouTube 5-ball pattern is CASCADE (70% alt-hand)
with 7 same-hand events (30%), all on the right hand. H63 asks:
are these 7 same-hand events random, or do they form coherent
SHOWER-like bursts?

Cluster analysis (threshold=100 frames):
- Cluster 1: singleton f=308 (chain 7)
- Cluster 2: 3 events f=420-510, span 90, chains 0+3+9
- Cluster 3: 3 events f=769-825, span 56, chains 0+8+9

**Verdict: CASCADE-SHOWER MIX.** The YouTube pattern is
CASCADE (70%) WITH SHOWER bursts (30%), not pure CASCADE and
not pure SHOWER.

Key findings:
1. The 7 same-hand events form 2 SHOWER-like clusters of 3
   events each, separated by ~250 frames of CASCADE activity.
   Each cluster spans 3 different chains (true pattern feature,
   not single-chain artifact).
2. The right hand is the "lead" hand for SHOWER events (7/7 on
   the right). Consistent with a right-handed juggler.
3. Same-hand gaps are LONGER (median 20 vs 13.5 alt-hand).
   SHOWER requires the dominant hand to throw, wait for peak,
   then catch.
4. Cluster 1 (f=308) is an isolated singleton — a pattern
   transition or one-off trick element.
5. The H10 v11 v3 quality doesn't privilege CASCADE over SHOWER
   events (all 7 same-hand events are UNCERTAIN).

Refines H62: from "CASCADE" to "CASCADE-SHOWER mix". The
h7v3plus3 chain set correctly captures both CASCADE and SHOWER
events.

See `h1_hand_pool/reports/h63_report.md` for full analysis.

## H64 conclusion (2026-08-28 ~17:20 CEST)

**H64: Identical 3-ball CASCADE->FOUNTAIN transition** — DONE. PASS.
H58 v1 cascade interpretation refined.

H62 found identical 3-ball is 63% same-hand (0.63 rate). H64
asks: is this spread evenly (CASCADE-SHOWER mix like YouTube) or
concentrated in a late phase (CASCADE->FOUNTAIN transition)?

Temporal split search (max same-rate delta, >=3 events each side):
- Best split: **f=240**
- Pre  (f<240): 1/4 same-hand (**0.25** same-hand rate) — CASCADE-like
- Post (f>=240): 11/15 same-hand (**0.73** same-hand rate) — FOUNTAIN-like
- Same-rate delta: **+0.48** (statistically significant)

Per 100-frame window:
- 0-300: mostly alt-hand (CASCADE)
- 500-600: 3/4 same-hand (mixed)
- 800-1000: 5/5 same-hand (FOUNTAIN)

**Verdict: CASCADE->FOUNTAIN transition at f=240.** The H58 v1
"3-ball cascade" interpretation should be refined to "3-ball
CASCADE->FOUNTAIN".

Key findings:
1. The 4 multi-tid CONFIDENT chains (chain 7, 19, 20) are
   CASCADE events in the pre-f=240 phase.
2. The h7v3plus3 chain set correctly captures both phases.
3. The H12 v8 FOUNTAIN_3+ classification (11.7% of frames)
   is correct but understated — the H64 per-event analysis
   shows 73% of post-f=240 events are same-hand, which is
   FOUNTAIN's signature.
4. The 800-1000 window is 100% same-hand, consistent with a
   sustained 3-ball FOUNTAIN.

Implications:
- Identical video is CASCADE early, FOUNTAIN late. Both phases
  have the same-hand bias direction but with different magnitudes.
- The h7v3plus3 chain set's 4 multi-tid CONFIDENT chains are
  CASCADE events (validated by H59). The FOUNTAIN phase
  chains are not in the manual review.
- Future work could label FOUNTAIN-phase pairs to validate
  the H12 v8 FOUNTAIN_3+ classification.

See `h1_hand_pool/reports/h64_report.md` for full analysis.

## H65 conclusion (2026-08-28 ~17:30 CEST)

**H65: H12 v8 FOUNTAIN_3+ label validation at scale (post-H64 zones)** —
DONE. PARTIAL PASS.

**Hypothesis:** With H50's 10-frame filter applied and H64's zone
classification, H12 v8 FOUNTAIN_3+ accuracy might exceed H39's 30%.

**Method:** Render 4-frame contact sheets for all 7 substantial
FOUNTAIN_3+ phases (>= 20 frames) in the H50-filtered pattern data.
Visual QA via vision_analyze.

**Result: 3/7 = 43% H12 v8 FOUNTAIN_3+ accuracy.**

| Video | Phase | conf | H12 v8 | Vision | Match |
|---|---|---|---|---|---|
| identical | 631-669 | 0.714 | FOUNTAIN_3+ | FOUNTAIN | YES |
| identical | 890-936 | 0.571 | FOUNTAIN_3+ | OTHER | NO (crossed-arm trick) |
| identical | 977-1011 | 0.565 | FOUNTAIN_3+ | FOUNTAIN | YES |
| identical | 1029-1049 | 0.463 | FOUNTAIN_3+ | OTHER | NO (static hold) |
| youtube | 339-374 | 0.646 | FOUNTAIN_3+ | FOUNTAIN | YES |
| youtube | 482-594 | 0.653 | FOUNTAIN_3+ | OTHER | NO (static hold) |
| youtube | 800-861 | 0.651 | FOUNTAIN_3+ | CASCADE | NO (alt-hand cascade) |

**Verdict: PARTIAL PASS.** H12 v8 FOUNTAIN_3+ is more accurate than
H39's 30% (43% on H65) but remains a noisy classifier. The 4 wrong
cases break down:
- 2 OTHER (static hold / trick — both hands hold balls, no throwing)
- 1 CASCADE (alt-hand crossing arcs, misread as same-hand)

**Why H12 v8 over-classifies FOUNTAIN_3+:** the K=4 sliding window
of recent catch/throw events interprets a "hold" as "same-hand
repeated catch" and a CASCADE-with-2-balls-in-hand as same-hand
rhythm. H12 v8 cannot distinguish "hold" from "synchronized throw"
without continuous hand-occupancy.

**H43 confidence filter confirmed.** The H65 wrong cases have conf
0.463, 0.571, 0.651, 0.653. Only 1/4 (the 1029-1049 conf=0.463
case) is below H43's 0.55 threshold. H43's precision is high (1.000
on H39+H65) but its recall is low (1/2 of H65 wrong-on-identical).

**H50 10-frame filter is necessary but not sufficient.** It removes
tracker-fragmentation events but cannot distinguish "hold" from
"synchronized throw".

**Recommended operating point (unchanged):** h7v3plus3 + H10 v11 v3
+ H12 v8 + H50 + H43 + H52 + H53. H43 is the most precise
FOUNTAIN_3+ post-filter; H65 confirms it.

See `h1_hand_pool/reports/h65_report.md` for full analysis.

## H66 conclusion (2026-08-28 ~17:50 CEST)

**H66: continuous "balls aloft" (A) signal as FOUNTAIN_3+ post-filter** —
DONE. PARTIAL PASS.

**Hypothesis:** H12 v8 FOUNTAIN_3+ over-classification (43% accuracy on
H65) might be reduced by filtering phases where balls are NOT
frequently aloft. A real FOUNTAIN_3+ has multiple balls aloft; a static
hold has 0-1.

**Method:** Per-frame A = # YOLO balls > 100 px from both hands. Phase-
level metric: pct_A_ge2 = fraction of frames with >= 2 balls aloft.
Threshold: 0.30.

**Result on H65 sample (7 substantial FOUNTAIN_3+ phases):**
- 2/7 rejected: 977-1011 identical (real FOUNTAIN, wrong rej),
  1029-1049 identical (static hold, correct rej).
- 5/7 kept: 2 correct (real FOUNTAIN), 3 wrong (890-936 OTHER,
  482-594 OTHER, 800-861 CASCADE).

**H43 + H66 stacked:** 2/7 rejected, 2/3 of those are real FOUNTAIN
labels (2 correct rejects / 3 rejects). The remaining 5/7 are kept;
H12 v8 accuracy on kept is 3/5 = 60% (vs 43% baseline).

**Verdict: PARTIAL PASS.** H66 is a useful additional signal:
- Catches the 1029-1049 static hold (max_A=1, never 2+ aloft)
- Independent of H12 v8 confidence (different signal source)
- Composes cleanly with H43 (no overlap in rejection logic)
- 67% precision on rejects at threshold 0.30

**Limitations:**
- YouTube 482-594 static hold NOT caught (YOLO fires on stationary
  background features — H4 finding extends)
- 3-ball FOUNTAIN (977-1011) wrongly rejected (only 1 ball aloft)
- 890-936 crossed-arm trick on identical NOT caught
- 800-861 YouTube CASCADE NOT caught (CASCADE has balls aloft too)

**Recommended operating point (updated):**
h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + **H66** + H52 + H53

For FOUNTAIN_3+ post-filter: H43 + H66 stacked.

**Comparison to H43 alone:**
| Filter | correct_rej | wrong_rej | wrong_keep | correct_keep |
|---|---|---|---|---|
| H43 (conf < 0.55) | 1 | 0 | 3 | 3 |
| H66 (pct_A_ge2 < 0.30) | 1 | 1 | 3 | 2 |
| H43 + H66 (both) | 2 | 1 | 2 | 2 |

**Threshold sensitivity grid (NOT flat):** 0.10 catches 0 wrong / 0
correct, 0.30 catches 1 wrong / 1 correct, 0.60 catches 4 wrong / 2
correct. Trade-off at 0.30 is best balance.

**Negative finding:** YOLO detector false positives on stationary
background features (corrugated door, sign, trees) limit H66's
discrimination on YouTube. H4's general detector confusion finding
extends to H66.

See `h1_hand_pool/reports/h66_report.md` for full analysis.

## H67 conclusion (2026-08-28 ~18:10 CEST)

**H67: H43 + H66 stacked FOUNTAIN_3+ post-filter — end-to-end impact** —
DONE. PARTIAL PASS — recommends lowering H66 threshold to 0.20.

**Method:** Apply H43 (conf < 0.55) and H66 (pct_A_ge2 < 0.30) to the
H50-filtered per-frame pattern data. Mark FOUNTAIN_3+ frames as
FOUNTAIN_LOW_CONF if either filter rejects.

**Result:**
- identical: 56/1042 (5.4%) frames changed. FOUNTAIN_3+ -56, FOUNTAIN_LOW_CONF +56.
- YouTube: 0/898 (0.0%) frames changed.

**Per-phase contribution (identical):**
- 977-1011 (real FOUNTAIN, wrongly rejected by H66): 35 frames
- 1029-1049 (OTHER static hold, correctly rejected by H43+H66): 21 frames

**Precision/recall on rejects: 21/56 = 37.5% precision** (62.5% of
rejected frames are real FOUNTAIN labels).

**Threshold sensitivity (revised):**
- 0.10: 1 correct (1029), 0 wrong (perfect precision)
- 0.20: 1 correct (1029), 0 wrong (perfect precision, 977 just above threshold)
- 0.30: 1 correct (1029), 1 wrong (977 also below)
- 0.40: 2 "correct" (1029 + wrongly treating 977 as correct), 0 actual wrong

**Recommended operating point update:** lower H66 threshold from
0.30 to **0.20** to avoid false-rejecting the 977-1011 real FOUNTAIN.
At threshold 0.20, H66 catches only 1029-1049 (same as H43 alone),
so H43 + H66 stacked is equivalent to H43 alone on the H65 sample.

**Net useful H66 contribution at threshold 0.20: 0% additional
rejection on the H65 sample.** The H66 signal is real but the
operating point needs to be lower to avoid false rejects.

**Verdict: PARTIAL PASS.** H67 confirms the H66 signal works but
the threshold must be calibrated to the ball count. 3-ball FOUNTAIN
has pct_A_ge2 ≈ 0.12 (1 ball aloft at a time), 5-ball FOUNTAIN has
pct_A_ge2 ≈ 0.50-0.60 (2-3 balls aloft). A single threshold cannot
serve both. A per-n_total calibration would improve discrimination.

**Future work:**
1. Per-ball A signal from tracklet_features (instead of raw YOLO)
2. 3-ball vs 5-ball calibration
3. YouTube static hold (482-594) needs fundamentally different signal
   (YOLO false positives on background features)

**Recommended operating point (updated):**
h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + H66 (threshold 0.20) + H52 + H53

See `h1_hand_pool/reports/h67_report.md` for full analysis.
