// game/filter09: pause / stop screen filter (D:/Bio4/Prog/filter09.cpp). While the game is stopped
// (Filter09SetbUse(1)) it keeps a half-size copy of the last frame in temp buffer 12 and blends it
// back every frame, optionally spreading it outwards (g_bSpred: the death / option screen ripple);
// FilterTrans skips every other filter while it is in use.
#include "filter.h"
#include "light.h"
#include "gx.h"
#include "main_sub.h"
#include "main_mem.h"
#include "os_vi.h"
#include "db_log.h"
#include "trans_ot.h"

// Screen fade-out filter: keeps a half-size copy of the last frame and blends it back,
// spreading it outwards (g_bSpred) while the game is stopped.

#define SCR_W ((u32) Screen.width)
#define SCR_H ((u32) Screen.height)

extern f32 ZNEAR;
extern f32 ZFAR;
int GetDrawTmpBufType();

extern "C" {
void GXSetScissor(u32 left, u32 top, u32 wd, u32 ht);
void Filter09Render();
void Filter09GetEFB(int div, int div2);
#if !(defined(RE4DC_DOOR_FREEZE) && RE4DC_DOOR_FREEZE)
static void Filter09GXDraw(f32 x, f32 y, f32 z, f32 u, f32 v, f32 alpha, f32 s, f32 ofs, int div);
#endif
void Filter09DrawBuffer();
void Filter09GetEFB_801D19E0();
void Filter09SetbUse(int use, int spred);
}

void* filter09_buff = 0;
static int g_bUse;
int g_bSpred;
int g_bGet;

// Boot: same as the room init.
void Filter09Init()
{
    Filter09RoomInit();
}

// Room init: off, no capture pending.
void Filter09RoomInit()
{
    filter09_buff = 0;
    g_bUse = 0;
    g_bGet = 0;
}

// Queues Filter09Render (called from the stop screen code, not FilterTrans).
// Never called (the original linker dropped the body; its 0.0f pool constant stayed).
static void Filter09Trans()
{
    if (Render_checkBlurPermission()) {
        AddOtDirect(0x12, (void*) 0xCDCDCDCD, Filter09Render, 7, 0x400, 0, 0.0f);
    }
}

// Copies the frame at 1/div x 1/div2 into the filter buffer.
void Filter09GetEFB(int div, int div2)
{
    GXRenderModeObj* rm = &Rmode;
    static u8 vfilter[7] __attribute__((aligned(32))) = { 32, 0, 0, 0, 0, 0, 32 };

    GXSetCopyFilter(0, rm->sample_pattern, 0, vfilter);
    GXSetTexCopySrc(0, 0, SCR_W / div, SCR_H / div);
    GXSetTexCopyDst((SCR_W >> 1) / div2, (SCR_H >> 1) / div2, 6, 1);
    GXCopyTex(filter09_buff, 0);
    GXSetCopyFilter(rm->aa, rm->sample_pattern, 1, rm->vfilter);
    GXPixModeSync();
    GXInvalidateTexAll();
}

// OT callback while in use: takes temp buffer 12 (error when someone else holds a temp buffer and no
// capture was requested) and draws the stored frame.
void Filter09Render()
{
    GXColor col = { 0, 0, 0, 0 };

    if (g_bUse == 0) {
        return;
    }
    if (g_bGet == 0 && GetDrawTmpBufType() != 0) {
        pLog->err(0, 0, "Filter09SetbUse() : someone use TmpBuffer!!");
        return;
    }
    filter09_buff = GetDrawTmpBufAddr(12);
#if !(defined(RE4DC_DOOR_FREEZE) && RE4DC_DOOR_FREEZE)  // DOOR_FREEZE: the picture is a PVR texture
    if (filter09_buff == 0) {
        pLog->warn(0, 0, "Filter09Trans() : not enough memory");
        return;
    }
    DCInvalidateRange(filter09_buff, 0x38000);
#endif
    GXSetFog(0, 0.0f, 0.0f, ZNEAR, ZFAR, col);
    GXSetScissor(0, 56, SCR_W, SCR_H - 111);
    Filter09DrawBuffer();
    SetScissorState();
    LightMgr.setFog();
}

#if !(defined(RE4DC_DOOR_FREEZE) && RE4DC_DOOR_FREEZE)
// Draws the buffer as a screen quad scaled by ofs around the centre.
static void Filter09GXDraw(f32 x, f32 y, f32 z, f32 u, f32 v, f32 alpha, f32 s, f32 ofs, int div)
{
    GXTexObj tex;

    GXInitTexObj(&tex, filter09_buff, (SCR_W >> 1) / div, (SCR_H >> 1) / div, 6, 0, 0, 0);
    GXInitTexObjLOD(&tex, 1, 1, 0.0f, 0.0f, 0.0f, 0, 0, 0);
    GXLoadTexObj(&tex, 0);
    GXBegin(0x80, 0, 4);
    GXPosition3f32(x - ofs, y - ofs, z);
    GXColor4u8(0xFF, 0xFF, 0xFF, (u8) alpha);
    GXTexCoord2f32(u + 0.0f, v + 0.0f);
    GXPosition3f32(x + (f32) SCR_W / s + ofs, y - ofs, z);
    GXColor4u8(0xFF, 0xFF, 0xFF, (u8) alpha);
    GXTexCoord2f32(u + 1.0f, v + 0.0f);
    GXPosition3f32(x + (f32) SCR_W / s + ofs, y + (f32) SCR_H / s + ofs, z);
    GXColor4u8(0xFF, 0xFF, 0xFF, (u8) alpha);
    GXTexCoord2f32(u + 1.0f, v + 1.0f);
    GXPosition3f32(x - ofs, y + (f32) SCR_H / s + ofs, z);
    GXColor4u8(0xFF, 0xFF, 0xFF, (u8) alpha);
    GXTexCoord2f32(u + 0.0f, v + 1.0f);
}
#endif

