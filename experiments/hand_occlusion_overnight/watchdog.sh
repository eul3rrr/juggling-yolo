#!/usr/bin/env bash
# Watchdog for the autonomous hand-occlusion overnight research lab.
#
# Responsibilities:
#   - Single-instance protection via flock.
#   - STOP sentinel detection at /home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight/STOP
#   - Memory preflight: wait for MemAvailable >= 3 GiB AND SwapFree >= 768 MiB.
#   - One research worker at a time, fresh one-shot Hermes session per episode.
#   - Per-episode wall-clock cap (~75 min) with graceful then hard kill.
#   - In-episode memory guard: poll every ~30s, terminate worker if system
#     enters a critical memory zone.
#   - Low scheduling priority (nice + ionice).
#   - Optional transient systemd user scope with conservative memory limits.
#   - OOM-aware restart backoff.
#   - Append-only logging to watchdog.log.
#   - Robust PID + lock handling.
#   - Never touches production, never resets dirty work, never deletes STOP.
#
# This watchdog does NOT perform research itself; it only orchestrates workers.

set -u

LAB_DIR="/home/it-admin/projects/juggling-yolo-hand-occlusion-night/experiments/hand_occlusion_overnight"
LOCK_DIR="$LAB_DIR/watchdog.lock"
PID_FILE="$LAB_DIR/watchdog.pid"
LOG_FILE="$LAB_DIR/watchdog.log"
STOP_FILE="$LAB_DIR/STOP"
WORKER_PROMPT_FILE="$LAB_DIR/worker_prompt.txt"

HERMES="/home/it-admin/.local/bin/hermes"
HERMES_PY="/home/it-admin/.hermes/hermes-agent/venv/bin/python"
HERMES_BIN="/home/it-admin/.hermes/hermes-agent/hermes"
PROFILE="juggling-tracker"
PROVIDER="gmi"
MODEL="MiniMaxAI/MiniMax-M3"

EPISODE_BUDGET_SECONDS=4500   # 75 minutes per worker episode
GRACE_BEFORE_KILL=45         # seconds between SIGTERM and SIGKILL
MEM_POLL_INTERVAL=30         # seconds between in-episode memory checks

# Preflight thresholds
MIN_MEM_AVAIL_MIB=3072       # 3 GiB
MIN_SWAP_FREE_MIB=768        # 768 MiB

# Critical in-episode thresholds
CRIT_MEM_AVAIL_MIB=1536      # 1.5 GiB
CRIT_SWAP_FREE_MIB=256       # 256 MiB

# Cooldowns
NORMAL_COOLDOWN=25
ABNORMAL_COOLDOWN=120
ABNORMAL_STREAK_LONG_COOLDOWN=600
ABNORMAL_STREAK_TRIGGER=3

log() { echo "[ $(date '+%F %T') ] $*" >> "$LOG_FILE"; }

# --- Single-instance lock ---------------------------------------------------
# Try to acquire the lock; if another watchdog owns it, exit quietly.
acquire_lock() {
    if ! mkdir "$LOCK_DIR" 2>/dev/null; then
        log "another watchdog already owns $LOCK_DIR; exiting."
        exit 0
    fi
    echo $$ > "$PID_FILE"
    trap 'rm -f "$PID_FILE"; rmdir "$LOCK_DIR" 2>/dev/null' EXIT
}

# --- Helpers -----------------------------------------------------------------
meminfo_field() {
    # $1: name (e.g. MemAvailable)
    # Use grep + awk to avoid awk-v-variable quoting issues across shells.
    grep -E "^${1}:" /proc/meminfo 2>/dev/null | awk '{print $2; exit}'
}

