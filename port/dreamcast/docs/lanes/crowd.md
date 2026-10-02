# Lane crowd

Rules: port/dreamcast/docs/D367_WORKSTREAMS.md. Branch lane/crowd, tree /root/work/lanes/crowd, evidence /root/probe/lanes/crowd.
Private outputs (sheets, bundles): C:\Game Dev\Emulators\re4-assets-private\crowd-20261001 (HANDOFF.md, SHA256SUMS).

## Goal

User, 2026-09-30: "We already know the Ganados need to be optimized + we need to draw less of them on screen."
- A. Exact per-Ganado cost (render only, logic STRICT, look unchanged).
- B. Draw fewer Ganados (render only; every Ganado still exists, moves, animates its skeleton and collides): options
  priced in hw ms with before/after look sheets, for the user to choose. Looks are the user's call.
- Coordinator additions: PS2 em15-00 for the near Ganados + the cast's lean level for the far ones (runtime tier
  choice, default off); gore stumps / alternate hands as section replacements in coarse_ganado_cast.cpp.

## DECISION FOR THE USER: draw-fewer options (2026-10-01)

hw ms = hwproject.sh hardware projection, ms/frame, release play recipe (build-r21.sh + PC_SAMPLER, ARENA_FIT 147456,
ASSETS play-actor-bundle-20260928; tier arms add the far / PS2 headers), lane/crowd code. Views (stride 15):
**k** r101 kite (kite-mesh-fixture-r21.json) 900:1380, ~5 Ganados within 5 m (the Ganados-on-screen view);
**l** r101 entry tour 2040:2520 (worst tour view; 5 seen, 2 at 12..25 m drawn, 3 beyond 25 m);
**e** r101 entry tour 900:1380 (every Ganado beyond 25 m); **b** r101 bell fight 1240:1720 (enc fixture; 1..4 drawn);
**s** r100 s20 1240:1720 (no Ganado reaches the owner path in this window: every arm 73.5..73.8, not repeated below).
Noise between two runs of one arm: about +-0.5 ms (k, b), +-0.3 (l, e). Every kite/tour arm ran the same fixture on
the same kite base disc, so all ran the base disc's own dc/padscript.txt (58 entries): A/B comparable.

| Option (knob) | k | l | e | b | Look (sheets in crowd-20261001/sheets) |
|---|---|---|---|---|---|
| today (c0) | 95.8 | 107.0 | 77.8 | 77.2 | - |
| exact baseline g1 = CROWD_READOPT=1 + CROWD_CULL=1 | 95.1 | 106.8 | 78.5 | 76.7 | tour: the 2 mid-distance Ganados go from the lit source mesh to the approved flat cast mesh (0.2 % of pixels, tour-2279-readopt-fogskip); kite 0.00 % |
| **+ CROWD_FOGSKIP=1** (g1f) | 93.7 (-1.4) | 103.2 (-3.6) | 75.7 (-2.8) | 77.5 (+0.8) | no pixel changed at either held tour frame (Ganados past the fogged View far + 2.5 m, where the GC clips) |
| **+ CROWD_DRAW_MAX=2** (g1n2; only the 2 nearest drawn) | 88.7 (-6.4) | 104.1 (-2.7) | | | kite: the 3rd..5th Ganado vanish (1.1 %, kite-draw-fewer r1n2) |
| + CROWD_DRAW_MAX=4 (r1n4 vs r1c) | -2.3 | -0.2 | | -0.1 | kite 1.7 % (kite-draw-fewer r1n4) |
| + CROWD_DRAW_M=12 (r1d12 vs r1c; none beyond 12 m) | +0.1 | -3.0 | | -0.1 | tour: the mid Ganados vanish; kite 1.6 % |
| **CROWD_READOPT=2** (Leon too; r1c2 vs g1) | -0.1 | -8.6 | -8.3 | 0.0 | tour: Leon goes from the lit source path to the owner-path look, 8 % of pixels (tour-2279-draw-fewer, r1c tile) |
| tier: PS2 em15-00 everywhere (p2 vs r1c) | -0.1 | +0.5 | | -0.3 | kite-tiers p2 (1.7 %) |
| tier: PS2 near 3 + v4-fit lean far (p2n3 vs r1c) | +0.7 | +0.1 | | +0.2 | kite-tiers p2n3 (1.9 %) |
| tier: v4-fit near 3 + lean far (fn3 vs r1c) | +1.0 | -0.1 | | +0.4 | kite-tiers fn3 (0.3 %) |
| tier: lean beyond 12 m (f12 vs r1c) | +0.8 | -0.9 | | +0.5 | 0.0 % at the held frames |

(r1c / r1n4 / r1d12 / tier arms: CROWD_READOPT with Leon (the earlier =2 behaviour) + the first, inexact cull; they
are compared with r1c, which has the same two, so their deltas isolate the option.)

