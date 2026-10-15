# Lane objs: PS2 room objects for test 12 (2026-10-14)

User decision 2026-10-14: room objects go in test 12. A GameCube model on screen is a bug; PS2 assets are the target;
collision and game logic stay GameCube. Priority from the user (10-14 evening): r101 (village) fps first.

Worktree /root/probe/lanes-20261014/objs/tree, branch lane/objs from lane/t11 eb4e8813. Work dir
/root/probe/lanes-20261014/objs/work (scripts, out/<room>o|p, fixtures in ../fix). Private dars:
re4-assets-private\objs-20261014\<room>o (unpadded) and r100p / r101p (payload padded to the source size). Evidence
C:\Flycast-Evidence\re4-dreamcast\objs-20261014 (D: is below its 15 GB floor).

## What was already there (correction to the brief and to PARITY-CENSUS-20261014 section B)

Phase 2 item B1 did land, partly: tools/ps2_objects.py is in lane/t11 (2f6f85c6, 6f45a468, ed82fe46) and the test 8 /
9 / 10 / 11 package fixtures stage the p2b 10-11 object dars for r100 r103 r104 r106 r107 r108 r10a r10b r117 r118
r11a r11b (r119: r119c). Those dars skipped every object whose PS2 mesh is not smaller ("PS2 not smaller"), and r101,
r102, r105, r109 had no object dar at all. Offline census of the test 11 disc (objs_census, below): 54 room models
were still GameCube geometry, all 18 of r101's.

## Tool changes (tools/ps2_objects.py)

- `--keep-larger`: converts an object whose PS2 mesh has as many or more triangles (PS2 doors, racks and the r106 set
  piece 0x34 are more finely tessellated than GC). Without it the tool reproduces the 10-11 dars byte for byte
  (r100b 7e570668..., r103b c35c9a7e... checked 10-14).
- `--world-owned <GC arc>`: the GC room BIN the PS2 version draws as part of its scenario SMD. The GC copy keeps its
  header, joints, part headers and order with no triangles (one unused vertex / normal / UV so no array is empty).
  r101 BIN 0x20 = SetObj00 at (-2880, 50, 2810) = the burning stake in the square (5,277 GC triangles; sound and fire
  effect are separate). The PS2 r101.dat has no such BIN; its scenario SMD has the stake (SMD_016, 997 faces, and the
  pole SMD_120, 32 faces), and the r101 PS2 world package draws all 209 SMD placements (world-mesh-r21 package-uvg,
  ids file: SMD_016 -> SMX 0x0a). So test 11 drew the stake twice: PS2 world + GC object.
- A model with no PS2 triangle is refused unless world-owned: the window panes et0000 / et2500 are PS2 placeholders
  (one degenerate triangle); converting them would silently delete the GC pane.

## Room table (offline; GC models -> PS2, per model, not per instance)

