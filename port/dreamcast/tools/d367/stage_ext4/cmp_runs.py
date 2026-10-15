"""cmp_runs.py <scenA> <scenB>: compare two harness runs of the same disc (copy vs hard link)."""
import hashlib, json, re, sys
from pathlib import Path
H = Path(r'C:\Game Dev\Emulators\re4-assets-private\world-agent-20260926\continuation-20260927\playability-r11-r1\scenarios')
def load(s):
    c = H / s / 'capture'
    r = json.loads((c / 'run-result.json').read_text())
    log = (c / 'run-output.txt').read_bytes()
    return r, log
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''): h.update(b)
    return h.hexdigest()
(ra, la), (rb, lb) = load(sys.argv[1]), load(sys.argv[2])
for s, r in ((sys.argv[1], ra), (sys.argv[2], rb)):
    print(s, r.get('status'), 'errors', r.get('errors'), 'disc', r.get('disc_sha256', '')[:16])
    d = H / s / 'capture' / 'disc.bin'
    if d.exists(): print('  disc.bin after run sha', sha(d)[:16])
la_l, lb_l = la.splitlines(), lb.splitlines()
n = min(len(la_l), len(lb_l))
same = 0
while same < n and la_l[same] == lb_l[same]: same += 1
print('log lines A %d B %d, identical prefix %d lines' % (len(la_l), len(lb_l), same))
if same < n:
    print('first difference at line %d:\n A: %r\n B: %r' % (same + 1, la_l[same][:200], lb_l[same][:200]))
for pat in (rb'^warp:', rb'HALT', rb'RE4DC MISSING', rb'FAULT', rb'LOG OVERRUN'):
    print(pat.decode(), sum(1 for l in la_l if re.search(pat, l)), sum(1 for l in lb_l if re.search(pat, l)))
