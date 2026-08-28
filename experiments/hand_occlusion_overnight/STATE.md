# Hand Occlusion Overnight Lab — State

LAST_UPDATE: 2026-08-28 12:50 CEST
STATUS: H30 + H31 + H32 + H33 + **H34** COMPLETE. **H32 NEGATIVE**: per-chain
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
