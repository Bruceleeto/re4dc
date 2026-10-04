"""ps2_room_r4im.py texture packages against the runtime's CRC-checking reader (room/texture_package.cpp).

The writer's re4dctx_bytes() is the bytes emit() writes. The runtime checks payload_crc32 over every byte after the
48-byte header (Package::adopt via validate(), and open_streamed unless TEX_RESIDENT=1 without TEX_PAYLOAD_CRC).
Packages written before the 2026-10-03 correction carry CRC32 of the texels alone in that field (legacy): the
reader rejects them wherever it checks, and only the play images' CRC-skipping path loads them."""
import ast
import pathlib
import shutil
import struct
import subprocess
import tempfile
import unittest
import zlib

ROOT = pathlib.Path(__file__).parents[1]
TOOL = ROOT / 'tools/ps2_room_r4im.py'


def writer():
    """fnv and re4dctx_bytes from the tool, without its numpy/PIL imports."""
    tree = ast.parse(TOOL.read_text())
    keep = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in ('fnv', 're4dctx_bytes')]
    assert len(keep) == 2
    scope = {'zlib': zlib, 'struct': struct}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(TOOL), 'exec'), scope)
    return scope['re4dctx_bytes'], scope['fnv']


def legacy(data):
    """The pre-correction header: payload_crc32 = CRC32 of the texels alone."""
    out = bytearray(data)
    struct.pack_into('<I', out, 36, zlib.crc32(data[144:]) & 0xffffffff)
    return bytes(out)


READER = r'''
#include "texture_package.hpp"
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <vector>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
int fs_open(const char* p,int f){return ::open(p,f);}
int fs_close(int f){return ::close(f);}
ssize_t fs_total(int f){struct stat s;return fstat(f,&s)?-1:s.st_size;}
void* fs_mmap(int){return nullptr;}
ssize_t fs_read(int f,void* b,size_t n){return ::read(f,b,n);}
off_t fs_seek(int f,off_t o,int w){return ::lseek(f,o,w);}
void* pvr_mem_malloc(std::size_t n){return std::malloc(n);}
void pvr_mem_free(void* p){std::free(p);}
void pvr_txr_load_ex(const void*,void*,unsigned,unsigned,unsigned){}
void pvr_txr_load(const void*,void*,std::size_t){}
int pvr_wait_ready(){return 0;}
int pvr_wait_render_done(){return 0;}
std::uint64_t timer_us_gettime64(){return 0;}
extern "C" void re4dc_pvr_vram_fence(){}
// reader <file>...: "<adopt result> <open_streamed result>" per file ("ok" or the reader's error)
int main(int argc,char** argv){
    for(int i=1;i<argc;++i){
        std::ifstream in(argv[i],std::ios::binary);
        std::vector<unsigned char> raw((std::istreambuf_iterator<char>(in)),{});
        std::vector<std::uint32_t> words((raw.size()+3)/4);if(!raw.empty())std::memcpy(words.data(),raw.data(),raw.size());
        re4dc::texture::Package a,s;
        const bool adopted=a.adopt(reinterpret_cast<const std::uint8_t*>(words.data()),raw.size());
        const bool streamed=s.open_streamed(argv[i]);
        std::printf("%s|%s\n",adopted?"ok":a.error(),streamed?"ok":s.error());
        a.close();s.close();
    }
    return 0;
}
'''


