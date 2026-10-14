// Source bodies replace the marked blocks when the retained host test builds.
// Hardware calls, decoder transport and unrelated source drawing are seams.
#include <cassert>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <functional>
#include <stdexcept>
#define RE4DC_CABIN_SOURCE 1
#define RE4DC_CABIN_HANDOFF_DIAG 0
#define RE4DC_ROUTE_MOVIES 1
#define RE4DC_PVR_PIPELINE 2
#define RE4DC_PVR_READY_STRICT RE4DC_PVR_RECOVER
#define RE4DC_PVR_STREAM 1
#define RE4DC_D349_RENDERER_STACK 1
#define RE4DC_TEX_RESIDENT 1
#define RE4DC_MOVIE_WINDOW 1
#define RE4DC_GAME 1
#define RE4DC_PROFILE_SCOPE(x)
#define O_RDONLY 0
#define PVR_TA_INPUT 0
#define PVR_LIST_OP_POLY 0
#define PVR_LIST_TR_POLY 2
enum {RE4DC_MOVIE_RUNNING=0,RE4DC_MOVIE_EOF=1,RE4DC_MOVIE_SKIP=2,RE4DC_MOVIE_ERROR=3,RE4DC_MOVIE_CANCEL=4};
using pvr_ptr_t=void*;using pvr_list_t=int;using file_t=int;struct plm_frame_t{};
// @HEADER@
unsigned checks=0,irq_depth=0,freed=0,claims=0,discarded=0,reset_count=0,waits=0,missing=0;
unsigned opens=0,closes=0,sleeps=0,presented_movie=0,finish_calls=0,audio_closed=0;
unsigned frame=0,present_failures=0,present_submitted=0,present_resolved=0,present_reported=0,fence_blocked=0,fence_timeouts=0;
uint64_t fence_wait_us=0,clock_us=0;
bool direct_open=false,stream_scene=false,draining_parts=false,ready=true,source_draws_finished=false;
void* deferred_first=nullptr;void* deferred_last=nullptr;void* deferred_spill=nullptr;
void* deferred_light_sets=nullptr;void* deferred_basis=nullptr;void* deferred_lights=nullptr;
unsigned deferred_spill_top=0,deferred_spill_capacity=0,deferred_top=0,deferred_count=0;unsigned char frame_storage[64];
namespace re4dc{namespace room{namespace ps2{struct {bool pending=false;unsigned frame=0,flushed=0;}state;}}}
bool stream_aborted=false,stream_retire=false,frame_ready=true,pending=false,hold_pending=false;
bool gpu_ok=true,gpu_leaves_busy=false,wait_ok=true,list_fail=false,scene_fail=false,async_fail=false,present_wait_fail=false;
struct {bool ta_busy=false,render_busy=false;} pvr_state;
pvr_list_t stream_list=0,desired_list=0;unsigned stream_discards=0,stream_black_frames=0;
pvr_ptr_t movie_texture=nullptr;bool movie_picture=false,movie_background=false;
unsigned movie_width=0,movie_height=0,movie_upload_serial=0,movie_shown_serial=0,movie_presentations=0;
uint64_t movie_first_picture_us=0;
struct Entry{};Entry entries[0];void close_entry(Entry&){}
struct {bool field_rendering=false;}Rmode;struct {float width=640,height=480;}Screen;
struct {unsigned System_flg=0;}global_work;auto* pG=&global_work;
void* pFrame_buff[2]={(void*)1,(void*)2};void* pCurrent_buff=pFrame_buff[0];
void check(bool value){++checks;if(!value){fprintf(stderr,"check %u failed\n",checks);assert(value);}}
unsigned irq_disable(){unsigned old=irq_depth;irq_depth=1;return old;}
void irq_restore(unsigned old){irq_depth=old;}
void re4dc_log(const char*,...){}
void re4dc_missing(const char*){++missing;} // Intentionally returns: failure must still retain owners.
uint64_t timer_us_gettime64(){return ++clock_us;}
std::function<void(int)> hook;
void yield_hook(int phase){if(hook){check(irq_depth==0);auto call=hook;hook={};call(phase);}}
int pvr_present_pending(){return pending;}
int pvr_present_wait(){++waits;yield_hook(1);if(!hold_pending){pending=false;pvr_state.ta_busy=false;pvr_state.render_busy=false;}return present_wait_fail?-1:0;}
int pvr_present_async(bool present){if(async_fail)return -1;pending=true;if(present&&movie_texture&&movie_picture)++presented_movie;return 0;}
void pvr_scene_begin(){++opens;pvr_state.ta_busy=true;}
int pvr_list_begin(pvr_list_t){return 0;}
int pvr_list_finish(){yield_hook(5);return list_fail?-1:0;}
int pvr_scene_finish(){++closes;pvr_state.render_busy=true;return scene_fail?-1:0;}
void sq_lock(void*){}void sq_unlock(){}
namespace re4dc{namespace gpu{enum class FenceResult{ready,pending};FenceResult quiesce(){++waits;yield_hook(2);if(gpu_ok&&!gpu_leaves_busy)pvr_state.ta_busy=pvr_state.render_busy=false;return gpu_ok?FenceResult::ready:FenceResult::pending;}}}
namespace pvr_ready{unsigned ta_timeouts=0,render_timeouts=0;int present_wait(){return pvr_present_wait();}bool wait_clear(bool& busy,const char*,char,unsigned&){++waits;yield_hook(3);if(wait_ok&&!gpu_leaves_busy)busy=false;return wait_ok;} }
bool vram_claim(unsigned,bool){++claims;return true;}
pvr_ptr_t pvr_mem_malloc(unsigned){return (void*)0x12340000;}
void pvr_mem_free(pvr_ptr_t ptr){check(ptr==(void*)0x12340000);yield_hook(4);++freed;}
void re4dc_ui_vram_unclaim(){yield_hook(6);check(claims==1);--claims;}
void* re4dc_ui_movie_texture(){return movie_texture;}
void re4dc_model_draw_plan_frame(unsigned){}int re4dc_vi_black(){return 0;}
void stream_open();void stream_close(bool);
void re4dc_ui_present(){if(!stream_scene)stream_open();stream_close(true);}
extern "C" int re4dc_ui_movie_open(unsigned,unsigned);extern "C" int re4dc_ui_movie_close();extern "C" int re4dc_ui_movie_try_close();
// @UI@
struct Movie {bool texture=false,entered=false;void* tex=nullptr;unsigned id=0,k=0;plm_frame_t* pending=nullptr;}m;
int cabin_movie_finish(int);int cabin_movie_fast_final(){assert(false);return 0;}int iterate(void*,bool){assert(false);return 0;}
// @MOVIE@
int cabin_movie_finish(int){++finish_calls;return cabin_movie.terminal;}
struct Re4dcIoScope{};
file_t fs_open(const char*,int){return -1;}unsigned fs_total(file_t){return 0;}void fs_close(file_t){}
namespace re4dc{namespace storage{bool read_exact(file_t,void*,unsigned){return false;}}}
extern "C" int re4dc_movie_cabin_available(unsigned){return 0;}
extern "C" unsigned re4dc_movie_cabin_open(unsigned){return 0;}
extern "C" unsigned re4dc_cabin_audio_owner_open(const void*,unsigned){return 0;}
extern "C" int re4dc_cabin_audio_owner_close(unsigned){++audio_closed;return 1;}
extern "C" unsigned re4dc_cabin_audio_error(unsigned){return 0;}
void re4dc_cabin_carriers_before_events(){}void re4dc_cabin_carriers_after_events(){}
int re4dc_cabin_carriers_before_heap(const void*,unsigned){return 1;}
// @CABIN@
void re4dc_ui_begin(){++frame;stream_aborted=false;source_draws_finished=false;}
void GXSetViewportJitter(float,float,float,float,float,float,int){}void GXSetViewport(float,float,float,float,float,float){}
int VIGetNextField(){return 0;}void GXInvalidateVtxCache(){}void GXInvalidateTexAll(){}void Bg_brightness_set(float){}
void VISetNextFrameBuffer(void*){}void VIFlush(){}
void Render(){stream_open();} // Unrelated source draw packets seam: opens the actual stream owner.
void SceSleep(int);
// @RENDER@
void SceSleep(int frames){check(frames==1);++sleeps;check(stream_scene);if(sleeps>=8)throw std::runtime_error("bounded old retry");Render_swap();Render_before();Render();}
void reset(unsigned id=0x11c00,int terminal=RE4DC_MOVIE_EOF){
    check(irq_depth==0);hook={};direct_open=stream_scene=draining_parts=source_draws_finished=false;
    stream_aborted=stream_retire=pending=hold_pending=gpu_leaves_busy=list_fail=scene_fail=async_fail=present_wait_fail=false;
    ready=frame_ready=gpu_ok=wait_ok=true;pvr_state={};present_failures=present_submitted=present_resolved=present_reported=0;
    freed=claims=discarded=reset_count=waits=missing=opens=closes=sleeps=presented_movie=finish_calls=audio_closed=0;
    movie_texture=nullptr;movie_picture=movie_background=false;movie_cabin_ui_busy=false;
    check(re4dc_ui_movie_open(288,192));movie_picture=movie_background=true;movie_upload_serial=movie_shown_serial=2236;
    m=Movie{};m.id=id;m.texture=m.entered=true;m.tex=movie_texture;
    cabin_movie=CabinMovie{};cabin_movie.generation=++cabin_movie_epoch;cabin_movie.ui_generation=movie_cabin_ui_epoch;
    cabin_movie.final_upload=2236;cabin_movie.checked=cabin_movie.transport_retired=true;cabin_movie.terminal=terminal;
    cabin=CabinSource{};cabin.id=id;cabin.movie=cabin_movie.generation;cabin.bound=true;cabin.event=(void*)0x99900000;
    cabin.heap_begin=0x1000;cabin.heap_end=0x2000;cabin.room_begin=0x3000;cabin.room_end=0x4000;
    cabin_event_readers=0;cabin_event_reader_fault=false;cabin_preflight_ready=true;
    deferred_first=deferred_last=deferred_spill=deferred_light_sets=deferred_basis=deferred_lights=(void*)0x55550000;
    deferred_spill_top=deferred_spill_capacity=deferred_top=deferred_count=55;
    re4dc::room::ps2::state={true,frame,frame-1};
}
void open_frame(){Render_before();Render();check(stream_scene&&pvr_state.ta_busy);}
void retained(){check(cabin.id&&cabin_movie.generation&&m.texture&&m.tex&&movie_texture&&claims==1&&freed==0);check(movie_picture&&movie_background);check(!cabin.retiring&&!cabin_movie.retiring&&!movie_cabin_ui_busy&&!irq_depth);}
void reenter(int){
    const auto id=cabin.id,gen=cabin.movie,ui=cabin_movie.ui_generation;const auto ptr=movie_texture;
    check(cabin.retiring&&cabin_movie.retiring&&movie_cabin_ui_busy);
    check(!re4dc_cabin_aftermath(id));check(!re4dc_cabin_aftermath(id+1));
    check(!re4dc_cabin_preflight(0));check(!re4dc_cabin_begin(id,(void*)0x1000,0x1000,(void*)0x3000,0x1000));
    re4dc_cabin_source_done(id,0);re4dc_cabin_event_bound((void*)1,"event/evd/r11cs00.evd");
    re4dc_cabin_cancel_accepted(cabin.event);re4dc_cabin_death_committed(cabin.event);re4dc_cabin_event_deleted(cabin.event);
    check(cabin.event==(void*)0x99900000&&!cabin.failed&&!cabin.halted&&!cabin.accepted_skip&&!cabin.death);
    check(!re4dc_cabin_before_heap_change((void*)0x1000,16));
    check(!re4dc_movie_cabin_close(gen));check(re4dc_movie_cabin_abort(gen)==RE4DC_MOVIE_ERROR);
    check(re4dc_movie_cabin_step(gen)==RE4DC_MOVIE_ERROR);check(!re4dc_movie_cabin_skip(gen));
#if RE4DC_CABIN_COMPLETE_HANDOFF
    check(!re4dc_movie_cabin_complete(gen));check(!re4dc_ui_movie_cabin_complete(ui,ptr,2236,gen));
#endif
    check(!re4dc_ui_movie_open(288,192));check(!re4dc_ui_movie_close());check(!re4dc_ui_movie_try_close());check(!re4dc_ui_movie_cabin_try_close(ui));
    re4dc_cabin_before_events();re4dc_cabin_after_events();check(cabin_event_readers==0);
}
int main(){
    reset();open_frame();
#if !RE4DC_CABIN_COMPLETE_HANDOFF
    bool exhausted=false;try{r11c_cabin_done(0x11c00,0);}catch(const std::runtime_error&){exhausted=true;}
    check(exhausted&&sleeps==8&&opens==8&&freed==0&&discarded==0);retained();
    printf("PASS OFF: 8 source aftermath retries each see a newly opened actual stream; no completion/free\n");
#else
    for(unsigned id:{0x11c00u,0x11c10u})for(int terminal:{RE4DC_MOVIE_EOF,RE4DC_MOVIE_SKIP}){
        reset(id,terminal);open_frame();r11c_cabin_done(id,0);
        check(!cabin.id&&!cabin_movie.generation&&!m.texture&&!movie_texture&&freed==1&&claims==0);
        check(sleeps==0&&discarded==1&&stream_aborted&&!stream_scene&&!pvr_state.ta_busy&&!pvr_state.render_busy&&!pending);
        check(!deferred_first&&!deferred_last&&!deferred_spill&&!deferred_light_sets&&!deferred_basis&&!deferred_lights);
        check(deferred_top==sizeof(frame_storage)&&!deferred_count&&!deferred_spill_top&&!deferred_spill_capacity);
        check(!re4dc::room::ps2::state.pending&&re4dc::room::ps2::state.frame==~0u&&re4dc::room::ps2::state.flushed==~0u);
        Render_swap();check(presented_movie==0);open_frame();check(opens==2&&!stream_aborted&&!movie_texture);Render_swap();
    }
    reset(0x11c20);cabin.death=true;open_frame();r11c_cabin_done(0x11c20,1);check(cabin.id==0x11c20&&discarded==0&&waits==0&&freed==0);
    // Exact movie qualifications reject before UI state is modified.
    for(int which=0;which<13;++which){
        reset();cabin.source_done=true;open_frame();unsigned gen=cabin.movie;
        if(which==0)++gen;if(which==1)cabin_movie.readers=1;if(which==2)cabin_movie.finishing=true;
        if(which==3)cabin_movie.retiring=true;if(which==4)cabin_movie.transport_retired=false;
        if(which==5)cabin_movie.terminal=RE4DC_MOVIE_RUNNING;if(which==6)cabin_movie.checked=false;
        if(which==7)cabin_movie.final_upload=0;if(which==8)++cabin_movie.ui_generation;
        if(which==9)m.tex=(void*)0x77770000;if(which==10)++movie_upload_serial;
        if(which==11)--movie_shown_serial;if(which==12)cabin_movie.terminal=RE4DC_MOVIE_ERROR;
        cabin.retiring=true;check(!re4dc_movie_cabin_complete(gen));check(discarded==0&&waits==0&&freed==0&&movie_texture&&stream_scene);
    }
    for(int which=0;which<5;++which){
        reset();cabin.source_done=true;open_frame();
        if(which==0)direct_open=true;if(which==1)draining_parts=true;if(which==2)cabin_event_readers=1;
        if(which==3)cabin_event_reader_fault=true;if(which==4)ready=false;
        check(!re4dc_cabin_aftermath(cabin.id));check(discarded==0&&reset_count==0&&waits==0&&freed==0&&stream_scene);
    }
    // Pending despite a successful waiter must retain; a later successful attempt can complete.
    reset();cabin.source_done=true;open_frame();hold_pending=true;
    check(!re4dc_cabin_aftermath(cabin.id));check(pending&&present_failures==0);retained();
    hold_pending=false;check(re4dc_cabin_aftermath(cabin.id));check(freed==1&&!movie_texture);
    for(int which=0;which<5;++which){
        reset();cabin.source_done=true;open_frame();
        if(which==0){present_wait_fail=true;hold_pending=true;}if(which==1)async_fail=true;
        if(which==2)present_failures=1;if(which==3)list_fail=true;if(which==4)scene_fail=true;
        check(!re4dc_cabin_aftermath(cabin.id));retained();
        if(which>=3){check(movie_cabin_ui_close_fault==movie_cabin_ui_epoch&&missing==1);list_fail=scene_fail=false;
            check(!re4dc_cabin_aftermath(cabin.id));retained();}
    }
    // Every close/fence boundary rechecks source/movie/UI generation, pointers,
    // upload serial and live readers before releasing either ownership record.
    for(int phase:{1,2,3,5})for(int which=0;which<14;++which){
#if RE4DC_PVR_RECOVER
        if(phase==2)continue;
#else
        if(phase==3)continue;
#endif
        reset();cabin.source_done=true;open_frame();bool seen=false;
        std::function<void(int)> stale;stale=[&](int at){if(at!=phase){hook=stale;return;}seen=true;
            if(which==0)++movie_cabin_ui_epoch;if(which==1)movie_texture=(void*)0x88880000;
            if(which==2)++movie_upload_serial;if(which==3)--movie_shown_serial;
            if(which==4)++cabin_movie.generation;if(which==5)cabin_movie.readers=1;
            if(which==6)++cabin.id;if(which==7)re4dc_cabin_before_events();
            if(which==8)cabin_event_reader_fault=true;if(which==9)cabin_movie.terminal=RE4DC_MOVIE_ERROR;
            if(which==10)cabin_movie.transport_retired=false;if(which==11)cabin_movie.checked=false;
            if(which==12)m.tex=(void*)0x44440000;if(which==13)cabin.failed=true;};hook=stale;
        check(!re4dc_cabin_aftermath(cabin.id));retained();
        check(seen);
        if(which==7){check(cabin_event_readers==1);re4dc_cabin_after_events();check(cabin_event_readers==0);
            check(re4dc_cabin_aftermath(cabin.id));check(freed==1&&!movie_texture&&!cabin.id);}
    }
    for(int phase:{1,2,3,4,5,6}){
#if RE4DC_PVR_RECOVER
        if(phase==2)continue;
#else
        if(phase==3)continue;
#endif
        reset();cabin.source_done=true;open_frame();bool seen=false;
        // Rearm at earlier seams until the requested boundary is reached.
        std::function<void(int)> probe;probe=[&](int at){if(at==phase){seen=true;reenter(at);}else hook=probe;};hook=probe;
        check(re4dc_cabin_aftermath(cabin.id));check(seen&&freed==1&&!movie_texture&&!cabin.id&&!irq_depth);
    }
    reset();cabin.source_done=true;open_frame();
    std::function<void(int)> badgpu;badgpu=[&](int at){if(at==2 || at==3){pvr_state.ta_busy=true;pvr_state.render_busy=true;gpu_leaves_busy=true;}
        else hook=badgpu;};
    // Seed false-ready busy state after the present service has resolved.
    hook=badgpu;
    check(!re4dc_cabin_aftermath(cabin.id));retained();gpu_leaves_busy=false;
    check(re4dc_cabin_aftermath(cabin.id));
    reset();cabin.source_done=true;open_frame();gpu_ok=false;wait_ok=false;
    check(!re4dc_cabin_aftermath(cabin.id));retained();gpu_ok=wait_ok=true;check(re4dc_cabin_aftermath(cabin.id));
    // A close fault is sticky for that epoch, even after the low-level failure
    // stops. An identical address/final serial in a fresh owner is independent.
    reset();cabin.source_done=true;open_frame();list_fail=true;
    const unsigned failed_epoch=movie_cabin_ui_epoch;check(!re4dc_cabin_aftermath(cabin.id));retained();
    reset();cabin.source_done=true;open_frame();check(movie_cabin_ui_epoch>failed_epoch&&movie_cabin_ui_close_fault==failed_epoch);
    check(re4dc_cabin_aftermath(cabin.id)&&freed==1);
    // Heap change remains strictly nonblocking even with source terminal qualified.
    reset();cabin.source_done=true;open_frame();check(!re4dc_cabin_before_heap_change((void*)0x1000,16));
    check(waits==0&&discarded==0&&reset_count==0&&freed==0&&stream_scene);retained();
    printf("PASS ON recover=%d: source schedule completes, next frame reopens; qualifications, failures, stale owners, reentry and nonblocking heap retirement (%u checks)\n",RE4DC_PVR_RECOVER,checks);
#endif
}
