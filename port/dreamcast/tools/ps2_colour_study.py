#!/usr/bin/env python3
"""PS2 scenario vertex-colour study (the r100 "saturated colours" question): per room and per SMX / SMD type,
how bright the authored COLOR-group vertex colours are (exported /128, so 1.0 = GS 0x80 = texel unchanged under
GS modulate, 2.0 = 0xFF), with the SMX row fields next to them.

usage: ps2_colour_study.py <inputs root> [<inputs root> ...] [--json out.json]
(one <root>/<room>/ per room, as ps2_room_extract.py writes; Windows Python like ps2_room_r4im.py)
"""
import argparse, collections, json, re, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ps2_room_r4im as R  # noqa: E402


def room_rows(room, src):
    obj = R.ps.read_obj(src / f'{room}_004.scenario.obj')
    smx = R.ps.smx_entries(src / f'{room}_005.SMX', False)
    VC = np.asarray([c if c is not None else (1, 1, 1, 1) for c in obj['vc']], np.float64)
    rows = []
    for g in obj['groups']:
        if g['kind'] != 'COLOR':
            continue
        ix = np.asarray([f for f, _ in g['faces']], int)[:, :, 0].ravel()
        c = VC[ix, :3]
        typ = re.search(r'TYPE_([0-9A-F]{2})', g['name'])
        sem = smx.get(g['smx'], {})
        rows.append(dict(group=g['name'], smx=g['smx'], type=typ.group(1) if typ else '?', corners=len(ix),
                         median=float(np.median(c.max(1))), p90=float(np.percentile(c.max(1), 90)),
                         sat=float((c.max(1) > 1.9).mean()), mode=sem.get('mode'),
                         light=sem.get('light_switch'), smx_rgb=tuple(sem.get('smx_colour_rgb', ())),
                         opacity=sem.get('opacity_hierarchy'), alpha=sem.get('alpha_hierarchy')))
    return rows


def summarise(rows, key):
    acc = collections.defaultdict(lambda: [0, [], 0.0])
    for r in rows:
        k = r[key]
        acc[k][0] += r['corners']
        acc[k][1].append(r['median'])
        acc[k][2] += r['sat'] * r['corners']
    return {str(k): dict(corners=v[0], groups=len(v[1]), median_of_group_medians=round(float(np.median(v[1])), 3),
                         saturated_share=round(v[2] / max(v[0], 1), 3)) for k, v in sorted(acc.items(), key=str)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('roots', nargs='+', type=Path)
    ap.add_argument('--json', type=Path)
    a = ap.parse_args()
    out = {}
    for root in a.roots:
        for src in sorted(p for p in root.iterdir() if p.is_dir()):
            room = src.name
            if not (src / f'{room}_004.scenario.obj').exists() or room in out:
                continue
            rows = room_rows(room, src)
            allc = sum(r['corners'] for r in rows)
            med = float(np.median(np.repeat([r['median'] for r in rows], [max(1, r['corners'] // 100) for r in rows])))
            sat = sum(r['sat'] * r['corners'] for r in rows) / max(allc, 1)
            out[room] = dict(groups=len(rows), corners=allc, median=round(med, 3), saturated_share=round(sat, 3),
                             by_type=summarise(rows, 'type'), by_light=summarise(rows, 'light'),
                             by_mode=summarise(rows, 'mode'), by_smx_rgb=summarise(rows, 'smx_rgb'), rows=rows)
            print('%s groups %3d median %.2f saturated %.2f  types %s  light %s' % (
                room, len(rows), med, sat,
                {k: (v['median_of_group_medians'], v['saturated_share']) for k, v in out[room]['by_type'].items()},
                {k: (v['median_of_group_medians'], v['groups']) for k, v in out[room]['by_light'].items()}))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
