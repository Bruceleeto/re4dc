// VGA_SOFT (Phase 2 C5, 2026-10-12; default 0: this file is not built; render only): the PVR's vertical filter on a
// VGA box. On a TV (interlaced) KOS's pvr_init sets SCALER_CFG's vertical scale factor to 1025, which turns on the
// scaler's 3-tap vertical filter (coefficients Y_COEFF 0x118 = 0x8040: 1/4, 1/2, 1/4, written by pvr_init on
// every cable); on VGA it leaves 1024, so VGA players get the raw progressive image. The filter runs in the tile
// write-out to the framebuffer (before the video output reads it), so it applies to progressive output too and
// costs no render time.
//
// Written once, right after pvr_init (native_ui.cpp), before any render exists: issue #11 (a VGA box, 2026-10-10)
// hung the PVR when a look preset wrote SCALER_CFG mid-render, so nothing here writes it at run time, and the look
// presets keep leaving SCALER_CFG alone on VGA. The FSAA bit (RES_MODES) is kept.
#include <kos.h>
#include <dc/pvr.h>
#include <dc/video.h>

extern "C" void re4dc_log(const char* fmt, ...);

extern "C" void re4dc_vga_soft_init(void) {
    if (!vid_mode || vid_mode->cable_type != CT_VGA) {
        re4dc_log("vga soft: not VGA (scaler %08x untouched)\n", unsigned(PVR_GET(PVR_SCALER_CFG)));
        return;
    }
    const uint32_t before = PVR_GET(PVR_SCALER_CFG);
    PVR_SET(PVR_UNK_0118, 0x00008040);   // Y_COEFF 1/4, 1/2, 1/4 (pvr_init's value, restated)
    PVR_SET(PVR_SCALER_CFG, (before & ~PVR_SCALER_CFG_VSCALE_FACTOR) | 1025U);
    re4dc_log("vga soft: vertical filter on (scaler %08x -> %08x, y_coeff %08x)\n", unsigned(before),
              unsigned(PVR_GET(PVR_SCALER_CFG)), unsigned(PVR_GET(PVR_UNK_0118)));
}
