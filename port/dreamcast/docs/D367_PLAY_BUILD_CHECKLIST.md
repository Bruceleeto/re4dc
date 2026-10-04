# D367 play build checklist (user, 2026-09-29)

## 2026-10-04: review follow-ups for the next play disc

Details in the route doc, "2026-10-04: review of 2026-10-03/04". For play discs:
- New rule: every play disc opens and closes the inventory in r100 and r104 ("Play build rules", inventory check).
- r21t GDEMU image: the released zip boots in Flycast (built-in HLE BIOS) from disc.gdi to the VMU prompt, the title
  and r100 gameplay (route doc). GDEMU and a console are still untested.
- After r21u: experiment/supervisor-20261004's code lands default-off (user 2026-10-04; route doc, review section).
- lane/review-fixes-20261004 is LANDED (gates in docs/lanes/review-fixes.md "Landing"): TEX_PACK retry spacing plus
  a preload re-run after the pack recovers (both change the play image's error path only), the TA_HASH
  whole-meshlet hook, a native_static `#error` guard, build-r21.sh failing on knobs no makefile reads (five dead ones
  dropped from the recipe), route-build.sh failing without resolved-knobs.txt and printing link.sh's missing symbols
  (`$O/missing.txt`, copied from the tree's game/obj). r21u is cut from the landed tip b730bf1a
  (step 6: C:/RE4DC-Play-Discs/r21u-title + r21u-gdemu, launcher Play-r21u-Review-Fixes.cmd; every check passed; not
  released).

## 2026-10-04: r21t public play downloads

User-authorized public release:
[play-r21t-inventory-fix-20261004](https://github.com/lamb2k/re4dc/releases/tag/play-r21t-inventory-fix-20261004).
Windows, SteamOS, CachyOS and GDEMU archives package the already verified r21t images. Every archived
file is read back and hash-checked; GitHub asset digests and sizes match the local release manifest.
SHA256SUMS.txt and inline release-note hashes support manual and existing scripted downloads.
The runtime remains 6819f3a2, ELF b9dc7b75819fb03e; packaging fix 0b9f6a35. No game-code rebuild or new
performance claim accompanies publication. The continuous chapter playthrough, GDI boot test,
physical-console acceptance and separate SteamOS/CachyOS runtime checks remain pending.

## 2026-10-04: inventory room-replacement ownership repair

The approved 16f0da96 play code reproduces the broken inventory in r100 and r104 with the title-c14 pack.
SS_PACK=0 reproduces it too. Inventory rigid models carry static_geometry; PS2_WORLD_ROOMS=2 therefore
mistook them for the first room-scene draw and submitted the PS2 world inside SS_UI_ORDER's single TR
stream. This closed that list and sent later UI parts through CLOSED_PASS_KEEP, corrupting the case,
items, menu bars and Leon preview. The missing inventory texture was a separate packaging issue.

native_static now uses the existing re4dc_ss_ui_order owner query to exclude swapped subscreen models
from room replacement. subscreen.mk supplies the existing generated setting to that object. No new
renderer, gameplay change, experimental optimization, or play-recipe knob is introduced.

Validation: the same assets before/after show the inventory restored in both rooms; each 180-second
Flycast run opens and closes it, restores the saved area with the matching hash, and returns to gameplay
with HALT 0 / MISSING 0. The matched source/fix gameplay trace pair passes STRICT for 1,804 r100 frames
(room offsets 0..1803, anchors 182/182), no gaps or duplicates, ACT_CAP=0 / PACE_MODE=off. This trace
covers ordinary gameplay, not the swapped inventory memory; the inventory gate is visual plus restore
checks. Production and traced builds report zero missing stubs.

The new title-invfix pack adds the already recovered cd5691f8-b993e9b1 material (656 bytes); all 3,241
existing package payloads are byte-identical. The production image uses the current play recipe,
DBG_WARP=0 / PC_SAMPLER=0 / GAME_PWC_DIAG=1 / PACE_MODE=fast / PACE_DEBUG=1. The final pack passes two inventory open/close cycles in each room with matching restore hashes,
zero missing packages and zero upload failures. The production title/New Game run completes the three
opening movies (1971/1971, 2360/2360 and 1175/1175 pictures) and reaches r100 gameplay.

The existing chapter-end fixture starts in r106: its ending movie plays 1738/1738, the chapter 1-1
results and Save prompt appear, VMU save and syswrite return 0, and r104 is entered. Its s00 movie
finishes and the expected missed-QTE branch reaches Continue. These checks are separate endpoints,
not a continuous manual title-to-chapter-end playthrough or QTE-success qualification.

r21t is installed locally: C:/RE4DC-Play-Discs/r21t-title/disc.cue and r21t-gdemu/disc.gdi; launcher
D:/RE4DC-Play/Play-r21t-Inventory-Fix.cmd. Runtime source is 6819f3a2; production ELF SHA-256 begins
b9dc7b75819fb03e. CUE disc SHA-256 is 226db5f2b4cadc91ee350b325c6a15db17b1cac463b740d853a44894d324bddf.
The CUE has 458649 logical sectors. The newly authored GDI has 458647 raw 2352-byte data sectors at
LBA 45000; all 1143 file payloads match, with the expected unscrambled boot-program difference.

GDI packaging now accepts INPUT_CHARSET (legacy iso8859-1 default unchanged). The UTF-8 tree extracted
from the tested CUE is packaged with INPUT_CHARSET=utf-8, preserving one legacy text filename that
the first draft re-encoded. Both drafts remain private; only the fully verified UTF-8 image is delivered.
The packager change does not change the compiled game. Final evidence: delivery-report-r21t.json and
r21t-gdemu-utf8-verification.json in the private playable-first directory.
The first route milestone remains title -> r120 -> r100 -> r101 bell -> r103 -> r106 results/save -> r104.
Later emblem/key pickups and full chapter-route acceptance are still unproven; this repair does not
establish 30 fps or physical-console acceptance.

Evidence: private architect-review-20261003/tools/supervisor-20261003/playable-first/; scenarios
route-play-main-r100-inventory-r1, route-play-main-r104-inventory-r1,
route-play-main-r104-inventory-unpacked-r1, route-play-invfix-r100-r2, route-play-invfix-r104-r2,
route-play-inv-control-strict-r1 and route-play-inv-fix-strict-r1. The first repair prototype omitted the
native_static generated-header dependency and compiled the check out; it is retained as a failed check.

## 2026-10-03: native vertex coverage in graphics diagnostics

`TA_HASH` now includes the direct store-queue strips emitted by `vp::emit_sq` (PS2 world/mesh fast path)
and the native actor fast path. Previously both bypassed `re4dc_ta_put`, so matching hashes did not cover
their vertex data. The diagnostic hashes the copied words with the final vertex's EOL flag. Direct
store-queue writes in `coarse.cpp` and `coarse_world.cpp` are still outside this coverage.

This repair compiles out with the normal `TA_HASH=0`. On a standalone ce39455f-based image, fresh
`sup-ps-id-base` vs `sup-ps-sq-off` builds have identical .text/.data/overlay, .bss (803644 bytes) and
`_end` (8c3afffc); only four __TIME__ bytes differ. `sup-ps-sq-t1` with TA_HASH=1 also builds with zero
missing symbols. The enabled hooks ran in the stacked diagnostic route checks, including 3754 matched
r101 frames; the standalone TA_HASH=1 image is build-verified, not separately route-tested.

Evidence: private architect-review-20261003/tools/supervisor-20261003/pass-share/ARCHIVE.md,
sqfix.log, sqfix2.log and tacmp-k.txt. This does not adopt PS2_PASS_SHARE (parked after mixed cost
results), change the play recipe, establish complete TA equivalence against the old baseline, or
claim a performance/physical-console result. Native scene coverage remains under implementation.

Correction (review 2026-10-04): the actor fast path is only partly covered. Its whole meshlets (`Part::whole` ->
`emit_meshlet<true>`, the common case under NATIVE_ACTOR_DIRECT=1, also in the COARSE_ONE_SUBMIT window) still go
to the store queues unhashed, so matching `ta_hash:` lines do not prove matching actor geometry. The hook is on
lane/review-fixes-20261004 (docs/lanes/review-fixes.md), not landed. Merging experiment/supervisor-20261004 would
add MESH_STRIP_LEAN paths that also bypass or misattribute the hash (=1/=3 write the store queues in their own
assembly; =2 hashes a dry-run copy that never reaches the TA).

Goal: one play build that feels like the game from the title as far as it goes (r120 intro -> r100 -> r101 -> r103),
on the fastest measured render pipeline, with every existing fix landed. Update this file with every step (status,
commit, evidence). Do not start a later step's work inside an earlier step. Before calling the build complete, re-run
the unlanded-work sweep (every local tree's files hashed against every dreamcast-port blob) and account for every hit.

## Play build rules (verified 2026-09-29)

- Recipe: `tools/d367/build-r21.sh` plus `DBG_WARP=0 QUALITY_PICKER=0 ARENA_FIT_KOS_BYTES=147456 PACE_MODE=fast
  PACE_DEBUG=1 LOGIC_TRACE=0 GAME_DECISION_TRACE=0 ACTOR_TRANSACTION_DIAG=0`; keep `GAME_PWC_DIAG=1` (an exact logic
  cut; only =2 is test-only). Test spots use a `DBG_WARP=1` twin; the pad fixture works without it.
  Recipe truth (2026-10-03, 8f34aa63): build-r21.sh writes `$OUT/resolved-knobs.txt` (make's own resolved values;
  route-build.sh records its path in programs-route.json): read that, not the make line. MESH_CLIP_LEAN=1 is in the
  play recipe since 2026-10-03 (user; H2 -2.18 hw ms, STRICT, off/on captures); MODEL_DRAW_PLANS is forced to 1 by the D349 renderer-stack
  override in the Makefile.
- Calls and cutscene memory (2026-10-02, r21n play): build-r21.sh sets `SS_PACK=1` (the sub screen packs its
  3 MiB into TA bank 1 instead of releasing ~2.3 MB of room textures per call) and `MOVIE_HEAP_EVICT=1` (a route
  movie short of heap 4 evicts unpinned motion keys; the r100 s30 cliff cutscene failed without it).
- PS2 world packages (2026-10-03, r21o play): play fixtures stage the `--lod-uv-guard 0.002` rebuilds
  (tour/play/title-c13-pw.json; the unguarded LOD shears wall textures). build-r21.sh sets `CLOSED_PASS_KEEP=1`
  (an opaque draw after the translucent list no longer halts; a crash-avoidance fallback with unresolved
  ordering / alpha / depth, not proof of correct rendering: each caller needs a visual gate) and `PS2_PRELOAD_LEAN=1` (PS2 world rooms preload
  the package's textures, not the replaced GameCube scenery's).
- Crowd knobs (user 2026-10-03, implementation handoff WP2): build-r21.sh sets `CROWD_READOPT=2 CROWD_CULL=1
  CROWD_FOGSKIP=1`. Leon re-proves his native-cast records after the r100 s20 cutscene (H2 -7.09 hw ms; the r100
  post-cutscene Leon is now the 4K cast, as in r101/r103); Ganados outside the view or past the fog are not drawn.
  Gate on ed818b8e: STRICT H2 120/120 + r100 1391/1391, r101 bell 120/120 + r101 941/941; route checks r100 calls,
  r101 bell, r103 entry HALT 0 MISSING 0; Leon captures (aim, fire, reload, walk, damage) normal. The recipe image
  equals the gated build (.text/.data/overlay identical, 5 __TIME__ bytes).
- Texture pack (2026-10-03): build-r21.sh sets `TEX_PACK=1`; a play disc stages the pack fixture made by
  `tools/d367/route/pack-fixture.sh tour/play/<fixture> <arm> tour/play/<fixture>-pak.json` (re-run whenever the
  fixture's or the base disc's textures change). Without dc/tex.pak the build loads per file, as before.
  Failure policy (2026-10-03, 766a5fa5; route doc "Pack failure policy"): an absent pack loads per file, which is
  fine only on a loose-file disc. pack-fixture.sh play discs drop the packed loose files, so there a read error
  means no texture until a retry (init 3 times, then once per room load) and an INVALID pack means missing
  textures. pack-fixture.sh (13eaccec) writes verified `<name>.<sha16>.pak` packs with a provenance manifest and
  refuses to overwrite without `--replace`; check a pack with `texpack.py --verify`.
- Benchmark fixtures vs the play image (architect review 2026-10-03). Keep them apart:
  - **H**, the original house timing fixture: unguarded PS2 worlds and the 2,512-entry pack.
  - **H2**: UV-guarded PS2 worlds and the title-c14 pack (3,241 packages), the play image's assets. A diagnostic
    house fixture, not a full play validation. Measured with same-binary late activation (warp.txt
    `late <mask> 1400 0x100`; tools/d367/README.md "Late activation").
  - Neither replaces the route checks of a play disc (r21s and later).
- Inventory check (review 2026-10-04): every play disc opens and closes the inventory in r100 and r104 before it is
  called done (route-play-invfix-r100-r2 / -r104-r2 pattern: matching restore hash, and a capture showing the case,
  items, menu bars and Leon preview). HALT / MISSING counts never open it: the corruption fixed by 6819f3a2 came in
  with ad0c59d0 (PS2_WORLD_ROOMS=2, 2026-09-29) and was very likely in every disc from r21i to r21s, the public
  r21k, r21l and r21m included.
- Crash screen (user 2026-10-02): build-r21.sh sets `CRASH_SCREEN=1` for every play build. Before a console disc
  the build must log 0 misaligned accesses over its rooms (`tools/d367/hwready/route-hw.sh align`).
- Disc: `debug/config.txt` ROOM 0x20 (New Game -> r120 intro), no `dc/quality.txt`, the r100 release (route fix e)
  re-cut from the disc's own r100.dar (A1 blocks + A2 archive; the old A2 dar would drop r100's AICA overlay).
  Two artifacts per disc (route doc "Goals and decision rules", disc artifacts): `<rNN>-title` is the Flycast image (`disc.cue`, one
  MODE1/2048 track of 2048-byte logical sectors); `<rNN>-gdemu` is the GDEMU image (`disc.gdi`, `SECTOR=2352` raw
  sectors, track 3 at LBA 45000). Same data-track sector count (r21s: 458,648); data sector n is at byte n x 2352 + 16
  of track03.bin (GD LBA 45000 + n) and n x 2048 of disc.bin. A Flycast boot of the CUE image does not validate the GDEMU TOC or physical media.
- World: the PS2 world in r100, r101 and r103 through PS2_WORLD_MESH + PS2_WORLD_ROOMS=2 (64-vertex packages; r101
  the adopted world-mesh-r21 package, r100/r103 from tools/ps2_room_r4im.py). The disc must stage
  dc/native/r100|r101|r103/ps2-world.{re4mesh,r4pw} and their dc/tex files (tour/play/*-pw.json); a room whose
  package is missing falls back to its Standard scenery.
- r106 (route lane, landed f66e8c5b, 2026-10-01): the play image reaches r106 through the r103 door. Its disc needs
  st1/r106.{dar,arc} (compact + release), dc/native/r106/MAINSCENARIO.re4mesh (release identity), the PS2 world
  dc/native/r106/ps2-world.* from ps2rooms out/r106-ps2 (`--color-light ps2`, TEV x4) with its tex, the r106 room
  textures, dc/movie/r106s00.seq, and the dc/native/r106 directory (stage-scenario.py creates missing directories).
  tools/d367/route/make-route-fixtures.py writes these fixtures (recipe in docs/lanes/route.md). Open: a direct start
  in r106 (warp or a save made there) fails every disc open after the room read.
- r106 end of chapter 1-1 (route lane, 2026-10-01): also the chapter results pictures (tex-chap01-vq + tex-chap01) and
  the em2a picture (tex-em2a); make-route-fixtures.py sets chap01 / em2a.
- r104 (route lane, 2026-10-01; lane/route d4424cf3, landing pending): the build needs PLAYER_RESIDENT_BYTES=869728 (in
  build-r21.sh) and em13 in MODULES (em10g group). The disc needs:
  - st1/r104.{dar,arc} and em/em13.drs from the r104 AICA build;
  - em/pl08.drs, textures-only (Leon without the jacket);
  - dc/native/r104/MAINSCENARIO.re4mesh and ps2-world.* from ps2rooms out/r104-ps2, with its tex;
  - the tex-r104 / tex-em13 / tex-pl08 pictures;
  - dc/movie/r104s00, s00c, s01, s02, s10, s20 .seq.
  make-route-fixtures.py sets r104, em13, pl08 and r104mov stage these files.

## Steps

| # | Step | Status | Evidence / commit |
|---|---|---|---|
| 1 | MOTION_RESERVE (ambush: cold-clip slots at bind) onto the tip; ambush run | done | 8c000e81: on in build-r21.sh. Knob-off .text/.data == p9w; STRICT vs r20k3w 0..1941; r100-s20 ambush preset (s20 571/571, em21/em2a, post-house call, 5100 frames) no HALT / no OOM; New Game -> r100, r101 entry, r103 entry no HALT. Slabs 2x27584 (55 KB heap 4); the idle script used 0 (its 75 loads were hot clips): the reserve covers player-driven cold clips. Also landed default off: MOTION_USAGE_LOG, HEAP_REPLACE_LOG, HEAP_CENSUS. Follow-up 121fcc4e MOTION_RESERVE_SPILL=524288 (in build-r21.sh): the two slabs thrashed in the r101 fight (net_crc32le 18.85% of non-idle PC samples, ~50 key reloads/s); a cold key now spills into heap 4 while 512 KiB stay free: r101 entry 3480 -> 4413 frames / 200 s (+27%), r100 ambush 0 spills (under the margin, slabs as before), STRICT vs r20k3w 0..1941 with 4 spills taken |
| 2 | Effects: coarse mode hands qualified effects to EFFECT_SPRITES instead of markers; land EFFECT_ROOM | done | fe79a373: COARSE_FX_SPRITES=2 in build-r21.sh (weapon / shot / blood sprites, no opaque markers): r101 kite fight windows (ticks 300..1200) equal to the control, r100 after the call -0.45 ms, first window +62 ms once (correction: the kite fixture's Leon dies ~80 s in, so its later "quiet" windows are the Continue screen; fe79a373's "r101 quiet" figures measured that screen); STRICT 0..1941; knob-off identical. EFFECT_ROOM landed default 0. Found on the way: fbb2ee2e, a short MOTION_FAST_READ (GD DMA in flight) halted "motion key read"; now falls back to the storage reader (forced-short test: no halt) |
| 2b | Room effects in coarse (user 2026-09-29: after 2): EFFECT_ROOM=7 costs +3.4 ms r101 / +3.9 ms r100 and thrashes VRAM in r101 fights (1598 vs 291 loads). Do: hw profile (PC sampler) of the +3 ms; a resident VRAM slab for effect textures; sprite paths for the non-EspCommonTrans classes (r100 leaves d0/4e, light shafts d0/08 Esp08, trails Esp16) | done | Cause (PC sampler + texture counters, 2026-09-29): with EFFECT_ROOM=7 the r101 fight runs 2203 frames / 200 s at 61% idle vs 4413 without (both with MOTION_RESERVE_SPILL); the UI texture cache thrashes (2990 loads / 2239 evictions in 1680 frames vs 766 / 91 in 3960): the room effects add ~1.5 MB of CI8 flip frames (45 x 96x96 at 32 KB 16-bit) to a working set already over the 2.44 MB UI budget, so textures cycle through disc reads. Measured fixes (r101 entry fight, EFFECT_ROOM=7, frames / 200 s; effects off = 4413): control 2203-2369 (idle 58-61%); the 32 loaded 96x96 effect frames as VQ (re4-assets-private/fx-vq-20260929, 1.18 MB -> 213 KB, PSNR 36-46 dB; fixture tour/rel-r101-entry-pw-fxvq.json) 2343; plus TEX_SLOTS=448 2773 (idle 50%). The 192-entry table recycles a slot on every new key (not counted as an eviction; 432 unique in-room keys); 448 needs the entry hints widened (COPY_LEAN, patches/tex-slots-hint-wide.patch, default image unchanged by construction) and costs ~63 KB of image (+57 KB .data), which heap 4 pays. Still VRAM-bound after that (1906 evictions): the effects-on working set is ~5.5 MB against the 2.44 MB UI budget. Next options, each lossy or costly, to decide by hw ms: VQ the large 16-bit room/model textures (vq_native_ui.py --model-min-bytes), a room-effects texture budget, fewer simultaneous effect classes. EFFECT_ROOM stays 0 in the play build until then. Model/room VQ measured 2026-09-29 (vq_native_ui.py --model-min-bytes 32768 over the 132 r101 fight textures >= 32 KB padded: 12.0 MB -> 1.77 MB VRAM, PSNR median 34.1 dB, p10 30.2, worst 25.6 = an alpha mask; the low ones are foliage / grass / alpha cut-outs; assets re4-assets-private/model-vq-20260929, fixture tour/rel-r101-entry-pw-mvq.json, look sheet model-vq-look.png): on the TEX_SLOTS=448 ELF with effect VQ, 3663 frames / 200 s (18.3 fps) vs 2773 (13.9) without it and 4413 (22.1) effects off; idle 31% (was 50%), loads 1185 (was 2578), freed 616 (was 1906); HALT 0, MISSING 0 (scenario kite-r21mvq1). Flycast proxy only, no hw ms yet. Room effects then cost ~9 ms/frame of Flycast time (was ~27). To land: TEX_SLOTS=448 (patches/tex-slots-hint-wide.patch) + the fx and model VQ packages in the staging; user decides the lossy look. LANDED 2026-09-30 (user: "do what makes sense"): EFFECT_ROOM=7 + TEX_SLOTS=448 in build-r21.sh; COPY_LEAN entry hints and the UI_HANDLES handle entry widened past 255 slots (the handle bug drew entries 256-447 with a wrong texture); the EFFECT_ROOM thrash guard (native_ui.cpp: an effect sprite never evicts; under pressure it draws only from resident textures, <= 4 new effect loads a frame). Found by the STRICT gate: without the guard the r101 bell fight with 16-bit effect frames reloaded textures every frame (6% game speed, ~1 tick/s; not a hang: the vblank heartbeat ran to the deadline). Play assets: tools/d367/texture-vq-rooms.sh, 304 model/room + effect textures as VQ (23.2 MB -> 3.5 MB VRAM, PSNR median 34.2 dB; PS2 world, manual and file keys excluded), staged by make-pw-fixtures.py. Gates: knob-off image = pw5 (.text/.data/overlay identical; .rodata differs only in the 5-byte __TIME__); STRICT tr8k (traced, ARENA_FIT_KOS_BYTES=147456 as in the play recipe; the default 131072 runs out of KOS heap with 448 slots + VQ) on the kite fixture: STRICT_TRACE_PASS over 0-1941 and --align room. With the VQ fixture the trace shifts at tick 184 (the room's enemies spawn a few ticks earlier): the entry preload fits 184 packages instead of 160 and takes 4.87 s instead of 4.4 s, so background DVD loads land on other ticks (the door-frame IO-timing class, not a logic change; an equalised arm is the open proof). r101 bell fight game speed per 300-tick window (Fast pacing): r21j effects off 25/43/15/59/85%; this build, effects on + VQ 26/47/36/75/95% |
| 3 | POST_F00 (Filter00 glow + contrast) + PVR_DITHER | done: off | a7dbcd3a landed default off, ~0 ms. Decision 2026-09-29 (user asked for my call): off in the play build. On the r101 PS2 world (r101-entry fixture) the play build is already at / above GameCube brightness (view mean 47 vs Dolphin r101 26-44); =1 / =4 lift it to 68 / 67. The "matches GC with Filter00" note came from the source-renderer world. PVR_DITHER is a no-op (KOS already dithers). Note: the default kite fixture stages no PS2 world (PS2MESH open failed, flat fallback): judge looks on rel-r101-entry |
| 4 | Door loading U0/U1/U2/U6 (IO_PROBE + dvdhold, TEX_KEEP, IO_ALIGNED, DVD_WAIT, DVD_FDCACHE); main-checkout extras (mkdisc.sh, tests, bake_room_prelit.py); PACE_PAGE vs the Options row | done | 4e9b4ccb: build-r21.sh sets TEX_KEEP=1 IO_ALIGNED=1 DVD_WAIT=1; DVD_FDCACHE lands default off. r100 -> r100 door x3 (tour/door-cycle-pw.json, emulated): baseline 13.1 s / 41 game frames per door, recipe units 8.3-9.6 s / 41 frames (the saving is CPU), all units incl. FDCACHE 7.6-8.9 s / 29 frames. Door-frame rule: the equalised arm holds each source request at its start (cDvdQueue::Read m_Rno0==0 && step==0; gating every step held reads in flight, +1 frame per door) until its baseline frame (tour/door/dvdhold.txt, 186 per-read targets), yielding like a contended step. U1+U2 (kite-r21dh12ch) and DVD_WAIT (kite-r21dh6wh) held: 41/41/41, aligned STRICT over the whole run. FDCACHE is parked: it moves the in-frame MemorySwap queue drain earlier (df 26 vs 38); the hold releases a drained request after 100 ms without a frame (no more HALT) but the doors come out 49-50 frames and FAIL, so it needs a different equaliser (worth ~0.7 s per door). Recipe arm (traced, kite-r21dkt) STRICT vs r20k3w 0..1941, resource 80; knob-off .text/.data identical. Extras landed fb082cbf (mkdisc.sh hardening, fixture-clock + r100 event-completion tests pass; test_event_file's host-compile error is pre-existing on the tip). PACE_PAGE not landed: it is a page of the boot quality picker, which the play build disables (QUALITY_PICKER=0, no boot picker); the title Options row stays a separate item and play discs keep Fast pacing + the R+START cycle |
| 5 | r100 + r103 PS2 worlds: extraction -> ps2_world_r4im -> any-room PS2_WORLD_MESH runtime | done (moved ahead of 4, user 2026-09-29: the fixes must be seen in the new world) | PS2_WORLD_ROOMS=2 in build-r21.sh. tools/ps2_room_r4im.py builds any room from the JADERLINK OBJ export (r101 reproduces the committed package: 190 meshes / 209 placements / level 0 47,770 vs 47,772; every triangle matches the wrapper in winding, UV, colour bytes, texture). r100 1.65 MB (177 meshes / 283 placements, 106 instanced), r103 1.14 MB. =2 opens the package at the room's first scenery bind and skips the Standard scenery package (r103 cannot hold both: 80 KiB heap-4 reserve); non-coarse images (route movies, events) draw the PS2 world at their first scenery part. Heap 4 free after open: r100 3.80 MB, r101 4.12 MB, r103 4.39 MB. Flycast steady ms control -> =2: r100 s20 37.1 -> 37.3, post-radio 26.8 -> 26.0, r101 entry 79.1 -> 78.8, r103 entry 67.3 -> 58.4. Knob-off identity; STRICT (traced, r101 package staged) passes 0..1941. Look: r100 forest floor / trees and r103 fences, house, trees now drawn (Standard showed dark ground and placeholder squares). Open: r100 authored colours are mostly saturated (median vc 1.99 vs r101 0.41), e.g. the gate hedge after the radio call is flat and bright; PS2 SMX colour semantics unknown. Staging: tour/*-pw.json (make-pw-fixtures.py); the play disc needs the same files |
| 6 | Full scripted run title -> r103 with screenshots (scenery, effects, manual, ambush); Windows + SteamOS packages | in progress | Play disc r21u (2026-10-04, b730bf1a = r21t + lane/review-fixes-20261004: TEX_PACK retry spacing + the preload re-run after a pack read error; the play image differs from r21t's source in native_ui.o and texture_package.o only): ELF route-build.sh r21u-play (TREE=b730bf1a, DBG_WARP=0 PC_SAMPLER=0, sha d8d7abbe; .text/.data/overlay = the gated m4-lfp, 4 __TIME__ bytes), twin r21u-warp (sha f1238df0; = m4-lfw, the route-check build, 4 __TIME__ bytes), C:\RE4DC-Play-Discs\r21u-title (fixture title-invfix-pak-r1.json, STAGED_PAYLOAD_IDENTITY_PASS; disc.bin sha 709bb5a4, disc.cue 881f64d2), GDEMU r21u-gdemu (INPUT_CHARSET=utf-8 SECTOR=2352; disc.gdi 1bac5c9d, track03.bin 6abb499d; GDI_ALL_PAYLOADS_PASS, 1,143 files, 458,647 sectors at LBA 45000), launcher D:\RE4DC-Play\Play-r21u-Review-Fixes.cmd. Checks: GDI boot (gdi-r21u-boot, the GDI itself in Flycast, 240 s): high-density TOC, data track FAD 45150, the VMU system-info prompt, crash screen armed, no fault; u-newgame (r21u-play, newgame-invfix-pak, 720 s): tex.pak 3,242 packages, r120s00 1971/1971, r120s01 2360/2360, r100 PS2 world, r100 s40 1175/1175, ~30 fps at 100% speed; u-chapter (r21u-warp, chapter1-end-invfix-pak, 600 s): r106s00 1738/1738 -> VMU syswrite rc=0 -> r104s00 4856/4856 -> missed QTE -> s02 25/25; inventory u-inv100 / u-inv104 (r21u-warp): open/close restore hashes e0beb775, 897ceed3 (r100) and 4075bead, 46f4dcf7 (r104), all ok, the same as the landing-tree gate; route checks (m4-lfw = r21u-warp's code): r100 calls 1465/571/340, r101 bell events released, r103 entry; every run HALT 0, MISSING 0. Not released. Play disc r21s (2026-10-03, 4e387548 = r21r + the MOVIE_HEAP_EVICT cache loan; r21r can skip the r100 cliff cutscene): ELF route-build.sh pc18 (TREE=step1, DBG_WARP=0 PC_SAMPLER=0, sha c75b60a2), C:\RE4DC-Play-Discs\r21s-title (fixture tour/play/title-c14-pak.json, the r21r pack; disc sha 457e4454), GDEMU r21s-gdemu (SECTOR=2352), launcher D:\RE4DC-Play\Play-r21s-Cliff-Fix.cmd. Checks: route-ng15 (pc18, newgame-c14-pak, 720 s): r120s00 1971/1971, r120s01 2360/2360, r100 s40 1175/1175, r100 PS2 world 20 fps at 100% speed, pack in use, HALT 0, MISSING 0, rejects 0, upload failures 0; calls18 (the same source): route-hm4 the cliff movie 340/340, cache back. Not released. Play disc r21r (2026-10-03, b6d1798b = r21q + TEX_PACK): ELF route-build.sh pc17 (TREE=step1, DBG_WARP=0 PC_SAMPLER=0, sha bdb0d9ab), C:\RE4DC-Play-Discs\r21r-title (fixture tour/play/title-c14-pak.json = route/pack-fixture.sh of title-c13-pw: dc/tex.pak 3,241 packages, 92,399,616 B, sha bacdb614; disc sha 59bec3c6, 939 MB), GDEMU r21r-gdemu (SECTOR=2352, boots from the high-density TOC), launcher D:\RE4DC-Play\Play-r21r-Texture-Pack.cmd. Checks: route-ng14b (pc17, newgame-c14-pak, 720 s): intros -> r100 PS2 world, 20 fps at 100% speed, pack in use, HALT 0, MISSING 0, rejects 0, upload failures 0, textured; calls15 (the same source + IO_PROBE): route-pak7 preload 7.2 -> 3.1 s, route-pak8 6.5 -> 2.7 s. Knob off = r21q (.rodata __TIME__ only). Not released. Play disc r21q (2026-10-03, 31470549 = r21p + PS2_PRELOAD_LEAN): ELF route-build.sh pc16 (TREE=step1, DBG_WARP=0 PC_SAMPLER=0, sha 7856266b), C:\RE4DC-Play-Discs\r21q-title (fixture tour/play/title-c13-pw.json, disc sha 200bb415), GDEMU r21q-gdemu (SECTOR=2352), launcher D:\RE4DC-Play\Play-r21q-Walls-Loading.cmd. Checks (calls10 = the same knobs): route-lean1 (r100 s20..cliff) preload 16.3 -> 7.2 s, route-lean2 (east walk) evictions 73 -> 0, HALT 0, MISSING 0, fully textured. Play disc r21p (2026-10-03, dcda51ca = r21o + UV-guarded PS2 world packages + CLOSED_PASS_KEEP): ELF pc15 (sha 73274a0e), r21p-title (fixture title-c13, disc sha 55176b25, the seven -uvg packages staged), r21p-gdemu, launcher Play-r21p-Walls-Crash.cmd. Checks: route-uvhg house walls straight; r101 entry +0.6..1.3 ms. Knobs off = r21o / r21p (.rodata __TIME__ only). Not released. Play disc r21o (2026-10-02, 3d895078 = r21n + SS_PACK + MOVIE_HEAP_EVICT, the user's r21n play findings): ELF route-build.sh pc14 (TREE=step1, DBG_WARP=0 PC_SAMPLER=0, sha 830a66de), C:\RE4DC-Play-Discs\r21o-title (fixture tour/play/title-c12-pw.json, disc sha 94308391), GDEMU r21o-gdemu (SECTOR=2352), launcher D:\RE4DC-Play\Play-r21o-Calls-Cliff.cmd. Checks (calls6 = the same knobs): route-pk1 post-house call 0 textures released, no preload after it; route-s30d the r100 s30 cliff movie 340/340 with audio, then the examine view; HALT 0, MISSING 0. Knobs off = r21n (.text/.data/overlay identical, .rodata __TIME__ only). Not released. Hardware-test disc r21n (2026-10-02, 4fb5e61f = r21m + the SH-4 alignment fixes + CRASH_SCREEN): ELF route-build.sh pc13 (TREE=step1, DBG_WARP=0 PC_SAMPLER=0, sha 20f90b92), C:\RE4DC-Play-Discs\r21n-title (fixture tour/play/title-c12-pw.json, disc sha 823b9c4e), GDEMU r21n-gdemu (SECTOR=2352; boots in Flycast via the high-density TOC to the VMU system prompt, crash screen armed). Gates against r21m (pc12w): kite frame 2100 identical, heap 4 -12,288 B; bridge / r105 / chapter end / r107 state identical apart from heap figures; align runs 0 misaligned over r100-r107, movies, VMU saves, QTE, manual (route doc "Hardware readiness"). Not released. Play disc r21m (2026-10-02, chapters 1-1 + 1-2, dafd193e): ELF route-build.sh pc12 (TREE=step1, DBG_WARP=0 PC_SAMPLER=0, sha c77e5276), C:\\RE4DC-Play-Discs\\r21m-title (disc sha 9de549ae), GDEMU r21m-gdemu (SECTOR=2352, boots in Flycast via the high-density TOC), launcher D:\\RE4DC-Play\\Play-r21m-Chapter-1-2.cmd, packages RE4DC-r21m{.zip,-SteamOS,-CachyOS} (local). Fixture tour/play/title-c12-pw.json = the union of the r106/r104, r104/r107 and r105 route fixtures without warp/padscript/quality (72 shared keys, all byte-identical). Checks (pc12/pc12w): New Game 720 s (intros -> r100, 21 fps 100%), bridge (s44 x16, steady 27.5 fps 100%; was 3 fps 12% before d498fd14 + MOVIE_WINDOW), r106 chapter end -> save -> r104, r104 -> r107 (14.5 fps 97%), r105 chapter 1-2 end -> save -> s10 (then 11 fps 74%): HALT 0, MISSING 0, OOM 0. Play disc r21l (2026-10-02, chapter 1-1 + r104, ba84cbdf): ELF route-build.sh pc11 (TREE=step1, DBG_WARP=0 PC_SAMPLER=0, sha 24869fe7), C:\\RE4DC-Play-Discs\\r21l-title (disc sha ba88d618), launcher D:\\RE4DC-Play\\Play-r21l-Chapter-1-1.cmd. Fixture tour/play/title-c11-pw.json = route-rel-r106-r104-chapter2-pw.json without dc/warp.txt / padscript / quality (1017 files: r106 + r104 rooms, movies, PS2 worlds, chap01, em2a, pl08, em13). Checks: route-c11ng (pc11, New Game 720 s: r120 intro 1971 + 2360 -> r100 PS2 world -> r100 s40 1175, ~20.7 fps at 100% speed), route-c11walk (twin pc11w: r103 -> r106 door, PS2MESH 106 open, ~12.5 fps / 84% speed in r106), route-c11chap (pc11w: r106s00 1738/1738 -> results -> VMU syswrite rc=0 -> r104 s00 4856 -> QTE miss -> s02): HALT 0, MISSING 0, OOM 0, open failed 0/0/1 (the known early r104 PS2 world open at the chapter end, retried). No single run plays title -> r106; the user's play is that check. Play disc r21k (2026-09-30, ac855419 = r21j + room effects, thrash guard, 448 texture slots, texture VQ): ELF pw8 (clean objdir), C:\\RE4DC-Play-Discs\\r21k-title (disc sha c1e7cbb4), launcher D:\\RE4DC-Play\\Play-r21k-Room-Effects.cmd; packages RE4DC-r21k.zip (590,177,701 B, sha256 5f502126...) and RE4DC-r21k-SteamOS.tar.gz (583,374,756 B, sha256 0fa84fdc...), local only. New Game pad fixture (kite-r21pw8ng, 720 s): r120 intro -> r100 PS2 world with room haze, HALT 0 / MISSING 0 / OOM 0. Warp tour on pw8w (kite-r21t8*): all 7 spots HALT 0, MISSING 0, OOM 0, PS2 world open; frames vs the r21j tour (effects off) within 0-12% except the bridge police-car scene (720 vs 960 frames / 240 s; that spot is 10-16% game speed in r21j too). Earlier: Play disc r21j (2026-09-29, 4f52c954 + fb082cbf tools): ELF pw5, C:\\RE4DC-Play-Discs\\r21j-title (disc sha bc00d36b), launcher D:\\RE4DC-Play\\Play-r21j-Doors-Manual.cmd; New Game pad fixture (kite-r21pw5ng, 720 s): intro movies -> r100 PS2 world -> next movie, no HALT / MISSING. Warp tour of the same build with DBG_WARP=1 (ELF pw5w, fixtures tour/rel-*-pw.json, 240-360 s each, scenarios kite-r21tj{prad,s20,brdg,east,r101,bell,r103}): r100 after the radio call, the s20 ambush, the bridge (police car scene), the east door, r101 entry, r101 after the bell at the door, r103 entry: all HALT 0, MISSING 0, the PS2 world open in each room (PS2MESH room=100/101/103), 11-17 screenshots each (contact sheet r21j-tour.png, session scratchpad). Packages built locally, not uploaded: C:\\RE4DC-Play-Discs\\pkg\\RE4DC-r21j.zip (590,365,151 B, sha256 2bd860a3...) and RE4DC-r21j-SteamOS.tar.gz (583,573,045 B, sha256 2cf6635e...). Earlier: Play disc r21i (2026-09-29): ELF pw4 = ad0c59d0 recipe + DBG_WARP=0 (checklist play flags), tour/play/title-pw.json -> C:\\RE4DC-Play-Discs\\r21i-title (disc sha 13291cb6), launcher D:\\RE4DC-Play\\Play-r21i-PS2-Worlds.cmd. New Game pad fixture (newgame-pw, 720 s): r120 intro -> r100 with the PS2 world, no halt |
| 7 | Clean up the local copies (186 clones/worktrees, 35 plain trees) once nothing unlanded remains | in progress | Sweep re-run 2026-09-29 evening (tip ad010aff): 85 knob names in novel files are absent from the tip, all accounted for. Diagnostics only (POOL_PEAK_LOG, SKEL_AUDIT, COL_STATS, CAM_LOG, WQ_CAMLOG, MOTION_MISS_LOG, H4DIAG, ROUTE_ACTION_DIAG, NO_STD_CENSUS, SOURCE_CENSUS, WD_FREEZE_AT, TEST_BSS_PAD, EC_COUNT, SCEN_LOG, GPMEMO_LOG, HWCAL_*, DBG_BUILD_ID, MOTION_HASH, COLLISION_QUERY_OBSERVER: read-only, no speed claim). Rejected by the user: CUT_GORE (gore stays); QUALITY_LOW, PACE_PAGE, DBG_AUTOLOAD_QUALITY (the boot picker; QUALITY_PICKER=0). Superseded: scenery-trials CULL_/FOG_/TREE_/LANDMARK_ knobs, COARSE_HOUSE, COARSE_WORLD_LAYERS, COARSE_SOURCE_POLICY, CW_KERNEL, OT_LOD0/OT_GXNRM/OT_SKYNOFOG (all coarse- or original-world trials; the PS2 world mesh won), UI_TEXTURE_SLOTS (frontier/tree4; now TEX_SLOTS), FIX_R101_CALL_DONE (a test knob; the call reset itself landed as 4980a40 + 976c93d), A30_OBJSCR, ACTOR_CROWD_OPEN, FENCE_SPLIT. Measured and dropped: SKEL_PF (sq58/59), IK_PASS (excluded from ddea9bf on purpose), HERMITE_FLAT / GETPOS_MEMO (P7/P8), Codex MOTION_LEASE_LEAN / GAME_HF_ASM (G 29.18 / 29.76 vs control 29.17 ms: keep 0). Before deleting, every novel file and each git tree's uncommitted diff + local commits go to /root/probe/unlanded-archive-20260929 |

## Known open items outside these steps

- Player's Manual / file pictures: FIXED 4f52c954. ss_item_draw.cpp's GameCube MRAM range check rejected every DC address (no file picture was ever drawn); the route's 1 MiB RGB565 page packages could not upload in-room (~300 KB VRAM free) and are staged as VQ (re4-assets-private/manual-vq-20260929); every other file picture is adopted by its own key (re4-assets-private/file-pictures-vq-20260929, all 49). Fixture: tour/manual-pw.json (w11 file opens).
- Diagnostics to land default-off or archive (HEAP_CENSUS, HEAP_REPLACE_LOG landed 8c000e81): POOL_PEAK_LOG, SKEL_AUDIT, COL_STATS,
  SKEL_PF, IK_PASS, CAM_LOG, WQ_CAMLOG, MOTION_MISS_LOG, H4DIAG, ROUTE_ACTION_DIAG.
- Codex 09-27 trials to check: GAME_MOTION_PROGRAM / COLLISION_QUERY_OBSERVER, COARSE_SOURCE_POLICY / SOURCE_CENSUS.
- Not landing (rejected / superseded): CUT_GORE, scenery-trials CULL/FOG/TREE knobs, OT_GXNRM / OT_SKYNOFOG / OT_LOD0,
  COARSE_WORLD_KERNEL, HERMITE_FLAT, DBG_AUTOLOAD, HWCAL_*, FIX_R101_CALL_DONE, A30_OBJSCR, CROWD_LOD_OPEN, FENCE_SPLIT,
  QUALITY_LOW.
