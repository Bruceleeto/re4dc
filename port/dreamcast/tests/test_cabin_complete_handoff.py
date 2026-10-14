#!/usr/bin/env python3
"""Composed source/movie/UI scheduling regression; KOS/decoder services are seams.

Retains exact extracted function bodies, applied source hashes, compiler commands,
test executables and logs. No Dreamcast build or runtime acceptance is implied.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def digest(data):
    return hashlib.sha256(data).hexdigest()


def function(src, signature, occurrence=0):
    matches = list(re.finditer(r'^' + re.escape(signature) + r'\s*\([^;{]*\)\s*\{', src, re.M))
    assert len(matches) > occurrence, signature
    start = matches[occurrence].start()
    i = src.index('{', start) + 1
    depth = 1
    branches = []
    while depth:
        end = src.find('\n', i)
        if end < 0:
            end = len(src)
        line = src[i:end]
        directive = line.strip()
        if re.match(r'#if(?:n?def)?\b', directive):
            branches.append([depth, []])
        elif re.match(r'#el(?:se|if)\b', directive):
            branches[-1][1].append(depth)
            depth = branches[-1][0]
        elif directive.startswith('#endif'):
            before, alternatives = branches.pop()
            depth = max([depth, *alternatives])
        else:
            for n, char in enumerate(line):
                depth += (char == '{') - (char == '}')
                if depth == 0:
                    return src[start:i+n+1] + '\n'
        i = end + 1
        assert i < len(src), signature
    return src[start:i] + '\n'


def block(src, name):
    return src.split('// ' + name + '_BEGIN\n', 1)[1].split('// ' + name + '_END', 1)[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--baseline', default='4e809c37b098628d009e459293bfd691688172b2')
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    root = Path(__file__).resolve().parents[3]
    paths = {
        'ui': 'port/dreamcast/game/platform/native_ui.cpp',
        'movie': 'port/dreamcast/game/platform/native_movie.cpp',
        'cabin': 'port/dreamcast/game/platform/native_cabin.cpp',
        'world': 'port/dreamcast/game/platform/native_ps2_world.cpp',
        'header': 'port/dreamcast/game/platform/include/native_cabin.h',
        'make': 'port/dreamcast/game/Makefile',
        'main': 'src/game/main.cpp', 'render': 'src/game/main_sub.cpp',
        'r11c': 'src/st1/r11c.cpp',
        'fixture': 'port/dreamcast/tests/fixtures/cabin_complete_handoff.cpp',
        'test': 'port/dreamcast/tests/test_cabin_complete_handoff.py',
    }
    src = {}
    pins = {}
    for key, path in paths.items():
        data = (root / path).read_bytes()
        pins[path] = digest(data)
        dst = out / 'sources' / path
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data)
        src[key] = data.decode()
    # Pin the real source task order; the host scheduler reproduces this order
    # while replacing unrelated render work and OS task switching with seams.
    schedule = ['Render_before();', 'Render();', 'TaskScheduler();', 'Render_swap();']
    positions = [src['main'].index(statement, src['main'].index('Render_before();')) for statement in schedule]
    assert positions == sorted(positions)
    extracts = {}

    def take(key, signature, occurrence=0):
        result = function(src[key], signature, occurrence)
        extracts[f'{key}:{signature}:{occurrence}'] = digest(result.encode())
        return result

    # The conditional signature shares one body in the production file.
    src['ui'] = src['ui'].replace('static int movie_cabin_ui_try_close_body(){\n#else\nextern "C" int re4dc_ui_movie_try_close(){\n#endif', 'static int movie_cabin_ui_try_close_body(){')
    ui = block(src['ui'], 'CABIN_UI_STATE')
    ui += '#define reset_deferred actual_reset_deferred\n' + take('ui','void reset_deferred') + '#undef reset_deferred\n'
    ui += 'void reset_deferred(){++reset_count;actual_reset_deferred();}\n'
    ui += '#define re4dc_ps2_world_movie_discard actual_world_movie_discard\n' + take('world','extern "C" void re4dc_ps2_world_movie_discard') + '#undef re4dc_ps2_world_movie_discard\n'
    ui += 'void re4dc_ps2_world_movie_discard(){++discarded;actual_world_movie_discard();}\n'
    ui += take('ui', 'void present_report')
    ui += take('ui', 'void present_fence', 0)
    ui += take('ui', 'void present_submit', 0)
    ui += take('ui', 'void stream_open') + take('ui', 'void stream_close')
    ui += take('ui', 'static int movie_cabin_ui_try_close_body')
    ui += block(src['ui'], 'CABIN_UI_API')
    ui += take('ui', 'extern "C" int re4dc_ui_movie_open')
    ui += take('ui', 'extern "C" int re4dc_ui_movie_close')
    # Exact frame-end rendering branch, excluding unrelated diagnostic stats.
    end = take('ui', 'extern "C" void re4dc_ui_end_frame')
    end = end[:end.index('    for(const auto& e:entries)')] + '}\n'
    extracts['ui:end_frame_render_branch'] = digest(end.encode())
    ui += end
    movie = block(src['movie'], 'CABIN_MOVIE_STATE')
    movie += take('movie', 'bool cabin_movie_identity')
    for sig in ['extern "C" int re4dc_movie_cabin_skip', 'extern "C" int re4dc_movie_cabin_step',
                'extern "C" int re4dc_movie_cabin_abort', 'extern "C" int re4dc_movie_cabin_status',
                'extern "C" int re4dc_movie_cabin_close']:
        movie += take('movie', sig)
    movie += '#if RE4DC_CABIN_COMPLETE_HANDOFF\n'
    movie += take('movie', 'static int cabin_movie_complete_qualified')
    movie += take('movie', 'extern "C" int re4dc_movie_cabin_complete_current')
    movie += take('movie', 'extern "C" int re4dc_movie_cabin_complete') + '#endif\n'
    cabin = re.sub(r'^#include[^\n]*\n', '', src['cabin'], flags=re.M)
    render = take('render', 'void Render_before') + take('render', 'void Render_swap')
    render += take('r11c', 'static void r11c_cabin_done')
    generated = src['fixture']
    for marker, value in [('HEADER',src['header']), ('UI',ui), ('MOVIE',movie), ('CABIN',cabin), ('RENDER',render)]:
        assert generated.count('// @' + marker + '@') == 1
        generated = generated.replace('// @' + marker + '@', value)
    cpp = out / 'composed.cpp'
    cpp.write_text(generated)
    report = {'sources': pins, 'extractions': extracts, 'generated_sha256':digest(generated.encode()),
              'schedule': dict(zip(schedule,positions)), 'runs': [],
              'limits': 'Actual selected source bodies with KOS, decoder, unrelated render/OS scheduling service seams; no target build or runtime evidence.'}
    # Full-body OFF preprocessing checks retain the D54 baseline and commands.
    # Includes are removed equally because these are source-selection checks,
    # not replacements for the later authorized target compiler/link checks.
    report['baseline'] = args.baseline
    report['off_checks'] = []
    for key in ['ui','movie','cabin','header']:
        path = paths[key]
        baseline = subprocess.check_output(['git','-C',str(root),'show',f'{args.baseline}:{path}'])
        basepath = out / 'baseline' / path
        basepath.parent.mkdir(parents=True,exist_ok=True)
        basepath.write_bytes(baseline)
        for cabin_on in [0,1]:
            for pipeline in [0,1,2]:
                for recover in [0,1]:
                    if recover and pipeline!=2:
                        continue
                    flags = ['-DRE4DC_CABIN_COMPLETE_HANDOFF=0',f'-DRE4DC_CABIN_SOURCE={cabin_on}',
                             '-DRE4DC_ROUTE_MOVIES=1','-DRE4DC_PVR_STREAM=1','-DRE4DC_D349_RENDERER_STACK=1',
                             '-DRE4DC_TEX_RESIDENT=1',f'-DRE4DC_PVR_PIPELINE={pipeline}',f'-DRE4DC_PVR_RECOVER={recover}',
                             f'-DRE4DC_PVR_READY_STRICT={recover}']
                    results=[]
                    commands=[]
                    for label,data in [('base',baseline),('applied',(root/path).read_bytes())]:
                        inp=out/f'off-{key}-{cabin_on}-{pipeline}-{recover}-{label}.cpp'
                        inp.write_text(re.sub(r'^#include[^\n]*\n','',data.decode(),flags=re.M))
                        cmd=['g++','-E','-P','-x','c++',*flags,str(inp)]
                        commands.append(cmd)
                        result=subprocess.run(cmd,text=True,capture_output=True)
                        assert result.returncode==0,result.stderr
                        results.append(result.stdout)
                    assert results[0]==results[1],(key,cabin_on,pipeline,recover,'OFF source changed')
                    report['off_checks'].append({'source':path,'commands':commands,'sha256':digest(results[0].encode())})
    # Legacy strict retirement bodies must remain byte-for-byte unchanged.
    report['unchanged_functions'] = []
    for key,signature in [('cabin','extern "C" int re4dc_cabin_before_heap_change'),
                          ('movie','extern "C" int re4dc_movie_cabin_close'),
                          ('ui','extern "C" int re4dc_ui_movie_close')]:
        old=(out/'baseline'/paths[key]).read_text()
        new=(root/paths[key]).read_text()
        a,b=function(old,signature),function(new,signature)
        assert a==b,signature
        report['unchanged_functions'].append({'signature':signature,'sha256':digest(a.encode())})
    # Exercise the actual Makefile policy and header recipe without compiling.
    fragment=src['make'].split('CABIN_SOURCE ?= 0\n',1)[1].split('CABIN_SOURCE_PLATFORM =',1)[0]
    makefile=out/'cabin-policy.mk'
    makefile.write_text('CABIN_SOURCE ?= 0\n'+fragment)
    report['make_checks']=[]
    for name,assignments,expected in [
        ('default',[],0),('requires-source',['CABIN_COMPLETE_HANDOFF=1'],2),
        ('reject-value',['CABIN_COMPLETE_HANDOFF=2'],2),
        ('enabled',['CABIN_SOURCE=1','CABIN_COMPLETE_HANDOFF=1','ROUTE_CH22=1','ROUTE_MOVIES=1',
                    'AICA_AUDIO=1','AICA_STREAMS=1','NATIVE_STATIC=1'],0)]:
        objdir=out/f'make-{name}'
        cmd=['make','--no-print-directory','-f',str(makefile),f'OBJDIR={objdir}',*assignments,str(objdir/'cabin-source.h')]
        result=subprocess.run(cmd,text=True,capture_output=True)
        (out/f'make-{name}.log').write_text(result.stdout+result.stderr)
        assert result.returncode==expected,(name,result.stdout,result.stderr)
        report['make_checks'].append({'command':cmd,'returncode':result.returncode})
        if expected==0:
            content=(objdir/'cabin-source.h').read_text()
            assert '#define RE4DC_CABIN_COMPLETE_HANDOFF '+('1' if name=='enabled' else '0')+'\n' in content
    for enabled, recover in [(0,0),(1,0),(1,1)]:
        name = f'handoff-{enabled}-recover-{recover}'
        exe = out / name
        cmd = ['g++','-std=gnu++17','-O1','-g','-fsanitize=address,undefined','-fno-sanitize-recover=all',
               '-fno-omit-frame-pointer','-fno-pie','-no-pie',f'-DRE4DC_CABIN_COMPLETE_HANDOFF={enabled}',
               f'-DRE4DC_PVR_RECOVER={recover}',str(cpp),'-o',str(exe)]
        result = subprocess.run(cmd, text=True, capture_output=True)
        (out / (name + '.build.log')).write_text(result.stdout + result.stderr)
        row = {'name':name,'command':cmd,'build_returncode':result.returncode}
        report['runs'].append(row)
        if result.returncode:
            (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
            raise RuntimeError(result.stderr)
        result = subprocess.run([str(exe)], text=True, capture_output=True)
        (out / (name + '.run.log')).write_text(result.stdout + result.stderr)
        row.update(run_returncode=result.returncode, binary_sha256=digest(exe.read_bytes()))
        print(result.stdout + result.stderr, end='')
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
        assert result.returncode == 0, name
    print('PASS composed cabin completion host regression')


if __name__ == '__main__':
    main()
