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
(padded). Not in T11_DATA. A test 12 recipe adds `objs` to its --data list.

## Gates and measurements

(pending: Flycast runs held until the test 11 gate is done)
