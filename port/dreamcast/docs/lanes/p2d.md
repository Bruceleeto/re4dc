# Lane D (Phase 2): route, memory, movie, audio

## D0 step 0: HEAP4_PARTS_RESERVE (2026-10-11; user decision: match the GameCube)

Mechanism. H2 frame 660 (r100, s30 setup): two em10 spawns call ModelInit; their parts runs come from the
PARTS_DEMAND pool (parts_bridge.cpp prepare_work, heap 4). On the GameCube cManager<cParts>::arrayAlloc takes the whole
1310 x 472 B array up front, so a model's parts never fail for heap there. On the port, with heap 4 a few KB short,
both runs failed (`alloc[3ee0]:free[..] native parts run`, `EM10 pEm->modelInit() failed`): e 41 at frame 661. The
GameCube outcome is e 43.

Proof that the PS2_OBJECTS divergence is exactly those spawns (lane B route-h2-c vs route-h2-o100c, unpadded r100 dar,
-315,712 B heap 4): frames 0..660 STRICT; frame 661 differs in r, e (41 -> 43), o (211 -> 212) and their hashes only.
Control log between LU 660 and 661: both em10 runs fail, `EM10 pEm->modelInit() failed` x2, then
`alloc[2a0] atari.cpp(2621)` / createSat() failed (o 211 -> 212 is that sat object: same heap-4 cause, also a
GameCube-succeeding allocation). Objects log: no failure lines, `em10 free size` printed by both spawns.

Knob. HEAP4_PARTS_RESERVE=1 (default 0; needs PARTS_DEMAND=1 and the unpadded PS2_OBJECTS r100 dar): in room
HEAP4_PARTS_RESERVE_ROOM (0x100) the parts pool takes a 73,728 B slab from heap 4 at room init (two em10 = 2 x 30 runs,
63,808 B with cell headers, + slack); a parts run heap 4 cannot give, after the dead-run reclaim, comes from the slab
(slab runs are never freed singly; the slab goes with the pool). HEAP4_PARTS_RESERVE=2 is a test mode (slab first) that
exercises the slab with heap 4 to spare. Default 0 compiles nothing: play image byte identical to da26605e (prog.bin
3,185,952 B, overlays identical). Knob on: +480 B image.

**New H2 baseline `d0-h2-a`** (test 8 base: test 7 recipe at da26605e + unpadded PS2_OBJECTS r100 dar r100b +
HEAP4_PARTS_RESERVE=1; trace arm p2d0aT, IMAGE_PAD_BYTES 4096): e 43 at frame 661 = the GameCube outcome (was 41),
es 9707e005; s30 340/340 heap_before 254,336 (was 56,960). Evidence D:\Flycast-Evidence\re4-dreamcast\p2d-20261011.

| run | arm / pad | ticks | e@661 | s30 heap_before | vs d0-h2-a |
|---|---|---:|---:|---:|---|
| d0-h2-r2 | p2d0rT / 0 | 7257 | 43 | 258,432 | STRICT 1450..1569, 0..740, 1218..; decision_cmp MUST-IDENTICAL |
| d0-h2-a | p2d0aT / 4096 | 7255 | 43 | 254,336 | baseline |
| d0-h2-d | p2d0dT / 16384 | 7255 | 43 | 242,048 | STRICT all windows, MUST-IDENTICAL |
| d0-h2-f | p2d0fT (=2, slab first, 32 runs 73,504 B) / 0 | 7260 | 43 | 334,016 | STRICT 1450..1569 and 1218..; 0..740 float drift at 740 only; must fields differ only in 741..1216 (sub screen open, below) |
| d0-h2-o | p2d0oT (objects, no reserve) / 0 | 7258 | 43 | 332,288 | as d0-h2-f |
| d0-h2p-r2 | p2d0rT + padded dar r100p | 7257 | 36 | 251,232 | FAIL from 661: without the freed 315 KB the slab starves em2a's 276 KB read (`EmSetFromList2() Em set failed, Id = 2a` x6) |

