#!/usr/bin/env python3
"""Host format/transaction tests; real pinned fixtures are supplied by the runner."""
import dataclasses
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import unittest
from unittest import mock

MODULE = Path(__file__).resolve().parents[1] / 'tools' / 'aica_banks_v2.py'
spec = importlib.util.spec_from_file_location('aica_banks_v2', MODULE)
V = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = V
spec.loader.exec_module(V)


def bank(samples=2, gc_bytes=513, same=False):
    table = b''.join(struct.pack('<HHIIH2x', 0, 32000, i * 32, 16, i) for i in range(samples))
    mram = b'original MRAM metadata\0' + table
    image = b''.join(bytes([17 if same else 17 + i]) * 8 for i in range(samples))
    identity = V.Identity('test', 3, 1, gc_bytes, V.digest(mram), V.digest(table), V.digest(image),
                          tuple(V.Sample(i * 32, 16, 0) for i in range(samples)))
    return V.Bank(identity, image, mram, table, (32000,) * samples)


def resign(blob):
    out = bytearray(blob)
    map_offset, extent_offset, data_offset = struct.unpack_from('<3I', out, 40)
    extent_count = struct.unpack_from('<I', out, 28)[0]
    out[160:192] = V.manifest_digest(out[:192], out[map_offset:extent_offset],
                                    out[extent_offset:extent_offset + extent_count * 64])
    return bytes(out)


def patch_word(blob, offset, value, sign=True):
    out = bytearray(blob)
    struct.pack_into('<I', out, offset, value)
    return resign(out) if sign else bytes(out)


def real_banks():
    root = os.environ.get('AIC2_FIXTURE_DIR')
    if not root:
        return []
    root = Path(root)
    rows = json.loads((root / 'banks.json').read_text())['banks']
    result = []
    for row in rows:
        identity = V.Identity(row['name'], row['source_class'], row['profile'], row['gc_bytes'],
                              bytes.fromhex(row['mram_sha256']), bytes.fromhex(row['table_sha256']),
                              bytes.fromhex(row['logical_sha256']), tuple(V.Sample(*s) for s in row['samples']))
        b = V.Bank(identity, (root / row['logical_file']).read_bytes(),
                   (root / row['mram_file']).read_bytes(), (root / row['table_file']).read_bytes(), tuple(row['rates']))
        result.append((row, b, (root / row['aic2_file']).read_bytes()))
    return result


