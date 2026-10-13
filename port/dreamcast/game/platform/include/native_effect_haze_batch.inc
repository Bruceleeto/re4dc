// All-or-none private haze replacement. Scratch quads may be resolution-scaled;
// no texture upload, spill allocation, source mutation or direct stream write.
// A successful empty/cull-only batch intentionally replaces an invisible group.
extern "C" int re4dc_effect_haze_batch(Re4dcEffectSprite* sprites,unsigned count,unsigned* submitted){
    if(submitted)*submitted=0;
    if(!frame_ready || stream_aborted || draining_parts || source_draws_finished || count>12 || (!sprites && count))return 0;
    if(fx_frame!=frame){fx_frame=frame;fx_count=0;
#if defined(RE4DC_EFFECT_ROOM) && RE4DC_EFFECT_ROOM
        fx_new_loads=0;
#endif
    }
    unsigned mask=0,visible=0;
    for(unsigned n=0;n<count;++n){
        Re4dcEffectSprite& s=sprites[n];
        if(s.src!=4 || s.dst!=5 || s.screen || (s.pad&~2U) || !same_image(s.image,sprites[0].image))return 0;
        for(unsigned i=0;i<4;++i){
            if(!re4dc::render::is_finite(s.x[i]) || !re4dc::render::is_finite(s.y[i]) ||
               !re4dc::render::is_finite(s.z[i]) || s.z[i]<=0 || !re4dc::render::is_finite(s.u[i]) ||
               !re4dc::render::is_finite(s.v[i]))return 0;
#if RE4DC_RES_MODES
            s.x[i]*=re4dc_ui_sx;s.y[i]*=re4dc_ui_sy;
            if(!re4dc::render::is_finite(s.x[i]) || !re4dc::render::is_finite(s.y[i]))return 0;
#endif
        }
        if(!(s.color>>24))continue;
#if defined(RE4DC_EFFECT_ROOM) && RE4DC_EFFECT_ROOM
        float x0=s.x[0],x1=x0,y0=s.y[0],y1=y0,zmax=s.z[0];
        for(unsigned i=1;i<4;++i){x0=std::min(x0,s.x[i]);x1=std::max(x1,s.x[i]);
            y0=std::min(y0,s.y[i]);y1=std::max(y1,s.y[i]);zmax=std::max(zmax,s.z[i]);}
        if(x1<0 || x0>RE4DC_SCREEN_WF || y1<0 || y0>RE4DC_SCREEN_HF)continue;
        const float fog_far=re4dc_fog_gate_far?re4dc_fog_gate_far():0.0f;
        if(fog_far>0 && zmax*fog_far<1.0f)continue;
#endif
        mask|=1U<<n;++visible;
    }
    if(!visible){fx_culled+=count;return 1;}
    if(fx_count>RE4DC_EFFECT_SPRITE_MAX || visible>RE4DC_EFFECT_SPRITE_MAX-fx_count){++fx_capped;return 0;}
    const unsigned stride=kSpriteNode+kSpritePacket,required=visible*stride,margin=8192;
    unsigned char* storage=frame_storage;unsigned* top=&deferred_top;
    if(required+margin>deferred_top || deferred_top-required-margin<std::max(8192U,nquad*unsigned(sizeof(Re4dcUiQuad)))){
        // Borrow an already-existing spill tail only; the candidate adds no allocator.
        if(!deferred_spill || required>deferred_spill_top){++fx_dropped;return 0;}
        storage=deferred_spill;top=&deferred_spill_top;
    }
    const Re4dcUiImage& image=sprites[0].image;
    if(!image.pixels || !image.width || !image.height || image.width>1024 || image.height>1024 || !image_size(image))return 0;
    Key key{};if(!image_key(image,key))return 0;
    Entry* texture=nullptr;
    for(auto& e:entries)if(e.valid && e.key==key){texture=&e;break;}
    if(!texture){++fx_missing;return 0;}
    // No operation below can fail: reserve once, build every packet, then link.
    texture->frame=frame;
    const unsigned base=*top-required;
    DeferredPart* first=nullptr;DeferredPart* last=nullptr;unsigned offset=base;
    for(unsigned n=0;n<count;++n)if(mask&(1U<<n)){
        auto* node=new(storage+offset) DeferredPart{};node->lighting=kSpriteTag;node->changed[0]=0;
        fx_packet(sprites[n],texture,storage+offset+kSpriteNode);
        if(last)last->next=node;else first=node;last=node;offset+=stride;
    }
    *top=base;if(deferred_last)deferred_last->next=first;else deferred_first=first;deferred_last=last;
    deferred_count+=visible;fx_queued+=visible;fx_count+=visible;fx_culled+=count-visible;
    fx_peak=std::max(fx_peak,fx_count);
    frame_queue_peak=std::max(frame_queue_peak,unsigned(sizeof(frame_storage))-deferred_top+deferred_spill_capacity-deferred_spill_top);
#if RE4DC_TA_BIN_DIAG
    for(unsigned n=0;n<count;++n)if(mask&(1U<<n)){
        const auto& s=sprites[n];(s.pad&2?tabin::fill_haze:tabin::fill_fx)+=tabin::clip_area(s.x,s.y,4);
    }
#endif
    if(submitted)*submitted=visible;
    return 1;
}
