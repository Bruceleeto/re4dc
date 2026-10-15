#!/bin/bash
# fsaa-build.sh <arm>... (copy of test10s/t10s-build.sh; FX=extra knobs on every arm): test 10 (small) build arms = the frozen test 9 / 9.1 recipe (lanes-20261012/test9/t9-build.sh,
#   lanes-20261013/rel91/r91-build.sh) built from origin/dreamcast-port a93e8be0 (9.1 + 6035dfd3 motion-read backoff,
#   other commits default-off), plus exactly HANDS (Leon stays PS2 in every hand pose; needs the disc package
#   dc/native/pl00/leon_hands_pl00.re4hp in the fixture). The GC-atlas face is data only (tex.pak in the fixture).
# Arms: tP play (packaged), tW warp, mW warp + MCHECK_LEONGC=1 TEX_CHECK=2 (test only), tT trace,
#       kP knob-off play (no HANDS: identity vs 9.1 r91tP), cT 9.1 control trace from the rel91 tree (40fb4deb),
#       cW 9.1 control warp (rel91 tree), cmW 9.1 control warp + MCHECK_LEONGC=1 TEX_CHECK=2.
# Env: LP (label prefix, default t10s), PAD_T / CPAD_T (trace pads), XON (test only).
set -u
K=/root/probe/lanes-20261014/fsaa
T=${T:-/root/probe/lanes-20261014/fsaa/tree}
C91=/root/probe/lanes-20261013/rel91/tree
export SOURCE_DATE_EPOCH=1760000000
F="PACE_DEBUG=1 ROUTE_CH13=1 ROUTE_CH21=1 SBB_STUB=1 PVR_READY_STRICT=1 ACT_CAP=0 PS2_INTERIOR_ACTORS=2 GAME_ATLIST_OVERFLOW=1 GAME_ATLIST_512=1 LEON_NATIVE_PIPE=0 LEON_FACE_LAZY=0 NATIVE_LASER=1 ACTOR_GANADO_SOURCE_LIGHT=0 PRIM_CAP_R10B=327680"
LOOK="EFFECT_PS2_TOGGLE=1 LOOK_TOGGLE=1 FILTER00_DC=1 CHARBAKE_TOGGLE=1 CHARBAKE_HAIR=0"
PS2="PS2_LEON=1 PS2_LEON_DIR=/root/probe/lanes-20261011/pl08/assets/arm-a ACTOR_PL08_PACK=1 PS2_GANADO=1 PS2_GANADO_DIR=/root/probe/lanes-20261010/ps2cast-all-assets/pg5 PS2_GANADO_F=1 PS2_GIGANTE=1 PS2_DELLAGO=1 PS2_VERTEX_ALPHA=1"
P2="MOVIE_DISC_QUIET=1 EFFECT_HAZE_LEAN=3 EFFECT_HAZE_LEAN_TOGGLE=0 RENDER_OPTION=1 PS2_GANADO_LIT=1 CAST_MIPMAP=1 PS2_CROW=1 PS2_ANIMALS=1 PS2_WOLF=1 HEAP4_PARTS_RESERVE=1 DVD_READ_SAFE=1 LAKE_RIPPLES=1 VGA_SOFT=1 LETTERBOX_CLIP=1 PS2_PT_CUTOUT=1 PACE_VMU=1 PACE_VMU_GPU=1 UI_FRAG_RESERVE=1"
T9K="DOOR_FREEZE=1 LOAD_INDICATOR=1 VMU_CONTEXT=1 OPTION_ROW_STYLE=1 PT_BLEND_FIX=1 MODEL_STREAM_FIX=1 SS_MENU_ANIM_RT=1 PS2_ENEMY_RULES=1 ACT_CAP_TABLE=1 RENDER_QUALITY_ONLY=1 RESET_HEAP_FIX=1"
# test 10 (small): the only new knobs
HANDS="LEON_HAND_POSES=1 LEON_HAND_PACK=1 LEON_SKIN_SLOTS=1"
ON="$T9K PVR_LATCH=2 PVR_RECOVER=1 TA_HEADROOM=1 CRASH_TASK_DETAIL=1 $PS2 $P2"
MC="MCHECK_LEONGC=1 TEX_CHECK=2"
TR="DBG_WARP=1 PC_SAMPLER=1 LOGIC_TRACE=1 GAME_DECISION_TRACE=1 PACE_MODE=off TRACE_SS_MASK=1 TRACE_ALLOC=1 CODEC_READY_FIXTURE=1"
WP="DBG_WARP=1 PC_SAMPLER=1"
PL="DBG_WARP=0 PC_SAMPLER=0"
b() { lab=$1; tree=$2; shift 2; t0=$(date +%s); echo "== $lab $(date +%T) tree=$tree $*" >> $K/logs-build.txt
  (cd $tree && TREE=$tree bash /root/probe/d367-buildslot.sh bash port/dreamcast/tools/d367/route/route-build.sh $lab $F $LOOK "$@" ${FX:-} >> $K/logs-build.txt 2>&1)
  rc=$?; O=/root/probe/lanes/route/out-$lab
  end=$(/opt/toolchains/dc/sh-elf/bin/sh-elf-nm $O/re4dc-game.elf 2>/dev/null | awk '$3=="_end"{print $1}')
  echo "rc=$rc $lab $(cut -c1-16 $O/elf.sha256 2>/dev/null) $(( $(date +%s) - t0 ))s missing=$(wc -c < $O/missing.txt 2>/dev/null) end=$end $(grep -E '^(LEON_HAND_POSES|LEON_HAND_PACK|LEON_SKIN_SLOTS|MCHECK_LEONGC|TEX_CHECK|RESET_HEAP_FIX|RESET_MEM_FIX|PS2_FX_ROOMS|PS2_R100_SMX|IMAGE_PAD_BYTES|LOGIC_TRACE|DBG_WARP)=' $O/resolved-knobs.txt | tr '\n' ' ')" | tee -a $K/logs-build.txt
  echo "$end" > $O/end.txt; }
L=${LP:-fsa}
for x in "$@"; do case $x in
  tP)  b ${L}tP  $T   $ON $HANDS IMAGE_PAD_BYTES=0 $PL ;;
  tW)  b ${L}tW  $T   $ON $HANDS IMAGE_PAD_BYTES=0 $WP ${XON:-} ;;
  mW)  b ${L}mW  $T   $ON $HANDS IMAGE_PAD_BYTES=0 $WP $MC ;;
  tT)  b ${L}tT  $T   $ON $HANDS IMAGE_PAD_BYTES=${PAD_T:-0} $TR ;;
  kP)  b ${L}kP  $T   $ON IMAGE_PAD_BYTES=0 $PL ;;
  cT)  b ${L}cT  $C91 $ON IMAGE_PAD_BYTES=${CPAD_T:-0} $TR ;;
  cW)  b ${L}cW  $C91 $ON IMAGE_PAD_BYTES=0 $WP ;;
  cmW) b ${L}cmW $C91 $ON IMAGE_PAD_BYTES=0 $WP $MC ;;
  *) echo "arm? $x" ;;
esac; done
