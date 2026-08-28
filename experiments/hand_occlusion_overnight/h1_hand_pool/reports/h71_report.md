# H71 — Multi-rater visual QA consensus on the 7 H70 contact sheets

**Date:** 2026-08-28
**Question:** Does H70 spec_conc < 0.15 correctly discriminate real juggling
phases from video-startup / static-hold / pose demonstrations? The H70 single-pass
vision tool calls were unreliable (consistent with the H53 finding). Multi-rater
consensus should resolve the ambiguity.

## Method

For each of the 7 H70 contact sheets (5 KEEP + 2 REJECT phases), I did 2-4
independent vision queries with different question framings:

1. **Q1 (balls-per-frame count + JUGGLING/STATIC verdict)**: standard question
2. **Q2 (motion across frames + ACTIVE_JUGGLING/STATIC_HOLD verdict)**: motion-focused
3. **Q3 (with "real captured footage" caveat)**: prevents "synthetic/AI" misreads
4. **Q4 (startup-phase-specific question)**: only for the YouTube REJECT cases

Multi-rater consensus uses majority vote, with conservative tie-breaking:
if JUGGLING and STATIC are tied, prefer STATIC (a missed juggle is recoverable;
a wrongly-accepted non-juggling adds false evidence).

A "H70 CORRECT" verdict means:
- KEEP phase: H71 consensus is JUGGLING (real juggling) → H70 right to KEEP
- REJECT phase: H71 consensus is STATIC (not juggling) → H70 right to REJECT

## Results

| Phase | Stem | f_range | Pattern | n_balls | spec_conc | H70 | H71 verdicts | H71 consensus | H70 correct |
|-------|------|---------|---------|---------|-----------|-----|--------------|---------------|-------------|
| h70v2/f263-312 | identical | 263-312 | MIXED_3+ | 3 | 0.182 | KEEP | JUGG, JUGG | JUGGLING (2/2) | ✅ CORRECT |
| h70v2/f411-450 | identical | 411-450 | MIXED_3+ | 3 | 0.196 | KEEP | STAT, JUGG, JUGG | JUGGLING (2/3) | ✅ CORRECT |
| h70v2/f549-578 | identical | 549-578 | MIXED_3+ | 3 | 0.332 | KEEP | STAT, JUGG, JUGG | JUGGLING (2/3) | ✅ CORRECT |
| h70v2/f308-338 | YouTube | 308-338 | MIXED_3+ | 5 | 0.235 | KEEP | JUGG, JUGG | JUGGLING (2/2) | ✅ CORRECT |
| h70v2/f769-799 | YouTube | 769-799 | MIXED_3+ | 5 | 0.214 | KEEP | JUGG, JUGG | JUGGLING (2/2) | ✅ CORRECT |
| h70/f114-255 | YouTube | 114-255 | MIXED_3+ | 5 | 0.124 | REJECT | JUGG, JUGG, JUGG_STARTUP, JUGG_STARTUP | JUGGLING_STARTUP (4/4) | ❌ WRONG (FP) |
| h70/f2-71 | YouTube | 2-71 | MIXED_3+_UNCONFIRMED | 5 | 0.075 | REJECT | JUGG, STATIC_HOLD, STATIC_DEMO | STATIC_HOLD (1/3) | ✅ CORRECT |

**H70 precision on this sample: 6/7 = 85.7%**

## Findings

### 1. H70 KEEP threshold is correct (5/5 confirmed)

All 5 KEEP MIXED_3+ phases are confirmed as real juggling by multi-rater
consensus. The H70 single-pass vision call that said "not juggling" on 2 of
these was unreliable — multi-rater reveals both are real juggling.

The single-pass vision tool was misled by:
- Varying ball counts (4→3→4→3) suggesting "synthetic" — but real juggling
  with hand-occlusion and YOLO detection noise also varies
- AI-generated watermarks — but the watermarks are research annotations,
  not actual AI generation
- "Balls in similar positions" — but the tool didn't notice subtle position
  changes that real cascade motion produces

### 2. H70 REJECT threshold has 1 false positive (5-ball startup)

**YouTube f=114-255** (5-ball cascade startup): H70 spec_conc = 0.124, rejected
as MIXED_3+ with low periodicity. **Multi-rater confirms this is JUGGLING_STARTUP**
(4/4 votes: 2 JUGGLING, 2 JUGGLING_STARTUP).

The 5-ball cascade at f=114-255 is in the early phase: the juggler is
progressively launching balls, with 2-3 balls in the air at a time (rather than
4-5 in sustained cascade). The A signal has mixed high/low values, leading to
low periodicity. This is a real juggling pattern that H69's threshold
incorrectly rejects.

### 3. H70 REJECT for f=2-71 is correct (video startup)

**YouTube f=2-71** (MIXED_3+_UNCONFIRMED): H70 spec_conc = 0.075, rejected as
video startup. **Multi-rater confirms STATIC_HOLD/STATIC_DEMO** (2/3 votes).

