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

## Numbers (image, build, evidence)

## Ready to land