Sources: the dars the 10-11 p2b packages were made from (audio-overlay / aica-rNNN / design-r103 w8b-rel; sha256
equal to each p2b report's dar_in), regenerated 10-14 with `--keep-larger`. Payload = the room archive read into
heap 4 at room entry ("DVD: Mem Alloc"); delta vs the test 11 disc.

| room | converted (GC tris -> PS2 tris) | still GC (why) | payload bytes test 11 -> objs |
|---|---|---|---|
| r100 | 7 set pieces + 0x33 (158=158), et0001, et0100, et0200, et0d00 door 56->176 | et0000 window (PS2 placeholder) | 1,602,816 -> 1,604,832 (+2,016) |
| r101 | stake 0x20 5,277 -> 0 (world-owned), door lock 0x1e 510=510, bottle 0x25 113=113, et0001 76->74, boxes et0100/0200 44->12, door et0300 870->392, racks et0400 346->460 / et0500 240->564, ladders et0600 144 / et0800 168, window frames et0700 84->252 / et0701 114, door et0d00 56->176, box et1100 164->68, box et1e00 212->76 | et0000, et2500 window panes (PS2 placeholder) | 1,848,800 -> 1,738,624 (-110,176) |
| r102 | et0100, lamp et0a00 828, door et0d00, et1100, door et1300 870, windows et2c00 80 / et2c01 93 | - | 1,277,408 -> 1,278,560 (+1,152) |
| r103 | + rack et0500 240->564, ladder et0600 144 | - | 1,434,880 -> 1,441,088 (+6,208) |
| r104 | + set piece 0x20 464, ladder et0600, barrel et1200 60, door et1300 870, door et1700 84->204 | - | 1,274,880 -> 1,279,648 (+4,768) |
| r105 | et0001, et0200, et1100, box et1f00 268, door et2200 870, et2400 56->366 | et0000, et2500 window panes | 1,399,936 -> 1,405,344 (+5,408) |
| r106 | + set pieces 0x20 464, 0x32 510, 0x34 324->612, 0x36 388, rack et0500, door et0d00, box et1f00 | - | 1,607,424 -> 1,621,120 (+13,696) |
| r107 | + window frames et0700 / et0701, door et1600 196->468, door et2b00 56->176 | et0000 window pane | 1,321,984 -> 1,331,008 (+9,024) |
| r108 | + box et1f00 | - | 1,328,480 -> 1,328,672 (+192) |
| r109 | torch et1000 414, box et1100 164->68 | - | 532,672 -> 530,624 (-2,048) |
| r10a | + set piece 0x20 464, box et1f00 | - | 1,646,304 -> 1,646,880 (+576) |
| r10b | + box et1f00 | - | 1,650,976 -> 1,651,168 (+192) |
| r117 | + door et1600 196->468 | - | 853,728 -> 858,048 (+4,320) |
| r118 | + box et1f00 | et1400 torch (absent from the PS2 ETM) | 1,361,632 -> 1,361,824 (+192) |
| r11a | + box et1f00 | et1000, et1400 torches (absent from the PS2 ETM) | 1,419,968 -> 1,420,160 (+192) |
| r11b | + box et1f00 | et1400 torch (absent from the PS2 ETM) | 1,433,920 -> 1,434,112 (+192) |
| r119 | unchanged (r119c: BIN 0x22) | et1000, et1100 (look lane dark block with both converted; not regenerated) | 1,298,208 |

"+" = in addition to what the test 11 dar already converted. Not covered by this lane (no change, listed for the
census): pickups / ITA item models and blue medals (ITM), characters (em2a traps, em24 snakes, ...), the boat pl0f,
Efm debris, Del Lago parts. The census's "r101 bell obj14" is not an object: SetObjBell is used only by r201 / r218;
the r101 bell is in the scenario SMD (PS2 world).

Offline census (`work/objs_census.py`, classifies every room / ETM model of a staged dar against le_mirror(GC)):
test 11 disc 54 GC + 15 known; objs 0 GC + 15 known (windows, PS2-absent torches, r119), exit 0.

## Switch

Disc data only (the executable is unchanged, so the knob-off image is the test 11 image by construction). Data sets in
tools/d367/test11/t11-fix.py: `objs-<room>` (one room, unpadded), `objs` (all 16 rooms), `objs-r100p` / `objs-r101p`
(padded). Not in T11_DATA. Since 10-15 the `objs-<room>` sources are the shared library copies
(ps2lib/objects/<room>/<room>.dar, byte-identical). A test 12 recipe adds `objs12` (r100 + r101, gated) to its --data
list; `objs` (16 rooms) is test 13.

## Gates and measurements

Builds (lane/objs eb4e8813 code = the test 11 release code; test11/t11-build.sh with K/T/LP=objs): objstW (tW: warp +
PC_SAMPLER, elf 36265277...), objstT (tT trace, 2a8cdcf3...), objsmW (mW: TEX_CHECK=2 + MCHECK_LEONGC, 7c0105ec...).
Every arm pair below = the same image, fixtures from t11-fix.py with T11_DATA (control) vs T11_DATA + objs set (test).
Runners: work/o-run.sh, o-trace.sh (trace_lock), o-strict.sh, o-hw.sh; queue _tools/qs3.sh + qjob3.sh (host cap 8
Flycasts, C: floor, one staging at a time). All numbers are Flycast / SH-4 model = MODELLED, not console.

### r101 (first, user priority)

- Warp-in STRICT (objs-sq101 = st-square without its still freeze; stop tick 2400): sq101c-t vs sq101o-t2 STRICT 2402
  ticks, decision_cmp MUST-IDENTICAL, 0 HALT / MISSING / FAULT / LEONGC / overrun. (The first objs run sq101o-t was
  cut after 10 s by the harness C: capacity guard: RUN_FAILED, not a game result.)
- Village view mcheck runs (objs-v101: Leon west of the square facing the burning stake, fight live, 150 s): objs
  LEON-GC PASS; TEX_CHECK FAIL on one key, 9fe00ef7-6123f7d5 256x256 "PVR texture allocation failed / frag-latched"
  (frame 1228); the test 11 control fails the same key twice (frames 517, 1224): pre-existing in test 11, not from
  this change. Stills: the stake (now only the PS2 world copy) and the Ganados look the same; sheet
  C:\Flycast-Evidence\re4-dreamcast\objs-20261014\sheets\r101-before-after.png.
- hw model (hwproject, objs-v101 view, global frames 1330:1409, stride 7; 5 Ganados drawn per drawn tick), CPU work
  per drawn tick without the wait rows (bench-split.py over proj-drawn):

| arm | traced drawn ticks | CPU work ms (hw nominal) | actor/model submit | frame/TA/UI | world submit |
|---|---:|---:|---:|---:|---:|
| test 11 (v101c) | 6 | 85.16 | 22.69 | 8.16 | 16.74 |
| test 11 (v101c4, stride 4) | 20 | 82.59 | 22.69 | 7.87 | 16.73 |
| objs-r101 (v101o) | 6 | 80.98 | 19.42 | 6.85 | 16.71 |

  The saving is the stake's 5,277 GC triangles plus the smaller etc models: re4dc_avk_pos_rigid_s16 2.13 -> 0.83,
  texture hash_bytes 2.53 -> 1.44, pass_baked 0.78 -> 0, Part::whole 2.61 -> 2.01. Target 50 ms per drawn frame (20 fps):
  CPU stays ~31 ms over it; objects are ~4 ms (5%) of the gap.

Other rooms: r100 (H2 STRICT h2c-t vs h2o-t 4702 ticks, 493 masked, MUST-IDENTICAL, s30 340/340 both arms, 0 overruns:
unpadded r100 holds with MOVIE_HEAP_PREFLIGHT) and r106 (wi106-c vs wi106-o warp STRICT 2402, MUST-IDENTICAL).

### Test 12 scope for objects (coordinator 10-14)

The all-room objects pass moved to test 13; the village (r101 fps) went first. Test 12 data set: `objs12` = r100 + r101
from the shared library (ps2lib/objects/<room>/<room>.dar, byte-identical to the lane's <room>o dars; rows PASS). r106
passed warp STRICT (wi106-c vs wi106-o 2402 ticks, MUST-IDENTICAL) but has no TEX_CHECK / LEON-GC run yet: its rows say
`UNGATED:wi106-o(...)`. `objs` (all 16 rooms) stays defined for test 13. `objs-r11a2` (r11a + et1000 torch from r109's
PS2 ETM) and `objst-<room>` (PS2 pictures, re4-assets-private/objs-20261014/tex13) are test 13 and NOT READY: the
picture tool swaps only the colour image, so ModelPart flag-4 parts (racks et0400 / et0500, lamp et0a00) would hit
"pair missing" (items lane relay 10-14). Before test 13: reuse lane/items 421b7251 (ps2_items.py v2 + ps2_items_tex.py)
pair logic (mask from the PS2 TPL entry of the same index, 4-bit masks n*17, resampled to the colour size, colour RGB +
mask alpha, GC-opaque colours packaged opaque), reconvert the whole class, gate, then write the ps2lib rows.
GC textures left in converted objects: r100 BIN 0x33 (Leon archive texture), r117 BIN 0x1f.

## Village world submit (r101 release gate, lane/objs-w)

Coordinator 10-14 night: no release until benchmark-r101 <= 50 ms in the hw model; this lane owns world culling and
submit. Branch lane/objs-w (worktree /root/probe/lanes-20261014/objs/w) from crowd12's STACK V3 (lane/crowd12-s2
7e3b2e94 + 48c95b5e). Every number below is MODELLED (Flycast PC sampler + SH-4 hw model, hwproject nominal), not
console: build = c12V3 knobs (HW_FOG_HAZE=1 FX_LEVEL=0 FX_SPRITE_TRIM=2 UI_SOURCE_LRU=1 ACT_CAP_FAR_M=15 ACT_CAP_LOG=300
TEX_PAL4_ALPHA=1 FX_PS2_PACK=1 FX_FLIPBOOK=2 R101_ALIVE_CAP=8 TEX_WRAP_SAFE=1 PACE_MODE=off PC_SAMPLER_BYTES=8192) + the
arm's knobs, test11/t11-build.sh tW; scene benchmark-r101-v3 (Leon by the pyre facing the square, 12 alive, crowd
alerted at room frame 30, god mode, no pad input); global frames 500:1399, trace stride 60 (15 traced frames); data
tex-v3-ws.pak + objs r101o. Evidence C:\Flycast-Evidence\re4-dreamcast\bench-20261014\hwmodel-<arm>-r101.

