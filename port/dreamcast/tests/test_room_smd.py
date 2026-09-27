"""Any-room scenery (D367 W9): room SMD extraction, convert_room_bins.py --smd,
the release contract (tools/room_smd.py) and the runtime's released-BIN
identity (room/instanced_mesh.hpp source_part). Synthetic by default; the
r101/r103 cases run when the private route files are present
(RE4DC_ROUTE_DAS_DIR, default the frontier mirror's iso-src/st1)."""
import importlib.util
import json
import os
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
spec = importlib.util.spec_from_file_location('room_bins_v1_tests_smd', pathlib.Path(__file__).with_name('test_room_bins.py'))
T = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = T
spec.loader.exec_module(T)
C = T.C
import room_smd as R  # noqa: E402

ROUTE = pathlib.Path(os.environ.get('RE4DC_ROUTE_DAS_DIR', '/root/probe/d367-agents/frontier/iso-src/st1'))


def aligned_fixture(scale_pos=0.0):
    """test_room_bins.fixture with its part block 32-byte aligned (as every
    real BIN: trans.cpp halts on an unaligned stream)."""
    body = T.fixture()
    part_off = struct.unpack_from('>I', body, 0x1C)[0]
    pad = (-part_off) % 32
    data = T.fixture(pad=pad)
    if scale_pos:
        data = bytearray(data)
        struct.pack_into('>h', data, 0x48, int(scale_pos))  # move vertex 0: a different box
        data = bytes(data)
    return data


def synth_smd(bins, placements, tpl=b'TPL-TABLE-BYTES!' * 4, fcv=b'FCV-TABLE-BYTES!' * 2):
    """Big-endian SMD: works [(bin, pos, rot, scale, flags)], BIN table + bodies, TPL and FCV tables."""
    work = 0x10
    table = work + 72 * len(placements)
    table = (table + 31) & ~31
    body_at = (table + 4 * len(bins) + 31) & ~31
    offs, blob = [], bytearray()
    for b in bins:
        offs.append(body_at + len(blob) - table)
        blob += b + bytes((-len(b)) % 32)
    tpl_at = body_at + len(blob)
    fcv_at = tpl_at + len(tpl)
    out = bytearray(fcv_at + len(fcv))
    out[0] = 0x40
    struct.pack_into('>H', out, 2, len(placements))
    struct.pack_into('>3I', out, 4, table, tpl_at, fcv_at)
    for i, (b, pos, rot, scale, flags) in enumerate(placements):
        p = work + 72 * i
        struct.pack_into('>9f', out, p, *pos, *rot, *scale)
        out[p + 36:p + 40] = bytes((b, 0, 0xFF, i))
        struct.pack_into('>I', out, p + 0x44, flags)
    for i, o in enumerate(offs):
        struct.pack_into('>I', out, table + 4 * i, o)
    out[body_at:body_at + len(blob)] = blob
    out[tpl_at:tpl_at + len(tpl)] = tpl
    out[fcv_at:fcv_at + len(fcv)] = fcv
    return bytes(out)


def tagged(subfiles):
    """Big-endian tagged archive [(tag, bytes)]."""
    n = len(subfiles)
    at = (0x10 + 8 * n + 31) & ~31
    offs, blob = [], bytearray()
    for _, data in subfiles:
        offs.append(at + len(blob))
        blob += data + bytes((-len(data)) % 32)
    head = bytearray(at)
    struct.pack_into('>I', head, 0, n)
    for i, (tag, _) in enumerate(subfiles):
        struct.pack_into('>I', head, 0x10 + 4 * i, offs[i])
        head[0x10 + 4 * n + 4 * i:0x14 + 4 * n + 4 * i] = tag
    return bytes(head + blob)


class RoomSmdTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = pathlib.Path(cls.temp.name)
        cls.bins = [aligned_fixture(), aligned_fixture(scale_pos=-640)]
        cls.smd = synth_smd(cls.bins, [(0, (0, 0, 0), (0, 0, 0), (1, 1, 1), 0),
                                       (1, (100, 0, 5), (0, 1.5, 0), (2.5, 2.5, 2.5), 0),
                                       (0, (7, 8, 9), (0, 0, 0), (-3, 3, 3), 0),
                                       (1, (0, 0, 0), (0, 0, 0), (1, 1, 1), 0x10)])   # common: not local
        cls.arc = tagged([(b'SAT\0', b'collision' * 7), (b'SMD\0', cls.smd), (b'EFF\0', b'effects' * 9)])
        (cls.root / 'room.arc').write_bytes(cls.arc)
        (cls.root / 'kos').mkdir()
        (cls.root / 'kos/fs.h').write_text('#pragma once\n#include <sys/types.h>\nusing file_t=int;\n'
                                           '#define FILEHND_INVALID (-1)\n')
        (cls.root / 'part.cpp').write_text(r'''
#include "instanced_mesh.hpp"
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <vector>
#include <cstring>
int main(int argc,char** argv){
    std::ifstream in(argv[1],std::ios::binary);
    std::vector<unsigned char> raw((std::istreambuf_iterator<char>(in)),{});
    std::vector<std::uint32_t> words((raw.size()+3)/4);std::memcpy(words.data(),raw.data(),raw.size());
    re4dc::room::MeshPackage p;
    if(!p.adopt(reinterpret_cast<const std::uint8_t*>(words.data()),std::uint32_t(raw.size()),true)){std::printf("reject\n");return 1;}
    for(int i=2;i+4<argc;i+=5){
        const unsigned m=unsigned(std::atoi(argv[i]));
        const auto* part=p.source_part(m,unsigned(std::atoi(argv[i+1])),unsigned(std::atoi(argv[i+2])),
                                       std::uint32_t(std::atoi(argv[i+3])),std::uint32_t(std::atoi(argv[i+4])));
        if(part)std::printf("%d ",int(part-(p.parts()+p.meshes()[m].first_part)));else std::printf("none ");
    }
    std::printf("\n");return 0;
}
''')
        cls.exe = cls.root / 'part'
        subprocess.run(['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror', '-I', str(cls.root),
                        '-I', str(ROOT / 'room'), str(cls.root / 'part.cpp'), '-o', str(cls.exe)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_smd_reads_local_bins_placements_and_scales(self):
        smd, e = R.load_smd(self.root / 'room.arc')
        self.assertEqual((smd, e), (self.smd, '>'))
        s = R.Smd(smd, e)
        self.assertEqual(s.local_bins(), [0, 1])
        self.assertEqual([p['common'] for p in s.used()], [False, False, False, True])
        got = s.bins()
        for i, b in enumerate(self.bins):
            self.assertEqual(got[i][:len(b)], b)
        self.assertEqual(s.scales(), {'255:0': 3.0, '255:1': 2.5})

    def test_smd_conversion_lists_every_part_for_release(self):
        room = C.smd_entries(self.root / 'room.arc', 0xFF)
        self.assertEqual([e[2] for e in room['entries']], [0, 1])
        self.assertEqual(room['scales'], {0: 3.0, 1: 2.5})
        blob, summary = C.convert_lod(room['entries'], 1.0, {(0xFF, b): s for b, s in room['scales'].items()},
                                      eps_world=(0.05, 0.5), cluster_world=1000.0)
        rel = C.release_identities(room['entries'], summary)
        self.assertEqual([r['bin'] for r in rel], [0, 1])
        for r, data in zip(rel, self.bins):
            src = C.parse_bin(data)
            self.assertEqual(r['parts'], len(src['parts']))
            self.assertEqual(r['part_offsets'], [p['offset'] for p in src['parts']])
            self.assertEqual(r['part_sizes'], [p['size'] for p in src['parts']])
            self.assertEqual(r['vertices'], src['nvtx'])
            self.assertLess(r['resident_bytes'], r['source_bytes'])
        (self.root / 'pkg.re4mesh').write_bytes(blob)
        # The runtime matches source and released identities to the same part.
        m = 0
        offs, sizes, nv = rel[0]['part_offsets'], rel[0]['part_sizes'], rel[0]['vertices']
        args = []
        for k in range(len(offs)):
            args += [m, nv, len(offs), offs[k], sizes[k]]          # source layout
            args += [m, R.RELEASED_VERTICES, len(offs), 32 * k, 0]  # released
        args += [m, R.RELEASED_VERTICES, len(offs), 32, 4]          # released must have no stream
        args += [m, R.RELEASED_VERTICES, len(offs) + 1, 0, 0]       # part count is identity
        args += [m, nv, len(offs), 32, 0]                           # source layout, wrong offset
        args += [m, R.RELEASED_VERTICES, len(offs), 32 * len(offs), 0]
        out = subprocess.run([str(self.exe), str(self.root / 'pkg.re4mesh')] + [str(a) for a in args],
                             text=True, capture_output=True, check=True).stdout.split()
        want = [str(k) for k in range(len(offs)) for _ in (0, 1)] + ['none'] * 4
        self.assertEqual(out, want)

    def test_release_keeps_what_the_game_reads(self):
        release = {0: dict(vertices=C.parse_bin(self.bins[0])['nvtx']), 1: {}}
        new, report = R.release_archive(self.arc, release)
        self.assertEqual(report['saved'], len(self.arc) - len(new))
        self.assertEqual(report['saved'] % 32, 0)
        a, b = R.tagged_entries(self.arc, '>'), R.tagged_entries(new, '>')
        for (ta, sa, xa), (tb, sb, xb) in zip(a, b):
            self.assertEqual(ta, tb)
            if ta != b'SMD\0':
                self.assertEqual(self.arc[sa:xa], new[sb:xb])
        old, smd = self.arc[a[1][1]:a[1][2]], new[b[1][1]:b[1][2]]
        s0, s1 = R.Smd(old), R.Smd(smd)
        self.assertEqual(s0.placements, s1.placements)
        self.assertEqual(s0.tables[1] - s1.tables[1], report['saved'])  # TPL / FCV move with the region
        self.assertEqual(old[s0.tables[1]:], smd[s1.tables[1]:])
        self.assertEqual((old[:4], old[0x10:s0.tables[0]]), (smd[:4], smd[0x10:s1.tables[0]]))
        self.assertEqual(s0.tables[0], s1.tables[0])
        for i, src in s0.bins().items():
            stub = s1.bins()[i]
            self.assertEqual(R.released_bounds(src, '>'), R.released_bounds(stub, '>'))
            la, lb = R.bin_layout(src, '>'), R.bin_layout(stub, '>')
            self.assertEqual((lb['nv'], lb['nn'], lb['nd']), (R.RELEASED_VERTICES, 1, la['nd']))
            self.assertEqual(R.part_headers(stub, '>', lb), [(32 * k, 0) for k in range(la['nd'])])
            self.assertEqual(lb['ptr']['parts'] % 32, 0)
            self.assertEqual(src[la['ptr']['clr']:la['ptr']['tex']], stub[lb['ptr']['clr']:lb['ptr']['tex']])
            for k in range(la['nd']):   # part headers keep texture, flags, alpha
                ha = src[la['ptr']['parts'] + R.part_headers(src, '>', la)[k][0]:][:0x18]
                hb = stub[lb['ptr']['parts'] + 32 * k:][:0x18]
                self.assertEqual(ha, hb)
            self.assertEqual(src[0x20:0x2C], stub[0x20:0x2C])

    def test_release_rebases_the_compact_room_texture_index(self):
        import zlib
        head = tagged([(b'SAT\0', b'collision' * 7), (b'SMD\0', self.smd), (b'EFF\0', b'effects' * 9),
                       (b'NTR\0', bytes(64))])
        ents = R.tagged_entries(head, '>')
        smd_at, eff_at, ntr_at = ents[1][1], ents[2][1], ents[3][1]
        tpl_at = smd_at + R.Smd(self.smd).tables[1]
        records = [eff_at + 32, eff_at, tpl_at, 0x40, eff_at + 4, tpl_at + 8]  # 2 records: payload, header, tpl
        table = struct.pack('>6I', *records)
        arc = bytearray(head)
        struct.pack_into('>8s6I', arc, ntr_at, b'R4NTBL\0\0', 1, 2, 12, zlib.crc32(table), 1 << 24, len(arc))
        arc[ntr_at + 32:ntr_at + 56] = table
        new, report = R.release_archive(bytes(arc), {0: {}, 1: {}})
        at = R.tagged_entries(new, '>')[3][1]
        magic, version, count, stride, crc, original, resident = struct.unpack_from('>8s6I', new, at)
        got = struct.unpack_from('>6I', new, at + 32)
        d = report['saved']
        self.assertEqual((magic, count, original, resident), (b'R4NTBL\0\0', 2, 1 << 24, len(new)))
        self.assertEqual(list(got), [eff_at + 32 - d, eff_at - d, tpl_at - d, 0x40, eff_at + 4 - d, tpl_at + 8 - d])
        self.assertEqual(crc, zlib.crc32(new[at + 32:at + 56]))
        self.assertEqual(new[got[1]:got[1] + 16], arc[eff_at:eff_at + 16])
        self.assertEqual(new[got[2]:got[2] + 16], arc[tpl_at:tpl_at + 16])
        bad = bytearray(arc)
        struct.pack_into('>I', bad, ntr_at + 32, smd_at + R.Smd(self.smd).bin_table()[1][0] + 8)
        with self.assertRaises(ValueError):
            R.release_archive(bytes(bad), {0: {}, 1: {}})

    def test_release_refuses_a_package_of_another_bin(self):
        with self.assertRaises(ValueError):
            R.release_archive(self.arc, {0: dict(vertices=3)})
        with self.assertRaises(ValueError):
            R.release_archive(self.arc, {1: dict(part_sizes=[0, 0])})

    def test_package_identities_are_the_converter_release_list(self):
        room = C.smd_entries(self.root / 'room.arc', 0xFF)
        blob, summary = C.convert_lod(room['entries'], 1.0, {(0xFF, b): s for b, s in room['scales'].items()},
                                      eps_world=(0.05, 0.5), cluster_world=1000.0)
        rel = {r['bin']: {k: r[k] for k in R.IDENTITY_KEYS} for r in C.release_identities(room['entries'], summary)}
        got = R.package_identities(blob)
        self.assertEqual({b: {k: v[k] for k in R.IDENTITY_KEYS} for b, v in got.items()}, rel)
        self.assertEqual(R.package_identities(blob, common=True), {})
        with self.assertRaises(ValueError):
            R.package_identities(blob[:-4])
        # Summary and package agree; a package of other BINs releases nothing.
        (self.root / 'ident.re4mesh').write_bytes(blob)
        (self.root / 'ident.json').write_text(json.dumps(dict(release=C.release_identities(room['entries'], summary))))
        both, skipped = R.load_identities([self.root / 'ident.re4mesh', self.root / 'ident.json'])
        self.assertEqual((sorted(both), skipped), ([0, 1], {}))
        other = json.loads((self.root / 'ident.json').read_text())
        other['release'][1]['part_sizes'] = [z + 4 for z in other['release'][1]['part_sizes']]
        del other['release'][0]
        (self.root / 'other.json').write_text(json.dumps(other))
        both, skipped = R.load_identities([self.root / 'ident.re4mesh', self.root / 'other.json'])
        self.assertEqual((both, skipped), ({}, {0: 'not in every identity source', 1: 'identity sources disagree'}))

    def indexed_room(self):
        """Room archive with a main and a common SMD and both prepared indexes
        (NTR texture identities, ESQ effect sequences) after them."""
        import zlib
        common = synth_smd(list(reversed(self.bins)), [(0, (0, 0, 0), (0, 0, 0), (1, 1, 1), 0),
                                                       (1, (5, 5, 5), (0, 0, 0), (1, 1, 1), 0)],
                           tpl=b'COMMON-TPLTABLE!' * 4)
        effects = bytes(range(256)) * 2
        head = tagged([(b'SAT\0', b'collision' * 7), (b'SMD\0', self.smd), (b'SMD\0', common),
                       (b'EFF\0', effects), (b'ESQ\0', bytes(64)), (b'NTR\0', bytes(64))])
        ents = R.tagged_entries(head, '>')
        eff_at, esq_at, ntr_at = ents[3][1], ents[4][1], ents[5][1]
        tpl_at = ents[2][1] + R.Smd(common).tables[1]
        arc = bytearray(head)
        seqs = struct.pack('>6I', eff_at, 64, 2, eff_at + 128, 96, 3)
        struct.pack_into('>8s6I', arc, esq_at, b'R4ESQTBL', 1, 2, 12, zlib.crc32(seqs), len(arc), 0)
        arc[esq_at + 32:esq_at + 56] = seqs
        recs = struct.pack('>3I', eff_at + 256, tpl_at + 4, tpl_at)
        struct.pack_into('>8s6I', arc, ntr_at, b'R4NTBL\0\0', 1, 1, 12, zlib.crc32(recs), 1 << 24, len(arc))
        arc[ntr_at + 32:ntr_at + 44] = recs
        return bytes(arc), common

    def test_release_of_a_room_with_a_common_smd_and_indexes(self):
        import zlib
        arc, common = self.indexed_room()
        with self.assertRaises(ValueError):
            R.release_archive(arc, {0: {}, 1: {}})   # two SMDs: one map each
        new, report = R.release_archive(arc, [{0: {}, 1: {}}, {0: {}, 1: {}}])
        check = R.diff_release(arc, new)
        self.assertEqual((check['released_bins'], check['kept_bins']), (4, 0))
        self.assertEqual(report['saved'], len(arc) - len(new))
        self.assertEqual([r['entry'] for r in report['smds']], [1, 2])
        ents_a, ents_b = R.tagged_entries(arc, '>'), R.tagged_entries(new, '>')
        for (ta, sa, xa), (tb, sb, xb) in zip(ents_a, ents_b):
            if ta in (b'SAT\0', b'EFF\0'):
                self.assertEqual(arc[sa:xa], new[sb:xb])
        d1 = report['smds'][0]['saved']
        d = report['saved']
        eff_a, eff_b = ents_a[3][1], ents_b[3][1]
        self.assertEqual(eff_a - eff_b, d)
        esq = ents_b[4][1]
        magic, version, count, stride, crc, size, zero = struct.unpack_from('>8s6I', new, esq)
        self.assertEqual((magic, count, size, zero), (b'R4ESQTBL', 2, len(new), 0))
        self.assertEqual(struct.unpack_from('>6I', new, esq + 32), (eff_b, 64, 2, eff_b + 128, 96, 3))
        self.assertEqual(crc, zlib.crc32(new[esq + 32:esq + 56]))
        ntr = ents_b[5][1]
        tpl_b = ents_b[2][1] + R.Smd(new[ents_b[2][1]:ents_b[2][2]], '>').tables[1]
        self.assertEqual(struct.unpack_from('>3I', new, ntr + 32), (eff_b + 256, tpl_b + 4, tpl_b))
        self.assertEqual(new[tpl_b:tpl_b + 16], arc[ents_a[2][1] + R.Smd(common).tables[1]:][:16])
        self.assertGreater(d, d1)                      # both SMDs gave bytes
        # The common SMD kept: only the main SMD's bytes, the indexes still valid.
        kept, rep2 = R.release_archive(arc, [{0: {}, 1: {}}, None])
        self.assertEqual(R.diff_release(arc, kept)['released_bins'], 2)
        self.assertEqual(rep2['saved'], d1)
        self.assertTrue(rep2['smds'][1]['kept'])
        # An ESQ sequence inside a released BIN region, or an ESQ of another archive size: refused.
        bad = bytearray(arc)
        struct.pack_into('>I', bad, ents_a[4][1] + 32, ents_a[1][1] + R.Smd(self.smd).bin_table()[1][0] + 32)
        with self.assertRaises(ValueError):
            R.release_archive(bytes(bad), [{0: {}}, None])
        bad = bytearray(arc)
        struct.pack_into('>I', bad, ents_a[4][1] + 24, len(arc) + 32)
        with self.assertRaises(ValueError):
            R.release_archive(bytes(bad), [{0: {}}, None])

    def test_check_refuses_anything_but_the_release(self):
        arc, _ = self.indexed_room()
        new, _ = R.release_archive(arc, [{0: {}, 1: {}}, {1: {}}])
        R.diff_release(arc, new)
        ents = R.tagged_entries(new, '>')
        smd_at = ents[1][1]
        stub_at = smd_at + R.Smd(new[smd_at:ents[1][2]], '>').bin_table()[1][0]
        for where in (ents[3][1] + 5,           # effects
                      ents[0][1] + 1,           # collision
                      stub_at + 0x40,           # a released BIN's kept header / joint head
                      ents[2][2] - 8,           # the common SMD's FCV table
                      ents[5][1] + 32):         # an NTR record
            bad = bytearray(new)
            bad[where] ^= 1
            with self.assertRaises(ValueError, msg=hex(where)):
                R.diff_release(arc, bytes(bad))

    def test_release_refuses_an_unplaced_bin_in_the_table(self):
        # Three table entries, two placed BINs: the third body would be swallowed.
        smd = bytearray(synth_smd(self.bins + [self.bins[0]], [(0, (0, 0, 0), (0, 0, 0), (1, 1, 1), 0),
                                                               (1, (0, 0, 0), (0, 0, 0), (1, 1, 1), 0)]))
        with self.assertRaises(ValueError):
            R.release_smd(bytes(smd), '>', {1: {}})

    def test_render_unqualified_bins_keep_the_gx_path(self):
        multi = bytearray(self.bins[0])
        multi[0x19] = 2
        self.assertEqual(R.releasable(bytes(multi), '>'), 'multi-node')
        shape = bytearray(self.bins[0])
        struct.pack_into('>I', shape, 0x2C, 0x48)
        self.assertEqual(R.releasable(bytes(shape), '>'), 'shape')
        arc = tagged([(b'SMD\0', synth_smd([bytes(multi), self.bins[1]], [(0, (0, 0, 0), (0, 0, 0), (1, 1, 1), 0),
                                                                          (1, (0, 0, 0), (0, 0, 0), (1, 1, 1), 0)]))])
        (self.root / 'multi.arc').write_bytes(arc)
        room = C.smd_entries(self.root / 'multi.arc', 0xFF)
        self.assertEqual(([e[2] for e in room['entries']], room['kept']), ([1], {0: 'multi-node'}))


@unittest.skipUnless((ROUTE / 'r101.das').is_file() and (ROUTE / 'r103.das').is_file(), 'private route rooms absent')
class RouteRoomTests(unittest.TestCase):
    """r101 / r103 (private data): every local BIN converts and may be released."""
    def check(self, room, bins, bin_bytes):
        smd, e = R.load_smd(ROUTE / (room + '.das'))
        s = R.Smd(smd, e)
        got = s.bins()
        self.assertEqual((len(got), sum(len(b) for b in got.values())), (bins, bin_bytes))
        self.assertFalse([p for p in s.used() if p['common']])
        self.assertEqual({i: R.releasable(b, e) for i, b in got.items() if R.releasable(b, e)}, {})
        stubs = sum(len(R.release_bin(b, e)) for b in got.values())
        self.assertLess(stubs, bin_bytes // 40)
        for b in got.values():
            self.assertEqual(R.released_bounds(b, e), R.released_bounds(R.release_bin(b, e), e))

    def test_r101(self):
        self.check('r101', 81, 1623008)

    def test_r103(self):
        self.check('r103', 119, 1591040)


R100 = pathlib.Path(os.environ.get('RE4DC_R100_MIRROR', '/root/probe/d367-agents/frontier/mirror-w4q/st1'))
PACKAGES = pathlib.Path(os.environ.get('RE4DC_R100_PACKAGES', '/root/probe/d367-agents/assets/out'))


@unittest.skipUnless((R100 / 'r100.dar').is_file() and (R100 / 'r100_04.dat').is_file() and
                     (PACKAGES / 'standard/r100/low/COMMON.re4mesh').is_file(), 'private r100 files absent')
class R100ReleaseTests(unittest.TestCase):
    """r100 (private data): the scroll block files and the room archive release
    every BIN against both the Original and the Standard package of its owner
    (either may be opened at run time)."""
    def identities(self, owner, common=False):
        return R.load_identities([PACKAGES / 'original/r100/mesh' / (owner + '.re4mesh'),
                                  PACKAGES / 'standard/r100/low' / (owner + '.re4mesh')], common)

    def test_block_files_shrink_the_block_pool(self):
        sizes = []
        for n in range(5):
            src = (R100 / ('r100_%02d.dat' % n)).read_bytes()
            release, skipped = self.identities('FILE_%02d' % n)
            new, _ = R.release_container(src, release)
            check = R.diff_release(src, new)
            self.assertEqual((skipped, check['kept_bins']), ({}, 0))
            sizes.append((len(src), len(new)))
        # block.cpp checkBlockMemory: the largest sum over the BLK connection sets.
        sets = ([0, 1, 2], [1, 2, 3], [2, 3, 4], [3, 4])
        self.assertEqual([max(sum(sizes[i][k] for i in s) for s in sets) for k in (0, 1)], [1126272, 39808])

    def test_room_archive_releases_main_and_common(self):
        src = (R100 / 'r100.dar').read_bytes()
        own, skipped = self.identities('MAINSCENARIO')
        common, skipped_common = self.identities('COMMON', True)
        new, _ = R.release_container(src, [own, common])
        check = R.diff_release(src, new)
        self.assertEqual((skipped, skipped_common, check['released_bins'], check['kept_bins'], check['saved']),
                         ({}, {}, 31, 0, 696640))


if __name__ == '__main__':
    unittest.main()