Frame 740 drift explained: the H2 fixture opens the sub screen at frame 740 (`subscreen backing: open type=20`,
close at 1217). While it is open the 3 MiB window at pStFnt holds sub screen data, and the trace's em / player fields
read that window; the window's contents depend on the r100 heap 4 layout (packed 1,641,416 B without the slab vs
1,665,692 B with it, restore hash differs). So only the reads during 741..1216 (476 ticks, exactly the open period)
and the em float hash at 740 differ; every tick after the close is STRICT, and arms with the same layout (all reserve
arms at any pad) are STRICT throughout. Not a gameplay difference; it is why the standard H2 windows skip 741..1217.
The s30 movie (after 1217) plays 340/340 in every arm.

Other gates (reserve arms, unpadded dar): bell p2d0rT vs p2d0oT STRICT frame (5158) and room (4976), MUST-IDENTICAL;
r10b s20 (f6s, p2d0rW) 800/800, dropped 7, smooth (test 7: 12); New Game (p2d0rP) intros 1971/2360, s40 1175;
0 HALT, 0 MISSING, 0 MISALIGN everywhere; missing.txt empty.

## D4: DVD_READ_SAFE (2026-10-11, disc reader robustness; unblocks the El Gigante GC texture bake)

Failure. Test 7 recipe + the GC-bake r119 package (reg-gig-gctex), g3 fixture (r119 boss): after the r119 s20
movie every disc stream request was refused ("cdrom_stream_request: Previous DMA request is in progress") until the
end of the run: 249 texture uploads failed, every tex.pak index re-read failed (d4-g3-off, reproduces test 7's
f1-g3 exactly). KOS's dma_in_progress (hardware/cdrom.c) stays set while a stream command runs: the vblank handler
leaves it alone for a streaming command and only a G1 DMA completion clears it. It is timing dependent: the same
configuration passes with the image 384 B larger (d4-g3-pad).

Fix. DVD_READ_SAFE=1 (default 0; platform/dvd_read_safe.cpp, built only with the knob) wraps cdrom_stream_start /
cdrom_stream_request. A refused request is retried for 10 ms; if still refused the flag is stale: the G1 ATA semaphore
is taken, cdrom_abort_cmd(1000, abort_dma=true) clears the flag and the stream command, the stream is started again
where it stood (sector granular) and the request repeated. A request that succeeds first time takes the old path.
DVD_STUCK_TEST=<s> + DVD_STUCK_ADDR=<KOS dma_in_progress address> (test only) set the flag before the first stream
start after <s> seconds.

Proof (evidence D:\Flycast-Evidence\re4-dreamcast\p2d-20261011):
- d4-g3-s (fix, the failing configuration): one real refusal episode at the same point (6 refusals), "recovered after a
  stream restart"; 0 upload failures, 0 index read errors (off: 249 / 237).
- Injected stuck flag at 150 s, same point: off (d4-g3-x2) `DVDReadAsyncPrio: short read /cd/em/em21.drs got=0
  errno=5`; on (d4-g3-y2) "recovered after a stream restart", em21.drs read, no short read.
- H2 knob on vs knob off (test 7 control fixture): STRICT 1450..1569, 0..740, 1218.., decision_cmp MUST-IDENTICAL,
  7128 ticks both (door timings unchanged), s30 340/340 heap_before 56,960 both.
- r10b s20 (f6) 800/800 dropped 7; New Game 1971 / 2360 / 1175; 0 HALT, 0 MISALIGN, missing.txt empty. The one f6
  upload failure is the known missing pair 18d0fd82 (open failed; test 7 has it too).
- Knob off: play image byte identical to 56db3649 (prog.bin 3,185,952 B, overlays identical). Knob on: +608 B (W).

## D5: TRACE_ALLOC / TRACE_SS_MASK (trace builds only, 2026-10-11; from lane B's B4 audit)

