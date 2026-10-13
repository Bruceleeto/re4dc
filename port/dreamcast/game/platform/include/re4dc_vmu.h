#ifndef RE4DC_VMU_H
#define RE4DC_VMU_H
// Forced into only the enabled Dreamcast objects; shared PPC compiles never see it.
#if defined(RE4DC_VMU_CONTEXT) && RE4DC_VMU_CONTEXT && !defined(__PPC__)
extern "C" {
void re4dc_vmu_snapshot();
void re4dc_vmu_poll();
void re4dc_vmu_reset();
void re4dc_vmu_invalidate();
void re4dc_vmu_call(int no);
void re4dc_vmu_companion(void* instance,int kind);
void re4dc_vmu_speed(const void* frame,int enabled);
void re4dc_vmu_debug(const void* frame);
}
#endif
#endif
