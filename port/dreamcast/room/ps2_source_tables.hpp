#pragma once
// Exact wrapper-v1 table layouts for readback/compile checks. The externally
// described room-owned blob has no new magic or runtime adoption hook.
#include "ps2_source_view.hpp"

namespace re4dc { namespace room { namespace ps2 {
struct OffsetCount {std::uint32_t offset,count;};
struct TemplateRecord {
    std::uint16_t source_bin; std::uint8_t attribute_kind,reserved;
    OffsetCount position,uv,attribute,corner;
    float factor;
    std::uint32_t first_batch,batch_count;
};
struct MaterialRecord {
    std::uint16_t source_bin,source_material;
    std::uint8_t source_bytes[12];
};
struct AuthoredBatchRecord {
    std::uint32_t first_corner,corner_count;
    std::uint16_t material_index,source_segment;
    std::uint32_t reserved;
};
struct OrderedRangeRecord {
    std::uint16_t placement,template_index,source_material,reserved;
    std::uint32_t first_group,group_count,first_corner,corner_count;
};
struct PlacementRecord {
    std::uint16_t placement,template_index,source_smd,source_smx,source_tpl,coverage;
    std::uint32_t source_status,first_range,range_count,coverage_index,reserved;
    float affine[3][4]; // local millimetres -> world millimetres, S*R then T
};
struct OrderedBoundRecord {
    std::uint32_t first_corner;
    std::uint16_t corner_count,reserved;
    std::int16_t minimum[3],maximum[3];
};
static_assert(sizeof(TemplateRecord)==48 && offsetof(TemplateRecord,factor)==36);
static_assert(offsetof(TemplateRecord,first_batch)==40);
static_assert(sizeof(MaterialRecord)==16 && offsetof(MaterialRecord,source_bytes)==4);
static_assert(sizeof(AuthoredBatchRecord)==16 && offsetof(AuthoredBatchRecord,reserved)==12);
static_assert(sizeof(OrderedRangeRecord)==24 && offsetof(OrderedRangeRecord,first_group)==8);
static_assert(sizeof(PlacementRecord)==80 && offsetof(PlacementRecord,affine)==32);
static_assert(offsetof(PlacementRecord,coverage)==10 && offsetof(PlacementRecord,coverage_index)==24);
static_assert(sizeof(OrderedBoundRecord)==20 && offsetof(OrderedBoundRecord,minimum)==8);

// Target is little-endian SH4. No unaligned struct dereference is used.
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ != __ORDER_LITTLE_ENDIAN__
#error PS2 source table readback requires explicit little-endian conversion on this host
#endif
template<class Record>
inline Error table_record(Bytes table,std::uint32_t index,Record& result) {
    if(!table.data || table.size%sizeof(Record)) return Error::span;
    if(index>=table.size/sizeof(Record)) return Error::range;
    std::memcpy(&result,table.data+std::size_t(index)*sizeof(Record),sizeof(Record));
    return Error::ok;
}
inline bool unmapped(const PlacementRecord& p) {
    return p.coverage==0 && p.coverage_index==0xffffffffU && p.reserved==0;
}
inline OrderedRange ordered_range(const OrderedRangeRecord& r,std::uint32_t source_bin) {
    return {r.placement,source_bin,r.source_material,r.first_group,r.group_count,r.first_corner,r.corner_count};
}
}}}
