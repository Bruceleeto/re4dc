// EL_CENSUS (game30.mk; lane el 2026-10-05; diagnostic, measurement builds only, read-only): the census that bounds
// exact reuse in the enemies' logic over global ticks [EL_CENSUS_FROM, EL_CENSUS_TO] (pG->Frame_cnt, the hw model's
// frame numbers). Its hooks only read game state; every table is its own.
//  - Line queries (cSatMgr::hitCheck2): the complete inputs (manager, both ends' bits, flag, mask, seCk and every live
//    piece's identity, data pointers and matrices) hashed into a key; each query is new, a repeat of an earlier query
//    of the same tick, of the previous tick, or of one 2..8 ticks back. A repeat's stored outputs (return, hit point,
//    normal pointer, winning piece, the moved end) are compared ("mis": a key that missed an input). The work counters
//    (pieces, leaves, listed / tested / box-overlapping / plane-crossing / surviving polygons, hits) say what each
//    query cost and what an order-preserving index could leave out. Grouped by the caller chain (hitCheck2's return
//    address, then hitCheck / getFloor's, rckLineHitCheck's, getNearPoint's) and the enemy whose move() runs.
//  - getNearPoint: (pos bits, mode, mask) + the same world key: repeats as above, grouped by caller.
//  - Skeletons: after each emMove'd unit's move(), a hash of its motion work, coordinates and every part's pose,
//    local and world matrices; "same" = equal to its hash one tick earlier (nothing in the skeleton changed).
//  - Part-world passes (cModel::partsWorldCalc): a hash of everything the pass reads (the model's matrix and scale,
//    every part's local matrix, scale, parent, the skip / addRot flags and addRot); "redundant" = equal to the
//    model's previous pass with no pass of that model in between changing it (same tick or the previous tick).
// One summary per class at the first hook after EL_CENSUS_TO ("ELC" lines).
#include "types.h"
#include "global.h"
#include "atari.h"
#include "model.h"
#include "em.h"
#include "el_census.h"

extern "C" void re4dc_log(const char* fmt, ...);
#if defined(RE4DC_SKEL_FTRV) && RE4DC_SKEL_FTRV
extern "C" int re4dc_skel_scope;   // model.cpp: inside a Ganado's update
#endif

#ifndef RE4DC_EL_CENSUS_FROM
#define RE4DC_EL_CENSUS_FROM 2300
#endif
#ifndef RE4DC_EL_CENSUS_TO
#define RE4DC_EL_CENSUS_TO 2379
#endif

extern "C" {
u32 re4dc_elc_ra1;
u32 re4dc_elc_ra2;
u32 re4dc_elc_ra3;
void* re4dc_elc_em;
u32 re4dc_elc_w[12];
}