Base (hV3, c12V3htW): total 71.83 ms, world submit 16.13 (transform_sched 5.64, walk_lean 2.59, MeshDraw::draw 1.57,
group_visible 1.39 at 1170 calls/frame, clip_strip 0.85, ps2_pass 0.75, MeshDraw::run 0.70, concat 0.45 at 303 calls,
load_screen 0.32, dyn_source 0.21), actor submit 18.55.

### Draw distance (rule: PS2 per-room View far if <= ~1 hw ms CPU and GPU well under budget)

| room / view | 25 m | 40 m | View far | decision |
|---|---|---|---|---|
| r101 benchmark view (old objs base, hw 700:899 stride 7): world submit / total ms | 16.15 / 88.32 | 22.11 / 91.27 | 24.80 / 98.36 (70 m) | stays 25 m (coordinator 10-14: rule); church / houses behind the stake are sky at 25 m (sheet far-r101.png) |
| r101 GPU proxy ms | 9.75 | 10.16 | 8.93 | |
| r100 bridge view (w100, 700:819 stride 7) total ms | 33.27 | 33.27 | 33.27 (42.7 m) | View far free at this view (7 placements drawn either way; GPU proxy 11.69 = 11.69); one view only, not a wide one |
| r11b x11b view (rsf 0x11b 0 + goto 200 -58471 1875 -12698, hw 700:819 stride 7): world / total ms | 7.93 / 65.01 | 9.15 / 66.56 | 9.49 / 66.28 (270 m) | stays 25 m: View far +1.56 world / +1.27 total (just over ~1 ms), no visible gain (sheet far-r11b.png) |
| r11b GPU proxy ms | 17.50 | | 17.51 | |