Findings:
- The model tier does not matter for cost: PS2 near (1243 tris), v4-fit (898) and lean (628) are all within noise.
  The PS2 em15-00 look is free; the lean far tier buys nothing. A drawn Ganado costs ~2.1 ms (kite: 3 fewer drawn =
  -6.4 ms), almost all of it per-actor work, not triangles: per 3 Ganados avk_pos_skin_u16 +1.0, UI texture key
  hash_bytes +0.6, owner_ganado_palettes +0.4, one_chunk +0.3, pass_positions +0.3, Part::strips +0.2,
  coarse_skin_groups +0.2, owner_ganado_bind +0.2, actor_current_role +0.2 (hwmodel-cw-g1-k vs cw-g1n2-k).
- So "draw fewer" = DRAW_MAX (count) and FOGSKIP (distance); a cheaper model does not pay.
- The tour's big number is Leon (READOPT=2: -8.5 ms), not the Ganados.

**Decisions needed (looks are the user's call):** (1) CROWD_FOGSKIP on? (2) a draw cap: DRAW_MAX=2 (is this the
decided "crowd rule N=2"?), 4, or none? (3) READOPT for Leon too (=2) or Ganados only (=1)? (4) Ganado model: v4-fit
(today) or PS2 em15-00 (same cost)?

## How the Ganados are drawn in the play build (read 2026-09-30)

- The play recipe (tools/d367/build-r21.sh) sets ACTOR_TRANSACTION=1 + COARSE_SOURCE_ACTORS=1: every actor gets its
  source emTrans; at the OT callback commonModelTrans calls re4dc_actor_transaction_draw
  (coarse_actor_transaction.inc): plan (coarse_actor_owner_ganado.inc owner_ganado_bind, four cast chunks per
  appearance), semantics (immutable chunk proofs, material certificate), acquire (textures, workspace, palette bank;
  owner_ganado_palettes = FTRV bones + palettes), preflight, then per OT pass re4dc_actor_submit_owned_runs ->
  one_chunk (fog gate, positions kernel, meshlet outcodes, emit).
