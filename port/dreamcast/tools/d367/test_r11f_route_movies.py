#!/usr/bin/env python3
"""Source-extracted r11f movie lifecycle tests; no game data or target runtime needed."""
from pathlib import Path
import argparse,hashlib,json,subprocess

ROOT=Path(__file__).resolve().parents[4]
parser=argparse.ArgumentParser()
parser.add_argument('--out',type=Path,required=True)
args=parser.parse_args();OUT=args.out
OUT.mkdir(parents=True,exist_ok=False)

def extract(rel,signature):
    text=(ROOT/rel).read_text();start=text.index(signature)
    begin=text.index('{',start);depth=1;end=begin+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]

room='src/st1/r11f.cpp'
bridge='port/dreamcast/game/route_movie_bridge.cpp'
functions=[
 (room,'extern "C" void Evt_R11FS02_Func(Event* e)\n{'),
 (room,'extern "C" void Evt_R11FS10_Func(Event* e)\n{'),
 (room,'extern "C" void Evt_R11FS11_Func(Event* e)\n{'),
 (room,'static void r11fMovieCut(RouteEvtFunc func, unsigned cut)'),
 (room,'static void r11fMovieS02Func(Event* e)'),
 (room,'static void r11fMovieS02Tick(unsigned picture)'),
 (room,'static void r11fMovieS11Func(Event* e)'),
 (room,'static void r11fMovieS11Tick(unsigned picture)'),
 (room,'static bool r11fMovieFailed(unsigned id, int terminal)'),
 (bridge,'static void routeFunc(RouteEvtFunc func, int mode)'),
 (bridge,'int RouteMoviePlay(unsigned id, unsigned flags, RouteEvtFunc func, RouteMovieTick tick)'),
 (room,'static void r11f_Eventxxx()\n{'),
 (room,'static void r11f_EventS11()\n{'),
]

