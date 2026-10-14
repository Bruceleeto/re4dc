#!/usr/bin/env python3
"""Synthetic tests only: no extracted game assets are stored here."""
import copy
import importlib.util
import json
from pathlib import Path
import struct
import shutil
import subprocess
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location("ch23", Path(__file__).with_name("ps2_enemy_ch23.py"))
ch23 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ch23)


def row(room=0x10F, hp=1000, alive=1):
    return (alive, 0x17, 2, 14, 0x10203040, hp, 0x73, 2,
            -1234, 5678, -90, -32768, 32767, -1, room, -1337, b"\x91\x82\x73\x64")


def pack(rows, endian):
    return b"".join(struct.pack(endian + ch23.FORMAT, *item) for item in rows)


class EnemyRecords(unittest.TestCase):
    def test_full_layout_and_endianness(self):
        data = pack([row()], ">")
        self.assertEqual(len(data), 32)
        converted = ch23.as_le(ch23.decode(data, ">")[0])
        expected = bytearray(data)
        for offset, size in ((4, 4), (8, 2), *((n, 2) for n in range(12, 28, 2))):
            expected[offset:offset + size] = reversed(data[offset:offset + size])
        self.assertEqual(converted, expected)
        self.assertEqual(converted[10:12], b"\x73\x02")
        self.assertEqual(converted[28:32], b"\x91\x82\x73\x64")

    def test_all_fields_including_hp_and_reserved(self):
        rows = [row(room) for room in sorted(ch23.TARGETS[1])]
        # Change one selected row in every semantic field except room identity.
        changed = list(rows[0])
        for index in range(len(changed)):
            if index == ch23.ROOM_INDEX:
                continue
            if index == 16:
                changed[index] = b"abcd"
            elif index in (11, 12):
                changed[index] += 1 if index == 11 else -1
            else:
                changed[index] += 1
        new = [tuple(changed)] + rows[1:]
        audit, baseline, replacements, held = ch23.audit_list(1, pack(rows, ">"), pack(new, "<"))
        self.assertEqual(audit["changed_rows"], 1)
        self.assertEqual(set(audit["records"][0]["changed_fields"]), set(ch23.FIELD_NAMES) - {"room"})
        self.assertEqual(replacements, [(0, pack(new[:1], "<"))])
        self.assertEqual(len(baseline), 5)
        self.assertEqual(held, {"r10f": [0]})

    def test_zero_id_and_outside_rooms_are_preserved(self):
        selected = list(row(0x11F))
        selected[1] = 0
        rows = [row(room) for room in sorted(ch23.TARGETS[1]) if room != 0x11F]
        rows += [tuple(selected), row(0x101)]
        new = list(rows)
        new[-1] = row(0x101, hp=4)
        audit, baseline, replacements, held = ch23.audit_list(1, pack(rows, ">"), pack(new, "<"))
        self.assertEqual(len(baseline), 5)
        self.assertEqual(replacements, [])
        self.assertIn(4, [index for index, data in baseline])
        self.assertEqual(audit["records"][-1]["after"]["id"], 0)
        self.assertEqual(held, {})

    def test_source_alignment_is_required(self):
        rows = [row(room) for room in sorted(ch23.TARGETS[1])]
        with self.assertRaisesRegex(ValueError, "room identity"):
            ch23.audit_list(1, pack(rows, ">"), pack(list(reversed(rows)), "<"))
        with self.assertRaisesRegex(ValueError, "row counts"):
            ch23.audit_list(1, pack(rows, ">"), pack(rows[:-1], "<"))
        with self.assertRaisesRegex(ValueError, "missing target"):
            ch23.audit_list(1, pack(rows[:-1], ">"), pack(rows[:-1], "<"))

    def test_invalid_sizes(self):
        for data in (b"", b"0" * 31, b"0" * 8193, b"0" * 8224):
            with self.assertRaises(ValueError):
                ch23.decode(data, "<")

    def test_unchanged_second_list_needs_no_replacements(self):
        audit, baseline, replacements, held = ch23.audit_list(2, pack([row(0x200)], ">"), pack([row(0x200)], "<"))
        self.assertEqual(audit["changed_rows"], 0)
        header = ch23.emit_header([(2, baseline, replacements)])
        self.assertIn("{2, ps2_enemy_ch23_baseline_2, 1, NULL, 0}", header)


