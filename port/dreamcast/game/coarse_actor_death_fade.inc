// G1: a whole-actor token at the original source FIFO position. The probe is
// unpublished; all leases are released before source presentation is suppressed.
namespace {
int actor_fade_enqueue(cModel* m,const Re4dcActorPlan& p,const FrameIdentity& frame,const ModelIdentity& model) {
    Re4dcActorFadeTicket ticket{frame,model,0,0};
    if(!actor_fade_current(ticket,1)){actor_fail();return -1;}
    Re4dcActorFadeReservation reservation{};
    const int reserved=re4dc_model_actor_fade_reserve(&reservation);
    if(reserved<=0){actor_fade_note(reserved?"fail":"source",ticket,nullptr,1);return reserved;}
    // actor_acquire checks identity/binding AFTER all texture I/O, BEFORE
    // allocating its primitive header; later acquire work cannot yield. Keep
    // the plan on this call's source stack, never in a retained header.
    const void* parts_owner=m->pParts;
    const unsigned revision=re4dc_actor_binding_revision(m);
    bool failed=false;
    auto* r=actor_acquire(m,p,frame,model,failed,false,nullptr,revision,parts_owner);
    if(!r) {
        const bool current=actor_fade_current(ticket,1);
        const int canceled=re4dc_model_actor_fade_cancel(&reservation);
        if(failed || !current || canceled!=1){actor_fail();return -1;}
        actor_fade_note("source",ticket,nullptr,2);return 0;
    }
    if(!actor_fade_current(ticket,1)) {
        // Retirement revokes leases itself. Never read/release an old header.
        re4dc_model_actor_fade_cancel(&reservation);actor_fail();return -1;
    }
    const ActorFadeContext context=actor_fade_capture(m,*r);
    const bool released=actor_release(*r); // skin BEFORE palette, workspace, textures
    Re4dcActorStreamState stream{};
    if(!released || !actor_fade_current(ticket,1) || !re4dc_actor_stream_state(&stream)) {
        re4dc_model_actor_fade_cancel(&reservation);actor_fail();return -1;
    }
    if(!revision || (!actor_fade_sequence && actor_fade_head) || actor_fade_sequence==~0u) {
        re4dc_model_actor_fade_cancel(&reservation);actor_fail();return -1;
    }
    // Reuse the now lease-free unpublished header. No second primitive
    // allocation, I/O or yield occurs before publishing the pending ticket.
    ticket.sequence=++actor_fade_sequence;ticket.queue_epoch=reservation.epoch;
    auto* pending=::new(static_cast<void*>(r))ActorFadePending{};
    pending->ticket=ticket;pending->parts_owner=parts_owner;pending->binding_revision=revision;
    pending->plan=p;pending->context=context;
    if(!re4dc_actor_transaction_choose(m,2)) {
        re4dc_model_actor_fade_cancel(&reservation);actor_fail();return -1;
    }
    pending->next=actor_fade_head;actor_fade_head=pending;
    if(re4dc_model_actor_fade_commit(&reservation,&ticket)!=1) {
        pending->state=re4dc_fade::State::Failed;actor_fail();return -1;
    }
    ++actor_fade_pending;actor_fade_note("enqueue",ticket,&context);
#if RE4DC_ACTOR_TRANSACTION_DIAG
    actor_fade_snapshot(ticket,context);
#endif
    return 1;
}
int actor_fade_drain_failed(const Re4dcActorFadeTicket& ticket,const ActorFadeContext* context,unsigned why) {
    if(actor_fade_current(ticket,2)) {
        auto* p=actor_fade_find(ticket.model);
        if(p && re4dc_fade::same_ticket(p->ticket,ticket))p->state=re4dc_fade::State::Failed;
    }
    actor_fade_note("fail",ticket,context,why);actor_fail();return -1;
}
}
extern "C" int re4dc_actor_death_fade_drain(Re4dcActorFadeTicket ticket) {
    if(!actor_fade_current(ticket,2))return actor_fade_drain_failed(ticket,nullptr,10);
    auto* pending=actor_fade_find(ticket.model);
    if(!pending || !re4dc_fade::same_ticket(pending->ticket,ticket) || !re4dc_fade::begin(pending->state))
        return actor_fade_drain_failed(ticket,nullptr,11);
    // Copy before resource acquisition. A later identity check must precede
    // every lookup/write, even when a failure happens during texture I/O.
    const ActorFadePending saved=*pending;
    actor_fade_note("drain",ticket,&saved.context);
    auto* m=reinterpret_cast<cModel*>(ticket.model.address);
    if(m->pParts!=saved.parts_owner || !saved.binding_revision ||
       re4dc_actor_binding_revision(m)!=saved.binding_revision ||
       !actor_fade_eligible(m,saved.plan) || !actor_semantics(m,saved.plan) ||
       saved.context.hash!=actor_fade_hash(saved.context))return actor_fade_drain_failed(ticket,&saved.context,12);
    bool failed=false;
    auto* r=actor_acquire(m,saved.plan,ticket.frame,ticket.model,failed,false,&saved.context,saved.binding_revision,saved.parts_owner);
    if(!r)return actor_fade_drain_failed(ticket,&saved.context,13);
    if(failed || !actor_fade_current(ticket,2))return actor_fade_drain_failed(ticket,&saved.context,14);
    // The current-identity check above precedes every retained-header read.
    auto& draw=*r;
    if(m->pParts!=saved.parts_owner || re4dc_actor_binding_revision(m)!=saved.binding_revision) {
        actor_release(draw);return actor_fade_drain_failed(ticket,&saved.context,14);
    }
    // Source ot_type 0 has one pass. Preserve captured source-info order and
    // visibility, while the palette just built uses drain-current source bones.
    Re4dcActorDrawRun runs[kRe4dcActorRuns]{};unsigned count=0;
    for(unsigned i=0;i<draw.count;++i)if(draw.part[i].flags&8)
        for(unsigned j=0;j<draw.run_count;++j)if(draw.runs[j].chunk.info==draw.part[i].info)runs[count++]=draw.runs[j];
    const int result=count?re4dc_actor_submit_owned_runs(&draw.base,runs,count,draw.plan.materials,draw.plan.material_count,
        &draw.workspace,&draw.skin,draw.textures):1;
    // Even a failing emitter may have retired the frame. Retirement performs
    // revocation itself; never dereference its old primitive header afterward.
    if(!actor_fade_current(ticket,2))return actor_fade_drain_failed(ticket,&saved.context,15);
    const bool released=actor_release(draw);
    if(result!=1 || !released || !actor_fade_current(ticket,2))return actor_fade_drain_failed(ticket,&saved.context,15);
    pending=actor_fade_find(ticket.model);
    if(!pending || !re4dc_fade::same_ticket(pending->ticket,ticket) || !actor_fade_pending ||
       !re4dc_fade::finish(pending->state))return actor_fade_drain_failed(ticket,&saved.context,16);
    --actor_fade_pending;actor_fade_note("done",ticket,&saved.context);return 1;
}
