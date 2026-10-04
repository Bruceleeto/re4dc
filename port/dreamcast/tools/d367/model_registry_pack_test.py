#!/usr/bin/env python3
"""model_registry_pack_test.py <registry.re4nmr> <out dir> [--room 103]  (D367 generic native models, 2026-10-03)

Malformed-package test of the room registry package (NATIVE_MODEL_REGISTRY_PACK=1). Writes the generated package and
one variant per rule below into <out dir> (private: they hold converted meshes), builds model_registry_pack_test.cpp
(the target's own game/coarse_actor_registry_pack_check.inc on the host) and requires every variant to be refused
for the expected reason, and the original to pass. 'fixed' variants recompute every hash the change touches (the
geometry hash, the payload CRC32 / FNV-1a, the header CRC32), so the structural rule itself must refuse them.
Prints one line per case and exits 1 on any mismatch.
"""
import json, os, struct, subprocess, sys, zlib

HEADER, KINDS = 64, ('desc', 'ref', 'geom', 'blob', 'tex', 'parents', 'bind', 'fmodel', 'fpart', 'ftex', 'role', 'sblob')
HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.join(HERE, '..', '..', 'game')


def fnv(b):
    f = 2166136261
    for x in b:
        f = ((f ^ x) * 16777619) & 0xffffffff
    return f


class Pack:
    def __init__(self, data):
        self.b = bytearray(data)

    def u32(self, at):
        return struct.unpack_from('<I', self.b, at)[0]

    def put(self, at, v, fmt='<I'):
        struct.pack_into(fmt, self.b, at, v)

    def sec(self, kind):
        k = KINDS.index(kind); at = HEADER + 16 * k
        return dict(at=self.u32(at + 4), bytes=self.u32(at + 8), count=self.u32(at + 12), table=at)

    def rec(self, kind, i, size):
        return self.sec(kind)['at'] + i * size

    def regeom(self):
        """recompute every geometry record's hash over its five spans"""
        blob = self.sec('blob')['at']
        for g in range(self.sec('geom')['count']):
            r = self.rec('geom', g, 64)
            npos, nnrm, npal, _, sb, uvb = (self.u32(r + 4 * k) for k in range(6))
            spans = [(self.u32(r + 32), npos * 8), (self.u32(r + 36), nnrm * 8), (self.u32(r + 40), uvb), (self.u32(r + 44), sb),
                     (self.u32(r + 48), npal * 16)]
            data = b''.join(bytes(self.b[blob + a:blob + a + n]) for a, n in spans)
            self.put(r + 52, zlib.crc32(data) & 0xffffffff); self.put(r + 56, fnv(data))

    def fix(self):
        rest = bytes(self.b[HEADER:])
        self.put(36, zlib.crc32(rest) & 0xffffffff); self.put(40, fnv(rest))
        self.put(44, 0); self.put(44, zlib.crc32(bytes(self.b[:HEADER])) & 0xffffffff)
        return self


