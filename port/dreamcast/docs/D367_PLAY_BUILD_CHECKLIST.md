# D367 play build checklist (user, 2026-09-29)

Goal: one play build that feels like the game from the title as far as it goes (r120 intro -> r100 -> r101 -> r103),
on the fastest measured render pipeline, with every existing fix landed. Update this file with every step (status,
commit, evidence). Do not start a later step's work inside an earlier step. Before calling the build complete, re-run
the unlanded-work sweep (every local tree's files hashed against every dreamcast-port blob) and account for every hit.

## Play build rules (verified 2026-09-29)

- Recipe: `tools/d367/build-r21.sh` plus `DBG_WARP=0 QUALITY_PICKER=0 ARENA_FIT_KOS_BYTES=147456 PACE_MODE=fast
  PACE_DEBUG=1 LOGIC_TRACE=0 GAME_DECISION_TRACE=0 ACTOR_TRANSACTION_DIAG=0`; keep `GAME_PWC_DIAG=1` (an exact logic
  cut; only =2 is test-only). Test spots use a `DBG_WARP=1` twin; the pad fixture works without it.
- Disc: `debug/config.txt` ROOM 0x20 (New Game -> r120 intro), no `dc/quality.txt`, the r100 release (route fix e)
  re-cut from the disc's own r100.dar (A1 blocks + A2 archive; the old A2 dar would drop r100's AICA overlay).
