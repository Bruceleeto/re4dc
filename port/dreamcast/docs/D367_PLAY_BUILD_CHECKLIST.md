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
- World: r101 PS2 world through PS2_WORLD_MESH with the adopted 64-vertex package; r100/r103 Standard scenery through
  COARSE_SCENERY_FALLBACK until their PS2 worlds exist (step 5).

## Steps

| # | Step | Status | Evidence / commit |
|---|---|---|---|
| 1 | MOTION_RESERVE (ambush: cold-clip slots at bind) onto the tip; ambush run | done | 8c000e81: on in build-r21.sh. Knob-off .text/.data == p9w; STRICT vs r20k3w 0..1941; r100-s20 ambush preset (s20 571/571, em21/em2a, post-house call, 5100 frames) no HALT / no OOM; New Game -> r100, r101 entry, r103 entry no HALT. Slabs 2x27584 (55 KB heap 4); the idle script used 0 (its 75 loads were hot clips): the reserve covers player-driven cold clips. Also landed default off: MOTION_USAGE_LOG, HEAP_REPLACE_LOG, HEAP_CENSUS |
| 2 | Effects: coarse mode hands qualified effects to EFFECT_SPRITES instead of markers; land EFFECT_ROOM | done | fe79a373: COARSE_FX_SPRITES=2 in build-r21.sh (weapon / shot / blood sprites, no opaque markers): r101 quiet -0.15 ms, r100 after the call -0.45 ms, first window +62 ms once; STRICT 0..1941; knob-off identical. EFFECT_ROOM landed default 0. Found on the way: fbb2ee2e, a short MOTION_FAST_READ (GD DMA in flight) halted "motion key read"; now falls back to the storage reader (forced-short test: no halt) |
| 2b | Room effects in coarse (user 2026-09-29: after 2): EFFECT_ROOM=7 costs +3.4 ms r101 / +3.9 ms r100 and thrashes VRAM in r101 fights (1598 vs 291 loads). Do: hw profile (PC sampler) of the +3 ms; a resident VRAM slab for effect textures; sprite paths for the non-EspCommonTrans classes (r100 leaves d0/4e, light shafts d0/08 Esp08, trails Esp16) | todo | |
| 3 | POST_F00 (Filter00 glow + contrast) + PVR_DITHER | in progress | |
| 4 | Door loading U6 (DVD_WAIT, DVD_FDCACHE, IO_ALIGNED, TEX_KEEP); main-checkout extras (mkdisc.sh, tests, bake_room_prelit.py); PACE_PAGE vs the Options row | todo | |
| 5 | r100 + r103 PS2 worlds: extraction -> ps2_world_r4im -> any-room PS2_WORLD_MESH runtime | todo | |
| 6 | Full scripted run title -> r103 with screenshots (scenery, effects, manual, ambush); Windows + SteamOS packages | todo | |
| 7 | Clean up the local copies (186 clones/worktrees, 35 plain trees) once nothing unlanded remains | todo | |

## Known open items outside these steps

- Dark / black Player's Manual pages (continuation RENDERING-RECOVERY-PLAN-20260928.md).
- Diagnostics to land default-off or archive (HEAP_CENSUS, HEAP_REPLACE_LOG landed 8c000e81): POOL_PEAK_LOG, SKEL_AUDIT, COL_STATS,
  SKEL_PF, IK_PASS, CAM_LOG, WQ_CAMLOG, MOTION_MISS_LOG, H4DIAG, ROUTE_ACTION_DIAG.
- Codex 09-27 trials to check: GAME_MOTION_PROGRAM / COLLISION_QUERY_OBSERVER, COARSE_SOURCE_POLICY / SOURCE_CENSUS.
- Not landing (rejected / superseded): CUT_GORE, scenery-trials CULL/FOG/TREE knobs, OT_GXNRM / OT_SKYNOFOG / OT_LOD0,
  COARSE_WORLD_KERNEL, HERMITE_FLAT, DBG_AUTOLOAD, HWCAL_*, FIX_R101_CALL_DONE, A30_OBJSCR, CROWD_LOD_OPEN, FENCE_SPLIT,
  QUALITY_LOW.