namespace {

struct H2 {
    u32 a;
    u32 b;
};
inline void mix(H2& h, u32 w)
{
    h.a = (h.a ^ w) * 16777619u;
    h.b += w * 0x9E3779B1u;
    h.b = (h.b << 13) | (h.b >> 19);
    h.b = h.b * 5u + 0xE6546B64u;
}
inline u32 fb(f32 f)
{
    u32 u;
    __builtin_memcpy(&u, &f, 4);
    return u;
}
inline void mixv(H2& h, const Vec* v)
{
    mix(h, fb(v->x));
    mix(h, fb(v->y));
    mix(h, fb(v->z));
}
inline void mixw(H2& h, const void* p, int n)
{
    const u32* w = (const u32*) p;
    for (int i = 0; i < n; i++) {
        mix(h, w[i]);
    }
}
inline H2 seed(u32 s)
{
    H2 h = {0x811C9DC5u ^ s, 0x2545F491u + s};
    return h;
}

const u32 FROM = RE4DC_EL_CENSUS_FROM;
const u32 TO = RE4DC_EL_CENSUS_TO;
enum { NT = 9, NE = 256, NG = 32 };

struct Ent {
    u32 k1;
    u32 k2;
    u32 out;
};
Ent lqTab[NT][NE];
Ent gnTab[NT][NG];
u32 lqFull, gnFull;
int ring;                  // index of the current tick's tables
u32 curTick = 0xFFFFFFFFu;
int printed;

void clearSlot(int s)
{
    __builtin_memset(lqTab[s], 0, sizeof(lqTab[s]));
    __builtin_memset(gnTab[s], 0, sizeof(gnTab[s]));
}

void printAll();

// Ticks advance with pG->Frame_cnt; a skipped tick clears its slot, a counter that went back clears all.
inline u32 tick()
{
    const u32 t = pG->Frame_cnt;
    if (t != curTick) {
        if (curTick != 0xFFFFFFFFu && t > curTick && t - curTick < NT) {
            for (u32 s = curTick; s < t; s++) {
                ring = (ring + 1) % NT;
                clearSlot(ring);
            }
        } else {
            for (int s = 0; s < NT; s++) {
                clearSlot(s);
            }
            ring = 0;
        }
        curTick = t;
        if (!printed && t > TO) {
            printed = 1;
            printAll();
        }
    }
    return t;
}
inline int inWin(u32 t)
{
    return t >= FROM && t <= TO;
}
inline int tracked(u32 t)
{
    return t + 8 >= FROM && t <= TO;
}

// 0 new, 1 this tick, 2 previous tick, 3 two to eight ticks back; *same = the stored output equals `out`.
// The key goes into this tick's table when it is not there yet.
template <int N>
int classify(Ent (*tab)[N], u32* full, u32 k1, u32 k2, u32 out, int* same)
{
    k1 |= 1;
    int cls = 0;
    *same = 1;
    for (int age = 0; age < NT && !cls; age++) {
        Ent* t = tab[(ring + NT - age) % NT];
        for (u32 j = 0, i = k2 % N; j < (u32) N; j++, i = (i + 1) % N) {
            if (t[i].k1 == 0) {
                break;
            }
            if (t[i].k1 == k1 && t[i].k2 == k2) {
                cls = age == 0 ? 1 : age == 1 ? 2 : 3;
                *same = t[i].out == out;
                break;
            }
        }
    }
    if (cls != 1) {
        Ent* t = tab[ring];
        u32 j = 0, i = k2 % N;
        for (; j < (u32) N; j++, i = (i + 1) % N) {
            if (t[i].k1 == 0) {
                t[i].k1 = k1;
                t[i].k2 = k2;
                t[i].out = out;
                break;
            }
        }
        if (j == (u32) N) {
            ++*full;
        }
    }
    return cls;
}

// ---- line queries ----
enum { NCTX = 96, NWR = 4 };
const int wrField[NWR] = {ELC_W_ALIVE, ELC_W_LEAVES, ELC_W_LISTED, ELC_W_TESTED};
struct LqCtx {
    u32 ra0, ra1, ra2, ra3;
    u8 emId;
    u8 emLive;
    u8 pad[2];
    u32 n;
    u32 cls[4];
    u32 mis;
    u32 w[ELC_W_N];
    u32 wr[3][NWR];
    u32 len;              // summed segment length (units)
};
LqCtx lqCtx[NCTX];
int nLqCtx;
u32 lqCtxOver;
struct {
    int on;
    int ci;
    u32 k1;
    u32 k2;
    u32 t;
    f32 len;
} lq;

int findCtx(u32 ra0)
{
    const cEm* em = (const cEm*) re4dc_elc_em;
    const u8 id = em ? em->id : 0xFF;
    const u8 live = em ? (em->hp > 0) : 0;
    for (int i = 0; i < nLqCtx; i++) {
        const LqCtx& c = lqCtx[i];
        if (c.ra0 == ra0 && c.ra1 == re4dc_elc_ra1 && c.ra2 == re4dc_elc_ra2 && c.ra3 == re4dc_elc_ra3 && c.emId == id &&
            c.emLive == live) {
            return i;
        }
    }
    if (nLqCtx == NCTX) {
        ++lqCtxOver;
        return -1;
    }
    LqCtx& c = lqCtx[nLqCtx];
    c.ra0 = ra0;
    c.ra1 = re4dc_elc_ra1;
    c.ra2 = re4dc_elc_ra2;
    c.ra3 = re4dc_elc_ra3;
    c.emId = id;
    c.emLive = live;
    return nLqCtx++;
}

// The world a query reads: every live piece of the manager (identity, data pointers, matrices).
H2 worldKey(cSatMgr* mgr, u32 s)
{
    H2 w = seed(s);
    mix(w, (u32) mgr);
    mix(w, mgr->nArray);
    for (u32 i = 0; i < mgr->nArray; i++) {
        cSat* sat = (cSat*) ((u8*) mgr->pArray + mgr->size * i);
        if (!sat->isAlive()) {
            continue;
        }
        mix(w, i);
        mix(w, (u32) sat->block_p);
        mix(w, (u32) sat->vtx);
        mix(w, (u32) sat->norm_p);
        mix(w, (u32) sat->edge_p);
        mix(w, (u32) sat->poly_p);
        mix(w, sat->polygon_num);
        mixw(w, sat->imat, 12);
        mixw(w, sat->mat, 12);
    }
    return w;
}

// ---- getNearPoint ----
enum { NGC = 24 };
struct GnCtx {
    u32 ra;
    u8 emId;
    u8 pad[3];
    u32 n;
    u32 cls[4];
    u32 mis;
    u32 lq;              // line queries made inside
    u32 lqr[3];          // of the repeats, by class
};
GnCtx gnCtx[NGC];
int nGnCtx;
struct {
    int on;
    int ci;
    u32 k1;
    u32 k2;
    u32 t;
    u32 lq0;
} gn;
u32 lqCount;   // every line query (getNearPoint's share = the difference)

// ---- skeletons and part-world passes ----
enum { NEM = 64, NCLS = 32 };
struct EmRec {
    const void* em;
    u32 h1;
    u32 h2;
    u32 t;
};
EmRec emRec[NEM];
struct SkCls {
    u8 id;
    u8 pad[3];           // pad[0]: alive (hp > 0)
    u32 n;
    u32 same;
    u32 parts;
    u32 partsSame;
};
SkCls skCls[NCLS];
int nSkCls;
struct PwRec {
    const void* m;
    u32 h1;
    u32 h2;
    u32 t;
};
PwRec pwRec[NEM * 2];
struct PwCls {
    u8 id;
    u8 pad[3];
    u32 n;
    u32 redTick;     // equal to the model's previous pass in the same tick
    u32 redPrev;     // equal to its pass of the previous tick (no pass between)
    u32 parts;
    u32 partsRed;
};
PwCls pwCls[NCLS];
int nPwCls;

template <class C>
C* findCls(C* tab, int* n, u8 id, u8 live)
{
    for (int i = 0; i < *n; i++) {
        if (tab[i].id == id && (int) live == (int) tab[i].pad[0]) {
            return &tab[i];
        }
    }
    if (*n == NCLS) {
        return 0;
    }
    C* c = &tab[(*n)++];
    c->id = id;
    c->pad[0] = live;
    return c;
}

void printAll()
{
    re4dc_log("ELC begin from=%u to=%u lqctx=%d over=%u lqfull=%u gnfull=%u\n", FROM, TO, nLqCtx, lqCtxOver, lqFull, gnFull);
    for (int i = 0; i < nLqCtx; i++) {
        const LqCtx& c = lqCtx[i];
        re4dc_log("ELC lq ra0=%08x ra1=%08x ra2=%08x ra3=%08x em=%02x live=%u n=%u new=%u same=%u prev=%u r8=%u mis=%u "
                  "len=%u\n",
                  c.ra0, c.ra1, c.ra2, c.ra3, c.emId, c.emLive, c.n, c.cls[0], c.cls[1], c.cls[2], c.cls[3], c.mis, c.len);
        re4dc_log("ELC lw ra0=%08x ra1=%08x ra2=%08x ra3=%08x em=%02x live=%u alive=%u walked=%u leaves=%u listed=%u "
                  "tested=%u axz=%u axyz=%u plane=%u surv=%u hits=%u taken=%u\n",
                  c.ra0, c.ra1, c.ra2, c.ra3, c.emId, c.emLive, c.w[ELC_W_ALIVE], c.w[ELC_W_WALKED], c.w[ELC_W_LEAVES],
                  c.w[ELC_W_LISTED], c.w[ELC_W_TESTED], c.w[ELC_W_AABBXZ], c.w[ELC_W_AABBXYZ], c.w[ELC_W_PLANE],
                  c.w[ELC_W_SURV], c.w[ELC_W_HITS], c.w[ELC_W_TAKEN]);
        re4dc_log("ELC lr ra0=%08x ra1=%08x ra2=%08x ra3=%08x em=%02x live=%u same=%u,%u,%u,%u prev=%u,%u,%u,%u "
                  "r8=%u,%u,%u,%u\n",
                  c.ra0, c.ra1, c.ra2, c.ra3, c.emId, c.emLive, c.wr[0][0], c.wr[0][1], c.wr[0][2], c.wr[0][3], c.wr[1][0],
                  c.wr[1][1], c.wr[1][2], c.wr[1][3], c.wr[2][0], c.wr[2][1], c.wr[2][2], c.wr[2][3]);
    }
    for (int i = 0; i < nGnCtx; i++) {
        const GnCtx& c = gnCtx[i];
        re4dc_log("ELC gn ra=%08x em=%02x n=%u new=%u same=%u prev=%u r8=%u mis=%u lq=%u lqr=%u,%u,%u\n", c.ra, c.emId,
                  c.n, c.cls[0], c.cls[1], c.cls[2], c.cls[3], c.mis, c.lq, c.lqr[0], c.lqr[1], c.lqr[2]);
    }
    for (int i = 0; i < nSkCls; i++) {
        const SkCls& c = skCls[i];
        re4dc_log("ELC sk id=%02x live=%u n=%u same=%u parts=%u parts_same=%u\n", c.id, c.pad[0], c.n, c.same, c.parts,
                  c.partsSame);
    }
    for (int i = 0; i < nPwCls; i++) {
        const PwCls& c = pwCls[i];
        re4dc_log("ELC pw id=%02x n=%u red_tick=%u red_prev=%u parts=%u parts_red=%u\n", c.id, c.n, c.redTick, c.redPrev,
                  c.parts, c.partsRed);
    }
    re4dc_log("ELC end\n");
}

}   // namespace

