# H12 v6 / v6b — Ensemble of v2 (event-log) and v5 (detector signal)

## Hypothesis (master §17 priority)

> After H12 v4/v5, the next logical step is a v2 (event-log) and v5
> (per-frame detector) ensemble. v2's high-confidence windows should
> anchor v5's noisy per-frame signal; v5's per-frame signal should
> disambiguate v2's FOUNTAIN miscalls.

## H12 v6: basic ensemble (no confidence weighting)

Decision tree per frame:
- 0 events: NO_BALL.
- n_total < 3: v2 and v5 should agree (both see 1-2 balls). Take the
  more confident on disagreement.
- n_total >= 3 and v2/v5 DISAGREE (CASCADE vs FOUNTAIN): report
  `MIXED_3+_ENSEMBLE` with confidence = (c2 + c5) / 2.
- n_total >= 3 and v2/v5 AGREE: take the more confident.
- v2 CONFIDENT and v5 not: v2 wins.
- v5 CONFIDENT and v2 not: v5 wins.

Quantitative result (identical, 1077 frames):

| Pattern | v6 count | v6 % |
|---|---|---|
| FOUNTAIN_3+ | 280 | 26.0% |
| TWO_BALL | 273 | 25.3% |
| SINGLE_BALL | 219 | 20.3% |
| MIXED_3+ | 125 | 11.6% |
| CASCADE_3+ | 73 | 6.8% |
| MIXED_3+_ENSEMBLE | 68 | 6.3% |
| NO_BALL | 35 | 3.2% |
| MIXED_3+_UNCONFIRMED | 3 | 0.3% |
| TWO_BALL_ONE_HAND | 1 | 0.1% |

The 68 MIXED_3+_ENSEMBLE frames are exactly the frames where v2
and v5 disagree on CASCADE vs FOUNTAIN. Late phase (f=890-1050)
has 53 of these (78%).

The v2/v5 disagreement on identical breaks down as:
- 60.6% both say n_total<3
- 17.1% v2 says n_total<3, v5 says FOUNTAIN (v5 sees 3+ airborne)
- 8.9% both FOUNTAIN
- 6.8% v2 says n_total<3, v5 says CASCADE
- **6.3% v2 FOUNTAIN, v5 CASCADE (DISAGREE → MIXED_3+_ENSEMBLE)**
- 0.3% v2 FOUNTAIN, v5 says n_total<3

The 6.3% disagreement is concentrated in the late phase (f=890-1050).

## H12 v6b: confidence-weighted ensemble

v6 reports MIXED for ALL v2/v5 disagreements, but many of these
disagreements are due to v2's low confidence (0.42-0.63) while v5
is uniformly confident (0.70) in CASCADE. v6b adds a confidence
asymmetry rule:

```
if c5 > c2 + 0.10: v5 wins (with its pattern)
if c2 > c5 + 0.10: v2 wins (with its pattern)
if |c2 - c5| <= 0.10: MIXED_3+_ENSEMBLE
```

Quantitative result (identical, 1077 frames):

| Pattern | v6b count | v6b % |
|---|---|---|
| FOUNTAIN_3+ | 283 | 26.3% |
| TWO_BALL | 273 | 25.3% |
| SINGLE_BALL | 219 | 20.3% |
| MIXED_3+ | 125 | 11.6% |
| CASCADE_3+ | 116 | 10.8% |
| NO_BALL | 35 | 3.2% |
| MIXED_3+_ENSEMBLE | 25 | 2.3% |
| TWO_BALL_ONE_HAND | 1 | 0.1% |

Sources:
- agree: 970 (90.1%)
- v5_conf_wins_cascade: 43 (4.0%)
- no_ball: 35 (3.2%)
- ensemble_disagree_close_conf: 25 (2.3%)

v6b now correctly classifies 43 late-phase frames as CASCADE_3+
(v5 won, v2 was less confident). The remaining 25 MIXED_3+_ENSEMBLE
frames are cases where v2 and v5 had similar confidence (0.42-0.70
range, |diff| <= 0.10).

