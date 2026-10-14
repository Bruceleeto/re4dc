// Compiles the actual candidate readers. Source owners and GPU/cache services
// are synthetic; this test makes no residency or rendered-pixel claim.
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <new>
#include <cstring>
#include <array>
#include <algorithm>
#include <sys/mman.h>
#include "re4dc_platform.h"
#define RE4DC_PS2_WORLD_SOURCE_OWNER 1
#define RE4DC_PS2_WORLD_SOURCE_TEX_PREP 1
#define RE4DC_PRIMITIVE_BUFFERS 2
using u32=std::uint32_t;using u8=unsigned char;
template<class T> struct cManager;
struct Vec { float x=0,y=0,z=0; };
struct ModelDataHead { unsigned char partsNo=0,parentNo=255,x2=0,x3=0;Vec center{}; };
struct ModelData { unsigned nParts=1,shapeOfs=0;ModelDataHead* pHead=nullptr; };
struct cModelInfo { unsigned be_flag=9;float invisible_factor=1;unsigned char color[4]{255,255,255,255};cModelInfo* pList=nullptr;ModelData* pData=nullptr; };
class cModel;
struct cParts { unsigned be_flag=1;cParts* pList=nullptr;cModel* pParent=nullptr;Vec pos{},ang{},scale{1,1,1}; };
class cModel { public:unsigned serial=1,kindid=2,be_flag=3,nParts=1;float invisible_factor=1,invisible_factor2=1;Vec pos{},ang{},scale{1,1,1};cModelInfo* pModelInfo=nullptr;cParts* pList=nullptr;static cManager<cModelInfo>* mm;static cManager<cParts>* pm; };
class cObj:public cModel { public:int blk=-1; };
class cEm:public cModel {};
struct SmdWork { Vec pos{},rot{},scale{1,1,1};unsigned char binNo=0,tplNo=0,motNo=255,id=0;unsigned char pad[28]{};unsigned flags=0; };
static_assert(sizeof(SmdWork)==72);
struct cSmd { unsigned char Version=64,Flag=0;unsigned short nModel=90;unsigned BinTblOfs=0,TplTblOfs=0,MotTblOfs=0;SmdWork work[90]; };
struct Global { unsigned Rno0=3,stage_no=2,room_no=0,System_flg=0x400,Status_flg[4]{},Frame_cnt=300;unsigned long prim_cnt=0;unsigned nPrim=65536,vtx_buf_no=0; } global,*pG=&global;
#define G_ROOM_ID ((pG->stage_no<<8)|pG->room_no)
cSmd* pSmd=nullptr;cObj** scrTbl=nullptr;int nScrWork=90;
unsigned room_generation=10,frame=200,re4dc_alive_gen[4]{1,2,3,4};bool room_live=true,movie=false,subscreen=false;
int re4dc_coarse_image=0,re4dc_pace_skipping=0;unsigned log_count,aborts,camera_calls,draw_calls;
extern "C" void re4dc_log(const char*,...){++log_count;}
extern "C" int re4dc_room4_state(unsigned* g,unsigned* c,unsigned* b,unsigned* s,unsigned* r){*g=room_generation;*c=*b=*s=*r=0;return room_live;}
extern "C" int re4dc_ui_movie_texture(){return movie;}
extern "C" int re4dc_ss_ui_order(){return subscreen;}
extern "C" unsigned re4dc_ui_frame(){return frame;}
extern "C" void re4dc_model_packet_abort(){++aborts;}
// Synthetic allocator services, exercised by the actual allocator/pool readers.
struct OSHeapCell { OSHeapCell* prev=nullptr;OSHeapCell* next=nullptr;int size=0;char padding[12]{}; };
static_assert(sizeof(OSHeapCell)==32);
struct OSHeapDescriptor {int size=0;OSHeapCell* free=nullptr;OSHeapCell* allocated=nullptr;};
struct MemHeap {int handle=-1;unsigned long start=0,end=0;unsigned status=0;};
constexpr int MEM_HEAP_NUM=13;
MemHeap Heap[MEM_HEAP_NUM];Re4dcMemLayout re4dc_mem{};
alignas(32) unsigned char heap_memory[512000];unsigned heap_cursor;
OSHeapDescriptor* heap_descriptors;
void* host_alloc(unsigned bytes) {
 bytes=(bytes+31)&~31U;assert(heap_cursor+32+bytes<sizeof(heap_memory));
 auto* c=new(heap_memory+heap_cursor)OSHeapCell{};c->size=32+bytes;c->next=heap_descriptors[4].allocated;
 if(c->next)c->next->prev=c;heap_descriptors[4].allocated=c;heap_cursor+=32+bytes;return c+1;
}
template<class T> struct cManager {T* pArray=nullptr;unsigned nArray=0,size=sizeof(T),pArrayPush=0;bool suspended=false;};
template<class T> constexpr bool demand=true;
template<class T> struct Frozen {unsigned n=0;T** slots=nullptr;};
template<class T> Frozen<T>* frozen(cManager<T>* m){static Frozen<T> f;return m->suspended?&f:nullptr;}
#include "source_world_actual_pools.inc"
cManager<cObj> ObjMgr;cManager<cEm> EmMgr;cManager<cModelInfo> ModInfoMgr;cManager<cParts> PartsMgr;
cManager<cModelInfo>* cModel::mm=&ModInfoMgr;cManager<cParts>* cModel::pm=&PartsMgr;
#include "source_world_pools.inc"
template<class T> T* make_pool(cManager<T>& manager,unsigned count) {
 auto* p=new(host_alloc(sizeof(Pool<T>)+count*sizeof(T*)))Pool<T>{};
 auto* c=new(host_alloc(sizeof(Chunk<T>)+count*sizeof(T)))Chunk<T>{};
 p->capacity=count;p->heap=p->handle=4;p->chunks=c;c->count=count;c->bytes=sizeof(Chunk<T>)+count*sizeof(T);
 manager={reinterpret_cast<T*>(p),count,sizeof(T),0,false};
 for(unsigned i=0;i<count;++i){new(c->parts()+i)T{};p->slots()[i]=c->parts()+i;}return c->parts();
}
std::array<cObj,90>* objects_storage;std::array<cModelInfo,90>* infos_storage;std::array<cParts,90>* parts_storage;
alignas(32) unsigned char archive[30000]{};bool archive_live=true;
extern "C" int re4dc_model_owned_source(const void* p,unsigned bytes){const auto a=reinterpret_cast<std::uintptr_t>(p),b=reinterpret_cast<std::uintptr_t>(archive);return archive_live&&a>=b&&a-b<=sizeof(archive)&&bytes<=sizeof(archive)-(a-b);}
#include "ps2_source_world.h"
#include "source_world_scroll.inc"
struct PartMeta { unsigned crc=0,fnv=0,width=0,height=0,pass=0,cull=0,texture=0,reserved=0; };
struct MeshHeader {unsigned version=3,bytes=510048,crc=3459209119U,mesh_count=63,part_count=152;};
struct WorldPackage {MeshHeader h{};const MeshHeader& header()const{return h;}};
struct Counts {unsigned native=1,fallback=0,aborts=0;};
PartMeta world_parts[152];unsigned sourceWorldPackageGeneration=2,sourceWorldSidecarCrc=4040448078U;
struct Ps2World {void* storage=archive;PartMeta* parts=world_parts;void* placements=archive;void* lut=archive;void* gather=archive;unsigned room=0x200,want=0x200,nplacements=90;WorldPackage package{};Counts count[3]{};}ps2w;
namespace dyn { const unsigned char* ids=archive;unsigned nids=90; }
extern "C" int re4dc_coarse_source_camera(float*,float*,float*){++camera_calls;return 1;}
extern "C" void re4dc_ps2_mesh_camera(const float*,const float*,const float*){}
extern "C" int re4dc_ps2_world_source_draw(){++draw_calls;return 1;}
#include "native_source_world.inc"
void ModelRender(cModel*){}
struct OtData {void* data=nullptr;void(*func)(void*)=nullptr;OtData* next=nullptr;unsigned short kind=0;};
struct OtPrim {OtData ot;void* data=nullptr;};
struct Ot {OtData* list=nullptr;unsigned max=0;};
// Real enum values are extracted from include/trans_ot.h by the host runner.
#include "source_world_actual_ot.inc"
Ot g_OtWork[OT_MAX]{};OtData* nodes=nullptr;
struct Gx {unsigned char* prim=nullptr;} gx;
#define GXWORK() (&gx)
#include "source_world_frame.inc"
struct Key {unsigned crc=0,fnv=0;bool operator==(const Key& b)const{return crc==b.crc&&fnv==b.fnv;}};
struct Tex {unsigned width=256,height=256;};struct TexHeader {unsigned texture_count=1;};
struct TexturePackage {bool uploaded=true;unsigned bytes=131072;void* vram=archive;Tex t{};TexHeader h{};bool upload_complete()const{return uploaded;}unsigned vram_bytes()const{return bytes;}void* pvr_texture(unsigned)const{return vram;}const TexHeader& header()const{return h;}const Tex* textures()const{return &t;}};
struct Entry {bool valid=true;Key key{};unsigned frame=0;TexturePackage package{};}cache_entry;
bool frame_ready=true,stream_scene=false,stream_retire=false,stream_aborted=false,direct_open=false;unsigned vram_claims=0,loads=0,load_case=0,texfails=0;bool loaded_pin=false;
#include "native_ui.h"
Entry* load(const Re4dcUiImage& image,bool pin,const Key* key){++loads;loaded_pin=pin;assert(image.format==5&&image.width==256&&image.height==256);cache_entry.key=*key;cache_entry.frame=frame;
 if(load_case==1)return nullptr;if(load_case==2)++sourceWorldPackageGeneration;if(load_case==3)++room_generation;if(load_case==4)++global.Frame_cnt;return &cache_entry;}
