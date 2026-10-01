// Included once after material row definitions and bounded texture comparator.
// Full BIN identity is computed at archive adoption, before relocation/FE.
// Metadata borrows real source allocations; it never owns or duplicates them.
#include "actor_transaction_diag.h"
#if RE4DC_CROWD_CENSUS
unsigned crowd_adopt_calls,crowd_adopt_ok,crowd_adopt_fail[4],crowd_archive_full,crowd_archive_unsupported,crowd_revokes,crowd_revoked_infos,crowd_readopt_ok,crowd_readopt_fail;
#define CROWD_LIFE(stmt) stmt
#else
#define CROWD_LIFE(stmt)
#endif
namespace re4dc_material { namespace life {
constexpr unsigned kArchives=8,kAssets=40,kInfos=160,kModels=40;
struct Archive { const void* key;const unsigned char* base;unsigned bytes,revision,family; };
struct Asset {
    const ModelData* data;const unsigned char* base;unsigned bytes;
    unsigned archive,owner_revision,serial,templates,pending;
    const void* section[7]; // head,colour,UV,weights,parts,positions,normals
};
struct Info { cModelInfo* info;unsigned asset,asset_serial,roles[2],tpl_owner,tpl_revision;const void* tpl;unsigned tpl_bytes; };
struct Binding { cModel* model;const void* parts;unsigned serial,revision,epoch; };
static_assert(sizeof(source_blobs)/sizeof(source_blobs[0])<=32,"asset template mask capacity");
static_assert(sizeof(roles)/sizeof(roles[0])<=64,"info role mask capacity");
static_assert(sizeof(void*)!=4 || (sizeof(Archive)==20 && sizeof(Asset)==60 && sizeof(Info)==36 && sizeof(Binding)==20),"reviewed 32-bit metadata size");
Archive archives[kArchives]{};Asset assets[kAssets]{};Info infos_live[kInfos]{};Binding bindings[kModels]{};
unsigned serial=1,epoch=1;bool exhausted=false;
unsigned next() {if(exhausted || serial==~0u){exhausted=true;return 0;}return ++serial;}
bool span(const void* begin,unsigned size,const void* p,unsigned n) {
    const auto a=reinterpret_cast<std::uintptr_t>(begin),b=reinterpret_cast<std::uintptr_t>(p);
    return begin && p && b>=a && b-a<=size && n<=size-(b-a);
}
bool overlap(const void* a,unsigned an,const void* b,unsigned bn) {
    const auto x=reinterpret_cast<std::uintptr_t>(a),y=reinterpret_cast<std::uintptr_t>(b);
    return an && bn && (x<=y ? y-x<an : x-y<bn);
}
void changed() {epoch=next();}
void revoke(unsigned owner) {
#if RE4DC_CROWD_CENSUS
    ++crowd_revokes;
    for(auto& i:infos_live)if(i.info && (i.tpl_owner==owner || assets[i.asset].archive==owner))++crowd_revoked_infos;
#endif
    for(auto& i:infos_live)if(i.info && (i.tpl_owner==owner || assets[i.asset].archive==owner))i={};
    for(auto& a:assets)if(a.data && a.archive==owner)a={};
    archives[owner]={};changed();
}
bool entry(const Archive& o,unsigned no,const char* tag,const unsigned char*& begin,unsigned& size) {
    if(!o.key || no<4 || !span(o.base,o.bytes,o.base,16))return false;
    const unsigned count=u32at(o.base,0);if(count>4096 || no-4>=count || 16u+count*8u>o.bytes)return false;
    const unsigned idx=no-4,at=u32at(o.base,16+idx*4),table=16+count*4;
    if(std::memcmp(o.base+table+idx*4,tag,3) || at<16+count*8 || at>=o.bytes)return false;
    unsigned end=o.bytes;
    // Empty DRS slots have a zero four-byte tag and zero length: their
    // immediate next offset equals their own. Only the contiguous empty run
    // directly before this tagged entry may alias it. Tagged, later and
    // noncontiguous aliases remain ambiguous and are rejected.
    unsigned empty_first=idx;
    while(empty_first && u32at(o.base,16+(empty_first-1)*4)==at &&
          u32at(o.base,table+(empty_first-1)*4)==0) --empty_first;
    // REL begins at header+4. Use the nearest later entry/REL as the span.
    unsigned rel=u32at(o.base,4);if(rel>at && rel<end)end=rel;
    for(unsigned k=0;k<count;++k)if(k!=idx) {
        const unsigned off=u32at(o.base,16+k*4);
        if(off==at && (k<empty_first || k>=idx))return false;
        if(off>at && off<end)end=off;
    }
    begin=o.base+at;size=end-at;return true;
}
bool current(const Asset& a) {
    if(!a.data || a.archive>=kArchives || a.pending)return false;
    const auto& o=archives[a.archive];
    if(!o.key || o.revision!=a.owner_revision || !span(o.base,o.bytes,a.base,a.bytes))return false;
    const auto* d=a.data;
    return d->pHead==a.section[0] && d->pClr==a.section[1] && d->pTex==a.section[2] &&
      d->pWeight==a.section[3] && d->pParts==a.section[4] && d->vtxOrig==a.section[5] && d->nrmOrig==a.section[6];
}
bool tpl_owned(const Archive& o,const void* p,unsigned bytes,const Role& r) {
    if(!span(o.base,o.bytes,p,bytes) || !span(p,bytes,p,12) || u32at(p,4)!=r.texture_count)return false;
    const void* td=ptrat(p,8);
    if(!span(p,bytes,td,r.texture_count*8))return false;
    for(unsigned k=0;k<r.texture_count;++k) {
        const auto* t=static_cast<const unsigned char*>(td)+k*8;const void* h=ptrat(t,0),*c=ptrat(t,4);
        if(!span(p,bytes,h,36))return false;
        const unsigned n=r.textures[k].palette.bytes?64u:32u;
        if(!span(p,bytes,ptrat(h,8),n))return false;
        if(c && (!span(p,bytes,c,12) || !span(p,bytes,ptrat(c,8),r.textures[k].palette.bytes)))return false;
        if(texture(t,r.textures[k])!=Error::None)return false;
    }
    return true;
}
Info* find_info(const void* p) {for(auto& i:infos_live)if(i.info==p)return &i;return nullptr;}
bool info_current(const Info& i,unsigned role) {
    if(!i.info || i.asset>=kAssets || i.tpl_owner>=kArchives || role>=64 || !(i.roles[role/32]&(1u<<(role%32))))return false;
    const auto& a=assets[i.asset];const auto& t=archives[i.tpl_owner];
    return current(a) && a.serial==i.asset_serial && t.key && t.revision==i.tpl_revision &&
      span(t.base,t.bytes,i.tpl,i.tpl_bytes) && i.info->pData==a.data && i.info->tpl_addr==i.tpl;
}
} }
extern "C" void re4dc_actor_archive_retire(const void* key) {
    using namespace re4dc_material::life;
    if(!key)return;for(unsigned k=0;k<kArchives;++k)if(archives[k].key==key)revoke(k);
}
extern "C" void re4dc_actor_archive_adopt(const void* key,void* base,unsigned bytes,unsigned family) {
    using namespace re4dc_material;using namespace life;
    // This owner revision was issued by the same successful load boundary and
    // has NOT passed its mandatory unbind-before-overwrite boundary. Duplicate
    // UI adoption preserves that revision after relocation/native conversion.
    // A retired owner cannot enter this branch even at the same address.
    for(const auto& o:archives)if(o.key==key && o.base==base && o.bytes==bytes && o.family==family)return;
    re4dc_actor_archive_retire(key);
    // Overlapping adoption revokes the old owner before any positive proof.
    for(unsigned k=0;k<kArchives;++k)if(archives[k].key && overlap(base,bytes,archives[k].base,archives[k].bytes))revoke(k);
    if(exhausted || !key || !readable(base,bytes) || bytes<16 || family<1 || family>3)return;
    unsigned oi=0;while(oi<kArchives && archives[oi].key)++oi;if(oi==kArchives){CROWD_LIFE(++crowd_archive_full);return;}
    auto& owner=archives[oi];owner={key,static_cast<const unsigned char*>(base),bytes,next(),family};
    for(unsigned t=0;t<sizeof(source_blobs)/sizeof(source_blobs[0]);++t) {
        const auto& s=source_blobs[t];if(s.family!=family)continue;
        const unsigned char* b=nullptr;unsigned n=0;
        if(!entry(owner,s.bin,"BIN",b,n) || s.normalized.bytes>n || !digest(b,s.normalized))continue;
        Asset* a=nullptr;
        for(auto& x:assets)if(x.data==reinterpret_cast<const ModelData*>(b)){a=&x;break;}
        if(a){a->templates|=1u<<t;continue;}
        for(auto& x:assets)if(!x.data){a=&x;break;}if(!a)continue;
        *a={};a->data=reinterpret_cast<const ModelData*>(b);a->base=b;a->bytes=s.normalized.bytes;
        a->archive=oi;a->owner_revision=owner.revision;a->serial=next();a->templates=1u<<t;
        const unsigned fields[7]={0,12,16,20,28,48,52};bool okay=true;
        for(unsigned j=0;j<7;++j) {
            const unsigned off=u32at(b,fields[j]);
            if(off>=a->bytes){okay=false;break;}a->section[j]=b+off;
        }
        if(!okay)*a={};
    }
    // Unrelated animals/actors must not consume all eight reviewed owner slots.
    // They retain their source preparation/rendering and acquire no proof.
    bool supported=false;for(const auto& a:assets)if(a.data && a.archive==oi)supported=true;
    if(!supported){owner={};CROWD_LIFE(++crowd_archive_unsupported);}
    changed();
}
extern "C" void re4dc_actor_archive_retire_transient() {
    using namespace re4dc_material::life;
    for(unsigned k=0;k<kArchives;++k)if(archives[k].key && archives[k].family==2)revoke(k);
}
extern "C" void re4dc_actor_info_retire(const void* p) {
    using namespace re4dc_material::life;
    if(auto* i=find_info(p)){*i={};changed();}
}
#if RE4DC_CROWD_CENSUS
// Lane crowd census (diagnostic): why infos stay unadopted (every owner-path plan of their actor then fails at
// find_info and the actor draws through the source path). adopt_fail: [0] no asset, [1] asset not current, [2] no
// role / TPL row, [3] no free info slot; revokes: archives revoked (their infos dropped until setTplAddr runs again).
extern "C" void re4dc_crowd_life_report(unsigned frame) {
    using namespace re4dc_material::life;
    unsigned ar=0,as=0,in=0;
    for(const auto& a:archives)ar+=a.key!=nullptr;
    for(const auto& a:assets)as+=a.data!=nullptr;
    for(const auto& i:infos_live)in+=i.info!=nullptr;
    re4dc_log("CROWDLIFE f=%u archives=%u/%u assets=%u/%u infos=%u/%u exhausted=%u adopt=%u ok=%u fail=%u/%u/%u/%u archive_full=%u unsupported=%u revokes=%u revoked_infos=%u readopt=%u/%u\n",
        frame,ar,kArchives,as,kAssets,in,kInfos,unsigned(exhausted),crowd_adopt_calls,crowd_adopt_ok,crowd_adopt_fail[0],crowd_adopt_fail[1],
        crowd_adopt_fail[2],crowd_adopt_fail[3],crowd_archive_full,crowd_archive_unsupported,crowd_revokes,crowd_revoked_infos,crowd_readopt_ok,crowd_readopt_fail);
}
#endif
extern "C" void re4dc_actor_info_adopt(cModelInfo* info) {
    using namespace re4dc_material;using namespace life;
    re4dc_actor_info_retire(info);if(exhausted || !info)return;
    CROWD_LIFE(++crowd_adopt_calls);
    unsigned ai=0;while(ai<kAssets && assets[ai].data!=info->pData)++ai;
    if(ai==kAssets || !current(assets[ai])){CROWD_LIFE(++crowd_adopt_fail[ai==kAssets?0:1]);return;}
    const auto& a=assets[ai];Info found{};
    for(unsigned r=0;r<sizeof(roles)/sizeof(roles[0]);++r) {
        const auto& row=roles[r];bool match=false;
        for(unsigned t=0;t<sizeof(source_blobs)/sizeof(source_blobs[0]);++t)
            if((a.templates&(1u<<t)) && source_blobs[t].model==row.model)match=true;
        if(!match)continue;
        for(unsigned k=0;k<kArchives;++k) {
            const auto& o=archives[k];if(o.family!=(row.appearance==256?1u:2u))continue;
            const unsigned char* p=nullptr;unsigned n=0;
            if(!entry(o,row.source_tpl,"TPL",p,n) || p!=info->tpl_addr || !tpl_owned(o,p,n,row))continue;
            // Multiple rows may intentionally share default hand geometry.
            if(found.info && (found.tpl_owner!=k || found.tpl!=p))return;
            found.roles[r/32]|=1u<<(r%32);
            found={info,ai,a.serial,{found.roles[0],found.roles[1]},k,o.revision,p,n};
        }
    }
    if(!found.info){CROWD_LIFE(++crowd_adopt_fail[2]);return;}
    for(auto& slot:infos_live)if(!slot.info){slot=found;changed();CROWD_LIFE(++crowd_adopt_ok);return;}
    CROWD_LIFE(++crowd_adopt_fail[3]);
}
extern "C" void re4dc_actor_forget_range(const void* p,unsigned bytes) {
    using namespace re4dc_material::life;if(!p || !bytes)return;
    for(unsigned k=0;k<kArchives;++k)if(archives[k].key && overlap(p,bytes,archives[k].base,archives[k].bytes))revoke(k);
    bool hit=false;for(auto& i:infos_live)if(i.info && overlap(p,bytes,i.info,sizeof(cModelInfo))){i={};hit=true;}
    for(auto& b:bindings)if(b.model && (overlap(p,bytes,b.model,sizeof(cModel)) || span(p,bytes,b.parts,1))){b={};hit=true;}
    if(hit)changed();
}
extern "C" void re4dc_actor_forget_all() {
    using namespace re4dc_material::life;
    for(unsigned k=0;k<kArchives;++k)if(archives[k].key)revoke(k);
    for(auto& i:infos_live)i={};for(auto& b:bindings)b={};changed();
}
extern "C" void re4dc_actor_data_move(const void* p) {
    using namespace re4dc_material::life;
    for(unsigned k=0;k<kArchives;++k)if(archives[k].key && span(archives[k].base,archives[k].bytes,p,1))revoke(k);
}
extern "C" void re4dc_actor_model_retire(cModel* m) {
    using namespace re4dc_material::life;
    // Also called on destruction: release the slot rather than accumulating
    // dead model addresses. A later binding receives a fresh monotonic token.
    for(auto& b:bindings)if(b.model==m){b={};return;}
}
extern "C" void re4dc_actor_model_changed(cModel* m) { re4dc_actor_model_retire(m); }
extern "C" unsigned re4dc_actor_binding_revision(cModel* m) {
    using namespace re4dc_material::life;
    if(!m || exhausted)return 0;
    Binding* free=nullptr;
    for(auto& b:bindings) {
        if(!b.model && !free)free=&b;
        if(b.model!=m)continue;
        if(b.serial!=m->serial || b.parts!=m->pParts || b.epoch!=epoch){b={m,m->pParts,m->serial,next(),epoch};}
        return b.revision;
    }
    if(!free)return 0;*free={m,m->pParts,m->serial,next(),epoch};return free->revision;
}
// Returns the unique currently-owned material row, never a pointer-only match.
// Multiple rows can share geometry but must resolve one exact TPL owner.
static const re4dc_material::Role* actor_current_role(cModel* m,cModelInfo* info,unsigned app,unsigned role) {
    using namespace re4dc_material;using namespace life;
    if(!m || exhausted)return nullptr;
    unsigned n=0;bool member=false;
    for(auto* p=m->pModelInfo;p && n<9;p=p->pList,++n)if(p==info)member=true;
    if(!member || n>8)return nullptr;
    auto* i=find_info(info);if(!i)return nullptr;
    const Role* found=nullptr;
    for(unsigned r=0;r<sizeof(roles)/sizeof(roles[0]);++r)
        if(roles[r].appearance==app && roles[r].role==role && info_current(*i,r)) {
            if(found)return nullptr;found=&roles[r];
        }
    return found;
}
extern "C" unsigned re4dc_actor_role_source_bin(cModel* m,cModelInfo* info,unsigned app,unsigned role) {
    const auto* r=actor_current_role(m,info,app,role);return r?r->source_bin:0;
}
extern "C" int re4dc_actor_material_owner_proof(cModel* m,cModelInfo* info,unsigned appearance,unsigned role,unsigned revision) {
    using namespace re4dc_material;using namespace life;
    if(!m || exhausted || revision!=RE4DC_ACTOR_MATERIAL_RECORD_REVISION)return 0;
    unsigned n=0;bool member=false;
    for(auto* p=m->pModelInfo;p && n<9;p=p->pList,++n)if(p==info)member=true;
    if(!member || n>8)return 0;
    auto* i=find_info(info);if(!i)return 0;
    for(unsigned r=0;r<sizeof(roles)/sizeof(roles[0]);++r)
        if(roles[r].appearance==appearance && roles[r].role==role && info_current(*i,r))return 1;
    return 0;
}
extern "C" int re4dc_actor_role_bindings(cModel* m,unsigned appearance,cModelInfo** out,unsigned count) {
    using namespace re4dc_material;using namespace life;
    if(!m || !out || (appearance==256?count!=8u:(count<4u || count>5u || (appearance==0 && count!=4u))) || exhausted){ATD(m,30,appearance,exhausted);return 0;}
    unsigned seen=0,n=0;for(unsigned k=0;k<count;++k)out[k]=nullptr;
    static const unsigned char leon_order[8]={0,1,2,3,4,7,5,6};
    for(auto* p=m->pModelInfo;p;p=p->pList) {
        if(n++==count){ATD(m,21,appearance,n);return 0;}auto* i=find_info(p);
#if RE4DC_CROWD_READOPT
        // Lane crowd (CROWD_READOPT=1): an info with no live record (dropped by a heap free / forget_range, or
        // set up before its archive was adopted) is proved again here with the load-time proof
        // (re4dc_actor_info_adopt: current asset sections, the reviewed TPL owner and row). Nothing is assumed:
        // an info that fails the proof stays unadopted and its actor keeps the source path.
        // =1: Ganados only (Leon keeps whichever path he has today); =2: Ganados and Leon (appearance 256).
        if(!i && (RE4DC_CROWD_READOPT==2 || appearance!=256)){re4dc_actor_info_adopt(p);i=find_info(p);CROWD_LIFE(++(i?crowd_readopt_ok:crowd_readopt_fail));}
#endif
        if(!i){ATD(m,22,appearance,n-1);return 0;}
        unsigned role=count;
        for(unsigned r=0;r<sizeof(roles)/sizeof(roles[0]);++r)
            if(roles[r].appearance==appearance && info_current(*i,r)) {if(role!=count && role!=roles[r].role){ATD(m,24,appearance,n-1);return 0;}role=roles[r].role;}
        const unsigned expected=appearance==256?leon_order[n-1]:n-1;
        if(role>=count || role!=expected || (seen&(1u<<role))){ATD(m,23,appearance,(n-1)*256+role);return 0;}out[role]=p;seen|=1u<<role;
    }
    if(n!=count || seen!=((1u<<count)-1)){ATD(m,25,n,seen);return 0;}return 1;
}
extern "C" unsigned re4dc_actor_stream_begin(const void* p,unsigned bytes) {
    using namespace re4dc_material::life;
    if(!p || !bytes || exhausted)return 0;
    for(unsigned k=0;k<kAssets;++k) {auto& a=assets[k];
        if(!a.data || !overlap(a.base,a.bytes,p,bytes))continue;
        if(!span(a.base,a.bytes,p,bytes) || !current(a)){revoke(a.archive);return 0;}
        // Only a recorded source ModelPart stream may transition to native.
        const auto* part=static_cast<const unsigned char*>(a.section[4]);
        const unsigned count=a.data->displist_num;
        for(unsigned n=0;n<count;++n) {
            if(!span(a.base,a.bytes,part,32))break;unsigned length=re4dc_material::u32at(part,24);
            if(!span(a.base,a.bytes,part+32,length))break;
            if(part+32==p && length==bytes) {
                if(a.pending){revoke(a.archive);return 0;}
                a.pending=next();return a.pending;
            }
            part+=32+length;
        }
        // A mutation in any other certified section invalidates its owner.
        revoke(a.archive);return 0;
    }
    return 0;
}
extern "C" void re4dc_actor_stream_end(unsigned ticket,const void* p,unsigned bytes) {
    using namespace re4dc_material::life;
    if(!ticket)return;
    for(auto& a:assets)if(a.data && a.pending==ticket) {
        if(!span(a.base,a.bytes,p,bytes)){revoke(a.archive);return;}
        a.pending=0;return;
    }
    // Retired during conversion: never resurrect a proof into a newer owner.
}
