# CH23 PS2 actor conversion candidates, 2026-10-13

These are private-data regeneration specifications and host-qualified candidates.
They do not establish target admission, appearance, encounters, or hardware speed.
No encounter, info, material, or source animation is removed to make a model fit.

## Exact source identities

| Preset | Actor/source initialization | Source infos in order (BIN/TPL, hex) | Bones | Converted nondegenerate triangles |
| --- | --- | --- | ---: | ---: |
| merchant13-c0/o0 | em13 type6, `Em13Set` + `em10ModelInit` | 1e7/1e8, 1f0/1f1, 1ee or 1ed/1f1, 1ef/1e8, 1e9/1ea, 1f4/1e8, 1f8/1e8 | 61 | 3165 / 3161 |
| merchant18-c0/o0 | standalone em18, `em18_R0_Init` | 5/6, e/f, 7/8, 12/6, 13/6, c or b/f, d/6 | 61 | 3165 / 3161 |
| cart-em3b-02 | em3b type2, `em3b_R0_Init` | b/c | 7 | 2328 |
| truck-em3b-00 | em3b type0, `em3b_R0_Init` | 4/5 | 8 | 2712 |
| mendez35-full | em35 type0, `em35_R0_Init` | 4/5, 6/5 | 83 | 6956 |
| mendez35-upper | em35 type1 | 7/5 | 76 | 5706 |
| mendez35-legs | em35 type2 | 8/5 | 83 | 1273 |

The em13 type6 model is the robed Ganado form that has the `em10_R1_Trade`
merchant routine. It is not actor em18. The two archives and their different
source info orders are independently checked. The complete hidden goods info
is retained; source visibility controls whether it draws. The em13 normal
wait/trade routines use base hands. Other em13 hand variants have a different
bone table and remain unqualified; exact identity matching must refuse them.

Every selected PS2 bone id, parent, and rest translation is compared with the
GC source skeleton before conversion. Runtime source identities retain the
actual GC BIN/TPL facts and archive digests. The geometry, diffuse images,
corner normals and weights come from the PS2 archive. Source normal lengths
are restored by `model_registry.py --source-normal-length`.

The cart has 24 triangles using negative repeated U coordinates. Its explicit
`repeat_uvs` preset reads the source TPL sampler and shifts a complete triangle
by an integer texture period only for GX_REPEAT. It never wraps individual
corners, clamps coordinates, changes UV derivatives, or splits/removes faces.
A triangle crossing a period boundary is refused. Other presets are unchanged.

## Material status

Robe, cloth, truck and Mendez mask runs are generated with `ps2_mask_runs.py`
against their exact source section and bound runtime-header SHA256. That tool
maps the source GC alpha material onto the PS2 triangles. The opaque and masked
runs retain all converted triangles. This mapping still needs target visual
review; package validation alone is not an alpha-coverage guarantee.

Mendez's GC material flags require bump and specular, and its body/upper form
also requires the mask pass. The converted PS2 atlas contains diffuse RGB;
it does not bake bump or specular. The spec's `source_drops: ["bump"]` records
the current Dreamcast source-path limitation, not a new PS2 shader:

- `src/game/trans.cpp:bumpSetup` loads the bump texture through `org_LoadTexObj`
  and calls indirect GX setup routines.
- `port/dreamcast/game/platform/gx_stub.cpp` implements `GXLoadTexObj`,
  `GXSetTevIndBumpXYZ`, and the indirect setup calls as no-ops.
- `trans.cpp:materialSetup` separately selects the diffuse texture through
  `re4dc_model_material`; `model_bridge.cpp` retains that diffuse selection.
  Source alpha has a separate bridge and is preserved by the mask runs.
- The existing generic native material policy already advertises Specular;
  this conversion does not change its lighting or claim a new specular stage.

