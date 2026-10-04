"""PS2_WORLD_REGISTRY: the generated room bitmap (game/platform/include/ps2_world_rooms.inc, written by
tools/d367/ps2world/world_registry.py) and the host package check (tools/d367/ps2world/ps2_world_check.cpp, the
runtime's MeshPackage::adopt + ps2_open's sidecar checks)."""
from pathlib import Path
import hashlib, importlib.util, json, re, shutil, struct, subprocess, tempfile, unittest, zlib

HERE = Path(__file__).resolve().parent
DC = HERE.parent
INC = DC / "game" / "platform" / "include" / "ps2_world_rooms.inc"
TOOL = DC / "tools" / "d367" / "ps2world"
spec = importlib.util.spec_from_file_location("world_registry", TOOL / "world_registry.py")
registry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(registry)


def decode(text):
    """The rooms native_static.cpp re4dc_ps2_world_room admits for an .inc (its lookup, in Python)."""
    rows = [[int(w, 16) for w in re.findall(r"0x([0-9a-f]{8})U", line)] for line in text.splitlines()
            if line.startswith("{")]
    assert len(rows) == 6 and all(len(r) == 8 for r in rows), rows
    return sorted("r%x%02x" % (st, ix) for st in range(6) for ix in range(256) if (rows[st][ix >> 5] >> (ix & 31)) & 1)


class Bitmap(unittest.TestCase):
    def test_round_trip(self):
        rooms = ["r100", "r101", "r11f", "r120", "r21d", "r2ff", "r400", "r411", "r5ff"]
        self.assertEqual(decode(registry.bitmap_inc(rooms, "x")), rooms)

    def test_generated_inc(self):
        text = INC.read_text()
        listed = re.search(r"^//   (.*)$", text, re.M).group(1).split()
        self.assertEqual(decode(text), sorted(listed))
        # the hand list (PS2_WORLD_REGISTRY=0) must stay admitted: those rooms are runtime-proven
        for room in ("r100", "r101", "r103", "r104", "r105", "r106", "r107"):
            self.assertIn(room, listed)
        self.assertNotIn("r120", listed)   # no scenario SMD: nothing to draw


@unittest.skipUnless(shutil.which("g++"), "host compiler required")
class Check(unittest.TestCase):
    def test_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            exe = t / "check"
            subprocess.run(["g++", "-std=c++17", "-O1", "-DRE4DC_TREE_IMPOSTOR=1", "-DRE4DC_MESH_TEXTURES=1",
                            "-I", str(TOOL / "hostinc"), "-I", str(DC / "room"), str(TOOL / "ps2_world_check.cpp"),
                            "-o", str(exe)], check=True)
            side = t / "w.r4pw"
            side.write_bytes(struct.pack("<4s7I", b"R4PW", 1, 0, 0, 0, 0, 0, 0))

            def why(mesh_bytes):
                mesh = t / "w.re4mesh"
                mesh.write_bytes(mesh_bytes)
                r = subprocess.run([str(exe), str(mesh), str(side)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 1)
                return re.search(r'"why": "([^"]*)"', r.stdout).group(1)

            self.assertEqual(why(b""), "missing or no heap")                       # ps2_open: msize 0
            self.assertEqual(why(b"R4IM" + bytes(20)), "size")                     # shorter than the header
            self.assertEqual(why(b"XXXX" + struct.pack("<I", 3) + bytes(72)), "header")
            # right magic/version but the byte count disagrees with the file size
            self.assertEqual(why(b"R4IM" + struct.pack("<II", 3, 999) + bytes(68)), "header")


def re4tex(w=8, h=8, rule="data", payload_kind=2, fmt=0):
    """A one-descriptor RE4DCTX package as the PS2 converter writes it (VQ by default)."""
    size = 2048 + w * h // 4 if payload_kind == 2 else w * h * 2
    data = bytes((i * 7) & 255 for i in range(size))
    desc = struct.pack("<64s8I", b"t", w, h, fmt, 144, size, 0, payload_kind, 0)
    crc = zlib.crc32(data) if rule == "data" else zlib.crc32(desc + data)
    return struct.pack("<8s10I", b"RE4DCTX\0", 2, 48, 96, 1, 48, 144, size, crc, 1, 0) + desc + data


class Textures(unittest.TestCase):
    def test_accepts_both_crc_rules(self):
        self.assertEqual(registry.tex_package_error(re4tex(), 8, 8), (None, "data"))
        self.assertEqual(registry.tex_package_error(re4tex(rule="header"), 8, 8), (None, "header"))

    def test_rejects(self):
        good = re4tex(16, 8)
        bad = lambda b, w=16, h=8: registry.tex_package_error(b, w, h)[0]
        self.assertIsNotNone(bad(good[:-1]))                              # truncated payload
        self.assertIsNotNone(bad(good[:40]))                              # truncated header
        self.assertIsNotNone(bad(good[:-1] + bytes([good[-1] ^ 1])))      # altered texel
        self.assertIn("part samples", bad(good, 8, 8))                    # not the part's size
        self.assertIsNotNone(bad(re4tex(payload_kind=0), 8, 8))           # linear: open_streamed refuses it
        self.assertIsNotNone(bad(re4tex(fmt=5), 8, 8))                    # unknown format
        self.assertIsNotNone(bad(b"RE4DCTY\0" + good[8:]))                # magic

    def test_missing_texture_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "tex").mkdir()
            (d / "tex" / "0000000a-0000000b.re4tex").write_bytes(re4tex())
            keys = [["0000000a", "0000000b", 8, 8, 0, 0], ["0000000c", "0000000d", 8, 8, 0, 0]]
            r = registry.check_textures(d, keys, None)
            self.assertEqual(r["missing"], ["0000000c-0000000d"])
            self.assertEqual(len(r["files"]), 1)


