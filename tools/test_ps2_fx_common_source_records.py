#!/usr/bin/env python3
"""Check common-haze parent/release fields against the 28 qualified source records.

Usage: python3 tools/test_ps2_fx_common_source_records.py /private/eff/cache
The cache must contain r100.gc.eff0, r100.ps2.eff0, etc. No game assets are
written or copied. A record must match its reviewed SHA before fields are read.
"""
import argparse
import hashlib
from pathlib import Path

RECORDS = (
    ('r100', 'gc', 430000, '94beb05ecdeeb6b6aebb59b4722cce1ec1a490edf51bd75a5ffb1539698ede5f'),
    ('r100', 'ps2', 57144, '7460f1e5aea898b14d297997289a5fb38e10f84f97057d6f9e83de24ab657f6c'),
    ('r101', 'gc', 474384, '36a2629376c27eb762ea9e3469ff9ff6d0faa344a7c46db88b4082b442d6a871'),
    ('r101', 'ps2', 143276, 'f7fbcac03696726a102065bb7d3b54d2572f4a78f85b499be44ec3c3cee8dcec'),
    ('r102', 'gc', 543952, 'e5c336d11798d1aa8e8fe1974d5789187f04d8cc4e1c12b3f4f688eff6a7ad23'),
    ('r102', 'ps2', 91308, 'a0d8f42d3b704f700719d122037b4b480c0b9515e84735f441853c09e39c179c'),
    ('r103', 'gc', 600400, '4dd8e009eceb647c4f131d7d89a4b50db4a8c1ef4050412a84f970a5f2b97d0e'),
    ('r103', 'ps2', 106540, '6e8d44976b1d4aa50d0022c258b20da213adb7aaec0e77b4df79242d5420a7f1'),
    ('r104', 'gc', 68528, '510d37b1ccb88216103b224b5f4b9f2355acd6507edfdd020bd20535817db82c'),
    ('r104', 'ps2', 33516, '7a1340893e63ae18a41f578c6bf393e949b765d25f7e57b486b306fe69de1043'),
    ('r105', 'gc', 945520, 'a158f339918b5f3c568f99faaebec15f71bc8f585fd4e81bd506e72621044721'),
    ('r105', 'ps2', 77184, 'cdcc605d1107bed6d32be7f1ed79515103685899d26425accbcc1a8ab7ac5efc'),
    ('r105', 'gc', 945872, '7020e95825a9f25f3aab82608c7861bcb2fc355ae2654f59e4d5652fc020bc04'),
    ('r105', 'ps2', 77536, 'dcb7780c69baae307da8a738f4fe96423ce71c6c92ee44e3279b33ab1a98166c'),
    ('r106', 'gc', 258576, '48510c1a587e5adc1b896f2ed7655be5114569e6ac20774657dfbc8a47edcfed'),
    ('r106', 'ps2', 27472, '8bdf5fcce97474f2dca7bc120919767768a23e82cd13c89e38905699a1f7c643'),
    ('r106', 'gc', 274576, '9716b0e79fa3aae31e96235d6ce35f6ed44c654d0ddb1151f6b89a81ba7fa0be'),
    ('r106', 'ps2', 27824, 'fa56b1bb774db13a40df6ac7231da7ff43e5a5a3f92505c8f406c9da14c22da0'),
    ('r107', 'gc', 359600, 'c378adff7918ee9c9ee07a2e20e78b1241ab74bc54d198941a6ebed4af54f104'),
    ('r107', 'ps2', 163352, 'ae0241e84fb20ee82221514c20d8f39f945584786f5eb4b619dd451ab4715507'),
    ('r107', 'gc', 369104, 'b4c61836ad7a46d2d8c521177b336afb336bc13c42b31317e78b87604ca8ca13'),
    ('r107', 'ps2', 162400, 'eef490cfb0823ae1ce04ba518edb08a7c0ae100bd401690d0a9f24b962e66b43'),
    ('r109', 'gc', 165232, '812ae9b775038e24517be8c9eb9ca7db0769019c1ac51e60ff31de2e8e242e8d'),
    ('r109', 'ps2', 800, '43bbad28674ec428b0bf976a3eaad0a14bdca3fa4b9d26063faf3287679002ae'),
    ('r10a', 'gc', 502576, '5245c03189f0c6656225803d7027797a6faf026d0325035885742784874576e1'),
    ('r10a', 'ps2', 228060, '83eba94c41c30883b06a21ff9bdbff234207b43b64e93297990a8edd6a126dbe'),
    ('r10b', 'gc', 830480, 'ff164cb9e56ea940d205b87ebdc5c0dee23495f91419efcf22584a3ed572be0c'),
    ('r10b', 'ps2', 311308, '248c40c8193d3edec0538cc381b15720fd62ab947903af5330dd7202ce187d2f'),
)

def verify(cache):
    assert len(RECORDS) == 28 and len(set(RECORDS)) == 28
    checked = 0
    for room, side, offset, expected in RECORDS:
        path = cache / (room + '.' + side + '.eff0')
        data = path.read_bytes()
        record = data[offset:offset + 0x12c]
        if len(record) != 0x12c or hashlib.sha256(record).hexdigest() != expected:
            raise ValueError(f'{path}: source record at {offset:#x} changed')
        # EspGenWork layout: Parts_no @ 0x07; Release_time @ 0xc0.
        # EspSeqSet copies release unchanged and binds Parts_no 0xfe to world.
        if record[7] != 0xfe or record[0xc0] != 0:
            raise ValueError(f'{path}: unexpected parent/release source contract')
        checked += 1
    return checked

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cache', type=Path)
    args = parser.parse_args()
    count = verify(args.cache)
    print(f'PASS {count} SHA-bound source records: free world particles, Release_time=0')
