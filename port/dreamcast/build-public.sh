#!/usr/bin/env bash
# build-public.sh [extra make knobs...]: the play program from the public repository alone.
#
# Builds the current test recipe (tools/d367/build-r21.sh plus the knobs of the r22j test 7 play build)
# with the neutral headers of game/public-assets in place of the maintainers' private asset bundle, and
# with the knobs that need other private directories (the PS2 character arms) off. See CONTRIBUTING-PORT.md.
#
# Output (OUT, default port/dreamcast/out-public): re4dc-game.elf, the room overlays (*.ovl) linked
# against it, resolved-knobs.txt (every knob as make resolved it) and build.log. Put it on a disc with
#   python3 port/dreamcast/tools/swap-program.py <release zip> <OUT> <new disc dir>
#
# Env: RE4DC_KOS_BASE / RE4DC_KOS_CC_BASE (from setup-toolchain.sh's env.sh or the Docker image),
#      OUT, OBJDIR (default OUT/obj; always rebuilt from scratch), JOBS (default 4),
#      ASSETS (default game/public-assets; the maintainers point it at the private bundle).
# Extra arguments are make knobs and override the recipe, e.g. MY_FEATURE=1.
set -euo pipefail
PORT=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
OUT=${OUT:-$PORT/out-public}
OBJDIR=${OBJDIR:-$OUT/obj}
ASSETS=${ASSETS:-$PORT/game/public-assets}
case "$OUT$OBJDIR$ASSETS" in *' '*) echo "build-public: OUT, OBJDIR and ASSETS must not contain spaces" >&2; exit 2 ;; esac
: "${RE4DC_KOS_BASE:?source the toolchain env first (tools/setup-toolchain.sh writes PREFIX/env.sh)}"
[ -f "$RE4DC_KOS_BASE/lib/dreamcast/libkallisti.a" ] || { echo "build-public: $RE4DC_KOS_BASE is not a built KOS" >&2; exit 2; }
rm -rf "$OBJDIR"; mkdir -p "$OUT" "$OBJDIR"
rm -f "$OUT"/re4dc-game.elf "$OUT"/*.ovl

# The play knobs of the release build (route/route-build.sh PLAY, test 7 t7-build.sh F, LOOK and ON, play twin).
PLAY="LOGIC_TRACE=0 GAME_DECISION_TRACE=0 ACTOR_TRANSACTION_DIAG=0 GAME_PWC_DIAG=1 ARENA_FIT_KOS_BYTES=147456 QUALITY_PICKER=0 PACE_MODE=fast"
T7="PACE_DEBUG=1 ROUTE_CH13=1 ROUTE_CH21=1 SBB_STUB=1 PVR_READY_STRICT=1 ACT_CAP=0 PS2_INTERIOR_ACTORS=2 GAME_ATLIST_OVERFLOW=1 GAME_ATLIST_512=1 LEON_NATIVE_PIPE=0 LEON_FACE_LAZY=0 NATIVE_LASER=1 ACTOR_GANADO_SOURCE_LIGHT=0 PRIM_CAP_R10B=327680"
LOOK="EFFECT_PS2_TOGGLE=1 LOOK_TOGGLE=1 FILTER00_DC=1 CHARBAKE_TOGGLE=1 CHARBAKE_HAIR=0"
ON="PVR_LATCH=2 PVR_RECOVER=1 TA_HEADROOM=1 CRASH_TASK_DETAIL=1"
# Off in the public build: these compile private generated meshes (PS2_LEON_DIR, PS2_GANADO_DIR).
PRIVATE_OFF="PS2_LEON=0 PS2_GANADO=0 PS2_GANADO_F=0 PS2_GIGANTE=0 PS2_DELLAGO=0 PS2_VERTEX_ALPHA=0"
# A maintainer asset pack (ASSETS with ps2leon/ and ps2ganado/ beside the actor bundle) turns them on as the
# release does, so the program is the release recipe's.
if [ -f "$ASSETS/ps2leon/ps2leon_runtime.h" ] && [ -f "$ASSETS/ps2ganado/ganado_cast_runtime.h" ]; then
  PRIVATE_OFF="PS2_LEON=1 PS2_LEON_DIR=$ASSETS/ps2leon ACTOR_PL08_PACK=1 PS2_GANADO=1 PS2_GANADO_DIR=$ASSETS/ps2ganado PS2_GANADO_F=1 PS2_GIGANTE=1 PS2_DELLAGO=1 PS2_VERTEX_ALPHA=1"
  echo "build-public: PS2 character arms from $ASSETS"
fi
PL="DBG_WARP=0 PC_SAMPLER=0 IMAGE_PAD_BYTES=0"

# The release builds pin __DATE__ / __TIME__ (the crash screen prints them) to this instant.
export SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-1760000000}
t0=$(date +%s)
echo "build-public: ASSETS=$ASSETS OUT=$OUT"
# shellcheck disable=SC2086
ASSETS=$ASSETS OBJDIR=$OBJDIR OUT=$OUT JOBS=${JOBS:-4} \
  bash "$PORT/tools/d367/build-r21.sh" $PLAY $T7 $LOOK $ON $PRIVATE_OFF $PL "$@" > "$OUT/build.log" 2>&1 ||
  { tail -40 "$OUT/build.log"; echo "build-public: FAILED (full log $OUT/build.log)" >&2; exit 1; }
MISSING=$PORT/game/obj/missing.txt
if [ -s "$MISSING" ]; then
  cp "$MISSING" "$OUT/missing.txt"
  echo "build-public: unresolved symbols (they link to silent stubs):"; cat "$OUT/missing.txt"
fi
ls "$OUT"/re4dc-game.elf "$OUT"/*.ovl >/dev/null
(cd "$OUT" && sha256sum re4dc-game.elf ./*.ovl > SHA256SUMS)
echo "build-public: ok in $(( $(date +%s) - t0 )) s"
cat "$OUT/SHA256SUMS"
