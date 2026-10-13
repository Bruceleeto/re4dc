// ACTOR_TEX_PREP: included after the ordinary material/lifetime readers. This
// does not call the owner binder, READOPT, the record cache or any transaction.
#include "actor_tex_prep.h"
namespace re4dc_material { namespace tex_prep {
using namespace life;
using Reason=Re4dcActorTexReason;
bool storage(const void* p,unsigned bytes) {
    return !(reinterpret_cast<std::uintptr_t>(p)&3u) && readable(p,bytes);
}
bool archive(const Archive& o) {
    return o.key && o.revision && storage(o.base,o.bytes);
}
bool asset(const Asset& a) {
    return storage(a.data,sizeof(ModelData)) && a.archive<kArchives &&
        archive(archives[a.archive]) && current(a);
}
// A missing live Info may be proved into this stack object using the same
// asset/template/TPL closure as info_adopt. An existing but stale Info never
// falls through to the dry proof. No retire, insert, next, changed or memo.
Reason inspect(cModelInfo* p,Info& out,bool& dry) {
    dry=false;
    if(const Info* live=find_info(p)) {
        if(live->asset>=kAssets || !asset(assets[live->asset]) ||
           live->tpl_owner>=kArchives || !archive(archives[live->tpl_owner]))return Reason::Lifetime;
        out=*live;return Reason::None;
    }
#if !RE4DC_CROWD_READOPT
    return Reason::Owner; // the ordinary owner would not adopt a missing Info
#endif
    unsigned ai=kAssets;
    for(unsigned k=0;k<kAssets;++k)if(assets[k].data==p->pData) {
        if(ai!=kAssets)return Reason::Asset;
        ai=k;
    }
    if(ai==kAssets || !asset(assets[ai]))return Reason::Asset;
    const auto& a=assets[ai];Info found{};
    for(unsigned r=0;r<RE4DC_ROLE_COUNT;++r) {
        const auto& row=RE4DC_ROLE(r);bool match=false;
        if(row.appearance>=5)continue;
        for(unsigned t=0;t<RE4DC_BLOB_COUNT;++t)
            if((a.templates&(BlobMask(1u)<<t)) && RE4DC_BLOB(t).model==row.model)match=true;
        if(!match)continue;
        for(unsigned k=0;k<kArchives;++k) {
            const auto& o=archives[k];if(o.family!=2 || !archive(o))continue;
            const unsigned char* begin=nullptr;unsigned bytes=0;
            if(!entry(o,row.source_tpl,"TPL",begin,bytes) || begin!=p->tpl_addr ||
               !tpl_owned(o,begin,bytes,row))continue;
            if(found.info && (found.tpl_owner!=k || found.tpl!=begin))return Reason::Owner;
            found.info=p;found.asset=ai;found.asset_serial=a.serial;
            found.roles[r/32]|=1u<<(r%32);found.tpl_owner=k;found.tpl_revision=o.revision;
            found.tpl=begin;found.tpl_bytes=bytes;
        }
    }
    if(!found.info)return Reason::Owner;
    out=found;dry=true;return Reason::None;
}
const Role* row(const Info& i,unsigned app,unsigned role) {
    const Role* found=nullptr;
    for(unsigned r=0;r<RE4DC_ROLE_COUNT;++r) {
        const auto& candidate=RE4DC_ROLE(r);
        if(candidate.appearance!=app || candidate.role!=role || !info_current(i,r))continue;
        const auto& o=archives[i.tpl_owner];const unsigned char* begin=nullptr;unsigned bytes=0;
        if(!entry(o,candidate.source_tpl,"TPL",begin,bytes) || begin!=i.tpl || bytes!=i.tpl_bytes ||
           !tpl_owned(o,begin,bytes,candidate))return nullptr;
        if(found)return nullptr;found=&candidate;
    }
    return found;
}
} }
extern "C" int re4dc_actor_tex_lifetime(unsigned* serial,unsigned* epoch) {
    using namespace re4dc_material::life;
    if(!serial || !epoch || exhausted)return 0;
    *serial=re4dc_material::life::serial;*epoch=re4dc_material::life::epoch;return 1;
}
extern "C" unsigned re4dc_actor_tex_metadata(cModel* m,const re4dc_source::FrameIdentity* frame,
        const re4dc_source::ModelIdentity* identity,Re4dcActorTexMetadata* output) {
    using namespace re4dc_material;using namespace life;using namespace tex_prep;
    if(!output)return unsigned(Reason::Range);*output={};
    if(!storage(m,sizeof(*m)) || !frame || !identity)return unsigned(Reason::Range);
    if(!re4dc_actor_tex_source_current(m,frame,identity))return unsigned(Reason::Source);
    if(m==(cModel*)pPL || m==(cModel*)pSubEm || m->id<0x10 || m->id>0x20 || m->nParts!=34 ||
       !m->pList || (m->be_flag&0x4000) || m->ot_type)return unsigned(Reason::Model);
    if(m->pTexChg || m->Shader_type || m->CullMode || m->invisible_factor!=1.0f ||
       m->invisible_factor2!=1.0f || m->alpha_omit!=255 || m->TevScaleGroup!=0 ||
       !room_colour_scale(gxCsScale[0],true) || m->AddAmb_r || m->AddAmb_g || m->AddAmb_b)
        return unsigned(Reason::Material);
    if(exhausted)return unsigned(Reason::Lifetime);
    const unsigned first_serial=serial,first_epoch=epoch;
    cModelInfo* chain[5]{};Info records[5]{};unsigned n=0,dry_count=0;
    for(auto* p=m->pModelInfo;p;p=p->pList) {
        if(n==5 || !storage(p,sizeof(*p)) || !storage(p->pData,sizeof(ModelData)))return unsigned(Reason::Chain);
        for(unsigned k=0;k<n;++k)if(chain[k]==p)return unsigned(Reason::Chain);
        bool dry=false;const auto reason=inspect(p,records[n],dry);
        if(reason!=Reason::None)return unsigned(reason);
        chain[n++]=p;dry_count+=dry;
    }
    if(n<4)return unsigned(Reason::Chain);
    Re4dcActorTexMetadata result{};bool matched=false;Reason miss=Reason::Row;
    for(unsigned app=0;app<5;++app) {
        if((!app && n!=4) || !source_appearance_type(app,m->id,m->type))continue;
        unsigned atlas=0;bool good=true;
        for(unsigned k=0;k<n;++k) {
            const auto* r=row(records[k],app,k);
            if(!r){good=false;break;}
            if((k==2 && r->source_bin!=448 && r->source_bin!=451) ||
               (k==3 && r->source_bin!=453 && r->source_bin!=456) ||
               (k==4 && r->source_bin!=467 && r->source_bin!=484)){good=false;break;}
            Result material{Error::None,0,0,0,0};
#if RE4DC_ACTOR_MATERIAL_RECORD
            const auto error=info(chain[k],*r,material,false,true);
#else
            const auto error=info(chain[k],*r,material,false);
#endif
            if(error!=Error::None){good=false;miss=Reason::Material;break;}
            const bool native=k<2 || (k==2 && r->source_bin==448) || (k==3 && r->source_bin==453);
            if(native && (chain[k]->be_flag&8) && chain[k]->invisible_factor>0)atlas|=1u<<k;
        }
        if(!good)continue;
        if(matched)return unsigned(Reason::Row);
        result={app,n,n-dry_count,dry_count,atlas};matched=true;
    }
    if(!matched)return unsigned(miss);
    if(!result.visible_atlas_roles)return unsigned(Reason::Hidden);
    if(exhausted || serial!=first_serial || epoch!=first_epoch ||
       !re4dc_actor_tex_source_current(m,frame,identity))return unsigned(Reason::Changed);
    // Recheck the exact current chain/roles, including descriptors, after the
    // local dry proof. No source storage survives this synchronous call.
    auto* p=m->pModelInfo;
    for(unsigned k=0;k<n;++k) {
        if(p!=chain[k] || !row(records[k],result.appearance,k))return unsigned(Reason::Changed);
        p=p->pList;
    }
    if(p)return unsigned(Reason::Changed);
    *output=result;return unsigned(Reason::None);
}
