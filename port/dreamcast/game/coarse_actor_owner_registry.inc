// NATIVE_MODEL_REGISTRY (native_model_registry.mk; render only): generic native models on the ACTOR_TRANSACTION owner
// path. Included once by coarse_actor_owner_leon.inc, before the geometry-once table and the transaction.
// Input: native_model_registry.h from a private bundle (tools/d367/model_registry.py): per descriptor the source
// model id, the pack's own bone count, parents and inverse bind, one chunk per source info (source info order),
// each chunk's texture package, and the source identity rows (native_model_registry_*.inc, merged into
// actor_material_records.inc) that the lifetime/material proofs check. Nothing is matched by model id alone: an
// actor plans a descriptor only when the archive adoption proof binds EVERY info of the actor to that descriptor's
// exact source BIN + TPL rows (re4dc_actor_role_bindings), its skeleton has the descriptor's bone count and parents
// and its rest rotations equal the descriptor's inverse bind. The plan then goes through the unchanged transaction:
// layout, semantics (live info state, immutable chunk proof), the material certificate (registry branch in
// coarse_actor_material.inc), the shared palette/workspace/skin/texture leases and the source pass order.
// Any failure before the first TA header keeps the whole actor on the source path (counted by reason below).
// =1 draws admitted actors; =2 (compare) runs the same admission and the palette build into a scratch buffer, then
// keeps the source path (no native TA submission): "NMR" lines count would-admit and every decline reason.
#include "native_model_registry.h"
#include "coarse_skin.h"
#if RE4DC_COARSE_SKIN_FTRV != 1
#error NATIVE_MODEL_REGISTRY builds its palettes with COARSE_SKIN_FTRV=1
#endif
static_assert(nmr::descriptor_count && nmr::descriptor_count<=32 && nmr::chunk_count && nmr::max_bones<=256,"registry bundle shape");
static_assert(nmr::texture_count<=64,"registry textures");
extern "C" unsigned re4dc_ui_frame();
// NATIVE_MODEL_REGISTRY_CENSUS (diagnostic, default 0): the decline-reason counters, bind deviation maxima and the
// scene census below exist only in census builds; a production / cost build has none of their storage or work.
#if RE4DC_NATIVE_MODEL_REGISTRY_CENSUS
#define NMR_CENSUS(...) __VA_ARGS__
#else
#define NMR_CENSUS(...)
#endif
#define NMR_WHY(x) NMR_CENSUS(registry_why=(x))
namespace {
// Immutable asset IDs after the transaction's fixed table (coarse_actor_geometry_once.inc).
#if RE4DC_CROWD_FAR
constexpr unsigned kRegistryAsset0=66u+1u;
#else
constexpr unsigned kRegistryAsset0=46u+1u;
#endif
constexpr unsigned kRegistryAssetEnd=kRegistryAsset0+nmr::chunk_count;  // one past the last ID
// Decline reasons (the first failing stage of an actor whose model id has a descriptor).
enum RegistryWhy : unsigned {
    kRwNone,kRwShape,kRwRevision,kRwRoles,kRwSkeleton,kRwFinite,kRwSkin,kRwPlan,kRwLayout,kRwSemantics,
    kRwCertificate,kRwAcquire,kRwCount
};
unsigned registry_tokens[nmr::texture_count];
Re4dcUiImage registry_image(unsigned t) {
    return Re4dcUiImage{&registry_tokens[t],nullptr,nmr::textures[t].width,nmr::textures[t].height,6,0xffffffffU,0};
}
// Per-descriptor FTRV palette groups, built once from the generated weights (coarse_skin.h).
alignas(32) unsigned char registry_skin[(nmr::skin_stream_bytes+31u)&~31u];
unsigned registry_skin_first[nmr::chunk_count],registry_skin_groups[nmr::chunk_count];
unsigned char registry_skin_bone[nmr::descriptor_count][nmr::max_bones];
unsigned registry_skin_used[nmr::descriptor_count],registry_skin_state[nmr::descriptor_count],registry_skin_next;
alignas(32) float registry_T[nmr::max_bones][12];
CoarseBoneJob registry_jobs[nmr::max_bones];
// Model ids with at least one descriptor: an O(1) reject for every other actor.
unsigned registry_id_mask[8];
bool registry_mask_ready;
struct RegistryBinding {
    cModel* owner;cParts* list;const void* root;unsigned serial,revision,descriptor,count;
    cModelInfo* infos[8];cParts* parts[nmr::max_bones];
};
RegistryBinding registry_bindings[16];
unsigned registry_replace;
RegistryBinding* registry_bound;
#if RE4DC_NATIVE_MODEL_REGISTRY_CENSUS
unsigned registry_why;
// Census (cumulative since boot): per descriptor admitted / declined, per reason, the largest rest-inverse deviation
// from the descriptor's bind accepted (rotation, translation), the last planned actor's position, and the scene table.
struct RegistryCount { unsigned planned,admitted,would,declined,why[kRwCount];float bind_rotation,bind_translation,pos[3]; };
RegistryCount registry_count[nmr::descriptor_count];
unsigned registry_unbound_why[kRwCount];  // declines before a descriptor was chosen (shape / roles / skeleton)
#endif
#if RE4DC_NATIVE_MODEL_REGISTRY == 2
alignas(32) float registry_scratch[256*12];
// Compare mode: the source palette of this game frame (trans.cpp commonScreenMatSub, right after calcWeightMat) per
// registry actor, checked against inv(root) x part.mat x descriptor bind recomputed at the owner draw: equal when
// the native palettes see the same pose and bind the source skinned with.
struct RegistrySnap { const cModel* m;unsigned serial,frame,bones;float T[nmr::max_bones][12]; };
RegistrySnap registry_snaps[16];
unsigned registry_snap_next,registry_cmp_models,registry_cmp_bad,registry_cmp_nosnap;
float registry_cmp_max;
#endif
inline bool registry_id(unsigned id) {
    if(!registry_mask_ready) {
        for(const auto& d:nmr::descriptors)registry_id_mask[(d.model_id&255u)>>5]|=1u<<(d.model_id&31u);
        registry_mask_ready=true;
    }
    return id<256 && (registry_id_mask[id>>5]>>(id&31u)&1u);
}
inline const nmr::Descriptor* registry_descriptor(unsigned appearance) {
    if(appearance<nmr::appearance_first || appearance-nmr::appearance_first>=nmr::descriptor_count)return nullptr;
    return &nmr::descriptors[appearance-nmr::appearance_first];
}
bool registry_skin_init(unsigned d) {
    if(registry_skin_state[d])return registry_skin_state[d]==1;
    const auto& desc=nmr::descriptors[d];
    unsigned bytes=registry_skin_next;unsigned char used[nmr::max_bones]={};
    for(unsigned i=0;i<desc.sections;++i) {
        const auto& c=nmr::chunks[desc.first_chunk+i];
        for(unsigned j=0;j<c.palette_count;++j)for(unsigned k=0;k<c.weights[j].count;++k)
            if(c.weights[j].bone[k]>=desc.bones){registry_skin_state[d]=2;return false;}
        registry_skin_first[desc.first_chunk+i]=bytes;
        const unsigned b=coarse_group_build(c.weights,c.palette_count,registry_skin+bytes,sizeof(registry_skin)-bytes,
            &registry_skin_groups[desc.first_chunk+i],used);
        if(!b || b!=c.skin_bytes){registry_skin_state[d]=2;re4dc_log("NMR %s skin palette does not fit\n",desc.name);return false;}
        bytes+=b;
    }
    registry_skin_next=bytes;registry_skin_used[d]=0;
    for(unsigned b=0;b<desc.bones;++b)if(used[b])registry_skin_bone[d][registry_skin_used[d]++]=(unsigned char)b;
    re4dc_log("NMR skin %s bones=%u used=%u stream=%u/%u\n",desc.name,desc.bones,registry_skin_used[d],registry_skin_next,
        unsigned(sizeof(registry_skin)));
    registry_skin_state[d]=1;return true;
}
// The skeleton proof, run on EVERY bind (a cache hit included, so no skeleton / inverse-bind change depends on which
// source mutations bump re4dc_actor_binding_revision): the parts list is walked again (count = the descriptor's
// bones), every part's parent is the descriptor's, its rest inverse (lt_inv_mat, written by the source joint setup)
// equals the descriptor's inverse bind (rotation within .001, translation within kRegistryBindMm source units: the
// generated bind, from the cast's captured source rest, is what the palettes skin with), and every matrix is finite.
constexpr float kRegistryBindMm=0.1f;
bool registry_skeleton(cModel* m,RegistryBinding& b,const nmr::Descriptor& desc) {
    cParts* part=m->pList;
    for(unsigned k=0;k<desc.bones;++k){if(!part)return false;b.parts[k]=part;part=part->pList;}
    if(part)return false;
#if RE4DC_NATIVE_MODEL_REGISTRY_CENSUS
    float dr=0.0f,dt=0.0f;
#endif
    for(unsigned k=0;k<desc.bones;++k) {
        const int parent=desc.parents[k];
        const cCoord* want=parent<0?(const cCoord*)m:(const cCoord*)b.parts[parent];
        if(b.parts[k]->pParent!=want)return false;
        for(unsigned row=0;row<3;++row)for(unsigned col=0;col<4;++col) {
            const float d=__builtin_fabsf(b.parts[k]->lt_inv_mat[row][col]-desc.bind[k][row*4+col]);
            if(!(d<=(col==3?kRegistryBindMm:.001f)))return false;
#if RE4DC_NATIVE_MODEL_REGISTRY_CENSUS
            if(col==3){if(d>dt)dt=d;}else if(d>dr)dr=d;
#endif
        }
    }
    NMR_WHY(kRwFinite);
    for(unsigned i=0;i<desc.bones;++i)for(unsigned j=0;j<12;++j)
        if(!coarse_finite((&b.parts[i]->lt_inv_mat[0][0])[j]) || !coarse_finite((&b.parts[i]->mat[0][0])[j]))return false;
#if RE4DC_NATIVE_MODEL_REGISTRY_CENSUS
    auto& c=registry_count[&desc-nmr::descriptors];
    if(dr>c.bind_rotation)c.bind_rotation=dr;
    if(dt>c.bind_translation)c.bind_translation=dt;
#endif
    return true;
}
// The actor's descriptor from its adopted source infos and skeleton (sets registry_bound / registry_why). The cache
// only remembers which descriptor's role rows proved the infos (the multi-descriptor search); the role proof itself,
// the info pointers and the skeleton proof run again on every call.
bool registry_bind(cModel* m) {
    registry_bound=nullptr;NMR_WHY(kRwShape);
    if(!m || !registry_id(m->id) || !m->pList || !m->pParts || (m->be_flag&0x4000) || m->nParts>nmr::max_bones)return false;
    unsigned count=0;
    for(auto* i=m->pModelInfo;i;i=i->pList)if(++count>8)return false;
    if(!count)return false;
    NMR_WHY(kRwRevision);
    const unsigned revision=re4dc_actor_binding_revision(m);if(!revision)return false;
    RegistryBinding* b=nullptr;
    for(auto& e:registry_bindings)
        if(e.owner==m && e.serial==m->serial && e.list==m->pList && e.root==m->pParts && e.revision==revision && e.count==count){b=&e;break;}
    cModelInfo* infos[8]{};
    NMR_WHY(kRwRoles);
    if(b) {
        // Current source pointers/owner revisions are checked even on a binding hit.
        if(!re4dc_actor_role_bindings(m,nmr::descriptors[b->descriptor].appearance,infos,count))return false;
        for(unsigned i=0;i<count;++i)if(infos[i]!=b->infos[i])return false;
    } else {
        unsigned found=nmr::descriptor_count;
        for(unsigned d=0;d<nmr::descriptor_count;++d) {
            const auto& desc=nmr::descriptors[d];
            if(desc.model_id!=m->id || desc.sections!=count || desc.bones!=m->nParts)continue;
            if(!re4dc_actor_role_bindings(m,desc.appearance,infos,count))continue;
            // Two descriptors proving the same infos would be ambiguous: the generator refuses equal source
            // identities, and role rows bind an info to one TPL owner; refuse here too.
            if(found!=nmr::descriptor_count)return false;
            found=d;
        }
        if(found==nmr::descriptor_count)return false;
        const auto& desc=nmr::descriptors[found];
        if(!re4dc_actor_role_bindings(m,desc.appearance,infos,count))return false;
        b=&registry_bindings[registry_replace++%16];*b={};
        b->owner=m;b->serial=m->serial;b->list=m->pList;b->root=m->pParts;b->revision=revision;b->descriptor=found;b->count=count;
        for(unsigned i=0;i<count;++i)b->infos[i]=infos[i];
    }
    NMR_WHY(kRwSkeleton);
    if(!registry_skeleton(m,*b,nmr::descriptors[b->descriptor])){b->owner=nullptr;return false;}
    registry_bound=b;NMR_WHY(kRwNone);return true;
}
int registry_palettes(cModel* m,const Re4dcActorPlan& p,float* const* output) {
    const auto* desc=registry_descriptor(p.appearance);
    if(!desc || !registry_bind(m) || registry_bound->descriptor!=p.appearance-nmr::appearance_first ||
       p.count!=desc->sections || !registry_skin_init(registry_bound->descriptor))return 0;
    for(unsigned i=0;i<p.count;++i)if(p.info[i]!=registry_bound->infos[i] || !output[i])return 0;
    Mtx inv;if(!PSMTXInverse(m->pParts->mat,inv))return 0;
    alignas(32) float invx[16];coarse_inv_xmtrx(inv,invx);
    const unsigned d=registry_bound->descriptor;
    for(unsigned u=0;u<registry_skin_used[d];++u) {
        const unsigned b=registry_skin_bone[d][u];
        registry_jobs[u]={&registry_bound->parts[b]->mat[0][0],desc->bind[b],registry_T[b]};
    }
    re4dc_coarse_skin_bones(invx,registry_jobs,registry_skin_used[d]);
#if RE4DC_NATIVE_MODEL_REGISTRY == 2
    {
        const RegistrySnap* s=nullptr;
        for(const auto& e:registry_snaps)if(e.m==m && e.serial==unsigned(m->serial) && e.frame==unsigned(pG->Frame_cnt)){s=&e;break;}
        if(!s || s->bones!=desc->bones)++registry_cmp_nosnap;
        else {
            float worst=0.0f;
            for(unsigned b=0;b<desc->bones;++b) {
                Mtx tmp,bind,T;PSMTXConcat(inv,registry_bound->parts[b]->mat,tmp);
                for(unsigned k=0;k<12;++k)(&bind[0][0])[k]=desc->bind[b][k];
                PSMTXConcat(tmp,bind,T);
                for(unsigned k=0;k<12;++k){const float e=__builtin_fabsf((&T[0][0])[k]-s->T[b][k]);if(!(e<=worst))worst=e;}
            }
            ++registry_cmp_models;if(!(worst<=0.5f))++registry_cmp_bad;
            if(!(worst<=registry_cmp_max))registry_cmp_max=worst;
        }
    }
#endif
    for(unsigned i=0;i<p.count;++i) {
        const auto& c=nmr::chunks[desc->first_chunk+i];
        if(p.input[i].palette_count!=c.palette_count)return 0;
        re4dc_coarse_skin_groups(registry_skin+registry_skin_first[desc->first_chunk+i],registry_skin_groups[desc->first_chunk+i],
            &registry_T[0][0],output[i],c.palette_count);
        for(unsigned j=0;j<c.palette_count*12;++j)if(!coarse_finite(output[i][j]))return 0;
    }
    return 1;
}
#if RE4DC_NATIVE_MODEL_REGISTRY_CENSUS
void registry_decline(const Re4dcActorPlan* p,unsigned why) {
    const auto* desc=p?registry_descriptor(p->appearance):nullptr;
    if(desc) {auto& c=registry_count[desc-nmr::descriptors];++c.declined;++c.why[why<kRwCount?why:0];}
    else ++registry_unbound_why[why<kRwCount?why:0];
}
// Scene census: every model whose first OT pass reaches the transaction, by (id, ot_type, parts, infos) and outcome.
enum SceneClass : unsigned { kScNative,kScCrowd,kScDeclined,kScRegistryDeclined,kScAbsent,kScWould,kScCount };
const char* const kSceneName[kScCount]={"native","crowd-skip","declined","registry-declined","absent","would-native"};
struct SceneRow { unsigned short id,parts;unsigned char ot,infos,plan,pad;unsigned count[kScCount]; };
SceneRow scene_rows[48];
unsigned scene_count,scene_overflow,scene_last_frame;
unsigned short scene_room;
void scene_report(unsigned frame) {
    for(unsigned d=0;d<nmr::descriptor_count;++d) {
        const auto& c=registry_count[d];if(!c.planned && !c.declined)continue;
        re4dc_log("NMRD f=%u %s planned=%u admitted=%u would=%u declined=%u roles=%u skeleton=%u layout=%u semantics=%u certificate=%u acquire=%u skin=%u bind_rot_e6=%d bind_mm_e4=%d pos=%d,%d,%d\n",
            frame,nmr::descriptors[d].name,c.planned,c.admitted,c.would,c.declined,c.why[kRwRoles],c.why[kRwSkeleton],c.why[kRwLayout],
            c.why[kRwSemantics],c.why[kRwCertificate],c.why[kRwAcquire],c.why[kRwSkin],int(c.bind_rotation*1e6f),int(c.bind_translation*1e4f),
            int(c.pos[0]),int(c.pos[1]),int(c.pos[2]));
    }
#if RE4DC_NATIVE_MODEL_REGISTRY == 2
    re4dc_log("NMRC f=%u palette_check models=%u over_0.5=%u no_snapshot=%u max_abs_e4=%d\n",frame,registry_cmp_models,
        registry_cmp_bad,registry_cmp_nosnap,int(registry_cmp_max*1e4f));
#endif
    re4dc_log("NMRU f=%u shape=%u revision=%u roles=%u skeleton=%u finite=%u\n",frame,registry_unbound_why[kRwShape],
        registry_unbound_why[kRwRevision],registry_unbound_why[kRwRoles],registry_unbound_why[kRwSkeleton],registry_unbound_why[kRwFinite]);
    for(unsigned k=0;k<scene_count;++k) {
        const auto& r=scene_rows[k];
        re4dc_log("NMRS f=%u room=%04x id=%02x ot=%u parts=%u infos=%u plan=%c native=%u crowd=%u declined=%u registry_declined=%u absent=%u would=%u\n",
            frame,scene_room,r.id,r.ot,r.parts,r.infos,"-LGR"[r.plan&3],r.count[kScNative],r.count[kScCrowd],r.count[kScDeclined],
            r.count[kScRegistryDeclined],r.count[kScAbsent],r.count[kScWould]);
    }
    if(scene_overflow)re4dc_log("NMRS f=%u overflow=%u\n",frame,scene_overflow);
}
// plan: 0 none, 1 Leon, 2 Ganado, 3 registry
void scene_note(cModel* m,unsigned plan,unsigned cls) {
    const unsigned frame=re4dc_ui_frame();
    const unsigned short room=(unsigned short)G_ROOM_ID;
    if(room!=scene_room || frame-scene_last_frame>=600) {
        // One report per 600 UI frames and at every room change (the rows are per room).
        if(scene_count)scene_report(frame);
        if(room!=scene_room){scene_count=0;scene_overflow=0;scene_room=room;}
        scene_last_frame=frame;
    }
    unsigned infos=0;for(auto* i=m->pModelInfo;i && infos<255;i=i->pList)++infos;
    SceneRow* row=nullptr;
    for(unsigned k=0;k<scene_count;++k) {
        auto& r=scene_rows[k];
        if(r.id==m->id && r.ot==m->ot_type && r.parts==m->nParts && r.infos==infos && r.plan==plan){row=&r;break;}
    }
    if(!row) {
        if(scene_count==sizeof(scene_rows)/sizeof(scene_rows[0])){++scene_overflow;return;}
        row=&scene_rows[scene_count++];*row={};row->id=(unsigned short)m->id;row->ot=(unsigned char)m->ot_type;
        row->parts=(unsigned short)m->nParts;row->infos=(unsigned char)infos;row->plan=(unsigned char)plan;
    }
    ++row->count[cls<kScCount?cls:kScAbsent];
}
#endif
}
#if RE4DC_NATIVE_MODEL_REGISTRY == 2
extern "C" void re4dc_registry_snapshot(cModel* m,const Mtx* palette) {
    if(!m || !registry_id(m->id) || !m->nParts || m->nParts>nmr::max_bones)return;
    auto& s=registry_snaps[registry_snap_next++%16];
    s.m=m;s.serial=unsigned(m->serial);s.frame=unsigned(pG->Frame_cnt);s.bones=m->nParts;
    for(unsigned b=0;b<s.bones;++b)for(unsigned k=0;k<12;++k)s.T[b][k]=(&palette[b][0][0])[k];
    // One exact sample for host attribution (skinning the source BIN and the pack chunk with the same palette):
    // every registry actor's source palette at the first skinned game frame >= 600 (a paced build may skip 600's
    // Trans), as raw float bits.
    static unsigned dump_frame;
    if(!dump_frame && s.frame>=600)dump_frame=s.frame;
    if(s.frame==dump_frame) {
        re4dc_log("NMRP f=%u m=%08x id=%02x serial=%u pos=%d,%d,%d bones=%u\n",s.frame,unsigned(uintptr_t(m)),unsigned(m->id),s.serial,
            int(m->pos.x),int(m->pos.y),int(m->pos.z),s.bones);
        for(unsigned b=0;b<s.bones;++b) {
            unsigned u[12];__builtin_memcpy(u,s.T[b],sizeof(u));
            re4dc_log("NMRP m=%08x b=%u %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x %08x\n",unsigned(uintptr_t(m)),b,
                u[0],u[1],u[2],u[3],u[4],u[5],u[6],u[7],u[8],u[9],u[10],u[11]);
        }
    }
}
#endif
extern "C" int re4dc_actor_plan_registry(cModel* m,Re4dcActorPlan* out) {
    if(!out || !registry_bind(m)) {
        NMR_CENSUS(if(m && registry_id(m->id))registry_decline(nullptr,registry_why));
        return 0;
    }
    const unsigned d=registry_bound->descriptor;const auto& desc=nmr::descriptors[d];
    if(!registry_skin_init(d)){NMR_CENSUS(registry_decline(nullptr,kRwSkin));return 0;}
    Re4dcActorPlan p{};p.count=desc.sections;p.appearance=desc.appearance;p.palettes=registry_palettes;
    for(unsigned i=0;i<desc.sections;++i) {
        auto& c=nmr::chunks[desc.first_chunk+i];
        const re4dc_source::ChunkInput input{{c.positions,c.position_count*8u},{c.normals,c.normal_count*8u},{c.uv,c.uv_bytes},
            {c.stream,c.stream_bytes},{reinterpret_cast<const unsigned char*>(c.weights),c.palette_count*16u},
            c.position_count,c.normal_count,c.palette_count,c.triangles,desc.bones};
        re4dc_actor::plan_chunk(p,i,registry_bound->infos[i],c,input);
        p.immutable_asset_id[i]=kRegistryAsset0+desc.first_chunk+i;
        // Materials: each chunk's own texture package, shared when chunks name the same package.
        unsigned mat=0;
        while(mat<p.material_count && p.materials[mat].image.pixels!=&registry_tokens[c.texture])++mat;
        if(mat==p.material_count) {
            if(p.material_count==kRe4dcActorMaterials){NMR_CENSUS(registry_decline(&p,kRwPlan));return 0;}
            auto& m0=p.materials[p.material_count++];m0.image=registry_image(c.texture);
            m0.crc=nmr::textures[c.texture].crc;m0.fnv=nmr::textures[c.texture].fnv;
        }
        auto& run=p.runs[p.run_count++];run.role=i;run.material=mat;run.immutable_asset_id=p.immutable_asset_id[i];
        run.triangles=c.triangles;run.uv=input.uv;run.stream=input.stream;
    }
    p.image=p.materials[0].image;p.crc=p.materials[0].crc;p.fnv=p.materials[0].fnv;
    NMR_CENSUS(++registry_count[d].planned;registry_count[d].pos[0]=m->pos.x;registry_count[d].pos[1]=m->pos.y;
        registry_count[d].pos[2]=m->pos.z);
    *out=p;return 1;
}
// The certificate's registry branch: every run draws its chunk's own descriptor texture (coarse_actor_material.inc).
extern "C" int re4dc_registry_runs_match(const Re4dcActorPlan* p) {
    const auto* desc=p?registry_descriptor(p->appearance):nullptr;
    if(!desc || p->count!=desc->sections || p->run_count!=desc->sections || !p->material_count || p->material_count>kRe4dcActorMaterials)return 0;
    unsigned seen=0;
    for(unsigned j=0;j<p->run_count;++j) {
        const auto& r=p->runs[j];const auto& c=nmr::chunks[desc->first_chunk+j];
        if(r.role!=j || r.material>=p->material_count || r.immutable_asset_id!=kRegistryAsset0+desc->first_chunk+j ||
           r.triangles!=c.triangles || r.stream.data!=c.stream || r.uv.data!=c.uv)return 0;
        const auto& m=p->materials[r.material];
        if(m.image.pixels!=&registry_tokens[c.texture] || m.crc!=nmr::textures[c.texture].crc || m.fnv!=nmr::textures[c.texture].fnv ||
           m.image.width!=nmr::textures[c.texture].width || m.image.height!=nmr::textures[c.texture].height || m.image.format!=6 ||
           m.image.palette || m.image.palette_bytes || m.mask.pixels || m.material_flags || m.blend || m.depth_mode ||
           m.mask_ref!=256 || m.wrap_s || m.wrap_t)return 0;
        seen|=1u<<r.material;
    }
    return seen==(1u<<p->material_count)-1u;
}
extern "C" int re4dc_registry_model(const cModel* m,const Re4dcActorPlan* p) {
    const auto* desc=p?registry_descriptor(p->appearance):nullptr;
    return desc && m && m->id==desc->model_id && m->nParts==desc->bones && p->count==desc->sections && !m->ot_type;
}
// The entry gate (source_actor_owner_hooks.inc, re4dc_actor_transaction_candidate): a model id with a validated
// runtime descriptor (contract entries such as the crow have none) leaves the FRONT_NATIVE fast return so its OT
// callbacks reach commonModelTrans and the transaction. Id and part count only nominate (another model class can
// share an id: r103 has a 4-part id 0x21 model besides the 32-bone dog); admission is the proofs above.
extern "C" int re4dc_registry_candidate(const cModel* m) {
    if(!registry_id(m->id))return 0;
    for(const auto& d:nmr::descriptors)if(d.model_id==m->id && d.bones==m->nParts)return 1;
    return 0;
}
extern "C" unsigned re4dc_registry_sections(unsigned appearance) {
    const auto* desc=registry_descriptor(appearance);return desc?desc->sections:0;
}
extern "C" int re4dc_registry_texture_key(const Re4dcUiImage* i,unsigned* c,unsigned* f) {
    if(!i || i->format!=6 || i->palette_bytes)return 0;
    for(unsigned t=0;t<nmr::texture_count;++t) {
        if(i->pixels!=&registry_tokens[t] || i->width!=nmr::textures[t].width || i->height!=nmr::textures[t].height)continue;
        *c=nmr::textures[t].crc;*f=nmr::textures[t].fnv;return 1;
    }
    return 0;
}
