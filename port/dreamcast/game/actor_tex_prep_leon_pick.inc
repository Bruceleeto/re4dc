// Value-only access to the standard Leon atlas already selected for drawing.
// The tag is an immutable variant index, not a mutable package lifetime epoch.
extern "C" int re4dc_leon_tex_current(unsigned tag) {
#if RE4DC_CHARBAKE_TOGGLE
    if(charbake_variant>=re4dc_charbake::kCount || tag!=charbake_variant+1)return 0;
    const auto& v=re4dc_charbake::variants[charbake_variant];
    if(image.pixels!=&texture_tokens[charbake_variant] || crc!=v.leon_crc || fnv!=v.leon_fnv)return 0;
#else
    if(tag!=1 || image.pixels!=&texture_token || crc!=0xec255e66U || fnv!=0x76812316U)return 0;
#endif
    return image.width==512 && image.height==512 && image.format==6 &&
        !image.palette && image.palette_format==0xffffffffU && !image.palette_bytes;
}
extern "C" int re4dc_leon_tex_pick(unsigned appearance,Re4dcActorTexPick* out) {
    if(!out)return 0;*out={};
#if RE4DC_CHARBAKE_TOGGLE
    const unsigned tag=charbake_variant+1;
#else
    const unsigned tag=1;
#endif
    if(appearance!=0x100 || !re4dc_leon_tex_current(tag))return 0;
    const Re4dcActorTexPick pick{image,crc,fnv,0,0,Re4dcActorTexKind::PlayerLeon,tag};
    if(!re4dc_leon_tex_current(tag))return 0;
    *out=pick;return 1;
}
