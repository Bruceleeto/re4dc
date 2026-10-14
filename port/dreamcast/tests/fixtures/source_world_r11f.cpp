// D45 production readers/controllers/callbacks/pass loop with external services
// instrumented on the host. This is not a SH4, texture-cache or rendered-pixel test.
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <cstdarg>
#include <cstdlib>
#include <new>
#include <cstring>
#include <array>
#include <algorithm>
#include <vector>
#include <cmath>
#include <fstream>
#include <sys/mman.h>
#include "re4dc_platform.h"
#define RE4DC_PS2_WORLD_R11F_OWNER 1
#define RE4DC_PRIMITIVE_BUFFERS 2
using u32=std::uint32_t;using u8=unsigned char;using u16=unsigned short;using f32=float;
using Mtx=float[3][4];
template<class T> struct cManager;
struct Vec { float x=0,y=0,z=0; };
struct Camera {struct {Vec pos{};} param;Mtx v_mat{};};
struct Scissor {u32 x=0,y=0,width=640,height=448;bool operator==(const Scissor& b)const{return x==b.x&&y==b.y&&width==b.width&&height==b.height;}}scissor;
struct cLightInfo {Vec Size{1,1,1},Offset{};unsigned PartsNo=1,SelectMask=~0U;};
#include "source_world_actual_data.inc"
#include "tpl.h"
struct cModelInfo {
 unsigned be_flag=9;float invisible_factor=1;cModelInfo* pList=nullptr;ModelData* pData=nullptr;
 void* tpl_addr=nullptr;void* pShape=nullptr;TEXPalette* pAddTpl=nullptr;unsigned nAddTex=0;
 Mtx mat{};unsigned char color[4]{255,255,255,255},color2[4]{};unsigned char blend_mode=0;
 alignas(8) u16 flagsDC=0;u16 blendRatio=0;u8 anm_no=0,blendType=0,pad_E2[2]{};
 void* texBlendTbl=nullptr;float uvU=0,uvV=0,uvScrollU=0,uvScrollV=0;u8* pTexAnim=nullptr;
};
class cModel;
struct cParts { unsigned be_flag=1;cParts* pList=nullptr;cModel* pParent=nullptr;Vec pos{},ang{},scale{1,1,1};Mtx mat{},l_mat{},lt_inv_mat{};Vec addRot{};struct {unsigned flags=0;}motParts; };
class cModel { public:
 unsigned serial=1,kindid=2,be_flag=7,nParts=1,ot_type=3,z_mode=0;
 u8 id=0,type=0,CullMode=0,alpha_omit=255,TevScaleGroup=0,Shader_type=0,AddAmb_r=0,AddAmb_g=0,AddAmb_b=0;
 float invisible_factor=1,invisible_factor2=1;Vec pos{},ang{},scale{1,1,1},world{};Mtx mat{},l_mat{};
 cModel* pParent=nullptr;void* pMotion=nullptr;void* pTexChg=nullptr;cLightInfo LightInfo;
 void* pParts=nullptr;cModelInfo* pModelInfo=nullptr;cParts* pList=nullptr;
 static cManager<cModelInfo>* mm;static cManager<cParts>* pm;
 cModel* getPartsPtr(int){return this;}void drawAllBoundingBox(cModelInfo*){}
};
class cObj:public cModel { public:int blk=-1;u8 x3D0=0,work[0x78]{}; };
class cEm:public cModel {};
struct Global { unsigned Rno0=3,stage_no=1,room_no=0x1f,System_flg=0x400,Status_flg[4]{},Debug_flg[4]{},Stop_flg=0,Frame_cnt=300;unsigned long prim_cnt=0;unsigned nPrim=65536,vtx_buf_no=0;Camera Cam{}; } global,*pG=&global;
#define G_ROOM_ID ((pG->stage_no<<8)|pG->room_no)
cSmd* pSmd=nullptr;cSmx* pSmx=nullptr;cObj** scrTbl=nullptr;int nScrWork=251;
unsigned room_generation=10,frame=200,re4dc_alive_gen[4]{1,2,3,4};bool room_live=true,movie=false,subscreen=false;
int re4dc_coarse_image=0,re4dc_pace_skipping=0;unsigned aborts,camera_calls,draw_calls;
extern "C" void re4dc_log(const char* fmt,...){va_list args;va_start(args,fmt);std::vfprintf(stderr,fmt,args);va_end(args);}
extern "C" int re4dc_room4_state(unsigned* g,unsigned* c,unsigned* b,unsigned* s,unsigned* r){*g=room_generation;*c=*b=*s=*r=0;return room_live;}
extern "C" int re4dc_ui_movie_texture(){return movie;}
extern "C" int re4dc_ss_ui_order(){return subscreen;}
extern "C" unsigned re4dc_ui_frame(){return frame;}
bool frame_ready=true,stream_scene=false,stream_retire=false,stream_aborted=false,direct_open=false,source_draws_finished=false;
unsigned model_used=0,stream_model_bytes=0,stream_closed_lists=0,stream_discards=0,world_barrier_logs=0;
constexpr unsigned PVR_LIST_OP_POLY=0,PVR_LIST_TR_POLY=2,PVR_LIST_PT_POLY=4;
unsigned stream_list=PVR_LIST_OP_POLY;
extern "C" void re4dc_model_packet_abort(){assert(!direct_open);if(!stream_aborted)++aborts;stream_aborted=true;model_used=0;}
#include "source_world_allocator.inc"
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
 p->capacity=count;p->heap=4;p->handle=Heap[4].handle;p->chunks=c;c->count=count;c->bytes=sizeof(Chunk<T>)+count*sizeof(T);
 manager={reinterpret_cast<T*>(p),count,sizeof(T),0,false};
 for(unsigned i=0;i<count;++i){new(c->parts()+i)T{};p->slots()[i]=c->parts()+i;}return c->parts();
}
cObj* objects;cModelInfo* infos;cParts* source_parts;
alignas(32) unsigned char archive[3*1024*1024]{};bool archive_live=true;
std::vector<unsigned char> source_file,mesh_file,side_file,ids_file;
extern "C" int re4dc_model_owned_source(const void* p,unsigned bytes){const auto a=reinterpret_cast<std::uintptr_t>(p),b=reinterpret_cast<std::uintptr_t>(archive);return archive_live&&a>=b&&a-b<=sizeof(archive)&&bytes<=sizeof(archive)-(a-b);}
#include "ps2_source_world.h"
#include "source_world_r11f_scroll.inc"
#include "source_world_actual_callback.inc"
void ModelRender(cModel*);
#include "source_world_actual_ot.inc"
OtWork g_OtWork[OT_MAX]{};
struct Gx {unsigned char* prim=nullptr;} gx;
using GxWork=Gx;
#define GXWORK() (&::gx)
#include "source_world_r11f.inc"
#include "source_world_actual_uv.inc"
// Instrumented geometry/GX services around exact production registration bodies.
struct GeoSphere {Vec pos;float r;};struct GeoHexahedron{};
void* CameraViewFrustumPtr(Camera*){static GeoHexahedron h;return &h;}
bool collision_sphere_hexahedron(GeoSphere*,GeoHexahedron*){return true;}
void CameraGetLookVecInverse(Camera*,Vec* out){*out={0,0,1};}
float PSVECDotProduct(Vec* a,Vec* b){return a->x*b->x+a->y*b->y+a->z*b->z;}
void PSMTXMultVecSR(Mtx,Vec* a,Vec* out){*out=*a;}
void PSVECAdd(Vec* a,Vec* b,Vec* out){*out={a->x+b->x,a->y+b->y,a->z+b->z};}
bool isBit(unsigned a,unsigned b){return (a&b)!=0;}
#define SQRTF(x) std::sqrt(x)
#define ENCV_TRANS_NOTE(m,n) ((void)0)
#define OT_MARK(w,f) ((void)0)
#undef RE4_MEM_LO
#undef RE4_MEM_HI
#define RE4_MEM_LO 1U
#define RE4_MEM_HI 0xffffffffU
#define PTR_INVALID(p) (reinterpret_cast<std::uintptr_t>(p)<RE4_MEM_LO)
void U32Set(u32& value,u32 next){value=next;}
int g_NowExecOtType=OT_MAX;float OT_MUL=.05f;
unsigned screen_prepares,light_prepares,callback_postludes,source_geometry,shader_resets,draw_syncs,mixed_callbacks;
void (*after_model)(cModel*)=nullptr;
int commonScreenMat(cModel* m){++screen_prepares;actual_source_uv(m->pModelInfo);return 1;}
void lightSetEm(cModel*){++light_prepares;}void lightSetObj(cModel*){++light_prepares;}
void GXSetAlphaCompare(int,int,int,int,int){}void GXSetZMode(int,int,int){}void CameraCurrentProjection(){}
void GXSetNumChans(int){}void GXSetChanCtrl(int,int,int,int,int,int,int){}
struct GXColor {u8 r,g,b,a;};
void GXSetChanAmbColor(int,GXColor){}void GXSetChanMatColor(int,GXColor){}void LightSetModel(cModel*){}
void GXSetAlphaUpdate(int){}void GXSetDstAlpha(int,int){}void shaderReset(){++shader_resets;}
void* g_prev_tpl_addr=nullptr;void* g_prev_add_tpl_addr=nullptr;void GXSetCurrentGXThread(){}
struct {void setFog(){}} LightMgr;
void SetDrawTmpBufType(int){}void bio4_AddBgColor(){}void drawGround(int){}void ClearZbuf(){}
Camera itemCamera{};void GXSetFog(int,float,float,float,float,GXColor){}
#define FRef(x) 1.f
int Filter09GetbUse(){return 0;}void Filter09Render(int){}void GXSetDrawSync(int){++draw_syncs;}
void Render_DrawSyncCallback(u16){}void GXSetDrawSyncCallback(void(*)(u16)){}
struct {float x=0,y=0,width=640,height=448;}Screen;
void GXSetScissor(u32 x,u32 y,u32 w,u32 h){scissor={x,y,w,h};}
void ClearOt();void clearOtWork(OtWork*);void CrearOtMirrorWork(){}
#if RE4DC_ENCV
volatile unsigned g_encvLast;unsigned encv_picks=0,encv_notes=0;
extern "C" unsigned re4dc_encv_render_pick(cModel* model){assert(sourceWorldModelDepth==1);++encv_picks;return model->serial%10;}
extern "C" void re4dc_encv_render_done(){}
extern "C" unsigned re4dc_model_output_count(){return source_geometry;}
extern "C" unsigned re4dc_model_input_count(){return callback_postludes;}
extern "C" void re4dc_encv_render_note(cModel*,unsigned,unsigned){assert(sourceWorldModelDepth==1);++encv_notes;}
#endif
#include "source_world_actual_registration.inc"
#include "source_world_actual_smx.inc"
// The real native package reader and pass loop; graphics service records UVs.
#include "native_model.h"
#include "room/instanced_mesh.hpp"
#include "re4dc_screen.h"
#define RE4DC_MOVIE_WORLD_ARENA 1
#define RE4DC_PS2_WORLD_DYNAMIC 1
#define RE4DC_PS2_WORLD_PARTS 1
#define RE4DC_PS2_WORLD_MESH 1
#define RE4DC_PS2_WORLD_ROOMS 2
#define RE4DC_PS2_WORLD_DRAW 1
#define RE4DC_PT_BLEND_FIX 0
#define RE4DC_TA_DIRECT 1
#ifndef RE4DC_PS2_WORLD_HDR_CACHE
#define RE4DC_PS2_WORLD_HDR_CACHE 2
#endif
#define RE4DC_MESH_DIRECT 1
#define RE4DC_MESH_FASTPATH 1
#define RE4DC_MESH_LOD_PX 1
#define RE4DC_PS2_FAR 25000
#define RE4DC_D349_RENDERER_STACK 1
#define RE4DC_PVR_PIPELINE 1
#define RE4DC_PS2_WORLD_FOG_LATCH() ((void)0)
#define RE4DC_PROFILE_SCOPE(x) ((void)0)
namespace re4dc::render {
struct DrawBounds {float minimum[3],maximum[3];};
bool is_finite(float f){return std::isfinite(f);}
bool visible=true;
bool group_visible(const DrawBounds&,const float*,const float*,const float*,float,float,int){return visible;}
}
namespace re4dc::vp {void build_lut(std::uint32_t* p){std::fill_n(p,512,0);}}
struct Ps2Part {std::uint32_t crc,fnv;std::uint16_t width,height;std::uint8_t pass,cull,texture,reserved;};
struct Ps2Placement {std::uint16_t mesh,placement;float affine[12];};
struct Ps2Head {char magic[4];std::uint32_t version,placements,parts,meshes,crc,reserved[2];};
struct Ps2Counts {unsigned placements,culled,parts,native,fallback,aborts;float near,far,cull_far;};
struct Ps2World {re4dc::room::MeshPackage package;unsigned char* storage=nullptr;unsigned bytes=0;const Ps2Part* parts=nullptr;const Ps2Placement* placements=nullptr;unsigned nplacements=0;const std::uint32_t* lut=nullptr;re4dc::room::CompactVertex12* gather=nullptr;float view[12]{},projection[7]{},viewport[6]{};bool camera=false,attempted=false;Ps2Counts count[3]{};unsigned room=0x11f,want=0x11f;}ps2w;
constexpr unsigned kLutBytes=2048,kGatherBytes=3072;
alignas(4096) unsigned char world_bytes[811264];alignas(4096) unsigned char id_bytes[160];bool world_live=true,ids_live=true;
namespace dyn {
struct Head {char magic[4];std::uint32_t version,count,crc;};
constexpr unsigned kIds=250,kNone=255;
unsigned char* block=id_bytes;const std::uint8_t* ids=id_bytes+sizeof(Head);unsigned nids=121;
unsigned char slot_of[250],state[250],moved_of[250];float delta[16][12];
unsigned frame=~0U,nmoved=0,logged_frame=0,binds=0,hidden=0,moved=0,overflow=0;
unsigned query_calls=0;unsigned query(unsigned){++query_calls;return 0;}
}
unsigned r11fPackageGeneration=1,r11fSidecarCrc;
extern "C" int re4dc_room4_live_generation(unsigned* g){*g=room_generation;return room_live;}
extern "C" int re4dc_room4_cell_valid(const void* p,unsigned bytes,unsigned g){return room_live&&g==room_generation&&((p==world_bytes&&world_live&&bytes<=sizeof(world_bytes))||(p==id_bytes&&ids_live&&bytes<=sizeof(id_bytes)));}
#include "movie_world_arena_lifecycle.inc"
movie_world::Ledger ps2_movie;
struct MovieWorldFiles {unsigned mesh=0,side=0,mesh_crc=0,mesh_fnv=0,side_crc=0,side_fnv=0;}ps2_movie_files;
struct MovieWorldRead {MovieWorldRead(){++ps2_movie.readers;}~MovieWorldRead(){--ps2_movie.readers;}};
bool ps2_movie_current();bool ps2_movie_blocked(){return ps2_movie.unavailable();}
struct Re4dcIoScope {};
constexpr int O_RDONLY=0;
bool io_failure=false;
int fs_open(const char* path,int){if(io_failure)return FILEHND_INVALID;return std::strstr(path,"re4mesh")?0:1;}
std::ptrdiff_t fs_total(int fd){return fd?side_file.size():mesh_file.size();}
void fs_close(int){}
bool read_package(int fd,unsigned char* dst,unsigned n,int){const auto& src=fd?side_file:mesh_file;if(io_failure||src.size()!=n)return false;std::memcpy(dst,src.data(),n);return true;}
#include "source_world_actual_movie.inc"
#include "native_source_world_r11f.inc"
struct RecordedUv {unsigned pass,index;float u,v;};std::vector<RecordedUv> native_uv;
int mesh_result=1;unsigned mesh_fail_pass=~0U,mesh_fail_index=~0U;bool borrow_during_draw=false,borrow_refused=false;
void (*stream_yield)()=nullptr;void (*scene_yield)()=nullptr;void (*finish_yield)()=nullptr;
void one_service(void (**slot)()){auto action=*slot;*slot=nullptr;if(action)action();}
void stream_select(unsigned list){if(!stream_scene){stream_scene=true;stream_list=list;stream_closed_lists=0;}else if(stream_list!=list){stream_closed_lists|=1U<<stream_list;stream_list=list;}one_service(&stream_yield);}
void concat(const float* a,const float* b,float* out){for(unsigned r=0;r<3;++r)for(unsigned c=0;c<4;++c){out[r*4+c]=c==3?a[r*4+3]:0;for(unsigned k=0;k<3;++k)out[r*4+c]+=a[r*4+k]*b[k*4+c];}}
struct pvr_vertex_t {unsigned word[8];};pvr_vertex_t packet_scratch[512];std::uint32_t queue_words[16]{};
void (*binding_yield)()=nullptr;bool force_packet=false;unsigned geometry_emits=0,emits_at_yield=0,bind_calls=0;
void binding_service(){++bind_calls;if(binding_yield){auto action=binding_yield;binding_yield=nullptr;emits_at_yield=geometry_emits;action();}}
#include "source_world_host_pvr_constants.inc"
using pvr_list_t=unsigned;using pvr_cull_mode_t=unsigned;using pvr_blend_mode_t=unsigned;using pvr_uv_clamp_t=unsigned;using pvr_ptr_t=void*;
struct pvr_poly_hdr_t {unsigned words[8]{};};
struct pvr_poly_cxt_t {struct {unsigned culling=0,fog_type=0;}gen;struct {unsigned comparison=0,write=0;}depth;struct {unsigned src=0,dst=0;}blend;struct {unsigned env=0,alpha=0,uv_clamp=0;}txr;};
void pvr_poly_cxt_txr(pvr_poly_cxt_t* c,unsigned,unsigned,unsigned,unsigned,void*,unsigned){*c={};}
void pvr_poly_compile(pvr_poly_hdr_t* header,const pvr_poly_cxt_t* context){std::memset(header,0,sizeof(*header));header->words[0]=context->gen.culling;header->words[1]=context->blend.src;header->words[2]=context->blend.dst;header->words[3]=context->txr.uv_clamp;}
struct Key {unsigned crc=0,fnv=0;bool operator==(const Key& b)const{return crc==b.crc&&fnv==b.fnv;}};
struct Texture {unsigned width=256,height=128;};
struct TexturePackage {Texture texture;const Texture* textures()const{return &texture;}void* pvr_texture(unsigned)const{return reinterpret_cast<void*>(0x100);}};
struct Entry {bool valid=true;Key key;TexturePackage package;unsigned frame=0,model_header_key=~0U;pvr_poly_hdr_t model_header;};
union alignas(4096) TexturePage {Entry entry;unsigned char bytes[4096];TexturePage():entry{} {}} texture_page;
Entry& texture_entry=texture_page.entry;Entry* entries=&texture_entry;bool texture_protected=false;
const unsigned* model_texture=nullptr;
Entry* load(const Re4dcUiImage& image,bool,const Key* key){texture_entry.key=key?*key:Key{};texture_entry.package.texture={image.width?image.width:256,image.height?image.height:128};binding_service();return &texture_entry;}
Entry* resolve(const Re4dcUiImage& image,const Re4dcModelPart*,bool){return load(image,false,nullptr);}
namespace re4dc::texture {unsigned pvr_format(const Texture&){return 1;}}
namespace re4dc::render {void begin_pvr_packet(pvr_vertex_t* data,std::uint32_t& count,const pvr_poly_hdr_t& header){std::memcpy(data,&header,32);count=1;}}
#define RE4DC_PROFILE_COUNT(a,b) ((void)0)
#define RE4DC_TOUCH(a) ((void)pin)
constexpr unsigned kPs2HdrSets=32,kPs2HdrWays=4;
struct Ps2HdrSlot {unsigned crc,fnv,size,mode;Entry* entry;pvr_ptr_t texture;std::uint32_t words[4];};
Ps2HdrSlot ps2_hdr[kPs2HdrSets][kPs2HdrWays]{};unsigned char ps2_hdr_next[kPs2HdrSets]{};
unsigned ps2_hdr_hits=0,ps2_hdr_fills=0,ps2_hdr_log=~0U,ps2_hdr_checked=0,ps2_hdr_bad=0;bool header_cache=true;
#define RE4DC_PS2_HDR_ON header_cache
unsigned model_texture_rejects=0,model_wrap_rejects=0,model_header_hits=0,model_header_builds=0,model_scale_rebuilds=0,model_alpha_vertex=0,model_alpha_material=0,model_alpha_faded=0,model_parts=10;
unsigned model_pending=0,frame_pvr_calls=0,frame_pvr_bytes=0;
pvr_vertex_t* model_packets=packet_scratch;Entry* model_handle=nullptr;constexpr unsigned kModelPacketBytes=sizeof(packet_scratch);
bool draining_parts=false;unsigned draining_list=PVR_LIST_TR_POLY;
bool ensure_model_storage(){return true;}unsigned select_model_pass(const Re4dcModelPart*);void stream_open();void re4dc_missing(const char*);
bool model_mask_key(const Re4dcModelPart*,Key&){return false;}void log_pair_miss(const Re4dcModelPart*,const Key&){}
constexpr unsigned PVR_TA_INPUT=0;void* sq_lock(void*){return queue_words;}void sq_flush(void*){}
extern "C" int re4dc_model_packet_reserve(const Re4dcModelPart*,Re4dcModelPacket* out){*out={packet_scratch,512,1,1};return frame_ready&&!stream_aborted;}
extern "C" void re4dc_model_direct_end(unsigned){assert(direct_open);direct_open=false;}
#include "source_world_actual_ui_bind.inc"
void load_screen(const float*,const float*,const float*){}
struct FakeEmitter {
 const Re4dcModelPart& p;float mv[12];float near,far;
 float mvq[12]{};Re4dcModelPacket packet{};pvr_vertex_t* dst=nullptr;
 unsigned limit=0,slots=0;bool bound=false,submitted=false,direct=false;
 std::uint32_t* sq=nullptr;const unsigned* ps2=nullptr;
 #include "source_world_actual_emitter_bind.inc"
};
struct MeshDraw:FakeEmitter {
 const re4dc::room::MeshPackage& package;const re4dc::room::MeshPart& part;
 const std::uint32_t* lut;re4dc::room::CompactVertex12* gather;
 unsigned alpha=0,part_index=0;bool vertex_alpha=false;float cull_far=0,lod_scale=0;
 int run(){
  const unsigned pass=ps2[4];if(force_packet)direct=false;
  if(!bind())return submitted?-1:0;
  if(borrow_during_draw)borrow_refused=ps2_movie.borrow(ps2_movie_current(),true)==0;
  native_uv.push_back({pass,part_index,p.uv_offset[0],p.uv_offset[1]});
  if(pass==mesh_fail_pass && part_index==mesh_fail_index)return mesh_result;
  ++geometry_emits;stream_select(pass==0?PVR_LIST_OP_POLY:pass==1?PVR_LIST_PT_POLY:PVR_LIST_TR_POLY);stream_model_bytes+=32;return 1;
 }
};
namespace {
#include "source_world_actual_native_pass.inc"
}
namespace re4dc::room::ps2 {struct Frame {unsigned frame=~0U,flushed=~0U;float far=25000;bool pending=false;struct Counts { unsigned groups=0,reject_groups=0,input=0,output=0,packets=0,failed=0,clipped=0,culls=0; }count[3];}state;struct WorldDraw { explicit WorldDraw(int){} bool draw(unsigned){assert(false);return false;} };int storage(){return 0;}}
bool ps2_open(){return world_live&&ps2w.storage;}
extern "C" int re4dc_ps2_mesh_movie_blocked(){return ps2_movie_blocked();}
extern "C" void re4dc_ps2_mesh_log(unsigned){}
#include "source_world_actual_native_draw.inc"
extern "C" int re4dc_coarse_source_camera(float* view,float* projection,float* viewport){++camera_calls;std::memcpy(view,pG->Cam.v_mat,sizeof(Mtx));const float p[7]={0,1,0,1,0,-0.01f,-1.01f};const float v[6]={0,0,640,448,0,1};std::memcpy(projection,p,sizeof(p));std::memcpy(viewport,v,sizeof(v));return 1;}
extern "C" void re4dc_ps2_mesh_camera(const float* view,const float* projection,const float* viewport){std::memcpy(ps2w.view,view,48);std::memcpy(ps2w.projection,projection,28);std::memcpy(ps2w.viewport,viewport,24);ps2w.camera=true;}
// Execute the actual final drain and central stream_close guard.
using SourceLighting=re4dc::render::SourceLighting;
struct DeferredPart {DeferredPart* next=nullptr;const void* lighting=nullptr;};DeferredPart* deferred_first=nullptr;
Re4dcModelPart restore_view(DeferredPart*){return {};}
SourceLighting restore_lighting(const void*){return {};}
extern "C" void re4dc_model_submit(const Re4dcModelPart*){++source_geometry;}
void reset_deferred(){deferred_first=nullptr;}
unsigned select_model_pass(const Re4dcModelPart* p){return (!source_draws_finished && !p->depth_mode && (p->blend==4||(p->blend==0&&p->alpha_state==255)))?PVR_LIST_OP_POLY:PVR_LIST_TR_POLY;}
void re4dc_static_flush_impostors(){}
void stream_open(){stream_scene=true;stream_list=PVR_LIST_OP_POLY;stream_closed_lists=0;one_service(&scene_yield);}
int pvr_list_finish(){return 0;}int pvr_scene_finish(){one_service(&finish_yield);return 0;}
void re4dc_missing(const char*){assert(false);}
unsigned shown=0,discarded=0;
void present_submit(bool present,unsigned){present?++shown:++discarded;}
#include "source_world_actual_ui.inc"
unsigned checks=0;void check_at(bool ok,unsigned line){++checks;if(!ok){std::fprintf(stderr,"check %u at line %u failed planned=%u withheld=%u started=%u failed=%u seen=%u/%u receipt=%u/%u\n",checks,line,r11fFrame.planned,r11fFrame.withheld,r11fFrame.started,r11fFrame.failed,r11fFrame.seen,r11fFrame.count,r11fNativeReceipt.attempted,r11fNativeReceipt.completed);std::abort();}}
#define check(v) check_at((v),__LINE__)
std::vector<unsigned char> read_file(const char* p){std::ifstream f(p,std::ios::binary);assert(f);return {std::istreambuf_iterator<char>(f),std::istreambuf_iterator<char>()};}
unsigned scratch=0;
template<class T> T* source_new(unsigned count=1){scratch=(scratch+alignof(T)-1)&~unsigned(alignof(T)-1);assert(scratch+sizeof(T)*count<=sizeof(archive));auto* p=reinterpret_cast<T*>(archive+scratch);for(unsigned i=0;i<count;++i)new(p+i)T{};scratch+=sizeof(T)*count;return p;}
void native_reset(){
 ps2w=Ps2World{};world_live=ids_live=true;io_failure=false;std::memset(world_bytes,0,sizeof(world_bytes));
 std::memcpy(world_bytes,mesh_file.data(),mesh_file.size());std::memcpy(world_bytes+797056,side_file.data(),side_file.size());std::memcpy(id_bytes,ids_file.data(),ids_file.size());
 assert(ps2w.package.adopt(world_bytes,797056,true,true));ps2w.storage=world_bytes;ps2w.bytes=811264;
 ps2w.parts=reinterpret_cast<Ps2Part*>(world_bytes+797056+32);ps2w.placements=reinterpret_cast<Ps2Placement*>(world_bytes+797056+32+172*16);ps2w.nplacements=121;
 ps2w.lut=reinterpret_cast<std::uint32_t*>(world_bytes+797056+9088);ps2w.gather=reinterpret_cast<re4dc::room::CompactVertex12*>(world_bytes+797056+9088+2048);
 dyn::block=id_bytes;dyn::ids=id_bytes+16;dyn::nids=121;std::fill_n(dyn::slot_of,250,255);dyn::slot_of[0]=0;dyn::query_calls=0;
 r11fPackageGeneration=2;r11fSidecarCrc=0x5ea2af04;r11fNativeReceipt={};r11fLegacyFrame=~0U;
 ps2_movie={};assert(ps2_movie.capture(world_bytes,sizeof(world_bytes),room_generation));
 ps2_movie_files={797056,9076,ps2_crc32(world_bytes,797056),movie_world::fnv(world_bytes,797056),ps2_crc32(world_bytes+797056,9076),movie_world::fnv(world_bytes+797056,9076)};
 re4dc::room::ps2::state={};native_uv.clear();mesh_result=1;mesh_fail_pass=mesh_fail_index=~0U;borrow_during_draw=borrow_refused=false;re4dc::render::visible=true;binding_yield=stream_yield=scene_yield=finish_yield=nullptr;force_packet=false;geometry_emits=emits_at_yield=bind_calls=0;assert(!texture_protected);texture_entry=Entry{};std::memset(ps2_hdr,0,sizeof(ps2_hdr));std::memset(ps2_hdr_next,0,sizeof(ps2_hdr_next));header_cache=true;model_texture=nullptr;model_header_builds=frame_pvr_calls=frame_pvr_bytes=0;
}
void reset(bool register_all=true){
 global=Global{};pG=&global;room_generation=10;frame=200;room_live=archive_live=true;movie=subscreen=false;re4dc_coarse_image=re4dc_pace_skipping=0;
 allocator_reset();assert(MemReplaceHeap(0,1)&&MemSetCurrentHeap(1));InitOt();
 assert(MemReplaceHeap(1,2)&&MemSetCurrentHeap(2));host_alloc(96);assert(MemReplaceHeap(2,3)&&MemSetCurrentHeap(3));host_alloc(96);assert(MemReplaceHeap(3,4)&&MemSetCurrentHeap(4));
 objects=make_pool(ObjMgr,251);infos=make_pool(ModInfoMgr,251);source_parts=make_pool(PartsMgr,251);make_pool(EmMgr,4);cModel::mm=&ModInfoMgr;cModel::pm=&PartsMgr;
 scrTbl=static_cast<cObj**>(host_alloc(251*sizeof(cObj*)));std::fill_n(scrTbl,251,nullptr);
 global.prim_cnt=reinterpret_cast<unsigned long>(host_alloc(global.nPrim*2));gx.prim=reinterpret_cast<unsigned char*>(global.prim_cnt);sourceWorldPrimGeneration=1;
 re4dc_alive_gen[0]=1;re4dc_alive_gen[2]=3;r11fFrame={};r11fPlans=r11fDeclines=r11fAborts=0;sourceWorldCallbackDepth=sourceWorldModelDepth=0;sourceWorldCallbackPoisoned=false;
 frame_ready=true;stream_scene=stream_retire=stream_aborted=direct_open=source_draws_finished=false;model_used=stream_model_bytes=stream_closed_lists=stream_discards=0;stream_list=PVR_LIST_OP_POLY;
#if RE4DC_ENCV
 encv_picks=encv_notes=0;
#endif
 aborts=camera_calls=draw_calls=shown=discarded=0;screen_prepares=light_prepares=callback_postludes=source_geometry=shader_resets=draw_syncs=mixed_callbacks=0;after_model=nullptr;deferred_first=nullptr;
 std::memcpy(archive,source_file.data(),source_file.size());scratch=2200000;
 pSmd=reinterpret_cast<cSmd*>(archive+123808);pSmx=reinterpret_cast<cSmx*>(archive+1368800);nScrWork=251;
 sourceWorldR11fQualify();check(r11fRawQualified);
 auto* palette=source_new<TEXPalette>();palette->version=0x20af30;palette->numDescriptors=2;palette->descriptorArray=source_new<TEXDescriptor>(2);
 for(unsigned j=0;j<2;++j){auto* tex=source_new<TEXHeader>();tex->width=256;tex->height=128;tex->wrapS=tex->wrapT=1;tex->data=archive+2100000;palette->descriptorArray[j].textureHeader=tex;}
 auto* offsets=reinterpret_cast<u32*>(reinterpret_cast<unsigned char*>(pSmd)+pSmd->BinTblOfs);
 bool built[256]{};
 for(unsigned i=0;i<251;++i){auto& w=pSmd->work[i];auto* d=reinterpret_cast<ModelData*>(reinterpret_cast<unsigned char*>(offsets)+offsets[w.binNo]);
  if(!built[w.binNo]){new(d)ModelData{};d->nParts=1;d->displist_num=1;d->pHead=source_new<ModelDataHead>();d->pHead->parentNo=255;d->pParts=source_new<ModelPart>();d->pParts->texId=1;built[w.binNo]=true;}
  auto& m=objects[i];auto& info=infos[i];auto& part=source_parts[i];m.serial=100+i;m.pos=w.pos;m.ang=w.rot;m.scale=w.scale;m.pModelInfo=&info;m.pList=&part;info.pData=d;info.tpl_addr=palette;part.pParent=&m;part.pos=d->pHead->center;scrTbl[i]=&m;
  for(unsigned j=0;j<pSmx->nWork;++j)if(pSmx->work[j].id==w.id && w.id!=0xfe){smxInit(&m,&pSmx->work[j]);break;}
  sourceWorldR11fScrollBind(i,&m);
 }
 sourceWorldR11fScrollPublish();check(r11fScrollPublished);check(re4dc_r11f_scroll_group());
 native_reset();global.Cam.v_mat[0][0]=global.Cam.v_mat[1][1]=global.Cam.v_mat[2][2]=1;
 if(register_all)for(unsigned i=0;i<251;++i)ModelTrans(&objects[i]);
}
void finish_and_present(){re4dc_model_finish_source_draws();stream_close(true);}
void manual_callback(unsigned index){auto& e=r11fFrame.entries[index];re4dc_source_world_callback_begin(e.table,e.node,reinterpret_cast<void(*)(void*)>(ModelRender),e.model,e.kind);ModelRender(e.model);re4dc_source_world_callback_end();}
void remove_anchor(){for(auto& ot:g_OtWork)for(auto* p=ot.list?&ot.list[ot.max-1]:nullptr;p;p=p->next)if(p->next&&p->next->data==objects){p->next=p->next->next;return;}}
void hide_anchor_after_first(cModel*){after_model=nullptr;remove_anchor();}
void late_anchor_after_first(cModel*){after_model=nullptr;stream_select(PVR_LIST_TR_POLY);}
void change_sibling_after_first(cModel*){after_model=nullptr;objects[100].pos.x+=1;}
void recursive_same_model(cModel* m){after_model=nullptr;ModelRender(m);}
void recursive_bad_model(cModel*){after_model=nullptr;ModelRender(reinterpret_cast<cModel*>(1));}
void retire_ot_after_first(cModel*){after_model=nullptr;MemDestroyHeap(1);}
void yield_change_pose(){objects[100].pos.x+=1;}
void yield_change_visibility(){objects[100].be_flag&=~2U;}
void yield_change_material(){infos[100].color[0]^=1U;}
void yield_change_source_work(){pSmd->work[100].pos.x+=1;}
void yield_change_frame(){++frame;}
void yield_change_source_frame(){++global.Frame_cnt;}
void yield_change_phase(){infos[0].uvU+=.25f;}
void yield_retire_texture_after_pose(){yield_change_pose();texture_protected=true;assert(mprotect(&texture_page,4096,PROT_NONE)==0);}
void texture_unprotect(){if(texture_protected){assert(mprotect(&texture_page,4096,PROT_READ|PROT_WRITE)==0);texture_protected=false;}}
unsigned protected_mode=0;void* protected_page=nullptr;
void protect_retired_primitive(cModel*) {
 after_model=nullptr;Re4dcSourceWorldCallback call{};assert(re4dc_source_world_callback_current(&call));
 const auto* node=static_cast<const OtData*>(call.node);const void* selected=protected_mode?node->next:node;
 assert(selected);assert((reinterpret_cast<std::uintptr_t>(node)&~std::uintptr_t(4095))!=(reinterpret_cast<std::uintptr_t>(node->next)&~std::uintptr_t(4095)));protected_page=reinterpret_cast<void*>(reinterpret_cast<std::uintptr_t>(selected)&~std::uintptr_t(4095));
 Mem_free_h(reinterpret_cast<void*>(global.prim_cnt),4);
 assert(!sourceWorldAllocated(reinterpret_cast<void*>(global.prim_cnt),global.nPrim*2,true));
 assert(mprotect(protected_page,4096,PROT_NONE)==0);
}
void unprotect_retired(){assert(protected_page);assert(mprotect(protected_page,4096,PROT_READ|PROT_WRITE)==0);protected_page=nullptr;}
int main(int argc,char** argv){
 assert(argc==5);source_file=read_file(argv[1]);mesh_file=read_file(argv[2]);side_file=read_file(argv[3]);ids_file=read_file(argv[4]);
 reset();re4dc_r11f_prepare(frame);check(r11fFrame.planned&&r11fFrame.count==251&&r11fFrame.anchor>0);
 const float phase=infos[0].uvU;Render();check(r11fFrame.withheld&&r11fFrame.anchor_seen&&r11fFrame.started&&r11fFrame.render_done);
 check(source_geometry==0&&callback_postludes==251&&shader_resets==251&&aborts==0&&dyn::query_calls==0);finish_and_present();
#if RE4DC_ENCV
 check(encv_picks==251&&encv_notes>0&&sourceWorldModelDepth==0);
#endif
 check(shown==1&&discarded==0&&r11fNativeReceipt.attempted==7&&r11fNativeReceipt.completed==7);
 check(r11fNativeReceipt.uv[0]==phase);unsigned changed=0;for(const auto& u:native_uv){if(u.index==0&&u.pass==0){check(u.u==phase&&u.v==0);++changed;}else check(u.u==0&&u.v==0);}check(changed==1);
 const unsigned packets=stream_model_bytes;re4dc_ps2_world_flush();check(stream_model_bytes==packets);
 // Source-produced phase: exact original stop and wrap code, including >1.
 reset(false);infos[0].uvU=1.25f;infos[0].uvV=1.75f;global.Stop_flg=0x08000000;actual_source_uv(&infos[0]);check(infos[0].uvU==1.25f&&infos[0].uvV==1.75f);
 global.Stop_flg=0;infos[0].uvU=1.99999f;actual_source_uv(&infos[0]);check(infos[0].uvU<.001f);
 infos[0].uvU=-.0003f;actual_source_uv(&infos[0]);check(infos[0].uvU>1.999f);
 for(unsigned i=0;i<251;++i)ModelTrans(&objects[i]);const float wrapped=infos[0].uvU;re4dc_r11f_prepare(frame);Render();finish_and_present();check(shown==1&&r11fNativeReceipt.uv[0]==wrapped);
 // Complete authored group rejection occurs before any withholding.
 for(unsigned mutation=0;mutation<12;++mutation){reset();
  switch(mutation){case 0:objects[100].pos.x+=1;break;case 1:objects[100].type=1;break;case 2:infos[100].color[0]^=1;break;case 3:infos[100].uvU=.25f;break;case 4:infos[100].pShape=(void*)1;break;case 5:objects[100].ot_type=7;break;case 6:source_parts[100].mat[0][0]=1;break;case 7:infos[100].pData->pParts->flags^=4;break;case 8:static_cast<TEXPalette*>(infos[100].tpl_addr)->descriptorArray[1].textureHeader->wrapS=0;break;case 9:objects[100].serial++;break;case 10:scrTbl[100]=scrTbl[99];break;case 11:pSmd->work[100].scale.x+=1;break;}
  re4dc_r11f_prepare(frame);check(!r11fFrame.planned&&!r11fFrame.withheld&&aborts==0);}
 reset();remove_anchor();re4dc_r11f_prepare(frame);check(!r11fFrame.planned&&aborts==0);
 reset();r11fLegacyStamp(frame);re4dc_r11f_prepare(frame);check(!r11fFrame.planned&&!r11fNativeClaimed());
 // Earlier withheld callbacks make a missing, late, changed or recursive
 // anchor/group fatal to this scene, without replaying any GC room geometry.
 for(auto action:{hide_anchor_after_first,late_anchor_after_first,change_sibling_after_first,recursive_same_model,recursive_bad_model,retire_ot_after_first}){reset();re4dc_r11f_prepare(frame);after_model=action;Render();finish_and_present();check(r11fFrame.failed&&aborts==1&&shown==0&&discarded==1&&source_geometry==0);}
 // Actual ExecOt must not read kind/next after the callback retires the
 // primitive allocation. Current and next nodes are separate protected pages.
 for(protected_mode=0;protected_mode<2;++protected_mode){reset(false);
  GetPrimBuff(4096);ModelTrans(&objects[0]);GetPrimBuff(4096);ModelTrans(&objects[1]);GetPrimBuff(4096);ModelTrans(&objects[2]);
  re4dc_r11f_prepare(frame);check(r11fFrame.planned&&r11fFrame.count==3&&r11fFrame.anchor==2);
  after_model=protect_retired_primitive;Render();unprotect_retired();finish_and_present();
  check(r11fFrame.failed&&aborts==1&&shown==0&&discarded==1&&source_geometry==0);
 }
 // Native passes: actual loop fallback/abort, missing PT/TR, projection failure.
 for(unsigned pass=0;pass<3;++pass)for(int result:{0,-1}){reset();re4dc_r11f_prepare(frame);mesh_fail_pass=pass;mesh_result=result;for(unsigned p=0;p<172;++p)if(ps2w.parts[p].pass==pass){mesh_fail_index=p;break;}Render();finish_and_present();check(shown==0&&discarded==1&&aborts==1&&r11fFrame.failed&&r11fNativeReceipt.completed!=7);}
 reset();re4dc_r11f_prepare(frame);Render();stream_close(true);check(shown==0&&discarded==1&&r11fFrame.failed);
 reset();re4dc_r11f_prepare(frame);Render();re4dc::room::ps2::state.pending=false;finish_and_present();check(shown==0&&discarded==1&&r11fNativeReceipt.completed==1);
 reset();re4dc_r11f_prepare(frame);borrow_during_draw=true;Render();finish_and_present();check(shown==1&&borrow_refused&&ps2_movie.phase==movie_world::Phase::ready);
 // Execute production Emitter::bind for direct and packet paths. A source
 // mutation while the texture service yields aborts before its first vertex.
 for(bool packet:{false,true})for(auto action:{yield_change_pose,yield_change_visibility,yield_change_material,yield_change_source_work,yield_change_frame,yield_change_source_frame,yield_change_phase,yield_retire_texture_after_pose}) {
  reset();re4dc_r11f_prepare(frame);force_packet=packet;binding_yield=action;Render();texture_unprotect();finish_and_present();
  check(r11fFrame.failed&&aborts==1&&shown==0&&discarded==1&&source_geometry==0);
  check(bind_calls==1&&geometry_emits==emits_at_yield&&geometry_emits==0&&!direct_open&&dyn::query_calls==0&&frame_pvr_calls==0&&model_header_builds==0);
 }
#if RE4DC_PS2_WORLD_HDR_CACHE==2
 // Cached-hit diagnostic load is also a yielding path. The source mutation
 // invalidates the claim before touching the returned unreadable Entry.
 reset(false);const unsigned cacheKey[6]={0xf417e94dU,0x46e00253U,256,128,0,2};Re4dcModelDirect warm{};
 check(re4dc_ps2_world_direct_begin(cacheKey,&warm)==1);re4dc_model_direct_end(0);
 ++frame;++global.Frame_cnt;stream_scene=false;stream_model_bytes=0;frame_pvr_calls=model_header_builds=bind_calls=geometry_emits=0;
 for(unsigned i=0;i<251;++i)ModelTrans(&objects[i]);re4dc_r11f_prepare(frame);binding_yield=yield_retire_texture_after_pose;Render();texture_unprotect();finish_and_present();
 check(r11fFrame.failed&&aborts==1&&shown==0&&geometry_emits==0&&frame_pvr_calls==0&&model_header_builds==0&&bind_calls==1&&ps2_hdr_hits>0);
#endif
 // A claim that fails before OP returns remains closed against direct pass
 // or legacy entry attempts until the explicit new-frame prepare lifecycle.
 reset();re4dc_r11f_prepare(frame);binding_yield=yield_change_frame;Render();check(r11fNativeClaimed()&&re4dc_r11f_legacy_blocked(frame));
 const unsigned oldEmits=geometry_emits,oldBinds=bind_calls;check(re4dc_ps2_mesh_draw(1,25000)==0);check(geometry_emits==oldEmits&&bind_calls==oldBinds);finish_and_present();check(shown==0&&aborts==1);
 ++frame;re4dc_r11f_prepare(frame);check(!r11fFrame.failed&&!r11fNativeClaimed());
#if RE4DC_MESH_TEXTURES
 reset();re4dc_r11f_prepare(frame);const unsigned bakedKey[4]={0xf417e94dU,0x46e00253U,256,128};model_texture=bakedKey;force_packet=true;binding_yield=yield_retire_texture_after_pose;Render();texture_unprotect();finish_and_present();
 check(r11fFrame.failed&&aborts==1&&shown==0&&geometry_emits==0&&model_header_builds==0&&bind_calls==1);
#endif
 // A list/scene wait also cannot resume a stale cached texture/header.
 for(bool packet:{false,true}){reset();re4dc_r11f_prepare(frame);force_packet=packet;stream_yield=yield_retire_texture_after_pose;Render();texture_unprotect();finish_and_present();check(r11fFrame.failed&&shown==0&&geometry_emits==0&&frame_pvr_calls==0&&aborts==1);}
 for(unsigned where=0;where<2;++where){reset();re4dc_r11f_prepare(frame);Render();re4dc_model_finish_source_draws();
  if(where==0){stream_scene=false;scene_yield=yield_change_frame;}else finish_yield=yield_change_frame;
  stream_close(true);check(r11fFrame.failed&&shown==0&&discarded==1&&aborts==1);
 }
 // The unchanged, unclaimed PS2 path still executes the existing dynamic query.
 reset(false);ps2w.camera=true;ps2w.projection[1]=ps2w.projection[3]=1;ps2w.projection[5]=-.01f;ps2w.projection[6]=-1.01f;ps2w.viewport[2]=640;ps2w.viewport[3]=448;
 check(ps2_pass(0,25000)==1&&dyn::query_calls>0&&geometry_emits>0);
 // Primary ownership and movie lease reject before any package read.
 reset();unsigned generation=0;check(re4dc_r11f_package(&generation,1));world_live=false;check(!re4dc_r11f_package(&generation,1));world_live=true;ids_live=false;check(!re4dc_r11f_package(&generation,1));
 reset();re4dc_r11f_prepare(frame);{R11fRenderScope scope;manual_callback(0);check(r11fFrame.withheld&&!r11fFrame.started);const unsigned before=r11fPackageGeneration;const auto token=ps2_movie.borrow(ps2_movie_current(),true);check(token);ps2_movie_unpublish();check(r11fPackageGeneration!=before);manual_callback(1);}finish_and_present();check(r11fFrame.failed&&shown==0&&aborts==1);
 // Primary allocation provenance precedes header/ID reads, even when
 // the retired bytes are unreadable; rejected source pool slots likewise.
 reset();world_live=false;assert(mprotect(world_bytes,4096,PROT_NONE)==0);check(!re4dc_r11f_package(&generation,1));assert(mprotect(world_bytes,4096,PROT_READ|PROT_WRITE)==0);
 reset();ids_live=false;assert(mprotect(id_bytes,4096,PROT_NONE)==0);check(!re4dc_r11f_package(&generation,1));assert(mprotect(id_bytes,4096,PROT_READ|PROT_WRITE)==0);
 reset();re4dc_r11f_prepare(frame);{R11fRenderScope scope;manual_callback(0);unsigned targetIndex=0;while(r11fFrame.entries[targetIndex].work!=100)++targetIndex;const auto target=r11fFrame.entries[targetIndex].model;
  auto* poolCell=pool(&ObjMgr)->chunks;Mem_free_h(poolCell,4);
  void* page=reinterpret_cast<void*>(reinterpret_cast<std::uintptr_t>(target)&~std::uintptr_t(4095));
  // Pool proof must fail before accessing any captured model. This selected
  // page is wholly inside the old chunk, separate from allocator headers.
  assert(mprotect(page,4096,PROT_NONE)==0);manual_callback(targetIndex);assert(mprotect(page,4096,PROT_READ|PROT_WRITE)==0);
 }finish_and_present();check(r11fFrame.failed&&aborts==1&&shown==0);
 // Wrong callback role/depth, duplicate callback and extra unqualified room
 // callback cannot consume an existing role or acknowledge missing source work.
 for(unsigned mode=0;mode<5;++mode){reset();re4dc_r11f_prepare(frame);{R11fRenderScope scope;manual_callback(0);
  auto e=r11fFrame.entries[mode==4?0:1];
  re4dc_source_world_callback_begin(mode==0?0x11:e.table,e.node,reinterpret_cast<void(*)(void*)>(ModelRender),e.model,mode==1?3:e.kind);
  if(mode==2)re4dc_source_world_callback_begin(e.table,e.node,reinterpret_cast<void(*)(void*)>(ModelRender),e.model,e.kind);
  ModelRender(e.model);
  if(mode==2)re4dc_source_world_callback_end();re4dc_source_world_callback_end();
  if(mode==3)objects[100].pModelInfo=reinterpret_cast<cModelInfo*>(1);
 }finish_and_present();check(r11fFrame.failed&&aborts==1&&shown==0&&source_geometry==0);}
 // Receipt UV data is transient for only the unique placement/part/pass;
 // cancellation and new frames leave reused local part views neutral.
 reset();re4dc_r11f_prepare(frame);Render();Re4dcModelPart view{};r11fNativeReceipt.uv[0]=.75f;
 {R11fUvScope uv(view,0,0,0,0);check(view.uv_offset[0]==.75f);}check(view.uv_offset[0]==0&&view.uv_offset[1]==0);
 for(unsigned mode=0;mode<4;++mode){view.uv_offset[0]=.8f;{R11fUvScope uv(view,mode==0?1:0,mode==1?1:0,mode==2?1:0,mode==3?1:0);check(view.uv_offset[0]==0);}check(view.uv_offset[0]==0);}
 re4dc_r11f_native_cancel(0);{R11fUvScope uv(view,0,0,0,0);check(view.uv_offset[0]==0);}++frame;{R11fUvScope uv(view,0,0,0,0);check(view.uv_offset[0]==0);}
 // Exact movie reload function advances generation on each failed and successful
 // same-address readoption; the old receipt never becomes current again.
 reset();const unsigned before=r11fPackageGeneration;const auto token=ps2_movie.borrow(ps2_movie_current(),true);check(token);ps2_movie_unpublish();check(ps2_movie.begin_return(token,ps2_movie_current()));io_failure=true;check(!ps2_movie_reload());const auto failed_generation=r11fPackageGeneration;io_failure=false;check(ps2_movie_reload());check(r11fPackageGeneration!=before&&r11fPackageGeneration!=failed_generation);check(ps2_movie.restored(token,ps2_movie_current(),true));check(re4dc_r11f_package(&generation,1));
 // Presentation cannot acknowledge mutated metadata or reset zero counters.
 reset();re4dc_r11f_prepare(frame);Render();re4dc_model_finish_source_draws();const_cast<Ps2Part*>(ps2w.parts)[1]=ps2w.parts[0];stream_close(true);check(shown==0&&r11fFrame.failed);
 reset();re4dc_r11f_prepare(frame);Render();re4dc_model_finish_source_draws();r11fNativeReceipt.result[2]=0;stream_close(true);check(shown==0&&r11fFrame.failed);
 std::printf("r11f actual source/OT/pass/drain/present: %u checks PASS (synthetic constructors/GPU, pinned private inputs)\n",checks);
}
