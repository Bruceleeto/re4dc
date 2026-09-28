#ifndef RE4DC_COARSE_ACTOR_PREFLIGHT_H
#define RE4DC_COARSE_ACTOR_PREFLIGHT_H

#include <cstddef>
#include <cstdint>
#include <cstring>
#include "coarse_source_frame.h"

// Preflight only. No source preparation, texture load, allocator, registry or
// submission. A passing result is NOT native admission: real owners must lease
// every required resource and validate it through the final source OT pass.
namespace re4dc_source {
struct ByteSpan {
    const unsigned char* data;
    std::size_t size;
    bool contains(std::size_t at,std::size_t n) const {
        return data && at<=size && n<=size-at;
    }
};
inline unsigned pre_u16(const unsigned char* p) {return unsigned(p[0])|(unsigned(p[1])<<8);}
inline std::uint32_t pre_u32(const unsigned char* p) {return pre_u16(p)|(std::uint32_t(pre_u16(p+2))<<16);}
inline float pre_float(const unsigned char* p) {float x;std::uint32_t w=pre_u32(p);std::memcpy(&x,&w,4);return x;}
inline bool pre_finite(float x) {
    static_assert(sizeof(float)==sizeof(std::uint32_t),"IEEE binary32 preflight");
    std::uint32_t bits;std::memcpy(&bits,&x,sizeof(bits));
    return (bits&0x7f800000u)!=0x7f800000u;
}
struct ChunkInput {
    ByteSpan positions,normals,uv,stream,weights;
    unsigned position_count,normal_count,palette_count,triangles,bones;
};
enum class BlobError : unsigned {None,Array,Weights,Palette,Header,Table,Record,Strip,Count};
struct ChunkProof {
    unsigned meshlets,records,indices,triangles,palette_bytes,skin_table_bytes;
};
inline BlobError preflight_chunk(const ChunkInput& c,ChunkProof& proof) {
    proof={};
    if(!c.position_count || c.position_count>65535 || !c.normal_count || c.normal_count>65535 ||
       !c.palette_count || c.palette_count>256 || !c.bones || c.bones>256 ||
       !c.positions.contains(0,std::size_t(c.position_count)*8) ||
       !c.normals.contains(0,std::size_t(c.normal_count)*8) || !c.uv.data || c.uv.size%4 ||
       !c.weights.contains(0,std::size_t(c.palette_count)*16))return BlobError::Array;
    for(unsigned i=0;i<c.palette_count;++i) {
        const unsigned char* w=c.weights.data+i*16;const unsigned n=w[3];
        if(!n || n>3)return BlobError::Weights;
        float sum=0;
        for(unsigned k=0;k<n;++k) {
            const float v=pre_float(w+4+k*4);
            if(w[k]>=c.bones || !pre_finite(v) || v<0 || v>1)return BlobError::Weights;
            sum+=v;
        }
        const float delta=sum-1.0f;
        if(!pre_finite(sum) || delta < -0.0001f || delta > 0.0001f)return BlobError::Weights;
    }
    for(unsigned i=0;i<c.position_count;++i)
        if(pre_u16(c.positions.data+i*8+6)>=c.palette_count)return BlobError::Palette;
    for(unsigned i=0;i<c.normal_count;++i)
        if(pre_u16(c.normals.data+i*8+6)>=c.palette_count)return BlobError::Palette;
    const auto& s=c.stream;
    if(!s.contains(0,32) || s.size>1024*1024)return BlobError::Header;
    const auto* h=s.data;
    // Initial transaction accepts the actual reviewed FE/v3 level-zero blobs.
    // LOD mutation, vertex colours and baked light fields require another proof.
    if(h[0]!=0xfe || h[1]!=3 || (h[2]&0x83) || h[3] || pre_u16(h+12) || pre_u16(h+14))return BlobError::Header;
    for(unsigned k=0;k<4;++k)if(!pre_finite(pre_float(h+16+k*4)))return BlobError::Header;
    if(pre_float(h+28)<0)return BlobError::Header;
    const unsigned nm=pre_u16(h+4),rec=pre_u16(h+8)*4u,idx=pre_u16(h+10)*4u;
    if(!nm || !s.contains(32,std::size_t(nm)*8) || rec<32+nm*8u || idx<rec || idx>s.size)return BlobError::Table;
    unsigned records=0,indices=0,triangles=0;
    for(unsigned m=0;m<nm;++m) {
        const auto* t=h+32+m*8;const unsigned counts=pre_u32(t);
        const unsigned nv=counts&255,ni=(counts>>8)&4095,nt=counts>>20;
        if(!nv || nv>128 || !ni || ni>1024 || !nt || pre_u16(t+4)!=records || pre_u16(t+6)!=indices)return BlobError::Table;
        if(std::size_t(records+nv)*6>idx-rec || !s.contains(idx+indices,ni))return BlobError::Table;
        for(unsigned v=0;v<nv;++v) {
            const auto* r=h+rec+(records+v)*6;
            if(pre_u16(r)>=c.position_count || pre_u16(r+2)>=c.normal_count ||
               std::size_t(pre_u16(r+4))*4>=c.uv.size)return BlobError::Record;
        }
        unsigned len=0,tris=0;
        for(unsigned j=0;j<ni;++j) {
            const unsigned index=h[idx+indices+j];
            if((index&127)>=nv || ++len>64)return BlobError::Strip;
            if(index&128) {if(len<3)return BlobError::Strip;tris+=len-2;len=0;}
        }
        if(len || tris!=nt)return BlobError::Count;
        records+=nv;indices+=ni;triangles+=nt;
    }
    if(triangles!=c.triangles)return BlobError::Count;
    // Padding is permitted; each claimed record/list has been bounded and read.
    proof={nm,records,indices,triangles,(c.palette_count*48u+31u)&~31u,(c.palette_count*114u+31u)&~31u};
    return BlobError::None;
}

enum AdmissionReason : std::uint32_t {
    ABinding=1u<<0,AExtra=1u<<1,AHand=1u<<2,AFade=1u<<3,ABlend=1u<<4,
    AMaterial=1u<<5,AMorph=1u<<6,AColour=1u<<7,AShadow=1u<<8,AState=1u<<9,
    AInvalid=1u<<10,ARoles=1u<<11,AResource=1u<<12,APass=1u<<13
};
struct ActorInfoFacts {
    std::uintptr_t address;
    unsigned role,be,material_flags,blend,colour;
    float alpha,u,v,su,sv;
    bool default_hand,approved_morph,extra_texture,valid_data;
};
struct ActorFacts {
    bool source_entry,source_active,binding,texture_change,shader,shadow;
    float alpha,alpha2;
    unsigned expected_roles;
};
struct ActorProof {
    std::uint32_t reasons,seen_roles,visible_roles,pass0_roles,pass1_roles;
    unsigned infos;
};
inline ActorProof actor_begin(const ActorFacts& a) {
    ActorProof p{};
    if(!a.binding)p.reasons|=ABinding;
    if(!a.source_entry || !a.source_active)p.reasons|=AState;
    if(a.alpha!=1 || a.alpha2!=1)p.reasons|=AFade;
    if(a.texture_change || a.shader)p.reasons|=AMaterial;
    if(a.shadow)p.reasons|=AShadow;
    if(!a.expected_roles || a.expected_roles>8)p.reasons|=ARoles;
    return p;
}
inline void actor_info(ActorProof& p,const ActorInfoFacts& i) {
    ++p.infos;
    if(!i.address || !i.valid_data)p.reasons|=AInvalid;
    const bool matched=i.role<8;
    if(!matched)p.reasons|=AExtra;
    else {
        const unsigned bit=1u<<i.role;
        if(p.seen_roles&bit)p.reasons|=ARoles;
        p.seen_roles|=bit;
        if(i.be&8) {p.visible_roles|=bit;if(i.be&0x40)p.pass1_roles|=bit;else p.pass0_roles|=bit;}
    }
    // These checks intentionally include hidden infos: original preparation
    // visits them and may advance material/UV/shape state.
    if(!i.default_hand)p.reasons|=AHand;
    if(i.alpha!=1)p.reasons|=AFade;
    if(i.blend)p.reasons|=ABlend;
    if(i.material_flags || i.extra_texture || i.u!=0 || i.v!=0 || i.su!=0 || i.sv!=0)p.reasons|=AMaterial;
    if((i.be&2) && !i.approved_morph)p.reasons|=AMorph;
    if(i.colour!=0xffffffffu)p.reasons|=AColour;
}
inline void actor_finish(ActorProof& p,unsigned expected_roles,bool list_ended) {
    if(!list_ended || p.infos>32)p.reasons|=AInvalid;
    if(!expected_roles || expected_roles>8 || p.infos!=expected_roles ||
       p.seen_roles!=((1u<<expected_roles)-1u))p.reasons|=ARoles;
}

// The caller must already have completed original source preparation once via
// FrameLedger. This boundary cannot bless a binding-only preparation skip.
// ResourceOwner is a real owner adapter contract, not implemented here: acquire
// must atomically reserve texture, skin-slot, palette and workspace identities;
// validate checks every lease without mutation; release retires before free.
// No production owner is wired in this revision, hence no native runtime path.
enum class TransactionResult : unsigned {Source,Native,Invalid};
template<class ResourceOwner> class ActorTransaction {
public:
    using Lease=typename ResourceOwner::Lease;
    ActorTransaction():owner_(nullptr),revision_(0),state_(Empty),passes_(0),done_(0),begun_(0),
        consumed_(false),frame_{},model_{},lease_{} {}
    ActorTransaction(const ActorTransaction&)=delete;
    ActorTransaction& operator=(const ActorTransaction&)=delete;
    ~ActorTransaction(){retire();}
    bool prepare(const FrameLedger& ledger,const FrameIdentity& f,const ModelIdentity& m,
                 const ActorProof& semantic,ResourceOwner& owner,unsigned passes) {
        if(consumed_ && frame_==f && model_==m)return false;
        retire();consumed_=false;
        if(revision_==UINT32_MAX || semantic.reasons || !passes || (passes&~3u) ||
           ledger.membership(f,m)!=Membership::SourceHandled)return false;
        frame_=f;model_=m;passes_=passes;owner_=&owner;
        if(!owner_->acquire(f,m,semantic,lease_)) {owner_=nullptr;return false;}
        state_=Prepared;
        if(!owner_->validate(f,m,lease_)){retire();return false;}
        return true;
    }
    TransactionResult begin(const FrameLedger& ledger,const FrameIdentity& f,const ModelIdentity& m,unsigned pass) {
        if(ledger.membership(f,m)!=Membership::SourceHandled)return TransactionResult::Invalid;
        if(state_==Empty)return consumed_ && frame_==f && model_==m ? TransactionResult::Invalid:TransactionResult::Source;
        if(!(frame_==f) || !(model_==m) || ledger.membership(f,m)!=Membership::SourceHandled ||
           !owner_ || !owner_->validate(f,m,lease_) || pass>1 || !(passes_&(1u<<pass)) ||
           (done_&(1u<<pass)) || state_==Committing || state_==Failed ||
           (pass==1 && (passes_&1) && !(done_&1)))return reject();
        state_=Committing;begun_=1u<<pass;consumed_=true;return TransactionResult::Native;
    }
    bool complete(bool emitted_ok) {
        if(state_!=Committing)return false;
        if(!emitted_ok){state_=Failed;return false;}
        done_|=begun_;begun_=0;state_=Prepared;return true;
    }
    void retire() {
        // Revoke state before the owner may free borrowed storage.
        ResourceOwner* owner=owner_;owner_=nullptr;state_=Empty;
        if(revision_!=UINT32_MAX)++revision_;
        if(owner)owner->release(lease_);
        done_=passes_=begun_=0;
    }
private:
    enum State {Empty,Prepared,Committing,Failed};
    TransactionResult reject() {
        // Source fallback is legal only before any native pass has begun.
        const bool submitted=done_ || begun_ || state_==Failed || state_==Committing;
        if(submitted){state_=Failed;return TransactionResult::Invalid;}
        retire();return TransactionResult::Source;
    }
    ResourceOwner* owner_;
    std::uint32_t revision_;
    State state_;
    unsigned passes_,done_,begun_;
    bool consumed_;
    FrameIdentity frame_;ModelIdentity model_;Lease lease_;
};
}
#endif
