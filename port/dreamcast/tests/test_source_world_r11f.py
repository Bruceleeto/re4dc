#!/usr/bin/env python3
"""D45 actual source callbacks, readers, pass loop and presentation guards.
Private qualified files are inputs, never copied into the source repository.
GPU, source constructors and file services are instrumented host services.
"""
from pathlib import Path
import argparse,contextlib,hashlib,json,os,re,subprocess,tempfile
from test_source_world_retained import generate,link_flags,function,FLAGS
ROOT=Path(__file__).resolve().parents[3]
INC=ROOT/'port/dreamcast/game/platform/include'
def scoped(text,marker):
    start=text.index(marker);brace=text.index('{',start);depth=1;end=brace+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
def inputs(out,encv):
    out=Path(out);generate(out)
    (out/"kos").mkdir(exist_ok=True);(out/"kos/fs.h").write_text("#pragma once\nusing file_t=int;constexpr int FILEHND_INVALID=-1;\n")
    backing=(ROOT/'port/dreamcast/game/parts_bridge.cpp').read_text()
    pool=backing[backing.index('template<class T> struct alignas(32) Chunk'):backing.index('static_assert(sizeof(Chunk')]
    (out/'source_world_actual_pools.inc').write_text(pool+'\n'+ '\n'.join(scoped(backing,m) for m in ('template<class T> bool sparse','template<class T> Pool<T>* pool','template<class T> T* work_at')))
    (out/'tpl.h').write_text((ROOT/'include/tpl.h').read_text().replace('#include "types.h"',''))
    model=(ROOT/'include/model.h').read_text();scroll=(ROOT/'include/scroll.h').read_text();trans=(ROOT/'src/game/trans.cpp').read_text();ot=(ROOT/'src/game/trans_ot.cpp').read_text();sub=(ROOT/'src/game/main_sub.cpp').read_text();ui=(ROOT/'port/dreamcast/game/platform/native_ui.cpp').read_text();static=(ROOT/'port/dreamcast/game/platform/native_static.cpp').read_text();native=(ROOT/'port/dreamcast/game/platform/native_ps2_world.cpp').read_text()
    data='\n'.join(scoped(model,'struct '+name+' {')+';' for name in ('ModelPart','ModelDataHead','ModelData'))
    data+='\n'+'\n'.join(scoped(scroll,kind+' '+name+' {')+';' for kind,name in [('struct','SmdWork'),('class','cSmd'),('struct','SmxWork'),('class','cSmx')])
    data=data.replace('SmdWork work[1]','SmdWork work[251]')
    (out/'source_world_actual_data.inc').write_text(data)
    common=trans[trans.index('#if RE4DC_PS2_WORLD_R11F_OWNER ||'):trans.index('\n#include "em.h"')]
    (out/'source_world_actual_callback.inc').write_text(common)
    uv=trans[trans.index('#define UV_WRAP_HI'):trans.index('// For every model info')]
    tex=(ROOT/'include/trans.h').read_text();uv+=scoped(tex,'struct ModelTexInfo')+';\n#define MODEL_TEX(info) ((ModelTexInfo*) &(info)->flagsDC)\n'
    uv+='void actual_source_uv(cModelInfo* info) { auto* t=MODEL_TEX(info);'+scoped(trans,'if (!(pG->Stop_flg & 0x08000000)')+'}\n'
    (out/'source_world_actual_uv.inc').write_text(uv)
    ot_bodies='\n'.join(function(ot,m) for m in ('static inline void ISet','static inline OtWork* otWork','void InitOt()','void ClearOt()','void clearOtWork','OtData* MakeOtData','int AddOtWorldPosRadius','int AddOtModelPosRadius','extern "C" int AddOtDirect','int ExecOt','void DeleteOtData'))
    maximums=re.search(r'static int Ot_max_tbl\[OT_MAX\] = \{.*?\};',ot,re.S).group(0)
    light=trans[trans.index('#define LIGHT_POS'):trans.index('// Registers a visible model')]
    marker='void ModelRender(cModel* m)\n#endif';body=function(trans,marker).replace(marker,'void ModelRender(cModel* m)',1)
    if encv:
        body=body.replace('void ModelRender(cModel* m)','static void ModelRenderBody(cModel* m)',1)
        wrap=trans[trans.index('#define ENCV_RENDER_WRAP'):trans.index('extern "C" {',trans.index('#define ENCV_RENDER_WRAP'))]
        entries='\n'.join(x for x in trans.splitlines() if x.startswith('ENCV_RENDER_WRAP(re4dc_'))
        body+='\n'+wrap+'\nextern "C" {\n'+entries+'\n}\n'+scoped(trans,'void ModelRender(cModel* m)\n{')+'\n'
    hook=next(x for x in trans.splitlines() if 'if(!flag && sourceWorldR11fDraw(m)!=0)' in x)
    generated=maximums+'\n'+function(trans,'void SetPrimBuffPtr()')+'\n'+function(trans,'void* GetPrimBuff(int size)')+'\n'+ot_bodies+'\n'+light+'\n'+function(trans,'void ModelTrans(cModel* m)')+'\n'
    generated+='void commonModelTrans(cModel* m,cModelInfo* info,Mtx,int flag){\n'+hook+'\n if(info)++source_geometry; ++callback_postludes; if(after_model)after_model(m); }\n'
    generated+='static const GXColor col64={0x40,0x40,0x40,0x40};\n'+body+'\n'+function(sub,'void SetNoScissor()')+'\n'+function(sub,'void SetScissorState()')+'\n'+function(trans,'void Render()')+'\n'
    (out/'source_world_actual_registration.inc').write_text(generated)
    sg=(ROOT/'src/game/scroll.cpp').read_text();(out/'source_world_actual_smx.inc').write_text(function(sg,'void SmxSetFlag(')+'\n'+function(sg,'static void NativeStoreSourceColor(')+'\n'+function(sg,'void smxInit(cObj* obj, SmxWork* w)'))
    ui_bind='\n'.join(scoped(ui,m) for m in ('extern "C" int re4dc_model_packet_begin(', 'extern "C" int re4dc_model_direct_begin(', 'extern "C" int re4dc_ps2_world_direct_begin('))
    (out/'source_world_actual_ui_bind.inc').write_text(ui_bind+'\n')
    constants=sorted(set(re.findall(r'\bPVR_[A-Z0-9_]+',ui_bind))-{'PVR_LIST_OP_POLY','PVR_LIST_PT_POLY','PVR_LIST_TR_POLY','PVR_TA_INPUT'})
    (out/'source_world_host_pvr_constants.inc').write_text('\n'.join('constexpr unsigned '+key+'='+str(i+1)+';' for i,key in enumerate(constants))+'\n')
    (out/'source_world_actual_emitter_bind.inc').write_text(scoped(static,'void end_direct(){')+'\n'+scoped(static,'bool bind(){')+'\n')
    (out/'source_world_actual_native_pass.inc').write_text(function(static,'int ps2_pass(unsigned pass,float zfar)'))
    (out/'source_world_actual_native_draw.inc').write_text(function(static,'extern "C" int re4dc_ps2_mesh_draw(')+'\n'+function(native,'extern "C" int re4dc_ps2_world_source_draw()')+'\n'+function(native,'extern "C" int re4dc_ps2_world_pending()')+'\n'+function(native,'extern "C" void re4dc_ps2_world_flush()'))
    finish_scope=scoped(ui,'struct R11fSourceFinishScope')+';\n'
    (out/'source_world_actual_ui.inc').write_text(function(ui,'extern "C" int re4dc_r11f_op_window()')+'\n'+scoped(ui,'extern "C" unsigned re4dc_r11f_packet_bytes()')+'\n'+finish_scope+function(ui,'extern "C" int re4dc_ps2_world_before_owned_tr(')+'\n'+function(ui,'extern "C" void re4dc_model_finish_source_draws()')+'\n'+function(ui,'void stream_close(bool present)'))
    lifecycle='\n'.join(function(static,m) for m in ('std::uint32_t ps2_crc32(', 'void r11fPackageAdvance()','bool ps2_movie_current()','void ps2_movie_unpublish()','bool ps2_movie_reload()'))
    (out/'source_world_actual_movie.inc').write_text(lifecycle)
    return [ROOT/'src/game/trans.cpp',ROOT/'src/game/trans_ot.cpp',ROOT/'src/game/scroll.cpp',ROOT/'src/game/main_sub.cpp',ROOT/'include/model.h',ROOT/'include/scroll.h',ROOT/'include/trans.h',ROOT/'port/dreamcast/game/platform/native_static.cpp',ROOT/'port/dreamcast/game/platform/native_ps2_world.cpp',ROOT/'port/dreamcast/game/platform/native_ui.cpp',ROOT/'port/dreamcast/room/instanced_mesh.hpp',*INC.glob('*source_world*')]
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source-archive',required=True);ap.add_argument('--native-dir',required=True);ap.add_argument('--encv',type=int,choices=[0,1],default=0);ap.add_argument('--header-cache',type=int,choices=[0,1,2],default=2);ap.add_argument('--ui-handles',type=int,choices=[0,1],default=0);ap.add_argument('--mesh-textures',type=int,choices=[0,1],default=0);args=ap.parse_args()
    required=[(Path(args.source_archive),'ec398ab13d70c828dd807490b9a3e81ae62c0471f623798892b08e8bc9baae6d'),(Path(args.native_dir)/'ps2-world.re4mesh','ef5e84ae75aab525e0b7919118212d1d4f52192ef982ba832b5204dbad5c2fab'),(Path(args.native_dir)/'ps2-world.r4pw','a2cd504ea130027f9ba76539d2fec3368a15542fbc346dda0fab4b5e65fa7e85'),(Path(args.native_dir)/'ps2-world.ids','dfd12bfbceb090b94fcf963eceb5f66d988d4bf81fb0d5113a1733d66dfd14e8')]
    for p,h in required:
        assert hashlib.sha256(p.read_bytes()).hexdigest()==h,str(p)
    saved=os.environ.get('RE4DC_TEST_ARTIFACT_DIR')
    if saved:Path(saved).mkdir(parents=True,exist_ok=False)
    with contextlib.nullcontext(saved) if saved else tempfile.TemporaryDirectory(prefix='re4-r11f-') as path:
        out=Path(path);pins=inputs(out,args.encv);exe=out/'test';fixture=Path(__file__).with_name('fixtures')/'source_world_r11f.cpp'
        argv=[os.environ.get('CXX','g++'),'-std=c++17',*FLAGS,'-Wall','-Wextra','-fpermissive','-Wno-misleading-indentation','-DRE4DC_ENCV='+str(args.encv),'-DRE4DC_PS2_WORLD_HDR_CACHE='+str(args.header_cache),'-DRE4DC_UI_HANDLES='+str(args.ui_handles),'-DRE4DC_MESH_TEXTURES='+str(args.mesh_textures),'-I',str(INC),'-I',str(ROOT/'port/dreamcast'),'-I',str(out),str(fixture),*link_flags(out),'-o',str(exe)]
        (out/'compiler-command.json').write_text(json.dumps(argv,indent=2))
        compile=subprocess.run(argv,capture_output=True,text=True);(out/'compiler-output.txt').write_text(compile.stdout+compile.stderr)
        if compile.returncode:print(compile.stdout+compile.stderr)
        compile.check_returncode()
        run=subprocess.run([str(exe),*[str(p) for p,h in required]],capture_output=True,text=True);(out/'run-output.txt').write_text(run.stdout+run.stderr);print(run.stdout+run.stderr,end='');run.check_returncode()
        pins.extend([fixture,Path(__file__)])
        manifest={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(pins))};manifest.update({str(p):h for p,h in required});(out/'production-inputs.json').write_text(json.dumps(manifest,indent=2))
