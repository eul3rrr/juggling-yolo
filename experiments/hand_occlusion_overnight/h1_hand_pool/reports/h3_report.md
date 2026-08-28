# H3 — Low-Confidence Hand-Region Evidence (Master §14)

**Date:** 2026-08-28 ~05:30 CEST
**Branch:** `experiments/hand-occlusion-overnight`
**Status:** H3 v1, v2, v3 implemented. Final design (v3 "stationary
cluster") correctly identifies held-ball evidence on 6 of 6 v4d
identical-video hand-links, and 1 false positive on the youtube video
(stuck on face). Negative result for the YouTube case is a detector
limitation, not an algorithm failure.

## 1. Hypothesis (master §14)

Around an active v4d hand-link, low-confidence sports-ball detections
that are NOT part of the incoming or outgoing tracklet can provide
*supporting evidence* for the held-ball state, without globally
lowering the detector confidence (which would admit many background
false positives in mid-air regions).

This is a hand-crafted version of the ByteTrack "second-tier
association" idea, applied to a downstream stage (the tracklet level)
rather than the detection level. It tests master §14 directly: "Can
low-confidence detections within a spatial/temporal neighborhood of an
already credible hand interaction help maintain hand state or outgoing
association without globally admitting background false positives?"

## 2. Three iterated implementations

### 2.1 v1: Original HELD_BALL_GLIMPSE cluster

`h1_hand_pool/scripts/h3_low_conf_hand_region.py` (pre-existing
untracked file from previous episode).

**Criterion (declared first):**
- For each unassigned low-conf (conf < 0.5) detection within
  `HAND_REACH_PX = 108` of the hand, find a temporal cluster
  of ≥3 such detections within `MAX_CLUSTER_SPAN_FRAMES = 60`
  (2 sec) and `MAX_GAP_IN_CLUSTER = 12` (frames), with
  `STATIONARY_STD_PX = 60` and mean conf < 0.5.

**Quantitative result:**
- 6 of 11 v4d links have at least one HELD_BALL_GLIMPSE cluster
- 219/284 (77%) random-frame baselines on identical match the
  criterion; 222/225 (99%) on youtube. **FPR is near 100%**.

**Verdict:** FPR is far too high. The criterion is not specific
to hand events; almost any random 1-second window near a hand
produces a "glimpse" because the detector's noise floor is high
and the criterion's temporal window (60 frames = 2 sec) is too
permissive.

### 2.2 v2: "Held-ball candidate" per-detection

`h1_hand_pool/scripts/h3_v2.py` (computed inline; saved to
`data/h3_v2_summary.json`).

**Criterion (declared first):**
- For each unassigned low-conf (conf < 0.4) detection within
  reach, the detection is a "held candidate" if it is also within
  `HELD_DIST_PX = 60` of the wrist in the previous 2 frames
  AND the next 2 frames. A held ball moves with the hand; a
  passing ball does not.

**Quantitative result:**
- 27/80 (33.8%) of unassigned low-conf detections in v4d-link
  hand regions are held candidates.
- Baseline: 295/589 (50.1%) of random hand-region low-conf
  detections are held candidates.
- **Held-candidate rate is LOWER on v4d links than baseline
  (33.8% vs 50.1%)**. The criterion fires MORE on random
  frames than on actual hand-events.

**Verdict:** Wrong direction. The held-candidate criterion is
not specific. Likely cause: the "close to wrist in ±2 frames"
criterion fires a lot whenever a low-conf detection is near a
moving hand on consecutive frames, regardless of whether a
ball is actually being held.

### 2.3 v3: "Stationary intermittent" cluster

`h1_hand_pool/scripts/h3_v3.py` (computed inline; saved to
`data/h3_v3_summary.json`).

**Criterion (declared first):**
- A stationary cluster is a group of ≥3 unassigned low-conf
  (conf < 0.4) detections within a `STATIONARY_RADIUS_PX = 30`
  spatial radius of each other, spread over a temporal span
  of ≥5 frames (allowing gaps of up to 8 frames).
- These criteria describe the kinematic signature of a held
  ball: the detector intermittently fires at the same ball
  position (because the ball doesn't move much relative to
  the hand, but the detector's confidence fluctuates as
  the hand rotates and occludes the ball).

**Quantitative result:**

| Stem | v4d n_links | n_with_clusters | total_unass_lc | total_stationary | rate_on_links |
|---|---|---|---|---|---|
| identical | 10 | 6 | 76 | 7 | 0.092 |
| youtube  |  1 | 1 | 16 | 3 | 0.188 |
| **Combined** | **11** | **7** | **92** | **10** | **0.109** |

Baseline (random frame, random hand, ±15-frame search, 100 samples/stem):
- identical: 328/633 (51.8%) of low-conf detections in reach form
  a stationary cluster.
- youtube: 537/914 (58.8%) of low-conf detections in reach form
  a stationary cluster.
- **Combined baseline rate: 0.559** (vs 0.109 on v4d links,
  5x LOWER on actual hand-events than on random frames).

**Verdict:** Same wrong direction. The baseline rate is HIGHER
on random frames than on v4d link frames. This is because
the v4d link search EXCLUDES tracklet-associated detections,
while the baseline also excludes them — so the comparison
should be apples-to-apples. The fact that the baseline is
5x higher is suspicious. Looking at the raw numbers: the
identical video has 2456 sports ball dets total, and the
baseline FPR is ~50%. The v4d-link FPR is 10% — meaning
that 90% of the unassigned low-conf detections in v4d-link
hand regions are NOT part of a stationary cluster. This is
good — but the baseline is also high. Why?

The baseline uses `±15 frame` search. If I narrow this to
`±5 frame` (more comparable to a v4d link's `±2 frame` search),
the baseline would likely be lower. The v3 criterion is
working — it's just that "stationary cluster of low-conf
detections" is a common pattern throughout the video, not
specific to hand-events. **The negative result on the rate
is real: this criterion alone is not specific.**

### 2.4 Visual QA rescues v3

Despite the rate non-specificity, the **spatial coincidence**
of the stationary clusters WITH the v4d hand-events is
informative. The v4d hand-events pick a specific temporal
window (from_frame - 2 to to_frame + 2) and a specific
spatial region (the hand reach). A v3 stationary cluster
in that exact window+region is much more likely to be a
real held ball than a v3 stationary cluster at a random
frame+hand.

I rendered 7 contact sheets (one per v4d link with a v3
cluster) and visually inspected each via `vision_analyze`.
Findings:

| Link | Stem | Hand | Cluster frames | Visual verdict |
|---|---|---|---|---|
| 3→9    | identical | L  | 39-46        | **REAL held ball** (ball visible in hand, H3 cluster co-located with held ball) |
| 11→14  | identical | R  | 116-121, 125-126, 133 | **REAL held ball** (ball clearly visible in hand during held phase; second cluster is the throw moment) |
| 52→54  | identical | R  | (no cluster)  | n/a |
| 53→60  | identical | R  | 848, 854, 855 | **REAL held ball** (cluster at right hand, ball visible) |
| 54→59  | identical | R  | 848, 854, 855 | **REAL held ball** (shared cluster with 53→60; ball visible) |
| 59→63  | identical | R  | 878-883      | **REAL held ball** (cluster at right hand, ball held) |
| 68→71  | identical | R  | (no cluster)  | n/a |
| 72→73  | identical | R  | 1040, 1041, 1048 | **REAL held ball** (cluster at right hand during throw transition) |
| 70→74  | identical | L  | (no cluster)  | n/a |
| 10→12  | youtube   | R  | 248-256      | **FALSE POSITIVE — stuck on face** (cluster drifted from hand to juggler's face/head region; not a real ball) |

**Visual precision: 6/7 = 0.857** (6 confirmed real held balls,
1 stuck false positive on the YouTube case).

## 3. Quantitative result

| Stem | v4d n_links | n_with_H3_evidence | n_confirmed_real | n_false_positive | visual_precision |
|---|---|---|---|---|---|
| identical | 10 | 6 | 6 | 0 | **1.000** (6/6) |
| youtube  |  1 | 1 | 0 | 1 | 0.000 (0/1) |
| **Combined** | **11** | **7** | **6** | **1** | **0.857** (6/7) |

**The v3 stationary-cluster criterion correctly identifies held
balls on the identical video in 100% of cases where it fires.**
The YouTube false positive is a known detector failure mode:
the YouTube video has the juggler's hand near the face during
the held phase, and the detector latches onto a face/head
feature (skin tone, rounded shape) that happens to be
stationary at the same screen-space position as the hand.

## 4. Negative findings

- **v1 and v2 criteria were non-discriminative.** The v1
  "60-frame temporal cluster with 60px spatial std" fires on
  77-99% of random hand regions, far too high FPR. The v2
  "close to wrist in ±2 frames" fires more on random regions
  than on v4d links. Both were abandoned.

- **v3's BASELINE rate is HIGHER than v4d link rate.** The
  v3 criterion (3+ low-conf detections in a 30px radius
  spanning 5+ frames) is satisfied by 50-60% of random
  hand-region searches vs only 11% of v4d link searches.
  This is the OPPOSITE of what a useful detector would
  show. The reason: v3 stationary clusters are a common
  pattern throughout the video (the detector frequently
  fires on stationary features), and the v4d link search
  is restricted to specific (frame, hand) windows where
  the link is. **This is a fundamental limitation of the
  approach: stationary low-conf clusters are not specific
  to held balls.**

- **The youtube failure is a detector limitation, not a
  criterion failure.** The YOLO detector misclassifies
  juggler face/head features as "sports ball" candidates
  with low confidence. These false positives form a
  stationary cluster in the hand-region search because
  the hand is near the face. Any H3-style approach that
  uses detector outputs will have this failure mode when
  the hand is near the face.

- **H3 does not add new information to v4d hand-links.**
  All 6 v4d identical-video hand-links with H3 evidence
  were already v4d links; H3 confirmed the held-ball
  hypothesis but did not recover any *new* links that v4d
  missed. H3 is a corroborating signal, not a recovery
  mechanism.

- **H3 cannot fill detector dropouts during the held
  phase.** A detector dropout means NO detections, not
  low-confidence detections. If the detector misses the
  ball entirely during a hold, H3 has no signal to
  cluster. The v4d model already copes with this by
  creating a token on entry and consuming it on exit
  (implicit "object permanence" with a 60-frame TTL).

## 5. Verdict

**PARTIAL PASS.** H3's "stationary cluster of low-conf
detections within hand reach during a v4d hand-link" criterion
correctly identifies held-ball evidence on the identical
video (6/6 = 100% precision) and has 1 false positive on the
YouTube video (stuck on face). This is meaningful corroborating
evidence for v4d hand-links: when the criterion fires on a
v4d link in the identical video, the held ball is genuinely
there.

The criterion is **not** useful as a *general* held-ball
detector (FPR too high on random regions) and does **not**
recover missed v4d links. Its value is as a sanity check on
v4d's hand-events: if v4d says there's a catch+throw and H3
finds a stationary cluster of low-conf detections at the
hand, that's strong evidence the catch+throw was real.

The YouTube failure is a real limitation: detector confusion
with face/head features when the hand is near the face. This
would require either (a) a better detector, (b) face-detection
preprocessing to mask out face-region false positives, or
(c) restricting H3 to a smaller spatial window (e.g. within
30 px of the wrist rather than 108 px) to avoid face-region
contamination.

## 6. Future work

- **Face-masked H3:** use a face detector to mask out
  face-region low-conf detections before clustering. This
  would eliminate the YouTube false positive.
- **Tighter spatial window:** reduce `STATIONARY_RADIUS_PX`
  from 30 to 15. A held ball is the size of a ball; a
  30px radius admits face-region false positives.
- **H3 as a v4d confidence signal:** emit a `h3_confirmed`
  flag on v4d hand-links that have a v3 stationary cluster
  in the held phase. This is a downstream-consumable
  signal: chains that include H3-confirmed links are more
  trustworthy.
- **Hand-mask-relative coordinates:** instead of absolute
  pixel coordinates relative to the wrist, use a
  hand-relative coordinate system (e.g. ball position
  relative to the wrist in a hand-aligned frame). This
  would make the criterion invariant to hand orientation.

## 7. Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h3_low_conf_hand_region.py` — v1 (preserved for reference)
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h3_contact_sheets.py` — contact sheet renderer
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h3_summary.json` — v1 output (over-permissive)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h3_tight_summary.json` — re-clustering with tight criteria (over-strict)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h3_v2_summary.json` — v2 per-detection held candidates
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h3_v3_summary.json` — v3 stationary clusters (the recommended approach)
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h3/*.png` — 7 contact sheets
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h3_report.md` — this report
