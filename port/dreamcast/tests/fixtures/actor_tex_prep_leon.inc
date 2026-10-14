// Synthetic owners; the real lifetime, material and Leon metadata readers run.
unsigned player_inject=0;
void player_mutate(unsigned call) {
    if(call!=2)return;
    switch(player_inject) {
    case 1:++serial;break;
    case 2:++epoch;break;
    case 3:pPL->Body=reinterpret_cast<cPlBody*>(arena+0x87000);break;
    case 4:pPL->Body->pRight=links;break;
    case 5:charbake_variant=1;break;
    case 6:image.width=256;break;
    case 7:archives[0].revision++;break;
    case 8:links[4].pList=links+2;break;
    case 9:crc++;break;
    case 10:pPL=nullptr;break;
    }
}
void player_reset() {
    reset(8);player_inject=0;set_variant(0);
    model->id=model->type=0;model->nParts=119;model->ot_type=7;model->TevScaleGroup=1;
    pPL=model;model->Body=reinterpret_cast<cPlBody*>(arena+0x86000);
    model->Body->pRight=links+5;model->Body->pLeft=links+6;gxCsScale[1]=0;
    archives[0].family=1;
    for(unsigned k=0;k<8;++k){roles[k].appearance=0x100;source_blobs[k].family=1;}
    links[3].be_flag=11;links[7].be_flag=73;
    const unsigned order[]={0,1,2,3,4,7,5,6};
    for(unsigned k=0;k<8;++k)links[order[k]].pList=k<7?links+order[k+1]:nullptr;
    source_model={reinterpret_cast<std::uintptr_t>(model),model->serial,0};
}
Re4dcActorTexMetadata player_expected_at(Re4dcActorTexReason reason,unsigned line) {
    Snapshot before;source_calls=0;
    const auto prior_image=image;const auto prior_crc=crc,prior_fnv=fnv,prior_variant=charbake_variant;
    Re4dcActorTexMetadata out{99,99,99,99,99,99};
    const auto result=re4dc_leon_tex_metadata(model,&source_frame,&source_model,&out);
    if(result!=unsigned(reason))std::fprintf(stderr,"Leon line %u expected %u got %u\n",line,unsigned(reason),result);
    check(result==unsigned(reason));
    if(!player_inject){check(before.same());check(!std::memcmp(&prior_image,&image,sizeof image));check(prior_crc==crc&&prior_fnv==fnv&&prior_variant==charbake_variant);}
    if(reason!=Re4dcActorTexReason::None)check(!out.appearance&&!out.roles&&!out.owned&&!out.dry&&!out.visible_atlas_roles&&!out.package_generation);
    return out;
}
#define player_expected(reason) player_expected_at(reason,__LINE__)
int main() {
    check(mmap(arena,kArenaBytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0)==arena);
    player_reset();auto out=player_expected(Re4dcActorTexReason::None);
    check(out.appearance==0x100&&out.roles==8&&out.dry==8&&!out.owned&&out.visible_atlas_roles==0x7f&&out.package_generation==1);
    for(unsigned k=0;k<8;++k)re4dc_actor_info_adopt(links+k);
    out=player_expected(Re4dcActorTexReason::None);check(out.owned==8&&!out.dry);
    for(unsigned k=0;k<8;++k)if(k!=5&&k!=6)check(actor_current_role(model,links+k,0x100,k)==roles+k);
    player_reset();const unsigned order[]={6,7,4,3,2,1,0,5};model->pModelInfo=links+6;
    for(unsigned k=0;k<8;++k)links[order[k]].pList=k<7?links+order[k+1]:nullptr;
    player_expected(Re4dcActorTexReason::None);
    player_reset();auto* grip=reinterpret_cast<ModelData*>(arena+0x88000);*grip=ModelData{};
    grip->nParts=37;grip->version=999;links[5].pData=grip;
    out=player_expected(Re4dcActorTexReason::None);check(out.dry==8);
    player_reset();model->Body->pRight=links+6;model->Body->pLeft=links+5;player_expected(Re4dcActorTexReason::Owner);
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
    player_reset();links[7].pList=links+6;player_expected(Re4dcActorTexReason::Chain);
    player_reset();links[6].pList=reinterpret_cast<cModelInfo*>(kArena+3);player_expected(Re4dcActorTexReason::Chain);
    player_reset();roles[4].appearance=0x108;player_expected(Re4dcActorTexReason::Owner);
    player_reset();for(unsigned k=0;k<8;++k)roles[k].appearance=0x108;player_expected(Re4dcActorTexReason::Owner);
    player_reset();roles[4].role=1;player_expected(Re4dcActorTexReason::Row);
    player_reset();roles[8]=roles[5];role_count=9;player_expected(Re4dcActorTexReason::Row);
    player_reset();roles[8]=roles[0];role_count=9;player_expected(Re4dcActorTexReason::Row);
    player_reset();assets[7].pending=1;player_expected(Re4dcActorTexReason::Asset);
    player_reset();assets[8]=assets[7];player_expected(Re4dcActorTexReason::Asset);
    player_reset();archives[1]=archives[0];player_expected(Re4dcActorTexReason::Owner);
    player_reset();archives[0].family=2;player_expected(Re4dcActorTexReason::Owner);
    player_reset();re4dc_actor_info_adopt(links+5);infos_live[0].asset_serial++;player_expected(Re4dcActorTexReason::Lifetime);
    player_reset();re4dc_actor_info_adopt(links+5);infos_live[0].tpl_revision++;player_expected(Re4dcActorTexReason::Lifetime);
    player_reset();re4dc_actor_info_adopt(links+5);infos_live[0].tpl_bytes--;player_expected(Re4dcActorTexReason::Lifetime);
    player_reset();re4dc_actor_info_adopt(links+5);assets[5].pending=1;player_expected(Re4dcActorTexReason::Lifetime);
    player_reset();re4dc_actor_info_adopt(links+5);links[5].pData=links[6].pData;player_expected(Re4dcActorTexReason::Lifetime);
    player_reset();re4dc_actor_info_adopt(links);infos_live[0].asset_serial++;player_expected(Re4dcActorTexReason::Row);
    player_reset();re4dc_actor_info_adopt(links);archives[0].revision++;player_expected(Re4dcActorTexReason::Lifetime);
    player_reset();word(const_cast<void*>(links[5].tpl_addr),88,123);player_expected(Re4dcActorTexReason::Owner);
    player_reset();word(const_cast<void*>(links[5].tpl_addr),44,0);player_expected(Re4dcActorTexReason::Owner);
    player_reset();links[5].uvScrollU=1;player_expected(Re4dcActorTexReason::Material);
    player_reset();links[5].be_flag|=2;player_expected(Re4dcActorTexReason::Material);
    player_reset();links[5].invisible_factor=0.5;player_expected(Re4dcActorTexReason::Material);
    player_reset();links[4].uvScrollU=1;player_expected(Re4dcActorTexReason::Material);
    player_reset();for(unsigned k=0;k<8;++k)re4dc_actor_info_adopt(links+k);
    static_cast<unsigned char*>(const_cast<void*>(links[4].pData->pParts))[11]=0x80;
    player_expected(Re4dcActorTexReason::Material);
    player_reset();for(unsigned k=0;k<8;++k)links[k].be_flag&=~8u;player_expected(Re4dcActorTexReason::Hidden);
    player_reset();for(unsigned k=0;k<8;++k)if(k!=7)links[k].be_flag&=~8u;player_expected(Re4dcActorTexReason::Hidden);
    for(unsigned i=1;i<=10;++i){player_reset();player_inject=i;player_expected(Re4dcActorTexReason::Changed);}
    for(unsigned i=0;i<re4dc_charbake::kCount;++i){player_reset();set_variant(i);out=player_expected(Re4dcActorTexReason::None);check(out.package_generation==i+1);}
    player_reset();image.pixels=&texture_tokens[1];player_expected(Re4dcActorTexReason::Owner);
    player_reset();image.palette=arena;player_expected(Re4dcActorTexReason::Owner);
    player_reset();image.format=5;player_expected(Re4dcActorTexReason::Owner);
    player_reset();fnv++;player_expected(Re4dcActorTexReason::Owner);
    std::printf("standard Leon metadata: %u checks, eight roles, current hands, lifetime/material purity PASS\n",checks);
}
