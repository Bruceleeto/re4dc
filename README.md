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

Builds are private test builds. Each one is checked in [Flycast](https://github.com/flyinghead/flycast).

| Chapter | Rooms | State |
| --- | --- | --- |
| 1-1 | intro, r100 forest, r101 village, r103 farm, r106 woods | **Playable** from the title to the chapter end and save (build r21l) |
| 1-2 | r104, r107, r105 | r104 playable; r107 and r105 run in tests, chapter end and save work |
| 1-3 | r105, r101, r102, r108, r109, r10a, r10b | Opening cutscene plays; the rooms are next |

Speed in Flycast with frame pacing on (Fast):

| Spot | Pictures / s | Game speed |
| --- | --- | --- |
| r100 forest, ambush | 21-23 | 100% |
| r103 farm | ~14 | 90-99% |
| r101 village fight | ~12 | ~80% |
| r106 woods | ~12.5 | ~84% |
| r100 bridge (police car) | ~3 | ~12% |
| r104 | 30 | 100% |

The target is 30 fps on a real NTSC Dreamcast. Flycast is only a stand-in for that.

## Backlog

1. First test on a real Dreamcast (GDEMU image built, boots in Flycast).
2. The r100 bridge scene slowdown.
3. Speed in r103, the r101 fight and r106, toward 30 fps.
4. Finish chapter 1-2: r105 merged, emblem and key-item pickups checked in play, r107 speed.
5. Chapter 1-3 rooms.
6. Loading a save made inside r106.

## Playing

Download a build from [Releases](https://github.com/lamb2k/re4dc/releases). No BIOS is included.

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

## Credits

Built on the RE4 GameCube decompilation ([docs/DECOMPILATION.md](docs/DECOMPILATION.md)),
[KallistiOS](https://github.com/KallistiOS/KallistiOS) and Flycast. Resident Evil is a trademark of
Capcom. This is an independent fan project for research and preservation, not affiliated with or
endorsed by Capcom, Sega or Nintendo. The game's code and data belong to their owners; the tools and
documentation written for this project are CC0 ([LICENSE](LICENSE)).
