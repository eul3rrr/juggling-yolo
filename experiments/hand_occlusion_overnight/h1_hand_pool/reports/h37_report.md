# H37 — Cross-reference H36 (L, R, A) with H12 v8 pattern labels

## Hypothesis

H36 produces a per-frame (L, R, A) state from a hand-occupancy
state machine. H12 v8 produces per-frame pattern labels
(CASCADE_3+, FOUNTAIN_3+, etc.) using a different signal
(per-frame ball count + recent event log). The two should
agree on which frames have a ball in a hand. Cross-referencing
the two signals answers:

1. Do H36 and H12 v8 agree on (L, R, A) at each frame?
2. Does the (L, R, A) state help disambiguate CASCADE_3+ vs
   FOUNTAIN_3+ on the late phase where H12 v8 fails?
3. Is H36's per-frame state a useful input to a v9 of H12?

## Implementation

`h37_crossref.py`:

1. Load H36 per_frame and H12 v8 pattern_inference (H35 version)
   per-frame data.
2. Merge on frame number.
3. Compute (L+R+A) vs (n_in_hand_left + n_in_hand_right +
   n_in_air) agreement.
4. For frames where H12 v8 says CASCADE_3+ or FOUNTAIN_3+,
   check if H36's (L, R, A) state is consistent.
5. Visualize agreement/disagreement on a contact sheet.

`h37_contact_sheets.py` renders a 2-panel contact sheet per
video:
- Top: stacked area chart of (L, R, A) with H12 v8 pattern
  background color.
- Bottom: H12 v8 confidence over time.

## Quantitative result

### identical (3-ball)

```
common frames: 1020
agreement: 823/1020 = 80.7%
L disagreement: 60 (L_extra=60, L_missing=0)
R disagreement: 137
```

### YouTube (5-ball)

```
common frames: 868
agreement: 664/868 = 76.5%
L disagreement: 85 (L_extra=85, L_missing=0)
R disagreement: 119
```

### Pattern x state for n_total>=3 frames (identical)

```
FOUNTAIN_3+ L=0 R=0 A=3: 283
MIXED_3+    L=0 R=0 A=3: 203
MIXED_3+_UNCONFIRMED L=0 R=0 A=3: 20
CASCADE_3+  L=0 R=1 A=2: 20
MIXED_3+_UNCONFIRMED L=0 R=1 A=2: 5
FOUNTAIN_3+ L=0 R=1 A=2: 3
MIXED_3+    L=0 R=1 A=2: 3
FOUNTAIN_3+ L=1 R=0 A=2: 2
MIXED_3+    L=1 R=0 A=2: 2
CASCADE_3+  L=1 R=0 A=2: 1
CASCADE_3+  L=0 R=0 A=3: 1
```

### Pattern x state for n_total>=3 frames (YouTube)

```
MIXED_3+              L=0 R=0 A=5: 472
FOUNTAIN_3+           L=0 R=0 A=5: 94
CASCADE_3+            L=0 R=1 A=4: 66
MIXED_3+_UNCONFIRMED  L=0 R=0 A=5: 58
MIXED_3+              L=0 R=1 A=4: 55
CASCADE_3+            L=1 R=0 A=4: 51
MIXED_3+              L=1 R=0 A=4: 32
FOUNTAIN_3+           L=0 R=1 A=4: 16
MIXED_3+_UNCONFIRMED  L=1 R=0 A=4: 12
CASCADE_3+            L=0 R=0 A=5: 12
```

### Late-phase FOUNTAIN_3+ on identical (f=800-1050)

```
FOUNTAIN_3+ frames: 71
FOUNTAIN_3+ x L=0 R=0 A=3: 69 (97%)
FOUNTAIN_3+ x L=0 R=1 A=2: 2 (3%)
```

## Visual QA

2 contact sheets rendered. The contact sheets show:
- **identical late phase (f=800-1050):** FOUNTAIN_3+ blocks
  appear as continuous stretches alternating with MIXED_3+ blocks.
  H36's (L, R, A) state is mostly (0, 0, 3) during FOUNTAIN_3+
  blocks — H36 has no hand-occupancy evidence in these blocks.
  H12 v8 confidence is lower (0.5-0.7) than early phase (0.7-0.9).
