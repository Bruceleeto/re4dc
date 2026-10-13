#!/usr/bin/env python3
"""Audit render-only PS2 room recipes against bounded GC/PS2 EFF records.

Reads private extracted EFF files; it never edits a room archive or stages game
assets. Undecoded sequence-table variants are reported separately, never treated
as empty. The runtime retains GC simulation, textures, RNG and effect-pool work.
"""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import struct


RECORD_SIZE = 0x12C
HAZE_PAIRS = (
    ('r102', (0, 'sst', 2, 0), (0, 'sst', 0, 1)),
    ('r104', (0, 'sst', 0, 0), (0, 'sst', 0, 1)),
    ('r105', (0, 'sst', 4, 0), (0, 'sst', 4, 0)),
    ('r105', (0, 'sst', 5, 0), (0, 'sst', 5, 0)),
    ('r107', (0, 'sst', 0, 0), (0, 'sst', 9, 2)),
    ('r107', (0, 'sst', 8, 0), (0, 'sst', 8, 0)),
)
STREAK_CUTS = (
    ('r102', (0, 'sst', 1, 14)),
    ('r104', (0, 'sst', 0, 6)),
    ('r107', (0, 'sst', 3, 2)),
)
SHEET_CUTS = (('r105', 0x48, 0xD0), ('r107', 0x48, 0xD0))
FORMERLY_UNDECODED = ('r109', 'r10f', 'r11e', 'r200')
INVENTORY_ROOMS = tuple('r100 r101 r102 r103 r104 r105 r106 r107 r108 r109 r10a r10b r10c r10d r10e r10f '
                        'r111 r112 r113 r117 r118 r119 r11a r11b r11c r11d r11e r11f r200'.split())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def decode_eff(data, endian):
    """Read the established v0xB sequence layout, refusing unsupported bounds.

    Texture/path sections are outside this audit; no image-size inference is
    made from their headers. All sequence tables and record spans are checked.
    """
    if endian not in ('>', '<'):
        raise ValueError('endian must be > or <')

    def read(fmt, offset):
        width = struct.calcsize(endian + fmt)
        if offset < 0 or offset + width > len(data):
            raise ValueError('EFF field outside file at 0x%x' % offset)
        return struct.unpack_from(endian + fmt, data, offset)

    header = read('12I', 0)
    if header[0] != 0xB:
        raise ValueError('unsupported EFF version 0x%x' % header[0])
    result = []
    for kind, list_offset, data_offset in (('est', header[2], header[8]), ('sst', header[3], header[9])):
        # Optional table sections use either two null offsets (PS2) or an
        # explicit zero-count list with null data (GC). A populated list with
        # absent data is incomplete, not an empty sequence inventory.
        if not list_offset and not data_offset:
            continue
        if not list_offset:
            raise ValueError('missing %s list with nonzero data offset' % kind)
        count, = read('I', list_offset)
        if not data_offset:
            if count:
                raise ValueError('missing %s data for populated list' % kind)
            continue
        data_count, = read('I', data_offset)
        if count != data_count:
            raise ValueError('%s list/data counts differ: %d/%d' % (kind, count, data_count))
        if count > (len(data)-list_offset-4)//8 or count > (len(data)-data_offset-4)//4:
            raise ValueError('%s table exceeds EFF bounds' % kind)
        floor = data_offset + 4 + 4*count
        spans = []
        for i in range(count):
            no, area, flags = read('HHI', list_offset+4+8*i)
            relative, = read('I', data_offset+4+4*i)
            offset = data_offset + relative
            if offset < floor:
                raise ValueError('%s sequence overlaps offset table' % kind)
            number, = read('H', offset)
            end = offset + 0x30 + RECORD_SIZE*number
            if end > len(data):
                raise ValueError('%s sequence records exceed EFF bounds' % kind)
            if any(offset < b and a < end for a, b in spans):
                raise ValueError('%s sequence records overlap' % kind)
            spans.append((offset, end))
            for index in range(number):
                r = offset+0x30+RECORD_SIZE*index
                identity = read('4B', r)
                values = {
                    'table': kind, 'no': no, 'area': area, 'list_flags': flags,
                    'index': index, 'offset': r, 'record_sha256': sha(data[r:r+RECORD_SIZE]),
                    'be_flags': identity[0], 'id': identity[1], 'tex': identity[2], 'type': identity[3],
                    'range': read('f', r+0x20)[0], 'size_x': read('f', r+0x88)[0],
                    'size_y': read('f', r+0x8C)[0], 'size_plus': read('f', r+0x94)[0],
                    'd_size_plus': read('f', r+0x98)[0], 'rgba': list(read('4B', r+0x9C)),
                    'life_max': read('H', r+0xB8)[0], 'blend': read('B', r+0xC2)[0],
                    'del_far': read('B', r+0xC6)[0], 'del_near': read('B', r+0xC7)[0],
                    'work8': list(read('4B', r+0xC8)), 'kind': read('B', r+0x108)[0],
                    'generator': read('B', r+0x109)[0], 'count_per_emission': read('B', r+0x10D)[0]+1,
                }
                result.append(values)
    return result