The Bump capability allowance now also covers a qualified em35 registry plan
only when both ROUTE_CH23 and NATIVE_MODEL_REGISTRY_DROP_BUMP are enabled.
Other actors and non-registry plans receive no new capability. This narrowly
records the source-path limitation described above and still needs target
visual qualification. No transaction, lighting, or hand-cache code is changed.

## Reproduction and limits

Use `ps2_cast.py convert`, `ps2_cast_native.sh`, then `ps2_cast.py finish` and
`regcast`, with the presets above. The native script runs host tools only.
Its conversion workspace may be 512 KiB; that setting is not a Dreamcast
runtime-memory measurement. Generate the corresponding JSON specification with:

```text
model_registry.py SPEC OUTPUT --tree CHECKOUT --package-room ROOM \
  --wide-identity --source-normal-length --pack-bones 96 --ch23-facts
```

Add `--ch23-mendez-budget` only for room 11f. `ROUTE_CH23=1` permits 128 source
part facts; r11f alone permits nine images per source TPL and a 640 KiB room
package/skin budget. Other rooms keep 192 KiB and eight images. Default-off
limits stay 32 source part facts and 192 KiB. The loader allocates actual
package+skin bytes plus 32 alignment bytes, not the ceiling.

| Candidate room | Package bytes | Skin bytes | Arena bytes | Source part facts |
| --- | ---: | ---: | ---: | ---: |
| r10f (em13) | 105088 | 8160 | 113248 | 35 |
| r10d / r112 (em18) | 105088 | 8160 | 113248 | 35 |
| r11d cart | 42208 | 280 | 42488 | 7 |
| r200 truck | 137504 | 320 | 137824 | 15 |
| r11f all three Mendez forms | 607840 | 18152 | 625992 | 124 |

The r10d/r112 em18 candidates currently also require ROUTE_CH23 because they
need 35 facts. These specifications contain only the listed actors; when
combining with an existing room package, merge its descriptors rather than
replacing unrelated native actor coverage. Identity mismatch retains the
original source path and is not native acceptance.

## Host evidence

Private evidence root: `/root/probe/codex-ch23-enemies-20261013`.

- `test_ps2_cast_sections.py`: ten synthetic source-TPL/UV tests.
- `single-tpl-byte-regression.json`: thirteen chicken conversion files,
  including mesh, atlas, native arrays, source facts and validation, are
  byte-identical to d9bb69d. Both conversions use the same 0.002 mm tolerance.
- Each model's `native/host-check.txt` and `runtime/verify-blob.json` or native
  stage log record the host conversion/triangle check; each `manifest.json`
  pins its runtime header and texture package.
- `merchant-pack-validator-v4/results.json`: 35 package/refusal cases.
- `mendez-pack-validator-v2/results.json`: 36 package/refusal cases compiled
  with exactly 96 bones, including CH23-off and other-room budget refusal.
- `mendez-material-guard-host-v1/results.json`: 40 combinations compile the
  actual capability excerpt; the new bit requires both flags, id35, and the
  registry gate. This checks routing, not the full certificate or appearance.
- `candidate-shared-texture-content-proof.json`: repeated em13/em18 texture
  keys have byte-identical image metadata and payloads. Only their text labels
  and package checksums differ; r10f-v2 texture copies are canonical for staging.

Current package roots are `reg-r10f-v2`, `reg-r11d-v1`, `reg-r11f-v3`,
`reg-r200-v1`, `reg-r10d-v2`, and `reg-r112-v1`. Each contains
`package/rROOM/registry.re4nmr`, `tex/`, `registry-manifest.json`, and
`SHA256SUMS`. Stage registry payloads into `dc/native/rROOM/`. Texture payloads must use
`dc/tex/<first-hex-character-of-key>/<key>.re4tex` for TEX_RESIDENT; for example
`61519868-9ee3f93f.re4tex` belongs in `dc/tex/6/`. A flat `dc/tex/<key>.re4tex`
file does not satisfy the resident loader. Stage only in a coordinated fixture. No payload or private source archive belongs
in Git or a public package.
