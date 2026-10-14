// Production OSAlloc and source heap transitions; no renderer/GPU claim.
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <sys/mman.h>
#include "re4dc_platform.h"
#define RE4DC_PS2_WORLD_SOURCE_OWNER 1
using u32=std::uint32_t;using u8=unsigned char;using u16=unsigned short;using f32=float;
#include "source_world_allocator.inc"
#include "source_world_memory.inc"
#include "source_world_actual_ot.inc"
OtWork g_OtWork[OT_MAX];int g_NowExecOtType=OT_MAX;
void ClearOt();void clearOtWork(OtWork*);void CrearOtMirrorWork(){}
#include "source_world_actual_init_ot.inc"
unsigned checks=0;
void check_at(bool value,unsigned line){++checks;if(!value){std::fprintf(stderr,"retained check%u line%u failed\n",checks,line);std::abort();}}
#define check(v) check_at(bool(v),__LINE__)
extern "C" unsigned long source_test_sdk_state(unsigned);
unsigned read_only_queries=0,rejected_read_only_queries=0;
std::vector<unsigned char> allocator_snapshot(){
 std::vector<unsigned char> out;
 auto add=[&](const void* p,std::size_t n){const auto* b=static_cast<const unsigned char*>(p);out.insert(out.end(),b,b+n);};
 // Includes every source cell/free list/SDK descriptor, suspended descriptors,
 // source checker heads, both allocator generations and SDK-private globals.
 add(heap_memory,sizeof(heap_memory));add(Heap,sizeof(Heap));add(heap_backup,sizeof(heap_backup));
 add(&HeapHead,sizeof(HeapHead));add(&SysMem,sizeof(SysMem));add(&re4dc_mem,sizeof(re4dc_mem));
 add(&sourceWorldRetained,sizeof(sourceWorldRetained));add(&sourceWorldHeapMutation,sizeof(sourceWorldHeapMutation));
 add(&cell_main,sizeof(cell_main));add(&cell_game,sizeof(cell_game));add(&cell_stage,sizeof(cell_stage));add(&cell_dll,sizeof(cell_dll));
 add(&arenaLo,sizeof(arenaLo));add(&arenaHi,sizeof(arenaHi));add(&CurrentHeap,sizeof(CurrentHeap));add(&CurrentDbgHeap,sizeof(CurrentDbgHeap));
 add(&pMemTile,sizeof(pMemTile));add(&pRK,sizeof(pRK));
 for(unsigned i=0;i<5;++i){const auto v=source_test_sdk_state(i);add(&v,sizeof(v));}
 return out;
}
int query_readonly(const void* value,unsigned bytes){
 const auto before=allocator_snapshot();const int result=re4dc_source_world_ot_retained(value,bytes);
 check(before==allocator_snapshot());++read_only_queries;if(!result)++rejected_read_only_queries;return result;
}
OSHeapCell* embedded_header(OSHeapCell* head,void* storage,bool append){
 auto* fake=static_cast<OSHeapCell*>(storage);std::memset(fake,0,96);fake->size=96;
 auto* tag=reinterpret_cast<unsigned char*>(fake)+64;tag[0]=0;std::memcpy(tag+1,"MAD",3);
 if(append){auto* tail=head;while(tail->next)tail=tail->next;tail->next=fake;fake->prev=tail;}
 else {fake->next=head;head->prev=fake;}
 return append?head:fake;
}
void begin_game(){allocator_reset();check(MemReplaceHeap(0,1));check(MemSetCurrentHeap(1));}
void freeze_game(){check(MemReplaceHeap(1,2));check(MemSetCurrentHeap(2));}
void game_prefix(){begin_game();InitOt();freeze_game();check(sourceWorldRetained.live);}
bool bucket(unsigned table=0x0b){const auto& ot=g_OtWork[table];return query_readonly(ot.list,ot.max*sizeof(OtData));}
unsigned observed_epoch=0,observations=0;
void revoked_before_write(){++observations;check(!sourceWorldRetained.live);check(re4dc_source_world_ot_epoch()!=observed_epoch);}
void extra_owner_retirement(){check(MemDestroyHeap(1)==0);}
void extra_suspend(){MemSuspendHeap(7);}
struct GuardPage {void* p=mmap(nullptr,4096,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);GuardPage(){assert(p!=MAP_FAILED);}~GuardPage(){munmap(p,4096);}};
int main(){
 begin_game();InitOt();
 for(auto& ot:g_OtWork)check(sourceWorldAllocated(ot.list,ot.max*sizeof(OtData),true));
 auto* game_head=HeapHead[Heap[1].handle].allocated;const int old_descriptor=Heap[1].handle;
 const auto first=reinterpret_cast<unsigned long>(g_OtWork[0x0b].list);
 freeze_game();check(cell_game==game_head&&sourceWorldRetained.head==game_head);
 check(Heap[1].handle==-1&&Heap[2].handle==old_descriptor);
 for(unsigned i=0;i<OT_MAX;++i){const auto& ot=g_OtWork[i];
  check(!sourceWorldAllocated(ot.list,ot.max*sizeof(OtData),true));check(bucket(i));
  check(!query_readonly(reinterpret_cast<unsigned char*>(ot.list)+1,ot.max*sizeof(OtData)));
  const unsigned rounded=(ot.max*sizeof(OtData)+31)&~31U;
  check(!query_readonly(ot.list,rounded+1));}
 std::puts("D35 defect reproduced: all23 actual InitOt buckets survive replacement but active-only guard refuses them");
 const auto epoch=re4dc_source_world_ot_epoch();
 host_alloc(96);check(MemReplaceHeap(2,3)&&MemSetCurrentHeap(3));host_alloc(96);
 check(MemReplaceHeap(3,4)&&MemSetCurrentHeap(4));auto* prim=host_alloc(4096);
 check(sourceWorldAllocated(prim,4096,true)&&!query_readonly(prim,4096));
 check(bucket()&&re4dc_source_world_ot_epoch()==epoch);
 // Inactive-from replacements reuse only child tails and keep game lifetime.
 for(int from=3;from>=1;--from){check(MemReplaceHeap(from,from+1));check(MemSetCurrentHeap(from+1));check(bucket());check(re4dc_source_world_ot_epoch()==epoch);}
 // A freed interior source cell is not rescued by its old MAD tag or range.
 begin_game();void* hole=host_alloc(256);InitOt();OSFreeToHeap(Heap[1].handle,hole);freeze_game();
 check(bucket()&&!query_readonly(hole,256));
 check(!query_readonly(reinterpret_cast<void*>(sourceWorldRetained.begin),32));
 check(!query_readonly(reinterpret_cast<void*>(sourceWorldRetained.end),32));
 // Actual first-fit/no-split behavior gives32 spare bytes after MAD.
 begin_game();void* donor=OSAllocFromHeap(Heap[1].handle,320);host_alloc(96);
 OSFreeToHeap(Heap[1].handle,donor);void* donated=mem_alloc(256,"trans_ot.cpp",53,1,1);
 check(donated==donor&&((OSHeapCell*)donated-1)->size==352);freeze_game();
 check(query_readonly(donated,256));check(!query_readonly(donated,257));
 // A forged linked header and valid MAD inside a real allocation must not
 // become another OT allocation, in either list order. This was admitted by
 // the original D41 bounded-header validator (preserved failing artifact).
 for(unsigned append=0;append<2;++append){game_prefix();auto* storage=reinterpret_cast<unsigned char*>(g_OtWork[0x0b].list)+32;
  sourceWorldRetained.head=embedded_header(sourceWorldRetained.head,storage,append);
  std::fprintf(stderr,"embedded OT header/MAD order%u must be rejected\n",append);
  check(!query_readonly(reinterpret_cast<OSHeapCell*>(storage)+1,32));check(!bucket());
 }
 // Capture must reject any overlap before the source's unbounded traversal,
 // even if no queried OT belongs to the conflicting pair.
 for(unsigned append=0;append<2;++append){begin_game();InitOt();auto& descriptor=HeapHead[Heap[1].handle];
  descriptor.allocated=embedded_header(descriptor.allocated,reinterpret_cast<unsigned char*>(g_OtWork[0x0b].list)+32,append);
  check(!MemReplaceHeap(1,2));check(Heap[1].handle>=0&&!sourceWorldRetained.live);
 }
 begin_game();InitOt();auto* overlapping=HeapHead[Heap[1].handle].allocated->next;overlapping->size+=32;
 check(!MemReplaceHeap(1,2));check(Heap[1].handle>=0&&!sourceWorldRetained.live);
 // Multi-node repeats/cycles, including a duplicate interior node.
 for(unsigned shape=0;shape<3;++shape){game_prefix();auto* h=sourceWorldRetained.head;
  if(shape==0)h->next->next=h;else if(shape==1)h->next->next=h->next;
  else {auto* tail=h;while(tail->next)tail=tail->next;tail->next=h->next;}
  check(!bucket());
 }
 // The source donor's MAD block and spare32 bytes are never independent OT
 // allocations. Query isolation covers the entire containing cell, including
 // spare bytes after the actual MAD block.
 begin_game();donor=OSAllocFromHeap(Heap[1].handle,320);host_alloc(96);OSFreeToHeap(Heap[1].handle,donor);
 donated=mem_alloc(256,"trans_ot.cpp",53,1,1);check(donated==donor);freeze_game();
 check(query_readonly(donated,256));check(query_readonly(donated,255));
 for(unsigned bytes:{0U,257U,288U,289U,320U,~0U})check(!query_readonly(donated,bytes));
 check(!query_readonly(reinterpret_cast<unsigned char*>(donated)-32,32));
 for(unsigned offset:{1U,256U,288U,320U})
  check(!query_readonly(reinterpret_cast<unsigned char*>(donated)+offset,32));
 check(!query_readonly(nullptr,32));check(!query_readonly(nullptr,0));
 auto* slack_header=reinterpret_cast<OSHeapCell*>(reinterpret_cast<unsigned char*>(donated)+288);
 std::memset(slack_header,0,32);slack_header->size=64;slack_header->next=sourceWorldRetained.head;
 sourceWorldRetained.head->prev=slack_header;sourceWorldRetained.head=slack_header;
 check(!query_readonly(donated,256));
 // Revocation occurs before source/SDK writes, including negative handles.
 for(unsigned mutation=0;mutation<8;++mutation){game_prefix();observed_epoch=re4dc_source_world_ot_epoch();
  const u32 begin=sourceWorldRetained.begin,end=sourceWorldRetained.end;
  switch(mutation){
   case 0:sdk_before_create=revoked_before_write;check(MemCreateHeap(1,begin,end));break;
   case 1:sdk_before_create=revoked_before_write;check(MemCreateHeap(1,Heap[2].start+1024,Heap[2].start+2048));break;
   case 2:sdk_before_create=revoked_before_write;check(MemCreateHeap(7,begin,end));break;
   case 3:check(MemDestroyHeap(1)==0);break;
   case 4:check(MemDestroyHeap(2));check(sourceWorldRetained.live);MemClearAllHeap();break;
   case 5:memInitHeapTbl();break;
   case 6:sdk_before_init=revoked_before_write;SystemMemInit();break;
   case 7:MemSuspendHeap(2);check(bucket());Heap[2].start=begin;MemSignalHeap(2);break;
  }
  check(!sourceWorldRetained.live&&re4dc_source_world_ot_epoch()!=observed_epoch);check(!bucket());
 }
 check(observations==4);
 for(unsigned debug=0;debug<2;++debug){game_prefix();observed_epoch=re4dc_source_world_ot_epoch();sdk_before_free=revoked_before_write;
  // Deliberately invalid cross-heap frees probe the conservative pre-write
  // invalidation; ordinary source never frees this frozen game allocation.
  if(debug)Debug_free_h(g_OtWork[0x0b].list,2);else Mem_free_h(g_OtWork[0x0b].list,2);
  check(!sourceWorldRetained.live&&!bucket());}
 check(observations==6);
 // Corrupt publications/links and inaccessible addresses fail before read.
 {GuardPage guard;for(unsigned mutation=0;mutation<12;++mutation){game_prefix();auto* head=sourceWorldRetained.head;
  switch(mutation){
   case 0:sourceWorldRetained.head=static_cast<OSHeapCell*>(guard.p);break;
   case 1:sourceWorldRetained.head=reinterpret_cast<OSHeapCell*>(reinterpret_cast<unsigned char*>(head)+1);break;
   case 2:head->size=32;break;case 3:head->size=-32;break;
   case 4:head->size=0x7fffffe0;break;case 5:head->next=static_cast<OSHeapCell*>(guard.p);break;
   case 6:head->prev=static_cast<OSHeapCell*>(guard.p);break;case 7:head->next=head;break;
   case 8:head->size=int(sourceWorldRetained.end-reinterpret_cast<unsigned long>(head)+32);break;
   case 9:sourceWorldRetained.head=nullptr;break;
   case 10:Heap[7]={7,u32(sourceWorldRetained.begin),u32(sourceWorldRetained.end),0,{}};break;
   case 11:{auto& ot=g_OtWork[0x0b];auto* tag=reinterpret_cast<unsigned char*>(ot.list)+((ot.max*sizeof(OtData)+31)&~31U);tag[1]='X';break;}
  }
  check(!bucket());
 }}
 // An invented readable cell in an actual freed hole is not in the chain.
 begin_game();hole=host_alloc(256);InitOt();OSFreeToHeap(Heap[1].handle,hole);freeze_game();
 auto* fake=static_cast<OSHeapCell*>(hole);std::memset(fake,0,256);fake->size=128;
 reinterpret_cast<unsigned char*>(fake)[96]=0;std::memcpy(reinterpret_cast<unsigned char*>(fake)+97,"MAD",3);
 check(!query_readonly(fake+1,64));
 // Capture validates before the source's unbounded MemCheckHeapEnd walk.
 {GuardPage guard;begin_game();InitOt();HeapHead[Heap[1].handle].allocated->next=static_cast<OSHeapCell*>(guard.p);
  check(!MemReplaceHeap(1,2));check(Heap[1].handle>=0&&!sourceWorldRetained.live);}
 // Empty, failed and reentrant replacement never publish a guessed lifetime.
 begin_game();freeze_game();check(!sourceWorldRetained.live);
 begin_game();InitOt();sdk_fail_create=true;check(!MemReplaceHeap(1,2));check(!sourceWorldRetained.live);
 for(unsigned during=0;during<2;++during){begin_game();InitOt();
  if(during)sdk_before_create=extra_owner_retirement;else sdk_before_destroy=extra_suspend;
  check(MemReplaceHeap(1,2));check(!sourceWorldRetained.live&&!bucket());}
 // The enabled target actor-retirement service is external to this test;
 // reentry from its actual main_mem call site also withdraws the transfer.
 begin_game();InitOt();actor_before_forget=extra_suspend;
 check(MemReplaceHeap(1,2));check(!sourceWorldRetained.live&&!bucket());
 // Same storage is a fresh publication, never the old frame's epoch.
 game_prefix();const auto old_epoch=re4dc_source_world_ot_epoch();check(reinterpret_cast<unsigned long>(g_OtWork[0x0b].list)==first);
 game_prefix();check(reinterpret_cast<unsigned long>(g_OtWork[0x0b].list)==first);
 check(re4dc_source_world_ot_epoch()!=old_epoch&&bucket());
 // Active heap1 OTs also have a lifetime before the retained publication.
 begin_game();InitOt();const auto active_epoch=re4dc_source_world_ot_epoch();
 check(!sourceWorldRetained.live&&sourceWorldAllocated(g_OtWork[0x0b].list,g_OtWork[0x0b].max*sizeof(OtData),true));
 MemSuspendHeap(1);check(re4dc_source_world_ot_epoch()!=active_epoch);
 check(!sourceWorldAllocated(g_OtWork[0x0b].list,g_OtWork[0x0b].max*sizeof(OtData),true));
 MemSignalHeap(1);const auto restored_epoch=re4dc_source_world_ot_epoch();check(restored_epoch!=active_epoch);
 check(MemDestroyHeap(1));check(re4dc_source_world_ot_epoch()!=restored_epoch);
 // Counter wrap cannot accidentally restore zero/unpublished generations.
 sourceWorldRetained.epoch=~0U;check(MemDestroyHeap(1)==0);check(re4dc_source_world_ot_epoch()==1);
 begin_game();InitOt();sourceWorldHeapMutation=~0U;freeze_game();check(bucket());
 check(read_only_queries>100&&rejected_read_only_queries>50);
 std::printf("read-only allocator snapshots: %u queries (%u rejected) unchanged\n",read_only_queries,rejected_read_only_queries);
 std::printf("source retained prefix: %u checks PASS (real OSAlloc/main_mem/InitOt, ASan+UBSan)\n",checks);
}
