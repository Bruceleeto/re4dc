#!/usr/bin/env python3
"""swap-program.py: put a freshly built game program into a published RE4DC GDEMU test disc.

    swap-program.py <release> <program> <outdir> [--replace DISC/PATH=FILE ...]

<release>  a published GDEMU test zip (RE4DC-...-GDEMU.zip, with gdemu/disc.gdi and three tracks)
           or a directory holding disc.gdi and its tracks (an extracted gdemu folder).
<program>  the build output directory (build-public.sh OUT, or any build with re4dc-game.elf and the
           *.ovl overlays beside it), or a single re4dc-game.elf / 1ST_READ.BIN.
<outdir>   receives disc.gdi, track01.bin, track02.raw and a new track03.bin.

What it writes, the way the release packaging (tools/d367/mkgdi.sh) does:
  * 1ST_READ.BIN = the ELF as a raw binary (sh-elf-objcopy -R .stack -O binary). It is NOT
    scrambled: the boot ROM descrambles only on a CD-R (MIL-CD) disc, never on a GD-ROM.
  * The program's overlays (pl0f.ovl, em2f.ovl, sscrn.ovl ...) go to /dc/<name>.ovl. They are linked
    against this ELF's addresses, so a program without its own overlays would crash in those rooms.
IP.BIN and every other file stay byte-identical. A file that grew is appended after the last
sector of track 3 and its directory records (ISO9660 and Joliet) are pointed at the new copy;
changed sectors get fresh MODE1 EDC/ECC, so GDEMU and Flycast read the result as any other GDI.
Only the Python standard library is needed (plus sh-elf-objcopy when given an ELF).
"""
import argparse, hashlib, io, os, shutil, struct, subprocess, sys, zipfile
from pathlib import Path

RAW, USER = 2352, 2048
HD_LBA = 45000
HD_END = 549150  # end of the GD-ROM high-density area

# ---- MODE1 sector EDC/ECC (ECMA-130), as tools/d367/mode1raw.c --------------------------------
EDC = []
for i in range(256):
    e = i
    for _ in range(8):
        e = (e >> 1) ^ (0xD8018001 if e & 1 else 0)
    EDC.append(e)
F_LUT = [((i << 1) ^ (0x11D if i & 0x80 else 0)) & 0xFF for i in range(256)]
B_LUT = [0] * 256
for i in range(256):
    B_LUT[i ^ F_LUT[i]] = i


def edc(buf):
    e = 0
    for b in buf:
        e = (e >> 8) ^ EDC[(e ^ b) & 0xFF]
    return e


def ecc_block(s, major_count, minor_count, major_mult, minor_inc, dest):
    size = major_count * minor_count
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            t = s[0xC + index]
            index += minor_inc
            if index >= size:
                index -= size
            a ^= t
            b ^= t
            a = F_LUT[a]
        a = B_LUT[F_LUT[a] ^ b]
        s[dest + major] = a
        s[dest + major + major_count] = a ^ b