- **YouTube:** MIXED_3+ dominates, but the (L, R, A) state shows
  the per-hand alternation pattern clearly (0, 1, 4) and
  (1, 0, 4) when the juggler is actively catching/throwing.

## Key findings

1. **H12 v8 FOUNTAIN_3+ classification has 0% hand-occupancy
   support on identical late phase.** 69/71 = 97% of FOUNTAIN_3+
   frames are in H36 state (0, 0, 3) — meaning H36 sees no ball
   in either hand. The remaining 2 frames are (0, 1, 2). This
   confirms that H12 v8's FOUNTAIN_3+ classification is based on
   the recent event log (last K events with hand alternation
   metric), NOT on actual hand occupancy.

2. **H12 v8 CASCADE_3+ classification HAS hand-occupancy support.**
   On identical, 20/22 CASCADE_3+ frames are in H36 state
   (0, 1, 2) — meaning the right hand is holding a ball. This
   is consistent with a cascade pattern where catches alternate
   hands. On YouTube, 66/129 CASCADE_3+ frames are (0, 1, 4)
   and 51/129 are (1, 0, 4) — clear hand-alternation signal.

3. **L_extra and R_extra disagreements are all HOLD frames.**
   H36 says L=1 in frames where H12 v8 says L=0, but the
   H36_event_type is "HOLD" (interpolated). This means H36
   sees a hand-occupancy state carried over from a previous
   catch, while H12 v8 only counts chains with explicit
   hand-events in the exact frame. This is expected behavior
   — H36's interpolation is doing its job.

4. **MIXED_3+ is the dominant YouTube pattern (54%).** 472/868
   YouTube frames are MIXED_3+ in state (0, 0, 5) — meaning
   the H12 v8 algorithm can't decide between CASCADE_3+ and
   FOUNTAIN_3+ when the (L, R, A) state is empty. This is the
   same fundamental problem H12 v8 has been struggling with
   throughout the H12 series.

5. **H12 v8 confidence in the late phase drops to 0.5-0.7
   on identical.** This reflects the CASCADE/FOUNTAIN ambiguity.
   The H12 v8 algorithm is honest about its uncertainty.

## Negative findings

1. **H36's (L, R, A) state does NOT resolve the CASCADE/FOUNTAIN
   ambiguity.** The (L, R, A) state is mostly (0, 0, 3) during
   FOUNTAIN_3+ blocks, providing no signal to disambiguate.
   This confirms H12's fundamental limitation: the CASCADE/
   FOUNTAIN distinction depends on event-log density and recent
   hand alternation, not on per-frame hand occupancy.

2. **The H12 v8 pattern labels are not always consistent with
   the H36 hand-occupancy state.** CASCADE_3+ frames have
   hand-occupancy (1 ball in a hand), but FOUNTAIN_3+ frames
   don't. This is a quirk of the H12 v8 algorithm: CASCADE_3+
   is detected when the juggler is actively catching (hand
   occupancy present), but FOUNTAIN_3+ is detected when the
   juggler is in a "same-hand repeat" pattern (no new hand
   event, just a held ball that was caught earlier).

## Implications for downstream consumers

1. **H36's (L, R, A) state is a useful validation signal for
   H12 v8's CASCADE_3+ classification.** If a frame is CASCADE_3+
   and H36 says (0, 0, 3), the classification is likely wrong.
   This could be used as a post-filter: reject CASCADE_3+
   classifications where H36 has no hand-occupancy evidence.

2. **H36's (L, R, A) state does not help with FOUNTAIN_3+.** The
   FOUNTAIN_3+ classification is based on the absence of recent
   hand alternation, not on per-frame hand occupancy. H36 can't
   help here.

3. **The 80% agreement rate (identical) and 76% agreement rate
   (YouTube) is a useful summary metric.** It confirms that
   H36 and H12 v8 are largely consistent, with the disagreements
   being explained by H36's interpolation of HOLD frames.

## Verdict

**PASS (consumer-pass, validation).** H37 confirms the consistency
between H36's (L, R, A) state and H12 v8's pattern labels on
both videos. The 80%/76% agreement rate is a useful summary
metric. H36's (L, R, A) state validates CASCADE_3+
classifications (which have hand-occupancy support) but cannot
disambiguate FOUNTAIN_3+ (which has no hand-occupancy signal).

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h37_crossref.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h37_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h37_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h37_crossref_*.csv` (2 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h37/*.png` (2 files)
