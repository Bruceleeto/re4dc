"""Candidate policy gates using synthetic native packages; no game data."""
from pathlib import Path
import copy
import importlib.util
import json
import struct
import tempfile
import unittest
import zlib

import numpy as np
from PIL import Image

TOOL = Path(__file__).resolve().parents[1] / "tools/ps2_vegetation_candidate.py"
spec = importlib.util.spec_from_file_location("vegetation_candidate", TOOL)
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        rgba = np.zeros((8, 8, 4), np.uint8)
        rgba[..., :3] = [68, 102, 153]
        rgba[..., 3] = np.tile(np.array([0, 64, 128, 239, 0, 239, 128, 64], np.uint8), (8, 1))
        Image.fromarray(rgba).save(self.root / "source.png")
        words = v.pack_rgba(rgba, 2)
        blob = v.cb.package_twiddled16("synthetic graded foliage", words, fmt=2)
        self.key = v.key_of_payload(blob[144:])
        other = rgba.copy()
        other[..., :3] = [34, 17, 51]
        other_blob = v.cb.package_twiddled16("unselected soft shade", v.pack_rgba(other, 2), fmt=2)
        self.other_key = v.key_of_payload(other_blob[144:])
        self.packages = {self.key: blob, self.other_key: other_blob}
        parts = [
            (*self.key, 8, 8, 2, 2, 3, 0),
            (*self.key, 8, 8, 0, 2, 3, 0),  # same key on an opaque part must stay byte-identical
            (*self.other_key, 8, 8, 2, 0, 12, 0),
        ]
        place = struct.pack("<HH12f", 0, 0, 1, 0, 0, 12, 0, 1, 0, 34, 0, 0, 1, 56)
        body = b"".join(v.PART.pack(*p) for p in parts) + place
        self.side = v.SIDECAR.pack(b"R4PW", 1, 1, 3, 1, zlib.crc32(body), 0, 0) + body
        # Mesh is opaque to material conversion. Counts and native body CRC must agree.
        mesh_body = bytes(range(32)) + bytes([71]) * 48
        self.mesh = struct.pack("<4s19I", b"R4IM", 3, 80 + len(mesh_body), zlib.crc32(mesh_body),
                                1, 3, 0, 0, 0, 0, *([0] * 10)) + mesh_body
        self.ids = struct.pack("<4s3I", b"R4ID", 1, 1, zlib.crc32(body)) + b"\x25" + bytes(15)
        self.material = {
            "key": v.key_string(self.key), "source_texture_index": 3, "class": "vegetation",
            "semantic_review": True, "threshold": 160, "rgb_gain": [1, 1, 1],
            "source_png": self.pin("source.png"),
        }
        self.room = {
            "room": "r101", "r4pw": self.write_pin("world.r4pw", self.side),
            "mesh": self.write_pin("world.re4mesh", self.mesh),
            "ids": self.write_pin("world.ids", self.ids), "materials": [self.material],
        }
        pack, _ = v.texpack.build(self.packages)
        self.policy = {"schema": v.POLICY_SCHEMA, "tex_pak": self.write_pin("tex.pak", pack),
                       "rooms": [self.room]}

    def tearDown(self):
        self.tmp.cleanup()

    def pin(self, name):
        return {"path": name, "sha256": v.sha((self.root / name).read_bytes())}

    def write_pin(self, name, blob):
        (self.root / name).write_bytes(blob)
        return self.pin(name)

    def run_room(self, room=None):
        return v.build_room(room or self.room, self.packages, self.root)

    def test_only_explicit_tr_part_changes(self):
        files, new, proof = self.run_room()
        self.assertEqual(files["ps2-world.re4mesh"], self.mesh)
        oldh, oldp, oldplace, _ = v.parse_sidecar(self.side)
        newh, newp, newplace, _ = v.parse_sidecar(files["ps2-world.r4pw"])
        self.assertEqual(oldplace, newplace)
        self.assertEqual(newp[1:], oldp[1:])
        self.assertEqual((oldp[0][4], newp[0][4]), (2, 1))
        self.assertEqual(proof["changed_parts"], [0])
        self.assertEqual(struct.unpack_from("<I", files["ps2-world.ids"], 12)[0], newh[5])
        self.assertNotEqual(oldh[5], newh[5])
        self.assertEqual(files["ps2-world.ids"][16:], self.ids[16:])
        self.assertEqual(len(new), 1)
        self.assertTrue(proof["materials"][0]["baseline_payload_reproduced"])

    def test_r100_cell_changes_only_actual_sidecar_identity(self):
        room = copy.deepcopy(self.room)
        room["room"] = "r100"
        mh = v.parse_mesh(self.mesh, v.parse_sidecar(self.side)[0])
        old_crc = v.parse_sidecar(self.side)[0][5]
        cell = struct.pack("<4s7I", b"PCL1", 0x100, mh["crc"], old_crc, len(self.mesh), 1, 1, 0)
        cell += struct.pack("<6f2H", -1, -2, -3, 1, 2, 3, 0, 1)
        cell += struct.pack("<I5f", 0, 100, -50, 50, -40, 40)
        room["cell"] = self.write_pin("interior.cell", cell)
        files, _, proof = self.run_room(room)
        after = files["interior.cell"]
        self.assertEqual(after[:12] + after[16:], cell[:12] + cell[16:])
        self.assertEqual(struct.unpack_from("<I", after, 12)[0],
                         int(proof["required_kPcSidecarUse"], 16))
        self.assertTrue(proof["interior_cell_identity_only"])

    def test_reject_missing_r100_cell(self):
        room = copy.deepcopy(self.room)
        room["room"] = "r100"
        with self.assertRaisesRegex(v.CandidateError, "requires.*cell"):
            self.run_room(room)

    def test_reject_soft_or_unreviewed_material(self):
        for update in ({"class": "soft"}, {"class": "unclassified"}, {"semantic_review": False}):
            room = copy.deepcopy(self.room)
            room["materials"][0].update(update)
            with self.assertRaises(v.CandidateError):
                self.run_room(room)

    def test_reject_source_gain_or_alpha_mismatch(self):
        room = copy.deepcopy(self.room)
        room["materials"][0]["rgb_gain"] = [1, 1, 0.5]
        with self.assertRaisesRegex(v.CandidateError, "does not reproduce"):
            self.run_room(room)
        im = np.asarray(Image.open(self.root / "source.png")).copy()
        im[0, 0, 3] = 239
        Image.fromarray(im).save(self.root / "different.png")
        room["materials"][0]["rgb_gain"] = [1, 1, 1]
        room["materials"][0]["source_png"] = self.pin("different.png")
        with self.assertRaisesRegex(v.CandidateError, "does not reproduce"):
            self.run_room(room)

    def test_reject_pin_mismatch(self):
        room = copy.deepcopy(self.room)
        room["materials"][0]["source_png"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(v.CandidateError, "SHA mismatch"):
            self.run_room(room)

    def test_reject_vertex_alpha_marked_part(self):
        changed = bytearray(self.side)
        changed[32 + 15] = 1
        struct.pack_into("<I", changed, 20, zlib.crc32(changed[32:]))
        room = copy.deepcopy(self.room)
        room["r4pw"] = self.write_pin("marked.r4pw", changed)
        with self.assertRaisesRegex(v.CandidateError, "vertex-alpha"):
            self.run_room(room)

    def test_reject_geometry_or_opaque_edit_proof(self):
        files, _, _ = self.run_room()
        changed = bytearray(files["ps2-world.r4pw"])
        changed[32 + 16 + 12] = 1  # unselected OP part
        struct.pack_into("<I", changed, 20, zlib.crc32(changed[32:]))
        with self.assertRaisesRegex(v.CandidateError, "unselected"):
            v.prove_sidecar_edit(self.side, changed, {0})
        changed = bytearray(files["ps2-world.r4pw"])
        changed[-1] ^= 1  # placement affine
        struct.pack_into("<I", changed, 20, zlib.crc32(changed[32:]))
        with self.assertRaisesRegex(v.CandidateError, "placements"):
            v.prove_sidecar_edit(self.side, changed, {0})

    def test_reject_bad_crc_duplicate_or_wrong_selector(self):
        changed = bytearray(self.side)
        changed[35] ^= 1
        with self.assertRaisesRegex(v.CandidateError, "body CRC"):
            v.parse_sidecar(changed)
        room = copy.deepcopy(self.room)
        room["materials"].append(copy.deepcopy(room["materials"][0]))
        with self.assertRaisesRegex(v.CandidateError, "duplicate"):
            self.run_room(room)
        room["materials"] = [room["materials"][0]]
        room["materials"][0]["source_texture_index"] = 99
        with self.assertRaisesRegex(v.CandidateError, "no TR parts"):
            self.run_room(room)

    def test_complete_output_retains_every_baseline_package(self):
        policy = self.root / "policy.json"
        policy.write_text(json.dumps(self.policy))
        output = self.root / "candidate"
        report = v.build_policy(policy, output, ["r101"], "/private/candidate")
        after = v.parse_pack((output / "tex.pak").read_bytes())
        for key, value in self.packages.items():
            self.assertEqual(after[key], value)
        self.assertEqual((output / "rooms/r101/ps2-world.re4mesh").read_bytes(), self.mesh)
        self.assertEqual(report["new_texture_count"], 1)
        fixture = json.loads((output / "fixture-replace.json").read_text())
        self.assertEqual(fixture["replace"]["dc/tex.pak"], "/private/candidate/tex.pak")
        with self.assertRaisesRegex(v.CandidateError, "output already exists"):
            v.build_policy(policy, output, ["r101"])
        self.assertEqual(v.sha((output / "tex.pak").read_bytes()),
                         report["candidate_tex_pak_sha256"])

    def test_invalid_policy_has_no_partial_output(self):
        policy = self.root / "policy.json"
        bad = copy.deepcopy(self.policy)
        bad["rooms"][0]["materials"][0]["class"] = "soft"
        policy.write_text(json.dumps(bad))
        output = self.root / "must-not-exist"
        with self.assertRaises(v.CandidateError):
            v.build_policy(policy, output, ["r101"])
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
