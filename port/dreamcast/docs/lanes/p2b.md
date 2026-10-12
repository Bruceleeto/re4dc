# Lane p2b: Phase 2 lane B, objects and room packages (2026-10-11)

Owner of the room packages in Phase 2 (D367_PHASE2_PLAN.md). Worktree /root/probe/lanes-20261011/p2b/tree, work dir
/root/probe/lanes-20261011/p2b/work, evidence D:\Flycast-Evidence\re4-dreamcast\p2b-20261011. Private outputs:
re4-assets-private\p2b-20261011.

## B1 PS2 room objects (PS2_OBJECTS, disc data only)

The loose room objects (room-code set pieces: SetObjSmd / ModInfoMgr / EvtMgr.SetBin BINs of the room archive; etc
models: ETM BINs) are GameCube ModelData drawn by the recovered game on the generic model path (survey:
ps2cast-4-20261011\OBJECTS.md). `tools/ps2_objects.py` swaps only their geometry:

- It writes a GameCube-format ModelData whose positions, normals, UVs and GX streams come from the PS2 BIN of the same
  object. The GC header, joints, weight palette layout, part (material) headers and order, colour table, nTex and
  blend / flip joint tables are kept. A part with no PS2 triangle keeps its header with an empty stream.
- The GC TPL stays the texture: the PS2 UVs index the GC texture space (checked per material: coincident vertices
  agree to 0.003 in UV). The PS2 TPLs are reduced copies, so dc/tex.pak keys do not change.
- PS2 triangle -> GC part: the part of the nearest GC triangle sampling the same TPL image. Winding: oriented like the
  GC source (face normal vs corner normals). Weights: the PS2 bone weights as GC palette entries.
- `ps2_objects.py room` rewrites a native room `.dar` payload in place: each replaced BIN is le_mirror's `fmt_bin`
  of the rebuilt BIN. It refuses an entry that is not exactly le_mirror(GC BIN), so modified data is never
  overwritten. Every other payload byte is kept; offsets are recomputed (32-byte aligned).
- The knob is the staging (`st1/rNNN.dar` replaced in the fixture). The executable is byte-identical, so knob-off
  identity holds by construction. Collision (SAT / EAT / ETS), placement and room code are untouched.
- Prepared-table trap (fixed 2026-10-11): the native payload's ESQ (effect sequences, R4ESQTBL) and NTR (texture
  identities, R4NTBL) tables hold absolute payload offsets and the payload size; ESQ rows also point INTO ETM
  sub-files. A stale table halts at room entry ("invalid prepared native room effects"). `remap_native_tables`
  rebases every row through the entry and ETM sub-file moves, refuses rows inside a replaced body and checks that the
  referenced bytes moved intact.
- `--pad-to source` zero-pads the payload to the control's bytes (equalised gate arm: same heap 4 layout).
- The room archive is read into heap 4 (`DVD: Mem Alloc` at the heap 4 base), so a smaller payload frees heap 4 by
  the same number of bytes.

Interior cell trap (r100): the cell (dc/native/r100/interior.cell, ps2_interior_cell.inc) pairs with the r100 PS2
world mesh CRC / bytes. PS2_OBJECTS does not touch ps2-world.re4mesh, so the pairing is unchanged (`PCCULL cell ...
adopted` in both arms). r100 keeps the uvg world package (not tr4), as test 7 does.

### r100 (batch 1)

| object | GC tris | PS2 tris | payload bytes before -> after |
|---|---:|---:|---|
| BIN 0x1d (obm2a00) | 7,412 | 2,792 | 178,976 -> 74,848 |
| BIN 0x1f | 6,032 | 2,713 | 131,328 -> 63,264 |
| BIN 0x24 (pl0700) | 3,135 | 1,582 | 66,048 -> 37,056 |
| BIN 0x26 (pl0700a) | 3,151 | 1,571 | 66,240 -> 36,896 |
| BIN 0x27 (ModInfo) | 2,595 | 1,021 | 53,952 -> 26,304 |
| BIN 0x29 (ModInfo) | 3,012 | 1,276 | 61,408 -> 29,728 |
| BIN 0x31 | 3,018 | 1,675 | 62,624 -> 38,688 |
| ETM et0001 / et0100 / et0200 | 76 / 44 / 44 | 74 / 12 / 12 | 2,880 / 1,568 / 1,536 -> 2,816 / 640 / 608 |

