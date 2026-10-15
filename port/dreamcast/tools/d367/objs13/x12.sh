#!/bin/bash
# x12.sh: hw-model (MODELLED) cross vs wall views on the published test 12 recipe + DBG_WARP (t12c2tW 3fb11639)
R=/root/probe/lanes-20261014/objs; cd $R || exit 1
rm -f work/hwlog/stage-hw-x12*.json work/hwlog/run-x12*.txt
for v in cross wall; do
  ( time bash work/o-hw.sh t12c2tW $R/fix/x101-$v-t12c2tW.json hw-x12$v 1000:1119 7 ) > work/hwlog/run-x12$v.txt 2>&1
  tail -3 work/hwlog/run-x12$v.txt
done
