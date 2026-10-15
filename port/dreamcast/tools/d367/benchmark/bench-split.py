#!/usr/bin/env python3
"""bench-split.py HWMODEL_DIR... [--top N]: the per-frame CPU breakdown of hwproject runs by subsystem (lane crowd12).

Reads <dir>/proj/rep/functions.tsv (hw ms per frame per function, SH-4 hardware model = MODELLED) and sums the
functions into the buckets below, by function name and source file (first matching rule wins). The wait rows
(main, re4dc_pace_end, re4dc_vi_retrace_count) are left out: work only. Shared helpers called from every subsystem
(matrix maths, sin/cos, memcpy) cannot be attributed to a caller from a flat profile; they get their own bucket.
--top N lists each bucket's N heaviest functions. --tsv prints one machine-readable row per run.
"""
import csv
import re
import sys
from pathlib import Path

WAIT = {'main', 're4dc_pace_end', 're4dc_vi_retrace_count'}
# (bucket, regex on "name|file"); first match wins. Order matters (skinning before actor submit, etc.).
RULES = [
    ('effects update', r'^(cEsp\w*::(move|AnmMove|CommonMove|moveSub\w*)|EspMove\w*|EspSet\w*|EspCreate|idSysMove\w*|'
                       r'IDSystem::move\w*|ESP_IsActive|EspKill\w*|cEspMgr::move\w*|EspCheck\w*)\b'),
    ('effects setup+submit', r'^(EspTrans|EspCommonTrans|EspSpriteEligible|Ps2fxClass|cEsp\w*::ChannelSet|IDSystem::trans|'
                             r're4dc_esp_\w+|re4dc_effect\w*|re4dc_fx\w*|re4dc_draw_id_quad|re4dc_hwfog\w*|re4dc_haze\w*|'
                             r'Esp\w*Trans\w*|cEsp\w*::trans\w*|EspDraw\w*|IdSys\w*Draw\w*)|\|.*(esp|id_sys|ps2fx|effect|hwfog)\w*\.(cpp|inc)$'),
    ('skinning', r'^(re4dc_avk_\w*skin\w*|re4dc_coarse_skin\w*|re4dc_sk1_\w+|re4dc_actor_skin\w*|re4dc_skin\w*)\b'),
    ('motion/animation', r'^(Motion\w*|MotLink\w*|Mot\w*|InverseKinematics|PartsWorldPosCalc|cModel::\w+|re4dc_pwc_\w+|'
                         r're4dc_pmc_\w+|PenCloth\w*|penCloth\w*|SeqMove\w*|quat\w*|C_QUAT\w*|PSQUAT\w*)|'
                         r'\|.*/(motion|model|ik|pendulum|quat)\.(cpp|c)$'),
    ('enemy logic/AI', r'^(cEm\w*::\w+|em\w+|Em\w+|__em_\w+|At_em_\w+|GetEmPtr\w*|r10\d\w*|cEmMgr\w*)|\|.*/em\w*\.(cpp|inc)$'),
    ('collision', r'^(At_\w+|re4dc_line_\w+|re4dc_sphere_walk|collision_\w+|ObjHitCheck|areaHitCheck\w*|getNearPoint|'
                  r'Sat\w*|cSat\w*|AtCk\w*)|\|.*/(at_mod|atari|at_sub|sce_at)\.cpp$'),
    ('actor submit', r'^(re4dc_actor_\w+|re4dc_avk_\w+|re4dc_draw_model\w*|re4dc_model_\w+|ModelRender\w*|ModelTrans\w*|'
                     r'Trans|LightSetModel|cLightMgr::\w+|lightSet\w*|re4dc_prepare_model\w*|re4dc_material\w*|'
                     r're4dc_mv_\w+|AddOtModel\w*|re4dc_coarse_\w+|re4dc_leon\w*|re4dc_probe\w*)\b|'
                     r'\|.*/(actor_lifetime|coarse_actor\w*|native_actor\w*|trans_lit|model_bridge|light)\.(inc|cpp)$'),
    ('world submit', r'^(re4dc_ps2_world\w*|re4dc_ps2_dyn\w*|re4dc_static\w*|re4dc::render::\w+|re4dc::texture::\w+|'
                     r're4dc_world\w*|re4dc_scenery\w*|re4dc_mesh\w*)|\|.*/(native_static|texture_package|pvr_geometry|'
                     r'mesh\w*|instanced_mesh\w*|ps2_world\w*)\.(cpp|hpp|inc)$'),
    ('frame/TA/UI overhead', r'^(ExecOt|clearOtWork|GetPrimBuff|sq_\w+|pvr_\w+|OSCheckHeap|GX\w+|AddOtWorld\w*|'
                             r'commonScreenMat\w*|re4dc_ui\w*)|\|.*/(native_ui|trans_ot|gx_stub|ui_bridge|pvr\w*)\.(cpp|c)$'),
    ('kos/sound/idle', r'^(Snd\w*|iss_\w+|snd\w*|mutex_\w+|genwait\w*|thd_\w+|irq_\w+|save_regs\w*|__dreamcast\w*|g2_\w+|'
                       r'timer_\w+|sem_\w+|cond_\w+|aica\w*)|\|.*/(thread|kernel|arch|snd_\w+|audio\w*)/'),
    ('shared math/copies', r'^(PSMTX\w*|PSVEC\w*|RotVector|sinf|cosf|acosf|asinf|atan2f|sqrtf|SQRTF|SINF|COSF|re4dc_sincosf|'
                           r'memcpy|memset|memcmp|memmove|L_\w+|__\w*div\w*|low_RotMatrix|RotMatrix\w*|VecRadLimit|'
                           r'GetDistance\w*|_svfprintf_r|vsnprintf|snprintf)\b|\|.*/(math_sub|mtx|vec|game30_trig)\.(cpp|c)$'),
    ('player/scene/other logic', r'^(cPl\w*::\w+|pl\w+|cObjMgr::\w+|obj\w+|Sce\w*|sce\w*|cCam\w*|Cam\w*|cGame\w*)|'
                                 r'\|.*/(pl\w*|obj|sub2|sce\w*|cam\w*|game)\.(cpp|inc)$'),
]
COMPILED = [(b, re.compile(r)) for b, r in RULES]
ORDER = ['enemy logic/AI', 'motion/animation', 'skinning', 'effects update', 'effects setup+submit', 'world submit',
         'actor submit', 'collision', 'player/scene/other logic', 'frame/TA/UI overhead', 'kos/sound/idle',
         'shared math/copies', 'unclassified']


