"""TEX_PACK: the runtime index (game/platform/include/texpack_index.inc, compiled unchanged against a mock disc
reader by tests/texpack_index_host.cpp) and the builder (tools/d367/texpack.py).

Architect review 2026-10-03: P1, one transient header read failure latched the pack off for the session (and the
per-file fallback then cached the packed keys as missing); P2, the index CRC, the count bound (count*16 wrapped at
0x10000000), extents and key order were not checked; the builder silently replaced duplicate keys.
"""
from pathlib import Path
import importlib.util, shutil, struct, subprocess, tempfile, unittest, zlib

HERE = Path(__file__).resolve().parent
INC = HERE.parent / "game" / "platform" / "include"
TOOL = HERE.parent / "tools" / "d367" / "texpack.py"
spec = importlib.util.spec_from_file_location("texpack", TOOL)
texpack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(texpack)


def package(tag):
    return b"RE4DCTX\x00" + bytes([tag]) * 40


@unittest.skipUnless(shutil.which("g++"), "host compiler required")
class RuntimeIndex(unittest.TestCase):
    def test_host(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "texpack_index_host"
            subprocess.run(["g++", "-std=c++17", "-O1", "-Wall", "-Wno-unused-function", "-I", str(INC),
                            str(HERE / "texpack_index_host.cpp"), "-o", str(exe)], check=True)
            r = subprocess.run([str(exe)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("TEXPACK_INDEX_HOST_TEST PASS", r.stdout)


class Builder(unittest.TestCase):
    def test_layout_and_crc(self):
        pkgs = {(2, 1): package(2), (1, 9): package(1), (1, 3): package(3)}
        blob, count = texpack.build(pkgs)
        self.assertEqual(count, 3)
        magic, (ver, n, index_at, data_at, crc) = blob[:8], struct.unpack_from("<5I", blob, 8)
        self.assertEqual((magic, ver, n, index_at, data_at), (b"RE4PAK1\x00", 1, 3, 2048, 4096))
        self.assertEqual(crc, zlib.crc32(blob[2048:4096]))
        keys = [struct.unpack_from("<2I", blob, 2048 + 16 * i) for i in range(3)]
        self.assertEqual(keys, sorted(keys))
        for i in range(3):
            off, size = struct.unpack_from("<2I", blob, 2048 + 16 * i + 8)
            self.assertEqual(off % 2048, 0)
            self.assertEqual(blob[off:off + size], pkgs[keys[i]])

    def test_verify(self):
        blob, _ = texpack.build({(1, 1): package(1), (2, 2): package(2)})
        self.assertEqual(texpack.verify(blob)[0], 2)
        bad = bytearray(blob)
        bad[2048 + 8:2048 + 12] = bad[2048 + 16 + 8:2048 + 16 + 12]   # key 1 -> key 2's package: the CRC catches it
        with self.assertRaises(SystemExit):
            texpack.verify(bytes(bad))
        bad = bytearray(blob)
        struct.pack_into("<I", bad, 12, 0x10000000)
        with self.assertRaises(SystemExit):
            texpack.verify(bytes(bad))

    def test_count_cap(self):
        with self.assertRaises(SystemExit):
            texpack.build({(i, 0): package(1) for i in range(texpack.MAX_COUNT + 1)})
        with self.assertRaises(SystemExit):
            texpack.build({})

    def test_duplicate_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "0", Path(tmp) / "1"
            a.mkdir(); b.mkdir()
            (a / "00000001-00000002.re4tex").write_bytes(package(1))
            (b / "00000001-00000002.re4tex").write_bytes(package(1))
            self.assertEqual(len(texpack.from_dir(tmp)), 1)          # identical copies are one package
            (b / "00000001-00000002.re4tex").write_bytes(package(2))
            with self.assertRaises(SystemExit):
                texpack.from_dir(tmp)


if __name__ == "__main__":
    unittest.main()