## Visual QA

Two contact sheets rendered for visual inspection:

1. `contact_sheets_h12v6b/late_phase_v6b_cascade.png` (6 frames
   where v6b chose CASCADE_3+ over v2's FOUNTAIN_3+):
   - Vision tool said these frames are visually FOUNTAIN, not
     CASCADE. This contradicts the H12 v4/v5 report which said
     v5's CASCADE classification was correct in 4/6 of similar
     frames. The vision tool is unreliable on this distinction
     because: (a) cascade and fountain can look similar at single
     frames; (b) the 2D camera projection loses 3D depth cues;
     (c) hand proximity makes the hand-crossing pattern ambiguous.

2. `contact_sheets_h12v6b/late_phase_v6b_ensemble.png` (6 frames
   where v2 and v5 had close confidence, v6b reports MIXED):
   - Vision tool also said these are FOUNTAIN. v6b's MIXED label
     is honest but not particularly informative.

3. `contact_sheets_h12v6b/late_phase_890_1050_v6b.png` (standard
   f=890, 920, 950, 980, 1010, 1040):
   - Same conclusion: visually FOUNTAIN-like.

## Negative findings

1. **Vision tool is unreliable for CASCADE/FOUNTAIN distinction.**
   Three independent vision queries on different late-phase
   contact sheets all said FOUNTAIN, but the H12 v4/v5 report
   said v5's CASCADE was correct in 4/6 frames. This is a real
   epistemic problem: cascade vs fountain cannot be reliably
   determined from single frames in this video.

2. **The detector signal is not a clean CASCADE/FOUNTAIN
   discriminator.** Per-frame vx direction analysis on identical:
   - early (0-300): 58% 1-dir, 42% 2-dir
   - mid (300-700): 91% 1-dir (low activity)
   - late (700-1100): 59% 1-dir, 41% 2-dir

   The 2-dir signal is not strongly concentrated in cascade-like
   phases. Either the detector misses too many balls (causing
   vx=0) or the actual pattern is mixed.

3. **v6b's "v5 won" decision may be wrong.** If the vision tool
   is right that the late phase is FOUNTAIN, then v2 is right
   and v5 is wrong, so v6b's choice of CASCADE_3+ is wrong.
   But if H12 v4/v5's earlier visual QA was right that v5 was
   correct, then v6b's choice is right. Without ground truth,
   we can't tell.

4. **YouTube is uninformative.** v6b reports 99.8% CASCADE_3+
   on YouTube (driven entirely by v5's per-frame detector
   signal, which is inflated by H10 v5 over-counting). The
   v2 event log has 1 event on YouTube, so v2 is mostly
   UNCONFIRMED. v6b inherits v5's verdict by default.

## Verdict

**v6: PARTIAL PASS.** v6 correctly identifies v2/v5
disagreements as MIXED_3+_ENSEMBLE. This is the honest answer
but loses the correct v5 signal in 6.3% of identical frames.

**v6b: MIXED.** v6b propagates v5's answer when v5 is
meaningfully more confident. The 43 frames where v5 won are
either correct (per H12 v4/v5) or wrong (per current vision
QA) — we cannot tell. v6b is a reasonable operating point
when the visual ground truth is unknown.

**The fundamental question — is the late phase a cascade or
fountain? — remains UNRESOLVED.** The detector signal is
ambiguous, the event log is too sparse, and vision tools
disagree across passes. H12 cannot answer this with the
current data.

A more decisive test would require:
- A controlled experiment with a juggler performing
  CASCADE/FOUNTAIN on command with ground-truth labels.
- Multi-view video to disambiguate 3D ball trajectories.
- Higher frame rate to capture apex/throw moments cleanly.

These are out of scope for the current data.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v6_ensemble.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v6b_confidence_weighted.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v6_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h12_v6b_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_v6_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_inference_v6b_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/pattern_phases_v6*.csv` (4 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_v6_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h12_v6b_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h12v6/*.png` (4 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h12v6b/*.png` (3 files)