void elcQueryBegin(cSatMgr* mgr, Vec* pos0, Vec* pos1, int flag, int mask, int seCk, u32 ra0)
{
    const u32 t = tick();
    lq.on = tracked(t);
    for (int i = 0; i < ELC_W_N; i++) {
        re4dc_elc_w[i] = 0;
    }
    if (!lq.on) {
        return;
    }
    ++lqCount;
    H2 k = worldKey(mgr, 0x51);
    mixv(k, pos0);
    mixv(k, pos1);
    mix(k, (u32) flag);
    mix(k, (u32) mask);
    mix(k, (u32) seCk);
    lq.k1 = k.a;
    lq.k2 = k.b;
    lq.t = t;
    lq.ci = inWin(t) ? findCtx(ra0) : -1;
    const f32 dx = pos1->x - pos0->x;
    const f32 dy = pos1->y - pos0->y;
    const f32 dz = pos1->z - pos0->z;
    lq.len = __builtin_sqrtf(dx * dx + dy * dy + dz * dz);
}

void elcQueryEnd(int ret, const Vec* hit, u32 pn, const Vec* pos1, const void* bypass)
{
    if (!lq.on) {
        return;
    }
    lq.on = 0;
    H2 o = seed(0x77);
    mix(o, (u32) ret);
    mixv(o, hit);
    mix(o, ret ? pn : 0);
    mix(o, ret ? (u32) bypass : 0);   // hitCheck reads the winning piece only after a hit
    mixv(o, pos1);
    int same;
    const int cls = classify<NE>(lqTab, &lqFull, lq.k1, lq.k2, o.a ^ o.b, &same);
    if (lq.ci < 0) {
        return;
    }
    LqCtx& c = lqCtx[lq.ci];
    c.n++;
    c.cls[cls]++;
    if (cls && !same) {
        c.mis++;
    }
    for (int i = 0; i < ELC_W_N; i++) {
        c.w[i] += re4dc_elc_w[i];
    }
    if (cls) {
        for (int i = 0; i < NWR; i++) {
            c.wr[cls - 1][i] += re4dc_elc_w[wrField[i]];
        }
    }
    c.len += (u32) lq.len;
}

