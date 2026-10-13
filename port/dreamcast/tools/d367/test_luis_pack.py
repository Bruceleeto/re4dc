#!/usr/bin/env python3
"""Run the real package checker against a pinned Luis fixture and malformed copies.

Usage: test_luis_pack.py <registry.re4nmr> <fresh private output directory>
Input may use synthetic replacement pixels for structural testing. This test
neither proves texture sampling fidelity nor authorizes staging its input.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import subprocess
import sys

HERE=Path(__file__).resolve().parent
GAME=HERE.parents[1]/'game'

def main():
    if len(sys.argv)!=3:raise SystemExit(__doc__)
    fixture=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(exist_ok=False,parents=True)
    module=importlib.util.spec_from_file_location('packtest',HERE/'model_registry_pack_test.py')
    pt=importlib.util.module_from_spec(module);module.loader.exec_module(pt)
    good=fixture.read_bytes();orig=pt.Pack(good)
    assert orig.u32(32)==0x11c and orig.sec('desc')['count']==1 and orig.sec('ref')['count']==6
    assert orig.u32(orig.rec('desc',0,48)+20)==4 and orig.u32(orig.rec('ref',2,16)+8)==0x80000001
    mat=(GAME/'coarse_actor_material.inc').read_text();reg=(GAME/'coarse_actor_owner_registry.inc').read_text()
    a=mat.index('struct Digest');b=mat.index('\n',mat.index('struct SourceBlob'))+1
    c=reg.index('namespace nmr {');d=reg.index('\n',reg.index('constexpr unsigned kRegDescriptors=16'))+1
    (out/'pack_test_types.h').write_text('#pragma once\n#include <cstdint>\nnamespace re4dc_material {\n'+mat[a:b]+'#include "actor_material_records.inc"\n}\n'+reg[c:d]+reg[reg.index('nmr::Chunk registry_geom_view('):reg.index('nmr::Chunk registry_gview(')])
    compile=['g++','-std=c++17','-O1','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-variable','-DRE4DC_ACTOR_PL08=1','-DRE4DC_ACTOR_WIDE_IDENTITY=1','-DRE4DC_NATIVE_MODEL_REGISTRY_PACK=1','-DRE4DC_NMR_BONES=96','-DRE4DC_NMR_MASK=1','-DRE4DC_NMR_SHIFT=1','-I',str(out),'-I',str(GAME),str(HERE/'model_registry_pack_test.cpp')]
    for on,ch23 in ((0,1),(1,0),(1,1)):
        label=f'{on}{ch23}'
        subprocess.run(compile+[f'-DRE4DC_ROUTE_CH22={on}',f'-DRE4DC_ROUTE_CH23={ch23}','-o',str(out/f'validator-{label}')],check=True)
    built,absent=pt.cases(good);skip={'role-capacity','ref-bones','identity-ambiguous'}
    cases=[]
    for name,why,p in built:
        if name in skip:continue
        if name=='descriptor-sections':why='descriptor';p=pt.Pack(good);p.put(p.rec('desc',0,48)+28,0);p.fix()
        if name=='role-range':p=pt.Pack(good);p.put(p.rec('role',0,32)+4,8);p.fix()
        cases.append((name,why,p,0x11c,1))
    def add(name,mut,why='ref',room=0x11c,on=1):
        p=pt.Pack(good);mut(p);p.fix();cases.append((name,why,p,room,on))
    add('CH22-disabled',lambda p:None,'ref',on=0)
    add('other-room',lambda p:p.put(32,0x11d),'ref',room=0x11d)
    add('other-model',lambda p:p.put(p.rec('desc',0,48)+20,5))
    add('other-bones',lambda p:p.put(p.rec('desc',0,48)+24,89))
    for role in (0,1,3,4,5):add(f'alias-other-role-{role}',lambda p,i=role:p.put(p.rec('ref',i,16)+8,0x80000001))
    for own in (0,2,3,4,5,7):add(f'alias-wrong-owner-{own}',lambda p,i=own:p.put(p.rec('ref',2,16)+8,0x80000000|i))
    add('alias-missing',lambda p:p.put(p.rec('ref',2,16)+8,2),'binding')
    add('alias-geometry-mismatch',lambda p:p.put(p.rec('ref',2,16),p.u32(p.rec('ref',0,16))))
    add('alias-texture-mismatch',lambda p:p.put(p.rec('ref',2,16)+4,1))
    mw=orig.u32(orig.rec('ref',3,16)+12);gh=((mw>>8)&255)-1
    for role in (1,2):add(f'head-mask-{role}',lambda p,i=role:p.put(p.rec('ref',i,16)+12,mw))
    for role in (0,4,5):add(f'mask-only-other-role-{role}',lambda p,i=role:p.put(p.rec('ref',i,16)+12,mw))
    add('mask-only-missing',lambda p:p.put(p.rec('ref',3,16)+12,0))
    add('mask-geometry-outside',lambda p:p.put(p.rec('ref',3,16)+12,(mw&~0xff00)|0xff00))
    add('mask-geometry-primary',lambda p:p.put(p.rec('ref',3,16)+12,(mw&~0xff00)|((p.u32(p.rec('ref',3,16))+1)<<8)))
    add('mask-colour-same-as-mask',lambda p:p.put(p.rec('ref',3,16)+12,(mw&~0xff0000)|((mw>>24)<<16)))
    add('mask-colour-primary',lambda p:p.put(p.rec('ref',3,16)+12,mw&~0xff0000))
    add('mask-triangle-incomplete',lambda p:p.put(p.rec('geom',gh,64)+12,p.u32(p.rec('geom',gh,64)+12)-1))
    add('zero-geometry',lambda p:p.put(p.rec('geom',gh,64)+12,0),'geometry')
    def changed_array(p,offset):
        at=p.sec('blob')['at']+p.u32(p.rec('geom',gh,64)+offset);p.put(at,p.u32(at)^1);p.regeom()
    for field,offset in [('positions',32),('normals',36),('weights',48)]:add('mask-'+field+'-mismatch',lambda p,o=offset:changed_array(p,o))
    for role in range(6):
        for digestword in (12,16,20):add(f'source-identity-{role}-{digestword}',lambda p,i=role,j=digestword:p.put(p.rec('sblob',i,32)+j,p.u32(p.rec('sblob',i,32)+j)^1),'binding')
        add(f'source-tpl-{role}',lambda p,i=role:p.put(p.rec('role',i,32)+12,99),'binding')
        def wrong_bin(p,i=role):p.put(p.rec('role',i,32)+8,99);p.put(p.rec('sblob',i,32)+8,99)
        add(f'source-bin-{role}',wrong_bin,'binding')
    add('missing-face-role',lambda p:(p.put(p.sec('role')['table']+8,5*32),p.put(p.sec('role')['table']+12,5)),'role')
    add('duplicate-face-role',lambda p:p.put(p.rec('role',2,32)+4,1),'duplicate')
    groups={};wanted={}
    for name,why,p,room,on in cases:
        path=out/(name+'.re4nmr');path.write_bytes(p.b);groups.setdefault((room,on),[]).append(str(path));wanted[str(path)]=(name,why)
    rows=[]
    for (room,on),paths in groups.items():
        result=subprocess.run([str(out/f'validator-{on}1'),f'{room:x}']+paths,check=True,capture_output=True,text=True)
        for line in result.stdout.splitlines():
            path,why,detail=line.rsplit(' ',2);name,expected=wanted[path];rows.append(dict(case=name,expected=expected,got=why,detail=int(detail),ok=why==expected))
    alone=subprocess.check_output([str(out/'validator-10'),'11c',str(fixture)],text=True).strip().rsplit(' ',2)
    rows.append(dict(case='CH22-without-CH23',expected='none',got=alone[1],detail=int(alone[2]),ok=alone[1]=='none'))
    report=dict(fixture=str(fixture),fixture_sha256=hashlib.sha256(good).hexdigest(),scope='Actual loader structure, source identity pins and guarded coverage only. No texture/visual/lifetime acceptance.',checker_sha256=hashlib.sha256((GAME/'coarse_actor_registry_pack_check.inc').read_bytes()).hexdigest(),tests=rows,failures=sum(not r['ok'] for r in rows),skipped_inapplicable=sorted(skip),absent=absent)
    (out/'results.json').write_text(json.dumps(report,indent=2))
    for row in rows:
        if not row['ok']:print('FAIL',row)
    print(len(rows),'actual loader checks;',report['failures'],'failures')
    raise SystemExit(bool(report['failures']))

if __name__=='__main__':main()