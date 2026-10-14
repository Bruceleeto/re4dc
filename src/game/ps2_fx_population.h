#ifndef RE4DC_PS2_FX_POPULATION_H
#define RE4DC_PS2_FX_POPULATION_H

// Render-owned, allocation-free selection. Reader returns immutable source identity
// and counts for a live qualifying particle. No source slot is written or retained.
namespace ps2fx {
// Immutable source certificate shared by the runtime and host qualification.
// r104 keeps core texture 1e on both platforms; r10f replaces GC 1e with PS2 1f.
inline bool population_source_matches(unsigned room, unsigned life_max, unsigned parts,
                                      unsigned tool, unsigned texture, unsigned type, bool world_parent)
{
    const unsigned expected_tool = room == 0x10f ? 0x80U : 0U;
    const unsigned expected_texture = room == 0x104 || room == 0x10f ? 0x1eU : 0x1fU;
    return !life_max && parts == 0xfe && tool == expected_tool && texture == expected_texture && !type && world_parent;
}
// Expanding a quad around its texture anchor also handles noncentral anchors.
// row_x/y already include the source dimensions and orientation.
inline float anchored_corner_delta(float row_x,float row_y,float change_x,float change_y,
                                   float corner_x,float corner_y,float anchor_x,float anchor_y)
{
    return row_x*change_x*(corner_x+anchor_x)+row_y*change_y*(corner_y+anchor_y);
}
struct PopulationKey {
    unsigned call, core;
    unsigned short recipe, flags, source_count, target_count;
    unsigned char owner, kind;
    bool operator==(const PopulationKey& b) const
    {
        return call == b.call && core == b.core && recipe == b.recipe && flags == b.flags &&
               source_count == b.source_count && target_count == b.target_count && owner == b.owner && kind == b.kind;
    }
};
class Population {
public:
    enum { MaxSlots = 2048, MaxGroups = 32, MaxCandidates = 256 };
    enum Issue { SlotOverflow = 1, GroupOverflow = 2, CandidateOverflow = 4,
                 BadCounts = 8, AmbiguousSource = 16, PartialSource = 32 };
    struct Stats {
        unsigned slots, candidates, groups, selected, fallback, issues;
        bool operator==(const Stats& b) const
        {
            return slots == b.slots && candidates == b.candidates && groups == b.groups &&
                   selected == b.selected && fallback == b.fallback && issues == b.issues;
        }
    };
    Population() { clear(0); }
    void clear(unsigned slots)
    {
        stats.slots = slots;
        stats.candidates = stats.groups = stats.selected = stats.fallback = stats.issues = 0;
        for (unsigned i = 0; i < MaxSlots / 32; ++i) handled_[i] = selected_[i] = 0;
    }
    template <class Reader> void build(unsigned slots, const Reader& read)
    {
        clear(slots);
        if (slots > MaxSlots) { fail(SlotOverflow); return; }
        // Exactly one pool walk. The second pass visits only captured candidates.
        for (unsigned slot = 0; slot < slots; ++slot) {
            PopulationKey key;
            if (!read(slot, key)) continue;
            if (!key.source_count || key.source_count > MaxCandidates || key.target_count > key.source_count) {
                fail(BadCounts); return;
            }
            unsigned g = 0;
            for (; g < stats.groups; ++g) if (groups_[g].key == key) break;
            if (g == stats.groups) {
                if (g == MaxGroups) { fail(GroupOverflow); return; }
                groups_[g].key = key;
                groups_[g].count = groups_[g].error = 0;
                ++stats.groups;
            }
            if (stats.candidates == MaxCandidates) { fail(CandidateOverflow); return; }
            candidates_[stats.candidates].slot = (unsigned short)slot;
            candidates_[stats.candidates].group = (unsigned char)g;
            ++stats.candidates;
            ++groups_[g].count;
        }
        for (unsigned g = 0; g < stats.groups; ++g) {
            Group& group = groups_[g];
            if (group.count > group.key.source_count) {
                stats.issues |= AmbiguousSource;
                stats.fallback += group.count;
            } else if (group.count < group.key.source_count) {
                stats.issues |= PartialSource;
            }
        }
        for (unsigned i = 0; i < stats.candidates; ++i) {
            const Candidate& c = candidates_[i];
            Group& g = groups_[c.group];
            if (g.count > g.key.source_count) continue; // never silently merge repeated emitters
            const unsigned target = g.key.target_count < g.count ? g.key.target_count : g.count;
            const unsigned word = c.slot / 32, mask = 1U << (c.slot % 32);
            handled_[word] |= mask;
            g.error += target;
            if (g.error >= g.count) {
                g.error -= g.count;
                selected_[word] |= mask;
                ++stats.selected;
            }
        }
    }
    // -1: unqualified/fallback; 0: selected for omission; 1: selected for drawing.
    int state(unsigned slot) const
    {
        if (slot >= MaxSlots || !(handled_[slot / 32] & (1U << (slot % 32)))) return -1;
        return (selected_[slot / 32] & (1U << (slot % 32))) ? 1 : 0;
    }
    Stats stats;
private:
    struct Group { PopulationKey key; unsigned short count, error; } groups_[MaxGroups];
    struct Candidate { unsigned short slot; unsigned char group; } candidates_[MaxCandidates];
    unsigned handled_[MaxSlots / 32], selected_[MaxSlots / 32];
    void fail(unsigned issue)
    {
        // Failures occur before selection, so every source remains on its prior draw path.
        stats.issues |= issue;
        stats.selected = 0;
        stats.fallback = stats.candidates;
    }
};

// Source Esp0a Type0 clones before CommonMove. At life zero colour does
// not decay; later steps stop before cloning an alpha below four.
struct TrailPoint { float z, size_mul, alpha; };
inline unsigned puzzle_trail(TrailPoint* out, float speed=-500.0f, float growth=0.049999989569187164f,
                             float alpha=60.0f, float damping=0.9000000357627869f)
{
    float z=0.0f,size=1.0f;
    unsigned count=0;
    for(unsigned life=0;life<50;++life) {
        out[count].z=z;out[count].size_mul=size;out[count].alpha=alpha;++count;
        z+=speed;size+=growth;
        if(life) alpha*=damping;
        if(alpha<4.0f) break;
    }
    return count;
}
struct TrailIdentity {
    PopulationKey key;
    unsigned parent, model, serial;
    bool operator==(const TrailIdentity& b) const
    { return key==b.key && parent==b.parent && model==b.model && serial==b.serial; }
};
struct TrailEvidence {
    TrailIdentity identity;
    unsigned expected,count,mask[2],issues;
    void clear(unsigned n) { expected=n;count=mask[0]=mask[1]=issues=0; }
    void add(unsigned rank,const TrailIdentity& value)
    {
        if(!expected || expected>50 || rank>=expected) { issues|=1;return; }
        if(!count) identity=value;
        else if(!(identity==value)) issues|=2;
        const unsigned bit=1U<<(rank%32),word=rank/32;
        if(mask[word]&bit) issues|=4;
        mask[word]|=bit;++count;
    }
    bool complete() const { return count==expected && !issues; }
};

// Two source-qualified additions. This private state never points into or writes
// an effect/controller pool. Its LCG is local and never calls the engine RNG.
struct GateEvidence {
    PopulationKey key;
    unsigned count, mask, clock, issues;
    GateEvidence() : count(0), mask(0), clock(0), issues(0) {}
    void add(unsigned record, const PopulationKey& identity, unsigned age, bool prefix_valid)
    {
        if (record>=4) { issues|=0x400; return; }
        if (!count) { key=identity; clock=age; }
        if ((mask&(1U<<record)) || !(key==identity) || clock!=age || !prefix_valid) issues|=0x400;
        mask|=1U<<record; ++count;
    }
    bool finish()
    {
        if(count && (count!=4 || mask!=15)) issues|=0x800;
        return count==4 && mask==15 && !issues;
    }
};
struct HazeVec { float x, y, z; };
struct HazeCamera { HazeVec position, side, up, view; };
struct HazeRecipe {
    float size, speed[3], random_speed[3];
    unsigned seed;
    unsigned char indoor_frames, r, g, b, a;
};
struct HazeParticle { HazeVec position, speed; float size, angle, angle_step; };
class HazeAddition {
public:
    enum { Count = 10, MaxCatchup = 8 };
    enum Issue { MissedCameraHistory = 1, ClockReset = 2, ClockOverflow = 4 };
    HazeAddition() { clear(); }
    void clear() { active = false; issues = age = last_clock = indoor_count = 0; size_mul = 1.0f; size_plus = 0.009999997913837433f; }
    void start(const HazeRecipe& recipe, bool indoors)
    {
        clear(); active = true; indoor_count = indoors ? recipe.indoor_frames : 0;
        unsigned seed = recipe.seed;
        for (unsigned i = 0; i < Count; ++i) {
            HazeParticle& p = particles[i];
            // EspSeqSet consumes every random lane even when its multiplier is zero.
            next(seed); next(seed); p.position.z = 5000.0f * next(seed);
            p.position.x = 0.0f; p.position.y = 60.0f;
            p.speed.x = recipe.speed[0] + recipe.random_speed[0] * next(seed);
            p.speed.y = recipe.speed[1] + recipe.random_speed[1] * next(seed);
            p.speed.z = recipe.speed[2] + recipe.random_speed[2] * next(seed);
            next(seed); next(seed); next(seed); // zero acceleration random lanes
            next(seed); next(seed); p.angle = (180.0f * next(seed)) * (3.14f / 180.0f);
            next(seed); next(seed); p.angle_step = (0.20000000298023224f * next(seed)) * (3.14f / 180.0f);
            p.size = recipe.size + 40.0f * next(seed);
            // Esp15::SetFreeWork then adds a second, independent position jitter.
            p.position.x += 5000.0f * next(seed);
            p.position.y += 5000.0f * next(seed);
            p.position.z += 5000.0f * next(seed);
        }
    }
    // Caller supplies a read-only simulation clock and its exact current gate.
    // Repeated render passes do not advance. A bounded catch-up records missing
    // camera/indoor history rather than claiming recovered PS2 trajectory parity.
    void sample(bool enabled, unsigned clock, unsigned first_steps, bool moving,
                bool slow, const HazeRecipe& recipe, const HazeCamera& camera, bool indoors)
    {
        if (!enabled) { clear(); return; }
        unsigned steps;
        if (!active) {
            start(recipe, indoors); steps = first_steps; last_clock = clock;
        } else {
            steps = clock - last_clock;
            if (steps > 0x80000000U) {
                start(recipe, indoors); issues |= ClockReset; steps = first_steps;
            }
            last_clock = clock;
        }
        if (steps > 1) issues |= MissedCameraHistory;
        if (steps > MaxCatchup) { issues |= ClockOverflow; steps = MaxCatchup; }
        for (unsigned i = steps; i != 0; --i) {
            if (moving && (!slow || (clock - i + 1) % 3 == 0)) move(recipe, camera, indoors);
        }
    }
    float alpha(const HazeRecipe& recipe, float depth) const
    {
        float a = (float)recipe.a;
        if (recipe.indoor_frames) a *= 1.0f - (float)indoor_count / recipe.indoor_frames;
        if (depth > 3500.0f) a *= 1.0f - (depth - 3500.0f) / 1500.0f;
        if (depth < 3000.0f) {
            const float near = 1.0f - (3000.0f - depth) / 2500.0f;
            a *= near > 0.0f ? near : 0.0f;
        }
        return a > 0.0f ? a : 0.0f;
    }
    bool active;
    unsigned issues, age, last_clock, indoor_count;
    float size_mul, size_plus;
    HazeParticle particles[Count];
private:
    static float next(unsigned& seed)
    {
        seed = seed * 0x19660dU + 0x3c6ef35fU;
        // Equivalent to fRandSeed1_1's mantissa construction without type punning.
        return (float)(seed & 0x007fffffU) * (1.0f / 4194304.0f) - 1.0f;
    }
    static void wrap(HazeVec& p, const HazeCamera& c, const HazeVec& axis, bool forward)
    {
        const float d = (p.x-c.position.x)*axis.x + (p.y-c.position.y)*axis.y + (p.z-c.position.z)*axis.z;
        const float width = forward ? 5000.0f : 6000.0f;
        const int n = forward ? (d >= 0.0f ? (int)(d/width) : -(int)(-d/width)-1) :
            (d >= 0.0f ? (int)((d+3000.0f)/width) : (int)((d-3000.0f)/width));
        const float shift = -(width * (float)n);
        p.x += axis.x * shift; p.y += axis.y * shift; p.z += axis.z * shift;
    }
    void move(const HazeRecipe& recipe, const HazeCamera& camera, bool indoors)
    {
        size_mul += size_plus; size_plus *= 0.9900000095367432f;
        if (recipe.indoor_frames) {
            if (indoors && indoor_count < recipe.indoor_frames) ++indoor_count;
            else if (!indoors && indoor_count) --indoor_count;
        }
        for (unsigned i = 0; i < Count; ++i) {
            HazeParticle& p = particles[i];
            p.position.x += p.speed.x; p.position.y += p.speed.y; p.position.z += p.speed.z;
            p.angle += p.angle_step;
            wrap(p.position, camera, camera.side, false);
            wrap(p.position, camera, camera.up, false);
            wrap(p.position, camera, camera.view, true);
        }
        ++age;
    }
};
// Chapter 1 visual candidate. The legacy HazeAddition path above deliberately
// retains its existing tuple/fade arithmetic. This fixed-capacity state shares
// one raw-source recipe contract across all chapter 1 rows; it never touches an
// effect pool or the engine RNG. Source position identity is not asserted.
struct CommonHazeRecipe {
    float size, range, random_size, speed[3], random_speed[3], random_angle_step;
    float near_start, near_end;
    unsigned seed;
    unsigned char count, indoor_frames, fade_in_frames, texture, rgba[4];
};
class CommonHazeState {
public:
    enum { Capacity=12 };
    HazeParticle particles[Capacity];
    float size_mul,size_plus,base_alpha;
    unsigned short age,indoor_count;
    void start(const CommonHazeRecipe& r,bool indoors) {
        for(unsigned i=0;i<Capacity;++i)particles[i]=HazeParticle{};
        age=indoor_count=0;size_mul=1;size_plus=.009999997913837433f;
        base_alpha=r.rgba[3];indoor_count=indoors?r.indoor_frames:0;unsigned seed=r.seed;
        for(unsigned i=0;i<r.count;++i) {
            HazeParticle& q=particles[i];random(seed);random(seed);
            q.position={0,60,r.range*random(seed)};
            q.speed.x=r.speed[0]+r.random_speed[0]*random(seed);
            q.speed.y=r.speed[1]+r.random_speed[1]*random(seed);
            q.speed.z=r.speed[2]+r.random_speed[2]*random(seed);
            random(seed);random(seed);random(seed);
            random(seed);random(seed);q.angle=(180.0f*random(seed))*(3.14f/180.0f);
            random(seed);random(seed);q.angle_step=(r.random_angle_step*random(seed))*(3.14f/180.0f);
            q.size=r.size+r.random_size*random(seed);
            q.position.x+=r.range*random(seed);q.position.y+=r.range*random(seed);q.position.z+=r.range*random(seed);
        }
    }
    static float random(unsigned& seed) {
        seed=seed*0x19660dU+0x3c6ef35fU;
        return (float)(seed&0x007fffffU)*(1.0f/4194304.0f)-1.0f;
    }
    static float dot(const HazeVec& p,const HazeCamera& c,const HazeVec& v) {
        return (p.x-c.position.x)*v.x+(p.y-c.position.y)*v.y+(p.z-c.position.z)*v.z;
    }
    static void wrap(HazeVec& p,const HazeCamera& c,const HazeVec& axis,float range,bool forward) {
        const float d=dot(p,c,axis),half=range*.6f,width=forward?range:half*2.0f;
        const int n=forward?(d>=0?(int)(d/range):-(int)(-d/range)-1):
                           (d>=0?(int)((d+half)/width):(int)((d-half)/width));
        if(n) { const float shift=-(width*(float)n);p.x+=axis.x*shift;p.y+=axis.y*shift;p.z+=axis.z*shift; }
    }
    void move(const CommonHazeRecipe& r,const HazeCamera& c,bool indoors) {
        size_mul+=size_plus;size_plus*=.9900000095367432f;
        if(r.fade_in_frames && age<=r.fade_in_frames)base_alpha=(float)r.rgba[3]*((float)age/r.fade_in_frames);
        if(r.indoor_frames) {
            if(indoors && indoor_count<r.indoor_frames)++indoor_count;
            else if(!indoors && indoor_count)--indoor_count;
        }
        for(unsigned i=0;i<r.count;++i) {
            HazeParticle& q=particles[i];q.position.x+=q.speed.x;q.position.y+=q.speed.y;q.position.z+=q.speed.z;q.angle+=q.angle_step;
            wrap(q.position,c,c.side,r.range,false);wrap(q.position,c,c.up,r.range,false);wrap(q.position,c,c.view,r.range,true);
        }
        ++age;
    }
    float alpha(const CommonHazeRecipe& r,float d) const {
        float a=base_alpha;
        if(r.indoor_frames)a*=1.0f-(float)indoor_count/r.indoor_frames;
        // Work8[2] == 30. Match SetFreeWork and Esp15 operation order.
        const float ratio=1.0f-(float)(signed char)30/100.0f;
        if(d>r.range*ratio)a*=1.0f-(d-r.range*ratio)/(r.range*(1.0f-ratio));
        if(d<r.near_start) { const float n=1.0f-(r.near_start-d)/(r.near_start-r.near_end);a*=n>0?n:0; }
        return a>0?a:0;
    }
};

struct CommonHazeBinding {
    unsigned generation, call, core;
    unsigned short first_slot, recipe, flags;
    unsigned char kind, owner;
    bool operator==(const CommonHazeBinding& b) const {
        return generation==b.generation && call==b.call && core==b.core && first_slot==b.first_slot &&
               recipe==b.recipe && flags==b.flags && kind==b.kind && owner==b.owner;
    }
};
class CommonHazeClock {
public:
    enum { MaxAdvance=1025, MaxSourceTickGap=63 };
    enum Issue { MissingHistory=1, SourceRestart=2, AdvanceOverflow=4, BadInput=8,
                 ClockWitnessMismatch=16, SourceTickGap=32, UnadvancedSource=64 };
    enum { HardIssues=AdvanceOverflow|BadInput|ClockWitnessMismatch|SourceTickGap };
    CommonHazeState state;
    CommonHazeBinding binding;
    unsigned issues, source_tick;
    float source_mul, source_plus;
    unsigned short clock;
    bool active;
    CommonHazeClock() { clear(); }
    void clear() {
        binding=CommonHazeBinding{};issues=source_tick=clock=0;
        source_mul=source_plus=0;active=false;
    }
    static bool finite(float v) { return v==v && v<=3.4028234663852886e38f && v>=-3.4028234663852886e38f; }
    static bool valid(const CommonHazeRecipe& r,const HazeCamera& c,float mul,float plus) {
        if(!r.count || r.count>CommonHazeState::Capacity || !finite(r.size) || !finite(r.range) ||
           !finite(r.random_size) || !finite(r.random_angle_step) || !finite(r.near_start) || !finite(r.near_end) ||
           r.range<=0 || r.size<=0 || r.random_size<0 || r.random_size>=r.size || r.near_end<0 || r.near_start<=r.near_end ||
           !finite(mul) || !finite(plus) || mul<=0 || plus<0)return false;
        for(unsigned i=0;i<3;++i)if(!finite(r.speed[i]) || !finite(r.random_speed[i]))return false;
        const HazeVec v[4]={c.position,c.side,c.up,c.view};
        for(unsigned i=0;i<4;++i)if(!finite(v[i].x) || !finite(v[i].y) || !finite(v[i].z))return false;
        return true;
    }
    // Source age drives the private advance. Source tick only bounds an unseen
    // interval, so a whole 16-bit age cycle cannot silently look like zero work.
    // Missing camera/indoor history is explicit; no source observation hook.
    bool sample(bool enabled,const CommonHazeBinding& id,unsigned tick,unsigned short age,
                float mul,float plus,float source_initial_plus,const CommonHazeRecipe& r,const HazeCamera& c,bool indoors) {
        if(!enabled){clear();return false;}
        if(!valid(r,c,mul,plus) || !finite(source_initial_plus) || source_initial_plus<=0){issues|=BadInput;return false;}
        const bool changed=active && !(binding==id);
        const bool reset=active && (mul<source_mul || plus>source_plus);
        unsigned steps;
        if(!active || changed || reset) {
            clear();if(reset)issues|=SourceRestart;
            if(!age){issues|=UnadvancedSource;return false;}
            if(age>MaxAdvance){issues|=AdvanceOverflow;return false;}
            // A cold observer cannot assume a small u16 age is the first cycle.
            // Replay only the bounded uniform GC growth witnesses, using their
            // certified initial increment and the common source .99 damping.
            float expected_mul=1.0f,expected_plus=source_initial_plus;
            for(unsigned i=0;i<age;++i){expected_mul+=expected_plus;expected_plus*=.9900000095367432f;}
            if(mul!=expected_mul || plus!=expected_plus){issues|=ClockWitnessMismatch;return false;}
            binding=id;active=true;state.start(r,indoors);steps=age;
        } else {
            steps=(unsigned short)(age-clock);
            // 64 unseen source ticks could contain a whole u16 age cycle
            // (64 * 1025 > 65536); refuse that ambiguity even if ages match.
            if(tick-source_tick>MaxSourceTickGap)issues|=SourceTickGap;
            if(!steps && (mul!=source_mul || plus!=source_plus))issues|=ClockWitnessMismatch;
        }
        clock=age;source_tick=tick;source_mul=mul;source_plus=plus;
        if(steps>MaxAdvance)issues|=AdvanceOverflow;
        if(issues&HardIssues)return false;
        if(steps>1)issues|=MissingHistory;
        while(steps--)state.move(r,c,indoors);
        return true;
    }
};

}
#endif