// Before the leaf kernel marks them: the untested polygons of one leaf chunk against the segment p0-p1 (piece space).
void elcLeafPolys(cSat* sat, const u16* idx, int n, const Vec* p0, const Vec* p1, const u8* bits)
{
    if (!lq.on) {
        return;
    }
    const f32 m = 1.0f;
    const f32 sx0 = (p0->x < p1->x ? p0->x : p1->x) - m, sx1 = (p0->x < p1->x ? p1->x : p0->x) + m;
    const f32 sy0 = (p0->y < p1->y ? p0->y : p1->y) - m, sy1 = (p0->y < p1->y ? p1->y : p0->y) + m;
    const f32 sz0 = (p0->z < p1->z ? p0->z : p1->z) - m, sz1 = (p0->z < p1->z ? p1->z : p0->z) + m;
    re4dc_elc_w[ELC_W_LISTED] += n;
    for (int i = 0; i < n; i++) {
        const u32 no = idx[i];
        if (bits[no >> 3] & (1 << (no & 7))) {
            continue;
        }
        int dup = 0;
        for (int j = 0; j < i; j++) {
            dup |= idx[j] == no;
        }
        if (dup) {
            continue;
        }
        re4dc_elc_w[ELC_W_TESTED]++;
        const AtPoly* poly = &sat->poly_p[no];
        const Vec* a = &sat->vtx[poly->v[0]];
        const Vec* b = &sat->vtx[poly->v[1]];
        const Vec* c = &sat->vtx[poly->v[2]];
        const f32 x0 = __builtin_fminf(a->x, __builtin_fminf(b->x, c->x)), x1 = __builtin_fmaxf(a->x, __builtin_fmaxf(b->x, c->x));
        const f32 y0 = __builtin_fminf(a->y, __builtin_fminf(b->y, c->y)), y1 = __builtin_fmaxf(a->y, __builtin_fmaxf(b->y, c->y));
        const f32 z0 = __builtin_fminf(a->z, __builtin_fminf(b->z, c->z)), z1 = __builtin_fmaxf(a->z, __builtin_fmaxf(b->z, c->z));
        const int xz = !(x1 < sx0 || x0 > sx1 || z1 < sz0 || z0 > sz1);
        re4dc_elc_w[ELC_W_AABBXZ] += xz;
        re4dc_elc_w[ELC_W_AABBXYZ] += xz && !(y1 < sy0 || y0 > sy1);
        const Vec* nr = &sat->norm_p[poly->n];
        const f32 dp0 = (p0->x - a->x) * nr->x + (p0->y - a->y) * nr->y + (p0->z - a->z) * nr->z;
        const f32 dp1 = (p1->x - a->x) * nr->x + (p1->y - a->y) * nr->y + (p1->z - a->z) * nr->z;
        re4dc_elc_w[ELC_W_PLANE] += !(dp0 * dp1 > 0.0f);
    }
}

