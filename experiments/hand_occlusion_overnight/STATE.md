# Hand Occlusion Overnight Lab — State

LAST_UPDATE: 2026-08-28 18:05 CEST
STATUS: H7v2 + H10 v8 + H12 v7 + H237 v6 + H11 v6 + H13 v1 + H13 v2 + H14 v1 + **H15 v1 + v2** + **H10 v9** COMPLETE. Pipeline advanced. **H15 v2 PASS (with YouTube caveat)**: pure V-shape reclassification of h7v2-kept BALLISTIC edges recovers 4 hidden catch-throws on identical (23→25, 30→33, 39→47, 51→52) and admits 1 YouTube FP (27→28). H15 v1's combined V-shape + velocity-jump was mis-calibrated (rejected 23→25 which has jump=23.4 px/frame; admitted 27→28 which has jump=14.5). v2 abandons the velocity-jump check. **H10 v9 (h10v9_with_h15v2.py) is the new recommended chain quality score**, excluding V_RECLASSIFIED from h3-eligible set (fixes a pre-existing h3=None redistribution bug). Mean quality: identical 0.814 → 0.828 (+0.014), YouTube 0.679 → 0.685 (+0.007). Concentrated on chain 13 and chain 30 (each +0.30). Combined h7v2 + h15v2 = h7v3-pure chains.

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

None. H14 v1 (PASS) committed in this episode.

## Next action

H15 v2 (pass) committed in the most recent episode. H10 v9 is the new
recommended chain quality score, replacing H10 v8. The combined
h7v3pure chain construction (h7v2 + h15v2) is the new recommended
chain pipeline. STATE/PLAN/RESULTS_LOG updated to reflect this.

A natural follow-up is **H11 v7: re-run identity propagation on
h7v3pure chains**. H11 v6 was a big win for YouTube (1 → 48 catch/
throw events, 24x). H11 v7 should pick up the 4 new V_RECLASSIFIED
identical catch-throws as additional identity events, and propagate
the h7v3pure chain structure to downstream consumers.

Other directions:
1. **H16: smarter filter for YouTube 27→28 false positive** —
   parabolic-fit check on the gap trajectory, or look at
   H8 v8's per-arc gravity to see if a V-shape with high
   gravity anomaly can be flagged.
2. **H17: V-shape recovery for v4d-missed links** — apply V-shape
   to pairs of tracklets that v4d rejected (e.g. 35→40) and
   check if any are V-shape hidden catch-throws.
3. **H18: H12 v8 — re-run pattern inference on h7v3pure chains
   with H10 v9 quality.** Similar to v7 but with the new
   chain quality score.
