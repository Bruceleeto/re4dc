// Extends the existing scrTbl publication with serial witnesses only. No
// second object table or native renderer allocation is created.
#include "re4dc_platform.h"
#include "source_world_memory.inc"
namespace {
constexpr unsigned kSourceWorldWorks=90;
unsigned sourceWorldSerial[kSourceWorldWorks]{};
cSmd* sourceWorldSmd;
unsigned sourceWorldRoomGeneration;
extern "C" int re4dc_room4_state(unsigned*,unsigned*,unsigned*,unsigned*,unsigned*);
extern "C" int re4dc_model_owned_source(const void*,unsigned);
unsigned sourceWorldRoom() {
    unsigned generation=0,c,b,s,r;
    return re4dc_room4_state(&generation,&c,&b,&s,&r)?generation:0;
}
void sourceWorldScrollClear() {
    sourceWorldSmd=nullptr;sourceWorldRoomGeneration=0;
    for(auto& serial:sourceWorldSerial)serial=0;
}
void sourceWorldScrollBind(unsigned work,cObj* object) {
    if(!pG || G_ROOM_ID!=0x200 || !pSmd || reinterpret_cast<unsigned long>(pSmd)%alignof(cSmd) ||
       !re4dc_model_owned_source(pSmd,0x10+kSourceWorldWorks*sizeof(SmdWork)) || pSmd->Flag ||
       pSmd->nModel!=kSourceWorldWorks || nScrWork!=int(kSourceWorldWorks) ||
       work>=kSourceWorldWorks || !re4dc_source_world_pool(object,0) ||
       (object->be_flag&0x201)!=1)return;
    const unsigned generation=sourceWorldRoom();if(!generation)return;
    if(sourceWorldSmd!=pSmd || sourceWorldRoomGeneration!=generation)sourceWorldScrollClear();
    sourceWorldSmd=pSmd;sourceWorldRoomGeneration=generation;
    sourceWorldSerial[work]=object->serial;
}
bool sourceWorldRange(const void* p,unsigned bytes,unsigned alignment=4) {
    return p && reinterpret_cast<unsigned long>(p)%alignment==0 && re4dc_model_owned_source(p,bytes)!=0;
}
bool sourceWorldVec(const Vec& a,const Vec& b){return a.x==b.x && a.y==b.y && a.z==b.z;}
}
#if RE4DC_PS2_WORLD_TRANSITION_OWNER
namespace {
unsigned sourceWorldMemberField;
bool sourceWorldMemberTest(bool valid,unsigned field){if(!valid)sourceWorldMemberField=field;return valid;}
}
#define RE4DC_MEMBER_TEST(test,field) sourceWorldMemberTest((test),(field))
#else
#define RE4DC_MEMBER_TEST(test,field) (test)
#endif
extern "C" int re4dc_scroll_source_member(cModel* model,unsigned serial,unsigned* index) {
#if RE4DC_PS2_WORLD_TRANSITION_OWNER
    sourceWorldMemberField=0;
#endif
    if(!RE4DC_MEMBER_TEST(model,1) || !RE4DC_MEMBER_TEST(index,2) || !RE4DC_MEMBER_TEST(pG,3) ||
       !RE4DC_MEMBER_TEST(G_ROOM_ID==0x200,4) || !RE4DC_MEMBER_TEST(serial,5) ||
       !RE4DC_MEMBER_TEST(sourceWorldRoomGeneration,6) || !RE4DC_MEMBER_TEST(sourceWorldRoom()==sourceWorldRoomGeneration,7) ||
       !RE4DC_MEMBER_TEST(pSmd==sourceWorldSmd,8) || !RE4DC_MEMBER_TEST(sourceWorldRange(pSmd,0x10+kSourceWorldWorks*sizeof(SmdWork),alignof(cSmd)),9) ||
       !RE4DC_MEMBER_TEST(!pSmd->Flag,10) || !RE4DC_MEMBER_TEST(pSmd->nModel==kSourceWorldWorks,11) ||
       !RE4DC_MEMBER_TEST(nScrWork==int(kSourceWorldWorks),12) ||
       !RE4DC_MEMBER_TEST(sourceWorldAllocated(scrTbl,kSourceWorldWorks*sizeof(cObj*),true),13) ||
       !RE4DC_MEMBER_TEST(re4dc_source_world_pool(model,0),14))return 0;
    // The table can retain a destroyed pool address. The publication serial,
    // checked before any info/part dereference, refuses that address's new life.
    unsigned found=kSourceWorldWorks;
    for(unsigned i=0;i<kSourceWorldWorks;++i)if(scrTbl[i]==model) {
        if(!RE4DC_MEMBER_TEST(found==kSourceWorldWorks,15) || !RE4DC_MEMBER_TEST(sourceWorldSerial[i]==serial,16))return 0;
        found=i;
    }
    if(!RE4DC_MEMBER_TEST(found!=kSourceWorldWorks,17) || !RE4DC_MEMBER_TEST(model->serial==serial,18) ||
       !RE4DC_MEMBER_TEST(model->kindid==2,19) || !RE4DC_MEMBER_TEST((model->be_flag&0x201)==1,20) ||
       !RE4DC_MEMBER_TEST(static_cast<cObj*>(model)->blk==-1,21) ||
       !RE4DC_MEMBER_TEST(model->invisible_factor==1.f,22) || !RE4DC_MEMBER_TEST(model->invisible_factor2==1.f,23))return 0;
    const auto& w=pSmd->work[found];
    if(!RE4DC_MEMBER_TEST(w.id!=0xff,24) || !RE4DC_MEMBER_TEST(w.binNo!=0xff,25) ||
       !RE4DC_MEMBER_TEST(!(w.flags&0x10),26) || !RE4DC_MEMBER_TEST(w.motNo==0xff,27) ||
       !RE4DC_MEMBER_TEST(sourceWorldVec(model->pos,w.pos),28) || !RE4DC_MEMBER_TEST(sourceWorldVec(model->ang,w.rot),29) ||
       !RE4DC_MEMBER_TEST(sourceWorldVec(model->scale,w.scale),30))return 0;
    const auto base=reinterpret_cast<unsigned long>(pSmd);
    if(!RE4DC_MEMBER_TEST(pSmd->BinTblOfs<=0x200000U,31))return 0;
    const auto* table=reinterpret_cast<const u32*>(base+pSmd->BinTblOfs);
    if(!RE4DC_MEMBER_TEST(sourceWorldRange(table,(unsigned(w.binNo)+1U)*sizeof(u32)),32) ||
       !RE4DC_MEMBER_TEST(table[w.binNo]<=0x200000U,33))return 0;
    const auto* data=reinterpret_cast<const ModelData*>(reinterpret_cast<unsigned long>(table)+table[w.binNo]);
    const auto* info=model->pModelInfo;
    if(!RE4DC_MEMBER_TEST(re4dc_source_world_pool(info,2),34) || !RE4DC_MEMBER_TEST((info->be_flag&0x201)==1,35) ||
       !RE4DC_MEMBER_TEST(info->invisible_factor==1.f,36) || !RE4DC_MEMBER_TEST(info->color[3]==255,37) ||
       !RE4DC_MEMBER_TEST(!info->pList,38) || !RE4DC_MEMBER_TEST(info->pData==data,39) ||
       !RE4DC_MEMBER_TEST(sourceWorldRange(data,sizeof(ModelData),alignof(ModelData)),40) ||
       !RE4DC_MEMBER_TEST(info->be_flag&8,41) || !RE4DC_MEMBER_TEST(!(info->be_flag&2),42) ||
       !RE4DC_MEMBER_TEST(!data->shapeOfs,43) || !RE4DC_MEMBER_TEST(data->nParts==1,44) ||
       !RE4DC_MEMBER_TEST(model->nParts==1,45) || !RE4DC_MEMBER_TEST(sourceWorldRange(data->pHead,sizeof(ModelDataHead)),46))return 0;
    // This first candidate covers unchanged one-joint room meshes only. An
    // animated gate, a changed hierarchy or an added model stays source-owned.
    const auto* part=model->pList;const auto& rest=*data->pHead;
    if(!RE4DC_MEMBER_TEST(re4dc_source_world_pool(part,3),47) || !RE4DC_MEMBER_TEST((part->be_flag&0x201)==1,48) ||
       !RE4DC_MEMBER_TEST(!part->pList,49) || !RE4DC_MEMBER_TEST(part->pParent==model,50) ||
       !RE4DC_MEMBER_TEST(rest.parentNo==0xff,51) || !RE4DC_MEMBER_TEST(sourceWorldVec(part->pos,rest.center),52) ||
       !RE4DC_MEMBER_TEST(part->ang.x==0.f,53) || !RE4DC_MEMBER_TEST(part->ang.y==0.f,54) || !RE4DC_MEMBER_TEST(part->ang.z==0.f,55) ||
       !RE4DC_MEMBER_TEST(part->scale.x==1.f,56) || !RE4DC_MEMBER_TEST(part->scale.y==1.f,57) || !RE4DC_MEMBER_TEST(part->scale.z==1.f,58))return 0;
    *index=found;return 1;
}
#undef RE4DC_MEMBER_TEST
extern "C" int re4dc_scroll_source_probe(cModel* model,unsigned* serial,unsigned* work) {
    // Other ModelRender callbacks can share these OTs. Establish their source
    // pool publication before even inspecting kind/visibility; never nominate
    // a raw callback payload merely because it points somewhere in RAM.
    if(!serial || !work ||
       (!re4dc_source_world_pool(model,0) && !re4dc_source_world_pool(model,1))){
#if RE4DC_PS2_WORLD_TRANSITION_OWNER
        sourceWorldMemberField=60;
#endif
        return -1;
    }
    if((model->be_flag&0x201)!=1){
#if RE4DC_PS2_WORLD_TRANSITION_OWNER
        sourceWorldMemberField=61;
#endif
        return -1;
    }
    if(model->kindid!=2 || model->invisible_factor*model->invisible_factor2==0.f)return 0;
    const unsigned current=model->serial;
    if(!re4dc_scroll_source_member(model,current,work))return -1;
    *serial=current;return 1;
}

