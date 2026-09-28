// Included after the source actor ledger block, before Trans().
// All helpers are values; no borrowed ledger/primitive pointers escape.
extern "C" int re4dc_actor_transaction_identity(cModel* m,re4dc_source::FrameIdentity* frame,re4dc_source::ModelIdentity* model) {
    if(!sourceActorActive || !sourceActorRenderActive)return 0;
    if(!m || !frame || !model || !sourceActorRam(m) || !sourceActorIdentity(*frame) ||
       !sourceActorLedger.ready(*frame))return -1;
    *model=sourceActorModel(m);
    if(sourceActorLedger.membership(*frame,*model)==Membership::SourceHandled)return 1;
    // A reused actor address cannot become an untracked source fallback after
    // a native first pass. Unrelated ObjMgr/world models are not participants.
    return sourceActorLedger.presentation_address(*frame,model->address)?-1:0;
}
extern "C" int re4dc_actor_transaction_choice(cModel* m,unsigned* value) {
    FrameIdentity frame{};ModelIdentity model{};
    return value && re4dc_actor_transaction_identity(m,&frame,&model)==1 &&
        sourceActorLedger.presentation_choice(frame,model,*value);
}
extern "C" int re4dc_actor_transaction_choose(cModel* m,unsigned value) {
    FrameIdentity frame{};ModelIdentity model{};
    return re4dc_actor_transaction_identity(m,&frame,&model)==1 &&
        sourceActorLedger.presentation_choose(frame,model,value);
}
extern "C" int re4dc_actor_transaction_candidate(cModel* m) {
    // Disable the FRONT_NATIVE fast return only for these source-prepared
    // reviewed classes. Their ordinary state/postlude runs via commonModelTrans.
    if(!m || !(m==(cModel*)pPL || (m!=(cModel*)pSUB && m->id>=0x10 && m->id<=0x20)))return 0;
    FrameIdentity frame{};ModelIdentity model{};
    return re4dc_actor_transaction_identity(m,&frame,&model)!=0;
}
