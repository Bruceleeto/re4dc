"""ACTOR_PROBE_LIGHT (lane lp2): the per-actor light probe on the actual native-actor implementation.

Checks, for ACTOR_PROBE_LIGHT=1 and =2: one light reproduces build_lights' fold exactly (direction, colour, ambient);
lights on one side fold into one direction with the residual in the ambient; opposite equal lights give ambient only;
the probe is built once per (model, record, frame) and reused by the actor's other parts; Leon's per-part normal basis
is applied; Ganado ids are taken only at =2; unsupported records (tinted material, disabled lighting, per-vertex colour)
decline to build_lights; the source record is never written. LEON_LIGHT_FILL: Leon's camera fill in the second direction.
A Make parse test checks the knobs' requirements.
"""
from pathlib import Path
import shutil, subprocess, tempfile, unittest
ROOT = Path(__file__).resolve().parents[3]

FIXTURE = r'''
#include <cassert>
#include <cmath>
#include <cstdio>
#include "ACTOR_IMPLEMENTATION"
static int model_id = 0x12;
extern "C" int re4dc_actor_model_id(const void*) { return model_id; }
extern "C" void re4dc_log(const char*, ...) {}
#if RE4DC_LEON_LIGHT_TOGGLE
extern "C" unsigned re4dc_vi_retrace_count(void) { return 0; }
#endif
static bool near(float a, float b, float tol) { return std::fabs(a - b) <= tol; }
#if RE4DC_LEON_LIGHT_HEADROOM
constexpr float kLeonGain = 0.5f;  // LEON_LIGHT_HEADROOM: Leon's lit colours at x0.5 (his textures are 2x)
#else
constexpr float kLeonGain = 1.0f;
#endif
static SourceLighting base(unsigned lamps) {
    SourceLighting s{}; s.enable = 1; s.diffuse = 2; s.attenuation = 0; s.mask = (1u << lamps) - 1;
    s.ambient[0] = 20; s.ambient[1] = 30; s.ambient[2] = 40;
    s.material[0] = s.material[1] = s.material[2] = 255; s.tev_scale = 1;
    s.normal_matrix[0] = s.normal_matrix[5] = s.normal_matrix[10] = 1;
    return s;
}
static Re4dcModelPart part(SourceLighting& s, const void* model, const float* mv) {
    Re4dcModelPart p{}; p.lighting = &s; p.model = model; std::memcpy(p.modelview, mv, 48); return p;
}
int main() {
    const float I[12] = {1,0,0,100, 0,1,0,-50, 0,0,1,-900};
    Frame f{}; f.nq = 1.0f / 64;
    const float centre[3] = {0, 0, 0};
    int model_a = 0, model_b = 0;
    // 1. one light: the probe equals build_lights' fold (part centre = actor origin).
    for (bool leon : {false, true}) {
        SourceLighting s = base(1);
        if (leon) s.normal_matrix[3] = 1.0e30f;
        s.lights[0].position[0] = 1100; s.lights[0].position[1] = 400; s.lights[0].position[2] = -300;
        s.lights[0].color[0] = 200; s.lights[0].color[1] = 150; s.lights[0].color[2] = 90;
        const SourceLighting original = s;
        ++frame_serial;
        Re4dcModelPart p = part(s, &model_a, I);
        Lights a{}, b{};
        const bool took = probe_lights(p, f, a);
#if RE4DC_ACTOR_PROBE_LIGHT >= 2
        assert(took);
#else
        assert(took == leon);  // =1: Leon only
#endif
        if (!took) continue;
#if RE4DC_LEON_LIGHT_FILL
        unsigned probe_count = leon ? 2U : 1U;  // LEON_LIGHT_FILL: Leon's second direction is the camera fill
#else
        unsigned probe_count = 1U;
#endif
#if defined(RE4DC_GANADO_LIT_FILL) && RE4DC_GANADO_LIT_FILL > 0
        if (!leon) probe_count = 2U;  // GANADO_LIT_FILL: the Ganados' camera fill
#endif
        assert(build_lights(p, f, centre, b) && b.count == 1 && a.count == probe_count && a.fast && a.probe && !a.constant);
        for (unsigned c = 0; c < 3; ++c) {
            assert(near(a.dir[0][c], b.dir[0][c], 1e-6f));
            assert(near(a.color[c], b.color[c], 1e-3f));
            assert(near(a.color[12 + c], b.color[12 + c], 1e-3f));
        }
        assert(near(a.view_dot[0], b.view_dot[0], 1e-5f));
#if RE4DC_LEON_LIGHT_HEADROOM
        // LEON_LIGHT_HEADROOM: Leon's lit colour matrix at x0.5 (2x textures); others unchanged. Ambient 20 x 255/255.
        assert(near(b.color[12], (leon ? 0.5f : 1.0f) * 20.0f, 1e-3f) && near(a.color[12], b.color[12], 1e-3f));
#endif
        assert(!std::memcmp(&s, &original, sizeof(s)));
    }
    // 2. two lights on one side fold into one direction; opposite equal lights give ambient only.
    {
        SourceLighting s = base(2); s.normal_matrix[3] = 1.0e30f;
        for (unsigned i = 0; i < 2; ++i) { s.lights[i].color[0] = s.lights[i].color[1] = s.lights[i].color[2] = 120; }
        s.lights[0].position[0] = 1100; s.lights[0].position[1] = -50; s.lights[0].position[2] = -900;   // +x of origin
        s.lights[1].position[0] = 100; s.lights[1].position[1] = 950; s.lights[1].position[2] = -900;    // +y
        ++frame_serial;
        Re4dcModelPart p = part(s, &model_a, I);
        Lights a{}; assert(probe_lights(p, f, a));
        const float r = std::sqrt(0.5f);
        assert(near(a.dir[0][0], r * f.nq, 1e-5f) && near(a.dir[0][1], r * f.nq, 1e-5f) && near(a.dir[0][2], 0, 1e-6f));
        const float coherence = r;  // |V| / W for two equal orthogonal lights
        const float total = 2 * 120 / 255.0f;
        for (unsigned c = 0; c < 3; ++c) {
            assert(near(a.color[c], 0.5f * coherence * total * 255 * kLeonGain, 1e-2f));
            assert(near(a.color[12 + c], (s.ambient[c] / 255.0f + .25f * (1 - coherence) * total) * 255 * kLeonGain, 1e-2f));
        }
        s.lights[1].position[0] = -900; s.lights[1].position[1] = -50;  // now opposite (-x)
        ++frame_serial;
        Lights o{}; assert(probe_lights(p, f, o));
        for (unsigned c = 0; c < 3; ++c) {
            assert(near(o.dir[0][c], 0, 1e-6f) && near(o.color[c], 0, 1e-3f));
            assert(near(o.color[12 + c], (s.ambient[c] / 255.0f + .25f * total) * 255 * kLeonGain, 1e-2f));
        }
    }
    // 3. one probe per (model, record, frame): reused by later parts, rebuilt next frame or for another model.
    {
        SourceLighting s = base(1); s.normal_matrix[3] = 1.0e30f;
        s.lights[0].position[0] = 5100; s.lights[0].position[1] = -50; s.lights[0].position[2] = -900; s.lights[0].color[0] = 255;
        ++frame_serial;
        Re4dcModelPart p = part(s, &model_a, I);
        const unsigned built = probe_stats.built, reused = probe_stats.reused;
        Lights a{};
        for (unsigned k = 0; k < 5; ++k) assert(probe_lights(p, f, a));
        assert(probe_stats.built == built + 1 && probe_stats.reused == reused + 4);
        Re4dcModelPart q = part(s, &model_b, I);
        assert(probe_lights(q, f, a) && probe_stats.built == built + 2);
        // the shared record (actor_light_probe.h): this frame's probe of the model, unit direction toward the light
        Re4dcLightProbe rec{};
        assert(re4dc_actor_light_probe(&model_a, &rec) == 1 && rec.serial == frame_serial);
        assert(near(rec.dir[0], 1, 1e-6f) && near(rec.dir[1], 0, 1e-6f) && near(rec.dir[2], 0, 1e-6f));
        assert(near(rec.coherence, 1, 1e-6f) && near(rec.color[0], 1, 1e-6f) && rec.extra_n == 0 && rec.flash[0] == 0);
        int nobody = 0; assert(re4dc_actor_light_probe(&nobody, &rec) == 0);
        ++frame_serial;
        assert(probe_lights(p, f, a) && probe_stats.built == built + 3);
        // Leon's per-part basis: a part rotated 90 degrees about z sees the light along its own -y.
        const float R[12] = {0,-1,0,100, 1,0,0,-50, 0,0,1,-900};
        Re4dcModelPart rp = part(s, &model_a, R);
        Lights b{}; assert(probe_lights(rp, f, b));
        assert(near(b.dir[0][0], 0, 1e-6f) && near(b.dir[0][1], -f.nq, 1e-5f) && near(b.dir[0][2], 0, 1e-6f));
    }
    // 4. records the probe does not take: build_lights decides.
    {
        ++frame_serial;
        SourceLighting t = base(1); t.normal_matrix[3] = 1.0e30f; t.material[0] = 128; t.tev_scale = 1;  // tinted
        Re4dcModelPart p = part(t, &model_a, I); Lights a{};
        assert(!probe_lights(p, f, a));
        SourceLighting d = base(1); d.normal_matrix[3] = 1.0e30f; d.enable = 0;
        p = part(d, &model_a, I); assert(!probe_lights(p, f, a));
        SourceLighting v = base(1); v.normal_matrix[3] = 1.0e30f; v.material_vertex = 1;
        p = part(v, &model_a, I); assert(!probe_lights(p, f, a));
        model_id = 0x2B;  // El Gigante: never a probe
        SourceLighting g = base(1); p = part(g, &model_a, I); assert(!probe_lights(p, f, a));
        model_id = 0x12;
    }
    // 5. probe_dirs_all: every palette entry as skin_light_dirs builds it for the same one-direction fold.
    {
        SourceLighting s = base(1); s.normal_matrix[3] = 1.0e30f;
        s.lights[0].position[0] = 700; s.lights[0].position[1] = 300; s.lights[0].position[2] = -400; s.lights[0].color[1] = 200;
        ++frame_serial;
        Re4dcModelPart p = part(s, &model_a, I); Lights a{}; assert(probe_lights(p, f, a));
        float palette[3 * 12] = {1,0,0, 0,1,0, 0,0,1, 0,0,0,  0,0,1, 0,1,0, -1,0,0, 5,6,7,  .5f,.5f,0, -.5f,.5f,0, 0,0,1, 1,1,1};
        float all[3 * 12], each[3 * 12]; u8 ready_a[3]{}, ready_b[3]{};
        Frame g = f; g.mode = kSkin; g.palette = palette; g.palette_entries = 3;
        g.skin_dirs = all; g.dirs_ready = ready_a; probe_dirs_all(g, a);
        Frame h = g; h.skin_dirs = each; h.dirs_ready = ready_b;
        for (unsigned i = 0; i < 3; ++i) skin_light_dirs(h, a, i, nullptr);
        for (unsigned i = 0; i < 3; ++i) assert(ready_a[i] == 1 && ready_b[i] == 1);
        for (unsigned k = 0; k < 36; ++k) assert(near(all[k], each[k], 1e-7f));
    }
#if RE4DC_LEON_LIGHT_HEADROOM
    {   // a 2x-texture part outside the owner path (re4dc_model_submit's x0.5 record: tev_scale halved, marker [7]):
        // the fast fold runs at full scale with half_post; disabled lighting gives the halved constant
        SourceLighting s = base(1); s.normal_matrix[7] = 1.0e30f; s.tev_scale = 0.5f;
        s.lights[0].position[0] = 1100; s.lights[0].color[0] = 200; s.lights[0].color[1] = 150; s.lights[0].color[2] = 90;
        Re4dcModelPart p = part(s, &model_b, I);
        Lights L{};
        assert(build_lights(p, f, centre, L) && L.fast && L.half_post && near(L.color[12], 20.0f, 1e-3f));
        s.enable = 0;
        Lights c{};
        assert(build_lights(p, f, centre, c) && c.constant && !c.half_post && c.constant_rgb == 0x7F7F7FU);
        std::printf("PASS LEON_LIGHT_HEADROOM: source-path x0.5 record keeps the fast fold (half_post), constant 127\n");
    }
#endif
#if RE4DC_LEON_LIGHT_FILL
    {   // LEON_LIGHT_FILL=F: Leon's second direction points from the part origin to the camera, coloured F% of the
        // probe total (directional + ambient) at the probe's scale; Ganados (=2) and the probe direction are unchanged.
        constexpr float kF = RE4DC_LEON_LIGHT_FILL / 100.0f;
        SourceLighting s = base(1); s.normal_matrix[3] = 1.0e30f;
        s.lights[0].position[0] = 5100; s.lights[0].position[1] = -50; s.lights[0].position[2] = -900;  // +x, unit colour
        s.lights[0].color[0] = s.lights[0].color[1] = s.lights[0].color[2] = 220;
        ++frame_serial;
        Re4dcModelPart p = part(s, &model_a, I);
        Lights L{}; assert(probe_lights(p, f, L) && L.count == 2 && L.fast && L.probe);
        const float t = std::sqrt(100.0f * 100 + 50.0f * 50 + 900.0f * 900);
        const float cam[3] = {-100 / t, 50 / t, 900 / t};
        for (unsigned c = 0; c < 3; ++c) assert(near(L.dir[1][c], cam[c] * f.nq, 1e-6f));
        assert(near(L.dir[0][0], f.nq, 1e-6f) && near(L.dir[2][0], 0, 0) && near(L.view_dot[1], 1, 0));
        for (unsigned c = 0; c < 3; ++c) {
            const float expect = 0.5f * kF * (220.0f + s.ambient[c]) * kLeonGain;
            assert(near(L.color[4 + c], expect, 1e-3f) && near(L.color[8 + c], 0, 0));
            assert(near(L.color[c], 0.5f * 220.0f * kLeonGain, 1e-3f));             // the probe colour is unchanged
            assert(near(L.color[12 + c], s.ambient[c] * kLeonGain, 1e-3f));         // and its ambient
        }
        // the shared record keeps the probe's direction (the shadows lane), not the fill
        Re4dcLightProbe rec{};
        assert(re4dc_actor_light_probe(&model_a, &rec) == 1 && near(rec.dir[0], 1, 1e-6f) && near(rec.dir[2], 0, 1e-6f));
        // skinned parts: probe_dirs_all builds direction 1 per palette entry exactly as skin_light_dirs
        float palette[2 * 12] = {0,0,1, 0,1,0, -1,0,0, 5,6,7,  .5f,.5f,0, -.5f,.5f,0, 0,0,1, 1,1,1};
        float all[2 * 12], each[2 * 12]; u8 ready_a[2]{}, ready_b[2]{};
        Frame g = f; g.mode = kSkin; g.palette = palette; g.palette_entries = 2;
        g.skin_dirs = all; g.dirs_ready = ready_a; probe_dirs_all(g, L);
        Frame h = g; h.skin_dirs = each; h.dirs_ready = ready_b;
        for (unsigned i = 0; i < 2; ++i) skin_light_dirs(h, L, i, nullptr);
        for (unsigned k = 0; k < 24; ++k) assert(near(all[k], each[k], 1e-7f));
        assert(!near(all[4], 0, 1e-6f) || !near(all[5], 0, 1e-6f) || !near(all[6], 0, 1e-6f));
#if RE4DC_ACTOR_PROBE_LIGHT >= 2 && !(defined(RE4DC_GANADO_LIT_FILL) && RE4DC_GANADO_LIT_FILL > 0)
        SourceLighting gs = base(1);  // a Ganado (model id 0x12): one direction, no fill (unless GANADO_LIT_FILL)
        gs.lights[0].position[0] = 5100; gs.lights[0].color[0] = 220;
        Re4dcModelPart gp = part(gs, &model_b, I);
        Lights G{}; assert(probe_lights(gp, f, G) && G.count == 1 && near(G.color[4], 0, 0) && near(G.dir[1][0], 0, 0));
#endif
        std::printf("PASS LEON_LIGHT_FILL=%d: camera fill in direction 1 (Leon only), colour F%% of probe total, probe and shared record unchanged, palette directions\n", RE4DC_LEON_LIGHT_FILL);
    }
#endif
#if RE4DC_LEON_LIGHT_TOGGLE
    {   // LEON_LIGHT_TOGGLE: the four live modes on a Leon record
        SourceLighting s = base(1); s.normal_matrix[3] = 1.0e30f;
        s.lights[0].position[0] = 1100; s.lights[0].color[0] = 200; s.lights[0].color[1] = 150; s.lights[0].color[2] = 90;
        Re4dcModelPart p = part(s, &model_a, I);
        Lights L{};
        re4dc_leon_light_set(0); ++frame_serial;
        assert(part_lights(p, f, centre, L) && L.constant && L.constant_rgb == 0x808080U);          // FLAT
        re4dc_leon_light_set(3);                                                                     // FLAT WARM
        assert(part_lights(p, f, centre, L) && L.constant && L.constant_rgb == ((128U << 16) | (104U << 8) | 75U));
        re4dc_leon_light_set(2); ++frame_serial;                                                     // PROBE + HEADROOM
        assert(part_lights(p, f, centre, L) && !L.constant && L.probe && near(L.color[12], 10.0f, 1e-3f));
        re4dc_leon_light_set(1); ++frame_serial;                                                     // PROBE (full scale)
        assert(part_lights(p, f, centre, L) && !L.constant && near(L.color[12], 20.0f, 1e-3f));
        re4dc_leon_light_set(6); assert(re4dc_leon_light_mode == 2);
        std::printf("PASS LEON_LIGHT_TOGGLE: flat 128, warm hue, headroom x0.5, probe full scale\n");
    }
#endif
#if RE4DC_GANADO_LIT
    {   // GANADO_LIT: only the RE4DC_GANADO_LIT_NEAREST nearest crowd models are marked for the per-vertex probe light;
        // the next one keeps the mark while within 10% of the Nth's distance; a model first seen this frame is unmarked
        static int models[6];
        auto rank = [&](const float* d, unsigned n) {
            ++frame_serial;
            for (unsigned i = 0; i < n; ++i) {
                CrowdEntry* e = nullptr;
                for (unsigned k = 0; k < crowd_count; ++k) if (crowd[k].model == &models[i]) e = &crowd[k];
                if (!e) { e = &crowd[crowd_count++]; *e = CrowdEntry{&models[i], d[i], frame_serial, kTierNear}; }
                e->distance = d[i]; e->seen = frame_serial;
            }
            ++frame_serial; crowd_rank();
        };
        const int N = RE4DC_GANADO_LIT_NEAREST;
        const float d1[6] = {9000, 3000, 4000, 12000, 2500, 6000};  // nearest first: 4, 1, 2, 5, 0, 3
        rank(d1, 6);
        const unsigned order[6] = {4, 1, 2, 5, 0, 3};
        for (unsigned r = 0; r < 6; ++r) assert(crowd_lit(&models[order[r]]) == (N < 0 || int(r) < N));
        static int stranger;
        assert(!crowd_lit(&stranger));
        if (N >= 1) {   // hysteresis: the lit model falls to rank N but stays within 10% of the new Nth: kept
            const unsigned last = order[N - 1], next = order[N];
            float d2[6]; for (unsigned i = 0; i < 6; ++i) d2[i] = d1[i];
            d2[last] = d1[next]; d2[next] = d1[next] * 0.95f;  // the next one moves just ahead of it
            rank(d2, 6);
            assert(crowd_lit(&models[next]) && crowd_lit(&models[last]));
            d2[last] = d2[next] * 1.5f + 1000.0f;            // now clearly farther: dropped
            rank(d2, 6);
            assert(crowd_lit(&models[next]) && !crowd_lit(&models[last]));
        }
#if RE4DC_GANADO_LIT_TOGGLE
        SourceLighting gs = base(1); gs.lights[0].position[0] = 5100; gs.lights[0].color[0] = 220;
        Re4dcModelPart gp = part(gs, &model_b, I);
        re4dc_ganlit_set(0); ++frame_serial;
        Lights G0{}; assert(!probe_lights(gp, f, G0));                    // mode 0: Ganados off the probe (test 15)
        re4dc_ganlit_set(1); assert(ganlit_nearest == 0);                 // probe, every Ganado flat
        re4dc_ganlit_set(9); assert(ganlit_nearest == -1);                // every near-tier Ganado per vertex
        re4dc_ganlit_set(3); assert(ganlit_nearest == 2);
        Lights G1{}; ++frame_serial; assert(probe_lights(gp, f, G1) && G1.probe);
        re4dc_ganlit_set(N < 0 ? 9U : unsigned(N) + 1U);
#endif
#if RE4DC_GANADO_LIT_FILL
        {   // GANADO_LIT_FILL: a Ganado's second direction is the camera fill, F% of its probe total; Leon unchanged
#if RE4DC_GANADO_LIT_TOGGLE
            re4dc_ganlit_fill_set(40);
            const float F = 0.40f;
#else
            const float F = RE4DC_GANADO_LIT_FILL / 100.0f;
#endif
            SourceLighting fs = base(1); fs.lights[0].position[0] = 5100; fs.lights[0].position[2] = -900;
            fs.lights[0].color[0] = fs.lights[0].color[1] = fs.lights[0].color[2] = 220;
            Re4dcModelPart fp = part(fs, &model_b, I);
            ++frame_serial;
            Lights G{}; assert(probe_lights(fp, f, G) && G.count == 2 && near(G.view_dot[1], 1, 0));
            const float t = std::sqrt(100.0f * 100 + 50.0f * 50 + 900.0f * 900);
            const float cam[3] = {-100 / t, 50 / t, 900 / t};
            for (unsigned c = 0; c < 3; ++c) {
                assert(near(G.dir[1][c], cam[c] * f.nq, 1e-6f));
                assert(near(G.color[4 + c], 0.5f * F * (220.0f + fs.ambient[c]), 1e-3f));
            }
#if RE4DC_GANADO_LIT_TOGGLE
            re4dc_ganlit_fill_set(0);
            Lights Z{}; ++frame_serial; assert(probe_lights(fp, f, Z) && Z.count == 1);
#endif
            std::printf("PASS GANADO_LIT_FILL: camera fill in direction 1 for the probe-lit Ganados\n");
        }
#endif
        crowd_count = 0;
        std::printf("PASS GANADO_LIT nearest=%d: per-vertex mark on the N nearest, 10%% hysteresis, new models unmarked\n", N);
    }
#endif
    std::printf("PASS ACTOR_PROBE_LIGHT=%d: one-light parity with build_lights, folds, per-frame cache, Leon part basis, declines, palette directions, shared probe record, source immutable\n", RE4DC_ACTOR_PROBE_LIGHT);
}
'''

