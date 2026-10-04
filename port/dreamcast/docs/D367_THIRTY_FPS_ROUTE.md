# D367: 30 fps on real hardware, three-room route

## 2026-10-04: local experimental checkpoint and delivery audit

The combined full-module candidate measured90.0806 ->82.6492ms in the uncapped r101 square (ticks1330:1389,60frames,stride1,tail3; ACT_CAP0/PACEoff; SH-4-model CPU work excluding waits). Seven controlled schema5 source/candidate pairs pass24,279 complete state/decision/effect frames. This is not30fps, natural-transition, visual or physical-console acceptance. r104 inventory is visibly broken in both controls and the introducing change remains unresolved.

Source checkpoints4386239f and3739a8e0 are on experiment/supervisor-20261004. The latter preserves a default-off early-admission experiment that lost6.1125ms and must not be enabled. No play recipe change. The isolated ready diagnostic16f0da96 remains in the coordinator checkout.

The supervisor did not follow incremental delivery promptly. A rejected publication attempt remained unresolved while local work accumulated. Live GitHub verification shows lamb2k/re4dc is public, contradicting the old private description; the publication question now explicitly states that fact. The remote wasce39455f at audit time. See [delivery audit](SUPERVISOR_DELIVERY_AUDIT_20261004.md) and [combined baseline](SUPERVISOR_BASELINE_20261004.md) for results and preserved failures.

Active since 2026-09-23 (Claude, user-directed). This document supersedes the
paused D366 handover and the "beat D349" sequence as the current plan. Earlier
checkpoints remain evidence.

## Goals and decision rules (user)

- **Target: 30 fps on a real Dreamcast.** Flycast is a proxy. It counts issued
  instructions and has no cache or latency model. It does not enforce TA or VRAM
  capacity.
- **Decide by frame time.** Every option states its ms/frame impact as:
  - a real-hardware estimate against the 33 ms frame;
  - the measured Flycast figure, noting the 16.7 ms vblank quantisation.

  Take the fastest option whose visual difference is negligible. A modest cost
  is acceptable only when the result looks substantially better.
- **GameCube rendering tech may be abandoned** for Dreamcast-native approaches,
  including new or simplified assets and PS2-derived art. Collision, events,
  game sequencing and gameplay state stay source-authoritative.
- **An ODE (GDEMU) may be required.** Ship GDI with 2048-byte data tracks, not
  CDI. Design for ms-class latency and 1.5-3 MB/s sustained reads, all async
  and prefetched. The G1 bus caps reads at about 10 MB/s.
  - Disc artifacts (architect review 2026-10-03). "2048-byte data tracks" means 2048-byte MODE1 user data; the
    stored sector size differs between the two images. The GDEMU image (`stage.sh GDI=1` / mkgdi.sh,
    `SECTOR=2352` default; e.g. r21s-gdemu) has three tracks with raw 2352-byte sectors (16-byte sync + header,
    2048 user bytes, EDC/ECC); track 3 starts at LBA 45000. The Flycast play image (e.g. r21s-title `disc.cue`) is one MODE1/2048 track of 2048-byte logical
    sectors. Same data-track sector count (r21s: 458,648). Sector n of the data track is at byte n x 2352 + 16 of
    track03.bin (GD LBA 45000 + n) and at byte n x 2048 of disc.bin.
    A Flycast boot of the CUE image does not validate the GDEMU TOC, the raw tracks or physical media.
- **Floating point:** `-ffp-contract=off` everywhere was approved (logic plan
  step 6B). Recapture the determinism baseline once. After that, O2 changes
  must be strictly identical.
  - GAME_FDLIBM=1 (contract-off trig built from the recovered newlib sources)
    goes in the same step.
  - Render-only native renderer objects are exempt, saving about 0.5 ms on
    hardware.
  - KOS flushes denormals (FPSCR), so O2 isn't identical by construction. The
    STRICT trace gate decides.
- **Hardware test gate:**
  - No console testing until the recovered game plays r100 -> r101 -> r103
    through normal transitions, with cutscenes, music, sound effects,
    inventory and death/retry.
  - Flycast must reach about 15 fps first.
  - The test kit is a GDEMU and a VMU, with no serial link. Diagnostics go on
    the VMU LCD (dca3 style) and an on-screen PERF_HUD with the logic digest.
- **Cutscenes must play.** Skipping them loses story context. Present each
  route event with its PS2 pre-rendered movie (BIO4MOV.AFS) while the GC event
  code applies every gameplay effect. Build on branch
  `experiment/ps2-fmv-spike`: it has the menu, the intro FMV with audio, and
  the route entry. Its FMV state is largely uncommitted in that worktree.

## Hardware readiness (2026-10-02)

User asked for a pass over what could stop the game on a real console. Flycast runs some code a Dreamcast
does not, so r21m, clean in every Flycast test, would have crashed on hardware in the first minutes of r100:
- **Misaligned accesses** (the SH-4 raises an address error; Flycast without its MMU performs them). An
  alignment-checking interpreter Flycast found 17 PCs on the new-game route: cCtrl's work at 0x13 (Ctrl11 /
  Ctrl12 / ctrl01), and the u16 arrays motion, camera-motion and shape data keep at offset 3 plus Hermite key
  counts / frames after odd-stride key blocks. Fixed off the PowerPC only: work at 0x14, `u16_un` (types.h).
  The fixed build logs 0 over every route room (r100-r107, movies, VMU saves, QTE, manual).
- **Memory never written**, **vertex buffer size** and **no logs without a serial cable**: POISON_RAM runs match
  r21m; TA peak 1.67 MB of input in the r101 fight against the 2 MB buffer; CRASH_SCREEN=1.
- **User decisions:** CRASH_SCREEN is in every play build (build-r21.sh), and the screen asks the player to
  raise a ticket with a photo (github.com/lamb2k/re4dc/issues).
- Gates for the fixes + crash screen against r21m (pc12w): kite frame 2100 identical (heap 4 -12,288 B);
  bridge, r105, chapter end and r107 game state identical apart from heap figures.
- Rule from now on: run `tools/d367/hwready/route-hw.sh align` over any new room or data format before a console
  disc (tools/d367/hwready/README.md).

## Radio calls and the cliff cutscene (2026-10-02, user play of r21n)

The user played r21n and reported slow loading after cutscenes and calls, and the radio missing in some cutscenes.
From the play log (D:\RE4DC-Play\logs\game-20261002-163147.txt):
- **Calls.** The sub screen (call, inventory, map) parks 3 MiB of live game memory while it is open: 2 MiB in TA
  bank 1 and 1 MiB in one contiguous texture-pool block. Carving that block out of a full, fragmented pool released
  159-211 room textures (2.2-2.3 MB), and the preload after the close reloaded 207-209 of them (5.4-5.9 s of disc
  reads) after every call.
  **SS_PACK=1** (subscreen.mk): the area is stored LZ4-block packed (the VMU codec's format; 4096-entry table,
  64 KiB window, LZ4 skip), 3,144,608 -> 1,824,352 B in the r100 post-house call (1.72:1), so it fits bank 1 and
  takes no pool memory. If a later state packs worse, pool blocks are taken as the stream grows (free memory first,
  then the least recently used textures), never one contiguous MiB. The encoder's table and staging sit in the
  area's first 8.5 KiB, which go raw first and are put back before anything else reads the area. Same bytes back:
  the close checks the hash taken at open. Route run route-pk1 (r100 s20 + ambush + post-house call): textures
  released 0, preload after the close none (route-hs20 without it: 209 reloaded in 5.4 s). Open 583 ms and close 246 ms
  in Flycast with the LZ4 skip and bulk literal copies (route-s30a; 656 / 349 ms without them; the plain backing
  75 / 68 ms): about 0.8 s per call instead of ~5.5 s.
- **The cliff cutscene (r100 s30, area 01: face west at the cliff edge and press A).** Its movie needs 363 KB of
  heap-4 staging in pieces of up to 166 KB. After the ambush heap 4 had 257,568-313,504 B free with no 83 KB piece, so
  the movie failed (terminal=3) and the cutscene was skipped silently.
  **MOVIE_HEAP_EVICT=1** (game30.mk, needs MOTION_OOM_EVICT and ROUTE_MOVIES): a movie staging allocation that
  fails evicts unpinned motion keys, least recently used first, and retries. The movie owns the frame, so nothing
  animates (true for blocking movies such as this s30 cliff; not for stepped / QTE movies, see the 2026-10-03
  correction below); evicted keys reload from disc at their next use, as with MOTION_OOM_EVICT. Each of the decoder's two frames is also split into its three planes (largest piece 55,296 B; pl_mpeg local
  option PLM_VIDEO_SPLIT_FRAMES), and the sound service's 32,800 B separation buffer gets the same eviction first.
  Route run route-s30d (r100 s20 + ambush + post-house call + the cliff, A at area 01): 17 motion keys evicted
  (251,360 B), the movie plays 340/340 with audio (dropped 0, HALT 0, MISSING 0) and the game continues into the
  examine view ("I hope they got out in time."). With whole frames (route-s30b) the same 17 keys went and no 83 KB
  piece appeared; with planes but no room for the buffer (route-s30c) the sound service could not start.
- Both knobs are in the play recipe (build-r21.sh); with them off the image is unchanged.
- 2026-10-03 (TEX_PACK builds, r21r): the route reached the cliff at another frame and the LRU keys (166 KB)
  never joined into the second 55,296 B luma plane: 197 KB free, largest hole 40,736 B, the cutscene skipped
  (route-pak7). The failure-only free map (route-hm1) put that hole next to the 131,168 B model preparation
  cache, rebuilt every frame and idle while the movie owns it. MOVIE_HEAP_EVICT now lends that cache first and
  allocates it again when the movie retires: route-hm4 / route-hm3 play 340/340, cache back, HALT 0.
- Correction (architect review 2026-10-03; f845b301, 68d3b05a):
  - **Blocking vs stepped movies.** A blocking movie (the r100 s30 cliff) owns the frame:
    no game frame draws while it plays. A stepped / QTE movie (r104s00) does not: game frames keep drawing and may
    ask for the lent cache during the loan.
  - **"Cache back" means re-acquisition was attempted**, not that capacity returned. The loan is now owned by
    ui_bridge.cpp (f845b301): while lent, a model draw is refused and counted without latching its one attempt.
    At retirement the log says "model preparation cache back (N B), K model draws asked during the loan", or
    "cache back FAILED (0 B) ... the next model draw retries". Before f845b301 a failed re-allocation latched the
    attempt and the cache never came back for the rest of the session.
  - **Stepped-movie gate: open.** MOVIE_LOAN_TEST=1 (test only, default 0) lends the cache at each movie's first
    staging allocation. On the r104 QTE fixture no cache is held when the movies start (0 B to lend), so the
    stepped case is not reproduced in Flycast. The r100 s30 cliff run shows the blocking loan: lent 131,072 B,
    back 131,072 B, 0 draws asked.
- Also from the same play: the house ambush runs 12-17 fps, and outdoors Fast pacing draws 17.7 fps by skipping
  about 2 frames in 5 (each drawn frame ~43 ms against the 33 ms tick), which reads as skippy. Hold R + START cycles
  Smooth / Fast / Off.

## Skewed wall textures and the closed-pass crash (2026-10-03, user play of r21o)

The user: "the texture on the wall looks like floor", "the textures on the first house look backwards", "game also
crashes". Live frames from the user's Flycast showed the r100 house wainscot (texture 0038, vertical board seams)
drawn with diagonal seams, and the floor smeared.
- **Cause: the LOD simplifier, not the PS2 data.** The OBJ export maps every 0038 face straight (8 of 8 at 0 degrees).
  mesh_lod.py's quadric collapse judges geometry only; on a flat wall every collapse is free, and a corner moved
  across a UV seam or a tiling restart gets its UV extrapolated and clamped, which shears the texture. It happens at
  every distance: level 0 is the `--lod-floor 2.0` level, already simplified.
- **Fix: `--lod-uv-guard 0.002`** (ps2_room_r4im.py and ps2_world_r4im.py -> mesh_lod.UV_GUARD; default off, so the
  shipped packages still rebuild byte-identical: all seven reproduced). A collapse is refused when a surviving
  corner's new UV leaves its triangle's own mapping by more than the tolerance. Level-0 triangles: r100 68,261 ->
  70,231, r101 47,772 -> 49,565, r103 41,507 -> 42,558, r104 24,881 -> 26,228, r105 29,734 -> 32,653, r106 41,802
  -> 44,226, r107 36,222 -> 39,256; every package gets smaller (fewer coarse levels pass min_gain). Packages
  `<room>-uvg` / `<room>-ps2-uvg` / `world-mesh-r21/package-uvg` in the store (re4mesh sha256 r100 508e5ba2,
  r101 50d1d1e5, r103 b98d867c, r104 d44ed564, r105 35205b01, r106 99e01506, r107 3887749a); play fixture
  `tour/play/title-c13-pw.json` = c12 with the 14 package entries swapped.
