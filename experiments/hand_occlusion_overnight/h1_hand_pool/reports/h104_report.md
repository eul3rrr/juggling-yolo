# H104 — H12 v9 continuous-density pattern classifier

**Date:** 2026-08-29 (continuation episode)
**Status:** NEGATIVE — the time-density guard does not fix H12 v8 over-classification.

## Hypothesis (from H103)

H12 v8's K=4 sliding window over-classifies H93 STATIC_HOLD /
OTHER_CROSSED_ARM phases as active patterns (FOUNTAIN_3+ /
CASCADE_3+) because it treats sparse hand-handoff events the same
as dense active juggling. A real cascade has 4+ events in 30-60
frames; a static hold with hand-handoffs has 4 events spread
over 100+ frames. The K=4 window sees both as "n=4 events" but
the time density is very different.

H104 (H12 v9) adds a TIME-DENSITY check:
- For each frame, compute `time_span = max(event_frame) - min(event_frame)`
  in the K=4 events_window.
- If `time_span > TIME_SPAN_MAX`, the events are too sparse for a
  non-UNCONFIRMED classification.
- Default operating point: `TIME_SPAN_MAX = 80` frames.

## Method

`h104_h12_v9_time_density.py` re-implements H12 v8's K=4 logic
with the time-density guard, evaluates on H93 corrected GT (21
phases), and sweeps TIME_SPAN_THR ∈ {40, 50, 60, 70, 80, 90, 100,
120, 150, 200, 300, 500}.

## Quantitative result

**H12 v8 baseline (no guard):** 17 TP / 1 TN / 3 FP / 0 FN,
P=0.850, R=1.000, acc=0.857 on 21 H93 phases.

The 3 H12 v8 over-classifications:
- f=685-716 identical (STATIC_HOLD, contact-juggling pose)
  → CASCADE_3+ (H12 v8 conf 0.738)
- f=890-936 identical (OTHER_CROSSED_ARM, Mills Mess)
  → FOUNTAIN_3+ (H12 v8 conf 0.571)
- f=482-594 YouTube (STATIC_HOLD with embedded hand-handoffs)
  → FOUNTAIN_3+ (H12 v8 conf 0.615)

**Sensitivity grid (H104 v1 with TIME_SPAN_THR guard):**

| thr  | TP | TN | FP | FN | P     | R     | acc   |
|------|---:|---:|---:|---:|-------|-------|-------|
| 40   | 11 |  2 |  2 |  6 | 0.846 | 0.647 | 0.619 |
| 50   | 14 |  1 |  3 |  3 | 0.824 | 0.824 | 0.714 |
| 60   | 16 |  1 |  3 |  1 | 0.842 | 0.941 | 0.810 |
| 70   | 17 |  1 |  3 |  0 | 0.850 | 1.000 | 0.857 |
| 80   | 17 |  1 |  3 |  0 | 0.850 | 1.000 | 0.857 |
| 90+  | 17 |  1 |  3 |  0 | 0.850 | 1.000 | 0.857 |

The TIME_SPAN_THR guard has a flat region (70+) that is **identical
to the H12 v8 baseline**. The guard is essentially a no-op at the
default threshold. The only "catchable" over-classification is the
f=2-71 YouTube STATIC_HOLD which is already correctly classified as
MIXED_3+_UNCONFIRMED by H12 v8.

**Per-phase max time_span analysis (K=4 events window):**

| Phase | Verdict | Pred | max_span | avg_conf | n_with_max_win |
|-------|---------|------|---------:|---------:|---------------:|
| 685-716 id | STATIC_HOLD   | CASCADE_3+ | **15** | 0.738 | 32/32 |
| 890-936 id | OTHER_CROSSED | FOUNTAIN_3+| **34** | 0.571 | 47/47 |
| 482-594 yt | STATIC_HOLD   | FOUNTAIN_3+| 100     | 0.615 | 113/113 |

The 2 identical FP cases have **dense** K=4 events (max_span 15-34),
so a time-density guard cannot catch them. Only f=482-594 YouTube
has a sparse K=4 window (max_span 100), and even at thr=80, the
H12 v9 classifier still calls it FOUNTAIN_3+ (because the H12 v8
per-frame logic is dominated by hand-alternation metrics, not by
the time-span guard alone).

## Why H104 v1 doesn't work — the deeper analysis

The 3 H12 v8 over-classified phases have very different K=4
event density patterns:

1. **f=685-716 (identical STATIC_HOLD):** 1 chain event in-phase
   (chain 24, hand=?). The K=4 events_window pulls in 4 events
   from chain 24's broader context (t39→t47 hand-edge and
   surrounding chain events). These events are densely packed
   (max_span 15) but the phase itself is a contact-juggling
   pose with body rolls.

2. **f=890-936 (identical OTHER_CROSSED_ARM):** 1 chain event
   in-phase (chain 30, hand=right). The K=4 events_window pulls
   in events from chain 30's prior context. max_span 34.

