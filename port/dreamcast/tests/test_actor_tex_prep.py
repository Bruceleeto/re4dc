#!/usr/bin/env python3
"""Actual ACTOR_TEX_PREP readers on synthetic source owners; no target claim."""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
GAME = ROOT / "port/dreamcast/game"
INC = GAME / "platform/include"


def function(text, marker, body=False):
    start = text.index(marker)
    begin = text.index("{", start)
    depth, end = 1, begin + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[begin if body else start:end]


def material_harness():
    mat = (GAME / "coarse_actor_material.inc").read_text()
    types = mat[mat.index("struct Digest {"):mat.index("// These are direct SOURCE")]
    pure = "\n".join(function(mat, marker) for marker in (
        "inline bool readable(", "inline unsigned u32at(", "inline unsigned u16at(",
        "inline const void* ptrat(", "inline unsigned floatbits(", "bool digest(",
        "inline bool base_level_sampler(", "inline bool source_appearance_type(",
        "inline bool room_colour_scale(", "Error texture("))
    begin = mat.index("#if RE4DC_ACTOR_MATERIAL_RECORD\n// archive=false:")
    info = mat[begin:mat.index("\n#if RE4DC_LEON_HAND_POSES", begin)]
    begin = mat.index("namespace re4dc_material { namespace record {")
    record = mat[begin:mat.index("\n#endif\nnamespace re4dc_material {", begin)]
    return r'''
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <vector>
#include <sys/mman.h>
#define RE4DC_ACTOR_TRANSACTION 1
#define RE4DC_ACTOR_TEX_PREP 1
#define RE4DC_ACTOR_APPEARANCE_ALIAS 2
#define RE4DC_CROWD_READOPT 2
#define RE4DC_CROWD_READOPT_MEMO 1
#define RE4DC_ACTOR_WIDE_IDENTITY 1
#define RE4DC_ACTOR_PL08 0
#define RE4DC_ACTOR_LEON_NATIVE_LOOK 0
#define RE4DC_LEON_LIKE(a) ((a)==256u)
constexpr unsigned kRe4dcActorRoles=9;
struct ModelData {
 unsigned flags=1,shift=0,nParts=1,nVtx=1,nNrm=0,nTex=1,weight_palette_num=0,weight_ext_num=0,displist_num=1,version=1;
 const void* pHead=nullptr;const void* pClr=nullptr;const void* pTex=nullptr;const void* pWeight=nullptr;
 const void* pParts=nullptr;const void* vtxOrig=nullptr;const void* nrmOrig=nullptr;
};
class cModelInfo { public:
 ModelData* pData=nullptr;const void* tpl_addr=nullptr;cModelInfo* pList=nullptr;
 unsigned be_flag=9;float invisible_factor=1;unsigned blend_mode=0,colorWord=~0u,color2[4]{},flagsDC=0;
 void* pAddTpl=nullptr;unsigned nAddTex=0,blendRatio=0,blendType=0;void* texBlendTbl=nullptr;void* pTexAnim=nullptr;
 unsigned uvU=0,uvV=0,uvScrollU=0,uvScrollV=0;void* pShape=nullptr;
 struct Shape {float rate=0;void* data=nullptr;} shape[4];
};
class cModel { public:
 unsigned serial=42;void* pParts=nullptr;void* pList=nullptr;cModelInfo* pModelInfo=nullptr;
 unsigned id=0x15,type=0,nParts=34,be_flag=0,ot_type=0;
 void* pTexChg=nullptr;unsigned Shader_type=0,CullMode=0;float invisible_factor=1,invisible_factor2=1;
 unsigned alpha_omit=255,TevScaleGroup=0,AddAmb_r=0,AddAmb_g=0,AddAmb_b=0;
};
cModel* pPL=nullptr; cModel* pSubEm=nullptr;unsigned char gxCsScale[4]{};
bool coarse_finite(float f){return std::isfinite(f);}
extern "C" void re4dc_log(const char*,...){}
#include "actor_lifetime.h"
#include "actor_tex_prep.h"
namespace re4dc_material {
''' + types + r'''
constexpr unsigned kRoleMaskWords=3,kRoleMaskBits=96,kBlobMaskBits=64;
using BlobMask=std::uint64_t;
Role roles[32]{};SourceBlob source_blobs[16]{};unsigned role_count=0,blob_count=0;
#define RE4DC_ROLE_COUNT (re4dc_material::role_count)
#define RE4DC_ROLE(r) (re4dc_material::roles[r])
#define RE4DC_BLOB_COUNT (re4dc_material::blob_count)
#define RE4DC_BLOB(t) (re4dc_material::source_blobs[t])
''' + pure + r'''
}
#include "actor_lifetime.inc"
#if RE4DC_ACTOR_MATERIAL_RECORD
struct Re4dcActorPlan {unsigned count,appearance;cModelInfo* info[kRe4dcActorRoles];};
''' + record + r'''
#endif
namespace re4dc_material {
''' + info + r'''
}
bool source_current=true,change_source_after_first=false;unsigned source_calls;
re4dc_source::FrameIdentity source_frame{100,0x101,9,3,10,20};
re4dc_source::ModelIdentity source_model{};
extern "C" int re4dc_actor_tex_source_current(cModel* m,const re4dc_source::FrameIdentity* f,
 const re4dc_source::ModelIdentity* id) {
 ++source_calls;return source_current && (!change_source_after_first || source_calls==1) &&
 f && id && *f==source_frame && *id==source_model && id->address==reinterpret_cast<std::uintptr_t>(m) && id->serial==m->serial;
}
#include "actor_tex_prep_material.inc"
using namespace re4dc_material;using namespace re4dc_material::life;
unsigned checks;
void check(bool x){if(!x)std::fprintf(stderr,"material check %u failed\n",checks+1);assert(x);++checks;}
constexpr std::uintptr_t kArena=0x8c000000u;constexpr unsigned kArenaBytes=1<<20;
unsigned char* arena=reinterpret_cast<unsigned char*>(kArena);
cModel* model=reinterpret_cast<cModel*>(kArena+0x80000);
cModelInfo* links=reinterpret_cast<cModelInfo*>(kArena+0x81000);
Model models[8]{};Texture textures[8]{};Part parts[8]{};
void word(void* p,unsigned at,unsigned value){std::memcpy(static_cast<unsigned char*>(p)+at,&value,4);}
void half(void* p,unsigned at,unsigned value){unsigned short x=value;std::memcpy(static_cast<unsigned char*>(p)+at,&x,2);}
unsigned address(const void* p){return unsigned(reinterpret_cast<std::uintptr_t>(p));}
void reset(unsigned n=4) {
 std::memset(arena,0,kArenaBytes);for(auto& x:archives)x={};for(auto& x:assets)x={};
 for(auto& x:infos_live)x={};for(auto& x:bindings)x={};for(auto& x:adopt_miss)x={};adopt_miss_next=0;
 serial=epoch=1;exhausted=false;role_count=blob_count=n;
#if RE4DC_ACTOR_MATERIAL_RECORD
 for(auto& r:record::records)r={};record::replace=37;
#if RE4DC_ACTOR_MATERIAL_RECORD == 2
 record::c={11,13,17,19,23};
#endif
#endif
 source_calls=0;source_current=true;change_source_after_first=false;*model=cModel{};
 model->pParts=arena+0x85000;model->pList=model->pParts;model->pModelInfo=links;
 pPL=pSubEm=nullptr;gxCsScale[0]=0;
 const unsigned bytes=128+n*1024;word(arena,0,n*2);
 archives[0]={arena,arena,bytes,2,2};
 for(unsigned k=0;k<n;++k) {
  auto* bin=arena+128+k*1024;auto* tpl=bin+512;
  word(arena,16+2*k*4,address(bin)-address(arena));word(arena,16+(2*k+1)*4,address(tpl)-address(arena));
  std::memcpy(arena+16+2*n*4+2*k*4,"BIN\0TPL\0",8);
  auto* data=reinterpret_cast<ModelData*>(bin);*data=ModelData{};
  data->pHead=bin+192;data->pClr=bin+200;data->pTex=bin+208;data->pWeight=bin+216;
  data->pParts=bin+256;data->vtxOrig=bin+224;data->nrmOrig=bin+232;
  const unsigned header[10]={1,0,1,1,0,1,0,0,1,1};std::memcpy(models[k].header,header,sizeof header);
  parts[k]={};parts[k].material[2]=parts[k].material[3]=parts[k].material[4]=255;
  models[k].parts=&parts[k];std::memcpy(bin+256+11,parts[k].material,13);
  textures[k]={};auto& t=textures[k];t.crc=0x12340000+k;t.fnv=0xaabb0000+k;t.width=t.height=4;t.format=6;
  t.sampler[0]=t.sampler[1]=t.sampler[2]=t.sampler[3]=1;
  word(tpl,4,1);word(tpl,8,address(tpl+16));word(tpl,16,address(tpl+32));
  half(tpl,32,4);half(tpl,34,4);word(tpl,36,6);word(tpl,40,address(tpl+80));
  for(unsigned j=0;j<4;++j)word(tpl,44+j*4,1);
  std::memcpy(tpl+80,"R4NREF\0",8);word(tpl,88,t.crc);word(tpl,92,t.fnv);word(tpl,96,4);word(tpl,100,4);word(tpl,104,6);
  const unsigned source_bin=k==2?448:k==3?453:k==4?467:100+k;
  roles[k]={1,k,source_bin,5+2*k,&models[k],&textures[k],1};source_blobs[k]={&models[k],2,4+2*k,{}};
  assets[k]={data,bin,512,0,2,10+k,BlobMask(1)<<k,0,{data->pHead,data->pClr,data->pTex,data->pWeight,data->pParts,data->vtxOrig,data->nrmOrig}};
  links[k]=cModelInfo{};links[k].pData=data;links[k].tpl_addr=tpl;links[k].pList=k+1<n?links+k+1:nullptr;
 }
 source_model={reinterpret_cast<std::uintptr_t>(model),model->serial,2};
}
struct Snapshot {
 std::vector<unsigned char> memory;
 Archive ar[kArchives];Asset as[kAssets];Info in[kInfos];Binding bi[kModels];AdoptMiss misses[4];
 unsigned s,e,memo;bool ex;
#if RE4DC_ACTOR_MATERIAL_RECORD
 record::Record cached[record::kRecords];unsigned replace;
#if RE4DC_ACTOR_MATERIAL_RECORD == 2
 record::Count counters;
#endif
#endif
 Snapshot():memory(arena,arena+kArenaBytes),s(serial),e(epoch),memo(adopt_miss_next),ex(exhausted){
  std::memcpy(ar,archives,sizeof ar);std::memcpy(as,assets,sizeof as);std::memcpy(in,infos_live,sizeof in);
  std::memcpy(bi,bindings,sizeof bi);std::memcpy(misses,adopt_miss,sizeof misses);
#if RE4DC_ACTOR_MATERIAL_RECORD
  std::memcpy(cached,record::records,sizeof cached);replace=record::replace;
#if RE4DC_ACTOR_MATERIAL_RECORD == 2
  counters=record::c;
#endif
#endif
 }
 bool same()const{
#if RE4DC_ACTOR_MATERIAL_RECORD
  if(replace!=record::replace || std::memcmp(cached,record::records,sizeof cached))return false;
#if RE4DC_ACTOR_MATERIAL_RECORD == 2
  if(std::memcmp(&counters,&record::c,sizeof counters))return false;
#endif
#endif
  return memory==std::vector<unsigned char>(arena,arena+kArenaBytes) && s==serial && e==epoch && ex==exhausted && memo==adopt_miss_next &&
  !std::memcmp(ar,archives,sizeof ar)&&!std::memcmp(as,assets,sizeof as)&&!std::memcmp(in,infos_live,sizeof in)&&
  !std::memcmp(bi,bindings,sizeof bi)&&!std::memcmp(misses,adopt_miss,sizeof misses);}
};
Re4dcActorTexMetadata inspect_expected(Re4dcActorTexReason reason) {
 Snapshot before;source_calls=0;Re4dcActorTexMetadata out{99,99,99,99,99};
 auto result=re4dc_actor_tex_metadata(model,&source_frame,&source_model,&out);
 if(result!=unsigned(reason))std::fprintf(stderr,"expected reason %u got %u\n",unsigned(reason),result);
 check(result==unsigned(reason));check(before.same());
 if(reason!=Re4dcActorTexReason::None)check(!out.roles && !out.owned && !out.dry && !out.visible_atlas_roles);
 return out;
}
int main(){
 check(mmap(arena,kArenaBytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0)==arena);
 reset();auto out=inspect_expected(Re4dcActorTexReason::None);check(out.appearance==1 && out.roles==4 && out.dry==4 && !out.owned && out.visible_atlas_roles==15);
 // The real later adoption must obtain exactly the dry proof's four roles.
 for(unsigned k=0;k<4;++k)re4dc_actor_info_adopt(links+k);
 out=inspect_expected(Re4dcActorTexReason::None);check(out.owned==4 && !out.dry);
 for(unsigned k=0;k<4;++k)check(actor_current_role(model,links+k,1,k)==roles+k);
 reset();model->id=0x12;out=inspect_expected(Re4dcActorTexReason::None);check(out.appearance==1); // real alias table
 reset();model->serial++;inspect_expected(Re4dcActorTexReason::Source);
 reset();source_current=false;inspect_expected(Re4dcActorTexReason::Source);
 reset();change_source_after_first=true;inspect_expected(Re4dcActorTexReason::Changed);
 reset();model->nParts=33;inspect_expected(Re4dcActorTexReason::Model);
 reset();model->be_flag=0x4000;inspect_expected(Re4dcActorTexReason::Model);
 reset();model->type=255;inspect_expected(Re4dcActorTexReason::Row);
 reset();model->Shader_type=1;inspect_expected(Re4dcActorTexReason::Material);
 reset();links[3].pList=links;inspect_expected(Re4dcActorTexReason::Chain);
 reset();links[0].pList=links+3;inspect_expected(Re4dcActorTexReason::Chain);
 reset();links[3].pList=reinterpret_cast<cModelInfo*>(kArena+3);inspect_expected(Re4dcActorTexReason::Chain);
 reset();std::swap(links[0].pData,links[1].pData);std::swap(links[0].tpl_addr,links[1].tpl_addr);inspect_expected(Re4dcActorTexReason::Row);
 reset();assets[0].pending=1;inspect_expected(Re4dcActorTexReason::Asset);
 reset();links[0].pData->pHead=arena+42;inspect_expected(Re4dcActorTexReason::Asset);
 reset();archives[0].revision++;inspect_expected(Re4dcActorTexReason::Asset);
 reset();assets[8]=assets[0];inspect_expected(Re4dcActorTexReason::Asset);
 reset();archives[1]=archives[0];inspect_expected(Re4dcActorTexReason::Owner);
 reset();for(unsigned k=0;k<4;++k)re4dc_actor_info_adopt(links+k);archives[0].revision++;inspect_expected(Re4dcActorTexReason::Lifetime);
 reset();re4dc_actor_info_adopt(links);infos_live[0].asset_serial++;inspect_expected(Re4dcActorTexReason::Row); // never dry-repairs stale owned record
 reset();word(const_cast<void*>(links[0].tpl_addr),88,123);inspect_expected(Re4dcActorTexReason::Owner);
 reset();word(const_cast<void*>(links[0].tpl_addr),44,0);inspect_expected(Re4dcActorTexReason::Owner); // sampler
 reset();re4dc_actor_info_adopt(links);word(const_cast<void*>(links[0].tpl_addr),88,123);inspect_expected(Re4dcActorTexReason::Row);
 reset();links[0].uvScrollU=1;inspect_expected(Re4dcActorTexReason::Material);
 // Archive=true must inspect ModelPart bytes even when record caching is enabled.
 reset();for(unsigned k=0;k<4;++k)re4dc_actor_info_adopt(links+k);
 static_cast<unsigned char*>(const_cast<void*>(links[0].pData->pParts))[11]=0x80;
 inspect_expected(Re4dcActorTexReason::Material);
 reset();for(unsigned k=0;k<4;++k)links[k].be_flag=1;inspect_expected(Re4dcActorTexReason::Hidden);
 reset();roles[2].source_bin=451;roles[3].source_bin=456;links[0].be_flag=links[1].be_flag=1;inspect_expected(Re4dcActorTexReason::Hidden);
 reset(5);out=inspect_expected(Re4dcActorTexReason::None);check(out.roles==5 && out.dry==5 && out.visible_atlas_roles==15);
 reset(5);roles[4].source_bin=484;out=inspect_expected(Re4dcActorTexReason::None);check(out.roles==5);
 reset(5);roles[4].source_bin=999;inspect_expected(Re4dcActorTexReason::Row);
 reset();roles[4]=roles[0];role_count=5;inspect_expected(Re4dcActorTexReason::Row); // ambiguous current row
 reset();exhausted=true;inspect_expected(Re4dcActorTexReason::Lifetime);
 unsigned s=0,e=0;check(!re4dc_actor_tex_lifetime(&s,&e));reset();Snapshot before;
 check(re4dc_actor_tex_lifetime(&s,&e)&&s==serial&&e==epoch&&before.same());
 std::printf("actor texture material: %u checks, pure owned/dry proof PASS\n",checks);
}
'''


