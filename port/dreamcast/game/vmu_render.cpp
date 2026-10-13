// Pure logical framebuffer: no game globals, allocations, clocks, RNG or I/O.
#include "vmu_context.h"
#include "vmu_assets/re4_vmu_assets.h"
#include <stdint.h>
#include "vmu_assets/re4_vmu_leon_packed.inc"   // tools/pack_vmu_leon.py: the growth region of re4_vmu_leon.h
#include "vmu_assets/font.inc"
// VMU_LUIS (vmu_context.mk): Luis's portraits only when his module (pl14) is linked; host tests keep them.
#ifndef RE4DC_VMU_LUIS
#define RE4DC_VMU_LUIS 1
#endif
#if RE4DC_VMU_LUIS
#include "vmu_assets/luis.inc"
#endif
#include <string.h>

namespace re4vmu {
namespace {
struct Canvas {
    uint8_t* data;
    void dot(int x,int y,bool ink=true) {
        if (x<0 || x>=48 || y<0 || y>=32) return;
        const unsigned bit=0x80u>>(x&7), p=y*6+x/8;
        if(ink) data[p]|=bit; else data[p]&=~bit;
    }
    void rect(int x,int y,int w,int h,bool ink=true) {
        for(int j=y;j<y+h;++j) for(int i=x;i<x+w;++i) dot(i,j,ink);
    }
    void line(int x,int y,int x1,int y1) {
        int dx=x1>x?x1-x:x-x1, sx=x<x1?1:-1;
        int dy=y1>y?y-y1:y1-y, sy=y<y1?1:-1, err=dx+dy;
        for(;;) { dot(x,y); if(x==x1&&y==y1) break; int e=2*err;
            if(e>=dy){err+=dy;x+=sx;} if(e<=dx){err+=dx;y+=sy;}
        }
    }
    void text(const char* str,int x,int y) {
        for(;*str;++str){ const FontGlyph* g=nullptr;
            for(unsigned i=0;i<sizeof(kFont)/sizeof(kFont[0]);++i)
                if(kFont[i].ch==*str){g=&kFont[i];break;}
            if(!g){x+=3;continue;}
            for(int yy=0;yy<5;++yy) for(int xx=0;xx<g->width;++xx)
                if(g->rows[yy]&(1u<<(g->width-1-xx))) dot(x+xx,y+yy);
            x+=g->width+1;
        }
    }
};
const char* condition(Condition c) {
    static const char* const t[]={"FINE","CAUT","DNGR","DEAD"};
    return t[(unsigned)c<4?c:Dead];
}
void strip(Canvas& c,const View& v) {
    c.rect(0,27,48,5,false); c.text(v.owner==Ashley?"A":"L",1,27);
    c.rect(6,28,20,3); c.rect(7,29,18,1,false);
    unsigned filled=0;
    if(v.hp>0&&v.max_hp>0) {
        unsigned hp=v.hp>v.max_hp?v.max_hp:v.hp;
        filled=(18u*hp+unsigned(v.max_hp)/2)/unsigned(v.max_hp);
        if(!filled) filled=1;
    }
    c.rect(7,29,filled,1);c.text(condition(v.condition),30,27);
}
void number(Canvas& c,unsigned n) {
    char digits[11]; unsigned count=0;
    do { digits[count++]=char('0'+n%10);n/=10;}while(n&&count<10);
    // Snapshot ammo is a u16. Preserve all five digits in the 20px header region.
    if(count<2)digits[count++]='0';
    char out[11];for(unsigned i=0;i<count;++i)out[i]=digits[count-1-i];out[count]=0;
    c.text(out,47-int(count)*4,1);
}
}

View resolve(const Snapshot& s) {
    View v={};v.mode=Blank;
    if(!s.valid || (s.player!=Leon&&s.player!=Ashley))return v;
    v.owner=s.player;v.subject=s.player;v.hp=s.hp;v.max_hp=s.max_hp;
    v.condition=s.hp<=0?Dead:s.condition;v.ammo_kind=s.ammo_kind;
    v.ammo=s.ammo;v.infection=s.infection<4?s.infection:0;
    v.mode=s.player==Ashley?Companion:Vitals;v.status=s.player==Ashley?Play:Health;
    if(v.condition>=Danger){v.urgent=true;v.status=Health;return v;}
    if(s.companion==Ashley&&s.companion_help){
        v.mode=Companion;v.subject=Ashley;v.status=Help;v.urgent=true;return v;
    }
    if(s.call){v.mode=Call;return v;}
    if(s.player==Leon && (s.companion==Ashley||s.companion==Luis)){
        v.mode=Companion;v.subject=s.companion;
        v.status=s.companion==Luis?Ally:(s.companion_condition&2?Wait:Follow);
    }
    return v;
}

void render(const View& v,const Phase& p,uint8_t out[192]) {
    memset(out,0,192);Canvas c={out};if(v.mode==Blank)return;
    if(v.mode==Vitals){
        c.text("LEON",1,1);
        if(v.ammo_kind==Finite){
            if(v.ammo<100){c.dot(32,1);c.rect(31,2,3,3);} number(c,v.ammo);
        } else if(v.ammo_kind==Infinite)c.text("INF",36,1);
        static const int a[][2]={{1,16},{8,16},{10,13},{12,21},{15,9},{18,21},{20,16},{27,16},{29,14},{31,16},{34,16}};
        static const int b[][2]={{1,16},{7,16},{9,14},{11,16},{12,16},{13,12},{15,21},{18,9},{21,21},{23,16},{28,16},{30,14},{32,16},{34,16}};
        if(v.hp<=0)c.line(1,16,34,16);
        else if(p.beat&1){for(unsigned i=1;i<sizeof(b)/sizeof(b[0]);++i)c.line(b[i-1][0],b[i-1][1],b[i][0],b[i][1]);}
        else {for(unsigned i=1;i<sizeof(a)/sizeof(a[0]);++i)c.line(a[i-1][0],a[i-1][1],a[i][0],a[i][1]);}
        unsigned stage=v.infection<4?v.infection:0, from=p.from_stage<4?p.from_stage:stage;
        for(int y=7;y<=25;++y)for(int x=30;x<48;++x){
            // Preview rank ((47-x)+(25-y)*.65)/28.7, represented exactly as integers.
            int rank=20*(47-x)+13*(25-y);if(stage<from)rank=574-rank;
            unsigned pick=p.reveal>=1000 || rank*1000<=int(p.reveal)*574?stage:from;
            if(pick&&RE4_VMU_LEON_GROWTH_PACKED[pick-1][y-7][x/8-3]&(0x80>>(x&7)))c.dot(x,y);
        }
    } else if(v.mode==Call) {
        memcpy(out,p.alternate?RE4_VMU_HUNNIGAN_SPEAKING:RE4_VMU_HUNNIGAN,162);
    } else {
#if RE4DC_VMU_LUIS
        const uint8_t* art=v.subject==Luis?(p.alternate?kLuisBlink:kLuisNeutral):
            (p.alternate?RE4_VMU_ASHLEY_BLINK:RE4_VMU_ASHLEY_NEUTRAL);
        memcpy(out,art,162);
#else
        if(v.subject!=Luis)memcpy(out,p.alternate?RE4_VMU_ASHLEY_BLINK:RE4_VMU_ASHLEY_NEUTRAL,162);
#endif
    }
    strip(c,v);
    if(v.mode==Call){c.rect(26,27,22,5,false);c.text("CALL",32,27);c.rect(27,30,1,2);c.rect(29,28,1,4);if(p.alternate)c.dot(29,28,false);}
    else if(v.mode==Companion&&v.status!=Health){
        const char* word=v.status==Follow?"GO":v.status==Wait?"WAIT":v.status==Help?"HELP":v.status==Play?"PLAY":"ALLY";
        c.rect(29,27,19,5,false);c.text(word,32,27);
    }
    if(v.urgent&&v.mode==Companion){c.text("!",44,2);c.text("!",44,9);}
}

bool ammo_visible(unsigned player,uint32_t stat,unsigned no) {
    if(player==1 || (stat&0xffff0000u)==0x000f0000u)return false;
    return (no>=1&&no<=15)||no==17||no==19||no==22||no==23||no==25||no==28||no==29||no==31||no==32||no==33;
}

unsigned infection_stage(bool injected,uint32_t scenario0,uint32_t scenario1,bool suppressed) {
    // Authored visual milestones, not a hidden engine severity metric. Highest
    // applicable story milestone wins, freshly derived after every save load.
    if(scenario1&0x800u)return 0;       // r330s00: parasite removal completed
    if(suppressed)return 2;            // r325s00: Leon takes the suppressant pills
    if(scenario0&0x40000u)return 3;     // r204s00: castle loss of control
    if(scenario0&0x01000000u)return 2;  // r11b: post-lake infection nightmare
    return injected?1:0;               // r104 arrival after the injection
}

Phase Animation::update(const View& v,unsigned gen,unsigned now,bool reduced) {
    bool changed=!initialized||gen!=generation||v.mode!=previous.mode||v.subject!=previous.subject||v.status!=previous.status||v.urgent!=previous.urgent||v.hp!=previous.hp||v.max_hp!=previous.max_hp||v.condition!=previous.condition;
    bool stage_changed=initialized&&v.infection!=previous.infection;
    if(changed){began=now;growth=false;}
    if(stage_changed && !changed && v.mode==Vitals){from_stage=previous.infection;growth_began=now;growth=true;}
    if(!growth)from_stage=v.infection;
    Phase p={0,from_stage,1000,false};
    if(!reduced){
        unsigned elapsed=now-began;
        p.beat=(elapsed%2000>=200&&elapsed%2000<400)?1:0;
        p.alternate=v.mode==Call?((elapsed%1600)/200)%2!=0:(elapsed%5000>=400&&elapsed%5000<600);
        if(growth){unsigned t=now-growth_began;p.reveal=t>=800?1000:t*1000/800;if(t>=800)growth=false;}
    } else growth=false;
    previous=v;generation=gen;initialized=true;return p;
}
}
