
alignas(16) static u8 source_pool[2048*0x150],source_copy[sizeof(source_pool)];
static Parent parent;static cModel model={41,2};
static EspgenWork gens[4],gen_copy[4];static Ps2fxGeneratorClock clocks[4],clock_copy[4];
static Anm puzzle_anm={0,0,96,96,1};static unsigned cases;
static cPs2fxEsp0a* particle(unsigned n){return reinterpret_cast<cPs2fxEsp0a*>(source_pool+n*0x150);}
static cPs2fxEsp0a* add(unsigned color,unsigned rank,bool child=false){
 auto* e=new(source_pool+sys.nEsp++*0x150)cPs2fxEsp0a{};
 e->info={unsigned(100+color),123,0x4001,2,1};e->m_Be_flg=1;e->m_Id=(color==1||child)?0:0x0a;
 e->m_Tex_id=0xff;e->m_Release_time=0xff;e->m_Size_base_x=e->m_Size_base_y=470;
 e->m_Col_start_a=130;e->m_Del_far=200;e->m_Del_near=50;e->m_Blend_type=1;
 e->m_Col_start_r=color==0?50:0;e->m_Col_start_g=color==1?50:0;e->m_Col_start_b=color==2?50:0;
 e->parent=&parent;e->m_pMod=&model;e->m_Guid_pMod=model.serial;e->m_Tool_flg=color==1?0x8000:0x8400;
 e->m_Life_max=child?1:0;e->m_Size_mul=1;e->m_Pos={kPuzzleX[color],kPuzzleY[color],color==1?-250.0f*rank:0};
 e->m_Speed={0,0,(color==1||child)?0.0f:-250.0f};e->type=1;e->base_alpha=130;return e;
}
static void setup(unsigned room=0x117){
 std::memset(source_pool,0,sizeof(source_pool));sys.nEsp=0;sys.pEspBuf=source_pool;g_pEspSys=&sys;pG=&globals;
 ++globals.Frame_cnt;++fake_generation;G_ROOM_ID=room;re4dc_ps2fx=PS2FX_HAZE|PS2FX_STREAK;
 globals.Status_flg[1]=globals.Status_flg[3]=globals.Stop_flg=0;model.be_flag=2;
 globals.Cam.param.pos={0,0,0};globals.Cam.param.at={0,0,-1};globals.Cam.up={0,1,0};
 std::memset(globals.Cam.v_mat,0,sizeof(Mtx));std::memset(globals.Cam.ProjMat,0,sizeof(Mtx44));std::memset(parent.mat,0,sizeof(Mtx));
 for(unsigned i=0;i<3;++i){globals.Cam.v_mat[i][i]=1;parent.mat[i][i]=1;}parent.mat[2][3]=-3000;
 globals.Cam.ProjMat[0][0]=globals.Cam.ProjMat[1][1]=1;globals.Cam.ProjMat[2][2]=-.00005f;globals.Cam.ProjMat[2][3]=-1;
 for(unsigned id:{0x13U,0x1fU}){auto& tw=sys.Esp_tex_tbl[id];tw={};tw.pTpl=&tpl;tw.pAnm=id==0x13?&puzzle_anm:&anm;tw.mtx[0][0]=tw.mtx[1][1]=1;}
 EspgenArray=gens;nEspgen=4;seq.num=4;
 for(unsigned i=0;i<4;++i){clocks[i]={refs+i,nullptr,1,15,(u16)(i%2?130:110)};gens[i]={1,2,{101,123,0x4001,2,1},clocks+i};}
 for(auto& e:observed)e=nullptr;
 if(room==0x117){add(0,0);for(unsigned i=0;i<50;++i){auto* e=add(1,i);if(!i)observed[1]=e;}add(2,0);observed[0]=add(0,0,true);observed[2]=add(2,0,true);}
 phase_step=phase_begin=phase_coarse=phase_batch=phase_clear=phase_effect=0;phase_ready=false;phase_finished=true;
 fake_queued=0;fake_fail_call=0;fake_submit=fake_resident=fake_area=true;
 re4dc_pace_skipping=re4dc_esp_logic_queued=0;re4dc_coarse_image=1;
}
static void prepare(){
 const unsigned calls=fake_batch_calls,populations=population_builds;const auto old=s_fx_addition;
 std::memcpy(source_copy,source_pool,sizeof(source_pool));std::memcpy(gen_copy,gens,sizeof(gens));std::memcpy(clock_copy,clocks,sizeof(clocks));
 re4dc_esp_sprite_pass_begin();assert(s_stage1_pending.pending&&!s_puzzle_active);
 assert(fake_batch_calls==calls&&population_builds==populations+1&&s_vis_far==8000);
 assert(!std::memcmp(&old,&s_fx_addition,sizeof(old))&&!std::memcmp(source_copy,source_pool,sizeof(source_pool)));
}
static void draw(){Render_before();Render();assert(!s_stage1_pending.pending);
 assert(!std::memcmp(source_copy,source_pool,sizeof(source_pool))&&!std::memcmp(gen_copy,gens,sizeof(gens))&&!std::memcmp(clock_copy,clocks,sizeof(clocks)));}
static void refused(){const unsigned calls=fake_batch_calls;const auto old=s_fx_addition;draw();
 assert(fake_batch_calls==calls&&!s_puzzle_active&&!std::memcmp(&old,&s_fx_addition,sizeof(old)));++cases;}
