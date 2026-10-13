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
}
#endif