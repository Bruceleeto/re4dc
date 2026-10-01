# Lane crowd

Rules: port/dreamcast/docs/D367_WORKSTREAMS.md. Branch lane/crowd, tree /root/work/lanes/crowd, evidence /root/probe/lanes/crowd.

## Goal

User, 2026-09-30: "We already know the Ganados need to be optimized + we need to draw less of them on screen."
- A. Exact per-Ganado cost (render only, logic STRICT, look unchanged).
- B. Draw fewer Ganados (render only; every Ganado still exists, moves, animates its skeleton and collides): options
  priced in hw ms with before/after look sheets, for the user to choose. Looks are the user's call.

## How the Ganados are drawn in the play build (read 2026-09-30)

- The play recipe (tools/d367/build-r21.sh) sets ACTOR_TRANSACTION=1 + COARSE_SOURCE_ACTORS=1: every actor gets its
  source emTrans (visibility, material animation, OTs); at the OT callback commonModelTrans calls
  re4dc_actor_transaction_draw (coarse_actor_transaction.inc), which for a Ganado plans the cast mesh
  (coarse_actor_owner_ganado.inc: owner_ganado_bind, four cast chunks per appearance), checks semantics (immutable
  chunk proofs, material certificate), acquires (texture pins, workspace, palette bank; owner_ganado_palettes =
  the FTRV bone + palette build), preflights every run, then submits the runs per OT pass
  (re4dc_actor_submit_owned_runs -> one_chunk: fog gate, positions kernel, meshlet outcodes, emit).
