import math
import copy
import struct
from pathlib import Path
import tempfile
import unittest

from audit_ps2_fx_recipes import static_sprite_recipe, addition_recipe, core_haze_animations, decode_room_ear, decode_eff, haze_indoor_selector, haze_recipe, inventory, population_recipe, steady_size


def sample_eff(endian='<'):
    """Small EFF with one SST generator and explicitly absent optional EST."""
    data = bytearray(0x1BC)
    struct.pack_into(endian+'12I', data, 0, 0xB, 0, 0, 0x40, 0, 0, 0, 0, 0, 0x50, 0, 0)
    struct.pack_into(endian+'IHHI', data, 0x40, 1, 4, 3, 0x11223344)
    struct.pack_into(endian+'II', data, 0x50, 1, 0x10)
    struct.pack_into(endian+'H', data, 0x60, 1)
    r = 0x90
    struct.pack_into('4B', data, r, 1, 0x15, 0x1F, 0)
    struct.pack_into(endian+'f', data, r+0x20, 5000)
    struct.pack_into(endian+'5f', data, r+0x88, 2000, 2000, 0, .01, .99)
    struct.pack_into('4B', data, r+0x9C, 255, 240, 220, 35)
    struct.pack_into('4B', data, r+0xC8, 30, 5, 30, 30)
    struct.pack_into('BB', data, r+0x108, 1, 0)
    data[r+0x10D] = 9
    data[r+7] = 0xFE
    struct.pack_into(endian+'h', data, r+0x110, 1)
    return data


