// ps2_world_check <ps2-world.re4mesh> <ps2-world.r4pw>: the runtime's own acceptance test for one PS2 world package,
// on the host (world_registry.py builds and runs it). The R4IM test is room/instanced_mesh.hpp MeshPackage::adopt
// (lod, prelit) built with the play recipe's TREE_IMPOSTOR=1 MESH_TEXTURES=1; the R4PW test repeats
// native_static.cpp ps2_open's sidecar checks line for line (keep them in step). Prints one JSON object: ok, why
// (the runtime's "PS2MESH open failed" reason), the header counts, the heap-4 block the open allocates, the
// placement translation box and the part texture keys {crc, fnv, width, height, pass, cull}.
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include "instanced_mesh.hpp"

namespace {
struct Ps2Part { std::uint32_t crc,fnv; std::uint16_t width,height; std::uint8_t pass,cull,texture,reserved; };
struct Ps2Placement { std::uint16_t mesh,placement; float affine[12]; };
struct Ps2Head { char magic[4]; std::uint32_t version,placements,parts,meshes,crc,reserved[2]; };
static_assert(sizeof(Ps2Part)==16 && sizeof(Ps2Placement)==52 && sizeof(Ps2Head)==32);
constexpr unsigned kLutBytes=512*4;   // native_static.cpp, RE4DC_MESH_FASTPATH (the play recipe)
constexpr unsigned kGatherBytes=(256U*unsigned(sizeof(re4dc::room::CompactVertex12))+31U)&~31U;
std::uint32_t ps2_crc32(const unsigned char* p,unsigned n){
    std::uint32_t c=~0U;
    for(unsigned i=0;i<n;++i){c^=p[i];for(unsigned b=0;b<8;++b)c=(c>>1)^(0xedb88320U&(0U-(c&1U)));}
    return ~c;
}
bool is_finite(float f){return std::isfinite(f);}
std::vector<unsigned char> slurp(const char* path){
    std::vector<unsigned char> v;
    if(FILE* f=std::fopen(path,"rb")){
        unsigned char b[65536];size_t n;
        while((n=std::fread(b,1,sizeof(b),f))>0)v.insert(v.end(),b,b+n);
        std::fclose(f);
    }
    return v;
}
}

int main(int argc,char** argv){
    if(argc!=3){std::fprintf(stderr,"usage: ps2_world_check <re4mesh> <r4pw>\n");return 2;}
    const auto m=slurp(argv[1]),p=slurp(argv[2]);
    const unsigned msize=unsigned(m.size()),psize=unsigned(p.size());
    const unsigned mbytes=(msize+31U)&~31U,pbytes=(psize+31U)&~31U,total=mbytes+pbytes+kLutBytes+kGatherBytes;
    // ps2_open: one 32-byte aligned block, mesh first, sidecar at mbytes
    std::vector<std::uint32_t> words((mbytes+pbytes)/4+8);
    auto* s=reinterpret_cast<unsigned char*>(words.data());
    if(msize)std::memcpy(s,m.data(),msize);
    if(psize)std::memcpy(s+mbytes,p.data(),psize);
    bool ok=msize && psize>=sizeof(Ps2Head);
    const char* why=ok?nullptr:"missing or no heap";
    re4dc::room::MeshPackage package;
    if(ok && !package.adopt(s,msize,true,true)){why=package.error();ok=false;}
    Ps2Head h{};
    if(ok){
        std::memcpy(&h,s+mbytes,sizeof(h));
        const auto& mh=package.header();
        const unsigned body=psize-unsigned(sizeof(h));
        if(std::memcmp(h.magic,"R4PW",4) || h.version!=1 || h.parts!=mh.part_count || h.meshes!=mh.mesh_count ||
           body!=h.parts*sizeof(Ps2Part)+h.placements*sizeof(Ps2Placement) || ps2_crc32(s+mbytes+sizeof(h),body)!=h.crc){why="sidecar";ok=false;}
    }
    const Ps2Part* parts=nullptr;const Ps2Placement* placements=nullptr;
    if(ok){
        parts=reinterpret_cast<const Ps2Part*>(s+mbytes+sizeof(h));
        placements=reinterpret_cast<const Ps2Placement*>(parts+h.parts);
        for(unsigned i=0;i<h.parts && ok;++i){
            const auto& q=parts[i];
            ok=q.pass<=2 && q.cull<=2 && q.width && q.height && q.width<=1024 && q.height<=1024;
        }
        for(unsigned i=0;i<h.placements && ok;++i){
            const auto& q=placements[i];ok=q.mesh<h.meshes;
            for(float f:q.affine)ok=ok && is_finite(f);
        }
        if(!ok)why="sidecar records";
    }
    std::printf("{\"ok\": %s, \"why\": %s%s%s, \"mesh_bytes\": %u, \"sidecar_bytes\": %u, \"heap_bytes\": %u",
        ok?"true":"false",why?"\"":"",why?why:"null",why?"\"":"",msize,psize,total);
    if(ok){
        const auto& mh=package.header();
        std::printf(", \"version\": %u, \"meshes\": %u, \"parts\": %u, \"meshlets\": %u, \"vertices\": %u, \"placements\": %u",
            mh.version,mh.mesh_count,mh.part_count,mh.meshlet_count,mh.vertex_count,h.placements);
        float lo[3]={3e38f,3e38f,3e38f},hi[3]={-3e38f,-3e38f,-3e38f};
        float blo[3]={3e38f,3e38f,3e38f},bhi[3]={-3e38f,-3e38f,-3e38f};
        for(unsigned i=0;i<h.placements;++i){
            const auto& q=placements[i];const auto& r=package.meshes()[q.mesh];
            for(unsigned a=0;a<3;++a){
                const float t=q.affine[4*a+3];
                if(t<lo[a])lo[a]=t;
                if(t>hi[a])hi[a]=t;
                // world box of the mesh bounds under the placement (the cull test's box)
                float c0=t,c1=t;
                for(unsigned b=0;b<3;++b){
                    const float x0=q.affine[4*a+b]*r.bounds_min[b],x1=q.affine[4*a+b]*r.bounds_max[b];
                    c0+=x0<x1?x0:x1;c1+=x0<x1?x1:x0;
                }
                if(c0<blo[a])blo[a]=c0;
                if(c1>bhi[a])bhi[a]=c1;
            }
        }
        std::printf(", \"translation_min\": [%.1f, %.1f, %.1f], \"translation_max\": [%.1f, %.1f, %.1f]",lo[0],lo[1],lo[2],hi[0],hi[1],hi[2]);
        std::printf(", \"world_min\": [%.1f, %.1f, %.1f], \"world_max\": [%.1f, %.1f, %.1f]",blo[0],blo[1],blo[2],bhi[0],bhi[1],bhi[2]);
        std::printf(", \"part_keys\": [");
        for(unsigned i=0;i<h.parts;++i){
            const auto& q=parts[i];
            std::printf("%s[\"%08x\", \"%08x\", %u, %u, %u, %u]",i?", ":"",q.crc,q.fnv,q.width,q.height,q.pass,q.cull);
        }
        std::printf("]");
    }
    std::printf("}\n");
    return ok?0:1;
}
