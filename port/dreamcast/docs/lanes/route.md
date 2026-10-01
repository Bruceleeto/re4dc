# Lane route (coordinator): make r106 playable

Rules: port/dreamcast/docs/D367_WORKSTREAMS.md. Branch lane/route, tree /root/work/lanes/route, evidence /root/probe/lanes/route.

## Goal
The play build continues past r103: r103 -> r106 (chapter 1-1 end), following R4_FIRST_STAGE_GAP_AUDIT.md "Full stage-1 route".

## State and next step
`assets.sh discover r106` (2026-10-01):
- em29 / em2e: lint value-init (`new (em) cEmXX();`), not in MODULES / modules.cpp / the ENEMY_DEMAND audit list.
- The room container st1/r106 is not prepared.
- Event r106s00 (4,268,192 B, 165 assets) has no route movie and no prepared evd.
- Heap 4: 4 enemy archives, worst case 1,524,352 B, no measured budget yet.

## Progress 2026-10-01

- **em29 (bats) and em2e (crawlers) are in the image** (ebde74a5). Changes:
  - `new (em) cEmXX;` off the GC (value-init zeroed the subArc);
  - em29's slot scan uses `EmMgr.workAt` (sparse slots);
  - wired by `assets.sh discover r106 --wire` (MODULES, MODULE(27, em29), MODULE(38, em2e), the ENEMY_DEMAND
    audit list).

  The play recipe + DBG_WARP=1 builds (out-r1). It has the same 4 UNRESOLVED stubs as r21k pw8w. The image is
  +16,192 B (text +15,872, data +160, bss +160), so heap 4 is ~16 KB smaller in every room.
- **Room container.** The GC debug disc's St1/r106.das (3,880,960 B, sha 8cc9473e..) is the same source as the
  mirrors (r103.das byte-identical to frontier iso-src). `le_mirror.py <src> <dst> --native-rooms` converts it
  (62 report entries, none incomplete): r106.dar 8,791,072 B, r106.arc 4,910,112 B. That is too big to load:
  r103's uncompacted 4.8 MB .dar failed until W8b compacted it to 1.45 MB.
  Next:
  - a compact-room contract for r106 in prepare_native_ui.py ROOM_CONTRACTS;
  - release the GC scenery BINs the PS2 world replaces (room_smd.py release);
  - measure the loaded size.

  Output (rebuildable, private): /root/probe/lanes/route/mirror-r106. Source: /root/probe/lanes/route/iso-src.
- **Event r106s00.** The PS2 movie archive (BIO4MOV.AFS) has r106s00.sfd + .evd, and a movie for all 46 stage-1
  events. The route-movie path (ROUTE_MOVIES, tools/convert_route_movies.py) can present it, skipping the
  4,268,192 B evd. Needs: add r106s00 to the converter's names, a call site in src/st1/r106.cpp (as r100/r101),
  and staging.
- **Build note.** `make` breaks on the store path's space ("Game Dev"). Pass ASSETS=/root/probe/lanes/play-actor-bundle
  (a symlink to re4-assets-private/play-actor-bundle-20260928).

## Progress 2026-10-01 (room size)

