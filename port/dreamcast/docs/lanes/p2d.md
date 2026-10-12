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
