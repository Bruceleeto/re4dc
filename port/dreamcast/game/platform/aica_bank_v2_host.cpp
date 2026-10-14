#include "aica_bank_v2_host.h"
#if RE4DC_AICA_BANK_V2
#include <string.h>
#include <initializer_list>

namespace re4dc_aic2 {
namespace {
constexpr uint32_t kU32 = 0xffffffffu;
const uint8_t kSharedSha[32] = {
    0xd2,0x24,0xdd,0x18,0x5b,0xd1,0x85,0x6c,0xec,0x5e,0x31,0x57,0xc9,0xbc,0x69,0xba,
    0x57,0xde,0x39,0xdd,0xbc,0x82,0xa0,0x46,0x20,0x70,0xaa,0xa8,0x53,0x9f,0xd4,0xb5
};
bool span(uint32_t base, uint32_t bytes, uint32_t limit) {
    return base <= limit && bytes <= limit - base;
}
Result aligned(uint32_t bytes, uint32_t& out) {
    if (!bytes) return Result::Invalid;
    if (bytes > kU32 - 31) return Result::Overflow;
    out = (bytes + 31) & ~31u;
    return Result::Ok;
}
Token empty_token() { return {{0,0},{0,0}}; }
}

const char* result_name(Result r) {
    switch (r) {
    case Result::Ok: return "ok";
    case Result::Invalid: return "invalid";
    case Result::NoSpace: return "no_space";
    case Result::Capacity: return "capacity";
    case Result::Overflow: return "overflow";
    case Result::Stale: return "stale";
    case Result::Busy: return "busy";
    case Result::Cancelled: return "cancelled";
    case Result::State: return "state";
    case Result::Collision: return "collision";
    case Result::Faulted: return "faulted";
    }
    return "unknown";
}
bool equal(Counter a, Counter b) { return a.lo == b.lo && a.hi == b.hi; }
bool equal(Token a, Token b) { return equal(a.epoch,b.epoch) && equal(a.serial,b.serial); }
bool nonzero(Counter a) { return a.lo || a.hi; }
bool greater(Counter a, Counter b) { return a.hi > b.hi || (a.hi == b.hi && a.lo > b.lo); }
Result next_counter(Counter& value) {
    if (value.lo == kU32 && value.hi == kU32) return Result::Overflow;
    if (++value.lo == 0) ++value.hi;
    return Result::Ok;
}

Pool::Pool(uint32_t bytes) : capacity(bytes), free_count(0), allocated_count(0) {
    memset(free_ranges, 0, sizeof(free_ranges));
    memset(allocated, 0, sizeof(allocated));
    if (bytes && !(bytes & 31)) { free_ranges[0] = {0,bytes}; free_count = 1; }
    else capacity = 0;
}
Result Pool::allocate(uint32_t bytes, bool high, Interval& out) {
    out = {0,0};
    uint32_t need;
    Result r = aligned(bytes,need);
    if (r != Result::Ok) return r;
    if (allocated_count == kExtents) return Result::Capacity;
    uint32_t pick = kInvalid;
    for (uint32_t i = 0; i < free_count; ++i) {
        if (free_ranges[i].bytes >= need) { pick = i; if (!high) break; }
    }
    if (pick == kInvalid) return Result::NoSpace;
    Interval& h = free_ranges[pick];
    out = {high ? h.base + h.bytes - need : h.base,need};
    if (high) h.bytes -= need;
    else { h.base += need; h.bytes -= need; }
    if (!h.bytes) {
        for (uint32_t i = pick + 1; i < free_count; ++i) free_ranges[i-1] = free_ranges[i];
        --free_count;
    }
    allocated[allocated_count++] = out;
    return Result::Ok;
}
Result Pool::release(Interval allocation) {
    if (!allocation.bytes || (allocation.base & 31) || (allocation.bytes & 31) ||
        !span(allocation.base,allocation.bytes,capacity)) return Result::Invalid;
    uint32_t record = kInvalid;
    for (uint32_t i=0; i<allocated_count; ++i)
        if (allocated[i].base == allocation.base && allocated[i].bytes == allocation.bytes) { record=i; break; }
    if (record == kInvalid) return Result::Stale; // Partial, forged and duplicate frees cannot create space.
    uint32_t pos=0;
    while (pos<free_count && free_ranges[pos].base < allocation.base) ++pos;
    if ((pos && free_ranges[pos-1].base + free_ranges[pos-1].bytes > allocation.base) ||
        (pos<free_count && allocation.base + allocation.bytes > free_ranges[pos].base)) return Result::Invalid;
    if (free_count == kIntervals) return Result::Capacity;
    for (uint32_t i=free_count; i>pos; --i) free_ranges[i]=free_ranges[i-1];
    free_ranges[pos]=allocation; ++free_count;
    for (uint32_t i=record+1; i<allocated_count; ++i) allocated[i-1]=allocated[i];
    --allocated_count;
    if (pos && free_ranges[pos-1].base + free_ranges[pos-1].bytes == free_ranges[pos].base) {
        free_ranges[pos-1].bytes += free_ranges[pos].bytes;
        for (uint32_t i=pos+1; i<free_count; ++i) free_ranges[i-1]=free_ranges[i];
        --free_count; --pos;
    }
    if (pos+1<free_count && free_ranges[pos].base + free_ranges[pos].bytes == free_ranges[pos+1].base) {
        free_ranges[pos].bytes += free_ranges[pos+1].bytes;
        for (uint32_t i=pos+2; i<free_count; ++i) free_ranges[i-1]=free_ranges[i];
        --free_count;
    }
    return Result::Ok;
}
uint32_t Pool::free_bytes() const {
    uint32_t n=0; for (uint32_t i=0;i<free_count;++i) n+=free_ranges[i].bytes; return n;
}
uint32_t Pool::largest_free() const {
    uint32_t n=0; for (uint32_t i=0;i<free_count;++i) if (free_ranges[i].bytes>n) n=free_ranges[i].bytes; return n;
}
bool Pool::invariant() const {
    if (!capacity || (capacity&31) || free_count>kIntervals || allocated_count>kExtents) return false;
    uint32_t total=0;
    for (uint32_t i=0;i<free_count;++i) {
        const Interval& a=free_ranges[i];
        if (!a.bytes || (a.base&31) || (a.bytes&31) || !span(a.base,a.bytes,capacity)) return false;
        if (i && free_ranges[i-1].base+free_ranges[i-1].bytes>=a.base) return false;
        if (a.bytes>capacity-total) return false;
        total+=a.bytes;
    }
    for (uint32_t i=0;i<allocated_count;++i) {
        const Interval& a=allocated[i];
        if (!a.bytes || (a.base&31) || (a.bytes&31) || !span(a.base,a.bytes,capacity)) return false;
        if (a.bytes>capacity-total) return false;
        total+=a.bytes;
        for (uint32_t j=0;j<i;++j) {
            const Interval& b=allocated[j]; if (a.base<b.base+b.bytes && b.base<a.base+a.bytes) return false;
        }
        for (uint32_t j=0;j<free_count;++j) {
            const Interval& b=free_ranges[j]; if (a.base<b.base+b.bytes && b.base<a.base+a.bytes) return false;
        }
    }
    return total==capacity;
}
bool full_byte_equal(const uint8_t* a,const uint8_t* b,uint32_t bytes) {
    return a && b && bytes && memcmp(a,b,bytes)==0;
}

Core::Core(uint32_t bytes,Counter epoch,uint32_t boot_serial) : pool_(bytes), epoch_(epoch),
    generation_counter_{0,0},lease_counter_{0,0},boot_serial_(boot_serial),faulted_(0),shared_index_(kInvalid) {
    clear_metadata();
    if (!nonzero(epoch) || !boot_serial || !pool_.capacity || bytes > kMixedBytes) faulted_=1;
}
void Core::clear_metadata() {
    memset(generations_,0,sizeof(generations_)); memset(owners_,0,sizeof(owners_));
    memset(extents_,0,sizeof(extents_)); memset(channels_,0,sizeof(channels_));
    memset(maps_,0,sizeof(maps_)); memset(map_owners_,0,sizeof(map_owners_)); memset(map_valid_,0,sizeof(map_valid_));
    for (uint32_t& slot:slots_) slot=kInvalid;
    shared_index_=kInvalid;
}
uint32_t Core::find(Token token) const {
    if (!equal(token.epoch,epoch_) || !nonzero(token.serial)) return kInvalid;
    for (uint32_t i=0;i<kGenerations;++i)
        if (generations_[i].state!=Empty && equal(generations_[i].serial,token.serial)) return i;
    return kInvalid;
}
uint32_t Core::owner_for(uint32_t owner,Token token) const {
    if (!equal(token.epoch,epoch_)) return kInvalid;
    for (uint32_t i=0;i<kOwners;++i)
        if (owners_[i].used && owners_[i].cookie==owner && equal(owners_[i].serial,token.serial)) return i;
    return kInvalid;
}
Token Core::token_for(uint32_t i) const { return i<kGenerations ? Token{epoch_,generations_[i].serial}:empty_token(); }
uint32_t Core::free_extent() const {
    for (uint32_t i=0;i<kExtents;++i) if (!extents_[i].used) return i;
    return kInvalid;
}
uint32_t Core::map_range(uint32_t count) const {
    if (!count || count>kMaps) return kInvalid;
    uint32_t run=0;
    for (uint32_t i=0;i<kMaps;++i) {
        run=map_owners_[i]?0:run+1;
        if (run==count) return i+1-count;
    }
    return kInvalid;
}
void Core::detach_owner(uint32_t gen) {
    for (Owner& owner:owners_) if (owner.used && owner.generation==gen) memset(&owner,0,sizeof(owner));
}
void Core::release_extent(uint32_t index) {
    if (index==kInvalid) return;
    Extent& e=extents_[index];
    if (--e.refs==0) {
        if (pool_.release({e.base,e.bytes})!=Result::Ok) { faulted_=1; return; }
        if (index==shared_index_) shared_index_=kInvalid;
        memset(&e,0,sizeof(e));
    }
}
void Core::collect(uint32_t i) {
    Generation& g=generations_[i];
    if (g.state==Empty || g.upload_ref || g.copies || g.resident_ref || g.pending_refs || g.hardware_refs) return;
    release_extent(g.local_extent); release_extent(g.shared_extent);
    for (uint32_t j=0;j<g.map_count;++j) {
        map_owners_[g.first_map+j]=0; map_valid_[g.first_map+j]=0; maps_[g.first_map+j]={0,0,0};
    }
    detach_owner(i);
    memset(&g,0,sizeof(g));
}
Result Core::begin(uint32_t owner,uint32_t slot,uint32_t bytes,Token& token) {
    token=empty_token();
    if (faulted_) return Result::Faulted;
    if (!owner || slot>=14 || !bytes) return Result::Invalid;
    uint32_t oi=kInvalid,gi=kInvalid;
    for (uint32_t i=0;i<kOwners;++i) {
        if (owners_[i].used && owners_[i].cookie==owner) return Result::Busy;
        if (!owners_[i].used && oi==kInvalid) oi=i;
    }
    for (uint32_t i=0;i<kGenerations;++i) if (generations_[i].state==Empty) {gi=i;break;}
    if (oi==kInvalid || gi==kInvalid) return Result::Capacity;
    Result r=next_counter(generation_counter_); if(r!=Result::Ok)return r;
    Generation& g=generations_[gi]; memset(&g,0,sizeof(g));
    g.serial=generation_counter_; g.state=Receiving;g.source_slot=slot;g.upload_ref=1;
    g.local_extent=g.shared_extent=kInvalid;
    owners_[oi]={1,owner,gi,bytes,0,g.serial}; token=token_for(gi);
    return Result::Ok;
}
Result Core::reserve(Token token,uint32_t count,uint32_t local,const SharedInput* shared) {
    if (faulted_)return Result::Faulted;
    uint32_t gi=find(token);if(gi==kInvalid)return Result::Stale;
    Generation& g=generations_[gi];if(g.state!=Receiving)return Result::State;
    if(!count || count>512)return Result::Capacity;
    uint32_t first=map_range(count);if(first==kInvalid)return Result::Capacity;
    uint32_t aligned_local;Result r=aligned(local,aligned_local);if(r!=Result::Ok)return r;
    uint32_t si=kInvalid; bool created_shared=false;
    if(shared) {
        if(g.source_slot!=3 && g.source_slot!=4)return Result::Invalid;
        if(shared->bytes!=kSharedBytes || memcmp(shared->sha,kSharedSha,32)!=0 || !shared->incoming)return Result::Invalid;
        si=shared_index_;
        if(si!=kInvalid) {
            Extent& e=extents_[si];
            if(e.payload_bytes!=shared->bytes || memcmp(e.sha,shared->sha,32)!=0)return Result::Collision;
            if(!full_byte_equal(shared->incoming,shared->resident_readback,shared->bytes))return Result::Collision;
            if(e.refs==kU32)return Result::Overflow;
        } else {
            si=free_extent();if(si==kInvalid)return Result::Capacity;
            Interval block;r=pool_.allocate(shared->bytes,true,block);if(r!=Result::Ok)return r;
            Extent& e=extents_[si]; memset(&e,0,sizeof(e));e.used=1;e.kind=2;e.base=block.base;e.bytes=block.bytes;
            e.payload_bytes=shared->bytes;e.refs=0;memcpy(e.sha,shared->sha,32);created_shared=true;
        }
    }
    uint32_t li=free_extent();
    if(li==kInvalid) {
        if(created_shared){pool_.release({extents_[si].base,extents_[si].bytes});memset(&extents_[si],0,sizeof(Extent));}
        return Result::Capacity;
    }
    Interval block;r=pool_.allocate(local,g.source_slot==3||g.source_slot==4,block);
    if(r!=Result::Ok) {
        if(created_shared){pool_.release({extents_[si].base,extents_[si].bytes});memset(&extents_[si],0,sizeof(Extent));}
        return r;
    }
    Extent& e=extents_[li];memset(&e,0,sizeof(e));e.used=1;e.kind=1;e.base=block.base;e.bytes=block.bytes;e.payload_bytes=local;e.refs=1;
    if(shared){++extents_[si].refs;shared_index_=si;}
    g.local_extent=li;g.shared_extent=si;g.first_map=first;g.map_count=count;g.state=Reserved;
    for(uint32_t j=0;j<count;++j)map_owners_[first+j]=static_cast<uint8_t>(gi+1);
    return Result::Ok;
}
Result Core::feed(uint32_t owner,Token token,uint32_t offset,uint32_t bytes) {
    if(faulted_)return Result::Faulted;
    uint32_t oi=owner_for(owner,token);if(oi==kInvalid)return Result::Stale;
    Owner& o=owners_[oi];Generation& g=generations_[o.generation];
    if(g.state!=Receiving && g.state!=Reserved)return Result::State;
    if(!bytes || offset!=o.received_bytes || !span(offset,bytes,o.expected_bytes))return Result::Invalid;
    o.received_bytes+=bytes;return Result::Ok;
}
Result Core::copy_begin(Token token) {
    if(faulted_)return Result::Faulted;
    uint32_t gi=find(token);if(gi==kInvalid)return Result::Stale;
    Generation& g=generations_[gi];if(g.state!=Reserved)return Result::State;
    if(g.copies==kU32)return Result::Overflow;
    ++g.copies;return Result::Ok;
}
Result Core::copy_end(Token token) {
    uint32_t gi=find(token);if(gi==kInvalid)return Result::Stale;
    Generation& g=generations_[gi];if(!g.copies)return Result::State;
    --g.copies;collect(gi);return Result::Ok;
}
Result Core::verify(uint32_t owner,Token token,bool ok) {
    if(faulted_)return Result::Faulted;
    uint32_t oi=owner_for(owner,token);if(oi==kInvalid)return Result::Stale;
    Owner& o=owners_[oi];Generation& g=generations_[o.generation];
    if(g.state!=Reserved)return Result::State;
    if(o.received_bytes!=o.expected_bytes || g.copies)return Result::Busy;
    if(!ok){cancel(owner,token);return Result::Invalid;}
    for(uint32_t i=0;i<g.map_count;++i)if(!map_valid_[g.first_map+i])return Result::Invalid;
    g.state=Verified;return Result::Ok;
}
Result Core::publish(uint32_t owner,Token token) {
    if(faulted_)return Result::Faulted;
    uint32_t oi=owner_for(owner,token);if(oi==kInvalid)return Result::Stale;
    uint32_t gi=owners_[oi].generation;Generation& g=generations_[gi];
    if(g.state!=Verified || g.copies)return Result::State;
    if(slots_[g.source_slot]!=kInvalid)return Result::Busy;
    g.resident_ref=1;g.upload_ref=0;slots_[g.source_slot]=gi;g.state=Published;detach_owner(gi);
    return Result::Ok;
}
Result Core::cancel(uint32_t owner,Token token) {
    uint32_t oi=owner_for(owner,token);if(oi==kInvalid)return Result::Stale;
    uint32_t gi=owners_[oi].generation;Generation& g=generations_[gi];
    if(g.state==Published || g.state==Retired)return Result::State;
    g.state=Aborted;g.upload_ref=0;detach_owner(gi);collect(gi);return Result::Ok;
}
Result Core::retire_bank(Token token) {
    uint32_t gi=find(token);if(gi==kInvalid)return Result::Stale;
    Generation& g=generations_[gi];
    if(g.state==Retired)return Result::Ok;
    if(g.state!=Published || slots_[g.source_slot]!=gi)return Result::State;
    slots_[g.source_slot]=kInvalid;g.resident_ref=0;g.state=Retired;collect(gi);return Result::Ok;
}
Result Core::pin_pending(Token token) {
    if(faulted_)return Result::Faulted;
    uint32_t gi=find(token);if(gi==kInvalid)return Result::Stale;
    Generation& g=generations_[gi];if(g.state!=Published || !g.resident_ref)return Result::State;
    if(g.pending_refs==kU32)return Result::Overflow;
    ++g.pending_refs;return Result::Ok;
}
Result Core::drop_pending(Token token) {
    uint32_t gi=find(token);if(gi==kInvalid)return Result::Stale;
    Generation& g=generations_[gi];if(!g.pending_refs)return Result::State;
    --g.pending_refs;collect(gi);return Result::Ok;
}
Result Core::start_channel(uint32_t ch,Token token,uint32_t address,Token& lease) {
    lease=empty_token();if(faulted_)return Result::Faulted;
    if(ch>=kChannels)return Result::Invalid;
    uint32_t gi=find(token);if(gi==kInvalid)return Result::Stale;
    Generation& g=generations_[gi];if(!g.pending_refs || (g.state!=Published && g.state!=Retired))return Result::State;
    bool owned=false;
    for(uint32_t ei:{g.local_extent,g.shared_extent}) {
        if(ei!=kInvalid){const Extent& e=extents_[ei];if(address>=e.base && address-e.base<e.payload_bytes)owned=true;}
    }
    if(!owned)return Result::Invalid;
    Channel& c=channels_[ch];
    if(c.state!=ChannelFree)return Result::Busy;
    if(g.hardware_refs==kU32)return Result::Overflow;
    Result r=next_counter(lease_counter_);if(r!=Result::Ok)return r;
    memset(&c,0,sizeof(c));c.state=ChannelActive;c.generation=gi;c.generation_serial=g.serial;c.lease=lease_counter_;
    c.request={0,epoch_,c.lease,0,address,0};--g.pending_refs;++g.hardware_refs;lease={epoch_,c.lease};return Result::Ok;
}
Result Core::reuse_same_generation(uint32_t ch,Token previous,Token token,uint32_t address,Token& lease) {
    lease=empty_token();
    if(faulted_)return Result::Faulted;
    if(ch>=kChannels)return Result::Invalid;
    uint32_t gi=find(token);if(gi==kInvalid)return Result::Stale;
    Channel& c=channels_[ch];Generation& g=generations_[gi];
    if(c.state==ChannelFree || !equal(previous.epoch,epoch_) || !equal(previous.serial,c.lease))return Result::Stale;
    if(c.generation!=gi || !equal(c.generation_serial,g.serial))return Result::Busy;
    if(!g.pending_refs || (g.state!=Published && g.state!=Retired))return Result::State;
    bool owned=false;
    for(uint32_t ei:{g.local_extent,g.shared_extent}) {
        if(ei!=kInvalid){const Extent& e=extents_[ei];if(address>=e.base && address-e.base<e.payload_bytes)owned=true;}
    }
    if(!owned)return Result::Invalid;
    Result r=next_counter(lease_counter_);if(r!=Result::Ok)return r;
    // Transfer the existing hardware pin, rather than dropping and reacquiring.
    c.state=ChannelActive;c.lease=lease_counter_;c.request={0,epoch_,c.lease,0,address,0};
    --g.pending_refs;lease={epoch_,c.lease};return Result::Ok;
}
Result Core::retire_channel(uint32_t ch,Token lease,Request& request) {
    if(faulted_)return Result::Faulted;
    if(ch>=kChannels)return Result::Invalid;
    Channel& c=channels_[ch];
    if(!equal(lease.epoch,epoch_) || !equal(c.lease,lease.serial) || c.state==ChannelFree)return Result::Stale;
    if(c.state==ChannelRetiring){request=c.request;return Result::Ok;}
    if(c.request.sequence>kU32-2)return Result::Overflow;
    c.request.sequence+=2;c.request.opcode=1;c.state=ChannelRetiring;request=c.request;return Result::Ok;
}
Result Core::acknowledge(uint32_t ch,const Ack& ack) {
    if(faulted_)return Result::Faulted;
    if(ch>=kChannels)return Result::Invalid;
    Channel& c=channels_[ch];const Request& req=c.request;
    if(c.state!=ChannelRetiring || !ack.sequence || (ack.sequence&1) || ack.sequence!=req.sequence ||
       !equal(ack.epoch,epoch_) || !equal(ack.epoch,req.epoch) || !equal(ack.lease,c.lease) ||
       ack.boot_serial!=boot_serial_ || ack.flags!=3)return Result::Stale;
    uint32_t gi=c.generation;Generation& g=generations_[gi];
    if(!equal(g.serial,c.generation_serial) || !g.hardware_refs){faulted_=1;return Result::Faulted;}
    // No EG calculation here. This only consumes an externally supplied fence.
    --g.hardware_refs;memset(&c,0,sizeof(c));collect(gi);return Result::Ok;
}
Result Core::observe_boot(uint32_t serial) {
    if(serial!=boot_serial_){faulted_=1;return Result::Faulted;}
    return faulted_?Result::Faulted:Result::Ok;
}
Result Core::controlled_reset(Counter next,uint32_t boot,bool qualified) {
    if(!qualified || !nonzero(next) || !greater(next,epoch_) || !boot)return Result::Invalid;
    for(const Generation& g:generations_)if(g.copies || g.pending_refs)return Result::Busy;
    // External all-channel quiescence is an explicit assumption of this call.
    uint32_t capacity=pool_.capacity;pool_=Pool(capacity);clear_metadata();epoch_=next;boot_serial_=boot;
    generation_counter_={0,0};lease_counter_={0,0};faulted_=0;return Result::Ok;
}
Result Core::set_map(Token token,uint32_t index,LogicalMap map) {
    if(faulted_)return Result::Faulted;
    uint32_t gi=find(token);if(gi==kInvalid)return Result::Stale;
    Generation& g=generations_[gi];if(g.state!=Reserved || index>=g.map_count)return Result::Invalid;
    uint32_t address=map.aica_shift&0xffffffu,shift=(map.aica_shift>>24)&3u;
    if(!map.length || (map.aica_shift&0x7c000000u) || !(map.aica_shift&0x80000000u))return Result::Invalid;
    // Round-up and byte formula use a wide intermediate only in local arithmetic,
    // never in stored metadata. Validate the whole sample range, not just its SA.
    uint64_t frames=(static_cast<uint64_t>(map.length)+(1u<<shift)-1)>>shift;
    uint64_t need=((frames+7)/8)*4;
    if(need>kU32)return Result::Overflow;
    bool owned=false;
    for(uint32_t ei:{g.local_extent,g.shared_extent}) {
        if(ei!=kInvalid){const Extent& e=extents_[ei];if(address>=e.base && span(address-e.base,static_cast<uint32_t>(need),e.payload_bytes))owned=true;}
    }
    if(!owned)return Result::Invalid;
    maps_[g.first_map+index]=map;map_valid_[g.first_map+index]=1;return Result::Ok;
}
Result Core::resolve(Token token,uint32_t index,LogicalMap& out) const {
    if(faulted_)return Result::Faulted;
    uint32_t gi=find(token);if(gi==kInvalid)return Result::Stale;
    const Generation& g=generations_[gi];
    if(g.state!=Published || !g.resident_ref || index>=g.map_count || !map_valid_[g.first_map+index])return Result::State;
    out=maps_[g.first_map+index];return Result::Ok;
}
Token Core::current(uint32_t slot) const { return slot<14 && slots_[slot]!=kInvalid?token_for(slots_[slot]):empty_token(); }
const Generation* Core::inspect(Token token) const {uint32_t i=find(token);return i==kInvalid?nullptr:&generations_[i];}
const Extent* Core::extent(uint32_t i) const {return i<kExtents && extents_[i].used?&extents_[i]:nullptr;}
const Channel* Core::channel(uint32_t i) const {return i<kChannels?&channels_[i]:nullptr;}
uint32_t Core::active_generations() const {uint32_t n=0;for(const Generation& g:generations_)n+=g.state!=Empty;return n;}
uint32_t Core::maps_used() const {uint32_t n=0;for(uint8_t o:map_owners_)n+=o!=0;return n;}
uint32_t Core::owners_used() const {uint32_t n=0;for(const Owner& o:owners_)n+=o.used!=0;return n;}
uint32_t Core::active_channels() const {uint32_t n=0;for(const Channel& c:channels_)n+=c.state!=ChannelFree;return n;}
bool Core::invariant() const {
    if(!pool_.invariant())return false;
    uint32_t refs[kExtents]={0},hw[kGenerations]={0},owners[kGenerations]={0};
    for(const Owner& o:owners_) {
        if(!o.used)continue;
        if(o.generation>=kGenerations || o.received_bytes>o.expected_bytes || !o.cookie)return false;
        const Generation& g=generations_[o.generation];if(g.state==Empty || !g.upload_ref || !equal(g.serial,o.serial))return false;
        ++owners[o.generation];
    }
    for(const Channel& c:channels_) {
        if(c.state==ChannelFree)continue;
        if(c.generation>=kGenerations || !nonzero(c.lease))return false;
        const Generation& g=generations_[c.generation];if(g.state==Empty || !equal(c.generation_serial,g.serial))return false;
        ++hw[c.generation];
        if(c.state==ChannelRetiring && (!c.request.sequence || (c.request.sequence&1) || c.request.opcode!=1 ||
           !equal(c.request.epoch,epoch_) || !equal(c.request.lease,c.lease)))return false;
    }
    uint32_t gm=0;
    for(uint32_t i=0;i<kGenerations;++i) {
        const Generation& g=generations_[i];if(g.state==Empty){if(hw[i] || owners[i])return false;continue;}
        if(!nonzero(g.serial) || g.source_slot>=14 || g.hardware_refs!=hw[i] || g.upload_ref!=owners[i] || g.resident_ref>1)return false;
        if(g.resident_ref && slots_[g.source_slot]!=i)return false;
        if(!span(g.first_map,g.map_count,kMaps))return false;
        gm+=g.map_count;
        for(uint32_t j=0;j<g.map_count;++j)if(map_owners_[g.first_map+j]!=i+1)return false;
        for(uint32_t ei:{g.local_extent,g.shared_extent})if(ei!=kInvalid){if(ei>=kExtents || !extents_[ei].used)return false;++refs[ei];}
    }
    if(gm!=maps_used())return false;
    uint32_t es=0;
    for(uint32_t i=0;i<kExtents;++i) {
        const Extent& e=extents_[i];if(!e.used){if(refs[i])return false;continue;}
        if(!refs[i] || refs[i]!=e.refs || !e.payload_bytes || e.payload_bytes>e.bytes)return false;
        bool found=false;for(uint32_t j=0;j<pool_.allocated_count;++j)
            if(pool_.allocated[j].base==e.base && pool_.allocated[j].bytes==e.bytes)found=true;
        if(!found)return false;
        ++es;
    }
    if(es!=pool_.allocated_count)return false;
    if(shared_index_!=kInvalid && (!extents_[shared_index_].used || extents_[shared_index_].kind!=2))return false;
    for(uint32_t slot=0;slot<14;++slot)if(slots_[slot]!=kInvalid){
        if(slots_[slot]>=kGenerations)return false;
        const Generation& g=generations_[slots_[slot]];
        if(g.state!=Published || !g.resident_ref || g.source_slot!=slot)return false;
    }
    return true;
}
} // namespace re4dc_aic2
#endif
