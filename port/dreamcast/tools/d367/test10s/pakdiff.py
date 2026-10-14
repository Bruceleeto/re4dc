import struct, sys, hashlib
def load(p):
    d = open(p, 'rb').read()
    assert d[:8] == b'RE4PAK1\0'
    ver, n, io, do, crc = struct.unpack_from('<5I', d, 8)
    e = {}
    for i in range(n):
        c, f, o, s = struct.unpack_from('<4I', d, io + 16 * i)
        e['%08x-%08x' % (c, f)] = (o, s, hashlib.sha256(d[o:o + s]).hexdigest())
    return d, ver, n, io, do, e
a = load(sys.argv[1]); b = load(sys.argv[2])
print('count', a[2], b[2], 'data_offset', a[4], b[4], 'size', len(a[0]), len(b[0]))
ka, kb = set(a[5]), set(b[5])
print('only in A', sorted(ka - kb)); print('only in B', sorted(kb - ka))
diff = []
for k in sorted(ka & kb):
    if a[5][k][2] != b[5][k][2]: diff.append(k)
    if a[5][k][:2] != b[5][k][:2]: print('offset/size moved', k, a[5][k][:2], b[5][k][:2])
print('content differs', diff)
for k in diff: print(' ', k, 'size', a[5][k][1], b[5][k][1])
