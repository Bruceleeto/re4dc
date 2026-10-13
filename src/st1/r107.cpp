#include "types.h"
#include "main_mem.h"
#include "st_room.h"
#include "atari.h"
#include "light.h"
#include "flag_rsf.h"
#include "global.h"
#include "sce.h"
#include "sce_sys.h"
#include "scroll.h"
#include "obj.h"
#include "em.h"
#include "em27.h"
#include "emdoor.h"
#include "etc_model.h"
#include "esp.h"
#include "snd.h"
#include "em_wrap.h"

// Room 1-07 (D:/Bio4/Prog/r107.cpp): the lake house; the kiln item events (shared with r104), the
// fish water height and the battle BGM.

struct R107Work {
    u8 pad[1];
};

static R107Work* r107_work;

// Hit effects of attribute type 2 (water)
static const AtEffInfo r107_eff_info = {
    1, {1, 0x2C}, {1, 0x2F}, {1, 0x2E}, {1, 0x2D}, {1, 0x20}, {1, 0x20}, {1, 0x2B}, {1, 0x2F},
};

static void r107_setFish();
void r104_openKiln_main(int type, int opened);
static void r104_openedKiln(int type);
static void r104_openKiln(int type);
static void r107_checkBgmPlay();
#if defined(RE4DC_PS2_ENEMY_RULES) && RE4DC_PS2_ENEMY_RULES
#include "area.h"
#include "em_set.h"
#include "read.h"
#include "player.h"
#include "dbg_tool.h"
static void r107_ps2Areas();
#endif

// Room init: pairs door 0 with door 0x15 (double door), starts the battle-BGM task, sets Room_flg bit 0
// on first visit, registers the two kiln item events (item 0x92 at area 3 -> kiln 0, 0x93 at area 5 ->
// kiln 1, reusing r104's opener), the water hit effects and the fish height task.
void R107Init()
{
    cEm* door0;
    cEm* door1;

#line 50 "D:/Bio4/Prog/r107.cpp"
    r107_work = (R107Work*) MEM_CALLOC(1, 1, 0xd);

    if (getRoomEtcDoor(0, &door0, 1) && getRoomEtcDoor(0x15, &door1, 1)) {
        ((cEmDoor*) door0)->setDoor((cEmDoor*) door1);
    }
    SceExec(0x12, (TaskFunc) r107_checkBgmPlay, 0, 0, SCE_PRIO_DEF_2, 0);
    if (RsfCheck(G_ROOM_ID, 0) == 0) {
        RsfSet(G_ROOM_ID, 0);
    }
    SceSetItemEvent(3, 0x92, 1, 0xB, r104_openKiln, (void (*)()) r104_openedKiln, 0, 0);
    SceSetItemEvent(5, 0x93, 2, 0xC, r104_openKiln, (void (*)()) r104_openedKiln, 1, 0);
    EatMgr.registEffInfo(EAT_ET_WATER, (AtEffInfo*) &r107_eff_info);
    SceExec(0x12, (TaskFunc) r107_setFish, 0, 0, SCE_PRIO_DEF_2, 0);
#if defined(RE4DC_PS2_ENEMY_RULES) && RE4DC_PS2_ENEMY_RULES
    // PS2 R107Init: the deferred Ganado (em12) and fish (em27) modules are read up front.
    EmReadSearch(GetEmIdFromList(0xEF), 0, 0);
    EmReadSearch(GetEmIdFromList(0xA5), 0, 0);
    SceExec(0x12, (TaskFunc) r107_ps2Areas, 0, 0, SCE_PRIO_DEF_2, 0);
#endif
}

#if defined(RE4DC_PS2_ENEMY_RULES) && RE4DC_PS2_ENEMY_RULES
// PS2 enemy rules (PS2 USA st1_1.rel R107Init / the three area tasks after R107Main): list entries 0xED..0xEF
// (three Ganados) and 0xA5..0xA9 (five fish) start dead (stage.cpp list patch) and are sent once when the
// player first enters PS2-only areas 6 / 7 / 8 (AEV type 2, trigger inside + once, player; room save flags
// 3 / 4 / 5). The GameCube AEV ends at area 5, so the PS2 quadrilaterals (PS2 r107.dat) are tested here.
static AreaData r107Ps2Area[3] = {
    {1, AREA_TYPE_XZ4, 0, {{-2503.0f, 3501.0f, 750.0f, {{66111.0f, -61476.0f}, {67611.0f, -61476.0f}, {67511.0f, -57766.0f}, {66012.0f, -57783.0f}}}}},
    {1, AREA_TYPE_XZ4, 0, {{188.0f, 1000.0f, 750.0f, {{71033.0f, -46982.0f}, {74663.0f, -46776.0f}, {74773.0f, -41505.0f}, {71237.0f, -41517.0f}}}}},
    {1, AREA_TYPE_XZ4, 0, {{188.0f, 1000.0f, 750.0f, {{67080.0f, -57594.0f}, {71088.0f, -57623.0f}, {70823.0f, -52857.0f}, {67598.0f, -52778.0f}}}}},
};

