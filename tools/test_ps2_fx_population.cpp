#include "../src/game/ps2_fx_population.h"
#include <cassert>
#include <cstring>
#include <cstdio>
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
int main() {
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