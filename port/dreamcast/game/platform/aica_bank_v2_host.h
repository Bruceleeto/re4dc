#ifndef RE4DC_AICA_BANK_V2_HOST_H
#define RE4DC_AICA_BANK_V2_HOST_H
#ifndef RE4DC_AICA_BANK_V2
#define RE4DC_AICA_BANK_V2 0
#endif
#if RE4DC_AICA_BANK_V2
#include <stdint.h>
#include <stddef.h>

// Phase 1: platform-only metadata core. No KOS, MMIO, source loader or locks.
// The caller serializes mutations. Hardware acknowledgements are external
// inputs, not a hardware predicate implemented or qualified by this module.
namespace re4dc_aic2 {
constexpr uint32_t kMixedBytes = 1298784;
constexpr uint32_t kMaps = 640;
constexpr uint32_t kGenerations = 32;
constexpr uint32_t kOwners = 16;
constexpr uint32_t kChannels = 64;
constexpr uint32_t kExtents = 64;
constexpr uint32_t kIntervals = 66;
constexpr uint32_t kInvalid = 0xffffffffu;
constexpr uint32_t kSharedBytes = 27040;

enum class Result : uint32_t {
    Ok, Invalid, NoSpace, Capacity, Overflow, Stale, Busy, Cancelled,
    State, Collision, Faulted
};
const char* result_name(Result r);
struct Counter { uint32_t lo, hi; };
struct Token { Counter epoch, serial; };
bool equal(Counter a, Counter b);
bool equal(Token a, Token b);
bool nonzero(Counter a);
bool greater(Counter a, Counter b);
Result next_counter(Counter& value);

struct Interval { uint32_t base, bytes; };
struct Pool {
    Interval free_ranges[kIntervals];
    Interval allocated[kExtents];
    uint32_t capacity, free_count, allocated_count;
    explicit Pool(uint32_t bytes = kMixedBytes);
    Result allocate(uint32_t bytes, bool high, Interval& out);
    Result release(Interval allocation);
    uint32_t free_bytes() const;
    uint32_t largest_free() const;
    bool invariant() const;
};

// The on-wire mailbox layouts deliberately contain only 32-bit fields.
struct Request {
    uint32_t sequence;
    Counter epoch, lease;
    uint32_t opcode, expected_sample_address, reserved;
};
struct Ack {
    uint32_t sequence;
    Counter epoch, lease;
    uint32_t boot_serial, observed_eg, flags;
};
static_assert(sizeof(Request) == 32 && sizeof(Ack) == 32, "mailbox ABI");
static_assert(alignof(Request) == 4 && alignof(Ack) == 4, "mailbox alignment");

// The parser must validate the incoming digest and whitelist before reserve().
// This metadata-only core compares full bytes on a hit; it does not perform
// transfers or prove that a readback buffer came from physical AICA memory.
struct SharedInput {
    uint32_t bytes;
    uint8_t sha[32];
    const uint8_t* incoming;
    // Required for a registry hit: complete independently read-back bytes.
    const uint8_t* resident_readback;
};
bool full_byte_equal(const uint8_t* a, const uint8_t* b, uint32_t bytes);

struct LogicalMap { uint32_t gc_nibble, length, aica_shift; };
struct Generation {
    Counter serial;
    uint32_t state, source_slot, first_map, map_count;
    uint32_t upload_ref, copies, resident_ref, pending_refs, hardware_refs;
    uint32_t local_extent, shared_extent;
};
struct Owner {
    uint32_t used, cookie, generation, expected_bytes, received_bytes;
    Counter serial;
};
struct Extent {
    uint32_t used, kind, base, bytes, payload_bytes, refs;
    uint8_t sha[32];
};
struct Channel {
    uint32_t state, generation;
    Counter generation_serial, lease;
    Request request;
};

class Core {
public:
    explicit Core(uint32_t bytes = kMixedBytes, Counter epoch = {1, 0}, uint32_t boot_serial = 1);
    Result begin(uint32_t owner, uint32_t source_slot, uint32_t expected_bytes, Token& token);
    Result reserve(Token token, uint32_t map_count, uint32_t local_bytes, const SharedInput* shared = nullptr);
    Result feed(uint32_t owner, Token token, uint32_t offset, uint32_t bytes);
    Result copy_begin(Token token);
    Result copy_end(Token token);
    Result verify(uint32_t owner, Token token, bool full_logical_readback_ok);
    Result publish(uint32_t owner, Token token);
    Result cancel(uint32_t owner, Token token);
    Result retire_bank(Token token);
    Result pin_pending(Token token);
    Result drop_pending(Token token);
    Result start_channel(uint32_t channel, Token bank, uint32_t sample_address, Token& lease);
    Result reuse_same_generation(uint32_t channel, Token previous, Token bank, uint32_t sample_address, Token& lease);
    Result retire_channel(uint32_t channel, Token lease, Request& request);
    // Ack flags VALID|INACTIVE must be supplied by a qualified external source.
    // observed_eg is diagnostic ONLY: this host core never decides inactivity.
    Result acknowledge(uint32_t channel, const Ack& injected_ack);
    Result observe_boot(uint32_t boot_serial);
    Result controlled_reset(Counter new_epoch, uint32_t new_boot_serial, bool externally_qualified_idle);
    Result set_map(Token token, uint32_t index, LogicalMap map);
    Result resolve(Token token, uint32_t index, LogicalMap& out) const;
    Token current(uint32_t source_slot) const;
    const Generation* inspect(Token token) const;
    const Extent* extent(uint32_t index) const;
    const Channel* channel(uint32_t index) const;
    const Pool& pool() const { return pool_; }
    bool faulted() const { return faulted_ != 0; }
    bool invariant() const;
    uint32_t active_generations() const;
    uint32_t maps_used() const;
    uint32_t owners_used() const;
    uint32_t active_channels() const;
    Counter epoch() const { return epoch_; }
    uint32_t boot_serial() const { return boot_serial_; }
    static size_t metadata_bytes() { return sizeof(Core); }
private:
    enum : uint32_t { Empty, Receiving, Reserved, Verified, Published, Retired, Aborted };
    enum : uint32_t { ChannelFree, ChannelActive, ChannelRetiring };
    Pool pool_;
    Generation generations_[kGenerations];
    Owner owners_[kOwners];
    Extent extents_[kExtents];
    Channel channels_[kChannels];
    LogicalMap maps_[kMaps];
    uint8_t map_owners_[kMaps];
    uint8_t map_valid_[kMaps];
    uint32_t slots_[14];
    Counter epoch_, generation_counter_, lease_counter_;
    uint32_t boot_serial_, faulted_, shared_index_;
    uint32_t find(Token token) const;
    uint32_t owner_for(uint32_t owner, Token token) const;
    uint32_t free_extent() const;
    uint32_t map_range(uint32_t count) const;
    Token token_for(uint32_t generation) const;
    void detach_owner(uint32_t generation);
    void collect(uint32_t generation);
    void release_extent(uint32_t extent);
    void clear_metadata();
};

// All stored metadata excludes pointers, size_t, uint64_t and vtables. These
// fixed-width layouts make the proposed SH4 footprint explicit; a target build
// still has to confirm its ABI/BSS before integration.
static_assert(sizeof(Counter) == 8 && sizeof(Token) == 16, "counter ABI");
static_assert(sizeof(LogicalMap) == 12, "map ABI");
static_assert(sizeof(Generation) == 52, "generation ABI");
static_assert(sizeof(Owner) == 28, "owner ABI");
static_assert(sizeof(Extent) == 56, "extent ABI");
static_assert(sizeof(Channel) == 56, "channel ABI");
static_assert(alignof(Core) == 4, "stored metadata alignment");
} // namespace re4dc_aic2
#endif
#endif
