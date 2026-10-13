// KOS_CENSUS=1 (game30.mk, diagnostic builds only): a map of the live KOS malloc blocks by caller.
// The link wraps malloc / calloc / realloc / memalign / free and operator new / new[]; each live block is kept in a
// fixed table (pointer, size, caller return address; operator new's caller replaces malloc's). re4dc_kos_census_log()
// prints the callers by live bytes at each room lifecycle audit ("kos census:" lines; resolve the ra with
// sh-elf-addr2line). newlib's internal _malloc_r callers are not seen (the census total says how much is covered).
#ifndef RE4DC_KOS_CENSUS
#define RE4DC_KOS_CENSUS 0
#endif
#if RE4DC_KOS_CENSUS
#include <cstddef>
#include <cstdint>
#include <arch/irq.h>
extern "C" void* __real_malloc(std::size_t);
extern "C" void* __real_calloc(std::size_t,std::size_t);
extern "C" void* __real_realloc(void*,std::size_t);
extern "C" void* __real_memalign(std::size_t,std::size_t);
extern "C" void __real_free(void*);
extern "C" void* __real__Znwj(std::size_t);
extern "C" void* __real__Znaj(std::size_t);
extern "C" void re4dc_log(const char*,...);
namespace {
struct Live { std::uintptr_t p; unsigned size; std::uintptr_t ra; };
constexpr unsigned kLive=4096;   // power of two, open addressing; deleted slots are p=1 tombstones
Live live[kLive];
unsigned lost,count;
inline unsigned slot0(std::uintptr_t p){return unsigned((p>>3)^(p>>15))&(kLive-1U);}
void add(void* q,std::size_t n,void* ra){
    if(!q)return;
    const auto p=reinterpret_cast<std::uintptr_t>(q);
    const int old=irq_disable();
    unsigned h=slot0(p),tomb=kLive;
    for(unsigned i=0;i<kLive;++i,h=(h+1U)&(kLive-1U)){
        if(live[h].p==p){live[h].size=unsigned(n);live[h].ra=reinterpret_cast<std::uintptr_t>(ra);irq_restore(old);return;}
        if(live[h].p==1U && tomb==kLive)tomb=h;
        if(!live[h].p){if(tomb==kLive)tomb=h;break;}
    }
    if(tomb==kLive)++lost;
    else{live[tomb]={p,unsigned(n),reinterpret_cast<std::uintptr_t>(ra)};++count;}
    irq_restore(old);
}
void drop(void* q){
    if(!q)return;
    const auto p=reinterpret_cast<std::uintptr_t>(q);
    const int old=irq_disable();
    unsigned h=slot0(p);
    for(unsigned i=0;i<kLive && live[h].p;++i,h=(h+1U)&(kLive-1U))
        if(live[h].p==p){live[h].p=1U;--count;break;}
    irq_restore(old);
}
void reattribute(void* q,void* ra){
    const auto p=reinterpret_cast<std::uintptr_t>(q);
    const int old=irq_disable();
    unsigned h=slot0(p);
    for(unsigned i=0;i<kLive && live[h].p;++i,h=(h+1U)&(kLive-1U))
        if(live[h].p==p){live[h].ra=reinterpret_cast<std::uintptr_t>(ra);break;}
    irq_restore(old);
}
}
extern "C" void* __wrap_malloc(std::size_t n){void* q=__real_malloc(n);add(q,n,__builtin_return_address(0));return q;}
extern "C" void* __wrap_calloc(std::size_t a,std::size_t b){void* q=__real_calloc(a,b);add(q,a*b,__builtin_return_address(0));return q;}
extern "C" void* __wrap_memalign(std::size_t a,std::size_t n){void* q=__real_memalign(a,n);add(q,n,__builtin_return_address(0));return q;}
extern "C" void* __wrap_realloc(void* o,std::size_t n){
    void* q=__real_realloc(o,n);
    if(q || !n){drop(o);add(q,n,__builtin_return_address(0));}
    return q;
}
extern "C" void __wrap_free(void* q){drop(q);__real_free(q);}
extern "C" void* __wrap__Znwj(std::size_t n){void* q=__real__Znwj(n);reattribute(q,__builtin_return_address(0));return q;}
extern "C" void* __wrap__Znaj(std::size_t n){void* q=__real__Znaj(n);reattribute(q,__builtin_return_address(0));return q;}
extern "C" void re4dc_kos_census_log(const char* phase,unsigned room){
    struct Row { std::uintptr_t ra; unsigned blocks,bytes; };
    static Row rows[256];
    unsigned nrows=0,total=0,blocks=0,overflow=0;
    const int old=irq_disable();
    for(const Live& l:live){
        if(l.p<=1U)continue;
        total+=l.size;++blocks;
        unsigned i=0;
        while(i<nrows && rows[i].ra!=l.ra)++i;
        if(i==nrows){if(nrows==256){++overflow;continue;}rows[nrows++]={l.ra,0,0};}
        ++rows[i].blocks;rows[i].bytes+=l.size;
    }
    irq_restore(old);
    // largest first
    for(unsigned i=1;i<nrows;++i){Row r=rows[i];unsigned j=i;while(j && rows[j-1].bytes<r.bytes){rows[j]=rows[j-1];--j;}rows[j]=r;}
    re4dc_log("kos census: phase=%s room=%03x blocks=%u bytes=%u callers=%u lost=%u overflow=%u\n",phase,room,blocks,total,
        nrows,lost,overflow);
    for(unsigned i=0;i<nrows;++i)
        re4dc_log("kos census: phase=%s room=%03x ra=%08x blocks=%u bytes=%u\n",phase,room,unsigned(rows[i].ra),
            rows[i].blocks,rows[i].bytes);
}
#endif
