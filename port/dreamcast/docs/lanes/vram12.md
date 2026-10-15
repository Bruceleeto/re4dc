# Lane vram12: VRAM reclaim for test 12 (2026-10-14)

Owner: the VRAM reclaim lane (the user's graphics memory rule in the workspace CLAUDE.md). The VRAM map is
`C:\Game Dev\Emulators\VRAM-MAP-20261014.md`. Flycast numbers are MODELLED; the TA parameter figures come from the
TA_BIN_DIAG tiler model (stored bytes) and lane ms's flycast6 TA stats (TA input bytes, `RE4DC_TA_STATS`).

## TA vertex buffer: keep TA_VERTBUF_KB=2048

Per bank the vertex buffer is 2,000,896 B (2048 KiB, minus TA_HEADROOM 48,128 and MV_SHADOWS 48,128). Peaks per scene
(arm vr12dtW = test 11 recipe + TA_HASH=1 TA_BIN_DIAG=1 RENDER_OPTION=0 RES_MODES=0; evidence
`C:\Flycast-Evidence\re4-dreamcast\vram-map-20261014\ta-*`):

| Scene | TA input peak (flycast6) | Stored params, model peak / p99 | OPB pool peak (of 230,400) |
|---|---|---|---|
| benchmark-r101, room frames to 3600 | 2,026,272 | **1,756,744** / 1,754,376 | 140,224 |
| benchmark-r101, window to room frame 1500 | 1,638,656 | 1,418,664 / 1,405,424 | 101,664 |
| r101 house siege (crowd12) | 1,760,736 | 1,519,016 / 1,467,308 | 111,264 |
| r119 El Gigante (g3 segment, r118-r11a-r119) | 1,671,808 | 1,442,100 / 1,141,468 | 100,448 |
| r117 (ch21 segment) | 908,672 | 819,744 / 760,728 | 98,560 |
| r105 (ch12 segment) | 880,736 | 823,140 / 681,360 | 72,480 |
| r11b (segment) | 723,136 | 615,880 / 592,696 | 52,256 |

The worst scene uses 88% of a bank (margin 244,152 B, 12%). 1920 KiB would leave 6%, 1792 KiB would overflow the
benchmark's late phase. 2048 was chosen in 700e2d02 (2026-09-23): r100 needed ~1,031 KB of TA parameters per frame,
over the 1024 KiB bank on hardware; the 10-02 console check measured 1.67 MB of TA input in the r101 fight.

## Data set blackgc14v (in this branch's t11-fix.py; data only)

`tools/d367/vram/vq_pak.py` re-encodes r101's 12 large 16-bit PS2 world textures (ARGB4444, >= 16 KiB; keys from
`ps2_world_data.inc`, census `tools/d367/vram/ps2tex_census.py`) as full-codebook VQ with the pinned KOS pvrtex: same
keys, native sizes, 16-bit format, material names and CRC rule. 458,752 -> 81,920 B (-376,832). The 11 small ones
(<= 4 KiB) stay 16-bit (VQ would be larger). PSNR 29.7-50.2 dB. `blackgc14vl` adds Leon's atlas as VQ (LVQ,
524,288 -> 67,584 B; needs the user's look decision).

Gates (binary unchanged, so knob-off identity holds by construction; the play ELF is not rebuilt):
- STRICT + decisions, r101 bell-warp, trace arm vr12tT, stop tick 2000: STRICT (2002 ticks, 0 masked), decisions
  MUST-IDENTICAL (`strict-bell-ps2vq-*`).
- TEX_CHECK=2 (vr12mW) on benchmark-r101: fails=0 meta_changes=0 vram_changes=0 (`texchk-ps2vq`).
- Census (vmaptW, benchmark-r101, frames to 1800) vs the release pak: preload 1,956,736 -> 1,579,904 B; "no
  contiguous block" 4 -> 0; effect sprites queued 25,095 -> 41,900, missing 36,188 -> 19,336. With LVQ as well:
  queued 56,697, missing 4,433, fragmentation retries 417 -> 215.
- Look: `vram-map-20261014\sheets` (texture sheet ps2vq-sheet.png, r101 stills r101-ps2vq-pair/crop.png).

## D4: per-room VRAM report and the VRAM gaps gate (VRAM_ROOM_LOG=1, 2026-10-15)

The graphics memory rule asks for each room's VRAM use in benchmark and full-play logs and for refusals, "no
contiguous block" failures and GameCube fallbacks to fail a check. `VRAM_ROOM_LOG=1` (Makefile, render/log only,
default 0, needs UI_VRAM=1 VRAM_PAGES=1; in the test 12 recipe T12REC) logs, at each room-entry preload pass, every
600 frames and at the room change ("exit": the visit's minima and counters):

- `vram room:` pinned (cache bytes drawn in the last 60 frames, leased or pool-pinned), dynamic (other resident cache
  bytes), other (non-cache allocations and page padding), free, largest free block, the visit's min free / min
  largest / peak pinned, and the visit's uploads, evictions and fragmentation retries.
- `vram gaps:` the visit's budget refusals, thrash-guard skips (guard, and guard_p = those while the cache was
  evicting: VRAM pressure; the rest are the 4-new-loads-per-frame cap), no contiguous block, latched, absent packages,
  GameCube effect pictures (gc_fx, FX_PS2_PACK=1), WORLD_HOLE_FIX dropped parts, effect sprites past the queue, model
  parts without their texture, silent AICA bank blocks (snd_fail) and AICA bytes in use.
- `vram gc-fx:` each GameCube-picture effect key (first 64 per visit).

Cost: one profile-source read and pvr_mem_available() per frame, a 448-entry walk plus the allocator census every 30
frames and at each sample; about 1 KB of BSS. Knob off: play image byte-identical (ident.sh vd4otP vs t12rctP).

Gates: `tools/d367/vram/vram_gate.py <run-output.txt>` (benchmark; bench-run.sh runs it after bench-ms.py) and
`fullplay/fp_check.py` (every segment; REPORT.md gets a "VRAM per room" table). They fail on refusals, guard_p,
nocontig and gc-fx keys that ps2lib/INDEX.tsv does not list as ps2_source=NONE. Keys map to INDEX rows through
`ps2lib/effects-tex/KEYS.tsv` (`tools/d367/vram/fx_keys.py <ps2lib>`, re-run after fx_ps2_pack.py lib). Logs from
builds without the knob (test 11) are judged on rejects= and "no contiguous block" only; their thrash-guard count has no
pressure split and is noted, not failed (no new failures on the test 11 candidate gate logs g5b-183453 / pcr2-193643).
