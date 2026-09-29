// COARSE_WORLD (lane wd, test knob): the coarse view's world beyond the flat collision pieces, drawn from
// read-only room data prepared offline (coarse_world.h, generated from private assets; never committed).
// Nothing here is written by gameplay; doors stay their own collision pieces (drawn by coarse.cpp, they
// move with the game).
//   bit 1  house shells: each house BIN of the room (the Standard set's houses; r101's well, BIN 45, is a
//          landmark and never shelled) as its baked render shell (bl_house_shell.py, 400 / 200 faces, a
//          128 x 128 VQ bake with each face's flat light in it), placed by the room SMD, in place of the
//          collision polygons of its outer surfaces (coarse.cpp skips those by coarse_world.h kSkip).
//   bit 2  ground: the collision floors that have the source ground over them, in 6.4 m chunks cut at
//          3.2 m cells, a colour per vertex from the source ground there and one grey detail texture
//          repeating per cell, in place of those floors (kSkipGround). The vertex colour is the source's
//          rendered tone before fog: its ground layers' textures, each times the lit vertex colour the
//          Standard mesh gives that part (native_static light_part: the source light evaluation at the
//          part's first draw), Gouraud over the covering source triangle (coarse_world.h v10; v9 took the
//          unlit textures, ~5x too light: the HUD gauge read "88" over it).
//   bit 4  sky: the room's sky dome (BIN 0, tex 1 clouds), unfogged, fading into the fog colour towards
//          the horizon (vertex offset colour); game30.mk makes the PVR background the fog colour.
//   bit 8  trees: every tree of the Standard impostor records as its atlas quad (camera-facing, the cell
//          by the eye's azimuth in the tree's frame), queued here and sent in the punch-through list by
//          re4dc_coarse_world_flush() (native_ui re4dc_model_finish_source_draws, after the OP pass).
// Shells: a facing group the eye sees wholly from behind is skipped by one test, a group whose bounding
// sphere is outside a side of the view (a screen edge or the near plane) by another; a group wholly in front
// of the near plane goes out as its strips, each vertex transformed as it goes (16-bit UVs, white: the
// PVR culls the back faces among them); a group across the plane goes out strip by strip (a strip wholly
// outside one side of the view skipped), a strip with a vertex behind the plane triangle by triangle,
// near-clipped with its UVs. Ground chunks: vertices
// transformed once, pieces (convex, wound up) out as strips, near-clipped the same way. Sky: vertices
// transformed and packed once, triangles out as they are or near-clipped. A triangle or piece that needs
// the clip, or a sky triangle, is first dropped when all its vertices are outside one side of the view
// (the 640 x 480 screen or the near plane, in homogeneous coordinates).
// Layout 11 (world-agent-20260926 from-main\renderer-contract.md; a coarse_world.h with kWorldLayout = 11, which
// defines every v10 name as well; bits 16-128 need it, and with them off the build is as before):
//   bit 16  R1 (+R6) mesh records: kMesh with its own positions, facing groups, strips, 16-bit or 32-bit UVs
//           and an optional ARGB per strip vertex (multiplied into the texture); a mode byte per record:
//           0x01 repeat, 0x02 fog, 0x04 cull (without it both sides draw: always groups), 0x08 32-bit UVs,
//           0x10 ARGB; 0x20-0x80 reserved (R2): such a record is skipped and counted as a reject. Drawn after
//           the shells as the shells are (box, facing group, group sphere against the view, near path).
//   bit 32  R7 backdrop segments: kBackdrop, each with its own texture, sky vertices (the sky's fade into the
//           fog colour) and byte triangles, world-fixed or following the eye (mode 0x04), unfogged unless 0x02;
//           after the sky, before the ground; a segment whose sphere is outside a side of the view is skipped.
//   bit 64  R3 world texture preload: kWorldTex (re4dc_coarse_world_tex) joins native_ui's room-entry preload.
//   bit 128 K0: the data covers every piece-0 polygon (kCover full), so coarse.cpp does not walk piece 0 at all
//           (drawing only: collision data and queries are never read here); checked at compile time below.
// The data is trusted (no per-vertex bounds checks): a header is checked by the host reference decoder
// (ref_decoder.py) and the static_asserts below before it is built: counts against their arrays, every record's
// ranges, group sizes against the g_sv buffer, strips ending inside their groups, backdrop triangles inside their
// segments, bitsets (no bit at or past kPolys), every member offset and type of Mesh, Backdrop, WorldTex, Group and
// SkyVertex, and each kWorldTex entry's bytes against its real size (renderer-contract.md Revision 2).
// Revision 2 (R7): with backdrop segments the sky dome writes no depth, so a band farther than the dome (whose
// horizon ring is 67-101 m from the world origin) is never hidden by it.
#include "re4dc_screen.h"
#include "coarse_scene.h"
#include "coarse_world.h"
#include "native_model.h"
#include <dc/matrix.h>
#include <dc/pvr.h>
#include <kos/timer.h>
#include <cstdint>
#if RE4DC_COARSE_WORLD & 0xF0
#include <cstddef>
#endif

// Host test builds (the layout-11 decode check compiles this file on the PC): no store queue, no FSRRA.
#if defined(__sh__)
#define CW_PREF(p) __asm__ __volatile__("pref @%0" : : "r"(p) : "memory")
#else
#define CW_PREF(p) ((void) (p))
#endif

extern "C" std::uint32_t* re4dc_coarse_begin_mode(unsigned crc, unsigned fnv, unsigned width, unsigned height,
                                                  unsigned mode);   // platform/native_ui.cpp
extern "C" void re4dc_coarse_end(unsigned vertices);
extern "C" void re4dc_log(const char* fmt, ...);
#if RE4DC_COARSE_WORLD & 8
extern "C" unsigned re4dc_ui_frame();
extern "C" int re4dc_model_pt_begin(unsigned crc, unsigned fnv, unsigned width, unsigned height, int fog,
                                    Re4dcModelPacket* out);   // TREE_IMPOSTOR (native_ui.cpp)
#endif