void elcGnpBegin(const Vec* pos, int mode, int mask, u32 ra)
{
    const u32 t = tick();
    gn.on = tracked(t);
    if (!gn.on) {
        return;
    }
    H2 k = worldKey(&SatMgr, 0x93);
    mixv(k, pos);
    mix(k, (u32) mode);
    mix(k, (u32) mask);
    mix(k, (u32) pG->Rtp);
    gn.k1 = k.a;
    gn.k2 = k.b;
    gn.t = t;
    gn.lq0 = lqCount;
    gn.ci = -1;
    if (inWin(t)) {
        const cEm* em = (const cEm*) re4dc_elc_em;
        const u8 id = em ? em->id : 0xFF;
        for (int i = 0; i < nGnCtx; i++) {
            if (gnCtx[i].ra == ra && gnCtx[i].emId == id) {
                gn.ci = i;
                break;
            }
        }
        if (gn.ci < 0 && nGnCtx < NGC) {
            gnCtx[nGnCtx].ra = ra;
            gnCtx[nGnCtx].emId = id;
            gn.ci = nGnCtx++;
        }
    }
}

void elcGnpEnd(int ret)
{
    if (!gn.on) {
        return;
    }
    gn.on = 0;
    int same;
    const int cls = classify<NG>(gnTab, &gnFull, gn.k1, gn.k2, (u32) ret, &same);
    if (gn.ci < 0) {
        return;
    }
    GnCtx& c = gnCtx[gn.ci];
    const u32 nlq = lqCount - gn.lq0;
    c.n++;
    c.cls[cls]++;
    if (cls && !same) {
        c.mis++;
    }
    c.lq += nlq;
    if (cls) {
        c.lqr[cls - 1] += nlq;
    }
}