def bucket(name, path):
    key = f'{name}|{path}'
    for b, r in COMPILED:
        if r.search(key):
            return b
    return 'unclassified'


def split(d):
    rows = list(csv.DictReader((Path(d) / 'proj/rep/functions.tsv').open(encoding='utf-8'), delimiter='\t'))
    out, funcs = {}, {}
    for r in rows:
        if r['func'] in WAIT:
            continue
        b = bucket(r['func'], r.get('file', ''))
        ms = float(r['hw_ms'])
        out[b] = out.get(b, 0.0) + ms
        funcs.setdefault(b, []).append((ms, r['func']))
    return out, funcs


def main():
    top = int(sys.argv[sys.argv.index('--top') + 1]) if '--top' in sys.argv else 0
    dirs = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith('--') and sys.argv[i - 1] != '--top']
    res = [(d, *split(d)) for d in dirs]
    names = [Path(d).name.replace('hwmodel-', '') for d in dirs]
    print('| bucket (hw ms per frame, MODELLED) | ' + ' | '.join(names) + ' |')
    print('|---|' + '---|' * len(names))
    for b in ORDER:
        print(f'| {b} | ' + ' | '.join(f"{o.get(b, 0.0):.2f}" for _, o, _ in res) + ' |')
    print('| **total work** | ' + ' | '.join(f"**{sum(o.values()):.2f}**" for _, o, _ in res) + ' |')
    if top:
        for d, o, f in res:
            print(f'\n{Path(d).name}:')
            for b in ORDER:
                if b in f:
                    fs = sorted(f[b], reverse=True)[:top]
                    print(f'  {b} {o[b]:.2f}: ' + ', '.join(f'{n[:40]} {m:.2f}' for m, n in fs))


if __name__ == '__main__':
    main()
