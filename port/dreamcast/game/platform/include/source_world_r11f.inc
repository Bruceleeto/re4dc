// Bounded r11f original-room presentation transaction. A source callback is a
// one-shot role, not a pointer-shaped permission to draw the native group.
extern "C" int re4dc_ui_movie_texture();
extern "C" unsigned re4dc_ui_frame();
#include "re4dc_platform.h"
#include "source_world_memory.inc"
#include "source_world_r11f_profile.h"
namespace {
#if !RE4DC_PS2_WORLD_SOURCE_OWNER
unsigned sourceWorldPrimGeneration;
#endif
namespace r11fp=source_world_r11f_profile;
struct R11fEntry {
    cModel* model;unsigned serial,work,table,kind;const void* node;bool seen;
};
struct R11fFrame {
    unsigned native=~0U,source=0,room=0,package=0,objects=0,pools=0;
    unsigned long prim=0,begin=0,end=0;
    unsigned bytes=0,buffer=0,prim_generation=0,ot_epoch=0,count=0,seen=0,anchor=~0U;
    bool planned=false,withheld=false,anchor_seen=false,started=false,failed=false;
    bool render_active=false,render_done=false,source_done=false;float uv[2]{};
    R11fEntry entries[r11fp::works]{};
    cModel* group[r11fp::works]{};
} r11fFrame;
unsigned r11fPlans,r11fDeclines,r11fAborts;
bool r11fContext() {
    return pG && pG->Rno0==3 && G_ROOM_ID==r11fp::room && (pG->System_flg&0x400) &&
        !(pG->System_flg&0x100000) && !(pG->Status_flg[2]&0x04000000) &&
        !(pG->Status_flg[1]&0x100) && !re4dc_coarse_image && !re4dc_pace_skipping &&
        !re4dc_ui_movie_texture() && !re4dc_ss_ui_order();
}
bool r11fKnownPointer(const cModel* model) {
    for(auto* captured:r11fFrame.group)if(captured==model)return true;
    return false;
}
void r11fRefuse(unsigned reason) {
    auto& f=r11fFrame;
    if(f.failed)return;
    re4dc_r11f_native_cancel(f.withheld || f.started);
    if(f.withheld || f.started) {
        f.failed=true;f.planned=false;++r11fAborts;re4dc_model_packet_abort();
        re4dc_log("R11FOWNER_ABORT f=%u t=%u reason=%u seen=%u/%u anchor=%u started=%u\n",
            f.native,f.source,reason,f.seen,f.count,unsigned(f.anchor_seen),unsigned(f.started));
    } else {
        f.planned=false;++r11fDeclines;
        if(r11fDeclines<=16 || !(f.native%120))
            re4dc_log("R11FOWNER_DECLINE f=%u reason=%u count=%u\n",f.native,reason,r11fDeclines);
    }
}
bool r11fPhaseCurrent() {
    const auto& f=r11fFrame;if(!f.anchor_seen)return true;
    if(f.anchor>=f.count)return false;const auto& e=f.entries[f.anchor];float phase[2]{};
    return re4dc_r11f_scroll_member(e.model,e.serial,e.work,phase) && phase[0]==f.uv[0] && phase[1]==f.uv[1];
}
bool r11fIdentity(unsigned native,unsigned generation,bool deep) {
    const auto& f=r11fFrame;unsigned rg=0,c,b,s,r,pg=0;
    return f.planned && !f.failed && r11fContext() && native==f.native && native==re4dc_ui_frame() && generation==f.package &&
        unsigned(pG->Frame_cnt)==f.source && static_cast<unsigned long>(pG->prim_cnt)==f.prim &&
        unsigned(pG->nPrim)==f.bytes && unsigned(pG->vtx_buf_no)==f.buffer &&
        sourceWorldPrimGeneration==f.prim_generation && re4dc_source_world_ot_epoch()==f.ot_epoch &&
        sourceWorldAllocated(reinterpret_cast<const void*>(f.prim),f.bytes*RE4DC_PRIMITIVE_BUFFERS,true) &&
        reinterpret_cast<unsigned long>(GXWORK()->prim)>=f.end &&
        reinterpret_cast<unsigned long>(GXWORK()->prim)-f.begin<=f.bytes &&
        re4dc_alive_gen[2]==f.objects && re4dc_alive_gen[0]==f.pools &&
        re4dc_room4_state(&rg,&c,&b,&s,&r) && rg==f.room &&
        re4dc_r11f_package(&pg,deep) && pg==f.package && (!deep || (re4dc_r11f_scroll_group() && r11fPhaseCurrent()));
}
bool r11fWalk(bool publish) {
    auto& f=r11fFrame;unsigned count=0,anchor=~0U;
    if(re4dc_source_world_ot_epoch()!=f.ot_epoch)return false;
    const unsigned tables[4]={0x0b,0x0d,0x10,0x11};
    for(unsigned table:tables) {
        const auto& ot=g_OtWork[table];if(!ot.list && !ot.max)continue;
        const auto buckets=reinterpret_cast<unsigned long>(ot.list);
        if(!ot.list || !ot.max || ot.max>4096 || buckets%alignof(OtData))return false;
        const unsigned bytes=unsigned(ot.max)*sizeof(OtData);
        if(!sourceWorldAllocated(ot.list,bytes,true) && !re4dc_source_world_ot_retained(ot.list,bytes))return false;
        unsigned visited=0;
        for(auto* node=&ot.list[ot.max-1];node;node=node->next) {
            const auto address=reinterpret_cast<unsigned long>(node);
            const bool bucket=address>=buckets && address-buckets<bytes && (address-buckets)%sizeof(OtData)==0;
            const bool primitive=address>=f.begin && address<=f.end && !(address&31UL) && sizeof(OtPrim)<=f.end-address;
            if(++visited>4096 || (!bucket && !primitive))return false;
            if(!node->data || node->func!=(void (*)(void*))ModelRender)continue;
            auto* model=static_cast<cModel*>(node->data);unsigned serial=0,work=~0U;
            // Existing ordered entries need only pointer/role equality here.
            // The callback validates its member; pass barriers validate the
            // whole group. Never repeatedly fingerprint every model per node.
            if(!publish && count<f.count && model==f.entries[count].model) {
                serial=f.entries[count].serial;work=f.entries[count].work;
            } else {
                const int accepted=re4dc_r11f_scroll_probe(model,&serial,&work);
                if(accepted<0 || (!publish && accepted>0))return false;
                if(!accepted)continue;
            }
            if(count>=r11fp::works || node->kind!=2 || (table!=0x0b && table!=0x10))return false;
            for(unsigned i=0;i<count;++i)if(f.entries[i].model==model)return false;
            if(work==0) {
                if(anchor!=~0U || table!=0x0b || (publish && model->ot_type!=3))return false;
                anchor=count;
            }
            if(publish)f.entries[count]={model,serial,work,table,node->kind,node,false};
            else {
                if(count>=f.count)return false;const auto& old=f.entries[count];
                if(old.model!=model || old.serial!=serial || old.work!=work || old.table!=table ||
                   old.kind!=node->kind || old.node!=node)return false;
            }
            ++count;
        }
    }
    if(publish){f.count=count;f.anchor=anchor;}
    return count && count==f.count && anchor!=~0U && anchor==f.anchor;
}
int r11fExactEntry(cModel* model) {
    auto& f=r11fFrame;Re4dcSourceWorldCallback call{};
    if(!f.render_active || !re4dc_source_world_callback_current(&call) ||
       call.callback_depth!=1 || call.model_depth!=1 || call.func!=(void(*)(void*))ModelRender || call.data!=model)return -1;
    for(unsigned i=0;i<f.count;++i) {
        const auto& e=f.entries[i];
        if(e.model==model && e.node==call.node && e.table==call.table && e.kind==call.kind)return int(i);
    }
    return -1;
}
bool sourceWorldR11fModelAborted(const cModel* model) {
    return r11fFrame.failed && r11fKnownPointer(model);
}
bool sourceWorldR11fModelBlocked(cModel* model) {
    auto& f=r11fFrame;
    if(!f.planned && !f.withheld && !f.failed)return false;
    Re4dcSourceWorldCallback call{};
    if((f.planned || f.failed) && f.render_active && re4dc_source_world_callback_current(&call) &&
       r11fKnownPointer(static_cast<const cModel*>(call.data)) &&
       (model!=call.data || call.callback_depth!=1 || call.model_depth!=1)) {
        r11fRefuse(8);return true; // reject recursive/mismatched payload before its first field read
    }
    if(!r11fKnownPointer(model))return false;
    if(f.failed)return true;
    if(f.planned && (!re4dc_source_world_pool(model,0) ||
       !re4dc_source_world_pool(model->pModelInfo,2) || !re4dc_source_world_pool(model->pList,3))) {
        f.withheld=true;r11fRefuse(8);return true; // the captured source storage retired
    }
    if(f.planned && (!r11fIdentity(f.native,f.package,false) || r11fExactEntry(model)<0)) {
        r11fRefuse(8);return f.failed;
    }
    return false;
}
struct R11fRenderScope {
    bool previous;
    R11fRenderScope():previous(r11fFrame.render_active){r11fFrame.render_active=true;}
    ~R11fRenderScope() {
        auto& f=r11fFrame;
        if(f.withheld && !f.failed && (!r11fIdentity(f.native,f.package,true) || !r11fWalk(false) ||
           !f.anchor_seen || !f.started || f.seen!=f.count))r11fRefuse(9);
        if(f.withheld && !f.failed)f.render_done=true;
        f.render_active=previous;
    }
};
bool sourceWorldR11fCandidate(cModel* model) {
    auto& f=r11fFrame;
    return (f.failed && r11fKnownPointer(model)) || (f.planned && r11fExactEntry(model)>=0);
}
int sourceWorldR11fDraw(cModel* model) {
    auto& f=r11fFrame;
    if(f.failed)return r11fKnownPointer(model)?-1:0;
    if(!f.planned)return 0;
    const int index=r11fExactEntry(model);
    if(index<0) {
        if(r11fKnownPointer(model)){r11fRefuse(8);return f.failed?-1:0;}
        return 0;
    }
    auto& e=f.entries[index];float uv[2]{};
    if(e.seen || !r11fIdentity(f.native,f.package,false) ||
       !re4dc_r11f_scroll_member(model,e.serial,e.work,e.work==0?uv:nullptr)) {
        r11fRefuse(10);return f.failed?-1:0;
    }
    if(!f.withheld || e.work==0) {
        if(!re4dc_r11f_op_window() || !r11fIdentity(f.native,f.package,true) || !r11fWalk(false)) {
            r11fRefuse(11);return f.failed?-1:0;
        }
    }
    f.withheld=true;e.seen=true;++f.seen;
    if(e.work==0) {
        if(f.anchor_seen){r11fRefuse(12);return -1;}
        f.uv[0]=uv[0];f.uv[1]=uv[1];f.anchor_seen=true;
        const int drawn=re4dc_r11f_native_draw(f.package,f.source,uv);
        if(drawn!=1){r11fRefuse(13);return -1;}
        f.started=true;
    }
    return 1;
}
}
extern "C" void re4dc_r11f_prepare(unsigned native) {
    auto& f=r11fFrame;
    if(f.native==native && (f.withheld || f.failed))return;
    if(f.native!=native)re4dc_r11f_native_frame(native);
    f.native=native;f.source=f.room=f.package=f.objects=f.pools=0;
    f.prim=f.begin=f.end=0;f.bytes=f.buffer=f.prim_generation=f.ot_epoch=f.count=f.seen=0;f.anchor=~0U;
    f.planned=f.withheld=f.anchor_seen=f.started=f.failed=f.render_active=f.render_done=f.source_done=false;f.uv[0]=f.uv[1]=0;
    for(auto& entry:f.entries)entry={};for(auto& pointer:f.group)pointer=nullptr;
    re4dc_r11f_native_cancel(0);
    if(!r11fContext())return;
    unsigned rg=0,c,b,s,r,pg=0;
    if(!re4dc_r11f_op_window() || !re4dc_room4_state(&rg,&c,&b,&s,&r) || !rg ||
       !re4dc_r11f_package(&pg,1) || !re4dc_r11f_scroll_group() ||
       !re4dc_r11f_scroll_pointers(f.group,r11fp::works)){r11fRefuse(1);return;}
    f.source=pG->Frame_cnt;f.room=rg;f.package=pg;
    f.objects=re4dc_alive_gen[2];f.pools=re4dc_alive_gen[0];
    f.prim=pG->prim_cnt;f.bytes=pG->nPrim;f.buffer=pG->vtx_buf_no;
    f.prim_generation=sourceWorldPrimGeneration;f.ot_epoch=re4dc_source_world_ot_epoch();
    if(!f.bytes || f.buffer>=RE4DC_PRIMITIVE_BUFFERS || f.bytes>~0U/RE4DC_PRIMITIVE_BUFFERS ||
       !sourceWorldAllocated(reinterpret_cast<const void*>(f.prim),f.bytes*RE4DC_PRIMITIVE_BUFFERS,true)) {
        r11fRefuse(2);return;
    }
    f.begin=f.prim+static_cast<unsigned long>(f.bytes)*f.buffer;f.end=reinterpret_cast<unsigned long>(GXWORK()->prim);
    if(f.end<f.begin || f.end-f.begin>f.bytes || !r11fWalk(true)){r11fRefuse(3);return;}
    f.planned=true;
    if(!r11fIdentity(native,pg,true) || !re4dc_r11f_native_plan(native,pg)){r11fRefuse(4);return;}
    if(++r11fPlans<=16 || !(native%120))
        re4dc_log("R11FOWNER_PLAN f=%u t=%u gen=%u package=%u callbacks=%u anchor=%u\n",native,f.source,rg,pg,f.count,f.anchor);
}
extern "C" int re4dc_r11f_check_current(unsigned native,unsigned generation,int deep) {
    return r11fIdentity(native,generation,deep!=0) && (!deep || r11fWalk(false));
}
extern "C" int re4dc_r11f_current(unsigned native,unsigned generation,int deep) {
    if(re4dc_r11f_check_current(native,generation,deep))return 1;
    if(r11fFrame.planned || r11fFrame.withheld)r11fRefuse(14);
    return 0;
}
extern "C" int re4dc_r11f_barrier(unsigned native) {
    auto& f=r11fFrame;
    if(f.failed)return 0;if(!f.planned)return 1;
    if(!f.anchor_seen || !r11fIdentity(native,f.package,true) || !r11fWalk(false))r11fRefuse(15);
    return !f.failed;
}
extern "C" void re4dc_r11f_source_finished(unsigned native,int finished,int aborted) {
    auto& f=r11fFrame;if(!f.withheld || f.failed)return;
    if(!finished || aborted || !f.render_done || f.seen!=f.count ||
       !r11fIdentity(native,f.package,true) || !r11fWalk(false) ||
       !re4dc_r11f_native_complete(native,f.package,f.source)){r11fRefuse(16);return;}
    f.source_done=true;
}
extern "C" int re4dc_r11f_present(unsigned native,int finished,int aborted) {
    auto& f=r11fFrame;
    if(f.failed)return 0;if(!f.withheld)return 1;
    if(!f.source_done || !finished || aborted || !f.render_done || f.seen!=f.count ||
       !r11fIdentity(native,f.package,true) || !r11fWalk(false) ||
       !re4dc_r11f_native_complete(native,f.package,f.source)){r11fRefuse(17);return 0;}
    return 1;
}
extern "C" int re4dc_r11f_legacy_blocked(unsigned native) {
    const auto& f=r11fFrame;
    (void)native;return f.planned || f.withheld || f.started || f.failed;
}

extern "C" int re4dc_r11f_callback_continue() {
    auto& f=r11fFrame;
    if(f.failed)return 0;if(!f.planned)return 1;
    // ExecOt calls this before the first node read and before any post-callback
    // kind/next read. A callback may have retired the current or next node.
    if(!r11fIdentity(f.native,f.package,false) || !r11fWalk(false)) {
        r11fRefuse(18);return 0;
    }
    return 1;
}
extern "C" void re4dc_r11f_pass_failed(unsigned native) {
    (void)native;if(r11fFrame.planned || r11fFrame.withheld)r11fRefuse(19);
}
