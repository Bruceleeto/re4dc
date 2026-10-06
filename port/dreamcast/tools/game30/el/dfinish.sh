#!/bin/bash
# (Git Bash) dfinish.sh <name>: after capture-run.out says done: delete the staged image, print key lines.
# A CST=1 run (run dir + stage under C:\Flycast-Evidence\re4-dreamcast\_el-cstage) is moved to the D: evidence root.
N=$1
D=/d/Flycast-Evidence/re4-dreamcast/el-20261005/dyn-$N
G=/d/Flycast-Evidence/re4-dreamcast/_el-stage/perfdyn-$N
CD=/c/Flycast-Evidence/re4-dreamcast/_el-cstage/run/dyn-$N
if [ -d "$CD" ]; then
  grep -q '^done' $CD/capture-run.out 2>/dev/null || { echo "$N not done"; tail -2 $CD/capture-run.out; exit 1; }
  G=/c/Flycast-Evidence/re4-dreamcast/_el-cstage/stage/perfdyn-$N
  cp $G/stage.json $CD/stage.json 2>/dev/null
  rm -f $G/disc/disc.bin
  echo "run dir: C:\\Flycast-Evidence\\re4-dreamcast\\_el-cstage\\run\\dyn-$N (stage on C:), moved here by dfinish.sh" >> $CD/PURPOSE.txt
  [ -e "$D" ] && { echo "$D exists"; exit 1; }
  mkdir -p "$(dirname $D)" && cp -r $CD $D && rm -rf $CD
fi
grep -q '^done' $D/capture-run.out 2>/dev/null || { echo "$N not done"; tail -2 $D/capture-run.out; exit 1; }
cp $G/stage.json $D/stage.json 2>/dev/null
rm -f $G/disc/disc.bin
grep -a -E 'warp:|route movie|room enter|HALT|RE4DC MISSING' $D/run-output.txt | grep -av 'area \|kill watch\|card pulse' > $D/route.txt
echo "$N: route lines $(wc -l < $D/route.txt) halt=$(grep -ac HALT $D/run-output.txt) missing=$(grep -ac 'RE4DC MISSING' $D/run-output.txt)"
