// load_indicator.cpp -- LOAD_INDICATOR=1 (test 9 lane LOADIND; game30.mk, default 0: not built): the PS2 version's
// room-loading indicator ("Loading..." with a pulsing glow). The PS2 gameRoomInit (SLUS_211.34 0x217ee0) sets id class
// 0x2D from its option archive entry 0x3C (textures entry 0x10, IdTexDataLoad owner 10 = TEX_OWNER_ID_DEAD) for the
// whole room set-up, and its main loop runs IdSys.move / trans after FadeControl(1) while Status_flg bit 0x2000 (PS2
// layout) is set, so the units draw over the black fade while the game task sleeps in the room's disc reads. The
// GameCube option archive has no such entries; tools/d367/ps2_load_indicator.py converts the two units and their one
// texture (id 0x24) from the user's PS2 disc into dc/loadind.dat (+ the native texture dc/tex/c/cf2208cd-a6bfb2ef).
//
// Static banner (test 9): the port's room set-up runs mostly without yielding, so the screen holds the last frame
// presented before each blocking call. Every frame presented while the indicator is up (gameRoomInit start to end;
// door, warp, New Game and continue loads all pass through it) draws the units at the PS2 resting state, after
// FadeControl(1) (on top of the fade / the Filter09 door freeze), so the held frame carries the banner. No reads or
// waits are added. Follow-up after test 9: the animated version needs the room set-up to yield (async loading).
// Port differences (minimal, no logic writes):
//  - The PS2 moved IdSys.roomInit / Cckpt.roomInit to the start of gameRoomInit; the port keeps the GameCube order, so
//    the two units are saved before IdSys.roomInit and re-created (texture re-registered, unit bodies restored) after
//    Cckpt.roomInit: the animation continues instead of restarting.
//  - The active flag is this file's re4dc_loadind_active, not a game word (Status_flg is traced).
//  - Disp_flg: as the PS2, 0x2000 (id drawing off) is cleared and 0x10000 (hide OT type 0x13, the HUD) set at the
//    start; gameRoomInit zeroes Disp_flg later anyway. Only id_sys.cpp reads those two bits.
// The 1,664-byte file is read once at boot into a KOS allocation (not heap 4, not the option reservation); missing
// or invalid -> nothing happens (logged once).
#include "types.h"
#include "global.h"
#include "id_sys.h"
#include "texture.h"
#include <kos/fs.h>
#include <malloc.h>
#include <stdlib.h>
#include <string.h>

extern "C" void re4dc_log(const char* fmt, ...);
extern "C" void re4dc_draw_id_quad(const IdUnit*);  // ui_bridge.cpp
#if defined(RE4DC_DOOR_FREEZE) && RE4DC_DOOR_FREEZE
extern "C" void re4dc_ui_door_mark(void);  // platform/native_ui.cpp
#endif
extern cTexSys* g_pIdTexSys;
int IdTexDataLoad(void* data, int id);
void IdTexRelease(int id);

namespace {
struct LoadIndHeader {
    char magic[4];   // "R4LI"
    u32 version;     // 1
    u32 bytes;
    u32 tex_at;      // id texture data version 0xB
    u32 id_at;       // id table 2.00
    u32 tex_id;      // 0x24
    u32 pad[2];
};
const u8 kClass = 0x2D;
const int kOwner = TEX_OWNER_ID_DEAD;  // PS2: owner 10 (the died-demo textures; never live during a room set-up)
u8* blob;
bool tried;
bool shown;            // units set this room load
unsigned frames;       // main loop iterations drawn with the indicator this room load
IdUnit saved[4];
int nsaved;

bool load_textures()
{
    const LoadIndHeader* h = (const LoadIndHeader*) blob;
    if (g_pIdTexSys->wk[h->tex_id].owner != 0) {
        re4dc_log("loadind: texture id %02x held by owner %u, indicator skipped\n", (unsigned) h->tex_id,
                  (unsigned) g_pIdTexSys->wk[h->tex_id].owner);
        return false;
    }
    return IdTexDataLoad(blob + h->tex_at, kOwner) != 0;
}

// Static banner (test 9, user 2026-10-12): the port's room set-up blocks presentation for most of a load, so the
// held frame must already show the PS2 resting state. Colour curves off (idSysMove02 then uses col0), alpha fixed:
// unit 8 (the text) at its fade-in end value 150, unit 7 (the additive glow) at the middle of its 0..150 pulse.
void rest()
{
    for (int i = 0; i < IdSys.m_maxId; i++) {
        IdUnit* u = &IdSys.pUnit[i];
        if (u->be_flag == 0xFF || u->classNo != kClass) {
            continue;
        }
        u->curve[2] = 0;
        u->col0[3] = u->unitNo == 8 ? 150 : 75;
    }
}
}  // namespace