class Provenance(unittest.TestCase):
    """check_provenance fails closed: removing the report, the manifest record or an input excludes the room."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.pd = t / "out" / "r2ff-ps2"
        self.pd.mkdir(parents=True)
        (self.pd / "ps2-world.re4mesh").write_bytes(b"mesh")
        (self.pd / "ps2-world.r4pw").write_bytes(b"side")
        self.m, self.s = registry.sha(self.pd / "ps2-world.re4mesh"), registry.sha(self.pd / "ps2-world.r4pw")
        inputs = t / "inputs" / "r2ff"
        inputs.mkdir(parents=True)
        (inputs / "r2ff_004.SMD").write_bytes(b"smd")
        self.input = inputs / "r2ff_004.SMD"
        (self.pd / "ps2-world.json").write_text(json.dumps(dict(
            re4mesh_sha256=self.m, r4pw_sha256=self.s, args=dict(src=str(inputs)))))
        self.iso = t / "ps2.iso"
        self.iso.write_bytes(bytes(4096) + bytes(range(100)))
        self.member = dict(name="r2ff.dat", offset=4096, size=100)
        claim = hashlib.sha256(bytes(range(100))).hexdigest()
        self.manifests = {"m": {"rooms": {"r2ff": dict(member=dict(self.member, sha256=claim), files={
            "r2ff_004.SMD": dict(bytes=3, sha256=registry.sha(self.input))})}}}

    def tearDown(self):
        self.tmp.cleanup()

    def fails(self, manifests=None, member=None):
        return registry.check_provenance("r2ff", self.pd, self.m, self.s,
                                         self.manifests if manifests is None else manifests,
                                         self.member if member is None else member, iso=self.iso)[1]

    def test_complete_passes(self):
        self.assertEqual(self.fails(), [])

    def test_no_report(self):
        (self.pd / "ps2-world.json").unlink()
        self.assertTrue(any("no converter report" in f for f in self.fails()))

    def test_report_names_other_bytes(self):
        (self.pd / "ps2-world.re4mesh").write_bytes(b"other")
        self.m = registry.sha(self.pd / "ps2-world.re4mesh")
        self.assertTrue(any("other package hashes" in f for f in self.fails()))

    def test_no_manifest_record(self):
        self.assertTrue(any("no extraction manifest" in f for f in self.fails(manifests={"m": {"rooms": {}}})))

    def test_empty_manifest_record(self):
        empty = {"m": {"rooms": {"r2ff": dict(member=dict(self.member, sha256="00" * 32), files={})}}}
        self.assertTrue(any("lists no input files" in f for f in self.fails(manifests=empty)))

    def test_missing_input(self):
        self.input.unlink()
        self.assertTrue(any("converter input" in f for f in self.fails()))

    def test_changed_input(self):
        self.input.write_bytes(b"smd2")
        self.assertTrue(any("converter input" in f for f in self.fails()))

    def test_inputs_dir_absent(self):
        shutil.rmtree(self.input.parent)
        self.assertTrue(any("converter inputs absent" in f for f in self.fails()))

    def test_member_mismatch(self):
        self.assertTrue(any("AFS member" in f for f in self.fails(member=dict(self.member, size=101))))

    def test_legacy_binds_exact_bytes(self):
        leg = registry.LEGACY["r101"]
        prov = dict(report=dict(sha256=leg["report_sha256"]))
        self.assertFalse(registry.legacy_holds("r101", leg["re4mesh_sha256"], "0" * 64, prov))
        self.assertFalse(registry.legacy_holds("r101", leg["re4mesh_sha256"], leg["r4pw_sha256"],
                                               dict(report=dict(sha256="0" * 64))))
        self.assertFalse(registry.legacy_holds("r100", leg["re4mesh_sha256"], leg["r4pw_sha256"], prov))


class TexturePrecedence(unittest.TestCase):
    """select_texture / pack_members: the bytes native_ui.cpp load() reads for a key."""

    def test_pack_member_wins_over_conflicting_loose(self):
        import sys
        sys.path.insert(0, str(DC / "tools" / "d367"))
        import texpack
        packed, loose = re4tex(8, 8), re4tex(16, 16)
        blob, _ = texpack.build({(0xa, 0xb): packed})
        pack = registry.pack_members(blob)
        key = "0000000a-0000000b"
        staged = {"dc/tex/0/%s.re4tex" % key: hashlib.sha256(loose).hexdigest()}
        self.assertEqual(registry.select_texture(key, True, pack, set(), staged),
                         ("pack", hashlib.sha256(packed).hexdigest()))
        # TEX_PACK=0 image, or no usable pack: the loose file
        self.assertEqual(registry.select_texture(key, False, pack, set(), staged)[1], hashlib.sha256(loose).hexdigest())
        self.assertEqual(registry.select_texture(key, True, None, set(), staged)[0], "loose")
        # a key the pack lacks falls back to its loose file, or to nothing
        other = "0000000c-0000000d"
        self.assertEqual(registry.select_texture(other, True, pack, set(), staged), ("loose", None))
        staged["dc/tex/0/%s.re4tex" % other] = "ab" * 32
        self.assertEqual(registry.select_texture(other, True, pack, set(), staged), ("loose", "ab" * 32))
        # a Standard (texlow) key never reads the pack
        self.assertEqual(registry.select_texture(key, True, pack, {key}, staged), ("texlow", None))

    def test_invalid_pack_is_unusable(self):
        import sys
        sys.path.insert(0, str(DC / "tools" / "d367"))
        import texpack
        blob, _ = texpack.build({(0xa, 0xb): re4tex()})
        self.assertIsNone(registry.pack_members(blob[:2048 + 8] + b"\xff" + blob[2048 + 9:]))   # index crc


class MemberBytes(unittest.TestCase):
    def test_claimed_member_hash_must_match_disc_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            iso = t / "ps2.iso"
            iso.write_bytes(bytes(4096) + b"member bytes" + bytes(100))
            pd = t / "out" / "r2ff-ps2"
            pd.mkdir(parents=True)
            (pd / "ps2-world.re4mesh").write_bytes(b"m")
            (pd / "ps2-world.r4pw").write_bytes(b"s")
            m, s = registry.sha(pd / "ps2-world.re4mesh"), registry.sha(pd / "ps2-world.r4pw")
            inputs = t / "inputs" / "r2ff"
            inputs.mkdir(parents=True)
            (inputs / "a.SMD").write_bytes(b"x")
            (pd / "ps2-world.json").write_text(json.dumps(dict(re4mesh_sha256=m, r4pw_sha256=s, args=dict(src=str(inputs)))))
            member = dict(name="r2ff.dat", offset=4096, size=12)
            good = hashlib.sha256(b"member bytes").hexdigest()

            def fails(claim):
                man = {"m": {"rooms": {"r2ff": dict(member=dict(member, sha256=claim),
                                                    files={"a.SMD": dict(sha256=registry.sha(inputs / "a.SMD"))})}}}
                return registry.check_provenance("r2ff", pd, m, s, man, member, iso=iso)[1]

            self.assertEqual(fails(good), [])
            self.assertTrue(any("differs from the configured disc" in f for f in fails("00" * 32)))


class StagedFixture(unittest.TestCase):
    """Fixture: what a disc staged from a fixture holds (stage-scenario.py: sources relative to the fixture's own
    directory, removals, then the media overlay and the base disc); texture(): pack member over loose file."""

    def setUp(self):
        import sys
        sys.path.insert(0, str(DC / "tools" / "d367"))
        self.tmp = tempfile.TemporaryDirectory()
        self.t = Path(self.tmp.name)
        self.saved = (registry.TOUR, registry.ROUTE_FIXTURES, registry.OVERLAY, registry.BASE_DISC)
        registry.TOUR, registry.ROUTE_FIXTURES = self.t / "tour", self.t / "repo"
        registry.OVERLAY, registry.BASE_DISC = self.t / "overlay", self.t / "none.bin"
        for d in ("tour/play", "repo", "pkg", "overlay/dc/tex/0"):
            (self.t / d).mkdir(parents=True)

    def tearDown(self):
        registry.TOUR, registry.ROUTE_FIXTURES, registry.OVERLAY, registry.BASE_DISC = self.saved
        self.tmp.cleanup()

    def write(self, path, doc):
        path.write_text(json.dumps(doc))
        return path

    def test_relative_sources_resolve_against_the_fixture_directory(self):
        (self.t / "pkg" / "w.re4mesh").write_bytes(b"play world")
        (self.t / "tour" / "pkg.re4mesh").write_bytes(b"other bytes")
        f = self.write(self.t / "tour" / "play" / "p.json", {"replace": {"dc/native/r100/ps2-world.re4mesh": "../../pkg/w.re4mesh"}})
        self.assertEqual(registry.Fixture(f).read("dc/native/r100/ps2-world.re4mesh")[0], b"play world")
        # a repo copy of a tour/ fixture resolves against tour/, as the staged tour/ original did
        g = self.write(self.t / "repo" / "r.json", {"replace": {"dc/native/r100/ps2-world.re4mesh": "pkg.re4mesh"}})
        self.assertEqual(registry.Fixture(g).read("dc/native/r100/ps2-world.re4mesh")[0], b"other bytes")

    def test_fixture_dirs_add_lane_stagings(self):
        (self.t / "pkg" / "w.re4mesh").write_bytes(b"lane world")
        lane = self.t / "lane"
        lane.mkdir()
        self.write(lane / "l.json", {"replace": {"dc/native/r219/ps2-world.re4mesh": str(self.t / "pkg" / "w.re4mesh"),
                                                "st2/r219.dar": str(self.t / "pkg" / "w.re4mesh")}})
        (lane / "l.json.sources").write_text("{}")   # not a fixture
        pkg, rooms, plays = registry.fixture_staging(play_fixtures=[], fixture_dirs=[lane])
        self.assertEqual([s["fixture"].name for s in pkg["r219"]], ["l.json"])
        self.assertEqual(rooms["r219"], ["l.json"])
        self.assertEqual(registry.fixture_staging(play_fixtures=[])[0].get("r219"), None)

    def test_pack_member_over_loose_and_removed_files(self):
        import texpack
        packed, loose, other = re4tex(8, 8), re4tex(16, 16), re4tex(32, 32)
        blob, _ = texpack.build({(0xa, 0xb): packed})
        (self.t / "pkg" / "t.pak").write_bytes(blob)
        (self.t / "pkg" / "a.re4tex").write_bytes(loose)
        (self.t / "overlay" / "dc/tex/0/0000000e-0000000f.re4tex").write_bytes(other)
        f = self.write(self.t / "tour" / "play" / "p.json", {
            "replace": {"dc/tex.pak": "../../pkg/t.pak", "dc/tex/0/0000000a-0000000b.re4tex": "../../pkg/a.re4tex"},
            "remove": ["dc/tex/0/0000000c-0000000d.re4tex"]})
        fx = registry.Fixture(f)
        self.assertEqual(fx.texture("0000000a-0000000b")[0], packed)           # the member, not the loose file
        self.assertIsNone(fx.texture("0000000c-0000000d")[0])                  # removed and not packed: nothing
        self.assertEqual(fx.texture("0000000e-0000000f")[0], other)            # not in the fixture: the overlay
        self.assertIsNone(fx.texture("00000010-00000011")[0])                  # nowhere (no base disc)
        # an invalid pack is unusable: the loose file is read
        (self.t / "pkg" / "t.pak").write_bytes(blob[:2048 + 8] + b"\xff" + blob[2048 + 9:])
        self.assertEqual(registry.Fixture(f).texture("0000000a-0000000b")[0], loose)


class SourceHealth(unittest.TestCase):
    """source_health: the game's soft failure logs, attributed to the room last entered; healthy lines ignored."""

    def test_categories_and_rooms(self):
        log = b"\n".join([
            b"DVD: Memory allocate failed",                                   # before any room mark
            b"warp: room enter 104 (#1) vbl=376 wall_ms=6505",
            b"DVD: Memory allocate failed",
            b"EmSetFromList2() Em set failed, Id = 13",
            b"work backing: grow size=3552 capacity=60 resident=7584 peak=7584 chunks=1 reclaimed=0 failures=0 heap=4",
            b"native pipeline: frame=120 mode=x submitted=1 resolved=1 fence_blocked=0 fence_wait_us=0 fence_timeouts=0 failures=0",
            b"ShadowModelInit():PtNum Over (Em:3/Sh:4)",                      # a warning, not a failure
            b"native UI: upload FAILED vram=0",                               # render staging, not a source failure
            b"room lifecycle: phase=enter room=107 generation=2 frames=0",
            b"em21() ModelInit failed.",
            b"createSat() memory alloc failed.",
            b"work backing: grow size=1 capacity=1 resident=1 peak=1 chunks=1 reclaimed=0 failures=2 heap=4",
            b"native pipeline: frame=240 mode=x submitted=1 resolved=1 failures=1 wake_render=0",
        ])
        h = registry.source_health(log)
        self.assertEqual(h["rooms"]["r???"], {"dvd_alloc_failed": 1})
        self.assertEqual(h["rooms"]["r104"], {"dvd_alloc_failed": 1, "em_set_failed": 1})
        self.assertEqual(h["rooms"]["r107"], {"model_init_failed": 1, "create_sat_failed": 1, "backing_failed": 1,
                                              "pipeline_failures": 1})
        self.assertEqual(sum(h["counts"].values()), 7)


class DoorCache(unittest.TestCase):
    def test_keyed_by_disc_and_parser(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            iso = t / "disc.iso"
            iso.write_bytes(b"disc one")
            parser = {str(p.relative_to(registry.TOOLS)): registry.sha(p) for p in registry.ARRIVAL_PARSER}
            psha = hashlib.sha256(json.dumps(parser, sort_keys=True).encode()).hexdigest()
            isha = registry.sha(iso)
            doc = dict(iso_sha256=isha, parser_sha256=psha, rooms=["r100"], arrivals={})
            (t / f"gc-doors-{isha[:16]}-{psha[:16]}.json").write_text(json.dumps(doc))
            self.assertEqual(registry.gc_rooms_and_arrivals(iso, t)["rooms"], ["r100"])
            iso.write_bytes(b"disc two")   # other media: the cached scan must not be reused (the parse then fails)
            with self.assertRaises(Exception):
                registry.gc_rooms_and_arrivals(iso, t)


if __name__ == "__main__":
    unittest.main()