Not converted: BIN 0x33 (158 = 158 tris), et0000 (GC BIN has no normal array the converter reads), et0d00 (PS2 176 >
GC 56: the PS2 strip count is not trusted). r100 payload 1,918,528 -> 1,602,816 B (heap 4 -315,712 B at r100 entry).

Gates and numbers: see "Ready to land" below.

## B2 combined r118 registry package

r118 holds both the female Ganado (PS2_GANADO_F) and the parasite dog (PS2_WOLF), and a room has one registry package,
so the two casts are merged: `tools/d367/merge_cast.py` builds one model_registry.py cast dir from both (descriptor
dirs copied, catalogs / archive audits / candidate revisions merged), and `tools/d367/model-registry/ps2-r118.json`
packages both descriptors for room 118. Output (private): re4-assets-private\p2b-20261011\reg-r118 (registry.re4nmr
79,360 B, arena 88,144 B vs 46,360 B for the female Ganado alone; role rows 52+5/64, source blobs 26+5/32).

PS2_WOLF staging for a test build (needs PS2_WOLF=1; the image `_end` is unchanged by it on the test 7 recipe):
- dc/native/r118/registry.re4nmr = reg-r118/package/r118/registry.re4nmr (this lane)
- dc/native/r11b/registry.re4nmr = ps2cast-4-20261011/packages/reg-wolf-11b/package/r11b/registry.re4nmr
- em/em22.drs = ps2cast-4-20261011/em22-prepared/em22.drs (prepare_enemy_motions em22 texture contract + aica_banks)
- dc/tex.pak + the wolf atlas c0afb726-15c7c9b5 (the female textures are already in the test 7 pak)

## Ready to land / results (2026-10-11, evidence D:\Flycast-Evidence\re4-dreamcast\p2b-20261011)

Disc data only (fixture `st1/rNNN.dar`); the executable is unchanged, so knob-off identity holds by construction. Private
dars: re4-assets-private\p2b-20261011\objects\{r100b,r100p,r103b,r108b,r118b}.

| room | objects | tris GC -> PS2 (per model) | payload bytes (= heap 4 freed) | gate |
|---|---|---|---|---|
| r100 | 7 set-piece BINs + et0001/0100/0200 | set pieces 28,355 -> 12,630 | 1,918,528 -> 1,602,816 (-315,712) | equalised arm (r100p) H2 STRICT 7128 ticks, decision_cmp MUST-IDENTICAL, s30 340/340 heap_before 56,960 = control; unpadded (r100b) s30 heap_before 332,288 but H2 diverges at frame 661 (enemies 41 vs 43: em10 parts alloc, the step 0 coupling) |
| r103 | et0100/0200/1100/1a00 | 1a00 952 -> 68, 1100 164 -> 68, crates 44 -> 12 | -20,576 | warp-in STRICT 1659 ticks MUST-IDENTICAL |
| r108 | et0100/1a00 | as above | -17,728 | warp-in STRICT 1100 ticks MUST-IDENTICAL |
| r118 | et0100/1a00 | as above | -17,728 | warp-in STRICT 2296 ticks MUST-IDENTICAL |

All runs: 0 HALT, 0 MISSING, 0 MISALIGN. Interior cell pairing unchanged (`PCCULL cell ... adopted` both arms).
hw ms, r100 house view 1450:1569 (p2bW, equalised dar), drawn tick: 191.81 -> 118.80 (RENDER 31.60 -> 27.75; the
"other(kos/irq)" PVR wait 136.6 -> 65.1); skipped ticks 36.48 -> 38.55. Only 1 drawn tick in the window: low confidence.

