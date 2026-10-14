#include "types.h"
#include "main_mem.h"
#include "st_room.h"
#include "atari.h"
#include "event.h"
#include "light.h"
#include "flag_rsf.h"
#include "global.h"
#include "sce.h"
#include "sce_sys.h"
#include "em.h"
#include "emwindow.h"
#include "etc_model.h"
#include "esp.h"
#include "player.h"
#include "flr_at.h"
#include "rnd.h"

#if defined(RE4DC_GAME) && !defined(__PPC__) && RE4DC_ROUTE_CH22 && \
    defined(RE4DC_PS2_ENEMY_RULES) && RE4DC_PS2_ENEMY_RULES
#define CH22_PS2_ROOM 1
#include "libgpu.h"
#include "sce_at.h"
#include "em_set.h"
#include "global.h"
#include "sce.h"
#include "sce_sys.h"
extern "C" void OSPanic(const char* file, int line, const char* msg, ...);
#else
#define CH22_PS2_ROOM 0
#endif

#if CH22_PS2_ROOM
#include "cam_ctrl.h"
#include "scroll.h"
#endif

// Room 1-11 (D:/Bio4/Prog/r111.cpp): the village house exterior in the storm; the rack ranges, the
// rain effects and the thunder task.

struct R111Work {
    u8 pad[0x1C];
};

static R111Work* r111_work;

static void r111_ThunderMove();

#if CH22_PS2_ROOM
// PS2 USA st1_3.rel 0x8a98..0x8c58: two independent area gates, a
// two-frame entry delay, and one-shot room-save bits for held A1/A6/A7.
static void r111_ps2EmSet()
{
    SceSleep(2);
    for (;;) {
        if (RsfCheck(G_ROOM_ID, 3) == 0 &&
            (pG->Room_flg[2] & 0x40000000) && SceCountEmAlive(0x10, 0x20) < 5) {
            RsfSet(G_ROOM_ID, 3);
            EmSetFromList2(0xA7, 1);
        }
        if (RsfCheck(G_ROOM_ID, 2) == 0 &&
            (pG->Room_flg[2] & 0x80000000) && SceCountEmAlive(0x10, 0x20) < 5) {
            if (RsfCheck(G_ROOM_ID, 0) == 0) {
                RsfSet(G_ROOM_ID, 0);
                EmSetFromList2(0xA1, 1);
            } else if (RsfCheck(G_ROOM_ID, 1) == 0) {
                RsfSet(G_ROOM_ID, 1);
                RsfSet(G_ROOM_ID, 2);
                EmSetFromList2(0xA6, 1);
            }
        }
        SceSleep(1);
    }
}

// PS2 AEV7/15, absent from GC: flag64 after native6 and flag65 after14.
static AreaData r111Ps2Areas[2] = {
    {1, AREA_TYPE_XZ4, 0, {{-5622.45508f, 19434.1523f, 750.0f, {{-1728.04785f, -28364.9316f}, {52805.8047f, -37177.4883f}, {39884.8281f, 27951.7949f}, {2243.34985f, 30472.1309f}}}}},
    {1, AREA_TYPE_XZ4, 0, {{-10247.3975f, 22469.6914f, 750.0f, {{-2735.62402f, -41376.7305f}, {52955.2852f, -35198.9375f}, {30357.7012f, 2179.44238f}, {-1243.21509f, -4900.1665f}}}}},
};

// Allocate with native ownership/cleanup and a free number, then insert at the
// source AEV position. Item areas can already occupy the PS2 logical number.
static SceAtWork* r111_ps2FlagArea(SceAtWork* prev, AreaData* area, int flagNo)
{
    if (prev == 0 || prev->otNo != 2) {
        OSPanic(__FILE__, __LINE__, "ch22 r111: unexpected AEV boundary");
        return 0;
    }
    Vec corners[4];
    for (int i = 0; i < 4; i++) {
        corners[i].x = area->u.xz4.p[i].x;
        corners[i].y = area->u.xz4.floor;
        corners[i].z = area->u.xz4.p[i].z;
    }
    int no = SceAtCreateExecAt(pPL, corners, 0, 1, 1, area->u.xz4.height,
                             2, 0.0f, 0.0f, 0, 0, 0, 0, 0);
    SceAtWork* at = no >= 0 ? SceAtPtr(no) : 0;
    if (at == 0) {
        OSPanic(__FILE__, __LINE__, "ch22 r111: PS2 AEV allocation failed");
        return 0;
    }
    DelPrim((u32*) sceAtSetOtStart(), (u32*) at);
    at->area = *area;
    at->type = 4;
    at->pParent = 0;
    at->parentParts = 0;
    at->angleRange = 45;
    at->flg.kind = 0;
    at->flg.off = 0;
    at->flg.no = flagNo;
    AddPrim((u32*) prev, (u32*) at);
    return at;
}

