# Lane ps2cast

Rules: port/dreamcast/docs/D367_WORKSTREAMS.md. Branch lane/ps2cast, tree /root/work/lanes/ps2cast, evidence
/root/probe/lanes/ps2cast, private assets `re4-assets-private/ps2cast-20260930/`.

## Goal

The user (2026-09-30): "we need to build the remaining character models and world sourced from PS2". This lane
converts PS2 character models (a converter, like the PS2 world converter; no hand modelling) into the cast bundle
format that `cast_bundle.py` / `coarse_ganado_cast.cpp` consume, compares them with the external cast's v4-fit
Ganados on cost and look, then converts the stage-1 characters the external cast does not cover, in route order.
The external cast delivery (cast-20260925, play-actor-bundle-20260928) is not modified.

## State and next step

- Done: the converter (tools below), reproducible end to end; the first PS2 Ganado (em15 type 00, r101) converted,
  bound to the GC skeleton, packed through the cast's own packer / host check / strip builder, bundled by
  cast_bundle.py unchanged; cost numbers and a look sheet against v4-fit.
- Next: the stage-1 character inventory table, then the remaining em15 / em12 appearances and the missing
  characters in route order (r106 after r103).

## The converter

| Tool | Runs on | Does |
|---|---|---|
| `tools/ps2_bin.py` | any Python | PS2 disc reader: ISO9660 -> BIO4DAT.AFS -> emXX.dat entry table; PS2 skinned model BIN decoder (JADERLINK RE4-PS2-BIN-TOOL layout: bones, materials, VIF nodes, weight maps, strips) |
| `tools/ps2_cast.py convert <preset> <out>` | Windows Python (numpy, PIL) | GC skeleton + signatures from the GC debug disc, PS2 mesh + weights + TPL atlas, validation, then the cast's packer (`character-prototype-20260925/tools/pack_coarse_actor.py`, unchanged) and the host fixture |
| `tools/ps2_cast_native.sh <out>` | WSL | host check (the cast's test_cast_dynamic.cpp built against THIS tree's native_actor_fast.cpp), fastpath build_blob / verify_blob / patch_header -> runtime header, pvrtex VQ + vq_export.py -> `<key>.re4tex` |
| `tools/ps2_cast.py finish / castdir` | Windows Python | manifest (counts from the runtime header), cast dir layout for cast_bundle.py (manifest, source-bindings with GC signatures, source.json, header, texture, em15-hand-N hand-pose signatures) |
| `tools/ps2_cast_run.sh <store> <preset>...` | Git Bash | all stages + the bundle (`<store>/bundle-<tag>`) |
| `tools/ps2_cast_sheet.py <spec> <png>` | Windows Python | look sheet: models side by side, same views and GC pose, runtime look (texture only) + geometry |

Presets: ganado-em15-00 / -0b / -03 / -04 (arcs from Em15Set), ganado-em12-01. Disc extracts are cached on ext4
(`/root/probe/lanes/ps2cast/inputs`, PS2CAST_INPUTS), sha256 in validation.json.

### Binding to the GC skeleton (the mapping)

- The PS2 em15.dat has the same entry slots as the GC em15.drs (arc = entry + 4; body 0x1bc, head 0x1be, hands
  0x1c0 / 0x1c5, TPL 0x1bd). Every section's PS2 bone table equals the GC BIN's: 34 bones, PS2 (id, parent) ==
  GC (partsNo/attach, parent) for all 34, rest translations equal to 5.5e-12 mm (body / head) and 1.1e-4 mm
  (hands). The converter asserts this (tolerance 0.001 mm).
- GC attach == index for all 34 parts, so a PS2 weight's bone id IS the GC part index (identity map, checked).
  Positions: PS2 s16 x the segment factor (1/16 for all 47 segments here) = GC millimetres, same axes (Y up).
  The packer's 1/16 quantization is then exact (max position quantization 0.0 mm).
