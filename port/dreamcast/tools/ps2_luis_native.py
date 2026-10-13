#!/usr/bin/env python3
"""Host-check sparse source-info chunks without renumbering their GC identities.

The external fastpath tools consume contiguous disk filenames. This adapter
uses a fresh ordinal-only scratch view, verifies every chunk, and restores the
original source-info filenames before patching the runtime header. The source
header, fixture, mesh, coverage manifest, and source bindings stay unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def run(command, log):
    with log.open('w') as stream:
        subprocess.run(command, stdout=stream, stderr=subprocess.STDOUT, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('model', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--host-check', type=Path, required=True)
    parser.add_argument('--private', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('choose a fresh output directory')
    native = args.model/'native'
    report = json.loads((native/'native-report.json').read_text())
    coverage = json.loads((args.model/'coverage-manifest.json').read_text())
    roles = [c['info'] for c in report['chunks']]
    if roles != [r['role'] for r in coverage['coverage']] or len(set(roles)) != len(roles):
        raise ValueError('native chunk roles differ from source coverage')
    args.output.mkdir(parents=True)
    flat, fitted, remapped, runtime = [args.output/x for x in ('ordinal-source', 'ordinal-fitted', 'source-info-fitted', 'runtime')]
    for d in (flat, fitted, remapped, runtime):
        d.mkdir()
    shutil.copyfile(native/'host-fixture.bin', flat/'host-fixture.bin')
    identity = []
    for ordinal, role in enumerate(roles):
        item = dict(ordinal=ordinal, source_info=role, arrays={})
        for suffix in ('pos', 'nrm', 'uv', 'gx'):
            source = native/f'info{role}.{suffix}'
            data = source.read_bytes()
            (flat/f'info{ordinal}.{suffix}').write_bytes(data)
            item['arrays'][suffix] = hashlib.sha256(data).hexdigest()
        identity.append(item)
    fast = args.private/'character-prototype-20260925/tools/fastpath'
    run([str(args.host_check), str(flat)], args.output/'host-check.log')
    run([sys.executable, str(fast/'build_blob.py'), str(flat), str(fitted), '--report', str(args.output/'fit-report.json'), '--look', '8'], args.output/'fit.log')
    run([sys.executable, str(fast/'verify_blob.py'), str(flat), str(fitted)], args.output/'verify.log')
    for ordinal, role in enumerate(roles):
        shutil.copyfile(fitted/f'info{ordinal}.meshlets', remapped/f'info{role}.meshlets')
    header = runtime/'castmodel_runtime.h'
    run([sys.executable, str(fast/'patch_header.py'), str(native/'castmodel_native.h'), str(remapped), str(header)], args.output/'header.log')
    proof = dict(schema='ps2-mapped-native-host-proof-1', source_coverage_sha256=hashlib.sha256((args.model/'coverage-manifest.json').read_bytes()).hexdigest(),
                 source_header_sha256=hashlib.sha256((native/'castmodel_native.h').read_bytes()).hexdigest(),
                 runtime_header_sha256=hashlib.sha256(header.read_bytes()).hexdigest(), source_info_ordinals=identity,
                 host_check_sha256=hashlib.sha256(args.host_check.read_bytes()).hexdigest(),
                 source_triangles=coverage['nondegenerate_triangles'], verified_triangles=json.loads((args.output/'fit-report.json').read_text())['total']['triangles'],
                 target_admission=False, original_animation_review=False)
    if proof['source_triangles'] != proof['verified_triangles']:
        raise ValueError('fitted output did not cover every source triangle')
    (args.output/'native-proof.json').write_text(json.dumps(proof, indent=2))
    print((args.output/'host-check.log').read_text().strip())
    print((args.output/'verify.log').read_text().strip())
    print('Source-info roles restored:', roles)
    print('Header:', header)


if __name__ == '__main__':
    main()
