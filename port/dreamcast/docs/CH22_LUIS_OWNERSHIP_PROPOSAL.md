# Luis merged source ownership proposal

This is a proposal, not a runtime patch. It follows `CH22_LUIS_MODELS.md` and the
private `models/luis-actor-v1/coverage-manifest.json` in the lane evidence root.
Root coordinates the two transaction hunks with the lighting owner before edits.

## Offline evidence now available

`tools/ps2_luis.py` emits all 4197 PS2 actor triangles and all 857 gun triangles.
The actor retains six GC source-info identities with draw roles `0,1,3,4,5`.
Role 1 covers the merged PS2 head against GC source roles 1 and 2. Source
bindings still include both distinct GC BIN/TPL pairs, 06/07 and 08/07.
No triangle is removed, duplicated, or assigned to a fabricated empty mesh.

All source BIN, TPL, and material identities are in the coverage manifest.
All decoded PS2 texture images, including the separate opacity image, are
retained. The RGB atlas by itself is not a completed masked material.

The eight hair roots match unique source GC roots by exact X coordinate and
parent 4. Four also match Y/Z exactly. The other four record the actual source
rest displacement as an explicit transform; no nearest-bone search or tolerance
increase chooses a root. For PS2 rest P and matched GC rest G, the virtual root
is `G_animated * inverse(G) * P`; its skin transform simplifies to
`G_animated * inverse(G)`. This preserves the PS2 rest geometry. It does not
prove source cloth-animation equivalence.

Actual bind proof: maximum rest-position error `0.000050253` mm (source floating
weight sums); maximum virtual-root algebra error `2.28e-13` mm. Gun errors are
zero. The matrix test is synthetic math, not captured animation.

Actual native host checks: actor 4197 triangles, 12591 triangle checks, three
host frames, zero failures; gun 857 triangles, 2571 checks, zero failures. These
used a 512 KiB host conversion workspace, not target memory. The sparse-source
adapter `tools/ps2_luis_native.py` verifies all five chunks through an ordinal
scratch view and restores roles 0/1/3/4/5 in the runtime header. Exact triangle
multisets and the coincident head group draw order pass. Runtime admission,
source animation review, and user visual acceptance remain pending.

## Narrow package representation

Retain six descriptor sections and six source roles. Add a CH22-only ownership
marker to the reference word currently required to equal the section index:
ordinary word values remain unchanged; only role 2 of the qualified id-4,
90-bone, six-info Luis descriptor may encode `0x80000001` (covered by role 1).
The covered reference must repeat role 1's exact geometry and texture indices,
and neither reference may request a mask. This marker means shared geometry
ownership, not permission to drop a source identity. A source-role fact row for
each of the six infos remains mandatory.

The runtime chunk keeps its original source-info index. Store the draw owner in
a CH22-only field/array instead of repurposing `source_info`. A normal chunk owns
itself. Role 2 shares role 1's input geometry for immutable proof and lifetime
accounting but emits no draw run. Source roles 1 and 2 must have identical live
visibility/pass flags and model-info matrices; if they differ, decline the whole
actor. Their other mutable render state remains subject to every existing
per-info transaction and material check. Independent head/face visibility is
not silently approximated by the merged mesh.

Only permit this exact coverage relation after all descriptor, reference,
source-model, material, and texture bounds checks. Default-off code remains the
original literal branches, including comparisons and calls. Existing packages
keep the same reference words and identities.

## Fully masked hair role

PS2 BIN 06 material 0 is exactly `0403ff04ff000000000000ff30010000`:
flag 4, colour image 3, opacity image 4 from TPL 05. All 1273 triangles
in that source section use this material. An opaque run with any of those
triangles would therefore be fabricated, and a zero-triangle geometry is
correctly rejected by the existing package validator.

