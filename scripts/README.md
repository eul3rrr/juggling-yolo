# Code guide

The frozen demo follows the path below. Each stage consumes explicit CSV inputs; the renderer does not make association decisions.

## Demonstrated pipeline

| Stage | Entry point | Role |
| --- | --- | --- |
| Ball detection | [detect_video.py](detect_video.py) | YOLO sports-ball detections in original-image coordinates |
| Local tracking | [track_norfair.py](track_norfair.py) | Local track IDs and observed/predicted state separation |
| Pose extraction | [analyze_stitch_features.py](analyze_stitch_features.py) (`pose`) | Pose keypoints, including anatomical wrists |
| Boundary features | [hand_boundaries.py](hand_boundaries.py) | Observed track endpoints and wrist-relative features |
| Hand events | [hand_events.py](hand_events.py) | Classify entry/exit events at those boundaries |
| Association | [hand_state_machine.py](hand_state_machine.py) | Pending-hand state and compatible tracklet associations |
| Visualization | [render_demo_videos.py](render_demo_videos.py) | Read saved decisions, construct HID groups, render the three views and GIF previews |

Start with [hand-repair reproduction](../docs/HAND_REPRODUCTION.md) for the exact frozen inputs, producer provenance, commands, and regression checks. The hand modules were published from the implementation that produced the demo artifacts; this cleanup does not revise their thresholds or association rules.

For a single command, [reproduce_demo_hand.py](reproduce_demo_hand.py) runs the frozen boundary/event/state stages into an empty output directory and checks all three CSVs against the snapshot. It uses the restored augmented pose fixture, not the renderer's wrist-only CSV.

The original support modules [hand_association.py](hand_association.py), [hand_features.py](hand_features.py), and [hand_overlay.py](hand_overlay.py) provide configuration, loading, and geometry helpers used by the boundary stage. They are kept intact for provenance; their older high-level association code is not the FIFO decision path shown here.

HID construction is in `build_hid_mapping()` in the renderer. It groups accepted links; it is not a second association algorithm or a ground-truth evaluator.

## Earlier baseline and review tools

These remain available for research and compatibility, but are not additional steps needed to produce the frozen hand demo:

- [track_video.py](track_video.py): ByteTrack / BoT-SORT comparison.
- [stitch_tracklets.py](stitch_tracklets.py): earlier motion-based candidate ranking.
- [review_stitches.py](review_stitches.py): manual review of proposed stitches.
- [analyze_stitch_features.py](analyze_stitch_features.py) (`enrich`): feature analysis of reviewed hypotheses.
- [reconstruct_stitched_video.py](reconstruct_stitched_video.py): earlier reconstruction visualization.

Their commands are in [baseline usage](../docs/BASELINES.md). Exploratory implementations and their reports are in [the research archive](../archive/README.md), separate from the demonstrated hand pipeline.

## Development boundary

Run the tests before changing behavior. Keep raw observations, inferred associations, and display overlays distinguishable. Treat frozen CSVs as regression fixtures, not editable answers to make a changed algorithm pass. Source clips and generated output directories are local; do not add weights or new videos as part of routine code changes.
