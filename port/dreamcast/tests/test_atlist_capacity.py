#!/usr/bin/env python3
"""Exercise production alive/candidate helpers and dirty-field wrappers at both capacities."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
PRELUDE = r'''
#include <cassert>
#include <cstdint>
#include <cstddef>
#include <cstdio>
#include <cstring>
#include <vector>
#include <algorithm>
#include <limits>
using u32 = uintptr_t;
using u16 = uint16_t;
using u8 = uint8_t;
using f32 = float;
extern "C" void re4dc_log(const char*, ...) {}
static unsigned builds, collections;
'''
LAYOUT = r'''
struct cAtariInfo {
    u8 prefix[0x10];
    AtRadius m_radius2;
    u8 middle[6];
    AtFlag16 m_flag;
};
static_assert(offsetof(cAtariInfo,m_radius2)==0x10,"radius wrapper owner");
static_assert(offsetof(cAtariInfo,m_flag)==0x1a,"flag wrapper owner");
struct cEm { cEm* pNext; cAtariInfo atari; };
'''
CASES = r'''
static cEm pool[704]{};
static void link(std::vector<cEm*>& list) {
    for (unsigned i=0;i<list.size();++i)
        list[i]->pNext=i+1<list.size()?list[i+1]:nullptr;
}
static std::vector<cEm*> reference(cEm* head) {
    std::vector<cEm*> out;
    for (;head;head=head->pNext)
        if ((head->atari.m_flag&0x200) && head->atari.m_radius2!=0)
            out.push_back(head);
    return out;
}
static void verify(AtList& list,AtCand& cand,std::vector<cEm*>& nodes,u32 gen) {
    cEm* head=nodes.empty()?nullptr:nodes[0];
    cEm* result[ATCHK_MAX];
    int n=atchkCandidates(&cand,&list,head,gen,result);
    auto expected=reference(head);
    if(expected.size()>ATCHK_MAX)assert(n==-1);
    else {
        assert(n==int(expected.size()));
        assert(std::equal(expected.begin(),expected.end(),result));
    }
    // Same ordered array is consumed by ObjHitCheck; every object must remain.
    if(list.n>=0) {
        assert(list.n==int(nodes.size()));
        assert(std::equal(nodes.begin(),nodes.end(),list.v));
    }
}
static void fill(std::vector<cEm*>& nodes,unsigned n,unsigned stride) {
    nodes.clear();
    for(unsigned i=0;i<n;++i) {
        pool[i].atari.m_flag=i%stride==0?0x200:0;
        pool[i].atari.m_radius2=1.0f;
        nodes.push_back(&pool[i]);
    }
    link(nodes);
}
int main() {
    std::vector<cEm*> nodes;
    AtList list={0,0,-1};AtCand cand={0,0,0,0,-1};u32 gen=11;
    fill(nodes,470,7);verify(list,cand,nodes,gen);
    assert(list.n==(RE4DC_ATLIST_512?470:-1));
    unsigned b=builds,c=collections;
    for(unsigned i=0;i<33;++i)verify(list,cand,nodes,gen);
    assert(builds==b);
#if RE4DC_ATLIST_512 && RE4DC_ATCHK_CACHE == 1
    assert(collections==c); // actual positive cache, not merely a larger fallback
#else
    assert(collections==c+33);
#endif
    // Actual field wrappers note flag/radius changes, including beyond the old limit.
    pool[400].atari.m_flag=0x200;pool[7].atari.m_radius2=0;
    verify(list,cand,nodes,gen);
    pool[7].atari.m_radius2=2;pool[400].atari.m_flag=0;
    verify(list,cand,nodes,gen);
    // Stable-head reorder, retirement, and same-address reuse each change generation.
    std::swap(nodes[2],nodes[400]);link(nodes);verify(list,cand,nodes,++gen);
    auto retired=nodes[30];nodes.erase(nodes.begin()+30);link(nodes);verify(list,cand,nodes,++gen);
    retired->atari.m_flag=0x200;retired->atari.m_radius2=3;
    nodes.insert(nodes.begin()+1,retired);link(nodes);verify(list,cand,nodes,++gen);
    // Head replacement independently invalidates even if generation did not change.
    std::swap(nodes[0],nodes[1]);link(nodes);verify(list,cand,nodes,gen);
    // Ring exactly full and over-full: apply or recollect, preserving final values/order.
    for(unsigned count: {64U,65U}) {
        for(unsigned i=0;i<count;++i)pool[401].atari.m_flag^=0x200;
        verify(list,cand,nodes,gen);
    }
    // Sequence wrap uses the same unsigned arithmetic as the production ring.
    re4dc_atari_seq=std::numeric_limits<u32>::max()-3;
    cand.n=-1;verify(list,cand,nodes,gen);
    for(unsigned i=0;i<8;++i)pool[401].atari.m_flag^=0x200;
    verify(list,cand,nodes,gen);
    // Exact boundaries, retained over-capacity fallback, then shrinking and empty.
    for(unsigned n: {320U,321U,511U,512U,513U,600U,512U,319U,0U}) {
        fill(nodes,n,11);verify(list,cand,nodes,++gen);
        assert(list.n==(n<=ATLIST_MAX?int(n):-1));
        b=builds;verify(list,cand,nodes,gen);assert(builds==b);
    }
    // Ninety-six collidables fit; ninety-seven retain the original failure signal.
    fill(nodes,470,700);for(unsigned i=0;i<96;++i)pool[i].atari.m_flag=0x200;
    verify(list,cand,nodes,++gen);assert(reference(nodes[0]).size()==96);
    pool[450].atari.m_flag=0x200;verify(list,cand,nodes,gen);
    assert(reference(nodes[0]).size()==97);
    pool[450].atari.m_flag=0;verify(list,cand,nodes,gen);
    // Independent manager, disjoint storage, same generation value.
    AtList second={0,0,-1};AtCand secondCand={0,0,0,0,-1};
    std::vector<cEm*> other={&pool[650],&pool[651]};
    pool[650].atari.m_flag=0x200;pool[650].atari.m_radius2=1;link(other);
    verify(second,secondCand,other,gen);verify(list,cand,nodes,gen);
#if RE4DC_ATCHK_CACHE == 2
    assert(atcMis==0);
#if RE4DC_ATLIST_512
    // Negative control: bypass a live-field wrapper and prove check mode detects it.
    auto before=atcMis;pool[300].atari.m_flag.v=0x200;
    verify(list,cand,nodes,gen);assert(atcMis==before+1);
    pool[300].atari.m_flag=0;verify(list,cand,nodes,gen);
#endif
#endif
#if RE4DC_ATCHK_LIST == 2
    assert(atlMis==0);
    fill(nodes,600,11);verify(list,cand,nodes,++gen);
    auto beforeList=atlMis;nodes.resize(12);link(nodes);
    verify(list,cand,nodes,gen);assert(atlMis==beforeList+1);
#endif
    puts("PASS: 470 reuse, ordered candidates, dirty wrappers, lifetime, ring/wrap, limits, fallback, negative controls");
}
'''

class AtListCapacityTest(unittest.TestCase):
    def test_production_helpers(self):
        source=(ROOT/'src/game/at_mod.cpp').read_text()
        header=(ROOT/'include/atariInfo.h').read_text()
        wrappers=header[header.index('extern "C" u32 re4dc_atari_seq;'):header.index('#define RE4DC_AT_FLAG16')]
        collect=source[source.index('#define ATCHK_MAX'):source.index('#if defined(RE4DC_ATCHK_LIST)')]
        begin=source.index('#if defined(RE4DC_ATLIST_512)')
        helpers=source[begin:source.index('static int atchkCollectEm(',begin)]+'\n#endif\n'
        marker='static int atListBuild(AtList* L, cEm* head, u32 gen)\n{'
        self.assertIn(marker,helpers);helpers=helpers.replace(marker,marker+'\n    ++builds;',1)
        for name,text in [('atchkCollect(cEm* head, cEm** out)',collect),('atchkCollectList(const AtList* L, int N, cEm** out)',helpers)]:
            marker='static int '+name+'\n{';self.assertIn(marker,text)
            if name.startswith('atchkCollect('):collect=text.replace(marker,marker+'\n    ++collections;',1)
            else:helpers=text.replace(marker,marker+'\n    ++collections;',1)
        with tempfile.TemporaryDirectory() as td:
            td=Path(td);cpp=td/'probe.cpp';cpp.write_text(PRELUDE+wrappers+LAYOUT+collect+helpers+CASES)
            for enabled in (0,1):
                for check in (1,2):
                    for cache in (1,2):
                        binary=td/f'probe-{enabled}-{check}-{cache}'
                        subprocess.run(['g++','-std=c++11','-O2','-Wall','-Wextra',
                            '-Wno-missing-field-initializers','-Wno-unused-variable',
                            '-DRE4DC_ATLIST_OVERFLOW=1',f'-DRE4DC_ATLIST_512={enabled}',
                            f'-DRE4DC_ATCHK_LIST={check}',f'-DRE4DC_ATCHK_CACHE={cache}',
                            str(cpp),'-o',str(binary)],check=True)
                        subprocess.run([str(binary)],check=True)

if __name__=='__main__':unittest.main()