(The first r11b rows, w11b entry warp, were invalid: the r11bs00 entry movie covers the window, then the screen
stays black.) Decisions: r101 25 m, r100 View far, r11b 25 m. Source View far known: r101 70 m, r100 cut 0 42.7 m (house cut 24.8 m, the source's own). The other route rooms need
a View-far run each (FOG_FAR=1000000 FOG_FAR_CAP=1 logs cull_far per pass) or a parse of the room camera data: not done.

### Options ranked (estimates first, then built)

| item | estimate (MODELLED) | built? | measured world / total (base 16.13 / 71.83) |
|---|---|---|---|
| (e) strip groups: reject before transform | 47 % of walked strips are culled after transform; 46 % of transformed vertices feed only culled strips. Cost model (40 cyc/vertex, 80/strip, 100/group test) with the real kd-split records: vertices 22,952 -> 16,728, strips 5,661 -> 3,926, saves ~1.3 model ms | yes, PS2_STRIP_GROUPS=1 | 15.08 / 70.85 (oe23s) |
| (b) placement bake + (d) repeated per-frame work | group_visible 1.39 + concat 0.45 + dyn_source 0.21 are the repeated parts | yes, PS2_WORLD_LEAN=23 | 15.90 / 71.94 (hy23): -0.2 world, total within noise |
| (c) cell PVS | at the bench view a per-view z-buffer hides 4-8 % of vertices at cluster / meshlet level, 0.1 % at placement level: <= 0.3-0.6 ms ideal, less from a cell; r101 heap free ~1.05 MB at the bench | no (not worth it for test 12) | - |
| MESH_CLASSIFY=1 (existing) | - | arm owc | 22.30 / 78.53: rejected (classified meshlets take the unscheduled transform and the old walk; MeshDraw::draw 6.43) |
| Morton strip order before meshlet chunking | worldlean/morton.py (lane/objs-w) at the bench eye: re-chunking each cluster's level-0 strips in Z-order (same per-cluster meshlet limits; 588 -> 590 meshlets in view, corners 31,574 -> 31,476): without groups model 7.15 -> 6.61 (-0.54, the coordinator's -0.3..-0.5); on top of strip groups 5.29 -> 4.98 (-0.31 model, ~-0.25 hw by the (e) model-to-hw ratio) | not built: needs a re-meshleted r101 package + new r4sg + re-gate for ~0.25 ms; left for a decision | - |