- Weights: PS2 weight maps (up to 3 bones, float weights summing to 1 +- 3e-8); the packer keeps the last influence
  as the remainder as MakeWeightPalette does. UV = PS2 s16 / 256 (the world converter's rule), placed in its
  TPL image's 256 cell of the atlas. Winding as read agrees with the GC convention (face vs vertex normal
  agreement: PS2 99.8-100 %, GC 99.9-100 %), so no flip. One zero PS2 normal -> the face normal. No degenerate
  strip triangles.
- The runtime identifies the loaded GC model by the GC source signatures (counts + vertex FNV), so the
  appearance keeps the GC signatures and draws the PS2 mesh in its place; no format change was needed.

## Numbers (image, build, evidence)

Ganado em15 type 00 (r101 square), conservative level; counts from cast_bundle.py blob_stats on each runtime
header (the same tool for both). Unit costs: the cl lane's (D367_SQUARE_PERF_PLAN.md): 0.25 us per transformed
vertex (record), 0.30 us per palette switch (run), 0.93 us per palette entry, 0.07 us per emitted strip vertex.

| em15-00 | tris | records (/tri) | strip verts (/tri) | palettes | runs | meshlets | skin stream | modelled us / Ganado |
|---|---|---|---|---|---|---|---|---|
| GC source | 3013 | - | - | 111 (source) | - | - | - | - |
| v4-fit conservative (play build) | 898 | 821 (0.914) | 1402 (1.561) | 151 | 181 | 8 | 4552 B | 498 |
| v4-fit lean | 628 | 628 (1.000) | 1024 (1.631) | 112 | 122 | 7 | 3600 B | 369 |
| **PS2 ps2-v1 (no reduction)** | **1243** | **1148 (0.924)** | **1925 (1.549)** | **93** | **126** | 11 | 3016 B | **546** |

- The PS2 Ganado is NOT cheaper at equal look: +48 us per drawn Ganado vs v4-fit conservative (+9.6 %): 38 % more
  triangles outweigh 38 % fewer palette entries (93 vs 151; the most expensive unit) and fewer runs. Also +345
  triangles for the PVR per Ganado.
- Its look is closer to the GC source than v4-fit (sheet): the PS2 mesh is Capcom's own reduction (41 % of the GC
  triangles) with the source's weights; v4-fit is a Blender reduction to 30 %.
- For the crowd lane: the PS2 mesh has fewer palette entries than the GC source (93 vs 111) and than v4-fit
  (151). A reduction of the PS2 mesh to ~900 triangles at its own palettes would model at ~425 us (-73 us vs
  v4-fit) if records / strips per triangle hold; that is a hypothesis, not built (model reduction is not this
  lane's converter work).
- Texture: PS2 TPL 0x1bd = 3 x 256x256 4-bit CLUT (decoded, GS-unswizzled) -> one 512x512 atlas VQ, 67,584 B VRAM
  per appearance (v4-fit shares one 1024x512 human atlas across its 5 appearances).
- Validation (validation.json): PS2 -> GC surface distance at rest, median / p95 / max mm: body 0.0 / 11.9 /
  88.2, head 0.0 / 2.0 / 6.3, hands 1.9 / 5.7 / 7.1; over 114 GC poses (pose-samples.json, every 4th of 456) the
  p95 stays 18.3 / 2.6 / 9.1 at worst (binding correct: posed error ~ rest error). Host check PASS (1243
  triangles, 3 frames, 0 failures); strip verify PASS (triangle multisets SAME in all 4 infos); the pipeline is
  deterministic (rerun: identical mesh.json a9acd796.., header 74bae93b.., texture package 5f6e64e3..).
- Look sheet: `re4-assets-private/ps2cast-20260930/sheets/em15-00-look.png` (GC source / v4-fit / PS2, front,
  side, back, posed 3/4, geometry).
- Bundle: `re4-assets-private/ps2cast-20260930/bundle-em15-00` (cast_bundle.py, 1 appearance, 11 signatures).
  v4-fit comparison bundles (stats only): /root/probe/lanes/ps2cast/v4fit-bundle{,-lean}.
- No Flycast / hwproject run yet: these are modelled costs from the unit costs, not hardware ms.

## Ready to land

Nothing yet (tools only; no runtime change).
