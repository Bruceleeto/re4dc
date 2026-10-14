// Real allocator/main_mem fixture shared by the retained-lifetime and full
// callback tests. Only external platform services and fault injection are fake.
#include <cstddef>
#define RE4DC_GAME 1
#define RE4DC_ACTOR_TRANSACTION 1
#include "ps2_source_world.h"
using s32=std::int32_t;
#include "source_world_actual_memory_types.inc"
static_assert(sizeof(OSHeapCell)==32,"OSAlloc literal32-byte header");
static_assert(sizeof(void*)==8 || sizeof(void*)==4);
constexpr int MEM_HEAP_NUM=13,MEM_HEAP_CURRENT=13;
MemHeap Heap[MEM_HEAP_NUM];OSHeapDescriptor heap_backup[MEM_HEAP_NUM];
static OSHeapDescriptor* HeapHead;
OSHeapCell* cell_main=nullptr;OSHeapCell* cell_game=nullptr;static OSHeapCell* cell_stage=nullptr;OSHeapCell* cell_dll=nullptr;
u32 arenaLo,arenaHi;u8 CurrentHeap,CurrentDbgHeap;void* pMemTile;char* pRK;
Re4dcMemLayout re4dc_mem{};int re4dc_diag=0;
alignas(32) unsigned char heap_memory[4*1024*1024];
OSHeapDescriptor* heap_descriptors;
extern "C" {
unsigned source_test_sdk_descriptor_size();unsigned source_test_sdk_cell_size_offset();unsigned source_test_sdk_payload_offset();
void* OSInitAlloc(void*,void*,int);int OSCreateHeap(void*,void*);void OSDestroyHeap(int);
void* OSAllocFromHeap(int,u32);void OSFreeToHeap(int,void*);s32 OSCheckHeap(int);int OSSetCurrentHeap(int);
extern volatile int __OSCurrHeap;
void* __real_OSInitAlloc(void*,void*,int);int __real_OSCreateHeap(void*,void*);
void __real_OSDestroyHeap(int);void __real_OSFreeToHeap(int,void*);
void OSReport(const char*,...){}
void* OSGetArenaLo(){return reinterpret_cast<void*>(re4dc_mem.arena_lo);}
void* OSGetArenaHi(){return reinterpret_cast<void*>(re4dc_mem.heap_end);}
void OSSetArenaLo(void*){}void OSSetArenaHi(void*){}void OSSetSaveRegion(void*,void*){}
void* re4dc_gx_fifo(){return nullptr;}void* re4dc_frame_buffer(int){return nullptr;}
void memclr_asm(void* p,u32 n){std::memset(p,0,n);}
}
struct Logger {template<class... A>void warn(A...){assert(false);}template<class... A>void err(A...){assert(false);}} logger,*pLog=&logger;
#define HALT() std::abort()
#define MEM_ALLOC(size,a,b) mem_alloc(size,__FILE__,__LINE__,a,b)
void memInitHeapTbl();void MemSuspendHeap(int);void MemSignalHeap(int);int memGetHeapSattus(int);
int memCheckHeapActive(int);int MemSetCurrentHeap(int);u32 MemCheckHeapEnd(int);
int MemCreateHeap(int,u32,u32);int MemDestroyHeap(int);int MemReplaceHeap(int,int);void MemClearAllHeap();
void* mem_alloc(u32,const char*,int,int,int);void Mem_free_h(void*,int);void Debug_free_h(void*,int);
void (*actor_before_forget)()=nullptr;
void re4dc_actor_forget_all(){}
void re4dc_actor_forget_range(void*,unsigned){auto* f=actor_before_forget;actor_before_forget=nullptr;if(f)f();}
#include "source_world_retained.inc"
#include "source_world_actual_memory.inc"
void (*sdk_before_create)()=nullptr;void (*sdk_before_destroy)()=nullptr;
void (*sdk_before_init)()=nullptr;void (*sdk_before_free)()=nullptr;
bool sdk_fail_create=false;
void one_shot(void (**hook)()){auto* next=*hook;*hook=nullptr;if(next)next();}
extern "C" int __wrap_OSCreateHeap(void* a,void* b){one_shot(&sdk_before_create);if(sdk_fail_create){sdk_fail_create=false;return -1;}return __real_OSCreateHeap(a,b);}
extern "C" void __wrap_OSDestroyHeap(int h){one_shot(&sdk_before_destroy);__real_OSDestroyHeap(h);}
extern "C" void* __wrap_OSInitAlloc(void* a,void* b,int n){one_shot(&sdk_before_init);return __real_OSInitAlloc(a,b,n);}
extern "C" void __wrap_OSFreeToHeap(int h,void* p){one_shot(&sdk_before_free);__real_OSFreeToHeap(h,p);}
void allocator_reset(){
    assert(source_test_sdk_descriptor_size()==sizeof(OSHeapDescriptor));
    assert(source_test_sdk_cell_size_offset()==offsetof(OSHeapCell,size));
    assert(source_test_sdk_payload_offset()==sizeof(OSHeapCell));
    sdk_before_create=sdk_before_destroy=sdk_before_init=sdk_before_free=nullptr;actor_before_forget=nullptr;sdk_fail_create=false;
    const auto base=reinterpret_cast<unsigned long>(heap_memory);assert(base+sizeof(heap_memory)<=0xffffffffUL);
    re4dc_mem={};re4dc_mem.heap=base;re4dc_mem.heap_end=base+sizeof(heap_memory);
    re4dc_mem.arena_lo=re4dc_mem.dvd=base;
    // SystemMemInit itself revokes the old lifetime before OSInitAlloc writes.
    SystemMemInit();heap_descriptors=HeapHead;
}
void* host_alloc(unsigned bytes){void* p=mem_alloc(bytes,"host fixture",0,1,MEM_HEAP_CURRENT);assert(p);return p;}