def ledger_harness():
    trans = (ROOT / "src/game/trans.cpp").read_text()
    identity = function(trans, "bool sourceActorIdentity(")
    model = function(trans, "ModelIdentity sourceActorModel(")
    bridge = (GAME / "ui_bridge.cpp").read_text()
    room_type = bridge[bridge.index("struct Room4 {"):bridge.index("\nRoom4 room4", bridge.index("struct Room4 {"))]
    room_state = function(bridge, 'extern "C" int re4dc_room4_state(unsigned* generation,unsigned* cells,unsigned* bytes,unsigned* stale,unsigned* refused){')
    return r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <vector>
#define RE4DC_ACTOR_TRANSACTION 1
#include "actor_tex_prep.h"
using namespace re4dc_source;
class cUnit {public:cUnit* pNext=nullptr;};
class cModel:public cUnit {public:unsigned serial=1,id=0x15,type=1;};
cModel models[4];cModel* pPL=models;cModel* pSUB=nullptr;
struct Manager {cUnit* pAlive;unsigned nArray;} EmMgr{};
struct Global {unsigned prim_cnt=100,nPrim=1000,vtx_buf_no=0,Frame_cnt=9,stage_no=1,room_no=1;} global;
Global* pG=&global;unsigned re4dc_alive_gen[3]{0,3,4};
unsigned sourceActorEpoch=1,sourceActorPrimBase=100,sourceActorPrimBytes=1000,sourceActorPrimBuffer=0,sourceActorCount;
bool sourceActorActive=true,sourceActorRenderActive=false;
FrameLedger sourceActorLedger;alignas(16) FrameEntry entries[FrameLedger::MaxEntries];
''' + room_type + r'''
Room4 room4{true,12,2,4096,3,4};bool& room_good=room4.live;unsigned& room_generation=room4.generation;
''' + room_state + "\n" + identity + "\n" + model + r'''
unsigned life_serial=1,life_epoch=1,variant=0,metadata_calls=0,mutation=0;bool life_good=true;
extern "C" int re4dc_actor_tex_lifetime(unsigned* s,unsigned* e){*s=life_serial;*e=life_epoch;return life_good;}
extern "C" unsigned re4dc_ganado_tex_variant(){return variant;}
extern "C" unsigned re4dc_actor_tex_metadata(cModel* m,const FrameIdentity*,const ModelIdentity*,Re4dcActorTexMetadata* p){
 ++metadata_calls;
 if(metadata_calls==1){if(mutation==1)++life_serial;if(mutation==2)++variant;if(mutation==3)++room_generation;
  if(mutation==4)++models[2].serial;if(mutation==5)++sourceActorPrimBytes;}
 if(m->type==99)return unsigned(Re4dcActorTexReason::Row);
 *p={m->type,4,1,3,15};return 0;
}
extern "C" int re4dc_ganado_tex_picks(unsigned app,unsigned expected,Re4dcActorTexPick* p,unsigned* n){
 if(expected!=variant)return 0;
 const unsigned k=app*2;*n=2;
 for(unsigned i=0;i<2;++i)p[i]={{reinterpret_cast<const void*>(std::uintptr_t(128+k+i)),nullptr,512,512,6,~0u,0},50-k-i,100+k+i,1u<<app,i};
 return 1;
}
#include "source_actor_tex_prep.inc"
unsigned checks;
void check(bool x){if(!x)std::fprintf(stderr,"ledger check %u failed\n",checks+1);assert(x);++checks;}
void reset(unsigned n=3,bool complete=true){
 sourceActorLedger.retire();for(auto& e:entries)e={};global={};
 sourceActorEpoch=1;sourceActorPrimBase=100;sourceActorPrimBytes=1000;sourceActorPrimBuffer=0;
 sourceActorActive=true;sourceActorRenderActive=false;sourceActorCount=n;EmMgr={models,n};room_good=true;room_generation=12;
 re4dc_alive_gen[1]=3;re4dc_alive_gen[2]=4;pPL=models;pSUB=nullptr;
 life_serial=life_epoch=1;variant=metadata_calls=mutation=0;life_good=true;
 for(unsigned i=0;i<4;++i){models[i]={};models[i].serial=i+1;models[i].type=1;models[i].id=i?0x15:0;models[i].pNext=i+1<n?models+i+1:nullptr;}
 FrameIdentity frame{};check(sourceActorIdentity(frame));check(sourceActorLedger.begin(entries,sizeof entries,n,frame));
 for(unsigned i=0;i<n;++i)check(sourceActorLedger.append(frame,sourceActorModel(models+i),ModelPath::Source,0));
 check(sourceActorLedger.seal(frame));
 if(complete)for(unsigned i=0;i<n;++i){PreparationTicket t{};check(sourceActorLedger.claim(frame,t));check(sourceActorLedger.complete(frame,t,sourceActorModel(models+i)));}
}
std::vector<unsigned char> source_state(){
 std::vector<unsigned char> bytes;
 auto add=[&](const auto& x){const auto* p=reinterpret_cast<const unsigned char*>(&x);bytes.insert(bytes.end(),p,p+sizeof x);};
 add(global);add(EmMgr);add(models);add(pPL);add(pSUB);add(re4dc_alive_gen);add(room4);
 add(sourceActorActive);add(sourceActorRenderActive);add(sourceActorCount);add(sourceActorEpoch);
 add(sourceActorPrimBase);add(sourceActorPrimBytes);add(sourceActorPrimBuffer);
 return bytes;
}
Re4dcActorTexBatch run(bool success){
 const auto before=source_state();
 unsigned char ledger[sizeof sourceActorLedger],storage[sizeof entries];std::memcpy(ledger,&sourceActorLedger,sizeof ledger);std::memcpy(storage,entries,sizeof storage);
 Re4dcActorTexBatch b{};b.count=5;check(bool(re4dc_actor_tex_enumerate(&b))==success);
 check(!std::memcmp(ledger,&sourceActorLedger,sizeof ledger) && !std::memcmp(storage,entries,sizeof storage));
 if(!mutation)check(before==source_state()); // injected changes are deliberately external to the reader
 if(!success){check(!b.count);for(const auto& p:b.picks)check(!p.crc&&!p.fnv&&!p.image.pixels);}
 return b;
}
int main(){
 reset();auto b=run(true);check(b.count==2&&b.models==3&&b.qualified==2&&b.owned==2&&b.dry==6);
 check(b.picks[0].crc<b.picks[1].crc); // exact-key deduplication and stable ordering
 reset();models[2].type=2;b=run(true);check(b.count==4&&b.qualified==2);
 reset();models[2].type=99;b=run(true);check(b.count==2&&b.qualified==1&&b.declined[unsigned(Re4dcActorTexReason::Row)]==1);
 reset(4);models[1].type=1;models[2].type=2;models[3].type=3;b=run(false);check(b.declined[unsigned(Re4dcActorTexReason::Capacity)]==1);
 reset(3,false);run(false);reset();sourceActorRenderActive=true;run(false);
 reset();sourceActorActive=false;run(false);reset();room_good=false;run(false);reset();room_generation++;run(false);
 reset();pG->prim_cnt++;run(false);reset();pG->nPrim++;run(false);reset();pG->vtx_buf_no++;run(false);
 reset();pG->Frame_cnt++;run(false);reset();re4dc_alive_gen[1]++;run(false);reset();re4dc_alive_gen[2]++;run(false);
 reset();models[2].serial++;run(false);reset();models[2].pNext=models+1;run(false);
 reset();EmMgr.nArray=2;run(false);reset();sourceActorCount=4;run(false);
 reset();pSUB=models+2;run(false); // manager identity changed
 reset();life_good=false;run(false);
 for(unsigned i=1;i<=5;++i){reset();mutation=i;run(false);}
 std::printf("actor texture ledger: %u checks, identity/retirement/presentation purity PASS\n",checks);
}
'''


def mapping_harness():
    cast = (GAME / "coarse_ganado_cast.cpp").read_text()
    methods = "\n".join(function(cast, marker) for marker in (
        "unsigned far_texture(", "bool far_same(", "Re4dcUiImage image_of("))
    return r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#define RE4DC_CHARBAKE_TOGGLE 1
#define RE4DC_CROWD_FAR 1
#include "actor_tex_prep.h"
namespace gc {
constexpr unsigned texture_count=5;
struct Texture{unsigned crc,fnv,width,height;};
Texture textures[5]={{10,11,512,512},{20,21,512,512},{30,31,512,512},{40,41,512,512},{50,51,512,512}};
unsigned appearance_texture[5]={0,1,2,3,4};
const char* appearance_names[5]={"a","b","c","d","e"};
float bind[5][34][12]{};unsigned parents[34]{};
namespace far {
Texture textures[5]={{10,11,512,512},{20,21,512,512},{30,31,512,512},{40,41,512,512},{50,51,512,512}};
unsigned appearance_texture[5]={0,1,2,3,4};
const char* appearance_names[5]={"a","b","c","d","e"};
float bind[5][34][12]{};unsigned parents[34]{};
}
}
namespace re4dc_charbake {
constexpr unsigned kGanadoCrc=20,kGanadoFnv=21;
struct Variant {unsigned ganado_crc,ganado_fnv;};
Variant variants[2]={{200,201},{300,301}};
}
unsigned charbake_variant=0,texture_tokens[2][5]{};bool charbake_ready=false;
gc::Texture charbake_textures[5]{};
unsigned char skin_stream[256]{},skin_state[10]{},palette[34*12]{};
#define RE4DC_GC_TOKEN(t) (&texture_tokens[charbake_variant][t])
constexpr unsigned kApps=5;
inline unsigned cast_app(unsigned a){return a<kApps?a:a-kApps;}
''' + methods + r'''
#include "actor_tex_prep_ganado.inc"
unsigned checks;
void check(bool x){if(!x)std::fprintf(stderr,"mapping check %u failed\n",checks+1);assert(x);++checks;}
int main(){
 unsigned n=0;Re4dcActorTexPick p[2]{};auto run=[&](unsigned app,unsigned variant){
  unsigned char state[sizeof texture_tokens+sizeof charbake_textures+sizeof skin_stream+sizeof skin_state+sizeof palette];
  unsigned char* dst=state;
#define SAVE(x) std::memcpy(dst,x,sizeof x);dst+=sizeof x
  SAVE(texture_tokens);SAVE(charbake_textures);SAVE(skin_stream);SAVE(skin_state);SAVE(palette);
#undef SAVE
  const bool ready=charbake_ready;int result=re4dc_ganado_tex_picks(app,variant,p,&n);dst=state;
#define SAME(x) check(!std::memcmp(dst,x,sizeof x));dst+=sizeof x
  SAME(texture_tokens);SAME(charbake_textures);SAME(skin_stream);SAME(skin_state);SAME(palette);
#undef SAME
  check(ready==charbake_ready);return result;
 };
 check(run(0,0)&&n==1&&p[0].crc==10&&p[0].image.pixels==&texture_tokens[0][0]);
 check(run(1,0)&&n==1&&p[0].crc==200&&p[0].fnv==201);
 charbake_variant=1;check(run(1,1)&&n==1&&p[0].crc==300&&p[0].image.pixels==&texture_tokens[1][1]);
 check(!run(1,0)&&n==0);check(!run(5,1)&&n==0);
 gc::far::appearance_texture[0]=1;check(run(0,1)&&n==2&&p[1].crc==300&&p[1].far==1);
 gc::far::bind[0][0][0]=1;check(run(0,1)&&n==1);gc::far::bind[0][0][0]=0;
 gc::far::textures[1].crc++;check(run(0,1)&&n==1);
 std::printf("actor texture mapping: %u checks, variants/far immutable PASS\n",checks);
}
'''


