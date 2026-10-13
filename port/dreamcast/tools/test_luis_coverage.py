#!/usr/bin/env python3
"""Compile the actual Luis coverage helper and both final transaction checks.

Focused host evidence only: this verifies ownership/coverage and rejects changed
live flags, transforms and immutable spans. Source BIN/TPL and lifetime checks
remain in the original complete transaction and need separate/runtime evidence.
"""
from pathlib import Path
import subprocess
import tempfile

GAME = Path(__file__).resolve().parents[1] / 'game'
owner = (GAME / 'coarse_actor_owner_registry.inc').read_text()
transaction = (GAME / 'coarse_actor_transaction.inc').read_text()
start = owner.index('extern "C" int re4dc_registry_covered_roles(')
helper = owner[start:owner.index('\n}', start) + 2]
needle = '#if RE4DC_ROUTE_CH22 && RE4DC_NATIVE_MODEL_REGISTRY_PACK\n    unsigned covered=0;'
a = transaction.index(needle)
b = transaction.index('\n#endif', a) + len('\n#endif')
coverage = transaction[a:b]
a = transaction.index(needle, b)
b = transaction.index('\n#endif', a) + len('\n#endif')
diagnostic = transaction[a:b]
preflight = (GAME / 'platform/include/coarse_actor_preflight.h').read_text()
a = preflight.index('struct ChunkInput {')
chunk = preflight[a:preflight.index('\n};', a) + 3]
source = r'''#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstddef>
struct ByteSpan {const unsigned char* data; std::size_t size;};
''' + chunk + r'''
struct cModelInfo {unsigned be_flag=1;float mat[3][4]{};};
struct cModel {unsigned id=4,nParts=90;};
struct Re4dcActorPlan {
 unsigned count=6,appearance=512,material_count=2;
 cModelInfo* info[8]{};ChunkInput input[8]{};unsigned immutable_asset_id[8]{};
};
struct Desc {unsigned model_id=4,bones=90,sections=6,first_chunk=0;};
struct Chunk {unsigned draw_owner=0,geometry=0,texture=0;};
struct Registry {Chunk chunks[8];}registry;
Desc desc;bool present=true;
const Desc* registry_descriptor(unsigned appearance) {return appearance==512 && present?&desc:nullptr;}
''' + helper + r'''
bool final_check(cModel* m,const Re4dcActorPlan& p,unsigned seen,unsigned materials,const unsigned* triangles) {
 (void)m;
''' + coverage + r'''
 return true;
}
unsigned diagnostic_check(cModel* m,const Re4dcActorPlan& p,unsigned seen,unsigned materials,const unsigned* triangles,unsigned* detail) {
 (void)m;(void)detail;
''' + diagnostic + r'''
 return 0;
}
unsigned checks=0;unsigned char bytes[8]{};cModelInfo infos[6];
void want(bool pass,const char* label) {++checks;if(!pass){std::fprintf(stderr,"FAIL %s\n",label);std::exit(1);}}
Re4dcActorPlan init() {
 registry={};desc={};present=true;Re4dcActorPlan p;
 for(unsigned i=0;i<6;++i) {
  registry.chunks[i]={i,i,0};infos[i]={};p.info[i]=&infos[i];p.immutable_asset_id[i]=100+i;
  auto& c=p.input[i];c.positions={bytes,8};c.normals={bytes,8};c.uv={bytes,4};c.stream={bytes,8};c.weights={bytes,8};
  c.position_count=1;c.normal_count=1;c.palette_count=1;c.triangles=10;c.bones=90;
 }
 registry.chunks[2]={1,1,0};p.immutable_asset_id[2]=101;
 return p;
}
void reject(const Re4dcActorPlan& p,const char* label) {cModel m;unsigned covered=~0u;want(!re4dc_registry_covered_roles(&m,&p,&covered),label);}
int main() {
 cModel m;auto p=init();unsigned mask=0;
 want(re4dc_registry_covered_roles(&m,&p,&mask) && mask==4,"exact six-info mapping");
 want(!re4dc_registry_covered_roles(&m,&p,nullptr),"missing output");
 want(!re4dc_registry_covered_roles(&m,nullptr,&mask),"missing plan");
 want(!re4dc_registry_covered_roles(nullptr,&p,&mask),"missing model");
 p.appearance=0x100;mask=~0u;want(re4dc_registry_covered_roles(nullptr,&p,&mask) && !mask,"nonregistry retains ordinary coverage");
 p=init();registry.chunks[2].draw_owner=2;mask=~0u;want(re4dc_registry_covered_roles(&m,&p,&mask) && !mask,"ordinary registry retains every draw");
 for(unsigned Desc::* f:{&Desc::model_id,&Desc::bones,&Desc::sections}) {p=init();desc.*f+=1;reject(p,"descriptor identity");}
 for(unsigned cModel::* f:{&cModel::id,&cModel::nParts}) {p=init();cModel wrong;wrong.*f+=1;want(!re4dc_registry_covered_roles(&wrong,&p,&mask),"model identity");}
 p=init();p.count=5;reject(p,"missing source role");
 for(unsigned role=0;role<6;++role) {if(role==2)continue;p=init();registry.chunks[role].draw_owner=2;reject(p,"other role alias or cycle");}
 for(unsigned target:{0u,3u,4u,5u,7u}) {p=init();registry.chunks[2].draw_owner=target;reject(p,"wrong covered owner");}
 p=init();registry.chunks[2].geometry=2;reject(p,"geometry mismatch");
 p=init();registry.chunks[2].texture=1;reject(p,"texture mismatch");
 p=init();p.immutable_asset_id[2]=102;reject(p,"immutable asset mismatch");
 ByteSpan ChunkInput::* spans[]={&ChunkInput::positions,&ChunkInput::normals,&ChunkInput::uv,&ChunkInput::stream,&ChunkInput::weights};
 for(auto f:spans) {p=init();(p.input[2].*f).data=bytes+1;reject(p,"immutable span pointer");p=init();(p.input[2].*f).size+=1;reject(p,"immutable span size");}
 unsigned ChunkInput::* counts[]={&ChunkInput::position_count,&ChunkInput::normal_count,&ChunkInput::palette_count,&ChunkInput::triangles,&ChunkInput::bones};
 for(auto f:counts) {p=init();p.input[2].*f+=1;reject(p,"immutable count mismatch");}
 p=init();p.info[2]=nullptr;reject(p,"missing face source info");
 p=init();p.info[1]=nullptr;reject(p,"missing head source info");
 p=init();p.info[2]=p.info[1];reject(p,"aliased source info pointer");
 for(unsigned bit=0;bit<16;++bit) {p=init();infos[2].be_flag^=1u<<bit;reject(p,"unequal live face flags");}
 for(unsigned i=0;i<3;++i)for(unsigned j=0;j<4;++j) {p=init();infos[2].mat[i][j]=1;reject(p,"unequal live face transform");}
 p=init();infos[1].be_flag=infos[2].be_flag=9;want(re4dc_registry_covered_roles(&m,&p,&mask) && mask==4,"matching source visibility");
 p=init();unsigned tris[6]={10,10,0,10,10,10};unsigned detail=0;
#if RE4DC_ROUTE_CH22 && RE4DC_NATIVE_MODEL_REGISTRY_PACK
 want(final_check(&m,p,0x3b,3,tris),"source-complete single head draw");
 want(diagnostic_check(&m,p,0x3b,3,tris,&detail)==0,"diagnostic agrees");
 for(unsigned role:{0u,1u,3u,4u,5u}) {want(!final_check(&m,p,0x3b&~(1u<<role),3,tris),"missing source draw");want(diagnostic_check(&m,p,0x3b&~(1u<<role),3,tris,&detail)==26,"diagnostic missing source draw");}
 want(!final_check(&m,p,0x3f,3,tris),"double-covered face draw");
 want(diagnostic_check(&m,p,0x3f,3,tris,&detail)==26,"diagnostic double coverage");
 for(unsigned role=0;role<6;++role) {tris[role]+=1;want(!final_check(&m,p,0x3b,3,tris),"triangle mismatch");want(diagnostic_check(&m,p,0x3b,3,tris,&detail)==27 && detail==role,"diagnostic triangle role");tris[role]-=1;}
 want(!final_check(&m,p,0x3b,1,tris),"unused material");
 infos[2].mat[0][0]=1;want(!final_check(&m,p,0x3b,3,tris),"helper failure reaches transaction");
#else
 want(!final_check(&m,p,0x3b,3,tris),"guard off rejects missing face draw");
 want(diagnostic_check(&m,p,0x3b,3,tris,&detail)==26,"guard off diagnostic");
 tris[2]=10;want(final_check(&m,p,0x3f,3,tris),"guard off accepts ordinary complete coverage");
 want(diagnostic_check(&m,p,0x3f,3,tris,&detail)==0,"guard off diagnostic complete coverage");
#endif
 std::printf("%u extracted ownership and coverage checks passed\n",checks);
}
'''
source='#include <initializer_list>\n'+source
with tempfile.TemporaryDirectory() as tmp:
    cpp=Path(tmp)/'luis.cpp';cpp.write_text(source)
    for ch22,pack in ((0,0),(0,1),(1,0),(1,1)):
        exe=Path(tmp)/f'luis-{ch22}{pack}'
        subprocess.run(['g++','-std=c++17','-O2','-Wall','-Wextra','-Werror',f'-DRE4DC_ROUTE_CH22={ch22}',f'-DRE4DC_NATIVE_MODEL_REGISTRY_PACK={pack}',str(cpp),'-o',str(exe)],check=True)
        print(f'CH22={ch22} PACK={pack}:',subprocess.check_output([str(exe)],text=True).strip())