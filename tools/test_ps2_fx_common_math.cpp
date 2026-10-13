// Independent expanded source oracle against the actual shared helper and table.
// Host math qualification only; no PS2 RNG identity or runtime acceptance claim.
#include <cassert>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include "../src/game/ps2_fx_common_haze_recipes.h"
using ps2fx::HazeVec;
using ps2fx::HazeCamera;
using ps2fx::HazeParticle;
using Recipe=ps2fx::CommonHazeRecipe;
static float random_lane(unsigned& state) {
    state=state*0x19660dU+0x3c6ef35fU;
    return (float)(state&0x007fffffU)*(1.0f/4194304.0f)-1.0f;
}
static float depth(const HazeVec& p,const HazeCamera& c,const HazeVec& v) {
    return (p.x-c.position.x)*v.x+(p.y-c.position.y)*v.y+(p.z-c.position.z)*v.z;
}
using State=ps2fx::CommonHazeState;
// Expanded scalar source oracle: EspSeqSet + CommonMove + Esp15::move.
// Each source particle owns its scale and alpha; the proposed State shares those
// only because the fresh source profile proves identical lifecycle fields.
struct SourceParticle {
    float pos[3],speed[3],angle[3],angular_speed[3],size_x,size_y,mul,plus,base_alpha,alpha;
    unsigned short life,indoor_count;
};
static void source_start(SourceParticle& e,const Recipe& r,unsigned& seed,bool indoors) {
    std::memset(&e,0,sizeof(e));
    const float pos[3]={0,60,0},random_pos[3]={0,0,r.range},a[3]={0,0,180},da[3]={0,0,r.random_angle_step};
    for(unsigned j=0;j<3;++j)e.pos[j]=pos[j]+random_pos[j]*random_lane(seed);
    for(unsigned j=0;j<3;++j)e.speed[j]=r.speed[j]+r.random_speed[j]*random_lane(seed);
    for(unsigned j=0;j<3;++j)random_lane(seed);
    for(unsigned j=0;j<3;++j)e.angle[j]=a[j]*random_lane(seed);
    for(unsigned j=0;j<3;++j)e.angle[j]*=(3.14f/180.0f);
    for(unsigned j=0;j<3;++j)e.angular_speed[j]=da[j]*random_lane(seed);
    for(unsigned j=0;j<3;++j)e.angular_speed[j]*=(3.14f/180.0f);
    const float random_size=r.random_size*random_lane(seed);
    e.size_x=r.size+random_size;e.size_y=r.size+random_size;e.mul=1;e.plus=.009999997913837433f;
    e.base_alpha=e.alpha=r.rgba[3];
    for(unsigned j=0;j<3;++j)e.pos[j]+=r.range*random_lane(seed);
    if(indoors) {e.alpha=0;e.indoor_count=r.indoor_frames;}
}
static void source_move(SourceParticle& e,const Recipe& r,const HazeCamera& c,bool indoors) {
    e.alpha=e.base_alpha;
    for(unsigned j=0;j<3;++j)e.pos[j]+=e.speed[j];
    e.mul+=e.plus;e.plus*=.9900000095367432f;
    for(unsigned j=0;j<3;++j)e.angle[j]+=e.angular_speed[j];
    if(r.fade_in_frames<e.life) {e.alpha*=1.0f;assert(e.alpha>=4);}
    else if(r.fade_in_frames)e.alpha=(float)r.rgba[3]*((float)e.life/(float)r.fade_in_frames);
    ++e.life;e.base_alpha=e.alpha;
    if(r.indoor_frames) {
        if(indoors)++e.indoor_count;else if(e.indoor_count)--e.indoor_count;
        if(e.indoor_count) {
            if(e.indoor_count>=r.indoor_frames)e.indoor_count=r.indoor_frames;
            e.alpha=e.alpha*(1.0f-(float)e.indoor_count/r.indoor_frames);
        }
    }
    const HazeVec dirs[3]={c.side,c.up,c.view};const float camera[3]={c.position.x,c.position.y,c.position.z};
    float d=0;
    for(unsigned axis=0;axis<3;++axis) {
        const float v[3]={dirs[axis].x,dirs[axis].y,dirs[axis].z};
        d=(e.pos[0]-camera[0])*v[0]+(e.pos[1]-camera[1])*v[1]+(e.pos[2]-camera[2])*v[2];
        const float half=r.range*.6f;int n;
        if(axis<2)n=d>=0?(int)((d+half)/(half*2.0f)):(int)((d-half)/(half*2.0f));
        else n=d>=0?(int)(d/r.range):-(int)(-d/r.range)-1;
        if(n) {
            const float shift=axis<2?-(half*2.0f*(float)n):-(r.range*(float)n);
            for(unsigned j=0;j<3;++j)e.pos[j]+=v[j]*shift;
            if(axis==2)d=(e.pos[0]-camera[0])*v[0]+(e.pos[1]-camera[1])*v[1]+(e.pos[2]-camera[2])*v[2];
        }
    }
    const float ratio=1.0f-(float)(signed char)30/100.0f;
    if(d>r.range*ratio)e.alpha=e.alpha*(1.0f-(d-r.range*ratio)/(r.range*(1.0f-ratio)));
    if(d<r.near_start) {const float rate=1.0f-(r.near_start-d)/(r.near_start-r.near_end);e.alpha*=rate>0?rate:0;}
}
static bool equal(float a,float b) {return std::memcmp(&a,&b,sizeof(a))==0;}
static unsigned comparisons=0;
static void compare(const State& a,const SourceParticle* b,const Recipe& r,const HazeCamera& c) {
    for(unsigned i=0;i<r.count;++i) {
        const HazeParticle& p=a.particles[i];const SourceParticle& q=b[i];
        assert(equal(p.position.x,q.pos[0]) && equal(p.position.y,q.pos[1]) && equal(p.position.z,q.pos[2]));
        assert(equal(p.speed.x,q.speed[0]) && equal(p.speed.y,q.speed[1]) && equal(p.speed.z,q.speed[2]));
        assert(equal(p.angle,q.angle[2]) && equal(p.angle_step,q.angular_speed[2]));
        assert(equal(p.size,q.size_x) && equal(p.size,q.size_y) && equal(a.size_mul,q.mul) && equal(a.size_plus,q.plus));
        assert(equal(a.base_alpha,q.base_alpha) && a.age==q.life && a.indoor_count==q.indoor_count);
        if(a.age)assert(equal(a.alpha(r,depth(p.position,c,c.view)),q.alpha));
        ++comparisons;
    }
}
using Binding=ps2fx::CommonHazeBinding;
using Clock=ps2fx::CommonHazeClock;
struct Witness {
    float mul,plus;unsigned short age;
    void start(float initial){mul=1;plus=initial;age=0;}
    void advance(unsigned n){while(n--){mul+=plus;plus*=.9900000095367432f;++age;}}
};
static void test_clock(const Recipe& r,unsigned row,const HazeCamera& camera) {
    const float source_growth=kPs2CommonHaze[row].gc_initial_plus;Witness w;w.start(source_growth);w.advance(200);
    Clock x;Binding id={1,2,3,4,(unsigned short)row,0x4001,1,0xd0};
    assert(x.sample(true,id,10,w.age,w.mul,w.plus,source_growth,r,camera,false));
    State sequential;sequential.start(r,false);for(unsigned n=0;n<200;++n)sequential.move(r,camera,false);
    assert(std::memcmp(&x.state,&sequential,sizeof(State))==0);
    const State once=x.state;assert(x.sample(true,id,11,w.age,w.mul,w.plus,source_growth,r,camera,true));
    assert(std::memcmp(&once,&x.state,sizeof(State))==0);
    w.advance(1025);assert(x.sample(true,id,12,w.age,w.mul,w.plus,source_growth,r,camera,false));
    for(unsigned n=0;n<1025;++n)sequential.move(r,camera,false);
    assert(std::memcmp(&x.state,&sequential,sizeof(State))==0);
    w.advance(3775);assert(!x.sample(true,id,13,w.age,w.mul,w.plus,source_growth,r,camera,false) && (x.issues&Clock::AdvanceOverflow));
    assert(!x.sample(false,id,14,w.age,w.mul,w.plus,source_growth,r,camera,false));
    w.start(source_growth);w.advance(1);assert(x.sample(true,id,15,w.age,w.mul,w.plus,source_growth,r,camera,false));
    State first;first.start(r,false);first.move(r,camera,false);assert(std::memcmp(&x.state,&first,sizeof(first))==0);
    w.advance(1);assert(x.sample(true,id,16,w.age,w.mul,w.plus,source_growth,r,camera,false));
    w.start(source_growth);w.advance(1);assert(x.sample(true,id,17,w.age,w.mul,w.plus,source_growth,r,camera,false) && (x.issues&Clock::SourceRestart));
    assert(std::memcmp(&x.state,&first,sizeof(first))==0);
    x.clear();w.start(source_growth);
    assert(!x.sample(true,id,0,0,w.mul,w.plus,source_growth,r,camera,false) && (x.issues&Clock::UnadvancedSource));
    for(unsigned n=1;n<=65536;++n){w.advance(1);assert(x.sample(true,id,n,w.age,w.mul,w.plus,source_growth,r,camera,false));}
    assert(x.state.age==0 && !(x.issues&Clock::SourceRestart));
    // Mature wrapped cold state cannot masquerade as a newly created group.
    w.advance(1);Clock cold;
    assert(!cold.sample(true,id,65537,w.age,w.mul,w.plus,source_growth,r,camera,false) && (cold.issues&Clock::ClockWitnessMismatch));
    // A whole u16 cycle may fit in 64 source ticks when every tick prewarms.
    assert(!x.sample(true,id,65600,w.age,w.mul,w.plus,source_growth,r,camera,false) && (x.issues&Clock::SourceTickGap));
    x.clear();w.start(source_growth);w.advance(1);
    assert(x.sample(true,id,1,w.age,w.mul,w.plus,source_growth,r,camera,false));
    assert(!x.sample(true,id,2,w.age,w.mul+.1f,w.plus,source_growth,r,camera,false) && (x.issues&Clock::ClockWitnessMismatch));
    Recipe bad=r;bad.count=13;Clock invalid;
    assert(!invalid.sample(true,id,1,w.age,w.mul,w.plus,source_growth,bad,camera,false) && (invalid.issues&Clock::BadInput));
}
int main() {
    static_assert(sizeof(Recipe)==60,"recipe budget");
    const HazeCamera camera={{0,0,0},{1,0,0},{0,1,0},{0,0,1}};
    for(unsigned row=0;row<14;++row) {
        const Recipe& r=kPs2CommonHaze[row].visual;assert(r.count<=State::Capacity);
        State a;SourceParticle source[State::Capacity];unsigned seed=r.seed;
        a.start(r,false);for(unsigned i=0;i<r.count;++i)source_start(source[i],r,seed,false);
        compare(a,source,r,camera);
        for(unsigned frame=0;frame<66000;++frame) {
            HazeCamera c=camera;c.position={(float)((frame%47)*73),(float)((frame%31)*-29),(float)((frame%59)*51)};
            if(frame%101>50) {c.side={0,0,-1};c.view={1,0,0};}
            const bool indoor=frame%97<33;
            a.move(r,c,indoor);for(unsigned i=0;i<r.count;++i)source_move(source[i],r,c,indoor);
            compare(a,source,r,c);
        }
        test_clock(r,row,camera);
    }
    // Existing r118/r11c defaults retain their particle tuples and legacy alpha.
    for(unsigned gate=0;gate<2;++gate) {
        ps2fx::HazeRecipe old={2000,{5,0,0},{.2f,.2f,.2f},0x118c0defU,(unsigned char)(gate?0:30),145,155,155,34};
        Recipe r={2000,5000,40,{5,0,0},{.2f,.2f,.2f},.2f,3000,500,old.seed,10,old.indoor_frames,0,0x1f,{145,155,155,34}};
        ps2fx::HazeAddition legacy;State a;a.start(r,false);legacy.start(old,false);
        for(unsigned f=1;f<600;++f) {
            legacy.sample(true,f,1,true,false,old,camera,f%50<20);a.move(r,camera,f%50<20);
            assert(std::memcmp(a.particles,legacy.particles,sizeof(legacy.particles))==0);
            assert(a.size_mul==legacy.size_mul && a.size_plus==legacy.size_plus && a.indoor_count==legacy.indoor_count);
            // Algebraically identical fades have a few float ULP differences;
            // runtime legacy alpha must keep its existing arithmetic path.
            assert(std::fabs(a.alpha(r,4250)-legacy.alpha(old,4250))<.0001f);
        }
    }
    std::printf("PASS: 14 raw-source profiles; %u per-particle source comparisons across 66,000 steps each; camera motion, indoors, 16-bit wrap, 200/1025-step bootstrap/catch-up, pause/repeated draw, bounded overflow, exit/reentry, reuse and legacy tuples. Recipe=%zu State=%zu Binding=%zu Clock=%zu two_clocks=%zu table=%zu bytes.\n",comparisons,sizeof(Recipe),sizeof(State),sizeof(Binding),sizeof(Clock),2*sizeof(Clock),sizeof(kPs2CommonHaze));
}