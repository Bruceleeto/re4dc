#!/bin/bash
# gcmp.sh <A run dir> <B run dir> [label]: lane el gate compare: decision_cmp.py (frame + room aligned) and
# logic_trace_diff.py (frame + room aligned) of two LOGIC_TRACE=1 GAME_DECISION_TRACE=1 runs.
T=/root/probe/lanes-20261005/el/tree/port/dreamcast/tools/game30
D=/root/probe/d367-agents/game30/tools/logic_trace_diff.py
A=$1/run-output.txt; B=$2/run-output.txt
echo "=== ${3:-} $(basename $1) / $(basename $2)"
for al in frame room; do
  echo "-- decision_cmp --align $al"; python3 $T/decision_cmp.py "$A" "$B" --align $al 2>&1 | tail -12
  echo "-- logic_trace_diff --align $al"; python3 $D "$A" "$B" --align $al 2>&1 | tail -5
done