// Captures the frame when requested, draws it back, and with g_bSpred adds the expanding
// fade_alpha/fade_scale copy and recaptures (feedback ripple).
#if defined(RE4DC_DOOR_FREEZE) && RE4DC_DOOR_FREEZE
// DOOR_FREEZE=1 (Makefile, default 0; render only): the Dreamcast version of the frame below. The capture copies the
// displayed picture into a 320x240 PVR texture (re4dc_ui_door_capture). GameCube frame n (n = 1 the capture frame)
// shows B(n) = (1 - a) B(n-1) + a S(B(n-1)), a = 64/255, S = the copy enlarged by fade_scale px per side, and
// recaptures it: B(n) = sum_j C(n, j) (1 - a)^(n-j) a^j S^j(B0). native_ui.cpp draws those terms as layered quads
// (scale S^j, exact blend weights) inside the scissor band; the source fades (FadeControl runs after Render() in the
// same frame) are drawn over it at present time, in the same order.
extern "C" int re4dc_ui_door_capture(void);
extern "C" void re4dc_ui_door_queue(unsigned steps);
static unsigned door_steps;
void Filter09DrawBuffer()
{
    if (g_bGet == 1) {
        g_bGet = 0;
        re4dc_ui_door_capture();
        door_steps = 0;
    }
    if (g_bSpred == 1) {
        ++door_steps;
    }
    re4dc_ui_door_queue(door_steps);
}
// native_ui.cpp: the filter's picture stays allocated while in use.
extern "C" int re4dc_door_in_use(void)
{
    return g_bUse;
}
#include "fade.h"
// native_ui.cpp at present: the active source fades (normal group, then late group), as FadeControl draws them.
extern "C" unsigned re4dc_door_fades(unsigned* argb, unsigned max)
{
    unsigned n = 0;
    for (int late = 0; late < 2; ++late) {
        for (int i = 0; i < 4 && n < max; ++i) {
            const FadeWork* f = &Fade[i];
            if (((f->flags & 4) != 0) != (late != 0) || !(f->flags & 3)) {
                continue;
            }
            argb[n++] = ((u32) f->cur.a << 24) | ((u32) f->cur.r << 16) | ((u32) f->cur.g << 8) | f->cur.b;
        }
    }
    return n;
}
#else
void Filter09DrawBuffer()
{
    Mtx44 proj;
    Mtx mv;
    GXColor amb = { 0, 0, 0, 0 };
    f32 y = 0.0f;
    f32 z;
    int a;
    static f32 fade_alpha = 64.0f;
    static f32 fade_scale = 20.0f;

    GXSetAlphaCompare(7, 0, 1, 7, 0);
    GXSetColorUpdate(1);
    GXSetAlphaUpdate(0);
    GXSetCullMode(0);
    C_MTXOrtho(proj, 0.0f, (f32) SCR_H, 0.0f, (f32) SCR_W, 0.0f, -65536.0f);
    GXSetProjection(proj, 1);
    PSMTXIdentity(mv);
    GXLoadPosMtxImm(mv, 0);
    GXSetCurrentMtx(0);
    GXSetBlendMode(1, 4, 5, 0);
    GXSetNumTevStages(1);
    GXSetNumChans(0);
    GXSetNumTexGens(1);
    GXSetTexCoordGen(0, 1, 4, 0x3C);
    GXSetChanCtrl(0, 0, 1, 1, 0, 2, 1);
    GXSetChanCtrl(2, 0, 1, 1, 0, 2, 1);
    GXSetChanAmbColor(4, amb);
    GXSetNumChans(1);
    GXSetTevOrder(0, 0, 0, 4);
    GXSetTevColorIn(0, 15, 15, 15, 8);
    GXSetTevColorOp(0, 0, 0, 0, 1, 0);
    GXSetTevAlphaIn(0, 7, 7, 7, 5);
    GXSetTevAlphaOp(0, 0, 0, 0, 1, 0);
    GXClearVtxDesc();
    GXSetVtxDesc(9, 1);
    GXSetVtxDesc(11, 1);
    GXSetVtxDesc(13, 1);
    GXSetVtxAttrFmt(0, 9, 1, 4, 0);
    GXSetVtxAttrFmt(0, 11, 1, 5, 0);
    GXSetVtxAttrFmt(0, 13, 1, 4, 0);
    y = 0.0f;
    GXSetZMode(0, 6, 0);
    z = 65530.0f;
    if (g_bGet == 1) {
        g_bGet = 0;
        Filter09GetEFB(1, 1);
    }
    a = 0xFF;
    Filter09GXDraw(y, y, z, y, y, (f32) (u8) a, 1.0f, 1.0f, 1);
    if (g_bSpred == 1) {
        Filter09GXDraw(y, y, z, y, y, fade_alpha, 1.0f, fade_scale, 1);
        Filter09GetEFB(1, 1);
    }
    GXSetZMode(1, 3, 1);
    GXSetAlphaUpdate(1);
}
#endif

// Requests a fresh capture of the frame on the next render.
void Filter09GetEFB_801D19E0()
{
    g_bGet = 1;
}

// Turns the stop filter on/off and selects the spreading variant.
void Filter09SetbUse(int use, int spred)
{
    g_bUse = use;
    g_bSpred = spred;
}

// 1 while the stop filter is in use (FilterTrans then skips the other filters).
int Filter09GetbUse()
{
    return g_bUse;
}

asm(".section .sdata,\"aw\"\n\t.balign 32\n\t.text");
asm(".section .sbss,\"aw\",@nobits\n\t.balign 8\n\t.text");
