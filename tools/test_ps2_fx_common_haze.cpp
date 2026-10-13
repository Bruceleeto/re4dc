// Host adapter qualification of the actual default-off common haze include.
// Synthetic source objects exercise read-only grouping, fallback and submission;
// this does not claim source ABI, runtime visuals or hardware performance.
#include <cassert>
#include <cmath>
#include <cstring>
#include <cstdio>
#include <new>
#include <cstdint>
using u8=unsigned char;using u16=unsigned short;using u32=unsigned;using f32=float;
#define RE4DC_PS2_FX_COMMON_HAZE 1
#define RE4DC_TA_BIN_DIAG 1
#include "../src/game/ps2_fx_population.h"
#include "../port/dreamcast/game/platform/include/native_ui.h"
struct Vec{float x,y,z;};using Mtx44=float[4][4];using Mtx=float[3][4];
struct GXColor{u8 r,g,b,a;};struct Info{u32 Call_no,Core_pEm;u16 Core_flg;u8 Core_kind,owner;};
struct cEsp{
    Info info;u8 m_Be_flg,m_Id,m_Tex_id,m_Type,m_Parts_no,m_Release_time,m_Blend_type,xA4,xA5,xA6;
    u8 m_Shimmer_type,m_Shimmer_pow,m_MaskTex_id,m_Ptn_no,m_Anm_rate,m_Col_start_r,m_Col_start_g,m_Col_start_b,m_Col_start_a;
    u16 m_Flg,m_Life_max,m_Life_time,m_Col_max_cnt,m_Col_start_cnt,m_Pos_start_cnt,m_Size_start_cnt,m_Del_far,m_Del_near;
    u32 m_Tool_flg;void* parent;void* m_pMod;
    float m_Size_base_x,m_Size_base_y,m_Size_mul,m_Size_plus,m_D_size_plus,m_D_speed,m_Col_d_r,m_Col_d_g,m_Col_d_b,m_Col_d_a;
    Vec m_Speed_plus,m_Ang,m_Ang_plus;
};
struct Ps2fxEsp15Work{float Range,Del_ratio,Base_alpha,Min_y;u8 Room_del_frame,Room_del_cnt;};
struct cPs2fxEsp15:cEsp{Ps2fxEsp15Work m_Free;};
static_assert(sizeof(cPs2fxEsp15)<=0x150,"synthetic source fits bounded slot");
struct AreaXZ{float x,z;};struct AreaXZ4{float floor,height,radius;AreaXZ p[4];};
struct AreaData{u8 Be_flag,type;u16 x2;union {AreaXZ4 xz4;}u;};
struct SstAreaEnt{u8 no,be_flag,area_no,pad;u8 area[0x30];u32 flag;};struct SstArea{u32 num;SstAreaEnt ent[19];};
enum{AREA_TYPE_XZ4=1,PS2FX_HAZE=2};
struct TEXHeader{const void* data;unsigned width,height,format;};struct CLUT{const void* data;unsigned format,numEntries;};
struct TEXDescriptor{TEXHeader* textureHeader;CLUT* CLUTHeader;};struct TPL{unsigned numDescriptors;};
struct Anm{unsigned Cx,Cy,Width,Height,Frames;};struct EspTexWk{unsigned Owner;TPL* pTpl;Anm* pAnm;Mtx mtx;};
struct Sys{u8* pEspBuf;unsigned nEsp;SstArea* pSstArea;EspTexWk Esp_tex_tbl[256];};
struct Camera{struct {Vec pos,at;}param;Vec up;Mtx v_mat;Mtx44 ProjMat;};
struct Global{unsigned Frame_cnt,Status_flg[4],Stop_flg;Camera Cam;};struct Player{Vec pos;};
static Sys sys;static Global globals;static Player player;static Sys* g_pEspSys=&sys;static Global* pG=&globals;static Player* pPL=&player;
static unsigned G_ROOM_ID,re4dc_ps2fx=PS2FX_HAZE;static void* pEffParentWorld=(void*)1;
static unsigned fake_generation=1,fake_batch_calls,fake_submitted;static bool fake_resident=true,fake_submit=true,fake_area=true;
static bool fake_other_indoor=false,fake_ps2_indoor=false;static unsigned fake_other_calls,fake_ps2_calls;
static TEXHeader tex={(void*)2,128,128,5};static TEXDescriptor td={&tex,nullptr};static TPL tpl={1};static Anm anm={0,0,128,128,1};
static void PSVECSubtract(const Vec* a,const Vec* z,Vec* o){*o={a->x-z->x,a->y-z->y,a->z-z->z};}
static void PSVECCrossProduct(const Vec* a,const Vec* z,Vec* o){*o={a->y*z->z-a->z*z->y,a->z*z->x-a->x*z->z,a->x*z->y-a->y*z->x};}
static void PSVECNormalize(const Vec* a,Vec* o){const float r=std::sqrt(a->x*a->x+a->y*a->y+a->z*a->z);*o={a->x/r,a->y/r,a->z/r};}
static void PSMTXMultVec(const Mtx m,const Vec* v,Vec* o){*o={m[0][0]*v->x+m[0][1]*v->y+m[0][2]*v->z+m[0][3],m[1][0]*v->x+m[1][1]*v->y+m[1][2]*v->z+m[1][3],m[2][0]*v->x+m[2][1]*v->y+m[2][2]*v->z+m[2][3]};}
static const TEXDescriptor* TEXGet(TPL*,unsigned){return &td;}
static void GXGetViewportv(float* o){const float v[6]={0,0,640,480,0,1};std::memcpy(o,v,sizeof(v));}
static int EffIsSetFinalCol(){return 0;}static void EffGetFinalCol(GXColor* c){*c={255,255,255,255};}
static int EffGetAreaState(unsigned n){assert(n<32);return fake_area;}
static int EspSpriteEligible(cEsp*){return 1;}
static int AreaHitCheck(void*,Vec*){++fake_other_calls;return fake_other_indoor;}
static int areaHitCheck_xz4(AreaXZ4* a,Vec*){++fake_ps2_calls;assert(a->height==5827.89599609375f);assert(a->p[2].x==24412.912109375f);assert(a->p[3].z==-25024.001953125f);return fake_ps2_indoor;}
extern "C" int ESP_IsActive(cEsp* e){return (e->m_Be_flg&1)!=0;}
extern "C" int re4dc_room4_state(unsigned* gen,unsigned* cells,unsigned* bytes,unsigned* stale,unsigned* refused){*gen=fake_generation;*cells=*bytes=*stale=*refused=0;return fake_resident;}
extern "C" void re4dc_log(const char*,...){}
extern "C" int re4dc_effect_haze_batch(Re4dcEffectSprite* s,unsigned n,unsigned* submitted){
    ++fake_batch_calls;assert(n<=12);
    for(unsigned i=0;i<n;++i){assert(s[i].src==4 && s[i].dst==5 && s[i].pad==2);for(unsigned j=0;j<4;++j)assert(std::isfinite(s[i].x[j]) && std::isfinite(s[i].y[j]) && s[i].z[j]>0);}
    *submitted=fake_submit?n:0;fake_submitted+=*submitted;return fake_submit;
}
#include "../src/game/ps2_fx_common_haze.inc"
alignas(16) static u8 source_pool[2048*0x150];static u8 source_copy[sizeof(source_pool)];static SstArea area;
static void setup_weather(){
    area={};area.num=19;for(unsigned i=0;i<13;++i){area.ent[i].no=(u8)i;area.ent[i].be_flag=1;area.ent[i].flag=1;}
    auto& e=area.ent[10];e.area_no=255;AreaData d={};d.Be_flag=1;d.type=1;
    d.u.xz4={3.737884521484375f,5759.1259765625f,3500,{{16768.234375f,-29085.21484375f},{23186.787109375f,-31056.982421875f},{24521.90625f,-27215.91796875f},{17823.53125f,-25192.62109375f}}};
    std::memcpy(e.area,&d,sizeof(d));sys.pSstArea=&area;
}
static cPs2fxEsp15* particle(unsigned n){return reinterpret_cast<cPs2fxEsp15*>(source_pool+n*0x150);}
static void source_age(cEsp& e,unsigned short age,float initial){e.m_Life_time=age;e.m_Size_mul=1;e.m_Size_plus=initial;for(unsigned n=0;n<age;++n){e.m_Size_mul+=e.m_Size_plus;e.m_Size_plus*=.9900000095367432f;}}
static void fill(unsigned room,unsigned age=200){
    std::memset(source_pool,0,sizeof(source_pool));G_ROOM_ID=room;++fake_generation;++globals.Frame_cnt;sys.nEsp=0;
    for(const auto& r:kPs2CommonHaze)if(r.room==room)for(unsigned n=0;n<r.count;++n){
        auto& e=*new(source_pool+sys.nEsp++*0x150)cPs2fxEsp15{};
        e.info={unsigned(r.kind)+300,0,0x4001,r.kind,0xd0};e.m_Be_flg=1;e.m_Id=0x15;e.m_Tex_id=r.visual.texture;e.m_Parts_no=0xfe;e.m_Release_time=0xff;
        e.parent=pEffParentWorld;e.xA4=1;e.xA5=4;e.xA6=5;e.m_Anm_rate=0x20;e.m_Size_base_x=e.m_Size_base_y=r.gc_size;
        e.m_D_size_plus=.9900000095367432f;e.m_D_speed=e.m_Col_d_r=e.m_Col_d_g=e.m_Col_d_b=e.m_Col_d_a=1;
        e.m_Col_start_r=r.rgba[0];e.m_Col_start_g=r.rgba[1];e.m_Col_start_b=r.rgba[2];e.m_Col_start_a=r.rgba[3];
        e.m_Col_max_cnt=r.color_max;e.m_Del_far=r.work[0]*10;e.m_Del_near=r.work[1]*10;
        e.m_Free.Range=r.gc_range;e.m_Free.Del_ratio=1.0f-(float)r.work[2]/100.0f;e.m_Free.Room_del_frame=r.work[3];
        source_age(e,(u16)age,r.gc_initial_plus);
    }
}
static void draw_unchanged(){std::memcpy(source_copy,source_pool,sizeof(source_pool));Ps2fxCommonHazeDraw();assert(!std::memcmp(source_copy,source_pool,sizeof(source_pool)));}
int main(){
    sys.pEspBuf=source_pool;globals.Cam.param.at={0,0,-1};globals.Cam.up={0,1,0};for(unsigned i=0;i<3;++i)globals.Cam.v_mat[i][i]=1;
    globals.Cam.ProjMat[0][0]=globals.Cam.ProjMat[1][1]=1;globals.Cam.ProjMat[2][2]=-.0001f;globals.Cam.ProjMat[2][3]=-1;
    for(unsigned i=30;i<=31;++i){auto& tw=sys.Esp_tex_tbl[i];tw.Owner=0;tw.pTpl=&tpl;tw.pAnm=&anm;tw.mtx[0][0]=tw.mtx[1][1]=1;}
    setup_weather();unsigned rooms=0;
    for(unsigned room=0x100;room<=0x10b;++room){if(room==0x108)continue;++rooms;fill(room);draw_unchanged();
        assert(s_common_accepted==(room==0x105 || room==0x106 || room==0x107?3U:1U));
        assert(s_common_haze[0].state.age==200);const auto old=s_common_haze[0].state;draw_unchanged();assert(!std::memcmp(&old,&s_common_haze[0].state,sizeof(old)));
        for(unsigned n=0;n<sys.nEsp;++n){auto& e=*particle(n);++e.m_Life_time;e.m_Size_mul+=e.m_Size_plus;e.m_Size_plus*=.9900000095367432f;}
        ++globals.Frame_cnt;draw_unchanged();assert(s_common_haze[0].state.age==201);assert(Ps2fxCommonHazeSuppress(particle(0)));
    }
    fill(0x100);--sys.nEsp;draw_unchanged();assert(!s_common_accepted && !Ps2fxCommonHazeSuppress(particle(0)));
    fill(0x100);++particle(2)->info.Call_no;draw_unchanged();assert(!s_common_accepted);
    fill(0x100);++particle(2)->m_Life_time;draw_unchanged();assert(!s_common_accepted);
    fill(0x100);particle(2)->m_Size_mul+=.1f;draw_unchanged();assert(!s_common_accepted);
    fill(0x100);particle(2)->m_Tool_flg=1;draw_unchanged();assert(!s_common_accepted);
    fill(0x100);fake_submit=false;draw_unchanged();assert(!s_common_accepted && !Ps2fxCommonHazeSuppress(particle(0)));fake_submit=true;draw_unchanged();assert(s_common_accepted==1);
    fill(0x105);fake_area=false;draw_unchanged();assert(!s_common_accepted);fake_area=true;draw_unchanged();assert(s_common_accepted==3);
    fill(0x105);particle(1)->m_Life_max=1;draw_unchanged();assert(s_common_accepted==2 && !Ps2fxCommonHazeSuppress(particle(0)) && Ps2fxCommonHazeSuppress(particle(51)));
    fill(0x100,0);draw_unchanged();assert(!s_common_accepted);
    fill(0x100,1026);draw_unchanged();assert(!s_common_accepted);
    fill(0x100);sys.nEsp=2049;draw_unchanged();assert(!s_common_accepted);
    fill(0x100);anm.Width=64;draw_unchanged();assert(!s_common_accepted);anm.Width=128;
    fill(0x100);globals.Cam.param.pos.x=NAN;draw_unchanged();assert(!s_common_accepted);globals.Cam.param.pos.x=0;
    fill(0x100);globals.Cam.ProjMat[0][0]=NAN;draw_unchanged();assert(!s_common_accepted);globals.Cam.ProjMat[0][0]=1;
    fill(0x100);fake_resident=false;draw_unchanged();assert(!s_common_accepted);fake_resident=true;
    fill(0x100);re4dc_ps2fx=0;draw_unchanged();assert(!s_common_accepted);re4dc_ps2fx=PS2FX_HAZE;
    fill(0x101);SstArea saved=area;fake_ps2_indoor=true;draw_unchanged();assert(s_common_accepted==1 && s_common_haze[0].state.indoor_count==30);assert(!std::memcmp(&saved,&area,sizeof(area)));fake_ps2_indoor=false;
    fill(0x101);area.ent[10].no=11;draw_unchanged();assert(!s_common_accepted);setup_weather();
    fill(0x101);globals.Stop_flg=0x20;globals.Status_flg[1]=0x800;draw_unchanged();assert(s_common_accepted==1 && s_common_haze[0].state.indoor_count==30);globals.Stop_flg=globals.Status_flg[1]=0;
    assert(fake_submitted>0);
    std::printf("PASS actual common adapter: %u rooms/14 profiles, complete/mixed/partial/duplicate/source-clock/resource/area/room-generation fallback, source bytes unchanged; submitted=%u calls=%u. Host sizes row=%zu clock=%zu scratch=%zu\n",rooms,fake_submitted,fake_batch_calls,sizeof(Ps2fxCommonRow),sizeof(ps2fx::CommonHazeClock),sizeof(Re4dcEffectSprite)*12);
}
