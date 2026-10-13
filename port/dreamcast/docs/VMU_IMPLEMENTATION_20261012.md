# Docked RE4 VMU implementation — 2026-10-12

Implemented as an opt-in candidate in `/root/probe/codex-vmu-plan-20261012/tree`, pinned to `d4bc5f45362c8de3ed2549328a0bc97d9f71a8c0`. The active port checkout and supplied handoff are unchanged. No commit, merge, release or SD-card write has been made.

The runtime covers Leon vitals, Ashley escort/playable status, real Hunnigan terminal calls, and a Luis companion adapter with new matching portrait assets. This is the docked display milestone. The separate executable for a detached VMU is not part of this change.

## Enable and reproduce

Append `VMU_CONTEXT=1` to the existing Dreamcast build recipe. `VMU_CONTEXT=0` is the default and excludes the new objects and hooks. `VMU_MOTION=0` renders static final states; the default is `1`. The existing speed-display setting still takes priority: set Speed Display to Off/Screen to see contextual pages, or use `speed=off` in the existing private test `quality.txt`. No persistent setting or save format was added.

Run portable checks with:

```sh
python3 port/dreamcast/tests/vmu/run_tests.py
```

The private build driver and captured evidence are in `/root/probe/codex-vmu-plan-20261012/out`. The final runtime ELF is `out/build-vmu-complete/re4dc-game.elf`, SHA-256 `16c03395179f711dab91fa2f364d24b25941594ad65d77b56aa741290d97db4d`. Its `resolved-knobs.txt`, source patch, symbol table and build log identify the exact inputs. The qualification build uses the pinned play recipe with `ACT_CAP=0`, `VMU_CONTEXT=1`, `LOGIC_TRACE=1`, `GAME_DECISION_TRACE=1`, `PACE_MODE=off`, `TRACE_SS_MASK=1`, `TRACE_ALLOC=1`, and `CODEC_READY_FIXTURE=1`. It links with no unresolved symbols.

## Live inputs and priority

`game/vmu_context.cpp` publishes one coherent snapshot after the recovered `TaskScheduler`. The display does not change AI, collision, RNG, gameplay decisions, health, inventory, story flags or saves. While the subscreen owns the room heap, the observer retains the last coherent snapshot and updates only the actual call lifecycle. It never dereferences swapped player/companion/inventory storage there.

| Input | Runtime mapping and source authority |
|---|---|
| Player and health | `pG->pl_type`, signed active `pl_life` / `pl_life_max`; `cPlayer::getLifeLevel()` supplies the original game's condition thresholds. Upgraded maxima affect the bar, not the base-HP condition rules. Zero/negative HP is DEAD. |
| Ammo | `ItemMgr.bulletNum()` with `WeaponId2WeaponNo()` and the visibility cases from `cockpit.cpp::dispBulletDigit`. Values above 99 are preserved, hidden ammo is omitted, and only the verified debug infinite-ammo mode becomes INF. |
| Ashley | Register the constructed instance in `SubCharInit(type == 1)` and `Pl11Init`; require both current `pSUB` identity and the matching vtable. Follow/wait come from `SubCharGetCondition()`. HELP uses the actual per-tick capture flag `Status_flg[2] & 0x20000000` or Ashley death, not a generic damage/event routine number. Playable Ashley retains active-player health ownership. |
| Luis | Register the constructed `cSubLuis` instance in `LuisInit`, then check current `pSUB` and vtable. His distinct layout is never passed to Ashley helpers. The supported companion label is ALLY. Conflicting source comments about his numeric ID are not used as identity. |
| Hunnigan | `SsTermMain::init/quit` and terminal cancel/end hooks; operation numbers 0..13 and 23 match the actual `partnerType` table. The subscreen must currently be an uncancelled terminal. A stored last-call number alone cannot show CALL. Speaking motion is illustrative, not lip synchronization. |
| Lifecycle | Restart/room initialization invalidate cached state and visual generations. Frame rollback, room/player changes and LCD device changes cancel old animation. Health changes cancel unfinished growth. Returning from a call resolves current state. Unsupported playable characters produce a blank contextual page. |

Priority is active-player critical/dead, Ashley HELP, active Hunnigan call, companion/playable-Ashley context, then Leon vitals. The bottom strip always belongs to the active playable character.

