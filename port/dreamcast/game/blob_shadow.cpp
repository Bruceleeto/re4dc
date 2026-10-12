// blob_shadow.cpp -- SHADOW_BLOB (game30.mk; render only, default off): soft dark ground blobs under the characters,
// the look of the game's own foot shadow sprites (foot_shadow.cpp DrawFootShadow, cut by FX_LEAN) without the type 4
// light it needs, as PS2-style round/oval darkening under Leon and every drawn Ganado/enemy.
//
// Casters: the game's own foot shadow set, read only: Leon (pPL) and the live characters of EmMgr's alive list
// (be_flag & 0x201 == 1) that carry a foot shadow table (cModel::pFootShadowTbl, as trans.cpp calls DrawFootShadow) or
// are Ganado ids 0x10..0x20 (as mv_shadow.cpp), drawn this frame (be_flag bit1, cModel::isTrans), within
// SHADOW_BLOB_RANGE_M metres of the camera, nearest SHADOW_BLOB_MAX first. The game's own off switches apply:
// Disp_flg 0x02000000, Shd_color 0xFF (and Shd_color scales the alpha as in DrawFootShadow), Status_flg[1] 0x100.
// Placement: the floor point DrawFootShadow uses (cEm::pos: the ground height the collision step already set this
// tick), lifted SHADOW_BLOB_LIFT mm; the blob stretches from the feet toward the root joint (pParts->world, x/z only)
// so a body lying down gets a long oval. No collision or floor query is made.
// Draw: per caster one untextured TR strip set (a flat inner disc at full alpha, a ring fading to zero), black, blend
// SRCALPHA/INVSRCALPHA, depth GEQUAL against the opaque depth, no depth write, no fog (alpha fades out with distance
// instead). Emitted in stream_close while the TR list is open and the world sorts per pixel (WORLD_AUTOSORT), so the
// blob sorts over the translucent ground layers (PS2_VERTEX_ALPHA soft layers) that hide the MV_SHADOWS volumes.
// Reads game state only; writes nothing the game reads, so the logic trace is unchanged.
#include "global.h"
#include "player.h"
#include "em.h"
#include "camera.h"
#include "re4dc_platform.h"
#include "re4dc_screen.h"
#include <dc/pvr.h>
#include <string.h>

#ifndef RE4DC_SHADOW_BLOB_SIDES
#define RE4DC_SHADOW_BLOB_SIDES 10
#endif
#ifndef RE4DC_SHADOW_BLOB_RADIUS
#define RE4DC_SHADOW_BLOB_RADIUS 400
#endif
#ifndef RE4DC_SHADOW_BLOB_ALPHA
#define RE4DC_SHADOW_BLOB_ALPHA 120
#endif
#ifndef RE4DC_SHADOW_BLOB_LIFT
#define RE4DC_SHADOW_BLOB_LIFT 25
#endif
#ifndef RE4DC_SHADOW_BLOB_RANGE_M
#define RE4DC_SHADOW_BLOB_RANGE_M 25
#endif
#ifndef RE4DC_SHADOW_BLOB_MAX
#define RE4DC_SHADOW_BLOB_MAX 12
#endif

extern "C" {
extern float re4dc_blob_projection[7], re4dc_blob_viewport[6];   // native_static.cpp: the frame's world camera
extern unsigned re4dc_blob_camera_frame;
int re4dc_ui_blob_send(const void* data, unsigned bytes);         // native_ui.cpp
void re4dc_log(const char* fmt, ...);
}

#if defined(RE4DC_SHADOW_BLOB_TOGGLE)
// SHADOW_BLOB_TOGGLE (test builds; watch discs): the blob strength at run time. pad.cpp X + D-pad left + START steps
// OFF -> alpha 120 r400 -> alpha 180 r400 -> alpha 180 r550 -> alpha 230 r550; native_static.cpp shows the name 3 s.
extern "C" unsigned re4dc_vi_retrace_count(void);
static unsigned s_blob_step = 1, s_blob_osd_until;
static const unsigned short kBlobAlpha[5] = {0, 120, 180, 180, 230}, kBlobRadius[5] = {0, 400, 400, 550, 550};
static const char* const kBlobText[5] = {"Shadows: off", "Shadows: alpha 120 r400", "Shadows: alpha 180 r400",
                                         "Shadows: alpha 180 r550", "Shadows: alpha 230 r550"};
