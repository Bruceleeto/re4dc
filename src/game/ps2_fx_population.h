#ifndef RE4DC_PS2_FX_POPULATION_H
#define RE4DC_PS2_FX_POPULATION_H

// Render-owned, allocation-free selection. Reader returns immutable source identity
// and counts for a live qualifying particle. No source slot is written or retained.
namespace ps2fx {
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
}
#endif