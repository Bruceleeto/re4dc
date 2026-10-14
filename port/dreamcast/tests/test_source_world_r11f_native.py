#!/usr/bin/env python3
"""D45 actual Emitter UV methods, MeshDraw::borrow and portable fast kernel.
This verifies host arithmetic only, not SH4 assembly, GPU packets or pixels.
"""
from pathlib import Path
import argparse,contextlib,hashlib,json,os,subprocess,tempfile
from test_source_world_r11f import scoped
from test_source_world_retained import FLAGS
ROOT=Path(__file__).resolve().parents[3]
INC=ROOT/'port/dreamcast/game/platform/include'
def generate(out):
    out=Path(out);(out/'dc').mkdir();(out/'kos').mkdir()
    (out/'kos/fs.h').write_text("#pragma once\nusing file_t=int;constexpr int FILEHND_INVALID=-1;\n")
    (out/'dc/pvr.h').write_text("#pragma once\n#include <cstdint>\nstruct pvr_vertex_t { std::uint32_t flags;float x,y,z,u,v;std::uint32_t argb,oargb; };\nconstexpr unsigned PVR_CMD_VERTEX=0xe0000000U,PVR_CMD_VERTEX_EOL=0xf0000000U;\n")
    source=(ROOT/'port/dreamcast/game/platform/native_static.cpp').read_text()
    geo=(ROOT/'port/dreamcast/room/pvr_geometry.hpp').read_text();prep=(ROOT/'port/dreamcast/room/static_room_prepare.hpp').read_text()
    structs='namespace re4dc::render {\n'+scoped(geo,'struct ProjectedVertex {')+';\n'+scoped(geo,'struct RenderVertex {')+';\n'+scoped(prep,'struct StaticCorner {')+';\n}\n'
    (out/'actual_uv_types.inc').write_text(structs)
    emitter='\n'.join(scoped(source,marker) for marker in ('float u(float value)const','float v(float value)const','void clip_vertex('))
    (out/'actual_emitter_uv.inc').write_text(emitter+'\n')
    mesh=source[source.index('struct MeshDraw :'):]
    (out/'actual_mesh_borrow.inc').write_text(scoped(mesh,'bool borrow(){')+'\n')
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--mesh',required=True);args=ap.parse_args()
    mesh=Path(args.mesh);expected='ef5e84ae75aab525e0b7919118212d1d4f52192ef982ba832b5204dbad5c2fab'
    assert hashlib.sha256(mesh.read_bytes()).hexdigest()==expected
    saved=os.environ.get('RE4DC_TEST_ARTIFACT_DIR')
    if saved:Path(saved).mkdir(parents=True,exist_ok=False)
    with contextlib.nullcontext(saved) if saved else tempfile.TemporaryDirectory(prefix='r11f-uv-') as path:
        out=Path(path);generate(out);fixture=Path(__file__).with_name('fixtures')/'source_world_r11f_native.cpp';exe=out/'test'
        cmd=[os.environ.get('CXX','g++'),'-std=c++17',*FLAGS,'-Wall','-Wextra','-Werror','-I',str(out),'-I',str(INC),'-I',str(ROOT/'port/dreamcast'),str(fixture),'-o',str(exe)]
        (out/'compiler-command.json').write_text(json.dumps(cmd,indent=2));run=subprocess.run(cmd,capture_output=True,text=True)
        (out/'compiler-output.txt').write_text(run.stdout+run.stderr)
        if run.returncode:print(run.stdout+run.stderr)
        run.check_returncode();run=subprocess.run([str(exe),str(mesh)],capture_output=True,text=True)
        (out/'run-output.txt').write_text(run.stdout+run.stderr);print(run.stdout+run.stderr,end='');run.check_returncode()
        pins=[Path(__file__),fixture,ROOT/'port/dreamcast/game/platform/native_static.cpp',ROOT/'port/dreamcast/room/mesh_fastpath.hpp',ROOT/'port/dreamcast/room/instanced_mesh.hpp',ROOT/'port/dreamcast/room/pvr_geometry.hpp',ROOT/'port/dreamcast/room/static_room_prepare.hpp',mesh]
        (out/'production-inputs.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in pins},indent=2))
