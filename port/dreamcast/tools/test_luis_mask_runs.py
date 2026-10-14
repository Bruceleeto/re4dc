#!/usr/bin/env python3
"""Exercise the extracted masked-run matcher using source-complete plan fixtures.

This tests run/material identity and coverage, not texture appearance or draws.
"""
from pathlib import Path
import subprocess,tempfile
GAME=Path(__file__).resolve().parents[1]/'game'
owner=(GAME/'coarse_actor_owner_registry.inc').read_text()
a=owner.index('bool registry_plain_material(');b=owner.index('\n}',owner.index('bool registry_run_is(',a))+2
utilities=owner[a:b]
a=owner.index('extern "C" int re4dc_registry_runs_match(');b=owner.index('\n}',a)+2
matcher=owner[a:b]
a=owner.index('extern "C" int re4dc_registry_masked(');b=owner.index('\n}',a)+2
masked=owner[a:b]
def structure(path,name):
 s=(GAME/'platform/include'/path).read_text();a=s.index('struct '+name+' {');return s[a:s.index('\n};',a)+3]
source=r'''#include <cstdio>
#include <cstdlib>
#include <cstddef>
#include <initializer_list>
#define RE4DC_NATIVE_MODEL_REGISTRY_PACK 1
#define RE4DC_NMR_MASK 1
constexpr unsigned kRegistryAsset0=47,kRe4dcActorMaterials=3;
namespace re4dc_source {struct ByteSpan{const unsigned char* data;std::size_t size;};}
'''+structure('native_ui.h','Re4dcUiImage')+structure('actor_native_owner.h','Re4dcActorOwnedMaterial')+structure('coarse_actor_transaction.h','Re4dcActorPlannedRun')+r'''
struct Re4dcActorPlan {unsigned appearance=512,count=6,material_count=2,run_count=5;Re4dcActorOwnedMaterial materials[3];Re4dcActorPlannedRun runs[10];};
namespace nmr {struct Chunk {unsigned draw_owner,geometry,texture,triangles,stream_bytes,uv_bytes;const unsigned char *stream,*uv;unsigned mask_geometry[2],mask_texture[2],pair_crc,pair_fnv;};}
struct Texture {unsigned crc,fnv,width,height;};
struct Descriptor {unsigned sections=6,first_chunk=0;}desc;
struct Registry{nmr::Chunk chunks[8];Texture textures[3];}registry;
nmr::Chunk geoms[10];unsigned registry_tokens[3];unsigned char bytes[64];
const Descriptor* registry_descriptor(unsigned app){return app==512?&desc:nullptr;}
unsigned registry_geometry(unsigned i){return registry.chunks[i].geometry;}
nmr::Chunk registry_gview(unsigned g){return geoms[g];}
'''+utilities+matcher+masked+r'''
unsigned checks=0;
void want(bool v,const char* label){++checks;if(!v){std::fprintf(stderr,"FAIL %s\n",label);std::exit(1);}}
Re4dcActorPlan make(unsigned mode) {
 Re4dcActorPlan p;registry={};desc={};
 registry.textures[0]={11,22,512,512};registry.textures[1]={33,44,128,64};registry.textures[2]={55,66,128,64};
 for(unsigned i=0;i<10;++i){geoms[i]={};geoms[i].geometry=i;geoms[i].triangles=10;geoms[i].stream=bytes+i;geoms[i].uv=bytes+i+12;geoms[i].stream_bytes=8;geoms[i].uv_bytes=4;}
 for(unsigned i=0;i<6;++i){auto& c=registry.chunks[i];c=geoms[i];c.draw_owner=i;c.texture=0;c.mask_geometry[0]=c.mask_geometry[1]=~0u;}
 auto& plain=p.materials[0];plain.image={&registry_tokens[0],nullptr,512,512,6,~0u,0};plain.crc=11;plain.fnv=22;
 auto& pair=p.materials[1];pair.image={&registry_tokens[1],nullptr,128,64,6,~0u,0};pair.mask={&registry_tokens[2],nullptr,128,64,0,~0u,0};pair.crc=77;pair.fnv=88;pair.material_flags=4;pair.depth_mode=1;pair.mask_ref=0;pair.mask_same_uv=1;pair.wrap_s=pair.wrap_t=1;
 auto& hair=registry.chunks[3];hair.mask_texture[0]=1;hair.mask_texture[1]=2;hair.pair_crc=77;hair.pair_fnv=88;
 if(mode==0) {registry.chunks[2]=registry.chunks[1];registry.chunks[2].draw_owner=1;hair.mask_geometry[1]=7;}
 else if(mode==1) {hair.mask_geometry[0]=6;hair.mask_geometry[1]=7;geoms[6].triangles=4;geoms[7].triangles=6;}
 else {p.material_count=1;}
 p.run_count=0;
 for(unsigned role=0;role<6;++role) {
  const auto& c=registry.chunks[role];if(c.draw_owner!=role)continue;
  const unsigned gs[2]={c.mask_geometry[0]==~0u?c.geometry:c.mask_geometry[0],c.mask_geometry[1]};
  for(unsigned k=(mode==0 && role==3)?1:0;k<2;++k) {
   if(gs[k]==~0u)continue;
   const auto& g=geoms[gs[k]];auto& r=p.runs[p.run_count++];
   r.role=role;r.material=k?1:0;r.immutable_asset_id=kRegistryAsset0+gs[k];r.triangles=g.triangles;r.uv={g.uv,g.uv_bytes};r.stream={g.stream,g.stream_bytes};
  }
 }
 return p;
}
int main() {
 auto p=make(0);
#if RE4DC_ROUTE_CH22
 want(re4dc_registry_runs_match(&p),"complete five-run Luis plan");want(re4dc_registry_masked(&p),"mask-only capability");
 for(unsigned i=0;i<5;++i){p=make(0);p.runs[i].role^=1;want(!re4dc_registry_runs_match(&p),"run source role");}
 for(unsigned Re4dcActorPlannedRun::* f:{&Re4dcActorPlannedRun::material,&Re4dcActorPlannedRun::immutable_asset_id,&Re4dcActorPlannedRun::triangles}){p=make(0);p.runs[2].*f+=1;want(!re4dc_registry_runs_match(&p),"mask run identity");}
 for(auto f:{&Re4dcActorPlannedRun::uv,&Re4dcActorPlannedRun::stream}) {p=make(0);(p.runs[2].*f).data=bytes+40;want(!re4dc_registry_runs_match(&p),"mask run span pointer");p=make(0);(p.runs[2].*f).size+=1;want(!re4dc_registry_runs_match(&p),"mask run span size");}
 for(unsigned Re4dcActorOwnedMaterial::* f:{&Re4dcActorOwnedMaterial::crc,&Re4dcActorOwnedMaterial::fnv,&Re4dcActorOwnedMaterial::material_flags,&Re4dcActorOwnedMaterial::blend,&Re4dcActorOwnedMaterial::depth_mode,&Re4dcActorOwnedMaterial::mask_ref,&Re4dcActorOwnedMaterial::mask_same_uv,&Re4dcActorOwnedMaterial::wrap_s,&Re4dcActorOwnedMaterial::wrap_t}){p=make(0);p.materials[1].*f+=1;want(!re4dc_registry_runs_match(&p),"mask material state");}
 for(auto im:{&Re4dcActorOwnedMaterial::image,&Re4dcActorOwnedMaterial::mask}) {
  for(unsigned Re4dcUiImage::* f:{&Re4dcUiImage::width,&Re4dcUiImage::height,&Re4dcUiImage::format}) {p=make(0);(p.materials[1].*im).*f+=1;want(!re4dc_registry_runs_match(&p),"mask image shape/format");}
  p=make(0);(p.materials[1].*im).pixels=bytes;want(!re4dc_registry_runs_match(&p),"mask image token");
 }
 p=make(0);p.materials[1].image.palette=bytes;want(!re4dc_registry_runs_match(&p),"unexpected colour palette");
 p=make(0);p.materials[1].image.palette_bytes=1;want(!re4dc_registry_runs_match(&p),"unexpected colour palette bytes");
 p=make(0);p.run_count--;want(!re4dc_registry_runs_match(&p),"missing draw");
 p=make(0);p.runs[p.run_count++]=p.runs[1];p.runs[p.run_count-1].role=2;want(!re4dc_registry_runs_match(&p),"spurious covered face draw");
 p=make(0);p.material_count=3;want(!re4dc_registry_runs_match(&p),"unused material");
#else
 want(!re4dc_registry_runs_match(&p),"guard off rejects alias/mask-only plan");want(!re4dc_registry_masked(&p),"guard off retains two-run capability check");
#endif
 p=make(1);want(re4dc_registry_runs_match(&p),"ordinary two-run mask unchanged");want(re4dc_registry_masked(&p),"ordinary mask capability");
 p=make(2);want(re4dc_registry_runs_match(&p),"ordinary opaque plan unchanged");want(!re4dc_registry_masked(&p),"opaque has no mask capability");
 want(!re4dc_registry_runs_match(nullptr),"missing plan");p.appearance=0x100;want(!re4dc_registry_runs_match(&p),"unregistered plan");
 std::printf("%u actual run matcher checks passed\n",checks);
}
'''
with tempfile.TemporaryDirectory() as tmp:
 p=Path(tmp);cpp=p/'mask.cpp';cpp.write_text(source)
 for on in (0,1):
  exe=p/f'mask-{on}';subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror',f'-DRE4DC_ROUTE_CH22={on}',str(cpp),'-o',str(exe)],check=True)
  print(f'CH22={on}:',subprocess.check_output([str(exe)],text=True).strip())