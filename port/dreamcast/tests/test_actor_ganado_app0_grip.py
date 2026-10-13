#!/usr/bin/env python3
"""Exercise the actual role tables, texture comparator and lifetime/role consumers.

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
    return r"""
#include <cassert>
#include <cstdint>
#include <cstring>
#include <cstdio>
#include <new>
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
static void tpl(unsigned no,const Texture* textures) {
 const unsigned b=at(no),desc=b+12;
 std::memcpy(arena+16+500*4+(no-4)*4,"TPL",3);
 word(b,0x20af30);word(b+4,3);word(b+8,desc);
 for(unsigned k=0;k<3;++k) {
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
int main() {
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
 std::printf("APP0_GRIP=%d PL08=%d NMR=%d checks=%u PASS\n",RE4DC_ACTOR_GANADO_APP0_GRIP,RE4DC_ACTOR_PL08,RE4DC_NATIVE_MODEL_REGISTRY,checks);
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
        for pl08, registry in [(0, 0), (1, 0), (0, 1), (1, 1)]:
            for enabled in (0, 1):
                binary = out / f'grip-{enabled}-pl08-{pl08}-registry-{registry}'
                subprocess.run([args.cxx, '-std=c++17', '-O1', '-g', '-fsanitize=address,undefined',
                    '-fno-omit-frame-pointer', '-fno-pie', '-no-pie', '-Wall', '-Wextra', '-Werror',
                    '-Wno-misleading-indentation', f'-DRE4DC_ACTOR_GANADO_APP0_GRIP={enabled}',
                    f'-DRE4DC_ACTOR_PL08={pl08}', f'-DRE4DC_NATIVE_MODEL_REGISTRY={registry}',
                    f'-DRE4DC_NATIVE_MODEL_REGISTRY_PACK={registry}', '-DRE4DC_ACTOR_APPEARANCE_ALIAS=2',
                    '-I'+str(GAME), '-I'+str(GAME/'platform/include'), str(source), '-o', str(binary)], check=True)
                subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
