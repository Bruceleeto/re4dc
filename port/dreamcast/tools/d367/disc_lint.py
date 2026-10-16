#!/usr/bin/env python3
"""disc_lint.py: check a Dreamcast GD-ROM image (.gdi + tracks) against the standard three-track layout.

The reference is the layout the community tool mkdcdisc writes with -F gdi (gitlab.com/simulant/mkdcdisc,
docs/topics/gd-image.md, src/build_gd.cpp) and pressed GD-ROMs share:

  track01  LBA 0      data (CTRL 4), low-density area: ISO9660 with IP0000.BIN headers in the system area
  track02  LBA t1+150 audio (CTRL 0), >= 300 sectors (4 s Red Book minimum), ends before LBA 45000
  track03  LBA 45000  data (CTRL 4), high-density area: IP.BIN (16 sectors, header + TOC1 + licence code +
                      bootstrap) then ISO9660 with absolute extents; padded to LBA 549150; boot file last

Usage:
  disc_lint.py <disc.gdi> [--profile standard|loader] [--json out.json] [--full-scan]
  disc_lint.py --compare <a.gdi> <b.gdi>        side-by-side facts of two images (no verdict)

Profiles:
  loader   (rules every loader needs: GDEMU, MODE, USB-GDROM, DreamShell, Flycast; violations are ERROR)
  standard (default: loader rules plus the mkdcdisc / pressed-disc layout rules, marked STD)
Exit status: 0 = no violation in the chosen profile, 1 = violation(s), 2 = cannot read the image.
WARN lines never change the exit status.
"""
import argparse
import hashlib
import json
import os
import re
import struct
import sys

HD_LBA = 45000
HD_END = 549150            # end of the GD-ROM high-density area (LBA)
PREGAP = 150
SYNC = bytes([0x00] + [0xFF] * 10 + [0x00])
# SHA-256 of IP.BIN bytes 0x300-0x36FF (the SEGA licence screen code the boot ROM compares byte for byte).
# Same value in KOS makeip's IP.BIN and in mkdcdisc's GD-ROM template (checked 2026-10-16).
LICENCE_SHA = '9f3ef07ef0f2d5f5'
AREA_TEXT = {'J': b'For JAPAN,TAIWAN,PHILIPINES.', 'U': b'For USA and CANADA.', 'E': b'For EUROPE.'}


# ------------------------------------------------------------------------------------------------ Mode 1 EDC/ECC
def _edc_table():
    t = []
    for i in range(256):
        e = i
        for _ in range(8):
            e = (e >> 1) ^ (0xD8018001 if e & 1 else 0)
        t.append(e)
    return t


EDC_T = _edc_table()

def edc(data):
    e = 0
    for b in data:
        e = (e >> 8) ^ EDC_T[(e ^ b) & 0xFF]
    return e


# lookup tables exactly as ecm.c (Neill Corlett): ecc_f_lut / ecc_b_lut
ECC_F = [0] * 256
ECC_B = [0] * 256
for _i in range(256):
    _j = ((_i << 1) ^ (0x11D if _i & 0x80 else 0)) & 0xFF
    ECC_F[_i] = _j
    ECC_B[_i ^ _j] = _i


def _ecc_compute(src, major_count, minor_count, major_mult, minor_inc):
    size = major_count * minor_count
    dest = bytearray(major_count * 2)
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        ecc_a = ecc_b = 0
        for _ in range(minor_count):
            temp = src[index]
            index += minor_inc
            if index >= size:
                index -= size
            ecc_a ^= temp
            ecc_b ^= temp
            ecc_a = ECC_F[ecc_a]
        ecc_a = ECC_B[ECC_F[ecc_a] ^ ecc_b]
        dest[major] = ecc_a
        dest[major + major_count] = ecc_a ^ ecc_b
    return dest


def mode1_ok(sect):
    """(edc_ok, ecc_ok) for a raw 2352-byte Mode 1 sector."""
    e = edc(sect[0:0x810])
    edc_ok = struct.unpack_from('<I', sect, 0x810)[0] == e
    body = bytearray(sect[12:12 + 2340])     # header .. P parity, as ecm.c (address bytes included for Mode 1)
    p = _ecc_compute(body, 86, 24, 2, 86)
    body[0x81C - 12:0x81C - 12 + 172] = p
    q = _ecc_compute(body, 52, 43, 86, 88)
    ecc_ok = bytes(p) == sect[0x81C:0x81C + 172] and bytes(q) == sect[0x8C8:0x8C8 + 104]
    return edc_ok, ecc_ok


