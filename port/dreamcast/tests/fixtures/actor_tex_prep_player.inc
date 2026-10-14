// Host-only synthetic pl08 source owners. Actual player/material/lifetime and
// immutable-package accessor code is compiled by test_actor_tex_prep.py.
// Hand tests establish current role/TPL/material identity, NOT pose geometry.
unsigned player_inject=0;
void player_mutate(unsigned call) {
    if(call!=2)return;
    switch(player_inject) {
    case 1:++serial;break;
    case 2:++epoch;break;
    case 3:pPL->Body=reinterpret_cast<cPlBody*>(arena+0x87000);break;
    case 4:pPL->Body->pRight=links;break;
    case 5:++pl08_pack.generation;break;
    case 6:pl08_pack.published=false;break;
    case 7:archives[0].revision++;break;
    case 8:links[4].pList=links+2;break;
    case 9:pl08_pack.player_file=0;break;
    case 10:pPL=nullptr;break;
    }
}
void player_reset() {
    reset(9);player_inject=0;
    model->id=model->type=0;model->nParts=119;model->ot_type=7;model->TevScaleGroup=1;
    pPL=model;model->Body=reinterpret_cast<cPlBody*>(arena+0x86000);
    model->Body->pRight=links+5;model->Body->pLeft=links+6;gxCsScale[1]=0;
    archives[0].family=1;
    for(unsigned k=0;k<9;++k){roles[k].appearance=0x108;source_blobs[k].family=1;}
    links[3].be_flag=11;links[7].be_flag=73;
    const unsigned order[]={0,1,2,3,4,7,8,5,6};
    for(unsigned k=0;k<9;++k)links[order[k]].pList=k<8?links+order[k+1]:nullptr;
    source_model={reinterpret_cast<std::uintptr_t>(model),model->serial,0};
    pl08_pack={reinterpret_cast<void*>(128),reinterpret_cast<void*>(160),true,0x5a,7};
}
Re4dcActorTexMetadata player_expected_at(Re4dcActorTexReason reason,unsigned line) {
    Snapshot before;const auto pack=pl08_pack;source_calls=0;
    Re4dcActorTexMetadata out{99,99,99,99,99,99};
    const auto result=re4dc_player_tex_metadata(model,&source_frame,&source_model,&out);
    if(result!=unsigned(reason))std::fprintf(stderr,"player line %u expected %u got %u\n",line,unsigned(reason),result);
    check(result==unsigned(reason));
    if(!player_inject){check(before.same());check(!std::memcmp(&pack,&pl08_pack,sizeof pack));}
    if(reason!=Re4dcActorTexReason::None)check(!out.appearance&&!out.roles&&!out.owned&&!out.dry&&!out.visible_atlas_roles&&!out.package_generation);
    return out;
}
#define player_expected(reason) player_expected_at(reason,__LINE__)
int main() {
    check(mmap(arena,kArenaBytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0)==arena);
    player_reset();auto out=player_expected(Re4dcActorTexReason::None);
    check(out.appearance==0x108&&out.roles==9&&out.dry==9&&!out.owned&&out.visible_atlas_roles==0x17f&&out.package_generation==7);
    for(unsigned k=0;k<9;++k)re4dc_actor_info_adopt(links+k);
    out=player_expected(Re4dcActorTexReason::None);check(out.owned==9&&!out.dry);
    // All seven ordinary geometry roles are the exact source pl08 rows.
    for(unsigned k=0;k<9;++k)if(k!=5&&k!=6)check(actor_current_role(model,links+k,0x108,k)==roles+k);
    // Re-appended/current hands and arbitrary valid source chain order.
    player_reset();const unsigned order[]={6,8,7,4,3,2,1,0,5};model->pModelInfo=links+6;
    for(unsigned k=0;k<9;++k)links[order[k]].pList=k<8?links+order[k+1]:nullptr;
    player_expected(Re4dcActorTexReason::None);
    // Unregistered alternate grip geometry has no invented asset/geometry row.
    // Current hand identity + current owned TPL/material is the existing rule.
    player_reset();auto* grip=reinterpret_cast<ModelData*>(arena+0x88000);*grip=ModelData{};
    grip->nParts=37;grip->version=999;links[5].pData=grip;
    out=player_expected(Re4dcActorTexReason::None);check(out.dry==9);
    player_reset();model->Body->pRight=links+6;model->Body->pLeft=links+5;
    player_expected(Re4dcActorTexReason::Owner); // swapped identities but different TPLs cannot borrow the other hand's row
    player_reset();pPL=nullptr;player_expected(Re4dcActorTexReason::Model);
    player_reset();model->id=1;player_expected(Re4dcActorTexReason::Model);
    player_reset();model->type=1;player_expected(Re4dcActorTexReason::Model);
    player_reset();model->nParts=118;player_expected(Re4dcActorTexReason::Model);
    player_reset();model->ot_type=3;player_expected(Re4dcActorTexReason::Model);
    player_reset();model->TevScaleGroup=0;player_expected(Re4dcActorTexReason::Material);
    player_reset();model->Shader_type=1;player_expected(Re4dcActorTexReason::Material);
    player_reset();source_current=false;player_expected(Re4dcActorTexReason::Source);
    player_reset();change_source_after_first=true;player_expected(Re4dcActorTexReason::Changed);
    player_reset();model->serial++;player_expected(Re4dcActorTexReason::Source);
    player_reset();model->Body=nullptr;player_expected(Re4dcActorTexReason::Range);
    player_reset();model->Body=reinterpret_cast<cPlBody*>(kArena+3);player_expected(Re4dcActorTexReason::Range);
    player_reset();model->Body->pRight=model->Body->pLeft;player_expected(Re4dcActorTexReason::Chain);
    player_reset();model->Body->pRight=links;player_expected(Re4dcActorTexReason::Owner);
    player_reset();model->Body->pLeft=nullptr;player_expected(Re4dcActorTexReason::Chain);
    player_reset();links[6].pList=links;player_expected(Re4dcActorTexReason::Chain);
    player_reset();links[8].pList=links+6;player_expected(Re4dcActorTexReason::Chain); // missing current right hand is never relabeled
    player_reset();links[6].pList=reinterpret_cast<cModelInfo*>(kArena+3);player_expected(Re4dcActorTexReason::Chain);
    player_reset();roles[8].appearance=0x100;player_expected(Re4dcActorTexReason::Owner);
    player_reset();roles[8].role=1;player_expected(Re4dcActorTexReason::Row);
    player_reset();roles[9]=roles[5];role_count=10;player_expected(Re4dcActorTexReason::Row);
    player_reset();roles[9]=roles[0];role_count=10;player_expected(Re4dcActorTexReason::Row);
    player_reset();assets[8].pending=1;player_expected(Re4dcActorTexReason::Asset);
    player_reset();assets[9]=assets[8];player_expected(Re4dcActorTexReason::Asset);
    player_reset();archives[1]=archives[0];player_expected(Re4dcActorTexReason::Owner);
    player_reset();archives[0].family=2;player_expected(Re4dcActorTexReason::Owner);
    // Existing stale hand metadata is refused; the missing-hand rule cannot
    // hide stale serial, owner, section, TPL revision or source pointer data.
    player_reset();re4dc_actor_info_adopt(links+5);infos_live[0].asset_serial++;
    player_expected(Re4dcActorTexReason::Lifetime);
    player_reset();re4dc_actor_info_adopt(links+5);infos_live[0].tpl_revision++;
    player_expected(Re4dcActorTexReason::Lifetime);
    player_reset();re4dc_actor_info_adopt(links+5);infos_live[0].tpl_bytes--;
    player_expected(Re4dcActorTexReason::Lifetime);
    player_reset();re4dc_actor_info_adopt(links+5);assets[5].pending=1;
    player_expected(Re4dcActorTexReason::Lifetime);
    player_reset();re4dc_actor_info_adopt(links+5);links[5].pData=links[6].pData;
    player_expected(Re4dcActorTexReason::Lifetime);
    player_reset();re4dc_actor_info_adopt(links);infos_live[0].asset_serial++;
    player_expected(Re4dcActorTexReason::Row);
    player_reset();re4dc_actor_info_adopt(links);archives[0].revision++;
    player_expected(Re4dcActorTexReason::Lifetime);
    player_reset();word(const_cast<void*>(links[5].tpl_addr),88,123);player_expected(Re4dcActorTexReason::Owner);
    player_reset();word(const_cast<void*>(links[5].tpl_addr),44,0);player_expected(Re4dcActorTexReason::Owner);
    player_reset();links[5].uvScrollU=1;player_expected(Re4dcActorTexReason::Material);
    player_reset();links[5].be_flag|=2;player_expected(Re4dcActorTexReason::Material);
    player_reset();links[5].invisible_factor=0.5;player_expected(Re4dcActorTexReason::Material);
    player_reset();links[8].uvScrollU=1;player_expected(Re4dcActorTexReason::Material);
    player_reset();for(unsigned k=0;k<9;++k)re4dc_actor_info_adopt(links+k);
    static_cast<unsigned char*>(const_cast<void*>(links[8].pData->pParts))[11]=0x80;
    player_expected(Re4dcActorTexReason::Material); // archive=true even with record cache modes
    player_reset();for(unsigned k=0;k<9;++k)links[k].be_flag&=~8u;player_expected(Re4dcActorTexReason::Hidden);
    player_reset();for(unsigned k=0;k<9;++k)if(k!=7)links[k].be_flag&=~8u;player_expected(Re4dcActorTexReason::Hidden);
    player_reset();pl08_pack.published=false;player_expected(Re4dcActorTexReason::Owner);
    player_reset();pl08_pack.generation=0;player_expected(Re4dcActorTexReason::Owner);
    player_reset();pl08_pack.player_file=0;player_expected(Re4dcActorTexReason::Owner);
    player_reset();pl08_pack.cell=nullptr;player_expected(Re4dcActorTexReason::Owner);
    player_reset();pl08_pack.base=nullptr;player_expected(Re4dcActorTexReason::Owner);
    for(unsigned i=1;i<=10;++i){player_reset();player_inject=i;player_expected(Re4dcActorTexReason::Changed);}
    player_reset();Snapshot before;const auto pack=pl08_pack;Re4dcActorTexPick pick{};
    check(re4dc_player_tex_pick(0x108,&pick)&&pick.kind==Re4dcActorTexKind::PlayerPl08&&pick.package_generation==7);
    check(pick.crc==pl08_crc&&pick.fnv==pl08_fnv&&pick.image.pixels==pl08_image.pixels&&pick.appearances==0);
    check(!re4dc_player_tex_pick(0x100,&pick)&&!pick.image.pixels&&!pick.package_generation);
    check(!re4dc_player_tex_current(6)&&re4dc_player_tex_current(7));
    check(before.same()&&!std::memcmp(&pack,&pl08_pack,sizeof pack));
    std::printf("actor texture player: %u checks, seven geometry roles plus current hand role/TPL/material proof, pure package/lifetime state PASS\n",checks);
}
