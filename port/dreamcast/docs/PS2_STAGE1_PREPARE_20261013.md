# Stage1 core-image preparation (2026-10-13)

Status: isolated implementation and host/SH-4 object checks pass. Full linked
build, exact staged-pack runtime, output pixels, physical hardware and STRICT
acceptance remain with the integration owner. This change does not change a
default or qualify the broader stage1 recipes.

## Problem and change

The corrected stageD8 Render phase reached the r117 puzzle batch, but the
replacement texture was absent and the resident-only batch refused with reason
31. The source fallback uses another texture, so drawing the fallback cannot warm
the replacement. In the outdoor r118 fixture the addition became resident only
after the first three rejected frames.

The existing `PS2_FX_ADDITIONS` feature now requests one reviewed core image at
non-skipped native begin, after model preparation and before source Render.
`TEX_RESIDENT` must also be enabled. There is no new feature knob. The request
validates the still-pending source ticket without consuming it: frame, room,
room generation, pool pointer/count and generator pointer/count must match.
Texture owner, animation shape, TPL/descriptor, original dimensions and I8 format
must qualify. The native side requires an exact identity from the current
`core_identities` owner and the reviewed original key:

| Source recipe | Texture | Original dimensions/format | Original key | Existing native payload |
| --- | --- | --- | --- | --- |
| r117 puzzle, STREAK enabled | 0x13 | 96 x 96, I8 | 5889803d-d2ef2224 | 128 x 128 ARGB4444 VQ, 6144 bytes |
| r118/r11c addition, HAZE enabled | 0x1f | 128 x 128, I8 | dbbad2e7-5b0b1eed | 128 x 128 ARGB4444 VQ, 6144 bytes |

The live staged core uses NTR external-image records. The request resolves those
records through the current core owner; it never hashes the discarded pixel
placeholder or substitutes a hard-coded key for an unknown source image.

The cache hit passes through the existing load/TEX_CHECK path and pins the actual
entry to the current native frame. A cold request first honors the existing
preload slot and byte reserves, current actor leases, missing-key suppression,
and real VRAM availability (including evictable stale bytes under TEX_KEEP).
One normal `load` request retains existing fragment/fence/upload/eviction rules.
Every drawn frame rechecks the real cache, so eviction can be recovered before
Render. No upload path is added to the atomic batch. No source RNG, pool,
generator, private simulation clock, callback, activation or suppression logic
is changed.

## Diagnostics

`PS2FXSTAGE1_PREP` logs only a texture/key/status change. Status 0 means inactive;
1 newly loaded; 2 resident hit; 3 unqualified live identity; 4 slot reserve;
5 byte reserve; 6 real pool limit; 7 known missing; 8 normal load refusal. A source
query refusal has no qualified descriptor and therefore reports inactive.

## Checks and limits

- `python3 tools/test_ps2_fx_stage1_prepare.py`: actual source query,
  SourceIdentityTable adopt/lookup, native preparation helper and source phase
  functions; 87 cases with TEX_KEEP=0 and 86 with TEX_KEEP=1, ASan/UBSan clean.
  The cache/load boundary is explicitly stubbed. It covers foreign/interior and
  stale owner records, exact source metadata/key gates, pending ticket identity,
  immutability, reserves/leases, frame pinning, eviction/load-failure recovery,
  native-begin ordering, skipped images and no calls during Render.
- `python3 tools/test_ps2_fx_stage1_phase.py`: 35 actual phase cases,
  ASan/UBSan clean.
- `tools/test_native_effect_stage1_batch.cpp`: 64 actual atomic batch cases,
  ASan/UBSan clean; resident-only behavior remains unchanged.
- SH-4 target compiler: baseline feature-off, candidate off and candidate on
  compile for both modified translation units using the stageD8 flags.
  After stripping debug, feature-off baseline/candidate objects are byte-equal:
  `native_ui` 312904 bytes, SHA256
  `f457a24e0c2ae5f70c70709fd10e0eb31b16c8a4874075d10f88f6ba38cfcae4`;
  `esp_sub` 71668 bytes, SHA256
  `f51d17bf3805930232c8b9ef5db7b2dcb28011d9012043452ce961e4d1b7d057`.
  This is two-object identity, not a linked-program identity claim.

The integration owner must build and run the exact staged core/native pack,
verify initial preparation and no reason-31 first-draw refusals, inspect the
puzzle and outdoor addition images, and retain all ordinary resource/owner and
retirement gates. The prior r118 fixtures include normal dog attacks/death;
they do not establish 120-second living-player or room-wide acceptance.
