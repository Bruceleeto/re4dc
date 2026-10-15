#!/bin/bash
# gen13.sh: lane objs object dars for test 13 on the published test 12 package.
# 1. ps2_objects room from the GC-object source dars (the dars the 10-11 p2b packages were made from; gen-all.sh) with
#    the breakable class left GC (cEmBox/cEmBarrel family: et0100 et0200 et1100 et1200 et1e00 et1f00 et2d00 et2e00/01
#    et2f00/01 et3c00; game code spawns the break debris on the box model: documented exception, coordinator 10-15).
#    This also puts back the GC breakables the p2b dars (tests 8..12) shipped converted.  -> work/out/<room>g
# 2. ps2_items.py pack (lane items, test 12 code ac1c912e) with the shared ps2lib on top -> work/out/<room>t
#    (the test 12 st1 dars are items packs of the p2b dars; pack is in place, payload size unchanged).
W=/root/probe/lanes-20261014/objs/work
AO=/root/probe/lanes-20261009/test/audio-overlay/st1
LR=/root/probe/lanes-20261010
LIB="/mnt/c/Game Dev/Emulators/re4-assets-private/ps2lib"
IT=/root/probe/lanes-20261014/t12rc/tree/port/dreamcast/tools
K="--keep-larger"
g() {
  bash $W/gen.sh "$@" > /dev/null 2>&1 || { echo "FAIL $1 $2"; tail -3 $W/out/$2/gen.log; return; }
  local r=$1 o=$W/out/${2%g}t
  mkdir -p $o
  ( cd $IT && python3 ps2_items.py pack --dar $W/out/$2/$r.dar --room $r --lib "$LIB" --out $o/$r.dar --json $o/pack.json > $o/pack.log 2>&1 ) || { echo "PACKFAIL $r"; tail -3 $o/pack.log; }
  echo "$2 $(tail -1 $W/out/$2/gen.log) | items: $(tail -1 $o/pack.log | cut -c1-80)"
}
g r102 r102g $AO/r102.dar --etm et0a00.bin,et0d00.bin,et1300.bin,et2c00.bin,et2c01.bin $K
g r103 r103g /root/probe/d367-agents/design-r103/w8b-rel/st1/r103.dar --etm et0500.bin,et0600.bin,et1a00.bin $K
g r104 r104g $AO/r104.dar --pairs 20:20 --etm et0600.bin,et1300.bin,et1700.bin $K
g r105 r105g $AO/r105.dar --etm et0001.bin,et2200.bin,et2400.bin $K
g r106 r106g $AO/r106.dar --pairs 20:20,32:32,34:34,36:36 --etm et0500.bin,et0d00.bin $K
g r107 r107g $AO/r107.dar --etm et0001.bin,et0700.bin,et0701.bin,et1600.bin,et2b00.bin $K
g r108 r108g $AO/r108.dar --etm et1a00.bin $K
g r109 r109g $AO/r109.dar --etm et1000.bin $K
g r10a r10ag $AO/r10a.dar --pairs 20:20 $K
g r10b r10bg /root/probe/lanes-20261009/r10b/rooms/aica-r10b/st1/r10b.dar --pairs 1e:1e $K
g r117 r117g $LR/r117/rooms/aica-r117/st1/r117.dar --pairs 1f:1f --etm et1600.bin $K
g r118 r118g $LR/r118/rooms/aica-r118/st1/r118.dar --etm et1a00.bin $K
g r11a r11ag $LR/r11a/rooms/aica-r11a/st1/r11a.dar --etm et1000.bin --etm-from et1000.bin=r109 $K
g r11b r11bg $LR/r11b/rooms/aica-r11b/st1/r11b.dar --pairs 1f:1f --etm et0300.bin $K
g r119 r119g $LR/r119/rooms/aica-r119/st1/r119.dar --pairs 22:22 --etm et1000.bin $K
