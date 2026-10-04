# PS2 world coverage: packages -> validated manifest -> runtime room list

The native PS2 world (PS2_WORLD_MESH + PS2_WORLD_ROOMS, `game/platform/native_static.cpp` ps2_open / ps2_pass) draws a
room from `/cd/dc/native/r%03x/ps2-world.{re4mesh,r4pw}` plus its `dc/tex` packages. Which rooms try is
`re4dc_ps2_world_room`: a hand list (r100 r101 r103-r107) by default, or with `PS2_WORLD_REGISTRY=1` the bitmap
`game/platform/include/ps2_world_rooms.inc` that `world_registry.py` generates from validated packages. A listed room
whose package is not on the disc (or does not fit the heap) logs `PS2MESH open failed` and opens its own scenery
package, exactly as a failed open does with the hand list. By default that fallback only draws an oct scenery
package: the scenery path adopts with prelit=false (native_static.cpp open()), so a `convert_room_bins.py --color
prelit` package (route r104-r107, any room with more than 16 CLR0 colours) is rejected ("color encoding") and the
room has no world (its source BINs were released). `SCENERY_ENCODING=1` adopts each scenery package by its own header
encoding (room/instanced_mesh.hpp adopt_by_encoding: prelit corners drawn as stored, parts marked lit, never relit;
unknown encodings rejected). Measured 2026-10-03: r104/r107 (route walk, both PS2 packages removed) and r210 draw
their prelit scenery with it, and are rejected without it.

Prelit is not the source lighting: it stores CLR0 alone, with no light, no ambient and no GC TEV scale, so the fallback
is near black (r210 hall luma 6.4). The source path (room/source_lighting.cpp, applied once per part at its first draw)
is material(CLR0) x clamp(ambient + lights) x TEV scale; oct packages feed it a palette of at most 16 CLR0 colours.
`convert_room_bins.py --color oct-vertex` (encoding 3) keeps every vertex's CLR0 x colour scale in a per-vertex table
with the oct normal in the slot, and SCENERY_ENCODING=1 lights it in the same light_part as oct: any number of
colours (r210: 209, one mesh 207; r106: two meshes of 35), no double lighting (r40c, 2 colours: oct vs oct-vertex
frames pixel-identical; r210 hall luma 16.2).

`PS2_WORLD_FOG_SOURCE=1` (native_ui.cpp) gives the PS2 world headers table fog only while the source GX fog is on
at the scenery draw, as model_bridge.cpp does for model parts. Without it they always take table fog: a room whose
source fog is off (r210) is drawn as the fog colour (flat grey) on a direct entry, or with the previous room's table
after a room change.

The fallback draws the room's GameCube textures, 16-bit as prepare_native_ui.py wrote them: r40c and r210 exceed VRAM
(thousands of "upload FAILED"). Stage them under the play rule (tools/d367/texture-vq-rooms.sh: vq_native_ui.py
--model-min-bytes 32768 over the textures a run loaded; keys and dimensions unchanged): r40c 3.1 MB -> 0.46 MB.

`PS2_OPEN_READ=1` (needs IO_ALIGNED=1) reads the package pair through read_package: r210's 6,120 B sidecar hit the
KOS stream stall R4_5A with a plain fs_read (`PS2_OPEN_TRACE=1` logs each ps2_open step).

A world package does not make a room playable. A room is enterable only after the route lane's bring-up
(`docs/lanes/route.md`: room container via le_mirror + `prepare_native_ui.py --compact-room` + `room_smd.py release`,
AICA banks, enemy modules via `assets.sh discover --wire`, warp preset, fixture via `route/make-route-fixtures.py`).

## Files

- `ps2_world_check.cpp`: the runtime's acceptance test on the host (MeshPackage::adopt with lod + prelit, built like
  the play recipe with TREE_IMPOSTOR=1 MESH_TEXTURES=1, and ps2_open's R4PW checks line for line). Keep it in step
  with ps2_open. Prints the heap-4 block the open allocates, the placed world box and the part texture keys.
