// res_mode.cpp -- RES_MODES (game30.mk; Phase 2 item C0, test builds): the render resolution and the FSAA scaler
// at run time. Modes (bit n of RES_MODES makes mode n available; RES_MODE is the boot mode):
//   0  640x480 (today)
//   1  640x240 rendered, each line shown twice: about half the pixel fill
//   2  1280x240 rendered into the FSAA scaler (horizontal halving on write-out): about today's fill, horizontal
//      edge anti-aliasing, vertical softness (PS2-like)
//   3  1280x480 into the FSAA scaler (about twice today's fill; needs the 600-tile allocation: see below)
// The display mode (KOS vid_set_mode 640x480, interlaced on a TV, progressive on VGA) never changes; a 240-line
// picture is shown by reading each frame-buffer line twice:
//   TV (480i): both fields read the same 240 lines (FB_R_SIZE modulus 1, odd-field address = even-field address);
//   VGA (480p): FB_R_CTRL line double (bit 1), FB_R_SIZE 240 lines.
// VRAM: KOS allocates the TA object pointer blocks, tile matrices and both 640x480 frame buffers once at pvr_init,
// so the texture pool never moves. Per bank the region [opb, opb + opb_size x (1 + overflow)) is re-cut per mode:
// the mode's initial blocks (bytes per tile x tiles), then the rest as the overflow pool. A mode with more tiles
// than KOS allocated (mode 2: 320 > 300) keeps its tile matrix at the end of that region. Its extra region is paid
// for as TA_HEADROOM pays (one more overflow pool, the vertex buffer one pool smaller), so the texture pool is
// unchanged unless mode 3 is built (KOS then allocates 600 tiles: the pool shrinks by the extra blocks).
// Safe point: a mode change is requested from the pad (test builds) and applied at the start of a frame
// (re4dc_ui_begin) after the previous scene was presented, with no scene in the TA, no render running and none
// completed (KOS pvr_set_vbuf_doublebuf's precondition): the tile matrices, TA registers and SCALER_CFG are only
// written while the PVR is idle (issue 9 / issue 11: scaler or TA writes during a render hang the console). The
// display registers change in the vblank of the first flip to a frame rendered in the new mode.
#if defined(RE4DC_RES_MODES) && RE4DC_RES_MODES
#include <kos.h>
#include <dc/pvr.h>
#include <dc/pvr/pvr_regs.h>
#include <dc/video.h>
#include <dc/vblank.h>
#include <arch/irq.h>
extern "C" {
#include "pvr_internal.h"  // KOS internals (C linkage): pvr_state, pvr_sync_reg_buffer
}
#include "re4dc_screen.h"

extern "C" void re4dc_log(const char* fmt, ...);
extern "C" unsigned re4dc_vi_retrace_count(void);

#ifndef RE4DC_RES_MODE
#define RE4DC_RES_MODE 0
#endif
static_assert((RE4DC_RES_MODES & ~15) == 0 && (RE4DC_RES_MODES >> RE4DC_RES_MODE & 1), "RES_MODES 1..15, RES_MODE in it");

extern "C" {
int re4dc_screen_w = 640, re4dc_screen_h = 480;
float re4dc_screen_wf = 640.0f, re4dc_screen_hf = 480.0f, re4dc_ui_sx = 1.0f, re4dc_ui_sy = 1.0f;
}

