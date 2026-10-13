#ifndef RE4DC_VMU_LCD_QUEUE_H
#define RE4DC_VMU_LCD_QUEUE_H
#include <stdint.h>
#include <string.h>
namespace re4vmu {
// A bounded single-frame mailbox, never a queue of obsolete LCD packets.
struct LcdQueue {
    alignas(4) uint8_t sent[192];
    unsigned last_attempt, last_scan, errors;
    uintptr_t device;
    bool sent_valid, attempted;
    bool ready(unsigned now,uintptr_t current,const uint8_t* wanted) {
        if(current!=device){device=current;sent_valid=false;errors=0;}
        if(!current)return false;
        unsigned delay=errors>=3?1000:100;
        if(attempted&&now-last_attempt<delay)return false;
        return !sent_valid||memcmp(sent,wanted,192)!=0;
    }
    void result(unsigned now,int rc,const uint8_t* wanted){
        attempted=true;last_attempt=now;
        if(rc==0){memcpy(sent,wanted,192);sent_valid=true;errors=0;}
        else {if(errors<3)++errors;}
    }
    void disconnected(){device=0;sent_valid=false;errors=0;}
};
}
#endif
