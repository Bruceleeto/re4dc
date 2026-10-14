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
    generated=maximums+'\n'+function(trans,'void SetPrimBuffPtr()')+'\n'+function(trans,'void* GetPrimBuff(int size)')+'\n'+ot_bodies+'\n'+light+'\n'+function(trans,'void ModelTrans(cModel* m)')+'\n'
    common_body=scoped(trans,'void commonModelTrans(cModel* m, cModelInfo* info, Mtx viewMat, int flag)')
    # Retain the complete production body, including real foot-shadow/model
    # postludes. A final observer counts only completed bodies; no source code
    # branch or field read is replaced by a synthetic postlude.
    common_body=common_body[:-1]+'    ++callback_postludes; if(after_model)after_model(m);\n}'
    generated+=common_body+'\n'
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
D59_CAMERA_SERVICE = r'''
// Host GX state services around the exact production source-camera getter.
float d59_projection[7],d59_viewport[6];
void d59_camera_reset(){
 const float p[7]={0,1,0,1,0,-.01f,-1.01f},v[6]={0,0,640,448,0,1};
 std::memcpy(d59_projection,p,sizeof(p));std::memcpy(d59_viewport,v,sizeof(v));
}
void GXGetProjectionv(float* p){++camera_calls;std::memcpy(p,d59_projection,sizeof(d59_projection));}
void GXGetViewportv(float* v){std::memcpy(v,d59_viewport,sizeof(d59_viewport));}
'''
D59_CONTEXT_TESTS = r'''
// D59 additions are host stimulus and assertions only. Production owner,
// callback, camera-getter, pass and presentation bodies remain unmodified.
unsigned d59_cases=0,d59_mutation=0,d59_mutated=0,d59_item_calls=0;
unsigned d59_emits_at_mutation=0,d59_binds_at_mutation=0;
Mtx d59_expected_view{};
float d59_expected_projection[7],d59_expected_viewport[6];
void d59_begin(unsigned mode=1){
 d59_request_baseline=mode!=0;reset();
 if(mode==2)global.System_flg|=0x400;
}
void d59_mutate(){
 ++d59_mutated;d59_emits_at_mutation=geometry_emits;d59_binds_at_mutation=bind_calls;
 if(d59_mutation==0)global.Status_flg[1]|=2;
 else if(d59_mutation==1)subscreen=true;
 else if(d59_mutation==2)global.Status_flg[2]&=~0x04000000u;
 else assert(false);
}
void d59_mutate_first(cModel*){after_model=nullptr;check(r11fFrame.withheld&&!r11fFrame.started&&r11fFrame.seen==1);d59_mutate();}
void d59_mutate_anchor(cModel* m){if(m==objects){after_model=nullptr;check(r11fFrame.started&&r11fNativeReceipt.completed==1);d59_mutate();}}
void d59_change_camera(cModel*){
 after_model=nullptr;check(camera_calls==0&&r11fFrame.withheld&&!r11fFrame.started);
 std::memcpy(global.Cam.v_mat,d59_expected_view,sizeof(Mtx));
 std::memcpy(d59_projection,d59_expected_projection,sizeof(d59_projection));
 std::memcpy(d59_viewport,d59_expected_viewport,sizeof(d59_viewport));
}
void d59_item_probe(void*){
 ++d59_item_calls;check(g_NowExecOtType==0x14);
 check(std::memcmp(global.Cam.v_mat,itemCamera.v_mat,sizeof(Mtx))==0);
 check(r11fFrame.started&&r11fFrame.seen==r11fFrame.count&&r11fExactEntry(objects)<0);
}
void d59_switch_window(cModel*){
 after_model=nullptr;check(r11fFrame.withheld&&!r11fFrame.started);
 if(d59_mutation==0){global.System_flg|=0x400;global.Status_flg[2]&=~0x04000000u;}
 else {global.Status_flg[2]|=0x04000000;global.System_flg&=~0x400u;}
 check(r11fContext());
}
void d59_context_tests(){
 const unsigned before=checks;
 // The recorded request-only case, the original held window, and both bits.
 for(unsigned mode=0;mode<3;++mode)for(bool packet:{false,true}){
  d59_begin(mode);force_packet=packet;re4dc_r11f_prepare(frame);
  check(r11fFrame.planned&&r11fFrame.count==251);
  if(mode==1)check(frame==2463&&global.Frame_cnt==3601&&global.System_flg==0x840&&global.Status_flg[1]==0x205&&global.Status_flg[2]==0x04000000);
  Render();finish_and_present();
  check(shown==1&&discarded==0&&aborts==0&&source_geometry==0&&callback_postludes==251);
  check(r11fNativeReceipt.attempted==7&&r11fNativeReceipt.completed==7&&r11fFrame.source_done);
  for(unsigned pass=0;pass<3;++pass)check(r11fNativeReceipt.result[pass]==1&&!r11fNativeReceipt.fallback[pass]&&!r11fNativeReceipt.aborts[pass]);
  ++d59_cases;
 }
 // Scene-hidden and actual swapped states are independent; neither source
 // window, old context exclusions, and null global all refuse before payloads.
 for(unsigned mode=0;mode<16;++mode){
  d59_begin();
  switch(mode){
   case 0:global.Status_flg[2]=0;break;
   case 1:global.Status_flg[1]|=2;break;
   case 2:subscreen=true;break;
   case 3:global.Status_flg[1]|=2;subscreen=true;break;
   case 4:global.room_no=0x20;break;
   case 5:global.Rno0=4;break;
   case 6:global.System_flg|=0x100000;break;
   case 7:global.Status_flg[1]|=0x100;break;
   case 8:re4dc_coarse_image=1;break;
   case 9:re4dc_pace_skipping=1;break;
   case 10:movie=true;break;
   case 11:pG=nullptr;break;
   case 12:global.System_flg|=0x400;global.Status_flg[2]=0;global.Status_flg[1]|=2;break;
   case 13:global.System_flg|=0x400;global.Status_flg[1]|=2;break;
   case 14:global.System_flg|=0x400;global.Status_flg[2]=0;subscreen=true;break;
   case 15:global.System_flg|=0x400;subscreen=true;break;
  }
  re4dc_r11f_prepare(frame);
  check(!r11fFrame.planned&&!r11fFrame.withheld&&!r11fFrame.failed&&!r11fNativeClaimed());
  check(camera_calls==0&&geometry_emits==0&&aborts==0);pG=&global;++d59_cases;
 }
 // Camera/GX state changes after prepare but before the anchor must be read
 // from the current source state, while the later item camera stays in0x14.
 d59_begin();d59_item_calls=0;std::memset(itemCamera.v_mat,0,sizeof(Mtx));itemCamera.v_mat[0][0]=9;itemCamera.v_mat[0][3]=99;
 std::memset(d59_expected_view,0,sizeof(Mtx));d59_expected_view[0][0]=d59_expected_view[1][1]=d59_expected_view[2][2]=1;
 d59_expected_view[0][3]=.25f;d59_expected_view[1][3]=-.5f;
 const float projection[7]={0,1.25f,.03f,1.5f,.07f,-.01f,-1.01f},viewport[6]={7,11,600,420,0,1};
 std::memcpy(d59_expected_projection,projection,sizeof(projection));std::memcpy(d59_expected_viewport,viewport,sizeof(viewport));
 check(AddOtDirect(0x14,&global,reinterpret_cast<void(*)()>(d59_item_probe),0,0,nullptr,0)!=0xffff);
 re4dc_r11f_prepare(frame);check(r11fFrame.planned&&camera_calls==0);after_model=d59_change_camera;
 Render();finish_and_present();
 check(shown==1&&aborts==0&&d59_item_calls==1&&camera_calls==1);
 check(std::memcmp(ps2w.view,d59_expected_view,sizeof(Mtx))==0&&std::memcmp(global.Cam.v_mat,d59_expected_view,sizeof(Mtx))==0);
 check(std::memcmp(ps2w.projection,d59_expected_projection,sizeof(ps2w.projection))==0&&std::memcmp(ps2w.viewport,d59_expected_viewport,sizeof(ps2w.viewport))==0);
 ++d59_cases;
 // A captured scenery pointer cannot forge its callback role through0x14.
 d59_begin();re4dc_r11f_prepare(frame);
 {R11fRenderScope scope;manual_callback(0);auto e=r11fFrame.entries[1];
  re4dc_source_world_callback_begin(0x14,e.node,reinterpret_cast<void(*)(void*)>(ModelRender),e.model,e.kind);
  ModelRender(e.model);re4dc_source_world_callback_end();}
 finish_and_present();check(r11fFrame.failed&&shown==0&&discarded==1&&aborts==1&&source_geometry==0);++d59_cases;
 // Revoke after the first withheld callback, after OP's anchor, between OP/PT,
 // between PT/TR, before presentation, or during the scene-finish wait.
 // PT is completed through its actual native entry for the between-pass case.
 for(bool packet:{false,true})for(unsigned mutation=0;mutation<3;++mutation)for(unsigned where=0;where<6;++where){
  d59_begin();force_packet=packet;d59_mutation=mutation;d59_mutated=0;re4dc_r11f_prepare(frame);
  if(where==0)after_model=d59_mutate_first;
  if(where==1)after_model=d59_mutate_anchor;
  Render();
  if(where<2){check(d59_mutated==1);finish_and_present();}
  else if(where==2){check(r11fNativeReceipt.completed==1);d59_mutate();finish_and_present();}
  else if(where==3){check(re4dc_ps2_mesh_draw(1,25000)==1&&r11fNativeReceipt.completed==3);d59_mutate();finish_and_present();}
  else {re4dc_model_finish_source_draws();check(r11fNativeReceipt.completed==7&&r11fFrame.source_done);
   if(where==4)d59_mutate();else finish_yield=d59_mutate;
   stream_close(true);}
  check(d59_mutated==1&&r11fFrame.failed&&aborts==1&&shown==0&&discarded==1&&source_geometry==0&&!direct_open);
  check(geometry_emits==d59_emits_at_mutation&&bind_calls==d59_binds_at_mutation);
  if(where==0)check(r11fFrame.seen==1&&!r11fFrame.started&&camera_calls==0&&r11fNativeReceipt.completed==0&&callback_postludes==1);
  if(where==1)check(r11fFrame.seen==r11fFrame.anchor+1&&r11fFrame.started&&r11fNativeReceipt.completed==1);
  if(where==2)check(r11fNativeReceipt.completed==1);
  if(where==3)check(r11fNativeReceipt.completed==3);
  check(sourceWorldCallbackDepth==0&&sourceWorldModelDepth==0);
  // Restoring flags and preparing the same native image cannot revive an abort.
  global.System_flg=0x840;global.Status_flg[1]=0x205;global.Status_flg[2]=0x04000000;subscreen=false;
  re4dc_r11f_prepare(frame);check(r11fFrame.failed&&!re4dc_r11f_present(frame,1,0));++d59_cases;
 }
 // Eligibility follows the OR expression; switching which valid window stays
 // active does not manufacture a lifetime change while all ownership is current.
 for(unsigned direction=0;direction<2;++direction){
  d59_begin(direction==0?1:0);d59_mutation=direction;re4dc_r11f_prepare(frame);after_model=d59_switch_window;
  Render();finish_and_present();check(shown==1&&aborts==0&&r11fNativeReceipt.completed==7);++d59_cases;
 }
 d59_request_baseline=false;
 std::printf("D59 actual context: %u cases, %u checks PASS (real owner/camera/OT/pass/present; synthetic constructors/GPU)\n",d59_cases,checks-before);
}
'''

