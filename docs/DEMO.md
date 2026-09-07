# Frozen demonstration

This snapshot records the hand-repair pipeline shown in the README. It is a demonstration of the current implementation, not a claim that all ball identities are recovered. Later algorithm development should be evaluated separately before replacing it.

## What is frozen

- Source: `videos/identical_balls_trick_000_018.mp4` (local, not distributed).
- Detector: YOLO26l sports-ball detections, not the YOLO26s baseline in the historical quick start.
- Tracker: the matching Norfair `dt50_hc5` tracklets.
- Renderer pose: `detections/identical_balls_trick_000_018_yolo26s-pose.csv` (wrist overlay input).
- Hand-producer pose: `tests/fixtures/demo_hand/identical_balls_trick_000_018_yolo26s-pose-hands.csv` (the original augmented pose features). These inputs are not interchangeable; see the hand reproduction guide.
- Hand decisions: the association, event, and state-trace CSVs in `detections/demo/`.
- Full videos: the three `docs/assets/demo-*.mp4` files introduced in commit `3eabefe236f6304cc0cad3834ed513561b792719`.
- GIF previews: the matching four-second excerpts from commit `933abfb6648af4fd25cb8cfcee1c9c75284ab0c9`.

The [manifest](demo-manifest.json) records SHA-256 hashes for the inputs, source, and media. The [hand reproduction guide](HAND_REPRODUCTION.md) records the producer implementation and verifies its saved decisions. Source and media bytes are not changed by this documentation/code-publication cleanup.

## Reading the comparison

1. **Local tracking:** YOLO boxes, local `T#`, and observed trails. Identity fragmentation stays visible.
2. **Hand stitching:** local `T#`, wrists, pending-hand state, and thick dashed association bridges. The bridges are graphical connections, not fitted ball paths.
3. **Reconstructed identity:** accepted links share an HID and color; local IDs and boxes are hidden.

In the full clip, the accepted chains are `T1 → T5 → T10`, `T2 → T11`, and `T3 → T4 → T6 → T13`. Other tracklets remain unconnected. There are 14 local tracklets, six links, and eight HID components. These counts describe the artifacts, not association accuracy.

The short preview includes the first three associations. Watch near the end for `T1 → T5` and `T4 → T6`; their HID colors stay consistent in the final view. GIFs share source frames but GitHub does not synchronize playback. Click an image for its MP4 and native playback controls.

## Media settings

| | GIF previews | Full MP4s |
| --- | --- | --- |
| Source interval | Frames 0–239 inclusive | Frames 0–1078 inclusive |
| Dimensions | 560 × 316 | 1280 × 720 |
| Playback | 10 fps, 40 frames, 4 seconds | 60000/1001 fps, 1079 frames, 18.001317 seconds |
| Encoding | Palette-optimized, infinite loop | H.264, yuv420p, faststart, no audio |

| Stage | GIF bytes | MP4 bytes |
| --- | ---: | ---: |
| Local tracking | 3,294,288 | 3,370,194 |
| Hand stitching | 3,228,222 | 3,065,221 |
| Reconstructed identity | 3,209,488 | 2,919,839 |

JPG posters are retained for the optional static viewer. All three views use the same source, crop, timing, and resolution within each format.

## Regenerate without changing the checkpoint

Install the [dependencies](SETUP.md) and `ffmpeg`, then run from the repository root.

GIFs only, from the existing MP4s (no inference or source footage needed):

```bash
.venv/bin/python scripts/render_demo_videos.py --gif-only
```

Full videos and GIFs, requiring the original local source clip and the committed canonical CSVs:

```bash
.venv/bin/python scripts/render_demo_videos.py --output-dir /tmp/juggling-demo-render
```

The second command writes outside the frozen asset directory. The renderer reads saved hand decisions; it does not run the hand classifier. To regenerate those decisions separately, use [hand-repair reproduction](HAND_REPRODUCTION.md).

## Known limits

HID is an offline reconstructed identity, not a guaranteed physical identity. Detector false positives and unresolved fragments remain. A historical trail endpoint may remain briefly visible after a track ends; it should not be read as a new observation. This cleanup deliberately preserves the reviewed renderer and media rather than changing tracking or display logic.

Source footage is not included. Its filename is not an attribution or redistribution license. Confirm the original footage's attribution and reuse permission before redistributing it elsewhere; the intended replacement is the project author's own footage. No new license grant for third-party media is implied here.

## Replacing the source later

1. Use footage you own or have permission to publish; record its origin and hash.
2. Generate matching detections, Norfair tracklets, and pose for that clip. Do not mix YOLO26s and YOLO26l artifact families.
3. Run the hand stages on those inputs with explicit output paths and review their associations.
4. Pass the new `--video`, `--detections`, `--tracklets`, `--pose`, `--associations`, `--events`, and `--state-trace` paths to `scripts/render_demo_videos.py`. Render into a separate `--output-dir` first.
5. Select one shared interval using `--gif-start-frame`, `--gif-end-frame` (exclusive), `--gif-fps`, and `--gif-width`.
6. Check timing, labels, links, and sizes, then intentionally replace the frozen assets and update the manifest, counts, and viewing cues together.

Do not overwrite canonical CSVs just to accommodate a new algorithm. Preserve this checkpoint in Git and publish a new snapshot only after review.
