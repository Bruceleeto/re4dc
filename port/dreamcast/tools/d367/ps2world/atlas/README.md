# World texture and material census

`census.py` reads a prelit R4IM v3 mesh, its R4PW sidecar, and a fixture's
`replace` mapping. It reports texture formats and payload sizes, used VQ vector
unions, effective material groups, and UV repeat bounds. It only writes JSON to
the supplied output directory. Game assets and fixture files remain inputs.

```sh
python3 port/dreamcast/tools/d367/ps2world/atlas/census.py \
  --mesh /path/to/world.re4mesh --sidecar /path/to/world.r4pw \
  --fixture /path/to/fixture.json --spatial-first-mesh 120 \
  --out /path/to/new/census
```

Set `--spatial-first-mesh` to the actual first appended batch mesh from that
package's conversion metadata. If no meshes were appended, use its mesh count.
This is an explicit input, not an inferred room convention. An optional
`--expect-mesh-sha256` pins the package before analysis. The fixture must name
`dc/tex.pak` and any separately supplied `dc/tex/...re4tex` packages. Relative
fixture paths resolve against the fixture directory.

The parser is the read-only sibling `packages.py`; Python 3's standard library
is the only dependency. No converter, emulator, timing model or original game
source tree is needed to run the census on already converted packages.

The report is asset-wide and includes every referenced LOD. It does not say how
many parts a particular camera draws, whether a texture is currently resident,
or how much free VRAM exists. Texture payload totals exclude runtime allocation
overhead and other owners.

The finite repeat rectangle includes a one-texel bilinear gutter on every side.
It is a conservative size estimate across disconnected UV islands, not a packed
atlas minimum. Existing source textures repeat in the keyed PS2 path; preserving
that sampling requires a separate gutter/repeat design. At most 256 distinct
used VQ vectors is a codebook capacity condition, not proof that an atlas fits
or that remapped UVs render identically. Pixel, state, lifetime and performance
qualification remain separate.