namespace {
using namespace coarse_world;
constexpr float kNear = 40.0f;   // as coarse.cpp
constexpr unsigned kModeFog = 1, kModeRepeat = 2, kModeOffset = 4, kModeCullPos = 8, kModeCullNeg = 16,
                   kModeUV16 = 32;
constexpr std::uint32_t kWhite = 0xFFFFFFFFu;

struct Stats {
    unsigned shells, tris, near, groupsCulled, vtxCulled, groupsOff, chunks, gtris, sky, trees, clipped, offscreen,
        verts, us, rejects;
#if RE4DC_COARSE_WORLD & 0xF0
    unsigned meshes, mtris, backdrops, k0, reserved;
#endif
} g_st;

inline std::uint32_t fbits(float f) { return __builtin_bit_cast(std::uint32_t, f); }
inline float bitsf(std::uint32_t u) { return __builtin_bit_cast(float, u); }
inline float rsqrt(float x)
{
#if defined(__sh__)
    __asm__("fsrra %0" : "+f"(x));
    return x;
#else
    return 1.0f / __builtin_sqrtf(x);
#endif
}
inline float rcp(float w) { return rsqrt(w * w); }
inline std::uint32_t uv16(float u, float v) { return (fbits(u) & 0xFFFF0000u) | (fbits(v) >> 16); }

struct Emit {
    std::uint32_t* sq;
    unsigned n;
};
inline void put(Emit& o, std::uint32_t cmd, float x, float y, float z, std::uint32_t w4, std::uint32_t w5,
                std::uint32_t argb, std::uint32_t oargb)
{
    std::uint32_t* d = o.sq;
    d[0] = cmd;
    d[1] = fbits(x);
    d[2] = fbits(y);
    d[3] = fbits(z);
    d[4] = w4;
    d[5] = w5;
    d[6] = argb;
    d[7] = oargb;
    CW_PREF(d);
    o.sq = d + 8;
    o.n++;
}

// XMTRX = [S * [I | lo]; 0 0 0 1]: positions relative to lo go through as they are.
void load_rows(const CoarseView& v, const float lo[3])
{
    static matrix_t mt __attribute__((aligned(32)));
    for (unsigned r = 0; r < 3; ++r) {
        mt[0][r] = v.S[r][0];
        mt[1][r] = v.S[r][1];
        mt[2][r] = v.S[r][2];
        mt[3][r] = v.S[r][3] + v.S[r][0] * lo[0] + v.S[r][1] * lo[1] + v.S[r][2] * lo[2];
    }
    mt[0][3] = mt[1][3] = mt[2][3] = 0.0f;
    mt[3][3] = 1.0f;
    mat_load(&mt);
}

#if RE4DC_COARSE_WORLD & 0x13
// A world box against the view: beyond the far plane, behind the eye, outside a side plane.
bool box_visible(const CoarseView& v, const float lo[3], const float hi[3])
{
    const float x0 = lo[0], z0 = lo[2], x1 = hi[0], z1 = hi[2];
    const float ex = v.eye[0], ez = v.eye[2];
    const float dx = ex < x0 ? x0 - ex : ex > x1 ? ex - x1 : 0.0f;
    const float dz = ez < z0 ? z0 - ez : ez > z1 ? ez - z1 : 0.0f;
    if (dx * dx + dz * dz > v.far * v.far) {
        return false;
    }
    if (dx == 0.0f && dz == 0.0f) {
        return true;
    }
    const float xs[4] = {x0, x1, x1, x0}, zs[4] = {z0, z0, z1, z1};
    int behind = 0, out0 = 0, out1 = 0, beyond = 0;
    for (int i = 0; i < 4; ++i) {
        const float rx = xs[i] - ex, rz = zs[i] - ez;
        const float depth = rx * v.dir[0] + rz * v.dir[1];
        behind += depth < -1500.0f;
        beyond += depth > v.far + 1500.0f;
        out0 += rx * v.n0[0] + rz * v.n0[1] < -800.0f;
        out1 += rx * v.n1[0] + rz * v.n1[1] < -800.0f;
    }
    return behind < 4 && beyond < 4 && out0 < 4 && out1 < 4;
}
#endif

// ------------------------------------------------------------------ near-plane clip
// A clip vertex: X' Y' W', UV, base and offset colour channels (A R G B).
struct CV {
    float x, y, w, u, v, c[4], s[4];
};
inline std::uint32_t argb_of(const float* c)
{
    return ((std::uint32_t) c[0] << 24) | ((std::uint32_t) c[1] << 16) | ((std::uint32_t) c[2] << 8) | (std::uint32_t) c[3];
}
inline void unpack(std::uint32_t argb, float* c)
{
    c[0] = (float) (argb >> 24);
    c[1] = (float) ((argb >> 16) & 0xFFu);
    c[2] = (float) ((argb >> 8) & 0xFFu);
    c[3] = (float) (argb & 0xFFu);
}
// strip order of a convex polygon given in fan order (0 1 n-1 2 n-2 ...): keeps every triangle's winding
inline unsigned zig(unsigned n, unsigned k) { return k == 0 ? 0 : (k & 1) ? (k + 1) >> 1 : n - (k >> 1); }

// The sides of the view a vertex (X' Y' W', screen = X' / W') is outside of: the screen's four edges and
// the near plane, each a half-space in homogeneous coordinates (so valid behind the eye too). A polygon
// whose vertices share a bit is wholly outside the view.
inline unsigned outcode(float x, float y, float w)
{
    return (unsigned) (x < 0.0f) | (unsigned) (x > RE4DC_SCREEN_WF * w) << 1 | (unsigned) (y < 0.0f) << 2 |
           (unsigned) (y > RE4DC_SCREEN_HF * w) << 3 | (unsigned) (w < kNear) << 4;
}

enum ClipKind { kClipUV16, kClipUV32, kClipUV32Offset, kClipUV16Col };
// A convex polygon (fan order) near-clipped against W' >= kNear, out as one strip. The clip keeps the
// winding, so the PVR cull still sees it as authored. kClipUV16: white (the colours are not read),
// kClipUV32: base colour, kClipUV32Offset: base and offset colours, kClipUV16Col: 16-bit UVs, base colour.
template <ClipKind kind>
void emit_poly_clip(Emit& o, const CV* in, unsigned n)
{
    CV c[10];
    unsigned m = 0;
    for (unsigned i = 0; i < n; ++i) {
        const CV& a = in[i];
        const CV& b = in[i + 1 == n ? 0 : i + 1];
        const bool ia = a.w >= kNear, ib = b.w >= kNear;
        if (ia) {
            c[m++] = a;
        }
        if (ia != ib) {
            const float t = (kNear - a.w) / (b.w - a.w);
            CV& r = c[m++];
            r.x = a.x + (b.x - a.x) * t;
            r.y = a.y + (b.y - a.y) * t;
            r.w = kNear;
            r.u = a.u + (b.u - a.u) * t;
            r.v = a.v + (b.v - a.v) * t;
            if (kind != kClipUV16) {
                for (unsigned k = 0; k < 4; ++k) {
                    r.c[k] = a.c[k] + (b.c[k] - a.c[k]) * t;
                }
            }
            if (kind == kClipUV32Offset) {
                for (unsigned k = 0; k < 4; ++k) {
                    r.s[k] = a.s[k] + (b.s[k] - a.s[k]) * t;
                }
            }
        }
    }
    if (m < 3) {
        return;
    }
    for (unsigned k = 0; k < m; ++k) {
        const CV& q = c[zig(m, k)];
        const float iw = rcp(q.w);
        const std::uint32_t cmd = k + 1 == m ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX;
        if (kind == kClipUV16) {
            put(o, cmd, q.x * iw, q.y * iw, iw, uv16(q.u, q.v), 0, kWhite, 0);
        } else if (kind == kClipUV16Col) {
            put(o, cmd, q.x * iw, q.y * iw, iw, uv16(q.u, q.v), 0, argb_of(q.c), 0);
        } else {
            put(o, cmd, q.x * iw, q.y * iw, iw, fbits(q.u), fbits(q.v), argb_of(q.c),
                kind == kClipUV32Offset ? argb_of(q.s) : 0);
        }
    }
    g_st.clipped++;
}

#if RE4DC_COARSE_WORLD & 0x31
// ------------------------------------------------------------------ house shells (the vertex words: also meshes, backdrops)
union SqVertex {   // one PVR vertex in the store queue (float words stored as floats)
    std::uint32_t u[8];
    float f[8];
};
constexpr std::uint32_t kCmd[2] = {PVR_CMD_VERTEX, PVR_CMD_VERTEX_EOL};
#endif

#if RE4DC_COARSE_WORLD & 1
// A group wholly in front of the near plane: each strip vertex (position << 1 | end of strip) transformed
// as it goes out, with its packed UV.
std::uint32_t* emit_group(std::uint32_t* d, const unsigned short (*P)[3], const unsigned short* sp,
                          const unsigned* uv, unsigned n)
{
    for (unsigned i = 0; i < n; ++i) {
        const unsigned w = sp[i];
        const unsigned short* q = P[w >> 1];
        float x = (float) q[0], y = (float) q[1], z = (float) q[2];
        mat_trans_single3_nodiv(x, y, z);
        const float iw = rcp(z);
        SqVertex* o = reinterpret_cast<SqVertex*>(d);
        o->u[0] = kCmd[w & 1u];
        o->f[1] = x * iw;
        o->f[2] = y * iw;
        o->f[3] = iw;
        o->u[4] = uv[i];
        o->u[5] = 0;
        o->u[6] = kWhite;
        o->u[7] = 0;
        CW_PREF(d);
        d += 8;
    }
    return d;
}
#endif

#if RE4DC_COARSE_WORLD & 0x31
union SV {   // one strip vertex of the group being clipped: screen x, y, 1 / W' (valid when W' >= kNear), W'
    struct {
        float sx, sy, iw, w, x, y;   // and X' Y' for the clip
        unsigned oc;                 // outcode
    } v;
    std::uint32_t u[7];
};
#if RE4DC_COARSE_WORLD & 0x30
// one buffer for the shells' and the mesh records' groups across the near plane and the backdrop segments
constexpr unsigned cw_max(unsigned a, unsigned b) { return a > b ? a : b; }
constexpr unsigned backdrop_max_vtx()
{
    unsigned m = 1;
    for (unsigned i = 0; i < kBackdrops; ++i) {
        m = cw_max(m, kBackdrop[i].nvtx);
    }
    return m;
}
constexpr unsigned kSvCount = cw_max(cw_max((RE4DC_COARSE_WORLD & 1) ? kMaxGroupVtx : 1u,
                                            (RE4DC_COARSE_WORLD & 16) ? kMeshMaxGroupVtx : 1u),
                                     (RE4DC_COARSE_WORLD & 32) ? backdrop_max_vtx() : 1u);
#else
constexpr unsigned kSvCount = kMaxGroupVtx;
#endif
SV g_sv[kSvCount];
#endif

#if RE4DC_COARSE_WORLD & 1
inline std::uint32_t* put_sv(std::uint32_t* d, std::uint32_t cmd, const SV& q, std::uint32_t uv)
{
    d[0] = cmd;
    d[1] = q.u[0];
    d[2] = q.u[1];
    d[3] = q.u[2];
    d[4] = uv;
    d[5] = 0;
    d[6] = kWhite;
    d[7] = 0;
    CW_PREF(d);
    return d + 8;
}

// A group across the near plane: its strip vertices transformed into g_sv, then a strip wholly in front
// goes out as it is, else triangle by triangle (wholly in front: as it is; across: near-clipped).
void emit_group_near(Emit& o, const CoarseView& v, const Shell& s, const unsigned short* sp, const unsigned* uv,
                     unsigned nvtx)
{
    const unsigned short(*P)[3] = kPos + s.pos;
    for (unsigned i = 0; i < nvtx; ++i) {
        const unsigned short* q = P[sp[i] >> 1];
        float x = (float) q[0], y = (float) q[1], z = (float) q[2];
        mat_trans_single3_nodiv(x, y, z);
        const float iw = rcp(z);
        SV& t = g_sv[i];
        t.v.sx = x * iw;
        t.v.sy = y * iw;
        t.v.iw = iw;
        t.v.w = z;
        t.v.x = x;
        t.v.y = y;
        t.v.oc = outcode(x, y, z);
    }
    std::uint32_t* d = o.sq;
    unsigned j = 0;
    while (j < nvtx) {
        unsigned n = 1, all = g_sv[j].v.oc, any = all;
        while (!(sp[j + n - 1] & 1u)) {
            const unsigned oc = g_sv[j + n].v.oc;
            all &= oc;
            any |= oc;
            ++n;
        }
        const SV* t = g_sv + j;
        const unsigned* uu = uv + j;
        if (all) {
            g_st.offscreen++;
        } else if (!(any & 0x10u)) {
            for (unsigned k = 0; k < n; ++k) {
                d = put_sv(d, kCmd[k + 1 == n], t[k], uu[k]);
            }
            o.n += n;
            g_st.tris += n - 2;
        } else {
            for (unsigned k = 0; k + 2 < n; ++k) {
                // strip triangle k in its authored winding (the odd ones are stored reversed)
                const unsigned a = k + (k & 1), b = k + 1 - (k & 1), c = k + 2;
                const unsigned oa = t[a].v.oc, ob = t[b].v.oc, oc = t[c].v.oc;
                if (oa & ob & oc) {   // outside one side of the view (wholly behind the near plane included)
                    g_st.offscreen++;
                    continue;
                }
                if (!((oa | ob | oc) & 0x10u)) {
                    d = put_sv(d, PVR_CMD_VERTEX, t[a], uu[a]);
                    d = put_sv(d, PVR_CMD_VERTEX, t[b], uu[b]);
                    d = put_sv(d, PVR_CMD_VERTEX_EOL, t[c], uu[c]);
                    o.n += 3;
                    g_st.tris++;
                    continue;
                }
                // across the plane: skip it if the eye sees its back (the world plane), else clip it
                const unsigned short* p0 = P[sp[j + a] >> 1];
                const unsigned short* p1 = P[sp[j + b] >> 1];
                const unsigned short* p2 = P[sp[j + c] >> 1];
                const float ax = (float) p1[0] - p0[0], ay = (float) p1[1] - p0[1], az = (float) p1[2] - p0[2];
                const float bx = (float) p2[0] - p0[0], by = (float) p2[1] - p0[1], bz = (float) p2[2] - p0[2];
                const float nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx;
                const float ex = v.eye[0] - s.lo[0] - p0[0], ey = v.eye[1] - s.lo[1] - p0[1],
                            ez = v.eye[2] - s.lo[2] - p0[2];
                if (nx * ex + ny * ey + nz * ez <= 0.0f) {
                    continue;
                }
                CV q[3];
                const unsigned idx[3] = {a, b, c};
                for (unsigned i = 0; i < 3; ++i) {
                    const SV& r = t[idx[i]];
                    const std::uint32_t w = uu[idx[i]];
                    q[i].x = r.v.x;
                    q[i].y = r.v.y;
                    q[i].w = r.v.w;
                    q[i].u = bitsf(w & 0xFFFF0000u);
                    q[i].v = bitsf(w << 16);
                }
                o.sq = d;
                emit_poly_clip<kClipUV16>(o, q, 3);
                d = o.sq;
                g_st.tris++;
            }
        }
        j += n;
    }
    o.sq = d;
}
#endif

#if RE4DC_COARSE_WORLD & 0x31
// |gradient| of each side of the view (X', 640 W' - X', Y', 480 W' - Y', W'), per frame
float g_side[5];
inline float norm3(float a, float b, float c)
{
    const float d2 = a * a + b * b + c * c;
    return d2 > 0.0f ? d2 * rsqrt(d2) : 0.0f;
}
void set_sides(const CoarseView& v)
{
    const float *X = v.S[0], *Y = v.S[1], *W = v.S[2];
    g_side[0] = norm3(X[0], X[1], X[2]);
    g_side[1] = norm3(RE4DC_SCREEN_WF * W[0] - X[0], RE4DC_SCREEN_WF * W[1] - X[1], RE4DC_SCREEN_WF * W[2] - X[2]);
    g_side[2] = norm3(Y[0], Y[1], Y[2]);
    g_side[3] = norm3(RE4DC_SCREEN_HF * W[0] - Y[0], RE4DC_SCREEN_HF * W[1] - Y[1], RE4DC_SCREEN_HF * W[2] - Y[2]);
    g_side[4] = norm3(W[0], W[1], W[2]);
}
#endif

#if RE4DC_COARSE_WORLD & 1
unsigned draw_shell(const CoarseView& v, const Shell& s, unsigned cull)
{
    Emit o{re4dc_coarse_begin_mode(s.key[0], s.key[1], s.size, s.size, kModeFog | cull | kModeUV16), 0};
    if (!o.sq) {
        g_st.rejects++;
        return 0;
    }
    g_st.shells++;
    load_rows(v, s.lo);
    const unsigned short(*P)[3] = kPos + s.pos;
    // the eye in the shell's frame (positions are mm over lo)
    const float ex = v.eye[0] - s.lo[0], ey = v.eye[1] - s.lo[1], ez = v.eye[2] - s.lo[2];
    const unsigned short* sp = kStripPos + s.vtx;
    const unsigned* uv = kStripUV + s.vtx;
    const Group* G = kGroup + s.grp;
    bool near = false;
    for (unsigned g = 0; g < s.ngrp; ++g) {
        const Group& c = G[g];
        const float dx = ex - c.c[0], dy = ey - c.c[1], dz = ez - c.c[2];
        const float d2 = dx * dx + dy * dy + dz * dz;
        const float dist = d2 > 1.0f ? d2 * rsqrt(d2) : 1.0f;
        if (c.a[0] * ex + c.a[1] * ey + c.a[2] * ez + c.s * (dist + c.r) <= c.dmin) {
            g_st.groupsCulled++;
            g_st.vtxCulled += c.nvtx;
        } else {
            // the group's sphere against the view's sides: each side's value (X', 640 W' - X', Y',
            // 480 W' - Y', W') is affine, so over the sphere it is the centre's +- r |gradient|
            float cx = c.c[0], cy = c.c[1], cw = c.c[2];
            mat_trans_single3_nodiv(cx, cy, cw);   // X' Y' W' at the centre
            const float* gn = g_side;
            if (cx + c.r * gn[0] < 0.0f || RE4DC_SCREEN_WF * cw - cx + c.r * gn[1] < 0.0f || cy + c.r * gn[2] < 0.0f ||
                RE4DC_SCREEN_HF * cw - cy + c.r * gn[3] < 0.0f || cw + c.r * gn[4] < kNear) {
                g_st.groupsOff++;
            } else if (cw - c.r * gn[4] >= kNear) {
                o.sq = emit_group(o.sq, P, sp, uv, c.nvtx);
                o.n += c.nvtx;
                g_st.tris += c.nvtx - 2u * c.nstrip;
            } else {
                near = true;
                emit_group_near(o, v, s, sp, uv, c.nvtx);
            }
        }
        sp += c.nvtx;
        uv += c.nvtx;
    }
    g_st.near += near;
    re4dc_coarse_end(o.n);
    return o.n;
}
#endif

#if RE4DC_COARSE_WORLD & 16
// ------------------------------------------------------------------ mesh records (R1 + R6)
// A v10 Shell is a Mesh of mode 0x06: the same box test, facing groups, sphere test and near path, with the
// vertex words chosen by the mode (templates: 16- or 32-bit UVs, white or ARGB, culled or both-sided).
constexpr unsigned kMmRepeat = 0x01, kMmFog = 0x02, kMmCull = 0x04, kMmUV32 = 0x08, kMmARGB = 0x10,
                   kMmReserved = 0xE0;  // 0x20 R2 punch-through, 0x40 0x80

// A group wholly in front of the near plane: each strip vertex transformed as it goes out.
template <bool kUV32, bool kARGB>
std::uint32_t* emit_mesh_group(std::uint32_t* d, const unsigned short (*P)[3], const unsigned short* sp,
                               const unsigned* uv16, const float (*uv32)[2], const unsigned* col, unsigned n)
{
    for (unsigned i = 0; i < n; ++i) {
        const unsigned w = sp[i];
        const unsigned short* q = P[w >> 1];
        float x = (float) q[0], y = (float) q[1], z = (float) q[2];
        mat_trans_single3_nodiv(x, y, z);
        const float iw = rcp(z);
        SqVertex* o = reinterpret_cast<SqVertex*>(d);
        o->u[0] = kCmd[w & 1u];
        o->f[1] = x * iw;
        o->f[2] = y * iw;
        o->f[3] = iw;
        if (kUV32) {
            o->f[4] = uv32[i][0];
            o->f[5] = uv32[i][1];
        } else {
            o->u[4] = uv16[i];
            o->u[5] = 0;
        }
        o->u[6] = kARGB ? col[i] : kWhite;
        o->u[7] = 0;
        CW_PREF(d);
        d += 8;
    }
    return d;
}

template <bool kUV32, bool kARGB>
inline std::uint32_t* put_mesh_sv(std::uint32_t* d, std::uint32_t cmd, const SV& q, unsigned i,
                                  const unsigned* uv16, const float (*uv32)[2], const unsigned* col)
{
    SqVertex* o = reinterpret_cast<SqVertex*>(d);
    o->u[0] = cmd;
    o->u[1] = q.u[0];
    o->u[2] = q.u[1];
    o->u[3] = q.u[2];
    if (kUV32) {
        o->f[4] = uv32[i][0];
        o->f[5] = uv32[i][1];
    } else {
        o->u[4] = uv16[i];
        o->u[5] = 0;
    }
    o->u[6] = kARGB ? col[i] : kWhite;
    o->u[7] = 0;
    CW_PREF(d);
    return d + 8;
}

// A group across the near plane (as emit_group_near): its strip vertices transformed into g_sv, a strip
// wholly in front out as it is, else triangle by triangle, those across the plane near-clipped with their UVs
// and colours (a culled record skips the ones the eye sees from behind first).
template <bool kUV32, bool kARGB, bool kCull>
void emit_mesh_group_near(Emit& o, const CoarseView& v, const Mesh& m, const unsigned short (*P)[3],
                          const unsigned short* sp, const unsigned* uv16, const float (*uv32)[2], const unsigned* col,
                          unsigned nvtx)
{
    for (unsigned i = 0; i < nvtx; ++i) {
        const unsigned short* q = P[sp[i] >> 1];
        float x = (float) q[0], y = (float) q[1], z = (float) q[2];
        mat_trans_single3_nodiv(x, y, z);
        const float iw = rcp(z);
        SV& t = g_sv[i];
        t.v.sx = x * iw;
        t.v.sy = y * iw;
        t.v.iw = iw;
        t.v.w = z;
        t.v.x = x;
        t.v.y = y;
        t.v.oc = outcode(x, y, z);
    }
    std::uint32_t* d = o.sq;
    unsigned j = 0;
    while (j < nvtx) {
        unsigned n = 1, all = g_sv[j].v.oc, any = all;
        while (!(sp[j + n - 1] & 1u)) {
            const unsigned oc = g_sv[j + n].v.oc;
            all &= oc;
            any |= oc;
            ++n;
        }
        const SV* t = g_sv + j;
        if (all) {
            g_st.offscreen++;
        } else if (!(any & 0x10u)) {
            for (unsigned k = 0; k < n; ++k) {
                d = put_mesh_sv<kUV32, kARGB>(d, kCmd[k + 1 == n], t[k], j + k, uv16, uv32, col);
            }
            o.n += n;
            g_st.mtris += n - 2;
        } else {
            for (unsigned k = 0; k + 2 < n; ++k) {
                // strip triangle k in its authored winding (the odd ones are stored reversed)
                const unsigned a = k + (k & 1), b = k + 1 - (k & 1), c = k + 2;
                const unsigned oa = t[a].v.oc, ob = t[b].v.oc, oc = t[c].v.oc;
                if (oa & ob & oc) {
                    g_st.offscreen++;
                    continue;
                }
                if (!((oa | ob | oc) & 0x10u)) {
                    d = put_mesh_sv<kUV32, kARGB>(d, PVR_CMD_VERTEX, t[a], j + a, uv16, uv32, col);
                    d = put_mesh_sv<kUV32, kARGB>(d, PVR_CMD_VERTEX, t[b], j + b, uv16, uv32, col);
                    d = put_mesh_sv<kUV32, kARGB>(d, PVR_CMD_VERTEX_EOL, t[c], j + c, uv16, uv32, col);
                    o.n += 3;
                    g_st.mtris++;
                    continue;
                }
                if (kCull) {
                    // the PVR would drop it: skip it before the clip when the eye sees its back (the world plane)
                    const unsigned short* p0 = P[sp[j + a] >> 1];
                    const unsigned short* p1 = P[sp[j + b] >> 1];
                    const unsigned short* p2 = P[sp[j + c] >> 1];
                    const float ax = (float) p1[0] - p0[0], ay = (float) p1[1] - p0[1], az = (float) p1[2] - p0[2];
                    const float bx = (float) p2[0] - p0[0], by = (float) p2[1] - p0[1], bz = (float) p2[2] - p0[2];
                    const float nx = ay * bz - az * by, ny = az * bx - ax * bz, nz = ax * by - ay * bx;
                    const float ex = v.eye[0] - m.lo[0] - p0[0], ey = v.eye[1] - m.lo[1] - p0[1],
                                ez = v.eye[2] - m.lo[2] - p0[2];
                    if (nx * ex + ny * ey + nz * ez <= 0.0f) {
                        continue;
                    }
                }
                CV q[3];
                const unsigned idx[3] = {a, b, c};
                for (unsigned i = 0; i < 3; ++i) {
                    const SV& r = t[idx[i]];
                    const unsigned s = j + idx[i];
                    q[i].x = r.v.x;
                    q[i].y = r.v.y;
                    q[i].w = r.v.w;
                    if (kUV32) {
                        q[i].u = uv32[s][0];
                        q[i].v = uv32[s][1];
                    } else {
                        q[i].u = bitsf(uv16[s] & 0xFFFF0000u);
                        q[i].v = bitsf(uv16[s] << 16);
                    }
                    unpack(kARGB ? col[s] : kWhite, q[i].c);
                }
                o.sq = d;
                if (kUV32) {
                    emit_poly_clip<kClipUV32>(o, q, 3);
                } else if (kARGB) {
                    emit_poly_clip<kClipUV16Col>(o, q, 3);
                } else {
                    emit_poly_clip<kClipUV16>(o, q, 3);
                }
                d = o.sq;
                g_st.mtris++;
            }
        }
        j += n;
    }
    o.sq = d;
}

template <bool kUV32, bool kARGB, bool kCull>
void draw_mesh_groups(Emit& o, const CoarseView& v, const Mesh& m)
{
    const unsigned short(*P)[3] = kMeshPos + m.pos;
    // the eye in the record's frame (positions are mm over lo)
    const float ex = v.eye[0] - m.lo[0], ey = v.eye[1] - m.lo[1], ez = v.eye[2] - m.lo[2];
    const unsigned short* sp = kMeshStrip + m.vtx;
    const unsigned* uv16 = kUV32 ? nullptr : kMeshUV16 + m.uv;
    const float(*uv32)[2] = kUV32 ? kMeshUV32 + m.uv : nullptr;
    const unsigned* col = kARGB ? kMeshCol + m.col : nullptr;
    const Group* G = kMeshGroup + m.grp;
    bool near = false;
    for (unsigned g = 0; g < m.ngrp; ++g) {
        const Group& c = G[g];
        const float dx = ex - c.c[0], dy = ey - c.c[1], dz = ez - c.c[2];
        const float d2 = dx * dx + dy * dy + dz * dz;
        const float dist = d2 > 1.0f ? d2 * rsqrt(d2) : 1.0f;
        if (kCull && c.a[0] * ex + c.a[1] * ey + c.a[2] * ez + c.s * (dist + c.r) <= c.dmin) {
            g_st.groupsCulled++;
            g_st.vtxCulled += c.nvtx;
        } else {
            float cx = c.c[0], cy = c.c[1], cw = c.c[2];
            mat_trans_single3_nodiv(cx, cy, cw);   // X' Y' W' at the centre
            const float* gn = g_side;
            if (cx + c.r * gn[0] < 0.0f || RE4DC_SCREEN_WF * cw - cx + c.r * gn[1] < 0.0f || cy + c.r * gn[2] < 0.0f ||
                RE4DC_SCREEN_HF * cw - cy + c.r * gn[3] < 0.0f || cw + c.r * gn[4] < kNear) {
                g_st.groupsOff++;
            } else if (cw - c.r * gn[4] >= kNear) {
                o.sq = emit_mesh_group<kUV32, kARGB>(o.sq, P, sp, uv16, uv32, col, c.nvtx);
                o.n += c.nvtx;
                g_st.mtris += c.nvtx - 2u * c.nstrip;
            } else {
                near = true;
                emit_mesh_group_near<kUV32, kARGB, kCull>(o, v, m, P, sp, uv16, uv32, col, c.nvtx);
            }
        }
        sp += c.nvtx;
        if (kUV32) {
            uv32 += c.nvtx;
        } else {
            uv16 += c.nvtx;
        }
        if (kARGB) {
            col += c.nvtx;
        }
    }
    g_st.near += near;
}

unsigned draw_mesh(const CoarseView& v, const Mesh& m, unsigned cull)
{
    if (m.mode & kMmReserved) {
        g_st.rejects++;   // an R2 record: not drawn by R1 (renderer-contract.md 3)
        g_st.reserved++;
        return 0;
    }
    const unsigned mode = ((m.mode & kMmFog) ? kModeFog : 0u) | ((m.mode & kMmRepeat) ? kModeRepeat : 0u) |
                          ((m.mode & kMmCull) ? cull : 0u) | ((m.mode & kMmUV32) ? 0u : kModeUV16);
    Emit o{re4dc_coarse_begin_mode(m.key[0], m.key[1], m.tw, m.th, mode), 0};
    if (!o.sq) {
        g_st.rejects++;
        return 0;
    }
    g_st.meshes++;
    load_rows(v, m.lo);
    switch (m.mode & (kMmCull | kMmUV32 | kMmARGB)) {
    case kMmCull:
        draw_mesh_groups<false, false, true>(o, v, m);
        break;
    case kMmCull | kMmUV32:
        draw_mesh_groups<true, false, true>(o, v, m);
        break;
    case kMmCull | kMmARGB:
        draw_mesh_groups<false, true, true>(o, v, m);
        break;
    case kMmCull | kMmUV32 | kMmARGB:
        draw_mesh_groups<true, true, true>(o, v, m);
        break;
    case 0:
        draw_mesh_groups<false, false, false>(o, v, m);
        break;
    case kMmUV32:
        draw_mesh_groups<true, false, false>(o, v, m);
        break;
    case kMmARGB:
        draw_mesh_groups<false, true, false>(o, v, m);
        break;
    default:
        draw_mesh_groups<true, true, false>(o, v, m);
        break;
    }
    re4dc_coarse_end(o.n);
    return o.n;
}
#endif

#if RE4DC_COARSE_WORLD & 2
// ------------------------------------------------------------------ ground
struct GV {
    float x, y, iw, w, u, v;   // screen x, y, 1 / W' (valid when W' >= kNear), W', the detail UV
    std::uint32_t col, pad;
};
union GVU {
    GV g;
    std::uint32_t u[8];
};
GVU g_gv[kGroundMaxVtx];

unsigned draw_ground(const CoarseView& v, unsigned cull)
{
    Emit o{nullptr, 0};
    constexpr float kInv = 1.0f / kGroundCell;
    const float far2 = v.far * v.far;
    for (unsigned ci = 0; ci < kChunks; ++ci) {
        const Chunk& c = kChunk[ci];
        // beyond the far plane (the common case): the XZ distance to the chunk square
        const float ex = v.eye[0], ez = v.eye[2];
        const float dx = ex < c.x0 ? c.x0 - ex : ex > c.x0 + kGroundSpan ? ex - c.x0 - kGroundSpan : 0.0f;
        const float dz = ez < c.z0 ? c.z0 - ez : ez > c.z0 + kGroundSpan ? ez - c.z0 - kGroundSpan : 0.0f;
        if (dx * dx + dz * dz > far2) {
            continue;
        }
        const float lo[3] = {c.x0, c.y0, c.z0};
        const float hi[3] = {c.x0 + kGroundSpan, c.y1, c.z0 + kGroundSpan};
        if (!box_visible(v, lo, hi)) {
            continue;
        }
        if (!o.sq) {
            o.sq = re4dc_coarse_begin_mode(kGroundKey[0], kGroundKey[1], kGroundTex, kGroundTex,
                                           kModeFog | kModeRepeat | cull);
            if (!o.sq) {
                g_st.rejects++;
                return 0;
            }
        }
        g_st.chunks++;
        load_rows(v, lo);
        const unsigned short(*P)[3] = kGroundPos + c.vtx;
        const unsigned* col = kGroundCol + c.vtx;
        unsigned behind = 0;
        for (unsigned i = 0; i < c.nvtx; ++i) {
            const float px = (float) P[i][0], pz = (float) P[i][2];
            float x = px, y = (float) P[i][1], z = pz;
            mat_trans_single3_nodiv(x, y, z);
            const float iw = rcp(z);
            GV& g = g_gv[i].g;
            g.x = x * iw;
            g.y = y * iw;
            g.iw = iw;
            g.w = z;
            g.u = px * kInv;
            g.v = pz * kInv;
            g.col = col[i];
            behind += z < kNear;
        }
        const unsigned char* pc = kGroundPiece + c.piece;
        for (unsigned p = 0; p < c.npiece; ++p) {
            const unsigned n = *pc++;
            bool front = true;
            if (behind) {
                for (unsigned k = 0; k < n; ++k) {
                    front = front && g_gv[pc[k]].g.w >= kNear;
                }
            }
            if (front) {
                std::uint32_t* d = o.sq;
                for (unsigned k = 0; k < n; ++k) {
                    const std::uint32_t* q = g_gv[pc[zig(n, k)]].u;
                    d[0] = k + 1 == n ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX;
                    d[1] = q[0];
                    d[2] = q[1];
                    d[3] = q[2];
                    d[4] = q[4];
                    d[5] = q[5];
                    d[6] = q[6];
                    d[7] = 0;
                    CW_PREF(d);
                    d += 8;
                }
                o.sq = d;
                o.n += n;
                g_st.gtris += n - 2;
            } else {
                CV t[8];
                unsigned out = 0x1Fu;
                for (unsigned k = 0; k < n; ++k) {
                    const unsigned i = pc[k];
                    float x = (float) P[i][0], y = (float) P[i][1], z = (float) P[i][2];
                    mat_trans_single3_nodiv(x, y, z);   // XMTRX still holds the chunk's rows
                    t[k].x = x;
                    t[k].y = y;
                    t[k].w = z;
                    out &= outcode(x, y, z);
                }
                if (out) {
                    g_st.offscreen++;
                } else {
                    for (unsigned k = 0; k < n; ++k) {
                        const unsigned i = pc[k];
                        t[k].u = g_gv[i].g.u;
                        t[k].v = g_gv[i].g.v;
                        unpack(g_gv[i].g.col, t[k].c);
                    }
                    emit_poly_clip<kClipUV32>(o, t, n);
                    g_st.gtris += n - 2;
                }
            }
            pc += n;
        }
    }
    if (o.sq) {
        re4dc_coarse_end(o.n);
    }
    return o.n;
}
#endif

#if RE4DC_COARSE_WORLD & 4
// ------------------------------------------------------------------ sky
// base = white x (1 - fade), offset = fog x fade: the clouds fade into the fog colour at the horizon.
#if RE4DC_COARSE_WORLD & 32
// R7 (renderer-contract.md Revision 2): with backdrop segments the dome writes no depth (it is still depth-tested,
// so nearer geometry already drawn hides it). The dome's horizon ring is 67-101 m from the world origin, so from a
// pose near the square's edge it is nearer than a band 40-60 m from the eye in that direction; writing no depth,
// it never hides a band, and every band, ground, shell and record drawn after it covers it as before.
constexpr unsigned kModeNoDepthWrite = 64;
constexpr unsigned kSkyMode = kModeRepeat | kModeOffset | (kBackdrops ? kModeNoDepthWrite : 0u);
#else
constexpr unsigned kSkyMode = kModeRepeat | kModeOffset;
#endif
unsigned draw_sky(const CoarseView& v)
{
    Emit o{re4dc_coarse_begin_mode(kSkyKey[0], kSkyKey[1], kSkyW, kSkyH, kSkyMode), 0};
    if (!o.sq) {
        g_st.rejects++;
        return 0;
    }
    g_st.sky++;
    // the colours (base, offset) of each vertex for this fog colour, packed once
    static float fog[3] = {-1.0f, -1.0f, -1.0f};
    static std::uint32_t argb[kSkyVerts][2];
    if (fog[0] != v.fog_rgb[0] || fog[1] != v.fog_rgb[1] || fog[2] != v.fog_rgb[2]) {
        for (unsigned k = 0; k < 3; ++k) {
            fog[k] = v.fog_rgb[k];
        }
        for (unsigned i = 0; i < kSkyVerts; ++i) {
            const float f = (float) kSkyVertex[i].fade * (1.0f / 255.0f);
            const float b = 255.0f * (1.0f - f);
            const float c[4] = {255.0f, b, b, b}, s[4] = {255.0f, fog[0] * f, fog[1] * f, fog[2] * f};
            argb[i][0] = argb_of(c);
            argb[i][1] = argb_of(s);
        }
    }
    static const float zero[3] = {0.0f, 0.0f, 0.0f};
    load_rows(v, zero);
    // per vertex: its vertex words (x y 1/W' u v argb oargb; valid when W' >= kNear), X' Y' W' and outcode
    static union {
        float f[8];
        std::uint32_t u[8];
    } sv[kSkyVerts] __attribute__((aligned(32)));
    static float cw[kSkyVerts][3];
    static unsigned char oc[kSkyVerts];
    for (unsigned i = 0; i < kSkyVerts; ++i) {
        const SkyVertex& s = kSkyVertex[i];
        float x = s.p[0], y = s.p[1], z = s.p[2];
        mat_trans_single3_nodiv(x, y, z);
        const float iw = rcp(z);
        sv[i].f[1] = x * iw;
        sv[i].f[2] = y * iw;
        sv[i].f[3] = iw;
        sv[i].f[4] = s.u;
        sv[i].f[5] = s.v;
        sv[i].u[6] = argb[i][0];
        sv[i].u[7] = argb[i][1];
        cw[i][0] = x;
        cw[i][1] = y;
        cw[i][2] = z;
        oc[i] = (unsigned char) outcode(x, y, z);
    }
    for (unsigned t = 0; t < kSkyTris; ++t) {
        const unsigned i0 = kSkyTri[t][0], i1 = kSkyTri[t][1], i2 = kSkyTri[t][2];
        const unsigned o0 = oc[i0], o1 = oc[i1], o2 = oc[i2];
        if (o0 & o1 & o2) {
            g_st.offscreen++;
            continue;
        }
        if (!((o0 | o1 | o2) & 0x10u)) {
            const unsigned idx[3] = {i0, i1, i2};
            std::uint32_t* d = o.sq;
            for (unsigned k = 0; k < 3; ++k) {
                const std::uint32_t* q = sv[idx[k]].u;
                d[0] = k == 2 ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX;
                d[1] = q[1];
                d[2] = q[2];
                d[3] = q[3];
                d[4] = q[4];
                d[5] = q[5];
                d[6] = q[6];
                d[7] = q[7];
                CW_PREF(d);
                d += 8;
            }
            o.sq = d;
            o.n += 3;
        } else {
            const unsigned idx[3] = {i0, i1, i2};
            CV tri[3];
            for (unsigned k = 0; k < 3; ++k) {
                const unsigned i = idx[k];
                tri[k].x = cw[i][0];
                tri[k].y = cw[i][1];
                tri[k].w = cw[i][2];
                tri[k].u = kSkyVertex[i].u;
                tri[k].v = kSkyVertex[i].v;
                unpack(argb[i][0], tri[k].c);
                unpack(argb[i][1], tri[k].s);
            }
            emit_poly_clip<kClipUV32Offset>(o, tri, 3);
        }
    }
    re4dc_coarse_end(o.n);
    return o.n;
}
#endif

#if RE4DC_COARSE_WORLD & 32
// ------------------------------------------------------------------ backdrop segments (R7)
// As the sky: base = white x (1 - fade), offset = fog x fade (colours per vertex, packed once per fog colour);
// every vertex of a segment in view transformed, triangles out as they are, dropped by outcode or near-clipped.
constexpr unsigned kBackRepeat = 0x01, kBackFog = 0x02, kBackFollow = 0x04;
constexpr unsigned kBackdropVertexCount = sizeof(kBackdropVertex) / sizeof(kBackdropVertex[0]);

unsigned draw_backdrops(const CoarseView& v)
{
    static float fog[3] = {-1.0f, -1.0f, -1.0f};
    static std::uint32_t argb[kBackdropVertexCount][2];
    if (fog[0] != v.fog_rgb[0] || fog[1] != v.fog_rgb[1] || fog[2] != v.fog_rgb[2]) {
        for (unsigned k = 0; k < 3; ++k) {
            fog[k] = v.fog_rgb[k];
        }
        for (unsigned i = 0; i < kBackdropVertexCount; ++i) {
            const float f = (float) kBackdropVertex[i].fade * (1.0f / 255.0f);
            const float b = 255.0f * (1.0f - f);
            const float c[4] = {255.0f, b, b, b}, s[4] = {255.0f, fog[0] * f, fog[1] * f, fog[2] * f};
            argb[i][0] = argb_of(c);
            argb[i][1] = argb_of(s);
        }
    }
    unsigned verts = 0;
    for (unsigned bi = 0; bi < kBackdrops; ++bi) {
        const Backdrop& s = kBackdrop[bi];
        // follow mode: x and z (vertices and sphere) are relative to the eye
        const bool follow = s.mode & kBackFollow;
        const float lo[3] = {follow ? v.eye[0] : 0.0f, 0.0f, follow ? v.eye[2] : 0.0f};
        load_rows(v, lo);
        float cx = s.c[0], cy = s.c[1], cw = s.c[2];
        mat_trans_single3_nodiv(cx, cy, cw);   // X' Y' W' at the sphere's centre
        const float* gn = g_side;
        if (cx + s.r * gn[0] < 0.0f || RE4DC_SCREEN_WF * cw - cx + s.r * gn[1] < 0.0f || cy + s.r * gn[2] < 0.0f ||
            RE4DC_SCREEN_HF * cw - cy + s.r * gn[3] < 0.0f || cw + s.r * gn[4] < kNear) {
            continue;   // outside a side of the view
        }
        Emit o{re4dc_coarse_begin_mode(s.key[0], s.key[1], s.tw, s.th,
                                       kModeOffset | ((s.mode & kBackRepeat) ? kModeRepeat : 0u) |
                                           ((s.mode & kBackFog) ? kModeFog : 0u)),
               0};
        if (!o.sq) {
            g_st.rejects++;
            continue;
        }
        g_st.backdrops++;
        const SkyVertex* V = kBackdropVertex + s.vtx;
        const std::uint32_t(*C)[2] = argb + s.vtx;
        for (unsigned i = 0; i < s.nvtx; ++i) {
            float x = V[i].p[0], y = V[i].p[1], z = V[i].p[2];
            mat_trans_single3_nodiv(x, y, z);
            const float iw = rcp(z);
            SV& t = g_sv[i];
            t.v.sx = x * iw;
            t.v.sy = y * iw;
            t.v.iw = iw;
            t.v.w = z;
            t.v.x = x;
            t.v.y = y;
            t.v.oc = outcode(x, y, z);
        }
        const unsigned char(*T)[3] = kBackdropTri + s.tri;
        for (unsigned t = 0; t < s.ntri; ++t) {
            const unsigned idx[3] = {T[t][0], T[t][1], T[t][2]};
            const unsigned o0 = g_sv[idx[0]].v.oc, o1 = g_sv[idx[1]].v.oc, o2 = g_sv[idx[2]].v.oc;
            if (o0 & o1 & o2) {
                g_st.offscreen++;
                continue;
            }
            if (!((o0 | o1 | o2) & 0x10u)) {
                std::uint32_t* d = o.sq;
                for (unsigned k = 0; k < 3; ++k) {
                    const unsigned i = idx[k];
                    SqVertex* q = reinterpret_cast<SqVertex*>(d);
                    q->u[0] = k == 2 ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX;
                    q->u[1] = g_sv[i].u[0];
                    q->u[2] = g_sv[i].u[1];
                    q->u[3] = g_sv[i].u[2];
                    q->f[4] = V[i].u;
                    q->f[5] = V[i].v;
                    q->u[6] = C[i][0];
                    q->u[7] = C[i][1];
                    CW_PREF(d);
                    d += 8;
                }
                o.sq = d;
                o.n += 3;
            } else {
                CV tri[3];
                for (unsigned k = 0; k < 3; ++k) {
                    const unsigned i = idx[k];
                    tri[k].x = g_sv[i].v.x;
                    tri[k].y = g_sv[i].v.y;
                    tri[k].w = g_sv[i].v.w;
                    tri[k].u = V[i].u;
                    tri[k].v = V[i].v;
                    unpack(C[i][0], tri[k].c);
                    unpack(C[i][1], tri[k].s);
                }
                emit_poly_clip<kClipUV32Offset>(o, tri, 3);
            }
        }
        re4dc_coarse_end(o.n);
        verts += o.n;
    }
    return verts;
}
#endif

#if RE4DC_COARSE_WORLD & 8
// ------------------------------------------------------------------ trees
float turns(float y, float x)   // as native_static.cpp: atan2 in turns, [0, 1)
{
    const float ax = x < 0.0f ? -x : x, ay = y < 0.0f ? -y : y, lo = ax < ay ? ax : ay, hi = ax < ay ? ay : ax;
    if (!(hi > 0.0f)) {
        return 0.0f;
    }
    const float a = lo / hi, s = a * a;
    float r = ((-0.0464964749f * s + 0.15931422f) * s - 0.327622764f) * s * a + a;
    if (ay > ax) {
        r = 1.57079633f - r;
    }
    if (x < 0.0f) {
        r = 3.14159265f - r;
    }
    r *= 0.159154943f;
    return y < 0.0f ? 1.0f - r : r;
}
struct TreeQuad {
    unsigned short atlas, cell;
    float s[4][3];   // screen x, y, 1 / W' per corner: TL, TR, BL, BR
};
constexpr unsigned kTreeQuads = 64;
TreeQuad g_tq[kTreeQuads];
unsigned g_ntq, g_tqFrame = ~0u;

void queue_trees(const CoarseView& v)
{
    g_ntq = 0;
    g_tqFrame = re4dc_ui_frame();
    static const float zero[3] = {0.0f, 0.0f, 0.0f};
    load_rows(v, zero);
    for (unsigned i = 0; i < kTrees && g_ntq < kTreeQuads; ++i) {
        const Tree& t = kTree[i];
        const float dx = v.eye[0] - t.c[0], dz = v.eye[2] - t.c[2];
        const float d2 = dx * dx + dz * dz;
        const float reach = v.far + t.hw;
        if (d2 > reach * reach || d2 < 1.0f) {
            continue;
        }
        const float il = rsqrt(d2), bx = dx * il, bz = dz * il;
        const TreeAtlas& a = kTreeAtlas[t.atlas];
        // the eye's azimuth in the tree's own frame picks the cell (native_static mesh_impostor)
        const float mx = dx * t.ex[0] + dz * t.ex[1], mz = dx * t.ez[0] + dz * t.ez[1];
        unsigned cell = (unsigned) (turns(-mz, mx) * (float) a.views + 0.5f);
        if (cell >= a.views) {
            cell -= a.views;
        }
        TreeQuad& q = g_tq[g_ntq];
        unsigned left = 0, right = 0, top = 0, bottom = 0;
        bool ok = true;
        for (unsigned k = 0; k < 4 && ok; ++k) {
            const float sx = (k & 1) ? t.hw : -t.hw, sy = (k & 2) ? -t.hh : t.hh;
            float x = t.c[0] + sx * bz, y = t.c[1] + sy, z = t.c[2] - sx * bx;
            mat_trans_single3_nodiv(x, y, z);
            if (!(z >= kNear)) {
                ok = false;
                break;
            }
            const float iw = rcp(z);
            float* s = q.s[k];
            s[0] = x * iw;
            s[1] = y * iw;
            s[2] = iw;
            left += s[0] < 0.0f;
            right += s[0] > RE4DC_SCREEN_WF;
            top += s[1] < 0.0f;
            bottom += s[1] > RE4DC_SCREEN_HF;
        }
        if (!ok || left == 4 || right == 4 || top == 4 || bottom == 4) {
            continue;
        }
        q.atlas = (unsigned short) t.atlas;
        q.cell = (unsigned short) cell;
        ++g_ntq;
        ++g_st.trees;
    }
}
#endif

#if RE4DC_COARSE_WORLD & 0xF0
// ------------------------------------------------------------------ layout 11: the data gate (renderer-contract.md 2-7, 9,
// Revision 2). The runtime trusts the data (no per-vertex bounds checks), so a header that would index past an array,
// overrun g_sv or change a record's layout does not build. ref_decoder.py reports each of these as an error as well.
// The checks read the whole header whichever of bits 16-128 are on (a delivery is one header).
static_assert(kWorldLayout == 11, "COARSE_WORLD bits 16-128 read a layout-11 coarse_world.h (renderer-contract.md)");
template <class A, class B>
struct cw_same {
    static constexpr bool v = false;
};
template <class A>
struct cw_same<A, A> {
    static constexpr bool v = true;
};
template <class T, unsigned N>
constexpr unsigned cw_count(const T (&)[N])
{
    return N;
}
// [first, first + n) inside an array of `size` elements, without wrapping
constexpr bool cw_in(unsigned first, unsigned n, unsigned size) { return first <= size && n <= size - first; }
constexpr bool cw_side(unsigned s) { return s >= 8 && s <= 1024 && !(s & (s - 1)); }
// ---- every member of the records in sections 3-5 (and the v10 Group, SkyVertex they use): offset and type
#define CW_M(S, m, off, T) (offsetof(S, m) == (off) && cw_same<decltype(S::m), T>::v)
static_assert(sizeof(Mesh) == 64 && alignof(Mesh) == 4 && CW_M(Mesh, lo, 0, float[3]) && CW_M(Mesh, hi, 12, float[3]) &&
                  CW_M(Mesh, pos, 24, unsigned) && CW_M(Mesh, vtx, 28, unsigned) && CW_M(Mesh, nvtx, 32, unsigned) &&
                  CW_M(Mesh, uv, 36, unsigned) && CW_M(Mesh, col, 40, unsigned) && CW_M(Mesh, key, 44, unsigned[2]) &&
                  CW_M(Mesh, grp, 52, unsigned short) && CW_M(Mesh, ngrp, 54, unsigned short) &&
                  CW_M(Mesh, npos, 56, unsigned short) && CW_M(Mesh, tw, 58, unsigned short) &&
                  CW_M(Mesh, th, 60, unsigned short) && CW_M(Mesh, mode, 62, unsigned char) &&
                  CW_M(Mesh, rsv, 63, unsigned char),
              "layout 11: struct Mesh differs from renderer-contract.md 3 (a member's offset or type)");
static_assert(sizeof(Backdrop) == 40 && alignof(Backdrop) == 4 && CW_M(Backdrop, c, 0, float[3]) &&
                  CW_M(Backdrop, r, 12, float) && CW_M(Backdrop, key, 16, unsigned[2]) &&
                  CW_M(Backdrop, tw, 24, unsigned short) && CW_M(Backdrop, th, 26, unsigned short) &&
                  CW_M(Backdrop, vtx, 28, unsigned short) && CW_M(Backdrop, nvtx, 30, unsigned short) &&
                  CW_M(Backdrop, tri, 32, unsigned short) && CW_M(Backdrop, ntri, 34, unsigned short) &&
                  CW_M(Backdrop, mode, 36, unsigned char) && CW_M(Backdrop, band, 37, unsigned char) &&
                  CW_M(Backdrop, rsv, 38, unsigned short),
              "layout 11: struct Backdrop differs from renderer-contract.md 4 (a member's offset or type)");
static_assert(sizeof(WorldTex) == 16 && alignof(WorldTex) == 4 && CW_M(WorldTex, key, 0, unsigned[2]) &&
                  CW_M(WorldTex, w, 8, unsigned short) && CW_M(WorldTex, h, 10, unsigned short) &&
                  CW_M(WorldTex, bytes, 12, unsigned),
              "layout 11: struct WorldTex differs from renderer-contract.md 5 (a member's offset or type)");
static_assert(sizeof(Group) == 40 && alignof(Group) == 4 && CW_M(Group, a, 0, float[3]) && CW_M(Group, s, 12, float) &&
                  CW_M(Group, dmin, 16, float) && CW_M(Group, c, 20, float[3]) && CW_M(Group, r, 32, float) &&
                  CW_M(Group, nstrip, 36, unsigned short) && CW_M(Group, nvtx, 38, unsigned short),
              "layout 11: struct Group differs from v10 (renderer-contract.md 2: a member's offset or type)");
static_assert(sizeof(SkyVertex) == 24 && alignof(SkyVertex) == 4 && CW_M(SkyVertex, p, 0, float[3]) &&
                  CW_M(SkyVertex, u, 12, float) && CW_M(SkyVertex, v, 16, float) &&
                  CW_M(SkyVertex, fade, 20, unsigned),
              "layout 11: struct SkyVertex differs from v10 (renderer-contract.md 4: a member's offset or type)");
#undef CW_M
// ---- counts against their arrays, and the format limits (section 7)
static_assert(kMeshes <= cw_count(kMesh), "layout 11: kMeshes is larger than the kMesh array");
static_assert(kBackdrops <= cw_count(kBackdrop), "layout 11: kBackdrops is larger than the kBackdrop array");
static_assert(kWorldTexCount <= cw_count(kWorldTex), "layout 11: kWorldTexCount is larger than the kWorldTex array");
static_assert(kShells <= cw_count(kShell) && kChunks <= cw_count(kChunk) && kSkyVerts <= cw_count(kSkyVertex) &&
                  kSkyTris <= cw_count(kSkyTri) && kTreeAtlases <= cw_count(kTreeAtlas) && kTrees <= cw_count(kTree),
              "layout 11: a v10 count (kShells, kChunks, kSkyVerts, kSkyTris, kTreeAtlases, kTrees) is larger than its array");
static_assert(kShells + kMeshes <= 256 && kMeshMaxGroupVtx <= 512 && kBackdrops <= 16 && kWorldTexCount <= 48,
              "layout 11 limits (renderer-contract.md 7)");
static_assert(sizeof(kSkip) == (kPolys + 7) / 8 && sizeof(kSkipGround) == sizeof(kSkip) &&
                  sizeof(kSkipMesh) == sizeof(kSkip) && sizeof(kSkipBackdrop) == sizeof(kSkip) &&
                  sizeof(kCover) == sizeof(kSkip) && sizeof(kWorldDataId) <= 64,
              "layout 11 bitsets, id");
// ---- R1 records (section 3): ranges, group sizes (g_sv), strips, positions
constexpr bool mesh_ranges_ok()
{
    for (unsigned i = 0; i < kMeshes; ++i) {
        const Mesh& m = kMesh[i];
        if (!cw_in(m.grp, m.ngrp, cw_count(kMeshGroup)) || !cw_in(m.pos, m.npos, cw_count(kMeshPos)) ||
            !cw_in(m.vtx, m.nvtx, cw_count(kMeshStrip)) ||
            !((m.mode & 0x08u) ? cw_in(m.uv, m.nvtx, cw_count(kMeshUV32)) : cw_in(m.uv, m.nvtx, cw_count(kMeshUV16))) ||
            ((m.mode & 0x10u) && !cw_in(m.col, m.nvtx, cw_count(kMeshCol))) || m.nvtx > 8000 || m.npos > 32767 ||
            m.rsv || !cw_side(m.tw) || !cw_side(m.th)) {
            return false;
        }
    }
    return true;
}
static_assert(mesh_ranges_ok(), "layout 11: a kMesh record's grp/ngrp, pos/npos, vtx/nvtx, uv or col range runs past its "
                                "array, or nvtx > 8000, npos > 32767, rsv != 0, a texture side not a power of two 8..1024");
constexpr bool mesh_groups_fit()
{
    if (!mesh_ranges_ok()) {
        return true;   // reported by the range check above
    }
    for (unsigned i = 0; i < kMeshes; ++i) {
        for (unsigned g = kMesh[i].grp; g < (unsigned) kMesh[i].grp + kMesh[i].ngrp; ++g) {
            if (kMeshGroup[g].nvtx > kMeshMaxGroupVtx) {
                return false;
            }
        }
    }
    return true;
}
static_assert(mesh_groups_fit(), "layout 11: a mesh group has more strip vertices than kMeshMaxGroupVtx (it sizes g_sv)");
// strips (the caller checked that the groups hold nvtx): in each group every strip has 3 or more vertices and ends
// (EOL) inside the group, nstrip is the group's EOL count, and every strip vertex names a position below npos
template <class R>
constexpr bool strips_ok(const R& m, const Group* G, const unsigned short* S)
{
    unsigned j = 0;
    for (unsigned g = 0; g < m.ngrp; ++g) {
        const Group& c = G[m.grp + g];
        unsigned n = 0, eol = 0;
        for (unsigned k = 0; k < c.nvtx; ++k) {
            const unsigned w = S[m.vtx + j + k];
            if ((w >> 1) >= m.npos) {
                return false;
            }
            ++n;
            if (w & 1u) {
                if (n < 3) {
                    return false;
                }
                n = 0;
                ++eol;
            }
        }
        if (n || eol != c.nstrip) {
            return false;
        }
        j += c.nvtx;
    }
    return true;
}
template <class R>
constexpr unsigned group_sum(const R& m, const Group* G)
{
    unsigned sum = 0;
    for (unsigned g = 0; g < m.ngrp; ++g) {
        sum += G[m.grp + g].nvtx;
    }
    return sum;
}
constexpr bool mesh_strips_ok()
{
    if (!mesh_ranges_ok()) {
        return true;
    }
    for (unsigned i = 0; i < kMeshes; ++i) {
        if (group_sum(kMesh[i], kMeshGroup) != kMesh[i].nvtx || !strips_ok(kMesh[i], kMeshGroup, kMeshStrip)) {
            return false;
        }
    }
    return true;
}
static_assert(mesh_strips_ok(), "layout 11: a kMesh record's groups do not hold its nvtx, a strip has fewer than 3 "
                                "vertices or no end-of-strip bit inside its group, nstrip is not the group's EOL count, "
                                "or a strip vertex names a position at or past npos");
// v10 shells in a layout-11 header go through the same g_sv buffer (bit 1)
constexpr bool shells_ok()
{
    for (unsigned i = 0; i < kShells; ++i) {
        const Shell& s = kShell[i];
        if (!cw_in(s.grp, s.ngrp, cw_count(kGroup)) || !cw_in(s.pos, s.npos, cw_count(kPos)) ||
            !cw_in(s.vtx, s.nvtx, cw_count(kStripPos)) || !cw_in(s.vtx, s.nvtx, cw_count(kStripUV)) ||
            group_sum(s, kGroup) != s.nvtx) {
            return false;
        }
        for (unsigned g = s.grp; g < (unsigned) s.grp + s.ngrp; ++g) {
            if (kGroup[g].nvtx > kMaxGroupVtx) {
                return false;
            }
        }
        if (!strips_ok(s, kGroup, kStripPos)) {
            return false;
        }
    }
    return true;
}
static_assert(shells_ok(), "layout 11: a v10 kShell record's ranges run past their arrays, a group has more strip "
                           "vertices than kMaxGroupVtx, or its strips do not end inside their groups");
// ---- R7 segments (section 4): ranges, sizes, triangles inside their segment
constexpr bool backdrop_ranges_ok()
{
    unsigned total = 0;
    for (unsigned i = 0; i < kBackdrops; ++i) {
        const Backdrop& b = kBackdrop[i];
        if (!cw_in(b.vtx, b.nvtx, cw_count(kBackdropVertex)) || !cw_in(b.tri, b.ntri, cw_count(kBackdropTri)) ||
            b.nvtx < 3 || b.nvtx > 256 || b.ntri > 512 || (b.mode & 0xF8u) || b.rsv || !cw_side(b.tw) ||
            !cw_side(b.th)) {
            return false;
        }
        total += b.nvtx;
    }
    return total <= 1024;
}
static_assert(backdrop_ranges_ok(), "layout 11: a kBackdrop segment's vtx/nvtx or tri/ntri runs past kBackdropVertex / "
                                    "kBackdropTri, nvtx not in 3..256, ntri > 512, more than 1,024 vertices in all, "
                                    "a reserved mode bit or rsv set, or a texture side not a power of two 8..1024");
constexpr bool backdrop_tris_ok()
{
    if (!backdrop_ranges_ok()) {
        return true;
    }
    for (unsigned i = 0; i < kBackdrops; ++i) {
        const Backdrop& b = kBackdrop[i];
        for (unsigned t = b.tri; t < (unsigned) b.tri + b.ntri; ++t) {
            if (kBackdropTri[t][0] >= b.nvtx || kBackdropTri[t][1] >= b.nvtx || kBackdropTri[t][2] >= b.nvtx) {
                return false;
            }
        }
    }
    return true;
}
static_assert(backdrop_tris_ok(), "layout 11: a backdrop triangle names a vertex at or past its segment's nvtx");
// ---- R3 list (section 5): sides, and bytes = the texture's real size: full-codebook VQ 2048 + w h / 4, 16-bit
// w h 2, or (the Standard impostor atlases a TreeAtlas names) 4-bit palettised VQ 2048 + w h / 16 + 32
constexpr bool tree_atlas_key(const unsigned* key)
{
    for (unsigned a = 0; a < kTreeAtlases; ++a) {
        if (kTreeAtlas[a].key[0] == key[0] && kTreeAtlas[a].key[1] == key[1]) {
            return true;
        }
    }
    return false;
}
constexpr bool world_tex_ok()
{
    for (unsigned i = 0; i < kWorldTexCount; ++i) {
        const WorldTex& t = kWorldTex[i];
        const unsigned wh = (unsigned) t.w * t.h;
        if (!cw_side(t.w) || !cw_side(t.h) ||
            !(t.bytes == 2048u + wh / 4u || t.bytes == wh * 2u || (tree_atlas_key(t.key) && t.bytes == 2048u + wh / 16u + 32u))) {
            return false;
        }
    }
    return true;
}
static_assert(world_tex_ok(), "layout 11: a kWorldTex entry's side is not a power of two 8..1024, or its bytes is not "
                              "its real size (2048 + w*h/4 VQ, w*h*2 16-bit, tree atlas 2048 + w*h/16 + 32)");
// ---- bitsets (section 6): no bit at or past kPolys; kCoverCount counts kCover's bits
constexpr unsigned cw_bits(const unsigned char* b, unsigned from, unsigned to)
{
    unsigned c = 0;
    for (unsigned i = from; i < to; ++i) {
        c += (b[i >> 3] >> (i & 7)) & 1u;
    }
    return c;
}
constexpr unsigned kBitsetBits = 8 * sizeof(kSkip);
static_assert(cw_bits(kSkip, kPolys, kBitsetBits) == 0 && cw_bits(kSkipGround, kPolys, kBitsetBits) == 0 &&
                  cw_bits(kSkipMesh, kPolys, kBitsetBits) == 0 && cw_bits(kSkipBackdrop, kPolys, kBitsetBits) == 0 &&
                  cw_bits(kCover, kPolys, kBitsetBits) == 0,
              "layout 11: a skip set or kCover has a bit at or past kPolys (renderer-contract.md 6)");
static_assert(cw_bits(kCover, 0, kPolys) == kCoverCount, "layout 11: kCoverCount is not the number of kCover bits");
#if RE4DC_COARSE_WORLD & 128
// K0 skips piece 0's walk: every polygon must be covered, and every skip set the coverage relies on drawn.
static_assert(kCoverCount == kPolys && cw_bits(kCover, 0, kPolys) == kPolys,
              "COARSE_WORLD bit 128 (K0) needs full coverage: kCoverCount == kPolys (renderer-contract.md 6)");
static_assert((RE4DC_COARSE_WORLD & 1) || cw_bits(kSkip, 0, kPolys) == 0,
              "COARSE_WORLD bit 128 (K0): kSkip is not empty but bit 1 (the shells that replace it) is off");
static_assert((RE4DC_COARSE_WORLD & 2) || cw_bits(kSkipGround, 0, kPolys) == 0,
              "COARSE_WORLD bit 128 (K0): kSkipGround is not empty but bit 2 (the ground) is off");
static_assert((RE4DC_COARSE_WORLD & 16) || cw_bits(kSkipMesh, 0, kPolys) == 0,
              "COARSE_WORLD bit 128 (K0): kSkipMesh is not empty but bit 16 (the mesh records) is off");
static_assert((RE4DC_COARSE_WORLD & 32) || cw_bits(kSkipBackdrop, 0, kPolys) == 0,
              "COARSE_WORLD bit 128 (K0): kSkipBackdrop is not empty but bit 32 (the backdrop) is off");
#endif
#endif
}  // namespace

