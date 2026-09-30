#pragma once
#ifndef RE4DC_PAD_PROMPT_MANUAL_ART
#define RE4DC_PAD_PROMPT_MANUAL_ART 0
#endif
#if RE4DC_PAD_PROMPT_MANUAL_ART
enum {
    RE4DC_MANUAL_AIM=0, RE4DC_MANUAL_KNIFE, RE4DC_MANUAL_ACTION,
    RE4DC_MANUAL_CAMERA, RE4DC_MANUAL_RELOAD, RE4DC_MANUAL_KICK,
    RE4DC_MANUAL_INVENTORY, RE4DC_MANUAL_COVER1, RE4DC_MANUAL_PAGE_COUNT
};
enum { RE4DC_MANUAL_SOURCE_BYTES=115264, RE4DC_MANUAL_BUFFER_BYTES=0x20000,
       RE4DC_MANUAL_PACKAGE_BYTES=1048720,
       // tools/vq_native_ui.py: the same 1024x512 native image as full-codebook VQ (133,120 B of PVR RAM).
       // In-room VRAM has ~300 KB free, so only the VQ form of a page can upload there.
       RE4DC_MANUAL_VQ_PACKAGE_BYTES=133264 };
struct Re4dcManualPageContext {
    unsigned file_no, page, picture, message_base;
    const char* companion_path; // nullptr: exact original-only page, no replacement request
};
struct Re4dcUiImage;
// One exact original/companion pair per context; no other GX image is admitted.
extern "C" const Re4dcManualPageContext* re4dc_ui_manual_page(unsigned);
extern "C" int re4dc_ui_manual_page_available(unsigned);
extern "C" unsigned re4dc_ui_manual_page_identify(unsigned,const Re4dcUiImage*);
extern "C" int re4dc_ui_manual_page_image(unsigned,unsigned,int,Re4dcUiImage*);
// Any other file-reader picture (every ss/eng/fNNx.tpl is 640x360 CMPR): adopted by its own image key
// when the disc has that key's native package (tools/vq_native_ui.py over prepare_native_ui.py output).
enum { RE4DC_MANUAL_KIND_GENERIC=3 };
extern "C" int re4dc_ui_manual_generic_identify(const Re4dcUiImage*);
extern "C" int re4dc_ui_manual_generic_image(Re4dcUiImage*);
// Source owner: one fresh unrelocated read, revoked before request/cancel/free.
extern "C" void re4dc_manual_pages_retire();
extern "C" void re4dc_manual_pages_adopt(void*,unsigned,unsigned,unsigned);
extern "C" int re4dc_manual_page_companion_allowed(unsigned);
// Manual camera text and picture share one presentation choice per source tick.
extern "C" unsigned re4dc_manual_camera_live_kind();
extern "C" void re4dc_manual_camera_text_choice(unsigned);
#endif
