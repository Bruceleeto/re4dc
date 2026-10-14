#include "../game/platform/aica_bank_v2_host.h"
#include <algorithm>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
using namespace re4dc_aic2;
namespace {
unsigned checks=0;
void check(bool ok,const char* expression,int line) {
 ++checks;
 if(!ok) { std::ostringstream s;s<<"line "<<line<<": "<<expression;throw std::runtime_error(s.str()); }
}
#define CHECK(x) check((x),#x,__LINE__)
#define OK(x) CHECK((x)==Result::Ok)
#define IS(x,y) CHECK((x)==Result::y)
void sound(Core& c) { CHECK(c.invariant()); }
struct Map { uint32_t gc,length,shift,extent,offset; };
struct Bank { uint32_t index,slot,bytes,count,local,shared;std::vector<Map> maps; };
struct Room { std::string name;std::vector<unsigned> base,actors;int bgm[2]; };
std::vector<Bank> banks;std::vector<Room> rooms;std::vector<uint8_t> sample,resident_sample;
SharedInput share() {
 SharedInput s{};s.bytes=kSharedBytes;s.incoming=sample.data();s.resident_readback=resident_sample.data();
 const uint8_t hash[32]={0xd2,0x24,0xdd,0x18,0x5b,0xd1,0x85,0x6c,0xec,0x5e,0x31,0x57,0xc9,0xbc,0x69,0xba,0x57,0xde,0x39,0xdd,0xbc,0x82,0xa0,0x46,0x20,0x70,0xaa,0xa8,0x53,0x9f,0xd4,0xb5};
 std::copy(hash,hash+32,s.sha);return s;
}
void load(const std::string& path) {
 std::ifstream f(path+"/banks.txt");unsigned count=0;f>>count;CHECK(count==30);
 for(unsigned i=0;i<count;++i) {
  Bank b{};f>>b.index>>b.slot>>b.bytes>>b.count>>b.local>>b.shared;CHECK(b.index==i);
  for(unsigned j=0;j<b.count;++j){Map m{};f>>m.gc>>m.length>>m.shift>>m.extent>>m.offset;b.maps.push_back(m);}
  CHECK(bool(f));banks.push_back(b);
 }
 std::ifstream g(path+"/rooms.txt");g>>count;CHECK(count==6);
 for(unsigned i=0;i<count;++i) {Room r;unsigned n,a;g>>r.name>>n>>a>>r.bgm[0]>>r.bgm[1];
  for(unsigned j=0,x;j<n;++j){g>>x;r.base.push_back(x);}for(unsigned j=0,x;j<a;++j){g>>x;r.actors.push_back(x);}
  CHECK(bool(g));rooms.push_back(r);
 }
 std::ifstream h(path+"/shared.bin",std::ios::binary);sample.assign(std::istreambuf_iterator<char>(h),{});CHECK(sample.size()==kSharedBytes);resident_sample=sample;CHECK(sample.data()!=resident_sample.data());
}
Token reserve_simple(Core& c,unsigned owner=1,unsigned slot=5,unsigned bytes=32,unsigned maps=1) {
 Token t;OK(c.begin(owner,slot,bytes,t));OK(c.reserve(t,maps,bytes));
 const auto* e=c.extent(c.inspect(t)->local_extent);CHECK(e);
 for(unsigned i=0;i<maps;++i)OK(c.set_map(t,i,{i*64,8,0x80000000u|e->base}));
 sound(c);return t;
}
Token publish_simple(Core& c,unsigned owner=1,unsigned slot=5,unsigned bytes=32,unsigned maps=1) {
 Token t=reserve_simple(c,owner,slot,bytes,maps);OK(c.feed(owner,t,0,bytes));OK(c.verify(owner,t,true));OK(c.publish(owner,t));
 sound(c);return t;
}
uint32_t address(Core& c,Token t) {const auto* g=c.inspect(t);CHECK(g);const auto* e=c.extent(g->local_extent);CHECK(e);return e->base;}
Token publish_fixture(Core& c,unsigned index,unsigned slot) {
 const Bank& b=banks.at(index);Token t;unsigned owner=100+slot;OK(c.begin(owner,slot,b.bytes,t));SharedInput s=share();
 OK(c.reserve(t,b.count,b.local,b.shared?&s:nullptr));const Generation* g=c.inspect(t);CHECK(g);
 for(unsigned i=0;i<b.count;++i){const Map& m=b.maps[i];const Extent* e=c.extent(m.extent?g->shared_extent:g->local_extent);CHECK(e);OK(c.set_map(t,i,{m.gc,m.length,0x80000000u|(m.shift<<24)|(e->base+m.offset)}));}
 LogicalMap unavailable{};IS(c.resolve(t,0,unavailable),State);IS(c.publish(owner,t),State);
 for(unsigned off=0;off<b.bytes;){unsigned n=std::min(131072u,b.bytes-off);OK(c.copy_begin(t));OK(c.feed(owner,t,off,n));IS(c.verify(owner,t,true),Busy);OK(c.copy_end(t));off+=n;}
 OK(c.verify(owner,t,true));OK(c.publish(owner,t));CHECK(equal(c.current(slot),t));
 for(unsigned i=0;i<b.count;++i){LogicalMap m{};OK(c.resolve(t,i,m));CHECK(m.gc_nibble==b.maps[i].gc);CHECK(m.length==b.maps[i].length);CHECK(((m.aica_shift>>24)&3)==b.maps[i].shift);}
 sound(c);return t;
}
Ack ack_for(const Request& r,unsigned boot=1) {return {r.sequence,r.epoch,r.lease,boot,0,3};}
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
void owner_chunk_tests() {
 Core c(4096);Token old=reserve_simple(c,7,5,513);CHECK(c.pool().free_bytes()==3552);Token unused;
 IS(c.begin(7,5,32,unused),Busy);IS(c.feed(8,old,0,1),Stale);IS(c.feed(7,old,1,1),Invalid);IS(c.feed(7,old,0,514),Invalid);IS(c.feed(7,old,0,0),Invalid);
 OK(c.copy_begin(old));OK(c.feed(7,old,0,128));OK(c.cancel(7,old));CHECK(c.inspect(old)&&c.pool().free_bytes()==3552);CHECK(c.owners_used()==0);
 Token fresh=reserve_simple(c,7,5,32);CHECK(!equal(old,fresh));IS(c.feed(7,old,128,1),Stale);IS(c.cancel(7,old),Stale);OK(c.copy_end(old));CHECK(!c.inspect(old));IS(c.copy_end(old),Stale);
 OK(c.feed(7,fresh,0,32));OK(c.copy_begin(fresh));IS(c.verify(7,fresh,true),Busy);IS(c.publish(7,fresh),State);OK(c.copy_end(fresh));IS(c.copy_end(fresh),State);OK(c.verify(7,fresh,true));OK(c.publish(7,fresh));CHECK(c.owners_used()==0);IS(c.cancel(7,fresh),Stale);sound(c);
 Token next=reserve_simple(c,7,5);OK(c.feed(7,next,0,32));OK(c.verify(7,next,true));IS(c.publish(7,next),Busy);CHECK(equal(c.current(5),fresh));OK(c.retire_bank(fresh));OK(c.publish(7,next));CHECK(equal(c.current(5),next));OK(c.retire_bank(next));CHECK(c.pool().free_bytes()==4096);
 Token bad=reserve_simple(c);OK(c.feed(1,bad,0,32));IS(c.verify(1,bad,false),Invalid);CHECK(!c.inspect(bad)&&c.pool().free_bytes()==4096);sound(c);
 // Every split of a non-aligned part goes through the actual owner state machine.
 for(unsigned cut=1;cut<513;++cut){Token t=reserve_simple(c,8,6,513);OK(c.feed(8,t,0,cut));IS(c.verify(8,t,true),Busy);OK(c.feed(8,t,cut,513-cut));OK(c.verify(8,t,true));OK(c.publish(8,t));OK(c.retire_bank(t));sound(c);}
}
void capacity_tests() {
 Core oversize(kMixedBytes+32);Token invalid;CHECK(oversize.faulted());IS(oversize.begin(1,5,32,invalid),Faulted);
 Core bad_epoch(32,{0,0},1);CHECK(bad_epoch.faulted());Core bad_boot(32,{1,0},0);CHECK(bad_boot.faulted());
 Core c(65536);IS(c.begin(0,5,32,invalid),Invalid);IS(c.begin(1,14,32,invalid),Invalid);IS(c.begin(1,5,0,invalid),Invalid);std::vector<Token> tokens;
 for(unsigned i=0;i<16;++i){Token t;OK(c.begin(i+1,5,32,t));tokens.push_back(t);}Token extra;IS(c.begin(17,5,32,extra),Capacity);
 for(unsigned i=0;i<16;++i)OK(c.cancel(i+1,tokens[i]));
 CHECK(c.active_generations()==0);
 Token large=reserve_simple(c,1,5,32,512),small=reserve_simple(c,2,6,32,128);OK(c.begin(3,7,32,extra));IS(c.reserve(extra,1,32),Capacity);CHECK(c.maps_used()==640);OK(c.cancel(3,extra));OK(c.cancel(1,large));OK(c.cancel(2,small));
 OK(c.begin(1,5,32,extra));IS(c.reserve(extra,513,32),Capacity);IS(c.reserve(extra,0,32),Capacity);IS(c.reserve(extra,1,0xffffffffu),Overflow);IS(c.reserve(extra,1,65568),NoSpace);CHECK(c.pool().free_bytes()==65536);OK(c.cancel(1,extra));
 tokens.clear();
 for(unsigned i=0;i<32;++i){Token t=publish_simple(c,1,5);OK(c.pin_pending(t));OK(c.retire_bank(t));tokens.push_back(t);}
 IS(c.begin(1,5,32,extra),Capacity);CHECK(c.active_generations()==32);for(Token t:tokens)OK(c.drop_pending(t));CHECK(c.active_generations()==0&&c.pool().free_bytes()==65536);
 Token t=reserve_simple(c);uint32_t addr=address(c,t);IS(c.set_map(t,0,{0,0,0x80000000u|addr}),Invalid);IS(c.set_map(t,1,{0,8,0x80000000u|addr}),Invalid);IS(c.set_map(t,0,{0,8,addr}),Invalid);IS(c.set_map(t,0,{0,8,0xfc000000u|addr}),Invalid);IS(c.set_map(t,0,{0,1000,0x80000000u|addr}),Invalid);OK(c.cancel(1,t));sound(c);
}
void shared_tests() {
 for(bool reverse:{false,true}) {
  Core c;unsigned a=reverse?20:19,b=reverse?19:20;Token x=publish_fixture(c,a,3),y=publish_fixture(c,b,4);
  const Generation gx=*c.inspect(x),gy=*c.inspect(y);CHECK(gx.shared_extent==gy.shared_extent);CHECK(c.extent(gx.shared_extent)->refs==2);
  uint32_t expected=((banks[a].local+31)&~31u)+((banks[b].local+31)&~31u)+kSharedBytes;CHECK(c.pool().free_bytes()==kMixedBytes-expected);
  OK(c.retire_bank(x));CHECK(c.extent(gy.shared_extent)->refs==1);OK(c.retire_bank(y));CHECK(c.pool().free_bytes()==kMixedBytes);sound(c);
 }
 Core c;Token x=publish_fixture(c,19,3);Token t;OK(c.begin(91,4,64,t));SharedInput s=share();std::vector<uint8_t> wrong=sample;wrong.back()^=1;s.incoming=wrong.data();uint32_t free=c.pool().free_bytes();
 IS(c.reserve(t,1,32,&s),Collision);CHECK(c.pool().free_bytes()==free);s=share();s.resident_readback=nullptr;IS(c.reserve(t,1,32,&s),Collision);s=share();s.sha[31]^=1;IS(c.reserve(t,1,32,&s),Invalid);OK(c.cancel(91,t));
 OK(c.begin(91,5,64,t));s=share();IS(c.reserve(t,1,32,&s),Invalid);OK(c.cancel(91,t));OK(c.retire_bank(x));sound(c);
 Core tiny(27040);OK(tiny.begin(1,3,64,t));s=share();IS(tiny.reserve(t,1,32,&s),NoSpace);CHECK(tiny.pool().free_bytes()==27040&&tiny.invariant());OK(tiny.cancel(1,t));
}
void fences_tests() {
 Core c(4096);Token a=publish_simple(c),lease;uint32_t addr=address(c,a);IS(c.start_channel(0,a,addr,lease),State);OK(c.pin_pending(a));OK(c.start_channel(0,a,addr,lease));CHECK(c.inspect(a)->hardware_refs==1&&c.inspect(a)->pending_refs==0);
 OK(c.retire_bank(a));CHECK(!nonzero(c.current(5).serial));CHECK(c.inspect(a)&&c.pool().free_bytes()==4064);Request r;OK(c.retire_channel(0,lease,r));Request repeat;OK(c.retire_channel(0,lease,repeat));CHECK(repeat.sequence==r.sequence);
 Ack ack=ack_for(r);Ack bad=ack;bad.sequence|=1;IS(c.acknowledge(0,bad),Stale);bad=ack;bad.epoch.lo++;IS(c.acknowledge(0,bad),Stale);bad=ack;bad.lease.lo++;IS(c.acknowledge(0,bad),Stale);bad=ack;bad.boot_serial++;IS(c.acknowledge(0,bad),Stale);bad=ack;bad.flags=1;bad.observed_eg=0xffffffffu;IS(c.acknowledge(0,bad),Stale);
 CHECK(c.inspect(a)->hardware_refs==1&&c.pool().free_bytes()==4064);ack.observed_eg=0;OK(c.acknowledge(0,ack));CHECK(!c.inspect(a)&&c.pool().free_bytes()==4096);IS(c.acknowledge(0,ack),Stale);sound(c);
 // Same-generation physical channel reuse transfers its pin and invalidates old acknowledgements.
 a=publish_simple(c);addr=address(c,a);OK(c.pin_pending(a));OK(c.start_channel(0,a,addr,lease));OK(c.retire_channel(0,lease,r));Ack old=ack_for(r);OK(c.pin_pending(a));Token newer;OK(c.reuse_same_generation(0,lease,a,addr,newer));CHECK(!equal(lease,newer));CHECK(c.inspect(a)->hardware_refs==1);IS(c.acknowledge(0,old),Stale);IS(c.retire_channel(0,lease,r),Stale);
 Token b=publish_simple(c,2,6);OK(c.pin_pending(b));IS(c.reuse_same_generation(0,newer,b,address(c,b),lease),Busy);IS(c.start_channel(0,b,address(c,b),lease),Busy);CHECK(c.inspect(b)->pending_refs==1);OK(c.retire_channel(0,newer,r));OK(c.acknowledge(0,ack_for(r)));OK(c.start_channel(0,b,address(c,b),lease));OK(c.retire_bank(a));OK(c.retire_bank(b));CHECK(c.inspect(b));
 OK(c.retire_channel(0,lease,r));old=ack_for(r);uint32_t retained=c.pool().free_bytes();IS(c.observe_boot(2),Faulted);CHECK(c.pool().free_bytes()==retained&&c.inspect(b));IS(c.acknowledge(0,old),Faulted);IS(c.controlled_reset({2,0},2,false),Invalid);OK(c.controlled_reset({2,0},2,true));CHECK(c.pool().free_bytes()==4096&&!c.faulted());IS(c.acknowledge(0,old),Stale);IS(c.retire_bank(b),Stale);IS(c.controlled_reset({2,0},2,true),Invalid);
 a=publish_simple(c);OK(c.pin_pending(a));OK(c.start_channel(0,a,address(c,a),newer));OK(c.retire_channel(0,newer,r));IS(c.acknowledge(0,old),Stale);OK(c.acknowledge(0,ack_for(r,2)));OK(c.retire_bank(a));sound(c);
 a=reserve_simple(c);OK(c.copy_begin(a));IS(c.controlled_reset({3,0},3,true),Busy);OK(c.cancel(1,a));IS(c.controlled_reset({3,0},3,true),Busy);OK(c.copy_end(a));OK(c.controlled_reset({3,0},3,true));
 a=publish_simple(c);OK(c.pin_pending(a));IS(c.controlled_reset({4,0},4,true),Busy);OK(c.drop_pending(a));OK(c.controlled_reset({4,0},4,true));sound(c);
 Core full;Token f=publish_simple(full);std::vector<Token> leases;
 for(unsigned ch=0;ch<64;++ch){OK(full.pin_pending(f));Token l;OK(full.start_channel(ch,f,address(full,f),l));leases.push_back(l);}CHECK(full.inspect(f)->hardware_refs==64);OK(full.pin_pending(f));IS(full.start_channel(64,f,address(full,f),lease),Invalid);OK(full.drop_pending(f));OK(full.retire_bank(f));
 for(unsigned ch=0;ch<64;++ch){OK(full.retire_channel(ch,leases[ch],r));OK(full.acknowledge(ch,ack_for(r)));}CHECK(full.pool().free_bytes()==kMixedBytes&&full.active_generations()==0);sound(full);
}
struct Live {Core core;std::vector<Token> room,actors;Token music[2]{};int music_id[2]={-1,-1};};
void drain_bank(Core& c,Token t,unsigned ch) {
 OK(c.pin_pending(t));Token lease;OK(c.start_channel(ch,t,address(c,t),lease));OK(c.retire_bank(t));Request r;OK(c.retire_channel(ch,lease,r));uint32_t free=c.pool().free_bytes();
 for(unsigned delay=0;delay<3;++delay){Ack stale=ack_for(r);stale.lease.lo+=delay+1;IS(c.acknowledge(ch,stale),Stale);CHECK(c.pool().free_bytes()==free);sound(c);}
 OK(c.acknowledge(ch,ack_for(r)));sound(c);
}
void enter(Live& live,const Room& room,bool reverse) {
 Core& c=live.core;for(Token t:live.actors)drain_bank(c,t,0);live.actors.clear();for(Token t:live.room)drain_bank(c,t,1);live.room.clear();
 for(unsigned i:room.base)live.room.push_back(publish_fixture(c,i,banks[i].slot));
 for(unsigned which=0;which<2;++which){int idx=room.bgm[which];if(which==0&&idx==live.music_id[which])continue;
  if(live.music_id[which]>=0)drain_bank(c,live.music[which],2+which);
  live.music_id[which]=-1;
  if(idx>=0){live.music[which]=publish_fixture(c,static_cast<unsigned>(idx),3+which);live.music_id[which]=idx;}
 }
 auto order=room.actors;if(reverse)std::reverse(order.begin(),order.end());
 for(unsigned i=0;i<order.size();++i)live.actors.push_back(publish_fixture(c,order[i],8+i));
 sound(c);
}
void schedule_tests() {
 const unsigned margins[6]={237728,98752,611648,2688,259808,5248};
 std::cout<<"\"cold_rooms\":[";
 for(unsigned i=0;i<6;++i){Live live;enter(live,rooms[i],false);CHECK(live.core.pool().free_bytes()==margins[i]);if(i)std::cout<<',';
  std::cout<<"{\"room\":\""<<rooms[i].name<<"\",\"free\":"<<live.core.pool().free_bytes()<<",\"largest\":"<<live.core.pool().largest_free()<<",\"maps\":"<<live.core.maps_used()<<"}";
 }
 std::cout<<"],";
 unsigned transitions=0;
 for(unsigned from=0;from<6;++from)for(unsigned to=0;to<6;++to)for(bool reverse:{false,true}) {
  Live live;enter(live,rooms[from],reverse);enter(live,rooms[to],!reverse);CHECK(live.core.pool().free_bytes()==margins[to]);++transitions;
 }
 for(unsigned from=0;from<6;++from)for(unsigned to=0;to<6;++to) {
  Live live;for(unsigned j=0;j<20;++j){unsigned i=j%2?to:from;enter(live,rooms[i],(j&2)!=0);CHECK(live.core.pool().free_bytes()==margins[i]);if(j)++transitions;}
 }
 std::cout<<"\"transitions\":"<<transitions<<',';
}
}
int main(int argc,char** argv) {
 try {CHECK(argc==2);load(argv[1]);pool_tests();owner_chunk_tests();capacity_tests();shared_tests();fences_tests();std::cout<<'{';schedule_tests();
  std::cout<<"\"checks\":"<<checks<<",\"metadata_bytes\":"<<Core::metadata_bytes()<<",\"pool_bytes\":"<<sizeof(Pool)<<",\"host_only\":true,\"hardware_inactivity_qualified\":false}\n";return 0;
 } catch(const std::exception& e){std::cerr<<"FAIL: "<<e.what()<<'\n';return 1;}
}
