#!/bin/bash
# D367 W10: GDEMU image (GDI) from the same inputs as mkdisc-hardlink.sh.
#   [LAYOUT=standard|legacy] [SECTOR=2352|2048] [PAD_1ST=0|1] [PERIPHERALS=0799810] [PRODUCT=T0000] [TITLE=..] \
#     [INPUT_CHARSET=..] [MKDCDISC=<binary>] mkgdi.sh <elf> <datadir> <outdir> [fixturesdir]
#
# LAYOUT=standard (default; the release disc format from test 15 on, CONTRIBUTING-PORT.md section 8): the standard
# GD-ROM layout, written by the community tool mkdcdisc (-F gdi), pinned at v0.0.4 / 2b98b0d9 (setup-mkdcdisc.sh):
#   track01  LBA 0       MODE1 data, low-density area: 450 sectors, ISO9660 with COPYRIGH.TXT / ABSTRACT.TXT /
#                        BIBLIOGR.TXT and the IP.BIN header in all 16 system sectors (IP0000.BIN)
#   track02  LBA 600     audio, 526 sectors of silence (the "warning" track)
#   track03  LBA 45000   MODE1 data, high-density area: IP.BIN (header, TOC1, SEGA licence code, mkdcdisc's GD-ROM
#                        bootstrap; no licence-screen logo), then the ISO9660 game tree (Rock Ridge names, absolute
#                        extents), padded to LBA 549150 (the end of a real GD-ROM): the files sit at the outer end of
#                        the disc, 1ST_READ.BIN last, 150 sectors before the end.
# The console test of 2026-10-16 (GDEMU, slot 167 "RE4DC Test14 Standard GDI": "new gdi runs fine") ran this layout;
# the users' GDEMU-only failures (#27, LinkOrder) were on the legacy one. The image is checked with disc_lint.py
# (standard profile) before this script returns. Contributors swap their program into it with tools/swap-program.py.
# About 213 MB more on the SD card than the legacy layout (the padding is zeros; zips shrink it away).
#
# LAYOUT=legacy (explicit opt-in, internal benchmark / harness discs only; test releases up to test 14): the old
# genisoimage layout (no TOC1, track01 606 sectors with a README.TXT, track02 at LBA 756, track03 ending with its last
# file, 1ST_READ.BIN first, Joliet + Rock Ridge). It never goes on a test release.
#
# The game tree is built exactly as mkdisc-hardlink.sh builds it (data tree hard-linked, fixtures under /dc/), so the
# CUE and the GDI carry the same files, in both layouts.
#
# Boot chain differences from the CD-R image:
#   - 1ST_READ.BIN is NOT scrambled. The boot ROM descrambles only on a CD-ROM
#     (MIL-CD) disc; on a GD-ROM it loads the binary as is.
#   - IP.BIN Device Info is "GD-ROM1/1".
#   - KOS mounts /cd from the low-density TOC; the game's cdrom_read_toc wrap
#     (game/platform/gdrom_mount.cpp) redirects that to track 3 on a GD-ROM.
#     An ELF built without that wrap boots this image and then cannot open /cd.
#
# SECTOR=2352 (default) writes raw MODE1 tracks with EDC/ECC (the Redump/TOSEC form every GDEMU firmware reads).
# SECTOR=2048 writes .iso data tracks (Flycast reads both; not for the SD card).
set -euo pipefail
here=$(cd "$(dirname "$0")" && pwd)
ELF=${1:?usage: mkgdi.sh <elf> <datadir> <outdir> [fixturesdir]}
DATA=${2:?usage: mkgdi.sh <elf> <datadir> <outdir> [fixturesdir]}
OUTDIR=${3:?usage: mkgdi.sh <elf> <datadir> <outdir> [fixturesdir]}
EXTRA=${4:-}
KOS=${KOS_TOOLS_BASE:-/root/work/kos}
LAYOUT=${LAYOUT:-standard}
SECTOR=${SECTOR:-2352}
# Peripherals (makeip README bit table): VGA box, memory card (VMU),
# Start+A+B+directions, X, Y, analog L/R triggers, analog stick. Add 0x200
# (0799A10) to declare jump pack support once the game drives one.
PERIPHERALS=${PERIPHERALS:-0799810}
PRODUCT=${PRODUCT:-T0000}
TITLE=${TITLE:-RE4DC}
# UTF-8 extracted trees can opt in; retain the legacy source-mirror default.
INPUT_CHARSET=${INPUT_CHARSET:-iso8859-1}
HD_LBA=45000
case "$LAYOUT" in standard|legacy) ;; *) echo "mkgdi: LAYOUT must be standard or legacy" >&2; exit 1 ;; esac
case "$SECTOR" in 2352|2048) ;; *) echo "mkgdi: SECTOR must be 2352 or 2048" >&2; exit 1 ;; esac
[ -d "$DATA" ] || { echo "mkgdi: data directory $DATA missing" >&2; exit 1; }
[ -z "$EXTRA" ] || [ -d "$EXTRA" ] || { echo "mkgdi: fixtures directory $EXTRA missing" >&2; exit 1; }
if [ "$LAYOUT" = standard ]; then
  MKDCDISC=${MKDCDISC:-$(command -v mkdcdisc || echo /root/work/tools/mkdcdisc/builddir/mkdcdisc)}
  [ -x "$MKDCDISC" ] || { echo "mkgdi: no mkdcdisc at $MKDCDISC (build the pinned one: tools/d367/setup-mkdcdisc.sh)" >&2; exit 1; }
  "$MKDCDISC" --help 2>&1 | sed -n 1p | grep -q 'mkdcdisc v0.0.4 ' ||
    { echo "mkgdi: $MKDCDISC is not mkdcdisc v0.0.4 (the release layout is pinned; tools/d367/setup-mkdcdisc.sh)" >&2; exit 1; }
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp}/re4dc-gdi.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
rm -rf "$OUTDIR"
mkdir -p "$WORK/cdroot" "$WORK/t1root" "$OUTDIR"

