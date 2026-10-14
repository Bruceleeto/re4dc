#include "types.h"
#include "main_mem.h"
#include "st_room.h"
#include "atari.h"
#include "light.h"
#include "event.h"
#include "map_obj.h"
#include "widget.h"
#include "flag_rsf.h"
#include "global.h"
#include "datactrl.h"
#include "sce.h"
#include "sce_sys.h"
#include "sce_at.h"
#include "scroll.h"
#include "obj.h"
#include "em.h"
#include "emdoor.h"
#include "em_set.h"
#include "em_wrap.h"
#include "etc_model.h"
#include "player.h"
#include "cam_ctrl.h"
#include "act_btn.h"
#include "item.h"
#include "mes.h"
#include "sscrn.h"
#include "fade.h"
#include "snd.h"
#include "rnd.h"

#if defined(RE4DC_PS2_ENEMY_ROOMS) && (RE4DC_PS2_ENEMY_ROOMS & 0x04)
// PS2_ENEMY_ROOMS r104: the PS2 USA room code (st1_1.rel R104Init 0x8890 .. 0xab70) replaces the enemy parts.
#define R104_PS2 1
#include "area.h"
#include "dbg_tool.h"
#else
#define R104_PS2 0
#endif

// Room 1-04 (D:/Bio4/Prog/r104.cpp): the farm; the double door, the enemy reset waves per area,
// the patrolling Ganados, the shelves / boxes to open and the four events (s00 arrival, s10, s20).

// One reset wave: three enemies with their flag numbers (the reset table entries).
struct R104ResetData {
    int em[3];        // 0x00  list entries
    int flagA;        // 0x0C  save flag: wave 1 done
    int flagB;        // 0x10  wave 2 done
    int flagC;        // 0x14  wave 3 done
    int flagD;        // 0x18  pG->flags_174 bit: the wave was set once
};

struct EmReset : R104ResetData {
    cEmWrap em[3];    // 0x1C
};

// One patrol: the enemy and its second way point.
struct R104PatrolData {
    int no;           // 0x00
    Vec pos;          // 0x04
};

class cPatrol104 {
public:
    int active;       // 0x00
    cEmWrap em;       // 0x04
    u32 nPoint;       // 0x10
    u32 cur;          // 0x14
    Vec pos[2];       // 0x18
};

#if R104_PS2
// A PS2 reset wave (EmReset::init / ::set, st1_1 0x9978 / 0x9b58): the GameCube table plus flagE, the save flag
// that retires the wave once it was sent twice (cnt).
struct R104Ps2ResetData {
    int em[3];
    int flagA;
    int flagB;
    int flagC;
    int flagD;        // event flag: the first send done
    int flagE;        // room save flag: the wave is retired
};

struct R104Ps2Reset {
    const R104Ps2ResetData* d;
    int cnt;          // sends this visit (PS2 work +0x20)
    cEmWrap em[3];
};
#endif

struct R104Work {
    int pad_0;
    u32 emNum;        // 0x04  enemies to kill before the next wave
    u32 resetCnt;     // 0x08  waves done
    EmReset reset[4]; // 0x0C
    u32 strId;        // 0x10C
    cEmDoor* door0;   // 0x110
    cEmDoor* door1;   // 0x114
#if R104_PS2
    R104Ps2Reset ps2Reset[4];
    cEmWrap ps2Merchant;   // the s20 enemy 0x5E (PS2 work +0x148)
#endif
};

static R104Work* r104_work;

// The original's .rodata and .data are 8-aligned (the .rodata end is padded to 0x2a8; r105 has the same).
// Both tables are global in the REL (ADDR16 fields hold A only).
asm(".section .rodata; .balign 8; .section .data; .balign 8");
R104ResetData r104_resetData[4] = {
    {{0xD9, 0xDA, 0xDB}, 2, 3, 4, 1},
    {{0xDC, 0xDD, 0xDE}, 5, 6, 7, 2},
    {{0xDF, 0xE0, 0xE1}, 8, 9, 0xA, 3},
    {{0xE2, 0xE3, 0xE4}, 0xB, 0xC, 0xD, 4},
};

R104PatrolData r104_patrolData[7] = {
    {0xF0, {16350.0f, 70.0f, -4050.0f}},
    {0xF1, {31430.0f, 6740.0f, -16170.0f}},
    {0xF3, {28880.0f, 7900.0f, -29940.0f}},
    {0xF4, {4690.0f, -1950.0f, -4430.0f}},
    {0xF5, {5860.0f, -2120.0f, -12750.0f}},
    {0xF6, {11080.0f, -90.0f, -18990.0f}},
    {0xF7, {24710.0f, 3570.0f, -27760.0f}},
};

// COMPILER-DIFF #4: the original passes the int table entry to the s16 parameter without
// truncation (`lwz` straight into r4); an int-parameter view of the callee (r11d).
int cEmWrapSetPtrI(cEmWrap* w, int no, int list, int errOn) asm("setPtr__7cEmWrapsSci");
int cEmWrapSetEmI(cEmWrap* w, int no, int list, int errOn, int chkDead, int setAlive) asm("setEm__7cEmWrapsSciii");

// Event flag words at pG+0x174 addressed as an integer base plus the word offset (r108).
static inline u32 evtFlagBase()
{
    return (u32) &pG->Room_flg[0];
}
// Test event flag `no` in the pG->flags_174 words (bit 31 - (no & 31) of word no >> 5).
static inline u32 EvtFlagChk(u32 base, u32 no)
{
    return *(u32*) (((no >> 5) << 2) + base) & (0x80000000 >> (no & 31));
}
// Set event flag `no` (the reset waves remember they were spawned once).
static inline void EvtFlagOn(u32 base, u32 no)
{
    *(u32*) (((no >> 5) << 2) + base) |= 0x80000000 >> (no & 31);
}

// The rooms call Event::FlgOnStatus out of line (event.h has it in-class).
void EvtFlgOnStatus(Event* e, u32 no) asm("FlgOnStatus__5EventUl");

// The running event's key (&EvtMgr.x34 as an accessor result: the address is formed last).
static inline u32* evtKey(EventMgr* m) { return &m->NowExeEvtKey; }

