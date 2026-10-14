#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cmath>
#include <cstring>
#include <limits>
#include <fstream>
#include <vector>
#include "native_model.h"
#include "room/instanced_mesh.hpp"
#include "room/mesh_fastpath.hpp"
#include "actual_uv_types.inc"
#define RE4DC_INV255 /255.f
float vp_host_xmtrx[4][4]={{1,0,0,0},{0,1,0,0},{0,0,1,0},{0,0,0,1}};
struct SlowEmitter {
 const Re4dcModelPart& p;struct {float u_scale=1,v_scale=1;}packet{};
 float mvq[12]{1,0,0,0,0,1,0,0,0,0,1,0};
 static void project(float&,float&,float&,const void*){}
 #include "actual_emitter_uv.inc"
};
struct FastBorrow:SlowEmitter {
 const re4dc::room::MeshPart& part;const std::uint32_t* lut;
 unsigned limit=400,alpha=0xff000000U;bool vertex_alpha=false;
 float near=.1f,far=10000;
 pvr_vertex_t storage[400]{},*dst=storage,*cache=nullptr;std::uint8_t* outcodes=nullptr;
 re4dc::vp::Constants k{};
 #include "actual_mesh_borrow.inc"
};
unsigned checks=0;
void check(bool value){++checks;if(!value){std::fprintf(stderr,"UV check %u failed\n",checks);std::abort();}}
std::uint32_t bits(float f){std::uint32_t value;std::memcpy(&value,&f,4);return value;}
int main(int argc,char** argv){
 assert(argc==2);std::ifstream input(argv[1],std::ios::binary);std::vector<unsigned char> bytes{std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>()};
 re4dc::room::MeshPackage package;check(package.adopt(bytes.data(),bytes.size(),true,true));
 const auto& part=package.parts()[0];std::uint32_t lut[512];re4dc::vp::build_lut(lut);
 const unsigned q[6]={0,1,67,12345,32768,65535};
 for(float phase:{0.f,.000173f,.25f,.75f,1.25f,1.99999f,-.375f})for(float native:{.5f,1.f,1.1f}) {
  Re4dcModelPart view{};view.uv_offset[0]=phase;view.uv_offset[1]=-phase;
  SlowEmitter slow{view};slow.packet.u_scale=native;slow.packet.v_scale=native;
  FastBorrow fast{{view},part,lut};fast.packet=slow.packet;check(fast.borrow());
  check(fast.k.off_u==phase&&fast.k.off_v==-phase);check(fast.k.su==part.uv_scale[0]&&fast.k.bu==part.uv_bias[0]);
  re4dc::room::CompactBatch batch{};for(unsigned axis=0;axis<2;++axis){batch.uv_scale[axis]=part.uv_scale[axis];batch.uv_bias[axis]=part.uv_bias[axis];}
  for(unsigned u:q)for(unsigned v:q){
   re4dc::render::StaticCorner corner{1,2,3,std::uint16_t(u),std::uint16_t(v),0xffffffffU};re4dc::render::RenderVertex clipped;
   slow.clip_vertex(corner,batch,clipped);
   re4dc::vp::Vertex12 source{1,2,3,std::uint16_t(u),std::uint16_t(v),0xffff};pvr_vertex_t result{},folded{};
   re4dc::vp::transform_c<re4dc::vp::kChecksNone>(&source,1,&result,nullptr,fast.k);
   re4dc::vp::transform_c<re4dc::vp::kChecksNone,true>(&source,1,&folded,nullptr,fast.k);
   check(bits(result.u)==bits(clipped.u)&&bits(result.v)==bits(clipped.v));
   const float expectedU=((part.uv_bias[0]+float(u)*part.uv_scale[0])+phase)*native;
   const float expectedV=((part.uv_bias[1]+float(v)*part.uv_scale[1])-phase)*native;
   check(bits(clipped.u)==bits(expectedU)&&bits(clipped.v)==bits(expectedV));
   const float tolerance=4*std::numeric_limits<float>::epsilon()*std::fmax(1.f,std::fmax(std::fabs(expectedU),std::fabs(expectedV)));
   check(std::fabs(folded.u-expectedU)<=tolerance&&std::fabs(folded.v-expectedV)<=tolerance);
  }
 }
 // Failed cache borrow preserves the per-corner path and does not consume UV.
 Re4dcModelPart view{};view.uv_offset[0]=.75f;FastBorrow tooSmall{{view},part,lut};tooSmall.limit=10;check(!tooSmall.borrow());check(view.uv_offset[0]==.75f);
 FastBorrow noLut{{view},part,nullptr};check(!noLut.borrow());check(view.uv_offset[0]==.75f);
 std::printf("r11f actual Emitter/borrow/portable fast UV: %u checks PASS (host arithmetic, no SH4/pixels)\n",checks);
}
