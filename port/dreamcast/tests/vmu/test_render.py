#!/usr/bin/env python3
"""Independent native-vs-supplied-browser golden comparison; not a second renderer."""
import argparse,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('binary');a=p.parse_args()
frames=json.loads(Path(__file__).with_name('golden-docked.json').read_text())['frames']
def run(values):return subprocess.check_output([a.binary,*map(str,values), '0','0'],text=True).strip()
for f in frames:
    ls=f['leon_state'];o=f['options'];hp=ls['hpPercent'];stage=ls['infectionStage'];scene=f['preview_scene']
    condition=3 if hp<=0 else 2 if hp<=25 else 1 if hp<=50 else 0 # fixture only; production uses getLifeLevel
    mode={'leon':1,'ashley':2,'radio':3}[f['display']];subject=2 if mode==2 else 1;owner=2 if scene=='playable' else 1
    status={'escort':1,'resume':1,'wait':2,'danger':3,'playable':4}.get(scene,0)
    args=[mode,subject,owner,condition,status,100 if owner==2 else hp,100,1,ls['ammo'],stage,int(scene=='danger'),o.get('beat',0),o.get('fromStage',stage),round(o.get('growthReveal',1)*1000),int(o.get('blink',o.get('frame',0)))]
    actual=run(args);expected=f['canonical_row_major_msb_hex']
    if actual!=expected:
        aa=bytes.fromhex(actual);bb=bytes.fromhex(expected)
        coords=[(i%6*8+b,i//6) for i,(x,y) in enumerate(zip(aa,bb)) for b in range(8) if (x^y)&(128>>b)]
        raise AssertionError((f['id'],len(coords),coords[:25]))
print('PASS: all 25 supplied docked golden frames match byte for byte')
subprocess.run([a.binary],check=True)
# Full production ammo range and invalid health maxima must stay inside the buffer.
for n in (0,1,9,10,99,100,999,1000,65535):
    run([1,1,1,0,0,1,2400,1,n,0,0,0,0,1000,0])
for hp,maximum in ((0,0),(-1,1200),(1,0),(1,2400),(4000,2400)):
    run([1,1,1,0,0,hp,maximum,0,0,0,0,0,0,1000,0])
print('PASS: production ammo and health edge cases preserve framebuffer bounds')
