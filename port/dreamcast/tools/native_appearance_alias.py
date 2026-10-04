#!/usr/bin/env python3
"""Native appearance aliases (native scene coverage, 2026-10-03): which Ganado (module, model type) pairs load
EXACTLY the source models of an appearance the actor owner path already certifies, so the existing native cast
draws their actual source appearance.

The owner path admits a Ganado only when coarse_actor_material.inc source_appearance_type(appearance, id, type)
names its (module id, cModel::type); every role row of actor_material_records.inc then proves the live infos'
BIN / TPL owners by content (normalized BIN digests at archive adoption, TPL descriptors every draw). The
certified table was written for em15 types 0/3/4/11 and em12 type 1. Other Ganado modules share the cEm10 class
and bind the same archive entry numbers for some model types (src/emXX/emXX_set.cpp); for those this tool proves,
from the original archives, that every model slot the source loads for that type (mot[0..20]: TPL, body, head,
cloth, hands, hand poses, stumps) and every role row's BIN/TPL of the appearance are byte-identical entries. Only
such pairs are emitted as aliases; nothing is relabelled on a signature match alone, and no check is relaxed.

usage (WSL, pure Python; reads the GC disc through assetpipe sources.toml, or --archive-dir):
  native_appearance_alias.py check <out.json> [--archives em12,em13,em16,em17] [--archive-dir DIR]
                                   [--emit game/actor_appearance_aliases.inc --emit-archives em12]
  ACTOR_APPEARANCE_ALIAS=2 table: --emit game/actor_appearance_aliases_ext.inc --emit-archives em12,em13,em16,em17,em10
                                  --knob 2
Exit status 0 when every requested --emit-archives pair set verified (or nothing was requested), 1 otherwise.
Fail closed: a setter outside SETTER_SHAPE (an unparsed / duplicate / missing mot write, a branch, fallthrough or
any other statement) is 'unsupported-source' and never emitted; a certified module in that state stops the tool.
The report records the setter, shared-draw, material-record and archive hashes and a semantic digest that the
generated table's header repeats (logical source names only, no machine paths).
"""
import argparse, hashlib, json, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GAME = HERE.parent / 'game'
REPO = HERE.parents[2]
sys.path[:0] = [str(HERE), str(REPO / 'tools')]
import drs  # noqa: E402

MODEL_SLOTS = range(0, 21)  # w->mot[0..20]: TPL, body, head, cloth, hands, hand poses / stumps (EmXXSet)
ALL_SLOTS = range(0, 41)    # w->mot[0..40]: every case must assign each exactly once (21..40 are reported)


class SourceError(Exception):
    """The setter is not in the one reviewed shape; nothing from it may be certified."""


def _strip_comments(s):
    s = re.sub(r'/\*.*?\*/', ' ', s, flags=re.S)
    return re.sub(r'//[^\n]*', '', s)


def _braced(s, open_at):
    """s[open_at] == '{' -> the text between it and its matching '}'."""
    depth = 0
    for i in range(open_at, len(s)):
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                return s[open_at + 1:i]
    raise SourceError('unbalanced braces')


SETTER_SHAPE = """void EmXXSet(cEm10* em) { Em10Work* w = EM10_WK(em); switch (em->type) { <groups> }
  [w->Ganado = N;] [EmXXWeaponSet(em);] }  -- each group: one or more 'case N:' / 'default:' labels, then only
  'w->mot[K] = ARC(0x..);' / 'w->mot[K] = 0;' (K = 0..40, each exactly once), optional 'em->type = N;' (every numeric
  case label of the group equal to N; a default label may normalise to N) and 'Em10SetSeTbl(em, N);', ending in 'break;' (or the closing brace for the last group)."""


