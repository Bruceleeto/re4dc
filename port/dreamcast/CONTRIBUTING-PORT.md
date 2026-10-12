# Contributing to the Dreamcast port

This page gets you from a clean Linux machine (or WSL) to your own build of the game running in
Flycast or on a Dreamcast with GDEMU. You build only the program. The game data comes from a
published test release, so you never need the original discs or our private asset folders.

## 1. Toolchain

You need the exact toolchain the maintainers use: KallistiOS commit 804b3195 with the three patches in
`patches/`, and the KOS "stable" SH4 compiler (GCC 15.2.0, binutils 2.45.1, newlib 4.6.0.20260123).
Pick one way.

**Docker.** From the repository root:

    docker build -t re4dc-toolchain -f port/dreamcast/docker/Dockerfile .
    docker run --rm -it -v "$PWD":/src re4dc-toolchain bash port/dreamcast/build-public.sh

(The Dockerfile runs the same script as below; the maintainers have tested the script, not yet the image.)

**Script.** On Ubuntu 24.04 install the host packages listed at the top of
`tools/setup-toolchain.sh`, then:

    bash port/dreamcast/tools/setup-toolchain.sh ~/re4dc-toolchain
    . ~/re4dc-toolchain/env.sh

The script took 11 minutes on 12 threads in a clean directory and needs about 6 GB free while it
builds. The finished toolchain is 402 MB.

## 2. Build the program

    bash port/dreamcast/build-public.sh

This builds the current test recipe into `port/dreamcast/out-public`: `re4dc-game.elf`, the room
overlays (`*.ovl`) that belong to it, and `resolved-knobs.txt` with every build knob as make saw it.
Add your own knobs at the end, for example `bash port/dreamcast/build-public.sh MY_FEATURE=1`.

The public build differs from a maintainer build in a few places, because some inputs are generated
from game data and cannot be in a public repository. `game/public-assets` holds neutral stand ins:

* Leon and the villagers draw with their original GameCube models from the disc instead of the
  converted meshes. They look the same as the GameCube version but cost more time to draw.
* The PS2 character models (Leon, villagers, El Gigante, Del Lago) are off.
* The memory card messages show the GameCube wording ("Memory Card in Slot A") instead of the VMU wording.

So measure your change against your own public build with the change switched off, not against the
release numbers.

## 3. Put it on a release disc

Download a GDEMU test release from the releases page, then:

    python3 port/dreamcast/tools/swap-program.py RE4DC-Console-Test-c29c4bf5-20261011-GDEMU.zip \
        port/dreamcast/out-public mydisc

`mydisc` gets `disc.gdi` and its three tracks: the release disc with your program as the boot file and
your overlays in place. Everything else on the disc is unchanged. Use a release made from the same or a
close source revision; a program much newer than the release may need data files the release lacks.

To start a new game by itself (useful for repeatable tests), add the scripted pad file:

    ... mydisc --add dc/padscript.txt=port/dreamcast/tools/padscript-newgame.txt

Do not use that disc for normal play: the script presses buttons at fixed times.

## 4. Run it

**Flycast:** open `mydisc/disc.gdi`. Keep the track files beside it.

**GDEMU:** copy the four files into a new numbered folder on the SD card.

## 5. Speed display

Test builds show their speed on the VMU in controller slot 1: drawn frames per second, game speed,
CPU percentage and the frame pacing mode. Hold R and press START to cycle the frame pacing
(Smooth, Fast, Off). Builds that also have the on screen display use R and START to cycle the display
instead: Off, VMU, Screen, Both. Hold X and press START to switch the look preset.

## 6. Send a patch

* Put every change behind a build knob whose default is 0, so the default program does not change.
  The knob goes in the makefiles under `game/` with a comment saying what it does.
* Describe the gain in milliseconds per frame, and say where you measured it: the room, the camera
  view and how many enemies were on screen. Numbers from a fight with villagers in view matter most.
* Say what the change looks like, with a screenshot pair (knob off, knob on) if it changes the picture.
* Open a pull request against the `dreamcast-port` branch.

The maintainers then run the gameplay identity gates before a change goes into a test build. They
replay recorded sessions and compare the game logic tick by tick, so a render change must leave the
gameplay exactly as it was. That harness uses private recordings, so you do not need to run it.

## 7. A full disc from your own discs

You do not need this to work on the code. A whole disc (not only the program) can only be built from
your own copies of the games; the repository holds the tools and recipes, never game data. Today that
path is not one command: several outputs are frozen results of conversion and review work that the
maintainers keep outside the repository.

| Source you need | What the port makes from it | Rebuilt by a script from the disc? |
| --- | --- | --- |
| GameCube Resident Evil 4 debug disc 1 (G4BE08, extracted file tree) | base disc tree: rooms, enemies, sound banks, menus | mostly (`tools/le_mirror.py`, `tools/d367/stage.sh`, `tools/aica_banks.py disc`) |
| same | Dreamcast room meshes (`dc/native/rXXX/MAINSCENARIO.re4mesh`) | yes, per room (`tools/convert_room_bins.py`) |
| same | room archives with Dreamcast audio (`st1/rXXX.dar`) | per room steps, not one command |
| same plus game run logs | texture package `dc/tex.pak` (VQ textures) | no: the VQ selection comes from logs of test runs |
| PS2 Resident Evil 4, USA (SLUS 21134), `BIO4MOV.AFS` | cutscene movies `dc/movie/*.seq` | yes (`tools/convert_route_movies.py`, needs ffmpeg) |
| PS2 USA, `BIO4DAT.AFS` rooms (plus two JADERLINK unpack tools) | PS2 room worlds `dc/native/rXXX/ps2-world.*` | converters exist; the released set is a reviewed frozen output |
| PS2 USA characters | PS2 Leon and villager meshes (compiled into the program), registry packs, pl08 pack | no: needs Blender and review steps |
| none (made by hand or by tools) | title art, look presets, glyphs, character bakes, test scripts | no |

No PC version and no GameCube retail disc are used. The second GameCube debug disc is used only by
the decompilation build.

## Questions

Open an issue. The build notes for maintainers are in `tools/d367/README.md`, and the port notes are
in `README.md` in this folder.
