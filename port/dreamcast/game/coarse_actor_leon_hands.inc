// LEON_HAND_PACK=1 (crowd.mk; needs LEON_HAND_POSES=1, PS2_LEON=1, ACTOR_PL08=1; render only). Included by
// coarse_actor_owner_leon.inc. Leon's hands (roles 5 right / 6 left) for every pose come from the outfit's hand package
// (dc/native/pl00/leon_hands_pl00.re4hp, tools/d367/ps2leon/hands_pack.py), not from the image: the standard hands'
// arrays are left out of ps2leon_runtime.h (hands_pack.py derive), and leon4k::chunks[5] / [6] point at two fixed draw
// slots that hold the pose drawn now.
//   - Directory: read once from the package (rows: GC runtime key -> blob; blobs; sources: weapon archive -> blob).
//   - Cache: 4 cells in AICA RAM (per side: the home pose, prefetched at room load, and the last other pose), filled
//     from the disc and copied to the draw slot over G2 when the game swaps a hand info. A real-time swap between the
//     home hand and the equipped weapon's hand (grabs, the boat, the knife) is a copy, not a disc read.
//   - Prefetch: room load (the home poses) and weapon equip (ReadWepData: the weapon's own hand BINs).
//   - Anything else is read from the disc into the slot the first time it is drawn (the port's disc reads are
//     synchronous; the hand drawn before stays in the slot until then).
//   - The movie audio stream needs the whole 64 KiB AICA movie reserve: the cells are freed at movie open (and before
//     any runtime sound bank conversion) and refilled lazily on the next Leon draw.
// A slot change resets the role's immutable proof (IDs 6 / 7) and is part of the skin key, so the FTRV palette program
// and the chunk proof are rebuilt from the new bytes before use.
#include <kos/fs.h>
#include <fcntl.h>
#include <dc/spu.h>
#include <dc/sound/sound.h>
extern "C" unsigned char re4dc_dvd_buff[0x20000];
#pragma GCC push_options
#pragma GCC optimize("Os")  // cold loader code: size, not speed (image bytes are heap 4)
namespace leon_hand_pack {
constexpr unsigned kMagic=0x3150484Cu,kVersion=1,kRows=48,kBlobs=32,kSources=64;
constexpr unsigned kSlotBytes[2]={6144,6400};   // hands_pack.py SLOT_CAP (right, left)
constexpr unsigned kCellBytes=2*(6144+6400);    // AICA: per side a home cell and an other cell
struct Row { unsigned char role,blob; unsigned short positions,normals,palette; unsigned hash; };
struct Blob { unsigned char role,flags; unsigned short pc,nc,pal,tri,size[5],stream,offset32; };
struct Src { unsigned char wep,arc; unsigned short blob; };
static_assert(sizeof(Row)==12 && sizeof(Blob)==24 && sizeof(Src)==4,"hand package directory layout");
Row rows[kRows];Blob blobs[kBlobs];Src srcs[kSources];
unsigned nrows,nblobs,nsrcs,file_bytes;
int dir_state;  // 0 not read, 1 ready, 2 failed (logged once)
alignas(32) unsigned char slot5[kSlotBytes[0]];
alignas(32) unsigned char slot6[kSlotBytes[1]];
unsigned char* const slot[2]={slot5,slot6};
int slot_blob[2]={-1,-1};
unsigned aica;               // the cells' base (0: not allocated)
int cell_blob[4]={-1,-1,-1,-1};   // 0 right home, 1 right other, 2 left home, 3 left other
int refill[4]={-1,-1,-1,-1};      // what the cells held when they were freed
unsigned cell_used[4],use_clock;   // LRU per side: the least recently drawn cell of the side is replaced
unsigned reads,read_bytes,copies,hits,misses,yields,refills,alloc_fails;
inline unsigned r32(unsigned x){return (x+31u)&~31u;}
unsigned blob_bytes(const Blob& b){unsigned n=0;for(unsigned i=0;i<5;++i)n+=r32(b.size[i]);return n;}
unsigned cell_offset(unsigned c){return (c>>1)*2u*kSlotBytes[0]+(c&1u)*kSlotBytes[c>>1];}
const char* package(){return "/cd/dc/native/pl00/leon_hands_pl00.re4hp";}  // pl00 and pl08 hands are byte-identical

bool read_at(unsigned offset,void* to,unsigned bytes) {
    file_t f=fs_open(package(),O_RDONLY);
    if(f==FILEHND_INVALID)return false;
    const bool ok=fs_seek(f,offset,SEEK_SET)==off_t(offset) && fs_read(f,to,bytes)==ssize_t(bytes);
    fs_close(f);
    ++reads;read_bytes+=bytes;
    return ok;
}
// The package's directory (hands_pack.py checks every field it writes; here: the layout, the bounds the reads and
// slots rely on, and the standard hands as blobs 0 (right) and 1 (left)).
bool directory() {
    if(dir_state)return dir_state==1;
    dir_state=2;
    unsigned char* b=re4dc_dvd_buff+0x10000;  // DVD_BUFF2: used only inside synchronous DVD swaps (src/game/dvd.cpp)
    unsigned h[8]{};
    unsigned bad=1;
    if(read_at(0,h,32) && h[0]==kMagic && (h[1]&0xffffu)==kVersion && h[3]==kSlotBytes[0] && h[4]==kSlotBytes[1]) {
        nrows=h[1]>>16;nblobs=h[2]&0xffffu;nsrcs=h[2]>>16;file_bytes=h[6];
        const unsigned dir=h[5],ro=32,bo=ro+nrows*12,so=bo+nblobs*24;
        bad=2;
        if(nrows<=kRows && nblobs>=2 && nblobs<=kBlobs && nsrcs<=kSources && dir<=0x10000 && so+nsrcs*4<=dir && read_at(0,b,dir)) {
            std::memcpy(rows,b+ro,nrows*12);std::memcpy(blobs,b+bo,nblobs*24);std::memcpy(srcs,b+so,nsrcs*4);
            bad=(blobs[0].role!=5 || blobs[1].role!=6 || !(blobs[0].flags&blobs[1].flags&1))?3:0;
            for(unsigned i=0;i<nblobs;++i){const Blob& x=blobs[i];
                if((x.role-5u)>1u || blob_bytes(x)>kSlotBytes[x.role-5] || x.offset32*32u+blob_bytes(x)>file_bytes)bad=4;}
        }
    }
    re4dc_log("LHPACK directory %s rows=%u blobs=%u sources=%u file=%u why=%u\n",package(),nrows,nblobs,nsrcs,file_bytes,bad);
    if(bad)return false;
    dir_state=1;
    return true;
}
// The cells live in AICA RAM between the sound layout and the movie reserve; never while a movie streams.
bool cells() {
    if(aica)return true;
    aica=snd_mem_malloc(kCellBytes);
    if(!aica){if(alloc_fails++<4)re4dc_log("LHPACK cells: no %u AICA bytes (largest %u)\n",kCellBytes,unsigned(snd_mem_available()));return false;}
    return true;
}
int cell_of(int b){for(unsigned c=0;c<4;++c)if(cell_blob[c]==b)return int(c);return -1;}
// The side's cell for a new blob: an empty one, else the least recently drawn (the home poses are only prefetched first).
unsigned cell_for(int b){const unsigned c=(blobs[b].role-5u)*2u;
    if(cell_blob[c]<0)return c;if(cell_blob[c+1]<0)return c+1;return cell_used[c]<=cell_used[c+1]?c:c+1;}
// Put blob b in its cell from `from` (main RAM holding its bytes).
void cache(int b,const unsigned char* from) {
    if(!cells())return;
    const unsigned c=cell_for(b);
    spu_memload(aica+cell_offset(c),from,blob_bytes(blobs[b]));
    cell_blob[c]=b;cell_used[c]=++use_clock;
}
// Prefetch blob b into its cell (bounce through DVD_BUFF2; the draw slots are not touched).
void prefetch(int b) {
    if(b<0 || unsigned(b)>=nblobs || cell_of(b)>=0 || !cells())return;
    unsigned char* t=re4dc_dvd_buff+0x10000;
    if(!read_at(unsigned(blobs[b].offset32)*32u,t,blob_bytes(blobs[b])))return;
    cache(b,t);
}
void refill_now() {
    if(refill[0]<0 && refill[1]<0 && refill[2]<0 && refill[3]<0)return;
    if(!cells())return;
    ++refills;
    for(unsigned c=0;c<4;++c){const int b=refill[c];refill[c]=-1;prefetch(b);}
}
void prefetch_home() {
    if(!directory())return;
    for(unsigned i=0;i<nblobs;++i)if(blobs[i].flags&2)prefetch(int(i));
}
void reset_role_ids(unsigned role);   // coarse_actor_owner_leon.inc, after coarse_actor_geometry_once.inc
// Make slot `side` hold blob b and point leon4k::chunks[5 + side] at it.
bool load(unsigned side,int b) {
    if(slot_blob[side]==b)return true;
    const Blob& x=blobs[b];
    const int c=cell_of(b);
    if(c>=0){spu_memread(slot[side],aica+cell_offset(unsigned(c)),blob_bytes(x));++copies;++hits;cell_used[c]=++use_clock;}
    else {
        ++misses;
        slot_blob[side]=-1;
        if(!read_at(unsigned(x.offset32)*32u,slot[side],blob_bytes(x)))return false;
        // The hitch check reads these: a disc read while drawing (a pose not in the cache).
        if(misses<=64)re4dc_log("LHPACK miss blob=%u role=%u cells=%d/%d/%d/%d aica=%u\n",unsigned(b),5u+side,
            cell_blob[0],cell_blob[1],cell_blob[2],cell_blob[3],aica?1u:0u);
        cache(b,slot[side]);
    }
    unsigned char* p=slot[side];const unsigned char* a[5];
    for(unsigned i=0;i<5;++i){a[i]=p;p+=r32(x.size[i]);}
    leon4k::chunks[5+side]=leon4k::Chunk{5+side,x.pc,x.nc,x.pal,x.tri,x.stream,a[0],a[1],a[2],a[3],
        reinterpret_cast<const leon4k::Weight*>(a[4])};
    slot_blob[side]=b;
    reset_role_ids(5+side);
    return true;
}
// The blob that draws role 5 / 6 for this hand info: its GC key's row, else the standard hand.
int blob_for(unsigned role,const cModelInfo* info) {
    if(info && info->pData && info->pData->vtxOrig) {
        const ModelData* d=info->pData;
        const unsigned pal=d->weight_ext_num>255?d->weight_ext_num:d->weight_palette_num;
        const unsigned h=fingerprint(d->vtxOrig);
        for(unsigned k=0;k<nrows;++k) {
            const Row& r=rows[k];
            if(r.role==role && r.positions==d->nVtx && r.normals==d->nNrm && r.palette==pal && r.hash==h && r.blob<nblobs &&
               blobs[r.blob].role==role)return r.blob;
        }
#if defined(RE4DC_DBG_WARP) && RE4DC_DBG_WARP
        static unsigned seen[16],nseen;bool known=false;
        for(unsigned k=0;k<nseen;++k)known|=seen[k]==(h^role);
        if(!known && nseen<16){seen[nseen++]=h^role;
            re4dc_log("LEONHAND standard role=%u key=%u/%u/%u/%u (no PS2 pose hand)\n",role,unsigned(d->nVtx),unsigned(d->nNrm),pal,h);}
#endif
    }
    return int(role-5);   // the standard hand (blob 0 right, 1 left)
}
inline unsigned std_pal(unsigned role){return blobs[role-5].pal;}  // the standard hands are blobs 0 / 1
}
namespace {
unsigned leon_hand_asset(unsigned){return 0;}  // unused: the slots keep IDs 6 / 7
struct LeonHandPick { const leon4k::Chunk* chunk;re4dc_source::ChunkInput input;unsigned asset;int pose; };
// Role 5 / 6 for this hand info, loaded into its slot (nullptr: no package / read failure: the plan declines).
__attribute__((noinline)) LeonHandPick leon_hand_pick(unsigned role,const cModelInfo* info,const leon4k::Chunk&,const re4dc_source::ChunkInput&) {
    using namespace leon_hand_pack;
    if(!directory())return {nullptr,{},0,-1};
    refill_now();
    const int b=blob_for(role,info);
    if(!load(role-5,b))return {nullptr,{},0,-1};
    const auto& c=leon4k::chunks[role];const Blob& x=blobs[b];
    return {&c,re4dc_source::ChunkInput{{c.positions,x.size[0]},{c.normals,x.size[1]},{c.uv,x.size[2]},{c.stream,x.size[3]},
        {reinterpret_cast<const unsigned char*>(c.weights),x.size[4]},c.position_count,c.normal_count,c.palette_count,c.triangles,119u},
        role+1u,b};
}
inline unsigned leon_r32(unsigned x){return (x+31u)&~31u;}
const leon4k::Chunk* leon_cur[8]={&leon4k::chunks[0],&leon4k::chunks[1],&leon4k::chunks[2],&leon4k::chunks[3],
    &leon4k::chunks[4],&leon4k::chunks[5],&leon4k::chunks[6],&leon4k::chunks[7]};
unsigned leon_cur_key;
inline unsigned leon_hand_key(unsigned costume,int right,int left) {
    return costume|unsigned(right+1)<<8|unsigned(left+1)<<16;
}
}
// Room load (ui_bridge.cpp, with the pl08 package): the home poses into their cells.
extern "C" void re4dc_leon_hands_room_enter() {
    using namespace leon_hand_pack;
    prefetch_home();refill_now();
    re4dc_log("LHPACK room reads=%u bytes=%u copies=%u hits=%u misses=%u yields=%u refills=%u cells=%d/%d/%d/%d\n",
        reads,read_bytes,copies,hits,misses,yields,refills,cell_blob[0],cell_blob[1],cell_blob[2],cell_blob[3]);
}
// Weapon equip (read.cpp ReadWepData, after the weapon archive read): the weapon's own hand BINs into the other cells.
extern "C" void re4dc_leon_hands_weapon(const char* name) {
    using namespace leon_hand_pack;
    if(!name || !directory())return;
    const char* w=name;
    while(*w && !(w[0]=='w' && w[1]=='e' && w[2]=='p'))++w;
    if(!*w || unsigned(w[3]-'0')>9u || unsigned(w[4]-'0')>9u)return;
    const unsigned no=unsigned(w[3]-'0')*10u+unsigned(w[4]-'0');
    bool done[2]={};
    for(unsigned i=0;i<nsrcs;++i) {
        const Blob& x=blobs[srcs[i].blob];
        if(srcs[i].wep!=no || done[x.role-5] || (x.flags&2))continue;
        done[x.role-5]=true;prefetch(srcs[i].blob);
    }
}
// Movie open (native_movie.cpp) and a runtime sound bank conversion (audio_aica.cpp): give the AICA cells back.
extern "C" void re4dc_leon_hands_yield() {
    using namespace leon_hand_pack;
    if(!aica)return;
    snd_mem_free(aica);aica=0;++yields;
    for(unsigned c=0;c<4;++c){refill[c]=cell_blob[c];cell_blob[c]=-1;}
}
#pragma GCC pop_options
