#ifndef RE4DC_ACTOR_VISIBILITY_DIAG_H
#define RE4DC_ACTOR_VISIBILITY_DIAG_H
#include "actor_transaction_diag.h"
#if RE4DC_ACTOR_TRANSACTION_DIAG
#include <cstdint>
#include <cstring>
class cModelInfo;
struct Re4dcModelPart;
namespace re4dc_visdiag {
// Frames are sampled native UI frames, not proof of successful presentation.
// List events cover attempted transitions/openings, including refused late OP,
// and omit calls selecting an already-open list (not a list-call census).
// Stream.flags: bit0 ready, 1 aborted, 2 scene, 3 source finished, 4 draining, 5 direct.
// Reset detail=0 means caller unknown; FinishEnd: 1 empty, 2 visited, 3 aborted.
// Direct detail for a model: 0 drain replay, 1 after finish, 2 opaque; for FX: tag.
// Fixed diagnostic storage, no allocator, no source/renderer ownership. All addresses
// are labels copied while live; no saved pointer is dereferenced by this collector.
constexpr unsigned kModels=4,kFrames=12,kRoles=5,kBefore=64,kAfter=128;
using Address=uintptr_t;
enum Event { Decline=1,Source=2,Enqueue=3,Drain=4,ListRequest=5,ListResult=6,
             FinishBegin=7,FinishEnd=8,Reset=9,Direct=10,DrainModel=11 };
struct Stream { unsigned frame,epoch,count,list,closed,flags; Address first,last; };
struct Order { unsigned seq,event,detail,serial,known,alpha; Address node,model,info,part; Stream stream; };
struct Life { Address model;unsigned serial,frames,last_frame;bool used; };
struct Role { Address info;unsigned parts,first_alpha,last_alpha,changes; };
struct Active { Address model;unsigned serial,frame,count,unknown_infos;Role roles[kRoles]; };
struct Collector {
    Life lives[kModels];Active active[kModels];Order before[kBefore],after[kAfter];
    unsigned frame,nlife,nbefore,before_head,nafter,ordinal,before_lost,after_lost,model_lost,frame_lost;
    bool started,marked,model_notice,frame_notice;
    void begin(unsigned f) {
        frame=f;started=true;marked=false;nbefore=before_head=nafter=ordinal=before_lost=after_lost=0;
        std::memset(active,0,sizeof(active));
    }
    int decline(Address m,unsigned serial) {
        unsigned i=0;while(i<nlife && (lives[i].model!=m || lives[i].serial!=serial))++i;
        if(i==nlife){if(nlife==kModels){++model_lost;return -1;}lives[i]={m,serial,0,0,false};++nlife;}
        Life& l=lives[i];
        if(!l.used || l.last_frame!=frame){
            if(l.frames==kFrames){++frame_lost;return -2;}
            ++l.frames;l.last_frame=frame;l.used=true;
        }
        Active& a=active[i];
        if(!a.model){a.model=m;a.serial=serial;a.frame=frame;}
        marked=true;return int(i);
    }
    int find(Address m,unsigned serial) const {
        for(unsigned i=0;i<nlife;++i)if(active[i].model==m && active[i].serial==serial)return int(i);
        return -1;
    }
    int source(Address m,unsigned serial,Address info,unsigned alpha) {
        const int slot=find(m,serial);if(slot<0)return -1;Active& a=active[slot];
        for(unsigned r=0;r<a.count;++r)if(a.roles[r].info==info){
            Role& v=a.roles[r];if(!v.parts)v.first_alpha=alpha;
            else if(v.last_alpha!=alpha)++v.changes;
            v.last_alpha=alpha;++v.parts;return int(r);
        }
        ++a.unknown_infos;return -1;
    }
    void event(Order e) {
        e.seq=++ordinal;
        if(marked){if(nafter<kAfter)after[nafter++]=e;else ++after_lost;}
        else {before[before_head]=e;before_head=(before_head+1)%kBefore;
              if(nbefore<kBefore)++nbefore;else ++before_lost;}
    }
    const Order* queued(Address node,unsigned epoch) const {
        for(unsigned i=nafter;i>0;--i)if(after[i-1].event==Enqueue && after[i-1].node==node && after[i-1].stream.epoch==epoch)return &after[i-1];
        for(unsigned i=0;i<nbefore;++i){const Order& e=before[(before_head+kBefore-1-i)%kBefore];
            if(e.event==Enqueue && e.node==node && e.stream.epoch==epoch)return &e;}
        return nullptr;
    }
};
inline unsigned bits(float x){unsigned u;std::memcpy(&u,&x,sizeof(u));return u;}
struct ModelState { unsigned id,type,kind,ot,parts,be,alpha,depth,cull,shader,routine[4],factor[2]; };
// These templates are also compiled by the host fixtures. Const access only.
template<class M> ModelState model_state(const M& m) {
    return {unsigned(m.id),unsigned(m.type),unsigned(m.kindid),unsigned(m.ot_type),unsigned(m.nParts),
        unsigned(m.be_flag),unsigned(m.alpha_omit),unsigned(m.z_mode),unsigned(m.CullMode),unsigned(m.Shader_type),
        {unsigned(m.r_no_0),unsigned(m.r_no_1),unsigned(m.r_no_2),unsigned(m.r_no_3)},
        {bits(m.invisible_factor),bits(m.invisible_factor2)}};
}
template<class Manager,class M> auto existing_enemy(Manager& mgr,const M* model,unsigned& slot,unsigned& truncated)
    -> decltype(mgr.workAt(0)) {
    truncated=mgr.nArray>1024;const unsigned n=truncated?1024:unsigned(mgr.nArray);
    for(unsigned i=0;i<n;++i){auto* e=mgr.workAt(i);if(static_cast<const M*>(e)==model){slot=i;return e;}}
    slot=~0u;return nullptr;
}
}
extern "C" void re4dc_actor_vis_decline(const cModel*,unsigned,const cModelInfo* const*,unsigned);
extern "C" void re4dc_actor_vis_source(const cModel*,const cModelInfo*,const Re4dcModelPart*);
extern "C" void re4dc_actor_vis_event(unsigned,const void*,const Re4dcModelPart*,unsigned);
extern "C" void re4dc_actor_vis_source_end();
extern "C" void re4dc_actor_vis_stream(re4dc_visdiag::Stream*);
extern "C" void re4dc_actor_vis_flush(unsigned);
#define AVD_EVENT(e,n,p,d) re4dc_actor_vis_event(re4dc_visdiag::e,n,p,d)
#define AVD_IF_EVENT(c,e,n,p,d) do { if(c) AVD_EVENT(e,n,p,d); } while(0)
#else
#define AVD_EVENT(e,n,p,d) ((void)0)
#define AVD_IF_EVENT(c,e,n,p,d) ((void)0)
#endif
#endif
