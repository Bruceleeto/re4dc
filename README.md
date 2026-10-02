![RE4 Dreamcast](docs/images/title.jpg)

# RE4 Dreamcast

**Resident Evil 4, running on the Sega Dreamcast.**

A port of the GameCube game to the Dreamcast, built on a complete byte-identical decompilation of the
GameCube debug build. The game's own logic runs unchanged, so collision, enemy AI and event scripting
behave as in the original. Rendering, memory and loading were rebuilt for the Dreamcast's 16 MB of
RAM and its PowerVR graphics chip.

- **Dreamcast rendering:** a native PowerVR renderer, room worlds rebuilt from the PS2 version's
  lighter assets, and textures compressed to VQ.
- **The full presentation:** cutscenes play as streamed movies with audio, alongside the in-game
  events, the HUD, radio calls, the Player's Manual and the chapter results screens.
- **Dreamcast hardware:** VMU saves, selectable frame pacing, and a GD-ROM image for GDEMU.

[Releases](https://github.com/lamb2k/re4dc/releases) · [Roadmap](port/dreamcast/docs/D367_THIRTY_FPS_ROUTE.md) ·
[Port notes](port/dreamcast/README.md) · [Decompilation](docs/DECOMPILATION.md)

## Status

Published builds are public prerelease test builds. Each one is checked in [Flycast](https://github.com/flyinghead/flycast).
They are not a full game disc: a build holds only the data for the rooms below.

| Chapter | Rooms | State |
| --- | --- | --- |
| 1-1 | intro, r100 forest, r101 village, r103 farm, r106 woods | **Playable** from the title to the chapter end and save |
| 1-2 | r104, r107, r105 | **Playable** to the chapter end and save (build r21m); emblem and key-item pickups not yet checked in play |
| 1-3 | r105, r101, r102, r108, r109, r10a, r10b | Opening cutscene plays; the rooms are next |

The target is 30 fps on a real NTSC Dreamcast. Flycast is only a stand-in for that; the slow spots are
under [Known issues](#known-issues).

## Backlog

1. First test on a real Dreamcast (GDEMU image built, boots in Flycast).
2. Speed in r103, the r101 fight, r106 and r105, toward 30 fps.
3. Chapter 1-2: emblem and key-item pickups checked in play.
4. Chapter 1-3 rooms.
5. Loading a save made inside r106.

## Known issues

As of build r21m, checked in Flycast:

- **The game stops at r105.** Chapter 1-3's opening cutscene plays, but the rooms after it are not built yet.
- **Saves made inside r106 don't load.** After the room loads, every disc read fails. The end-of-chapter
  saves load fine.
- **Untested pickups.** The emblem (the r104 gate to r107) and r105's key item were only forced in tests,
  never picked up in normal play.
- **Slow spots** (Flycast, Fast frame pacing): the r101 village fight (~12 fps, ~80% game speed), r106
  (~12.5 fps, ~84%), r103 (~14 fps, 90-99%) and r105 after chapter 1-3's opening (~11 fps, ~74%). r107
  keeps ~97% speed at ~14.5 fps. The rest runs at full speed, 21-30 fps.
- **Slow frames after radio calls and the inventory** (about 5 s while the room's textures reload). Fixed for
  the next build.
- **The cliff cutscene in the first area doesn't play** (examining the cliff edge; not enough memory for its
  video). Fixed for the next build.
- **The first house fight runs at 12-17 fps**, and outdoors in the first area Fast pacing skips about 2 frames
  in 5 (17-20 fps), which looks choppy. Hold R and press START to cycle the pacing: Off draws every frame
  but the game runs slower there.
- **r104's arrival cutscene drops some frames** (about 25 of 4,856) when reached from the chapter 1-1 save.
- **Some effects are skipped in busy fights.** When video memory is full, a few effect sprites are left
  out rather than stalling the game.
- **Over-bright colours in r100.** Parts of the PS2 world are flat and bright, e.g. the hedge by the gate
  after the radio call.
- **Never run on a real Dreamcast.** The GDEMU image is only tested in Flycast, which boots with its
  built-in BIOS. Builds up to r21m would crash on a console early in the first room (misaligned memory
  reads that Flycast lets through); this is fixed for the next build, which also shows a crash report on
  screen if the game stops.

## Playing

Download a build from [Releases](https://github.com/lamb2k/re4dc/releases). Each build covers only the
rooms in [Status](#status), not the full game. No BIOS is included.

- **Windows:** unzip `RE4DC-<build>.zip`, double-click `Play-<build>.cmd`.
- **Steam Deck / SteamOS:** extract `RE4DC-<build>-SteamOS.tar.gz` and run `play.sh`. It installs
  Flycast from Flathub if needed.
- **CachyOS / Arch:** extract `RE4DC-<build>-CachyOS.tar.gz`, run `./play.sh`.
- **Dreamcast with GDEMU:** copy `disc.gdi`, `track01.bin`, `track02.raw` and `track03.bin` into a
  new numbered folder on the SD card. Not yet tested on hardware.

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

## Development

Rooms, characters and textures are rebuilt from the original data by offline tools, and each change is
reviewed on sheets like these before it lands. Rendering changes are checked against a logic trace of
the original code, so gameplay stays identical.

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
- the build (e.g. r21m);
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