- Look: route-uvhb / route-uvhg (Leon placed in the house facing each wall): the window-wall and back-wall wainscot
  straight, the floor planks no longer smeared. Cost (Flycast draw ms per drawn frame, same fixture): r100 house
  route mean 41.49 -> 41.84, worst window +1.1; r101 entry fight steady windows +0.6..+1.3 (12.1 -> 12.0 fps).
- **Crash:** "RE4DC MISSING: native closed pass requested" in r100 right after an A press (PS2PASS closed from=2 to=0:
  an opaque draw after the translucent list opened; the PVR cannot reopen a closed list). **CLOSED_PASS_KEEP=1**
  (game30.mk, render only, in build-r21.sh) keeps the packet in the open list (the TA latches the list type at the
  list's first header, so the packet draws with its own blend) and logs "PS2PASS kept ... ra=" for the root fix. The
  late opaque caller is still unknown. Correction (architect review 2026-10-03): CLOSED_PASS_KEEP is a
  crash-avoidance fallback, not proof of correct rendering. Ordering, alpha and depth for a kept opaque or
  punch-through packet in the translucent list are unresolved; each caller needs its own visual gate.
- **Loading (same play):** after the s03 and s20 cutscenes the area change reloads 157 / 203 textures (4.9 / 6.1 s), and
  running around loads 644 more while the pool is full (2.44 MB budget). TEX_USE_CENSUS=1 (test only) counts the
  resident set the last 2 s / 20 s drew: at the r100 cliff 146 of 178 resident textures (1.69 of 2.13 MB) were idle
  for 20 s; on the r100 east walk 103 of the 105 room-archive textures (896 of 921 KB) were idle. In a PS2 world
  room the room archive's textures are the GameCube scenery the PS2 world replaces, and the Standard index's shells
  and impostor atlases are not drawn either, yet the room preload loaded them first and the PS2 world's own
  textures loaded on first sight.
- **PS2_PRELOAD_LEAN=1** (game30.mk, render only, in build-r21.sh): with the room's PS2 world package open, the
  room pass preloads the package's own textures instead (r100: 59 loads, 2.4 s, in place of 141, 4.1 s); the room
  archive's textures load on first sight if an object draws them. r100 s20 + ambush + call + cliff (route-tuse2 ->
  route-lean1): preload 457 loads / 16.3 s -> 134 / 7.2 s, first-sight loads 298 -> 150, the area change after the
  s20 cutscene 141 loads / 4.1 s -> 4 / 0.6 s, the route reaches the cliff ~30 s earlier. r100 east walk
  (route-tuse3 -> route-lean2): preload 8.2 -> 6.5 s, first-sight loads 48 -> 28, evictions 73 -> 0; draw ms
  26.40 -> 26.33. HALT 0, MISSING 0, screenshots fully textured.
- Still per file after that: the room entry's ~130 loads took 6.5 s in Flycast (~50 ms each). IO_PROBE: 130 opens
  were 3.9 s of it, each a directory lookup (234 directory-sector reads) in dc/tex/<n>/.
