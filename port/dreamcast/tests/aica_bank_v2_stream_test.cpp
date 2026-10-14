#include "../game/platform/aica_bank_v2_stream.h"
#include <algorithm>
#include <cstring>
#include <fstream>
#include <functional>
#include <iostream>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
using namespace re4dc_aic2;
namespace {
uint64_t checks=0;uint32_t passed_cases=0;
void check(bool ok,const char* expression,int line){++checks;if(!ok){std::ostringstream s;s<<"line "<<line<<": "<<expression;throw std::runtime_error(s.str());}}
#define CHECK(x) check((x),#x,__LINE__)
#define OK(x) CHECK((x)==Result::Ok)
#define IS(x,y) CHECK((x)==Result::y)
uint32_t u32(const uint8_t* p){return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24);}
void le(std::vector<uint8_t>& v,uint32_t at,uint32_t n){CHECK(at+4<=v.size());for(uint32_t i=0;i<4;++i)v[at+i]=n>>(8*i);}
void sha(const uint8_t* p,uint32_t n,uint8_t* out){Sha256 hash;hash.reset();hash.update(p,n);hash.finish(out);}
std::vector<uint8_t> bytes(const std::string& path){std::ifstream f(path,std::ios::binary);CHECK(bool(f));return std::vector<uint8_t>(std::istreambuf_iterator<char>(f),{});}
struct Map {uint32_t gc,length,shift,extent,offset;};
struct Bank {uint32_t index,slot,bytes,count,local,shared;Profile profile{};std::vector<Map> maps;std::vector<uint8_t> blob,mram,table,logical;};
struct Room {std::string name;std::vector<unsigned> base,actors;int bgm[2];};
std::vector<Bank> banks;std::vector<Room> rooms;
void load_fixtures(const std::string& root,const std::string& profiles){
    std::ifstream f(root+"/banks.txt");unsigned count;f>>count;CHECK(count==30);banks.reserve(count);
    auto pp=bytes(profiles);CHECK(pp.size()==count*sizeof(Profile));
    for(unsigned i=0;i<count;++i){
        Bank b{};f>>b.index>>b.slot>>b.bytes>>b.count>>b.local>>b.shared;CHECK(b.index==i);
        for(unsigned j=0;j<b.count;++j){Map m{};f>>m.gc>>m.length>>m.shift>>m.extent>>m.offset;b.maps.push_back(m);}CHECK(bool(f));
        char name[20];snprintf(name,sizeof(name),"/%03u",i);std::string prefix=root+name;
        b.blob=bytes(prefix+".aic2");b.mram=bytes(prefix+".mram");b.table=bytes(prefix+".table");b.logical=bytes(prefix+".logical");
        memcpy(&b.profile,pp.data()+sizeof(Profile)*i,sizeof(Profile));CHECK(b.bytes==b.blob.size());banks.push_back(std::move(b));
    }
    std::ifstream g(root+"/rooms.txt");g>>count;CHECK(count==6);
    for(unsigned i=0;i<count;++i){Room r;unsigned n,a;g>>r.name>>n>>a>>r.bgm[0]>>r.bgm[1];for(unsigned j=0,x;j<n;++j){g>>x;r.base.push_back(x);}for(unsigned j=0,x;j<a;++j){g>>x;r.actors.push_back(x);}CHECK(bool(g));rooms.push_back(r);}
}
void stamp(std::vector<uint8_t>& blob){
    uint32_t end=u32(blob.data()+48);CHECK(end<=blob.size());uint8_t digest[32];std::fill(blob.begin()+160,blob.begin()+192,0);sha(blob.data(),end,digest);memcpy(blob.data()+160,digest,32);
}
Bank compact(uint32_t count=2){
    Bank b{};b.slot=5;b.count=count;b.bytes=192+64*count+64+((count*8+31)&~31u)+97;b.local=count*8;
    b.mram.assign(20+24+16*count+46,0);le(b.mram,0,4);le(b.mram,4,1);le(b.mram,8,16);
    for(uint32_t at=20;at<=36;at+=4){le(b.mram,at,24);}
    le(b.mram,40,24+16*count);
    b.logical.resize(b.local);for(uint32_t i=0;i<b.local;++i)b.logical[i]=static_cast<uint8_t>(3+i*7);
    for(uint32_t i=0;i<count;++i){uint32_t at=44+16*i;le(b.mram,at,16000u<<16);le(b.mram,at+4,32*i);le(b.mram,at+8,16);b.maps.push_back({32*i,16,0,0,i*8});}
    b.table.assign(b.mram.begin()+44,b.mram.begin()+44+16*count);
    Profile& p=b.profile;p.source_class=5;p.id=77;p.cap_hz=32000;p.gc_bytes=b.bytes;p.mram_bytes=b.mram.size();p.count=count;p.logical_bytes=b.local;p.policy=0;
    sha(b.mram.data(),b.mram.size(),p.mram_sha);sha(b.table.data(),b.table.size(),p.table_sha);sha(b.logical.data(),b.logical.size(),p.logical_sha);
    b.blob.assign(b.bytes,0);uint32_t extent=192+64*count,data=extent+64,stored=(b.local+31)&~31u;
    le(b.blob,0,0x32434941);le(b.blob,4,(192u<<16)|2);le(b.blob,8,0x12345678);le(b.blob,16,5);le(b.blob,20,count);le(b.blob,24,64);le(b.blob,28,1);le(b.blob,32,64);le(b.blob,36,b.local);le(b.blob,40,192);le(b.blob,44,extent);le(b.blob,48,data);le(b.blob,52,data+stored);le(b.blob,56,b.bytes);le(b.blob,60,77);
    memcpy(b.blob.data()+64,p.mram_sha,32);memcpy(b.blob.data()+96,p.table_sha,32);memcpy(b.blob.data()+128,p.logical_sha,32);
    for(uint32_t i=0;i<count;++i){uint32_t at=192+64*i;le(b.blob,at,32*i);le(b.blob,at+4,16);le(b.blob,at+8,i*8);le(b.blob,at+12,8);le(b.blob,at+24,i*8);sha(b.logical.data()+i*8,8,b.blob.data()+at+32);}
    le(b.blob,extent,1);le(b.blob,extent+4,data);le(b.blob,extent+8,b.local);le(b.blob,extent+12,stored);memcpy(b.blob.data()+extent+32,p.logical_sha,32);memcpy(b.blob.data()+data,b.logical.data(),b.local);stamp(b.blob);return b;
}
struct Physical final:PhysicalAdapter {
    uint32_t base;std::vector<uint8_t> ram;uint64_t writes=0,reads=0,write_bytes=0,read_bytes=0;uint32_t max_packet=0,wrong_origin=0,short_copy=0,wrong_access=0;
    std::function<void(bool,uint32_t,uint32_t)> hook;
    explicit Physical(uint32_t origin=0x30000):base(origin),ram(kArenaBytes,0xcd){}
    PhysicalResult action(bool write,uint32_t address,uint8_t* out,const uint8_t* in,uint32_t n){
        CHECK(address>=base);CHECK(n&&n<=4096&&!(n&3)&&!(address&3));CHECK(address-base<=ram.size()&&n<=ram.size()-(address-base));max_packet=std::max(max_packet,n);
        if(write){++writes;write_bytes+=n;memcpy(ram.data()+address-base,in,n);}else{++reads;read_bytes+=n;memcpy(out,ram.data()+address-base,n);}
        if(hook){auto saved=hook;hook={};saved(write,address,n);}
        return {address+(wrong_origin?4u:0u),n-(short_copy?4u:0u),(write?1u:0u)^wrong_access};
    }
    PhysicalResult read(uint32_t a,uint8_t* p,uint32_t n)override{return action(false,a,p,nullptr,n);}
    PhysicalResult write(uint32_t a,const uint8_t* p,uint32_t n)override{return action(true,a,nullptr,p,n);}
};
struct Live {
    Core core;Physical physical;Engine engine;std::vector<Token> room,actors,fixed;Token music[2]{};int music_id[2]={-1,-1};uint32_t wire[64]{};
    explicit Live(uint32_t mixed=kMixedBytes,uint32_t base=0x30000):core(mixed,{1,0},1,base),physical(base),engine(core,physical){}
};
Result piece(Live& live,uint32_t owner,Token t,const std::vector<uint8_t>& blob,uint32_t at,uint32_t n,uint32_t& consumed){return live.engine.feed(owner,t,at,blob.data()+at,n,n,consumed);}
Result rest(Live& live,uint32_t owner,Token t,const std::vector<uint8_t>& blob,uint32_t at=0,uint32_t fragment=0x20000){
    while(at<blob.size()){uint32_t n=std::min(fragment,static_cast<uint32_t>(blob.size())-at),used=0;Result r=piece(live,owner,t,blob,at,n,used);at+=used;if(r!=Result::Ok)return r;CHECK(used==n);}return Result::Ok;
}
void logical(Live& live,const Bank& b,Token t){
    uint32_t cursor=0;const Generation* g=live.core.inspect(t);CHECK(g&&g->map_count==b.count);
    for(uint32_t i=0;i<b.count;++i){LogicalMap m{};OK(live.core.resolve(t,i,m));const Map& expected=b.maps[i];CHECK(m.gc_nibble==expected.gc&&m.length==expected.length&&((m.aica_shift>>24)&3)==expected.shift);
        const Extent* extent=live.core.extent(expected.extent?g->shared_extent:g->local_extent);CHECK(extent);uint32_t address=m.aica_shift&0xffffffu;CHECK(address==live.core.physical_base()+extent->base+expected.offset);
        uint32_t frames=(expected.length+(1u<<expected.shift)-1)>>expected.shift,n=((frames+7)/8)*4;CHECK(cursor+n<=b.logical.size());CHECK(memcmp(live.physical.ram.data()+address-live.physical.base,b.logical.data()+cursor,n)==0);cursor+=n;
    }
    CHECK(cursor==b.logical.size());CHECK(live.core.invariant());
}
Token upload(Live& live,const Bank& b,uint32_t slot,uint32_t owner=1,uint32_t fragment=0x20000){
    Token t;OK(live.engine.begin(owner,slot,b.profile,b.mram.data(),b.mram.size(),0,t));LogicalMap m{};IS(live.core.resolve(t,0,m),State);
    Result result=rest(live,owner,t,b.blob,0,fragment);if(result!=Result::Ok){std::ostringstream s;s<<"upload "<<b.index<<" slot "<<slot<<" result "<<result_name(result);throw std::runtime_error(s.str());}
    CHECK(equal(live.core.current(slot),t));logical(live,b,t);return t;
}
uint32_t address(Live& live,Token t){const Generation* g=live.core.inspect(t);CHECK(g);const Extent* e=live.core.extent(g->local_extent);CHECK(e);return live.core.physical_base()+e->base;}
Ack ack(const Request& r,uint32_t boot=1){return {r.sequence,r.epoch,r.lease,boot,0,3};}
void release(Live& live,Token t,uint32_t channel){
    OK(live.core.pin_pending(t));Token lease;OK(live.core.start_channel(channel,t,address(live,t),lease));OK(live.core.retire_bank(t));Request req;live.wire[channel]+=6;OK(live.core.retire_channel(channel,lease,live.wire[channel],req));uint32_t free=live.core.pool().free_bytes();
    for(uint32_t i=0;i<3;++i){Ack stale=ack(req);stale.lease.lo+=i+1;IS(live.core.acknowledge(channel,stale),Stale);CHECK(live.core.pool().free_bytes()==free);CHECK(live.core.invariant());}
    OK(live.core.acknowledge(channel,ack(req)));CHECK(live.core.invariant());
}
void sha_tests(){
    struct V{const char* input;const char* digest;};const V vectors[]={{"","e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},{"abc","ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"},{"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq","248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"}};
    for(const V& v:vectors)for(uint32_t step=1;step<=65;++step){Sha256 hash;hash.reset();uint32_t n=strlen(v.input);for(uint32_t at=0;at<n;){uint32_t take=std::min(step,n-at);hash.update(v.input+at,take);at+=take;}uint8_t out[32];hash.finish(out);const char* hex="0123456789abcdef";for(uint32_t i=0;i<32;++i){CHECK(hex[out[i]>>4]==v.digest[2*i]);CHECK(hex[out[i]&15]==v.digest[2*i+1]);}}
    ++passed_cases;
}
void real_banks(){
    for(const Bank& b:banks){
        Live live;Token t;OK(live.engine.begin(1,b.slot,b.profile,b.mram.data(),b.mram.size(),0,t));auto original=b.mram;
        std::set<uint32_t> cuts={0,b.bytes};auto cut=[&](uint32_t at){for(int d=-1;d<=1;++d)if(int64_t(at)+d>0&&int64_t(at)+d<b.bytes)cuts.insert(at+d);};
        for(uint32_t at=0;at<=u32(b.blob.data()+48);at+=64)cut(at);
        for(uint32_t at=0;at<b.bytes;at+=0x20000)cut(at);
        for(const Map& m:b.maps){uint32_t eo=u32(b.blob.data()+44)+64*m.extent;cut(u32(b.blob.data()+eo+4)+m.offset);}
        uint32_t at=0;for(uint32_t end:cuts){while(at<end){uint32_t n=std::min(0x20000u,end-at),used;OK(piece(live,1,t,b.blob,at,n,used));CHECK(used==n);at+=used;}}
        logical(live,b,t);CHECK(b.mram==original);CHECK(!live.engine.active_contexts());CHECK(live.physical.max_packet<=4096);OK(live.core.retire_bank(t));CHECK(live.core.pool().free_bytes()==kMixedBytes&&live.core.maps_used()==0);++passed_cases;
    }
}
void splits_and_owners(){
    Bank b=compact();
    for(uint32_t split=1;split<b.bytes;++split){Live live;Token t;OK(live.engine.begin(1,5,b.profile,b.mram.data(),b.mram.size(),0,t));uint32_t used;OK(piece(live,1,t,b.blob,0,split,used));CHECK(used==split);OK(piece(live,1,t,b.blob,split,b.bytes-split,used));logical(live,b,t);}
    {Live live;Token t=upload(live,b,5,1,1);OK(live.core.retire_bank(t));}
    {Live live;std::vector<Token> tokens;for(uint32_t i=1;i<=16;++i){Token t;OK(live.engine.begin(i,5,b.profile,b.mram.data(),b.mram.size(),0,t));tokens.push_back(t);}Token excess;IS(live.engine.begin(17,5,b.profile,b.mram.data(),b.mram.size(),0,excess),Capacity);
        for(uint32_t at=0;at<b.bytes-1;++at)for(uint32_t i=0;i<16;++i){uint32_t used;OK(piece(live,i+1,tokens[i],b.blob,at,1,used));}
        for(uint32_t i=0;i<16;++i){uint32_t used;OK(piece(live,i+1,tokens[i],b.blob,b.bytes-1,1,used));logical(live,b,tokens[i]);OK(live.core.retire_bank(tokens[i]));}CHECK(live.core.maps_used()==0&&live.engine.active_contexts()==0);}
    {Live live;Token old;OK(live.engine.begin(42,5,b.profile,b.mram.data(),b.mram.size(),0,old));uint32_t used;
        IS(piece(live,43,old,b.blob,0,1,used),Stale);IS(piece(live,42,old,b.blob,1,1,used),Invalid);OK(piece(live,42,old,b.blob,0,10,used));IS(piece(live,42,old,b.blob,0,10,used),Invalid);IS(piece(live,42,old,b.blob,9,2,used),Invalid);OK(live.engine.cancel(42,old));
        Token fresh;OK(live.engine.begin(42,5,b.profile,b.mram.data(),b.mram.size(),0,fresh));CHECK(!equal(fresh,old));IS(live.engine.cancel(42,old),Stale);IS(piece(live,42,old,b.blob,10,1,used),Stale);OK(rest(live,42,fresh,b.blob));logical(live,b,fresh);}
    {Live live;Token t;OK(live.engine.begin(1,5,b.profile,b.mram.data(),b.mram.size(),0,t));auto padded=b.blob;padded.resize((b.bytes+31)&~31u,0xa5);uint32_t used;
        OK(live.engine.feed(1,t,0,padded.data(),padded.size(),b.bytes,used));CHECK(used==b.bytes);logical(live,b,t);}
    ++passed_cases;
}
void malformed(){
    Bank b=compact();
    auto reject=[&](std::vector<uint8_t> blob,bool before_write){Live live;Token t;OK(live.engine.begin(1,5,b.profile,b.mram.data(),b.mram.size(),0,t));Result r=rest(live,1,t,blob);CHECK(r==Result::Invalid||r==Result::Overflow||r==Result::Collision);CHECK(!live.core.inspect(t)&&!live.engine.active_contexts());CHECK(live.core.pool().free_bytes()==kMixedBytes&&live.core.maps_used()==0&&live.core.invariant());if(before_write)CHECK(!live.physical.writes);};
    for(uint32_t at=0;at<64;at+=4){auto bad=b.blob;bad[at]^=0x80;reject(bad,true);}
    for(uint32_t at=64;at<192;at+=13){auto bad=b.blob;bad[at]^=1;reject(bad,true);}
    for(uint32_t at=0;at<32;at+=4){auto bad=b.blob;le(bad,192+at,0xffffffffu);stamp(bad);reject(bad,true);}
    uint32_t eo=u32(b.blob.data()+44);
    for(uint32_t at=0;at<32;at+=4){auto bad=b.blob;le(bad,eo+at,0xffffffffu);stamp(bad);reject(bad,true);}
    {auto bad=b.blob;bad[192+32]^=1;stamp(bad);reject(bad,false);} // folded per-index hash, correct logical hash
    {auto bad=b.blob;std::swap_ranges(bad.begin()+224,bad.begin()+256,bad.begin()+288);stamp(bad);reject(bad,false);} // original sample order is authenticated
    {auto bad=b.blob;bad[eo+32]^=1;stamp(bad);reject(bad,false);}
    uint32_t data=u32(b.blob.data()+48);
    for(uint32_t at:{data,data+7,data+b.local,data+31,b.bytes-1}){auto bad=b.blob;bad[at]^=1;reject(bad,false);}
    // Exact owner offset validation precedes any mutation and permits a correct retry.
    {Live live;Token t;OK(live.engine.begin(1,5,b.profile,b.mram.data(),b.mram.size(),0,t));uint32_t used;
        IS(live.engine.feed(1,t,0,b.blob.data(),0,0,used),Invalid);IS(live.engine.feed(1,t,0,b.blob.data(),b.bytes+1,b.bytes+1,used),Invalid);
        IS(live.engine.feed(1,t,0,b.blob.data(),64,63,used),Invalid);IS(live.engine.feed(1,t,0,b.blob.data(),0x20001,1,used),Invalid);OK(rest(live,1,t,b.blob));}
    // Source bytes changed in the same allocation are rehashed before publishing.
    {Live live;Bank changed=b;Token t;OK(live.engine.begin(1,5,changed.profile,changed.mram.data(),changed.mram.size(),0,t));uint32_t used;OK(piece(live,1,t,changed.blob,0,changed.bytes-1,used));changed.mram.back()^=1;IS(piece(live,1,t,changed.blob,changed.bytes-1,1,used),Invalid);CHECK(!live.core.inspect(t));}
    ++passed_cases;
}
void mram_bounds(){
    Bank b=compact();const uint8_t* table=nullptr;
    OK(inspect_mram(b.mram.data(),b.mram.size(),0,b.mram.size(),5,2,table));CHECK(table==b.mram.data()+44);
    for(uint32_t at:{0u,8u,12u,16u,20u,24u,28u,32u,36u,40u,56u}){auto bad=b.mram;le(bad,at,0xffffffffu);IS(inspect_mram(bad.data(),bad.size(),0,bad.size(),5,2,table),Invalid);}
    for(uint32_t n=0;n<b.mram.size();++n)IS(inspect_mram(b.mram.data(),n,0,b.mram.size(),5,2,table),Invalid);
    IS(inspect_mram(b.mram.data(),b.mram.size(),0xffffffffu,b.mram.size(),5,2,table),Invalid);
    IS(inspect_mram(b.mram.data(),b.mram.size(),0,b.mram.size(),5,513,table),Invalid);
    for(uint32_t region:{256u*1024,384u*1024,512u*1024}){std::vector<uint8_t> sound(region,0);uint32_t at=region-b.mram.size();memcpy(sound.data()+at,b.mram.data(),b.mram.size());Live live;Token t;OK(live.engine.begin(1,5,b.profile,sound.data(),sound.size(),at,t));OK(rest(live,1,t,b.blob));logical(live,b,t);}
    for(uint32_t bad_kind=0;bad_kind<6;++bad_kind){Live live;Profile p=b.profile;Bank changed=b;switch(bad_kind){case 0:p.cap_hz=1234;break;case 1:p.count=513;break;case 2:p.policy=1;break;case 3:p.mram_sha[0]^=1;break;case 4:p.table_sha[0]^=1;break;case 5:changed.mram[46]^=1;break;}Token t;IS(live.engine.begin(1,5,p,changed.mram.data(),changed.mram.size(),0,t),Invalid);CHECK(!live.core.active_generations()&&!live.physical.writes);}
    ++passed_cases;
}
void physical_proofs(){
    Bank b=compact();
    for(uint32_t mode=0;mode<6;++mode){std::function<void(bool,uint32_t,uint32_t)> hook;Live live;Token t;OK(live.engine.begin(1,5,b.profile,b.mram.data(),b.mram.size(),0,t));if(mode==0)live.physical.wrong_origin=1;if(mode==1)live.physical.short_copy=1;if(mode==4)live.physical.wrong_access=1;
        if(mode==2 || mode==3 || mode==5){hook=[&](bool write,uint32_t,uint32_t){if(write)live.physical.hook=hook;else if(mode==2)live.physical.wrong_origin=1;else if(mode==3)live.physical.short_copy=1;else live.physical.wrong_access=1;};live.physical.hook=hook;}
        IS(rest(live,1,t,b.blob),Invalid);CHECK(!live.core.inspect(t)&&live.core.pool().free_bytes()==kMixedBytes&&live.core.invariant());}
    // Corrupt actual stored local bytes and zero padding after the write receipt.
    for(uint32_t off:{0u,7u,16u,31u}){Live live;Token t;OK(live.engine.begin(1,5,b.profile,b.mram.data(),b.mram.size(),0,t));live.physical.hook=[&](bool write,uint32_t addr,uint32_t){CHECK(write);live.physical.ram[addr-live.physical.base+off]^=1;};IS(rest(live,1,t,b.blob),Invalid);CHECK(!live.core.inspect(t));}
    // Aliased samples are physically read again during logical reconstruction.
    {const Bank& alias_bank=banks[29];Live live;Token t;OK(live.engine.begin(1,3,alias_bank.profile,alias_bank.mram.data(),alias_bank.mram.size(),0,t));uint32_t used;OK(piece(live,1,t,alias_bank.blob,0,u32(alias_bank.blob.data()+48),used));OK(live.engine.resume(1,t));
        const Generation* g=live.core.inspect(t);uint32_t base=live.core.extent(g->local_extent)->base;std::function<void(bool,uint32_t,uint32_t)> hook;hook=[&](bool write,uint32_t addr,uint32_t n){if(write && addr-live.physical.base+n==base+((alias_bank.local+31)&~31u))live.physical.ram[base+alias_bank.maps[8].offset]^=1;else live.physical.hook=hook;};live.physical.hook=hook;
        IS(rest(live,1,t,alias_bank.blob,used),Invalid);CHECK(!live.core.inspect(t));}
    // A valid actual readback cannot authenticate a different compact map.
    {Live live;Token t;OK(live.engine.begin(1,5,b.profile,b.mram.data(),b.mram.size(),0,t));std::function<void(bool,uint32_t,uint32_t)> hook;
        hook=[&](bool write,uint32_t,uint32_t){if(write){live.physical.hook=hook;return;}const Generation* g=live.core.inspect(t);uint32_t addr=live.core.physical_base()+live.core.extent(g->local_extent)->base;OK(live.core.set_map(t,0,{0,16,0x80000000u|(addr+8)}));};live.physical.hook=hook;
        IS(rest(live,1,t,b.blob),Invalid);CHECK(!live.core.inspect(t));}
    ++passed_cases;
}
void cancellation(){
    Bank b=compact();
    // Every ingress split, including partial header/map/extent/word/tail.
    for(uint32_t cut=0;cut<b.bytes;++cut){Live live;Token t;OK(live.engine.begin(1,5,b.profile,b.mram.data(),b.mram.size(),0,t));if(cut){uint32_t used;OK(piece(live,1,t,b.blob,0,cut,used));}OK(live.engine.cancel(1,t));IS(live.engine.cancel(1,t),Stale);CHECK(!live.core.inspect(t)&&live.core.pool().free_bytes()==kMixedBytes&&live.core.maps_used()==0&&live.core.invariant());}
    Live reference;upload(reference,b,5);uint64_t calls=reference.physical.writes+reference.physical.reads;CHECK(calls>=4);
    for(uint64_t target=1;target<=calls;++target){Live live;Token t;OK(live.engine.begin(1,5,b.profile,b.mram.data(),b.mram.size(),0,t));uint64_t count=0;std::function<void(bool,uint32_t,uint32_t)> hook;hook=[&](bool,uint32_t,uint32_t){if(++count!=target){live.physical.hook=hook;return;}uint32_t free=live.core.pool().free_bytes();CHECK(live.core.inspect(t)->copies==1);OK(live.engine.cancel(1,t));CHECK(live.core.inspect(t)&&live.core.inspect(t)->copies==1&&live.core.pool().free_bytes()==free);IS(live.core.controlled_reset({2,0},2,true),Busy);Token nested;IS(live.engine.begin(1,5,b.profile,b.mram.data(),b.mram.size(),0,nested),Busy);};live.physical.hook=hook;
        IS(rest(live,1,t,b.blob),Cancelled);CHECK(!live.core.inspect(t)&&live.core.pool().free_bytes()==kMixedBytes&&!live.engine.active_contexts());}
    // Cancelling another receiver during a copy must also release its context.
    {Live live;Token a,z;OK(live.engine.begin(1,5,b.profile,b.mram.data(),b.mram.size(),0,a));OK(live.engine.begin(2,5,b.profile,b.mram.data(),b.mram.size(),0,z));live.physical.hook=[&](bool,uint32_t,uint32_t){OK(live.engine.cancel(2,z));CHECK(live.engine.active_contexts()==1);};OK(rest(live,1,a,b.blob));CHECK(!live.engine.active_contexts()&&!live.core.inspect(z));}
    ++passed_cases;
}
void shared_registry(){
    for(bool reverse:{false,true}){Live live;const Bank& a=banks[reverse?20:19];const Bank& b=banks[reverse?19:20];Token x=upload(live,a,3),y;uint64_t writes=live.physical.write_bytes;y=upload(live,b,4,2,17);CHECK(live.physical.write_bytes-writes==((b.local+31)&~31u));const Generation gx=*live.core.inspect(x),gy=*live.core.inspect(y);CHECK(gx.shared_extent==gy.shared_extent&&live.core.extent(gx.shared_extent)->refs==2);OK(live.core.retire_bank(x));CHECK(live.core.extent(gy.shared_extent)->refs==1);OK(live.core.retire_bank(y));CHECK(live.core.pool().free_bytes()==kMixedBytes&&live.core.invariant());}
    // A matching registry SHA is not permission to reuse differing physical bytes.
    {Live live;Token x=upload(live,banks[19],3);uint32_t si=live.core.inspect(x)->shared_extent;live.physical.ram[live.core.extent(si)->base+kSharedBytes-1]^=1;const Bank& b=banks[20];Token y;OK(live.engine.begin(2,4,b.profile,b.mram.data(),b.mram.size(),0,y));IS(rest(live,2,y,b.blob),Collision);CHECK(!live.core.inspect(y)&&live.core.extent(si)->refs==1&&live.core.invariant());}
    for(bool cancel_first:{false,true}){Live live;const Bank& a=banks[19];const Bank& b=banks[20];Token x,y;OK(live.engine.begin(1,3,a.profile,a.mram.data(),a.mram.size(),0,x));OK(live.engine.begin(2,4,b.profile,b.mram.data(),b.mram.size(),0,y));uint32_t ax=u32(a.blob.data()+48),by=u32(b.blob.data()+48),used;
        OK(piece(live,1,x,a.blob,0,ax,used));OK(live.engine.resume(1,x));uint32_t free=live.core.pool().free_bytes();IS(piece(live,2,y,b.blob,0,by+4,used),Busy);CHECK(used==by&&live.core.pool().free_bytes()==free);IS(live.engine.resume(2,y),Busy);
        if(cancel_first)OK(live.engine.cancel(1,x));else OK(rest(live,1,x,a.blob,ax));OK(live.engine.resume(2,y));OK(rest(live,2,y,b.blob,by));logical(live,b,y);if(!cancel_first)OK(live.core.retire_bank(x));OK(live.core.retire_bank(y));CHECK(live.core.pool().free_bytes()==kMixedBytes&&live.core.invariant());}
    ++passed_cases;
}
void capacity_and_fixed(){
    Bank b=compact();
    // An external hardware-idle claim cannot erase a live Engine receiver.
    {Live live;Token t;OK(live.engine.begin(1,5,b.profile,b.mram.data(),b.mram.size(),0,t));IS(live.core.controlled_reset({2,0},2,true),Busy);uint32_t used;OK(piece(live,1,t,b.blob,0,u32(b.blob.data()+48),used));OK(live.engine.resume(1,t));IS(live.core.controlled_reset({2,0},2,true),Busy);OK(rest(live,1,t,b.blob,used));logical(live,b,t);OK(live.core.controlled_reset({2,0},2,true));CHECK(!live.engine.active_contexts()&&live.core.invariant());}
    {Live live(32);Token a=upload(live,b,5),t;OK(live.engine.begin(2,5,b.profile,b.mram.data(),b.mram.size(),0,t));uint32_t used;IS(piece(live,2,t,b.blob,0,b.bytes,used),NoSpace);CHECK(used==u32(b.blob.data()+48));OK(live.core.retire_bank(a));OK(live.engine.resume(2,t));OK(rest(live,2,t,b.blob,used));logical(live,b,t);}
    {Live live(kSharedBytes);const Bank& shared=banks[19];Token t;OK(live.engine.begin(1,3,shared.profile,shared.mram.data(),shared.mram.size(),0,t));uint32_t used;IS(piece(live,1,t,shared.blob,0,0x20000,used),NoSpace);CHECK(live.core.pool().free_bytes()==kSharedBytes&&live.core.invariant());OK(live.engine.cancel(1,t));}
    {Live live;std::vector<Token> all;for(uint32_t i=0;i<32;++i){Token t=upload(live,b,5);OK(live.core.pin_pending(t));OK(live.core.retire_bank(t));all.push_back(t);}Token extra;IS(live.engine.begin(1,5,b.profile,b.mram.data(),b.mram.size(),0,extra),Capacity);for(Token t:all)OK(live.core.drop_pending(t));CHECK(live.core.active_generations()==0);}
    {Core core;Token a,big,other;OK(core.begin(1,5,1,a));OK(core.reserve(a,512,32));OK(core.begin(2,6,1,big));OK(core.reserve(big,128,32));OK(core.begin(3,5,1,other));IS(core.reserve(other,1,32),Capacity);CHECK(core.maps_used()==640);OK(core.cancel(3,other));OK(core.cancel(1,a));OK(core.cancel(2,big));CHECK(core.invariant());}
    {Core bad(kMixedBytes+32);Token t;CHECK(bad.faulted());IS(bad.begin(1,5,1,t),Faulted);Core zero(32,{0,0});CHECK(zero.faulted());Core misaligned(32,{1,0},1,1);CHECK(misaligned.faulted());Core far(32,{1,0},1,0xff0000);CHECK(far.faulted());}
    {Live live;const Bank& fixed=banks[0];Token old=upload(live,fixed,0);CHECK(live.core.extent(live.core.inspect(old)->local_extent)->kind==3);CHECK(live.core.pool().free_bytes()==kMixedBytes);OK(live.core.pin_pending(old));Token lease;OK(live.core.start_channel(0,old,address(live,old),lease));OK(live.core.retire_bank(old));Token next;OK(live.engine.begin(2,0,fixed.profile,fixed.mram.data(),fixed.mram.size(),0,next));uint32_t used;IS(piece(live,2,next,fixed.blob,0,0x20000,used),Busy);CHECK(used==u32(fixed.blob.data()+48));CHECK(live.physical.write_bytes==((fixed.local+31)&~31u));Request req;OK(live.core.retire_channel(0,lease,42,req));OK(live.core.acknowledge(0,ack(req)));OK(live.engine.resume(2,next));OK(rest(live,2,next,fixed.blob,used));logical(live,fixed,next);CHECK(live.core.pool().free_bytes()==kMixedBytes);OK(live.core.retire_bank(next));CHECK(live.core.invariant());}
    // Publication waits for the previous slot owner even after full verification.
    {Live live;Token a=upload(live,b,5),next;OK(live.engine.begin(2,5,b.profile,b.mram.data(),b.mram.size(),0,next));IS(rest(live,2,next,b.blob),Busy);CHECK(equal(live.core.current(5),a));OK(live.core.retire_bank(a));OK(live.engine.resume(2,next));CHECK(equal(live.core.current(5),next));}
    // A blocked publish must re-read changed source metadata before it becomes valid.
    {Live live;Token a=upload(live,b,5),next;Bank changed=b;OK(live.engine.begin(2,5,changed.profile,changed.mram.data(),changed.mram.size(),0,next));IS(rest(live,2,next,changed.blob),Busy);changed.mram.back()^=1;OK(live.core.retire_bank(a));IS(live.engine.resume(2,next),Invalid);CHECK(!live.core.inspect(next)&&!live.engine.active_contexts());}
    // A blocked publish must also repeat physical readback, never cache an old proof.
    {Live live;Token a=upload(live,b,5),next;OK(live.engine.begin(2,5,b.profile,b.mram.data(),b.mram.size(),0,next));IS(rest(live,2,next,b.blob),Busy);uint32_t at=live.core.extent(live.core.inspect(next)->local_extent)->base;live.physical.ram[at]^=1;OK(live.core.retire_bank(a));IS(live.engine.resume(2,next),Invalid);CHECK(!live.core.inspect(next));}
    ++passed_cases;
}
void fences(){
    Bank b=compact();Live live(4096);Token bank=upload(live,b,5),lease;uint32_t addr=address(live,bank);
    IS(live.core.start_channel(0,bank,addr,lease),State);OK(live.core.pin_pending(bank));IS(live.core.start_channel(0,bank,addr-live.core.physical_base(),lease),Invalid);OK(live.core.start_channel(0,bank,addr,lease));CHECK(live.core.inspect(bank)->hardware_refs==1);
    Request req;IS(live.core.retire_channel(0,lease,0,req),Invalid);IS(live.core.retire_channel(0,lease,3,req),Invalid);OK(live.core.retire_channel(0,lease,6,req));CHECK(req.sequence==6);Request duplicate;OK(live.core.retire_channel(0,lease,6,duplicate));IS(live.core.retire_channel(0,lease,8,duplicate),Busy);
    OK(live.core.pin_pending(bank));Token newer;IS(live.core.reuse_same_generation(0,lease,bank,addr,newer),Busy);CHECK(live.core.inspect(bank)->pending_refs==1&&live.core.inspect(bank)->hardware_refs==1);
    Ack proper=ack(req);for(uint32_t field=0;field<7;++field){Ack wrong=proper;switch(field){case 0:wrong.sequence|=1;break;case 1:wrong.sequence+=2;break;case 2:++wrong.epoch.lo;break;case 3:++wrong.lease.lo;break;case 4:++wrong.boot_serial;break;case 5:wrong.flags=1;wrong.observed_eg=0xffffffffu;break;case 6:wrong.flags=7;break;}IS(live.core.acknowledge(0,wrong),Stale);}
    OK(live.core.acknowledge(0,proper));OK(live.core.start_channel(0,bank,addr,newer));CHECK(!equal(lease,newer));IS(live.core.retire_channel(0,newer,6,req),Invalid);OK(live.core.retire_channel(0,newer,0xfffffffeu,req));IS(live.core.acknowledge(0,proper),Stale);OK(live.core.acknowledge(0,ack(req)));OK(live.core.pin_pending(bank));OK(live.core.start_channel(0,bank,addr,newer));IS(live.core.retire_channel(0,newer,2,req),Invalid);
    // Reset is a caller-qualified external assumption, never a timer/EG proof.
    IS(live.core.observe_boot(2),Faulted);IS(live.core.controlled_reset({2,0},2,false),Invalid);OK(live.core.controlled_reset({2,0},2,true));CHECK(live.core.pool().free_bytes()==4096);IS(live.core.retire_bank(bank),Stale);IS(live.core.acknowledge(0,proper),Stale);
    bank=upload(live,b,5);OK(live.core.pin_pending(bank));IS(live.core.controlled_reset({3,0},3,true),Busy);OK(live.core.drop_pending(bank));OK(live.core.controlled_reset({3,0},3,true));CHECK(live.core.invariant());
    {Live many;Token t=upload(many,b,5);std::vector<Token> leases;for(uint32_t ch=0;ch<64;++ch){OK(many.core.pin_pending(t));Token l;OK(many.core.start_channel(ch,t,address(many,t),l));leases.push_back(l);}CHECK(many.core.inspect(t)->hardware_refs==64);OK(many.core.retire_bank(t));for(uint32_t ch=0;ch<64;++ch){Request r;OK(many.core.retire_channel(ch,leases[ch],100+2*ch,r));OK(many.core.acknowledge(ch,ack(r)));}CHECK(many.core.active_generations()==0&&many.core.invariant());}
    ++passed_cases;
}
void fixed_prefix(Live& live){for(uint32_t i=0;i<4;++i)live.fixed.push_back(upload(live,banks[i],banks[i].slot));CHECK(live.core.maps_used()==111&&live.core.pool().free_bytes()==kMixedBytes);}
void enter(Live& live,const Room& room,bool reverse){
    for(Token t:live.actors){release(live,t,0);}
    live.actors.clear();for(Token t:live.room){release(live,t,1);}
    live.room.clear();
    for(unsigned i:room.base)live.room.push_back(upload(live,banks[i],banks[i].slot));
    for(unsigned which=0;which<2;++which){int idx=room.bgm[which];if(which==0&&idx==live.music_id[which])continue;if(live.music_id[which]>=0)release(live,live.music[which],2+which);live.music_id[which]=-1;if(idx>=0){live.music[which]=upload(live,banks.at(idx),3+which);live.music_id[which]=idx;}}
    auto order=room.actors;if(reverse)std::reverse(order.begin(),order.end());for(uint32_t i=0;i<order.size();++i)live.actors.push_back(upload(live,banks[order[i]],8+i));CHECK(live.core.invariant());
}
void schedules(bool quick){
    const uint32_t margins[6]={237728,98752,611648,2688,259808,5248},maps[6]={347,351,218,350,260,339};uint32_t transitions=0;
    std::cout<<"\"cold_rooms\":[";
    for(uint32_t i=0;i<6;++i){Live live;fixed_prefix(live);enter(live,rooms[i],false);CHECK(live.core.pool().free_bytes()==margins[i]&&live.core.maps_used()==maps[i]);if(i)std::cout<<',';std::cout<<"{\"room\":\""<<rooms[i].name<<"\",\"free\":"<<margins[i]<<",\"maps\":"<<live.core.maps_used()<<'}';}
    if(!quick){
        for(uint32_t from=0;from<6;++from)for(uint32_t to=0;to<6;++to)for(bool reverse:{false,true}){Live live;fixed_prefix(live);enter(live,rooms[from],reverse);enter(live,rooms[to],!reverse);CHECK(live.core.pool().free_bytes()==margins[to]);++transitions;}
        for(uint32_t from=0;from<6;++from)for(uint32_t to=0;to<6;++to){Live live;fixed_prefix(live);for(uint32_t j=0;j<20;++j){uint32_t i=j%2?to:from;enter(live,rooms[i],(j&2)!=0);CHECK(live.core.pool().free_bytes()==margins[i]);if(j)++transitions;}}
    }
    std::cout<<"],\"transitions\":"<<transitions<<',';++passed_cases;
}
}
int main(int argc,char** argv){
    try{CHECK(argc==3||argc==4);load_fixtures(argv[1],argv[2]);sha_tests();std::cerr<<"sha passed\n";real_banks();std::cerr<<"real banks passed\n";splits_and_owners();std::cerr<<"splits/owners passed\n";malformed();std::cerr<<"malformed passed\n";mram_bounds();std::cerr<<"MRAM bounds passed\n";physical_proofs();std::cerr<<"physical proofs passed\n";cancellation();std::cerr<<"cancel passed\n";shared_registry();std::cerr<<"shared registry passed\n";capacity_and_fixed();std::cerr<<"capacity/fixed passed\n";fences();std::cerr<<"fences passed\n";std::cout<<'{';schedules(argc==4);
        std::cout<<"\"checks\":"<<checks<<",\"cases\":"<<passed_cases<<",\"core_bytes\":"<<sizeof(Core)<<",\"receiver_bytes\":"<<sizeof(Receiver)<<",\"engine_bytes\":"<<sizeof(Engine)<<",\"scratch_bytes\":4096,\"hardware_inactivity_qualified\":false,\"runtime_loader_integrated\":false}\n";return 0;
    }catch(const std::exception& e){std::cerr<<"FAIL "<<e.what()<<'\n';return 1;}
}
