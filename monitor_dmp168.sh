#!/usr/bin/env bash
# Monitor a DMP168 device's state every 30 seconds, appending each
# observation (with a UTC timestamp) to a log file. The device's reported
# uptime is captured as part of each entry, which lets us pinpoint when
# the device transitions from "on" into the "problem" state.
#
# Usage: ./monitor_dmp168.sh <ip> [log-file]
#
# Stop with Ctrl-C. Output is written to the log file AND echoed to the
# terminal so you can watch it live or `tail -f` from another shell.

set -uo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <ip> [log-file]" >&2
    exit 2
fi

HERE="$(cd "$(dirname "$0")" && pwd)"
IP="$1"
LOG="${2:-$HERE/dmp168_monitor.log}"
INTERVAL=30

echo "monitoring $IP every ${INTERVAL}s -> $LOG (Ctrl-C to stop)"

while true; do
    ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
    {
        printf '\n==== %s ====\n' "$ts"
        python3 "$HERE/tools/dmp168_state.py" "$IP" 2>&1
    } | tee -a "$LOG"
    sleep "$INTERVAL"
done
