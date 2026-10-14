// Included by the read-only material preparation reader. The seven non-hand
// roles prove exact pl08 source geometry/TPL rows. Current player hands use the
// existing hand-role identity/TPL/material rule: their source pose geometry is
// not drawn by the native owner and is not claimed to match a fixed hand row.
#if RE4DC_ACTOR_PL08
namespace re4dc_material { namespace tex_prep {
const Role* player_role(unsigned role) {
    const Role* found=nullptr;
    for(unsigned r=0;r<RE4DC_ROLE_COUNT;++r) {
        const auto& candidate=RE4DC_ROLE(r);
        if(candidate.appearance!=0x108 || candidate.role!=role)continue;
        if(found)return nullptr;found=&candidate;
    }
    return found;
}
#if RE4DC_LEON_HAND_POSES
Reason player_hand(cModelInfo* p,const Role& row,Info& out,bool& dry) {
    // A stale live record must never be bypassed by the hand exception. Missing
    // records are proved locally; no geometry asset/role is invented for a grip.
    const Info* live=find_info(p);dry=!live;
    if(live) {
        if(live->asset>=kAssets || !asset(assets[live->asset]) ||
           live->tpl_owner>=kArchives || !archive(archives[live->tpl_owner]))return Reason::Lifetime;
        const auto& a=assets[live->asset];const auto& t=archives[live->tpl_owner];
        if(a.serial!=live->asset_serial || p->pData!=a.data || t.revision!=live->tpl_revision ||
           p->tpl_addr!=live->tpl || !span(t.base,t.bytes,live->tpl,live->tpl_bytes))return Reason::Lifetime;
    }
    Info proof{};
    for(unsigned k=0;k<kArchives;++k) {
        const auto& o=archives[k];if(o.family!=1 || !archive(o))continue;
        const unsigned char* begin=nullptr;unsigned bytes=0;
        if(!entry(o,row.source_tpl,"TPL",begin,bytes) || begin!=p->tpl_addr ||
           !tpl_owned(o,begin,bytes,row))continue;
        if(proof.info)return Reason::Owner;
        proof.info=p;proof.tpl_owner=k;proof.tpl_revision=o.revision;proof.tpl=begin;proof.tpl_bytes=bytes;
    }
    if(!proof.info)return Reason::Owner;
    if(live && (live->tpl_owner!=proof.tpl_owner || live->tpl!=proof.tpl || live->tpl_bytes!=proof.tpl_bytes))
        return Reason::Lifetime;
    out=live?*live:proof;return Reason::None;
}
#endif
} }
#endif
extern "C" unsigned re4dc_player_tex_metadata(cModel* m,const re4dc_source::FrameIdentity* frame,
        const re4dc_source::ModelIdentity* identity,Re4dcActorTexMetadata* output) {
    using namespace re4dc_material;using namespace life;using namespace tex_prep;
    if(!output)return unsigned(Reason::Range);*output={};
#if RE4DC_ACTOR_PL08
    if(!storage(m,sizeof(*m)) || !frame || !identity)return unsigned(Reason::Range);
    if(!re4dc_actor_tex_source_current(m,frame,identity))return unsigned(Reason::Source);
    if(m!=(cModel*)pPL || !storage(pPL,sizeof(*pPL)) || !source_appearance_type(0x108,m->id,m->type) ||
       m->nParts!=119 || !m->pList || !m->pParts || (m->be_flag&0x4000) || RE4DC_LEON_OT_BAD(m))
        return unsigned(Reason::Model);
    if(m->pTexChg || m->Shader_type || m->CullMode || m->invisible_factor!=1.0f ||
       m->invisible_factor2!=1.0f || m->alpha_omit!=255 || m->TevScaleGroup!=1 ||
       !room_colour_scale(gxCsScale[1],RE4DC_ACTOR_LEON_NATIVE_LOOK) ||
       m->AddAmb_r || m->AddAmb_g || m->AddAmb_b)return unsigned(Reason::Material);
    if(exhausted)return unsigned(Reason::Lifetime);
    Re4dcActorTexPick selected{};
    if(!re4dc_player_tex_pick(0x108,&selected))return unsigned(Reason::Owner);
    const unsigned first_serial=serial,first_epoch=epoch;
#if RE4DC_LEON_HAND_POSES
    auto* const body=pPL->Body;
    if(!storage(body,sizeof(*body)))return unsigned(Reason::Range);
    auto* const right=body->pRight;auto* const left=body->pLeft;
    if(!right || !left || right==left)return unsigned(Reason::Chain);
#endif
    cModelInfo* chain[9]{};Info records[9]{};unsigned role_at[9]{};
    unsigned n=0,seen=0,dry_count=0,visible=0;
    for(auto* p=m->pModelInfo;p;p=p->pList) {
        if(n==9 || !storage(p,sizeof(*p)) || !storage(p->pData,sizeof(ModelData)))return unsigned(Reason::Chain);
        for(unsigned k=0;k<n;++k)if(chain[k]==p)return unsigned(Reason::Chain);
        unsigned role=9;const Role* r=nullptr;bool dry=false;
#if RE4DC_LEON_HAND_POSES
        if(p==right || p==left) {
            role=p==right?5u:6u;r=player_role(role);
            if(!r)return unsigned(Reason::Row);
            const auto why=player_hand(p,*r,records[n],dry);
            if(why!=Reason::None)return unsigned(why);
            Result material{Error::None,0,0,0,0};
            if(hand_info(p,*r,material)!=Error::None)return unsigned(Reason::Material);
        } else
#endif
        {
            const auto why=inspect(p,records[n],dry,0x108);
            if(why!=Reason::None)return unsigned(why);
            for(unsigned k=0;k<9;++k) {
#if RE4DC_LEON_HAND_POSES
                if(k==5 || k==6)continue;
#endif
                if(const auto* candidate=row(records[n],0x108,k)) {
                    if(r)return unsigned(Reason::Row);r=candidate;role=k;
                }
            }
            if(!r)return unsigned(Reason::Row);
            Result material{Error::None,0,0,0,0};
#if RE4DC_ACTOR_MATERIAL_RECORD
            const auto error=info(p,*r,material,false,true);
#else
            const auto error=info(p,*r,material,false);
#endif
            if(error!=Error::None)return unsigned(Reason::Material);
        }
#if !RE4DC_LEON_HAND_POSES
        static const unsigned char order[9]={0,1,2,3,4,7,8,5,6};
        if(role!=order[n])return unsigned(Reason::Row);
#endif
        if(role>=9 || (seen&(1u<<role)))return unsigned(Reason::Row);
        seen|=1u<<role;chain[n]=p;role_at[n]=role;++n;dry_count+=dry;
        if(role!=7 && (p->be_flag&8) && p->invisible_factor>0)visible|=1u<<role;
    }
    if(n!=9 || seen!=0x1ff)return unsigned(Reason::Chain);
    if(!visible)return unsigned(Reason::Hidden);
    if(exhausted || serial!=first_serial || epoch!=first_epoch || m!=(cModel*)pPL ||
       !re4dc_actor_tex_source_current(m,frame,identity))return unsigned(Reason::Changed);
    if(m!=(cModel*)pPL || !storage(pPL,sizeof(*pPL)) || exhausted ||
       serial!=first_serial || epoch!=first_epoch)return unsigned(Reason::Changed);
#if RE4DC_LEON_HAND_POSES
    if(pPL->Body!=body || body->pRight!=right || body->pLeft!=left)return unsigned(Reason::Changed);
#endif
    auto* p=m->pModelInfo;
    for(unsigned k=0;k<n;++k) {
        if(p!=chain[k])return unsigned(Reason::Changed);
#if RE4DC_LEON_HAND_POSES
        if(role_at[k]==5 || role_at[k]==6) {
            const auto* r=player_role(role_at[k]);Info checked{};bool dry=false;
            if(!r || player_hand(p,*r,checked,dry)!=Reason::None ||
               checked.tpl_owner!=records[k].tpl_owner || checked.tpl_revision!=records[k].tpl_revision ||
               checked.tpl!=records[k].tpl || checked.tpl_bytes!=records[k].tpl_bytes)return unsigned(Reason::Changed);
        } else
#endif
        if(!row(records[k],0x108,role_at[k]))return unsigned(Reason::Changed);
        p=p->pList;
    }
    if(p || !re4dc_player_tex_current(selected.package_generation))return unsigned(Reason::Changed);
    *output={0x108,n,n-dry_count,dry_count,visible,selected.package_generation};return unsigned(Reason::None);
#else
    (void)m;(void)frame;(void)identity;return unsigned(Reason::Model);
#endif
}