def context_fixture(out,fixture):
    """Keep original assertions and add request-context/control-flow coverage.

    Only host-service stubs and the test driver change in generated output.
    Extracted production bodies are shared unchanged with the original suite.
    """
    original=fixture.read_text();text=original
    def replace(old,new):
        nonlocal text
        assert text.count(old)==1,(old,text.count(old))
        text=text.replace(old,new)
    camera_file=ROOT/'port/dreamcast/game/coarse.cpp'
    getter=scoped(camera_file.read_text(),'extern "C" int re4dc_coarse_source_camera(')
    old_getter=scoped(text,'extern "C" int re4dc_coarse_source_camera(')
    replace(old_getter,D59_CAMERA_SERVICE+'\n'+getter)
    replace('void reset(bool register_all=true){','bool d59_request_baseline=false;\nvoid reset(bool register_all=true){')
    first=' global=Global{};pG=&global;room_generation=10;frame=200;room_live=archive_live=true;movie=subscreen=false;re4dc_coarse_image=re4dc_pace_skipping=0;'
    replace(first,first+'\n d59_camera_reset();\n if(d59_request_baseline){global.System_flg=0x840;global.Status_flg[1]=0x205;global.Status_flg[2]=0x04000000;global.Frame_cnt=3601;frame=2463;}')
    old_main=scoped(text,'int main(int argc,char** argv)')
    load=' assert(argc==5);source_file=read_file(argv[1]);mesh_file=read_file(argv[2]);side_file=read_file(argv[3]);ids_file=read_file(argv[4]);'
    assert old_main.count(load)==1
    legacy=old_main.replace('int main(int argc,char** argv)','void d45_original_tests()',1).replace(load,'',1)
    assert legacy.replace('void d45_original_tests()','int main(int argc,char** argv)',1).replace('{\n','{\n'+load,1)==old_main
    main='int main(int argc,char** argv){\n'+load+"\n for(bool request:{false,true}){d59_request_baseline=request;checks=0;d45_original_tests();std::printf(\"D59 retained suite baseline=%s checks=%u PASS\\n\",request?\"request\":\"held\",checks); }\n d59_context_tests();\n}\n"
    replace(old_main,D59_CONTEXT_TESTS+'\n'+legacy+'\n'+main)
    generated=out/'source_world_r11f_context.cpp';generated.write_text(text)
    (out/'context-fixture-adaptation.json').write_text(json.dumps({'original_fixture':str(fixture),'original_sha256':hashlib.sha256(original.encode()).hexdigest(),'production_camera':str(camera_file),'production_camera_getter_sha256':hashlib.sha256(getter.encode()).hexdigest(),'original_assertion_body_preserved':legacy.replace('void d45_original_tests()','int main(int argc,char** argv)',1).replace('{\n','{\n'+load,1)==old_main,'scope':'Original assertions run in held and recorded request baselines. Generated host camera stub replaced by exact production getter plus GX services; original source/constructor/GPU qualifications retained.'},indent=2)+'\n')
    return generated,camera_file

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--source-archive',required=True);ap.add_argument('--native-dir',required=True);ap.add_argument('--encv',type=int,choices=[0,1],default=0);ap.add_argument('--header-cache',type=int,choices=[0,1,2],default=2);ap.add_argument('--ui-handles',type=int,choices=[0,1],default=0);ap.add_argument('--mesh-textures',type=int,choices=[0,1],default=0);ap.add_argument('--crowd-invis-skip',type=int,choices=[0,2],default=0);args=ap.parse_args()
    required=[(Path(args.source_archive),'ec398ab13d70c828dd807490b9a3e81ae62c0471f623798892b08e8bc9baae6d'),(Path(args.native_dir)/'ps2-world.re4mesh','ef5e84ae75aab525e0b7919118212d1d4f52192ef982ba832b5204dbad5c2fab'),(Path(args.native_dir)/'ps2-world.r4pw','a2cd504ea130027f9ba76539d2fec3368a15542fbc346dda0fab4b5e65fa7e85'),(Path(args.native_dir)/'ps2-world.ids','dfd12bfbceb090b94fcf963eceb5f66d988d4bf81fb0d5113a1733d66dfd14e8')]
    for p,h in required:
        assert hashlib.sha256(p.read_bytes()).hexdigest()==h,str(p)
    saved=os.environ.get('RE4DC_TEST_ARTIFACT_DIR')
    if saved:Path(saved).mkdir(parents=True,exist_ok=False)
    with contextlib.nullcontext(saved) if saved else tempfile.TemporaryDirectory(prefix='re4-r11f-') as path:
        out=Path(path);pins=inputs(out,args.encv);exe=out/'test';original_fixture=Path(__file__).with_name('fixtures')/'source_world_r11f.cpp'
        fixture,camera_file=context_fixture(out,original_fixture);pins.extend([original_fixture,original_fixture.parent/'source_world_allocator.inc',camera_file])
        argv=[os.environ.get('CXX','g++'),'-std=c++17',*FLAGS,'-Wall','-Wextra','-fpermissive','-Wno-misleading-indentation','-DRE4DC_ENCV='+str(args.encv),'-DRE4DC_CROWD_INVIS_SKIP='+str(args.crowd_invis_skip),'-DRE4DC_PS2_WORLD_HDR_CACHE='+str(args.header_cache),'-DRE4DC_UI_HANDLES='+str(args.ui_handles),'-DRE4DC_MESH_TEXTURES='+str(args.mesh_textures),'-I',str(INC),'-I',str(ROOT/'port/dreamcast'),'-I',str(out),'-I',str(original_fixture.parent),str(fixture),*link_flags(out),'-o',str(exe)]
        (out/'compiler-command.json').write_text(json.dumps(argv,indent=2))
        compile=subprocess.run(argv,capture_output=True,text=True);(out/'compiler-output.txt').write_text(compile.stdout+compile.stderr)
        if compile.returncode:print(compile.stdout+compile.stderr)
        compile.check_returncode()
        run=subprocess.run([str(exe),*[str(p) for p,h in required]],capture_output=True,text=True);(out/'run-output.txt').write_text(run.stdout+run.stderr);print(run.stdout+run.stderr,end='');run.check_returncode()
        pins.append(Path(__file__))
        manifest={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(pins))};manifest.update({str(p):h for p,h in required});(out/'production-inputs.json').write_text(json.dumps(manifest,indent=2))
