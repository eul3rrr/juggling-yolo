# H39 — FOUNTAIN_3+ post-filter via H36 hand-occupancy

## Hypothesis

H37 found that CASCADE_3+ frames have hand-occupancy support from H36
(20/22 identical CASCADE_3+ are H36 state (0, 1, 2)). H38 used this
to implement a strict post-filter that rejects CASCADE_3+ frames
where H36 has no hand-occupancy (state (0, 0, total)).

**H39 hypothesis:** the symmetric question — does FOUNTAIN_3+ have
hand-occupancy support? If H12 v8 calls a frame FOUNTAIN_3+ but H36
has no hand-occupancy, the FOUNTAIN_3+ classification may be a
misclassification.

## Quantitative result

### H39 v1 (frame-level: reject FOUNTAIN_3+ where H36 (L, R) = (0, 0))

| Video | FOUNTAIN_3+ before | FOUNTAIN_3+ rejected | FOUNTAIN_3+ after | Phases (>=5f) before / after |
|---|---|---|---|---|
| identical | 288 | 283 (98.3%) | 5 | 10 / 0 |
| YouTube | 110 | 94 (85.5%) | 16 | 3 / 2 |

The rejection rate is huge (~85-98%). All 10 identical FOUNTAIN
phases are eliminated; only 2 small fragments remain on YouTube.

### H39 v2 (phase-level: reject FOUNTAIN_3+ phases with zero H36 events)

| Video | FOUNTAIN_3+ before | FOUNTAIN_3+ rejected | FOUNTAIN_3+ after | Phases rejected / kept |
|---|---|---|---|---|
| identical | 288 | 74 | 214 | 2 / 8 (74 frames / 204 frames) |
| YouTube | 110 | 0 | 110 | 0 / 3 |

Phase-level rejection is much more conservative: only 2 phases
rejected (f=411-449, f=977-1011) on identical, 0 on YouTube.

## Visual QA

10 FOUNTAIN_3+ phases (n>=10) inspected via `vision_analyze` with
structured verdicts. Each contact sheet shows 6 evenly-spaced frames
spanning the phase.

| Phase | Video | n | Vision verdict | Hand-occ visible? | H39v1 | H39v2 |
|---|---|---|---|---|---|---|
| f=243-252 | identical | 10 | **FOUNTAIN** | YES (both) | KEPT | KEPT |
| f=263-312 | identical | 50 | MIXED | YES (left) | REJECT | KEPT |
| f=411-449 | identical | 39 | MIXED | YES (left) | REJECT | REJECT |
| f=631-669 | identical | 39 | **FOUNTAIN** | YES (left) | REJECT | KEPT |
| f=685-716 | identical | 32 | **FOUNTAIN** | YES (both, R=high) | REJECT | KEPT |
| f=733-766 | identical | 34 | QA_PENDING | (vision error) | REJECT | KEPT |
| f=860-871 | identical | 12 | MIXED (crossed-arms) | YES (both) | REJECT | KEPT |
| f=977-1011 | identical | 35 | OTHER (hold trick) | YES (both) | REJECT | REJECT |
| f=1029-1050 | identical | 22 | OTHER (2-ball exercise) | YES (right) | REJECT | KEPT |
| f=339-374 | YouTube | 36 | **CASCADE** | YES (right) | REJECT | KEPT |
| f=800-861 | YouTube | 62 | MIXED | YES (both) | PARTIAL | KEPT |

### H12 v8 FOUNTAIN_3+ accuracy on visual QA (n=10)

- **3/10 correct FOUNTAIN** (30%)
- 4/10 MIXED (40%)
- 1/10 CASCADE (10%)
- 2/10 OTHER — hold trick + 2-ball exercise (20%)

This is a real finding: **H12 v8 over-classifies FOUNTAIN_3+ by
~70%**. Many "FOUNTAIN_3+" phases are actually MIXED, CASCADE, or
hold tricks.

### H39 v1 (frame-level) precision on visual QA

- 2/10 correctly rejected (the 2 OTHER phases)
- 6/10 over-rejected (real FOUNTAIN/MIXED/CASCADE with hand-occupancy)
- 1/10 partial-rejected
- 1/10 not rejected
- **Precision: 20% (2/10)**

### H39 v2 (phase-level) precision on visual QA

- 1/2 correctly rejected (f=977-1011 hold trick)
- 1/2 over-rejected (f=411-449 real MIXED)
- 8/10 not rejected (1 correct FOUNTAIN, 7 real)
- **Precision: 50% (1/2)**

## Key findings