prefix=r'''
#include <algorithm>
#include <cassert>
#include <cstdarg>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <map>
#include <string>
#include <vector>
using u8=uint8_t;using u32=uint32_t;using f32=float;
#define R11F_ROUTE_MOVIES 1
#define G_ROOM_ID 0x11f
#define SCE_LEVEL10 10
#define SCE_PRIO_DEF_2 2
#define ROUTE_SCE_MODE(f) 0
#define BitOn(x,y) ((x)|=(y))
#define BitOff(x,y) ((x)&=~(y))
enum {ROUTE_MOVIE_SND_EVENT=1,ROUTE_MOVIE_KEEP_POSE=2,
 RE4DC_MOVIE_RUNNING=0,RE4DC_MOVIE_EOF=1,RE4DC_MOVIE_SKIP=2,
 RE4DC_MOVIE_ERROR=-1,RE4DC_MOVIE_UNHANDLED=-2};
struct Event;
using RouteEvtFunc=void(*)(Event*);using RouteMovieTick=void(*)(unsigned);
static std::vector<std::string> calls,failures;
static std::map<int,int> smd;
static std::vector<unsigned> pictures;
static int depth,terminal,area_registered,area_reset,area_executed,area_enabled,
 sub_initialized,sub_controlled,fence_calls,followups,post_effects,movie_fire,
 post_fire,fire_resets,model_reads,boss_death,stream_stops,sleeps,effect_wait;
static bool available10,available11,inside_movie,vanish10;
static int reads10;
static void note(const std::string&s){calls.push_back(s);}
struct Vec{float x,y,z;};
struct Global{u32 Room_flg[1],Status_flg[4],Disp_flg,Stop_flg,System_flg,Scenario_flg[1];}global,*pG=&global;
struct cModel{u32 be_flag=0;struct{u32 EnableMask=0;}LightInfo;};
struct cObj:cModel{};
struct cEm:cObj{};
struct cEm2b:cEm{void v50(){++boss_death;note("boss-v50");}}boss;
struct cEmWindow:cEm{void SetEnableFence(int a,int b){assert(a==1&&b==0);++fence_calls;}}window;
struct cPlayer{Vec pos{},ang{};void setPos(Vec*p){pos=*p;note("player-pos");}void setAng(Vec*p){ang=*p;}void zeroPartsPosInit(Vec*p,Vec*a){pos=*p;ang=*a;}}player,*pPL=&player,*pPLS=&player;
struct cEmWrap{int polls=0;int isActive(){return polls++==0;}cEm2b*getPtr(){return &boss;}};
struct R11fWork{cEmWrap em0;cEm*win=&window;}work,*r11f_work=&work;
struct Event{int funcMode=0,NowCut=0,NowFrame=0;int GetMod(void**,const char*,int,int){++model_reads;assert(false&&"baked event model was accessed");return 0;}};
struct EvtManager{
 void EvtReadAram(const char*name,int,int,int,int){note(std::string("preload:")+name);}
 int EvtReadExec(const char*name,int,int){note(std::string("evd:")+name);return 1;}
}EvtMgr;
static void SceEventStart(int){++depth;note("start");}
static void SceEventEnd(int){--depth;assert(depth>=0);note("end");}
static void SndEventInit(){note("snd-begin");}
static void SndEventEnd(){note("snd-end");}
static void SceSleep(int n){assert(n==1);++sleeps;}
static void SndRoomStrStop(int n){assert(n==2);++stream_stops;note("stream-stop");}
static void r11f_EventS11();
static void r11f_AshleyRunUp(){}
static void SceAtDataSet_exec(int id,int,int,void(*fn)(),int,int){assert(id==0x80&&fn==r11f_EventS11);++area_registered;note("area-register");}
static void SceAtDataReset(int id){assert(id==0x80);++area_reset;}
static void SceAtSetEnable(int id,int on){assert(id==8&&on==1);++area_enabled;note("area-enable");}
static void SceAtExecute(int id){assert(id==0x80);++area_executed;}
static void SmdSetTrans(int id,int on){smd[id]=on;note("smd:"+std::to_string(id)+":"+std::to_string(on));}
static void Obj18CmfOn(cObj*,u32){assert(false);}
static void EffectEspDelete(int family,int no,int,int){if(family==0x2001){assert(no==3);++fire_resets;}else{assert(family==0x801&&no==2);++post_effects;}}
static void EffectEspgenDelete(int family,int no,int){assert((family==0x2001&&no==3)||(family==0x801&&no==2));}
static void EffectEfmDelete(int family,int no,int){assert((family==0x2001&&no==3)||(family==0x801&&no==2));}
static void EstSet(int,int,int,int,int,int id,int family,int,int,int){if(id==7&&family==1){if(inside_movie)++movie_fire;else ++post_fire;}else if(id==5&&family==1){++post_effects;}else assert(family==0x2001&&(id==0||id==4));}
static void EspGenSetMoveLoop(int n){assert(n==200);}
static int EffGetAreaState(int n){assert(n==0);return effect_wait++==0;}
static void SubCharInit(int n,Vec*p,float a){assert(n==1&&p->x==44154.0f&&a==2.987f);++sub_initialized;}
static void SubCharCtrl(int,int){++sub_controlled;}
static void SceExec(int,void(*f)(),int,int,int,int){assert(f==r11f_AshleyRunUp);++followups;note("ashley-followup");}
struct Camera{void AreaOnOff(int,int,int){}void UnsetAreaAttr(int,int,int){}void SetAreaAttr(int,int,int){}}CamCtrl;
static void re4dc_weapon_heap4_movie_restore(){}
static void re4dc_ps2_interior_movie_restore(){}
extern "C" void re4dc_log(const char*fmt,...){char buf[512];va_list ap;va_start(ap,fmt);vsnprintf(buf,sizeof(buf),fmt,ap);va_end(ap);if(strstr(buf,"progression=blocked"))failures.push_back(buf);}
static bool re4dc_movie_available(unsigned id){
 if(id==0x11f10){++reads10;return available10&&!(vanish10&&reads10>=2);}
 if(id==0x11f11)return available11;
 assert(id==0x11f02);return true;
}
static int re4dc_movie_play(unsigned id,unsigned mask,RouteMovieTick tick){
 assert(mask==0x1000);note("movie:"+std::to_string(id));inside_movie=true;
 for(unsigned p:pictures)if(tick)tick(p);
 inside_movie=false;return terminal;
}
static bool r11fMovieS02Fire;
static unsigned r11fMovieS11NextCut;
'''