extern "C" void re4dc_blob_cycle(void)
{
    s_blob_step = (s_blob_step + 1) % 5;
    s_blob_osd_until = re4dc_vi_retrace_count() + 180U;
    re4dc_log("blob shadows: %s\n", kBlobText[s_blob_step]);
}
extern "C" const char* re4dc_blob_osd_text(void)
{
    return (int) (s_blob_osd_until - re4dc_vi_retrace_count()) > 0 ? kBlobText[s_blob_step] : 0;
}
#define BLOB_ALPHA ((float) kBlobAlpha[s_blob_step])
#define BLOB_RADIUS ((float) kBlobRadius[s_blob_step])
#else
#define BLOB_ALPHA ((float) RE4DC_SHADOW_BLOB_ALPHA)
#define BLOB_RADIUS ((float) RE4DC_SHADOW_BLOB_RADIUS)
#endif

namespace {
constexpr int kSides = RE4DC_SHADOW_BLOB_SIDES;
static_assert(kSides >= 6 && kSides <= 16, "SHADOW_BLOB_SIDES 6..16");
constexpr int kMax = RE4DC_SHADOW_BLOB_MAX;
constexpr float kRange = (float) (RE4DC_SHADOW_BLOB_RANGE_M * 1000);
constexpr float kFade0 = kRange * 0.66f;                // alpha fades to zero from here to kRange
constexpr float kInner = 0.5f;                           // the full-alpha disc, a fraction of the radius
constexpr int kInnerVerts = kSides;                      // the inner disc as one strip
constexpr int kRingVerts = 2 * kSides + 2;               // the fading ring as one strip
constexpr int kVerts = kInnerVerts + kRingVerts;

struct V3 { float x, y, z; };
struct Caster { float x, y, z, ax, az, a, b, alpha, d2; };

alignas(32) unsigned char g_buf[32 + kVerts * 32];
pvr_poly_hdr_t g_hdr;
bool g_hdr_ready;
unsigned g_frames, g_casters, g_skipped, g_failed, g_seen, g_table, g_ids;
float M[3][4], P[7], VP[6], g_near;

inline V3 to_view(float x, float y, float z)
{
    V3 v;
    v.x = M[0][0] * x + M[0][1] * y + M[0][2] * z + M[0][3];
    v.y = M[1][0] * x + M[1][1] * y + M[1][2] * z + M[1][3];
    v.z = M[2][0] * x + M[2][1] * y + M[2][2] * z + M[2][3];
    return v;
}
// native_static.cpp's projection (MeshDraw::project), as mv_shadow.cpp.
inline void project(const V3& v, float* o)
{
    const float inv = 1.0f / (-v.z);
    o[0] = (VP[2] * .5f * (P[1] * v.x + P[2] * v.z) * inv + VP[0] + VP[2] * .5f) * RE4DC_SCREEN_WF / VP[2];
    o[1] = (-VP[3] * .5f * (P[3] * v.y + P[4] * v.z) * inv + VP[1] + VP[3] * .5f) * RE4DC_SCREEN_HF / VP[3];
    o[2] = inv;
}

void blob(const Caster& c)
{
    // Ellipse corners on the ground plane: axis (ax, az) of half-length a, the cross axis of half-length b.
    V3 in[kSides], out[kSides];
    float si[kSides][3], so[kSides][3];
    int l = 0, r = 0, u = 0, d = 0;
    const float y = c.y + (float) RE4DC_SHADOW_BLOB_LIFT;
    for (int i = 0; i < kSides; ++i) {
        const float t = 6.2831853f * (float) i / (float) kSides;
        const float ca = __builtin_cosf(t) * c.a, sb = __builtin_sinf(t) * c.b;
        const float ox = c.ax * ca - c.az * sb, oz = c.az * ca + c.ax * sb;
        out[i] = to_view(c.x + ox, y, c.z + oz);
        in[i] = to_view(c.x + ox * kInner, y, c.z + oz * kInner);
        if (-out[i].z < g_near || -in[i].z < g_near) { ++g_skipped; return; }   // crosses the near plane: skip
        project(out[i], so[i]);
        project(in[i], si[i]);
        l += so[i][0] < 0; r += so[i][0] > RE4DC_SCREEN_WF; u += so[i][1] < 0; d += so[i][1] > RE4DC_SCREEN_HF;
    }
#ifdef RE4DC_SHADOW_BLOB_DEBUG
    if (!(g_frames % 60))
        re4dc_log("blob dbg: w=%d,%d,%d s0=%d,%d,%f l=%d r=%d u=%d d=%d P=%f,%f,%f,%f,%f,%f,%f VP=%f,%f,%f,%f\n", (int) c.x, (int) c.y,
                  (int) c.z, (int) so[0][0], (int) so[0][1], so[0][2], l, r, u, d, P[0], P[1], P[2], P[3], P[4], P[5], P[6],
                  VP[0], VP[1], VP[2], VP[3]);
#endif
    if (l == kSides || r == kSides || u == kSides || d == kSides) { ++g_skipped; return; }
    const unsigned a = (unsigned) c.alpha;
    const unsigned full = a << 24, none = 0;
    pvr_vertex_t* v = reinterpret_cast<pvr_vertex_t*>(g_buf + 32);
    auto put = [&](const float* s, unsigned argb, bool eol) {
        v->flags = eol ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX;
        v->x = s[0]; v->y = s[1]; v->z = s[2]; v->u = v->v = 0; v->argb = argb; v->oargb = 0;
        ++v;
    };
    // Inner disc: the convex polygon as a zig-zag strip 0, 1, n-1, 2, n-2, ...
    {
        int lo = 1, hi = kSides - 1, k = 0;
        put(si[0], full, false);
        while (lo <= hi) {
            const int idx = (k++ & 1) ? hi-- : lo++;
            put(si[idx], full, lo > hi);
        }
    }
    // Ring: inner (full) / outer (zero) pairs all the way round, closed.
    for (int i = 0; i <= kSides; ++i) {
        const int j = i % kSides;
        put(si[j], full, false);
        put(so[j], none, i == kSides);
    }
    memcpy(g_buf, &g_hdr, 32);
    if (!re4dc_ui_blob_send(g_buf, 32 + kVerts * 32)) { ++g_failed; return; }
    ++g_casters;
}

void add(Caster* list, int& n, cEm* e, float radius, const V3& cam)
{
    if (e->Shd_color == 0xFF) return;
    const float dx = e->pos.x - cam.x, dz = e->pos.z - cam.z, d2 = dx * dx + dz * dz;
    if (d2 > kRange * kRange) return;
    // Only blobs near the view take a slot (the crowd behind the camera would fill the list otherwise).
    {
        const V3 v = to_view(e->pos.x, e->pos.y, e->pos.z);
        if (-v.z < g_near + radius) return;
        float s[3];
        project(v, s);
        const float m = radius * 2.5f * s[2] * RE4DC_SCREEN_WF;   // ~2.5 radii in pixels, plus a fixed margin
        if (s[0] < -m - 32 || s[0] > RE4DC_SCREEN_WF + m + 32 || s[1] < -m - 32 || s[1] > RE4DC_SCREEN_HF + m + 32) return;
    }
    // From the feet toward the root joint (x/z): the long axis of a body lying down.
    float ox = 0, oz = 0;
    if (e->pParts) { ox = e->pParts->world.x - e->pos.x; oz = e->pParts->world.z - e->pos.z; }
    float len = __builtin_sqrtf(ox * ox + oz * oz);
    if (len > 900.0f) { ox *= 900.0f / len; oz *= 900.0f / len; len = 900.0f; }
    Caster c;
    c.x = e->pos.x + ox * 0.5f; c.y = e->pos.y; c.z = e->pos.z + oz * 0.5f;
    if (len > 1.0f) { c.ax = ox / len; c.az = oz / len; } else { c.ax = 1; c.az = 0; }
    c.b = radius; c.a = radius + len * 0.5f;
    const float dist = __builtin_sqrtf(d2);
    float alpha = BLOB_ALPHA * (float) (255 - e->Shd_color) / 255.0f;
    if (dist > kFade0) alpha *= (kRange - dist) / (kRange - kFade0);
    if (!(alpha >= 2.0f)) return;
    c.alpha = alpha > 255.0f ? 255.0f : alpha;
    c.d2 = d2;
    if (n < kMax) { list[n++] = c; return; }
    int far = 0;
    for (int i = 1; i < n; ++i) if (list[i].d2 > list[far].d2) far = i;
    if (list[far].d2 > d2) list[far] = c;
}
}  // namespace

