# HW_FOG_HAZE: the distant camera haze as PVR table fog (issue #29)

Lane hwfog, 2026-10-14. Knob `HW_FOG_HAZE=1` (game/hwfog.mk, default 0). Code: game/hwfog.cpp (rows, veil table),
platform/native_static.cpp (re4dc_fog_frame folds the veil into the GXSetFog table), and the per-sprite hook
`re4dc_hwfog_haze()` in src/game/esp_sub.cpp, which the effects lane carries (lane/t11-fx 2a8c8e45, lane/t11 ae6cc5be).
hwfog.mk refuses `HW_FOG_HAZE=1` on a tree without the hook.

## Problem

Outdoor frame dips (#29) come from translucent fill: the console measured ~53 ms/frame of GPU outdoors against ~14
indoors (r22g, 2026-10-05), and that fill is mostly full-screen mist sprites. The room generator's camera haze (Esp15,
owner 0xd0) keeps its particles in a box in front of the camera. Near the camera they are the visible, drifting
mist. Deep in the box they only lay an even veil, but each one still costs a full translucent fill.

## What the fog can and cannot carry (audit)

- NATIVE_FOG=1 (test 10) already loads the room's GXSetFog curve into the PVR fog table. The fog is enabled on the
  world, actors and effect sprites. EFFECT_HAZE_LEAN=3 (M1 + M3) already moves part of the r100 / r101 / r103 haze
  into that table. Those three rooms keep M3 and get no hwfog row.
- PS2: the GS dumps of every target room show no GS fog (PRIM.FGE=0, no FOGCOL writes). PS2 haze is sprites only, so
  this is a Dreamcast-specific substitution. The PS2 sprite recipe stays the reference for how the haze looks.
- The PVR has one table-fog colour, and that colour is also the background. Moving it toward the haze colour
  brightened all fogged distance and the sky: r11b gained +27/255, against +1/255 from the sprites it replaced. That
  mechanism was dropped. The fog colour stays the room's own, so rooms with a night fog colour (r11b 262727, r119
  191c1d) cannot carry a bright veil. Their far haze is cut, with no veil in its place.

## Design

- `re4dc_hwfog_haze(room, depth, indoor)` runs per haze sprite. In a room with a row, a sprite deeper than the keep
  depth is skipped (returns 1). The keep depth is 3.0 m, which is where the PS2 recipe's near fade reaches full alpha.
  The function also notes the row, the indoor step (8 steps) and the FX_LEVEL.
- The fog table: the veil in front of a surface at depth z is the replaced sprites' alpha (near fade 0.5 to 3 m, far
  fade over the last 30 % of the 5 m box) integrated from the keep depth to z. It is scaled by the row's veil and
  the indoor fade, then combined as 1-(1-fog)(1-veil), capped at 0.95.
- The table is rewritten only when the row, the indoor step or the level changes. Each rewrite goes through
  re4dc_fog_frame_pending, which fences the TA double buffer. A note is valid for 60 frames.
- FX_LEVEL 0 / 1 / 2 moves the keep depth to 3.0 / 2.5 / 2.0 m. The veil keeps the level-0 density of the replaced
  layers (the fog costs no fill, so there is no reason to thin it first). The level is part of the table key.
- Render only: generators, Rnd() draws, the effect pool and sprite motion are unchanged.

## Rows

| room | fog colour | keep | box | veil | how the veil was set |
|---|---|---|---|---|---|
| r106 | 6e6a59 | 3 m | 5 m | 0.09 | frozen stills: sprites added 0.92x a 0.10 veil's brightness |
| r107 | 5f6059 | 3 m | 5 m | 0.02 | far sprites added 0.0-0.2/255 (ratio <= 0.12 of 0.10) |
| r109 | 737166 | 3 m | 5 m | 0.04 | ratio 0.43 of 0.10 |
| r119 | 191c1d | 3 m | 5 m | 0 | night colour: far haze cut |
| r11b | 262727 | 3 m | 5 m | 0 | night colour: far haze cut (far sprites added <= 2.2/255) |

Calibration method: frozen stills at the same tick and camera in three arms (all haze, far haze skipped with no veil,
skipped + veil). The far sprites added only 0.0-2.2/255 of mean brightness in every room.

