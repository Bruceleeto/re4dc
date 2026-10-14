#!/bin/bash
# kit-boot.sh <WORK> [play seconds, default 300] [warp seconds, default 150]   (Git Bash, maintainers; after kit-check.sh)
# The boot half of the kit publish gate: boots kit-check.sh's two swapped discs in Flycast (zipboot.py, the harness
# template, no controller) and fails on a HALT, a fault or a misaligned access, or when a disc does not get where it
# must: disc-play (the kit's play program + padscript-newgame.txt) through the title into New Game (r100);
# disc-warp (the kit's warp twin, TEX_CHECK=2 MCHECK_LEONGC=1) into r101 by the warp rig.
# Evidence: C:\Flycast-Evidence\re4-dreamcast\kit-check\<test>-<time>-{play,warp} (track copies deleted); the discs
# in WORK are deleted when both pass (sha256 kept in WORK/discs.sha256).
set -u
W=$1; PS=${2:-300}; WS=${3:-150}
H="/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
ZB=/c/Flycast-Evidence/re4-dreamcast/t10s-20261014/_tools/zipboot.py
E=/c/Flycast-Evidence/re4-dreamcast/kit-check; mkdir -p $E
UNC='\\wsl.localhost\Ubuntu-24.04'$(echo "$W" | tr / '\\')
N=$(basename "$W")-$(date +%m%d-%H%M)
rc=0
for d in play warp; do
  [ $d = play ] && s=$PS || s=$WS
  cap=$E/$N-$d
  (cd "$H" && python "$(cygpath -w $ZB)" "$UNC\\disc-$d" "$(cygpath -w $cap)" "$UNC\\disc-$d\\syms.txt" --seconds $s --period 60 > /dev/null)
  rm -f $cap/track0*.bin $cap/track02.raw
  f=$cap/run-output.txt
  bad=$(grep -acE 'HALT|FAULT|MISALIGN|RE4DC MISSING|LOG OVERRUN' $f)
  case $d in
    play) reach=$(grep -ac 'room lifecycle: phase=enter room=100 ' $f) ;;
    warp) reach=$(grep -ac 'room lifecycle: phase=enter room=101 ' $f) ;;
  esac
  tex=$(grep -ac 'texchk' $f); texfail=$(grep -acE 'texchk:.* (fails|total_fails)=[1-9]' $f); leongc=$(grep -ac '^LEONGC f=' $f)
  echo "kit-boot $d: lines=$(wc -l < $f) bad=$bad reached=$reach texchk=$tex texfail=$texfail leongc=$leongc evidence $cap"
  grep -aE 'HALT|FAULT|MISALIGN|RE4DC MISSING' $f | head -5
  [ "$bad" = 0 ] && [ "$texfail" = 0 ] && [ "$reach" != 0 ] || rc=1
done
if [ $rc = 0 ]; then
  MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -u root -- bash -c "cd $W && sha256sum disc-*/track03.bin > discs.sha256 && rm -rf disc-play disc-warp"
  echo "KIT-BOOT OK"
else
  echo "KIT-BOOT FAILED (discs kept in $W)"
fi
exit $rc