extern "C" {
int re4dc_loadind_active;

// OptionDataRead (boot): the converted indicator, once.
void re4dc_loadind_boot()
{
    if (tried) {
        return;
    }
    tried = true;
    file_t f = fs_open("/cd/dc/loadind.dat", O_RDONLY);
    if (f < 0) {
        re4dc_log("loadind: no dc/loadind.dat (indicator off)\n");
        return;
    }
    const int size = (int) fs_total(f);
    u8* p = size >= (int) sizeof(LoadIndHeader) && size <= 16384 ? (u8*) memalign(32, size) : 0;
    const bool ok = p != 0 && fs_read(f, p, size) == size;
    fs_close(f);
    const LoadIndHeader* h = (const LoadIndHeader*) p;
    if (!ok || memcmp(h->magic, "R4LI", 4) != 0 || h->version != 1 || h->bytes != (u32) size || h->tex_at >= h->bytes ||
        h->id_at >= h->bytes || h->tex_id > 0xFF || memcmp(p + h->id_at, "2.00", 4) != 0) {
        re4dc_log("loadind: dc/loadind.dat invalid (%d bytes)\n", size);
        free(p);
        return;
    }
    blob = p;
    re4dc_log("loadind: %d bytes at %p (KOS heap)\n", size, (void*) p);
}

// gameRoomInit start (PS2 order: before SndReadAddrInit and the room memory init).
void re4dc_loadind_begin()
{
    shown = false;
    frames = 0;
    nsaved = 0;
    if (blob == 0 || !load_textures()) {
        return;
    }
    BitOff(pG->Disp_flg, 0x2000);
    BitOn(pG->Disp_flg, 0x10000);
    IdSys.set(blob + ((const LoadIndHeader*) blob)->id_at, 0xFF, kClass, 0x0F, 0, 0);
    rest();
    shown = true;
    re4dc_loadind_active = 1;
}

// Before IdSys.roomInit (gameRoomInit): keep the units' animation state.
void re4dc_loadind_hold()
{
    nsaved = 0;
    if (!shown) {
        return;
    }
    for (int i = 0; i < IdSys.m_maxId && nsaved < 4; i++) {
        IdUnit* u = &IdSys.pUnit[i];
        if (u->be_flag != 0xFF && u->classNo == kClass) {
            saved[nsaved++] = *u;
        }
    }
    re4dc_loadind_active = 0;  // no drawing until resume (the pool and textures are being reset)
}

// After Cckpt.roomInit (gameRoomInit): the units again, continuing where they were.
void re4dc_loadind_resume()
{
    if (!shown) {
        return;
    }
    if (!load_textures()) {
        shown = false;
        return;
    }
    BitOff(pG->Disp_flg, 0x2000);
    BitOn(pG->Disp_flg, 0x10000);
    IdSys.set(blob + ((const LoadIndHeader*) blob)->id_at, 0xFF, kClass, 0x0F, 0, 0);
    rest();
    for (int i = 0, k = 0; i < IdSys.m_maxId && k < nsaved; i++) {
        IdUnit* u = &IdSys.pUnit[i];
        if (u->be_flag != 0xFF && u->classNo == kClass) {
            for (int j = 0; j < nsaved; j++) {
                if (saved[j].unitNo == u->unitNo) {
                    *u = saved[j];  // pointers are into the resident file; no parent (parentNo 0xFF)
                    u->be_flag &= ~0x10;
                    k++;
                    break;
                }
            }
        }
    }
    re4dc_loadind_active = 1;
}

// gameRoomInit end (PS2: after DoorSeCall): units and textures go.
void re4dc_loadind_end()
{
    re4dc_loadind_active = 0;
    if (!shown) {
        return;
    }
    BitOff(pG->Disp_flg, 0x10000);
    IdTexRelease(kOwner);
    IdSys.kill(0xFF, kClass);
    shown = false;
    re4dc_log("loadind: room %03x shown for %u frames\n", (unsigned) pG->room_id, frames);
}

// Main loop (main.cpp), after FadeControl(1): the PS2's second IdSys move/trans call.
// The room set-up releases the frame's primitive buffer (pG->prim_cnt), so AddOtDirect overflows for most of a load
// and an OT entry would never draw (test 9 stills: no banner; "AddOtDirect():PrimBuffer OVERFLOW!!" on every loading
// frame). The indicator's units are therefore kept out of IdSys.trans (visible bit cleared around the call) and drawn
// directly through the native id quad (ui_bridge.cpp, what IdCommonTrans does on the Dreamcast), on top of the fade.
void re4dc_loadind_frame()
{
    frames++;
    IdSys.move();
    IdUnit* mine[4];
    int n = 0;
    for (int i = 0; i < IdSys.m_maxId && n < 4; i++) {
        IdUnit* u = &IdSys.pUnit[i];
        if (u->be_flag != 0xFF && u->classNo == kClass && (u->be_flag & 0x8)) {
            u->be_flag &= ~0x8;
            mine[n++] = u;
        }
    }
    IdSys.trans();
#if defined(RE4DC_DOOR_FREEZE) && RE4DC_DOOR_FREEZE
    if (n) {
        re4dc_ui_door_mark();  // native_ui.cpp: the door's frozen picture and fades go under the banner
    }
#endif
    for (int k = 0; k < n; k++) {
        IdUnit* u = mine[k];
        u->be_flag = (u8) ((u->be_flag | 0x8) & ~0x10);
        if ((u->be_flag & 0x1) && u->pParent == 0 && u->texId != 0xFF) {
            re4dc_draw_id_quad(u);
        }
    }
}
}