### Knobs (lane/objs-w, all render only, default 0, game30.mk; knob-off image identical to c12V3htW de566ad4...)

- `PS2_WORLD_LEAN` (bitmask): 1 world-space placement pretest; 2 fully-inside propagation (a placement / cluster wholly
  inside every plane skips its children's tests; its box is grown by one grid step; meshlets nest in their clusters:
  0 of 1,726 outside); 4 cache prime once per pass; 8 diagnostics (check_bad, prime_bad, class_diff: all 0 over 3,600
  frames on every arm); 16 dyn_source 64-bit hash-mask fast reject. Helpers built at O2 (#pragma: native_static.cpp is
  -O1; the hw model priced the -O1 box test at ~370 instructions with fr0 spills).
  Arms: hy1 16.08 / 71.94, hy3 16.39 / 72.49, hy7 16.05 / 72.25, hy23 15.90 / 71.94. (The first ow* / ox* arms were
  invalid: the lean members sat before MeshDraw's positional initializers, so every PS2 part was refused; fixed 77d7972b,
  runs renamed *-INVALID.)
- `PS2_STRIP_GROUPS=1` (needs LEAN bit 2) + data `sg101` (t11-fix.py): ps2lib/world/r101-sg4 = tools/ps2_strip_groups.py
  --groups 4 of the test 11 r101 package (f5592282): strips of each meshlet kd-split into up to 4 spatial groups
  (opaque / punch-through only; translucent strips keep their order), corners renumbered by first use per group,
  indexed LOD meshlets re-pointed, same package size (1,207,456 B, crc recomputed); ps2-world.r4sg 110,496 B (16 B per
  group: grid box, strip end, corner range; mesh crc checked at open). sgcheck.py: every meshlet draws the same oriented
  triangles. Runtime: a meshlet crossing a cull plane (box_mask) tests its groups against just the planes it crosses
  (per-part plane forms P.hi + Q.lo + d, 1 unit slack, built once per part), then transforms / walks only the kept
  groups' corner and strip ranges.
  Iterations: oz23s box_class per group 17.74 / 74.93 (worse); ob23s plane mask 15.59 / 71.25; od23s per-part plane
  forms 15.30 / 70.99; oe23s crossed-plane list once per meshlet 15.08 / 70.85 (transform_sched 5.64 -> 3.87, walk_lean
  2.59 -> 2.00, group_visible 1.39 -> 0, concat 0.45 -> 0.26, dyn_source 0.21 -> 0.10; new sg_select 1.04, box_mask
  0.61, box_class 0.64, world_out 0.46).
  Proof the picture is unchanged: logic is deterministic, so the emitted-strip counters must match frame for frame; the
  cumulative `PS2MESH strips=` at frames 1200 / 2400 / 3600 are 2,992,329 / 7,212,667 / 11,731,041 on knob-off ow0 and
  on every knob-on arm (ox31, ob31s, od31s, ocpm, oe31s), while transformed vertices fall 100.6 M -> 68.6 M (od31s).
  Stills: sheets\sg-r101-bench.png (Flycast framebuffer, knob-off ow0 vs od31s at the same wall seconds; differences are
  the moving Ganados / camera).
- `PS2_ROOM_PIN=1` (native_ui.cpp): r101's 9fe00ef7-6123f7d5 (256x256 PS2 world texture, 128 KB) is never LRU-evicted
  during the visit (set at each room preload: `PS2PIN room=101 key=...`), so it cannot reload late into a fragmented
  pool (test 11 TEX_CHECK fail at frame 1228). ocpm (TEX_CHECK=2 + MCHECK_LEONGC, LEAN=23 SG=1 PIN=1, 3,600 frames):
  the texture loads once, TEXCHK PASS, LEON-GC PASS.
