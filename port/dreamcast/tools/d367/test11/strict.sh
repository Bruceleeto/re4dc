#!/bin/bash
# strict.sh <ref run name> <test run name> [out name] (WSL): STRICT (logic_trace_diff.py, frame alignment) and decisions
# (decision_cmp.py) of two t11 trace runs in C:\Flycast-Evidence\re4-dreamcast\t11-20261014\<name>\capture\run-output.txt.
# Writes <evidence>/strict/<out>-raw.json, -raw.txt (verdict) and -dcmp.txt; prints both verdicts and s30 frames.
E=/mnt/c/Flycast-Evidence/re4-dreamcast/t11-20261014
G=$(cd "$(dirname "$0")/../../game30" && pwd)
R=$E/$1/capture/run-output.txt; C=$E/$2/capture/run-output.txt; O=$E/strict/${3:-$1-vs-$2}
mkdir -p $E/strict
for f in $R $C; do grep -q 'LOG OVERRUN' $f && echo "INVALID: LOG OVERRUN in $f"; done
python3 $G/logic_trace_diff.py $R $C --align frame --json $O-raw.json > $O-raw.txt 2>&1
python3 -c "import json,sys;j=json.load(open(sys.argv[1]));fd=j.get('first_divergence') or {};print('STRICT verdict',j.get('verdict'),'compared',j.get('compared'),'masked',j.get('masked'),'first',fd.get('ref_frame'),list((fd.get('fields') or {}).keys())[:6])" $O-raw.json
python3 $G/decision_cmp.py $R $C --align frame > $O-dcmp.txt 2>&1; head -2 $O-dcmp.txt
for f in $R $C; do echo "s30 $(grep -a -o 'route movie terminal=[0-9] id=10030 frames=[0-9/]*' $f | tail -1)  $(grep -ac 'LOG OVERRUN' $f) overruns"; done
