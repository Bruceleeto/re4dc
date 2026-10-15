# Lane t2exact: tranche 2 exact levers (2026-10-15)

Branch lane/t2exact from dreamcast-port 1c79d543 (test 13), worktree /root/probe/lanes-20261015/t2exact/tree, work
files in /root/probe/lanes-20261015/t2exact (build/run scripts, warp files, price.py / lineprof.py / pcprof.py /
callers.py). Local commits only; the coordinator lands. Every knob is default 0 (t2exact.mk): the knob-off image is
test 13's (objcopy -R .stack c1ae83dd, 6 overlays identical).

Levers (PERF-BACKLOG-CH1-2-20261015.md section 4): A2b GC render census removals, B4 world walk lean, B6 read-side
prefetch; B5 (I-cache code size) added by the coordinator.

Labels: MODELLED = the SH-4 hw model (hwproject, nominal penalties). MODELLED-corrected = MODELLED x the
HWMODEL-CALIBRATION-20261015 part factors (WORLD x1.23, ACTOR DRAW x1.25, OTHER x1.15, LOGIC x1.06), for exact work
removal only. CONSOLE = the user's console. Cache / layout / prefetch levers (B5, B6) are not priced by the model (it
charges a D miss ~10 cycles, the console ~24.5): they go to a console A/B.

## Scenes and windows

- r101 cross: benchpub scene 1 without its bench line (cross-warp.txt): Leon by the cross, crowd alerted at room
  frame 30, god, no input, cap 6. Global frames 500..799, 10 traced (stride 30).
- r103 farm: benchpub scene 4 without its bench line (farm-warp.txt): wide view over the farm, 5 Ganados not alerted.
  Global frames 500..799, 10 traced.
- Data set T13_DATA (t11-fix.py), build = test 13 recipe (test13/t13-build.sh rW + PACE_MODE=off PC_SAMPLER_BYTES=8192).
- Evidence: D:\Flycast-Evidence\re4-dreamcast\t2exact-20261015\hwmodel-* (hw model), C:\Flycast-Evidence\re4-dreamcast\
  t2exact-20261015\<run> (Flycast trace / gate runs).

## Control (knob-off cost arm t2crW, 7075c866)

| scene | MODELLED ms/frame | game-render | scenery | actors | logic |
|---|---|---|---|---|---|
| r101 cross | 57.3 [48.9..69.5] | 18.6 | 16.6 | 7.6 | 7.0 |
| r103 farm | 88.0 [75.8..105.3] | 32.3 | 15.8 | 17.7 | 9.3 |

Function groups each lever targets (price.py, MODELLED hw ms per frame, cross / farm):

| group | cross | farm |
|---|---|---|
| A2b #3 GX state (15-18 GX stubs) | 0.27 | 1.05 |
| A2b #11 coarse hooks (sourceActorIdentity, coarse source lookups, room4 state) | 0.28 | 0.55 |
| A2b #12 re4dc_model_diagnostic_enabled (lane g1parts G1_DIAG_INLINE, not repeated here) | 0.05 | 0.12 |
| B4 placement walk (ps2_pass self, world_out, dyn) | 1.65 | 1.63 |
| B4 cluster / meshlet tests (MeshDraw draw/run, box tests, sg_select) | 6.01 | 3.74 |
| B4 strip walk (walk_lean, clip; per strip, not walk overhead) | 3.10 | 3.47 |
| B6 world transform (transform_sched) | 4.44 (dmiss 0.36) | 5.35 (dmiss 0.44) |
| B6 skin / light kernels (avk_*) | 3.71 (dmiss 0.55) | 4.25 (dmiss 0.55) |

## A2b: GC_CENSUS_TRIM