def steady_size(record):
    fields = [record[k] for k in ('size_x', 'size_plus', 'd_size_plus')]
    if not all(math.isfinite(v) for v in fields) or fields[0] <= 0 or not 0 <= fields[2] < 1:
        raise ValueError('unsupported haze size recurrence')
    result = fields[0]*(1+fields[1]/(1-fields[2]))
    if not math.isfinite(result) or result <= 0:
        raise ValueError('nonpositive haze steady size')
    return result


def haze_recipe(gc, ps2):
    for record in (gc, ps2):
        if record['id'] != 0x15 or record['kind'] != 1 or record['generator'] != 0:
            raise ValueError('expected camera-haze generator 0')
        if not math.isfinite(record['range']) or record['range'] <= 0:
            raise ValueError('invalid haze source box')
    if gc['tex'] != ps2['tex']:
        raise ValueError('texture changed; size-only recipe needs separate texture audit')
    # The existing renderer clips source positions; a larger PS2 box cannot
    # create source particles outside the GC box. This is a count estimate.
    admitted = gc['count_per_emission']*min(1, ps2['range']/gc['range'])**3
    count = ps2['count_per_emission']
    every = min(range(1, 256), key=lambda stride: (abs(admitted/stride-count), stride))
    far, near = ps2['work8'][:2]
    if not 0 <= near < far < 128:
        raise ValueError('unsupported signed near-fade range')
    if ps2['work8'][2] != 30:
        raise ValueError('existing renderer requires PS2 far fade over final 30 percent')
    return {
        'every': every, 'gc_rgb_selector': gc['rgba'][:3], 'gc_range_selector': gc['range'],
        'ps2_rgba': ps2['rgba'], 'ps2_range': ps2['range'],
        'steady_size_ratio': steady_size(ps2)/steady_size(gc),
        'near_far_mm': far*100, 'near_near_mm': near*100,
        'gc_emitted_per_generator_step': gc['count_per_emission'],
        'ps2_emitted_per_generator_step': count,
        'estimated_draw_subset_per_emission': admitted/every,
        'larger_ps2_box_not_repopulated': ps2['range'] > gc['range'],
        'scope': 'statistical draw subset; not an exact active-sprite count or a runtime measurement',
    }


def streak_signature(record):
    return (record['tex'], record['blend'], record['del_far'], record['del_near'])


