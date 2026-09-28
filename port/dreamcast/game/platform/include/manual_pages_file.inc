// ss_file.cpp, after file_tpl_name and the unchanged camera text helper.
// The request ID is scoped by this begin/finish pair, not a pointer-cache proof.
static unsigned file_manual_row=RE4DC_MANUAL_PAGE_COUNT,file_manual_kind;
static int file_manual_request=-1;
static void file_manual_retire(){
    re4dc_manual_pages_retire();file_manual_row=RE4DC_MANUAL_PAGE_COUNT;
    file_manual_kind=0;file_manual_request=-1;
}
static int file_manual_context(SsFileWork* fw,unsigned row){
    const Re4dcManualPageContext* p=re4dc_ui_manual_page(row);
    return p && pSys->language==1 && fw->fileNo==p->file_no && fw->page==p->page &&
        fw->msgBase==p->message_base && fw->layout==1 && fw->attr==0x80054;
}
static void file_manual_begin(SsFileWork* fw,int no,unsigned picture){
    file_manual_retire(); // revoke BEFORE this shared 128KiB buffer is reused
    for(unsigned row=0;row<RE4DC_MANUAL_PAGE_COUNT;++row){
        const Re4dcManualPageContext* p=re4dc_ui_manual_page(row);
        if(!file_manual_context(fw,row) || unsigned(no)!=p->file_no || picture!=p->picture)continue;
        file_manual_row=row;file_manual_kind=1; // exact original selected by default
        if(!p->companion_path || !re4dc_manual_page_companion_allowed(row))return;
        // Camera text is latched by the original MesSet setup; no reinitializing
        // text after a device poll. The other six messages are not substituted.
        if(row==RE4DC_MANUAL_CAMERA && file_prompt_kind!=RE4DC_PROMPT_DPAD)return;
        u32 bytes=0;
        if(Dvd.FileExistCheck(p->companion_path,&bytes)>=0 && bytes==RE4DC_MANUAL_SOURCE_BYTES &&
           re4dc_ui_manual_page_available(row)){
            file_tpl_name[10]=p->companion_path[10];file_manual_kind=2;
        }
        return;
    }
}
static int file_manual_finish(SUB_SCREEN* wk,SsFileWork* fw,int request,int ready,int bytes){
    // Only a successful exact tracked read can schedule the current picture.
    // Cancel/error/short/mismatched requests remain terminal, without retries.
    const int complete=ready==1 && request>=0 && request==file_manual_request &&
        bytes==RE4DC_MANUAL_SOURCE_BYTES && file_manual_kind;
    const Re4dcManualPageContext* p=complete ? re4dc_ui_manual_page(file_manual_row) : 0;
    const int page_moved=p && pSys->language==1 && fw->fileNo==p->file_no &&
        fw->msgBase==p->message_base && fw->layout==1 && fw->attr==0x80054 && fw->page!=p->page;
    // The old page is never adopted as the current page. This return value only
    // lets the caller use its existing next-frame request state if cur!=nxt.
    if(complete && file_manual_context(fw,file_manual_row))
        re4dc_manual_pages_adopt(wk->pTplDat,unsigned(bytes),file_manual_row,file_manual_kind);
    else re4dc_manual_pages_retire();
    file_manual_row=RE4DC_MANUAL_PAGE_COUNT;file_manual_kind=0;file_manual_request=-1;
    return page_moved;
}
