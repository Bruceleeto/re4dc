#ifndef RE4DC_VMU_CONTEXT_H
#define RE4DC_VMU_CONTEXT_H
#include <stdint.h>

namespace re4vmu {
enum Person { Nobody, Leon, Ashley, Luis };
enum Condition { Fine, Caution, Danger, Dead };
enum Ammo { Hidden, Finite, Infinite };
enum Mode { Blank, Vitals, Companion, Call };
enum Status { Health, Follow, Wait, Help, Play, Ally };
struct Snapshot {
    bool valid, call, companion_help;
    Person player, companion;
    Condition condition;
    int hp, max_hp;
    Ammo ammo_kind;
    unsigned ammo, infection, companion_condition, generation;
};
struct View {
    Mode mode;
    Person subject, owner;
    Condition condition;
    Status status;
    int hp, max_hp;
    Ammo ammo_kind;
    unsigned ammo, infection;
    bool urgent;
};
struct Phase { unsigned beat, from_stage, reveal; bool alternate; }; // reveal 0..1000
View resolve(const Snapshot& s);
void render(const View& v, const Phase& phase, uint8_t out[192]);
// Source-state mapping helpers also exercised by host boundary tests.
unsigned infection_stage(bool injected, uint32_t scenario0, uint32_t scenario1, bool suppressed=false);
bool ammo_visible(unsigned player, uint32_t player_stat, unsigned weapon_no);
struct Animation {
    View previous;
    unsigned generation, began, growth_began, from_stage;
    bool initialized, growth;
    Phase update(const View& v, unsigned generation, unsigned now, bool reduced);
};
}
extern "C" {
void re4dc_vmu_snapshot();
void re4dc_vmu_poll();
void re4dc_vmu_reset();
void re4dc_vmu_call(int no); // -1 ends/cancels a real terminal call
void re4dc_vmu_companion(void* instance, int kind); // 2 Ashley / 3 Luis, observed after construction
void re4dc_vmu_invalidate(); // room/load: discard pending snapshots and visual epochs
void re4dc_vmu_speed(const void* frame, int enabled);
void re4dc_vmu_debug(const void* frame);
}
#endif