#if RE4DC_PS2_WORLD_TRANSITION_OWNER
extern "C" unsigned re4dc_scroll_source_member_field(){return sourceWorldMemberField;}
// Original r200 authored group qualification and bounded publication witnesses.
// The raw source signature is checked before relocation. Only metadata is kept;
// no source model, material, texture or geometry array is copied.
#include "re4dc_platform.h"
#include "source_world_memory.inc"
#include "source_world_r200_profile.h"
#include "tpl.h"
namespace {
namespace r200p=source_world_r200_profile;
struct R200ScrollWitness { cModel* model; cModelInfo* info; cParts* part; unsigned serial,hash; };
R200ScrollWitness r200ScrollWitness[r200p::works]{};
cSmd* r200Smd;
cSmx* r200Smx;
unsigned r200ScrollGeneration,r200SmdHeaderHash;
bool r200RawQualified,r200ScrollPublished;
extern "C" int re4dc_room4_state(unsigned*,unsigned*,unsigned*,unsigned*,unsigned*);
extern "C" int re4dc_model_owned_source(const void*,unsigned);
unsigned r200RoomGeneration() {
    unsigned g=0,c,b,s,r;return re4dc_room4_state(&g,&c,&b,&s,&r)?g:0;
}
bool r200Range(const void* p,unsigned bytes,unsigned alignment=4) {
    return p && bytes && reinterpret_cast<unsigned long>(p)%alignment==0 &&
        re4dc_model_owned_source(p,bytes)!=0;
}
unsigned r200Hash(const void* ptr,unsigned bytes,unsigned h=2166136261U) {
    const auto* p=static_cast<const unsigned char*>(ptr);
    while(bytes--)h=(h^*p++)*16777619U;
    return h;
}
template<class T> void r200HashValue(unsigned& h,const T& value) { h=r200Hash(&value,sizeof(value),h); }
bool r200Vec(const Vec& a,const Vec& b){return a.x==b.x && a.y==b.y && a.z==b.z;}
bool r200Phase(float p){return p==p && p>=-3.402823466e38F && p<=3.402823466e38F;}
void sourceWorldR200ScrollClear() {
    r200Smd=nullptr;r200Smx=nullptr;r200ScrollGeneration=0;
    r200RawQualified=false;r200ScrollPublished=false;r200SmdHeaderHash=0;
    for(auto& w:r200ScrollWitness)w={};
}
void sourceWorldR200Qualify() {
    sourceWorldR200ScrollClear();
    if(!pG || G_ROOM_ID!=r200p::room || nScrWork!=int(r200p::works) ||
       !r200Range(pSmd,r200p::smd_bytes,alignof(cSmd)) ||
       !r200Range(pSmx,r200p::smx_bytes,alignof(cSmx)) ||
       pSmd->Version!=0x40 || pSmd->Flag || pSmd->nModel!=r200p::works || pSmx->nWork!=54 ||
       r200Hash(pSmd,r200p::smd_bytes)!=r200p::smd_fnv ||
       r200Hash(pSmx,r200p::smx_bytes)!=r200p::smx_fnv)return;
    const unsigned generation=r200RoomGeneration();if(!generation)return;
    r200Smd=pSmd;r200Smx=pSmx;r200ScrollGeneration=generation;
    r200SmdHeaderHash=r200Hash(pSmd,16);r200RawQualified=true;
}
bool r200ScrollBase(bool deep) {
    return r200RawQualified && pG && G_ROOM_ID==r200p::room &&
        r200ScrollGeneration && r200RoomGeneration()==r200ScrollGeneration &&
        pSmd==r200Smd && pSmx==r200Smx && nScrWork==int(r200p::works) &&
        r200Range(pSmd,0x10+r200p::works*sizeof(SmdWork),alignof(cSmd)) &&
        pSmd->Version==0x40 && !pSmd->Flag && pSmd->nModel==r200p::works &&
        r200Hash(pSmd,16)==r200SmdHeaderHash &&
        sourceWorldAllocated(scrTbl,r200p::works*sizeof(cObj*),true) &&
        (!deep || (r200Range(pSmx,r200p::smx_bytes,alignof(cSmx)) &&
          r200Hash(pSmx,r200p::smx_bytes)==r200p::smx_fnv &&
          r200Hash(pSmd->work,r200p::works*sizeof(SmdWork))==r200p::works_fnv));
}
bool r200Texture(TEXPalette* palette,unsigned id,unsigned& hash) {
    if(!r200Range(palette,sizeof(TEXPalette),alignof(TEXPalette)) ||
       !palette->numDescriptors || palette->numDescriptors>1024 || id>=palette->numDescriptors ||
       !r200Range(palette->descriptorArray,palette->numDescriptors*sizeof(TEXDescriptor),alignof(TEXDescriptor)))return false;
    r200HashValue(hash,*palette);
    const auto& d=palette->descriptorArray[id];r200HashValue(hash,d);
    if(!r200Range(d.textureHeader,sizeof(TEXHeader),alignof(TEXHeader)))return false;
    r200HashValue(hash,*d.textureHeader);
    if(d.CLUTHeader) {
        if(!r200Range(d.CLUTHeader,sizeof(CLUTHeader),alignof(CLUTHeader)))return false;
        r200HashValue(hash,*d.CLUTHeader);
    }
    return true;
}
bool r200MaterialTexture(const cModelInfo* info,unsigned id,unsigned& hash) {
    auto* palette=static_cast<TEXPalette*>(info->tpl_addr);
    if(!r200Range(palette,sizeof(TEXPalette),alignof(TEXPalette)))return false;
    if(id<palette->numDescriptors)return r200Texture(palette,id,hash);
    id-=palette->numDescriptors;
    return id<info->nAddTex && r200Texture(info->pAddTpl,id,hash);
}
bool r200ScrollFingerprint(unsigned work,cModel* model,unsigned& hash) {
    if(work>=r200p::works || !re4dc_source_world_pool(model,0))return false;
    const auto& w=pSmd->work[work];const auto& witness=r200ScrollWitness[work];
    if(w.id==0xff || w.binNo==0xff || (w.flags&0x10) || w.motNo!=0xff ||
       witness.model!=model || scrTbl[work]!=model || !witness.serial || model->serial!=witness.serial ||
       model->kindid!=2 || model->type || (model->be_flag&0x207)!=7 ||
       static_cast<cObj*>(model)->blk!=-1 || model->invisible_factor!=1.f || model->invisible_factor2!=1.f ||
       model->pMotion || model->pTexChg || model->Shader_type || model->nParts!=1 ||
       !r200Vec(model->pos,w.pos) || !r200Vec(model->ang,w.rot) || !r200Vec(model->scale,w.scale))return false;
    if(pSmd->BinTblOfs>r200p::smd_bytes ||
       (unsigned(w.binNo)+1U)*sizeof(u32)>r200p::smd_bytes-pSmd->BinTblOfs)return false;
    const auto* table=reinterpret_cast<const u32*>(reinterpret_cast<unsigned long>(pSmd)+pSmd->BinTblOfs);
    if(!r200Range(table,(unsigned(w.binNo)+1U)*sizeof(u32)) || table[w.binNo]>r200p::smd_bytes)return false;
    const auto* data=reinterpret_cast<const ModelData*>(reinterpret_cast<unsigned long>(table)+table[w.binNo]);
    const auto* info=model->pModelInfo;const auto* part=model->pList;
    if(info!=witness.info || part!=witness.part || !re4dc_source_world_pool(info,2) ||
       !re4dc_source_world_pool(part,3) || (info->be_flag&0x201)!=1 || !(info->be_flag&8) ||
       (info->be_flag&2) || info->pData!=data || info->pList || info->pShape ||
       info->invisible_factor!=1.f || info->color[3]!=255 || info->pTexAnim || info->texBlendTbl ||
       info->flagsDC!=((work==10 || work==16)?1:0) || !r200Phase(info->uvU) || !r200Phase(info->uvV) ||
       (work!=10 && work!=16 && (info->uvU!=0.f || info->uvV!=0.f)) ||
       !r200Range(data,sizeof(ModelData),alignof(ModelData)) || data->shapeOfs || data->nParts!=1 ||
       !data->displist_num || data->displist_num>1024 || !r200Range(data->pHead,sizeof(ModelDataHead)) ||
       (part->be_flag&0x201)!=1 || part->pList || part->pParent!=model || data->pHead->parentNo!=0xff ||
       !r200Vec(part->pos,data->pHead->center) || part->ang.x!=0.f || part->ang.y!=0.f || part->ang.z!=0.f ||
       part->scale.x!=1.f || part->scale.y!=1.f || part->scale.z!=1.f)return false;
    // Authored OT role, blend, depth/cull, material and bind matrices must remain.
    // UV phases alone are live and are sampled from ids16/10 at their exact color callbacks.
    hash=2166136261U;
#define R200_HASH(value) r200HashValue(hash,value)
    R200_HASH(model->be_flag);R200_HASH(info->be_flag);
    R200_HASH(model->pParent);R200_HASH(model->mat);R200_HASH(model->l_mat);
    R200_HASH(model->ot_type);R200_HASH(model->z_mode);R200_HASH(model->CullMode);
    R200_HASH(model->alpha_omit);R200_HASH(model->TevScaleGroup);
    R200_HASH(model->AddAmb_r);R200_HASH(model->AddAmb_g);R200_HASH(model->AddAmb_b);
    R200_HASH(model->LightInfo.SelectMask);R200_HASH(part->mat);R200_HASH(part->l_mat);
    R200_HASH(part->lt_inv_mat);R200_HASH(part->addRot);R200_HASH(part->motParts.flags);
    R200_HASH(info->tpl_addr);R200_HASH(info->pAddTpl);R200_HASH(info->nAddTex);
    R200_HASH(info->mat);R200_HASH(info->color);R200_HASH(info->color2);
    R200_HASH(info->blend_mode);R200_HASH(info->blendRatio);R200_HASH(info->blendType);
    R200_HASH(info->anm_no);R200_HASH(info->uvScrollU);R200_HASH(info->uvScrollV);
    R200_HASH(*data);R200_HASH(*data->pHead);
    const ModelPart* material=data->pParts;
    for(unsigned i=0;i<data->displist_num;++i) {
        if(!r200Range(material,sizeof(ModelPart),alignof(ModelPart)) ||
           material->size>r200p::smd_bytes ||
           !r200Range(material,sizeof(ModelPart)+material->size,alignof(ModelPart)))return false;
        R200_HASH(*material);
        if(!r200MaterialTexture(info,material->texId,hash) ||
           ((material->flags&1) && !r200MaterialTexture(info,material->bumpTex,hash)) ||
           ((material->flags&4) && !r200MaterialTexture(info,material->alphaTex,hash)) ||
           ((material->flags&16) && !r200MaterialTexture(info,material->specTexOrg,hash)))return false;
        material=reinterpret_cast<const ModelPart*>(reinterpret_cast<unsigned long>(material)+sizeof(ModelPart)+material->size);
    }
#undef R200_HASH
    return true;
}
void sourceWorldR200ScrollBind(unsigned work,cObj* object) {
    r200ScrollPublished=false;
    if(!r200ScrollBase(false) || work>=r200p::works || !re4dc_source_world_pool(object,0) ||
       (object->be_flag&0x201)!=1 || !object->serial)return;
    r200ScrollWitness[work]={object,object->pModelInfo,object->pList,object->serial,0};
}
void sourceWorldR200ScrollPublish() {
    r200ScrollPublished=false;if(!r200ScrollBase(true))return;
    for(unsigned i=0;i<r200p::works;++i) {
        for(unsigned j=0;j<i;++j)if(scrTbl[i]==scrTbl[j])return;
        unsigned hash=0;if(!r200ScrollFingerprint(i,scrTbl[i],hash))return;
        r200ScrollWitness[i].hash=hash;
    }
    r200ScrollPublished=true;
}
}
extern "C" int re4dc_r200_scroll_storage_current() {
    // Address/owner proof survives a safe admission decline. Do not require
    // pose/material equality: ordinary live source rendering may still proceed.
    if(!r200ScrollPublished || !r200ScrollBase(false) ||
       !r200Range(pSmd,r200p::smd_bytes,alignof(cSmd)) ||
       !r200Range(pSmx,r200p::smx_bytes,alignof(cSmx)))return 0;
    for(unsigned i=0;i<r200p::works;++i){
        const auto& w=r200ScrollWitness[i];
        if(scrTbl[i]!=w.model || !re4dc_source_world_pool(w.model,0) ||
           w.model->serial!=w.serial || w.model->pModelInfo!=w.info || w.model->pList!=w.part ||
           !re4dc_source_world_pool(w.info,2) || !re4dc_source_world_pool(w.part,3))return 0;
        const auto* data=w.info->pData;
        if(w.info->pList || w.part->pList || !r200Range(data,sizeof(ModelData),alignof(ModelData)) ||
           !r200Range(data->pHead,sizeof(ModelDataHead)) || !data->displist_num || data->displist_num>1024 ||
           !r200Range(data->pParts,data->displist_num*sizeof(ModelPart),alignof(ModelPart)))return 0;
        unsigned ignored=2166136261U;
        for(unsigned j=0;j<data->displist_num;++j)
            if(!r200MaterialTexture(w.info,data->pParts[j].texId,ignored))return 0;
    }
    return 1;
}
extern "C" int re4dc_r200_scroll_group() {
    if(!r200ScrollPublished || !r200ScrollBase(true))return 0;
    for(unsigned i=0;i<r200p::works;++i) {
        for(unsigned j=0;j<i;++j)if(scrTbl[i]==scrTbl[j])return 0;
        unsigned hash=0;if(!r200ScrollFingerprint(i,scrTbl[i],hash) || hash!=r200ScrollWitness[i].hash)return 0;
    }
    return 1;
}
extern "C" int re4dc_r200_scroll_member(cModel* model,unsigned serial,unsigned work,float* uv) {
    if(!r200ScrollPublished || !r200ScrollBase(false) || work>=r200p::works ||
       r200ScrollWitness[work].serial!=serial)return 0;
    unsigned hash=0;if(!r200ScrollFingerprint(work,model,hash) || hash!=r200ScrollWitness[work].hash)return 0;
    if(uv){uv[0]=model->pModelInfo->uvU;uv[1]=model->pModelInfo->uvV;}
    return 1;
}
extern "C" int re4dc_r200_scroll_probe(cModel* model,unsigned* serial,unsigned* work) {
    if(!serial || !work || !r200ScrollPublished || !r200ScrollBase(false))return -1;
    // Pointer comparison first; other model payloads require a live pool slot.
    for(unsigned i=0;i<r200p::works;++i)if(r200ScrollWitness[i].model==model) {
        *work=i;*serial=r200ScrollWitness[i].serial;
        return re4dc_r200_scroll_member(model,*serial,i,nullptr)?1:-1;
    }
    if(!re4dc_source_world_pool(model,0) && !re4dc_source_world_pool(model,1))return -1;
    return (model->be_flag&0x207)!=7 || model->kindid==2?-1:0;
}
extern "C" int re4dc_r200_scroll_pointers(cModel** out,unsigned count) {
    if(!out || count!=r200p::works || !r200ScrollPublished || !r200ScrollBase(false))return 0;
    for(unsigned i=0;i<count;++i)out[i]=r200ScrollWitness[i].model;
    return 1;
}
extern "C" int re4dc_r200_scroll_pointer(const cModel* model) {
    // No dereference: keeps retired source addresses suppressed after failure.
    for(const auto& witness:r200ScrollWitness)if(witness.model==model)return 1;
    return 0;
}

extern "C" int re4dc_scroll_source_transition_member(cModel* model,unsigned serial,unsigned* work,unsigned* reason) {
    if(reason)*reason=0;
    unsigned found=~0U,current=0;
    if(re4dc_r200_scroll_probe(model,&current,&found)!=1 || current!=serial || !work){
        if(reason)*reason=101;return 0;
    }
    *work=found;return 1;
}
#endif
