#pragma once
#include "actor_resource_lease.h"
class cModel;
struct Re4dcActorEarlyTicket {
    Re4dcActorTextureLease texture{};
    unsigned binding_revision=0;
};
static_assert(sizeof(Re4dcActorEarlyTicket)==12,"bounded early actor ticket");
extern "C" {
int re4dc_actor_texture_acquire_next(const Re4dcUiImage*,unsigned,unsigned,Re4dcActorTextureLease*);
int re4dc_actor_texture_validate_key(const Re4dcActorTextureLease*,unsigned,unsigned);
int re4dc_actor_early_coarse_admit(cModel*,Re4dcActorEarlyTicket*);
int re4dc_actor_early_coarse_validate(cModel*,const Re4dcActorEarlyTicket*);
void re4dc_actor_early_coarse_note_frame();
int re4dc_actor_early_proof_active(cModel*);
int re4dc_coarse_source_actor_texture(cModel*,Re4dcActorTextureLease*);
int re4dc_ganado_early_ready(cModel*);
}
