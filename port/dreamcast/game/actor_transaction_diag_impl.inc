// Diagnostic only: cumulative counters and one bounded sample per reason/class.
// Event0 is callback attempts; commits/pass1/pass2 separately prove actual use.
#if RE4DC_ACTOR_TRANSACTION_DIAG
extern "C" unsigned re4dc_ui_frame();
extern "C" void re4dc_log(const char*,...);
namespace {
unsigned atd_counts[3][32]{},atd_last_frame;
bool atd_started;
void atd_report(unsigned frame) {
    for(unsigned g=0;g<3;++g)for(unsigned half=0;half<2;++half) {
        const unsigned* c=&atd_counts[g][half*16];
        re4dc_log("ATX f=%u g=%u base=%u c=%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
            frame,g,half*16,c[0],c[1],c[2],c[3],c[4],c[5],c[6],c[7],c[8],c[9],c[10],c[11],c[12],c[13],c[14],c[15]);
    }
}
}
extern "C" void re4dc_actor_txdiag_note(cModel* m,unsigned event,unsigned a,unsigned b) {
    if(event>=32)return;
    const unsigned frame=re4dc_ui_frame();
    if(!atd_started || unsigned(frame-atd_last_frame)>=120u) {
        atd_started=true;atd_last_frame=frame;atd_report(frame);
    }
    const unsigned g=m && m->id==0?0u:m && m->id>=0x10 && m->id<=0x20?1u:2u;
    unsigned& count=atd_counts[g][event];
    if(count==0 && event!=0 && event!=1 && event!=2)
        re4dc_log("ATX_SAMPLE g=%u e=%u m=%p id=%u serial=%u flags=%08x ot=%u parts=%u root=%p infos=%p a=%u b=%u\n",
            g,event,m,m?unsigned(m->id):~0u,m?unsigned(m->serial):0u,m?unsigned(m->be_flag):0u,
            m?unsigned(m->ot_type):0u,m?unsigned(m->nParts):0u,m?m->pParts:nullptr,m?m->pModelInfo:nullptr,a,b);
    if(count!=~0u)++count;
}
#endif