Knob GC_CENSUS_TRIM=1 (t2exact.mk; exact, render only). What it does: the per-call leftovers of the GameCube render census.
- #3 GX state: gx_fast.h inlines the hot GXGetProjectionv / GXGetViewportv / GXSetProjection callers (re4dc_draw_model_part,
  EspCommonTrans, the UI ID quad, CameraSetProjection): they copy / store gx_stub.cpp's state words in place of the call
  (the viewport copy adds the RES_ALTERNATE line jitter exactly as GXGetViewportv does; gx_stub.cpp has an #error if the
  two settings disagree). include/gx.h includes gx_fast.h at its end (adding an #include to esp_sub.cpp shifted __LINE__
  and changed EspCommonTrans's code with the knob off).
- #11 coarse hooks: trans.cpp sourceActorIdentity reads room heap 4's live flag and generation through two exported
  pointers instead of calling re4dc_room4_state(); re4dc_coarse_actor_source / re4dc_coarse_ganado_source find a static
  chunk element from the table's address range (chunk_find.h) instead of comparing every element.
- #12 is lane g1parts' G1_DIAG_INLINE (test 14), not repeated.

Knob-off identity: PASS (x3krP: image c1ae83dd + 6 overlays identical to test 13's t2krP, with the A2b and B4 code in the tree).

| scene (frames 500..799, 10 traced) | control t2crW | a2rW (95b1c618) | delta MODELLED | target groups (price.py) | MODELLED-corrected (OTHER x1.15) |
|---|---|---|---|---|---|
| r101 cross | 57.3 | 57.0 | -0.3 | 0.55 -> 0.39 (-0.16; GX -0.11, hooks -0.05) | -0.35 |
| r103 farm | 88.0 | 87.6 | -0.4 | 1.60 -> 1.12 (-0.48; GX -0.40, hooks -0.08) | -0.46 |

The saving is in game-render-side (effects' EspCommonTrans and the actor part setup), so the OTHER factor applies. The
farm pays more because its GX getters run ~350 times a frame (effects + actor parts); the coarse hooks mostly did not
move: sourceActorIdentity's own body is the cost, not re4dc_room4_state. I-cache fills a frame: 108,990 -> 107,956
(cross), 154,741 -> 154,068 (farm).

## B4: PS2_WALK_CELLS (DROPPED)

Built and measured, not committed (patch kept at /root/probe/lanes-20261015/t2exact/b4-ps2-walk-cells.patch, on
native_static.cpp of 1c79d543). Design: at package open, bin the fixed placements (no dynamic id slot, not the sky row,
not wider than a cell) on a 5 x 6 X/Z grid, the cell id in bits 3..7 of the pass-mask byte, each cell's box the union
of its placements' world_out boxes; each pass tests the 30 cells against the world planes once and ps2_pass skips the
placements of a cell that is wholly outside a plane, before reading their placement and mesh records. =2 check build:
world_out still runs for each skipped placement and counts any it would not reject.

- Correctness (check build b4crW, 60 s runs): r101 cross 223 placements, 202 fixed, 154 binned (48 wider than a
  cell), ~76 skipped a frame, bad=0; r103 farm 134 placements, only 9 fixed (the rest have a dynamic id slot), 8
  binned, ~4 skipped a frame, bad=0. halt / missing /
  fault 0.
- Cost (b4rW 175f1a2d vs t2crW): r101 cross 57.3 -> 59.8, r103 farm 88.0 -> 86.2 MODELLED. Neither is the lever. The
  pipeline column (issue + dependency + branch, independent of cache placement) did not move: placement walk 0.65 ->
  0.65 (cross), 0.63 -> 0.68 (farm); scenery pipe 11.8 -> 11.9 on both. world_out fell 0.11 ms at the cross, but the
  cell tests in ps2_pass cost what they saved. The +2.5 / -1.8 ms are cache placement: native_static.cpp's code and
  data grew, every scenery function moved, and the I and D fills of MeshDraw::draw, transform_sched, box_mask,
  sg_select changed (cross: imiss +1.0, dmiss +0.65 ms in scenery alone).
- Why it cannot pay: the cross walk does 669 placement iterations a frame, the pass mask already rejects 434 of them
  for a byte compare, and only ~235 reach world_out (~140 rejected, ~93 drawn). The fixed 2-7 ms console world walk is
  in the meshlet level (MeshDraw::draw / run, sg_select, box tests: 6.0 ms cross) and the strip walk (3.1 ms), and that
  work belongs to the ~93 placements that are drawn: a cell or PVS pre-reject cannot remove it.
- Verdict: DROPPED (< 0.2 ms MODELLED on both scenes, in the layout-independent pipe column). Finding for A6 / B5:
  a layout shift alone moved the cross by +2.5 ms MODELLED (I and D fills), larger than every exact lever in this lane.

## B6: read-side prefetch

Finding (MODELLED per-instruction profile, pcprof.py): both streams the backlog names already prefetch their input.
- World transform (mesh_fastpath_sched.hpp): PREF 3 vertices ahead on the vertex stream; the stream's own read misses
  are ~0.02 ms. Its D misses are the colour LUT reads (two 1 KB tables, 1238 + 531 misses a frame at the cross,
  990 + 920 at the farm: evicted by the streaming vertex data and the vertex cache writes in the direct-mapped 16 KB
  operand cache) and write misses to the vertex cache entries (2587 / 3201 a frame).
- Skin kernels (avk_sh4.S): the position records are prefetched (pfwait 0.17 ms: issued a little late). The read
  misses left are the bone palette matrices at a palette change (~215 a frame per load, pos_skin_u16) and the n16
  normal stream of re4dc_avk_light_skin_n16, which has no PREF (565 + 515 misses a frame at the cross).
- What is left for a read-side PREF: the n16 normal stream (1,080 read misses a frame at the cross, ~1,000 at the farm).
  At the console's own price (~24.5 cycles a miss, HWMODEL-CALIBRATION-20261015) that is 1,080 x 24.5 / 200 MHz =
  0.13 ms a frame, the most a perfect prefetch could recover; the model (10 cycles a miss) says 0.05. The colour LUT
  reads are indexed by the vertex's own colour bytes, so a PREF for them needs the next vertex's colour loaded and
  decoded a vertex ahead (~9 more instructions per vertex in a loop scheduled to 34.5 cycles): the issue cost is about
  as large as the misses it would hide (1,769 a frame = 0.22 ms CONSOLE at best).
- Verdict: DROPPED, not built. Below 0.2 ms even at the console's miss price on both scenes, so no console A/B was spent
  on it. Recorded for a later lane (not read-side, so not B6): the vertex cache entries are written with ordinary
  stores into lines that are not in the cache (2,587 write misses a frame at the cross, 3,201 at the farm). The SH-4
  fetches each such line from RAM before the store. MOVCA.L (allocate without the fetch) would remove those fills, an
  estimated 0.3-0.4 ms CONSOLE. It needs the whole 32-byte entry written, starting with the MOVCA store, inside the
  scheduled assembly kernel (mesh_fastpath_sched.hpp writes 24 of the 32 bytes). Per the optimization rule that needs a
  console A/B, plus a reason why a layout change is not enough, before anyone builds it.

## B5: I-cache code size

(in progress)
