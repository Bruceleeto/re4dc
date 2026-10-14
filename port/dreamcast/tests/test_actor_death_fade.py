#!/usr/bin/env python3
"""Compile the actual transaction, acquire/release and tagged FIFO with injected resource boundaries.
Host evidence for lifecycle/context/predicate contracts; target layout and runtime rendering are separate gates.
"""
from pathlib import Path
import subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
GAME=ROOT/'game'
HEADER=GAME/'platform/include'
CPP=r"""
#include <algorithm>
#include <cassert>
#include <cmath>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <limits>
#include <string>
#include <vector>
#include <sys/mman.h>
#define RE4DC_ACTOR_TRANSACTION 1
#define RE4DC_ACTOR_GANADO_DEATH_FADE 1
#define RE4DC_PS2_GANADO_LIT 1
#define NMR_CENSUS(...)
using u8=unsigned char;
using Mtx=float[3][4];
void identity(Mtx m){std::memset(m,0,sizeof(Mtx));m[0][0]=m[1][1]=m[2][2]=1;}
struct cParts {Mtx mat{};};
class cModelInfo {public:
    cModelInfo* pList=nullptr;void* pData=(void*)0x1000;
    float invisible_factor=1;unsigned blend_mode=0;
    union {u8 color[4];unsigned colorWord=0xffffffffu;};
    unsigned flagsDC=0,nAddTex=0,be_flag=8;
    void* pAddTpl=nullptr;void* texBlendTbl=nullptr;void* pTexAnim=nullptr;
    float uvU=0,uvV=0,uvScrollU=0,uvScrollV=0;Mtx mat{};
};
class cModel {public:
    cParts* pParts=nullptr;cModelInfo* pModelInfo=nullptr;
    unsigned kindid=1,id=0x13,serial=22,ot_type=0,alpha_omit=255,z_mode=0,CullMode=0,Shader_type=0;
    unsigned AddAmb_r=0,AddAmb_g=0,AddAmb_b=0,be_flag=0,TevScaleGroup=0;
    unsigned r_no_0=3,r_no_1=3,r_no_2=1,r_no_3=0;
    float invisible_factor=.7999999523162842f,invisible_factor2=1;
};
class cEm: public cModel {public:short hp=0;};
#include "coarse_actor_transaction.h"
#include "actor_death_fade.h"
struct Global {unsigned Frame_cnt=77,Status_flg[3]{},Disp_flg=0;struct {Mtx v_mat{};}Cam;} global;
Global* pG=&global;u8 gxCsScale[2]{};
re4dc::render::SourceLighting light{},gxlight{};
float gxprojection[7]{},gxviewport[6]{};unsigned fog=1;
void PSMTXConcat(const Mtx a,const Mtx b,Mtx out){for(unsigned i=0;i<3;++i){for(unsigned j=0;j<3;++j){out[i][j]=0;for(unsigned k=0;k<3;++k)out[i][j]+=a[i][k]*b[k][j];}out[i][3]=a[i][3];for(unsigned k=0;k<3;++k)out[i][3]+=a[i][k]*b[k][3];}}
int PSMTXInverse(const Mtx a,Mtx b){identity(b);for(unsigned i=0;i<3;++i)b[i][3]=-a[i][3];return 1;}
void PSMTXTranspose(const Mtx a,Mtx b){for(unsigned i=0;i<3;++i){for(unsigned j=0;j<3;++j)b[i][j]=a[j][i];b[i][3]=0;}}
bool coarse_finite(float f){return std::isfinite(f);}
extern "C" void GXGetProjectionv(float* out){std::memcpy(out,gxprojection,sizeof(gxprojection));}
extern "C" void GXGetViewportv(float* out){std::memcpy(out,gxviewport,sizeof(gxviewport));}
extern "C" void re4dc_gx_model_lighting(re4dc::render::SourceLighting* out){*out=gxlight;}
extern "C" unsigned re4dc_fog_enabled(){return fog;}
extern "C" unsigned re4dc_actor_binding_revision(cModel*);
extern "C" void re4dc_bind_actor_frame(){}
std::string log_text,release_order;
extern "C" void re4dc_log(const char* fmt,...){char b[2048];va_list v;va_start(v,fmt);const int n=vsnprintf(b,sizeof(b),fmt,v);va_end(v);assert(n<256);log_text+=b;}
struct DeferredLighting {void* next;void* lights;};
@@DEFERRED_LAYOUT@@
alignas(32) unsigned char frame_storage[32768],spill_storage[8192];
alignas(4096) unsigned char primitive[262144];
void protect_primitive(){assert(mprotect(primitive,sizeof(primitive),PROT_NONE)==0);}
unsigned deferred_top=sizeof(frame_storage),deferred_peak=0,deferred_count=0,frame_queue_peak=0,nquad=0;
unsigned char* deferred_spill=nullptr;unsigned deferred_spill_top=0,deferred_spill_capacity=0;
DeferredPart* deferred_first=nullptr;DeferredPart* deferred_last=nullptr;
bool draining_parts=false,source_draws_finished=false,direct_open=false,frame_ready=true,stream_aborted=false;
constexpr unsigned PVR_LIST_TR_POLY=2;unsigned draining_list=PVR_LIST_TR_POLY;
unsigned aborts=0,prim_top=sizeof(primitive),binding_revision=1,emits=0,palette_calls=0,certificate_calls=0;
unsigned texture_live=0,workspace_live=0,skin_live=0,resource_serial=0;
bool spill_enabled=true,identity_live=true,certificate_valid=true,choose_fails=false;
enum class Fault {None,TextureFirst,TextureSecond,Workspace,Bank,Pending,Palette,Skin,Lighting,Preflight,Submit,SkinRelease,RetireTexture,RetireSubmit};
Fault fault=Fault::None;
cEm model[2];cParts parts[2];cModelInfo infos[2][4];unsigned choices[2]{};
re4dc_source::FrameIdentity current_frame{77,0x11c,2,3,4,5};
std::vector<unsigned> emitted_order;std::vector<const void*> emitted_infos;
float palette_value=0;std::vector<float> consumed_palette;
re4dc::render::SourceLighting consumed_lighting{};
float consumed_projection[7]{},consumed_viewport[6]{},consumed_mv[12]{};
unsigned consumed_alpha=0,consumed_fog=0;
extern "C" void re4dc_model_packet_abort(){stream_aborted=true;++aborts;}
extern "C" void* re4dc_model_deferred_storage(unsigned* n){*n=spill_enabled?sizeof(spill_storage):0;return spill_enabled?spill_storage:nullptr;}
extern "C" void* re4dc_prim_tail(unsigned n,unsigned reserve){
    if((fault==Fault::Bank && n==65536) || (fault==Fault::Pending && n!=65536) || n>prim_top || prim_top-n<reserve)return nullptr;
    prim_top-=n;return primitive+prim_top;
}
extern "C" int re4dc_actor_transaction_identity(cModel* m,re4dc_source::FrameIdentity* f,re4dc_source::ModelIdentity* id){
    if(!identity_live)return 0;
    if(m!=&model[0] && m!=&model[1])return -1;
    *f=current_frame;*id={reinterpret_cast<std::uintptr_t>(m),m->serial,1};return 1;
}
extern "C" int re4dc_actor_transaction_choice(cModel* m,unsigned* c){if(!identity_live)return 0;*c=choices[m==&model[1]];return 1;}
extern "C" int re4dc_actor_transaction_choose(cModel* m,unsigned c){if(!identity_live || (choose_fails && c==2))return 0;choices[m==&model[1]]=c;return 1;}
extern "C" unsigned re4dc_actor_binding_revision(cModel*){return binding_revision;}
extern "C" int re4dc_actor_stream_state(Re4dcActorStreamState* s){*s={current_frame.frame,aborts,0,0};return !stream_aborted;}
extern "C" int re4dc_actor_texture_acquire(const Re4dcUiImage*,unsigned,unsigned,Re4dcActorTextureLease* t){
    if(fault==Fault::RetireTexture){identity_live=false;re4dc_actor_transaction_retire();std::memset(primitive,0xed,sizeof(primitive));protect_primitive();return 0;}
    if(fault==Fault::TextureFirst || (fault==Fault::TextureSecond && texture_live==1))return 0;
    *t={++texture_live,++resource_serial};return 1;
}
extern "C" void re4dc_actor_texture_release(Re4dcActorTextureLease* t){if(t->serial){assert(texture_live);--texture_live;release_order+='T';}*t={};}
extern "C" void re4dc_actor_texture_retire_all(){texture_live=0;}
extern "C" int re4dc_actor_workspace_acquire(unsigned n,Re4dcActorWorkspaceLease* w){if(fault==Fault::Workspace)return 0;*w={1,++resource_serial,1,n};++workspace_live;return 1;}
extern "C" void re4dc_actor_workspace_release(Re4dcActorWorkspaceLease*);
// A source registry view that must be restored exactly by every probe/drain.
struct SkinView {const void* info;const float* palette;unsigned count;};
SkinView source_skin[4]{},saved_skin[4]{};
extern "C" int re4dc_actor_skin_acquire(unsigned frame,const Re4dcActorSkinBinding* b,unsigned n,Re4dcActorSkinLease* s){
    if(fault==Fault::Skin)return 0;assert(!skin_live && n==4);std::memcpy(saved_skin,source_skin,sizeof(source_skin));
    *s={};s->serial=++resource_serial;s->frame=frame;s->count=n;++skin_live;
    for(unsigned i=0;i<n;++i){source_skin[i]={b[i].info,b[i].palette,b[i].entries};assert(b[i].palette[0]==palette_value);}return 1;
}
extern "C" int re4dc_actor_skin_release(Re4dcActorSkinLease* s){if(s->serial){assert(skin_live==1);--skin_live;std::memcpy(source_skin,saved_skin,sizeof(source_skin));release_order+='S';}*s={};return fault!=Fault::SkinRelease;}
extern "C" void re4dc_actor_owner_retire(){skin_live=0;std::memcpy(source_skin,saved_skin,sizeof(source_skin));}
extern "C" void re4dc_actor_model_frame_retire(){workspace_live=0;}
extern "C" re4dc_source::BlobError re4dc_actor_immutable_chunk_proof(unsigned,const re4dc_source::ChunkInput& c,re4dc_source::ChunkProof& p){p={1,1,3,c.triangles,(c.palette_count*48u+31u)&~31u,128};return re4dc_source::BlobError::None;}
extern "C" int re4dc_actor_material_certificate(cModel*,const Re4dcActorPlan*){++certificate_calls;return certificate_valid;}
int palettes(cModel* m,const Re4dcActorPlan& p,float* const* out){++palette_calls;if(fault==Fault::Palette)return 0;palette_value=m->pParts->mat[0][3];for(unsigned i=0;i<p.count;++i)for(unsigned k=0;k<12;++k)out[i][k]=palette_value;return 1;}
Re4dcActorPlan make_plan(cModel* m){
    Re4dcActorPlan p{};p.count=4;p.appearance=m==&model[1]?3:0;p.palette_bytes=256;p.workspace_bytes=128;p.material_count=2;p.run_count=4;p.palettes=palettes;
    const unsigned who=m==&model[1];static const unsigned char bytes[64]{};
    for(unsigned i=0;i<4;++i){p.info[i]=&infos[who][i];auto& c=p.input[i];c={{bytes,64},{bytes,64},{bytes,64},{bytes,64},{bytes,64},1,1,1,1,34};p.immutable_asset_id[i]=9+i;p.runs[i]={i,i%2,9+i,1,{bytes,64},{bytes,64}};}
    return p;
}
extern "C" int re4dc_actor_plan_leon(cModel*,Re4dcActorPlan*){return 0;}
extern "C" int re4dc_actor_plan_ganado(cModel* m,Re4dcActorPlan* p){*p=make_plan(m);return 1;}
extern "C" int re4dc_actor_preflight_owned_runs(Re4dcModelPart*,const Re4dcActorDrawRun*,unsigned,
    const Re4dcActorOwnedMaterial*,unsigned,const Re4dcActorWorkspaceLease*,const Re4dcActorSkinLease*,const Re4dcActorTextureLease*){return fault!=Fault::Preflight;}
extern "C" int re4dc_actor_submit_owned_runs(Re4dcModelPart* b,const Re4dcActorDrawRun* runs,unsigned n,
    const Re4dcActorOwnedMaterial*,unsigned,const Re4dcActorWorkspaceLease*,const Re4dcActorSkinLease*,const Re4dcActorTextureLease*){
    assert(draining_parts && draining_list==PVR_LIST_TR_POLY && skin_live==1);
    if(fault==Fault::Submit)return -1;
    if(fault==Fault::RetireSubmit){identity_live=false;re4dc_actor_transaction_retire();std::memset(primitive,0xed,sizeof(primitive));protect_primitive();return 1;}
    ++emits;emitted_order.push_back(b->model==&model[1]?101:100);for(unsigned i=0;i<n;++i)emitted_infos.push_back(runs[i].chunk.info);
    consumed_lighting=*b->lighting;consumed_alpha=b->alpha_state;consumed_fog=b->source_key[2];
    std::memcpy(consumed_projection,b->projection,sizeof(consumed_projection));std::memcpy(consumed_viewport,b->viewport,sizeof(consumed_viewport));
    std::memcpy(consumed_mv,runs[0].chunk.modelview,sizeof(consumed_mv));consumed_palette.push_back(palette_value);return 1;
}
#include "coarse_actor_transaction.inc"
extern "C" void re4dc_actor_workspace_release(Re4dcActorWorkspaceLease* w){
    if(w->serial){assert(workspace_live && !skin_live);--workspace_live;release_order+='W';
        if(actor_palette_arena.bound() && fault!=Fault::SkinRelease){re4dc_actor::PaletteLease full{};assert(actor_palette_arena.acquire(65536,full));assert(actor_palette_arena.release(full));}}
    *w={};
}
#undef RE4DC_ACTOR_TRANSACTION_DIAG
#define RE4DC_ACTOR_TRANSACTION_DIAG 1
#include "native_ui_actor_fade.inc"
#undef RE4DC_ACTOR_TRANSACTION_DIAG
#define RE4DC_ACTOR_TRANSACTION_DIAG 0
void reset_case(){
    assert(mprotect(primitive,sizeof(primitive),PROT_READ|PROT_WRITE)==0);
    // Retire without traversing any previous primitive payload, then poison it.
    actor_fade_pending=0;actor_fade_head=nullptr;re4dc_actor_transaction_retire();actor_fade_queue_pending=0;actor_fade_queue_reset();
    std::memset(primitive,0xcd,sizeof(primitive));prim_top=sizeof(primitive);
    deferred_first=deferred_last=nullptr;deferred_top=sizeof(frame_storage);deferred_spill=nullptr;deferred_spill_top=deferred_spill_capacity=0;
    deferred_count=0;nquad=0;draining_parts=source_draws_finished=direct_open=stream_aborted=false;frame_ready=true;draining_list=PVR_LIST_TR_POLY;
    current_frame={77,0x11c,2,3,4,5};global={};pG->Frame_cnt=77;identity(pG->Cam.v_mat);
    texture_live=workspace_live=skin_live=aborts=emits=palette_calls=certificate_calls=0;
    identity_live=certificate_valid=spill_enabled=true;choose_fails=false;fault=Fault::None;binding_revision=1;
    log_text.clear();release_order.clear();emitted_order.clear();emitted_infos.clear();consumed_palette.clear();choices[0]=choices[1]=0;
    gxlight={};gxlight.mask=3;gxlight.enable=1;gxlight.ambient[0]=35;gxlight.lights[0].position[0]=42;gxlight.lights[1].color[1]=71;
    for(unsigned i=0;i<7;++i)gxprojection[i]=float(i+1);for(unsigned i=0;i<6;++i)gxviewport[i]=float(i+10);fog=1;
    for(unsigned j=0;j<2;++j){model[j]={};model[j].serial=22+j;identity(parts[j].mat);parts[j].mat[0][3]=10.0f+j;
        for(unsigned i=0;i<4;++i){infos[j][i]={};identity(infos[j][i].mat);}
        infos[j][2].pList=&infos[j][0];infos[j][0].pList=&infos[j][3];infos[j][3].pList=&infos[j][1];
        model[j].pParts=&parts[j];model[j].pModelInfo=&infos[j][2];}
    for(unsigned i=0;i<4;++i)source_skin[i]={&infos[0][i],reinterpret_cast<const float*>(std::uintptr_t(0x1230+i*32)),9+i};
    std::memcpy(saved_skin,source_skin,sizeof(source_skin));
}
void ordinary(unsigned tag){auto* p=new(frame_storage+(deferred_top-=kActorFadeNode))DeferredPart{};p->lighting=reinterpret_cast<DeferredLighting*>(std::uintptr_t(tag));p->changed[0]=tag;if(deferred_last)deferred_last->next=p;else deferred_first=p;deferred_last=p;++deferred_count;}
void drain_all(){draining_parts=true;while(deferred_first && !stream_aborted){if(actor_fade_drain_head())continue;auto* p=deferred_first;deferred_first=p->next;emitted_order.push_back(p->changed[0]);}draining_parts=false;}
void no_leases(){assert(!texture_live && !workspace_live && !skin_live);assert(!std::memcmp(source_skin,saved_skin,sizeof(source_skin)));}
unsigned checks=0;
void passed(){++checks;}
void predicate_and_alpha(){
    reset_case();const auto p=make_plan(&model[0]);auto before=model[0];
    assert(actor_fade_eligible(&model[0],p) && actor_semantics(&model[0],p));
    assert(!std::memcmp(&model[0],&before,sizeof(before)));
    for(unsigned i=0;i<14;++i){model[0]=before;auto q=p;
        switch(i){case 0:model[0].hp=1;break;case 1:model[0].kindid=0;break;case 2:model[0].id=0x17;break;
        case 3:q.appearance=1;break;case 4:model[0].ot_type=7;break;case 5:model[0].r_no_0=2;break;
        case 6:model[0].r_no_1=2;break;case 7:model[0].r_no_2=0;break;case 8:model[0].r_no_3=1;break;
        case 9:model[0].invisible_factor2=.9f;break;case 10:model[0].alpha_omit=254;break;
        case 11:model[0].invisible_factor=std::numeric_limits<float>::quiet_NaN();break;
        case 12:model[0].invisible_factor=std::numeric_limits<float>::infinity();break;case 13:model[0].invisible_factor=-.1f;break;}
        assert(!actor_fade_eligible(&model[0],q));passed();}
    model[0]=before;model[0].invisible_factor=0;assert(!actor_fade_eligible(&model[0],p));
    model[0].invisible_factor=1;assert(!actor_fade_eligible(&model[0],p));model[0]=before;
    infos[0][0].invisible_factor=.5f;assert(!actor_semantics(&model[0],p));infos[0][0].invisible_factor=1;
    infos[0][0].colorWord=0xfeffffffu;assert(!actor_semantics(&model[0],p));infos[0][0].colorWord=0xffffffffu;
    const float f[]={.7999999523162842f,.5999999046325684f,.3999999165534973f,.19999992847442627f,
        .8999999761581421f,.6999999284744263f,.49999991059303284f,.2999999225139618f,.09999992698431015f};
    const unsigned expected[]={203,152,101,50,229,178,127,76,25};
    for(unsigned i=0;i<9;++i)assert(re4dc_fade::alpha(f[i],1,1,255)==expected[i]);
    assert(re4dc_fade::alpha(0,1,1,255)==0 && re4dc_fade::alpha(1,1,1,255)==255);passed();
}
void successful_order_and_snapshot(){
    reset_case();ordinary(11);
    const auto source=model[0];cModelInfo source_infos[4];std::memcpy(source_infos,infos[0],sizeof(source_infos));
    assert(re4dc_actor_transaction_draw(&model[0])==1 && choices[0]==2);
    assert(actor_owned_head==nullptr && actor_fade_pending==1 && !emits);no_leases();
    assert(release_order=="SWTT");const auto ticket=actor_fade_head->ticket;const auto captured=actor_fade_head->context;
    assert(captured.alpha==203 && captured.lit.material[3]==255 && captured.hash==actor_fade_hash(captured));
    assert(!std::memcmp(&source,&model[0],sizeof(source)) && !std::memcmp(source_infos,infos[0],sizeof(source_infos)));
    ordinary(1); // source foot shadow / non-actor packet
    assert(re4dc_actor_transaction_draw(&model[1])==1 && actor_fade_pending==2);ordinary(2);ordinary(4);
    // Later source callbacks overwrite GX and transforms. The palette is
    // drain-current, while the actual acquisition must consume captured views.
    gxlight.material[0]=1;gxlight.material[3]=1;gxlight.lights[0].position[0]=-999;
    gxprojection[0]=-888;gxviewport[0]=-777;fog=0;parts[0].mat[0][3]=20;parts[1].mat[0][3]=21;
    pG->Cam.v_mat[0][3]=500;infos[0][0].mat[0][3]=700;
    drain_all();assert(!aborts && !actor_fade_pending && emits==2);no_leases();
    assert((emitted_order==std::vector<unsigned>{11,100,1,101,2,4}));
    assert((consumed_palette==std::vector<float>{20,21}));
    assert(consumed_projection[0]==captured.projection[0] && consumed_viewport[0]==captured.viewport[0]);
    assert(consumed_lighting.material[3]==255 && consumed_lighting.lights[0].position[0]==42 && consumed_alpha==203 && consumed_fog==1);
    assert(consumed_mv[3]==11); // second actor's captured root, not live21 + camera500
    const std::vector<const void*> want={&infos[0][2],&infos[0][0],&infos[0][3],&infos[0][1],&infos[1][2],&infos[1][0],&infos[1][3],&infos[1][1]};
    assert(emitted_infos==want && certificate_calls==4 && palette_calls==4);
    assert(actor_fade_find(ticket.model)->state==re4dc_fade::State::Done);
    assert(re4dc_actor_death_fade_drain(ticket)==-1 && aborts && emits==2);passed();
}
void pre_suppression_faults(){
    const Fault faults[]={Fault::TextureFirst,Fault::TextureSecond,Fault::Workspace,Fault::Bank,Fault::Pending,
        Fault::Palette,Fault::Skin,Fault::Lighting,Fault::Preflight};
    for(auto f:faults){reset_case();fault=f;if(f==Fault::Lighting)gxlight.material_vertex=1;
        ordinary(11);const auto* first=deferred_first;const auto* last=deferred_last;const unsigned top=deferred_top;
        assert(re4dc_actor_transaction_draw(&model[0])==0);assert(choices[0]==1 && !aborts && !emits && !actor_owned_head && !actor_fade_pending);
        assert(deferred_first==first && deferred_last==last && deferred_top==top && !actor_fade_reserved.node);no_leases();
        assert(re4dc_actor_transaction_draw(&model[0])==0);passed();}
    reset_case();fault=Fault::SkinRelease;assert(re4dc_actor_transaction_draw(&model[0])==-1 && aborts && !emits && !deferred_first);no_leases();passed();
    reset_case();fault=Fault::RetireTexture;assert(re4dc_actor_transaction_draw(&model[0])==-1 && aborts && !emits && !actor_fade_head);no_leases();passed();
    reset_case();choose_fails=true;assert(re4dc_actor_transaction_draw(&model[0])==-1 && aborts && !emits && !deferred_first);no_leases();passed();
}
void post_suppression_faults(){
    const Fault faults[]={Fault::TextureFirst,Fault::TextureSecond,Fault::Workspace,Fault::Pending,Fault::Palette,
        Fault::Skin,Fault::Preflight,Fault::Submit,Fault::SkinRelease,Fault::RetireTexture,Fault::RetireSubmit};
    for(auto f:faults){reset_case();assert(re4dc_actor_transaction_draw(&model[0])==1);fault=f;
        if(f==Fault::Lighting){actor_fade_head->context.lit.material_vertex=1;actor_fade_head->context.hash=actor_fade_hash(actor_fade_head->context);}
        drain_all();assert(aborts && choices[0]==2 && emits==(f==Fault::SkinRelease?1u:0u));no_leases();passed();}
    // Each identity component is independently authoritative before pointers.
    for(unsigned i=0;i<9;++i){reset_case();assert(re4dc_actor_transaction_draw(&model[0])==1);
        switch(i){case 0:++current_frame.frame;break;case 1:++current_frame.room;break;case 2:++current_frame.room_generation;break;
        case 3:++current_frame.primitive_epoch;break;case 4:++current_frame.enemy_generation;break;case 5:++current_frame.object_generation;break;
        case 6:++model[0].serial;break;case 7:identity_live=false;break;case 8:++binding_revision;break;}
        if(i<8)protect_primitive();drain_all();assert(aborts && !emits && choices[0]==2);no_leases();passed();}
    reset_case();assert(re4dc_actor_transaction_draw(&model[0])==1);certificate_valid=false;drain_all();assert(aborts && !emits);passed();
    reset_case();assert(re4dc_actor_transaction_draw(&model[0])==1);model[0].hp=1;drain_all();assert(aborts && !emits);passed();
    reset_case();assert(re4dc_actor_transaction_draw(&model[0])==1);model[0].pParts=&parts[1];drain_all();assert(aborts && !emits);passed();
    reset_case();assert(re4dc_actor_transaction_draw(&model[0])==1);actor_fade_head->context.projection[0]+=1;drain_all();assert(aborts && !emits);passed();
    reset_case();assert(re4dc_actor_transaction_draw(&model[0])==1);assert(re4dc_actor_transaction_draw(&model[0])==-1 && aborts && !emits);passed();
    reset_case();assert(re4dc_actor_transaction_draw(&model[0])==1);re4dc_actor_transaction_retire();std::memset(primitive,0xee,sizeof(primitive));protect_primitive();
    assert(!actor_fade_head && !actor_fade_pending && aborts);stream_aborted=false;drain_all();assert(aborts>=2 && !emits);passed();
}
void queue_contracts(){
    reset_case();ordinary(11);const unsigned top=deferred_top,count=deferred_count;const auto* first=deferred_first;const auto* last=deferred_last;
    Re4dcActorFadeReservation r{};assert(re4dc_model_actor_fade_reserve(&r)==1 && deferred_top<top);
    assert(re4dc_model_actor_fade_cancel(&r)==1 && !r.node && !r.epoch && deferred_top==top && deferred_count==count && deferred_first==first && deferred_last==last);passed();
    reset_case();deferred_top=8192;spill_enabled=false;assert(re4dc_actor_transaction_draw(&model[0])==0 && choices[0]==1 && !aborts && !deferred_first);passed();
    reset_case();deferred_top=8192;assert(re4dc_actor_transaction_draw(&model[0])==1 && deferred_spill==spill_storage);drain_all();assert(emits==1 && !aborts);passed();
    for(unsigned i=0;i<3;++i){reset_case();if(i==0)direct_open=true;if(i==1)draining_parts=true;if(i==2)source_draws_finished=true;
        assert(re4dc_actor_transaction_draw(&model[0])==0 && choices[0]==1 && !aborts && !deferred_first);passed();}
    for(unsigned i=0;i<3;++i){reset_case();if(i==0)frame_ready=false;if(i==1)stream_aborted=true;if(i==2)actor_fade_queue_epoch=0;
        assert(re4dc_model_actor_fade_reserve(&r)==-1 && aborts);actor_fade_queue_epoch=5;passed();}
    reset_case();assert(re4dc_model_actor_fade_reserve(&r)==1);Re4dcActorFadeReservation other{};assert(re4dc_model_actor_fade_reserve(&other)==-1 && aborts);passed();
    reset_case();r={};assert(re4dc_model_actor_fade_reserve(&r)==1);ordinary(2);assert(re4dc_model_actor_fade_cancel(&r)==-1 && aborts);passed();
    reset_case();r={};assert(re4dc_model_actor_fade_reserve(&r)==1);actor_fade_queue_reset();assert(re4dc_model_actor_fade_cancel(&r)==-1 && aborts);passed();
    reset_case();r={};assert(re4dc_model_actor_fade_reserve(&r)==1);Re4dcActorFadeTicket t{current_frame,{reinterpret_cast<std::uintptr_t>(&model[0]),22,1},1,r.epoch+1};
    assert(re4dc_model_actor_fade_commit(&r,&t)==-1 && aborts && !deferred_first);passed();
    for(unsigned i=0;i<3;++i){reset_case();assert(re4dc_actor_transaction_draw(&model[0])==1);if(i==0)deferred_first->changed[0]=0;if(i==1)draining_list=0;if(i==2)frame_ready=false;
        drain_all();assert(aborts && !emits);passed();}
    reset_case();assert(re4dc_actor_transaction_draw(&model[0])==1);const auto ticket=actor_fade_head->ticket;const auto bytes=kActorFadeBytes;
    auto* duplicate=reinterpret_cast<DeferredPart*>(frame_storage+(deferred_top-=bytes));std::memcpy(duplicate,deferred_first,bytes);
    deferred_last->next=duplicate;deferred_last=duplicate;++actor_fade_queue_pending;
    drain_all();assert(emits==1 && aborts && choices[0]==2);assert(re4dc_actor_death_fade_drain(ticket)==-1);passed();
    reset_case();assert(re4dc_actor_transaction_draw(&model[0])==1);actor_fade_queue_reset();assert(aborts && !actor_fade_queue_pending);passed();
}
@@SNAPSHOT_IMPLEMENTATION@@
void snapshot_dump(){reset_case();assert(re4dc_actor_transaction_draw(&model[0])==1);const auto& c=actor_fade_head->context;
    actor_fade_snapshot(actor_fade_head->ticket,c);assert(log_text.find("field=control")!=std::string::npos);
    assert(log_text.find("field=projection")!=std::string::npos && log_text.find("field=viewport")!=std::string::npos);
    assert(log_text.find("field=light i=7")!=std::string::npos && log_text.find("000000cb")!=std::string::npos);
    assert(log_text.find("AFD_FIFO enqueue")!=std::string::npos);drain_all();assert(log_text.find("AFD_FIFO actor")!=std::string::npos);passed();}
int main(){snapshot_dump();predicate_and_alpha();successful_order_and_snapshot();pre_suppression_faults();post_suppression_faults();queue_contracts();
    printf("PASS %u actual-code checks: source predicate/alpha, lease restoration, FIFO order, context snapshots, drain-current palettes, one-shot/fault/retirement paths\n",checks);}

"""
def main():
    source=(GAME/'platform/native_ui.cpp').read_text()
    start=source.index('constexpr unsigned kViewWords=')
    end=source.index('Re4dcModelPart* deferred_basis=',start)
    cpp=CPP.replace('@@DEFERRED_LAYOUT@@',source[start:end])
    context=(GAME/'coarse_actor_death_fade_context.inc').read_text()
    first=context.index('#if RE4DC_ACTOR_TRANSACTION_DIAG')+len('#if RE4DC_ACTOR_TRANSACTION_DIAG')
    last=context.index('#endif',first)
    cpp=cpp.replace('@@SNAPSHOT_IMPLEMENTATION@@',context[first:last])
    with tempfile.TemporaryDirectory(prefix='actor-death-fade-') as d:
        p=Path(d);(p/'test.cpp').write_text(cpp);(p/'em.h').write_text('// Actual reader uses the source-shaped const test fixture.\n')
        exe=p/'test'
        subprocess.run(['c++','-std=c++17','-O1','-g','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(p),'-I'+str(HEADER),'-I'+str(GAME),str(p/'test.cpp'),'-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True)
if __name__=='__main__':main()
