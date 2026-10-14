#!/usr/bin/env python3
"""D56 scalar observer: exact production predicate/observer, no owner admission."""
from pathlib import Path
import contextlib, hashlib, json, os, subprocess, tempfile

ROOT = Path(__file__).resolve().parents[3]
INC = ROOT / 'port/dreamcast/game/platform/include/source_world_r11f.inc'

def scoped(text, marker):
    start = text.index(marker)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]

PRELUDE = r'''
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
#include <sys/mman.h>
#include <unistd.h>
struct cModel {};
namespace r11fp { constexpr unsigned room=0x11f,works=251; }
struct Global {
    unsigned Frame_cnt=77,Rno0=3,stage_no=1,room_no=0x1f;
    unsigned System_flg=0x400,Status_flg[4]{};
} global,*pG=&global;
#define G_ROOM_ID ((pG->stage_no<<8)|pG->room_no)
int re4dc_coarse_image,re4dc_pace_skipping,movie,ss;
unsigned movie_reads,ss_reads,checks,cases;
std::vector<std::string> lines;
extern "C" int re4dc_ui_movie_texture(){++movie_reads;return movie;}
extern "C" int re4dc_ss_ui_order(){++ss_reads;return ss;}
extern "C" void re4dc_log(const char* fmt,...){
    char b[768];va_list ap;va_start(ap,fmt);
    const int n=vsnprintf(b,sizeof(b),fmt,ap);va_end(ap);
    assert(n>=0 && unsigned(n)<sizeof(b));lines.emplace_back(b);
}
void check(bool okay){++checks;assert(okay);}
'''

