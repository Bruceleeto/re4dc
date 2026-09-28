#pragma once
// Review scaffold only: non-owning views of the coordinator's source pools.
// No file format, allocator, source replacement or renderer hook is introduced.
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace re4dc { namespace room { namespace ps2 {
struct Bytes { const std::uint8_t* data=nullptr; std::size_t size=0; };
struct Owner { std::uint32_t room=0, generation=0; };
inline bool same_owner(Owner a, Owner b) {
    return a.room==b.room && a.generation==b.generation;
}
enum class Attribute : std::uint8_t { color128, normal_i16 };
enum class Error : std::uint8_t {
    ok, owner, kind, factor, span, count, index, short_strip, open_strip,
    stale, range, not_strip_boundary, reserved, bounds, coverage, identity
};
struct Pools {
    Bytes positions, uv, attributes, corners;
    std::uint32_t position_count=0, uv_count=0, attribute_count=0, corner_count=0;
    float factor=0;
    std::uint16_t source_bin=0;
    Attribute kind=Attribute::color128;
};
struct Corner {
    std::uint16_t position=0, uv=0, attribute=0;
    bool strip_end=false;
};
struct Decoded {
    std::int16_t position[3]{}, uv[2]{}, normal[3]{};
    std::uint8_t color128[4]{};
};
inline std::uint16_t u16(const std::uint8_t* p) {
    return std::uint16_t(p[0]) | (std::uint16_t(p[1])<<8);
}
inline std::int16_t i16(const std::uint8_t* p) {
    const auto v=u16(p);
    return static_cast<std::int16_t>(v<32768U ? int(v) : int(v)-65536);
}
inline std::uint32_t u32(const std::uint8_t* p) {
    return std::uint32_t(u16(p)) | (std::uint32_t(u16(p+2))<<16);
}
inline bool exact_span(Bytes b, std::uint32_t count, unsigned stride) {
    // Divide before multiplying: also safe on the 32-bit target.
    return b.data && b.size/stride==count && b.size%stride==0;
}
class SourceView {
    Pools pools_{};
    Owner owner_{};
    std::uint32_t revision_=0;
    bool valid_=false;
    Corner unchecked(std::uint32_t at) const {
        const auto* p=pools_.corners.data+std::size_t(at)*6;
        const auto position=u16(p);
        return {std::uint16_t(position&0x7fff),u16(p+2),u16(p+4),bool(position&0x8000)};
    }
public:
    void retire() {
        pools_={}; owner_={}; valid_=false;
        if(revision_!=UINT32_MAX) ++revision_;
    }
    std::uint32_t revision() const {return revision_;}
    bool live(Owner o) const { return valid_ && same_owner(o,owner_); }
    const Pools* pools(Owner o) const { return live(o)?&pools_:nullptr; }
    Error bind(const Pools& p, Owner o) {
        retire();
        if(revision_==UINT32_MAX) return Error::stale; // never wrap a borrowed view identity
        if (!o.generation) return Error::owner;
        if (p.kind!=Attribute::color128 && p.kind!=Attribute::normal_i16) return Error::kind;
        std::uint32_t factor_bits; std::memcpy(&factor_bits,&p.factor,4);
        // Bit validation stays effective if the caller enables finite-math.
        if ((factor_bits&0x80000000U) || !(factor_bits&0x7fffffffU) ||
            (factor_bits&0x7f800000U)==0x7f800000U) return Error::factor;
        if (!p.position_count || p.position_count>32768 || !p.uv_count || p.uv_count>65536 ||
            !p.attribute_count || p.attribute_count>65536 || !p.corner_count) return Error::count;
        if (!exact_span(p.positions,p.position_count,6) || !exact_span(p.uv,p.uv_count,4) ||
            !exact_span(p.attributes,p.attribute_count,p.kind==Attribute::color128?4:6) ||
            !exact_span(p.corners,p.corner_count,6)) return Error::span;
        unsigned strip_length=0;
        for (std::uint32_t i=0; i<p.corner_count; ++i) {
            const auto* c=p.corners.data+std::size_t(i)*6;
            const auto pos=u16(c);
            if ((pos&0x7fff)>=p.position_count || u16(c+2)>=p.uv_count ||
                u16(c+4)>=p.attribute_count) return Error::index;
            ++strip_length;
            if (pos&0x8000) {
                if (strip_length<3) return Error::short_strip;
                strip_length=0;
            }
        }
        if (strip_length) return Error::open_strip;
        pools_=p; owner_=o; valid_=true;
        return Error::ok;
    }
    Error corner(Owner o, std::uint32_t at, Corner& out) const {
        if (!live(o)) return Error::stale;
        if (at>=pools_.corner_count) return Error::range;
        out=unchecked(at); return Error::ok;
    }
    Error decode(Owner o, std::uint32_t at, Decoded& out) const {
        Corner c; const auto err=corner(o,at,c); if (err!=Error::ok) return err;
        out={};
        const auto* p=pools_.positions.data+std::size_t(c.position)*6;
        const auto* u=pools_.uv.data+std::size_t(c.uv)*4;
        for (unsigned j=0;j<3;++j) out.position[j]=i16(p+j*2);
        for (unsigned j=0;j<2;++j) out.uv[j]=i16(u+j*2);
        if (pools_.kind==Attribute::color128) {
            const auto* a=pools_.attributes.data+std::size_t(c.attribute)*4;
            for (unsigned j=0;j<4;++j) out.color128[j]=a[j];
        } else {
            const auto* a=pools_.attributes.data+std::size_t(c.attribute)*6;
            for (unsigned j=0;j<3;++j) out.normal[j]=i16(a+j*2);
        }
        return Error::ok;
    }
    Error strip_range(Owner o, std::uint32_t first, std::uint32_t count) const {
        if (!live(o)) return Error::stale;
        if (first>pools_.corner_count || count>pools_.corner_count-first) return Error::range;
        if (!count) return Error::ok;
        if ((first && !unchecked(first-1).strip_end) || !unchecked(first+count-1).strip_end)
            return Error::not_strip_boundary;
        return Error::ok;
    }
    // Visits original triangle corner indices. No position/colour expansion,
    // regrouping, lighting, clipping, gain, culling or source suppression.
    // A range must contain whole strips; an interior split needs explicit
    // seed/parity metadata in the later subgroup adapter, not a guessed restart.
    template<class Visitor>
    Error triangles(Owner o, std::uint32_t first, std::uint32_t count, Visitor&& visit) const {
        const auto err=strip_range(o,first,count); if(err!=Error::ok) return err;
        std::uint32_t length=0;
        for (std::uint32_t i=first;i<first+count;++i) {
            if (length>=2) {
                if (length&1) visit(i,i-1,i-2);
                else visit(i-2,i-1,i);
            }
            ++length;
            if (unchecked(i).strip_end) length=0;
        }
        return Error::ok;
    }
};

// Describes an authored material's complete ordered corner span. The room
// wrapper supplies this metadata; it is deliberately not a disk struct.
struct OrderedRange {
    std::uint32_t placement=0, source_bin=0, material=0;
    std::uint32_t first_group=0, group_count=0, first_corner=0, corner_count=0;
};
struct OrderedGroup {
    std::uint32_t first_corner=0;
    std::uint16_t corner_count=0;
    std::int16_t minimum[3]{}, maximum[3]{};
};
class OrderedGroups {
    Bytes records_{};
    const SourceView* source_=nullptr; // must outlive the group view
    Owner owner_{};
    std::uint32_t revision_=0;
    OrderedRange range_{};
    static OrderedGroup unchecked(const std::uint8_t* p) {
        OrderedGroup g; g.first_corner=u32(p);g.corner_count=u16(p+4);
        for(unsigned i=0;i<3;++i) {g.minimum[i]=i16(p+8+i*2);g.maximum[i]=i16(p+14+i*2);}
        return g;
    }
public:
    void retire() {records_={};source_=nullptr;owner_={};revision_=0;range_={};}
    bool live(Owner o) const {
        return source_ && same_owner(o,owner_) && source_->live(o) && source_->revision()==revision_;
    }
    Error bind(Bytes all_records,std::uint32_t total_groups,const SourceView& source,
               Owner owner,const OrderedRange& range) {
        retire();
        const auto* pool=source.pools(owner); if(!pool) return Error::stale;
        if(range.source_bin!=pool->source_bin) return Error::identity;
        if(!exact_span(all_records,total_groups,20)) return Error::span;
        if(!range.group_count || !range.corner_count) return Error::count;
        if(range.first_group>total_groups || range.group_count>total_groups-range.first_group)
            return Error::range;
        const auto err=source.strip_range(owner,range.first_corner,range.corner_count);
        if(err!=Error::ok) return err;
        auto expected=range.first_corner;
        const auto end=range.first_corner+range.corner_count; // range already checked
        for(std::uint32_t i=0;i<range.group_count;++i) {
            const auto* p=all_records.data+std::size_t(range.first_group+i)*20;
            if(u16(p+6)) return Error::reserved;
            const auto g=unchecked(p);
            if(g.first_corner!=expected) return Error::coverage;
            if(!g.corner_count || g.corner_count>end-expected) return Error::range;
            const auto strip=source.strip_range(owner,g.first_corner,g.corner_count);
            if(strip!=Error::ok) return strip;
            for(unsigned axis=0;axis<3;++axis)
                if(g.minimum[axis]>g.maximum[axis]) return Error::bounds;
            for(std::uint32_t c=expected;c<expected+g.corner_count;++c) {
                Decoded d; const auto decoded=source.decode(owner,c,d);
                if(decoded!=Error::ok) return decoded;
                for(unsigned axis=0;axis<3;++axis)
                    if(d.position[axis]<g.minimum[axis] || d.position[axis]>g.maximum[axis])
                        return Error::bounds;
            }
            expected+=g.corner_count;
        }
        if(expected!=end) return Error::coverage;
        records_=all_records;source_=&source;owner_=owner;revision_=source.revision();range_=range;
        return Error::ok;
    }
    Error group(Owner o,std::uint32_t index,OrderedGroup& out) const {
        if(!live(o)) return Error::stale;
        if(index>=range_.group_count) return Error::range;
        out=unchecked(records_.data+std::size_t(range_.first_group+index)*20);
        return Error::ok;
    }
};

// Load-time cursor: admission requires every append AND finish to succeed.
// Rejects omitted/duplicate/overlapping groups or placement corner ranges.
class OrderedCoverage {
    Owner owner_{};
    std::uint32_t placement_=0,bin_=0,corners_=0,corner_total_=0,groups_=0;
    bool started_=false,failed_=false;
public:
    explicit OrderedCoverage(Owner owner):owner_(owner) {}
    Error append(Owner owner,const SourceView& source,const OrderedRange& range) {
        if(failed_) return Error::coverage;
        auto fail=[&](Error error){failed_=true;return error;};
        const auto* pool=source.pools(owner);
        if(!same_owner(owner,owner_) || !pool) return fail(Error::stale);
        if(!range.group_count || !range.corner_count) return fail(Error::count);
        if(range.source_bin!=pool->source_bin) return fail(Error::identity);
        if(range.first_group!=groups_ || range.group_count>UINT32_MAX-groups_)
            return fail(Error::coverage);
        if(!started_) {
            if(range.placement!=0 || range.first_corner!=0) return fail(Error::coverage);
        } else if(range.placement!=placement_) {
            if(placement_==UINT32_MAX || range.placement!=placement_+1 || corners_!=corner_total_ ||
               range.first_corner!=0) return fail(Error::coverage);
            corners_=0;
        } else if(range.source_bin!=bin_ || pool->corner_count!=corner_total_) {
            return fail(Error::identity);
        }
        if(range.first_corner!=corners_ || corners_>pool->corner_count ||
           range.corner_count>pool->corner_count-corners_) return fail(Error::coverage);
        const auto strip=source.strip_range(owner,range.first_corner,range.corner_count);
        if(strip!=Error::ok) return fail(strip);
        placement_=range.placement;bin_=range.source_bin;corner_total_=pool->corner_count;
        corners_+=range.corner_count;groups_+=range.group_count;started_=true;
        return Error::ok;
    }
    Error finish(Owner owner,std::uint32_t placements,std::uint32_t total_groups) const {
        if(!same_owner(owner,owner_)) return Error::stale;
        if(failed_ || !started_ || !placements || placement_!=placements-1 ||
           corners_!=corner_total_ || groups_!=total_groups) return Error::coverage;
        return Error::ok;
    }
};
}}}
