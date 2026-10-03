// Source candidate, included ONCE by coarse_actor_owner_leon.inc instead of
// coarse_actor_certificate_pending.inc. No source preparation or texture load.
// The comparison executes synchronously at the original Render callback; no
// result or borrowed pointer survives it. This is not a source-allocation lease.
#include <cstdint>
#include <cstring>
#include "player.h" // canonical pPL declaration for the reviewed Leon identity
#include "actor_lifetime.h"
#include "actor_material_policy.h"
extern u8 gxCsScale[];
namespace re4dc_material {
struct Digest { unsigned bytes,crc,fnv; };
struct Part { unsigned char material[13]; unsigned bytes,polygons,crc,fnv; };
struct Texture {
    unsigned crc,fnv,width,height,format;
    unsigned sampler[8]; // wrap S/T, min/mag, LOD bits, edge, min/max LOD
    unsigned palette_format; Digest palette;
};
struct Model {
    unsigned header[10]; // see archive-materials.json header_fields
    Digest positions,normals,weights,uv;
    const Part* parts;
};
struct Role {
    unsigned appearance,role,source_bin,source_tpl;
    const Model* model; const Texture* textures; unsigned texture_count;
};
struct SourceBlob { const Model* model; unsigned family,bin; Digest normalized; };

enum Need : unsigned {
    Diffuse=1, Specular=2, Mask=4, Bump=8, Morph=16,
    SourceLighting=32, SourcePass=64, AtlasSampler=128
};
enum class Error : unsigned {
    None, UnknownAppearance, MissingRole, FrameOwner, BadRange,
    Geometry, ConvertedStream, Material, Texture, Palette, Sampler,
    LiveModifier, PassGroup, Capability, MissingOwnerProof, IncompleteColourProof
};
struct Result { Error error; unsigned role,part,required,identity_roles; };
// These are direct SOURCE archive facts, not declarations that the atlas
// implements the material. No production default is enabled by this table.
#include "actor_material_records.inc"

inline bool readable(const void* p,unsigned n) {
    const auto a=reinterpret_cast<std::uintptr_t>(p);
    return a>=0x8c000000u && a<=0x8d000000u && n<=0x8d000000u-a;
}
inline unsigned u32at(const void* p,unsigned at) {
    unsigned x;std::memcpy(&x,static_cast<const unsigned char*>(p)+at,4);return x;
}
inline unsigned u16at(const void* p,unsigned at) {
    unsigned short x;std::memcpy(&x,static_cast<const unsigned char*>(p)+at,2);return x;
}
inline const void* ptrat(const void* p,unsigned at) {
    return reinterpret_cast<const void*>(std::uintptr_t(u32at(p,at)));
}
inline unsigned floatbits(float f) { unsigned x;std::memcpy(&x,&f,4);return x; }
bool digest(const void* p,const Digest& want) {
    if(!readable(p,want.bytes))return false;
    unsigned crc=~0u,fnv=2166136261u;
    auto* b=static_cast<const unsigned char*>(p);
    for(unsigned k=0;k<want.bytes;++k) {
        crc^=b[k];fnv=(fnv^b[k])*16777619u;
        for(unsigned j=0;j<8;++j)crc=(crc>>1)^(0xedb88320u&(0u-(crc&1u)));
    }
    return ~crc==want.crc && fnv==want.fnv;
}
const Role* find(unsigned appearance,unsigned role) {
    for(const auto& r:roles)if(r.appearance==appearance && r.role==role)return &r;
    return nullptr;
}
// Exact certified descriptors have a single base level. Source
// commonModelTrans calls GXInitTexObjLOD (and applies global aniso) only
// when minLOD != maxLOD, so room aniso is inapplicable to these textures.
inline bool base_level_sampler(const unsigned* s) {
    return s[0]==1 && s[1]==1 && s[2]==1 && s[3]==1 &&
           s[4]==0 && s[5]==0 && s[6]==0 && s[7]==0;
}
// cModel::type selects the authored appearance, not a shader modifier.
// Em12Set and Em15Set bind precisely these body/head/TPL families. The
// per-role immutable owner and complete material checks still run below.
inline bool source_appearance_type(unsigned appearance,unsigned id,unsigned type) {
    if(appearance==0x100)return id==0 && type==0;
    static const unsigned char types[5]={1,0,3,4,11};
    return appearance<5 && id==(appearance==0?0x12u:0x15u) && type==types[appearance];
}
inline bool room_colour_scale(unsigned scale,bool flat_native_look) {
    // The approved native look uses its existing constant lighting. Room
    // TEV scales 0/1/2 are valid source environment states, not actor fades.
    return flat_native_look ? scale<=2 : scale==2;
}
Error texture(const void* descriptor,const Texture& e) {
    if(!readable(descriptor,8))return Error::BadRange;
    const void* h=ptrat(descriptor,0);const void* clut=ptrat(descriptor,4);
    if(!readable(h,36))return Error::BadRange;
    const auto* b=static_cast<const unsigned char*>(h);
    if(u16at(h,2)!=e.width || u16at(h,0)!=e.height || u32at(h,4)!=e.format)return Error::Texture;
    unsigned sampler[8]={u32at(h,12),u32at(h,16),u32at(h,20),u32at(h,24),u32at(h,28),b[32],b[33],b[34]};
    if(std::memcmp(sampler,e.sampler,sizeof(sampler)))return Error::Sampler;
    // Keep the exact row comparison above and reject any changed sampler,
    // LOD range, bias or edge flag. Only the source-inapplicable global aniso
    // test is removed; no mipmapped descriptor gains admission here.
    if(!base_level_sampler(sampler))return Error::Sampler;
    const void* n=ptrat(h,8);const unsigned size=e.palette.bytes?64u:32u;
    if(!readable(n,size))return Error::BadRange;
    const char* magic=e.palette.bytes?"R4PREF\0":"R4NREF\0";
    if(std::memcmp(n,magic,8) || u32at(n,8)!=e.crc || u32at(n,12)!=e.fnv ||
       u32at(n,16)!=e.width || u32at(n,20)!=e.height || u32at(n,24)!=e.format)return Error::Texture;
    if(e.palette.bytes) {
        if(!readable(clut,12) || u16at(clut,0)*2u!=e.palette.bytes || u32at(clut,4)!=e.palette_format ||
           u32at(n,32)!=e.palette_format || u32at(n,36)!=e.palette.bytes ||
           u32at(n,40)!=e.palette.crc || u32at(n,44)!=e.palette.fnv ||
           !digest(ptrat(clut,8),e.palette))return Error::Palette;
    } else if(clut)return Error::Palette;
    return Error::None;
}
} // re4dc_material
#include "actor_lifetime.inc"
namespace re4dc_material {
Error info(cModelInfo* i,const Role& row,Result& out,bool diagnostic) {
    if(!readable(i,sizeof(*i)) || !readable(i->pData,sizeof(ModelData)))return Error::BadRange;
    const auto& e=*row.model;const auto& d=*i->pData;
    unsigned h[10]={d.flags,d.shift,d.nParts,d.nVtx,d.nNrm,d.nTex,
      d.weight_palette_num,d.weight_ext_num,d.displist_num,d.version};
    if(std::memcmp(h,e.header,sizeof(h)))return Error::Geometry;
    // Immutable arrays are scanned ONLY by the explicit diagnostic entry.
    // Production requires the current owner/revision proof before this reader.
    if(diagnostic && (!digest(d.vtxOrig,e.positions) || !digest(d.nrmOrig,e.normals) ||
       !digest(d.pWeight,e.weights) || !digest(d.pTex,e.uv)))return Error::Geometry;
    // These are exact infos including their hidden state and second-pass bit.
    // Source visibility bit8 can vary; all other unproved bits decline.
    unsigned expected=1;
    if(row.appearance==0x100 && row.role==3)expected|=2;
    if(row.appearance==0x100 && row.role==7)expected|=0x40;
    if((i->be_flag&~8u)!=expected)return Error::PassGroup;
    if(i->invisible_factor!=1.0f || i->blend_mode || i->colorWord!=0xffffffffu ||
       i->color2[0] || i->color2[1] || i->color2[2] || i->color2[3] ||
       i->flagsDC || i->pAddTpl || i->nAddTex || i->blendRatio || i->blendType ||
       i->texBlendTbl || i->pTexAnim || i->uvU || i->uvV || i->uvScrollU || i->uvScrollV)return Error::LiveModifier;
    if(i->be_flag&2) {
        // shape.cpp writes the prepared destination buffer, not vtxOrig.
        // Native-look explicitly retains the reviewed bone-driven Leon face.
        // Source callback/ShapeMove still runs; this does not emulate morphs.
        const bool face=RE4DC_ACTOR_LEON_NATIVE_LOOK && row.appearance==256 && row.role==3;
        if(i->pShape && !readable(i->pShape,4))return Error::BadRange;
        for(const auto& shape:i->shape) {
            if(!coarse_finite(shape.rate) || (shape.data && !readable(shape.data,4)))return Error::BadRange;
            if(shape.rate!=0.0f && (!face || !shape.data))return Error::LiveModifier;
        }
        out.required|=Morph;
    }
    const void* tp=i->tpl_addr;
    if(!readable(tp,12) || u32at(tp,4)!=row.texture_count)return Error::Texture;
    const void* td=ptrat(tp,8);
    if(!readable(td,row.texture_count*8u))return Error::BadRange;
    for(unsigned k=0;k<row.texture_count;++k) {
        Error r=texture(static_cast<const unsigned char*>(td)+k*8,row.textures[k]);
        if(r!=Error::None)return r;
    }
    auto* p=reinterpret_cast<const unsigned char*>(d.pParts);
    for(unsigned k=0;k<d.displist_num;++k) {
        out.part=k;const auto& want=e.parts[k];
        if(!readable(p,32))return Error::BadRange;
        if(std::memcmp(p+11,want.material,13) || u32at(p,24)!=want.bytes ||
           u32at(p,28)!=want.polygons)return Error::Material;
        if(!readable(p+32,want.bytes))return Error::BadRange;
        // In-place FE conversion destroys original GX bytes. Do not pretend
        // header/pointer identity proves its UV/topology/material admission.
        if(diagnostic && want.bytes && p[32]==0xfe)return Error::ConvertedStream;
        if(diagnostic && !digest(p+32,{want.bytes,want.crc,want.fnv}))return Error::Geometry;
        const auto* mat=want.material;const unsigned f=mat[0];
        if(mat[1]>=row.texture_count)return Error::Material;
        if(f&4) {
            if(mat[3]>=row.texture_count)return Error::Material;
            out.required|=Mask|SourcePass;
        }
        if(f&1) {
            if(mat[2]>=row.texture_count)return Error::Material;
            out.required|=Bump;
        }
        if(f&0x13)out.required|=Specular;
        // All material bytes, including alphaRef/specType/specPow/specTexOrg,
        // already matched. Unknown source flag programs remain unsupported.
        if(f&~7u)return Error::Material;
        p+=32+want.bytes;
    }
    ++out.identity_roles;return Error::None;
}
Result compare(cModel* m,const Re4dcActorPlan* p,bool diagnostic) {
    Result out{Error::None,0,0,Diffuse|SourceLighting|AtlasSampler,0};
    if(!m || !p || !readable(m,sizeof(*m))) {out.error=Error::BadRange;return out;}
    re4dc_source::FrameIdentity frame{};re4dc_source::ModelIdentity owner{};
    if(re4dc_actor_transaction_identity(m,&frame,&owner)!=1) {out.error=Error::FrameOwner;return out;}
    const bool leon=p->appearance==0x100;
    if((leon && (p->count!=8 || m!=(cModel*)pPL || m->id || m->ot_type!=7)) ||
       (!leon && (p->appearance>=5 || p->count<4 || p->count>5 || m->id<0x10 || m->id>0x20 || m->ot_type))) {
        out.error=Error::UnknownAppearance;return out;
    }
    if(m->pTexChg || m->Shader_type || m->CullMode ||
       !source_appearance_type(p->appearance,m->id,m->type) ||
       m->invisible_factor!=1.0f || m->invisible_factor2!=1.0f || m->alpha_omit!=255 ||
       m->TevScaleGroup!=(leon?1:0) ||
       !room_colour_scale(gxCsScale[m->TevScaleGroup],!leon || RE4DC_ACTOR_LEON_NATIVE_LOOK) ||
       m->AddAmb_r || m->AddAmb_g || m->AddAmb_b) {out.error=Error::LiveModifier;return out;}
    for(unsigned k=0;k<p->count;++k) {
        out.role=k;const auto* row=diagnostic?find(p->appearance,k):actor_current_role(m,p->info[k],p->appearance,k);
        if(!row){out.error=Error::MissingRole;return out;}
        if(!diagnostic && !re4dc_actor_material_owner_proof(m,p->info[k],p->appearance,k,RE4DC_ACTOR_MATERIAL_RECORD_REVISION)) {
            out.error=Error::MissingOwnerProof;return out;
        }
        out.error=info(p->info[k],*row,out,diagnostic);if(out.error!=Error::None)return out;
    }
    if(!leon) {
        unsigned source_material_seen=1;
        for(unsigned j=0;j<p->run_count;++j) {
            const auto& run=p->runs[j];const unsigned role=run.role;
            if(role>=p->count || run.material>=p->material_count){out.error=Error::Material;return out;}
            const auto* row=actor_current_role(m,p->info[role],p->appearance,role);
            if(!row){out.error=Error::MissingOwnerProof;return out;}
            const bool original=(role==2 && row->source_bin==451) ||
                (role==3 && row->source_bin==456) || role==4;
            if(!original) {if(run.material!=0){out.error=Error::Material;return out;}continue;}
            Re4dcActorOwnedMaterial want{};
            if(!re4dc_actor_source_material(m,p->info[role],p->appearance,role,&want)) {out.error=Error::Material;return out;}
            const auto& have=p->materials[run.material];
            if(have.image.pixels!=want.image.pixels || have.crc!=want.crc || have.fnv!=want.fnv ||
               have.image.width!=want.image.width || have.image.height!=want.image.height ||
               have.image.format!=want.image.format || have.image.palette || have.image.palette_bytes ||
               have.material_flags || have.blend || have.depth_mode || have.mask_ref!=256 ||
               have.wrap_s!=want.wrap_s || have.wrap_t!=want.wrap_t) {out.error=Error::Material;return out;}
            source_material_seen|=1u<<run.material;
        }
        if(source_material_seen!=(1u<<p->material_count)-1){out.error=Error::Material;return out;}
    }
    // The diagnostic still hashes only the legacy sections. Production's
    // whole normalized BIN proof also covers pClr, heads, blend/flip and padding.
    if(diagnostic) {out.error=Error::IncompleteColourProof;return out;}
    // User-approved flat Ganado look: constant light/specular omission and the
    // reviewed atlas are deliberate, while all source material bytes, masks,
    // samplers, current modifiers and pass identity must still match above.
    unsigned implemented=Diffuse|SourceLighting|AtlasSampler|Specular;
    if(leon) {
        implemented=Diffuse; // source-exact mode has no proven shader substitute
#if RE4DC_ACTOR_LEON_NATIVE_LOOK
        const unsigned runs=re4dc_actor_material_runs_capability(p);
        constexpr unsigned need=RE4DC_ACTOR_RUN_LEASES|RE4DC_ACTOR_RUN_ORDER|RE4DC_ACTOR_RUN_HAIR_TR_NOWRITE;
        if((runs&need)==need)
            implemented=Diffuse|SourceLighting|AtlasSampler|Specular|Bump|Mask|SourcePass|Morph;
        // Known colour/mask pairs + ordered second-pass TR/no-depth-write is
        // an opt-in Dreamcast approximation. It is NOT GC coverage equivalence.
#endif
    }
    if(out.required&~implemented)out.error=Error::Capability;
    return out;
}
}
extern "C" int re4dc_actor_source_material(cModel* m,cModelInfo* info,unsigned app,unsigned role,Re4dcActorOwnedMaterial* out) {
    using namespace re4dc_material;
    if(!out || app<1 || app>4 || role<2 || role>4)return 0;
    const auto* row=actor_current_role(m,info,app,role);if(!row)return 0;
    const bool hand=(role==2 && row->source_bin==451) || (role==3 && row->source_bin==456);
    if(!hand && !(role==4 && (row->source_bin==467 || row->source_bin==484)))return 0;
    const unsigned slot=hand?2u:0u;
    // These four sources have only identical ordinary opaque material states.
    for(unsigned k=0;k<row->model->header[8];++k) {
        const auto* a=row->model->parts[k].material;
        if(a[0] || a[1]!=slot || a[2]!=255 || a[3]!=255 || a[4]!=255)return 0;
    }
    const void* tp=info->tpl_addr;
    if(!readable(tp,12) || u32at(tp,4)!=row->texture_count || slot>=row->texture_count)return 0;
    const auto* d=static_cast<const unsigned char*>(ptrat(tp,8));
    if(!readable(d,row->texture_count*8))return 0;d+=slot*8;
    const auto& e=row->textures[slot];if(e.palette.bytes || texture(d,e)!=Error::None)return 0;
    const void* h=ptrat(d,0);Re4dcActorOwnedMaterial value{};
    value.image={ptrat(h,8),nullptr,e.width,e.height,e.format,0xffffffffu,0};
    value.crc=e.crc;value.fnv=e.fnv;value.wrap_s=e.sampler[0];value.wrap_t=e.sampler[1];
    *out=value;return 1;
}
extern "C" int re4dc_actor_material_certificate(cModel* m,const Re4dcActorPlan* p) {
    const auto r=re4dc_material::compare(m,p,false);
    if(r.error!=re4dc_material::Error::None) {
        static unsigned logged;
        if(logged++<8)re4dc_log("ACTOR_MATERIAL decline=%u app=%u role=%u part=%u need=%x matched=%u\n",
          unsigned(r.error),p?p->appearance:~0u,r.role,r.part,r.required,r.identity_roles);
#if RE4DC_ACTOR_TRANSACTION_DIAG
        // WP2 census: the model-level modifier state behind a LiveModifier decline (bounded).
        static unsigned live_logged;
        if(r.error==re4dc_material::Error::LiveModifier && m && live_logged++<16)
            re4dc_log("ACTOR_MATERIAL live m=%p id=%02x type=%u app=%u role=%u texchg=%p shader=%u cull=%u inv=%d/%d alpha=%u "
                      "tevgrp=%u csscale=%u amb=%u,%u,%u info_be=%x\n",m,unsigned(m->id),unsigned(m->type),p?p->appearance:~0u,r.role,
                      m->pTexChg,unsigned(m->Shader_type),unsigned(m->CullMode),int(m->invisible_factor*1000),
                      int(m->invisible_factor2*1000),unsigned(m->alpha_omit),unsigned(m->TevScaleGroup),
                      unsigned(gxCsScale[m->TevScaleGroup]),unsigned(m->AddAmb_r),unsigned(m->AddAmb_g),unsigned(m->AddAmb_b),
                      p && r.role<p->count && p->info[r.role]?unsigned(p->info[r.role]->be_flag):0u);
#endif
        return 0;
    }
    return 1;
}
// Not called by admission or any installed path. A future bounded diagnostic
// may call this from the same valid original callback, before GX conversion.
// IncompleteColourProof means the stated stored digests/headers matched, not
// complete source identity. No diagnostic result is itself an owner proof.
extern "C" unsigned re4dc_actor_material_diagnose(cModel* m,const Re4dcActorPlan* p,unsigned* need,unsigned* matched) {
    const auto r=re4dc_material::compare(m,p,true);
    if(need)*need=r.required;if(matched)*matched=r.identity_roles;
    return unsigned(r.error);
}
