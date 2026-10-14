"""ACTOR_PROBE_LIGHT (lane lp2): the per-actor light probe on the actual native-actor implementation.

Checks, for ACTOR_PROBE_LIGHT=1 and =2: one light reproduces build_lights' fold exactly (direction, colour, ambient);
lights on one side fold into one direction with the residual in the ambient; opposite equal lights give ambient only;
the probe is built once per (model, record, frame) and reused by the actor's other parts; Leon's per-part normal basis
is applied; Ganado ids are taken only at =2; unsupported records (tinted material, disabled lighting, per-vertex colour)
decline to build_lights; the source record is never written. A Make parse test checks the knob's requirements.
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
        assert(build_lights(p, f, centre, b) && b.count == 1 && a.count == 1 && a.fast && a.probe && !a.constant);
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
            for level, extra in ((1, []), (2, []), (1, ['-DRE4DC_LEON_LIGHT_HEADROOM=1']),
                                 (1, ['-DRE4DC_LEON_LIGHT_HEADROOM=1', '-DRE4DC_LEON_LIGHT_TOGGLE=1'])):
                exe = t / f'probe-{level}-{len(extra)}'
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
