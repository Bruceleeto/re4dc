"""Actual native-actor light preparation/evaluation, including Leon's per-part marker."""
from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT=Path(__file__).resolve().parents[3]

@unittest.skipUnless(shutil.which('g++'), 'host compiler required')
class LeonSourceLight(unittest.TestCase):
 def test_per_part_normals_reach_both_exact_evaluators(self):
  with tempfile.TemporaryDirectory() as temporary:
   t=Path(temporary);(t/'dc').mkdir()
   (t/'dc/pvr.h').write_text('#pragma once\n#include <cstddef>\n#include <cstdint>\nstruct pvr_vertex_t{std::uint32_t flags;float x,y,z,u,v;std::uint32_t argb,oargb;};\nstruct pvr_poly_hdr_t{std::uint32_t words[8];};\n#define PVR_CMD_VERTEX 0xe0000000U\n#define PVR_CMD_VERTEX_EOL 0xf0000000U\nint pvr_prim(const void*,std::size_t);\n')
   (t/'fixture.cpp').write_text(r'''
#include <cassert>
#include <cstdio>
#include <limits>
#include "ACTOR_IMPLEMENTATION"
// Independent double-precision inverse, then transpose; does not reuse the runtime cofactor formula.
void inverse_transpose(const float* m,float* out) {
 double a[3][6]{};
 for(unsigned r=0;r<3;++r)for(unsigned c=0;c<3;++c){a[r][c]=m[4*r+c];a[r][c+3]=r==c;}
 for(unsigned c=0;c<3;++c){
  unsigned pivot=c;for(unsigned r=c+1;r<3;++r)if(std::abs(a[r][c])>std::abs(a[pivot][c]))pivot=r;
  assert(std::abs(a[pivot][c])>1e-12);for(unsigned k=0;k<6;++k)std::swap(a[c][k],a[pivot][k]);
  const double d=a[c][c];for(double& v:a[c])v/=d;
  for(unsigned r=0;r<3;++r)if(r!=c){const double f=a[r][c];for(unsigned k=0;k<6;++k)a[r][k]-=f*a[c][k];}
 }
 for(unsigned r=0;r<3;++r){for(unsigned c=0;c<3;++c)out[4*r+c]=float(a[c][r+3]);out[4*r+3]=0;}
}
void check(unsigned lamps,bool marked,bool skin,bool tinted,const float* matrix) {
 SourceLighting s{};s.enable=1;s.mask=(1u<<lamps)-1;s.attenuation=0;
 s.ambient[0]=12;s.ambient[1]=18;s.ambient[2]=25;
 s.normal_matrix[0]=s.normal_matrix[5]=s.normal_matrix[10]=1;
 if(marked)s.normal_matrix[3]=1.0e30f;
 if(tinted){s.material[0]=128;s.material[1]=192;s.material[2]=64;s.tev_scale=2;}
 for(unsigned i=0;i<lamps;++i){s.lights[i].position[0]=1000+float(i)*10;s.lights[i].position[1]=50;
  s.lights[i].color[0]=28;s.lights[i].color[1]=17;s.lights[i].color[2]=9;}
 const SourceLighting original=s;
 short positions[2][4]={{0,0,0,0},{2,3,1,0}};
 signed char normals[2][4]={{0,0,64,0},{0,64,0,0}};
 // Palette columns: rotate local normal +Y into +Z and local +Z into -Y.
 float palette[12]={1,0,0,0,0,1,0,-1,0,0,0,0};
 Frame f{};f.mode=skin?kSkin:kRigid;f.positions=(u8*)positions;f.normals=(u8*)normals;
 f.position_stride=8;f.normal_stride=4;f.position_count=f.normal_count=2;f.small_normals=true;f.nq=1.f/64;
 f.palette=palette;f.palette_entries=1;
 Re4dcModelPart p{};p.lighting=&s;std::memcpy(p.modelview,matrix,48);
 Lights lights{};const float center[3]={0,0,0};const bool fast=build_lights(p,f,center,lights);
 if(lamps>3 || tinted)assert(!fast);
 if(fast){
  float basis[12];std::memcpy(basis,s.normal_matrix,sizeof(basis));
#if RE4DC_LEON_SOURCE_LIGHT
  if(marked)inverse_transpose(matrix,basis);
#endif
  for(unsigned j=0;j<lamps;++j){
   float v[3]={s.lights[j].position[0]-matrix[3],s.lights[j].position[1]-matrix[7],s.lights[j].position[2]-matrix[11]};
   const float inv=1/std::sqrt(v[0]*v[0]+v[1]*v[1]+v[2]*v[2]);for(float& x:v)x*=inv;
   for(unsigned c=0;c<3;++c){float expected=0;for(unsigned r=0;r<3;++r)expected+=basis[4*r+c]*v[r]*f.nq;
    assert(std::abs(lights.dir[j][c]-expected)<1e-7f);}
  }
 }
 lights.prepared=re4dc::render::prepare_actor_lights(s);
 const u16 packed[]={0,0,0,1,1,0};Records records{packed,3,0,false};
 pvr_vertex_t vertices[2]{};Part part{p,f,{nullptr,nullptr},{}};part.cache.v=vertices;part.alpha=0x71000000;
 pass_lights_exact(part,lights,records,2);
 float nmat[12];std::memcpy(nmat,s.normal_matrix,sizeof(nmat));
#if RE4DC_LEON_SOURCE_LIGHT
 if(marked)inverse_transpose(matrix,nmat);
#endif
 for(unsigned i=0;i<2;++i){
  float xyz[3]={float(positions[i][0]),float(positions[i][1]),float(positions[i][2])};
  float nn[3]={normals[i][0]/64.f,normals[i][1]/64.f,normals[i][2]/64.f};
  if(skin){for(float* v:{xyz,nn}){const float y=v[1],z=v[2];v[1]=-z;v[2]=y;}}
  float w[3]{},normal[3]{};
  for(unsigned r=0;r<3;++r){w[r]=matrix[4*r+3];for(unsigned c=0;c<3;++c){w[r]+=matrix[4*r+c]*xyz[c];normal[r]+=nmat[4*r+c]*nn[c];}}
  float rgb[3];const u8 white[4]={255,255,255,255};
  re4dc::render::evaluate_prepared_source_lighting(w[0],w[1],w[2],normal[0],normal[1],normal[2],s,lights.prepared,white,rgb);
  const u32 expected=part.alpha | channel(rgb[0]*255)<<16 | channel(rgb[1]*255)<<8 | channel(rgb[2]*255);
  if(vertices[i].argb!=expected){std::fprintf(stderr,"lamps=%u marked=%u skin=%u tint=%u vertex=%u have=%08x expected=%08x\n",lamps,marked,skin,tinted,i,vertices[i].argb,expected);assert(false);}
 }
 assert(!std::memcmp(&s,&original,sizeof(s)));
}
#if RE4DC_LEON_SOURCE_LIGHT
void check_unusable_basis() {
 const float bases[][12]={{0},{1,0,0,0,0,1,0,0,0,0,std::numeric_limits<float>::infinity(),0},
  {1,0,0,0,0,1,0,0,0,0,std::numeric_limits<float>::quiet_NaN(),0}};
 for(auto& matrix:bases){
  float result[12];assert(!leon_part_normal(matrix,result));
  SourceLighting s{};s.enable=1;s.mask=15;s.normal_matrix[3]=1.0e30f;s.material[0]=80;s.material[1]=100;s.material[2]=120;s.tev_scale=2;
  const SourceLighting original=s;Re4dcModelPart p{};p.lighting=&s;std::memcpy(p.modelview,matrix,48);
  Frame frame{};Lights lights{};const float center[3]={0,0,0};assert(!build_lights(p,frame,center,lights));
  pvr_vertex_t vertex{};Part part{p,frame,{nullptr,nullptr},{}};part.cache.v=&vertex;part.alpha=0x71000000;
  const u16 packed[3]={};Records records{packed,3,0,false};
  pass_lights_exact(part,lights,records,1);assert(vertex.argb==0x71a0c8f0);
  assert(!std::memcmp(&s,&original,sizeof(s)));
 }
}
#endif
int main(){
#if RE4DC_LEON_SOURCE_LIGHT
 check_unusable_basis();
#endif
 const float matrices[][12]={{0,0,1,0,0,1,0,0,-1,0,0,0},{0,0,2,9,0,.5f,0,-8,-1,0,0,7},{1,.25f,0,0,0,1,.5f,0,0,0,2,0},{-1,0,0,0,0,1,0,0,0,0,1,0}};
 for(auto& m:matrices)for(bool marked:{false,true})for(bool skin:{false,true})for(bool tinted:{false,true})for(unsigned lamps:{3u,4u,8u})check(lamps,marked,skin,tinted,m);
 std::puts("PASS actual actor exact lighting: 3/4/8 lamps, rigid/skinned, rotated/scaled/sheared roles, colored material, source immutable");
}
'''.replace('ACTOR_IMPLEMENTATION',str(ROOT/'port/dreamcast/game/platform/native_actor_fast.cpp')))
   for enabled in (0,1):
    for exact in (0,1):
     executable=t/f'check-{enabled}-{exact}'
     cmd=['g++','-std=c++20','-O2','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-DRE4DC_LEON_SOURCE_LIGHT='+str(enabled),'-DRE4DC_ACTOR_EXACT_FAST='+str(exact),'-I'+str(t),'-I'+str(ROOT/'port/dreamcast/game/platform/include'),str(t/'fixture.cpp'),str(ROOT/'port/dreamcast/room/source_lighting.cpp'),'-o',str(executable)]
     compile=subprocess.run(cmd,capture_output=True,text=True)
     self.assertEqual(compile.returncode,0,compile.stderr)
     result=subprocess.run([str(executable)],capture_output=True,text=True)
     self.assertEqual(result.returncode,0,result.stderr)
     print(f'LEON_SOURCE_LIGHT={enabled} ACTOR_EXACT_FAST={exact}: {result.stdout.strip()}')
@unittest.skipUnless(shutil.which('make'), 'make required')
class LeonLightKnobs(unittest.TestCase):
 def test_unsupported_lean_acquisition_is_rejected(self):
  with tempfile.TemporaryDirectory() as temporary:
   makefile=Path(temporary)/'Makefile'
   makefile.write_text('OBJDIR := obj\ninclude '+str(ROOT/'port/dreamcast/game/crowd.mk')+'\nall:\n\t@echo parsed\n')
   for light,pipe in ((0,0),(0,1),(1,0),(1,1)):
    result=subprocess.run(['make','-f',str(makefile),'--dry-run','--no-print-directory','all','ACTOR_TRANSACTION=1',
      'LEON_SOURCE_LIGHT='+str(light),'LEON_NATIVE_PIPE='+str(pipe)],capture_output=True,text=True)
    if light and pipe:
     self.assertNotEqual(result.returncode,0)
     self.assertIn('LEON_SOURCE_LIGHT=1 needs LEON_NATIVE_PIPE=0',result.stderr)
    else:self.assertEqual(result.returncode,0,result.stderr)

if __name__=='__main__':unittest.main()