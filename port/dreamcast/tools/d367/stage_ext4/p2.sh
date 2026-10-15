#!/bin/bash
# proof 2: fp_master.sh (release base) old path vs ext4+cache cold vs reuse; then 5 stagings C: free.
set -u
T=/root/probe/lanes-20261014/stage/tree/port/dreamcast/tools/d367
C=/root/probe/lanes-20261014/fullplay/work/rel-2ff31eabfe163183
E=/mnt/c/Flycast-Evidence/re4-dreamcast/stx4-proof-20261014
mkdir -p $E
TIMEFORMAT='%R wall %U user %S sys'
free() { df -B1 --output=avail /mnt/c | tail -1; }
case "${1:-}" in
fp)
  for m in old cold reuse; do
    f0=$(free)
    if [ $m = old ]; then
      { time RE4DC_STAGE_EXT4=0 bash $T/fullplay/fp_master.sh $C/tree $C/manifest.json $C/IP.BIN $E/fp-$m > $E/fp-$m.log 2>&1; } 2> $E/fp-$m.time
    else
      { time RE4DC_STAGE_EXT4=1 bash $T/fullplay/fp_master.sh $C/tree $C/manifest.json $C/IP.BIN $E/fp-$m > $E/fp-$m.log 2>&1; } 2> $E/fp-$m.time
    fi
    echo "fp $m: $(cat $E/fp-$m.time) | C: delta $(( ($(free) - f0) / 1048576 )) MB | $(tail -1 $E/fp-$m.log | cut -c1-160) | sha $(cut -c1-16 $E/fp-$m/track03.sha256) links $(stat -c %h $E/fp-$m/track03.iso)"
  done ;;
five)
  HW="/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
  OV=/mnt/c/Flycast-Evidence/re4-dreamcast/r11-media-overlay-r1/payloads
  cd "$HW"
  f0=$(free); echo "C: free before $((f0/1048576)) MB"
  for i in 1 2 3 4 5; do
    { time python3 $T/stage_ext4/stage_scenario.py stx4-five-$i --arm candidate-routet10smW --programs programs-route.json --overlay $OV \
        --fixture /root/probe/lanes-20261014/t10s/fix/mh2-t10smW.json > $E/five-$i.json 2> $E/five-$i.err; } 2> $E/five-$i.time
    echo "staging $i: $(cat $E/five-$i.time) $(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['status'],d['disc_sha256'][:16],'reused',d['ext4']['reused_image'],'9p_w_MB',d['ext4']['p9_write']>>20)" $E/five-$i.json 2>/dev/null || tail -2 $E/five-$i.err) | C: free $(( $(free)/1048576 )) MB"
  done
  echo "C: delta after 5 stagings $(( ($(free) - f0) / 1048576 )) MB"
  python3 $T/stage_ext4/disccache.py status ;;
esac
