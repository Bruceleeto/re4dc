#!/usr/bin/env python3
"""Exercise actual reservation, source plan, skin readers and owner lifecycle.

Host proof: synthetic source objects and palettes, actual implementation bodies.
No target ABI, visual or hardware-performance acceptance is inferred.
"""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
INCLUDE = ROOT / "port/dreamcast/game/platform/include"


def function(text, marker):
    start = text.index(marker)
    begin = text.index("{", start)
    depth, end = 1, begin + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def native_prefix():
    fast = (ROOT / "port/dreamcast/game/platform/native_actor_fast.cpp").read_text()
    begin = fast.index("struct SkinEntry {")
    end = fast.index("\n\n", fast.index("    return nullptr;", begin))
    result = r"""
#include <cassert>
#include <cstdio>
#include <cstring>
#include <climits>
#include <cstdarg>
#include "actor_native_owner.h"
extern "C" void re4dc_log(const char*,...){}
""" + fast[begin:end] + r"""
#include "native_actor_owner_registry.inc"
#if RE4DC_ACTOR_SKIN_RESERVE
#include "native_actor_skin_reserve.inc"
#endif
struct Frame { unsigned dummy=0; }; Frame frames[4];
unsigned char* workspace; unsigned workspace_bytes,workspace_top,workspace_end,frame_serial;
unsigned lod_budget,lod_budget_frame;bool lod_wanted_last,lod_wanted;
constexpr bool kCrowd=false;void crowd_rank(){}
Re4dcActorStats stats{};
#include "native_actor_owner_workspace.inc"
unsigned materialize_calls,resolve_calls,buffer_calls;bool materialize_ok=true;
unsigned char fallback_pos[8]{},fallback_nrm[8]{};
extern "C" int re4dc_skin_materialize(const void*,const float* palette){assert(palette);++materialize_calls;return materialize_ok;}
extern "C" void re4dc_skin_palette_resolve(const float* palette){assert(palette);++resolve_calls;}
extern "C" int re4dc_actor_model_buffers(Re4dcModelPart* p){++buffer_calls;p->positions=fallback_pos;p->normals=fallback_nrm;return 1;}
"""
    for marker in ('extern "C" void re4dc_actor_frame(', 'extern "C" int re4dc_actor_skin_register(',
                   'extern "C" const float* re4dc_actor_skin_palette(', 'extern "C" void re4dc_actor_materialize(',
                   'extern "C" int re4dc_actor_materialize_lazy('):
        result += function(fast, marker) + "\n"
    return result + r"""
unsigned checks;void check(bool value){if(!value)std::fprintf(stderr,"failed check %u\n",checks+1);assert(value);++checks;}
struct Snapshot {
 SkinEntry source[kSkins];OwnedSkin owned[kSkins];unsigned count,frame,serial;
 Snapshot():count(skin_count),frame(skin_frame),serial(owned_skin_serial){
  std::memcpy(source,skins,sizeof skins);std::memcpy(owned,owned_skins,sizeof owned_skins);
 }
 bool same()const{return count==skin_count && frame==skin_frame && serial==owned_skin_serial &&
  !std::memcmp(source,skins,sizeof skins) && !std::memcmp(owned,owned_skins,sizeof owned_skins);}
};
"""


