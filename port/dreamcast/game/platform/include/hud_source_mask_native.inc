// Included after re4dc_ui_submit. This changes no stream, pass or list state.
extern "C" int re4dc_ui_hud_mask_submit(const Re4dcUiQuad* q,const Re4dcUiImage* mask) {
    if(!q || !mask || q->masked!=1 || q->blend>1 ||
       q->image.width!=32 || q->image.height!=32 || q->image.format!=8 ||
       q->image.palette_format!=2 || q->image.palette_bytes!=32 ||
       mask->width!=64 || mask->height!=64 || mask->palette_format!=2){
#if RE4DC_UI_HUD_MASK_DIAG
        static unsigned d0;if(d0<8){++d0;re4dc_log("HUDDIAG reject=shape mask=%ux%u fmt=%u pal=%u/%u\n",mask?mask->width:0,mask?mask->height:0,mask?mask->format:0,mask?mask->palette_format:0,mask?mask->palette_bytes:0);}
#endif
        return 0;}
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
       mask_key.fnv!=(index?0x45bfa53fU:0x8081114fU)){
#if RE4DC_UI_HUD_MASK_DIAG
        static unsigned d1;if(d1<8){++d1;re4dc_log("HUDDIAG reject=identity color=%08x-%08x mask=%08x-%08x index=%u\n",color_key.crc,color_key.fnv,mask_key.crc,mask_key.fnv,index);}
#endif
        return 0;}
    Re4dcUiQuad prepared=*q;
    prepared.image=hud_mask_image(index);prepared.masked=0;
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
