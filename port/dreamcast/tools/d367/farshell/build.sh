#!/bin/bash
# build.sh <room> <pkg dir> <tex.pak> <rtp> <work dir> <out far-shell.fsh> [extra eyes x,y,z ...]  (Git Bash, Windows)
# FAR_SHELL offline build of one room (lane farshell16, 2026-10-16). Steps:
#   1. fs_extract.py: the room's PS2 world package (ps2-world.re4mesh + .r4pw) -> world.npz + decoded textures
#   2. fs_eyes.py: reachable eyes (PS2 enemy route graph + 1.6 m, densified every 3 m between each node and its 4 nearest
#      neighbours under 25 m, plus the extra points given here: warp positions, the boat start)
#   3. fs_blender.py build (Blender 5.2, background): far-seen faces -> decimated material shell -> shell.npz
#   4. fs_pack.py: shell.npz -> FSH1 (runtime platform/far_shell.inc)
#   5. fs_vram.py: texture bytes by closest approach (far-only textures = what a shell proxy could reclaim)
# params/<room>.json: cut 12.5 m, Full far 25 m, 6000 triangles, 12 m cells, max_dev 1.5 m; r10b adds the lake box
# (open-water eyes at boat height). PY / BLENDER override the interpreters.
# v3 eyes as built 10-16:
#   r100: -81362,1500,-50384 -99685,-484,-1343 -112251,-193,-4420 96523,-6771,-8536 -86558,0,-1243 -83382,1100,-34851
#   r101: -7914,0,2000 4012,0,-13300 39372,3201,-26667 -7914,0,-254
#   r10b: -48810,-1000,25500
set -eu
R=$1; PKG=$2; PAK=$3; RTP=$4; W=$5; OUT=$6; shift 6
H=$(cd "$(dirname "$0")" && pwd)
PY=${PY:-python}
BLENDER=${BLENDER:-"/c/Program Files/Blender Foundation/Blender 5.2/blender.exe"}
mkdir -p "$W"
$PY "$H/fs_extract.py" "$PKG" "$PAK" "$W"
$PY "$H/fs_eyes.py" "$R" "$RTP" "$W" "$@" --densify 3000 25000
cp "$H/params/$R.json" "$W/params.json"
"$BLENDER" -b --factory-startup --python "$H/fs_blender.py" -- build "$W" "$W/params.json"
$PY "$H/fs_pack.py" "$W" "${R#r}" "$OUT"
$PY "$H/fs_vram.py" "$W" "$PAK" 12500
