// Exercise the actual guarded batch implementation with bounded native queue
// stubs. Verifies transaction/fallback, not Dreamcast packets or GPU behavior.
#include <cassert>
#include <cmath>
#include <cstdio>
#include <cstdarg>
#include <cstring>
#include <algorithm>
#include <new>
#include <initializer_list>
#define RE4DC_PS2_FX_ADDITIONS 1
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
alignas(32) static unsigned char frame_storage[32768],spill[8192];
static unsigned deferred_top,deferred_spill_top,deferred_spill_capacity,deferred_count;
static unsigned char* deferred_spill;static DeferredPart* deferred_first;static DeferredPart* deferred_last;
static bool frame_ready,stream_aborted,draining_parts,source_draws_finished;
static unsigned frame,fx_frame,fx_count,fx_new_loads,fx_culled,fx_capped,fx_dropped,fx_missing,fx_queued,fx_peak,frame_queue_peak,nquad;
static float re4dc_ui_sx=.5f,re4dc_ui_sy=.5f,fog_far;
static bool fake_image_size=true,fake_key=true;static unsigned batch_logs,batch_why;static char batch_log[512];
static Entry entries[3];static unsigned fake_packet_calls,fake_identity_calls;
static float fake_fog(){return fog_far;}static float (*re4dc_fog_gate_far)()=fake_fog;
static bool same_image(const Re4dcUiImage& a,const Re4dcUiImage& z){return a.pixels==z.pixels && a.palette==z.palette && a.width==z.width && a.height==z.height && a.format==z.format && a.palette_format==z.palette_format && a.palette_bytes==z.palette_bytes;}
static unsigned image_size(const Re4dcUiImage& s){return fake_image_size?s.width*s.height*2:0;}
static bool image_key(const Re4dcUiImage&,Key& k){++fake_identity_calls;k={1,2};return fake_key;}
static void fx_packet(const Re4dcEffectSprite& s,Entry*,unsigned char* out){++fake_packet_calls;std::memset(out,0,kSpritePacket);std::memcpy(out,&s.color,sizeof(s.color));}
extern "C" void re4dc_log(const char* format,...){
    va_list ap;va_start(ap,format);std::vsnprintf(batch_log,sizeof(batch_log),format,ap);va_end(ap);
    const char* p=std::strstr(batch_log,"why=");assert(p && std::sscanf(p,"why=%u",&batch_why)==1);++batch_logs;
}
#include "../port/dreamcast/game/platform/include/native_effect_stage1_batch.inc"
static Re4dcEffectSprite sprites[50];
static void setup(){
    ++frame;fx_frame=frame;fake_image_size=fake_key=true;re4dc_ui_sx=re4dc_ui_sy=.5f;frame_ready=true;stream_aborted=draining_parts=source_draws_finished=false;
    deferred_top=sizeof(frame_storage);deferred_spill=nullptr;deferred_spill_top=deferred_spill_capacity=deferred_count=0;
    deferred_first=deferred_last=nullptr;fx_count=fx_culled=fx_capped=fx_dropped=fx_missing=fx_queued=fx_peak=frame_queue_peak=nquad=0;
    fake_packet_calls=fake_identity_calls=0;fog_far=0;tabin::fill_haze=tabin::fill_fx=0;
    entries[0]={true,{1,2},0};entries[1]=entries[2]={};
    for(unsigned n=0;n<50;++n){auto& s=sprites[n];s={};s.image={(void*)2,nullptr,128,128,5,0xffffffffU,0};
        for(unsigned i=0;i<4;++i){s.x[i]=20+float(i*3);s.y[i]=30+float(i*3);s.z[i]=.001f;s.u[i]=s.v[i]=float(i&1);}
        s.color=0x20202020U+n;s.src=4;s.dst=1;s.pad=2;
    }
}
static void empty(){assert(!deferred_first && !deferred_last && !deferred_count && !fake_packet_calls && !fx_queued);}
static void expect_batch_refusal(unsigned why,unsigned count=50,Re4dcEffectSprite* input=sprites){
    const unsigned logs=batch_logs,top=deferred_top,spill_top=deferred_spill_top;
    const Entry textures[3]={entries[0],entries[1],entries[2]};unsigned submitted=999;
    assert(!re4dc_effect_stage1_batch(input,count,1,&submitted) && submitted==0);
    assert(batch_logs==logs+1 && batch_why==why);empty();
    assert(deferred_top==top && deferred_spill_top==spill_top && !std::memcmp(entries,textures,sizeof(entries)));
    assert(!re4dc_effect_stage1_batch(input,count,1,&submitted) && submitted==0 && batch_logs==logs+1);empty();
}
static void test_refusals(){
    const unsigned before=batch_logs;
    setup();frame_ready=false;expect_batch_refusal(1);
    setup();stream_aborted=true;expect_batch_refusal(2);
    setup();draining_parts=true;expect_batch_refusal(3);
    setup();source_draws_finished=true;expect_batch_refusal(4);
    setup();expect_batch_refusal(5,51);
    setup();expect_batch_refusal(6,1,nullptr);
    setup();sprites[49].src=1;expect_batch_refusal(7);
    setup();sprites[49].dst=5;expect_batch_refusal(8);
    setup();sprites[49].screen=1;expect_batch_refusal(9);
    setup();sprites[49].pad=1;expect_batch_refusal(10);
    setup();sprites[49].image.width=64;expect_batch_refusal(11);
    for(unsigned i=0;i<4;++i){
        setup();sprites[49].x[i]=NAN;expect_batch_refusal(12);
        setup();sprites[49].y[i]=NAN;expect_batch_refusal(13);
        setup();sprites[49].z[i]=INFINITY;expect_batch_refusal(14);
        setup();sprites[49].z[i]=0;expect_batch_refusal(15);
        setup();sprites[49].u[i]=NAN;expect_batch_refusal(16);
        setup();sprites[49].v[i]=NAN;expect_batch_refusal(17);
    }
    setup();re4dc_ui_sx=INFINITY;expect_batch_refusal(18);
    setup();re4dc_ui_sy=INFINITY;expect_batch_refusal(19);
    setup();fx_count=65;expect_batch_refusal(20);
    setup();fx_count=15;expect_batch_refusal(21);
    setup();deferred_top=16384;expect_batch_refusal(22);
    setup();deferred_top=16384;deferred_spill=spill;deferred_spill_top=16;expect_batch_refusal(23);
    setup();for(auto& x:sprites)x.image.pixels=nullptr;expect_batch_refusal(24);
    setup();for(auto& x:sprites)x.image.width=0;expect_batch_refusal(25);
    setup();for(auto& x:sprites)x.image.height=0;expect_batch_refusal(26);
    setup();for(auto& x:sprites)x.image.width=1025;expect_batch_refusal(27);
    setup();for(auto& x:sprites)x.image.height=1025;expect_batch_refusal(28);
    setup();fake_image_size=false;expect_batch_refusal(29);
    setup();fake_key=false;expect_batch_refusal(30);
    setup();entries[0].valid=false;expect_batch_refusal(31);assert(batch_logs==before+49);
}
int main(){unsigned submitted=999,cases=0;
    for(unsigned count:{0U,10U,32U,49U,50U}){
        setup();assert(re4dc_effect_stage1_batch(sprites,count,1,&submitted) && submitted==count);
        assert(fake_packet_calls==count && fx_count==count);
        assert(deferred_top==sizeof(frame_storage)-count*(kSpriteNode+kSpritePacket));unsigned n=0;
        for(auto* p=deferred_first;p;p=p->next,++n){unsigned color;std::memcpy(&color,(unsigned char*)p+kSpriteNode,4);assert(color==0x20202020U+n);}
        assert(n==count && (!deferred_last || !deferred_last->next));++cases;
    }
    test_refusals();cases+=49;
    setup();assert(!re4dc_effect_stage1_batch(sprites,0,2,&submitted) && !submitted && batch_why==32);empty();++cases;
    setup();for(auto& s:sprites)s.dst=5;
    assert(re4dc_effect_stage1_batch(sprites,10,5,&submitted) && submitted==10);++cases;
    setup();for(auto& s:sprites)s.dst=5;
    assert(!re4dc_effect_stage1_batch(sprites,11,5,&submitted) && !submitted && batch_why==5);empty();++cases;
    setup();deferred_top=16384;deferred_spill=spill;deferred_spill_capacity=deferred_spill_top=sizeof(spill);
    assert(re4dc_effect_stage1_batch(sprites,50,1,&submitted) && submitted==50 && deferred_top==16384 && deferred_spill_top==sizeof(spill)-50*(kSpriteNode+kSpritePacket));++cases;
    setup();for(auto& s:sprites)s.color=0;assert(re4dc_effect_stage1_batch(sprites,50,1,&submitted) && !submitted);empty();assert(!fake_identity_calls && fx_culled==50);++cases;
    setup();for(auto& s:sprites)for(float& x:s.x)x=-100;assert(re4dc_effect_stage1_batch(sprites,50,1,&submitted) && !submitted);empty();++cases;
    setup();fog_far=500;assert(re4dc_effect_stage1_batch(sprites,50,1,&submitted) && !submitted);empty();++cases;
    setup();for(unsigned i:{0U,31U,32U,48U,49U})sprites[i].color=0;
    assert(re4dc_effect_stage1_batch(sprites,50,1,&submitted) && submitted==45 && fx_culled==5);
    unsigned n=0;for(auto* p=deferred_first;p;p=p->next){while(n==0||n==31||n==32||n==48||n==49)++n;unsigned color;std::memcpy(&color,(unsigned char*)p+kSpriteNode,4);assert(color==0x20202020U+n++);}++cases;
    // Preserve an earlier colour and all of its queue state on later refusal.
    setup();assert(re4dc_effect_stage1_batch(sprites,32,1,&submitted) && submitted==32);
    const unsigned top=deferred_top,packets=fake_packet_calls;auto* first=deferred_first;auto* last=deferred_last;
    const Entry texture=entries[0];
    assert(!re4dc_effect_stage1_batch(sprites,50,1,&submitted) && !submitted);
    assert(fx_count==32 && deferred_count==32 && deferred_top==top && fake_packet_calls==packets && deferred_first==first && deferred_last==last && !last->next && !std::memcmp(&texture,entries,sizeof(texture)));++cases;
    // A failed first batch cannot reset frame/counters as a side effect.
    setup();fx_frame=frame-1;fx_count=44;fx_new_loads=3;sprites[49].z[3]=NAN;
    assert(!re4dc_effect_stage1_batch(sprites,50,1,&submitted) && fx_frame==frame-1 && fx_count==44 && fx_new_loads==3);empty();++cases;
    std::printf("PASS stage1 atomic batch: %u cases;0/10/32/49/50, all32 refusal codes, visible indices beyond31, prior-colour preservation, resident-only capacity, no partial packets\n",cases);
}