namespace {
struct Mode {
    unsigned short w, lines;
    unsigned char fsaa;
    const char* name;
};
const Mode kModes[4] = {{640, 480, 0, "R0 640x480"},
                        {640, 240, 0, "R1 640x240 line double"},
                        {1280, 240, 1, "R2 640x240 FSAA"},
                        {1280, 480, 1, "R3 640x480 FSAA"}};
constexpr unsigned kTileMatrixHeader = 0x48;  // KOS PVR_TILE_MATRIX_HEADER_SIZE
unsigned tiles_of(unsigned m) { return (kModes[m].w / 32U) * ((kModes[m].lines + 31U) / 32U); }
unsigned max_tiles()
{
    unsigned t = 0;
    for (unsigned m = 0; m < 4; ++m)
        if ((RE4DC_RES_MODES >> m & 1) && tiles_of(m) > t) t = tiles_of(m);
    return t;
}
struct Bank {
    uint32_t opb, region_end, tm_kos;
};
Bank banks[2];
unsigned kos_tiles, tile_bytes, cur = ~0U, applied;
volatile unsigned want = RE4DC_RES_MODE;
bool vga, interlaced, inited;
uint32_t boot_fb_size, boot_fb_cfg1;
volatile int disp_pending = -1, disp_view;
volatile unsigned disp_lines = 480;
unsigned osd_until;
int vbl_handle = -1;

void set_display(unsigned lines)
{
    if (lines == 480) {
        PVR_SET(PVR_FB_SIZE, boot_fb_size);
        PVR_SET(PVR_FB_CFG_1, boot_fb_cfg1);
        if (interlaced) PVR_SET(PVR_FB_IL_ADDR, (PVR_GET(PVR_FB_ADDR) & (PVR_RAM_SIZE - 1)) + 640U * 2U);
    } else {
        PVR_SET(PVR_FB_SIZE, (boot_fb_size & 0x3ffU) | ((lines - 1U) << 10) | (1U << 20));
        if (vga)
            PVR_SET(PVR_FB_CFG_1, boot_fb_cfg1 | 2U);
        else if (interlaced)
            PVR_SET(PVR_FB_IL_ADDR, PVR_GET(PVR_FB_ADDR));
    }
    disp_lines = lines;
}
// After KOS's vblank handler (registered later, TAILQ order): it flipped (pvr_sync_view: FB_R_SOF1 and, on an
// interlaced mode, FB_R_SOF2 = SOF1 + one line) in this same vblank.
void vblank(uint32_t, void*)
{
    if (disp_pending >= 0 && pvr_state.view_target != disp_view) {
        set_display(kModes[disp_pending].lines);
        disp_pending = -1;
    }
    if (disp_lines != 480 && interlaced && !vga) PVR_SET(PVR_FB_IL_ADDR, PVR_GET(PVR_FB_ADDR));
}
// KOS pvr_init_tile_matrix: the zero header and the initial tile; the tiles follow (apply).
void write_matrix_head(uint32_t tm)
{
    uint32_t* vr = reinterpret_cast<uint32_t*>(PVR_RAM_BASE) + (tm - kTileMatrixHeader) / 4U;
    for (unsigned i = 0; i < kTileMatrixHeader / 4U; ++i) *vr++ = 0;
    vr[0] = 0x10000000U;
    for (unsigned i = 1; i < 6; ++i) vr[i] = 0x80000000U;
}
// The PVR is idle (caller): re-cut both banks for mode m.
void apply(unsigned m)
{
    const Mode& M = kModes[m];
    const unsigned tw = M.w / 32U, th = (M.lines + 31U) / 32U, T = tw * th;
    for (unsigned b = 0; b < 2; ++b) {
        volatile pvr_ta_buffers_t* buf = pvr_state.ta_buffers + b;
        const uint32_t* old = reinterpret_cast<const uint32_t*>(PVR_RAM_BASE) + buf->tile_matrix / 4U;
        const bool presort = (old[6] >> 29) & 1U;  // the bank's first tile (WORLD_AUTOSORT switches it per scene)
        const uint32_t tm_bytes = 4U * (6U + 6U * T);
        uint32_t tm = banks[b].tm_kos, end = banks[b].region_end;
        if (T > kos_tiles) {
            tm = (banks[b].region_end - tm_bytes) & ~127U;
            end = (tm - kTileMatrixHeader) & ~127U;
        }
        const uint32_t initial = tile_bytes * T;
        const int overflow = int((end - banks[b].opb) / initial) - 1;
        buf->opb_size = initial;
        buf->opb_overflow_count = overflow;
        uint32_t accum = 0;
        for (unsigned j = 0; j < PVR_OPB_COUNT; ++j) {
            buf->opb_addresses[j] = banks[b].opb + accum;
            accum += pvr_state.opb_size[j] * T;
        }
        buf->tile_matrix = tm;
        buf->tile_matrix_size = tm_bytes;
        write_matrix_head(tm);
        uint32_t* vr = reinterpret_cast<uint32_t*>(PVR_RAM_BASE) + tm / 4U + 6U;
        for (unsigned x = 0; x < tw; ++x)
            for (unsigned y = 0; y < th; ++y) {
                const unsigned tn = tw * y + x;
                vr[0] = (y << 8) | (x << 2) | (unsigned(presort) << 29);
                for (unsigned l = 0; l < PVR_OPB_COUNT; ++l)
                    vr[1 + l] = (pvr_state.lists_enabled & BIT(l)) ? buf->opb_addresses[l] + pvr_state.opb_size[l] * tn
                                                                    : 0x80000000U;
                vr += 6;
            }
        vr[-6] |= BIT(31);
        re4dc_log("res: bank %u tiles %u (%ux%u) opb %06x initial %u overflow %d (pool %u B) tile matrix %06x end %06x\n", b, T,
                  tw, th, unsigned(banks[b].opb), unsigned(initial), overflow, unsigned(initial) * unsigned(overflow),
                  unsigned(tm), unsigned(end));
    }
    pvr_state.tw = int(tw);
    pvr_state.th = int(th);
    pvr_state.tsize_const = ((th - 1U) << 16) | (tw - 1U);
    pvr_state.w = 640;
    pvr_state.h = int(th * 32U);
    pvr_state.fsaa = M.fsaa;
    pvr_state.pclip_bottom = M.lines - 1U;
    pvr_state.pclip_y = (pvr_state.pclip_bottom << 16) | pvr_state.pclip_top;
    const uint32_t scaler = (PVR_GET(PVR_SCALER_CFG) & ~PVR_SCALER_CFG_FSAA) | (M.fsaa ? PVR_SCALER_CFG_FSAA : 0U);
    PVR_SET(PVR_SCALER_CFG, scaler);
    pvr_sync_reg_buffer();  // the TA of the current target bank with the new tile count and blocks
    re4dc_screen_w = M.w;
    re4dc_screen_h = M.lines;
    re4dc_screen_wf = float(M.w);
    re4dc_screen_hf = float(M.lines);
    re4dc_ui_sx = float(M.w) / 640.0f;
    re4dc_ui_sy = float(M.lines) / 480.0f;
    const bool lines_change = cur == ~0U || kModes[cur].lines != M.lines;
    cur = m;
    ++applied;
    osd_until = re4dc_vi_retrace_count() + 180U;
    if (lines_change) {
        disp_view = pvr_state.view_target;
        disp_pending = int(m);
    }
    re4dc_log("res: mode %u %s applied (scaler %08x, %s%s)\n", m, M.name, unsigned(PVR_GET(PVR_SCALER_CFG)),
              vga ? "VGA" : interlaced ? "TV 480i" : "TV", lines_change ? ", display at the next flip" : "");
}
}  // namespace

