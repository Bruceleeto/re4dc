// NATIVE_MODEL_REGISTRY_PACK: the room package's complete validation (coarse_actor_registry_pack.inc), apart so the
// host test (tools/d367/model_registry_pack_test.cpp) runs this exact code on generated and malformed packages.
// Needs, declared before it: nmr::Descriptor / Chunk / Texture / Weight and kReg* (coarse_actor_owner_registry.inc),
// re4dc_material::Part / Texture / Model / Role / SourceBlob, kRoomRoles / kRoomBlobs (actor_material_records.inc)
// and coarse_finite (coarse_skin.h). Writes only the pack_* records below; publishes nothing.
#include <cstddef>
#include <cstring>
namespace {
using re4dc_material::kRoomRoles;using re4dc_material::kRoomBlobs;
constexpr unsigned kPackMaxBytes=192u*1024u;  // model_registry.py PACK_MAX_BYTES: aligned package + skin arena
constexpr unsigned kPackHeader=64,kPackKinds=12,kPackPayload=kPackHeader+kPackKinds*16;
enum PackKind : unsigned {kDesc,kRef,kGeom,kBlob,kTex,kParents,kBind,kFModel,kFPart,kFTex,kRole,kSBlob};
constexpr unsigned kPackRecord[kPackKinds]={48,16,64,1,16,1,48,96,32,68,32,32};
constexpr unsigned kPackModels=8,kPackParts=32,kPackTexFacts=16;
constexpr unsigned kPackCapacity[kPackKinds]={kRegDescriptors,kRegChunks,kRegGeometry,kPackMaxBytes,kRegTextures,
    kRegDescriptors*kRegBones,kRegDescriptors*kRegBones,kPackModels,kPackParts,kPackTexFacts,kRoomRoles,kRoomBlobs};
static_assert(sizeof(re4dc_material::Part)==32 && offsetof(re4dc_material::Part,bytes)==16,"package part fact records");
static_assert(sizeof(re4dc_material::Texture)==68,"package texture fact records");
enum PackWhy : unsigned {
    kPwNone,kPwMissing,kPwSize,kPwAlloc,kPwRead,kPwHeader,kPwHash,kPwRoom,kPwTable,kPwDescriptor,kPwRef,kPwGeometry,
    kPwOverlap,kPwDuplicate,kPwTexture,kPwSkeleton,kPwFacts,kPwRole,kPwBlob,kPwBinding,kPwPreflight,kPwSkin,kPwCount
};
const char* const kPackWhy[kPwCount]={"none","missing","size","alloc","read","header","hash","room","table","descriptor",
    "ref","geometry","overlap","duplicate","texture","skeleton","facts","role","blob","binding","preflight","skin"};
// The view's records (bounded; written while validating, read only after the publish).
nmr::Descriptor pack_desc[kRegDescriptors];
nmr::Chunk pack_chunks[kRegChunks];
nmr::Texture pack_tex[kRegTextures];
re4dc_material::Model pack_models[kPackModels];
re4dc_material::Role pack_roles[kRoomRoles];
re4dc_material::SourceBlob pack_blobs[kRoomBlobs];

inline unsigned pu32(const unsigned char* p,unsigned at) {unsigned x;std::memcpy(&x,p+at,4);return x;}
struct PackHash {
    unsigned crc=~0u,fnv=2166136261u;
    void add(const unsigned char* b,unsigned n) {
        for(unsigned k=0;k<n;++k) {
            crc^=b[k];fnv=(fnv^b[k])*16777619u;
            for(unsigned j=0;j<8;++j)crc=(crc>>1)^(0xedb88320u&(0u-(crc&1u)));
        }
    }
    unsigned crc32() const {return ~crc;}
};
struct PackSection { unsigned at,bytes,count; };
struct PackSpan { unsigned at,bytes; };

// Validation and the record build. On kPwNone the pack_* records describe the package at base; nothing is published.
PackWhy pack_validate(const unsigned char* p,unsigned size,unsigned room,unsigned& detail) {
    detail=0;
    if(size<kPackPayload || std::memcmp(p,"RE4NMR1\0",8))return kPwHeader;
    const unsigned version=pu32(p,8),header=pu32(p,12),total=pu32(p,16),kinds=pu32(p,20),table=pu32(p,24),skin=pu32(p,28),
        proom=pu32(p,32),pcrc=pu32(p,36),pfnv=pu32(p,40),hcrc=pu32(p,44),app0=pu32(p,48),max_bones=pu32(p,52);
    if(version!=1 || header!=kPackHeader || total!=size || kinds!=kPackKinds || table!=kPackHeader || app0!=nmr::appearance_first ||
       !max_bones || max_bones>kRegBones || pu32(p,56) || pu32(p,60)){detail=version;return kPwHeader;}
    if(!skin || skin%8u || ((size+31u)&~31u)+skin>kPackMaxBytes){detail=skin;return kPwSize;}
    {
        unsigned char h[kPackHeader];std::memcpy(h,p,kPackHeader);std::memset(h+44,0,4);
        PackHash a;a.add(h,kPackHeader);if(a.crc32()!=hcrc){detail=1;return kPwHash;}
        PackHash b;b.add(p+kPackHeader,size-kPackHeader);if(b.crc32()!=pcrc || b.fnv!=pfnv){detail=2;return kPwHash;}
    }
    if(proom!=room){detail=proom;return kPwRoom;}
    // ---- section table
    PackSection sec[kPackKinds];unsigned end=kPackPayload;
    for(unsigned k=0;k<kPackKinds;++k) {
        const unsigned at=kPackHeader+k*16,kind=pu32(p,at),off=pu32(p,at+4),bytes=pu32(p,at+8),count=pu32(p,at+12);
        detail=k;
        if(kind!=k+1 || off%32u || off<end || off>size || bytes>size-off || !count || count>kPackCapacity[k] ||
           bytes!=count*kPackRecord[k])return kPwTable;
        sec[k]={off,bytes,count};end=off+bytes;
    }
    const unsigned char* blob=p+sec[kBlob].at;
    // ---- textures: power-of-two sizes, unique keys
    for(unsigned t=0;t<sec[kTex].count;++t) {
        const unsigned char* r=p+sec[kTex].at+t*16;detail=t;
        const unsigned crc=pu32(r,0),fnv=pu32(r,4),w=pu32(r,8),h=pu32(r,12);
        if(w<8 || w>1024 || (w&(w-1)) || h<8 || h>1024 || (h&(h-1)))return kPwTexture;
        for(unsigned u=0;u<t;++u)if(pack_tex[u].crc==crc && pack_tex[u].fnv==fnv)return kPwDuplicate;
        pack_tex[t]={crc,fnv,w,h};
    }
    // ---- geometry: counts, aligned spans inside the blob section, hashes; every array disjoint from every other
    PackSpan spans[kRegGeometry*5];unsigned nspans=0,skin_sum=0;
    for(unsigned g=0;g<sec[kGeom].count;++g) {
        const unsigned char* r=p+sec[kGeom].at+g*64;detail=g;
        const unsigned np=pu32(r,0),nn=pu32(r,4),npal=pu32(r,8),tris=pu32(r,12),sbytes=pu32(r,16),uvb=pu32(r,20),
            sk=pu32(r,24),bones=pu32(r,28);
        if(!np || np>65535 || !nn || nn>65535 || !npal || npal>256 || !tris || sbytes<32 || sbytes>(1u<<20) || !uvb || uvb%4u ||
           !sk || sk%8u || !bones || bones>max_bones || pu32(r,60))return kPwGeometry;
        const unsigned want[5]={np*8u,nn*8u,uvb,sbytes,npal*16u};
        PackHash hsh;
        for(unsigned a=0;a<5;++a) {
            const unsigned at=pu32(r,32+a*4);
            if(at%32u || at>sec[kBlob].bytes || want[a]>sec[kBlob].bytes-at)return kPwGeometry;
            spans[nspans++]={at,want[a]};hsh.add(blob+at,want[a]);
        }
        if(hsh.crc32()!=pu32(r,52) || hsh.fnv!=pu32(r,56))return kPwHash;
        const auto* w=reinterpret_cast<const nmr::Weight*>(blob+pu32(r,48));
        for(unsigned j=0;j<npal;++j) {
            if(!w[j].count || w[j].count>3)return kPwGeometry;
            for(unsigned k=0;k<3;++k)
                if((k<w[j].count && w[j].bone[k]>=bones) || !coarse_finite(w[j].value[k]))return kPwGeometry;
        }
        // An identical geometry stored twice: the generator stores each once, so this package is malformed.
        for(unsigned u=0;u<g;++u) {
            const unsigned char* q=p+sec[kGeom].at+u*64;bool same=!std::memcmp(q,r,32) && pu32(q,52)==pu32(r,52) && pu32(q,56)==pu32(r,56);
            for(unsigned a=0;a<5 && same;++a)same=!std::memcmp(blob+pu32(q,32+a*4),blob+pu32(r,32+a*4),want[a]);
            if(same){detail=g*256+u;return kPwDuplicate;}
        }
        skin_sum+=sk;
    }
    if(skin_sum!=skin){detail=skin_sum;return kPwSize;}
    for(unsigned i=1;i<nspans;++i)for(unsigned j=i;j>0 && spans[j-1].at>spans[j].at;--j){const PackSpan t=spans[j];spans[j]=spans[j-1];spans[j-1]=t;}
    for(unsigned i=1;i<nspans;++i)if(spans[i-1].at+spans[i-1].bytes>spans[i].at){detail=i;return kPwOverlap;}
    // ---- descriptors, their chunk references, parents and binds
    const auto* parents=reinterpret_cast<const signed char*>(p+sec[kParents].at);
    const auto* bind=reinterpret_cast<const float (*)[12]>(p+sec[kBind].at);
    unsigned refs=0,parents_used=0,binds_used=0,geom_used[kRegGeometry]={},tex_used=0;
    for(unsigned d=0;d<sec[kDesc].count;++d) {
        const unsigned char* r=p+sec[kDesc].at+d*48;detail=d;auto& desc=pack_desc[d];
        unsigned n=0;while(n<16 && r[n])++n;
        if(!n || n==16)return kPwDescriptor;
        for(unsigned k=0;k<n;++k)if(r[k]<0x20 || r[k]>0x7e)return kPwDescriptor;
        for(unsigned k=n;k<16;++k)if(r[k])return kPwDescriptor;
        const unsigned app=pu32(r,16),id=pu32(r,20),bones=pu32(r,24),sections=pu32(r,28),first=pu32(r,32),pat=pu32(r,36),bfirst=pu32(r,40);
        if(app!=nmr::appearance_first+d || id>255 || !bones || bones>max_bones || !sections || sections>8 || first!=refs ||
           pat!=parents_used || bfirst!=binds_used || pu32(r,44) || refs+sections>sec[kRef].count ||
           pat+bones>sec[kParents].count || bfirst+bones>sec[kBind].count)return kPwDescriptor;
        // Skeleton: an index-ordered forest rooted at bone 0, finite inverse binds.
        if(parents[pat]!=-1)return kPwSkeleton;
        for(unsigned k=1;k<bones;++k)if(parents[pat+k]<-1 || parents[pat+k]>=int(k))return kPwSkeleton;
        for(unsigned k=0;k<bones;++k)for(unsigned e=0;e<12;++e)if(!coarse_finite(bind[bfirst+k][e]))return kPwSkeleton;
        std::memset(desc.name,0,sizeof(desc.name));std::memcpy(desc.name,r,n);
        desc.appearance=app;desc.model_id=id;desc.bones=bones;desc.sections=sections;desc.first_chunk=first;desc.skin_bytes=0;
        desc.parents=parents+pat;desc.bind=bind+bfirst;
        for(unsigned i=0;i<sections;++i) {
            const unsigned char* f=p+sec[kRef].at+(first+i)*16;detail=d*256+i;
            const unsigned g=pu32(f,0),t=pu32(f,4);
            if(g>=sec[kGeom].count || t>=sec[kTex].count || pu32(f,8)!=i || pu32(f,12))return kPwRef;
            const unsigned char* q=p+sec[kGeom].at+g*64;
            if(pu32(q,28)!=bones)return kPwRef;
            auto& c=pack_chunks[first+i];
            c.source_info=i;c.position_count=pu32(q,0);c.normal_count=pu32(q,4);c.palette_count=pu32(q,8);c.triangles=pu32(q,12);
            c.stream_bytes=pu32(q,16);c.uv_bytes=pu32(q,20);c.skin_bytes=pu32(q,24);c.texture=t;c.geometry=g;
            c.positions=blob+pu32(q,32);c.normals=blob+pu32(q,36);c.uv=blob+pu32(q,40);c.stream=blob+pu32(q,44);
            c.weights=reinterpret_cast<const nmr::Weight*>(blob+pu32(q,48));
            desc.skin_bytes+=c.skin_bytes;geom_used[g]=1;tex_used|=1u<<t;
        }
        refs+=sections;parents_used+=bones;binds_used+=bones;
    }
    detail=0;
    if(refs!=sec[kRef].count || parents_used!=sec[kParents].count || binds_used!=sec[kBind].count)return kPwDescriptor;
    for(unsigned g=0;g<sec[kGeom].count;++g)if(!geom_used[g]){detail=g;return kPwRef;}
    if(tex_used!=(sec[kTex].count==32?~0u:(1u<<sec[kTex].count)-1u))return kPwRef;
    // ---- source identity facts: models own contiguous part ranges; texture facts are read in place
    const auto* parts=reinterpret_cast<const re4dc_material::Part*>(p+sec[kFPart].at);
    const auto* tfacts=reinterpret_cast<const re4dc_material::Texture*>(p+sec[kFTex].at);
    unsigned parts_used=0;
    for(unsigned m=0;m<sec[kFModel].count;++m) {
        const unsigned char* r=p+sec[kFModel].at+m*96;detail=m;auto& model=pack_models[m];
        std::memcpy(model.header,r,40);
        const unsigned* dg=reinterpret_cast<const unsigned*>(r+40);
        model.positions={dg[0],dg[1],dg[2]};model.normals={dg[3],dg[4],dg[5]};model.weights={dg[6],dg[7],dg[8]};model.uv={dg[9],dg[10],dg[11]};
        const unsigned first=pu32(r,88),count=pu32(r,92);
        if(first!=parts_used || !count || count!=model.header[8] || first+count>sec[kFPart].count)return kPwFacts;
        model.parts=parts+first;parts_used+=count;
    }
    if(parts_used!=sec[kFPart].count)return kPwFacts;
    for(unsigned k=0;k<sec[kFPart].count;++k) {
        const unsigned char* r=p+sec[kFPart].at+k*32;detail=k;
        if(r[13] || r[14] || r[15])return kPwFacts;
    }
    // ---- role rows: one per descriptor section (appearance, role) and nothing else
    for(unsigned k=0;k<sec[kRole].count;++k) {
        const unsigned char* r=p+sec[kRole].at+k*32;detail=k;
        const unsigned app=pu32(r,0),role=pu32(r,4),bin=pu32(r,8),tpl=pu32(r,12),fm=pu32(r,16),tf=pu32(r,20),tn=pu32(r,24);
        if(app<nmr::appearance_first || app-nmr::appearance_first>=sec[kDesc].count ||
           role>=pack_desc[app-nmr::appearance_first].sections || fm>=sec[kFModel].count || !tn || tn>8 ||
           tf>sec[kFTex].count || tn>sec[kFTex].count-tf || pu32(r,28) || !bin || !tpl)return kPwRole;
        for(unsigned u=0;u<k;++u)if(pack_roles[u].appearance==app && pack_roles[u].role==role)return kPwDuplicate;
        pack_roles[k]={app,role,bin,tpl,&pack_models[fm],tfacts+tf,tn};
    }
    if(sec[kRole].count!=refs){detail=refs;return kPwRole;}
    // Two descriptors whose sections prove the same source identity (model + TPL rows) would be ambiguous.
    for(unsigned a=0;a<sec[kDesc].count;++a)for(unsigned b=a+1;b<sec[kDesc].count;++b) {
        if(pack_desc[a].sections!=pack_desc[b].sections)continue;
        bool same=true;
        for(unsigned i=0;i<pack_desc[a].sections && same;++i) {
            const re4dc_material::Role* x=nullptr;const re4dc_material::Role* y=nullptr;
            for(unsigned k=0;k<sec[kRole].count;++k) {
                if(pack_roles[k].appearance==pack_desc[a].appearance && pack_roles[k].role==i)x=&pack_roles[k];
                if(pack_roles[k].appearance==pack_desc[b].appearance && pack_roles[k].role==i)y=&pack_roles[k];
            }
            same=x && y && x->model==y->model && x->source_tpl==y->source_tpl && x->textures==y->textures;
        }
        if(same){detail=a*256+b;return kPwDuplicate;}
    }
    // ---- source blobs: one per fact model, enemy archives; every role's model has the blob of its BIN
    for(unsigned k=0;k<sec[kSBlob].count;++k) {
        const unsigned char* r=p+sec[kSBlob].at+k*32;detail=k;
        const unsigned fm=pu32(r,0),family=pu32(r,4),bin=pu32(r,8);
        if(fm>=sec[kFModel].count || family!=2 || !bin || !pu32(r,12) || pu32(r,24) || pu32(r,28))return kPwBlob;
        for(unsigned u=0;u<k;++u)if(pack_blobs[u].model==&pack_models[fm])return kPwDuplicate;
        pack_blobs[k]={&pack_models[fm],family,bin,{pu32(r,12),pu32(r,16),pu32(r,20)}};
    }
    for(unsigned k=0;k<sec[kRole].count;++k) {
        bool bound=false;detail=k;
        for(unsigned u=0;u<sec[kSBlob].count;++u)bound|=pack_blobs[u].model==pack_roles[k].model && pack_blobs[u].bin==pack_roles[k].source_bin;
        if(!bound)return kPwBinding;
    }
    for(unsigned u=0;u<sec[kSBlob].count;++u) {
        bool used=false;detail=u;
        for(unsigned k=0;k<sec[kRole].count;++k)used|=pack_roles[k].model==pack_blobs[u].model;
        if(!used)return kPwBinding;
    }
    detail=0;return kPwNone;
}
}
