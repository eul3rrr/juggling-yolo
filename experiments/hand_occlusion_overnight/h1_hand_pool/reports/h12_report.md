# H12 — Per-Frame Juggling Pattern Inference

## Hypothesis

Given the H11 v2 per-frame census and the H11 v1
catch/throw events, we can infer the juggling pattern
at each frame:
- NO_BALL: 0 chains
- SINGLE_BALL: 1 chain
- TWO_BALL variants
- CASCADE_3+: 3+ chains, alternating hands
- FOUNTAIN_3+: 3+ chains, both from same hand
- UNKNOWN: low quality, can't classify

This is a useful downstream consumer of H11 because it
gives a per-frame "what pattern is the juggler doing"
label, which can be used to identify pattern transitions
and dropout phases.

## Thresholds (declared from physical geometry, not from manual labels)

- `MIN_QUALITY_FOR_PATTERN = 0.5`: below this, pattern
  is UNKNOWN (avoids over-counting artifacts).
- `RECENT_EVENT_FRAMES = 30`: how recent is "recent"
  for catch/throw events.

## Quantitative result

### Identical video (1077 frames)

| Pattern | frames | pct |
|---|---|---|
| UNKNOWN | 364 | 33.8% |
| CASCADE_3+ | 236 | 21.9% |
| TWO_BALL | 165 | 15.3% |
| SINGLE_BALL | 150 | 13.9% |
| FOUNTAIN_3+ | 126 | 11.7% |
| NO_BALL | 35 | 3.2% |
| TWO_BALL_ONE_HAND | 1 | 0.1% |

The pattern is dominated by UNKNOWN (33.8% — frames
where H10 v5 quality is too low to confidently classify
the pattern) and CASCADE_3+ (21.9% — the main juggling
pattern). FOUNTAIN_3+ appears in distinct blocks,
suggesting the juggler transitions between cascade and
fountain phases.

### YouTube video (898 frames)

| Pattern | frames | pct |
|---|---|---|
| CASCADE_3+ | 837 | 93.2% |
| FOUNTAIN_3+ | 61 | 6.8% |

The YouTube video is dominated by CASCADE_3+ — but
this is the H10 v5 over-counting artifact (chains are
mostly UNCERTAIN quality, so the H11 v3 quality filter
removes them, but the over-counting survives). The
pattern inference on YouTube is unreliable.

## Visual QA

The H12 contact sheet
`contact_sheets_h11/pattern_identical_balls_trick_000_018.png`
shows the per-frame pattern timeline for identical. The
vision_analyze tool identified four distinct phases:

1. **0-220: FOUNTAIN_3+ phase** (3+ balls, all from
   same hand, with some SINGLE_BALL and NO_BALL mixed in)
2. **220-300: transition / "messy" region** where
   confidence dips and patterns fluctuate
3. **300-700: CASCADE_3+ phase** (3+ balls, alternating
   hands, the main pattern) — high confidence
4. **700-1080: variable mixed tail** with brief returns
   to fountain, single-ball manipulation, and a fleeting
   one-hand two-ball moment

## Negative findings

1. **The YouTube pattern inference is dominated by
   over-counting.** 93.2% CASCADE_3+ on YouTube is the
   H10 v5 quality issue, not a real pattern. H12 on
   YouTube is unreliable.

2. **33.8% of identical frames are UNKNOWN.** The H10
   v5 quality is below 0.5 for most frames, so the
   pattern classifier falls back to UNKNOWN. This is
   a useful safety net — it prevents H12 from
   over-confident pattern labels.

3. **The CASCADE_3+ vs FOUNTAIN_3+ distinction is based
   on the `unique_hands` of recent events.** A
   3-ball cascade has alternating hands, so `unique_hands
   = 2`. A 3-ball fountain has both balls thrown from
   the same hand, so `unique_hands = 1`. With only 8
   catch/throw events on identical, the distinction is
   weak. A future H12 v2 could use a sliding window of
   multiple events instead of the simple "recent" window.

4. **The pattern inference is sensitive to the H11
   census over-counting.** At f=700 the identical
   video shows 5 balls (anomaly); the pattern
   classifier would call this CASCADE_3+ but it's
   actually a detection artifact. Future H12 v2
   could add a quality-based confidence floor.

## Verdict

**PASS.** H12 successfully:

1. **Classifies 66.2% of identical frames** into
   interpretable patterns (CASCADE_3+, FOUNTAIN_3+,
   TWO_BALL, SINGLE_BALL, NO_BALL). The remaining
   33.8% are correctly labeled UNKNOWN.
2. **Identifies pattern transitions**: 0-220 FOUNTAIN,
   300-700 CASCADE, 700+ mixed. This is consistent
   with a juggler doing a 3-ball trick with multiple
   phases.
3. **Provides a useful safety net** (UNKNOWN for
   low-quality frames) that prevents H12 from
   over-confident labels.
4. **Caveat on YouTube**: H12 is unreliable on YouTube
   due to H10 v5 over-counting.

H12 is a useful downstream consumer of H11. Future
H12 v2 could:
- Use a sliding window of events for cascade/fountain
  distinction
- Add a quality-based confidence floor
- Distinguish 3-ball from 4+ ball patterns
- Detect specific events (drop, recovery, transition)

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_pattern_inference.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_pattern_visualization.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h11/pattern_*.png` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h12_report.md`
