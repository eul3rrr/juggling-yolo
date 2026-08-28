# Trajectory viewer visual QA notes

This file records visual QA observations only. No E6c assignment, threshold, prediction, or stitching methodology was changed.

## Rendering checks

- Both contact sheets show repeated three-panel event rows with native-aspect video panels.
- The observed portions use solid colored trails and small filled raw detector-center dots; the current observed point is larger.
- Missing portions use dashed ballistic curves without fake detector-point dots.
- Gap endpoints are marked with hollow circles. Long gaps show compact `gap Nf` labels, and the normal overlay uses `T#` trajectory labels rather than physical ball identities.
- The legend now visibly reads `Observed = solid • Inferred = dashed`, with `frame N` beneath it.
- The translucent bands are intentionally broad at long gaps because they use the prescribed synthetic-cut q90 display scale. They are not confidence intervals.
- The generated H.264 videos retain source dimensions and FPS and are browser-playable from the local HTML page.
- The contact sheets did not show a stretched panel or an obvious renderer artifact.

## Candidates for human inspection

These are not fixes or judgments; they are selected because the long-gap envelope or hand marker makes them informative to inspect in the viewer:

- Identical-balls: `T2`, source tracklet 2 -> successor 8, frames 17–43, gap 25f, normalized error 0.97, marked `HAND ?`.
- Identical-balls: `T18`, source tracklet 42 -> successor 44, frames 598–623, gap 24f, normalized error 0.30, marked `HAND ?`.
- Identical-balls: `T14`, source tracklet 27 -> successor 28, frames 312–333, gap 20f, normalized error 0.06.
- YouTube: `T9`, source tracklet 11 -> successor 15, frames 299–329, gap 29f, normalized error 0.24, marked `HAND ?`.
- YouTube: `T5`, source tracklet 12 -> successor 16, frames 309–339, gap 29f, normalized error 0.29, marked `HAND ?`.
- YouTube: `T8`, source tracklet 10 -> successor 13, frames 238–267, gap 28f, normalized error 0.53, marked `HAND ?`.

The viewer intentionally retains all of these accepted E6c links, including the hand-adjacent and high-envelope cases, for human review.
