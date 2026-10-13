# Known issues

The official list of known problems in the public test builds. Updated with each test release.
Report new problems with the [bug report form](https://github.com/lamb2k/re4dc/issues/new/choose);
please name the build, real console or emulator, and where in the game it happened.

Last updated: October 13, 2026. The current public build is console test `c29c4bf5` (r22j test 7).
Test 8 (`d4bc5f45`) is withdrawn while test 9 is prepared.

Status: **Fixed in test 9** = fixed and checked on our side, waiting for test 9 to ship.
**Investigating** = reproduced or being traced. **Open** = known, not yet worked on.

## Stability

| Problem | Builds | Status | Report |
| --- | --- | --- | --- |
| Random crashes on a real console, often in the village or shortly after a room loads (memory corruption) | test 7, test 8 | Fixed in test 9 | [#23](https://github.com/lamb2k/re4dc/issues/23), [#26](https://github.com/lamb2k/re4dc/issues/26) |
| Opening the attaché case and pressing B twice stops the game | test 8 | Investigating | |
| Changing the Rendering level sometimes crashes a few seconds later | test 8 | Investigating | [#26](https://github.com/lamb2k/re4dc/issues/26) |
| Loading a save and then starting a New Game shows an error | test 8 | Investigating | [#26](https://github.com/lamb2k/re4dc/issues/26) |
| Freeze in the cabin | | Investigating | [#24](https://github.com/lamb2k/re4dc/issues/24) |
| GDEMU disc problem | | Investigating | [#25](https://github.com/lamb2k/re4dc/issues/25) |

## Picture

| Problem | Builds | Status | Report |
| --- | --- | --- | --- |
| Leaves, fences and tree branch tips draw as solid shapes on a real console (fine in emulators) | test 8 | Fixed in test 9 | [#26](https://github.com/lamb2k/re4dc/issues/26) |
| Blank screen on door transitions | test 7, test 8 | Fixed in test 9 | |
| The item name disappears when its menu opens in the inventory | test 7, test 8 | Fixed in test 9 | |
| Some textures are missing or corrupted | test 7, test 8 | Open | [#26](https://github.com/lamb2k/re4dc/issues/26) |
| The on-screen speed display is cut off by the border at the Quality rendering level | test 8 | Open | [#26](https://github.com/lamb2k/re4dc/issues/26) |
| Leon and most villagers are not lit by the scene's lights | test 8 | Open | [#26](https://github.com/lamb2k/re4dc/issues/26) |
| Leon switches back to the GameCube model after the boat | test 8 | Open | [#26](https://github.com/lamb2k/re4dc/issues/26) |
| Water, puddles and lake ripples are missing | test 7, test 8 | Open | [#19](https://github.com/lamb2k/re4dc/issues/19), [#26](https://github.com/lamb2k/re4dc/issues/26) |
| Shadows draw incorrectly | test 7 | Open | [#20](https://github.com/lamb2k/re4dc/issues/20) |
| Curtains in the first house have no texture | test 8 | Investigating | |

## Sound

| Problem | Builds | Status | Report |
| --- | --- | --- | --- |
| The rifle sound is lower quality | all | Open (memory limit) | |
| The chapter results music is silent on the third results screen | all | Open | |

## Performance and loading

| Problem | Builds | Status | Report |
| --- | --- | --- | --- |
| Below the 30 fps / full speed target, slowest in the village fight | all | In progress | |
| Pauses when entering rooms | all | In progress | |

The game currently ends at a **Coming Soon** screen after chapter 2-1. See the
[disc 1 route](DISC1_ROUTE.md) for the rooms still to come.
