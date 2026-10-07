![RE4 Dreamcast](docs/images/title.jpg)

# RE4 Dreamcast

**An experimental Resident Evil 4 port for the Sega Dreamcast.**

The recovered GameCube code runs the gameplay, collision and enemy AI. A native PowerVR renderer,
lighter PS2 room assets, streamed movies and VMU saves adapt it to Dreamcast hardware.

**[Download r22j](https://github.com/lamb2k/re4dc/releases/tag/play-r22j-audio-performance-20261007)** ·
[Roadmap](port/dreamcast/docs/D367_THIRTY_FPS_ROUTE.md) ·
[Port notes](port/dreamcast/README.md) · [Decompilation](docs/DECOMPILATION.md)

## Playing

Extract the complete package for your system:

| System | Download | Launch |
| --- | --- | --- |
| Windows | [RE4DC-r22j.zip](https://github.com/lamb2k/re4dc/releases/download/play-r22j-audio-performance-20261007/RE4DC-r22j.zip) | Double-click `Play-r22j.cmd`. Includes Flycast and keyboard/DualSense support. |
| Steam Deck / SteamOS | [SteamOS package](https://github.com/lamb2k/re4dc/releases/download/play-r22j-audio-performance-20261007/RE4DC-r22j-SteamOS.tar.gz) | In Desktop Mode, run `play.sh`; uses Flathub Flycast. |
| CachyOS / Arch | [CachyOS package](https://github.com/lamb2k/re4dc/releases/download/play-r22j-audio-performance-20261007/RE4DC-r22j-CachyOS.tar.gz) | Run `./play.sh`; uses native or Flathub Flycast. |
| Dreamcast / GDEMU | [GDEMU image](https://github.com/lamb2k/re4dc/releases/download/play-r22j-audio-performance-20261007/RE4DC-r22j-GDEMU.zip) | Copy `disc.gdi` and all three track files into a new numbered SD-card folder. |

[SHA-256 checksums](https://github.com/lamb2k/re4dc/releases/download/play-r22j-audio-performance-20261007/SHA256SUMS.txt) · [Release notes and verification](https://github.com/lamb2k/re4dc/releases/tag/play-r22j-audio-performance-20261007)

Already have Flycast? Open `disc/disc.cue` from an emulator package and keep its `disc.bin` beside it.
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
| Frame pacing: Smooth → Fast → Off | Hold R, press START |

Fast pacing is the default. A VMU in controller slot 1 shows FPS, game speed, CPU percentage and pacing.

## Status and limitations

**r22j, October 7, 2026:** restores room music in r104/r107 and adds indoor enemy culling
and a CPU optimization. Includes the r22i herb, pickup layering, object animation and movie fixes.
The route extends through r10a; the unfinished r10b door shows **Coming Soon**. This is a prerelease,
not the complete game.

Combined New Game, movie, radio and logic checks pass in Flycast. All three grenade types trigger
their mapped sound sample. The exact GDEMU image boots to the VMU prompt, and every archive member
was hash checked. Continuous playthrough, mixed audio listening and physical Dreamcast acceptance
remain pending. See the [build checklist](port/dreamcast/docs/D367_PLAY_BUILD_CHECKLIST.md).

- **Performance:** below the 30 fps/full-speed target. The separate r22g console test ran the r100
  outdoor fight at about 10 fps and 70% speed; this is not an r22j measurement.
- **Presentation and sound:** some models/effects and textures need work. Rifle sound is lower quality;
  the restored room music and grenade sounds still need listening checks on hardware.
- **Stability:** the r103 hang remains under investigation. If the freeze report appears, attach a photo
  to a bug report.
- **Loading and saves:** room-entry pauses remain. Normal chapter 1-2 key-item pickups and reloading
  a save made inside r106 still need checking.

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
newest game log from `logs/`. For a console crash, include a photo of the crash report. One bug per issue.

## Credits

Built on the [RE4 GameCube decompilation](docs/DECOMPILATION.md),
[KallistiOS](https://github.com/KallistiOS/KallistiOS) and [Flycast](https://github.com/flyinghead/flycast).
An independent fan project for research and preservation, not affiliated with Capcom, Sega or Nintendo.
Resident Evil is a Capcom trademark; game code and data belong to their owners. Project tools and
documentation are [CC0](LICENSE).
