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

## State and next step

- 2026-09-30: control c0 (play recipe, release + PC_SAMPLER) profiling (hwmodel-cw-c0); census arm cen (CROWD_CENSUS=1
  CROWD_CULL=2) running (scenario cw-cen1); CROWD_CULL=1 arm cu1 built.

## Numbers (image, build, evidence)

(pending)

## Ready to land

(none yet)
