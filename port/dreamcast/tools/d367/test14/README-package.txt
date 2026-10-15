RE4 Dreamcast test 13, source SHA_PLACEHOLDER (2026 10 15)

See Known Issues: https://github.com/lamb2k/re4dc/blob/dreamcast-port/port/dreamcast/docs/KNOWN_ISSUES.md

Extract the gdemu folder and use its four disc files with your usual GDEMU setup.
Flycast can open gdemu/disc.gdi directly (if menu or popup text looks broken
in Flycast, use its per-pixel renderer setting). This build follows test 12.2
and plays to the end of chapter two, part one.

New in test 13:
* Enemies in chapter 1 follow the PS2 version's rules in every room: which
  villagers are there at the start, when more arrive, and the extra group in
  the village square. At most 6 villagers are active at once in any room; the
  others wait and join as villagers fall, so every villager still appears and
  the kills, waves and events are unchanged.
* Fixed: broken boxes and barrels no longer leave dark debris in the rooms
  after the village. Breakable boxes and barrels use the GameCube models
  everywhere; the other room objects from r102 to r11b (doors, gates, racks,
  the floating islands, the r119 tree and more) use their PS2 models and
  pictures.
* Ashley uses her PS2 model (with a resting face; her GameCube facial
  expressions are not shown yet).
* The village (r101) does less work each frame: the doors, windows and racks
  that stand still are drawn together with the village itself until something
  moves them, and a few other parts of the frame are quicker.
* r103 after the village and r100 after coming back from the village keep
  their textures in graphics memory: textures are loaded when the room starts
  instead of during play, so there are fewer disc reads and fewer missing
  effect pictures right after the door.
* r107 hides the scenery groups the PS2 version hides in each area.

Known issue from test 12, unchanged: the cutscene at the r100 cliff (after the
first house) is skipped; the game goes on normally after it.

Please tell us about any crash, freeze or missing texture, and where. Photos
help a lot.

Source: https://github.com/lamb2k/re4dc/commit/SHA_PLACEHOLDER