def loader_harness():
    ui = (GAME / "platform/native_ui.cpp").read_text()
    acquire = function(ui, 'extern "C" int re4dc_actor_texture_acquire(')
    return r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#include <cstdint>
#define RE4DC_ACTOR_TEX_PREP 1
#define RE4DC_ACTOR_TEX_PREP_DIAG 1
#include "actor_tex_prep.h"
#include "actor_resource_lease.h"
struct Key {unsigned crc=0,fnv=0;bool operator==(const Key& o)const{return crc==o.crc&&fnv==o.fnv;}};
namespace re4dc { namespace texture {constexpr unsigned kArgb4444=2;} }
struct Package {
 bool complete=true;unsigned char* address=reinterpret_cast<unsigned char*>(128);
 struct Header {unsigned texture_count=1;} h;
 struct Texture {unsigned width=512,height=512,format=1;} t;
 bool upload_complete()const{return complete;}const Header& header()const{return h;}
 const Texture* textures()const{return &t;}const void* pvr_texture(unsigned)const{return address;}
 unsigned vram_bytes()const{return 89440;}
};
struct Entry {bool valid=true;Key key{};unsigned frame=0;Package package;};
Entry entries[5];unsigned frame=100,variant=0,vram_claims=0,loads=0,failures=0,forbid=99;bool prior_preload=false,plan_ok=true;
bool frame_ready=true,stream_scene=false,stream_retire=false,stream_aborted=false,direct_open=false;
Re4dcActorTexBatch planned;
re4dc_actor::TextureLeases<5> actor_texture_leases;
extern "C" unsigned re4dc_ganado_tex_variant(){return variant;}
extern "C" int re4dc_actor_tex_enumerate(Re4dcActorTexBatch* b){*b=planned;return plan_ok;}
unsigned long long timer_us_gettime64(){static unsigned long long clock;return ++clock;}
extern "C" void re4dc_log(const char*,...){}
#define RE4DC_TEXCHK_FAIL(key,why) (++failures)
Entry* load(const Re4dcUiImage&,bool pin,const Key* key){
 assert(prior_preload && !stream_scene && !stream_retire && !stream_aborted && !direct_open && !vram_claims);++loads;
 for(unsigned i=0;i<5;++i)if(entries[i].key==*key){if(i==forbid){++failures;return nullptr;}if(pin)entries[i].frame=frame;return entries+i;}
 return nullptr;
}
#include "native_ui_actor_tex_prep.inc"
''' + acquire + r'''
unsigned checks;
void check(bool x){if(!x)std::fprintf(stderr,"loader check %u failed\n",checks+1);assert(x);++checks;}
void reset(){
 actor_texture_leases.retire_frame();actor_tex_prepared_count=0;planned={};planned.count=2;planned.candidates=2;planned.qualified=2;
 planned.source.frame=99;planned.source.room=0x101;planned.source.room_generation=3;
 variant=vram_claims=loads=failures=0;forbid=99;frame_ready=true;stream_scene=stream_retire=stream_aborted=direct_open=false;plan_ok=true;
 for(unsigned i=0;i<5;++i){entries[i]={};entries[i].key={100+i,200+i};entries[i].frame=frame-1;}
 for(unsigned i=0;i<planned.count;++i)planned.picks[i]={{reinterpret_cast<void*>(128+i),nullptr,512,512,6,~0u,0},100+i,200+i,1u<<i,0};
 prior_preload=true;
}
void pure_leases(){unsigned char before[sizeof actor_texture_leases];std::memcpy(before,&actor_texture_leases,sizeof before);
 actor_texture_prepare();check(!std::memcmp(before,&actor_texture_leases,sizeof before));}