static void r104_checkBgmPlay();
static void r104_execEmDash();
extern "C" void r104_openBox_main(int no, int opened);
#if defined(RE4DC_GAME) && !defined(__PPC__)
static void r104_openedBox(int no);
#else
static void r104_openedBox();
#endif
static void r104_openBox(int no);
extern "C" void r104_openShelf_main(int no, int opened);
#if defined(RE4DC_GAME) && !defined(__PPC__)
static void r104_openedShelf(int no);
#else
static void r104_openedShelf();
#endif
static void r104_openShelf(int no);
extern "C" void cPatrol104_getNextTarget(cPatrol104* p, Vec* out);
extern "C" void cPatrol104_init(cPatrol104* p, R104PatrolData* d);
extern "C" void cPatrol104_move(cPatrol104* p);
static void r104_initEmPatrol();
static void r104_execShowView_end();
static void r104_execShowView();
static void r104_checkDoor107KeyUse();
static void r104_checkDoor107();
extern "C" void EmReset_init(EmReset* r, R104ResetData* d);
extern "C" int EmReset_set(EmReset* r);
extern "C" int r104_checkNowArea();
extern "C" void r104_execEmReset(int area);
static void r104_checkEmReset();
static void r104_execEvent20();
static void r104_execEvent10();
static void r104_execEvent00();
static void r104_succeedAction();
static void Evt_R104S00_Func(Event* e);
static void Evt_R104S01_Func(Event* e);
#if defined(RE4DC_GAME) && !defined(__PPC__) && RE4DC_ROUTE_MOVIES
// Route cutscenes (route lane 2026-10-01): r104's events are presented by their PS2 movies; the
// surrounding source code (flags, doors, enemies, the shop) runs unchanged (docs/ROUTE_CUTSCENES.md).
// s00 (chapter 1-2's arrival) ends on a QTE at its cancel cut 0x1E (ActBtn A+B or L+R): PS2 evd camera
// cuts put it at picture 4795, 60 frames (r104s00c is that cut alone, played after a skip). Its result
// picks s01 (passed) or s02 (the death demo). No evd is read when the movies own the events, so the ARAM
// pre-reads are skipped too.
#include "route_movie.h"
#include "game.h"
#define R104_ROUTE_MOVIES 1
static u8 r104MoviesOwn = 0xFF;
static int r104MoviesOwnCheck()
{
    if (r104MoviesOwn == 0xFF) {
        r104MoviesOwn = re4dc_movie_available(0x10400) && re4dc_movie_available(0x10401) &&
                        re4dc_movie_available(0x10402) && re4dc_movie_available(0x10410) &&
                        re4dc_movie_available(0x10420);
        OSReport("route movie r104: %s\n", r104MoviesOwn ? "movies own s00/s01/s02/s10/s20" : "no media, source events");
    }
    return r104MoviesOwn;
}
#define R104_MOVIES_OWN() r104MoviesOwnCheck()
#else
#define R104_ROUTE_MOVIES 0
#define R104_MOVIES_OWN() 0
#endif

#if R104_PS2
static const R104Ps2ResetData r104_ps2ResetData[4] = {
    {{0xD9, 0xDA, 0xDB}, 2, 3, 4, 1, 24},
    {{0xDC, 0xDD, 0xDE}, 5, 6, 7, 2, 25},
    {{0xDF, 0xE0, 0xE1}, 8, 9, 0xA, 3, 26},
    {{0xE2, 0xE3, 0xE4}, 0xB, 0xC, 0xD, 4, 27},
};

// PS2 em_patrol_data (st1_1 0x173b0): six patrols (no 0xF5); mode 1 = destroyed and 2 = joins the fight
// (setFindPL) once the dash-in has run (room save flag 15).
struct R104Ps2PatrolData {
    int no;
    Vec pos;
    int mode;
};
static const R104Ps2PatrolData r104_ps2PatrolData[6] = {
    {0xF0, {16350.0f, 70.0f, -4050.0f}, 0},
    {0xF1, {31430.0f, 6740.0f, -16170.0f}, 2},
    {0xF3, {28880.0f, 7900.0f, -29940.0f}, 1},
    {0xF4, {4690.0f, -1950.0f, -4430.0f}, 0},
    {0xF6, {11080.0f, -90.0f, -18990.0f}, 1},
    {0xF7, {24710.0f, 3570.0f, -27760.0f}, 2},
};

struct R104Ps2Patrol {
    cPatrol104 p;
    int mode;
};

// PS2 r104.dat AEV areas the GameCube AEV does not carry with these meanings; tested directly (as r101's area
// 0x21). 0x15 / 0x16 / 0x17: type 0, player; 0x18: type 4 flag 64 (Room_flg[2] bit 31).
static AreaData r104Ps2Area[4] = {
    {1, AREA_TYPE_XZ4, 0, {{-2101.0f, 1000.0f, 750.0f, {{-948.0f, -34153.0f}, {7134.0f, -23760.0f}, {8167.0f, -3559.0f}, {3622.0f, 127.0f}}}}},
    {1, AREA_TYPE_XZ4, 0, {{-2101.0f, 1000.0f, 750.0f, {{-7736.0f, -17033.0f}, {-2466.0f, -21039.0f}, {6342.0f, -9040.0f}, {1638.0f, -5752.0f}}}}},
    {1, AREA_TYPE_XZ4, 0, {{-2101.0f, 1000.0f, 750.0f, {{-3319.0f, -20258.0f}, {1533.0f, -24029.0f}, {3593.0f, -21105.0f}, {-1342.0f, -16940.0f}}}}},
    {1, AREA_TYPE_XZ4, 0, {{0.0f, 1000.0f, 750.0f, {{-24691.0f, 9279.0f}, {-16275.0f, -872.0f}, {60.0f, 21379.0f}, {-8180.0f, 26748.0f}}}}},
};

static int r104_ps2InArea(int i)
{
    return AreaHitCheck(&r104Ps2Area[i], &pPL->pos) != 0;
}

// PS2 IsGanado (SLUS 0x1bb630) is ids 0x10..0x20 and 0x40..0x4F except 0x4B / 0x4E, in the PS2 id map: the PS2
// moved the GameCube object ids up by 0x10 (SetDoor creates 0x51 = GC door 0x41, SetEmHit 0x5D = GC 0x4D), so
// its 0x40..0x4F are enemies, while here they are doors, boxes, barrels, windows, items and hit targets (taking
// them deleted 20 objects, doors included, in the first test). Only 0x10..0x20 here: r104's Ganados are all id
// 0x13, the range of the rooms' own SceCountEmAlive(0x10, 0x20); the count (PS2 SceCountEmAliveGanado) is the same.
static int r104_ps2IsGanado(int id)
{
    return id >= 0x10 && id < 0x21;
}

// PS2 EmFarDeleteNoWrap(keep, 0) (st1_1 0x2de8): while more than `keep` Ganados are alive, delete the one
// farthest from the player (list entry cleared) - never types 2/5/6/0xA/0xD/0x16 nor flag 0x10000000 ones.
static int r104_ps2FarDelete(int keep)
{
    int n = 0;
    int done = 0;
    u32 i;

    for (i = 0; i < EmMgr.nArray; i++) {
        cEm* em = (cEm*) EmMgr.workAt(i);

        if (em != 0 && r104_ps2IsGanado(em->id) && SceCheckEmAlive(em) == 1) {
            n++;
        }
    }
    while (done < n - keep) {
        cEm* best = 0;
        f32 bestD = 0.0f;

        for (i = 0; i < EmMgr.nArray; i++) {
            cEm* em = (cEm*) EmMgr.workAt(i);
            f32 dx, dy, dz, d2;

            if (em == 0 || !r104_ps2IsGanado(em->id) || SceCheckEmAlive(em) != 1) {
                continue;
            }
            switch (em->type) {
            case 0x16: case 2: case 5: case 6: case 0xA: case 0xD:
                continue;
            }
            if (em->flag & 0x10000000) {
                continue;
            }
            dx = em->pos.x - pPL->pos.x;
            dy = em->pos.y - pPL->pos.y;
            dz = em->pos.z - pPL->pos.z;
            d2 = dx * dx + dy * dy + dz * dz;
            if (!(d2 > 3000.0f) || !(d2 > bestD)) {
                continue;
            }
            bestD = d2;
            best = em;
        }
        if (best == 0) {
            break;
        }
        {
            EmListData* l = GetListPtrFromEm(best);

            if (l != 0) {
                l->be_flag &= ~1;
            }
        }
        EmMgr.destroy(best);
        done++;
    }
    return done;
}

