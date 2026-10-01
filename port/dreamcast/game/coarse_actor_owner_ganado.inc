// Appended to coarse_ganado_cast.cpp. Original adapter remains unchanged off.
#if RE4DC_ACTOR_TRANSACTION
#include "coarse_actor_transaction.h"
#include "actor_lifetime.h"
#include "ganado_source_extras.h"
namespace {
unsigned owner_binding_revision[32]{};
unsigned char owner_info_count[32]{};
unsigned short owner_source_bin[32][5]{};
cModelInfo* owner_extra_info[32]{};
unsigned owner_current_slot;
// Lane crowd far tier: far chunks use their own immutable asset IDs (coarse_actor_geometry_once.inc grows by 20
// under RE4DC_CROWD_FAR). owner_plan_app is the tier appearance (a, or a + kApps) of the last plan.
constexpr unsigned kOwnerFarAsset=47u;
unsigned owner_plan_app;
inline unsigned owner_tier_app(const Re4dcActorPlan& p) {
#if RE4DC_CROWD_FAR
    return p.immutable_asset_id[0]>=kOwnerFarAsset?p.appearance+kApps:p.appearance;
#else
    return p.appearance;
#endif
}
bool owner_ganado_bind(cModel* m) {
    if(!m || m->id<0x10 || m->id>0x20 || m->nParts!=kBones ||
       !m->pList || (m->be_flag&0x4000))return false;
    unsigned count=0;
    for(auto* i=m->pModelInfo;i;i=i->pList)if(++count>5)return false;
    if(count<4)return false;
    const unsigned revision=re4dc_actor_binding_revision(m);if(!revision)return false;
    bound=nullptr;unsigned slot=32;
    for(unsigned k=0;k<32;++k) {
        auto& b=bindings[k];
        if(b.owner==m && b.serial==m->serial && b.list==m->pList &&
           owner_binding_revision[k]==revision && owner_info_count[k]==count){bound=&b;slot=k;break;}
    }
    cModelInfo* infos[5]{};
    if(bound) {
        if(!re4dc_actor_role_bindings(m,bound->appearance,infos,count))return false;
        for(unsigned r=0;r<4;++r)if(infos[r]!=bound->infos[r])return false;
        if(count==5 && infos[4]!=owner_extra_info[slot])return false;
    } else {
        unsigned app=0;
        while(app<kApps && !re4dc_actor_role_bindings(m,app,infos,count))++app;
        if(app==kApps)return false;
        slot=replacement++%32;auto& b=bindings[slot];b={};owner_binding_revision[slot]=0;
        owner_info_count[slot]=0;owner_extra_info[slot]=nullptr;
        auto* part=m->pList;
        for(unsigned k=0;k<kBones;++k){if(!part)return false;b.parts[k]=part;part=part->pList;}
        if(part)return false;
        for(unsigned k=0;k<kBones;++k) {
            const int parent=gc::parents[k];
            const cCoord* want=parent<0?(const cCoord*)m:(const cCoord*)b.parts[parent];
            if(b.parts[k]->pParent!=want)return false;
            for(unsigned row=0;row<3;++row)for(unsigned col=0;col<3;++col)
                if(__builtin_fabsf(b.parts[k]->lt_inv_mat[row][col]-gc::bind[app][k][row*4+col])>.001f)return false;
        }
        for(unsigned r=0;r<count;++r) {
            const unsigned bin=re4dc_actor_role_source_bin(m,infos[r],app,r);
            if(!bin || bin>65535)return false;
            // A reviewed body/head and exact source-selected hand/attachment.
            if((r==2 && bin!=448 && bin!=451) || (r==3 && bin!=453 && bin!=456) ||
               (r==4 && bin!=467 && bin!=484))return false;
            owner_source_bin[slot][r]=(unsigned short)bin;
        }
        b.owner=m;b.serial=m->serial;b.list=m->pList;b.appearance=app;
        for(unsigned r=0;r<4;++r)b.infos[r]=infos[r];
        owner_extra_info[slot]=count==5?infos[4]:nullptr;owner_info_count[slot]=(unsigned char)count;
        owner_binding_revision[slot]=revision;bound=&b;
    }
    // Current source pointers/owner revisions are checked even on a binding hit.
    for(unsigned r=0;r<count;++r)
        if(re4dc_actor_role_source_bin(m,infos[r],bound->appearance,r)!=owner_source_bin[slot][r])return false;
    for(unsigned i=0;i<kBones;++i)for(unsigned j=0;j<12;++j)
        if(!coarse_finite((&bound->parts[i]->lt_inv_mat[0][0])[j]) ||
           !coarse_finite((&bound->parts[i]->mat[0][0])[j]))return false;
    owner_current_slot=slot;return true;
}
const ganado_extra::Chunk* owner_original_chunk(unsigned role) {
    const unsigned bin=owner_source_bin[owner_current_slot][role];
    if((role==2 && bin==451) || (role==3 && bin==456) || role==4)return ganado_extra::find(bin);
    return nullptr;
}
int owner_ganado_palettes(cModel* m,const Re4dcActorPlan& p,float* const* output) {
    if(!owner_ganado_bind(m) || bound->appearance!=p.appearance || p.count!=owner_info_count[owner_current_slot] || !skin_init(owner_tier_app(p)))return 0;
    for(unsigned i=0;i<p.count;++i)
        if(p.info[i]!=(i<4?bound->infos[i]:owner_extra_info[owner_current_slot]) || !output[i])return 0;
    Mtx inv;if(!PSMTXInverse(m->pParts->mat,inv))return 0;
    alignas(32) float invx[16];coarse_inv_xmtrx(inv,invx);
    const unsigned a=p.appearance,ta=owner_tier_app(p);
    // Extra source palettes may reference bones absent from the reduced body.
    // Only those actors evaluate all34 matrices; default actors retain the set.
    bool extra=false;for(unsigned i=2;i<p.count;++i)extra|=owner_original_chunk(i)!=nullptr;
    const unsigned used=extra?kBones:skin_used[ta];
    for(unsigned u=0;u<used;++u) {
        const unsigned b=extra?u:skin_bone[ta][u];
        skin_jobs[u]={&bound->parts[b]->mat[0][0],&gc::bind[a][b][0],bone_T[b]};
    }
    re4dc_coarse_skin_bones(invx,skin_jobs,used);
    for(unsigned i=0;i<p.count;++i) {
        const auto* source=owner_original_chunk(i);
        const unsigned palettes=source?source->palette_count:cast_chunk(ta,i).palette_count;
        if(p.input[i].palette_count!=palettes)return 0;
        if(source)re4dc_coarse_skin_groups(source->groups,source->group_count,&bone_T[0][0],output[i],palettes);
        else re4dc_coarse_skin_groups(skin_stream+skin_first[ta][i],skin_groups[ta][i],&bone_T[0][0],output[i],palettes);
        for(unsigned j=0;j<palettes*12;++j)if(!coarse_finite(output[i][j]))return 0;
    }
    return 1;
}
bool owner_add_source_material(cModel* m,Re4dcActorPlan& p,unsigned role,unsigned& index) {
    Re4dcActorOwnedMaterial mat{};
    if(!re4dc_actor_source_material(m,p.info[role],p.appearance,role,&mat))return false;
    for(unsigned k=1;k<p.material_count;++k) {
        const auto& t=p.materials[k];
        if(t.crc==mat.crc && t.fnv==mat.fnv && t.image.width==mat.image.width && t.image.height==mat.image.height &&
           t.image.format==mat.image.format && t.wrap_s==mat.wrap_s && t.wrap_t==mat.wrap_t) {index=k;return true;}
    }
    if(p.material_count==kRe4dcActorMaterials)return false;
    index=p.material_count++;p.materials[index]=mat;return true;
}
}
#if RE4DC_CROWD_FAR
extern "C" int re4dc_crowd_far(cModel*);  // coarse_actor_transaction.inc
#endif
#if RE4DC_CROWD
// Lane crowd (crowd.mk CROWD_CULL; render only, exact): the owner path's whole-actor form of COARSE_PREGATE. Called
// right after re4dc_actor_plan_ganado bound m. 1 when every visible chunk is provably outside one of the actor path's
// culling planes (gate_cull_once: per-bone balls from the cast chunk's own positions and weights), so
// re4dc_actor_submit_owned_runs would emit nothing for the actor. The balls cover the four cast chunks only: an actor
// with a fifth (attachment) info or an original source hand is never culled.
extern "C" int re4dc_crowd_offscreen(cModel* m) {
#if RE4DC_CROWD_CULL
    if(!bound || bound->owner!=m || owner_info_count[owner_current_slot]!=4)return 0;
    for(unsigned role=2;role<4;++role)if(owner_original_chunk(role))return 0;
    Mtx inv;if(!PSMTXInverse(m->pParts->mat,inv))return 0;
    Mtx mv[4];
    const unsigned skip=gate_cull_checked(m,owner_plan_app,bound->infos,bound->parts,inv,mv);
    return skip==gate_visible;
#else
    (void)m;return 0;
#endif
}
#endif
extern "C" int re4dc_actor_plan_ganado(cModel* m,Re4dcActorPlan* out) {
    if(!out || !owner_ganado_bind(m))return 0;
    Re4dcActorPlan p{};const unsigned a=bound->appearance,t=gc::appearance_texture[a];
    p.count=owner_info_count[owner_current_slot];p.appearance=a;p.image=image_of(t);p.crc=gc::textures[t].crc;p.fnv=gc::textures[t].fnv;p.palettes=owner_ganado_palettes;
#define RE4DC_GANADO_ROLE(app,role,prefix) re4dc_actor::plan_chunk(p,role,bound->infos[role],gc::chunks[app][role],RE4DC_OWNER_INPUT(ganadocast,prefix,gc::chunks[app][role],34))
#define RE4DC_GANADO_APP(app) \
    case app: RE4DC_GANADO_ROLE(app,0,a##app##_i0);RE4DC_GANADO_ROLE(app,1,a##app##_i1); \
              RE4DC_GANADO_ROLE(app,2,a##app##_i2);RE4DC_GANADO_ROLE(app,3,a##app##_i3);break
    owner_plan_app=a;
#if RE4DC_CROWD_FAR
    if(re4dc_crowd_far(m) && skin_init(a+kApps)) {
#define RE4DC_GANADO_FAR_ROLE(app,role,prefix) re4dc_actor::plan_chunk(p,role,bound->infos[role],gc::far::chunks[app][role],RE4DC_OWNER_INPUT(ganadocast::far,prefix,gc::far::chunks[app][role],34))
#define RE4DC_GANADO_FAR_APP(app) \
    case app: RE4DC_GANADO_FAR_ROLE(app,0,a##app##_i0);RE4DC_GANADO_FAR_ROLE(app,1,a##app##_i1); \
              RE4DC_GANADO_FAR_ROLE(app,2,a##app##_i2);RE4DC_GANADO_FAR_ROLE(app,3,a##app##_i3);break
        switch(a) { RE4DC_GANADO_FAR_APP(0);RE4DC_GANADO_FAR_APP(1);RE4DC_GANADO_FAR_APP(2);RE4DC_GANADO_FAR_APP(3);RE4DC_GANADO_FAR_APP(4);default:return 0; }
#undef RE4DC_GANADO_FAR_APP
#undef RE4DC_GANADO_FAR_ROLE
        for(unsigned role=0;role<4;++role)p.immutable_asset_id[role]=kOwnerFarAsset+a*4u+role;
        const unsigned ft=far_texture(a);  // skin_init's far_same proved it is a near atlas
        p.image=image_of(ft);p.crc=gc::textures[ft].crc;p.fnv=gc::textures[ft].fnv;
        owner_plan_app=a+kApps;
    } else
#endif
    {
    switch(a) { RE4DC_GANADO_APP(0);RE4DC_GANADO_APP(1);RE4DC_GANADO_APP(2);RE4DC_GANADO_APP(3);RE4DC_GANADO_APP(4);default:return 0; }
    for(unsigned role=0;role<4;++role)p.immutable_asset_id[role]=9u+a*4u+role;
    }
#undef RE4DC_GANADO_APP
#undef RE4DC_GANADO_ROLE
    p.material_count=1;p.materials[0].image=p.image;p.materials[0].crc=p.crc;p.materials[0].fnv=p.fnv;
    for(unsigned role=0;role<p.count;++role) {
        if(const auto* source=owner_original_chunk(role)) {
            if(role<4)p.palette_bytes-=(p.input[role].palette_count*48u+31u)&~31u;
            auto* info=role<4?bound->infos[role]:owner_extra_info[owner_current_slot];
            re4dc_actor::plan_chunk(p,role,info,*source,source->input);p.immutable_asset_id[role]=source->asset_id;
        }
        auto& run=p.runs[p.run_count++];run.role=role;run.immutable_asset_id=p.immutable_asset_id[role];
        run.triangles=p.input[role].triangles;run.uv=p.input[role].uv;run.stream=p.input[role].stream;
        if(owner_original_chunk(role) && !owner_add_source_material(m,p,role,run.material))return 0;
    }
    // One optional six-entry source accessory adds at most288 palette bytes.
    if(p.palette_bytes>7776 || p.workspace_bytes>13696)return 0;
    *out=p;return 1;
}
#endif
