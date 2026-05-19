#!/bin/sh
# scheduler.sh — periodic serverdocs scan loop for the serverdocs-scheduler
# container. Replaces the previous one-line `while sleep` invocation so each
# cycle is timestamped, exit codes are logged, and failures back off briefly
# instead of immediately hammering the same broken hosts for an hour.

set -u

: "${SCAN_INTERVAL:=3600}"   # seconds between scheduled scans (default 1h)
: "${FAILURE_BACKOFF:=60}"   # seconds to wait after a failed scan before retry
: "${SCAN_CMD:=serverdocs run}"

log() {
    # ISO-8601 UTC timestamp; -u so the container's local TZ doesn't matter.
    printf '%s [scheduler] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"
}

shutdown() {
    log "received signal, exiting"
    exit 0
}
trap shutdown INT TERM

log "starting (SCAN_INTERVAL=${SCAN_INTERVAL}s, FAILURE_BACKOFF=${FAILURE_BACKOFF}s)"

run_once() {
    label="$1"
    start_epoch=$(date -u +%s)
    log "${label}: invoking '${SCAN_CMD}'"
    # shellcheck disable=SC2086  # intentional word-split on SCAN_CMD
    $SCAN_CMD
    rc=$?
    duration=$(( $(date -u +%s) - start_epoch ))
    if [ "$rc" -eq 0 ]; then
        log "${label}: completed ok in ${duration}s"
    else
        log "${label}: FAILED (exit ${rc}) after ${duration}s"
    fi
    return "$rc"
}

# Initial scan on boot so the output tree is fresh immediately.
run_once "initial scan"
last_rc=$?

cycle=0
while :; do
    cycle=$((cycle + 1))
    if [ "$last_rc" -eq 0 ]; then
        sleep_for="$SCAN_INTERVAL"
    else
        sleep_for="$FAILURE_BACKOFF"
        log "previous scan failed; backing off ${sleep_for}s before retry"
    fi

    next_at=$(date -u -d "+${sleep_for} seconds" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo "+${sleep_for}s")
    log "sleeping until ${next_at} (cycle ${cycle})"
    sleep "$sleep_for"

    run_once "scheduled scan #${cycle}"
    last_rc=$?
done
