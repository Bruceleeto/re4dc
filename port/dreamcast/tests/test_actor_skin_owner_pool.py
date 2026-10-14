"""Actual native actor skin ownership under ordinary-registry saturation.

Builds the complete native_actor_fast.cpp with its existing host CPU branches.
Model-source, one_qualifies and Leon lease lookup are extracted unchanged from
production. Only source-object layout, palette resolution/materialization and
hardware APIs are host boundaries. No target rendering/timing claim is made.
"""
from pathlib import Path
import hashlib,json,os,re,shlex,shutil,subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[3]
SHA=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

FIXTURE = r'''
#include "actor_native_owner.h"
#include "actor_palette_arena.h"
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <sys/mman.h>
#include <unistd.h>

// Source-object layout is a fixture boundary; the model-source function body
// below is extracted unchanged. Native skin/lease/cache types are production.
struct ModelData { void* vtxOrig; void* nrmOrig; unsigned nVtx,nNrm,weight_ext_num,weight_palette_num,flags; };
struct cModelInfo { ModelData* pData; };
struct HostGame { unsigned Frame_cnt; } host_game;
static HostGame* pG=&host_game;

// The complete production TU, with its existing host CPU branches. No skin,
// registration, materialization, cache or lifetime implementation is mocked.
#include "@NATIVE_SOURCE@"

@MODEL_SOURCE@
@ONE_QUALIFIES@
@LEON_SKIN_OF@

static unsigned checks=0,cases=0,materialize_calls=0,buffer_calls=0,resolve_calls=0;
static int materialize_result=1;
static const void* materialized_info;
static const float* materialized_palette;
static unsigned char ordinary_pos[32]{},ordinary_nrm[32]{},owned_pos[32]{},owned_nrm[32]{};
static unsigned char stream_bytes[64]{},uv_bytes[32]{};
static float palettes[2048][24]{};
static ModelData source_data[2048]{};
static cModelInfo infos[2048]{};
alignas(32) static unsigned char frame_workspace[128*1024];
alignas(32) static unsigned char palette_bank[65536];
static unsigned source_frame=200;

#define CHECK(x) do { ++checks; if(!(x)){std::fprintf(stderr,"FAIL %s:%d: %s\n",__FILE__,__LINE__,#x);std::exit(2);} }while(0)
extern "C" int re4dc_skin_materialize(const void* info,const float* palette) {
    ++materialize_calls;materialized_info=info;materialized_palette=palette;return materialize_result;
}
extern "C" int re4dc_actor_model_buffers(Re4dcModelPart* p) {
    ++buffer_calls;p->positions=ordinary_pos;p->normals=ordinary_nrm;return 1;
}
extern "C" void re4dc_skin_palette_resolve(const float* palette) {
    ++resolve_calls;volatile float alive=palette[0];(void)alive;
}
extern "C" void re4dc_log(const char*,...) {}
extern "C" int re4dc_model_diagnostic_enabled(){return 1;}

struct Bytes {
    std::array<unsigned char,sizeof(skins)> ordinary;
    std::array<unsigned char,sizeof(owned_skins)> owner;
    std::array<unsigned char,sizeof(frames)> cache;
    unsigned count,frame,serial;
#if RE4DC_ACTOR_SKIN_OWNER_POOL
    unsigned high;
#endif
    Bytes():count(skin_count),frame(skin_frame),serial(owned_skin_serial) {
        std::memcpy(ordinary.data(),skins,sizeof(skins));std::memcpy(owner.data(),owned_skins,sizeof(owned_skins));std::memcpy(cache.data(),frames,sizeof(frames));
#if RE4DC_ACTOR_SKIN_OWNER_POOL
        high=owned_skin_high;
#endif
    }
    void ordinary_same()const {CHECK(count==skin_count && frame==skin_frame);CHECK(!std::memcmp(ordinary.data(),skins,sizeof(skins)));}
    void all_same()const {
        ordinary_same();CHECK(serial==owned_skin_serial);CHECK(!std::memcmp(owner.data(),owned_skins,sizeof(owned_skins)));CHECK(!std::memcmp(cache.data(),frames,sizeof(frames)));
#if RE4DC_ACTOR_SKIN_OWNER_POOL
        CHECK(high==owned_skin_high);
#endif
    }
};
void seed_cache(const void* info,const float* palette) {
    for(auto& f:frames){f.info=info;f.palette=palette;f.positions=owned_pos;f.normals=owned_nrm;f.skin_positions=const_cast<float*>(palette);f.skin_dirs=const_cast<float*>(palette);}
}
void empty_cache(){for(const auto& f:frames)CHECK(!f.info && !f.palette && !f.positions && !f.normals && !f.skin_positions && !f.skin_dirs);}
void begin_case(const char* name) {
    ++cases;std::printf("CASE %s\n",name);re4dc_actor_frame(frame_workspace,sizeof(frame_workspace));
    host_game.Frame_cnt=++source_frame;
    CHECK(!re4dc_actor_skin_register(source_frame,nullptr,nullptr,nullptr,0));CHECK(skin_count==0);empty_cache();
}
void fill_ordinary() {
    for(unsigned i=0;i<64;++i)CHECK(re4dc_actor_skin_register(source_frame,&infos[i],nullptr,palettes[i],2));
    CHECK(skin_count==64);CHECK(!re4dc_actor_skin_register(source_frame,&infos[64],nullptr,palettes[64],2));
}
Re4dcActorSkinBinding binding(unsigned id,const float* palette=nullptr,unsigned entries=2) {
    return {&infos[id],{owned_pos,owned_nrm,3,3,entries,0},palette?palette:palettes[id],entries};
}
std::array<Re4dcActorSkinBinding,kRe4dcActorRoles> bindings(unsigned first) {
    std::array<Re4dcActorSkinBinding,kRe4dcActorRoles> out{};
    for(unsigned i=0;i<out.size();++i)out[i]=binding(first+i);return out;
}
Re4dcModelPart part(const void* info) {
    static re4dc::render::SourceLighting light{};
    Re4dcModelPart p{};p.info=info;p.position_stride=6;p.normal_stride=6;p.normal_shift=14;p.position_count=p.normal_count=3;
    p.stream=stream_bytes;p.stream_bytes=sizeof(stream_bytes);p.uv=uv_bytes;p.lighting=&light;p.viewport[2]=640;p.viewport[3]=480;return p;
}
void owner_view(const Re4dcActorSkinLease& lease,const Re4dcActorSkinBinding& b) {
    CHECK(re4dc_actor_skin_validate(&lease));auto* e=find_skin(b.info,nullptr);CHECK(e && !e->materialized && e->palette==b.palette);
    unsigned n=0;CHECK(re4dc_actor_skin_palette(b.info,nullptr,&n)==b.palette && n==b.entries);
    Re4dcActorSource source{};CHECK(re4dc_actor_owned_source(b.info,source_frame,&source));CHECK(!std::memcmp(&source,&b.source,sizeof(source)));
    Re4dcActorSource bridge{};CHECK(re4dc_actor_model_source(b.info,&bridge));CHECK(!std::memcmp(&bridge,&b.source,sizeof(bridge)));
    auto p=part(b.info);CHECK(lazy_skin(p));const SkinEntry* q=nullptr;Re4dcActorSource s{};CHECK(one_qualifies(p,q,s));CHECK(q==e && !std::memcmp(&s,&b.source,sizeof(s)));
    const SkinEntry* lean=nullptr;Re4dcActorSource ls{};CHECK(leon_skin_of(&lease,b.info,lean,ls));CHECK(lean==e && !std::memcmp(&ls,&b.source,sizeof(ls)));
}

void first_image() {
    ++cases;std::puts("CASE captured-first-image-source186-native187");
    for(unsigned i=0;i<187;++i)re4dc_actor_frame(frame_workspace,sizeof(frame_workspace));
    host_game.Frame_cnt=source_frame=186;CHECK(!re4dc_actor_skin_register(source_frame,nullptr,nullptr,nullptr,0));
    CHECK(frame_serial==187 && skin_frame==186);fill_ordinary();seed_cache(&infos[0],palettes[0]);
    const Bytes before;auto in=bindings(100);Re4dcActorSkinLease lease{};
    const int result=re4dc_actor_skin_acquire(source_frame,in.data(),in.size(),&lease);
#if RE4DC_ACTOR_SKIN_OWNER_POOL
    CHECK(result);before.ordinary_same();empty_cache();
    for(unsigned pass=0;pass<2;++pass)for(const auto& b:in)owner_view(lease,b);
    CHECK(re4dc_actor_skin_release(&lease));before.ordinary_same();CHECK(!lease.serial && !lease.count);
#else
    CHECK(!result);before.all_same();CHECK(!lease.serial && !lease.count);
#endif
}

#if RE4DC_ACTOR_SKIN_OWNER_POOL
void ordinary_collisions() {
    begin_case("ordinary-lazy-eager-materialized-collisions");
    for(unsigned i=0;i<64;++i)CHECK(re4dc_actor_skin_register(source_frame,&infos[i==3?1:i],i==1?ordinary_pos:nullptr,palettes[i],2));
    auto mat=part(&infos[2]);re4dc_actor_materialize(&mat);CHECK(find_ordinary_skin(&infos[2],nullptr)->materialized==1);
    const Bytes before;auto in=bindings(100);for(unsigned i=0;i<3;++i)in[i]=binding(i,palettes[100+i]);
    Re4dcActorSkinLease lease{};CHECK(re4dc_actor_skin_acquire(source_frame,in.data(),in.size(),&lease));before.ordinary_same();
    for(const auto& b:in){owner_view(lease,b);CHECK(!re4dc_actor_skin_register(source_frame,b.info,nullptr,palettes[999],2));CHECK(!re4dc_actor_skin_register(source_frame,b.info,ordinary_pos,palettes[999],2));}
    CHECK(find_skin(&infos[1],ordinary_pos)==find_ordinary_skin(&infos[1],ordinary_pos));unsigned count=0;CHECK(re4dc_actor_skin_palette(&infos[1],ordinary_pos,&count)==palettes[1] && count==2);
    CHECK(!re4dc_actor_skin_register(source_frame,&infos[900],nullptr,palettes[900],2));before.ordinary_same();
    CHECK(re4dc_actor_skin_release(&lease));before.ordinary_same();
    CHECK(find_skin(&infos[0],nullptr)==find_ordinary_skin(&infos[0],nullptr));CHECK(find_skin(&infos[1],nullptr)==find_ordinary_skin(&infos[1],nullptr));
    CHECK(re4dc_actor_skin_palette(&infos[1],nullptr,&count)==palettes[3] && count==2);
    CHECK(!re4dc_actor_skin_palette(&infos[2],nullptr,&count) && count==0);
    Re4dcActorSource fallback{};CHECK(re4dc_actor_model_source(&infos[0],&fallback));CHECK(fallback.positions==ordinary_pos && fallback.normals==ordinary_nrm);
    CHECK(re4dc_actor_skin_register(source_frame,&infos[0],nullptr,palettes[999],2));CHECK(skin_count==64 && find_ordinary_skin(&infos[0],nullptr)->palette==palettes[999]);
}
void admission_failures() {
    for(unsigned fault=0;fault<17;++fault){
        begin_case("atomic-admission-negative");fill_ordinary();auto in=bindings(100);Re4dcActorSkinLease lease{};
        unsigned n=in.size(),frame=source_frame;auto* input=in.data();auto* output=&lease;
        switch(fault){
        case 0:in.back().info=nullptr;break;case 1:in.back().palette=nullptr;break;case 2:in.back().entries=0;break;case 3:in.back().entries=257;break;
        case 4:in.back().source.positions=nullptr;break;case 5:in.back().source.normals=nullptr;break;case 6:in.back().source.position_count=0;break;case 7:in.back().source.normal_count=0;break;
        case 8:in.back().source.palette_entries=1;break;case 9:in.back().info=in[0].info;break;case 10:frame++;break;case 11:n=0;break;case 12:n=kRe4dcActorRoles+1;break;
        case 13:input=nullptr;break;case 14:output=nullptr;break;case 15:lease.serial=91;break;case 16:lease.count=1;break;
        }
        seed_cache(&infos[0],palettes[0]);const Bytes before;const auto old=lease;
        CHECK(!re4dc_actor_skin_acquire(frame,input,n,output));before.all_same();CHECK(!std::memcmp(&lease,&old,sizeof(old)));
    }
    begin_case("live-info-readmission-negative");fill_ordinary();auto in=bindings(100);Re4dcActorSkinLease a{},b{};CHECK(re4dc_actor_skin_acquire(source_frame,in.data(),in.size(),&a));
    auto other=bindings(200);other.back().info=in[0].info;seed_cache(in[0].info,in[0].palette);const Bytes before;
    CHECK(!re4dc_actor_skin_acquire(source_frame,other.data(),other.size(),&b));before.all_same();CHECK(!b.serial && !b.count);CHECK(re4dc_actor_skin_release(&a));
}
void hostile_handles() {
    for(unsigned fault=0;fault<13;++fault){
        begin_case("hostile-handle-full-serial-revocation");fill_ordinary();auto ia=bindings(100),ib=bindings(200);Re4dcActorSkinLease a{},b{};
        CHECK(re4dc_actor_skin_acquire(source_frame,ia.data(),ia.size(),&a));CHECK(re4dc_actor_skin_acquire(source_frame,ib.data(),ib.size(),&b));
        const auto good_a=a;auto bad=a;const Bytes before;std::array<OwnedEntry,kRe4dcActorRoles> protected_b{};
        for(unsigned k=0;k<b.count;++k)protected_b[k]=owned_skins[b.old[k].index];
        switch(fault){
        case 0:bad.count=0;break;case 1:--bad.count;break;case 2:bad.count=kRe4dcActorRoles+1;break;case 3:bad.old[0].index=owned_skin_high;break;case 4:bad.old[0].index=UINT32_MAX;break;
        case 5:bad.old[1].index=bad.old[0].index;break;case 6:++bad.frame;break;case 7:bad.old[0].info=&infos[999];break;case 8:bad.old[0].palette=palettes[999];break;
        case 9:++bad.old[0].entries;break;case 10:bad.old[0].positions=ordinary_pos;break;case 11:bad.old[0].materialized=1;break;case 12:bad.old[0].index=b.old[0].index;break;
        }
        CHECK(!re4dc_actor_skin_validate(&bad));CHECK(!re4dc_actor_skin_release(&bad));CHECK(!bad.serial && !bad.count);CHECK(!re4dc_actor_skin_validate(&good_a));
        for(unsigned k=0;k<good_a.count;++k)CHECK(!owned_skins[good_a.old[k].index].serial);
        CHECK(re4dc_actor_skin_validate(&b));for(unsigned k=0;k<b.count;++k)CHECK(!std::memcmp(&protected_b[k],&owned_skins[b.old[k].index],sizeof(OwnedEntry)));
        before.ordinary_same();empty_cache();CHECK(re4dc_actor_skin_release(&b));CHECK(owned_skin_high==0);
    }
    begin_case("stale-value-handle-does-not-release-new-owner");fill_ordinary();auto in=bindings(100);Re4dcActorSkinLease a{};
    CHECK(re4dc_actor_skin_acquire(source_frame,in.data(),in.size(),&a));auto stale=a;CHECK(re4dc_actor_skin_release(&a));
    Re4dcActorSkinLease b{};CHECK(re4dc_actor_skin_acquire(source_frame,in.data(),in.size(),&b));CHECK(b.serial!=stale.serial && b.old[0].index==stale.old[0].index);const Bytes before;
    CHECK(!re4dc_actor_skin_validate(&stale));CHECK(!re4dc_actor_skin_release(&stale));CHECK(re4dc_actor_skin_validate(&b));before.ordinary_same();CHECK(!std::memcmp(before.owner.data(),owned_skins,sizeof(owned_skins)));CHECK(re4dc_actor_skin_release(&b));
    CHECK(!re4dc_actor_skin_validate(nullptr));CHECK(!re4dc_actor_skin_release(nullptr));
    Re4dcActorSkinLease empty{};empty.count=7;CHECK(re4dc_actor_skin_release(&empty));CHECK(!empty.serial && !empty.count);
}
void materialization() {
    for(unsigned lazy=0;lazy<2;++lazy){
        begin_case("owned-materialization-invalidates-complete-lease");fill_ordinary();auto in=bindings(100);in[0]=binding(0,palettes[100]);Re4dcActorSkinLease lease{};
        CHECK(re4dc_actor_skin_acquire(source_frame,in.data(),in.size(),&lease));const Bytes before;auto p=part(in[0].info);const auto calls=materialize_calls;
        if(lazy)CHECK(re4dc_actor_materialize_lazy(&p));else re4dc_actor_materialize(&p);
        CHECK(materialize_calls==calls+1 && materialized_info==in[0].info && materialized_palette==in[0].palette);
        CHECK(find_skin(in[0].info,nullptr)!=find_ordinary_skin(in[0].info,nullptr));CHECK(find_skin(in[0].info,nullptr)->materialized==1);
        CHECK(!re4dc_actor_skin_validate(&lease));unsigned n=77;CHECK(!re4dc_actor_skin_palette(in[0].info,nullptr,&n) && n==0);
        Re4dcActorSource src{};CHECK(!re4dc_actor_owned_source(in[0].info,source_frame,&src));
        p=part(in[0].info);CHECK(!lazy_skin(p));const SkinEntry* se=nullptr;CHECK(!one_qualifies(p,se,src));
        const SkinEntry* ls=nullptr;CHECK(!leon_skin_of(&lease,in[0].info,ls,src));
        CHECK(!re4dc_actor_skin_release(&lease));CHECK(owned_skin_high==0);before.ordinary_same();empty_cache();
    }
    begin_case("failed-lazy-materialization-keeps-owner-and-ordinary-records");fill_ordinary();auto in=bindings(100);Re4dcActorSkinLease lease{};
    CHECK(re4dc_actor_skin_acquire(source_frame,in.data(),in.size(),&lease));auto p=part(in[0].info);const Bytes before;const unsigned prior_buffers=buffer_calls;
    materialize_result=0;CHECK(!re4dc_actor_materialize_lazy(&p));materialize_result=1;
    CHECK(!p.positions && !p.normals && buffer_calls==prior_buffers);before.all_same();CHECK(re4dc_actor_skin_validate(&lease));CHECK(re4dc_actor_skin_release(&lease));
}
void changed_entry_failures() {
    for(unsigned fault=0;fault<7;++fault){
        begin_case("changed-owned-entry-invalidates-and-revokes-whole-serial");fill_ordinary();auto ia=bindings(100),ib=bindings(200);Re4dcActorSkinLease a{},b{};
        CHECK(re4dc_actor_skin_acquire(source_frame,ia.data(),ia.size(),&a));CHECK(re4dc_actor_skin_acquire(source_frame,ib.data(),ib.size(),&b));const Bytes before;
        auto& e=owned_skins[a.old[a.count-1].index];
        switch(fault){case 0:e.skin.info=&infos[999];break;case 1:e.skin.positions=ordinary_pos;break;case 2:e.skin.palette=palettes[999];break;case 3:++e.skin.entries;break;case 4:e.source.positions=nullptr;break;case 5:e.source.normals=nullptr;break;case 6:++e.source.palette_entries;break;}
        CHECK(!re4dc_actor_skin_validate(&a));const auto old=a;CHECK(!re4dc_actor_skin_release(&a));for(unsigned k=0;k<old.count;++k)CHECK(!owned_skins[old.old[k].index].serial);
        before.ordinary_same();CHECK(re4dc_actor_skin_validate(&b));for(unsigned k=0;k<b.count;++k){const unsigned index=b.old[k].index;CHECK(!std::memcmp(before.owner.data()+index*sizeof(OwnedEntry),&owned_skins[index],sizeof(OwnedEntry)));}
        CHECK(re4dc_actor_skin_release(&b));CHECK(owned_skin_high==0);
    }
}
void maximum_owners() {
    begin_case("64-real-workspace-and-palette-owners-at-maximum-roles");fill_ordinary();const Bytes before;
    re4dc_actor::PaletteArena bank;CHECK(bank.bind(palette_bank,sizeof(palette_bank)));
    std::array<Re4dcActorSkinLease,64> leases{};std::array<Re4dcActorWorkspaceLease,64> work{};std::array<re4dc_actor::PaletteLease,64> pal{};
    for(unsigned owner=0;owner<64;++owner){
        CHECK(re4dc_actor_workspace_acquire(32,&work[owner]));CHECK(bank.acquire(kRe4dcActorRoles*64,pal[owner]));
        auto* bytes=static_cast<unsigned char*>(bank.data(pal[owner],kRe4dcActorRoles*64));CHECK(bytes);
        auto in=bindings(100+owner*kRe4dcActorRoles);for(unsigned k=0;k<in.size();++k)in[k]=binding(100+owner*kRe4dcActorRoles+k,reinterpret_cast<float*>(bytes+k*64),1);
        CHECK(re4dc_actor_skin_acquire(source_frame,in.data(),in.size(),&leases[owner]));CHECK(re4dc_actor_workspace_validate(&work[owner]));before.ordinary_same();
    }
    CHECK(owned_skin_high==kOwnedSkins && kOwnedSkins==64*kRe4dcActorRoles);for(const auto& lease:leases)CHECK(re4dc_actor_skin_validate(&lease));
    Re4dcActorWorkspaceLease no_work{};re4dc_actor::PaletteLease no_palette{};CHECK(!re4dc_actor_workspace_acquire(32,&no_work));CHECK(!bank.acquire(64,no_palette));
    auto extra=bindings(1000);Re4dcActorSkinLease no_skin{};const Bytes full;CHECK(!re4dc_actor_skin_acquire(source_frame,extra.data(),extra.size(),&no_skin));full.all_same();
    const auto stale=leases[17];for(unsigned i:{17u,41u}){CHECK(re4dc_actor_skin_release(&leases[i]));CHECK(bank.release(pal[i]));re4dc_actor_workspace_release(&work[i]);}
    CHECK(owned_skin_high==kOwnedSkins);
    for(unsigned i:{17u,41u}){
        CHECK(re4dc_actor_workspace_acquire(32,&work[i]));CHECK(bank.acquire(kRe4dcActorRoles*64,pal[i]));
        auto replacement=bindings(1000+i*kRe4dcActorRoles);CHECK(re4dc_actor_skin_acquire(source_frame,replacement.data(),replacement.size(),&leases[i]));CHECK(leases[i].old[0].index==i*kRe4dcActorRoles);
    }
    auto stale_copy=stale;const Bytes reused;CHECK(!re4dc_actor_skin_release(&stale_copy));CHECK(!std::memcmp(reused.owner.data(),owned_skins,sizeof(owned_skins)));before.ordinary_same();
    for(unsigned i=0;i<64;++i){CHECK(re4dc_actor_skin_release(&leases[i]));CHECK(bank.release(pal[i]));re4dc_actor_workspace_release(&work[i]);}
    CHECK(owned_skin_high==0);before.ordinary_same();bank.retire();
}
void protected_retirement() {
    for(unsigned mode=0;mode<4;++mode){
        begin_case("protected-borrowed-storage-retirement");fill_ordinary();const Bytes ordinary;
        const unsigned bytes=unsigned(sysconf(_SC_PAGESIZE));auto* memory=static_cast<unsigned char*>(mmap(nullptr,bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0));CHECK(memory!=MAP_FAILED);
        auto in=bindings(100);for(auto& b:in){b.palette=reinterpret_cast<float*>(memory);b.source.positions=memory+256;b.source.normals=memory+512;}
        Re4dcActorSkinLease lease{};CHECK(re4dc_actor_skin_acquire(source_frame,in.data(),in.size(),&lease));const auto stale=lease;seed_cache(in[0].info,in[0].palette);
        Re4dcActorWorkspaceLease work{};CHECK(re4dc_actor_workspace_acquire(32,&work));
        CHECK(mprotect(memory,bytes,PROT_NONE)==0);
        if(mode==0)CHECK(re4dc_actor_skin_release(&lease));
        if(mode==1){lease.count--;CHECK(!re4dc_actor_skin_release(&lease));}
        if(mode==2)re4dc_actor_frame(frame_workspace,sizeof(frame_workspace));
        if(mode==3){host_game.Frame_cnt=++source_frame;CHECK(re4dc_actor_skin_register(source_frame,&infos[900],nullptr,palettes[900],2));}
        CHECK(!re4dc_actor_skin_validate(&stale));CHECK(owned_skin_high==0);empty_cache();
        Re4dcActorSource src{};CHECK(!re4dc_actor_owned_source(in[0].info,source_frame,&src));CHECK(!find_owned_skin(in[0].info));
        if(mode!=3)ordinary.ordinary_same();else CHECK(skin_count==1 && skin_frame==source_frame);
        if(mode==2)CHECK(!re4dc_actor_workspace_validate(&work));else re4dc_actor_workspace_release(&work);
        auto bad=stale;CHECK(!re4dc_actor_skin_release(&bad));CHECK(munmap(memory,bytes)==0);
    }
}
void serial_exhaustion() {
    begin_case("serial-exhaustion-fails-closed");fill_ordinary();owned_skin_serial=UINT32_MAX;auto in=bindings(100);Re4dcActorSkinLease lease{};const Bytes before;
    CHECK(!re4dc_actor_skin_acquire(source_frame,in.data(),in.size(),&lease));before.all_same();re4dc_actor_owner_retire();CHECK(owned_skin_serial==UINT32_MAX);
    CHECK(!re4dc_actor_skin_acquire(source_frame,in.data(),in.size(),&lease));CHECK(!lease.serial && !lease.count);
}
#endif

int main(){
    static_assert(sizeof(void*)==4 && sizeof(SkinEntry)==20 && sizeof(Re4dcActorSource)==24,"32-bit production field layout");
    static_assert(sizeof(Re4dcActorSkinLease)==12+24*kRe4dcActorRoles,"lease value ABI retained");
    static_assert(re4dc_actor::WorkspaceReservations::MaxOwners==64,"existing reservation capacity");
    static_assert(sizeof(re4dc_actor::WorkspaceReservations)==520,"reservation object layout unchanged");
    for(unsigned i=0;i<2048;++i){source_data[i]={ordinary_pos,ordinary_nrm,3,3,0,2,0};infos[i]={&source_data[i]};palettes[i][0]=1;}
    first_image();
#if RE4DC_ACTOR_SKIN_OWNER_POOL
    ordinary_collisions();admission_failures();hostile_handles();materialization();changed_entry_failures();maximum_owners();protected_retirement();serial_exhaustion();
#endif
    std::printf("PASS pool=%u roles=%u cases=%u checks=%u sizeof_lease=%u sizeof_owner_table=%u\n",unsigned(RE4DC_ACTOR_SKIN_OWNER_POOL),kRe4dcActorRoles,cases,checks,unsigned(sizeof(Re4dcActorSkinLease)),unsigned(sizeof(owned_skins)));
}
'''


