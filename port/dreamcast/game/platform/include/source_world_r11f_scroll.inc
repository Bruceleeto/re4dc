// Original r11f authored group qualification and bounded publication witnesses.
// The raw source signature is checked before relocation. Only metadata is kept;
// no source model, material, texture or geometry array is copied.
#include "re4dc_platform.h"
#include "source_world_memory.inc"
#include "source_world_r11f_profile.h"
#include "tpl.h"
namespace {
namespace r11fp=source_world_r11f_profile;
struct R11fScrollWitness { cModel* model; cModelInfo* info; cParts* part; unsigned serial,hash; };
R11fScrollWitness r11fScrollWitness[r11fp::works]{};
cSmd* r11fSmd;
cSmx* r11fSmx;
unsigned r11fScrollGeneration,r11fSmdHeaderHash;
bool r11fRawQualified,r11fScrollPublished;
extern "C" int re4dc_room4_state(unsigned*,unsigned*,unsigned*,unsigned*,unsigned*);
extern "C" int re4dc_model_owned_source(const void*,unsigned);
unsigned r11fRoomGeneration() {
    unsigned g=0,c,b,s,r;return re4dc_room4_state(&g,&c,&b,&s,&r)?g:0;
}
bool r11fRange(const void* p,unsigned bytes,unsigned alignment=4) {
    return p && bytes && reinterpret_cast<unsigned long>(p)%alignment==0 &&
        re4dc_model_owned_source(p,bytes)!=0;
}
unsigned r11fHash(const void* ptr,unsigned bytes,unsigned h=2166136261U) {
    const auto* p=static_cast<const unsigned char*>(ptr);
    while(bytes--)h=(h^*p++)*16777619U;
    return h;
}
template<class T> void r11fHashValue(unsigned& h,const T& value) { h=r11fHash(&value,sizeof(value),h); }
bool r11fVec(const Vec& a,const Vec& b){return a.x==b.x && a.y==b.y && a.z==b.z;}
bool r11fPhase(float p){return p==p && p>=-3.402823466e38F && p<=3.402823466e38F;}
void sourceWorldR11fScrollClear() {
    r11fSmd=nullptr;r11fSmx=nullptr;r11fScrollGeneration=0;
    r11fRawQualified=false;r11fScrollPublished=false;r11fSmdHeaderHash=0;
    for(auto& w:r11fScrollWitness)w={};
}
void sourceWorldR11fQualify() {
    sourceWorldR11fScrollClear();
    if(!pG || G_ROOM_ID!=r11fp::room || nScrWork!=int(r11fp::works) ||
       !r11fRange(pSmd,r11fp::smd_bytes,alignof(cSmd)) ||
       !r11fRange(pSmx,r11fp::smx_bytes,alignof(cSmx)) ||
       pSmd->Version!=0x40 || pSmd->Flag || pSmd->nModel!=r11fp::works || pSmx->nWork!=21 ||
       r11fHash(pSmd,r11fp::smd_bytes)!=r11fp::smd_fnv ||
       r11fHash(pSmx,r11fp::smx_bytes)!=r11fp::smx_fnv)return;
    const unsigned generation=r11fRoomGeneration();if(!generation)return;
    r11fSmd=pSmd;r11fSmx=pSmx;r11fScrollGeneration=generation;
    r11fSmdHeaderHash=r11fHash(pSmd,16);r11fRawQualified=true;
}
bool r11fScrollBase(bool deep) {
    return r11fRawQualified && pG && G_ROOM_ID==r11fp::room &&
        r11fScrollGeneration && r11fRoomGeneration()==r11fScrollGeneration &&
        pSmd==r11fSmd && pSmx==r11fSmx && nScrWork==int(r11fp::works) &&
        r11fRange(pSmd,0x10+r11fp::works*sizeof(SmdWork),alignof(cSmd)) &&
        pSmd->Version==0x40 && !pSmd->Flag && pSmd->nModel==r11fp::works &&
        r11fHash(pSmd,16)==r11fSmdHeaderHash &&
        sourceWorldAllocated(scrTbl,r11fp::works*sizeof(cObj*),true) &&
        (!deep || (r11fRange(pSmx,r11fp::smx_bytes,alignof(cSmx)) &&
          r11fHash(pSmx,r11fp::smx_bytes)==r11fp::smx_fnv &&
          r11fHash(pSmd->work,r11fp::works*sizeof(SmdWork))==r11fp::works_fnv));
}
bool r11fTexture(TEXPalette* palette,unsigned id,unsigned& hash) {
    if(!r11fRange(palette,sizeof(TEXPalette),alignof(TEXPalette)) ||
       !palette->numDescriptors || palette->numDescriptors>1024 || id>=palette->numDescriptors ||
       !r11fRange(palette->descriptorArray,palette->numDescriptors*sizeof(TEXDescriptor),alignof(TEXDescriptor)))return false;
    r11fHashValue(hash,*palette);
    const auto& d=palette->descriptorArray[id];r11fHashValue(hash,d);
    if(!r11fRange(d.textureHeader,sizeof(TEXHeader),alignof(TEXHeader)))return false;
    r11fHashValue(hash,*d.textureHeader);
    if(d.CLUTHeader) {
        if(!r11fRange(d.CLUTHeader,sizeof(CLUTHeader),alignof(CLUTHeader)))return false;
        r11fHashValue(hash,*d.CLUTHeader);
    }
    return true;
}
bool r11fMaterialTexture(const cModelInfo* info,unsigned id,unsigned& hash) {
    auto* palette=static_cast<TEXPalette*>(info->tpl_addr);
    if(!r11fRange(palette,sizeof(TEXPalette),alignof(TEXPalette)))return false;
    if(id<palette->numDescriptors)return r11fTexture(palette,id,hash);
    id-=palette->numDescriptors;
    return id<info->nAddTex && r11fTexture(info->pAddTpl,id,hash);
}
bool r11fScrollFingerprint(unsigned work,cModel* model,unsigned& hash) {
    if(work>=r11fp::works || !re4dc_source_world_pool(model,0))return false;
    const auto& w=pSmd->work[work];const auto& witness=r11fScrollWitness[work];
    if(w.id==0xff || w.binNo==0xff || (w.flags&0x10) || w.motNo!=0xff ||
       witness.model!=model || scrTbl[work]!=model || !witness.serial || model->serial!=witness.serial ||
       model->kindid!=2 || model->type || (model->be_flag&0x207)!=7 ||
       static_cast<cObj*>(model)->blk!=-1 || model->invisible_factor!=1.f || model->invisible_factor2!=1.f ||
       model->pMotion || model->pTexChg || model->Shader_type || model->nParts!=1 ||
       !r11fVec(model->pos,w.pos) || !r11fVec(model->ang,w.rot) || !r11fVec(model->scale,w.scale))return false;
    if(pSmd->BinTblOfs>r11fp::smd_bytes ||
       (unsigned(w.binNo)+1U)*sizeof(u32)>r11fp::smd_bytes-pSmd->BinTblOfs)return false;
    const auto* table=reinterpret_cast<const u32*>(reinterpret_cast<unsigned long>(pSmd)+pSmd->BinTblOfs);
    if(!r11fRange(table,(unsigned(w.binNo)+1U)*sizeof(u32)) || table[w.binNo]>r11fp::smd_bytes)return false;
    const auto* data=reinterpret_cast<const ModelData*>(reinterpret_cast<unsigned long>(table)+table[w.binNo]);
    const auto* info=model->pModelInfo;const auto* part=model->pList;
    if(info!=witness.info || part!=witness.part || !re4dc_source_world_pool(info,2) ||
       !re4dc_source_world_pool(part,3) || (info->be_flag&0x201)!=1 || !(info->be_flag&8) ||
       (info->be_flag&2) || info->pData!=data || info->pList || info->pShape ||
       info->invisible_factor!=1.f || info->color[3]!=255 || info->pTexAnim || info->texBlendTbl ||
       info->flagsDC!=(work==0?1:0) || !r11fPhase(info->uvU) || !r11fPhase(info->uvV) ||
       (work!=0 && (info->uvU!=0.f || info->uvV!=0.f)) ||
       !r11fRange(data,sizeof(ModelData),alignof(ModelData)) || data->shapeOfs || data->nParts!=1 ||
       !data->displist_num || data->displist_num>1024 || !r11fRange(data->pHead,sizeof(ModelDataHead)) ||
       (part->be_flag&0x201)!=1 || part->pList || part->pParent!=model || data->pHead->parentNo!=0xff ||
       !r11fVec(part->pos,data->pHead->center) || part->ang.x!=0.f || part->ang.y!=0.f || part->ang.z!=0.f ||
       part->scale.x!=1.f || part->scale.y!=1.f || part->scale.z!=1.f)return false;
    // Authored OT role, blend, depth/cull, material and bind matrices must remain.
    // UV phase alone is live and is copied from id0 at its exact color callback.
    hash=2166136261U;
#define R11F_HASH(value) r11fHashValue(hash,value)
    R11F_HASH(model->be_flag);R11F_HASH(info->be_flag);R11F_HASH(part->be_flag);
    R11F_HASH(model->pParent);R11F_HASH(model->mat);R11F_HASH(model->l_mat);
    R11F_HASH(model->ot_type);R11F_HASH(model->z_mode);R11F_HASH(model->CullMode);
    R11F_HASH(model->alpha_omit);R11F_HASH(model->TevScaleGroup);
    R11F_HASH(model->AddAmb_r);R11F_HASH(model->AddAmb_g);R11F_HASH(model->AddAmb_b);
    R11F_HASH(model->LightInfo.SelectMask);R11F_HASH(part->mat);R11F_HASH(part->l_mat);
    R11F_HASH(part->lt_inv_mat);R11F_HASH(part->addRot);R11F_HASH(part->motParts.flags);
    R11F_HASH(info->tpl_addr);R11F_HASH(info->pAddTpl);R11F_HASH(info->nAddTex);
    R11F_HASH(info->mat);R11F_HASH(info->color);R11F_HASH(info->color2);
    R11F_HASH(info->blend_mode);R11F_HASH(info->blendRatio);R11F_HASH(info->blendType);
    R11F_HASH(info->anm_no);R11F_HASH(info->uvScrollU);R11F_HASH(info->uvScrollV);
    R11F_HASH(*data);R11F_HASH(*data->pHead);
    const ModelPart* material=data->pParts;
    for(unsigned i=0;i<data->displist_num;++i) {
        if(!r11fRange(material,sizeof(ModelPart),alignof(ModelPart)) ||
           material->size>r11fp::smd_bytes ||
           !r11fRange(material,sizeof(ModelPart)+material->size,alignof(ModelPart)))return false;
        R11F_HASH(*material);
        if(!r11fMaterialTexture(info,material->texId,hash) ||
           ((material->flags&1) && !r11fMaterialTexture(info,material->bumpTex,hash)) ||
           ((material->flags&4) && !r11fMaterialTexture(info,material->alphaTex,hash)) ||
           ((material->flags&16) && !r11fMaterialTexture(info,material->specTexOrg,hash)))return false;
        material=reinterpret_cast<const ModelPart*>(reinterpret_cast<unsigned long>(material)+sizeof(ModelPart)+material->size);
    }
#undef R11F_HASH
    return true;
}
void sourceWorldR11fScrollBind(unsigned work,cObj* object) {
    r11fScrollPublished=false;
    if(!r11fScrollBase(false) || work>=r11fp::works || !re4dc_source_world_pool(object,0) ||
       (object->be_flag&0x201)!=1 || !object->serial)return;
    r11fScrollWitness[work]={object,object->pModelInfo,object->pList,object->serial,0};
}
void sourceWorldR11fScrollPublish() {
    r11fScrollPublished=false;if(!r11fScrollBase(true))return;
    for(unsigned i=0;i<r11fp::works;++i) {
        for(unsigned j=0;j<i;++j)if(scrTbl[i]==scrTbl[j])return;
        unsigned hash=0;if(!r11fScrollFingerprint(i,scrTbl[i],hash))return;
        r11fScrollWitness[i].hash=hash;
    }
    r11fScrollPublished=true;
}
}
extern "C" int re4dc_r11f_scroll_group() {
    if(!r11fScrollPublished || !r11fScrollBase(true))return 0;
    for(unsigned i=0;i<r11fp::works;++i) {
        for(unsigned j=0;j<i;++j)if(scrTbl[i]==scrTbl[j])return 0;
        unsigned hash=0;if(!r11fScrollFingerprint(i,scrTbl[i],hash) || hash!=r11fScrollWitness[i].hash)return 0;
    }
    return 1;
}
extern "C" int re4dc_r11f_scroll_member(cModel* model,unsigned serial,unsigned work,float* uv) {
    if(!r11fScrollPublished || !r11fScrollBase(false) || work>=r11fp::works ||
       r11fScrollWitness[work].serial!=serial)return 0;
    unsigned hash=0;if(!r11fScrollFingerprint(work,model,hash) || hash!=r11fScrollWitness[work].hash)return 0;
    if(uv){uv[0]=model->pModelInfo->uvU;uv[1]=model->pModelInfo->uvV;}
    return 1;
}
extern "C" int re4dc_r11f_scroll_probe(cModel* model,unsigned* serial,unsigned* work) {
    if(!serial || !work || !r11fScrollPublished || !r11fScrollBase(false))return -1;
    // Pointer comparison first; other model payloads require a live pool slot.
    for(unsigned i=0;i<r11fp::works;++i)if(r11fScrollWitness[i].model==model) {
        *work=i;*serial=r11fScrollWitness[i].serial;
        return re4dc_r11f_scroll_member(model,*serial,i,nullptr)?1:-1;
    }
    if(!re4dc_source_world_pool(model,0) && !re4dc_source_world_pool(model,1))return -1;
    return (model->be_flag&0x207)!=7 || model->kindid==2?-1:0;
}
extern "C" int re4dc_r11f_scroll_pointers(cModel** out,unsigned count) {
    if(!out || count!=r11fp::works || !r11fScrollPublished || !r11fScrollBase(false))return 0;
    for(unsigned i=0;i<count;++i)out[i]=r11fScrollWitness[i].model;
    return 1;
}
extern "C" int re4dc_r11f_scroll_pointer(const cModel* model) {
    // No dereference: keeps retired source addresses suppressed after failure.
    for(const auto& witness:r11fScrollWitness)if(witness.model==model)return 1;
    return 0;
}