## Authored story mapping

These four images are an authored story visualization, not a numeric infection meter supplied by the engine. Every snapshot derives the stage from the loaded save; health changes, timers and display use cannot advance it. The table is evaluated in this order:

| Output | Saved source evidence |
|---|---|
| Clear (0) | `Scenario_flg[1] & 0x00000800`, set after `r330` parasite removal. |
| Branching (2), suppressed | Room `0x325` save bit 0 (`word +4 & 0x80000000`), from `R325EventS00`; the original `r325s00` movie shows Leon taking Luis's pills. This recedes from Advanced without claiming removal. |
| Advanced (3) | `Scenario_flg[0] & 0x00040000`, the `r204s00` castle loss-of-control event. |
| Branching (2) | `Scenario_flg[0] & 0x01000000`, set by `R11bInit` after the lake; the original movie shows Leon's infection nightmare. |
| Stirring (1) | Room `0x104` save bit 1 (`word +4 & 0x40000000`), arrival after injection. |
| Clear (0) | Earlier story state with none of these milestones. |

Loading a pre-suppression or earlier save can restore a larger or smaller stage; no monotonic progress is stored separately. Suppression has no invented expiry timer. The native room flag is committed at event entry; normal game snapshots resume when the blocking event yields/returns. Source comments for several cutscenes were inconsistent, so the corresponding original movie members were inspected privately. Those extracted frames and movie data are excluded from this repository. A secondary [cutscene transcript](https://residentevil.fandom.com/wiki/Chapter_5-4_scene_3) helped locate the suppressant scene; original movie and recovered source establish the mapping.

## Pixels, animation and transport

The renderer produces exactly 192 bytes (48×32, row-major MSB, 1 = ink). The supplied Ashley/Hunnigan portraits, Leon growth layers, custom font and ECG geometry are preserved. Positive HP has a minimum one-pixel bar. Growth/retraction settles after 800 ms. Pulse, blink and the illustrative speaking frames use bounded clock phases, with a static build option.

Luis has a neutral/blink pair at the same 48×27 portrait scale. The generated source, canonical packed arrays, rows and provenance live under `game/vmu_assets/`; `tools/export_vmu_context.py` performs offline conversion. Runtime code never loads or resizes PNGs. The blink is restricted to the eye region; other portrait pixels remain identical. See `game/vmu_assets/luis.prompt.txt` for the generation prompt. The built-in image generation tool was used, followed by deterministic 1-bit asset encoding and native-size comparison against Ashley/Hunnigan.

One game-thread LCD owner arbitrates all pages: debug feedback has a three-second lease; the explicitly selected speed page follows; otherwise contextual output wins. It selects the lowest LCD slot on the physical port of controller enumeration 0, matching the gameplay pad mapping, and uses KOS's connector-direction orientation rule. It rescans devices, composes at most 10 times per second, submits only changed frames, coalesces busy updates, and backs off to one attempt per second after three errors. Reconnection sends current committed state.

The existing CARD/save/configuration code is untouched. LCD submission uses KOS's nonblocking packet-copy path. The `sent` inspection counter means KOS accepted the queued request; it is not physical acknowledgement. `read_vmu_lcd.py` now selects the new symbol, including SH-4's leading underscore, and retains the old PACE buffer fallback. Guest-RAM captures prove composition only.

## Validation and remaining acceptance

- Native renderer: all 25 supplied docked golden frames match all 192 bytes; selector, interruption, reduced-motion, ammo/health boundary, saved-story, suppression/removal and transport tests pass with `-Wall -Wextra -Werror`.
- Actual LCD-owner host test: debug lease, speed override, physical controller port, two-slot selection, both orientation calls, rate limiting and reconnect cancellation pass with a fake Maple boundary.
- Feature off: the linked program and all six overlays are byte-for-byte identical to the pre-change control (`out/off-identity-final.json`). The sole initial difference was an existing allocation's `__LINE__` diagnostic; its original logical line is preserved. All six modified recovered files have identical normalized preprocessor output with `__PPC__=1` against their originals (`out/ppc-preprocess.json`). A new PowerPC object-comparison build was not run.
- Disc staging: both ISO namespaces, payload hashes, the independent raw reader and the original boot area pass for every test image.
- First Flycast smoke run: real r100 health changed 1200→820, Hunnigan CALL began and ended, then current Leon vitals returned; 130 LCD requests accepted, zero immediate queue errors. The movie retained a static display while its blocking playback owned execution.
- Repeated control: 3,258 complete records, no gaps, frame-aligned STRICT (including 493 masked subscreen records).
- Full runtime and comparison results: see the final evidence summary below.

Memory cost is material on this pinned build: the final feature increases `_end` by 9,664 bytes. Arena rounding reduces the room heap by 12,288 bytes. The unpadded house comparison consequently differs in allocation-failure history; it must not be called STRICT or accepted for default enablement. A control with matched memory consumption isolates display behavior, but cannot erase this cost. No KOS reserve or existing resource floor was reduced to conceal it.

Physical VMU orientation, asynchronous delivery, disconnects during real save I/O, and Dreamcast CPU/Maple cost remain untested. Luis's `pl14` gameplay module is not part of the pinned native build recipe; its observation hook and portrait are implemented, but native Luis/cabin runtime acceptance needs that underlying module. Playable Ashley, HELP and later story transitions have source/host coverage unless explicitly listed as runtime-observed below. The feature remains default off pending these integration checks.

## Final evidence summary

| Check | Result |
|---|---|
| Reference/reference | 3,258 frame-aligned records: STRICT; no gaps or duplicate frames. |
| Unpadded reference/VMU | 3,075 room-aligned records: FAIL solely in allocation-failure history, first at source frame 1,672. All other traced gameplay/state/decision fields match, with zero player/enemy drift. This is an explicit footprint regression, not a passed gate. |
| Matched-footprint reference/VMU | 3,066 room-aligned records: STRICT and MUST-IDENTICAL, including 493 masked subscreen records. 120,754 em-em decisions, 81,607 line queries, 3,791 area checks and 41,500 damage tests match. Player/enemy drift is zero; one audio-timing query hash differs in the comparator's informational category. |
| Matched control construction | `IMAGE_PAD_BYTES=9568`, with 96 bytes of existing padding diagnostics/alignment overhead, makes both `_end` values `0x8c40553c`. Both logged arenas and heap boundaries are identical. Control ELF SHA-256: `9ff46832f8b20cfa55764858c7bb281d63f6e8d79ac48b0e4a3a18d0c2ae035d`. |
| Final feature, r100 house | 2,582 sampled snapshots; real HP 1200 then 820, loaded ammo 10; call takeover and return; 240 queued LCD requests accepted, zero immediate errors. |
| Final feature, r117 Ashley rescue | Ashley identity/follow status observed from real initialization; Hunnigan takeover and return; 1,559 sampled Ashley-context snapshots; 157 queued requests accepted, zero immediate errors. The test ends in the sequence's subscreen UI; it does not certify every rescue/next-room action. |
| Normal-menu private image | Non-traced `build-vmu-play`, ELF SHA-256 `45db1b2c8c097257298ca6efcc5104388ea215bfbe37c76f01b59efc0c54de2f`. Normal-menu staging removes warp/padscript files, retains the compiled Fast pacing default, and selects contextual output via `speed=off`. A 35-second boot smoke has no halt and keeps the contextual LCD blank outside gameplay. This is boot evidence, not a manual playthrough. |

Machine-readable results: `out/aa-final.json`, `ab-unpadded-final.json`, `ab-unpadded-decisions-final.json`, `ab-padded-final.json`, `ab-padded-decisions.json`, `runtime-observations-summary.json`, `off-identity-final.json`, and `ppc-preprocess.json`. Windows runtime evidence is under `C:/Flycast-Evidence/re4-dreamcast/codex-vmu-20261012/`.

The private normal-menu image is `C:/Flycast-Evidence/re4-dreamcast/codex-vmu-20261012/staging/play-menu/disc/disc.cue` (with its adjacent `disc.bin`). It is a candidate for this pinned base and has not replaced any installed play build. Review material, portrait comparison, validation JSON and the owned source patch/new files are in `C:/Game Dev/Emulators/re4-vmu-implementation-20261012/`.

