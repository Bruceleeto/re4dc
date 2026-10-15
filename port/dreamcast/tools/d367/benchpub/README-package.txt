RE4 DREAMCAST BENCHMARK DISC - THIS IS NOT THE GAME
===================================================

This disc only measures how fast the RE4 Dreamcast port runs on your
console. It cannot be played: there is no title menu and no New Game, and
it saves nothing (it does not touch your VMU). To play, use the current test
release: https://github.com/lamb2k/re4dc/releases

Build SHA_PLACEHOLDER: the test 12.1 program and data, plus the two scripted
benchmark scenes.

What it does (about 4 minutes, no input needed)
1. A start screen says what the disc is. Press START (or wait 20 seconds),
   then put the controller down until the results screen.
2. Scene 1, the village (r101): Leon stands by the burning cross while the
   villagers attack (at most 6 at once), with fire, haze and torches.
   30 seconds are measured.
3. Scene 2, the first house (r100): a short cutscene plays, then Leon waits
   at the back window while the villagers close in. About 17 seconds are
   measured.
4. A results screen shows the numbers for each scene and a code.
5. Press A on the results screen to run both scenes again (optional).

A red banner "BENCHMARK DISC - NOT THE GAME" stays at the top of the screen
the whole time.

How to report
Open a new issue named "Benchmark results" at
https://github.com/lamb2k/re4dc/issues and include:
- a photo of the results screen (sharp, straight on, all text readable)
- the CODE line from the results screen, typed out
- your console region (NTSC-U, NTSC-J or PAL)
- how you ran it: GDEMU, another optical drive emulator (say which), or a
  burned disc
- your video cable (VGA, S-Video, composite, RGB SCART, HDMI adapter)
If it crashes or hangs, photograph the screen and say which scene it was in.

Setup
Copy the four files in the gdemu folder (disc.gdi, track01.bin, track02.raw,
track03.bin) to a new folder on your SD card, the same way as any GDEMU
game. The menu lists it as "RE4DC BENCHMARK (NOT THE GAME)". Flycast can
open gdemu/disc.gdi as well, but emulator numbers are not console numbers.

The results screen
FPS         average frames drawn per second
MIN1S       the lowest one-second window
CPU         milliseconds of game work per game tick (30 ticks a second)
GPU         milliseconds the graphics chip needs to draw one frame
SPD%        game speed (100 = real time; lower means slow motion)
READS/S     disc reads per second
WAIT MS/S   milliseconds per second the game waited for the disc
KOS MIN KB  the lowest free system memory during the scene, in KB (this
            disc gives the system 64 KB more than the game disc does)
CODE        the numbers above in one line, with a check value at the end

SHA256SUMS.txt lists the sha256 of each file in the gdemu folder.