def audit(cache):
    rooms = sorted({row[0] for row in HAZE_PAIRS})
    records, inputs = {}, []
    for room in rooms:
        for side, endian in (('gc', '>'), ('ps2', '<')):
            all_records = []
            paths = sorted(cache.glob('%s.%s.eff[0-9]' % (room, side)))
            if not paths:
                raise ValueError('missing extracted EFF for %s %s' % (room, side))
            for path in paths:
                data = path.read_bytes()
                inputs.append({'path': str(path), 'bytes': len(data), 'sha256': sha(data)})
                eff = int(path.name.rsplit('eff', 1)[1])
                for record in decode_eff(data, endian):
                    all_records.append(dict(record, eff=eff, source=str(path)))
            records[room, side] = all_records

    def select(room, side, reference):
        eff, table, number, index = reference
        found = [r for r in records[room, side] if (r['eff'],r['table'],r['no'],r['index']) == reference]
        if len(found) != 1:
            raise ValueError('reference is not unique: %s %s %r' % (room, side, reference))
        return found[0]

    haze = []
    for room, gc_ref, ps_ref in HAZE_PAIRS:
        gc, ps2 = select(room, 'gc', gc_ref), select(room, 'ps2', ps_ref)
        same = [r for r in records[room, 'gc'] if r['table'] == 'sst' and r['id'] == 0x15 and
                abs(r['range']-gc['range']) <= 1 and r['rgba'][:3] == gc['rgba'][:3]]
        if len(same) != 1:
            raise ValueError('ambiguous haze range/RGB selector in '+room)
        haze.append({'room': room, 'gc': gc, 'ps2': ps2, 'recipe': haze_recipe(gc, ps2)})
    streaks = []
    for room, ref in STREAK_CUTS:
        gc = select(room, 'gc', ref)
        if gc['id'] != 0x0A or gc['work8'][0] != 0 or gc['work8'][2] != 0 or gc['blend'] != 1:
            raise ValueError('not a permanent additive streak-copy source')
        signature = streak_signature(gc)
        def matching(side):
            return [r for r in records[room,side] if r['table']=='sst' and r['id'] in (0,0x0A) and
                    streak_signature(r)==signature]
        if len(matching('gc')) != 1 or matching('ps2'):
            raise ValueError('streak signature is ambiguous or remains on PS2 in '+room)
        streaks.append({'room':room, 'gc':gc, 'runtime_signature': {
            'owner':0xD0, 'id':0, 'life_max':0, 'blend':1, 'tex':gc['tex'],
            'del_far':gc['del_far']*10, 'del_near':gc['del_near']*10}, 'ps2_matching_records':0})
    sheets = []
    for room, effect_id, tex in SHEET_CUTS:
        gc = [r for r in records[room,'gc'] if r['table']=='sst' and r['id']==effect_id and r['tex']==tex]
        ps2 = [r for r in records[room,'ps2'] if r['id']==effect_id]
        if len(gc) != 2 or ps2:
            raise ValueError('sheet-removal evidence changed in '+room)
        sheets.append({'room':room, 'owner':0xD0, 'id':effect_id, 'tex':tex,
                       'gc':gc, 'ps2_effect_id_records':0})
    remaining = []
    for room in FORMERLY_UNDECODED:
        path = cache/(room+'.ps2.eff0')
        item = {'room':room,'path':str(path),'runtime_changed':False}
        if path.exists():
            data = path.read_bytes()
            try:
                decoded = decode_eff(data, '<')
                item.update(status='SOURCE_DECODED_NOT_ADOPTED', records=len(decoded),
                            bytes=len(data), sha256=sha(data))
            except ValueError as error:
                item.update(status='UNDECODED', reason=str(error))
        else:
            item.update(status='SOURCE_UNAVAILABLE')
        remaining.append(item)
    return {'schema':'ps2-fx-render-recipes/2','inputs':inputs,'haze':haze,'streak_cuts':streaks,
            'sheet_cuts':sheets,'remaining':remaining,
            'scope':'Render recipes only. GC generators, RNG, pool occupancy, motion and effect textures remain source-owned.'}



def inventory(cache, rooms=INVENTORY_ROOMS):
    """Decode route order, keeping SST and EST effect ownership separate."""
    result = {}
    for room in rooms:
        sides = {}
        for side, endian in (('gc', '>'), ('ps2', '<')):
            rows, files = [], []
            for path in sorted(cache.glob('%s.%s.eff[0-9]' % (room, side))):
                data = path.read_bytes()
                decoded = decode_eff(data, endian)
                header = struct.unpack_from(endian+'12I', data)
                files.append({'path':str(path), 'bytes':len(data), 'sha256':sha(data),
                              'records':len(decoded), 'header':list(header),
                              'texture_table_absent':header[1] == 0,
                              'tpl_table_absent':header[6] == 0,
                              'anm_table_absent':header[7] == 0})
                for row in decoded:
                    rows.append(dict(row, source=str(path)))
            if not files:
                raise ValueError('no extracted EFF files for '+room+' '+side)
            sides[side] = {'files':files, 'record_count':len(rows),
                           'by_id':dict(sorted(Counter('%02x'%r['id'] for r in rows).items())),
                           'by_table':dict(Counter(r['table'] for r in rows)),
                           'haze':[r for r in rows if r['id']==0x15],
                           'streaks':[r for r in rows if r['id']==0x0A],
                           'sheets':[r for r in rows if r['id']==0x48]}
            sides[side]['sst_streak_candidates'] = []
            for signature in sorted({streak_signature(r) for r in rows if r['table']=='sst' and r['id']==0x0A}):
                matching = [r for r in rows if r['table']=='sst' and r['id'] in (0, 0x0A) and streak_signature(r)==signature]
                sides[side]['sst_streak_candidates'].append({'signature':list(signature), 'records':matching})
        result[room] = sides
    return {'schema':'ps2-fx-route-inventory/1','room_order':list(rooms),'rooms':result,
            'formerly_undecoded':list(FORMERLY_UNDECODED),
            'layout':'Version 0xB, 0x30-byte sequence headers and 0x12C-byte records; absent optional tables are null.',
            'scope':'Source inventory only. SST/EST ownership, effect areas, live counts and omitted/added effects need separate runtime qualification.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--scope', choices=('first-group', 'inventory'), default='first-group')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('refusing to overwrite evidence')
    result = inventory(args.cache) if args.scope == 'inventory' else audit(args.cache)
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'schema':result['schema'], 'output':str(args.output)}))


if __name__ == '__main__':
    main()