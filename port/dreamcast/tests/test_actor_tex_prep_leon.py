#!/usr/bin/env python3
"""Actual standard Leon preparation readers; synthetic source/cache fixtures."""
import test_actor_tex_prep as a

STATE=r'''
#if RE4DC_CHARBAKE_TOGGLE
namespace re4dc_charbake {
struct Variant {unsigned leon_crc,leon_fnv;};
constexpr unsigned kCount=3;
constexpr Variant variants[]={{0xec255e66,0x76812316},{91,92},{81,82}};
}
unsigned texture_tokens[3],charbake_variant=0;
Re4dcUiImage image{&texture_tokens[0],nullptr,512,512,6,~0u,0};
unsigned crc=0xec255e66,fnv=0x76812316;
void set_variant(unsigned v){charbake_variant=v;image={&texture_tokens[v],nullptr,512,512,6,~0u,0};crc=re4dc_charbake::variants[v].leon_crc;fnv=re4dc_charbake::variants[v].leon_fnv;}
#else
unsigned texture_token;
const Re4dcUiImage image{&texture_token,nullptr,512,512,6,~0u,0};
constexpr unsigned crc=0xec255e66,fnv=0x76812316;
#endif
#include "actor_tex_prep_leon_pick.inc"
'''

def material():
    s=a.material_harness(player=True)
    fixture=(a.ROOT/'port/dreamcast/tests/fixtures/actor_tex_prep_player.inc').read_text()
    assert s.endswith(fixture)
    s=s[:-len(fixture)]+(a.ROOT/'port/dreamcast/tests/fixtures/actor_tex_prep_leon.inc').read_text()
    return s.replace('#include "actor_tex_prep_material.inc"',STATE+'\n#include "actor_tex_prep_material.inc"')

def ledger():
    s=a.ledger_harness()
    extra=STATE+r'''
bool leon_enabled=false;
extern "C" unsigned re4dc_leon_tex_metadata(cModel*,const FrameIdentity*,const ModelIdentity*,Re4dcActorTexMetadata* p){
 if(!leon_enabled)return unsigned(Re4dcActorTexReason::Model);
 *p={0x100,8,2,6,0x7f,charbake_variant+1};return 0;
}
'''
    s=s.replace('#include "source_actor_tex_prep.inc"',extra+'\n#include "source_actor_tex_prep.inc"')
    s=s.replace('if(mutation==7)pl08_pack.published=false;','if(mutation==7)pl08_pack.published=false;if(mutation==8)charbake_variant=1;')
    # A forward declaration permits mutation from the actual enumeration's
    # synthetic material boundary without replacing the real variant reader.
    s=s.replace('unsigned life_serial=','extern unsigned charbake_variant;\nunsigned life_serial=')
    s=s.replace('int main(){','int legacy_main(){').replace('std::printf("actor texture ledger:', 'return 0;std::printf("actor texture ledger:')
    s+=r'''
int main(){
 legacy_main();leon_enabled=true;set_variant(0);reset();auto b=run(true);
 check(b.count==3&&b.qualified==3&&b.picks[0].kind==Re4dcActorTexKind::PlayerLeon);
 check(b.picks[0].crc==crc&&b.picks[0].package_generation==1&&!b.picks[0].appearances);
 reset();EmMgr.pAlive=models+1;models[1].pNext=models+2;models[2].pNext=models;models[0].pNext=nullptr;
 b=run(true);check(b.picks[0].kind==Re4dcActorTexKind::PlayerLeon);
 reset(4);single_third=true;models[1].type=1;models[2].type=2;models[3].type=3;
 b=run(true);check(b.count==6&&b.picks[0].kind==Re4dcActorTexKind::PlayerLeon);
 reset();player_reason=0;b=run(true);check(b.picks[0].kind==Re4dcActorTexKind::PlayerPl08);
 reset();mutation=8;run(false);
 for(unsigned v=0;v<3;++v){reset();set_variant(v);b=run(true);check(b.picks[0].crc==crc&&b.picks[0].package_generation==v+1);}
 std::printf("Leon plus existing ledger: %u checks, player-first ordering/current variant/unchanged source ownership PASS\n",checks);
}
'''
    return s

def loader():
    s=a.loader_harness().replace('Entry* load(',STATE+'\nbool mutate_leon=false;\nEntry* load(')
    s=s.replace('++loads;', '++loads;if(mutate_leon){charbake_variant=1;mutate_leon=false;}')
    s=s.replace('int main(){','int legacy_main(){').replace('std::printf("actor texture loader:', 'return 0;std::printf("actor texture loader:')
    s+=r'''
void leon_plan(){reset();set_variant(0);planned.picks[0].kind=Re4dcActorTexKind::PlayerLeon;planned.picks[0].package_generation=1;}
int main(){
 legacy_main();leon_plan();pure_leases();check(loads==2&&!failures&&load_order[0]==100&&actor_tex_prepared_count==2);
 leon_plan();charbake_variant=1;pure_leases();check(loads==1&&entries[0].frame==frame-1);
 leon_plan();mutate_leon=true;pure_leases();check(loads==2&&failures==1&&actor_tex_prepared_count==1);
 leon_plan();planned.picks[0].package_generation=0;pure_leases();check(loads==1);
 leon_plan();planned.picks[0].kind=static_cast<Re4dcActorTexKind>(99);pure_leases();check(!loads);
 std::printf("Leon plus existing loader: %u checks, pre/post-load identity and no texture-lease authority PASS\n",checks);
}
'''
    return s

def pick():
    return '#include <cassert>\n#include "actor_tex_prep.h"\n'+STATE+r'''
int main(){
 Re4dcActorTexPick p{};assert(re4dc_leon_tex_pick(0x100,&p));
 assert(p.kind==Re4dcActorTexKind::PlayerLeon&&p.package_generation==1&&p.image.pixels==image.pixels&&p.crc==crc&&p.fnv==fnv);
 assert(!re4dc_leon_tex_current(0)&&!re4dc_leon_tex_current(2));
 assert(!re4dc_leon_tex_pick(0x108,&p)&&!p.image.pixels&&!p.crc);
 assert(!re4dc_leon_tex_pick(0x100,nullptr));
}
'''

if __name__=='__main__':
    common=('-DRE4DC_ACTOR_TEX_PREP_LEON=1','-fsanitize=address,undefined','-fno-omit-frame-pointer')
    for mode in (0,1,2):
        # The actual source reader requires addresses in Dreamcast's 32-bit
        # 0x8c RAM range. ASan reserves that range in a 64-bit host process.
        a.run_harness(f'leon_material_{mode}',material(),('-DRE4DC_ACTOR_TEX_PREP_LEON=1','-m32','-fsanitize=undefined','-fno-omit-frame-pointer','-DRE4DC_CHARBAKE_TOGGLE=1',f'-DRE4DC_ACTOR_MATERIAL_RECORD={mode}'))
    a.run_harness('leon_ledger',ledger(),common+('-DRE4DC_CHARBAKE_TOGGLE=1',))
    a.run_harness('leon_loader',loader(),common+('-DRE4DC_CHARBAKE_TOGGLE=1',))
    for mode in (0,1):
        a.run_harness(f'leon_pick_{mode}',pick(),common+(f'-DRE4DC_CHARBAKE_TOGGLE={mode}',))
