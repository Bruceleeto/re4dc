#ifndef EM_FAR_DELETE_H
#define EM_FAR_DELETE_H

// PS2 EmFarDelete / EmFarDeleteNoWrap (lane alivecap 2026-10-15; PS2-ENEMY-CODE-DIFF-20261015.md "Far delete"):
// shared room helper of the PS2 stage modules (st1_1 0x2a80 / 0x2de8, st2_4 0x1ff0 / 0x2358). While more than
// `keep` Ganados are alive, the one farthest from Leon (3D squared distance > 3000) is destroyed. Never deleted:
// types 2 / 5 / 6 / 0xA / 0xD / 0x16 (and 0x1A in the wrap version) and flag 0x10000000 ones. With `offscreen`,
// only Ganados whose sphere (pos.y + 1000, radius 1000) is outside the camera frustum. The NoWrap version also
// clears the list entry's alive bit (as SceDestroyEm), the wrap version leaves the list entry alone.
//
// Ganado range: the PS2 IsGanado map is 0x10..0x20 plus some 0x40..0x4F, but the PS2 moved the GameCube object
// ids up by 0x10, so its 0x40..0x4F are doors / boxes / windows here (r104.cpp r104_ps2IsGanado): 0x10..0x20 only,
// the rooms' own SceCountEmAlive range. PS2 ids 0x4B / 0x4E are excluded there and do not occur here.
//
// Header-only (static, no cost until a room calls it): r104 keeps its private, byte-identical r104_ps2FarDelete
// (the keep / any-view / NoWrap case of this helper) so the test 12 recipe image does not change; r301 / r327
// (castle / island lanes) call this one. Provisional until the ps2code lane's spec confirms the wrap details.
#include "types.h"
#include "global.h"
#include "em.h"
#include "em_set.h"
#include "player.h"
#include "camera.h"
#include "geometry.h"

#include "sce.h"

static inline int re4dc_emFarDeleteGanado(int id)
{
    return id >= 0x10 && id <= 0x20;
}

#if defined(RE4DC_ALIVE_CAP_ON) && RE4DC_ALIVE_CAP_ON
// ALIVE_CAP (em_set.cpp; coordinator decision 10-15, st3 lane r301): held Ganados count here as the PS2 counts them
// (there they are alive). The ones above `keep` are dropped first (latest held first; they are off screen), then the
// farthest live ones go as before, down to `keep` minus the held ones left. Not compiled without the cap.
extern "C" int re4dc_aliveCapHeldCount(int lo, int hi);
extern "C" int re4dc_aliveCapFarDrop(int max, int clearAlive);
#endif

// Returns the number of Ganados deleted (held entries dropped included).
static int re4dc_emFarDeleteImpl(int keep, int offscreen, int noWrap)
{
    int n = 0;
    int done = 0;
    u32 i;
#if defined(RE4DC_ALIVE_CAP_ON) && RE4DC_ALIVE_CAP_ON
    int dropped = 0;
#endif

    if (pPL == 0) {
        return 0;
    }
    for (i = 0; i < EmMgr.nArray; i++) {
        cEm* em = (cEm*) EmMgr.workAt(i);

        if (em != 0 && re4dc_emFarDeleteGanado(em->id) && SceCheckEmAlive(em) == 1) {
            n++;
        }
    }
#if defined(RE4DC_ALIVE_CAP_ON) && RE4DC_ALIVE_CAP_ON
    {
        const int held = re4dc_aliveCapHeldCount(0x10, 0x20);
        int excess = n + held - keep;

        if (excess > held) {
            excess = held;
        }
        if (excess > 0) {
            dropped = re4dc_aliveCapFarDrop(excess, noWrap);
        }
        keep -= held - dropped;
        if (keep < 0) {
            keep = 0;
        }
    }
#endif
    while (done < n - keep) {
        cEm* best = 0;
        f32 bestD = 0.0f;

        for (i = 0; i < EmMgr.nArray; i++) {
            cEm* em = (cEm*) EmMgr.workAt(i);
            f32 dx, dy, dz, d2;

            if (em == 0 || !re4dc_emFarDeleteGanado(em->id) || SceCheckEmAlive(em) != 1) {
                continue;
            }
            switch (em->type) {
            case 0x16: case 2: case 5: case 6: case 0xA: case 0xD:
                continue;
            case 0x1A:
                if (!noWrap) {
                    continue;
                }
                break;
            }
            if (em->flag & 0x10000000) {
                continue;
            }
            if (offscreen) {
                GeoSphere sph;

                sph.pos = em->pos;
                sph.pos.y += 1000.0f;
                sph.r = 1000.0f;
                if (collision_sphere_hexahedron(&sph, (GeoHexahedron*) CameraViewFrustumPtr(&pG->Cam))) {
                    continue;   // in view: kept
                }
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
        if (noWrap) {
            EmListData* l = GetListPtrFromEm(best);

            if (l != 0) {
                l->be_flag &= ~1;
            }
        }
        EmMgr.destroy(best);
        done++;
    }
#if defined(RE4DC_ALIVE_CAP_ON) && RE4DC_ALIVE_CAP_ON
    return done + dropped;
#else
    return done;
#endif
}

// PS2 EmFarDeleteNoWrap(keep, offscreen): the list entry's alive bit is cleared too.
static inline int re4dc_EmFarDeleteNoWrap(int keep, int offscreen)
{
    return re4dc_emFarDeleteImpl(keep, offscreen, 1);
}

// PS2 EmFarDelete(keep, offscreen): type 0x1A kept, the list entry left alone.
static inline int re4dc_EmFarDelete(int keep, int offscreen)
{
    return re4dc_emFarDeleteImpl(keep, offscreen, 0);
}

#endif