def set_cases(module):
    """EmXXSet -> {type: {slot: arc}} (and 'default'), or None when the module has no setter file. Fails closed
    (SourceError) on any statement, branch, fallthrough, duplicate or missing slot write outside SETTER_SHAPE, so a
    source change can never silently widen certification."""
    p = REPO / f'src/{module}/{module}_set.cpp'
    if not p.exists():
        return None
    s = _strip_comments(p.read_text())
    name = module.capitalize() + 'Set'
    heads = [m for m in re.finditer(r'\bvoid\s+%s\s*\(\s*cEm10\s*\*\s*em\s*\)\s*\{' % name, s)]
    if len(heads) != 1:
        raise SourceError(f'{name}: {len(heads)} definitions')
    body = _braced(s, heads[0].end() - 1)
    sw = list(re.finditer(r'\bswitch\s*\(\s*em->type\s*\)\s*\{', body))
    if len(sw) != 1 or len(re.findall(r'\bswitch\b', body)) != 1:
        raise SourceError(f'{name}: expected exactly one switch (em->type)')
    pre = body[:sw[0].start()].split()
    if ' '.join(pre) != 'Em10Work* w = EM10_WK(em);':
        raise SourceError(f'{name}: unexpected statements before the switch: {" ".join(pre)!r}')
    inner = _braced(body, sw[0].end() - 1)
    post = body[sw[0].end() + len(inner) + 1:]
    post_ok = re.fullmatch(r'\s*(?:w->Ganado\s*=\s*\d+\s*;\s*)?(?:%sWeaponSet\s*\(\s*em\s*\)\s*;\s*)?' % module.capitalize(), post)
    if not post_ok:
        raise SourceError(f'{name}: unexpected statements after the switch: {post.strip()!r}')
    if re.search(r'\b(if|else|for|while|do|goto|return)\b|\?|\{', inner):
        raise SourceError(f'{name}: branch or block inside the switch')
    tokens = re.findall(r'(case\s+(?:0x[0-9A-Fa-f]+|\d+)\s*:|default\s*:|[^;:]+;)', inner)
    if re.sub(r'\s+', '', ''.join(tokens)) != re.sub(r'\s+', '', inner):
        raise SourceError(f'{name}: unparsed text in the switch')
    out, labels, stmts = {}, [], []

    def close(ended_by_break):
        if not labels:
            if stmts:
                raise SourceError(f'{name}: statements before the first label')
            return
        if not stmts:
            raise SourceError(f'{name}: empty group {labels}')
        if not ended_by_break:
            raise SourceError(f'{name}: group {labels} falls through')
        slots, retype = {}, None
        for st in stmts:
            m = re.fullmatch(r'w->mot\[(\d+)\]\s*=\s*(?:ARC\((0x[0-9A-Fa-f]+)\)|(0))\s*;', st)
            if m:
                k = int(m.group(1))
                if k in slots:
                    raise SourceError(f'{name}: group {labels} writes mot[{k}] twice')
                slots[k] = int(m.group(2), 16) if m.group(2) else 0
                continue
            if re.fullmatch(r'Em10SetSeTbl\(\s*em\s*,\s*\d+\s*\)\s*;', st):
                continue
            m = re.fullmatch(r'em->type\s*=\s*(\d+)\s*;', st)
            if m:
                # Only an identity rewrite keeps every label's key true: every numeric label must already be N (a
                # default label may normalise to N). 'case 1: case 2: em->type = 1;' would make type 2 run as type 1.
                n = int(m.group(1))
                if retype is not None:
                    raise SourceError(f'{name}: group {labels} rewrites em->type twice')
                if any(lab != n for lab in labels if lab != 'default'):
                    raise SourceError(f'{name}: group {labels} rewrites em->type to {n} (a label other than {n} '
                                      f'would not keep its own type)')
                retype = n
                continue
            raise SourceError(f'{name}: group {labels}: unsupported statement {st!r}')
        if set(slots) != set(ALL_SLOTS):
            raise SourceError(f'{name}: group {labels} does not assign mot[0..40] exactly once '
                              f'(missing {sorted(set(ALL_SLOTS) - set(slots))}, extra {sorted(set(slots) - set(ALL_SLOTS))})')
        for lab in labels:
            if lab in out:
                raise SourceError(f'{name}: label {lab} twice')
            out[lab] = slots

    for t in (x.strip() for x in tokens):
        if t.startswith('case') or t.startswith('default'):
            if stmts and not labels:
                raise SourceError(f'{name}: statements before the first label')
            if stmts and labels:
                if stmts[-1] != 'break;':
                    raise SourceError(f'{name}: group {labels} falls through into {t}')
            if stmts and labels:
                stmts.pop(); close(True); labels, stmts = [], []
            labels.append('default' if t.startswith('default') else int(t[4:-1].strip(), 0))
        else:
            stmts.append(re.sub(r'\s+', ' ', t))
    if labels:
        last_break = bool(stmts) and stmts[-1] == 'break;'
        if last_break:
            stmts.pop()
        close(True)
    if not out:
        raise SourceError(f'{name}: no case groups')
    return out


