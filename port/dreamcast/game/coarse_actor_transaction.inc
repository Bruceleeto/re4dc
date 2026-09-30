// Included once by coarse_actor.cpp under RE4DC_ACTOR_TRANSACTION.
// Owners are acquired only from commonModelTrans, after re4dc_ui_begin.
// The original emTrans/commonScreenMatSub has already run once for ALL actors.
#include "actor_palette_arena.h"
#include "actor_transaction_diag.h"
#include "actor_transaction_diag_impl.inc"
namespace {
using re4dc_source::FrameIdentity;
using re4dc_source::ModelIdentity;
struct ActorOwnedPart {
    cModelInfo* info;
    Re4dcActorSource source;
    Re4dcActorChunk chunk;
    float mv[12];
    unsigned flags,role;
};
struct ActorOwnedRecord {
    ActorOwnedRecord* next;
    const void* parts_owner;
    FrameIdentity frame;
    ModelIdentity model;
    Re4dcActorTextureLease textures[kRe4dcActorMaterials];
    Re4dcActorWorkspaceLease workspace;
    re4dc_actor::PaletteLease palette;
    Re4dcActorSkinLease skin;
    Re4dcModelPart base;
    Re4dcActorPlan plan;
    unsigned count,run_count,done,passes,submitted,released;
#if RE4DC_CROWD
    unsigned crowd_ganado,crowd_would,crowd_emit;  // lane crowd: a Ganado; its policy reason (=2 check); triangles emitted
#endif
    ActorOwnedPart part[8];
    Re4dcActorDrawRun runs[kRe4dcActorRuns];
};
ActorOwnedRecord* actor_owned_head;
FrameIdentity actor_owned_frame{};
bool actor_owned_live;
re4dc_actor::PaletteArena actor_palette_arena;
constexpr unsigned kActorPaletteCap=64*1024;
constexpr unsigned kActorOwnerReserve=16*1024;
extern "C" void* re4dc_prim_tail(unsigned,unsigned);
extern "C" void re4dc_model_packet_abort();
extern "C" void re4dc_actor_model_frame_retire();

void actor_fail() { ATD(nullptr,20,0,0);re4dc_model_packet_abort(); }
bool actor_release(ActorOwnedRecord& r) {
    if(r.released)return true;
    // Revoke every borrowed skin/cache pointer BEFORE matrix space is reused.
    // A failed revocation keeps that space occupied until frame retirement.
    const bool skin_ok=re4dc_actor_skin_release(&r.skin)!=0;
    const bool okay=skin_ok && actor_palette_arena.release(r.palette);
    re4dc_actor_workspace_release(&r.workspace);
    for(unsigned i=r.plan.material_count;i>0;--i)re4dc_actor_texture_release(&r.textures[i-1]);
    r.released=1;
    if(!okay)actor_fail();
    return okay;
}
bool actor_plan_layout(Re4dcActorPlan& p) {
    if(!p.count || p.count>8)return false;
    // Legacy Ganado factories retain their one-atlas representation.
    if(!p.material_count && !p.run_count) {
        p.material_count=1;p.materials[0].image=p.image;p.materials[0].crc=p.crc;p.materials[0].fnv=p.fnv;
        for(unsigned i=0;i<p.count;++i) {
            const auto& c=p.input[i];auto& r=p.runs[p.run_count++];
            r.role=i;r.immutable_asset_id=p.immutable_asset_id[i];r.triangles=c.triangles;r.uv=c.uv;r.stream=c.stream;
        }
    }
    return p.material_count && p.material_count<=kRe4dcActorMaterials && p.run_count && p.run_count<=kRe4dcActorRuns;
}
bool actor_semantics(cModel* m,const Re4dcActorPlan& p) {
    if(!m->pParts || !p.count || p.count>8 || !p.palettes ||
       m->invisible_factor!=1.0f || m->invisible_factor2!=1.0f || m->alpha_omit!=255 ||
       m->z_mode!=0 || m->CullMode || m->Shader_type || m->AddAmb_r || m->AddAmb_g || m->AddAmb_b ||
       (m->be_flag&(0x4000u|0x00020000u)) ||
       !re4dc_actor::exact_infos(m->pModelInfo,p.info,p.count) ||
       !p.material_count || p.material_count>kRe4dcActorMaterials || !p.run_count || p.run_count>kRe4dcActorRuns)return false;
    // Shadow/depth, special rendering and texture modifications remain source.
    if(pG->Status_flg[1]&0x100)return false;
    if((pG->Status_flg[2]&0x00100000) && (m->be_flag&0x02000000) &&
       !(pG->Disp_flg&0x00040000) && (pG->Status_flg[1]&0x200))return false;
    unsigned palette_bytes=0,workspace_bytes=0;
    for(unsigned i=0;i<p.count;++i) {
        auto* info=p.info[i];
        // Hidden infos were still prepared and animated by the source callback.
        // They participate in the certificate and lease proof too.
        if(!info || !info->pData || info->invisible_factor!=1.0f || info->blend_mode ||
           info->colorWord!=0xffffffffu || info->flagsDC || info->pAddTpl || info->nAddTex ||
           info->texBlendTbl || info->pTexAnim || info->uvU || info->uvV || info->uvScrollU || info->uvScrollV ||
           ((info->be_flag&2) && !(p.count==8 && i==3)))return false;
        re4dc_source::ChunkProof proof{};
        if(re4dc_actor_immutable_chunk_proof(p.immutable_asset_id[i],p.input[i],proof)!=re4dc_source::BlobError::None)return false;
        palette_bytes+=proof.palette_bytes;
        if(proof.skin_table_bytes>workspace_bytes)workspace_bytes=proof.skin_table_bytes;
    }
    if(palette_bytes!=p.palette_bytes || workspace_bytes!=p.workspace_bytes)return false;
    unsigned triangles[8]{},seen=0,materials=0,previous_role=0;
    for(unsigned j=0;j<p.run_count;++j) {
        const auto& r=p.runs[j];
        if(r.role>=p.count || r.material>=p.material_count || (j && r.role<previous_role))return false;
        previous_role=r.role;seen|=1u<<r.role;materials|=1u<<r.material;
        auto c=p.input[r.role];c.uv=r.uv;c.stream=r.stream;c.triangles=r.triangles;
        re4dc_source::ChunkProof proof{};
        // Compiled const run bytes have separate IDs29..42. Their shared role7
        // palette is accounted once above, never once per material run.
        if(re4dc_actor_immutable_chunk_proof(r.immutable_asset_id,c,proof)!=re4dc_source::BlobError::None)return false;
        if(r.triangles>p.input[r.role].triangles-triangles[r.role])return false;
        triangles[r.role]+=r.triangles;
    }
    if(seen!=(1u<<p.count)-1 || materials!=(1u<<p.material_count)-1)return false;
    for(unsigned i=0;i<p.count;++i)if(triangles[i]!=p.input[i].triangles)return false;
    // Geometry signatures do not prove unchanged materials, costumes or TPLs.
    return re4dc_actor_material_certificate(m,&p)!=0;
}
ActorOwnedRecord* actor_decline(ActorOwnedRecord& r,bool& failed) {
    const bool released=actor_release(r);Re4dcActorStreamState state{};
    if(!released || !re4dc_actor_stream_state(&state))failed=true;
    return nullptr;
}
ActorOwnedRecord* actor_acquire(cModel* m,const Re4dcActorPlan& p,
    const FrameIdentity& frame,const ModelIdentity& model,bool& failed) {
    failed=false;
    if(!p.palette_bytes || p.palette_bytes>kActorPaletteCap){ATD(m,7,p.palette_bytes,kActorPaletteCap);return nullptr;}
    re4dc_bind_actor_frame(); // existing single frame owner, before its lease
    Re4dcActorTextureLease textures[kRe4dcActorMaterials]{};
    Re4dcActorWorkspaceLease workspace{};
    unsigned acquired=0;
    auto release_textures=[&]{while(acquired)re4dc_actor_texture_release(&textures[--acquired]);};
    for(;acquired<p.material_count;++acquired) {
        const auto& mat=p.materials[acquired];
        if(!re4dc_actor_texture_acquire(&mat.image,mat.crc,mat.fnv,&textures[acquired])) {ATD(m,8,acquired,p.material_count);release_textures();return nullptr;}
    }
    if(!re4dc_actor_workspace_acquire(p.workspace_bytes,&workspace)) {
        ATD(m,9,p.workspace_bytes,0);
        release_textures();return nullptr;
    }
    const unsigned header=(sizeof(ActorOwnedRecord)+31u)&~31u;
    if(!actor_palette_arena.bound()) {
        // Fund the whole reusable bank, this record and the existing reserve.
        // The bank survives until primitive retirement, even after a decline.
        void* bank=re4dc_prim_tail(kActorPaletteCap,kActorOwnerReserve+header);
        if(!bank || !actor_palette_arena.bind(bank,kActorPaletteCap)) {
            ATD(m,10,kActorPaletteCap,header);
            re4dc_actor_workspace_release(&workspace);release_textures();return nullptr;
        }
    }
    re4dc_actor::PaletteLease palette_lease{};
    if(!actor_palette_arena.acquire(p.palette_bytes,palette_lease)) {
        ATD(m,11,p.palette_bytes,0);
        re4dc_actor_workspace_release(&workspace);release_textures();return nullptr;
    }
    void* palette_memory=actor_palette_arena.data(palette_lease,p.palette_bytes);
    void* memory=palette_memory?re4dc_prim_tail(header,kActorOwnerReserve):nullptr;
    if(!memory) {
        ATD(m,12,header,p.palette_bytes);
        if(!actor_palette_arena.release(palette_lease))failed=true;
        re4dc_actor_workspace_release(&workspace);release_textures();return nullptr;
    }
    auto* r=::new(memory) ActorOwnedRecord{};
    r->parts_owner=m->pParts;r->frame=frame;r->model=model;r->workspace=workspace;r->count=p.count;r->plan=p;
    r->palette=palette_lease;
    for(unsigned i=0;i<p.material_count;++i)r->textures[i]=textures[i];
    // All roles of this actor share one allocation. Material runs only borrow
    // their role's palette, including all fourteen ordered hair draws.
    float* palettes[8]{};unsigned at=0;
    for(unsigned i=0;i<p.count;++i) {
        palettes[i]=reinterpret_cast<float*>(static_cast<unsigned char*>(palette_memory)+at);
        at+=(p.input[i].palette_count*48u+31u)&~31u;
    }
    if(!p.palettes(m,p,palettes)){ATD(m,13,p.appearance,0);return actor_decline(*r,failed);}
    Re4dcActorSkinBinding bindings[8]{};
    unsigned order=0;
    for(cModelInfo* info=m->pModelInfo;info;info=info->pList) {
        unsigned i=0;for(;i<p.count && p.info[i]!=info;++i){}
        if(i==p.count || order==p.count)return actor_decline(*r,failed);
        const auto& c=p.input[i];auto& part=r->part[order];
        part.info=info;part.flags=info->be_flag;part.role=i;
        part.source={c.positions.data,c.normals.data,c.position_count,c.normal_count,c.palette_count,0};
        Mtx pm,mv;PSMTXConcat(m->pParts->mat,info->mat,pm);PSMTXConcat(pG->Cam.v_mat,pm,mv);
        std::memcpy(part.mv,mv,sizeof(mv));
        for(float f:part.mv)if(!coarse_finite(f))return actor_decline(*r,failed);
        part.chunk={info,c.stream.data,c.uv.data,part.mv,unsigned(c.stream.size),c.position_count,c.normal_count};
        bindings[order]={info,part.source,palettes[i],c.palette_count};
        // Expand materials in this role's source order, not texture-key order.
        for(unsigned j=0;j<p.run_count;++j)if(p.runs[j].role==i) {
            const auto& run=p.runs[j];auto& draw=r->runs[r->run_count++];
            draw.chunk={info,run.stream.data,run.uv.data,part.mv,unsigned(run.stream.size),c.position_count,c.normal_count};
            draw.material=run.material;
        }
        ++order;
    }
    if(!re4dc_actor_skin_acquire(frame.frame,bindings,order,&r->skin)){ATD(m,14,order,0);return actor_decline(*r,failed);}
    auto& b=r->base;b.model=m;b.position_stride=6;b.normal_stride=6;b.normal_shift=14;b.shift=4;
    b.lighting=&light;b.image=p.image;b.source_key[2]=1;b.depth_mode=m->z_mode;b.cull=0;b.alpha_state=255;
    GXGetProjectionv(b.projection);GXGetViewportv(b.viewport);
    r->passes=m->ot_type==7?3u:1u;
    // The whole actor, BOTH pass groups, qualifies before its first TA header.
    if(r->run_count!=p.run_count || !re4dc_actor_preflight_owned_runs(&b,r->runs,r->run_count,p.materials,p.material_count,&r->workspace,&r->skin,r->textures)) {
        ATD(m,15,r->run_count,p.run_count);return actor_decline(*r,failed);
    }
    r->next=actor_owned_head;actor_owned_head=r;return r;
}
}