extern "C" unsigned re4dc_coarse_world_draw(const CoarseView* view)
{
    const std::uint64_t t0 = timer_us_gettime64();
    // the PVR culls what the eye sees from behind: a front face's screen area has the sign opposite det(S3)
    const unsigned cull = view->det > 0.0f ? kModeCullPos : kModeCullNeg;
    unsigned verts = 0;
#if RE4DC_COARSE_WORLD & 4
    verts += draw_sky(*view);
#endif
#if RE4DC_COARSE_WORLD & 32
    set_sides(*view);
    verts += draw_backdrops(*view);   // after the sky, before the ground (renderer-contract.md 4)
#endif
#if RE4DC_COARSE_WORLD & 2
    verts += draw_ground(*view, cull);
#endif
#if RE4DC_COARSE_WORLD & 1
    set_sides(*view);
    for (unsigned i = 0; i < kShells; ++i) {
        if (box_visible(*view, kShell[i].lo, kShell[i].hi)) {
            verts += draw_shell(*view, kShell[i], cull);
        }
    }
#endif
#if RE4DC_COARSE_WORLD & 16
#if !(RE4DC_COARSE_WORLD & 0x21)
    set_sides(*view);
#endif
    for (unsigned i = 0; i < kMeshes; ++i) {   // after the shells, in array order
        if (box_visible(*view, kMesh[i].lo, kMesh[i].hi)) {
            verts += draw_mesh(*view, kMesh[i], cull);
        }
    }
#endif
#if RE4DC_COARSE_WORLD & 8
    queue_trees(*view);
#endif
#if RE4DC_COARSE_WORLD & 128
    g_st.k0++;   // coarse.cpp skips piece 0's walk in every image this draws (the same room gate)
#endif
    (void) cull;
    g_st.verts += verts;
    g_st.us += (unsigned) (timer_us_gettime64() - t0);
    return verts;
}