def registry_harness():
    return native_prefix() + r"""
int main(){
 int infos[100]{};unsigned char pos[32]{},nrm[32]{};float source_palette[12]{},owner_palette[12]{};
 const void* player[kRe4dcActorRoles];Re4dcActorSkinBinding bind[kRe4dcActorRoles];
 for(unsigned i=0;i<kRe4dcActorRoles;++i){player[i]=&infos[i];bind[i]={player[i],{pos,nrm,2,2,1,0},owner_palette,1};}
 auto fill=[&](unsigned frame,unsigned first,unsigned n){for(unsigned i=first;i<first+n;++i)check(re4dc_actor_skin_register(frame,&infos[i],nullptr,source_palette,1));};
 Re4dcActorSkinLease lease{};
 // The observed failure: a full lazy/unowned source table has no player key.
 fill(185,16,64);Snapshot full;
 check(!re4dc_actor_skin_acquire(185,bind,kRe4dcActorRoles,&lease) && full.same() && !lease.serial);
 check(!re4dc_actor_skin_reserve(185,player,kRe4dcActorRoles) && full.same());
 // A bad batch cannot even change the frame owner.
 check(!re4dc_actor_skin_reserve(186,nullptr,kRe4dcActorRoles) && full.same());
 check(!re4dc_actor_skin_reserve(186,player,0) && full.same());
 check(!re4dc_actor_skin_reserve(186,player,kSkins+1) && full.same());
 const void* bad[kRe4dcActorRoles];std::memcpy(bad,player,sizeof bad);bad[kRe4dcActorRoles-1]=nullptr;
 check(!re4dc_actor_skin_reserve(186,bad,kRe4dcActorRoles) && full.same());bad[kRe4dcActorRoles-1]=bad[0];
 check(!re4dc_actor_skin_reserve(186,bad,kRe4dcActorRoles) && full.same());
 check(re4dc_actor_skin_reserve(186,player,kRe4dcActorRoles));check(skin_count==kRe4dcActorRoles && skin_frame==186);
 // Inert reservations cannot resolve palettes, materialize or grant ownership.
 for(unsigned i=0;i<kRe4dcActorRoles;++i){unsigned entries=99;Re4dcActorSource source{};
  check(!re4dc_actor_skin_palette(player[i],nullptr,&entries) && !entries);
  Re4dcModelPart p{};p.info=player[i];re4dc_actor_materialize(&p);
  check(!re4dc_actor_materialize_lazy(&p) && !p.positions && !p.normals);
  check(!re4dc_actor_owned_source(player[i],186,&source));
 }
 check(!materialize_calls && !resolve_calls && !buffer_calls);Snapshot placeholders;
 check(re4dc_actor_skin_reserve(186,player,kRe4dcActorRoles) && placeholders.same());
 check(!re4dc_actor_skin_acquire(185,bind,kRe4dcActorRoles,&lease) && placeholders.same());
 // Ordinary source order is retained. Unrelated deferrals fill only remaining
 // slots; their first excess uses the existing eager fallback (register==0).
 fill(186,16,64-kRe4dcActorRoles);check(skin_count==64);
 Snapshot filled;check(!re4dc_actor_skin_register(186,&infos[90],nullptr,source_palette,1) && filled.same());
 // Rigid/morphed roles need no source deferral; other player slots are filled
 // by the unmodified same-info source registration, despite the full table.
 for(unsigned i=0;i<kRe4dcActorRoles;++i)if(i!=3 && i!=6)
  check(re4dc_actor_skin_register(186,player[i],nullptr,source_palette,1));
 Snapshot prepared;auto invalid=bind[kRe4dcActorRoles-1];bind[kRe4dcActorRoles-1].entries=0;
 check(!re4dc_actor_skin_acquire(186,bind,kRe4dcActorRoles,&lease) && prepared.same());bind[kRe4dcActorRoles-1]=invalid;
 check(re4dc_actor_skin_acquire(186,bind,kRe4dcActorRoles,&lease));check(re4dc_actor_skin_validate(&lease));
 const unsigned player_serial=lease.serial;Snapshot first_pass;
 check(!re4dc_actor_skin_reserve(186,player,kRe4dcActorRoles) && first_pass.same());
 check(!re4dc_actor_skin_register(186,player[0],nullptr,source_palette,1) && first_pass.same());
 // Between the player's two passes, unrelated source palettes and another
 // native owner remain readable. No source entry was borrowed or evicted.
 for(unsigned i=16;i<16+64-kRe4dcActorRoles;++i){unsigned entries=0;
  check(re4dc_actor_skin_palette(&infos[i],nullptr,&entries)==source_palette && entries==1);
 }
 Re4dcActorSkinBinding other{&infos[16],{pos,nrm,2,2,1,0},owner_palette,1};Re4dcActorSkinLease other_lease{};
 check(re4dc_actor_skin_acquire(186,&other,1,&other_lease));check(re4dc_actor_skin_validate(&lease));
 check(re4dc_actor_skin_release(&other_lease));check(re4dc_actor_skin_validate(&lease) && lease.serial==player_serial);
 check(re4dc_actor_skin_release(&lease));
 for(unsigned i=0;i<kSkins;++i){check(!std::memcmp(&skins[i],&prepared.source[i],sizeof(SkinEntry)));check(!owned_skins[i].serial);}
 // Source fallback works after a native decline/release; a real deferred
 // palette materializes once, while rigid/morph placeholders remain inert.
 Re4dcModelPart p{};p.info=player[0];check(re4dc_actor_materialize_lazy(&p));check(materialize_calls==1 && buffer_calls==1);
 const auto source_materialized=skins[0];check(re4dc_actor_skin_acquire(186,bind,kRe4dcActorRoles,&lease));
 check(re4dc_actor_skin_release(&lease));check(!std::memcmp(&source_materialized,&skins[0],sizeof(SkinEntry)));
 p={};p.info=player[3];check(!re4dc_actor_materialize_lazy(&p) && materialize_calls==1);
 // A render workspace bind retires ownership, not source reservations. It
 // cannot make a placeholder a palette or initialize an unrelated frame.
 alignas(32) unsigned char ws[1024];re4dc_actor_frame(ws,sizeof ws);
 check(skin_frame==186 && find_skin(player[3],nullptr) && !find_skin(player[3],nullptr)->palette);
 check(!re4dc_actor_skin_acquire(187,bind,kRe4dcActorRoles,&lease));
 // Partial-capacity refusal leaves every attempted slot and serial untouched.
 fill(187,16,61);Snapshot partial;check(!re4dc_actor_skin_reserve(187,player,kRe4dcActorRoles) && partial.same());
 check(re4dc_actor_skin_reserve(188,player,kRe4dcActorRoles));check(re4dc_actor_skin_acquire(188,bind,kRe4dcActorRoles,&lease));
 Re4dcActorSkinLease stale=lease;
 check(re4dc_actor_skin_reserve(189,player,kRe4dcActorRoles));Re4dcActorSkinLease current{};
 check(re4dc_actor_skin_acquire(189,bind,kRe4dcActorRoles,&current));check(!re4dc_actor_skin_validate(&stale));
 check(!re4dc_actor_skin_release(&stale));check(re4dc_actor_skin_validate(&current));check(re4dc_actor_skin_release(&current));
 // Whole-table batches use exactly the existing 64 slots; the 65th key
 // declines before reading it or changing any owner/frame/source entry.
 const void* batch[kSkins];for(unsigned i=0;i<kSkins;++i)batch[i]=&infos[i];
 check(re4dc_actor_skin_reserve(190,batch,kSkins) && skin_count==kSkins);Snapshot all_keys;
 check(!re4dc_actor_skin_reserve(191,batch,kSkins+1) && all_keys.same());
 check(re4dc_actor_skin_reserve(190,batch,kSkins) && all_keys.same());
 // Source-register frame advancement alone also retires all old placeholders.
 check(re4dc_actor_skin_register(191,&infos[99],nullptr,source_palette,1));check(skin_count==1 && !find_skin(player[3],nullptr));
 check(re4dc_actor_skin_reserve(191,player,kRe4dcActorRoles));owned_skin_serial=UINT_MAX;Snapshot exhausted;
 current={};check(!re4dc_actor_skin_acquire(191,bind,kRe4dcActorRoles,&current) && exhausted.same());
 // Existing positioned source keys are never overwritten by reservations.
 owned_skin_serial=0;check(re4dc_actor_skin_register(192,player[0],pos,source_palette,1));
 check(re4dc_actor_skin_reserve(192,player,kRe4dcActorRoles));check(skin_count==kRe4dcActorRoles+1);
 check(find_skin(player[0],pos)->palette==source_palette && !find_skin(player[0],nullptr)->palette);
 // Released append slots are reusable holes; reservation never grows the
 // table when an existing empty slot can hold the exact new key.
 fill(193,16,62);Re4dcActorSkinBinding missing{player[0],{pos,nrm,2,2,1,0},owner_palette,1};current={};
 check(re4dc_actor_skin_acquire(193,&missing,1,&current));check(skin_count==63);
 check(re4dc_actor_skin_release(&current) && !skins[62].info);
 check(re4dc_actor_skin_reserve(193,player,1) && skin_count==63 && skins[62].info==player[0]);
 for(unsigned value:infos)check(value==0);for(float value:source_palette)check(value==0);for(float value:owner_palette)check(value==0);
 std::printf("PASS actual reserve/registry roles=%u checks=%u: bounded slots, inert placeholders, eager fallback, atomic rollback and two-pass interleaving\n",kRe4dcActorRoles,checks);
}
"""


