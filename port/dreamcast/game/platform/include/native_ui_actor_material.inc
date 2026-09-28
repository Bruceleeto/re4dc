// Include once beside r1's actor texture lease API, under ACTOR_TRANSACTION.
// Key/entry identity only: no texture load, memory allocation, header or SQ.
extern "C" int re4dc_actor_texture_material_validate(const Re4dcModelPart* p,const Re4dcActorTextureLease* lease) {
    if(!p || !re4dc_actor_texture_validate(lease))return 0;
    unsigned index;if(!actor_texture_leases.resolve(*lease,frame,index))return 0;
    Key requested{};
    if(p->material_flags&4) {
#if RE4DC_D349_RENDERER_STACK
        if(!p->mask.pixels || !p->mask_same_uv || p->mask_ref || p->mask.width!=p->image.width || p->mask.height!=p->image.height ||
           !model_mask_key(p,requested))return 0;
#else
        return 0;
#endif
    } else if(!image_key(p->image,requested))return 0;
    const auto& e=entries[index];if(!(e.key==requested) || e.package.header().texture_count!=1)return 0;
    const auto& t=e.package.textures()[0];
    if((p->wrap_s && t.width!=p->image.width) || (p->wrap_t && t.height!=p->image.height))return 0;
    if((p->material_flags&4) && t.format!=re4dc::texture::kArgb4444)return 0;
    return 1;
}
