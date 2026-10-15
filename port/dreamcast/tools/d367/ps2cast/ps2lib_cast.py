#!/usr/bin/env python3
# ps2lib_cast.py (lane ps2cast, 2026-10-14): copy this lane's preconverted PS2 cast into the shared library
# re4-assets-private/ps2lib/cast/<room or common>/ unchanged and append INDEX.tsv rows (idempotent: rows whose
# class/room/gc_id/dc_format already exist are skipped). Run in WSL.
import hashlib, json, os, shutil, sys, glob

LIB = '/mnt/c/Game Dev/Emulators/re4-assets-private/ps2lib'
PRIV = '/mnt/c/Game Dev/Emulators/re4-assets-private'
CONV = '/root/probe/lanes-20261014/ps2cast/work/conv'
ASH = '/root/probe/lanes-20261014/ps2cast/ashley'
LANE = 'ps2cast'
AFS = 'BIO4DAT.AFS:'
CONV_E4 = 'ps2_cast.py+model_registry.py@e4eb9a49'
CONV_M = 'ps2_cast.py regcast (Codex CH23)+model_registry.py+vq_chroma.py+prep_archive.sh@0d2eed0f'
CONV_A = 'ps2_ashley.py+model_registry.py --slots+prep_archive.sh@778e4674'
GATE_M = 'PASS:t11-r102 census 1800/1800 + h2-t3T/h2-t3kT STRICT MUST-IDENTICAL (test 11 base)'


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def copytree(src, dst, ignore=None):
    if os.path.exists(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=ignore)


def tree_bytes(d):
    return sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(d) for f in fs)


rows = []


def row(room, gc_id, src, fmt, conv, path, gate='UNGATED'):
    if path and os.path.isfile(path):
        s, n = sha(path), os.path.getsize(path)
    elif path and os.path.isdir(path):
        s, n = '-', tree_bytes(path)
    else:
        s, n = '-', 0
    rows.append(['cast', room, gc_id, src, fmt, conv, s, str(n), gate, LANE])


# 1. merchant em18 (test 12 candidate A), disc-root mirror
d = f'{LIB}/cast/r102/merchant-em18'
copytree(f'{PRIV}/ps2cast-t13-20261014/merchant-r102', d)
shutil.copy2(f'{PRIV}/ps2cast-t13-20261014/merchant-r102.sha256', f'{LIB}/cast/r102/merchant-em18.sha256')
for typ in ('c0 closed coat', 'o0 open coat'):
    row('r102', f'em18 merchant {typ}', AFS + 'em18.dat#BIN5/0xE/7/0xB/0xC (TPL 6/0xF)',
        f're4nmr room package cast/r102/merchant-em18/dc/native/r102/registry.re4nmr (+4 re4tex, prepared em/em18.drs); knob PS2_CAST_MERCHANT=1',
        CONV_M, f'{d}/dc/native/r102/registry.re4nmr', GATE_M)

# 2. chapter-1 cast (e4eb9a49): per-room disc overlays + the converter output per preset
PRESET_ID = {
    'trap-em2a-00': ('em2a t0 bear trap', 'em2a.dat#BIN4/TPL5'), 'trap-em2a-02': ('em2a t2 trap', 'em2a.dat#BIN8/TPL9'),
    'bat-em29-00': ('em29 bat', 'em29.dat#BIN4/TPL5'), 'crawler-em2e-00': ('em2e t0 crawler', 'em2e.dat#BIN4/TPL5'),
    'crawler-em2e-01': ('em2e t1 crawler', 'em2e.dat#BIN4/TPL6'), 'fish-em27-00': ('em27 fish', 'em27.dat#BIN4/TPL5'),
    'snake-em24-00': ('em24 snake', 'em24.dat#BIN5/TPL6'), 'boat-pl0f-00': ('pl0f boat', 'pl0f.dat#BIN5/TPL6'),
    'merchant13-c0': ('em13 t6 (merchant13 closed coat)', 'em13.dat (Codex merchant13-c0)'),
    'merchant13-o0': ('em13 t6 (merchant13 open coat)', 'em13.dat (Codex merchant13-o0)'),
}
for ov in sorted(glob.glob(f'{CONV}/ov-r1*')):
    room = os.path.basename(ov)[3:]
    regs = [r for r in glob.glob(f'{CONV}/reg-{room[1:]}-ch1*') if os.path.isdir(r)]
    if len(regs) != 1:
        sys.exit(f'{room}: registry dirs {regs}')
    names = [x['name'] for x in json.load(open(regs[0] + '/registry-manifest.json'))['room_package']['descriptors']]
    d = f'{LIB}/cast/{room}/ch1-cast'
    copytree(ov, d)
    pkg = f'{d}/dc/native/{room}/registry.re4nmr'
    merged = regs[0].endswith('ch1m')
    for n in names:
        if n not in PRESET_ID:
            continue
        gc, src = PRESET_ID[n]
        row(room, gc, AFS + src,
            f're4nmr room package cast/{room}/ch1-cast/dc/native/{room}/registry.re4nmr'
            + (' (replaces the released package: keeps its descriptors byte-identically)' if merged else ' (new room package)')
            + '; runtime NOT wired (needs prepared archive / allowances / nomination), not on any disc', CONV_E4, pkg)
