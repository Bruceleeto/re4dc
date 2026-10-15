# Lane discread: disc-read compatibility (test 14 items 11/12), 2026-10-15

Branch `lane/discread` (local), on `lane/ds28b` 34a92694 (test 12.2 + issue #28 v2). Research:
`RE4DC-DISC-COMPAT-RESEARCH-20261015.md` section 6. All numbers below are Flycast (emulated time), not console.

## The knob: `DISC_COMPAT=1` (default 0, image unchanged: knob-off image fcedaecf + 6 overlays == 12.2)

| Part | What it does | Flycast result |
|---|---|---|
| `DISC_READ_FALLBACK=2` (v2) | No `cdrom_stream` at all: every read is a bounded GD command (DMA, DMA after a bounded re-init, PIO). No stream is ever cancelled with data queued, and DVD_READ_SAFE's 10 ms force-abort (dvd_read_safe.cpp, stream request path) cannot run: it only follows a refused stream request. v2 aborts a command only after 5 s + 8 ms/sector. | Boots, plays; load times below; logic MUST-DIFFER (load timing) |
| `DISC_BOOT_LOG=2` | The disc log goes on screen only after a read had trouble (=1 is the #28 always-on log). | Boot shot clean |
| `KOS_DISC_FIX=1` | Build-time patched copies of KOS `fs_iso9660.c` (upstream aeee10d9, one mutex) and `cdrom.c` (exec_cmd_timed abort deadlock; reinit_ex 8 tries; 100 ms settle after an abort's reset + init). KOS checkout untouched (`patches/README.md`). | STRICT vs 12.2, load times identical to 12.2 |
| Split-image mount (`gdrom_mount.cpp`) | Mounts the data track holding the ISO9660 volume descriptor, not blindly the last one ("Shrink GDI", #17). | Split GDI: control fails (`File not found` for every file), DISC_COMPAT reaches the title |
| `mkgdi.sh PAD_1ST=1 PRODUCT=...` (packaging) | 1ST_READ.BIN padded to whole sectors (KOS #1492; the zeros land in .bss, checked against `__bss_start`/`_end`); own product number. | Boots (2352 form, product RE4DC01) |

`DISC_COMPAT=1 DISC_READ_FALLBACK=0` is the timing-neutral subset (KOS fixes + mount, 12.2's stream reads kept).
`DISC_POLL_SPIN_MS=N` (default 0, not in the set): v2 yields N ms before sleeping (KOS sleeps last until the next
10 ms tick at THD_SCHED_HZ 100).

Static cost: v2 +9.2 KB image (`_end`; first build was +27.7 KB: a `dcache_purge_range` over 39 KB instanced KOS's
16 KB purge-all buffer, and a 2 KB static sector; both removed). Subset +0.8 KB.

## Gates (Flycast, 2026-10-15)

- Knob-off identity: image fcedaecf and em22/em2b/em2f/pl0f/pl11/sscrn overlays byte-identical to out-t122auP.
- Boots to the title (state title=1): 2352 PAD_1ST + RE4DC01 (frame 67), split image DISC_COMPAT (67) and subset (34);
  control on the split image fails to open any file.
- KOS squeeze 48 KiB (10 runs): full set PASS (fight 9,056 B min headroom at 4 KiB pieces, call 42,376, door 24,136,
  leave100/103 9,416); the first build (+27.7 KB) failed leave100/103 at 4 KiB pieces (12 KB thread stack at r100
  entry). Control 12.2 twin leave100/103: 6,272 B. Subset (DISC_READ_FALLBACK=0) PASS: fight 9,344, call 42,664,
  door 24,424, leave100/103 9,544.
- Lane scripts (not in the tree): /root/probe/discread/{dr-build.sh, dr-master.sh, dr-discs.sh (2352/2048/split
  masters), strict.sh, ident.sh}; Windows runners C:\Game Dev\Emulators\_discread\{dr-run.sh, dr-wrun.sh, dr-trace.sh}.
  Evidence C:\Flycast-Evidence\re4-dreamcast\discread-20261015 (traces, load runs, kos-*), D:\...\discread-boot*.
- STRICT r101 (leave100 warp, stop tick 670, `--align room 0101` and frame):
  - KOS fix only: STRICT, MUST-IDENTICAL (672 ticks frame-aligned, through the r100 entry).
  - Timing control (12.2 + LOGIC_TRACE_DELAY_US=5000): STRICT.
  - Full set: MUST-DIFFER from r101 room tick 3 (line queries), RNG redistributed over room ticks 7-9 and equal again
    at tick 10; the room starts 22 ticks later after the title (v2 boot +31 frames). Cause class: load timing (v2 reads
    complete on different ticks; the KOS fix alone is STRICT). Not proven equalised yet.
- Room-entry load (DISC_READ_METER `DISCRD: room=... load_ms`, same fixtures, control -> DISC_COMPAT):

  | Fixture | Room | 12.2 recipe | DISC_COMPAT | KOS fix only | v2 only |
  |---|---|---|---|---|---|
  | kos-leave100 | r101 from title | 10.55 s | 8.45 s | - | - |
  | kos-leave100 | r100 (room change) | 4.70 s | 5.85 s | - | - |
  | door103 | r101 from title | 8.42 s | 5.81 s | 8.42 s | 5.81 s |
  | door103 | r103 (door) | 5.45 s | 6.38 s | 5.45 s | 6.38 s |
  | r11b | r11b from title | 5.42 s | 6.05 s | 5.42 s | 6.05 s |

  The read count is about the same (r103: 728 vs 766); v2 costs ~1.3 ms more per read [inf: a chunked file read that a
  stream continued is now one GD command per chunk]. DISC_POLL_SPIN_MS=4 changes nothing, =20 gives r103 6.01 s. Console
  GDEMU times decide; Flycast's per-command cost is not GDEMU's.
- No cabin room on the 12.2 disc (r11c is not in the release); r100 (the first house) is covered by leave100.

## Product number

`PRODUCT=T0000` is shared with much homebrew (openMenu artwork, the shrink blacklist, `read_limit = -1` keys on it).
A new number moves saves: openMenu/GDMenu per-game virtual VMUs and Flycast's per-game VMU files are named after it
(`T0000_vmu_save_A1.bin` in the harness template; fp_run.py copies saves under that name), so a release with a new
number starts with an empty per-game VMU for players who use that mode, and the full-play harness needs the new name.
Decide with the user; RE4DC01 was used only on test discs.

## Disc-check disc (design)

A separate program on the release's own data (`DISC_CHECK=1` build of the same ELF sources, KOS fixes included, so it
tests the same read code), on the standard GDI forms (2352, 2048, split):

1. Mastering writes `dc/disccheck.txt`: every file's path, size, first LBA and CRC32 (from the extracted tree).
2. Boot screen: firmware facts (disc type, TOC, which track mounted as /cd, product number), then three passes per file:
   A = KOS file read with streams (12.2's path), B = plain sector reads (DMA, the v2 path), C = PIO on a sample
   (every 16th file). Each read is bounded (5 s + 8 ms/sector); a timeout is recorded, not fatal.
3. Per pass: files OK / CRC mismatch / timeout / open failure, MB/s, slowest file and its time, worst-case command
   latency; a running line during the check, one photographable summary page at the end, PASS only with 0 failures.
4. Modes: QUICK (the 40 files a room load touches + the largest and smallest + one per directory, ~2 min on GDEMU) and
   FULL (all 2,560 files twice, ~970 MB each way: ~25-35 min on GDEMU at 1-1.5 MB/s [est]), chosen with A/B.
5. Results also go to the VMU (one 1-block file) so a tester can send the numbers without a photo.
Testers run it once per unit/card/firmware; the matrix in KNOWN_ISSUES gets one row per result.

## Weak-clone imitation

User note: `RE4DC-WEAK-GDEMU-IMITATION-NOTE-20261015.md` (GDEMU.ini `read_limit = 600`, an old slow SD card, undo
steps). Not applied to any card.
