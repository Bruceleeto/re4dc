#pragma once
#include <cstdint>
#include <cstring>

// Read-only MCHECK_PT observer. Sizes follow Flycast's ta.cpp TaTypeLut / TA
// state machine and KOS pvr_vertex_tpcm_t, pvr_sprite_* and pvr_modifier_vol_t.
// A continuation has no PCW: even header-looking words there are payload.
namespace re4dc_pt_audit {
enum Reason : unsigned {
    None, InvalidList, InvalidBytes, InvalidMarker, HeaderListMismatch,
    InvalidCommand, InvalidFormat, OrphanVertex, IncompletePacket,
    ReopenedList, MissingMarker
};
struct Stats {
    unsigned headers{}, bad{}, invalid{}, incomplete{}, reason{};
    std::uint32_t w0{}, w2{};
    std::uintptr_t caller{};
};
class Decoder {
    struct List {
        bool header{}, vertex64{}, tail{}, poisoned{};
    } lists_[5]{};
    unsigned active_{5}, opened_{};
    Stats stats_{};
    void invalid(Reason why) {
        ++stats_.invalid;
        if (!stats_.reason) stats_.reason=why;
    }
    void close_tail(List& s) {
        if (!s.tail) return;
        ++stats_.incomplete;
        if (!stats_.reason) stats_.reason=IncompletePacket;
        s.tail=false;
        s.poisoned=true;
    }
    void marker(unsigned list) {
        // The hash hook's marker is emitted after KOS ends the previous list.
        // A half-packet cannot legally continue across that boundary.
        if (active_<5) close_tail(lists_[active_]);
        if (opened_ & (1u<<list)) invalid(ReopenedList);
        opened_|=1u<<list;
        lists_[list]=List{};
        active_=list;
    }
    void block(unsigned list,const std::uint32_t* q,std::uintptr_t caller) {
        List& s=lists_[list];
        if (s.poisoned) return; // no trustworthy framing after a malformed burst
        if (s.tail) { s.tail=false; return; }
        const unsigned pcw=q[0],type=pcw>>29;
        if (type==0) { s=List{}; return; } // end of list
        if (type==1 || type==2) return;    // user clip / object list set: 32 B
        if (type==4 || type==5) {
            if (((pcw>>24)&7u)!=list) invalid(HeaderListMismatch);
            const bool modifier=list==1 || list==3;
            const bool sprite=type==5,texture=(pcw&8u)!=0,volume=(pcw&64u)!=0;
            const unsigned color=(pcw>>4)&3u;
            if ((modifier && sprite) || (!modifier && !sprite && volume && color==1)) {
                invalid(InvalidFormat); s.poisoned=true; return;
            }
            s.header=true;
            s.vertex64=modifier || sprite || (texture && (color==1 || volume));
            s.tail=!modifier && !sprite && color==2 && (volume || (texture && (pcw&4u)));
            if (list==4) {
                ++stats_.headers;
                if ((q[2]>>29)!=4u || ((q[2]>>26)&7u)!=5u) {
                    if (!stats_.bad) { stats_.w0=q[0]; stats_.w2=q[2]; stats_.caller=caller; }
                    ++stats_.bad;
                }
            }
            return;
        }
        if (type==7) {
            if (!s.header) { invalid(OrphanVertex); s.poisoned=true; return; }
            s.tail=s.vertex64;
            return;
        }
        invalid(InvalidCommand); // reserved parameter types 3 / 6
        s.poisoned=true;
    }
public:
    void feed(unsigned list,const void* data,unsigned bytes,std::uintptr_t caller=0) {
        if (list>=5) { invalid(InvalidList); return; }
        if (!bytes) return;
        if (!data) { invalid(InvalidBytes); lists_[list].poisoned=true; return; }
        const auto* raw=static_cast<const unsigned char*>(data);
        if (bytes==4) {
            std::uint32_t tag; std::memcpy(&tag,raw,4);
            if (tag==(0xf00d0000u|list)) marker(list);
            else { invalid(InvalidMarker); lists_[list].poisoned=true; }
            return;
        }
        if (bytes%32) { invalid(InvalidBytes); lists_[list].poisoned=true; return; }
        if (active_!=list) { invalid(MissingMarker); active_=list; }
        for (unsigned offset=0;offset<bytes;offset+=32) {
            std::uint32_t q[8]; // avoid alignment/aliasing assumptions about observed buffers
            std::memcpy(q,raw+offset,32);
            block(list,q,caller);
        }
    }
    Stats finish_scene() {
        for (auto& s:lists_) close_tail(s);
        const Stats result=stats_;
        *this=Decoder{};
        return result;
    }
};
} // namespace re4dc_pt_audit