static void r104_ps2ResetInit(R104Ps2Reset* r, const R104Ps2ResetData* d)
{
    r->d = d;
    r->cnt = 0;
    if (RsfCheck(G_ROOM_ID, d->flagC) == 0) {
        if (RsfCheck(G_ROOM_ID, d->flagB)) {
            RsfClear(G_ROOM_ID, d->flagB);
        } else {
            RsfClear(G_ROOM_ID, d->flagA);
        }
    }
}

// PS2 EmReset::set: a third try retires the wave (flagE); no kill counting.
static int r104_ps2ResetSet(R104Ps2Reset* r)
{
    const R104Ps2ResetData* d = r->d;

    if (r->cnt >= 2) {
        RsfSet(G_ROOM_ID, d->flagE);
        return 0;
    }
    if (RsfCheck(G_ROOM_ID, d->flagE)) {
        return 0;
    }
    if (EvtFlagChk(evtFlagBase(), d->flagD) == 0) {
        cEmWrapSetEmI(&r->em[0], d->em[0], -1, 0, 0, 1);
        cEmWrapSetEmI(&r->em[1], d->em[1], -1, 0, 0, 1);
        cEmWrapSetEmI(&r->em[2], d->em[2], -1, 0, 0, 1);
        EvtFlagOn(evtFlagBase(), d->flagD);
        r->cnt = 0;
    } else {
        if (r->em[0].ckResetEnable() != 1 || r->em[1].ckResetEnable() != 1 || r->em[2].ckResetEnable() != 1) {
            return 0;
        }
        r->em[0].setReset();
        r->em[1].setReset();
        r->em[2].setReset();
    }
    r->cnt++;
    OSReport("ps2en: r104 wave %d send %d\n", (int) (r - r104_work->ps2Reset), r->cnt);
    return 1;
}

static void r104_ps2ExecEmReset(int area)
{
    static const u8 order[4][2] = {{2, 3}, {3, 2}, {0, 1}, {1, 0}};

    if (r104_ps2ResetSet(&r104_work->ps2Reset[order[area][0]]) != 1) {
        r104_ps2ResetSet(&r104_work->ps2Reset[order[area][1]]);
    }
}

// PS2 checkEmReset (st1_1 0x9f38): nothing until the dash-in (flag 15); area 3 retires wave 1; area 0x15 once
// (flag 29) far-deletes down to 7 and sends 0xF8 / 0xF9; areas 0x16 / 0x17 once (flag 30) send 0xF2 / 0xFE
// while fewer than 8 are alive; otherwise a wave for the player's area while fewer than 7 are alive.
static void r104_ps2CheckEmReset()
{
    u32 i;
    u32 alive;
    int area;

    SceSleep(1);
    U32Set(r104_work->emNum, SceCountEmAlive(0x10, 0x20));
    if (r104_work->emNum <= 10) {
        r104_work->emNum = 10;
    }
    r104_work->resetCnt = 0;
    for (i = 0; i < 4; i++) {
        r104_ps2ResetInit(&r104_work->ps2Reset[i], &r104_ps2ResetData[i]);
    }
    for (;;) {
        SceSleep(1);
        if (RsfCheck(G_ROOM_ID, 15) == 0) {
            continue;
        }
        alive = SceCountEmAlive(0x10, 0x20);
        if (SceAtHitCheck(3) == 1) {
            r104_work->ps2Reset[1].cnt = 2;
            RsfSet(G_ROOM_ID, 5);
            RsfSet(G_ROOM_ID, 6);
            RsfSet(G_ROOM_ID, 7);
        }
        if (RsfCheck(G_ROOM_ID, 29) == 0 && r104_ps2InArea(0)) {
            int n = r104_ps2FarDelete(7);

            RsfSet(G_ROOM_ID, 29);
            setEm(0xF8, -1, 0, 1, 1);
            setEm(0xF9, -1, 0, 1, 1);
            OSReport("ps2en: r104 area 0x15: far-deleted %d, sent 0xF8/0xF9 (alive %d)\n", n, SceCountEmAlive(0x10, 0x20));
            continue;
        }
        if (RsfCheck(G_ROOM_ID, 30) == 0 && alive < 8 && (r104_ps2InArea(1) || r104_ps2InArea(2))) {
            RsfSet(G_ROOM_ID, 30);
            setEm(0xF2, -1, 0, 1, 1);
            setEm(0xFE, -1, 0, 1, 1);
            OSReport("ps2en: r104 area 0x16/0x17: sent 0xF2/0xFE (alive %d)\n", alive);
            continue;
        }
        area = r104_checkNowArea();
        if (area >= 0 && alive < 7) {
            r104_ps2ExecEmReset(area);
        }
    }
}

// PS2 cPatrol104::move (st1_1 0x9468): after the dash-in, mode 1 patrols are removed and mode 2 ones join.
static void r104_ps2PatrolMove(R104Ps2Patrol* w)
{
    cPatrol104* p = &w->p;
    Vec t;

    if (p->active == 0) {
        return;
    }
    if (RsfCheck(G_ROOM_ID, 15)) {
        if (w->mode == 1) {
            if (p->em.isAlive() == 1) {
                p->em.destroy();
            }
            p->active = 0;
            return;
        }
        if (w->mode == 2) {
            if (p->em.isAlive() == 1) {
                p->em.setFindPL();
            }
            p->active = 0;
            return;
        }
    }
    if (p->em.isAlive() == 0 || p->em.ckFindPL() == 1) {
        p->active = 0;
        return;
    }
    if (p->em.ckGoto() == 0) {
        cPatrol104_getNextTarget(p, &t);
        p->em.setGoto(&t, 6);
    }
}

static void r104_ps2InitEmPatrol()
{
    u32 i;
    R104Ps2Patrol pat[6];

    SceSleep(1);
    for (i = 0; i < 6; i++) {
        R104PatrolData d;

        d.no = r104_ps2PatrolData[i].no;
        d.pos = r104_ps2PatrolData[i].pos;
        cPatrol104_init(&pat[i].p, &d);
        pat[i].mode = r104_ps2PatrolData[i].mode;
    }
    SceSleep(1);
    for (;;) {
        for (i = 0; i < 6; i++) {
            r104_ps2PatrolMove(&pat[i]);
        }
        SceSleep(1);
    }
}

