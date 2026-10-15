#!/bin/bash
# fx12-gates.sh <step>... (Git Bash): the test 12 effects lane gates. Run only after "test 11 gate done" (Flycast free).
# Evidence: C:\Flycast-Evidence\re4-dreamcast\t11-20261014\fx12-* (test11 t-run.sh / trace.sh / strict.sh use that root).
# Build first (WSL, fx12-build.sh): base knob, c:W t1:W t2:W m:W lo:W, PAD_TO=fx12mtT m:T c:T t2:T lo:T, t2:mW.
# Priority (user 10-14): r101 village fps first (FX_SPRITE_TRIM, FX_LEVEL medium/low); generator + owners (g) after.
# Env SETS (arm sets, default "c t1 t2 m lo"), SEGS (ms segments, default "bell villager"; later "h2 r106").
# Steps:
#   fix    fixtures (WSL t11-fix.py, data T11_DATA = the release set): fx12-h2tr-<label>.json (H2 trace: h2-late warp +
#          tour padscript, as fxtr-h2), fx12-<seg>-<label>.json for W runs (segment warps; bell / villager = the r101
#          square fight with Ganados on screen, h2 = r100 fight, r106)
#   ident  knob-off play image fx12ktP vs lane/t11 fx12btP (byte-identical; offline)
#   trace  H2 logic-trace runs per trace set (one at a time through trace_lock.sh; stop tick 4700, past s30 at 1672)
#   strict STRICT + decisions MUST-IDENTICAL of each trace set vs c; s30 frames 340/340 in both
#   tex    TEX_CHECK=2 runs of fx12t2mW on bell, villager, h2: texchk total_fails, package absent, effect missing
#   ms     W runs of every set on every segment (300 s), then fx12-ms.py (MODELLED table, deltas vs c)
set -u
K=/root/probe/lanes-20261014/fx12/tree/port/dreamcast/tools/d367
T11=$K/test11
W=//wsl.localhost/Ubuntu-24.04
E=/c/Flycast-Evidence/re4-dreamcast/t11-20261014
FIX=/root/probe/lanes-20261014/fx12/fix
SEG=$K/fullplay/segments
SETS=${SETS:-c t1 t2 m lo}
TSETS=${TSETS:-c t2 m lo}
SEGS=${SEGS:-bell villager}
wsl_() { MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -u root -- "$@"; }
for s in "$@"; do case $s in
  fix)
    cat > $W/tmp/fx12-fix.sh <<EOS
set -e; mkdir -p $FIX; cd $T11
D=\$(python3 -c "import re;print(re.search(r\"^T11_DATA = '([^']*)'\", open('t11-fix.py').read(), re.M).group(1))")
PAD='/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1/tour/padscript.txt'
for a in $TSETS; do python3 t11-fix.py fx12\${a}tT $FIX/fx12-h2tr-fx12\${a}tT.json --data \$D --warp /root/probe/impl-20261003/fixtures/h2-late-00-warp.txt --pad "\$PAD"; done
for a in $SETS; do for g in bell villager h2 r106; do
  P=""; [ -f $SEG/\$g-pad.txt ] && P="--pad $SEG/\$g-pad.txt"
  python3 t11-fix.py fx12\${a}tW $FIX/fx12-\$g-fx12\${a}tW.json --data \$D --warp $SEG/\$g-warp.txt \$P; done; done
for g in bell villager h2; do P=""; [ -f $SEG/\$g-pad.txt ] && P="--pad $SEG/\$g-pad.txt"
  python3 t11-fix.py fx12t2mW $FIX/fx12-\$g-fx12t2mW.json --data \$D --warp $SEG/\$g-warp.txt \$P; done
ls $FIX | wc -l
EOS
    wsl_ bash /tmp/fx12-fix.sh ;;
  ident) wsl_ bash $T11/ident.sh fx12btP fx12ktP ;;
  trace) for a in $TSETS; do bash $W$T11/trace.sh fx12-h2tr-$a fx12${a}tT $FIX/fx12-h2tr-fx12${a}tT.json 4700 600; done ;;
  strict) for a in $TSETS; do [ $a = c ] || wsl_ bash $T11/strict.sh fx12-h2tr-c fx12-h2tr-$a fx12-c-vs-$a; done ;;
  tex)
    for g in bell villager h2; do
      PURPOSE="fx12 TEX_CHECK $g arm t2" bash $W$T11/t-run.sh fx12-tex-$g fx12t2mW $FIX/fx12-$g-fx12t2mW.json 300
      f=$E/fx12-tex-$g/capture/run-output.txt
      echo "$g: $(grep -a 'texchk: room' $f | tail -1 | grep -o 'total_fails=[0-9]*') absent=$(grep -ac 'package absent' $f) $(grep -a 'native effect sprites' $f | tail -1 | grep -o 'missing=[0-9]*')"
    done ;;
  ms)
    for g in $SEGS; do for a in $SETS; do
      PURPOSE="fx12 ms $g arm $a" bash $W$T11/t-run.sh fx12-ms-$g-$a fx12${a}tW $FIX/fx12-$g-fx12${a}tW.json 300
    done; done
    wsl_ python3 $K/test12fx/fx12-ms.py /mnt/c/Flycast-Evidence/re4-dreamcast/t11-20261014 --sets "$SETS" --segs "$SEGS" ;;
  *) echo "step? $s"; exit 1 ;;
esac; done
