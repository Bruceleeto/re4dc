#!/usr/bin/env python3
"""Compile actual source-world readers with adversarial synthetic services."""
from pathlib import Path
import os
import re
import json
import hashlib
import contextlib
import subprocess
import tempfile
from test_source_world_retained import generate,link_flags
ROOT=Path(__file__).resolve().parents[3]
INC=ROOT/'port/dreamcast/game/platform/include'
if __name__=='__main__':
    saved=os.environ.get('RE4DC_TEST_ARTIFACT_DIR')
    if saved:Path(saved).mkdir(parents=True,exist_ok=False)
    with contextlib.nullcontext(saved) if saved else tempfile.TemporaryDirectory(prefix='re4-source-world-') as out:
        exe=Path(out)/'test'
        generate(out)
        # This regression previously used invented3/5 table aliases, masking
        # a real integration bug. Compile the actual enum and require source
        # registration/Render scope agreement at the source boundary.
        header=(ROOT/'include/trans_ot.h').read_text()
        enum=re.search(r'enum OT_TYPE\s*\{.*?\};',header,re.S).group(0)
        maximum=re.search(r'^#define OT_MAX .*$',header,re.M).group(0)
        backing=(ROOT/'port/dreamcast/game/parts_bridge.cpp').read_text()
        def function(text, marker):
            start=text.index(marker);brace=text.index('{',start);depth=1;end=brace+1
            # Recovered functions close at column zero. Counting both arms of
            # #if/#else would count mutually exclusive opening braces twice.
            if '\n' in text[brace:text.index('}',brace)]:
                return text[start:text.index('\n}',brace)+2]
            while depth:
                depth+=(text[end]=='{')-(text[end]=='}');end+=1
            return text[start:end]
        types='\n'.join(function(header,'struct '+name)+';' for name in ('OtData','OtPrim','OtWork'))
        (Path(out)/'source_world_actual_ot.inc').write_text(maximum+'\n'+types+'\n'+enum+'\n')
        pool_structs=backing[backing.index('template<class T> struct alignas(32) Chunk'):backing.index('static_assert(sizeof(Chunk')]
        (Path(out)/'source_world_actual_pools.inc').write_text(pool_structs+'\n'+
            function(backing,'template<class T> bool sparse')+'\n'+
            function(backing,'template<class T> Pool<T>* pool')+'\n'+
            function(backing,'template<class T> T* work_at')+'\n')
        trans=(ROOT/'src/game/trans.cpp').read_text()
        ots=(ROOT/'src/game/trans_ot.cpp').read_text()
        assert 'AddOtDirect(0xB, m, (void (*)()) ModelRender' in trans
        assert 'OtWork* w = otWork(13);' in ots and 'OtWork* w = otWork(17);' in ots
        for name in ['OT_TYPE_EFFECT_VU1','OT_TYPE_COCKPIT','OT_TYPE_AFTER_RENDER','OT_TYPE_DEBUG']:
            assert '{ SourceWorldRenderScope sourceWorldScope; ExecOt('+name+'); }' in trans
        # Execute exact production bodies for registration, linked OT traversal,
        # ModelRender postludes and Render scopes. Geometry/GX services stay
        # synthetic and are explicitly outside this host acceptance boundary.
        ot_bodies='\n'.join(function(ots,marker) for marker in (
            'static inline void ISet','static inline OtWork* otWork','void InitOt()','void ClearOt()','void clearOtWork',
            'OtData* MakeOtData','int AddOtWorldPosRadius','int AddOtModelPosRadius',
            'extern "C" int AddOtDirect','int ExecOt','void DeleteOtData'))
        maximums=re.search(r'static int Ot_max_tbl\[OT_MAX\] = \{.*?\};',ots,re.S).group(0)
        light_macro=trans[trans.index('#define LIGHT_POS'):trans.index('// Registers a visible model')]
        render_marker='void ModelRender(cModel* m)\n#endif'
        model_body=function(trans,render_marker).replace(render_marker,'void ModelRender(cModel* m)',1)
        hook=next(line for line in trans.splitlines() if 'sourceWorldDraw(m)!=0)info=nullptr' in line)
        sub=(ROOT/'src/game/main_sub.cpp').read_text()
        prim_bodies=function(trans,'void SetPrimBuffPtr()')+'\n'+function(trans,'void* GetPrimBuff(int size)')
        generated=maximums+'\n'+prim_bodies+'\n'+ot_bodies+'\n'+light_macro+'\n'+function(trans,'void ModelTrans(cModel* m)')+'\n'
        generated+=('void commonModelTrans(cModel* m,cModelInfo* info,Mtx,int flag) {\n'+hook+
            '\n if(info)++source_geometry; ++callback_postludes; callback_tables.push_back(g_NowExecOtType);'
            ' callback_scissors.push_back(scissor); callback_cameras.push_back(pG->Cam); }\n')
        generated+='static const GXColor col64={0x40,0x40,0x40,0x40};\n'+model_body+'\n'
        generated+=function(sub,'void SetNoScissor()')+'\n'+function(sub,'void SetScissorState()')+'\n'+function(trans,'void Render()')+'\n'
        (Path(out)/'source_world_actual_registration.inc').write_text(generated)
        argv=[os.environ.get('CXX','g++'),'-std=c++17','-O1','-g','-Wall','-Wextra',
            '-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-fno-pie','-no-pie','-fpermissive',
            '-Wno-misleading-indentation','-I',str(INC),'-I',str(out),
            str(Path(__file__).with_name('fixtures')/'source_world_r200.cpp'),*link_flags(out),'-o',str(exe)]
        (Path(out)/'compiler-command.json').write_text(json.dumps(argv,indent=2)+'\n')
        inputs=[ROOT/'src/game/trans.cpp',ROOT/'src/game/trans_ot.cpp',ROOT/'src/game/main_sub.cpp',
            ROOT/'include/trans_ot.h',ROOT/'port/dreamcast/game/parts_bridge.cpp',Path(__file__),
            Path(__file__).with_name('fixtures')/'source_world_r200.cpp']
        inputs+=list(INC.glob('*source_world*'))
        manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(inputs))}
        (Path(out)/'production-inputs.json').write_text(json.dumps(manifest,indent=2)+'\n')
        compiled=subprocess.run(argv,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (Path(out)/'compiler-output.txt').write_text(compiled.stdout)
        if compiled.returncode:print(compiled.stdout)
        compiled.check_returncode()
        run=subprocess.run([str(exe)],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (Path(out)/'run-output.txt').write_text(run.stdout)
        print(run.stdout,end='');run.check_returncode()
