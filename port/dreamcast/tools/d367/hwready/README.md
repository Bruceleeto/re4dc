# Hardware readiness checks

Flycast runs code that a real Dreamcast does not, so a build that plays in Flycast can still crash or
glitch on the console. These checks cover the gaps found on 2026-10-02 (r21m). Run them over any new room,
data format or platform change before a console disc.

| Gap | Check | r21m result |
| --- | --- | --- |
| Misaligned 16/32-bit accesses: the SH-4 raises an address error, Flycast performs them | `route-hw.sh align` (log must show 0 `MISALIGN`) | 17 PCs on the new-game route, a crash in the first minutes; fixed (cCtrl work, `u16_un`) |
| Memory the game never wrote: Flycast starts with zeroed RAM, VRAM and sound RAM | build with `POISON_RAM=0xA5`, compare game state with `state-cmp.sh` | no difference on 4 route runs |
| Vertex buffer overflow: Flycast has no limit, the PVR has 2 MB a frame | `route-hw.sh ta` (`TA peak` in `ta-stats.txt`) | worst 1.67 MB of TA input (r101 fight; the PVR stores about 3/4) |
| No logs on hardware without a serial cable | `CRASH_SCREEN=1` (in every play build): fault, HALT or 30 s hang draws a report asking for a ticket | tested with `tour/hwready-crash-{fault,halt,hang}-pw.json` |

Also checked and fine: KOS DMA reads invalidate the cache; AICA writes wait on the G2 FIFO and lock;
store-queue users hold `sq_lock`; the sub screen overlay syncs its code; no cache-RAM mode; FSCA/FSRRA only in
render code; 640x480 through KOS picks NTSC interlace on S-Video; stick and trigger dead zones absorb drift.

## Tools

- `route-hw.sh <align|ta> <name> <label> <fixture> [seconds]`: `route/route-run.sh` with the hwmodel Flycast
  (`tools/hwmodel/flycast/hwtrace.patch` + `hwready.patch`). `align` runs the interpreter at about 6 game fps;
  its fixture input lands on other ticks than in a dynarec run, so compare game state against dynarec runs only.
- `state-cmp.sh <base> <test>`: tick-indexed player state (`warp: frame` lines), cutscenes, HALT / FAULT counts.
- Knobs (default 0): `POISON_RAM=<byte>`, `CRASH_SCREEN=1` (the play recipe sets it). `/cd/dc/crashtest.txt`
  (`fault`, `halt` or `hang`) arms a crash test 20 s after boot.

Fixes for misaligned data go off the PowerPC only (`#if defined(__PPC__)`), so the GameCube build stays
byte-identical: an aligned layout, or `u16_un` (types.h) for u16 arrays the data format leaves at odd offsets.
