# r22j test 8: release checks (2026-10-12)

Build: origin d4bc5f45, test 8 recipe (t8-build.sh: the test 7 recipe + the Phase 2 knobs, now with UI_FRAG_RESERVE=1).
Evidence: C:\Flycast-Evidence\re4-dreamcast\test8-20261012 (route-r9-* = this image). Work dir: /root/probe/lanes-20261011/test8.

## Fixed during the checks

- **Motion key read retry (issue #25, 72cc87e4).** A console stopped in the intro on `MISSING motion key read`: one
  key read returned an error or came back short, and only `storage reader re-entry` was retried. Any failed or short
  read is now read again up to 3 times (logged `motion key read retry`) before the stop. No knob (error path only).
  `MOTION_READ_FAULT_TEST=<n>` (test only) makes every nth key miss short on its first read so Flycast runs the retry.
- **UI_FRAG_RESERVE (d4bc5f45).** r10b f6a fixture: back in r11b after the chapter end, 7506e95f (512x512) was refused
  15 times to the end of the run with 2.2 MB of the 2.5 MB pool free: 31 small uploads (285 KB), all used by the frame,
  left a largest hole of ~508 KiB. Now the next frame start fences the previous render, releases the cheapest window of
  unpinned uploads (movie_window_release) and holds the block until that texture asks again: refused once, uploaded two
  frames later. An unused hold is dropped after 120 frames or at a room change.
- **VRAM_CENSUS map (ee88e3da, test only).** `vram frag:` lines on the first two refusals: every allocation as
  P (used this frame / leased), U (evictable) or X (no cache entry), with its key.

## Tried and dropped

- **LAKE_RIPPLES=0 bisect:** same 15 refusals. The lake ripples are not the cause (they stay on).
- **VRAM_SPLIT** (small allocations top down, large best fit bottom up): small uploads still scattered (evictions open
  holes everywhere), same 15 refusals, and the r10b 10b20 movie ended terminal=4 (792/800). Not landed.

## Accepted (user, 2026-10-12)

- r100 s30 `heap_before` 207,136 B vs the padded control's 229,568 B: the gap is exactly the r100 crow + dog package;
  s30 plays 340/340.
- r118 em22 41e94bbe (512x256) after r119: requested once, on a transition frame; under VRAM pressure it can miss that
  one frame (r5 / r7 images), and a hold cannot help a texture that is never asked for again.

## Notes

- H2 differs from the padded control only in `af` (render-side texture staging, from tick 1672); with `af` blanked
  decision_cmp is MUST-IDENTICAL over 7256 ticks.
- hw model, test 8 vs test 7: r101 square drawn 67.9 vs 69.7 ms; r100 house 75.5 vs 191.8 ms (one traced frame each,
  the test 7 frame looks like a load spike: no claim). Hardware-model runs never block a release.