class EffectRecipeAuditTests(unittest.TestCase):
    def record(self):
        return decode_eff(sample_eff(), '<')[0]

    def test_static_raw_contract_allows_only_size_and_colour(self):
        raw=[];records=[]
        for endian in ('>','<'):
            data=sample_eff(endian);r=0x90
            data[r+1]=0;data[r+2]=8;data[r+0x108]=0
            struct.pack_into(endian+'I',data,r+8,1)
            struct.pack_into(endian+'f',data,r+0x20,0)
            struct.pack_into(endian+'f',data,r+0x30,1)
            struct.pack_into(endian+'2f',data,r+0x94,0,1)
            struct.pack_into(endian+'4f',data,r+0xa0,1,1,1,1)
            data[r+0xc2]=1
            raw.append(bytes(data[r:r+0x12c]));records.append(decode_eff(data,endian)[0])
        result=static_sprite_recipe(*records,*raw)
        self.assertEqual(1,result['scale_x'])
        changed=bytearray(raw[1]);struct.pack_into('<f',changed,0x88,4000);changed[0x9c]=80
        ps2=copy.deepcopy(records[1]);ps2['size_x']=4000;ps2['rgba'][0]=80
        self.assertEqual(2,static_sprite_recipe(records[0],ps2,raw[0],changed)['scale_x'])
        changed[0x104]=1
        with self.assertRaisesRegex(ValueError,'raw field changed'):
            static_sprite_recipe(records[0],ps2,raw[0],changed)
        with self.assertRaisesRegex(ValueError,'record width'):
            static_sprite_recipe(*records,raw[0][:-1],raw[1])
        for key,value in (('random_size',1),('life_max',1),('tool_flags',0x80000)):
            gc=copy.deepcopy(records[0]);ps2=copy.deepcopy(records[1]);gc[key]=ps2[key]=value
            with self.assertRaisesRegex(ValueError,'unsupported static field: '+key):
                static_sprite_recipe(gc,ps2,*raw)

    def test_known_record_fields_decode_in_both_byte_orders(self):
        little = decode_eff(sample_eff('<'), '<')[0]
        big = decode_eff(sample_eff('>'), '>')[0]
        for key in ('id', 'tex', 'range', 'size_x', 'size_plus', 'd_size_plus', 'rgba', 'work8',
                    'kind', 'generator', 'count_per_emission', 'no', 'area', 'list_flags', 'offset'):
            self.assertEqual(little[key], big[key], key)
        self.assertEqual(10, little['count_per_emission'])
        self.assertEqual(4, little['no'])
        self.assertEqual(3, little['area'])
        self.assertEqual(0x11223344, little['list_flags'])
        self.assertEqual(0x90, little['offset'])

    def test_addition_motion_and_trigger_contracts_reject_changed_fields(self):
        data=sample_eff()
        r=0x90
        struct.pack_into('<HH',data,0x44,3,6)
        struct.pack_into('<3f',data,r+0x0c,0,60,0)
        struct.pack_into('<3f',data,r+0x24,5,0,0)
        struct.pack_into('<f',data,r+0x30,1)
        struct.pack_into('<3f',data,r+0x34,0.20000001788139343,0.20000000298023224,0.20000000298023224)
        struct.pack_into('<f',data,r+0x6c,180)
        struct.pack_into('<f',data,r+0x84,0.20000000298023224)
        struct.pack_into('<3f',data,r+0x90,40,0.009999997913837433,0.9900000095367432)
        struct.pack_into('<4f',data,r+0xa0,1,1,1,1)
        struct.pack_into('4B',data,r+0x9c,145,155,155,34)
        record=decode_eff(data,'<')[0]
        self.assertEqual(10,addition_recipe(record,'r118')['count'])
        for field,bad in (('area',5),('speed',[6,0,0]),('generator_flags',2),('generator_wait_random',1),
                          ('set_time',1),('life_max',1),('floor',30),('color_start',2),('count_per_emission',11)):
            changed=copy.deepcopy(record);changed[field]=bad
            with self.assertRaisesRegex(ValueError,'unsupported addition field: '+field):
                addition_recipe(changed,'r118')
        with self.assertRaisesRegex(ValueError,'unqualified addition room'):
            addition_recipe(record,'r100')

    def test_generator_wait_random_uses_128_not_unrelated_10f(self):
        for endian in ('<','>'):
            data=sample_eff(endian)
            data[0x90+0x10f]=7
            data[0x90+0x128]=3
            self.assertEqual(3,decode_eff(data,endian)[0]['generator_wait_random'])
            self.assertEqual(7,data[0x90+0x10f])

    def test_absent_texture_tables_do_not_read_version_as_a_count(self):
        # The old dump treated ofsTexId=ofsTpl=ofsAnm=0 as an 11-item table
        # because it read the version (0xB) at file offset zero.
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            for side, endian in (('gc', '>'), ('ps2', '<')):
                (cache/('r109.'+side+'.eff0')).write_bytes(sample_eff(endian))
            result = inventory(cache, ('r109',))
            for side in ('gc', 'ps2'):
                value = result['rooms']['r109'][side]
                self.assertEqual(1, value['record_count'])
                self.assertTrue(value['files'][0]['texture_table_absent'])
                self.assertTrue(value['files'][0]['tpl_table_absent'])
                self.assertTrue(value['files'][0]['anm_table_absent'])
                self.assertEqual(10, value['haze'][0]['count_per_emission'])

    def test_inventory_keeps_est_and_sst_ownership_distinct(self):
        with tempfile.TemporaryDirectory() as temp:
            cache = Path(temp)
            (cache/'r200.gc.eff0').write_bytes(sample_eff('>'))
            data = sample_eff('<')
            struct.pack_into('<I', data, 2*4, 0x40)
            struct.pack_into('<I', data, 8*4, 0x50)
            struct.pack_into('<I', data, 3*4, 0)
            struct.pack_into('<I', data, 9*4, 0)
            (cache/'r200.ps2.eff0').write_bytes(data)
            result = inventory(cache, ('r200',))['rooms']['r200']
            self.assertEqual('sst', result['gc']['haze'][0]['table'])
            self.assertEqual('est', result['ps2']['haze'][0]['table'])
            self.assertEqual({'est': 1}, result['ps2']['by_table'])

    def test_populated_list_without_data_is_not_empty_evidence(self):
        data = sample_eff()
        struct.pack_into('<I', data, 9*4, 0)
        with self.assertRaisesRegex(ValueError, 'missing sst data for populated list'):
            decode_eff(data, '<')
        struct.pack_into('<I', data, 0x40, 0)
        self.assertEqual([], decode_eff(data, '<'))

    def test_inconsistent_tables_and_truncated_records_are_rejected(self):
        data = sample_eff()
        struct.pack_into('<I', data, 0x50, 2)
        with self.assertRaisesRegex(ValueError, 'list/data counts differ'):
            decode_eff(data, '<')
        with self.assertRaisesRegex(ValueError, 'sequence records exceed EFF bounds'):
            decode_eff(sample_eff()[:-1], '<')
        data = sample_eff()
        struct.pack_into('<I', data, 0x54, 0)
        with self.assertRaisesRegex(ValueError, 'overlaps offset table'):
            decode_eff(data, '<')

    def test_unknown_version_and_endian_are_rejected(self):
        data = sample_eff()
        struct.pack_into('<I', data, 0, 0xC)
        with self.assertRaisesRegex(ValueError, 'unsupported EFF version'):
            decode_eff(data, '<')
        with self.assertRaisesRegex(ValueError, 'endian must be'):
            decode_eff(data, 'guess')

    def test_larger_ps2_box_does_not_invent_gc_particles(self):
        gc, ps2 = self.record(), self.record()
        gc.update(count_per_emission=59, range=4000)
        value = haze_recipe(gc, ps2)
        self.assertEqual(6, value['every'])
        self.assertAlmostEqual(59/6, value['estimated_draw_subset_per_emission'])
        self.assertTrue(value['larger_ps2_box_not_repopulated'])
        self.assertEqual(3000, value['near_far_mm'])
        self.assertEqual(500, value['near_near_mm'])

    def test_clipped_volume_precedes_stride_choice(self):
        gc, ps2 = self.record(), self.record()
        gc['count_per_emission'] = 80
        ps2['range'] = 2500
        value = haze_recipe(gc, ps2)
        self.assertEqual(1, value['every'])
        self.assertAlmostEqual(10, value['estimated_draw_subset_per_emission'])
        self.assertFalse(value['larger_ps2_box_not_repopulated'])

    def test_unsupported_texture_or_effect_semantics_are_not_guessed(self):
        for change, message in (({'tex': 7}, 'texture changed'),
                                ({'id': 0x48}, 'camera-haze generator'),
                                ({'range': math.nan}, 'invalid haze source box'),
                                ({'work8': [5, 30, 30, 30]}, 'signed near-fade'),
                                ({'work8': [30, 5, 50, 30]}, 'final 30 percent')):
            with self.subTest(change=change):
                gc, ps2 = self.record(), self.record()
                ps2.update(change)
                with self.assertRaisesRegex(ValueError, message):
                    haze_recipe(gc, ps2)

    def test_indoor_duration_resolves_equal_range_and_rgb_without_live_state(self):
        global_haze = self.record()
        area_haze = dict(global_haze, work8=[30, 5, 30, 0])
        records = [global_haze, area_haze]
        self.assertEqual(31, haze_indoor_selector(records, global_haze))
        self.assertEqual(1, haze_indoor_selector(records, area_haze))
        self.assertEqual(0, haze_indoor_selector([global_haze], global_haze))
        # EST sharing the signature cannot collide with the room-SST owner gate.
        self.assertEqual(0, haze_indoor_selector([global_haze, dict(global_haze, table='est')], global_haze))

    def test_bounded_ear_decoder_preserves_relocated_area(self):
        for endian in ('<','>'):
            data = bytearray(0x20+0x10+0x98)
            struct.pack_into(endian+'I',data,0,1)
            struct.pack_into(endian+'I',data,16,0x20)
            data[20:24] = bytes([69,65,82,0])
            struct.pack_into(endian+'II',data,0x20,1,0)
            data[0x30:0x33] = bytes([7,1,5])
            data[0x35] = 1
            struct.pack_into(endian+'11f',data,0x38,-2000,1500,3500,
                             -100,-100,100,-100,100,100,-100,100)
            result = decode_room_ear(data,endian)
            self.assertEqual(5,result['rows'][0]['area'])
            self.assertEqual(-2000,result['rows'][0]['floor'])
            self.assertEqual([100,100],result['rows'][0]['points'][2])
            with self.assertRaisesRegex(ValueError,'truncated EAR'):
                decode_room_ear(data[:-1],endian)
            struct.pack_into(endian+'I',data,0,100)
            with self.assertRaisesRegex(ValueError,'table outside'):
                decode_room_ear(data,endian)

    def test_core_haze_contract_and_corrupt_tables(self):
        for endian,magic in (('>',0x20AF30),('<',0x1000)):
            data = bytearray(0x200)
            struct.pack_into(endian+'12I',data,0,0xB,0x40,0,0,0,0,0x60,0x70,0,0,0,0)
            struct.pack_into(endian+'I',data,0x40,2)
            struct.pack_into(endian+'H',data,0x44,0x1e)
            struct.pack_into(endian+'H',data,0x4c,0x1f)
            struct.pack_into(endian+'III',data,0x60,2,0x40,0x60)
            struct.pack_into(endian+'III',data,0x70,2,0x90,0xB0)
            for offset in (0xa0,0xc0): struct.pack_into(endian+'II',data,offset,magic,1)
            for offset in (0x100,0x120): struct.pack_into(endian+'HHhhHBBB',data,offset,128,128,0,0,1,1,1,0)
            self.assertEqual({0x1e,0x1f},set(core_haze_animations(data,endian)))
            struct.pack_into(endian+'h',data,0x104,1)
            with self.assertRaisesRegex(ValueError,'animation contract'):
                core_haze_animations(data,endian)
            struct.pack_into(endian+'h',data,0x104,0)
            struct.pack_into(endian+'I',data,0x74,0x200)
            with self.assertRaisesRegex(ValueError,'outside bounds'):
                core_haze_animations(data,endian)

    def test_population_lifecycle_and_trigger_changes_are_rejected(self):
        gc, ps2 = self.record(), self.record()
        gc['count_per_emission'] = 59
        result = population_recipe(gc, ps2)
        self.assertEqual(59, result['gc_count'])
        self.assertEqual(10, result['ps2_count'])
        for name, value in (('generator_life', 0), ('life_max', 1), ('generator_wait', 1),
                            ('generator_wait_random', 1), ('generator_type', 1), ('generator_flags', 1),
                            ('parts', 0), ('tool_flags', 1), ('type', 1)):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'lifecycle'):
                population_recipe(gc, dict(ps2, **{name:value}))
        with self.assertRaisesRegex(ValueError, 'area or trigger'):
            population_recipe(gc, dict(ps2, area=7))
        with self.assertRaisesRegex(ValueError, 'supported source subset'):
            population_recipe(gc, dict(ps2, count_per_emission=60))
        # Explicit residuals prevent count qualification from claiming full motion/fade/size parity.
        result = population_recipe(dict(gc, floor=900, random_size=40, work8=[30,5,30,0]),
                                   dict(ps2, floor=0, random_size=30, work8=[30,5,30,30]))
        self.assertEqual(900, result['source_floor_retained'])
        self.assertEqual(0, result['ps2_floor'])
        self.assertEqual(40, result['source_random_size_retained'])
        self.assertEqual(30, result['ps2_random_size'])
        self.assertEqual(0, result['source_indoor_frames_retained'])
        self.assertEqual(30, result['ps2_indoor_frames'])

    def test_ambiguous_or_unrepresentable_indoor_selector_is_rejected(self):
        a = self.record()
        with self.assertRaisesRegex(ValueError, 'ambiguous haze'):
            haze_indoor_selector([a, dict(a)], a)
        b = dict(a, work8=[30, 5, 30, 255])
        with self.assertRaisesRegex(ValueError, 'cannot encode 255'):
            haze_indoor_selector([a, b], b)

    def test_steady_size_requires_a_convergent_finite_recurrence(self):
        record = self.record()
        self.assertAlmostEqual(4000, steady_size(record), delta=.01)
        for change in ({'d_size_plus': 1}, {'size_plus': math.nan}, {'size_x': -1}):
            with self.subTest(change=change):
                value = dict(record, **change)
                with self.assertRaises(ValueError):
                    steady_size(value)


if __name__ == '__main__':
    unittest.main()