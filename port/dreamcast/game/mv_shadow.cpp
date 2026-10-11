// mv_shadow.cpp -- MV_SHADOWS (game30.mk; Phase 2 item C2, render only, default off): character shadows as PVR
// cheap-shadow modifier volumes (KOS examples cheap_shadow and modifier_volume_zclip are the templates).
//
// Casters: Leon (pPL) and the live Ganados (EmMgr's alive list, ids 0x10..0x20, be_flag & 0x201 == 1, as act_cap.cpp
// counts them) within MV_RANGE_M metres of the camera, nearest first, at most MV_MAX. Each caster gets a closed prism:
// a MV_SIDES-gon of radius MV_RADIUS (mm) around its feet, from MV_TOP mm above the feet straight down to MV_DEPTH mm
// below them, so the ground, slopes, steps and room objects under the character fall inside it.
// Receivers: every MeshDraw part (room scenery and objects, the PS2 world) carries the cheap-shadow modifier bit on
// its opaque header (native_static.cpp / native_ui.cpp); characters do not, so the volume never darkens a body.
// Inside a volume a receiver's colour is scaled by MV_SCALE % (pvr_set_shadow_scale).
// Near plane: a prism that crosses the camera's near plane is clipped against it in view space and closed with a cap
// polygon on the plane (the zclip example's rule: an open volume would invert the inside test on screen).
// Volumes go into the opaque modifier volume list at the end of a presented scene (native_ui.cpp stream_close ->
// re4dc_mv_emit -> re4dc_ui_mv_send): per caster one header (OTHER_POLY), its triangles, a header INCLUDE_LAST_POLY and
// the last triangle. Reads game state only (positions, the camera matrix); writes nothing the game reads, so the
// logic trace is unchanged.
#include "global.h"
#include "player.h"
#include "em.h"
#include "camera.h"
#include "re4dc_platform.h"
#include "re4dc_screen.h"
#include <dc/pvr.h>
#include <string.h>

#ifndef RE4DC_MV_SIDES
#define RE4DC_MV_SIDES 8
#endif
#ifndef RE4DC_MV_RADIUS
#define RE4DC_MV_RADIUS 420
#endif
#ifndef RE4DC_MV_TOP
#define RE4DC_MV_TOP 250
#endif
#ifndef RE4DC_MV_DEPTH
#define RE4DC_MV_DEPTH 1200
#endif
#ifndef RE4DC_MV_RANGE_M
#define RE4DC_MV_RANGE_M 15
#endif
#ifndef RE4DC_MV_MAX
#define RE4DC_MV_MAX 12
#endif

extern "C" {
extern float re4dc_mv_projection[7], re4dc_mv_viewport[6];   // native_static.cpp: the frame's receiver camera
extern unsigned re4dc_mv_camera_frame;
int re4dc_ui_mv_send(const void* data, unsigned bytes);       // native_ui.cpp
void re4dc_ui_mv_stats(unsigned* sends, unsigned* bytes, unsigned* scenes, unsigned* receivers);
void re4dc_log(const char* fmt, ...);
}

