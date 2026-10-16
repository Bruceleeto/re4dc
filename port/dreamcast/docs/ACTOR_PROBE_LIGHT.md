# Character lighting phase 2: per-actor light probe (ACTOR_PROBE_LIGHT)

Lane lp2, 2026-10-14. Branch `lane/light-p2` (local), commits `7ac3635b` (probe) and `ad45bdd1` (shared record).
Then `d44c3059` (LEON_LIGHT_HEADROOM + LEON_LIGHT_TOGGLE). Option branch `lane/light-p2-extra` (`a6496bef`, unmerged): `ACTOR_PROBE_LIGHT_EXTRA`. All knobs default 0.
Evidence: `C:\Flycast-Evidence\re4-dreamcast\lp2-20261014` (cost projections `hwmodel-*`, `cost-table.json`, gates under
`gates\`, stills sheet `lighting-sheet.png`).

## What it does

`ACTOR_PROBE_LIGHT=1` (Leon) / `=2` (Leon and the Ganado classes 0x10..0x20). Each actor gets one light probe per frame.
The probe is ambient light plus one directional light. Each vertex then needs one dot product's worth of lighting.

- **Source.** The probe is evaluated from the actor's GameCube light set, once, at the actor's origin. This is the set
  that the game's own `LightSetModel` selected: room `.lit` lights, plus dynamic lights such as the muzzle flash, fires
  and effect lights. These are the same records that `LEON_SOURCE_LIGHT` and `PS2_GANADO_LIT` capture.
- **Fit.** The probe is the L0 + L1 fit of the clamped-cosine sum.
  - Light vector: V = Σ luma(C_i) · l_i.
  - Coherence: a = |V| / Σ luma(C_i).
  - Directional term: a · ΣC_i, along V/|V|.
  - Ambient term: 0.25 · (1 − a) · ΣC_i, added to the GX ambient.
  - A single light reproduces `build_lights` exactly (host test).
- **Parts.** Each part lights with that direction, expressed in the part's own normal space.
  - Leon uses the per-part (modelview 3×3)^-T, as D36 does.
  - Ganados use the record's shared normal matrix.
  - All parts go through the existing fast kernel, never the exact per-vertex evaluator.
  - Every palette entry's direction is built in one pass per fold (`probe_dirs_all`). Before this, the kernels' record
    walks built them per palette (`avk_build_dirs_n16` + `skin_light_dirs`), which cost 0.83 ms for Leon in the house.
- **Distance tiers (=2).** The near tier is lit per vertex. Mid and far tiers get one colour per part from the probe, as
  `CROWD_FLAT` does today.
- **Requirements.** `LEON_SOURCE_LIGHT=1`, for Leon's light-set capture. `=2` also needs `PS2_GANADO_LIT=1` and
  `CROWD_LOD=1`. Make enforces both.
- **Fallback.** A part the probe cannot serve (about 11% of parts in the `PROBE_LIGHT` log, likely the material caps
  check or Leon's basis case; not investigated) keeps the existing `build_lights` path. That path is the D36 / Ganado
  light of today, not a GameCube model fallback.
- **Code.** About 210 lines of C++ in `platform/native_actor_fast.cpp`, the 42-line header, 28 lines of `crowd.mk` and the host test
  `tests/test_actor_probe_light.py`. No new assembly and no linker change: it reuses the existing
  `re4dc_avk_light_*` kernels with one direction.

### Why not D36 or an offline probe grid (the simpler alternatives)

- **D36 (`LEON_SOURCE_LIGHT=1`) alone** is the simplest code that is already there. Measured on the model, it is not
  safe. When Leon stands under more than 3 lights (r100 house, 690:749), every Leon vertex takes the exact per-vertex
  evaluator (`pass_lights_exact` + `world_of`), which costs +21.9 ms per frame. The probe removes that path for Leon.
- **No offline per-room probe grid.** The user's proposal baked probes from the GC room light sets. That is not
  needed:
  - The game already runs `LightSetModel` for every model every frame, as part of the source frame.
  - Sampling that set once per actor costs about 0.05 ms per frame for Leon (`probe_lights` + `probe_of`, modelled,
    r100 house).
  - A baked grid would save almost nothing. It would also lose the dynamic lights and add a converter, disc data and
    heap.
- **A one-direction kernel** (new SH-4 asm) would save about 0.4 ms for Leon (estimate from the instruction share of
  the unused directions, not modelled). It was not done. The probe is already within about 1.4 ms of flat, and the
  saving does not justify a new kernel (CLAUDE.md rule).

## Shared light record (lp2 owns the format)

`platform/include/actor_light_probe.h` exports `re4dc_actor_light_probe(model, out)`. It returns the newest probe for
that model (this frame's, else the previous frame's):

- `dir`: view space, unit vector from the actor toward the dominant light. A shadow falls along −dir. All zero means
  no direction.
- `color`: directional colour, GX units / 255.
- `ambient`: GX ambient / 255 + the folded residual.
- `coherence`: 0..1. 1 means one clear light; 0 means light from all sides.
- `serial`: the actor-frame serial the record was built in.
- Reserved extension terms, zero today:
  - `extra_n` and `extra_index` (the option below).
  - `flash` (a global flash or tint term).

Fields are only appended, never reordered.

The shadow lane (PVR modifier volumes, lane/shadow `614c0552`, `mv_shadow.cpp`) reads this record for Leon and the
live Ganados 0x10..0x20:

- World shadow direction = −(Vᵀ · dir), with V = `pG->Cam.v_mat`.
- Footprint stretch = 1700 mm body height × slope × coherence, capped at 1800 mm.
- No probe, or an all-zero dir, gives a round footprint straight down.
- It reads the record in `stream_close` after the owner draws, so it gets this frame's record.

So light and shadow agree, and there is one light table. With `ACTOR_PROBE_LIGHT=1`, Ganados have no probe, so their
shadows are round.

The record exists only in builds with `ACTOR_PROBE_LIGHT=1` or `=2`. Those builds define
`RE4DC_ACTOR_LIGHT_PROBE_API=1`, and callers must guard on it, because unresolved symbols link to silent stubs.

## Extension contract (so later light or shadow options need no rework)

- **Characters.** The light path is "probe + 0..N extra lights", with N = 0 by default. `ACTOR_PROBE_LIGHT_EXTRA=N`
  (option branch `a6496bef`) works as follows:
  - The N strongest lights at the origin are left out of the probe and evaluated per part.
  - They go into the fast kernel's otherwise-zero directions 1 and 2.
  - The per-vertex cost is unchanged.
  - `EXTRA=0` builds are byte-identical to the probe builds (identity PASS lp2Z1C vs lp2R1C, lp2Z2C vs lp2R2C).
- **Flash.** A future flash term adds to the ambient (`Re4dcLightProbe.flash`). That is 3 adds per actor per frame.
- **World.** The world keeps its baked per-vertex colour, since the PS2 world is prelit. A global flash or tint
  modulates the frame through the existing post-quad path: Filter00 / `POST_F00`, or the `LOOK_TOGGLE` grade quad.
  Nothing relights world vertices.
- **Shadows.** The shadow lane takes direction and strength from `dir` and `coherence`. If the meaning of either
  changes, the shadow lane must be told.

## Cost (SH-4 hardware model, MODELLED, not console)

How these were measured:

- Build: the test 10 recipe (`t10s-build.sh`) on `lane/light-p2`, plus `DBG_WARP=1 PC_SAMPLER=1 PACE_MODE=off`.
  PACE_MODE=fast arms mixed drawn and skipped frames differently per arm, so they were thrown out.
- Assets: the test 10 data fixture (`t10s-fix.py`, pkg-r91tP.json, `--pak gc --hands 1`). These are the PS2 world and
  PS2 cast packages; there are no GC model fallbacks (MCHECK_LEONGC PASS below).
- Projection: `hwproject.sh`, nominal model with the low..high what-if range, global frame windows.
- Scenes:
  - houseA: r100 house, Codex warp/pad, 690:749. Leon stands under more than 3 lights.
  - house: the same run, 740:819 (Codex's window).
  - wide: the r101 wide burning-cross warp, 1390:1469, 12 Ganados alive.
  - r10b: room start, warp `room 0x10b inv default god`, 500:579.
- Reading the table: the flat row is absolute whole-frame ms; every other cell is its delta against flat. "Lighting" is the sum of the
  lighting functions. Binaries differ in layout and I-cache, which moves the whole frame by about ±0.5..2 ms (for
  example X1 vs R1 wide: whole frame +1.96, lighting +0.21). Read the lighting column for the scheme's own cost.

| Option | r100 house, Leon >3 lights (690:749) | r100 house (740:819, Codex window) | r101 burning cross (1390:1469) | r10b start (500:579) |
|---|---|---|---|---|
| Flat (test 10) | 37.97 (33.06..44.95); lighting 0.27 | 39.15 (34.12..46.28); lighting 0.25 | 86.76 (75.91..102.66); lighting 3.17 | 39.00 (34.37..45.57); lighting 0.27 |
| D36 LEON_SOURCE_LIGHT=1 | +21.87 (+21.23..+22.68); lighting 21.47 | +5.40 (+5.12..+5.74); lighting 5.40 | +3.76 (+3.25..+4.40); lighting 4.95 | +1.13 (+1.28..+0.96); lighting 2.42 |
| D5 design 1 (CROWD_FLAT=0) | +0.75 (+0.68..+0.84); lighting 0.89 | +0.63 (+0.57..+0.70); lighting 0.88 | +2.78 (+2.49..+3.15); lighting 4.99 | - |
| D5 design 2 (GANADO_ONE_LIGHT=1) | +1.77 (+1.62..+1.97); lighting 1.80 | +1.85 (+1.66..+2.08); lighting 1.80 | +5.54 (+4.95..+6.31); lighting 7.91 | - |
| Probe ACTOR_PROBE_LIGHT=1 | +1.36 (+1.18..+1.57); lighting 1.69 | +1.30 (+1.13..+1.50); lighting 1.64 | +1.92 (+1.76..+2.16); lighting 4.46 | +1.36 (+1.25..+1.54); lighting 1.81 |
| Probe ACTOR_PROBE_LIGHT=2 | +2.02 (+1.72..+2.40); lighting 2.08 | +1.84 (+1.57..+2.18); lighting 2.02 | +3.38 (+2.89..+4.07); lighting 5.59 | +1.43 (+1.30..+1.65); lighting 1.82 |
| Probe =1 + 1 extra light (option) | - | - | +3.88 (+3.25..+4.73); lighting 4.67 | - |
| Probe =1 + 2 extra lights (option) | - | - | +4.27 (+3.51..+5.28); lighting 4.67 | - |
| Probe =2 + 1 extra light (option) | - | - | +5.09 (+4.26..+6.22); lighting 6.02 | - |
| Probe =2 + 2 extra lights (option) | - | - | +4.75 (+4.04..+5.71); lighting 6.07 | - |

What each arm lights:

| Arm | Leon | Ganados |
|---|---|---|
| Flat | flat | flat (`PS2_GANADO_LIT=1 CROWD_FLAT=1`) |
| D36 | source lights | flat |
| D5 d1, D5 d2 | flat | lit |
| Probe =1 | lit | flat |
| Probe =2 | lit | lit |

So the D5 rows are a Ganado cost only. Compare them with the Ganado increment of the probe, which is =2 minus =1:

| Ganado lighting | houseA | house | wide |
|---|---|---|---|
| D5 design 1 | +0.75 (lighting +0.62) | +0.63 (+0.63) | +2.78 (+1.82) |
| D5 design 2 | +1.77 (+1.53) | +1.85 (+1.55) | +5.54 (+4.74) |
| Probe =2 minus =1 | +0.66 (+0.39) | +0.54 (+0.38) | +1.46 (+1.13) |

Each cell is the whole-frame ms, with the lighting-function ms in brackets.

Extra lights for the dynamic option, in the worst r101 view (wide). "Leon only" means probe =1 + N; "Leon + near
enemies" means probe =2 + N:

| Wide, modelled | Whole frame vs flat | Lighting functions | Lighting delta vs the probe alone |
|---|---|---|---|
| Leon only: probe =1 | +1.92 | 4.46 | - |
| Leon only: probe =1 + 1 extra light | +3.88 | 4.67 | +0.21 |
| Leon only: probe =1 + 2 extra lights | +4.27 | 4.67 | +0.21 |
| Leon + near enemies: probe =2 | +3.38 | 5.59 | - |
| Leon + near enemies: probe =2 + 1 extra light | +5.09 | 6.02 | +0.43 |
| Leon + near enemies: probe =2 + 2 extra lights | +4.75 | 6.07 | +0.48 |

How to read the extra-light rows:

- The lighting column is the real cost of the option: +0.2 ms for Leon, about +0.45..0.7 ms with the near Ganados.
- Per function:
  - The palette directions go back to per palette: `skin_light_dirs` rises by 0.37 ms for Leon and 0.72 ms for
    Leon + Ganados.
  - `probe_extra` and `probe_of` add 0.25 ms in the Leon + Ganados case.
  - `probe_dirs_all` falls by 0.15..0.28 ms.
- Most of the larger whole-frame delta is layout and I-cache noise, not lighting. `MeshDraw::draw` (world meshlets)
  rose by 0.57 / 0.70 ms with an identical instruction count.
- So the extra lights cost about 0.2..0.7 ms of real work in the worst view, and the whole frame can still move
  1..2 ms either way when the binary changes.

## Gates (on the final code, ad45bdd1)

| Gate | Result |
|---|---|
| Knob-off identity | lp2KP vs t10stP (test 10 play image): IDENTITY PASS (objcopy image + overlays + syms). Rechecked after every change. |
| H2 STRICT, probe on | lp2GT (knob-off) vs lp2S2T (`ACTOR_PROBE_LIGHT=2 LEON_SOURCE_LIGHT=1`). Both have `_end` 8c40a29c (`IMAGE_PAD_BYTES=4288` on the off arm), `RE4DC_LOG_STOP_TICK=4700`, trace_lock, overruns 0. logic_trace_diff rc=0 (STRICT). |
| Decisions | decision_cmp MUST-IDENTICAL over 4702 ticks: em-em 133840, line queries 81607, area 3791, damage 56040. Drift 0. Info only: sq=4@285 (sound). |
| s30 | Route movie id=10030 shown 340, dropped 0, in both arms. |
| MCHECK_LEONGC + TEX_CHECK | lp2S2M (probe =2 + `MCHECK_LEONGC=1 TEX_CHECK=2`): h2, boat and square routes give LEON-GC PASS ×3 and TEXCHK PASS (3/3); halt/missing/fault 0. |
| Host test | `tests/test_actor_probe_light.py`: fit, one light = `build_lights`, cache, declines, palette directions, shared record, source data unchanged. |

The STRICT and MCHECK runs used probe =2, which covers =1 (Leon's path is the same in both). The `EXTRA` option has no
STRICT run or host test.

## Look

The stills sheet is `C:\Flycast-Evidence\re4-dreamcast\lp2-20261014\lighting-sheet.png`.

- Columns: Flat | D36 | D5 d1 | D5 d2 | Probe =1 | Probe =2 | GameCube.
- Rows: r100 house Leon; r101 square, villager + Leon; r101 wide crowd; r10b start Leon.

What it shows:

- The probe is nearly identical to D36 in the house and in r101F.
- In the wide shot the probe makes Leon backlit and darker, which is closer to GC.
- GC Leon's jacket is brighter and greener in r101F. That is a material/TEV difference shared by all DC columns.
- The freeze-tick villager pose differs slightly between arms.
- The r10b GC shot is the lake path at room start, not the dock.
- There is no PS2 column (left for the PCSX2 agent).

## Dynamic lights (study only; nothing implemented beyond the probe)

### Inventory, chapter 1 to 2-1

From GameCube code; the PS2 side is mostly inferred.

How GC handles lights:

- Lights are `cLight` in `LightMgr`. Room `.lit` cut lights come in at `light.cpp:727`, and dynamic lights through
  `create()`.
- Behaviours: flicker (type 1), sine (2), fade (6), and 0x10 for muzzle/explosion fades (×0.3 per frame).
- `setModel2` gives each model up to 8 lights, chosen by mask: Leon 1, Ganado 2, room SMD scenery 0x10.

| Source | GC | What it lights | Port today |
|---|---|---|---|
| Muzzle flash | `EstSet` 0x45/0x46/0x4B/0x36 effect light, fade type 0x10 | Characters near the gun; world SMD if its mask allows | Reaches Leon and lit Ganados through the probe/D36; not the world |
| Grenade / explosion | `objSubWep.cpp` 591/658/722, effect light + `Filter00SetAddSpread` screen glow | Characters + a full-screen additive glow | Character light through the probe; the screen glow is likely missing (GXCopyTex stub, POST_F00 has no spread colour) |
| Flash grenade | `EstSet` 0x3F, 15000 hit radius, Filter00 white-out | Screen + characters | Same as above |
| r101 pyre / burning cross | cut 0 light 12, flicker, R 5.6 m, (255,216,152), mask 0x10 | World/SMD only, not characters | PS2 world is prelit (static): no flicker |
| r100 house fire / lamp | cut 0 light 2, flicker, R 4.8 m, mask 0x57 | World and characters | Characters flicker through the probe; world static |
| Torch / dynamite Ganados | effect lights (`em10.cpp`) | Nearby characters | Through the probe when the effect has a light (effect data, not decoded) |
| Lightning | r113/r11d/r11b thunder tasks (chapter 2-2 onward), room light intensity or scenery colour | World + characters | Not in chapter 1 / 2-1 |
| Attached lights | Del Lago boat core light (`pl0f.cpp:397`), Ashley (`pl_npc.cpp:174`) | The owner's surroundings | Through the probe for the owner |

On PS2:

- The ELF keeps the whole light system: `cLightMgr`, `Light00..10_Move`, `cEsp11`, `setModel2`, `LightSetModel`,
  `Filter00SetAddSpread`.
- The PS2 world is prelit COLOR with no normals.
- So PS2 dynamic lights reach characters and objects, but not the world. The port matches that today.

### Options (look gain, ms, complexity, risk)

The ms figures are modelled where marked; the rest are estimates.

| Option | Look gain | ms | Complexity | Risk |
|---|---|---|---|---|
| A. Dynamic lights inside the probe (default, done) | Muzzle flash, fires and effect lights move Leon's (and with =2 the near Ganados') light | 0 extra: already inside the probe numbers | None | None |
| B. `ACTOR_PROBE_LIGHT_EXTRA=1/2` (option branch) | The strongest 1-2 lights keep their own direction and falloff, e.g. a muzzle flash next to a lamp | Wide, modelled: lighting +0.21 ms (Leon), +0.43..0.48 ms (Leon + Ganados) over the probe; whole frame +1.4..2.4 ms, mostly layout noise | Small C++ (per-part fold); palette directions go back to per palette (`skin_light_dirs` 0.41 ms in X1-wide) | Low; needs its own STRICT + host test before use |
| C. Character flash term (`flash` → ambient) | Grenade/explosion flash on characters | About 0 (3 adds per actor) | Small | Low |
| D. World flash/tint via post quad (POST_F00 with RGB, or LOOK_TOGGLE grade) | Explosion, flash grenade, fire pulse on the whole screen | CPU negligible; GPU one full-screen translucent layer, only on flash frames (not modelled) | Small (POST_F00 needs an RGB colour) | Low; check fill rate on flash frames outdoors |
| E. Regional world glow in the world kernel | Pyre/torch flicker on nearby world vertices | Estimate +0.3..0.5 ms house, about +1 ms outdoors, while active | Assembly change in the world kernel (t11/Codex area) | Medium-high; not recommended |
| F. Per-vertex world relight | Full GC-like world lights | Not costed: the PS2 world has no normals | Large (converter + kernel) | High; rejected |
| G. One-direction asm kernel | None (speed only) | Estimate −0.4 ms for Leon | New SH-4 asm | Medium; not justified now |

## Leon headroom (LEON_LIGHT_HEADROOM) and the lab toggle (LEON_LIGHT_TOGGLE)

Commit `d44c3059`. Both knobs default 0.

**Problem.** PVR MODULATE maps vertex colour 255 to 1.0x of the texel. A lit Leon (D36 or the probe) could therefore
only get darker than the flat Leon (white 255). The GameCube TEV multiplies Leon's lit colour by x2 in r100, x1 in r101
and x4 in r10b. The PS2 GS treats 0x80 as 1.0, which allows 2x. (Brightness study:
`C:\Game Dev\Emulators\BRIGHTNESS-GAP-20261014.md`.)

**Fix, `LEON_LIGHT_HEADROOM=1`.** It has two halves, and the knob only works when both are in place.
- **Data.** `tools/d367/charbake/cb_headroom.py` writes Leon's textures to `tex.pak` at 2x. It covers every Leon atlas
  and hair key in `charbake_variants.h`, plus the pl08 atlas: 15 packages in `tex-gcatlas.pak`.
  - The tool doubles the integer levels (RGB565 / ARGB4444 RGB; VQ codebooks). Keys, sizes and formats stay the same,
    so VRAM is unchanged.
  - Clipped texels: 2.2% in the play atlas and the pl08 atlas, 0-0.02% in the play hair.
- **Code.** Every Leon vertex colour is halved.
  - The flat record is 128: `leon_flat_light` in `coarse_actor.cpp`, used by the transaction owner and the coarse
    paths.
  - The lit records (the LEON_SOURCE_LIGHT marker) take x0.5 *after* the fast fold's caps check: `build_lights`,
    `probe_lights`, and the exact evaluator. The folds and kernels are unchanged; only the colour matrix differs.
  - Result: flat Leon looks as it did in test 10, and lit vertices can reach 2.0x of the texel.
- **The pair must ship together.**
  - A headroom binary with a normal pak draws Leon at half brightness.
  - A knob-off binary with the 2x pak draws Leon at 2x.
  - Fixture tool: `t10s-fix.py --pak gchr`.
  - The 2x pak is private: `/root/probe/lanes-20261014/lp2/hr/tex-gcatlas-hr.pak`, sha256 `1eb18ec4...`.
- **Known difference from GC.** The GX channel clamp min(light sum, 1) before the TEV scale is reproduced exactly when
  TEV is x2 or more (r100, r10b). Where TEV is x1 (r101), the lit side can go up to the light sum (about 1.2-1.3)
  instead of stopping at 1.0.

**Lab toggle, `LEON_LIGHT_TOGGLE=1`** (debug only; make requires `DBG_WARP=1 LOOK_TOGGLE=1` plus headroom and the
probe).
- The combo is hold X + D-pad right + START. The mode name shows on screen for 3 s, and each change logs
  `LEON_LIGHT_MODE`. A warp line `leonlight <n>` sets the mode at load.
- Modes:
  - 0 FLAT (test 10)
  - 1 PROBE: full scale, then halved per vertex. This gives test 10's 1.0x cap.
  - 2 PROBE + HEADROOM (the boot mode)
  - 3 FLAT WARM: one colour per part, with the hue of the room's GameCube light set (ambient + Leon's
    LightSetModel lights, live), brightest channel 128.
- The probe modes already use each room's GameCube light colours, so mode 3 gives flat Leon the per-room warm hue.
- Build for the lighting lab: `C:\Game Dev\Emulators\LIGHTING-LAB-20261014\FLYCAST-BUILD.txt`.
- Check of the toggle: modes 0 and 1 reproduce the test 10 flat and probe stills to within 1% of jacket luma
  (house 35.9 vs 35.5 and 24.1 vs 24.1; r101F 42.7 vs 42.2 and 23.8 vs 23.7).

**Gates on `d44c3059`** (evidence `...\lp2-20261014\gates\`):
- **Knob-off identity:** hkP vs t10stP, IDENTITY PASS.
- **H2 STRICT.**
  - Arms: hgT (knob-off, `IMAGE_PAD_BYTES=4448`, gc pak) vs h1T (`ACTOR_PROBE_LIGHT=1 LEON_SOURCE_LIGHT=1
    LEON_LIGHT_HEADROOM=1`, 2x pak).
  - Both arms: `_end` 8c40a33c, stop tick 4700, trace_lock, 0 overruns.
  - Result: STRICT, no divergence.
- **Decisions:** MUST-IDENTICAL over 4701 ticks, drift 0.
- **s30:** 340/340 shown, 0 dropped, in both arms.
- **MCHECK_LEONGC + TEX_CHECK=2** (h1M, 2x pak): LEON-GC PASS on h2, boat and square; TEXCHK PASS 3/3.
- **VRAM:** identical between the arms. Both make 404 uploads totalling 4,994,296 bytes.
- **Host test:** headroom x0.5 and the four toggle modes.
- **Cost:** not run separately. Headroom adds 3 multiplies per part and no per-vertex work, so the modelled ms is the
  probe =1 row.

**Look and jacket luma.** Sheet: `C:\Flycast-Evidence\re4-dreamcast\lp2-20261014\headroom-sheet.png`; numbers in
`headroom-sheet.json`.
- Each cell is the jacket patch's Y mean / p90, using the same patches as the brightness study.
- DC values are Flycast framebuffer. The console column is a MODEL: 480i flicker filter, S-Video bandwidth, CRT gamma
  2.4.

| Jacket Y mean / p90 / top-10% mean (B/G) | Flat (test 10) | Probe =1 | Probe =1 + headroom | + console model (est.) | Flat warm (mode 3) | GameCube | PS2 |
|---|---|---|---|---|---|---|---|
| r100 house | 35.5 / 51 / 58 (0.91) | 24.1 / 45 / 52 (0.87) | 27.2 / 58 / 73 (0.85) | 22.7 / 50 / 64 (0.84) | 35.5 / 52 / 58 (0.86) | 48.3 / 76 / 84 (0.80) | 37.6 / 65 / 73 (0.87) |
| r101 F | 42.2 / 56 / 63 (0.90) | 23.7 / 42 / 52 (0.85) | 23.9 / 42 / 53 (0.85) | 19.5 / 35 / 45 (0.84) | 42.2 / 57 / 63 (0.85) | 45.1 / 70 / 81 (0.77) | 52.8 / 76 / 82 (0.79) |
| r101 wide | 38.7 / 53 / 69 (0.90) | 20.8 / 44 / 62 (0.86) | 21.7 / 48 / 67 (0.85) | 17.8 / 42 / 58 (0.84) | 38.7 / 53 / 69 (0.85) | 27.6 / 43 / 51 (0.78) | 44.5 / 70 / 79 (0.78) |
| r10b start | 32.1 / 43 / 50 (0.95) | 21.6 / 37 / 46 (0.94) | 22.8 / 43 / 52 (0.93) | 18.5 / 35 / 43 (0.93) | 32.1 / 43 / 49 (0.91) | 36.4 / 69 / 83 (0.92) | 25.8 / 56 / 67 (0.89) (jacket, not comparable) |

The GC r100 house shot has approximate framing.

What this shows:
- **Headroom brings back the highlights.** The p90 rises from 45 to 58 in the house, 37 to 43 in r10b, and 44 to 48 in
  the wide shot. In r101F (TEV x1, Leon in his own shadow) it does not change.
- **It does not bring back the mean.** Probe + headroom is still 25-45% below the flat test 10 Leon:
  - house: 27 vs 36
  - r101F: 24 vs 42
  - wide: 22 vs 39
  - r10b: 23 vs 32
- GC and PS2 are above flat in most rows. In r101, GC's brightness is Filter00 (x1.41); see the brightness study.
- The modelled console makes every DC column about 15% darker again (CRT gamma).
- The remaining mean gap is the light intensity on Leon's camera-facing (back) side. Only the ambient and the folded
  residual light it, and D36's exact GC lights give the same result. It is not the 1.0x cap.
- Mode 3 (FLAT WARM) keeps flat's luma and warms the hue. The jacket's B/G goes from 0.90-0.95 to 0.85-0.91; GC is
  0.77-0.92.

## Leon fill (LEON_LIGHT_FILL) and draws outside the owner path

Lane light-p3 (branch `lane/light-p3`, for test 12). Both changes are render only and default off.

**Draws of Leon's 2x textures outside the owner path** (commit `eeef15ae`, part of `LEON_LIGHT_HEADROOM=1`).
- With headroom, the owner path halves Leon's vertex colours, but the radio-call portrait and the source fallback
  draw Leon through `re4dc_model_submit` at full scale, so the 2x textures came out blown (test 11 known issue).
- `re4dc_model_submit` (native_model.cpp) now gives any part not already marked, whose image is one of Leon's 2x keys
  (`re4dc_leon_hr_image`, native_ui.cpp: the `charbake_variants.h` keys plus pl08; only 512x512 and 64x128 images are
  looked up), a copied lighting record with `tev_scale` x0.5, marked in `normal_matrix[7]`.
- `build_lights` keeps the fast fold for those records: it folds at full scale (caps checked on 2x the scale) and
  halves the vertex colours after the pass (`half_post`), so the result is exactly the 1x look.
- Path audit (code reading): the owner paths were already halved; every other model draw goes through
  `re4dc_model_submit`; Ganado casts never use Leon textures; UI, title, save, menus and movies have no Leon textures.

**Fill, `LEON_LIGHT_FILL=F`** (commit `5ccb3a9b`; F is an integer 0..100; needs `ACTOR_PROBE_LIGHT=1/2`).
- **Problem.** With the probe, Leon's camera-facing side is lit only by the ambient and the folded residual, so the
  jacket mean stays 25-45% below the flat Leon even with headroom (table above).
- **What it does.** Leon's parts get a second direction from the part origin toward the camera (view space `-t/|t|`,
  in the part's normal basis like the probe direction). Its colour is F% of the probe's total (directional + ambient)
  at the probe's scale, headroom x0.5 included. `probe_dirs_all` builds it per palette entry for skinned parts.
- It uses the fast kernel's direction 1, which is zero for a probe fold, so there is no new pass, path or per-vertex
  work: the kernel already evaluates three directions.
- **Unchanged:** the probe direction, its colour, the ambient, and the shared `actor_light_probe.h` record (the
  shadow lane reads `dir` and `coherence`). Ganados keep one direction.
- **Why not simpler.** A higher ambient lifts every side equally and flattens the probe's shading; the flat Leon has
  no shading at all. The fill lifts only the side the camera sees, which is what the jacket-luma gap measures.
- **Extension contract.** The fill takes direction 1. `ACTOR_PROBE_LIGHT_EXTRA` (option branch `a6496bef`) also uses
  directions 1 and 2, so with the fill on it may use only direction 2 (EXTRA <= 1). Not combined in any build yet.
- **Checks.** Host test: fill=45 with headroom, fill=30 at probe=2 (direction, colour, Ganado unchanged, shared record
  unchanged, palette directions equal to `skin_light_dirs`), and make-rule cases. Knob-off identity lfoffP vs p3baseP
  and vs p3off2P: IDENTITY PASS. `LEON_LIGHT_FILL=0` with probe + headroom (lf0W) vs p3hr2W: IDENTITY PASS.
- **Runtime check of the x0.5 draws (2026-10-14).** Arms are on the test 11 recipe and data, with Leon's textures at 2x.
  - The radio-call hair in the test 11 lead's frames measures test 10 40/70 and test 11 81/139 (Y mean/p90). Test 11
    is exactly 2x, so the bleaching is the doubled hair texture `ac381b1a`/`7a9de1fd` (64x128). The inventory Leon
    (`ssPlModel`, `src/Sscrn/ss_model.cpp`) and the call portrait (`tel00ModelInit`) are generic player-archive
    cModels. Only their hair uses a doubled key; the body and face use GameCube keys that are not doubled.
  - `LEON_HR source part 64x128 x0.5` is logged in the door103 call run and in the source-fallback run (warp
    `late 0x10`, 12 hits). It is not logged in the owner runs (house, r101F).
- **Gates on light-p3** (evidence `C:\Flycast-Evidence\re4-dreamcast\lp2-20261014\gates\t12*`; test 11 recipe and data):
  - Knob-off identity: PASS (lfoffP vs p3baseP / p3off2P). `LEON_LIGHT_FILL=0` (lf0W) vs the eeef15ae-only build
    p3hr2W: PASS, so the fill code adds nothing when it is off.
  - H2 STRICT, t12h2b4 (l12baseptT: lane/t11 `c4f7c78e`, padded to `_end` 8c415edc) vs t12h2c (l12f45tT: eeef15ae +
    `LEON_LIGHT_FILL=45`), stop tick 4700, trace_lock, 0 overruns: STRICT over 4701 ticks; decisions MUST-IDENTICAL,
    drift 0. The candidate carries both changes, so this covers eeef15ae alone too (render only; the fill is the only
    other difference).
  - s30: 340/340 shown, 0 dropped, in both arms.
  - LEON-GC PASS on h2 / boat / square (t12mh2d, t12mboatd, t12msq; l12f45mW); TEXCHK PASS 3/3.
  - Earlier runs cut by the C: capacity guard (t12h2b, t12h2b2, t12h2b3, t12mh2, t12mboat, t12mh2c, t12mboatc) are
    superseded.
- **Cost of the call screen (SH-4 hardware model, MODELLED, not console).** hwproject on the door103 radio call, frames
  400..479 (the sub screen is open from about frame 250 to the end of the run), 12 traced frames:
  - l12h0tW (test 11 recipe + eeef15ae, half_post on Leon's hair): 40.79 ms/frame (what-if 35.8..48.1).
  - l12basetW (lane/t11 `c4f7c78e`): 42.75 ms/frame (what-if 37.4..50.5).
  - The difference is within layout noise. half_post halves the vertex colours of a few hair parts after the pass,
    and no cost can be measured.
- **Look:** sheet `C:\Flycast-Evidence\re4-dreamcast\lp2-20261014\t12\leon-fill-sheet.png` (tmp/lp3/sheet12.py),
  with the values in `leon-fill-sheet.json`.
  - Hair Y mean/p90. Call portrait: test 10 40/70, test 11 81/139, test 12 48/77; the test 12 frame is 1 s earlier in
    the head animation. Inventory: test 10 26/49, test 11 46/78, test 12 26/49.
  - Source fallback, jacket 28/48.
  - Fill, jacket Y mean/p90:

    | Scene | Test 10 flat | Fill 0 (test 11) | Fill 30 | Fill 45 | Fill 60 | GameCube |
    |---|---|---|---|---|---|---|
    | r100 house | 36/52 | 27/58 | 42/80 | (run cut) | 56/98 | 48/76 |
    | r101 F | 43/58 | 24/42 | 33/56 | 38/63 | 43/70 | 45/70 |
    | r10b start | 32/43 | 23/43 | 34/56 | 39/64 | 44/70 | 36/69 |

  - **Test 12 ships eeef15ae and `LEON_LIGHT_FILL=45`** (update 2026-10-15). The user approved the lighting look
    ("just dark... fix in 12"), and fill 45 is the strength that matches the GameCube jacket brightness. Gates for
    fill 45: H2 STRICT 4700 (t12h2b4 vs t12h2c) and knob-off identity. It is in the test 12 recipe (test12/t12-build.sh
    T12REC). An earlier note here said the fill would wait for test 14; that no longer applies.

## Recommendation

- **Leon, update of 2026-10-14: if the probe ships, ship it with `LEON_LIGHT_HEADROOM=1` and the 2x pak.** Without
  headroom the probe only darkens Leon. With it, the highlights come back (p90 up to flat or above), but the mean stays
  25-45% below the flat test 10 Leon. Judge it live with the lab toggle against Dolphin before making it the default
  look. The cheapest warm-up for flat Leon is mode 3 (0 ms).
- **Leon: ship `ACTOR_PROBE_LIGHT=1`.** It costs about +1.3..1.9 ms modelled (lighting 1.6..1.8 ms on its own) in
  every scene, looks like D36, and carries the dynamic lights. D36 on its own is unsafe: +21.9 ms when Leon is under
  more than 3 lights.
- **Ganados: keep CROWD_FLAT (flat) by default. `ACTOR_PROBE_LIGHT=2` is the option to choose by fps and look.** It
  adds about +0.5..0.7 ms in the house and about +1.5 ms in the wide fight on top of =1. That is cheaper than both
  D5 designs: design 1 costs +0.6..0.75 in the house and +2.8 wide; design 2 costs +1.8 and +5.5. It also gives the
  shadow lane a direction for every near Ganado.
- **Dynamic lights:** keep A (free, already in). C and D are the cheap next options if a flash is wanted. B stays an
  unmerged option. Do not do E, F or G.
- **Budget** (whole frame vs flat, worst r101 view):
  - Characters about 2 ms with =1, about 3.4 ms with =2.
  - With option B (extra lights), add about 0.2..0.5 ms of lighting work.
  - World dynamic light: 0 ms CPU.
- **Shadows** take direction and strength from the probe record (one light table). The shadow lane owns its volumes;
  this lane does not touch them.

The ms figures are modelled on the SH-4 hardware model, not measured on a console. A console run is needed before the
fps claim is final.

## Villagers (GANADO_LIT, lane ganlit, 2026-10-16)

KNOWN_ISSUES "Leon and most villagers are not lit": since test 10 the cast villagers take the room's GX light set
(PS2_GANADO_LIT), but CROWD_FLAT draws every part in one colour, so they read flat next to the probe-lit Leon.
Branch `lane/ganlit16` (from t15/int ae3d2c8b), all knobs default 0, user picks from the still sheet
`C:\Game Dev\Emulators\ganlit-20261016\GANLIT-SHEET.png`. Evidence `C:\Flycast-Evidence\re4-dreamcast\ganlit-20261016`.

Knobs (crowd.mk; render only):

- `GANADO_LIT=1` (needs `ACTOR_PROBE_LIGHT=2`): `GANADO_LIT_NEAREST=N` limits the per-vertex probe light to the N
  nearest Ganado models (crowd ranking, 10% hysteresis so two equally near villagers do not flicker); the rest take
  one colour per part from their probe. N=0: every villager flat from its probe; N=-1 (default): every near-tier
  villager, i.e. `ACTOR_PROBE_LIGHT=2` alone.
- `GANADO_LIT_FILL=F`: Leon's camera fill (`LEON_LIGHT_FILL`) for the probe-lit villagers, F% of the probe total in
  the kernel's spare second direction (no new pass). It brings the shaded villagers back near today's brightness under
  the PVR's 1.0x vertex-colour cap.
- `GANADO_LIT_TOGGLE=1` (debug, DBG_WARP): warp `ganlit <m>` (0 = test 15 flat, 1..8 = the m-1 nearest, 9 = every
  near one) and `ganfill <F>`, so every option is priced and shot from one binary.

Cost: SH-4 hardware model, console-fit what-if, MODELLED (not console). Per drawn tick, delta vs today in the same
binary (layout noise excluded). benchmark-r101-t12 (cross, 500:1399, 6 alive, g70 Ganados) and benchmark-r100house
(1300:2199), T15 data (t14rcrP + cast15, glod, res16).

| Option | Knobs on top of T15REC | Cross | House | Look |
|---|---|---|---|---|
| Today | - | 70.81 ms | 72.33 ms | one flat colour per part |
| (a) probe, flat | `ACTOR_PROBE_LIGHT=2 GANADO_LIT=1 GANADO_LIT_NEAREST=0` | -0.08 | -0.02 | as today (slightly brighter); no shading |
| (b1) nearest 1 shaded | `... GANADO_LIT_NEAREST=1` | +0.41 | +0.06 | one villager shaded, the rest flat |
| (b) nearest 2 shaded | `... GANADO_LIT_NEAREST=2` | +0.49 | +0.06 | two shaded, rank changes swap flat/shaded |
| (c) all near shaded | `ACTOR_PROBE_LIGHT=2` (or `GANADO_LIT=1`) | +0.55 | +0.07 | shaded like PS2, darker than today |
| (b) + fill 45 | `... NEAREST=2 GANADO_LIT_FILL=45` | +0.58 | - | |
| (c) + fill 45 | `ACTOR_PROBE_LIGHT=2 GANADO_LIT=1 GANADO_LIT_FILL=45` | +0.70 | +0.31 | shaded, near today's brightness (recommended) |

Fill rows come from a second toggle binary (glDrW: cross today 70.87, house 72.32). The per-vertex cost is
`re4dc_avk_light_skin_n16` (1.06 -> 1.65 ms at the cross); the probe itself replaces build_lights for the villagers,
which is why (a) is slightly cheaper than today. The old +1.8..3.4 ms (10-14) was a whole-frame delta across binaries
with 12 full-mesh Ganados; at cap 6 with g70 the villager share is about +0.55 ms.

Not built (option, costed): villager headroom like `LEON_LIGHT_HEADROOM` (Ganado atlases at 2x offline, villager
colours x0.5): 0 ms and 0 VRAM, but every other draw of a villager texture (source-path fallbacks, cutscene full
models) must halve too; data + about 10 lines, medium risk. The probe's directional colour reaches 1.1-1.3x in r101
(TEV x1) and more in r100 (x2), so lit sides clip without it; fill 45 is the cheaper brightness fix.

Gates (lane, 10-16): knob-off identity (glrP image 72d5a307 = t15/int rP, 6 overlays) PASS; rP `_end` 8c41f138 with
(c)+fill (+0 B, no KOS squeeze needed); STRICT + decisions MUST-IDENTICAL vs T15REC trace (padded `_end`) on h2, bell,
door103 for NEAREST=2 and on h2, bell for NEAREST=-1 FILL=45 (door103 has no villager in its 2000 ticks); TEXCHK
PASS 3/3 + LEON-GC PASS 3/3 + wrap=0 (h2 120 s, bell, door103); host test `tests/test_actor_probe_light.py`
(ranking, hysteresis, toggle, fill). No r104 / r106 row on the sheet: no villager reached a warp view there (DC or PS2).
