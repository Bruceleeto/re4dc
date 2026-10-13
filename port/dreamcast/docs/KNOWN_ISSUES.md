# Known issues

The official list of known problems in the public test builds. Updated with each test release.
Report new problems with the [bug report form](https://github.com/lamb2k/re4dc/issues/new/choose);
please name the build, real console or emulator, and where in the game it happened.

Last updated: October 13, 2026. The current public build is console test `c29c4bf5` (r22j test 7).
Test 8 (`d4bc5f45`) is withdrawn while test 9 is prepared.

## Status at a glance

| Status | Meaning | Count |
| --- | --- | --- |
| ✅ Confirmed fixed | Fixed and confirmed on a real Dreamcast | 0 |
| 🟢 Fixed, needs console check | Fixed and checked in our tests; waiting for a console report (see the checklist below) | 3 |
| 🟢 Fixed in test 9 | Fixed and checked in our tests; the problem was not console-only | 2 |
| 🛠️ In progress | Being fixed now | 4 |
| 🔍 Investigating | Being reproduced or traced | 4 |
| ⏸️ Open | Known, not yet worked on | 7 |
| ❔ Not reproduced | We could not make it happen; more details welcome | 1 |

## Stability

| Problem | Builds | Status | Report |
| --- | --- | --- | --- |
| Random crashes on a real console, often in the village or shortly after a room loads (memory corruption) | test 7, test 8 | 🟢 Fixed, needs console check | [#23](https://github.com/lamb2k/re4dc/issues/23), [#26](https://github.com/lamb2k/re4dc/issues/26) |
| Changing the Rendering level sometimes crashes a few seconds later | test 8 | 🛠️ In progress: the Rendering option is removed in test 9; the game always uses the full picture | [#26](https://github.com/lamb2k/re4dc/issues/26) |
| Loading a save and then starting a New Game shows an error | test 8 | 🛠️ In progress | [#26](https://github.com/lamb2k/re4dc/issues/26) |
| Opening the attaché case and pressing B twice stops the game | test 8 | ❔ Not reproduced in 8 tries | |
| Freeze in the cabin | | 🔍 Investigating | [#24](https://github.com/lamb2k/re4dc/issues/24) |
| GDEMU disc problem | | 🔍 Investigating | [#25](https://github.com/lamb2k/re4dc/issues/25) |

## Picture

| Problem | Builds | Status | Report |
| --- | --- | --- | --- |
| Leaves, fences and tree branch tips draw as solid shapes on a real console (fine in emulators) | test 8 | 🟢 Fixed, needs console check | [#26](https://github.com/lamb2k/re4dc/issues/26) |
| Blank screen on door transitions | test 7, test 8 | 🟢 Fixed in test 9 | |
| The item name disappears when its menu opens in the inventory | test 7, test 8 | 🟢 Fixed in test 9 | |
| The on-screen speed display is cut off by the border on a real console | test 8 | 🛠️ In progress | [#26](https://github.com/lamb2k/re4dc/issues/26) |
| Leon switches back to the GameCube model after the boat | test 8 | 🛠️ In progress | [#26](https://github.com/lamb2k/re4dc/issues/26) |
| Lake ripples are not visible | test 8 | 🔍 Investigating | [#26](https://github.com/lamb2k/re4dc/issues/26) |
| Curtains in the first house have no texture | test 8 | 🟢 Fixed, needs console check (cause not confirmed) | |
| Some textures are missing or corrupted | test 7, test 8 | 🔍 Investigating | [#26](https://github.com/lamb2k/re4dc/issues/26) |
| Leon and most villagers are not lit by the scene's lights | test 8 | ⏸️ Open | [#26](https://github.com/lamb2k/re4dc/issues/26) |
| Water and puddles are missing | test 7, test 8 | ⏸️ Open | [#19](https://github.com/lamb2k/re4dc/issues/19) |
| Shadows draw incorrectly | test 7 | ⏸️ Open | [#20](https://github.com/lamb2k/re4dc/issues/20) |

## Sound

| Problem | Builds | Status | Report |
| --- | --- | --- | --- |
| The rifle sound is lower quality | all | ⏸️ Open (memory limit) | |
| The chapter results music is silent on the third results screen | all | ⏸️ Open | |

## Performance and loading

| Problem | Builds | Status | Report |
| --- | --- | --- | --- |
| Below the 30 fps / full speed target, slowest in the village fight | all | ⏸️ Open: PS2 enemy and effect reductions under way | |
| Pauses when entering rooms | all | ⏸️ Open | |

## Console checklist for test 9

These fixes can only be confirmed on a real Dreamcast, because emulators draw the old and new versions the same.
If you play test 9 on a console, please report on any of these in the test 9 feedback issue:

1. **Long play in the village and the first house.** Play for 20 minutes or more, through room loads. Any crash screen?
2. **Trees and fences by the first house.** Do branch tips, leaves and fence gaps show the sky or wall behind them, or
   solid blocks?
3. **Curtains in the first house.** Textured or flat?
4. **Speed display** (hold R, press START until it shows on screen). Is the counter fully visible?

An item moves to ✅ Confirmed fixed after a console report.

The game currently ends at a **Coming Soon** screen after chapter 2-1. See the
[disc 1 route](DISC1_ROUTE.md) for the rooms still to come.