// PS2 BGM task (st1_1 0x8e68): the battle stream ends once every wave is retired (24..27), the dash-in (15)
// and both area sends (29, 30) have run and no Ganado is left.
static void r104_ps2CheckBgmPlay()
{
    static const u8 need[7] = {24, 25, 26, 27, 15, 29, 30};
    int i;

    while (SceCkFindPL(0) != 1) {
        SceSleep(1);
    }
    SndRoomStrStart(1, 3, 1);
    for (;;) {
        for (i = 0; i < 7; i++) {
            if (RsfCheck(G_ROOM_ID, need[i]) == 0) {
                break;
            }
        }
        if (i == 7) {
            break;
        }
        SceSleep(1);
    }
    while (SceCountEmAlive(0x10, 0x20) != 0) {
        SceSleep(1);
    }
    SndRoomStrStop(3);
}
#define R104_CHECK_EM_RESET r104_ps2CheckEmReset
#define R104_INIT_EM_PATROL r104_ps2InitEmPatrol
#define R104_CHECK_BGM_PLAY r104_ps2CheckBgmPlay
#else
#define R104_CHECK_EM_RESET r104_checkEmReset
#define R104_INIT_EM_PATROL r104_initEmPatrol
#define R104_CHECK_BGM_PLAY r104_checkBgmPlay
#endif

// Room init: doors 1/2 paired as a double door with be_flag 8 and an ambient boost; the s00/s01 event
// callbacks. First visit (Room_flg bit 1 clear, debug trigger 1 skips) runs the arrival event, else the
// kill-count reset waves and the patrols start at once. Area 0x11 = event s10 once (bit 21), area 0x12 =
// event s20 once (bit 22, pre-loaded after s00). Item area 0x97 is the door-107 key, hidden until
// door_unlock[0] 0x00400000 (area 0 = locked door message + key-use watcher). Area 0xA = the view once
// (bit 14), area 0xE = the dash-in wave once (bit 15); three shelf and two box item events; BGM task.
void R104Init()
{
    cModel* m;

#line 49 "D:/Bio4/Prog/r104.cpp"
    r104_work = (R104Work*) MEM_CALLOC(sizeof(R104Work), 1, 0xd);

    if (getRoomEtcDoor(1, (cEm**) &r104_work->door0, 1)) {
        if (getRoomEtcDoor(2, (cEm**) &r104_work->door1, 1)) {
            r104_work->door0->setDoor(r104_work->door1);
        }
        {
            cEmDoor* d = r104_work->door0;

            BitOn(d->be_flag, 8);
            d->AddAmb_b = d->AddAmb_g = d->AddAmb_r = 0x28;
        }
        {
            cEmDoor* d = r104_work->door1;

            BitOn(d->be_flag, 8);
            d->AddAmb_b = d->AddAmb_g = d->AddAmb_r = 0x28;
        }
    }
    EvtMgr.SetFunc("evt_r104s00_func", (void*) Evt_R104S00_Func);
    EvtMgr.SetFunc("evt_r104s01_func", (void*) Evt_R104S01_Func);
    if (DebugTrg(1) == 1) {
        RsfSet(G_ROOM_ID, 1);
    }
    if (RsfCheck(G_ROOM_ID, 1) == 0) {
        SceExec(0x12, (TaskFunc) r104_execEvent00, 0, 0, SCE_PRIO_DEF_2, 0);
    } else {
        SceExec(0x12, (TaskFunc) R104_CHECK_EM_RESET, 0, 0, SCE_PRIO_DEF_2, 0);
        SceExec(0x12, (TaskFunc) R104_INIT_EM_PATROL, 0, 0, SCE_PRIO_DEF_2, 0);
    }
    if (RsfCheck(G_ROOM_ID, 21) == 0) {
        SceAtDataSet_exec(0x11, SCE_LEVEL10, 0, (TaskFunc) r104_execEvent10, 0, 1);
    }
    if (RsfCheck(G_ROOM_ID, 22) == 0) {
        if (RsfCheck(G_ROOM_ID, 1) && !R104_MOVIES_OWN()) {
            EvtMgr.EvtReadAram("event/evd/r104s20.evd", 0, 0, 0, 0);
        }
        SceAtDataSet_exec(0x12, SCE_LEVEL10, 0, (TaskFunc) r104_execEvent20, 0, 1);
    }
    SceAtSetEnable(0x97, 1);
    m = SceAtItemModelPtr(0x97);
    if (m != 0) {
        m->LightInfo.EnableMask = (m->LightInfo.EnableMask & ~0x20) | 0x10;
        m->setNoSuspend(1);
    }
    if (!(pG->door_unlock[0] & 0x00400000)) {
        SceAtSetEnable(0x97, 0);
        SceAtDataSet_exec(0, SCE_LEVEL10, 0, (TaskFunc) r104_checkDoor107, 0, 1);
        SceExec(0x12, (TaskFunc) r104_checkDoor107KeyUse, 0, 0, SCE_PRIO_DEF_2, 0);
    }
    if (RsfCheck(G_ROOM_ID, 14) == 0) {
        SceAtDataSet_exec(0xA, SCE_LEVEL10, 0, (TaskFunc) r104_execShowView, 0, 1);
    }
    if (RsfCheck(G_ROOM_ID, 15) == 0) {
        SceAtDataSet_exec(0xE, SCE_LEVEL10, 0, (TaskFunc) r104_execEmDash, 0, 1);
    }
#if defined(RE4DC_GAME) && !defined(__PPC__)
    SceSetItemEvent(0xB, 0x84, 0x10, 7, r104_openShelf, (TaskFunc) r104_openedShelf, 0, 0);
    SceSetItemEvent(0xC, 0x8E, 0x11, 8, r104_openShelf, (TaskFunc) r104_openedShelf, 1, 0);
    SceSetItemEvent(0xD, 0x89, 0x12, 9, r104_openShelf, (TaskFunc) r104_openedShelf, 2, 0);
    SceSetItemEvent(0xF, 0x8F, 0x13, 0xA, r104_openBox, (TaskFunc) r104_openedBox, 0, 0);
    SceSetItemEvent(0x10, 0x90, 0x14, 0xB, r104_openBox, (TaskFunc) r104_openedBox, 1, 0);
#else
    SceSetItemEvent(0xB, 0x84, 0x10, 7, r104_openShelf, r104_openedShelf, 0, 0);
    SceSetItemEvent(0xC, 0x8E, 0x11, 8, r104_openShelf, r104_openedShelf, 1, 0);
    SceSetItemEvent(0xD, 0x89, 0x12, 9, r104_openShelf, r104_openedShelf, 2, 0);
    SceSetItemEvent(0xF, 0x8F, 0x13, 0xA, r104_openBox, r104_openedBox, 0, 0);
    SceSetItemEvent(0x10, 0x90, 0x14, 0xB, r104_openBox, r104_openedBox, 1, 0);
#endif
    SceExec(0x12, (TaskFunc) R104_CHECK_BGM_PLAY, 0, 0, SCE_PRIO_DEF_2, 0);
}