# Returns 0 if memory preflight passes; 1 otherwise.
preflight_ok() {
    local avail swap_free
    avail=$(meminfo_field MemAvailable)
    swap_free=$(meminfo_field SwapFree)
    [ -z "$avail" ] && avail=0
    [ -z "$swap_free" ] && swap_free=0
    if [ "$avail" -ge "$MIN_MEM_AVAIL_MIB" ] && [ "$swap_free" -ge "$MIN_SWAP_FREE_MIB" ]; then
        return 0
    fi
    log "preflight not met: MemAvailable=${avail} KiB, SwapFree=${swap_free} KiB; waiting 60s."
    return 1
}

# --- Worker launch -----------------------------------------------------------
# Returns 0 if a worker was launched and exited normally.
# Returns 1 if worker exited abnormally (or preflight failed and we bailed).
# Returns 2 if STOP was detected before launch.
# Returns 3 if a fresh worker is still running on entry (defensive).

is_worker_alive() {
    # pgrep on the distinctive combination of flags we always pass.
    # Match the actual provider+model+--in flags (escaped for the regex).
    local pat="hermes chat.*-p ${PROFILE}.*--provider ${PROVIDER}.*--model ${MODEL}.*--in .*--query-file ${WORKER_PROMPT_FILE}"
    pgrep -f -- "$pat" >/dev/null 2>&1
}