def extract(path,marker):
    text=path.read_text();start=text.index(marker);at=text.index('{',start);depth=1;end=at+1
    while depth:
        if text[end]=='{':depth+=1
        elif text[end]=='}':depth-=1
        end+=1
    value=text[start:end]
    return value,{'path':str(path.relative_to(ROOT)),'line':text[:start].count('\n')+1,'sha256':hashlib.sha256(value.encode()).hexdigest()}

def run_suite(output):
    output.mkdir(parents=True,exist_ok=False)
    game=ROOT/'port/dreamcast/game';native=game/'platform/native_actor_fast.cpp'
    flags_file=os.environ.get('RE4DC_OWNER_HOST_FLAGS')
    compiler_flags=json.loads(Path(flags_file).read_text())if flags_file else ['-m32']
    if flags_file:shutil.copyfile(flags_file,output/'host-flags.json')
    substitutions={'@NATIVE_SOURCE@':native.as_posix()};extractions=[]
    for key,path,marker in [('@MODEL_SOURCE@',game/'model_bridge.cpp','extern "C" int re4dc_actor_model_source('),('@ONE_QUALIFIES@',native,'bool one_qualifies('),('@LEON_SKIN_OF@',game/'platform/include/native_actor_leon_pipe.inc','bool leon_skin_of(')]:
        substitutions[key],meta=extract(path,marker);extractions.append(meta)
    cpp=FIXTURE
    for key,value in substitutions.items():cpp=cpp.replace(key,value)
    (output/'fixture.cpp').write_text(cpp)
    (output/'dc').mkdir();(output/'dc/pvr.h').write_text('#pragma once\n#include <cstddef>\n#include <cstdint>\nstruct pvr_vertex_t{std::uint32_t flags;float x,y,z,u,v;std::uint32_t argb,oargb;};\nstruct pvr_poly_hdr_t{std::uint32_t words[8];};\n#define PVR_CMD_VERTEX 0xe0000000U\n#define PVR_CMD_VERTEX_EOL 0xf0000000U\nint pvr_prim(const void*,std::size_t);\n')
    report={'status':'running','extractions':extractions,'arms':[],'policy':[],'limits':['Complete native actor TU uses its existing non-SH CPU/address branches.','Hardware packet submission is not executed. Palette materialization/resolution and source fallback object layouts are declared host boundaries.','The model-source body and one_qualifies/Leon lookup are byte-extracted production code. Two repeated consumer rounds are not source OT/gameplay or target-render execution.','Complete grouped-submit/Leon-pipe target syntax is not a host gate: the unchanged TU deliberately rejects store queues on non-SH hosts. The changed Leon lookup body is exercised by exact extraction.','Linked target BSS/end and default-off binary identity remain pending root authorization.']}
    dependencies={native,*[ROOT/x['path']for x in extractions],ROOT/'port/dreamcast/tests/test_actor_skin_owner_pool.py'}
    try:
        for pool,pl08 in [(0,0),(0,1),(1,0),(1,1)]:
            name=f'pool{pool}-pl08{pl08}';exe=output/name;dep=output/(name+'.d')
            command=['g++',*compiler_flags,'-std=c++20','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=all','-ffunction-sections','-fdata-sections','-Wl,--gc-sections','-DRE4DC_ACTOR_TEST=1','-DRE4DC_ACTOR_TRANSACTION=1',f'-DRE4DC_ACTOR_SKIN_OWNER_POOL={pool}',f'-DRE4DC_ACTOR_PL08={pl08}','-DRE4DC_NATIVE_ACTOR_SKIN_LAZY=1','-DRE4DC_SKIN_PALETTE_LAZY=1','-DRE4DC_ACTOR_LOG=0','-DRE4DC_COARSE_ONE_SUBMIT=0','-DRE4DC_COARSE_LEON=0','-I'+str(output),'-I'+str(game/'platform/include'),'-I'+str(game),'-MMD','-MF',str(dep),str(output/'fixture.cpp'),'-o',str(exe)]
            compile_result=subprocess.run(command,capture_output=True,text=True)
            (output/(name+'-compile.stdout')).write_text(compile_result.stdout);(output/(name+'-compile.stderr')).write_text(compile_result.stderr)
            arm={'pool':pool,'pl08':pl08,'command':command,'compile_returncode':compile_result.returncode};report['arms'].append(arm)
            if compile_result.returncode:raise AssertionError(f'{name} host compile failed; see {name}-compile.stderr')
            deptext=dep.read_text().replace('\\\n',' ');tokens=shlex.split(deptext.split(': ',1)[1])
            dependencies.update(Path(x).resolve()for x in tokens if Path(x).resolve().is_relative_to(ROOT))
            run=subprocess.run([str(exe)],capture_output=True,text=True,timeout=60)
            (output/(name+'-run.stdout')).write_text(run.stdout);(output/(name+'-run.stderr')).write_text(run.stderr)
            arm.update(run_returncode=run.returncode,binary_sha256=SHA(exe))
            if run.returncode:raise AssertionError(f'{name} host run failed: {run.stderr}')
            match=re.search(r'PASS pool=(\d+) roles=(\d+) cases=(\d+) checks=(\d+) sizeof_lease=(\d+) sizeof_owner_table=(\d+)',run.stdout)
            if not match:raise AssertionError(f'{name} missing PASS receipt')
            arm['result']=dict(zip(['pool','roles','cases','checks','sizeof_lease','sizeof_owner_table'],map(int,match.groups())))
        make=game/'crowd.mk';text=make.read_text();start=text.index('# Isolate transaction skin entries');policy=text[start:]
        (output/'policy.mk').write_text('OBJDIR:=host-obj\n'+policy+'\nhost-obj/platform/native_actor_fast.o:\n\t@echo FLAGS=$(PLATFORM_CPPFLAGS)\n')
        dependencies.add(make)
        for pool,tx,okay,want in [('default','1',True,False),('0','1',True,False),('1','1',True,True),('2','1',False,False),('1','0',False,False)]:
            command=['make','--no-print-directory','-f',str(output/'policy.mk'),'-n','host-obj/platform/native_actor_fast.o','ACTOR_TRANSACTION='+tx]
            if pool!='default':command.append('ACTOR_SKIN_OWNER_POOL='+pool)
            result=subprocess.run(command,capture_output=True,text=True)
            report['policy'].append({'pool':pool,'transaction':tx,'command':command,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
            assert (result.returncode==0)==okay
            if okay:assert ('-DRE4DC_ACTOR_SKIN_OWNER_POOL=1'in result.stdout)==want
        report['status']='passed'
    except BaseException as error:
        report['status']='failed';report['error']=repr(error);raise
    finally:
        manifest={str(path.relative_to(ROOT)):SHA(path)for path in sorted(dependencies)if path.is_file()}
        report['source_manifest']=manifest
        for path in dependencies:
            if path.is_file():
                dest=output/'source'/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,dest)
        (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'arms':[arm['result']for arm in report['arms']],'policy_checks':len(report['policy'])},indent=2))
    return report

@unittest.skipUnless(shutil.which('g++')and shutil.which('make'),'host C++ and make required')
class ActorSkinOwnerPool(unittest.TestCase):
    def test_actual_source_ownership(self):
        keep=os.environ.get('RE4DC_OWNER_TEST_OUTPUT')
        if keep:run_suite(Path(keep))
        else:
            with tempfile.TemporaryDirectory()as tmp:run_suite(Path(tmp)/'case')

if __name__=='__main__':unittest.main()