- Bell route with the 110 KB r4sg in heap 4 (benchmark-r101-v3sgbell / v3bell = the v3 scene + `trg 0 1200`):
  r101s30 plays in both arms (knob on 1302 / 1331 shown, 29 dropped; knob off 1300 / 1331, 31 dropped). Both arms then
  stop at the same watchdog HALT main.cpp(548) at ui_frame 1526 (the long-movie haltExecCheck of this god-mode bench
  rig; identical knob off: not from these knobs).
- Image growth knob on ~6.5 KB (end 8c414dfc -> 8c41675c): heap 4 couples to image size (s30 gate above holds).
- Flycast bench (emulator wall, not hw): ow0 19.16 fps 52.2 ms; ob31s 19.58 / 51.1; od31s 19.52 / 51.2.

sg101 is derived from the r101 package the test 11 / V3 discs stage (re4mesh f5592282, r4pw 300a346f; checked in the
bench payload manifests). If a recipe stages a different r101 package, regenerate r101-sg4 from it (ps2_strip_groups.py
+ sgcheck.py): the data set replaces the re4mesh, and the runtime refuses a stale r4sg only by its mesh crc.

Recommended test 12 recipe additions: `PS2_WORLD_LEAN=23 PS2_STRIP_GROUPS=1 PS2_ROOM_PIN=1` + data `sg101`. Modelled
r101 bench: total 71.83 -> 70.85 (-1.0 ms), world submit 16.13 -> 15.08. The 50 ms gate stays ~21 ms away; the rest is
actor submit (18.55) and logic, not world culling.

### Pre-transform strip rejection (coordinator 10-15 item: price first)

Already built: PS2_STRIP_GROUPS is per-meshlet strip-group bounds baked offline into the package (r4sg) and tested
against the frustum before transform. Pricing finer bounds from the existing counts (worldlean/stripcull.py at the
bench eye -15300,1721,2377 yaw 90 pitch -8; MODELLED cost 40 cyc/vertex, 80/strip, 100/group test; base transform +
walk 6.85 model ms): sorted groups of 4 (shipped) save 1.86, 8 save 1.89, 16 save 1.55, 64 (about per strip) 1.15.
Finer rejection gains nothing more: the group test itself costs more than the vertices it saves. At runtime strips
culled after transform fell from ~46 % to ~21 % of walked strips (oe31s: 3.2 M culled vs 11.7 M emitted over 3,600
frames). What is left is the group test (sg_select 1.04 + box_mask 0.61 hw ms); only a fipr/asm version might take
~0.5 ms off it, and that is not built (no measured case yet that justifies it under the CLAUDE.md rule).

### PS2 per-area scenery hiding: PS2_AREA_HIDE (lane/objs-w a5188bc0; PS2-ENEMY-CODE-DIFF-20261015 item 11)

- r107: PS2 st1_1.rel R107Main (0xf130) reads Room_flg[2]: bit 31 -> SMD groups 60 70 80 90 drawn, 50 100 hidden;
  bit 30 -> 90 100 drawn, 50 60 70 80 hidden; neither -> 50 60 drawn, 70 80 90 100 hidden (SmdSetTrans(id, 1) =
  drawn, be_flag bit 1). The bits come from PS2-only AEV flag areas (PS2 AEV record 0xA0 B, payload at 0x60): area 9
  -> flag 64 (bit 31), areas 10 / 11 -> flag 65 (bit 30), trigger inside, player.
- Port: r107.cpp tests the same three quads read only (no flag written; STRICT by construction) and hands the bits to
  native_static.cpp area::, which skips the hidden groups' placements from a baked table (room 0x107, package R4PW crc
  9081e7fd, 71 placements; any other crc or count logs "mismatch: off"). r11f's PS2 re-show of groups 30 / 15 after
  the barn event is already r11f.cpp r11f_ps2Area9 (game objects): nothing new there.
- Knob-off image identical (oa0htW de566ad4...). sa107-1b (w107 warp, v3pak): `PS2AREA ... ok`, state 0 hidden
  07800000 0fde0fc0; pass-0 placements 61 -> 41, parts 70 -> 46, transformed vertices 4.565 M -> 4.325 M (-5.3 %),
  emitted strips 753,960 -> 751,494; stills identical at that view (sheets\area-r107.png).
