// NATIVE_MODEL_REGISTRY_PACK=1 (native_model_registry.mk; render only): the room-owned registry package. Included once
// by coarse_actor_owner_leon.inc after coarse_actor_material.inc: it fills the registry view of
// coarse_actor_owner_registry.inc, the room identity rows of actor_material_records.inc / actor_lifetime.inc and
// resets the registry IDs of coarse_actor_geometry_once.inc.
//
// re4dc_registry_room_enter (ui_bridge.cpp re4dc_room_enter, after the heap-4 room opens and before the room's
// archives load and adopt): dc/native/r<room>/registry.re4nmr (tools/d367/model_registry.py --package-room) is read
// into ONE heap-4 room cell (re4dc_static_alloc: the native static room storage, high end, 80 KiB source reserve)
// with its skin arena after it. Everything is validated before anything is visible: header magic / version /
// sizes / room, header and payload CRC32 + FNV-1a, the section table (kinds, order, 32-byte alignment, bounds, no
// overlap, record sizes, explicit capacities), every record (counts, offsets, spans inside the blob section,
// alignment, pairwise disjoint arrays, per-geometry hashes, finite binds and weights, parents as an index-ordered
// forest), every cross reference (descriptor -> chunk refs -> geometry / texture, geometry bones = descriptor
// bones, role rows = exactly the descriptor sections, fact model / part / texture ranges, source blob for every
// role's BIN), duplicates (identical geometry stored twice, texture keys, role keys, ambiguous descriptor source
// identities), then the target preflight of every geometry and every descriptor's skin stream. Only then are the
// view and the identity rows published (one generation; the lifetime epoch moves). Any failure frees the cell and
// publishes nothing: every actor keeps the whole source path. No pointer is read from the file.
//
// re4dc_registry_room_leave (ui_bridge.cpp re4dc_room_leave, before the UI / static retire and the heap-4 close):
// the transaction's owned records are revoked if a frame still holds them, the room rows leave every live
// lifetime record (records left with no row are dropped; the epoch moves), the registry IDs' immutable proofs are
// reset, the view / id mask / binding cache / skin state are cleared and the cell is freed. A room enter with a
// package still published retires it first, so two generations never overlap (peak overlap 0 cells).
#include <kos/fs.h>
#include <fcntl.h>
#include <cstddef>
#include <cstdio>
extern "C" void* re4dc_static_alloc(unsigned);
extern "C" void re4dc_static_free(void*);
extern "C" int re4dc_static_heap_free();
extern "C" int re4dc_room4_state(unsigned*,unsigned*,unsigned*,unsigned*,unsigned*);
#include "coarse_actor_registry_pack_check.inc"
namespace {
struct PackState {
    unsigned char* cell;unsigned char* base;unsigned room,bytes,arena,generation,heap_before,heap_after;
    unsigned opens,publishes,refusals,retires,late_retires;
};
PackState pack{};
void registry_view_clear() {
    registry=RegistryView{};registry_mask_ready=false;std::memset(registry_id_mask,0,sizeof(registry_id_mask));
    for(auto& b:registry_bindings)b=RegistryBinding{};
    registry_replace=0;registry_bound=nullptr;
    std::memset(registry_skin_built,0,sizeof(registry_skin_built));std::memset(registry_skin_state,0,sizeof(registry_skin_state));
    std::memset(registry_skin_used,0,sizeof(registry_skin_used));registry_skin_next=0;registry_skin=nullptr;registry_skin_cap=0;
#if RE4DC_NATIVE_MODEL_REGISTRY == 2
    for(auto& s:registry_snaps)s.m=nullptr;
#endif
}
void pack_refuse(unsigned room,PackWhy why,unsigned detail) {
    ++pack.refusals;
    re4dc_log("NMRPACK refuse room=%04x why=%s detail=%u heap4_free=%d: every actor keeps the source path\n",room,
        kPackWhy[why<kPwCount?why:0],detail,re4dc_static_heap_free());
}
}

extern "C" void re4dc_registry_room_leave() {
    if(!pack.cell)return;
    const unsigned room=pack.room,generation=pack.generation;
    const bool owned=actor_owned_live;
    // A frame that still holds owned records is revoked the transaction's own way (no traversal of their storage).
    if(owned)re4dc_actor_transaction_retire();
    unsigned infos=0,assets=0;
    const unsigned users_before=re4dc_material::life::room_rows_users();  // live records naming a room row now
    re4dc_material::life::room_rows_retire(infos,assets);
    const unsigned proofs=actor_immutable_reset_registry();
#if RE4DC_NATIVE_MODEL_REGISTRY_CENSUS
    if(registry.descriptor_count)scene_report(re4dc_ui_frame());  // this generation's census before its view goes
    while(registry_tracked_n)registry_note_retire(registry_tracked[0].m,"room-retire");
#endif
    registry_view_clear();
    re4dc_static_free(pack.cell);
    const unsigned bytes=pack.arena;pack.cell=nullptr;pack.base=nullptr;pack.arena=0;++pack.retires;
    re4dc_log("NMRPACK retire room=%04x gen=%u bytes=%u owned_live=%u row_users_before=%u infos_dropped=%u assets_dropped=%u "
        "proofs_reset=%u row_users=%u heap4_free=%d retires=%u\n",room,generation,bytes,unsigned(owned),users_before,infos,assets,proofs,
        re4dc_material::life::room_rows_users(),re4dc_static_heap_free(),pack.retires);
}

