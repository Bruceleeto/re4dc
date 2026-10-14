#include "../src/game/ps2_fx_population.h"
#include <cassert>
#include <cstring>
#include <cstdio>
#include <cmath>
struct Slot { bool active; ps2fx::PopulationKey key; };
struct Reader {
    const Slot* slots;
    unsigned* calls;
    bool operator()(unsigned i, ps2fx::PopulationKey& key) const {
        ++*calls;
        if (!slots[i].active) return false;
        key = slots[i].key;
        return true;
    }
};
static ps2fx::PopulationKey key(unsigned source, unsigned target, unsigned recipe = 0) {
    ps2fx::PopulationKey k = {12, 0, (unsigned short)recipe, 0,
        (unsigned short)source, (unsigned short)target, 0xd0, 5};
    return k;
}
static Slot slots[ps2fx::Population::MaxSlots], saved[ps2fx::Population::MaxSlots];
static ps2fx::Population pop;
static void fill(unsigned n, unsigned source, unsigned target, unsigned recipe = 0, unsigned start = 0) {
    for (unsigned i = 0; i < n; ++i) { slots[start+i].active = true; slots[start+i].key = key(source,target,recipe); }
}
static void run(unsigned n) {
    unsigned calls = 0;
    std::memcpy(saved, slots, sizeof(slots));
    Reader read = {slots, &calls};
    pop.build(n, read);
    assert(std::memcmp(saved, slots, sizeof(slots)) == 0);
    assert(calls <= n);
    if (!(pop.stats.issues & (ps2fx::Population::SlotOverflow | ps2fx::Population::GroupOverflow |
            ps2fx::Population::CandidateOverflow | ps2fx::Population::BadCounts))) assert(calls == n);
}
static unsigned selected(unsigned n) { unsigned result=0; for(unsigned i=0;i<n;++i)result+=pop.state(i)==1;return result; }
static void clear() { std::memset(slots,0,sizeof(slots)); }

