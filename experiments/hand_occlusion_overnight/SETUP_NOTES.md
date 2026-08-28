# Setup Notes — Hand Occlusion Overnight Lab

## Setup timestamp
2026-08-28 03:23 CEST (bootstrap re-verification: corrected from earlier `minimax/minimax-m3:free` → `MiniMaxAI/MiniMax-M3` direct GMI).

## Branch / worktree
- Branch: `experiments/hand-occlusion-overnight`
- Worktree absolute path: `/home/it-admin/projects/juggling-yolo-hand-occlusion-night`
- Base commit: `2ddf422` on `main` ("experiment: E15 detector headroom — dropouts are threshold+association, not blindness")
- Upstream: `origin/experiments/hand-occlusion-overnight` (pushed at bootstrap)

## Stop sentinel (authoritative clean stop)
- Absolute path: `/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/STOP`
- To stop the lab: `touch /home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/STOP`
- The watchdog detects the sentinel at the top of every loop and exits cleanly.
- Workers detect the sentinel at the top of every new experiment and exit cleanly.
- Do not delete the STOP file.

## Direct GMI configuration (the critical fix in this bootstrap)
- Provider name in Hermes: `gmi`
- Base URL (Hermes config): `https://api.gmi-serving.com/v1`
- **Exact GMI MiniMax M3 model ID**: `MiniMaxAI/MiniMax-M3`
- One-shot verification (2026-08-28 03:18 CEST):
  - command: `hermes chat -p juggling-tracker -m MiniMaxAI/MiniMax-M3 --provider gmi --reasoning ultra -q "Reply with exactly the single word: GMI_OK" --quiet --no-restore-cwd`
  - reply: `GMI_OK`
  - session_id: `20260828_031850_9a5c7d`
  - provider: `gmi` (verified; OpenRouter NOT used; no auto-selection fallback)
- `GMI_API_KEY` is set in `/home/it-admin/.hermes/profiles/juggling-tracker/.env`; Hermes reads it automatically; no further changes required.
- `https://api.gmi-serving.com/v1/models` and `…/chat/completions` reject direct curl with Cloudflare 1010 (browser-only), but Hermes' own OpenAI-compatible client works fine — confirmed end-to-end.
- OpenRouter is configured in the same profile but is **not** used by the overnight workers.

## Reasoning configuration (`ultra`)
- Mechanism: per-model override keyed to the exact GMI model.
- File: `/home/it-admin/.hermes/profiles/juggling-tracker/config.yaml`
- Block:
  ```yaml
  agent:
    max_turns: 150
    reasoning_overrides:
      "MiniMaxAI/MiniMax-M3": ultra
  ```
- Belt-and-braces: watchdog also passes `--reasoning ultra` on every `hermes chat` invocation.
- Verification: `hermes config get agent.reasoning_overrides` → `{'MiniMaxAI/MiniMax-M3': 'ultra'}`.
- Earlier wrong key `minimax/minimax-m3:free` (an OpenRouter alias) was replaced. The change is scoped to this one model; no other models' reasoning is changed.
- Backup of pre-edit config: `config.yaml.bak.20260828_032242` (in the same profile directory).

## Watchdog
- Script: `experiments/hand_occlusion_overnight/watchdog.sh`
- PID file: `experiments/hand_occlusion_overnight/watchdog.pid`
- Lock dir: `experiments/hand_occlusion_overnight/watchdog.lock` (mkdir-based, mutex via mkdir(2))
- Log: `experiments/hand_occlusion_overnight/watchdog.log`
- Launched detached from this bootstrap terminal via `setsid + nohup` with stdin closed and stdout/stderr redirected.
- Survives terminal close.
- Lock acquisition is via `mkdir` (atomic on POSIX); duplicate invocations exit 0 silently.

## Worker invocation
- Hermes executable: `/home/it-admin/.local/bin/hermes`
- Profile: `juggling-tracker`
- **Provider**: `gmi` (explicit, never auto)
- **Model**: `MiniMaxAI/MiniMax-M3`
- Reasoning: `--reasoning ultra` plus per-model override `agent.reasoning_overrides["MiniMaxAI/MiniMax-M3"] = "ultra"`
- Continuation prompt file: `experiments/hand_occlusion_overnight/worker_prompt.txt`
- Episode cap: 4500s (75 min) wall-clock; graceful SIGTERM, then SIGKILL after 45s.
- One worker at a time; single-instance lock prevents duplicates.
- CPU/disk throttling: `nice -n 10 ionice -c2 -n7`.
- If `systemd-run --user --scope` is available, worker is wrapped in a transient scope with `MemoryHigh=4G`, `MemoryMax=6G`, `MemorySwapMax=2G`; otherwise throttling-only.

## Memory protection
- Preflight: `MemAvailable >= 3072 MiB` AND `SwapFree >= 768 MiB`; otherwise wait 60s and re-check.
- While worker runs: poll `/proc/meminfo` every 30s; if `MemAvailable < 1536 MiB` OR `SwapFree < 256 MiB`, send SIGTERM to worker process group, then SIGKILL after grace, then wait for memory to recover before next launch.
- After abnormal exit, sniff dmesg for OOM signatures; if present, use a long cooldown (10 min).
- Never kill unrelated processes; only the worker's process group.
- The watchdog also pre-allocates a `MemoryHigh=4G / MemoryMax=6G / MemorySwapMax=2G` user transient systemd scope when the system supports it.

## Restart policy
- Normal exit (or 75-min budget expiry): sleep ~25s, then start a new episode.
- Abnormal exit: sleep ~2 min, then retry.
- 3+ abnormal exits in a row: back off ~10 min, then continue.
- Provider rate limits / network failures: increasing cooldowns, never permanent stop.
- "No-progress" episodes (HEAD unchanged AND STATE.md mtime unchanged) are logged, not punished.

## Watchdog destructive-command audit
The watchdog NEVER executes:
- `git reset --hard`
- `git clean -fd` (or any variant)
- automatic `git stash drop`
- automatic branch rewrite
- anything that touches production code or `experiments/overnight/`

## Setup commit(s)
- Bootstrap H0 commit (earlier): `5f69f25` — "experiment: bootstrap hand-occlusion overnight lab (H0 setup)"
- This bootstrap fixup: pending — adds the corrected `watchdog.sh` and refreshed `STATE.md` / `SETUP_NOTES.md` / `RESULTS_LOG.md`.
