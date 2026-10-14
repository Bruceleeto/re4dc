// Actual production ledger, shared with host lifetime/guard-page tests.
// This class never reads through base or frees it. The Room4 owner validates its
// generation/range BEFORE either it or callers may touch retained bytes.
namespace movie_world {
constexpr unsigned arena_bytes=363360, max_slots=13;
enum class Phase { retired, ready, borrowed, returning, failed };
struct Slot { void* p=nullptr; unsigned bytes=0; bool live=false; };
struct Ledger {
    void* base=nullptr; unsigned capacity=0,generation=0,serial=0,used=0,nslots=0,live=0,readers=0,blocked=0;
    Phase phase=Phase::retired; Slot slots[max_slots]{};
    bool unavailable() const { return phase==Phase::borrowed || phase==Phase::returning || phase==Phase::failed; }
    bool capture(void* p,unsigned cap,unsigned gen) {
        if(unavailable() || readers || !p || cap<arena_bytes || (reinterpret_cast<uintptr_t>(p)&31))return false;
        base=p;capacity=cap;generation=gen;phase=Phase::ready;return true;
    }
    unsigned borrow(bool owner_valid,bool fence_ready) {
        if(!owner_valid || !fence_ready || phase!=Phase::ready || readers || !base || capacity<arena_bytes)return 0;
        if(++serial==0)++serial;
        used=nslots=live=0;for(auto& s:slots)s=Slot{};phase=Phase::borrowed;return serial;
    }
    bool valid(unsigned token,bool owner_valid) const {
        return owner_valid && token && token==serial && phase==Phase::borrowed;
    }
    // Exact full-range 288x192 split-plane production request multiset. A new
    // decoder/service allocation requires review; it cannot silently use heap 4.
    bool allowed(unsigned bytes) const {
        unsigned limit=0;
        switch(bytes){case 52:case 716:case 16416:case 49152:case 32768:case 65536:case 32800:limit=1;break;
        case 55296:limit=2;break;case 13824:limit=4;break;default:return false;}
        unsigned seen=0;for(unsigned i=0;i<nslots;++i)seen+=slots[i].bytes==bytes;return seen<limit;
    }
    void* alloc(unsigned token,unsigned bytes,bool owner_valid) {
        if(!valid(token,owner_valid) || nslots==max_slots || !allowed(bytes))return nullptr;
        const unsigned padded=(bytes+31)&~31u;
        if(padded>arena_bytes-used || padded>capacity-used)return nullptr;
        auto* p=static_cast<unsigned char*>(base)+used;used+=padded;
        slots[nslots++]={p,bytes,true};++live;return p;
    }
    bool release(unsigned token,void* p,bool owner_valid) {
        if(!valid(token,owner_valid) || !p)return false;
        for(unsigned i=0;i<nslots;++i)if(slots[i].p==p){
            if(!slots[i].live)return false;
            slots[i].live=false;--live;return true;
        }
        return false;
    }
    bool begin_return(unsigned token,bool owner_valid) {
        if(!valid(token,owner_valid) || live || readers)return false;
        phase=Phase::returning;return true;
    }
    bool restored(unsigned token,bool owner_valid,bool identity) {
        if(!owner_valid || token!=serial || phase!=Phase::returning || readers)return false;
        phase=identity?Phase::ready:Phase::failed;return identity;
    }
    bool retire(unsigned token,bool owner_valid) {
        if(!owner_valid || readers || live || (unavailable() && token!=serial))return false;
        phase=Phase::retired;base=nullptr;capacity=generation=used=nslots=0;
        if(++serial==0)++serial;
        return true;
    }
};
inline unsigned fnv(const unsigned char* p,unsigned n){
    unsigned h=2166136261u;for(unsigned i=0;i<n;++i)h=(h^p[i])*16777619u;return h;
}
}
