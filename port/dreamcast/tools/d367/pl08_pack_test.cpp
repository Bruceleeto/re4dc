// pl08_pack_test.cpp (host; driven by pl08_pack_test.sh): the target's own ACTOR_PL08_PACK routines
// (game/actor_pl08_pack_check.inc: validation + lifetime) with mocked hooks.
//   pl08_pack_test validate <package>...   "<file> <why> <detail>" per package (malformed variants)
//   pl08_pack_test identity <package>      the package arrays == leon_pl08_runtime.h's compiled arrays (needs -I the
//                                          private ACTOR_PL08_DIR and the leon4k bundle)
//   pl08_pack_test life <package>          lifetime scenarios; exits 1 on the first failed check
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>
#include "leon4k_runtime.h"
#include "leon_pl08_runtime.h"
#define P8LOG(...) std::printf(__VA_ARGS__)
namespace {
// ---- mocks
std::vector<unsigned char> g_file;bool g_present=true,g_alloc_fail=false,g_read_fail=false;int g_preflight_fail=-1;
bool g_open=false;unsigned g_opens=0,g_closes=0,g_allocs=0,g_frees=0,g_resets=0,g_owned=0;
alignas(64) unsigned char g_arena[65536];bool g_arena_used=false;
std::vector<std::string> g_events;const unsigned char* g_view_lo=nullptr;const unsigned char* g_view_hi=nullptr;
const void* g_published=nullptr;
int pl08_hook_open() {if(!g_present)return -1;g_open=true;++g_opens;return int(g_file.size());}
bool pl08_hook_read(unsigned char* d,unsigned n) {
    if(!g_open)return false;
    g_open=false;++g_closes;
    if(g_read_fail || n!=g_file.size())return false;
    std::memcpy(d,g_file.data(),n);return true;
}
void pl08_hook_close() {if(g_open){g_open=false;++g_closes;}}
unsigned char* pl08_hook_alloc(unsigned n) {
    if(g_alloc_fail || g_arena_used || n+8>sizeof(g_arena))return nullptr;
    g_arena_used=true;++g_allocs;g_view_lo=g_arena+8;g_view_hi=g_arena+8+n;g_events.push_back("alloc");
    return g_arena+8;  // deliberately 8 mod 32: the routines must align
}
void pl08_hook_free(unsigned char* p) {
    if(p!=g_arena+8 || !g_arena_used){std::printf("FAIL free of a pointer not allocated\n");std::exit(1);}
    std::memset(g_arena,0xa5,sizeof(g_arena));g_arena_used=false;++g_frees;g_events.push_back("free");
}
struct Pl08ChunkView;
bool pl08_hook_preflight(const Pl08ChunkView&,unsigned&);
unsigned pl08_hook_reset() {++g_resets;g_events.push_back("reset");return 3;}
void pl08_hook_published(const Pl08ChunkView*);
void pl08_hook_retire_owned() {++g_owned;g_events.push_back("owned");}
}
namespace {
#include "actor_pl08_pack_check.inc"
unsigned g_preflight_calls=0;
bool pl08_hook_preflight(const Pl08ChunkView& v,unsigned& d) {
    ++g_preflight_calls;d=v.role;return g_preflight_fail<0 || unsigned(g_preflight_fail)!=v.role;
}
void pl08_hook_published(const Pl08ChunkView* v) {
    g_published=v;g_events.push_back(v?"publish":"clear");
    if(v)for(unsigned k=0;k<3;++k)for(unsigned a=0;a<5;++a)
        if(v[k].array[a]<g_view_lo || v[k].array[a]+v[k].bytes[a]>g_view_hi || (reinterpret_cast<unsigned long>(v[k].array[a])&31u)){
            std::printf("FAIL view outside the cell or misaligned\n");std::exit(1);}
}
int failures=0;
#define CHECK(c) do{if(!(c)){std::printf("FAIL %s:%d %s\n",__FILE__,__LINE__,#c);++failures;}}while(0)
std::vector<unsigned char> load(const char* path) {
    std::vector<unsigned char> b;FILE* f=std::fopen(path,"rb");if(!f)return b;
    unsigned char buf[4096];size_t n;while((n=std::fread(buf,1,sizeof(buf),f))>0)b.insert(b.end(),buf,buf+n);std::fclose(f);return b;
}
void reset_mocks() {g_present=true;g_alloc_fail=g_read_fail=false;g_preflight_fail=-1;g_events.clear();}
std::string events() {std::string s;for(auto& e:g_events)s+=e+" ";g_events.clear();return s;}
int life(const std::vector<unsigned char>& pkg) {
    g_file=pkg;Pl08PackLife L{};
    // 1. pl00 bound: nothing is read or allocated in its rooms.
    pl08_life_player(L,6);pl08_life_room_enter(L);pl08_life_room_leave(L,"leave");pl08_life_room_enter(L);
    CHECK(g_allocs==0 && g_opens==0 && !L.published && !L.cell);
    pl08_life_room_leave(L,"leave");
    // 2. pl00 -> pl08 inside a room load (chapter change: bind after the room enter): open, reset BEFORE publish.
    pl08_life_room_enter(L);events();pl08_life_player(L,0x5A);
    CHECK(L.published && L.cell && L.generation==1 && g_allocs==1);
    CHECK(events()=="alloc reset publish ");
    CHECK(!g_open && g_opens==g_closes);
    // 3. pl08 -> pl08 room change: owned revoked, proofs reset, freed; the next room reloads at the SAME address and
    //    the reset precedes the new publication.
    pl08_life_room_leave(L,"leave");
    CHECK(!L.published && !L.cell && g_frees==1 && events()=="clear owned reset free ");
    pl08_life_room_enter(L);
    CHECK(L.published && L.generation==2 && L.same_address==1 && events()=="alloc reset publish ");
    // 4. pl08 -> pl00 inside a room (PlChangeData): unpublish, cell kept (queued frames), no free until the leave.
    pl08_life_player(L,6);
    CHECK(!L.published && L.cell && g_frees==1 && events()=="clear reset ");
    //    ... and back to pl08 in the same room: the kept bytes are revalidated, no second cell.
    unsigned allocs=g_allocs;pl08_life_player(L,0x5A);
    CHECK(L.published && g_allocs==allocs && L.revalidations==1 && L.generation==3);
    events();
    //    ... kept bytes changed while unpublished: the revalidation refuses, nothing is published, freed at leave.
    pl08_life_player(L,6);L.base[300]^=1u;pl08_life_player(L,0x5A);
    CHECK(!L.published && L.last_why==kP8Hash && L.cell);  // the payload hash catches it first
    pl08_life_room_leave(L,"leave");CHECK(!L.cell && g_frees==2);
    // 5. pl08 -> pl00 at a room change (room enter still sees pl08, the bind then switches): open, unpublish, free.
    pl08_life_room_enter(L);CHECK(L.published);pl08_life_player(L,6);CHECK(!L.published && L.cell);
    pl08_life_room_leave(L,"leave");CHECK(!L.cell);
    pl08_life_room_enter(L);CHECK(!L.cell && !L.published);pl08_life_room_leave(L,"leave");
    // 6. missing package: refusal, no allocation, source path.
    reset_mocks();g_present=false;unsigned a0=g_allocs;pl08_life_player(L,0x5A);pl08_life_room_enter(L);
    CHECK(!L.published && !L.cell && g_allocs==a0 && L.last_why==kP8Missing);pl08_life_room_leave(L,"leave");
    // 7. corrupt package (one payload bit): refused, the cell freed, nothing published.
    reset_mocks();g_file[1000]^=1u;unsigned f0=g_frees;pl08_life_room_enter(L);
    CHECK(!L.published && !L.cell && g_frees==f0+1 && L.last_why==kP8Hash);g_file=pkg;pl08_life_room_leave(L,"leave");
    // 8. truncated file: refused before any allocation.
    reset_mocks();g_file.resize(pkg.size()-32);a0=g_allocs;pl08_life_room_enter(L);
    CHECK(!L.published && g_allocs==a0 && L.last_why==kP8Size && !g_open);g_file=pkg;pl08_life_room_leave(L,"leave");
    // 9. allocation refused (heap-4 reserve): nothing published, file closed.
    reset_mocks();g_alloc_fail=true;pl08_life_room_enter(L);
    CHECK(!L.published && !L.cell && L.last_why==kP8Alloc && !g_open && g_opens==g_closes);pl08_life_room_leave(L,"leave");
    // 10. read failure: the cell is freed.
    reset_mocks();g_read_fail=true;f0=g_frees;pl08_life_room_enter(L);
    CHECK(!L.published && !L.cell && g_frees==f0+1 && L.last_why==kP8Read);pl08_life_room_leave(L,"leave");
    // 11. one chunk fails the target preflight: no partial model (nothing published), freed.
    reset_mocks();g_preflight_fail=8;f0=g_frees;pl08_life_room_enter(L);
    CHECK(!L.published && !L.cell && g_frees==f0+1 && L.last_why==kP8Preflight && g_published==nullptr);
    pl08_life_room_leave(L,"leave");
    // 12. a room enter while a cell is still live (no leave hook ran): late retire first, one generation at a time.
    reset_mocks();pl08_life_room_enter(L);CHECK(L.published);unsigned r0=L.retires;pl08_life_room_enter(L);
    CHECK(L.late_retires==1 && L.retires==r0+1 && L.published && g_arena_used);pl08_life_room_leave(L,"leave");
    CHECK(!g_arena_used && !g_open);
    std::printf("life: generation=%u publishes=%u unpublishes=%u retires=%u same_address=%u revalidations=%u refusals=%u "
        "late=%u allocs=%u frees=%u resets=%u owned=%u preflights=%u -> %s\n",L.generation,L.publishes,L.unpublishes,
        L.retires,L.same_address,L.revalidations,L.refusals,L.late_retires,g_allocs,g_frees,g_resets,g_owned,g_preflight_calls,
        failures?"FAIL":"PASS");
    return failures?1:0;
}
int identity(const std::vector<unsigned char>& pkg) {
    alignas(32) static unsigned char buf[65536];if(pkg.size()>sizeof(buf))return 1;std::memcpy(buf,pkg.data(),pkg.size());
    Pl08ChunkView v[3];unsigned d=0;const Pl08Why why=pl08_pack_validate(buf,unsigned(pkg.size()),v,d);
    CHECK(why==kP8None);if(why!=kP8None)return 1;
    for(unsigned k=0;k<3;++k) {
        const leon4k::Chunk& c=leon_pl08::chunks[k];
        const unsigned char* src[5]={c.positions,c.normals,c.uv,c.stream,reinterpret_cast<const unsigned char*>(c.weights)};
        CHECK(v[k].source_info==c.source_info && v[k].position_count==c.position_count && v[k].normal_count==c.normal_count &&
              v[k].palette_count==c.palette_count && v[k].triangles==c.triangles && v[k].bytes[3]==c.stream_bytes);
        for(unsigned a=0;a<5;++a)CHECK(!std::memcmp(v[k].array[a],src[a],v[k].bytes[a]));
    }
    CHECK(v[0].bytes[0]==sizeof(leon_pl08::r0_pos) && v[0].bytes[1]==sizeof(leon_pl08::r0_nrm) && v[0].bytes[2]==sizeof(leon_pl08::r0_uv) &&
          v[0].bytes[3]==sizeof(leon_pl08::r0_gx) && v[0].bytes[4]==sizeof(leon_pl08::r0_weights));
    CHECK(v[1].bytes[0]==sizeof(leon_pl08::r1_pos) && v[1].bytes[1]==sizeof(leon_pl08::r1_nrm) && v[1].bytes[2]==sizeof(leon_pl08::r1_uv) &&
          v[1].bytes[3]==sizeof(leon_pl08::r1_gx) && v[1].bytes[4]==sizeof(leon_pl08::r1_weights));
    CHECK(v[2].bytes[0]==sizeof(leon_pl08::r8_pos) && v[2].bytes[1]==sizeof(leon_pl08::r8_nrm) && v[2].bytes[2]==sizeof(leon_pl08::r8_uv) &&
          v[2].bytes[3]==sizeof(leon_pl08::r8_gx) && v[2].bytes[4]==sizeof(leon_pl08::r8_weights));
    std::printf("identity: 3 chunks, 15 arrays equal to leon_pl08_runtime.h (sizeof included) -> %s\n",failures?"FAIL":"PASS");
    return failures?1:0;
}
}
int main(int argc,char** argv) {
    if(argc>=3 && !std::strcmp(argv[1],"validate")) {
        for(int a=2;a<argc;++a) {
            const auto b=load(argv[a]);alignas(32) static unsigned char buf[65536 + 64];
            unsigned d=0;Pl08ChunkView v[3];Pl08Why why=kP8Size;
            if(b.size()<=65536){if(!b.empty())std::memcpy(buf,b.data(),b.size());why=pl08_pack_validate(buf,unsigned(b.size()),v,d);}
            std::printf("%s %s %u\n",argv[a],kPl08Why[why],d);
        }
        return 0;
    }
    if(argc==3 && !std::strcmp(argv[1],"identity"))return identity(load(argv[2]));
    if(argc==3 && !std::strcmp(argv[1],"life"))return life(load(argv[2]));
    std::fprintf(stderr,"usage: %s validate|identity|life <package>...\n",argv[0]);return 2;
}
