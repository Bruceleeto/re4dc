"""Lane crowd: package build-<label> (cbuild.sh) as the harness program candidate-cw<label>.

Usage (WSL): python3 cprep.py <label>
Writes <harness>/programs/candidate-cw<label>/{1ST_READ.BIN,prog.bin,sscrn.ovl,syms.txt} (new dir only) and the
entry in <harness>/programs-crowd.json (this lane's own programs file, passed to stage-scenario.py --programs).
Adapted from the harness's prepare-r21.py (same steps, the build dir as an argument).
"""
from pathlib import Path
import hashlib, json, subprocess, sys

H = Path('/mnt/c/Game Dev/Emulators/re4-assets-private/world-agent-20260926/continuation-20260927/playability-r11-r1')
EV = Path('/root/probe/lanes/crowd')
TOOL = Path('/opt/toolchains/dc/sh-elf/bin')


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


label = sys.argv[1]
arm = f'candidate-cw{label}'
b = EV / f'build-{label}'
elf, ovl = b / 're4dc-game.elf', b / 'sscrn.ovl'
assert sha(elf) == (b / 'elf.sha256').read_text().split()[0]
out = H / 'programs' / arm
out.mkdir(parents=True, exist_ok=False)
subprocess.run([str(TOOL / 'sh-elf-objcopy'), '-R', '.stack', '-O', 'binary', str(elf), str(out / 'prog.bin')], check=True)
subprocess.run(['/root/work/kos/utils/scramble/scramble', str(out / 'prog.bin'), str(out / '1ST_READ.BIN')], check=True)
(out / 'sscrn.ovl').write_bytes(ovl.read_bytes())
syms = {}
for line in subprocess.check_output([str(TOOL / 'sh-elf-nm'), '-S', str(elf)], text=True).splitlines():
    f = line.split()
    if len(f) == 4 and f[-1] in ('_re4dc_logbuf', '_re4dc_log_head', '_re4dc_stage'):
        syms[f[-1]] = int(f[0], 16)
assert len(syms) == 3
(out / 'syms.txt').write_text(' '.join(hex(syms[n] - 0x8c000000) for n in ('_re4dc_logbuf', '_re4dc_log_head', '_re4dc_stage')) + '\n')
pj = H / 'programs-crowd.json'
import fcntl
with open(EV / 'programs-crowd.lock', 'w') as lock:  # two preps at once lost an entry (read-modify-write race)
    fcntl.flock(lock, fcntl.LOCK_EX)
    report = json.loads(pj.read_text()) if pj.exists() else {}
    report[arm] = dict(elf=str(elf), elf_sha256=sha(elf), overlay_sha256=sha(ovl), symbols=syms,
                       files={p.name: dict(bytes=p.stat().st_size, sha256=sha(p)) for p in out.iterdir() if p.is_file()})
    pj.write_text(json.dumps(report, indent=2) + '\n')
print(arm, report[arm]['elf_sha256'])
