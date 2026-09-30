// ui_bridge.cpp only. Original ss_Draw_tpl -> DrawTexture OT path is retained.
static const void* manual_pages_pixels;
static unsigned manual_pages_row=RE4DC_MANUAL_PAGE_COUNT,manual_pages_kind;
extern "C" void re4dc_manual_pages_retire(){
    manual_pages_pixels=0;manual_pages_row=RE4DC_MANUAL_PAGE_COUNT;manual_pages_kind=0;
}
extern "C" int re4dc_manual_page_companion_allowed(unsigned row){
    const Re4dcManualPageContext* context=re4dc_ui_manual_page(row);
    if(!context || !context->companion_path)return 0; // original-only cover
    if(row>=RE4DC_MANUAL_PAGE_COUNT || !pSys || !pG || pSys->language!=1 ||
       pSys->key_type!=0 || pG->pl_type!=0 || !re4dc_pad_manual_standard(0))return 0;
    // Source option changes remain authoritative, including while a page is open.
    if(row==RE4DC_MANUAL_KNIFE && (pSys->flags&0x04000000U))return 0;
    if(row==RE4DC_MANUAL_RELOAD && PlKeyReloadType!=0)return 0;
    return 1;
}
// This is presentation publication only; it never polls or remaps input.
static unsigned manual_camera_text_frame,manual_camera_text_kind=3;
extern "C" unsigned re4dc_manual_camera_live_kind(){
    if(!pSys || !pG || pSys->language!=1 || pSys->key_type!=0 || pG->pl_type!=0)
        return RE4DC_PROMPT_UNKNOWN;
    const unsigned kind=re4dc_pad_prompt_kind(0,0);
    if(kind==RE4DC_PROMPT_DPAD && !re4dc_pad_manual_standard(0))return RE4DC_PROMPT_UNKNOWN;
    return kind;
}
extern "C" void re4dc_manual_camera_text_choice(unsigned kind){
    manual_camera_text_kind=kind;
    manual_camera_text_frame=pG ? pG->Frame_cnt : 0;
}
extern "C" void re4dc_manual_pages_adopt(void* memory,unsigned bytes,unsigned row,unsigned requested_kind){
    re4dc_manual_pages_retire();
    const bool generic=requested_kind==RE4DC_MANUAL_KIND_GENERIC;
    if(!memory || (!generic && (row>=RE4DC_MANUAL_PAGE_COUNT || requested_kind<1 || requested_kind>2)) ||
       bytes!=RE4DC_MANUAL_SOURCE_BYTES || bytes>RE4DC_MANUAL_BUFFER_BYTES)return;
    const unsigned char* b=static_cast<const unsigned char*>(memory);
    // The exact standalone LE header binds descriptor/image offsets and sampler,
    // LOD, palette absence, unpacked flags and padding. No permissive TPL walker.
    static const unsigned char header[64]={
        0x30,0xaf,0x20,0, 1,0,0,0, 12,0,0,0, 20,0,0,0,
        0,0,0,0, 0x68,1,0x80,2, 14,0,0,0, 64,0,0,0,
        0,0,0,0, 0,0,0,0, 1,0,0,0, 1,0,0,0,
        0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,0,0
    };
    for(unsigned i=0;i<sizeof(header);++i)if(b[i]!=header[i])return;
    const Re4dcUiImage source={b+64,0,640,360,14,0xffffffffU,0};
    if(generic){
        if(re4dc_ui_manual_generic_identify(&source)){
            manual_pages_pixels=b+64;manual_pages_row=RE4DC_MANUAL_PAGE_COUNT;manual_pages_kind=RE4DC_MANUAL_KIND_GENERIC;
        }
        return;
    }
    const unsigned kind=re4dc_ui_manual_page_identify(row,&source);
    if(kind==requested_kind){manual_pages_pixels=b+64;manual_pages_row=row;manual_pages_kind=kind;}
}
extern "C" int re4dc_draw_manual_pages(GXTexObj* obj,short x,short y,short z,short w,short h){
    if(!manual_pages_kind || GXGetTexObjData(obj)!=manual_pages_pixels)return 0;
    Re4dcUiQuad q={};
    int companion=0;
    if(manual_pages_kind==RE4DC_MANUAL_KIND_GENERIC){
        if(!re4dc_ui_manual_generic_image(&q.image))return 0;   // no package / no room: the source path
    } else {
    companion=re4dc_manual_page_companion_allowed(manual_pages_row);
    if(manual_pages_row==RE4DC_MANUAL_CAMERA){
        // Retain original art for secondary/neutral help. D-pad text selects
        // only the approved D-pad image, even if an original TPL was read first.
        if(!pG || manual_camera_text_frame!=pG->Frame_cnt || manual_camera_text_kind>2 ||
           manual_camera_text_kind!=re4dc_manual_camera_live_kind())return 1;
        companion=manual_camera_text_kind==RE4DC_PROMPT_DPAD;
    }
    if(!re4dc_ui_manual_page_image(manual_pages_row,manual_pages_kind,companion,&q.image)){
        // A denied companion is still physically in this source buffer. Never
        // fall through to GX with those bytes when the exact original cannot
        // load: consume this image only; original text/input remain live.
        return manual_pages_row==RE4DC_MANUAL_CAMERA || (manual_pages_kind==2 && !companion) ? 1 : 0;
    }
    }
    const short x2=(short)(x+w),y2=(short)(y+h);
    const short xx[4]={x,x2,x2,x},yy[4]={y,y,y2,y2};
    float projection[7],viewport[6];Mtx identity;
    GXGetProjectionv(projection);GXGetViewportv(viewport);PSMTXIdentity(identity);
    if(viewport[2]<=0 || viewport[3]<=0)return 0;
    for(unsigned i=0;i<4;++i){
        float sx,sy,sz;
        GXProject(xx[i],yy[i],z,identity,projection,viewport,&sx,&sy,&sz);
        q.xy[2*i]=sx*640.0f/viewport[2];q.xy[2*i+1]=sy*480.0f/viewport[3];
    }
    const float uv[8]={0,0,1,0,1,1,0,1};
    for(unsigned i=0;i<8;++i)q.uv[i]=uv[i];
    // All admitted assets are opaque RGB565. Preserve the established manual
    // callback's projected rectangle, alpha1 blend and always/no-write UI depth.
    q.color=0xffffffffU;q.blend=0;q.masked=0;
    re4dc_ui_submit(&q);return 1;
}