// Per-frame room main: nothing (PS2_ENEMY_ROOMS r104: PS2 R104Main 0x8dd0, after s20 the merchant 0x5E is drawn
// and moved only while Leon is in PS2 area 0x18).
void R104Main()
{
#if R104_PS2
    if (RsfCheck(G_ROOM_ID, 22) && r104_work->ps2Merchant.isAlive() == 1) {
        static int last = -1;
        int in = r104_ps2InArea(3);

        r104_work->ps2Merchant.setTrans(in);
        r104_work->ps2Merchant.setMove(in);
        if (in != last) {
            OSReport("ps2en: r104 merchant %s\n", in ? "drawn and moving (area 0x18)" : "hidden and frozen");
            last = in;
        }
    }
#endif
}

// Battle stream from the first contact until every wave is done and the Ganados are dead.
static void r104_checkBgmPlay()
{
    while (SceCkFindPL(0) != 1) {
        SceSleep(1);
    }
    SndRoomStrStart(1, 3, 1);
    while (!(RsfCheck(G_ROOM_ID, 3) && RsfCheck(G_ROOM_ID, 6) && RsfCheck(G_ROOM_ID, 9) && RsfCheck(G_ROOM_ID, 12))) {
        SceSleep(1);
    }
    while (SceCountEmAlive(0x10, 0x20) != 0) {
        SceSleep(1);
    }
    SndRoomStrStop(3);
}

// Three more Ganados rush in from the back.
static void r104_execEmDash()
{
#if R104_PS2
    // PS2 (st1_1 0x8fe0): two, not three.
    RsfSet(G_ROOM_ID, 15);
    EM_LIST(0xFC)->be_flag |= 1;
    EM_LIST(0xFD)->be_flag |= 1;
    setEm(0xFC, -1, 0, 1, 1);
    setEm(0xFD, -1, 0, 1, 1);
    r104_work->emNum += 2;
    OSReport("ps2en: r104 dash-in 0xFC/0xFD (alive %d)\n", SceCountEmAlive(0x10, 0x20));
    return;
#endif
    RsfSet(G_ROOM_ID, 15);
    EM_LIST(0xF2)->be_flag |= 1;
    EM_LIST(0xFC)->be_flag |= 1;
    EM_LIST(0xFD)->be_flag |= 1;
    setEm(0xF2, -1, 0, 1, 1);
    setEm(0xFC, -1, 0, 1, 1);
    setEm(0xFD, -1, 0, 1, 1);
    r104_work->emNum += 3;
}

// Box `no` opens (opened: already open, snap the lid).
extern "C" void r104_openBox_main(int no, int opened)
{
    f32 ang = 0.0f;
    cObj* obj = 0;

    switch (no) {
    case 0:
        obj = SmdGetObjPtr(0x36);
        ang = 1.7f;
        break;
    case 1:
        obj = SmdGetObjPtr(0x38);
        ang = 1.7f;
        break;
    default:
        SceExit();
        break;
    }
    if (obj != 0) {
        obj->be_flag |= 0x20;
        if (opened == 1) {
            obj->pParts->ang.z = ang;
        } else {
            int i;

            ang /= 30.0f;
            SndCall(6, 0x5B, 0, 0, 0, 0);
            for (i = 30; i != 0; i--) {
                if (obj != 0) {
                    obj->pParts->ang.z += ang;
                }
                SceSleep(1);
            }
        }
    }
}

// Item-event "already opened": pose box `no` open (no comes in r3 untouched, see the note).
#if defined(RE4DC_GAME) && !defined(__PPC__)
// SceExec passes the item-event argument; do not depend on the PPC r3 register
// surviving an uninitialised C local on the native target.
static void r104_openedBox(int no)
{
    r104_openBox_main(no, 1);
}
#else
static void r104_openedBox()
{
    int no; // uninitialised in the original: the item event passes `no` in r3 and the void-parameter
            // helper forwards whatever r3 holds (the target is `li r4,1; bl` with r3 untouched)
    r104_openBox_main(no, 1);
}
#endif

// Item-event opener: animate box `no` open.
static void r104_openBox(int no)
{
    r104_openBox_main(no, 0);
}

// Shelf `no` opens.
extern "C" void r104_openShelf_main(int no, int opened)
{
    f32 ang = 0.0f;
    cObj* obj = 0;

    switch ((u32) no) {
    case 0:
        obj = SmdGetObjPtr(0x29);
        ang = -2.0943952f;
        break;
    case 1:
        obj = SmdGetObjPtr(0x2A);
        ang = -2.7925267f;
        break;
    case 2:
        obj = SmdGetObjPtr(0x2B);
        ang = -2.7925267f;
        break;
    default:
        SceExit();
        break;
    }
    if (obj != 0) {
        obj->be_flag |= 0x20;
        if (opened == 1) {
            obj->pParts->ang.y = ang;
        } else {
            int i;

            ang /= 30.0f;
            SndCall(6, 0x1C, 0, 0, 0, 0);
            for (i = 30; i != 0; i--) {
                if (obj != 0) {
                    obj->pParts->ang.y += ang;
                }
                SceSleep(1);
            }
        }
    }
}

// Item-event "already opened": pose shelf `no` open.
#if defined(RE4DC_GAME) && !defined(__PPC__)
// SceExec passes the item-event argument; do not depend on the PPC r3 register
// surviving an uninitialised C local on the native target.
static void r104_openedShelf(int no)
{
    r104_openShelf_main(no, 1);
}
#else
static void r104_openedShelf()
{
    int no; // same as r104_openedBox
    r104_openShelf_main(no, 1);
}
#endif

// Item-event opener: animate shelf `no` open.
static void r104_openShelf(int no)
{
    r104_openShelf_main(no, 0);
}

// Advance the two-point patrol to its next way point (wraps) and return that position.
extern "C" void cPatrol104_getNextTarget(cPatrol104* p, Vec* out)
{
    p->cur++;
    if (p->cur >= p->nPoint) {
        p->cur = 0;
    }
    *out = p->pos[p->cur];
}

// Bind a patrol to the Ganado of table entry d: way points = its spawn position and d->pos; starts it
// walking (goto mode 6) toward the table point. Inactive if the enemy is not alive.
extern "C" void cPatrol104_init(cPatrol104* p, R104PatrolData* d)
{
    cEmWrapSetPtrI(&p->em, d->no, -1, 0);
    if (p->em.isAlive() == 1) {
        p->active = 1;
        p->em.getPos(&p->pos[0]);
        p->pos[1] = d->pos;
        p->cur = 1;
        p->nPoint = 2;
        p->em.setGoto(&d->pos, 6);
    } else {
        p->active = 0;
    }
}

// Per-frame patrol step: stops (active = 0) when the enemy dies or spots the player; otherwise, each time
// the goto finished, walks to the other way point.
extern "C" void cPatrol104_move(cPatrol104* p)
{
    Vec t;

    if (p->active == 0) {
        return;
    }
    if (p->em.isAlive() == 0 || p->em.ckFindPL() == 1) {
        p->active = 0;
    }
    if (p->em.ckGoto() == 0) {
        cPatrol104_getNextTarget(p, &t);
        p->em.setGoto(&t, 6);
    }
}

