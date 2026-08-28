# Setup Notes — Hand Occlusion Overnight Lab

## Branch / worktree

- Branch: `experiments/hand-occlusion-overnight`
- Worktree absolute path: `/home/it-admin/projects/juggling-yolo-hand-occlusion-night`
- Base commit: `2ddf422` on `main`
- Upstream: `origin/experiments/hand-occlusion-overnight` (pushed at bootstrap)

## Stop sentinel (authoritative clean stop)

- Absolute path: `/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/STOP`
- To stop the lab: `touch /home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/STOP`
- The watchdog detects the sentinel at the top of every loop and exits cleanly.
- Workers detect the sentinel at the top of every new experiment and exit cleanly.
- Do not delete the STOP file.

## Profile config change

- Profile config file: `/home/it-admin/.hermes/profiles/juggling-tracker/config.yaml`
- Backup before edit: `config.yaml.bak.<bootstrap_timestamp>`
- Change: added `reasoning_overrides` under `agent:` (a new sub-key, not overwriting the existing `agent:` block):

```yaml
agent:
  max_turns: 150
  reasoning_overrides:
    "minimax/minimax-m3:free": "ultra"
```

- The existing `max_turns: 150` line is preserved unchanged.
- No other models' reasoning is changed.
- The watchdog also passes `--reasoning ultra` explicitly on every `hermes chat` invocation.

## Watchdog

- Watchdog script: `/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/watchdog.sh`
- Watchdog PID file: `/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/watchdog.pid`
- Watchdog lock dir: `/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/watchdog.lock`
- Watchdog log: `/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/watchdog.log`
- Launched detached from this bootstrap terminal via `setsid + nohup` and stdin closed.
- Survives terminal close.

## Worker invocation

- Hermes executable: `/home/it-admin/.local/bin/hermes`
- Profile: `juggling-tracker`
- Model: `minimax/minimax-m3:free`
- Reasoning flag: `--reasoning ultra` (and per-model override above as belt-and-braces)
- Continuation prompt file: `experiments/hand_occlusion_overnight/worker_prompt.txt`
- Episode cap: 75 minutes wall-clock; graceful SIGTERM, then SIGKILL after 45s.
- One worker at a time; single-instance lock prevents duplicates.
- CPU/disk throttling: `nice -n 10 ionice -c2 -n7`.

## Memory protection

- Preflight: MemAvailable >= 3 GiB AND SwapFree >= 768 MiB; otherwise wait 60s.
- While running: poll every 30s; if MemAvailable < 1.5 GiB or SwapFree < 256 MiB,
  gracefully terminate the worker (its process group), then wait for recovery.
- If `systemd-run --user --scope` is available, use a transient scope with
  MemoryHigh=4G, MemoryMax=6G, MemorySwapMax=2G; otherwise fall back to polling.
- After abnormal exit, check dmesg/syslog for OOM signatures; if present, use a long cooldown.

## Restart policy

- Normal exit: sleep ~25s, then start a new episode.
- Abnormal exit: sleep ~2 min, then retry.
- 3+ abnormal exits in a row: back off ~10 min, then continue.
- Provider rate limits / network failures: increasing cooldowns, never permanent stop.

## Setup commit

Recorded after the first push of the bootstrap files. See git log of the new branch.