static void r111_ps2Init()
{
    static const int before[2] = {6, 14};
    for (int i = 0; i < 2; i++) {
        SceAtWork* prev = SceAtPtr(before[i]);
        if (prev == 0 || prev->type != 5 || prev->otNo != 2) {
            OSPanic(__FILE__, __LINE__, "ch22 r111: expected source message AEV boundary");
            return;
        }
        if (r111_ps2FlagArea(prev, &r111Ps2Areas[i], 64 + i) == 0) return;
    }
    SceExec(0x12, (TaskFunc) r111_ps2EmSet, 0, 0, SCE_PRIO_DEF_2, 0);
}
#endif

// Room init: sets the three rack (cEmRack, etc_model) trigger ranges (moving rack 0x11 to a fixed
// position), starts the thunder task, attaches the rain effects to the player (EstSet 1/3/0x23),
// sets Status_flg[1] 0x400 (raining), pre-breaks windows 0 and 0x13, and default floor attribute 3.
void R111Init()
{
    cEm* rack;
    cEm* win;

#line 47 "D:/Bio4/Prog/r111.cpp"
    r111_work = (R111Work*) MEM_CALLOC(sizeof(R111Work), 1, 0xd);

    if (getRoomEtcRack(0xD, &rack, 1)) {
        ((cEmRack*) rack)->setRange(0.0f, 1000.0f, 0.0f, 2000.0f);
    }
    if (getRoomEtcRack(0xF, &rack, 1)) {
        ((cEmRack*) rack)->setRange(2000.0f, 2000.0f, 0.0f, 2600.0f);
    }
    if (getRoomEtcRack(0x11, &rack, 1)) {
        FSet(rack->pos.x, 6656.0f);
        FSet(rack->pos.y, 902.0f);
        FSet(rack->pos.z, 8925.0f);
        ((cEmRack*) rack)->setRange(2000.0f, 800.0f, 0.0f, 4400.0f);
    }
    SceExec(0x12, (TaskFunc) r111_ThunderMove, 0, 0, SCE_PRIO_DEF_2, 0);
    {
        void* zero = 0;

        EstSet((int) pPL, -1, 0, 0, 1, 0, 0x800, 0, (u32) zero, zero);
        EstSet((int) pPL, -1, 0, 0, 3, 1, 0x800, 0, (u32) zero, zero);
        EstSet((int) pPL, -1, 0, 0, 0, 0x23, 0x800, 0, (u32) zero, zero);
    }
    pG->Status_flg[1] |= 0x400;
    if (getRoomEtcWindow(0, &win, 1)) {
        ((cEmWindow*) win)->SetBreakModel();
    }
    if (getRoomEtcWindow(0x13, &win, 1)) {
        ((cEmWindow*) win)->SetBreakModel();
    }
    FlrAtSetDefVal(0, 0, 3);
#if CH22_PS2_ROOM
    r111_ps2Init();
#endif
}

// PS2 room main also switches the house model at camera cuts 13/14.
void R111Main()
{
#if CH22_PS2_ROOM
    // PS2 R111Main 0x8a10: update only on the inside/outside transition.
    int camera = CamCtrl.CurrentCameraNo();
    if (camera == 13 || camera == 14) {
        if (!(pG->Room_flg[0] & 0x80000000)) {
            pG->Room_flg[0] |= 0x80000000;
            SmdSetTrans(0x1E, 0);
        }
    } else if (pG->Room_flg[0] & 0x80000000) {
        pG->Room_flg[0] &= ~0x80000000u;
        SmdSetTrans(0x1E, 1);
    }
#endif
}

// Thunder every 90..235 frames: the flash (indoors: the window flash), the lit rain areas, the sound.
static void r111_ThunderMove()
{
    int cnt;
    void* zero = 0;

    SceSleep(1);
    {
        u8 r = Rnd() % 30;
        cnt = r * 5 + 90;
    }
    for (;;) {
        if (cnt == 0) {
            if (!(pG->Status_flg[1] & 0x02000000)) {
                EstSet(0, -1, 0, 0, 1, 2, 1, 0, 0, 0);
            } else {
                EstSet(0, -1, 0, 0, 1, 0x10, 1, 0, 0, 0);
            }
            if (EffGetAreaState(0)) {
                EstSet(0, -1, 0, 0, 1, 4, 0, 0, (u32) zero, zero);
            }
            if (EffGetAreaState(1)) {
                EstSet(0, -1, 0, 0, 1, 6, 0, 0, (u32) zero, zero);
            }
            if (EffGetAreaState(2)) {
                EstSet(0, -1, 0, 0, 1, 8, 0, 0, (u32) zero, zero);
            }
            if (EffGetAreaState(3)) {
                EstSet(0, -1, 0, 0, 1, 0xA, 0, 0, (u32) zero, zero);
            }
            if (EffGetAreaState(4)) {
                EstSet(0, -1, 0, 0, 1, 0xC, 0, 0, (u32) zero, zero);
            }
            if (EffGetAreaState(5)) {
                EstSet(0, -1, 0, 0, 1, 0xE, 0, 0, (u32) zero, zero);
            }
            {
                u8 r = Rnd() % 30;
                cnt = r * 5 + 90;
            }
            SceSndCallThunder();
        }
        cnt--;
        SceSleep(1);
    }
}
