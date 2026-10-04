// ACTOR_PL08_PACK (crowd.mk, default 0): validation and lifetime of the pl08 costume package (the three pl08-only
// immutable chunks, roles 0 / 1 / 8, tools/d367/pl08_pack.py). Host-compilable: the target (coarse_actor_pl08_pack.inc)
// and the host test (tools/d367/pl08_pack_test.cpp) include it inside an unnamed namespace after defining the hooks
// below, so both run these exact routines.
//
// Lifetime (one state, no second generation ever overlaps):
//   - want = the bound player archive is pl08 (ReadPlayerData file 0x5A: FileTbl "em/pl08.das"); the source decides.
//   - room enter (heap-4 room storage just opened) and every player bind sync to want.
//   - open: the file is read into ONE heap-4 room cell (re4dc_static_alloc) and validated completely (size, header,
//     header and payload CRC32 + FNV-1a, every table field and every array's CRC32 + FNV-1a against the compiled
//     identity, layout bounds / alignment / order, weight rows) and every chunk passes the target preflight BEFORE
//     anything is visible. Any failure frees the cell and publishes nothing: pl08 keeps the whole source path.
//   - publish: the immutable proofs of the three IDs and the costume-1 skin stream are reset FIRST, then the
//     descriptors are filled and the state becomes published (generation + 1). A base equal to the previous
//     publication's is counted (same-address reload): the reset ran before it, so no proof of the old bytes survives.
//   - a bind away from pl08 inside a room unpublishes (plans stop at once; proofs reset) but keeps the cell: owned
//     records of a queued frame may still point into it. Binding pl08 again in the same room revalidates the kept
//     bytes completely before republishing.
//   - room leave: the transaction's owned records are revoked if live, the proofs reset, the cell freed.
#include <cstring>
struct Pl08PackExpect {
    unsigned role,source_info,position_count,normal_count,palette_count,triangles,stream_bytes;
    unsigned layout[10];  // pos, nrm, uv, gx, weights: offset, bytes
    unsigned hash[10];    // the same arrays: CRC32, FNV-1a
};
#include "actor_pl08_pack_identity.inc"
constexpr unsigned kPl08PackHeader=256u,kPl08PackTable=64u,kPl08PackEntry=64u,kPl08PlayerFile=0x5Au,kPl08Bones=119u;
enum Pl08Why : unsigned {kP8None,kP8Size,kP8Header,kP8Hash,kP8Table,kP8Layout,kP8Array,kP8Weight,kP8Missing,kP8Read,
    kP8Alloc,kP8Preflight,kP8Count};
const char* const kPl08Why[kP8Count]={"none","size","header","hash","table","layout","array","weight","missing","read",
    "alloc","preflight"};
