#!/bin/bash
# gdiboot.sh <package dir (Git Bash path)> <name> [play label, default t8tP]: boot the package's gdemu/disc.gdi in Flycast
# for 150 s (zipboot.py); the play build's syms.txt locates the log; track copies are deleted after.
PKG=$1; N=$2; LAB=${3:-t10stP}
LOG=/c/Flycast-Evidence/re4-dreamcast/t10s-20261014
H="/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
SYMS='\\wsl.localhost\Ubuntu-24.04\root\probe\lanes\route\out-'$LAB'\syms.txt'
cd "$H" && python "$(cygpath -w /c/Flycast-Evidence/re4-dreamcast/t10s-20261014/_tools/zipboot.py)" "$(cygpath -w "$PKG")" "$(cygpath -w $LOG/$N)" "$SYMS" --seconds 150 --period 30
rm -f $LOG/$N/track0*.bin $LOG/$N/track02.raw
f=$LOG/$N/run-output.txt
echo "gdiboot $N halt=$(grep -ac HALT $f) misalign=$(grep -ac MISALIGN $f) lines=$(wc -l < $f) title=$(grep -ac -i 'title' $f)"