// native_ui.cpp re4dc_ui_init, before pvr_init: the allocation for the largest available mode.
extern "C" unsigned re4dc_res_params(pvr_init_params_t* p)
{
    const unsigned mt = max_tiles();
    unsigned shrink = 0;
    if (mt > 320) {
        p->fsaa_enabled = 1;  // KOS allocates 1280x480 (600 tiles); the boot mode is applied after pvr_init
    } else if (mt > 300) {
        unsigned words = 0;
        for (unsigned l = 0; l < PVR_OPB_COUNT; ++l) words += unsigned(p->opb_sizes[l]);
        shrink = (words * 4U * 300U + 1023U) & ~1023U;  // one more overflow pool, paid by the vertex buffer
        p->opb_overflow_count += 1;
        p->vertex_buf_size -= int(shrink);
    }
    re4dc_log("res: RES_MODES %u boot %u: max tiles %u, %s, vertex buffer %d B per bank (-%u)\n", unsigned(RE4DC_RES_MODES),
              unsigned(RE4DC_RES_MODE), mt, mt > 320 ? "FSAA allocation (600 tiles)" : mt > 300 ? "+1 overflow pool" : "KOS allocation",
              p->vertex_buf_size, shrink);
    return unsigned(p->vertex_buf_size);
}

// native_ui.cpp re4dc_ui_init, after pvr_init (no scene yet).
extern "C" void re4dc_res_init()
{
    vga = vid_mode && vid_mode->cable_type == CT_VGA;
    interlaced = vid_mode && (vid_mode->flags & VID_INTERLACE);
    boot_fb_size = PVR_GET(PVR_FB_SIZE);
    boot_fb_cfg1 = PVR_GET(PVR_FB_CFG_1);
    kos_tiles = unsigned(pvr_state.tw * pvr_state.th);
    tile_bytes = 0;
    for (unsigned l = 0; l < PVR_OPB_COUNT; ++l) tile_bytes += pvr_state.opb_size[l];
    for (unsigned b = 0; b < 2; ++b) {
        volatile pvr_ta_buffers_t* buf = pvr_state.ta_buffers + b;
        banks[b].opb = buf->opb;
        banks[b].region_end = buf->opb + buf->opb_size * (1U + buf->opb_overflow_count);
        banks[b].tm_kos = buf->tile_matrix;
    }
    cur = pvr_state.fsaa ? 3U : 0U;
    re4dc_log("res: KOS tiles %u (%dx%d fsaa %d) bytes per tile %u region %06x..%06x / %06x..%06x frame %06x+%u texture pool %u %s\n",
              kos_tiles, pvr_state.tw, pvr_state.th, pvr_state.fsaa, tile_bytes, unsigned(banks[0].opb),
              unsigned(banks[0].region_end), unsigned(banks[1].opb), unsigned(banks[1].region_end),
              unsigned(pvr_state.frame_buffers[0].frame), unsigned(pvr_state.frame_buffers[0].frame_size),
              unsigned(pvr_mem_available()), vga ? "VGA" : interlaced ? "TV 480i" : "TV");
    const int o = irq_disable();
    const unsigned boot = RE4DC_RES_MODE;
    cur = ~0U;
    apply(boot);
    disp_pending = -1;
    set_display(kModes[boot].lines);
    irq_restore(o);
    vbl_handle = vblank_handler_add(vblank, nullptr);
    inited = true;
}

