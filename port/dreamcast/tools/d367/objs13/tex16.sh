#!/bin/bash
# tex16.sh (Git Bash, Windows python): PS2 pictures (ps2_objects_tex.py v2, material pairs) for the test 13 object dars
# work/out/<room>t (gen13: geometry minus breakables + items pack) proven against the test 12 tex.pak (tex-t12d.pak).
# Output work/out/<room>x/<room>.dar + tex/ (loose <key>.re4tex).
WS=//wsl.localhost/Ubuntu-24.04
T=$WS/root/probe/lanes-20261014/objs/tree/port/dreamcast/tools
O=$WS/root/probe/lanes-20261014/objs/work/out
PAK=$WS/root/probe/lanes-20261014/t12rc/data/tex-t12d.pak
GI="C:/Game Dev/Emulators/Resident Evil 4 Debug (Disc 1)/Resident Evil 4 Debug (Disc 1).iso"
PI="C:/Game Dev/Emulators/re4_helpers/Resident Evil 4 (USA)/Resident Evil 4 (USA).iso"
cd "$T" || exit 1
for r in "$@"; do  # 10-15 v3: shared GC pictures kept (default)
  MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -u root -e mkdir -p /root/probe/lanes-20261014/objs/work/out/${r}x/tex; mkdir -p /c/tmp/objs/tex16
  python ps2_objects_tex.py --room $r --dar "$O/${r}t/$r.dar" --report "$O/${r}g/report.json" --out "$O/${r}x/$r.dar" \
    --texdir "$O/${r}x/tex" --json "$O/${r}x/tex.json" --pak "$PAK" --gc-room "C:/tmp/objs/gcroom/$r.arc" \
    --gc-iso "$GI" --ps2-iso "$PI" > /c/tmp/objs/tex16/$r.log 2>&1
  echo "$r rc=$? $(tail -1 /c/tmp/objs/tex16/$r.log | cut -c1-150)"
done