B2: PS2_WOLF arm (p2bTw) + reg-r118 + reg-wolf-11b + em22.drs + wolf atlas: H2 STRICT 7128 ticks MUST-IDENTICAL vs
control, s30 heap_before 56,960 = control. w1 walk reaches r118: `NMRPACK open room=0118 descriptors=2` (em17 + em22
skins), em22.drs loads (26,496 B), 0 HALT/MISALIGN.

## B3 (2026-10-11 evening, branch p2/b3-crow)

- r100 with the PS2_CROW package (build 39d41f68 + PS2_CROW=1, arm p2bTcr; lane A r100 package + prepared em23.drs)
  and the unpadded PS2_OBJECTS r100 dar (run h2-cro): NMRPACK r100 39,968 B, heap4 7,864,128 -> 7,815,296 (package
  48,832 B vs 26,400 for the control package, +22,432); room archive 1,918,528 -> 1,602,816 (-315,712); net heap 4
  freed at r100 entry 293,280 B. s30 340/340 heap_before 334,240 (control 56,960). 0 HALT / MISALIGN. The crow +
  GC-objects arm (h2-cr) failed in the harness (RUN_FAILED at boot, disk guard), not rerun.
- Crow room packages r105 / r109 (ps2-crow.json room_packages): 20,672 B on disc, arena 24,864 B each
  (re4-assets-private\p2b-20261011\reg-crow-105 / reg-crow-109). Gates pending (warp-in pairs queued, w105 / w109).
- r108 combined (em17 + crow, ps2-r108.json, cast regcast-r108): BLOCKED, model_registry "source blobs 26+7 > 32
  (actor_lifetime.inc templates mask)". Needs a runtime capacity change (lane A file) or fewer blobs: a decision.
- PS2 objects for r104 r106 r107 r10a r10b r11a r11b r117 r119 built (out/r1xxb); payload saved: r11b 46,784, r10b
  38,624, r117 30,368, r119 9,888, r106 3,776 (SetObjSmd 0x34 PS2 is larger: skipped), r10a 2,848, r11a 2,848,
  r107 1,984, r104 1,920. Warp-in gates pending (fixtures wi<room>-c/o, warps w<room>.txt).

### B3 gates (warp-in pairs, same image p2bT; crow pairs p2bT/p2bTcr)

| room | heap 4 freed | warp-in STRICT |
|---|---:|---|
| r10b | 38,624 | MUST-IDENTICAL 2851 ticks |
| r11b | 46,784 | unpadded MUST-DIFFER at frame 267 (enemies 1 vs 8, objects 1 vs 12: heap 4 layout coupling); padded (r11bp) MUST-IDENTICAL 2658 ticks |
| r117 | 30,368 | MUST-IDENTICAL 3719 |
| r119 | 9,888 | MUST-IDENTICAL 1420 |
| r106 | 3,776 | MUST-IDENTICAL 2700 |
| r10a / r11a | 2,848 each | MUST-IDENTICAL 2907 / 3025 |
| r107 | 1,984 | MUST-IDENTICAL 1925 |
| r104 | 1,920 | MUST-IDENTICAL 2411 |

All 0 HALT / MISSING / MISALIGN, room identities ok with the new archive bytes.

Crow packages: r109 (bridge walk r108 -> r109, package 20,672 B, heap 4 -24,992) MUST-IDENTICAL 3156 ticks vs control.
r105: MUST-DIFFER at frame 184 (System_flg 0x2000, enemies 16 vs 20) against both controls (p2bT and the same image
p2bTcr without the package, wc105-k; c vs k is STRICT, so it is the package, not the image). The package takes 24,992 B
of heap 4 at r105 entry before the room archive; same class as the r100 / r11b heap 4 layout coupling. r105 crow not
ready (needs D0-style reservation or an equalised check).

hw ms (hwproject, p2bW, drawn / skipped tick nominal; few drawn ticks per window, low confidence):
- r11b entry view 600:719 (padded dar): 41.20 / 40.96 -> 32.55 / 32.23.
- r117 entry view 600:719: 36.92 / 36.69 -> 36.91 / 36.70 (no change; the set piece is not in view).
- r10b Del Lago fb 2340:2419: 69.51 / 69.03 -> 69.70 / 69.17 (no change, within noise).
