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
#if RE4DC_NATIVE_MODEL_REGISTRY
extern "C" int re4dc_registry_candidate(const cModel*);
#endif
extern "C" int re4dc_actor_transaction_candidate(cModel* m) {
    // Disable the FRONT_NATIVE fast return only for these source-prepared
    // reviewed classes. Their ordinary state/postlude runs via commonModelTrans.
#if RE4DC_NATIVE_MODEL_REGISTRY
    // NATIVE_MODEL_REGISTRY: also non-partner models whose id has a validated
    // runtime descriptor of the same part count (coarse_actor_owner_registry.inc,
    // O(1) id mask first). These only nominate; the ledger membership below and the transaction's
    // role / skeleton / material proofs admit, and a declined actor draws the
    // whole source path through commonModelTrans.
    if(!m || !(m==(cModel*)pPL || (m!=(cModel*)pSUB && ((m->id>=0x10 && m->id<=0x20) ||
       re4dc_registry_candidate(m)))))return 0;
#else
    if(!m || !(m==(cModel*)pPL || (m!=(cModel*)pSUB && m->id>=0x10 && m->id<=0x20)))return 0;
#endif
    FrameIdentity frame{};ModelIdentity model{};
    return re4dc_actor_transaction_identity(m,&frame,&model)!=0;
}
