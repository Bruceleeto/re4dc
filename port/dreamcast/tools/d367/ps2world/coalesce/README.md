# Adjacent world-part diagnostics

These tools read prelit R4IM v3, R4PW and R4ID files. They do not convert assets
or alter a runtime. Python 3's standard library and the read-only sibling
`packages.py` are the only dependencies.

`census.py` identifies adjacent opaque part ranges with equal effective material
state and exact UV float bits, contiguous meshlet/cluster ranges and adjoining
vertex pools. `review_verify.py` checks a supplied source/candidate pair for
count-only coalescing, unchanged bytes and traversal state, protected mappings,
package bounds/CRCs, and active/fallback strip-group behavior.

```sh
python3 port/dreamcast/tools/d367/ps2world/coalesce/census.py \
  --source /path/to/source-assets --plan /path/to/private-plan.json
python3 port/dreamcast/tools/d367/ps2world/coalesce/review_verify.py \
  --source /path/to/source-assets --candidate /path/to/candidate-assets \
  --plan /path/to/private-plan.json
```

Both commands write JSON to stdout. Redirect it to a new report outside the
checkout. The caller-owned plan contains:

- `active_mesh`, `fallback_mesh`, `sidecar`, `ids`: package filenames relative to
  the supplied directories. The verifier checks both mesh files.
- `spatial_first_mesh`: the first appended batch mesh, used by the census.
- `protected_placements`: every additional gated or otherwise protected
  placement ID. Sky IDs 0 through 2 and dynamic IDs below 250 are also protected.
  Supply this list from the package's authoritative conversion/ownership data.
- `pairs`: selected `[mesh_index, first_part, second_part]` triples. The verifier
  requires nonoverlapping, adjacent pairs. The census can suggest overlapping
  alternatives; selection and runtime review remain the caller's responsibility.
- `strip_groups`: a mapping of group filenames to `active` or
  `padded_active_reserve`. The latter explicitly describes a padded allocation
  reserve carrying active-mesh identity; it must retain the source's rejection
  against the fallback mesh. No such exception is inferred automatically.

The effective-state comparison intentionally ignores the legacy
`MeshPart.texture` source index. Before using this result, verify that the exact
runtime binds by the R4PW texture key and that no per-part callback, PVS map,
cluster mask, UV animation or other owner depends on a boundary being removed.
All sidecar fields and the remaining part flags are compared. The verifier
checks source and candidate bytes independently of a converter; its host PASS
does not perform that runtime review.

Zero-count rows remain in the part table. A successful merge does not itself
remove parent-loop iterations or prove fewer runtime counters. Culling can
hide either range, so an asset-level pair count is not a measured bind count or
frame-time saving. Capture appearance and price the exact runtime separately.

The verifier uses Python assertions for binary invariants; run normal Python,
without `-O`. Keep plans, source arrays, textures and generated reports private.
