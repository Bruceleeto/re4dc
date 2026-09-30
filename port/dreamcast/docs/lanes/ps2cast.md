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
- Done: the stage-1 character inventory (below; `tools/ps2_cast_inventory.py`).
- Next (route order): the Ganado appearances the cast lacks that fit the cast format (em13 type 6 from r104,
  em17 / em16 type 0xc from r108 / r11d) through ps2_cast.py; for the non-Ganado characters (em2a traps from r100
  on, em29 bats and em2e crawlers in r106, ...) the runtime format proposal below comes first.

## Stage-1 character inventory (2026-09-30)

`python3 port/dreamcast/tools/ps2_cast_inventory.py /root/probe/lanes/ps2cast/inventory` (WSL): every required
room in route order (plus the alternates r10c/r10e, r11e) through `assets.sh discover` (enemy list entries with
model type, script loads / spawns, event actors). Ganado appearances resolve through each module's EmXXSet
(src/emXX/emXX_set.cpp: TPL / body / head arcs per model type); the key is archive:body/head/tpl. "External cast"
= the GC body and head signatures match a cast Ganado's (what coarse_ganado_cast.cpp matches, so identical
models in other archives are covered automatically), or the cast's animal packs, or leon4k. "PS2 source" = the
PS2 archive has BINs at the same arcs with bone tables equal to the GC's (the converter's precondition). ESL
ids map to archives through read.cpp EmFileTbl (0x03 -> pl11, 0x04 -> pl14, 0x0f -> pl0f). Event rows are evd
actor groups (their models load from the event files, not the enemy archive). Output: inventory.json / .md.

| Character | Name | Model types | Rooms (route order) | External cast | PS2 source | GC tris | PS2 tris |
|---|---|---|---|---|---|---|---|
| event:pl00 | Leon | - | r120 r100 r101 r106 r104 r105 r102 r10b r11b r119 r117 r11c r11f | leon4k (cl lane) | event model (evd files) |  |  |
| event:pl07 | pl07 (event actor) | - | r120 r100 r10b | **missing** | event model (evd files) |  |  |
| em12:0x1bc/0x1be/0x1bd | Ganado (em12 set) | 0x0 | r100 r103 r106 r107 r10a r11a r10c | ganado-em15-00 | yes, skeleton identical | 3013 | 1243 |
| em12:0x1d8/0x1da/0x1d9 | Ganado (em12 set) | 0x1 | r100 r103 r106 r107 r10a r11a r10c | ganado-em12-01 | yes, skeleton identical | 3057 | 1234 |
| em12:0x1dc/0x1de/0x1dd | Ganado (em12 set) | 0x3 | r100 r103 r106 r107 r10a r11a r10c | ganado-em15-03 | yes, skeleton identical | 2829 | 1003 |
| em12:0x1e0/0x1e2/0x1e1 | Ganado (em12 set) | 0x4 | r100 r103 r106 r107 r10a r11a r10c | ganado-em15-04 | yes, skeleton identical | 3014 | 1237 |
| em21 | dog | 0x0,0x1 | r100 r103 r119 | dog-00/01 | em21.dat (1 BINs) |  |  |
| em23 | crow | 0x0 | r100 r105 r108 r109 | crow-folded/spread | em23.dat (3 BINs) |  |  |
| em2a | traps (bear trap, tripwire bombs) | 0x0,0x2 | r100 r106 r107 r105 r10a r111 r113 | **missing** | em2a.dat (3 BINs) |  |  |
| event:em10 | Ganado (em10 set) | - | r100 r101 r106 r104 r119 r11c | **missing** | event model (evd files) |  |  |
| em15:0x1bc/0x1be/0x1bd | Ganado (em15 set, r101 village) | 0x0 | r101 r105 | ganado-em15-00 | yes, skeleton identical | 3013 | 1243 |
| em15:0x1c9/0x1cb/0x1ca | Ganado (em15 set) | 0xb | r101 r105 | ganado-em15-0b | yes, a section rest differs 2.0 mm | 2925 | 1241 |
| em15:0x1dc/0x1de/0x1dd | Ganado (em15 set) | 0x3 | r101 r105 | ganado-em15-03 | yes, skeleton identical | 2829 | 1003 |
| em15:0x1e0/0x1e2/0x1e1 | Ganado (em15 set) | 0x4 | r101 r105 | ganado-em15-04 | yes, skeleton identical | 3014 | 1237 |
| em26 | cow | 0x0,0x1 | r101 r103 | cow-00/01 | em26.dat (1 BINs) |  |  |
| em28 | chicken | 0x0,0x1 | r101 r103 | chicken-00/01 | em28.dat (2 BINs) |  |  |
| event:em13 / em15 / em16 | Ganados in events | - | r101 r106 r119 | **missing** | event model (evd files) |  |  |
| em29 | bats | 0x0 | r106 r10e | **missing** | em29.dat (1 BINs) |  |  |
| em2e | small crawler | - | r106 | **missing** | em2e.dat (1 BINs) |  |  |
| event:em34 | em34/em37/em33 large biter | - | r106 r105 r11f | **missing** | event model (evd files) |  |  |
| event:pl04 | pl04 (event actor) | - | r106 r104 r11c | **missing** | event model (evd files) |  |  |
| em13:0x1bc / 0x1d8 / 0x1dc / 0x1e0 | Ganado (em13 set) | 0x0,0x1,0x3,0x4 | r104 r11c r10f | the em15-00/em12-01/em15-03/em15-04 casts | yes, skeleton identical | 3013 / 3057 / 2829 / 3014 | 1243 / 1234 / 1003 / 1237 |
| em13:0x1e7/0x1e9/0x1e8 | Ganado (em13 set) | 0x6 | r104 r11c r10f | **missing** | yes, skeleton identical | 2055 | 1837 |
| event:em18 | merchant | - | r104 r102 | **missing** | event model (evd files) |  |  |
| event:em30 | large stationary parasite enemy | - | r104 r117 | **missing** | event model (evd files) |  |  |
| em27 | lake fish | 0x0,0x1 | r107 r11b r10e | **missing** | em27.dat (1 BINs) |  |  |
| event:pl02 / pl82 | event actors | - | r105 | **missing** | event model (evd files) |  |  |
| em18 | merchant | 0x0,0x1 | r102 r10e r112 | **missing** | em18.dat (8 BINs) |  |  |
| em17:0x1bc / 0x1d8 / 0x1dc | Ganado (em17 set) | 0x0,0x1,0x3 | r108 r118 r111 r113 | the em15-00/em12-01/em15-03 casts | yes, skeleton identical | 3013 / 3057 / 2829 | 1243 / 1234 / 1003 |
| em17:0x1cd/0x1cf/0x1ce | Ganado (em17 set) | 0xc | r108 r118 r111 r113 | **missing** | yes, skeleton identical | 2981 | 1242 |
| em24 | small box / coil enemy | 0x0 | r10a | **missing** | em24.dat (2 BINs) |  |  |
| em2f (+ event) | lake monster (boss) | 0x0 | r10b | **missing** | em2f.dat (3 BINs) |  |  |
| pl0f (+ event) | lake boat (Del Lago fight) | 0x0,0x2..0x5 | r10b r11b r10e | **missing** | pl0f.dat (5 BINs) |  |  |
| em22 | dog (parasite dog) | 0x0 | r11b r118 | **missing** | em22.dat (3 BINs) |  |  |
| em2b (+ event) | giant | 0x0,0x2 | r119 r11e | **missing** | em2b.dat (14 BINs) |  |  |
| event:em21 | dog | - | r119 | dog-00/01 | event model (evd files) |  |  |
| em3b | truck / mine carts | 0x1,0x2 | r118 r11d | **missing** | em3b.dat (2 BINs) |  |  |
| em11:0x1fc/0x1fe/0x1fd | Ganado (em11 set, 37 bones) | 0x7 | r117 | **missing** | bone tables differ: 0x1fe 13 vs 37, 0x204 4 vs 41, 0x208 4 vs 41 | 2758 | 1065 |
| event:pl01 | pl01 (event actor) | - | r117 r11c r11f | **missing** | event model (evd files) |  |  |
| pl11 | Ashley (partner archive pl11) | - | r117 r11c | **missing** | pl11.dat (8 BINs) |  |  |
| pl14 | Luis (partner, cabin fight r11c) | - | r11c | **missing** | pl14.dat (5 BINs) |  |  |
| em16:0x1c9 / 0x1dc / 0x1e0 | Ganado (em16 set) | 0xb,0x3,0x4 | r11d | the em15-0b/em15-03/em15-04 casts | yes (0x1c9: a section rest differs 2.0 mm) | 2925 / 2829 / 3014 | 1241 / 1003 / 1237 |
| em16:0x1cd/0x1cf/0x1ce | Ganado (em16 set) | 0xc | r11d | **missing** (same models as em17 type 0xc) | yes, skeleton identical | 2981 | 1242 |
| em35 (+ event) | beam hall boss | 0x0,0x1,0x2 | r11f | **missing** | em35.dat (5 BINs) |  |  |

