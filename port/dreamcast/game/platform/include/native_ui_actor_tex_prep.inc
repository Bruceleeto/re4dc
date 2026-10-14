// ACTOR_TEX_PREP uses the existing fenced loader and ordinary frame pin only.
// It never opens a PVR scene or creates a native-actor resource lease.
namespace {
#if RE4DC_ACTOR_TEX_PREP_DIAG
struct ActorTexPrepared { Key key{};unsigned frame=0,binds=0; };
ActorTexPrepared actor_tex_prepared[kRe4dcActorTexPicks]{};
unsigned actor_tex_prepared_count,actor_tex_reports,actor_tex_failures;
void actor_tex_prep_bound(const Key& key) {
    for(unsigned i=0;i<actor_tex_prepared_count;++i) {
        auto& p=actor_tex_prepared[i];if(p.frame!=frame || !(p.key==key))continue;
        if(!p.binds && (actor_tex_reports<12 || !(frame%120)))
            re4dc_log("ATEXP_ACQUIRE f=%u key=%08x-%08x\n",frame,key.crc,key.fnv);
        ++p.binds;return;
    }
}
#endif
void actor_texture_prepare() {
#if RE4DC_ACTOR_TEX_PREP_DIAG
    unsigned previous=0,consumed=0;
    for(unsigned i=0;i<actor_tex_prepared_count;++i) {
        previous=actor_tex_prepared[i].frame;consumed+=actor_tex_prepared[i].binds!=0;
    }
    if(actor_tex_prepared_count && (actor_tex_reports<12 || !(frame%120)))
        re4dc_log("ATEXP_USED f=%u prepared=%u acquired=%u unacquired=%u\n",previous,
            actor_tex_prepared_count,consumed,actor_tex_prepared_count-consumed);
    actor_tex_prepared_count=0;
#endif
    if(!frame_ready || stream_scene || stream_retire || stream_aborted || direct_open || vram_claims)return;
    Re4dcActorTexBatch batch{};const auto start=timer_us_gettime64();
    const int complete=re4dc_actor_tex_enumerate(&batch);
#if RE4DC_ACTOR_TEX_PREP_DIAG
    const bool report=actor_tex_reports<12 || !(frame%120);
    if(batch.candidates)++actor_tex_reports;
    if(report && batch.candidates) {
        re4dc_log("ATEXP_PLAN f=%u t=%u room=%x gen=%u models=%u candidates=%u qualified=%u keys=%u owned=%u dry=%u ok=%u\n",
            frame,batch.source.frame,batch.source.room,batch.source.room_generation,batch.models,
            batch.candidates,batch.qualified,batch.count,batch.owned,batch.dry,unsigned(complete));
        for(unsigned r=1;r<unsigned(Re4dcActorTexReason::Count);++r)if(batch.declined[r])
            re4dc_log("ATEXP_DECLINE f=%u reason=%u count=%u\n",frame,r,batch.declined[r]);
    }
#endif
    if(!complete)return;
    unsigned loaded=0;
    for(unsigned i=0;i<batch.count;++i) {
        const auto& pick=batch.picks[i];const Key key{pick.crc,pick.fnv};
        if(pick.kind==Re4dcActorTexKind::PlayerPl08) {
            if(!re4dc_player_tex_current(pick.package_generation))continue;
        } else if(pick.kind!=Re4dcActorTexKind::Ganado || batch.variant!=re4dc_ganado_tex_variant())break;
        const auto& image=pick.image; // TEX_CHECK diagnostics use the same descriptor.
        Entry* entry=load(image,true,&key);
        const bool current=pick.kind!=Re4dcActorTexKind::PlayerPl08 || re4dc_player_tex_current(pick.package_generation);
        const bool valid=current && entry && entry->valid && entry->key==key && entry->frame==frame &&
            entry->package.upload_complete() && entry->package.header().texture_count==1 &&
            entry->package.pvr_texture(0) && entry->package.textures()[0].width==pick.image.width &&
            entry->package.textures()[0].height==pick.image.height &&
            entry->package.textures()[0].format<=re4dc::texture::kArgb4444;
        if(!valid) {
            if(entry)RE4DC_TEXCHK_FAIL(key,"actor-prep-descriptor");
#if RE4DC_ACTOR_TEX_PREP_DIAG
            ++actor_tex_failures;
#endif
            re4dc_log("ATEXP_LOAD_FAIL f=%u t=%u key=%08x-%08x\n",frame,batch.source.frame,key.crc,key.fnv);
            continue; // original load/fallback/ownership paths are untouched
        }
        ++loaded;
#if RE4DC_ACTOR_TEX_PREP_DIAG
        actor_tex_prepared[actor_tex_prepared_count++]={key,frame,0};
        if(report)re4dc_log("ATEXP_KEY f=%u key=%08x-%08x apps=%x far=%u kind=%u gen=%u bytes=%u pin=%u scene=%u\n",
            frame,key.crc,key.fnv,pick.appearances,pick.far,unsigned(pick.kind),pick.package_generation,entry->package.vram_bytes(),
            entry->frame,unsigned(stream_scene));
#endif
    }
#if RE4DC_ACTOR_TEX_PREP_DIAG
    if(report && batch.count)re4dc_log("ATEXP_DONE f=%u keys=%u loaded=%u fail=%u us=%u\n",
        frame,batch.count,loaded,actor_tex_failures,unsigned(timer_us_gettime64()-start));
#else
    (void)loaded;(void)start;
#endif
}
}