#if RE4DC_COARSE_WORLD & 64
// R3: the world's texture list (kWorldTex, most important first) for native_ui's room-entry preload, which
// asks only in the data's room (coarse.cpp re4dc_coarse_world_room). out: crc, fnv, width, height, bytes.
extern "C" int re4dc_coarse_world_tex(unsigned i, unsigned out[5])
{
    if (i >= kWorldTexCount) {
        return 0;
    }
    const WorldTex& t = kWorldTex[i];
    out[0] = t.key[0];
    out[1] = t.key[1];
    out[2] = t.w;
    out[3] = t.h;
    out[4] = t.bytes;
    return 1;
}
#endif

// The trees queued by this frame's coarse view, one punch-through batch per atlas (native_ui
// re4dc_model_finish_source_draws: after the OP pass, before the translucent drain).
extern "C" void re4dc_coarse_world_flush()
{
#if RE4DC_COARSE_WORLD & 8
    if (g_tqFrame != re4dc_ui_frame()) {
        g_ntq = 0;
        return;
    }
    for (unsigned a = 0; a < kTreeAtlases && g_ntq; ++a) {
        unsigned any = 0;
        for (unsigned i = 0; i < g_ntq; ++i) {
            any += g_tq[i].atlas == a;
        }
        if (!any) {
            continue;
        }
        const TreeAtlas& r = kTreeAtlas[a];
        Re4dcModelPacket packet{};
        if (!re4dc_model_pt_begin(r.key[0], r.key[1], r.atlas_w, r.atlas_h, 1, &packet)) {
            g_st.rejects++;
            continue;
        }
        auto* out = static_cast<pvr_vertex_t*>(packet.vertices);
        unsigned used = 0;
        const float iw = 1.0f / (float) r.atlas_w, ih = 1.0f / (float) r.atlas_h;   // half-texel inset
        for (unsigned i = 0; i < g_ntq && used + 4 <= packet.capacity; ++i) {
            const TreeQuad& q = g_tq[i];
            if (q.atlas != a) {
                continue;
            }
            const unsigned col = q.cell % r.cols, row = q.cell / r.cols;
            const float u0 = ((float) (col * r.cell_w) + 0.5f) * iw, u1 = ((float) ((col + 1) * r.cell_w) - 0.5f) * iw;
            const float v0 = ((float) (row * r.cell_h) + 0.5f) * ih, v1 = ((float) ((row + 1) * r.cell_h) - 0.5f) * ih;
            for (unsigned k = 0; k < 4; ++k) {
                pvr_vertex_t& o = out[used + k];
                o.flags = k == 3 ? PVR_CMD_VERTEX_EOL : PVR_CMD_VERTEX;
                o.x = q.s[k][0];
                o.y = q.s[k][1];
                o.z = q.s[k][2];
                o.u = (k & 1) ? u1 : u0;
                o.v = (k & 2) ? v1 : v0;
                o.argb = kTreeArgb;
                o.oargb = 0;
            }
            used += 4;
        }
        re4dc_model_packet_commit(used);
    }
    g_ntq = 0;
#endif
}

