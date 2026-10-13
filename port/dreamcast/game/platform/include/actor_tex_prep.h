#pragma once
#include "coarse_source_frame.h"
#include "native_ui.h"
class cModel;

// Residency hints only. No source pointer, binding revision, skin, palette or
// presentation ticket leaves the synchronous completed-ledger inspection.
constexpr unsigned kRe4dcActorTexPicks=5;
enum class Re4dcActorTexReason : unsigned {
    None, Source, Range, Model, Chain, Lifetime, Asset, Owner, Row, Material,
    Hidden, Variant, Capacity, Changed, Count
};
struct Re4dcActorTexMetadata {
    unsigned appearance=0,roles=0,owned=0,dry=0,visible_atlas_roles=0;
};
struct Re4dcActorTexPick {
    Re4dcUiImage image{}; // pixels is the existing immutable bundle token
    unsigned crc=0,fnv=0,appearances=0,far=0;
};
struct Re4dcActorTexBatch {
    re4dc_source::FrameIdentity source{};
    unsigned variant=0,count=0,models=0,candidates=0,qualified=0,owned=0,dry=0;
    unsigned declined[unsigned(Re4dcActorTexReason::Count)]{};
    Re4dcActorTexPick picks[kRe4dcActorTexPicks]{};
};
extern "C" {
int re4dc_actor_tex_source_current(cModel*,const re4dc_source::FrameIdentity*,
                                 const re4dc_source::ModelIdentity*);
int re4dc_actor_tex_lifetime(unsigned*,unsigned*);
unsigned re4dc_actor_tex_metadata(cModel*,const re4dc_source::FrameIdentity*,
                                  const re4dc_source::ModelIdentity*,Re4dcActorTexMetadata*);
unsigned re4dc_ganado_tex_variant();
int re4dc_ganado_tex_picks(unsigned,unsigned,Re4dcActorTexPick*,unsigned*);
int re4dc_actor_tex_enumerate(Re4dcActorTexBatch*);
}
