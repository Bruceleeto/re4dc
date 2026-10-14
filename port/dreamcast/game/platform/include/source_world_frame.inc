// Current accepted registrations, not a visibility/lifetime replacement.
// All borrowed objects are revisited synchronously before the first native draw.
extern "C" int re4dc_room4_state(unsigned*,unsigned*,unsigned*,unsigned*,unsigned*);
extern "C" int re4dc_ui_movie_texture();
extern "C" int re4dc_ss_ui_order();
extern "C" unsigned re4dc_ui_frame();
#include "re4dc_platform.h"
#include "source_world_memory.inc"
namespace {
constexpr unsigned kSourceWorldCallbacks=90;
struct SourceWorldEntry { cModel* model;unsigned serial,work; };
struct SourceWorldFrame {
    unsigned native=0,source=0,room_generation=0,package_generation=0,objects=0,pools=0;
    unsigned long prim=0,begin=0,end=0;
    unsigned bytes=0,buffer=0,prim_generation=0,ot_epoch=0,count=0;
    bool active=false,ready=false,started=false,failed=false;
    SourceWorldEntry entries[kSourceWorldCallbacks]{};
} sourceWorldFrame;
bool sourceWorldRenderActive;
unsigned sourceWorldPrimGeneration;
unsigned sourceWorldReports,sourceWorldFailures;
#if RE4DC_PS2_WORLD_PREFLIGHT_DIAG
// Scalar observers only. CardMainTask owns System_flg 0x1000 until its objects
// and layouts are retired. Observe in r200, then record four native frames once.
struct SourceWorldDiagnostic {
    bool armed=false,used=false,active=false,done=false,draw_observed=false;
    unsigned first=0,native=0,field=0,reason=0,memory=0;
    const char* stage="idle";
    const void* model=nullptr;unsigned serial=0,work=~0U,table=~0U;int probe=0;
    void begin(unsigned frame,bool in_room,bool card) {
        active=false;native=frame;field=reason=memory=0;stage="prepare";draw_observed=false;
        model=nullptr;serial=0;work=table=~0U;probe=0;
        if(done)return;
        if(!in_room){armed=false;if(used)done=true;return;}
        if(!used){
            if(card){armed=true;return;}
            if(!armed)return;
            used=true;first=frame;
        }
        // Unsigned subtraction handles frame wrap; the window never re-arms.
        active=unsigned(frame-first)<4U;if(!active)done=true;
    }
} sourceWorldDiagnostic;
bool sourceWorldDiagTest(bool ok,unsigned field) {
    if(!ok && sourceWorldDiagnostic.active)sourceWorldDiagnostic.field=field;
    return ok;
}
void sourceWorldDiagStage(const char* stage) {
    if(sourceWorldDiagnostic.active)sourceWorldDiagnostic.stage=stage;
}
#define RE4DC_SOURCE_DIAG_TEST(test,field) sourceWorldDiagTest((test),(field))
#define RE4DC_SOURCE_DIAG_STAGE(stage) sourceWorldDiagStage(stage)
#else
#define RE4DC_SOURCE_DIAG_TEST(test,field) (test)
#define RE4DC_SOURCE_DIAG_STAGE(stage) ((void)0)
#endif
bool sourceWorldContext() {
    return RE4DC_SOURCE_DIAG_TEST(pG,1) && RE4DC_SOURCE_DIAG_TEST(pG->Rno0==3,2) &&
        RE4DC_SOURCE_DIAG_TEST(G_ROOM_ID==0x200,3) && RE4DC_SOURCE_DIAG_TEST(pG->System_flg&0x400,4) &&
        // SceEventStart's 0x800 is not a movie exclusion; source OTs still run.
        RE4DC_SOURCE_DIAG_TEST(!(pG->System_flg&0x100000),5) &&
        RE4DC_SOURCE_DIAG_TEST(!(pG->Status_flg[2]&0x04000000),6) &&
        RE4DC_SOURCE_DIAG_TEST(!(pG->Status_flg[1]&0x100),7) &&
        RE4DC_SOURCE_DIAG_TEST(!re4dc_coarse_image,8) && RE4DC_SOURCE_DIAG_TEST(!re4dc_pace_skipping,9) &&
        RE4DC_SOURCE_DIAG_TEST(!re4dc_ui_movie_texture(),10) && RE4DC_SOURCE_DIAG_TEST(!re4dc_ss_ui_order(),11);
}
void sourceWorldFail(unsigned reason) {
#if RE4DC_PS2_WORLD_PREFLIGHT_DIAG
    if(sourceWorldDiagnostic.active)sourceWorldDiagnostic.reason=reason;
#endif
    ++sourceWorldFailures;
    if(sourceWorldFailures<=16 || !(re4dc_ui_frame()%120))
        re4dc_log("PS2SOURCE_DECLINE f=%u reason=%u count=%u\n",re4dc_ui_frame(),reason,sourceWorldFailures);
    sourceWorldFrame.active=false;sourceWorldFrame.ready=false;
}
// reason12 subcodes: 1 primitive metadata, 2 primitive owner, 3 cursor,
// 4 OT metadata, 5 OT owner, 6 node bounds, 7 walk limit, 8 OT epoch.
void sourceWorldMemoryFail(unsigned sub,unsigned table,unsigned long address,unsigned bytes) {
#if RE4DC_PS2_WORLD_PREFLIGHT_DIAG
    if(sourceWorldDiagnostic.active)sourceWorldDiagnostic.memory=sub;
#endif
    if(sourceWorldFailures<16 || !(re4dc_ui_frame()%120)) {
        Re4dcSourceWorldOtMemory memory{};re4dc_source_world_ot_memory(&memory);
        re4dc_log("PS2SOURCE_MEMORY f=%u sub=%u table=%x addr=%08lx bytes=%u retained=%u:%08lx-%08lx epoch=%u/%u\n",
            re4dc_ui_frame(),sub,table,address,bytes,memory.live,memory.begin,memory.end,sourceWorldFrame.ot_epoch,memory.epoch);
    }
    sourceWorldFail(12);
}
void sourceWorldAbort(unsigned reason) {
    if(sourceWorldFrame.failed)return;
    sourceWorldFrame.failed=true;sourceWorldFail(reason);re4dc_model_packet_abort();
}
bool sourceWorldIdentity(unsigned native,unsigned generation) {
    const auto& f=sourceWorldFrame;unsigned rg=0,c,b,s,r,pg=0;
    return RE4DC_SOURCE_DIAG_TEST(f.active,20) && sourceWorldContext() &&
        RE4DC_SOURCE_DIAG_TEST(native==f.native,21) && RE4DC_SOURCE_DIAG_TEST(generation==f.package_generation,22) &&
        RE4DC_SOURCE_DIAG_TEST(unsigned(pG->Frame_cnt)==f.source,23) &&
        RE4DC_SOURCE_DIAG_TEST(static_cast<unsigned long>(pG->prim_cnt)==f.prim,24) &&
        RE4DC_SOURCE_DIAG_TEST(unsigned(pG->nPrim)==f.bytes,25) && RE4DC_SOURCE_DIAG_TEST(unsigned(pG->vtx_buf_no)==f.buffer,26) &&
        RE4DC_SOURCE_DIAG_TEST(sourceWorldPrimGeneration==f.prim_generation,27) &&
        RE4DC_SOURCE_DIAG_TEST(re4dc_source_world_ot_epoch()==f.ot_epoch,28) &&
        RE4DC_SOURCE_DIAG_TEST(reinterpret_cast<unsigned long>(GXWORK()->prim)>=f.end,29) &&
        RE4DC_SOURCE_DIAG_TEST(reinterpret_cast<unsigned long>(GXWORK()->prim)-f.begin<=f.bytes,30) &&
        RE4DC_SOURCE_DIAG_TEST(re4dc_alive_gen[2]==f.objects,31) && RE4DC_SOURCE_DIAG_TEST(re4dc_alive_gen[0]==f.pools,32) &&
        RE4DC_SOURCE_DIAG_TEST(re4dc_room4_state(&rg,&c,&b,&s,&r),33) && RE4DC_SOURCE_DIAG_TEST(rg==f.room_generation,34) &&
        RE4DC_SOURCE_DIAG_TEST(re4dc_ps2_source_package(&pg),35) && RE4DC_SOURCE_DIAG_TEST(pg==f.package_generation,36);
}
bool sourceWorldWalk(bool publish) {
    auto& f=sourceWorldFrame;unsigned count=0;
    if(re4dc_source_world_ot_epoch()!=f.ot_epoch){sourceWorldMemoryFail(8,~0U,0,0);return false;}
    // ModelTrans registers the current source callbacks into raw tables
    // 0x0b (direct), 0x0d (model depth), 0x10 (after render), 0x11 (world depth).
    // Keep this order identical to Render's scopes. The descriptive
    // OT_TYPE_SCROLL/MODEL aliases name different tables in trans_ot.h.
    const unsigned tables[4]={0x0b,0x0d,0x10,0x11};
    for(unsigned table:tables){
        const auto& ot=g_OtWork[table];if(!ot.list && !ot.max)continue;
        const auto buckets=reinterpret_cast<unsigned long>(ot.list);
        if(!ot.list || !ot.max || ot.max>4096 || buckets%alignof(OtData)) {
            sourceWorldMemoryFail(4,table,buckets,0);return false;
        }
        const unsigned bytes=unsigned(ot.max)*sizeof(OtData);
        if(!sourceWorldAllocated(ot.list,bytes,true) && !re4dc_source_world_ot_retained(ot.list,bytes)) {
            sourceWorldMemoryFail(5,table,buckets,bytes);return false;
        }
        unsigned visited=0;
        for(auto* node=&ot.list[ot.max-1];node;node=node->next){
            const auto address=reinterpret_cast<unsigned long>(node);
            const bool bucket=address>=buckets && address-buckets<unsigned(ot.max)*sizeof(OtData) &&
                (address-buckets)%sizeof(OtData)==0;
            const bool primitive=address>=f.begin && address<=f.end &&
                !(address&31UL) && sizeof(OtPrim)<=f.end-address;
            // next is read only after this iteration proved the complete node.
            if(++visited>4096){sourceWorldMemoryFail(7,table,address,sizeof(OtPrim));return false;}
            if(!bucket && !primitive){sourceWorldMemoryFail(6,table,address,sizeof(OtPrim));return false;}
            if(!node->data || node->func!=(void (*)(void*))ModelRender)continue;
            auto* model=static_cast<cModel*>(node->data);
            unsigned serial=0,work=~0U;
            const int accepted=re4dc_scroll_source_probe(model,&serial,&work);
#if RE4DC_PS2_WORLD_PREFLIGHT_DIAG
            if(sourceWorldDiagnostic.active){auto& d=sourceWorldDiagnostic;d.model=model;d.serial=serial;d.work=work;d.table=table;d.probe=accepted;}
#endif
            if(accepted<0){sourceWorldFail(4);return false;}
            if(!accepted)continue;
            if(count>=kSourceWorldCallbacks){sourceWorldFail(2);return false;}
            for(unsigned i=0;i<count;++i)if(f.entries[i].model==model){sourceWorldFail(3);return false;}
            if(publish)f.entries[count]={model,serial,work};
            else if(count>=f.count || f.entries[count].model!=model || f.entries[count].serial!=serial ||
                    f.entries[count].work!=work){sourceWorldFail(9);return false;}
            ++count;
        }
    }
    if(publish)f.count=count;
    return RE4DC_SOURCE_DIAG_TEST(count!=0,40) && RE4DC_SOURCE_DIAG_TEST(count==f.count,41);
}
struct SourceWorldRenderScope {
    bool previous;
    explicit SourceWorldRenderScope():previous(sourceWorldRenderActive){sourceWorldRenderActive=true;}
    ~SourceWorldRenderScope(){
        auto& f=sourceWorldFrame;
        if(f.started && !f.failed && f.native==re4dc_ui_frame() &&
           (!sourceWorldIdentity(f.native,f.package_generation) || !sourceWorldWalk(false)))sourceWorldAbort(11);
        sourceWorldRenderActive=previous;
    }
};
bool sourceWorldCandidate(cModel* model) {
    const auto& f=sourceWorldFrame;
    if(!sourceWorldRenderActive || f.native!=re4dc_ui_frame())return false;
    if(f.started && !f.failed && !sourceWorldIdentity(f.native,f.package_generation))sourceWorldAbort(11);
    if(f.failed) {
        // Once this image was suppressed, captured pointer values suffice to
        // keep refusing it. A retired pointer must never be read to do that.
        for(unsigned i=0;i<f.count;++i)if(f.entries[i].model==model)return true;
        return false;
    }
    if(!f.ready || !sourceWorldIdentity(f.native,f.package_generation))return false;
    for(unsigned i=0;i<f.count;++i)if(f.entries[i].model==model) {
        unsigned work=~0U;
        if(re4dc_scroll_source_member(model,f.entries[i].serial,&work) && work==f.entries[i].work)return true;
        if(f.started){sourceWorldAbort(5);return true;}
        sourceWorldFail(5);return false;
    }
    return false;
}
int sourceWorldDraw(cModel* model) {
    if(!sourceWorldCandidate(model))return 0;
    auto& f=sourceWorldFrame;
    if(f.failed)return -1;
    // Revalidate the complete accepted set before any PS2 header; a changed
    // sibling is a whole-frame refusal, never a silent per-object omission.
    if(!f.started && !sourceWorldWalk(false))return 0;
    unsigned work=~0U;
    unsigned serial=0;
    for(unsigned i=0;i<f.count;++i)if(f.entries[i].model==model){serial=f.entries[i].serial;break;}
    if(!re4dc_scroll_source_member(model,serial,&work)) {
        const bool started=f.started;sourceWorldFail(5);
        if(started){sourceWorldAbort(5);return -1;}return 0;
    }
#if RE4DC_PS2_WORLD_PREFLIGHT_DIAG
    if(sourceWorldDiagnostic.active && !sourceWorldDiagnostic.draw_observed){
        sourceWorldDiagnostic.draw_observed=true;
        re4dc_log("PS2PF owned f=%u model=%p serial=%u work=%u\n",re4dc_ui_frame(),static_cast<void*>(model),serial,work);
    }
#endif
    const int result=re4dc_ps2_source_draw(f.package_generation);
    if(result){f.started=true;if(result<0){f.failed=true;sourceWorldFail(6);}return result;}
    sourceWorldFail(7);return 0;
}
}
extern "C" int re4dc_source_world_prepare(unsigned native,unsigned* generation) {
    auto& f=sourceWorldFrame;f.active=false;f.ready=false;f.started=false;f.failed=false;f.count=0;
    RE4DC_SOURCE_DIAG_STAGE("context");
    if(!RE4DC_SOURCE_DIAG_TEST(generation,12) || !sourceWorldContext())return 0;
    RE4DC_SOURCE_DIAG_STAGE("room-package");
    unsigned rg=0,c,b,s,r,pg=0;
    if(!RE4DC_SOURCE_DIAG_TEST(re4dc_room4_state(&rg,&c,&b,&s,&r),13) ||
       !RE4DC_SOURCE_DIAG_TEST(rg,14) || !RE4DC_SOURCE_DIAG_TEST(re4dc_ps2_source_package(&pg),15)){sourceWorldFail(1);return 0;}
    f.native=native;f.source=pG->Frame_cnt;f.room_generation=rg;f.package_generation=pg;
    f.objects=re4dc_alive_gen[2];f.pools=re4dc_alive_gen[0];
    f.prim=pG->prim_cnt;f.bytes=pG->nPrim;f.buffer=pG->vtx_buf_no;
    f.prim_generation=sourceWorldPrimGeneration;f.ot_epoch=re4dc_source_world_ot_epoch();
    RE4DC_SOURCE_DIAG_STAGE("primitive-meta");
    if(!f.bytes || f.buffer>=RE4DC_PRIMITIVE_BUFFERS || f.bytes>~0U/RE4DC_PRIMITIVE_BUFFERS) {
        sourceWorldMemoryFail(1,~0U,f.prim,f.bytes);return 0;
    }
    RE4DC_SOURCE_DIAG_STAGE("primitive-owner");
    if(!sourceWorldAllocated(reinterpret_cast<const void*>(f.prim),f.bytes*RE4DC_PRIMITIVE_BUFFERS,true)) {
        sourceWorldMemoryFail(2,~0U,f.prim,f.bytes*RE4DC_PRIMITIVE_BUFFERS);return 0;
    }
    f.begin=f.prim+static_cast<unsigned long>(f.bytes)*f.buffer;
    f.end=reinterpret_cast<unsigned long>(GXWORK()->prim);
    RE4DC_SOURCE_DIAG_STAGE("primitive-cursor");
    if(f.end<f.begin || f.end-f.begin>f.bytes){sourceWorldMemoryFail(3,~0U,f.end,f.bytes);return 0;}
    RE4DC_SOURCE_DIAG_STAGE("walk");
    if(!sourceWorldWalk(true))return 0;
    f.active=f.count!=0;
    RE4DC_SOURCE_DIAG_STAGE("identity");
    if(!sourceWorldIdentity(native,pg)){f.active=false;return 0;}
    RE4DC_SOURCE_DIAG_STAGE("accepted");
    *generation=pg;
#if !RE4DC_PS2_WORLD_SOURCE_TEX_PREP
    f.ready=true;
#endif
    if(++sourceWorldReports<=16 || !(native%120))
        re4dc_log("PS2SOURCE_PLAN f=%u t=%u room=200 gen=%u package=%u callbacks=%u\n",native,f.source,rg,pg,f.count);
    return 1;
}
extern "C" int re4dc_source_world_current(unsigned native,unsigned generation) {
    return sourceWorldFrame.ready && sourceWorldIdentity(native,generation);
}
extern "C" void re4dc_source_world_prepared(unsigned native,unsigned generation,int ready) {
    if(!ready || !sourceWorldIdentity(native,generation)){sourceWorldFail(8);return;}
    sourceWorldFrame.ready=true;
}
extern "C" void re4dc_source_world_flush_result(unsigned native,int complete) {
    if(sourceWorldFrame.native==native && sourceWorldFrame.started && !complete){
        sourceWorldAbort(10);
    }
}