- **r106 room container fits like r103's.** The resident archive (heap 4) goes from 4,910,112 to 1,611,200 B (r103 1,455,456;
  r100 1,918,528). The container .dar is 5,492,160 B. Recipe (private outputs, rebuildable, under /root/probe/lanes/route):
  ```
  echo st1/r106.arc > r106-tex.manifest
  python3 tools/prepare_native_ui.py iso-src r106-tex.manifest tex-r106          # 127 native images
  python3 tools/prepare_native_ui.py --compact-room iso-src/st1/r106.das --compact-room-mips     --textures tex-r106 --output w-r106c                                          # 4,910,112 -> 3,879,136, 117 identities
  python3 tools/convert_room_bins.py pkg-r106/MAINSCENARIO.re4mesh --owner 0xff --smd iso-src/st1/r106.das     --lod --lod-min-gain 0.4 --lod-max-levels 4 --lod-eps 24,48,96,192,384 --lod-share --class-auto --color prelit
  python3 tools/room_smd.py release w-r106c/r106.{dar,arc} pkg-r106/MAINSCENARIO.re4mesh.json rel-r106/st1/r106.{dar,arc}
  ```
  All 87 scenery BINs released; check passes (other slots unchanged). sha256: package 67c20da2.., r106.dar c55fdfc0..,
  r106.arc dd005831...
  - `prepare_native_ui.py`: ROOM_CONTRACTS r106 = 55 slots, SMD#4, EFF#7/#42, ITM#9, model TPLs #47/#49/#51 (r101's layout).
  - `convert_room_bins.py --color prelit` (new CLI option; default `oct` unchanged): r106 has more than 16 CLR0 values,
    which the oct palette can't hold. Under PS2_WORLD_ROOMS=2 this package is the release identity and the
    open-failure fallback only (the PS2 world opens first and the scenery package is skipped).
- **Runtime:** one shared room list, `re4dc_ps2_world_room()` (native_static.cpp), now r100/r101/r103/r106, used by
  the =2 preload and native_ps2_world.cpp's covers(). Default image unchanged (PS2_WORLD_ROOMS defaults 0). out-r2
  builds with the play recipe + DBG_WARP=1, the same UNRESOLVED list as out-r1.
- **Lighting:** the r106 PS2 world package comes from the ps2rooms lane, relaunched 2026-10-01 on the user's PS2-pattern
  lighting decision (prelit, 0 runtime ms, enhanced for DC). Until it delivers, staging uses its authored package
  (ps2rooms-20260930/out/r106).
- **r106s00 route movie** (chapter 1-1's end): r106.cpp presents it through RouteMoviePlay(0x10600) like r101's events (ROUTE_CUTSCENES.md row); r106.o gets the route-movies header; convert_route_movies.py names it. Converted into the shared movie folder (/root/probe/d367-agents/cutscenes/movies-288x192-full/r106s00, index merged, not replaced): 288x192, 1,738 frames, 58.0 s, seq 12,184,020 B (sha 1e5e3b02..). out-r4 builds (play recipe + DBG_WARP=1), same UNRESOLVED list.
- **r106 reached in game through the r103 door (2026-10-01).** Image: route-build.sh r6 (play recipe + PACE_MODE=fast
  DBG_WARP=1 PC_SAMPLER=1 ARENA_FIT_KOS_BYTES=180224; ELF 8832fa42), fixture tour/route-rel-r103-r106-walk-pw.json (preset
  r103-r106-door --door; r106 PS2 world = the ps2rooms authored package), run scenarios/route-r106w1 (240 s, HALT 0, MISSING 0):
  - Door taken at vbl 1602, r106 entered vbl 1649; room identities ok (117, archive 1,611,200 B); PS2 world opens
    (1,038,208 B, heap 4 5,445,600 -> 4,407,296 free); scenery package skipped; route movie 10600 owns the event
    (3,932,160 B em12 reservation released). Ran to frame 3,360 (deadline) with no HALT.
  - Open: VRAM free at entry 69,760 B (r103's room set still resident: no r106 VQ overlay yet); 156 of 212 source-OT
    model parts rejected (to check against r103); the closet event (area 2) not walked yet.
  - The direct warp start (preset r106-entry, scenarios route-r106e1/e2/e3) does NOT work: every disc open fails after
    the first r106.dar read (KOS heap and the disc layout are fine: a KOS-style Joliet walk finds every file; +32 KB
    KOS heap changes nothing). The door route does not hit it, so the warp-only path is parked; use the door walk.
  - Fixture maker fix: door views pass warp.py options (route-r103-r106-walk = r103-r106-door --door); the first
    r103-r106-door fixture had no door actions (single-use name kept).
- Next: r106 PS2 world from ps2rooms' `--color-light ps2` bake (TEV x4), r106 VQ overlay, the closet event + r106s00
  movie run, heap-4 / hw ms measurement.

## Numbers (image, build, evidence)

## Ready to land
