# Lane ps2rooms

Rules: port/dreamcast/docs/D367_WORKSTREAMS.md. Branch lane/ps2rooms, tree /root/work/lanes/ps2rooms, evidence
/root/probe/lanes/ps2rooms, private store `re4-assets-private\ps2rooms-20260930` (HANDOFF.md there).

## Goal

The PS2-sourced world for every remaining stage-1 room (user 2026-09-30: "build the remaining ... world sourced from
PS2"; environments are never cut without the user). Route order after r103 (R4_FIRST_STAGE_GAP_AUDIT.md "Full
stage-1 route"): r106, r104, r107, r105, r102, r108, r109, r10a, r10b, r11b, r11a (or r10c + r10e), r119, r118,
r117, r112, r111, r113, r11c, r11d or r11e, r10f, r11f (+ r10d optional; r120 has no scenario model).
Per room: package, numbers (size, meshes/placements, triangles, textures/VRAM, heap-4 fit), look sheet, in-game
capture when the warp rig reaches the room.

## Tools (this lane)

- `tools/ps2_room_extract.py` (WSL, mono): PS2 ISO -> AFS `<room>.dat` -> JADERLINK DATUDAS 1.0.4 (dat.exe) ->
  RE4_PS2_SCENARIO_SMD_TOOL 1.3.0 -> the converter's inputs (`<out>/inputs/<room>`) + `aux/<room>` (CAM/LIT/AEV/RTP)
  + `extract-manifest.json`. Tools pinned by sha256, run with -bat and stdin closed. `--remaining` = all rooms
  above; `--compare <root>` byte-compares against committed inputs. **Reproduces r100/r101/r103 byte-for-byte**
  (142/181/156 files; the only difference is gc-lit-cut0.json, which gc_lit_dump.py makes, not the disc); a second
  extraction of r106/r104 matched the first. All 25 remaining rooms extract (scenario SMD/SMX are _004/_005 in
  every room; all COLOR groups, no NORMAL groups, so no gc-lit file is needed). ~10 s for all rooms.
- `tools/ps2_room_r4im.py`: unchanged rules; new `--vc-scale` (default 1.0: packages unchanged, r103 still
  reproduces 55efd327.../7ab3747c...), a review lift for the colour question below.
- `tools/ps2_room_sheet.py` (Windows Python): look sheet. Left the package as the runtime holds it (R4IM level 0,
  R4PW placements, packed textures, ARGB1555 prelit), middle the PS2 source (OBJ + TPL, authored colours, GS
  modulate), right an optional reference frame (`--ref label;x,y,z;yaw;png`). Views: a plan, door spawns
  (aev_doors.json), route-graph points (RTP). Numpy rasteriser, no fog; not a Flycast frame.
- `tools/ps2_colour_study.py`: per room / SMX field statistics of the authored vertex colours.
- GC reference frames: the original-tryit Dolphin rig (AR codes + .dtm) with a new code `ow-r106-start`
  (room 0x120 -> 0x106); ~35 s per run; Dolphin.ini restored after (DumpFrames False, speed 1.0).

## Settled lighting decision (user, 2026-10-01)

Verbatim: "PS2 assets seem to have accounted for things that would make things faster such as lighting. We should be
ok with leveraging their approach but enhanced for Dreamcast even if that means Dreamcast looks better than GameCube
because of its texture and lighting techniques. Use your best judgment but don't reinvent patterns." Also: "Yes you
can download PCSX2 if it's needed."

This supersedes "GC lights on PS2 geometry" (option 2) as the goal; option 2's code (`--color-light gc`) stays as a
component. Coordinator's reading: runtime = the PS2 pattern (scenery fully prelit in vertex colours, no runtime
scenery light, PVR Gouraud modulate as the PS2 world path already does, characters unchanged); the GameCube is the
floor, not the ceiling (each room at least as bright, warm and shaped as the Dolphin frames); the bake extends
`ps2_room_r4im.py --color-light` only; DC enhancements from existing patterns only (VQ / texture pipeline, PVR fog
table).

