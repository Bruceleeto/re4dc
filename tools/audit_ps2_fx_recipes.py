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
REMAINING_HAZE_PAIRS = (
    ('r109', (0, 'sst', 1, 0), (0, 'sst', 1, 0)),
    ('r10c', (0, 'sst', 1, 0), (0, 'sst', 1, 1)),
    ('r10e', (0, 'sst', 6, 0), (0, 'sst', 6, 1)),
    ('r111', (0, 'sst', 1, 0), (0, 'sst', 1, 1)),
    ('r113', (0, 'sst', 0, 0), (0, 'sst', 0, 1)),
    ('r119', (0, 'sst', 1, 0), (0, 'sst', 0, 1)),
    ('r11a', (0, 'sst', 4, 0), (0, 'sst', 4, 1)),
    ('r11c', (0, 'sst', 1, 0), (0, 'sst', 0, 1)),
    ('r11d', (0, 'sst', 1, 0), (0, 'sst', 0, 1)),
    ('r11d', (0, 'sst', 9, 0), (0, 'sst', 9, 0)),
    ('r11e', (0, 'sst', 0, 0), (0, 'sst', 0, 1)),
    ('r11f', (0, 'sst', 1, 0), (0, 'sst', 0, 1)),
    ('r200', (0, 'est', 2, 0), (0, 'est', 2, 0)),
)
POPULATION_HAZE_PAIRS = (('r11b', (0, 'sst', 0, 0), (0, 'sst', 0, 1)),)
STREAK_CUTS = (
    ('r102', (0, 'sst', 1, 14), 1),
    ('r104', (0, 'sst', 0, 6), 1),
    ('r107', (0, 'sst', 3, 2), 1),
)
REMAINING_STREAK_CUTS = (
    ('r10f', (0, 'sst', 1, 0), 15),
    ('r112', (0, 'sst', 1, 15), 1),
)
SHEET_CUTS = (('r105', 0x48, 0xD0, 2), ('r107', 0x48, 0xD0, 2))
REMAINING_SHEET_CUTS = (
    ('r108', 0x48, 0xD0, 4), ('r108', 0x48, 0xCB, 2),
    ('r109', 0x48, 0x1F, 1), ('r109', 0x48, 0xF6, 16), ('r109', 0x48, 0xCB, 11),
    ('r111', 0x48, 0xF6, 34), ('r111', 0x48, 0xCB, 14), ('r111', 0x48, 0x33, 5),
    ('r113', 0x48, 0x33, 5), ('r113', 0x48, 0xF6, 44), ('r113', 0x48, 0xCB, 4),
    ('r118', 0x48, 0xD0, 4), ('r118', 0x48, 0xCB, 1),
    ('r119', 0x48, 0x29, 9), ('r119', 0x48, 0x2C, 2), ('r119', 0x48, 0x1F, 1),
    ('r119', 0x48, 0xF6, 15), ('r119', 0x48, 0x34, 4), ('r119', 0x48, 0xCB, 15),
    ('r11c', 0x48, 0xCB, 3), ('r11c', 0x48, 0x34, 3), ('r11c', 0x48, 0x33, 1),
    ('r200', 0x48, 0xF6, 14),
)
EST_STREAK_CUTS = (('r111', (0, 'est', 3, 4), 1),
                   ('r111', (0, 'est', 7, 0), 3),
                   ('r112', (0, 'est', 2, 0), 1))
EST_SHEET_CUTS = (('r11c', 0xCB, 12), ('r11c', 0x34, 4),
                  ('r11c', 0x33, 10), ('r11c', 0xF6, 19))
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
                    'parts': read('B', r+7)[0], 'tool_flags': read('I', r+8)[0],
                    'random_size': read('f', r+0x90)[0], 'floor': read('f', r+0xD8)[0],
                    'generator_type': read('B', r+0x10A)[0], 'generator_flags': read('B', r+0x10B)[0],
                    'generator_wait': read('B', r+0x10C)[0], 'generator_wait_random': read('B', r+0x10F)[0],
                    'generator_life': read('h', r+0x110)[0],
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