def cases(good):
    def m(fn, fixed=True, geom=False):
        p = Pack(good); r = fn(p)
        if r is not None:
            p = r
        if geom:
            p.regeom()
        return p.fix() if fixed else p
    blob_at = Pack(good).sec('blob')['at']
    C = []
    C.append(('good', 'none', Pack(good)))
    C.append(('truncated', 'header', Pack(good[:-32])))
    C.append(('magic', 'header', m(lambda p: p.put(0, 0x58585858), fixed=False)))
    C.append(('version-2', 'header', m(lambda p: p.put(8, 2))))
    C.append(('header-crc', 'hash', m(lambda p: p.put(44, p.u32(44) ^ 1), fixed=False)))
    C.append(('payload-bit', 'hash', m(lambda p: p.put(blob_at + 100, p.b[blob_at + 100] ^ 0x10, '<B'), fixed=False)))
    C.append(('wrong-room', 'room', m(lambda p: p.put(32, 0x106))))
    C.append(('oversize-skin', 'size', m(lambda p: p.put(28, 200000))))
    C.append(('skin-sum', 'size', m(lambda p: p.put(28, p.u32(28) + 8))))
    C.append(('section-misaligned', 'table', m(lambda p: p.put(p.sec('desc')['table'] + 4, p.sec('desc')['at'] + 4))))
    C.append(('section-kind', 'table', m(lambda p: p.put(p.sec('tex')['table'], 9))))
    C.append(('role-capacity', 'table', m(lambda p: (p.put(p.sec('role')['table'] + 12, 13), p.put(p.sec('role')['table'] + 8, 13 * 32)) and None)))
    C.append(('descriptor-appearance', 'descriptor', m(lambda p: p.put(p.rec('desc', 0, 48) + 16, 0x201))))
    C.append(('descriptor-name', 'descriptor', m(lambda p: p.b.__setitem__(slice(p.rec('desc', 0, 48), p.rec('desc', 0, 48) + 16), b'x' * 16))))
    C.append(('descriptor-sections', 'ref',  # its 2nd section's ref is cow-01's (source_info 0 != 1)
              m(lambda p: p.put(p.rec('desc', 0, 48) + 28, 2))))
    C.append(('ref-geometry', 'ref', m(lambda p: p.put(p.rec('ref', 0, 16), 31))))
    C.append(('ref-bones', 'ref', m(lambda p: p.put(p.rec('ref', 2, 16), 0))))  # chicken section -> cow geometry (27 bones)
    C.append(('geometry-span', 'geometry', m(lambda p: p.put(p.rec('geom', 0, 64) + 32, p.sec('blob')['bytes']))))
    C.append(('geometry-unaligned', 'geometry', m(lambda p: p.put(p.rec('geom', 0, 64) + 40, p.u32(p.rec('geom', 0, 64) + 40) + 4), geom=True)))
    C.append(('geometry-hash', 'hash', m(lambda p: p.put(p.rec('geom', 1, 64) + 52, p.u32(p.rec('geom', 1, 64) + 52) ^ 1))))
    C.append(('geometry-overlap', 'overlap', m(lambda p: p.put(p.rec('geom', 1, 64) + 40, p.u32(p.rec('geom', 0, 64) + 32)), geom=True)))
    C.append(('geometry-duplicate', 'duplicate', m(lambda p: p.b.__setitem__(slice(p.rec('geom', 1, 64), p.rec('geom', 1, 64) + 64),
                                                                              bytes(p.b[p.rec('geom', 0, 64):p.rec('geom', 0, 64) + 64])))))
    def weight_bone(p):
        r = p.rec('geom', 1, 64); w = p.sec('blob')['at'] + p.u32(r + 48)
        p.put(w, p.u32(r + 28), '<B')  # first weight's bone = the geometry's bone count
    C.append(('weight-bone', 'geometry', m(weight_bone, geom=True)))
    def weight_nan(p):
        r = p.rec('geom', 2, 64); w = p.sec('blob')['at'] + p.u32(r + 48)
        p.put(w + 4, 0x7fc00000)
    C.append(('weight-nan', 'geometry', m(weight_nan, geom=True)))
    C.append(('bind-nan', 'skeleton', m(lambda p: p.put(p.sec('bind')['at'] + 5 * 4, 0x7f800000))))
    C.append(('parents-order', 'skeleton', m(lambda p: p.put(p.sec('parents')['at'] + 1, 5, '<b'))))
    C.append(('parents-root', 'skeleton', m(lambda p: p.put(p.sec('parents')['at'], 0, '<b'))))
    C.append(('texture-duplicate', 'duplicate', m(lambda p: p.b.__setitem__(slice(p.rec('tex', 1, 16), p.rec('tex', 1, 16) + 8),
                                                                             bytes(p.b[p.rec('tex', 0, 16):p.rec('tex', 0, 16) + 8])))))
    C.append(('texture-size', 'texture', m(lambda p: p.put(p.rec('tex', 0, 16) + 8, 300))))
    C.append(('fact-part-pad', 'facts', m(lambda p: p.put(p.rec('fpart', 0, 32) + 13, 1, '<B'))))
    C.append(('fact-part-count', 'facts', m(lambda p: p.put(p.rec('fmodel', 0, 96) + 92, 2))))
    C.append(('role-duplicate', 'duplicate', m(lambda p: p.b.__setitem__(slice(p.rec('role', 1, 32), p.rec('role', 1, 32) + 32),
                                                                          bytes(p.b[p.rec('role', 0, 32):p.rec('role', 0, 32) + 32])))))
    C.append(('role-range', 'role', m(lambda p: p.put(p.rec('role', 0, 32) + 4, 1))))
    C.append(('role-binding', 'binding', m(lambda p: p.put(p.rec('role', 0, 32) + 8, 99))))
    def ambiguous(p):  # cow-01's row proves cow-00's TPL and texture facts: two descriptors, one source identity
        a, b = p.rec('role', 0, 32), p.rec('role', 1, 32)
        for off in (12, 20, 24):
            p.put(b + off, p.u32(a + off))
    C.append(('identity-ambiguous', 'duplicate', m(ambiguous)))
    C.append(('blob-family', 'blob', m(lambda p: p.put(p.rec('sblob', 0, 32) + 4, 1))))
    C.append(('blob-bin', 'binding', m(lambda p: p.put(p.rec('sblob', 0, 32) + 8, 77))))
    return C