// The seven patrolling Ganados walk between their start and the table point.
static void r104_initEmPatrol()
{
    u32 i;
    u32 n = 7;

    SceSleep(1);
    cPatrol104 pat[7];
    for (i = 0; i < n; i++) {
        cPatrol104_init(&pat[i], &r104_patrolData[i]);
    }
    SceSleep(1);
    for (;;) {
        for (i = 0; i < n; i++) {
            cPatrol104_move(&pat[i]);
        }
        SceSleep(1);
    }
}

// End of the view event: stream faded out over 50 frames, camera back, SceEventEnd.
static void r104_execShowView_end()
{
    SndStrReq(r104_work->strId, 4, 50, 0);
    CamCtrl.Comeback(0);
    SceEventEnd(0);
}

// Show the farm: camera cut 4 with the stream.
static inline f32 FCRef(const f32& v) { return v; }

// Area 0xA once (Room_flg bit 14): stream 0x15 with camera cut 4 (the look over the area), clearing
// Status_flg[1] 0x10000000, until the camera motion ends; player-cancellable.
static void r104_execShowView()
{
    // The 0.0 is loaded after the RsfSet store: a pool constant would move above it (pool loads never
    // depend on stores), a `static const` read through a reference stays below (docs/matching.md, cSceObj).
    static const f32 vol = 0.0f;

    RsfSet(G_ROOM_ID, 14);
    r104_work->strId = SndStrReq(0, 0x15, 0x80000003, 0, 0, FCRef(vol));
    SceSetEventCancel(1, (TaskFunc) r104_execShowView_end, 0, -1, 1);
    SceEventStart(1);
    pG->Status_flg[1] &= ~0x10000000;
    CamCtrl.CutCall(4);
    while (CamCtrl.IsMotionEnd() == 0) {
        SceSleep(1);
    }
    r104_execShowView_end();
}

// The player holds the key: the door unlocks with a camera cut and the message.
static void r104_checkDoor107KeyUse()
{
    while (ItemMgr.check(0xA6) != 1) {
        SceSleep(1);
    }
    SceEventStart(0);
    CamCtrl.CutCall(0xC);
    SceSleep(20);
    SceAtSetEnable(0x97, 1);
    SndCall(6, 3, 0, 0, 0, 0);
    SceMesSet(1, 0, 1, 0x64, 0x150 - cMes.getWork()->lineSpace - cMes.getWork()->m_font_h - 1);
    pG->door_unlock[0] |= 0x00400000;
    SceAtDataReset(0);
    CamCtrl.Comeback(0);
    SceEventEnd(0);
}

// The locked door: the sub screen when the key or both halves are held.
static void r104_checkDoor107()
{
    SceUpCut(0, 0xC, 2, UP_CUT_ATTR_CUT_FIX);
    if (ItemMgr.num(0xA6) == 0) {
        if (ItemMgr.num(0xA4) == 1 && ItemMgr.num(0xA5) == 1) {
            SubScreenOpen(SS_OPEN_ITEM, SS_ATTR_EVENT);
        } else {
            CamCtrl.Comeback(0);
        }
    } else {
        SubScreenOpen(SS_OPEN_ITEM, SS_ATTR_EVENT);
    }
}

// A reset wave from its table entry: the wave flags of an interrupted run are cleared.
extern "C" void EmReset_init(EmReset* r, R104ResetData* d)
{
    r->R104ResetData::em[0] = d->em[0];
    r->R104ResetData::em[1] = d->em[1];
    r->R104ResetData::em[2] = d->em[2];
    r->flagA = d->flagA;
    r->flagB = d->flagB;
    r->flagC = d->flagC;
    IntSet(r->flagD, d->flagD);   // reference store: keeps the `lwz pG` of the RsfCheck below the copies
    if (RsfCheck(G_ROOM_ID, r->flagC) == 0) {
        if (RsfCheck(G_ROOM_ID, r->flagB)) {
            RsfClear(G_ROOM_ID, r->flagB);
        } else {
            RsfClear(G_ROOM_ID, r->flagA);
        }
    }
}

// Sets the wave (first time) or resets its three enemies; 1 when it ran.
extern "C" int EmReset_set(EmReset* r)
{
    if (RsfCheck(G_ROOM_ID, r->flagC)) {
        return 0;
    }
    if (EvtFlagChk(evtFlagBase(), r->flagD) == 0) {
        cEmWrapSetEmI(&r->em[0], r->R104ResetData::em[0], -1, 0, 0, 1);
        cEmWrapSetEmI(&r->em[1], r->R104ResetData::em[1], -1, 0, 0, 1);
        cEmWrapSetEmI(&r->em[2], r->R104ResetData::em[2], -1, 0, 0, 1);
        EvtFlagOn(evtFlagBase(), r->flagD);
    } else {
        if (r->em[0].ckResetEnable() != 1 || r->em[1].ckResetEnable() != 1 || r->em[2].ckResetEnable() != 1) {
            return 0;
        }
        r->em[0].setReset();
        r->em[1].setReset();
        r->em[2].setReset();
    }
    U32Set(r104_work->emNum, r104_work->emNum + 3);
    U32Set(r104_work->resetCnt, r104_work->resetCnt + 1);
    if (RsfCheck(G_ROOM_ID, r->flagA) == 0) {
        RsfSet(G_ROOM_ID, r->flagA);
    } else if (RsfCheck(G_ROOM_ID, r->flagB) == 0) {
        RsfSet(G_ROOM_ID, r->flagB);
    } else {
        RsfSet(G_ROOM_ID, r->flagC);
    }
    return 1;
}

// The area the player stands in (0..3), -1 elsewhere.
extern "C" int r104_checkNowArea()
{
    if (SceAtHitCheck(4) == 1) {
        return 0;
    }
    if (SceAtHitCheck(5) == 1) {
        return 1;
    }
    if (SceAtHitCheck(6) == 1 || SceAtHitCheck(7) == 1) {
        return 2;
    }
    if (SceAtHitCheck(8) == 1) {
        return 3;
    }
    return -1;
}

