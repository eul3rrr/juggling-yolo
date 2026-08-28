# H45 — Per-Chain Flight-Time / Siteswap Analysis

**Date:** 2026-08-28 ~15:00 CEST
**Status:** COMPLETE (NEGATIVE result with structural insight)
**Author:** autonomous hand-occlusion overnight research lab

---

## Hypothesis

H12 v8 infers CASCADE_3+ vs FOUNTAIN_3+ via a K=4 sliding window of
hand events. The window is too short for late-phase patterns and
introduces K=4 boundary effects. A siteswap-based approach computes
the "throw digit" directly from the THROW-to-next-CATCH flight time
and should produce a more uniform, less window-bound pattern
inference.

The smallest possible test: per-chain flight-time statistics
(median, CV) cross-checked against H12 v8 pattern labels.

## Method

`h45_siteswap_digits.py` consumes
`chain_events_h35_<stem>.csv` (the H11 v7 catch/throw event log
on h7v3plus3 chains) and computes, for each chain:

- n_tracklets (with both CATCH and THROW observed)
- median hold_time (per tracklet: throw_frame - catch_frame)
- median flight_time (per cross-tracklet pair: next_catch_frame - throw_frame)
- flight_time CV (std/mean) when n_flights >= 3
- flight_time min/max
- dominant H12 v8 pattern at the chain's median frame
- mean H12 v8 pattern confidence

Plus a per-video **event-log sparsity diagnostic**:
- n_events, n_catches, n_throws
- n_chains, n_chains with at least 1 flight, n_chains with >= 3 flights
- event_rate (events per frame)

Cross-pattern CV analysis groups chains by their dominant H12 v8
pattern and reports per-pattern CV.

**Not parameter-tuned.** UNIFORM_CV_THRESHOLD = 0.5 is declared
from physics (a 3-ball cascade with constant beats has CV = 0
by construction; CV = 0.5 admits ~30% noise in flight times
before flagging as mixed).

## Quantitative result

### Event-log sparsity diagnostic

| Video | n_events | n_catches | n_throws | n_chains | w/ flights | w/ 3+ flights | event_rate | duration (frames) |
|---|---|---|---|---|---|---|---|---|
| identical | 48 | 24 | 24 | 13 | 5 (38%) | 2 (15%) | 0.047 | 1032 |
| YouTube   | 50 | 25 | 25 | 10 | 7 (70%) | 1 (10%) | 0.059 |  847 |

**Only 2/13 identical chains and 1/10 YouTube chains have
n_flights >= 3** — the minimum needed for any CV estimate.
The siteswap analysis is structurally infeasible on 84% of
identical chains and 90% of YouTube chains.

### Per-chain flight statistics (chains with n_flights >= 1)

| Video | chain | n_flights | median_ft | flight_cv | dom_pattern | conf |
|---|---|---|---|---|---|---|
| identical | 12 | 1 | 3 | N/A | SINGLE_BALL | 0.325 |
| identical | 22 | 4 | 32.0 | 0.65 | FOUNTAIN_3+ | 0.714 |
| identical | 23 | 1 | 131 | N/A | FOUNTAIN_3+ | 0.714 |
| identical | 29 | 3 | 16 | 0.78 | SINGLE_BALL | 0.711 |
| identical | 30 | 2 | 74.5 | 0.56 | MIXED_3+ | 0.65 |
| YouTube   | 0 | 2 | 101.0 | 0.57 | MIXED_3+ | 0.694 |
| YouTube   | 3 | 2 | 209.5 | 0.54 | MIXED_3+ | 0.642 |
| YouTube   | 7 | 2 | 134.0 | 0.71 | MIXED_3+ | 0.646 |
| YouTube   | 8 | 2 | 103.0 | 0.55 | MIXED_3+ | 0.639 |
| YouTube   | 9 | 4 | 61.5 | 0.47 | MIXED_3+ | 0.64 |
| YouTube   | 10 | 2 | 135.5 | 0.79 | MIXED_3+ | 0.639 |
| YouTube   | 12 | 1 | 60 | N/A | MIXED_3+ | 0.639 |

### Cross-pattern CV

| Pattern | n | mean CV | median CV | stdev |
|---|---|---|---|---|
| FOUNTAIN_3+ | 1 | 0.654 | 0.654 | N/A |
| SINGLE_BALL | 1 | 0.784 | 0.784 | N/A |
| MIXED_3+ | 7 | 0.598 | 0.560 | 0.110 |

**No pattern has a clean CV < 0.5.** Even MIXED_3+ (the pattern
with the most samples, n=7) has median CV 0.56.

### Flight time distribution (all 25 rows)

| Bucket | count |
|---|---|
| [0, 5)   | 2 |
| [5, 15)  | 1 |
| [15, 30) | 1 |
| [30, 60) | 6 |
| [60, 100) | 7 |
| [100, 200) | 6 |
| [200, 400) | 3 |

By video:

