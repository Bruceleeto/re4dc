#!/bin/bash
# install.sh [--uninstall]  (WSL; lane stage-ext4 2026-10-14)
# Puts the ext4 + disc-cache staging behind the harness's own stage-scenario.py, so every caller that runs
# `cd "$HW" && python3 stage-scenario.py ...` (t-run.sh, route-run.sh, look.sh, enc/crowd/ps2rooms/hwready scripts)
# gets it without edits. The previous script is kept as stage-scenario-copy.py; RE4DC_STAGE_EXT4=0 runs it.
# --uninstall puts the previous script back.
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
HW=${RE4DC_HARNESS:-"/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"}
DERIVED=5c3d19e1e6cc3b5d627335a3f8212a791271bd5a32cc489cc734f87d292d1d7b
cd "$HW"
if [ "${1:-}" = --uninstall ]; then
  [ -f stage-scenario-copy.py ] || { echo "not installed"; exit 1; }
  cp stage-scenario-copy.py stage-scenario.py.tmp && mv stage-scenario.py.tmp stage-scenario.py
  echo "restored stage-scenario.py ($(sha256sum stage-scenario.py | cut -c1-16)); stage-ext4/ and stage-scenario-copy.py left in place"
  exit 0
fi
if [ ! -f stage-scenario-copy.py ]; then
  [ "$(sha256sum stage-scenario.py | cut -c1-64)" = $DERIVED ] || { echo "stage-scenario.py is not the derived version; re-derive first"; exit 1; }
  cp -p stage-scenario.py stage-scenario-copy.py
fi
[ "$(sha256sum stage-scenario-copy.py | cut -c1-64)" = $DERIVED ] || { echo "stage-scenario-copy.py changed"; exit 1; }
mkdir -p stage-ext4
for f in stage_scenario.py disccache.py; do cp "$here/$f" stage-ext4/$f.tmp && mv stage-ext4/$f.tmp stage-ext4/$f; done
(cd "$here" && echo "installed $(date -Is) from $(git rev-parse HEAD) $(git status --short . | wc -l) dirty") > stage-ext4/INSTALLED-FROM.txt
cp "$here/harness-shim.py" stage-scenario.py.tmp && mv stage-scenario.py.tmp stage-scenario.py
echo "installed: stage-scenario.py -> stage-ext4/stage_scenario.py (RE4DC_STAGE_EXT4=0 -> stage-scenario-copy.py)"
