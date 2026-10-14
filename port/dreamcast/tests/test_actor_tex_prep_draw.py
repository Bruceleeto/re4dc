#!/usr/bin/env python3
"""Production ledger/filter and ModelTrans post-OT decision block.
OT insertion is an unchanged boundary: its result is injected. The complete
production block from that result through screen failure, invisible skip,
light handling and the new hint is compiled, with real source identity checks.
"""
import test_actor_tex_prep as a

def harness():
    trans=(a.ROOT/'src/game/trans.cpp').read_text()
    s='#include <sys/mman.h>\n#include <unistd.h>\n'+a.ledger_harness()
    s=s.replace('serial=1,id=0x15,type=1;', 'serial=1,id=0x15,type=1,kindid=0,ot_type=7,be_flag=3;struct {unsigned pLight[4];} LightInfo;')
    s=s.replace('stage_no=1,room_no=1;', 'stage_no=1,room_no=1,Debug_flg[1]{},Disp_flg=0;')
    s=s.replace('check(sourceActorLedger.complete(frame,t,sourceActorModel(models+i)));', 'check(sourceActorLedger.note_texture_draw(frame,sourceActorModel(models+i)));check(sourceActorLedger.complete(frame,t,sourceActorModel(models+i)));')
    s=s.replace('int main(){','int legacy_main(){').replace('std::printf("actor texture ledger:', 'return 0;std::printf("actor texture ledger:')
    fn=trans[trans.index('void ModelTrans('):trans.index('\nint commonScreenMat(')].rstrip()
    start=fn.index('    ENCV_TRANS_NOTE(m, ret != 0xFFFF ?')
    tail=fn[start:]
    # Enable the unmodified SH-only lean block on a host without pretending the
    # entire source header/ABI is SH. Only this preprocessing predicate changes.
    tail=tail.replace('RE4DC_FRONT_LEAN && defined(__sh__)', 'RE4DC_FRONT_LEAN && defined(DRAW_TEST_TARGET_LEAN)')
    s+='\n'+a.function(trans,'bool sourceActorRam(')+'\n'+a.function(trans,'void sourceActorTextureDraw(')+r'''
using u16=unsigned short;
#define ENCV_TRANS_NOTE(m,reason) ((void)0)
bool g_invisArmed=true,hidden=false;unsigned deleted=0,lights=0,screen_calls=0;int screen_ok=1,inject=0;
int g_skinLazyArm=0,g_leanWeights=0;unsigned g_leanSkippedNum=0;const unsigned FRONT_LEAN_WEIGHTS=1,FRONT_LEAN_LIGHTS=2;
cModel* g_leanSkipped[8];int lean_value=0;
void memclr_asm(void* p,unsigned n){std::memset(p,0,n);}
int frontLean(cModel*){return lean_value;}
int invisSkip(cModel*,int,int){return hidden;}
int commonScreenMat(cModel*){
 ++screen_calls;
 if(inject==1)++pG->Frame_cnt;if(inject==2)++room_generation;
 if(inject==3)++sourceActorPrimBase;if(inject==4)++re4dc_alive_gen[1];
 if(inject==5)sourceActorLedger.retire();if(inject==6)sourceActorRenderActive=true;
 if(inject==7)sourceActorActive=false;
 return screen_ok;
}
void DeleteOtData(int,u16){++deleted;}
void lightSetEm(cModel*){++lights;}void lightSetObj(cModel*){++lights;}
void post_ot(cModel* m,int ret,int ot=1,int ret2=1,int ot2=2){
'''+tail+r'''
void fresh(){reset(3,false);deleted=lights=screen_calls=0;screen_ok=1;inject=0;hidden=false;g_invisArmed=true;lean_value=g_leanWeights=0;g_leanSkippedNum=0;}
void finish(unsigned visible_mask,unsigned failed_mask=0,unsigned outside_mask=0,unsigned hidden_mask=0){
 FrameIdentity f{};check(sourceActorIdentity(f));
 for(unsigned i=0;i<3;++i){
  PreparationTicket ticket{};auto id=sourceActorModel(models+i);check(sourceActorLedger.claim(f,ticket));
  check(!sourceActorLedger.texture_draw(f,id));
  if(visible_mask&(1u<<i)){
   screen_ok=!(failed_mask&(1u<<i));hidden=hidden_mask&(1u<<i);
   post_ot(models+i,(outside_mask&(1u<<i))?0xffff:1);
  }
  check(!sourceActorLedger.texture_draw(f,id));
  check(sourceActorLedger.complete(f,ticket,id));
 }
}
int main(){
 legacy_main();
 // Completed emTrans alone is not a draw; player preparation remains mandatory.
 fresh();player_reason=0;finish(0);auto b=run(true);
 check(b.count==1&&b.picks[0].kind==Re4dcActorTexKind::PlayerPl08&&metadata_calls==0);
 check(b.declined[unsigned(Re4dcActorTexReason::Hidden)]==2);
 fresh();models[2].type=2;finish(2);b=run(true);check(b.count==2&&b.qualified==1&&metadata_calls==1);
 fresh();models[2].type=2;finish(6);b=run(true);check(b.count==4&&b.qualified==2&&metadata_calls==2);
 // Source OT rejection, matrix failure (both OTs), and invis replay cannot hint.
 fresh();finish(2,0,2);check(!screen_calls&&!deleted);b=run(true);check(!b.count);
 fresh();finish(2,2);check(screen_calls==1&&deleted==2);b=run(true);check(!b.count);
#if RE4DC_CROWD_INVIS_SKIP
 fresh();finish(2,0,0,2);check(!screen_calls&&!deleted);b=run(true);check(!b.count);
#endif
 // Every source/primitive identity is rechecked after the potentially yielding
 // screen work. Retirement never dereferences the old borrowed ledger.
 for(int j=1;j<=7;++j){fresh();FrameIdentity f{};check(sourceActorIdentity(f));PreparationTicket ticket{};
  check(sourceActorLedger.claim(f,ticket));inject=j;post_ot(models,1);
  check(entries[0].texture_draw==0);
 }
 // Wrong model or serial, wrong callback phase and stale frame cannot write.
 fresh();FrameIdentity f{};check(sourceActorIdentity(f));auto id=sourceActorModel(models);
 check(!sourceActorLedger.note_texture_draw(f,id));PreparationTicket ticket{};check(sourceActorLedger.claim(f,ticket));
 check(!sourceActorLedger.note_texture_draw(f,sourceActorModel(models+1)));auto changed=id;++changed.serial;
 check(!sourceActorLedger.note_texture_draw(f,changed));auto changed_frame=f;++changed_frame.primitive_epoch;
 check(!sourceActorLedger.note_texture_draw(changed_frame,id));check(!entries[0].texture_draw);
 check(sourceActorLedger.note_texture_draw(f,id));check(sourceActorLedger.note_texture_draw(f,id));
 check(sourceActorLedger.complete(f,ticket,id));check(!sourceActorLedger.note_texture_draw(f,id));
 sourceActorLedger.retire();check(!sourceActorLedger.texture_draw(f,id));check(!sourceActorLedger.note_texture_draw(f,id));
 // Ready hint is revoked by every current frame/model identity dimension.
 fresh();finish(6);check(sourceActorIdentity(f));id=sourceActorModel(models+1);check(sourceActorLedger.texture_draw(f,id));
 for(unsigned j=0;j<6;++j){auto bad=f;reinterpret_cast<unsigned*>(&bad)[j]++;check(!sourceActorLedger.texture_draw(bad,id));}
 changed=id;++changed.serial;check(!sourceActorLedger.texture_draw(f,changed));
 changed=id;++changed.manager;check(!sourceActorLedger.texture_draw(f,changed));
 // Protect the model itself: a changed ledger must reject before reading its
 // serial. A raw guest-address check alone is not sufficient lifetime proof.
 const auto page=unsigned(sysconf(_SC_PAGESIZE));
 auto* protected_model=static_cast<cModel*>(mmap(nullptr,page,PROT_NONE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0));
 check(protected_model!=MAP_FAILED);
 for(unsigned j=0;j<5;++j){fresh();check(sourceActorIdentity(f));
  sourceActorLedger.retire();check(sourceActorLedger.begin(entries,sizeof entries,1,f));
  ModelIdentity protected_id{reinterpret_cast<std::uintptr_t>(protected_model),1,2};
  check(sourceActorLedger.append(f,protected_id,ModelPath::Source,0));check(sourceActorLedger.seal(f));
  PreparationTicket t{};check(sourceActorLedger.claim(f,t));
  if(j==0)++pG->Frame_cnt;if(j==1)++re4dc_alive_gen[1];if(j==2)++room_generation;
  if(j==3)sourceActorLedger.retire();if(j==4)++sourceActorEpoch;
  sourceActorTextureDraw(protected_model);check(!entries[0].texture_draw);
 }
 fresh();check(sourceActorIdentity(f));PreparationTicket t{};check(sourceActorLedger.claim(f,t));
 sourceActorTextureDraw(protected_model);check(!entries[0].texture_draw); // wrong captured address
 check(munmap(protected_model,page)==0);
 // Lean and ordinary paths reach the same success site; light selection stays
 // after the hint and its source calls/flags remain unmodified.
 fresh();lean_value=FRONT_LEAN_WEIGHTS;finish(2);b=run(true);check(b.count==2&&!g_leanWeights&&lights==1);
 std::printf("draw-qualified texture prep: %u checks PASS\n",checks);
}
'''
    return s

if __name__=='__main__':
    for invis,lean in ((0,0),(1,0),(0,1),(1,1)):
        a.run_harness(f'draw_invis{invis}_lean{lean}',harness(),('-DRE4DC_ACTOR_TEX_PREP_DRAW=1','-DRE4DC_SKIN_PALETTE_LAZY=1',f'-DRE4DC_CROWD_INVIS_SKIP={invis}',f'-DRE4DC_FRONT_LEAN={lean}','-DDRAW_TEST_TARGET_LEAN=1','-fsanitize=address,undefined','-fno-omit-frame-pointer'))
