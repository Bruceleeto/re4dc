// Included beside Trans's completed source ledger. This read-only capability
// does not set SourceActorRenderActive, claim a preparation or choose a draw.
namespace {
bool sourceActorTexStorage(const void* p,unsigned bytes) {
    if(!p || (reinterpret_cast<std::uintptr_t>(p)&3u))return false;
#if defined(__sh__)
    const auto a=reinterpret_cast<std::uintptr_t>(p);
    return a>=RE4_MEM_LO && a<=RE4_MEM_HI && bytes<=RE4_MEM_HI-a;
#else
    (void)bytes;return true; // the host harness supplies real source objects
#endif
}
bool sourceActorTexPickEqual(const Re4dcActorTexPick& a,const Re4dcActorTexPick& b) {
    return a.kind==b.kind && a.package_generation==b.package_generation &&
        a.crc==b.crc && a.fnv==b.fnv && a.image.width==b.image.width &&
        a.image.height==b.image.height && a.image.format==b.image.format;
}
}
extern "C" int re4dc_actor_tex_source_current(cModel* m,const FrameIdentity* frame,const ModelIdentity* model) {
    FrameIdentity now{};
    return frame && model && sourceActorTexStorage(m,sizeof(*m)) && sourceActorActive &&
        !sourceActorRenderActive && sourceActorIdentity(now) && now==*frame &&
        sourceActorLedger.ready(now) && sourceActorModel(m)==*model &&
        sourceActorLedger.membership(now,*model)==Membership::SourceHandled;
}
extern "C" int re4dc_actor_tex_enumerate(Re4dcActorTexBatch* output) {
    if(!output)return 0;*output=Re4dcActorTexBatch{};
    Re4dcActorTexBatch batch{};FrameIdentity now{};unsigned serial=0,epoch=0;
    auto fail=[&](Re4dcActorTexReason reason) {
        // Diagnostic values survive; no partially proved picks escape.
        batch.count=0;for(auto& p:batch.picks)p={};
        ++batch.declined[unsigned(reason)];*output=batch;return 0;
    };
    if(!sourceActorActive || sourceActorRenderActive || !sourceActorIdentity(now) ||
       !sourceActorLedger.ready(now))return fail(Re4dcActorTexReason::Source);
    batch.source=now;batch.variant=re4dc_ganado_tex_variant();
    if(!re4dc_actor_tex_lifetime(&serial,&epoch))return fail(Re4dcActorTexReason::Lifetime);
    const auto* head=EmMgr.pAlive;const unsigned capacity=EmMgr.nArray,expected=sourceActorCount;
    auto* player=pPL;auto* partner=pSUB;unsigned player_keys=0,ganado_keys=0;
    bool player_seen=!player,partner_seen=!partner;
    for(cUnit* u=EmMgr.pAlive;u;u=u->pNext) {
        if(!sourceActorTexStorage(u,sizeof(cModel)) || batch.models>=capacity ||
           batch.models>=expected || batch.models>=re4dc_source::FrameLedger::MaxEntries)
            return fail(Re4dcActorTexReason::Chain);
        cModel* m=(cModel*)u;const ModelIdentity model=sourceActorModel(m);++batch.models;
        if(!re4dc_actor_tex_source_current(m,&now,&model))return fail(Re4dcActorTexReason::Source);
        player_seen|=m==(cModel*)player;partner_seen|=m==(cModel*)partner;
        const bool is_player=m==(cModel*)player;
        if(!is_player && (m==(cModel*)partner || m->id<0x10 || m->id>0x20))continue;
        ++batch.candidates;
#if RE4DC_ACTOR_TEX_PREP_DRAW
        // An optional Ganado preload needs an actual source OT preparation in
        // this exact completed ledger, not merely an alive-list emTrans call.
        // This hint cannot suppress a later draw or grant a texture lease.
        if(!is_player && !sourceActorLedger.texture_draw(now,model)) {
            ++batch.declined[unsigned(Re4dcActorTexReason::Hidden)];continue;
        }
#endif
        Re4dcActorTexMetadata metadata{};
        unsigned reason=is_player?re4dc_player_tex_metadata(m,&now,&model,&metadata):
            re4dc_actor_tex_metadata(m,&now,&model,&metadata);
#if RE4DC_ACTOR_TEX_PREP_LEON
        if(is_player && reason)reason=re4dc_leon_tex_metadata(m,&now,&model,&metadata);
#endif
        if(reason) {
            if(reason>=unsigned(Re4dcActorTexReason::Count))return fail(Re4dcActorTexReason::Changed);
            ++batch.declined[reason];continue;
        }
        Re4dcActorTexPick picks[2]{};unsigned count=0;
        if(is_player) {
#if RE4DC_ACTOR_TEX_PREP_LEON
            if(metadata.appearance==0x100) {
                if(player_keys || !re4dc_leon_tex_pick(metadata.appearance,picks) ||
                   picks[0].kind!=Re4dcActorTexKind::PlayerLeon ||
                   picks[0].package_generation!=metadata.package_generation)return fail(Re4dcActorTexReason::Changed);
            } else
#endif
            if(player_keys || !re4dc_player_tex_pick(metadata.appearance,picks) ||
               picks[0].kind!=Re4dcActorTexKind::PlayerPl08 ||
               picks[0].package_generation!=metadata.package_generation)return fail(Re4dcActorTexReason::Changed);
            count=1;
        } else if(!re4dc_ganado_tex_picks(metadata.appearance,batch.variant,picks,&count) || !count || count>2)
            return fail(Re4dcActorTexReason::Variant);
        ++batch.qualified;batch.owned+=metadata.owned;batch.dry+=metadata.dry;
        for(unsigned n=0;n<count;++n) {
            auto& p=picks[n];unsigned at=0;
            for(;at<batch.count;++at)if(sourceActorTexPickEqual(batch.picks[at],p))break;
            if(at==batch.count) {
                if(batch.count==kRe4dcActorTexPicks || (!is_player && ganado_keys==kRe4dcGanadoTexPicks))
                    return fail(Re4dcActorTexReason::Capacity);
                batch.picks[batch.count++]=p;
                if(is_player)++player_keys;else ++ganado_keys;
            } else {batch.picks[at].appearances|=p.appearances;batch.picks[at].far|=p.far;}
        }
    }
    FrameIdentity after{};unsigned after_serial=0,after_epoch=0;
    if(batch.models!=expected || !player_seen || !partner_seen || EmMgr.pAlive!=head ||
       EmMgr.nArray!=capacity || sourceActorCount!=expected || pPL!=player || pSUB!=partner ||
       !sourceActorIdentity(after) || !(after==now) || !sourceActorLedger.ready(after) ||
       !re4dc_actor_tex_lifetime(&after_serial,&after_epoch) || serial!=after_serial || epoch!=after_epoch ||
       batch.variant!=re4dc_ganado_tex_variant())return fail(Re4dcActorTexReason::Changed);
    // Rewalk identity membership before publishing value-only output. Bounded
    // counts also reject a cyclic/repeated source chain without an allocation.
    unsigned checked=0;
    for(cUnit* u=EmMgr.pAlive;u;u=u->pNext) {
        if(!sourceActorTexStorage(u,sizeof(cModel)) || checked++>=expected)return fail(Re4dcActorTexReason::Chain);
        cModel* m=(cModel*)u;const auto model=sourceActorModel(m);
        if(!re4dc_actor_tex_source_current(m,&now,&model))return fail(Re4dcActorTexReason::Changed);
    }
    if(checked!=expected)return fail(Re4dcActorTexReason::Changed);
    // The single player atlas goes first, then the unchanged Ganado key order.
    // The real cache/package accounts VRAM; these are not size estimates.
    for(unsigned i=1;i<batch.count;++i) {
        auto p=batch.picks[i];unsigned j=i;
        while(j && (unsigned(batch.picks[j-1].kind)<unsigned(p.kind) ||
              (batch.picks[j-1].kind==p.kind && (batch.picks[j-1].crc>p.crc ||
               (batch.picks[j-1].crc==p.crc && batch.picks[j-1].fnv>p.fnv))))) {
            batch.picks[j]=batch.picks[j-1];--j;
        }
        batch.picks[j]=p;
    }
    for(unsigned i=0;i<batch.count;++i)if(batch.picks[i].kind==Re4dcActorTexKind::PlayerPl08 &&
        !re4dc_player_tex_current(batch.picks[i].package_generation))return fail(Re4dcActorTexReason::Changed);
#if RE4DC_ACTOR_TEX_PREP_LEON
    for(unsigned i=0;i<batch.count;++i)if(batch.picks[i].kind==Re4dcActorTexKind::PlayerLeon &&
        !re4dc_leon_tex_current(batch.picks[i].package_generation))return fail(Re4dcActorTexReason::Changed);
#endif
    *output=batch;return 1;
}
