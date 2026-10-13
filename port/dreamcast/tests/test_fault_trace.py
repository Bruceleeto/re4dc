"""Fault diagnostics must not follow corrupt stack/instruction addresses."""
from pathlib import Path
import subprocess
import tempfile
import unittest

HEADER = Path(__file__).resolve().parents[1] / 'game/platform/fault_trace.hpp'


class FaultTraceBounds(unittest.TestCase):
    def test_corrupt_context_and_bounded_candidate_scan(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            (p/'test.cpp').write_text('#include "'+str(HEADER)+'"\n'+SOURCE)
            subprocess.run(['g++','-std=c++20','-O1','-g','-fsanitize=address,undefined',
                            '-fno-pie','-no-pie',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
            subprocess.run([str(p/'test')],check=True)


SOURCE = r'''
#include <array>
#include <cassert>
#include <cstdint>
int main() {
    std::array<std::uint32_t,600> stack{};
    std::array<std::uint16_t,32> code{};
    std::uint32_t output[12]{};
    unsigned reads=0, fetches=0;
    auto word=[&](std::uint32_t a) {
        assert(a>=0x2000 && a<0x2000+stack.size()*4 && !(a&3));
        ++reads; return stack[(a-0x2000)/4];
    };
    auto half=[&](std::uint32_t a) {
        assert(a>=0x1000 && a<0x1040 && !(a&1));
        ++fetches; return code[(a-0x1000)/2];
    };
    auto scan=[&](std::uint32_t sp, std::uint32_t end, unsigned cap=12) {
        reads=fetches=0;
        return re4dc::fault_trace::collect(sp,0x2000,end,0x1000,0x1040,output,cap,word,half);
    };
    code[0]=0x430b; code[2]=0xb123; code[4]=0x0503;  // jsr, bsr, bsrf
    code[6]=0x402b; code[8]=0x000b;                 // jmp and rts are not calls
    stack[0]=0x1004; stack[1]=0x1008; stack[2]=0x100c;
    stack[3]=0x1010; stack[4]=0x1014;
    stack[5]=0x1005; stack[6]=0x1000; stack[7]=0xffffffff; stack[8]=0x1040;
    assert(scan(0x2000,0x2024)==3 && reads==9 && fetches==5);
    assert(output[0]==0x1004 && output[1]==0x1008 && output[2]==0x100c);
    assert(scan(0x2000,0x2024,2)==2 && reads==2);
    assert(scan(0x2000,0x2024,0)==0 && reads==0);
    for (auto sp : {0U,0x1ffcU,0x2001U,0x2024U,0xfffffff0U})
        assert(scan(sp,0x2024)==0 && reads==0 && fetches==0);
    assert(scan(0x2000,0x2003)==0 && reads==0);  // no complete stack word
    assert(scan(0x2000,0x2000)==0 && reads==0);
    assert(scan(0x2000,0x1ffc)==0 && reads==0);
    stack.fill(0);
    assert(scan(0x2000,0x2000+600*4)==0 && reads==512);
    stack[599]=0x1004;
    assert(scan(0x2000+599*4,0x2000+600*4)==1 && reads==1);
    reads=fetches=0;
    assert(re4dc::fault_trace::collect(0x2000,0x2000,0x2004,0xfffffffdU,0xffffffffU,
                                     output,12,word,half)==0 && !reads && !fetches);
}
'''

if __name__ == '__main__':
    unittest.main()
