#!/usr/bin/env python3
"""Run the real bounded collector and observer implementation with const source fixtures.
Target compilation separately verifies real source layouts; no renderer or gameplay is run.
"""
from pathlib import Path
import subprocess,tempfile
ROOT=Path(__file__).resolve().parents[1]
GAME=ROOT/'game'
HEADER=GAME/'platform/include'
CPP=r"""
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <string>
#include <cstring>
#include <new>
#define RE4DC_ACTOR_TRANSACTION_DIAG 1
#include "actor_visibility_diag.h"
class cModel { public:
    unsigned vptr=0x12345678,id=0x10,type=2,kindid=1,ot_type=7,nParts=34,be_flag=0x20;
    unsigned alpha_omit=255,z_mode=0,CullMode=0,Shader_type=0,r_no_0=1,r_no_1=2,r_no_2=3,r_no_3=4,serial=9;
    float invisible_factor=.75f,invisible_factor2=.25f;
};
class cModelInfo { public:
    void* pData=(void*)0x2000;void* tpl_addr=(void*)0x3000;
    unsigned be_flag=0x20,colorWord=0x11223344;float invisible_factor=.5f;
};
struct Re4dcModelPart {const void* model;const void* info;const void* part;unsigned alpha_state,blend,depth_mode,material_flags;};
struct cEm: cModel {short hp=27,hp_max=80;unsigned set=2,emset_no=7,status=9;float plDist2=25;
    void (*pScenario)(cEm*)=nullptr;};
struct Em10Work {unsigned flags=0x123;int Timer=1,Timer2=2,Timer3=3;float Compress_y=.7f;unsigned Reset_enable=1;};
struct Manager {unsigned nArray=4,reads=0;const cEm* ptr=nullptr;
    const cEm* workAt(unsigned i){++reads;return i==2?ptr:nullptr;}
    // An observer accidentally using the allocating API will not compile.
    bool prepareWork(unsigned,unsigned)=delete;
} EmMgr;
struct Global {unsigned Frame_cnt=777;} global;Global* pG=&global;
re4dc_visdiag::Stream test_stream{10,2,0,0,0,1,0,0};
std::string output;
extern "C" void re4dc_log(const char* fmt,...){char b[2048];va_list v;va_start(v,fmt);const int n=vsnprintf(b,sizeof(b),fmt,v);va_end(v);assert(n<256);output+=b;}
extern "C" void re4dc_actor_vis_stream(re4dc_visdiag::Stream* out){*out=test_stream;}
#include "actor_visibility_diag_impl.inc"
using namespace re4dc_visdiag;
int main(){
    Collector c{};c.begin(7);
    for(unsigned i=0;i<kBefore+9;++i){Order e{};e.event=ListRequest;c.event(e);}
    assert(c.nbefore==kBefore && c.before_lost==9);
    assert(c.decline(0x1000,1)==0);assert(c.decline(0x1000,1)==0 && c.lives[0].frames==1);
    assert(c.decline(0x1000,2)==1); // Same address, new serial is a different lifetime.
    assert(c.decline(0x2000,1)==2);assert(c.decline(0x3000,1)==3);
    assert(c.decline(0x4000,1)==-1 && c.model_lost==1);
    for(unsigned i=0;i<kAfter+11;++i){Order e{};e.event=Enqueue;e.node=0x400+i;e.stream.epoch=3;c.event(e);}
    assert(c.nafter==kAfter && c.after_lost==11);
    assert(c.queued(0x400,3) && !c.queued(0x400,4));
    for(unsigned f=8;f<7+kFrames;++f){c.begin(f);assert(c.decline(0x1000,1)==0);}
    assert(c.lives[0].frames==kFrames);c.begin(99);assert(c.decline(0x1000,1)==-2 && c.frame_lost==1);
    assert(!c.active[0].model);
    cModel m;const cModel before=m;const ModelState state=model_state(m);
    assert(state.factor[0]==bits(.75f) && state.factor[1]==bits(.25f) && state.routine[3]==4);
    assert(!memcmp(&before,&m,sizeof(m)));
    unsigned slot,trunc;assert(existing_enemy(EmMgr,&m,slot,trunc)==nullptr && slot==~0u && !trunc && EmMgr.reads==4);
    EmMgr.nArray=1025;EmMgr.reads=0;existing_enemy(EmMgr,&m,slot,trunc);assert(trunc && EmMgr.reads==1024);EmMgr.nArray=4;
    // Run the actual decline implementation on existing enemy storage; source
    // model/info/work bytes must be unchanged even when a slot is found.
    alignas(cEm) unsigned char backing[0x3e0+sizeof(Em10Work)]{};
    cEm* em=new(backing)cEm;EmMgr.ptr=em;
    new(backing+0x3e0)Em10Work;
    unsigned char saved[sizeof(backing)];memcpy(saved,backing,sizeof(saved));
    cModelInfo info[6];cModelInfo info_saved[6];memcpy(info_saved,info,sizeof(info));
    const cModelInfo* roles[6]={info,info+1,info+2,info+3,info+4,info+5};
    re4dc_actor_vis_decline(em,1,roles,6);
    assert(avd_detail::avd.active[0].count==5);assert(output.find("roles_lost=1")!=std::string::npos);
    assert(output.find("hp=27 hpmax=80")!=std::string::npos);
    // Actual p.alpha_state is deliberately unrelated to factor arithmetic.
    Re4dcModelPart p{em,info,(void*)0x4000,0x123456a7,3,2,4};const Re4dcModelPart ps=p;
    re4dc_actor_vis_source(em,info,&p);
    assert(output.find("actual=123456a7")!=std::string::npos);
    re4dc_actor_vis_event(Enqueue,(void*)0x5000,&p,0);
    re4dc_actor_vis_source_end();
    re4dc_actor_vis_event(Drain,(void*)0x5000,nullptr,0);
    const auto& e=avd_detail::avd.after[avd_detail::avd.nafter-1];
    assert(e.known && e.serial==em->serial && e.alpha==p.alpha_state);
    p.alpha_state=0xdeadbeef;re4dc_actor_vis_event(DrainModel,(void*)0x5000,&p,0);
    assert(avd_detail::avd.after[avd_detail::avd.nafter-1].alpha==0xdeadbeef);
    const void* part_save=p.part;p.part=(void*)0x9999;
    re4dc_actor_vis_event(DrainModel,(void*)0x5000,&p,0);
    assert(!avd_detail::avd.after[avd_detail::avd.nafter-1].known);
    assert(avd_detail::avd.after[avd_detail::avd.nafter-1].detail==0x80000000u);
    p.part=part_save;
    // Reused node in a fresh epoch must not inherit old identity.
    ++test_stream.epoch;re4dc_actor_vis_event(Drain,(void*)0x5000,nullptr,0);
    assert(!avd_detail::avd.after[avd_detail::avd.nafter-1].known);
    p.alpha_state=0x765432a7;re4dc_actor_vis_source(em,info,&p);
    assert(avd_detail::avd.active[0].roles[0].parts==2 && avd_detail::avd.active[0].roles[0].changes==1);
    p.info=info+5;re4dc_actor_vis_source(em,info+5,&p);assert(avd_detail::avd.active[0].unknown_infos==1);
    assert(!memcmp(saved,backing,sizeof(saved)) && !memcmp(info_saved,info,sizeof(info)));
    p=ps;re4dc_actor_vis_source(em,info,&p);assert(!memcmp(&ps,&p,sizeof(p)));
    re4dc_actor_vis_flush(42);assert(output.find("reason=42")!=std::string::npos);
    puts("PASS actual collector, source snapshots, alpha pass-through, identity/epoch joins, frame/role/order bounds, no source writes");
}
"""
def main():
    bridge=(GAME/'model_bridge.cpp').read_text()
    assert bridge.index('p.alpha_state=re4dc_gx_model_alpha();') < bridge.index('re4dc_actor_vis_source(m,info,&p);') < bridge.index('re4dc_model_submit(&p);') < bridge.index('re4dc_actor_vis_source_end();')
    with tempfile.TemporaryDirectory(prefix='actor-visdiag-') as d:
        p=Path(d);(p/'test.cpp').write_text(CPP);(p/'em10.h').write_text('// Source types supplied by const host fixture.\n')
        exe=p/'test'
        subprocess.run(['c++','-std=c++17','-O2','-Wall','-Wextra','-Werror','-I'+str(p),'-I'+str(HEADER),'-I'+str(GAME),str(p/'test.cpp'),'-o',str(exe)],check=True)
        subprocess.run([str(exe)],check=True)
if __name__=='__main__':main()
