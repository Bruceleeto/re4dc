#pragma once
// LEON_NATIVE_PIPE (native_model_registry.mk; default 0; render only, exact): the declarations shared by Leon's lean
// owner passes (coarse_actor_leon_pipe.inc), their native submission (native_actor_leon_pipe.inc) and the frame
// owner's in-window header change (native_ui.cpp). Included only by builds with the knob on.
#include <cstdint>
#include "native_model.h"
#include "actor_native_owner.h"

// What a material's own first direct window began with in this submission (re4dc_leon_direct_capture): the header
// words re4dc_model_packet_begin took from its texture entry's cache, the entry, the list and the header-cache key,
// and whether that begin counted a UV scale rebuild. Valid inside the submission call that captured it.
struct Re4dcLeonHeader {
    std::uint32_t words[8];
    void* entry;
    unsigned list, key, scale_rebuild, valid;
};
extern "C" {
// native_ui.cpp
int re4dc_leon_direct_capture(const Re4dcModelPart* part, Re4dcLeonHeader* out);
std::uint32_t* re4dc_leon_direct_switch(const Re4dcModelPart* part, const Re4dcLeonHeader* header, unsigned vertices,
                                        std::uint32_t* sq);
int re4dc_leon_owned_tr_idle(const Re4dcModelPart* part);
// native_actor_fast.cpp (native_actor_leon_pipe.inc)
int re4dc_leon_pipe_preflight(Re4dcModelPart* part, const Re4dcActorDrawRun* runs, unsigned n,
                              const Re4dcActorOwnedMaterial* materials, unsigned nm,
                              const Re4dcActorWorkspaceLease* workspace, const Re4dcActorSkinLease* skin,
                              const Re4dcActorTextureLease* textures, unsigned source_frame);
int re4dc_leon_pipe_submit(Re4dcModelPart* part, const Re4dcActorDrawRun* runs, unsigned n,
                           const Re4dcActorOwnedMaterial* materials, unsigned nm,
                           const Re4dcActorWorkspaceLease* workspace, const Re4dcActorSkinLease* skin,
                           const Re4dcActorTextureLease* textures, unsigned source_frame, int preflight);
}