BODY = r'''
void configure(unsigned bits) {
    global=Global{};pG=(bits&1)?nullptr:&global;
    global.Rno0=(bits&2)?2:3;
    global.room_no=(bits&4)?0x1c:0x1f;
    global.System_flg=((bits&8)?0:0x400)|((bits&16)?0x100000:0)|0x80000040u;
    global.Status_flg[2]=(bits&32)?0x04000000:0;
    global.Status_flg[1]=(bits&64)?0x100:0;
    re4dc_coarse_image=(bits&128)?-7:0;
    re4dc_pace_skipping=(bits&256)?2:0;
    movie=(bits&512)?-1:0;ss=(bits&1024)?3:0;
}
int main() {
    const long page=sysconf(_SC_PAGESIZE);
    void* poison=mmap(nullptr,page,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    assert(poison!=MAP_FAILED);
    r11fFrame.source=81;r11fFrame.room=4;r11fFrame.package=5;
    r11fFrame.prim=0x112233;r11fFrame.count=251;r11fFrame.planned=true;
    for(auto& entry:r11fFrame.entries)entry.model=static_cast<cModel*>(poison);
    for(auto& pointer:r11fFrame.group)pointer=static_cast<cModel*>(poison);
    for(unsigned bits=0;bits<2048;++bits) {
        configure(bits);
        const Global before=global;Global* const ptr=pG;
        const auto owner=r11fFrame;
        const unsigned expected=(bits&1)?(bits&(1|0x780)):bits;
        check(r11fContext()==(expected==0));
#if RE4DC_PS2_WORLD_R11F_CONTEXT_DIAG
        const auto s=r11fContextSnapshot(123);
        check(r11fContextRefusal(s)==expected);
        check((r11fContextRefusal(s)==0)==r11fContext());
        check(s.present==unsigned(pG!=nullptr));
        if(pG) {
            check(s.source==global.Frame_cnt && s.rno==global.Rno0);
            check(s.system==global.System_flg && s.status1==global.Status_flg[1] && s.status2==global.Status_flg[2]);
        } else check(s.room==~0u && s.rno==~0u && s.source==0);
        r11fContextDiagnosticState={};lines.clear();
        r11fContextDiagnostic(123);
        check(lines.size()==1 && lines[0].find("R11FOWNER_CONTEXT n=1 f=123 ")==0);
        char mask[32];snprintf(mask,sizeof(mask),"mask=%03x ",expected);
        check(lines[0].find(mask)!=std::string::npos);
        const auto reads=movie_reads+ss_reads;
        r11fContextDiagnostic(123);
        check(lines.size()==1 && movie_reads+ss_reads==reads);
#endif
        check(pG==ptr && std::memcmp(&global,&before,sizeof(global))==0);
        check(std::memcmp(&r11fFrame,&owner,sizeof(owner))==0);
        check(re4dc_coarse_image==((bits&128)?-7:0));
        check(re4dc_pace_skipping==((bits&256)?2:0));
        check(movie==((bits&512)?-1:0) && ss==((bits&1024)?3:0));
    }
    ++cases;
#if RE4DC_PS2_WORLD_R11F_CONTEXT_DIAG
    configure(4);r11fFrame={};r11fContextDiagnosticState={};lines.clear();
    for(unsigned n=0;n<4;++n){r11fContextDiagnostic(n);r11fContextDiagnostic(n);}
    check(lines.size()==4);
    for(unsigned n=4;n<600;++n)r11fContextDiagnostic(n);
    check(lines.size()==4); // other-room periodic calls remain quiet
    configure(0);r11fContextDiagnostic(600);check(lines.size()==5);
    for(unsigned n=601;n<720;++n)r11fContextDiagnostic(n);
    check(lines.size()==5);r11fContextDiagnostic(720);check(lines.size()==6);
    re4dc_pace_skipping=1;r11fContextDiagnostic(721);check(lines.size()==7);
    r11fFrame.native=722;r11fFrame.withheld=true;r11fContextDiagnostic(722);
    check(lines.size()==8 && lines.back().find("same=1 withheld=1 failed=0")!=std::string::npos);
    r11fFrame.native=723;r11fFrame.failed=true;r11fContextDiagnostic(723);check(lines.size()==9);
    r11fFrame.native=724;r11fFrame.withheld=false;r11fContextDiagnostic(724);check(lines.size()==10);
    r11fFrame.native=725;r11fFrame.failed=false;r11fContextDiagnostic(725);check(lines.size()==11);
    for(unsigned n=726;n<2000;++n){re4dc_coarse_image=n&1;r11fContextDiagnostic(n);}
    check(lines.size()==96 && r11fContextDiagnosticState.lines==96);
    const auto reads=movie_reads+ss_reads;
    for(unsigned n=2000;n<3000;++n)r11fContextDiagnostic(n);
    check(lines.size()==96 && movie_reads+ss_reads==reads);
    ++cases;
    // Unsigned frame wrap preserves a 120-frame periodic interval.
    configure(0);r11fFrame={};r11fContextDiagnosticState={};lines.clear();
    for(unsigned n=0;n<4;++n)r11fContextDiagnostic(~0u-60+n);
    check(lines.size()==4);
    r11fContextDiagnostic(61);check(lines.size()==4);
    r11fContextDiagnostic(62);check(lines.size()==5);
    ++cases;
    // Null global is sampled safely; the observer never follows owner pointers.
    pG=nullptr;r11fContextDiagnosticState={};lines.clear();
    r11fContextDiagnostic(0);check(lines.size()==1 && lines[0].find("present=0")!=std::string::npos);
    ++cases;
#else
    check(lines.empty());
#endif
    assert(munmap(poison,page)==0);
    printf("R11F_CONTEXT_TEST diag=%d combinations=2048 cases=%u checks=%u PASS\n",RE4DC_PS2_WORLD_R11F_CONTEXT_DIAG,cases,checks);
}
'''

