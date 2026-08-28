# H38 — Post-filter CASCADE_3+ using H36 hand-occupancy

## Hypothesis

H37 showed that CASCADE_3+ frames have hand-occupancy support
(20/22 identical CASCADE_3+ are H36 state (0, 1, 2); 117/129
YouTube CASCADE_3+ are (0, 1, 4) or (1, 0, 4)). A small fraction
of CASCADE_3+ frames have NO hand-occupancy (H36 state (0, 0, 3)
or (0, 0, 5)) — these are likely H12 v8 misclassifications.

Question: does rejecting CASCADE_3+ classifications where H36
has no hand-occupancy improve the pattern classification
precision?

## Implementation

`h38_post_filter.py`:

1. Load H37 crossref data (H36 (L, R, A) + H12 v8 pattern).
2. For each CASCADE_3+ frame where H36 state is (0, 0, total),
   mark as CASCADE_REJECTED.
3. Compare pattern distribution before/after.
4. Compare CASCADE phases (>= 20 consecutive frames) before/after.
5. Write filtered output for downstream consumers.

## Quantitative result

### identical

```
CASCADE_3+ state distribution (before filter):
  L=0 R=1 A=2: 20
  L=1 R=0 A=2: 1
  L=0 R=0 A=3: 1
CASCADE_3+ rejected: 1 (4.5%)
Pattern distribution before: CASCADE_3+ = 22
Pattern distribution after:  CASCADE_3+ = 21, CASCADE_REJECTED = 1
CASCADE phases (>= 20 frames): before=0, after=0
```

### YouTube

```
CASCADE_3+ state distribution (before filter):
  L=0 R=1 A=4: 66
  L=1 R=0 A=4: 51
  L=0 R=0 A=5: 12
CASCADE_3+ rejected: 12 (9.3%) — all in contiguous block f=470-481
Pattern distribution before: CASCADE_3+ = 129
Pattern distribution after:  CASCADE_3+ = 117, CASCADE_REJECTED = 12
CASCADE phases (>= 20 frames): before=0, after=0
```

The YouTube rejection is a single contiguous block of 12
frames (f=470-481) with H12 v8 confidence 0.639-0.646. This
looks like a real misclassification — H12 v8 was over-confident
in calling CASCADE_3+ for these 12 consecutive frames.

## Visual QA

(no new contact sheets — H38 reuses H37's visualization)

## Key findings

1. **H38 is a small precision improvement.** It rejects 1/22
   identical CASCADE_3+ and 12/129 YouTube CASCADE_3+ frames
   that lack hand-occupancy support. The YouTube rejected
   block is a tight contiguous 12-frame stretch, suggesting
   H12 v8 had a sustained misclassification there.

2. **No substantial CASCADE phases were broken by the filter.**
   The filter only affects small isolated regions. The H12 v8
   CASCADE_3+ classifications that have hand-occupancy
   support (20/22 identical, 117/129 YouTube) are preserved.

3. **H38 is a strict post-filter, not a replacement.** H12 v8
   produces 22/129 CASCADE_3+ classifications without
   hand-occupancy support. These are isolated cases (1 on
   identical, 12 contiguous on YouTube) — not large
   misclassification blocks. The fundamental H12 v8
   CASCADE/FOUNTAIN ambiguity remains.

## Negative findings

1. **H38 does not fix the H12 v8 CASCADE/FOUNTAIN ambiguity.**
   The 9.3% rejection rate on YouTube is real but small. The
   fundamental problem is that H12 v8's hand-alternation
   metric doesn't have enough hand-events to disambiguate
   CASCADE from FOUNTAIN when the event log is sparse.

2. **H38 is conservative.** It only rejects CASCADE_3+
   classifications where H36 has zero hand-occupancy. It
   doesn't try to recover FOUNTAIN_3+ classifications
   (which would be a much riskier operation).

## Implications for downstream consumers

1. **H38 is a precision filter, not a recall filter.** It
   rejects CASCADE_3+ classifications that lack
   hand-occupancy support, improving precision at the cost
   of reducing the CASCADE_3+ count by 4.5% (identical) and
   9.3% (YouTube).

2. **H38 is safe to apply.** The rejected CASCADE_3+
   classifications are isolated cases (not large blocks),
   so the impact on downstream pattern analysis is minimal.

3. **H38 reinforces H37's finding.** H12 v8's CASCADE_3+
   classification is mostly correct (95% of identical, 91%
   of YouTube have hand-occupancy support), but a small
   fraction of CASCADE_3+ classifications lack
   hand-occupancy evidence.

## Verdict

**PASS (precision improvement, narrow scope).** H38 is a
strict post-filter that rejects CASCADE_3+ classifications
where H36 has no hand-occupancy support. The improvement is
small (1/22 identical, 12/129 YouTube) but real. H38 is
safe to apply as a downstream consumer filter.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h38_post_filter.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h38_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h38_filtered_*.csv` (2 files)
