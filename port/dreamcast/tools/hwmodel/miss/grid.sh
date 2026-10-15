#!/bin/bash
# grid.sh "name:args" ... : runs variants two at a time, then fit.py on all.
T=/mnt/c/Flycast-Evidence/re4-dreamcast/hwmiss-20261015/tools
names=()
n=0
for spec in "$@"; do
  name=${spec%%:*}; args=${spec#*:}
  names+=("$name")
  bash $T/sim.sh "$name" $args > /dev/null &
  n=$((n+1)); if [ $((n % 2)) = 0 ]; then wait; fi
done
wait
python3 $T/fit.py "${names[@]}"