# 1ST_READ.BIN: raw binary, unscrambled.
# elf2bin can exit 0 without writing the file (2026-10-02, r21l): fall back on an empty result too.
if ! bash "$KOS/utils/elf2bin/elf2bin" "$ELF" "$WORK/prog.bin" >/dev/null 2>&1 || [ ! -s "$WORK/prog.bin" ]; then
  "${SH_OBJCOPY:-/opt/toolchains/dc/sh-elf/bin/sh-elf-objcopy}" -R .stack -O binary "$ELF" "$WORK/prog.bin"
fi
test -s "$WORK/prog.bin"
# PAD_1ST=1 (test 14 DISC_COMPAT packaging, default 0): 1ST_READ.BIN padded with zeros to a whole number of 2048-byte
# sectors. KOS issue #1492 (a MODE ODE): an unpadded 1ST_READ.BIN left BIOS read residue that stalled or wedged KOS's
# first GD command; padding cured it. The zeros load just past the image's data, into .bss, which crt0 clears anyway.
if [ "${PAD_1ST:-0}" = 1 ]; then
  pb=$(stat -c %s "$WORK/prog.bin"); pp=$(( (pb + 2047) / 2048 * 2048 ))
  NM=${SH_NM:-/opt/toolchains/dc/sh-elf/bin/sh-elf-nm}
  bss=$("$NM" "$ELF" | awk '$3=="__bss_start"{print $1}'); endv=$("$NM" "$ELF" | awk '$3=="_end"{print $1}')
  # the padding must land inside [__bss_start, _end) (the image is loaded at 0x8c010000)
  { [ -n "$bss" ] && [ -n "$endv" ] && [ $(( 0x8c010000 + pb )) -ge $(( 0x$bss - 32 )) ] && \
    [ $(( 0x8c010000 + pp )) -le $(( 0x$endv )) ]; } || \
    { echo "mkgdi: PAD_1ST: image end $(printf %x $(( 0x8c010000 + pb ))) is not at .bss ($bss.._end $endv)" >&2; exit 1; }
  [ $pp = $pb ] || truncate -s $pp "$WORK/prog.bin"
  echo "mkgdi: 1ST_READ.BIN $pb -> $pp bytes (PAD_1ST=1)" >&2
fi

# Game tree, as mkdisc-hardlink.sh builds it.
cp -al "$DATA"/. "$WORK/cdroot/"
if [ -n "$EXTRA" ]; then
  mkdir -p "$WORK/cdroot/dc"
  cp -r "$EXTRA"/. "$WORK/cdroot/dc/"
fi

