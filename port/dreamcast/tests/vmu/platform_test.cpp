// Runs the actual shared LCD owner with a fake Maple boundary; no game state writes.
#include <kos.h>
#include <dc/maple.h>
#include "vmu_context.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
using namespace re4vmu;
static unsigned clock_ms,calls;
static maple_device_t controller={2,0,{MAPLE_FUNC_CONTROLLER,0}};
static maple_device_t first={2,1,{MAPLE_FUNC_LCD,1}}, second={2,2,{MAPLE_FUNC_LCD,0}};
static bool present=true,slot_one=true,rotated;
static maple_device_t* last;
static unsigned char frame[192];
uint64_t timer_ms_gettime64(){return clock_ms;}
maple_device_t* maple_enum_type(int i,unsigned f){assert(i==0&&f==MAPLE_FUNC_CONTROLLER);return &controller;}
maple_device_t* maple_enum_dev(int p,int u){assert(p==2);return present?(u==1&&slot_one?&first:u==2?&second:nullptr):nullptr;}
int vmu_draw_lcd(maple_device_t* d,void* p){++calls;last=d;rotated=false;memcpy(frame,p,192);return 0;}
int vmu_draw_lcd_rotated(maple_device_t* d,void* p){++calls;last=d;rotated=true;memcpy(frame,p,192);return 0;}
extern "C" void re4dc_vmu_publish(const Snapshot*);
static void tick(unsigned now){clock_ms=now;re4dc_vmu_poll();}
int main(){
 Snapshot s={true,false,false,Leon,Nobody,Fine,1200,1200,Finite,12,0,0,1};
 re4dc_vmu_publish(&s);tick(1000);
 assert(calls==1&&last==&first&&!rotated); // controller C, lower LCD slot wins
 tick(1050);assert(calls==1); // composition/submission rate cap
 unsigned char speed[192],debug[192];memset(speed,0xa5,192);memset(debug,0x5a,192);
 re4dc_vmu_speed(speed,1);tick(1100);assert(!memcmp(frame,speed,192));
 re4dc_vmu_debug(debug);tick(1200);assert(!memcmp(frame,debug,192));
 tick(1300);assert(calls==3); // identical diagnostic is not resent
 tick(4100);assert(!memcmp(frame,speed,192)); // lease expired, explicit speed page resumes
 re4dc_vmu_speed(nullptr,0);tick(4200);assert(memcmp(frame,speed,192));
 slot_one=false;tick(4300);assert(last==&second&&rotated); // same port, next slot, KOS orientation rule
 present=false;unsigned before=calls;tick(4400);assert(calls==before);
 present=true;tick(4500);assert(calls==before+1); // same bytes resent on reconnect
 s.infection=3;re4dc_vmu_publish(&s);tick(4600); // growth just started
 present=false;tick(4700);present=true;tick(4800);
 unsigned char expected[192];render(resolve(s),Phase{0,3,1000,false},expected);
 assert(!memcmp(frame,expected,192)); // reconnect gets committed final stage
 puts("PASS: shared priority/lease, port/slot/orientation, rate cap and reconnect cancellation");
}