- `world_registry.py`: per room on the GC disc 1 / PS2 AFS: sources and hashes, the package (the one route fixtures
  stage, else `<corpus>/out/<room>-ps2`), validation, staging, registration and runtime evidence. Validation: runtime
  open; textures as the game loads them (open_streamed + validate() rules, part size, sha256 bound); identity (PS2
  route-graph points and GC door arrivals inside the world box); provenance, fail closed (converter report naming the
  package hashes, its inputs, an extraction-manifest record whose AFS member hashes equal the configured disc's
  bytes, every input hash; LEGACY binds r101's exact package/report/source). Evidence: a run counts only if it staged
  the same mesh + sidecar and the game read the same bytes for every part texture under the tested image's
  TEX_PACK / QUALITY_ASSETS precedence (pack member > loose file; texlow never packed); otherwise `unverified` with the
  reason. Writes `world-coverage.json` (schema re4dc-world-coverage/1) + `.md`, and with `--inc` the runtime bitmap.
  result: `native` (a clean run read these bytes: observed views only), `unverified` (valid, no such run),
  `fallback` (no valid package: blockers say why).
- `room_fixture.py`: a route-run.sh fixture that warps into one brought-up room (below).
- `tests/test_ps2_world_registry.py`: the .inc decodes to its room list and keeps the hand list; the checker's
  reject reasons; texture loadability; fail-closed provenance (report / manifest / input / member hash removed or
  changed); pack-vs-loose precedence; the keyed door cache.

## Add the next room (example r108; WSL unless noted)

```bash
T=port/dreamcast/tools
S=<owned corpus root>                    # e.g. .../world-coverage/ps2rooms-st24 (inputs/, aux/, out/ under it)
# 1. PS2 scenario inputs + GC LIT cut 0 (TEV scale) for the room
python3 $T/ps2_room_extract.py --out /root/probe/<lane>/extract --inputs "$S/inputs" r108
python3 $T/gc_room_lit.py r108 "$S/inputs/r108/gc-lit-cut0.json"
# 2. Convert (Git Bash + Windows Python, the ps2rooms lane's approved PS2-pattern bake)
python $T/ps2_room_r4im.py r108 "$S/inputs/r108" "$S/out/r108-ps2" --color-light ps2 --lod-uv-guard 0.002
#    (--lod-uv-guard: level-0 simplification must not collapse across UV seams; without it r100's wainscot and r210's
#    doors show diagonal smears. The route packages are the -uvg rebuilds.)
# 3. Validate + regenerate the manifest and the runtime list (add --corpus for every corpus root you use)
python3 $T/d367/ps2world/world_registry.py --out <evidence dir> --inc port/dreamcast/game/platform/include/ps2_world_rooms.inc
# 4. Stage it with the room's route fixture (make-route-fixtures.py ROOMS: (package dir, movies, banks)) and run a
#    PS2_WORLD_REGISTRY=1 image through it; re-run step 3: the room turns `native` when the run is clean.
```

## Enter a room outside the route (St2 / St4; measured with r40c and r210, 2026-10-03)

Image: `PS2_WORLD_REGISTRY=1 WORLD_STAGE_MODULES=1` (links st2_0, st4_0 and pl11, Ashley's partner module).
```bash
# room container + scenery + banks (private outputs): le_mirror --native-rooms, prepare_native_ui.py (room textures
# and --compact-room --compact-room-mips: ROOM_CONTRACTS entry), convert_room_bins.py (oct when the room has <= 16
# CLR0 colours per part, else --color oct-vertex with a SCENERY_ENCODING=1 image), room_smd.py release (one archive per call),
# aica_banks.py build --fixed-route title,r100,r101,r103 (ROOMS entry)
python3 tools/d367/ps2world/room_fixture.py --room r40c --preset r40c-entry --base <play fixture.json> \
  --rel <rel dir> --aica <aica dir> --scenery <pkg dir> --room-tex <tex dir> --ps2 <ps2 package dir> \
  --file em/pl08.drs=/root/probe/lanes/route/aica-r104/em/pl08.drs --tex /root/probe/lanes/route/tex-pl08 \
  --tex <pairs dir> -o <fixtures>/r40c-entry.json      # --no-ps2 instead of --ps2: the fallback arm
```
- Leon is costume 1 outside St1 (pl08): the GC pl08.drs (1,057,792 B) exceeds the 869,728 B player area
  ("native player read REJECTED"); stage the route lane's pl08 set as above.
- Missing pair pictures ("native UI: pair missing"): `tools/d367/pairs_from_log.py --log <run-output> --file
  stN/<room>.das ...` builds them; stage the output with `--tex`.
- Rooms whose script spawns enemies need their enemy modules and archives (assets.sh discover lists them); r210 and
  r40c have none. r210 needs Ashley's images (prepare_native_ui.py over em/pl11.drs).
- r210 poses: `r210-entry` (the r206 door arrival, facing a wall) and `r210-hall` (the door 4 arrival inside the
  main hall: stairs, balustrade, columns).
- Room lifetime between rooms without a wired door (DIAGNOSTIC, not a door route): a `WARP_JUMP=1` image and warp.txt
  lines `jump <room frame> <from> <to> x y z ang` (the source's SceAtExecRoomJump); merge both rooms' fixtures.

## Rooms that cannot be converted from the configured sources

- St3 / St5 (r3xx, r5xx): the PS2 disc has their scenario models, but the approved bake needs the room TEV colour
  scale from the GameCube LIT, which is on GC disc 2 (sources.toml gc_iso2 empty). The PS2 LIT is a different
  format (r106: 60 cuts vs the GC's 8; other TEV bytes), so it cannot stand in. Needed: GC disc 2 configured, then the
  steps above unchanged (or `--tev-scale` per room from a reviewed source).
- r120: no scenario SMD (the intro cinematic room).
