// Host-only cache/load boundary. The identity table and preparation above/below
// are actual production code; GPU work is intentionally not simulated here.
#define RE4DC_UI_VRAM 1
#define RE4DC_PVR_STREAM 1
#define RE4DC_TEX_RESIDENT_RESERVE_KB 8U
#define RE4DC_TEX_RESIDENT_RESERVE_SLOTS 2U
struct Key {unsigned crc,fnv;bool operator==(const Key& b)const{return crc==b.crc&&fnv==b.fnv;}};
struct FakePackage {unsigned bytes;unsigned vram_bytes()const{return bytes;}};
struct Entry {bool valid,lease;Key key;unsigned frame;FakePackage package;};
static const unsigned kTextureCount=8,kVramBudget=65536;
static Entry entries[kTextureCount];static Key missing_keys[4];
static unsigned frame,vram_claims,vram_budget,used,preload_loads,preload_skipped,pool_free;
static unsigned load_calls,hit_calls,uploads,prepare_order;
static bool frame_ready,source_draws_finished,stream_scene,stream_aborted,stream_retire,load_failure;
static SourceIdentityTable core_identities;
#define RE4DC_ENTRY_PINNED(e) ((e).frame==frame || (e).lease)
static unsigned pvr_mem_available(){return pool_free;}
static Entry* load(const Re4dcUiImage& image,bool pin,const Key* key){
 ++load_calls;
 assert(frame_ready&&!vram_claims&&!source_draws_finished&&!stream_scene&&!stream_aborted&&!stream_retire);
 assert(!phase_coarse&&!phase_batch&&!phase_effect&&pin&&key);
 assert(image.pixels&&image.format==1&&(image.width==96||image.width==128));
 if(load_failure)return nullptr;
 for(auto& e:entries)if(e.valid&&e.key==*key){++hit_calls;e.frame=frame;return &e;}
 for(auto& e:entries)if(!e.valid||!RE4DC_ENTRY_PINNED(e)){
  e={true,false,*key,frame,{6144}};++uploads;return &e;
 }
 assert(false);return nullptr;
}
static unsigned preload_least(unsigned width,unsigned height){
 unsigned pw=8,ph=8;while(pw<width)pw*=2;while(ph<height)ph*=2;
 return std::min(pw*ph*2,2048+pw*ph/4);
}
#include "../port/dreamcast/game/platform/include/native_effect_stage1_prepare.inc"
static void test_native_begin(){
 phase_ready=frame_ready=true;phase_finished=source_draws_finished=false;phase_begin=++phase_step;++frame;
 stage1_prepare_image();prepare_order=++phase_step;
}
static void test_native_skip(){phase_ready=frame_ready=false;phase_finished=source_draws_finished=false;phase_begin=++phase_step;}
alignas(32) static unsigned char archive_bytes[512],foreign_archive[512];
static void put32(unsigned offset,unsigned value){std::memcpy(archive_bytes+offset,&value,4);}
static void put16(unsigned offset,unsigned short value){std::memcpy(archive_bytes+offset,&value,2);}
static Key expected(unsigned room){return room==0x117?Key{0x5889803dU,0xd2ef2224U}:Key{0xdbbad2e7U,0x5b0b1eedU};}
static void make_archive(unsigned room){
 std::memset(archive_bytes,0,sizeof(archive_bytes));const unsigned width=room==0x117?96:128;
 const auto key=expected(room);
 put32(0,1);put32(16,448);std::memcpy(archive_bytes+20,"NTR",4);
 put16(84,width);put16(86,width);put32(88,1);put32(92,64);
 std::memcpy(archive_bytes+128,"R4NREF\0",8);put32(136,key.crc);put32(140,key.fnv);
 put32(144,width);put32(148,width);put32(152,1);put32(156,width*width);
 std::memcpy(archive_bytes+448,"R4NTBL\0",8);put32(456,1);put32(460,1);put32(464,12);
 put32(472,65536);put32(476,sizeof(archive_bytes));put32(480,128);put32(484,84);put32(488,64);
 put32(468,crc32(archive_bytes+480,12));assert(core_identities.adopt(archive_bytes,sizeof(archive_bytes)));
 assert(core_identities.count()==1);std::memcpy(foreign_archive,archive_bytes,sizeof(archive_bytes));
 tex={archive_bytes+128,width,width,1};td={&tex,nullptr};tpl={1};fake_descriptor=true;
 puzzle_anm={0,0,96,96,1};anm={0,0,128,128,1};
}
static void start(unsigned room=0x117){
 setup(room);make_archive(room);if(room==0x117||room==0x118||room==0x11c)prepare();else re4dc_esp_sprite_pass_begin();
 for(auto& e:entries)e={};
 for(auto& k:missing_keys)k={};
 ++frame;frame_ready=true;vram_claims=0;source_draws_finished=stream_scene=stream_aborted=stream_retire=load_failure=false;
 vram_budget=kVramBudget;used=preload_loads=preload_skipped=load_calls=hit_calls=uploads=prepare_order=0;pool_free=kVramBudget;
}
static void unchanged_prepare(){
 const auto ticket=s_stage1_pending;const auto addition=s_fx_addition;const unsigned active=s_puzzle_active,batches=fake_batch_calls;
 std::memcpy(source_copy,source_pool,sizeof(source_pool));std::memcpy(gen_copy,gens,sizeof(gens));std::memcpy(clock_copy,clocks,sizeof(clocks));
 stage1_prepare_image();
 assert(!std::memcmp(&ticket,&s_stage1_pending,sizeof(ticket))&&!std::memcmp(&addition,&s_fx_addition,sizeof(addition)));
 assert(active==s_puzzle_active&&batches==fake_batch_calls);
 assert(!std::memcmp(source_copy,source_pool,sizeof(source_pool))&&!std::memcmp(gen_copy,gens,sizeof(gens))&&!std::memcmp(clock_copy,clocks,sizeof(clocks)));
}
static void refused_prepare(){unchanged_prepare();assert(!load_calls&&!uploads);++cases;}
static void query_refused(){
 Re4dcUiImage image={(void*)7,(void*)8,1,2,3,4,5};const auto ticket=s_stage1_pending, copy=ticket;
 assert(!re4dc_ps2_fx_stage1_image(&image));assert(!image.pixels&&!image.palette&&!image.width&&!image.height&&!image.format&&!image.palette_format&&!image.palette_bytes);
 assert(!std::memcmp(&copy,&s_stage1_pending,sizeof(copy)));refused_prepare();
}
int main(){
 // Each approved room uses its live owner record and exact original I8 shape.
 for(unsigned room:{0x117U,0x118U,0x11cU}){
  start(room);Re4dcUiImage image{};const auto ticket=s_stage1_pending;
  assert(re4dc_ps2_fx_stage1_image(&image)==(room==0x117?0x13U:0x1fU));
  assert(image.pixels==archive_bytes+128&&image.width==(room==0x117?96U:128U)&&image.height==image.width&&image.format==1);
  assert(!std::memcmp(&ticket,&s_stage1_pending,sizeof(ticket)));
  unchanged_prepare();assert(load_calls==1&&uploads==1&&preload_loads==1&&entries[0].key==expected(room)&&entries[0].frame==frame);
  ++frame;unchanged_prepare();assert(load_calls==2&&uploads==1&&hit_calls==1&&entries[0].frame==frame);
  // Actual cache eviction between frames: no secondary sticky residency bit.
  entries[0]={};++frame;unchanged_prepare();assert(load_calls==3&&uploads==2&&preload_loads==2&&entries[0].frame==frame);++cases;
 }
 start();assert(!re4dc_ps2_fx_stage1_image(nullptr));++cases;
 start();s_stage1_pending.pending=false;query_refused();
 start();pG=nullptr;query_refused();pG=&globals;
 start();g_pEspSys=nullptr;query_refused();g_pEspSys=&sys;
 start();++globals.Frame_cnt;query_refused();start();--globals.Frame_cnt;query_refused();
 start();++G_ROOM_ID;query_refused();start();sys.pEspBuf=source_pool+0x150;query_refused();
 start();++sys.nEsp;query_refused();start();--sys.nEsp;query_refused();
 start();EspgenArray=gens+1;query_refused();start();--nEspgen;query_refused();
 start();++fake_generation;query_refused();start();fake_resident=false;query_refused();
 for(unsigned room:{0x117U,0x118U,0x11cU}){start(room);re4dc_ps2fx=room==0x117?PS2FX_HAZE:PS2FX_STREAK;query_refused();}
 start(0x103);assert(!s_stage1_pending.pending);refused_prepare();
 // Every source descriptor gate refuses before the cache boundary.
 for(unsigned room:{0x117U,0x118U}){
  const unsigned id=room==0x117?0x13:0x1f;
  start(room);sys.Esp_tex_tbl[id].Owner=0xd2;query_refused();
  start(room);sys.Esp_tex_tbl[id].pTpl=nullptr;query_refused();
  start(room);tpl.numDescriptors=2;query_refused();
  start(room);sys.Esp_tex_tbl[id].pAnm=nullptr;query_refused();
  start(room);sys.Esp_tex_tbl[id].pAnm->Cx=1;query_refused();
  start(room);sys.Esp_tex_tbl[id].pAnm->Cy=1;query_refused();
  start(room);sys.Esp_tex_tbl[id].pAnm->Width=64;query_refused();
  start(room);sys.Esp_tex_tbl[id].pAnm->Height=64;query_refused();
  start(room);sys.Esp_tex_tbl[id].pAnm->Frames=2;query_refused();
  start(room);fake_descriptor=false;query_refused();
  start(room);td.textureHeader=nullptr;query_refused();
  CLUT clut{};start(room);td.CLUTHeader=&clut;query_refused();
  start(room);tex.data=nullptr;query_refused();
  start(room);tex.width=64;query_refused();start(room);tex.height=64;query_refused();
  start(room);tex.format=5;query_refused();
 }
 // Actual SourceIdentityTable: matching foreign bytes, unknown ordinary pixels,
 // interior NTR pointers, stale metadata and unknown original keys never load.
 start();tex.data=foreign_archive+128;refused_prepare();
 start();tex.data=archive_bytes+64;refused_prepare();
 start();tex.data=archive_bytes+129;refused_prepare();
 start();put32(144,64);refused_prepare();
 start();put32(148,64);refused_prepare();
 start();put32(152,5);refused_prepare();
 start();put32(136,0xdeadbeef);refused_prepare();
 start();put32(140,0xdeadbeef);refused_prepare();
 start();core_identities.clear();refused_prepare();
 start();assert(core_identities.adopt(foreign_archive,sizeof(foreign_archive)));refused_prepare();
 start();archive_bytes[480]^=1;assert(!core_identities.adopt(archive_bytes,sizeof(archive_bytes)));refused_prepare();
 // Native phase and existing VRAM claims deny both cold and resident requests.
 start();frame_ready=false;refused_prepare();start();vram_claims=1;refused_prepare();
 start();source_draws_finished=true;refused_prepare();start();stream_scene=true;refused_prepare();
 start();stream_aborted=true;refused_prepare();start();stream_retire=true;refused_prepare();
 start();missing_keys[1]=expected(0x117);refused_prepare();
 // Reserves are strict, include leased entries, and account for real pool space.
 start();for(unsigned i=0;i<6;++i)entries[i]={true,false,{i+1,1},frame,{512}};refused_prepare();
 start();for(unsigned i=0;i<6;++i)entries[i]={true,true,{i+1,1},frame-1,{512}};refused_prepare();
 start();vram_budget=8192;refused_prepare();
 start();entries[0]={true,false,{1,1},frame,{57345}};refused_prepare();
 start();entries[0]={true,false,{1,1},frame,{51201}};refused_prepare();
 start();pool_free=8192+6144-1;refused_prepare();
 start();pool_free=8192+6144;unchanged_prepare();assert(uploads==1);++cases;
 start();entries[0]={true,false,{1,1},frame,{51200}};unchanged_prepare();assert(uploads==1);++cases;
 start();pool_free=8192;entries[1]={true,false,{1,1},frame-1,{6144}};unchanged_prepare();
#if RE4DC_TEX_KEEP
 assert(uploads==1);
#else
 assert(!uploads);used=kVramBudget-8192;pool_free=kVramBudget;refused_prepare();
#endif
 ++cases;
 // A current resident hit pins through the normal loader even when cold-load
 // reserves are full. Load failure can retry on a later drawn frame.
 start();entries[0]={true,false,expected(0x117),frame-1,{6144}};pool_free=0;vram_budget=8192;
 unchanged_prepare();assert(load_calls==1&&hit_calls==1&&!uploads&&entries[0].frame==frame);++cases;
 start();load_failure=true;unchanged_prepare();assert(load_calls==1&&!uploads&&preload_skipped==1);
 load_failure=false;++frame;unchanged_prepare();assert(load_calls==2&&uploads==1&&preload_loads==1);++cases;
 // Existing source phase functions prove ordering and unchanged ticket use.
 for(unsigned room:{0x117U,0x118U,0x11cU}){
  start(room);Render_before();const unsigned calls=load_calls;assert(calls==1&&phase_begin<prepare_order);
  Render();assert(load_calls==calls&&prepare_order<phase_coarse&&phase_coarse<phase_batch&&!s_stage1_pending.pending);++cases;
 }
 start();re4dc_pace_skipping=1;Render_before();Render();assert(!load_calls&&!uploads&&!s_stage1_pending.pending);++cases;
 std::printf("PASS actual stage1 prepare: %u cases KEEP=%u; live source/core ownership, unchanged tickets/pool/generators/private clocks, pre-draw ordering, skip/refusal, real frame pins and bounded eviction recovery at stubbed load boundary\n",cases,RE4DC_TEX_KEEP);
}
