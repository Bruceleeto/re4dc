# PS2 vegetation cutout candidates

`tools/ps2_vegetation_candidate.py` builds offline candidates from explicit, hash-pinned
material decisions. It reuses `d367/charbake/cb_tex.py` for native texture packaging and
`d367/texpack.py` for the packed texture index. It does not regenerate meshes, infer
semantics from alpha histograms, change gameplay, or accept a visual result.

The existing generic converter option `--cutout-max-alpha 224` has a narrower meaning:
it recognizes an exact two-value source alpha set `{0,max}` with `max >= 224`. It is
not a general per-pixel threshold. This tool applies an individually reviewed
threshold to an explicit texture key and source texture index.

## Input contract

The policy schema is `re4dc-ps2-vegetation-policy/1`. Every file reference has a
`path` and SHA-256; relative paths resolve against the policy file. Source PNGs,
policies containing private paths, game packages, previews and proof outputs
belong outside Git.

```json
{
  "schema": "re4dc-ps2-vegetation-policy/1",
  "tex_pak": {"path": "baseline/tex.pak", "sha256": "<sha256>"},
  "rooms": [{
    "room": "r101",
    "r4pw": {"path": "baseline/ps2-world.r4pw", "sha256": "<sha256>"},
    "mesh": {"path": "baseline/ps2-world.re4mesh", "sha256": "<sha256>"},
    "ids": {"path": "baseline/ps2-world.ids", "sha256": "<sha256>"},
    "materials": [{
      "key": "<8-digit-crc>-<8-digit-fnv>",
      "source_texture_index": 3,
      "class": "vegetation",
      "semantic_review": true,
      "label": "reviewed cutout foliage",
      "threshold": 160,
      "rgb_gain": [1.0, 1.0, 1.0],
      "source_png": {"path": "source/0003.png", "sha256": "<sha256>"}
    }]
  }]
}
```

Add the hash-pinned `cell` file reference for r100; it is mandatory there.
`semantic_review` records source/material inspection, **not user approval of the
result**. Only vegetation and fence/ironwork classes are accepted. Soft effects,
ground overlays, gradients, water, glass, fades and unclassified materials stay TR.

The source image must decode to the exact current native16 ARGB4444 payload
when its recorded forward RGB gain and original alpha are packed. This catches
wrong source indices, palette variants, gains and stale packages before emission.
The original r101 wrapper table stores a float32 **inverse gain for vertex
colours**. Use the exact original forward texture gain from its conversion
manifest; inverting the rounded table value can cross a quantization boundary.

## Invocation and outputs

Use Python with numpy and Pillow. The Windows Python environment used for other
PS2 texture conversions is supported, including explicit WSL UNC paths.

```text
python -B port/dreamcast/tools/ps2_vegetation_candidate.py \
  <private-policy.json> <fresh-private-output-directory> \
  --room r101 --fixture-prefix <absolute-staging-host-output-path>
```

Select each requested room with another `--room`. The output directory must not
exist. All package and policy validation finishes before output creation.

Outputs are:

- `rooms/<room>/ps2-world.re4mesh`: byte-identical copy.
- `rooms/<room>/ps2-world.r4pw`: selected TR parts get new keys and PT tags.
- `rooms/<room>/ps2-world.ids`: only its sidecar identity CRC changes.
- `rooms/r100/interior.cell`, when selected: only its sidecar identity CRC changes.
- `textures/*.re4tex`: newly keyed native ARGB1555 packages.
- `tex.pak`: all baseline entries retained byte-for-byte plus new textures.
- `policy.json`, `proof.json`, and `fixture-replace.json`.

The fixture replacement file is a narrow overlay to merge into the exact
baseline fixture. It does not remove unrelated files or construct a disc.
Existing payload-key aliases are reused only if their dimensions, format,
flags and payload agree. Incompatible collisions are rejected.

A selected key also used by an opaque part leaves that opaque part and its
original key unchanged. Vertex-alpha marked parts are rejected. Therefore a
world's unique resident payload byte count may increase even though each new
texture has the same dimensions and 16-bit storage. The report gives these
offline world payload counts; they are not runtime heap or VRAM measurements.

## Geometry and r100 interior identity

The tool checks mesh size, CRC and counts. It proves that only selected R4PW
key words and pass bytes change, with exact placement bytes, unselected parts
and the opaque occluder set preserved. The actual new R4PW CRC32 is stored at
offset20 and copied to offset12 in R4ID and PCL1. No checksum collision is used.

The PCL1 file's subcells, portals, bounds and mesh identity stay byte-identical.
For r100, the parent build must select the report's `required_kPcSidecarUse`
under a default-off candidate knob. Its branch must take precedence over
`PS2_PT_CUTOUT`, while knob0 keeps the baseline checksum. Do not change
`ps2_interior_cell.inc`, disable culling, or alter cell geometry to admit a package.

Offline preservation is necessary but does not prove live culling. Require
`PCCULL cell file loaded` with the expected file size and a matched interior
view without a header or “not culling” failure.

## Room rollout and acceptance

Start with r101 and r100 separately, after their measured baselines. Maintain a
per-room evidence row for every currently shipped room in r100–r10b and
r117–r11b, then extend it when additional rooms ship. No automatic semantic
classification or global threshold is safe for the remaining rooms.

For each room, record the baseline fixture and package hashes, exact key/source
index/class decisions, rejected soft or ambiguous keys, chosen thresholds,
source/payload parity, new CRCs, geometry proof, before/after fill and polygons,
modelled costs, still paths and acceptance status. A room with no safe cutout
candidate still needs a coverage audit; zero candidates is not missing work.

Required before landing a candidate:

1. Matching scene, frame window, camera, enemy population, gameplay knobs,
   warp/pad files and decision evidence. Label the actual build and window.
2. Render-only STRICT under the existing exclusive trace lock.
3. TEX_CHECK, every PT header using SRCALPHA/INVSRCALPHA via MCHECK_PT,
   zero GC fallback, and measured heap4/VRAM. Include r100 culling checks.
4. Per-class mean/p99 TR polygons and fill from complete presented scenes,
   with unknown/overflow coverage retained. Keep effects, models and UI separate.
5. Modelled GPU/SH4 costs labelled as estimates; physical hardware evidence is
   a different gate.
6. Matched stills and closeups for the user's visual judgment. Alpha coverage
   and offline threshold sheets cannot accept edge quality or filtering.

Runtime knobs stay default0. Private assets and candidate packages stay local;
the parent runs combined gates and handles landing.

## Host checks

```text
python -B port/dreamcast/tests/test_ps2_vegetation_candidate.py
```

Synthetic fixtures check source/gain mismatch, bad hashes and CRCs, semantic
rejection, vertex-alpha rejection, unchanged opaque/shared-key parts, exact
placement and mesh preservation, true R4ID/PCL1 identity updates, immutable
baseline texture-pack entries and refusal to overwrite previous output.

## r100 candidate runtime identity

`PS2_PT_VARIANT_CRC=176921082` selects the genuine `0x0a8b99fa` R4PW/PCL1 identity for the reviewed per-material r100 candidate. It requires `PS2_PT_CUTOUT=1`; its default is zero, which retains the existing selection. Both the mesh/sidecar package check and the PCL1 header check still apply. This setting does not alter visibility cells or the culling algorithm. A baseline capture must use the baseline CRC selection and its matching original package; a candidate capture must use the candidate selection and its matching package. Never use a mismatched package to disable culling as a comparison control. The candidate remains pending runtime and visual gates.