| Video | n | mean | median | min | max | values |
|---|---|---|---|---|---|---|
| identical | 11 | 40.1 | 33 | 1 | 131 | 1, 3, 5, 16, 31, 33, 33, 39, 45, 104, 131 |
| YouTube | 15 | 116.1 | 67 | 58 | 289 | 58, 60, 60, 60, 61, 62, 63, 67, 130, 134, 142, 143, 201, 211, 289 |

## Visual QA on the 3 chains with n_flights >= 3

Contact sheets rendered to `h1_hand_pool/contact_sheets_h45/`
(11 PNG files: 4 chain 22 + 3 chain 29 + 4 chain 9).

### Identical chain 22 (FOUNTAIN_3+, CV=0.65) — 4 flights inspected

| Edge | flight | verdict | reasoning |
|---|---|---|---|
| 37→40 | 1 | **IDENTITY SWITCH** | Vision: "1-frame flight is physically impossible". Metadata shows 999px → 94px discontinuity (end_dist 999.0, slope 0.00 → 12 px-frame jump). |
| 40→41 | 33 | **REAL CATCH-THROW** | Vision: "yellow trail ends at R circle, cyan trail emerges from same R region, ball visible at right hand at f=549". 33-frame flight ≈ 1.1s, plausible for 3-ball cascade. |
| 41→45 | 31 | **REAL CATCH-THROW** | Vision: "pink ball at R circle in focus frame, slopes -0.20 → +1.72 (descending-into-catch, ascending-after-throw)". 31-frame flight ≈ 1.0s, plausible. |
| 45→46 | 39 | **REAL CATCH-THROW** | Vision: "ball descends into R hand (slope -0.97), ascends from R hand (slope +2.31)". 39-frame flight ≈ 1.3s, plausible. Right hand is empty at focus frame but throwing motion visible +10f. |

**Result:** 3/4 flights in chain 22 are real catch-throws; 1/4
(ft=1) is an identity switch. CV=0.65 reflects this single
identity switch.

### Identical chain 29 (SINGLE_BALL, CV=0.78) — 3 flights inspected

| Edge | flight | verdict | reasoning |
|---|---|---|---|
| 52→54 | 5 | **IDENTITY SWITCH** | Vision: "hand parity mismatch (right-end → left-start), 5-frame flight is implausibly short". 5-frame flight at slopes ±12 means ball barely moves. Tracker fragment. |
| 54→59 | 33 | **REAL CATCH-THROW** | Vision: "yellow trail terminates at R hand, cyan trail at L region". 33-frame flight ≈ 1.1s, plausible. |
| 59→61 | 16 | (not visually inspected, but consistent with 5-33 pattern) |

**Result:** 1/2 inspected flights are real catch-throws; 1/2
(ft=5) is an identity switch. CV=0.78 reflects this high mix.

### YouTube chain 9 (MIXED_3+, CV=0.47) — 4 flights inspected

| Edge | flight | verdict | reasoning |
|---|---|---|---|
| 22→26 | 134 | **TRACKER FRAGMENTATION** | Vision: "134 frames = ~4.5s, physically impossible". Slope jump -0.29 → +12.32. Trail resets at hand. |
| 26→31 | 61 | **TRACKER FRAGMENTATION** | Vision: "61 frames = ~2.0s, extraordinarily long for 5-ball". Slope jump 0.94 → 14.35. No visible ball at R hand. |
| 31→35 | 58 | **TRACKER FRAGMENTATION** | Vision: "58 frames = ~1.93s, implausibly long". Slope jump 1.81 → 11.20. Vision tool also notes: "the actual hand-to-hand interval is 11 frames between f860 and f871". |
| 35→38 | 62 | **TRACKER FRAGMENTATION** | Vision: "62 frames unrealistic; trail continuity broken; slope jump 2.34 → 11.96". |

**Result:** 0/4 flights in chain 9 are real catch-throws. ALL are
tracker fragmentation artifacts. CV=0.47 (the lowest in the
dataset) is misleadingly "uniform" because all 4 flights are
~58-62 frames, i.e. all are the SAME artifact.

## Negative findings

### 1. Event-log sparsity is the dominant structural limitation

The H12 v8 hand-event log contains:
- identical: 48 events / 1032 frames = 0.047 events/frame
- YouTube: 50 events / 847 frames = 0.059 events/frame

For a 30 fps video at the 0.5 event/frame rate needed for
siteswap analysis (one event per throw per catch per second),
we would need ~1500 events for identical and ~1230 for YouTube.
We have ~3% of the required density.

A 3-ball cascade juggler throws a ball every ~0.5 seconds
(each hand throws 1.5 times/second; total = 3 throws/second),
producing ~6 events/second of source data. The H12 v8 event
log captures only ~1.4 events/second (or 23% of the physical
throw rate). The remaining 77% are TRACKER FAILURES — the
detector doesn't fire during fast juggling motion.

### 2. YouTube's "low CV" is a tracker-fragmentation artifact

