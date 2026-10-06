#!/bin/bash
# ib.sh <label> [make knobs...]: one route-build arm of lane el (exp/el-20261005) from /root/probe/lanes-20261005/el/tree.
# Never two builds in this tree at once (they share game/obj/overlay-b.elf): chains run serially.
set -u
T=/root/probe/lanes-20261005/el/tree
W=/root/probe/lanes-20261005/el
L=$1; shift
mkdir -p $W/logs
export MAKEFLAGS=-j4 SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-1759300000}
t0=$(date +%s)
TREE=$T /root/probe/d367-buildslot.sh bash $T/port/dreamcast/tools/d367/route/route-build.sh $L "$@" > $W/logs/build-$L.log 2>&1
rc=$?
O=/root/probe/lanes/route/out-$L
echo "$L rc=$rc $(( $(date +%s) - t0 )) s head=$(git -C $T rev-parse --short HEAD) dirty=$(git -C $T status --short | wc -l) $(tail -1 $W/logs/build-$L.log) missing=$(cat $O/missing.txt 2>/dev/null | wc -l)"