if [ "$LAYOUT" = standard ]; then
  # mkdcdisc adds the boot file itself (-b, unscrambled), last on the disc; a 1ST_READ.BIN in the data tree (an
  # extracted release) would be a second copy, so it goes (the tree is hard-linked: only the link is removed).
  rm -f "$WORK/cdroot/1ST_READ.BIN" "$WORK/cdroot/1st_read.bin"
  mkdir -p "$WORK/mkdc-tmp"
  # File order: libisofs places files of equal sort weight by the host's inode numbers (the order mkdcdisc's staging
  # copy happened to allocate them). A sort file with one weight per file, in byte order of the disc paths, fixes the
  # placement by the names alone (first path innermost; mkdcdisc still pins 1ST_READ.BIN last). What stays host
  # dependent is the Rock Ridge inode serial in each directory record (PX), metadata no loader reads: compare two
  # images by their files (fullplay/fp_iso.py manifest + diff, or disc_lint.py --compare), not by track hashes.
  (cd "$WORK/cdroot" && find . -type f | LC_ALL=C sort) > "$WORK/files.txt"
  if grep -q '[[:space:]]' "$WORK/files.txt"; then
    echo "mkgdi: a disc path has whitespace (mkdcdisc sort files cannot name it):" >&2; grep '[[:space:]]' "$WORK/files.txt" >&2; exit 1
  fi
  awk -v n="$(wc -l < "$WORK/files.txt")" '{print substr($0, 2), n - NR + 1}' "$WORK/files.txt" > "$WORK/sort.txt"
  # Fixed IP.BIN fields (as the console-tested test 14 standard image): maker RE4DC, V1.000, 20260920, no licence-screen
  # logo (-m). The volume and file dates come from SOURCE_DATE_EPOCH (DISC_EPOCH, default 2026-09-20 00:00 UTC), not
  # from the build day.
  if ! TZ=UTC SOURCE_DATE_EPOCH=${DISC_EPOCH:-1789862400} "$MKDCDISC" --no-banner --color never -v 1 -F gdi \
      --gdi-sector-size "$SECTOR" -b "$WORK/prog.bin" -D "$WORK/cdroot" -m -n "$TITLE" -a RE4DC -s "$PRODUCT" \
      -P V1.000 -r 20260920 -H "$PERIPHERALS" -V RE4DCROOM -S "$WORK/sort.txt" --temp-dir "$WORK/mkdc-tmp" \
      -o "$OUTDIR/disc.gdi" > "$WORK/mkdcdisc.log" 2>&1; then
    cat "$WORK/mkdcdisc.log" >&2; echo "mkgdi: mkdcdisc failed" >&2; exit 1
  fi
  if grep -ai 'warning' "$WORK/mkdcdisc.log" >&2; then
    echo "mkgdi: mkdcdisc warned (above); the release layout needs a clean run" >&2; exit 1
  fi
  ext=bin; [ "$SECTOR" = 2352 ] || ext=iso
  for f in disc.gdi track01.$ext track02.raw track03.$ext; do
    [ -s "$OUTDIR/$f" ] || { echo "mkgdi: mkdcdisc wrote no $f" >&2; ls -l "$OUTDIR" >&2; exit 1; }
  done
  # IP.BIN as it is on the disc (the high-density system area), for reference
  python3 - "$OUTDIR/track03.$ext" "$SECTOR" "$OUTDIR/IP.BIN" <<'PY'
import sys
t, ss, out = sys.argv[1], int(sys.argv[2]), sys.argv[3]
with open(t, 'rb') as f, open(out, 'wb') as w:
    for i in range(16):
        f.seek(i * ss + (16 if ss == 2352 else 0)); w.write(f.read(2048))
PY
  if [ "$SECTOR" = 2352 ]; then
    python3 "$here/disc_lint.py" --profile standard "$OUTDIR/disc.gdi" > "$OUTDIR/disc_lint.txt" ||
      { grep -vE '^(ok|WARN) ' "$OUTDIR/disc_lint.txt" >&2; echo "mkgdi: disc_lint (standard) failed" >&2; exit 1; }
    tail -1 "$OUTDIR/disc_lint.txt"
  fi
  {
    echo "layout standard (mkdcdisc $("$MKDCDISC" --help 2>&1 | sed -n 1p | awk '{print $2}'))"
    echo "sector_bytes $SECTOR"
    for f in track01.$ext track02.raw track03.$ext; do
      ss=$SECTOR; [ $f = track02.raw ] && ss=2352
      echo "$f sectors $(( $(stat -c %s "$OUTDIR/$f") / ss )) bytes $(stat -c %s "$OUTDIR/$f")"
    done
    echo "game_bytes $(du -sbL "$WORK/cdroot" | cut -f1) boot_bytes $(stat -c %s "$WORK/prog.bin")"
  } | tee "$OUTDIR/layout.txt"
  echo "built $OUTDIR/disc.gdi"
  ls -l "$OUTDIR"
  exit 0
fi

# ---- LAYOUT=legacy (internal discs only) ----
T1_SECTORS=606   # track02 then starts at 756 after its 150-sector pregap
T2_SECTORS=302   # 4 s minimum audio track
cp "$WORK/prog.bin" "$WORK/cdroot/1ST_READ.BIN"