struct Pl08ChunkView {
    const unsigned char* array[5];  // pos, nrm, uv, gx, weights
    unsigned bytes[5];
    unsigned role,source_info,position_count,normal_count,palette_count,triangles;
};
inline unsigned p8u32(const unsigned char* p,unsigned at) {unsigned x;std::memcpy(&x,p+at,4);return x;}
struct Pl08Hash {
    unsigned crc=~0u,fnv=2166136261u;
    void add(const unsigned char* b,unsigned n) {
        for(unsigned k=0;k<n;++k) {
            crc^=b[k];fnv=(fnv^b[k])*16777619u;
            for(unsigned j=0;j<8;++j)crc=(crc>>1)^(0xedb88320u&(0u-(crc&1u)));
        }
    }
    unsigned crc32() const {return ~crc;}
};
// Validates p[0..size) (32-byte aligned) completely; fills out[3] only on kP8None.
Pl08Why pl08_pack_validate(const unsigned char* p,unsigned size,Pl08ChunkView out[3],unsigned& detail) {
    detail=0;
    if(size!=kPl08PackBytes){detail=size;return kP8Size;}
    if(std::memcmp(p,"RE4PL08\0",8) || p8u32(p,8)!=1u || p8u32(p,12)!=kPl08PackHeader || p8u32(p,16)!=size || p8u32(p,20)!=3u)
        {detail=1;return kP8Header;}
    for(unsigned at=36;at<64;at+=4)if(p8u32(p,at)){detail=at;return kP8Header;}
    {
        unsigned char h[kPl08PackHeader];std::memcpy(h,p,kPl08PackHeader);std::memset(h+32,0,4);
        Pl08Hash a;a.add(h,kPl08PackHeader);if(a.crc32()!=p8u32(p,32)){detail=1;return kP8Hash;}
        Pl08Hash b;b.add(p+kPl08PackHeader,size-kPl08PackHeader);
        if(b.crc32()!=p8u32(p,24) || b.fnv!=p8u32(p,28) || b.crc32()!=kPl08PackPayloadCrc || b.fnv!=kPl08PackPayloadFnv)
            {detail=2;return kP8Hash;}
    }
    for(unsigned at=kPl08PackTable+3u*kPl08PackEntry;at<kPl08PackHeader;at+=4)if(p8u32(p,at)){detail=at;return kP8Table;}
    unsigned end=kPl08PackHeader;  // arrays in file order, each after the previous
    for(unsigned k=0;k<3;++k) {
        const unsigned char* e=p+kPl08PackTable+k*kPl08PackEntry;const Pl08PackExpect& x=kPl08PackExpect[k];
        const unsigned f[16]={x.role,x.source_info,x.position_count,x.normal_count,x.palette_count,x.triangles,x.stream_bytes,
            x.layout[0],x.layout[1],x.layout[2],x.layout[3],x.layout[4],x.layout[5],x.layout[6],x.layout[8],0u};
        for(unsigned i=0;i<16;++i)if(p8u32(e,i*4)!=f[i]){detail=k*16+i;return kP8Table;}
        // The identity fixes the layout; it is still checked structurally (no array outside the file or overlapping).
        if(x.layout[1]!=x.position_count*8u || x.layout[3]!=x.normal_count*8u || x.layout[7]!=x.stream_bytes ||
           x.layout[9]!=x.palette_count*16u){detail=k;return kP8Layout;}
        Pl08ChunkView& v=out[k];
        for(unsigned a=0;a<5;++a) {
            const unsigned off=x.layout[a*2],n=x.layout[a*2+1];
            if(off%32u || off<end || n>size || off>size-n || !n){detail=k*8+a;return kP8Layout;}
            end=off+n;
            Pl08Hash h;h.add(p+off,n);
            if(h.crc32()!=x.hash[a*2] || h.fnv!=x.hash[a*2+1]){detail=k*8+a;return kP8Array;}
            v.array[a]=p+off;v.bytes[a]=n;
        }
        const unsigned char* w=v.array[4];
        for(unsigned j=0;j<x.palette_count;++j,w+=16) {
            const unsigned n=w[3];if(!n || n>3u){detail=k*65536+j;return kP8Weight;}
            for(unsigned i=0;i<n;++i) {
                float f;std::memcpy(&f,w+4+i*4,4);
                if(w[i]>=kPl08Bones || !(f==f) || f>1e30f || f< -1e30f){detail=k*65536+j;return kP8Weight;}
            }
        }
        v.role=x.role;v.source_info=x.source_info;v.position_count=x.position_count;v.normal_count=x.normal_count;
        v.palette_count=x.palette_count;v.triangles=x.triangles;
    }
    return kP8None;
}
struct Pl08PackLife {
    unsigned char* cell;unsigned char* base;
    bool published;unsigned player_file;unsigned generation;const unsigned char* last_base;
    unsigned opens,publishes,refusals,unpublishes,retires,same_address,revalidations,late_retires,last_why;
    Pl08ChunkView view[3];
};
// Hooks, defined by the includer before this file:
//   int pl08_hook_open();                         file size, -1 absent (the file stays open for read / close)
//   bool pl08_hook_read(unsigned char*,unsigned); reads the open file completely and closes it
//   void pl08_hook_close();                       closes it unread (idempotent)
//   unsigned char* pl08_hook_alloc(unsigned);     a heap-4 room cell or nullptr
//   void pl08_hook_free(unsigned char*);
//   bool pl08_hook_preflight(const Pl08ChunkView&,unsigned& detail);   the target chunk preflight
//   unsigned pl08_hook_reset();                   reset the three immutable proofs + the costume-1 skin stream
//   void pl08_hook_published(const Pl08ChunkView*); descriptors (nullptr: cleared)
//   void pl08_hook_retire_owned();                revoke the transaction's owned records if any (room leave only)
//   P8LOG(...)                                    the log
void pl08_life_refuse(Pl08PackLife& L,const char* where,Pl08Why why,unsigned detail) {
    ++L.refusals;L.last_why=why;
    P8LOG("P8PACK refuse at=%s why=%s detail=%u: pl08 keeps the source path\n",where,kPl08Why[unsigned(why)<kP8Count?unsigned(why):0u],detail);
}
bool pl08_life_check(Pl08PackLife& L,const char* where,Pl08ChunkView view[3]) {
    unsigned detail=0;Pl08Why why=pl08_pack_validate(L.base,kPl08PackBytes,view,detail);
    for(unsigned k=0;k<3 && why==kP8None;++k)if(!pl08_hook_preflight(view[k],detail)){why=kP8Preflight;detail=k*256+detail;}
    if(why!=kP8None){pl08_life_refuse(L,where,why,detail);return false;}
    return true;
}
void pl08_life_publish(Pl08PackLife& L,const char* where,const Pl08ChunkView view[3]) {
    const unsigned reset=pl08_hook_reset();  // no proof or skin program of earlier bytes survives this publication
    for(unsigned k=0;k<3;++k)L.view[k]=view[k];
    const bool same=L.last_base==L.base;
    if(same)++L.same_address;
    L.last_base=L.base;++L.generation;++L.publishes;L.published=true;
    pl08_hook_published(L.view);
    P8LOG("P8PACK publish at=%s gen=%u base=%p bytes=%u ids_reset=%u same_address=%u publishes=%u\n",where,L.generation,
        static_cast<const void*>(L.base),kPl08PackBytes,reset,unsigned(same),L.publishes);
}
void pl08_life_unpublish(Pl08PackLife& L,const char* where) {
    if(!L.published)return;
    L.published=false;pl08_hook_published(nullptr);
    const unsigned reset=pl08_hook_reset();++L.unpublishes;
    P8LOG("P8PACK unpublish at=%s gen=%u ids_reset=%u cell_kept=%u\n",where,L.generation,reset,unsigned(L.cell!=nullptr));
}
void pl08_life_open(Pl08PackLife& L,const char* where) {
    const int size=pl08_hook_open();
    if(size<0){pl08_life_refuse(L,where,kP8Missing,0);return;}
    ++L.opens;
    if(unsigned(size)!=kPl08PackBytes){pl08_hook_close();pl08_life_refuse(L,where,kP8Size,unsigned(size));return;}
    unsigned char* cell=pl08_hook_alloc(kPl08PackBytes+32u);
    if(!cell){pl08_hook_close();pl08_life_refuse(L,where,kP8Alloc,kPl08PackBytes+32u);return;}
    unsigned char* base=reinterpret_cast<unsigned char*>((reinterpret_cast<unsigned long>(cell)+31ul)&~31ul);
    if(!pl08_hook_read(base,kPl08PackBytes)){pl08_hook_free(cell);pl08_life_refuse(L,where,kP8Read,0);return;}
    L.cell=cell;L.base=base;
    Pl08ChunkView view[3];
    if(!pl08_life_check(L,where,view)){pl08_hook_free(cell);L.cell=nullptr;L.base=nullptr;return;}
    pl08_life_publish(L,where,view);
}
void pl08_life_sync(Pl08PackLife& L,const char* where) {
    const bool want=L.player_file==kPl08PlayerFile;
    if(!want){pl08_life_unpublish(L,where);return;}
    if(L.published)return;
    if(!L.cell){pl08_life_open(L,where);return;}
    // pl08 again in the room that unpublished it: the kept bytes are proved again before anything is visible.
    ++L.revalidations;
    Pl08ChunkView view[3];
    if(pl08_life_check(L,where,view))pl08_life_publish(L,where,view);
}
void pl08_life_room_leave(Pl08PackLife& L,const char* where) {
    if(!L.cell){pl08_life_unpublish(L,where);return;}
    L.published=false;pl08_hook_published(nullptr);
    pl08_hook_retire_owned();                // queued owned records are revoked before the bytes go
    const unsigned reset=pl08_hook_reset();
    pl08_hook_free(L.cell);L.cell=nullptr;L.base=nullptr;++L.retires;
    P8LOG("P8PACK retire at=%s gen=%u ids_reset=%u retires=%u\n",where,L.generation,reset,L.retires);
}
void pl08_life_room_enter(Pl08PackLife& L) {
    if(L.cell){++L.late_retires;pl08_life_room_leave(L,"late");}  // never two generations
    pl08_life_sync(L,"enter");
}
void pl08_life_player(Pl08PackLife& L,unsigned file) {L.player_file=file;pl08_life_sync(L,"bind");}
