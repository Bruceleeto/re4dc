#!/usr/bin/env python3
"""Exercise the actual role tables, lifetime and full/lean material consumers.

Fixtures model already-adopted BINs and relocated TPLs. They do not substitute for
private archive hash verification, PS2 geometry provenance, or target rendering.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
GAME = ROOT / 'port/dreamcast/game'


def function(text, signature):
    start = text.index(signature)
    opening = text.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


def harness():
    material = (GAME / 'coarse_actor_material.inc').read_text()
    definitions = material[material.index('namespace re4dc_material {'):material.index('\ninline bool readable')]
    actual = '\n'.join(function(material, s) for s in [
        'bool digest(', 'inline bool base_level_sampler(', 'Error texture(',
        'inline bool source_appearance_type('])
    owned = (GAME / 'platform/include/actor_native_owner.h').read_text()
    owned = owned[owned.index('struct Re4dcActorOwnedMaterial {'):owned.index('struct Re4dcActorDrawRun')]
    start = material.index('#if RE4DC_ACTOR_GANADO_APP0_GRIP\n// Appearance 0 may use')
    end = material.index('extern "C" int re4dc_actor_material_certificate(', start)
    consumers = material[start:end]
    return r"""
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <new>
#include <initializer_list>
struct ModelData {
 const void *pHead,*pClr,*pTex,*pWeight,*pParts,*vtxOrig,*nrmOrig;
 unsigned displist_num;
};
struct cModelInfo { ModelData* pData; void* tpl_addr; cModelInfo* pList; };
class cModel { public: cModelInfo* pModelInfo; void* pParts; unsigned serial; };
constexpr unsigned kRe4dcActorRoles=RE4DC_ACTOR_PL08?9:8;
constexpr unsigned RE4DC_ACTOR_MATERIAL_RECORD_REVISION=0x20260930;
#define RE4DC_LEON_LIKE(a) ((a)==256 || (RE4DC_ACTOR_PL08 && (a)==264))
static unsigned checks;
static void check_at(bool value,unsigned line) { ++checks; if(!value)std::fprintf(stderr,"check %u line %u failed\n",checks,line);assert(value); }
#define check(value) check_at(bool(value),__LINE__)
static unsigned char arena[300000];
static unsigned at(unsigned no) { return 4096+(no-4)*512; }
static void word(unsigned pos,unsigned x) {std::memcpy(arena+pos,&x,4);}
static void half(unsigned pos,unsigned short x) {std::memcpy(arena+pos,&x,2);}
""" + definitions + r"""
bool readable(const void* p,unsigned n) {
 auto a=reinterpret_cast<std::uintptr_t>(arena),b=reinterpret_cast<std::uintptr_t>(p);
 return b>=a && b-a<=sizeof(arena) && n<=sizeof(arena)-(b-a);
}
unsigned u32at(const void* p,unsigned at) {unsigned v;std::memcpy(&v,static_cast<const unsigned char*>(p)+at,4);return v;}
unsigned u16at(const void* p,unsigned at) {unsigned short v;std::memcpy(&v,static_cast<const unsigned char*>(p)+at,2);return v;}
// Synthetic relocated pointer encoding for the host fixture only.
const void* ptrat(const void* p,unsigned at) {unsigned v=u32at(p,at);return v && v<sizeof(arena)?arena+v:nullptr;}
""" + actual + r"""
}
unsigned re4dc_registry_sections(unsigned) {return 0;}
#include "actor_lifetime.inc"
#include "native_ui.h"
""" + owned + r"""
#if RE4DC_ACTOR_PROOF_LEAN
static int lean_source_material(cModel*,cModelInfo*,unsigned,unsigned,const re4dc_material::Role*,Re4dcActorOwnedMaterial*);
#endif
""" + consumers + r"""
using namespace re4dc_material;
using namespace re4dc_material::life;
static ModelData* data[4];
static cModelInfo infos[5];
static cModel model;
static unsigned tpl_number=473;
static const Role* row(unsigned app,unsigned role,unsigned bin) {
 for(const auto& r:roles)if(r.appearance==app && r.role==role && r.source_bin==bin)return &r;
 return nullptr;
}
static void tpl(unsigned no,const Texture* textures,unsigned count=3) {
 const unsigned b=at(no),desc=b+12;
 std::memcpy(arena+16+500*4+(no-4)*4,"TPL",3);
 word(b,0x20af30);word(b+4,count);word(b+8,desc);
 for(unsigned k=0;k<count;++k) {
  const unsigned h=b+36+k*36,p=b+160+k*32;const auto& t=textures[k];
  word(desc+k*8,h);word(desc+k*8+4,0);half(h,t.height);half(h+2,t.width);
  word(h+4,t.format);word(h+8,p);
  for(unsigned j=0;j<5;++j)word(h+12+j*4,t.sampler[j]);
  for(unsigned j=0;j<3;++j)arena[h+32+j]=t.sampler[j+5];
  std::memcpy(arena+p,"R4NREF\0",8);word(p+8,t.crc);word(p+12,t.fnv);
  word(p+16,t.width);word(p+20,t.height);word(p+24,t.format);
 }
}
static void setup(bool grip=true) {
 for(auto& x:archives)x={};for(auto& x:assets)x={};for(auto& x:infos_live)x={};for(auto& x:bindings)x={};
#if RE4DC_NATIVE_MODEL_REGISTRY_PACK
 room_rows={};
#endif
 serial=1;epoch=1;exhausted=false;std::memset(arena,0,sizeof(arena));
 word(0,500);word(4,at(504));for(unsigned i=0;i<500;++i)word(16+i*4,at(i+4));
 tpl(473,t_em12_473);tpl(445,t_em15_445);tpl_number=473;
 archives[0]={arena,arena,sizeof(arena),77,2};
 const unsigned bins[4]={472,474,grip?451u:448u,grip?456u:453u};
 for(unsigned k=0;k<4;++k) {
  const unsigned no=bins[k],offset=at(no);std::memcpy(arena+16+500*4+(no-4)*4,"BIN",3);
  data[k]=new(arena+offset)ModelData{};
  const void* sec[7];for(unsigned j=0;j<7;++j)sec[j]=arena+offset+96+j*8;
  *data[k]={sec[0],sec[1],sec[2],sec[3],sec[4],sec[5],sec[6],1};
  BlobMask mask=0;for(unsigned t=0;t<RE4DC_BLOB_COUNT;++t)if(RE4DC_BLOB(t).family==2 && RE4DC_BLOB(t).bin==no)mask|=BlobMask(1u)<<t;
  assets[k]={data[k],arena+offset,512,0,77,100+k,mask,0,{sec[0],sec[1],sec[2],sec[3],sec[4],sec[5],sec[6]}};
  infos[k]={data[k],arena+at(473),k<3?&infos[k+1]:nullptr};
 }
 infos[4]={};model={&infos[0],arena+2048,9};
}
static bool adopt_and_bind(unsigned app=0) {
 for(unsigned k=0;k<4;++k)re4dc_actor_info_adopt(&infos[k]);
 cModelInfo* got[5]{};return re4dc_actor_role_bindings(&model,app,got,4);
}
[[maybe_unused]] static void reject_after_adoption() {
 cModelInfo* got[4]{};check(!re4dc_actor_role_bindings(&model,0,got,4));
 check(!re4dc_actor_role_source_bin(&model,&infos[2],0,2));
}
// Adopt one real table row through the actual immutable source-owner path.
static void setup_row(const Role& r) {
 setup();for(auto& x:assets)x={};for(auto& x:infos)x={};
 const unsigned no=r.source_bin,offset=at(no);
 std::memcpy(arena+16+500*4+(no-4)*4,"BIN",3);
 data[0]=new(arena+offset)ModelData{};
 const void* sec[7];for(unsigned j=0;j<7;++j)sec[j]=arena+offset+96+j*8;
 *data[0]={sec[0],sec[1],sec[2],sec[3],sec[4],sec[5],sec[6],1};
 BlobMask mask=0;for(unsigned t=0;t<RE4DC_BLOB_COUNT;++t)
  if(RE4DC_BLOB(t).family==2 && RE4DC_BLOB(t).bin==no)mask|=BlobMask(1u)<<t;
 assets[0]={data[0],arena+offset,512,0,77,100,mask,0,{sec[0],sec[1],sec[2],sec[3],sec[4],sec[5],sec[6]}};
 tpl(r.source_tpl,r.textures,r.texture_count);
 infos[0]={data[0],arena+at(r.source_tpl),nullptr};model={&infos[0],arena+2048,9};
 re4dc_actor_info_adopt(&infos[0]);
}
static void material_result(bool lean,unsigned app,unsigned role,const Role* resolved,bool expected) {
 Re4dcActorOwnedMaterial value;
 std::memset(&value,0x5a,sizeof(value));unsigned char before[sizeof(value)];std::memcpy(before,&value,sizeof(value));
 int got=0;
#if RE4DC_ACTOR_PROOF_LEAN
 if(lean)got=lean_source_material(&model,&infos[0],app,role,resolved,&value);else
#else
 (void)lean;(void)resolved;
#endif
 got=re4dc_actor_source_material(&model,&infos[0],app,role,&value);
 check(bool(got)==expected);
 if(!got){check(std::memcmp(before,&value,sizeof(value))==0);return;}
 const unsigned slot=role==4?0:2;check(resolved!=nullptr);const auto& want=resolved->textures[slot];
 check(value.image.pixels==arena+at(resolved->source_tpl)+160+slot*32);
 check(!value.image.palette && value.image.width==want.width && value.image.height==want.height);
 check(value.image.format==want.format && value.image.palette_format==0xffffffffu && !value.image.palette_bytes);
 check(value.crc==want.crc && value.fnv==want.fnv && value.wrap_s==want.sampler[0] && value.wrap_t==want.sampler[1]);
 check(!value.mask.pixels && !value.mask.palette && !value.mask.width && !value.mask.height && !value.mask.format);
 check(!value.material_flags && !value.blend && !value.depth_mode && value.mask_ref==256 && !value.mask_same_uv);
}
static void source_material_tests() {
 // All authored hand and accessory rows for appearances 0..4 retain their result.
 for(const auto& r:roles)if(r.appearance<=4 && r.role>=2 && r.role<=4) {
  setup_row(r);const Role* resolved=actor_current_role(&model,&infos[0],r.appearance,r.role);check(resolved==&r);
  const bool supported=(r.role==2 && r.source_bin==451) || (r.role==3 && r.source_bin==456) ||
      (r.role==4 && (r.source_bin==467 || r.source_bin==484));
  const bool expected=supported && (r.appearance>0 || RE4DC_ACTOR_GANADO_APP0_GRIP);
  material_result(false,r.appearance,r.role,resolved,expected);
#if RE4DC_ACTOR_PROOF_LEAN
  material_result(true,r.appearance,r.role,resolved,expected);
#endif
  // Neither an existing accessory nor another appearance supplies app0 identity.
  if(r.appearance>0) {
   material_result(false,0,r.role,resolved,false);
#if RE4DC_ACTOR_PROOF_LEAN
   material_result(true,0,r.role,resolved,false);
#endif
  }
 }
 for(unsigned role:{2u,3u}) {
  const Role grip={0,role,role==2?451u:456u,473,role==2?&m_extra_451:&m_extra_456,t_em12_473,3};
  setup_row(grip);const Role* resolved=actor_current_role(&model,&infos[0],0,role);
  material_result(false,0,role,resolved,RE4DC_ACTOR_GANADO_APP0_GRIP);
#if RE4DC_ACTOR_PROOF_LEAN
  material_result(true,0,role,&grip,RE4DC_ACTOR_GANADO_APP0_GRIP);
  // The lean entry consumes a resolved row; app0 must match every identity field.
  for(unsigned field=0;field<7;++field) {
   Role bad=grip;
   if(field==0)bad.appearance=1;if(field==1)bad.role=5;if(field==2)bad.source_bin=448;
   if(field==3)bad.source_tpl=445;if(field==4)bad.model=&m_em15_448;
   if(field==5)bad.textures=t_em15_445;if(field==6)bad.texture_count=2;
   material_result(true,0,role,&bad,false);
  }
  material_result(true,0,role,nullptr,false);
#endif
  // Current ownership remains mandatory for the public path.
  for(unsigned failure=0;failure<7;++failure) {
   setup_row(grip);
   if(failure==0)assets[0].owner_revision++;
   if(failure==1)assets[0].serial++;
   if(failure==2)archives[0].revision++;
   if(failure==3)infos[0].tpl_addr=arena+at(445);
   if(failure==4)model.pModelInfo=nullptr;
   if(failure==5)assets[0].pending=1;
   if(failure==6)data[0]->pTex=arena;
   material_result(false,0,role,resolved,false);
  }
  // Live material texture checks must reject late changes in either extraction path.
  for(unsigned failure=0;failure<6;++failure) {
   setup_row(grip);resolved=actor_current_role(&model,&infos[0],0,role);
   const unsigned b=at(473),h=b+36+2*36,p=b+160+2*32;
   if(failure==0)word(p+8,t_em12_473[2].crc^1);
   if(failure==1)half(h,t_em12_473[2].height+1);
   if(failure==2)word(h+4,t_em12_473[2].format^1);
   if(failure==3)word(h+12,t_em12_473[2].sampler[0]^1);
   if(failure==4)word(b+4,2);
   if(failure==5)word(h+8,sizeof(arena)+32);
   material_result(false,0,role,resolved,false);
#if RE4DC_ACTOR_PROOF_LEAN
   material_result(true,0,role,&grip,false);
#endif
  }
  setup_row(grip);
  for(unsigned app:{5u,256u,264u,~0u}) {
   material_result(false,app,role,resolved,false);
#if RE4DC_ACTOR_PROOF_LEAN
   material_result(true,app,role,&grip,false);
#endif
  }
  for(unsigned badrole:{0u,1u,4u,5u,~0u}) {
   material_result(false,0,badrole,resolved,false);
#if RE4DC_ACTOR_PROOF_LEAN
   material_result(true,0,badrole,&grip,false);
#endif
  }
  check(!re4dc_actor_source_material(&model,&infos[0],0,role,nullptr));
#if RE4DC_ACTOR_PROOF_LEAN
  check(!lean_source_material(&model,&infos[0],0,role,&grip,nullptr));
#endif
 }
}
int main() {
 source_material_tests();
 const unsigned base_roles=52+(RE4DC_ACTOR_PL08?9:0),base_blobs=26+(RE4DC_ACTOR_PL08?4:0);
 check(sizeof(roles)/sizeof(roles[0])==base_roles+(RE4DC_ACTOR_GANADO_APP0_GRIP?2:0));
 check(sizeof(source_blobs)/sizeof(source_blobs[0])==base_blobs);
 const auto* right=row(0,2,451);const auto* left=row(0,3,456);
 check(bool(right)==bool(RE4DC_ACTOR_GANADO_APP0_GRIP));check(bool(left)==bool(RE4DC_ACTOR_GANADO_APP0_GRIP));
#if RE4DC_ACTOR_GANADO_APP0_GRIP
 check(right->model==&m_extra_451 && left->model==&m_extra_456);
 check(right->textures==t_em12_473 && left->textures==t_em12_473);
 check(right->source_tpl==473 && left->source_tpl==473 && right->texture_count==3 && left->texture_count==3);
 for(unsigned k=0;k<base_roles;++k)check(roles[k].appearance!=0 || roles[k].source_bin!=451);
#endif
 check(source_appearance_type(0,0x12,1));check(source_appearance_type(0,0x13,1));
 check(!source_appearance_type(0,0x13,0));check(!source_appearance_type(0,0x15,1));
 check(!source_appearance_type(0,0x26,1));check(!source_appearance_type(1,0x13,1));
 setup(false);check(adopt_and_bind());
 setup();check(adopt_and_bind()==bool(RE4DC_ACTOR_GANADO_APP0_GRIP));
#if RE4DC_ACTOR_GANADO_APP0_GRIP
 check(re4dc_actor_role_source_bin(&model,&infos[2],0,2)==451);
 check(re4dc_actor_role_source_bin(&model,&infos[3],0,3)==456);
 check(!re4dc_actor_role_source_bin(&model,&infos[2],0,3));
 check(!re4dc_actor_role_source_bin(&model,&infos[2],1,2));
 check(re4dc_actor_material_owner_proof(&model,&infos[2],0,2,RE4DC_ACTOR_MATERIAL_RECORD_REVISION));
 check(!re4dc_actor_material_owner_proof(&model,&infos[2],0,2,0));
 auto revision=re4dc_actor_binding_revision(&model);check(revision);
 // Exact keys, dimensions, formats, every sampler word, and owner ranges stay mandatory.
 for(unsigned k=0;k<3;++k)for(unsigned field=0;field<18;++field) {
  setup();const unsigned h=at(473)+36+k*36,p=at(473)+160+k*32;
  unsigned loc=field==0?p:field==1?p+8:field==2?p+12:field==3?p+16:field==4?p+20:field==5?p+24:
    field==6?h:field==7?h+2:field==8?h+4:field<14?h+12+(field-9)*4:h+32+(field-14);
  if(field<17)arena[loc]^=1;else word(h+8,sizeof(arena)+32);
  check(!adopt_and_bind());check(!find_info(&infos[2]));
 }
 setup();infos[2].tpl_addr=arena+at(445);check(!adopt_and_bind());
 check(re4dc_actor_role_source_bin(&model,&infos[2],1,2)==451); // another exact appearance is not app0
 setup();archives[0].family=1;check(!adopt_and_bind());
 setup();assets[2].templates=0;check(!adopt_and_bind());
 setup();assets[2].templates=BlobMask(1u)<<23;check(!adopt_and_bind()); // left identity cannot become right
 setup();assets[2].owner_revision++;check(!adopt_and_bind());
 setup();data[2]->pTex=arena;check(!adopt_and_bind());
 setup();assets[2].pending=123;check(!adopt_and_bind());
 setup();infos[2].pData=data[3];check(!adopt_and_bind());
 setup();check(adopt_and_bind());assets[2].serial++;reject_after_adoption();
 setup();check(adopt_and_bind());archives[0].revision++;reject_after_adoption();
 setup();check(adopt_and_bind());re4dc_actor_archive_retire(arena);reject_after_adoption();
 setup();check(adopt_and_bind());re4dc_actor_info_retire(&infos[2]);reject_after_adoption();
 setup();check(adopt_and_bind());infos[2].tpl_addr=arena+at(445);reject_after_adoption();
 setup();check(adopt_and_bind());infos[2].pList=&infos[2];reject_after_adoption();
 setup();check(adopt_and_bind());model.pModelInfo=&infos[3];reject_after_adoption();
 setup();check(adopt_and_bind());infos[4]=infos[2];infos[3].pList=&infos[4];check(!adopt_and_bind());
 setup();check(adopt_and_bind());exhausted=true;reject_after_adoption();
 setup();check(adopt_and_bind());revision=re4dc_actor_binding_revision(&model);model.serial++;check(re4dc_actor_binding_revision(&model)!=revision);
#if RE4DC_NATIVE_MODEL_REGISTRY_PACK
 // A duplicate row cannot give the unique source-bin consumer an ambiguous proof.
 setup();Role duplicate=*right;room_rows_publish(&duplicate,1,nullptr,0,1);check(adopt_and_bind());
 check(!re4dc_actor_role_source_bin(&model,&infos[2],0,2));
 duplicate.role=3;setup();room_rows_publish(&duplicate,1,nullptr,0,1);check(!adopt_and_bind());
 check(kBaseRoles==base_roles+2 && kBaseBlobs==base_blobs);
 check(kRoomRoles==kRoleMaskBits-base_roles-2 && kRoomBlobs==kBlobMaskBits-base_blobs);
#endif
#endif
 std::printf("APP0_GRIP=%d PL08=%d NMR=%d LEAN=%d checks=%u PASS\n",RE4DC_ACTOR_GANADO_APP0_GRIP,RE4DC_ACTOR_PL08,RE4DC_NATIVE_MODEL_REGISTRY,RE4DC_ACTOR_PROOF_LEAN,checks);
}
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx', default='c++')
    parser.add_argument('--keep', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='app0-grip-') as temporary:
        out = args.keep or Path(temporary)
        out.mkdir(exist_ok=True, parents=True)
        source = out / 'test.cpp'
        source.write_text(harness())
        for pl08, registry, lean in [(p, r, l) for p in (0, 1) for r in (0, 1) for l in (0, 1, 2)]:
            for enabled in (0, 1):
                binary = out / f'grip-{enabled}-pl08-{pl08}-registry-{registry}-lean-{lean}'
                subprocess.run([args.cxx, '-std=c++17', '-O1', '-g', '-fsanitize=address,undefined',
                    '-fno-omit-frame-pointer', '-fno-pie', '-no-pie', '-Wall', '-Wextra', '-Werror',
                    '-Wno-misleading-indentation', '-Wno-class-memaccess', f'-DRE4DC_ACTOR_GANADO_APP0_GRIP={enabled}',
                    f'-DRE4DC_ACTOR_PL08={pl08}', f'-DRE4DC_ACTOR_PROOF_LEAN={lean}', f'-DRE4DC_NATIVE_MODEL_REGISTRY={registry}',
                    f'-DRE4DC_NATIVE_MODEL_REGISTRY_PACK={registry}', '-DRE4DC_ACTOR_APPEARANCE_ALIAS=2',
                    '-I'+str(GAME), '-I'+str(GAME/'platform/include'), str(source), '-o', str(binary)], check=True)
                subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