for p in sorted(PRESET_ID):
    s = f'{CONV}/{p}'
    if not os.path.isdir(s):
        continue
    d = f'{LIB}/cast/common/{p}'
    copytree(s, d, ignore=shutil.ignore_patterns('inputs'))
    for m in glob.glob(f'{CONV}/mask-{p}'):
        copytree(m, f'{LIB}/cast/common/mask-{p}')
    gc, src = PRESET_ID[p]
    tex = sorted(glob.glob(f'{d}/texture/*.re4tex'))
    row('common', gc, AFS + src, f'ps2_cast.py convert+finish output cast/common/{p} (mesh / native / runtime header / VQ atlas'
        + (f' {os.path.basename(tex[0])}' if tex else '') + '); sha = atlas re4tex', CONV_E4, tex[0] if tex else d)

# 3. Ashley pl11 (code + offline data, 778e4674): r117 package + prepared archive
d = f'{LIB}/cast/r117/ashley-pl11'
if os.path.exists(d):
    shutil.rmtree(d)
os.makedirs(f'{d}/dc/native/r117')
os.makedirs(f'{d}/em')
shutil.copy2(f'{ASH}/reg-r117-a7/package/r117/registry.re4nmr', f'{d}/dc/native/r117/registry.re4nmr')
for t in sorted(glob.glob(f'{ASH}/reg-r117-a7/tex/*.re4tex')):
    k = os.path.basename(t)
    os.makedirs(f'{d}/dc/tex/{k[0]}', exist_ok=True)
    shutil.copy2(t, f'{d}/dc/tex/{k[0]}/{k}')
shutil.copy2(f'{ASH}/pl11prep/pl11.drs', f'{d}/em/pl11.drs')
for h in ('ashley11 hands 0xC/0xF', 'ashley11-h1 hands 0xD/0x10', 'ashley11-h3 hands 0xE/0xF'):
    row('r117', f'pl11 Ashley {h}', AFS + 'pl11.dat#BIN4/7/6/9/0xA + hands (Codex extract pl11-PS2.dat)',
        'draw-slot re4nmr room package cast/r117/ashley-pl11/dc/native/r117/registry.re4nmr (+4 re4tex, prepared em/pl11.drs);'
        ' knob PS2_ASHLEY=2; code + offline only, no Flycast run; face expressions need a user look decision', CONV_A,
        f'{d}/dc/native/r117/registry.re4nmr')

# 4. GC-only route characters with no converted output (gap rows)
row('r117', 'em11 t7 zealot', AFS + 'em11.dat#BIN0x1FC/0x1FE/0x204/0x208 (TPL 0x1FD/0x201)',
    'NONE: converter blocked (GC hand BINs 0x204/0x208 = 41-part sparse tables on the 37-bone body); GC on screen', '-', None)
row('r118', 'em3b t1 mine cart', AFS + 'em3b.dat (8,552 PS2 / 5,047 GC tris, rigid)',
    'NONE in ps2cast (Codex has a native r200 truck descriptor on the CH23 route); GC on screen', '-', None)
for r in ('r108', 'r118', 'r111', 'r113', 'r11a'):
    row(r, 'em17/em12 app0 grip hands BIN 0x1C3/0x1C8', AFS + 'em17.dat / em12.dat grip-hand BINs',
        'NONE: ACTOR_GANADO_APP0_GRIP=1 draws them natively from GC-source geometry (no PS2 hands yet)', '-', None)

idx = f'{LIB}/INDEX.tsv'
have = set()
with open(idx) as f:
    for line in f.read().splitlines()[1:]:
        c = line.split('\t')
        if len(c) >= 5:
            have.add((c[0], c[1], c[2], c[4]))
new = [r for r in rows if (r[0], r[1], r[2], r[4]) not in have]
with open(idx, 'a', newline='\n') as f:
    for r in new:
        f.write('\t'.join(x.replace('\t', ' ') for x in r) + '\n')
print(f'rows {len(rows)} appended {len(new)}')
for r in rows:
    print(r[1], '|', r[2], '|', r[6][:16], r[7], '|', r[8][:12])
