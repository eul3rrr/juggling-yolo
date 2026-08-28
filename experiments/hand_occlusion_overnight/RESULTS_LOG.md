# Hand Occlusion Overnight Lab — Results Log

Each result entry should be a self-contained record. Negative results are first-class.

Suggested fields per entry (adapt as needed):

- Experiment ID (e.g. H1, H2, H1.1, L1)
- Date / time (CEST)
- Worker session ID
- Branch / commit
- Hypothesis
- Setup (script, parameters, grid, video)
- Outputs (paths, counts, headline numbers)
- Visual QA verdicts
- Conclusion (clean, mixed, or negative)
- Follow-up

---

## H0 — Bootstrap (no experiment, just setup)

- Date: 2026-08-28 ~02:55 CEST
- Branch: `experiments/hand-occlusion-overnight` @ `2ddf422` base
- Worktree: `/home/it-admin/projects/juggling-yolo-hand-occlusion-night`
- Profile: `juggling-tracker`
- Model: `minimax/minimax-m3:free`
- Reasoning: `ultra` (per-model override + `--reasoning` flag)
- Watchdog: implemented and launching detached
- STOP sentinel: `experiments/hand_occlusion_overnight/STOP` (not yet created)
- Conclusion: setup complete; no research result yet.
