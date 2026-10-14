RE4 Dreamcast test 11, source SHA_PLACEHOLDER (2026 10 14)

Extract the gdemu folder and use its four disc files with your usual GDEMU setup.
Flycast can open gdemu/disc.gdi directly (if menu or popup text looks broken
in Flycast, use its per-pixel renderer setting). This build follows test 10
and plays to the end of chapter two, part one.

Known issues: https://github.com/lamb2k/re4dc/blob/dreamcast-port/port/dreamcast/docs/KNOWN_ISSUES.md

New in test 11 (everything else is the same as test 10):
* Leon is lit by the scene's lights. He reads darker than before, and his
  radio call portrait and inventory picture are too bright; both are being
  tuned for test 12.
* Leon and the villagers cast shadows again.
* Enemy placement in r100, r101, r104, r108, r11a and r11b follows the PS2
  version.
* The speed display is off unless you switch it on (hold R and press START: Off or
  On screen). It no longer uses the VMU; the VMU keeps its Leon, Ashley, call and
  Luis pages.
* Torches glow again, and r11b's rain falls as light streaks like on the PS2.
* Room effects follow the PS2 version.
* Black walls and floors in chapter 1 and 2-1 rooms are lit the way the
  GameCube lights them (not yet in r119).
* Missing pieces of the world (r117 entrance, the El Gigante fight) are drawn.
* The first village (r100) uses its PS2 colours and see-through overlays.
* Missing textures are back: the chapter 2-1 results picture, the r106 bats,
  a dark block in r119 and a texture at the village bell.
* The lake ripples stay on top of the water.

Please tell us about any crash, freeze or missing texture, and where. Photos
help a lot.

Source: https://github.com/lamb2k/re4dc/commit/SHA_PLACEHOLDER