#if RE4DC_PS2_WORLD_PREFLIGHT_DIAG
extern "C" void re4dc_source_world_diag_begin(unsigned native) {
    sourceWorldDiagnostic.begin(native,pG && G_ROOM_ID==0x200,pG && (pG->System_flg&0x1000));
}
extern "C" int re4dc_source_world_diag_active(unsigned native) {
    return sourceWorldDiagnostic.active && sourceWorldDiagnostic.native==native;
}
extern "C" void re4dc_source_world_diag_report(unsigned native,const char* where) {
    if(!re4dc_source_world_diag_active(native))return;
    const auto& d=sourceWorldDiagnostic;const auto& f=sourceWorldFrame;
    re4dc_log("PS2PF source f=%u where=%s stage=%s field=%u reason=%u memory=%u callbacks=%u ticket=%u/%u/%u/%u source=%u/%u sys=%08x status=%08x/%08x mode=%u coarse=%u pace=%u epochs=%u/%u package=%u\n",
        native,where,d.stage,d.field,d.reason,d.memory,f.count,unsigned(f.active),unsigned(f.ready),unsigned(f.started),unsigned(f.failed),
        pG?unsigned(pG->Frame_cnt):0U,f.source,pG?unsigned(pG->System_flg):0U,
        pG?unsigned(pG->Status_flg[1]):0U,pG?unsigned(pG->Status_flg[2]):0U,pG?unsigned(pG->Rno0):0U,
        unsigned(re4dc_coarse_image),unsigned(re4dc_pace_skipping),sourceWorldPrimGeneration,f.prim_generation,f.package_generation);
    if(d.model)re4dc_log("PS2PF walk-last f=%u where=%s table=%x model=%p serial=%u work=%u accepted=%d\n",
        native,where,d.table,d.model,d.serial,d.work,d.probe);
}
#endif
#undef RE4DC_SOURCE_DIAG_TEST
#undef RE4DC_SOURCE_DIAG_STAGE