- re4dc_coarse_ganado (coarse_ganado_cast.cpp's own adapter, with COARSE_PREGATE) is never called in this build
  (COARSE_CROWD lines: candidates=0): COARSE_PREGATE / COARSE_GANADO_LIMIT do nothing for the play build's Ganados.
- The cast chunks draw with constant colour and carry no LOD levels, so CROWD_LOD / CROWD_FLAT / CROWD_NEAR* /
  CROWD_MID_M (all set in the recipe) change nothing for them either: every drawn Ganado is the full cast mesh.
- A Ganado beyond the 25 m fog gate or wholly off-screen still pays bind, semantics, bones, palettes, preflight and
  the per-chunk gate (the fog gate and the meshlet outcodes run after the palettes are built).

## Knobs (game/crowd.mk, all default off)

- CROWD_CULL=1 (A, exact): the owner path's whole-actor COARSE_PREGATE. After admission, a Ganado whose every visible
  chunk is provably off-screen is not acquired or submitted (choice 2, no record; both passes return handled).
  =2 check build: nothing skipped, "CROWDCULL" lines count would-cull actors that emitted (must be 0).
- CROWD_CENSUS=1 (diagnostic): "CROWDC" per-frame lines in the UI-frame window 900..1380.
- CROWD_DRAW_MAX=N / CROWD_DRAW_M=D (B, look change): not drawn beyond the N nearest / beyond D metres.

## Tools (tools/d367/crowd)

- cbuild.sh <label> [knobs]: one arm of the play recipe (MODE=rel: release + PC_SAMPLER; MODE=trace: STRICT build),
  fresh objdir, ext4 copy of play-actor-bundle-20260928 (verified against its SHA256SUMS).
- cprep.py <label>: harness program candidate-cw<label> (programs-crowd.json).
- chw.sh <label> <name>: hwproject at the r101 entry tour (tour/rel-r101-entry-pw.json, frames 900..1380, stride 15).
- crun.sh <label> <name> [s]: a Flycast run (Git Bash) with screenshots.

## Why most Ganados take the source path at the r101 entry (census, 2026-09-30)

- The owner path finds a Ganado's material-lifetime record (actor_lifetime.inc) through re4dc_actor_role_bindings ->
  find_info. Records are adopted only at setTplAddr / model load. In the tour fixture (tour/rel-r101-entry-pw.json)
  the live info count falls from 53 to 23 by UI frame 840 (revokes 0; ~300 adopt failures with reason 0), so most
  Ganado draws end in ATD event 22 (find_info failed) and fall back to the source per-part path
  (re4dc_actor_submit + per-vertex lights: the avk_light_skin / build_lights rows of the profile).
  Census cen3/cen6 (tour): ATD g=1 attempts 9262, no-plan 7590, admitted 1672, find_info failed 35896 (all passes).
  Kite fixture (cen5/cen7): no-plan 23, nearly every Ganado admitted.
- CROWD_READOPT=1 re-adopts a Ganado's info at plan time when find_info misses (38 ok / 50 fail in the window);
  with it every attempt is admitted (cenr1: e16 = 9262). LOOK CHANGE at the r101 entry: those Ganados go from the
  source GC mesh (lit) to the approved cast mesh (constant colour, Flat Ganado lighting = the Standard). Needs a
  look sheet and the user's acknowledgement before it lands.
- In frames 995..1369 of view e every Ganado is beyond 25 m: drawn 0, empty 5 per frame (setup paid, nothing emitted).
- CROWD_CULL alone (cu1) changes nothing at the tour entry: the skip sits after admission, and the Ganados weren't
  admitted. It needs READOPT (arms r1c, r1n4, r1n2, r1d12).

## Far tier (design, in progress)

- bundle-lean (/root/probe/lanes/crowd/bundle-lean, cast_bundle.py LEVEL=lean REVISION=revision-20260926): external
  cast v4-fit lean, 5 appearances (em12-01, em15-00, em15-03, em15-04, em15-0b), ~626 tris each, same texture
  1279a218-f8cb0063, skin_stream_bytes 17064. bundle-cons equals the play bundle (const qualifiers only).
- Runtime choice: re4dc_actor_plan_ganado picks the far namespace for a Ganado beyond CROWD_FAR_M (default off).
  The far chunks need their own immutable asset IDs (coarse_actor_geometry_once.inc kActorImmutableChunks=46 is
  full: Ganado 9+a*4+role, hair 29..42), so the table grows by 20 for the far tier (and by 4 for a PS2 near em15-00).

## State and next step

- Detached queues (tools/d367/crowd/cqueue.sh; log /root/probe/lanes/crowd/logs/queue-jobs-<b>.out, per job
  logs/hw-<name>.out + hw-<name>.log; evidence C:\Flycast-Evidence\re4-dreamcast\hwmodel-cw-<name>):
  - jobs-b1 PID 107850 (04:38): c0, r1, r1c, ck, r1n4, r1n2, r1d12 at views l/e/s.
  - jobs-b2 PID 131103 (04:58): far / PS2 tier arms f12, fn3, p2, p2n3 at l/s.
  - jobs-b3 PID 144220: ck2 (cull check with the reason logged) at l/s.
  - jobs-b4 PID 145600: STOPPED by me at 05:15 (C: fell to 15 GB with 7 traced runs at once); its c0-b run killed
    (Flycast PID 4424), disc + partial evidence deleted; ck-b finished. Rest moved to jobs-b6.
  - jobs-b6 (after.sh PID 151969, starts when b1..b3 end; 3 workers, MINFREE 22): bell fight b and kite k views for
    every arm, ck3 / r1c2 (exact cull).
- Look-sheet builds z<arm> (looks.sh build; CROWD_FREEZE_AT=1100 AT2=2280 HOLD=40): kite t=1099, tour t=2279.

## Numbers (image, build, evidence)

Views: e = r101 entry tour 900:1380, l = r101 entry tour 2040:2520 (worst), s = r100 s20 1240:1720; all stride 15,
release + PC_SAMPLER play recipe at 942a8847 with ARENA_FIT_KOS_BYTES=147456.

| Arm | Knobs | e | l | s | Look |
|---|---|---|---|---|---|
| c0 (control) | none | 77.82 | | | today |
| cu1 | CROWD_CULL=1 | 77.76 | | | today |

c0 view e profile: actors 11.97 ms (re4dc_actor_submit 3.16, Part::whole 1.24, build_lights 0.73, pass_positions
0.68, owned_source 0.54); render avk_light_skin 2.22, avk_pos_skin 2.03 (hwmodel-cw-c0b).

## Ready to land

(none yet)
