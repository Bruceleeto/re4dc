#include "vmu_context.h"
#include "vmu_lcd_queue.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
using namespace re4vmu;
int main(){
    LcdQueue q={};unsigned char a[192]={},b[192]={};b[12]=0x80;
    assert(!q.ready(0,0,a));
    assert(q.ready(0,1,a));q.result(0,0,a);
    assert(!q.ready(10000,1,a)); // static output does not transmit repeatedly
    assert(q.ready(10001,1,b));q.result(10001,-1,b);
    assert(!q.ready(10050,1,b));assert(q.ready(10101,1,b));q.result(10101,-1,b);
    assert(q.ready(10201,1,b));q.result(10201,-1,b);
    assert(!q.ready(11100,1,b));assert(q.ready(11201,1,b));
    // Busy did not commit an obsolete frame; a reverted desired frame needs no write.
    assert(!q.ready(11201,1,a));
    q.disconnected();assert(q.ready(11301,1,a));q.result(11301,0,a);
    assert(q.ready(11401,2,a)); // same bytes, different/reconnected device
    q.result(11401,0,a);assert(q.ready(11501,2,b));q.result(11501,0,b);
    q.last_attempt=0xffffffc0u;q.attempted=true;
    assert(q.ready(0x40u,2,a)); // timer wrap
    assert(infection_stage(false,0,0)==0);
    assert(infection_stage(true,0,0)==1);
    assert(infection_stage(true,0x01000000,0)==2);
    assert(infection_stage(true,0x01040000,0)==3);
    assert(infection_stage(true,0x01040000,0,true)==2); // actual suppressant event
    assert(infection_stage(true,0x01040000,0x800,true)==0); // removal wins
    assert(infection_stage(true,0x01040000,0,false)==3); // pre-suppression save
    assert(infection_stage(true,0x01040000,0x800)==0);
    assert(infection_stage(false,0,0)==0); // older loaded save overrides later state
    puts("PASS: LCD latest-frame retry/backoff/reconnect/wrap and saved-story mappings");
}
