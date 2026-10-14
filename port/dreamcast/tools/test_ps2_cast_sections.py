#!/usr/bin/env python3
"""Host checks for source TPL selection and whole-triangle repeated UVs."""
import struct
import unittest

from ps2_cast import PRESETS, repeat_triangle_uv, section_specs, tpl_wrap_modes


class SourceSelections(unittest.TestCase):
    def test_legacy_single_tpl(self):
        for name, spec in PRESETS.items():
            if 'section_tpls' not in spec:
                self.assertEqual(section_specs(spec), [(arc, role, spec['tpl']) for arc, role in spec['sections']], name)

    def test_merchant_three_tpls_and_seven_infos(self):
        for name, cloth in [('merchant13-c0', 0x1ee), ('merchant13-o0', 0x1ed)]:
            selected = section_specs(PRESETS[name])
            self.assertEqual([(arc, tpl) for arc, _, tpl in selected], [
                (0x1e7, 0x1e8), (0x1f0, 0x1f1), (cloth, 0x1f1),
                (0x1ef, 0x1e8), (0x1e9, 0x1ea), (0x1f4, 0x1e8), (0x1f8, 0x1e8)])

    def test_unknown_tpl_override_refused(self):
        with self.assertRaises(ValueError):
            section_specs(dict(sections=[(4, 'body')], tpl=5, section_tpls={6: 7}))

    def test_standalone_merchant_keeps_own_archive_and_info_order(self):
        for name, cloth in [('merchant18-c0', 12), ('merchant18-o0', 11)]:
            spec = PRESETS[name]
            self.assertEqual((spec['archive'], spec['model_id']), ('em18', 0x18))
            self.assertEqual([(arc, tpl) for arc, _, tpl in section_specs(spec)],
                             [(5, 6), (14, 15), (7, 8), (18, 6), (19, 6), (cloth, 15), (13, 6)])


class RepeatUVs(unittest.TestCase):
    def test_inside_cell_unchanged(self):
        uv = [[0, 1], [256, 256], [127, 25]]
        self.assertEqual(repeat_triangle_uv(uv, (0, 0)), uv)

    def test_negative_period_preserves_interpolation_and_phase(self):
        uv = [[-255, 0], [-1, 128], [0, 256]]
        got = repeat_triangle_uv(uv, (1, 1))
        self.assertEqual(got, [[1, 0], [255, 128], [256, 256]])
        for a, b in zip(uv, got):
            self.assertEqual([(x - y) % 256 for x, y in zip(a, b)], [0, 0])
        for axis in range(2):
            for n in (1, 2):
                self.assertEqual(got[n][axis] - got[0][axis], uv[n][axis] - uv[0][axis])

    def test_positive_period(self):
        self.assertEqual(repeat_triangle_uv([[256, 512], [257, 514], [511, 766]], (1, 1)),
                         [[0, 0], [1, 2], [255, 254]])

    def test_clamp_or_mirror_refused(self):
        for wrap in (0, 2):
            with self.assertRaises(ValueError):
                repeat_triangle_uv([[-2, 0], [0, 0], [-1, 1]], (wrap, 1))

    def test_crossing_period_refused(self):
        for uv in ([[-1, 0], [1, 0], [0, 1]], [[0, 0], [257, 0], [1, 1]]):
            with self.assertRaises(ValueError):
                repeat_triangle_uv(uv, (1, 1))

    def test_original_sampler_read_and_bounds(self):
        data = bytearray(64)
        struct.pack_into('>3I', data, 0, 0x20af30, 1, 12)
        struct.pack_into('>I', data, 12, 24)
        struct.pack_into('>2I', data, 36, 1, 2)
        self.assertEqual(tpl_wrap_modes(data, 0), (1, 2))
        for bad, index in ((data, 1), (data, -1), (data[:42], 0), (b'', 0)):
            with self.assertRaises(ValueError):
                tpl_wrap_modes(bad, index)


if __name__ == '__main__':
    unittest.main()
