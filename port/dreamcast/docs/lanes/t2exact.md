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

Gates (all on the committed tree 4633156c, knob on):
- STRICT + decisions vs the knob-off control, same fixtures: r101 cross fight (stop 800) STRICT, MUST-IDENTICAL, 802
  ticks; door103 (stop 1400) STRICT, MUST-IDENTICAL, 1402 ticks, DOORDEMO END reached; 0 overruns (a2-fight / a2-door vs
  c0-fight / c0-door).
- Align logger (interpreter, 60 s each): r101 fight 0 MISALIGN, halt / missing 0 (reached the fight, PS2 world and
  actors drawn); the door103 run reached r101 only in 60 s (the door is covered by STRICT and the KOS door runs).
- KOS squeeze 48 KiB (twin fpa2sqW, mastered on the test 13 release tree): GATE PASS, 10 runs: fight min 6,488 B, call
  39,944 B, door 20,528 B, leave100 / leave103 6,688 B; 0 out-of-memory / MISSING / HALT.
- Ready for test 15: yes (exact, render only; small: -0.3 / -0.4 ms MODELLED, -0.35 / -0.46 corrected).

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

## B4 rescoped: offline occlusion PVS (coordinator 10-15, ceiling measured first)

Existing culling in the PS2 world path (native_static.cpp), so nothing is duplicated: the pass mask byte per placement;
lean::world_out (world-plane pretest of the placement box); the placement box frustum + 25 m depth cull (box_class /
group_visible); per cluster the same box test, then the LOD level and strip-group selection (sg_select); the fog far.
Visibility data: only PS2_INTERIOR_CULL (r100 house interior portals, offline) and PS2_AREA_HIDE (r107: the PS2 room
code's per-area SMD groups). No occlusion culling for outdoor rooms; no GC / PS2 PVS data.

Ceiling (MODELLED-free count, the user's camera positions): the game logged its camera every frame (PS2_PVS build, warp
line "pvs 2"), frames 500..799: 56 cameras at the r101 cross, 35 at the r103 farm (cam-cross / cam-farm runs).
tools/d367/ps2world/pvs/pvs_cast.cpp "ceil" shoots a ray through every pixel (640 x 480; 2560 x 1920 on 8 cameras to
check convergence) with the game's projection, from the near plane to the 25 m cull depth, against the package's
level-0 triangles (only opaque, static triangles occlude; one-sided ones only from the front). A cluster instance is
visible when any ray hits it before an occluder. "In frustum" = the instance's world box is inside the frustum and the
25 m depth (what the existing culls keep). Vertex counts are level-0 meshlet vertices.

| scene | in frustum (verts / instances per frame) | visible | occluded share (exact, per view) |
|---|---|---|---|
| r101 cross | 37,568 / 210 | 18,877 / 90 | 49.8% (47-55%); 48.1% at 2560 x 1920 |
| r103 farm | 32,056 / 142 | 23,153 / 101 | 27.8%, but all of it is dynamic placements (125 of r103's 134 placements have a unique id); static only: ~0% |
| r103 farm, dynamic placements also occluding (baked spots) | 32,056 | 18,543 | 42.2% |

What an offline cell PVS keeps of that (r101 cross, same cameras, the set of the camera's cell intersected with the
frustum; level-0 vertices drawn of the 37,568 in frustum):

| cell set | drawn | cut |
|---|---|---|
| exact per view (the ceiling, needs per-frame occlusion) | 18,877 (50%) | 50% |
| 2 m cells, eyes 1.0-2.8 m, 3x3 per cell, 16k directions, no dilation | 32,953 (88%) | 12% |
| 2 m cells, conservative (neighbour cells + 3 m near + non-opaque within 60 m) | 34,228 (91%) | 9% |
| 4 m cells, eyes 0.4-3.6 m, conservative (the whole room: 86 KB file) | 35,094 (93%) | 7% |

Why the cell set loses most of it: moving the eye 1-2 m sideways or up reveals a sliver of many clusters between the
houses (535 clusters, each a large piece), and one pixel makes a cluster visible. Per-view occlusion is real (half the
in-frustum world at the cross); a static per-cell set captures a fifth of it.

ms: at the cross the per-cluster world work (everything in scenery except the ~1.6 ms placement walk) is ~15 ms
MODELLED for ~37.6k in-frustum level-0 vertices, so a cut share s is worth about s x 15 ms MODELLED (x1.23 corrected).
This overstates: the occluded clusters are the far ones, drawn at coarser LOD levels.
- cell PVS (7-12%): ~1.0-1.8 ms MODELLED, ~1.3-2.2 corrected, at most. r103 farm: ~0 (its occludable world is
  dynamic placements, which a static set must keep).
- per-view ceiling (48-50%): ~7 ms MODELLED, ~9 corrected, only with a runtime occlusion test that is itself cheap
  (e.g. a few large occluders per room - house boxes - tested against cluster boxes per frame, like the r100 interior
  portals); not built.

Runtime (built, default 0, in the tree): PS2_PVS=1 (t2exact.mk) reads /cd/dc/native/rXXX/ps2-world.pvs, finds the
camera's cell once per frame and skips clusters (and whole placements) whose bit is clear. Runtime toggle
re4dc_ps2_pvs_on (default PS2_PVS_DEFAULT=1; warp line "pvs 0|1"; re4dc_ps2_pvs_set() for a benchmark sweep row);
"pvs 2" = no set + a per-frame PS2CAM camera log line (used above). No file / another package's file / a camera outside
the cells: no culling. Run so far: the camera-log mode (cam-cross, cam-farm: halt / missing / fault 0, file=absent
path); the set path has not run (no .pvs on a disc yet). Knob-off identity: test 13 image c1ae83dd + 6 overlays.

Tools (tools/d367/ps2world/pvs): pvs_prep.py (package -> instances + triangles), pvs_cast.cpp (cell sets; "verify"
random eyes; "ceil" logged cameras), pvs_emit.py (conservative sets -> .pvs file, stats, verify).

### PVS format (shared with lane worldlod)

Cluster instance id = position in this walk of the package: placements in R4PW array order; for each, its mesh's parts
in order; for each part, its part_lod clusters in order (first_cluster .. +cluster_count). r101 (bake13 package): 223
placements, 554 instances. A far-LOD level added to a cluster keeps the id (it is the same cluster). The .pvs file
(pvs_emit.py docstring): 64-byte header R4PV v1 with the package's mesh crc / bytes and R4PW crc, an X/Z grid (x0, z0,
cell mm, nx, nz) of 8-byte cells {u16 set (0xffff none), i16 ylo, yhi decimetres}, then deduplicated bit sets
((ninst+7)/8 bytes, bit i = instance i). Memory (heap 4): r101 4 m cells 86 KB (+ 0.5 KB offsets); 5 m cells 55 KB.

Verdict: the r101 cell PVS is worth ~1-2 ms MODELLED at most (under or near the coordinator's ~1 ms bar once LOD is
counted), r103 ~0. Stopped here for the coordinator's decision (10-15: "if under ~1 ms at the cross, tell me before
building more"). The per-view ceiling (~7 ms MODELLED) points at runtime occluder tests instead.

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

## B5: I-cache code size (HOT_COLD_SPLIT)

Knob HOT_COLD_SPLIT=1 (t2exact.mk; exact, code placement only): every C++ / C object gets -include cold_decls.h, which
declares re4dc_log and re4dc_missing cold; GCC then lays the blocks that only lead to a log line / MISSING report after
the hot path of each function. The image shrinks ~4 KB (text 2,694,004 -> 2,689,876).

Tried and rejected:
- -freorder-blocks-and-partition (cold blocks in a separate .text.unlikely section): does not assemble on SH ("pcrel too
  far": the hot part's constant pools end up out of reach).
- the same + -freorder-blocks-algorithm=stc for the -O1 objects: text +13 KB (block duplication), I-cache fills not
  lower (cross 108,194 vs 108,990), D fills +11%; MODELLED cross 59.6 (layout).

MODELLED fill counts (the model counts misses right; it cannot price them: console A/B only), frames 500..799:

| scene | control I fills / frame | HOT_COLD_SPLIT=1 | D fills | MODELLED ms |
|---|---|---|---|---|
| r101 cross | 108,990 | 104,362 (-4.2%) | 144,203 -> 145,055 | 57.3 -> 57.0 |
| r103 farm | 154,741 | 153,846 (-0.6%) | 213,931 -> 211,847 | 88.0 -> 83.7 (farm runs differ by 0.8M instructions of disc / KOS work: not comparable) |

Image b5drW (committed knob) = b5crW (measured) objcopy image 24960240. Knob-off identity: test 13 image c1ae83dd.
Not done yet: STRICT (it changes block order in logic code too: needs the trace pair), align / KOS gates, and the
console bench disc (bench/definitive 702d82ef via t14/bench aa7554d6 + this knob, Part 1 fixtures, same-tree control;
branch lane/t2exact-bench, worktree /root/probe/lanes-20261015/t2exact/bench, no commits yet).
Finding for A6 / B5: layout alone moves the cross by up to +2.5 ms MODELLED (B4's code growth), more than this lever.
