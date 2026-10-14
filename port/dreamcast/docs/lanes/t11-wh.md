# Test 11 item E: PS2 world holes in r117 / r119 (lane t11-wh, 2026-10-14)

Knobs (worldhole.mk, both default 0): `WORLD_HOLE_DIAG=1` (test only: per-part refusal reason, WHD / WHDABORT /
WHDSUM lines) and `WORLD_HOLE_FIX=1` (render only: a translucent actor part that finds the frame queue full is
dropped alone instead of aborting the frame; WHFIX lines). Recipe: `WORLD_HOLE_FIX=1`.

**Cause** (Flycast count, test 10 recipe + WORLD_HOLE_DIAG, warp segments ch21 and g3): every refused PS2 world
part is reason "aborted". `re4dc_actor_submit` (native_actor_fast.cpp:4191) -> `defer_part` finds the frame queue
(frame_storage 26,624 B shared with the UI quads + the 8 KiB model spill) full with ~104-110 queued translucent actor
parts, sets `stream_aborted`, the frame is not presented and every later PS2 world PT / TR part is refused.
No "full" (model packet store), "tex" (texture not resident), "notready" or "storage" refusal was seen in r117,
r119 (g3 fight, audit r119-st warp) or r118 / r11a. So no packet-store reserve and no world-texture VRAM reserve is
needed for the holes; the r119 fragmented-VRAM evict-retry churn (36 retries on the r119-st warp, all loads succeed,
TEXCHK fails=0) is the UI_FRAG_WINDOW lane's.

| Scene (Flycast count) | knob off | WORLD_HOLE_FIX=1 |
|---|---|---|
| r117 entry (ch21): world TR parts refused | 308 in 7 frames (up to 55 of 66 per frame) | 0 |
| r117: scene frames not presented | 193-197, 233-236 (9) | 193-196 (4, the room-load window, also in the off arm) |
| r119 Gigante fight (g3): world PT/TR parts refused | 2,211 in 61 frames (frames 682-748) | 0 |
| r119: frames not presented | 68 | 1 (frame 1478) |
| actor TR parts dropped instead | n/a | r117: 9-39 per frame in 6 frames; r119: up to 139 per frame, 5,217 in frames 681-750 |

What is left: in those frames some translucent actor parts (El Gigante / Ashley) are missing for about a second
instead of the whole frame freezing with holes in the world. Removing that needs a bigger frame queue (r119 asks up
to ~16.7 KB more per frame: a heap cost, not taken here).

Gates: knob-off identity (t11whkP vs t10stP PASS); H2 trace pair wh-h2k2 (t11whkT) / wh-h2t (t11whtT, WORLD_HOLE_FIX=1),
_end 8c40927c both, stop 4700: STRICT (4702 compared) + decisions MUST-IDENTICAL, s30 340/340 both, 0 overruns;
TEXCHK PASS + LEON-GC PASS on wh3-g3-fix (r11a/r119/r118) and wh3b-ch21-fix (r117); PT-BLEND PASS on r11a/r119
(r118 and r117 log no PT headers: NODATA in both arms). Evidence: C:\Flycast-Evidence\re4-dreamcast\t11-20261014\wh*.
