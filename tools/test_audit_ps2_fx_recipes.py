import math
import struct
import unittest

from audit_ps2_fx_recipes import decode_eff, haze_recipe, steady_size


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
    return data


class EffectRecipeAuditTests(unittest.TestCase):
    def record(self):
        return decode_eff(sample_eff(), '<')[0]

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