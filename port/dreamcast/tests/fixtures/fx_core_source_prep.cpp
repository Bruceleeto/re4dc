// Minimal host platform/source types with the actual implementation included.
// Source field layouts are target-compiled separately; no callback body runs here.
#include <array>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <functional>
#include <string>
#include <vector>
#include <sys/mman.h>
#define RE4DC_FX_CORE_TEX_PREP 1
#define RE4DC_EFFECT_ROOM 7
#define RE4DC_FX_SCAN 1
#define RE4DC_ROUTE_MOVIES 1
#define RE4DC_SS_UI_ORDER 1
#define RE4DC_UI_FRAG_RESERVE 1
#include "native_ui.h"
using u32=unsigned;
struct cEsp {
    struct { unsigned owner,Call_no; } info;
    unsigned m_Be_flg,m_Id,m_Tex_id,m_Ptn_no,m_Shimmer_type,m_Tool_flg,m_Flg,xA4;
};
struct cEsp0a:cEsp { struct { unsigned char Type,Base_alpha; } m_Free; };
struct cEsp0e:cEsp { struct { float alpha; unsigned Rand_seed; } m_Free; };
struct TEXHeader { unsigned width,height,format; const void* data; };
struct TEXDescriptor { const void* CLUTHeader; TEXHeader* textureHeader; };
struct TEXPalette { unsigned numDescriptors; TEXDescriptor* descriptorArray; };
struct EspAnmData { unsigned Frames,Width,Height,Cx,Cy; };
struct TextureWork { unsigned Owner; TEXPalette* pTpl; EspAnmData* pAnm; };
struct EspSystem { unsigned nEsp; cEsp *pEspBuf,*pDmyEsp; TextureWork Esp_tex_tbl[32]; };
struct Game { unsigned Rno0,Frame_cnt,System; int nPrim; unsigned vtx_buf_no; std::uintptr_t prim_cnt,prim_base; };
struct OtData { OtData* next; void* data; void (*func)(void*); };
using OtPrim=OtData;
struct OtWork { OtData* list; unsigned max; };
constexpr unsigned OT_MAX=23;
struct Source { TEXPalette tpl; EspAnmData anm; TEXDescriptor td; TEXHeader th; alignas(32) unsigned char pixels[32]; };
struct Arena { Game game; EspSystem sys; alignas(32) unsigned char pool[8][0x150]; OtData buckets[2]; alignas(32) unsigned char prims[1024]; Source source; };
unsigned char* mapping;
Arena* arena;
#define RE4_MEM_LO reinterpret_cast<std::uintptr_t>(mapping)
#define RE4_MEM_HI (RE4_MEM_LO+65535)
Game* pG;
EspSystem* g_pEspSys;
OtWork g_OtWork[OT_MAX];
unsigned G_ROOM_ID,re4dc_fx_esp_gen,room_generation,callback_calls,owned_calls;
bool room_live,owner_live;
extern "C" int re4dc_room4_state(unsigned* g,unsigned*,unsigned*,unsigned*,unsigned*) { *g=room_generation;return room_live; }
extern "C" int re4dc_model_owned_source(const void* p,unsigned n) {
    ++owned_calls;
    auto a=reinterpret_cast<std::uintptr_t>(p),b=reinterpret_cast<std::uintptr_t>(&arena->source);
    return owner_live && a>=b && n<=sizeof(Source) && a-b<=sizeof(Source)-n;
}
void EspCommonTrans(cEsp*){++callback_calls;}
extern "C" void Esp0a_Trans(cEsp*){++callback_calls;}
extern "C" void Esp0a_Trans2(cEsp*){++callback_calls;}
extern "C" void Esp0b_Trans(cEsp*){++callback_calls;}
extern "C" void Esp0e_Trans(cEsp*){++callback_calls;}
void Esp47_Trans(cEsp*){++callback_calls;}
void Unknown(cEsp*){++callback_calls;}
#include "actual_source_helpers.inc"
#include "fx_core_source_prep.inc"
struct Key { unsigned crc,fnv; bool operator==(const Key& b)const{return crc==b.crc&&fnv==b.fnv;} };
namespace re4dc::texture { constexpr unsigned kArgb4444=2,kAlpha=1,kPayloadTwiddled=1; }
struct NativeTexture { unsigned width=256,height=256,format=2,flags=1,payload=1,data_size=131072,reserved_0=0; };
struct Package {
    struct Header {unsigned texture_count=1;} h;
    NativeTexture texture;
    bool complete=true,has_vram=true,has_textures=true;
    unsigned bytes=131072;
    bool upload_complete()const{return complete;}
    const Header& header()const{return h;}
    void* pvr_texture(unsigned)const{return has_vram?reinterpret_cast<void*>(32):nullptr;}
    unsigned vram_bytes()const{return bytes;}
    const NativeTexture* textures()const{return has_textures?&texture:nullptr;}
};
struct Entry { bool valid=true; Key key{0x441a0cca,0x10da6929}; unsigned frame=1; Package package; } entries[4];
unsigned frame,handle_reset,fx_frame,fx_count,fx_new_loads,load_opens,fx_evict_frame,vram_claims;
constexpr unsigned kFxNewLoads=4;
bool ready,frame_ready,stream_scene,stream_retire,stream_aborted,direct_open,draining_parts,fx_resident_only,movie_texture,ss_ui,frag_held;
Key frag_key;
int identity_result;
Key identity_key;
struct Identity { int lookup(const void*,unsigned,unsigned,unsigned,unsigned& crc,unsigned& fnv,const void*,unsigned,unsigned) {crc=identity_key.crc;fnv=identity_key.fnv;return identity_result;} } core_identities;
int re4dc_ss_ui_order(){return ss_ui;}
unsigned pvr_mem_available(){return 929920;}
std::vector<std::string> logs;
void re4dc_log(const char* format,...) {char b[1024];va_list a;va_start(a,format);vsnprintf(b,sizeof(b),format,a);va_end(a);logs.emplace_back(b);}
unsigned texcheck_failures,loader_calls,loader_opens;
#define RE4DC_TEXCHK_FAIL(key,reason) (++texcheck_failures)
Entry* loader_result;
std::function<void()> on_load;
Entry* load(const Re4dcUiImage&,bool ordinary,const Key* key) {
    if(!ordinary || !key || !(*key==identity_key))std::abort();
    ++loader_calls;load_opens+=loader_opens;
    if(on_load)on_load();
    return loader_result;
}
#include "native_ui_fx_core_prep.inc"
unsigned assertions;
#define CHECK(x) do{++assertions;if(!(x)){std::fprintf(stderr,"check failed line %d: %s\n",__LINE__,#x);std::exit(1);}}while(0)
cEsp* slot(unsigned i=0){return reinterpret_cast<cEsp*>(arena->pool[i]);}
OtData* primitive(unsigned i=0){return reinterpret_cast<OtData*>(arena->prims+i*64);}
void reset() {
    std::memset(arena,0,sizeof(*arena));std::memset(g_OtWork,0,sizeof(g_OtWork));
    pG=&arena->game;g_pEspSys=&arena->sys;
    pG->Rno0=3;pG->Frame_cnt=900;pG->nPrim=512;pG->prim_cnt=reinterpret_cast<std::uintptr_t>(arena->prims);pG->prim_base=pG->prim_cnt+64;
    G_ROOM_ID=0x11c;room_live=owner_live=true;room_generation=12;re4dc_fx_esp_gen=4;
    g_pEspSys->nEsp=8;g_pEspSys->pEspBuf=slot();
    auto* e=slot();e->m_Be_flg=1;e->m_Id=0;e->m_Tex_id=0x1d;e->xA4=1;e->info.owner=1;e->info.Call_no=9;
    g_OtWork[0]={arena->buckets,2};arena->buckets[1].next=primitive();primitive()->data=e;primitive()->func=reinterpret_cast<void(*)(void*)>(EspCommonTrans);
    auto& s=arena->source;s.tpl={1,&s.td};s.anm={1,256,256,0,0};s.td={nullptr,&s.th};s.th={256,256,1,s.pixels};g_pEspSys->Esp_tex_tbl[0x1d]={0,&s.tpl,&s.anm};
    frame=1;handle_reset=2;fx_frame=0;fx_count=99;fx_new_loads=3;load_opens=10;fx_evict_frame=0;vram_claims=0;
    ready=frame_ready=true;stream_scene=stream_retire=stream_aborted=direct_open=draining_parts=fx_resident_only=movie_texture=ss_ui=frag_held=false;
    frag_key=identity_key=kFxCoreKey;identity_result=1;
    for(auto& entry:entries)entry=Entry{};
    loader_result=&entries[0];loader_calls=0;loader_opens=1;on_load={};texcheck_failures=0;callback_calls=0;owned_calls=0;logs.clear();
    fxCoreAttemptFrame=~0U;fxCorePreparedFrame=fxCorePreparedEpoch=fxCoreAcquired=0;fxCoreCounts={};
}
Re4dcFxCoreDemand demand;
int source(){return re4dc_fx_core_source(frame,&demand);}
void expect_source(int value){CHECK(source()==value);CHECK(callback_calls==0);}
void check_refusal(const std::function<void()>& change,int result){reset();change();expect_source(result);}
void source_tests() {
    reset();const Arena before=*arena;expect_source(1);CHECK(std::memcmp(arena,&before,sizeof(before))==0);CHECK(demand.accepted==1&&demand.slot==0&&demand.callback==1);CHECK(re4dc_fx_core_current(frame,&demand)==1);
    struct Callback {void(*fn)(cEsp*);unsigned id,kind;} callbacks[]={{EspCommonTrans,0x0b,1},{Esp0a_Trans2,0,2},{Esp0a_Trans,0x0a,3},{Esp0b_Trans,0x0b,4},{Esp0e_Trans,0x0e,5},{Esp47_Trans,0x47,6}};
    for(auto c:callbacks){reset();slot()->m_Id=c.id;primitive()->func=reinterpret_cast<void(*)(void*)>(c.fn);if(c.kind==3)reinterpret_cast<cEsp0a*>(slot())->m_Free.Type=1;if(c.kind==5)reinterpret_cast<cEsp0e*>(slot())->m_Free.alpha=.02f;expect_source(1);CHECK(demand.callback==c.kind);}
    for(auto c:callbacks)if(c.kind!=1){reset();slot()->m_Id=0x72;primitive()->func=reinterpret_cast<void(*)(void*)>(c.fn);expect_source(0);}
    check_refusal([]{slot()->m_Id=0;primitive()->func=reinterpret_cast<void(*)(void*)>(Unknown);},0);
    check_refusal([]{slot()->m_Id=0xa;primitive()->func=reinterpret_cast<void(*)(void*)>(Esp0a_Trans);},0);
    check_refusal([]{slot()->m_Id=0xe;primitive()->func=reinterpret_cast<void(*)(void*)>(Esp0e_Trans);reinterpret_cast<cEsp0e*>(slot())->m_Free.alpha=.01f;},0);
    for(unsigned owner:{0U,0x10U,0x34U,0x4fU,0x5eU,1U,0xd0U}){reset();slot()->info.owner=owner;expect_source(1);}
    check_refusal([]{slot()->info.owner=0x51;},0);
    check_refusal([]{slot()->m_Be_flg=0;},0);check_refusal([]{slot()->m_Id=0xff;},0);check_refusal([]{slot()->m_Tex_id=0x1c;},0);check_refusal([]{slot()->m_Ptn_no=1;},0);check_refusal([]{slot()->m_Shimmer_type=1;},0);
    for(unsigned flag:{0x2000U,0x4000U,0x10000U})check_refusal([flag]{slot()->m_Tool_flg=flag;},0);
    check_refusal([]{slot()->m_Flg=0x10;},0);check_refusal([]{slot()->xA4=0;},0);check_refusal([]{g_pEspSys->pDmyEsp=slot();},0);
    check_refusal([]{G_ROOM_ID=0x200;},0);check_refusal([]{pG->Rno0=2;},0);check_refusal([]{pG=nullptr;},0);
    reset();pG->System=0x100c00;expect_source(1);
    check_refusal([]{room_live=false;},-1);check_refusal([]{room_generation=0;},-1);
    check_refusal([]{g_pEspSys=reinterpret_cast<EspSystem*>(1);},-2);check_refusal([]{g_pEspSys->nEsp=1025;},-2);check_refusal([]{g_pEspSys->nEsp=0;},-2);check_refusal([]{g_pEspSys->pEspBuf=reinterpret_cast<cEsp*>(1);},-2);
    check_refusal([]{pG->nPrim=0;},-3);check_refusal([]{pG->nPrim=0x100001;},-3);check_refusal([]{pG->vtx_buf_no=2;},-3);check_refusal([]{pG->prim_base=pG->prim_cnt-32;},-3);check_refusal([]{pG->prim_base=pG->prim_cnt+544;},-3);check_refusal([]{++pG->prim_base;},-3);
    check_refusal([]{g_OtWork[0].max=1025;},-4);check_refusal([]{g_OtWork[0].list=reinterpret_cast<OtData*>(1);},-4);check_refusal([]{arena->buckets[1].data=slot();},-4);check_refusal([]{primitive()->next=reinterpret_cast<OtData*>(1);},-4);check_refusal([]{primitive()->next=primitive(1);},-4);check_refusal([]{primitive()->next=primitive();},-4);
    check_refusal([]{primitive()->data=reinterpret_cast<void*>(1);},0);check_refusal([]{primitive()->data=arena->pool[0]+4;},0);
    reset();pG->prim_base+=64;*slot(1)=*slot();*primitive(1)=*primitive();primitive(1)->data=slot(1);primitive()->next=primitive(1);expect_source(1);CHECK(demand.accepted==2);
    check_refusal([]{owner_live=false;},-5);check_refusal([]{g_pEspSys->Esp_tex_tbl[0x1d].Owner=1;},-5);
    // Address is inside RAM bounds but PROT_NONE and outside the live source owner.
    check_refusal([]{g_pEspSys->Esp_tex_tbl[0x1d].pTpl=reinterpret_cast<TEXPalette*>(mapping+61440);},-5);
    check_refusal([]{arena->source.tpl.descriptorArray=reinterpret_cast<TEXDescriptor*>(mapping+61440);},-5);
    check_refusal([]{arena->source.td.textureHeader=reinterpret_cast<TEXHeader*>(mapping+61440);},-5);
    for(auto change:std::vector<std::function<void()>>{[]{arena->source.tpl.numDescriptors=2;},[]{arena->source.anm.Frames=2;},[]{arena->source.anm.Width=128;},[]{arena->source.anm.Height=128;},[]{arena->source.anm.Cx=1;},[]{arena->source.anm.Cy=1;},[]{arena->source.td.CLUTHeader=arena->source.pixels;},[]{arena->source.th.width=128;},[]{arena->source.th.height=128;},[]{arena->source.th.format=2;},[]{arena->source.th.data=reinterpret_cast<void*>(1);}})check_refusal(change,-5);
    for(auto change:std::vector<std::function<void()>>{[]{++frame;},[]{++pG->Frame_cnt;},[]{++room_generation;},[]{++re4dc_fx_esp_gen;},[]{++g_pEspSys->nEsp;},[]{++slot()->info.Call_no;},[]{arena->pool[0][0x140]^=1;},[]{primitive()->data=slot(1);},[]{g_OtWork[0].max=1;},[]{arena->source.th.data=arena->source.pixels+4;}}){reset();CHECK(source()==1);change();CHECK(re4dc_fx_core_current(frame,&demand)==0);}
}
void native_tests() {
    reset();const Arena before=*arena;fxCoreTexturePrepare();CHECK(loader_calls==1&&fxCoreCounts.ready==1&&fxCorePreparedFrame==1);CHECK(fx_new_loads==1&&fx_count==0&&fx_frame==frame);CHECK(!fx_resident_only&&callback_calls==0);CHECK(std::memcmp(arena,&before,sizeof(before))==0);fxCoreBeginFxFrame();CHECK(fx_new_loads==1);fxCoreTexturePrepare();CHECK(loader_calls==1);CHECK(source()==1);fxCoreTextureAcquired(demand.image,&entries[0]);CHECK(fxCoreAcquired==1);fxCoreFinish();CHECK(fxCoreCounts.unused==0);
    reset();fxCoreTexturePrepare();fxCoreFinish();CHECK(fxCoreCounts.unused==1);CHECK(logs.back().find("potential_only=1")!=std::string::npos);
    reset();pG->prim_base=pG->prim_cnt+8*64;for(unsigned i=1;i<8;++i){*slot(i)=*slot();*primitive(i)=*primitive();primitive(i)->data=slot(i);primitive(i-1)->next=primitive(i);}primitive(7)->next=nullptr;fxCoreTexturePrepare();CHECK(loader_calls==1&&fxCoreCounts.ready==1);CHECK(source()==1&&demand.accepted==8);
    reset();primitive()->data=nullptr;fxCoreTexturePrepare();CHECK(loader_calls==0&&fxCoreCounts.attempts==0);
    reset();loader_opens=0;fxCoreTexturePrepare();CHECK(fxCoreCounts.ready==1&&fx_new_loads==0);
    reset();frag_held=true;fxCoreTexturePrepare();CHECK(fxCoreCounts.ready==1);CHECK(logs.back().find("held=1")!=std::string::npos);
    for(bool* guard:{&stream_scene,&stream_retire,&stream_aborted,&direct_open,&draining_parts,&fx_resident_only,&movie_texture,&ss_ui}){reset();*guard=true;fxCoreTexturePrepare();CHECK(loader_calls==0&&*guard);}
    reset();vram_claims=1;fxCoreTexturePrepare();CHECK(loader_calls==0);reset();ready=false;fxCoreTexturePrepare();CHECK(loader_calls==0);reset();frame_ready=false;fxCoreTexturePrepare();CHECK(loader_calls==0);reset();frame=0;fxCoreTexturePrepare();CHECK(loader_calls==0);
    reset();fx_frame=frame;fx_new_loads=4;fxCoreTexturePrepare();CHECK(loader_calls==0&&fx_new_loads==4);
    reset();fx_frame=frame;fx_new_loads=3;fxCoreTexturePrepare();CHECK(loader_calls==1&&fx_new_loads==4);fxCoreBeginFxFrame();CHECK(fx_new_loads==4);
    for(int result:{-1,0,2}){reset();identity_result=result;fxCoreTexturePrepare();CHECK(loader_calls==0&&fxCoreCounts.refused==1);}
    reset();identity_key.fnv^=1;fxCoreTexturePrepare();CHECK(loader_calls==0);
    reset();loader_result=nullptr;fxCoreTexturePrepare();CHECK(fxCoreCounts.failed==1&&texcheck_failures==0&&!stream_aborted);
    for(auto change:std::vector<std::function<void()>>{[]{++handle_reset;g_pEspSys=reinterpret_cast<EspSystem*>(1);},[]{++frame;},[]{++pG->Frame_cnt;},[]{++room_generation;},[]{++re4dc_fx_esp_gen;},[]{++slot()->info.Call_no;},[]{primitive()->data=nullptr;},[]{identity_result=-1;},[]{identity_key.crc^=1;}}){reset();on_load=change;fxCoreTexturePrepare();CHECK(fxCoreCounts.failed==1&&fxCorePreparedFrame==0&&texcheck_failures==1);CHECK(!fx_resident_only);}
    for(auto change:std::vector<std::function<void()>>{[]{entries[0].valid=false;},[]{entries[0].key.fnv^=1;},[]{entries[0].frame=0;},[]{entries[0].package.complete=false;},[]{entries[0].package.h.texture_count=2;},[]{entries[0].package.has_vram=false;},[]{entries[0].package.bytes=1;},[]{entries[0].package.has_textures=false;},[]{entries[0].package.texture.width=128;},[]{entries[0].package.texture.height=128;},[]{entries[0].package.texture.format=1;},[]{entries[0].package.texture.flags=0;},[]{entries[0].package.texture.payload=0;},[]{entries[0].package.texture.data_size=1;},[]{entries[0].package.texture.reserved_0=1;},[]{loader_result=reinterpret_cast<Entry*>(1);},[]{loader_result=reinterpret_cast<Entry*>(reinterpret_cast<char*>(entries)+4);}}){reset();change();fxCoreTexturePrepare();CHECK(fxCoreCounts.failed==1&&fxCorePreparedFrame==0);}
    reset();CHECK(source()==1);fxCoreTextureAcquired(demand.image,nullptr);CHECK(fxCoreCounts.unprepared==1&&fxCoreCounts.acquired==0);
    reset();fxCoreTexturePrepare();CHECK(source()==1);++handle_reset;fxCoreTextureAcquired(demand.image,&entries[0]);CHECK(fxCoreCounts.unprepared==1&&fxCoreCounts.acquired==0);
    reset();frame=120;entries[0].frame=120;fxCoreTexturePrepare();fxCoreFinish();CHECK(logs.back().find("FXCORE_SUMMARY")!=std::string::npos);
}
int main(){mapping=static_cast<unsigned char*>(mmap(nullptr,65536,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0));CHECK(mapping!=MAP_FAILED);arena=reinterpret_cast<Arena*>(mapping);CHECK(sizeof(Arena)<61440);CHECK(mprotect(mapping+61440,4096,PROT_NONE)==0);source_tests();native_tests();std::printf("PASS %u assertions: actual reader, helper predicates and native prep; cache/platform are stubs\n",assertions);munmap(mapping,65536);}