Two knobs for logic-trace builds (game30.mk; both need LOGIC_TRACE=1; default 0 = no code; with both off the play
image and the trace image are byte-identical to a0f0e43f, prog.bin 3,185,952 / 3,209,292 B).
- TRACE_ALLOC=1: a failed required heap-4 allocation (main_mem.cpp mem_alloc with flag 1, the `alloc[..]:free[..]`
  log; the native parts run in parts_bridge.cpp once its reservation fallback has also failed) bumps the must-match LU
  field `af=<count>/<FNV of size + site tag>` and logs `LA t= n= size= site= af=`. A layout-dependent spawn change
  then shows up as af on the tick it happens.
- TRACE_SS_MASK=1: while the sub screen backing has room memory swapped out (sscrn_bridge.cpp swap open / close,
  logged as `LSS ... open=1/0`), the player / enemy / object fields print `~` and the lists are not walked. Globals,
  flags, RNG, camera and af are still recorded, and the pad fixture feed keeps its old reads. Does not combine with
  LOGIC_TRACE_SWAPPED / LOGIC_TRACE_OWNERSHIP (those read the swapped bytes themselves).
- Tools: tools/game30/logic_trace_diff.py (new in the repo; the d367-agents copy plus an optional discrete `af`
  field and a `masked` count) and decision_cmp.py (accepts `~`, must field `af`, which reads `-` without the knob).
  `~` only equals `~`. On existing traces both tools give the old verdicts: d4-h2 off/on, d0-h2 a/r, p2b wi11b c/o.

Gates (test 7 recipe T arm, test 7 control H2 fixture):
- H2, knob on (d5-h2-on) vs off (d5-h2-off), old tool: STRICT over 1450..1569, 0..739 and 1217..; decision_cmp: every
  must field ok except af, which is missing in the off arm. 7127 ticks each; s30 340/340 with heap_before 56,960 in
  both; 0 HALT / MISALIGN. The sub screen window is 740..1216 (`LSS`), so frame 740 is masked.