void elcEmAfterMove(cModel* m)
{
    const u32 t = tick();
    if (!tracked(t)) {
        return;
    }
    H2 h = seed(0x31);
    mixw(h, &m->Motion, sizeof(MotionWork) / 4);
    mixv(h, &m->pos);
    mixv(h, &m->ang);
    mixv(h, &m->scale);
    mixw(h, m->mat, 12);
    u32 np = 0;
    for (cParts* p = m->pList; p && np < 256; p = p->pList, np++) {
        mixv(h, &p->pos);
        mixv(h, &p->ang);
        mixv(h, &p->scale);
        mixw(h, p->l_mat, 12);
        mixw(h, p->mat, 12);
        mixv(h, &p->world);
    }
    int slot = -1;
    for (int i = 0; i < NEM; i++) {
        if (emRec[i].em == m) {
            slot = i;
            break;
        }
        if (slot < 0 && (emRec[i].em == 0 || emRec[i].t + 16 < t)) {
            slot = i;
        }
    }
    if (slot < 0) {
        return;
    }
    EmRec& r = emRec[slot];
    const int same = r.em == m && r.t + 1 == t && r.h1 == h.a && r.h2 == h.b;
    r.em = m;
    r.h1 = h.a;
    r.h2 = h.b;
    r.t = t;
    if (!inWin(t)) {
        return;
    }
    const cEm* em = (const cEm*) m;
    SkCls* c = findCls(skCls, &nSkCls, m->id, (u8) (em->hp > 0));
    if (!c) {
        return;
    }
    c->n++;
    c->parts += np;
    if (same) {
        c->same++;
        c->partsSame += np;
    }
}

void elcPartsWorld(cModel* m)
{
    const u32 t = tick();
    if (!tracked(t)) {
        return;
    }
    H2 h = seed(0x45);
#if defined(RE4DC_SKEL_FTRV) && RE4DC_SKEL_FTRV
    mix(h, (u32) (re4dc_skel_scope != 0));   // the FTRV pass or the library one
#endif
    mixw(h, m->mat, 12);
    mixv(h, &m->scale);
    u32 np = 0;
    for (cParts* p = m->pList; p && np < 256; p = p->pList, np++) {
        const u32 fl = p->motParts.flags & 0x40000002u;
        mix(h, (u32) p->pParent);
        mix(h, fl);
        mixw(h, p->l_mat, 12);
        mixv(h, &p->scale);
        if (fl & 0x40000000u) {
            mixv(h, &p->addRot);
        }
    }
    int slot = -1;
    for (int i = 0; i < NEM * 2; i++) {
        if (pwRec[i].m == m) {
            slot = i;
            break;
        }
        if (slot < 0 && (pwRec[i].m == 0 || pwRec[i].t + 16 < t)) {
            slot = i;
        }
    }
    if (slot < 0) {
        return;
    }
    PwRec& r = pwRec[slot];
    const int eq = r.m == m && r.h1 == h.a && r.h2 == h.b;
    const int redTick = eq && r.t == t;
    const int redPrev = eq && r.t + 1 == t;
    r.m = m;
    r.h1 = h.a;
    r.h2 = h.b;
    r.t = t;
    if (!inWin(t)) {
        return;
    }
    PwCls* c = findCls(pwCls, &nPwCls, m->id, 0);
    if (!c) {
        return;
    }
    c->n++;
    c->parts += np;
    if (redTick) {
        c->redTick++;
        c->partsRed += np;
    } else if (redPrev) {
        c->redPrev++;
        c->partsRed += np;
    }
}
