#!/usr/bin/env python3
"""Synthetic qualification and atomic full-record adoption checks."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import ps2_enemy_ch22 as ch22
import ps2_enemy_ch23 as common


def row(room, hp=1000, alive=1):
    return (alive, 0x13, 2, 14, 0x10203040, hp, 0x73, 2,
            -1234, 5678, -90, -32768, 32767, -1, room, -1337, b"abcd")


def pack(rows, endian):
    import struct
    return b"".join(struct.pack(endian + common.FORMAT, *item) for item in rows)


def fixture():
    zero = common.decode(bytes(32), "<")[0]
    before = [zero] * 256
    for index, room in enumerate(sorted(ch22.TARGETS[1])):
        before[index] = row(room)
    before[255] = row(0x111)
    after = list(before)
    for index in range(153, 160):
        after[index] = row(0x11c, hp=1000 + index, alive=0)
    after[0] = row(0x111, hp=1500, alive=0)
    return before, after


class Audit(unittest.TestCase):
    def test_full_zero_population_and_held_coverage(self):
        before, after = fixture()
        audit, baseline, replacements, needs = ch22.audit_list(1, pack(before, ">"), pack(after, "<"))
        self.assertEqual(audit["selected_rows"], 13)
        self.assertEqual(audit["changed_rows"], 8)
        self.assertEqual(needs["r11c"]["activation_indices"], list(range(153, 160)))
        self.assertEqual(needs["r11c"]["populated_indices"], list(range(153, 160)))
        self.assertEqual(needs["r111"]["activation_indices"], [0])
        self.assertEqual(dict(replacements)[153], common.as_le(after[153]))
        self.assertEqual(dict(baseline)[153], bytes(32))

    def test_population_refuses_nonzero_slot_wrong_room_id_alive_or_index(self):
        for kind in ("old_nonzero", "room", "id", "alive", "index"):
            before, after = fixture()
            if kind == "old_nonzero":
                changed = list(before[153]); changed[-1] = b"abcd"; before[153] = tuple(changed)
            elif kind == "index":
                after[152], after[153] = after[153], after[152]
            else:
                changed = list(after[153]); changed[{"room":14, "id":1, "alive":0}[kind]] = {"room":0x111, "id":0x12, "alive":1}[kind]
                after[153] = tuple(changed)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError, "room identity"):
                ch22.audit_list(1, pack(before, ">"), pack(after, "<"))

    def test_existing_room_move_and_missing_target_refused(self):
        before, after = fixture()
        after[0], after[1] = after[1], after[0]
        with self.assertRaisesRegex(ValueError, "room identity"):
            ch22.audit_list(1, pack(before, ">"), pack(after, "<"))
        before, after = [row(0x100)], [row(0x100)]
        with self.assertRaisesRegex(ValueError, "missing target"):
            ch22.audit_list(0, pack(before, ">"), pack(after, "<"))

    def test_opening_flags_health_and_reserved_are_full_record_changes(self):
        before = [row(0x100), row(0x104), row(0x101)]
        after = copy.deepcopy(before)
        value = list(after[0]); value[4] ^= 0xA0000000; value[5] = 1300; value[-1] = b"wxyz"; after[0] = tuple(value)
        after[-1] = row(0x101, hp=2)
        audit, baseline, replacements, needs = ch22.audit_list(0, pack(before, ">"), pack(after, "<"))
        self.assertEqual(audit["selected_rows"], 2)
        self.assertEqual(audit["records"][0]["changed_fields"], ["flag", "hp", "reserved"])
        self.assertEqual(needs, {"r100": {"changed_indices":[0], "activation_indices":[], "populated_indices":[]}})
        self.assertEqual(replacements, [(0, common.as_le(after[0]))])


class Qualification(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.needs = {"r11a":{"changed_indices":[22], "activation_indices":[22], "populated_indices":[]},
                      "r11c":{"changed_indices":[153], "activation_indices":[153], "populated_indices":[153]}}
        self.manifest = {"schema":ch22.QUAL_SCHEMA, "rooms":{}}
        for room, requirement in self.needs.items():
            entry = {"status":"source-qualified", **requirement}
            for key in ("source_rel", "implementation", "evidence"):
                path = self.path / (room + "-" + key); path.write_text(room + key)
                record = {"path":str(path), "sha256":common.sha256(path.read_bytes())}
                entry[key] = [record] if key == "evidence" else record
            self.manifest["rooms"][room] = entry

    def test_independent_room_rels_and_coverage(self):
        result = ch22.qualify(self.manifest, self.needs)
        self.assertNotEqual(result["rooms"]["r11a"]["source_rel"], result["rooms"]["r11c"]["source_rel"])
        for key in ("changed_indices", "activation_indices", "populated_indices"):
            manifest = copy.deepcopy(self.manifest); manifest["rooms"]["r11c"][key] = []
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "coverage"):
                ch22.qualify(manifest, self.needs)

    def test_absent_pending_or_stale_proofs_refused(self):
        with self.assertRaises(ValueError): ch22.qualify(None, self.needs)
        for key in ("status", "implementation", "source_rel", "evidence"):
            manifest = copy.deepcopy(self.manifest)
            manifest["rooms"]["r11c"][key] = {"status":"pending", "implementation":None, "source_rel":None, "evidence":[]}[key]
            with self.subTest(key=key), self.assertRaises(ValueError): ch22.qualify(manifest, self.needs)
        Path(self.manifest["rooms"]["r11a"]["source_rel"]["path"]).write_text("changed")
        with self.assertRaisesRegex(ValueError, "sha256 mismatch"): ch22.qualify(self.manifest, self.needs)

    def test_refused_header_preserves_prior_artifact(self):
        gc, ps2 = self.path/"gc", self.path/"ps2"; gc.mkdir(); ps2.mkdir()
        for no, rooms in ch22.TARGETS.items():
            rows = [row(room) for room in sorted(rooms)]
            (gc/f"emleon{no:02d}.esl").write_bytes(pack(rows, ">"))
            (ps2/f"ps2_emleon{no:02d}.esl").write_bytes(pack(rows, "<"))
        header = self.path/"data.inc"; header.write_text("prior")
        rc = ch22.main(["--gc-dir",str(gc),"--ps2-dir",str(ps2),"--audit-json",str(self.path/"audit.json"),"--header",str(header)])
        self.assertEqual(rc,2); self.assertEqual(header.read_text(),"prior")


@unittest.skipUnless(shutil.which("g++"), "host g++ unavailable")
class Runtime(unittest.TestCase):
    def test_full_copy_zero_population_and_atomic_refusal(self):
        before, after = fixture()
        audit, baseline, replacements, needs = ch22.audit_list(1, pack(before, ">"), pack(after, "<"))
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp); (path/"ps2_enemy_ch22_data.inc").write_text(ch22.emit_header([(1,baseline,replacements)]))
            values=lambda data: ",".join(str(x) for x in data)
            source = """
