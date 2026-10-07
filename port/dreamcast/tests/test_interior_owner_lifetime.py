"""The owner cull mark cannot survive a model identity change within one Trans."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "game/coarse_actor_owner_ganado.inc"

def fixture(source):
    def block(token):
        start = source.index(token)
        brace = source.index("{", start)
        depth, end = 1, brace + 1
        while depth:
            depth += (source[end] == "{") - (source[end] == "}")
            end += 1
        return source[start:end]
    return '''#include <cassert>
    #include <climits>
    #define RE4DC_PS2_INTERIOR_OWNER 1
    struct ModelData {};
    struct cModelInfo { cModelInfo* pList; const ModelData* pData; };
    struct cModel { unsigned serial,id; void* pList; cModelInfo* pModelInfo; };
    '''+block('struct InvisRec')+';\nconstexpr unsigned kInvisRecs=48;\nInvisRec invis_rec[kInvisRecs];\nunsigned invis_rec_next,invis_gen;\n'+ '\n'.join(block(x) for x in ['InvisRec* invis_find(', 'bool invis_same(', 'void invis_capture(', 'extern "C" int re4dc_invis_owner_marked('])+'''
    int main() {
     const unsigned generations[] = {0u, 5u, UINT_MAX};
     for (unsigned generation : generations) {
     ModelData data[2]; cModelInfo info{nullptr,&data[0]}; int parts[2];
     cModel m{11,0x10,parts,&info}; invis_gen=generation;
     auto* r=invis_find(&m,true); invis_capture(*r,&m); r->outcome=1;
     assert(!re4dc_invis_owner_marked(&m));
     r->pc_gen=invis_gen; assert(re4dc_invis_owner_marked(&m));
     // The transaction observes a replacement owner at the same address and recaptures its identity.
     ++m.serial; assert(!invis_same(*r,&m)); invis_capture(*r,&m); r->outcome=1;
     assert(!re4dc_invis_owner_marked(&m));
     r->pc_gen=invis_gen; info.pData=&data[1];
     assert(!invis_same(*r,&m)); invis_capture(*r,&m); r->outcome=1;
     assert(!re4dc_invis_owner_marked(&m));
     r->pc_gen=invis_gen; m.pList=parts+1;
     assert(!invis_same(*r,&m)); invis_capture(*r,&m); r->outcome=1;
     assert(!re4dc_invis_owner_marked(&m));
     r->pc_gen=invis_gen; ++invis_gen; assert(!re4dc_invis_owner_marked(&m));
     }
     return 0;
    }
    '''


@unittest.skipUnless(shutil.which("g++"), "g++ is required")
class OwnerCullLifetime(unittest.TestCase):
    def execute(self, source):
        with tempfile.TemporaryDirectory() as tmp:
            cpp, exe = Path(tmp) / "lifetime.cpp", Path(tmp) / "lifetime"
            cpp.write_text(fixture(source))
            subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            str(cpp), "-o", str(exe)], check=True, capture_output=True)
            return subprocess.run([str(exe)], capture_output=True, text=True)

    def test_replacement_identity_discards_mark(self):
        result = self.execute(SOURCE.read_text())
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_negative_control_detects_inherited_mark(self):
        source = SOURCE.read_text()
        invalidation = "    r.pc_gen = invis_gen - 1u;"
        self.assertEqual(source.count(invalidation), 1)
        result = self.execute(source.replace(invalidation, ""))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("re4dc_invis_owner_marked", result.stderr)


if __name__ == "__main__":
    unittest.main()
