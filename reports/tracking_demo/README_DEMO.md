# Tracking Reconstruction Review Demo

This is an offline, vanilla HTML/CSS/JavaScript comparison of the frozen pre-overnight E6c reconstruction and hand-aware reconstructions.

## Launch

From the repository root:

    reports/tracking_demo/serve_demo.sh

Open http://127.0.0.1:8765/ in a browser.

The demo uses two synchronized `<video>` panels and JSON overlays. The source videos are intentionally not committed. On this machine they are symlinked from:

`/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/videos/`

If the symlinks are broken on another machine, place the two MP4 files at `reports/tracking_demo/assets/` with the filenames already present there.

## Controls

- Shared play/pause, scrubber, frame/time, and 0.25x/0.5x/1x speed.
- Previous/next difference buttons.
- Space = play/pause; J/K = previous/next frame; arrows = previous/next difference; 1/2/3 = overview/selected chain/what changed.
- WHAT CHANGED is the default. OVERVIEW, SELECTED CHAIN, H125 CANDIDATE PROPOSALS, FAILURE GALLERY, and SUMMARY are separate views.
- Click an event marker/card to pause, jump before the event, select it, and open details. Click a contact strip to enlarge it.

AUTO is the default new reconstruction. RESEARCH-TUNED is visibly marked as development-video informed. H125 is never drawn as a coherent chain.

See CODE_AUDIT.md for source-grounded interpretation and DEMO_NOTES.md for limitations.