tests=r'''
static int count(const std::string&s){return std::count(calls.begin(),calls.end(),s);}
static size_t at(const std::string&s){auto p=std::find(calls.begin(),calls.end(),s);assert(p!=calls.end());return p-calls.begin();}
static void reset(){
 calls.clear();failures.clear();smd.clear();pictures={0,109,110,190,191,320};
 depth=area_registered=area_reset=area_executed=area_enabled=sub_initialized=sub_controlled=fence_calls=followups=post_effects=movie_fire=post_fire=fire_resets=model_reads=boss_death=stream_stops=sleeps=effect_wait=reads10=0;
 terminal=RE4DC_MOVIE_EOF;available10=available11=true;inside_movie=vanish10=false;
 global={};global.Disp_flg=0x12345678;player={};work={};
}
static void no_escape_aftermath(){assert(area_enabled==0&&area_executed==0&&post_fire==0&&post_effects==0&&sub_initialized==0&&sub_controlled==0&&fence_calls==0&&followups==0);assert(!(pG->Room_flg[0]&0x40000000));assert(player.pos.x==0);}
static void escape_aftermath(){assert(area_reset==1&&area_enabled==1&&area_executed==1&&post_fire==1&&sub_initialized==1&&sub_controlled==1&&fence_calls==1&&followups==1);assert(pG->Room_flg[0]&0x40000000);assert(player.pos.x==35332.0f&&player.pos.y==-8000.0f&&player.pos.z==-60179.0f&&player.ang.y==1.33f);assert(depth==0&&model_reads==0);}
int main(){
 int cases=0;
 // Each media availability controls only its own preload and exec fallback.
 for(bool a:{false,true})for(bool b:{false,true}){
  reset();available10=a;available11=b;r11f_Eventxxx();
  assert(count("preload:event/evd/r11fs10.evd")==!a&&count("preload:event/evd/r11fs11.evd")==!b);
  assert(count("evd:event/evd/r11fs10.evd")==!a);assert(area_registered==1&&depth==0&&boss_death==1&&stream_stops==1&&sleeps==1&&model_reads==0);
  assert(at("boss-v50")<at("stream-stop")&&at("stream-stop")<at("area-register"));++cases;
 }
 // Untouched UNHANDLED after a positive preload probe can still use source EVD.
 reset();vanish10=true;r11f_Eventxxx();assert(count("preload:event/evd/r11fs10.evd")==0&&count("evd:event/evd/r11fs10.evd")==1&&area_registered==1&&failures.empty());++cases;
 for(int end:{RE4DC_MOVIE_EOF,RE4DC_MOVIE_SKIP}){
  reset();terminal=end;r11f_Eventxxx();assert(area_registered==1&&depth==0&&failures.empty()&&model_reads==0);++cases;
 }
 for(int end:{RE4DC_MOVIE_ERROR,RE4DC_MOVIE_UNHANDLED}){
  // A started native player returning UNHANDLED is promoted to ERROR by the real bridge.
  reset();terminal=end;pictures.clear();r11f_Eventxxx();assert(area_registered==0&&depth==0&&failures.size()==1&&count("evd:event/evd/r11fs10.evd")==0);assert(failures[0].find("room=11f id=11f10 terminal=-1")!=std::string::npos);++cases;
 }
 // Natural playback, duplicates, and all cut-start pictures dropped give the same lasting callbacks.
 for(const std::vector<unsigned>&p:{std::vector<unsigned>{0,109,110,190,191,320},std::vector<unsigned>{0,0,111,192,192,320},std::vector<unsigned>{320}}){
  reset();pictures=p;r11f_EventS11();escape_aftermath();assert(movie_fire==1&&smd[14]==0&&smd[20]==0&&smd[21]==1&&smd[22]==1);assert(count("smd:14:1")==2&&count("smd:14:0")==1);assert(failures.empty());++cases;
 }
 // Repeated invocation resets cut delivery; previous playback cannot suppress a new cut.
 reset();pictures={320};r11f_EventS11();r11f_EventS11();assert(movie_fire==2&&count("smd:14:1")==4&&count("smd:14:0")==2&&depth==0);++cases;
 // Real skip before picture0, before cut2, and after cut2: cancel only restores, never catches up.
 for(const std::vector<unsigned>&p:{std::vector<unsigned>{},std::vector<unsigned>{0,110},std::vector<unsigned>{191}}){
  reset();terminal=RE4DC_MOVIE_SKIP;pictures=p;r11f_EventS11();escape_aftermath();assert(movie_fire==(p==std::vector<unsigned>{191}));assert(smd[14]==1&&smd[20]==0&&smd[21]==1&&smd[22]==1&&failures.empty());++cases;
 }
 // Errors before the first picture and after cut2 preserve delivered effects, but no escape aftermath.
 for(const std::vector<unsigned>&p:{std::vector<unsigned>{},std::vector<unsigned>{191}}){
  reset();terminal=RE4DC_MOVIE_ERROR;pictures=p;r11f_EventS11();no_escape_aftermath();assert(area_reset==1&&depth==0&&failures.size()==1&&count("evd:event/evd/r11fs11.evd")==0);assert(failures[0].find("room=11f id=11f11 terminal=-1")!=std::string::npos);assert(movie_fire==!p.empty());if(!p.empty())assert(smd[14]==0&&smd[21]==1);else assert(smd.empty());++cases;
 }
 reset();available11=false;r11f_EventS11();escape_aftermath();assert(count("evd:event/evd/r11fs11.evd")==1&&movie_fire==0&&failures.empty());++cases;
 // S02's separate crossed585 correction: no event-model calls and no missed-cut synthesis on skip.
 for(const std::vector<unsigned>&p:{std::vector<unsigned>{584,585,586},std::vector<unsigned>{584,600,600},std::vector<unsigned>{1066}}){
  reset();pictures=p;RouteMoviePlay(0x11f02,ROUTE_MOVIE_SND_EVENT,r11fMovieS02Func,r11fMovieS02Tick);assert(fire_resets==1&&model_reads==0&&depth==0);++cases;
 }
 reset();pictures={600};RouteMoviePlay(0x11f02,ROUTE_MOVIE_SND_EVENT,r11fMovieS02Func,r11fMovieS02Tick);pictures={0,584};terminal=RE4DC_MOVIE_SKIP;RouteMoviePlay(0x11f02,ROUTE_MOVIE_SND_EVENT,r11fMovieS02Func,r11fMovieS02Tick);assert(fire_resets==1&&model_reads==0&&depth==0);++cases;
 printf("PASS %d extracted-source cases: independent availability, untouched fallback, natural/drop/repeat, skip before/after cuts, partial errors, source aftermath, S02 crossed585\n",cases);
}
'''

body='\n\n'.join(extract(p,s) for p,s in functions)
cpp=OUT/'source-extracted.cpp';cpp.write_text(prefix+'\n'+body+'\n'+tests)
command=['g++','-std=c++17','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(cpp),'-o',str(OUT/'source-extracted')]
compiled=subprocess.run(command,text=True,capture_output=True)
(OUT/'compile.log').write_text(compiled.stdout+compiled.stderr)
assert compiled.returncode==0,compiled.stderr
run=subprocess.run([str(OUT/'source-extracted')],text=True,capture_output=True)
(OUT/'run.log').write_text(run.stdout+run.stderr)
assert run.returncode==0,run.stdout+run.stderr
report={'status':'PASS','command':command,'output':run.stdout,'functions':[{'path':p,'signature':s,'sha256':hashlib.sha256(extract(p,s).encode()).hexdigest()}for p,s in functions],
 'scope':'Actual extracted source callbacks, room control flow and RouteMoviePlay bridge with host mocks at external effects and native player boundaries. No copied source implementation, native runtime, media decode timing or physical hardware claim.'}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(run.stdout.strip())