def source_harness():
    trans = (ROOT / "src/game/trans.cpp").read_text()
    result = native_prefix() + r"""
#include "coarse_source_frame.h"
using namespace re4dc_source;
struct cModelInfo {cModelInfo* pList;unsigned role,kind;unsigned char source_bytes[20];};
struct cUnit {cUnit* pNext;};
struct cModel:cUnit {unsigned serial,id;cModelInfo* pModelInfo;unsigned nParts;};
struct Global {unsigned Frame_cnt,stage_no,room_no,prim_cnt,nPrim,vtx_buf_no;};
Global globals{400,1,3,100,200,0};Global* pG=&globals;
cModel* pPL; cModel* pSUB;
struct Manager {cUnit* pAlive;unsigned nArray;};Manager EmMgr;
unsigned re4dc_alive_gen[3]{0,1,1};unsigned room_generation=1;bool room_valid=true,storage_ok=true;
unsigned sourceActorEpoch,sourceActorFailures,sourceActorCount;
unsigned sourceActorPrimBase,sourceActorPrimBytes,sourceActorPrimBuffer;
bool sourceActorActive,sourceActorRenderActive;
FrameLedger sourceActorLedger;
alignas(FrameEntry) unsigned char source_storage[FrameLedger::MaxEntries*sizeof(FrameEntry)];
extern "C" int re4dc_room4_state(unsigned* g,unsigned* c,unsigned* b,unsigned* s,unsigned* r){*g=room_generation;*c=*b=*s=*r=0;return room_valid;}
extern "C" void* re4dc_prim_tail(unsigned bytes,unsigned){return storage_ok && bytes<=sizeof source_storage?source_storage:nullptr;}
extern "C" void re4dc_actor_transaction_retire(){re4dc_actor_owner_retire();}
void sourceActorFailure(unsigned){++sourceActorFailures;}
#if RE4DC_ACTOR_EARLY_COARSE
cModel* early_model;
extern "C" int re4dc_actor_early_coarse_admit(cModel* m,Re4dcActorEarlyTicket* ticket){
 if(m!=early_model)return 0;ticket->texture.slot=ticket->texture.serial=ticket->binding_revision=1;return 1;
}
extern "C" void re4dc_actor_texture_release(Re4dcActorTextureLease*){}
extern "C" void re4dc_actor_texture_retire_all(){}
#endif
unsigned prepared_order[256],prepared_n,eager_count,deferred_count;float source_palette[12]{};
void emTrans(cModel* m){
 prepared_order[prepared_n++]=m->id;
 for(cModelInfo* info=m->pModelInfo;info;info=info->pList){
  if(info->kind || !re4dc_actor_skin_register(pG->Frame_cnt,info,nullptr,source_palette,1))++eager_count;
  else ++deferred_count;
 }
}
"""
    registry = (ROOT / "port/dreamcast/game/coarse_actor_owner_registry.inc").read_text()
    result += r"""
struct Descriptor {unsigned model_id,bones;};
Descriptor descriptors[]{{0x26,27},{0x28,19}};
struct Registry {unsigned descriptor_count;Descriptor* descriptors;} registry{2,descriptors};
unsigned registry_id_mask[8]{};bool registry_mask_ready;
"""
    result += function(registry, "bool registry_id(") + "\n"
    result += function(registry, 'extern "C" int re4dc_registry_candidate(') + "\n"
    for marker in ('bool sourceActorRam(', 'void sourceActorRetire(', 'bool sourceActorIdentity(',
                   'ModelIdentity sourceActorModel(', 'ModelPath sourceActorPath(',
                   'static bool sourceActorNativeOwner(', 'static int sourceActorReserveNative(', 'int sourceActorPlan(', 'bool sourceActorPrepare('):
        result += function(trans, marker) + "\n"
        if marker == 'ModelIdentity sourceActorModel(':
            first = trans.index('#if RE4DC_ACTOR_EARLY_COARSE\n// This synchronous')
            last = trans.index('ModelPath sourceActorPath(', first)
            result += trans[first:last]
    return result + r"""
#include "source_actor_owner_hooks.inc"
int main(){
 cModelInfo infos[160]{};for(unsigned i=0;i<160;++i){infos[i].role=i;std::memset(infos[i].source_bytes,int(i),sizeof infos[i].source_bytes);}
 for(unsigned i=0;i<kRe4dcActorRoles-1;++i)infos[i].pList=&infos[i+1];
 infos[3].kind=1;infos[6].kind=2; // actual source omits lazy deferral for morph/rigid
 for(unsigned i=16;i<24;i+=2)infos[i].pList=&infos[i+1];
 cModel player{{nullptr},10,0,&infos[0],24};
 cModel animals[4]{{{&animals[1]},20,0x26,&infos[16],27},{{&animals[2]},21,0x26,&infos[18],27},
                   {{&animals[3]},22,0x28,&infos[20],19},{{&player},23,0x28,&infos[22],19}};
 pPL=&player;EmMgr={animals,5};pSUB=nullptr;
 cModelInfo original[160];std::memcpy(original,infos,sizeof infos);
 cModel original_player=player,original_animals[4];std::memcpy(original_animals,animals,sizeof animals);
 const unsigned animal_keys=RE4DC_NATIVE_MODEL_REGISTRY?8:0;
 const unsigned reserved=kRe4dcActorRoles+animal_keys;
 check(sourceActorPlan()==1);check(skin_frame==400 && skin_count==reserved);
 check(!std::memcmp(original,infos,sizeof infos) && !std::memcmp(&original_player,&player,sizeof player) && !std::memcmp(original_animals,animals,sizeof animals));
 FrameIdentity planned{};check(sourceActorIdentity(planned));const auto planned_player=sourceActorModel(pPL);
 sourceActorRenderActive=true;FrameIdentity out{};ModelIdentity model{};
 check(re4dc_actor_transaction_identity(pPL,&out,&model)==-1); // reservation is no preparation ticket
 unsigned choice=0;check(!re4dc_actor_transaction_choose(pPL,2));
 check(!sourceActorNativeOwner(nullptr));
 // Shared predicate nominates exactly the same models for reservation and the
 // original OT path. A wrong skeleton or source partner never gains priority.
 check(sourceActorNativeOwner(&player) && re4dc_actor_transaction_candidate(&player)==1);
 for(auto& animal:animals)check(sourceActorNativeOwner(&animal)==bool(RE4DC_NATIVE_MODEL_REGISTRY) &&
  re4dc_actor_transaction_candidate(&animal)==int(RE4DC_NATIVE_MODEL_REGISTRY));
 ++animals[0].nParts;check(!sourceActorNativeOwner(&animals[0]));--animals[0].nParts;
 pSUB=&animals[0];check(!sourceActorNativeOwner(&animals[0]));pSUB=nullptr;
 cModel enemy{{nullptr},99,0x13,&infos[159],17};check(sourceActorNativeOwner(&enemy));
 pSUB=&enemy;check(!sourceActorNativeOwner(&enemy));pSUB=nullptr;
 // Synthetic ObjMgr callbacks run first in their original order. The plan
 // has not called source preparation, initialized palettes or granted owners.
 check(!prepared_n && !deferred_count && !eager_count);
 for(unsigned i=64;i<128;++i){cModel object{{nullptr},100+i,0x100+i,&infos[i],1};emTrans(&object);}
 check(sourceActorPrepare());check(prepared_n==69);
 for(unsigned i=0;i<64;++i)check(prepared_order[i]==0x140+i);
 for(unsigned i=0;i<4;++i)check(prepared_order[64+i]==animals[i].id);
 check(prepared_order[68]==0);
 check(re4dc_actor_transaction_identity(pPL,&out,&model)==1);
 check(re4dc_actor_transaction_choice(pPL,&choice) && choice==0);
 check(deferred_count==64-2 && eager_count==64+8+kRe4dcActorRoles-deferred_count);
 check(skin_count==64);check(!std::memcmp(original,infos,sizeof infos));
 // All five current native owners coexist across both passes despite the 64
 // earlier registrations. Each owner retains only its existing bounded lease.
 unsigned char pos[32]{},nrm[32]{};float owner_palette[12]{};
 Re4dcActorSkinLease leases[5]{};Snapshot source_prepared;
 for(unsigned owner=0;owner<(RE4DC_NATIVE_MODEL_REGISTRY?5u:1u);++owner){
  cModel* m=owner?&animals[owner-1]:&player;Re4dcActorSkinBinding bind[kRe4dcActorRoles]{};unsigned n=0;
  for(auto* info=m->pModelInfo;info;info=info->pList)bind[n++]={info,{pos,nrm,2,2,1,0},owner_palette,1};
  check(re4dc_actor_skin_acquire(400,bind,n,&leases[owner]));
  for(unsigned previous=0;previous<=owner;++previous)check(re4dc_actor_skin_validate(&leases[previous]));
 }
 Snapshot owned;check(!sourceActorReserveNative(planned,planned_player) && owned.same());
 for(unsigned owner=0;owner<(RE4DC_NATIVE_MODEL_REGISTRY?5u:1u);++owner){
  check(re4dc_actor_skin_validate(&leases[owner]));check(re4dc_actor_skin_release(&leases[owner]));
  for(unsigned next=owner+1;next<(RE4DC_NATIVE_MODEL_REGISTRY?5u:1u);++next)check(re4dc_actor_skin_validate(&leases[next]));
 }
 check(!std::memcmp(source_prepared.source,skins,sizeof skins));
 Snapshot before;
 ++player.serial;check(!sourceActorReserveNative(planned,planned_player) && before.same());--player.serial;
 ++animals[2].serial;check(!sourceActorReserveNative(planned,planned_player) && before.same());--animals[2].serial;
 auto* saved_player=pPL;pPL=&animals[0];check(!sourceActorReserveNative(planned,planned_player) && before.same());pPL=saved_player;
 pSUB=&animals[0];check(!sourceActorReserveNative(planned,planned_player) && before.same());pSUB=nullptr;
 for(unsigned field=0;field<6;++field){FrameIdentity wrong=planned;
  switch(field){case 0:++wrong.frame;break;case 1:++wrong.room;break;case 2:++wrong.room_generation;break;
   case 3:++wrong.primitive_epoch;break;case 4:++wrong.enemy_generation;break;case 5:++wrong.object_generation;break;}
  check(!sourceActorReserveNative(wrong,planned_player) && before.same());
 }
 ++globals.prim_cnt;check(!sourceActorReserveNative(planned,planned_player) && before.same());--globals.prim_cnt;
 ++globals.nPrim;check(!sourceActorReserveNative(planned,planned_player) && before.same());--globals.nPrim;
 ++globals.vtx_buf_no;check(!sourceActorReserveNative(planned,planned_player) && before.same());--globals.vtx_buf_no;
 // Malformed source traversal or any candidate chain refuses the entire batch.
 --EmMgr.nArray;check(!sourceActorReserveNative(planned,planned_player) && before.same());++EmMgr.nArray;
 animals[2].pNext=&player;check(!sourceActorReserveNative(planned,planned_player) && before.same());animals[2].pNext=&animals[3];
 player.pNext=&animals[0];check(!sourceActorReserveNative(planned,planned_player) && before.same());player.pNext=nullptr;
 infos[kRe4dcActorRoles-1].pList=&infos[0];check(!sourceActorReserveNative(planned,planned_player) && before.same());
 infos[kRe4dcActorRoles-1].pList=&infos[15];check(!sourceActorReserveNative(planned,planned_player) && before.same());
 infos[kRe4dcActorRoles-1].pList=nullptr;player.pModelInfo=nullptr;
 check(!sourceActorReserveNative(planned,planned_player) && before.same());player.pModelInfo=infos;
#if RE4DC_NATIVE_MODEL_REGISTRY
 animals[3].pModelInfo=nullptr;check(!sourceActorReserveNative(planned,planned_player) && before.same());animals[3].pModelInfo=&infos[22];
 infos[23].pList=&infos[22];check(!sourceActorReserveNative(planned,planned_player) && before.same());infos[23].pList=nullptr;
#endif
 // Plan failure does not change reservations or skip original source callbacks.
 ++globals.Frame_cnt;animals[3].pNext=nullptr;check(sourceActorPlan()==0 && skin_frame==400);animals[3].pNext=&player;
 storage_ok=false;check(sourceActorPlan()==0 && skin_frame==400);storage_ok=true;
 room_valid=false;check(sourceActorPlan()==0 && skin_frame==400);room_valid=true;
 check(sourceActorPlan()==1 && skin_frame==401 && skin_count==reserved);
 check(!std::memcmp(original,infos,sizeof infos));
 // Sharing a real info between actors deduplicates storage priority, without
 // weakening the later rule that a live owner cannot be borrowed by another.
 ++globals.Frame_cnt;animals[1].pModelInfo=animals[0].pModelInfo;
 check(sourceActorPlan()==1 && skin_count==reserved-(RE4DC_NATIVE_MODEL_REGISTRY?2:0));
#if RE4DC_NATIVE_MODEL_REGISTRY
 Re4dcActorSkinBinding shared{animals[0].pModelInfo,{pos,nrm,2,2,1,0},owner_palette,1};
 Re4dcActorSkinLease first{},second{};check(re4dc_actor_skin_acquire(402,&shared,1,&first));Snapshot shared_owned;
 check(!re4dc_actor_skin_acquire(402,&shared,1,&second) && shared_owned.same());check(re4dc_actor_skin_release(&first));
#endif
 animals[1].pModelInfo=&infos[18];
#if RE4DC_ACTOR_EARLY_COARSE
 // A sealed coarse choice keeps its existing admission; no source key or
 // source callback is requested by this storage-priority extension.
 ++globals.Frame_cnt;early_model=&animals[0];prepared_n=eager_count=deferred_count=0;
 check(sourceActorPlan()==1 && skin_count==reserved-(RE4DC_NATIVE_MODEL_REGISTRY?2:0));
 check(sourceActorPrepare() && prepared_n==4 && prepared_order[0]==0x26 && prepared_order[3]==0);
 early_model=nullptr;
#endif
 // More than 64 unique eligible keys: no partial reservation, even when each
 // individual chain is legal. Exactly 64 succeeds; a shared 65th also fits.
 cModel many[65]{};cModelInfo many_infos[65]{};
 for(unsigned i=0;i<65;++i){many[i]={{i==64?nullptr:&many[i+1]},200+i,0x13,&many_infos[i],1};}
 pPL=many;EmMgr={many,65};++globals.Frame_cnt;Snapshot too_many;
 check(sourceActorPlan()==1 && too_many.same());
 check(sourceActorIdentity(planned));auto many_player=sourceActorModel(pPL);
 check(!sourceActorReserveNative(planned,many_player) && too_many.same());
 many[63].pNext=nullptr;EmMgr.nArray=64;check(sourceActorPlan()==1 && skin_frame==globals.Frame_cnt && skin_count==64);
 ++globals.Frame_cnt;many[63].pNext=&many[64];many[64].pModelInfo=&many_infos[63];EmMgr.nArray=65;
 check(sourceActorPlan()==1 && skin_count==64);
 sourceActorRetire();Snapshot retired;check(!sourceActorReserveNative(planned,many_player) && retired.same());
 std::printf("PASS actual source plan/hook roles=%u early=%u registry=%u checks=%u: five owner saturation, exact identities, shared keys, atomic batch, original callback order\n",kRe4dcActorRoles,unsigned(RE4DC_ACTOR_EARLY_COARSE),unsigned(RE4DC_NATIVE_MODEL_REGISTRY),checks);
}
"""


