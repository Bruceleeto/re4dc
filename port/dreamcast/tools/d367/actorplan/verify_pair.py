#!/usr/bin/env python3
"""Reject a supposed switch comparison that actually built the same configuration.

verify_pair.py CONTROL_OUT CANDIDATE_OUT [--switch NAME ...] [--output JSON]
Uses resolved make values, compiler command lines, affected object code and the
loadable image. ELF debug paths are deliberately excluded from code identity.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import tempfile

SWITCHES = ('ACTOR_PROOF_LEAN', 'ACTOR_MATERIAL_RECORD', 'ACTOR_BIND_REUSE')
SOURCES = {'coarse_actor': 'coarse_actor.cpp', 'coarse_ganado': 'coarse_ganado_cast.cpp'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inspect(path, switches, tool_prefix):
    knobs = dict(line.split('=', 1) for line in (path / 'resolved-knobs.txt').read_text().splitlines() if '=' in line)
    lines = (path / 'build.log').read_text().splitlines()
    result = {'path': str(path), 'resolved': {k: knobs.get(k) for k in switches},
              'all_resolved': knobs, 'objects': {}}
    for name, source in SOURCES.items():
        command = next(line for line in lines if line.startswith('kos-c++ ') and ' -c ' + source + ' ' in line)
        argv = shlex.split(command)
        definitions = {k: next((a.split('=', 1)[1] for a in reversed(argv)
                                      if a.startswith('-DRE4DC_' + k + '=')), '0') for k in switches}
        code = subprocess.check_output([tool_prefix + 'objdump', '-dr', str(path / 'obj' / (name + '.o'))])
        # Only the first header line names the object path. The rest is code,
        # local labels and relocations, so path-only ELF changes pass while an
        # effective call/data-symbol target change remains visible.
        code = b'\n'.join(code.splitlines()[2:])
        result['objects'][name] = {'definitions': definitions, 'code_sha256': digest(code)}
    with tempfile.TemporaryDirectory(prefix='actor-switch-') as tmp:
        image = Path(tmp) / 'image.bin'
        subprocess.run([tool_prefix + 'objcopy', '-R', '.stack', '-O', 'binary',
                        str(path / 're4dc-game.elf'), str(image)], check=True)
        result['image_sha256'] = digest(image.read_bytes())
    result['elf_sha256'] = digest((path / 're4dc-game.elf').read_bytes())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('control', type=Path)
    parser.add_argument('candidate', type=Path)
    parser.add_argument('--switch', action='append')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--tool-prefix', default='sh-elf-',
                        help='SH-4 binutils prefix, optionally including a directory')
    args = parser.parse_args()
    switches = args.switch or SWITCHES
    control, candidate = (inspect(p, switches, args.tool_prefix) for p in (args.control, args.candidate))
    changed = [k for k in switches if control['resolved'][k] != candidate['resolved'][k]]
    errors = []
    if not changed:
        errors.append('No selected resolved knob differs; this is not an off/on experiment.')
    for arm in (control, candidate):
        for k in switches:
            # All three affect coarse_actor; BIND_REUSE also affects coarse_ganado.
            for obj in ('coarse_actor', 'coarse_ganado') if k == 'ACTOR_BIND_REUSE' else ('coarse_actor',):
                if arm['resolved'][k] != arm['objects'][obj]['definitions'][k]:
                    errors.append('%s: %s disagrees with %s compiler definition' % (arm['path'], k, obj))
    if control['image_sha256'] == candidate['image_sha256']:
        errors.append('Loadable images are identical; do not attribute a timing difference to these switches.')
    affected = sorted({obj for k in changed for obj in
                       (('coarse_actor', 'coarse_ganado') if k == 'ACTOR_BIND_REUSE' else ('coarse_actor',))})
    changed_objects = [obj for obj in affected
                       if control['objects'][obj]['code_sha256'] != candidate['objects'][obj]['code_sha256']]
    if changed and not changed_objects:
        errors.append('Requested switch objects have identical code; an unrelated image change does not qualify this pair.')
    other_changes = {k: [control['all_resolved'].get(k), candidate['all_resolved'].get(k)]
                     for k in sorted(set(control['all_resolved']) | set(candidate['all_resolved']))
                     if k not in switches and control['all_resolved'].get(k) != candidate['all_resolved'].get(k)}
    del control['all_resolved'], candidate['all_resolved']
    report = {'status': 'INVALID_PAIR' if errors else 'DISTINCT_PAIR', 'changed_switches': changed,
              'changed_affected_objects': changed_objects, 'other_resolved_changes': other_changes,
              'scope': 'Confirms selected definitions, affected object code and image differ. '
                       'Other recipe/source/asset differences still require review; this is not timing acceptance.',
              'control': control, 'candidate': candidate, 'errors': errors}
    text = json.dumps(report, indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    print(text, end='')
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
