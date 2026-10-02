# Lane enc

Rules: port/dreamcast/docs/D367_WORKSTREAMS.md. Branch lane/enc, tree /root/work/lanes/enc, evidence /root/probe/lanes/enc.

## Goal

Answer whether the r101 square encounter (e9b: r101 entry with Ganados approaching, 67.7 hw ms/frame) is an anomaly:
a hardware-model cost table (hwproject.sh) for every combat or crowd view on the route r100 -> r101 -> r103, on the
current play recipe, with the Ganados alive / in view / drawn per view, the per-area split, the Ganado-driven share
and the worst views to use as crowd-lane benchmarks. Measurement only (no game code changes except default-off
counters).

## State and next step

- 2026-10-01: DONE. Census of the 8 route views, hwproject tables of 16 runs (all jobs2 done 09-30 19:13, queue pid
  44452 exited; kite and bellf c3 controls are complete in hwmodel-enc-kite / -bellf, no re-run needed), the answer
  below, ENC_CENSUS / ENC_SKIP_GANADO knob-off identity clean (Ready to land).
- Open (not this lane's brief): the r100 east-door preset HALTs with PACE_MODE=off (below); the source-path Ganados
  (em15 with no cast plan, em12 failing the plan semantics) for the crowd lane.

## Method

- Image: `tools/d367/build-r21.sh` at origin/dreamcast-port 160df411 (room effects EFFECT_ROOM=7, TEX_SLOTS=448,
  PS2 worlds in r100/r101/r103, everything in the play recipe) + the play flags (`LOGIC_TRACE=0
  GAME_DECISION_TRACE=0 ACTOR_TRANSACTION_DIAG=0 GAME_PWC_DIAG=1 ARENA_FIT_KOS_BYTES=147456 QUALITY_PICKER=0`) with
  `PACE_MODE=off` (every tick renders: one hwproject frame = one tick of work; the play disc's Fast pacing would skip
  renders), `DBG_WARP=1` (warp twin), `PC_SAMPLER=1`, `ENC_CENSUS=1`. ASSETS = play-actor-bundle-20260928 (SHA256SUMS
  verified, ext4 copy). `tools/d367/enc/enc-build.sh <label>`.
- Discs: the playability harness (stage-scenario.py) with the r21k tour fixtures `tour/rel-<view>-pw.json` (PS2
  worlds, texture VQ, release r100) and `tour/enc-rel-r101-bell-fight-pw.json` (tools/d367/enc/make-enc-fixtures.py:
  warp preset r101-bell-fight + the shared tour pad script). Copies of the warps/pad scripts: tools/d367/enc/fixtures.
- Cost: `tools/d367/enc/enc-hw.sh <view> <label> <fixture> [count] [trace]` = hwproject.sh, frames 900..1380, trace
  stride 16 (31 traced frames), evidence `C:\Flycast-Evidence\re4-dreamcast\hwmodel-enc-<view>`; the ENC census
  lines of the same run in `enc-census.txt` there.
- Census (ENC_CENSUS=1, `ENC f=` lines, one per presented frame at the PC-sampler frame mark): ga/oa = Ganados /
  other enemies alive in EmMgr; gr = Ganados reaching commonModelTrans (the game's own OT view test); go/gs/gx = drawn
  by the actor owner (cast mesh) / left to the source path / failed; gb = owned Ganados by view distance <5 / 5-12 /
  12-25 / >=25 m; or = other enemies reaching the draw; ct = native_actor_fast crowd tiers drawn (full/near/mid/far).

## Numbers (image, build, evidence)

Builds (tools/d367/enc/enc-build.sh, tree lane/enc; every arm = the play recipe above, PACE_MODE=off, DBG_WARP=1,
PC_SAMPLER=1, ENC_CENSUS=1): c1 (d6e2cbb9, census v1), c2 (495de4e5), **c3** (a6984274, census v2 + Leon's life;
the measurement image), c3s = c3 + ENC_SKIP_GANADO=1 (Ganados get no transform pass: prices their render side), c3x
= c3 + EFFECT_ROOM=0 (room effects off). ELFs /root/probe/lanes/enc/out-<label> (elf.sha256 there).

### Census (dynarec Flycast, c2/c3, 300-420 s per view; scenarios enc-<view> in the playability harness)

Global frames = the PC-sampler frame marks (hwproject frames). "reach" = Ganados reaching commonModelTrans (passed
the game's own OT view test); "<25 m" of those within the 25 m fog far. Chosen hw windows: the best 480-frame window
from frame 900 (or later) by Ganados reaching within 25 m, with Leon alive throughout (enc-windows.py).

| view (fixture) | Ganados alive | reach draw (max) | reach <25 m | other enemies alive | notes | hw window |
|---|---|---|---|---|---|---|
| r100 s20 ambush (rel-r100-s20-pw) | 11 from ~f1300 | 1.0-1.3 (4) | 1.0 | 0-1 | s03 movie plays first; the Ganados stay outside / behind walls, one in view | 1240:1720 |
| r100 after the radio call (rel-r100-post-radio-pw) | 1 | 0 | 0 | 1 | no Ganado in view | 900:1380 |
| r100 bridge / police-car scene (rel-r100-bridge-pw) | 1 | 0 | 0 | 18 (ids 23 x5, 43 x8 ...) | run reaches only f1753 in 300 s (slow scene) | 900:1380 |
| r100 east door (rel-r100-east-door-pw) | - | - | - | - | not measured: HALT main.cpp(548) (the 3600-vsync hang detector: no frame presented after ui_frame 182) in c2, c3 (east2) and c3n = c3 without the census (east3); c3f = play pacing (PACE_MODE=fast, no PC sampler) runs (east4, 3960 frames, HALT 0), as on the r21k tour. So PACE_MODE=off hangs at this preset; quiet view anyway (34.6 work in the 09-29 tour) | - |
| r101 entry square (rel-r101-entry-pw; the e9b view) | 11 (+40 other: villagers/animals/crows list) | 3.7 (8) in 900:1380 | 0 | 40 | at 900:1380 every reaching Ganado is beyond 25 m; 3.0 of 3.7 are drawn by the SOURCE path (no cast plan, ATD 4) | 900:1380 (e9b); 2040:2520 (5 reach, 2 <25 m) |
| r101 bell fight (enc-rel-r101-bell-fight-pw) | 14 | 4.0 (9) | 4.0 (all <12 m) | 40 | from f1640 four Ganados on Leon, all cast-owned | 1640:2120; 1240:1720 (3-9 reaching) |
| r101 kite fight (kite-mesh-fixture-r21-vq) | 14 | 5-7 (7) | 4.8-6.3 | 40-42 | Leon dies at f997 (hp 0): window must end before it | 500:980 |
| r101 after the bell (rel-r101-post-bell-door-pw) | 0 | 0 | 0 | 29-30 | the bell's 40 dead | 900:1380 |
| r103 entry (rel-r103-entry-pw) | 5 | 3.0 | 2.0 | 43-44 (cows, chickens, dog, corpses) | 2 of 3 on the source path | 1400:1880 |

### Hardware model (hwproject.sh, nominal [low..high], 31 traced frames per window)

work = frame minus the modelled vsync spin in `main` (the hardware-relevant figure; = frame where CPU-bound).
render-side .. copies = hwproject areas (render-side includes the spin). Census columns = means over the window from
the same hwmodel run (`enc-census.txt`): Ganados alive / reaching the draw (max) / drawn by the cast owner / by the
source path; reaching ones by view distance; crowd tiers full/near/mid/far. Evidence
`C:\Flycast-Evidence\re4-dreamcast\hwmodel-enc-<view>`; table + per-frame TSV: tools/d367/enc/enc-table-20260930.tsv,
enc-frames-20260930.tsv (`enc-table.py`).

| view | image | window | frame hw ms | work | vs 33.3 (work) | render-side | actors | logic | scenery | ui | copies | Ganados alive / reach (max) / cast / source | reach <5/5-12/12-25/>25 m | tiers f/n/m/f |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| e9b (old, 2026-09-28) | release through d21356f0, no room effects | 900:1380 | 67.7 [58.2..80.8] | 67.7 | +34.4 | 27.5 | 12.7 | 9.8 | 9.1 | 3.8 | 2.7 | - | - | - |
| **r101 kite fight** (kite) | c3 | 500:980 | **105.8** [92.1..124.8] | 105.8 | **+72.5** | 36.2 | 18.2 | 12.7 | 21.9 | 8.3 | 4.3 | 14 / 5.5 (7) / 5.5 / 0 | 1.9/1.8/0.7/1.1 | 0/2.7/1.0/0.7 |
| **r101 entry, later** (r101l) | c3 | 2040:2520 | **105.2** [90.6..125.8] | 105.2 | **+71.9** | 36.2 | 16.9 | 10.0 | 20.8 | 13.6 | 3.5 | 11 / 5.0 (5) / 1.0 / 4.0 | 0/0/2.0/3.0 | 0/2.0/0/0 |
| r101 entry = e9b view (r101e3) | c3 | 900:1380 | 77.8 [66.7..93.1] | 77.8 | +44.5 | 32.1 | 11.9 | 10.5 | 13.2 | 5.2 | 2.4 | 11 / 3.7 (8) / 0.7 / 3.0 | 0/0/0/3.7 | 0/0/0/0 |
| r101 bell fight, engaging (bella) | c3 | 1240:1720 | 76.1 [66.4..89.4] | 73.5 | +40.2 | 30.1 | 12.2 | 11.1 | 13.8 | 3.7 | 3.0 | 14 / 4.1 (9) / 3.6 / 0.5 | 2.7/0.2/0.2/1.0 | 0/3.0/0/0.2 |
| r103 entry (r103) | c3 | 1400:1880 | 75.6 [66.2..88.8] | 72.5 | +39.2 | 32.0 | 9.7 | 11.3 | 13.5 | 3.9 | 2.6 | 5 / 3.0 (3) / 1.0 / 2.0 | 0/0/2.0/1.0 | 0/2.0/0/0 |
| r100 s20 ambush (s20) | c3 | 1240:1720 | 75.5 [66.9..87.3] | 60.5 | +27.2 | 38.5 | 8.0 | 10.0 | 11.0 | 4.2 | 1.7 | 11 / 1.2 (4) / 0 / 1.2 | 1.0/0/0.2/0 | 0/1.1/0/0.1 |
| r100 after the radio call (prad) | c3 | 900:1380 | 61.9 [54.9..72.0] | 57.3 | +24.0 | 24.1 | 7.2 | 7.6 | 15.6 | 3.4 | 1.9 | 1 / 0 / 0 / 0 | - | - |
| r100 bridge, police car (brdg) | c3 | 900:1380 | 56.3 [50.1..65.1] | 49.5 | +16.2 | 23.5 | 6.1 | 7.5 | 13.0 | 2.8 | 1.6 | 1 / 0 / 0 / 0 (18 other enemies) | - | - |
| r101 bell fight, 4 on Leon (bellf) | c3 | 1640:2120 | 54.9 [47.4..65.1] | 54.9 | +21.6 | 20.5 | 11.2 | 6.4 | 9.7 | 2.8 | 2.6 | 14 / 4.0 (4) / 4.0 / 0 | 4.0/0/0/0 | 0/4.0/0/0 |
| r101 after the bell (pbell) | c3 | 900:1380 | 37.8 [32.1..46.0] | 37.8 | +4.5 | 16.9 | 7.5 | 3.8 | 4.0 | 3.1 | 1.2 | 0 | - | - |
| A/B: r101 entry, Ganados skipped (r101es) | c3s | 900:1380 | 72.7 | 72.7 | +39.4 | 30.7 | 9.0 | 10.4 | 13.2 | 5.0 | 1.9 | 11 / 0 | - | - |
| A/B: r101 entry, room effects off (r101ex) | c3x | 900:1380 | 71.5 | 71.5 | +38.2 | 27.7 | 11.8 | 9.9 | 13.0 | 4.4 | 2.4 | as r101e3 | | |
| A/B: kite, Ganados skipped (kites) | c3s | 500:980 | 91.4 | 91.4 | +58.1 | 32.9 | 10.2 | 12.5 | 21.9 | 7.1 | 3.0 | 14 / 0 | - | - |
| A/B: bell fight, Ganados skipped (bellfs) | c3s | 1640:2120 | 50.3 | 45.4 | +12.1 | 22.6 | 6.3 | 6.3 | 9.6 | 2.4 | 1.7 | 14 / 0 | - | - |
| A/B: r103, Ganados skipped (r103s) | c3s | 1400:1880 | 75.8 | 64.7 | +31.4 | 37.6 | 6.2 | 11.2 | 13.4 | 3.2 | 2.1 | 5 / 0 | - | - |
| A/B: s20, Ganados skipped (s20s) | c3s | 1240:1720 | 71.3 | 56.9 | +23.6 | 36.4 | 6.6 | 9.9 | 11.0 | 3.8 | 1.6 | 11 / 0 | - | - |

Row groups (hw ms, functions.tsv by name; effects = Esp*/effect sprite/ChannelSet; PS2 world = MeshDraw,
vp::transform, ps2_pass, clippers, group_visible; actor skin = avk_*/wpal/sk1/coarse skin; skeleton/motion =
hermite, Motion*, pwc/pmc, PSMTXConcat/Inverse, IK, RotMatrix, parts; model trans/light = commonModelTrans,
ModelRender, LightSetModel, setModel2, materialSetup; em logic = cEm*/em10*):

| view | effects | PS2 world | actor skin | skeleton/motion | model trans/light | em logic |
|---|---|---|---|---|---|---|
| kite / kites | 5.9 / 5.9 | 21.6 / 21.5 | 9.1 / 6.4 | 9.3 / 8.9 | 1.2 / 1.0 | 1.1 / 1.1 |
| r101l | 6.0 | 19.8 | 12.2 | 7.4 | 2.5 | 0.9 |
| r101e3 / r101es / r101ex | 6.2 / 6.2 / 2.8 | 12.7 / 12.7 / 12.5 | 7.3 / 6.8 / 7.3 | 7.2 / 6.8 / 6.5 | 2.0 / 1.6 / 2.0 | 0.9 |
| bella | 5.2 | 13.6 | 5.9 | 8.3 | 0.9 | 1.0 |
| bellf / bellfs | 3.6 / 3.6 | 9.6 / 9.5 | 6.3 / 4.2 | 4.9 / 4.6 | 0.7 / 0.5 | 0.5 |
| r103 / r103s | 5.6 / 5.7 | 13.3 / 13.2 | 5.5 / 4.0 | 10.0 / 9.8 | 1.2 / 0.8 | 0.5 |
| s20 / s20s | 3.7 / 3.7 | 10.6 / 10.6 | 6.5 / 5.5 | 7.8 / 7.7 | 1.1 / 0.9 | 0.6 |
| prad | 5.5 | 15.4 | 5.6 | 4.7 | 0.6 | 0.1 |
| brdg | 5.5 | 12.7 | 3.7 | 4.6 | 0.3 | 0.1 |
| pbell | 2.5 | 3.7 | 8.6 | 2.3 | 0.5 | 0.1 |

(actor skin and skeleton rows include Leon: pbell, with no Ganado, still has 8.6 + 2.3.)

r101 entry now vs e9b: +10.1 ms, from room effects (EspCommonTrans 1.8, EspTrans 0.6, re4dc_effect_sprite 0.6,
cEsp::ChannelSet 0.5, sprite visibility 0.3) and the PS2 world draw (MeshDraw::draw +2.6, clip_projected_triangle
+0.8, project +0.5); the character rows are unchanged (avk_light_skin +0.3). The census of each hwmodel run matches
its dynarec census frame for frame (r101e at 900..1380).

Source-path Ganados (ENC_GS, c4 census runs enc-r101g / enc-r103g): r101 entry: 7 em15 models (34 parts, 4-5 infos)
with no cast plan (ATD 4: re4dc_actor_plan_ganado declined, so the GC skin path draws them); r103: 4 em12 models fail
the plan semantics (ATD 6). These are the "source" column above and cost more per Ganado than cast-owned ones.

## Answer: is the r101 square an anomaly?

**No.** On the play recipe (c3, room effects on, PS2 worlds) every combat or crowd view on the route is 2-3x the
33.3 ms budget, and even views with no Ganado in sight are far over it:
- Worst views (work hw ms): **kite fight 105.8** (5.5 Ganados drawn, 4 within 12 m), **r101 entry later in the
  approach 105.2** (r101l: 5 reaching, 2 inside 25 m, 4 on the source path; ui 13.6 of texture churn), then r101
  entry = e9b view 77.8, bell fight while engaging 73.5, r103 entry 72.5, s20 ambush 60.5. Quiet views: after the radio
  call 57.3, bridge 49.5, bell fight with 4 on Leon 54.9, after the bell 37.8 (the only view near budget).
- Over budget by: kite +72.5, r101l +71.9, r101 entry +44.5, bella +40.2, r103 +39.2, s20 +27.2, prad +24.0, bellf
  +21.6, brdg +16.2, pbell +4.5.
- The e9b square (67.7 then, 77.8 now) is mid-pack, not the outlier; the kite fight and the later r101 approach are
  worse by ~28 ms.

What is Ganado-driven (render side, ENC_SKIP_GANADO A/B on the same window; their AI/logic still runs):
- kite 14.4 ms of 105.8 (14%; 5.5 drawn: 2.6 ms each), bell fight 9.5 of 54.9 (17%; 4 drawn: 2.4 each), r103 7.8 of
  72.5 (11%; 3: 2.6 each), r101 entry 5.1 of 77.8 (7%; 3.7 far ones: 1.4 each), s20 3.6 of 60.5 (6%; 1.2: ~3 each).
  Per Ganado drawn: **~2.4-2.6 ms** near (pooled within-view fit over 480 traced frames: 5.0 ms per Ganado reaching the
  draw, which also carries the camera / world changes that come with them; take the A/B figure).
- The A/B moves the actors area (-1.4 to -8.0 ms), actor skin (-0.5 to -2.7) and model trans/light; the skeleton/motion rows
  barely move (-0.1 to -0.4): they are logic-side (motion, IK, parts) and are paid whether or not a Ganado is drawn.
  The Ganados' own logic rows (em logic) are only 0.5-1.1 ms; game logic as a whole is 6-13 ms.
- So drawing fewer Ganados alone cannot reach 33.3: at kite, removing every Ganado draw leaves 91.4 ms.

World and effects:
- PS2 world rows: 9.6-21.6 ms (kite 21.6, r101l 19.8, prad 15.4, r103 13.3, r101 entry 12.7): the largest single
  render block in every heavy view, and the main difference between the two 105 ms views and the 75 ms ones.
- Room effects (c3 vs c3x, r101 entry): 6.3 ms (77.8 -> 71.5); effect rows 2.5-6.2 ms across views.
- Game-render-side (source pose / skinning / collision line tests run on the render thread) 17-38 ms is the largest
  area everywhere, partly Leon (pbell: 16.9 with no Ganado).

Benchmarks for the crowd lane: **kite 500:980** (worst, 5.5 Ganados drawn, all cast-owned, Leon alive) and
**r101l = r101-entry 2040:2520** (as heavy, source-path Ganados + texture churn), plus **bella** (bell fight
1240:1720, 3-9 Ganados engaging) for a mid-range view; keep r101 entry 900:1380 as the e9b continuity point. Each
with its c3s (Ganados skipped) arm as the floor a crowd policy can reach.

## Ready to land

- **ENC_CENSUS (default 0) + ENC_SKIP_GANADO (default 0)**, lane/enc commits d6e2cbb9..4dbe7dd7 (game30.mk,
  coarse.cpp, coarse_actor_transaction.inc, platform/native_actor_fast.cpp, platform/native_ui.cpp,
  platform/include/actor_transaction_diag.h, src/game/trans.cpp; all under #if). Diagnostic only; ENC_SKIP_GANADO is
  an A/B knob that hides Ganados and must never be in a play build. Gate: knob-off identity, play recipe (DBG_WARP=0,
  PACE_MODE=fast), lane/enc 09c02b84 vs origin/dreamcast-port 029ec84a, fresh objdirs: .text, .data, .bss and
  sscrn.ovl identical; .rodata differs in 1 byte (__TIME__). No STRICT gate needed (no code in the default image).
- tools/d367/enc/ (enc-build.sh, enc-hw.sh, enc-queue.sh, enc-census-run.sh, enc-windows.py, enc-table.py,
  make-enc-fixtures.py, fixtures/, jobs/, the result TSVs): measurement tooling, no game impact.
