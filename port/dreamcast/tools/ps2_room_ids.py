#!/usr/bin/env python3
"""PS2 world package -> scroll object id sidecar (ps2-world.ids) for PS2_WORLD_DYNAMIC (native_static.cpp).

    python3 tools/ps2_room_ids.py <room>_004.scenario.obj <ps2-world.r4pw> <out ps2-world.ids>

A PS2 world package (tools/ps2_room_r4im.py, tools/ps2_world_r4im.py) has one R4PW placement per OBJ group, in group
order, and each placement's `placement` field is that group index. Each OBJ group is one PS2 SMD row; its name
carries the row's scroll object id as `SMX_nnn` (the SMD row's id byte, which the game also uses as the SMX index).
The PS2 SMD rows are not the GameCube SMD works (counts and order differ: r104 291 rows vs 443 works), but the ids
are the same objects (r105 door: ids 0x20 / 0x21 / 0x22 / 0x32 at the same world place on both), so the runtime
finds the game's object for a placement by id (SmdGetGroupObjPtr2), as the room code does.

ids (little endian): {'R4ID', u32 version 1, u32 count, u32 crc32 of the R4PW body (its header crc)} then count
bytes, the id of placement field value i (0xFF: none), the file zero padded to a multiple of 32 bytes. The runtime uses
the file only when count and crc match the package it opened.
"""
import re, struct, sys, zlib
from pathlib import Path


def group_ids(obj_path):
    ids = []
    with open(obj_path, encoding='latin-1') as f:
        for line in f:
            if line.startswith('g '):
                m = re.search(r'#SMD_(\d+)#SMX_(\d+)#', line)
                if not m:
                    raise SystemExit('%s: group without SMD/SMX fields: %s' % (obj_path, line.strip()))
                if int(m.group(1)) != len(ids):
                    raise SystemExit('%s: group %d is SMD row %s' % (obj_path, len(ids), m.group(1)))
                ids.append(int(m.group(2)))
    return ids


def r4pw(path):
    d = Path(path).read_bytes()
    magic, ver, npl, nparts, nmesh, crc = struct.unpack_from('<4s5I', d, 0)
    if magic != b'R4PW' or ver != 1 or zlib.crc32(d[32:]) != crc:
        raise SystemExit('%s: not an R4PW v1 sidecar' % path)
    off = 32 + 16 * nparts
    fields = [struct.unpack_from('<HH', d, off + 52 * i)[1] for i in range(npl)]
    return crc, fields


def main():
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    write(*sys.argv[1:4])


def write(obj_path, r4pw_path, out_path):
    ids = group_ids(obj_path)
    crc, fields = r4pw(r4pw_path)
    if max(fields) >= len(ids):
        raise SystemExit('placement field %d past the %d OBJ groups' % (max(fields), len(ids)))
    count = max(fields) + 1
    body = bytes(i if i < 0xFF else 0xFF for i in ids[:count])
    data = struct.pack('<4s3I', b'R4ID', 1, count, crc) + body
    data += b'\0' * (-len(data) % 32)    # the runtime reads it whole, 32-byte units (read_package)
    Path(out_path).write_bytes(data)
    shared = {}
    for i in ids[:count]:
        shared[i] = shared.get(i, 0) + 1
    unique = sum(1 for i, n in shared.items() if i < 250 and n == 1)
    print("%s: %d placements, %d ids, %d unique ids < 250" % (out_path, len(fields), len(shared), unique))


if __name__ == '__main__':
    main()