def bcd(v):
    return ((v // 10) << 4) | (v % 10)


def mode1_sector(lba, data):
    assert len(data) == USER
    s = bytearray(RAW)
    s[0:12] = b'\x00' + b'\xff' * 10 + b'\x00'
    a = lba + 150
    s[12:16] = bytes((bcd(a // 4500), bcd(a // 75 % 60), bcd(a % 75), 1))
    s[16:16 + USER] = data
    s[0x810:0x814] = struct.pack('<I', edc(s[0:0x810]))
    ecc_block(s, 86, 24, 2, 86, 0x81C)
    ecc_block(s, 52, 43, 86, 88, 0x8C8)
    return bytes(s)


# ---- track 3 access -----------------------------------------------------------------------------
class Track:
    def __init__(self, path):
        self.f = open(path, 'r+b')
        self.sectors = os.path.getsize(path) // RAW

    def raw(self, i):
        self.f.seek(i * RAW)
        return self.f.read(RAW)

    def user(self, i):
        return self.raw(i)[16:16 + USER]

    def lba_user(self, lba):
        return self.user(lba - HD_LBA)

    def write_lba(self, lba, data):
        i = lba - HD_LBA
        self.f.seek(i * RAW)
        self.f.write(mode1_sector(lba, data.ljust(USER, b'\0')))
        self.sectors = max(self.sectors, i + 1)


def dir_records(t, lba, size):
    """Yield (record_lba, offset_in_sector, record) for one directory extent."""
    for k in range((size + USER - 1) // USER):
        sec = t.lba_user(lba + k)
        o = 0
        while o < USER:
            n = sec[o]
            if n == 0:
                break
            yield lba + k, o, sec[o:o + n]
            o += n


def rec_name(rec, joliet):
    n = rec[32]
    raw = rec[33:33 + n]
    if raw in (b'\0', b'\1'):
        return None
    name = raw.decode('utf-16-be') if joliet else raw.decode('latin-1')
    return name.split(';')[0].rstrip('.')


def walk(t, root_lba, root_size, joliet):
    """{lower-case path: [(record_lba, offset, extent, size)]} for every file of one tree."""
    out = {}
    stack = [('', root_lba, root_size)]
    while stack:
        prefix, lba, size = stack.pop()
        for rlba, off, rec in dir_records(t, lba, size):
            name = rec_name(rec, joliet)
            if name is None:
                continue
            ext, ln, flags = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0], rec[25]
            path = (prefix + '/' + name).lower()
            if flags & 2:
                stack.append((path, ext, ln))
            else:
                out.setdefault(path, []).append((rlba, off, ext, ln))
    return out


def volumes(t):
    """[(descriptor lba, joliet, root extent, root size)] for the primary and Joliet descriptors."""
    vols = []
    for k in range(16, 32):
        d = t.user(k)
        if d[1:6] != b'CD001' or d[0] == 255:
            if d[0] == 255:
                break
            continue
        if d[0] in (1, 2):
            joliet = d[0] == 2 and d[88:91] in (b'%/@', b'%/C', b'%/E')
            if d[0] == 2 and not joliet:
                continue
            root = d[156:156 + 34]
            vols.append((HD_LBA + k, joliet, struct.unpack_from('<I', root, 2)[0], struct.unpack_from('<I', root, 10)[0]))
    return vols


def both(v, fmt):
    le, be = ('<I', '>I') if fmt == 4 else ('<H', '>H')
    return struct.pack(le, v) + struct.pack(be, v)


def patch_user(t, lba, off, data):
    sec = bytearray(t.lba_user(lba))
    sec[off:off + len(data)] = data
    t.write_lba(lba, bytes(sec))


def replace_file(t, files, path, blob, report):
    recs = []
    for tree in files:
        recs += tree.get(path, [])
    if not recs:
        sys.exit('swap-program: %s is not on the disc' % path)
    ext, ln = recs[0][2], recs[0][3]
    if any(r[2] != ext for r in recs):
        sys.exit('swap-program: %s has directory records with different extents' % path)
    if max(1, (len(blob) + USER - 1) // USER) <= max(1, (ln + USER - 1) // USER):
        new = ext  # fits in its own sectors: rewrite in place
    else:
        new = HD_LBA + t.sectors  # append after the last sector of the track
    n = max(1, (len(blob) + USER - 1) // USER)
    if new + n > HD_END:
        sys.exit('swap-program: track 3 would pass the end of the GD-ROM high-density area')
    for k in range(n):
        t.write_lba(new + k, blob[k * USER:(k + 1) * USER])
    for rlba, off, _, _ in recs:
        patch_user(t, rlba, off + 2, both(new, 4) + both(len(blob), 4))
    report.append('%-22s %9d -> %9d bytes  lba %d -> %d%s' % (path, ln, len(blob), ext, new, '' if new == ext else ' (appended)'))


def dir_extent(t, root_lba, root_size, joliet, path):
    """(lba, size) of the directory at path ('' = root) in one tree."""
    lba, size = root_lba, root_size
    for part in [p for p in path.split('/') if p]:
        for _, _, rec in dir_records(t, lba, size):
            name = rec_name(rec, joliet)
            if name is not None and rec[25] & 2 and name.lower() == part.lower():
                lba, size = struct.unpack_from('<I', rec, 2)[0], struct.unpack_from('<I', rec, 10)[0]
                break
        else:
            sys.exit('swap-program: directory /%s is not on the disc' % path)
    return lba, size


def add_file(t, vols, path, blob, report):
    """A new file in an existing directory: data appended to the track, one record per tree placed in the
    free tail of the directory's last sector (records stay unsorted; the KOS reader scans linearly)."""
    parent, name = path.rsplit('/', 1)
    new = HD_LBA + t.sectors
    n = max(1, (len(blob) + USER - 1) // USER)
    if new + n > HD_END:
        sys.exit('swap-program: track 3 would pass the end of the GD-ROM high-density area')
    for k in range(n):
        t.write_lba(new + k, blob[k * USER:(k + 1) * USER])
    for _, joliet, root, size in vols:
        dlba, dsize = dir_extent(t, root, size, joliet, parent)
        ident = name.encode('utf-16-be') if joliet else (name.upper() + ';1').encode('latin-1')
        rec = bytearray(33 + len(ident) + (1 - len(ident) % 2))
        rec[0] = len(rec)
        rec[2:10] = both(new, 4)
        rec[10:18] = both(len(blob), 4)
        rec[18:25] = bytes((126, 10, 12, 0, 0, 0, 0))  # 2026-10-12 00:00:00 UTC
        rec[28:32] = both(1, 2)
        rec[32] = len(ident)
        rec[33:33 + len(ident)] = ident
        last = dlba + (dsize + USER - 1) // USER - 1
        sec = t.lba_user(last)
        o = 0
        while o < USER and sec[o]:
            o += sec[o]
        if o + len(rec) > USER:
            sys.exit('swap-program: no room for %s in the last sector of /%s' % (path, parent))
        patch_user(t, last, o, bytes(rec))
    report.append('%-22s %9s -> %9d bytes  lba %d (added)' % (path, '-', len(blob), new))


def program_files(prog, objcopy):
    prog = Path(prog)
    out = {}
    elf = prog / 're4dc-game.elf' if prog.is_dir() else prog
    if elf.suffix.lower() == '.elf':
        tmp = elf.with_name('.swap-prog.bin')
        subprocess.check_call([objcopy, '-R', '.stack', '-O', 'binary', str(elf), str(tmp)])
        out['/1st_read.bin'] = tmp.read_bytes()
        tmp.unlink()
    else:
        out['/1st_read.bin'] = elf.read_bytes()
    if prog.is_dir():
        for o in sorted(prog.glob('*.ovl')):
            out['/dc/' + o.name.lower()] = o.read_bytes()
    if not out['/1st_read.bin']:
        sys.exit('swap-program: empty program')
    return out


def unpack_release(src, out):
    """Copy disc.gdi and its tracks from a zip or a directory into out."""
    src = Path(src)
    out.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        gdi = (src / 'disc.gdi').read_text()
        names = [l.split()[4] for l in gdi.splitlines()[1:] if l.strip()]
        for n in ['disc.gdi'] + names:
            shutil.copyfile(src / n, out / n)
        return gdi
    with zipfile.ZipFile(src) as z:
        gdis = [n for n in z.namelist() if n.lower().endswith('disc.gdi')]
        if len(gdis) != 1:
            sys.exit('swap-program: expected one disc.gdi in %s, found %d' % (src, len(gdis)))
        base = gdis[0][:-len('disc.gdi')]
        gdi = z.read(gdis[0]).decode()
        names = [l.split()[4] for l in gdi.splitlines()[1:] if l.strip()]
        for n in ['disc.gdi'] + names:
            with z.open(base + n) as r, open(out / n, 'wb') as w:
                shutil.copyfileobj(r, w, 1 << 22)
    return gdi


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('release')
    ap.add_argument('program')
    ap.add_argument('outdir')
    ap.add_argument('--replace', action='append', default=[], metavar='DISC/PATH=FILE',
                    help='also replace another disc file, e.g. debug/config.txt=my.txt')
    ap.add_argument('--add', action='append', default=[], metavar='DISC/PATH=FILE',
                    help='add a file that is not on the disc yet, e.g. dc/padscript.txt=padscript-newgame.txt')
    ap.add_argument('--objcopy', default=os.environ.get('SH_OBJCOPY', 'sh-elf-objcopy'))
    ap.add_argument('--selftest', action='store_true', help='re-encode the first sectors and compare (EDC/ECC check)')
    a = ap.parse_args()
    out = Path(a.outdir)
    if out.exists() and any(out.iterdir()):
        sys.exit('swap-program: %s is not empty' % out)
    blobs = program_files(a.program, a.objcopy)
    for r in a.replace:
        k, v = r.split('=', 1)
        blobs['/' + k.strip('/').lower()] = Path(v).read_bytes()
    gdi = unpack_release(a.release, out)
    lines = [l.split() for l in gdi.splitlines()[1:] if l.strip()]
    t3 = [l for l in lines if int(l[1]) == HD_LBA]
    if len(t3) != 1 or t3[0][3] != str(RAW):
        sys.exit('swap-program: track 3 must be a %d-byte MODE1 track at LBA %d (got %s)' % (RAW, HD_LBA, t3))
    t = Track(out / t3[0][4])
    first = t.raw(16)
    if mode1_sector(HD_LBA + 16, first[16:16 + USER]) != first:
        sys.exit('swap-program: sector encoder does not reproduce the disc (not a MODE1 raw track?)')
    if a.selftest:
        for i in range(0, min(t.sectors, 64)):
            r = t.raw(i)
            assert mode1_sector(HD_LBA + i, r[16:16 + USER]) == r, i
        print('selftest: 64 sectors re-encode byte-identical')
    vols = volumes(t)
    if not vols:
        sys.exit('swap-program: no ISO9660 volume in track 3')
    files = [walk(t, root, size, joliet) for _, joliet, root, size in vols]
    report = []
    for path, blob in blobs.items():
        replace_file(t, files, path, blob, report)
    for r in a.add:
        k, v = r.split('=', 1)
        p = '/' + k.strip('/').lower()
        if any(p in tree for tree in files):
            sys.exit('swap-program: %s is already on the disc (use --replace)' % p)
        add_file(t, vols, p, Path(v).read_bytes(), report)
    # Volume space size (both-endian at byte 80) of every descriptor covers the appended sectors.
    # genisoimage -C 0,45000 records the track's own sector count; it only grows when a file was appended.
    for vlba, _, _, _ in vols:
        if struct.unpack_from('<I', t.lba_user(vlba), 80)[0] < t.sectors:
            patch_user(t, vlba, 80, both(t.sectors, 4))
    t.f.close()
    for l in report:
        print(l)
    print('track03 sectors %d (user area to lba %d of %d)' % (t.sectors, HD_LBA + t.sectors, HD_END))
    with open(out / 'SHA256SUMS.txt', 'w') as w:
        for l in lines:
            h = hashlib.sha256()
            with open(out / l[4], 'rb') as f:
                for c in iter(lambda: f.read(1 << 22), b''):
                    h.update(c)
            w.write('%s  %s\n' % (h.hexdigest(), l[4]))
    print('wrote %s/disc.gdi' % out)


if __name__ == '__main__':
    main()
