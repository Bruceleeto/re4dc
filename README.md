![RE4 Dreamcast](docs/images/title.jpg)

# RE4 Dreamcast

**An experimental Resident Evil 4 port for the Sega Dreamcast.**

The recovered GameCube code runs the gameplay, collision and enemy AI. A native PowerVR renderer,
lighter PS2 room assets, streamed movies and VMU saves adapt it to Dreamcast hardware.

**[Download the latest GDEMU test build](https://github.com/lamb2k/re4dc/releases/latest)** ·
[Known issues](port/dreamcast/docs/KNOWN_ISSUES.md) · [Roadmap](port/dreamcast/docs/D367_THIRTY_FPS_ROUTE.md) ·
[Port notes](port/dreamcast/README.md) · [Build the port](port/dreamcast/CONTRIBUTING-PORT.md) · [Decompilation](docs/DECOMPILATION.md)

## Contributing

One command builds your own program and puts it on the latest test disc: `bash port/dreamcast/contrib.sh`.
See [CONTRIBUTING-PORT.md](port/dreamcast/CONTRIBUTING-PORT.md); contributors and their coding agents should then read
[CLAUDE.md](CLAUDE.md) or [AGENTS.md](AGENTS.md) (section "Outside contributors start here").

## Playing

The latest build is console test 14 (test 13 plus a disc read fix for the GDEMU freezes and crashes, the village textures kept in graphics memory, far fewer disc reads on the farm, and less work per frame). Desktop packages will return with a later test build;
until then, play the console test in Flycast. Extract the complete package:

| System | Download | Launch |
| --- | --- | --- |
| Dreamcast / GDEMU | Console test ZIP (`RE4DC-Console-Test-...-GDEMU.zip`) on the [latest release](https://github.com/lamb2k/re4dc/releases/latest) | Copy the four files inside `gdemu` into a new numbered SD card folder. |

The release page also has the test build checksums (`SHA256SUMS.txt`), the test notes, the Build-Assets zip for
contributors (see Contributing), a second DreamShell test disc for [#28](https://github.com/lamb2k/re4dc/issues/28)
and the benchmark disc (below).

### Benchmark disc (not the game)

`RE4DC-Benchmark-NOT-THE-GAME-...-GDEMU.zip` on the release page is a separate disc that only measures speed on a
real console. It cannot be played: no title menu, no New Game, no saves, and it does not touch your VMU. A red
"BENCHMARK DISC - NOT THE GAME" banner stays on screen, and the GDEMU menu lists it as
"RE4DC BENCHMARK (NOT THE GAME)". It runs two scripted scenes by itself (the village by the burning cross, then the
first house at its back window) and ends on a results screen; a full run takes about 4 minutes.

To report, open a new issue titled "Benchmark results" with a sharp photo of the results screen, the CODE line typed
out, your console region, how you ran it (GDEMU, another drive emulator, or a burned disc) and your video cable.
The README inside the zip explains each number. Flycast runs it too, but emulator numbers are not console numbers.

Already have Flycast? Open `gdemu/disc.gdi` from the console test ZIP, keeping all track files beside it.
For GDEMU, keep filenames unchanged and save any card-manager changes before ejecting the card.
No BIOS or personal VMU saves are included; keep your existing saves separately.

| Action | Dreamcast pad |
| --- | --- |
| Move | Analog stick |
| Aim / fire | Hold R, press A |
| Action / talk / pick up | A |
| Run / cancel | B |
| Knife | L |
| Inventory | Y |
| Pause / options | START |
| Speed display: Off → On screen | Hold R, press START |

Options has the Frame pacing row (Fast is the default) and the Rendering row: Standard (the default, the full
640x480 picture) or FSAA, which smooths edges by drawing twice the pixels and is slower in busy scenes. FSAA lasts
until the console is switched off; every boot starts in Standard.
The speed display shows the frame rate and game speed on screen; it is off unless you switch it on.
The VMU in controller slot 1 shows Leon, Ashley, Hunnigan and Luis pages.

## Status and limitations

**Console test 14, October 16, 2026:** the game plays to the end of chapter two, part one
(the lake and the boat ride, the wolves, the El Gigante fight, finding Ashley and the chapter results),
up to a **Coming Soon** screen. This is a prerelease, not the complete game.

Recent progress:

* Test 14: a disc read fix for the GDEMU freezes and crashes ([#27](https://github.com/lamb2k/re4dc/issues/27); please confirm on a console); the village keeps all its textures in graphics memory; the farm (r103) reads the disc far less; less work per frame.
* Test 13: the PS2 enemy rules in every chapter 1 room, with at most 6 villagers active at once; PS2 room
  objects from r102 to r11b with the GameCube breakable boxes (no more dark debris); the PS2 Ashley; less work per
  frame in the village; fewer disc reads in r103 and r100 after the village.
* Test 12: PS2 models for the room objects in the first two villages, the items you pick up, the villagers' caps
  and the merchant; a brighter Leon; at most 6 villagers attack at once; the radio call crash is fixed
  (confirmed on a real console).
* Fixes for the random console crashes and broken textures of test 7 and test 8 (please confirm on a console).
* Doors hold the last picture and fade to black, with the PS2 Loading banner.
* The village fight follows the PS2 rules: fewer villagers at once, new waves when fewer than 5 are left.
* VMU pages for Leon, Ashley, Hunnigan and Luis; the speed display setting is saved.
* PS2 models for Leon in both outfits, the villagers, the animals, El Gigante and the lake monster.
* The bridge door freeze is fixed, confirmed on a real console.

Known issues (full list: [KNOWN_ISSUES.md](port/dreamcast/docs/KNOWN_ISSUES.md)):

* **Stability:** random crashes and freezes on GDEMU while a room loads: the cause is found (the Dreamcast system
  library could take an old "disc read finished" signal and use half-read data); the fix comes in test 14 and needs a
  console check ([#27](https://github.com/lamb2k/re4dc/issues/27)). The memory corruption crashes of tests 7 and 8
  were fixed in test 9 (needs a console check). A few menu actions can stop the game;
  the r100 cliff cutscene is skipped (test 12).
* **Picture:** some textures are missing; water, ripples and shadows are incomplete; the villagers are not lit by
  the scene (Leon is, since test 12); the night lake has no torch flames or rain.
* **Sound:** the rifle sound is lower quality.
* **Performance:** below the 30 fps / full speed target; pauses when entering rooms.

## Development

The GameCube C/C++ builds for SH-4 with KallistiOS. Dreamcast code replaces graphics, audio, disc and
memory-card services; offline tools convert room worlds, characters and textures from original data.
Game data is not committed. Rendering changes must preserve gameplay, checked with matching logic traces.

<p>
<img src="docs/images/dev/ganado-ps2-look.jpg" width="49%" alt="Ganado model from the PS2 version, prepared for the Dreamcast">
<img src="docs/images/dev/r104-world-sheet.jpg" width="49%" alt="r104 world rebuilt from PS2 room data, review sheet">
</p>
<p>
<img src="docs/images/dev/prompt-glyphs.jpg" width="49%" alt="The game's button-prompt glyphs, extracted for the native UI renderer">
<img src="docs/images/dev/manual-vq.jpg" width="49%" alt="Player's Manual page: original texture against PowerVR VQ">
</p>

Asset work: a PS2 Ganado, the r104 world, button glyphs and a Player's Manual texture before/after VQ compression.

Start with the [build recipes](port/dreamcast/tools/d367/README.md),
[room coverage](port/dreamcast/docs/R4_FIRST_STAGE_GAP_AUDIT.md) and [engine overview](docs/overview.md).
Contributions branch from `dreamcast-port`: one change per PR, relevant before/after checks, no game data.

## Pictures

Captured in Flycast from the play builds.

<p>
<img src="docs/images/01-intro.jpg" width="32%"> <img src="docs/images/02-radio.jpg" width="32%"> <img src="docs/images/03-forest.jpg" width="32%">
<img src="docs/images/04-village.jpg" width="32%"> <img src="docs/images/05-farm.jpg" width="32%"> <img src="docs/images/06-woods.jpg" width="32%">
<img src="docs/images/07-cutscene.jpg" width="32%"> <img src="docs/images/08-vmu-save.jpg" width="32%"> <img src="docs/images/09-r104.jpg" width="32%">
<img src="docs/images/10-mendez.jpg" width="32%"> <img src="docs/images/11-chapter-end.jpg" width="32%">
</p>

## Reporting bugs

[Open a Game bug issue](https://github.com/lamb2k/re4dc/issues/new/choose) with the build, room/chapter,
steps to reproduce, system (Flycast or Dreamcast), and a screenshot or video. On Windows, attach the
newest game log from `logs/`. For a console crash, include the Frame pacing setting and a clear photo
of the complete diagnostic screen. One bug per issue.

## Credits

Built on the [RE4 GameCube decompilation](docs/DECOMPILATION.md),
[KallistiOS](https://github.com/KallistiOS/KallistiOS) and [Flycast](https://github.com/flyinghead/flycast).
Third-party code in the program and its licences: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
An independent fan project for research and preservation, not affiliated with Capcom, Sega or Nintendo.
Resident Evil is a Capcom trademark; game code and data belong to their owners. Project tools and
documentation are [CC0](LICENSE).