def run(out):
    source=INC.read_text()
    diagnostic=source[source.index('// D56 observes only scalar context.'):source.index('bool r11fKnownPointer')]
    entry='extern "C" void re4dc_r11f_prepare(unsigned native) {\n'
    call='#if RE4DC_PS2_WORLD_R11F_CONTEXT_DIAG\n    r11fContextDiagnostic(native);\n#endif\n'
    assert source.count(call)==1 and source[source.index(entry)+len(entry):].startswith(call+'    auto& f=r11fFrame;')
    structures=scoped(source,'struct R11fEntry')+';\n'+scoped(source,'struct R11fFrame')+' r11fFrame;\n'
    fixture=PRELUDE+structures+scoped(source,'bool r11fContext()')+'\n'+diagnostic+BODY
    (out/'fixture.cpp').write_text(fixture)
    report={'status':'running','arms':[],'make_policy':[],'limits':['Host scalar predicate/observer only. Existing actual owner regression is run separately. No target identity, timing or runtime acceptance.']}
    try:
        for enabled in (0,1):
            arm=out/f'diag-{enabled}';arm.mkdir()
            argv=[os.environ.get('CXX','g++'),'-std=c++17','-O1','-g','-Wall','-Wextra','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-fno-pie','-no-pie',f'-DRE4DC_PS2_WORLD_R11F_CONTEXT_DIAG={enabled}',str(out/'fixture.cpp'),'-o',str(arm/'test')]
            (arm/'compiler-command.json').write_text(json.dumps(argv,indent=2)+'\n')
            cp=subprocess.run(argv,capture_output=True,text=True)
            (arm/'compiler-stdout.txt').write_text(cp.stdout);(arm/'compiler-stderr.txt').write_text(cp.stderr)
            rec={'diag':enabled,'compile_rc':cp.returncode};report['arms'].append(rec);cp.check_returncode()
            cp=subprocess.run([str(arm/'test')],capture_output=True,text=True)
            (arm/'run-stdout.txt').write_text(cp.stdout);(arm/'run-stderr.txt').write_text(cp.stderr)
            rec.update(run_rc=cp.returncode,stdout=cp.stdout,stderr=cp.stderr);print(cp.stdout,end='');cp.check_returncode()
        make=(ROOT/'port/dreamcast/game/game30.mk').read_text()
        block=make[make.index('# Scalar-only observation of the existing r11f owner context;'):make.index('# ITEM_UI_ORDER=1:')]
        mk=out/'policy.mk';mk.write_text('OBJDIR := obj\n'+block+'\n$(OBJDIR)/src/game/trans.o $(OBJDIR)/other.o:\n\t@echo target=$@ flags=$(GAME_CPPFLAGS)\n')
        for name,args,okay in [('default',[],True),('off',['PS2_WORLD_R11F_CONTEXT_DIAG=0','PS2_WORLD_R11F_OWNER=0'],True),('on',['PS2_WORLD_R11F_CONTEXT_DIAG=1','PS2_WORLD_R11F_OWNER=1'],True),('invalid',['PS2_WORLD_R11F_CONTEXT_DIAG=2','PS2_WORLD_R11F_OWNER=1'],False),('requires_owner',['PS2_WORLD_R11F_CONTEXT_DIAG=1','PS2_WORLD_R11F_OWNER=0'],False)]:
            argv=['make','--no-print-directory','-f',str(mk),*args,'obj/src/game/trans.o','obj/other.o']
            cp=subprocess.run(argv,capture_output=True,text=True,cwd=out);report['make_policy'].append(dict(name=name,argv=argv,rc=cp.returncode,stdout=cp.stdout,stderr=cp.stderr))
            assert (cp.returncode==0)==okay,(name,cp.stdout,cp.stderr)
            if okay:
                assert cp.stdout.count('-DRE4DC_PS2_WORLD_R11F_CONTEXT_DIAG=1')==(1 if name=='on' else 0)
                assert 'other.o flags=\n' in cp.stdout
        inputs=[INC,ROOT/'port/dreamcast/game/game30.mk',Path(__file__)]
        (out/'source-pins.json').write_text(json.dumps({str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},indent=2)+'\n')
        for p in inputs:
            q=out/'source'/p.relative_to(ROOT);q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes())
        report['status']='passed'
    finally:
        (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('D56 make policy PASS 5 cases; source/observer PASS')

if __name__=='__main__':
    saved=os.environ.get('RE4DC_TEST_ARTIFACT_DIR')
    if saved:Path(saved).mkdir(parents=True,exist_ok=False)
    with contextlib.nullcontext(saved) if saved else tempfile.TemporaryDirectory(prefix='re4-r11f-context-') as path:
        run(Path(path))
