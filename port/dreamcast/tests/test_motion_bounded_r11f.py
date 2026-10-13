#!/usr/bin/env python3
"""Private v3 r11f assets through the real native cache/storage and cancellation hooks.

Usage: python3 test_motion_bounded_r11f.py --assets <profiles root> --output <new evidence dir>
The root contains em35-profile/em35.arc, pl11-profile/pl11.arc and their mot/ files.
No game bytes are checked in. All tests run on copies, never the supplied files.
"""
from pathlib import Path
import argparse, hashlib, json, shutil, struct, subprocess
import test_motion_residency as base

FLAGS=['-DRE4DC_MOTION_RESERVE=1','-DRE4DC_MOTION_RESERVE_SPILL=524288',
       '-DRE4DC_MOTION_PRESSURE_BYTES=262144','-DRE4DC_SUBSCREEN=1','-DRE4DC_MOTION_INDEX=1',
       '-DRE4DC_MOTION_LEASE_LEAN=1','-DRE4DC_MOTION_OOM_EVICT=1']
EXTRA=r"""
extern "C" void re4dc_motion_hold(int);
extern "C" unsigned re4dc_motion_forget_dead_heaps();
int current_heap=4,fail_allocation=-1;unsigned allocation_calls,sleep_calls;int io_fault;unsigned fault_reads;
extern "C" int re4dc_static_heap_free(){return 8*1024*1024;}
extern "C" int re4dc_motion_owner_live(const void* p){return allocations.count(const_cast<void*>(p));}
struct Archive {
 unsigned char* a;unsigned bytes,mapped;
 Archive(const char* name){auto b=read_bytes_file(root+"/"+name);bytes=b.size();mapped=(bytes+4095)&~4095u;
  a=(unsigned char*)mmap(nullptr,mapped,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_32BIT,-1,0);
  assert(a!=MAP_FAILED);memcpy(a,b.data(),bytes);}
 ~Archive(){munmap(a,mapped);}
 unsigned mtc()const{return word(a+16+4*(word(a)-1));}
 unsigned count()const{return word(a+mtc()+12);}
 unsigned size(unsigned i)const{return word(a+mtc()+32+i*20+4);}
 void* proxy(unsigned i)const{return a+word(a+mtc()+32+i*20);}
};
void put(unsigned char* p,unsigned at,unsigned v){memcpy(p+at,&v,4);}
int acquire(const Archive& a,unsigned i,unsigned** out){int t=re4dc_motion_acquire(a.proxy(i),out);assert(t);verify_keys(a.proxy(i),*out);return t;}
void visit(const Archive& a,unsigned i){unsigned* t=nullptr;int token=acquire(a,i,&t);re4dc_motion_release(token);}
"""
CHECKS=r"""
int main(int argc,char**argv){
 assert(argc==2);root=argv[1];Archive em("em35.arc"),pl("pl11.arc");
 const auto em_original=read_bytes_file(root+"/em35.arc"),pl_original=read_bytes_file(root+"/pl11.arc");
 for(auto* a:{&em,&pl}){
  for(unsigned test=0;test<13;++test){auto bad=std::vector<unsigned char>(a->a,a->a+a->bytes);unsigned m=a->mtc(),r=word(a->a+4);
   switch(test){case 0:put(bad.data(),m+8,4);break;case 1:put(bad.data(),m+28,65536);break;
    case 2:put(bad.data(),m+12,a->count()-1);break;case 3:put(bad.data(),m+20,0);break;
    case 4:put(bad.data(),r,99);break;case 5:put(bad.data(),r+28,0);break;case 6:put(bad.data(),r+4,1);break;
    case 7:put(bad.data(),m+32+16,1);break;case 8:put(bad.data(),m+32+4,131104);break;
    case 9:put(bad.data(),m+52,word(bad.data()+m+32));break;case 10:put(bad.data(),m+24,a->bytes-32);break;
    case 11:bad[100]^=1;break;case 12:put(bad.data(),m+16,24);break;}
   assert(!re4dc_motion_bind(bad.data(),bad.size()) && !heap_live);
  }
  current_heap=12;assert(!re4dc_motion_bind(a->a,a->bytes));current_heap=4;
  for(int failat=0;failat<3;++failat){allocation_calls=0;fail_allocation=failat;
   assert(!re4dc_motion_bind(a->a,a->bytes));Re4dcMotionStats s{};re4dc_motion_get_stats(&s);assert(!heap_live&&!s.metadata_bytes&&!s.resident_bytes);
  }
  fail_allocation=-1;
 }
 assert(re4dc_motion_bind(em.a,em.bytes));assert(re4dc_motion_bind(pl.a,pl.bytes));
 assert(!re4dc_motion_bind(em.a,em.bytes));
 const unsigned reserved=heap_live;assert(allocations.size()==6);
 unsigned largest=0,second=1;for(unsigned i=0;i<em.count();++i)if(em.size(i)>em.size(largest))largest=i;
 for(unsigned i=0;i<em.count();++i)if(i!=largest&&em.size(i)>em.size(second))second=i;
 assert(em.size(largest)==123008);
 // All exact clips, repeated with ample free heap: six cells remain the only allocations, no spill.
 for(unsigned round=0;round<2;++round){for(unsigned i=0;i<pl.count();++i)visit(pl,i);for(unsigned i=0;i<em.count();++i)visit(em,i);}
 assert(heap_live==reserved&&allocations.size()==6);
 Re4dcMotionStats s{};re4dc_motion_get_stats(&s);assert(s.peak_cache_bytes<=262144);
 // Two large simultaneous leases survive pressure; a third cannot consume a new cell.
 unsigned *one=nullptr,*two=nullptr,*third=nullptr;int x=acquire(em,largest,&one),y=acquire(em,second,&two);bool refused=false;
 try{int z=acquire(em,(largest+1)%em.count(),&third);re4dc_motion_release(z);}catch(const std::runtime_error&){refused=true;}
 assert(refused&&heap_live==reserved);verify_keys(em.proxy(largest),one);verify_keys(em.proxy(second),two);
 re4dc_motion_release(y);re4dc_motion_release(x);assert(!re4dc_motion_thread_busy(thd_current));
 // Suspend every room-owned allocation, including archives and slots, with PROT_NONE.
 re4dc_motion_hold(1);current_heap=12;
 for(const auto& q:allocations)assert(!mprotect(q.first,(q.second+4095)&~4095u,PROT_NONE));
 void* ep=em.proxy(largest);void* pp=pl.proxy(0);
 assert(!mprotect(em.a,em.mapped,PROT_NONE));assert(!mprotect(pl.a,pl.mapped,PROT_NONE));
 unsigned* untouched=(unsigned*)0x1234;assert(!re4dc_motion_acquire(ep,&untouched)&&untouched==(unsigned*)0x1234);
 assert(!re4dc_motion_acquire(pp,&untouched)&&untouched==(unsigned*)0x1234);
 assert(!mprotect(em.a,em.mapped,PROT_READ|PROT_WRITE));assert(!mprotect(pl.a,pl.mapped,PROT_READ|PROT_WRITE));
 for(const auto& q:allocations)assert(!mprotect(q.first,(q.second+4095)&~4095u,PROT_READ|PROT_WRITE));
 current_heap=4;assert(!re4dc_motion_forget_dead_heaps());visit(em,largest);visit(pl,0);
 // Persistent short reads and corrupt files must keep slab ownership; then recover cleanly.
 re4dc_motion_retire_all();assert(!heap_live);assert(re4dc_motion_bind(em.a,em.bytes));unsigned bound=heap_live;
 io_fault=2;refused=false;try{visit(em,largest);}catch(const std::runtime_error&){refused=true;}
 assert(refused&&heap_live==bound&&!re4dc_motion_thread_busy(thd_current));io_fault=0;visit(em,largest);
 // A first read fault is retried by the actual storage/fallback code.
 io_fault=1;visit(em,(largest+1)%em.count());io_fault=0;assert(heap_live==bound&&fault_reads);
 unsigned k=(largest+2)%em.count();auto* row=em.a+em.mtc()+32+20*k;char file[128];
 snprintf(file,sizeof(file),"%s/mot/%08x-%08x.fcv",root.c_str(),word(row+8),word(row+12));auto data=read_bytes_file(file);
 {auto bad=data;bad.back()^=1;std::ofstream f(file,std::ios::binary);f.write((char*)bad.data(),bad.size());}
 refused=false;try{visit(em,k);}catch(const std::runtime_error&){refused=true;}assert(refused&&heap_live==bound);
 {std::ofstream f(file,std::ios::binary);f.write((char*)data.data(),data.size());}visit(em,k);
 // A genuinely truncated key is retried and refused, with the same six/three-cell ownership bound.
 k=(k+1)%em.count();row=em.a+em.mtc()+32+20*k;snprintf(file,sizeof(file),"%s/mot/%08x-%08x.fcv",root.c_str(),word(row+8),word(row+12));data=read_bytes_file(file);
 {std::ofstream f(file,std::ios::binary);f.write((char*)data.data(),data.size()-32);}
 refused=false;try{visit(em,k);}catch(const std::runtime_error&){refused=true;}assert(refused&&heap_live==bound);
 {std::ofstream f(file,std::ios::binary);f.write((char*)data.data(),data.size());}visit(em,k);
 re4dc_motion_get_stats(&s);re4dc_motion_retire_all();assert(!heap_live&&allocations.empty());
 assert(!memcmp(em.a,em_original.data(),em.bytes)&&!memcmp(pl.a,pl_original.data(),pl.bytes));
 printf("{\"clips\":151,\"largest_read\":123008,\"cells_bound\":6,\"host_reserved_bytes\":%u,\"peak_payload\":%u,\"peak_pinned\":%u,\"evictions\":%u,\"loads\":%u,\"fault_reads\":%u,\"hold_prot_none\":true}\n",reserved,s.peak_cache_bytes,s.peak_pinned_bytes,s.evictions,s.loads,fault_reads);
}
"""