- hw ms: knob off ha107-0 world 7.38 / total 47.73 (MODELLED, hw nominal, 700:819 stride 7). Knob on: about -0.2 ms
  MODELLED from the counters; the hw-model rerun (ha107-1) is pending (Flycast freeze 10-15; the first ha107-1 ran on
  the crc-off binary and is renamed *-CRCOFF-INVALID).

### Static object bake hooks (answered crowd12 10-15)

- The 9 r101 cObj00 (BIN 0x20, burning stake) were not baked by this lane: the PS2 r101 scenario SMD already has the
  stake (SMD_016 + pole SMD_120) and the world package draws all 209 SMD placements; ps2_objects.py --world-owned 0x20
  (0f071172) empties the GC copy. Lighting: prelit PS2 vertex colour x SMX ColorRGB + fog, no dynamic lights.
- Hooks: R4PW placement per OBJ group ('g ...#SMD_n#SMX_id#'), ps2_room_ids.py -> ps2-world.ids (R4ID, crc tied);
  runtime: the native_static.cpp ps2_pass placement loop (where PS2_WORLD_DYNAMIC and PS2_AREA_HIDE skip placements).
  Smallest change for a game-owned bake: a per-placement owned bitmask + re4dc_ps2_place_gate(room, placement, draw)
  set in the object's move / matUpdate before render (< 1 KB). A late opaque submit is not cheap (pass 0 is submitted
  during the scene draw, the OP list cannot reopen).

## Test 14 objects (coordinator 10-15; ON HOLD from 10-15 ~02:00 for the village)

- tools/ps2_objects_tex.py v2 (47b8e299; the commit text says 125 images, the route set is 112 images + 22 pairs):
  flag-4 parts keep the mask record's GC key and get a pair package keyed (new colour key, GC mask key) holding PS2
  colour RGB + mask alpha; the mask is the PS2 TPL entry closest to the GC mask (4-bit n*17, accepted at mean abs
  difference <= 16, good matches <= 6), else the GC mask resampled; --pak proves each mask key (the GC pair must be in
  tex-v3-ws.pak). Outputs re4-assets-private/objs-20261014/tex14 (sha256.txt; tex13 superseded).
- Still GC pictures: r100 BIN 0x33 (texture from the Leon archive, outside the room archive), r117 BIN 0x1f (one GC
  image sampled by PS2 images 0, 1, 3). r10b / r11b BIN 0x1e / 0x1f masks keep the GC mask (PS2 error 45.8 / 97.2).
- Gates (fixtures fix/g14-<r>-{c,t}-objstT.json + g14-<r>-t-objsmW.json, evaluator g14eval.sh):

| room | warp STRICT + decision_cmp | TEX_CHECK=2 | LEON-GC | pair missing | PS2 keys seen loading |
|---|---|---|---|---|---|
| r102 | 2402 ticks MUST-IDENTICAL | PASS | PASS | 0 | 5 / 12 (window pair 711d7345 loaded) |
| r103 | 2402 ticks MUST-IDENTICAL | not run (mcheck refused: C: floor guard) | not run | - | - |
| r104..r11b | not run (on hold) | | | | |

- r119 (BIN 0x22 tree + ETM et1100 box): the look lane's "hang" is the scripted `freeze 950` + 30 s watchdog (all three
  arms hit it: r119c ui 712, r119b 696, r119t 738); logic is identical (t119-c vs t119-b and t119-c vs t119-t: STRICT
  902 ticks MUST-IDENTICAL); r119b-m / r119t-m / r119c-m all TEXCHK PASS, LEON-GC PASS, pair missing 0. The "dark
  block" is a broken-box fragment: GC draws white splinters, the PS2 et1100 geometry draws a flat dark-grey shard. The
  tex14/r119 PS2 pictures (3e0bf632-0f5d6eba tree, 058ec2b1-11e00663 box; both seen loading) do NOT change it (sheets
  r119-tex14.png, r119-shard-zoom.png: identical shard with GC or PS2 pictures), so it is not the picture: suspect the
  PS2 et1100 fragment part's UVs / normals / colour as converted. Open; r119 stays BIN 0x22 only (r119c) until then.

