#include "aica_bank_v2_stream.h"
#if RE4DC_AICA_BANK_V2
#include <string.h>
namespace re4dc_aic2 {
namespace {
uint32_t u32(const uint8_t* p){return uint32_t(p[0])|(uint32_t(p[1])<<8)|(uint32_t(p[2])<<16)|(uint32_t(p[3])<<24);}
uint32_t u16(const uint8_t* p){return uint32_t(p[0])|(uint32_t(p[1])<<8);}
void le(uint8_t* p,uint32_t x){p[0]=x;p[1]=x>>8;p[2]=x>>16;p[3]=x>>24;}
bool span(uint32_t at,uint32_t n,uint32_t limit){return at<=limit && n<=limit-at;}
bool zero(const uint8_t* p,uint32_t n){for(uint32_t i=0;i<n;++i)if(p[i])return false;return true;}
uint32_t min32(uint32_t a,uint32_t b){return a<b?a:b;}
uint32_t h(const Receiver& r,uint32_t at){return u32(r.header+at);}
uint32_t e(const Receiver& r,uint32_t index,uint32_t at){return u32(r.extents+64*index+at);}
bool hex_equal(const uint8_t* p,const char* hex){
    const char* digits="0123456789abcdef";
    for(uint32_t i=0;i<32;++i)if(digits[p[i]>>4]!=hex[2*i] || digits[p[i]&15]!=hex[2*i+1])return false;
    return true;
}
uint32_t policy(const Profile& p){
    if(p.source_class!=3)return 0;
    if(hex_equal(p.mram_sha,"ffb4381fbc783d9baf5093cb12fd5bb68286f7279d7b46f1c87f3a9c27f85b59") &&
       hex_equal(p.table_sha,"263ea3609e2c89093b8abeaffd3202c4ccdb3671e7dad23b2d605c06e6b042e7"))return 1;
    if(hex_equal(p.mram_sha,"63c4ffabd6c489ecfc36179fb98814b4fe89e46ce90ce24128181832c9d2870a") &&
       hex_equal(p.table_sha,"328fe7104bdaee4046892f6905c0239dca0bea5bfcf3ae41a15f953acedb0bb0"))return 2;
    if(hex_equal(p.mram_sha,"b03ed77663ca406518a86d7aebd981067155ade75299c810f18a47b0b0dc294b") &&
       hex_equal(p.table_sha,"6192cf86967a2963af07d6bf288e65ea80ff1ffb6ed913e5ff03753dfe5451c0"))return 3;
    return 0;
}
uint32_t alias(uint32_t pol,uint32_t index){
    if(pol!=1 || index<8 || index>12)return index;
    const uint32_t first[5]={2,4,5,6,7};return first[index-8];
}
bool shared_sample(uint32_t pol,uint32_t index){return (pol==2 && index==6)||(pol==3 && index==0);}
Result sample(const Receiver& r,uint32_t index,uint32_t& bytes,uint32_t& shift){
    if(index>=r.profile->count)return Result::Invalid;
    const uint8_t* s=r.table+16*index;uint32_t rate=u16(s+2),length=u32(s+8),cap=r.profile->cap_hz;
    if(u16(s) || !rate || !length || u32(s+4)/2>=r.profile->gc_bytes)return Result::Invalid;
    shift=0;while(shift<3 && ((rate>>shift)>cap+cap/64 || (length>>shift)>65534))++shift;
    uint64_t frames=(uint64_t(length)+(1u<<shift)-1)>>shift;
    uint64_t n=((frames+7)/8)*4;if(n>0xffffffffu)return Result::Overflow;
    bytes=static_cast<uint32_t>(n);return Result::Ok;
}
Result location(const Receiver& r,uint32_t index,uint32_t& extent,uint32_t& offset,uint32_t& bytes,uint32_t& shift){
    Result result=sample(r,index,bytes,shift);if(result!=Result::Ok)return result;
    uint32_t target=alias(r.profile->policy,index);extent=shared_sample(r.profile->policy,target)?1:0;offset=0;
    if(extent)return bytes==kSharedBytes?Result::Ok:Result::Invalid;
    uint32_t target_bytes,target_shift;result=sample(r,target,target_bytes,target_shift);
    if(result!=Result::Ok || target_bytes!=bytes)return Result::Invalid;
    for(uint32_t i=0;i<target;++i){
        if(shared_sample(r.profile->policy,i) || alias(r.profile->policy,i)!=i)continue;
        uint32_t n,sh;result=sample(r,i,n,sh);if(result!=Result::Ok)return result;
        if(n>0xffffffffu-offset)return Result::Overflow;
        offset+=n;
    }
    return Result::Ok;
}
void fold_start(Sha256& hash,uint32_t count){
    const char domain[]="AIC2-SAMPLE-FOLD-v1";uint8_t n[4];le(n,count);
    hash.reset();hash.update(domain,sizeof(domain)-1);hash.update(n,4);
}
void fold_sample(Sha256& hash,uint32_t index,uint32_t bytes,const uint8_t digest[32]){
    uint8_t n[8];le(n,index);le(n+4,bytes);hash.update(n,8);hash.update(digest,32);
}
}
Result inspect_mram(const uint8_t* sound,uint32_t sound_bytes,uint32_t offset,uint32_t bytes,
                    uint32_t source_class,uint32_t count,const uint8_t*& table){
    table=nullptr;
    if(!sound || !bytes || !span(offset,bytes,sound_bytes) || !count || count>512)return Result::Invalid;
    const uint8_t* m=sound+offset;if(bytes<4)return Result::Invalid;
    uint32_t base=source_class==3?0:u32(m);
    if((base&3) || !span(base,16,bytes))return Result::Invalid;
    uint32_t dls=u32(m+base+4),sit=u32(m+base+8),seq=u32(m+base+12);
    if((dls&3) || !span(dls,24,bytes-base) || (sit && !span(sit,4,bytes-base)) || (seq && !span(seq,4,bytes-base)))return Result::Invalid;
    uint32_t wt=base+dls;const uint8_t* w=m+wt;
    if(u32(w)!=24)return Result::Invalid;
    uint32_t prior=24;
    for(uint32_t at=4;at<=20;at+=4){uint32_t v=u32(w+at);if(v<prior || !span(v,0,bytes-wt))return Result::Invalid;prior=v;}
    uint32_t smp=u32(w+16),adp=u32(w+20);
    if((smp&3) || adp<smp || adp-smp!=count*16 || !span(smp,count*16,bytes-wt))return Result::Invalid;
    const uint8_t* t=w+smp;
    for(uint32_t i=0;i<count;++i){uint32_t coef=u16(t+16*i+12);if(!span(adp,(coef+1)*46,bytes-wt))return Result::Invalid;}
    table=t;return Result::Ok;
}
Engine::Engine(Core& core,PhysicalAdapter& physical):core_(core),physical_(physical),busy_(0){memset(receivers_,0,sizeof(receivers_));memset(scratch_,0,sizeof(scratch_));sample_sha_.reset();}
Receiver* Engine::find(uint32_t owner,Token token){for(Receiver& r:receivers_)if(r.state && r.owner==owner && equal(r.token,token))return &r;return nullptr;}
uint32_t Engine::active_contexts()const{uint32_t n=0;for(const Receiver& r:receivers_)n+=r.state!=Empty;return n;}
Result Engine::metadata(Receiver& r){
    const Profile& p=*r.profile;const uint8_t* table=nullptr;
    Result result=inspect_mram(r.mram,p.mram_bytes,0,p.mram_bytes,p.source_class,p.count,table);
    if(result!=Result::Ok)return result;
    if(r.table && r.table!=table)return Result::Invalid;
    r.table=table;
    uint8_t digest[32];r.first.reset();r.first.update(r.mram,p.mram_bytes);r.first.finish(digest);
    if(memcmp(digest,p.mram_sha,32))return Result::Invalid;
    r.first.reset();r.first.update(table,p.count*16);r.first.finish(digest);
    if(memcmp(digest,p.table_sha,32) || p.policy!=policy(p))return Result::Invalid;
    uint32_t total=0;
    for(uint32_t i=0;i<p.count;++i){uint32_t n,sh;result=sample(r,i,n,sh);if(result!=Result::Ok)return result;if(n>0xffffffffu-total)return Result::Overflow;total+=n;}
    return total==p.logical_bytes?Result::Ok:Result::Invalid;
}
Result Engine::begin(uint32_t owner,uint32_t slot,const Profile& p,const uint8_t* sound,uint32_t sound_bytes,uint32_t offset,Token& token){
    token={};if(busy_)return Result::Busy;
    if(!owner || !sound || !p.id || p.gc_bytes<192 || !p.count || p.count>512 || !span(offset,p.mram_bytes,sound_bytes))return Result::Invalid;
    if(p.cap_hz!=8000 && p.cap_hz!=11025 && p.cap_hz!=16000 && p.cap_hz!=22050 && p.cap_hz!=32000)return Result::Invalid;
    if(p.source_class!=0 && p.source_class!=1 && p.source_class!=2 && p.source_class!=3 && p.source_class!=5 && p.source_class!=6 && p.source_class!=7 && p.source_class!=8)return Result::Invalid;
    if(!(p.source_class==3?(slot==3||slot==4):p.source_class==8?(slot>=8&&slot<=13):slot==p.source_class))return Result::Invalid;
    Receiver* target=nullptr;for(Receiver& r:receivers_){if(r.state && r.owner==owner)return Result::Busy;if(!r.state && !target)target=&r;}
    if(!target)return Result::Capacity;
    Receiver& r=*target;memset(&r,0,sizeof(r));r.profile=&p;r.mram=sound+offset;r.owner=owner;r.slot=slot;
    Result result=metadata(r);if(result!=Result::Ok){memset(&r,0,sizeof(r));return result;}
    result=core_.begin(owner,slot,p.gc_bytes,token);if(result!=Result::Ok){memset(&r,0,sizeof(r));return result;}
    r.token=token;r.state=Header;return Result::Ok;
}
Result Engine::header(Receiver& r){
    const Profile& p=*r.profile;uint32_t count=p.count,ne=p.policy>=2?2:1;
    if(h(r,0)!=0x32434941 || u16(r.header+4)!=2 || u16(r.header+6)!=192 || h(r,8)!=0x12345678 || h(r,12))return Result::Invalid;
    if(h(r,16)!=p.source_class || h(r,20)!=count || h(r,24)!=64 || h(r,28)!=ne || h(r,32)!=64 || h(r,36)!=p.logical_bytes || h(r,40)!=192 || h(r,44)!=192+64*count || h(r,48)!=192+64*(count+ne) || h(r,56)!=p.gc_bytes || h(r,60)!=p.id)return Result::Invalid;
    if(h(r,48)>h(r,52) || h(r,52)>p.gc_bytes || memcmp(r.header+64,p.mram_sha,32) || memcmp(r.header+96,p.table_sha,32) || memcmp(r.header+128,p.logical_sha,32))return Result::Invalid;
    r.first.reset();r.first.update(r.header,160);const uint8_t zeros[32]={0};r.first.update(zeros,32);fold_start(r.second,count);
    r.state=Maps;r.fill=0;r.index=0;return Result::Ok;
}
Result Engine::map(Receiver& r){
    uint32_t ex,at,n,sh;Result result=location(r,r.index,ex,at,n,sh);if(result!=Result::Ok)return result;
    const uint8_t* rec=r.record;const uint8_t* t=r.table+16*r.index;
    if(u32(rec)!=u32(t+4) || u32(rec+4)!=u32(t+8) || u32(rec+8)!=r.logical_cursor || u32(rec+12)!=n || u32(rec+16)!=sh || u32(rec+20)!=ex || u32(rec+24)!=at || u32(rec+28))return Result::Invalid;
    if(n>0xffffffffu-r.logical_cursor)return Result::Overflow;
    r.logical_cursor+=n;
    if(!ex && alias(r.profile->policy,r.index)==r.index){if(n>0xffffffffu-r.local_bytes)return Result::Overflow;r.local_bytes+=n;}
    r.first.update(rec,64);fold_sample(r.second,r.index,n,rec+32);++r.index;r.fill=0;
    if(r.index==r.profile->count){if(r.logical_cursor!=r.profile->logical_bytes)return Result::Invalid;r.second.finish(r.expected_fold);r.state=Extents;r.index=0;}
    return Result::Ok;
}
Result Engine::extents(Receiver& r){
    uint32_t cursor=h(r,48);
    for(uint32_t i=0;i<h(r,28);++i){
        const uint8_t* rec=r.extents+64*i;uint32_t payload=u32(rec+8),stored=u32(rec+12);
        if(u32(rec)!=i+1 || u32(rec+4)!=cursor || !payload || payload>0xffffffffu-31 || stored!=((payload+31)&~31u) || u32(rec+16)!=i || !zero(rec+20,12) || !span(cursor,stored,h(r,52)))return Result::Invalid;
        if(!i && payload!=r.local_bytes)return Result::Invalid;
        if(i && (payload!=kSharedBytes || !hex_equal(rec+32,"d224dd185bd1856cec5e3157c9bc69ba57de39ddbc82a0462070aaa8539fd4b5")))return Result::Invalid;
        r.first.update(rec,64);cursor+=stored;
    }
    uint8_t digest[32];r.first.finish(digest);
    if(cursor!=h(r,52) || memcmp(digest,r.header+160,32))return Result::Invalid;
    r.state=Reserve;r.fill=0;return Result::Ok;
}
Result Engine::reserve(Receiver& r){
    SharedSpec shared{};shared.bytes=kSharedBytes;memcpy(shared.sha,r.extents+96,32);
    Result result=core_.reserve(r.token,r.profile->count,r.local_bytes,h(r,28)==2?&shared:nullptr);if(result!=Result::Ok)return result;
    const Generation* g=core_.inspect(r.token);if(!g)return Result::Stale;
    r.shared_hit=g->shared_extent!=kInvalid && core_.extent(g->shared_extent)->verified;
    for(uint32_t i=0;i<r.profile->count;++i){
        uint32_t ex,at,n,sh;result=location(r,i,ex,at,n,sh);if(result!=Result::Ok)return result;
        const Extent* extent=core_.extent(ex?g->shared_extent:g->local_extent);if(!extent || !span(at,n,extent->payload_bytes))return Result::Invalid;
        uint32_t address=core_.physical_base()+extent->base+at;
        result=core_.set_map(r.token,i,{u32(r.table+16*i+4),u32(r.table+16*i+8),address|(sh<<24)|0x80000000u});if(result!=Result::Ok)return result;
    }
    r.state=Payload;r.payload_extent=r.payload_offset=r.carry_bytes=0;r.first.reset();return Result::Ok;
}
Result Engine::transfer(Receiver& r,uint32_t ei,uint32_t offset,uint32_t bytes,const uint8_t* write){
    CopyTicket ticket;Result result=core_.copy_begin(r.token,ei,offset,bytes,write!=nullptr,ticket);if(result!=Result::Ok)return result;
    uint32_t address=ticket.base_+ticket.offset_;
    PhysicalResult actual=write?physical_.write(address,write,bytes):physical_.read(address,scratch_,bytes);
    // The ticket and exact extent stay pinned across this untrusted callback.
    return core_.copy_end(ticket,actual.actual_address,actual.actual_bytes,actual.actual_access);
}
Result Engine::scatter(Receiver& r,const uint8_t* input,uint32_t count){
    const Generation* g=core_.inspect(r.token);if(!g)return Result::Stale;
    uint32_t ei=r.payload_extent?g->shared_extent:g->local_extent;
    bool compare=r.payload_extent && r.shared_hit;
    while(count){
        const uint8_t* packet=input;uint32_t bytes;
        if(r.carry_bytes || count<4){
            bytes=min32(4-r.carry_bytes,count);
            memcpy(reinterpret_cast<uint8_t*>(&r.carry)+r.carry_bytes,input,bytes);
            r.carry_bytes+=bytes;r.payload_offset+=bytes;input+=bytes;count-=bytes;
            if(r.carry_bytes<4)continue;
            packet=reinterpret_cast<const uint8_t*>(&r.carry);bytes=4;
            Result result=transfer(r,ei,r.payload_offset-4,bytes,compare?nullptr:packet);
            if(result!=Result::Ok)return result;
            if(compare && memcmp(packet,scratch_,4))return Result::Collision;
            r.carry_bytes=0;
        }else{
            bytes=min32(count&~3u,4096);
            Result result=transfer(r,ei,r.payload_offset,bytes,compare?nullptr:packet);
            if(result!=Result::Ok)return result;
            if(compare && memcmp(packet,scratch_,bytes))return Result::Collision;
            r.payload_offset+=bytes;input+=bytes;count-=bytes;
        }
    }
    return Result::Ok;
}
Result Engine::finish(Receiver& r){
    if(r.received!=r.profile->gc_bytes || r.carry_bytes)return Result::Busy;
    // Capacity waits cannot cache a publication proof across mutable MRAM or
    // physical memory. Re-attest after the previous slot owner retires.
    if(nonzero(core_.current(r.slot).serial)){r.state=Ready;return Result::Busy;}
    r.state=Readback;
    const Generation* g=core_.inspect(r.token);if(!g)return Result::Stale;
    // First attest every complete stored extent, including all zero padding.
    for(uint32_t i=0;i<h(r,28);++i){
        uint32_t ei=i?g->shared_extent:g->local_extent;r.first.reset();
        uint32_t payload=e(r,i,8),stored=e(r,i,12);
        for(uint32_t at=0;at<stored;){
            uint32_t n=min32(stored-at,4096);Result result=transfer(r,ei,at,n,nullptr);if(result!=Result::Ok)return result;
            uint32_t useful=at<payload?min32(n,payload-at):0;
            if(useful)r.first.update(scratch_,useful);
            if(!zero(scratch_+useful,n-useful))return Result::Invalid;
            at+=n;
        }
        uint8_t digest[32];r.first.finish(digest);if(memcmp(digest,r.extents+64*i+32,32))return Result::Invalid;
    }
    r.first.reset();fold_start(r.second,r.profile->count);
    for(uint32_t i=0;i<r.profile->count;++i){
        uint32_t ex,offset,bytes,shift;Result result=location(r,i,ex,offset,bytes,shift);if(result!=Result::Ok)return result;
        uint32_t ei=ex?g->shared_extent:g->local_extent;sample_sha_.reset();
        for(uint32_t at=0;at<bytes;){
            uint32_t n=min32(bytes-at,4096);result=transfer(r,ei,offset+at,n,nullptr);if(result!=Result::Ok)return result;
            r.first.update(scratch_,n);sample_sha_.update(scratch_,n);at+=n;
        }
        uint8_t digest[32];sample_sha_.finish(digest);fold_sample(r.second,i,bytes,digest);
    }
    uint8_t logical[32],folded[32];r.first.finish(logical);r.second.finish(folded);
    if(memcmp(logical,r.profile->logical_sha,32) || memcmp(logical,r.header+128,32) || memcmp(folded,r.expected_fold,32))return Result::Invalid;
    Result result=metadata(r);if(result!=Result::Ok)return result;
    g=core_.inspect(r.token);if(!g || r.state==Cancelled)return Result::Cancelled;
    // Verify the compact maps actually being published, including any change
    // attempted by an adapter callback during readback of an earlier sample.
    for(uint32_t i=0;i<r.profile->count;++i){
        uint32_t ex,at,n,sh;result=location(r,i,ex,at,n,sh);if(result!=Result::Ok)return result;
        const Extent* extent=core_.extent(ex?g->shared_extent:g->local_extent);if(!extent)return Result::Stale;
        LogicalMap map{};result=core_.prepared_map(r.token,i,map);if(result!=Result::Ok)return result;
        if(map.gc_nibble!=u32(r.table+16*i+4) || map.length!=u32(r.table+16*i+8) ||
           map.aica_shift!=((core_.physical_base()+extent->base+at)|(sh<<24)|0x80000000u))return Result::Invalid;
    }
    if(nonzero(core_.current(r.slot).serial)){r.state=Ready;return Result::Busy;}
    VerificationReceipt receipt;receipt.token_=r.token;receipt.owner_=r.owner;receipt.nonce_=g->copy_nonce;
    result=core_.verify(receipt);if(result!=Result::Ok)return result;
    r.state=Ready;result=core_.publish(r.owner,r.token);if(result==Result::Ok)memset(&r,0,sizeof(r));return result;
}
Result Engine::fail(Receiver& r,Result why){core_.cancel(r.owner,r.token);memset(&r,0,sizeof(r));return why;}
Result Engine::feed(uint32_t owner,Token token,uint32_t offset,const uint8_t* input,uint32_t input_bytes,uint32_t logical_bytes,uint32_t& consumed){
    consumed=0;if(busy_)return Result::Busy;
    Receiver* found=find(owner,token);if(!found)return Result::Stale;Receiver& r=*found;
    if(!input || !logical_bytes || logical_bytes>input_bytes || input_bytes>0x20000 || offset!=r.received || !span(offset,logical_bytes,r.profile->gc_bytes))return Result::Invalid;
    if(input_bytes!=logical_bytes && (offset+logical_bytes!=r.profile->gc_bytes || input_bytes!=((logical_bytes+31)&~31u)))return Result::Invalid;
    if(r.state==Ready || r.state==Cancelled)return Result::State;
    busy_=static_cast<uint32_t>(found-receivers_)+1;Result result=Result::Ok;
    while(consumed<logical_bytes){
        if(r.state==Reserve){result=reserve(r);if(result!=Result::Ok)break;}
        uint32_t n=0;const uint8_t* p=input+consumed;
        if(r.state==Header){n=min32(logical_bytes-consumed,192-r.fill);memcpy(r.header+r.fill,p,n);r.fill+=n;}
        else if(r.state==Maps){n=min32(logical_bytes-consumed,64-r.fill);memcpy(r.record+r.fill,p,n);r.fill+=n;}
        else if(r.state==Extents){n=min32(logical_bytes-consumed,64*h(r,28)-r.fill);memcpy(r.extents+r.fill,p,n);r.fill+=n;}
        else if(r.state==Payload){
            uint32_t i=r.payload_extent,payload=e(r,i,8),stored=e(r,i,12);
            n=min32(logical_bytes-consumed,stored-r.payload_offset);
            uint32_t useful=r.payload_offset<payload?min32(n,payload-r.payload_offset):0;
            if(!zero(p+useful,n-useful)){result=Result::Invalid;break;}
            if(useful)r.first.update(p,useful);
            result=scatter(r,p,n);if(result!=Result::Ok)break;
        }else if(r.state==Tail){n=logical_bytes-consumed;if(!zero(p,n)){result=Result::Invalid;break;}}
        else{result=Result::State;break;}
        result=core_.feed(owner,token,r.received,n);if(result!=Result::Ok)break;
        r.received+=n;consumed+=n;
        if(r.state==Header && r.fill==192)result=header(r);
        else if(r.state==Maps && r.fill==64)result=map(r);
        else if(r.state==Extents && r.fill==64*h(r,28))result=extents(r);
        else if(r.state==Payload && r.payload_offset==e(r,r.payload_extent,12)){
            uint8_t digest[32];r.first.finish(digest);
            if(r.carry_bytes || memcmp(digest,r.extents+64*r.payload_extent+32,32)){result=Result::Invalid;break;}
            ++r.payload_extent;r.payload_offset=0;r.first.reset();if(r.payload_extent==h(r,28))r.state=Tail;
        }
        if(result!=Result::Ok)break;
    }
    if(result==Result::Ok && r.received==r.profile->gc_bytes)result=finish(r);
    if(result!=Result::Ok && result!=Result::Busy && result!=Result::NoSpace && result!=Result::Capacity)result=fail(r,result);
    busy_=0;return result;
}
Result Engine::resume(uint32_t owner,Token token){
    if(busy_)return Result::Busy;
    Receiver* r=find(owner,token);if(!r)return Result::Stale;
    busy_=static_cast<uint32_t>(r-receivers_)+1;Result result=r->state==Reserve?reserve(*r):r->state==Ready?finish(*r):Result::State;
    if(result!=Result::Ok && result!=Result::Busy && result!=Result::NoSpace && result!=Result::Capacity && result!=Result::State)result=fail(*r,result);
    busy_=0;return result;
}
Result Engine::cancel(uint32_t owner,Token token){
    Receiver* r=find(owner,token);if(!r)return Result::Stale;
    Result result=core_.cancel(owner,token);if(result!=Result::Ok)return result;
    if(busy_==static_cast<uint32_t>(r-receivers_)+1)r->state=Cancelled;else memset(r,0,sizeof(*r));return Result::Ok;
}
}
#endif