namespace {
constexpr int kSides = RE4DC_MV_SIDES;
static_assert(kSides >= 3 && kSides <= 16, "MV_SIDES 3..16");
constexpr int kMaxPoly = kSides + 4;          // a clipped face gains at most one corner; the cap at most kSides + 2
constexpr int kMaxTris = 4 * kSides + 8;
constexpr int kMaxCasters = RE4DC_MV_MAX;
constexpr float kRange2 = (float) (RE4DC_MV_RANGE_M * 1000) * (float) (RE4DC_MV_RANGE_M * 1000);

struct V3 { float x, y, z; };
struct Caster { float x, y, z, r, d2; };

alignas(32) unsigned char g_buf[64 + kMaxTris * 64];
pvr_mod_hdr_t g_hdr_other, g_hdr_last;
bool g_hdr_ready;
unsigned g_frames, g_casters, g_tris, g_clipped, g_skipped, g_failed;

// The receiver camera: GX view matrix (pG->Cam.v_mat, as coarse.cpp re4dc_coarse_source_camera) and the
// perspective of the frame's first receiver part (native_static.cpp MeshDraw::bind).
float M[3][4], P[7], VP[6], g_near;

inline V3 to_view(float x, float y, float z)
{
    V3 v;
    v.x = M[0][0] * x + M[0][1] * y + M[0][2] * z + M[0][3];
    v.y = M[1][0] * x + M[1][1] * y + M[1][2] * z + M[1][3];
    v.z = M[2][0] * x + M[2][1] * y + M[2][2] * z + M[2][3];
    return v;
}
// native_static.cpp's projection (MeshDraw::project): screen x, y and 1/w for a view-space point with -z > 0.
inline void project(const V3& v, float* o)
{
    const float inv = 1.0f / (-v.z);
    o[0] = (VP[2] * .5f * (P[1] * v.x + P[2] * v.z) * inv + VP[0] + VP[2] * .5f) * RE4DC_SCREEN_WF / VP[2];
    o[1] = (-VP[3] * .5f * (P[3] * v.y + P[4] * v.z) * inv + VP[1] + VP[3] * .5f) * RE4DC_SCREEN_HF / VP[3];
    o[2] = inv;
}

struct Builder {
    unsigned tris = 0;
    pvr_modifier_vol_t* t() { return reinterpret_cast<pvr_modifier_vol_t*>(g_buf + 32 + tris * 64); }
    void tri(const V3& a, const V3& b, const V3& c)
    {
        if (tris >= (unsigned) kMaxTris) return;
        float pa[3], pb[3], pc[3];
        project(a, pa); project(b, pb); project(c, pc);
        pvr_modifier_vol_t* m = t();
        m->flags = PVR_CMD_VERTEX_EOL;
        m->ax = pa[0]; m->ay = pa[1]; m->az = pa[2];
        m->bx = pb[0]; m->by = pb[1]; m->bz = pb[2];
        m->cx = pc[0]; m->cy = pc[1]; m->cz = pc[2];
        m->d1 = m->d2 = m->d3 = m->d4 = m->d5 = m->d6 = 0;
        ++tris;
    }
    void fan(const V3* p, int n) { for (int i = 1; i + 1 < n; ++i) tri(p[0], p[i], p[i + 1]); }
    // Sends header, triangles 0..n-2, the INCLUDE_LAST_POLY header and triangle n-1 (the last one moved after it).
    bool send()
    {
        if (tris < 4) return false;
        unsigned char* last = g_buf + 32 + (tris - 1) * 64;
        alignas(32) unsigned char keep[64];
        memcpy(keep, last, 64);
        memcpy(g_buf, &g_hdr_other, 32);
        memcpy(last, &g_hdr_last, 32);
        memcpy(last + 32, keep, 64);
        return re4dc_ui_mv_send(g_buf, 32 + (tris - 1) * 64 + 32 + 64) != 0;
    }
};

// Clips the convex polygon p (n corners, view space) to -z >= near; the corners made on the plane go to cut.
int clip_poly(const V3* p, int n, V3* out, V3* cut, int& ncut)
{
    int m = 0;
    for (int i = 0; i < n; ++i) {
        const V3& a = p[i];
        const V3& b = p[(i + 1) % n];
        const float da = -a.z - g_near, db = -b.z - g_near;
        if (da >= 0) out[m++] = a;
        if ((da >= 0) != (db >= 0)) {
            const float s = da / (da - db);
            V3 q{a.x + (b.x - a.x) * s, a.y + (b.y - a.y) * s, -g_near};
            out[m++] = q;
            if (ncut < 2 * kMaxPoly) cut[ncut++] = q;
        }
        if (m >= kMaxPoly) break;
    }
    return m;
}

void volume(const Caster& c)
{
    V3 top[kSides], bot[kSides];
    for (int i = 0; i < kSides; ++i) {
        const float a = 6.2831853f * (float) i / (float) kSides;
        const float x = c.x + c.r * __builtin_cosf(a), z = c.z + c.r * __builtin_sinf(a);
        top[i] = to_view(x, c.y + (float) RE4DC_MV_TOP, z);
        bot[i] = to_view(x, c.y - (float) RE4DC_MV_DEPTH, z);
    }
    int behind = 0, l = 0, r = 0, u = 0, d = 0;
    for (int k = 0; k < 2 * kSides; ++k) {
        const V3& v = k < kSides ? top[k] : bot[k - kSides];
        if (-v.z < g_near) { ++behind; continue; }
        float s[3];
        project(v, s);
        l += s[0] < 0; r += s[0] > RE4DC_SCREEN_WF; u += s[1] < 0; d += s[1] > RE4DC_SCREEN_HF;
    }
    if (behind == 2 * kSides) { ++g_skipped; return; }
    if (!behind && (l == 2 * kSides || r == 2 * kSides || u == 2 * kSides || d == 2 * kSides)) { ++g_skipped; return; }
    Builder b;
    // Faces: top and bottom polygons, then the side quads (winding is irrelevant: culling none).
    V3 face[kMaxPoly], clipped[kMaxPoly + 2], cut[2 * kMaxPoly];
    int ncut = 0;
    for (int f = 0; f < kSides + 2; ++f) {
        int n;
        if (f == 0) { for (int i = 0; i < kSides; ++i) face[i] = top[i]; n = kSides; }
        else if (f == 1) { for (int i = 0; i < kSides; ++i) face[i] = bot[kSides - 1 - i]; n = kSides; }
        else {
            const int i = f - 2, j = (i + 1) % kSides;
            face[0] = top[i]; face[1] = bot[i]; face[2] = bot[j]; face[3] = top[j]; n = 4;
        }
        if (!behind) { b.fan(face, n); continue; }
        const int m = clip_poly(face, n, clipped, cut, ncut);
        if (m >= 3) b.fan(clipped, m);
    }
    if (behind) {
        ++g_clipped;
        // The cap: the cut corners on the near plane (each appears twice), ordered by angle around their centre.
        V3 cap[kMaxPoly];
        int nc = 0;
        for (int i = 0; i < ncut && nc < kMaxPoly; ++i) {
            bool dup = false;
            for (int j = 0; j < nc; ++j)
                if (fabsf(cap[j].x - cut[i].x) < 0.5f && fabsf(cap[j].y - cut[i].y) < 0.5f) { dup = true; break; }
            if (!dup) cap[nc++] = cut[i];
        }
        if (nc >= 3) {
            float cx = 0, cy = 0;
            for (int i = 0; i < nc; ++i) { cx += cap[i].x; cy += cap[i].y; }
            cx /= (float) nc; cy /= (float) nc;
            float ang[kMaxPoly];
            for (int i = 0; i < nc; ++i) ang[i] = __builtin_atan2f(cap[i].y - cy, cap[i].x - cx);
            for (int i = 1; i < nc; ++i)
                for (int j = i; j > 0 && ang[j] < ang[j - 1]; --j) {
                    const float ta = ang[j]; ang[j] = ang[j - 1]; ang[j - 1] = ta;
                    const V3 tv = cap[j]; cap[j] = cap[j - 1]; cap[j - 1] = tv;
                }
            b.fan(cap, nc);
        }
    }
    if (!b.send()) { ++g_failed; return; }
    ++g_casters;
    g_tris += b.tris;
}

void add(Caster* list, int& n, float x, float y, float z, float r, const V3& cam)
{
    const float dx = x - cam.x, dz = z - cam.z, d2 = dx * dx + dz * dz;
    if (d2 > kRange2) return;
    Caster c{x, y, z, r, d2};
    if (n < kMaxCasters) { list[n++] = c; return; }
    int far = 0;
    for (int i = 1; i < n; ++i) if (list[i].d2 > list[far].d2) far = i;
    if (list[far].d2 > d2) list[far] = c;
}
}  // namespace

