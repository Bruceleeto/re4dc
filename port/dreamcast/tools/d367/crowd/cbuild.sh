#!/bin/bash
# Lane crowd: build one arm of the play recipe (tools/d367/build-r21.sh) from this tree.
#   MODE=rel   (default) release measurement build: LOGIC_TRACE=0 GAME_DECISION_TRACE=0 ACTOR_TRANSACTION_DIAG=0
#              GAME_PWC_DIAG=0 PC_SAMPLER=1 PC_SAMPLER_BYTES=8192 (hwproject needs the sampler's frame word)
#   MODE=trace STRICT gate build: LOGIC_TRACE=1 (recipe default) ARENA_FIT_KOS_BYTES=147456
#   cbuild.sh <label> [extra make knobs...]
# Output /root/probe/lanes/crowd/build-<label>/{re4dc-game.elf,sscrn.ovl,elf.sha256,flags.txt,stack.txt,build.log};
# objdir /root/probe/lanes/crowd/obj-<label> is always fresh (a seeded objdir keeps stale objects).
set -euo pipefail
L=${1:?label}; shift
MODE=${MODE:-rel}
EV=/root/probe/lanes/crowd
ROOT=$(cd "$(dirname "$0")/../../../../.." && pwd)
BUNDLE="/mnt/c/Game Dev/Emulators/re4-assets-private/play-actor-bundle-20260928"
# build-r21.sh passes the asset dir unquoted to make: use a space-free ext4 copy, verified against the bundle's sums.
ASSETS=${ASSETS:-$EV/assets-play-actor-bundle-20260928}
[ -d "$ASSETS" ] || { mkdir -p "$ASSETS"; cp "$BUNDLE"/* "$ASSETS"/; }
(cd "$ASSETS" && sha256sum -c --quiet "$BUNDLE/SHA256SUMS") || { echo "asset bundle SHA256SUMS mismatch"; exit 1; }
OUT=$EV/build-$L OBJ=$EV/obj-$L
rm -rf "$OBJ" "$OUT"; mkdir -p "$OBJ" "$OUT"
case $MODE in
  rel) M="LOGIC_TRACE=0 GAME_DECISION_TRACE=0 ACTOR_TRANSACTION_DIAG=0 GAME_PWC_DIAG=0 PC_SAMPLER=1 PC_SAMPLER_BYTES=8192" ;;
  trace) M="ARENA_FIT_KOS_BYTES=147456" ;;
  *) echo "MODE rel|trace"; exit 2 ;;
esac
echo "$L MODE=$MODE $M $*" > "$OUT/flags.txt"
{ git -C "$ROOT" rev-parse HEAD; git -C "$ROOT" status --porcelain; } > "$OUT/stack.txt"
# shellcheck disable=SC2086
ASSETS="$ASSETS" OBJDIR="$OBJ" OUT="$OUT" /root/probe/d367-buildslot.sh bash "$ROOT/port/dreamcast/tools/d367/build-r21.sh" $M "$@" \
  > "$OUT/build.log" 2>&1 || { echo "BUILD FAILED $L"; grep -E 'error|Error' "$OUT/build.log" | head -20; tail -5 "$OUT/build.log"; exit 1; }
sha256sum "$OUT/re4dc-game.elf" | tee "$OUT/elf.sha256"
MISS=$(ls "$OBJ"/missing.txt 2>/dev/null || true)
[ -n "$MISS" ] && { echo "missing symbols:"; head -5 "$MISS"; } || true
