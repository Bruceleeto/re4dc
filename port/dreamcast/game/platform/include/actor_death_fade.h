#pragma once
#include "coarse_source_frame.h"
#include <cstdint>
#include <cstring>

// Default-off G1 candidate. The FIFO owns this value ticket, never a palette,
// skin lease or a pointer into the source ledger / primitive record list.
struct Re4dcActorFadeTicket {
    re4dc_source::FrameIdentity frame{};
    re4dc_source::ModelIdentity model{};
    unsigned sequence=0,queue_epoch=0;
};
struct Re4dcActorFadeReservation { void* node=nullptr;unsigned epoch=0; };
extern "C" {
// 0: ordinary pre-suppression refusal, no queue change. -1: frame failure.
int re4dc_model_actor_fade_reserve(Re4dcActorFadeReservation*);
int re4dc_model_actor_fade_cancel(Re4dcActorFadeReservation*);
int re4dc_model_actor_fade_commit(Re4dcActorFadeReservation*,const Re4dcActorFadeTicket*);
// Called synchronously at the tagged source FIFO node, inside Render's guard.
int re4dc_actor_death_fade_drain(Re4dcActorFadeTicket);
}

namespace re4dc_fade {
enum class State : unsigned { Pending,Draining,Done,Failed };
inline bool begin(State& state) {
    if(state!=State::Pending)return false;
    state=State::Draining;return true;
}
inline bool finish(State& state) {
    if(state!=State::Draining)return false;
    state=State::Done;return true;
}
inline bool same_ticket(const Re4dcActorFadeTicket& a,const Re4dcActorFadeTicket& b) {
    return a.frame==b.frame && a.model==b.model && a.sequence==b.sequence && a.queue_epoch==b.queue_epoch;
}
inline unsigned bits(float f) { unsigned u;static_assert(sizeof(u)==sizeof(f));std::memcpy(&u,&f,4);return u; }
// Use the source's evaluation order and truncating u8 conversion. The caller
// has proved finite factors in [0,1] and the unmodified source material alpha.
inline unsigned alpha(float model,float second,float info,unsigned material) {
    const float a=model*second*info;
    return static_cast<unsigned char>(static_cast<float>(material)*a);
}
// The same actual source-field reader is compiled by the owner and host tests.
// cEm's hp is read only after the caller proves the source enemy type/owner.
template<class Model> bool state_allows(const Model& m,unsigned appearance,int hp) {
    return m.kindid==0 && m.id==0x13 && (appearance==0 || appearance==3) && !m.ot_type && hp==0 &&
        m.r_no_0==3 && m.r_no_1==3 && m.r_no_2==1 && m.r_no_3==0 &&
        m.invisible_factor>0.0f && m.invisible_factor<1.0f && m.invisible_factor2==1.0f && m.alpha_omit==255;
}
}