def main():
    with tempfile.TemporaryDirectory(prefix="actor-skin-reserve-") as tmp:
        for name, code in (("registry", registry_harness()), ("source", source_harness())):
            source = Path(tmp) / (name + ".cpp")
            source.write_text(code)
            for pl08, early, registry in ((p, e, r) for p in (0, 1) for e in ((0, 1) if name == "source" else (0,)) for r in ((0, 1) if name == "source" else (0,))):
                binary = Path(tmp) / f"{name}-{pl08}-{early}-{registry}"
                command = [os.environ.get("CXX", "g++"), "-std=c++17", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                           "-Wno-misleading-indentation", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                           "-DRE4DC_ACTOR_TRANSACTION=1", "-DRE4DC_ACTOR_SKIN_RESERVE=1", "-DRE4DC_NATIVE_ACTOR_FAST=1",
                           "-DRE4DC_NATIVE_ACTOR_SKIN_LAZY=1", "-DRE4DC_SKIN_PALETTE_LAZY=1", f"-DRE4DC_ACTOR_PL08={pl08}", f"-DRE4DC_ACTOR_EARLY_COARSE={early}", f"-DRE4DC_NATIVE_MODEL_REGISTRY={registry}",
                           "-I" + str(INCLUDE), str(source), "-o", str(binary)]
                if name == "source":
                    command.insert(1, "-Wno-unused-parameter")  # existing sourceActorPath signature
                subprocess.run(command, check=True)
                subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
