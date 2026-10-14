// LAKE_RIPPLES (Phase 2 C4, 2026-10-11; default 0: this file is not built; render only): a moving surface on the r10b
// lake. WATER45_NATIVE draws the lake as a multiply of what is behind it (the GameCube's scene x TEV colour), and
// behind it there is only fog, so the water reads as dark fog without a surface. On top of each of that draw's cells
// (espgen45.cpp re4dc_water45_draw: view-space corners over the plane, fogged per corner) this adds one or two
// translucent layers of a small tileable ripple texture whose texture coordinates scroll each frame (the PVR has
// no texture matrix, so the corners' u, v are rewritten), faded out with the fog, plus a per-corner sun glint in
// the offset colour (a specular term from the reflected eye ray, evaluated on the CPU at the corners; the PVR
// interpolates it). The multiply stays, so the water still reads deep.
//
// The texture is made here at the first lake frame (64 x 64 ARGB4444, twiddled, 8 KiB of VRAM, kept while the
// lake is drawn and freed when a frame passes without it). Nothing here reads or writes game state; the frame
// counter that drives the scroll is the UI frame.
#include <kos.h>
#include <dc/pvr.h>
#include <cmath>
#include <cstdint>
#include <cstring>
#include "include/native_ui.h"
#include "include/subscreen_quad_geometry.hpp"

extern "C" unsigned re4dc_ui_frame();
extern "C" void re4dc_log(const char* fmt, ...);
extern "C" int re4dc_ui_tr_packet(const void* packet, unsigned bytes);  // native_ui.cpp (LAKE_RIPPLES)
extern "C" int re4dc_movie_open_now();                                  // native_movie.cpp (LAKE_RIPPLES)

#ifndef RE4DC_LAKE_RIPPLES
#define RE4DC_LAKE_RIPPLES 1   // layers: 1 or 2
#endif
#ifndef RE4DC_LAKE_TILE
#define RE4DC_LAKE_TILE 2800.0f   // lake-space mm per texture repeat (layer 1; layer 2 is 0.61 of it)
#endif
#ifndef RE4DC_LAKE_FADE
#define RE4DC_LAKE_FADE 18000.0f   // eye distance (mm) where the layers have faded out
#endif
#ifndef RE4DC_LAKE_ALPHA
#define RE4DC_LAKE_ALPHA 0.35f    // layer opacity before the fog fade
#endif

namespace {
constexpr unsigned kTex = 64;
pvr_ptr_t texture;
unsigned texture_frame, cells, drawn_frame = ~0U, log_frame;
unsigned st_cells, st_packets, st_dropped, st_frames, st_movie;
alignas(32) pvr_poly_hdr_t layer_header;   // compiled once with the texture

// Twiddled (Morton) offset of texel (x, y) for a square power-of-two texture: y bits even, x bits odd.
inline unsigned twiddle(unsigned x, unsigned y) {
    unsigned r = 0;
    for (unsigned b = 0; b < 8; ++b) r |= ((y >> b) & 1U) << (2 * b) | ((x >> b) & 1U) << (2 * b + 1);
    return r;
}

// A tileable ripple field: a few integer-frequency waves (so it wraps at the edges), shaped into thin bright
// crests. Colour: a pale sky tint; alpha carries the crest.
bool make_texture() {
    texture = pvr_mem_malloc(kTex * kTex * 2);
    if (!texture) return false;
    static std::uint16_t texels[kTex * kTex];
    const float k = 6.2831853f / float(kTex);
    for (unsigned y = 0; y < kTex; ++y)
        for (unsigned x = 0; x < kTex; ++x) {
            const float fx = float(x) * k, fy = float(y) * k;
            float h = std::sin(3 * fx + 1 * fy) + 0.8f * std::sin(-2 * fx + 4 * fy + 1.3f) +
                      0.6f * std::sin(5 * fx - 3 * fy + 2.1f) + 0.4f * std::sin(7 * fx + 6 * fy + 0.4f);
            h = h * (1.0f / 2.8f);                     // about -1 .. 1
            float c = 1.0f - 3.0f * std::fabs(h);      // thin ridges where the waves cross zero; troughs clear
            c = c > 0.0f ? c * c : 0.0f;
            const unsigned a = unsigned(c * 15.0f + 0.5f);
            texels[twiddle(x, y)] = std::uint16_t((a > 15 ? 15 : a) << 12 | 0x0FFFU);   // white, alpha = crest
        }
    pvr_txr_load(texels, texture, sizeof(texels));
    return true;
}

void header(pvr_poly_hdr_t* h) {
    pvr_poly_cxt_t c;
    pvr_poly_cxt_txr(&c, PVR_LIST_TR_POLY, PVR_TXRFMT_ARGB4444 | PVR_TXRFMT_TWIDDLED, int(kTex), int(kTex), texture,
                     PVR_FILTER_BILINEAR);
    c.gen.alpha = PVR_ALPHA_ENABLE;
    c.gen.culling = PVR_CULLING_NONE;
    c.gen.shading = PVR_SHADE_GOURAUD;
    c.gen.fog_type = PVR_FOG_DISABLE;     // the corner alpha carries the fog fade
    c.gen.specular = PVR_SPECULAR_ENABLE; // the offset colour carries the sun glint
    c.depth.comparison = PVR_DEPTHCMP_GEQUAL;
    c.depth.write = PVR_DEPTHWRITE_DISABLE;
    c.blend.src = PVR_BLEND_SRCALPHA;
    c.blend.dst = PVR_BLEND_INVSRCALPHA;
    c.txr.env = PVR_TXRENV_MODULATEALPHA;
    c.txr.alpha = PVR_TXRALPHA_ENABLE;
    c.txr.uv_clamp = PVR_UVCLAMP_NONE;
    pvr_poly_compile(h, &c);
}
}  // namespace

