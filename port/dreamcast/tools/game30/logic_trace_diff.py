#!/usr/bin/env python3
"""Compare two determinism traces (LT/LU line pairs from port/dreamcast/game/logic_trace.cpp, LOGIC_TRACE=1).

    logic_trace_diff.py REF.txt CAND.txt [--align frame|room|auto] [--room 0100] [--from K] [--to K]
                        [--json out.json]

Inputs are whatever read_log.py / the serial console captured (run-output.txt, serial.txt); other
lines are ignored. Exit status: 0 STRICT, 1 divergence, 2 unusable (no overlap).

Alignment (what "the same tick" means):
  frame  key = pG->Frame_cnt. Valid when both runs spent the same number of frames in every load
         wait (A/A of one build; builds whose frame time is equal).
  room   key = Frame_cnt - (first tick in room --room with the player present). Use for A/B of
         builds with different frame times: loading waits before the room may take a different
         number of frames, the room's own logic must then be identical tick for tick.
  auto   finds the offset that best matches (rng, room, player position) and reports it; for
         exploration only - the verdict text says which offset was used.

Verdicts:
  STRICT    every field identical on every aligned tick: behaviour-neutral change.
  DISCRETE  rng / flags / room / routine / hp / alive counts identical but float state differs:
            sub-ULP drift. NOT acceptable for collision / sequencing without the user's sign-off.
  FAIL      a discrete field differs (RNG draw count, routine bytes, flags, alive sets).

Trace extras (game30.mk, Phase 2 D5): TRACE_ALLOC=1 adds the LU field af=<failed heap-4 allocations>/<hash>, a
discrete field (compared when either run has it; a run without it reads "-"). TRACE_SS_MASK=1 prints the player /
enemy / object fields as "~" while the sub screen backing is swapped out; "~" compares equal only to "~", so a
tick masked in one run and not the other still differs. "masked" counts the compared ticks masked in both runs.

Protocol (see README): A/A (reference twice) must be STRICT with --align frame; the timing
control (reference with LOGIC_TRACE_DELAY_US>0 vs reference) must be STRICT with --align room;
only then is an A/B verdict (--align room) meaningful.
"""
import argparse, json, re, sys

DISCRETE = ['r', 'sy', 'sp', 'st', 'rf', 'sc', 'rm', 'ms', 'ps', 'e', 'es', 'o', 'os']
FLOAT = ['p', 'a', 'mf', 'pf', 'pm', 'ef', 'em', 'of', 'om', 'c']
OPTIONAL = ['af']                  # TRACE_ALLOC=1 only
LINE = re.compile(r'\b(L[TU]) (t=\d+ .*)$')

def parse(path):
    """One sample = an LT line and an LU line with the same (t, n) (the hook splits it because the
    log ring's line buffer is 256 bytes). A sample missing either half or any field (torn at a ring
    wrap) is dropped, never compared with fields missing."""
    parts, kinds = {}, {}
    for raw in open(path, errors='replace'):
        m = LINE.search(raw.rstrip('\r\n'))
        if not m:
            continue
        kv = dict(tok.split('=', 1) for tok in m.group(2).split() if '=' in tok)
        if 'm' in kv and '/' in kv['m']:
            kv['mf'], kv['ms'] = kv.pop('m').split('/', 1)
        try:
            key = (int(kv.pop('t')), kv.pop('n', None))
        except (KeyError, ValueError):
            continue
        parts.setdefault(key, {}).update(kv)
        kinds.setdefault(key, set()).add(m.group(1))
    recs, dups = {}, 0
    for (t, n), kv in parts.items():
        if kinds[(t, n)] != {'LT', 'LU'} or any(k not in kv for k in DISCRETE + FLOAT):
            continue                      # torn sample
        if t in recs and recs[t] != kv:
            dups += 1                     # same Frame_cnt twice with different state (soft reset?)
        recs[t] = kv
    ks = sorted(recs)
    gaps = [(a, b) for a, b in zip(ks, ks[1:]) if b != a + 1]
    return recs, dups, gaps

def anchor(recs, room):
    for t in sorted(recs):
        r = recs[t]
        if r.get('rm', '').lower() == room and r.get('p') not in (None, '00000000,00000000,00000000', '~,~,~'):
            return t
    return None