@unittest.skipUnless(shutil.which('g++'), 'host compiler required')
class ActorProbeLight(unittest.TestCase):
    def test_probe_on_actual_implementation(self):
        with tempfile.TemporaryDirectory() as temporary:
            t = Path(temporary); (t / 'dc').mkdir()
            (t / 'dc/pvr.h').write_text('#pragma once\n#include <cstddef>\n#include <cstdint>\nstruct pvr_vertex_t{std::uint32_t flags;float x,y,z,u,v;std::uint32_t argb,oargb;};\nstruct pvr_poly_hdr_t{std::uint32_t words[8];};\n#define PVR_CMD_VERTEX 0xe0000000U\n#define PVR_CMD_VERTEX_EOL 0xf0000000U\nint pvr_prim(const void*,std::size_t);\n')
            (t / 'fixture.cpp').write_text(FIXTURE.replace('ACTOR_IMPLEMENTATION', str(ROOT / 'port/dreamcast/game/platform/native_actor_fast.cpp')))
            # (level, extra defines): the probe alone, and with LEON_LIGHT_HEADROOM / LEON_LIGHT_TOGGLE
            for n, (level, extra) in enumerate(((1, []), (2, []), (1, ['-DRE4DC_LEON_LIGHT_HEADROOM=1']),
                                 (1, ['-DRE4DC_LEON_LIGHT_HEADROOM=1', '-DRE4DC_LEON_LIGHT_TOGGLE=1']),
                                 (1, ['-DRE4DC_LEON_LIGHT_HEADROOM=1', '-DRE4DC_LEON_LIGHT_FILL=45']),
                                 (2, ['-DRE4DC_LEON_LIGHT_FILL=30']),
                                 (2, ['-DRE4DC_GANADO_LIT=1', '-DRE4DC_GANADO_LIT_NEAREST=1']),
                                 (2, ['-DRE4DC_GANADO_LIT=1', '-DRE4DC_GANADO_LIT_NEAREST=2', '-DRE4DC_GANADO_LIT_TOGGLE=1', '-DRE4DC_GANADO_LIT_FILL=-1']),
                                 (2, ['-DRE4DC_GANADO_LIT=1', '-DRE4DC_GANADO_LIT_NEAREST=-1', '-DRE4DC_GANADO_LIT_FILL=40', '-DRE4DC_LEON_LIGHT_FILL=45']),
                                 (2, ['-DRE4DC_GANADO_LIT=1', '-DRE4DC_GANADO_LIT_NEAREST=0']))):
                exe = t / f'probe-{n}'
                cmd = ['g++', '-std=c++20', '-O2', '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections',
                       '-DRE4DC_LEON_SOURCE_LIGHT=1', f'-DRE4DC_ACTOR_PROBE_LIGHT={level}', *extra, '-I' + str(t),
                       '-I' + str(ROOT / 'port/dreamcast/game/platform/include'), str(t / 'fixture.cpp'),
                       str(ROOT / 'port/dreamcast/room/source_lighting.cpp'), '-o', str(exe)]
                c = subprocess.run(cmd, capture_output=True, text=True)
                self.assertEqual(c.returncode, 0, c.stderr)
                r = subprocess.run([str(exe)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                print(r.stdout.strip())


@unittest.skipUnless(shutil.which('make'), 'make required')
class ActorProbeLightKnobs(unittest.TestCase):
    def test_requirements(self):
        with tempfile.TemporaryDirectory() as temporary:
            mk = Path(temporary) / 'Makefile'
            mk.write_text('OBJDIR := obj\ninclude ' + str(ROOT / 'port/dreamcast/game/crowd.mk') + '\nall:\n\t@echo parsed\n')
            cases = [  # (knobs, error substring or None)
                ({'ACTOR_PROBE_LIGHT': '0'}, None),
                ({'ACTOR_PROBE_LIGHT': '3'}, 'ACTOR_PROBE_LIGHT must be 0, 1 or 2'),
                ({'ACTOR_PROBE_LIGHT': '1'}, 'ACTOR_PROBE_LIGHT needs LEON_SOURCE_LIGHT=1'),
                ({'ACTOR_PROBE_LIGHT': '1', 'LEON_SOURCE_LIGHT': '1'}, None),
                ({'ACTOR_PROBE_LIGHT': '2', 'LEON_SOURCE_LIGHT': '1'}, 'ACTOR_PROBE_LIGHT=2 needs PS2_GANADO_LIT=1 CROWD_LOD=1'),
                ({'LEON_LIGHT_HEADROOM': '1'}, None),
                ({'LEON_LIGHT_HEADROOM': '2'}, 'LEON_LIGHT_HEADROOM / LEON_LIGHT_TOGGLE are 0 or 1'),
                ({'LEON_LIGHT_TOGGLE': '1', 'LEON_LIGHT_HEADROOM': '1'}, 'needs LEON_LIGHT_HEADROOM=1 LOOK_TOGGLE=1 DBG_WARP=1'),
                ({'LEON_LIGHT_TOGGLE': '1', 'LEON_LIGHT_HEADROOM': '1', 'LOOK_TOGGLE': '1', 'DBG_WARP': '1'},
                 'LEON_LIGHT_TOGGLE=1 needs ACTOR_PROBE_LIGHT=1 or 2'),
                ({'LEON_LIGHT_TOGGLE': '1', 'LEON_LIGHT_HEADROOM': '1', 'LOOK_TOGGLE': '1', 'DBG_WARP': '1',
                  'ACTOR_PROBE_LIGHT': '1', 'LEON_SOURCE_LIGHT': '1'}, None),
                ({'LEON_LIGHT_FILL': '0'}, None),
                ({'LEON_LIGHT_FILL': '45'}, 'LEON_LIGHT_FILL needs ACTOR_PROBE_LIGHT=1 or 2'),
                ({'LEON_LIGHT_FILL': '101', 'ACTOR_PROBE_LIGHT': '1', 'LEON_SOURCE_LIGHT': '1'},
                 'LEON_LIGHT_FILL must be an integer 0..100'),
                ({'LEON_LIGHT_FILL': 'x', 'ACTOR_PROBE_LIGHT': '1', 'LEON_SOURCE_LIGHT': '1'},
                 'LEON_LIGHT_FILL must be an integer 0..100'),
                ({'LEON_LIGHT_FILL': '45', 'ACTOR_PROBE_LIGHT': '1', 'LEON_SOURCE_LIGHT': '1'}, None),
                ({'GANADO_LIT': '0'}, None),
                ({'GANADO_LIT': '2'}, 'GANADO_LIT / GANADO_LIT_TOGGLE are 0 or 1'),
                ({'GANADO_LIT': '1', 'ACTOR_PROBE_LIGHT': '1', 'LEON_SOURCE_LIGHT': '1'}, 'GANADO_LIT=1 needs ACTOR_PROBE_LIGHT=2'),
                ({'GANADO_LIT': '1', 'GANADO_LIT_NEAREST': '9', 'ACTOR_PROBE_LIGHT': '2', 'LEON_SOURCE_LIGHT': '1',
                  'PS2_GANADO_LIT': '1', 'CROWD_LOD': '1', 'PS2_GANADO': '1', 'GIGANTE_LIGHTS': '1'}, 'GANADO_LIT_NEAREST must be -1..7'),
                ({'GANADO_LIT': '1', 'ACTOR_PROBE_LIGHT': '2', 'LEON_SOURCE_LIGHT': '1', 'PS2_GANADO_LIT': '1',
                  'CROWD_LOD': '1', 'PS2_GANADO': '1', 'GIGANTE_LIGHTS': '1'}, None),
                ({'GANADO_LIT_FILL': '30'}, 'GANADO_LIT_FILL needs GANADO_LIT=1'),
                ({'GANADO_LIT': '1', 'GANADO_LIT_FILL': '101', 'ACTOR_PROBE_LIGHT': '2', 'LEON_SOURCE_LIGHT': '1', 'PS2_GANADO_LIT': '1',
                  'CROWD_LOD': '1', 'PS2_GANADO': '1', 'GIGANTE_LIGHTS': '1'}, 'GANADO_LIT_FILL must be an integer 0..100'),
                ({'GANADO_LIT_TOGGLE': '1', 'GANADO_LIT': '1', 'ACTOR_PROBE_LIGHT': '2', 'LEON_SOURCE_LIGHT': '1',
                  'PS2_GANADO_LIT': '1', 'CROWD_LOD': '1', 'PS2_GANADO': '1', 'GIGANTE_LIGHTS': '1'}, 'GANADO_LIT_TOGGLE=1 needs GANADO_LIT=1 DBG_WARP=1'),
            ]
            for knobs, err in cases:
                args = ['make', '-f', str(mk), '--dry-run', '--no-print-directory', 'all', 'ACTOR_TRANSACTION=1', 'LEON_NATIVE_PIPE=0']
                args += [f'{k}={v}' for k, v in knobs.items()]
                r = subprocess.run(args, capture_output=True, text=True)
                if err:
                    self.assertNotEqual(r.returncode, 0, knobs)
                    self.assertIn(err, r.stderr)
                else:
                    self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == '__main__':
    unittest.main()