class FormatTests(unittest.TestCase):
    def test_canonical_roundtrip_no_metadata_change(self):
        b = bank()
        before = (b.mram, b.table, b.rates)
        blob = V.generate(b)
        self.assertEqual(blob, V.generate(b))
        p = V.parse(blob, b.identity, 4)
        self.assertEqual(p.logical(), b.logical)
        self.assertEqual((b.mram, b.table, b.rates), before)
        self.assertEqual((len(blob), p.physical_bytes, p.file_bytes), (513, 32, 416))
        self.assertEqual([m.offset for m in p.maps], [0, 8])
        with self.assertRaises(V.FormatError): V.parse(blob, b.identity, 5)

    def test_source_table_order_is_preserved_without_sorting(self):
        b = bank()
        table = b.table[16:] + b.table[:16]
        mram = b'reordered source table' + table
        logical = b.logical[8:] + b.logical[:8]
        identity = dataclasses.replace(b.identity, samples=tuple(reversed(b.identity.samples)),
                                       mram_sha=V.digest(mram), table_sha=V.digest(table), logical_sha=V.digest(logical))
        b = V.Bank(identity, logical, mram, table, tuple(reversed(b.rates)))
        p = V.parse(V.generate(b), identity)
        self.assertEqual([m.gc_nibble for m in p.maps], [32, 0])
        self.assertEqual(p.logical(), logical)

    def test_never_generic_dedupe(self):
        b = bank(same=True)
        p = V.parse(V.generate(b), b.identity)
        self.assertNotEqual(p.maps[0].offset, p.maps[1].offset)
        broken = patch_word(V.generate(b), 192 + 64 + 24, 0)
        with self.assertRaisesRegex(V.FormatError, 'unapproved alias'): V.parse(broken, b.identity)

    def test_metadata_name_cannot_authorize_aliases(self):
        b = bank()
        identity = dataclasses.replace(b.identity, name='bgm/bio4midi.dat#5')
        with self.assertRaisesRegex(V.FormatError, 'audited metadata'): V.generate(dataclasses.replace(b, identity=identity))
        bad_table = bytearray(b.table); bad_table[2] ^= 1
        with self.assertRaises(V.FormatError): V.generate(dataclasses.replace(b, table=bytes(bad_table)))

    def test_sizes_flags_and_overflow_fail_before_use(self):
        b = bank(); blob = V.generate(b)
        for offset, value in [(0, 0), (8, 0), (12, 1), (16, 8), (20, 0xffffffff),
                              (24, 32), (28, 2), (32, 32), (36, 0xffffffff),
                              (40, 0xfffffff0), (44, 0xfffffff0), (48, 0xfffffff0),
                              (52, 0xffffffff), (56, 0xffffffff), (60, 0), (192 + 28, 1)]:
            with self.subTest(offset=offset):
                broken = patch_word(blob, offset, value, sign=False)
                with self.assertRaises(V.FormatError): V.parse(broken, b.identity)
        for value in [-1, 0x100000000, 0xffffffff]:
            with self.assertRaises(V.FormatError): V.align32(value)
        with self.assertRaises(V.FormatError): V.checked_span(0xfffffff0, 64, 0xffffffff, 'span')
        with self.assertRaises(V.FormatError): V.generate(dataclasses.replace(b, identity=dataclasses.replace(b.identity, gc_bytes=400)))
        with self.assertRaises(V.FormatError): V.generate(dataclasses.replace(b, identity=dataclasses.replace(b.identity, samples=tuple())))

    def test_manifest_and_physical_corruption(self):
        b = bank(); blob = V.generate(b); p = V.parse(blob, b.identity)
        offsets = [64, 96, 128, 160, 192 + 32, p.extents[0].file_offset,
                   p.extents[0].file_offset + p.extents[0].payload_bytes, len(blob) - 1]
        for offset in offsets:
            out = bytearray(blob); out[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(V.FormatError): V.parse(bytes(out), b.identity)
        for offset in [0, 1, 7, 191, 192, len(blob) - 1]:
            with self.assertRaises(V.FormatError): V.parse(blob[:offset], b.identity)
        with self.assertRaises(V.FormatError): V.parse(blob + b'\0', b.identity)

    def test_signed_map_and_extent_errors(self):
        b = bank(); blob = V.generate(b)
        ext = 192 + 2 * 64
        edits = [(192, 999), (196, 999), (200, 1), (204, 0xffffffff), (208, 4), (212, 2),
                 (216, 0xffffffff), (ext, 2), (ext + 4, 0xffffffe0), (ext + 8, 0xffffffff),
                 (ext + 12, 64), (ext + 16, 1), (ext + 20, 1)]
        for offset, value in edits:
            with self.subTest(offset=offset), self.assertRaises(V.FormatError):
                V.parse(patch_word(blob, offset, value), b.identity)

    def test_one_byte_hash_collision_is_not_shared(self):
        a = bytes(V.SHARED_BYTES); b = bytes(V.SHARED_BYTES - 1) + b'\x01'
        forced = bytes.fromhex(V.SHARED_SHA)
        with mock.patch.object(V, 'digest', return_value=forced):
            self.assertTrue(V.same_shared_bytes(a, a, forced))
            self.assertFalse(V.same_shared_bytes(a, b, forced))
        self.assertFalse(V.same_shared_bytes(a, a[:-1], forced))


class ChunkTests(unittest.TestCase):
    def test_every_split_and_one_byte_feed(self):
        b = bank(); blob = V.generate(b)
        for split in range(1, len(blob)):
            r = V.ChunkReceiver(b.identity, 101, (1, split), 3)
            r.feed(101, (1, split), 0, blob[:split])
            self.assertIsNone(r.published)
            with self.assertRaises(V.FormatError): r.publish(101, (1, split))
            r.feed(101, (1, split), split, blob[split:])
            self.assertIsNone(r.published)
            self.assertEqual(r.publish(101, (1, split)).logical(), b.logical)
        r = V.ChunkReceiver(b.identity, 101, (2, 1), 4)
        for offset, byte in enumerate(blob): r.feed(101, (2, 1), offset, bytes([byte]))
        self.assertEqual(r.publish(101, (2, 1)).logical(), b.logical)

    def test_chunk_owner_offset_and_final_padding(self):
        b = bank(); blob = V.generate(b); r = V.ChunkReceiver(b.identity, 101, (1, 1), 3)
        for owner, token, offset, data in [(102, (1, 1), 0, blob[:8]), (101, (1, 2), 0, blob[:8]),
                                           (101, (1, 1), 1, blob[:8]), (101, (1, 1), 0, b'')]:
            with self.assertRaises(V.FormatError): r.feed(owner, token, offset, data)
            self.assertEqual(len(r.buffer), 0)
        r.feed(101, (1, 1), 0, blob[:512])
        with self.assertRaises(V.FormatError): r.feed(101, (1, 1), 0, blob[:512])
        with self.assertRaises(V.FormatError): r.feed(101, (1, 1), 512, blob[512:] + bytes(32))
        # ARQ padding is outside the declared part and is ignored, not hashed.
        r.feed(101, (1, 1), 512, blob[512:] + b'\xAC' * 31, logical_bytes=1)
        self.assertEqual(r.publish(101, (1, 1)).logical(), b.logical)
        with self.assertRaises(V.FormatError): r.feed(101, (1, 1), 513, b'\0')

    def test_cancel_waits_copy_and_queue_pointer_reuse(self):
        b = bank(); blob = V.generate(b)
        old = V.ChunkReceiver(b.identity, 101, (1, 1), 3)
        old.copy_begin(101, (1, 1)); old.feed(101, (1, 1), 0, blob[:200]); old.cancel(101, (1, 1))
        self.assertEqual(len(old.buffer), 200)
        old.cancel(101, (1, 1))
        new = V.ChunkReceiver(b.identity, 101, (1, 2), 4)
        with self.assertRaises(V.FormatError): new.feed(101, (1, 1), 200, blob[200:])
        with self.assertRaises(V.FormatError): old.feed(101, (1, 1), 200, blob[200:])
        with self.assertRaises(V.FormatError): old.publish(101, (1, 1))
        old.copy_end(101, (1, 1)); self.assertEqual(len(old.buffer), 0)
        with self.assertRaises(V.FormatError): old.copy_end(101, (1, 1))
        new.feed(101, (1, 2), 0, blob)
        self.assertEqual(new.publish(101, (1, 2)).logical(), b.logical)
        with self.assertRaises(V.FormatError): new.cancel(101, (1, 2))

    def test_final_copy_drain_and_bad_data_never_publish(self):
        b = bank(); blob = V.generate(b); r = V.ChunkReceiver(b.identity, 2, (1, 1), 3)
        r.copy_begin(2, (1, 1)); r.feed(2, (1, 1), 0, blob)
        with self.assertRaises(V.FormatError): r.publish(2, (1, 1))
        r.copy_end(2, (1, 1)); r.publish(2, (1, 1))
        out = bytearray(blob); out[400] ^= 1
        bad = V.ChunkReceiver(b.identity, 2, (2, 1), 3)
        with self.assertRaises(V.FormatError): bad.feed(2, (2, 1), 0, bytes(out))
        self.assertEqual(bad.state, 'error'); self.assertIsNone(bad.published)
        with self.assertRaises(V.FormatError): bad.publish(2, (2, 1))


class RealPinnedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.banks = real_banks()
        if not cls.banks: raise unittest.SkipTest('pinned real fixtures required from host runner')

    def test_exact_all_logical_bytes_metadata_rates_and_canonical_repeat(self):
        self.assertGreaterEqual(len(self.banks), 20)
        for row, b, blob in self.banks:
            with self.subTest(bank=b.identity.name, block=row['block']):
                b.validate(); p = V.parse(blob, b.identity)
                self.assertEqual(p.logical(), b.logical)
                self.assertEqual(blob, V.generate(b))
                self.assertEqual(V.digest(b.mram).hex(), row['mram_sha256'])
                self.assertEqual(V.digest(b.table).hex(), row['table_sha256'])
                self.assertEqual([r / (1 << s.shift) for r, s in zip(b.rates, b.identity.samples)], row['effective_rates'])

    def test_real_alias_sets_and_budgets(self):
        by_name = {b.identity.name: (b, V.parse(blob, b.identity)) for row, b, blob in self.banks}
        b5, p5 = by_name['bgm/bio4midi.dat#5']
        b8, p8 = by_name['bgm/bio4midi.dat#8']
        b9, p9 = by_name['bgm/bio4midi.dat#9']
        self.assertEqual([m.offset for m in p5.maps[8:]], [p5.maps[i].offset for i in [2,4,5,6,7]])
        self.assertEqual((len(p5.maps), len(b5.logical), p5.physical_bytes), (13,264568,163968))
        self.assertEqual((p8.extents[0].stored_bytes, p9.extents[0].stored_bytes), (138528,209600))
        self.assertTrue(V.same_shared_bytes(p8.payloads[1], p9.payloads[1], bytes.fromhex(V.SHARED_SHA)))
        self.assertEqual(1298784 - (920928 + p8.extents[0].stored_bytes + p9.extents[0].stored_bytes + 27040), 2688)
        self.assertEqual(1298784 - (964000 + p8.physical_bytes + p5.physical_bytes), 5248)
        # Exact source metadata survives even where two payloads have different articulations.
        self.assertEqual(V.digest(b5.mram).hex(), V.AUDITED[b5.identity.name][0])
        self.assertEqual(len(b5.table), 13 * 16)

    def test_real_header_map_sample_and_128k_chunk_boundaries(self):
        for row, b, blob in self.banks:
            p = V.parse(blob, b.identity)
            boundaries = {1, 31, 32, 191, 192, 193, p.file_bytes, len(blob)}
            for index in range(len(p.maps) + 1): boundaries.add(192 + index * 64)
            for m in p.maps: boundaries.add(p.extents[m.extent].file_offset + m.offset)
            for e in p.extents: boundaries.update((e.file_offset, e.file_offset + e.payload_bytes, e.file_offset + e.stored_bytes))
            for offset in range(131072, len(blob), 131072): boundaries.update((offset-1, offset, offset+1))
            # Split exactly at, before and after every relevant structure/data boundary.
            cuts = sorted({z for x in boundaries for z in (x-1,x,x+1) if 0 < z < len(blob)}) + [len(blob)]
            receiver = V.ChunkReceiver(b.identity, 123, (4, row['index'] + 1), 4 if b.identity.source_class == 3 else row['block'])
            start = 0
            for end in cuts:
                receiver.feed(123, (4, row['index'] + 1), start, blob[start:end]); start = end
            self.assertEqual(receiver.publish(123, (4, row['index'] + 1)).logical(), b.logical)


if __name__ == '__main__':
    unittest.main(verbosity=2)