## Breakables stay GameCube (10-15 ~02:40; coordinator: documented exception "game logic reads the model's geometry")

- r119's dark block = the converted wood box et1100 (SetBox type 3): a run with only et1100 PS2 (GC pictures, r119-box,
  r119e-m) draws a flat dark shard at the break where GC draws white splinters (sheets r119-box-only.png). Not the
  picture (tex14 PS2 pictures: same), not the UV range (--uv-fold, u -0.96..-0.02 shifted into [0, 1]: same, r119f-m),
  not the normals (all outward). The box's break spawns effect models of et11.eff (EFM 0x09 / 0x19 / 0x2b, owner = the
  box cEm: EfmSetObj04(parent)); the GC box has 164 triangles (24 inward splinter faces), the PS2 box 68 (all outward).
  The exact coupling is not found yet (grep: no game code reads ModelData vertices outside rendering, shadows, bounds
  and debug); treated as the class below.
- Exception class (EtcModel.cpp, cEmBox / cEmBarrel): et0100 et0200 et1100 et1200 et1e00 et1f00 et2d00 et2e00/01
  et2f00/01 et3c00 stay GameCube in every room. In the converted sets: r100 et0100 et0200; r101 et0100 et0200 et1100
  et1e00; r102 et0100 et1100; r103 et0100 et0200 et1100; r104 et1100 et1200; r105 et0200 et1100 et1f00; r106 et0100
  et0200 et1100 et1f00; r107 et1100; r108 et0100 et1f00; r109 et1100; r10a / r10b / r11a et0100 et1100 et1f00; r117
  et1100; r118 et0100 et1f00; r11b et0100 et1100 et1f00; r119 et1100. The items lane's PS2 debris models
  (ps2lib breakables, e.g. r101 et11_efm09 / 19 / 2b) were gated with GC boxes and are unaffected.
- Test 12 data set objs12b (t11-fix.py; objs-20261014/r100b + r101b = ps2_objects.py with the r100o / r101o arguments
  minus the class; every other object identical): r100b sha256 c0eced0b..., payload 1,606,688 B (r100o 1,604,832; the
  GC source 1,918,528, so heap 4 / s30 is no worse than test 11); r101b fbb12e34..., payload 1,745,152 B.
- Gates (short runs, test 11 build objstT / objsmW, data test 11 + objs12b, 10-15 02:40-02:45):
  r101 v101 warp trace n101-c vs b101-t: 570 ticks MUST-IDENTICAL; b101-m TEX_CHECK=2 PASS, LEON-GC PASS, pair
  missing 0, halt 0. r100 w100 warp b100-c vs b100-t: 602 ticks MUST-IDENTICAL; b100-m TEX_CHECK PASS, LEON-GC PASS,
  pair missing 0, halt 0. (objs12n, r101 minus et1100 only: n101 570 ticks MUST-IDENTICAL, n101-m PASS / PASS.)
- Later (not test 12): the PS2 builds the box break from its own et11.eff (EFM 0x09 PS2 entry 19,424 B vs GC 12,512 B)
  with the 68-triangle box: converting the box together with the items lane's PS2 EFM debris (and checking the PS2
  break routine) is the way to make et1100 PS2.
- ps2_objects.py / ps2_objects_tex.py --uv-fold (cca4f2bf, default off): kept as an option (clamp-sampled objects).

## Place gate hook + world append (lane/objs-w; crowd12 STATIC_OBJ_BAKE)

- PS2_PLACE_GATE (7e3cc846, render only, default 0): re4dc_ps2_place_prepare_fn / _own / _gate; =2 diagnostic.
  Knob-off image identical (de566ad4); STRICT r101 gate=2 vs off (v101, pg-S / pg-2) 1802 ticks MUST-IDENTICAL.
- re4dc_ps2_place_ready (e818c023): lookup-only residency of a placement's part textures (r101: ready(0)=1, ready(8)=0).
- tools/ps2_world_append.py (c6cc9e59): baked COLOR OBJ groups + tex.pak-key materials appended to the shipped
  package (base tables byte-identical, selftest), then ps2_strip_groups.py (base region = ps2lib r101-sg4). Runtime
  check pa-3 (60 s): placements 212, PS2SG ok, boxes textured + tinted (sheets append-boxes.png).
