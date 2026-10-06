// EL_CENSUS (game30.mk; lane el 2026-10-05; diagnostic, measurement builds only, read-only): the hooks of
// el_census.cpp, the census that bounds exact reuse in the enemies' logic (line-query repeats with complete
// inputs, candidate polygons per line query, getNearPoint repeats, unchanged skeletons, redundant part-world
// passes). Every hook only reads game state and writes the census's own tables.
#ifndef EL_CENSUS_H
#define EL_CENSUS_H

#include "types.h"
#include "vec.h"

class cSatMgr;
class cSat;
class cModel;

#ifdef __cplusplus
extern "C" {
#endif
// caller context of the next line query: set by hitCheck / getFloor (ra1), rckLineHitCheck (ra2), getNearPoint (ra3)
extern u32 re4dc_elc_ra1;
extern u32 re4dc_elc_ra2;
extern u32 re4dc_elc_ra3;
extern void* re4dc_elc_em;   // the enemy whose move() runs (emMove)
// per-query work counters, counted by hitCheck2 / lineLeaf while a query runs
extern u32 re4dc_elc_w[12];
#ifdef __cplusplus
}
#endif

enum {
    ELC_W_ALIVE = 0,   // live pieces looked at
    ELC_W_WALKED,      // pieces with an overlapped leaf
    ELC_W_LEAVES,      // overlapped leaves
    ELC_W_LISTED,      // polygon indices in those leaves (flag subset)
    ELC_W_TESTED,      // polygons tested after the polyBit dedup
    ELC_W_AABBXZ,      // of those: the polygon's XZ box meets the segment's XZ box (margin 1)
    ELC_W_AABBXYZ,     // of those: the polygon's box meets the segment's box in x, y and z (margin 1)
    ELC_W_PLANE,       // of the tested: the plane test passes (dp0 * dp1 <= 0)
    ELC_W_SURV,        // survivors of the four tests (leaf kernel)
    ELC_W_HITS,        // survivors with an accepted attribute
    ELC_W_TAKEN,       // hits that became the nearest
    ELC_W_N
};

// Sets a caller-context slot for the scope and restores it after (nested queries keep their own).
struct ElcRa {
    u32* slot;
    u32 save;
    ElcRa(u32* s, u32 v) : slot(s), save(*s) { *s = v; }
    ~ElcRa() { *slot = save; }
};
#define ELC_RA(slot) ElcRa elcRaGuard(&(slot), (u32) __builtin_return_address(0))
#define ELC_W(f, v) (re4dc_elc_w[(f)] += (v))

void elcQueryBegin(cSatMgr* mgr, Vec* pos0, Vec* pos1, int flag, int mask, int seCk, u32 ra0);
void elcQueryEnd(int ret, const Vec* hit, u32 pn, const Vec* pos1, const void* bypass);
void elcLeafPolys(cSat* sat, const u16* idx, int n, const Vec* p0, const Vec* p1, const u8* bits);
void elcGnpBegin(const Vec* pos, int mode, int mask, u32 ra);
void elcGnpEnd(int ret);
void elcEmAfterMove(cModel* em);
void elcPartsWorld(cModel* m);

#endif
