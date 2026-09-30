# Lane enc

Rules: port/dreamcast/docs/D367_WORKSTREAMS.md. Branch lane/enc, tree /root/work/lanes/enc, evidence /root/probe/lanes/enc.

## Goal

Answer whether the r101 square encounter (e9b: r101 entry with Ganados approaching, 67.7 hw ms/frame) is an anomaly:
a hardware-model cost table (hwproject.sh) for every combat or crowd view on the route r100 -> r101 -> r103, on the
current play recipe, with the Ganados alive / in view / drawn per view, the per-area split, the Ganado-driven share
and the worst views to use as crowd-lane benchmarks. Measurement only (no game code changes except default-off
counters).

## State and next step

- 2026-09-30: ENC_CENSUS knob (default 0, diagnostic) + tools/d367/enc/ scripts built (enc-build.sh c1). Running the
  views.

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
| r100 east door (rel-r100-east-door-pw) | - | - | - | - | c2 run HALT main.cpp(548) at ui_frame 182 (route movie halt; not seen on the r21k tour); rerun east2 | - |
| r101 entry square (rel-r101-entry-pw; the e9b view) | 11 (+40 other: villagers/animals/crows list) | 3.7 (8) in 900:1380 | 0 | 40 | at 900:1380 every reaching Ganado is beyond 25 m; 3.0 of 3.7 are drawn by the SOURCE path (no cast plan, ATD 4) | 900:1380 (e9b); 2040:2520 (5 reach, 2 <25 m) |
| r101 bell fight (enc-rel-r101-bell-fight-pw) | 14 | 4.0 (9) | 4.0 (all <12 m) | 40 | from f1640 four Ganados on Leon, all cast-owned | 1640:2120; 1240:1720 (3-9 reaching) |
| r101 kite fight (kite-mesh-fixture-r21-vq) | 14 | 5-7 (7) | 4.8-6.3 | 40-42 | Leon dies at f997 (hp 0): window must end before it | 500:980 |
| r101 after the bell (rel-r101-post-bell-door-pw) | 0 | 0 | 0 | 29-30 | the bell's 40 dead | 900:1380 |
| r103 entry (rel-r103-entry-pw) | 5 | 3.0 | 2.0 | 43-44 (cows, chickens, dog, corpses) | 2 of 3 on the source path | 1400:1880 |

### Hardware model (hwproject.sh, nominal [low..high]; work = frame minus the modelled vsync spin in main, 0 here)

| view | image | window | frame hw ms | vs 33.3 | render-side | actors | logic | scenery | ui | copies | evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| e9b (old image, 2026-09-28) | release through d21356f0, no room effects | 900:1380 | 67.7 [58.2..80.8] | +34.4 | 27.5 | 12.7 | 9.8 | 9.1 | 3.8 | 2.7 | hwmodel-e9b |
| r101 entry (e9b view re-run) | c3 | 900:1380 | **77.8** [66.7..93.1] | +44.5 | 32.1 | 11.9 | 10.5 | 13.2 | 5.2 | 2.4 | hwmodel-enc-r101e3 (c1: 78.2, c2: 78.0, same view) |

r101 entry now vs e9b: +10.1 ms, from room effects (EspCommonTrans 1.8, EspTrans 0.6, re4dc_effect_sprite 0.6,
cEsp::ChannelSet 0.5, sprite visibility 0.3) and the PS2 world draw (MeshDraw::draw +2.6, clip_projected_triangle
+0.8, project +0.5); the character rows are unchanged (avk_light_skin +0.3). The census of the same hwmodel run
matches the dynarec census frame for frame at 900..1380.
(more views pending: jobs2)

## Ready to land

(none yet; ENC_CENSUS is a default-off diagnostic, listed here once its knob-off identity is checked)
