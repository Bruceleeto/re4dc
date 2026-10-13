// Included once by coarse_actor_transaction.inc. This observer never adopts or
// binds actors, invokes gameplay, changes packets, or allocates source work.
#if RE4DC_ACTOR_TRANSACTION_DIAG
#include "actor_visibility_diag.h"
#include "em10.h"
namespace avd_detail {
using namespace re4dc_visdiag;
Collector avd;
struct SourceIdentity { Address model,info,part;unsigned serial,frame,epoch,known; } avd_source;
void avd_line(const Order& e){
    // re4dc_log has a 256-byte buffer: continuation lines share frame+sequence.
    re4dc_log("ATX_ORDER f=%u seq=%u e=%u d=%u node=%p epoch=%u\n",
        e.stream.frame,e.seq,e.event,e.detail,(void*)e.node,e.stream.epoch);
    re4dc_log("ATX_ORDER_MODEL f=%u seq=%u m=%p serial=%u known=%u info=%p part=%p alpha=%08x\n",
        e.stream.frame,e.seq,(void*)e.model,e.serial,e.known,(void*)e.info,(void*)e.part,e.alpha);
    re4dc_log("ATX_ORDER_STREAM f=%u seq=%u count_total=%u list=%u closed=%x state=%x first=%p last=%p\n",
        e.stream.frame,e.seq,e.stream.count,e.stream.list,e.stream.closed,e.stream.flags,(void*)e.stream.first,(void*)e.stream.last);
}
void avd_frame(unsigned f){
    if(!avd.started || avd.frame!=f){if(avd.started)re4dc_actor_vis_flush(1);avd.begin(f);avd_source={};}
}
}
extern "C" void re4dc_actor_vis_flush(unsigned reason){
    using namespace avd_detail;using namespace re4dc_visdiag;
    if(!avd.marked)return;
    re4dc_log("ATX_VIS_BOUNDS f=%u reason=%u lives=%u cap_models=%u cap_frames=%u pre=%u pre_lost=%u post=%u post_lost=%u model_lost=%u frame_lost=%u bytes=%u\n",
        avd.frame,reason,avd.nlife,kModels,kFrames,avd.nbefore,avd.before_lost,avd.nafter,avd.after_lost,avd.model_lost,avd.frame_lost,unsigned(sizeof(avd)+sizeof(avd_source)));
    const unsigned start=(avd.before_head+kBefore-avd.nbefore)%kBefore;
    for(unsigned i=0;i<avd.nbefore;++i)avd_line(avd.before[(start+i)%kBefore]);
    for(unsigned i=0;i<avd.nafter;++i)avd_line(avd.after[i]);
    for(unsigned i=0;i<avd.nlife;++i){const auto& a=avd.active[i];if(!a.model)continue;
        for(unsigned r=0;r<a.count;++r){const auto& p=a.roles[r];
            re4dc_log("ATX_ALPHA_SUM f=%u m=%p serial=%u role=%u info=%p parts=%u first=%08x last=%08x changes=%u unknown_infos=%u\n",
                a.frame,(void*)a.model,a.serial,r,(void*)p.info,p.parts,p.first_alpha,p.last_alpha,p.changes,a.unknown_infos);}}
    // Keep lifetime limits and active role identities through possible same-frame
    // direct submissions; only consume this segment's ordering records.
    avd.marked=false;avd.nbefore=avd.before_head=avd.nafter=avd.before_lost=avd.after_lost=0;
}
extern "C" void re4dc_actor_vis_decline(const cModel* m,unsigned appearance,const cModelInfo* const* infos,unsigned count){
    using namespace avd_detail;using namespace re4dc_visdiag;
    if(!m || m->id<0x10 || m->id>0x20 || m->id==0x18 || appearance>=5 || m->nParts!=34)return;
    Stream s{};re4dc_actor_vis_stream(&s);avd_frame(s.frame);
    const int slot=avd.decline(Address(m),unsigned(m->serial));
    if(slot<0){bool& shown=slot==-1?avd.model_notice:avd.frame_notice;
        if(!shown){shown=true;re4dc_log("ATX_VIS_LIMIT f=%u reason=%d models=%u frames_per_identity=%u\n",s.frame,slot,kModels,kFrames);}return;}
    Active& a=avd.active[slot];if(a.count)return;
    a.count=count<kRoles?count:kRoles;for(unsigned r=0;r<a.count;++r)a.roles[r].info=Address(infos[r]);
    const ModelState v=model_state(*m);
    re4dc_log("ATX_VIS f=%u srcf=%u m=%p serial=%u vptr=%08x id=%02x type=%u kind=%u ot=%u app=%u roles=%u roles_lost=%u parts=%u\n",
        s.frame,unsigned(pG->Frame_cnt),m,unsigned(m->serial),*reinterpret_cast<const unsigned*>(m),v.id,v.type,v.kind,v.ot,
        appearance,a.count,count-a.count,v.parts);
    re4dc_log("ATX_VIS_STATE f=%u m=%p serial=%u be=%08x alpha=%u depth=%u cull=%u shader=%u rno=%u,%u,%u,%u factors=%08x,%08x\n",
        s.frame,m,unsigned(m->serial),v.be,v.alpha,v.depth,v.cull,v.shader,v.routine[0],v.routine[1],v.routine[2],v.routine[3],v.factor[0],v.factor[1]);
    unsigned index=~0u,truncated=0;const cEm* em=existing_enemy(EmMgr,m,index,truncated);
    if(em){const Em10Work* w=reinterpret_cast<const Em10Work*>(reinterpret_cast<const unsigned char*>(em)+0x3e0);
        re4dc_log("ATX_VIS_EM f=%u m=%p serial=%u slot=%u scan_trunc=%u hp=%d hpmax=%d set=%u emset=%u status=%08x dist2=%08x scenario=%p\n",
            s.frame,m,unsigned(m->serial),index,truncated,int(em->hp),int(em->hp_max),unsigned(em->set),unsigned(em->emset_no),unsigned(em->status),bits(em->plDist2),em->pScenario);
        re4dc_log("ATX_VIS_WORK f=%u m=%p serial=%u flags=%08x timers=%d,%d,%d compress=%08x reset=%u\n",
            s.frame,m,unsigned(m->serial),unsigned(w->flags),w->Timer,w->Timer2,w->Timer3,bits(w->Compress_y),unsigned(w->Reset_enable));
    }else re4dc_log("ATX_VIS_EM f=%u m=%p serial=%u slot=unknown scan_trunc=%u\n",s.frame,m,unsigned(m->serial),truncated);
    Order e{};e.event=Decline;e.model=Address(m);e.serial=m->serial;e.known=1;e.stream=s;avd.event(e);
}
extern "C" void re4dc_actor_vis_source(const cModel* m,const cModelInfo* info,const Re4dcModelPart* p){
    using namespace avd_detail;using namespace re4dc_visdiag;
    Stream s{};re4dc_actor_vis_stream(&s);avd_frame(s.frame);
    // Set even for an unselected model, so an identical/reused info address cannot
    // inherit the previous model's serial. Never use p.serial (zero for actors).
    avd_source={Address(m),Address(info),Address(p->part),unsigned(m->serial),s.frame,s.epoch,1};
    const int slot=avd.find(Address(m),unsigned(m->serial));if(slot<0)return;
    const int role=avd.source(Address(m),unsigned(m->serial),Address(info),p->alpha_state);
    avd.marked=true;
    if(role>=0 && avd.active[slot].roles[role].parts==1){
        re4dc_log("ATX_ALPHA f=%u m=%p serial=%u role=%u info=%p data=%p tpl=%p part=%p actual=%08x\n",
            s.frame,m,unsigned(m->serial),unsigned(role),info,info->pData,info->tpl_addr,p->part,p->alpha_state);
        re4dc_log("ATX_ALPHA_STATE f=%u m=%p serial=%u role=%u factors=%08x,%08x,%08x iflags=%08x color=%08x blend=%u depth=%u material=%08x\n",
            s.frame,m,unsigned(m->serial),unsigned(role),bits(m->invisible_factor),bits(m->invisible_factor2),bits(info->invisible_factor),
            unsigned(info->be_flag),unsigned(info->colorWord),p->blend,p->depth_mode,p->material_flags);
    }
    re4dc_actor_vis_event(Source,nullptr,p,role<0?~0u:unsigned(role));
}
extern "C" void re4dc_actor_vis_source_end(){avd_detail::avd_source={};}
extern "C" void re4dc_actor_vis_event(unsigned event,const void* node,const Re4dcModelPart* p,unsigned detail){
    using namespace avd_detail;using namespace re4dc_visdiag;
    Stream s{};re4dc_actor_vis_stream(&s);avd_frame(s.frame);
    Order e{};e.event=event;e.detail=detail;e.node=Address(node);e.stream=s;
    if(p){e.model=Address(p->model);e.info=Address(p->info);e.part=Address(p->part);e.alpha=p->alpha_state;
        if(avd_source.frame==s.frame && avd_source.epoch==s.epoch && avd_source.model==e.model && avd_source.info==e.info && avd_source.part==e.part){e.serial=avd_source.serial;e.known=avd_source.known;}}
    if(event==Drain || event==DrainModel){const Order* q=avd.queued(e.node,s.epoch);
        if(q){
            if(!p){e.model=q->model;e.info=q->info;e.part=q->part;e.alpha=q->alpha;}
            // Preserve restored packet values; never hide a restore mismatch by
            // replacing them with the enqueue-side snapshot.
            if(e.model==q->model && e.info==q->info && e.part==q->part){e.serial=q->serial;e.known=q->known;}
            else {e.serial=e.known=0;e.detail|=0x80000000u;}
        }}
    avd.event(e);
}
#endif
