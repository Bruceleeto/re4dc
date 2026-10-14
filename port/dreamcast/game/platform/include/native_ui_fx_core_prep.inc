// One early ordinary cache request from a stack-local current source proof.
// No allocator, residency, actor-lease or source callback policy is changed.
namespace {
constexpr Key kFxCoreKey{0x441a0ccaU,0x10da6929U};
unsigned fxCoreAttemptFrame=~0U,fxCorePreparedFrame,fxCorePreparedEpoch,fxCoreAcquired;
struct FxCoreCounts { unsigned attempts,ready,opens,refused,failed,draws,acquired,unused,unprepared; } fxCoreCounts{};
void fxCoreBeginFxFrame() {
    // Shared with the normal sprite call so its first draw does not discard
    // a preparation open already charged to the existing four-open cap.
    if(fx_frame!=frame){fx_frame=frame;fx_count=0;fx_new_loads=0;}
}
bool fxCoreIdentity(const Re4dcUiImage& image,Key& key) {
    return image.pixels && !image.palette && image.width==256 && image.height==256 && image.format==1 &&
        image.palette_format==0xffffffffU && image.palette_bytes==0 &&
        core_identities.lookup(image.pixels,image.width,image.height,image.format,key.crc,key.fnv,
                               image.palette,image.palette_format,image.palette_bytes)==1 && key==kFxCoreKey;
}
bool fxCoreEntry(const Entry* entry,const Key& key) {
    const auto a=reinterpret_cast<std::uintptr_t>(entry),base=reinterpret_cast<std::uintptr_t>(entries);
    if(!entry || a<base || a-base>=sizeof(entries) || (a-base)%sizeof(Entry) ||
       !entry->valid || !(entry->key==key) || entry->frame!=frame || !entry->package.upload_complete() ||
       entry->package.header().texture_count!=1 || !entry->package.pvr_texture(0) ||
       entry->package.vram_bytes()!=131072 || !entry->package.textures())return false;
    const auto& texture=entry->package.textures()[0];
    return texture.width==256 && texture.height==256 && texture.format==re4dc::texture::kArgb4444 &&
        texture.flags==re4dc::texture::kAlpha && texture.payload==re4dc::texture::kPayloadTwiddled &&
        texture.data_size==131072 && texture.reserved_0==0;
}
void fxCoreFinish() {
    if(!fxCorePreparedFrame)return;
    if(!fxCoreAcquired)++fxCoreCounts.unused;
    if(fxCoreCounts.ready<=16 || (!fxCoreAcquired && fxCoreCounts.unused<=16) || !(fxCorePreparedFrame%120))
        re4dc_log("FXCORE_USED f=%u acquired=%u potential_only=%u unused_total=%u\n",
                  fxCorePreparedFrame,fxCoreAcquired,unsigned(!fxCoreAcquired),fxCoreCounts.unused);
    if(!(fxCorePreparedFrame%120))
        re4dc_log("FXCORE_SUMMARY f=%u attempts=%u ready=%u opens=%u refused=%u failed=%u draws=%u acquired=%u unused=%u unprepared=%u\n",
            fxCorePreparedFrame,fxCoreCounts.attempts,fxCoreCounts.ready,fxCoreCounts.opens,fxCoreCounts.refused,
            fxCoreCounts.failed,fxCoreCounts.draws,fxCoreCounts.acquired,fxCoreCounts.unused,fxCoreCounts.unprepared);
    fxCorePreparedFrame=0;fxCorePreparedEpoch=0;fxCoreAcquired=0;
}
void fxCoreTexturePrepare() {
    if(fxCorePreparedFrame && fxCorePreparedFrame!=frame)fxCoreFinish();
    if(fxCoreAttemptFrame==frame)return;
    fxCoreAttemptFrame=frame;
    if(!frame || !ready || !frame_ready || stream_scene || stream_retire || stream_aborted ||
       direct_open || draining_parts || vram_claims || fx_resident_only)return;
#if RE4DC_ROUTE_MOVIES
    if(movie_texture)return;
#endif
#if RE4DC_SS_UI_ORDER
    if(re4dc_ss_ui_order())return;
#endif
    Re4dcFxCoreDemand demand;
    const int source=re4dc_fx_core_source(frame,&demand);
    if(source!=1) {
        if(source<0 && (++fxCoreCounts.refused<=16 || !(frame%120)))
            re4dc_log("FXCORE_REFUSE f=%u reason=%d total=%u\n",frame,source,fxCoreCounts.refused);
        return;
    }
    const Re4dcUiImage& image=demand.image;
    Key key{};
    const unsigned epoch=handle_reset;
    if(!fxCoreIdentity(image,key)) {
        if(++fxCoreCounts.refused<=16 || !(frame%120))
            re4dc_log("FXCORE_REFUSE f=%u reason=identity total=%u\n",frame,fxCoreCounts.refused);
        return;
    }
    fxCoreBeginFxFrame();
    if(fx_new_loads>=kFxNewLoads)return;
    ++fxCoreCounts.attempts;
    const unsigned opens=load_opens,free_before=pvr_mem_available();
#if RE4DC_UI_FRAG_RESERVE
    const unsigned held=frag_held && frag_key==key;
#else
    const unsigned held=0;
#endif
    // The complete source snapshot above precedes every loader call, including
    // a hit. Existing Package upload/close fences and ordinary frame pins apply.
    Entry* entry=load(image,true,&key);
    const unsigned opened=load_opens-opens;
    fx_new_loads+=opened;fxCoreCounts.opens+=opened;
    Key after{};
    const bool current=epoch==handle_reset && demand.native_frame==frame &&
        re4dc_fx_core_current(frame,&demand)==1 && fxCoreIdentity(image,after) && after==key;
    const bool good=current && fxCoreEntry(entry,key);
    if(good) {
        ++fxCoreCounts.ready;fxCorePreparedFrame=frame;fxCorePreparedEpoch=epoch;fxCoreAcquired=0;
    } else {
        ++fxCoreCounts.failed;
        if(entry)RE4DC_TEXCHK_FAIL(key,"fx-core-prep-proof");
    }
    if(fxCoreCounts.attempts<=16 || opened || (!good && fxCoreCounts.failed<=16) || !(frame%120)) {
        re4dc_log("FXCORE_PLAN f=%u t=%u rg=%u pg=%u slot=%u cb=%u owner=%x call=%x n=%u family=1 texowner=0 id=1d ptn=0\n",
            frame,demand.source_frame,demand.room_generation,demand.pool_generation,demand.slot,demand.callback,
            demand.owner,demand.call_no,demand.accepted);
        re4dc_log("FXCORE_PREP f=%u key=%08x-%08x ready=%u current=%u opens=%u cap=%u held=%u evict=%u free=%u->%u scene=%u\n",
            frame,key.crc,key.fnv,unsigned(good),unsigned(current),opened,fx_new_loads,held,
            unsigned(fx_evict_frame==frame),free_before,unsigned(pvr_mem_available()),unsigned(stream_scene));
    }
}
void fxCoreTextureAcquired(const Re4dcUiImage& image,const Entry* entry) {
    Key key{};
    if(!fxCoreIdentity(image,key))return;
    ++fxCoreCounts.draws;
    const bool prepared=fxCorePreparedFrame==frame && fxCorePreparedEpoch==handle_reset;
    if(!prepared)++fxCoreCounts.unprepared;
    const bool acquired=prepared && fxCoreEntry(entry,key);
    if(acquired){++fxCoreAcquired;++fxCoreCounts.acquired;}
    if(fxCoreCounts.draws<=16 || (!prepared && fxCoreCounts.unprepared<=16) || !(frame%120))
        re4dc_log("FXCORE_ACQUIRE f=%u key=%08x-%08x prepared=%u acquired=%u draws=%u unprepared=%u\n",
                  frame,key.crc,key.fnv,unsigned(prepared),unsigned(acquired),fxCoreCounts.draws,fxCoreCounts.unprepared);
}
}
