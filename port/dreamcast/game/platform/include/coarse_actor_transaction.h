#pragma once
#include "coarse_source_frame.h"
#include "coarse_actor_preflight.h"
#include "actor_native_owner.h"
#include "coarse_actor_geometry_once.h"
class cModel;
class cModelInfo;

// Source-only candidate; RE4DC_ACTOR_TRANSACTION remains default zero.
// Certificate rows must describe the reviewed SOURCE material/TPL identities,
// not only the replacement atlas. Missing certificates decline before owners.
struct Re4dcActorMaterialCertificate {
    unsigned appearance,role,parts,material_crc,material_fnv,texture_crc,texture_fnv;
};
struct Re4dcActorPlannedRun {
    unsigned role=0,material=0,immutable_asset_id=0,triangles=0;
    re4dc_source::ByteSpan uv{},stream{};
};
struct Re4dcActorPlan {
    unsigned count=0,appearance=0,palette_bytes=0,workspace_bytes=0;
    cModelInfo* info[8]{}; // role indexed; source list order is retained separately
    re4dc_source::ChunkInput input[8]{};
    Re4dcUiImage image{};
    unsigned crc=0,fnv=0;
    int (*palettes)(cModel*,const Re4dcActorPlan&,float* const*)=nullptr;
    // Palette/skin ownership remains role-indexed. Runs never allocate palettes.
    unsigned immutable_asset_id[8]{};
    unsigned material_count=0,run_count=0;
    Re4dcActorOwnedMaterial materials[kRe4dcActorMaterials]{};
    Re4dcActorPlannedRun runs[kRe4dcActorRuns]{};
};
extern "C" {
int re4dc_actor_plan_leon(cModel*,Re4dcActorPlan*);
int re4dc_actor_plan_ganado(cModel*,Re4dcActorPlan*);
// This callback is the explicit, currently unpopulated source certificate
// boundary. It may only return one after comparing every original info's
// material and source TPL identity to a reviewed private certificate row.
int re4dc_actor_material_certificate(cModel*,const Re4dcActorPlan*);
// Exact original opaque hand/accessory descriptor, owned and unchanged.
int re4dc_actor_source_material(cModel*,cModelInfo*,unsigned appearance,unsigned role,Re4dcActorOwnedMaterial*);
// Implementation routing capability only, not proof of exact alpha coverage,
// lighting, current source ownership or visual acceptance.
unsigned re4dc_actor_material_runs_capability(const Re4dcActorPlan*);
int re4dc_actor_transaction_draw(cModel*);
void re4dc_actor_transaction_retire();
// Trans owns these guards. A ticket never exports a borrowed ledger address.
int re4dc_actor_transaction_identity(cModel*,re4dc_source::FrameIdentity*,re4dc_source::ModelIdentity*);
int re4dc_actor_transaction_choice(cModel*,unsigned*);
int re4dc_actor_transaction_choose(cModel*,unsigned);
int re4dc_actor_transaction_candidate(cModel*);
}

namespace re4dc_actor {
inline bool exact_infos(cModelInfo* first,cModelInfo* const* roles,unsigned n) {
    unsigned seen=0,count=0;
    for(auto* p=first;p;p=p->pList) {
        if(count++==n)return false;
        unsigned k=0;for(;k<n && roles[k]!=p;++k){}
        if(k==n || (seen&(1u<<k)))return false;
        seen|=1u<<k;
    }
    return count==n && seen==(1u<<n)-1;
}
template<class Chunk> inline void plan_chunk(Re4dcActorPlan& p,unsigned role,cModelInfo* info,
    const Chunk& c,const re4dc_source::ChunkInput& input) {
    p.info[role]=info;p.input[role]=input;
    const unsigned palette=(c.palette_count*48u+31u)&~31u;
    const unsigned skin=(c.palette_count*114u+31u)&~31u;
    p.palette_bytes+=palette;
    if(skin>p.workspace_bytes)p.workspace_bytes=skin;
}
}
#define RE4DC_OWNER_SPAN(a) {reinterpret_cast<const unsigned char*>(a),sizeof(a)}
#define RE4DC_OWNER_INPUT(ns,prefix,c,bones) \
    re4dc_source::ChunkInput{RE4DC_OWNER_SPAN(ns::prefix##_pos),RE4DC_OWNER_SPAN(ns::prefix##_nrm), \
    RE4DC_OWNER_SPAN(ns::prefix##_uv),RE4DC_OWNER_SPAN(ns::prefix##_gx),RE4DC_OWNER_SPAN(ns::prefix##_weights), \
    c.position_count,c.normal_count,c.palette_count,c.triangles,bones}