## Results (2026-10-14)

TA-stats Flycast (flycast6, lane ms counters). TR = translucent screens of fill per frame. GPU ms is MODELLED with the
lane ms console fit (3.83 x TR - 6.5), not measured on a console. Arms: A = test 10; B = A + the test 11 PS2 effect
recipes (PS2_FX_ROOMS, STAGE1, POPULATION, ADDITIONS, ROOMS_EXT); C = B + HW_FOG_HAZE=1. Values are mean (p90)
over each view's run window.

| view | TR A | TR B | TR C | GPU A | GPU B | GPU C |
|---|---|---|---|---|---|---|
| r107 a180 | 19.5 | 5.87 | 4.23 | 68 (76) | 16.0 (20.4) | 9.7 (13.3) |
| r107 a0 | - | - | - | 67 | 13.9 (19.1) | 7.7 (12.3) |
| r109 a0 | 22.0 | 9.64 | 6.43 | 78 (85) | 30.4 (32.8) | 18.1 (18.8) |
| r109 a270 | - | - | - | 71.5 | 14.9 | 12.1 |
| r11b a0 | 12.4 | 9.12 | 7.95 | 41 (49) | 28.4 (30.9) | 23.9 (26.0) |
| r106 rails a270 | - | - | - | 13.1 | 19.3 (22.7) | 9.9 (10.1) |
| r106 a180 | - | - | - | 16.2 | 12.0 | 3.4 |
| r119 a90 | - | - | - | 9.7 (22) | 11.5 (21.8) | 11.0 (21.0) |
| r100 fight | - | - | - | 16.8 (32.6) | 17.6 (36.3) | 17.5 (36.5) |

- r100 / r101 / r103 / r10b lake / r118: TR 1.5-4.4. They are not GPU-bound and have no row.
- What remains in r109 C (~5.4 screens) is world translucent polygons, not haze.
- The r119 peaks come from far effect sprites (16 sprites, not Esp15 haze). The r100 fight peaks come from shot and
  hit effects 0.2-0.8 m from the camera, plus M3 haze at ~2 m. Both are outside this knob.
- Most of the saving comes from the test 11 recipes (A to B). HW fog adds 4-12 ms of modelled GPU saving in r106 /
  r107 / r109 / r11b on top of them.
- The C arm in the table is the calibration build (veil 0.10 / old ramp). The skipped-sprite set, and so the fill,
  is the same as the final rows, because the veil does not change fill.

CPU (SH-4 hardware model, hwproject, frames 3800:3919 stride 8, MODELLED): total minus the pacing spin
(re4dc_pace_end + re4dc_vi_retrace_count):

| view | A | B | C |
|---|---|---|---|
| r107 a180 | 44.8 | 43.5 | 43.5 |
| r109 a0 | 30.7 | 28.3 | 28.0 |

- The first C build's model totals (93.9 / 64.7 ms) were an icache-layout artefact in the pacing wait loop. In that
  link, re4dc_vi_retrace_count (icache set 138) sat inside re4dc_pace_end's sets 97-174, so the spin loop missed on
  every pass. The final link does not alias (184 against 187-8).
- The instruction counts and every other area matched B. That loop only waits for vblank, so this cost is not work.
- The r11b C trace was partial (4.5 M insns/frame against 11.5 M), so r11b CPU is not quoted.

## Gates

- Knob-off identity: hfkP2 (lane/hwfog, test 10 recipe) vs out-t10stP. Image 412198a093f8626b, every overlay and the
  syms are identical (PASS).
- Logic, knob on vs off (trace builds on the same base, the image padded to the same end, the same stop tick):
  - H2 (r100 to tick 4700): STRICT, decisions MUST-IDENTICAL, s30 340/340 in both runs, 0 overruns.
  - r107 (r104 door to r107, tick 3000, with 11,991 haze sprites replaced): STRICT, MUST-IDENTICAL.
- Stills sheet (3 haze rooms, entry views, test 10 | test 11 effects | HW fog | HW fog + modelled console vertical
  filter | PS2): C:\Flycast-Evidence\re4-dreamcast\hwfog-20261014\hwfog-sheet.png.