#if RE4DC_CROWD
// Lane crowd (crowd.mk; render only): after the owner path admitted a Ganado (plan + semantics), decide whether its
// cast mesh is acquired and submitted at all. A Ganado that is not drawn takes presentation choice 2 (native, so the
// source callback never draws it) with no record: both of its OT passes return "handled" without a submission. Its
// simulation, skeleton and collision ran before and are untouched.
//   reason 1: CROWD_CULL, every visible chunk provably off-screen (re4dc_crowd_offscreen, the cast pregate balls)
//   reason 2: CROWD_DRAW_M, farther than D metres; reason 3: CROWD_DRAW_MAX, beyond the N nearest.
extern "C" int re4dc_crowd_offscreen(cModel*);  // coarse_actor_owner_ganado.inc
extern "C" unsigned re4dc_model_output_count();
extern "C" unsigned re4dc_ui_frame();
namespace {
constexpr unsigned kCrowdSkips=64;
ModelIdentity crowd_skip[kCrowdSkips];
unsigned crowd_skips;
bool crowd_ganado(cModel* m) { return m && m->id>=0x10 && m->id<=0x20; }  // owner_ganado_bind's class
// The root's camera distance (source units: millimetres).
float crowd_distance(cModel* m) {
    const float (*r)[4]=m->pParts->mat;const float (*v)[4]=pG->Cam.v_mat;
    float t[3];
    for(unsigned i=0;i<3;++i)t[i]=v[i][0]*r[0][3]+v[i][1]*r[1][3]+v[i][2]*r[2][3]+v[i][3];
    return __builtin_sqrtf(t[0]*t[0]+t[1]*t[1]+t[2]*t[2]);
}
#if RE4DC_CROWD_DRAW_MAX >= 0
// Distances of the previous frame's drawable Ganados (kept by the cull and the distance limit), and this frame's.
struct CrowdSeen { std::uintptr_t address; float d; };
CrowdSeen crowd_prev[kCrowdSkips],crowd_cur[kCrowdSkips];
unsigned crowd_prev_n,crowd_cur_n;
#endif
#if RE4DC_CROWD_CENSUS
struct CrowdCensus { unsigned frame,game,seen,admitted,skip[4],drawn,empty,band[4],tris,cullcheck; } crowd_cc;
#endif
#if RE4DC_CROWD_CULL == 2
unsigned crowd_chk_would,crowd_chk_violations,crowd_chk_tris,crowd_chk_log;
#endif
void crowd_frame_begin() {
#if RE4DC_CROWD_CENSUS
    const CrowdCensus& c=crowd_cc;
    if(c.seen && c.frame>=RE4DC_CROWD_CENSUS_FROM && c.frame<=RE4DC_CROWD_CENSUS_TO)
        re4dc_log("CROWDC f=%u t=%u seen=%u admitted=%u off=%u far=%u cap=%u drawn=%u empty=%u band=%u/%u/%u/%u tris=%u\n",
            c.frame,c.game,c.seen,c.admitted,c.skip[1],c.skip[2],c.skip[3],c.drawn,c.empty,c.band[0],c.band[1],c.band[2],
            c.band[3],c.tris);
    crowd_cc=CrowdCensus{};crowd_cc.frame=re4dc_ui_frame();crowd_cc.game=unsigned(pG->Frame_cnt);
#endif
#if RE4DC_CROWD_CULL == 2
    if(!(pG->Frame_cnt%120))
        re4dc_log("CROWDCULL t=%u would_cull=%u violations=%u violation_tris=%u\n",unsigned(pG->Frame_cnt),crowd_chk_would,
            crowd_chk_violations,crowd_chk_tris);
#endif
#if RE4DC_CROWD_DRAW_MAX >= 0
    std::memcpy(crowd_prev,crowd_cur,sizeof(crowd_cur));crowd_prev_n=crowd_cur_n;crowd_cur_n=0;
#endif
}
// 0: draw; 1..3: the reason it is not drawn (above).
unsigned crowd_policy(cModel* m) {
    const float d=crowd_distance(m);
    (void)d;
#if RE4DC_CROWD_CENSUS
    ++crowd_cc.admitted;++crowd_cc.band[d<5000.0f?0:d<12000.0f?1:d<25000.0f?2:3];
#endif
#if RE4DC_CROWD_CULL
    if(re4dc_crowd_offscreen(m))return 1;
#endif
#if RE4DC_CROWD_DRAW_M > 0
    if(d>float(RE4DC_CROWD_DRAW_M)*1000.0f)return 2;
#endif
#if RE4DC_CROWD_DRAW_MAX >= 0
    const std::uintptr_t a=reinterpret_cast<std::uintptr_t>(m);
    if(crowd_cur_n<kCrowdSkips)crowd_cur[crowd_cur_n++]={a,d};
    unsigned rank=0;
    for(unsigned k=0;k<crowd_prev_n;++k)if(crowd_prev[k].address!=a && crowd_prev[k].d<d)++rank;
    if(rank>=unsigned(RE4DC_CROWD_DRAW_MAX))return 3;
#endif
    return 0;
}
bool crowd_skipped(const ModelIdentity& model) {
    for(unsigned k=0;k<crowd_skips;++k)if(crowd_skip[k]==model)return true;
    return false;
}
}
#endif
extern "C" void re4dc_actor_transaction_retire() {
    // Revoke exported owners without traversing old primitive storage. This is
    // called BEFORE FrameLedger retirement and SetPrimBuffPtr storage reuse.
    actor_owned_head=nullptr;actor_owned_live=false;
#if RE4DC_CROWD
    crowd_skips=0;
#endif
    re4dc_actor_owner_retire(); // revoke cached matrix pointers before bank reuse
    re4dc_actor_model_frame_retire(); // next primitive owner must reacquire its workspace
    actor_palette_arena.retire();
    re4dc_actor_texture_retire_all();
}
extern "C" int re4dc_actor_transaction_draw(cModel* m) {
    ATD(m,0,0,0);
    FrameIdentity frame{};ModelIdentity model{};unsigned choice=0;
    const int identity=re4dc_actor_transaction_identity(m,&frame,&model);
    if(identity<0){actor_fail();return -1;}
    if(!identity){ATD(m,1,0,0);return 0;}
    // Frame identity is checked BEFORE touching any retained record pointer.
    if(actor_owned_live && !(actor_owned_frame==frame)){actor_fail();return -1;}
    if(!actor_owned_live){
        actor_owned_frame=frame;actor_owned_live=true;
#if RE4DC_CROWD
        crowd_frame_begin();
#endif
    }
    if(!re4dc_actor_transaction_choice(m,&choice)){actor_fail();return -1;}
    if(choice==1){ATD(m,2,0,0);return 0;} // sticky original-source decision, including pass two
    ActorOwnedRecord* r=nullptr;
#if RE4DC_CROWD
    unsigned crowd_would=0;
    if(choice==0 && crowd_ganado(m)) {
#if RE4DC_CROWD_CENSUS
        ++crowd_cc.seen;
#endif
    }
#endif
    if(choice==2) {
        for(auto* p=actor_owned_head;p;p=p->next)if(p->model==model){r=p;break;}
#if RE4DC_CROWD
        if(!r && crowd_skipped(model))return 1;  // a Ganado the crowd policy does not draw: its second pass
#endif
        if(!r || !(r->frame==frame)){actor_fail();return -1;}
    } else {
        // Mark source first; any pre-header admission failure retains the
        // already prepared original path and cannot retry in a later OT group.
        if(!re4dc_actor_transaction_choose(m,1)){actor_fail();return -1;}
        if(m->ot_type==7 && (m->be_flag&0x08000000)){ATD(m,3,0,0);return 0;}
        Re4dcActorPlan p{};
        if(!(re4dc_actor_plan_leon(m,&p) || re4dc_actor_plan_ganado(m,&p))){ATD(m,4,0,0);return 0;}
        if(!actor_plan_layout(p)){ATD(m,5,p.count,p.run_count);return 0;}
        if(!actor_semantics(m,p)){ATD(m,6,p.appearance,p.count);return 0;}
#if RE4DC_CROWD
        if(crowd_ganado(m)) {
            crowd_would=crowd_policy(m);
#if RE4DC_CROWD_CENSUS
            ++crowd_cc.skip[crowd_would];
#endif
#if RE4DC_CROWD_CULL == 2
            if(crowd_would==1)++crowd_chk_would;
            if(crowd_would>1)  // =2 checks the cull only; a policy skip still skips
#else
            if(crowd_would)
#endif
            {
                if(crowd_skips==kCrowdSkips)crowd_would=0;  // no room to remember it: drawn as before
                else {
                    if(!re4dc_actor_transaction_choose(m,2)){actor_fail();return -1;}
                    crowd_skip[crowd_skips++]=model;
                    return 1;
                }
            }
        }
#endif
        bool failed=false;r=actor_acquire(m,p,frame,model,failed);
        if(failed){actor_fail();return -1;}
        if(!r){ATD(m,31,p.appearance,0);return 0;}
        if(!re4dc_actor_transaction_choose(m,2)){actor_release(*r);actor_fail();return -1;}
        ATD(m,16,p.appearance,p.run_count);
#if RE4DC_CROWD
        r->crowd_ganado=crowd_ganado(m);r->crowd_would=crowd_would;r->crowd_emit=0;
#endif
    }
    const unsigned pass=m->ot_type==7 && (m->be_flag&0x08000000)?2u:1u;
    if((r->done&pass) || r->released){actor_fail();return -1;}
    if(!actor_palette_arena.data(r->palette,r->plan.palette_bytes) ||
       m->pParts!=r->parts_owner || !actor_semantics(m,r->plan)){actor_release(*r);actor_fail();return -1;}
    float projection[7],viewport[6];GXGetProjectionv(projection);GXGetViewportv(viewport);
    if(std::memcmp(projection,r->base.projection,sizeof(projection)) || std::memcmp(viewport,r->base.viewport,sizeof(viewport))) {
        actor_release(*r);actor_fail();return -1;
    }
    // Detect changed visibility/list before any second-pass submission. Source
    // callbacks never run here. Once a prior pass emitted, failure aborts rather
    // than drawing a late source duplicate over a partial native actor.
    unsigned order=0;
    for(cModelInfo* info=m->pModelInfo;info;info=info->pList) {
        if(order==r->count || r->part[order].info!=info || r->part[order].flags!=info->be_flag) {
            actor_release(*r);actor_fail();return -1;
        }
        Mtx pm,mv;PSMTXConcat(m->pParts->mat,info->mat,pm);PSMTXConcat(pG->Cam.v_mat,pm,mv);
        if(std::memcmp(r->part[order].mv,mv,sizeof(mv))){actor_release(*r);actor_fail();return -1;}
        ++order;
    }
    if(order!=r->count){actor_release(*r);actor_fail();return -1;}
    Re4dcActorDrawRun runs[kRe4dcActorRuns];unsigned n=0;
    for(unsigned i=0;i<r->count;++i) {
        const auto& p=r->part[i];
        if(!(p.flags&8))continue;
        if(m->ot_type==7 && ((p.flags&0x40)?2u:1u)!=pass)continue;
        for(unsigned j=0;j<r->run_count;++j)if(r->runs[j].chunk.info==p.info)runs[n++]=r->runs[j];
    }
#if RE4DC_CROWD
    const unsigned crowd_out0=re4dc_model_output_count();
#endif
    const int result=n?re4dc_actor_submit_owned_runs(&r->base,runs,n,r->plan.materials,r->plan.material_count,&r->workspace,&r->skin,r->textures):1;
#if RE4DC_CROWD
    if(r->crowd_ganado) {
        const unsigned emitted=re4dc_model_output_count()-crowd_out0;
        r->crowd_emit+=emitted;
#if RE4DC_CROWD_CULL == 2
        if(r->crowd_would==1 && emitted) {
            ++crowd_chk_violations;crowd_chk_tris+=emitted;
            if(++crowd_chk_log<=12)re4dc_log("CROWDCULL VIOLATION t=%u m=%p pass=%u emitted=%u\n",unsigned(pG->Frame_cnt),m,pass,emitted);
        }
#endif
#if RE4DC_CROWD_CENSUS
        crowd_cc.tris+=emitted;
        if((r->done|pass)==r->passes)++(r->crowd_emit?crowd_cc.drawn:crowd_cc.empty);
#endif
    }
#endif
    if(result!=1) {
        actor_release(*r);
        // Even a pre-header decline is a broken reservation after admission;
        // never silently switch presentation at an original second pass.
        actor_fail();return -1;
    }
    ATD(m,n?(pass==1?18u:19u):17u,n,r->plan.appearance);
    r->submitted|=n!=0;r->done|=pass;
    if(r->done==r->passes && !actor_release(*r))return -1;
    return 1;
}