// espgen45.cpp re4dc_water45_draw, once per lake frame before the cells: the texture (made or kept).
extern "C" int re4dc_lake_begin() {
    const unsigned f = re4dc_ui_frame();
    if (texture && drawn_frame != ~0U && f - drawn_frame > 2U) {  // the lake was not drawn: give the VRAM back
        pvr_mem_free(texture); texture = nullptr;
    }
    if (re4dc_movie_open_now()) { ++st_movie; return 0; }   // a movie is open: its decoder needs the CPU
    if (!texture) {
#if defined(RE4DC_TEX_CHECK) && RE4DC_TEX_CHECK
        // TEX_CHECK (test only): a refused ripple texture is a failed texture lookup for the gate (texchk.sh);
        // logged at the first refusal and then every 600 frames with the count (it is retried every lake frame).
        static unsigned refusals, refusal_logged = ~0U;
        if (!make_texture()) {
            ++refusals;
            if (refusal_logged == ~0U || f - refusal_logged >= 600U) {
                refusal_logged = f;
                re4dc_log("texchk: FAIL lake-alloc 00000000-00000000 64x64 fmt=2 frame=%u refusals=%u free=%u\n", f,
                          refusals, unsigned(pvr_mem_available()));
            }
            return 0;
        }
        re4dc_log("texchk: lake texture ok frame=%u ptr=%08x refusals_before=%u\n", f, unsigned(std::uintptr_t(texture)),
                  refusals);
#else
        if (!make_texture()) return 0;
#endif
        header(&layer_header);
    }
    if (drawn_frame != f) { ++st_frames; drawn_frame = f; }
    if (f - log_frame >= 600U) {
        log_frame = f;
        re4dc_log("LAKE f=%u frames=%u cells=%u packets=%u dropped=%u movie=%u layers=%u\n", f, st_frames, st_cells,
                  st_packets, st_dropped, st_movie, unsigned(RE4DC_LAKE_RIPPLES));
    }
    return 1;
}

