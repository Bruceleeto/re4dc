#ifndef CTRL_H
#define CTRL_H

#include "types.h"
#include "vec.h"
#include "db_log.h"
#include "cManager.h"
#include "main_mem.h"

class cModel;

// Control work (game/ctrl.cpp, sizeof 0x214). cCtrl00/01/10.. specialise it by `id`.
class cCtrl : public cUnit {
public:
    u8 Id;                  // 0x0C  construct id (light: 1 = electric power path control)
#if defined(__PPC__)
    u8 pad_D[6];
    u8 work[0x214 - 0x13];  // 0x13  per-type work area
#else
    // The PowerPC reads the per-type work at 0x13 with misaligned halfword / word accesses
    // (Ctrl12Work timers, Ctrl11Work's u32 sound ids, ctrl01's s32); the SH-4 raises an address
    // error on them (Flycast does not). One byte later the work is word aligned; same size class.
    u8 pad_D[7];
    u8 work[0x214 - 0x14];  // 0x14  per-type work area
#endif

    virtual ~cCtrl() {}
    virtual void move();
    virtual void trans();
};

#line 113 "D:/Bio4/Prog/ctrl.h"
class cCtrlMgr : public cManager<cCtrl> {
public:
    cCtrlMgr();
    virtual void* memAlloc(u32 size) { return MEM_ALLOC(size, 1, 13); }
    virtual void memFree(void* p) { Mem_free(p); }
    virtual void memClear(cCtrl* p, u32 size) { memclr_asm(p, size); }
    virtual int construct(cCtrl* p, u32 id);

    void move();
    int trans();
};

extern cCtrlMgr CtrlMgr;

// Declared after cCtrlMgr: GCC walks the vtables in reverse declaration order, and the DOL has
// these three before the destroy() strings that instantiating cCtrlMgr's vtable emits.
class cCtrl00 : public cCtrl {};
class cCtrl01 : public cCtrl {};
class cCtrl10 : public cCtrl {};

// Work `no` of CtrlMgr, 0 when out of range (GetCtrlCtrl11/12 scan the array with it).
static inline cCtrl* CtrlMgrWork(u32 no)
{
    if (no >= CtrlMgr.nArray) {
        return 0;
    }
    return (cCtrl*)((u8*)CtrlMgr.pArray + CtrlMgr.size * no);
}

// ctrl11: sound effect handles kept per object (GetCtrlCtrl11 / Ctrl11SetSe*).
struct Ctrl11Work {
    s16 timer[16];   // 0x00  frames until the slot may play again
    u32 Se_id[15];  // 0x20  SndCall ids
    u32 Se_id_em38;    // 0x5C  em38 voice
};

class cCtrl11 : public cCtrl {
public:
    virtual void move();
};

// ctrl12: per-object timers, counters and TexRender handles.
struct Ctrl12Work {
    s16 timer[13];              // 0x00
    u16 cnt[6];                 // 0x1A
    u16 flag[1];                // 0x26
    struct TexRenderMng* tex2b; // 0x28
    struct TexRenderMng* tex2c; // 0x2C
    struct TexRenderMng* tex32; // 0x30
};

class cCtrl12 : public cCtrl {
public:
    virtual void move();
};

cCtrl* GetCtrlCtrl12();
enum CTRL12_ID {
    CTRL12_ID_EM1A_LIVE = 0,
    CTRL12_ID_EM27_RUSH = 1,
    CTRL12_ID_EM29_RUSH = 2,
    CTRL12_ID_EM29_LIVE = 3,
    CTRL12_ID_EM_ATK = 4,
    CTRL12_ID_EM10_PARASITE = 5,
    CTRL12_ID_EM10_ATK = 6,
    CTRL12_ID_EM10_LOST = 7,
    CTRL12_ID_EM10_THROW = 8,
    CTRL12_ID_EM10_NOT_NEAR = 9,
    CTRL12_ID_EM2B_ATK = 10,
    CTRL12_ID_BIGEFF = 11,
    CTRL12_ID_BACKSIGN = 12,
    CTRL12_ID_NUM = 13
};

void Ctrl12Set(cCtrl* pCtrl, int idx, u16 val);
int Ctrl12Ck(cCtrl* pCtrl, int idx);
enum CTRL12_ID_CNT {
    CTRL12_ID_CNT_EM1A_DIE = 0,
    CTRL12_ID_CNT_EM27_DIE = 1,
    CTRL12_ID_CNT_EM29_DIE = 2,
    CTRL12_ID_CNT_EM10_SET = 3,
    CTRL12_ID_CNT_PARASITE = 4,
    CTRL12_ID_CNT_EM2D_RESET = 5,
    CTRL12_ID_CNT_NUM = 6
};

void Ctrl12CntAdd(cCtrl* pCtrl, int idx, u16 add);
int Ctrl12CntCk(cCtrl* pCtrl, int idx, u16 val);
struct TexRenderMng* Ctrl12GetTexRenderEm2b(cCtrl* c);
struct TexRenderMng* Ctrl12GetTexRenderEm2c(cCtrl* c);
struct TexRenderMng* Ctrl12GetTexRenderEm32(cCtrl* c);

// ctrl14: the dragon head (stage 4 el gigante fire statue) pieces and their fire.
struct Ctrl14Work {
    cModel* obj[5];    // 0x00  [0] base, [1] head, [2] unused, [3]/[4] jaws
    u8 type;           // 0x14  dragon number (0..2)
    u8 espKind;        // 0x15  EspPullCoreKind at creation
    u8 flags;          // 0x16  bit0 moving, bit1 moved this frame
    u8 pad_17;
    s32 fireTimer;     // 0x18  frames the flame stays
    s32 fireDelay;     // 0x1C  frames until the flame starts
    class cSat* sat[3]; // 0x20  collision pieces
};

class cCtrl14 : public cCtrl {
public:
    virtual void move();
    virtual void getPos(Vec* out);
    virtual void getBaseMtx(Mtx m, int idx);
    virtual f32 getDir();
    virtual f32 getDir2();
    virtual void addWidth(f32 x);
    virtual void addHeight(f32 y);
    virtual void addDir(f32 add);
    virtual void setDir(f32 dir);
    virtual void resetDir();
    virtual void setFire();
    virtual int ckHitFire(Vec* p);
    virtual int ckHitFireBlocked();
};

cCtrl* GetCtrlDragon(u32 type);

cCtrl* GetCtrlCtrl11();
u32 Ctrl11SetSe(cCtrl* pCtrl, cModel* m, s16 time, u16 no, int idx);
u32 Ctrl11SetSe2(cCtrl* pCtrl, cModel* m, s16 time, u16 no, int idx, u16 blk);
u32 Ctrl11StopAndSetSe(cCtrl* pCtrl, cModel* m, s16 time, u16 no, int idx);
u32 Ctrl11SetSeEm38(cCtrl* pCtrl, cModel* m, u16 no);

#line 8 "D:/Bio4/Prog/ctrl.h"

// Control (ctrl*.cpp) header. Contents unknown; the object units include it after light.h and
// its range check emits the file-name string into their .rodata.
class cCtrlTbl {
public:
    u8* pData;
    u32 nData;

    u8* getData(u32 no) {
        if (no >= nData) {
            dbgAssert(__FILE__, __LINE__);
        }
        return pData + no;
    }
};

#endif