#define RE4DC_TEXCHK_FAIL(key,why) (++texfails)
#include "native_ui_source_world.inc"
#define objects (*objects_storage)
#define infos (*infos_storage)
#define source_parts (*parts_storage)
unsigned checks=0;void check_at(bool ok,unsigned line){++checks;if(!ok){std::fprintf(stderr,"check %u at line %u failed\n",checks,line);std::abort();}}
#define check(v) check_at((v),__LINE__)
struct GuardPage {
 void* p=mmap(nullptr,4096,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
 GuardPage(){assert(p!=MAP_FAILED);}~GuardPage(){munmap(p,4096);}
};
void NonModelCallback(void*){}
void reset(unsigned n=3){
 global=Global{};pG=&global;room_generation=10;frame=200;room_live=archive_live=true;movie=subscreen=false;re4dc_coarse_image=re4dc_pace_skipping=0;
 for(auto& h:Heap)h=MemHeap{};std::memset(heap_memory,0,sizeof(heap_memory));heap_descriptors=reinterpret_cast<OSHeapDescriptor*>(heap_memory);
 heap_cursor=(sizeof(OSHeapDescriptor)*MEM_HEAP_NUM+31)&~31U;
 re4dc_mem.heap=reinterpret_cast<unsigned long>(heap_memory);re4dc_mem.heap_end=re4dc_mem.heap+sizeof(heap_memory);
 Heap[4]={4,re4dc_mem.heap+heap_cursor,re4dc_mem.heap_end,0};heap_descriptors[4].size=sizeof(heap_memory)-heap_cursor;
 objects_storage=reinterpret_cast<std::array<cObj,90>*>(make_pool(ObjMgr,90));
 infos_storage=reinterpret_cast<std::array<cModelInfo,90>*>(make_pool(ModInfoMgr,90));
 parts_storage=reinterpret_cast<std::array<cParts,90>*>(make_pool(PartsMgr,90));make_pool(EmMgr,4);
 cModel::mm=&ModInfoMgr;cModel::pm=&PartsMgr;
 scrTbl=static_cast<cObj**>(host_alloc(90*sizeof(cObj*)));std::fill_n(scrTbl,90,nullptr);
 global.prim_cnt=reinterpret_cast<unsigned long>(host_alloc(global.nPrim*RE4DC_PRIMITIVE_BUFFERS));gx.prim=reinterpret_cast<unsigned char*>(global.prim_cnt);sourceWorldPrimGeneration=1;
 re4dc_alive_gen[0]=1;re4dc_alive_gen[2]=3;sourceWorldPackageGeneration=2;sourceWorldSidecarCrc=4040448078U;ps2w=Ps2World{};dyn::ids=archive;dyn::nids=90;
 sourceWorldImageFrame=~0U;sourceWorldImageGeneration=0;sourceWorldImageResult=0;sourceWorldFrame=SourceWorldFrame{};sourceWorldRenderActive=false;
 aborts=camera_calls=draw_calls=loads=load_case=texfails=0;loaded_pin=false;frame_ready=true;stream_scene=stream_retire=stream_aborted=direct_open=false;vram_claims=0;
 sourceWorldPreparedFrame=sourceWorldAcquired=0;cache_entry=Entry{};
 std::memset(archive,0,sizeof(archive));pSmd=new(archive)cSmd{};pSmd->BinTblOfs=(sizeof(cSmd)+31)&~31U;
 auto* offsets=reinterpret_cast<unsigned*>(archive+pSmd->BinTblOfs);unsigned off=(pSmd->BinTblOfs+90*4+31)&~31U;
 nScrWork=90;sourceWorldScrollClear();
 for(unsigned i=0;i<90;++i){
  auto& w=pSmd->work[i];w.binNo=i;w.id=i;offsets[i]=off-pSmd->BinTblOfs;
  auto* d=new(archive+off)ModelData{};off+=32;d->pHead=new(archive+off)ModelDataHead{};off+=32;
  objects[i]=cObj{};infos[i]=cModelInfo{};source_parts[i]=cParts{};
  objects[i].serial=100+i;objects[i].pModelInfo=&infos[i];objects[i].pList=&source_parts[i];infos[i].pData=d;source_parts[i].pParent=&objects[i];scrTbl[i]=&objects[i];sourceWorldScrollBind(i,&objects[i]);
 }
 for(auto& ot:g_OtWork)ot={};nodes=static_cast<OtData*>(host_alloc(100*sizeof(OtData)));for(unsigned i=0;i<100;++i)new(nodes+i)OtData{};
 for(unsigned i=0;i<n;++i){nodes[i]={&objects[i%90],reinterpret_cast<void(*)(void*)>(ModelRender),i?&nodes[i-1]:nullptr};}
 if(n)g_OtWork[0x0b]={nodes,n};world_parts[13]={0xfa6fe38cU,0x1a02365fU,256,256,2,0,17,0};
}
int main(){
 reset();unsigned work=999,gen=0;check(re4dc_scroll_source_member(&objects[0],100,&work)&&work==0);
 for(unsigned i=0;i<90;++i){check(re4dc_scroll_source_member(&objects[i],100+i,&work)&&work==i);}
 reset();sourceWorldTexturePrepare();check(loads==1&&loaded_pin&&sourceWorldPreparedFrame==frame);check(re4dc_source_world_current(frame,2));
 check(!sourceWorldCandidate(&objects[0]));{SourceWorldRenderScope scope;check(sourceWorldCandidate(&objects[0]));check(sourceWorldDraw(&objects[2])==1);check(sourceWorldDraw(&objects[1])==1);}check(draw_calls==1&&camera_calls==1&&!sourceWorldRenderActive);
 sourceWorldTextureAcquired(cache_entry.key);check(sourceWorldAcquired==1);check(re4dc_ps2_source_passes_complete());ps2w.count[2].fallback=1;re4dc_source_world_flush_result(frame,re4dc_ps2_source_passes_complete());check(aborts==1&&!sourceWorldFrame.active);
 // The actual event-transition mask still executes Render's source OTs.
 reset();global.System_flg=0x0c40;sourceWorldTexturePrepare();
 check(loads==1&&sourceWorldFrame.ready);{SourceWorldRenderScope scope;
 check(sourceWorldDraw(&objects[2])==1);check(sourceWorldDraw(&objects[1])==1);}
 check(draw_calls==1&&aborts==0&&global.System_flg==0x0c40);
 // The event bit alone never bypasses movie, source-OT or render exclusions.
 for(unsigned mutation=0;mutation<8;++mutation){reset();global.System_flg=0x0c40;
 switch(mutation){case 0:movie=true;break;case 1:subscreen=true;break;
 case 2:global.System_flg&=~0x400;break;case 3:re4dc_coarse_image=1;break;
 case 4:re4dc_pace_skipping=1;break;case 5:global.System_flg|=0x100000;break;
 case 6:global.Status_flg[1]=0x100;break;case 7:global.Status_flg[2]=0x04000000;break;}
 sourceWorldTexturePrepare();check(loads==0&&!sourceWorldFrame.ready);}
 // Each real ModelTrans target is accepted, descriptive aliases are not.
 for(unsigned table:{0x0bU,0x0dU,0x11U}){reset();g_OtWork[0x0b]={};g_OtWork[table]={nodes,3};
 sourceWorldTexturePrepare();check(sourceWorldFrame.count==3&&sourceWorldFrame.ready);
 {SourceWorldRenderScope scope;check(sourceWorldDraw(&objects[2])==1);}check(draw_calls==1&&aborts==0);}
 for(unsigned table:{unsigned(OT_TYPE_SCROLL),unsigned(OT_TYPE_MODEL)}){reset();g_OtWork[0x0b]={};g_OtWork[table]={nodes,3};
 sourceWorldTexturePrepare();check(!sourceWorldFrame.active&&loads==0);}
 // A member published twice across real tables is not silently drawn twice.
 reset();g_OtWork[0x0d]={nodes,3};sourceWorldTexturePrepare();check(!sourceWorldFrame.active&&loads==0);
 // Publication serial, current source owner and room generation fail before a stale info dereference.
 reset();objects[0].serial++;objects[0].pModelInfo=reinterpret_cast<cModelInfo*>(mmap(nullptr,4096,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0));check(!re4dc_scroll_source_member(&objects[0],101,&work));munmap(objects[0].pModelInfo,4096);
 reset();archive_live=false;check(!re4dc_scroll_source_member(&objects[0],100,&work));reset();room_generation++;check(!re4dc_scroll_source_member(&objects[0],100,&work));
 reset();scrTbl[1]=scrTbl[0];check(!re4dc_scroll_source_member(&objects[0],100,&work));reset();sourceWorldScrollClear();check(!re4dc_scroll_source_member(&objects[0],100,&work));
 // Protected pages are passed into the production reader. None is readable,
 // including the complete cModel payload (the old test protected only info).
 {GuardPage guard;
  for(unsigned mutation=0;mutation<11;++mutation){reset();switch(mutation){
   case 0:g_OtWork[0x0b].list=static_cast<OtData*>(guard.p);break;
   case 1:nodes[1].next=static_cast<OtData*>(guard.p);break;
   case 2:nodes[1].data=guard.p;break;
   case 3:nodes[1].data=guard.p;scrTbl[1]=static_cast<cObj*>(guard.p);break;
   case 4:objects[1].pModelInfo=static_cast<cModelInfo*>(guard.p);break;
   case 5:objects[1].pList=static_cast<cParts*>(guard.p);break;
   case 6:scrTbl=static_cast<cObj**>(guard.p);break;
   case 7:ObjMgr.pArray=static_cast<cObj*>(guard.p);break;
   case 8:ModInfoMgr.pArray=static_cast<cModelInfo*>(guard.p);break;
   case 9:PartsMgr.pArray=static_cast<cParts*>(guard.p);break;
   case 10:pool(&ObjMgr)->chunks=static_cast<Chunk<cObj>*>(guard.p);break;}
   check(!re4dc_source_world_prepare(frame,&gen));check(draw_calls==0&&aborts==0);
  }
  reset();nodes[1].data=guard.p;nodes[1].func=NonModelCallback;
  check(re4dc_source_world_prepare(frame,&gen)&&sourceWorldFrame.count==2);
  reset();auto* enemy=work_at(&EmMgr,0);enemy->kindid=0;nodes[1].data=enemy;
  check(re4dc_source_world_prepare(frame,&gen)&&sourceWorldFrame.count==2);
  reset();sourceWorldTexturePrepare();objects[1].pModelInfo=static_cast<cModelInfo*>(guard.p);
  {SourceWorldRenderScope scope;check(sourceWorldDraw(&objects[2])==0);}check(draw_calls==0&&aborts==0);
  reset();sourceWorldTexturePrepare();{SourceWorldRenderScope scope;check(sourceWorldDraw(&objects[2])==1);
   objects[1].pModelInfo=static_cast<cModelInfo*>(guard.p);check(sourceWorldDraw(&objects[1])==-1);
   check(!sourceWorldCandidate(static_cast<cModel*>(guard.p)));}check(aborts==1);
 }
 // Exact current slot publication is required, including reused addresses,
 // withdrawn chunks, frozen managers, offsets within a valid allocated cell.
 for(unsigned mutation=0;mutation<12;++mutation){reset();switch(mutation){
  case 0:pool(&ObjMgr)->slots()[1]=nullptr;break;
  case 1:pool(&ModInfoMgr)->slots()[1]=nullptr;break;
  case 2:pool(&PartsMgr)->slots()[1]=nullptr;break;
  case 3:ObjMgr.suspended=true;break;
  case 4:ObjMgr.pArrayPush=1;break;
  case 5:pool(&ObjMgr)->handle++;break;
  case 6:pool(&ObjMgr)->capacity--;break;
  case 7:nodes[1].data=reinterpret_cast<unsigned char*>(&objects[1])+4;break;
  case 8:objects[1].pModelInfo=reinterpret_cast<cModelInfo*>(reinterpret_cast<unsigned char*>(&infos[1])+4);break;
  case 9:objects[1].pList=reinterpret_cast<cParts*>(reinterpret_cast<unsigned char*>(&source_parts[1])+4);break;
  case 10:objects[1].serial++;break;
  case 11:Heap[4].status=1;break;}
  check(!re4dc_source_world_prepare(frame,&gen));check(draw_calls==0&&aborts==0);
 }
 // A real OtPrim must be fully below the captured allocation cursor. Allocated
 // but unused capacity, the previous buffer and misaligned addresses all fail.
 for(unsigned mutation=0;mutation<6;++mutation){reset();
  auto* primitive=new(reinterpret_cast<void*>(global.prim_cnt))OtPrim{};
  primitive->ot={&objects[3],reinterpret_cast<void(*)(void*)>(ModelRender),nodes,2};
  nodes[1].next=&primitive->ot;gx.prim+=64;
  switch(mutation){case 0:break;case 1:gx.prim-=64;break;
   case 2:nodes[1].next=reinterpret_cast<OtData*>(global.prim_cnt+32);break;
   case 3:nodes[1].next=reinterpret_cast<OtData*>(global.prim_cnt+global.nPrim);break;
   case 4:nodes[1].next=reinterpret_cast<OtData*>(global.prim_cnt+1);break;
   case 5:nodes[1].next=&nodes[1];break;}
  check(bool(re4dc_source_world_prepare(frame,&gen))==(mutation==0));
 }
 for(unsigned mutation=0;mutation<22;++mutation){reset();auto& m=objects[0];auto& info=infos[0];auto& p=source_parts[0];auto& w=pSmd->work[0];auto* d=info.pData;
  switch(mutation){case 0:m.blk=0;break;case 1:m.kindid=1;break;case 2:m.be_flag=0;break;case 3:m.invisible_factor=.5f;break;case 4:m.ang.x=.1f;break;case 5:m.pos.y=1;break;case 6:m.scale.z=2;break;case 7:w.flags=16;break;case 8:w.motNo=0;break;case 9:info.pList=&infos[1];break;case 10:info.pData=infos[1].pData;break;case 11:info.be_flag=11;break;case 12:info.invisible_factor=.5f;break;case 13:info.color[3]=128;break;case 14:d->nParts=2;break;case 15:d->shapeOfs=4;break;case 16:p.pParent=&objects[1];break;case 17:p.ang.x=.87266463f;break;case 18:p.pos.x=1;break;case 19:p.scale.y=2;break;case 20:p.pList=&source_parts[1];break;case 21:p.be_flag=0;break;}
  check(!re4dc_scroll_source_member(&m,100,&work));check(bool(re4dc_source_world_prepare(frame,&gen))==(mutation==1));
 }
 // Being inside the current allocation does not make a chunk header aligned.
 for(unsigned type=0;type<3;++type){reset();
  if(type==0)pool(&ObjMgr)->chunks=reinterpret_cast<Chunk<cObj>*>(reinterpret_cast<unsigned char*>(pool(&ObjMgr)->chunks)+1);
  else if(type==1)pool(&ModInfoMgr)->chunks=reinterpret_cast<Chunk<cModelInfo>*>(reinterpret_cast<unsigned char*>(pool(&ModInfoMgr)->chunks)+1);
  else pool(&PartsMgr)->chunks=reinterpret_cast<Chunk<cParts>*>(reinterpret_cast<unsigned char*>(pool(&PartsMgr)->chunks)+1);
  check(!re4dc_source_world_prepare(frame,&gen));check(!draw_calls&&!aborts);
 }
 // Context exclusions and exact source/package/primitive epochs.
 for(unsigned mutation=0;mutation<10;++mutation){reset();switch(mutation){case 0:movie=true;break;case 1:subscreen=true;break;case 2:global.System_flg=0;break;case 3:global.room_no=1;break;case 4:global.Rno0=2;break;case 5:re4dc_pace_skipping=1;break;case 6:re4dc_coarse_image=1;break;case 7:global.System_flg|=0x100000;break;case 8:global.Status_flg[2]=0x04000000;break;case 9:global.Status_flg[1]=0x100;break;}check(!re4dc_source_world_prepare(frame,&gen));check(loads==0);}
 for(unsigned mutation=0;mutation<9;++mutation){reset();sourceWorldTexturePrepare();switch(mutation){case 0:++room_generation;break;case 1:++sourceWorldPackageGeneration;break;case 2:++re4dc_alive_gen[2];break;case 3:++re4dc_alive_gen[0];break;case 4:++global.Frame_cnt;break;case 5:++global.prim_cnt;break;case 6:++global.nPrim;break;case 7:++global.vtx_buf_no;break;case 8:++sourceWorldPrimGeneration;break;}check(!re4dc_source_world_current(frame,2));}
 reset();nodes[0].data=nodes[1].data;check(!re4dc_source_world_prepare(frame,&gen));reset(91);check(!re4dc_source_world_prepare(frame,&gen));reset(0);check(!re4dc_source_world_prepare(frame,&gen));
 reset();sourceWorldTexturePrepare();nodes[0].data=&objects[4];{SourceWorldRenderScope scope;check(sourceWorldDraw(&objects[2])==0);}check(draw_calls==0);
 reset();sourceWorldTexturePrepare();source_parts[0].ang.x=.8f;{SourceWorldRenderScope scope;check(sourceWorldDraw(&objects[2])==0);}check(draw_calls==0);
 reset();sourceWorldTexturePrepare();ps2w.count[0].fallback=1;{SourceWorldRenderScope scope;check(sourceWorldDraw(&objects[2])==-1);}check(aborts==1&&draw_calls==1);
 // No mixed GC fallback after a native header: changed epochs/poses abort the scene once.
 for(unsigned mutation=0;mutation<9;++mutation){reset();sourceWorldTexturePrepare();{
  SourceWorldRenderScope scope;check(sourceWorldDraw(&objects[2])==1);
  switch(mutation){case 0:++room_generation;break;case 1:++sourceWorldPackageGeneration;break;case 2:++re4dc_alive_gen[2];break;case 3:++re4dc_alive_gen[0];break;case 4:++global.Frame_cnt;break;case 5:++global.prim_cnt;break;case 6:++global.nPrim;break;case 7:++global.vtx_buf_no;break;case 8:++sourceWorldPrimGeneration;break;}
  check(sourceWorldDraw(&objects[1])==-1);check(sourceWorldDraw(&objects[0])==-1);
 }check(aborts==1&&draw_calls==1&&sourceWorldFrame.failed);}
 reset();sourceWorldTexturePrepare();{SourceWorldRenderScope scope;check(sourceWorldDraw(&objects[2])==1);source_parts[0].ang.x=.8f;}check(aborts==1&&sourceWorldFrame.failed);
 reset();sourceWorldTexturePrepare();{SourceWorldRenderScope scope;check(sourceWorldDraw(&objects[2])==1);objects[0].invisible_factor=0;}check(aborts==1&&sourceWorldFrame.failed);
 for(unsigned mutation=0;mutation<11;++mutation){reset();switch(mutation){case 0:ps2w.storage=nullptr;break;case 1:sourceWorldPackageGeneration=~0U;break;case 2:sourceWorldSidecarCrc++;break;case 3:ps2w.package.h.crc++;break;case 4:ps2w.package.h.bytes++;break;case 5:ps2w.parts=nullptr;break;case 6:ps2w.nplacements++;break;case 7:dyn::ids=nullptr;break;case 8:dyn::nids--;break;case 9:ps2w.room++;break;case 10:ps2w.want++;break;}check(!re4dc_ps2_source_package(&gen));}
 for(unsigned mutation=0;mutation<7;++mutation){reset();auto& q=world_parts[13];switch(mutation){case 0:q.crc++;break;case 1:q.fnv++;break;case 2:q.width=128;break;case 3:q.pass=1;break;case 4:q.texture=18;break;case 5:q.height=128;break;case 6:q.reserved=1;break;}Re4dcSourceWorldTexture out{};check(!re4dc_ps2_source_texture(2,&out));sourceWorldTexturePrepare();check(loads==0&&!sourceWorldFrame.ready);}
 for(unsigned mutation=0;mutation<6;++mutation){reset();switch(mutation){case 0:frame_ready=false;break;case 1:stream_scene=true;break;case 2:stream_retire=true;break;case 3:stream_aborted=true;break;case 4:direct_open=true;break;case 5:vram_claims=1;break;}sourceWorldTexturePrepare();check(loads==0&&!sourceWorldFrame.active);}
 for(unsigned mutation=1;mutation<=4;++mutation){reset();load_case=mutation;sourceWorldTexturePrepare();check(loads==1&&!sourceWorldFrame.ready&&!sourceWorldPreparedFrame);}
 for(unsigned mutation=0;mutation<8;++mutation){reset();switch(mutation){case 0:cache_entry.valid=false;break;case 1:cache_entry.package.uploaded=false;break;case 2:cache_entry.package.bytes=10240;break;case 3:cache_entry.package.vram=nullptr;break;case 4:cache_entry.package.h.texture_count=2;break;case 5:cache_entry.package.t.width=128;break;case 6:cache_entry.package.t.height=128;break;case 7:cache_entry.package.bytes=65536;break;}sourceWorldTexturePrepare();check(loads==1&&!sourceWorldFrame.ready);}
 reset();const auto before=objects;const auto before_infos=infos;const auto before_parts=source_parts;const auto before_global=global;
 std::array<unsigned char,sizeof(archive)> before_archive;std::memcpy(before_archive.data(),archive,sizeof(archive));
 sourceWorldTexturePrepare();{SourceWorldRenderScope scope;check(sourceWorldDraw(&objects[2])==1);}
 for(unsigned i=0;i<90;++i){check(std::memcmp(&before[i],&objects[i],sizeof(cObj))==0);}
 check(std::memcmp(before_infos.data(),infos.data(),sizeof(infos))==0);
 check(std::memcmp(before_parts.data(),source_parts.data(),sizeof(source_parts))==0);
 check(std::memcmp(&before_global,&global,sizeof(global))==0);
 check(std::memcmp(before_archive.data(),archive,sizeof(archive))==0);
 check(aborts==0);
 std::printf("source world actual readers: %u checks PASS (synthetic source/cache/GPU services)\n",checks);
}