int main(){
 setup();prepare();const unsigned before=fake_batch_calls,fall=fallback_callbacks,supp=suppressed_callbacks;draw();
 assert(fake_batch_calls==before+3&&s_puzzle_active==3&&fake_queued==54&&suppressed_callbacks==supp+2&&fallback_callbacks==fall+1);
 assert(phase_begin<phase_coarse&&phase_coarse<phase_batch&&phase_batch<phase_clear&&phase_clear<phase_effect);++cases;
 assert(Ps2fxPuzzleSuppress(observed[0])&&Ps2fxPuzzleSuppress(observed[1])&&!Ps2fxPuzzleSuppress(observed[2]));
 re4dc_ps2_fx_stage1_render(1,0);assert(fake_batch_calls==before+3&&s_puzzle_active==3);++cases;
 ++globals.Frame_cnt;assert(!Ps2fxPuzzleSuppress(observed[0]));re4dc_ps2_fx_stage1_render(1,0);assert(fake_batch_calls==before+3);++cases;
 setup();prepare();++globals.Frame_cnt;refused();setup();prepare();--globals.Frame_cnt;refused();
 setup();prepare();++G_ROOM_ID;refused();setup();prepare();sys.pEspBuf=source_pool+0x150;refused();
 setup();prepare();--sys.nEsp;refused();setup();prepare();++sys.nEsp;refused();
 setup();prepare();++fake_generation;refused();setup();prepare();fake_resident=false;refused();
 setup();prepare();EspgenArray=gens+1;refused();setup();prepare();--nEspgen;refused();
 setup();prepare();re4dc_coarse_image=0;refused();
 setup();prepare();re4dc_pace_skipping=1;refused();assert(!phase_effect);re4dc_pace_skipping=0;re4dc_coarse_image=1;refused();
 setup();prepare();re4dc_pace_skipping=1;re4dc_esp_logic_queued=1;refused();assert(phase_effect);
 setup();prepare();fake_submit=false;draw();assert(!s_puzzle_active&&!fake_queued);++cases;
 setup();prepare();fake_fail_call=fake_batch_calls+2;draw();assert(s_puzzle_active==5&&fake_queued==54);++cases;
 // Empty/cull-only colours commit only through the batch gate.
 setup();model.be_flag=0;prepare();draw();assert(s_puzzle_active==7&&!fake_queued);++cases;
 setup();model.be_flag=0;prepare();fake_submit=false;draw();assert(!s_puzzle_active&&!fake_queued);++cases;
 // Exact complete source group certificates, including green ranks32..49.
 setup();particle(50)->m_Pos.z+=1;prepare();draw();assert(s_puzzle_active==5);++cases;
 setup();particle(50)->m_Pos.z=particle(49)->m_Pos.z;prepare();draw();assert(s_puzzle_active==5);++cases;
 setup();particle(50)->info.Call_no++;prepare();draw();assert(s_puzzle_active==5);++cases;
 setup();particle(0)->m_Guid_pMod++;prepare();draw();assert(s_puzzle_active==6);++cases;
 setup();sys.Esp_tex_tbl[0x13].Owner=0xd2;prepare();draw();assert(!s_puzzle_active);++cases;
 // Preparation clears acceptance even in invalid/no-ticket configurations.
 setup();prepare();draw();const auto old=s_fx_addition;re4dc_esp_sprite_pass_begin();assert(!s_puzzle_active&&!std::memcmp(&old,&s_fx_addition,sizeof(old)));++cases;
 fake_generation=0;re4dc_esp_sprite_pass_begin();assert(!s_stage1_pending.pending);++fake_generation;++cases;
 sys.nEsp=2049;re4dc_esp_sprite_pass_begin();assert(!s_stage1_pending.pending);++cases;
 setup();nEspgen=513;re4dc_esp_sprite_pass_begin();assert(!s_stage1_pending.pending);++cases;
 setup();EspgenArray=nullptr;re4dc_esp_sprite_pass_begin();assert(!s_stage1_pending.pending);++cases;
 setup();g_pEspSys=nullptr;re4dc_esp_sprite_pass_begin();assert(!s_stage1_pending.pending);g_pEspSys=&sys;++cases;
 // Addition private sampling happens once in Render, with immutable sources.
 for(unsigned room:{0x118U,0x11cU}){setup(room);prepare();const unsigned calls=fake_batch_calls;draw();assert(fake_batch_calls==calls+1&&s_fx_addition.age==(room==0x118?1U:8U));
 const auto sampled=s_fx_addition;re4dc_ps2_fx_stage1_render(1,0);assert(fake_batch_calls==calls+1&&!std::memcmp(&sampled,&s_fx_addition,sizeof(sampled)));++cases;}
 // A same-age r11c controller frame cannot advance the private clock.
 setup(0x11c);prepare();draw();const auto sampled=s_fx_addition;++globals.Frame_cnt;re4dc_coarse_image=1;fake_queued=0;prepare();draw();assert(!std::memcmp(&sampled.particles,&s_fx_addition.particles,sizeof(sampled.particles))&&s_fx_addition.age==8);++cases;
 std::printf("PASS actual stage1 phase: %u cases; same-frame Render order, one-use tickets, generation/pool/generator refusal, immutable source, exact puzzle groups, per-colour atomic acceptance, private clocks only in Render\n",cases);
}