Use a CH22-qualified mask-only reference for Luis role 3: reference word 12
keeps its existing pair texture indices and masked geometry byte; a zero low
byte means there is no opaque run. Accept it only for id 4, 90 bones, six
source infos, role 3, and a pinned coverage manifest proving that every hair
triangle uses the masked source material. `mask_geometry[0]` remains `~0u` and
`mask_geometry[1]` names the complete hair run. Both ordinary two-run masks and
ordinary opaque references retain their old encodings and literal off path.

The owner planner must allocate only the pair material for this role, emit one
nonempty masked run with all 1273 triangles, and retain the primary immutable
input for the all-info proof. No empty run, extra plain material or skipped
material certificate is allowed. The matching helper must recognize the one
masked run and prove its geometry, UV, texture keys and blend/depth state. This
requires changes only in the already listed pack validator, registry owner and
offline generator; the transaction sees complete role-3 triangle coverage.

Preserve both source decoded RGBA images and the raw TPL/CLUT. PS2 diffuse and
opacity alpha differ slightly. Resolve the actual opacity sampling channel and
GS alpha normalization from source renderer evidence before calling any
ARGB4444 pair exact. Do not silently replace this with a nearest GC mask bake.

## Runtime files and exact protected scope

- `coarse_actor_registry_pack_check.inc`: guard the special role-2 marker;
  validate duplicate geometry/texture, id/bones/section count and source facts;
  retain literal old comparisons under `#else`. Compute merged r11c capacity
  from actual generated bytes before extending its texture fact limit.
- `coarse_actor_owner_registry.inc`: preserve six bindings, six immutable input
  proofs, six lifetime snapshots and palette slots. Record the covered role;
  emit five draw groups; make `re4dc_registry_runs_match` verify exactly those
  groups. Provide a helper returning the validated covered-role mask (bit 2 for
  this Luis descriptor, zero for other descriptors, failure for an invalid
  covered group). The helper checks equal flags/matrices and equal geometry
  input identity; it does not certify materials by itself.
- `tools/d367/model_registry.py`: opt in to the exact offline coverage manifest;
  fingerprint all six source infos, allow the exact sparse source part-head
  tables, and emit the role-2 marker while retaining all material/TPL facts.
- `coarse_actor_material.inc`: separately qualify id 4 for the existing guarded
  bump-drop source proof. No diffuse, normal, alpha, or lighting changes.

The only requested protected transaction changes are the final coverage checks
in `actor_semantics` and its diagnostic twin `actor_semantics_why`. In this lane
base they follow the draw-run proof loops at lines 154-155 and 215-216. They must
be guarded by `RE4DC_ROUTE_CH22`; keep the original two lines literally in the
default-off branch. Proposed on-path logic, after every existing run proof:

```cpp
// covered is validated by the registry helper; p.count stays six.
if (!registry_covered_roles(m, p, &covered)) return false;
if ((seen | covered) != (1u << p.count) - 1u || (seen & covered) ||
    materials != (1u << p.material_count) - 1u) return false;
for (unsigned i = 0; i < p.count; ++i)
    if (triangles[i] != ((covered & (1u << i)) ? 0u : p.input[i].triangles))
        return false;
```

The helper returns zero coverage for non-registry plans and ordinary registry
plans. The diagnostic twin uses the same helper/conditions and existing error
codes 26/27. No changes to source lighting, matrix construction, transaction
acquisition, lease handling, submission, hand bindings, or destruction/reset.
The existing all-info `exact_infos`, per-info immutable proofs, and material
certificate remain mandatory, including the covered face info.

## Required negative evidence

Test both guards off/on and reject alias markers for other ids, bones, info
counts, roles, owners, rooms or malformed references; missing/duplicate source
fact rows; aliased geometry/texture disagreement; a mask on either head role;
and a coverage cycle. Prove all six original source identities still matter by
mutating the covered face model's normalized identity, TPL, visibility, matrix,
and lifetime independently. Each must decline before submission. A spurious
role-2 draw must fail the double-coverage check. Omitted primary head or hair
runs must fail coverage. Verify the 4197 source triangle multiset once, exact
mask silhouette, unchanged off build bytes, and a matched runtime logic trace.
Captured head turns, firing, walking, hit reactions, and hair swing remain the
visual qualification for the retargeted hair.

