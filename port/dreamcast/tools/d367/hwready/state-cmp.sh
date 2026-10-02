# state-cmp.sh <base> <test> (hardware readiness): tick-indexed player state (warp: frame lines minus wall fields), cutscenes, faults
H="/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1/scenarios"
ex(){ O="$H/route-$1/capture/run-output.txt"; grep -a -E "warp: frame |warp: placed|route cutscene:|route movie start:" "$O" | sed -E 's/ (vbl|wall_ms)=[0-9]+//g'; }
b=$(mktemp); t=$(mktemp); ex $1 > $b; ex $2 > $t
n=$(wc -l < $b); m=$(wc -l < $t)
common=$(( n < m ? n : m ))
d=$(diff <(head -$common $b) <(head -$common $t) | grep -c '^<')
echo "$1 vs $2: lines $n/$m, compared $common, differing $d"
diff <(head -$common $b) <(head -$common $t) | head -6
for s in $1 $2; do O="$H/route-$s/capture/run-output.txt"; echo "  $s HALT $(grep -ac HALT "$O") FAULT $(grep -ac 'FAULT code' "$O") MISSING $(grep -ac 'RE4DC MISSING' "$O") TAerr $(grep -aci 'TA.*overflow\|OPB_OUTOFMEM' "$O") POISON $(grep -ac POISON_RAM "$O")"; done
rm -f $b $t
