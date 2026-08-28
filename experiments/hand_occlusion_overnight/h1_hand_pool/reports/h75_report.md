# H75 — H43 + H69 + H74 stacked FOUNTAIN_3+ post-filter

**Date:** 2026-08-28
**Question:** Does the H43 + H69 + H74 stacked filter improve precision
on FOUNTAIN_3+ post-filtering compared to H43 + H69 alone?

## Background

H43 (conf < 0.55) and H69 (spec_conc < 0.15) form the recommended
FOUNTAIN_3+ post-filter from H69. H74 (LR_variance < 0.20) is a new
signal that catches static-hold-like misclassifications that H43+H69
miss.

Hypothesis: The H43 + H69 + H74 stack should catch all 4 misclassified
FOUNTAIN_3+ phases on the H65 sample while preserving all 3 real
FOUNTAIN phases. H74 adds value on the CASCADE_3+ side too (catches
1/2 misclassified phases via static-hold detection).

## Method

For each substantial FOUNTAIN_3+ / CASCADE_3+ phase in both videos,
compute three filter decisions:
- H43: conf < 0.55
- H69: spec_conc < 0.15
- H74: LR_variance < 0.20

Stack: REJECT if ANY filter rejects.

H75 v1: per-phase evaluation against H65/H72/H73 ground truth.
H75 v2: per-frame end-to-end impact on the H50-filtered pattern data.

## Results (H75 v1, per-phase)

| Phase | Stem | Pattern | conf | spec_conc | lr_var | H43 | H69 | H74 | Stacked | gt | correct |
|-------|------|---------|------|-----------|--------|-----|-----|-----|---------|-----|---------|
| f=631-669 | identical | FOUNTAIN_3+ | 0.714 | 0.411 | 0.621 | . | . | . | KEEP | REAL_FOUNTAIN | OK |
| f=890-936 | identical | FOUNTAIN_3+ | 0.571 | 0.308 | 0.586 | . | . | . | KEEP | OTHER | WRONG |
| f=977-1011 | identical | FOUNTAIN_3+ | 0.565 | 0.326 | 0.296 | . | . | . | KEEP | REAL_FOUNTAIN | OK |
| f=1029-1049 | identical | FOUNTAIN_3+ | 0.463 | 0.361 | 0.374 | X | . | . | REJECT | OTHER | OK |
| f=339-374 | YouTube | FOUNTAIN_3+ | 0.646 | 0.164 | 0.218 | . | . | . | KEEP | REAL_FOUNTAIN | OK |
| f=482-594 | YouTube | FOUNTAIN_3+ | 0.653 | 0.140 | 0.135 | . | X | X | REJECT | OTHER | OK |
| f=800-861 | YouTube | FOUNTAIN_3+ | 0.651 | 0.088 | 0.202 | . | X | . | REJECT | OTHER | OK |
| f=685-716 | identical | CASCADE_3+ | 0.738 | 0.498 | 0.386 | . | . | . | KEEP | MANIPULATION | WRONG |
| f=733-766 | identical | CASCADE_3+ | 0.738 | 0.498 | 0.157 | . | . | X | REJECT | STATIC_HOLD | OK |

**Stack performance (FOUNTAIN_3+ only):**
- 3/3 real FOUNTAIN kept (recall 100%)
- 3/4 misclassified FOUNTAIN_3+ caught (precision 75%)

**Stack performance (CASCADE_3+ only, 2 phases):**
- 0/0 real CASCADE_3+ in dataset (recall unmeasurable)
- 1/2 misclassified CASCADE_3+ caught (precision 50%)

**Comparison with H43 + H69 (no H74):**
- Same FOUNTAIN_3+ results (3/3 kept, 3/4 caught)
- H74 does NOT add value on the FOUNTAIN_3+ sample
- H74 DOES add value on the CASCADE_3+ sample (catches f=733-766)

## Results (H75 v2, per-frame end-to-end)

| Video | FOUNTAIN_3+ total frames | H43 reject | H43+H69 reject | H43+H69+H74 reject |
|-------|--------------------------|------------|----------------|---------------------|
| identical | 168 | 21 (12.5%) | 21 (12.5%) | 26 (15.5%) |
| YouTube | 211 | 0 (0.0%) | 175 (82.9%) | 175 (82.9%) |

- **identical**: H75 stack rejects 5 more frames than H43+H69. These
  are 4 short FOUNTAIN_3+ phases (1-2 frames each, transient
  misclassifications between the substantial FOUNTAIN phases). H74
  catches them via LR_variance=0.0 (single frame = no variance).
- **YouTube**: H75 stack rejects the same 175 frames as H43+H69
  (H74 adds nothing because H69 already catches f=482-594 and f=800-861).

## Key findings

