# E5: Literature sweep for juggling-ball multi-object tracking

Date: 2026-08-26 (overnight session). Raw arXiv metadata in `data/e5_raw/*.txt`.
Focus: our open problems P1 fragmentation, P2 ambiguity near hands, P3 unused
physics, P5 hand events, P6 detector gaps during overlap.

## A. Directly applicable papers

### A1. TrackNet series (sports ball detection under blur+occlusion)
- TrackNetV1 [1907.03698]: deep network tracking high-speed tiny balls; spatio-
  temporal heatmaps instead of per-frame boxes.
- TrackNetV4 [2409.14543]: adds motion attention maps; targets partial occlusion /
  low visibility explicitly.
- TrackNetV5 [2512.02789]: residual-driven spatio-temporal refinement + motion
  direction decoupling; states V1-V3 fail at occlusions due to purely visual cues.
- Verdict: the strongest known detector-side fix for P6 (our YOLO misses balls
  during blur/overlap). Requires fine-tuning on juggling-like footage (green
  balls, hand occlusions); pretrained tennis/badminton checkpoints exist but
  domain gap is large. ACTION: collect labels or synthesize training clips later;
  not a tonight-experiment.

### A2. Physics-Guided Fusion for Fast Moving Small Objects [2510.20126]
- RGB-D + physics-based tracking fused with learned detection; targets exactly
  "fast-moving tiny objects" where generic trackers break.
- Verdict: validates our physics-first architecture; their fusion ideas map to
  our ballistic scorer + gate design. No code needed; conceptual support.

### A3. Online Min Cost Circulation for MOT on Fragments [2311.04749]
- MOT global association as min-cost-flow/circulation over a fragment graph;
  online variant via sliding windows.
- Verdict: DIRECT implementation target for E6. Our E2 Hungarian is the
  single-link special case; flow formulation builds optimal CHAINS with
  conservation constraints (each tracklet has in<=1, out<=1) and naturally
  supports source/sink nodes for births/exits. Offline batch version is easy
  with scipy (min-cost flow via linear_sum_assignment on chained pairs is NOT
  equivalent - need true flow; use scipy.sparse.csgraph or networkx).

### A4. Tracking Intermittent Particles with Self-Learned Visual Features
[2607.09829] (fluorescence microscopy)
- Single-particle tracking under occlusion/intermittent detectability; same
  mathematical structure as identical-ball juggling (indistinguishable objects,
  fragmentation, gap linking).
- Verdict: closest cross-domain analogue found. Their self-learned appearance
  features are an option if we ever need appearance on identical balls (probably
  not useful - truly identical). Their gap-linking evaluation protocol is worth
  borrowing.

### A5. Human-robot juggling perception line (Ploeger/Peters group)
- "Catch, Throw, Repeat" [2607.15129], "Controlling the Cascade" [2207.01414],
  "Beyond the Cascade" [2410.19591], high-acceleration RL juggling [2010.13483].
- Verdict: robotic juggling works assume ballistic flight + contact events;
  confirms our state-machine framing (AIRBORNE/HELD/THROW_CANDIDATE). Their
  event-triggered planners mirror our P5 hand-event layer.

## B. Background / partially relevant

### B1. PMBM filters on sets of tree trajectories [2111.05620 and relatives]
- Random-finite-set tracking with explicit birth/spawn; trajectories as trees.
- Verdict: principled alternative to our heuristic hypotheses; heavyweight
  math, no public juggle-ready implementation found. Keep as theory anchor:
  our "tracklet stitching" = their trajectory-set inference in miniature.

### B2. GNN ranked assignment in delta-GLMB [2604.01696]
- Learned solver for ranked assignment inside GLMB truncation.
- Verdict: interesting but aimed at online automotive; our offline label set is
  too small to train GNN solvers.

### B3. Ball 3D localization from single calibrated image [2204.00003]; soccer
ball trajectory reconstruction [2506.07981]; TT3D [2504.10035]; BlurBall
[2509.18387].
- Sports-broadcast ball tracking: multi-mode ballistic state models, blur-aware
  labeling, physics-constrained optimization.
- Verdict: BlurBall's insight (motion-blur direction encodes velocity) could
  upgrade OUR detector features later; soccer multi-mode ballistic estimation
  parallels our gravity-mode discovery (E3c).

### B4. Shadowing filter for unknown accelerations [1502.07743]
- Tracking when acceleration is unknown/unbounded (non-ballistic phases).
- Verdict: relevant exactly at hand-contact intervals; supports switching-model
  idea: ballistic in air, near-zero-dynamics while held.

### B5. Gravity-aware monocular human-object reconstruction [2108.08844]
- Uses known g as prior for 3D from monocular video.
- Verdict: supports shared-gravity priors; we showed fixed-g adds nothing at
  short horizons (E3) but regime segmentation matters (E3c).

## C. Negative / not pursued
- SAR "juggling" papers, vehicle MTMC TrackNet [2205.13857], traffic TrackNet
  [1902.01466], UAV observer-follower trackers, polyhedral offline 3D MOT
  [2602.13772]: different problem shapes (appearance-rich, 3D, lidar).

## D. Decisions for next experiments
1. E6 (implement now): min-cost-flow CHAIN stitching over Norfair tracklets with
   ballistic costs (bal8), gate, per-regime cost scaling using E3c timeline;
   evaluate chains against the 113 labels (chain-level precision/recall vs
   greedy/global baselines from E2).
2. Detector path (later, needs data): fine-tune TrackNetV4/V5-class heatmap
   model on self-labeled juggling clips to attack P6 at the source.
3. Event layer (E7): switch model AIRBORNE(ballistic)/HELD(zero-dynamics) with
   wrists from pose CSVs; borrow shadowing-filter spirit for non-ballistic
   phases.
