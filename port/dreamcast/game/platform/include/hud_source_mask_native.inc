// Included after re4dc_ui_submit. This changes no stream, pass or list state.
extern "C" int re4dc_ui_hud_mask_submit(const Re4dcUiQuad* q,const Re4dcUiImage* mask) {
    if(!q || !mask || q->masked!=1 || q->blend>1 ||
       q->image.width!=32 || q->image.height!=32 || q->image.format!=8 ||
       q->image.palette_format!=2 || q->image.palette_bytes!=32 ||
       mask->width!=64 || mask->height!=64 || mask->palette_format!=2)return 0;
    unsigned index;
    if(mask->format==9 && mask->palette_bytes==512)index=0;
    else if(mask->format==8 && mask->palette_bytes==32)index=1;
    else return 0;
    Key color_key{},mask_key{};
    // image_key(): an adopted identity record when there is one (the CURRENT palette qualifies first),
    // otherwise the ordinary content key, hashed once and then cached per source pointer. In r19/r20
    // these three HUD textures are ordinary resident pixels (not in the core identity table), so the
    // exact-key checks below are what verify them (Claude r20 correction to hud-source-mask-r1).
    if(!image_key(q->image,color_key) || !image_key(*mask,mask_key) ||
       color_key.crc!=0x0565aab7U || color_key.fnv!=0xd85a337bU ||
       mask_key.crc!=(index?0x4453f667U:0x8f6b4eb2U) ||
       mask_key.fnv!=(index?0x45bfa53fU:0x8081114fU))return 0;
    Re4dcUiQuad prepared=*q;
    prepared.image=hud_mask_image(index);prepared.masked=0;
#if RE4DC_UI_HUD_LENS_ALPHA
    // UI_HUD_LENS_ALPHA (user, 2026-09-28: a more opaque lens): the dark backing pair's alpha is raised
    // to at least this value, so a bright world behind the lens no longer shows the unlit digit segments
    // as "88". The source colour's RGB is kept; the amber lens pair (1) is unchanged.
    if(index==0 && (prepared.color>>24)<unsigned(RE4DC_UI_HUD_LENS_ALPHA))
        prepared.color=(prepared.color&0x00ffffffU)|(unsigned(RE4DC_UI_HUD_LENS_ALPHA)<<24);
#endif
    const unsigned before=nquad;
    re4dc_ui_submit(&prepared);
    // One proof of actual queue admission per pair. Missing/invalid/resource
    // errors remain visible in the existing missing/dropped counters.
    static unsigned reported;
    if(nquad>before && !(reported&(1U<<index))) {
        reported|=1U<<index;
        re4dc_log("HUDMASK pair=%u key=%08x-%08x queued=1 blend=%u color=%08x\n",
                  index,hud_mask_keys[index].crc,hud_mask_keys[index].fnv,q->blend,q->color);
    }
    return 1;
}