// One cell of the water draw. pos: view-space corners (strip order 0 1 2 3); lake: their world x, z (mm);
// fog: the fog amount at each corner (0 clear .. 1 fully fogged); up: the plane normal in view space; sun: the
// light direction in view space (unit, toward the light); projection / viewport: GX's.
extern "C" void re4dc_lake_cell(const float pos[4][3], const float lake[4][2], const float fog[4], const float up[3],
                                const float sun[3], const float* projection, const float* viewport) {
    if (!texture) return;
    Re4dcSubscreenQuad q{};
    std::memcpy(q.projection, projection, sizeof(q.projection));
    std::memcpy(q.viewport, viewport, sizeof(q.viewport));
    const float near = q.projection[6] / (q.projection[5] - 1), far = q.projection[6] / q.projection[5];
    if (!(near > 0) || !(far > near)) return;
    re4dc::render::ClipParameters clip{near, far, RE4DC_SCREEN_WF, RE4DC_SCREEN_HF, re4dc::subscreen::project, &q};
    const float t = float(re4dc_ui_frame());
    // layer scroll (texture repeats per second at 60 frames): slow drift, crossing directions
    const float s[2][2] = {{0.00110f, 0.00045f}, {-0.00060f, 0.00095f}};
    const float scale[2] = {1.0f / RE4DC_LAKE_TILE, 1.0f / (0.61f * RE4DC_LAKE_TILE)};
    alignas(32) pvr_vertex_t packet[2][1 + 12];
    unsigned bytes = 0;
    alignas(32) static unsigned char out[2 * sizeof(packet[0])];
    ++st_cells;
    for (unsigned layer = 0; layer < unsigned(RE4DC_LAKE_RIPPLES) && layer < 2; ++layer) {
        re4dc::render::RenderVertex v[4]{};
        float alpha[4];
        bool any = false;
        for (unsigned i = 0; i < 4; ++i) {
            auto& p = v[i].position;
            p.world_x = p.x = pos[i][0]; p.world_y = p.y = pos[i][1]; p.world_z = p.z = pos[i][2];
            p.depth = -p.world_z;
            if (p.depth >= near) re4dc::subscreen::project(p.x, p.y, p.z, &q);
            v[i].u = lake[i][0] * scale[layer] + t * s[layer][0];
            v[i].v = lake[i][1] * scale[layer] + t * s[layer][1];
            v[i].u -= std::floor(v[i].u * (1.0f / 64.0f)) * 64.0f;  // keep the float precision near zero
            v[i].v -= std::floor(v[i].v * (1.0f / 64.0f)) * 64.0f;
            v[i].light_red = 0.78f; v[i].light_green = 0.86f; v[i].light_blue = 0.94f;
            // fade with the fog and with distance (no mipmaps: the far field would alias into noise)
            float near_fade = 1.0f - p.depth * (1.0f / RE4DC_LAKE_FADE);
            near_fade = near_fade < 0.0f ? 0.0f : near_fade > 1.0f ? 1.0f : near_fade;
            alpha[i] = RE4DC_LAKE_ALPHA * (1.0f - fog[i]) * near_fade * (layer ? 0.7f : 1.0f);
            if (alpha[i] > 0.01f) any = true;
            // sun glint (layer 0 only): reflect the eye ray about the plane normal, compare with the light
            unsigned glint = 0;
            if (!layer) {
                const float l = std::sqrt(pos[i][0] * pos[i][0] + pos[i][1] * pos[i][1] + pos[i][2] * pos[i][2]);
                if (l > 0) {
                    const float e[3] = {pos[i][0] / l, pos[i][1] / l, pos[i][2] / l};  // eye -> point
                    const float d = 2.0f * (e[0] * up[0] + e[1] * up[1] + e[2] * up[2]);
                    const float r[3] = {e[0] - d * up[0], e[1] - d * up[1], e[2] - d * up[2]};
                    float c = r[0] * sun[0] + r[1] * sun[1] + r[2] * sun[2];
                    if (c > 0) {
                        c = c * c; c = c * c; c = c * c; c = c * c; c = c * c; c = c * c;  // ^64
                        const unsigned g = unsigned(c * (1.0f - fog[i]) * 200.0f);
                        glint = g > 255 ? 255 : g;
                    }
                }
            }
            v[i].offset_color = glint ? (glint << 16 | glint << 8 | (glint * 15U / 16U)) : 0U;
        }
        if (!any) continue;
        pvr_vertex_t* o = packet[layer];
        std::memcpy(o, &layer_header, sizeof(layer_header));
        unsigned used = 0;
        constexpr unsigned strips[2][3] = {{0, 1, 2}, {2, 1, 3}};
        for (const auto& ix : strips) {
            const re4dc::render::RenderVertex tri[] = {v[ix[0]], v[ix[1]], v[ix[2]]};
            const float a3[3] = {alpha[ix[0]], alpha[ix[1]], alpha[ix[2]]};
            used += 3 * re4dc::render::clip_projected_triangle(tri, o + 1 + used, 0, clip, nullptr, a3);
        }
        if (!used) continue;
#ifdef RE4DC_LAKE_ZBIAS
        // LAKE_ZBIAS (Makefile): the layer sits in the multiply's plane (a depth tie between two translucent draws);
        // scale its 1/w so the sorter keeps one order (> 1: in front of the multiply).
        for (unsigned k = 1; k <= used; ++k) o[k].z *= RE4DC_LAKE_ZBIAS;
#endif
        // the clipper writes rgb from light_*, alpha from a3; the offset colour per input vertex
        const unsigned n = (used + 1) * sizeof(pvr_vertex_t);
        std::memcpy(out + bytes, o, n);
        bytes += n;
    }
    if (!bytes) return;
    if (re4dc_ui_tr_packet(out, bytes)) ++st_packets; else ++st_dropped;
}
