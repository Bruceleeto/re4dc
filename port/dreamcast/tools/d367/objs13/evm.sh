# wrap=N: native model rejections of wrapping parts whose package size differs from the TPL header
# (objs look check 10-15); a converted room must not exceed its control run.
K=/root/probe/lanes-20261014/objs/tree/port/dreamcast/tools/d367; E=/mnt/c/Flycast-Evidence/re4-dreamcast/objs-20261014
for x in "$@"; do f=$E/$x/capture/run-output.txt; [ -f $f ] || { echo "$x: no run"; continue; }
  tr -d '\0' < $f > /tmp/ev-$x.txt
  echo "$x $(bash $K/texchk/texchk.sh /tmp/ev-$x.txt 2>&1 | grep -o 'TEXCHK [A-Z]*' | tail -1) $(python3 $K/mcheck/leongc_check.py /tmp/ev-$x.txt 2>&1 | grep -o 'LEON-GC [A-Za-z]*' | tail -1) pair_missing=$(grep -ac 'pair missing' /tmp/ev-$x.txt) halt=$(grep -ac 'HALT \|LOG OVERRUN\|CRASH_SCREEN: no new' /tmp/ev-$x.txt) room=$(grep -a -o 'phase=enter room=[0-9a-f]*' /tmp/ev-$x.txt | tail -1) $(grep -a -o 'native model rejection: .* wrap=[0-9]*' /tmp/ev-$x.txt | tail -1 | grep -o 'wrap=[0-9]*')"
done