- r11b (lane B's false MUST-DIFFER: wi11b-c vs wi11b-o, unpadded dar): with the knobs on (d5-11b-c / -o), it is
  STRICT and MUST-IDENTICAL over 2657 ticks, with 2390 of them masked. Without the knobs it was MUST-DIFFER from
  frame 267.
- H2 knob on vs knob on + HEAP4_PARTS_RESERVE=1 (d5-h2-res): the first difference is tick 661, with af 5 -> 7 on the
  same tick as e 41 -> 36 / o 211 -> 212. The off arm logs 4 native parts run failures at 661. The reserve=1 arm
  instead logs `read.cpp(725)` 0x43660 failures: with mode 1 on this recipe, the slab starves a 275 KB read buffer.
  This is a D0 finding, not a D5 issue; the landed recipe uses mode 2, and this run used mode 1.

## C6: RENDER_OPTION, the Rendering levels and the speed display (2026-10-12; private, not pushed)

Knob RENDER_OPTION=1 (game30.mk; default 0 = no code; needs QUALITY=1, NATIVE_MES=1, PACE_CATCHUP, PACE_VMU=1).
Player settings (RE4DCCFG fields, quality.cpp; quality.txt `render=quality|standard|fast`, `perf=0|1` alias,
`speed=off|vmu|screen|both`). Test 8 default: Quality, speed display Off.
- Rendering: Quality = 640x480 (today). Standard = 640x240 per frame, alternating lines on 480i: each frame renders
  one parity (half-line viewport jitter, GXGetViewportv) into the matching lines of a 640x480 buffer; four
  half-buffers in the two KOS buffers, no copy, no extra VRAM, the other half at most one frame old. Fast = 320x240,
  pixel doubled by the video output, alternating lines on 480i. VGA: Standard / Fast are plain line doubling (the
  Options help line says so). One memory layout (RES_MODES=19: modes 0, 1, 4; 300 tiles at most; the KOS
  allocation), runtime switching at the safe point, a new alternating mode fills both parities while the old picture
  is held (no garbage half). The 240-line modes clip their last line and keep it black. Plain doubling stays as the
  RENDER_DOUBLE=1 debug fallback; the mode switch keeps a per-frame vertical offset hook (unused).
- Options screen (option.cpp + option_rows.cpp, title and pause): rows FRAME PACING (Smooth / Fast / Off) and
  RENDERING (Quality / Standard / Fast) below AUDIO SETUP in the message font; EXIT and the help line move down;
  the screen's cursor colour and sounds; left / right / A change the value at once and store RE4DCCFG.
- R + START (every RENDER_OPTION build; the game never sees that START) cycles the speed display Off -> VMU ->
  Screen -> Both with a 2 s note (four boxes). VMU = the PACE_VMU page; Screen = a corner counter (fps, game speed
  %, test builds CPU %) shown in room play only (no movie, sub screen, title or crash screen).
- Test builds keep the X + D-pad down + START mode chord and the mode label; RES_CYCLE_FRAMES=n cycles the modes.

Gates (evidence D:\Flycast-Evidence\re4-dreamcast\p2d-20261011, test 7 recipe):
- Knob off: play and trace images byte identical to the base (prog.bin 3,185,952 / 3,210,124 B, overlays equal).
- H2 with the call equaliser (CODEC_READY_FIXTURE=1, dc/codec_ready.txt "K 20", both arms): Standard vs Quality and
  Fast vs Quality STRICT over every window (7069 / 7070 ticks); in-play switching every 97 frames (RES_CYCLE_FRAMES)
  vs Quality STRICT outside 741..1232. Knob on vs knob off: STRICT over 0..740 and 1233..end; 741..1232 differs only
  in om (object parts read while the sub screen backing is swapped out; image layout dependent, the D5
  TRACE_SS_MASK case). s30 340/340 in every arm; codec ready released once, 0 FAIL.
- New Game (Standard): 1971 / 2360 / 1175. r10b (Fast): 10b00 / 10b10 / 10b22 / 11b00 complete, the one known
  upload failure as the base. r119 (Fast): 0 upload failures. VGA (Standard): scaler VGA doubled, s30 340/340.
  0 HALT, 0 MISALIGN everywhere.
- hw model (hwproject, drawn tick, nominal ms): square base 70.29 / Quality 70.90 / Standard 69.96 / Fast 70.00;
  house 192.06 / 192.46 / (window missed the stall) / 192.59; lake 51.79 / 53.82 / 53.80 / 53.69. The levels do
  not change CPU time (fill is GPU work). Speed counter on vs off at the square: 70.90 vs 71.00 (within noise).
- Flycast PVR timing does not model fill (GPU 7.5 ms at the house view for all three levels): the fill saving is
  the tile count, 300 / 150 / 75 tiles per frame, and needs a console reading.
- Stills: c6-stills\view-{sq,house,lake}.png (display-equivalent: Quality as captured, Standard as the TV interleaves
  it, Fast cropped and doubled; top row raw, bottom row 480i-softened); Options screen route-c6-opt5 t0177 / t0203.
- s30 first-picture failure: only in RES_MODES=15 builds (mode 3 makes KOS allocate 600 tiles: vram_free 43,264,
  kos_free about 11 KB at the movie start). RENDER_OPTION builds no FSAA mode (KOS 300-tile allocation): s30 340/340.

C6 follow-up (2026-10-12):
- Quality cost of the RES_MODES runtime path: every effect sprite / line was copied and scaled even at 640x480
  (now skipped when the scale is 1: -0.28 ms at the lake); RE4DC_SCREEN_W / _H are the float globals in RES_MODES
  builds (no int conversion per vertex), the half sizes are set with the mode, MeshDraw hoists them per strip and
  project() reads them per part. A padded base (+16 KB) and base + PACE_VMU are unchanged (51.67 / 51.79 ms). The
  rest of the lake difference is not render code: the lake fixture window is not logic-identical between binaries
  (the largest per-function deltas are PenClothMove and cModel::getPartsPtr, game logic, as frame timing differs),
  so lake drawn-tick ms compare different game states; MeshDraw::draw is +31k cycles per drawn tick (0.16 ms).
- Standard showed a static noise row at the bottom (rows 478 / 479; the "top edge" stripe in the earlier sheets
  was this row against the softened panel). Row 0 of every half buffer is black. The 240-line modes clip and clear
  their last line, and the alternating display shows 239 lines per field: row 479 is the last row of KOS buffer 0
  and holds data that is not ours when no 480-line render overwrites it (Quality overwrites it every frame; worth
  a VRAM-map check outside C6).
- Final code: knob off byte identical; H2 with the call equaliser Standard vs Quality STRICT over all 7071 ticks
  (fin2), Fast vs Quality STRICT over 7052 (fin, one display-register edit earlier), base vs Quality STRICT 0..740
  and 1233..; s30 340/340, codec released once, 0 FAIL / HALT / MISALIGN. Sheets c6-stillsiew-{sq,house,lake}.png
  refreshed from the final views (route-c6-fv-*).

## FSAA console test: RENDER_FSAA (2026-10-14; lane/fsaa, not pushed)

User report: the aa trial disc (98143f5b + RES_MODES=7, mode 2 "640x240 FSAA") flickered a lot on a 480i TV (S-Video).
Cause (register level, res_mode.cpp at 98143f5b and today): the 240-line modes 1 and 2 are shown doubled on a 480i TV:
FB_R_SIZE = 319 | 239 << 10 | 1 << 20 (modulus 1: no line skipped) and FB_R_SOF2 = FB_R_SOF1 (the vblank handler
rewrites it after KOS's flip), so both fields scan the same 240 rows; the interlace places field 2 one scan line lower,
so every horizontal edge moves one line up and down at 30 Hz. Quality instead reads FB_R_SIZE 319 | 239 << 10 |
321 << 20 (skip one line) with SOF2 = SOF1 + 1280 (the odd rows) and SCALER_CFG 0x401 (vertical scale 1025: the
3-tap 1/4, 1/2, 1/4 filter, Y_COEFF 0x8040). Mode 2 kept 0x10401, but the filter runs on 240-row data and cannot
remove the field offset. The FSAA bit itself (2:1 horizontal) has no temporal effect. Flycast cannot show this: it
reads neither Y_COEFF nor SCALER_CTL interlace / field select, and presents the rendered frame without the field scan.

RENDER_FSAA=1 (game30.mk, needs RENDER_OPTION=1; replaces RENDER_QUALITY_ONLY; RES_MODES=13; default 0, knob-off play
image byte-identical to the test 10 recipe from the same tree, objcopy image + all overlays): Rendering = QUALITY /
FSAA / FSAA LITE for this boot only (RE4DCCFG untouched; quality.txt render=quality|fsaa|lite).
- FSAA = mode 3, 1280x480, SCALER_CFG 0x10401: Quality's display and vertical filter. Twice Quality's fill (modelled:
  614,400 vs 307,200 samples). 600 tiles from the KOS 300-tile allocation plus 4 overflow pools per bank paid by the
  vertex buffer (2,049,024 -> 1,856,512 B per bank; worst TA parameter use seen 1,657,012 B, i9d): texture pool
  2,568,192 B (test 10 2,567,168; the old 600-tile KOS allocation left 2,072,576 and starved s30). OPB overflow pool:
  288,000 B (FSAA), 358,400 (LITE), 384,000 (Quality; was 192,000).
- FSAA LITE = mode 2, 1280x240, SCALER_CFG 0x10200 (vertical scale x2): the write-out writes 640x480, FB_Y_CLIP 479
  (written coordinates) clips the 8th tile row's overhang, Quality's display. Quality's fill. Whether the console's
  scaler interpolates a x2 enlargement (stable) or repeats lines (the old twitter) is unknown: console test.
Flycast (evidence C:\Flycast-Evidence\re4-dreamcast\fsaa-20261014): h2 warp + tour in FSAA and LITE, s30 340/340,
TEX_CHECK=2 fails 0, LEONGC 0, 0 HALT / FAULT; RES_CYCLE_FRAMES=450 over h2: 14 switches 0 -> 2 -> 3 -> 0, scaler
values restored (0x401 after LITE), s30 340/340. The st-square warp stops at ui frame ~909 in every arm, test 10's
own msq run included (Flycast fixture problem, not this knob). Console disc: RE4DC-FSAA-Test-20261014.
