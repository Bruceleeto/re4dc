// MEMPROF=1 (game30.mk, diagnostic builds only): memset / memcpy call sites by bytes.
// The link wraps both (--wrap); every call adds its size to its caller's row (return address), and
// re4dc_memprof_log() prints the heaviest rows every 120 frames, then clears them. Rows are
// approximate under interrupts (no locking); callers resolve with sh-elf-addr2line on the ELF.
#ifndef RE4DC_MEMPROF
#define RE4DC_MEMPROF 0
#endif
#if RE4DC_MEMPROF
#include <cstddef>
#include <cstdint>
extern "C" void* __real_memset(void*,int,std::size_t);
extern "C" void* __real_memcpy(void*,const void*,std::size_t);
extern "C" void re4dc_log(const char*,...);
namespace {
struct Row { std::uintptr_t ra; unsigned calls; unsigned bytes; };
constexpr unsigned kRows=128;
Row rows[2][kRows];
unsigned lost[2];
bool logging=false;
inline void note(unsigned kind,void* ra,std::size_t n){
    if(logging)return;
    const auto a=reinterpret_cast<std::uintptr_t>(ra);
    unsigned h=unsigned((a>>1)^(a>>9))&(kRows-1U);
    for(unsigned probe=0;probe<16;++probe,h=(h+1U)&(kRows-1U)){
        Row& r=rows[kind][h];
        if(r.ra==a || !r.ra){r.ra=a;++r.calls;r.bytes+=unsigned(n);return;}
    }
    ++lost[kind];
}
}
extern "C" void* __wrap_memset(void* d,int c,std::size_t n){note(0,__builtin_return_address(0),n);return __real_memset(d,c,n);}
extern "C" void* __wrap_memcpy(void* d,const void* s,std::size_t n){note(1,__builtin_return_address(0),n);return __real_memcpy(d,s,n);}
extern "C" void re4dc_memprof_log(unsigned frame,unsigned frames){
    logging=true;
    for(unsigned k=0;k<2;++k){
        Row top[12]{};
        for(const Row& r:rows[k]){
            if(!r.ra)continue;
            for(unsigned i=0;i<12;++i)if(r.bytes>top[i].bytes){for(unsigned j=11;j>i;--j)top[j]=top[j-1];top[i]=r;break;}
        }
        for(unsigned i=0;i<12 && top[i].ra;++i)
            re4dc_log("MEMPROF frame=%u kind=%s rank=%u ra=%08x calls=%u bytes=%u per_frame=%u\n",frame,k?"memcpy":"memset",
                i,unsigned(top[i].ra),top[i].calls,top[i].bytes,frames?top[i].bytes/frames:0U);
        if(lost[k])re4dc_log("MEMPROF frame=%u kind=%s lost=%u\n",frame,k?"memcpy":"memset",lost[k]);
        for(Row& r:rows[k])r={};
        lost[k]=0;
    }
    logging=false;
}
#endif
