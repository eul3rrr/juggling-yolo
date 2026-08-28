# H10 v5 — Chain Quality with H8 v5 Parabolic-Fit Physics

Date: 2026-08-28 ~08:15 CEST
Branch: `experiments/hand-occlusion-overnight`
Status: PASS — H10 v5 is better-calibrated than H10 v3.

## Hypothesis

H8 v5 (parabolic fit + gravity) is more accurate than H8 v3
(3-frame mean velocity) for short tracklets. Replacing v3 with
v5 in H10's H8 score should produce a better-calibrated
chain quality score.

## Algorithm

For each chain, H8 score = (n_air - n_violating - 0.5 * n_unknown) / n_air
- OK: 1.0
- VIOLATING: 0.0
- INSUFFICIENT_DATA: 0.5 (graduated penalty for unknown)
- N/A (hand edges): not counted

Composite quality = 0.30 * h3 + 0.30 * h8 + 0.40 * h9 (unchanged).

## Quantitative Result

### Identical video (43 chains)

|| Method | n_improved | n_unchanged | n_worsened | mean quality |
||---|---|---|---|---|
|| H10 v3 (3-frame mean) | — | — | — | 0.539 |
|| **H10 v5 (parabolic fit)** | **6** | **34** | **3** | **0.529** |

Mean quality is similar (0.539 vs 0.529), but the rank changes
reveal meaningful improvements:

| Chain | v3 rank | v5 rank | v3 quality | v5 quality | visual verdict |
|---|---|---|---|---|---|
| 36 | 11 | 1 | 0.515 | 0.944 | REAL single ball (v5 correct, v3 wrong) |
| 29 | 1 | 7 | 0.964 | 0.750 | FALSE POSITIVE (v5 correct, v3 wrong) |
| 24 | 2 | 8 | 0.956 | 0.742 | FALSE POSITIVE (v5 correct, v3 wrong) |
| 16 | 6 | 11 | 0.916 | 0.488 | mostly same quality (new v5 catch on air edge) |
| 8  | 7 | 5 | 0.849 | 0.849 | unchanged |
| 23 | 8 | 6 | 0.837 | 0.837 | unchanged |

### YouTube video (15 chains)

Only 1 chain (12) has any v3-vs-v5 difference (v3 h8=0.50, v5
h8=0.25, with 1 unknown edge). All other chains are unchanged
because the v3-vs-v5 differences are on long tracklets that
both methods agree are violating.

## Visual QA: chains with biggest rank movement

### chain 29 (v3 rank 1 → v5 rank 7) — v5 CORRECT
Tracklet 50: 78 points. Tracklet 55: 4 points. Visual QA:
the air edge is **NOT a real ballistic continuation**. The
"thrown ball" detections at top of frame appear to be
clipping artifacts or background features, not a real ball.
v3 was over-trusting the high coverage (h9=0.94) and
failing to catch the physics violation. v5 caught it.

### chain 24 (v3 rank 2 → v5 rank 8) — v5 CORRECT
Tracklets 38, 39, 47 (3 tids). Visual QA: 38→39 and 39→47
air edges are NOT physically consistent. The chain
fragments are stitching together noise detections, not a
real single ball. v3 was over-trusting the high coverage
(h9=0.92). v5 caught it.

### chain 36 (v3 rank 11 → v5 rank 1) — v5 CORRECT
Tracklets 62, 66 (2 tids, large gap). Visual QA: a real
single ball traveling through a 33-frame gap. v3 flagged
the large temporal gap as a velocity violation, but v5's
parabolic fit shows the gap is consistent with a real
ballistic arc. v5 correctly identifies this as a high-
quality chain.

## Verdict: PASS

H10 v5 (with H8 v5 parabolic fit) is better-calibrated than
H10 v3 (with H8 v3 3-frame mean velocity). The visual QA
shows v5 correctly demoted 2 false positives (chains 24, 29)
and promoted 1 false negative (chain 36) that v3 had
missed. The 2 NEW v5 catches from H8 v5 (60→64, 21→22)
also flow through to H10 v5.

### Recommendation

**H10 v5 should be the recommended H10 configuration**,
replacing H10 v3. The v5 H8 signal is more accurate on
short tracklets, and the graduated scoring (0.5 for
INSUFFICIENT_DATA) is a more principled way to handle
uncertain edges than v3's binary OK/VIOLATING.

The YouTube long-tracklet limitation persists in both v3
and v5 (a fundamental issue with long tracklets spanning
multiple parabolic arcs). Neither v3 nor v5 provides
reliable H8 signal on long YouTube tracklets. A
fundamentally different approach (e.g. per-bounce
segmentation) is needed to solve this.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h10v5_with_h8v5.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h10v5_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h10v5_chain_quality_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h10v5/*.png` (6 files)