## The missing term: the room's TEV colour scale (2026-10-01, answer to "the colour question")

- **What it is.** Every GC LIT cut carries `tev_scale[2]` at cLightEnv 0x40; `cLightMgr::setEnv` copies it to
  `gxCsScale[]` (light.cpp), and ShaderSetup (trans.cpp) puts `gxCsScale[m->TevScaleGroup]` on the TEV colour
  stage: GX_CS_SCALE_1 / _2 / _4 = 0 / 1 / 2. Scenery is TevScaleGroup 0. So the GameCube multiplies every scenery
  pixel by 1, 2 or 4 per room, after the texture x vertex/lit colour, before fog. Neither the converter nor
  ow_extract's `lit()` model had it.
- **Per room (cut 0; every cut of r100/r101/r103/r106 agrees):** x1 r101 r103; x2 r100 r104 r105 r107 r102 r10c
  r10e r117 r112 r111 r11d r11e r10f r10d; x4 r106 r108 r109 r10a r10b r11b r11a r119 r118 r113 r11c r11f. The PS2
  colour medians follow it: x1 rooms 0.40 / 0.60, x2 rooms 0.08-0.41 (r100 1.99 is the exception, below), x4 rooms
  0.00-0.24 (r106 0.05). The PS2 colours are authored before the scale.
- **Proof (Dolphin A/B at the r106 debug start, AR code `00314E94 000000vv` forcing gxCsScale[0] = 0x80314E94,
  store gc-ref/r106-tevscale-ab):** scenery-masked luma of the real GC frame (dump 1100; 1700 / 2600 agree within 2)
  x4 (the room's own) 47.3, x2 33.6, x1 26.8. Exactly linear: scenery term 6.8 per x1 + 20.0 of fog; so the TEV
  scale is the whole r106 gap and the light model is otherwise right.
- **Light selection was not the cause.** Lights 1 and 7 (I 1.40 sun) have xF 0x43 / 0x08; setModel2 selects a light
  when `xF & EnableMask`, and the masks are 1 player, 2 enemy, 4 obj, 8 effect, 0x10 scroll (scenery), 0x40 subchar
  (db_light.cpp names them), so 0x43 lights characters and 0x08 effects only. The xD 6 spots are out for the same
  reason. Adding them would have double-lit the scenery.
- **The PS2 data is not broken.** Raw BIN decode (the JADERLINK layout, scratch binstat) of r106 / r109 / r113: same
  VIF headers as r101 (2070 / 2382 / 1995 colour segments, no NORMAL), alpha 0x80, bin flags 0xA0/0xE0 as
  everywhere; RGB raw medians 15 / 2 / 0 of 128 (r106 25 % of corners exactly 0). They are authored dark, for x4.
- **r101's x3.1 ground gap is a different thing:** r101 is x1 in all 20 cuts, so this term does not touch it (and
  the r101 PS2 package is already at or above the GC brightness, D367_PLAY_BUILD_CHECKLIST step 3).
- **No PS2 frame was needed:** PCSX2 was not downloaded (the GC A/B explains the gap).
- **r100's hedge.** r100 is x2, and its colours are already near the GS limit (median 1.99, 77 % above 1.0), with
  SMX ColorRGB 85,84,83 / 70,70,70 on 43 % of the faces. The GX rule (vertex colour clamped to 1, times the SMX
  colour as the material register, times the TEV scale) turns the hedge and the white-silver birch trunks into the
  GC's darker browns and dark trunks; the GS rule (clamp at 2.0) keeps the silver trunks. GX clamp is the default.

## The bake: `--color-light ps2` (the PS2 pattern, prelit)

