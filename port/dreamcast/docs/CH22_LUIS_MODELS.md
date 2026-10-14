# Chapter 2-2 Luis native-model source plan

Status, 2026-10-13: source inventory and explicit mapping proposal only. No Luis
package, renderer admission, captured animation, or visual acceptance is claimed.
The complete PS2 model is available, but its sections and hair rig differ from GC.

## Identity and source inputs

`src/game/read.cpp` has `EmFileTbl[4] = {0x49, 0x4a, 1}`. The corresponding
`FileTbl` entries in `src/game/dvd.cpp` are `em/pl14.das` and `rel/pl14.rel`.
Luis is enemy id 4. The introductory id-3 comment in `src/pl14/pl14.cpp` is not
authoritative; the executable file tables and `cEmMgr::construct` bind the id.

Private source inputs live in `/root/probe/codex-ch23-enemies-20261013/luis-inputs/`:

| Input | Bytes | SHA-256 |
| --- | ---: | --- |
| PS2 `pl14.dat` | 604128 | `4949d656d05a3e25f37f5c511a3cdbb5aa04ab2a8bdb649071b63c2e34e2d4a5` |
| GC `pl14.drs` | 999072 | `2b5b554d45a67f12612474a9ed0a1bbeb7cf5882d16a7c67ce7ff25018676f27` |

`luis_inventory.py` and `luis_inventory_details.py` in that private root reproduce
`luis-model-inventory-v4.json`. It records every source part head, material,
texture count, bound, used weight id, and proposed hair root match. The initial
v1 same-index experiment failed and is retained as diagnostic evidence.

## Model sections

ARC numbers are entry index + 4. Triangle counts below are raw decoded source
triangles, before the converter's degenerate-triangle removal.

`cSubLuis::modelSet` appends six GC model infos in this exact order:

| GC BIN/TPL | Part heads | Triangles | Material facts | Source contract |
| --- | ---: | ---: | ---: | --- |
| `04/05` | 90 | 3477 | 14 | Body, bump and specular |
| `06/07` | 12 | 1021 | 5 | Opaque head/neck, including eyes |
| `08/07` | 12 | 1507 | 1 | Face; retained by `pFace` |
| `09/05` | 90 | 3512 | 50 | Hair, mask and source pass |
| `0a/05` | 2 | 650 | 2 | Right hand, owner bones 9/10 |
| `0b/05` | 2 | 650 | 2 | Left hand, owner bones 15/16 |

Geometry bounds and weight ids establish these roles. In particular, the source
comment calling BIN 06 the hair is inconsistent with the archive: BIN 09 uses
hair bones 64-89 and all of its materials request a mask; BIN 06 uses head/neck
and eye bones. All seven GC BINs, including the gun, have shape offset zero.

The PS2 actor contains four BINs, all using TPL 05:

| PS2 selection | Part heads | Triangles | Corresponding GC ownership |
| --- | ---: | ---: | --- |
| BIN 04, material 0, diffuse 2 | 72 in BIN | 1194 | Merged head/neck/face: GC 06 + 08 |
| BIN 04, materials 1-4 | 72 in BIN | 1228 | Body: GC 04 |
| BIN 06 | 13 | 1273 | Masked hair: GC 09 |
| BIN 07 | 2 | 258 | Right hand: GC 0a |
| BIN 08 | 2 | 244 | Left hand: GC 0b |

The body/head split follows the material bounds and bone use, not nearest-face
matching. PS2 head material 0 weights the eyes 32/33 but does not weight GC's jaw
27 or eyelid 28. A PS2 mesh therefore must not be advertised as retaining the
GC face's full deformation. No gameplay eye or neck routine should be altered.

The gun is a separate object: `cSubLuis::equipWeapon` creates object id `0x0b`,
loads GC BIN/TPL `0e/0f`, and attaches it to owner bone 10. Its PS2 counterparts
are `0b/0c` (857 raw triangles versus 967 GC, seven part heads in both). It needs
its own source identity and lifetime certificate; it must not be folded into
Luis's body descriptor. The thrown pickup object is a different owner/path.

## Skeleton and hair mapping

The GC body owns 90 bones. PS2 body bones 0-63 have the same ids, parents, and
translations (maximum component difference `1.82e-12` game units). Body and hands
can retain their existing owner bone ids. Sparse attachment part tables use
`attach` as the owner identity; the GC parser's local `no` is not that identity.

PS2 hair uses eight independent children of head bone 4. GC uses 26 hair bones
in chains. Four roots have an exact matching source rest translation:

| PS2 id | GC owner id | Rest match |
| ---: | ---: | --- |
| 64 | 64 | Candidate only; root displacement 38.9581 mm |
| 65 | 66 | Candidate only; root displacement 58.9415 mm |
| 66 | 72 | Exact parent and translation |
| 67 | 74 | Exact parent and translation |
| 68 | 78 | Exact parent and translation |
| 69 | 80 | Exact parent and translation |
| 70 | 85 | Candidate only; root displacement 58.9415 mm |
| 71 | 88 | Candidate only; root displacement 38.9581 mm |

This is an anatomical root proposal, not a certified animation mapping. Keep the
original 90-bone runtime skeleton, cloth update, and matrices. For a prototype,
map only the native mesh weights, using the selected GC inverse rest matrices
so the original PS2 rest-position geometry remains unchanged. A simple index
copy or an increased numerical tolerance is invalid. The remaining GC chain
bones continue updating even if the reduced PS2 mesh does not weight them.

Require a rest-pose numerical comparison and animated pose captures covering
head turns, locomotion, firing, hit reactions, and hair swing before admitting
this map. Inverse-bind correctness proves the rest pose only; it cannot prove
that eight PS2 hair roots reproduce 26 GC hair bones. If the shifted roots or
reduced chain look wrong, preserve full GC hair in a separate native candidate
or fit reviewed weights across the original GC chain. Do not change cloth logic.

## Bounded implementation work

1. Add explicit PS2 BIN/TPL/material selections separate from GC source-info
   bindings. Qualify all six GC infos before drawing any part of the actor.
   The merged PS2 head needs an ownership group for GC 06+08; emitting it twice
   or quietly omitting the second source identity is invalid. The current
   one-chunk-per-info generator cannot express this directly.
2. Support sparse attachment signatures without requiring every section to have
   90 part heads. Retain the exact source counts, attachment ids, parents, and
   normalized BIN hashes. The current generator rejects the 12/2-head sections.
3. Add an explicit opt-in mesh-only hair map with the proof and review above.
   Keep PS2 hair's alpha silhouette and source mask pass. Do not use an opaque
   atlas as an alpha substitute.
4. Retain all source material and TPL facts. Luis alone needs 74 material facts,
   six infos, 90 runtime bones, and 11 distinct source TPL image facts (8+3).
   The seven-head gun adds nine material facts and one TPL image. The 208 summed
   actor part heads are not 208 material facts. The current 128-material CH23
   limit covers Luis alone, but the ordinary eight-TPL-image limit does not;
   compute the merged r11c package including other actors before choosing limits.
5. GC body BIN 04 requires the bump/specular contract. The qualified em35-only
   material exception does not admit Luis. Any extension must be id-4 qualified,
   behind the existing drop-bump guard, and preserve diffuse/alpha evidence.
   Do not broaden generic material admission or modify transaction/lighting work.
6. Build a complete private candidate, validate malformed identity and capacity
   cases on host, and measure the actual packed allocation. Only the coordinator
   stages/builds the disc and runs the owned capture lane. Preserve the route's
   logic trace and state; no CH22 ESL work belongs to this model conversion.