def file_sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def material_revision():
    s = (GAME / 'platform/include/actor_lifetime.h').read_text()
    m = re.search(r'#define\s+RE4DC_ACTOR_MATERIAL_RECORD_REVISION\s+(0x[0-9A-Fa-f]+)u', s)
    if not m:
        raise SourceError('RE4DC_ACTOR_MATERIAL_RECORD_REVISION not found')
    return m.group(1)


def shared_draw(module):
    """The module's Init must construct the shared cEm10 class (em10.cpp draw/postlude) and register EmXXSet."""
    p = REPO / f'src/{module}/{module}_set.cpp'
    s = _strip_comments(p.read_text())
    cap = module.capitalize()
    ok = (re.search(r'\bvoid\s+%sInit\s*\(\s*cEm\s*\*\s*em\s*\)\s*\{[^}]*new\s*\(em\)\s*cEm10\b' % cap, s, re.S) is not None
          and re.search(r'Em10SetFunc\s*=\s*%sSet\s*;' % cap, s) is not None)
    if not ok:
        raise SourceError(f'{module}: Init does not construct cEm10 / register {cap}Set')
    return True


def certified_table():
    """source_appearance_type's appearance -> (module id, type), parsed from coarse_actor_material.inc."""
    s = (GAME / 'coarse_actor_material.inc').read_text()
    f = s[s.index('inline bool source_appearance_type'):]
    f = f[:f.index('\n}') + 2]
    types = [int(x, 0) for x in re.search(r'types\[\d+\]=\{([^}]*)\}', f).group(1).split(',')]
    m = re.search(r'id==\(appearance==0\?(0x[0-9a-fA-F]+)u:(0x[0-9a-fA-F]+)u\)', f)
    first, rest = int(m.group(1), 16), int(m.group(2), 16)
    return {a: (first if a == 0 else rest, t) for a, t in enumerate(types)}, f


def role_rows():
    s = (GAME / 'actor_material_records.inc').read_text()
    rows = []
    for a, r, b, t, mdl, tex, n in re.findall(r'\{(\d+)u,(\d+)u,(\d+)u,(\d+)u,&m_(\w+),t_(\w+),(\d+)u\}', s):
        rows.append(dict(appearance=int(a), role=int(r), bin=int(b), tpl=int(t), model=mdl, textures=tex, count=int(n)))
    return rows