CANCEL_SETUP=r"""
constexpr int STATE_WAIT=3,STATE_READY=1,OS_THREAD_STATE_MORIBUND=8;
struct NativeThread { int state=STATE_WAIT;void* wait_obj; };
struct OSThread { NativeThread* kt;int suspend=1,gateCount=1,state=0;unsigned nativeIoDepth=0; };
int g_gate;std::atomic<bool> destroyed{};unsigned unparks;
constexpr int TASK_NONE=0,TASK_EXEC=1,TASK_SLEEP=2,TASK_RUN=3,TASK_SUSPEND=128;
struct TASK { OSThread Thread;int Status=TASK_RUN,suspend_cnt=0; };
OSThread current_thread{};unsigned self_exits;
OSThread* OSGetCurrentThread(){return &current_thread;}
void TaskExit(){++self_exits;}
void unpark(OSThread* t){++unparks;t->kt->state=STATE_READY;}
void thd_add_to_runnable(NativeThread*,bool){}
void thd_destroy(NativeThread* t){assert(irq_depth&&!re4dc_motion_thread_busy(t));destroyed=true;}
"""
CANCEL_MAIN=r"""
int main(int argc,char**argv){
 assert(argc==2);root=argv[1];Archive em("em35.arc");assert(re4dc_motion_bind(em.a,em.bytes));
 unsigned largest=0;for(unsigned i=0;i<em.count();++i)if(em.size(i)>em.size(largest))largest=i;
 for(unsigned phase=0;phase<3;++phase){
  NativeThread native{STATE_WAIT,&g_gate};TASK task{{&native}};auto& target=task.Thread;
  destroyed=false;block_read=true;read_entered=false;let_read_finish=false;std::atomic<bool> pinned{},finish{},verified{};
  unsigned* blocker=nullptr;int blocktoken=0;
  std::thread owner;
  if(phase==2){ // another owner holds the loader mutex in I/O while the cancelled owner waits for it
   owner=std::thread([&]{thd_current=(void*)3;visit(em,(largest+1)%em.count());});
   while(!read_entered)std::this_thread::yield();
  }
  std::thread worker([&]{thd_current=&native;unsigned* t=nullptr;int token=acquire(em,largest,&t);pinned=true;
   while(!finish)std::this_thread::yield();assert(!destroyed);verify_keys(em.proxy(largest),t);verified=true;re4dc_motion_release(token);});
  if(phase<2){while(!read_entered)std::this_thread::yield();}
  while(!re4dc_motion_thread_busy(&native))std::this_thread::yield();
  if(phase==1){let_read_finish=true;while(!pinned)std::this_thread::yield();}
  std::thread completion([&]{std::this_thread::sleep_for(std::chrono::milliseconds(5));assert(!destroyed);let_read_finish=true;finish=true;});
  TaskKill(&task);worker.join();completion.join();if(owner.joinable())owner.join();
  assert(verified&&destroyed&&!target.kt&&!self_exits&&task.Status==TASK_NONE);
  block_read=false;re4dc_motion_unbind(em.a);assert(!heap_live);assert(re4dc_motion_bind(em.a,em.bytes));
 }
 re4dc_motion_retire_all();assert(!heap_live);puts("{\"actual_cancel_read_pin_mutex\":true}");
}
"""