def main():
    args = sys.argv[1:]
    room = '103'
    if '--room' in args:
        i = args.index('--room'); room = args[i + 1]; del args[i:i + 2]
    if len(args) != 2:
        sys.exit(__doc__)
    src, out = args
    if os.path.exists(out):
        sys.exit(f'{out} exists')
    os.makedirs(out)
    good = open(src, 'rb').read()
    # the target's record types, extracted (not restated)
    mat = open(os.path.join(GAME, 'coarse_actor_material.inc')).read()
    reg = open(os.path.join(GAME, 'coarse_actor_owner_registry.inc')).read()
    a, b = mat.index('struct Digest'), mat.index('struct SourceBlob'); b = mat.index('\n', b) + 1
    c = reg.index('namespace nmr {'); d = reg.index('constexpr unsigned kRegDescriptors=16'); d = reg.index('\n', d) + 1
    types = ('#pragma once\n#include <cstdint>\nnamespace re4dc_material {\n' + mat[a:b] + '#include "actor_material_records.inc"\n}\n'
             + reg[c:d])
    open(os.path.join(out, 'pack_test_types.h'), 'w').write(types)
    exe = os.path.join(out, 'model_registry_pack_test')
    cc = ['g++', '-std=c++17', '-O1', '-Wall', '-Wno-unused-function', '-Wno-unused-variable', '-I', out, '-I', GAME,
          os.path.join(HERE, 'model_registry_pack_test.cpp'), '-o', exe]
    r = subprocess.run(cc, capture_output=True, text=True)
    if r.returncode:
        sys.exit('build failed:\n' + r.stderr[-4000:])
    files, want = [], {}
    for name, why, p in cases(good):
        f = os.path.join(out, name + '.re4nmr'); open(f, 'wb').write(bytes(p.b)); files.append(f); want[f] = (name, why)
    r = subprocess.run([exe, room] + files, capture_output=True, text=True)
    bad, rows = 0, []
    for line in r.stdout.splitlines():
        f, why, detail = line.rsplit(' ', 2)
        name, exp = want[f]
        ok = why == exp
        bad += not ok
        rows.append(dict(case=name, expected=exp, got=why, detail=int(detail), ok=ok))
        print(f'{"PASS" if ok else "FAIL"} {name:24s} expected={exp:10s} got={why} detail={detail}')
    if len(rows) != len(files):
        bad += 1; print(f'FAIL {len(files)} cases, {len(rows)} results')
    json.dump(dict(package=src, room=room, cases=rows, failures=bad), open(os.path.join(out, 'results.json'), 'w'), indent=1)
    print(f'{len(rows) - bad}/{len(files)} as expected')
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
