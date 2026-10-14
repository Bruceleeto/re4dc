// FX_SPRITE_TRIM / FX_SPRITE_TRIM_DIAG (fxtrim.mk): included by native_ui.cpp inside its namespace, after Entry and
// before re4dc_effect_sprite. fx_trim() decides how an effect sprite is drawn over the part of its texture that can
// change a pixel (the texels with alpha > 0, tools/d367/fxtrim/fxtrim.py):
//   0 as before; 1 the PVR sprite over the box (`o`); 2 a textured 8-vertex strip over the bounding octagon (P / Q:
//   the corners in the sprite's local coordinates), only for big sprites where the octagon saves at least 10 % more.
struct FxTrimRect {
    unsigned crc, fnv;
    unsigned short x0, y0, x1, y1;   // box, package texels, x1 / y1 exclusive
    short s0, s1, d0, d1;            // octagon: s0 <= x + y <= s1, d0 <= x - y <= d1 (texel units)
};
#if RE4DC_FX_SPRITE_TRIM
#include "fx_sprite_trim_table.inc"   // kFxTrim[] sorted by (crc, fnv); kFxTrimCount (tools/d367/fxtrim/fxtrim.py)
DeferredLighting* const kFxOctTag=reinterpret_cast<DeferredLighting*>(8); // unique: 1..7 are taken (see kGradeTag)
constexpr unsigned kFxOctPacket=sizeof(pvr_poly_hdr_t)+8*sizeof(pvr_vertex_t);
#endif
#if RE4DC_FX_SPRITE_TRIM_DIAG
struct FxTrimSeen { unsigned crc, fnv; double px, px_after; unsigned n; };
FxTrimSeen fx_trim_seen[256]; unsigned fx_trim_nseen;
unsigned fx_trim_log_frame, fx_trim_n, fx_trim_oct, fx_trim_kept, fx_trim_skip, fx_trim_why[4]; // why: blend, depth, shape, uv
double fx_trim_before, fx_trim_after;   // screen pixels (unclipped) since the last log line
inline float fx_trim_area(const Re4dcEffectSprite& s){ // the parallelogram A B C (unclipped)
    return std::fabs((s.x[1]-s.x[0])*(s.y[2]-s.y[1])-(s.y[1]-s.y[0])*(s.x[2]-s.x[1]));
}
#endif
// The octagon's vertices (texel units, clockwise from the top edge's left end), clamped to the box.
inline void fx_trim_octagon(const FxTrimRect& r, float* X, float* Y){
    const float x0=r.x0,x1=r.x1,y0=r.y0,y1=r.y1,s0=r.s0,s1=r.s1,d0=r.d0,d1=r.d1;
    auto cl=[](float v,float lo,float hi){return v<lo?lo:v>hi?hi:v;};
    X[0]=cl(s0-y0,x0,x1);Y[0]=y0;   X[1]=cl(d1+y0,x0,x1);Y[1]=y0;
    X[2]=x1;Y[2]=cl(x1-d1,y0,y1);   X[3]=x1;Y[3]=cl(s1-x1,y0,y1);
    X[4]=cl(s1-y1,x0,x1);Y[4]=y1;   X[5]=cl(d0+y1,x0,x1);Y[5]=y1;
    X[6]=x0;Y[6]=cl(x0-d0,y0,y1);   X[7]=x0;Y[7]=cl(s0-x0,y0,y1);
}
// The nearest value at or below (up = false) / at or above (up = true) f whose float has 16 zero low bits: the UV a
// PVR sprite holds exactly (PVR_PACK_16BIT_UV keeps the top half of the float).
inline float fx_trim_f16(float f, bool up){
    unsigned b;std::memcpy(&b,&f,4);
    if(b&0xffffU){b&=0xffff0000U;if(up && f>0.0f)b+=0x10000U;}
    float r;std::memcpy(&r,&b,4);return r;
}
// An image UV u whose product with su (fx_packet) packs to exactly the 16-bit value pu; false when none is near.
inline bool fx_trim_fit(float pu, float su, float& u){
    u=pu/su;
    for(unsigned k=0;k<4;++k){
        const float x=u*su;unsigned bx,bp;std::memcpy(&bx,&x,4);std::memcpy(&bp,&pu,4);
        if((bx&0xffff0000U)==(bp&0xffff0000U)) return true;
        u=x<pu?std::nextafter(u,2.0f):std::nextafter(u,-1.0f);
    }
    return false;
}
inline int fx_trim(const Re4dcEffectSprite& s, const Entry* e, Re4dcEffectSprite& o, float* P8, float* Q8){
    const auto& t=e->package.textures()[0];
#if RE4DC_FX_SPRITE_TRIM_DIAG
    FxTrimSeen* seen=nullptr;
    {
        unsigned i=0;
        for(;i<fx_trim_nseen;++i) if(fx_trim_seen[i].crc==e->key.crc && fx_trim_seen[i].fnv==e->key.fnv) break;
        if(i==fx_trim_nseen && fx_trim_nseen<256){
            fx_trim_seen[fx_trim_nseen++]=FxTrimSeen{e->key.crc,e->key.fnv,0.0,0.0,0};
            re4dc_log("fxtrim key: %08x-%08x img=%ux%u tex=%ux%u fmt=%u pay=%u src=%u dst=%u pad=%u screen=%u "
                      "uv=%.4f,%.4f %.4f,%.4f %.4f,%.4f %.4f,%.4f z=%.6f,%.6f,%.6f,%.6f\n",
                      e->key.crc,e->key.fnv,unsigned(s.image.width),unsigned(s.image.height),unsigned(t.width),
                      unsigned(t.height),unsigned(t.format),unsigned(t.payload),unsigned(s.src),unsigned(s.dst),
                      unsigned(s.pad),unsigned(s.screen),double(s.u[0]),double(s.v[0]),double(s.u[1]),double(s.v[1]),
                      double(s.u[2]),double(s.v[2]),double(s.u[3]),double(s.v[3]),double(s.z[0]),double(s.z[1]),
                      double(s.z[2]),double(s.z[3]));
        }
        if(i<fx_trim_nseen) seen=&fx_trim_seen[i];
        if(frame-fx_trim_log_frame>=600){
            re4dc_log("fxtrim: frame=%u trimmed=%u oct=%u kept=%u skipped=%u why=%u,%u,%u,%u kpx_before=%u kpx_after=%u\n",
                      frame,fx_trim_n,fx_trim_oct,fx_trim_kept,fx_trim_skip,fx_trim_why[0],fx_trim_why[1],fx_trim_why[2],
                      fx_trim_why[3],unsigned(fx_trim_before/1000.0),unsigned(fx_trim_after/1000.0));
            // the keys that cover the most screen in this window (unclipped kpx before / after)
            for(unsigned k=0;k<6;++k){
                FxTrimSeen* b=nullptr;
                for(unsigned j=0;j<fx_trim_nseen;++j) if(fx_trim_seen[j].px>0.0 && (!b || fx_trim_seen[j].px>b->px)) b=&fx_trim_seen[j];
                if(!b) break;
                re4dc_log("fxtrim top: frame=%u key=%08x-%08x n=%u kpx=%u kpx_after=%u\n",frame,b->crc,b->fnv,b->n,
                          unsigned(b->px/1000.0),unsigned(b->px_after/1000.0));
                b->px=-b->px;
            }
            for(unsigned j=0;j<fx_trim_nseen;++j){fx_trim_seen[j].px=0.0;fx_trim_seen[j].px_after=0.0;fx_trim_seen[j].n=0;}
            fx_trim_log_frame=frame;fx_trim_n=fx_trim_oct=fx_trim_kept=fx_trim_skip=0;fx_trim_before=fx_trim_after=0.0;
            fx_trim_why[0]=fx_trim_why[1]=fx_trim_why[2]=fx_trim_why[3]=0;
        }
    }
    const float area0=fx_trim_area(s);
    if(seen){seen->px+=area0;++seen->n;}
#endif
#if RE4DC_FX_SPRITE_TRIM
    const FxTrimRect* r=nullptr;
    {
        unsigned lo=0,hi=kFxTrimCount;
        while(lo<hi){
            const unsigned mid=(lo+hi)>>1;const FxTrimRect& m=kFxTrim[mid];
            if(m.crc<e->key.crc || (m.crc==e->key.crc && m.fnv<e->key.fnv)) lo=mid+1; else hi=mid;
        }
        if(lo<kFxTrimCount && kFxTrim[lo].crc==e->key.crc && kFxTrim[lo].fnv==e->key.fnv) r=&kFxTrim[lo];
    }
    unsigned why=0;
    bool ok=r!=nullptr && !(s.pad&1) && s.src==4 && (s.dst==5 || s.dst==1);   // PVR SRCALPHA; INVSRCALPHA / ONE
    // One depth (a camera-facing sprite: UV is affine over the quad, as the PVR draws a sprite; an oblique one is left
    // alone: the PVR / Flycast derive the fourth corner affinely, a trimmed quad would move that split)
    if(ok){
        const float z0=s.z[0];
        float dz=0.0f;for(unsigned i=1;i<4;++i){const float d=std::fabs(s.z[i]-z0);if(d>dz)dz=d;}
        ok=z0>0.0f && dz<=1e-4f*z0;why=1;
    }
    // an exact parallelogram (the PVR sprite's D is A + C - B)
    if(ok){ok=std::fabs(s.x[0]+s.x[2]-s.x[1]-s.x[3])<0.01f && std::fabs(s.y[0]+s.y[2]-s.y[1]-s.y[3])<0.01f;why=2;}
    // the whole image, UV 0..1 along the edges (u along D -> C, v along D -> A)
    if(ok){
        ok=s.u[0]==s.u[3] && s.u[1]==s.u[2] && s.v[0]==s.v[1] && s.v[2]==s.v[3] &&
           ((s.u[3]==0.0f && s.u[2]==1.0f) || (s.u[3]==1.0f && s.u[2]==0.0f)) &&
           ((s.v[3]==0.0f && s.v[0]==1.0f) || (s.v[3]==1.0f && s.v[0]==0.0f));
        why=3;
    }
    if(!ok) goto keep;
    {
        const float fw=float(s.image.width),fh=float(s.image.height);
        const float su=fw/t.width,sv=fh/t.height;   // the PVR UV of image UV 1 (fx_packet)
        // the box in PVR UV, widened to values the sprite's 16-bit UV holds exactly (fx_packet PVR_PACK_16BIT_UV keeps
        // the top 16 float bits): the new corners then lie on the sprite's own UV plane and every pixel still drawn
        // samples the texture where it did. An edge at the image border stays where it is.
        const float pu0=fx_trim_f16(float(r->x0)/t.width,false),pu1=fx_trim_f16(float(r->x1)/t.width,true);
        const float pv0=fx_trim_f16(float(r->y0)/t.height,false),pv1=fx_trim_f16(float(r->y1)/t.height,true);
        const float u0=pu0>0.0f?pu0:0.0f,u1=pu1<su?pu1:su,v0=pv0>0.0f?pv0:0.0f,v1=pv1<sv?pv1:sv;   // PVR units
        if(!(u0<u1 && v0<v1)) goto keep;
        // local (p, q) of the box: point = D + p (C - D) + q (A - D); image u = s.u[3] + p (s.u[2] - s.u[3])
        float p0=u0/su,p1=u1/su,q0=v0/sv,q1=v1/sv;
        if(s.u[3]==1.0f){const float x=1.0f-p1;p1=1.0f-p0;p0=x;}
        if(s.v[3]==1.0f){const float x=1.0f-q1;q1=1.0f-q0;q0=x;}
#if RE4DC_FX_SPRITE_TRIM < 2
        (void)P8;(void)Q8;
#else
        if(!s.screen && r->s1>r->s0){
            // FX_SPRITE_TRIM=2: the bounding octagon as a strip (float UV on the same plane) for big sprites where it
            // saves at least 10 % more than the box
            const float quad=std::fabs((s.x[1]-s.x[0])*(s.y[2]-s.y[1])-(s.y[1]-s.y[0])*(s.x[2]-s.x[1]));
            if(quad>=4096.0f){
                float X[8],Y[8];fx_trim_octagon(*r,X,Y);
                float oa=0.0f;bool inside=true;
                for(unsigned i=0;i<8;++i){
                    P8[i]=X[i]/fw;Q8[i]=Y[i]/fh;   // image UV
                    if(s.u[3]==1.0f)P8[i]=1.0f-P8[i];
                    if(s.v[3]==1.0f)Q8[i]=1.0f-Q8[i];
                    inside=inside && P8[i]>=0.0f && P8[i]<=1.0f && Q8[i]>=0.0f && Q8[i]<=1.0f;
                }
                for(unsigned i=0;i<8;++i){const unsigned j=(i+1)&7;oa+=P8[i]*Q8[j]-P8[j]*Q8[i];}
                oa=std::fabs(oa)*0.5f;
                if(inside && oa<=0.9f*(p1-p0)*(q1-q0)){
#if RE4DC_FX_SPRITE_TRIM_DIAG
                    ++fx_trim_oct;fx_trim_before+=area0;fx_trim_after+=area0*oa;if(seen)seen->px_after+=area0*oa;
#endif
                    return 2;
                }
            }
        }
#endif
        if(!(p0>0.0f || p1<1.0f || q0>0.0f || q1<1.0f)) goto keep;
        o=s;
        const float P[4]={p0,p1,p1,p0},Q[4]={q1,q1,q0,q0};   // A(0,1) B(1,1) C(1,0) D(0,0)
        for(unsigned i=0;i<4;++i){
            o.x[i]=s.x[3]+P[i]*(s.x[2]-s.x[3])+Q[i]*(s.x[0]-s.x[3]);
            o.y[i]=s.y[3]+P[i]*(s.y[2]-s.y[3])+Q[i]*(s.y[0]-s.y[3]);
            o.z[i]=s.z[3];
            // image UV whose PVR UV (x su, fx_packet) is the snapped box edge exactly
            const float pu=(P[i]==p0)==(s.u[3]==0.0f)?u0:u1,pv=(Q[i]==q0)==(s.v[3]==0.0f)?v0:v1;
            if(!fx_trim_fit(pu,su,o.u[i]) || !fx_trim_fit(pv,sv,o.v[i])) goto keep;
        }
#if RE4DC_FX_SPRITE_TRIM_DIAG
        ++fx_trim_n;fx_trim_before+=area0;fx_trim_after+=fx_trim_area(o);if(seen)seen->px_after+=fx_trim_area(o);
#endif
        return 1;
    }
keep:
#if RE4DC_FX_SPRITE_TRIM_DIAG
    if(r){++fx_trim_skip;++fx_trim_why[why];} else ++fx_trim_kept;
    fx_trim_before+=area0;fx_trim_after+=area0;if(seen)seen->px_after+=area0;
#endif
    return 0;
#else
    (void)s;(void)o;(void)P8;(void)Q8;
    return 0;
#endif
}
#if RE4DC_FX_SPRITE_TRIM
// The octagon as one textured strip (0 1 7 2 6 3 5 4) with the sprite's texture, blend, depth and fog; every vertex on
// the sprite's own planes (as fx_trim's corners), so the pixels it covers are drawn exactly as the sprite drew them.
void fx_trim_oct_packet(const Re4dcEffectSprite& s,Entry* e,const float* P,const float* Q,unsigned char* out){
    const auto& t=e->package.textures()[0];
    pvr_poly_cxt_t c;pvr_poly_cxt_txr(&c,PVR_LIST_TR_POLY,re4dc::texture::pvr_format(t),t.width,t.height,
                                      const_cast<void*>(e->package.pvr_texture(0)),PVR_FILTER_BILINEAR);
    c.gen.culling=PVR_CULLING_NONE;
    c.depth.comparison=PVR_DEPTHCMP_GEQUAL;c.depth.write=PVR_DEPTHWRITE_DISABLE;
    c.blend.src=(pvr_blend_mode_t)s.src;c.blend.dst=(pvr_blend_mode_t)s.dst;
    c.txr.env=PVR_TXRENV_MODULATEALPHA;c.txr.uv_clamp=PVR_UVCLAMP_UV;
#if RE4DC_NATIVE_FOG
    c.gen.fog_type=PVR_FOG_TABLE;
#endif
    pvr_poly_compile(reinterpret_cast<pvr_poly_hdr_t*>(out),&c);
    static const unsigned char order[8]={0,1,7,2,6,3,5,4};
    const float su=float(s.image.width)/t.width,sv=float(s.image.height)/t.height;
    const float uz3=s.u[3]*s.z[3],vz3=s.v[3]*s.z[3];
    const float duz=s.u[2]*s.z[2]-uz3,duzq=s.u[0]*s.z[0]-uz3,dvz=s.v[2]*s.z[2]-vz3,dvzq=s.v[0]*s.z[0]-vz3;
    auto* v=reinterpret_cast<pvr_vertex_t*>(out+sizeof(pvr_poly_hdr_t));
    for(unsigned i=0;i<8;++i){
        const unsigned k=order[i];const float p=P[k],q=Q[k];
        v[i].flags=i==7?PVR_CMD_VERTEX_EOL:PVR_CMD_VERTEX;
        v[i].x=s.x[3]+p*(s.x[2]-s.x[3])+q*(s.x[0]-s.x[3]);
        v[i].y=s.y[3]+p*(s.y[2]-s.y[3])+q*(s.y[0]-s.y[3]);
        v[i].z=s.z[3]+p*(s.z[2]-s.z[3])+q*(s.z[0]-s.z[3]);
        v[i].u=(uz3+p*duz+q*duzq)/v[i].z*su;
        v[i].v=(vz3+p*dvz+q*dvzq)/v[i].z*sv;
        v[i].argb=s.color;v[i].oargb=0;
    }
}
#endif