def population_recipe(gc, ps2):
    """Qualify one immutable emitter identity; count exactness is a draw-selection property."""
    haze_recipe(gc, ps2)
    expected = {'generator_type':0, 'generator_flags':0, 'generator_wait':0,
                'generator_wait_random':0, 'generator_life':1, 'life_max':0,
                'parts':0xFE, 'tool_flags':0, 'type':0}
    for record in (gc, ps2):
        for name, value in expected.items():
            if record[name] != value:
                raise ValueError('unsupported population lifecycle: '+name)
    if gc['area'] != ps2['area'] or gc['table'] != ps2['table']:
        raise ValueError('population mapping requires separate area or trigger qualification')
    source, target = gc['count_per_emission'], ps2['count_per_emission']
    if not 0 < target <= source <= 255:
        raise ValueError('population counts exceed the supported source subset')
    return {'gc_count':source, 'ps2_count':target, 'position_ratio':ps2['range']/gc['range'],
            'selected_count':'min(live source group, PS2 count); exact only for unambiguous groups',
            'source_floor_retained':gc['floor'], 'ps2_floor':ps2['floor'],
            'source_random_size_retained':gc['random_size'], 'ps2_random_size':ps2['random_size'],
            'source_indoor_frames_retained':gc['work8'][3], 'ps2_indoor_frames':ps2['work8'][3],
            'scope':'Selected source-particle count and render-local box remap only; GC motion, random sizes and indoor fade duration remain source-owned.'}


def haze_indoor_selector(records, gc):
    """Resolve haze within its owner table using immutable fields, never live alpha."""
    same = [r for r in records if r['table'] == gc['table'] and r['id'] == 0x15 and
            abs(r['range']-gc['range']) <= 1 and r['rgba'][:3] == gc['rgba'][:3]]
    if len(same) == 1:
        return 0
    same = [r for r in same if r['work8'][3] == gc['work8'][3]]
    if gc['work8'][3] >= 255:
        raise ValueError('indoor-frame selector cannot encode 255')
    if len(same) != 1:
        raise ValueError('ambiguous haze range/RGB/indoor-duration selector')
    return gc['work8'][3]+1


def streak_signature(record):
    return (record['tex'], record['blend'], record['del_far'], record['del_near'])