def compile_test(out, main, fast=False, bounded=True):
    out.mkdir();base.headers(out)
    p=out/'kos/fs.h';p.write_text(p.read_text()+'off_t fs_seek(int,off_t,int);\n')
    support=base.SUPPORT.replace('extern "C" int re4dc_motion_current_heap(){return 4;}',
        'extern int current_heap,fail_allocation,io_fault;extern unsigned allocation_calls,fault_reads;\nextern "C" int re4dc_motion_current_heap(){return current_heap;}')
    support=support.replace('extern "C" void* re4dc_motion_alloc(unsigned n){',
        'extern "C" void* re4dc_motion_alloc(unsigned n){if(int(allocation_calls++)==fail_allocation)return nullptr;')
    support=support.replace('auto got=read(f,p,n);','if(io_fault){++fault_reads;if(io_fault==1)io_fault=0;return 0;}\n auto got=read(f,p,n);')
    support+='\noff_t fs_seek(int f,off_t p,int w){return lseek(f,p,w);}\n'
    src=out/'check.cpp';src.write_text(support+EXTRA+main);exe=out/'check'
    flags=FLAGS+(['-DRE4DC_MOTION_BOUNDED_R11F=1'] if bounded else [])+(['-DRE4DC_MOTION_FAST_READ=1'] if fast else [])
    cc=['g++','-std=c++20','-O2','-pthread','-fno-pie','-no-pie','-I'+str(out),'-I'+str(base.ROOT/'port/dreamcast/game/platform/include'),str(src),str(base.ROOT/'port/dreamcast/game/platform/native_motion.cpp'),str(base.ROOT/'port/dreamcast/room/room_storage.cpp'),*flags,'-lz','-o',str(exe)]
    r=subprocess.run(cc,capture_output=True,text=True)
    if r.returncode:raise RuntimeError(r.stderr)
    return exe

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--assets',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.mkdir();data=a.output/'assets';data.mkdir();(data/'mot').mkdir()
    for name in ['em35','pl11']:
        shutil.copyfile(a.assets/(name+'-profile')/(name+'.arc'),data/(name+'.arc'))
        for f in (a.assets/(name+'-profile')/'mot').glob('*.fcv'):
            dst=data/'mot'/f.name
            if dst.exists():assert dst.read_bytes()==f.read_bytes()
            else:shutil.copyfile(f,dst)
    reports={}
    for fast in [False,True]:
        exe=compile_test(a.output/('fast' if fast else 'storage'),CHECKS,fast=fast)
        r=subprocess.run([str(exe),str(data)],capture_output=True,text=True,timeout=60)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
        reports['fast' if fast else 'storage']=json.loads(r.stdout)
    source=(base.ROOT/'port/dreamcast/game/platform/os.cpp').read_text();start=source.index('void OSCancelThread(OSThread* thread)');hook=source[start:source.index('\nOSPriority OSGetThreadPriority',start)]
    source=(base.ROOT/'src/game/scheduler.cpp').read_text();start=source.index('void TaskKill(TASK* t)\n{');kill=source[start:source.index('\n// Suspends slot',start)]
    exe=compile_test(a.output/'cancel','#define RE4DC_GAME 1\n'+CANCEL_SETUP+hook+kill+CANCEL_MAIN)
    r=subprocess.run([str(exe),str(data)],check=True,capture_output=True,text=True,timeout=60);reports['cancel']=json.loads(r.stdout)
    (a.output/'results.json').write_text(json.dumps(reports,indent=2)+'\n');print(json.dumps(reports,indent=2))
if __name__=='__main__':main()
