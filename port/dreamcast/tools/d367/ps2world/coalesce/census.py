#!/usr/bin/env python3
"""Read-only census of adjacent opaque parts with identical effective state.

This identifies candidates for a separate runtime review, not permission to
merge them. No package, fixture, source file or texture is modified.
"""
import argparse
import collections
import hashlib
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import packages as F


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True,
                        help='package names, spatial-first-mesh and protected placements; see README')
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    blob = (args.source / plan['active_mesh']).read_bytes()
    p = F.read(blob)
    h = F.HEADER.unpack_from(blob)
    sh, meta, places = F.side_read(args.source / plan['sidecar'], p)
    ids_blob = (args.source / plan['ids']).read_bytes()
    assert struct.unpack_from('<4s3I', ids_blob) == (b'R4ID', 1, sh[2], sh[5])
    ids = ids_blob[16:16 + sh[2]]
    assert len(ids) == len(places)
    first = plan['spatial_first_mesh']
    assert isinstance(first, int) and 0 <= first <= len(p['meshes'])
    gates = set(plan['protected_placements'])
    assert all(isinstance(i, int) and 0 <= i < sh[2] for i in gates)
    protected = {i for i, pl in enumerate(places)
                 if pl[1] <= 2 or pl[1] in gates or ids[pl[1]] < 250}
    protected_meshes = {places[i][0] for i in protected}
    uses = collections.defaultdict(list)
    for row, pl in enumerate(places):
        assert pl[0] < len(p['meshes']) and pl[1] < len(places)
        uses[pl[0]].append(row)

    def uv_bits(pi):
        start = h[11] + F.PART.size * pi + 20
        return blob[start:start + 16]

    def state(pi):
        # The PS2 keyed path uses R4PW material identity. MeshPart.texture is
        # the legacy source index; runtime callers must verify that contract.
        return tuple(meta[pi]), tuple(p['parts'][pi][3:6])

    def pool(pi):
        part = p['parts'][pi]
        lets = p['lets'][part[6]:part[6] + part[7]]
        assert len(lets) == part[7] and lets
        return [min(m[0] for m in lets),
                max(max(F.let_corners(p, m)[0]) + 1 for m in lets)]

    groups = set()
    exact_groups = set()
    parts = 0
    pairs = []
    for mi in range(first, len(p['meshes'])):
        m = p['meshes'][mi]
        for pi in range(m[6], m[6] + m[7]):
            part = p['parts'][pi]
            if not part[7] or meta[pi][4] != 0:
                continue
            parts += 1
            groups.add((mi, state(pi)))
            exact_groups.add((mi, state(pi), uv_bits(pi)))
            qi = pi + 1
            if qi >= m[6] + m[7] or mi in protected_meshes or not uses[mi]:
                continue
            other = p['parts'][qi]
            if not other[7] or state(pi) != state(qi) or uv_bits(pi) != uv_bits(qi):
                continue
            a, b = p['plods'][pi], p['plods'][qi]
            if not a[1] or not b[1] or part[6] + part[7] != other[6] or a[0] + a[1] != b[0]:
                continue
            pools = [pool(pi), pool(qi)]
            if pools[0][1] != pools[1][0]:
                continue
            rows = uses[mi]
            pairs.append(dict(mesh=mi, parts=[pi, qi], placements=rows,
                              placement_ids=[places[i][1] for i in rows],
                              object_ids=[ids[places[i][1]] for i in rows],
                              part_records_before=[part, other], part_lods_before=[a, b],
                              vertex_pools_before=pools, sidecar_record=meta[pi],
                              uv_bits=uv_bits(pi).hex()))
    result = dict(scope='Read-only asset-wide candidate census; runtime state and visibility require separate review.',
                  mesh_sha256=hashlib.sha256(blob).hexdigest(),
                  plan_sha256=hashlib.sha256(args.plan.read_bytes()).hexdigest(),
                  spatial_opaque_parts=parts, same_key_state_groups=len(groups),
                  same_key_state_uv_groups=len(exact_groups),
                  protected_placement_rows=sorted(protected), protected_meshes=sorted(protected_meshes),
                  pairs=pairs)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
