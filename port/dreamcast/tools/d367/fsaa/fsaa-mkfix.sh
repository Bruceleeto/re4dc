set -eu
F=/root/probe/lanes-20261014/fsaa
mkdir -p $F/fix
printf 'render=fsaa\n' > $F/fix/q-fsaa.txt
printf 'render=lite\n' > $F/fix/q-lite.txt
printf 'render=quality\n' > $F/fix/q-quality.txt
P=/root/probe/lanes-20261013/rel91/fix/pkg-r91tP.json
FX="python3 /root/probe/lanes-20261014/t10s/t10s-fix.py $P r91tP"
H2W=/root/probe/impl-20261003/fixtures/h2-late-00-warp.txt
H2P="/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1/tour/padscript.txt"
SQ=/root/probe/lanes-20261011/test8/fix/warps/st-square.txt
$FX fsaFtP $F/fix/pkg-fsaFtP.json --pak gc --hands 1
for q in fsaa lite quality; do
  $FX fsaFmW $F/fix/h2$q-fsaFmW.json --pak gc --hands 1 --warp $H2W --pad "$H2P" --qtxt $F/fix/q-$q.txt
  $FX fsaFmW $F/fix/sq$q-fsaFmW.json --pak gc --hands 1 --warp $SQ --qtxt $F/fix/q-$q.txt
done
$FX fsaCmW $F/fix/sqcyc-fsaCmW.json --pak gc --hands 1 --warp $SQ
ls $F/fix
