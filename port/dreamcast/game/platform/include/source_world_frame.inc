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
bool sourceWorldContext() {
    return pG && pG->Rno0==3 && G_ROOM_ID==0x200 && (pG->System_flg&0x400) &&
        // SceEventStart sets 0x800; Render still runs the source OTs and
        // temporarily applies its scissor state. It is not a movie exclusion.
        // D29 measured r200's pre-movie draw at System_flg 0x0c40.
        !(pG->System_flg&0x100000) && !(pG->Status_flg[2]&0x04000000) &&
        !(pG->Status_flg[1]&0x100) && !re4dc_coarse_image && !re4dc_pace_skipping &&
        !re4dc_ui_movie_texture() && !re4dc_ss_ui_order();
}
void sourceWorldFail(unsigned reason) {
    ++sourceWorldFailures;
    if(sourceWorldFailures<=16 || !(re4dc_ui_frame()%120))
        re4dc_log("PS2SOURCE_DECLINE f=%u reason=%u count=%u\n",re4dc_ui_frame(),reason,sourceWorldFailures);
    sourceWorldFrame.active=false;sourceWorldFrame.ready=false;
}
// reason12 subcodes: 1 primitive metadata, 2 primitive owner, 3 cursor,
// 4 OT metadata, 5 OT owner, 6 node bounds, 7 walk limit, 8 OT epoch.
void sourceWorldMemoryFail(unsigned sub,unsigned table,unsigned long address,unsigned bytes) {
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
    return f.active && sourceWorldContext() && native==f.native && generation==f.package_generation &&
        unsigned(pG->Frame_cnt)==f.source && static_cast<unsigned long>(pG->prim_cnt)==f.prim &&
        unsigned(pG->nPrim)==f.bytes && unsigned(pG->vtx_buf_no)==f.buffer &&
        sourceWorldPrimGeneration==f.prim_generation && re4dc_source_world_ot_epoch()==f.ot_epoch &&
        reinterpret_cast<unsigned long>(GXWORK()->prim)>=f.end &&
        reinterpret_cast<unsigned long>(GXWORK()->prim)-f.begin<=f.bytes &&
        re4dc_alive_gen[2]==f.objects && re4dc_alive_gen[0]==f.pools &&
        re4dc_room4_state(&rg,&c,&b,&s,&r) && rg==f.room_generation &&
        re4dc_ps2_source_package(&pg) && pg==f.package_generation;
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
    return count!=0 && count==f.count;
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
    const int result=re4dc_ps2_source_draw(f.package_generation);
    if(result){f.started=true;if(result<0){f.failed=true;sourceWorldFail(6);}return result;}
    sourceWorldFail(7);return 0;
}
}
extern "C" int re4dc_source_world_prepare(unsigned native,unsigned* generation) {
    auto& f=sourceWorldFrame;f.active=false;f.ready=false;f.started=false;f.failed=false;f.count=0;
    if(!generation || !sourceWorldContext())return 0;
    unsigned rg=0,c,b,s,r,pg=0;
    if(!re4dc_room4_state(&rg,&c,&b,&s,&r) || !rg || !re4dc_ps2_source_package(&pg)){sourceWorldFail(1);return 0;}
    f.native=native;f.source=pG->Frame_cnt;f.room_generation=rg;f.package_generation=pg;
    f.objects=re4dc_alive_gen[2];f.pools=re4dc_alive_gen[0];
    f.prim=pG->prim_cnt;f.bytes=pG->nPrim;f.buffer=pG->vtx_buf_no;
    f.prim_generation=sourceWorldPrimGeneration;f.ot_epoch=re4dc_source_world_ot_epoch();
    if(!f.bytes || f.buffer>=RE4DC_PRIMITIVE_BUFFERS || f.bytes>~0U/RE4DC_PRIMITIVE_BUFFERS) {
        sourceWorldMemoryFail(1,~0U,f.prim,f.bytes);return 0;
    }
    if(!sourceWorldAllocated(reinterpret_cast<const void*>(f.prim),f.bytes*RE4DC_PRIMITIVE_BUFFERS,true)) {
        sourceWorldMemoryFail(2,~0U,f.prim,f.bytes*RE4DC_PRIMITIVE_BUFFERS);return 0;
    }
    f.begin=f.prim+static_cast<unsigned long>(f.bytes)*f.buffer;
    f.end=reinterpret_cast<unsigned long>(GXWORK()->prim);
    if(f.end<f.begin || f.end-f.begin>f.bytes){sourceWorldMemoryFail(3,~0U,f.end,f.bytes);return 0;}
    if(!sourceWorldWalk(true))return 0;
    f.active=f.count!=0;
    if(!sourceWorldIdentity(native,pg)){f.active=false;return 0;}
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