extern "C" void re4dc_coarse_world_log(unsigned f)
{
    if (f) {
        re4dc_log("COARSE world shells=%u tris=%u near=%u groups_culled=%u verts_culled=%u groups_off=%u chunks=%u "
                  "ground_tris=%u "
                  "sky=%u trees=%u clipped=%u offscreen=%u verts=%u us=%u rejects=%u\n",
                  g_st.shells / f, g_st.tris / f, g_st.near / f, g_st.groupsCulled / f, g_st.vtxCulled / f, g_st.groupsOff / f,
                  g_st.chunks / f, g_st.gtris / f, g_st.sky / f, g_st.trees / f, g_st.clipped / f, g_st.offscreen / f,
                  g_st.verts / f,
                  g_st.us / f, g_st.rejects);
#if RE4DC_COARSE_WORLD & 0xF0
        // layout 11 (renderer-contract.md Revision 2): a line of its own after the v10 line above (unchanged), so both
        // stay well under re4dc_log's 256-byte buffer with a 63-character id. rejects (above) and reserved are totals
        // over the f frames (texture failures + reserved-mode R2 records, and the R2 records alone): the in-game
        // rule is rejects == reserved. meshes, mtris, backdrops and k0 are per frame, as the v10 counts.
        re4dc_log("COARSE world l11 meshes=%u mtris=%u backdrops=%u k0=%u reserved=%u id=%s\n", g_st.meshes / f,
                  g_st.mtris / f, g_st.backdrops / f, g_st.k0 / f, g_st.reserved, kWorldDataId);
#endif
    }
    g_st = Stats();
}
