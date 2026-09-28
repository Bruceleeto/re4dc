#pragma once
#include <cstdint>
#include <cstddef>

namespace re4dc_actor {
struct PaletteLease { unsigned slot=0,serial=0; };

// One primitive-backed arena per source frame. Never releases the primitive
// backing allocation; only reuses matrices whose CPU consumers were revoked.
// The native actor submit path consumes palettes synchronously. The GPU sees
// submitted vertices, not these matrices. Second-OT-pass actors retain leases.
class PaletteArena {
    struct Slot { unsigned offset=0,bytes=0,serial=0; };
    static constexpr unsigned kSlots=64;
    Slot slots_[kSlots]{};
    unsigned char* base_=nullptr;
    unsigned capacity_=0,serial_=0;
public:
    PaletteArena()=default;
    PaletteArena(const PaletteArena&)=delete;
    PaletteArena& operator=(const PaletteArena&)=delete;
    bool bound()const {return base_!=nullptr;}
    bool bind(void* memory,unsigned bytes) {
        const auto address=reinterpret_cast<std::uintptr_t>(memory);
        if(base_ || !memory || (address&31u) || !bytes || (bytes&31u) ||
           bytes>65536u || address>UINTPTR_MAX-bytes)return false;
        for(const auto& s:slots_)if(s.serial)return false;
        base_=static_cast<unsigned char*>(memory);capacity_=bytes;return true;
    }
    bool acquire(unsigned bytes,PaletteLease& out) {
        if(!base_ || !bytes || (bytes&31u) || bytes>capacity_ ||
           out.slot || out.serial || serial_==UINT32_MAX)return false;
        unsigned free_slot=kSlots;
        for(unsigned i=0;i<kSlots;++i)if(!slots_[i].serial){free_slot=i;break;}
        if(free_slot==kSlots)return false;
        // First fit over at most64 live allocations. Each collision advances
        // offset past one allocation, so the bounded loop cannot cycle.
        unsigned offset=0;
        for(unsigned pass=0;pass<=kSlots;++pass) {
            if(offset>capacity_ || bytes>capacity_-offset)return false;
            bool collision=false;
            for(const auto& s:slots_)if(s.serial && offset<s.offset+s.bytes && s.offset<offset+bytes) {
                offset=s.offset+s.bytes;collision=true;break;
            }
            if(collision)continue;
            const unsigned serial=++serial_;
            slots_[free_slot]={offset,bytes,serial};out={free_slot+1,serial};return true;
        }
        return false;
    }
    void* data(const PaletteLease& lease,unsigned exact_bytes)const {
        if(!base_ || !lease.slot || lease.slot>kSlots || !lease.serial)return nullptr;
        const auto& s=slots_[lease.slot-1];
        if(s.serial!=lease.serial || s.bytes!=exact_bytes ||
           s.offset>capacity_ || s.bytes>capacity_-s.offset)return nullptr;
        return base_+s.offset;
    }
    bool release(PaletteLease& lease) {
        if(!lease.slot && !lease.serial)return true;
        if(!base_ || !lease.slot || lease.slot>kSlots || !lease.serial ||
           slots_[lease.slot-1].serial!=lease.serial) {lease={};return false;}
        slots_[lease.slot-1]={};lease={};return true;
    }
    void retire() {
        // Caller first revokes skin registry and cached frame pointers. No
        // reads through base_ or stale primitive records occur during retire.
        base_=nullptr;capacity_=0;
        for(auto& s:slots_)s={};
        // Retain serial_ across frames: old copied leases never become valid.
    }
};
}