3. **f=482-594 (YouTube STATIC_HOLD):** 5 chain events in-phase
   across 3 chains (0, 7, 9), all RIGHT hand. The H12 v8
   K=4 window sees 4+ right-hand events in succession and
   classifies as FOUNTAIN_3+ (which is the signature of same-hand
   repeat catches in the K=4 logic). max_span 100.

The H12 v8 over-classification is **not** a time-density
problem. It's a K=4+hand-alternation-metric problem. The K=4
events_window draws from a wider temporal context than the
phase itself.

## H104 v2 (in-phase event count) — also NEGATIVE

I also tested counting events strictly in [phase_start, phase_end]
and using a "n events in [f-W, f]" window for various W. Result:

| Phase | Verdict | avg_e30 | avg_e60 | avg_e15 |
|-------|---------|--------:|--------:|--------:|
| 685-716 id | STATIC_HOLD   | 2.94 | 4.22 | 1.06 |
| 890-936 id | OTHER_CROSSED | 0.96 | 3.38 | 0.34 |
| 482-594 yt | STATIC_HOLD   | 1.12 | 2.19 | 0.59 |
| 631-669 id | JUGGLING      | 1.36 | 2.85 | 0.59 |
| 339-374 yt | JUGGLING      | 1.39 | 3.42 | 0.56 |
| 733-766 id | JUGGLING      | 0.03 | 0.74 | 0.03 |

The JUGGLING and STATIC_HOLD phases have **overlapping** event
densities. avg_e60 (events in [f-60, f]):
- JUGGLING f=631-669 identical: 2.85
- STATIC_HOLD f=685-716 identical: 4.22 (HIGHER than the juggling phase)
- JUGGLING f=733-766 identical: 0.74 (very low — pred CASCADE_3+)

No single threshold on event density can separate the two classes.
The H12 v8 K=4 events_window is fundamentally confounded by the
fact that the underlying H7 chain-event log is **too sparse** to
characterize juggling patterns on its own (H45/H47 confirmed this).

## What would actually work (negative → positive follow-up)

The H12 v8 over-classification problem is **structural**: H12 v8
classifies frames based on the K=4 events_window alone, but the
K=4 events are too noisy/sparse to be a reliable phase-level
discriminator. The H96 v2 stack (H40v2 + H74v4 + H78 + H87+max_aloft
+ H90 NEW + H100 v4 guards) works because it **combines** the
H12 v8 pattern labels with auxiliary signals (hand-occupancy,
wrist distance, aloft ball distribution, YOLO conf).

H104 v3 (future work) would attempt to integrate the H40v2
hand-occupancy signal directly into the H12 v9 frame-level
classifier, e.g.:

```
if h40v2_LR_variance > 0.20 OR h40v2_unique_LR > 1:
    demote FOUNTAIN_3+ to MIXED_3+_UNCONFIRMED
```

This would be a H12 v9 hybrid that uses auxiliary signals at
the per-frame level, not as a post-filter. Such an integration
might catch the 2 identical FP cases (which have low LR_variance
due to H40v2 saturation) but the saturation problem is exactly
the H74v2 → H74v4 issue (H93 found H40v2 LR_variance < 0.20 is
not reliable for 3-ball patterns).

## Verdict: NEGATIVE

H104 v1 (time-density guard) and H104 v2 (in-phase event count)
both fail to fix H12 v8's over-classification problem. The K=4
events_window is fundamentally confounded: dense K=4 events do
not imply active juggling, and sparse K=4 events do not imply
static hold.

**Recommended operating point (unchanged from H96 v2):**
h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H43 + H69 + H74v4 +
H78 + H87+max_aloft + H90 NEW + H100 v4 (conf+spec_conc) +
H52 + H53 + H71 (MIXED_3+).

The H12 v8 K=4 pattern classifier alone is a hopeless starting
point; it must be combined with auxiliary signals via the H96 v2
stack. The H104 negative result documents that no per-frame
"events_window" reformulation can fix the over-classification.

## Recommended follow-up

The H104 negative result redirects effort to:

1. **H105: H12 v9 hybrid with H40v2 occupancy** — try integrating
   the H40v2 hand-occupancy signal directly into the H12 v9
   per-frame classifier. Hypothesis: a phase with high
   `LR_variance > 0.20` or `unique_LR > 1` should be demoted
   to MIXED_3+_UNCONFIRMED unless H87 max_aloft is high (real
   juggling has more aloft balls than H40v2-occupied).

2. **H106: H12 v8 "all" output as a confidence feature** — use
   the H12 v8 pattern label not as a hard class but as a soft
   feature in a downstream logistic regression. Treat the H12 v8
   conf and pattern as inputs to a learned classifier, not as
   the classifier.

3. **Stop here on H104.** The H96 v2 stack is the precision-
   optimized endpoint, and H104 confirms the H12 v8 K=4 logic
   alone is not improvable.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h104_h12_v9_time_density.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h104_per_phase.csv` (21 rows)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h104_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_v9_*.csv` (2 files)