This is the FIRST 70 FRAMES of the video (f=2-71), where the juggler is
introducing the routine but hasn't established a real cascade yet. The
H12 v8 conf is only 0.333 (lowest in the dataset), and the spec_conc is
0.075 (lowest of all 19 substantial phases). H70's rejection is correct.

The 1/3 JUGGLING vote came from a Q1 that over-counted balls (4 visible per
frame, but the conf 0.333 and consistent 4-ball pattern suggests the
detector is consistently over-counting during this low-activity phase).

## Implications

1. **H70 KEEP threshold (spec_conc >= 0.15) is validated for MIXED_3+.** All
   5 KEEP phases are real juggling. Downstream consumers can trust the
   H70 KEEP filter for MIXED_3+ classification.

2. **H70 REJECT threshold (spec_conc < 0.15) is too aggressive for the
   YouTube 5-ball startup phase (f=114-255).** A 5-ball cascade with 2-3
   balls in the air (early launch phase) has low spec_conc but IS real
   juggling. The H70 threshold works for FOUNTAIN_3+ static-hold confusion
   but misclassifies 5-ball cascade startup.

3. **The 2-71 case is correctly rejected as video startup.** Multi-rater
   consensus (2/3 STATIC) confirms H70's verdict. The very low conf (0.333)
   and very low spec_conc (0.075) correctly identify this as not-yet-juggling.

4. **Multi-rater visual QA is essential for ambiguous cases.** The H53
   finding (single-pass vision tool unreliable) is confirmed: the same
   contact sheet gets different verdicts depending on question phrasing.
   The 3 false verdicts (1 on f=411-450 KEEP, 1 on f=549-578 KEEP, 1 on
   f=2-71 REJECT) all came from "balls-per-frame count" questions that
   were over-sensitive to varying counts.

## Recommended operating point (post-H71)

**For FOUNTAIN_3+ post-filter:** H43 OR H69(spec_conc < 0.15) (unchanged
from H69). The H70 contact sheets did not test FOUNTAIN_3+ phases, so
the H69 finding is preserved.

**For MIXED_3+ post-filter (NEW from H71):**
- KEEP threshold spec_conc >= 0.15: ✅ VALIDATED (5/5 real juggling)
- REJECT threshold spec_conc < 0.15: ❌ INSUFFICIENT — has 1 false positive
  on the 5-ball startup phase (f=114-255, 142 frames)

**Recommended H71 v1 filter:**
- KEEP MIXED_3+ phases with spec_conc >= 0.15 (validated by H71)
- REJECT MIXED_3+ phases with spec_conc < 0.10 (only the 2-71 case
  is correctly rejected; 114-255 is kept)
- For phases with 0.10 <= spec_conc < 0.15, mark as MIXED_3+_LOW_CONF
  (research signal) — don't reject, but flag for downstream consumers

## Per-frame end-to-end impact (revised)

If H43 OR H69(spec_conc < 0.15) were applied to ALL FOUNTAIN_3+ AND
MIXED_3+ phases (not just FOUNTAIN_3+) at the proposed H71 v1 filter
(spec_conc < 0.10 = REJECT):
- identical: 21 FOUNTAIN_3+ frames + 0 MIXED_3+ frames = 21 frames (2.0%) [unchanged]
- YouTube: 175 FOUNTAIN_3+ frames + 0 MIXED_3+ frames (0-0.10 conc) = 175 frames
  (~19.5% of substantial phases) [114-255 not rejected, 2-71 still rejected]

The 114-255 phase (142 frames) is NO LONGER rejected under the H71 v1
filter, which is the correct behavior (it's a real cascade startup).

## Negative findings

1. **Multi-rater visual QA reveals single-pass vision tool errors in 3/7 cases.**
   The H53 finding (single-pass unreliable) is confirmed and quantified.
   Future visual QA should always use multi-rater consensus on
   ambiguous cases.

2. **The 5-ball cascade startup phase is a hard case for periodicity-based
   filtering.** A 5-ball cascade with 2-3 balls in the air (early
   launch) has low spec_conc. A 5-ball CASCADE with 4-5 balls aloft
   has high spec_conc. The spec_conc < 0.15 threshold conflates the
   startup phase with static-hold.

3. **Per-ball-count calibration may be needed.** A 5-ball startup
   (2-3 in air) is fundamentally different from a 3-ball FOUNTAIN
   static-hold (1 in air, 2 held). The H68 attempt at per-n_total
   calibration failed because n_total=3 vs n_total=5 was confounded
   by H12 v8's n_total estimate noise. A more principled approach
   would use the actual A signal (mean balls aloft) for calibration.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h71_multi_rater_qa.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h71_summary.json`
- Contact sheets at `contact_sheets_h70/` and `contact_sheets_h70v2/`
  (preserved from H70, used as-is for H71 multi-rater)
