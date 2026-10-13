#!/usr/bin/env python3
"""Negative coverage and bind-transform checks for the explicit Luis mapping."""
import copy
import unittest
import numpy as np
from ps2_luis import ACTOR_COVERAGE, HAIR_MAP, EXACT_HAIR, bind_pose_proof, check_coverage, luis_bone_map


class Coverage(unittest.TestCase):
    def test_complete_actor(self):
        check_coverage(ACTOR_COVERAGE, 6, {4: 5, 6: 1, 7: 2, 8: 2})

    def test_missing_original_face_is_refused(self):
        rows = copy.deepcopy(ACTOR_COVERAGE)
        rows[1]['gc_infos'] = [1]
        with self.assertRaisesRegex(ValueError, 'GC source infos'):
            check_coverage(rows, 6, {4: 5, 6: 1, 7: 2, 8: 2})

    def test_duplicate_original_face_is_refused(self):
        rows = copy.deepcopy(ACTOR_COVERAGE)
        rows[3]['gc_infos'].append(2)
        with self.assertRaisesRegex(ValueError, 'GC source infos'):
            check_coverage(rows, 6, {4: 5, 6: 1, 7: 2, 8: 2})

    def test_missing_ps2_material_is_refused(self):
        rows = copy.deepcopy(ACTOR_COVERAGE)
        rows[0]['materials'].remove(4)
        with self.assertRaisesRegex(ValueError, 'PS2 material sections'):
            check_coverage(rows, 6, {4: 5, 6: 1, 7: 2, 8: 2})

    def test_double_draw_ps2_material_is_refused(self):
        rows = copy.deepcopy(ACTOR_COVERAGE)
        rows[0]['materials'].append(0)
        with self.assertRaisesRegex(ValueError, 'PS2 material sections'):
            check_coverage(rows, 6, {4: 5, 6: 1, 7: 2, 8: 2})

    def test_out_of_range_material_is_refused(self):
        rows = copy.deepcopy(ACTOR_COVERAGE)
        rows[0]['materials'].append(5)
        with self.assertRaisesRegex(ValueError, 'outside'):
            check_coverage(rows, 6, {4: 5, 6: 1, 7: 2, 8: 2})


def skeletons():
    gc = [dict(id=i, attach=i, parent=-1 if i==0 else 0,
               translation=[float(i), 0., 0.], rest=np.eye(4).tolist()) for i in range(90)]
    ps2 = [dict(id=i, parent=gc[i]['parent'], pos=list(gc[i]['translation'])) for i in range(64)]
    for p, g in HAIR_MAP.items():
        gc[g]['parent'] = 4
        pos = list(gc[g]['translation'])
        if p not in EXACT_HAIR:
            pos[1] -= 20
        ps2.append(dict(id=p, parent=4, pos=pos))
    return ps2, gc


class HairIdentity(unittest.TestCase):
    def test_offset_is_recorded_and_not_discarded(self):
        p, g = skeletons()
        mapping, proof = luis_bone_map(p, g)
        self.assertEqual(mapping[64], 64)
        self.assertEqual(proof[0]['gc_to_ps2_rest_offset'][1][3], -20.)
        self.assertFalse(proof[0]['exact_xyz'])
        self.assertEqual(sum(r['exact_xyz'] for r in proof), 4)

    def test_arbitrary_nearest_root_is_refused(self):
        p, g = skeletons()
        p[64]['pos'][0] += .001
        with self.assertRaisesRegex(ValueError, 'unique source X'):
            luis_bone_map(p, g)

    def test_wrong_parent_is_refused(self):
        p, g = skeletons()
        g[64]['parent'] = 3
        with self.assertRaisesRegex(ValueError, 'direct head child'):
            luis_bone_map(p, g)

    def test_ambiguous_source_root_is_refused(self):
        p, g = skeletons()
        g[89]['parent'] = 4
        g[89]['translation'] = list(g[64]['translation'])
        with self.assertRaisesRegex(ValueError, 'unique source X'):
            luis_bone_map(p, g)

    def test_exact_root_cannot_be_shifted(self):
        p, g = skeletons()
        p[66]['pos'][1] = .01
        with self.assertRaisesRegex(ValueError, 'exact hair root'):
            luis_bone_map(p, g)

    def test_body_deformation_cannot_be_retargeted_implicitly(self):
        p, g = skeletons()
        p[4]['pos'][1] = .01
        with self.assertRaisesRegex(ValueError, 'body bone 4 translation'):
            luis_bone_map(p, g)


class BindTransforms(unittest.TestCase):
    def test_shifted_root_rest_and_nonidentity_transform_equivalence(self):
        p = [dict(id=0, parent=-1, pos=[0., 0., 0.]), dict(id=1, parent=0, pos=[0., 2., 0.])]
        r0, r1 = np.eye(4), np.eye(4)
        r1[1,3] = 4.
        g = [dict(attach=0, rest=r0.tolist()), dict(attach=1, rest=r1.tolist())]
        proof = bind_pose_proof(p, g, {0:0, 1:1}, [[1., 3., 1.]], [[(0,.25),(1,.75)]])
        self.assertLess(proof['maximum_rest_error_mm'], 1e-12)
        self.assertLess(proof['maximum_virtual_root_algebra_error_mm'], 1e-12)
        self.assertTrue(proof['animation_evidence'].startswith('NONE'))


if __name__ == '__main__':
    unittest.main()
