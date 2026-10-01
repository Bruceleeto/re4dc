#!/bin/bash
# ps2_cast pipeline driver (run from Git Bash on the Windows host): every stage for the given presets, then
# the cast dir and a cast_bundle.py bundle (the cl lane's bundle maker, unchanged) of all of them.
#   ps2_cast_run.sh <store dir (Windows path)> <preset>...
# e.g. ps2_cast_run.sh "C:/Game Dev/Emulators/re4-assets-private/ps2cast-20260930" ganado-em15-00
# Stage 1 (Windows Python) ps2_cast.py convert; stage 2 (WSL) ps2_cast_native.sh; finish; castdir;
# bundle: <store>/bundle-<tag> (tag = BUNDLE_TAG, default the presets joined) via cast_bundle.py.
set -euo pipefail
STORE=$1; shift
TOOLS='//wsl.localhost/Ubuntu-24.04/root/work/lanes/ps2cast/port/dreamcast/tools'
TOOLS_WSL=/root/work/lanes/ps2cast/port/dreamcast/tools
CAST=${CAST_POSES:-C:/Game Dev/Emulators/re4-assets-private/cast-20260925}
CB=${CAST_BUNDLE:-/root/probe/d367-agents/coarse-actors-4k/tools/cast_bundle.py}
to_wsl() { echo "$1" | sed -E 's#^([A-Za-z]):#/mnt/\L\1#; s#\\#/#g'; }
outs=()
for p in "$@"; do
  o="$STORE/$p"
  poses="$CAST/$p/pose-samples.json"; [ -f "$poses" ] || poses="$CAST/ganado-em15-00/pose-samples.json"
  python "$TOOLS/ps2_cast.py" convert "$p" "$o" --poses "$poses"
  MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -- bash "$TOOLS_WSL/ps2_cast_native.sh" "$(to_wsl "$o")"
  python "$TOOLS/ps2_cast.py" finish "$o"
  outs+=("$o")
done
python "$TOOLS/ps2_cast.py" castdir "$STORE/cast" "${outs[@]}"
tag=${BUNDLE_TAG:-$(IFS=+; echo "$*")}
B="$(to_wsl "$STORE")/bundle-$tag"
MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -- bash -c "rm -rf '$B' && python3 '$CB' '$(to_wsl "$STORE")/cast' '$B'"
