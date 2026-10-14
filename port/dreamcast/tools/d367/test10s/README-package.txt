RE4 Dreamcast r22j test 10, source SHA_PLACEHOLDER (2026 10 14)

Extract the gdemu folder and use its four disc files with your usual GDEMU setup.
Flycast can open gdemu/disc.gdi directly. This build follows test 9.1 and plays
to the end of chapter two, part one.

Known issues: https://github.com/lamb2k/re4dc/blob/dreamcast-port/port/dreamcast/docs/KNOWN_ISSUES.md

New in test 10 (everything else is the same as test 9.1):
* Leon keeps his PS2 model after the boat ride and in every hand pose.
  Before, he could switch to the GameCube model.
* Leon's face and hair textures are rebuilt from the original GameCube
  textures, so his face is sharper.
* If a character animation read from the disc fails, the game now waits a
  little before trying again instead of retrying at once.

New in test 9.1:
* Fixes a memory leak when leaving rooms that the test 9 reset fix caused.

Please tell us whether Leon ever looks different from the PS2 model, how his
face looks to you, and whether the game crashes in long play. Photos help a lot.

Source: https://github.com/lamb2k/re4dc/commit/SHA_PLACEHOLDER
