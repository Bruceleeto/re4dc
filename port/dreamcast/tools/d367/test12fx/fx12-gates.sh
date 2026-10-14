#!/bin/bash
# fx12-gates.sh <step>... (Git Bash): the test 12 effects lane gates, run once Flycast is free (NOT before the test 11
# gate is done). Evidence: C:\Flycast-Evidence\re4-dreamcast\t11-20261014\fx12-* (test11 t-run.sh / trace.sh /
# strict.sh hard-code that root). Build first (WSL): fx12-build.sh base knob L1T L0T L2T cT cW L0W L1W L2W mW
# Steps:
#   fix    fixtures (WSL t11-fix.py): fx12-<seg>-<label>.json for every arm; H2 trace = the fxtr-h2 opts (h2-late warp +
#          tour padscript), W runs = the segment warps h2 (r100 fight), bell (r101), r106. Data T11_DATA (release set).
#   ident  knob-off play image fx12ktP vs lane/t11 fx12btP (byte-identical; offline, no Flycast)
#   trace  H2 logic-trace runs c, L0, L1, L2 (one at a time through trace_lock.sh, stop tick 4700 = past s30 at 1672)
#   strict STRICT + decisions MUST-IDENTICAL of each level vs the padded control; s30 frames 340/340 both
#   tex    TEX_CHECK=2 runs of fx12m0mW on h2, bell, r106: texchk total_fails, package absent, fx missing
#   ms     W runs c, L0, L1, L2 on h2, bell, r106 (300 s; Flycast hw-model proxy, PACE lines) then fx12-ms.py table
set -u
K=/root/probe/lanes-20261014/fx12/tree/port/dreamcast/tools/d367
T11=$K/test11
W=//wsl.localhost/Ubuntu-24.04
E=/c/Flycast-Evidence/re4-dreamcast/t11-20261014
FIX=/root/probe/lanes-20261014/fx12/fix
SEG=$K/fullplay/segments
wsl_() { MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -u root -- "$@"; }
for s in "$@"; do case $s in
  fix)
    wsl_ bash -c "mkdir -p $FIX && cd $T11 && D=\$(grep -o \"^T11_DATA = '[^']*'\" t11-fix.py | cut -d\\' -f2) && \
      for L in fx12ctT fx12l0tT fx12l1tT fx12l2tT; do python3 t11-fix.py \$L $FIX/fx12-h2tr-\$L.json --data \$D \
        --warp /root/probe/impl-20261003/fixtures/h2-late-00-warp.txt \
        --pad '/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1/tour/padscript.txt' || exit 1; done && \
      for L in fx12ctW fx12l0tW fx12l1tW fx12l2tW fx12m0mW; do \
        python3 t11-fix.py \$L $FIX/fx12-h2-\$L.json --data \$D --warp $SEG/h2-warp.txt --pad $SEG/h2-pad.txt || exit 1; \
        python3 t11-fix.py \$L $FIX/fx12-bell-\$L.json --data \$D --warp $SEG/bell-warp.txt || exit 1; \
        python3 t11-fix.py \$L $FIX/fx12-r106-\$L.json --data \$D --warp $SEG/r106-warp.txt || exit 1; done && ls $FIX | wc -l" ;;
  ident) wsl_ bash $T11/ident.sh fx12btP fx12ktP ;;
  trace)
    for a in c l0 l1 l2; do
      bash $W$T11/trace.sh fx12-h2tr-$a fx12${a}tT $FIX/fx12-h2tr-fx12${a}tT.json 4700 600
    done ;;
  strict)
    for a in l0 l1 l2; do wsl_ bash $T11/strict.sh fx12-h2tr-c fx12-h2tr-$a fx12-c-vs-$a; done ;;
  tex)
    for seg in h2 bell r106; do
      PURPOSE="fx12 TEX_CHECK $seg FX_LEVEL=0" bash $W$T11/t-run.sh fx12-tex-$seg fx12m0mW $FIX/fx12-$seg-fx12m0mW.json 300
      f=$E/fx12-tex-$seg/capture/run-output.txt
      echo "$seg: $(grep -a 'texchk: room' $f | tail -1 | grep -o 'total_fails=[0-9]*') absent=$(grep -ac 'package absent' $f) $(grep -a 'native effect sprites' $f | tail -1 | grep -o 'missing=[0-9]*')"
    done ;;
  ms)
    for seg in h2 bell r106; do for a in c l0 l1 l2; do
      PURPOSE="fx12 ms $seg arm $a" bash $W$T11/t-run.sh fx12-ms-$seg-$a fx12${a}tW $FIX/fx12-$seg-fx12${a}tW.json 300
    done; done
    wsl_ python3 $K/test12fx/fx12-ms.py /mnt/c/Flycast-Evidence/re4-dreamcast/t11-20261014 ;;
  *) echo "step? $s"; exit 1 ;;
esac; done
