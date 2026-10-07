#!/usr/bin/env python3
"""Compile the actual alive-list helpers and exercise overflow invalidation."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'src/game/at_mod.cpp'

PRELUDE = r'''
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <vector>
#include <algorithm>
using u32 = uintptr_t;
struct cAtariInfo { unsigned m_flag; float m_radius2; };
struct cEm { cEm* pNext; cAtariInfo atari; };
extern "C" void re4dc_log(const char*, ...) {}
static unsigned builds;
'''

CASES = r'''
static void link(std::vector<cEm*>& list) {
    for (unsigned i=0; i<list.size(); ++i)
        list[i]->pNext = i+1<list.size() ? list[i+1] : nullptr;
}
static std::vector<cEm*> reference(cEm* h) {
    std::vector<cEm*> out;
    for (; h; h=h->pNext)
        if ((h->atari.m_flag & 0x200) && h->atari.m_radius2 != 0)
            out.push_back(h);
    return out;
}
static void verify(AtList& cache, std::vector<cEm*>& list, u32 gen) {
    cEm* head = list.empty() ? nullptr : list[0];
    cEm* out[ATCHK_MAX];
    int N=atListSync(&cache,head,gen);
    int n=N<0 ? atchkCollect(head,out) : atchkCollectList(&cache,N,out);
    const auto expected=reference(head);
    if (expected.size()>ATCHK_MAX) assert(n==-1);
    else {
        assert(n==(int)expected.size());
        assert(std::equal(expected.begin(),expected.end(),out));
    }
}
int main() {
    cEm pool[700]{};
    std::vector<cEm*> list;
    for (int i=0; i<469; ++i) {
        pool[i].atari={unsigned(i%7==0 ? 0x200 : 0),1.0f};
        list.push_back(&pool[i]);
    }
    link(list);
    AtList cache={0,0,-1};
    u32 gen=11;
    verify(cache,list,gen);
    assert(cache.n==-1);
    auto initial=builds;
    for (int i=0; i<33; ++i) verify(cache,list,gen);
#if RE4DC_ATLIST_OVERFLOW
    assert(builds==initial);
#else
    assert(builds==initial+33);
#endif
    // Live flag/radius changes still reach the complete fallback every query.
    pool[1].atari.m_flag=0x200;
    pool[7].atari.m_radius2=0.0f;
    verify(cache,list,gen);
    // Reordering with a stable head, retirement, and same-address reuse.
    std::swap(list[2],list[400]); link(list); ++gen;
    initial=builds; verify(cache,list,gen); assert(builds==initial+1);
    auto retired=list[30]; list.erase(list.begin()+30); link(list); ++gen;
    verify(cache,list,gen);
    retired->atari={0x200,3.0f}; list.insert(list.begin()+1,retired); link(list); ++gen;
    verify(cache,list,gen);
    // Overflow -> exact capacity -> under capacity -> empty.
    list.resize(320); link(list); ++gen; verify(cache,list,gen); assert(cache.n==320);
    list.resize(319); link(list); ++gen; verify(cache,list,gen); assert(cache.n==319);
    list.clear(); ++gen; verify(cache,list,gen); assert(cache.n==0);
    // Same-head same-address room replacement is invalidated by generation.
    list={&pool[0],&pool[500]}; link(list); ++gen;
    verify(cache,list,gen); assert(cache.n==2);
    list={&pool[0],&pool[600],&pool[500]}; link(list); ++gen;
    verify(cache,list,gen); assert(cache.n==3);
    // Distinct managers never share the overflow state.
    std::vector<cEm*> other;
    for(int i=0;i<400;++i) other.push_back(&pool[i]);
    link(other); AtList otherCache={0,0,-1};
    verify(otherCache,other,gen); assert(otherCache.n==-1);
    std::vector<cEm*> small={&pool[650],&pool[651]}; link(small);
    verify(cache,small,gen); assert(cache.n==2); // changed head, same generation
    // Candidate overflow remains the original full-walk fallback signal.
    for (auto p:other) p->atari={0x200,1.0f};
    verify(otherCache,other,gen);
#if RE4DC_ATLIST_OVERFLOW && RE4DC_ATCHK_LIST == 2
    // Negative control: an unreported shrink must be caught by the check build.
    const auto before=atlMis;
    other.resize(12); link(other);
    verify(otherCache,other,gen);
    assert(atlMis==before+1 && otherCache.n==12);
#endif
    puts("PASS: overflow reuse, full fallback, live flags, reorder, retire, reuse, shrink, empty, manager isolation");
}
'''

class AtListOverflowTest(unittest.TestCase):
    def test_extracted_helpers(self):
        source=SOURCE.read_text()
        collect=source[source.index('#define ATCHK_MAX'):source.index('#if defined(RE4DC_ATCHK_LIST)')]
        begin=source.index('#define ATLIST_MAX')
        end=source.index('#if defined(RE4DC_ATCHK_CACHE) && RE4DC_ATCHK_CACHE\n// GAME_ATCHK_CACHE',begin)
        helpers=source[begin:end]
        marker='static int atListBuild(AtList* L, cEm* head, u32 gen)\n{'
        self.assertIn(marker,helpers)
        helpers=helpers.replace(marker,marker+'\n    ++builds;',1)
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            cpp=td/'probe.cpp'; cpp.write_text(PRELUDE+collect+helpers+CASES)
            for enabled in (0,1):
                for check in (1,2):
                    for cache in (0,1):
                        binary=td/f'probe-{enabled}-{check}-{cache}'
                        subprocess.run(['g++','-std=c++11','-O2','-Wall','-Wextra',
                            '-Wno-missing-field-initializers','-Wno-unused-variable',
                            f'-DRE4DC_ATLIST_OVERFLOW={enabled}',f'-DRE4DC_ATCHK_LIST={check}',
                            f'-DRE4DC_ATCHK_CACHE={cache}',str(cpp),'-o',str(binary)],check=True)
                        subprocess.run([str(binary)],check=True)

if __name__=='__main__': unittest.main()