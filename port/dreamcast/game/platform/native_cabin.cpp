#include "include/native_cabin.h"
#if RE4DC_CABIN_SOURCE
#include <kos.h>
#include <fcntl.h>
#include <cstring>
#include <cstdint>
#include "include/native_movie.h"
#include "include/native_io.h"
#include "include/re4dc_platform.h"
#include "../../room/room_storage.hpp"
namespace {
struct CabinSource {
    unsigned id=0,movie=0,audio=0;
    uintptr_t heap_begin=0,heap_end=0,room_begin=0,room_end=0;
    const void* event=nullptr;
    bool beginning=false,retiring=false,source_done=false,death=false,accepted_skip=false;
    bool failed=false,error_reported=false,halted=false,bound=false;
} cabin;
bool cabin_preflight_ready=false;
// Manager pairing survives a cabin beginning or retiring inside an active call.
unsigned cabin_event_readers=0;
bool cabin_event_reader_fault=false;
const char* cabin_key(unsigned id){
    switch(id){case 0x11c00:return "event/evd/r11cs00.evd";
        case 0x11c10:return "event/evd/r11cs10.evd";
        case 0x11c20:return "event/evd/r11cs20.evd";default:return nullptr;}
}
void cabin_failure(const char* reason){
    cabin.failed=true;
    if(cabin.movie && !cabin.beginning && !cabin.retiring)
        re4dc_movie_cabin_abort(cabin.movie);
    if(!cabin.error_reported){
        cabin.error_reported=true;
        re4dc_log("cabin failure: id=%05x movie=%u source_done=%d death=%d skip=%d reason=%s\n",
            cabin.id,cabin.movie,cabin.source_done,cabin.death,cabin.accepted_skip,reason);
    }
    if(!cabin.death){
        cabin.halted=true;
        // Intentional stop: retain source event/camera/model ownership exactly
        // where it failed. No mode2, event counter, health or death workaround.
        re4dc_missing(reason);
    }
}
bool exact_carrier(const char* path,unsigned size,unsigned expected_crc){
    Re4dcIoScope owner;
    const file_t file=fs_open(path,O_RDONLY);
    if(file<0)return false;
    bool ok=fs_total(file)==size;
    unsigned char buffer[512];unsigned crc=~0u;
    for(unsigned left=size;ok&&left;){
        unsigned n=left<sizeof(buffer)?left:sizeof(buffer);
        if(!re4dc::storage::read_exact(file,buffer,n)){ok=false;break;}
        for(unsigned i=0;i<n;++i){crc^=buffer[i];for(unsigned b=0;b<8;++b)crc=(crc>>1)^(0xedb88320u&-(crc&1u));}
        left-=n;
    }
    fs_close(file);return ok && (crc^~0u)==expected_crc;
}
bool range_overlap(uintptr_t lo,uintptr_t hi,uintptr_t begin,uintptr_t end){return lo<end && hi>begin;}
bool close_audio(){
    if(!cabin.audio)return true;
    if(!re4dc_cabin_audio_owner_close(cabin.audio)){
        cabin_failure("cabin audio owner retirement");return false;
    }
    cabin.audio=0;return true;
}
void service(){
    if(!cabin.id || cabin.beginning || cabin.retiring || cabin.halted || cabin.failed)return;
    if(cabin.audio && re4dc_cabin_audio_error(cabin.audio)){cabin_failure("cabin sound ownership");return;}
    const int status=re4dc_movie_cabin_step(cabin.movie);
    if(status!=RE4DC_MOVIE_RUNNING && status!=RE4DC_MOVIE_EOF && status!=RE4DC_MOVIE_SKIP)
        cabin_failure("cabin media transport or final presentation");
}
}
extern "C" int re4dc_cabin_preflight(unsigned costume){
#if RE4DC_CABIN_COMPLETE_HANDOFF
    if(cabin.retiring)return 0;
#endif
    if(cabin.id){cabin_failure("cabin preflight with active owner");return 0;}
    cabin_preflight_ready=false;
    // The qualified packet/movie set is the ordinary costume source. Never use
    // its bytes as the separately authored armour-costume event.
    if(costume==1 || !exact_carrier("/cd/event/evd/r11cs00.evd",27456,0x049c020du) ||
       !exact_carrier("/cd/event/evd/r11cs10.evd",7296,0x5d7c586fu) ||
       !exact_carrier("/cd/event/evd/r11cs20.evd",5568,0x2d331534u) ||
       !re4dc_movie_cabin_available(0x11c00) || !re4dc_movie_cabin_available(0x11c10) ||
       !re4dc_movie_cabin_available(0x11c20)){
        cabin_failure("cabin exact original event/movie preflight");return 0;
    }
    cabin=CabinSource{};cabin_preflight_ready=true;return 1;
}
extern "C" int re4dc_cabin_begin(unsigned id,const void* heap,unsigned heap_bytes,const void* room,unsigned room_bytes){
#if RE4DC_CABIN_COMPLETE_HANDOFF
    if(cabin.retiring)return 0;
#endif
    const uintptr_t lo=(uintptr_t)heap,rl=(uintptr_t)room;
    if(!cabin_preflight_ready || cabin_event_reader_fault || cabin.id || !cabin_key(id) || !heap_bytes || !room_bytes ||
       lo+heap_bytes<lo || rl+room_bytes<rl){cabin_failure("cabin entry ownership");return 0;}
    cabin=CabinSource{};cabin.id=id;cabin.heap_begin=lo;cabin.heap_end=lo+heap_bytes;
    cabin.room_begin=rl;cabin.room_end=rl+room_bytes;cabin.beginning=true;
    cabin.movie=re4dc_movie_cabin_open(id);cabin.beginning=false;
    if(!cabin.movie || re4dc_movie_cabin_status(cabin.movie)!=RE4DC_MOVIE_RUNNING){
        cabin_failure("cabin media admission");return 0;
    }
    return 1;
}
extern "C" void re4dc_cabin_event_bound(const void* event,const char* key){
#if RE4DC_CABIN_COMPLETE_HANDOFF
    if(cabin.retiring)return;
#endif
    if(!cabin.id || !key || std::strcmp(key,cabin_key(cabin.id)))return;
    if(cabin.bound || cabin.source_done || cabin.retiring || !event){cabin_failure("cabin event reentry");return;}
    cabin.event=event;cabin.bound=true;
    cabin.audio=re4dc_cabin_audio_owner_open(event,cabin.id);
    if(!cabin.audio)cabin_failure("cabin sound owner admission");
}
extern "C" void re4dc_cabin_cancel_accepted(const void* event){
#if RE4DC_CABIN_COMPLETE_HANDOFF
    if(cabin.retiring)return;
#endif
    if(!cabin.id || cabin.event!=event || !event || cabin.death || cabin.source_done || cabin.failed)return;
    if(!cabin.accepted_skip){
        cabin.accepted_skip=true;
        // EOF already qualified can be held while source packets continue. A
        // later accepted cancel has no remaining transport to accelerate.
        const int status=re4dc_movie_cabin_status(cabin.movie);
        if(status==RE4DC_MOVIE_RUNNING && !re4dc_movie_cabin_skip(cabin.movie))
            cabin_failure("cabin accepted cancel ownership");
    }
}
extern "C" void re4dc_cabin_death_committed(const void* event){
#if RE4DC_CABIN_COMPLETE_HANDOFF
    if(cabin.retiring)return;
#endif
    if(cabin.id==0x11c20 && cabin.event==event && event)cabin.death=true;
}
extern "C" void re4dc_cabin_event_deleted(const void* event){
#if RE4DC_CABIN_COMPLETE_HANDOFF
    if(cabin.retiring)return;
#endif
    if(cabin.id && cabin.event==event && event){cabin.event=nullptr;close_audio();}
}
extern "C" void re4dc_cabin_before_events(){
    re4dc_cabin_carriers_before_events();
    if(cabin_event_reader_fault)return;
    if(cabin_event_readers==~0u){
        cabin_event_reader_fault=true;cabin_failure("cabin event reader overflow");return;
    }
    ++cabin_event_readers;
    service();
}
extern "C" void re4dc_cabin_after_events(){
    re4dc_cabin_carriers_after_events();
    if(cabin_event_reader_fault)return;
    if(!cabin_event_readers){
        cabin_event_reader_fault=true;cabin_failure("cabin event reader imbalance");return;
    }
    --cabin_event_readers;
    service();
}
extern "C" void re4dc_cabin_source_done(unsigned id,int keep){
#if RE4DC_CABIN_COMPLETE_HANDOFF
    if(cabin.retiring)return;
#endif
    if(cabin.id!=id || !cabin.bound || cabin.source_done || (keep && !cabin.death)){
        cabin_failure("cabin source terminal ownership");return;
    }
    if(!close_audio())return;
    cabin.source_done=true;
    // s20 remains a source kept event. Nothing here destroys it or calls mode2.
    re4dc_log("cabin source terminal: id=%05x movie=%u keep=%d death=%d skip=%d\n",
        id,cabin.movie,keep,cabin.death,cabin.accepted_skip);
}
#if RE4DC_CABIN_COMPLETE_HANDOFF
extern "C" int re4dc_cabin_complete_current(unsigned generation,unsigned id){
    return generation && generation==cabin.movie && id && id==cabin.id && cabin.retiring &&
        cabin.source_done && cabin.bound && !cabin.beginning && !cabin.failed && !cabin.halted &&
        !cabin_event_readers && !cabin_event_reader_fault;
}
#endif
extern "C" int re4dc_cabin_aftermath(unsigned id){
#if RE4DC_CABIN_COMPLETE_HANDOFF
    if(cabin.retiring)return 0;
#endif
    if(cabin.id!=id || !cabin.source_done){cabin_failure("cabin aftermath before source terminal");return 0;}
    if(cabin.failed){cabin_failure("cabin aftermath has failed media");return 0;}
    const int status=re4dc_movie_cabin_status(cabin.movie);
#if RE4DC_CABIN_HANDOFF_DIAG
    static unsigned waits=0;
    if(++waits<=3 || waits%120==0)
        re4dc_log("CABIN_HANDOFF n=%u id=%05x movie=%u status=%d readers=%u fault=%u retiring=%u\n",
            waits,id,cabin.movie,status,cabin_event_readers,unsigned(cabin_event_reader_fault),unsigned(cabin.retiring));
#endif
    if(status==RE4DC_MOVIE_RUNNING)return 0;
    if(status!=RE4DC_MOVIE_EOF && status!=RE4DC_MOVIE_SKIP){cabin_failure("cabin aftermath unqualified media");return 0;}
    if(cabin_event_readers || cabin_event_reader_fault || cabin.retiring)return 0;
    cabin.retiring=true;
#if RE4DC_CABIN_COMPLETE_HANDOFF
    const int closed=re4dc_movie_cabin_complete(cabin.movie);
#else
    const int closed=re4dc_movie_cabin_close(cabin.movie);
#endif
    cabin.retiring=false;
    if(!closed)return 0;
    cabin=CabinSource{};return 1;
}
extern "C" int re4dc_cabin_before_heap_change(const void* start,unsigned bytes){
    if(!re4dc_cabin_carriers_before_heap(start,bytes))return 0;
    if(!cabin.id || !bytes)return 1;
    const uintptr_t lo=(uintptr_t)start,hi=lo+bytes;
    if(hi<lo)return 0;
    if(!range_overlap(lo,hi,cabin.heap_begin,cabin.heap_end) &&
       !range_overlap(lo,hi,cabin.room_begin,cabin.room_end))return 1;
    if(cabin.beginning || cabin.retiring || cabin_event_readers || cabin_event_reader_fault || cabin.halted)return 0;
    cabin.retiring=true;
    if(!close_audio()){cabin.retiring=false;return 0;}
    if(!re4dc_movie_cabin_close(cabin.movie)){cabin.retiring=false;return 0;}
    cabin=CabinSource{};cabin_preflight_ready=false;
    return 1;
}
#endif