### 1. H75 stack is equivalent to H43 + H69 on FOUNTAIN_3+

On the H65 sample, the H75 stacked filter produces the same decisions
as H43 + H69 alone. H74 is a redundant filter on FOUNTAIN_3+ — it
catches f=482-594 (var=0.135), but H69 already catches it via
spec_conc=0.140. No new FOUNTAIN_3+ catches on the H65 sample.

### 2. H74 adds value on the CASCADE_3+ side

The H75 stack catches 1/2 CASCADE_3+ misclassifications (f=733-766
STATIC_HOLD) via H74. The H43 + H69 stack catches neither. H74 is
the only signal that detects static-hold CASCADE_3+ misclassifications.

### 3. H74 catches transient 1-frame FOUNTAIN_3+ labels (side effect)

On identical, H74 rejects 4 short FOUNTAIN_3+ phases (1-2 frames each)
that are transient misclassifications between the substantial FOUNTAIN
phases. The variance=0.0 for single-frame phases triggers H74. This
is a useful side effect (catches noise) but not a deliberate design.

### 4. H74 threshold sensitivity (flat region 0.15-0.20)

| thr | real_kept | mis_rejected (of 6) | notes |
|-----|-----------|----------------------|-------|
| 0.0 | 3/3 | 0 | no-op |
| 0.15 | 3/3 | 1 (STATIC_HOLD) | catches f=733-766 only |
| **0.20** | **3/3** | **2 (STATIC_HOLD + f=482-594)** | **optimal** |
| 0.25 | 2/3 | 3 | drops f=977-1011 (real FOUNTAIN) |
| 0.30 | 1/3 | 3 | drops 2 real FOUNTAIN |

Threshold 0.20 is the optimal operating point: catches 2/6 misclassified
(33%) while preserving 3/3 real FOUNTAIN (100% recall).

## Implications

### Recommended operating point (post-H75)

For FOUNTAIN_3+ post-filter (updated):
- **(H43 OR H69 OR H74) where H74 = LR_variance < 0.20**
- Equivalent to H43 + H69 for FOUNTAIN_3+ on H65 sample
- Adds CASCADE_3+ static-hold detection (1/2 misclassifications)

For CASCADE_3+ post-filter (updated):
- H74 is the only signal that catches static-hold misclassifications
- 0/2 accuracy is still the limit (H74 catches 1/2 static-hold, but
  the other 1/2 manipulation-trick is not caught)

For MIXED_3+ post-filter (unchanged from H71):
- KEEP at spec_conc >= 0.15 (91% precision)
- REJECT at spec_conc < 0.10 (1/1 correct on H71)

### H43 + H69 + H74 stack adds robustness

Even though H74 doesn't add new FOUNTAIN_3+ catches on the H65 sample,
it's a useful safety net:
- If H69 spec_conc is noisy on a new video, H74 would catch
  static-hold misclassifications
- If H43 conf is unreliable, H74 would still catch them
- H74 is the only signal that catches CASCADE_3+ static-hold

The H75 stack is the new recommended operating point.

## Negative findings

1. **H74 does not add new FOUNTAIN_3+ catches on H65 sample.** The
   H43 + H69 stack already catches all H74 catches on FOUNTAIN_3+.
2. **MANIPULATION_TRICK (f=685-716) is not caught by any of the 3
   filters.** Its conf (0.738) and spec_conc (0.498) are high; its
   LR_variance (0.386) is in the real-FOUNTAIN range. The trick
   has actual ball motion that fools all 3 filters.
3. **f=890-936 (crossed-arm trick) is not caught.** conf (0.571),
   spec_conc (0.308), var (0.586) — all in the real-FOUNTAIN range.
   A fundamentally different signal is needed.
4. **H74 threshold 0.20 is in a narrow flat region (0.15-0.20).**
   Above 0.20, real FOUNTAIN starts being rejected. Below 0.15, H74
   is too permissive.

## Future research directions

1. **H76: CASCADE_3+ as research signal** — accept that CASCADE_3+
   cannot be reliably detected, recommend downstream consumers use
   only FOUNTAIN_3+ and MIXED_3+ filters.

2. **H77: re-run H59 precision/recall on FULL H70 sample with
   ground truth** — characterize end-to-end quality of the
   h7v3plus3 + H10 v11 v3 + H12 v8 + H50 + H70/H71/H75 v1 stack.

3. **H78: novel signals for MANIPULATION_TRICK / crossed-arm trick
   detection.** The H43 + H69 + H74 stack cannot catch f=685-716
   (manipulation) or f=890-936 (crossed-arm). A learned model or
   hand-trajectory smoothness check might help.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h75_stacked_fountain_filter.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h75v2_per_frame_impact.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h75_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h75v2_summary.json`