// native_ui.cpp stream_close, a presented scene with every other list closed.
extern "C" void re4dc_mv_emit(unsigned frame)
{
    if (!pG || re4dc_mv_camera_frame != frame) return;   // no receiver drew with a perspective camera this frame
    memcpy(M, &pG->Cam.v_mat[0][0], sizeof(M));
    memcpy(P, re4dc_mv_projection, sizeof(P));
    memcpy(VP, re4dc_mv_viewport, sizeof(VP));
    g_near = P[6] / (P[5] - 1.0f);
    if (!(g_near > 0) || !(VP[2] > 0) || !(VP[3] > 0)) return;
    g_near *= 1.01f;
    if (!g_hdr_ready) {
        pvr_mod_compile(&g_hdr_other, PVR_LIST_OP_MOD, PVR_MODIFIER_OTHER_POLY, PVR_CULLING_NONE);
        pvr_mod_compile(&g_hdr_last, PVR_LIST_OP_MOD, PVR_MODIFIER_INCLUDE_LAST_POLY, PVR_CULLING_NONE);
        g_hdr_ready = true;
    }
    // Camera position: -R^T t of the view matrix.
    const V3 cam{-(M[0][0] * M[0][3] + M[1][0] * M[1][3] + M[2][0] * M[2][3]),
                 -(M[0][1] * M[0][3] + M[1][1] * M[1][3] + M[2][1] * M[2][3]),
                 -(M[0][2] * M[0][3] + M[1][2] * M[1][3] + M[2][2] * M[2][3])};
    Caster list[kMaxCasters];
    int n = 0;
    if (pPL) add(list, n, pPL->pos.x, pPL->pos.y, pPL->pos.z, (float) RE4DC_MV_RADIUS * 0.9f, cam);
    for (cEm* e = EmMgr.pAlive; e; e = (cEm*) e->pNext) {
        if ((e->be_flag & 0x201) != 1 || e->id < 0x10 || e->id > 0x20) continue;
        add(list, n, e->pos.x, e->pos.y, e->pos.z, (float) RE4DC_MV_RADIUS, cam);
    }
    for (int i = 0; i < n; ++i) volume(list[i]);
    if (!(++g_frames % 600)) {
        unsigned sends, bytes, scenes, receivers;
        re4dc_ui_mv_stats(&sends, &bytes, &scenes, &receivers);
        re4dc_log("MV shadows: frames=%u casters=%u tris=%u clipped=%u skipped=%u failed=%u sends=%u bytes=%u scenes=%u receivers=%u near=%d\n",
                  g_frames, g_casters, g_tris, g_clipped, g_skipped, g_failed, sends, bytes, scenes, receivers, (int) g_near);
        if (n) {   // the nearest-listed caster: world feet, view-space feet and screen point
            const V3 v = to_view(list[0].x, list[0].y, list[0].z);
            float s[3] = {0, 0, 0};
            if (-v.z > g_near) project(v, s);
            re4dc_log("MV caster: world %d,%d,%d view %d,%d,%d screen %d,%d cam %d,%d,%d P %d,%d,%d,%d,%d,%d VP %d,%d,%d,%d\n",
                      (int) list[0].x, (int) list[0].y, (int) list[0].z, (int) v.x, (int) v.y, (int) v.z, (int) s[0], (int) s[1],
                      (int) cam.x, (int) cam.y, (int) cam.z, (int) (P[1] * 1000), (int) (P[2] * 1000), (int) (P[3] * 1000),
                      (int) (P[4] * 1000), (int) (P[5] * 1000), (int) P[6], (int) VP[0], (int) VP[1], (int) VP[2], (int) VP[3]);
        }
    }
}
