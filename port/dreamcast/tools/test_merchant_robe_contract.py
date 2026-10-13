#!/usr/bin/env python3
"""Host-check the exact extracted merchant role/flag policy, guards off/on.

This tests policy nomination and live flag/color restrictions. It does not model
archive ownership, runtime lighting, or actor submission; those still use the
existing complete source certificate and need an actual runtime capture.
"""
from pathlib import Path
import subprocess
import tempfile

GAME = Path(__file__).resolve().parents[1] / "game"
owner = (GAME / "coarse_actor_owner_registry.inc").read_text()
material = (GAME / "coarse_actor_material.inc").read_text()
a = owner.index('extern "C" int re4dc_registry_merchant_robe(')
b = owner.index("\n}", a) + 2
helper = owner[a:b]
a = material.index("    unsigned expected=1;")
b = material.index("    if(i->be_flag&2)", a)
policy = material[a:b]
source = r'''#include <cstdio>
#include <cstdlib>
#define RE4DC_NATIVE_MODEL_REGISTRY 1
#define RE4DC_LEON_LIKE(x) false
struct Descriptor {unsigned model_id,bones,sections;};
Descriptor descriptor{0x18,61,7}; bool available=true;
const Descriptor* registry_descriptor(unsigned a) {return a==512 && available ? &descriptor : nullptr;}
''' + helper + r'''
enum class Error {None,PassGroup,LiveModifier};
struct Role {unsigned appearance,role,source_bin,source_tpl;};
struct Info {
 unsigned be_flag,colorWord,blend_mode,flagsDC,nAddTex,blendType;
 unsigned char color2[4];float invisible_factor,blendRatio,uvU,uvV,uvScrollU,uvScrollV;
 const void *pAddTpl,*texBlendTbl,*pTexAnim;
};
Error check(const Info* i,const Role& row) {
''' + policy + r'''
 return Error::None;
}
unsigned checks=0;
void want(bool x,const char* label) {++checks;if(!x){std::fprintf(stderr,"FAIL %s\n",label);std::exit(1);}}
int main() {
 Role role{512,1,14,15};Info good{};good.be_flag=1;good.colorWord=~0u;good.invisible_factor=1;
#if RE4DC_ROUTE_CH22 || RE4DC_ROUTE_CH23
 good.be_flag=0x21;
#endif
 want(check(&good,role)==Error::None,"exact source role");
 auto hidden=good;hidden.be_flag|=8;want(check(&hidden,role)==Error::None,"source visibility retained");
 for(unsigned bit:{2u,4u,16u,64u,128u,256u}) {auto v=good;v.be_flag|=bit;want(check(&v,role)==Error::PassGroup,"unproved flag");}
 auto color=good;color.colorWord=0xffeeeeee;want(check(&color,role)==Error::LiveModifier,"changed material color");
 for(unsigned k=0;k<4;++k){color=good;color.color2[k]=1;want(check(&color,role)==Error::LiveModifier,"secondary color");}
 color=good;color.invisible_factor=.5;want(check(&color,role)==Error::LiveModifier,"fade");
 color=good;color.blend_mode=1;want(check(&color,role)==Error::LiveModifier,"blend");
 color=good;color.uvU=1;want(check(&color,role)==Error::LiveModifier,"UV mutation");
 auto own=good;own.be_flag=0x21;
#if RE4DC_ROUTE_CH22 || RE4DC_ROUTE_CH23
 auto missing=good;missing.be_flag=1;want(check(&missing,role)==Error::PassGroup,"missing authored flag");
#else
 want(check(&own,role)==Error::PassGroup,"guard off retains original rejection");
#endif
 unsigned Role::* fields[]={&Role::appearance,&Role::role,&Role::source_bin,&Role::source_tpl};
 for(auto field:fields) {Role v=role;v.*field+=1;want(check(&own,v)==Error::PassGroup,"wrong certified role identity");}
 unsigned Descriptor::* ds[]={&Descriptor::model_id,&Descriptor::bones,&Descriptor::sections};
 for(auto field:ds){auto saved=descriptor;descriptor.*field+=1;want(check(&own,role)==Error::PassGroup,"wrong descriptor identity");descriptor=saved;}
 available=false;want(check(&own,role)==Error::PassGroup,"absent descriptor");
 std::printf("%u exact extracted role/flag policy checks passed\n",checks);
}
'''
# The initializer-list syntax needs the standard header, independent of transitive includes.
source = "#include <initializer_list>\n" + source
with tempfile.TemporaryDirectory() as tmp:
    cpp = Path(tmp) / "robe.cpp"; cpp.write_text(source)
    for ch22,ch23 in ((0,0),(1,0),(0,1),(1,1)):
        exe = Path(tmp) / ("robe-%d%d" % (ch22,ch23))
        subprocess.run(["g++","-std=c++17","-O2","-Wall","-Wextra","-Werror",
            "-DRE4DC_ROUTE_CH22=%d" % ch22,"-DRE4DC_ROUTE_CH23=%d" % ch23,str(cpp),"-o",str(exe)],check=True)
        print("CH22=%d CH23=%d:" % (ch22,ch23),subprocess.check_output([str(exe)],text=True).strip())
