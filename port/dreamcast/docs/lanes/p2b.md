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
