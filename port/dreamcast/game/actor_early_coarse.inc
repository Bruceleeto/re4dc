// Four-role prototype; every unsupported actor keeps its complete source path.
#include "actor_early_coarse.h"
namespace {
#if RE4DC_ACTOR_EARLY_COARSE_DIAG
unsigned early_seen,early_admitted,early_declined[6],early_checked,early_bad;
#define EARLY_COUNT(x) (++(x))
#else
#define EARLY_COUNT(x) ((void)0)
#endif
bool early_plan(cModel* m,Re4dcActorPlan& p,unsigned& why) {
    why=0;
    // Source presentation suppression and every hidden role remain source.
    // In particular a destroyed head, changed hand, hood or shadow model is
    // never substituted merely because the surviving body still matches.
    if(!m || m->id<0x10 || m->id>0x20 || m->kindid || (m->be_flag&7)!=7 ||
       m->ot_type || m->pShadowModelInfo || (s32)pG->Disp_flg<0 ||
       ((pG->Status_flg[1]&0x10000000) && !(m->be_flag&0x800)))return false;
    why=1;
    if(!re4dc_actor_plan_ganado(m,&p) || p.count!=4 || p.appearance>=5 || p.material_count!=1 || p.run_count!=4)return false;
    for(unsigned i=0;i<4;++i) {
        const auto& r=p.runs[i];const auto& c=p.input[i];
        if(!p.info[i] || !(p.info[i]->be_flag&8) || p.immutable_asset_id[i]!=9+p.appearance*4+i ||
           r.role!=i || r.material || r.immutable_asset_id!=p.immutable_asset_id[i] ||
           r.triangles!=c.triangles || r.uv.data!=c.uv.data || r.uv.size!=c.uv.size ||
           r.stream.data!=c.stream.data || r.stream.size!=c.stream.size)return false;
    }
    why=2;if(!actor_semantics(m,p))return false;
    why=3;if(!re4dc_ganado_early_ready(m))return false;
    return true;
}
}
extern "C" int re4dc_actor_early_coarse_admit(cModel* m,Re4dcActorEarlyTicket* out) {
    EARLY_COUNT(early_seen);Re4dcActorPlan p{};unsigned why=0;
    if(!out || out->texture.slot || out->texture.serial || out->binding_revision || !early_plan(m,p,why)) {
        EARLY_COUNT(early_declined[why]);return 0;
    }
    const unsigned revision=re4dc_actor_binding_revision(m);
    if(!revision){EARLY_COUNT(early_declined[4]);return 0;}
    if(!re4dc_actor_texture_acquire_next(&p.image,p.crc,p.fnv,&out->texture)) {
        EARLY_COUNT(early_declined[5]);return 0;
    }
    out->binding_revision=revision;EARLY_COUNT(early_admitted);return 1;
}
extern "C" int re4dc_actor_early_coarse_validate(cModel* m,const Re4dcActorEarlyTicket* ticket) {
    EARLY_COUNT(early_checked);Re4dcActorPlan p{};unsigned why=0;
    const bool okay=ticket && ticket->binding_revision &&
        ticket->binding_revision==re4dc_actor_binding_revision(m) && early_plan(m,p,why) &&
        re4dc_actor_texture_validate_key(&ticket->texture,p.crc,p.fnv);
    if(!okay){EARLY_COUNT(early_bad);re4dc_model_packet_abort();}
    return okay;
}
extern "C" void re4dc_actor_early_coarse_note_frame() {
#if RE4DC_ACTOR_EARLY_COARSE_DIAG
    if(!(pG->Frame_cnt%120))re4dc_log("EARLY_COARSE t=%u seen=%u admit=%u decline=%u/%u/%u/%u/%u/%u checked=%u bad=%u\n",
        unsigned(pG->Frame_cnt),early_seen,early_admitted,early_declined[0],early_declined[1],early_declined[2],
        early_declined[3],early_declined[4],early_declined[5],early_checked,early_bad);
#endif
}
#undef EARLY_COUNT
