#pragma once
#include "native_actor.hpp"
#include "actor_resource_lease.h"

// All handles are values. Skin backups belong to the current primitive owner.
// No pointer returned by these APIs may outlive its source FrameLedger ticket.
struct Re4dcActorWorkspaceLease { unsigned slot=0,serial=0,epoch=0,bytes=0; };
struct Re4dcActorSkinBinding {
    const void* info;
    Re4dcActorSource source;
    const float* palette;
    unsigned entries;
};
struct Re4dcActorSkinBackup {
    unsigned index;
    const void* info;
    const void* positions;
    const float* palette;
    unsigned entries,materialized;
};
struct Re4dcActorSkinLease {
    unsigned serial=0,frame=0,count=0;
    Re4dcActorSkinBackup old[8]{};
};
// Material identity is independent of the source info / its one skin palette.
// All textures are leased together before the actor can emit its first header.
constexpr unsigned kRe4dcActorMaterials=3,kRe4dcActorRuns=21;
struct Re4dcActorOwnedMaterial {
    Re4dcUiImage image{},mask{};
    unsigned crc=0,fnv=0,material_flags=0,blend=0,depth_mode=0;
    unsigned mask_ref=256,mask_same_uv=0,wrap_s=0,wrap_t=0;
};
struct Re4dcActorDrawRun { Re4dcActorChunk chunk; unsigned material; };
extern "C" {
int re4dc_actor_workspace_acquire(unsigned,Re4dcActorWorkspaceLease*);
int re4dc_actor_workspace_validate(const Re4dcActorWorkspaceLease*);
void re4dc_actor_workspace_release(Re4dcActorWorkspaceLease*);
int re4dc_actor_skin_acquire(unsigned,const Re4dcActorSkinBinding*,unsigned,Re4dcActorSkinLease*);
int re4dc_actor_skin_validate(const Re4dcActorSkinLease*);
int re4dc_actor_skin_release(Re4dcActorSkinLease*);
int re4dc_actor_owned_source(const void*,unsigned,Re4dcActorSource*);
void re4dc_actor_owner_retire();
int re4dc_actor_stream_state(Re4dcActorStreamState*);
int re4dc_actor_texture_material_validate(const Re4dcModelPart*,const Re4dcActorTextureLease*);
int re4dc_actor_preflight_owned_runs(Re4dcModelPart*,const Re4dcActorDrawRun*,unsigned,
    const Re4dcActorOwnedMaterial*,unsigned,const Re4dcActorWorkspaceLease*,const Re4dcActorSkinLease*,const Re4dcActorTextureLease*);
int re4dc_actor_submit_owned_runs(Re4dcModelPart*,const Re4dcActorDrawRun*,unsigned,
    const Re4dcActorOwnedMaterial*,unsigned,const Re4dcActorWorkspaceLease*,const Re4dcActorSkinLease*,const Re4dcActorTextureLease*);
int re4dc_actor_preflight_owned(Re4dcModelPart*,const Re4dcActorChunk*,unsigned,
    const Re4dcActorWorkspaceLease*,const Re4dcActorSkinLease*,const Re4dcActorTextureLease*);
// 0 is decline before any owned call, 1 complete synchronously, -1 frame failed.
int re4dc_actor_submit_owned(Re4dcModelPart*,const Re4dcActorChunk*,unsigned,
    const Re4dcActorWorkspaceLease*,const Re4dcActorSkinLease*,const Re4dcActorTextureLease*);
}

namespace re4dc_actor {
// Reservation reduces only transient-conversion capacity. Existing skin table
// allocations still use the high end and reuse it per info as before.
class WorkspaceReservations {
    struct Slot { unsigned serial=0,bytes=0; };
    Slot slots_[64]{};
    unsigned serial_=0,maximum_=0;
public:
    unsigned maximum()const{return maximum_;}
    bool acquire(unsigned bytes,unsigned epoch,Re4dcActorWorkspaceLease& out){
        if(!bytes || (bytes&31) || out.serial || out.slot || serial_==UINT32_MAX)return false;
        for(unsigned i=0;i<64;++i)if(!slots_[i].serial){
            slots_[i]={++serial_,bytes};out={i+1,serial_,epoch,bytes};
            if(bytes>maximum_)maximum_=bytes;return true;
        }
        return false;
    }
    bool valid(const Re4dcActorWorkspaceLease& t,unsigned epoch)const{
        return t.slot && t.slot<=64 && t.serial && t.epoch==epoch &&
            slots_[t.slot-1].serial==t.serial && slots_[t.slot-1].bytes==t.bytes;
    }
    void release(Re4dcActorWorkspaceLease& t){
        if(t.slot && t.slot<=64 && t.serial && slots_[t.slot-1].serial==t.serial){
            slots_[t.slot-1]={};maximum_=0;
            for(const auto& s:slots_)if(s.serial && s.bytes>maximum_)maximum_=s.bytes;
        }
        t={};
    }
    void retire(){for(auto& s:slots_)s={};maximum_=0;}
};
}
