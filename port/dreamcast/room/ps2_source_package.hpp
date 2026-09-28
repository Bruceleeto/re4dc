#pragma once
#include "room_package.hpp"
#include "ps2_source_tables.hpp"

namespace re4dc { namespace room { namespace ps2 {
constexpr std::uint32_t kSpanVersion=5;
enum Section : unsigned {templates,materials,authored_batches,ordered_ranges,placements,smd_rows,smx_rows,ordered_bounds,section_count};
struct SpanHeader {
    re4dc::room::Header base;
    std::uint32_t room,asset_owner,payload_bytes,sections;
    OffsetCount table[section_count];
    std::uint32_t pool_bytes,reserved[3];
};
static_assert(sizeof(SpanHeader)==224 && offsetof(SpanHeader,table)==144 && offsetof(SpanHeader,pool_bytes)==208);
struct ExpectedPackage {std::uint32_t room,asset_owner,max_payload_bytes;};
enum class PackageError {ok,header,size,identity,crc,table,pool,template_record,material,batch,placement,range,bounds,stale};
inline std::uint32_t payload_crc(const std::uint8_t* data,std::size_t bytes) {
    std::uint32_t crc=~0U;
    for(std::size_t i=0;i<bytes;++i) {
        crc^=data[i];
        for(unsigned bit=0;bit<8;++bit)crc=(crc>>1)^(0xedb88320U & (0U-(crc&1U)));
    }
    return ~crc;
}
inline bool finite_word(float value) {
    std::uint32_t bits;std::memcpy(&bits,&value,4);return (bits&0x7f800000U)!=0x7f800000U;
}
class WorldDraw;
class SpanPackage {
    friend class WorldDraw; // synchronous qualified consumer; no public borrowed pool API
    SpanHeader header_{};
    Bytes payload_{};
    Owner owner_{};
    bool valid_=false;
    static constexpr unsigned stride_[section_count]={48,16,16,24,80,64,144,20};
    Bytes table(Section s) const {
        const auto& t=header_.table[s];
        return {payload_.data+t.offset,std::size_t(t.count)*stride_[s]};
    }
    template<class T> T record(Section s,std::uint32_t at) const {
        T result{};table_record(table(s),at,result);return result;
    }
    bool pool_span(OffsetCount s,unsigned stride,Bytes& out) const {
        if(s.offset%4 || s.offset>header_.pool_bytes ||
           s.count>(header_.pool_bytes-s.offset)/stride)return false;
        out={payload_.data+s.offset,std::size_t(s.count)*stride};return true;
    }
    Error source_view(std::uint32_t at,SourceView& view) const {
        const auto t=record<TemplateRecord>(templates,at);Pools p;
        if(!pool_span(t.position,6,p.positions) || !pool_span(t.uv,4,p.uv) ||
           !pool_span(t.attribute,t.attribute_kind?6:4,p.attributes) || !pool_span(t.corner,6,p.corners))return Error::span;
        p.position_count=t.position.count;p.uv_count=t.uv.count;p.attribute_count=t.attribute.count;p.corner_count=t.corner.count;
        p.factor=t.factor;p.source_bin=t.source_bin;p.kind=t.attribute_kind?Attribute::normal_i16:Attribute::color128;
        return view.bind(p,owner_);
    }
    bool padding(std::uint32_t from,std::uint32_t to) const {
        if(from>to || to>payload_.size)return false;
        for(auto i=from;i<to;++i)if(payload_.data[i])return false;
        return true;
    }
    PackageError validate() {
        std::uint32_t last_end=header_.pool_bytes;
        // Tables are canonical, ordered, disjoint and four-byte aligned.
        for(unsigned i=0;i<section_count;++i) {
            const auto t=header_.table[i];
            if(!t.count || t.offset%4 || t.offset<last_end || t.offset>payload_.size ||
               t.count>(payload_.size-t.offset)/stride_[i] || !padding(last_end,t.offset))return PackageError::table;
            last_end=t.offset+t.count*stride_[i];
        }
        if(last_end!=payload_.size)return PackageError::table;
        if(header_.table[templates].count>65536 || header_.table[materials].count>65536 ||
           header_.table[placements].count>65536)return PackageError::table;
        auto align4=[](std::uint32_t value){return (value+3U)&~3U;};
        std::uint32_t pool_cursor=0,batch_cursor=0;SourceView source;
        for(std::uint32_t i=0;i<header_.table[templates].count;++i) {
            const auto t=record<TemplateRecord>(templates,i);
            if(t.reserved || t.attribute_kind>1 || (i && t.source_bin<=record<TemplateRecord>(templates,i-1).source_bin))return PackageError::template_record;
            const OffsetCount spans[]={t.position,t.uv,t.attribute,t.corner};
            const unsigned strides[]={6,4,t.attribute_kind?6U:4U,6};
            for(unsigned j=0;j<4;++j) {
                // Source factor payload copy occurs between attr and corners.
                if(j==3) {
                    const auto start=align4(pool_cursor);
                    if(start>header_.pool_bytes || header_.pool_bytes-start<4 || !padding(pool_cursor,start))return PackageError::pool;
                    if(std::memcmp(payload_.data+start,&t.factor,4))return PackageError::pool;
                    pool_cursor=start+4;
                }
                Bytes span;
                if(!pool_span(spans[j],strides[j],span) || spans[j].offset!=align4(pool_cursor) ||
                   !padding(pool_cursor,spans[j].offset))return PackageError::pool;
                pool_cursor=spans[j].offset+std::uint32_t(span.size);
            }
            if(source_view(i,source)!=Error::ok)return PackageError::pool;
            if(!t.batch_count || t.first_batch!=batch_cursor || batch_cursor>header_.table[authored_batches].count ||
               t.batch_count>header_.table[authored_batches].count-batch_cursor)return PackageError::batch;
            std::uint32_t corner_cursor=0;
            for(std::uint32_t b=0;b<t.batch_count;++b) {
                const auto batch=record<AuthoredBatchRecord>(authored_batches,batch_cursor+b);
                if(batch.reserved || !batch.corner_count || batch.first_corner!=corner_cursor ||
                   batch.material_index>=header_.table[materials].count ||
                   source.strip_range(owner_,batch.first_corner,batch.corner_count)!=Error::ok)return PackageError::batch;
                const auto material=record<MaterialRecord>(materials,batch.material_index);
                if(material.source_bin!=t.source_bin)return PackageError::material;
                corner_cursor+=batch.corner_count;
            }
            if(corner_cursor!=t.corner.count)return PackageError::batch;
            batch_cursor+=t.batch_count;
        }
        if(align4(pool_cursor)!=header_.pool_bytes || !padding(pool_cursor,header_.pool_bytes) ||
           batch_cursor!=header_.table[authored_batches].count)return PackageError::pool;
        for(std::uint32_t m=1;m<header_.table[materials].count;++m) {
            const auto a=record<MaterialRecord>(materials,m-1),b=record<MaterialRecord>(materials,m);
            if(b.source_bin<a.source_bin || (b.source_bin==a.source_bin && b.source_material<=a.source_material))return PackageError::material;
        }
        OrderedCoverage coverage(owner_);std::uint32_t range_cursor=0;std::uint64_t triangles=0;
        for(std::uint32_t pi=0;pi<header_.table[placements].count;++pi) {
            const auto p=record<PlacementRecord>(placements,pi);
            if(p.placement!=pi || p.template_index>=header_.table[templates].count || !unmapped(p) ||
               p.source_smd>=header_.table[smd_rows].count ||
               p.source_smx>255 || // original source identity, NOT a raw-row ordinal
               !p.range_count || p.first_range!=range_cursor || range_cursor>header_.table[ordered_ranges].count ||
               p.range_count>header_.table[ordered_ranges].count-range_cursor)return PackageError::placement;
            for(const auto& row:p.affine)for(float value:row)if(!finite_word(value))return PackageError::placement;
            const auto& a=p.affine;
            const double determinant=double(a[0][0])*(double(a[1][1])*a[2][2]-double(a[1][2])*a[2][1])-
                double(a[0][1])*(double(a[1][0])*a[2][2]-double(a[1][2])*a[2][0])+
                double(a[0][2])*(double(a[1][0])*a[2][1]-double(a[1][1])*a[2][0]);
            if(determinant==0)return PackageError::placement;
            if(source_view(p.template_index,source)!=Error::ok)return PackageError::pool;
            const auto t=record<TemplateRecord>(templates,p.template_index);
            std::uint32_t next_batch=t.first_batch;
            for(std::uint32_t ri=0;ri<p.range_count;++ri) {
                const auto r=record<OrderedRangeRecord>(ordered_ranges,range_cursor+ri);
                if(r.reserved || r.placement!=pi || r.template_index!=p.template_index)return PackageError::range;
                const auto range=ordered_range(r,t.source_bin);OrderedGroups groups;
                if(coverage.append(owner_,source,range)!=Error::ok ||
                   groups.bind(table(ordered_bounds),header_.table[ordered_bounds].count,source,owner_,range)!=Error::ok)return PackageError::bounds;
                // Range material must agree with every authored segment it spans.
                std::uint32_t cursor=r.first_corner;
                while(cursor<r.first_corner+r.corner_count) {
                    if(next_batch>=t.first_batch+t.batch_count)return PackageError::batch;
                    const auto b=record<AuthoredBatchRecord>(authored_batches,next_batch++);
                    const auto m=record<MaterialRecord>(materials,b.material_index);
                    if(b.first_corner!=cursor || m.source_material!=r.source_material ||
                       b.corner_count>r.first_corner+r.corner_count-cursor)return PackageError::material;
                    cursor+=b.corner_count;
                }
                if(source.triangles(owner_,r.first_corner,r.corner_count,[&](auto,auto,auto){++triangles;})!=Error::ok)return PackageError::range;
            }
            if(next_batch!=t.first_batch+t.batch_count)return PackageError::batch;
            range_cursor+=p.range_count;
        }
        if(range_cursor!=header_.table[ordered_ranges].count ||
           coverage.finish(owner_,header_.table[placements].count,header_.table[ordered_bounds].count)!=Error::ok ||
           triangles!=header_.base.triangle_count)return PackageError::range;
        return PackageError::ok;
    }
public:
    void retire(){valid_=false;payload_={};owner_={};header_={};}
    bool live(Owner owner) const {return valid_ && same_owner(owner,owner_);}
    static PackageError check_header(const SpanHeader& h,std::size_t file_bytes,const ExpectedPackage& expected) {
        re4dc::room::Header wanted{};
        std::memcpy(wanted.magic,re4dc::room::kMagic,8);wanted.version=kSpanVersion;wanted.header_size=sizeof(SpanHeader);
        wanted.payload_crc32=h.base.payload_crc32;wanted.triangle_count=h.base.triangle_count;
        if(std::memcmp(&wanted,&h.base,sizeof(wanted)) || h.sections!=section_count ||
           h.reserved[0] || h.reserved[1] || h.reserved[2])return PackageError::header;
        if(file_bytes<sizeof(h) || h.payload_bytes!=file_bytes-sizeof(h) || !h.payload_bytes ||
           h.payload_bytes>expected.max_payload_bytes || !h.pool_bytes || h.pool_bytes>h.payload_bytes ||
           h.pool_bytes%4 || h.payload_bytes>UINT32_MAX-3U)return PackageError::size;
        if(h.room!=expected.room || h.asset_owner!=expected.asset_owner)return PackageError::identity;
        return PackageError::ok;
    }
    PackageError adopt(Bytes bytes,const ExpectedPackage& expected,Owner owner) {
        retire();if(!bytes.data || bytes.size<sizeof(SpanHeader))return PackageError::size;
        SpanHeader header;std::memcpy(&header,bytes.data,sizeof(header));
        auto error=check_header(header,bytes.size,expected);if(error!=PackageError::ok)return error;
        if(!owner.generation || owner.room!=expected.room)return PackageError::identity;
        const Bytes payload{bytes.data+sizeof(header),header.payload_bytes};
        if(payload_crc(payload.data,payload.size)!=header.base.payload_crc32)return PackageError::crc;
        header_=header;payload_=payload;owner_=owner;error=validate();
        if(error!=PackageError::ok){retire();return error;}
        valid_=true;return PackageError::ok;
    }
    PackageError summary(Owner owner,SpanHeader& output) const {
        if(!live(owner))return PackageError::stale;
        output=header_;return PackageError::ok;
    }
};
}}}
