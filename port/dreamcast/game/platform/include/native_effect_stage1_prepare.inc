// One qualified existing core image, at native begin after model preparation
// and before Render submits anything. Reuses the texture cache/load path and
// the preload slot/byte/real-pool reserves. No new allocator, cache or asset.
// Every drawn frame revalidates the live source ticket and pins the real entry;
// an eviction between frames is recovered here, never inside the batch gate.
static void stage1_prepare_report(unsigned texture,const Key& key,unsigned status,unsigned bytes){
    static unsigned last_texture,last_status;static Key last_key{};
    if(texture!=last_texture || !(key==last_key) || status!=last_status){
        re4dc_log("PS2FXSTAGE1_PREP f=%u tex=%02x key=%08x-%08x status=%u bytes=%u\n",
            frame,texture,key.crc,key.fnv,status,bytes);
        last_texture=texture;last_key=key;last_status=status;
    }
}
static void stage1_prepare_image(){
    // This function has one call site in non-skipped native begin. The same
    // phase checks as the atomic batch stay intact; claims defer preparation.
    if(!frame_ready || vram_claims || source_draws_finished)return;
#if RE4DC_PVR_STREAM
    if(stream_scene || stream_aborted || stream_retire)return;
#endif
    Re4dcUiImage image{};
    const unsigned texture=re4dc_ps2_fx_stage1_image(&image);
    if(!texture){stage1_prepare_report(0,Key{},0,0);return;}
    const bool puzzle=texture==0x13;
    const Key expected=puzzle?Key{0x5889803dU,0xd2ef2224U}:Key{0xdbbad2e7U,0x5b0b1eedU};
    const unsigned width=puzzle?96U:128U;
    Key key{};
    // The live descriptor must identify the reviewed original I8 image through
    // this core owner. Never hash a discarded-texel reference as source pixels,
    // trust another owner, or substitute a hard-coded key for an unknown image.
    if((!puzzle && texture!=0x1f) || !image.pixels || image.palette || image.palette_bytes ||
       image.palette_format!=0xffffffffU || image.width!=width || image.height!=width || image.format!=1 ||
       core_identities.lookup(image.pixels,image.width,image.height,image.format,key.crc,key.fnv,
           image.palette,image.palette_format,image.palette_bytes)!=1 || !(key==expected)){
        stage1_prepare_report(texture,key,3,0);return;
    }
    for(auto& e:entries)if(e.valid && e.key==key){
        // Reuse the normal hit path (including TEX_CHECK), without an upload.
        if(load(image,true,&key))stage1_prepare_report(texture,key,2,e.package.vram_bytes());
        return;
    }
    for(const auto& m:missing_keys)if((m.crc|m.fnv) && m==key){stage1_prepare_report(texture,key,7,0);return;}
    const unsigned budget=RE4DC_UI_VRAM?vram_budget:kVramBudget;
    const unsigned reserve=RE4DC_TEX_RESIDENT_RESERVE_KB*1024U;
    const unsigned least=preload_least(image.width,image.height);
    unsigned pinned=0,pinned_bytes=0,stale=0;
    for(const auto& e:entries)if(e.valid){
        if(RE4DC_ENTRY_PINNED(e)){++pinned;pinned_bytes+=e.package.vram_bytes();}
        else stale+=e.package.vram_bytes();
    }
    if(pinned>=kTextureCount || RE4DC_TEX_RESIDENT_RESERVE_SLOTS>=kTextureCount-pinned){
        stage1_prepare_report(texture,key,4,0);return;
    }
    if(reserve>=budget || pinned_bytes>budget-reserve || least>budget-reserve-pinned_bytes){
        stage1_prepare_report(texture,key,5,0);return;
    }
#if RE4DC_TEX_KEEP
    if(pvr_mem_available()+stale<reserve+least){stage1_prepare_report(texture,key,6,0);return;}
#else
    if(used+reserve>=budget || pvr_mem_available()<reserve+least){stage1_prepare_report(texture,key,6,0);return;}
#endif
    // One request only. load owns all existing budget, missing-file, fragment,
    // fence, upload, eviction and retirement rules, exactly as preload_identities.
    Entry* entry=load(image,true,&key);
    if(entry){++preload_loads;stage1_prepare_report(texture,key,1,entry->package.vram_bytes());}
    else {++preload_skipped;stage1_prepare_report(texture,key,8,0);}
}
