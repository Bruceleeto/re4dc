# Lane sk: lazy source weight palettes (2026-10-05)

REPORT.md (perf-20261004) candidate #7. Branch perf/sk-20261005 (worktree /root/probe/lanes-20261004/sk/tree), base
51d77d07. Knob SKIN_PALETTE_LAZY (game/game30.mk, default 0; needs NATIVE_ACTOR_SKIN_LAZY=1). Render only, exact.

## What it does

ModelTrans's commonScreenMatSub (trans.cpp) registers a lazily skinned info with its palette copy reserved (the same
re4dc_prim_tail allocation and re4dc_actor_skin_register call as re4dc_skin_defer_lazy) but not built: the copy holds
a pending header (NaN magic, frame, model, weights, count). calcWeightMat + MakeWeightPalette run when a render consumer
first reads the palette: re4dc_skin_palette_resolve, called from native_actor_fast.cpp re4dc_actor_skin_palette
(prepare_frame's skin Frame) and one_frame (COARSE_ONE_SUBMIT), and from trans.cpp re4dc_skin_materialize. Same game
frame, same functions (GAME_WPAL_FAST=3: re4dc_wpal_sh4 straight into the copy), so the same words. The parts matrices
of one model are built once per frame for its resolves (memo cleared by every other calcWeightMat). Owner-drawn actors
(ACTOR_TRANSACTION: the Ganado cast and Leon replace the source registry entry with their own palettes) and culled
actors never build source palettes; the s03 corpse and other source-path actors build theirs at render. Morphed infos,
failed registrations and the mirror / shadow / TexRender commonScreenMat calls keep the eager build. Four words of
.bss in the =1 image (no table: an earlier version with a 1 KiB table shifted .bss and cost +0.2 ms of sinf D-misses
per tick, on skipped ticks too).

=2 (check build): the eager palette is built and drawn; each resolve rebuilds lazily into the locked cache and compares
words ("SKLAZY frame= reg= resolved= never= bad= badw= stale= full= mtx=" every 600 frames).

## Consumer census

- SkinEntry.palette contents are read only through Frame.palette (set in prepare_frame and one_frame) and
  re4dc_skin_materialize. lazy_skin / one_qualifies test the pointer only. The owner registry (acquire / validate /
  release / owned_source) copies and compares pointers, never contents; owner palettes pass through resolve untouched
  (no magic). coarse_actor / coarse_ganado / coarse_ganado_cast register their own built palettes.
- pG->mtxPalette (pG+0x190..0x3010): written by calcWeightMat, read by MakeWeightPalette* right after, and by the
  NATIVE_MODEL_REGISTRY=2 snapshot (the knob refuses that build). Not in the save block (pG+0x4F80..), no other reader
  in src/ or port/. Its end-of-Trans contents differ with the knob; nothing reads them.
- Locked-cache palette (re4dc_locked_cache): CalcSk1_x reads it right after MakeWeightPalette in the same
  commonScreenMatSub; materialize uses its own palette pointer; pendulum.cpp uses the buffer as scratch, write first.
- Logic: nothing reads either (STRICT below). Leon, cutscenes, thermal scope and shadows go through the same paths.

## Gates (evidence C:\Flycast-Evidence\re4-dreamcast\sk-20261005, logs /root/probe/lanes-20261004/sk/logs)

- Knob-off identity vs 51d77d07, same flags, SOURCE_DATE_EPOCH pinned: cost arm (DBG_WARP=1 PACE_MODE=fast
  PC_SAMPLER=0 PACE_FORCE=2 ENC_CENSUS=1), play (DBG_WARP=0 PC_SAMPLER=0) and trace (+ LOGIC_TRACE=1
  GAME_DECISION_TRACE=1) images and sscrn.ovl byte-identical. missing.txt empty in every arm.
- Check build (sk5c2): r100-h-fight 300 s reg 59744 / resolved 15230 / never 44514; perf-r101sq 300 s reg 172890 /
  resolved 56712 / never 116178; bad=0 badw=0 stale=0 full=0 in both (dyn-sk5-hf-c2, dyn-sk5-sq-c2).
- H2 STRICT (sk5t2, h2-v.json 480 s, vs route-z-strict): 1450..1569 STRICT, to 740 STRICT, from 1218 STRICT, whole
  room om-only (dyn-sk5-h2-t2). Trace A/B on r100-h-fight (sk5ta vs sk5t2, PACE_MODE=off ACT_CAP=0, 5034 ticks):
  0..740 and 1218..5033 STRICT (incl. 2300..2379); 741..1216 om/ef float drift only (the radio call's wall-timed sub
  screen, the same span as the H2 gate's om-only region).
- Look: CROWD_FREEZE_AT=1371 / AT2=2351 / HOLD=40 on r100-h-fight, framebuffers fb0+fb1 read during the holds. The
  knob-off build itself varies run to run by two 3-pixel sets of 1 RGB565 step (fb1 at (492,65) (491,66) (367,373);
  fb0 at (630,265) (626,267) (632,267)) at the 2351 hold. knob-on run sk5-lk-hf-b3 is pixel-identical to knob-off run
  sk5-lk-hf-a in both buffers at both holds; every other pair differs only in those sets.
- 0 MISALIGN: interpreter + HWTRACE_ALIGN=1 (hwmodel Flycast), r100-h-fight 900 s to frame 12687 (dyn-sk5-align-b2).

## Cost (hw ms = model total minus PACE/WAIT; A = sk5a, B = sk5b2; one run per arm)

| preset | A drawn | B drawn | delta | A skip | B skip | delta |
|---|---:|---:|---:|---:|---:|---:|
| r100-h-quiet 1400:1479 | 47.80 | 47.08 | -0.72 | 24.56 | 24.61 | +0.05 |
| r100-h-fight 2300:2379 | 66.03 | 64.77 | -1.26 | 24.45 | 24.56 | +0.11 |
| perf-r101sq 1330:1409 | 78.03 | 75.81 | -2.22 | 27.87 | 28.16 | +0.29 |

Function deltas (drawn): re4dc_wpal_sh4 -0.34 / -0.51 / -0.78, palette memcpy (L_al4both_loop) -0.20 / -0.28 / -0.36,
PSMTXConcat (calcWeightMat) -0.03 / -0.19 / -0.41, re4dc_actor_skin_register -0.08 (square). The patch runs no code on
skipped ticks; their deltas are IRQ placement (LOGIC vs other(kos/irq) moves; no function moves > 0.05 ms).
Console (REPORT factors house 0.937, fight 1.107; speed = 66.7/(D+S)): house 98.4% 14.8 fps -> 99.3% 14.9 fps; fight
66.6% 10.0 fps -> 67.4% 10.1 fps; square (fight factor) 56.9% 8.5 fps -> 57.9% 8.7 fps.
