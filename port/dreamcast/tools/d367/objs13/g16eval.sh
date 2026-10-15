#!/bin/bash
# g14eval.sh room... (WSL): test 13 objects gates (g16, test 12 base) per room: STRICT + decision_cmp (g14-<r>-c vs g14-<r>-t), TEX_CHECK and
# LEON-GC on g14-<r>-m, HALT / overrun counts. Prints one line per room.
E=/mnt/c/Flycast-Evidence/re4-dreamcast/objs-20261014
K=/root/probe/lanes-20261014/objs/tree/port/dreamcast/tools/d367
for r in "$@"; do
  c=$E/g16-$r-c/capture/run-output.txt; t=$E/g16-$r-t/capture/run-output.txt; m=$E/g16-$r-m/capture/run-output.txt
  s="-"; d="-"; tc="-"; lg="-"
  if [ -f $c ] && [ -f $t ]; then
    out=$(bash /mnt/c/tmp/objs/o-strict.sh g16-$r-c g16-$r-t g16-$r 2>&1)
    s=$(echo "$out" | sed -n 's/^STRICT verdict \([A-Z_]*\) compared \([0-9]*\).*/\1 \2/p' | head -1)
    d=$(echo "$out" | grep -o "MUST-IDENTICAL[^ ]*\|DIFFER[^ ]*\|IDENTICAL[^ ]*" | head -1)
  fi
  if [ -f $m ]; then
    tr -d '\0' < $m > /tmp/g16m-$r.txt
    tc=$(bash $K/texchk/texchk.sh /tmp/g16m-$r.txt 2>&1 | grep -o "TEXCHK [A-Z]*" | tail -1)
    lg=$(python3 $K/mcheck/leongc_check.py /tmp/g16m-$r.txt 2>&1 | grep -o "LEON-GC [A-Za-z ]*" | tail -1)
    pm=$(grep -ac "pair missing" /tmp/g16m-$r.txt)
  fi
  h=0; for f in $c $t $m; do [ -f $f ] && h=$((h + $(tr -d '\0' < $f | grep -ac "HALT \|LOG OVERRUN"))); done
  echo "r$r STRICT=[$s] dcmp=[$d] [$tc] [$lg] pair_missing=${pm:--} halt_or_overrun=$h"
done
# coverage: PS2 object picture / pair keys of the room seen loading in the mcheck run
for r in "$@"; do
  m=/tmp/g16m-$r.txt; j=/root/probe/lanes-20261014/objs/work/out/r${r}x/tex.json
  [ -f $m ] && [ -f "$j" ] && python3 - "$j" $m r$r <<'PY'
import json,sys
j=json.load(open(sys.argv[1])); log=open(sys.argv[2],errors='replace').read()
keys=[i['key'] for i in j['images']]+[p['key'] for i in j['images'] for p in i['ps2'].get('pairs',[])]+[p['key'] for e in j['pair_extras'] for p in e['pairs']]
seen=[k for k in keys if k in log]
print('%s coverage: %d / %d PS2 keys loaded in the mcheck run' % (sys.argv[3], len(seen), len(keys)))
PY
done
