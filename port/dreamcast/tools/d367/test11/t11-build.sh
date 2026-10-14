#!/bin/bash
# t11-build.sh <arm>...: test 11 build arms = the test 10 recipe (test10s/t10s-build.sh, a93e8be0 + HANDS) built from
#   lane/t11 (origin a65045fe + the test 11 commits), plus the test 11 knobs ($T11). Every test 11 knob is default 0 in
#   the Makefiles: with T11="" (arm kP) the play image must be byte-identical to test 10 (out-t10stP).
# Arms: tP play (packaged), tW warp, mW warp + MCHECK_LEONGC=1 TEX_CHECK=2 (+ MCHECK_PT=1 TA_HASH=2 MCHECK_SAFE=1 with MPT=1),
#       tT trace, kP knob-off play (identity vs out-t10stP), kW knob-off warp, kT knob-off trace (STRICT control).
# Env: T (tree, default $K/tree), LP (label prefix, default t11), T11 (test 11 knobs, default the recipe below),
#      XON (extra knobs, test only), PAD_T / PAD_K (trace image pads).
set -u
K=${K:-/root/probe/lanes-20261014/t11}
T=${T:-$K/tree}
export SOURCE_DATE_EPOCH=1760000000
F="PACE_DEBUG=1 ROUTE_CH13=1 ROUTE_CH21=1 SBB_STUB=1 PVR_READY_STRICT=1 ACT_CAP=0 PS2_INTERIOR_ACTORS=2 GAME_ATLIST_OVERFLOW=1 GAME_ATLIST_512=1 LEON_NATIVE_PIPE=0 LEON_FACE_LAZY=0 NATIVE_LASER=1 ACTOR_GANADO_SOURCE_LIGHT=0 PRIM_CAP_R10B=327680"
LOOK="EFFECT_PS2_TOGGLE=1 LOOK_TOGGLE=1 FILTER00_DC=1 CHARBAKE_TOGGLE=1 CHARBAKE_HAIR=0"
PS2="PS2_LEON=1 PS2_LEON_DIR=/root/probe/lanes-20261011/pl08/assets/arm-a ACTOR_PL08_PACK=1 PS2_GANADO=1 PS2_GANADO_DIR=/root/probe/lanes-20261010/ps2cast-all-assets/pg5 PS2_GANADO_F=1 PS2_GIGANTE=1 PS2_DELLAGO=1 PS2_VERTEX_ALPHA=1"
P2="MOVIE_DISC_QUIET=1 EFFECT_HAZE_LEAN=3 EFFECT_HAZE_LEAN_TOGGLE=0 RENDER_OPTION=1 PS2_GANADO_LIT=1 CAST_MIPMAP=1 PS2_CROW=1 PS2_ANIMALS=1 PS2_WOLF=1 HEAP4_PARTS_RESERVE=1 DVD_READ_SAFE=1 LAKE_RIPPLES=1 VGA_SOFT=1 LETTERBOX_CLIP=1 PS2_PT_CUTOUT=1 PACE_VMU=1 PACE_VMU_GPU=1 UI_FRAG_RESERVE=1"
T9K="DOOR_FREEZE=1 LOAD_INDICATOR=1 VMU_CONTEXT=1 OPTION_ROW_STYLE=1 PT_BLEND_FIX=1 MODEL_STREAM_FIX=1 SS_MENU_ANIM_RT=1 PS2_ENEMY_RULES=1 ACT_CAP_TABLE=1 RENDER_QUALITY_ONLY=1 RESET_HEAP_FIX=1"
HANDS="LEON_HAND_POSES=1 LEON_HAND_PACK=1 LEON_SKIN_SLOTS=1"
# test 11: the new knobs (each default 0 in the tree). T11REC = the test 11 release recipe (default; T11="" = none).
# Leon light (ACTOR_PROBE_LIGHT LEON_SOURCE_LIGHT LEON_LIGHT_HEADROOM) needs the leonhr data set (2x Leon tex.pak):
# binary and pak must match. LEON_LIGHT_TOGGLE is debug only, never in the release recipe.
T11REC="PS2_R100_SMX=1 PS2_R100_TR4=1 LAKE_ZBIAS=1.001 WORLD_HOLE_FIX=1 SPEED_VMU_OFF=2 TEX_REF_SELFKEY=1 MOVIE_HEAP_PREFLIGHT=1 PS2_FX_ROOMS=1 PS2_FX_STAGE1=1 PS2_FX_POPULATION=1 PS2_FX_ADDITIONS=1 PS2_FX_ROOMS_EXT=1 EFFECT_TORCH=1 RAIN_PS2=1 ACTOR_PROBE_LIGHT=1 LEON_SOURCE_LIGHT=1 LEON_LIGHT_HEADROOM=1 PS2_ENEMY_ROOMS=0x3f MV_SHADOWS=1"
T11=${T11-$T11REC}
ON="$T9K PVR_LATCH=2 PVR_RECOVER=1 TA_HEADROOM=1 CRASH_TASK_DETAIL=1 $PS2 $P2 $HANDS"
MC="MCHECK_LEONGC=1 TEX_CHECK=2"
[ "${MPT:-0}" = 1 ] && MC="$MC TA_HASH=2 MCHECK_PT=1 MCHECK_SAFE=1"
TR="DBG_WARP=1 PC_SAMPLER=1 LOGIC_TRACE=1 GAME_DECISION_TRACE=1 PACE_MODE=off TRACE_SS_MASK=1 TRACE_ALLOC=1 CODEC_READY_FIXTURE=1"
WP="DBG_WARP=1 PC_SAMPLER=1"
PL="DBG_WARP=0 PC_SAMPLER=0"
b() { lab=$1; tree=$2; shift 2; t0=$(date +%s); echo "== $lab $(date +%T) tree=$tree $*" >> $K/logs-build.txt
  (cd $tree && TREE=$tree bash /root/probe/d367-buildslot.sh bash port/dreamcast/tools/d367/route/route-build.sh $lab $F $LOOK "$@" >> $K/logs-build.txt 2>&1)
  rc=$?; O=/root/probe/lanes/route/out-$lab
  end=$(/opt/toolchains/dc/sh-elf/bin/sh-elf-nm $O/re4dc-game.elf 2>/dev/null | awk '$3=="_end"{print $1}')
  echo "rc=$rc $lab $(cut -c1-16 $O/elf.sha256 2>/dev/null) $(( $(date +%s) - t0 ))s missing=$(wc -c < $O/missing.txt 2>/dev/null) end=$end $(cd $tree && git rev-parse --short=8 HEAD) $*" | sed 's/PS2_LEON_DIR=[^ ]* //;s/PS2_GANADO_DIR=[^ ]* //' | tee -a $K/logs-build.txt | cut -c1-400
  echo "$end" > $O/end.txt; }
L=${LP:-t11}
for x in "$@"; do case $x in
  tP)  b ${L}tP  $T $ON $T11 IMAGE_PAD_BYTES=0 $PL ;;
  tW)  b ${L}tW  $T $ON $T11 IMAGE_PAD_BYTES=0 $WP ${XON:-} ;;
  mW)  b ${L}mW  $T $ON $T11 IMAGE_PAD_BYTES=0 $WP $MC ${XON:-} ;;
  tT)  b ${L}tT  $T $ON $T11 IMAGE_PAD_BYTES=${PAD_T:-0} $TR ${XON:-} ;;
  kP)  b ${L}kP  $T $ON IMAGE_PAD_BYTES=0 $PL ;;
  kW)  b ${L}kW  $T $ON IMAGE_PAD_BYTES=0 $WP ;;
  kmW) b ${L}kmW $T $ON IMAGE_PAD_BYTES=0 $WP $MC ;;
  kT)  b ${L}kT  $T $ON IMAGE_PAD_BYTES=${PAD_K:-0} $TR ;;
  *) echo "arm? $x" ;;
esac; done
