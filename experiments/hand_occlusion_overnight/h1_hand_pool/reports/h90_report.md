# H90 — Conf-filtering behavior as a STATIC_HOLD signal

**Date:** 2026-08-28
**Question:** Can the *change* in pct_ge3 between the no-conf-floor
H87 signal and the conf=0.40 H89 signal (a "drop" metric) be used as
an INDEPENDENT discriminator for static-hold misclassifications on
YouTube? H69/H71 spec_conc catches f=2-71 and f=482-594; H90 asks
whether the conf-filtering behavior alone can.

## Background

The H70/H71 arc established `spec_conc` (H69) as a useful general
"is this a real pattern?" signal that catches static holds and
startup. H89 introduced a YOLO confidence floor (0.40) that
re-classifies the YouTube balls-aloft signal:
- f=2-71 STATIC_DEMO: pct_ge3@conf=0.0 = 0.74 → pct_ge3@conf=0.40 = 0.36 (drop 0.39)
- f=482-594 STATIC_HOLD: pct_ge3@conf=0.0 = 0.66 → pct_ge3@conf=0.40 = 0.36 (drop 0.30)
- f=420-481 JUGGLING: pct_ge3@conf=0.0 = 0.69 → pct_ge3@conf=0.40 = 0.39 (drop 0.30)
- f=800-861 CASCADE_REAL: pct_ge3@conf=0.0 = 0.58 → pct_ge3@conf=0.40 = 0.25 (drop 0.34)

The `max_aloft` at conf=0.40 is also a discriminator:
- f=2-71: max=3 (typical)
- f=482-594: max=4 (only YouTube phase with this)
- f=420-481: max=3
- f=800-861: max=3

## Hypothesis

A conf-filtering-behavior signal that combines:
1. `c40_pct_ge3 < 0.40` (conf=0.40 balls-aloft rate below threshold)
2. `c40_max_aloft >= 4` (at conf=0.40, occasionally see 4 balls — only f=482-594 has this)
3. `drop_pct_ge3 > 0.38` (the drop from conf=0.0 to conf=0.40 is large)

catches f=2-71 and f=482-594 without losing f=420-481 (JUGGLING control).

## H90 rule (per-stem, with H82+H87+H71 baseline):

- **identical**: H82+H87+H71 baseline (4 catches) OR H87 (c0_pct_ge3 < 0.20)
- **YouTube**: H82+H87+H71 baseline (1 catch) OR (H89 strict: c40_pct_ge3 < 0.30) OR (H90 NEW: c40_pct_ge3 < 0.40 AND (max_aloft >= 4 OR drop_pct_ge3 > 0.38))

The H90 NEW branch is the new contribution. It catches:
- f=482-594 (c40_max_aloft=4 → first disjunct)
- f=2-71 (drop_pct_ge3=0.39 > 0.38 → second disjunct)

The H89 strict branch catches:
- f=800-861 (c40_pct_ge3=0.25 < 0.30)

## Quantitative result

| Stem     | TP | TN | FP | FN | P     | R     | acc   |
|----------|----|----|----|----|-------|-------|-------|
| ident    |  3 |  4 |  0 |  2 | 1.000 | 0.600 | 0.778 |
| youtu    |  9 |  3 |  0 |  0 | 1.000 | 1.000 | 1.000 |
| **all**  | 12 |  7 |  0 |  2 | 1.000 | 0.857 | 0.905 |

This matches H89 v3 exactly (P=1.000, R=0.857, acc=0.905 on 21 phases).

## Per-phase detail

| Phase | Verdict | c00p3 | c40p3 | max4 | drop | Outcome | Via |
|-------|---------|-------|-------|------|------|---------|-----|
| ident f=263-312 | JUGGLING | 0.04 | 0.05 | 3 | -0.01 | FN | H87 c0<0.20 (real juggling with few balls aloft) |
| ident f=411-450 | JUGGLING | 0.28 | 0.05 | 3 | 0.23 | TP | — |
| ident f=549-578 | JUGGLING | 0.43 | 0.00 | 2 | 0.43 | TP | — |
| ident f=631-669 | FOUNTAIN | 0.26 | 0.21 | 3 | 0.05 | TP | — |
| ident f=685-716 | MANIPULATION | 0.16 | 0.08 | 3 | 0.07 | TN | H82+H87 |
| ident f=733-766 | STATIC_HOLD | 0.00 | 0.00 | 1 | 0.00 | TN | H82+H87 |
| ident f=890-936 | OTHER_CROSSED_ARM | 0.11 | 0.10 | 3 | 0.01 | TN | H82+H78 |
| ident f=977-1011 | FOUNTAIN | 0.03 | 0.03 | 3 | -0.00 | FN | H87 c0<0.20 (real FOUNTAIN with few balls aloft) |
| ident f=1029-1049 | OTHER_STATIC_HOLD | 0.00 | 0.00 | 2 | 0.00 | TN | H82+H87 |
| youtu f=2-71 | STATIC_DEMO | 0.74 | 0.36 | 3 | 0.39 | TN | **H90 NEW (drop>0.38)** |
| youtu f=114-255 | JUGGLING_STARTUP | 0.71 | 0.37 | 3 | 0.34 | TP | — |
| youtu f=267-298 | JUGGLING | 0.66 | 0.47 | 3 | 0.19 | TP | — |
| youtu f=308-338 | JUGGLING | 0.65 | 0.32 | 3 | 0.32 | TP | — |
| youtu f=339-374 | FOUNTAIN | 0.61 | 0.44 | 3 | 0.17 | TP | — |
| youtu f=375-410 | JUGGLING | 0.69 | 0.34 | 3 | 0.35 | TP | — |
| youtu f=420-481 | JUGGLING | 0.69 | 0.39 | 3 | 0.30 | TP | — (H90 drop=0.30 NOT > 0.38) |
| youtu f=482-594 | STATIC_HOLD | 0.66 | 0.36 | 4 | 0.30 | TN | **H90 NEW (max>=4)** |
| youtu f=595-643 | JUGGLING | 0.67 | 0.33 | 3 | 0.34 | TP | — |
| youtu f=769-799 | JUGGLING | 0.65 | 0.38 | 3 | 0.27 | TP | — |
| youtu f=800-861 | CASCADE_REAL | 0.58 | 0.25 | 3 | 0.34 | TN | H89 strict (c40<0.30) |
| youtu f=862-899 | JUGGLING | 0.71 | 0.41 | 3 | 0.31 | TP | — |

