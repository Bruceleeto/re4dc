# D367 Phase 2 plan (2026-10-11)

Goal: PS2-based look with Dreamcast-native strengths, faster frames, route to chapter 2-2. Every item ships behind a default-off knob, chosen by hw ms, tested by the tiers below.

## Safe build

- **Phase 2 base = r22j test 7.** After the console confirms it, release it as **r23** and tag `phase2-base`. Testers always have r23 as the fallback.
- Lanes branch from origin, land default-off knobs, and never touch the r23 recipe.
- Only the coordinator builds test discs: r23 recipe + the landed Phase 2 knobs, one disc, `OBSERVE.md`, release gates. A regression = switch that knob off and rebuild; r23 stays playable.

## Step 0: remove the shared dependency (first, small)

Every lane is coupled through heap 4: any image size change shifts the em10 parts alloc (H2 frame 660) and r10b streaming, so each landing forces an `IMAGE_PAD_BYTES` recompute and re-gates the others. **Land the fixed parts reservation** (heap 4 slab for em10 parts, sized from the worst case) so image growth no longer changes gameplay. Full tier gates (memory trigger). After it, lanes are independent.

## Ownership rules (prevent collisions)

| Shared thing | Single owner |
|---|---|
| Room packages (r4im) | Lane B; others request rebuilds |
| `dc/tex.pak` | coordinator, regenerated at integration from lane atlases |
| Test recipe | coordinator; a lane adds only its knob line when landed |
| `native_actor_fast.cpp` / registry draw | Lane A |
| PVR submission / lists (`native_ui.cpp` submit path) | Lane C |
| Room code, overlays, route | Lane D |

## Lanes

| Lane | Items, in order | Main files | Gate tier 2 triggers |
|---|---|---|---|
| **A Characters** | A1 lit villagers: PS2 3 lights + ambient, FIPR, intensity mode. A2 character mipmaps + PS2 4bpp palette textures. A3 crow, solid PS2 wing. | actor draw, registry, texture tools | perf decision |
| **B Objects + packages** | B1 PS2 room objects, heaviest rooms first (r100 set pieces, r103, r108, r118). B2 combined r118 package (wolf + female Ganado). | ps2_cast / room tools, room packages | memory (packages), perf |
| **C GPU / submit** | C1 vertex DMA (CPU time). C2 modifier volume shadows. C3 Del Lago bump. | PVR submit path | PVR timing (console), perf |
| **D Route + fixes** | D0 = Step 0. D1 Flycast cutscene hang: timed wait + recovery. D2 silent chapter 1-3 results music. D3 chapter 2-2: r112, r111, r113, r11c. | mem, movie, audio, room code | memory, logic, new rooms |

Kept as is: GameCube Ashley (PS2 skeleton does not bind). Out of scope: glow via render to texture (GPU bound outdoors), lake ripples (look decision pending).

## Waves (two builder agents at a time)

| Wave | Agent 1 | Agent 2 | Ships in |
|---|---|---|---|
| 1 | D0 fixed parts reservation, then D1 | A1 lit villagers, A2 mipmaps + palettes | test 8 (+ animals, wolf) |
| 2 | B1 objects, B2 r118 | A3 crow, then C1 vertex DMA | test 9 |
| 3 | D3 chapter 2-2, D2 music | C2 shadows, C3 bump | test 10 → **r24** |

A lane that finishes early takes the next item in its own column; no lane starts work owned by another.

## Per item

Lean gates (build, missing.txt, knob-off identity, one H2 STRICT, 0 MISALIGN, s30 if size changed) plus the listed triggers. One hw number vs control for perf items. No sheets, one still per visual item, discs deleted after gates. Branch `p2/<lane><n>-<topic>`, report "Ready to land" with head and numbers.

## Human tests

Each test build: `OBSERVE.md`, 5 to 8 lines, room + what to look at. Console-only questions go to testers in the release notes. Looks are judged by watching the disc; players confirm on hardware.

## Test tiers

- Tier 1, every change: build, empty missing.txt, knob-off byte identity, one H2 STRICT (ACT_CAP=0, decision_cmp), 0 MISALIGN, s30 heap_before >= control if the image size changed.
- Tier 2, only when triggered: memory layout (full s30, r10b s20, all H2 windows), logic or events (all STRICT windows, bell, New Game), new rooms (warp and play through), PVR timing (console test), perf decisions (hw model at worst views with enemies, one arm vs control), release candidates (everything once on the final image).
- Tier 3, human: looks, feel, console-only bugs, route playability.