1. **H12 v8 FOUNTAIN_3+ classification is unreliable.** Only 30%
   of FOUNTAIN_3+ phases are visually FOUNTAIN. The remaining 70%
   are MIXED, CASCADE, or OTHER (hold trick, 2-ball exercise).
   This is consistent with H12 v6b's reported limitation:
   FOUNTAIN_3+ is based on event-log density, not visual pattern.

2. **H36 (L, R, A) state is too sparse to validate FOUNTAIN_3+.**
   H36 only marks hand-occupancy at chain events, but most
   FOUNTAIN_3+ phases span intervals between chain events. H36
   reports (0, 0, total) HOLD state during these intervals even
   when the juggler's hands ARE occupied (just not at chain
   events). This is a structural limitation, not a bug.

3. **H39 v1 (frame-level) over-rejects 60% of real juggling.**
   6/10 visually-confirmed real FOUNTAIN/MIXED/CASCADE phases
   are rejected because H36 reports no hand-occupancy during the
   phase. H39 v1 precision 20% is too low to be useful.

4. **H39 v2 (phase-level) precision 50% is also low.** The
   phase-level criterion is more conservative but still misses
   the real issue: H36 chain events don't correlate with
   continuous hand-occupancy. The 2 H39v2-rejected phases are
   the worst visual misclassifications (hold trick + MIXED with
   no chain events at boundary), but the 8 KEPT phases include
   a real CASCADE (f=339-374 YouTube) that H12 v8 misclassified.

5. **H39 is a NEGATIVE result for H12 v8 FOUNTAIN_3+
   post-filtering using H36 alone.** A reliable filter would
   require a continuous hand-occupancy signal, which H36 doesn't
   provide.

## Implication for the chain set

The H12 v8 FOUNTAIN_3+ classification is event-log-driven, not
hand-occupancy-driven. The h7v3plus3 chain set is mostly
multi-ball merges (per H32) and the K=4 sliding window of events
in H12 v8 produces FOUNTAIN_3+ classifications whenever the
last 4 events are all same-hand — which happens often because
the chain set has many right-hand events (H32 reported YouTube
right-hand bias).

The correct fix for H12 v8 FOUNTAIN_3+ would be:
- Use a continuous per-frame hand-occupancy signal (not chain-driven)
- Or integrate detector-level ball position signals (H12 v4/v5 direction)
- Or relax the FOUNTAIN_3+ confidence when K=4 events don't
  include a HAND_OCCUPIED state

None of these are implemented in H39. H39 is a documented
negative result.

## Negative findings

1. **H12 v8 FOUNTAIN_3+ classification is fundamentally
   unreliable** on these videos. ~70% of FOUNTAIN_3+ phases
   are visually NOT FOUNTAIN. The H12 v8 K=4 sliding window
   of chain events over-classifies FOUNTAIN_3+.

2. **H36 chain-driven state is too sparse to validate
   FOUNTAIN_3+.** H36 only emits state changes at chain
   events. Continuous hand-occupancy is invisible to H36.
   This is a known limitation of H36's design (it walks
   the chain set, not raw detector positions).

3. **H39 v1 over-rejects 60% of real juggling** because H36
   doesn't see the hand-occupancy during chain-event gaps.
   H39 v2 is more conservative but still 50% precision on
   the small QA sample.

4. **The h7v3plus3 chain set's FOUNTAIN_3+ classifications
   should be considered suspect** for downstream pattern
   analysis. H38's CASCADE_3+ post-filter is more reliable
   because CASCADE_3+ HAS hand-occupancy (per H37); FOUNTAIN_3+
   doesn't have a corresponding positive signal.

## Verdict

**NEGATIVE.** H39 v1 (frame-level) over-rejects 80% of
real juggling activity. H39 v2 (phase-level) is more
conservative but only 50% precise on visual QA. The
underlying finding — that H12 v8 FOUNTAIN_3+ is ~70%
inaccurate — is real and important, but H36 is not a
reliable validator of FOUNTAIN_3+ because it only marks
chain-driven state changes.

**Recommended:** do NOT use H39 v1 or v2 as a downstream
filter. The H12 v8 FOUNTAIN_3+ classification is best
left as-is with the caveat that it has ~70% error rate.
A better fix would be a continuous hand-occupancy signal,
which H36 doesn't provide.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h39_fountain_post_filter.py` (v1, frame-level)
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h39v2_phase_filter.py` (v2, phase-level)
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h39_contact_sheets.py` (contact sheets)
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h39_visual_qa.py` (verdicts)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h39_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h39v2_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h39_contact_sheets.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h39_visual_qa_verdicts.csv`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h39_filtered_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h39v2_filtered_*.csv` (2)
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h39/*.png` (11)
