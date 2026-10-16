#!/bin/bash
# room_c.sh <room> <tag> <srcdir> <walk.json> <source-groups|zero> <gate placements csv|-> -- <ladder args...>
# worldtest16 offline job (copy of world16 room.sh with the ladder arguments, source groups and gate placements as
# parameters). Output /root/probe/worldtest16-20261016/rooms/<room>-<tag>/out (6 files, the WORLD_VERT=1 LEVEL=5 set).
set -u
R=$1; TAG=$2; SD=$3; WALK=$4; SG=$5; GATE=$6; shift 7
T=/root/probe/codex-cpu-t15-20261016/tree/port/dreamcast/tools
O=/root/probe/worldtest16-20261016/rooms/$R-$TAG; rm -rf $O; mkdir -p $O; cd $O
exec > $O/job.log 2>&1
cp "$SD/ps2-world.re4mesh" src.re4mesh; cp "$SD/ps2-world.r4pw" src.r4pw; cp "$SD/ps2-world.ids" src.ids
SZ=$(stat -c %s src.re4mesh)
echo "room $R tag $TAG src=$SD bytes=$SZ walk=$WALK sg=$SG gate=$GATE ladder: $*"
python3 ${LADDER:-$T/ps2_world_vert_ladder.py} src.re4mesh L2.re4mesh --sidecar src.r4pw --walk "$WALK" "$@" --report L2.json >L2.out \
  || { echo "FAIL ladder"; exit 3; }
python3 $T/ps2_world_batch.py L2.re4mesh flat.re4mesh --sidecar src.r4pw --cell-mm 4000 --max-vertices 256 \
  --contiguous --max-bytes $SZ --report flat.json || { echo "contiguous over ceiling: indexed batch only"; python3 $T/ps2_world_batch.py L2.re4mesh flat.re4mesh --sidecar src.r4pw --cell-mm 4000 --max-vertices 256 --max-bytes $SZ --report flat.json || { echo "FAIL batch"; exit 4; }; echo "STORAGE=indexed"; }
python3 $T/ps2_strip_groups.py flat.re4mesh src.r4pw flatg.re4mesh flat.r4sg --report flatsg.json || { echo "FAIL groups"; exit 5; }
python3 - "$GATE" <<PY
import json,struct,sys
b=open('src.r4pw','rb').read(); crc=struct.unpack_from('<4s7I',b)[5]
g=sys.argv[1]; pl=[] if g=='-' else [int(x) for x in g.split(',')]
json.dump({'r4pw_crc':'%08x'%crc,'objects':[{'placement':p} for p in pl]},open('gate.json','w'))
PY
if [ "$SG" = zero ]; then head -c 262144 /dev/zero > cap.r4sg; else cp "$SG" cap.r4sg; fi
SPATIAL=none
if python3 $T/ps2_world_spatial_batch.py flat.re4mesh src.r4pw src.ids sp --cell-mm 32000 --max-bytes $SZ \
     --source-groups cap.r4sg --gated-manifest gate.json > spatial.out 2>&1; then SPATIAL=ok; else SPATIAL=fail; tail -3 spatial.out; fi
mkdir -p out
if [ "$SPATIAL" = ok ] && [ "$(python3 -c "import json;print(json.load(open('sp/report.json'))['cells'])")" = 0 ]; then SPATIAL=nocells; fi
if [ "$SPATIAL" = ok ]; then
  head -c $(stat -c %s sp/ps2-wv5.r4sg) sp/ps2-world.r4sg > sp/l0cap.r4sg; mv sp/l0cap.r4sg sp/ps2-world.r4sg
  cp sp/ps2-world.re4mesh sp/ps2-world.r4pw sp/ps2-world.ids sp/ps2-world.r4sg sp/ps2-wv5.re4mesh sp/ps2-wv5.r4sg out/
else
  cp src.re4mesh out/ps2-world.re4mesh; cp src.r4pw out/ps2-world.r4pw; cp src.ids out/ps2-world.ids
  cp flatg.re4mesh out/ps2-wv5.re4mesh; cp flat.r4sg out/ps2-wv5.r4sg
  head -c $(stat -c %s flat.r4sg) /dev/zero > out/ps2-world.r4sg
fi
echo "SPATIAL=$SPATIAL"
python3 -c "import json;L=json.load(open('L2.json'))['summary'];print('KEPT corners %d -> %d share %.3f bytes %d -> %d protect %s'%(L['all_corners_in'],L['all_corners_out'],L['all_corners_out']/L['all_corners_in'],L['bytes_in'],L['bytes_out'],L['protect_bins']))"
ls -l out; sha256sum out/*
echo DONE
