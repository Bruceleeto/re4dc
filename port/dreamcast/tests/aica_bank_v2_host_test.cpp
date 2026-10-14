#include "../game/platform/aica_bank_v2_host.h"
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <vector>
using namespace re4dc_aic2;
namespace {
unsigned checks=0;
void check(bool ok,const char* expression,int line){++checks;if(!ok){std::ostringstream s;s<<"line "<<line<<": "<<expression;throw std::runtime_error(s.str());}}
#define CHECK(x) check((x),#x,__LINE__)
#define OK(x) CHECK((x)==Result::Ok)
#define IS(x,y) CHECK((x)==Result::y)
void pool_tests() {
 Pool p(1024);Interval a,b,c,x;OK(p.allocate(256,false,a));OK(p.allocate(256,false,b));OK(p.allocate(256,false,c));CHECK(a.base==0&&b.base==256&&c.base==512);
 OK(p.release(b));CHECK(p.free_bytes()==512&&p.largest_free()==256);IS(p.allocate(512,false,x),NoSpace);IS(p.release({a.base,32}),Stale);IS(p.release(b),Stale);
 OK(p.release(a));CHECK(p.largest_free()==512);OK(p.allocate(512,true,x));CHECK(x.base==0);OK(p.release(c));OK(p.release(x));CHECK(p.free_bytes()==1024&&p.free_count==1&&p.invariant());
 IS(p.allocate(0,false,x),Invalid);IS(p.allocate(0xffffffffu,false,x),Overflow);IS(p.release({0xffffffe0u,64}),Invalid);
 Pool q(4096);std::vector<Interval> ext;
 for(unsigned i=0;i<64;++i){OK(q.allocate(1,i%2,x));ext.push_back(x);}IS(q.allocate(32,false,x),Capacity);CHECK(q.invariant());
 for(unsigned parity=0;parity<2;++parity)for(unsigned i=parity;i<64;i+=2){OK(q.release(ext[i]));CHECK(q.invariant());}
 CHECK(q.free_bytes()==4096&&q.free_count==1);Pool invalid(31);CHECK(!invalid.invariant());
 Counter n{0xffffffffu,3};OK(next_counter(n));CHECK(n.lo==0&&n.hi==4);n={0xffffffffu,0xffffffffu};IS(next_counter(n),Overflow);CHECK(n.lo==0xffffffffu&&n.hi==0xffffffffu);
}

void allocator_stress(){
    Pool p;std::vector<Interval> live;uint32_t seed=0x51a3c27u;
    for(uint32_t i=0;i<50000;++i){
        seed=seed*1664525u+1013904223u;
        if(!live.empty() && (seed&3)==0){uint32_t pick=(seed>>8)%live.size();OK(p.release(live[pick]));live.erase(live.begin()+pick);}
        else{Interval block;Result r=p.allocate(((seed>>9)%8192)+1,(seed&4)!=0,block);CHECK(r==Result::Ok||r==Result::Capacity||r==Result::NoSpace);if(r==Result::Ok)live.push_back(block);}
        CHECK(p.invariant());uint32_t total=p.free_bytes();for(Interval block:live)total+=block.bytes;CHECK(total==kMixedBytes);
    }
    for(Interval block:live){OK(p.release(block));}
    CHECK(p.invariant()&&p.free_bytes()==kMixedBytes);
    Core c;VerificationReceipt forged;IS(c.verify(forged),Stale);CHECK(c.invariant());
}
}
int main(){try{pool_tests();allocator_stress();std::cout<<"{\"checks\":"<<checks<<",\"metadata_bytes\":"<<sizeof(Core)<<",\"pool_bytes\":"<<sizeof(Pool)<<",\"host_only\":true}\n";return 0;}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}}