- World: the PS2 world in r100, r101 and r103 through PS2_WORLD_MESH + PS2_WORLD_ROOMS=2 (64-vertex packages; r101
  the adopted world-mesh-r21 package, r100/r103 from tools/ps2_room_r4im.py). The disc must stage
  dc/native/r100|r101|r103/ps2-world.{re4mesh,r4pw} and their dc/tex files (tour/play/*-pw.json); a room whose
  package is missing falls back to its Standard scenery.

## Steps

| # | Step | Status | Evidence / commit |
|---|---|---|---|
| 1 | MOTION_RESERVE (ambush: cold-clip slots at bind) onto the tip; ambush run | done | 8c000e81: on in build-r21.sh. Knob-off .text/.data == p9w; STRICT vs r20k3w 0..1941; r100-s20 ambush preset (s20 571/571, em21/em2a, post-house call, 5100 frames) no HALT / no OOM; New Game -> r100, r101 entry, r103 entry no HALT. Slabs 2x27584 (55 KB heap 4); the idle script used 0 (its 75 loads were hot clips): the reserve covers player-driven cold clips. Also landed default off: MOTION_USAGE_LOG, HEAP_REPLACE_LOG, HEAP_CENSUS. Follow-up 121fcc4e MOTION_RESERVE_SPILL=524288 (in build-r21.sh): the two slabs thrashed in the r101 fight (net_crc32le 18.85% of non-idle PC samples, ~50 key reloads/s); a cold key now spills into heap 4 while 512 KiB stay free: r101 entry 3480 -> 4413 frames / 200 s (+27%), r100 ambush 0 spills (under the margin, slabs as before), STRICT vs r20k3w 0..1941 with 4 spills taken |
| 2 | Effects: coarse mode hands qualified effects to EFFECT_SPRITES instead of markers; land EFFECT_ROOM | done | fe79a373: COARSE_FX_SPRITES=2 in build-r21.sh (weapon / shot / blood sprites, no opaque markers): r101 kite fight windows (ticks 300..1200) equal to the control, r100 after the call -0.45 ms, first window +62 ms once (correction: the kite fixture's Leon dies ~80 s in, so its later "quiet" windows are the Continue screen; fe79a373's "r101 quiet" figures measured that screen); STRICT 0..1941; knob-off identical. EFFECT_ROOM landed default 0. Found on the way: fbb2ee2e, a short MOTION_FAST_READ (GD DMA in flight) halted "motion key read"; now falls back to the storage reader (forced-short test: no halt) |
| 2b | Room effects in coarse (user 2026-09-29: after 2): EFFECT_ROOM=7 costs +3.4 ms r101 / +3.9 ms r100 and thrashes VRAM in r101 fights (1598 vs 291 loads). Do: hw profile (PC sampler) of the +3 ms; a resident VRAM slab for effect textures; sprite paths for the non-EspCommonTrans classes (r100 leaves d0/4e, light shafts d0/08 Esp08, trails Esp16) | todo | |
| 3 | POST_F00 (Filter00 glow + contrast) + PVR_DITHER | done: off | a7dbcd3a landed default off, ~0 ms. Decision 2026-09-29 (user asked for my call): off in the play build. On the r101 PS2 world (r101-entry fixture) the play build is already at / above GameCube brightness (view mean 47 vs Dolphin r101 26-44); =1 / =4 lift it to 68 / 67. The "matches GC with Filter00" note came from the source-renderer world. PVR_DITHER is a no-op (KOS already dithers). Note: the default kite fixture stages no PS2 world (PS2MESH open failed, flat fallback): judge looks on rel-r101-entry |
| 4 | Door loading (worktree step4 on 121fcc4e: U0 IO_PROBE + dvdhold, U1 TEX_KEEP, U2 IO_ALIGNED, U6 DVD_WAIT + DVD_FDCACHE); main-checkout extras (mkdisc.sh, tests, bake_room_prelit.py); PACE_PAGE vs the Options row | in progress | r100 -> r100 door x3 (tour/door-cycle-pw.json, emulated): baseline 13.1 s / 41 game frames per door, all units 7.6-8.9 s / 29 frames. Door-frame rule: the equalised arm holds each source request until its baseline frame (tour/door/dvdhold.txt, 186 per-read targets across the three doors). The hold must gate only a request's start (src/game/dvd.cpp cDvdQueue::Read, m_Rno0==0 && step==0): gating every step held a read in flight until the next read's target (+1 frame per door, FAIL). U1+U2 held (kite-r21dh12ch): 41/41/41 frames, logic_trace_diff --align room STRICT over all 11,382 ticks. U6 with the hold halted (main.cpp 548) with the old gate; all units held re-running |
| 5 | r100 + r103 PS2 worlds: extraction -> ps2_world_r4im -> any-room PS2_WORLD_MESH runtime | done (moved ahead of 4, user 2026-09-29: the fixes must be seen in the new world) | PS2_WORLD_ROOMS=2 in build-r21.sh. tools/ps2_room_r4im.py builds any room from the JADERLINK OBJ export (r101 reproduces the committed package: 190 meshes / 209 placements / level 0 47,770 vs 47,772; every triangle matches the wrapper in winding, UV, colour bytes, texture). r100 1.65 MB (177 meshes / 283 placements, 106 instanced), r103 1.14 MB. =2 opens the package at the room's first scenery bind and skips the Standard scenery package (r103 cannot hold both: 80 KiB heap-4 reserve); non-coarse images (route movies, events) draw the PS2 world at their first scenery part. Heap 4 free after open: r100 3.80 MB, r101 4.12 MB, r103 4.39 MB. Flycast steady ms control -> =2: r100 s20 37.1 -> 37.3, post-radio 26.8 -> 26.0, r101 entry 79.1 -> 78.8, r103 entry 67.3 -> 58.4. Knob-off identity; STRICT (traced, r101 package staged) passes 0..1941. Look: r100 forest floor / trees and r103 fences, house, trees now drawn (Standard showed dark ground and placeholder squares). Open: r100 authored colours are mostly saturated (median vc 1.99 vs r101 0.41), e.g. the gate hedge after the radio call is flat and bright; PS2 SMX colour semantics unknown. Staging: tour/*-pw.json (make-pw-fixtures.py); the play disc needs the same files |
| 6 | Full scripted run title -> r103 with screenshots (scenery, effects, manual, ambush); Windows + SteamOS packages | in progress | Play disc r21i (2026-09-29): ELF pw4 = ad0c59d0 recipe + DBG_WARP=0 (checklist play flags), tour/play/title-pw.json -> C:\\RE4DC-Play-Discs\\r21i-title (disc sha 13291cb6), launcher D:\\RE4DC-Play\\Play-r21i-PS2-Worlds.cmd. New Game pad fixture (newgame-pw, 720 s): r120 intro -> r100 with the PS2 world, no halt |
| 7 | Clean up the local copies (186 clones/worktrees, 35 plain trees) once nothing unlanded remains | todo | |

## Known open items outside these steps

- Dark / black Player's Manual pages (continuation RENDERING-RECOVERY-PLAN-20260928.md).
- Diagnostics to land default-off or archive (HEAP_CENSUS, HEAP_REPLACE_LOG landed 8c000e81): POOL_PEAK_LOG, SKEL_AUDIT, COL_STATS,
  SKEL_PF, IK_PASS, CAM_LOG, WQ_CAMLOG, MOTION_MISS_LOG, H4DIAG, ROUTE_ACTION_DIAG.
- Codex 09-27 trials to check: GAME_MOTION_PROGRAM / COLLISION_QUERY_OBSERVER, COARSE_SOURCE_POLICY / SOURCE_CENSUS.
- Not landing (rejected / superseded): CUT_GORE, scenery-trials CULL/FOG/TREE knobs, OT_GXNRM / OT_SKYNOFOG / OT_LOD0,
  COARSE_WORLD_KERNEL, HERMITE_FLAT, DBG_AUTOLOAD, HWCAL_*, FIX_R101_CALL_DONE, A30_OBJSCR, CROWD_LOD_OPEN, FENCE_SPLIT,
  QUALITY_LOW.
