"""Actual r100 callers retain gameplay around the two deferred presentations.

This host fixture proves boundary/state behavior, not manual gameplay or an
identical cancel-frame RNG sequence. Private EVD identities are qualified by
the existing certificate transport, separately exercised in test_event_file.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


def function(text, signature):
    begin = text.index(signature + "\n{")
    brace = text.index("{", begin)
    end, depth = brace + 1, 1
    while depth:
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[begin:end]


@unittest.skipUnless(shutil.which("g++"), "host C++ compiler required")
class R100Completion(unittest.TestCase):
    def test_source_callers_and_scope(self):
        source = (ROOT / "src/st1/r100.cpp").read_text()
        code = r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <initializer_list>
using u32=uintptr_t;
struct Vec { float x=0,y=0,z=0; };
struct Rejected {};
int resets, matrices, sounds_started, sounds_ended, frees, reads, swaps;
int qualified, starts, ends, nest, sleeps, spawns, car_moves, traps, open_term;
bool valid_reference=true, immutable=true; int busy_event_ticks=0;
u32 last_bytes,last_crc;
struct cCoord { void matUpdate(){++matrices;} };
struct cEm : cCoord {
    Vec pos,ang; u32 flag=0; int hp=500; bool suspended=false;
    void setPos(Vec* p){pos=*p;} void setAng(Vec* p){ang=*p;}
    void setNoSuspend(int v){suspended=v;}
    int checkStatus(int){return 0;}
    void zeroPartsPosInit(Vec* p,Vec* a){pos=*p;ang=*a;++resets;}
};
using cPlayer=cEm;
cEm enemy,enemy_error,ambush[7]; cEm* errEm=&enemy_error; cEm* pSubEm=nullptr;
cPlayer player; cPlayer* pPL=&player;
struct Global {
    u32 room_id=0x100,pl_type=0,game_costume=0,pl_costume=0,weapon_no=2,weapon_type=0;
    u32 System_flg=0,Status_flg[4]{},Item_find_flg=0;
} global,*pG=&global;
struct Unit { void* m_addr=(void*)0x1000; u32 m_size=1341504; } units[10];
struct Work { cEm* em; cEm* ems[7]; Unit* evt[10]; } work,*W=&work;
struct Event { u32 StatusFlag=0; } event;
struct EventManager {
    char NowExeEvtName[48]{}; u32 NowExeEvtKey=0;
    int SetEvt(void*,u32* out){if(out)*reinterpret_cast<Event**>(out)=&event;return 1;}
    int IsAliveEvt(void*,int,int){return 0;}
} EvtMgr;
const char* r100_evtName[10]={"evd/r100s03.evd","","","evd/r100s20.evd"};
struct Logger { void err(int,int,const char*,...){} } logger,*pLog=&logger;
struct DataController { int sort=1; void setAramSort(int n){sort=n;} } DC;
struct EmListData { int set=9; } lists[128];
using TaskFunc=void(*)();
constexpr int EM_STATUS_ACTIVE=1,SCE_LEVEL10=10,G_ROOM_ID=0x100;
u32 rsf=0;bool areas[64]{};int messages=0;
#define BitOn(v,b) ((v)|=(b))
#define BitOff(v,b) ((v)&=~u32(b))
#define EM_LIST(n) (&lists[n])
void SceEventStart(int){++starts;++nest;}
void SceEventEnd(int){++ends;--nest;}
void SceSleep(int n){sleeps+=n;}
int SceCheckEventStart(){
 if(busy_event_ticks){assert(!qualified);--busy_event_ticks;return 0;}
 EvtMgr.NowExeEvtName[0]=0;return 1;
}
void SceAtSetEnable(int n,int v){areas[n]=v;}
void RsfSet(int r,int b){assert(r==0x100);rsf|=1u<<b;}
void SndRoomStrStop(int){}
void SndEventInit(){++sounds_started;}
void SndEventEnd(){++sounds_ended;}
void r100_em_set(){++spawns;}
void r100_Car_pos_move(){++car_moves;}
void r100_trap_set(){++traps;}
void r100_MesGanado(){}
void r100_GakeEvent(){}
void r100_MesBrige(){}
int SceAtCreateExecAt(cEm*,Vec*,int,int,int,float,int,float,float,int,int,TaskFunc,int,int){++messages;return 0;}
void SceAtDataSet_exec(int,int,int,TaskFunc,int,int){}
void SetSstDispFlag(int,int){}
void OpeSetOpenTerm(int,float,float,float,float){++open_term;}
int readEvent(int,int wait,void** out){++reads;if(wait){++swaps;if(out)*out=&event;}return 1;}
void freeEvent(int no,int swap){assert(no==0||no==3);++frees;if(swap)++swaps;}
int re4dc_event_file_reference(const char*,unsigned bytes,unsigned crc){++qualified;last_bytes=bytes;last_crc=crc;return valid_reference;}
int re4dc_event_file_range(u32,u32){return immutable;}
void re4dc_log(const char*,...){}
void re4dc_missing(const char*){throw Rejected{};}
void reset(){
 global=Global{};player=cPlayer{};enemy=cEm{};work=Work{};EvtMgr=EventManager{};
 pPL=&player;pSubEm=nullptr;W->em=&enemy;
 for(int i=0;i<7;++i){ambush[i]=cEm{};W->ems[i]=&ambush[i];}
 for(int i=0;i<10;++i){units[i]=Unit{};W->evt[i]=&units[i];}
 units[3].m_size=689632;
 for(auto& l:lists)l=EmListData{};
 resets=matrices=sounds_started=sounds_ended=frees=reads=swaps=0;
 qualified=starts=ends=nest=sleeps=spawns=car_moves=traps=open_term=messages=0;
 valid_reference=immutable=true;busy_event_ticks=0;rsf=0;DC.sort=1;event.StatusFlag=0;
 memset(areas,0,sizeof areas);player.pos={5,6,7};player.ang={0,.5f,0};
}
'''
        names = ["static bool r100DeferredPresentation(int no)",
                 "static void r100EndDeferredPresentation(int no)",
                 "static void r100_Sce_look()",
                 "static void r100_Sce_zombi_dead(cEm* em)"]
        code += "\n".join(function(source, n) for n in names)
        code += r'''
int main(){
 for(int cycle=0;cycle<3;++cycle){
  reset();r100_Sce_look();
  assert(starts==1&&ends==1&&nest==0&&sleeps==5);
  assert((rsf&(1u<<3))&&!areas[10]&&enemy.flag==1&&enemy.hp==500);
  assert(enemy.pos.x==-79116&&enemy.pos.y==860&&enemy.pos.z==-38890&&enemy.ang.y==-1.39f);
  assert(player.pos.x==-82910&&player.pos.y==860&&player.pos.z==-38480&&player.ang.y==1.75f);
#if RE4DC_R100_DEFER_EVENTS
  assert(qualified==1&&last_bytes==1341504&&last_crc==0xf14c8dddu);
  assert(resets==1&&sounds_started==1&&sounds_ended==1&&frees==1&&!reads&&!swaps);
  assert(global.System_flg==0x40);
#else
  assert(!qualified&&reads==1&&swaps==2&&resets==0&&global.System_flg==0);
#endif
  reset();r100_Sce_zombi_dead(&enemy);
  assert(starts==1&&ends==1&&nest==0&&sleeps==1&&spawns==1&&car_moves==1&&traps==1);
  assert((rsf&(1u<<10))&&global.Item_find_flg==0x4000&&DC.sort==1&&messages==1&&open_term==1);
  assert(ambush[1].flag==1&&ambush[2].flag==1&&!ambush[0].suspended&&!ambush[1].suspended&&!ambush[2].suspended);
  assert(lists[4].set==0&&lists[5].set==0&&areas[1]&&areas[0x1c]&&!areas[0xc]&&!areas[0x19]&&!areas[0x1a]&&!areas[0x1e]);
  assert(player.pos.x==5&&player.pos.y==6&&player.pos.z==7&&player.ang.y==.5f&&resets==0);
#if RE4DC_R100_DEFER_EVENTS
  assert(qualified==1&&last_bytes==689632&&last_crc==0x4a3b7ce9u);
  assert(reads==1&&!swaps&&frees==1&&sounds_started==1&&sounds_ended==1&&global.System_flg==0x40);
#else
  assert(!qualified&&reads==2&&swaps==2&&event.StatusFlag==0x800);
#endif
 }
#if RE4DC_R100_DEFER_EVENTS
 for(int f=0;f<10;++f){
  reset();
  if(f==0)valid_reference=false;if(f==1)W->em=nullptr;if(f==2)W->em=errEm;
  if(f==3)pSubEm=&enemy;if(f==4)strcpy(EvtMgr.NowExeEvtName,"other");
  if(f==5)global.Status_flg[2]=0x10000;if(f==6)immutable=false;
  if(f==7)global.pl_costume=1;if(f==8)global.weapon_no=9;if(f==9)pPL=nullptr;
  bool rejected=false;try{r100_Sce_look();}catch(Rejected){rejected=true;}
  assert(rejected&&!starts&&!ends&&!rsf&&!frees&&!reads&&!swaps&&!resets&&!sounds_ended);
 }
 reset();busy_event_ticks=2;strcpy(EvtMgr.NowExeEvtName,"finishing");
 r100_Sce_zombi_dead(&enemy);
 assert(!busy_event_ticks&&qualified==1&&starts==1&&ends==1&&sleeps==3);
 reset();assert(!r100DeferredPresentation(4)&&!qualified);global.room_id=0x101;
 assert(!r100DeferredPresentation(0)&&!qualified);global.room_id=0x100;global.game_costume=1;
 assert(!r100DeferredPresentation(0)&&!qualified);
#endif
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "test.cpp").write_text(code)
            for enabled in (0, 1):
                exe = path / ("test" + str(enabled))
                subprocess.run(["g++", "-std=c++17", "-DRE4DC_GAME",
                                "-DRE4DC_R100_DEFER_EVENTS=" + str(enabled),
                                "-fno-pie", "-no-pie", "-fsanitize=address,undefined",
                                str(path / "test.cpp"), "-o", str(exe)], check=True)
                subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    unittest.main()
