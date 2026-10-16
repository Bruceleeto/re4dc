// KOS_CENSUS=1 (game30.mk, diagnostic builds only): a map of the live KOS malloc blocks by caller.
// The link wraps malloc / calloc / realloc / memalign / aligned_alloc / free and operator new / new[]; each live block is
// kept in a fixed table (pointer, size, caller return address; operator new's caller replaces malloc's).
// re4dc_kos_census_log() prints the callers by live bytes at each room lifecycle audit ("kos census:" lines; resolve the
// ra with sh-elf-addr2line). newlib's internal _malloc_r callers are not seen (the census total says how much is covered).
// KOS_CENSUS=2 (lane ramreclaim 2026-10-15) adds the peak census: the live total is tracked at every allocation, and the
// caller table is snapshotted at each new peak of the current window (with the KOS headroom and largest block at that
// moment, and the allocation that set the peak). re4dc_kos_census_window() prints the window's peak table ("kos peak:")
// and resets the window; re4dc_kos_threads_report() prints every KOS thread's stack and its measured high-water mark
// ("kos thread:"; a stack is painted below its saved / live stack pointer the first time a report sees the thread).
#ifndef RE4DC_KOS_CENSUS
#define RE4DC_KOS_CENSUS 0
#endif
#if RE4DC_KOS_CENSUS
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <malloc.h>
#include <unistd.h>
#include <arch/irq.h>
#include <kos/irq.h>
#include <kos/thread.h>
extern "C" void* __real_malloc(std::size_t);
extern "C" void* __real_calloc(std::size_t,std::size_t);
extern "C" void* __real_realloc(void*,std::size_t);
extern "C" void* __real_memalign(std::size_t,std::size_t);
extern "C" void* __real_aligned_alloc(std::size_t,std::size_t);
extern "C" void __real_free(void*);
extern "C" void* __real__Znwj(std::size_t);
extern "C" void* __real__Znaj(std::size_t);
extern "C" void re4dc_log(const char*,...);
extern "C" void re4dc_kos_heap_state(unsigned* free_chunks, unsigned* used, unsigned* break_room);  // platform/os.cpp
namespace {
struct Live { std::uintptr_t p; unsigned size; std::uintptr_t ra; };
constexpr unsigned kLive=4096;   // power of two, open addressing; deleted slots are p=1 tombstones
Live live[kLive];
unsigned lost,count;
unsigned cur;                    // live requested bytes (census-covered)
inline unsigned slot0(std::uintptr_t p){return unsigned((p>>3)^(p>>15))&(kLive-1U);}
#if RE4DC_KOS_CENSUS>=2
struct Row { std::uintptr_t ra; unsigned blocks,bytes,maxsz; };
constexpr unsigned kRows=192;
Row snap[kRows];
unsigned snap_rows,snap_live,snap_blocks,snap_free,snap_break,snap_top,snap_trig_size,snap_n;
std::uintptr_t snap_trig_ra;
unsigned win_peak;
bool in_snap;
void take_snapshot(unsigned trig_size,std::uintptr_t trig_ra){
    // called with IRQs enabled, outside the allocator: aggregate the table by caller
    in_snap=true;
    unsigned n=0,blocks=0;
    const int old=irq_disable();
    for(const Live& l:live){
        if(l.p<=1U)continue;
        ++blocks;
        unsigned i=0;
        while(i<n && snap[i].ra!=l.ra)++i;
        if(i==n){if(n==kRows)continue;snap[n++]={l.ra,0,0,0};}
        ++snap[i].blocks;snap[i].bytes+=l.size;if(l.size>snap[i].maxsz)snap[i].maxsz=l.size;
    }
    snap_live=cur;
    irq_restore(old);
    snap_rows=n;snap_blocks=blocks;snap_trig_size=trig_size;snap_trig_ra=trig_ra;++snap_n;
    unsigned kf=0,ku=0,kb=0;re4dc_kos_heap_state(&kf,&ku,&kb);
    const struct mallinfo mi=mallinfo();
    snap_free=kf;snap_break=kb;snap_top=kb+unsigned(mi.keepcost);
    in_snap=false;
}
#endif
void add(void* q,std::size_t n,void* ra){
    if(!q)return;
    const auto p=reinterpret_cast<std::uintptr_t>(q);
    const int old=irq_disable();
    unsigned h=slot0(p),tomb=kLive;
    for(unsigned i=0;i<kLive;++i,h=(h+1U)&(kLive-1U)){
        if(live[h].p==p){cur+=unsigned(n)-live[h].size;live[h].size=unsigned(n);live[h].ra=reinterpret_cast<std::uintptr_t>(ra);irq_restore(old);return;}
        if(live[h].p==1U && tomb==kLive)tomb=h;
        if(!live[h].p){if(tomb==kLive)tomb=h;break;}
    }
    if(tomb==kLive)++lost;
    else{live[tomb]={p,unsigned(n),reinterpret_cast<std::uintptr_t>(ra)};++count;cur+=unsigned(n);}
#if RE4DC_KOS_CENSUS>=2
    const bool peak=cur>win_peak;
    if(peak)win_peak=cur;
    irq_restore(old);
    if(peak && !in_snap && !irq_inside_int())take_snapshot(unsigned(n),reinterpret_cast<std::uintptr_t>(ra));
#else
    irq_restore(old);
#endif
}
void drop(void* q){
    if(!q)return;
    const auto p=reinterpret_cast<std::uintptr_t>(q);
    const int old=irq_disable();
    unsigned h=slot0(p);
    for(unsigned i=0;i<kLive && live[h].p;++i,h=(h+1U)&(kLive-1U))
        if(live[h].p==p){live[h].p=1U;--count;cur-=live[h].size;break;}
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
extern "C" void* __wrap_aligned_alloc(std::size_t a,std::size_t n){void* q=__real_aligned_alloc(a,n);add(q,n,__builtin_return_address(0));return q;}
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
#if RE4DC_KOS_CENSUS>=2
// The window's peak table, largest callers first, then a new window starting at the current live total.
extern "C" void re4dc_kos_census_window(unsigned room,unsigned frame){
    for(unsigned i=1;i<snap_rows;++i){Row r=snap[i];unsigned j=i;while(j && snap[j-1].bytes<r.bytes){snap[j]=snap[j-1];--j;}snap[j]=r;}
    unsigned kf=0,ku=0,kb=0;re4dc_kos_heap_state(&kf,&ku,&kb);
    re4dc_log("kos peak: room=%03x frame=%u live=%u blocks=%u callers=%u snaps=%u at_peak_headroom=%u free=%u break=%u top=%u "
        "trig_ra=%08x trig_size=%u now_live=%u now_headroom=%u lost=%u\n",room,frame,snap_live,snap_blocks,snap_rows,snap_n,
        snap_free+snap_break,snap_free,snap_break,snap_top,unsigned(snap_trig_ra),snap_trig_size,cur,kf+kb,lost);
    for(unsigned i=0;i<snap_rows && i<48;++i)
        re4dc_log("kos peak: room=%03x frame=%u ra=%08x blocks=%u bytes=%u max=%u\n",room,frame,unsigned(snap[i].ra),
            snap[i].blocks,snap[i].bytes,snap[i].maxsz);
    const int old=irq_disable();
    win_peak=cur;snap_n=0;
    irq_restore(old);
}
// Every KOS thread: label, tid, stack base and size, owned (KOS-allocated) or caller-provided, and the high-water mark.
// The first time a report sees a stack (by its base) it is painted with 0x5A from 32 bytes above the base (the source
// task stacks keep their 0xDEADBABE guard word there: scheduler.cpp StackOverflowCheck) up to 512 bytes below the saved
// stack pointer (the live one for the calling thread). Later reports count the bytes above the lowest word that is
// neither the paint nor the source pool's 0xB3 fill (the deepest use since the paint, by any thread on that stack).
namespace {
constexpr std::uint32_t kPaint=0x5A5A5A5Au, kPool=0xB3B3B3B3u;
constexpr unsigned kSkip=32;
struct Painted { std::uintptr_t lo; bool painted; };
Painted painted[64];
unsigned npainted;
void paint(kthread_t* t,Painted& e){
    const auto lo=reinterpret_cast<std::uintptr_t>(t->stack);
    std::uintptr_t sp;
    if(t==thd_current)__asm__ volatile("mov r15, %0":"=r"(sp));
    else sp=t->context.r[15];
    const std::uintptr_t stop=sp>512U?sp-512U:0;
    const bool ok=stop>lo+kSkip+16U && stop<=lo+t->stack_size;
    if(ok)for(std::uintptr_t a=lo+kSkip;a+4U<=stop;a+=4U)*reinterpret_cast<volatile std::uint32_t*>(a)=kPaint;
    e={lo,ok};
}
int report_cb(kthread_t* t,void*){
    if(!t->stack || !t->stack_size)return 0;
    const auto lo=reinterpret_cast<std::uintptr_t>(t->stack);
    unsigned i=0;while(i<npainted && painted[i].lo!=lo)++i;
    int high=-1;
    if(i<npainted){
        if(painted[i].painted){
            std::uintptr_t a=lo+kSkip;
            while(a<lo+t->stack_size){
                const std::uint32_t w=*reinterpret_cast<volatile std::uint32_t*>(a);
                if(w!=kPaint && w!=kPool)break;
                a+=4U;
            }
            high=int(lo+t->stack_size-a);
        }
    }else{
        if(npainted==64)return 0;
        ++npainted;
        const int old=irq_disable();
        paint(t,painted[i]);
        irq_restore(old);
        high=painted[i].painted?-2:-3;  // -2 painted now, -3 could not paint (stack pointer too low)
    }
    const std::uint32_t guard=*reinterpret_cast<volatile std::uint32_t*>(lo);
    re4dc_log("kos thread: tid=%d label=%s prio=%d stack=%08x size=%u owned=%u tls=%u guard=%08x high_water=%d\n",int(t->tid),
        t->label,int(t->prio),unsigned(lo),unsigned(t->stack_size),(t->flags&THD_OWNS_STACK)?1U:0U,t->tls_hnd?1U:0U,
        unsigned(guard),high);
    return 0;
}
}
extern "C" void re4dc_kos_threads_report(void){ thd_each(report_cb,nullptr); }
#endif
#endif
