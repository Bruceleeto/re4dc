// Ordinary fenced cache loading and the ordinary current-frame pin. No scene,
// queue, actor lease, preload priority or persistent residency policy changes.
namespace {
#if RE4DC_PS2_WORLD_SOURCE_TEX_PREP
Key sourceWorldPreparedKey{};unsigned sourceWorldPreparedFrame,sourceWorldAcquired;
void sourceWorldTextureAcquired(const Key& key) {
    if(frame!=sourceWorldPreparedFrame || !(key==sourceWorldPreparedKey) || sourceWorldAcquired)return;
    sourceWorldAcquired=1;
    re4dc_log("PS2SOURCE_TEX_ACQUIRE f=%u key=%08x-%08x\n",frame,key.crc,key.fnv);
}
#endif
void sourceWorldTexturePrepare() {
#if RE4DC_PS2_WORLD_SOURCE_TEX_PREP
    if(sourceWorldPreparedFrame)re4dc_log("PS2SOURCE_TEX_USED f=%u acquired=%u\n",sourceWorldPreparedFrame,sourceWorldAcquired);
    sourceWorldPreparedFrame=0;sourceWorldAcquired=0;
#endif
    // Also call prepare with an unusable frame to retire any previous ticket.
    unsigned generation=0;
    if(!re4dc_source_world_prepare(frame,&generation))return;
    if(!frame_ready || stream_scene || stream_retire || stream_aborted || direct_open || vram_claims){
        re4dc_source_world_prepared(frame,generation,0);return;
    }
#if RE4DC_PS2_WORLD_SOURCE_TEX_PREP
    Re4dcSourceWorldTexture pick{};
    if(!re4dc_ps2_source_texture(generation,&pick)){re4dc_source_world_prepared(frame,generation,0);return;}
    const Key key{pick.crc,pick.fnv};
    const Re4dcUiImage image{&key,nullptr,pick.width,pick.height,5,0,0};
    Entry* entry=load(image,true,&key);
    unsigned current=0;
    const bool valid=re4dc_ps2_source_package(&current) && current==generation &&
        entry && entry->valid && entry->key==key && entry->frame==frame &&
        entry->package.upload_complete() && entry->package.header().texture_count==1 &&
        entry->package.pvr_texture(0) && entry->package.vram_bytes()==pick.bytes &&
        entry->package.textures()[0].width==pick.width && entry->package.textures()[0].height==pick.height;
    re4dc_source_world_prepared(frame,generation,valid);
    const bool ready=valid && re4dc_source_world_current(frame,generation);
    if(ready){sourceWorldPreparedFrame=frame;sourceWorldPreparedKey=key;}
    re4dc_log("PS2SOURCE_TEX_PREP f=%u gen=%u key=%08x-%08x ready=%u bytes=%u scene=%u\n",
        frame,generation,key.crc,key.fnv,unsigned(ready),ready?unsigned(entry->package.vram_bytes()):0U,unsigned(stream_scene));
    if(!ready && entry)RE4DC_TEXCHK_FAIL(key,"source-world-prep-descriptor");
#endif
}
}