def best_offset(R, C, span=3000):
    rk = sorted(R)
    sig = lambda r: (r.get('r'), r.get('rm'), r.get('p'))
    csig = {}
    for t, r in C.items():
        csig.setdefault(sig(r), []).append(t)
    votes = {}
    for t in rk:
        for u in csig.get(sig(R[t]), [])[:50]:
            d = u - t
            if abs(d) <= span:
                votes[d] = votes.get(d, 0) + 1
    if not votes:
        return 0, 0
    d = max(votes, key=votes.get)
    return d, votes[d]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ref'); ap.add_argument('cand')
    ap.add_argument('--align', default='frame', choices=['frame', 'room', 'auto'])
    ap.add_argument('--room', default=None, help='hex stage<<8|room, default: room of the reference\'s last record')
    ap.add_argument('--from', dest='lo', type=int, default=None)
    ap.add_argument('--to', dest='hi', type=int, default=None)
    ap.add_argument('--json')
    a = ap.parse_args()
    R, rd, rg = parse(a.ref)
    C, cd, cg = parse(a.cand)
    out = dict(ref=a.ref, cand=a.cand, ref_records=len(R), cand_records=len(C), ref_gaps=rg[:10],
               cand_gaps=cg[:10], ref_duplicates=rd, cand_duplicates=cd, align=a.align)
    if not R or not C:
        out['verdict'] = 'UNUSABLE'; print(json.dumps(out, indent=1)); return 2
    if a.align == 'frame':
        dr = dc = 0
    elif a.align == 'room':
        room = (a.room or R[max(R)]['rm']).lower()
        ta, tc = anchor(R, room), anchor(C, room)
        out.update(room=room, ref_anchor=ta, cand_anchor=tc)
        if ta is None or tc is None:
            out['verdict'] = 'UNUSABLE (room never reached)'; print(json.dumps(out, indent=1)); return 2
        dr, dc = ta, tc
        if a.lo is None:
            a.lo = 0                      # the room's own ticks; earlier loading waits differ by design
    else:
        room = (a.room or R[max(R)]['rm']).lower()
        Rr = {t: v for t, v in R.items() if v.get('rm', '').lower() == room}
        d, votes = best_offset(Rr, C)
        out.update(room=room, auto_offset=d, auto_votes=votes)
        dr, dc = 0, d
        if a.lo is None and Rr:
            a.lo = min(Rr)
    RA = {t - dr: v for t, v in R.items()}
    CA = {t - dc: v for t, v in C.items()}
    common = sorted(k for k in set(RA) & set(CA)
                    if (a.lo is None or k >= a.lo) and (a.hi is None or k <= a.hi))
    if not common:
        out['verdict'] = 'UNUSABLE (no overlap)'; print(json.dumps(out, indent=1)); return 2
    fields = DISCRETE + [f for f in OPTIONAL if any(f in v for v in R.values()) or any(f in v for v in C.values())] + FLOAT
    disc = set(fields) - set(FLOAT)
    counts = {f: 0 for f in fields}
    masked = 0
    first = first_discrete = None
    for k in common:
        r, c = RA[k], CA[k]
        diff = [f for f in fields if r.get(f, '-') != c.get(f, '-')]
        if r.get('e') == '~' and c.get('e') == '~':
            masked += 1
        for f in diff:
            counts[f] += 1
        if diff and first is None:
            first = dict(key=k, ref_frame=k + dr, cand_frame=k + dc, fields={f: [r.get(f), c.get(f)] for f in diff})
        if first_discrete is None and any(f in disc for f in diff):
            first_discrete = dict(key=k, ref_frame=k + dr, cand_frame=k + dc,
                                  fields={f: [r.get(f), c.get(f)] for f in diff if f in disc})
    rooms = sorted({RA[k].get('rm') for k in common})
    out.update(window=[common[0], common[-1]], compared=len(common), masked=masked, rooms=rooms,
               first_divergence=first, first_discrete_divergence=first_discrete,
               ticks_with_field_difference={k: v for k, v in counts.items() if v})
    if first is None:
        out['verdict'] = 'STRICT'
    elif first_discrete is None:
        out['verdict'] = 'DISCRETE (float drift only)'
    else:
        out['verdict'] = 'FAIL'
    if rg or cg:
        out['warning'] = 'frame gaps (log ring overrun or capture stop); verdict covers aligned ticks only'
    print(json.dumps(out, indent=1))
    if a.json:
        open(a.json, 'w').write(json.dumps(out, indent=1))
    return 0 if out['verdict'] == 'STRICT' else 1

if __name__ == '__main__':
    sys.exit(main())
