"""Scenery adopt by colour encoding (game30.mk SCENERY_ENCODING, room/instanced_mesh.hpp adopt_by_encoding):
oct packages adopt exactly as the plain reader does and stay unlit until the first draw; prelit packages
(convert_room_bins.py --color prelit) adopt with every part marked lit and their ARGB1555 corners untouched;
oct-vertex packages (--color oct-vertex) adopt unlit with their per-vertex CLR0 table, giving the lighting the same
(material colour, normal) per vertex as the oct encoding; every other encoding is rejected. The plain reader (knob off)
keeps rejecting prelit and oct-vertex packages."""
import importlib.util
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('room_bins_v1_tests', pathlib.Path(__file__).with_name('test_room_bins.py'))
T = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = T
spec.loader.exec_module(T)
C = T.C

ENCODING = 64  # MeshHeader::reserved[0]


def convert(color_mode, data=None):
    with tempfile.TemporaryDirectory() as d:
        p = pathlib.Path(d) / '0000.BIN'
        p.write_bytes(data or T.fixture())
        return C.convert_lod([(1, False, 0, p)], 1.0, color_mode=color_mode)[0]


def many_colours(n=40):
    """A strip of n vertices, each with its own CLR0 (more than the oct palette's 16)."""
    positions = [(i // 2, i % 2, 0) for i in range(n)]
    colors = [(4 * i, 255 - 3 * i, (7 * i) & 255, 255) for i in range(n)]
    strip = [(i, 0, i, i) for i in range(n)]
    return T.synth_bin([(3, [(0x98, strip)])], positions, [(0, 0, 1)], colors, [(i, i % 2) for i in range(n)])


def table(blob):
    """(vertex colour table words, vertex colour slots) of an oct-vertex package."""
    h = C.HEADER.unpack_from(blob, 0)
    nv, off = h[7], h[17]
    return list(struct.unpack_from('<%dI' % nv, blob, off)), [v[5] for v in T.decode(blob)[4]]


def patched(blob, offset, fmt, value):
    out = bytearray(blob)
    struct.pack_into(fmt, out, offset, value)
    return bytes(out)


class SceneryEncodingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = pathlib.Path(cls.temp.name)
        (cls.root / 'kos').mkdir()
        (cls.root / 'kos/fs.h').write_text('#pragma once\n#include <sys/types.h>\nusing file_t=int;\n'
                                           '#define FILEHND_INVALID (-1)\n')
        (cls.root / 'read.cpp').write_text(r'''
#include "instanced_mesh.hpp"
#include <cstdio>
#include <cstring>
#include <fstream>
#include <iterator>
#include <vector>
// read <file> plain|encoding: "ok enc=<reserved[0]> lit=<parts marked lit>/<parts> same=<vertex bytes unchanged>"
int main(int,char** argv){
    std::ifstream in(argv[1],std::ios::binary);
    std::vector<unsigned char> raw((std::istreambuf_iterator<char>(in)),{});
    std::vector<std::uint32_t> words((raw.size()+3)/4);std::memcpy(words.data(),raw.data(),raw.size());
    auto* data=reinterpret_cast<std::uint8_t*>(words.data());
    const auto size=std::uint32_t(raw.size());
    re4dc::room::MeshPackage p;
    const std::uint32_t* vc=nullptr;
    const bool ok=std::strcmp(argv[2],"encoding")==0?re4dc::room::adopt_by_encoding(p,data,size,true,&vc):p.adopt(data,size,true);
    if(!ok){std::printf("reject %s\n",p.error());return 1;}
    const auto& h=p.header();
    unsigned lit=0;
    for(unsigned i=0;i<h.part_count;++i)lit+=p.parts()[i].reserved?1U:0U;
    const bool same=std::memcmp(data+h.vertex_offset,raw.data()+h.vertex_offset,h.vertex_count*12U)==0;
    std::uint32_t enc;std::memcpy(&enc,data+64,4); // the file's word (adopt_by_encoding restores it)
    std::printf("ok enc=%u lit=%u/%u same=%d%s\n",enc,lit,h.part_count,int(same),
                vc?(vc==reinterpret_cast<const std::uint32_t*>(data+h.reserved[1])?" vc":" vc-elsewhere"):"");
    return 0;
}
''')
        cls.exe = cls.root / 'read'
        subprocess.run(['g++', '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror', '-I', str(cls.root), '-I', str(ROOT / 'room'),
                        str(cls.root / 'read.cpp'), '-o', str(cls.exe)], check=True)
        cls.oct = convert('oct')
        cls.prelit = convert('prelit')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def read(self, blob, mode):
        p = self.root / 'x.re4mesh'
        p.write_bytes(blob)
        return subprocess.run([str(self.exe), str(p), mode], text=True, capture_output=True).stdout.strip()

    def parts(self, blob):
        return T.decode(blob)[2]

    def test_oct_adopts_as_the_plain_reader_and_stays_unlit(self):
        n = len(self.parts(self.oct))
        self.assertEqual(struct.unpack_from('<I', self.oct, ENCODING)[0], C.COLOR_OCT_NORMAL)
        self.assertEqual(self.read(self.oct, 'plain'), 'ok enc=1 lit=0/%d same=1' % n)
        self.assertEqual(self.read(self.oct, 'encoding'), 'ok enc=1 lit=0/%d same=1' % n)

    def test_prelit_is_rejected_off_and_adopted_lit_and_untouched_on(self):
        n = len(self.parts(self.prelit))
        self.assertEqual(struct.unpack_from('<I', self.prelit, ENCODING)[0], C.COLOR_ARGB1555)
        self.assertEqual(self.read(self.prelit, 'plain'), 'reject color encoding')
        self.assertEqual(self.read(self.prelit, 'encoding'), 'ok enc=2 lit=%d/%d same=1' % (n, n))

    def test_prelit_corners_are_the_source_colours_not_palette_and_normal(self):
        # fixture colours: (255,255,255,255) and (90,90,90,0); prelit stores ARGB1555 (alpha bit, 5:5:5)
        q = round(90 * 31 / 255)
        expected = {0x8000 | 0x7FFF, (q << 10) | (q << 5) | q}
        colors = {v[5] for v in T.decode(self.prelit)[4]}
        self.assertEqual(colors, expected)
        oct_colors = {v[5] for v in T.decode(self.oct)[4]}
        self.assertTrue(all(c >> 12 < 2 for c in oct_colors))   # palette index << 12 | oct normal

    def test_unknown_encodings_are_rejected(self):
        for value in (0, 3, 0xFFFFFFFF):
            for blob in (self.oct, self.prelit):
                self.assertEqual(self.read(patched(blob, ENCODING, '<I', value), 'encoding'), 'reject color encoding')

    def test_a_prelit_part_already_marked_lit_is_rejected_before_marking(self):
        op = C.HEADER.unpack_from(self.prelit, 0)[11]   # part_offset
        self.assertEqual(self.read(patched(self.prelit, op + 11, '<B', 1), 'encoding'), 'reject part state')

    def test_a_prelit_label_on_oct_corners_is_not_relit(self):
        # Labelled ARGB1555, the slots are drawn as stored: no palette lookup, no normal decode, no lighting.
        n = len(self.parts(self.oct))
        self.assertEqual(self.read(patched(self.oct, ENCODING, '<I', C.COLOR_ARGB1555), 'encoding'),
                         'ok enc=2 lit=%d/%d same=1' % (n, n))
        # Labelled oct, a prelit package's slots index past its one-word palette: rejected, never decoded as normals.
        self.assertEqual(self.read(patched(self.prelit, ENCODING, '<I', C.COLOR_OCT_NORMAL), 'encoding'), 'reject color')

    def test_truncated_header_is_rejected(self):
        self.assertEqual(self.read(self.prelit[:40], 'encoding'), 'reject size')


    def test_more_than_16_colours_adopt_unlit_with_their_table(self):
        with self.assertRaises(ValueError):
            convert('oct', many_colours())
        blob = convert('oct-vertex', many_colours())
        n = len(self.parts(blob))
        self.assertEqual(struct.unpack_from('<I', blob, ENCODING)[0], C.COLOR_OCT_VERTEX)
        self.assertEqual(self.read(blob, 'plain'), 'reject color encoding')
        self.assertEqual(self.read(blob, 'encoding'), 'ok enc=3 lit=0/%d same=1 vc' % n)
        words, slots = table(blob)
        self.assertEqual(len(set(words)), 40)
        self.assertTrue(all(s >> 12 == 0 for s in slots))

    def test_lighting_inputs_equal_the_oct_encoding(self):
        # Same source: per vertex, oct palette[slot >> 12] / slot & 0xfff == oct-vertex table[i] / slot & 0xfff.
        oct, vtx = convert('oct'), convert('oct-vertex')
        do, dv = T.decode(oct), T.decode(vtx)
        self.assertEqual([v[:5] for v in do[4]], [v[:5] for v in dv[4]])
        h = C.HEADER.unpack_from(oct, 0)
        palette = struct.unpack_from('<%dI' % h[9], oct, h[15])
        words, slots = table(vtx)
        self.assertEqual([(palette[v[5] >> 12], v[5] & 0xFFF) for v in do[4]], list(zip(words, [s & 0xFFF for s in slots])))

    def test_bad_table_or_palette_index_is_rejected(self):
        blob = convert('oct-vertex', many_colours())
        size = len(blob)
        for off in (0, 2, size, size - 4):
            self.assertEqual(self.read(patched(blob, ENCODING + 4, '<I', off), 'encoding'), 'reject color encoding')
        ov = C.HEADER.unpack_from(blob, 0)[13]
        self.assertEqual(self.read(patched(blob, ov + 10, '<H', 0x1000), 'encoding'), 'reject color')


if __name__ == '__main__':
    unittest.main()