static void r107_ps2Areas()
{
    for (;;) {
        int i;
        int left = 0;

        for (i = 0; i < 3; i++) {
            if (RsfCheck(G_ROOM_ID, 3 + i)) {
                continue;
            }
            left++;
            if (AreaHitCheck(&r107Ps2Area[i], &pPL->pos) == 0) {
                continue;
            }
            RsfSet(G_ROOM_ID, 3 + i);
            OSReport("ps2en: r107 area %d sends its enemies (frame %u)\n", 6 + i, (unsigned) pG->Frame_cnt);
            if (i == 0) {
                setEm(0xEF, -1, 1, 1, 1);
            } else if (i == 1) {
                setEm(0xED, -1, 1, 1, 1);
            } else {
                u32 n;

                setEm(0xEE, -1, 1, 1, 1);
                for (n = 0xA5; n <= 0xA9; n++) {
                    setEm(n, -1, 1, 1, 1);
                }
                // r107_setFish ran at room entry: give the new fish the lake's water level.
                r107_setFish();
            }
        }
        if (left == 0) {
            break;
        }
        SceSleep(1);
    }
}
#endif

// Per frame: switch the player's footstep/OT type to the water variant.
void R107Main()
{
    setPlWaterOtType();
}

// Put every fish enemy at the lake's water level.
static void r107_setFish()
{
    u32 i;

    SceSleep(1);
    for (i = 0; i < EmMgr.nArray; i++) {
#if !defined(__PPC__)
        cEm* em = (cEm*) EmMgr.workAt(i);
        if (!em) continue;
#else
        cEm* em = (cEm*) ((u8*) EmMgr.pArray + EmMgr.size * i);
#endif

        if (em->id == 0x27 && (em->be_flag & 0x201) == 1) {
            ((cEm27*) em)->setWaterHeight(-13700.0f);
        }
    }
}

// Open (opened != 0: already open) kiln `type`: the two door objects turn 1.9 rad over 30 frames.
void r104_openKiln_main(int type, int opened)
{
    f32 step = 0.0f;
    cObj* a = 0;
    cObj* b = 0;

    switch (type) {
    case 0:
        a = SmdGetObjPtr(0x3F);
        b = SmdGetObjPtr(0x40);
        step = -1.9f;
        break;
    case 1:
        a = SmdGetObjPtr(0x41);
        b = SmdGetObjPtr(0x42);
        step = 1.9f;
        break;
    default:
        SceExit();
        break;
    }
    if (a != 0 && b != 0) {
        a->be_flag |= 0x20;
        b->be_flag |= 0x20;
        if (opened == 1) {
            a->pParts->ang.y -= step;
            b->pParts->ang.y += step;
        } else {
            int i;

            step /= 30.0f;
            SndCall(6, 0x1C, 0, 0, 0, 0);
            for (i = 30; i != 0; i--) {
                a->pParts->ang.y -= step;
                b->pParts->ang.y += step;
                SceSleep(1);
            }
        }
    }
}

// Item-event "already opened" callback: put kiln `type`'s doors in the open pose without animating.
static void r104_openedKiln(int type)
{
    r104_openKiln_main(type, 1);
}

// Item-event opener callback: animate kiln `type` open (30-frame swing) when the item is taken.
static void r104_openKiln(int type)
{
    r104_openKiln_main(type, 0);
}

// Battle BGM while the enemies of list entries 0x10..0x20 live.
static void r107_checkBgmPlay()
{
    while (SceCkFindPL(0) != 1) {
        SceSleep(1);
    }
    SndRoomStrStart(1, 3, 1);
    while (SceCountEmAlive(0x10, 0x20) != 0) {
        SceSleep(1);
    }
    SndRoomStrStop(3);
}
