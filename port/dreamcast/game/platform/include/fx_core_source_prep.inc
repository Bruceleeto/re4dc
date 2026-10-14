// Included only by FX_CORE_TEX_PREP. Read accepted OTs and current owners;
// never execute a source callback, transform, animation, population map or RNG.
extern "C" {
void Esp0a_Trans(cEsp*);
void Esp0a_Trans2(cEsp*);
void Esp0b_Trans(cEsp*);
void Esp0e_Trans(cEsp*);
int re4dc_fx_core_0a(const void*);
int re4dc_fx_core_0e(const void*);
int re4dc_model_owned_source(const void*,unsigned);
int re4dc_room4_state(unsigned*,unsigned*,unsigned*,unsigned*,unsigned*);
}
void Esp47_Trans(cEsp*);
namespace {
constexpr unsigned kFxCoreStride=0x150, kFxCoreSlots=1024, kFxCoreNodes=4096;
bool fxCoreRam(const void* p,std::uintptr_t bytes) {
    const auto a=reinterpret_cast<std::uintptr_t>(p);
    return p && !(a&3U) && a>=std::uintptr_t(RE4_MEM_LO) && a<=std::uintptr_t(RE4_MEM_HI) &&
        bytes && bytes-1<=std::uintptr_t(RE4_MEM_HI)-a;
}
bool fxCoreSpan(const void* p,std::uintptr_t bytes,std::uintptr_t base,std::uintptr_t extent) {
    const auto a=reinterpret_cast<std::uintptr_t>(p);
    return a>=base && bytes<=extent && a-base<=extent-bytes;
}
bool fxCoreOwned(const void* p,unsigned bytes) {
    return fxCoreRam(p,bytes) && re4dc_model_owned_source(p,bytes)==1;
}
unsigned fxCoreCallback(void (*func)(void*),cEsp* esp) {
    if(func==(void (*)(void*))EspCommonTrans)return 1;
    if(func==(void (*)(void*))Esp0a_Trans2 && esp->m_Id==0)return 2;
    if(func==(void (*)(void*))Esp0a_Trans && esp->m_Id==0x0a && re4dc_fx_core_0a(esp))return 3;
    if(func==(void (*)(void*))Esp0b_Trans && esp->m_Id==0x0b)return 4;
    if(func==(void (*)(void*))Esp0e_Trans && esp->m_Id==0x0e && re4dc_fx_core_0e(esp))return 5;
    if(func==(void (*)(void*))Esp47_Trans && esp->m_Id==0x47)return 6;
    return 0;
}
}
extern "C" int re4dc_fx_core_source(unsigned native,Re4dcFxCoreDemand* out) {
    if(!out || !fxCoreRam(pG,sizeof(*pG)))return 0;
    // System 0x800 changes clipping, not OT execution. Accepted callbacks
    // remain potential demand during source events; native owners gate I/O.
    if(pG->Rno0!=3 || G_ROOM_ID!=0x11c)return 0;
    unsigned generation=0,c,b,s,r;
    if(!re4dc_room4_state(&generation,&c,&b,&s,&r) || !generation)return -1;
    auto* sys=g_pEspSys;
    if(!fxCoreRam(sys,sizeof(*sys)))return -2;
    if(!sys->nEsp || sys->nEsp>kFxCoreSlots ||
       !fxCoreRam(sys->pEspBuf,sys->nEsp*kFxCoreStride))return -2;
    if(pG->nPrim<=0 || unsigned(pG->nPrim)>0x100000U || pG->vtx_buf_no>1)return -3;
    const auto prim=std::uintptr_t(pG->prim_cnt),cursor=std::uintptr_t(pG->prim_base);
    const auto first=prim+unsigned(pG->nPrim)*unsigned(pG->vtx_buf_no);
    if(first<prim || (first&31U) || !fxCoreRam(reinterpret_cast<const void*>(first),unsigned(pG->nPrim)) ||
       cursor<first || cursor-first>unsigned(pG->nPrim) || (cursor&31U))return -3;
    Re4dcFxCoreDemand pick;
    std::memset(&pick,0,sizeof(pick));
    pick.game=pG;pick.system=sys;pick.pool=sys->pEspBuf;pick.dummy=sys->pDmyEsp;
    pick.native_frame=native;pick.source_frame=pG->Frame_cnt;pick.room_generation=generation;
#if defined(RE4DC_FX_SCAN) && RE4DC_FX_SCAN
    pick.pool_generation=re4dc_fx_esp_gen; // read only: never sync/rebuild the live map
#endif
    pick.pool_count=sys->nEsp;pick.prim=prim;pick.cursor=cursor;
    pick.prim_bytes=pG->nPrim;pick.prim_buffer=pG->vtx_buf_no;
    unsigned visited=0;
    for(unsigned table=0;table<OT_MAX;++table) {
        const auto& ot=g_OtWork[table];
        if(!ot.list || !ot.max)continue;
        if(ot.max>1024 || !fxCoreRam(ot.list,unsigned(ot.max)*sizeof(OtData)))return -4;
        for(auto* node=&ot.list[ot.max-1];node;) {
            if(++visited>kFxCoreNodes)return -4;
            const auto address=reinterpret_cast<std::uintptr_t>(node);
            const auto buckets=reinterpret_cast<std::uintptr_t>(ot.list);
            const bool bucket=fxCoreSpan(node,sizeof(OtData),buckets,unsigned(ot.max)*sizeof(OtData)) &&
                (address-buckets)%sizeof(OtData)==0;
            const bool allocated=fxCoreSpan(node,sizeof(OtPrim),first,cursor-first) && (address-first)%32==0;
            if(!bucket && !allocated)return -4;
            if(bucket && node->data)return -4;
            // Empty bucket heads do not initialize func. Validate the next node
            // at the top of the loop, before reading any of its fields.
            if(node->data) {
                const auto address=reinterpret_cast<std::uintptr_t>(node->data);
                const auto pool=reinterpret_cast<std::uintptr_t>(sys->pEspBuf);
                if(fxCoreSpan(node->data,kFxCoreStride,pool,sys->nEsp*kFxCoreStride) &&
                   (address-pool)%kFxCoreStride==0 && node->data!=sys->pDmyEsp) {
                    auto* esp=static_cast<cEsp*>(node->data);
                    if((esp->m_Be_flg&1) && esp->m_Id<0xff && esp->m_Tex_id==0x1d && esp->m_Ptn_no==0 &&
                       !esp->m_Shimmer_type && !(esp->m_Tool_flg&0x2000) && EspSpriteEligible(esp)) {
                        const unsigned callback=fxCoreCallback(node->func,esp);
                        if(callback) {
                            if(!pick.accepted) {
                                pick.node=node;pick.buckets=ot.list;pick.table=table;pick.table_max=ot.max;
                                pick.slot=(address-pool)/kFxCoreStride;pick.callback=callback;
                                pick.owner=esp->info.owner;pick.call_no=esp->info.Call_no;
                                // Raw lifetime/change witness only: stale m_Mat is
                                // never read as a visibility/transform decision.
                                std::memcpy(pick.source,esp,kFxCoreStride);
                            }
                            ++pick.accepted;
                        }
                    }
                }
            }
            node=node->next;
        }
    }
    if(!pick.accepted)return 0;
    const auto& tw=sys->Esp_tex_tbl[0x1d];
    if(tw.Owner!=0 || !fxCoreOwned(tw.pTpl,sizeof(TEXPalette)) ||
       !fxCoreOwned(tw.pAnm,sizeof(EspAnmData)))return -5;
    const auto* tpl=tw.pTpl;const auto* anm=tw.pAnm;
    if(tpl->numDescriptors!=1 || anm->Frames!=1 || anm->Width!=256 || anm->Height!=256 ||
       anm->Cx || anm->Cy || !fxCoreOwned(tpl->descriptorArray,sizeof(TEXDescriptor)))return -5;
    const auto* td=tpl->descriptorArray;
    if(td->CLUTHeader || !fxCoreOwned(td->textureHeader,sizeof(TEXHeader)))return -5;
    const auto* th=td->textureHeader;
    if(th->width!=256 || th->height!=256 || th->format!=1 || !fxCoreOwned(th->data,32))return -5;
    pick.tpl=tpl;pick.animation=anm;pick.descriptors=td;pick.header=th;
    pick.image.pixels=th->data;pick.image.width=pick.image.height=256;
    pick.image.format=1;pick.image.palette_format=0xffffffffU;
    // No load/yield/callback has occurred. The native side repeats this full
    // current-owner walk after its ordinary fenced load before claiming ready.
    std::memcpy(out,&pick,sizeof(pick));
    return 1;
}
extern "C" int re4dc_fx_core_current(unsigned native,const Re4dcFxCoreDemand* expected) {
    if(!expected || expected->native_frame!=native)return 0;
    Re4dcFxCoreDemand now;
    return re4dc_fx_core_source(native,&now)==1 && std::memcmp(&now,expected,sizeof(now))==0;
}
