#!/bin/bash
# t13-build.sh <arm>...: test 13 build arms (t13/rc, 2026-10-15; scope C:\Game Dev\Emulators\TEST13-SCOPE.md) = the test 12.2
#   recipe (test12/t12-build.sh arm uP: ON + T11REC + T12REC + T122, unchanged) + the test 13 knobs ($T13). Every test 13
#   knob is default 0 in the Makefiles: with T13="" (arm kP) the play image must be byte-identical to test 12.2's
#   (objcopy -R .stack image fcedaecf, out-t122auP, tag test-2602b5c3-20261015).
# Arms: rP release play (packaged by test13/t13-package.sh), rW warp, mW warp + MCHECK_LEONGC=1 TEX_CHECK=2, rT trace,
#       gT trace of the render-only test 13 knobs (T13 without the gameplay umbrella PS2_CH1_ENEMY: STRICT vs kT),
#       gW warp of the same (the decisions control for PS2_CH1_ENEMY, ALIVECAP-20261015.md), kP knob-off play (identity
#       vs 12.2), kT knob-off trace. The benchmark disc variant is benchpub/bench-build.sh with BASE=out-<LP>rP.
# Env: T (tree, default $K/tree), LP (label prefix, default t13rc), T13 (test 13 knobs, default T13REC), XON (extra knobs,
#      test only), PAD_T / PAD_K (trace image pads).
# The data set must match: T13_DATA in test11/t11-fix.py (tex.pak = test13/t13-texpak.sh).
set -u
K=${K:-/root/probe/lanes-20261015/t13rc}
T=${T:-$K/tree}
export SOURCE_DATE_EPOCH=1760000000
F="PACE_DEBUG=1 ROUTE_CH13=1 ROUTE_CH21=1 SBB_STUB=1 PVR_READY_STRICT=1 ACT_CAP=0 PS2_INTERIOR_ACTORS=2 GAME_ATLIST_OVERFLOW=1 GAME_ATLIST_512=1 LEON_NATIVE_PIPE=0 LEON_FACE_LAZY=0 NATIVE_LASER=1 ACTOR_GANADO_SOURCE_LIGHT=0 PRIM_CAP_R10B=327680"
LOOK="EFFECT_PS2_TOGGLE=1 LOOK_TOGGLE=1 FILTER00_DC=1 CHARBAKE_TOGGLE=1 CHARBAKE_HAIR=0"
PS2="PS2_LEON=1 PS2_LEON_DIR=/root/probe/lanes-20261011/pl08/assets/arm-a ACTOR_PL08_PACK=1 PS2_GANADO=1 PS2_GANADO_DIR=/root/probe/lanes-20261010/ps2cast-all-assets/pg5 PS2_GANADO_F=1 PS2_GIGANTE=1 PS2_DELLAGO=1 PS2_VERTEX_ALPHA=1"
P2="MOVIE_DISC_QUIET=1 EFFECT_HAZE_LEAN=3 EFFECT_HAZE_LEAN_TOGGLE=0 RENDER_OPTION=1 PS2_GANADO_LIT=1 CAST_MIPMAP=1 PS2_CROW=1 PS2_ANIMALS=1 PS2_WOLF=1 HEAP4_PARTS_RESERVE=1 DVD_READ_SAFE=1 LAKE_RIPPLES=1 VGA_SOFT=1 LETTERBOX_CLIP=1 PS2_PT_CUTOUT=1 PACE_VMU=1 PACE_VMU_GPU=1 UI_FRAG_RESERVE=1"
T9K="DOOR_FREEZE=1 LOAD_INDICATOR=1 VMU_CONTEXT=1 OPTION_ROW_STYLE=1 PT_BLEND_FIX=1 MODEL_STREAM_FIX=1 SS_MENU_ANIM_RT=1 PS2_ENEMY_RULES=1 ACT_CAP_TABLE=1 RENDER_QUALITY_ONLY=1 RESET_HEAP_FIX=1"
HANDS="LEON_HAND_POSES=1 LEON_HAND_PACK=1 LEON_SKIN_SLOTS=1"
T11REC="PS2_R100_SMX=1 PS2_R100_TR4=1 LAKE_ZBIAS=1.001 WORLD_HOLE_FIX=1 SPEED_VMU_OFF=2 TEX_REF_SELFKEY=1 MOVIE_HEAP_PREFLIGHT=1 PS2_FX_ROOMS=1 PS2_FX_STAGE1=1 PS2_FX_POPULATION=1 PS2_FX_ADDITIONS=1 PS2_FX_ROOMS_EXT=1 EFFECT_TORCH=1 RAIN_PS2=1 ACTOR_PROBE_LIGHT=1 LEON_SOURCE_LIGHT=1 LEON_LIGHT_HEADROOM=1 PS2_ENEMY_ROOMS=0x3f MV_SHADOWS=1"
T12REC="UI_SOURCE_LRU=1 HW_FOG_HAZE=1 FX_SPRITE_TRIM=2 TEX_PAL4_ALPHA=1 FX_PS2_PACK=1 FX_FLIPBOOK=2 R101_ALIVE_CAP=6 TEX_WRAP_SAFE=1 PS2_CAST_MERCHANT=1 ACTOR_GANADO_APP0_GRIP=1 RENDER_FSAA=1 GC_STUB_SKIP=1 OWNER_SETUP_LEAN=1 TEX_IDENT_LEAN=1 PS2_WORLD_LEAN=23 PS2_STRIP_GROUPS=1 PS2_ROOM_PIN=1 LEON_LIGHT_FILL=45 VRAM_ROOM_LOG=1 EFM_PS2_CUT=1 STATIC_OBJ_BATCH=2 TEX_META_EVICT=1 PRELOAD_LARGE_FIRST=1 ROOM_RESIDENT=1 SS_FREEZE_RESERVE=1 DCINV_PURGE=1 MAPLE_RECV_PURGE=1 ARENA_FIT_KOS_BYTES=196608"
T122="RETIRE_KOS_FLOOR=65536"
# Test 13 knobs (TEST13-SCOPE.md items 1..5; item 6 = T13_6 when it lands; item 7 is a tool):
#   1 STATIC_OBJ_BAKE=1 + PS2_PLACE_GATE=1 (lane crowd12-t13 ce0b7a82; render only; data bake13)
#   3 PS2_ASHLEY=2 PS2_ASHLEY_ROOMS=1 (lane ps2cast3 d940cbc0; render only; data ashley13; user choice B: PS2 model, rest face)
#   4 PS2_CH1_ENEMY=1 (lane alivecap-1015 659f2280; GAMEPLAY by design: PS2 chapter 1 enemy rules + ALIVE_CAP=6 +
#     ALIVE_CAP_PARK + R101_CAP_WAVES; gated by the decisions check of ALIVECAP-20261015.md, not by STRICT)
#   5 GAME_LQ_MEMO=1 (exact, logic; STRICT), LEON_FACE_LAZY=1 (exact, render), PS2_AREA_HIDE=1 (r107, render only)
#     (the GC render census removals of item 5 were never built: no knob)
#   2 objs13 is data only (objs13d)
T13R="STATIC_OBJ_BAKE=1 PS2_PLACE_GATE=1 PS2_ASHLEY=2 PS2_ASHLEY_ROOMS=1 GAME_LQ_MEMO=1 LEON_FACE_LAZY=1 PS2_AREA_HIDE=1"
T13G="PS2_CH1_ENEMY=1"
T13_6=${T13_6:-}
T13REC="$T13R $T13G $T13_6"
T13=${T13-$T13REC}
ON="$T9K PVR_LATCH=2 PVR_RECOVER=1 TA_HEADROOM=1 CRASH_TASK_DETAIL=1 $PS2 $P2 $HANDS"
BASE="$ON $T11REC $T12REC $T122"
MC="MCHECK_LEONGC=1 TEX_CHECK=2"
TR="DBG_WARP=1 PC_SAMPLER=1 LOGIC_TRACE=1 GAME_DECISION_TRACE=1 PACE_MODE=off TRACE_SS_MASK=1 TRACE_ALLOC=1 CODEC_READY_FIXTURE=1"
WP="DBG_WARP=1 PC_SAMPLER=1"
PL="DBG_WARP=0 PC_SAMPLER=0"
b() { lab=$1; tree=$2; shift 2; t0=$(date +%s); echo "== $lab $(date +%T) tree=$tree $*" >> $K/logs-build.txt
  (cd $tree && TREE=$tree bash /root/probe/d367-buildslot.sh bash port/dreamcast/tools/d367/route/route-build.sh $lab $F $LOOK "$@" >> $K/logs-build.txt 2>&1)
  rc=$?; O=/root/probe/lanes/route/out-$lab
  end=$(/opt/toolchains/dc/sh-elf/bin/sh-elf-nm $O/re4dc-game.elf 2>/dev/null | awk '$3=="_end"{print $1}')
  echo "rc=$rc $lab $(cut -c1-16 $O/elf.sha256 2>/dev/null) $(( $(date +%s) - t0 ))s missing=$(wc -c < $O/missing.txt 2>/dev/null) end=$end $(cd $tree && git rev-parse --short=8 HEAD) $*" | sed 's/PS2_LEON_DIR=[^ ]* //;s/PS2_GANADO_DIR=[^ ]* //' | tee -a $K/logs-build.txt | cut -c1-400
  echo "$end" > $O/end.txt; }
L=${LP:-t13rc}
mkdir -p $K
for x in "$@"; do case $x in
  rP)  b ${L}rP  $T $BASE $T13 IMAGE_PAD_BYTES=0 $PL ;;
  rW)  b ${L}rW  $T $BASE $T13 IMAGE_PAD_BYTES=0 $WP ${XON:-} ;;
  mW)  b ${L}mW  $T $BASE $T13 IMAGE_PAD_BYTES=0 $WP $MC ${XON:-} ;;
  gW)  b ${L}gW  $T $BASE $T13R $T13_6 IMAGE_PAD_BYTES=0 $WP ${XON:-} ;;
  rT)  b ${L}rT  $T $BASE $T13 IMAGE_PAD_BYTES=${PAD_T:-0} $TR ${XON:-} ;;
  gT)  b ${L}gT  $T $BASE $T13R $T13_6 IMAGE_PAD_BYTES=${PAD_T:-0} $TR ${XON:-} ;;
  kP)  b ${L}kP  $T $BASE IMAGE_PAD_BYTES=0 $PL ;;
  kT)  b ${L}kT  $T $BASE IMAGE_PAD_BYTES=${PAD_K:-0} $TR ${XON:-} ;;
  *) echo "arm? $x" ;;
esac; done
