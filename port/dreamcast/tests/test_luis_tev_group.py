#!/usr/bin/env python3
"""Exercise the actual material modifier gate for Luis's authored TEV group."""
from pathlib import Path
import os, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[3]

def function(text, marker):
 start=text.index(marker);i=text.index('{',start);depth=1;j=i+1
 while depth:
  depth+=(text[j]=='{')-(text[j]=='}');j+=1
 return text[start:j]

def harness():
 source=(ROOT/'port/dreamcast/game/coarse_actor_material.inc').read_text()
 init=function((ROOT/'src/pl14/pl14.cpp').read_text(),'void cSubLuis::init()')
 assert 'TevScaleGroup = 1;' in init
 alias=(ROOT/'include/player.h').read_text()
 assert 'pSubEm asm("pSUB")' in alias
 begin=source.index('    if(m->pTexChg',source.index('const bool registry='))
 end=source.index('\n#else',source.index('return out;}',begin))
 gate=source[begin:end]
 return r'''
#include <cassert>
#include <cstdio>
#include <cstring>
#define RE4DC_ACTOR_LEON_NATIVE_LOOK 1
struct cModel {
 unsigned id=4,type=0;void* pTexChg=nullptr;unsigned Shader_type=0,CullMode=0;
 float invisible_factor=1,invisible_factor2=1;unsigned alpha_omit=255,TevScaleGroup=1;
 unsigned AddAmb_r=0,AddAmb_g=0,AddAmb_b=0;
};
struct Plan {unsigned appearance=512;};
enum class Error {None,LiveModifier};
struct Result {Error error=Error::None;};
cModel luis,other; cModel* pSubEm=&luis;
unsigned gxCsScale[3]={2,2,3};
bool source_appearance_type(unsigned a,unsigned,unsigned){return a<5;}
''' + function(source,'inline bool room_colour_scale(') + '\n' + function(source,'inline unsigned source_model_tev_group(') + r'''
Result modifiers(cModel* m,const Plan* p,bool leon,bool registry) {
 Result out{};
''' + gate + r'''
 return out;
}
unsigned checks=0;
void check(bool value){assert(value);++checks;}
bool okay(cModel* m=&luis,bool leon=false,bool registry=true) {Plan p;return modifiers(m,&p,leon,registry).error==Error::None;}
int main() {
 check(okay()==bool(RE4DC_ROUTE_CH22));
 luis.TevScaleGroup=0;check(okay()==!bool(RE4DC_ROUTE_CH22));luis=cModel{};
 check(!okay(&other)); // identical id/state is not the source partner
 other.TevScaleGroup=0;check(okay(&other));
 other.id=0x18;check(okay(&other)); // existing merchant rule
 other.TevScaleGroup=1;check(!okay(&other));
 luis.id=2;check(!okay());luis.id=3;check(!okay());luis.id=4;
 check(!okay(&luis,false,false)); // missing registry/source appearance
 pSubEm=nullptr;check(!okay());pSubEm=&luis;
 check(source_model_tev_group(nullptr,false,true)==0);
 for(unsigned scale=0;scale<4;++scale){
  gxCsScale[1]=scale;check(okay()==bool(RE4DC_ROUTE_CH22 && scale<=2));
 }gxCsScale[1]=2;
 // Source modifiers remain refusals; the group selector grants no capability.
 for(unsigned changed=0;changed<10;++changed) {
  luis=cModel{};
  switch(changed) {
   case 0:luis.pTexChg=&other;break;case 1:luis.Shader_type=1;break;
   case 2:luis.CullMode=1;break;case 3:luis.invisible_factor=0.5f;break;
   case 4:luis.invisible_factor2=0.5f;break;case 5:luis.alpha_omit=254;break;
   case 6:luis.TevScaleGroup=2;break;case 7:luis.AddAmb_r=1;break;
   case 8:luis.AddAmb_g=1;break;case 9:luis.AddAmb_b=1;break;
  }
  check(!okay());
 }
 luis=cModel{};luis.id=0;check(okay(&luis,true,true)); // existing Leon group
 check(source_model_tev_group(&luis,true,false)==1);
 std::printf("PASS CH22=%u material modifier cases=%u; exact authored Luis group and negative gates\n",unsigned(RE4DC_ROUTE_CH22),checks);
}
'''

def main():
 with tempfile.TemporaryDirectory(prefix='luis-tev-') as tmp:
  src=Path(tmp)/'check.cpp';src.write_text(harness())
  for enabled in (0,1):
   exe=Path(tmp)/('check'+str(enabled))
   subprocess.run([os.environ.get('CXX','g++'),'-std=c++17','-O1','-g','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer','-DRE4DC_ROUTE_CH22='+str(enabled),str(src),'-o',str(exe)],check=True)
   subprocess.run([str(exe)],check=True)
if __name__=='__main__':main()
