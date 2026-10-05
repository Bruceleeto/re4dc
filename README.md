![RE4 Dreamcast](docs/images/title.jpg)

# RE4 Dreamcast

**An experimental Resident Evil 4 port for the Sega Dreamcast.**

A port of the GameCube game to the Dreamcast, built on a complete byte-identical decompilation of the
GameCube debug build. The recovered game code drives collision, enemy AI and event scripting;
preserving that behaviour is a requirement for port changes. Rendering, memory and loading were
rebuilt for the Dreamcast's 16 MB of RAM and its PowerVR graphics chip.

- **Dreamcast rendering:** a native PowerVR renderer, room worlds rebuilt from the PS2 version's
  lighter assets, and textures compressed to VQ.
- **Presentation:** cutscenes play as streamed movies with audio, alongside the in-game
  events, the HUD, radio calls, the Player's Manual and the chapter results screens.
- **Dreamcast hardware:** VMU saves, selectable frame pacing, and a GD-ROM image for GDEMU.

[Releases](https://github.com/lamb2k/re4dc/releases) · [Roadmap](port/dreamcast/docs/D367_THIRTY_FPS_ROUTE.md) ·
[Port notes](port/dreamcast/README.md) · [Decompilation](docs/DECOMPILATION.md)

## Status

Updated **2026-10-05**. The newest public play build is
**[r22c (chapter 1-3 test)](https://github.com/lamb2k/re4dc/releases/tag/play-r22c-chapter-1-3-20261005)**, with downloads for Windows,
SteamOS / Steam Deck, CachyOS / Arch, and GDEMU, plus SHA-256 checksums. This is an experimental
prerelease test build, not the complete game.

**r22c combines the r22 performance changes with chapter 1-3 rooms through r10a.** The door into the
unfinished r10b room shows "Coming Soon". Its corrected texture pack keeps all 3,249 r22 packages
and adds 498 chapter 1-3 packages. Some chapter 1-3 rooms use substitute music.

For this exact r22c image, the GDEMU boot check reached the VMU prompt in Flycast, and content checks
confirmed that the r22 files and textures were preserved apart from the documented chapter additions.
Every file in the four release archives was read back and checked against its packaged source.
A continuous r22c playthrough and physical-console acceptance remain pending. Earlier chapter 1-3
route checks used separate builds. Build source:
[`2bb24730`](https://github.com/lamb2k/re4dc/commit/2bb24730ccfae533d8ce89addaa098bd2232e751),
with `ROUTE_CH13=1`.

**r21y fixes the console crash when Leon jumps out of the r100 house window.** The camera code deleted a special
camera (left over from examining the dead Ganado, a rifle scope, the binoculars or pushing an object) a second time;
Flycast resets there, the Dreamcast stops with an address error. r21y also shows the VMU's CPU line as a percentage.

**r22 performance changes (included in r22c)** add:
lazy skinning palettes, a faster effect-sprite path, actor and world preparation reused across frames, faster
animation-curve and cloth maths, and a regenerated code layout. Each change was checked to leave gameplay unchanged
(identical logic traces) and the picture identical. On a real NTSC Dreamcast, one r100 playthrough of the r22g test
disc (r22 plus a GPU line on the VMU) read:

| Moment | FPS | Speed | CPU | GPU (ms per frame) |
| --- | --- | --- | --- | --- |
| Outside, before the house | 17.6 | 98% | 102% | 43-46 |
| House, before the first Ganado | 21.8 | 102% | 100% | 14-15 |
| Right after the radio call | 12.9 | 87% | 116% | 11-14 |
| Inside, before the window jump | 9.9 | 67% | 150% | 14 |
| Fight after the jump, three Ganados | 10.4 | 70% | 142% | 53-55 |

The fight improved from r21x's 9 fps at 66% speed; shooting drops it to about 9 fps. The CPU limits every slow
moment. The graphics chip is light indoors and heavy outdoors, which would cap the outdoor fight near 19 fps once
the CPU is faster.

**r21v has now run on a real NTSC Dreamcast (GDEMU, S-Video).** r21x fixed what that first console test found:

- **Crash right after the first radio call and when opening the inventory (Y).** While a call or the inventory has
  the room's memory swapped out, the game still walked the room's object lists. Flycast reads past this; the
  Dreamcast's SH-4 stops with an address error. Those walks are now skipped while the memory is swapped.
- **Invisible blocker drawn as a tan wall in front of the r100 bridge.** Collision-only pieces were drawn as flat
  walls over the PS2 world; they are no longer drawn.
- **Tan frame before each radio call and the inventory.** The screen behind the menu showed the fog colour; it is
  now black, as on the GameCube.
- **Silent radio calls.** The call voices were missing from the disc; they are added.

**The VMU shows the speed.** Once a second the VMU in the first controller shows FPS (drawn frames per second),
SPD (game speed, % of full speed), CPU (work per game tick as % of the time a tick has; above 100% the console is
fully busy) and the pacing mode. Test builds can add GPU (the graphics chip's render time per frame, mean/max ms).

**First console measurements** (a self-running calibration disc on r21v's code, r100): one game-logic tick takes
12.7 ms with Leon alone and 20.3 ms with eight Ganados, inside the 24 ms budget for 30 fps. A drawn frame takes about
53 ms in a quiet view and 90-95 ms with four to eight Ganados, so drawing was the first
target; the r22 readings above show where the time goes now. These figures fell inside the ranges the PC-side hardware model predicted
before the run.

Checked in [Flycast](https://github.com/flyinghead/flycast) for r21y: examining the dead Ganado after s20 and then jumping out of the house window plays on (r21x resets there in Flycast and stops on the console); New Game, the radio call, inventory and the gameplay trace pass as for r21x. For r21x: the title / New Game sequence plays the three opening movies in full and reaches r100 gameplay; the radio call plays its voice; inventory open/close restores the saved game-memory area; no wall in front of the r100 bridge; gameplay traces match the previous build (the fixes change drawing only); the GDEMU image boots to the game's VMU prompt. These are separate checks; a continuous title-to-chapter-end playthrough remains pending.

See the [build checklist](port/dreamcast/docs/D367_PLAY_BUILD_CHECKLIST.md) for source revisions,
test scope and earlier build history.

The staged play data covers the following route; it is not the full game:

| Chapter | Rooms | Verification scope |
| --- | --- | --- |
| 1-1 | intro, r100 forest, r101 village, r103 farm, r106 woods | Room and chapter-end/save checkpoints tested in earlier builds; continuous r22c playthrough pending |
| 1-2 | r104, r107, r105 | Route and chapter-end/save checkpoints tested in r21m; normal emblem/key-item pickups and a full r22c run remain unchecked |
| 1-3 | r105, r101, r102, r108, r109, r10a | Enabled in r22c through r10a; the r10b door shows "Coming Soon". Earlier builds passed separate Flycast route checks; continuous r22c and console checks remain pending |

The target remains **30 fps at full game speed on a real NTSC Dreamcast**. Flycast checks and hardware
estimates do not establish physical-console performance or compatibility.

## Backlog

1. Speed up the fights on the console (r22: 70% speed and 10 fps with three Ganados): the enemies' game logic
   (about 10 ms of every tick, with 9-11 Ganados active even when three are on screen), drawing Leon and the
   Ganados, and, for 30 fps outdoors, the graphics chip's 43-55 ms per frame.
2. Complete the continuous first-chapter playthrough, including combat, inventory, transitions and retry.
3. Fix remaining scene/model/effect rendering gaps.
4. Check normal chapter 1-2 emblem/key-item pickups and loading a save made inside r106.
5. Complete the chapter 1-3 route.
6. Keep testing each build on the console (GDEMU), where crashes Flycast hides show up.

## Known issues

- **Incomplete route and rendering coverage.** The onward chapter 1-3 route and some native scene/model/effect
  coverage remain unfinished. Some effect sprites are skipped when their textures cannot fit in video memory.
- **Untested pickups and saved-game reload.** Normal emblem and key-item pickups remain unchecked. A dedicated
  reload of a save made inside r106 is still needed. The earlier direct-start disc-open failure was fixed by
  serialized texture/disc reads; that test alone does not establish saved-game reload acceptance.
- **Performance is below target on the console.** r22 runs the quiet r100 house at full speed (about 22 fps) but
  slows to 87% after the radio call, 67% before the window jump and about 70% (10 fps) in the fight after it (about
  9 fps while shooting). Fast pacing skips drawing frames to keep the game speed up, so it can look choppy. The VMU
  shows the live numbers. Hold R and press START to cycle the pacing mode.
- **Room-entry pauses remain.** Texture packing reduced earlier measured Flycast entry loads to about 3 s;
  loading is still visible. Radio calls no longer require the earlier full room-texture reload in the tested case.
- **Cutscene playback can still drop frames.** The r104 arrival has shown dropped pictures. During the
  chapter-end checks, an early r104 world preload failed before the subsequent room-entry load succeeded.
- **Over-bright colours in r100.** Parts of the PS2 world, including the hedge by the gate after the radio call,
  remain flat and bright.
- **Console testing has started.** r21v ran on a real NTSC Dreamcast with GDEMU; r21x fixes the two crashes and
  the drawing and sound problems found there. A full console playthrough of r22c is still pending. r21y fixes the camera
  crash at the r100 house window found on r21x. The r22g test disc played r100 through the
  fight after the window jump on the console without a crash. A crash should show the on-screen crash report; please send a
  photo of it.

## Playing

Download **[r22c](https://github.com/lamb2k/re4dc/releases/tag/play-r22c-chapter-1-3-20261005)** for your system:

| System | Download | Start playing |
| --- | --- | --- |
| Windows | [RE4DC-r22c.zip](https://github.com/lamb2k/re4dc/releases/download/play-r22c-chapter-1-3-20261005/RE4DC-r22c.zip) | Extract the whole archive and double-click `Play-r22c.cmd`. Includes Flycast and the keyboard/DualSense launcher. |
| Steam Deck / SteamOS | [RE4DC-r22c-SteamOS.tar.gz](https://github.com/lamb2k/re4dc/releases/download/play-r22c-chapter-1-3-20261005/RE4DC-r22c-SteamOS.tar.gz) | Extract in Desktop Mode and run `play.sh`; uses Flathub Flycast. |
| CachyOS / Arch | [RE4DC-r22c-CachyOS.tar.gz](https://github.com/lamb2k/re4dc/releases/download/play-r22c-chapter-1-3-20261005/RE4DC-r22c-CachyOS.tar.gz) | Extract and run `./play.sh`; uses native Flycast or Flathub Flycast. |
| Dreamcast / GDEMU | [RE4DC-r22c-GDEMU.zip](https://github.com/lamb2k/re4dc/releases/download/play-r22c-chapter-1-3-20261005/RE4DC-r22c-GDEMU.zip) | Copy `disc.gdi`, `track01.bin`, `track02.raw` and `track03.bin` together into a new numbered SD-card folder. |

[SHA-256 checksums](https://github.com/lamb2k/re4dc/releases/download/play-r22c-chapter-1-3-20261005/SHA256SUMS.txt) and test notes accompany the release.
The emulator packages contain the title disc as `disc/disc.cue` and `disc/disc.bin`; open the `.cue`
in an existing Flycast installation if preferred. Keep both files together.

For GDEMU, keep all four filenames unchanged. If using a card manager, save its changes before safely
ejecting the card. Put a VMU in the first controller slot for the speed readout.
No BIOS or personal VMU saves are included; keep your existing saves separately. Game data is not
committed to this source repository.

| Action | Dreamcast pad |
| --- | --- |
| Move | Analog stick |
| Aim / fire | Hold R, press A |
| Action / talk / pick up | A |
| Run / cancel | B |
| Knife | L |
| Inventory | Y |
| Pause / options | START |
| Frame pacing (Smooth → Fast → Off) | Hold R, press START |
| Speed readout (FPS / speed / CPU % / pacing) | VMU in controller slot 1 |

## Development

Rooms, characters and textures are rebuilt from the original data by offline tools, and each change is
reviewed on sheets like these before it lands. Rendering changes require a matching gameplay trace
against their reference build; each test report states its covered rooms and frames.

<p>
<img src="docs/images/dev/ganado-ps2-look.jpg" width="49%" alt="Ganado model from the PS2 version, prepared for the Dreamcast">
<img src="docs/images/dev/r104-world-sheet.jpg" width="49%" alt="r104 world rebuilt from PS2 room data, review sheet">
</p>
<p>
<img src="docs/images/dev/prompt-glyphs.jpg" width="49%" alt="The game's button-prompt glyphs, extracted for the native UI renderer">
<img src="docs/images/dev/manual-vq.jpg" width="49%" alt="Player's Manual page: original texture against PowerVR VQ">
</p>

From left to right, top to bottom: a Ganado from the PS2 version prepared for the Dreamcast; the r104
world rebuilt from PS2 room data; the game's button-prompt glyphs, extracted for the native UI
renderer; a Player's Manual page, original texture against PowerVR VQ compression.

## Pictures

Captured in Flycast from the play builds.

<p>
<img src="docs/images/01-intro.jpg" width="32%"> <img src="docs/images/02-radio.jpg" width="32%"> <img src="docs/images/03-forest.jpg" width="32%">
<img src="docs/images/04-village.jpg" width="32%"> <img src="docs/images/05-farm.jpg" width="32%"> <img src="docs/images/06-woods.jpg" width="32%">
<img src="docs/images/07-cutscene.jpg" width="32%"> <img src="docs/images/08-vmu-save.jpg" width="32%"> <img src="docs/images/09-r104.jpg" width="32%">
<img src="docs/images/10-mendez.jpg" width="32%"> <img src="docs/images/11-chapter-end.jpg" width="32%">
</p>

## How it works

The port keeps the GameCube game's code and replaces the platform underneath it.

- **Game code:** the decompiled C/C++ in `src/` builds for the Dreamcast's SH-4 CPU with KallistiOS. Rooms,
  enemies and weapons stay separate modules loaded per room, as on GameCube
  (`port/dreamcast/game/tools/gen_modules.py`). Collision, AI, events and game state are not changed.
- **Platform layer** (`port/dreamcast/game/platform/`): the GameCube graphics, sound, disc and memory-card
  calls go to Dreamcast versions. These are a PowerVR renderer (`native_ui.cpp`), VQ texture packages
  with a video-memory allocator (`vram_pages.cpp`), streamed cutscene movies (`native_movie.cpp`) and VMU saves.
- **Assets:** game data is never committed. Offline tools convert it from your own discs: room worlds
  from the PS2 version's data, textures to VQ, and cutscenes from the PS2 movies at 288×192 with audio.
- **Checking behaviour:** a logic trace records the game state every tick. A rendering or speed change
  must leave it identical to the reference build. Frame pacing skips drawing, never game ticks.

## Expanding the game

Paths are under `port/dreamcast/`.

| Task | Tool |
| --- | --- |
| Build the play image | `tools/d367/build-r21.sh` (flags in `docs/D367_PLAY_BUILD_CHECKLIST.md`) |
| Build and run a test image in Flycast | `tools/d367/route/route-build.sh`, `route-run.sh` (needs a local Flycast test harness) |
| Jump to a room or spot and set story flags | `tools/d367/warp.py` presets, in test builds (`DBG_WARP=1`) |
| Make test setups for a room | `tools/d367/route/make-route-fixtures.py` |
| See which rooms each chapter needs | `tools/d367/stage_route.py` |
| List what a room needs | `tools/d367/assets.sh discover <room>` |
| Room memory, sound banks, byte order | `tools/prepare_native_ui.py`, `tools/aica_banks.py`, `tools/le_mirror.py` |
| Room worlds from PS2 data | `tools/ps2_room_r4im.py` |
| Textures to VQ; missing textures from a run log | `tools/vq_native_ui.py`; `tools/d367/pairs_from_log.py` |
| Cutscene movies | `tools/convert_route_movies.py` |
| GDEMU image | `tools/d367/mkgdi.sh` |

Adding a room, in short:
1. Run `assets.sh discover` on it and read its entry in `docs/R4_FIRST_STAGE_GAP_AUDIT.md`.
2. Add its memory contract, sound banks and enemy modules.
3. Build its PS2 world, convert its cutscenes and hook them into the room's code.
4. Add a `warp.py` preset, run it in Flycast, and fix missing textures, halts and missing symbols.
5. Before merging, run the regression run: Leon must end up at exactly the same spot as on the
   previous build.

`docs/lanes/route.md` records how each room since r106 was brought up, including the traps found along
the way.

Start reading with:
- `docs/D367_THIRTY_FPS_ROUTE.md`: goals and decisions;
- `tools/d367/README.md`: build recipes;
- [docs/overview.md](docs/overview.md): a guide to the engine's code.

To contribute:
- branch from `dreamcast-port`, one change per pull request;
- include Flycast numbers from before and after the change;
- keep gameplay identical;
- never commit game data.

## Reporting bugs

Open an issue with the **Game bug** form ([Issues](https://github.com/lamb2k/re4dc/issues/new/choose)); any
GitHub account can file one. Check [Known issues](#known-issues) first. Please include:
- the exact build (e.g. r22c);
- where it happened (chapter and room, or what was on screen);
- what you did and what happened;
- whether it was Flycast (and on which system) or a real Dreamcast;
- a screenshot or video.

On Windows, also attach the newest file in the package's `logs\` folder. One bug per issue.

## Credits

Built on the RE4 GameCube decompilation ([docs/DECOMPILATION.md](docs/DECOMPILATION.md)),
[KallistiOS](https://github.com/KallistiOS/KallistiOS) and Flycast. Resident Evil is a trademark of
Capcom. This is an independent fan project for research and preservation, not affiliated with or
endorsed by Capcom, Sega or Nintendo. The game's code and data belong to their owners; the tools and
documentation written for this project are CC0 ([LICENSE](LICENSE)).
