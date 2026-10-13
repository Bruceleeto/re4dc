#!/bin/bash
# D367 host-wide trace lock: only one logic-trace Flycast run (STRICT pairs, decision traces)
# at a time on this host, across Claude and Codex lanes. Other Flycast runs need no lock.
#
#   trace_lock.sh <command> [args...]   run the command while holding the lock (waits for it)
#   trace_lock.sh --status              show who holds it
#
# The lock is /root/probe/.trace.lock (flock); the holder is written to /root/probe/.trace.holder.
set -u
LOCK=/root/probe/.trace.lock
HOLDER=/root/probe/.trace.holder
if [ "${1:-}" = "--status" ]; then
    if flock -n "$LOCK" true; then echo "free"; else echo "held: $(cat "$HOLDER" 2>/dev/null)"; fi
    exit 0
fi
[ $# -ge 1 ] || { echo "usage: trace_lock.sh <command> [args...] | --status" >&2; exit 2; }
exec 9>"$LOCK"
if ! flock -n 9; then
    echo "trace_lock: waiting for $(cat "$HOLDER" 2>/dev/null)" >&2
    flock 9
fi
echo "$(date -Is) pid=$$ ${TRACE_LOCK_OWNER:-unknown} :: $*" > "$HOLDER"
"$@"
rc=$?
: > "$HOLDER"
exit $rc
