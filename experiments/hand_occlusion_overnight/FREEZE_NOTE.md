# Overnight Research Freeze

- Freeze requested: 2026-08-29 02:15 CEST.
- Research branch: `experiments/hand-occlusion-overnight`.
- Pre-freeze committed HEAD: `01f80dc8620b72b0884bc813d8b7e6e4253bec85` (H126).
- The STOP sentinel is intentionally permanent at `experiments/hand_occlusion_overnight/STOP`.
- The watchdog observed STOP, SIGTERM'd the active worker, waited its grace period, and exited cleanly at 02:16:40 CEST.
- No new research episode may start while STOP exists. Do not remove STOP or restart the watchdog.
- H127 work was interrupted and remains uncommitted/untouched for forensic preservation; it is not part of the frozen evidence basis.
- This freeze commit is the immutable research basis for the review/demo branch.