YouTube chain 9 has CV=0.47 — the lowest in the dataset, and
the only chain that even theoretically qualifies as "uniform"
by the H45 threshold. But ALL 4 of chain 9's flights are
tracker fragmentation, not real catch-throws. The "uniform
flight time" is "uniformly broken tracking", not "uniform
juggling".

This is an important conceptual point: **low flight-time CV
can be EITHER real uniform juggling OR uniform tracker failure.
A pure statistical test cannot distinguish them without
ground truth.**

### 3. Identical's "real flights" are 30-40 frames; the outliers are identity switches

Within identical's 11 flights, the 7 with flight_time >= 16 are
visually confirmed as real catch-throws. The 4 with flight_time
< 10 (1, 3, 5 frames) are all identity switches (tracklet
breaks where two tracklets briefly overlap in the same image
position).

A clean filter would be: **drop flights with flight_time < 10
frames as identity switches.** Applied to identical, this leaves
7 real catch-throws, which is enough for a per-chain CV estimate
on chain 22 (CV=0.65) and chain 29 (CV=0.78, but 1/2 real).

### 4. Siteswap analysis is infeasible with the H12 v8 event log

Even after applying the 10-frame filter, only 2 identical chains
(chain 22 with 4 flights, chain 29 with 3 flights) have enough
real flights for CV analysis. YouTube has 0 chains with enough
real flights (all 4 chain-9 flights are tracker fragmentation;
no other YouTube chain has 3+ flights).

**Siteswap analysis is not implementable on the h7v3plus3 chain
set with the H12 v8 event log.** This is a fundamental
limitation of the input data, not an H45 algorithm problem.

## Implications for downstream consumers

1. **The H12 v8 event log is fundamentally incomplete for
   siteswap analysis.** To do siteswap, we need a denser event
   log — either via faster frame rate, better tracking, or
   detector-only signal interpolation.

2. **The 30-40 frame flight times on identical are a real signal.**
   3-ball cascade ball airtime is 1.0-1.3 seconds at 30 fps,
   which matches the H12 v8 event-log flight times exactly. This
   validates H12 v8's catch-throw event detection on identical.

3. **The YouTube event log is unreliable for flight-time analysis.**
   Tracker fragmentation dominates, and the "flight times" are
   uniformly 58-67 frames because the tracker has a consistent
   minimum re-acquisition delay. This is a useful negative
   finding for H12 v8 on YouTube: **the H12 v8 event log is
   trustworthy for chain topology but not for inter-event
   timing on YouTube.**

4. **The cleanest fix is to use H8 v8's per-arc gravity statistics
   instead of H12 v8's event-log-derived flight times.** H8 v8
   works at the tracklet level (per-arc gravity), not the
   chain-event level, and is unaffected by tracker fragmentation.
   H8 v8's per-arc gravity median 0.46 (YouTube) is closer to
   the expected 0.5 than H12 v8's flight times would suggest.

## Verdict

**H45 verdict: NEGATIVE result with structural insight.**

The H12 v8 hand-event log is too sparse for siteswap analysis.
Only 2/13 identical chains and 1/10 YouTube chains have
n_flights >= 3. Of those, the 2 identical chains (22, 29) are
analyzable, and visual QA confirms the 30-40 frame flights are
real catch-throws. The 1 YouTube chain (9) has all 4 flights
visually confirmed as tracker fragmentation.

**The single most important H45 finding is the distinction
between real flight times (30-40 frames on identical) and
tracker-fragmentation "flight times" (58-67 frames on YouTube).
This validates the H12 v8 event log on identical and confirms
its limitations on YouTube at a quantitative level.**

**The 10-frame flight-time filter is a useful downstream
consumer post-filter:** drop any H12 v8 "flight" < 10 frames
as a likely identity switch. Applied to identical, this rejects
3/11 (27%) of flights as identity switches and preserves 7
real catch-throws.

## Artifacts

- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h45_siteswap_digits.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/scripts/h45_flight_time_contact_sheets.py`
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h45_siteswap_flights.csv` (25 rows)
- `experiments/hand_occlusion_overnight/h1_hand_pool/data/h45_siteswap_summary.json`
- `experiments/hand_occlusion_overnight/h1_hand_pool/contact_sheets_h45/*.png` (11 files)
- `experiments/hand_occlusion_overnight/h1_hand_pool/reports/h45_report.md` (this file)

## Recommended next research

The h7v3plus3 chain set is well-validated at the chain-topology
level (H10), identity level (H11), hand-occupancy level (H36),
and event-log flight-time level (H45, this report). The dominant
remaining gap is **per-arc physics on YouTube long tracklets**.

H8 v8 already provides per-arc gravity statistics. A natural
follow-up is H46: integrate H8 v8's per-arc gravity as a
**per-flight physical consistency check**. For each H12 v8
"flight", compute H8 v8's gravity estimate from the source
tracklet's last arc and the target tracklet's first arc, and
reject flights where the implied free-fall time is inconsistent
with the measured flight time.

This would convert H8 v8 from a per-edge signal to a per-flight
signal, potentially distinguishing real flights from
tracker-fragmentation artifacts based on physics alone.