@unittest.skipUnless(shutil.which('g++'), 'host compiler required')
class Ps2TextureCrcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        root = cls.root = pathlib.Path(cls.temp.name)
        (root / 'dc/pvr').mkdir(parents=True)
        (root / 'kos').mkdir()
        (root / 'dc/pvr.h').write_text('#pragma once\nusing pvr_ptr_t=void*;\n#define PVR_TXRFMT_RGB565 (1U<<27)\n'
                                       '#define PVR_TXRFMT_ARGB1555 0U\n#define PVR_TXRFMT_ARGB4444 (2U<<27)\n'
                                       '#define PVR_TXRFMT_VQ_ENABLE (1U<<30)\n#define PVR_TXRFMT_TWIDDLED 0U\n'
                                       '#define PVR_TXRFMT_NONTWIDDLED (1U<<26)\n'
                                       'int pvr_wait_ready();int pvr_wait_render_done();\n')
        (root / 'dc/pvr/pvr_mem.h').write_text('#include <cstddef>\nvoid* pvr_mem_malloc(std::size_t);void pvr_mem_free(void*);\n')
        (root / 'dc/pvr/pvr_txr.h').write_text('#include <cstddef>\n#define PVR_TXRLOAD_16BPP 0\nvoid pvr_txr_load_ex(const void*,void*,unsigned,unsigned,unsigned);'
                                               'void pvr_txr_load(const void*,void*,std::size_t);\n')
        (root / 'kos/fs.h').write_text('#pragma once\n#include <sys/types.h>\nusing file_t=int;\n#define FILEHND_INVALID -1\n'
                                       'int fs_open(const char*,int);int fs_close(int);ssize_t fs_total(int);void* fs_mmap(int);'
                                       'ssize_t fs_read(int,void*,size_t);off_t fs_seek(int,off_t,int);\n')
        (root / 'kos.h').write_text('#include <kos/fs.h>\n#include <fcntl.h>\n#include <cstdint>\nstd::uint64_t timer_us_gettime64();\n')
        (root / 'reader.cpp').write_text('#include <cstring>\n' + READER)
        scene = ROOT / 'room'
        cls.exe = {}
        # 0: the runtime CRC check (TEX_PAYLOAD_CRC=1 builds, every non-resident build); 1: the play images'
        # TEX_RESIDENT=1 open_streamed (no payload CRC, header and descriptors validated).
        for resident in ('0', '1'):
            exe = root / f'reader{resident}'
            subprocess.run(['g++', '-std=c++17', f'-DRE4DC_TEX_RESIDENT={resident}', '-DRE4DC_STORAGE_BOUNCE_BYTES=16384',
                            '-I' + str(root), '-I' + str(scene), str(root / 'reader.cpp'),
                            str(scene / 'texture_package.cpp'), str(scene / 'room_storage.cpp'), '-o', str(exe)],
                           check=True)
            cls.exe[resident] = exe
        write, fnv = writer()
        cls.write, cls.fnv = staticmethod(write), staticmethod(fnv)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def read(self, data, resident='0'):
        p = self.root / 'x.re4tex'
        p.write_bytes(data)
        return subprocess.run([str(self.exe[resident]), str(p)], text=True, capture_output=True,
                              check=True).stdout.strip()

    def packages(self):
        """The two payload kinds the converter writes: twiddled 16-bit (ptype 1) and full-codebook VQ (ptype 2)."""
        twiddled = bytes((i * 37) & 255 for i in range(8 * 8 * 2))
        vq = bytes((i * 11) & 255 for i in range(2048)) + bytes(range(16 * 16 // 4))
        return [self.write('PS2 test twiddled', 8, 8, 1, 1, twiddled), self.write('PS2 test vq', 16, 16, 0, 2, vq)]

    def test_written_texture_is_accepted_by_the_crc_checking_reader(self):
        for data, key in self.packages():
            self.assertEqual(self.read(data), 'ok|ok', key)
            self.assertEqual(struct.unpack_from('<I', data, 36)[0], zlib.crc32(data[48:]) & 0xffffffff)

    def test_key_is_the_texel_identity_and_unchanged_by_the_correction(self):
        for data, key in self.packages():
            payload = data[144:]
            self.assertEqual(key, '%08x-%08x' % (zlib.crc32(payload) & 0xffffffff, self.fnv(payload)))

    def test_legacy_header_is_rejected_where_the_crc_is_checked(self):
        for data, key in self.packages():
            old = legacy(data)
            self.assertEqual(len(old), len(data))
            self.assertEqual([i for i in range(len(data)) if old[i] != data[i]][:1][0] // 4, 9, key)  # payload_crc32, bytes 36..39 only
            self.assertEqual(old[:36] + old[40:], data[:36] + data[40:])
            self.assertEqual(self.read(old), 'payload CRC mismatch|streamed payload read or CRC mismatch')
            # The play images' streamed path skips the payload CRC: legacy files load there, as they always did.
            self.assertEqual(self.read(old, '1').split('|')[1], 'ok')

    def test_corrupted_texels_are_rejected(self):
        data, _ = self.packages()[0]
        bad = bytearray(data)
        bad[-1] ^= 1
        self.assertEqual(self.read(bytes(bad)), 'payload CRC mismatch|streamed payload read or CRC mismatch')


if __name__ == '__main__':
    unittest.main()
