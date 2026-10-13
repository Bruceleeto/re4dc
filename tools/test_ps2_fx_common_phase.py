#!/usr/bin/env python3
"""Run the actual pass-begin, Render_before and Render around common haze.

Synthetic source objects/native frame boundaries; actual production function
bodies and common adapter. No target ABI, pixels or performance claim.
"""
from pathlib import Path
import os
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def function(text, marker):
    start = text.index(marker)
    begin = text.index("{", start)
    depth, end = 1, begin + 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end]


def harness():
    fixture = (ROOT / "tools/test_ps2_fx_common_haze.cpp").read_text().split("int main(){")[0]
    fixture = fixture.replace('"../src/', '"' + str(ROOT / 'src') + '/')
    fixture = fixture.replace('"../port/', '"' + str(ROOT / 'port') + '/')
    fixture = fixture.replace('unsigned Frame_cnt,Status_flg[4],Stop_flg;',
                              'unsigned Frame_cnt,Status_flg[4],Stop_flg,System_flg,Debug_flg[3];')
    fixture = fixture.replace('extern "C" int re4dc_effect_haze_batch(', r"""
static bool phase_ready,phase_finished;
static unsigned phase_step,phase_begin,phase_coarse,phase_batch,phase_clear,phase_effect;
extern "C" int re4dc_effect_haze_batch(""")
    fixture = fixture.replace('*submitted=fake_submit?n:0;fake_submitted+=*submitted;return fake_submit;',
                              'phase_batch=++phase_step;const bool ok=fake_submit && phase_ready && !phase_finished;'
                              '*submitted=ok?n:0;fake_submitted+=*submitted;return ok;')
    code = r"""
#define RE4DC_GAME 1
#define RE4DC_COARSE 1
#define RE4DC_PACE_CATCHUP 2
#define RE4DC_PACE_TRANS_SKIP 3072
#define RE4DC_ACTOR_TRANSACTION 0
#define RE4DC_ESP_SPRITE_FAST 1
#define RE4DC_PS2_FX_POPULATION 1
#define RE4DC_PS2_FX_ADDITIONS 0
#define PTSK(b) ((RE4DC_PACE_TRANS_SKIP & (b)) && re4dc_pace_skipping)
""" + fixture + r"""
static unsigned population_builds,fallback_callbacks,suppressed_callbacks;
static float s_vis_far;
static float fog_far(){return 8000;}
static float (*re4dc_fog_gate_far)()=fog_far;
static void Ps2fxPopulationBuild(){++population_builds;}
static int re4dc_pace_skipping,re4dc_esp_logic_queued,re4dc_coarse_image;
static void* g_prev_tpl_addr;static void* g_prev_add_tpl_addr;
static Camera itemCamera;
struct {int field_rendering;} Rmode;
struct {float width=640,height=480;} Screen;
struct {void setFog(){}} LightMgr;
static float ZNEAR=1,ZFAR=10000;
#define FRef(value) value
extern "C" void re4dc_ui_begin(){phase_ready=true;phase_finished=false;phase_begin=++phase_step;}
static void re4dc_ui_begin_skip(){phase_ready=false;phase_finished=false;phase_begin=++phase_step;}
static void GXSetViewport(float x,float y,float w,float h,float n,float f){
 const float v[6]={x,y,w,h,n,f};std::memcpy(fake_viewport,v,sizeof(v));
}
static void GXSetViewportJitter(float x,float y,float w,float h,float n,float f,unsigned){GXSetViewport(x,y,w,h,n,f);}
static unsigned VIGetNextField(){return 0;}
static void GXInvalidateVtxCache(){}static void GXInvalidateTexAll(){}static void Bg_brightness_set(float){}
static void GXSetCurrentGXThread(){}static void SetScissorState(){}static void SetDrawTmpBufType(int){}
static void re4dc_coarse_draw(){phase_coarse=++phase_step;}
static void bio4_AddBgColor(){}static void drawGround(int){}
static void ClearZbuf(){phase_clear=++phase_step;}
static void GXSetFog(int,float,float,float,float,GXColor){}static int Filter09GetbUse(){return 0;}
static void Filter09Render(int){}static void Render_DrawSyncCallback(unsigned short){}
static void GXSetDrawSync(unsigned){phase_finished=true;}static void GXSetDrawSyncCallback(void (*)(unsigned short)){}
enum { OT_TYPE_TEX_RENDER1=1,OT_TYPE_SHADOW_SETUP,OT_TYPE_SUBSCRN_FAR,OT_TYPE_SCROLL,
 OT_TYPE_SUBSCRN,OT_TYPE_MODEL,OT_TYPE_SHADOW_DRAW,OT_TYPE_SUBSCRN_NEAR,OT_TYPE_EFFECT,
 OT_TYPE_WORLD,OT_TYPE_EFFECT_VU1,OT_TYPE_SCREEN,OT_TYPE_COCKPIT,OT_TYPE_ID_MODEL,
 OT_TYPE_MESSAGE,OT_TYPE_AFTER_RENDER,OT_TYPE_DEBUG,OT_TYPE_MAX };
static void ExecOt(unsigned ot){if(ot==OT_TYPE_EFFECT){phase_effect=++phase_step;
 if(Ps2fxCommonHazeSuppress(particle(0)))++suppressed_callbacks;else ++fallback_callbacks;}}
"""
    for file, marker in [('src/game/esp_sub.cpp', 'extern "C" void re4dc_esp_sprite_pass_begin('),
                         ('src/game/main_sub.cpp', 'void Render_before('),
                         ('src/game/trans.cpp', 'void Render()')]:
        code += function((ROOT / file).read_text(), marker) + '\n'
    return code + r"""
static unsigned cases;
static void prepare(){
 fill(0x100);phase_step=phase_begin=phase_coarse=phase_batch=phase_clear=phase_effect=0;
 phase_ready=false;phase_finished=true;re4dc_pace_skipping=re4dc_esp_logic_queued=0;re4dc_coarse_image=1;
 fake_resident=fake_submit=true;sys.pEspBuf=source_pool;g_pEspSys=&sys;
 const unsigned calls=fake_batch_calls,populations=population_builds;
 ps2fx::CommonHazeClock clocks[2];std::memcpy(clocks,s_common_haze,sizeof(clocks));
 std::memcpy(source_copy,source_pool,sizeof(source_pool));re4dc_esp_sprite_pass_begin();
 assert(s_common_pending.pending && !s_common_accepted && !Ps2fxCommonHazeSuppress(particle(0)));
 assert(fake_batch_calls==calls && population_builds==populations+1 && s_vis_far==8000);
 assert(!std::memcmp(clocks,s_common_haze,sizeof(clocks)) && !std::memcmp(source_copy,source_pool,sizeof(source_pool)));
}
static void draw(){Render_before();Render();assert(!s_common_pending.pending);assert(!std::memcmp(source_copy,source_pool,sizeof(source_pool)));}
static void refused(){
 const unsigned calls=fake_batch_calls,fall=fallback_callbacks;
 ps2fx::CommonHazeClock clocks[2];std::memcpy(clocks,s_common_haze,sizeof(clocks));draw();
 assert(fake_batch_calls==calls && fallback_callbacks==fall+1 && !s_common_accepted);
 assert(!std::memcmp(clocks,s_common_haze,sizeof(clocks)));++cases;
}
int main(){
 sys.pEspBuf=source_pool;globals.Cam.param.at={0,0,-1};globals.Cam.up={0,1,0};setup_weather();setup_submit();
 for(unsigned i=30;i<=31;++i){auto& tw=sys.Esp_tex_tbl[i];tw.Owner=0;tw.pTpl=&tpl;tw.pAnm=&anm;tw.mtx[0][0]=tw.mtx[1][1]=1;}
 prepare();const unsigned source_frame=globals.Frame_cnt;const unsigned before=fake_batch_calls,previous_suppressed=suppressed_callbacks;
 draw();assert(globals.Frame_cnt==source_frame && fake_batch_calls==before+1 && suppressed_callbacks==previous_suppressed+1);
 assert(phase_begin<phase_coarse && phase_coarse<phase_batch && phase_batch<phase_clear && phase_clear<phase_effect);
 assert(Ps2fxCommonHazeSuppress(particle(0)));++cases;
 // Duplicate/no-ticket render hooks retain accepted suppression but never replay.
 re4dc_ps2_fx_common_render(1,0);assert(fake_batch_calls==before+1 && Ps2fxCommonHazeSuppress(particle(0)));++cases;
 ++globals.Frame_cnt;assert(!Ps2fxCommonHazeSuppress(particle(0)));re4dc_ps2_fx_common_render(1,0);assert(fake_batch_calls==before+1);++cases;
 // No preparation on a dropped Trans tick: no token and no candidate submission.
 re4dc_coarse_image=1;draw();assert(fake_batch_calls==before+1 && !Ps2fxCommonHazeSuppress(particle(0)));++cases;
 // Source and native clock numbers need exact equality, not next-frame +1.
 prepare();++globals.Frame_cnt;refused();prepare();--globals.Frame_cnt;refused();
 prepare();++G_ROOM_ID;refused();prepare();sys.pEspBuf=source_pool+0x150;refused();sys.pEspBuf=source_pool;
 prepare();--sys.nEsp;refused();prepare();++sys.nEsp;refused();
 prepare();++fake_generation;refused();prepare();fake_resident=false;refused();fake_resident=true;
 prepare();re4dc_coarse_image=0;refused();
 // A full Render early return still consumes a skipped image. Turning drawing
 // back on in the same source frame cannot replay that retired token.
 prepare();const unsigned skip_calls=fake_batch_calls;re4dc_pace_skipping=1;draw();
 assert(!phase_effect && fake_batch_calls==skip_calls && !s_common_accepted);++cases;
 re4dc_pace_skipping=0;re4dc_coarse_image=1;draw();assert(fake_batch_calls==skip_calls && !s_common_accepted);++cases;
 // Logic-only skipped OTs also reject before submission, but keep fallback.
 prepare();re4dc_pace_skipping=1;re4dc_esp_logic_queued=1;refused();
 // Batch refusal preserves the queued source callback; a later frame may own
 // a fresh ticket, but no second attempt is possible in the failed frame.
 prepare();fake_submit=false;const unsigned failed_calls=fake_batch_calls,failed_fallback=fallback_callbacks;draw();
 assert(fake_batch_calls==failed_calls+1 && fallback_callbacks==failed_fallback+1 && !s_common_accepted);++cases;
 fake_submit=true;re4dc_ps2_fx_common_render(1,0);assert(fake_batch_calls==failed_calls+1 && !s_common_accepted);++cases;
 prepare();draw();assert(s_common_accepted && Ps2fxCommonHazeSuppress(particle(0)));++cases;
 // Preparation clears prior acceptance without resetting qualified clocks.
 const auto clock=s_common_haze[0];const unsigned clear_calls=fake_batch_calls;re4dc_esp_sprite_pass_begin();
 assert(!s_common_accepted && fake_batch_calls==clear_calls && !std::memcmp(&clock,&s_common_haze[0],sizeof(clock)));++cases;
 // Invalid preparation never leaves a borrowed pool token or stale suppression.
 fake_resident=false;re4dc_esp_sprite_pass_begin();assert(!s_common_pending.pending && !s_common_accepted);fake_resident=true;++cases;
 fake_generation=0;re4dc_esp_sprite_pass_begin();assert(!s_common_pending.pending);++fake_generation;++cases;
 sys.nEsp=2049;re4dc_esp_sprite_pass_begin();assert(!s_common_pending.pending);++cases;
 g_pEspSys=nullptr;re4dc_esp_sprite_pass_begin();assert(!s_common_pending.pending);g_pEspSys=&sys;++cases;
 prepare();re4dc_ps2fx=0;draw();assert(!s_common_accepted && !Ps2fxCommonHazeSuppress(particle(0)));re4dc_ps2fx=PS2FX_HAZE;++cases;
 std::printf("PASS actual common phase: %u cases; prepare -> next Render same source frame, native begin/coarse/batch/effect order, one-use identity, skip/drop, batch fallback, immutable source\n",cases);
}
"""


def main():
    with tempfile.TemporaryDirectory(prefix='ps2-fx-common-phase-') as tmp:
        source = Path(tmp) / 'phase.cpp'
        binary = Path(tmp) / 'phase'
        source.write_text(harness())
        subprocess.run([os.environ.get('CXX', 'g++'), '-std=c++11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-pedantic', '-Wno-unused-function', '-Wno-unused-variable', '-ffp-contract=off',
                        '-fsanitize=address,undefined', '-fno-omit-frame-pointer', str(source), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == '__main__':
    main()
