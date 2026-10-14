// Immutable atlas mapping only: neither charbake_keys' lazy cache nor far skin
// initialization is called. The ordinary later owner plan remains unchanged.
#include "actor_tex_prep.h"
static_assert(gc::texture_count<=kRe4dcActorTexPicks,"bounded Ganado atlas hints");
extern "C" unsigned re4dc_ganado_tex_variant() {
#if RE4DC_CHARBAKE_TOGGLE
    return charbake_variant;
#else
    return 0;
#endif
}
namespace {
Re4dcActorTexPick actor_tex_pick(unsigned t,unsigned app,bool far) {
    auto key=gc::textures[t];
#if RE4DC_CHARBAKE_TOGGLE
    // Same selector as charbake_keys(), without modifying its cache.
    if(key.crc==re4dc_charbake::kGanadoCrc && key.fnv==re4dc_charbake::kGanadoFnv) {
        const auto& variant=re4dc_charbake::variants[charbake_variant];
        key.crc=variant.ganado_crc;key.fnv=variant.ganado_fnv;
    }
#endif
    return {image_of(t),key.crc,key.fnv,1u<<app,unsigned(far)};
}
}
extern "C" int re4dc_ganado_tex_picks(unsigned app,unsigned variant,Re4dcActorTexPick* output,unsigned* count) {
    if(!output || !count)return 0;*count=0;
    if(app>=kApps || variant!=re4dc_ganado_tex_variant())return 0;
    const unsigned near=gc::appearance_texture[app];if(near>=gc::texture_count)return 0;
    output[0]=actor_tex_pick(near,app,false);unsigned n=1;
#if RE4DC_CROWD_FAR
    // The rank/policy and skin owner are intentionally not consulted. A valid
    // far bundle may use another near-table atlas; nominate its value as well.
    // A mismatched bundle keeps the original plan's near fallback.
    if(far_same(app+kApps)) {
        const unsigned far=far_texture(app);
        if(far>=gc::texture_count)return 0;
        if(far!=near)output[n++]=actor_tex_pick(far,app,true);
    }
#endif
    if(variant!=re4dc_ganado_tex_variant())return 0;
    *count=n;return 1;
}