def audit(cache, remaining=False, population=False):
    haze_pairs = HAZE_PAIRS + (REMAINING_HAZE_PAIRS if remaining else ()) + (POPULATION_HAZE_PAIRS if population else ())
    streak_cuts = STREAK_CUTS + (REMAINING_STREAK_CUTS if remaining else ())
    sheet_cuts = SHEET_CUTS + (REMAINING_SHEET_CUTS if remaining else ())
    rooms = sorted({row[0] for row in haze_pairs + streak_cuts + sheet_cuts} | ({'r10d'} if remaining else set()))
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
    for room, gc_ref, ps_ref in haze_pairs:
        gc, ps2 = select(room, 'gc', gc_ref), select(room, 'ps2', ps_ref)
        recipe = haze_recipe(gc, ps2)
        recipe['gc_indoor_frames_plus_one'] = haze_indoor_selector(records[room, 'gc'], gc)
        recipe['owner'] = 0xD0 if gc['table']=='sst' else 1
        if population:
            recipe['population'] = population_recipe(gc, ps2)
        haze.append({'room': room, 'gc': gc, 'ps2': ps2, 'recipe': recipe})
    streaks = []
    for room, ref, expected_count in streak_cuts:
        gc = select(room, 'gc', ref)
        if gc['id'] != 0x0A or gc['work8'][0] != 0 or gc['work8'][2] != 0 or gc['blend'] != 1:
            raise ValueError('not a permanent additive streak-copy source')
        signature = streak_signature(gc)
        def matching(side):
            return [r for r in records[room,side] if r['table']=='sst' and r['id'] in (0,0x0A) and
                    streak_signature(r)==signature]
        source_group = matching('gc')
        if len(source_group) != expected_count or matching('ps2') or any(
                r['id'] != 0x0A or r['work8'][0] or r['work8'][2] for r in source_group):
            raise ValueError('streak signature is ambiguous or remains on PS2 in '+room)
        streaks.append({'room':room, 'gc':gc, 'gc_group':source_group, 'runtime_signature': {
            'owner':0xD0, 'id':0, 'life_max':0, 'blend':1, 'tex':gc['tex'],
            'del_far':gc['del_far']*10, 'del_near':gc['del_near']*10}, 'ps2_matching_records':0})
    sheets = []
    for room, effect_id, tex, expected_count in sheet_cuts:
        gc = [r for r in records[room,'gc'] if r['table']=='sst' and r['id']==effect_id and r['tex']==tex]
        ps2 = [r for r in records[room,'ps2'] if r['id']==effect_id]
        if len(gc) != expected_count or ps2:
            raise ValueError('sheet-removal evidence changed in '+room)
        sheets.append({'room':room, 'owner':0xD0, 'id':effect_id, 'tex':tex,
                       'gc':gc, 'ps2_effect_id_records':0})
    removed_haze = []
    if remaining:
        # Room EFF 0 is installed as owner 1 by game.cpp. EST sources do not
        # receive SstSet's owner-0xd0 stamp; their selectors remain separate.
        for room, ref, expected_count in EST_STREAK_CUTS:
            gc = select(room, 'gc', ref)
            if gc['id'] != 0x0A or gc['work8'][:3] != [1, 0, 0] or gc['blend'] != 1:
                raise ValueError('not a one-frame additive EST streak-copy source')
            signature = streak_signature(gc) + tuple(gc['rgba'][:3])
            def matching_est(side):
                return [r for r in records[room, side] if r['eff']==0 and r['table']=='est' and
                        r['id'] in (0, 0x0A) and streak_signature(r)+tuple(r['rgba'][:3]) == signature]
            group = matching_est('gc')
            if len(group) != expected_count or matching_est('ps2') or any(
                    r['id'] != 0x0A or r['work8'][:3] != [1, 0, 0] for r in group):
                raise ValueError('ambiguous or retained EST streak-copy signature in '+room)
            streaks.append({'room':room, 'gc':gc, 'gc_group':group, 'runtime_signature': {
                'owner':1, 'id':0, 'life_max':1, 'blend':1, 'tex':gc['tex'],
                'del_far':gc['del_far']*10, 'del_near':gc['del_near']*10,
                'rgb':gc['rgba'][:3]}, 'ps2_matching_records':0})
        for room, tex, expected_count in EST_SHEET_CUTS:
            gc = [r for r in records[room, 'gc'] if r['eff']==0 and r['table']=='est' and r['id']==0x48 and r['tex']==tex]
            if len(gc) != expected_count or any(r['id']==0x48 for r in records[room, 'ps2']):
                raise ValueError('EST sheet-removal evidence changed in '+room)
            sheets.append({'room':room,'owner':1,'id':0x48,'tex':tex,'gc':gc,'ps2_effect_id_records':0})
        room = 'r10d'
        gc = [r for r in records[room, 'gc'] if r['id']==0x15]
        if [(r['eff'],r['table'],r['no'],r['index'],r['tex'],r['range']) for r in gc] != [
                (0,'est',1,2,0xC6,500.0), (0,'est',1,3,0x1E,1500.0)] or any(
                    r['id']==0x15 for r in records[room,'ps2']):
            raise ValueError('r10d special EST15 removal identity changed')
        removed_haze.append({'room':room,'owner':1,'gc':gc,'ps2_effect_id_records':0})
    remaining_sources = []
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
        remaining_sources.append(item)
    return {'schema':'ps2-fx-render-recipes/2','inputs':inputs,'haze':haze,'streak_cuts':streaks,
            'sheet_cuts':sheets,'removed_haze':removed_haze,'remaining':remaining_sources,
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
    parser.add_argument('--scope', choices=('first-group', 'stage1-recipes', 'population', 'inventory'), default='first-group')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('refusing to overwrite evidence')
    result = inventory(args.cache) if args.scope == 'inventory' else audit(args.cache, args.scope in ('stage1-recipes', 'population'), args.scope == 'population')
    args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'schema':result['schema'], 'output':str(args.output)}))


if __name__ == '__main__':
    main()