# Build the hermes command line. Echoes a single command line ready to be eval'd
# inside a transient systemd scope if available. Uses --query-file and
# --reasoning ultra; the per-model override is also configured in config.yaml.
# --in $worktree_root pins the worker's cwd regardless of how the watchdog was
# launched, so file-relative paths in worker_prompt.txt resolve correctly.
build_hermes_cmd() {
    local worktree_root
    worktree_root=$(git -C "$LAB_DIR" rev-parse --show-toplevel 2>/dev/null || echo "/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
    printf "%s chat -p %s --provider %s --model %s --reasoning ultra --in %s --query-file %s --no-restore-cwd --accept-hooks --yolo --pass-session-id" \
        "$HERMES" "$PROFILE" "$PROVIDER" "$MODEL" "$worktree_root" "$WORKER_PROMPT_FILE"
}

run_one_episode() {
    # Returns:
    #   0 normal exit
    #   1 abnormal exit
    #   2 STOP detected mid-episode
    local rc_normal=0
    local worker_pid
    local cmd
    cmd=$(build_hermes_cmd)

    log "episode: starting fresh MiniMax worker"
    log "episode: command => hermes chat -p ${PROFILE} --provider ${PROVIDER} --model ${MODEL} --reasoning ultra --in <worktree_root> --query-file ${WORKER_PROMPT_FILE} (provider=${PROVIDER}, per-model override ${MODEL}=ultra)"

    # Use systemd-run user scope if available (best effort, conservative limits).
    local pre_cmd=""
    if [ "${SYSTEMD_SCOPE_USABLE:-0}" = "1" ]; then
        pre_cmd="systemd-run --user --scope --quiet -p MemoryHigh=4G -p MemoryMax=6G -p MemorySwapMax=2G"
        log "episode: launching inside transient systemd user scope (MemoryHigh=4G, MemoryMax=6G, MemorySwapMax=2G)"
    else
        log "episode: systemd-run --user --scope not usable; using nice + ionice only"
    fi

    # Launch the worker; capture PID via $! of the systemd-run wrapper or of nice.
    # We always run in background, then monitor.
    # build_hermes_cmd pins the worker's cwd via --in <worktree_root>, so we
    # don't strictly need a cd here. We still cd for the watchdog-side checks
    # (HEAD, STATE.md mtime) and for any preflight that wants to be in the
    # worktree.
    local worktree_root
    worktree_root=$(git -C "$LAB_DIR" rev-parse --show-toplevel 2>/dev/null || echo "/home/it-admin/projects/juggling-yolo-hand-occlusion-night")
    local wrapped_cmd="nice -n 10 ionice -c2 -n7 $pre_cmd bash -c 'cd $worktree_root && exec $cmd'"

    # We want the actual worker PID for monitoring. systemd-run --scope doesn't
    # return a useful $! because the scope itself forks; instead we use pgrep in
    # the monitor loop. But we still want a process-group reference for kill.
    # Strategy: use setsid so the whole tree has its own pgid, then kill -<pgid>.
    setsid bash -c "$wrapped_cmd" </dev/null >>"$LOG_FILE" 2>&1 &
    worker_pid=$!
    log "episode: launched wrapper pid=${worker_pid}"

    # Monitor loop
    local elapsed=0
    local last_poll=0
    while kill -0 "$worker_pid" 2>/dev/null; do
        # STOP check
        if [ -f "$STOP_FILE" ]; then
            log "episode: STOP detected; sending SIGTERM to pgid of pid=${worker_pid}"
            kill -TERM -- -"$worker_pid" 2>/dev/null || kill -TERM "$worker_pid" 2>/dev/null
            sleep "$GRACE_BEFORE_KILL"
            kill -KILL -- -"$worker_pid" 2>/dev/null || kill -KILL "$worker_pid" 2>/dev/null
            wait "$worker_pid" 2>/dev/null
            return 2
        fi

        # In-episode memory guard
        if [ $((elapsed - last_poll)) -ge "$MEM_POLL_INTERVAL" ]; then
            last_poll=$elapsed
            local avail swap_free
            avail=$(meminfo_field MemAvailable)
            swap_free=$(meminfo_field SwapFree)
            [ -z "$avail" ] && avail=0
            [ -z "$swap_free" ] && swap_free=0
            if [ "$avail" -lt "$CRIT_MEM_AVAIL_MIB" ] || [ "$swap_free" -lt "$CRIT_SWAP_FREE_MIB" ]; then
                log "episode: critical memory zone (MemAvailable=${avail} KiB, SwapFree=${swap_free} KiB); terminating worker"
                kill -TERM -- -"$worker_pid" 2>/dev/null || kill -TERM "$worker_pid" 2>/dev/null
                sleep "$GRACE_BEFORE_KILL"
                kill -KILL -- -"$worker_pid" 2>/dev/null || kill -KILL "$worker_pid" 2>/dev/null
                wait "$worker_pid" 2>/dev/null
                log "episode: OOM-EMERGENCY termination complete; will wait for memory recovery before next episode"
                return 1
            fi
        fi

        # Episode budget
        if [ "$elapsed" -ge "$EPISODE_BUDGET_SECONDS" ]; then
            log "episode: budget ${EPISODE_BUDGET_SECONDS}s reached; sending SIGTERM"
            kill -TERM -- -"$worker_pid" 2>/dev/null || kill -TERM "$worker_pid" 2>/dev/null
            sleep "$GRACE_BEFORE_KILL"
            kill -KILL -- -"$worker_pid" 2>/dev/null || kill -KILL "$worker_pid" 2>/dev/null
            wait "$worker_pid" 2>/dev/null
            log "episode: budget-termination complete (graceful SIGTERM then SIGKILL)"
            # Budget expiry is treated as a normal episode end: the agent had
            # plenty of time to checkpoint per MASTER_INSTRUCTIONS §21.
            return 0
        fi

        sleep 5
        elapsed=$((elapsed + 5))
    done

    # Worker exited on its own
    wait "$worker_pid" 2>/dev/null
    local exit_code=$?
    log "episode: worker exited with code=${exit_code} after ${elapsed}s"
    if [ "$exit_code" -eq 0 ]; then
        return 0
    fi
    return 1
}

# --- Main loop ---------------------------------------------------------------
main() {
    mkdir -p "$LAB_DIR" 2>/dev/null || true
    : >/dev/null
    log "=== watchdog starting (pid $$), episode_budget=${EPISODE_BUDGET_SECONDS}s ==="
    log "model=${MODEL} provider=${PROVIDER} profile=${PROFILE} hermes=${HERMES}"
    log "lab_dir=${LAB_DIR}"

    # Probe systemd-run --user --scope ONCE; cache the result for the lifetime of
    # this watchdog. The probe creates and immediately exits a transient scope
    # named "watchdog-scope-probe" to confirm the user systemd manager is alive.
    if systemd-run --user --scope --unit=watchdog-scope-probe -- true </dev/null >/dev/null 2>&1; then
        export SYSTEMD_SCOPE_USABLE=1
        log "systemd-run --user --scope is usable; workers will run inside a transient cgroup memory scope"
    else
        export SYSTEMD_SCOPE_USABLE=0
        log "systemd-run --user --scope is NOT usable; workers will use nice + ionice only"
    fi

    # Defensive: if a worker is already running, do not double-launch.
    if is_worker_alive; then
        log "a worker is already running on entry; watchdog will monitor rather than launch another"
    fi

    local consecutive_abnormal=0
    local first_iteration=1

    while true; do
        if [ -f "$STOP_FILE" ]; then
            log "STOP file detected -> watchdog exiting cleanly"
            exit 0
        fi

        # Preflight: wait for memory
        if ! preflight_ok; then
            sleep 60
            continue
        fi

        # If a worker is already running from a prior iteration, monitor rather than launch.
        if [ "$first_iteration" -eq 1 ] && is_worker_alive; then
            log "defensive: existing worker detected; will not launch a duplicate"
            sleep 30
            first_iteration=0
            continue
        fi

        # Optional progress guard: capture HEAD before for later NO_PROGRESS_EPISODE check.
        local head_before
        head_before=$(git -C "$LAB_DIR/../.." rev-parse HEAD 2>/dev/null || echo unknown)
        local state_mtime_before
        state_mtime_before=$(stat -c %Y "$LAB_DIR/STATE.md" 2>/dev/null || echo 0)

        run_one_episode
        local rc=$?
        case "$rc" in
            0)
                # Normal (or budget-expiry) exit
                consecutive_abnormal=0
                log "post-episode: normal end; cooldown ${NORMAL_COOLDOWN}s"
                sleep "$NORMAL_COOLDOWN"
                ;;
            1)
                # Abnormal exit (incl. OOM-emergency termination)
                consecutive_abnormal=$((consecutive_abnormal + 1))
                # OOM log sniff (best effort)
                if dmesg 2>/dev/null | tail -200 | grep -qiE "Out of memory|Killed process" ; then
                    log "post-episode: abnormal; recent OOM signature detected in dmesg"
                fi
                if [ "$consecutive_abnormal" -ge "$ABNORMAL_STREAK_TRIGGER" ]; then
                    log "post-episode: abnormal streak=${consecutive_abnormal}; long cooldown ${ABNORMAL_STREAK_LONG_COOLDOWN}s"
                    sleep "$ABNORMAL_STREAK_LONG_COOLDOWN"
                else
                    log "post-episode: abnormal; cooldown ${ABNORMAL_COOLDOWN}s"
                    sleep "$ABNORMAL_COOLDOWN"
                fi
                ;;
            2)
                # STOP detected mid-episode
                log "post-episode: STOP-driven termination; watchdog exiting"
                exit 0
                ;;
            *)
                log "post-episode: unexpected rc=${rc}; cooldown ${ABNORMAL_COOLDOWN}s"
                sleep "$ABNORMAL_COOLDOWN"
                ;;
        esac

        # Progress detection
        local head_after state_mtime_after
        head_after=$(git -C "$LAB_DIR/../.." rev-parse HEAD 2>/dev/null || echo unknown)
        state_mtime_after=$(stat -c %Y "$LAB_DIR/STATE.md" 2>/dev/null || echo 0)
        if [ "$head_before" = "$head_after" ] && [ "$state_mtime_before" = "$state_mtime_after" ]; then
            log "post-episode: NO_PROGRESS_EPISODE (HEAD unchanged, STATE.md mtime unchanged)"
        else
            log "post-episode: progress detected (HEAD: ${head_before:0:7}->${head_after:0:7}, STATE.md mtime: ${state_mtime_before}->${state_mtime_after})"
        fi

        first_iteration=0
    done
}

acquire_lock
main