class Source:
    def __init__(self, archive_dir):
        self.dir = Path(archive_dir) if archive_dir else None
        self.iso = None
        self.cache, self.sha = {}, {}

    def archive(self, module):
        if module not in self.cache:
            if self.dir:
                p = self.dir / f'{module}.drs'
                data = p.read_bytes() if p.exists() else None
                origin = f'--archive-dir:{module}.drs'
            else:
                if self.iso is None:
                    from assetpipe.config import Config
                    from assetpipe.rooms import GcIso
                    self.iso = GcIso(Config().path('gc_iso'))
                    self.iso_path = str(Config().path('gc_iso'))
                try:
                    data = self.iso.read(f'em/{module}.drs')
                except KeyError:
                    data = None
                origin = f'GC disc 1 (sources.toml gc_iso):em/{module}.drs'
            self.cache[module] = drs.Drs(data) if data else None
            self.sha[module] = dict(origin=origin, sha256=hashlib.sha256(data).hexdigest() if data else None,
                                    bytes=len(data) if data else 0)
        return self.cache[module]


def entry(arc, no):
    i = no - 4
    if arc is None or i < 0 or i >= len(arc.entries):
        return None
    t, d = arc.entries[i]
    return drs.tag_name(t), d


def compare(src, module, typ, slots, cert_module, cert_slots, appearance, rows):
    a, b = src.archive(module), src.archive(cert_module)
    res = dict(module=module, type=typ, appearance=appearance, certified_by=f'{cert_module} type {cert_slots["_type"]}')
    want = {k: slots[k] for k in MODEL_SLOTS}   # set_cases guarantees every slot was written exactly once
    have = {k: cert_slots[k] for k in MODEL_SLOTS}
    res['slot_arcs'] = {str(k): hex(v) for k, v in want.items() if v}
    # mot[21..40] (accessory models, event motions) are not part of the certified body/head/hand/TPL set: listed so a
    # reviewer sees every difference; an extra accessory info still fails the runtime role binding (fail closed).
    res['slots_21_40_diff'] = {str(k): [hex(slots[k]), hex(cert_slots[k])] for k in ALL_SLOTS
                               if k >= 21 and slots[k] != cert_slots[k]}
    if want != have:
        res['status'] = 'slots-differ'
        res['slot_diff'] = {str(k): [hex(want[k]), hex(have[k])] for k in MODEL_SLOTS if want[k] != have[k]}
        return res
    # mot[21..40] hold accessory models the source attaches later (em10.cpp: em10SackSet mot[21]/[22], the hood
    # mot[23..25], pAccesory mot[28..]). A slot this type loads must be the certified type's own entry, byte for byte;
    # a slot it leaves empty only removes an accessory. Anything else is held out ('accessory-differs'), not emitted.
    acc = []
    for k in ALL_SLOTS:
        if k < 21 or not slots[k]:
            continue
        x, y = entry(a, slots[k]), entry(b, cert_slots[k]) if cert_slots[k] else None
        if x is None or y is None or x[0] != y[0] or x[1] != y[1]:
            acc.append(dict(slot=k, arc=[hex(slots[k]), hex(cert_slots[k])],
                            sha256=[hashlib.sha256(x[1]).hexdigest() if x else None,
                                    hashlib.sha256(y[1]).hexdigest() if y else None]))
    if acc:
        res['status'] = 'accessory-differs'
        res['accessory_diff'] = acc
        return res
    loaded = {v for v in want.values() if v}
    arcs = set(loaded)
    unreachable = []
    for r in rows:
        if r['appearance'] != appearance:
            continue
        # A role row whose BIN this module never loads for this type (an em15-only accessory) cannot match a live
        # info of this actor; it is listed, not compared.
        if r['bin'] in loaded:
            arcs |= {r['bin'], r['tpl']}
        else:
            unreachable.append(dict(role=r['role'], bin=r['bin'], tpl=r['tpl']))
    res['unreachable_rows'] = unreachable
    ent, bad = {}, []
    for no in sorted(arcs):
        x, y = entry(a, no), entry(b, no)
        if x is None or y is None:
            bad.append(dict(arc=hex(no), why='missing', present=[x is not None, y is not None]))
            continue
        hx, hy = hashlib.sha256(x[1]).hexdigest(), hashlib.sha256(y[1]).hexdigest()
        ent[hex(no)] = dict(tag=x[0], bytes=len(x[1]), sha256=hx)
        if x[0] != y[0] or hx != hy:
            bad.append(dict(arc=hex(no), why='bytes', tags=[x[0], y[0]], sha256=[hx, hy], bytes=[len(x[1]), len(y[1])]))
    res['entries'] = ent
    res['mismatches'] = bad
    res['status'] = 'verified' if not bad else 'bytes-differ'
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    c = sub.add_parser('check')
    c.add_argument('out', type=Path)
    c.add_argument('--archives', default='em12,em13,em16,em17')
    c.add_argument('--archive-dir')
    c.add_argument('--emit', type=Path)
    c.add_argument('--emit-archives', default='')
    c.add_argument('--knob', type=int, default=1, help='ACTOR_APPEARANCE_ALIAS value that reads the emitted table')
    a = ap.parse_args()

    try:
        cert, cert_src = certified_table()
    except (AttributeError, ValueError) as e:
        sys.exit(f'source_appearance_type: not in the reviewed shape ({e})')
    rows = role_rows()
    src = Source(a.archive_dir)
    cert_slots = {}
    setters = {}
    for app, (mid, typ) in cert.items():
        module = 'em%02x' % mid
        try:
            cases = set_cases(module)
            shared_draw(module)
        except SourceError as e:
            sys.exit(f'certified appearance {app}: {e}')
        setters[module] = file_sha(REPO / f'src/{module}/{module}_set.cpp')
        if cases is None or typ not in cases:
            sys.exit(f'certified appearance {app}: {module} has no type {typ} case')
        s = dict(cases[typ]); s['_type'] = typ
        role0 = [r for r in rows if r['appearance'] == app and r['role'] == 0]
        role1 = [r for r in rows if r['appearance'] == app and r['role'] == 1]
        # The certified table must agree with the role rows (body / head / TPL of the appearance).
        if not role0 or s.get(1) != role0[0]['bin'] or s.get(0) != role0[0]['tpl'] or not role1 or s.get(2) != role1[0]['bin']:
            sys.exit(f'certified appearance {app} ({module} type {typ}) does not match its role rows')
        cert_slots[app] = (module, s)

    results = []
    for module in [m for m in a.archives.split(',') if m]:
        try:
            cases = set_cases(module)
            if cases is not None:
                shared_draw(module)
        except SourceError as e:
            results.append(dict(module=module, status='unsupported-source', why=str(e)))
            continue
        if cases is None:
            results.append(dict(module=module, status='no-set-function'))
            continue
        setters[module] = file_sha(REPO / f'src/{module}/{module}_set.cpp')
        for typ, slots in sorted(((k, v) for k, v in cases.items() if k != 'default'), key=lambda x: x[0]):
            match = None
            for app, (cm, cs) in cert_slots.items():
                if cs.get(1) == slots.get(1) and cs.get(2) == slots.get(2) and cs.get(0) == slots.get(0):
                    match = app
            if match is None:
                results.append(dict(module=module, type=typ, status='no-certified-appearance',
                                    body=hex(slots.get(1, 0)), head=hex(slots.get(2, 0)), tpl=hex(slots.get(0, 0))))
                continue
            cm, cs = cert_slots[match]
            if cm == module and cs['_type'] == typ:
                results.append(dict(module=module, type=typ, appearance=match, status='certified'))
                continue
            results.append(compare(src, module, typ, slots, cm, cs, match, rows))

    emit_mods = [m for m in a.emit_archives.split(',') if m]
    emitted, ok = [], True
    for m in emit_mods:
        mine = [r for r in results if r.get('module') == m]
        ver = [r for r in mine if r['status'] == 'verified']
        if not ver:
            ok = False
        emitted += ver
    inputs = dict(
        setters={m: dict(file=f'src/{m}/{m}_set.cpp', sha256=h) for m, h in sorted(setters.items())},
        setter_shape=SETTER_SHAPE,
        shared_draw=dict(file='src/em10/em10.cpp', sha256=file_sha(REPO / 'src/em10/em10.cpp'),
                         note='every compared module constructs cEm10 (em10.cpp draw, ModelTrans/commonModelTrans '
                              'postlude) and registers its EmXXSet; weapons (EmXXWeaponSet) and effects are NOT '
                              'certified by this table'),
        material_records=dict(file='port/dreamcast/game/actor_material_records.inc',
                              sha256=file_sha(GAME / 'actor_material_records.inc'), revision=material_revision()),
        certified_source=dict(file='port/dreamcast/game/coarse_actor_material.inc',
                              source_appearance_type_sha256=hashlib.sha256(cert_src.encode()).hexdigest()))
    semantic = dict(certified={str(k): ['%#x' % v[0], v[1]] for k, v in cert.items()},
                    setters={m: v['sha256'] for m, v in inputs['setters'].items() if m in emit_mods or
                             any(c[0] == m for c in cert_slots.values())},
                    records=[inputs['material_records']['sha256'], inputs['material_records']['revision']],
                    archives={m: src.sha[m]['sha256'] for m in sorted(src.sha)},
                    emitted=[[r['appearance'], r['module'], r['type'], sorted((k, v['sha256']) for k, v in r['entries'].items())]
                             for r in emitted])
    digest = hashlib.sha256(json.dumps(semantic, sort_keys=True).encode()).hexdigest()
    # Eligibility counts per module: every type the setter names, by status, and how many rows this run emitted.
    eligibility = {}
    for r in results:
        e = eligibility.setdefault(r['module'], dict(types=0, emitted=0, by_status={}))
        e['types'] += 1 if r.get('type') is not None else 0
        e['by_status'][r['status']] = e['by_status'].get(r['status'], 0) + 1
    for r in emitted:
        eligibility[r['module']]['emitted'] += 1
    report = dict(tool='native_appearance_alias.py', certified={str(k): ['%#x' % v[0], v[1]] for k, v in cert.items()},
                  inputs=inputs, archives=src.sha, results=results, semantic_digest=digest, eligibility=eligibility,
                  emitted=[[r['appearance'], r['module'], r['type']] for r in emitted])
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=1) + '\n')
    if a.emit and emit_mods:
        lines = ['// GENERATED by port/dreamcast/tools/native_appearance_alias.py check --emit (do not edit).',
                 '// Rows {appearance, module id, cModel::type}: this module/type loads byte-identical source entries',
                 '// for every model slot (mot[0..20]) and every reachable role BIN/TPL of the certified appearance.',
                 f'// Read by source_appearance_type under ACTOR_APPEARANCE_ALIAS={a.knob}; all role/material/owner proofs still run.',
                 '// Weapons (EmXXWeaponSet) and effects are not certified by this table.',
                 f'// semantic digest {digest} (certified table, setter sources, material records '
                 f'{inputs["material_records"]["revision"]}, archives, per-entry hashes; see the check report)']
        for m in sorted(set(emit_mods) | {c[0] for c in cert_slots.values()}):
            src.archive(m)
            lines.append(f'// {m}: {src.sha[m]["origin"]} sha256 {src.sha[m]["sha256"]}; '
                         f'src/{m}/{m}_set.cpp sha256 {setters[m]}')
        for r in emitted:
            lines.append(f'{{{r["appearance"]}u,0x{int(r["module"][2:], 16):02x}u,{r["type"]}u}}, '
                         f'// {r["module"]} type {r["type"]} = {r["certified_by"]}, {len(r["entries"])} entries identical')
        a.emit.write_text('\n'.join(lines) + '\n')
    for r in results:
        print(r.get('module'), r.get('type'), r.get('appearance', '-'), r['status'],
              len(r.get('entries', {})) if 'entries' in r else '', r.get('mismatches') or r.get('slot_diff') or '')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
