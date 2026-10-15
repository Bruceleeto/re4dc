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
// A raw (unprefixed) "memset" reference (src/game/route_ck.cpp's asm) is wrapped to the raw symbol "__wrap_memset";
// without this alias it linked to a silent missing-symbol stub (obj/missing.txt "__wrap_memset").
extern "C" void* raw_wrap_memset(void* d,int c,std::size_t n) __asm__("__wrap_memset");
extern "C" void* raw_wrap_memset(void* d,int c,std::size_t n){note(0,__builtin_return_address(0),n);return __real_memset(d,c,n);}
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

// MEM_MOVCA=1 (game30.mk, lane memlay 2026-10-15; default 0): memset / memcpy through the same link wraps. Every
// whole 32-byte line of a destination in cached main RAM (P1 0x8c000000..0x8cffffff: KOS CCR 0x090d, CB=1 copy-
// back) is allocated with movca.l (no fill from RAM: the operand cache's write-allocate read) and then fully
// written. Head and tail bytes, calls under 64 bytes, unaligned memcpy sources and other areas go to the library
// routines unchanged; the bytes written are the same in every case. An interrupt between the movca and the line's
// last store can only write the partial line back early: the remaining stores then refill it and complete it.
#if defined(RE4DC_MEM_MOVCA) && RE4DC_MEM_MOVCA
#include <cstddef>
#include <cstdint>
extern "C" void* __real_memset(void*,int,std::size_t);
extern "C" void* __real_memcpy(void*,const void*,std::size_t);
namespace {
inline bool movca_area(std::uintptr_t a,std::size_t n){return (a>>24)==0x8cu && ((a+n-1)>>24)==0x8cu;}
inline void line_store(std::uintptr_t p,std::uint32_t w0,std::uint32_t w1,std::uint32_t w2,std::uint32_t w3,
                       std::uint32_t w4,std::uint32_t w5,std::uint32_t w6,std::uint32_t w7){
    __asm__ __volatile__("movca.l r0,@%0"::"r"(p),"z"(w0):"memory");
    auto* q=reinterpret_cast<volatile std::uint32_t*>(p);
    q[1]=w1;q[2]=w2;q[3]=w3;q[4]=w4;q[5]=w5;q[6]=w6;q[7]=w7;
}
}
extern "C" void* __wrap_memset(void* d,int c,std::size_t n){
    const auto a=reinterpret_cast<std::uintptr_t>(d);
    if(n<64 || !movca_area(a,n))return __real_memset(d,c,n);
    const std::uintptr_t lo=(a+31)&~std::uintptr_t(31),hi=(a+n)&~std::uintptr_t(31);
    if(lo>a)__real_memset(d,c,lo-a);
    std::uint32_t w=std::uint8_t(c);w|=w<<8;w|=w<<16;
    for(std::uintptr_t p=lo;p<hi;p+=32)line_store(p,w,w,w,w,w,w,w,w);
    if(a+n>hi)__real_memset(reinterpret_cast<void*>(hi),c,a+n-hi);
    return d;
}
// A raw (unprefixed) "memset" reference (src/game/route_ck.cpp's asm) wraps to the raw symbol (as MEMPROF).
extern "C" void* raw_movca_memset(void* d,int c,std::size_t n) __asm__("__wrap_memset");
extern "C" void* raw_movca_memset(void* d,int c,std::size_t n){return __wrap_memset(d,c,n);}
extern "C" void* __wrap_memcpy(void* d,const void* s,std::size_t n){
    const auto a=reinterpret_cast<std::uintptr_t>(d);
    if(n<64 || !movca_area(a,n))return __real_memcpy(d,s,n);
    const std::uintptr_t lo=(a+31)&~std::uintptr_t(31),hi=(a+n)&~std::uintptr_t(31);
    const auto* src=static_cast<const unsigned char*>(s);
    if(reinterpret_cast<std::uintptr_t>(src+(lo-a))&3U)return __real_memcpy(d,s,n);
    if(lo>a)__real_memcpy(d,s,lo-a);
    const auto* w=reinterpret_cast<const std::uint32_t*>(src+(lo-a));
    const std::uintptr_t end=reinterpret_cast<std::uintptr_t>(src)+n;
    for(std::uintptr_t p=lo;p<hi;p+=32,w+=8){
        if(reinterpret_cast<std::uintptr_t>(w+8)+32<=end)__asm__ __volatile__("pref @%0"::"r"(w+8));
        line_store(p,w[0],w[1],w[2],w[3],w[4],w[5],w[6],w[7]);
    }
    if(a+n>hi)__real_memcpy(reinterpret_cast<void*>(hi),src+(hi-a),a+n-hi);
    return d;
}
#endif
