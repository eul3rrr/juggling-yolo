#!/usr/bin/env bash
# Keepalive watchdog for the overnight juggling-tracking research session.
#
# What it does:
#   - Every INTERVAL seconds, checks whether the overnight hermes agent is alive
#     (interactive session OR any resumed run of SESSION_ID).
#   - If dead, resumes the SAME session inside tmux session "ox-resume" with a
#     self-contained nudge pointing at STATE.md, using exponential backoff if
#     revivals keep dying quickly.
#   - Stops cleanly if the file $BASE/STOP exists (touch that file to shut the
#     whole resurrection system down).
#
# It NEVER kills any process and NEVER types into the user's terminal.

set -u

BASE="/home/it-admin/.hermes/profiles/juggling-tracker/workspace/juggling-yolo/experiments/overnight"
SESSION_ID="20260826_061301_ccfd81"
PROFILE="juggling-tracker"
HERMES_PY="/home/it-admin/.hermes/hermes-agent/venv/bin/python"
HERMES="/home/it-admin/.hermes/hermes-agent/hermes"
WORKDIR="/home/it-admin/projects/crl-analyzer/data/processed"
LOG="$BASE/watchdog.log"
NUDGE_FILE="$BASE/nudge.txt"

INTERVAL=120          # seconds between liveness checks
BASE_COOLDOWN=420     # min seconds after a revival before another is allowed
MAX_COOLDOWN=1800     # backoff ceiling (30 min)

log() { echo "[ $(date '+%F %T') ] $*" >> "$LOG"; }

mkdir -p "$BASE" 2>/dev/null || true
if ! mkdir "$BASE/.watchdog.lock" 2>/dev/null; then
    log "another watchdog instance holds the lock; exiting."
    exit 1
fi
trap 'rmdir "$BASE/.watchdog.lock" 2>/dev/null' EXIT

log "=== watchdog started (pid $$), interval=${INTERVAL}s ==="

last_action=0
cooldown=$BASE_COOLDOWN
consecutive_fast_deaths=0

agent_alive() {
    # Alive if: interactive profile session, or any --resume of our session id.
    pgrep -f -- "-p ${PROFILE}$" >/dev/null 2>&1 && return 0
    pgrep -f -- "-p ${PROFILE} " >/dev/null 2>&1 && return 0
    pgrep -f -- "--profile ${PROFILE}" >/dev/null 2>&1 && return 0
    pgrep -f -- "--resume ${SESSION_ID}" >/dev/null 2>&1 && return 0
    return 1
}

revive() {
    local now
    now=$(date +%s)
    local wait_needed=$(( last_action + cooldown - now ))
    if (( wait_needed > 0 )); then
        log "in revival cooldown, ${wait_needed}s remaining"
        return 1
    fi
    last_action=$now
    log "agent NOT found -> reviving session ${SESSION_ID} in tmux (ox-resume)"
    if tmux has-session -t ox-resume 2>/dev/null; then
        tmux respawn-window -k -t ox-resume:0 \
            "cd '${WORKDIR}' && '${HERMES_PY}' '${HERMES}' -p ${PROFILE} chat --query-file '${NUDGE_FILE}' --resume ${SESSION_ID} --yolo --no-restore-cwd; rc=\$?; echo REVIVE_EXIT_CODE=\$rc >> '${LOG}'; sleep 900"
    else
        tmux new-session -d -s ox-resume \
            "cd '${WORKDIR}' && '${HERMES_PY}' '${HERMES}' -p ${PROFILE} chat --query-file '${NUDGE_FILE}' --resume ${SESSION_ID} --yolo --no-restore-cwd; rc=\$?; echo REVIVE_EXIT_CODE=\$rc >> '${LOG}'; sleep 900"
    fi
    log "revival dispatched"
    return 0
}

while true; do
    if [ -f "$BASE/STOP" ]; then
        log "STOP file detected -> watchdog exiting (session left untouched)."
        exit 0
    fi

    if agent_alive; then
        consecutive_fast_deaths=0
        cooldown=$BASE_COOLDOWN
        # quiet when healthy; only log every ~15 min so the file stays readable
        if (( $(date +%s) % 900 < INTERVAL )); then
            log "agent alive"
        fi
    else
        if revive; then
            consecutive_fast_deaths=$(( consecutive_fast_deaths + 1 ))
            if (( consecutive_fast_deaths >= 3 )); then
                cooldown=$(( cooldown * 2 ))
                (( cooldown > MAX_COOLDOWN )) && cooldown=$MAX_COOLDOWN
                log "fast-death streak=${consecutive_fast_deaths}, backing off to ${cooldown}s"
            fi
        fi
    fi

    sleep "$INTERVAL"
done
