#!/usr/bin/env python3
"""Actual stage1 adapters and phase functions, synthetic source/native fixtures.
No target ABI, output pixels, hardware timing or original-RNG equivalence claim.
"""
from pathlib import Path
import os
import subprocess
import tempfile
from test_ps2_fx_common_phase import function
ROOT=Path(__file__).resolve().parents[1]

def harness():
    fixture=(ROOT/'tools/test_ps2_fx_common_haze.cpp').read_text().split('#include "../src/game/ps2_fx_common_haze.inc"')[0]
    fixture=fixture[:fixture.index('extern "C" int re4dc_effect_haze_batch(')]
    fixture=fixture.replace('"../src/', '"'+str(ROOT/'src')+'/').replace('"../port/', '"'+str(ROOT/'port')+'/')
    fixture=fixture.replace('using u32=unsigned;', 'using u32=uintptr_t;') # Synthetic host pointer identity, not source ABI.
    fixture=fixture.replace('#define RE4DC_PS2_FX_COMMON_HAZE 1','#define RE4DC_PS2_FX_COMMON_HAZE 0')
    fixture=fixture.replace('struct cEsp{', 'struct cModel{unsigned serial,be_flag;};struct Parent{Mtx mat;};\nstruct cEsp{')
    fixture=fixture.replace('u32 m_Tool_flg;void* parent;void* m_pMod;', 'u32 m_Tool_flg;Parent* parent;cModel* m_pMod;unsigned m_Guid_pMod;')
    fixture=fixture.replace('Vec m_Speed_plus,m_Ang,m_Ang_plus;', 'Vec m_Speed_plus,m_Ang,m_Ang_plus,m_Speed,m_Pos;')
    fixture=fixture.replace('PS2FX_HAZE=2','PS2FX_HAZE=2,PS2FX_STREAK=8')
    fixture=fixture.replace('static void* pEffParentWorld=(void*)1;', 'static Parent* pEffParentWorld=(Parent*)1;')
    fixture=fixture.replace('unsigned Frame_cnt,Status_flg[4],Stop_flg;', 'unsigned Frame_cnt,Status_flg[4],Stop_flg,System_flg,Debug_flg[3];')
    code=r"""
#define RE4DC_GAME 1
#define RE4DC_COARSE 1
#define RE4DC_PACE_CATCHUP 2
#define RE4DC_PACE_TRANS_SKIP 3072
#define RE4DC_ACTOR_TRANSACTION 0
#define RE4DC_ESP_SPRITE_FAST 1
#define RE4DC_PS2_FX_POPULATION 1
#define RE4DC_PS2_FX_ADDITIONS 1
#define PTSK(b) ((RE4DC_PACE_TRANS_SKIP & (b)) && re4dc_pace_skipping)
"""+fixture+r"""
struct EspGenWork{unsigned id;};struct EspSeqData{unsigned num;};
struct EspgenWork{unsigned flag,id;Info info;void* work;};
EspgenWork* EspgenArray;u32 nEspgen;
static EspSeqData seq={4};static EspGenWork refs[4];
static EspSeqData* EspGetEstAddr(unsigned a,unsigned b,unsigned c){assert(a==1&&b==6&&c==1);return &seq;}
static EspGenWork* re4dc_effect_ref(EspSeqData* h,unsigned n){assert(h==&seq&&n<4);return refs+n;}
static void PSMTXConcat(const Mtx a,const Mtx b,Mtx out){
 Mtx temp={};for(unsigned i=0;i<3;++i){for(unsigned j=0;j<3;++j)for(unsigned k=0;k<3;++k)temp[i][j]+=a[i][k]*b[k][j];
 temp[i][3]=a[i][3];for(unsigned k=0;k<3;++k)temp[i][3]+=a[i][k]*b[k][3];}std::memcpy(out,temp,sizeof(temp));
}
static bool phase_ready,phase_finished;
static unsigned phase_step,phase_begin,phase_coarse,phase_batch,phase_clear,phase_effect;
static unsigned fake_queued,fake_fail_call;
extern "C" int re4dc_effect_stage1_batch(Re4dcEffectSprite* sprites,unsigned count,unsigned dst,unsigned* submitted){
 ++fake_batch_calls;phase_batch=++phase_step;*submitted=0;
 assert((dst==1&&count<=50)||(dst==5&&count<=10));
 for(unsigned n=0;n<count;++n){const auto& s=sprites[n];assert(s.src==4&&s.dst==dst);for(unsigned i=0;i<4;++i)assert(std::isfinite(s.x[i])&&std::isfinite(s.y[i])&&s.z[i]>0);}
 if(!phase_ready||phase_finished||!fake_submit||fake_batch_calls==fake_fail_call||fake_queued+count>64)return 0;
 *submitted=count;fake_queued+=count;fake_submitted+=count;return 1;
}
"""
    esp=(ROOT/'src/game/esp_sub.cpp').read_text()
    code+=esp[esp.index('#if RE4DC_PS2_FX_ADDITIONS\nextern EspgenWork*'):esp.index('#if defined(RE4DC_COARSE_FX_SPRITES) && RE4DC_COARSE_FX_SPRITES',esp.index('static void Ps2fxPuzzleDraw()'))]
    phase=(ROOT/'tools/test_ps2_fx_common_phase.py').read_text()
    stub=phase[phase.index('static unsigned population_builds'):phase.index('"""\n    for file, marker')]
    stub=stub[:stub.index('static void ExecOt(')]
    code+=stub+r"""
static cEsp* observed[3];
static void ExecOt(unsigned ot){if(ot==OT_TYPE_EFFECT){phase_effect=++phase_step;for(auto* e:observed)if(e){
 if(Ps2fxPuzzleSuppress(e))++suppressed_callbacks;else ++fallback_callbacks;}}}
"""
    for file,marker in [('src/game/esp_sub.cpp','extern "C" void re4dc_esp_sprite_pass_begin('),('src/game/main_sub.cpp','void Render_before('),('src/game/trans.cpp','void Render()')]:
        code+=function((ROOT/file).read_text(),marker)+'\n'
    code+=(ROOT/'tools/test_ps2_fx_stage1_phase_fixture.inc').read_text()
    return code

def main():
    with tempfile.TemporaryDirectory(prefix='ps2-fx-stage1-phase-') as tmp:
        source=Path(tmp)/'phase.cpp';binary=Path(tmp)/'phase';source.write_text(harness())
        subprocess.run([os.environ.get('CXX','g++'),'-std=c++11','-O1','-g','-Wall','-Wextra','-Werror','-pedantic','-Wno-narrowing','-Wno-unused-function','-Wno-unused-variable','-ffp-contract=off','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(source),'-o',str(binary)],check=True)
        subprocess.run([str(binary)],check=True)
if __name__=='__main__':main()