def bcd(n):
    return ((n // 10) << 4) | (n % 10)


def msf(lba):
    f = lba + PREGAP
    return bytes([bcd(f // 4500), bcd((f // 75) % 60), bcd(f % 75)])


# ------------------------------------------------------------------------------------------------ track access
class Track:
    def __init__(self, num, lba, ctrl, ss, path, off):
        self.num, self.lba, self.ctrl, self.ss, self.path, self.off = num, lba, ctrl, ss, path, off
        self.size = os.path.getsize(path) if os.path.exists(path) else -1
        self.sectors = self.size // ss if self.size >= 0 else 0
        self.f = open(path, 'rb') if self.size >= 0 else None

    def user(self, rel, n=1):
        """n user-data sectors (2048 B each) at sector index rel within this track."""
        out = bytearray()
        for k in range(n):
            if self.ss == 2352:
                self.f.seek((rel + k) * 2352 + 16)
            else:
                self.f.seek((rel + k) * 2048)
            out += self.f.read(2048)
        return bytes(out)

    def raw(self, rel):
        self.f.seek(rel * self.ss)
        return self.f.read(self.ss)


def parse_gdi(path):
    raw = open(path, 'rb').read()
    facts = {'gdi_bytes': len(raw), 'gdi_crlf': b'\r\n' in raw and raw.count(b'\n') == raw.count(b'\r\n'),
             'gdi_trailing_newline': raw.endswith(b'\n'), 'gdi_text': raw.decode('latin-1')}
    lines = [l.strip() for l in raw.decode('latin-1').splitlines() if l.strip()]
    n = int(lines[0])
    tracks = []
    base = os.path.dirname(os.path.abspath(path))
    for l in lines[1:]:
        m = re.match(r'^(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+("([^"]+)"|\S+)\s+(-?\d+)$', l)
        if not m:
            raise ValueError('bad .gdi line: %r' % l)
        name = m.group(6) or m.group(5)
        tracks.append(Track(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)),
                            os.path.join(base, name), int(m.group(7))))
    facts['gdi_declared_tracks'] = n
    facts['gdi_lines'] = len(lines)
    return facts, tracks


# ------------------------------------------------------------------------------------------------ ISO9660
def both16(b, o):
    return struct.unpack_from('<H', b, o)[0], struct.unpack_from('>H', b, o + 2)[0]


def both32(b, o):
    return struct.unpack_from('<I', b, o)[0], struct.unpack_from('>I', b, o + 4)[0]


def susp_names(rec, name_len):
    """Rock Ridge NM name and the SUSP signatures in a directory record's system use area."""
    o = 33 + name_len + ((name_len + 1) & 1)
    nm, sigs = None, []
    while o + 4 <= len(rec):
        sig, ln, ver = rec[o:o + 2], rec[o + 2], rec[o + 3]
        if ln < 4 or ver not in (1, 2):
            break
        sigs.append(sig.decode('latin-1'))
        if sig == b'NM':
            nm = (nm or '') + rec[o + 5:o + ln].decode('latin-1')
        o += ln
    return nm, sigs


def read_iso(tr, abs_base):
    """Walk the ISO9660 volume in track tr. abs_base = LBA of the track's first sector (extents are absolute when
    the image was built with -C 0,<lba>). Returns a dict of facts."""
    f = {}
    vds = []
    for s in range(16, 32):
        d = tr.user(s)
        if d[1:6] != b'CD001':
            f['vd_error'] = 'no CD001 at sector %d' % s
            break
        vds.append(d[0])
        if d[0] == 1:
            pvd = d
        if d[0] == 2:
            f['svd_escape'] = d[88:91].hex()
        if d[0] == 255:
            break
    f['volume_descriptors'] = vds
    f['joliet'] = 'svd_escape' in f and f['svd_escape'] in ('252f40', '252f43', '252f45')
    if 1 not in vds:
        f['pvd'] = False
        return f
    f['pvd'] = True
    f['volume_id'] = pvd[40:72].decode('latin-1').rstrip()
    f['system_id'] = pvd[8:40].decode('latin-1').rstrip()
    f['volume_space'] = both32(pvd, 80)[0]
    f['logical_block'] = both16(pvd, 128)[0]
    f['path_table_size'] = both32(pvd, 132)[0]
    f['path_table_l'] = struct.unpack_from('<I', pvd, 140)[0]
    f['path_table_m'] = struct.unpack_from('>I', pvd, 148)[0]
    f['copyright_file'] = pvd[702:739].decode('latin-1').strip()
    f['abstract_file'] = pvd[739:776].decode('latin-1').strip()
    f['biblio_file'] = pvd[776:813].decode('latin-1').strip()
    f['app_id'] = pvd[574:702].decode('latin-1').strip()
    root = pvd[156:156 + 34]
    rext, rlen = both32(root, 2)[0], both32(root, 10)[0]
    f['root_extent'] = rext
    files, dirs = [], []
    rr_all = True
    upper_only = True
    seen = set()
    stack = [('', rext, rlen)]
    while stack:
        path, ext, ln = stack.pop()
        if ext in seen:
            continue
        seen.add(ext)
        dirs.append((path or '/', ext, ln))
        rel = ext - abs_base
        if rel < 0 or rel >= tr.sectors:
            f.setdefault('bad_extents', []).append((path or '/', ext))
            continue
        data = tr.user(rel, (ln + 2047) // 2048)
        o = 0
        while o < ln:
            rl = data[o]
            if rl == 0:
                o = (o // 2048 + 1) * 2048
                continue
            rec = data[o:o + rl]
            nl = rec[32]
            ident = rec[33:33 + nl]
            e, sz, flags = both32(rec, 2)[0], both32(rec, 10)[0], rec[25]
            o += rl
            if ident in (b'\x00', b'\x01'):
                continue
            nm, sigs = susp_names(rec, nl)
            iso_name = ident.decode('latin-1').split(';')[0]
            if nm is None:
                rr_all = False
            if iso_name != iso_name.upper():
                upper_only = False
            name = nm or iso_name
            full = path + '/' + name
            if flags & 2:
                stack.append((full, e, sz))
            else:
                files.append(dict(path=full, iso=iso_name, lba=e, size=sz, hidden=bool(flags & 1)))
    f['rock_ridge'] = rr_all
    f['iso_names_upper'] = upper_only
    f['dirs'] = len(dirs)
    f['files'] = len(files)
    f['file_bytes'] = sum(x['size'] for x in files)
    f['_files'] = sorted(files, key=lambda x: x['lba'])
    f['_dirs'] = dirs
    # path table: entries name the same directory extents
    pt = tr.user(f['path_table_l'] - abs_base, (f['path_table_size'] + 2047) // 2048)[:f['path_table_size']]
    o, pt_ext = 0, []
    while o < len(pt):
        nl = pt[o]
        if nl == 0:
            break
        pt_ext.append(struct.unpack_from('<I', pt, o + 2)[0])
        o += 8 + nl + (nl & 1)
    f['path_table_entries'] = len(pt_ext)
    f['path_table_matches_dirs'] = sorted(pt_ext) == sorted(d[1] for d in dirs)
    return f


# ------------------------------------------------------------------------------------------------ IP.BIN
def read_ip(ip):
    s = lambda a, b: ip[a:b].decode('latin-1')
    f = dict(hardware_id=s(0, 16), maker_id=s(0x10, 0x20), device_info=s(0x20, 0x30), area=s(0x30, 0x38),
             peripherals=s(0x38, 0x40), product=s(0x40, 0x4A), version=s(0x4A, 0x50), release=s(0x50, 0x60),
             boot_file=s(0x60, 0x70), maker_name=s(0x70, 0x80), title=s(0x80, 0x100).rstrip())
    f['toc1'] = ip[0x100:0x104] == b'TOC1'
    if f['toc1']:
        ent = struct.unpack_from('<97I', ip, 0x104)
        f['toc1_entries'] = [('%08x' % e) for e in ent if e != 0xFFFFFFFF]
        first, last, lead = struct.unpack_from('<3I', ip, 0x288)
        f['toc1_first_track'] = (first >> 16) & 0xFF
        f['toc1_last_track'] = (last >> 16) & 0xFF
        f['toc1_leadout_fad'] = lead & 0xFFFFFF
    else:
        f['toc1_bytes_nonzero'] = sum(1 for b in ip[0x100:0x300] if b)
    f['licence_sha'] = hashlib.sha256(ip[0x300:0x3700]).hexdigest()[:16]
    f['region_text'] = [ip[0x3700 + 0x20 * i + 4:0x3700 + 0x20 * (i + 1)].rstrip(b' \0').decode('latin-1')
                        for i in range(3)]
    f['bootstrap1_sha'] = hashlib.sha256(ip[0x3800:0x6000]).hexdigest()[:16]
    f['bootstrap2_sha'] = hashlib.sha256(ip[0x6000:0x8000]).hexdigest()[:16]
    crc = 0xFFFF
    for ch in (f['product'] + f['version']).encode('latin-1'):
        crc ^= ch << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    f['device_crc_expected'] = '%04X' % crc
    return f


# ------------------------------------------------------------------------------------------------ facts
def gather(gdi, full_scan=False):
    facts, tracks = parse_gdi(gdi)
    facts['tracks'] = []
    for t in tracks:
        tf = dict(num=t.num, lba=t.lba, ctrl=t.ctrl, sector=t.ss, file=os.path.basename(t.path), offset=t.off,
                  exists=t.size >= 0, bytes=t.size, sectors=t.sectors, size_multiple=t.size >= 0 and t.size % t.ss == 0)
        tf['end_lba'] = t.lba + t.sectors
        if t.size > 0 and t.ctrl == 4 and t.ss == 2352:
            n = t.sectors
            # EDC/ECC in pure Python is slow (~5 ms a sector): a 64-sector spread, also under --full-scan
            edc_idx = set(sorted(set([0, 1, 15, 16, 17, n - 2, n - 1] + list(range(0, n, max(1, n // 57)))))[:64])
            idx = range(n) if full_scan else sorted(set([n // 2]) | edc_idx)
            bad_sync = bad_hdr = bad_edc = bad_ecc = 0
            checked = 0
            for i in idx:
                r = t.raw(i)
                checked += 1
                if r[:12] != SYNC:
                    bad_sync += 1
                if r[12:15] != msf(t.lba + i) or r[15] != 1:
                    bad_hdr += 1
                if i in edc_idx:
                    e, c = mode1_ok(r)
                    bad_edc += not e
                    bad_ecc += not c
            tf.update(raw_checked=checked, edc_checked=len(edc_idx), bad_sync=bad_sync, bad_header=bad_hdr,
                      bad_edc=bad_edc, bad_ecc=bad_ecc)
        if t.size > 0 and t.ctrl == 0:
            t.f.seek(0)
            head = t.f.read(min(t.size, 2352 * 75))
            tf['audio_silent_start'] = not any(head)
        facts['tracks'].append(tf)
    data = [t for t in tracks if t.ctrl == 4 and t.size > 0]
    hd = [t for t in data if t.lba >= HD_LBA]
    ld = [t for t in data if t.lba < HD_LBA]
    if ld:
        t1 = ld[0]
        ip = t1.user(0, 16)
        facts['ld_ip'] = read_ip(ip)
        facts['ld_ip_sector_headers_same'] = all(ip[i * 2048:i * 2048 + 256] == ip[:256] for i in range(16))
        lf = read_iso(t1, t1.lba)
        facts['ld_iso'] = {k: v for k, v in lf.items() if not k.startswith('_')}
        facts['ld_files'] = [(x['path'], x['lba'], x['size']) for x in lf.get('_files', [])]
    if hd:
        t3 = hd[0]
        ip = t3.user(0, 16)
        facts['hd_ip'] = read_ip(ip)
        hf = read_iso(t3, t3.lba)
        files = hf.pop('_files', [])
        hf.pop('_dirs', None)
        facts['hd_iso'] = hf
        if files:
            boot = facts['hd_ip']['boot_file'].strip()
            bf = [x for x in files if x['path'].lstrip('/').upper() == boot.upper()]
            vis = [x for x in files if not x['hidden']]
            first, last = files[0], files[-1]
            facts['hd_first_file'] = (first['path'], first['lba'])
            facts['hd_last_file'] = (last['path'], last['lba'], last['size'])
            facts['hd_first_visible_file'] = (vis[0]['path'], vis[0]['lba']) if vis else None
            facts['hd_front_gap_sectors'] = (vis[0]['lba'] if vis else 0) - t3.lba
            end = max(x['lba'] + (x['size'] + 2047) // 2048 for x in files)
            facts['hd_content_end_lba'] = end
            facts['hd_track_end_lba'] = t3.lba + t3.sectors
            facts['hd_tail_sectors'] = t3.lba + t3.sectors - end
            if bf:
                b = bf[0]
                facts['boot_file'] = dict(path=b['path'], lba=b['lba'], size=b['size'],
                                          end_lba=b['lba'] + (b['size'] + 2047) // 2048,
                                          is_last_file=b is last, size_sector_multiple=b['size'] % 2048 == 0)
            # overlaps / out-of-track extents
            bad, prev_end, prev = [], 0, None
            for x in files:
                if x['size'] and x['lba'] < prev_end:
                    bad.append((prev, x['path']))
                if x['size']:
                    prev_end, prev = x['lba'] + (x['size'] + 2047) // 2048, x['path']
            facts['hd_overlaps'] = bad[:5]
            facts['hd_out_of_track'] = [x['path'] for x in files
                                        if x['size'] and (x['lba'] < t3.lba + 16 or
                                                          x['lba'] + (x['size'] + 2047) // 2048 > t3.lba + t3.sectors)][:5]
            facts['hd_order_sample'] = [x['path'] for x in vis[:5]] + ['...'] + [x['path'] for x in vis[-3:]]
            facts['hd_files_sha'] = hashlib.sha256(
                '\n'.join('%s %d' % (x['path'], x['size']) for x in sorted(vis, key=lambda x: x['path'])).encode()
            ).hexdigest()[:16]
            facts['_hd_files'] = vis
    return facts, tracks


# ------------------------------------------------------------------------------------------------ rules
def lint(facts, profile):
    out = []

    def rule(ok, level, rid, msg):
        out.append((('ok' if ok else level), rid, msg))

    T = facts['tracks']
    rule(facts['gdi_declared_tracks'] == len(T), 'ERROR', 'gdi.count', 'first .gdi line = number of track lines (%d vs %d)'
         % (facts['gdi_declared_tracks'], len(T)))
    rule(all(t['offset'] == 0 for t in T), 'ERROR', 'gdi.offset', 'every track offset field is 0')
    rule(all(t['exists'] for t in T), 'ERROR', 'gdi.files', 'every track file exists')
    rule(all(re.match(r'^track\d\d\.(bin|raw|iso)$', t['file']) for t in T), 'ERROR', 'gdi.names',
         'track files are named trackNN.bin/.raw/.iso (8.3, no spaces)')
    rule(facts['gdi_crlf'], 'WARN', 'gdi.crlf', '.gdi uses CRLF line endings (TOSEC / mkdcdisc form)')
    rule(all(t['size_multiple'] for t in T if t['exists']), 'ERROR', 'track.size', 'each track file is a whole number of sectors')
    rule(len(T) == 3, 'ERROR', 'layout.3tracks', 'three tracks (data, audio, data)')
    if len(T) >= 3:
        t1, t2, t3 = T[0], T[1], T[2]
        rule(t1['lba'] == 0 and t1['ctrl'] == 4, 'ERROR', 'layout.t1', 'track 1: LBA 0, data (CTRL 4)')
        rule(t2['ctrl'] == 0 and t2['sector'] == 2352, 'ERROR', 'layout.t2', 'track 2: audio (CTRL 0), 2352-byte sectors')
        rule(t2['lba'] == t1['lba'] + t1['sectors'] + PREGAP, 'ERROR', 'layout.t2lba',
             'track 2 starts 150 sectors after track 1 ends (%d = %d + %d + 150)' % (t2['lba'], t1['lba'], t1['sectors']))
        rule(t2['sectors'] >= 300, 'ERROR', 'layout.t2len', 'track 2 is at least 300 sectors (4 s); has %d' % t2['sectors'])
        rule(t2['end_lba'] <= HD_LBA, 'ERROR', 'layout.ld', 'low-density area ends before LBA 45000')
        rule(t3['lba'] == HD_LBA and t3['ctrl'] == 4, 'ERROR', 'layout.t3', 'track 3: LBA 45000, data (CTRL 4)')
        rule(t3['end_lba'] <= HD_END, 'ERROR', 'layout.hdcap', 'track 3 ends by LBA 549150 (ends %d)' % t3['end_lba'])
        if profile == 'standard':
            rule(t1['sector'] == 2352 and t3['sector'] == 2352, 'STD', 'std.raw2352',
                 'data tracks are raw 2352-byte Mode 1 (track??.bin)')
            rule(t3['end_lba'] == HD_END, 'STD', 'std.hdpad',
                 'track 3 is padded to the end of the high-density area, LBA 549150 (ends %d; %d sectors short)'
                 % (t3['end_lba'], HD_END - t3['end_lba']))
            rule(t1['sectors'] >= 450, 'STD', 'std.t1len', 'track 1 is at least 450 sectors (has %d)' % t1['sectors'])
    for t in T:
        if 'raw_checked' in t:
            rule(t['bad_sync'] == 0 and t['bad_header'] == 0, 'ERROR', 'raw.header.t%d' % t['num'],
                 'track %d raw sectors: sync + MSF header + mode 1 (%d checked, %d bad sync, %d bad header)'
                 % (t['num'], t['raw_checked'], t['bad_sync'], t['bad_header']))
            rule(t['bad_edc'] == 0 and t['bad_ecc'] == 0, 'ERROR', 'raw.edcecc.t%d' % t['num'],
                 'track %d raw sectors: EDC + ECC valid (%d checked: %d bad EDC, %d bad ECC)'
                 % (t['num'], t['edc_checked'], t['bad_edc'], t['bad_ecc']))
    ip = facts.get('hd_ip')
    rule(ip is not None, 'ERROR', 'ip.present', 'high-density track carries IP.BIN')
    if ip:
        rule(ip['hardware_id'] == 'SEGA SEGAKATANA ', 'ERROR', 'ip.hwid', 'Hardware ID "SEGA SEGAKATANA "')
        rule(ip['maker_id'] == 'SEGA ENTERPRISES', 'ERROR', 'ip.maker', 'Maker ID "SEGA ENTERPRISES"')
        rule(ip['device_info'][5:].startswith('GD-ROM'), 'ERROR', 'ip.device', 'Device Info names GD-ROM (%r)' % ip['device_info'])
        rule(ip['device_info'][:4] == ip['device_crc_expected'], 'WARN', 'ip.devcrc',
             'Device Info CRC %s = CRC16(product+version) %s' % (ip['device_info'][:4], ip['device_crc_expected']))
        area = ip['area'].rstrip()
        rule(bool(area) and set(area) <= set('JUE'), 'ERROR', 'ip.area', 'Area symbols from J/U/E (%r)' % ip['area'])
        rule(all(ip['region_text'][i].encode('latin-1') == AREA_TEXT[c] for i, c in enumerate('JUE') if c in area),
             'ERROR', 'ip.regiontext', 'region text at 0x3700 matches every area symbol (%s)' % ip['region_text'])
        rule(bool(re.match(r'^[0-9A-F]{7} $', ip['peripherals'])), 'ERROR', 'ip.periph', 'Peripherals 7 hex digits (%r)' % ip['peripherals'])
        rule(bool(re.match(r'^V\d\.\d{3}$', ip['version'])), 'ERROR', 'ip.version', 'Version Vx.yyy (%r)' % ip['version'])
        rule(bool(re.match(r'^\d{8} {8}$', ip['release'])), 'ERROR', 'ip.date', 'Release date YYYYMMDD (%r)' % ip['release'])
        rule(ip['licence_sha'] == LICENCE_SHA, 'ERROR', 'ip.licence', 'SEGA licence code 0x300-0x36FF unmodified (%s)' % ip['licence_sha'])
        rule(ip['product'].strip() not in ('T0000', ''), 'WARN', 'ip.product',
             'distinct product number (%r; T0000 is shared by much homebrew: menus key art and lists on it)' % ip['product'])
        if profile == 'standard':
            t3 = T[2] if len(T) >= 3 else None
            ok = ip['toc1'] and t3 is not None and ip.get('toc1_entries', [''])[0] == '%08x' % (0x41000000 | (t3['lba'] + PREGAP)) \
                and ip.get('toc1_leadout_fad') == t3['end_lba'] + PREGAP
            rule(ok, 'STD', 'std.toc1', 'IP.BIN carries a TOC1 table at 0x100 matching track 3 (start FAD %d, lead-out FAD %d)%s'
                 % ((t3['lba'] + PREGAP) if t3 else 0, (t3['end_lba'] + PREGAP) if t3 else 0,
                    '' if ip['toc1'] else ': absent (%d non-zero bytes there)' % ip.get('toc1_bytes_nonzero', 0)))
    hi = facts.get('hd_iso', {})
    rule(hi.get('pvd', False), 'ERROR', 'iso.pvd', 'track 3 has an ISO9660 PVD at sector 16')
    if hi.get('pvd'):
        rule(hi['logical_block'] == 2048, 'ERROR', 'iso.block', 'logical block 2048')
        rule(hi['root_extent'] >= HD_LBA + 16 and not hi.get('bad_extents'), 'ERROR', 'iso.absolute',
             'directory extents are absolute LBAs inside track 3 (root at %d)' % hi['root_extent'])
        rule(hi['path_table_matches_dirs'], 'ERROR', 'iso.pathtable', 'L path table lists the same %d directories' % hi['dirs'])
        rule(not facts.get('hd_overlaps') and not facts.get('hd_out_of_track'), 'ERROR', 'iso.extents',
             'file extents inside track 3, no overlaps %s %s' % (facts.get('hd_overlaps') or '', facts.get('hd_out_of_track') or ''))
        rule(hi['joliet'] or hi['rock_ridge'], 'ERROR', 'iso.names',
             'long / lower-case names reachable by KOS fs_iso9660 (Joliet SVD or Rock Ridge NM on every record): joliet=%s rr=%s'
             % (hi['joliet'], hi['rock_ridge']))
        rule(hi['volume_space'] <= T[2]['sectors'] if len(T) >= 3 else True, 'ERROR', 'iso.space',
             'PVD volume space (%d) fits track 3' % hi['volume_space'])
    bf = facts.get('boot_file')
    rule(bf is not None, 'ERROR', 'boot.present', 'IP.BIN boot file %r is in the track 3 root'
         % (ip['boot_file'].strip() if ip else '?'))
    if bf:
        rule(bf['size_sector_multiple'], 'WARN', 'boot.pad',
             'boot file is a whole number of 2048-byte sectors (%d B; KOS #1492: an unpadded 1ST_READ.BIN can leave BIOS read residue)' % bf['size'])
        if profile == 'standard':
            rule(bf['is_last_file'] and facts['hd_tail_sectors'] == PREGAP, 'STD', 'std.bootlast',
                 'boot file is the last file, 150 sectors before the end of track 3 (at %d, tail %d sectors)'
                 % (bf['lba'], facts['hd_tail_sectors']))
    li = facts.get('ld_iso', {})
    rule(li.get('pvd', False), 'ERROR', 'ld.pvd', 'track 1 has an ISO9660 PVD at sector 16')
    lip = facts.get('ld_ip')
    rule(lip is not None and lip['hardware_id'] == 'SEGA SEGAKATANA ', 'ERROR', 'ld.ip',
         'track 1 system area starts with the SEGA SEGAKATANA header')
    if profile == 'standard' and lip:
        rule(facts.get('ld_ip_sector_headers_same', False), 'STD', 'std.ip0000',
             'track 1 system area = IP0000.BIN: the 256-byte header repeated in all 16 sectors')
        rule(bool(li.get('copyright_file') and li.get('abstract_file') and li.get('biblio_file')), 'STD', 'std.ldtext',
             'low-density PVD names COPYRIGH.TXT / ABSTRACT.TXT / BIBLIOGR.TXT (%r %r %r)'
             % (li.get('copyright_file'), li.get('abstract_file'), li.get('biblio_file')))
        if ip:
            hdr = ('hardware_id', 'maker_id', 'device_info', 'area', 'peripherals', 'product', 'version', 'release', 'boot_file')
            rule(all(lip[k] == ip[k] for k in hdr), 'STD', 'std.ldhdr', 'low-density header fields equal the high-density IP.BIN')
    return out


def print_facts(f):
    show = {k: v for k, v in f.items() if not k.startswith('_') and k not in ('ld_files',)}
    print(json.dumps(show, indent=1, default=str))


def compare(a, b):
    fa, _ = gather(a)
    fb, _ = gather(b)
    rows = []

    def row(k, va, vb):
        rows.append((k, va, vb))
    row('gdi text', fa['gdi_text'].replace('\r\n', ' / ').replace('\n', ' / '), fb['gdi_text'].replace('\r\n', ' / ').replace('\n', ' / '))
    for i in range(max(len(fa['tracks']), len(fb['tracks']))):
        ta = fa['tracks'][i] if i < len(fa['tracks']) else {}
        tb = fb['tracks'][i] if i < len(fb['tracks']) else {}
        for k in ('lba', 'ctrl', 'sector', 'file', 'sectors', 'bytes', 'end_lba', 'bad_edc', 'bad_ecc'):
            row('track%d %s' % (i + 1, k), ta.get(k), tb.get(k))
    for side in ('hd_ip', 'ld_ip'):
        for k in sorted(set(fa.get(side, {})) | set(fb.get(side, {}))):
            row('%s %s' % (side, k), fa.get(side, {}).get(k), fb.get(side, {}).get(k))
    for side in ('hd_iso', 'ld_iso'):
        for k in sorted(set(fa.get(side, {})) | set(fb.get(side, {}))):
            row('%s %s' % (side, k), fa.get(side, {}).get(k), fb.get(side, {}).get(k))
    for k in ('hd_first_file', 'hd_first_visible_file', 'hd_front_gap_sectors', 'hd_last_file', 'hd_content_end_lba',
              'hd_track_end_lba', 'hd_tail_sectors', 'boot_file', 'hd_order_sample', 'hd_files_sha', 'ld_files'):
        row(k, fa.get(k), fb.get(k))
    # same file set and contents positions
    pa = {x['path']: x for x in fa.get('_hd_files', [])}
    pb = {x['path']: x for x in fb.get('_hd_files', [])}
    row('hd files only in A', sorted(set(pa) - set(pb))[:8], None)
    row('hd files only in B', None, sorted(set(pb) - set(pa))[:8])
    row('hd files with different size', [p for p in pa if p in pb and pa[p]['size'] != pb[p]['size']][:8], None)
    oa = [p for p in sorted(pa, key=lambda p: pa[p]['lba']) if p in pb]
    ob = [p for p in sorted(pb, key=lambda p: pb[p]['lba']) if p in pa]
    row('hd same file order', oa == ob, None)
    deltas = sorted(set(pb[p]['lba'] - pa[p]['lba'] for p in oa))
    row('hd LBA shift B-A (distinct values)', len(deltas), (deltas[:3], deltas[-3:]))
    for k, va, vb in rows:
        mark = ' ' if va == vb else '*'
        print('%s %-34s | %s | %s' % (mark, k, va, vb))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('gdi', nargs='?')
    ap.add_argument('--profile', choices=('standard', 'loader'), default='standard')
    ap.add_argument('--json')
    ap.add_argument('--facts', action='store_true', help='print the gathered facts too')
    ap.add_argument('--full-scan', action='store_true',
                    help='check sync + MSF header of every raw sector (EDC/ECC stays a 64-sector spread; for a full '
                         'EDC/ECC check re-encode the user data with tools/d367/mode1raw.c and cmp)')
    ap.add_argument('--compare', nargs=2, metavar=('A_GDI', 'B_GDI'))
    a = ap.parse_args()
    if a.compare:
        compare(*a.compare)
        return 0
    if not a.gdi:
        ap.error('give a .gdi or --compare')
    try:
        facts, _ = gather(a.gdi, a.full_scan)
    except Exception as e:  # noqa: BLE001
        print('DISC_LINT CANNOT READ %s: %s' % (a.gdi, e))
        return 2
    res = lint(facts, a.profile)
    if a.facts:
        print_facts(facts)
    nbad = 0
    for lvl, rid, msg in res:
        if lvl in ('ERROR', 'STD'):
            nbad += 1
        print('%-5s %-18s %s' % (lvl, rid, msg))
    if a.json:
        json.dump(dict(gdi=a.gdi, profile=a.profile, results=res,
                       facts={k: v for k, v in facts.items() if not k.startswith('_')}), open(a.json, 'w'), indent=1, default=str)
    print('DISC_LINT %s %s profile=%s violations=%d' % ('PASS' if nbad == 0 else 'FAIL', a.gdi, a.profile, nbad))
    return 0 if nbad == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
