#!/bin/bash
E=/mnt/c/Flycast-Evidence/re4-dreamcast
T=$E/storemiss-20261015/tools
NM=$(ls /opt/toolchains/dc/sh-elf/bin/*-nm 2>/dev/null | head -1)
[ -z "$NM" ] && NM=$(find /opt/toolchains/dc -name 'sh-elf-nm' | head -1)
$NM -C /root/probe/lanes/route/out-skm0rW/re4dc-game.elf > /tmp/storemiss-nm.txt
for s in c0 h0; do echo "== $s"; python3 $T/rank.py /tmp/storemiss-nm.txt $E/sh4zam-skin-20261015/hwmodel-$s/proj 20; done
