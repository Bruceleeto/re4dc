// Included after workspace_top/workspace_end inside the native actor namespace.
re4dc_actor::WorkspaceReservations owned_workspace;
unsigned workspace_scratch_limit() {
    const unsigned reserve=owned_workspace.maximum();
    const unsigned limit=reserve<=workspace_bytes?workspace_bytes-reserve:0;
    return workspace_end<limit?workspace_end:limit;
}
void owned_skin_invalidate_frames(){for(auto& f:frames)f=Frame{};}
extern "C" int re4dc_actor_workspace_acquire(unsigned bytes,Re4dcActorWorkspaceLease* out) {
    if(!out || !bytes || bytes>UINT32_MAX-31)return 0;
    bytes=(bytes+31)&~31u;
    if(!workspace || bytes>workspace_bytes || workspace_top>workspace_bytes-bytes)return 0;
    return owned_workspace.acquire(bytes,frame_serial,*out)?1:0;
}
extern "C" int re4dc_actor_workspace_validate(const Re4dcActorWorkspaceLease* lease) {
    return lease && workspace && owned_workspace.valid(*lease,frame_serial) &&
        lease->bytes<=workspace_bytes && workspace_top<=workspace_bytes-lease->bytes;
}
extern "C" void re4dc_actor_workspace_release(Re4dcActorWorkspaceLease* lease) {
    if(lease)owned_workspace.release(*lease);
}
extern "C" void re4dc_actor_owner_retire() {
    owned_workspace.retire();owned_skin_clear();owned_skin_invalidate_frames();owned_submission=false;
    // This memory belongs to the retiring primitive allocation, not Frame_cnt.
    // re4dc_actor_frame installs a fresh span immediately after this function
    // when rebinding; retirement alone must leave no old workspace readable.
    workspace=nullptr;workspace_bytes=workspace_top=workspace_end=0;
}