`rgb = min(vertex colour, --vc-clamp 1.0) x SMX colour x TEV scale` for COLOR groups (NORMAL groups: the existing GC
light x TEV scale); the TEV scale comes from the room's LIT cut json (`gc_room_lit.py`, now with `tev_scale`) or
`--tev-scale`. No lights are added (the PS2 colours carry the room's light). Light above 1.0 is carried by the
existing per-texture gain (texture x g, vertex / g; gain_feasibility rule); `corners_clipped` in ps2-world.json
counts corners whose light the texture headroom cannot carry (they clamp, as the GX TEV clamps). Runtime unchanged:
0 ms of light, PVR modulate, the room's fog table.

## Numbers: PS2 pattern bake (2026-10-01; tree lane/ps2rooms 2e40bd4d; store ps2rooms-20260930)

Packages (same converter defaults otherwise; heap-4 block = re4mesh + r4pw + 5,136 B LUT/gather as before):

| package | meshes / placements (instanced) | level-0 tris | re4mesh / r4pw B | heap-4 block | tex / VRAM | corners clipped | sha (mesh / pw) |
|---|---|---:|---|---:|---|---:|---|
| r106 authored (default) | 100 / 156 (56) | 41,802 | 1,022,304 / 10,768 | 1,038,208 | 42 / 837,120 | - | 08bc3536 / fee1e87b |
| **r106 ps2 (x4)** | 100 / 156 (56) | 41,802 | 1,038,496 / 10,768 | 1,054,400 | 42 / 837,120 | 6,951 of 189,804 | 23d20157 / 5e87bf59 |
| r100 landed | 177 / 283 (106) | 68,261 | 1,621,664 / 19,484 | 1,646,284 | 55 / 698,880 | 132,962 | 51daa99d / bea1ade4 |
| **r100 ps2 (x2, GX clamp)** | 179 / 283 (104) | 68,405 | 1,619,168 / 19,532 | 1,643,836 | 55 / 698,880 | 34,619 | aba13e2d / 4a64dd02 |
| r100 ps2, GS clamp (review) | 179 / 283 (104) | 68,405 | 1,625,728 / 19,532 | 1,650,396 | 55 / 698,880 | 91,074 | 06505fa2 / a5ec14f5 |

- Instancing: r106 keeps all 56 instanced groups (the bake is per BIN vertex, so shared placements share it). r100
  loses 2 of 106: 7 placements of BINs 14 / 108 carry a different SMX colour than their first instance (rgb
  differs by 0.118 = 30/255: a visible material difference on the GC too), so they get 2 meshes of their own
  (+144 level-0 triangles, +0.2 %). Not quantised: the difference is visible.
- Runtime light cost 0 ms (prelit, as before). The geometry, parts and passes of r106 are identical to the authored
  package (only colour bytes and texture gains change), so its draw cost is the authored package's by construction;
  r106 is not reachable in-game yet (route lane), so no hwproject run of it.
- Defaults unchanged: r103 55efd327 / 7ab3747c, r100 51daa99d / bea1ade4, r106 08bc3536.

Look sheets (ps2_room_sheet.py with `--fog`: the DC runtime fog of the room's cut 0, FOG_FAR 25 m; reference rows
are approximate cameras, not camera-matched; scenery-masked luma; Dolphin frames have the GC fog to the LIT far):

r106 (`sheets/r106-ps2-sheet.png`, GC = Dolphin r106a dump 1100):

| view | DC authored | PS2 source | **DC ps2 bake (x4)** | GC (Dolphin) |
|---|---:|---:|---:|---:|
| camera A (yaw 300) | 13.4 | 13.8 | **46.7** (rgb 50/46/40) | 47.3 (51/47/40) |
| camera B (yaw 345) | 16.0 | 16.1 | **47.0** (52/46/39) | 47.3 |
| camera C | 13.0 | 13.3 | **42.9** (47/42/36) | 47.3 |
| spawn from r103 door | 28.4 | 28.4 | 63.6 | - |
| route point 6 (trees, tunnel) | 21.2 | 21.2 | 52.6 | - |

r100 hedge (`sheets/r100-hedge-sheet.png`, GC = Dolphin r100a dump 4000, Leon at the warp r100-post-radio spot
(-99685, -484, -1343), ang 2.246; the GC camera sits closer and lower than the sheet's):

| view | before (landed) | PS2 source | **after (x2, GX clamp)** | GS clamp variant | GC (Dolphin) |
|---|---:|---:|---:|---:|---:|
| post-radio spot | 93.0 (100/92/79) | 100.9 | **90.1** (97/89/78) | 95.7 | 66.0 (71/65/55) |
| yaw -30 | 84.9 | 100.1 | **81.6** | 87.3 | - |
| yaw +30 | 78.4 | 96.0 | **75.2** | 80.6 | - |

The r100 "after" keeps the brightness (the DC 25 m fog's pale colour lifts every DC column against the GC's
120 m fog) and changes the material: the hedge's flat yellow and the white-silver birch trunks of the landed
package become the GC's browns and dark trunks (the SMX colour the landed package ignored). The GS clamp variant
brings the silver trunks back.

r100 in game (`sheets/r100-hedge-ingame.png` + .json; Flycast framebuffer; image = lane enc's c3 ELF 428235ce (the
r21 play recipe, PACE_MODE=off, DBG_WARP=1, PC_SAMPLER=1; arm candidate-encc3), tour fixture
rel-r100-post-radio-pw with only the r100 package swapped (fixtures by tools/d367/ps2rooms/mkfix.py; the control's
rewrite is equal to the tour fixture), harness scenarios ps2rooms-r100ctla / -r100ps2a, 150 s, same seconds; HALT 0,
MISSING 0, open failed 0, PS2MESH open in both). Scenery-masked luma (GC = Dolphin r100a dump 4000 at the post-radio
spot):

| shot | before (landed) | after (ps2 x2) | GC |
|---|---:|---:|---:|
| t0041 (woods, birches) | 38.6 | 44.8 | 56.0 |
| t0051 (the car) | 45.7 | 48.6 | |
| t0072 (path) | 54.2 | 53.3 | |
| t0082 (the hedge mound, close) | 40.4 | 53.2 | |
| t0144 (the hedge mound, close) | 38.8 | 52.0 | |

In game the landed package is the darker one at the hedge (its saturated colours, 1.99, clamp at the texture
headroom: 132,962 corners clipped vs 34,619), and the bake moves toward the GC (52-53 vs 56). Birch trunks: white
before, dark after, dark on the GC. The bake's leaf texture reads more contrasty than the GC's (texture gain to the
headroom; the GC's mips soften it).

Cost (hwproject.sh, same image and window: enc c3, r100 post-radio, frames 900:1380, trace stride 16, 31 traced
frames; evidence C:\Flycast-Evidence\re4-dreamcast\hwmodel-ps2rooms-prad-{ctl,ps2}):

| arm | frame hw ms [low..high] | scenery | render-side | Flycast |
|---|---|---:|---:|---:|
| control (landed r100 package) | 61.9 [54.9..72.0] | 15.6 | 24.1 | 43.7 |
| **ps2 bake x2** | **61.8 [54.8..71.7]** | **15.5** | 24.1 | 43.6 |

So the bake is cost-neutral (-0.1 ms, within noise; lane enc's own control of this view: 61.9 / 15.64). Heap 4:
-2,448 B.

## State and next step (2026-10-01)

- r106 and r100 re-converted with `--color-light ps2`; sheets below. r100 is landed: the re-convert is for the
  user's look decision only, not ready to land.
- Next: the remaining stage-1 rooms with `--color-light ps2` (their gc-lit-cut0.json with tev_scale are in the
  store's inputs), each with a sheet and a Dolphin frame (`dab.ps1` + an `ow-<room>-start` code), in route order.
- DC enhancements, from existing patterns only: the PVR fog table is already the runtime's (the sheets draw it);
  opaque textures are already VQ (converter rule: VQ when smaller than native16). Higher-resolution textures
  (e.g. the GC TPLs through the existing texture pipeline) are a separate look + VRAM question, not started.
- Watch: r113 (x4, raw median 0 of 128, 50 % black corners) and r109 (median 2) will stay dark even at x4: their
  sheets need a Dolphin frame before any judgement.

## State (2026-09-30, history)

- r106: extracted, converted, numbers, look sheet with a GC reference. **Not reachable in-game** (no warp preset;
  `assets.sh discover r106`: room container st1/r106 not prepared, em29/em2e not built (value-init lint), event
  r106s00 has no route movie / prepared evd), so the offline sheet is the check.
- **Blocker for all later rooms: the colour question.** r106's COLOR vertex colours are not the final light (below).
  The package reproduces the PS2 data faithfully and is ~4x darker than the GameCube. Needs a user decision
  (options below) before more rooms are worth sheeting; extraction for every room is done and stored.
- Next: convert the remaining rooms (mechanical, ~10 s each) once the lighting option is chosen; measure r106's
  heap 4 when its room container is prepared.

## Numbers (image, build, evidence)

r106 package `ps2rooms-20260930\out\r106` (ps2_room_r4im.py defaults, lane tree f338e3b7 + --vc-scale option):

| item | r106 | r103 (landed) | r101 (landed) | r100 (landed) |
|---|---:|---:|---:|---:|
| source triangles | 63,268 (OP 50,338 / TR 12,930) | 42,627 | 51,237 | 92,754 |
| groups / meshes / placements | 156 / 100 / 156 (56 instanced, 18,272 tris) | 134 / 134 / 134 | 209 / 190 / 209 | 283 / 177 / 283 |
| level-0 triangles stored / drawn via placements | 41,802 / 60,025 | 41,507 | 47,770 | 68,261 |
| re4mesh + r4pw bytes | 1,022,304 + 10,768 | 1,125,888 + 11,272 | 1,245,344 + 16,068 | 1,621,664 + 19,484 |
| heap-4 block at open (+LUT 2 KiB, gather 3 KiB) | 1,038,208 | ~1.14 MB | ~1.27 MB | ~1.65 MB |
| textures / VRAM | 42 / 837,120 B | 52 / 758,784 | 97 / 1,015,808 | 55 / 698,880 |

- Heap-4 fit (estimate; r106 cannot run yet): the landed rooms had 5.39-5.53 MB heap 4 free at the package open
  (free after open + package: r100 3.80+1.65, r101 4.12+1.27, r103 4.39+1.14 MB, D367_PLAY_BUILD_CHECKLIST step
  5). At the same level r106 leaves ~4.35 MB after its open. Enemy archives (assets.sh discover r106): worst case
  1,524,352 B (em12 1,105,152 + em2a 276,064 + em29 99,040 + em2e 44,096) -> ~2.8 MB spare. With the source's
  em12 request floor 0x3C0000 (3,932,160, gap audit) the four requests are 4,351,360 B -> no margin under the
  80 KiB reserve. Measure with `assets.sh discover r106 --log` at the first r106 run.
- VRAM 837,120 B is below r101's 1,015,808 B, which the play build holds.
- Conversion fidelity: package vs PS2 source mean |diff| 0.4-1.4 luma per view (sheets/r106-sheet.json).
- Look: `ps2rooms-20260930\sheets\r106-sheet.png`. At the GC debug start (r103 door dst, 11141,-893,-120) the
  package view mean is 12.1 vs the GameCube frame 48.4 (Dolphin run r106a, dump 1100, band incl. Leon + HUD).

## The colour question (r100 hedge + r106 dark)

Answered 2026-10-01: the room's TEV colour scale (section "The missing term" above). History follows.

`ps2_colour_study.py` over 28 rooms (`study/colour-study.json`), median COLOR vertex colour (1.0 = GS 0x80 =
texel unchanged): r100 1.99, r103 0.60, r101 0.40, r104 0.41, r107 0.37, r10c 0.39, r11d 0.25, r11b 0.24, r105
0.23, r10f 0.23, r102 0.22, r10d 0.20, r112 0.20, r11f/r117/r10e 0.16, r10a 0.15, r11a/r11e 0.12, r10b 0.11,
r108 0.10, r118/r119 0.09, r111 0.08, r106/r11c 0.05, r109 0.01, r113 0.00.
- COLOR BINs store the colour in the vertex normal slot (JADERLINK PS2BIN_To_GenericModel), so these groups have
  no normals. SMX LightSwitch (32 bits, JADERLINK RE4-SMX-TOOL: 1 = light enabled) is 0xffffffff in most groups of
  r100/r101 and partly cleared in r106 (e.g. 0xffff7011); it does not by itself explain the gap (r101 has all
  lights enabled and matches the GC with vertex colours alone).
- The r106 GC frame is ~4x brighter than the authored PS2 colours. Either the PS2 adds light at runtime to COLOR
  groups in dark-coloured rooms, or it has a post/brightness stage the data does not show. No PS2 frame exists to
  decide (no PCSX2 on this machine).
- A uniform x4 lift (`--vc-scale 4`, out/r106-vc4, sheets/r106-vc4-sheet.png) reaches the GC mean (47.3 vs 48.4)
  but reads grey and flat next to the GC's warm browns: not a fix by itself.

Options for the user (looks are the user's call):
1. PS2 reference first: install PCSX2 (a download; needs the user's OK) and capture r106 + r100 on the PS2 disc,
   then model the PS2 light exactly (settles r100's hedge too).
2. GC light on PS2 geometry: vertex normals from the PS2 mesh, lit with the GC LIT cut-0 lights as the converter
   already does for NORMAL groups (the GC is the stated reference: "work backwards from the original world").
   Offline only, no runtime change; price the look with the Dolphin frames.
3. Per-room lift fitted to Dolphin frames (cheapest, least faithful).

## Ready to land

Nothing for the runtime (no runtime change, no knob). The tools on lane/ps2rooms can land any time:
- ps2_room_extract.py, ps2_room_sheet.py (`--fog` new), ps2_colour_study.py, gc_room_lit.py (tev_scale etc.);
- ps2_room_r4im.py with --vc-scale / --color-light authored|gc|ps2 / --gc-cut / --gc-lit / --tev-scale /
  --vc-clamp. Defaults give identical packages (checked 2026-10-01: r103 55efd327 / 7ab3747c, r100 51daa99d /
  bea1ade4, r106 08bc3536);
- tools/d367/ps2rooms/pr-hw.sh, pr-look.sh, mkfix.py (cost / look runs with a swapped package).

Not ready (user decisions): the r100 re-convert (`out/r100-ps2`, look sheets above; staging it = replacing the r100
package files in the play fixtures and the play recipe's staging); r106 `out/r106-ps2` waits for the route lane's r106
container (it is the package to stage then).

Decisions for the user:
1. Adopt the PS2-pattern bake (`--color-light ps2`: PS2 colours x SMX colour x the room's TEV scale) for every
   PS2 room? (r106 needs it: authored is 3.5x too dark.)
2. r100: replace the landed package with the bake (darker birches and browns like the GC, the hedge 52-53 vs GC 56
   instead of 39-40; cost-neutral)? Option: GS clamp variant (keeps the silver birches).
3. r101 / r103 (x1): the same bake changes them only by the SMX colour (r101 215 / 235 on ~20 % of faces, r103 some
   75,72,70): leave them as landed unless the user wants consistency (would need a sheet first).

## Option 2 (user 2026-09-30): GC lights on PS2 geometry, r106 result (2026-10-01)

Implementation (offline, no runtime change):
- `ps2_room_r4im.py --color-light gc [--gc-cut N]`. COLOR groups get the GameCube self-lit channel:
  `clamp01(vertex colour + the lights the model selects) x SMX colour`.
  - Normals come from the PS2 triangles: area-weighted, smoothed per OBJ vertex. Their orientation was checked
    against the authored normals of the r101 and r100 NORMAL groups: 98.5 % / 99.5 % of corners agree, median
    dot 0.89 / 0.97.
  - Light selection follows ow_extract.py `select()` (the light_house38.py rules), with the PS2 SMX LightSwitch as
    the mask and the group's world box as the light box. GX parameters come from `gx_light`.
  - The default `authored` is unchanged: the r103 package still reproduces 55efd327 / 7ab3747c, and the r106
    default package is unchanged (08bc3536).
- `gc_room_lit.py` dumps any room's LIT cut from the GC ISO. It matches gc_lit_dump.py exactly for r100/r101.
  r106 has 8 cuts; `inputs/r106/gc-lit-cut0..7.json` are in the store.
- `ps2_room_sheet.py` takes a second package column (`--pkg2`) and explicit `cam` reference views. It also writes
  scenery-masked luma/RGB per column (Leon and the HUD boxes are left out on reference rows).

Result. Look sheet `ps2rooms-20260930\sheets\r106-gclit-sheet.png` (+ .json). Columns: DC authored | PS2 source |
DC GC-lit (cut 1) | GC Dolphin r106a dump 1100. The three reference rows are approximate cameras at the r103-door
spawn, not camera-matched. Scenery-masked luma:

| view | DC authored | PS2 source | DC GC-lit | GC (Dolphin) |
|---|---:|---:|---:|---:|
| camera A (yaw 300) | 10.1 | 10.4 | 16.4 | 47.2 |
| camera B (yaw 345) | 11.2 | 11.2 | 16.6 | 47.2 |
| camera C | 9.5 | 9.8 | 16.2 | 47.2 |
| spawn from r103 door | 22.9 | 23.0 | 26.2 | - |

- The bake lifts r106 by only ~1.6x. The GameCube is ~4.5x brighter than authored.
- Corner brightness (median of the max channel) goes from 0.094 authored to 0.117 (cut 0) and 0.127 (cut 1).
- Why it falls short: in every r106 LIT cut, the only lights that reach scenery (xF bit 0x10) are light 0 (a
  parallel sun, col 88, I 0.24-0.44) and the spot light 3.
  - Lights 1 and 7 (I 1.40, a global sun) have xF 0x43 / 0x08, so they don't select scenery.
  - The xD 6 spot lights near the house (x 126-156 m) are a kind gx_light does not model.
  - So under the repo's GC light model, the GC itself would draw r106 about as dark as the PS2 data does. The
    Dolphin frame contradicts this.
  - It is the same gap the original-tryit Dolphin study found for r101's ground: the GC is x3.1 over the
    unit-normal model at V1E, with the cause untested.
- Instancing drops from 56 to 15 groups, because baked light differs per placement. The package grows to 141
  meshes, level 0 56,482, re4mesh 1,477,024 B (+44 %; heap-4 block ~1.49 MB, still under r100's 1.65 MB).
- GC CLR0 does not supply the missing light. In r106 only 28 of 87 GC BINs are self-lit (CLR0 median 0.10); the
  rest are GX-lit with an unused CLR0.
- An automatic camera fit to the Dolphin frame (gradient + luma correlation over route points and yaws) locked
  onto dark interiors. The darkness defeats it, so the reference rows use hand-picked approximate cameras.

r100 hedge (report only; r100 is landed). The same rules fix the over-bright colours. r100's saturated groups
carry SMX ColorRGB 85,84,83 or 70,70,70, which the authored packages ignore; the GC multiplies it in as the
material colour, and GX clamps the channel to 1.0. Under `--color-light gc`, r100's COLOR corners go from median
1.99 (77 % above 1.0) to 0.47 (none above 1.0). r101 moves only 0.45 -> 0.55. So the SMX colour multiplier,
which the converter drops today, is the likely answer for r100. Changing it is the user's call.

Next, for a decision:
1. Find the missing GC brightness term with Dolphin A/B frames: AR codes that disable scenery lights or change
   the ambient / material registers at the r106 start. This is the same unknown as r101's ground. Then fold it
   into `--color-light gc`.
2. Stopgap: a per-room gain on top of the GC bake, fitted to Dolphin frames.
