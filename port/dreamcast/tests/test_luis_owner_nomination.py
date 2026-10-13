#!/usr/bin/env python3
"""Exercise actual partner nomination, registry descriptor gate, and frame ledger.

Host proof only: no render submission or target-runtime acceptance is inferred.
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


def harness():
    registry = (ROOT / "port/dreamcast/game/coarse_actor_owner_registry.inc").read_text()
    trans = (ROOT / "src/game/trans.cpp").read_text()
    return r'''#include <cassert>
#include <cstdio>
#include <cstring>
#define RE4DC_ACTOR_TRANSACTION 1
#include "coarse_source_frame.h"
using namespace re4dc_source;
struct cModel { unsigned id, nParts, serial; };
cModel leon{0,119,1}, luis{4,90,2}, ashley{2,90,3}, ganado{0x13,34,4};
cModel* pPL=&leon; cModel* pSUB=&luis;
struct Descriptor {unsigned model_id,bones;};
struct Registry {Descriptor descriptors[2];unsigned descriptor_count;} registry{{{4,90},{11,7}},2};
unsigned registry_id_mask[8];bool registry_mask_ready;
''' + function(registry, "inline bool registry_id(") + "\n" + function(
        registry, 'extern "C" int re4dc_registry_candidate(') + r'''
FrameLedger sourceActorLedger;
FrameIdentity current{186,0x11c,1,1,1,1};
bool sourceActorActive=true,sourceActorRenderActive=true,valid_ram=true;
bool sourceActorRam(const void* p){return valid_ram && p;}
bool sourceActorIdentity(FrameIdentity& now){now=current;return true;}
''' + function(trans, "ModelIdentity sourceActorModel(") + r'''
#include "source_actor_owner_hooks.inc"
alignas(FrameEntry) unsigned char storage[sizeof(FrameEntry)];
unsigned checks;
void check(bool pass){assert(pass);++checks;}
void descriptor(unsigned id=4,unsigned bones=90,bool present=true){
 registry.descriptors[0]={id,bones};registry.descriptor_count=present?1:0;
 std::memset(registry_id_mask,0,sizeof registry_id_mask);registry_mask_ready=false;
}
void prepare(cModel* model,bool finish=true,ModelPath path=ModelPath::Source){
 sourceActorActive=sourceActorRenderActive=valid_ram=true;
 check(sourceActorLedger.begin(storage,sizeof storage,1,current));
 check(sourceActorLedger.append(current,sourceActorModel(model),path,0));
 check(sourceActorLedger.seal(current));
 if(path==ModelPath::Source && finish){PreparationTicket ticket{};
  check(sourceActorLedger.claim(current,ticket));
  check(sourceActorLedger.complete(current,ticket,sourceActorModel(model)));
 }
}
int identity(cModel* m){FrameIdentity frame{};ModelIdentity model{};
 return re4dc_actor_transaction_identity(m,&frame,&model);
}
int main(){
 constexpr bool admits=RE4DC_ROUTE_CH22 && RE4DC_NATIVE_MODEL_REGISTRY;
 check(!re4dc_actor_transaction_candidate(nullptr));
 prepare(&leon);check(re4dc_actor_transaction_candidate(&leon)==1);
 prepare(&ganado);check(re4dc_actor_transaction_candidate(&ganado)==1);
 prepare(&luis);check(identity(&luis)==1);
 check(re4dc_actor_transaction_candidate(&luis)==int(admits));
 unsigned choice=99;check(re4dc_actor_transaction_choice(&luis,&choice) && choice==0);
 check(re4dc_actor_transaction_choose(&luis,1));check(re4dc_actor_transaction_choice(&luis,&choice) && choice==1);
 check(!re4dc_actor_transaction_choose(&luis,1)); // original-source choice stays sticky
 pSUB=&ashley;descriptor(2,90);prepare(&ashley);check(!re4dc_actor_transaction_candidate(&ashley));
 ashley.id=3;descriptor(3,90);prepare(&ashley);check(!re4dc_actor_transaction_candidate(&ashley));ashley.id=2;
 pSUB=&luis;descriptor(4,90,false);prepare(&luis);check(!re4dc_actor_transaction_candidate(&luis));
 descriptor();luis.nParts=89;prepare(&luis);check(!re4dc_actor_transaction_candidate(&luis));luis.nParts=90;
 descriptor(4,91);prepare(&luis);check(!re4dc_actor_transaction_candidate(&luis));descriptor();
 prepare(&luis,false);check(identity(&luis)==-1);check(re4dc_actor_transaction_candidate(&luis)==int(admits));
 // Candidate intentionally keeps invalid participants out of FRONT_NATIVE;
 // the unchanged identity/transaction gate refuses any ownership afterward.
 for(unsigned field=0;field<6;++field){
  prepare(&luis);FrameIdentity saved=current;
  switch(field){case 0:++current.frame;break;case 1:++current.room;break;case 2:++current.room_generation;break;
   case 3:++current.primitive_epoch;break;case 4:++current.enemy_generation;break;case 5:++current.object_generation;break;}
  check(identity(&luis)==-1);check(re4dc_actor_transaction_candidate(&luis)==int(admits));
  check(!re4dc_actor_transaction_choice(&luis,&choice));check(!re4dc_actor_transaction_choose(&luis,2));current=saved;
 }
 prepare(&luis);++luis.serial;check(identity(&luis)==-1);check(!re4dc_actor_transaction_choose(&luis,2));--luis.serial;
 prepare(&luis);sourceActorLedger.retire();check(identity(&luis)==-1);check(!re4dc_actor_transaction_choose(&luis,2));
 prepare(&luis,true,ModelPath::Coarse);check(identity(&luis)==-1);check(!re4dc_actor_transaction_choose(&luis,2));
 prepare(&luis);sourceActorActive=false;check(identity(&luis)==0);check(!re4dc_actor_transaction_candidate(&luis));
 prepare(&luis);sourceActorRenderActive=false;check(identity(&luis)==0);check(!re4dc_actor_transaction_candidate(&luis));
 prepare(&luis);valid_ram=false;check(identity(&luis)==-1);check(!re4dc_actor_transaction_choose(&luis,2));
 std::printf("PASS CH22=%u registry=%u checks=%u: exact Luis nomination and stale/source fallback gates\n",
  unsigned(RE4DC_ROUTE_CH22),unsigned(RE4DC_NATIVE_MODEL_REGISTRY),checks);
}
'''


def main():
    with tempfile.TemporaryDirectory(prefix="luis-owner-nomination-") as tmp:
        source = Path(tmp) / "check.cpp"
        source.write_text(harness())
        for ch22, registry in ((0, 1), (1, 1), (1, 0)):
            binary = Path(tmp) / f"check-{ch22}-{registry}"
            command = [os.environ.get("CXX", "g++"), "-std=c++17", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                       "-Wno-misleading-indentation", "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
                       f"-DRE4DC_ROUTE_CH22={ch22}", f"-DRE4DC_NATIVE_MODEL_REGISTRY={registry}",
                       "-I" + str(INCLUDE), str(source), "-o", str(binary)]
            subprocess.run(command, check=True)
            subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