// The next wave for the player's area, by the wave flags.
extern "C" void r104_execEmReset(int area)
{
    switch (area) {
    case 0:
        if (RsfCheck(G_ROOM_ID, 8) == 0) {
            EmReset_set(&r104_work->reset[2]);
            return;
        }
        if (RsfCheck(G_ROOM_ID, 11) == 0) {
            EmReset_set(&r104_work->reset[3]);
            return;
        }
        if (RsfCheck(G_ROOM_ID, 9) == 0) {
            if (EmReset_set(&r104_work->reset[2]) == 0) {
                EmReset_set(&r104_work->reset[3]);
            }
            return;
        }
        if (RsfCheck(G_ROOM_ID, 12) == 0) {
            EmReset_set(&r104_work->reset[3]);
            return;
        }
        break;
    case 1:
        if (RsfCheck(G_ROOM_ID, 11) == 0) {
            EmReset_set(&r104_work->reset[3]);
            return;
        }
        if (RsfCheck(G_ROOM_ID, 8) == 0) {
            EmReset_set(&r104_work->reset[2]);
            return;
        }
        if (RsfCheck(G_ROOM_ID, 12) == 0) {
            if (EmReset_set(&r104_work->reset[3]) == 0) {
                EmReset_set(&r104_work->reset[2]);
            }
            return;
        }
        if (RsfCheck(G_ROOM_ID, 9) == 0) {
            EmReset_set(&r104_work->reset[2]);
            return;
        }
        break;
    case 2:
        if (RsfCheck(G_ROOM_ID, 2) == 0) {
            EmReset_set(&r104_work->reset[0]);
            return;
        }
        if (RsfCheck(G_ROOM_ID, 5) == 0) {
            EmReset_set(&r104_work->reset[1]);
            return;
        }
        if (RsfCheck(G_ROOM_ID, 3) == 0) {
            if (EmReset_set(&r104_work->reset[0]) == 0) {
                EmReset_set(&r104_work->reset[1]);
            }
            return;
        }
        if (RsfCheck(G_ROOM_ID, 6) == 0) {
            EmReset_set(&r104_work->reset[1]);
            return;
        }
        break;
    case 3:
        if (RsfCheck(G_ROOM_ID, 5) == 0) {
            EmReset_set(&r104_work->reset[1]);
            return;
        }
        if (RsfCheck(G_ROOM_ID, 2) == 0) {
            EmReset_set(&r104_work->reset[0]);
            return;
        }
        if (RsfCheck(G_ROOM_ID, 6) == 0) {
            if (EmReset_set(&r104_work->reset[1]) == 0) {
                EmReset_set(&r104_work->reset[0]);
            }
            return;
        }
        if (RsfCheck(G_ROOM_ID, 3) == 0) {
            EmReset_set(&r104_work->reset[0]);
            return;
        }
        break;
    }
}

// Counts the kills and starts the next wave for the player's area.
static void r104_checkEmReset()
{
    u32 i;
    int alive;
    int area;

    SceSleep(1);
    U32Set(r104_work->emNum, SceCountEmAlive(0x10, 0x20));
    if (r104_work->emNum <= 10) {
        r104_work->emNum = 10;
    }
    r104_work->resetCnt = 0;
    for (i = 0; i < 4; i++) {
        EmReset_init(&r104_work->reset[i], &r104_resetData[i]);
    }
    for (;;) {
        SceSleep(1);
        alive = SceCountEmAlive(0x10, 0x20);
        if (SceAtHitCheck(3) == 1) {
            RsfSet(G_ROOM_ID, 5);
            RsfSet(G_ROOM_ID, 6);
            RsfSet(G_ROOM_ID, 7);
        }
        area = r104_checkNowArea();
        if (area < 0) {
            continue;
        }
        if (r104_work->emNum - alive < r104_work->resetCnt * 3 + 3) {
            continue;
        }
        r104_execEmReset(area);
    }
}

// The house event (s20): the player is put on the other side, the sub screen shows the file.
static void r104_execEvent20()
{
    cPlayer* pl;

    while (SceCheckEventStart() == 0) {
        SceSleep(1);
    }
    RsfSet(G_ROOM_ID, 22);
#if R104_ROUTE_MOVIES
    if (!R104_MOVIES_OWN() || RouteMoviePlay(0x10420, ROUTE_MOVIE_SND_EVENT, 0, 0) == RE4DC_MOVIE_UNHANDLED)
#endif
    EvtMgr.EvtReadExec("event/evd/r104s20.evd", 0x13, 0);
    FadeSetW(1, 0, 0, 0);
#if R104_PS2
    r104_work->ps2Merchant.setPtr(setEm(0x5E, -1, 0, 1, 1), 1);
#else
    setEm(0x5E, -1, 0, 1, 1);
#endif
    Vec pos;
    Vec* pa = &pos;
    pl = pPL;
    pos.x = -11843.0f;
    pa->y = 0.0f;
    pa->z = 12672.0f;
    f32 ry = 0.5f;
    pl->setPos(&pos);
    pos.x = 0.0f;
    pa->y = ry;
    pos.z = 0.0f;
    pl->setAng(&pos);
    FadeSetW(1, 0, 0, 0);
    SubScreenOpen(SS_OPEN_SHOP, 0);
}

// Area 0x11 once (Room_flg bit 21): sets Scenario_flg[0] 0x20000000 and plays event r104s10 (slot 0x13).
static void r104_execEvent10()
{
    BitOn(pG->Scenario_flg[0], 0x20000000);
    RsfSet(G_ROOM_ID, 21);
#if R104_ROUTE_MOVIES
    if (R104_MOVIES_OWN() && RouteMoviePlay(0x10410, ROUTE_MOVIE_SND_EVENT, 0, 0) != RE4DC_MOVIE_UNHANDLED) {
        return;
    }
#endif
    EvtMgr.EvtReadExec("event/evd/r104s10.evd", 0x13, 0);
}

