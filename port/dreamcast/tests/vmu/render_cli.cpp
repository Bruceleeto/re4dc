#include "vmu_context.h"
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
using namespace re4vmu;
int main(int argc,char** argv){
    if(argc==18){
        int a[17];for(int i=0;i<17;++i)a[i]=atoi(argv[i+1]);
        View v={Mode(a[0]),Person(a[1]),Person(a[2]),Condition(a[3]),Status(a[4]),a[5],a[6],Ammo(a[7]),unsigned(a[8]),unsigned(a[9]),bool(a[10])};
        Phase p={unsigned(a[11]),unsigned(a[12]),unsigned(a[13]),bool(a[14])};
        struct { unsigned pre; unsigned char frame[192]; unsigned post; } buffer={0x12345678,{},0x87654321};
        render(v,p,buffer.frame);assert(buffer.pre==0x12345678&&buffer.post==0x87654321);
        for(unsigned char b:buffer.frame)printf("%02x",b);
        puts("");return 0;
    }
    Snapshot s={true,false,false,Leon,Ashley,Fine,900,2400,Finite,100,2,1,1};
    assert(resolve(s).subject==Ashley&&resolve(s).owner==Leon);
    s.call=true;assert(resolve(s).mode==Call);
    s.companion_help=true;assert(resolve(s).status==Help);
    s.condition=Danger;assert(resolve(s).subject==Leon&&resolve(s).mode==Vitals);
    s.hp=0;assert(resolve(s).condition==Dead);
    s.hp=600;s.condition=Fine;s.player=Ashley;s.companion=Nobody;s.call=false;s.companion_help=false;
    assert(resolve(s).owner==Ashley&&resolve(s).status==Play);
    s.player=Leon;s.companion=Luis;assert(resolve(s).subject==Luis&&resolve(s).status==Ally);
    s.valid=false;assert(resolve(s).mode==Blank);
    s.valid=true;s.companion=Nobody;
    Animation anim={};View v=resolve(s);auto p=anim.update(v,1,1000,false);assert(p.reveal==1000);
    v.infection=3;p=anim.update(v,1,1100,false);assert(p.reveal==0&&p.from_stage==2);
    p=anim.update(v,1,1500,false);assert(p.reveal==500);
    v.mode=Call;p=anim.update(v,1,1600,false);assert(p.reveal==1000);
    v.mode=Vitals;p=anim.update(v,1,1700,false);assert(p.from_stage==3&&p.reveal==1000);
    v.infection=0;p=anim.update(v,1,1800,false);assert(p.reveal==0);
    p=anim.update(v,2,1900,false);assert(p.reveal==1000&&p.from_stage==0);
    v.infection=2;p=anim.update(v,2,2000,true);assert(p.reveal==1000&&!p.alternate);
    v.infection=3;p=anim.update(v,2,2100,false);assert(p.reveal==0);
    --v.hp;p=anim.update(v,2,2200,false);assert(p.reveal==1000&&p.from_stage==3);
    assert(ammo_visible(0,0,1));assert(!ammo_visible(1,0,1));assert(!ammo_visible(0,0xf0000,1));assert(!ammo_visible(0,0,0));
    puts("selector, interruption, generation, reduced motion and ammo boundaries passed");
}
