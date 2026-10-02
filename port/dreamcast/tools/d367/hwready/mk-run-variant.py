"""mk-run-variant.py <align|ta> <out.py>: the playability harness's run-emulator.py with the hwmodel Flycast
(route-hw.sh). align: interpreter + HWTRACE_ALIGN=1; ta: dynarec + RE4DC_TA_STATS=<capture>/ta-stats.txt."""
import os, sys
mode, out = sys.argv[1], sys.argv[2]
assert mode in ('align', 'ta'), mode
H = os.environ.get('RE4DC_PLAYABILITY', r'C:\Game Dev\Emulators\re4-assets-private\world-agent-20260926'
                   r'\continuation-20260927\playability-r11-r1')
EXE = os.environ.get('HW_FLYCAST', r'C:\Game Dev\Emulators\flycast-hwmodel\build-hwtrace\flycast.exe')
s = open(os.path.join(H, 'run-emulator.py'), encoding='utf-8').read()


def rep(a, b):
    global s
    assert s.count(a) == 1, a
    s = s.replace(a, b)


rep("HERE=Path(__file__).resolve().parent", "HERE=Path(r'%s')" % H)
rep("assert 30<=args.seconds<=900", "assert 30<=args.seconds<=5400")
inject = "shutil.copyfile(Path(r'%s'),cap/'flycast.exe')\ncfg=(cap/'emu.cfg').read_text()\n" % EXE
if mode == 'align':
    inject += ("cfg=re.sub(r'(?m)^Dynarec\\.Enabled = \\w+\\n','',cfg).replace('[config]\\n','[config]\\nDynarec.Enabled = no\\n',1)\n"
               "assert 'Dynarec.Enabled = no' in cfg\n"
               "os.environ['HWTRACE_DIR']=str(cap);os.environ['HWTRACE_ALIGN']='1'")
else:
    inject += "os.environ['RE4DC_TA_STATS']=str(cap/'ta-stats.txt')"
rep("cfg=(cap/'emu.cfg').read_text()", inject)
open(out, 'w', encoding='utf-8').write(s)