// Arrival (s00): the intro event with the doors open-locked, then the enemies and the patrols.
static void r104_execEvent00()
{
    RsfSet(G_ROOM_ID, 1);
    if (Rnd() & 0x80) {
        pG->Room_flg[0] |= 0x04000000;
    } else {
        pG->Room_flg[0] &= ~0x04000000;
    }
    int skip = 0;
    DC.setAramSort(0);
    // The user variable on one side of the two tests keeps the pre-cse1 thread_jumps from threading the
    // first `beq` past the second test (rtx_equal_for_thread_p rejects REG_USERVAR_P pseudos): the second
    // compare is cse-deleted but its `bne` survives, as in the original (docs/research/, st1_1 pass 2).
    u32 f = pG->System_flg;
    if (f & 0x40) {
        skip = 1;
    }
    if (!(pG->System_flg & 0x40)) {
        SceEventStart(0);
        pG->System_flg |= 0x400;
        if (!R104_MOVIES_OWN()) {
        EvtMgr.EvtReadAram("event/evd/r104s01.evd", 0, 0, 0, 0);
        EvtMgr.EvtReadAram("event/evd/r104s02.evd", 0, 0, 0, 0);
        EvtMgr.EvtReadAram("event/evd/r104s10.evd", 0, 0, 0, 0);
        EvtMgr.EvtReadAram("event/evd/r104s20.evd", 0, 0, 0, 0);
        }
        if (r104_work->door0 != 0) {
            r104_work->door0->setOpenLock(1);
        }
        if (r104_work->door1 != 0) {
            r104_work->door1->setOpenLock(0);
        }
#if R104_ROUTE_MOVIES
        // EvtReadExec flags 0x20 = the evd StatusFlag 0x800 (keep the pose); flags 2 = a died-demo
        // event (Event::Run starts DiedemoExec at its end; s02 is 25 frames, shorter than 0x1E).
        if (R104_MOVIES_OWN()) {
            RouteMoviePlayQte(0x10400, ROUTE_MOVIE_SND_EVENT | ROUTE_MOVIE_KEEP_POSE,
                              (RouteEvtFunc) Evt_R104S00_Func, 0x1E, 4795, 60);
            BitOn(pG->System_flg, 0x400);
            if ((int) pG->Room_flg[0] < 0) {
                RouteMoviePlay(0x10401, ROUTE_MOVIE_SND_EVENT | ROUTE_MOVIE_KEEP_POSE,
                               (RouteEvtFunc) Evt_R104S01_Func, 0);
            } else {
                pG->System_flg &= ~0x40;
                RouteMoviePlay(0x10402, ROUTE_MOVIE_SND_EVENT, 0, 0);
                DiedemoExec(0, 1);
                for (;;) {
                    SceSleep(1);
                }
            }
        } else
#endif
        if (EvtMgr.EvtReadExec("event/evd/r104s00.evd", 0, 0x20)) {
            BitOn(pG->System_flg, 0x400);
            if ((int) pG->Room_flg[0] < 0) {
                EvtMgr.EvtReadExec("event/evd/r104s01.evd", 0, 0x20);
            } else {
                pG->System_flg &= ~0x40;
                EvtMgr.EvtReadExec("event/evd/r104s02.evd", 0, 2);
                for (;;) {
                    SceSleep(1);
                }
            }
        }
        if (r104_work->door0 != 0) {
            r104_work->door0->setNormal();
        }
        if (r104_work->door1 != 0) {
            r104_work->door1->setNormal();
        }
        SceEventEnd(0);
    }
#if R104_PS2
    // PS2 (st1_1 0xa6b0): seven at the start; 0xF8/0xF9/0xF2/0xFE come later by area, 0xF5/0xFA never.
    setEm(0xF0, -1, 0, 1, 1);
    setEm(0xF1, -1, 0, 1, 1);
    setEm(0xF3, -1, 0, 1, 1);
    setEm(0xF4, -1, 0, 1, 1);
    setEm(0xF6, -1, 0, 1, 1);
    setEm(0xF7, -1, 0, 1, 1);
    setEm(0xFB, -1, 0, 1, 1);
    OSReport("ps2en: r104 start 7 (alive %d)\n", SceCountEmAlive(0x10, 0x20));
#else
    setEm(0xF0, -1, 0, 1, 1);
    setEm(0xF1, -1, 0, 1, 1);
    setEm(0xF3, -1, 0, 1, 1);
    setEm(0xF4, -1, 0, 1, 1);
    setEm(0xF5, -1, 0, 1, 1);
    setEm(0xF6, -1, 0, 1, 1);
    setEm(0xF7, -1, 0, 1, 1);
    setEm(0xF8, -1, 0, 1, 1);
    setEm(0xF9, -1, 0, 1, 1);
    setEm(0xFA, -1, 0, 1, 1);
    setEm(0xFB, -1, 0, 1, 1);
    setEm(0xFE, -1, 0, 1, 1);
#endif
    SceExec(0x12, (TaskFunc) R104_INIT_EM_PATROL, 0, 0, SCE_PRIO_DEF_2, 0);
    SceExec(0x12, (TaskFunc) R104_CHECK_EM_RESET, 0, 0, SCE_PRIO_DEF_2, 0);
    SndBgmTblSet(0x104, 1);
    if (skip == 0) {
        OpeSetOpenTerm(4, 0.0f, 0.0f, 0.0f, 0.0f);
    }
    DC.setAramSort(1);
}

// Action-button success callback of the s00 event: Room_flg[0] bit 31 (the event's QTE passed).
static void r104_succeedAction()
{
    pG->Room_flg[0] |= 0x80000000;
}

// Event r104s00 callback: funcMode 0 marks status 3 and sets the cancel cut 0x1E; cuts 0/1/3 parent the
// kind-1 light to the event model evm4200; later cuts set the fade and the draw / CMF flags of the event
// models per cut.
static void Evt_R104S00_Func(Event* e)
{
    void* mod;
    void* mod2;
    int fadeOn;

    switch (e->funcMode) {
    case 0:
        EvtFlgOnStatus(e, 3);
        e->EvtCancelCut = 0x1E;
        break;
    case 1:
        switch (e->NowCut) {
        case 0:
        case 1:
        case 3:
            if (e->NowFrame == 0) {
                if (e->GetMod(&mod, "evm4200", 0, 0) == 1) {
                    cLight* l = LightMgr.getKindLight(1);

                    if (l != 0) {
                        l->setParent((cModel*) mod);
                    }
                }
            }
            break;
        }
        switch (e->NowCut) {
        case 0:
            if (e->NowFrame == 0) {
                fadeOn = 1;
                if (!(e->StatusFlag & 0x40000000)) {
                    fadeOn = 0;
                }
                if (fadeOn == 0) {
                    FadeSetW(2, 0, 0, 0);
                }
                if (e->GetMod(&mod2, "evm4500", 0, 0) == 1) {
                    ((cModel*) mod2)->be_flag |= 0x10;
                }
                if (e->GetMod(&mod2, "evm4600", 0, 0) == 1) {
                    ((cModel*) mod2)->be_flag |= 0x10;
                }
                if (e->GetMod(&mod2, "evm3700", 0, 0) == 1) {
                    ((cModel*) mod2)->ot_type = 1;
                }
            }
            if (e->NowFrame == 120) {
                fadeOn = 1;
                if (!(e->StatusFlag & 0x40000000)) {
                    fadeOn = 0;
                }
                if (fadeOn == 0) {
                    FadeSetW(0x80000002, 60, 0, 0);
                }
            }
            break;
        case 0x1E:
            BitOff(pG->Stop_flg, 0x100);
            if (!(pG->Room_flg[0] & 0x80000000)) {
                BitOff(pG->Disp_flg, 0x800);
                if (!(pG->Room_flg[0] & 0x04000000)) {
                    ActBtn.set(0x25, 5, (int) r104_succeedAction, 0, 0x42, 4, 0, 0);
                } else {
                    ActBtn.set(0x25, 5, (int) r104_succeedAction, 0, 0x42, 3, 0, 0);
                }
            } else {
                e->CancelSet();
            }
            break;
        }
        break;
    case 2:
        break;
    case 3:
        fadeOn = 1;
        if (!(e->StatusFlag & 0x4000)) {
            fadeOn = 0;
        }
        if (fadeOn == 0) {
            EvtMgr.EvtSndStrPlay(evtKey(&EvtMgr), 1, 0x86, 1, 0.0f);
        }
        break;
    }
}

// Event r104s01 callback: on its first frame make the event model evm4500 draw with be_flag 0x10.
static void Evt_R104S01_Func(Event* e)
{
    void* mod;

    if (e->funcMode == 1 && e->NowCut == 0 && e->NowFrame == 0) {
        if (e->GetMod(&mod, "evm4500", 0, 0) == 1) {
            ((cModel*) mod)->be_flag |= 0x10;
        }
    }
}
