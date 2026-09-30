"""Exercise the actual optional source-clock fixture parser/scheduler."""
from pathlib import Path
import subprocess,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
class FixtureClock(unittest.TestCase):
 def test_clocks_hold_state_and_timeout(self):
  code=(ROOT/'game/platform/pad.cpp').read_text()
  body=code[code.index('struct PadScriptEntry'):code.index('extern "C" {',code.index('static u16 scriptButtons'))]
  prefix=r'''#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <cstdint>
#include <string>
#include <cstdarg>
#include <cassert>
using u32=uint32_t;using u16=uint16_t;using file_t=int;
#define O_RDONLY 0
static std::string fixture,log_text;static unsigned retrace,source_tick;
extern "C" u32 re4dc_vi_retrace_count(){return retrace;}
extern "C" unsigned re4dc_fixture_source_frame(){return source_tick;}
int fs_open(const char* p,int){return std::strstr(p,"padscript")?1:-1;}
int fs_close(int){return 0;}
long fs_read(int,void* p,unsigned n){n=fixture.size()<n?fixture.size():n;memcpy(p,fixture.data(),n);return n;}
void re4dc_log(const char* f,...){char b[512];va_list ap;va_start(ap,f);vsnprintf(b,sizeof(b),f,ap);va_end(ap);log_text+=b;}
'''
  suffix=r'''
static void reset(const char* text){fixture=text;g_scriptCount=-1;g_scriptActive=-1;g_scriptSourceClock=false;g_lastDelivered=0;g_stateCount=0;memset(g_script,0,sizeof(g_script));log_text.clear();retrace=source_tick=0;}
int main(){
 reset("3 0100 2\n+3 0200 1\n");source_tick=999;retrace=2;assert(!scriptButtons());retrace=3;assert(scriptButtons()==0x100);retrace=4;assert(scriptButtons()==0x100);retrace=5;assert(!scriptButtons());retrace=6;assert(scriptButtons()==0x200);assert(log_text.find("retrace clock")!=std::string::npos);
 reset("clock source \t # CRLF fixture\r\n3 0100 2 title=7 4\r\n+3 0200 1\r\n");retrace=1000;source_tick=2;re4dc_fixture_state("title",7,0);assert(!scriptButtons());source_tick=3;assert(scriptButtons()==0x100);retrace=100000;source_tick=4;assert(scriptButtons()==0x100);source_tick=5;assert(!scriptButtons());source_tick=6;assert(scriptButtons()==0x200);source_tick=7;assert(!scriptButtons());assert(log_text.find("source clock")!=std::string::npos);
 reset("clock source\n3 0100 1 title=7 4\n");retrace=100000;source_tick=3;assert(!scriptButtons());source_tick=6;assert(!scriptButtons());assert(!g_script[0].done);source_tick=7;assert(!scriptButtons());assert(g_script[0].done);assert(log_text.find("dropped")!=std::string::npos);
}
'''
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'test.cpp').write_text(prefix+body+suffix)
   subprocess.run(['g++','-std=c++17','-O2',str(p/'test.cpp'),'-o',str(p/'test')],check=True)
   subprocess.run([str(p/'test')],check=True)
if __name__=='__main__':unittest.main()