extern "C" void re4dc_res_cycle();
// Called once per frame (re4dc_ui_begin). RES_CYCLE_FRAMES=n (test arms only: fixture buttons never fire the pad
// chord): the next mode every n frames, for the scripted Flycast pass.
extern "C" int re4dc_res_pending()
{
#if defined(RE4DC_RES_CYCLE_FRAMES) && RE4DC_RES_CYCLE_FRAMES
    static unsigned frames;
    if (inited && ++frames % unsigned(RE4DC_RES_CYCLE_FRAMES) == 0) re4dc_res_cycle();
#endif
    return inited && want != cur;
}

// native_ui.cpp re4dc_ui_begin after present_fence(): applies a requested mode if the PVR is idle.
extern "C" void re4dc_res_apply_pending()
{
    const unsigned m = want;
    if (!inited || m == cur) return;
    const int o = irq_disable();
    if (pvr_state.ta_busy || pvr_state.render_busy || pvr_state.render_completed || pvr_present_pending() ||
        disp_pending >= 0) {
        irq_restore(o);
        return;  // not idle yet: next frame
    }
    apply(m);
    irq_restore(o);
}

// Test builds (pad.cpp chord): the next available mode, applied at the next safe point.
extern "C" void re4dc_res_cycle()
{
    unsigned m = cur == ~0U ? 0U : cur;
    for (unsigned i = 0; i < 4; ++i) {
        m = (m + 1U) & 3U;
        if (RE4DC_RES_MODES >> m & 1) break;
    }
    want = m;
    re4dc_log("res: mode %u %s requested\n", m, kModes[m].name);
}

extern "C" unsigned re4dc_res_mode() { return cur; }

// The on-screen label (native_static.cpp re4dc_look_osd_text): 3 s after each applied change.
extern "C" const char* re4dc_res_osd_text()
{
    if (!applied || cur == ~0U || int(osd_until - re4dc_vi_retrace_count()) <= 0) return nullptr;
    return kModes[cur].name;
}

// crash_screen.cpp show(): the 640x480 display layout back (both frame buffers are always 640x480).
extern "C" void re4dc_res_crash_display()
{
    if (!inited) return;
    disp_pending = -1;
    set_display(480);
}
#endif