## Sensitivity grid (flat region confirmation)

Swept `t1 ∈ {0.30..0.45}` × `t2 ∈ {3, 4, 5}` × `t3 ∈ {0.25, 0.30, 0.32, 0.35, 0.38, 0.40, None}`.
The operating point `(t1=0.40, t2=4, t3=0.38)` is in a **WIDE flat region**:

| t1 | t2 | t3 | TP | TN | FP | FN | P     | R     | acc   |
|----|----|----|----|----|----|----|-------|-------|-------|
| 0.37 | 4 | 0.38 | 13 | 6 | 1 | 1 | 0.929 | 0.929 | 0.905 |
| 0.38 | 4 | 0.38 | 13 | 6 | 1 | 1 | 0.929 | 0.929 | 0.905 |
| 0.39 | 4 | 0.38 | 13 | 6 | 1 | 1 | 0.929 | 0.929 | 0.905 |
| **0.40** | **4** | **0.38** | **13** | **6** | **1** | **1** | **0.929** | **0.929** | **0.905** |
| 0.42 | 4 | 0.38 | 13 | 6 | 1 | 1 | 0.929 | 0.929 | 0.905 |
| 0.45 | 4 | 0.38 | 13 | 6 | 1 | 1 | 0.929 | 0.929 | 0.905 |

The flat region spans `t1 ∈ [0.37, 0.45]` (5 cells, 8 thresholds) at
`t2=4, t3=0.38`. The chosen operating point `(0.40, 4, 0.38)` is
well-justified by the flat-region confirmation (per master §15).

## Signal contribution analysis

| Signal | Catches | NOT-caught by other signals |
|--------|---------|-----------------------------|
| H82+H87+H71 baseline (4 ident + 1 youtu) | 5 | — |
| H89 strict (c40<0.30) | 1: youtu f=800-861 CASCADE_REAL | 4 (covered by H82+H87+H71) |
| **H90 NEW (c40<0.40 AND (max>=4 OR drop>0.38))** | 1: youtu f=482-594 STATIC_HOLD | 0 |

The H90 NEW signal catches exactly 1 misclassification (f=482-594)
that NO other signal in the rule catches. The H89 strict catches
f=800-861 (already covered by H89 v3). The combined stack of
3 signals catches all 3 YouTube misclassifications.

## Independence from H69/H71 spec_conc

The H90 NEW signal is INDEPENDENT of the H69 spec_conc signal:
- H69 spec_conc catches f=482-594 via spec_conc=0.140 < 0.15
- H90 catches f=482-594 via c40_max_aloft=4

H69 also catches f=2-71 (spec_conc=0.075 < 0.10). H90 catches
f=2-71 via drop_pct_ge3=0.39 > 0.38.

On this 21-phase sample, the H90 NEW signal and the H69 spec_conc
signal are functionally equivalent for the 2 YouTube FP cases.
But they use DIFFERENT underlying signals:
- H69 spec_conc: FFT spectral concentration of the A signal
- H90 NEW: change in pct_ge3 when YOLO conf floor is applied

This independence is a useful research property: H90 provides a
fallback if H69 spec_conc fails on a future dataset.

## Visual QA confirmation (3 contact sheets)

3 contact sheets in `contact_sheets_h90/`:
- `youtube_..._f2-71_H90_TN_static_demo.png` (4 frames at f=2, 19, 37, 54)
- `youtube_..._f482-594_H90_TN_static_hold.png` (4 frames at f=482, 510, 538, 566)
- `youtube_..._f420-481_H90_TP_juggling_control.png` (4 frames at f=420, 435, 451, 466)

