#!/usr/bin/env python3
"""Canonical AIC2 host generator/parser. No archive replacement or runtime hook.

Every build uses an explicit, hash-pinned source manifest. Existing prebuilt
bytes are copied; raw sources use the unchanged aica_banks codec at a fixed cap.
No fit-dependent resampling, generic deduplication or playback-table rewriting.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
from typing import Iterable

MAGIC = 0x32434941
VERSION = 2
HEADER_BYTES = 192
RECORD_BYTES = 64
ENDIAN_MARKER = 0x12345678
MAX_SAMPLES = 512
U32_MAX = (1 << 32) - 1
SHARED_BYTES = 27040
SHARED_SHA = 'd224dd185bd1856cec5e3157c9bc69ba57de39ddbc82a0462070aaa8539fd4b5'
LOCAL_ALIASES = {8: 2, 9: 4, 10: 5, 11: 6, 12: 7}
# Identification is by complete source metadata, not a caller-provided filename.
AUDITED = {
    'bgm/bio4midi.dat#5': (
        'ffb4381fbc783d9baf5093cb12fd5bb68286f7279d7b46f1c87f3a9c27f85b59',
        '263ea3609e2c89093b8abeaffd3202c4ccdb3671e7dad23b2d605c06e6b042e7'),
    'bgm/bio4midi.dat#8': (
        '63c4ffabd6c489ecfc36179fb98814b4fe89e46ce90ce24128181832c9d2870a',
        '328fe7104bdaee4046892f6905c0239dca0bea5bfcf3ae41a15f953acedb0bb0'),
    'bgm/bio4midi.dat#9': (
        'b03ed77663ca406518a86d7aebd981067155ade75299c810f18a47b0b0dc294b',
        '6192cf86967a2963af07d6bf288e65ea80ff1ffb6ed913e5ff03753dfe5451c0'),
}
MAP_STRUCT = struct.Struct('<8I32s')
EXTENT_STRUCT = struct.Struct('<8I32s')


class FormatError(ValueError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise FormatError(reason)


def digest(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def u32(value: int, label: str) -> int:
    require(isinstance(value, int) and 0 <= value <= U32_MAX, label + ': uint32 overflow')
    return value


def align32(value: int) -> int:
    u32(value, 'alignment')
    require(value <= U32_MAX - 31, 'alignment overflow')
    return (value + 31) & ~31


def checked_span(offset: int, size: int, limit: int, label: str) -> None:
    u32(offset, label); u32(size, label); u32(limit, label)
    require(offset <= limit and size <= limit - offset, label + ': out of bounds')


def sample_bytes(length: int, shift: int) -> int:
    u32(length, 'sample length')
    require(length > 0 and 0 <= shift <= 3, 'invalid sample length/shift')
    frames = (length + (1 << shift) - 1) >> shift
    u32(frames, 'decimated sample count')
    return u32(((frames + 7) // 8) * 4, 'encoded sample bytes')


@dataclasses.dataclass(frozen=True)
class Sample:
    gc_nibble: int
    length: int
    shift: int

    @property
    def bytes(self) -> int:
        return sample_bytes(self.length, self.shift)


@dataclasses.dataclass(frozen=True)
class Identity:
    name: str
    source_class: int
    profile: int
    gc_bytes: int
    mram_sha: bytes
    table_sha: bytes
    logical_sha: bytes
    samples: tuple[Sample, ...]

    def validate(self) -> None:
        require(self.source_class in (0, 1, 2, 3, 5, 6, 7, 8), 'invalid source class')
        require(0 < self.profile <= U32_MAX, 'invalid frozen profile')
        u32(self.gc_bytes, 'GC part')
        require(self.gc_bytes >= HEADER_BYTES, 'GC part too short')
        require(all(len(x) == 32 for x in (self.mram_sha, self.table_sha, self.logical_sha)), 'invalid digest size')
        require(0 < len(self.samples) <= MAX_SAMPLES, 'sample count capacity')
        for s in self.samples:
            u32(s.gc_nibble, 'GC nibble')
            require((s.gc_nibble // 2) < self.gc_bytes, 'source sample address beyond part')
            _ = s.bytes
        # Names alone never activate a sharing policy.
        if self.name in AUDITED:
            require(self.source_class == 3, 'audited BGM class')
            require((self.mram_sha.hex(), self.table_sha.hex()) == AUDITED[self.name], 'audited metadata identity')

    def aliases(self) -> dict[int, int]:
        return LOCAL_ALIASES if self.name == 'bgm/bio4midi.dat#5' else {}

    def shared_sample(self) -> int | None:
        return {'bgm/bio4midi.dat#8': 6, 'bgm/bio4midi.dat#9': 0}.get(self.name)

    def accepts_slot(self, slot: int) -> bool:
        return (slot in (3, 4) if self.source_class == 3 else
                8 <= slot <= 13 if self.source_class == 8 else slot == self.source_class)


@dataclasses.dataclass(frozen=True)
class Bank:
    identity: Identity
    logical: bytes
    mram: bytes
    table: bytes
    rates: tuple[int, ...]

    def validate(self) -> None:
        i = self.identity
        i.validate()
        require(digest(self.mram) == i.mram_sha and digest(self.table) == i.table_sha, 'source metadata bytes')
        require(len(self.table) == len(i.samples) * 16, 'source table length')
        require(len(self.rates) == len(i.samples), 'source rate count')
        require(len(self.logical) == sum(s.bytes for s in i.samples), 'logical byte length')
        require(digest(self.logical) == i.logical_sha, 'logical image identity')
        for index, s in enumerate(i.samples):
            fmt, rate, nib, length, coefficient = struct.unpack_from('<HHIIH', self.table, index * 16)
            require(fmt == 0 and rate == self.rates[index] and nib == s.gc_nibble and length == s.length,
                    'source table fields changed')
            require(rate > 0, 'source sample rate')


@dataclasses.dataclass(frozen=True)
class Map:
    gc_nibble: int
    length: int
    logical_offset: int
    encoded_bytes: int
    shift: int
    extent: int
    offset: int
    sha: bytes

    def pack(self) -> bytes:
        return MAP_STRUCT.pack(self.gc_nibble, self.length, self.logical_offset,
                               self.encoded_bytes, self.shift, self.extent, self.offset, 0, self.sha)


@dataclasses.dataclass(frozen=True)
class Extent:
    kind: int
    file_offset: int
    payload_bytes: int
    stored_bytes: int
    policy: int
    sha: bytes

    def pack(self) -> bytes:
        return EXTENT_STRUCT.pack(self.kind, self.file_offset, self.payload_bytes,
                                  self.stored_bytes, self.policy, 0, 0, 0, self.sha)


@dataclasses.dataclass(frozen=True)
class Parsed:
    identity: Identity
    maps: tuple[Map, ...]
    extents: tuple[Extent, ...]
    payloads: tuple[bytes, ...]
    file_bytes: int

    def logical_chunks(self) -> Iterable[bytes]:
        for m in self.maps:
            yield self.payloads[m.extent][m.offset:m.offset + m.encoded_bytes]

    def logical(self) -> bytes:
        return b''.join(self.logical_chunks())

    @property
    def physical_bytes(self) -> int:
        return sum(e.stored_bytes for e in self.extents)


def same_shared_bytes(existing: bytes, incoming: bytes, expected_sha: bytes) -> bool:
    """A matching digest is necessary, never sufficient for sharing."""
    return (len(existing) == len(incoming) == SHARED_BYTES and
            digest(existing) == expected_sha == digest(incoming) and existing == incoming)


def manifest_digest(header: bytes, maps: bytes, extents: bytes) -> bytes:
    return digest(header[:160] + bytes(32) + maps + extents)


def canonical_locations(identity: Identity) -> tuple[list[tuple[int, int]], int]:
    aliases = identity.aliases()
    shared = identity.shared_sample()
    locations: list[tuple[int, int]] = []
    local_bytes = 0
    for index, sample in enumerate(identity.samples):
        if index == shared:
            locations.append((1, 0))
        elif index in aliases:
            first = aliases[index]
            require(first < index and identity.samples[first].bytes == sample.bytes, 'invalid approved local alias')
            locations.append(locations[first])
        else:
            locations.append((0, local_bytes))
            local_bytes = u32(local_bytes + sample.bytes, 'local slab bytes')
    require(local_bytes > 0, 'empty local slab')
    return locations, local_bytes



def folded_sample_digest(samples: Iterable[tuple[int, bytes]]) -> bytes:
    """Ordered bounded-loader proof: no per-sample hash array on the target."""
    records = tuple(samples)
    h = hashlib.sha256(b'AIC2-SAMPLE-FOLD-v1' + struct.pack('<I', len(records)))
    for index, (encoded_bytes, sample_sha) in enumerate(records):
        require(encoded_bytes > 0 and len(sample_sha) == 32, 'folded sample fields')
        h.update(struct.pack('<II', index, u32(encoded_bytes, 'folded sample bytes')))
        h.update(sample_sha)
    return h.digest()


def profile_record(bank: Bank, cap_hz: int) -> bytes:
    """Generate the immutable 128-byte receiver profile; never infer a new cap."""
    bank.validate()
    require(cap_hz in (8000, 11025, 16000, 22050, 32000), 'frozen profile cap')
    for sample, rate in zip(bank.identity.samples, bank.rates):
        shift = 0
        while shift < 3 and ((rate >> shift) > cap_hz + cap_hz // 64 or (sample.length >> shift) > 65534):
            shift += 1
        require(shift == sample.shift, 'profile changes sample shift')
    i = bank.identity
    policy = {'bgm/bio4midi.dat#5': 1, 'bgm/bio4midi.dat#8': 2, 'bgm/bio4midi.dat#9': 3}.get(i.name, 0)
    return struct.pack('<8I', i.source_class, i.profile, cap_hz, i.gc_bytes,
                       len(bank.mram), len(i.samples), len(bank.logical), policy) + i.mram_sha + i.table_sha + i.logical_sha

def generate(bank: Bank) -> bytes:
    bank.validate()
    identity = bank.identity
    locations, local_size = canonical_locations(identity)
    count = 2 if identity.shared_sample() is not None else 1
    payloads = [bytearray(local_size)] + ([bytearray(SHARED_BYTES)] if count == 2 else [])
    maps = []
    cursor = 0
    for index, (sample, (extent, offset)) in enumerate(zip(identity.samples, locations)):
        payload = bank.logical[cursor:cursor + sample.bytes]
        if index in identity.aliases():
            first_map = maps[identity.aliases()[index]]
            first = bank.logical[first_map.logical_offset:first_map.logical_offset + first_map.encoded_bytes]
            require(first == payload, 'approved alias payloads differ')
        elif extent == 1:
            require(len(payload) == SHARED_BYTES and digest(payload).hex() == SHARED_SHA, 'shared payload identity')
            payloads[1][:] = payload
        else:
            payloads[0][offset:offset + sample.bytes] = payload
        maps.append(Map(sample.gc_nibble, sample.length, cursor, sample.bytes, sample.shift,
                        extent, offset, digest(payload)))
        cursor += sample.bytes
    map_blob = b''.join(m.pack() for m in maps)
    extent_offset = HEADER_BYTES + len(map_blob)
    data_offset = align32(extent_offset + count * RECORD_BYTES)
    file_cursor = data_offset
    extents = []
    for index, payload in enumerate(payloads):
        extents.append(Extent(1 + index, file_cursor, len(payload), align32(len(payload)), index, digest(payload)))
        file_cursor = u32(file_cursor + align32(len(payload)), 'file bytes')
    require(file_cursor <= identity.gc_bytes, 'AIC2 does not fit original GC part')
    extent_blob = b''.join(e.pack() for e in extents)
    header = bytearray(HEADER_BYTES)
    struct.pack_into('<IHH14I', header, 0, MAGIC, VERSION, HEADER_BYTES, ENDIAN_MARKER, 0,
                     identity.source_class, len(maps), RECORD_BYTES, count, RECORD_BYTES,
                     len(bank.logical), HEADER_BYTES, extent_offset, data_offset, file_cursor,
                     identity.gc_bytes, identity.profile)
    header[64:96] = identity.mram_sha
    header[96:128] = identity.table_sha
    header[128:160] = identity.logical_sha
    header[160:192] = manifest_digest(header, map_blob, extent_blob)
    out = bytearray(identity.gc_bytes)
    out[:HEADER_BYTES] = header
    out[HEADER_BYTES:extent_offset] = map_blob
    out[extent_offset:extent_offset + len(extent_blob)] = extent_blob
    for e, payload in zip(extents, payloads):
        out[e.file_offset:e.file_offset + e.payload_bytes] = payload
    result = bytes(out)
    parsed = parse(result, identity)
    require(parsed.logical() == bank.logical, 'generator logical reconstruction')
    return result


def parse(blob: bytes, identity: Identity, actual_slot: int | None = None) -> Parsed:
    identity.validate()
    require(len(blob) == identity.gc_bytes, 'part byte count')
    require(len(blob) >= HEADER_BYTES, 'short header')
    values = struct.unpack_from('<IHH14I', blob)
    magic, version, header_bytes, endian, flags, source_class, nsamples, map_size, nextents, extent_size, \
        logical_bytes, map_offset, extent_offset, data_offset, file_bytes, gc_bytes, profile = values
    require((magic, version, header_bytes, endian, flags) == (MAGIC, VERSION, HEADER_BYTES, ENDIAN_MARKER, 0), 'header magic/version/flags')
    require(source_class == identity.source_class and profile == identity.profile and gc_bytes == identity.gc_bytes, 'profile/class/GC identity')
    if actual_slot is not None:
        require(identity.accepts_slot(actual_slot), 'actual source slot mismatch')
    require(nsamples == len(identity.samples) and 0 < nsamples <= MAX_SAMPLES and map_size == RECORD_BYTES, 'map dimensions')
    require(nextents == (2 if identity.shared_sample() is not None else 1) and extent_size == RECORD_BYTES, 'extent dimensions')
    require(map_offset == HEADER_BYTES and extent_offset == HEADER_BYTES + RECORD_BYTES * nsamples, 'noncanonical table offsets')
    require(data_offset == align32(extent_offset + nextents * RECORD_BYTES), 'noncanonical data offset')
    checked_span(map_offset, nsamples * RECORD_BYTES, len(blob), 'maps')
    checked_span(extent_offset, nextents * RECORD_BYTES, len(blob), 'extents')
    require(data_offset <= file_bytes <= gc_bytes, 'file bounds')
    require(blob[64:96] == identity.mram_sha and blob[96:128] == identity.table_sha and blob[128:160] == identity.logical_sha, 'source/logical hashes')
    require(blob[160:192] == manifest_digest(blob[:HEADER_BYTES], blob[map_offset:extent_offset],
            blob[extent_offset:extent_offset + nextents * RECORD_BYTES]), 'manifest hash')
    require(not any(blob[extent_offset + nextents * RECORD_BYTES:data_offset]), 'nonzero table padding')
    maps = []
    for index in range(nsamples):
        fields = MAP_STRUCT.unpack_from(blob, map_offset + index * RECORD_BYTES)
        require(fields[7] == 0, 'map reserved bits')
        maps.append(Map(*fields[:7], fields[8]))
    extents = []
    payloads = []
    cursor = data_offset
    for index in range(nextents):
        f = EXTENT_STRUCT.unpack_from(blob, extent_offset + index * RECORD_BYTES)
        require(f[5:8] == (0, 0, 0), 'extent reserved bits')
        e = Extent(*f[:5], f[8])
        require((e.kind, e.policy) == (index + 1, index), 'extent kind/policy')
        require(e.file_offset == cursor and e.file_offset % 32 == 0 and e.payload_bytes > 0, 'noncanonical extent span')
        require(e.stored_bytes == align32(e.payload_bytes), 'extent stored alignment')
        checked_span(e.file_offset, e.stored_bytes, file_bytes, 'extent data')
        payload = blob[e.file_offset:e.file_offset + e.payload_bytes]
        require(digest(payload) == e.sha, 'extent payload hash')
        require(not any(blob[e.file_offset + e.payload_bytes:e.file_offset + e.stored_bytes]), 'nonzero extent padding')
        if index == 1:
            require(e.payload_bytes == SHARED_BYTES and e.sha.hex() == SHARED_SHA, 'shared extent whitelist')
        extents.append(e); payloads.append(payload)
        cursor += e.stored_bytes
    require(cursor == file_bytes and not any(blob[file_bytes:]), 'trailing bytes or file size')
    locations, local_size = canonical_locations(identity)
    require(extents[0].payload_bytes == local_size, 'local extent size')
    logical_cursor = 0
    logical_hash = hashlib.sha256()
    for index, (m, sample, (extent, offset)) in enumerate(zip(maps, identity.samples, locations)):
        require((m.gc_nibble, m.length, m.shift) == (sample.gc_nibble, sample.length, sample.shift), 'source sample fields')
        require(m.encoded_bytes == sample.bytes and m.logical_offset == logical_cursor, 'logical sample span')
        require((m.extent, m.offset) == (extent, offset), 'unapproved alias or noncanonical mapping')
        require(m.extent < len(extents), 'map extent index')
        checked_span(m.offset, m.encoded_bytes, extents[m.extent].payload_bytes, 'mapped sample')
        payload = payloads[m.extent][m.offset:m.offset + m.encoded_bytes]
        require(digest(payload) == m.sha, 'sample payload hash')
        if index in identity.aliases():
            old = maps[identity.aliases()[index]]
            require(m.sha == old.sha and m.encoded_bytes == old.encoded_bytes, 'local alias identity')
        logical_hash.update(payload)
        logical_cursor += m.encoded_bytes
    require(logical_cursor == logical_bytes and logical_hash.digest() == identity.logical_sha, 'logical readback identity')
    return Parsed(identity, tuple(maps), tuple(extents), tuple(payloads), file_bytes)


class ChunkReceiver:
    """Host reference for one owner/token upload; publish remains an explicit gate.

    Buffering here is deliberately host-only. The later SH4 loader will scatter
    with bounded scratch; no claim about that loader's memory is made here.
    """
    def __init__(self, identity: Identity, owner: int, token: tuple[int, int], actual_slot: int):
        identity.validate()
        require(owner > 0 and len(token) == 2 and all(0 < x < (1 << 64) for x in token), 'invalid upload owner/token')
        require(identity.accepts_slot(actual_slot), 'actual source slot mismatch')
        self.identity, self.owner, self.token, self.actual_slot = identity, owner, token, actual_slot
        self.buffer = bytearray()
        self.state = 'receiving'
        self.verified: Parsed | None = None
        self.published: Parsed | None = None
        self.inflight = 0

    def _owner(self, owner: int, token: tuple[int, int]) -> None:
        require(owner == self.owner and token == self.token, 'stale or different upload owner')

    def copy_begin(self, owner: int, token: tuple[int, int]) -> None:
        self._owner(owner, token)
        require(self.state == 'receiving', 'copy on closed upload')
        self.inflight += 1

    def copy_end(self, owner: int, token: tuple[int, int]) -> None:
        self._owner(owner, token)
        require(self.inflight > 0, 'duplicate copy completion')
        self.inflight -= 1
        if self.state == 'cancelled' and self.inflight == 0:
            self.buffer.clear()

    def feed(self, owner: int, token: tuple[int, int], offset: int, data: bytes, logical_bytes: int | None = None) -> None:
        self._owner(owner, token)
        require(self.state == 'receiving', 'chunk after completion/cancel')
        require(offset == len(self.buffer), 'noncontiguous chunk')
        n = len(data) if logical_bytes is None else logical_bytes
        require(n > 0 and n <= len(data), 'empty/invalid chunk')
        checked_span(offset, n, self.identity.gc_bytes, 'upload chunk')
        if n != len(data):
            require(offset + n == self.identity.gc_bytes and len(data) == align32(n), 'nonfinal ARQ padding')
        self.buffer.extend(data[:n])
        if len(self.buffer) == self.identity.gc_bytes:
            try:
                self.verified = parse(bytes(self.buffer), self.identity, self.actual_slot)
                self.state = 'verified'
            except FormatError:
                self.state = 'error'
                raise

    def publish(self, owner: int, token: tuple[int, int]) -> Parsed:
        self._owner(owner, token)
        require(self.state == 'verified' and self.inflight == 0 and self.verified is not None, 'publish before verified/drained')
        self.published = self.verified
        self.state = 'published'
        return self.published

    def cancel(self, owner: int, token: tuple[int, int]) -> None:
        self._owner(owner, token)
        require(self.state != 'published', 'cancel cannot unpublish a resident bank')
        self.state = 'cancelled'
        self.verified = None
        if self.inflight == 0:
            self.buffer.clear()


def load_source(row: dict, base_directory: Path = Path('.')) -> Bank:
    """Load one explicit source archive; never rewrite it or infer a lower cap."""
    module_path = Path(__file__).with_name('aica_banks.py')
    spec = importlib.util.spec_from_file_location('_aic2_original_codec', module_path)
    codec = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(codec)
    source = Path(row['source'])
    if not source.is_absolute():
        source = base_directory / source
    raw = source.read_bytes()
    require(digest(raw).hex() == row['source_sha256'], 'source archive hash')
    block, cap = int(row['block']), int(row['cap_hz'])
    require(cap in (8000, 11025, 16000, 22050, 32000), 'unsupported frozen cap')
    matches = [b for b in codec.sound_blocks(raw, int(row.get('base', 0))) if b[0] == block]
    require(len(matches) == 1, 'source sound block ambiguity')
    _, mo, ms, ao, aram_bytes = matches[0]
    table, samples, coefficients = codec.wavetable(raw, block, mo, ms)
    mram = raw[mo:mo + ms]
    if struct.unpack_from('<I', raw, ao)[0] == codec.MAGIC:
        header = codec.HDR.unpack_from(raw, ao)
        require(header[1] == 1 and header[2] == cap and header[4] == len(samples) and
                header[5] == codec.fnv1a(table) and header[6] == aram_bytes, 'prebuilt source contract')
        checked_span(ao + codec.HDR_SIZE, header[3], len(raw), 'prebuilt source payload')
        logical = raw[ao + codec.HDR_SIZE:ao + codec.HDR_SIZE + header[3]]
    else:
        logical, _ = codec.convert_block(raw[ao:ao + aram_bytes], samples, coefficients, cap,
                                        False, codec.sample_loops(raw, block, mo, ms, len(samples)))
    # Required external pins keep raw encodings and all metadata reviewable.
    require(digest(mram).hex() == row['mram_sha256'], 'MRAM source hash')
    require(digest(table).hex() == row['table_sha256'], 'sample table source hash')
    require(digest(logical).hex() == row['logical_sha256'], 'frozen encoded image hash')
    identity = Identity(row['name'], 3 if block in (3, 4) else 8 if block >= 8 else block,
                        int(row['profile_id']), aram_bytes, digest(mram), digest(table), digest(logical),
                        tuple(Sample(s[2], s[3], codec.sample_shift(s[1], s[3], cap)) for s in samples))
    bank = Bank(identity, logical, mram, table, tuple(s[1] for s in samples))
    bank.validate()
    return bank


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', required=True, type=Path, help='new host output directory; no in-place archive edit')
    args = parser.parse_args()
    require(not args.output.exists(), 'output directory already exists')
    manifest = json.loads(args.manifest.read_text())
    require(manifest.get('version') == 1 and isinstance(manifest.get('banks'), list), 'manifest version/banks')
    # Validate/build everything before creating any result files.
    built = []
    names = set()
    for index, row in enumerate(manifest['banks']):
        bank = load_source(row, args.manifest.parent)
        key = (bank.identity.name, int(row['block']))
        require(key not in names, 'duplicate manifest bank')
        names.add(key)
        blob = generate(bank)
        parsed = parse(blob, bank.identity)
        built.append((f'{index:03d}.aic2', blob, dict(name=bank.identity.name, block=row['block'],
                      cap_hz=row['cap_hz'], logical_sha256=bank.identity.logical_sha.hex(),
                      source_sha256=row['source_sha256'], table_sha256=bank.identity.table_sha.hex(),
                      mram_sha256=bank.identity.mram_sha.hex(), samples=len(bank.identity.samples),
                      physical_bytes=parsed.physical_bytes, file_bytes=parsed.file_bytes)))
    args.output.mkdir(parents=True)
    rows = []
    for name, blob, summary in built:
        (args.output / name).write_bytes(blob)
        rows.append(dict(file=name, sha256=digest(blob).hex(), bytes=len(blob), **summary))
    (args.output / 'report.json').write_text(json.dumps(dict(status='HOST_ONLY_NOT_STAGED', banks=rows), indent=2) + '\n')
    print(json.dumps(dict(banks=len(rows), output=str(args.output))))


if __name__ == '__main__':
    main()