static void test_additions() {
    const ps2fx::HazeRecipe recipe={2000,{5,0,0},{.2f,.2f,.2f},0x118c0defU,30,145,155,155,34};
    const ps2fx::HazeCamera camera={{0,0,0},{1,0,0},{0,1,0},{0,0,1}};
    ps2fx::HazeAddition a,b;
    a.sample(false,20,1,true,false,recipe,camera,false); assert(!a.active);
    a.sample(true,21,1,true,false,recipe,camera,false);
    b.sample(true,21,1,true,false,recipe,camera,false);
    assert(a.active && a.age==1 && a.issues==0);
    for(unsigned i=0;i<a.Count;++i) {
        const ps2fx::HazeParticle& p=a.particles[i];
        assert(std::memcmp(&p,&b.particles[i],sizeof(p))==0);
        assert(p.position.x>=-3000 && p.position.x<3000);
        assert(p.position.y>=-3000 && p.position.y<3000);
        assert(p.position.z>=0 && p.position.z<5000);
        assert(p.size>=1960 && p.size<2040 && p.speed.x>=4.8f && p.speed.x<5.2f);
    }
    const ps2fx::HazeParticle initial=a.particles[0];
    a.sample(true,21,1,true,false,recipe,camera,false);
    assert(a.age==1 && std::memcmp(&initial,&a.particles[0],sizeof(initial))==0);
    a.sample(true,22,1,false,false,recipe,camera,false); assert(a.age==1);
    a.sample(true,23,1,true,true,recipe,camera,false); assert(a.age==1);
    a.sample(true,24,1,true,true,recipe,camera,false); assert(a.age==2);
    // Indoor fade reaches zero at its source duration and then recovers exactly.
    for(unsigned f=25;f<55;++f)a.sample(true,f,1,true,false,recipe,camera,true);
    assert(a.indoor_count==30 && a.alpha(recipe,3000)==0);
    for(unsigned f=55;f<85;++f)a.sample(true,f,1,true,false,recipe,camera,false);
    assert(a.indoor_count==0 && a.alpha(recipe,3000)==34);
    assert(a.alpha(recipe,500)==0 && a.alpha(recipe,5000)==0);
    assert(std::fabs(a.alpha(recipe,4250)-17)<.001f);
    assert(std::fabs(a.alpha(recipe,1750)-17)<.001f);
    // Area exit destroys only render state; reentry restarts its private seed.
    a.sample(false,85,1,true,false,recipe,camera,false);assert(!a.active);
    a.sample(true,86,1,true,false,recipe,camera,false);
    assert(a.age==1 && std::memcmp(&initial,&a.particles[0],sizeof(initial))==0);
    // Clock discontinuities are bounded and stay explicit for the activation.
    a.sample(true,89,1,true,false,recipe,camera,false);
    assert(a.age==4 && a.issues==a.MissedCameraHistory);
    a.sample(true,10000,1,true,false,recipe,camera,false);
    assert(a.age==12 && (a.issues&a.ClockOverflow));
    a.sample(true,3,1,true,false,recipe,camera,false);
    assert(a.age==1 && (a.issues&a.ClockReset));
    a.clear();a.sample(true,0xffffffffU,1,true,false,recipe,camera,false);
    a.sample(true,0,1,true,false,recipe,camera,false); assert(a.age==2 && a.issues==0);
    // Constant camera catch-up equals sequential frames; changing history is diagnosed.
    a.clear();b.clear();a.sample(true,10,1,true,false,recipe,camera,false);b.sample(true,10,1,true,false,recipe,camera,false);
    a.sample(true,14,1,true,false,recipe,camera,false);
    for(unsigned f=11;f<=14;++f)b.sample(true,f,1,true,false,recipe,camera,false);
    assert(a.age==b.age && a.size_mul==b.size_mul && std::memcmp(a.particles,b.particles,sizeof(a.particles))==0);
    ps2fx::HazeCamera shifted=camera;shifted.position.x=100000;shifted.position.y=-80000;shifted.position.z=70000;
    a.sample(true,15,1,true,false,recipe,shifted,false);
    for(unsigned i=0;i<a.Count;++i) {
        assert(a.particles[i].position.x>=97000 && a.particles[i].position.x<103000);
        assert(a.particles[i].position.y>=-83000 && a.particles[i].position.y<-77000);
        assert(a.particles[i].position.z>=70000 && a.particles[i].position.z<75000);
    }
    // Gate identity: unrelated, partial, duplicate, different-age or reused-core
    // controllers cannot qualify the four-record activation.
    const ps2fx::PopulationKey identity=key(0,0);
    ps2fx::GateEvidence g; assert(!g.finish() && g.issues==0);
    for(unsigned i=0;i<4;++i)g.add(i,identity,5,true);
    assert(g.finish() && g.clock==5 && g.issues==0);
    for(unsigned bad=0;bad<5;++bad) {
        ps2fx::GateEvidence q;
        for(unsigned i=0;i<4;++i) {
            ps2fx::PopulationKey other=identity;if(bad==0 && i==3)++other.kind;
            if(bad==1 && i==3)continue;
            q.add(bad==2 && i==3 ? 2:i,other,bad==3 && i==3 ? 6:5,!(bad==4 && i==3));
        }
        assert(!q.finish() && q.issues);
    }
    ps2fx::HazeRecipe gate=recipe;gate.indoor_frames=0;gate.seed=0x1234567fU;
    a.clear();a.sample(true,0,0,true,false,gate,camera,true);assert(a.age==0 && a.indoor_count==0);
    a.sample(true,1,1,true,false,gate,camera,true);assert(a.age==1 && a.alpha(gate,3000)==34);
    a.sample(false,0,0,true,false,gate,camera,true);assert(!a.active);
    std::printf("PS2 additions helper PASS: deterministic private particles, area exit/reentry, pause, slow, wrap, fades, repeated draws, clock bounds and gate evidence; state bytes=%zu\n",sizeof(a));
}
int main() {
    // Actual source certificate: r104 haze uses 1e; the substituted r10f source
    // also uses 1e but needs tool80. Other qualified haze uses 1f/tool0.
    const unsigned source_cases[][3]={{0x104,0,0x1e},{0x10f,0x80,0x1e},{0x102,0,0x1f},{0x200,0,0x1f}};
    for(unsigned i=0;i<4;++i) {
        const unsigned room=source_cases[i][0],tool=source_cases[i][1],texture=source_cases[i][2];
        assert(ps2fx::population_source_matches(room,0,0xfe,tool,texture,0,true));
        assert(!ps2fx::population_source_matches(room,1,0xfe,tool,texture,0,true));
        assert(!ps2fx::population_source_matches(room,0,0,tool,texture,0,true));
        assert(!ps2fx::population_source_matches(room,0,0xfe,tool^1,texture,0,true));
        assert(!ps2fx::population_source_matches(room,0,0xfe,tool,texture^1,0,true));
        assert(!ps2fx::population_source_matches(room,0,0xfe,tool,texture,1,true));
        assert(!ps2fx::population_source_matches(room,0,0xfe,tool,texture,0,false));
    }
    ps2fx::TrailPoint trail[50],gc_trail[50];
    unsigned trail_count=ps2fx::puzzle_trail(trail);
    assert(trail_count==27 && trail[0].alpha==60.0f && trail[1].alpha==60.0f);
    assert(trail[0].z==0.0f && trail[26].z==-13000.0f && trail[26].alpha>=4.0f);
    assert(trail[26].alpha*0.9000000357627869f<4.0f);
    assert(ps2fx::puzzle_trail(gc_trail,-250.0f,0.05000000447034836f,130.0f,0.9500000476837158f)==50);
    for(unsigned i=1;i<trail_count;++i) {
        assert(trail[i].z==trail[i-1].z-500.0f);
        assert(trail[i].size_mul==trail[i-1].size_mul+0.049999989569187164f);
        assert(trail[i].alpha==(i==1?trail[i-1].alpha:trail[i-1].alpha*0.9000000357627869f));
    }
    ps2fx::TrailIdentity trail_id={key(50,0),1234,2345,42};
    ps2fx::TrailEvidence evidence;evidence.clear(50);
    assert(!evidence.complete());
    for(unsigned i=0;i<49;++i)evidence.add(i,trail_id);
    assert(!evidence.complete());evidence.add(49,trail_id);assert(evidence.complete());
    evidence.add(49,trail_id);assert(!evidence.complete() && (evidence.issues&4));
    evidence.clear(50);evidence.add(50,trail_id);assert(evidence.issues&1);
    for(unsigned field=0;field<3;++field) {
        evidence.clear(50);evidence.add(0,trail_id);
        ps2fx::TrailIdentity other=trail_id;
        if(field==0)++other.parent;
        if(field==1)++other.model;
        if(field==2)++other.serial;
        evidence.add(1,other);assert(evidence.issues&2);
    }
    evidence.clear(1);evidence.add(0,trail_id);assert(evidence.complete());
    evidence.clear(1);assert(!evidence.complete()); // every render pass/reentry resets ownership

    // Independent world-coordinate reconstruction verifies anchor preservation:
    // scaling around a screen centroid would fail the E9 Cy=1/128 case.
    const float anchors[][2]={{-0.5f,-0.5f},{-0.5f,1.0f/128.0f-1.0f}};
    for(unsigned anchor=0;anchor<2;++anchor) for(unsigned corner=0;corner<4;++corner) {
        const float x=(corner==1 || corner==2)?1.0f:0.0f,y=corner<2?1.0f:0.0f;
        for(unsigned axis=0;axis<3;++axis) {
            const float rx=(float)(axis+1)*13.0f,ry=(float)(axis+2)*-7.0f,origin=123.0f;
            const float old=origin+rx*(x+anchors[anchor][0])+ry*(y+anchors[anchor][1]);
            const float expected=origin+rx*1.7f*(x+anchors[anchor][0])+ry*1.2f*(y+anchors[anchor][1]);
            const float actual=old+ps2fx::anchored_corner_delta(rx,ry,.7f,.2f,x,y,anchors[anchor][0],anchors[anchor][1]);
            assert(actual-expected<0.0001f && expected-actual<0.0001f);
            assert(ps2fx::anchored_corner_delta(rx,ry,.7f,.2f,-anchors[anchor][0],-anchors[anchor][1],anchors[anchor][0],anchors[anchor][1])==0.0f);
        }
    }

    test_additions();
    // Exhaustive count boundaries cover zero, undersupply, full and target=source.
    for (unsigned source=1; source<=256; ++source) {
        for (unsigned target=0; target<=source; ++target) {
            clear(); fill(source,source,target); run(source);
            assert(pop.stats.issues==0 && selected(source)==target);
            assert(pop.stats.selected==target && pop.state(source)==-1);
        }
    }
    clear(); run(0); assert(pop.stats.groups==0 && pop.state(0)==-1);
    clear(); run(2048); assert(pop.stats.issues==0 && pop.stats.candidates==0);
    run(2049); assert(pop.stats.issues==ps2fx::Population::SlotOverflow && pop.state(0)==-1);
    clear(); fill(7,59,10); run(20);
    assert(selected(20)==7 && pop.stats.issues==ps2fx::Population::PartialSource);
    // Sparse allocation and interleaved independent groups remain exact and repeatable.
    clear();
    for(unsigned i=0;i<59;++i) { slots[3*i].active=true;slots[3*i].key=key(59,10); }
    for(unsigned i=0;i<51;++i) { slots[3*i+1].active=true;slots[3*i+1].key=key(51,11,1); }
    run(2048); assert(pop.stats.selected==21 && pop.stats.groups==2);
    int states[2048]; for(unsigned i=0;i<2048;++i)states[i]=pop.state(i);
    run(2048); for(unsigned i=0;i<2048;++i)assert(states[i]==pop.state(i));
    // Each immutable emitter identity field separates otherwise matching groups.
    for(unsigned field=0;field<5;++field) {
        clear();fill(59,59,10);fill(59,59,10,0,59);
        for(unsigned i=59;i<118;++i) {
            if(field==0)++slots[i].key.call;
            if(field==1)++slots[i].key.core;
            if(field==2)++slots[i].key.flags;
            if(field==3)++slots[i].key.owner;
            if(field==4)++slots[i].key.kind;
        }
        run(118);assert(pop.stats.groups==2 && selected(118)==20 && pop.stats.issues==0);
    }
    clear(); fill(60,59,10); fill(10,10,7,1,100); run(120);
    assert(pop.stats.issues==ps2fx::Population::AmbiguousSource && pop.stats.fallback==60);
    assert(pop.state(0)==-1 && selected(120)==7);
    clear(); for(unsigned i=0;i<33;++i)fill(1,1,1,i,i);run(33);
    assert(pop.stats.issues==ps2fx::Population::GroupOverflow && selected(33)==0);
    clear();fill(256,256,10);fill(1,1,1,1,256);run(257);
    assert(pop.stats.issues==ps2fx::Population::CandidateOverflow && selected(257)==0);
    clear();fill(1,0,0);run(1);assert(pop.stats.issues==ps2fx::Population::BadCounts);
    clear();fill(1,10,11);run(1);assert(pop.stats.issues==ps2fx::Population::BadCounts);
    // Rebuilding after a room/pool change must discard the previous selection.
    clear();fill(53,53,12);run(53);clear();run(53);assert(pop.stats.selected==0 && pop.state(52)==-1);
    std::printf("PS2 population helper PASS: exhaustive counts, sparse groups, identity, bounds, fallback, source immutability; state bytes=%zu\n",sizeof(pop));
}
