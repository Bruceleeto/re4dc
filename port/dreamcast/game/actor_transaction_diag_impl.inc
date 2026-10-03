// Diagnostic only: cumulative counters and one bounded sample per reason/class.
// Event0 is callback attempts; commits/pass1/pass2 separately prove actual use.
#if RE4DC_ACTOR_TRANSACTION_DIAG
#include <cstdio>
extern "C" unsigned re4dc_ui_frame();
extern "C" void re4dc_log(const char*,...);
namespace {
unsigned atd_counts[3][32]{},atd_last_frame;
bool atd_started;
// Per model (lane impl 2026-10-03, WP2 census): the events of each model since the last report, with its vtable
// pointer (symbolise against the ELF: cPlLeon, event models ...), so a group's counts can be split by model.
struct AtdModel { const cModel* m; unsigned vptr,id,ot,parts,infos,ev[32]; };
constexpr unsigned kAtdModels=24;
AtdModel atd_models[kAtdModels];
unsigned atd_nmodels,atd_model_overflow;
void atd_report(unsigned frame) {
    for(unsigned g=0;g<3;++g)for(unsigned half=0;half<2;++half) {
        const unsigned* c=&atd_counts[g][half*16];
        re4dc_log("ATX f=%u g=%u base=%u c=%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",
            frame,g,half*16,c[0],c[1],c[2],c[3],c[4],c[5],c[6],c[7],c[8],c[9],c[10],c[11],c[12],c[13],c[14],c[15]);
    }
    for(unsigned i=0;i<atd_nmodels;++i) {
        AtdModel& a=atd_models[i];
        char text[256];unsigned n=0;
        for(unsigned e=0;e<32 && n+16<sizeof(text);++e)if(a.ev[e])n+=snprintf(text+n,sizeof(text)-n,"%u:%u ",e,a.ev[e]);
        text[n]=0;
        if(n)re4dc_log("ATX_M f=%u m=%p vptr=%08x id=%02x ot=%u parts=%u infos=%u ev=%s\n",frame,a.m,a.vptr,a.id,a.ot,a.parts,
                       a.infos,text);
    }
    if(atd_model_overflow)re4dc_log("ATX_M f=%u overflow=%u (more than %u models)\n",frame,atd_model_overflow,kAtdModels);
    atd_nmodels=0;atd_model_overflow=0;
}
void atd_model_note(const cModel* m,unsigned event) {
    if(!m)return;
    unsigned i=0;while(i<atd_nmodels && atd_models[i].m!=m)++i;
    if(i==atd_nmodels) {
        if(atd_nmodels==kAtdModels){++atd_model_overflow;return;}
        AtdModel& a=atd_models[atd_nmodels++];a=AtdModel{};
        a.m=m;a.vptr=*reinterpret_cast<const unsigned*>(m);a.id=m->id;a.ot=m->ot_type;a.parts=m->nParts;
        for(const cModelInfo* f=m->pModelInfo;f && a.infos<999;f=f->pList)++a.infos;
    }
    ++atd_models[i].ev[event];
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
    atd_model_note(m,event);
}
// One line per model, check and reason code: why a check declined it (WP2 census). The code is the number of the
// first failing clause of the check's *_why twin (DIAG builds only).
extern "C" void re4dc_actor_txdiag_why(const cModel* m,const char* what,unsigned code,unsigned detail) {
    static struct { const cModel* m; const char* what; unsigned code; } seen[48];
    static unsigned nseen;
    for(unsigned i=0;i<nseen;++i)if(seen[i].m==m && seen[i].what==what && seen[i].code==code)return;
    if(nseen<48)seen[nseen++]={m,what,code};
    re4dc_log("ATX_WHY f=%u m=%p vptr=%08x id=%02x ot=%u parts=%u %s=%u detail=%u\n",re4dc_ui_frame(),m,
              m?*reinterpret_cast<const unsigned*>(m):0u,m?unsigned(m->id):0u,m?unsigned(m->ot_type):0u,
              m?unsigned(m->nParts):0u,what,code,detail);
}
#endif