#include "ps2_enemy_ch22.h"
#include <assert.h>
#include <string.h>
static const unsigned char baseline[] = {BASELINE};
static const unsigned char expected[] = {EXPECTED};
int main() {
 unsigned char data[8192], snapshot[8192];
 memcpy(data,baseline,sizeof(data));
 assert(re4dc_ps2EnemyListCh22(1,data,sizeof(data))==1);
 assert(memcmp(data,expected,sizeof(data))==0);
 memcpy(snapshot,data,sizeof(data));
 assert(re4dc_ps2EnemyListCh22(1,data,sizeof(data))==-2);
 assert(memcmp(data,snapshot,sizeof(data))==0);
 for(unsigned byte=0;byte<32;++byte) {
  memcpy(data,baseline,sizeof(data)); data[255*32+byte]^=1;
  memcpy(snapshot,data,sizeof(data));
  assert(re4dc_ps2EnemyListCh22(1,data,sizeof(data))==-2);
  assert(memcmp(data,snapshot,sizeof(data))==0);
 }
 memcpy(data,baseline,sizeof(data));
 assert(re4dc_ps2EnemyListCh22(1,data,8191)==-1);
 assert(memcmp(data,baseline,sizeof(data))==0);
 assert(re4dc_ps2EnemyListCh22(1,0,8192)==-1);
 assert(re4dc_ps2EnemyListCh22(99,0,0)==0);
}
""".replace("BASELINE",values(pack(before,"<"))).replace("EXPECTED",values(pack(after,"<")))
            (path/"test.cpp").write_text(source)
            platform=Path(__file__).resolve().parents[5]/"port/dreamcast/game/platform"
            command=["g++","-std=c++98","-Wall","-Wextra","-Werror","-DRE4DC_ROUTE_CH22=1","-DRE4DC_PS2_ENEMY_RULES=1",
                     "-I",str(path),"-I",str(platform/"include"),str(platform/"ps2_enemy_ch22.cpp"),str(path/"test.cpp"),"-o",str(path/"test")]
            result=subprocess.run(command,capture_output=True,text=True); self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(path/"test")],capture_output=True,text=True); self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn("verified=13 replaced=8 full32=1",result.stdout)

    def test_either_guard_off_needs_no_private_data(self):
        platform=Path(__file__).resolve().parents[5]/"port/dreamcast/game/platform"
        with tempfile.TemporaryDirectory() as temp:
            for route,rules in ((0,0),(1,0),(0,1)):
                result=subprocess.run(["g++","-std=c++98","-Wall","-Wextra","-Werror",f"-DRE4DC_ROUTE_CH22={route}",f"-DRE4DC_PS2_ENEMY_RULES={rules}",
                                       "-I",str(platform/"include"),"-c",str(platform/"ps2_enemy_ch22.cpp"),"-o",str(Path(temp)/"off.o")],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,result.stderr)

if __name__ == "__main__": unittest.main()