## Implemented candidate and host evidence (2026-10-13)

The guarded coverage contract is implemented in the four runtime files above.
The only transaction edits are the two final coverage checks. The generator's
`--ch22-luis-coverage` switch requires room 11c, the pinned coverage manifest,
source skeleton/identity JSON, exact sparse source part tables, all six
normalized BIN digests, and the proved native header. Hair keeps its entire
original stream, with an exactly reversible atlas-to-source UV transform.
CH22 alone permits 83 material facts in r11c (74 for Luis and 9 for the gun);
other rooms retain 32 unless CH23 is enabled. No arena ceiling increase is used.

The candidate selects the PS2 hair diffuse image's alpha. This is supported by
the [PS2 actor format viewer's material binding](https://github.com/JADERLINK/JADERLINK_MODEL_VIEWER/blob/ecd32acd1c62cf34ce4a6e958d8ea1ddafbd7dec/ALL_VIEWER/RE4_PS2_MODEL_VIEWER/src/LoadPs2BinModel.cs#L291-L301)
and [its alpha sampling shader](https://github.com/JADERLINK/JADERLINK_MODEL_VIEWER/blob/ecd32acd1c62cf34ce4a6e958d8ea1ddafbd7dec/ALL_VIEWER/Resources/ObjShaderFrag.frag#L28-L42).
This is format-renderer evidence, not a capture of the original PS2 GS commands.
The original diffuse image 3 has TEX0 `400000059d308000` (TCC 1, MODULATE),
128x64 PSMT8 RGBA. `ps2_luis_mask.py` preserves both original decoded images
and the raw TPL, using image 3's own alpha while retaining opacity-index image 4
as evidence. It emits the established native ARGB4444 pair format, with RGB
high-nibble and alpha `/17` quantization, and reads back every package texel.

This conversion changes 53 alpha levels to 15. Maximum alpha error is 16/255;
mean absolute error is 1.264893/255. The 771 texels below the first native
alpha step become zero; all 4629 fully opaque texels stay opaque. This is an
explicit native-format approximation requiring look review, not pixel-exact
PS2 opacity or proof of original alpha-test/blend registers.

The combined body + independent gun package is 140288 bytes with 4568 bytes
of unique skin data: 144856 bytes of the existing 196608-byte arena. It has
7 source references, 7 geometry records (including the complete hair run),
7 source BIN identities, 83 material facts and 12 source texture facts. The
head/face pair is the only shared primary geometry. Texture payloads are a
67584-byte VQ body atlas, a 16384-byte native hair pair, and the 4096-byte gun
atlas. These are candidate resource sizes, not runtime residency measurements.

Reproducible host checks:

- `tools/test_luis_coverage.py`: 328 extracted helper/transaction checks across
  CH22/PACK off/on, including input identities, visibility, all 12 matrix
  elements, missing/double coverage and triangle totals.
- `tools/test_luis_mask_runs.py`: 50 checks of the actual run matcher, including
  complete mask-only coverage, material state and unchanged opaque/two-run masks.
- `tools/d367/test_luis_pack.py <private fixture> <fresh private out>`: 100 real
  loader checks, including every pinned source identity, malformed aliases and
  masks, CH22-disabled rejection and CH22-only acceptance.
- `tools/d367/test_luis_generator.py <private fixture spec> <fresh private out>`:
  19 fail-closed cases for opt-in, source data, sparse tables, native header,
  complete hair stream/UVs and missing/fabricated runs.

With CH22 and CH23 disabled, all four modified runtime includes preprocess to
identical bytes against the pre-candidate base. Target ELF equality, complete
runtime admission, independently mutated source lifetime checks, original
animation/logic traces and visual review remain separate acceptance work.