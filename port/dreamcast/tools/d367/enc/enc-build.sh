#!/bin/bash
# enc-build.sh <label> [make knobs...]  (lane enc, 2026-09-30)
# Measurement ELF of the current play recipe from this tree: tools/d367/build-r21.sh + the play flags
# (D367_PLAY_BUILD_CHECKLIST.md "Play build rules") with PACE_MODE=off (every tick renders, so a hwproject frame
# is one tick of work), DBG_WARP=1 (warp twin), PC_SAMPLER=1 (hwproject frame marks) and, by default,
# ENC_CENSUS=1 (the per-frame Ganado census line). Extra knobs override (e.g. ENC_CENSUS=0).
# Output /root/probe/lanes/enc/out-<label> (fresh objdir), packaged for the playability harness as
# programs/candidate-enc<label> + programs-enc.json (new files only).
set -euo pipefail
L=$1; shift
T=$(cd "$(dirname "$0")/../../../../.." && pwd)
E=/root/probe/lanes/enc
H="/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1"
SRC="/mnt/c/Game Dev/Emulators/re4-assets-private/play-actor-bundle-20260928"
A=$E/assets/play-actor-bundle-20260928
# build-r21.sh passes ASSETS unquoted to make: use an ext4 copy verified against the bundle's SHA256SUMS.
if [ ! -f $A/.verified ]; then
  mkdir -p $A; cp "$SRC"/* $A/
  (cd $A && sha256sum -c SHA256SUMS) && touch $A/.verified
fi
O=$E/out-$L; rm -rf $O; mkdir -p $O
PLAY="LOGIC_TRACE=0 GAME_DECISION_TRACE=0 ACTOR_TRANSACTION_DIAG=0 GAME_PWC_DIAG=1 ARENA_FIT_KOS_BYTES=147456 QUALITY_PICKER=0"
( cd $T && ASSETS=$A OBJDIR=$O/obj OUT=$O bash /root/probe/d367-buildslot.sh \
    bash port/dreamcast/tools/d367/build-r21.sh $PLAY PACE_MODE=off DBG_WARP=1 PC_SAMPLER=1 ENC_CENSUS=1 "$@" ) \
  > $O/build.log 2>&1 || { tail -30 $O/build.log; exit 1; }
[ -s $O/obj/missing.txt ] && { echo "missing symbols:"; cat $O/obj/missing.txt; }
TOOL=/opt/toolchains/dc/sh-elf/bin
ELF=$O/re4dc-game.elf
sha256sum $ELF > $O/elf.sha256
(cd $T && git rev-parse HEAD && git status --short) > $O/stack.txt
echo "$PLAY PACE_MODE=off DBG_WARP=1 PC_SAMPLER=1 ENC_CENSUS=1 $*" > $O/candidate.txt
# Harness program dir (as prepare-r21.py): scrambled 1ST_READ.BIN, the overlay, the log symbols.
P="$H/programs/candidate-enc$L"
rm -rf "$P"; mkdir -p "$P"
$TOOL/sh-elf-objcopy -R .stack -O binary $ELF $O/prog.bin
/root/work/kos/utils/scramble/scramble $O/prog.bin "$P/1ST_READ.BIN"
cp $O/sscrn.ovl "$P/sscrn.ovl"
python3 - "$ELF" "$O/sscrn.ovl" "$P" "$H/programs-enc.json" "candidate-enc$L" <<'PY'
import hashlib, json, subprocess, sys
from pathlib import Path
elf, ovl, out, pj, arm = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4]), sys.argv[5]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
syms = {}
for line in subprocess.check_output(['/opt/toolchains/dc/sh-elf/bin/sh-elf-nm', '-S', str(elf)], text=True).splitlines():
    f = line.split()
    if len(f) == 4 and f[-1] in ('_re4dc_logbuf', '_re4dc_log_head', '_re4dc_stage', '_re4dc_pcs'):
        syms[f[-1]] = int(f[0], 16)
assert len(syms) == 4, syms
(out / 'syms.txt').write_text(' '.join(hex(syms[n] - 0x8c000000) for n in ('_re4dc_logbuf', '_re4dc_log_head', '_re4dc_stage')) + '\n')
(elf.parent / 'syms.txt').write_text(' '.join(hex(syms[n] - 0x8c000000) for n in ('_re4dc_logbuf', '_re4dc_log_head', '_re4dc_stage', '_re4dc_pcs')) + '\n')
report = json.loads(pj.read_text()) if pj.exists() else {}
report[arm] = dict(elf=str(elf), elf_sha256=sha(elf), overlay_sha256=sha(ovl), symbols=syms,
                   files={p.name: dict(bytes=p.stat().st_size, sha256=sha(p)) for p in out.iterdir() if p.is_file()})
pj.write_text(json.dumps(report, indent=2) + '\n')
PY
rm -f $O/prog.bin
echo "built enc$L $(cut -c1-16 $O/elf.sha256)"