extern "C" void re4dc_registry_room_enter(unsigned room) {
    // Never two generations at once: a package the room leave did not retire is retired before the next opens
    // (counted as late; the peak is one package cell either way).
    if(pack.cell){++pack.late_retires;re4dc_registry_room_leave();}
    char path[64];snprintf(path,sizeof(path),"/cd/dc/native/r%x%02x/registry.re4nmr",room>>8,room&255u);
    const file_t file=fs_open(path,O_RDONLY);
    if(file==FILEHND_INVALID){re4dc_log("NMRPACK room=%04x none (%s)\n",room,path);return;}
    ++pack.opens;
    const unsigned size=unsigned(fs_total(file));
    unsigned char head[kPackHeader];
    if(size<kPackPayload || size>kPackMaxBytes || fs_read(file,head,kPackHeader)!=ssize_t(kPackHeader)) {
        fs_close(file);pack_refuse(room,size<kPackPayload || size>kPackMaxBytes?kPwSize:kPwRead,size);return;
    }
    const unsigned skin=pu32(head,28);
    if(skin%8u || skin>kPackMaxBytes || ((size+31u)&~31u)+skin>kPackMaxBytes){fs_close(file);pack_refuse(room,kPwSize,skin);return;}
    const unsigned arena=((size+31u)&~31u)+skin;
    const int heap_before=re4dc_static_heap_free();
    auto* cell=static_cast<unsigned char*>(re4dc_static_alloc(arena+32u));
    if(!cell){fs_close(file);pack_refuse(room,kPwAlloc,arena);return;}
    auto* base=reinterpret_cast<unsigned char*>((reinterpret_cast<std::uintptr_t>(cell)+31u)&~std::uintptr_t(31u));
    std::memcpy(base,head,kPackHeader);
    const ssize_t rest=ssize_t(size-kPackHeader);
    const bool read=fs_read(file,base+kPackHeader,rest)==rest;
    fs_close(file);
    unsigned detail=0;
    PackWhy why=read?pack_validate(base,size,room,detail):kPwRead;
    unsigned generation=0,cells=0,cell_bytes=0,stale=0,refused=0;
    re4dc_room4_state(&generation,&cells,&cell_bytes,&stale,&refused);
    if(why==kPwNone) {
        // The target preflight of every unique geometry (through a chunk that references it: all do), then the
        // view is staged for every descriptor's skin stream.
        const unsigned nd=pu32(base,kPackHeader+kDesc*16+12),nc=pu32(base,kPackHeader+kRef*16+12),
            ng=pu32(base,kPackHeader+kGeom*16+12),nt=pu32(base,kPackHeader+kTex*16+12),geom_at=pu32(base,kPackHeader+kGeom*16+4);
        unsigned geometries=0;
        for(unsigned g=0;g<ng && why==kPwNone;++g) {
            unsigned ci=0;while(ci<nc && pack_chunks[ci].geometry!=g)++ci;
            const auto& c=pack_chunks[ci];const unsigned bones=pu32(base,geom_at+g*64+28);
            const re4dc_source::ChunkInput input{{c.positions,c.position_count*8u},{c.normals,c.normal_count*8u},{c.uv,c.uv_bytes},
                {c.stream,c.stream_bytes},{reinterpret_cast<const unsigned char*>(c.weights),c.palette_count*16u},
                c.position_count,c.normal_count,c.palette_count,c.triangles,bones};
            re4dc_source::ChunkProof proof{};
            const auto e=re4dc_source::preflight_chunk(input,proof);
            if(e!=re4dc_source::BlobError::None){why=kPwPreflight;detail=g*256+unsigned(e);}
            ++geometries;
        }
        if(why==kPwNone) {
            registry_view_clear();
            registry=RegistryView{pack_desc,pack_chunks,pack_tex,nd,nc,nt,ng,generation};
            registry_skin=base+((size+31u)&~31u);registry_skin_cap=skin;
            for(unsigned d=0;d<nd && why==kPwNone;++d)if(!registry_skin_init(d)){why=kPwSkin;detail=d;}
            if(why==kPwNone && registry_skin_next!=skin){why=kPwSkin;detail=registry_skin_next;}
            if(why!=kPwNone)registry_view_clear();
        }
        if(why==kPwNone) {
            const unsigned nr=pu32(base,kPackHeader+kRole*16+12),nb=pu32(base,kPackHeader+kSBlob*16+12);
            const unsigned early=re4dc_material::life::live_family(2);
            re4dc_material::life::room_rows_publish(pack_roles,nr,pack_blobs,nb,generation);
            pack.cell=cell;pack.base=base;pack.room=room;pack.bytes=size;pack.arena=arena+32u;pack.generation=generation;
            pack.heap_before=unsigned(heap_before);pack.heap_after=unsigned(re4dc_static_heap_free());++pack.publishes;
            re4dc_log("NMRPACK open room=%04x gen=%u bytes=%u skin=%u cell=%u descriptors=%u chunks=%u geometry=%u textures=%u "
                "roles=%u blobs=%u preflight=%u heap4_free=%d->%d room4_cells=%u enemy_archives_before=%u publishes=%u late_retires=%u\n",
                room,generation,size,skin,arena+32u,nd,nc,ng,nt,nr,nb,geometries,heap_before,re4dc_static_heap_free(),cells,early,
                pack.publishes,pack.late_retires);
            return;
        }
    }
    re4dc_static_free(cell);
    pack_refuse(room,why,detail);
}