int main(){
 reset();pure_leases();check(loads==2&&!failures&&entries[0].frame==frame&&entries[1].frame==frame);
 check(!actor_texture_leases.pinned(0)&&!actor_texture_leases.pinned(1));
 Re4dcActorTextureLease ticket{};check(re4dc_actor_texture_acquire(&planned.picks[0].image,100,200,&ticket));
 check(actor_texture_leases.pinned(0)&&ticket.serial&&actor_tex_prepared[0].binds==1);actor_texture_leases.release(ticket);
 reset();frame_ready=false;pure_leases();check(!loads);
 reset();stream_scene=true;pure_leases();check(!loads);
 reset();stream_retire=true;pure_leases();check(!loads);
 reset();stream_aborted=true;pure_leases();check(!loads);
 reset();direct_open=true;pure_leases();check(!loads);
 reset();vram_claims=1;pure_leases();check(!loads);
 reset();plan_ok=false;pure_leases();check(!loads);
 reset();variant=1;pure_leases();check(!loads);
 reset();forbid=0;pure_leases();check(loads==2&&failures==1&&entries[0].frame==frame-1&&entries[1].frame==frame);
 // A preparation failure remains a failure; the normal later lease can retry.
 forbid=99;check(re4dc_actor_texture_acquire(&planned.picks[0].image,100,200,&ticket));actor_texture_leases.release(ticket);
 reset();entries[0].package.t.width=256;pure_leases();check(failures==1&&actor_tex_prepared_count==1);
 reset();entries[0].package.t.format=3;pure_leases();check(failures==1&&actor_tex_prepared_count==1);
 reset();entries[0].package.h.texture_count=2;pure_leases();check(failures==1&&actor_tex_prepared_count==1);
 reset();entries[0].package.complete=false;pure_leases();check(failures==1&&actor_tex_prepared_count==1);
 reset();entries[0].package.address=nullptr;pure_leases();check(failures==1&&actor_tex_prepared_count==1);
 std::printf("actor texture loader: %u checks, pre-scene pins and unchanged lease authority PASS\n",checks);
}
'''


def run_harness(name, source, defines=()):
    with tempfile.TemporaryDirectory(prefix="re4-actor-tex-") as directory:
        directory = Path(directory)
        cpp, exe = directory / (name + ".cpp"), directory / name
        cpp.write_text(source)
        command = [os.environ.get("CXX", "g++"), "-std=c++17", "-O2", "-Wall", "-Wextra",
                   "-Wno-misleading-indentation", "-I", str(INC), "-I", str(GAME),
                   *defines, str(cpp), "-o", str(exe)]
        subprocess.run(command, check=True)
        subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    for mode in (0, 1, 2):
        run_harness(f"material_record{mode}", material_harness(),
                    (f"-DRE4DC_ACTOR_MATERIAL_RECORD={mode}",))
    run_harness("ledger", ledger_harness())
    run_harness("mapping", mapping_harness())
    run_harness("loader", loader_harness())
