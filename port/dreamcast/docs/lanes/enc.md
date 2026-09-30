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

(pending)

## Ready to land

(none yet; ENC_CENSUS is a default-off diagnostic, listed here once its knob-off identity is checked)
