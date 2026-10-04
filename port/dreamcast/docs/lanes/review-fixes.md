# Lane review-fixes (2026-10-04)

Branch `lane/review-fixes-20261004`, from dreamcast-port 80912a72. Written in a cloud session with no SH-4 toolchain,
no Flycast harness and no private assets: host tests only. **Nothing here is landed.** The local session builds,
gates and lands it (or sends it back), then cuts the next play disc (r21u) from the landed tip.

Source: the 2026-10-04 review of the previous 24 hours (findings in the route doc, "2026-10-04 review"). The user
asked for these fixes as one batch so the target gates run once.

## Patches

| # | Files | What | Play image |
|---|---|---|---|
| 1 | `game/platform/include/texpack_index.inc`, `game/platform/native_ui.cpp`, `room/texture_package.{hpp,cpp}`, `tests/texpack_index_host.cpp` | TEX_PACK retry policy. Init attempts after a read error are spaced in UI frames (`find(..., frame)`): 3 attempts 30 frames apart, then one every 300 frames, and at once after a room load. A burst of lookups in one frame (a preload) spends one attempt, not all three, and the first room after boot (which no room leave re-arms) recovers too. A pack shorter than its header is INVALID (new `RangeRead::short_file`), not a transient error forever. A lookup's index sector that failed is re-read at most once per 30 frames (was every use, one log line each). | Changes (TEX_PACK=1 is in the recipe). Success path unchanged: no read error, same reads in the same order |
| 2 | `game/platform/native_actor_fast.cpp` | TA_HASH covers the actor fast path's whole meshlets (`emit_meshlet<true>`: Part::whole, the common direct case, and the ONE_SUBMIT window). 16f0da96 hashed `emit_sq` strips and `re4dc_ta_put` only. Words hashed as sent: the cache entry with its flags word from index bit 7. | None (TA_HASH=0 compiles it out) |
| 3 | `game/platform/native_static.cpp` | `#ifndef RE4DC_SS_UI_ORDER` -> `#error`: the inventory fix's exclusion can no longer compile out silently when subscreen.h is not force-included (the first 6819f3a2 prototype did). subscreen.mk is included unconditionally and always defines it. | None |
| 4 | `tools/d367/build-r21.sh` | Fails when a recipe or caller knob is read by no makefile (assigned, expanded, `ifdef` / `ifndef` / `origin`). Drops the five dead recipe knobs COARSE_WORLD_LAYERS, MOTION_HASH, NATIVE_STATIC_PROBE_SKIP, PS2_SOURCE_SPANS and SOURCE_CENSUS (all 0, read by nothing; checklist step 7 lists them as unlanded or superseded). | None expected (the removed names reached no makefile) |
| 5 | `tools/d367/route/route-build.sh` | A tree with `game/knobs.mk` must leave `resolved-knobs.txt` (fails otherwise, as 8f34aa63's message said); an older control tree still only warns. | None |

## Verified here

- `python3 -m unittest tests.test_texpack_index`: 5/5. The host test (texpack_index.inc compiled unchanged, also
  with `-Wextra -fsanitize=address,undefined`) adds SPACED_RETRY, FRAME_WRAP, FIRST_ROOM, RETRY_LOG, SHORT_FILE and
  the spaced LOOKUP_SECTOR_READ cases; the existing transient-header/index cases now wait the 30-frame spacing.
- The knob check passes the trimmed recipe (217 knobs) with the usual overrides (PACE_MODE, DBG_WARP, QUALITY_PICKER,
  PC_SAMPLER_BYTES, TA_HASH, ...) and rejects a misspelled one (MESH_CLIP_LAEN). `bash -n` on both scripts.
- Full host suite: no new failures (the 16 pre-existing ones stay).
- Not compiled for SH-4: native_ui.cpp, native_actor_fast.cpp, native_static.cpp, texture_package.cpp.

## Gates for the local session (one build/gate cycle)

1. Build the play recipe (build-r21.sh via route-build.sh). The knob check must pass. resolved-knobs.txt equals the
   80912a72 build's.
2. Identity:
   - TEX_PACK=0 build of this branch vs 80912a72: .text/.data/overlay identical (patches 1-5 are guarded or compile-time
     only there).
   - Play recipe with TA_HASH=0: only native_ui.o and texture_package.o differ from 80912a72's (patch 1).
3. TA_HASH=1 builds with zero missing symbols; two runs of one fixture give identical `ta_hash:` lines. Optional:
   ACTOR_VTX_KERNEL=2 (the AVK self-check) with TA_HASH=1 still passes.
4. TEX_PACK fault runs (r100 route fixture with the title-c14/invfix pack):
   - TEX_PACK_FAULT=1: one "read error ... next attempt in 30 frames", then "tex pack: ... count=... (after read
     errors)" within ~30 frames, textured.
   - TEX_PACK_FAULT=3: three fast attempts, then the 300-frame attempt recovers without a room change.
   - A truncated dc/tex.pak (e.g. 100 bytes): one "INVALID: file shorter than its header" line, per-file loads.
5. STRICT on the play recipe vs the 80912a72 build (H2 1450..1569 and the whole r100 room, as for 7cbea8e7), route
   checks r100 calls / r101 bell / r103 entry: HALT 0, MISSING 0, upload failures 0.
6. The new play-disc rule: inventory open/close in r100 and r104 (route-play-invfix-r100-r2 / -r104-r2 pattern:
   matching restore hash, capture shows the case, items, menu bars and Leon preview).
7. Land on dreamcast-port with the gate evidence in the commit messages, then cut r21u per the checklist.
