#ifndef RE4DC_COARSE_SOURCE_FRAME_H
#define RE4DC_COARSE_SOURCE_FRAME_H

#include <cstddef>
#include <cstdint>
#if defined(__sh__)
// Match cManager.h/cam_extra.h: the recovered target <new> compatibility
// header omits placement new. Share its guard to avoid a duplicate overload.
#ifndef PLACEMENT_NEW_DEFINED
#define PLACEMENT_NEW_DEFINED
inline void* operator new(unsigned int, void* p) { return p; }
#endif
#else
#include <new>
#endif

namespace re4dc_source {

// No allocator, game pointers to dereference, rendering, callbacks or globals.
// The future Trans owner must retire this ledger BEFORE resetting/freeing the
// borrowed primitive buffer. Only value tickets escape; entries never do.
struct FrameIdentity {
    std::uint32_t frame, room, room_generation, primitive_epoch;
    std::uint32_t enemy_generation, object_generation;
    bool operator==(const FrameIdentity& b) const {
        return frame==b.frame && room==b.room && room_generation==b.room_generation &&
            primitive_epoch==b.primitive_epoch && enemy_generation==b.enemy_generation &&
            object_generation==b.object_generation;
    }
};
struct ModelIdentity {
    std::uintptr_t address;
    std::uint32_t serial, manager;
    bool operator==(const ModelIdentity& b) const {
        return address==b.address && serial==b.serial && manager==b.manager;
    }
};
enum class ModelPath : std::uint32_t { Coarse=0, Source=1 };
enum class Membership : std::uint32_t { Unknown=0, Coarse=1, SourceHandled=2 };
struct FrameEntry {
    ModelIdentity model;
    std::uint32_t reasons;
    ModelPath path;
    std::uint32_t prepared;
#if RE4DC_ACTOR_TRANSACTION
    std::uint32_t presentation=0;
#endif

};
struct PreparationTicket {
    ModelIdentity model;
    std::uint32_t revision, index;
};

class FrameLedger {
public:
    static constexpr std::uint32_t MaxEntries=256;
    FrameLedger(): entries_(nullptr), capacity_(0), expected_(0), count_(0),
        cursor_(0), revision_(0), phase_(Empty), identity_{} {}
    FrameLedger(const FrameLedger&)=delete;
    FrameLedger& operator=(const FrameLedger&)=delete;

    static bool storage_bytes(std::uint32_t count, std::size_t& bytes) {
        if (count>MaxEntries) return false;
        bytes=sizeof(FrameEntry)*count;
        return true;
    }
    void retire() {
        // Clear the borrowed address first. A same-frame rebind cannot make an
        // old ticket valid; exhausted revision space fails closed until reboot.
        entries_=nullptr;
        capacity_=expected_=count_=cursor_=0;
        phase_=Empty;
        if (revision_!=UINT32_MAX) ++revision_;
    }
    bool begin(void* storage, std::size_t bytes, std::uint32_t expected,
               const FrameIdentity& identity) {
        retire();
        if (revision_==UINT32_MAX || expected>MaxEntries ||
            (expected && (!storage || reinterpret_cast<std::uintptr_t>(storage)%alignof(FrameEntry))) ||
            bytes/sizeof(FrameEntry)<expected) return fail();
        entries_=static_cast<FrameEntry*>(storage);
        capacity_=expected_=expected;
        identity_=identity;
        phase_=Building;
        return true;
    }
    bool append(const FrameIdentity& now, const ModelIdentity& model,
                ModelPath path, std::uint32_t reasons) {
        if (!valid(now) || phase_!=Building || count_>=capacity_ || !model.address ||
            model.manager>3 || (path!=ModelPath::Coarse && path!=ModelPath::Source)) return fail();
        // A source object belongs to exactly one source manager walk. Reject a
        // repeated address even with a changed serial: never prepare recycled
        // storage twice within this frame or accept an accidental second walk.
        for (std::uint32_t k=0;k<count_;++k)
            if (entries_[k].model.address==model.address) return fail();
        ::new (static_cast<void*>(entries_+count_++)) FrameEntry{model,reasons,path,0};
        return true;
    }
    bool seal(const FrameIdentity& now) {
        if (!valid(now) || phase_!=Building || count_!=expected_) return fail();
        phase_=Sealed;
        skip_coarse();
        return true;
    }
    bool claim(const FrameIdentity& now, PreparationTicket& ticket) {
        if (!valid(now) || phase_!=Sealed) return false;
        // A single in-flight ticket prevents reentrancy or a second preparation
        // claim before the original source callback has returned.
        const FrameEntry& e=entries_[cursor_];
        ticket={e.model,revision_,cursor_};
        phase_=Claimed;
        return true;
    }
    bool complete(const FrameIdentity& now, const PreparationTicket& ticket,
                  const ModelIdentity& current_model) {
        if (!valid(now) || phase_!=Claimed || ticket.revision!=revision_ ||
            ticket.index!=cursor_ || !(ticket.model==current_model) ||
            !(entries_[cursor_].model==current_model)) return fail();
        // "Handled" means original objTrans/emTrans was called once. It does
        // NOT mean visible, prepared successfully, or drawn: source culling,
        // commonScreenMat failure and OT registration remain authoritative.
        entries_[cursor_].prepared=1;
        ++cursor_;
        phase_=Sealed;
        skip_coarse();
        return true;
    }
    Membership membership(const FrameIdentity& now, const ModelIdentity& model) const {
        // This guard precedes every borrowed-storage read. Retired/rebound or
        // changed-frame/owner/manager identities never authorize suppression.
        // Unknown is an invalid plan, not permission to fall through to ribbons.
        if (!valid(now) || phase_!=Ready) return Membership::Unknown;
        for (std::uint32_t k=0;k<count_;++k) if (entries_[k].model==model) {
            const FrameEntry& e=entries_[k];
            return e.path==ModelPath::Coarse ? Membership::Coarse :
                e.prepared ? Membership::SourceHandled : Membership::Unknown;
        }
        return Membership::Unknown;
    }
    bool ready(const FrameIdentity& now) const { return valid(now) && phase_==Ready; }
    bool failed() const { return phase_==Failed; }


#if RE4DC_ACTOR_TRANSACTION
#include "source_actor_owner_ledger.inc"
#endif
private:
    enum Phase { Empty, Building, Sealed, Claimed, Ready, Failed };
    bool valid(const FrameIdentity& now) const {
        return phase_!=Empty && phase_!=Failed && identity_==now;
    }
    bool fail() { phase_=Failed; return false; }
    void skip_coarse() {
        while (cursor_<count_ && entries_[cursor_].path==ModelPath::Coarse) ++cursor_;
        if (cursor_==count_) phase_=Ready;
    }
    FrameEntry* entries_;
    std::uint32_t capacity_, expected_, count_, cursor_, revision_;
    Phase phase_;
    FrameIdentity identity_;
};
}
#endif