cat > "$WORK/ip.txt" <<IPTXT
Hardware ID   : SEGA SEGAKATANA
Maker ID      : SEGA ENTERPRISES
Device Info   : 0000 GD-ROM1/1
Area Symbols  : JUE
Peripherals   : $PERIPHERALS
Product No    : $PRODUCT
Version       : V1.000
Release Date  : 20260920
Boot Filename : 1ST_READ.BIN
SW Maker Name : RE4DC
Game Title    : $TITLE
IPTXT
chmod +x "$KOS/utils/makeip/makeip" 2>/dev/null || true
"$KOS/utils/makeip/makeip" -f "$WORK/ip.txt" "$WORK/IP.BIN" >/dev/null
test "$(stat -c %s "$WORK/IP.BIN")" -eq 32768
# Fail here rather than on the console if a field did not land.
for want in "SEGA SEGAKATANA" "SEGA ENTERPRISES" "GD-ROM1/1" "1ST_READ.BIN"; do
  head -c 256 "$WORK/IP.BIN" | grep -aq "$want" || { echo "mkgdi: IP.BIN lacks '$want'" >&2; exit 1; }
done

# track03: IP.BIN + ISO9660 at LBA 45000 (absolute extents), written straight
# to OUTDIR because it is the big file. Rock Ridge and Joliet carry the real
# lower-case long names, as on the CD-R image.
genisoimage -quiet -C 0,$HD_LBA -G "$WORK/IP.BIN" -r -J -l \
  -input-charset "$INPUT_CHARSET" -V RE4DCROOM -o "$OUTDIR/track03.iso" "$WORK/cdroot"
# Per-file absolute LBAs (isoinfo -N: the image starts at LBA 45000).
if command -v isoinfo >/dev/null; then
  isoinfo -N $HD_LBA -R -l -i "$OUTDIR/track03.iso" > "$OUTDIR/track03-files.txt" 2>/dev/null || true
fi

# track01: placeholder ISO in the low-density area, padded to T1_SECTORS.
printf 'RE4DC GD-ROM image. The game is in the high-density area (track 3).\r\n' > "$WORK/t1root/README.TXT"
genisoimage -quiet -G "$WORK/IP.BIN" -V RE4DCLD -input-charset "$INPUT_CHARSET" \
  -o "$WORK/track01.iso" "$WORK/t1root"
t1=$(( $(stat -c %s "$WORK/track01.iso") / 2048 ))
[ "$t1" -le "$T1_SECTORS" ] || { echo "mkgdi: track01 is $t1 sectors" >&2; exit 1; }
truncate -s $((T1_SECTORS * 2048)) "$WORK/track01.iso"

if [ "$SECTOR" = 2352 ]; then
  cc -O2 -o "$WORK/mode1raw" "$here/mode1raw.c"
  "$WORK/mode1raw" "$WORK/track01.iso" "$OUTDIR/track01.bin" 0
  "$WORK/mode1raw" "$OUTDIR/track03.iso" "$OUTDIR/track03.bin" $HD_LBA
  rm -f "$OUTDIR/track03.iso"
  t1f=track01.bin; t3f=track03.bin
else
  mv "$WORK/track01.iso" "$OUTDIR/track01.iso"
  t1f=track01.iso; t3f=track03.iso
fi
head -c $((T2_SECTORS * 2352)) /dev/zero > "$OUTDIR/track02.raw"
t2_lba=$((T1_SECTORS + 150))
printf '3\r\n1 0 4 %s %s 0\r\n2 %s 0 2352 track02.raw 0\r\n3 %s 4 %s %s 0\r\n' \
  "$SECTOR" "$t1f" "$t2_lba" "$HD_LBA" "$SECTOR" "$t3f" > "$OUTDIR/disc.gdi"
cp "$WORK/IP.BIN" "$OUTDIR/IP.BIN"

# Layout report: track sizes, GD-ROM capacity, and each file's LBA in track 3.
t3_sectors=$(( $(stat -c %s "$OUTDIR/$t3f") / SECTOR ))
hd_cap=$((549150 - HD_LBA))   # GD-ROM high-density area ends at LBA 549150 (~1.03 GB of user data)
{
  echo "layout legacy"
  echo "sector_bytes $SECTOR"
  echo "track01 lba 0 sectors $T1_SECTORS bytes $(stat -c %s "$OUTDIR/$t1f")"
  echo "track02 lba $t2_lba sectors $T2_SECTORS bytes $(stat -c %s "$OUTDIR/track02.raw")"
  echo "track03 lba $HD_LBA sectors $t3_sectors bytes $(stat -c %s "$OUTDIR/$t3f") user_bytes $((t3_sectors * 2048))"
  echo "hd_capacity_sectors $hd_cap user_bytes $((hd_cap * 2048)) used_pct $((100 * t3_sectors / hd_cap))"
} | tee "$OUTDIR/layout.txt"
echo "built $OUTDIR/disc.gdi"
ls -l "$OUTDIR"
