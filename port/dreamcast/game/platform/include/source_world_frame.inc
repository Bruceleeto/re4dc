// Current accepted registrations, not a visibility/lifetime replacement.
// All borrowed objects are revisited synchronously before the first native draw.
extern "C" int re4dc_room4_state(unsigned*,unsigned*,unsigned*,unsigned*,unsigned*);
extern "C" int re4dc_ui_movie_texture();
extern "C" int re4dc_ss_ui_order();
extern "C" unsigned re4dc_ui_frame();
namespace {
constexpr unsigned kSourceWorldCallbacks=90;
struct SourceWorldEntry { cModel* model;unsigned serial,work; };
struct SourceWorldFrame {
    unsigned native=0,source=0,room_generation=0,package_generation=0,objects=0,pools=0;
    unsigned prim=0,bytes=0,buffer=0,count=0;
    bool active=false,ready=false,started=false,failed=false;
    SourceWorldEntry entries[kSourceWorldCallbacks]{};
} sourceWorldFrame;
bool sourceWorldRenderActive;
unsigned sourceWorldReports,sourceWorldFailures;
bool sourceWorldContext() {
    return pG && pG->Rno0==3 && G_ROOM_ID==0x200 && (pG->System_flg&0x400) &&
        !(pG->System_flg&(0x800|0x100000)) && !(pG->Status_flg[2]&0x04000000) &&
        !(pG->Status_flg[1]&0x100) && !re4dc_coarse_image && !re4dc_pace_skipping &&
        !re4dc_ui_movie_texture() && !re4dc_ss_ui_order();
}
void sourceWorldFail(unsigned reason) {
    ++sourceWorldFailures;
    if(sourceWorldFailures<=16 || !(re4dc_ui_frame()%120))
        re4dc_log("PS2SOURCE_DECLINE f=%u reason=%u count=%u\n",re4dc_ui_frame(),reason,sourceWorldFailures);
    sourceWorldFrame.active=false;sourceWorldFrame.ready=false;
}
void sourceWorldAbort(unsigned reason) {
    if(sourceWorldFrame.failed)return;
    sourceWorldFrame.failed=true;sourceWorldFail(reason);re4dc_model_packet_abort();
}
bool sourceWorldIdentity(unsigned native,unsigned generation) {
    const auto& f=sourceWorldFrame;unsigned rg=0,c,b,s,r,pg=0;
    return f.active && sourceWorldContext() && native==f.native && generation==f.package_generation &&
        unsigned(pG->Frame_cnt)==f.source && unsigned(pG->prim_cnt)==f.prim &&
        unsigned(pG->nPrim)==f.bytes && unsigned(pG->vtx_buf_no)==f.buffer &&
        re4dc_alive_gen[2]==f.objects && re4dc_alive_gen[0]==f.pools &&
        re4dc_room4_state(&rg,&c,&b,&s,&r) && rg==f.room_generation &&
        re4dc_ps2_source_package(&pg) && pg==f.package_generation;
}
bool sourceWorldWalk(bool publish) {
    auto& f=sourceWorldFrame;unsigned count=0;
    const unsigned tables[2]={OT_TYPE_SCROLL,OT_TYPE_MODEL};
    for(unsigned table:tables){
        const auto& ot=g_OtWork[table];if(!ot.list || !ot.max)continue;
        unsigned visited=0;
        for(auto* node=&ot.list[ot.max-1];node;node=node->next){
            if(++visited>4096){sourceWorldFail(2);return false;}
            if(!node->data || node->func!=(void (*)(void*))ModelRender)continue;
            auto* model=static_cast<cModel*>(node->data);
            if(model->kindid!=2 || model->invisible_factor*model->invisible_factor2==0.f)continue;
            if(count>=kSourceWorldCallbacks){sourceWorldFail(2);return false;}
            for(unsigned i=0;i<count;++i)if(f.entries[i].model==model){sourceWorldFail(3);return false;}
            const unsigned serial=model->serial;unsigned work=~0U;
            if(!re4dc_scroll_source_member(model,serial,&work)){sourceWorldFail(4);return false;}
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
    if(f.failed)return model->kindid==2;
    if(!f.ready || !sourceWorldIdentity(f.native,f.package_generation))return false;
    for(unsigned i=0;i<f.count;++i)if(f.entries[i].model==model && f.entries[i].serial==model->serial)return true;
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
    if(!re4dc_scroll_source_member(model,model->serial,&work)) {
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