- re4dc_coarse_ganado (COARSE_PREGATE's adapter) is never called in this build; CROWD_LOD / FLAT / NEAR* / MID_M do
  nothing for cast chunks (constant colour, no LOD levels).
- Why most tour Ganados took the source path: the owner path finds a Ganado's material-lifetime record
  (actor_lifetime.inc find_info); records are adopted only at setTplAddr / model load. In the tour fixture the live
  info count falls 53 -> 23 by UI frame 840 (no revokes; ~300 adopt failures, reason 0), so most draws end in ATD 22
  and fall back to re4dc_actor_submit + per-vertex lights. Kite: nearly every Ganado admitted. CROWD_READOPT fixes it.
- Gore (stumps em15-stump-1bc/1c9/1dc/1e0, em12-stump-1d8 = "lost-head-stump", replacing the head section; hand poses
  em15-hand-N[-<body>]) is NOT wired yet. Today a Ganado whose head or hand section changes to a stump / other pose
  has no reviewed record for that bin (or fails owner_ganado_bind's bin check), so the whole actor takes the source
  path: gore stays complete (source mesh). Wiring them as cast section replacements needs cast_bundle.py to emit the
  state chunks and certificate rows for those bins; open (lane doc next steps).

## Knobs (game/crowd.mk, all default off; no -D added when every knob is at its default)

- CROWD_READOPT=1 (fix): a Ganado info whose material-lifetime record was dropped is proved again at plan time with
  the load-time proof (an info that fails stays on the source path). =2 also Leon. Look change only where records
  were dropped (the r101 entry tour).
- CROWD_CULL=1 (exact, look unchanged): after admission, a Ganado whose every visible cast chunk is provably outside
  a screen edge or a far plane at the fog-gate cull depth (pregate balls; far plane = fogged View far) is not
  acquired or submitted (choice 2, no record). Actors with a 5th (weapon) info or an original-source hand are never
  culled. =2 check build counts would-cull actors that emitted. History: the first version used "root depth > fog
  far + 2.5 m"; its check build found 16 violating actor-frames at view l (cw-ck-l, cw-ck2-l: depth 27.5..28.3 m,
  fog 25 m, 396..617 triangles emitted, fully fogged), so that test moved to CROWD_FOGSKIP (a look option).
- CROWD_FOGSKIP=1 (look change): root more than 2.5 m beyond the fogged View far -> not drawn (reason 4).
- CROWD_DRAW_MAX=N / CROWD_DRAW_M=D (look change): not drawn beyond the N nearest (previous frame) / beyond D metres.
- CROWD_FAR_M=D / CROWD_NEAR_MAX=N (look change): far tier (ganado_far_runtime.h = the cast's lean level) beyond D m /
  outside the N nearest; far chunks use immutable IDs 47..66 (kActorImmutableChunks 46 -> 66 under RE4DC_CROWD_FAR).
- CROWD_CENSUS=1 (diagnostic): "CROWDC" per-frame lines (CENSUS_FROM..TO), "CROWDLIFE" record census.
- CROWD_FREEZE_AT=N [AT2=M HOLD=S] (look sheets only): hold game frame N-1 (and M-1) on screen for S seconds.

## Tools (tools/d367/crowd)

- cbuild.sh <label> [knobs]: one arm (MODE=rel release + PC_SAMPLER; trace = STRICT build; play = recipe only;
  ASSETS=<dir> for tier arms, checked against its SHA256SUMS; ROOT=<tree>), fresh objdir, missing-symbol check.
- cprep.py, chw.sh (hwproject), crun.sh (Flycast run; deletes the disc, keeps disc.sha256), cqueue.sh <jobs>
  <workers> (detached build + hw queue; views e/l/s/b/k and e2/l2/s2/b2/k2 with the PS2 atlas; MINFREE), after.sh.
- far_header.py, ps2near_cast.sh, assets.sh (tier asset dirs + PS2 fixtures), looks.sh (freeze builds), sheet.py
  (look sheet + difference sheet), identity.sh <base> (knob-off identity, SOURCE_DATE_EPOCH pinned).
- Look-sheet runs: kite t=1099 (CROWD_FREEZE_AT=1100), tour t=1099 and t=2279 (AT2=2280), HOLD=40, screenshots every
  10 s; scenarios cw-look[b|x]-<arm>-<k|l> under playability-r11-r1/scenarios (discs deleted).

## Gates

- STRICT (gameplay/r11-runtime-gates-r1/audit.py, STRICT_TRACE_PASS, diff_counts {}), LOGIC_TRACE builds
  (MODE=trace), control t0 (no knob):
  - tg = READOPT=1 CULL=1 FOGSKIP=1 DRAW_MAX=2: kite 0..1941 PASS (cw-strict-tg-k), tour 0..4800 PASS (cw-strict-tg-l).
  - t1 = READOPT (with Leon) + first cull: kite 0..1941 PASS, tour 0..4800 PASS.
  - t2 = assets-far, READOPT + CULL + DRAW_MAX=2 + NEAR_MAX=1 (far tier live): kite 0..1941 PASS.
- Knob-off identity (identity.sh 160df41123 = merge base with dreamcast-port): play and trace images byte-identical
  at f26febc6 and again at 6f831cc4 (IDENTITY play OK, trace OK; logs/identity-6f831cc4.out).

## Numbers (image, build, evidence)

All: hwmodel-cw-<arm>-<view> under C:\Flycast-Evidence\re4-dreamcast (ARM.txt names ELF, fixture, flags); logs
/root/probe/lanes/crowd/hw-cw-*.log. Full per-arm table: tab.py over those logs. Highlights not in the decision table:
r1 (READOPT with Leon, no cull) e 71.1 / l 98.5 / s 73.7; r1c (+ first cull) e 67.3 / l 95.4 / k 93.5 / b 77.7;
r1c2 (+ exact cull) e 70.2 / l 98.2 / k 95.0 / b 76.7; cu1 (CULL without READOPT) e 77.76 (no Ganado admitted).
c0 view e profile: actors 11.97 ms (re4dc_actor_submit 3.16, Part::whole 1.24, build_lights 0.73, pass_positions
0.68, owned_source 0.54); render avk_light_skin 2.22, avk_pos_skin 2.03 (hwmodel-cw-c0b).

## State and next step

- 2026-10-01 20:30: no queue or Flycast of mine running (b1..b7 finished; b4 was stopped at 05:15 when C: fell to
  15 GB, its rest ran in b6). All my staged discs deleted (disc.sha256 kept).
- Next (after the user's decision): wire the chosen knobs into a play recipe arm; A items: the per-actor list in
  Findings (texture key hashing per Ganado, palettes, positions kernel); gore section replacements.

## Ready to land

- lane/crowd 6f831cc4 (+ doc commit): game/crowd.mk (included by the Makefile), coarse_actor_transaction.inc,
  coarse_actor_owner_ganado.inc, coarse_ganado_cast.cpp, coarse_actor_geometry_once.inc, actor_lifetime.inc,
  platform/native_ui.cpp (export under RE4DC_CROWD_OUTPUT only), tools/d367/crowd/*. Every knob default 0/-1 (no
  -D, image byte-identical: identity.sh). STRICT: tg / t1 / t2 above. Landing it changes nothing until the user picks
  knobs; then add them to build-r21.sh.
