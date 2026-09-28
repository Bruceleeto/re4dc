// PS2_WORLD_DRAW=1: full authored r101 world; isolated presentation candidate.
// Original collision, object/event lifecycles and gameplay do not use this data.
#ifndef RE4DC_PS2_WORLD_DRAW
#define RE4DC_PS2_WORLD_DRAW 0
#endif
#if RE4DC_PS2_WORLD_DRAW
#include <kos/fs.h>
#include <fcntl.h>
#include <dc/pvr.h>
#include <cmath>
#include "native_render_profile.hpp"
#include "include/native_ps2_world.h"
#include "include/native_model.h"
#include "../../room/ps2_source_owner.hpp"
extern "C" void* re4dc_static_alloc(unsigned);
extern "C" void re4dc_static_free(void*);
extern "C" int re4dc_static_heap_free();
extern "C" unsigned re4dc_ui_frame();
extern "C" void re4dc_log(const char*,...);
extern "C" int re4dc_room4_state(unsigned*,unsigned*,unsigned*,unsigned*,unsigned*);
extern "C" void re4dc_profile_source(re4dc::profile::Source*);
extern "C" int re4dc_ps2_world_packet(unsigned,unsigned,unsigned,unsigned,unsigned,Re4dcModelPacket*);

namespace re4dc { namespace room { namespace ps2 {
namespace {
#include "include/ps2_world_data.inc"
int open_file(void*,const char* p){return int(fs_open(p,O_RDONLY));}
std::int64_t file_size(void*,int f){return fs_total(file_t(f));}
std::ptrdiff_t read_file(void*,int f,void* p,std::size_t n){return fs_read(file_t(f),p,n);}
void close_file(void*,int f){fs_close(file_t(f));}
void* allocate(void*,std::size_t n){return n<=UINT32_MAX?re4dc_static_alloc(unsigned(n)):nullptr;}
void release(void*,void* p){re4dc_static_free(p);}
bool current(void*,Owner& o){
    unsigned generation=0,c,b,s,r;
    const bool live=re4dc_room4_state(&generation,&c,&b,&s,&r)!=0;
    o.generation=generation;
    re4dc::profile::Source source{};re4dc_profile_source(&source);o.room=source.room;return live;
}
SourceOwner& storage(){static SourceOwner owner({nullptr,open_file,file_size,read_file,close_file,allocate,release,current});return owner;}
struct Counters {unsigned groups=0,reject_groups=0,input=0,output=0,packets=0,failed=0,clipped=0,culls=0;};
struct Frame {
    Owner owner{},attempted{};float screen[3][4]{},far=25000;
    unsigned frame=~0u,flushed=~0u,fallbacks=0;bool pending=false;
    Counters count[3];
} state;
int fallback(unsigned reason){
    ++state.fallbacks;const unsigned frame=re4dc_ui_frame();
    if(state.fallbacks<=4 || !(frame%120))re4dc_log("PS2WORLD fallback frame=%u reason=%u count=%u collision_piece0=kept\n",frame,reason,state.fallbacks);
    return 0;
}
struct Vertex {float x,y,w,u,v,r,g,b,a;};
float clamp(float f){return f<0?0:f>1?1:f;}
unsigned channel(float f){return unsigned(clamp(f)*255.0f+0.5f);}
unsigned color(const Vertex& v){return channel(v.a)<<24|channel(v.r)<<16|channel(v.g)<<8|channel(v.b);}
float distance(const Vertex& v,unsigned plane){
    switch(plane){case 0:return v.w-40;case 1:return state.far-v.w;case 2:return v.x;
        case 3:return 640*v.w-v.x;case 4:return v.y;default:return 480*v.w-v.y;}
}
Vertex interpolate(const Vertex& a,const Vertex& b,float t){
    return {a.x+t*(b.x-a.x),a.y+t*(b.y-a.y),a.w+t*(b.w-a.w),
        a.u+t*(b.u-a.u),a.v+t*(b.v-a.v),a.r+t*(b.r-a.r),
        a.g+t*(b.g-a.g),a.b+t*(b.b-a.b),a.a+t*(b.a-a.a)};
}
void normal_light(unsigned placement,const PlacementRecord& p,const std::int16_t* pos,const std::int16_t* normal,float factor,float* rgb){
    // Reproduce the reviewed GC cut0 sun/sky reference, not an invented PS2 light claim.
    const auto& ref=ps2_reference_lighting[placement-79];float world[3],n[3];
    for(unsigned r=0;r<3;++r){
        world[r]=p.affine[r][3];n[r]=0;
        for(unsigned c=0;c<3;++c){world[r]+=p.affine[r][c]*(pos[c]*factor);n[r]+=ref.rotation[r*3+c]*normal[c];}
        rgb[r]=ps2_ambient[r];
    }
    const float norm=std::sqrt(n[0]*n[0]+n[1]*n[1]+n[2]*n[2]);
    if(norm>0)for(auto& x:n)x/=norm;
    for(const auto& l:ref.lights){
        float d[3];for(unsigned c=0;c<3;++c)d[c]=l.pos[c]-world[c];
        const float len=std::sqrt(d[0]*d[0]+d[1]*d[1]+d[2]*d[2]);
        if(len<=0)continue;
        for(auto& x:d)x/=len;
        float cosine=d[0]*l.dir[0]+d[1]*l.dir[1]+d[2]*l.dir[2];if(cosine<0)cosine=0;
        float dot=n[0]*d[0]+n[1]*d[1]+n[2]*d[2];if(dot<0)dot=0;
        float num=l.a[0]+l.a[1]*cosine+l.a[2]*cosine*cosine;if(num<0)num=0;
        const float den=l.k[0]+l.k[1]*len+l.k[2]*len*len;
        if(den>0)for(unsigned c=0;c<3;++c)rgb[c]+=l.col[c]*num/den*dot;
    }
    for(unsigned c=0;c<3;++c)rgb[c]=clamp(rgb[c]);
}
}

// The only friend of the package/owner. Borrowed pool addresses are used inside
// this synchronous call only; Frame stores copied camera/identity scalars.
class WorldDraw {
    SourceOwner& source_;const SpanPackage& package_;
    bool live() const {return source_.live() && same_owner(state.owner,source_.owner_);}
    template<class T>T record(Section section,unsigned index) const{return package_.record<T>(section,index);}
    const std::uint8_t* at(unsigned offset)const{return package_.payload_.data+offset;}
    static void compose(const PlacementRecord& p,float factor,float screen[3][4]){
        for(unsigned r=0;r<3;++r){
            for(unsigned c=0;c<3;++c){screen[r][c]=0;for(unsigned k=0;k<3;++k)screen[r][c]+=state.screen[r][k]*p.affine[k][c]*factor;}
            screen[r][3]=state.screen[r][3];for(unsigned k=0;k<3;++k)screen[r][3]+=state.screen[r][k]*p.affine[k][3];
        }
    }
    static bool reject(const OrderedBoundRecord& g,const float screen[3][4]){
        unsigned mask=63;
        for(unsigned bits=0;bits<8;++bits){
            Vertex v{};float xyz[3];
            for(unsigned r=0;r<3;++r){xyz[r]=screen[r][3];for(unsigned c=0;c<3;++c)xyz[r]+=screen[r][c]*((bits&(1u<<c))?g.maximum[c]:g.minimum[c]);}
            v.x=xyz[0];v.y=xyz[1];v.w=xyz[2];
            // Inflate the rejection boundary for SH4 float composition/rounding.
            // This only admits extra work; the triangle clipper remains authoritative.
            const float margin=32+(std::fabs(v.x)+std::fabs(v.y)+640*std::fabs(v.w))*0.00001f;
            unsigned outside=0;for(unsigned k=0;k<6;++k)if(distance(v,k)<-margin)outside|=1u<<k;
            mask&=outside;
        }
        return mask!=0;
    }
    Vertex vertex(const TemplateRecord& t,const PlacementRecord& p,const float screen[3][4],const Ps2Texture& texture,unsigned corner) const{
        const auto* c=at(t.corner.offset+corner*6);const auto* pos=at(t.position.offset+(u16(c)&0x7fff)*6);
        const auto* uv=at(t.uv.offset+u16(c+2)*4);const auto* attr=at(t.attribute.offset+u16(c+4)*(t.attribute_kind?6:4));
        std::int16_t q[3]={i16(pos),i16(pos+2),i16(pos+4)};Vertex v{};float xyz[3];
        for(unsigned r=0;r<3;++r){xyz[r]=screen[r][3];for(unsigned j=0;j<3;++j)xyz[r]+=screen[r][j]*q[j];}
        v.x=xyz[0];v.y=xyz[1];v.w=xyz[2];
        v.u=i16(uv)*(1.0f/256);v.v=i16(uv+2)*(1.0f/256);
        float rgb[3];
        if(t.attribute_kind){std::int16_t n[3]={i16(attr),i16(attr+2),i16(attr+4)};normal_light(p.placement,p,q,n,t.factor,rgb);v.a=1;}
        else {for(unsigned j=0;j<3;++j)rgb[j]=attr[j]*(1.0f/128);v.a=attr[3]*(1.0f/128);}
        v.r=clamp(rgb[0]*texture.gain[0]);v.g=clamp(rgb[1]*texture.gain[1]);v.b=clamp(rgb[2]*texture.gain[2]);
        return v;
    }
    static unsigned triangle(const Vertex& a,const Vertex& b,const Vertex& c,unsigned cull,pvr_vertex_t* output,Counters& stats){
        ++stats.input;Vertex aa[12]={a,b,c},bb[12];Vertex* in=aa;Vertex* out=bb;unsigned count=3;
        for(unsigned plane=0;plane<6 && count;++plane){
            unsigned next=0;Vertex prev=in[count-1];float pd=distance(prev,plane);
            for(unsigned i=0;i<count;++i){const Vertex now=in[i];const float nd=distance(now,plane);
                if((pd<0)!=(nd<0))out[next++]=interpolate(prev,now,pd/(pd-nd));
                if(nd>=0)out[next++]=now;
                prev=now;pd=nd;
            }
            count=next;Vertex* swap=in;in=out;out=swap;
        }
        if(count<3){++stats.clipped;return 0;}
        if(count!=3)++stats.clipped;
        unsigned written=0;
        for(unsigned j=1;j+1<count;++j){
            const Vertex* v[3]={in,in+j,in+j+1};float x[3],y[3],z[3];
            for(unsigned k=0;k<3;++k){z[k]=1/v[k]->w;x[k]=v[k]->x*z[k];y[k]=v[k]->y*z[k];}
            const float area=(x[1]-x[0])*(y[2]-y[0])-(y[1]-y[0])*(x[2]-x[0]);
            if((cull==0 && area>=0)||(cull==1 && area<=0)||area==0){++stats.culls;continue;}
            for(unsigned k=0;k<3;++k)output[written++]={k==2?PVR_CMD_VERTEX_EOL:PVR_CMD_VERTEX,x[k],y[k],z[k],v[k]->u,v[k]->v,color(*v[k]),0};
        }
        return written;
    }
public:
    explicit WorldDraw(SourceOwner& owner):source_(owner),package_(owner.package_){}
    bool qualified()const{
        if(!source_.live())return false;
        const auto& h=package_.header_;
        if(h.base.payload_crc32!=ps2_payload_crc || h.base.triangle_count!=51237 || h.table[ordered_ranges].count!=342 || h.table[placements].count!=209)return false;
        // Generated reference lighting only covers the22 original NORMAL placements.
        for(unsigned pi=0;pi<209;++pi){const auto p=record<PlacementRecord>(placements,pi);const auto t=record<TemplateRecord>(templates,p.template_index);
            if(bool(t.attribute_kind)!=(pi>=79 && pi<=100))return false;}
        return true;
    }
    Owner owner()const{return source_.owner_;}
    bool draw(unsigned pass){
        auto& stats=state.count[pass];
        for(unsigned ri=0;ri<342;++ri){
            const auto& policy=ps2_policy[ri];if(policy.pass!=pass)continue;
            if(!live()){++stats.failed;return false;}
            const auto r=record<OrderedRangeRecord>(ordered_ranges,ri);const auto p=record<PlacementRecord>(placements,r.placement);
            const auto t=record<TemplateRecord>(templates,r.template_index);const auto& tex=ps2_textures[policy.texture];
            float screen[3][4];compose(p,t.factor,screen);Re4dcModelPacket packet{};unsigned used=0;bool failed=false;
            for(unsigned gi=0;gi<r.group_count && !failed;++gi){
                const auto g=record<OrderedBoundRecord>(ordered_bounds,r.first_group+gi);++stats.groups;
                if(reject(g,screen)){++stats.reject_groups;continue;}
                Vertex ring[3];unsigned length=0;
                for(unsigned ci=g.first_corner;ci<g.first_corner+g.corner_count;++ci){
                    ring[length%3]=vertex(t,p,screen,tex,ci);
                    if(length>=2){
                        pvr_vertex_t scratch[30];const Vertex& a=ring[(length-2)%3];const Vertex& b=ring[(length-1)%3];const Vertex& c=ring[length%3];
                        const unsigned n=(length&1)?triangle(c,b,a,policy.cull,scratch,stats):triangle(a,b,c,policy.cull,scratch,stats);
                        if(n){
                            if(!packet.vertices || used+n>packet.capacity){
                                if(used){re4dc_model_packet_commit(used);stats.output+=used/3;used=0;}
                                if(!re4dc_ps2_world_packet(tex.crc,tex.fnv,tex.width,tex.height,pass,&packet)||packet.capacity<n||!live()){
                                    ++stats.failed;failed=true;
                                    if(stats.failed<=8)re4dc_log("PS2WORLD reject frame=%u pass=%u range=%u key=%08x-%08x\n",state.frame,pass,ri,tex.crc,tex.fnv);
                                    break;
                                }
                                ++stats.packets;
                            }
                            std::memcpy(static_cast<pvr_vertex_t*>(packet.vertices)+used,scratch,n*sizeof(pvr_vertex_t));used+=n;
                        }
                    }
                    ++length;if(u16(at(t.corner.offset+ci*6))&0x8000)length=0;
                }
            }
            if(used){re4dc_model_packet_commit(used);stats.output+=used/3;}
        }
        return stats.failed==0;
    }
};
}}}
extern "C" int re4dc_ps2_world_draw(unsigned room,const float screen[3][4],float far){
    using namespace re4dc::room::ps2;
    state.pending=false;auto& owner=storage();Owner now{};
    if(room!=0x101 || !current(nullptr,now) || now.room!=room){owner.retire();return 0;}
    if(!owner.live()){
        if(same_owner(now,state.attempted))return fallback(1);
        state.attempted=now;
        const int before=re4dc_static_heap_free();
        const auto status=owner.load("/cd/dc/native/r101/ps2-world.r4p",{0x101,ps2_asset_owner,1191800});
        re4dc_log("PS2WORLD adopt room=%03x gen=%u status=%u package=%u bytes=%u heap=%d/%d\n",room,unsigned(now.generation),unsigned(status),unsigned(owner.package_error()),unsigned(owner.resident_bytes()),before,re4dc_static_heap_free());
    }
    WorldDraw draw(owner);if(!draw.qualified())return fallback(2);
    for(unsigned r=0;r<3;++r)for(unsigned c=0;c<4;++c)if(!finite_word(screen[r][c]))return fallback(3);
    if(!finite_word(far) || far<=40)return fallback(3);
    state.owner=draw.owner();state.frame=re4dc_ui_frame();state.flushed=~0u;state.far=far<25000?far:25000;
    std::memcpy(state.screen,screen,sizeof(state.screen));for(auto& c:state.count)c={};
    const bool complete=draw.draw(0);state.pending=true;
    // Failure leaves piece0 collision fallback enabled; already emitted triangles
    // are not falsely called complete. PT/TR success is separately reported.
    return complete?1:fallback(4);
}
extern "C" int re4dc_ps2_world_pending(){
    using namespace re4dc::room::ps2;
    return state.pending && state.frame==re4dc_ui_frame() && state.flushed!=state.frame;
}
extern "C" void re4dc_ps2_world_flush(){
    using namespace re4dc::room::ps2;
    if(!state.pending || state.frame!=re4dc_ui_frame() || state.flushed==state.frame)return;
    state.flushed=state.frame;state.pending=false;WorldDraw draw(storage());
    const bool pt=draw.draw(1),tr=draw.draw(2);
    if(!(state.frame%120) || !pt || !tr || state.count[0].failed){
        for(unsigned p=0;p<3;++p){const auto& c=state.count[p];
            re4dc_log("PS2WORLD frame=%u pass=%u groups=%u reject=%u input=%u out=%u packets=%u fail=%u clip=%u cull=%u\n",state.frame,p,c.groups,c.reject_groups,c.input,c.output,c.packets,c.failed,c.clipped,c.culls);}
    }
}
extern "C" void re4dc_ps2_world_retire(){
    using namespace re4dc::room::ps2;state.pending=false;state.frame=~0u;state.owner={};state.attempted={};state.fallbacks=0;storage().retire();
}
#endif
