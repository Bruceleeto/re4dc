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
extern "C" int re4dc_scroll_source_member(cModel* model,unsigned serial,unsigned* index) {
    if(!model || !index || !pG || G_ROOM_ID!=0x200 || !serial ||
       !sourceWorldRoomGeneration || sourceWorldRoom()!=sourceWorldRoomGeneration ||
       pSmd!=sourceWorldSmd || !sourceWorldRange(pSmd,0x10+kSourceWorldWorks*sizeof(SmdWork),alignof(cSmd)) ||
       pSmd->Flag || pSmd->nModel!=kSourceWorldWorks || nScrWork!=int(kSourceWorldWorks) ||
       !sourceWorldAllocated(scrTbl,kSourceWorldWorks*sizeof(cObj*),true) ||
       !re4dc_source_world_pool(model,0))return 0;
    // The table can retain a destroyed pool address. The publication serial,
    // checked before any info/part dereference, refuses that address's new life.
    unsigned found=kSourceWorldWorks;
    for(unsigned i=0;i<kSourceWorldWorks;++i)if(scrTbl[i]==model) {
        if(found!=kSourceWorldWorks || sourceWorldSerial[i]!=serial)return 0;
        found=i;
    }
    if(found==kSourceWorldWorks || model->serial!=serial || model->kindid!=2 ||
       (model->be_flag&0x201)!=1 || static_cast<cObj*>(model)->blk!=-1 ||
       model->invisible_factor!=1.f || model->invisible_factor2!=1.f)return 0;
    const auto& w=pSmd->work[found];
    if(w.id==0xff || w.binNo==0xff || (w.flags&0x10) || w.motNo!=0xff ||
       !sourceWorldVec(model->pos,w.pos) || !sourceWorldVec(model->ang,w.rot) ||
       !sourceWorldVec(model->scale,w.scale))return 0;
    const auto base=reinterpret_cast<unsigned long>(pSmd);
    if(pSmd->BinTblOfs>0x200000U)return 0;
    const auto* table=reinterpret_cast<const u32*>(base+pSmd->BinTblOfs);
    if(!sourceWorldRange(table,(unsigned(w.binNo)+1U)*sizeof(u32)) || table[w.binNo]>0x200000U)return 0;
    const auto* data=reinterpret_cast<const ModelData*>(reinterpret_cast<unsigned long>(table)+table[w.binNo]);
    const auto* info=model->pModelInfo;
    if(!re4dc_source_world_pool(info,2) || (info->be_flag&0x201)!=1 || info->invisible_factor!=1.f || info->color[3]!=255 || info->pList || info->pData!=data || !sourceWorldRange(data,sizeof(ModelData),alignof(ModelData)) ||
       !(info->be_flag&8) || (info->be_flag&2) || data->shapeOfs ||
       data->nParts!=1 || model->nParts!=1 || !sourceWorldRange(data->pHead,sizeof(ModelDataHead)))return 0;
    // This first candidate covers unchanged one-joint room meshes only. An
    // animated gate, a changed hierarchy or an added model stays source-owned.
    const auto* part=model->pList;const auto& rest=*data->pHead;
    if(!re4dc_source_world_pool(part,3) || (part->be_flag&0x201)!=1 || part->pList || part->pParent!=model || rest.parentNo!=0xff ||
       !sourceWorldVec(part->pos,rest.center) || part->ang.x!=0.f || part->ang.y!=0.f || part->ang.z!=0.f ||
       part->scale.x!=1.f || part->scale.y!=1.f || part->scale.z!=1.f)return 0;
    *index=found;return 1;
}
extern "C" int re4dc_scroll_source_probe(cModel* model,unsigned* serial,unsigned* work) {
    // Other ModelRender callbacks can share these OTs. Establish their source
    // pool publication before even inspecting kind/visibility; never nominate
    // a raw callback payload merely because it points somewhere in RAM.
    if(!serial || !work ||
       (!re4dc_source_world_pool(model,0) && !re4dc_source_world_pool(model,1)))return -1;
    if((model->be_flag&0x201)!=1)return -1;
    if(model->kindid!=2 || model->invisible_factor*model->invisible_factor2==0.f)return 0;
    const unsigned current=model->serial;
    if(!re4dc_scroll_source_member(model,current,work))return -1;
    *serial=current;return 1;
}