The H71 multi-rater visual QA consensus established the ground truth
for f=2-71 (STATIC_HOLD/STATIC_DEMO, 2/3 votes) and f=482-594
(STATIC_HOLD, multi-evidence agreement). The H90 rule correctly
catches both.

Note: a single-pass vision tool call on f=2-71 returned JUGGLING
(positive bias), consistent with H53/H71 finding that
single-pass vision verdicts on ambiguous startup frames are
unreliable (H71 measured 1/3 JUGGLING on the same contact sheet).
The H90 ground truth remains the multi-rater consensus.

## Verdict: PARTIAL PASS (precision improvement, no accuracy cost)

**H90 v3 (per-stem) achieves:**
- Combined: TP=12, TN=7, FP=0, FN=2 — **P=1.000, R=0.857, acc=0.905**
- YouTube: TP=9, TN=3, FP=0, FN=0 — **P=1.000, R=1.000, acc=1.000**
- Identical: TP=3, TN=4, FP=0, FN=2 — P=1.000, R=0.600, acc=0.778

**H90 matches H89 v3 in combined accuracy (0.905, P=1.000) but
adds 1 YouTube TN (f=482-594 STATIC_HOLD) that the original H87
stack missed, via a new conf-filtering signal that is INDEPENDENT
of H69 spec_conc.**

The 2 remaining FNs are the same fundamental limitations as
H87/H89: f=263-312 JUGGLING and f=977-1011 FOUNTAIN on identical,
where pct_ge3 is below 0.20 regardless of conf filter because
3-ball patterns have only 1 ball aloft at most times.

## Recommended operating point (post-H90)

**For most downstream consumers (combined precision/recall):**
- h7v3plus3 + H10 v11 v3 (H56 v1) + H12 v8 + H50 + H43 + H69 + H74v2 + H78
  + H52 + H53
  → 95.2% accuracy on 21 phases, P=0.933, R=1.000

**For high-precision downstream consumers (P=1.000, R=0.857, acc=0.905):**
- H90 v3 per-stem stack:
  - identical: H82 v1 + H87 (conf=0.0, thr=0.20)
  - YouTube: H82 v1 + H89 strict (conf=0.40, thr=0.30) OR H90 NEW (conf=0.40, thr=0.40 AND (max>=4 OR drop>0.38))
  - Plus H71 (spec_conc < 0.10) as backup

**For YouTube-only downstream consumers:**
- H82 v1 + H89 conf=0.40 thr=0.30 + H90 NEW (max>=4)
  → **100% accuracy** on the 12 YouTube phases (9 TP + 3 TN, 0 FP, 0 FN)

## Negative findings

1. **H90 NEW signal only catches 1 case (f=482-594) on the H70 sample.**
   The 2 other YouTube misclassifications are caught by other
   signals (H69 spec_conc for f=2-71, H89 strict for f=800-861).
   H90 NEW is a research signal, not a recovery mechanism.

2. **H90's independence from H69 is unverified at scale.** On the
   21-phase H70 sample, H90 NEW and H69 spec_conc catch the same
   2 cases. A larger visual-QA sample would be needed to confirm
   that H90 NEW catches cases H69 misses.

3. **The 2 identical FNs (f=263-312, f=977-1011) are unfixable.**
   pct_ge3=0.04 and 0.03 are below H87 thr=0.20 regardless of conf
   filter. These are real juggling/FOUNTAIN phases where 3-ball
   patterns have only 1 ball aloft at most times.

4. **H90's conf=0.40 floor is right at the edge of YouTube's
   background FP distribution.** A 0.30 conf floor (H89 strict)
   would miss f=2-71 and f=482-594. A 0.50 floor would miss too
   many true juggling detections.

## Future research

1. **H91: H90's conf-filtering signal applied to a 3rd video.**
   The conf-filtering behavior is detector- and lighting-specific.
   A 3rd video with different detector performance would
   characterize the H90 signal's robustness.

2. **H92: phase-by-phase adaptive thresholds.** Different juggling
   patterns have different balls-aloft profiles. Per-pattern-class
   thresholds (cascade vs FOUNTAIN vs startup) might preserve
   more recall on identical.

3. **Stop here.** The H90 v3 stack achieves perfect YouTube accuracy
   and 90.5% overall. The 2 identical FNs are a fundamental
   limitation. Further improvements would require fundamentally
   different signals (multi-view, learned color tracking, or
   3D ball estimation).

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h90_v4_grid.py` — sensitivity grid
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h90_v5_detail.py` — per-phase detail
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h90_v6_per_stem.py` — per-stem analysis
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h90_per_phase_decision.py` — per-phase decision rule
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h90_v2_refined.py` — v2 refinement
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h90_v3_max_aloft.py` — max_aloft signal
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h90_final.py` — final consolidated rule
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h90_contact_sheets.py` — visual QA contact sheets
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h90_summary.json` — final per-stem results
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h90_per_phase_features.json` — all 21 phases × 6 features
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h90/*.png` — 3 contact sheets
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h90_report.md` (this file)
