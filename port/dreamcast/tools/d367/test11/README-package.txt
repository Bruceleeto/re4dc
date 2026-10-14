RE4 Dreamcast test 11, source SHA_PLACEHOLDER (2026 10 14)

Extract the gdemu folder and use its four disc files with your usual GDEMU setup.
Flycast can open gdemu/disc.gdi directly. This build follows test 10 and plays
to the end of chapter two, part one.

Known issues: https://github.com/lamb2k/re4dc/blob/dreamcast-port/port/dreamcast/docs/KNOWN_ISSUES.md

New in test 11 (everything else is the same as test 10):
* The speed display no longer uses the VMU: hold R and press START to switch
  it Off or On screen. The VMU keeps its Leon, Ashley, call and Luis pages.
* Black walls and floors in chapter 1 and 2-1 rooms are lit the way the
  GameCube lights them.
* Missing pieces of the world (r117 entrance, the El Gigante fight) are drawn.
* Torches glow again, and r11b's rain falls as light streaks like on the PS2.
* The first village (r100) uses its PS2 colours and see-through overlays.
* Fixes missing textures: the chapter 1-2 and 2-1 results pictures, the r106
  bats and a texture at the village bell; less texture memory trouble.
* The lake ripples stay on top of the water.

New in test 10:
* Leon keeps his PS2 model after the boat ride and in every hand pose.
* Leon's face and hair textures are sharper.

Please tell us about any crash, freeze or missing texture, and where. Photos
help a lot.

Source: https://github.com/lamb2k/re4dc/commit/SHA_PLACEHOLDER
