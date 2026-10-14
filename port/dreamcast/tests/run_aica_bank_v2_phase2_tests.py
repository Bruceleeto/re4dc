#!/usr/bin/env python3
"""Bounded AIC2 host/standalone SH4 checks. No game link, runtime or asset staging."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


def pin(path):
    return dict(path=str(path), bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures',required=True,type=Path)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--sh4-cxx',default='/opt/toolchains/dc/sh-elf/bin/sh-elf-g++')
    parser.add_argument('--quick',action='store_true',help='development only: skip extended schedules, sanitizer and SH4 checks')
    args=parser.parse_args()
    if args.output.exists():parser.error('output must be a fresh directory')
    args.output.mkdir(parents=True)
    root=Path(__file__).resolve().parents[1];platform=root/'game/platform'
    sources=[platform/('aica_bank_v2_'+n+'.cpp') for n in ('host','stream','sha256')]
    tests=[root/'tests/aica_bank_v2_host_test.cpp',root/'tests/aica_bank_v2_stream_test.cpp']
    results=dict(status='DEVELOPMENT_ONLY' if args.quick else 'HOST_ONLY_STANDALONE_SH4',commands=[],fixtures=[pin(p) for p in sorted(args.fixtures.iterdir()) if p.is_file()],source_pins=[pin(p) for p in sources+tests])
    env=dict(os.environ,AIC2_FIXTURE_DIR=str(args.fixtures),PYTHONDONTWRITEBYTECODE='1')
    def run(name,command,environment=env):
        result=subprocess.run(list(map(str,command)),capture_output=True,text=True,env=environment)
        (args.output/(name+'.stdout')).write_text(result.stdout);(args.output/(name+'.stderr')).write_text(result.stderr)
        results['commands'].append(dict(name=name,argv=list(map(str,command)),returncode=result.returncode))
        (args.output/'progress.json').write_text(json.dumps(results,indent=2)+'\n')
        if result.returncode:raise RuntimeError(name+' failed: '+result.stderr[-6000:])
        print(name+' passed',flush=True)
        return result.stdout
    spec=importlib.util.spec_from_file_location('phase2_format',root/'tools/aica_banks_v2.py');fmt=importlib.util.module_from_spec(spec);sys.modules[spec.name]=fmt;spec.loader.exec_module(fmt)
    rows=json.loads((args.fixtures/'banks.json').read_text())['banks']
    if len(rows)!=30:raise RuntimeError('all30 fixtures required')
    profiles=[]
    for row in rows:
        ident=fmt.Identity(row['name'],row['source_class'],row['profile'],row['gc_bytes'],bytes.fromhex(row['mram_sha256']),bytes.fromhex(row['table_sha256']),bytes.fromhex(row['logical_sha256']),tuple(fmt.Sample(*s) for s in row['samples']))
        bank=fmt.Bank(ident,(args.fixtures/row['logical_file']).read_bytes(),(args.fixtures/row['mram_file']).read_bytes(),(args.fixtures/row['table_file']).read_bytes(),tuple(row['rates']))
        profiles.append(fmt.profile_record(bank,row['cap_hz']))
        parsed=fmt.parse((args.fixtures/row['aic2_file']).read_bytes(),ident,row['block'])
        assert len(fmt.folded_sample_digest((m.encoded_bytes,m.sha) for m in parsed.maps))==32
    profile=args.output/'profiles.bin';profile.write_bytes(b''.join(profiles));results['profiles']=pin(profile)
    run('python-tests',[sys.executable,'-B',root/'tests/test_aica_banks_v2.py'])
    cxx=shutil.which('g++');flags=['-std=c++17','-Wall','-Wextra','-Werror','-pedantic','-DRE4DC_AICA_BANK_V2=1']
    summaries={}
    for index,test in enumerate(tests):
        name='metadata' if index==0 else 'stream';exe=args.output/(name+'-tests')
        run(name+'-compile',[cxx,*flags,'-O2',test,*sources,'-o',exe])
        command=[exe] if index==0 else [exe,args.fixtures,profile]+(['quick'] if args.quick else [])
        summaries[name]=json.loads(run(name+'-tests',command))
        if not args.quick:
            san=args.output/(name+'-sanitized');run(name+'-sanitizer-compile',[cxx,*flags,'-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',test,*sources,'-o',san])
            se=dict(env,ASAN_OPTIONS='detect_leaks=1:halt_on_error=1',UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1')
            got=json.loads(run(name+'-sanitizer-tests',[san,*command[1:]],se))
            if got!=summaries[name]:raise RuntimeError(name+' normal/sanitized results differ')
    if not args.quick:
        # Inaccessible proofs must fail to compile, not merely reject a boolean
        # after an API accidentally reintroduces a caller-trusted verification.
        forbidden={
            'verify-bool':'Core c; Token t{}; c.verify(1,t,true);',
            'forge-receipt':'VerificationReceipt r; r.nonce_=1;',
            'issue-ticket':'Core c; Token t{}; CopyTicket x; c.copy_begin(t,0,0,4,true,x);',
            'forge-ticket':'CopyTicket x; x.base_=0x30000;',
        }
        for name,body in forbidden.items():
            path=args.output/(name+'.cpp');path.write_text('#include "aica_bank_v2_stream.h"\nusing namespace re4dc_aic2;\nvoid attack(){'+body+'}\n')
            command=[cxx,*flags,'-I'+str(platform),'-fsyntax-only',str(path)]
            result=subprocess.run(command,capture_output=True,text=True)
            (args.output/(name+'.stderr')).write_text(result.stderr)
            if result.returncode==0 or not any(s in result.stderr for s in ('private','no matching function')):raise RuntimeError('opaque API negative control failed: '+name)
            results['commands'].append(dict(name=name,argv=command,returncode=result.returncode,expected_failure=True))
        for source in sources:
            obj=args.output/(source.stem+'-off.o');run(source.stem+'-off-compile',[cxx,'-std=c++17','-c',source,'-o',obj])
            if run(source.stem+'-off-nm',['nm','--defined-only',obj]).strip():raise RuntimeError('default-off symbols')
        sh4=args.sh4_cxx
        if not Path(sh4).is_file():raise RuntimeError('standalone SH4 compiler required')
        target=['-std=c++17','-m4-single-only','-ml','-ffreestanding','-fno-exceptions','-fno-rtti','-DRE4DC_AICA_BANK_V2=1','-Wall','-Wextra','-Werror','-fstack-usage','-I'+str(platform)]
        for source in sources:
            obj=args.output/(source.stem+'-sh4.o');run(source.stem+'-sh4-compile',[sh4,*target,'-O2','-c',source,'-o',obj])
            run(source.stem+'-sh4-size',[sh4.replace('g++','size'),obj]);run(source.stem+'-sh4-undefined',[sh4.replace('g++','nm'),'-u',obj])
        probe=args.output/'footprint.cpp';probe.write_text('#include "aica_bank_v2_stream.h"\nusing namespace re4dc_aic2;\nunsigned char aic2_core[sizeof(Core)];\nunsigned char aic2_receiver[sizeof(Receiver)];\nunsigned char aic2_engine[sizeof(Engine)];\nunsigned char aic2_sha[sizeof(Sha256)];\n')
        run('sh4-footprint-compile',[sh4,*target,'-c',probe,'-o',args.output/'footprint.o'])
        syms=run('sh4-footprint-nm',[sh4.replace('g++','nm'),'-S','--defined-only',args.output/'footprint.o'])
        sizes={line.split()[-1].lstrip('_'):int(line.split()[1],16) for line in syms.splitlines()}
        if sizes['aic2_receiver']>768 or sizes['aic2_core']>19384+2048 or sizes['aic2_core']+sizes['aic2_engine']>56*1024:raise RuntimeError('approved footprint budget exceeded')
        results['sh4_sizes']=sizes
        run('host-version',[cxx,'--version']);run('sh4-version',[sh4,'--version'])
    results.update(summaries=summaries,hardware_inactivity_qualified=False,runtime_loader_integrated=False,game_link_performed=False)
    (args.output/'results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(dict(output=str(args.output),summaries=summaries)))

if __name__=='__main__':main()