Readings:
- Ganados: the external cast's five appearances cover every Ganado model in the stage except three: em13
  type 6 (r104, r11c, r10f), the type 0xc model shared by em17 / em16 (r108, r118, r111, r113, r11d) and em11
  type 7 (r117; a 37-bone skeleton whose PS2 head / hands carry reduced bone tables: needs an id-based bone map
  in the converter and a runtime that is not fixed at 34 bones). The first two convert with ps2_cast.py as is.
- em15 / em16 type 0xb: the PS2 head BIN's rest differs from the GC head by 2.0 mm (the GC head itself is
  ~1.6 mm off the body; cast_bundle.py reports this spread): converting it needs --bone-tol 2.1 and moves face
  vertices by up to ~2 mm.
- Everything else missing is a non-Ganado character (traps, bats, crawler, fish, merchant, boss, boat, giant,
  parasite dog, carts, Ashley, Luis) or an event actor. The PS2 disc has every one of their archives.
- Leon (pl00) is the cl lane's leon4k; Ashley (pl11) and Luis (pl14) are partner archives with their own sets.

## Proposal: a runtime format for non-Ganado characters (for the coordinator / crowd lane)

coarse_ganado_cast.cpp (and cast_bundle.py) express exactly one kind of model: a 34-bone Ganado appearance of four
sections (body, head, right hand, left hand) matched by GC signatures, one texture. The PS2 conversion itself is
general (the cast packer takes any bone count and section list; the external cast's animal packs already use
that pack layout), so the converter can write the same per-model pack (native arrays, strip blob, runtime
header, texture package, GC signatures) for any character. What the runtime lacks is an adapter that draws a
pack for a non-Ganado model: proposal, not implemented here (runtime code belongs to crowd / coordinator):
- a generic coarse model table keyed by the GC ModelData signature (positions, normals, palettes, vertex FNV)
  per section instead of the fixed role order, with the pack's own bone count (kBones per pack, not a
  static_assert on 34) and parents / inverse bind per pack;
- sections optional (a bat, a trap: one section), several textures per pack (a boss); the skin, pregate and
  one-submit paths already work per chunk;
- the bundle maker (cast_bundle.py) generalised the same way (per pack: bone count, chunk list, signatures).
Until then, non-Ganado characters keep the source renderer path.

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
