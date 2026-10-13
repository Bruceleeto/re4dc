// Exercise the actual guarded batch implementation with bounded native queue
// stubs. Verifies transaction/fallback, not Dreamcast packets or GPU behavior.
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <algorithm>
#include <new>
#define RE4DC_PS2_FX_COMMON_HAZE 1
#define RE4DC_EFFECT_ROOM 1
#define RE4DC_RES_MODES 1
#define RE4DC_TA_BIN_DIAG 1
#define RE4DC_EFFECT_SPRITE_MAX 64U
#define RE4DC_SCREEN_WF 320.0f
#define RE4DC_SCREEN_HF 240.0f
#include "../port/dreamcast/game/platform/include/native_ui.h"
namespace re4dc {namespace render {bool is_finite(float f){return std::isfinite(f);}}}
namespace tabin {float fill_haze,fill_fx;float clip_area(const float*,const float*,unsigned){return 100;}}
struct Key {unsigned a,b;bool operator==(const Key& x)const{return a==x.a && b==x.b;}};
struct Entry {bool valid;Key key;unsigned frame;};
struct DeferredPart{DeferredPart* next;void* lighting;unsigned changed[1];};
constexpr unsigned kSpriteNode=(sizeof(DeferredPart)+31)&~31U,kSpritePacket=96;
static void* const kSpriteTag=(void*)1;
alignas(32) static unsigned char frame_storage[32768],spill[4096];
static unsigned deferred_top,deferred_spill_top,deferred_spill_capacity,deferred_count;
static unsigned char* deferred_spill;static DeferredPart* deferred_first;static DeferredPart* deferred_last;
static bool frame_ready,stream_aborted,draining_parts,source_draws_finished;
static unsigned frame,fx_frame,fx_count,fx_new_loads,fx_culled,fx_capped,fx_dropped,fx_missing,fx_queued,fx_peak,frame_queue_peak,nquad;
static float re4dc_ui_sx=.5f,re4dc_ui_sy=.5f,fog_far;
static Entry entries[3];static unsigned fake_packet_calls,fake_identity_calls;
static float fake_fog(){return fog_far;}static float (*re4dc_fog_gate_far)()=fake_fog;
static bool same_image(const Re4dcUiImage& a,const Re4dcUiImage& z){return a.pixels==z.pixels && a.palette==z.palette && a.width==z.width && a.height==z.height && a.format==z.format && a.palette_format==z.palette_format && a.palette_bytes==z.palette_bytes;}
static unsigned image_size(const Re4dcUiImage& s){return s.width*s.height*2;}
static bool image_key(const Re4dcUiImage&,Key& k){++fake_identity_calls;k={1,2};return true;}
static void fx_packet(const Re4dcEffectSprite& s,Entry*,unsigned char* out){++fake_packet_calls;std::memset(out,0,kSpritePacket);std::memcpy(out,&s.color,sizeof(s.color));}
#include "../port/dreamcast/game/platform/include/native_effect_haze_batch.inc"
static Re4dcEffectSprite sprites[12];
static void setup(){
    ++frame;fx_frame=frame;frame_ready=true;stream_aborted=draining_parts=source_draws_finished=false;
    deferred_top=sizeof(frame_storage);deferred_spill=nullptr;deferred_spill_top=deferred_spill_capacity=deferred_count=0;
    deferred_first=deferred_last=nullptr;fx_count=fx_culled=fx_capped=fx_dropped=fx_missing=fx_queued=fx_peak=frame_queue_peak=nquad=0;
    fake_packet_calls=fake_identity_calls=0;fog_far=0;tabin::fill_haze=tabin::fill_fx=0;
    entries[0]={true,{1,2},0};entries[1]=entries[2]={};
    for(unsigned n=0;n<12;++n){auto& s=sprites[n];s={};s.image={(void*)2,nullptr,128,128,5,0xffffffffU,0};
        for(unsigned i=0;i<4;++i){s.x[i]=20+float(i*3);s.y[i]=30+float(i*3);s.z[i]=.001f;s.u[i]=s.v[i]=float(i&1);}
        s.color=0x20202020U+n;s.src=4;s.dst=5;s.pad=2;
    }
}
static void empty(){assert(!deferred_first && !deferred_last && !deferred_count && !fake_packet_calls && !fx_queued);}
int main(){unsigned submitted=999;
    setup();assert(re4dc_effect_haze_batch(sprites,12,&submitted)==1 && submitted==12);assert(fake_packet_calls==12 && fx_count==12 && entries[0].frame==frame);
    assert(deferred_top==sizeof(frame_storage)-12*(kSpriteNode+kSpritePacket));unsigned n=0;
    for(auto* p=deferred_first;p;p=p->next,++n){assert(p->lighting==kSpriteTag && !p->changed[0]);unsigned color;std::memcpy(&color,(unsigned char*)p+kSpriteNode,4);assert(color==0x20202020U+n);}
    assert(n==12 && !deferred_last->next && tabin::fill_haze==1200 && sprites[0].x[0]==10);
    setup();sprites[11].x[3]=NAN;assert(!re4dc_effect_haze_batch(sprites,12,&submitted) && submitted==0);empty();assert(deferred_top==sizeof(frame_storage));
    setup();sprites[11].image.width=64;assert(!re4dc_effect_haze_batch(sprites,12,&submitted));empty();
    setup();sprites[11].src=1;assert(!re4dc_effect_haze_batch(sprites,12,&submitted));empty();
    setup();fx_count=53;assert(!re4dc_effect_haze_batch(sprites,12,&submitted));empty();assert(fx_count==53);
    setup();deferred_top=16384;assert(!re4dc_effect_haze_batch(sprites,12,&submitted));empty();assert(deferred_top==16384);
    setup();deferred_top=16384;deferred_spill=spill;deferred_spill_capacity=deferred_spill_top=sizeof(spill);
    assert(re4dc_effect_haze_batch(sprites,12,&submitted) && submitted==12 && deferred_top==16384 && deferred_spill_top==sizeof(spill)-12*(kSpriteNode+kSpritePacket));
    setup();entries[0].valid=false;assert(!re4dc_effect_haze_batch(sprites,12,&submitted));empty();assert(deferred_top==sizeof(frame_storage));
    setup();source_draws_finished=true;assert(!re4dc_effect_haze_batch(sprites,12,&submitted));empty();
    setup();frame_ready=false;assert(!re4dc_effect_haze_batch(sprites,12,&submitted));empty();
    setup();stream_aborted=true;assert(!re4dc_effect_haze_batch(sprites,12,&submitted));empty();
    setup();draining_parts=true;assert(!re4dc_effect_haze_batch(sprites,12,&submitted));empty();
    setup();for(auto& s:sprites)s.color=0;assert(re4dc_effect_haze_batch(sprites,12,&submitted) && !submitted);empty();assert(!fake_identity_calls && fx_culled==12);
    setup();for(auto& s:sprites)for(float& x:s.x)x=-100;assert(re4dc_effect_haze_batch(sprites,12,&submitted) && !submitted);empty();
    setup();fog_far=500;assert(re4dc_effect_haze_batch(sprites,12,&submitted) && !submitted);empty();
    setup();sprites[1].color=sprites[5].color=0;assert(re4dc_effect_haze_batch(sprites,12,&submitted) && submitted==10 && fx_queued==10 && fx_culled==2);
    setup();assert(re4dc_effect_haze_batch(nullptr,0,&submitted) && !submitted);empty();assert(!re4dc_effect_haze_batch(sprites,13,&submitted));empty();
    std::puts("PASS actual batch: whole queue/cap/identity preflight, resident-only texture, pre-existing spill, 12/10/0 quads, final-invalid rollback, no partial packet calls; source-finished rejection.");
}