class Qualification(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.rel = self.path / "source.rel"
        self.rel.write_bytes(b"synthetic REL")
        self.impl = self.path / "r10f.cpp"
        self.impl.write_bytes(b"synthetic implementation")
        self.proof = self.path / "proof.json"
        self.proof.write_bytes(b"synthetic callback and area evidence")
        def file(path):
            return {"path": str(path), "sha256": ch23.sha256(path.read_bytes())}
        self.manifest = {"schema": ch23.QUAL_SCHEMA, "source_rel": file(self.rel), "rooms": {
            "r10f": {"status": "source-qualified", "held_indices": [46, 47, 48],
                     "implementation": file(self.impl), "evidence": [file(self.proof)]}}}
        self.held = {"r10f": [46, 47, 48]}

    def test_absent_qualification_refused(self):
        with self.assertRaisesRegex(ValueError, "missing"):
            ch23.qualify(None, self.held, self.rel)

    def test_complete_qualification_accepted(self):
        result = ch23.qualify(self.manifest, self.held, self.rel)
        self.assertEqual(result["rooms"]["r10f"]["held_indices"], [46, 47, 48])

    def test_stale_evidence_refused(self):
        self.proof.write_bytes(b"changed source evidence")
        with self.assertRaisesRegex(ValueError, "sha256 mismatch"):
            ch23.qualify(self.manifest, self.held, self.rel)

    def test_missing_indices_status_implementation_refused(self):
        for key, replacement in (("held_indices", [46, 47]), ("status", "pending"), ("implementation", None), ("evidence", [])):
            manifest = copy.deepcopy(self.manifest)
            manifest["rooms"]["r10f"][key] = replacement
            with self.subTest(key=key), self.assertRaises(ValueError):
                ch23.qualify(manifest, self.held, self.rel)

    def test_refused_header_does_not_replace_previous_artifact(self):
        gc_dir, ps2_dir = self.path / "gc", self.path / "ps2"
        gc_dir.mkdir()
        ps2_dir.mkdir()
        for no, rooms in ch23.TARGETS.items():
            rows = [row(room) for room in sorted(rooms)]
            (gc_dir / f"emleon{no:02d}.esl").write_bytes(pack(rows, ">"))
            (ps2_dir / f"ps2_emleon{no:02d}.esl").write_bytes(pack(rows, "<"))
        header, audit = self.path / "data.inc", self.path / "audit.json"
        header.write_bytes(b"prior artifact")
        result = ch23.main(["--gc-dir", str(gc_dir), "--ps2-dir", str(ps2_dir),
                           "--audit-json", str(audit), "--header", str(header)])
        self.assertEqual(result, 2)
        self.assertEqual(header.read_bytes(), b"prior artifact")
        self.assertFalse(json.loads(audit.read_text())["header_eligible"])


@unittest.skipUnless(shutil.which("g++"), "host g++ unavailable")
class Runtime(unittest.TestCase):
    def test_runtime_full_copy_and_atomic_failures(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            before = [row(room) for room in sorted(ch23.TARGETS[1])] + [row(0x101)]
            after = list(before)
            changed = list(after[0])
            changed[0], changed[3], changed[5], changed[7], changed[10] = 0, 0, 1400, 6, -89
            changed[16] = b"WXYZ"
            after[0] = tuple(changed)
            a, baseline, replacements, held = ch23.audit_list(1, pack(before, ">"), pack(after, "<"))
            b, base2, repl2, h2 = ch23.audit_list(2, pack([row(0x200)], ">"), pack([row(0x200)], "<"))
            (path / "ps2_enemy_ch23_data.inc").write_text(ch23.emit_header([(1, baseline, replacements), (2, base2, repl2)]))
            def values(data):
                return ",".join(str(x) for x in data)
            source = '''
#include "ps2_enemy_ch23.h"
#include <assert.h>
#include <string.h>
static const unsigned char baseline[] = {BASELINE};
static const unsigned char expected[] = {EXPECTED};
static const unsigned char list2[] = {LIST2};
int main() {
    unsigned char data[sizeof(baseline)], snapshot[sizeof(baseline)];
    memcpy(data, baseline, sizeof(data));
    assert(re4dc_ps2EnemyListCh23(1, data, sizeof(data)) == 1);
    assert(memcmp(data, expected, sizeof(data)) == 0);
    // A restored/already-modified list is never accepted as a fresh baseline.
    memcpy(snapshot, data, sizeof(data));
    assert(re4dc_ps2EnemyListCh23(1, data, sizeof(data)) == -2);
    assert(memcmp(data, snapshot, sizeof(data)) == 0);
    // A mismatch at the last selected row cannot allow earlier copies.
    for (unsigned byte = 0; byte < 32; ++byte) {
        memcpy(data, baseline, sizeof(data));
        data[4 * 32 + byte] ^= 1;
        memcpy(snapshot, data, sizeof(data));
        assert(re4dc_ps2EnemyListCh23(1, data, sizeof(data)) == -2);
        assert(memcmp(data, snapshot, sizeof(data)) == 0);
    }
    memcpy(data, baseline, sizeof(data));
    assert(re4dc_ps2EnemyListCh23(1, data, 4 * 32 + 31) == -1);
    assert(memcmp(data, baseline, sizeof(data)) == 0);
    assert(re4dc_ps2EnemyListCh23(1, 0, sizeof(data)) == -1);
    assert(re4dc_ps2EnemyListCh23(0, 0, 0) == 0);
    assert(re4dc_ps2EnemyListCh23(99, 0, 0) == 0);
    memcpy(data, list2, sizeof(list2));
    assert(re4dc_ps2EnemyListCh23(2, data, sizeof(list2)) == 1);
    assert(memcmp(data, list2, sizeof(list2)) == 0);
}
'''.replace("BASELINE", values(pack(before, "<"))).replace("EXPECTED", values(pack(after, "<"))).replace("LIST2", values(pack([row(0x200)], "<")))
            (path / "test.cpp").write_text(source)
            root = Path(__file__).resolve().parents[5]
            platform = root / "port/dreamcast/game/platform"
            command = ["g++", "-std=c++98", "-Wall", "-Wextra", "-Werror",
                       "-DRE4DC_ROUTE_CH23=1", "-DRE4DC_PS2_ENEMY_RULES=1",
                       "-I", str(path), "-I", str(platform / "include"),
                       str(platform / "ps2_enemy_ch23.cpp"), str(path / "test.cpp"),
                       "-o", str(path / "test")]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(path / "test")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("verified=5 replaced=1 full32=1", result.stdout)
            self.assertIn("verified=1 replaced=0 full32=1", result.stdout)

    def test_either_guard_off_needs_no_private_data(self):
        root = Path(__file__).resolve().parents[5]
        platform = root / "port/dreamcast/game/platform"
        with tempfile.TemporaryDirectory() as temp:
            for route, rules in ((0, 0), (1, 0), (0, 1)):
                command = ["g++", "-std=c++98", "-Wall", "-Wextra", "-Werror",
                           f"-DRE4DC_ROUTE_CH23={route}", f"-DRE4DC_PS2_ENEMY_RULES={rules}",
                           "-I", str(platform / "include"), "-c",
                           str(platform / "ps2_enemy_ch23.cpp"), "-o", str(Path(temp) / "off.o")]
                result = subprocess.run(command, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
