# Lane D (Phase 2): route, memory, movie, audio

## D0 step 0: HEAP4_PARTS_RESERVE (2026-10-11, in progress; user decision: match the GameCube)

Mechanism. H2 frame 660 (r100, s30 setup): two em10 spawns call ModelInit; their parts runs come from the
PARTS_DEMAND pool (parts_bridge.cpp prepare_work, heap 4). On the GameCube cManager<cParts>::arrayAlloc takes the whole
1310 x 472 B array up front, so a model's parts never fail for heap there. On the port, with heap 4 a few KB short,
both runs failed (`alloc[3ee0]:free[..] native parts run`, `EM10 pEm->modelInit() failed`): e 41 at frame 661. The
GameCube outcome is e 43.

Proof that the PS2_OBJECTS divergence is exactly those two spawns (lane B runs route-h2-c vs route-h2-o100c, unpadded
r100 dar, -315,712 B heap 4): frames 0..660 STRICT; frame 661 differs in r, e (41 -> 43), o (211 -> 212) and their
hashes only. In the control log between LU 660 and 661: both em10 runs fail, `EM10 pEm->modelInit() failed` x2, then
`alloc[2a0] atari.cpp(2621)` / createSat() failed (the o 211 -> 212 is that sat object, the same heap-4 cause: a third
GameCube-succeeding allocation). In the objects log: no failure lines, `em10 free size` printed by both spawns.

Knob. HEAP4_PARTS_RESERVE=1 (default 0; needs PARTS_DEMAND=1 and the PS2_OBJECTS r100 dar): in room
HEAP4_PARTS_RESERVE_ROOM (0x100) the parts pool takes a 73,728 B slab from heap 4 at room init (two em10 = 2 x 30 runs,
63,808 B with cell headers, + slack); a parts run heap 4 cannot give, after the dead-run reclaim, comes from the slab
(slab runs are never freed singly; the slab goes with the pool). Default 0 compiles nothing: play image byte identical
to da26605e (prog.bin 3,185,952 B, overlays identical). Knob on: +480 B image.

New H2 baseline "d0-h2-a" (test 8 base: test 7 recipe at da26605e + unpadded PS2_OBJECTS r100 dar r100b +
HEAP4_PARTS_RESERVE=1; trace arm p2d0aT, IMAGE_PAD_BYTES 4096): e 43 at frame 661 (the GameCube outcome), es 9707e005.
Evidence D:\Flycast-Evidence\re4-dreamcast\p2d-20261011.

| arm | pad | ticks | e@661 | s30 | heap_before | vs d0-h2-a |
|---|---:|---:|---:|---|---:|---|
| d0-h2-r (p2d0rT) | 0 | 4659 (cut by the C: capacity guard) | 43 | 340/340 | 258,432 | STRICT all windows over its ticks, MUST-IDENTICAL |
| d0-h2-a (p2d0aT) | 4096 | 7255 | 43 | 340/340 | 254,336 | baseline |
| d0-h2-d (p2d0dT) | 16384 | 7255 | 43 | 340/340 | 242,048 | STRICT 1450..1569 / 0..740 / 1218.., decision_cmp MUST-IDENTICAL (7255 ticks) |
| d0-h2-o (p2d0oT, objects, no reserve) | 0 | 7258 | 43 | 340/340 | 332,288 | same to 739; differs from 740/741 (em float drift at 740, ms/ps at 741): not yet explained |

Control before step 0 (test 7): e 41, s30 heap_before 56,960.

Still to run: full-length pad 0 arm, padded-dar slab diagnostic (h2p: the slab actually used), bell, r10b s20 (f6),
New Game intros; the o vs reserve difference at 741.
