"""Render an in-place converted part again after its static eligibility changes.
Uses the actual actor converter and model dispatcher; host packets are compared.
"""
from pathlib import Path
import os,shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
@unittest.skipUnless(shutil.which('g++'),'host compiler required')
class ModelStreamDispatch(unittest.TestCase):
 def test_converted_stream_keeps_its_decoder(self):
  with tempfile.TemporaryDirectory() as tmp:
   t=Path(tmp);(t/'dc').mkdir()
   (t/'dc/pvr.h').write_text('#pragma once\n#include <cstddef>\n#include <cstdint>\nstruct pvr_vertex_t{std::uint32_t flags;float x,y,z,u,v;std::uint32_t argb,oargb;};\nstruct pvr_poly_hdr_t{std::uint32_t words[8];};\n#define PVR_CMD_VERTEX 0xe0000000U\n#define PVR_CMD_VERTEX_EOL 0xf0000000U\nint pvr_prim(const void*,std::size_t);\n')
   (t/'fixture.cpp').write_text(r'''
#include "native_actor.hpp"
#include "native_draw_plan.hpp"
#include "pvr_geometry.hpp"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
static pvr_vertex_t packet[1400];
static std::vector<pvr_vertex_t> output;
static unsigned status=99,lookups=0,materializes=0,buffer_reads=0;
static Re4dcActorSource source{};
static const unsigned char *materialized_positions=nullptr,*materialized_normals=nullptr;
extern "C" int re4dc_model_packet_reserve(const Re4dcModelPart*,Re4dcModelPacket* out){*out={packet,1400,1,1};return 1;}
extern "C" int re4dc_model_packet_begin(const Re4dcModelPart* p,Re4dcModelPacket* out){return re4dc_model_packet_reserve(p,out);}
extern "C" void re4dc_model_packet_commit(unsigned n){output.insert(output.end(),packet,packet+n);}
extern "C" void re4dc_model_packet_abort(){assert(false);}
extern "C" int re4dc_model_packet_streaming(){return 1;}
extern "C" void re4dc_model_result(unsigned why,unsigned,unsigned){status=why;}
extern "C" int re4dc_model_defer_part(const Re4dcModelPart*){return 0;}
extern "C" void re4dc_model_next_header_pcw(unsigned,unsigned){}
extern "C" int re4dc_actor_model_source(const void*,Re4dcActorSource* out){*out=source;return 1;}
extern "C" int re4dc_actor_model_prelit(const void*,const void*){return 0;}
extern "C" int re4dc_actor_model_class(const void*,const void*){return 0;}
extern "C" int re4dc_skin_materialize(const void*,const float*){++materializes;return 1;}
extern "C" int re4dc_actor_model_buffers(Re4dcModelPart* p){++buffer_reads;p->positions=materialized_positions;p->normals=materialized_normals;return p->positions&&p->normals;}
extern "C" int re4dc_model_diagnostic_enabled(){return 1;}
extern "C" void re4dc_log(const char*,...){}
extern "C" const re4dc::render::NativeDrawPlan* re4dc_model_acquire_draw_plan(const Re4dcModelPart* p,int* invalid){
 ++lookups;
 // The old plan remains resident after conversion. No packed data may reach
 // this GX-only owner, whether a positive or a negative plan is cached.
 if(p->stream[0]==0xfe){std::fputs("REGRESSION: converted stream reached GX plan\n",stderr);std::exit(86);}
 *invalid=0;return nullptr;
}
extern "C" const re4dc::render::DrawPlanBounds* re4dc_model_acquired_bounds(){return nullptr;}
extern "C" const re4dc::render::DrawLocalPlan* re4dc_model_acquired_locals(){return nullptr;}
extern "C" void re4dc_model_release_draw_plan(){}
extern "C" void* re4dc_model_static_lighting_storage(unsigned* n){*n=0;return nullptr;}
extern "C" void* re4dc_model_retained_storage(unsigned* n){*n=0;return nullptr;}
alignas(32) unsigned char prep[12288];
extern "C" void* re4dc_model_preparation_storage(unsigned* n){*n=sizeof(prep);return prep;}
int pvr_prim(const void*,std::size_t){assert(false);return -1;}
int main(){
 short positions[3][4]={{-2,-2,0,0},{2,-2,0,0},{0,2,0,0}};
 signed char normals[3][4]={{0,0,64,0},{0,0,64,0},{0,0,64,0}};
 unsigned short uv[3][2]={{0,0},{32768,0},{0,32768}};
 std::vector<unsigned char> stream{0x90,0,30};
 for(unsigned i=0;i<30;++i)for(unsigned j=0;j<3;++j){stream.push_back(0);stream.push_back(i%3);}
 stream.resize(192);const auto gx=stream;
 std::vector<unsigned char> workspace(128*1024);
 re4dc::render::SourceLighting light{};
 Re4dcModelPart p{};p.model=&p;p.info=&p;p.part=stream.data();
 p.positions=(unsigned char*)positions;p.normals=(unsigned char*)normals;p.uv=(unsigned char*)uv;
 p.position_count=p.normal_count=3;p.position_stride=8;p.normal_stride=4;p.normal_shift=6;
 p.stream=stream.data();p.stream_bytes=stream.size();p.lighting=&light;
 p.modelview[0]=p.modelview[5]=p.modelview[10]=1;p.modelview[11]=-10;
 p.projection[1]=p.projection[3]=1;p.projection[5]=-1.f/99;p.projection[6]=-100.f/99;
 p.viewport[2]=640;p.viewport[3]=480;p.viewport[5]=1;p.image.width=p.image.height=32;
 source={(unsigned char*)positions,(unsigned char*)normals,3,3,1,1};
 re4dc_actor_lod(0,0);
 auto draw=[&](){status=99;output.clear();re4dc_model_preparation_frame();re4dc_actor_frame(workspace.data(),workspace.size());re4dc_model_submit(&p);assert(status==0&&!output.empty());};
 p.static_geometry=1;draw();assert(stream==gx&&lookups==1);
 p.static_geometry=0;draw();assert(stream[0]==0xfe&&stream[1]==3&&lookups==1);
 const auto converted=stream;const auto expected=output;
 // Same mechanism as H2 frame 1585: another part already materialized the
 // info, while this view still holds null lazy arrays. The first actor
 // qualification declines; the refreshed arrays must return to that decoder.
 short packed_pos[3][3]={{-2,-2,0},{2,-2,0},{0,2,0}};
 signed char packed_normal[3][3]={{0,0,64},{0,0,64},{0,0,64}};
 materialized_positions=(unsigned char*)packed_pos;materialized_normals=(unsigned char*)packed_normal;
 float palette[12]={1,0,0,0,0,1,0,0,0,0,1,0};
 p.positions=p.normals=nullptr;p.position_stride=6;p.normal_stride=3;
 assert(re4dc_actor_skin_register(17,p.info,nullptr,palette,1));
 re4dc_actor_materialize(&p);assert(materializes==1);
 const auto declined_before=re4dc_actor_stats()->declined;
 draw();assert(lookups==1&&stream==converted&&materializes==1&&buffer_reads==1);
 assert(re4dc_actor_stats()->declined==declined_before+1);
 assert(output.size()==expected.size()&&!std::memcmp(output.data(),expected.data(),output.size()*sizeof(pvr_vertex_t)));
 p.positions=materialized_positions;p.normals=materialized_normals;

 for(unsigned i=0;i<6;++i){p.static_geometry=i%2==0;draw();assert(lookups==1&&stream==converted);assert(output.size()==expected.size());assert(!std::memcmp(output.data(),expected.data(),output.size()*sizeof(pvr_vertex_t)));}
 // Both opaque and deferred-capable material views keep the packed owner.
 p.blend=1;p.static_geometry=1;draw();assert(lookups==1&&stream==converted);
 std::puts("PASS converted part retained decoder and exact packets after lazy materialization and static transitions");
}
''')
   game=ROOT/'port/dreamcast/game';room=ROOT/'port/dreamcast/room';exe=t/'check'
   mode=int(os.environ.get('RE4DC_TEST_STREAM_FIX','1'))
   cmd=['g++','-std=c++20','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-DRE4DC_ACTOR_TEST=1','-DRE4DC_D349_RENDERER_STACK=1','-DRE4DC_NATIVE_ACTOR=1','-DRE4DC_NATIVE_ACTOR_FAST=1','-DRE4DC_NATIVE_ACTOR_SKIN=1','-DRE4DC_NATIVE_ACTOR_SKIN_LAZY=1','-DRE4DC_MODEL_DRAW_PLANS=1','-DRE4DC_MODEL_ROOM_STRIPS=1','-DRE4DC_MODEL_STREAM_FIX='+str(mode),'-I'+str(t),'-I'+str(game/'platform/include'),'-I'+str(room),str(t/'fixture.cpp'),str(game/'platform/native_model.cpp'),str(game/'platform/native_actor_fast.cpp'),str(room/'pvr_geometry.cpp'),str(room/'source_lighting.cpp'),'-o',str(exe)]
   subprocess.run(cmd,check=True)
   p=subprocess.run([str(exe)],capture_output=True,text=True)
   if mode==0:self.assertEqual(p.returncode,86,p.stderr);self.assertIn('converted stream reached GX plan',p.stderr)
   else:self.assertEqual(p.returncode,0,p.stderr);print(p.stdout.strip())
if __name__=='__main__':unittest.main()
