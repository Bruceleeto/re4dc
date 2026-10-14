#!/usr/bin/env python3
"""Fail-closed generator checks with a caller-provided private Luis structural fixture.

Usage: test_luis_generator.py <fixture spec.json> <fresh private output directory>
Fixture output is never staged here. Native-look material fidelity is separate.
"""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys

HERE=Path(__file__).resolve().parent

def main():
    if len(sys.argv)!=3:raise SystemExit(__doc__)
    original=Path(sys.argv[1]);out=Path(sys.argv[2]).resolve();out.mkdir(parents=True,exist_ok=False)
    base=json.loads(original.read_text());assert len(base['descriptors'])==1
    tree=HERE.parents[3]
    cases=['no-opt-in','wrong-room','wrong-model','wrong-name','source-rest','source-identity','sparse-parent','sparse-attach','sparse-translation','source-bin','source-tpl','coverage-manifest','runtime-header','hair-uv','hair-stream','hair-size','opaque-payload','missing-mask','wrong-mask-role']
    rows=[]
    def read(p):return json.loads(p.read_text())
    def write(p,value):p.write_text(json.dumps(value))
    sha=lambda b:hashlib.sha256(b).hexdigest()
    for name in cases:
        case=out/name;case.mkdir();cast=case/'cast';shutil.copytree(base['cast_dir'],cast)
        spec=json.loads(json.dumps(base));spec['cast_dir']=str(cast);d=spec['descriptors'][0]
        mask=case/'mask';shutil.copytree(d['mask_runs']['3'],mask);d['mask_runs']['3']=str(mask)
        cov=case/'coverage.json';shutil.copy2(d['source_coverage_manifest'],cov);d['source_coverage_manifest']=str(cov)
        srcp=cast/'luis-actor/source.json';bp=cast/'luis-actor/source-bindings.json';mp=mask/'mask-runs.json'
        src,binds,mj=read(srcp),read(bp),read(mp);extra=['--ch22-luis-coverage'];room='11c'
        if name=='no-opt-in':extra=[];expected='explicit pinned CH22'
        elif name=='wrong-room':room='11d';expected='requires --package-room 11c'
        elif name=='wrong-model':d['model_id']='0x05';expected='differ from source.json'
        elif name=='wrong-name':d['name']='other';expected='not in the ps2-overlay catalog'
        elif name=='source-rest':src['bones'][5]['rest'][0][3]+=1;expected='source skeleton and coverage'
        elif name=='source-identity':src['infos'][2]['source_tpl_arc']=5;expected='source skeleton and coverage'
        elif name=='sparse-parent':binds[1]['part_bindings'][1]['parent']+=1;expected='sparse part table'
        elif name=='sparse-attach':binds[1]['part_bindings'][1]['attach']+=1;expected='sparse part table'
        elif name=='sparse-translation':binds[4]['part_bindings'][0]['translation'][0]+=1;expected='sparse part table'
        elif name=='source-bin':binds[2]['bin']=6;expected='six source BIN/TPL identities'
        elif name=='source-tpl':binds[2]['tpl']=5;expected='six source BIN/TPL identities'
        elif name=='coverage-manifest':cov.write_bytes(cov.read_bytes()+b' ');expected='coverage manifest differs'
        elif name=='runtime-header':
            hp=cast/'luis-actor/ps2-v1/castmodel_runtime.h';hp.write_bytes(hp.read_bytes()+b'\n')
            catp=cast/'ps2-overlay/integration-bundle/catalog.json';cat=read(catp);cat[0]['levels']['conservative']['header_sha256']=sha(hp.read_bytes());write(catp,cat)
            rp=cast/'luis-actor/ps2-v1/revision-manifest.json';revision=read(rp);revision['levels']['conservative']['header_sha256']=sha(hp.read_bytes());write(rp,revision)
            expected='native header differs'
        elif name=='hair-uv':
            p=mask/'hair.uv';b=bytearray(p.read_bytes());b[0]^=1;p.write_bytes(b);expected='hair stream/UV/texture size'
        elif name=='hair-stream':
            p=mask/'hair.blob';b=bytearray(p.read_bytes());b[-1]^=1;p.write_bytes(b);mj['runs']['hair']['sha256']=sha(b);expected='hair stream/UV/texture size'
        elif name=='hair-size':mj['texture']['width']=256;expected='hair stream/UV/texture size'
        elif name=='opaque-payload':
            b=b'x';(mask/'opaque.blob').write_bytes(b);mj['runs']['opaque']['sha256']=sha(b);expected='opaque payload must be absent'
        elif name=='missing-mask':d['mask_runs']={};expected='complete mask-only source hair'
        elif name=='wrong-mask-role':d['mask_runs']={'0':str(mask)};expected='another header / section'
        write(srcp,src);write(bp,binds);write(mp,mj);sp=case/'spec.json';write(sp,spec)
        cmd=[sys.executable,'-B',str(HERE/'model_registry.py'),str(sp),str(case/'generated'),'--tree',str(tree),'--package-room',room,'--pack-bones','96','--wide-identity','--source-normal-length']+extra
        result=subprocess.run(cmd,capture_output=True,text=True);combined=result.stdout+result.stderr
        ok=result.returncode!=0 and expected in combined and not (case/'generated').exists()
        rows.append(dict(case=name,ok=ok,exit_code=result.returncode,expected=expected,output=combined[-1000:]));(case/'run.log').write_text(combined)
    report=dict(tests=rows,failures=sum(not r['ok'] for r in rows));(out/'results.json').write_text(json.dumps(report,indent=2))
    for row in rows:
        if not row['ok']:print('FAIL',row)
    print(len(rows),'fail-closed generator cases;',report['failures'],'failures');raise SystemExit(bool(report['failures']))

if __name__=='__main__':main()