// native_ui.cpp stream_close: a presented scene, the TR list still open and sorting per pixel.
extern "C" void re4dc_blob_emit(unsigned frame)
{
    if (!pG || re4dc_blob_camera_frame != frame) return;   // no world part drew with a perspective camera this frame
    if (pG->Disp_flg & 0x02000000) return;
    if (pG->Status_flg[1] & 0x100) return;
#if defined(RE4DC_SHADOW_BLOB_TOGGLE)
    if (!s_blob_step) return;
#endif
    memcpy(M, &pG->Cam.v_mat[0][0], sizeof(M));
    memcpy(P, re4dc_blob_projection, sizeof(P));
    memcpy(VP, re4dc_blob_viewport, sizeof(VP));
    g_near = P[6] / (P[5] - 1.0f);
    if (!(g_near > 0) || !(VP[2] > 0) || !(VP[3] > 0)) return;
    g_near *= 1.01f;
    if (!g_hdr_ready) {
        pvr_poly_cxt_t cx;
        pvr_poly_cxt_col(&cx, PVR_LIST_TR_POLY);
        cx.gen.culling = PVR_CULLING_NONE;
        cx.gen.shading = PVR_SHADE_GOURAUD;
        cx.gen.fog_type = PVR_FOG_DISABLE;
        cx.depth.comparison = PVR_DEPTHCMP_GEQUAL;
        cx.depth.write = PVR_DEPTHWRITE_DISABLE;
        cx.blend.src = PVR_BLEND_SRCALPHA;
        cx.blend.dst = PVR_BLEND_INVSRCALPHA;
        pvr_poly_compile(&g_hdr, &cx);
        g_hdr_ready = true;
    }
    const V3 cam{-(M[0][0] * M[0][3] + M[1][0] * M[1][3] + M[2][0] * M[2][3]),
                 -(M[0][1] * M[0][3] + M[1][1] * M[1][3] + M[2][1] * M[2][3]),
                 -(M[0][2] * M[0][3] + M[1][2] * M[1][3] + M[2][2] * M[2][3])};
    Caster list[kMax];
    int n = 0;
    bool pl_listed = false;
    for (cEm* e = EmMgr.pAlive; e; e = (cEm*) e->pNext) {
        if ((e->be_flag & 0x201) != 1) continue;
        const bool table = e->pFootShadowTbl != 0, ganado = e->id >= 0x10 && e->id <= 0x20;
        if (!table && !ganado) continue;
        ++g_seen; g_table += table; g_ids += ganado;
        if (!(e->be_flag & 2)) continue;   // not drawn this frame
        if ((cEm*) pPL == e) pl_listed = true;
        add(list, n, e, BLOB_RADIUS, cam);
    }
    if (pPL && !pl_listed && (pPL->be_flag & 2)) add(list, n, pPL, BLOB_RADIUS * 0.9f, cam);
    for (int i = 0; i < n; ++i) blob(list[i]);
    if (!(++g_frames % 600))
        re4dc_log("blob shadows: frames=%u casters=%u skipped=%u failed=%u seen=%u table=%u ganado_ids=%u\n",
                  g_frames, g_casters, g_skipped, g_failed, g_seen, g_table, g_ids);
}
