#!/usr/bin/env python3
"""Run real AIC2 format/state tests; fixtures are private pinned evidence.

Does not build the game, replace assets, stage a runtime, or exercise hardware.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--sh4-cxx', default='/opt/toolchains/dc/sh-elf/bin/sh-elf-g++')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('output must be a new evidence directory')
    args.output.mkdir(parents=True)
    fixtures = args.fixtures.resolve()
    root = Path(__file__).resolve().parents[1]
    platform = root / 'game/platform'
    source = platform / 'aica_bank_v2_host.cpp'
    test = root / 'tests/aica_bank_v2_host_test.cpp'
    rows = json.loads((fixtures / 'banks.json').read_text())['banks']
    if len(rows) != 30:
        raise RuntimeError('all 30 pinned real banks are required; no skipped real tests')
    inputs = {}
    for path in sorted(fixtures.iterdir()):
        if path.is_file():
            inputs[str(path)] = dict(bytes=path.stat().st_size, sha256=sha(path))
    results = dict(status='HOST_ONLY', fixtures=inputs, commands=[])
    env = dict(os.environ, AIC2_FIXTURE_DIR=str(fixtures), PYTHONDONTWRITEBYTECODE='1')

    def run(name, command, command_env=env):
        result = subprocess.run(list(map(str, command)), capture_output=True, text=True, env=command_env)
        (args.output / (name + '.stdout')).write_text(result.stdout)
        (args.output / (name + '.stderr')).write_text(result.stderr)
        results['commands'].append(dict(name=name, argv=list(map(str, command)), returncode=result.returncode))
        if result.returncode:
            raise RuntimeError(name + ' failed: ' + result.stderr[-4000:])
        return result.stdout

    run('python-tests', [sys.executable, '-B', root / 'tests/test_aica_banks_v2.py'])
    python_log = (args.output / 'python-tests.stderr').read_text()
    if 'skipped' in python_log or '\nOK\n' not in python_log:
        raise RuntimeError('full Python suite did not run cleanly')
    cxx = shutil.which('g++')
    if not cxx:
        raise RuntimeError('g++ unavailable')
    flags = ['-std=c++17', '-Wall', '-Wextra', '-Werror', '-pedantic', '-DRE4DC_AICA_BANK_V2=1']
    run('host-compile', [cxx, *flags, '-O2', test, source, '-o', args.output / 'host-tests'])
    normal = json.loads(run('host-tests', [args.output / 'host-tests', fixtures]))
    run('sanitizer-compile', [cxx, *flags, '-O1', '-g', '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                              test, source, '-o', args.output / 'host-tests-sanitized'])
    sanitizer_env = dict(env, ASAN_OPTIONS='detect_leaks=1:halt_on_error=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
    sanitized = json.loads(run('sanitizer-tests', [args.output / 'host-tests-sanitized', fixtures], sanitizer_env))
    if normal != sanitized:
        raise RuntimeError('normal and sanitized results disagree')
    run('default-off-compile', [cxx, '-std=c++17', '-Wall', '-Wextra', '-Werror', '-c', source, '-o', args.output / 'default-off.o'])
    if run('default-off-nm', ['nm', '--defined-only', args.output / 'default-off.o']).strip():
        raise RuntimeError('default-off object contains defined symbols')
    # Standalone metadata object only. No game linker, source integration or KOS.
    sh4 = Path(args.sh4_cxx)
    if not sh4.is_file():
        raise RuntimeError('SH4 compiler required for the requested footprint confirmation')
    probe = args.output / 'metadata-sh4-probe.cpp'
    probe.write_text('#include "aica_bank_v2_host.h"\n'
                     'using namespace re4dc_aic2;\n'
                     'unsigned char aic2_core_metadata[sizeof(Core)];\n'
                     'unsigned char aic2_pool_metadata[sizeof(Pool)];\n'
                     'unsigned char aic2_mailbox_pair[sizeof(Request)+sizeof(Ack)];\n')
    target_flags = ['-std=c++17', '-m4-single-only', '-ml', '-ffreestanding', '-fno-exceptions', '-fno-rtti',
                    '-DRE4DC_AICA_BANK_V2=1', '-Wall', '-Wextra', '-Werror', '-I' + str(platform)]
    run('sh4-core-compile', [sh4, *target_flags, '-O2', '-c', source, '-o', args.output / 'core-sh4.o'])
    run('sh4-metadata-compile', [sh4, *target_flags, '-c', probe, '-o', args.output / 'metadata-sh4.o'])
    nm = str(sh4).replace('g++', 'nm')
    symbols = run('sh4-metadata-nm', [nm, '-S', '--defined-only', args.output / 'metadata-sh4.o'])
    sizes = {line.split()[-1]: int(line.split()[1], 16) for line in symbols.splitlines()}
    if sizes.get('_aic2_core_metadata', sizes.get('aic2_core_metadata')) != normal['metadata_bytes']:
        raise RuntimeError('SH4 metadata ABI differs from host')
    run('sh4-core-size', [str(sh4).replace('g++', 'size'), args.output / 'core-sh4.o'])
    run('host-compiler-version', [cxx, '--version'])
    run('sh4-compiler-version', [sh4, '--version'])
    results.update(python_summary=python_log.strip().splitlines()[-3:], cpp=normal, sh4_metadata_symbols=sizes,
                   hardware_inactivity_qualified=False, runtime_loader_integrated=False)
    (args.output / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(dict(output=str(args.output), cpp=normal, sh4_metadata_symbols=sizes)))


if __name__ == '__main__':
    main()