- **TEX_PACK=1** (game30.mk, in build-r21.sh; design-doorload U4 step 1): every dc/tex package of the disc in one
  file, dc/tex.pak (tools/d367/texpack.py: 2048-byte header, an index sorted by (crc, fnv), the packages byte for
  byte at 2048-byte boundaries). The runtime keeps the first key of each index sector (20 sectors for 2,512
  packages, 160 B); a lookup reads one index sector, a load opens the pack and seeks to its package. Keys not in the
  pack (texlow, absent) and discs without one take the per-file path. Play discs stage the derived fixture:
  `tools/d367/route/pack-fixture.sh <fixture> <arm> <out fixture>` stages the fixture once, packs its disc and
  writes a fixture that adds dc/tex.pak and removes the packed loose files (texlow/ and the media overlay's stay).
  Same bytes uploaded, same loads: r100 s20..cliff (route-lean1 -> route-pak7) preload 7.2 -> 3.1 s; east walk
  (route-lean2 -> route-pak8) 6.5 -> 2.7 s; HALT 0, MISSING 0, no rejects, screenshots fully textured.
  Trap (route-pak3): a sector-aligned read into a 32-byte aligned buffer is a KOS CD DMA stream; on a long-lived
  index handle it stayed open and an audio-stream start then failed a texture upload ("Previous DMA request is in
  progress"). Unaligned reads avoid the stream but cost ~16 ms a sector (route-pak5: preload 4.5 s). Index reads
  now go through re4dc::texture::read_file_range: its own handle, closed before returning, after the IO_SERIAL wait.
- **Pack failure policy (architect review 2026-10-03; 766a5fa5, 13eaccec).** "Per file after a pack failure" is
  only safe on a loose-file disc: play discs made by pack-fixture.sh drop the packed loose files.
  - **Absent** (fs_open fails): per-file loads, as before. Fine on a loose-file disc.
  - **Read error** (header, an index sector at init, or a lookup's sector): no texture this time; the key is not
    marked missing, nothing is evicted, the loose file is not probed. Init retries 3 times, then once per room load.
  - **Invalid** (bad magic / version / count / offsets / extents / key order / index CRC): one loud
    "tex pack: ... INVALID: <why>" line, then per-file loads. On a packed-only disc that means missing textures.
  - Known weakness (measured in Flycast): if 3 header reads fail in a room that never changes,
    that room has no pack textures until the next room load.
  - Tools: `texpack.py --verify <pak>` runs the runtime's checks plus each package's magic. pack-fixture.sh
    (13eaccec) writes content-addressed verified packs `<name>.<sha16>.pak` with a provenance manifest beside
    them, and refuses to overwrite an output fixture without `--replace`.
- Next for loading (U4 step 2): coalesce a room's preload into a few long reads (its packages are scattered over
  the pack; ordering the pack by room would make the room pass one sequential read).

## Hardware budget

Sources are the official Sega documents (catalogue and citations in the
private probe `dc-official-docs/REPORT.md`) and the dca3-game source.

**Render rate.** Sega's real-world figure is 1 M polys/s for 100-pixel
triangles, about 33k triangles per frame at 30 fps.
- Plan about 20-24k scenery triangles and 6-8k actor triangles.
- That is 50-65k strip vertices per frame.

**VRAM parameter cost** (Dev.Box 3.7.9). Stored cost is 12 B per sub-strip,
plus per vertex:

| Vertex format | Bytes per vertex |
|---|---|
| Textured, 16-bit UV | 20 B |
| Textured, 32-bit UV or offset colour | 24 B |
| Textured, 32-bit UV and offset colour | 28 B |

- At Strip_Len 6 that is 28.7-39.3 B per triangle.
- TA input is 32 B per vertex; don't confuse the two.
- The TA guard must count stored bytes.

**Vertex buffer.** It is a pvr_init VRAM allocation, not a hardware constant.
- dca3 uses 2 MiB per bank x2 with an adaptive per-meshlet guard.
- Historical (2026-09-23): "We currently use 1 MiB, which r100 exceeds on hardware even after LOD. Larger buffers
  are blocked by UI texture VRAM: the UI cache holds 3.0-3.6 MB at the title screen." Superseded by UI_VRAM=1
  + tex-vq3 (700e2d0, item 16 below).
- Current (architect review 2026-10-03): the reviewed recipe (build-r21.sh) uses `TA_VERTBUF_KB=2048` with
  `TA_DOUBLEBUF=1`, i.e. 2 MiB x 2 TA banks, sharing VRAM with the UI texture pool. While a sub screen is open the
  TA drops to one bank and the sub screen owns bank 1: SS_PACK=1 packs its 3 MiB area LZ4 into bank 1 (r100
  post-house call 1,824,352 B) and takes pool blocks only if a state packs worse. Capacity evidence: TA input
  peak 1.67 MB in the r101 fight against the 2 MiB bank ("Hardware readiness").

**Overflow.** A parameter or object-list overflow means that frame cannot be
drawn. Kamui never overflows.

**CPU.** One SH-4 core carries logic and rendering in the same 33 ms.
- Estimated cycles per vertex:
  - prelit scenery: 30-45;
  - lit geometry: 45-70;
  - skinned actors: 70-120.
- Timings: FTRV 1 per 4 cycles; FDIV 12-13 cycles.

## Measured progression (Flycast, r100, frames 2401-2520)

| Candidate | ms/frame | Change |
|---|---|---|
| Q | 559 | |
| S | 409 | NO_EH (f10ed71) |
| T | 234 | Meshlet fast path (02d5a0f), dense actor path (bfa1452) |
| U | 217 | Spatial meshlet packages |
| V2 | 200 | pipeline30: PVR_FAST_WAKE, BRIDGE_LEAN, PVR_PIPELINE=1 |
| LA | 150 | scenery30: MESH_LOD=1 MESH_LOD_PX=3 NATIVE_FOG=1 (LOD packages, GX fog as PVR table fog to the 42.7 m source far plane) |
| LB | 150 | Lightly reduced GC trees; about 2 ms less work, same vblank step |
| LC | 117 | actors30: NATIVE_ACTOR_FAST=1 NATIVE_ACTOR_SKIN=1; actors about 51 -> 18 ms |
| LD | 117 | PS2 trees (ps2-blender stage.sh overlay). About 2.5 ms less work; COMMON package 507 -> 136 KB, so heap 4 gains ~370 KB. **Chosen.** |
| LE | 117-119 | PS2 "groves" variant. 6% more TA data; a few more background trunks; the visual gain is negligible. Rejected by the frame-time rule. |
| LF | 117 | LD + async present (PVR_PIPELINE=2, KOS patch `kos-804b319-async-present`). Work ~96 ms plus ~6 ms fence wait still lands on the 100 ms+ vblank step, so Flycast shows no change. **Adopted as the default**: the better architecture (CPU no longer waits on render), per the user's rule. |
| FE | 100 | LD + frontend30 (COPY_LEAN, FRONT_LEAN, MESH_DIRECT+TA_DIRECT+NATIVE_ACTOR_DIRECT; de03f28): work 95.9 -> 79.9 ms, one vblank step fewer. The logic trace is STRICT. Being re-validated on LF. |
| LG | 100 | LF + frontend30 + printf pass (f52746a). Hardware model: **158.1 -> 131.3 ms** (-26.8); Flycast work 95.8 -> 78.9. STRICT; safe under async present. Game30 knobs not yet included (integration run LH pending). |

Remaining work in LC is about 98 ms. It rounds up to 7 vblanks.

| Area | ms/frame |
|---|---|
| Game-side CPU | ~36 |
| Actors | ~21 |
| Scenery | ~19 |
| Memory copies | ~12-15 |
| Vblank pacing waste | ~19 idle |

## Hardware projection (SH-4 model, 2026-09-23)

The model: an interpreter-mode Flycast trace of LD, frames 2401-2520 (30 frames fully traced), replayed through an SH-4 timing model built from the Sega/SH-4 manuals. It covers pairing and latencies, the 8 KB I-cache and 16 KB D-cache with copy-back, miss penalties, the shared bus, and store queues. PVR/DMA bus contention is not modelled, so the figures lean low. Uncalibrated until console microbenchmarks run.

**LD work projects to ~158 ms/frame on hardware (137-187; quote 130-195) against ~96 ms in Flycast: real hardware costs about 1.65x Flycast.** That is ~4.7x over the 33 ms budget, not ~2.9x.

| Area | Flycast | HW nominal (range) | of which I-miss / D-miss |
|---|---|---|---|
| GC code on render thread (model/light setup, matrices, GX stubs) | 19.7 | 37.3 (31.6-44.9) | 8.3 / 2.0 |
| Actors | 20.6 | 34.5 (31.2-38.9) | 3.0 / 3.7 |
| Scenery | 17.7 | 31.4 (27.6-36.2) | 3.9 / 5.0 |
| Game logic | 15.5 | 25.8 (22.3-30.5) | 5.4 / 1.2 |
| UI / texture cache (native_ui.cpp) | 5.5 | 12.3 (10.0-15.1) | 2.3 / 0.5 |
| Copies | 10.9 | 8.3 (7.6-9.1) | 0.5 / 1.1 |
| TA submission | 4.0 | 5.0 (3.7-7.7) | |
| KOS | 0.6 | 3.3 | |
| **Total** | **~95** | **157.8 (136.7-186.6)** | 24.8 / 14.2 |

Ranked hardware levers:
1. copies, up to 8.75 ms;
2. direct store-queue vertex writes and movca.l staging, 7-8 ms;
3. instruction scheduling and FTRV in hot render asm, ceiling 28.8 ms, realistic 30-50% of it;
4. UI texture-cache O(1) handles, 8-10 ms;
5. fsrra, ~1.4 ms;
6. GC render front-end reduction, worth ~1.7x its Flycast gain.

Not worth doing:
- hot/cold link ordering (+1.2 ms worse);
- OC-RAM (net 1.4-3.2 ms);
- OIX (+17.8 ms; never enable it);
- pref in loops (0.4 ms);
- game-object data packing (at most ~1 ms).

Game logic alone is ~26 ms on hardware, so a 33 ms frame leaves almost nothing for rendering. See "Plan to 30 fps".

Tools: port/dreamcast/tools/hwmodel (24ba078). `hwproject.sh <dir>` projects any candidate in about 6 minutes.

Current stack (LF + frontend30 + UI_VRAM 2048 + tex-vq3) projects to **130.3 ms (114.7-151.1)** against LD's 157.8. Hardware keeps 172% of the Flycast gain.
By area: render-side 32.3, actors 31.1, scenery 27.2, logic 24.7, UI 8.5, copies 3.6, TA 0.3, KOS 2.5.

### D349 on hardware (hwmodel-d349)

D349 (5f42caa, the r100 autoplay prototype: reduced gameplay, sampled camera and animation) projects to **76.3 ms on hardware** (Flycast 53.4). It is not cheaper per unit of work:
- actors cost 2.69 hardware ms per 1k TA vertex records, against our 1.28;
- scenery costs 2.20, against our 1.42.

It draws less (0.87 MB TA/frame vs 1.40 MB) and runs almost no game logic, UI or GC front end. Those three are ~65 ms of our 130.

Not worth porting:
- its prepared actor lights (its most expensive kernel);
- its RAM-buffer-plus-copy packet path;
- AoS20 (already in our static path).

Worth porting (with estimated hardware savings):
1. prepared per-model records instead of the GC front end (-8 to -12).
   - **v1 landed as FRONT_NATIVE=1 (c881fba): -4.1 hw ms** (129.0 -> 124.9; band -3.7 to -4.6). ModelRender draws from only the state the bridge reads.
   - Proof: FRONT_NATIVE=2 compares every model part bit-exactly (0 mismatches over 349,713 parts); the logic trace is STRICT.
   - Ceiling: -11.8 if the whole model front end goes. Left for v2: per-TPL texture objects (~0.9), bridge build, and the HUD unitTrans O(n^2) scan (0.46).
   - Finding: effects are never drawn on DC. EspCommonTrans ends in a no-op GXCallDisplayList stub, so part of its ~1.5-2 hw ms is dead work. Most of it must be kept, because the bridge reads the m_Mat and ChannelSet colour results, so EFFECT_LEAN is estimated at only -0.4 to -0.6 hw ms (another -0.4 to -0.5 if nothing reads m_Mat).
   - Native effect sprites (the default and sub-rectangle sprite paths: fire, smoke, blood, sparks, muzzle flash, weather) are estimated at +0.3 to +0.5 hw ms in r100 (~200-230 sprites, ~20 KB TA) and +0.5 to +1.0 in an r101 fight (300-450 sprites). That's roughly cost-neutral with EFFECT_LEAN. Effect VRAM and translucent fill (large fog sheets, ~1.5 ms PVR each) are unmeasured. User decision pending. (Historical: decided 2026-09-23 and landed: EFFECT_SPRITES=1 a0a32aa, COARSE_FX_SPRITES=2, EFFECT_ROOM=7, all in build-r21.sh. Current scope keeps gore and effects; do not count these gains again.)
   - Effect creation and movement draw from the shared game random-number stream, so logic-side effect caps break the STRICT trace. Only the draw side is safe to gate.
2. one straight per-part emission loop instead of the packet/defer layer (-5 to -6);
3. precompiled HUD headers (~-1.5);
4. a small grouped render hot path (-1 to -2);
5. ~~a per-frame transformed-vertex cache for scenery~~: measured at 0. The transform-once meshlets (02d5a0f) already realise it (24.4% of corners saved), and repeats across draws use different matrices. What's left is a converter-side position/attribute split, ~-0.5 to -0.8 ms, unmeasured.

## Work plan: serialized perf lane (2026-09-23; superseded 2026-09-25 by the parallel lanes under "30 fps rethink")

Performance work was serialized until 2026-09-25: one integrated build, one change at a time.
- After each step, measure the stacked build with hwproject and Flycast, in the r100 quiet window and the r101 fight, reporting p50, p99 and max against the 50 ms target.
- Gains measured as separate arms overlap in the same frames, so only the stacked number counts.

| Step | Change | Status |
|---|---|---|
| 0 | FRONT_NATIVE v1, RELEASE_FLAGS | landed (c881fba, ecbea1f) |
| 1 | Texture preload per room, O(1) handles, no runtime CRC (movement hitches; crowd texture cost) | finishing |
| 2 | Game-logic cuts (game30 LH recipe, then tick cuts) | LH recipe + GAME_TRIG landed (7dd50e7, 28ef388): hw game-logic 25.8 -> **12.0 ms/tick**, inside the ~15 budget; frame 157.8 -> 120.3 hw. STRICT. Next, ranked: D-cache prefetch in the logic list walks (EmAtCheck, partsWorldCalc; ceiling -3.25), EmAtCheck prefilter (<1), Hermite/vector maths (~0.5). Skip: I-cache relink (makes it worse), reciprocal fdiv (not bit-exact). Visual sims stay: cloth and pendulum write the parts chain; effects share the RNG. Per-Ganado design (design-logic/DESIGN.md, call-graph profile; hwproject's game-logic area undercounts logic because it books the shared matrix kernel as render: 29.5 vs 36.2 hw ms at 11): r100 ring fight 23.6 / 27.5 / 31.0 hw ms/tick at 4 / 6 / 8 engaged Ganados, ~1.86 per engaged Ganado (skeleton maths 0.50, foot IK 0.25, collision 0.21, key decode 0.21, EmAtCheck 0.19, AI ~0.14). Bit-exact cuts P1 partsWorldCalc reduced maths, P2 single-pass EmAtCheck, P4 motion-index binary search: 31.0 -> 28.2 at 8, STRICT; further designed cuts P3/P10/P5/P7/P6/P8/P9 project ~22.3 at 6 and ~25.2 at 8. P3 GAME_CONCAT_COL landed (dbe1abb, in LH): 25.19 -> 24.13 at 6, 28.45 -> 27.20 at 8, STRICT, fpsym2 EQUIVALENT. Rejected: P10 GAME_PWC_FAST (+0.45 hw, cache hit rate 28%, prefetch bus stalls), GAME_SCHED=game (no logic gain). Next: FTRV arm with a collision-shadow check build (user sign-off before any recipe change), then P6 fused sin/cos (exhaustive 2^32 host check: 0 mismatches). ACT_CAP never parks engaged Ganados, so it doesn't change these. |
| 3 | Enemies: Leon <=5 ms, CROWD_LOD tiers, ACT_CAP, safe cuts (FX_LEAN, static car/cops; gore kept), Leon fewer-bone rebuild, low-poly Ganado meshes | **3a landed (520e8a0), in PERF:** NATIVE_ACTOR_LOD=1 NATIVE_ACTOR_PRELIT=1 CROWD_LOD=1 (whole-part LOD, prelit static-lit parts, near/mid/far crowd tiers; heads class 2, ladder {0.5, 0.25, 0.1}; every actor still skinned each frame; SH4 skin kernels rescheduled). hw -19.9 ms/frame with 8 Ganados on screen (144.4 -> 124.5; actor path 65.6 -> 43.9) and -4.3 in quiet r100 (114.5 -> 110.2). STRICT 2494 r100 ticks, 8 live. +19,360 B from heap 4; default image unchanged. ACT_CAP code landed off (f708887): N=8 only -1.8 hw ms and our fight check stalls at 5 kills, so it waits for a full-wave r101 fight. Earlier notes: NATIVE_ACTOR_SKIN_LAZY also fixes a 128 KiB prim-buffer overflow that made Leon vanish with 6+ Ganados. Per Ganado: 7.4 hw ms full, 4.5 with tiers. Any Ganado in view also adds ~93 hw ms of texture CRC/reload, which is step 1's fix. Logic trace STRICT at 4 and 8 Ganados. |
| 4 | Render front end: EFFECT_LEAN, EMIT_DIRECT, FRONT_NATIVE v2 | queued |
| 5 | Scenery: fog distance, tree cap, house from halfway, W9 worst views and per-room fog | queued. Trials done: 25 m far plane (room's own curve) is scenery 29.9 -> 18.7 hw ms, frame 158.3 -> 140.1. 20 m fails the enemy rule (a Ganado at 20 m is 100% fogged). Rule for other rooms: min(room far, 25 m). House from halfway (~21 m) needs per-object building fog: open. LOD 5 px (-2.9 at 42.7 m) and TREE_THIN are unmeasured on top. |

Work order (user, 2026-09-24, play testing): the r100 post-house ambush (heap 4), then **frame pacing (never to
be deprioritised again: sub-30 fps is slow motion until it lands)**, then low-poly Ganado meshes, then the Leon
rebuild. Fix review the same day: r101 scope lockup (9598ce2), launcher log, pacing, QUALITY_ASSETS into the recipe,
ambush reserve, ACTOR_FOG_GATE gates, SS_UI_ORDER. Proposed after QUALITY_ASSETS: **zero in-play disc loads per
room** (357 texture loads in play after the last preload in one Standard session; GD-ROM seeks are 100-200 ms).

**Persistent goal (user, 2026-09-24): the r101 square at 15 fps real time** ("at any cost, or the player can't
play"; budget 2 x logic + render <= 67 hw ms per drawn frame, today ~136). Plan, breakdown and the ledger of
every measured arm: [D367_SQUARE_PERF_PLAN.md](D367_SQUARE_PERF_PLAN.md). Order: logic speed-ups
(GAME_VEC_INLINE, collision fast paths, FTRV bones) -> offline-converted Ganado v4 blobs + flat light ->
converted Standard room archive with per-part residency (also the r100 ambush memory fix) -> single-version
scenery with better textures, nearer fog and a backdrop -> square PVS -> queued 64 KiB reads -> selective
-O3/LTO; Fast pacing (PACE_CAP=2) is the play default meanwhile. (The 30 fps rethink below replaced this goal on
2026-09-25.)

**30 fps rethink (user, 2026-09-25): the coarse complete square first**
(`re4-research\RE4_DC_30FPS_RETHINK_2026-09-25.md`; budget G <= 24 + R <= 6 + 3.33 margin per tick).
**Baseline correction (user review):** gameplay preservation is judged against the uncapped encounter
(ACT_CAP=0). The first capped arms (ACT_CAP=6) throttled parked Ganados and understated G by 4.82 ms.
ACT_CAP scope (architect review 2026-10-03): the 2026-09-24 approval is historical and covers the r101 square only;
the r100 house cap arm (H2, `late 0x08`) is a diagnostic spike; adopting ACT_CAP in a play recipe is a separate
decision (build-r21.sh has ACT_CAP=0). Capped results are reported apart from ACT_CAP=0 preservation claims.
Status, uncapped, same stack, hw ms:
- Step 1, qualified no-draw boundary: PACE_TRANS_SKIP=4063, **G_q = 37.52** (capped 32.70).
- Step 2, the coarse square COARSE=1 v0.4: world from collision, ribbon actors, effect markers, source
  HUD.
  - It draws in **R = 5.03** per image, against 63.22 for the source renderer.
  - STRICT with every decision identical against the uncapped control (tr41 / tr42, 4185 frames, 0 drift).
- Fit / gap: complete 42.55 ms per tick, against 33.33 bare (-9.22) and 30.00 with the margin (**-12.55**).
  R fits; **G_q must fall to <= 24.97**. G alone exceeds real time (37.52 > 33.33).
- Skeleton step (user's order, item 1) done: GAME_PWC_KERNEL=3 (last-bit, decisions identical) +
  GAME_PMC_KERNEL=1 + GAME_HERMITE_FAST=1 (exact): **G_q 37.52 -> 34.40** (landed default off: ddea9bf); complete coarse tick 39.78 ms
  (25.1 fps at 83.8% speed); gap 9.43.
- One-house test (user request): BIN 38 as a 400-triangle baked shell with a 256 VQ texture costs ~0.33
  ms per image (v2; v1 0.60), 18 KB VRAM, STRICT (tr51); views and door notes in the plan doc.
- **Current order (user, 2026-09-25):** (1) land the coarse renderer with frame pacing (done: f4da5fd), (2) R headroom
  (done: 801d72d; source work on a drawn coarse tick ~2.1 -> ~0.8 ms, R ~4), (3) back to G: code placement
  done (801d72d, LINK_ORDER, exact: G_q 33.39), collision traversal under way (the em-em candidate cache
  GAME_ATCHK_CACHE, aeefd26, the workAt inline GAME_WORKAT_INLINE, 3eaa868, and the line queries' leaf and
  block walk kernels GAME_LINE_LEAF, cf46edc, and GAME_LINE_WALK, ba73027, and the pieces' transforms in the walk
  kernel GAME_LINE_PIECE, 4e394ea, all exact: G_q 30.66, gap 5.69; then the effect pools' scans and moves GAME_FX_SCAN + GAME_FX_MOVE, 1d3dc4d,
  lane fx, exact: **G_q 29.55**, gap 4.58; then the collision stack, 7caa2f7, lane gc, exact: gc13 29.03 alone, -1.63;
  together on the landed stack with the skeleton kernels (ddea9bf): sq99 **G_q 28.29**, gap 3.32; then the
  skeleton lane, ee7d080, exact: sk10 29.14 alone, -1.52; then the object scans GAME_OB_SCAN, 0862e7c; all of
  it on one build, sq100: **G_q 26.34**, gap 1.37; the vertex kernel ACTOR_VTX_KERNEL, 42afaa1, rev 2 7726caa, rev 3 d938501 and rev 4 + 5 e4fb8e8:
  the reduced characters 15.84 -> 8.65 ms over stick figures; then collision batch 7, ca229cf, -0.62 alone, and the
  object batch 2 GAME_OB_MAT + GAME_OB_PATH, 9f66533, -0.64 alone; on one build, sq103: **G_q 25.22**, gap 0.25;
  a regenerated order file lost +0.38, sq102). Since the evening of 2026-09-25 the rest runs in parallel lanes
  (next bullet).
- **Parallel lanes (user, 2026-09-25: "I don't want to spend more time benchmarking. I want to focus on the
  remaining optimization that can be parallelized").** One agent per non-overlapping lane (arm prefix,
  tree under /root/probe/d367-agents): cl characters (coarse-actors-4k/stack-tree: meshes fitted to the
  character code losslessly, a cheaper adapter, then integrating new cast models), vl vertex loop
  (lane-vloop/tree: ACTOR_VTX_KERNEL; rev 1b landed 42afaa1, rev 2 7726caa, rev 3 d938501, rev 4 + 5 e4fb8e8; stopped), gc collision (lane-gcol/tree: sphere walk, em-em rows; stack landed 7caa2f7, batch 7 ca229cf, area lists rev 2 ff32da9; batch 9 ~0, not landed; parked), fx effects
  (lane-gfx/tree: Esp / Efm, exact; landed 1d3dc4d), ob enemy / object bookkeeping (lane-gfx/tree; GAME_OB_SCAN landed 0862e7c, GAME_OB_MAT + GAME_OB_PATH 9f66533, GAME_OB_NEAR + GAME_OB_DECODE 97874b5; parked), sk skeleton / motion / cloth / maths (lane-gskel/tree; batch 3 GAME_VEC_NORM_INLINE + GAME_MTXINV_SCHED 4f81bbd; exact, plus the
  gameplay-reader map; landed ee7d080), wd world (lane-world/tree: textured coarse world <= ~3 ms; landed 6f4c91c, R +0.68; v10 ground tones 05e402a; the user rejected the look 2026-09-26: an external agent rebuilds the world's assets from the prompt in re4-assets-private/world-agent-20260926/, wd integrates), bg route bugs
  (lane-bugs: memory load / unload, freezes, the r100 -> r101 -> r103 playthrough; relaunched 2026-09-26). By return
  (user, 2026-09-26): gc, ob and vl park after their current batches, wd idles; sk, cl and bg carry on. Per change: one
  cost arm and one STRICT gate, no series. The main session lands every patch via warp/tree7 (knob-off
  identity, carry-over), keeps the docs current. (The coarse HUD's "88" was the light coarse floor behind the translucent gauge;
  the coarse world's ground, 6f4c91c, fixes it.) An external, user-launched
  agent builds and reduces the first level's cast models (private `cast-20260925/`; integration COARSE_GANADO_CAST 08d2216; R levers COARSE_PREGATE / CHAR_DATA_BLOCK c6edb6f),
  and a second one will rebuild the r101 world's assets (prompt `re4-assets-private/world-agent-20260926/`, 2026-09-26); no in-session agent
  builds models. Lane map and owners: the plan doc, "Current order and status".
- Characters (2026-09-25): the reduced models (3,989-triangle Leon, 874-triangle Ganado) draw through the
  actors30 character code. Version C measured (r101 square, ACT_CAP=0, frames 1000-1119; every figure
  names its image): coarse world + reduced characters W 57.13, R 26.47 (cl21; 17.5 fps every tick drawn
  at 58% speed, 3.0 fps paced to full speed); coarse stick figures W 34.71, R 4.05 (cl22; 28.8 fps at 96%,
  19.8 paced); the source renderer with the same reduced characters R 63.02 (cl26), with source
  characters R 68.92 (cl27). The reduced characters cost 22.42 ms over stick figures (re4dc_actor_submit
  12.5, adapters 5.8, skin palettes 1.3); gate cl24 STRICT. The fast character path, first results: the cl
  lane's lossless mesh fitting and FTRV adapters (landed 9df764b, default off) took the characters to 15.84 ms
  (cl42: W 50.55, R 19.89, 4.0 fps paced; STRICT); next is the vl lane's vertex loop. Further mesh gains
  need new assets (the external agent). Plan doc,
  "Reduced characters and the character path".
- WP2 Leon pair (2026-10-03, architect review follow-up; hwsim projections in Flycast, not console measurements).
  Image H2 (r100 house, Leon's radio-call close-up), ticks 1450..1569, all 120 frames traced, ACT_CAP=0, build
  impl-w2c, one binary: Leon by the native 4K cast 49.55 ms work per tick vs the old per-part source path 56.64,
  7.09 ms saved (low-high 5.48-9.25). The old path came back because after the s20 cutscene Leon's material-lifetime
  records are dropped (a part swap at about UI frame 684, a heap teardown at about 1211) and nothing re-proves them.
  The existing default-off CROWD_READOPT=2 re-proves them with the load-time proof. Adopting it in the play recipe
  is a coordinator/user decision; it also changes the r100 post-cutscene Leon from the source mesh to the 4K cast,
  as already drawn in r101/r103.
  **Adopted (user 2026-10-03):** build-r21.sh sets CROWD_READOPT=2 CROWD_CULL=1 CROWD_FOGSKIP=1. Gate (impl lane,
  builds from ed818b8e): STRICT H2 120/120 (1450..1569), 100/100 (1300..1399), whole r100 1391/1391; r101 bell
  120/120 (1000..1119), 100/100 (900..999), whole r101 941/941; route checks r100 calls (movies complete, cliff
  loan back), r101 bell, r103 entry HALT 0 MISSING 0; Leon captures normal (one two-toned hair frame at a hit, in
  r101 where the cast was already drawn: not these knobs). r101 kite STRICT skipped (D: floor). Gore stumps take
  the whole source path (crowd lane note; not exercised in the captures).
- The calibration disc c8 is in `D:\RE4DC-HWCAL` with the model's predictions (hwcal PREDICTIONS.md).
  It awaits the user's console run.
- Landed f4da5fd (default off; knob-off identity, tr42 carry-over): frame pacing (PACE_CATCHUP), PACE_TRANS_SKIP,
  the decision-trace tags and COARSE v0.4 (coarse.cpp). Still private (tree5): the skeleton-step kernels,
  COARSE_HOUSE, the model-diagnostic latch, SS_UI_ORDER, MOTION_RESERVE, the heap / pool logs,
  GAME_SKEL_AUDIT, GAME_IK_PASS.
- Landed 801d72d (default off; knob-off identity, tr55 carry-over): the R-headroom knobs GAME_OT_MASK,
  GAME_ID_LISTS, UI_HEAP_LAZY, UI_PALETTE_SLOTS and the coarse effect-loop hoist (all exact, STRICT), and
  code placement: LINK_ORDER + tools/d367/ordgen_c3.py + link-order/r101-square-c3-8k.ld (never-draw G
  -1.25, drawn -0.94; STRICT).

Details and the ledger are in [D367_SQUARE_PERF_PLAN.md](D367_SQUARE_PERF_PLAN.md).

Parallel tracks (off the frame path; needed for the console gate):
- r101/r103 bring-up (frontier W4, W9 packages) and the route bugs: the bg lane (lane-bugs; relaunched 2026-09-26);
- audio;
- cutscenes;
- inventory/retry (W11);
- GDEMU disc reads (W10).

Asset exploration (PS2/Blender) is parked after the house images.

## Frame pacing (2026-09-23, design-pacing/DESIGN.md)

The game runs one logic tick per rendered frame (main.cpp waits for GetSystemVcnt()=2 vsyncs; no catch-up, no delta time), so any frame over 33.3 ms is slow motion: 20 fps = 67% speed. Chosen: render skip / catch-up (PACE_CATCHUP), with logic at 30 Hz by the vsync clock and draws skipped when behind (at most 2 ticks per drawn frame, 15 fps floor knob). ModelRender plus its deferred draws is ~90% of non-logic work and writes nothing logic reads. Trans() can't be skipped (Filter08Trans uses the shared RNG), and ShadowTrans, Espgen45, TexRender, Filter00/03 and drawLaserSight write logic-read state. Stages: v1 (ModelRender + native frame; 24.3 hw ms/tick left, Standard quiet), v2 (+ModelTrans; 20.7), v3 (+effect/HUD callbacks; 16.5; needs trace digests). Estimates: Standard quiet 43 hw ms -> v2 100% speed at 17 fps, v3 at 19 fps (today 78% at 23 fps). Fights: logic alone is 71/82/93% of the CPU at 4/6/8 engaged Ganados, so no pacing gives full speed there: 43-51% speed at 13-15 fps with the floor, 59-71% at 9-11 fps without. The corrected Standard fight frame is ~65 hw ms (the earlier ~53 used area-method logic). v1 + v2 were built in the private tree and landed on 2026-09-25 as f4da5fd, default off (play discs pass `PACE_CATCHUP=2 PACE_MODE=fast PACE_CAP=2`; the Options row is a later item).

**Tick vs drawn image (architect review 2026-10-03).** "One logic tick per rendered frame" above describes the
original loop. Terms from now on:
- a **logic tick** is one 33.3 ms game update; a **drawn image** is one presented frame;
- with active pacing (PACE_CATCHUP=2, Fast / Smooth) ticks run without draws, so fps and game speed are separate
  numbers;
- capacity per second of game time is **30 x G + F x R <= 1000 ms** (G = work per tick, R = render work per drawn
  image, F = drawn images a second). Admission uses direct cadence measurements (new images a second, game speed),
  not the formula;
- G / R values and the quiet / coarse / fight estimates in this document belong to their own images (Standard quiet,
  the coarse square, the kite fight). They do not transfer to the house images H and H2 (checklist "Benchmark
  fixtures") or to the r21s play image; measure each image.

User decision 2026-09-24: TA_DOUBLEBUF (async TA double buffer, ~12.5 ms/frame of stream_open wait removed; hw projection ~16 -> 20 fps at the 50 ms target) is adopted and option C (single-bank PVR layout, bigger texture pool) is dropped. It lands after sub-screen option (b) (single-bank TA while a sub screen is open) and a matched-window hwproject pair.

**TA_DOUBLEBUF landed (b7a7e2d, 2026-09-24) and is in the canonical recipe (PERF).** Option (b) as designed:
`pvr_set_vbuf_doublebuf()` (KOS patch kos-804b319-vbuf-switch) drops the TA to one bank while the sub-screen
backing holds bank 1, and stream_open switches back lazily. Gates: knob-off identity; inventory open/close in r100
and in the r101 fight (backing hash ok, no HALT); logic trace STRICT over 3,604 ticks; hwproject r101 fight
145.0 vs 145.7 hw ms (CPU-equal, matched game-logic rows). **Measured gain on the canonical recipe is smaller than
the study's ~12.5 ms:** Flycast PC-sampler wall in r100 quiet 73.2 -> 71.3 ms mean (p99 79 -> 74; the single-bank
fence waited 1.7 ms/frame), and 106.2 -> 106.2 ms in the r101 fight (the fence waited 0.08 ms/frame, since the frame
is CPU-bound). The study used a lighter SUBSCREEN=0 fixture (53.9 ms busy). The wait is at most one render per
frame and appears only when the CPU part of a frame is close to the render time, which is where the lane is
heading (50 ms target). Re-measure it on hardware with the calibration disc.

**Room discovery round 2 (2026-09-24, 9f2f45a..49b97b2; user: "we need that to make it through the game scalable").**
`assets.sh discover` now lints each needed module for the known porting traps and writes the module wiring
(`--wire`; audit list only when the lint is clean), lists heap-4 options per enemy archive with a covering plan,
checks each event's evd (route movie, or prepared + qualified evd), and reports Standard budgets and VRAM. Game logic
is never generated. For the r100 after-state crows (171,328 B short in Original): Standard with QUALITY_ASSETS=1 fits
(packages -282,560 B, 111,232 spare); for Original the cheapest option is a new em21 motion-stream contract
(<= 294,240 B). r101's enemy heap-4 room is measured (3,048,704 B, fits 1,595,136 spare); r103's waits for W8b.

User decisions 2026-09-26 (evening): (1) "We can't compromise on the environments so we really need to deal with it":
the r101 environment's look is the goal (as original as possible, not a "VR arena"), and the budget is made to fit it
(renderer vertex paths, characters, the fight's gameplay, VRAM / heap reclaims), not the other way round; the external
world agent prices what the look needs ("needs room") instead of cutting to the caps. (2) "We should work backwards from
the original world": start from the GameCube render set as is (all parts, source textures, source light), price it, and
reduce step by step (invisible reductions first, then near-identical, then visible). (3) The user doubts the original
world was ever fully drawn on the port: the port's "source renderer" captures used the Standard LOD package, so the
reference is an offline render of the GameCube render set; an audit and measurement are running
(/root/probe/d367-agents/original-world-20260926/). Measured the same day (version C, landed stack): G_std 24.84,
G_fight 29.30, R_fight 11.77 (~10 fps paced in the 6-Ganado kite fight), so 30 fps in the heavy fight is out of reach
with this image; the heavy-fight choices come with the make-room plan.

User decisions 2026-09-26 (night), on the world agent's C1b review (its sheets set against real GameCube frames from
Dolphin): **"Go with recommendations"**:
- **Look A:** source tiles + source light, unit normals.
- **Ground R14:** the source soft ground / shadow layers drawn as PVR translucent layers from the resident I4 masks, with a
  constant black colour. Estimated at +6,144 B VRAM and ~+0.6-0.75 ms SH-4 in the named views. G42 stays only as the
  fallback if the hardware fill page rejects the TR fill.
- **Trees:** the PS2 geometry direction, keeping the BIN17 forests as geometry. Estimated V3 tree share 6.44 ms, against
  13.52 for the GC trees.
- **Fog F0:** the approved 25 m.

The first slice (d1) is authorized (re4-assets-private world-agent-20260926 reviews\c1.md). Before its in-game sheet,
the runtime needs:
- R14 (a reserved mode today);
- a memory fit for the whole square (the PS2 trees alone are ~1.19 MB of layout-11 arrays);
- the native PS2 tree materials;
- the ground-brightness fix.

**Tried for real the same evening:** the port draws the full original set in-game.
- The set loads and draws at the square and matches the GameCube in shape and texture. The exceptions are the parts
  whose pair package is missing (invisible) and ~2 wrap-rejected packets a frame in F and W1.
- Cost (image C: 70 m, LOD 0; ot4 / ot5, F): R 94.74 hw ms, ~8 fps. The game's own GX path: R 689.
- The look gaps against Dolphin:
  - the ground is 1.3-3.2x too dark on every port path (cause under diagnosis);
  - no Filter00;
  - the sky and treeline are lost in the 25 m fog;
  - the V1E bonfire is missing;
  - 12 pair packages are not built by the pipeline;
  - no dither and no mips.
- Report: /root/probe/d367-agents/original-tryit-20260926/compare/REPORT.md. The look-gaps job
  (/root/probe/d367-agents/look-gaps-20260926/) is diagnosing the ground, the fires and a PVR Filter00.

Progress 2026-09-28. **Landed r19 -> r21** (user: "Yes land"): the Codex continuation's playability tree r19
(4fb68a8: actor transaction/owner path, the PS2 r101 world drawer PS2_WORLD_DRAW, manual pages, pad prompts, VMU
dialog), r20 (8745fac: PS2_WORLD_KERNEL, UI_HUD_MASK), r21 (09e6175: the PS2 world converted to R4IM v3 and drawn by
MeshDraw, PS2_WORLD_MESH; 64-vertex meshlets and UI_HUD_LENS_ALPHA=230 user-adopted; MEMPROF) and coarse_finite
(36e28e0). All knobs default off; the r21 recipe is tools/d367/build-r21.sh. (2026-10-03, 8f34aa63: it now writes
`$OUT/resolved-knobs.txt` with make's own resolved values, whose path route-build.sh records in programs-route.json;
MODEL_DRAW_PLANS is forced to 1 by the D349_RENDERER_STACK=1 override in the Makefile, whatever the line says.) A clean build of 36e28e0 passes STRICT vs
r20k3w over ticks 0..1941 (kite-r21land). Private source data stays outside git: ganado_source_extras.h and
vmu_dialog_english.inc come from the private asset dir (VMU_DIALOG_TEXT_DIR, default COARSE_ACTOR_ASSET_DIR). The shared
checkout's dirty overlay: 57 of its 71 modified files now equal dreamcast-port; 14 still differ.
**Release split (kite fight, frames 600..720, hw ms/frame):** traced builds carry ~30 ms of trace/diagnostics (r21
traced 128.4, release 98.7). Never-draw twin (PACE_FORCE=A needs PACE_MODE=smooth; PACE_MODE=off disables it) 45.9
with 16.9 of vsync wait: **G ~29.0**; **R ~69.7** = world 21.9, characters ~35 (actor path 18.4 + skin/palettes ~16.6),
UI 4.1, copies 3.6, KOS idle 2.2, isfinite ~2.6 (+ call overhead), TA submit 0.5. coarse_finite: 98.7 -> **93.3**.
The memory-copy item below is ~4 ms in release (the 15-19 ms figures were traced builds). World: 23.8k vertices and
~5,200 strips a frame; PS2 strips average 4.4 corners because UV seams stop joins (position-only keys: 6.7), so
per-strip overhead is about half the world's cost. Order by expected gain: characters (cl), world strips/emit, G 29 -> 24.
**Same day, later.** ACTOR_CENSUS (diagnostic) shows the per-part native path carries room props at source detail,
not only characters: the burning officer on the stake (r101 obj00, placed for region != 0; ~3.9k vertices/frame,
~4.1 hw ms by an A/B skip), doors, item pickups, racks, boxes, windows, the handgun: ~8.6k vertices, ~8 hw ms. The
reduced Leon/Ganados are drawn (ATX: ~3 reduced Ganados a frame; a few fall back). Props and world share the real
limit: ~200 cycles per drawn vertex (world 21.9 ms / 23.8k vertices). PS2 world strips cannot be joined invisibly:
39% of triangles are single quads with their own UV/colour (a swap stripifier, mesh_lod STRIP_SWAPS /
ps2_world_r4im --strip-swaps, gains only -13% strips, -0.4% corners; kept off). MESH_PRIME_LAZY (exact: prime only the
cache entries meshlets use; ~30k entries/frame were stamped for ~24k vertices): 93.3 -> **91.5** hw ms, STRICT
kite-r21lzt; on in tools/d367/build-r21.sh. Next: a software-pipelined meshlet transform (one vertex at a time now,
~64 cycles/vertex with fsrra), the near-plane clipper (~20% of MeshDraw::draw for ~170 strips/frame).
MESH_CLIP_LEAN (exact in pixels): 94% of the strips reaching the near/far clipper were wholly outside one
frustum plane (ground under the camera); they are dropped by a homogeneous test, and each clipped corner is computed
once: 91.5 -> **88.4** hw ms, accepted strips identical, STRICT kite-r21clt. Recipe truth (architect review
2026-10-03, 8f34aa63): MESH_CLIP_LEAN is **not** in the play recipe (build-r21.sh's make line never had it; game30.mk
default 0; the recipe header that claimed it is corrected). **Adopted 2026-10-03 (user):** build-r21.sh sets it. Gate (impl lane,
WP1d tree): H2 58.71 -> 56.53 hw ms (-2.18, all scenery 9.10 -> 6.44), STRICT 120/120, 100/100, r100 1391/1391; off/on
captures in the house and the r101 square fight (near fences and posts, wide views to the frustum edges, blood spray)
draw the same complete scenery. Not proven: pixel-exact frames, r103 views, console TA time. World distance detail is on (MESH_LOD;
Standard uses QUALITY_LOD_PX = 5 px, MESH_LOD_PX only applies to Original): 10 px 86.4, 1000 px (coarsest level
everywhere) 84.4, so world LOD is worth at most ~4 ms in the kite square (near geometry dominates).
Trap: never seed an objdir from another tree's objdir (its .d files name the old targets; edited includes keep stale
objects: the first coarse_finite arm ran with a stale coarse_ganado.o).
**Warp tour (user: "use the warp tool in more places such as r100 and r101")**: fixtures under the private
playability-r11-r1/tour/ (a shared turn/walk/run pad script; per-preset scripts close r101's post-bell call with A and
the r101 entry "Playing Manual 2" with A x4 + B x3; the post-bell preset backs off the r103 door first). It found:
(1) r100 after the ambush (r100-s20) HALTed at room frame ~600, "motion key allocation" (heap 4 full/fragmented while
the key cache was under budget): **MOTION_OOM_EVICT** (41d0310) evicts LRU unpinned keys and retries; one event, runs
to the end, STRICT, knob-off identical. The heap-4 shortage itself remains. (2) **r100 had no world in the r21 build**:
coarse images skipped all source scenery and drew the grey collision view outside r101 (the only PS2 world package).
**COARSE_SCENERY_FALLBACK** (0b68ee3) skips scenery only where re4dc_ps2_world_covers(room); other rooms draw their
assetpipe Standard R4IM scenery, and the owned-actor TR barrier closes the tree-impostor PT window first (else "native
closed pass requested"). STRICT, knob-off identical; r100 gate / east door / s20 draw textured and lit. The r100-bridge
preset opens a cutscene (needs a longer lead-in). A per-room PS2 world package stays an optional upgrade (the r101
chain in world-mesh-r21 is r101-hard-wired; r100/r103 PS2 exports exist under d353-ps2-r100-prelit and d367-agents/w9).
Tour hw ms (release sfr = 0b68ee3 recipe + PC sampler; frames 400..880 of the tour walk; "work" = frame minus the
vsync spin in main, which is ~0 in the CPU-bound kite fight): r101 entry 44.3 (work 36.2), r101 post-bell door 38.2
(35.6), r100 gate after the radio 47.2 (40.4), r100 east door 45.6 (33.7), r100 s20 house after the ambush 76.7 (51.4);
kite fight 88.4 (no spin). Render side dominates everywhere (game-render-side 19-42 + actors 5-15 hw ms); game logic
0.8-7 hw ms outside the fight. So ordinary play is ~20 fps (work just over 33.3 ms), the heaviest views 15 fps or lower.
r103 entry: the r21 base disc still carries the uncompacted st1/r103.dar (4,814,112 B), so em12.drs (1.08 MB) failed
with 402 KB free and model.cpp(1907) HALTed. Staging W8b's compact room (design-r103/w8b-r103-data-recipe.sh ->
w8b-rel/st1/r103.{dar,arc}, 1,455,456 B loaded; regenerated 2026-09-28, the old output was gone) plus m-r103-FIN fixes
it: r103 draws (trees, fence, house, animals, Ganados) and runs. hw 55.7 ms/frame (work 51.6; game logic 10.6 with 5
Ganados + animals). Every disc that reaches r103 needs these ROOMFILES.
**Exact character-path kernels (2026-09-28/29; hw ms as frame / work, work = frame minus the modelled vsync
spin, which is the hardware-relevant figure outside the CPU-bound kite).** AVK_RIGID6 (a5b11de): rigid parts with
stride-6 positions / stride-3 normals get generated pipelined kernels instead of the C fallback (exact, STRICT
kite-r21r7t): r101 entry 44.3 -> 42.2, post-bell 38.2 -> 37.2, r100 / kite neutral. GAME_WPAL_FAST=3 + GAME_SK1_ASM
(3f20eda): MakeWeightPalette and the source skinning CalcSk1_x/_x2 (morphed infos skinned in Trans(), in place, and
the Render() materialisation; SKIN_CENSUS: 2 morphed infos / 3,278 vertices a frame at r101 post-bell, 0 defer
failures) as exact SH-4 loops (check builds 0 mismatches over 70.1M / 29.8M words): r101 entry 42.2/35.9 -> 42.0/34.3,
post-bell 37.2/34.4 -> 36.8/32.5, r100 east door 45.8/33.8 -> 45.7/32.8, kite 89.1 -> 86.8. Post-bell and the east door
now average under 33.3 ms of work. Traps: -m4-single -ml passes float args pair-swapped (the first float in fr5);
serial log lines (aica notes, "[stage") can cut into a trace line, so a timing change can make the STRICT audit
REJECT on one garbled record: compare the records of two runs (every record in the window matching in at least one).
Fixed (2026-09-29): LOGIC_TRACE=1 builds append each re4dc_log line with interrupts off (RE4DC_LOG_ATOMIC on
platform/mem.o; the aica sequencer thread preempted the byte loop), and read_log.py prints whole lines only (its
"[stage N]" marker landed after a line the guest was still appending). Release builds are byte-identical.
Next candidates by size: the skinned-vertex kernels themselves (avk_pos_skin + avk_light_skin 4.5-6 ms at r101),
Part::whole (TA emit, 1.1-1.8), per-meshlet overhead in pass_positions (0.7-1.3), actor_submit preflight (~0.2).
**Correction (2026-09-29): the tour window 400..880 is not all gameplay.** At r101 entry it overlaps the
"Playing Manual" pages (IDSystem::unitTrans 1.56 ms, the sub screen's 434-unit ID pool; the lists fall back there on
be_flag 0xEF), and the other presets' windows start near their scripted prompts. Measured again at frames 900..1380
(release, everything landed through ACTOR_STATS_LEAN d21356f0; work = frame minus the modelled vsync spin):
r101 post-bell 37.2 / **35.8**, r100 east door 40.0 / **34.6**, r100 after the radio 50.5 / **49.9**, and **r101 entry in
play (Ganados approaching the square) 67.7 / 67.7** (render side 28.0, actors 12.7, game logic 9.3, world 9.1, UI 3.8,
copies 2.7). So quiet views are ~2 ms over 33.3 and the square with Ganados is ~2x, close to the kite fight (86.2).
The exact kernels above are real but small against that; the square needs the render budget work (characters,
world) and G. Use 900..1380 (or later) for tour benchmarks; ACTOR_STATS_LEAN (d21356f0, exact, STRICT
kite-r21slt1): actor_submit 2.26 -> 2.20 (post-bell), 1.38 -> 1.21 (kite).

Progress 2026-09-26 (night). **Corrections:** the evening figures were sampled on one `Frame_cnt` residue (trace
stride 8); over all ticks G_std is ~25.92 and G_fight ~29.61, so **G is not closed**, and every R / world cost arm ran at
FOG_FAR 18000 instead of the approved 25 m (square plan, "Corrections"; the stride 7 + 25 m re-baseline is running).
**The original world** (/root/probe/d367-agents/original-world-20260926/, try-it run original-tryit-20260926/): the full
GameCube render set of r101 (209 placements, 81 BINs, 135,813 triangles, 112 images, GC trees, per-frame light, 70 m
far) was never drawn by the game at the square: the P1 viewer was not the game, the P2 GX path ran out of heap 4, and
the "Original" quality package is itself reduced (PS2 trees, baked light, LOD biases, 25 m) and draws 10 of its 20
colour + mask pair packages invisible. Every "source renderer" image since 2026-09-25 is Standard quality. The data is
complete (offline reference renders); the GX path now runs in the game at the square (heap 4 minimum 679 KB free,
villagers, no HALT); Original mode halts after the bell on a KOS sbrk out-of-memory (sub screen). Light: the port's
unit-normal light matches a real-game Dolphin frame within 1-4% once the per-frame Filter00 (glow + contrast) is
added, so Filter00 is the visible gap, not the light maths. The sky dome and treeline sit 57-63 m from the square and
vanish only through the 25 m fog. Cost ladder (LADDER.md; estimates; the reduced Original mode's scenery measured
25.33 ms in F at 18 m): the original as is (70 m far) ~54.7 ms of world in F (57.9 V1E, 79.2 V3, 94.2 W1); invisible reductions (I11) 5.6 F / 8.4
V1E / 14.9 V3 / 4.6 W1; with a W1-class kernel ~2.1 F / 3.3 V1E / 6.3 V3 (2.9 with PS2 trees) / 1.9 W1. In V3 the GC
trees are 47.8 of 57 ms, so trees need a visible choice; hidden-placement culling (PVS, ~17 ms in F) is not built yet.
**World runtime rev 2 landed** default off (e69737e: COARSE_WORLD bits 16-128, the external world agent's renderer
contract rev 2; COARSE_NO_STD_SCENERY reclaims 599,424 B of heap 4 in coarse rooms, not for play recipes until door
and death captures show packaged scenery where the coarse path does not draw). **Route fixes** (7f1533d..c999bea):
(a) the SE random tables reached the Dreamcast big-endian on every disc (wild reads and stores, "Illegal SE No.",
extra draws of the shared game RNG); le_mirror now converts them (`--snd-random` for mirrors and derived archives);
switching the disc mirrors needs new logic-trace references and regenerated derived archives, scheduled while no lane
measures against the old references; the d367 / d362 / mirror-ss mirrors' bgm/doorse.dat and bgm/bio4midi.dat also kept GameCube headers in every
container but the first; the -rndle3 mirrors fix both (equal to mirror-w4q's). The switch (rev 4 in preparation, with
a guard that refuses a trace pair across it) moves every builder at once. (b) The r100 post-house call no longer soft-locks when the s20 ambush fills heap 4
(5fd2fe9: the call runs without the radio model), and cManager createBack takes a backed free slot when the source's
slot cannot be backed (5c33747). (c) The s20 route movie claims VRAM with a fallback pass when the pool has no hole
(072b574; user play 09-24: 6 of 10 s20 arrivals played the movie) and a failed open discards the interrupted frame's
scene (5d811f3; 0 fence stalls in 32 runs). (d) Warp rig: `kill` / `goto` verbs, r100-s20 presets, STALL_DIAG (1b2bcc3). (e) **r100 heap 4 for s20 and the full
ambush** (66b8edd): `room_smd.py release` strips the BINs the r100 Original + Standard packages already cover from the
block files (A1, +1,086,464 B) and the room archive (A2, +696,640 B more); at arena fit 13,312,000 the control fails
the s20 movie (0/571) while A1 plays it 571/571, spawns the full GameCube ambush and reaches the post-house call. The
data is private (lane-bugs/h4-data) and goes onto user discs only after the audit's missing proofs: an ambush STRICT
pair against a streamed-ambush control, tick-matched pixels in Standard and Original, a cost arm, and for A2 an
equalised s20 pair (the smaller archive moves the wall-timed s40 movie end). Smaller block files shorten the game's
block-swap stops (15/29/15 -> 9/17/9 ticks): that is load timing under the door rule, and running-tick logic must stay
STRICT with the stop ticks removed.

User decisions 2026-09-24 (later): (1) **r103: go.** Implement design-r103 PLAN (W8b room-archive compaction, W8c
textures + the post-bell radio stream, W8d census, W8e bell -> door -> r103; the r103 -> r106 exit fades to the title
on test discs). This is the end of the opening route. (2) **r100 Standard look approved and TREE_IMPOSTOR's 77 KB
(PT list) approved:** Standard stays the default and QUALITY_ASSETS=1 joins the M1 recipe after its gates (r100
Standard run, STRICT Standard vs Original, hw ms). With the Standard packages the r100 after-state crows fit (111 KB
spare). (3) **ACTOR_FOG_GATE's 1-pixel difference: delegated** ("make whatever looks good and is not too
computationally intensive"): prefer zero visible difference (cull only beyond far + a margin) unless the margin
costs more than ~0.2 hw ms against the 1-pixel variant; decided by the hwproject pair.

Progress 2026-09-24 (W8e, route A end): **r101 -> r103 through the real door works** (warp-r101-pbdoor4): the
post-bell radio call (stream 1:0x33, 5.2 s in full) closes on A, the door sound plays, DOORDEMO ends, r103 loads with
0 HALT/MISSING, em12 linked fresh (em15 -> em12), heap 4 free 1,127,104, VRAM 695 KB free, 0 missing textures. Two
port bugs every non-palindromic door hit: (a) 17f2aa5 `next_room` byte order (GlobalWork overlays u16 next_room on
next_stage/next_room_no; little-endian read 1:03 as 0x301 and HALTed); (b) fee2492 le_mirror converted only the first
container of bgm/doorse.dat (door sounds 1-11 kept GC headers; the door-sound read never completed) and of
bgm/bio4midi.dat (music archives 1-16: same latent fault for later BGM). Test rig: 1c9ae7d warp `dead` +
preset r101-post-bell-door (the bell's 40 dead ESL entries). Tooling: ac59b0f `discover --fix` (value-init,
slot-math; 124 of 130 sites across all modules fixed mechanically, all of stage 1). Next: W8f natural route (r101-bell
trg -> door), W8g perf bench in r103.

ACTOR_FOG_GATE's 1 pixel resolved without a trade: the framebuffer is RGB565 and the two values (blue 115 vs 123) are
one 5-bit step: a fully fogged polygon dithered against the undithered background, not a visible object. A far+margin
cull leaves the same residue wherever it culls, so the margin buys nothing: the gate stays at margin 0 (the cheaper
variant) and satisfies "no visible difference". Remaining gates before PERF: full STRICT tg0/tg1, n8 shots, hw quiet/n8.

User decisions 2026-09-23: (1) the fight floor (smoother-slower vs choppier-faster) is deferred until real numbers exist; it stays the PACE_FLOOR_FPS knob, default 15. (2) One early console timing run of a self-running r100 fight calibration disc is approved, purely to calibrate the hardware model (results on screen and on the VMU). All other console tests still wait for r100 -> r101 -> r103. (3) Gameplay-equivalent maths in game logic (SH-4 FTRV/FIPR for skeleton and foot IK) is approved as a measured option under the existing last-bit FP policy: deterministic but not bit-identical, with collision checked separately before adoption.

## 20 fps hardware budget (2026-09-23)

Game logic is a fixed 30 Hz tick: one update per frame (main.cpp, 2 vsyncs), with no delta-time scaling; only pad repeat timers use GetSystemVcnt. Rendering at 20 fps at the correct game speed therefore needs 1.5 logic ticks per rendered frame, so logic is a fixed per-second tax whatever the frame rate. At the modelled 25.8 ms/tick, logic alone is 77% of the CPU.

| Area | HW now (LD) | 20 fps budget (50 ms) |
|---|---|---|
| Game logic | 25.8 / tick (38.7 / frame) | ~15 / tick (22.5 / frame) |
| GC render front-end | 37.3 | ~3 (replace it; don't trim it) |
| Actors | 34.5 | ~7 (Leon full, Ganado tier + crowd rules) |
| Scenery | 31.4 | ~8 (shorter fog, coarser LOD, impostors, house shells) |
| UI / texture cache | 12.3 | ~2 (O(1) handles) |
| Copies + TA + KOS | 16.6 | ~7.5 |

User decisions (2026-09-23):
- **Approved:** shorter fog/draw distance, ~43 m -> 20-30 m ("most of the game is outdoors"). It must never hide an enemy within engagement range; trials pick the distance.
- **Approved, "more drastic":** Ganado crowd rules. Near 2-3 full detail; mid tier about 1/4 vertices, rigid parts, skinned every other frame; far tier a few hundred triangles, skinned every 3rd-4th frame. Leon always full; threats are never culled.
- **Closed, not possible:** visual-only simulations at half rate. Cloth and pendulum write the model parts chain, which feeds hit and attach points, and effects draw from the shared game random-number stream, so both change game state.
- **Decided (2026-09-23):**
  - Fog: 25 m confirmed ("34% fogged at 20 m seems right"). For reference, PS2 draws r100 to 78.9 m (EXP fog, end 263 m, ratio 0.70) and r101 to 38.4 m in most cuts; GC draws 42.7 m and 70 m.
  - House appearance: ~40% of the approach under the 25 m wall is fine; no per-object building fog.
  - Simplified house shells (item 21, MESH_TEXTURES=1): the mid mesh with a 512 VQ texture (66 KB per house), used everywhere with no near swap. -0.71 hw ms for FILE_01/17+18; ~-1.6 to -1.8 projected for all FILE_01. Step 5.
  - Effects: bring back native sprites for muzzle flash, blood and fire (+0.5 to 1.0 hw ms), together with EFFECT_LEAN. Step 4.
  - Cutscene subtitles: no, for now.
  - **Historical (architect review 2026-10-03):** the Low / Original mode items below are not current scope. Current
    scope: gore and effects kept, Standard quality only, `QUALITY_PICKER=0` (no boot picker; play recipe in the
    checklist). Gains that have since landed (kernels, batching, preloading, effect sprites) are not future
    options; do not count them again.
  - **Low setting mode (requested 2026-09-23):** a pre-game debug-menu toggle (Normal / Low, plus per-feature switches) that turns on the aggressive options: full replacement of the GC model drawing path, the Leon rebuild plus low-poly Ganados, and occlusion.
    - Normal targets 20 fps; Low pushes toward 30 fps (33 ms hw).
    - The switches are runtime, not compile-time. Only the selected asset set is resident. The logic trace is STRICT across modes.
    - In design at /root/probe/d367-agents/design-lowmode, design-scenery and design-ganado.
  - Outlook: all planned work lands at ~50-65 hw ms in quiet views, so 20 fps is the target. 30 fps would need every area near its floor at once.
  - **Low mode decisions (2026-09-23, design at /root/probe/d367-agents/design-lowmode):**
    - Estimates: Low is worth -2 to -4.5 hw ms quiet and -7 to -13.5 in r101 fights. It's a safety margin, not 30 fps.
    - The full native model path (-9 to -13 hw ms, bit-exact, records held in the existing 64 KiB slab) is ON in Standard.
    - Heavier Low levers approved: flat Ganado lighting; a draw-side crowd rule; a scenery-only cull at 18-20 m, with the fog kept at 25 m, only if it doesn't visibly pop.
    - Decided 2026-09-23: crowd rule **N=2** (the nearest 2 Ganados at near/mid detail, the rest at the far tier, none hidden; 8-Ganado fight 31.5 vs 32.1 hw ms at N=6, design-ganado 08). **FTRV render maths: yes** (render-only transforms; the logic trace stays STRICT). **Flat Ganado lighting: yes**, default in Standard (~-5.8 hw ms in the 8-Ganado fight, model estimate; verify on the hw model). **Heads always detailed: no** (heads follow the body's L1/L2 level).
    - A Low effect draw cap (draw side only): yes.
    - Thermal scope, self shadow and cast shadow stay in the build.
    - The quality choice is remembered on the VMU.
    - Picker: once per boot, at the first title main menu, in the game's message window; per-feature submenu in test builds only.
      - Built (`QUALITY=1`, default off; `port/dreamcast/game/quality_picker.cpp`, `platform/quality.{h,cpp}`): after Start, "Graphics quality" / "Standard" (budget-first, the default) / "Original" (faithful); up/down + A (attr 0x00800000, vertical choices). `/cd/dc/quality.txt`: `mode=standard|original`. Fixture proof w10q9-picker: no record -> Standard highlighted first; Down -> Original, A picks, record stored, frozen at titleExit.
      - The choice is the 32-byte `R4CF` record (`Re4dcQualityCfg`) through `re4dc_quality_cfg_load/store`: weak in-memory versions until the VMU layer (design-vmu S5) links the RE4DCCFG file.
      - Not visible yet: GX is a stub on the DC, so no `cMes` text renders anywhere (the picker, prompts, card Yes/No). The native message renderer (the game's own font) is W11's, after its MES/getMes fix.
    - Leon's face bones: PS2 FMV replaces most story cutscenes, so merge them always in Low, unless a route event still in-engine shows Leon's face up close (being checked).
    - Occlusion at the 25 m fog is ~0.1 hw ms for 32.7 KB heap: dropped unless the final scenery design shows more.
  - A bottom-up estimate puts Standard at ~73 hw ms quiet / ~80 in the r101 fight, above the earlier 50-65 outlook. Stacked step 3-5 measurements will settle it.
  - **Gore stays** ("keep gore don't remove it"): CUT_GORE (r103 corpses and the r100 gore object via the JP path) is rejected and must not enter the recipe. That route now relies on the r103 corpse constructor alias (55c0a5b). Safe cuts are down to FX_LEAN (foot shadows, about 0.1 ms). Particle/decal caps aren't possible (shared RNG), and screen filters stay (about 0 ms; some set game flags).
  - Added to the lane: outdoor occlusion/PVS (hide houses and trees behind buildings; est. -3 to -6 hw ms in r101/r103), step 5. Leon render rebuild with fewer skinned bones (render skin weights only; the game skeleton, attach points and hit zones untouched; ~5-6 -> ~3 hw ms), step 3. Lower-poly Ganado render meshes (heads kept), step 3.
  - **Rejected:** reduced animation/skin update rates for any actor ("might throw off gameplay"). Crowd tiers vary geometry and shading only; every actor's pose updates every frame. This supersedes the earlier "skinned every other/3rd-4th frame" crowd tiers.
- **Enemy/object census (aligned):**
  - Take the SAFE cuts: r103 corpses and the r100 gore object off via the JP path (CUT_GORE); effect and decal caps; no foot shadows; car and police props static.
  - Cap concurrent active Ganados in r101 (ACT_CAP, N=4/6/8 trials, ~12 hw ms estimate). Parked Ganados stay alive for every counter; engaged or visible threats are never parked. (Historical r101 item; capped arms throttle parked Ganados, see "Baseline correction" under the 30 fps rethink.)
  - Never cut: the r100 s03 Ganado; ESL entries 3/4/5 and 0x25; any r101 initial Ganado; the r101 kill/timer/wave logic; linked breakables.
  - Don't remove wave members: phantom kills (5 per wave) would shorten the fight.
  - Found alongside: with 10 Ganados on screen, texture_package.cpp costs 71.5 ms/frame in Flycast. It goes to the texture-hitch fix (preload per room, O(1) handles).

## Asset decisions

- **Trees:** PS2 trees for r100, with the source key texture replaced by the
  PS2 bark (VQ).
  - The worst village view drops from 61.7k to 35.7k strip corners.
  - A "groves" variant (one PS2 tree per GC trunk) costs about 2.5 ms more
    scenery time on hardware. It was compared in game (LD vs LE) and rejected:
    the visual gain is negligible.
- **PS2 static scenery** is the same geometry as GC, so there is no gain there.
- **PS2 character meshes** are not lighter (em12: 411 KB vs 407 KB). Actors
  instead rely on:
  - LOD;
  - moving non-animated room objects to the static prelit path;
  - 16-bit UV.
- **Blender** (5.2, Windows, headless) is used for measurement, planar
  decimation of static BINs and comparison renders. Its collapse and far-LOD
  output lost to the converter's own QEM LOD.

## Performance plan status (updated 2026-09-23)

Flycast ms are for r100, frames 2401-2520. The "work" figure excludes vblank
idle. Hardware figures are estimates until the projection model and the
console calibrate them.

| # | Item | Flycast effect | Hardware effect (est.) | Status |
|---|---|---|---|---|
| 1 | Instanced per-BIN scenery, source-to-native static path | 1390 -> 559 | large | Done (5dd04d3, ed9393c) |
| 2 | Remove per-vertex libcalls | 559 -> 434 | similar | Done (e62cc4b) |
| 3 | NO_EH; also frees 360 KB for heap 4 | 434 -> 409 | small | Done (f10ed71) |
| 4 | Meshlet fast path + dense actor path | 409 -> 234 | large | Done (02d5a0f, bfa1452) |
| 5 | Spatial meshlet packages | 234 -> 217 | medium | Done (e62cc4b option) |
| 6 | PVR pipeline, fast wake, lean bridge | 217 -> 200 | overlaps render on hardware | Done (a1db43d) |
| 7 | Scenery LOD + source fog + far cull | 200 -> 150 | scenery ~9-11 ms | Done (64b25dd) |
| 8 | Fast actor path + deferred skinning | 150 -> 117 (actors 51 -> 18) | actors ~16 ms | Done (4fa839d) |
| 9 | PS2 trees | -2.5 ms work, heap +370 KB | worst views 61.7k -> 35.7k corners | Done; tooling committed (7a7036a) |
| 10 | Async present (PVR_PIPELINE=2, private KOS) | removes part of ~19 ms pacing waste | overlaps CPU and render | Done: LF, adopted as default (neutral in Flycast) |
| 11 | Actors pass 2: static room objects, whole-part LOD, 16-bit UV | ~18 -> ~8 | ~16 -> 3-5 | In progress |
| 12 | Game CPU: SH-4 matrix kernels, rotation cache, -O2 on hot objects | game-side 13.9 -> 9.7 (wall 116.8 -> 100.1) | logic 25.8/tick on hardware (model); target ~15 | Done (6e79b70), STRICT. Next: bit-exact faster math, visual-only sims off the tick |
| 13 | FP 6B (contract-off + FDLIBM; render-only objects exempt) | ~0 | ~0 | Done (6e79b70), user-approved float-only drift; new STRICT baseline |
| 14 | Memory-copy audit (~15 ms) | -7.5 (COPY_LEAN) | more (cache thrash) | Done (de03f28); validating on LF |
| 15 | GC render front-end removal (objTrans, light setup, normal matrices, draw-plan walk) + direct TA meshes | -6.4 (FRONT_LEAN) -3.6 (MESH_DIRECT) | similar | Done (de03f28); validating on LF |
| 16 | UI VRAM diet -> 2 MiB vertex bank | 0 | required: r100 needs ~1,031 KB of TA params per frame, overflowing 1024 KB | Done (700e2d0, UI_VRAM=1 + TA_VERTBUF_KB=2048 + tex-vq3) |
| 17 | Hardware projection model (pairing + I/D-cache simulation) | - | LD = ~158 ms on hardware (1.65x Flycast) | Done; see Hardware projection |
| 18 | fsrra, movca.l staging, SQ-direct writes, instruction scheduling (OC-RAM and pref dropped by the model) | ~0 in Flycast | fsrra -1.4, SQ/movca.l -7 to -8, scheduling up to -29 ceiling | Assigned (frontend30 pass 2, actors) |
| 19 | I-cache hot/cold code layout | ~0 in Flycast | model: +1.2 ms worse; ideal packing only -1.8 | Dropped (the per-frame code footprint of 216 KB is the problem, not layout) |
| 20 | Tree impostors beyond ~12-15 m (16 views x 128, 4bpp VQ, 82 KB VRAM) | - | -1.0 to -1.2 (heavy mean 8.62 -> 7.39-7.64 ms with PS2 trees) | Designed; needs a batched punch-through quad path. Flat at 8 m |
| 21 | Lighter near-camera FILE_01 houses (5.18 of 8.6 ms hardware scenery; 17.1k corners in 3.9k strips) | - | automatic Blender reduction only -0.17 at acceptable error; new low-poly shells with a baked texture could save most of ~4 ms | Open: needs package-supplied textures + new house meshes |
| 22 | Bytes-based TA guard + 32-byte limits (Sega rules) | 0 | correctness | After #16 |
| - | Costs being added: music + SFX, FMV decode (cutscenes only) | +1-3 ms in gameplay | +1-3 ms | Audio and cutscene agents |

**Projection.** Items 10-15 take Flycast work from ~96 ms to about 55-65 ms
(15-18 fps), which clears the ~15 fps console gate. Items 17-21 target the
rest of the way to 33 ms on hardware.

## Plan to 30 fps

Historical (2026-09-23; architect review 2026-10-03): steps 2-5 below have largely landed (FP 6B + GAME_O2,
FRONT_NATIVE / FRONT_LEAN, COPY_LEAN, PVR_PIPELINE=2 + PACE_CATCHUP, UI_VRAM + 2 MiB banks) and are in
build-r21.sh; do not count them as future gains. The current plan is "30 fps rethink" above and D367_SQUARE_PERF_PLAN.md.

Steps are ordered by expected frame-time gain.

1. Actors, second pass: static-path room objects, whole-part LOD, 16-bit UV.
   Target about 8k triangles, about 3-5 ms on hardware.
2. Game-side CPU:
   - proven-identical SH-4 matrix kernels, PS alias links and the room index
     (about -6 ms);
   - 6B then O2;
   - removing GC render front-end work the native renderer makes redundant
     (objTrans about 13 ms, GX stubs, light setup).
3. Memory-copy audit (about 15 ms).
4. Async present (PVR_PIPELINE=2, KOS patch) and fixed 30 fps pacing.
5. UI VRAM diet, so 1.5-2 MiB vertex banks fit.
6. Hardware tuning after the first console session: cache layout, prefetch,
   OC-RAM.

## Controls (done: e024e19, 0a33d0c)

Standard pad:
- Stick, A, B, X, Y, Start, L and R map directly, with the GC PADClamp ranges.
- In free movement the D-pad is camera look, and a short tap of D-pad down is Z (map).
- In scope or binoculars, D-pad up/down zooms.
- In menus, aiming and QTEs the D-pad is the D-pad.

Dual-analog pads use the second stick as the C-stick, and C/Z as Z.

Debug traps (L+Start, Z item-maker) are blocked unless DEBUG_PAD=1.

0a33d0c fixes stick aiming on little-endian targets. Before it, only the D-pad aimed.

The glyph swap is still to do. The 2026-09-26 glyph survey (private catalog `/root/probe/d367-agents/ui-glyphs/CATALOG.md`, mockups in `re4-assets-private/ui-glyphs-20260926`) corrected this line: no Z glyph or Z wording exists, but ONE C-stick glyph is on the route: r101_035.EFF tex 0x89, the binocular ZOOM hint of r101_Event00 (first r101 pass), packaged in every warp fixture set but not in d354v7-fixtures. The C-stick is also named in ss_file #1 msg 4 (Playing Manual 1, camera page) and drawn in the f01e manual picture. The A/B/X/L/R/stick glyphs are in core.das #25 and the ss_map/ss_cmmn/ss_cap hint strips; the map strips and the manual pictures are not packaged on the port today. File-reader text is drawn in one frame (attr 0x40: no typing time), so rewording it cannot move a trace. The look (GC art recoloured vs DC-style buttons), the binocular glyph (D-pad + dual-pad zoom change vs per-pad-kind switch) and the wording are user decisions.

## Route plan (frontier units)

**Milestone 1 disc verified as an r100 disc (2026-09-23, 84fc8ff, canonical README recipe incl. NATIVE_MES, SUBSCREEN_OVL, VMU_SAVE, actor tiers).** Title (2026 art) -> picker (text visible, no backdrop yet) -> intro 1971/2360 frames -> s40 1175/1175 -> radio call (subtitles visible; transceiver video panes blank) -> r100 play (~15 fps Flycast) -> inventory open/close (backing hash ok) -> typewriter save to VMU (RE4DCS01A, 17 blocks). Heap 4 at r100 entry 8,988,032 B; s40 heap 433,824 B; lowest in-play VRAM free 18,632 B. 0 HALT/FAULT/MISSING. **Blocker for r101 (fixed, 9bba3c8):** the east-walk area-block swap (r100_03 ARAM_TO_MRAM) read stale data because the port had no ARAM backing (ARQPostRequest copied nothing). Now GD-ROM stands in for ARAM, with a blocking re-read of the unit file on ARAM_TO_MRAM (same logic tick, STRICT). **r101 first-visit call reset (fixed, 4980a40 + 976c93d, SS_POOL_HIGH=1 in M1):** the effect pools, LightMgr array and primitive buffer are placed above the sub screen's swapped window; the call and the file screen after it now run. **r100 westward reload (fixed, a0c3079, NATIVE_PKG_HIGH=1 in M1):** native packages are carved from the top of heap 4, so FILE_01 reloads after walking back west (area 1: 4 -> 15 fps Flycast, the source fallback is gone). **r101 scenery (W9b landed, 8332a22):** the staged v3 packages are adopted and draw; r101 was then VRAM-bound: its textures were never VQ, because the overlay came from r100 logs only. **Fixed by tex-vq6 (46b9f4f):** the pipeline 00-vq overlay covers r101 (61 images, 4.52 -> 0.69 MB). The square fight runs at 10.1 fps Standard / 9.4 Original in Flycast (test build; was stalled), and Standard vs Original is STRICT. Landed default off, not yet in the recipe: VRAM_PAGES (ea1e2d3; needs hwproject), items 20+21 (9951d17), QUALITY_ASSETS (010169c; r100 proof + hw ms + the 77 KB PT-list decision first). **VRAM:** 161 KB of the r100 gap is a 2 KiB page-alignment pad per texture (KOS pvr_mem in-VRAM headers defeat the page check); page allocator (option A) in progress; a single-bank PVR layout (option C, +1.2-1.5 MB pool, rules out TA_DOUBLEBUF) goes to the user with its fps cost. User trims for Standard VRAM: r101 remaining grove atlases to 8 views + shells 64 VQ; r100 tree atlases re-baked at 8 views.

Assessment: the recovered game reaches r100 gameplay. r101 and r103 have never
run in it; "r101 works" commits are the separate room viewer.

| Unit | Work | Status (2026-09-23) |
|---|---|---|
| W0 | Frozen private baseline | Done (private tree; hashes in frontier notes) |
| W1 | Extract route files from the debug ISO; build r101/r103 DARs; compact em15/26/28/21 | Done: tools ded299f; mirror complete for all 18 route files; em15 resident 3.86 -> 1.14 MB |
| W2 | Register the enemy modules | Patch ready (em15/26/28/21, slot audit). Held: +282 KB image comes out of heap 4, lands with W4 |
| W3 | First r101 entry fixture and measured census | Entered r101, then HALT: heap 4 short (s30 event 2.37 MB; em15 motion keys). Census: room archive 5.47 MB = 62% of heap 4 |
| W4 | Fit r101 memory and VRAM | In progress: ~1.2 MB short after dropping cutscene assets. Levers: event code without cutscene assets, room archive GC-render payload release, em15 hot motion |
| W5 | r100 events | Not started |
| W6 | Door lifecycle: relink-overlap hazard, module .bss reset, ARAlloc reset, KOS headroom | Done (a575a76): r100->r100 relink round trips repeat with 0 heap/VRAM/KOS change; 0 ms. Reload/continue hangs in SndRoomBgmLoad until audio lands (W12) |
| W7 | r101 events with FMV presentation | Working in Flycast: the r120 intro and r100 s40 play as 288x192 PS2 movies with audio; the source effects apply and gameplay continues (c6). Open: only 14-15 of 29.97 fps shown; s03/s20/s30/s41/s43/s44 not yet exercised; 57 KB heap margin during s40 |
| W8 | r101 -> r103 | **W8b-W8e done** (r103 room archive compaction + VQ textures, census, bell -> radio call -> door -> r103: warp-r101-pbdoor4; fixes 17f2aa5 next_room byte order, fee2492 multi-container doorse/bio4midi); W8f natural route and W8g perf next. Was: planned (design-r103/PLAN.md). Transition needs no new systems: bell FMV r101s30.sfd (already staged), the source re-opens the exit, W6 door code. Risks: r103 scenery ~2x r100 (p50 14.2 / worst 30.5 hw ms at 25 m fog); cow-pen worst view ~94 hw ms Original / ~61 Standard before corpses and animals; 10 corpses may need a bit-exact one-pose skin cache; heap 4 fits only with r103 room-archive compaction (+1.1-1.55 MB), VRAM unmeasured. Units: W8a offline fit sheet, W8b archive compaction + W9 release, W8c textures + stream (1,0x33), W8d r103 debug-start census. User decisions 2026-09-23: r103's exit to r106 (not on the disc) fades back to the title on test discs; animals (cows, chickens, dog) get the Ganado Standard treatment once measured; the Standard asset rollout rebuilds r101 and r103 together (done: 49d1e17; sheets published). Later decisions: r101's well (BIN 45) is excluded from house shelling (a landmark in the fight area); r100 uses 128x128 house-shell textures, like r101, to fit its full VRAM pool |
| W9 | r101/r103 scenery packages | Tooling done (`convert_room_bins.py --smd`, `room_smd.py release`, `ps2_trees.py --room`; recipe in `tools/d367/README.md`). Packages: r101 1.27 MB with the PS2 trees, r103 1.39 MB. The release frees 1.59 MB (r101) or 1.55 MB (r103) of GC geometry from the room archive, a net +0.32 MB (r101) of heap 4 after the package. With it, r101 gets past the em15 motion-key HALT and renders in Flycast (evidence `w9-r101-native-released-m2`); the unreleased control still halts. Model estimate (worst view, 70 m fog far): 67-71k strip vertices, 19-25 ms hardware, so over the 10 ms budget; median 7-10 ms. Flycast ms/frame not measured yet: the fixture's present counter stalls in r101 |
| W10 | GDEMU image, disc IO | GDI boot done (93a03e3). MOTION_FAST_READ (a09fd4d): r100->r100 door 24.1 -> 16.0 s on the old recipe. IO_PROBE telemetry + fs_read/fs_open/genwait wraps: on the old recipe the other ~10 s was 63 texture-package fs_opens (~159 ms each, iso9660 rescanning the flat tex directory), which the LFV recipe's TEX_RESIDENT fan-out already removes. LFV + MOTION_FAST_READ: door 6.8 s, of which 2.7 s is 575 misaligned 16 KiB-bounce texture preload reads, 0.9 s source DVD, 0.6 s opens, 0.3 s motion. Hardware-safe design (design-doorload/DESIGN.md): Flycast's door says little about hardware (~2,000 mostly single-sector GD commands, 12.1 MB); estimated today GDEMU 8-17 s, GD-ROM 20-40 s. Queued units: IO_PROBE counters + door summary, TEX_KEEP (textures resident across a room change; Flycast 6.85 -> ~3.4 s), aligned static-mesh reads, DVD wait/reopen fixes; then per-room texture and motion packs, and a GD-ROM disc layout. Target GDEMU ~5-9.5 s. Async/read-ahead and GD-DMA into VRAM rejected. U0 (IO counters) done: the canonical-recipe door is 10.22 s; U1 TEX_KEEP gives 7.2-7.7 s. Confirmed by the user 2026-09-23: the game counts door-load wait frames against wall time, as the original does (it varies with disc speed), so a faster door legitimately shifts the post-door RNG and timers (44 -> 43 frames). That isn't a sequencing change, and door frames are not pinned. Door-speed units prove themselves with a door-equalized arm (a test-only pad to the baseline frame count) that is STRICT over the whole run; a trace pair crossing a door is valid only with matched door frames |
| W11 | Inventory backing and retry | SUBSCREEN=1 landed (8878e3d, le_mirror formats 153dd7b): inventory/transceiver open and close over a saved 3 MiB backing window. Grey-screen root cause fixed: room demand pools (cEm/cParts/cModelInfo/cObj) had headers inside the zeroed window, and EmMgr growth wrote a heap cell into .text; the pools are now frozen at open and thawed at close. SS_POOL_HIGH=1 (2026-09-24, 4980a40 + 976c93d, in M1): allocations the sub screen loop keeps touching are allocated above the window: the effect pools, LightMgr array and primitive buffer. This fixes the r101 call reboot and the type 0x40 file-screen reset. It is STRICT outside the swap interval, and knob-off images are identical. r100 x3 open/close on the m1 recipe + TEX_RESIDENT (w11-ss17-m1-inv3): hashes ok, no HALT, heap 4 and player state identical, ~88 ms/frame before and after; ~1.4 s texture re-preload per close. The .text-change flag was KOS's IRQ temp stack below irq_save_regs (benign, present before any sub screen; w11-ss18-m1-textdiag). Open: ROUTE_MOVIES halt at main.cpp(548) ~3600 vblanks into the r120s00 intro (cause: the 60 s haltExecCheck during long movies, wedging the b50cfa3 YUV path; port-side fix in review). Death/Continue x3 in r100 passes on the m1 recipe (08d51b9 fixture; w11-ss20-m1-die3): heap 4 flat, VRAM 0, BGM restarts, player state identical. Open: r101 death (needs the movie route), VMU save (designed: design-vmu/DESIGN.md; virtual memory card over the VMU, game card.cpp unchanged, LZ4-style saves 16-36 blocks, RE4DCCFG 2, RE4DCSYS 2, test-build RE4DCDBG debug slot saved with L+START and loaded as FILE 20; blocker S0: the typewriter save's ~250 KB data swap halts via re4dc_missing unless it uses W11's VRAM backing; user decisions 2026-09-23: the game's format prompt never formats the VMU, a nearly full VMU overwrites in place, enemy-list delta compression off until real save sizes are measured; implementation S0-S9 started), merchant, r101 inventory, ~175 KB SUBSCREEN image cost |
| W12 | Audio (music and sound effects) | Backend committed (79d3252, AICA_AUDIO=1): GC sequencer + SFX engine on the AICA, ~0.2 ms/frame, fixes the continue hang. Next: offline bank conversion (5.3 s load-time CPU today), fixed per-room AICA layout, st002/st008 streams |

## Working rules carried forward

- Shared checkout: never broadly stage, reset or clean.
- Commit only reviewed owned hunks. The 75 inherited dirty files stay as
  they are.
- Private assets and evidence stay out of Git.
- Use new evidence directories; never overwrite accepted evidence.
- Toolchain: KOS `kos-re4dc-d336` with GCC 15.2.
