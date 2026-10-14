#ifndef RE4DC_AICA_BANK_V2_STREAM_H
#define RE4DC_AICA_BANK_V2_STREAM_H
#include "aica_bank_v2_sha256.h"
#if RE4DC_AICA_BANK_V2
namespace re4dc_aic2 {
// Immutable generated whitelist entry; callers must keep it and the registered
// sound span alive until publication/cancel completes. No ownership is guessed.
struct Profile {
    uint32_t source_class, id, cap_hz, gc_bytes, mram_bytes, count, logical_bytes, policy;
    uint8_t mram_sha[32], table_sha[32], logical_sha[32];
};
static_assert(sizeof(Profile)==128,"profile budget");
struct PhysicalResult { uint32_t actual_address, actual_bytes, actual_access; }; // read0, write1
class PhysicalAdapter {
public:
    virtual ~PhysicalAdapter() = default;
    // Narrow trusted hardware boundary. Implementations report what was really
    // transferred, not a desired address copied from an unexecuted request.
    virtual PhysicalResult read(uint32_t address,uint8_t* output,uint32_t bytes)=0;
    virtual PhysicalResult write(uint32_t address,const uint8_t* input,uint32_t bytes)=0;
};
Result inspect_mram(const uint8_t* sound,uint32_t sound_bytes,uint32_t mram_offset,
                    uint32_t mram_bytes,uint32_t source_class,uint32_t count,const uint8_t*& table);
struct Receiver {
    uint8_t header[192],record[64],extents[128];
    Sha256 first,second;
    uint8_t expected_fold[32];
    const Profile* profile;
    const uint8_t* mram;
    const uint8_t* table;
    Token token;
    uint32_t owner,slot,state,received,fill,index,logical_cursor,local_bytes;
    uint32_t payload_extent,payload_offset,carry,carry_bytes,shared_hit;
};
static_assert(sizeof(Receiver)<=768,"bounded receiver budget");
class Engine {
public:
    explicit Engine(Core& core,PhysicalAdapter& physical);
    Result begin(uint32_t owner,uint32_t slot,const Profile& profile,
                 const uint8_t* sound,uint32_t sound_bytes,uint32_t mram_offset,Token& token);
    // Input <=128KiB. logical_bytes excludes only explicit final ARQ32 padding.
    // On Busy, consumed is authoritative: retry at offset+consumed with the
    // remaining bytes. No input pointer or scratch lease survives this return.
    Result feed(uint32_t owner,Token token,uint32_t offset,const uint8_t* input,
                uint32_t input_bytes,uint32_t logical_bytes,uint32_t& consumed);
    Result resume(uint32_t owner,Token token);
    Result cancel(uint32_t owner,Token token);
    uint32_t active_contexts() const;
    static size_t receiver_bytes(){return sizeof(Receiver);}
    static size_t scratch_bytes(){return 4096;}
private:
    enum : uint32_t { Empty,Header,Maps,Extents,Reserve,Payload,Tail,Readback,Ready,Cancelled };
    Core& core_;
    PhysicalAdapter& physical_;
    Receiver receivers_[16];
    alignas(32) uint8_t scratch_[4096];
    Sha256 sample_sha_;
    uint32_t busy_;
    Receiver* find(uint32_t owner,Token token);
    Result metadata(Receiver& r);
    Result header(Receiver& r);
    Result map(Receiver& r);
    Result extents(Receiver& r);
    Result reserve(Receiver& r);
    Result scatter(Receiver& r,const uint8_t* bytes,uint32_t count);
    Result transfer(Receiver& r,uint32_t ei,uint32_t offset,uint32_t bytes,const uint8_t* write);
    Result finish(Receiver& r);
    Result fail(Receiver& r,Result why);
};
}
#endif
#endif
